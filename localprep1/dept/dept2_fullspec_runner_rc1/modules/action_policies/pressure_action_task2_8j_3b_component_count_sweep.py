"""Task 2-8j-3b: effective-dimension component-count sweep RC1.

Purpose:
    Sweep effective-dimension component counts for the Task 2-8j static /
    temporal PCA candidates, with special attention to the current 6-axis
    standard candidate and 7/8-axis future expansion probes.

    This task supports the DEPT2 principle that effective dimensions are
    slowly updated, but not immutable: an open complex system may need
    shadow expansion axes when residuals grow, instability appears, or
    information/coordination targets remain under-explained.

Boundary:
    - validation only
    - component-count sweep only
    - no effective dimension adoption or freeze
    - no dynamics-axis extraction
    - no action-weight conversion
    - no upper-pressure connection
    - no ActionFrame / ActionModule / FullSpec runtime / canonical write
    - no v2_hidden_trace as feature input
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .pressure_action_task2_8j_1_candidate_feature_log import (
    CandidateFeatureLogConfig,
    build_candidate_feature_log,
    validate_candidate_feature_log,
)
from .pressure_action_task2_8j_2_temporal_pca_validation import (
    PCA_MODES,
    TemporalPCAValidationConfig,
    build_model_summary_table,
    build_pca_component_table,
    build_prediction_table,
    build_stability_table,
    fit_pca_validation_models,
    validate_temporal_pca_validation_tables,
)
from .pressure_action_task2_8j_3_effective_dimension_evaluation import (
    EffectiveDimensionEvaluationConfig,
    build_component_count_table,
    build_effective_dimension_evaluation_table,
    build_feature_overlap_table,
)


TASK2_8J_3B_VERSION = "effective_dimension_component_count_sweep_rc1"
TASK2_8J_3B_CONTRACT = (
    "Task2_8j_3b_effective_dimension_component_count_sweep__"
    "3_to_8_axis_static_focus__shadow_expansion_only__no_adoption_no_freeze"
)

BOUNDARY_COLUMNS = [
    "task2_8j_3b_version",
    "task2_8j_3b_contract",
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

REQUIRED_SWEEP_COLUMNS = BOUNDARY_COLUMNS + [
    "mode",
    "requested_component_count",
    "actual_component_count",
    "component_count_role",
    "component_count_reason",
    "total_explained_variance_ratio",
    "reconstruction_error_ratio",
    "marginal_component_gain",
    "mean_prediction_r2",
    "information_quality_prediction_r2",
    "coordination_lag_prediction_r2",
    "mean_stability_similarity",
    "mean_projection_drift",
    "usefulness_score",
    "information_retention_score",
    "prediction_usefulness_score",
    "stability_score",
    "nonredundancy_score",
    "usability_score",
    "overall_evaluation_score",
    "candidate_status",
    "candidate_reason",
]

REQUIRED_TARGET_COLUMNS = BOUNDARY_COLUMNS + [
    "mode",
    "requested_component_count",
    "target_feature_key",
    "target_short_name",
    "prediction_horizon",
    "train_rows",
    "test_rows",
    "rmse",
    "baseline_rmse",
    "r2_vs_mean_baseline",
    "r2_delta_from_static_6",
    "prediction_status",
]

REQUIRED_STATIC_COMPONENT_COLUMNS = BOUNDARY_COLUMNS + [
    "requested_component_count",
    "component_index",
    "component_role",
    "n_samples",
    "n_features",
    "active_feature_count",
    "explained_variance_ratio",
    "cumulative_explained_variance_ratio",
    "reconstruction_error_ratio",
    "top_feature_keys",
    "top_feature_weights",
]

REQUIRED_FINAL_SUMMARY_COLUMNS = BOUNDARY_COLUMNS + [
    "standard_component_count",
    "standard_static_overall_score",
    "standard_static_information_retention_score",
    "standard_static_stability_score",
    "standard_static_mean_prediction_r2",
    "best_static_component_count_by_overall",
    "best_static_overall_score",
    "best_static_component_count_by_information_quality",
    "best_static_information_quality_r2",
    "best_static_component_count_by_coordination_lag",
    "best_static_coordination_lag_r2",
    "seven_axis_tested",
    "eight_axis_tested",
    "expansion_improves_overall",
    "expansion_watch_component_counts",
    "sweep_status",
    "recommendation",
    "adoption_performed",
    "freeze_performed",
    "next_task",
]


@dataclass(frozen=True)
class ComponentCountSweepConfig:
    component_counts: tuple[int, ...] = (3, 4, 5, 6, 7, 8)
    standard_component_count: int = 6
    sparse_top_k: int = 12
    prediction_horizon: int = 3
    min_prediction_rows: int = 8
    meaningful_gain_threshold: float = 0.01


def _boundary_payload() -> dict:
    return {
        "task2_8j_3b_version": TASK2_8J_3B_VERSION,
        "task2_8j_3b_contract": TASK2_8J_3B_CONTRACT,
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


def _safe_mean(series: pd.Series, default: float = 0.0) -> float:
    if series is None or len(series) == 0:
        return float(default)
    values = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if values.empty:
        return float(default)
    return float(values.mean())


def _target_short_name(key: object) -> str:
    parts = str(key).split("::")
    if len(parts) >= 3:
        return parts[2]
    return parts[-1] if parts else ""


def _target_r2(prediction_rows: pd.DataFrame, token: str) -> float:
    if prediction_rows is None or prediction_rows.empty:
        return float("nan")
    rows = prediction_rows[prediction_rows["target_feature_key"].astype(str).str.contains(token, regex=False)]
    if rows.empty:
        return float("nan")
    return _safe_mean(rows["r2_vs_mean_baseline"], default=float("nan"))


def _component_count_role(count: int, standard_count: int) -> tuple[str, str]:
    if int(count) < int(standard_count):
        return "compression_reference", "below_current_standard_count"
    if int(count) == int(standard_count):
        return "standard_candidate", "current_6_axis_standard_candidate"
    return "expansion_watch", "future_open_complex_system_expansion_probe"


def _marginal_gain(component_table: pd.DataFrame, mode: str, actual_count: int) -> float:
    if component_table is None or component_table.empty:
        return 0.0
    rows = component_table[
        (component_table["mode"].astype(str) == str(mode))
        & (component_table["component_index"].astype(int) == int(actual_count))
    ]
    if rows.empty:
        return 0.0
    return _safe_float(rows["explained_variance_ratio"].iloc[0], default=0.0)


def build_component_count_sweep_tables(
    feature_cfg: CandidateFeatureLogConfig | None = None,
    sweep_cfg: ComponentCountSweepConfig | None = None,
    eval_cfg: EffectiveDimensionEvaluationConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    feature_cfg = feature_cfg or CandidateFeatureLogConfig(steps=24, seeds=(501, 502, 503), window_sizes=(1, 6, 12))
    sweep_cfg = sweep_cfg or ComponentCountSweepConfig()
    eval_cfg = eval_cfg or EffectiveDimensionEvaluationConfig()

    feature_log = build_candidate_feature_log(feature_cfg)
    feature_errors = validate_candidate_feature_log(feature_log)

    sweep_rows: list[dict] = []
    target_rows: list[dict] = []
    static_component_rows: list[dict] = []
    errors: list[str] = []

    if feature_errors:
        errors.extend(f"task2_8j_3b_feature_log_error:{e}" for e in feature_errors)

    for requested_count in sweep_cfg.component_counts:
        pca_cfg = TemporalPCAValidationConfig(
            n_components=int(requested_count),
            sparse_top_k=int(sweep_cfg.sparse_top_k),
            prediction_horizon=int(sweep_cfg.prediction_horizon),
            min_prediction_rows=int(sweep_cfg.min_prediction_rows),
        )
        models = fit_pca_validation_models(feature_log, pca_cfg)
        component_table = build_pca_component_table(models)
        model_summary = build_model_summary_table(models, pca_cfg)
        stability_table = build_stability_table(models, pca_cfg)
        prediction_table = build_prediction_table(models, pca_cfg)

        upstream_errors = validate_temporal_pca_validation_tables(
            component_table,
            model_summary,
            stability_table,
            prediction_table,
            feature_errors,
        )
        if upstream_errors:
            errors.extend(f"task2_8j_3b_upstream_error:n{requested_count}:{e}" for e in upstream_errors)

        overlap_table = build_feature_overlap_table(component_table)
        _component_count_table = build_component_count_table(component_table, eval_cfg)
        evaluation_table = build_effective_dimension_evaluation_table(
            model_summary,
            stability_table,
            prediction_table,
            component_table,
            overlap_table,
            eval_cfg,
        )

        for _, eval_row in evaluation_table.iterrows():
            mode = str(eval_row["mode"])
            model_rows = model_summary[model_summary["mode"].astype(str) == mode]
            model_row = model_rows.iloc[0] if not model_rows.empty else pd.Series(dtype=object)
            actual_count = int(model_row.get("n_components", requested_count))
            role, reason = _component_count_role(int(requested_count), sweep_cfg.standard_component_count)
            pred_rows = prediction_table[prediction_table["mode"].astype(str) == mode] if prediction_table is not None and not prediction_table.empty else pd.DataFrame()
            stability_rows = stability_table[stability_table["mode"].astype(str) == mode] if stability_table is not None and not stability_table.empty else pd.DataFrame()
            sweep_rows.append(
                {
                    **_boundary_payload(),
                    "mode": mode,
                    "requested_component_count": int(requested_count),
                    "actual_component_count": actual_count,
                    "component_count_role": role,
                    "component_count_reason": reason,
                    "total_explained_variance_ratio": _safe_float(model_row.get("total_explained_variance_ratio", 0.0), default=0.0),
                    "reconstruction_error_ratio": _safe_float(model_row.get("reconstruction_error_ratio", 1.0), default=1.0),
                    "marginal_component_gain": _marginal_gain(component_table, mode, actual_count),
                    "mean_prediction_r2": _safe_mean(pred_rows["r2_vs_mean_baseline"], default=0.0) if not pred_rows.empty else 0.0,
                    "information_quality_prediction_r2": _target_r2(pred_rows, "information_quality_mean"),
                    "coordination_lag_prediction_r2": _target_r2(pred_rows, "coordination_lag_mean"),
                    "mean_stability_similarity": _safe_mean(stability_rows["subspace_similarity"], default=0.0) if not stability_rows.empty else 0.0,
                    "mean_projection_drift": _safe_mean(stability_rows["projection_drift"], default=1.0) if not stability_rows.empty else 1.0,
                    "usefulness_score": _safe_float(eval_row.get("usefulness_score", 0.0)),
                    "information_retention_score": _safe_float(eval_row.get("information_retention_score", 0.0)),
                    "prediction_usefulness_score": _safe_float(eval_row.get("prediction_usefulness_score", 0.0)),
                    "stability_score": _safe_float(eval_row.get("stability_score", 0.0)),
                    "nonredundancy_score": _safe_float(eval_row.get("nonredundancy_score", 0.0)),
                    "usability_score": _safe_float(eval_row.get("usability_score", 0.0)),
                    "overall_evaluation_score": _safe_float(eval_row.get("overall_evaluation_score", 0.0)),
                    "candidate_status": str(eval_row.get("candidate_status", "unknown")),
                    "candidate_reason": str(eval_row.get("candidate_reason", "")),
                }
            )

        if prediction_table is not None and not prediction_table.empty:
            for _, row in prediction_table.iterrows():
                target_rows.append(
                    {
                        **_boundary_payload(),
                        "mode": str(row["mode"]),
                        "requested_component_count": int(requested_count),
                        "target_feature_key": str(row["target_feature_key"]),
                        "target_short_name": _target_short_name(row["target_feature_key"]),
                        "prediction_horizon": int(row["prediction_horizon"]),
                        "train_rows": int(row["train_rows"]),
                        "test_rows": int(row["test_rows"]),
                        "rmse": _safe_float(row["rmse"]),
                        "baseline_rmse": _safe_float(row["baseline_rmse"]),
                        "r2_vs_mean_baseline": _safe_float(row["r2_vs_mean_baseline"]),
                        "r2_delta_from_static_6": float("nan"),
                        "prediction_status": str(row["prediction_status"]),
                    }
                )

        static_components = component_table[component_table["mode"].astype(str) == "static_pca"] if component_table is not None and not component_table.empty else pd.DataFrame()
        for _, row in static_components.iterrows():
            component_index = int(row["component_index"])
            static_component_rows.append(
                {
                    **_boundary_payload(),
                    "requested_component_count": int(requested_count),
                    "component_index": component_index,
                    "component_role": "standard_or_lower_component" if component_index <= sweep_cfg.standard_component_count else "expansion_component",
                    "n_samples": int(row["n_samples"]),
                    "n_features": int(row["n_features"]),
                    "active_feature_count": int(row["active_feature_count"]),
                    "explained_variance_ratio": _safe_float(row["explained_variance_ratio"]),
                    "cumulative_explained_variance_ratio": _safe_float(row["cumulative_explained_variance_ratio"]),
                    "reconstruction_error_ratio": _safe_float(row["reconstruction_error_ratio"]),
                    "top_feature_keys": str(row["top_feature_keys"]),
                    "top_feature_weights": str(row["top_feature_weights"]),
                }
            )

    sweep_table = pd.DataFrame(sweep_rows, columns=REQUIRED_SWEEP_COLUMNS)
    target_prediction_table = pd.DataFrame(target_rows, columns=REQUIRED_TARGET_COLUMNS)
    static_component_table = pd.DataFrame(static_component_rows, columns=REQUIRED_STATIC_COMPONENT_COLUMNS)

    if not target_prediction_table.empty:
        baseline_rows = target_prediction_table[
            (target_prediction_table["mode"].astype(str) == "static_pca")
            & (target_prediction_table["requested_component_count"].astype(int) == int(sweep_cfg.standard_component_count))
        ]
        baseline_by_target = {
            str(row["target_feature_key"]): _safe_float(row["r2_vs_mean_baseline"])
            for _, row in baseline_rows.iterrows()
        }
        deltas = []
        for _, row in target_prediction_table.iterrows():
            base = baseline_by_target.get(str(row["target_feature_key"]), float("nan"))
            current = _safe_float(row["r2_vs_mean_baseline"])
            deltas.append(current - base if np.isfinite(base) else float("nan"))
        target_prediction_table["r2_delta_from_static_6"] = deltas

    final_summary = build_component_count_sweep_final_summary(sweep_table, target_prediction_table, sweep_cfg)
    errors.extend(validate_component_count_sweep_tables(sweep_table, target_prediction_table, static_component_table, final_summary, sweep_cfg))
    summary = summarize_component_count_sweep(sweep_table, target_prediction_table, static_component_table, final_summary)
    summary["validation_errors"] = errors
    return sweep_table, target_prediction_table, static_component_table, final_summary, errors, summary


def _best_count_for_static_metric(static_rows: pd.DataFrame, metric: str, default_count: int) -> tuple[int, float]:
    if static_rows is None or static_rows.empty or metric not in static_rows.columns:
        return int(default_count), 0.0
    rows = static_rows.copy()
    rows[metric] = pd.to_numeric(rows[metric], errors="coerce")
    rows = rows.replace([np.inf, -np.inf], np.nan).dropna(subset=[metric])
    if rows.empty:
        return int(default_count), 0.0
    best = rows.sort_values(metric, ascending=False).iloc[0]
    return int(best["requested_component_count"]), _safe_float(best[metric])


def build_component_count_sweep_final_summary(
    sweep_table: pd.DataFrame,
    target_prediction_table: pd.DataFrame,
    cfg: ComponentCountSweepConfig | None = None,
) -> pd.DataFrame:
    cfg = cfg or ComponentCountSweepConfig()
    boundary = _boundary_payload()
    if sweep_table is None or sweep_table.empty:
        row = {
            **boundary,
            "standard_component_count": int(cfg.standard_component_count),
            "standard_static_overall_score": 0.0,
            "standard_static_information_retention_score": 0.0,
            "standard_static_stability_score": 0.0,
            "standard_static_mean_prediction_r2": 0.0,
            "best_static_component_count_by_overall": int(cfg.standard_component_count),
            "best_static_overall_score": 0.0,
            "best_static_component_count_by_information_quality": int(cfg.standard_component_count),
            "best_static_information_quality_r2": 0.0,
            "best_static_component_count_by_coordination_lag": int(cfg.standard_component_count),
            "best_static_coordination_lag_r2": 0.0,
            "seven_axis_tested": False,
            "eight_axis_tested": False,
            "expansion_improves_overall": False,
            "expansion_watch_component_counts": "",
            "sweep_status": "empty",
            "recommendation": "rerun_component_count_sweep",
            "adoption_performed": False,
            "freeze_performed": False,
            "next_task": "Task 2-8j-4: v2 game-structure re-identification test",
        }
        return pd.DataFrame([row], columns=REQUIRED_FINAL_SUMMARY_COLUMNS)

    static_rows = sweep_table[sweep_table["mode"].astype(str) == "static_pca"].copy()
    standard_rows = static_rows[static_rows["requested_component_count"].astype(int) == int(cfg.standard_component_count)]
    standard = standard_rows.iloc[0] if not standard_rows.empty else pd.Series(dtype=object)
    best_overall_count, best_overall = _best_count_for_static_metric(static_rows, "overall_evaluation_score", cfg.standard_component_count)
    best_info_count, best_info = _best_count_for_static_metric(static_rows, "information_quality_prediction_r2", cfg.standard_component_count)
    best_coord_count, best_coord = _best_count_for_static_metric(static_rows, "coordination_lag_prediction_r2", cfg.standard_component_count)
    standard_overall = _safe_float(standard.get("overall_evaluation_score", 0.0), default=0.0)
    expansion_rows = static_rows[static_rows["requested_component_count"].astype(int) > int(cfg.standard_component_count)]
    expansion_counts = sorted(expansion_rows["requested_component_count"].astype(int).unique().tolist()) if not expansion_rows.empty else []
    expansion_best = float(expansion_rows["overall_evaluation_score"].astype(float).max()) if not expansion_rows.empty else 0.0
    expansion_improves = bool(expansion_best > standard_overall + float(cfg.meaningful_gain_threshold))

    recommendation = "keep_6_axis_standard_with_7_8_shadow_expansion_watch"
    if expansion_improves:
        recommendation = "keep_no_adoption_but_prioritize_expansion_reidentification_check"
    elif best_info_count > cfg.standard_component_count or best_coord_count > cfg.standard_component_count:
        recommendation = "keep_6_axis_standard_but_track_information_or_coordination_expansion_axis"

    row = {
        **boundary,
        "standard_component_count": int(cfg.standard_component_count),
        "standard_static_overall_score": standard_overall,
        "standard_static_information_retention_score": _safe_float(standard.get("information_retention_score", 0.0), default=0.0),
        "standard_static_stability_score": _safe_float(standard.get("stability_score", 0.0), default=0.0),
        "standard_static_mean_prediction_r2": _safe_float(standard.get("mean_prediction_r2", 0.0), default=0.0),
        "best_static_component_count_by_overall": int(best_overall_count),
        "best_static_overall_score": float(best_overall),
        "best_static_component_count_by_information_quality": int(best_info_count),
        "best_static_information_quality_r2": float(best_info),
        "best_static_component_count_by_coordination_lag": int(best_coord_count),
        "best_static_coordination_lag_r2": float(best_coord),
        "seven_axis_tested": bool(7 in set(static_rows["requested_component_count"].astype(int).tolist())),
        "eight_axis_tested": bool(8 in set(static_rows["requested_component_count"].astype(int).tolist())),
        "expansion_improves_overall": expansion_improves,
        "expansion_watch_component_counts": ";".join(str(x) for x in expansion_counts),
        "sweep_status": "pass",
        "recommendation": recommendation,
        "adoption_performed": False,
        "freeze_performed": False,
        "next_task": "Task 2-8j-4: v2 game-structure re-identification test with 6-axis standard and 7/8-axis shadow comparison",
    }
    return pd.DataFrame([row], columns=REQUIRED_FINAL_SUMMARY_COLUMNS)


def validate_component_count_sweep_tables(
    sweep_table: pd.DataFrame,
    target_prediction_table: pd.DataFrame,
    static_component_table: pd.DataFrame,
    final_summary: pd.DataFrame,
    cfg: ComponentCountSweepConfig | None = None,
) -> list[str]:
    cfg = cfg or ComponentCountSweepConfig()
    errors: list[str] = []
    tables = {
        "sweep": (sweep_table, REQUIRED_SWEEP_COLUMNS),
        "target_prediction": (target_prediction_table, REQUIRED_TARGET_COLUMNS),
        "static_component": (static_component_table, REQUIRED_STATIC_COMPONENT_COLUMNS),
        "final_summary": (final_summary, REQUIRED_FINAL_SUMMARY_COLUMNS),
    }
    for name, (table, required) in tables.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_3b_empty_table:{name}")
            continue
        missing = [c for c in required if c not in table.columns]
        if missing:
            errors.append(f"task2_8j_3b_missing_columns:{name}:" + ",".join(missing))
            continue
        if not bool(table["validation_only"].astype(bool).all()):
            errors.append(f"task2_8j_3b_validation_only_not_all_true:{name}")
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
                errors.append(f"task2_8j_3b_forbidden_true:{name}:{col}")

    if sweep_table is not None and not sweep_table.empty:
        static_counts = set(
            sweep_table[sweep_table["mode"].astype(str) == "static_pca"]["requested_component_count"].astype(int).tolist()
        )
        missing_counts = sorted(set(int(x) for x in cfg.component_counts) - static_counts)
        if missing_counts:
            errors.append("task2_8j_3b_missing_static_component_counts:" + ",".join(str(x) for x in missing_counts))
        if 8 not in static_counts:
            errors.append("task2_8j_3b_eight_axis_not_tested")
        modes = set(sweep_table["mode"].astype(str).unique())
        missing_modes = sorted(set(PCA_MODES) - modes)
        if missing_modes:
            errors.append("task2_8j_3b_missing_modes:" + ",".join(missing_modes))
        for col in [
            "usefulness_score",
            "information_retention_score",
            "prediction_usefulness_score",
            "stability_score",
            "nonredundancy_score",
            "usability_score",
            "overall_evaluation_score",
        ]:
            if not bool(sweep_table[col].astype(float).between(0.0, 1.0).all()):
                errors.append(f"task2_8j_3b_score_out_of_range:{col}")

    if final_summary is not None and not final_summary.empty:
        if bool(final_summary["adoption_performed"].astype(bool).any()):
            errors.append("task2_8j_3b_adoption_performed_true")
        if bool(final_summary["freeze_performed"].astype(bool).any()):
            errors.append("task2_8j_3b_freeze_performed_true")
        if not bool(final_summary["seven_axis_tested"].astype(bool).all()):
            errors.append("task2_8j_3b_seven_axis_not_tested")
        if not bool(final_summary["eight_axis_tested"].astype(bool).all()):
            errors.append("task2_8j_3b_eight_axis_not_tested_in_summary")
    return errors


def summarize_component_count_sweep(
    sweep_table: pd.DataFrame,
    target_prediction_table: pd.DataFrame,
    static_component_table: pd.DataFrame,
    final_summary: pd.DataFrame,
) -> dict:
    if sweep_table is None or sweep_table.empty:
        return {"rows": 0, "best_static_component_count": 0}
    static_rows = sweep_table[sweep_table["mode"].astype(str) == "static_pca"].copy()
    best_static = static_rows.sort_values("overall_evaluation_score", ascending=False).iloc[0] if not static_rows.empty else pd.Series(dtype=object)
    summary_row = final_summary.iloc[0] if final_summary is not None and not final_summary.empty else pd.Series(dtype=object)
    return {
        "rows": int(len(sweep_table)),
        "target_prediction_rows": int(len(target_prediction_table)) if target_prediction_table is not None else 0,
        "static_component_rows": int(len(static_component_table)) if static_component_table is not None else 0,
        "final_summary_rows": int(len(final_summary)) if final_summary is not None else 0,
        "modes": sorted(sweep_table["mode"].astype(str).unique().tolist()),
        "component_counts": sorted(sweep_table["requested_component_count"].astype(int).unique().tolist()),
        "best_static_component_count": int(best_static.get("requested_component_count", 0)),
        "best_static_overall_score": _safe_float(best_static.get("overall_evaluation_score", 0.0), default=0.0),
        "standard_component_count": int(summary_row.get("standard_component_count", 6)),
        "seven_axis_tested": bool(summary_row.get("seven_axis_tested", False)),
        "eight_axis_tested": bool(summary_row.get("eight_axis_tested", False)),
        "expansion_improves_overall": bool(summary_row.get("expansion_improves_overall", False)),
        "recommendation": str(summary_row.get("recommendation", "")),
        "adoption_performed": False,
        "freeze_performed": False,
    }


def build_and_validate_component_count_sweep(
    feature_cfg: CandidateFeatureLogConfig | None = None,
    sweep_cfg: ComponentCountSweepConfig | None = None,
    eval_cfg: EffectiveDimensionEvaluationConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    return build_component_count_sweep_tables(feature_cfg, sweep_cfg, eval_cfg)
