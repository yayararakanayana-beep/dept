"""Task 2-8j-4b/4c/4d/4e pre-freeze validations RC1.

These validations are deliberately kept downstream of Task 2-8j-4 and upstream
of any fixed-map contract.  They help decide whether the 7-axis effective
map should replace the 6-axis standard in later validation code.

Common boundary:
    - validation only
    - no effective-dimension adoption or freeze
    - no dynamics-axis extraction
    - no action-weight conversion
    - no upper-pressure connection
    - no ActionFrame / ActionModule / FullSpec runtime / canonical write
    - no v2_hidden_trace as feature input
"""
from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

import numpy as np
import pandas as pd

from .pressure_action_task2_8j_1_candidate_feature_log import (
    CandidateFeatureLogConfig,
    build_candidate_feature_log,
    validate_candidate_feature_log,
)
from .pressure_action_task2_8j_2_temporal_pca_validation import (
    PCAModel,
    TemporalPCAValidationConfig,
    build_stability_table,
    fit_pca_validation_models,
)
from .pressure_action_task2_8j_4_game_structure_reidentification import (
    EVENT_TARGETS,
    GameStructureReidentificationConfig,
    build_event_reidentification_table,
)

COMMON_FORBIDDEN_COLUMNS = [
    "runtime_policy_input",
    "fullspec_runtime_connected",
    "upper_pressure_connected",
    "action_frame_created",
    "actionmodule_called",
    "canonical_write_performed",
    "gk_writeback_performed",
    "ot_writeback_performed",
    "effective_dimension_adopted",
    "effective_dimension_frozen",
    "dynamics_axis_extracted",
    "action_weight_converted",
    "hidden_truth_input",
]

COMMON_BOUNDARY_COLUMNS = ["task_name", "task_contract", "validation_only"] + COMMON_FORBIDDEN_COLUMNS


@dataclass(frozen=True)
class PreFreezeValidationConfig:
    component_counts: tuple[int, ...] = (3, 6, 7, 8)
    standard_component_count: int = 6
    shadow_component_count: int = 7
    prediction_horizon: int = 3
    train_quantile: float = 0.67
    min_train_rows: int = 8
    min_test_rows: int = 4
    high_event_quantile: float = 0.67
    low_event_quantile: float = 0.33
    random_seed: int = 173


def _boundary_payload(task_name: str, contract: str) -> dict:
    return {
        "task_name": task_name,
        "task_contract": contract,
        "validation_only": True,
        "runtime_policy_input": False,
        "fullspec_runtime_connected": False,
        "upper_pressure_connected": False,
        "action_frame_created": False,
        "actionmodule_called": False,
        "canonical_write_performed": False,
        "gk_writeback_performed": False,
        "ot_writeback_performed": False,
        "effective_dimension_adopted": False,
        "effective_dimension_frozen": False,
        "dynamics_axis_extracted": False,
        "action_weight_converted": False,
        "hidden_truth_input": False,
    }


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return float(default)
    if not np.isfinite(out):
        return float(default)
    return out


def _safe_mean(values: pd.Series | list[float] | np.ndarray, default: float = 0.0) -> float:
    if values is None:
        return float(default)
    arr = pd.to_numeric(pd.Series(values), errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if arr.empty:
        return float(default)
    return float(arr.mean())


def _fit_static_models(
    feature_cfg: CandidateFeatureLogConfig | None,
    cfg: PreFreezeValidationConfig,
) -> tuple[dict[int, PCAModel], list[str]]:
    feature_cfg = feature_cfg or CandidateFeatureLogConfig(steps=24, seeds=(501, 502, 503), window_sizes=(1, 6, 12))
    feature_log = build_candidate_feature_log(feature_cfg)
    errors = validate_candidate_feature_log(feature_log)
    models: dict[int, PCAModel] = {}
    for count in cfg.component_counts:
        pca_cfg = TemporalPCAValidationConfig(
            n_components=int(count),
            sparse_top_k=12,
            prediction_horizon=int(cfg.prediction_horizon),
            min_prediction_rows=int(cfg.min_train_rows),
        )
        models[int(count)] = fit_pca_validation_models(feature_log, pca_cfg)["static_pca"]
    return models, errors


def _find_feature_key(columns: list[str], token: str) -> str | None:
    preferred = [key for key in sorted(columns) if token in key and key.endswith("::w1")]
    if preferred:
        return preferred[0]
    matches = [key for key in sorted(columns) if token in key]
    return matches[0] if matches else None


def _time_split_mask(index: pd.Index, train_quantile: float) -> np.ndarray:
    t_values = np.asarray([int(idx[2]) for idx in index.tolist()], dtype=int)
    cutoff = float(np.quantile(t_values, train_quantile))
    return t_values <= cutoff


def _classification_metrics(true_label: np.ndarray, pred_label: np.ndarray) -> tuple[float, float, float, float]:
    true_bool = np.asarray(true_label, dtype=bool)
    pred_bool = np.asarray(pred_label, dtype=bool)
    if true_bool.size == 0:
        return 0.0, 0.0, 0.0, 0.0
    accuracy = float(np.mean(true_bool == pred_bool))
    tp = int(np.sum(true_bool & pred_bool))
    tn = int(np.sum(~true_bool & ~pred_bool))
    fp = int(np.sum(~true_bool & pred_bool))
    fn = int(np.sum(true_bool & ~pred_bool))
    tpr = tp / max(tp + fn, 1)
    tnr = tn / max(tn + fp, 1)
    balanced = float((tpr + tnr) / 2.0)
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = float(2.0 * precision * recall / max(precision + recall, 1e-12))
    prevalence = float(np.mean(true_bool))
    return accuracy, balanced, f1, prevalence


def _linear_regression_predict(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray) -> np.ndarray:
    x_train = np.column_stack([np.ones(train_x.shape[0]), train_x])
    x_test = np.column_stack([np.ones(test_x.shape[0]), test_x])
    beta, *_ = np.linalg.lstsq(x_train, train_y, rcond=None)
    return x_test @ beta


def _future_target_rows(model: PCAModel, key: str, horizon: int) -> tuple[pd.Index, np.ndarray, np.ndarray]:
    mat = model.matrix
    aligned: list[tuple[object, float]] = []
    for seed, scenario in sorted(set((idx[0], idx[1]) for idx in mat.index.tolist())):
        sub_idx = [idx for idx in mat.index if idx[0] == seed and idx[1] == scenario]
        sub_idx = sorted(sub_idx, key=lambda x: int(x[2]))
        for pos, idx in enumerate(sub_idx):
            future_pos = pos + int(horizon)
            if future_pos >= len(sub_idx):
                continue
            future_idx = sub_idx[future_pos]
            aligned.append((idx, _safe_float(mat.loc[future_idx, key], default=0.0)))
    if not aligned:
        return pd.Index([]), np.empty((0, model.scores.shape[1])), np.asarray([], dtype=float)
    idxs = pd.Index([row[0] for row in aligned])
    y = np.asarray([row[1] for row in aligned], dtype=float)
    score_df = pd.DataFrame(model.scores, index=mat.index, columns=[f"component_{i + 1}" for i in range(model.scores.shape[1])])
    x = score_df.loc[idxs].to_numpy(dtype=float)
    return idxs, x, y


def _event_metric_for_model(
    model: PCAModel,
    key: str,
    direction: str,
    cfg: PreFreezeValidationConfig,
    *,
    shuffled: bool = False,
) -> dict:
    idxs, x, y = _future_target_rows(model, key, cfg.prediction_horizon)
    if len(y) < cfg.min_train_rows + cfg.min_test_rows:
        return {"valid": False}
    if shuffled:
        rng = np.random.default_rng(cfg.random_seed)
        y = rng.permutation(y)
    train_mask = _time_split_mask(idxs, cfg.train_quantile)
    test_mask = ~train_mask
    if int(train_mask.sum()) < cfg.min_train_rows or int(test_mask.sum()) < cfg.min_test_rows:
        return {"valid": False}
    train_y = y[train_mask]
    test_y = y[test_mask]
    train_x = x[train_mask]
    test_x = x[test_mask]
    pred_y = _linear_regression_predict(train_x, train_y, test_x)
    if direction == "low":
        threshold = float(np.quantile(train_y, cfg.low_event_quantile))
        true_label = test_y <= threshold
        pred_label = pred_y <= threshold
    else:
        threshold = float(np.quantile(train_y, cfg.high_event_quantile))
        true_label = test_y >= threshold
        pred_label = pred_y >= threshold
    accuracy, balanced, f1, prevalence = _classification_metrics(true_label, pred_label)
    rmse = float(sqrt(float(np.mean((pred_y - test_y) ** 2))))
    baseline = float(np.mean(train_y))
    baseline_rmse = float(sqrt(float(np.mean((baseline - test_y) ** 2))))
    r2 = float(1.0 - (rmse**2 / max(baseline_rmse**2, 1e-12)))
    return {
        "valid": True,
        "threshold": threshold,
        "event_accuracy": accuracy,
        "event_balanced_accuracy": balanced,
        "event_f1": f1,
        "event_prevalence": prevalence,
        "r2_vs_mean_baseline": r2,
        "train_rows": int(train_mask.sum()),
        "test_rows": int(test_mask.sum()),
    }


def _validate_tables(tables: dict[str, tuple[pd.DataFrame, list[str]]], prefix: str) -> list[str]:
    errors: list[str] = []
    for name, (table, required) in tables.items():
        if table is None or table.empty:
            errors.append(f"{prefix}_empty_table:{name}")
            continue
        missing = [c for c in required if c not in table.columns]
        if missing:
            errors.append(f"{prefix}_missing_columns:{name}:" + ",".join(missing))
            continue
        if not bool(table["validation_only"].astype(bool).all()):
            errors.append(f"{prefix}_validation_only_not_all_true:{name}")
        for col in COMMON_FORBIDDEN_COLUMNS:
            if bool(table[col].astype(bool).any()):
                errors.append(f"{prefix}_forbidden_true:{name}:{col}")
    return errors


# ---------------------------------------------------------------------------
# Task 2-8j-4b: multi-scenario re-identification
# ---------------------------------------------------------------------------

REQUIRED_4B_COLUMNS = COMMON_BOUNDARY_COLUMNS + [
    "component_count",
    "map_role",
    "derived_scenario_count",
    "train_rows",
    "test_rows",
    "derived_scenario_accuracy",
    "derived_scenario_balanced_accuracy",
    "multi_scenario_status",
]
REQUIRED_4B_FINAL_COLUMNS = COMMON_BOUNDARY_COLUMNS + [
    "standard_component_count",
    "shadow_component_count",
    "standard_balanced_accuracy",
    "shadow_balanced_accuracy",
    "shadow_delta_from_standard",
    "multi_scenario_decision",
    "adoption_performed",
    "freeze_performed",
    "next_task",
]


def _derive_observable_scenario_labels(mat: pd.DataFrame) -> np.ndarray:
    columns = mat.columns.astype(str).tolist()
    relation_key = _find_feature_key(columns, "relation_lock")
    coord_key = _find_feature_key(columns, "coordination_lag_mean")
    info_key = _find_feature_key(columns, "information_quality_mean")
    resource_key = _find_feature_key(columns, "resource_pressure")
    thresholds: dict[str, float] = {}
    for key, direction in [(relation_key, "high"), (coord_key, "high"), (resource_key, "high"), (info_key, "low")]:
        if key is None:
            continue
        q = 0.67 if direction == "high" else 0.33
        thresholds[key] = float(np.quantile(mat[key].astype(float), q))
    labels = []
    for _, row in mat.iterrows():
        if coord_key and _safe_float(row[coord_key]) >= thresholds.get(coord_key, float("inf")):
            labels.append("coordination_lag_high")
        elif info_key and _safe_float(row[info_key]) <= thresholds.get(info_key, -float("inf")):
            labels.append("information_quality_low")
        elif relation_key and _safe_float(row[relation_key]) >= thresholds.get(relation_key, float("inf")):
            labels.append("relation_lock_high")
        elif resource_key and _safe_float(row[resource_key]) >= thresholds.get(resource_key, float("inf")):
            labels.append("resource_pressure_high")
        else:
            labels.append("stable_or_mixed")
    return np.asarray(labels, dtype=object)


def _multi_class_balanced_accuracy(true_labels: np.ndarray, pred_labels: np.ndarray) -> float:
    labels = sorted(set(true_labels.tolist()))
    if not labels:
        return 0.0
    accs = []
    for label in labels:
        mask = true_labels == label
        if mask.any():
            accs.append(float(np.mean(pred_labels[mask] == true_labels[mask])))
    return float(np.mean(accs)) if accs else 0.0


def build_and_validate_4b_multi_scenario_reidentification(
    feature_cfg: CandidateFeatureLogConfig | None = None,
    cfg: PreFreezeValidationConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str], dict]:
    cfg = cfg or PreFreezeValidationConfig()
    models, upstream_errors = _fit_static_models(feature_cfg, cfg)
    rows: list[dict] = []
    task = "Task2-8j-4b"
    contract = "multi_scenario_reidentification__observable_scenario_labels__no_adoption_no_freeze"
    for count, model in models.items():
        labels = _derive_observable_scenario_labels(model.matrix)
        train_mask = _time_split_mask(model.matrix.index, cfg.train_quantile)
        test_mask = ~train_mask
        train_x = model.scores[train_mask]
        test_x = model.scores[test_mask]
        train_y = labels[train_mask]
        test_y = labels[test_mask]
        centroids: dict[str, np.ndarray] = {}
        for label in sorted(set(train_y.tolist())):
            centroids[str(label)] = train_x[train_y == label].mean(axis=0)
        pred = []
        for score in test_x:
            best_label = min(centroids, key=lambda k: float(np.linalg.norm(score - centroids[k]))) if centroids else "none"
            pred.append(best_label)
        pred_y = np.asarray(pred, dtype=object)
        accuracy = float(np.mean(pred_y == test_y)) if len(test_y) else 0.0
        balanced = _multi_class_balanced_accuracy(test_y, pred_y) if len(test_y) else 0.0
        rows.append(
            {
                **_boundary_payload(task, contract),
                "component_count": int(count),
                "map_role": _map_role_for_prefreeze(count, cfg),
                "derived_scenario_count": int(len(set(labels.tolist()))),
                "train_rows": int(train_mask.sum()),
                "test_rows": int(test_mask.sum()),
                "derived_scenario_accuracy": accuracy,
                "derived_scenario_balanced_accuracy": balanced,
                "multi_scenario_status": "pass" if int(len(set(labels.tolist()))) >= 3 else "watch",
            }
        )
    table = pd.DataFrame(rows, columns=REQUIRED_4B_COLUMNS)
    final = _build_4b_final_summary(table, cfg)
    errors = [f"task2_8j_4b_upstream_error:{e}" for e in upstream_errors]
    errors.extend(_validate_tables({"multi_scenario": (table, REQUIRED_4B_COLUMNS), "final_summary": (final, REQUIRED_4B_FINAL_COLUMNS)}, "task2_8j_4b"))
    summary = {
        "rows": int(len(table)),
        "component_counts": sorted(table["component_count"].astype(int).tolist()) if not table.empty else [],
        "derived_scenario_count_max": int(table["derived_scenario_count"].astype(int).max()) if not table.empty else 0,
        "shadow_delta_from_standard": _safe_float(final["shadow_delta_from_standard"].iloc[0]) if not final.empty else 0.0,
        "multi_scenario_decision": str(final["multi_scenario_decision"].iloc[0]) if not final.empty else "empty",
        "adoption_performed": False,
        "freeze_performed": False,
        "validation_errors": errors,
    }
    return table, final, errors, summary


def _map_role_for_prefreeze(count: int, cfg: PreFreezeValidationConfig) -> str:
    if int(count) == int(cfg.standard_component_count):
        return "standard_6_axis_map"
    if int(count) == int(cfg.shadow_component_count):
        return "shadow_7_axis_expansion_map"
    if int(count) < int(cfg.standard_component_count):
        return "lightweight_coarse_map"
    return "extra_expansion_reference_map"


def _build_4b_final_summary(table: pd.DataFrame, cfg: PreFreezeValidationConfig) -> pd.DataFrame:
    task = "Task2-8j-4b"
    contract = "multi_scenario_reidentification__observable_scenario_labels__no_adoption_no_freeze"
    standard = table[table["component_count"].astype(int) == int(cfg.standard_component_count)]
    shadow = table[table["component_count"].astype(int) == int(cfg.shadow_component_count)]
    standard_bal = _safe_float(standard["derived_scenario_balanced_accuracy"].iloc[0]) if not standard.empty else 0.0
    shadow_bal = _safe_float(shadow["derived_scenario_balanced_accuracy"].iloc[0]) if not shadow.empty else 0.0
    delta = shadow_bal - standard_bal
    if delta > 0.03:
        decision = "shadow_7_multi_scenario_advantage"
    elif delta < -0.03:
        decision = "standard_6_multi_scenario_advantage"
    else:
        decision = "no_clear_multi_scenario_gap"
    row = {
        **_boundary_payload(task, contract),
        "standard_component_count": int(cfg.standard_component_count),
        "shadow_component_count": int(cfg.shadow_component_count),
        "standard_balanced_accuracy": standard_bal,
        "shadow_balanced_accuracy": shadow_bal,
        "shadow_delta_from_standard": delta,
        "multi_scenario_decision": decision,
        "adoption_performed": False,
        "freeze_performed": False,
        "next_task": "Task 2-8j-4c: seed and rolling-window stability",
    }
    return pd.DataFrame([row], columns=REQUIRED_4B_FINAL_COLUMNS)


# ---------------------------------------------------------------------------
# Task 2-8j-4c: seed and rolling-window stability
# ---------------------------------------------------------------------------

REQUIRED_4C_COLUMNS = COMMON_BOUNDARY_COLUMNS + [
    "component_count",
    "map_role",
    "mean_subspace_similarity",
    "mean_projection_drift",
    "projection_drift_score",
    "seed_score_consistency",
    "rolling_stability_score",
    "stability_status",
]
REQUIRED_4C_FINAL_COLUMNS = COMMON_BOUNDARY_COLUMNS + [
    "standard_component_count",
    "shadow_component_count",
    "standard_stability_score",
    "shadow_stability_score",
    "shadow_delta_from_standard",
    "stability_decision",
    "adoption_performed",
    "freeze_performed",
    "next_task",
]


def build_and_validate_4c_seed_rolling_stability(
    feature_cfg: CandidateFeatureLogConfig | None = None,
    cfg: PreFreezeValidationConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str], dict]:
    cfg = cfg or PreFreezeValidationConfig()
    models, upstream_errors = _fit_static_models(feature_cfg, cfg)
    task = "Task2-8j-4c"
    contract = "seed_rolling_window_stability__6_standard_vs_7_shadow__no_adoption_no_freeze"
    rows = []
    for count, model in models.items():
        pca_cfg = TemporalPCAValidationConfig(n_components=int(count), sparse_top_k=12, prediction_horizon=int(cfg.prediction_horizon))
        stability_table = build_stability_table({"static_pca": model}, pca_cfg)
        mean_similarity = _safe_mean(stability_table["subspace_similarity"], default=0.0) if not stability_table.empty else 0.0
        mean_drift = _safe_mean(stability_table["projection_drift"], default=1.0) if not stability_table.empty else 1.0
        drift_score = float(1.0 / (1.0 + max(0.0, mean_drift)))
        seed_consistency = _seed_score_consistency(model)
        rolling_score = float(np.clip(0.55 * mean_similarity + 0.25 * seed_consistency + 0.20 * drift_score, 0.0, 1.0))
        rows.append(
            {
                **_boundary_payload(task, contract),
                "component_count": int(count),
                "map_role": _map_role_for_prefreeze(count, cfg),
                "mean_subspace_similarity": mean_similarity,
                "mean_projection_drift": mean_drift,
                "projection_drift_score": drift_score,
                "seed_score_consistency": seed_consistency,
                "rolling_stability_score": rolling_score,
                "stability_status": "pass" if rolling_score >= 0.45 else "watch",
            }
        )
    table = pd.DataFrame(rows, columns=REQUIRED_4C_COLUMNS)
    final = _build_4c_final_summary(table, cfg)
    errors = [f"task2_8j_4c_upstream_error:{e}" for e in upstream_errors]
    errors.extend(_validate_tables({"seed_rolling": (table, REQUIRED_4C_COLUMNS), "final_summary": (final, REQUIRED_4C_FINAL_COLUMNS)}, "task2_8j_4c"))
    summary = {
        "rows": int(len(table)),
        "component_counts": sorted(table["component_count"].astype(int).tolist()) if not table.empty else [],
        "shadow_delta_from_standard": _safe_float(final["shadow_delta_from_standard"].iloc[0]) if not final.empty else 0.0,
        "stability_decision": str(final["stability_decision"].iloc[0]) if not final.empty else "empty",
        "adoption_performed": False,
        "freeze_performed": False,
        "validation_errors": errors,
    }
    return table, final, errors, summary


def _seed_score_consistency(model: PCAModel) -> float:
    index = model.matrix.index.tolist()
    seeds = sorted(set(idx[0] for idx in index))
    if len(seeds) <= 1:
        return 1.0
    score_df = pd.DataFrame(model.scores, index=model.matrix.index)
    means = []
    for seed in seeds:
        sub_idx = [idx for idx in model.matrix.index if idx[0] == seed]
        if sub_idx:
            means.append(score_df.loc[sub_idx].mean(axis=0).to_numpy(dtype=float))
    if len(means) <= 1:
        return 1.0
    sims = []
    for i in range(len(means)):
        for j in range(i + 1, len(means)):
            a, b = means[i], means[j]
            denom = float(np.linalg.norm(a) * np.linalg.norm(b))
            cos = float(np.dot(a, b) / denom) if denom > 1e-12 else 1.0
            sims.append((cos + 1.0) / 2.0)
    return float(np.clip(np.mean(sims), 0.0, 1.0)) if sims else 1.0


def _build_4c_final_summary(table: pd.DataFrame, cfg: PreFreezeValidationConfig) -> pd.DataFrame:
    task = "Task2-8j-4c"
    contract = "seed_rolling_window_stability__6_standard_vs_7_shadow__no_adoption_no_freeze"
    standard = table[table["component_count"].astype(int) == int(cfg.standard_component_count)]
    shadow = table[table["component_count"].astype(int) == int(cfg.shadow_component_count)]
    standard_score = _safe_float(standard["rolling_stability_score"].iloc[0]) if not standard.empty else 0.0
    shadow_score = _safe_float(shadow["rolling_stability_score"].iloc[0]) if not shadow.empty else 0.0
    delta = shadow_score - standard_score
    if delta > 0.03:
        decision = "shadow_7_stability_advantage"
    elif delta < -0.03:
        decision = "standard_6_stability_advantage"
    else:
        decision = "stability_gap_small"
    row = {
        **_boundary_payload(task, contract),
        "standard_component_count": int(cfg.standard_component_count),
        "shadow_component_count": int(cfg.shadow_component_count),
        "standard_stability_score": standard_score,
        "shadow_stability_score": shadow_score,
        "shadow_delta_from_standard": delta,
        "stability_decision": decision,
        "adoption_performed": False,
        "freeze_performed": False,
        "next_task": "Task 2-8j-4d: seventh-axis meaning and residual audit",
    }
    return pd.DataFrame([row], columns=REQUIRED_4C_FINAL_COLUMNS)


# ---------------------------------------------------------------------------
# Task 2-8j-4d: seventh-axis meaning and residual audit
# ---------------------------------------------------------------------------

REQUIRED_4D_MEANING_COLUMNS = COMMON_BOUNDARY_COLUMNS + [
    "component_count",
    "component_index",
    "rank",
    "feature_key",
    "feature_weight",
    "abs_feature_weight",
    "meaning_status",
]
REQUIRED_4D_RESIDUAL_COLUMNS = COMMON_BOUNDARY_COLUMNS + [
    "event_name",
    "r2_static_6",
    "r2_static_7",
    "r2_improvement_7_minus_6",
    "balanced_accuracy_static_6",
    "balanced_accuracy_static_7",
    "balanced_accuracy_improvement_7_minus_6",
    "rescued_by_7",
]
REQUIRED_4D_FINAL_COLUMNS = COMMON_BOUNDARY_COLUMNS + [
    "top_feature_rows",
    "residual_rows",
    "rescued_event_count",
    "mean_r2_improvement",
    "mean_balanced_accuracy_improvement",
    "seventh_axis_decision",
    "adoption_performed",
    "freeze_performed",
    "next_task",
]


def build_and_validate_4d_seventh_axis_meaning_residual_audit(
    feature_cfg: CandidateFeatureLogConfig | None = None,
    cfg: PreFreezeValidationConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    cfg = cfg or PreFreezeValidationConfig(component_counts=(6, 7))
    if 6 not in cfg.component_counts or 7 not in cfg.component_counts:
        cfg = PreFreezeValidationConfig(component_counts=(6, 7), standard_component_count=6, shadow_component_count=7)
    models, upstream_errors = _fit_static_models(feature_cfg, cfg)
    meaning = _build_4d_meaning_table(models[7])
    residual = _build_4d_residual_table(models, cfg)
    final = _build_4d_final_summary(meaning, residual)
    errors = [f"task2_8j_4d_upstream_error:{e}" for e in upstream_errors]
    errors.extend(
        _validate_tables(
            {
                "meaning": (meaning, REQUIRED_4D_MEANING_COLUMNS),
                "residual": (residual, REQUIRED_4D_RESIDUAL_COLUMNS),
                "final_summary": (final, REQUIRED_4D_FINAL_COLUMNS),
            },
            "task2_8j_4d",
        )
    )
    summary = {
        "top_feature_rows": int(len(meaning)),
        "residual_rows": int(len(residual)),
        "rescued_event_count": int(final["rescued_event_count"].iloc[0]) if not final.empty else 0,
        "mean_r2_improvement": _safe_float(final["mean_r2_improvement"].iloc[0]) if not final.empty else 0.0,
        "seventh_axis_decision": str(final["seventh_axis_decision"].iloc[0]) if not final.empty else "empty",
        "adoption_performed": False,
        "freeze_performed": False,
        "validation_errors": errors,
    }
    return meaning, residual, final, errors, summary


def _build_4d_meaning_table(model7: PCAModel, top_n: int = 20) -> pd.DataFrame:
    task = "Task2-8j-4d"
    contract = "seventh_axis_meaning_residual_audit__no_adoption_no_freeze"
    features = np.asarray(model7.matrix.columns.astype(str).tolist(), dtype=object)
    comp = model7.components[6] if model7.components.shape[0] >= 7 else model7.components[-1]
    idx = np.argsort(np.abs(comp))[-min(top_n, len(comp)) :][::-1]
    rows = []
    for rank, j in enumerate(idx, start=1):
        key = str(features[j])
        status = "interpretable_watch"
        if any(token in key for token in ["coordination_lag", "information_quality", "relation", "resource", "uncertainty"]):
            status = "interpretable_core_signal"
        rows.append(
            {
                **_boundary_payload(task, contract),
                "component_count": 7,
                "component_index": 7,
                "rank": int(rank),
                "feature_key": key,
                "feature_weight": _safe_float(comp[j]),
                "abs_feature_weight": abs(_safe_float(comp[j])),
                "meaning_status": status,
            }
        )
    return pd.DataFrame(rows, columns=REQUIRED_4D_MEANING_COLUMNS)


def _build_4d_residual_table(models: dict[int, PCAModel], cfg: PreFreezeValidationConfig) -> pd.DataFrame:
    task = "Task2-8j-4d"
    contract = "seventh_axis_meaning_residual_audit__no_adoption_no_freeze"
    reid_cfg = GameStructureReidentificationConfig(
        component_counts=(6, 7),
        standard_component_count=6,
        shadow_component_count=7,
        prediction_horizon=cfg.prediction_horizon,
        min_train_rows=cfg.min_train_rows,
        min_test_rows=cfg.min_test_rows,
    )
    event_table = build_event_reidentification_table({6: models[6], 7: models[7]}, reid_cfg)
    rows = []
    for event_name in sorted(set(event_table["event_name"].astype(str).tolist())):
        r6 = event_table[(event_table["component_count"].astype(int) == 6) & (event_table["event_name"].astype(str) == event_name)]
        r7 = event_table[(event_table["component_count"].astype(int) == 7) & (event_table["event_name"].astype(str) == event_name)]
        if r6.empty or r7.empty:
            continue
        r2_6 = _safe_float(r6["r2_vs_mean_baseline"].iloc[0])
        r2_7 = _safe_float(r7["r2_vs_mean_baseline"].iloc[0])
        bal6 = _safe_float(r6["event_balanced_accuracy"].iloc[0])
        bal7 = _safe_float(r7["event_balanced_accuracy"].iloc[0])
        rows.append(
            {
                **_boundary_payload(task, contract),
                "event_name": event_name,
                "r2_static_6": r2_6,
                "r2_static_7": r2_7,
                "r2_improvement_7_minus_6": r2_7 - r2_6,
                "balanced_accuracy_static_6": bal6,
                "balanced_accuracy_static_7": bal7,
                "balanced_accuracy_improvement_7_minus_6": bal7 - bal6,
                "rescued_by_7": bool((r2_7 - r2_6) > 0.10 or (bal7 - bal6) > 0.10),
            }
        )
    return pd.DataFrame(rows, columns=REQUIRED_4D_RESIDUAL_COLUMNS)


def _build_4d_final_summary(meaning: pd.DataFrame, residual: pd.DataFrame) -> pd.DataFrame:
    task = "Task2-8j-4d"
    contract = "seventh_axis_meaning_residual_audit__no_adoption_no_freeze"
    rescued = int(residual["rescued_by_7"].astype(bool).sum()) if residual is not None and not residual.empty else 0
    mean_r2 = _safe_mean(residual["r2_improvement_7_minus_6"], default=0.0) if residual is not None and not residual.empty else 0.0
    mean_bal = _safe_mean(residual["balanced_accuracy_improvement_7_minus_6"], default=0.0) if residual is not None and not residual.empty else 0.0
    core_features = int((meaning["meaning_status"].astype(str) == "interpretable_core_signal").sum()) if meaning is not None and not meaning.empty else 0
    if rescued >= 2 and core_features >= 3:
        decision = "seventh_axis_has_interpretable_residual_value"
    elif rescued >= 1:
        decision = "seventh_axis_has_partial_residual_value"
    else:
        decision = "seventh_axis_value_not_yet_confirmed"
    row = {
        **_boundary_payload(task, contract),
        "top_feature_rows": int(len(meaning)) if meaning is not None else 0,
        "residual_rows": int(len(residual)) if residual is not None else 0,
        "rescued_event_count": rescued,
        "mean_r2_improvement": mean_r2,
        "mean_balanced_accuracy_improvement": mean_bal,
        "seventh_axis_decision": decision,
        "adoption_performed": False,
        "freeze_performed": False,
        "next_task": "Task 2-8j-4e: negative control and leakage audit",
    }
    return pd.DataFrame([row], columns=REQUIRED_4D_FINAL_COLUMNS)


# ---------------------------------------------------------------------------
# Task 2-8j-4e: negative control and leakage audit
# ---------------------------------------------------------------------------

REQUIRED_4E_CONTROL_COLUMNS = COMMON_BOUNDARY_COLUMNS + [
    "event_name",
    "target_feature_key",
    "true_balanced_accuracy",
    "shuffled_balanced_accuracy",
    "balanced_accuracy_degradation",
    "true_r2",
    "shuffled_r2",
    "r2_degradation",
    "negative_control_status",
]
REQUIRED_4E_LEAKAGE_COLUMNS = COMMON_BOUNDARY_COLUMNS + [
    "component_count",
    "feature_count",
    "hidden_feature_count",
    "truth_feature_count",
    "future_feature_count",
    "hidden_truth_input_detected",
    "leakage_audit_status",
]
REQUIRED_4E_FINAL_COLUMNS = COMMON_BOUNDARY_COLUMNS + [
    "control_rows",
    "leakage_rows",
    "mean_balanced_accuracy_degradation",
    "mean_r2_degradation",
    "hidden_truth_input_detected",
    "negative_control_decision",
    "adoption_performed",
    "freeze_performed",
    "next_task",
]


def build_and_validate_4e_negative_control_leakage_audit(
    feature_cfg: CandidateFeatureLogConfig | None = None,
    cfg: PreFreezeValidationConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    cfg = cfg or PreFreezeValidationConfig(component_counts=(7,))
    if 7 not in cfg.component_counts:
        cfg = PreFreezeValidationConfig(component_counts=(7,), standard_component_count=6, shadow_component_count=7)
    models, upstream_errors = _fit_static_models(feature_cfg, cfg)
    model7 = models[7]
    control = _build_4e_control_table(model7, cfg)
    leakage = _build_4e_leakage_table(model7)
    final = _build_4e_final_summary(control, leakage)
    errors = [f"task2_8j_4e_upstream_error:{e}" for e in upstream_errors]
    errors.extend(
        _validate_tables(
            {
                "negative_control": (control, REQUIRED_4E_CONTROL_COLUMNS),
                "leakage": (leakage, REQUIRED_4E_LEAKAGE_COLUMNS),
                "final_summary": (final, REQUIRED_4E_FINAL_COLUMNS),
            },
            "task2_8j_4e",
        )
    )
    if bool(final["hidden_truth_input_detected"].astype(bool).any()):
        errors.append("task2_8j_4e_hidden_truth_input_detected")
    summary = {
        "control_rows": int(len(control)),
        "leakage_rows": int(len(leakage)),
        "mean_balanced_accuracy_degradation": _safe_float(final["mean_balanced_accuracy_degradation"].iloc[0]) if not final.empty else 0.0,
        "mean_r2_degradation": _safe_float(final["mean_r2_degradation"].iloc[0]) if not final.empty else 0.0,
        "hidden_truth_input_detected": bool(final["hidden_truth_input_detected"].iloc[0]) if not final.empty else False,
        "negative_control_decision": str(final["negative_control_decision"].iloc[0]) if not final.empty else "empty",
        "adoption_performed": False,
        "freeze_performed": False,
        "validation_errors": errors,
    }
    return control, leakage, final, errors, summary


def _build_4e_control_table(model7: PCAModel, cfg: PreFreezeValidationConfig) -> pd.DataFrame:
    task = "Task2-8j-4e"
    contract = "negative_control_leakage_audit__no_adoption_no_freeze"
    columns = model7.matrix.columns.astype(str).tolist()
    rows = []
    for token, event_name, direction in EVENT_TARGETS:
        key = _find_feature_key(columns, token)
        if key is None:
            continue
        true_metrics = _event_metric_for_model(model7, key, direction, cfg, shuffled=False)
        shuffled_metrics = _event_metric_for_model(model7, key, direction, cfg, shuffled=True)
        if not true_metrics.get("valid") or not shuffled_metrics.get("valid"):
            continue
        bal_deg = _safe_float(true_metrics["event_balanced_accuracy"]) - _safe_float(shuffled_metrics["event_balanced_accuracy"])
        r2_deg = _safe_float(true_metrics["r2_vs_mean_baseline"]) - _safe_float(shuffled_metrics["r2_vs_mean_baseline"])
        status = "pass" if (bal_deg >= -0.05 or r2_deg >= -0.10) else "watch"
        rows.append(
            {
                **_boundary_payload(task, contract),
                "event_name": str(event_name),
                "target_feature_key": str(key),
                "true_balanced_accuracy": _safe_float(true_metrics["event_balanced_accuracy"]),
                "shuffled_balanced_accuracy": _safe_float(shuffled_metrics["event_balanced_accuracy"]),
                "balanced_accuracy_degradation": bal_deg,
                "true_r2": _safe_float(true_metrics["r2_vs_mean_baseline"]),
                "shuffled_r2": _safe_float(shuffled_metrics["r2_vs_mean_baseline"]),
                "r2_degradation": r2_deg,
                "negative_control_status": status,
            }
        )
    return pd.DataFrame(rows, columns=REQUIRED_4E_CONTROL_COLUMNS)


def _build_4e_leakage_table(model7: PCAModel) -> pd.DataFrame:
    task = "Task2-8j-4e"
    contract = "negative_control_leakage_audit__no_adoption_no_freeze"
    features = [str(c).lower() for c in model7.matrix.columns.astype(str).tolist()]
    hidden_count = sum("hidden" in f for f in features)
    truth_count = sum("truth" in f for f in features)
    future_count = sum("future" in f for f in features)
    detected = bool(hidden_count or truth_count or future_count)
    row = {
        **_boundary_payload(task, contract),
        "component_count": 7,
        "feature_count": int(len(features)),
        "hidden_feature_count": int(hidden_count),
        "truth_feature_count": int(truth_count),
        "future_feature_count": int(future_count),
        "hidden_truth_input_detected": detected,
        "leakage_audit_status": "pass" if not detected else "fail",
    }
    return pd.DataFrame([row], columns=REQUIRED_4E_LEAKAGE_COLUMNS)


def _build_4e_final_summary(control: pd.DataFrame, leakage: pd.DataFrame) -> pd.DataFrame:
    task = "Task2-8j-4e"
    contract = "negative_control_leakage_audit__no_adoption_no_freeze"
    mean_bal_deg = _safe_mean(control["balanced_accuracy_degradation"], default=0.0) if control is not None and not control.empty else 0.0
    mean_r2_deg = _safe_mean(control["r2_degradation"], default=0.0) if control is not None and not control.empty else 0.0
    detected = bool(leakage["hidden_truth_input_detected"].astype(bool).any()) if leakage is not None and not leakage.empty else False
    if detected:
        decision = "fail_hidden_or_future_signal_detected"
    elif mean_bal_deg >= -0.05:
        decision = "negative_control_no_leakage_detected"
    else:
        decision = "negative_control_watch"
    row = {
        **_boundary_payload(task, contract),
        "control_rows": int(len(control)) if control is not None else 0,
        "leakage_rows": int(len(leakage)) if leakage is not None else 0,
        "mean_balanced_accuracy_degradation": mean_bal_deg,
        "mean_r2_degradation": mean_r2_deg,
        "hidden_truth_input_detected": detected,
        "negative_control_decision": decision,
        "adoption_performed": False,
        "freeze_performed": False,
        "next_task": "Task 2-8j-5: effective-dimension fixed map contract",
    }
    return pd.DataFrame([row], columns=REQUIRED_4E_FINAL_COLUMNS)
