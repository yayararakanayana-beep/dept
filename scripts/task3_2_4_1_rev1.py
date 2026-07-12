"""Task 3.2-4.1 Rev1 formal runner.

Rev1 integrates structural-truth revision, four continuation assumptions,
adaptive action-boundary search, and a lightweight prediction validation with
a pre-holdout selection lock.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from task3_2_4_1_rev1_common import (
    BranchBudget, CorpusIndex, DEFAULT_CONFIG, Entry, ROOT, Rev1Error,
    canonical_hash, continuation_schedule, file_sha256, generate_coarse_branches,
    json_dump, json_load, load_config, native, t41, write_csv,
)
from task3_2_4_1_rev1_boundaries import (
    aggregate_branches, detect_boundaries, probability_boundary_replicates,
    refine_boundaries,
)
from task3_2_4_1_rev1_prediction import (
    audit_feature_names, evaluate_predictions, feature_names, fit_predictor,
    predict, selection_key, time_confounding_audit,
)
from task3_2_4_1_rev1_truth import condition_truth, structural_truth_from_branches

# Stable alias used by focused tests and downstream audits.
_condition_truth = condition_truth


def write_manifest(root: Path) -> dict[str, Any]:
    files = [
        {"path": path.relative_to(root).as_posix(), "size_bytes": path.stat().st_size, "sha256": file_sha256(path)}
        for path in sorted(root.rglob("*")) if path.is_file() and path.name != "manifest.json"
    ]
    manifest = {
        "file_count": len(files),
        "total_size_bytes": sum(int(row["size_bytes"]) for row in files),
        "files": files,
    }
    json_dump(root / "manifest.json", manifest)
    return manifest


def validate_manifest(root: Path) -> dict[str, Any]:
    manifest = json_load(root / "manifest.json")
    for row in manifest["files"]:
        path = root / row["path"]
        if not path.is_file() or path.stat().st_size != int(row["size_bytes"]) or file_sha256(path) != row["sha256"]:
            raise Rev1Error(f"manifest mismatch: {row['path']}")
    return manifest


def run_split(
    entries: Sequence[Entry], safe: Mapping[str, Any], config: Mapping[str, Any], budget: BranchBudget
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], pd.DataFrame, list[dict[str, Any]]]:
    coarse = generate_coarse_branches(entries, safe, config, budget)
    candidates, nonmonotonic = detect_boundaries(aggregate_branches(coarse))
    boundary = refine_boundaries(candidates, entries, safe, config, budget)
    probability = probability_boundary_replicates(boundary, entries, safe, config, budget)
    truth = structural_truth_from_branches([*coarse, *boundary, *probability], nonmonotonic, config)
    return coarse, boundary, probability, truth, [*candidates, *nonmonotonic]


def prediction_frames(
    fit_entries: Sequence[Entry], target_entries: Sequence[Entry], truth: pd.DataFrame,
    config: Mapping[str, Any], task3_config: Mapping[str, Any], calibration: Mapping[str, Any],
    required_arrays: Sequence[str], *, preprocessor: Any = None, dynamics: Any = None,
    fit_series: Any = None,
) -> tuple[pd.DataFrame, Any, Any, list[str], list[str]]:
    return t41.feature_frame(
        fit_entries, target_entries, truth, config, task3_config, calibration,
        required_arrays, preprocessor=preprocessor, dynamics=dynamics, fit_series=fit_series,
    )


def write_contracts(output: Path, config: Mapping[str, Any], index: CorpusIndex, safe: Mapping[str, Any]) -> None:
    outputs = config["outputs"]
    json_dump(output / outputs["safe_region_schema"], safe)
    json_dump(output / outputs["split_manifest"], index.split_manifest())
    json_dump(output / outputs["branch_contract"], {
        "source_snapshot_is_immutable": True,
        "branch_world_is_new_instance": True,
        "primary_continuations": config["branch_probe"]["primary_conditions"],
        "adaptive_boundary": True,
        "conditional_escape_cost": True,
        "source_trajectory_writeback": False,
        "parameter_box_write": False,
        "action_module_connection": False,
    })
    json_dump(output / outputs["continuation_contract"], {
        "conditions": config["branch_probe"]["continuation_conditions"],
        "C0_role": "legacy sensitivity only",
        "C1_role": "immediate disturbance removal sensitivity only",
        "C2_role": "realized environment primary truth",
        "C3_role": "same-seed stable environment intrinsic truth",
        "conditions_are_not_averaged": True,
    })
    json_dump(output / outputs["structural_truth_schema"], {
        "labels": [
            "structural_contraction", "dangerous_shrinking", "irreversibility_progression",
            "environment_dependent_deterioration", "intrinsic_recovery_loss",
        ],
        "escape_observability_separate_from_conditional_cost": True,
        "reachable_range_components": [
            "geometric_outcome_spread", "successful_family_diversity", "safe_reachable_range"
        ],
        "future_side_only": True,
    })
    json_dump(output / outputs["boundary_schema"], config["adaptive_boundary"])


def run(corpus_dir: str | Path, output_dir: str | Path, config_path: str | Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = load_config(config_path)
    output = Path(output_dir)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    index = CorpusIndex(corpus_dir, config)
    fit_entries = index.entries_for("fit")
    validation_entries = index.entries_for("validation")
    safe = t41.calibrate_safe_region(fit_entries, config)
    write_contracts(output, config, index, safe)

    budget = BranchBudget(int(config["budget"]["absolute_maximum_branches"]))
    fit_coarse, fit_boundary, fit_probability, fit_truth, fit_ledger = run_split(
        fit_entries, safe, config, budget
    )
    validation_coarse, validation_boundary, validation_probability, validation_truth, validation_ledger = run_split(
        validation_entries, safe, config, budget
    )

    task3_config = json_load(ROOT / config["task3_config_path"])
    calibration = json_load(ROOT / config["calibration_config_path"])
    contract = json_load(ROOT / config["task1_contract_path"])
    required_arrays = list(contract["step_record"]["required_state_arrays"])
    fit_series = t41._load_series(fit_entries, task3_config, calibration)
    fit_features, preprocessor, dynamics, task3_names, macro_names = prediction_frames(
        fit_entries, fit_entries, fit_truth, config, task3_config, calibration,
        required_arrays, fit_series=fit_series,
    )
    validation_features, _, _, _, _ = prediction_frames(
        fit_entries, validation_entries, validation_truth, config, task3_config, calibration,
        required_arrays, preprocessor=preprocessor, dynamics=dynamics, fit_series=fit_series,
    )

    comparison: list[dict[str, Any]] = []
    validation_predictions: dict[str, pd.DataFrame] = {}
    for family in config["prediction"]["candidate_families"]:
        features = feature_names(family, task3_names, macro_names)
        model = fit_predictor(fit_features, features, config)
        predictions = predict(model, validation_features, config)
        comparison.append({
            "candidate_family": family,
            "feature_count": len(features),
            "features": features,
            "metrics": evaluate_predictions(predictions, config),
        })
        validation_predictions[family] = predictions
    primary = str(config["prediction"]["selection_primary_target"])
    selected = max(comparison, key=lambda row: selection_key(row, primary))
    selected_family = str(selected["candidate_family"])
    selected_validation = validation_predictions[selected_family]
    truth_hash = canonical_hash(
        pd.concat([fit_truth, validation_truth], ignore_index=True)
        .sort_values(["trajectory_id", "snapshot_step"]).to_dict(orient="records")
    )
    outputs = config["outputs"]
    lock = t41._create_lock(
        output / outputs["selection_lock"],
        {
            "candidate_family": selected_family,
            "features": selected["features"],
            "binary_targets": config["prediction"]["binary_targets"],
            "continuous_targets": config["prediction"]["continuous_targets"],
            "time_feature_forbidden": True,
        },
        safe, config, truth_hash,
    )
    t41._write_lock_validation(output / outputs["selection_lock_validation"], lock)
    time_audit = time_confounding_audit(validation_truth, selected_validation)
    json_dump(output / outputs["time_confounding_audit"], time_audit)
    json_dump(output / outputs["validation_metrics"], {
        "selected_candidate": selected,
        "all_candidates": comparison,
    })
    write_csv(output / outputs["validation_predictions"], selected_validation.to_dict(orient="records"))

    holdout_entries = index.entries_for(
        "holdout",
        lock_path=output / outputs["selection_lock"],
        validation_path=output / outputs["selection_lock_validation"],
    )
    holdout_coarse, holdout_boundary, holdout_probability, holdout_truth, holdout_ledger = run_split(
        holdout_entries, safe, config, budget
    )
    holdout_features, _, _, _, _ = prediction_frames(
        fit_entries, holdout_entries, holdout_truth, config, task3_config, calibration,
        required_arrays, preprocessor=preprocessor, dynamics=dynamics, fit_series=fit_series,
    )
    final_model = fit_predictor(
        pd.concat([fit_features, validation_features], ignore_index=True), selected["features"], config
    )
    holdout_predictions = predict(final_model, holdout_features, config)
    holdout_metrics = evaluate_predictions(holdout_predictions, config)

    all_coarse = [*fit_coarse, *validation_coarse, *holdout_coarse]
    all_boundary = [*fit_boundary, *validation_boundary, *holdout_boundary]
    all_probability = [*fit_probability, *validation_probability, *holdout_probability]
    all_truth = pd.concat([fit_truth, validation_truth, holdout_truth], ignore_index=True)
    all_ledger = [*fit_ledger, *validation_ledger, *holdout_ledger]
    if budget.coarse != int(config["budget"]["expected_coarse_branches"]):
        raise Rev1Error(f"formal coarse branch count mismatch: {budget.coarse}")
    if budget.boundary > int(config["budget"]["maximum_boundary_branches"]):
        raise Rev1Error("boundary budget exceeded")
    if budget.probability > int(config["budget"]["maximum_probability_branches"]):
        raise Rev1Error("probability budget exceeded")

    write_csv(output / outputs["coarse_branches"], all_coarse)
    write_csv(output / outputs["boundary_branches"], all_boundary)
    write_csv(output / outputs["probability_branches"], all_probability)
    write_csv(output / outputs["structural_truth"], all_truth.to_dict(orient="records"))
    write_csv(output / outputs["boundary_ledger"], all_ledger)
    comparison_rows = [{
        "candidate_family": row["candidate_family"],
        "feature_count": row["feature_count"],
        "dangerous_shrinking_ap": row["metrics"]["binary"]["dangerous_shrinking"]["average_precision"],
        "mean_variable_binary_ap": row["metrics"]["mean_variable_binary_ap"],
        "c3_escape_observed_ap": row["metrics"]["binary"]["c3_escape_observed"]["average_precision"],
        "mean_continuous_rank": row["metrics"]["mean_continuous_rank"],
        "mean_continuous_mae": row["metrics"]["mean_continuous_mae"],
        "selected": int(row["candidate_family"] == selected_family),
    } for row in comparison]
    write_csv(output / outputs["prediction_comparison"], comparison_rows)
    write_csv(output / outputs["holdout_predictions"], holdout_predictions.to_dict(orient="records"))
    json_dump(output / outputs["holdout_metrics"], holdout_metrics)
    budget_value = {
        "coarse": budget.coarse, "boundary": budget.boundary, "probability": budget.probability,
        "total": budget.used, "absolute_maximum": budget.maximum,
    }
    json_dump(output / outputs["branch_budget"], budget_value)

    current = next(row for row in comparison if row["candidate_family"] == "current_risk")
    prediction_gain = (
        float(selected["metrics"]["mean_variable_binary_ap"])
        > float(current["metrics"]["mean_variable_binary_ap"]) + 0.03
        or float(selected["metrics"]["binary"][primary]["average_precision"])
        > float(current["metrics"]["binary"][primary]["average_precision"]) + 0.05
    )
    dangerous_variation = 0 < int(all_truth["dangerous_shrinking"].sum()) < len(all_truth)
    time_dominates = (
        float(time_audit["step_ge_28"]["average_precision"])
        >= float(selected["metrics"]["binary"][primary]["average_precision"])
    )
    holdout_primary = holdout_metrics["binary"][primary]
    if dangerous_variation and prediction_gain and not time_dominates and float(holdout_primary["average_precision"]) >= 0.60:
        grade = "A_rev1_structural_truth_and_prediction_promising"
    elif dangerous_variation and budget.used <= budget.maximum:
        grade = "B_rev1_structural_truth_valid_prediction_limited"
    else:
        grade = "C_rev1_requires_additional_revision"
    summary = {
        "task_id": config["task_id"],
        "status": "complete",
        "grade": grade,
        "selected_candidate": selected_family,
        "branch_budget": budget_value,
        "trajectory_count": len(index.entries),
        "state_count": len(all_truth),
        "dangerous_shrinking_count": int(all_truth["dangerous_shrinking"].sum()),
        "structural_contraction_count": int(all_truth["structural_contraction"].sum()),
        "environment_dependent_deterioration_count": int(all_truth["environment_dependent_deterioration"].sum()),
        "intrinsic_recovery_loss_count": int(all_truth["intrinsic_recovery_loss"].sum()),
        "action_boundary_state_count": int(all_truth["action_boundary_exists"].sum()),
        "nonmonotonic_action_state_count": int(all_truth["nonmonotonic_action_response"].sum()),
        "validation_selected_metrics": selected["metrics"],
        "holdout_metrics": holdout_metrics,
        "time_confounding_audit": time_audit,
        "selection_lock_hash": lock["lock_hash"],
        "holdout_state_read_gate": "passed",
        "source_trajectory_writeback": False,
        "parameter_box_write": False,
        "action_module_connection": False,
        "universal_irreversibility_claim": False,
    }
    json_dump(output / "summary.json", summary)
    (output / outputs["results_markdown"]).write_text(
        f"""# Task 3.2-4.1 Rev1 結果

- 判定: `{grade}`
- 軌道: {len(index.entries)}
- 状態: {len(all_truth)}
- 分岐: {budget.used} / {budget.maximum}
- 選択予測器: `{selected_family}`
- 構造縮小: {int(all_truth['structural_contraction'].sum())}
- 危険な縮小: {int(all_truth['dangerous_shrinking'].sum())}
- 環境依存悪化: {int(all_truth['environment_dependent_deterioration'].sum())}
- 内在的回復能力喪失: {int(all_truth['intrinsic_recovery_loss'].sum())}
- 作用境界あり: {int(all_truth['action_boundary_exists'].sum())}

Rev1は構造正解、分岐継続仮定、作用境界探索を統合し、簡易予測検証をselection lock後のholdoutで評価した。
""",
        encoding="utf-8",
    )
    (output / outputs["completion_markdown"]).write_text(
        "# Task 3.2-4.1 Rev1 Completion\n\n"
        f"Status: complete\n\nGrade: `{grade}`\n\n"
        "All formal boundaries, holdout gate, manifest validation, and no-writeback contracts are enforced.\n",
        encoding="utf-8",
    )
    (output / outputs["handoff_markdown"]).write_text(
        "# Task 3.2-4.1 Rev1 Handoff\n\n"
        f"Selected predictor: `{selected_family}`\n\nGrade: `{grade}`\n\n"
        "Use Rev1 structural truth outputs for the next design review. Do not treat probe-set-conditional escape failure as universal irreversibility.\n",
        encoding="utf-8",
    )
    manifest = write_manifest(output)
    return {**summary, "manifest_file_count": manifest["file_count"]}


def validate_output(input_dir: str | Path, config_path: str | Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = load_config(config_path)
    root = Path(input_dir)
    required = set(config["outputs"].values()) | {"summary.json"}
    missing = sorted(name for name in required if not (root / name).is_file())
    if missing:
        raise Rev1Error(f"Rev1 output missing {missing}")
    manifest = validate_manifest(root)
    summary = json_load(root / "summary.json")
    if summary.get("status") != "complete":
        raise Rev1Error("Rev1 summary is not complete")
    if int(summary["branch_budget"]["coarse"]) != int(config["budget"]["expected_coarse_branches"]):
        raise Rev1Error("Rev1 coarse branch contract failed")
    if int(summary["branch_budget"]["total"]) > int(config["budget"]["absolute_maximum_branches"]):
        raise Rev1Error("Rev1 absolute branch budget failed")
    if summary.get("holdout_state_read_gate") != "passed":
        raise Rev1Error("Rev1 holdout gate failed")
    if summary.get("source_trajectory_writeback") is not False:
        raise Rev1Error("Rev1 source writeback boundary failed")
    if summary.get("parameter_box_write") is not False or summary.get("action_module_connection") is not False:
        raise Rev1Error("Rev1 external boundary failed")
    truth = pd.read_csv(root / config["outputs"]["structural_truth"])
    required_truth = {
        "structural_contraction", "dangerous_shrinking", "irreversibility_progression",
        "c2_escape_observed", "c3_escape_observed", "c2_conditional_escape_cost",
        "c3_conditional_escape_cost", "environment_dependent_deterioration",
        "intrinsic_recovery_loss", "action_boundary_exists", "c3_safe_reachable_range",
    }
    if not required_truth.issubset(truth.columns) or len(truth) != 90:
        raise Rev1Error("Rev1 structural truth schema/count failed")
    return {
        "status": "valid", "grade": summary["grade"],
        "selected_candidate": summary["selected_candidate"],
        "total_branches": summary["branch_budget"]["total"],
        "state_count": len(truth), "manifest_file_count": manifest["file_count"],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    execute = sub.add_parser("run")
    execute.add_argument("--corpus", required=True)
    execute.add_argument("--output", required=True)
    execute.add_argument("--config", default=str(DEFAULT_CONFIG))
    check = sub.add_parser("validate")
    check.add_argument("--input", required=True)
    check.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args(argv)
    result = run(args.corpus, args.output, args.config) if args.command == "run" else validate_output(args.input, args.config)
    print(json.dumps(native(result), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "BranchBudget", "Entry", "Rev1Error", "_condition_truth", "aggregate_branches",
    "audit_feature_names", "continuation_schedule", "detect_boundaries",
    "evaluate_predictions", "fit_predictor", "load_config", "predict", "run",
    "structural_truth_from_branches", "validate_output",
]
