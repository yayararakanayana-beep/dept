"""Task 2-8j-6: fixed-7-axis G_t macro-game relation-field validation RC1.

Purpose:
    Validate whether the fixed static_pca_7 G_t map can be used to extract
    macro-game dynamics and build a relation field among those dynamics.

Position:
    This task comes after:
        - Task 2-8j-5: static_pca_7 fixed-map contract
        - Task 2-8j-5b: incomplete-observation / coarse information-ingestion contract

Interpretation:
    G_t is treated as a fixed 7-axis distribution summary.  It is not a raw-log
    store.  Short/mid/long and local/relation/global history remain upstream in
    candidate feature logs / K_t-style buffers.  This task uses the resulting
    coarse observable information to ask whether relation-lock, coordination lag,
    information degradation, resource pressure, and related macro-game signals
    can be read back from G_t coordinates.

Boundary:
    - validation only
    - fixed static_pca_7 main map
    - no effective-dimension re-fitting
    - no axis mutation
    - no residual auxiliary dimension injection into G_t main map
    - no action-weight conversion
    - no upper-pressure connection
    - no ActionFrame / ActionModule / FullSpec runtime / canonical write
    - no hidden-truth / future-information input
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

TASK2_8J_6_VERSION = "fixed_7axis_macro_game_relation_field_validation_rc1"
TASK2_8J_6_CONTRACT = (
    "Task2_8j_6_macro_game_relation_field__static_pca_7_gt_main__"
    "coarse_observable_information__no_axis_mutation_no_runtime_write"
)

BOUNDARY_COLUMNS = [
    "task2_8j_6_version",
    "task2_8j_6_contract",
    "validation_only",
    "incomplete_observation_assumption",
    "gt_main_map_name",
    "gt_main_component_count",
    "runtime_policy_input",
    "fullspec_runtime_connected",
    "upper_pressure_connected",
    "action_frame_created",
    "actionmodule_called",
    "canonical_write_performed",
    "gk_writeback_performed",
    "ot_writeback_performed",
    "effective_dimension_refit_performed",
    "axis_mutation_performed",
    "residual_auxiliary_injected_into_gt_main",
    "dynamics_axis_extracted_for_action",
    "action_weight_converted",
    "hidden_truth_input",
    "future_information_used",
]

REQUIRED_SIGNAL_COLUMNS = BOUNDARY_COLUMNS + [
    "macro_signal",
    "signal_role",
    "source_feature_keys",
    "target_direction",
    "primary_gt_component",
    "primary_component_alignment",
    "train_rows",
    "test_rows",
    "rmse",
    "baseline_rmse",
    "r2_vs_mean_baseline",
    "extraction_confidence",
    "signal_status",
]

REQUIRED_STATE_COLUMNS = BOUNDARY_COLUMNS + [
    "seed",
    "scenario",
    "t",
    "macro_signal",
    "observed_signal_intensity",
    "gt_predicted_signal_intensity",
    "signal_residual",
    "state_confidence",
]

REQUIRED_RELATION_FIELD_COLUMNS = BOUNDARY_COLUMNS + [
    "source_macro_signal",
    "target_macro_signal",
    "same_time_correlation",
    "lagged_source_to_target_correlation",
    "relation_strength",
    "relation_direction",
    "relation_field_status",
]

REQUIRED_SUMMARY_COLUMNS = BOUNDARY_COLUMNS + [
    "macro_signal_count",
    "extractable_signal_count",
    "relation_edge_count",
    "strong_relation_edge_count",
    "mean_signal_r2",
    "mean_extraction_confidence",
    "relation_field_decision",
    "next_task",
]


@dataclass(frozen=True)
class MacroGameRelationFieldConfig:
    gt_main_component_count: int = 7
    prediction_train_quantile: float = 0.67
    min_train_rows: int = 8
    min_test_rows: int = 4
    extractable_r2_threshold: float = 0.0
    strong_relation_threshold: float = 0.35
    weak_relation_threshold: float = 0.20


@dataclass(frozen=True)
class MacroSignalSpec:
    name: str
    role: str
    tokens: tuple[str, ...]
    direction: str = "high"


MACRO_SIGNAL_SPECS: tuple[MacroSignalSpec, ...] = (
    MacroSignalSpec(
        "relation_lock",
        "relation rigidity / lock-in pressure",
        ("relation_lock", "relation_rigidity"),
        "high",
    ),
    MacroSignalSpec(
        "coordination_lag",
        "coordination delay and collective-response lag",
        ("coordination_lag_mean", "coordination_lag"),
        "high",
    ),
    MacroSignalSpec(
        "information_degradation",
        "observable information-quality degradation, delay, distortion, and misread pressure",
        ("information_quality_mean", "information_quality"),
        "low",
    ),
    MacroSignalSpec(
        "resource_pressure",
        "resource pressure, depletion, inequality, and commons-health stress",
        ("resource_pressure", "resource_inequality", "commons_health"),
        "high",
    ),
    MacroSignalSpec(
        "exploration_activity",
        "exploration / search activity retained by the system",
        ("exploration", "explore_tendency"),
        "high",
    ),
    MacroSignalSpec(
        "reversibility_loss",
        "loss of reversibility and recovery margin",
        ("reversibility_delta", "reversibility"),
        "low",
    ),
    MacroSignalSpec(
        "hoarding_extraction_pressure",
        "defensive hoarding / extraction / exploitation pressure",
        ("hoard_tendency", "extract_tendency", "exploitation_risk_delta"),
        "high",
    ),
)


def _boundary_payload() -> dict:
    return {
        "task2_8j_6_version": TASK2_8J_6_VERSION,
        "task2_8j_6_contract": TASK2_8J_6_CONTRACT,
        "validation_only": True,
        "incomplete_observation_assumption": True,
        "gt_main_map_name": "static_pca_7",
        "gt_main_component_count": 7,
        "runtime_policy_input": False,
        "fullspec_runtime_connected": False,
        "upper_pressure_connected": False,
        "action_frame_created": False,
        "actionmodule_called": False,
        "canonical_write_performed": False,
        "gk_writeback_performed": False,
        "ot_writeback_performed": False,
        "effective_dimension_refit_performed": False,
        "axis_mutation_performed": False,
        "residual_auxiliary_injected_into_gt_main": False,
        "dynamics_axis_extracted_for_action": False,
        "action_weight_converted": False,
        "hidden_truth_input": False,
        "future_information_used": False,
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
    arr = pd.to_numeric(pd.Series(values), errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if arr.empty:
        return float(default)
    return float(arr.mean())


def _safe_corr(a: np.ndarray, b: np.ndarray) -> float:
    x = np.asarray(a, dtype=float)
    y = np.asarray(b, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    x = x[mask]
    y = y[mask]
    if len(x) < 3 or float(np.std(x)) <= 1e-12 or float(np.std(y)) <= 1e-12:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


def _standardize(values: np.ndarray, *, invert: bool = False) -> np.ndarray:
    x = np.asarray(values, dtype=float)
    x = np.nan_to_num(x, nan=0.0, posinf=0.0, neginf=0.0)
    if invert:
        x = -x
    std = float(np.std(x))
    if std <= 1e-12:
        return np.zeros_like(x, dtype=float)
    return (x - float(np.mean(x))) / std


def _linear_regression_predict(train_x: np.ndarray, train_y: np.ndarray, test_x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    x_train = np.column_stack([np.ones(train_x.shape[0]), train_x])
    x_test = np.column_stack([np.ones(test_x.shape[0]), test_x])
    beta, *_ = np.linalg.lstsq(x_train, train_y, rcond=None)
    return x_test @ beta, beta[1:]


def _time_split_mask(index: pd.Index, train_quantile: float) -> np.ndarray:
    t_values = np.asarray([int(idx[2]) for idx in index.tolist()], dtype=int)
    cutoff = float(np.quantile(t_values, train_quantile))
    return t_values <= cutoff


def _find_signal_keys(columns: list[str], tokens: tuple[str, ...]) -> list[str]:
    out: list[str] = []
    for token in tokens:
        token_l = token.lower()
        matched = [c for c in columns if token_l in c.lower()]
        out.extend(matched)
    # Prefer a compact stable order and avoid duplicates.
    deduped = sorted(dict.fromkeys(out))
    # Use at most 8 feature keys per signal to avoid letting one broad token dominate.
    preferred = [c for c in deduped if c.endswith("::w1")]
    if preferred:
        remaining = [c for c in deduped if c not in preferred]
        return (preferred + remaining)[:8]
    return deduped[:8]


def _fit_fixed7_model(feature_cfg: CandidateFeatureLogConfig | None) -> tuple[PCAModel, list[str]]:
    feature_cfg = feature_cfg or CandidateFeatureLogConfig(steps=24, seeds=(501, 502, 503), window_sizes=(1, 6, 12))
    feature_log = build_candidate_feature_log(feature_cfg)
    errors = validate_candidate_feature_log(feature_log)
    pca_cfg = TemporalPCAValidationConfig(n_components=7, sparse_top_k=12, prediction_horizon=3, min_prediction_rows=8)
    model = fit_pca_validation_models(feature_log, pca_cfg)["static_pca"]
    return model, errors


def _signal_series(model: PCAModel, spec: MacroSignalSpec) -> tuple[list[str], np.ndarray]:
    columns = model.matrix.columns.astype(str).tolist()
    keys = _find_signal_keys(columns, spec.tokens)
    if not keys:
        return [], np.asarray([], dtype=float)
    values = model.matrix[keys].astype(float).mean(axis=1).to_numpy(dtype=float)
    return keys, _standardize(values, invert=(spec.direction == "low"))


def _signal_status(r2: float, confidence: float, cfg: MacroGameRelationFieldConfig) -> str:
    if r2 >= cfg.extractable_r2_threshold and confidence >= 0.45:
        return "extractable_from_fixed_7axis_gt"
    if r2 >= -0.10:
        return "watch_weak_but_available"
    return "weak_signal_not_reliable_yet"


def build_macro_signal_extraction_table(
    model: PCAModel,
    cfg: MacroGameRelationFieldConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, np.ndarray]]:
    cfg = cfg or MacroGameRelationFieldConfig()
    score_df = pd.DataFrame(
        model.scores[:, : int(cfg.gt_main_component_count)],
        index=model.matrix.index,
        columns=[f"gt_axis_{i + 1}" for i in range(int(cfg.gt_main_component_count))],
    )
    train_mask = _time_split_mask(score_df.index, cfg.prediction_train_quantile)
    test_mask = ~train_mask
    signal_rows = []
    state_rows = []
    predicted_signals: dict[str, np.ndarray] = {}
    for spec in MACRO_SIGNAL_SPECS:
        keys, y = _signal_series(model, spec)
        if not keys or len(y) != len(score_df):
            continue
        if int(train_mask.sum()) < cfg.min_train_rows or int(test_mask.sum()) < cfg.min_test_rows:
            continue
        train_x = score_df.to_numpy(dtype=float)[train_mask]
        test_x = score_df.to_numpy(dtype=float)[test_mask]
        train_y = y[train_mask]
        test_y = y[test_mask]
        pred_y, beta = _linear_regression_predict(train_x, train_y, test_x)
        full_pred = np.empty_like(y, dtype=float)
        full_pred[train_mask] = _linear_regression_predict(train_x, train_y, train_x)[0]
        full_pred[test_mask] = pred_y
        predicted_signals[spec.name] = full_pred
        rmse = float(sqrt(float(np.mean((pred_y - test_y) ** 2))))
        baseline = float(np.mean(train_y))
        baseline_rmse = float(sqrt(float(np.mean((baseline - test_y) ** 2))))
        r2 = float(1.0 - (rmse**2 / max(baseline_rmse**2, 1e-12)))
        primary_idx = int(np.argmax(np.abs(beta))) if beta.size else 0
        alignment = float(beta[primary_idx]) if beta.size else 0.0
        confidence = max(0.0, min(1.0, 0.5 + (r2 / 2.0)))
        signal_rows.append(
            {
                **_boundary_payload(),
                "macro_signal": spec.name,
                "signal_role": spec.role,
                "source_feature_keys": ";".join(keys),
                "target_direction": spec.direction,
                "primary_gt_component": int(primary_idx + 1),
                "primary_component_alignment": alignment,
                "train_rows": int(train_mask.sum()),
                "test_rows": int(test_mask.sum()),
                "rmse": rmse,
                "baseline_rmse": baseline_rmse,
                "r2_vs_mean_baseline": r2,
                "extraction_confidence": confidence,
                "signal_status": _signal_status(r2, confidence, cfg),
            }
        )
        for idx, observed, pred in zip(score_df.index.tolist(), y, full_pred):
            state_rows.append(
                {
                    **_boundary_payload(),
                    "seed": int(idx[0]),
                    "scenario": str(idx[1]),
                    "t": int(idx[2]),
                    "macro_signal": spec.name,
                    "observed_signal_intensity": _safe_float(observed),
                    "gt_predicted_signal_intensity": _safe_float(pred),
                    "signal_residual": _safe_float(observed - pred),
                    "state_confidence": confidence,
                }
            )
    signal_table = pd.DataFrame(signal_rows, columns=REQUIRED_SIGNAL_COLUMNS)
    state_table = pd.DataFrame(state_rows, columns=REQUIRED_STATE_COLUMNS)
    return signal_table, state_table, predicted_signals


def build_relation_field_table(
    model: PCAModel,
    predicted_signals: dict[str, np.ndarray],
    cfg: MacroGameRelationFieldConfig | None = None,
) -> pd.DataFrame:
    cfg = cfg or MacroGameRelationFieldConfig()
    rows = []
    names = sorted(predicted_signals)
    index = list(model.matrix.index.tolist())
    index_df = pd.DataFrame(index, columns=["seed", "scenario", "t"])
    for source in names:
        for target in names:
            if source == target:
                continue
            a = np.asarray(predicted_signals[source], dtype=float)
            b = np.asarray(predicted_signals[target], dtype=float)
            same_corr = _safe_corr(a, b)
            lag_source: list[float] = []
            lag_target: list[float] = []
            for (seed, scenario), sub in index_df.groupby(["seed", "scenario"], sort=True):
                sub = sub.sort_values("t")
                pos = sub.index.to_list()
                for left, right in zip(pos[:-1], pos[1:]):
                    lag_source.append(float(a[left]))
                    lag_target.append(float(b[right]))
            lag_corr = _safe_corr(np.asarray(lag_source), np.asarray(lag_target))
            strength = float(max(abs(same_corr), abs(lag_corr)))
            if strength >= cfg.strong_relation_threshold:
                status = "strong_relation_field_edge"
            elif strength >= cfg.weak_relation_threshold:
                status = "weak_relation_field_edge"
            else:
                status = "watch_relation_field_edge"
            direction = "positive" if (lag_corr if abs(lag_corr) >= abs(same_corr) else same_corr) >= 0.0 else "negative"
            rows.append(
                {
                    **_boundary_payload(),
                    "source_macro_signal": source,
                    "target_macro_signal": target,
                    "same_time_correlation": same_corr,
                    "lagged_source_to_target_correlation": lag_corr,
                    "relation_strength": strength,
                    "relation_direction": direction,
                    "relation_field_status": status,
                }
            )
    out = pd.DataFrame(rows, columns=REQUIRED_RELATION_FIELD_COLUMNS)
    if not out.empty:
        out = out.sort_values("relation_strength", ascending=False).reset_index(drop=True)
    return out


def build_relation_field_final_summary(
    signal_table: pd.DataFrame,
    relation_field: pd.DataFrame,
    cfg: MacroGameRelationFieldConfig | None = None,
) -> pd.DataFrame:
    cfg = cfg or MacroGameRelationFieldConfig()
    macro_signal_count = int(len(signal_table)) if signal_table is not None else 0
    extractable = 0
    if signal_table is not None and not signal_table.empty:
        extractable = int(signal_table["signal_status"].astype(str).str.contains("extractable|watch_weak").sum())
    edge_count = int(len(relation_field)) if relation_field is not None else 0
    strong_edges = 0
    if relation_field is not None and not relation_field.empty:
        strong_edges = int((relation_field["relation_strength"].astype(float) >= cfg.strong_relation_threshold).sum())
    mean_r2 = _safe_mean(signal_table["r2_vs_mean_baseline"], default=0.0) if signal_table is not None and not signal_table.empty else 0.0
    mean_conf = _safe_mean(signal_table["extraction_confidence"], default=0.0) if signal_table is not None and not signal_table.empty else 0.0
    core_signals = {"relation_lock", "coordination_lag", "information_degradation", "resource_pressure"}
    observed_core = set(signal_table["macro_signal"].astype(str)) if signal_table is not None and not signal_table.empty else set()
    if core_signals.issubset(observed_core) and edge_count > 0 and mean_conf >= 0.35:
        decision = "macro_game_relation_field_extractable_from_fixed_7axis_gt"
    elif core_signals.issubset(observed_core):
        decision = "macro_game_relation_field_watch_but_core_signals_available"
    else:
        decision = "macro_game_relation_field_not_ready_missing_core_signals"
    row = {
        **_boundary_payload(),
        "macro_signal_count": macro_signal_count,
        "extractable_signal_count": extractable,
        "relation_edge_count": edge_count,
        "strong_relation_edge_count": strong_edges,
        "mean_signal_r2": mean_r2,
        "mean_extraction_confidence": mean_conf,
        "relation_field_decision": decision,
        "next_task": "Task 2-8j-7: O_t observation map over fixed-7-axis G_t relation field",
    }
    return pd.DataFrame([row], columns=REQUIRED_SUMMARY_COLUMNS)


def validate_macro_game_relation_field_tables(
    signal_table: pd.DataFrame,
    state_table: pd.DataFrame,
    relation_field: pd.DataFrame,
    final_summary: pd.DataFrame,
) -> list[str]:
    errors: list[str] = []
    tables = {
        "signal_table": (signal_table, REQUIRED_SIGNAL_COLUMNS),
        "state_table": (state_table, REQUIRED_STATE_COLUMNS),
        "relation_field": (relation_field, REQUIRED_RELATION_FIELD_COLUMNS),
        "final_summary": (final_summary, REQUIRED_SUMMARY_COLUMNS),
    }
    forbidden_true = [
        "runtime_policy_input",
        "fullspec_runtime_connected",
        "upper_pressure_connected",
        "action_frame_created",
        "actionmodule_called",
        "canonical_write_performed",
        "gk_writeback_performed",
        "ot_writeback_performed",
        "effective_dimension_refit_performed",
        "axis_mutation_performed",
        "residual_auxiliary_injected_into_gt_main",
        "dynamics_axis_extracted_for_action",
        "action_weight_converted",
        "hidden_truth_input",
        "future_information_used",
    ]
    for name, (table, required) in tables.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_6_empty_table:{name}")
            continue
        missing = [c for c in required if c not in table.columns]
        if missing:
            errors.append(f"task2_8j_6_missing_columns:{name}:" + ",".join(missing))
            continue
        for col in ["validation_only", "incomplete_observation_assumption"]:
            if not bool(table[col].astype(bool).all()):
                errors.append(f"task2_8j_6_required_true_not_all_true:{name}:{col}")
        if set(table["gt_main_map_name"].astype(str)) != {"static_pca_7"}:
            errors.append(f"task2_8j_6_wrong_gt_main_map_name:{name}")
        if set(table["gt_main_component_count"].astype(int)) != {7}:
            errors.append(f"task2_8j_6_wrong_gt_main_component_count:{name}")
        for col in forbidden_true:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_6_forbidden_true:{name}:{col}")
    if signal_table is not None and not signal_table.empty:
        core = {"relation_lock", "coordination_lag", "information_degradation", "resource_pressure"}
        got = set(signal_table["macro_signal"].astype(str))
        missing_core = sorted(core - got)
        if missing_core:
            errors.append("task2_8j_6_missing_core_macro_signals:" + ",".join(missing_core))
        if not bool(signal_table["extraction_confidence"].astype(float).between(0.0, 1.0).all()):
            errors.append("task2_8j_6_confidence_out_of_range")
    if relation_field is not None and not relation_field.empty:
        if not bool(relation_field["relation_strength"].astype(float).between(0.0, 1.0).all()):
            errors.append("task2_8j_6_relation_strength_out_of_range")
    return errors


def build_and_validate_macro_game_relation_field(
    feature_cfg: CandidateFeatureLogConfig | None = None,
    cfg: MacroGameRelationFieldConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    cfg = cfg or MacroGameRelationFieldConfig()
    model, upstream_errors = _fit_fixed7_model(feature_cfg)
    signal_table, state_table, predicted = build_macro_signal_extraction_table(model, cfg)
    relation_field = build_relation_field_table(model, predicted, cfg)
    final_summary = build_relation_field_final_summary(signal_table, relation_field, cfg)
    errors = [f"task2_8j_6_upstream_error:{e}" for e in upstream_errors]
    errors.extend(validate_macro_game_relation_field_tables(signal_table, state_table, relation_field, final_summary))
    summary = {
        "gt_main_map_name": "static_pca_7",
        "gt_main_component_count": 7,
        "macro_signal_count": int(final_summary["macro_signal_count"].iloc[0]) if not final_summary.empty else 0,
        "relation_edge_count": int(final_summary["relation_edge_count"].iloc[0]) if not final_summary.empty else 0,
        "mean_signal_r2": _safe_float(final_summary["mean_signal_r2"].iloc[0]) if not final_summary.empty else 0.0,
        "mean_extraction_confidence": _safe_float(final_summary["mean_extraction_confidence"].iloc[0]) if not final_summary.empty else 0.0,
        "relation_field_decision": str(final_summary["relation_field_decision"].iloc[0]) if not final_summary.empty else "empty",
        "validation_errors": errors,
    }
    return signal_table, state_table, relation_field, final_summary, errors, summary
