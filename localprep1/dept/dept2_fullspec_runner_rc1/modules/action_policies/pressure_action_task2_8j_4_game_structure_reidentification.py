"""Task 2-8j-4: v2 game-structure re-identification test RC1.

Purpose:
    Test whether candidate effective-dimension maps can read back the v2
    game-structure from G_t-like coordinates.  This task compares the current
    6-axis static PCA standard candidate with a 7-axis shadow-expansion
    candidate, while keeping 3-axis as a lightweight coarse-map reference.

    This is not another PCA score check.  The goal is to ask whether the
    compressed G_t map can re-identify scenario structure and future structural
    events such as relation lock, uncertainty, resource pressure, information
    quality degradation, and coordination lag.

Boundary:
    - validation only
    - no effective dimension adoption or freeze
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
    fit_pca_validation_models,
)


TASK2_8J_4_VERSION = "game_structure_reidentification_rc1"
TASK2_8J_4_CONTRACT = (
    "Task2_8j_4_v2_game_structure_reidentification__"
    "static_pca_6_standard_vs_7_shadow_expansion__no_adoption_no_freeze"
)

BOUNDARY_COLUMNS = [
    "task2_8j_4_version",
    "task2_8j_4_contract",
    "validation_only",
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

REQUIRED_SCENARIO_COLUMNS = BOUNDARY_COLUMNS + [
    "mode",
    "component_count",
    "map_role",
    "train_rows",
    "test_rows",
    "scenario_count",
    "scenario_reidentification_accuracy",
    "scenario_reidentification_status",
]

REQUIRED_EVENT_COLUMNS = BOUNDARY_COLUMNS + [
    "mode",
    "component_count",
    "map_role",
    "target_feature_key",
    "event_name",
    "event_direction",
    "prediction_horizon",
    "train_rows",
    "test_rows",
    "threshold",
    "event_prevalence",
    "rmse",
    "baseline_rmse",
    "r2_vs_mean_baseline",
    "event_accuracy",
    "event_balanced_accuracy",
    "event_f1",
    "event_status",
]

REQUIRED_COMPARISON_COLUMNS = BOUNDARY_COLUMNS + [
    "component_count",
    "map_role",
    "scenario_accuracy",
    "mean_event_balanced_accuracy",
    "mean_event_f1",
    "mean_event_r2",
    "information_quality_balanced_accuracy",
    "coordination_lag_balanced_accuracy",
    "relation_lock_balanced_accuracy",
    "resource_pressure_balanced_accuracy",
    "structure_reidentification_score",
    "delta_score_from_static_6",
    "candidate_status",
    "candidate_reason",
]

REQUIRED_FINAL_SUMMARY_COLUMNS = BOUNDARY_COLUMNS + [
    "standard_component_count",
    "shadow_component_count",
    "standard_structure_reidentification_score",
    "shadow_structure_reidentification_score",
    "shadow_delta_from_standard",
    "standard_scenario_accuracy",
    "shadow_scenario_accuracy",
    "standard_mean_event_balanced_accuracy",
    "shadow_mean_event_balanced_accuracy",
    "standard_information_quality_balanced_accuracy",
    "shadow_information_quality_balanced_accuracy",
    "standard_coordination_lag_balanced_accuracy",
    "shadow_coordination_lag_balanced_accuracy",
    "baseline_update_worth_check",
    "recommendation",
    "adoption_performed",
    "freeze_performed",
    "next_task",
]


@dataclass(frozen=True)
class GameStructureReidentificationConfig:
    component_counts: tuple[int, ...] = (3, 6, 7, 8)
    standard_component_count: int = 6
    shadow_component_count: int = 7
    prediction_horizon: int = 3
    train_quantile: float = 0.67
    high_event_quantile: float = 0.67
    low_event_quantile: float = 0.33
    min_train_rows: int = 8
    min_test_rows: int = 4
    strong_delta_threshold: float = 0.04
    weak_delta_threshold: float = 0.015


EVENT_TARGETS: tuple[tuple[str, str, str], ...] = (
    ("relation_lock", "relation_lock_high", "high"),
    ("uncertainty", "uncertainty_high", "high"),
    ("resource_pressure", "resource_pressure_high", "high"),
    ("commons_health", "commons_health_low", "low"),
    ("information_quality_mean", "information_quality_low", "low"),
    ("coordination_lag_mean", "coordination_lag_high", "high"),
    ("exploration", "exploration_high", "high"),
    ("reversibility", "reversibility_low", "low"),
)


def _boundary_payload() -> dict:
    return {
        "task2_8j_4_version": TASK2_8J_4_VERSION,
        "task2_8j_4_contract": TASK2_8J_4_CONTRACT,
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


def _map_role(component_count: int, cfg: GameStructureReidentificationConfig) -> str:
    if int(component_count) == int(cfg.standard_component_count):
        return "standard_6_axis_map"
    if int(component_count) == int(cfg.shadow_component_count):
        return "shadow_7_axis_expansion_map"
    if int(component_count) < int(cfg.standard_component_count):
        return "lightweight_coarse_map"
    return "extra_expansion_reference_map"


def _linear_regression_predict(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray) -> np.ndarray:
    x_train = np.column_stack([np.ones(train_x.shape[0]), train_x])
    x_test = np.column_stack([np.ones(test_x.shape[0]), test_x])
    beta, *_ = np.linalg.lstsq(x_train, train_y, rcond=None)
    return x_test @ beta


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


def _time_split_mask(index: pd.Index, cfg: GameStructureReidentificationConfig) -> np.ndarray:
    t_values = np.asarray([int(idx[2]) for idx in index.tolist()], dtype=int)
    cutoff = float(np.quantile(t_values, cfg.train_quantile))
    return t_values <= cutoff


def _build_future_target_rows(model: PCAModel, key: str, cfg: GameStructureReidentificationConfig) -> tuple[pd.Index, np.ndarray, np.ndarray]:
    mat = model.matrix
    aligned: list[tuple[object, float]] = []
    for seed, scenario in sorted(set((idx[0], idx[1]) for idx in mat.index.tolist())):
        sub_idx = [idx for idx in mat.index if idx[0] == seed and idx[1] == scenario]
        sub_idx = sorted(sub_idx, key=lambda x: int(x[2]))
        for pos, idx in enumerate(sub_idx):
            future_pos = pos + int(cfg.prediction_horizon)
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


def build_scenario_reidentification_table(
    models: dict[int, PCAModel],
    cfg: GameStructureReidentificationConfig | None = None,
) -> pd.DataFrame:
    cfg = cfg or GameStructureReidentificationConfig()
    rows: list[dict] = []
    for component_count, model in models.items():
        mat = model.matrix
        if mat.empty:
            continue
        train_mask = _time_split_mask(mat.index, cfg)
        test_mask = ~train_mask
        if int(train_mask.sum()) < cfg.min_train_rows or int(test_mask.sum()) < cfg.min_test_rows:
            continue
        labels = np.asarray([str(idx[1]) for idx in mat.index.tolist()], dtype=object)
        train_x = model.scores[train_mask]
        test_x = model.scores[test_mask]
        train_y = labels[train_mask]
        test_y = labels[test_mask]
        centroids: dict[str, np.ndarray] = {}
        for label in sorted(set(train_y.tolist())):
            centroids[str(label)] = train_x[train_y == label].mean(axis=0)
        if not centroids:
            continue
        pred: list[str] = []
        for row in test_x:
            best_label = min(centroids, key=lambda k: float(np.linalg.norm(row - centroids[k])))
            pred.append(best_label)
        accuracy = float(np.mean(np.asarray(pred, dtype=object) == test_y)) if len(test_y) else 0.0
        rows.append(
            {
                **_boundary_payload(),
                "mode": "static_pca",
                "component_count": int(component_count),
                "map_role": _map_role(component_count, cfg),
                "train_rows": int(train_mask.sum()),
                "test_rows": int(test_mask.sum()),
                "scenario_count": int(len(set(labels.tolist()))),
                "scenario_reidentification_accuracy": accuracy,
                "scenario_reidentification_status": "pass" if accuracy >= 0.40 else "watch",
            }
        )
    return pd.DataFrame(rows, columns=REQUIRED_SCENARIO_COLUMNS)


def build_event_reidentification_table(
    models: dict[int, PCAModel],
    cfg: GameStructureReidentificationConfig | None = None,
) -> pd.DataFrame:
    cfg = cfg or GameStructureReidentificationConfig()
    rows: list[dict] = []
    for component_count, model in models.items():
        feature_keys = set(model.matrix.columns.astype(str).tolist())
        for token, event_name, direction in EVENT_TARGETS:
            matches = [key for key in sorted(feature_keys) if token in key and key.endswith("::w1")]
            if not matches:
                matches = [key for key in sorted(feature_keys) if token in key]
            if not matches:
                continue
            key = matches[0]
            idxs, x, y = _build_future_target_rows(model, key, cfg)
            if len(y) < cfg.min_train_rows + cfg.min_test_rows:
                continue
            train_mask = _time_split_mask(idxs, cfg)
            test_mask = ~train_mask
            if int(train_mask.sum()) < cfg.min_train_rows or int(test_mask.sum()) < cfg.min_test_rows:
                continue
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
            rows.append(
                {
                    **_boundary_payload(),
                    "mode": "static_pca",
                    "component_count": int(component_count),
                    "map_role": _map_role(component_count, cfg),
                    "target_feature_key": str(key),
                    "event_name": str(event_name),
                    "event_direction": str(direction),
                    "prediction_horizon": int(cfg.prediction_horizon),
                    "train_rows": int(train_mask.sum()),
                    "test_rows": int(test_mask.sum()),
                    "threshold": threshold,
                    "event_prevalence": prevalence,
                    "rmse": rmse,
                    "baseline_rmse": baseline_rmse,
                    "r2_vs_mean_baseline": r2,
                    "event_accuracy": accuracy,
                    "event_balanced_accuracy": balanced,
                    "event_f1": f1,
                    "event_status": "pass" if balanced >= 0.55 else "watch",
                }
            )
    return pd.DataFrame(rows, columns=REQUIRED_EVENT_COLUMNS)


def _event_metric(event_rows: pd.DataFrame, component_count: int, event_name: str, metric: str) -> float:
    if event_rows is None or event_rows.empty:
        return 0.0
    rows = event_rows[
        (event_rows["component_count"].astype(int) == int(component_count))
        & (event_rows["event_name"].astype(str) == str(event_name))
    ]
    if rows.empty:
        return 0.0
    return _safe_mean(rows[metric], default=0.0)


def build_reidentification_comparison_table(
    scenario_table: pd.DataFrame,
    event_table: pd.DataFrame,
    cfg: GameStructureReidentificationConfig | None = None,
) -> pd.DataFrame:
    cfg = cfg or GameStructureReidentificationConfig()
    rows: list[dict] = []
    standard_score = 0.0
    for component_count in cfg.component_counts:
        scn_rows = scenario_table[scenario_table["component_count"].astype(int) == int(component_count)] if scenario_table is not None and not scenario_table.empty else pd.DataFrame()
        ev_rows = event_table[event_table["component_count"].astype(int) == int(component_count)] if event_table is not None and not event_table.empty else pd.DataFrame()
        scenario_acc = _safe_mean(scn_rows["scenario_reidentification_accuracy"], default=0.0) if not scn_rows.empty else 0.0
        mean_event_bal = _safe_mean(ev_rows["event_balanced_accuracy"], default=0.0) if not ev_rows.empty else 0.0
        mean_event_f1 = _safe_mean(ev_rows["event_f1"], default=0.0) if not ev_rows.empty else 0.0
        mean_event_r2 = _safe_mean(ev_rows["r2_vs_mean_baseline"], default=0.0) if not ev_rows.empty else 0.0
        info_bal = _event_metric(event_table, component_count, "information_quality_low", "event_balanced_accuracy")
        coord_bal = _event_metric(event_table, component_count, "coordination_lag_high", "event_balanced_accuracy")
        rel_bal = _event_metric(event_table, component_count, "relation_lock_high", "event_balanced_accuracy")
        resource_bal = _event_metric(event_table, component_count, "resource_pressure_high", "event_balanced_accuracy")
        structure_score = float(
            np.clip(
                0.30 * scenario_acc
                + 0.30 * mean_event_bal
                + 0.15 * mean_event_f1
                + 0.10 * max(-1.0, min(1.0, mean_event_r2))
                + 0.10 * coord_bal
                + 0.05 * info_bal,
                0.0,
                1.0,
            )
        )
        if int(component_count) == int(cfg.standard_component_count):
            standard_score = structure_score
        rows.append(
            {
                **_boundary_payload(),
                "component_count": int(component_count),
                "map_role": _map_role(component_count, cfg),
                "scenario_accuracy": scenario_acc,
                "mean_event_balanced_accuracy": mean_event_bal,
                "mean_event_f1": mean_event_f1,
                "mean_event_r2": mean_event_r2,
                "information_quality_balanced_accuracy": info_bal,
                "coordination_lag_balanced_accuracy": coord_bal,
                "relation_lock_balanced_accuracy": rel_bal,
                "resource_pressure_balanced_accuracy": resource_bal,
                "structure_reidentification_score": structure_score,
                "delta_score_from_static_6": 0.0,
                "candidate_status": "candidate_watch",
                "candidate_reason": "pending_standard_delta",
            }
        )
    out = pd.DataFrame(rows, columns=REQUIRED_COMPARISON_COLUMNS)
    if not out.empty:
        out["delta_score_from_static_6"] = out["structure_reidentification_score"].astype(float) - float(standard_score)
        statuses = []
        reasons = []
        for _, row in out.iterrows():
            delta = _safe_float(row["delta_score_from_static_6"])
            count = int(row["component_count"])
            if count == int(cfg.standard_component_count):
                statuses.append("standard_reference")
                reasons.append("current_6_axis_standard_reference")
            elif delta >= cfg.strong_delta_threshold:
                statuses.append("candidate_strong")
                reasons.append("beats_static_6_by_strong_margin")
            elif delta >= cfg.weak_delta_threshold:
                statuses.append("candidate_watch")
                reasons.append("beats_static_6_by_weak_margin")
            else:
                statuses.append("candidate_watch")
                reasons.append("does_not_beat_static_6_by_meaningful_margin")
        out["candidate_status"] = statuses
        out["candidate_reason"] = reasons
    return out


def build_reidentification_final_summary(
    comparison_table: pd.DataFrame,
    cfg: GameStructureReidentificationConfig | None = None,
) -> pd.DataFrame:
    cfg = cfg or GameStructureReidentificationConfig()
    if comparison_table is None or comparison_table.empty:
        row = {
            **_boundary_payload(),
            "standard_component_count": int(cfg.standard_component_count),
            "shadow_component_count": int(cfg.shadow_component_count),
            "standard_structure_reidentification_score": 0.0,
            "shadow_structure_reidentification_score": 0.0,
            "shadow_delta_from_standard": 0.0,
            "standard_scenario_accuracy": 0.0,
            "shadow_scenario_accuracy": 0.0,
            "standard_mean_event_balanced_accuracy": 0.0,
            "shadow_mean_event_balanced_accuracy": 0.0,
            "standard_information_quality_balanced_accuracy": 0.0,
            "shadow_information_quality_balanced_accuracy": 0.0,
            "standard_coordination_lag_balanced_accuracy": 0.0,
            "shadow_coordination_lag_balanced_accuracy": 0.0,
            "baseline_update_worth_check": "insufficient_rows",
            "recommendation": "rerun_reidentification_validation",
            "adoption_performed": False,
            "freeze_performed": False,
            "next_task": "Task 2-8j-5: effective-dimension freeze candidate contract",
        }
        return pd.DataFrame([row], columns=REQUIRED_FINAL_SUMMARY_COLUMNS)

    def row_for(count: int) -> pd.Series:
        rows = comparison_table[comparison_table["component_count"].astype(int) == int(count)]
        if rows.empty:
            return pd.Series(dtype=object)
        return rows.iloc[0]

    standard = row_for(cfg.standard_component_count)
    shadow = row_for(cfg.shadow_component_count)
    standard_score = _safe_float(standard.get("structure_reidentification_score", 0.0), default=0.0)
    shadow_score = _safe_float(shadow.get("structure_reidentification_score", 0.0), default=0.0)
    delta = shadow_score - standard_score
    if delta >= cfg.strong_delta_threshold:
        worth = "yes_shadow_7_beats_standard_6"
        recommendation = "keep_no_adoption_yet_but_promote_7_axis_to_freeze_candidate_check"
    elif delta >= cfg.weak_delta_threshold:
        worth = "weak_shadow_7_advantage"
        recommendation = "keep_6_axis_standard_and_carry_7_axis_shadow_into_freeze_contract"
    else:
        worth = "no_clear_replacement_value_yet"
        recommendation = "keep_6_axis_standard_and_keep_7_axis_as_shadow_expansion_only"

    row = {
        **_boundary_payload(),
        "standard_component_count": int(cfg.standard_component_count),
        "shadow_component_count": int(cfg.shadow_component_count),
        "standard_structure_reidentification_score": standard_score,
        "shadow_structure_reidentification_score": shadow_score,
        "shadow_delta_from_standard": delta,
        "standard_scenario_accuracy": _safe_float(standard.get("scenario_accuracy", 0.0), default=0.0),
        "shadow_scenario_accuracy": _safe_float(shadow.get("scenario_accuracy", 0.0), default=0.0),
        "standard_mean_event_balanced_accuracy": _safe_float(standard.get("mean_event_balanced_accuracy", 0.0), default=0.0),
        "shadow_mean_event_balanced_accuracy": _safe_float(shadow.get("mean_event_balanced_accuracy", 0.0), default=0.0),
        "standard_information_quality_balanced_accuracy": _safe_float(standard.get("information_quality_balanced_accuracy", 0.0), default=0.0),
        "shadow_information_quality_balanced_accuracy": _safe_float(shadow.get("information_quality_balanced_accuracy", 0.0), default=0.0),
        "standard_coordination_lag_balanced_accuracy": _safe_float(standard.get("coordination_lag_balanced_accuracy", 0.0), default=0.0),
        "shadow_coordination_lag_balanced_accuracy": _safe_float(shadow.get("coordination_lag_balanced_accuracy", 0.0), default=0.0),
        "baseline_update_worth_check": worth,
        "recommendation": recommendation,
        "adoption_performed": False,
        "freeze_performed": False,
        "next_task": "Task 2-8j-5: effective-dimension freeze candidate contract",
    }
    return pd.DataFrame([row], columns=REQUIRED_FINAL_SUMMARY_COLUMNS)


def validate_game_structure_reidentification_tables(
    scenario_table: pd.DataFrame,
    event_table: pd.DataFrame,
    comparison_table: pd.DataFrame,
    final_summary: pd.DataFrame,
    cfg: GameStructureReidentificationConfig | None = None,
    upstream_errors: list[str] | None = None,
) -> list[str]:
    cfg = cfg or GameStructureReidentificationConfig()
    errors: list[str] = []
    if upstream_errors:
        errors.extend(f"task2_8j_4_upstream_error:{e}" for e in upstream_errors)
    tables = {
        "scenario": (scenario_table, REQUIRED_SCENARIO_COLUMNS),
        "event": (event_table, REQUIRED_EVENT_COLUMNS),
        "comparison": (comparison_table, REQUIRED_COMPARISON_COLUMNS),
        "final_summary": (final_summary, REQUIRED_FINAL_SUMMARY_COLUMNS),
    }
    for name, (table, required) in tables.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_4_empty_table:{name}")
            continue
        missing = [c for c in required if c not in table.columns]
        if missing:
            errors.append(f"task2_8j_4_missing_columns:{name}:" + ",".join(missing))
            continue
        if not bool(table["validation_only"].astype(bool).all()):
            errors.append(f"task2_8j_4_validation_only_not_all_true:{name}")
        for col in [
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
        ]:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_4_forbidden_true:{name}:{col}")

    if comparison_table is not None and not comparison_table.empty:
        counts = set(comparison_table["component_count"].astype(int).tolist())
        for required_count in [3, cfg.standard_component_count, cfg.shadow_component_count]:
            if int(required_count) not in counts:
                errors.append(f"task2_8j_4_missing_component_count:{required_count}")
        for col in [
            "scenario_accuracy",
            "mean_event_balanced_accuracy",
            "mean_event_f1",
            "information_quality_balanced_accuracy",
            "coordination_lag_balanced_accuracy",
            "structure_reidentification_score",
        ]:
            if not bool(comparison_table[col].astype(float).between(0.0, 1.0).all()):
                errors.append(f"task2_8j_4_score_out_of_range:{col}")
    if event_table is not None and not event_table.empty:
        names = set(event_table["event_name"].astype(str).unique().tolist())
        for required_event in ["information_quality_low", "coordination_lag_high", "relation_lock_high"]:
            if required_event not in names:
                errors.append(f"task2_8j_4_missing_event:{required_event}")
    if final_summary is not None and not final_summary.empty:
        if bool(final_summary["adoption_performed"].astype(bool).any()):
            errors.append("task2_8j_4_adoption_performed_true")
        if bool(final_summary["freeze_performed"].astype(bool).any()):
            errors.append("task2_8j_4_freeze_performed_true")
    return errors


def summarize_game_structure_reidentification(
    scenario_table: pd.DataFrame,
    event_table: pd.DataFrame,
    comparison_table: pd.DataFrame,
    final_summary: pd.DataFrame,
) -> dict:
    if comparison_table is None or comparison_table.empty:
        return {"rows": 0, "best_component_count": 0}
    best = comparison_table.sort_values("structure_reidentification_score", ascending=False).iloc[0]
    summary_row = final_summary.iloc[0] if final_summary is not None and not final_summary.empty else pd.Series(dtype=object)
    return {
        "scenario_rows": int(len(scenario_table)) if scenario_table is not None else 0,
        "event_rows": int(len(event_table)) if event_table is not None else 0,
        "comparison_rows": int(len(comparison_table)) if comparison_table is not None else 0,
        "final_summary_rows": int(len(final_summary)) if final_summary is not None else 0,
        "component_counts": sorted(comparison_table["component_count"].astype(int).unique().tolist()),
        "best_component_count": int(best["component_count"]),
        "best_structure_reidentification_score": _safe_float(best["structure_reidentification_score"]),
        "standard_component_count": int(summary_row.get("standard_component_count", 6)),
        "shadow_component_count": int(summary_row.get("shadow_component_count", 7)),
        "shadow_delta_from_standard": _safe_float(summary_row.get("shadow_delta_from_standard", 0.0), default=0.0),
        "baseline_update_worth_check": str(summary_row.get("baseline_update_worth_check", "")),
        "recommendation": str(summary_row.get("recommendation", "")),
        "adoption_performed": False,
        "freeze_performed": False,
    }


def build_and_validate_game_structure_reidentification(
    feature_cfg: CandidateFeatureLogConfig | None = None,
    reid_cfg: GameStructureReidentificationConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    feature_cfg = feature_cfg or CandidateFeatureLogConfig(steps=24, seeds=(501, 502, 503), window_sizes=(1, 6, 12))
    reid_cfg = reid_cfg or GameStructureReidentificationConfig()
    feature_log = build_candidate_feature_log(feature_cfg)
    feature_errors = validate_candidate_feature_log(feature_log)
    models: dict[int, PCAModel] = {}
    for count in reid_cfg.component_counts:
        pca_cfg = TemporalPCAValidationConfig(
            n_components=int(count),
            sparse_top_k=12,
            prediction_horizon=int(reid_cfg.prediction_horizon),
            min_prediction_rows=int(reid_cfg.min_train_rows),
        )
        fitted = fit_pca_validation_models(feature_log, pca_cfg)
        models[int(count)] = fitted["static_pca"]
    scenario_table = build_scenario_reidentification_table(models, reid_cfg)
    event_table = build_event_reidentification_table(models, reid_cfg)
    comparison_table = build_reidentification_comparison_table(scenario_table, event_table, reid_cfg)
    final_summary = build_reidentification_final_summary(comparison_table, reid_cfg)
    errors = validate_game_structure_reidentification_tables(
        scenario_table,
        event_table,
        comparison_table,
        final_summary,
        reid_cfg,
        feature_errors,
    )
    summary = summarize_game_structure_reidentification(scenario_table, event_table, comparison_table, final_summary)
    summary["validation_errors"] = errors
    return scenario_table, event_table, comparison_table, final_summary, errors, summary
