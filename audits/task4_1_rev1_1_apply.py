"""Apply the frozen Task 4.1 Rev1.1 decisions without rerunning branches.

The runner reuses the Rev1 formal branch ledgers, rebuilds structural truth with
low-cost-success-frontier relapse semantics, keeps the original locked Task 4
feature family, and revalidates a fixed two-stage C2 conditional-cost model.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT, ROOT / "scripts", ROOT / "audits"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import task3_2_4_1_rev1 as rev1  # noqa: E402
import task3_2_4_1_rev1_common as common  # noqa: E402
from task3_2_4_1_rev1_boundaries import aggregate_branches  # noqa: E402
from task3_2_4_1_rev1_prediction import evaluate_predictions, time_confounding_audit  # noqa: E402
from task3_2_4_1_rev1_truth import structural_truth_from_branches  # noqa: E402

DEFAULT_CONFIG = ROOT / "audit_configs" / "task4_1_rev1_1_apply.json"


class ApplyError(ValueError):
    pass


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dump_json(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(common.native(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_csv(path: str | Path, rows: Sequence[Mapping[str, Any]]) -> None:
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
        for row in rows:
            writer.writerow({key: common.native(value) for key, value in dict(row).items()})


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_config(path: str | Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = load_json(path)
    required = {
        "task_id", "base_config_path", "formal_artifact_run_id",
        "formal_artifact_name", "selection_contract", "relapse_truth",
        "c2_cost_model", "boundaries",
    }
    missing = sorted(required - set(config))
    if missing:
        raise ApplyError(f"apply config missing {missing}")
    if config["selection_contract"].get("candidate_family") != "task4":
        raise ApplyError("Rev1.1 must reuse the locked Task 4 candidate")
    if config["selection_contract"].get("post_holdout_reselection_forbidden") is not True:
        raise ApplyError("post-holdout reselection must remain forbidden")
    if config["boundaries"].get("new_branch_execution") is not False:
        raise ApplyError("Rev1.1 apply must execute zero new branches")
    return config


def resolve_artifact_root(path: str | Path) -> Path:
    root = Path(path)
    if (root / "summary.json").is_file() and (root / "coarse_branch_results.csv").is_file():
        return root
    for candidate in root.rglob("summary.json"):
        if (candidate.parent / "coarse_branch_results.csv").is_file():
            return candidate.parent
    raise ApplyError("Rev1 formal artifact root not found")


def _clean_branch_frame(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    if "boundary_id" not in result:
        result["boundary_id"] = ""
    result["boundary_id"] = result["boundary_id"].fillna("").astype(str)
    return result


def low_cost_relapse_metrics(
    aggregate: pd.DataFrame,
    apply_config: Mapping[str, Any],
) -> pd.DataFrame:
    settings = apply_config["relapse_truth"]
    threshold = float(settings["success_probability_threshold"])
    output: list[dict[str, Any]] = []
    for key, group in aggregate.groupby(
        ["trajectory_id", "snapshot_step", "continuation_condition"], sort=False
    ):
        successful = group[group["recovery_probability"] >= threshold].copy()
        all_probe = float(group["relapse_after_recovery_rate"].max())
        if successful.empty:
            frontier = 0.0
            frontier_count = 0
        else:
            minimum = float(successful["mean_escape_cost"].min())
            tolerance = max(
                float(settings["low_cost_absolute_tolerance"]),
                minimum * float(settings["low_cost_relative_tolerance"]),
            )
            low_cost = successful[successful["mean_escape_cost"] <= minimum + tolerance]
            frontier = float(low_cost["relapse_after_recovery_rate"].max())
            frontier_count = len(low_cost)
        output.append({
            "trajectory_id": key[0],
            "snapshot_step": int(key[1]),
            "continuation_condition": key[2],
            "all_probe_relapse_after_recovery_rate": all_probe,
            "low_cost_relapse_after_recovery_rate": frontier,
            "low_cost_frontier_setting_count": frontier_count,
        })
    return pd.DataFrame(output)


def patch_truth(
    branch_rows: Sequence[Mapping[str, Any]],
    nonmonotonic_rows: Sequence[Mapping[str, Any]],
    base_config: Mapping[str, Any],
    apply_config: Mapping[str, Any],
) -> pd.DataFrame:
    original = structural_truth_from_branches(branch_rows, nonmonotonic_rows, base_config)
    aggregate = aggregate_branches(branch_rows)
    relapse = low_cost_relapse_metrics(aggregate, apply_config)
    patched = original.copy()
    for prefix, condition in (
        ("c2", "C2_original_future_replay"),
        ("c3", "C3_same_seed_stable_future_replay"),
    ):
        subset = relapse[relapse["continuation_condition"] == condition].drop(
            columns=["continuation_condition"]
        )
        subset = subset.rename(columns={
            "all_probe_relapse_after_recovery_rate": f"{prefix}_all_probe_relapse_after_recovery_rate",
            "low_cost_relapse_after_recovery_rate": f"{prefix}_relapse_after_recovery_rate_patched",
            "low_cost_frontier_setting_count": f"{prefix}_low_cost_frontier_setting_count",
        })
        patched = patched.merge(
            subset, on=["trajectory_id", "snapshot_step"], how="left", validate="one_to_one"
        )
        patched[f"{prefix}_relapse_after_recovery_rate"] = patched[
            f"{prefix}_relapse_after_recovery_rate_patched"
        ]
        patched[f"{prefix}_active_intervention_required"] = (
            patched[f"{prefix}_escape_observed"].eq(1)
            & patched[f"{prefix}_best_probe_family"].ne("no_action")
            & patched[f"{prefix}_best_probe_strength"].fillna(0.0).gt(0.0)
        ).astype(int)

    threshold = float(apply_config["relapse_truth"]["relapse_increase_threshold"])
    labelled: list[dict[str, Any]] = []
    for _, group in patched.groupby("trajectory_id", sort=False):
        previous: Mapping[str, Any] | None = None
        for source in group.sort_values("snapshot_step").to_dict(orient="records"):
            row = dict(source)
            if previous is None:
                row["dangerous_shrinking"] = 0
            else:
                escape_transition = previous["c3_escape_observed"] == 1 and row["c3_escape_observed"] == 0
                window_decline = (
                    float(row["c3_last_action_window"])
                    - float(previous["c3_last_action_window"])
                    <= -float(base_config["structural_truth"]["last_action_window_decline"])
                )
                recovery_decline = (
                    float(row["c3_best_recovery_probability"])
                    - float(previous["c3_best_recovery_probability"])
                    <= -float(base_config["structural_truth"]["recovery_probability_decline"])
                )
                relapse_increase = (
                    float(row["c3_relapse_after_recovery_rate"])
                    - float(previous["c3_relapse_after_recovery_rate"])
                    >= threshold
                )
                stage_increase = int(row["c3_irreversibility_stage"]) > int(previous["c3_irreversibility_stage"])
                row["dangerous_shrinking"] = int(
                    int(row["structural_contraction"]) == 1
                    and (escape_transition or window_decline or recovery_decline or relapse_increase or stage_increase)
                )
            labelled.append(row)
            previous = row
    return pd.DataFrame(labelled)


def _fit_binary(X: np.ndarray, y: np.ndarray, config: Mapping[str, Any]) -> Any:
    if len(np.unique(y)) < 2:
        return {"kind": "constant_probability", "value": float(np.mean(y))}
    return LogisticRegression(
        C=float(config["c2_cost_model"]["logistic_C"]),
        max_iter=3000,
        class_weight="balanced",
        random_state=0,
    ).fit(X, y)


def _fit_regression(X: np.ndarray, y: np.ndarray, alpha: float) -> Any:
    if len(y) == 0:
        return {"kind": "missing"}
    if len(y) < 2 or np.allclose(y, y[0]):
        return {"kind": "constant", "value": float(y[0])}
    return Ridge(alpha=alpha).fit(X, y)


def _regression_predict(model: Any, X: np.ndarray) -> np.ndarray:
    if isinstance(model, dict) and model.get("kind") == "missing":
        return np.full(len(X), np.nan, dtype=np.float64)
    if isinstance(model, dict):
        return np.full(len(X), float(model["value"]), dtype=np.float64)
    return np.asarray(model.predict(X), dtype=np.float64)


def _probability_predict(model: Any, X: np.ndarray) -> np.ndarray:
    if isinstance(model, dict):
        return np.full(len(X), float(model["value"]), dtype=np.float64)
    return np.asarray(model.predict_proba(X)[:, 1], dtype=np.float64)


def effective_prediction_config(base_config: Mapping[str, Any]) -> dict[str, Any]:
    config = json.loads(json.dumps(base_config))
    if "c2_active_intervention_required" not in config["prediction"]["binary_targets"]:
        config["prediction"]["binary_targets"].append("c2_active_intervention_required")
    return config


def fit_fixed_task4_predictor(
    frame: pd.DataFrame,
    features: Sequence[str],
    base_config: Mapping[str, Any],
    apply_config: Mapping[str, Any],
) -> dict[str, Any]:
    X = frame[list(features)].to_numpy(dtype=np.float64)
    scaler = StandardScaler().fit(X)
    transformed = scaler.transform(X)
    effective = effective_prediction_config(base_config)
    models: dict[str, Any] = {}
    for target in effective["prediction"]["binary_targets"]:
        models[target] = _fit_binary(
            transformed, frame[target].to_numpy(dtype=int), apply_config
        )
    alpha = float(apply_config["c2_cost_model"]["ridge_alpha"])
    for target in effective["prediction"]["continuous_targets"]:
        if target == "c2_conditional_escape_cost":
            continue
        valid = frame[target].notna().to_numpy()
        models[target] = _fit_regression(
            transformed[valid], frame.loc[valid, target].to_numpy(dtype=np.float64), alpha
        )

    observed = frame["c2_conditional_escape_cost"].notna().to_numpy()
    active = frame["c2_active_intervention_required"].to_numpy(dtype=int)
    passive_rows = observed & (active == 0)
    active_rows = observed & (active == 1)
    if int(passive_rows.sum()) < int(apply_config["c2_cost_model"]["minimum_passive_samples"]):
        raise ApplyError("insufficient passive C2 cost samples")
    if int(active_rows.sum()) < int(apply_config["c2_cost_model"]["minimum_active_samples"]):
        raise ApplyError("insufficient active C2 cost samples")
    coefficient = (
        max(len(value) for value in base_config["branch_probe"]["action_axes"].values())
        * int(base_config["branch_probe"]["action_duration_steps"])
        * float(base_config["branch_probe"]["cost_weights"]["intensity_axis_step"])
    )
    models["c2_cost_two_stage"] = {
        "passive_cost": _fit_regression(
            transformed[passive_rows],
            frame.loc[passive_rows, "c2_conditional_escape_cost"].to_numpy(dtype=np.float64),
            alpha,
        ),
        "active_strength": _fit_regression(
            transformed[active_rows],
            frame.loc[active_rows, "c2_best_probe_strength"].to_numpy(dtype=np.float64),
            alpha,
        ),
        "active_residual": _fit_regression(
            transformed[active_rows],
            (
                frame.loc[active_rows, "c2_conditional_escape_cost"].to_numpy(dtype=np.float64)
                - coefficient * frame.loc[active_rows, "c2_best_probe_strength"].to_numpy(dtype=np.float64)
            ),
            alpha,
        ),
        "action_cost_coefficient": coefficient,
        "active_training_count": int(active_rows.sum()),
        "passive_training_count": int(passive_rows.sum()),
    }
    return {
        "features": list(features),
        "scaler": scaler,
        "models": models,
        "effective_config": effective,
    }


def predict_fixed(model: Mapping[str, Any], frame: pd.DataFrame, apply_config: Mapping[str, Any]) -> pd.DataFrame:
    X = frame[list(model["features"])].to_numpy(dtype=np.float64)
    transformed = model["scaler"].transform(X)
    config = model["effective_config"]
    output = frame[["trajectory_id", "scenario_id", "seed", "split", "snapshot_step"]].copy()
    for target in config["prediction"]["binary_targets"]:
        probability = _probability_predict(model["models"][target], transformed)
        output[f"actual__{target}"] = frame[target].to_numpy(dtype=float)
        output[f"predicted__{target}"] = probability
    for target in config["prediction"]["continuous_targets"]:
        if target == "c2_conditional_escape_cost":
            continue
        values = _regression_predict(model["models"][target], transformed)
        if "escape_cost" in target or "safe_reachable_range" in target:
            values = np.maximum(values, 0.0)
        if "last_action_window" in target:
            values = np.clip(values, -1.0, 8.0)
        output[f"actual__{target}"] = frame[target].to_numpy(dtype=float)
        output[f"predicted__{target}"] = values

    two = model["models"]["c2_cost_two_stage"]
    active_probability = output["predicted__c2_active_intervention_required"].to_numpy(dtype=float)
    passive_cost = np.maximum(_regression_predict(two["passive_cost"], transformed), 0.0)
    strength = np.clip(
        _regression_predict(two["active_strength"], transformed),
        0.0,
        float(apply_config["c2_cost_model"]["maximum_required_strength"]),
    )
    residual = np.maximum(_regression_predict(two["active_residual"], transformed), 0.0)
    active_cost = residual + float(two["action_cost_coefficient"]) * strength
    gate = active_probability >= float(apply_config["c2_cost_model"]["active_probability_threshold"])
    predicted_cost = np.where(gate, active_cost, passive_cost)
    output["actual__c2_conditional_escape_cost"] = frame[
        "c2_conditional_escape_cost"
    ].to_numpy(dtype=float)
    output["predicted__c2_conditional_escape_cost"] = predicted_cost
    output["predicted__c2_passive_cost"] = passive_cost
    output["predicted__c2_active_cost"] = active_cost
    output["predicted__c2_required_strength"] = strength
    output["actual__c2_required_strength"] = frame["c2_best_probe_strength"].to_numpy(dtype=float)
    output["predicted__c2_active_gate"] = gate.astype(int)
    return output


def write_manifest(root: Path) -> dict[str, Any]:
    files = [
        {"path": path.relative_to(root).as_posix(), "size_bytes": path.stat().st_size, "sha256": sha256(path)}
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    ]
    manifest = {
        "file_count": len(files),
        "total_size_bytes": sum(int(row["size_bytes"]) for row in files),
        "files": files,
    }
    dump_json(root / "manifest.json", manifest)
    return manifest


def validate_manifest(root: Path) -> dict[str, Any]:
    manifest = load_json(root / "manifest.json")
    for row in manifest["files"]:
        path = root / row["path"]
        if not path.is_file() or path.stat().st_size != int(row["size_bytes"]) or sha256(path) != row["sha256"]:
            raise ApplyError(f"manifest mismatch: {row['path']}")
    return manifest


def run(
    artifact_dir: str | Path,
    corpus_dir: str | Path,
    output_dir: str | Path,
    config_path: str | Path = DEFAULT_CONFIG,
) -> dict[str, Any]:
    apply_config = load_config(config_path)
    base_config = common.load_config(ROOT / apply_config["base_config_path"])
    source = resolve_artifact_root(artifact_dir)
    rev1.validate_manifest(source)
    output = Path(output_dir)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)

    coarse = _clean_branch_frame(pd.read_csv(source / "coarse_branch_results.csv"))
    boundary = _clean_branch_frame(pd.read_csv(source / "boundary_branch_results.csv"))
    probability = _clean_branch_frame(pd.read_csv(source / "probability_branch_results.csv"))
    branches = pd.concat([coarse, boundary, probability], ignore_index=True, sort=False)
    ledger = pd.read_csv(source / "action_boundary_ledger.csv")
    nonmonotonic = ledger[
        ledger.get("nonmonotonic_type", pd.Series(index=ledger.index, dtype=object)).notna()
    ].to_dict(orient="records")
    patched_truth = patch_truth(
        branches.to_dict(orient="records"), nonmonotonic, base_config, apply_config
    )

    original_lock = load_json(source / "task3_2_4_1_rev1_selection_lock.json")
    original_validation = load_json(source / "task3_2_4_1_rev1_selection_lock_validation.json")
    if not original_validation.get("valid"):
        raise ApplyError("original selection lock validation is not valid")
    selected = original_lock["selected_candidate"]
    if selected.get("candidate_family") != apply_config["selection_contract"]["candidate_family"]:
        raise ApplyError("original selection family does not match fixed Rev1.1 contract")
    locked_features = list(selected["features"])

    index = common.CorpusIndex(corpus_dir, base_config)
    fit_entries = index.entries_for("fit")
    validation_entries = index.entries_for("validation")
    holdout_entries = index.entries_for(
        "holdout",
        lock_path=source / "task3_2_4_1_rev1_selection_lock.json",
        validation_path=source / "task3_2_4_1_rev1_selection_lock_validation.json",
    )
    fit_truth = patched_truth[patched_truth["split"] == "fit"].copy()
    validation_truth = patched_truth[patched_truth["split"] == "validation"].copy()
    holdout_truth = patched_truth[patched_truth["split"] == "holdout"].copy()

    task3_config = common.json_load(ROOT / base_config["task3_config_path"])
    calibration = common.json_load(ROOT / base_config["calibration_config_path"])
    contract = common.json_load(ROOT / base_config["task1_contract_path"])
    required_arrays = list(contract["step_record"]["required_state_arrays"])
    fit_series = common.t41._load_series(fit_entries, task3_config, calibration)
    fit_features, preprocessor, dynamics, _, macro_names = rev1.prediction_frames(
        fit_entries, fit_entries, fit_truth, base_config, task3_config, calibration,
        required_arrays, fit_series=fit_series,
    )
    validation_features, _, _, _, _ = rev1.prediction_frames(
        fit_entries, validation_entries, validation_truth, base_config, task3_config, calibration,
        required_arrays, preprocessor=preprocessor, dynamics=dynamics, fit_series=fit_series,
    )
    holdout_features, _, _, _, _ = rev1.prediction_frames(
        fit_entries, holdout_entries, holdout_truth, base_config, task3_config, calibration,
        required_arrays, preprocessor=preprocessor, dynamics=dynamics, fit_series=fit_series,
    )
    if locked_features != list(macro_names):
        raise ApplyError("regenerated Task 4 feature schema differs from the original lock")

    validation_model = fit_fixed_task4_predictor(
        fit_features, locked_features, base_config, apply_config
    )
    validation_predictions = predict_fixed(validation_model, validation_features, apply_config)
    effective_config = validation_model["effective_config"]
    validation_metrics = evaluate_predictions(validation_predictions, effective_config)
    time_audit = time_confounding_audit(validation_truth, validation_predictions)

    final_model = fit_fixed_task4_predictor(
        pd.concat([fit_features, validation_features], ignore_index=True),
        locked_features,
        base_config,
        apply_config,
    )
    holdout_predictions = predict_fixed(final_model, holdout_features, apply_config)
    holdout_metrics = evaluate_predictions(holdout_predictions, final_model["effective_config"])
    old_holdout = load_json(source / "holdout_metrics.json")

    stable_dangerous = int(
        (patched_truth["scenario_id"].eq("stable_continuation") & patched_truth["dangerous_shrinking"].eq(1)).sum()
    )
    old_truth = pd.read_csv(source / "rev1_structural_truth.csv")
    old_irreversible = int(old_truth["irreversibility_progression"].sum())
    new_irreversible = int(patched_truth["irreversibility_progression"].sum())
    old_c2 = old_holdout["continuous"]["c2_conditional_escape_cost"]
    new_c2 = holdout_metrics["continuous"]["c2_conditional_escape_cost"]
    c2_improved = (
        new_c2["mae"] is not None
        and old_c2["mae"] is not None
        and float(new_c2["mae"]) < float(old_c2["mae"])
    )
    grade = (
        "A_rev1_1_patch_applied_and_revalidated"
        if stable_dangerous == 0 and new_irreversible == old_irreversible and c2_improved
        else "B_rev1_1_truth_patch_valid_prediction_still_limited"
    )

    fixed_contract = {
        "status": "fixed_without_reselection",
        "source_lock_hash": original_lock["lock_hash"],
        "candidate_family": selected["candidate_family"],
        "features": locked_features,
        "new_binary_target": "c2_active_intervention_required",
        "c2_cost_model": apply_config["c2_cost_model"],
        "post_holdout_reselection": False,
    }
    summary = {
        "task_id": apply_config["task_id"],
        "status": "complete",
        "grade": grade,
        "new_branches": 0,
        "source_branch_count": len(branches),
        "selection_reused": True,
        "selected_candidate": "task4",
        "stable_continuation_dangerous_count": stable_dangerous,
        "dangerous_shrinking_count": int(patched_truth["dangerous_shrinking"].sum()),
        "structural_contraction_count": int(patched_truth["structural_contraction"].sum()),
        "irreversibility_progression_count": new_irreversible,
        "old_irreversibility_progression_count": old_irreversible,
        "validation_metrics": validation_metrics,
        "holdout_metrics": holdout_metrics,
        "old_holdout_c2_cost_metrics": old_c2,
        "new_holdout_c2_cost_metrics": new_c2,
        "c2_cost_mae_improved": c2_improved,
        "time_confounding_audit": time_audit,
        "source_artifact_manifest_sha256": sha256(source / "manifest.json"),
        "boundaries": apply_config["boundaries"],
    }

    write_csv(output / "rev1_1_structural_truth.csv", patched_truth.to_dict(orient="records"))
    write_csv(output / "validation_predictions.csv", validation_predictions.to_dict(orient="records"))
    write_csv(output / "holdout_predictions.csv", holdout_predictions.to_dict(orient="records"))
    dump_json(output / "validation_metrics.json", validation_metrics)
    dump_json(output / "holdout_metrics.json", holdout_metrics)
    dump_json(output / "time_confounding_audit.json", time_audit)
    dump_json(output / "fixed_selection_contract.json", fixed_contract)
    two_stage = final_model["models"]["c2_cost_two_stage"]
    dump_json(output / "prediction_change.json", {
        "old_c2_cost": old_c2,
        "new_c2_cost": new_c2,
        "mae_improved": c2_improved,
        "two_stage_training": {
            "active_training_count": two_stage["active_training_count"],
            "passive_training_count": two_stage["passive_training_count"],
            "action_cost_coefficient": two_stage["action_cost_coefficient"],
        },
    })
    dump_json(output / "summary.json", summary)
    (output / "task4_1_rev1_1_applied_results.md").write_text(
        f"""# Task 3.2-4.1 Rev1.1 適用結果

- 新規分岐: 0
- 再利用分岐: {len(branches)}
- 選択予測器: Task 4（元selection lock固定）
- 危険な縮小: {int(patched_truth['dangerous_shrinking'].sum())}
- 安定継続の危険判定: {stable_dangerous}
- 不可逆化進行: {new_irreversible}
- C2費用 holdout MAE（旧）: {float(old_c2['mae']):.6f}
- C2費用 holdout MAE（新）: {float(new_c2['mae']):.6f}
- 判定: `{grade}`

構造正解は低費用成功経路群の再悪化へ更新した。C2費用は能動作用必要性を先に判定し、必要強度と残差費用から予測する固定二段階モデルで再検証した。
""",
        encoding="utf-8",
    )
    manifest = write_manifest(output)
    return {**summary, "manifest_file_count": manifest["file_count"]}


def validate_output(input_dir: str | Path) -> dict[str, Any]:
    root = Path(input_dir)
    required = {
        "summary.json", "manifest.json", "rev1_1_structural_truth.csv",
        "validation_predictions.csv", "holdout_predictions.csv",
        "validation_metrics.json", "holdout_metrics.json", "time_confounding_audit.json",
        "fixed_selection_contract.json", "prediction_change.json",
        "task4_1_rev1_1_applied_results.md",
    }
    missing = sorted(name for name in required if not (root / name).is_file())
    if missing:
        raise ApplyError(f"output missing {missing}")
    manifest = validate_manifest(root)
    summary = load_json(root / "summary.json")
    truth = pd.read_csv(root / "rev1_1_structural_truth.csv")
    contract = load_json(root / "fixed_selection_contract.json")
    if summary.get("status") != "complete" or summary.get("new_branches") != 0:
        raise ApplyError("Rev1.1 apply completion/budget contract failed")
    if summary.get("selection_reused") is not True or contract.get("candidate_family") != "task4":
        raise ApplyError("Rev1.1 selection reuse contract failed")
    if summary.get("stable_continuation_dangerous_count") != 0:
        raise ApplyError("stable-continuation danger was not removed")
    if summary.get("irreversibility_progression_count") != summary.get("old_irreversibility_progression_count"):
        raise ApplyError("irreversibility progression changed")
    if len(truth) != 90 or "c2_active_intervention_required" not in truth:
        raise ApplyError("patched structural truth schema/count failed")
    if summary["boundaries"].get("new_branch_execution") is not False:
        raise ApplyError("new branches were executed")
    return {
        "status": "valid",
        "grade": summary["grade"],
        "dangerous_shrinking_count": summary["dangerous_shrinking_count"],
        "stable_continuation_dangerous_count": 0,
        "c2_cost_mae_improved": summary["c2_cost_mae_improved"],
        "manifest_file_count": manifest["file_count"],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    execute = sub.add_parser("run")
    execute.add_argument("--artifact", required=True)
    execute.add_argument("--corpus", required=True)
    execute.add_argument("--output", required=True)
    execute.add_argument("--config", default=str(DEFAULT_CONFIG))
    check = sub.add_parser("validate")
    check.add_argument("--input", required=True)
    args = parser.parse_args(argv)
    result = (
        run(args.artifact, args.corpus, args.output, args.config)
        if args.command == "run"
        else validate_output(args.input)
    )
    print(json.dumps(common.native(result), ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
