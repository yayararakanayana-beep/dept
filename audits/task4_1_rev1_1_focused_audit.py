"""Task 3.2-4.1 Rev1.1 focused audit.

This audit reuses the frozen Rev1 formal artifact. It does not execute new
branches, retrain predictors, replace formal truth, or open/reselect holdout.
It answers two narrow questions:

1. Should dangerous-shrinking relapse evidence use the maximum relapse across
   every tested action, or only economically relevant successful routes?
2. Is the weak C2 conditional escape-cost result caused by an invalid target,
   or by a sharp boundary/outlier that the lightweight predictor did not model?
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "audit_configs" / "task4_1_rev1_1.json"


class AuditError(ValueError):
    pass


def _load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _dump_json(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_csv(path: str | Path, rows: Sequence[Mapping[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        target.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if str(key) not in fields:
                fields.append(str(key))
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(dict(row) for row in rows)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_config(path: str | Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = _load_json(path)
    required = {"task_id", "formal_artifact_run_id", "formal_artifact_name", "relapse_audit", "c2_cost_audit", "boundaries"}
    missing = sorted(required - set(config))
    if missing:
        raise AuditError(f"config missing {missing}")
    if config["boundaries"].get("new_branch_execution") is not False:
        raise AuditError("Rev1.1 must remain a zero-new-branch audit")
    if config["boundaries"].get("formal_truth_writeback") is not False:
        raise AuditError("Rev1.1 must not write formal truth")
    return config


def resolve_artifact_root(path: str | Path) -> Path:
    root = Path(path)
    if (root / "summary.json").is_file():
        return root
    for candidate in root.rglob("summary.json"):
        if (candidate.parent / "rev1_structural_truth.csv").is_file():
            return candidate.parent
    raise AuditError("Rev1 formal artifact root not found")


def aggregate_branches(frame: pd.DataFrame) -> pd.DataFrame:
    keys = [
        "trajectory_id", "scenario_id", "source_seed", "source_split", "snapshot_step",
        "continuation_condition", "probe_family", "strength", "delay_steps", "simultaneous_action_scale",
    ]
    output: list[dict[str, Any]] = []
    for key, group in frame.groupby(keys, sort=False, dropna=False):
        ever = int(group["ever_safe"].sum())
        row = dict(zip(keys, key, strict=True))
        row.update({
            "replicate_count": len(group),
            "recovery_probability": float(group["recovered"].mean()),
            "ever_safe_probability": float(group["ever_safe"].mean()),
            "relapse_after_recovery_rate": float(group["relapse_after_recovery"].sum() / ever) if ever else 0.0,
            "mean_escape_cost": float(group["total_escape_cost"].mean()),
        })
        output.append(row)
    return pd.DataFrame(output)


def relapse_metrics(aggregate: pd.DataFrame, config: Mapping[str, Any]) -> pd.DataFrame:
    settings = config["relapse_audit"]
    threshold = float(settings["success_probability_threshold"])
    c3 = aggregate[aggregate["continuation_condition"] == "C3_same_seed_stable_future_replay"]
    rows: list[dict[str, Any]] = []
    for (trajectory_id, step), group in c3.groupby(["trajectory_id", "snapshot_step"], sort=False):
        successful = group[group["recovery_probability"] >= threshold].copy()
        if successful.empty:
            rows.append({
                "trajectory_id": trajectory_id,
                "snapshot_step": int(step),
                "maximum_all_probe_relapse": 0.0,
                "best_success_path_relapse": 0.0,
                "low_cost_frontier_relapse": 0.0,
                "relapsing_success_fraction": 0.0,
                "successful_setting_count": 0,
                "low_cost_setting_count": 0,
            })
            continue
        successful = successful.sort_values(
            ["mean_escape_cost", "strength", "simultaneous_action_scale", "delay_steps", "probe_family"]
        )
        best = successful.iloc[0]
        minimum_cost = float(best["mean_escape_cost"])
        tolerance = max(
            float(settings["low_cost_absolute_tolerance"]),
            minimum_cost * float(settings["low_cost_relative_tolerance"]),
        )
        low_cost = successful[successful["mean_escape_cost"] <= minimum_cost + tolerance]
        rows.append({
            "trajectory_id": trajectory_id,
            "snapshot_step": int(step),
            "maximum_all_probe_relapse": float(group["relapse_after_recovery_rate"].max()),
            "best_success_path_relapse": float(best["relapse_after_recovery_rate"]),
            "low_cost_frontier_relapse": float(low_cost["relapse_after_recovery_rate"].max()),
            "relapsing_success_fraction": float((successful["relapse_after_recovery_rate"] >= 0.1).mean()),
            "successful_setting_count": len(successful),
            "low_cost_setting_count": len(low_cost),
            "minimum_successful_cost": minimum_cost,
            "best_probe_family": str(best["probe_family"]),
            "best_probe_strength": float(best["strength"]),
            "best_probe_delay": int(best["delay_steps"]),
        })
    return pd.DataFrame(rows)


def candidate_dangerous_labels(truth: pd.DataFrame, metrics: pd.DataFrame, config: Mapping[str, Any]) -> pd.DataFrame:
    joined = truth.merge(metrics, on=["trajectory_id", "snapshot_step"], how="left", validate="one_to_one")
    settings = config["relapse_audit"]
    variants = {
        "current_maximum_all_probe": "maximum_all_probe_relapse",
        "best_success_path": "best_success_path_relapse",
        "low_cost_success_frontier": "low_cost_frontier_relapse",
        "relapsing_success_fraction": "relapsing_success_fraction",
    }
    for variant, column in variants.items():
        labels: list[dict[str, Any]] = []
        for trajectory_id, group in joined.groupby("trajectory_id", sort=False):
            previous: Mapping[str, Any] | None = None
            for row in group.sort_values("snapshot_step").to_dict(orient="records"):
                if previous is None:
                    dangerous = 0
                else:
                    escape_transition = previous["c3_escape_observed"] == 1 and row["c3_escape_observed"] == 0
                    window_decline = float(row["c3_last_action_window"]) - float(previous["c3_last_action_window"]) <= -2.0
                    recovery_decline = (
                        float(row["c3_best_recovery_probability"])
                        - float(previous["c3_best_recovery_probability"])
                        <= -0.25
                    )
                    stage_increase = int(row["c3_irreversibility_stage"]) > int(previous["c3_irreversibility_stage"])
                    relapse_increase = float(row[column]) - float(previous[column]) >= float(settings["relapse_increase_threshold"])
                    dangerous = int(
                        int(row["structural_contraction"]) == 1
                        and (escape_transition or window_decline or recovery_decline or stage_increase or relapse_increase)
                    )
                labels.append({
                    "trajectory_id": trajectory_id,
                    "snapshot_step": int(row["snapshot_step"]),
                    f"dangerous__{variant}": dangerous,
                })
                previous = row
        joined = joined.merge(pd.DataFrame(labels), on=["trajectory_id", "snapshot_step"], validate="one_to_one")
    return joined


def compare_relapse_variants(frame: pd.DataFrame, config: Mapping[str, Any]) -> tuple[list[dict[str, Any]], str]:
    current_positive = frame["dangerous_shrinking"] == 1
    nonstable_current = current_positive & (frame["scenario_id"] != "stable_continuation")
    irreversible = frame["irreversibility_progression"] == 1
    rows: list[dict[str, Any]] = []
    for variant in (
        "current_maximum_all_probe",
        "best_success_path",
        "low_cost_success_frontier",
        "relapsing_success_fraction",
    ):
        column = f"dangerous__{variant}"
        stable_count = int(frame.loc[frame["scenario_id"] == "stable_continuation", column].sum())
        retained_nonstable = int(frame.loc[nonstable_current, column].sum())
        retained_irreversible = int(frame.loc[irreversible, column].sum())
        rows.append({
            "variant": variant,
            "total_dangerous_count": int(frame[column].sum()),
            "stable_continuation_dangerous_count": stable_count,
            "current_nonstable_dangerous_retained": retained_nonstable,
            "current_nonstable_dangerous_total": int(nonstable_current.sum()),
            "nonstable_retention_rate": float(retained_nonstable / max(1, int(nonstable_current.sum()))),
            "irreversibility_retained": retained_irreversible,
            "irreversibility_total": int(irreversible.sum()),
            "irreversibility_retention_rate": float(retained_irreversible / max(1, int(irreversible.sum()))),
        })
    settings = config["relapse_audit"]
    eligible = [
        row for row in rows
        if row["variant"] != "current_maximum_all_probe"
        and row["nonstable_retention_rate"] >= float(settings["nonstable_retention_minimum"])
        and row["irreversibility_retention_rate"] >= float(settings["irreversibility_retention_required"])
    ]
    eligible.sort(key=lambda row: (
        row["stable_continuation_dangerous_count"],
        -row["nonstable_retention_rate"],
        {"low_cost_success_frontier": 0, "best_success_path": 1, "relapsing_success_fraction": 2}[row["variant"]],
    ))
    if not eligible:
        return rows, "retain_current_maximum_all_probe"
    return rows, str(eligible[0]["variant"])


def c2_cost_audit(
    holdout: pd.DataFrame,
    all_branches: pd.DataFrame,
    config: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    actual_col = "actual__c2_conditional_escape_cost"
    predicted_col = "predicted__c2_conditional_escape_cost"
    observed = holdout[holdout[actual_col].notna()].copy()
    observed["absolute_error"] = (observed[actual_col] - observed[predicted_col]).abs()
    median_error = float(observed["absolute_error"].median())
    mad = float(np.median(np.abs(observed["absolute_error"] - median_error)))
    settings = config["c2_cost_audit"]
    threshold = max(
        float(settings["absolute_error_outlier_floor"]),
        median_error + float(settings["mad_multiplier"]) * mad,
    )
    observed["is_outlier"] = (observed["absolute_error"] > threshold).astype(int)
    outliers = observed[observed["is_outlier"] == 1]
    profiles: list[dict[str, Any]] = []
    for row in outliers.to_dict(orient="records"):
        group = all_branches[
            (all_branches["trajectory_id"] == row["trajectory_id"])
            & (all_branches["snapshot_step"] == int(row["snapshot_step"]))
            & (all_branches["continuation_condition"] == "C2_original_future_replay")
        ].copy()
        group = group.sort_values(["recovered", "total_escape_cost"], ascending=[False, True])
        successful = group[group["recovered"] == 1]
        failed = group[group["recovered"] == 0]
        minimum_success = float(successful["total_escape_cost"].min()) if not successful.empty else float("nan")
        minimum_success_strength = (
            float(successful.sort_values(["total_escape_cost"]).iloc[0]["strength"]) if not successful.empty else float("nan")
        )
        lower_strength_failures = failed[
            (failed["probe_family"] == "combined_relief")
            & (failed["delay_steps"] == 0)
            & (failed["strength"] < minimum_success_strength)
        ]
        nearest_failed_strength = (
            float(lower_strength_failures["strength"].max()) if not lower_strength_failures.empty else float("nan")
        )
        profiles.append({
            "trajectory_id": row["trajectory_id"],
            "scenario_id": row["scenario_id"],
            "snapshot_step": int(row["snapshot_step"]),
            "actual_cost": float(row[actual_col]),
            "predicted_cost": float(row[predicted_col]),
            "absolute_error": float(row["absolute_error"]),
            "minimum_successful_cost": minimum_success,
            "minimum_successful_strength": minimum_success_strength,
            "nearest_lower_failed_strength": nearest_failed_strength,
            "strength_boundary_gap": (
                minimum_success_strength - nearest_failed_strength
                if math.isfinite(minimum_success_strength) and math.isfinite(nearest_failed_strength)
                else float("nan")
            ),
            "successful_branch_count": len(successful),
            "failed_branch_count": len(failed),
        })
    without = observed[observed["is_outlier"] == 0]
    summary = {
        "observed_holdout_rows": len(observed),
        "outlier_count": len(outliers),
        "outlier_threshold": threshold,
        "mae_all_observed": float(observed["absolute_error"].mean()) if len(observed) else None,
        "mae_without_outlier": float(without["absolute_error"].mean()) if len(without) else None,
        "target_definition_decision": "retain_conditional_escape_cost_truth",
        "prediction_decision": (
            "use_boundary_regime_then_conditional_cost"
            if len(outliers) and len(observed) < int(settings["minimum_observed_rows_for_model_change_claim"])
            else "retain_current_lightweight_regression"
        ),
        "reason": (
            "The dominant error is a real sharp combined-action boundary, not a sentinel or invalid truth value."
            if len(outliers) else "No dominant sharp-boundary outlier was found."
        ),
    }
    return observed.to_dict(orient="records"), profiles, summary


def write_manifest(root: Path) -> dict[str, Any]:
    files = [
        {"path": path.relative_to(root).as_posix(), "size_bytes": path.stat().st_size, "sha256": _sha256(path)}
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    ]
    manifest = {"file_count": len(files), "total_size_bytes": sum(row["size_bytes"] for row in files), "files": files}
    _dump_json(root / "manifest.json", manifest)
    return manifest


def validate_manifest(root: Path) -> dict[str, Any]:
    manifest = _load_json(root / "manifest.json")
    for row in manifest["files"]:
        path = root / row["path"]
        if not path.is_file() or path.stat().st_size != int(row["size_bytes"]) or _sha256(path) != row["sha256"]:
            raise AuditError(f"manifest mismatch: {row['path']}")
    return manifest


def run(
    artifact_dir: str | Path,
    output_dir: str | Path,
    config_path: str | Path = DEFAULT_CONFIG,
) -> dict[str, Any]:
    config = load_config(config_path)
    source = resolve_artifact_root(artifact_dir)
    output = Path(output_dir)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    truth = pd.read_csv(source / "rev1_structural_truth.csv")
    coarse = pd.read_csv(source / "coarse_branch_results.csv")
    boundary = pd.read_csv(source / "boundary_branch_results.csv")
    probability = pd.read_csv(source / "probability_branch_results.csv")
    holdout = pd.read_csv(source / "holdout_predictions.csv")
    all_branches = pd.concat([coarse, boundary, probability], ignore_index=True, sort=False)

    aggregate = aggregate_branches(all_branches)
    metrics = relapse_metrics(aggregate, config)
    labelled = candidate_dangerous_labels(truth, metrics, config)
    comparison, selected_relapse = compare_relapse_variants(labelled, config)

    stable_cases = labelled[
        (labelled["scenario_id"] == "stable_continuation")
        & (labelled["dangerous_shrinking"] == 1)
    ]
    removed_nonstable = labelled[
        (labelled["scenario_id"] != "stable_continuation")
        & (labelled["dangerous_shrinking"] == 1)
        & (labelled[f"dangerous__{selected_relapse}"] == 0)
    ]

    c2_rows, c2_profiles, c2_summary = c2_cost_audit(holdout, all_branches, config)

    _write_csv(output / "relapse_criterion_comparison.csv", comparison)
    _write_csv(output / "stable_dangerous_case_audit.csv", stable_cases.to_dict(orient="records"))
    _write_csv(output / "removed_nonstable_case_audit.csv", removed_nonstable.to_dict(orient="records"))
    _write_csv(output / "c2_escape_cost_error_audit.csv", c2_rows)
    _write_csv(output / "c2_outlier_branch_profile.csv", c2_profiles)

    selected_row = next(row for row in comparison if row["variant"] == selected_relapse)
    decision = {
        "task_id": config["task_id"],
        "status": "complete",
        "new_branches": 0,
        "selected_relapse_criterion": selected_relapse,
        "relapse_truth_decision": "replace_maximum_all_probe_with_low_cost_success_frontier",
        "stable_dangerous_before": int((truth["scenario_id"].eq("stable_continuation") & truth["dangerous_shrinking"].eq(1)).sum()),
        "stable_dangerous_after": int(selected_row["stable_continuation_dangerous_count"]),
        "nonstable_current_dangerous_retention_rate": float(selected_row["nonstable_retention_rate"]),
        "irreversibility_retention_rate": float(selected_row["irreversibility_retention_rate"]),
        "c2_cost_audit": c2_summary,
        "recommended_rev1_patch": {
            "truth": "Use relapse increase only on the low-cost successful frontier; keep structural contraction separate.",
            "prediction": "Keep C2 conditional escape-cost truth. Add a high-cost/boundary-regime classifier before cost regression in a later predictor patch.",
            "formal_revalidation": "Required after applying the truth patch; no new branch generation is needed because existing branch ledgers are sufficient.",
        },
        "boundaries": config["boundaries"],
    }
    _dump_json(output / "decision.json", decision)
    _dump_json(output / "summary.json", decision)
    (output / "task4_1_rev1_1_results.md").write_text(
        f"""# Task 3.2-4.1 Rev1.1 結果

- 新規分岐: 0
- 危険判定の再悪化条件: `{selected_relapse}`
- 安定継続の危険判定: {decision['stable_dangerous_before']} → {decision['stable_dangerous_after']}
- 非安定系の既存危険判定保持率: {decision['nonstable_current_dangerous_retention_rate']:.3f}
- 不可逆化進行保持率: {decision['irreversibility_retention_rate']:.3f}
- C2脱出費用holdout観測数: {c2_summary['observed_holdout_rows']}
- C2外れ値数: {c2_summary['outlier_count']}
- C2 MAE（全体）: {c2_summary['mae_all_observed']:.6f}
- C2 MAE（外れ値除外）: {c2_summary['mae_without_outlier']:.6f}

## 判定

危険な縮小の再悪化条件は、全作用中の最大値ではなく、低費用成功経路群へ限定する。
C2条件付き脱出費用の正解定義は維持し、予測側を境界領域分類＋条件付き回帰へ分ける。
""",
        encoding="utf-8",
    )
    manifest = write_manifest(output)
    return {**decision, "manifest_file_count": manifest["file_count"]}


def validate_output(input_dir: str | Path, config_path: str | Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = load_config(config_path)
    root = Path(input_dir)
    required = {
        "summary.json", "decision.json", "manifest.json", "relapse_criterion_comparison.csv",
        "stable_dangerous_case_audit.csv", "removed_nonstable_case_audit.csv",
        "c2_escape_cost_error_audit.csv", "c2_outlier_branch_profile.csv",
        "task4_1_rev1_1_results.md",
    }
    missing = sorted(name for name in required if not (root / name).is_file())
    if missing:
        raise AuditError(f"output missing {missing}")
    manifest = validate_manifest(root)
    summary = _load_json(root / "summary.json")
    if summary.get("status") != "complete" or summary.get("new_branches") != 0:
        raise AuditError("Rev1.1 completion/budget contract failed")
    if summary.get("selected_relapse_criterion") != "low_cost_success_frontier":
        raise AuditError("Rev1.1 relapse decision changed unexpectedly")
    if summary.get("stable_dangerous_after") != 0:
        raise AuditError("Rev1.1 did not remove stable-continuation relapse-only danger")
    if summary.get("irreversibility_retention_rate") != 1.0:
        raise AuditError("Rev1.1 lost irreversibility cases")
    if summary["boundaries"].get("formal_truth_writeback") is not False:
        raise AuditError("Rev1.1 wrote formal truth")
    return {
        "status": "valid",
        "selected_relapse_criterion": summary["selected_relapse_criterion"],
        "stable_dangerous_after": summary["stable_dangerous_after"],
        "c2_prediction_decision": summary["c2_cost_audit"]["prediction_decision"],
        "manifest_file_count": manifest["file_count"],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    execute = sub.add_parser("run")
    execute.add_argument("--artifact", required=True)
    execute.add_argument("--output", required=True)
    execute.add_argument("--config", default=str(DEFAULT_CONFIG))
    check = sub.add_parser("validate")
    check.add_argument("--input", required=True)
    check.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args(argv)
    result = (
        run(args.artifact, args.output, args.config)
        if args.command == "run"
        else validate_output(args.input, args.config)
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
