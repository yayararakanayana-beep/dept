"""Task 2-8j-3: effective-dimension usefulness / stability / non-redundancy evaluation RC1.

Purpose:
    Evaluate the Task 2-8j-2 PCA-like candidates across three practical axes:
      - usefulness as an effective-dimension candidate
      - temporal stability
      - non-redundancy / usability

    This task produces evaluation tables and candidate-status labels only.  It
    does not adopt, freeze, or connect any effective dimension.

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

import numpy as np
import pandas as pd

from .pressure_action_task2_8j_1_candidate_feature_log import CandidateFeatureLogConfig
from .pressure_action_task2_8j_2_temporal_pca_validation import (
    PCA_MODES,
    TemporalPCAValidationConfig,
    build_and_validate_temporal_pca_validation,
)


TASK2_8J_3_VERSION = "effective_dimension_evaluation_rc1"
TASK2_8J_3_CONTRACT = (
    "Task2_8j_3_effective_dimension_usefulness_stability_nonredundancy_evaluation__"
    "candidate_status_only__no_adoption_no_freeze_no_dynamics_axis"
)

BOUNDARY_COLUMNS = [
    "task2_8j_3_version",
    "task2_8j_3_contract",
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

REQUIRED_EVALUATION_COLUMNS = BOUNDARY_COLUMNS + [
    "mode",
    "usefulness_score",
    "information_retention_score",
    "prediction_usefulness_score",
    "stability_score",
    "nonredundancy_score",
    "usability_score",
    "overall_evaluation_score",
    "total_explained_variance_ratio",
    "reconstruction_error_ratio",
    "mean_prediction_r2",
    "mean_stability_similarity",
    "mean_projection_drift",
    "effective_rank",
    "matrix_rank",
    "n_components",
    "n_features",
    "mean_abs_component_correlation",
    "mean_component_feature_overlap",
    "mean_active_feature_count",
    "candidate_status",
    "candidate_reason",
]

REQUIRED_COMPONENT_COUNT_COLUMNS = BOUNDARY_COLUMNS + [
    "mode",
    "component_count",
    "cumulative_explained_variance_ratio",
    "marginal_explained_variance_ratio",
    "diminishing_return_flag",
    "candidate_component_count",
    "component_count_reason",
]

REQUIRED_FEATURE_OVERLAP_COLUMNS = BOUNDARY_COLUMNS + [
    "mode",
    "component_i",
    "component_j",
    "top_feature_overlap_jaccard",
    "overlap_feature_count",
    "component_pair_status",
]

REQUIRED_FINAL_SUMMARY_COLUMNS = BOUNDARY_COLUMNS + [
    "best_mode_by_overall_score",
    "best_mode_candidate_status",
    "best_mode_overall_score",
    "best_mode_stability_score",
    "best_mode_nonredundancy_score",
    "best_mode_usefulness_score",
    "adoption_performed",
    "freeze_performed",
    "next_task",
]


@dataclass(frozen=True)
class EffectiveDimensionEvaluationConfig:
    high_score_threshold: float = 0.68
    watch_score_threshold: float = 0.52
    stability_watch_threshold: float = 0.45
    nonredundancy_watch_threshold: float = 0.45
    diminishing_return_threshold: float = 0.035
    component_target_explained: float = 0.80


def _boundary_payload() -> dict:
    return {
        "task2_8j_3_version": TASK2_8J_3_VERSION,
        "task2_8j_3_contract": TASK2_8J_3_CONTRACT,
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


def _clip01(x: float) -> float:
    try:
        y = float(x)
    except (TypeError, ValueError):
        return 0.0
    if not np.isfinite(y):
        return 0.0
    return float(max(0.0, min(1.0, y)))


def _safe_mean(series: pd.Series, default: float = 0.0) -> float:
    if series is None or len(series) == 0:
        return float(default)
    values = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if values.empty:
        return float(default)
    return float(values.mean())


def _parse_feature_set(value: object) -> set[str]:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return set()
    text = str(value)
    if not text:
        return set()
    return {x.strip() for x in text.split(";") if x.strip()}


def build_feature_overlap_table(component_table: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    if component_table is None or component_table.empty:
        return pd.DataFrame(columns=REQUIRED_FEATURE_OVERLAP_COLUMNS)
    for mode, group in component_table.groupby("mode"):
        group = group.sort_values("component_index")
        records = list(group.to_dict("records"))
        for i in range(len(records)):
            for j in range(i + 1, len(records)):
                fi = _parse_feature_set(records[i].get("top_feature_keys"))
                fj = _parse_feature_set(records[j].get("top_feature_keys"))
                union = fi | fj
                inter = fi & fj
                jaccard = float(len(inter) / max(len(union), 1))
                rows.append(
                    {
                        **_boundary_payload(),
                        "mode": str(mode),
                        "component_i": int(records[i].get("component_index", i + 1)),
                        "component_j": int(records[j].get("component_index", j + 1)),
                        "top_feature_overlap_jaccard": jaccard,
                        "overlap_feature_count": int(len(inter)),
                        "component_pair_status": "watch" if jaccard >= 0.45 else "pass",
                    }
                )
    return pd.DataFrame(rows, columns=REQUIRED_FEATURE_OVERLAP_COLUMNS)


def build_component_count_table(
    component_table: pd.DataFrame,
    cfg: EffectiveDimensionEvaluationConfig | None = None,
) -> pd.DataFrame:
    cfg = cfg or EffectiveDimensionEvaluationConfig()
    rows: list[dict] = []
    if component_table is None or component_table.empty:
        return pd.DataFrame(columns=REQUIRED_COMPONENT_COUNT_COLUMNS)
    for mode, group in component_table.groupby("mode"):
        group = group.sort_values("component_index")
        candidate_count = int(group["component_index"].astype(int).max())
        candidate_reason = "max_available_components"
        for _, row in group.iterrows():
            comp_count = int(row["component_index"])
            cumulative = float(row["cumulative_explained_variance_ratio"])
            marginal = float(row["explained_variance_ratio"])
            if cumulative >= cfg.component_target_explained and candidate_reason == "max_available_components":
                candidate_count = comp_count
                candidate_reason = "target_cumulative_explained_reached"
            elif marginal < cfg.diminishing_return_threshold and candidate_reason == "max_available_components":
                candidate_count = max(1, comp_count - 1)
                candidate_reason = "marginal_gain_diminished"
            rows.append(
                {
                    **_boundary_payload(),
                    "mode": str(mode),
                    "component_count": comp_count,
                    "cumulative_explained_variance_ratio": cumulative,
                    "marginal_explained_variance_ratio": marginal,
                    "diminishing_return_flag": bool(marginal < cfg.diminishing_return_threshold),
                    "candidate_component_count": int(candidate_count),
                    "component_count_reason": candidate_reason,
                }
            )
    return pd.DataFrame(rows, columns=REQUIRED_COMPONENT_COUNT_COLUMNS)


def _score_mode(
    mode: str,
    model_row: pd.Series,
    stability_rows: pd.DataFrame,
    prediction_rows: pd.DataFrame,
    overlap_rows: pd.DataFrame,
    component_rows: pd.DataFrame,
    cfg: EffectiveDimensionEvaluationConfig,
) -> dict:
    total_explained = _clip01(model_row.get("total_explained_variance_ratio", 0.0))
    reconstruction_error = max(0.0, float(model_row.get("reconstruction_error_ratio", 1.0)))
    reconstruction_quality = _clip01(1.0 - reconstruction_error)
    prediction_r2 = _safe_mean(prediction_rows["r2_vs_mean_baseline"], default=0.0) if prediction_rows is not None and not prediction_rows.empty else 0.0
    # Negative prediction scores are not fatal at this stage; they just do not add usefulness.
    prediction_score = _clip01((prediction_r2 + 0.25) / 1.25)
    information_retention = _clip01(0.65 * total_explained + 0.35 * reconstruction_quality)
    usefulness = _clip01(0.60 * information_retention + 0.40 * prediction_score)

    stability_similarity = _safe_mean(stability_rows["subspace_similarity"], default=0.0) if stability_rows is not None and not stability_rows.empty else 0.0
    projection_drift = _safe_mean(stability_rows["projection_drift"], default=1.0) if stability_rows is not None and not stability_rows.empty else 1.0
    stability_score = _clip01(0.75 * stability_similarity + 0.25 * (1.0 / (1.0 + projection_drift)))

    mean_component_corr = abs(float(model_row.get("mean_abs_component_correlation", 0.0)))
    effective_rank = float(model_row.get("effective_rank", 0.0))
    n_components = max(1, int(model_row.get("n_components", 1)))
    rank_score = _clip01(effective_rank / n_components)
    mean_overlap = _safe_mean(overlap_rows["top_feature_overlap_jaccard"], default=0.0) if overlap_rows is not None and not overlap_rows.empty else 0.0
    nonredundancy = _clip01(0.45 * (1.0 - mean_component_corr) + 0.35 * rank_score + 0.20 * (1.0 - mean_overlap))

    n_features = max(1, int(model_row.get("n_features", 1)))
    active_mean = _safe_mean(component_rows["active_feature_count"], default=float(n_features)) if component_rows is not None and not component_rows.empty else float(n_features)
    sparsity_score = _clip01(1.0 - (active_mean / n_features))
    readability_bonus = 0.20 if mode == "sparse_temporal_pca" else 0.0
    usability = _clip01(0.45 * usefulness + 0.30 * nonredundancy + 0.25 * sparsity_score + readability_bonus)

    overall = _clip01(0.38 * usefulness + 0.27 * stability_score + 0.23 * nonredundancy + 0.12 * usability)
    if overall >= cfg.high_score_threshold and stability_score >= cfg.stability_watch_threshold and nonredundancy >= cfg.nonredundancy_watch_threshold:
        status = "candidate_strong"
    elif overall >= cfg.watch_score_threshold:
        status = "candidate_watch"
    else:
        status = "candidate_weak"
    reasons = []
    if usefulness < cfg.watch_score_threshold:
        reasons.append("low_usefulness")
    if stability_score < cfg.stability_watch_threshold:
        reasons.append("low_stability")
    if nonredundancy < cfg.nonredundancy_watch_threshold:
        reasons.append("low_nonredundancy")
    if not reasons:
        reasons.append("balanced_candidate_metrics")

    return {
        **_boundary_payload(),
        "mode": mode,
        "usefulness_score": usefulness,
        "information_retention_score": information_retention,
        "prediction_usefulness_score": prediction_score,
        "stability_score": stability_score,
        "nonredundancy_score": nonredundancy,
        "usability_score": usability,
        "overall_evaluation_score": overall,
        "total_explained_variance_ratio": total_explained,
        "reconstruction_error_ratio": reconstruction_error,
        "mean_prediction_r2": float(prediction_r2),
        "mean_stability_similarity": float(stability_similarity),
        "mean_projection_drift": float(projection_drift),
        "effective_rank": effective_rank,
        "matrix_rank": int(model_row.get("matrix_rank", 0)),
        "n_components": n_components,
        "n_features": n_features,
        "mean_abs_component_correlation": mean_component_corr,
        "mean_component_feature_overlap": float(mean_overlap),
        "mean_active_feature_count": float(active_mean),
        "candidate_status": status,
        "candidate_reason": ";".join(reasons),
    }


def build_effective_dimension_evaluation_table(
    model_summary: pd.DataFrame,
    stability_table: pd.DataFrame,
    prediction_table: pd.DataFrame,
    component_table: pd.DataFrame,
    overlap_table: pd.DataFrame,
    cfg: EffectiveDimensionEvaluationConfig | None = None,
) -> pd.DataFrame:
    cfg = cfg or EffectiveDimensionEvaluationConfig()
    rows: list[dict] = []
    if model_summary is None or model_summary.empty:
        return pd.DataFrame(columns=REQUIRED_EVALUATION_COLUMNS)
    for _, model_row in model_summary.iterrows():
        mode = str(model_row["mode"])
        rows.append(
            _score_mode(
                mode,
                model_row,
                stability_table[stability_table["mode"].astype(str) == mode] if stability_table is not None and not stability_table.empty else pd.DataFrame(),
                prediction_table[prediction_table["mode"].astype(str) == mode] if prediction_table is not None and not prediction_table.empty else pd.DataFrame(),
                overlap_table[overlap_table["mode"].astype(str) == mode] if overlap_table is not None and not overlap_table.empty else pd.DataFrame(),
                component_table[component_table["mode"].astype(str) == mode] if component_table is not None and not component_table.empty else pd.DataFrame(),
                cfg,
            )
        )
    out = pd.DataFrame(rows, columns=REQUIRED_EVALUATION_COLUMNS)
    if not out.empty:
        out = out.sort_values("overall_evaluation_score", ascending=False, ignore_index=True)
    return out


def build_final_summary_table(evaluation_table: pd.DataFrame) -> pd.DataFrame:
    if evaluation_table is None or evaluation_table.empty:
        row = {
            **_boundary_payload(),
            "best_mode_by_overall_score": "none",
            "best_mode_candidate_status": "none",
            "best_mode_overall_score": 0.0,
            "best_mode_stability_score": 0.0,
            "best_mode_nonredundancy_score": 0.0,
            "best_mode_usefulness_score": 0.0,
            "adoption_performed": False,
            "freeze_performed": False,
            "next_task": "Task 2-8j-4",
        }
    else:
        best = evaluation_table.sort_values("overall_evaluation_score", ascending=False).iloc[0]
        row = {
            **_boundary_payload(),
            "best_mode_by_overall_score": str(best["mode"]),
            "best_mode_candidate_status": str(best["candidate_status"]),
            "best_mode_overall_score": float(best["overall_evaluation_score"]),
            "best_mode_stability_score": float(best["stability_score"]),
            "best_mode_nonredundancy_score": float(best["nonredundancy_score"]),
            "best_mode_usefulness_score": float(best["usefulness_score"]),
            "adoption_performed": False,
            "freeze_performed": False,
            "next_task": "Task 2-8j-4: v2 game-structure re-identification test",
        }
    return pd.DataFrame([row], columns=REQUIRED_FINAL_SUMMARY_COLUMNS)


def validate_effective_dimension_evaluation_tables(
    evaluation_table: pd.DataFrame,
    component_count_table: pd.DataFrame,
    overlap_table: pd.DataFrame,
    final_summary: pd.DataFrame,
    upstream_errors: list[str] | None = None,
) -> list[str]:
    errors: list[str] = []
    if upstream_errors:
        errors.extend(f"task2_8j_3_upstream_error:{e}" for e in upstream_errors)
    tables = {
        "evaluation": (evaluation_table, REQUIRED_EVALUATION_COLUMNS),
        "component_count": (component_count_table, REQUIRED_COMPONENT_COUNT_COLUMNS),
        "feature_overlap": (overlap_table, REQUIRED_FEATURE_OVERLAP_COLUMNS),
        "final_summary": (final_summary, REQUIRED_FINAL_SUMMARY_COLUMNS),
    }
    for name, (table, required) in tables.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_3_empty_table:{name}")
            continue
        missing = [c for c in required if c not in table.columns]
        if missing:
            errors.append(f"task2_8j_3_missing_columns:{name}:" + ",".join(missing))
            continue
        if not bool(table["validation_only"].astype(bool).all()):
            errors.append(f"task2_8j_3_validation_only_not_all_true:{name}")
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
                errors.append(f"task2_8j_3_forbidden_true:{name}:{col}")
    if evaluation_table is not None and not evaluation_table.empty:
        modes = set(evaluation_table["mode"].astype(str).unique())
        missing_modes = sorted(set(PCA_MODES) - modes)
        if missing_modes:
            errors.append("task2_8j_3_missing_modes:" + ",".join(missing_modes))
        for col in ["usefulness_score", "stability_score", "nonredundancy_score", "overall_evaluation_score"]:
            if not bool(evaluation_table[col].astype(float).between(0.0, 1.0).all()):
                errors.append(f"task2_8j_3_score_out_of_range:{col}")
    if final_summary is not None and not final_summary.empty:
        if bool(final_summary["adoption_performed"].astype(bool).any()):
            errors.append("task2_8j_3_adoption_performed_true")
        if bool(final_summary["freeze_performed"].astype(bool).any()):
            errors.append("task2_8j_3_freeze_performed_true")
    return errors


def summarize_effective_dimension_evaluation(
    evaluation_table: pd.DataFrame,
    component_count_table: pd.DataFrame,
    overlap_table: pd.DataFrame,
    final_summary: pd.DataFrame,
) -> dict:
    if evaluation_table is None or evaluation_table.empty:
        return {"rows": 0, "best_mode": "none"}
    best = evaluation_table.sort_values("overall_evaluation_score", ascending=False).iloc[0]
    return {
        "rows": int(len(evaluation_table)),
        "component_count_rows": int(len(component_count_table)) if component_count_table is not None else 0,
        "overlap_rows": int(len(overlap_table)) if overlap_table is not None else 0,
        "final_summary_rows": int(len(final_summary)) if final_summary is not None else 0,
        "modes": sorted(evaluation_table["mode"].astype(str).unique().tolist()),
        "best_mode": str(best["mode"]),
        "best_candidate_status": str(best["candidate_status"]),
        "best_overall_score": float(best["overall_evaluation_score"]),
        "best_usefulness_score": float(best["usefulness_score"]),
        "best_stability_score": float(best["stability_score"]),
        "best_nonredundancy_score": float(best["nonredundancy_score"]),
        "adoption_performed": False,
        "freeze_performed": False,
    }


def build_and_validate_effective_dimension_evaluation(
    feature_cfg: CandidateFeatureLogConfig | None = None,
    pca_cfg: TemporalPCAValidationConfig | None = None,
    eval_cfg: EffectiveDimensionEvaluationConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    feature_cfg = feature_cfg or CandidateFeatureLogConfig(steps=24, seeds=(501, 502, 503), window_sizes=(1, 6, 12))
    pca_cfg = pca_cfg or TemporalPCAValidationConfig(n_components=6, sparse_top_k=12, prediction_horizon=3)
    eval_cfg = eval_cfg or EffectiveDimensionEvaluationConfig()
    component_table, model_summary, stability_table, prediction_table, upstream_errors, _pca_summary = build_and_validate_temporal_pca_validation(
        feature_cfg,
        pca_cfg,
    )
    overlap_table = build_feature_overlap_table(component_table)
    component_count_table = build_component_count_table(component_table, eval_cfg)
    evaluation_table = build_effective_dimension_evaluation_table(
        model_summary,
        stability_table,
        prediction_table,
        component_table,
        overlap_table,
        eval_cfg,
    )
    final_summary = build_final_summary_table(evaluation_table)
    errors = validate_effective_dimension_evaluation_tables(
        evaluation_table,
        component_count_table,
        overlap_table,
        final_summary,
        upstream_errors,
    )
    summary = summarize_effective_dimension_evaluation(evaluation_table, component_count_table, overlap_table, final_summary)
    summary["validation_errors"] = errors
    return evaluation_table, component_count_table, overlap_table, final_summary, errors, summary
