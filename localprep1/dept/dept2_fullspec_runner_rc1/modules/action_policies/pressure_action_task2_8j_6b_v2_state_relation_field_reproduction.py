"""Task 2-8j-6b: v2-state / relation-field reproduction validation RC1.

Purpose:
    Check whether the macro-game relation field extracted from fixed static_pca_7
    G_t reproduces observable v2 game states and state transitions.

Position:
    Task 2-8j-6 validated that macro-game signals and a relation field can be
    extracted from fixed-7-axis G_t.  This task asks a stricter question: does
    that relation field actually reproduce the observable v2-side game-state
    structure, not just produce plausible signal correlations?

Boundary:
    - validation only
    - fixed static_pca_7 main map
    - observable / coarse-grained v2 state proxies only
    - no hidden-truth / future-information input
    - no effective-dimension re-fitting or axis mutation
    - no residual auxiliary dimension injection into G_t main map
    - no action-weight conversion
    - no upper-pressure connection
    - no ActionFrame / ActionModule / FullSpec runtime / canonical write
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .pressure_action_task2_8j_1_candidate_feature_log import CandidateFeatureLogConfig
from .pressure_action_task2_8j_6_macro_game_relation_field_validation import (
    MacroGameRelationFieldConfig,
    _fit_fixed7_model,
    _safe_corr,
    _safe_float,
    build_macro_signal_extraction_table,
    build_relation_field_table,
)

TASK2_8J_6B_VERSION = "v2_state_relation_field_reproduction_rc1"
TASK2_8J_6B_CONTRACT = (
    "Task2_8j_6b_v2_state_relation_field_reproduction__fixed_static_pca_7__"
    "observable_state_proxy_only__no_axis_mutation_no_runtime_write"
)

BOUNDARY_COLUMNS = [
    "task2_8j_6b_version",
    "task2_8j_6b_contract",
    "validation_only",
    "incomplete_observation_assumption",
    "gt_main_map_name",
    "gt_main_component_count",
    "observable_state_proxy_only",
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

REQUIRED_STATE_COLUMNS = BOUNDARY_COLUMNS + [
    "state_label",
    "observed_count",
    "predicted_count",
    "true_positive",
    "precision",
    "recall",
    "f1",
    "state_reproduction_status",
]

REQUIRED_ASSIGNMENT_COLUMNS = BOUNDARY_COLUMNS + [
    "seed",
    "scenario",
    "t",
    "observed_state_label",
    "predicted_state_label",
    "state_label_match",
    "observed_state_intensity",
    "predicted_state_intensity",
]

REQUIRED_TRANSITION_COLUMNS = BOUNDARY_COLUMNS + [
    "transition_label",
    "observed_transition_count",
    "predicted_transition_count",
    "matched_transition_count",
    "transition_recall",
    "transition_precision",
    "transition_f1",
    "transition_reproduction_status",
]

REQUIRED_EDGE_COLUMNS = BOUNDARY_COLUMNS + [
    "source_macro_signal",
    "target_macro_signal",
    "observed_same_time_correlation",
    "predicted_same_time_correlation",
    "predicted_lagged_correlation",
    "observed_relation_strength",
    "predicted_relation_strength",
    "relation_strength_delta",
    "relation_sign_match",
    "edge_reproduction_status",
]

REQUIRED_SUMMARY_COLUMNS = BOUNDARY_COLUMNS + [
    "state_label_count",
    "state_assignment_count",
    "mean_state_f1",
    "transition_label_count",
    "mean_transition_f1",
    "edge_count",
    "edge_sign_match_rate",
    "mean_relation_strength_delta",
    "resource_state_status",
    "v2_state_reproduction_decision",
    "next_task",
]


@dataclass(frozen=True)
class V2StateRelationFieldReproductionConfig:
    high_threshold: float = 0.35
    low_threshold: float = -0.35
    state_f1_pass_threshold: float = 0.50
    transition_f1_pass_threshold: float = 0.40
    edge_strength_tolerance: float = 0.35
    edge_sign_match_pass_rate: float = 0.65


def _boundary_payload() -> dict:
    return {
        "task2_8j_6b_version": TASK2_8J_6B_VERSION,
        "task2_8j_6b_contract": TASK2_8J_6B_CONTRACT,
        "validation_only": True,
        "incomplete_observation_assumption": True,
        "gt_main_map_name": "static_pca_7",
        "gt_main_component_count": 7,
        "observable_state_proxy_only": True,
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


def _safe_mean(values, default: float = 0.0) -> float:
    arr = pd.to_numeric(pd.Series(values), errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if arr.empty:
        return float(default)
    return float(arr.mean())


def _score(value: object) -> float:
    return _safe_float(value, default=0.0)


def _label_from_row(row: pd.Series, cfg: V2StateRelationFieldReproductionConfig) -> tuple[str, float]:
    relation_lock = _score(row.get("relation_lock", 0.0))
    coordination_lag = _score(row.get("coordination_lag", 0.0))
    information_degradation = _score(row.get("information_degradation", 0.0))
    resource_pressure = _score(row.get("resource_pressure", 0.0))
    exploration_activity = _score(row.get("exploration_activity", 0.0))
    reversibility_loss = _score(row.get("reversibility_loss", 0.0))
    hoarding_extraction_pressure = _score(row.get("hoarding_extraction_pressure", 0.0))
    candidates = [
        ("locked_extraction", min(relation_lock, hoarding_extraction_pressure)),
        ("coordination_information_failure", min(coordination_lag, information_degradation)),
        ("relation_coordination_lock", min(relation_lock, coordination_lag)),
        ("resource_stress", resource_pressure),
        ("exploration_recovery_window", min(exploration_activity, -reversibility_loss)),
        ("general_coordination_lag", coordination_lag),
        ("information_degradation", information_degradation),
        ("relation_lock", relation_lock),
        ("hoarding_extraction_pressure", hoarding_extraction_pressure),
    ]
    label, intensity = max(candidates, key=lambda item: item[1])
    if float(intensity) < cfg.high_threshold:
        return "neutral_or_low_signal", float(intensity)
    return str(label), float(intensity)


def _state_pivots(state_table: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    observed = state_table.pivot_table(
        index=["seed", "scenario", "t"],
        columns="macro_signal",
        values="observed_signal_intensity",
        aggfunc="mean",
    ).fillna(0.0)
    predicted = state_table.pivot_table(
        index=["seed", "scenario", "t"],
        columns="macro_signal",
        values="gt_predicted_signal_intensity",
        aggfunc="mean",
    ).fillna(0.0)
    observed = observed.sort_index(axis=0).sort_index(axis=1)
    predicted = predicted.reindex(index=observed.index, columns=observed.columns).fillna(0.0)
    return observed, predicted


def build_state_assignment_table(
    state_table: pd.DataFrame,
    cfg: V2StateRelationFieldReproductionConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cfg = cfg or V2StateRelationFieldReproductionConfig()
    observed, predicted = _state_pivots(state_table)
    rows = []
    for idx in observed.index.tolist():
        obs_label, obs_intensity = _label_from_row(observed.loc[idx], cfg)
        pred_label, pred_intensity = _label_from_row(predicted.loc[idx], cfg)
        rows.append(
            {
                **_boundary_payload(),
                "seed": int(idx[0]),
                "scenario": str(idx[1]),
                "t": int(idx[2]),
                "observed_state_label": obs_label,
                "predicted_state_label": pred_label,
                "state_label_match": bool(obs_label == pred_label),
                "observed_state_intensity": obs_intensity,
                "predicted_state_intensity": pred_intensity,
            }
        )
    assignment = pd.DataFrame(rows, columns=REQUIRED_ASSIGNMENT_COLUMNS)
    metrics = _build_state_reproduction_table(assignment)
    return assignment, metrics, observed


def _build_state_reproduction_table(assignment: pd.DataFrame) -> pd.DataFrame:
    labels = sorted(set(assignment["observed_state_label"].astype(str)) | set(assignment["predicted_state_label"].astype(str)))
    rows = []
    for label in labels:
        observed = assignment["observed_state_label"].astype(str) == label
        predicted = assignment["predicted_state_label"].astype(str) == label
        tp = int((observed & predicted).sum())
        pred_count = int(predicted.sum())
        obs_count = int(observed.sum())
        precision = float(tp / max(pred_count, 1))
        recall = float(tp / max(obs_count, 1))
        f1 = float(2.0 * precision * recall / max(precision + recall, 1e-12))
        if f1 >= 0.50:
            status = "state_reproduced"
        elif f1 >= 0.25:
            status = "state_weakly_reproduced"
        else:
            status = "state_watch_or_missed"
        rows.append(
            {
                **_boundary_payload(),
                "state_label": label,
                "observed_count": obs_count,
                "predicted_count": pred_count,
                "true_positive": tp,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "state_reproduction_status": status,
            }
        )
    return pd.DataFrame(rows, columns=REQUIRED_STATE_COLUMNS)


def build_transition_reproduction_table(assignment: pd.DataFrame) -> pd.DataFrame:
    transitions = []
    for (_seed, _scenario), sub in assignment.groupby(["seed", "scenario"], sort=True):
        sub = sub.sort_values("t")
        obs = sub["observed_state_label"].astype(str).tolist()
        pred = sub["predicted_state_label"].astype(str).tolist()
        for i in range(max(0, len(sub) - 1)):
            transitions.append((f"{obs[i]}->{obs[i + 1]}", f"{pred[i]}->{pred[i + 1]}"))
    if not transitions:
        return pd.DataFrame(columns=REQUIRED_TRANSITION_COLUMNS)
    frame = pd.DataFrame(transitions, columns=["observed_transition", "predicted_transition"])
    labels = sorted(set(frame["observed_transition"].astype(str)) | set(frame["predicted_transition"].astype(str)))
    rows = []
    for label in labels:
        observed = frame["observed_transition"].astype(str) == label
        predicted = frame["predicted_transition"].astype(str) == label
        matched = int((observed & predicted).sum())
        obs_count = int(observed.sum())
        pred_count = int(predicted.sum())
        precision = float(matched / max(pred_count, 1))
        recall = float(matched / max(obs_count, 1))
        f1 = float(2.0 * precision * recall / max(precision + recall, 1e-12))
        if f1 >= 0.40:
            status = "transition_reproduced"
        elif f1 >= 0.20:
            status = "transition_weakly_reproduced"
        else:
            status = "transition_watch_or_missed"
        rows.append(
            {
                **_boundary_payload(),
                "transition_label": label,
                "observed_transition_count": obs_count,
                "predicted_transition_count": pred_count,
                "matched_transition_count": matched,
                "transition_recall": recall,
                "transition_precision": precision,
                "transition_f1": f1,
                "transition_reproduction_status": status,
            }
        )
    return pd.DataFrame(rows, columns=REQUIRED_TRANSITION_COLUMNS)


def build_relation_edge_consistency_table(
    observed_signals: pd.DataFrame,
    relation_field: pd.DataFrame,
    cfg: V2StateRelationFieldReproductionConfig | None = None,
) -> pd.DataFrame:
    cfg = cfg or V2StateRelationFieldReproductionConfig()
    rows = []
    for _, edge in relation_field.iterrows():
        source = str(edge["source_macro_signal"])
        target = str(edge["target_macro_signal"])
        if source not in observed_signals.columns or target not in observed_signals.columns:
            continue
        obs_corr = _safe_corr(observed_signals[source].to_numpy(dtype=float), observed_signals[target].to_numpy(dtype=float))
        pred_same = _safe_float(edge.get("same_time_correlation", 0.0))
        pred_lag = _safe_float(edge.get("lagged_source_to_target_correlation", 0.0))
        pred_strength = _safe_float(edge.get("relation_strength", 0.0))
        obs_strength = float(abs(obs_corr))
        pred_basis = pred_lag if abs(pred_lag) >= abs(pred_same) else pred_same
        sign_match = bool((obs_corr >= 0.0 and pred_basis >= 0.0) or (obs_corr < 0.0 and pred_basis < 0.0))
        delta = float(abs(obs_strength - pred_strength))
        if sign_match and delta <= cfg.edge_strength_tolerance:
            status = "edge_reproduced"
        elif sign_match:
            status = "edge_sign_reproduced_strength_watch"
        else:
            status = "edge_sign_mismatch_watch"
        rows.append(
            {
                **_boundary_payload(),
                "source_macro_signal": source,
                "target_macro_signal": target,
                "observed_same_time_correlation": obs_corr,
                "predicted_same_time_correlation": pred_same,
                "predicted_lagged_correlation": pred_lag,
                "observed_relation_strength": obs_strength,
                "predicted_relation_strength": pred_strength,
                "relation_strength_delta": delta,
                "relation_sign_match": sign_match,
                "edge_reproduction_status": status,
            }
        )
    out = pd.DataFrame(rows, columns=REQUIRED_EDGE_COLUMNS)
    if not out.empty:
        out = out.sort_values("predicted_relation_strength", ascending=False).reset_index(drop=True)
    return out


def build_final_summary(
    state_metrics: pd.DataFrame,
    assignment: pd.DataFrame,
    transition: pd.DataFrame,
    edge_consistency: pd.DataFrame,
    cfg: V2StateRelationFieldReproductionConfig | None = None,
) -> pd.DataFrame:
    cfg = cfg or V2StateRelationFieldReproductionConfig()
    mean_state_f1 = _safe_mean(state_metrics["f1"], 0.0) if state_metrics is not None and not state_metrics.empty else 0.0
    mean_transition_f1 = _safe_mean(transition["transition_f1"], 0.0) if transition is not None and not transition.empty else 0.0
    edge_match_rate = _safe_mean(edge_consistency["relation_sign_match"].astype(float), 0.0) if edge_consistency is not None and not edge_consistency.empty else 0.0
    mean_delta = _safe_mean(edge_consistency["relation_strength_delta"], 0.0) if edge_consistency is not None and not edge_consistency.empty else 0.0
    resource_status = "not_observed"
    if state_metrics is not None and not state_metrics.empty:
        resource_rows = state_metrics[state_metrics["state_label"].astype(str).str.contains("resource")]
        if not resource_rows.empty:
            resource_status = str(resource_rows["state_reproduction_status"].iloc[0])
    if mean_state_f1 >= cfg.state_f1_pass_threshold and edge_match_rate >= cfg.edge_sign_match_pass_rate:
        decision = "v2_state_structure_reproduced_by_relation_field"
    elif mean_state_f1 >= 0.30 and edge_match_rate >= 0.50:
        decision = "v2_state_structure_partially_reproduced_with_watch_items"
    else:
        decision = "v2_state_structure_not_reproduced_enough_yet"
    row = {
        **_boundary_payload(),
        "state_label_count": int(len(state_metrics)) if state_metrics is not None else 0,
        "state_assignment_count": int(len(assignment)) if assignment is not None else 0,
        "mean_state_f1": float(mean_state_f1),
        "transition_label_count": int(len(transition)) if transition is not None else 0,
        "mean_transition_f1": float(mean_transition_f1),
        "edge_count": int(len(edge_consistency)) if edge_consistency is not None else 0,
        "edge_sign_match_rate": float(edge_match_rate),
        "mean_relation_strength_delta": float(mean_delta),
        "resource_state_status": resource_status,
        "v2_state_reproduction_decision": decision,
        "next_task": "Task 2-8j-7: O_t observation map over fixed-7-axis G_t relation field",
    }
    return pd.DataFrame([row], columns=REQUIRED_SUMMARY_COLUMNS)


def validate_v2_state_reproduction_tables(
    state_metrics: pd.DataFrame,
    assignment: pd.DataFrame,
    transition: pd.DataFrame,
    edge_consistency: pd.DataFrame,
    final_summary: pd.DataFrame,
) -> list[str]:
    errors: list[str] = []
    tables = {
        "state_metrics": (state_metrics, REQUIRED_STATE_COLUMNS),
        "assignment": (assignment, REQUIRED_ASSIGNMENT_COLUMNS),
        "transition": (transition, REQUIRED_TRANSITION_COLUMNS),
        "edge_consistency": (edge_consistency, REQUIRED_EDGE_COLUMNS),
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
            errors.append(f"task2_8j_6b_empty_table:{name}")
            continue
        missing = [c for c in required if c not in table.columns]
        if missing:
            errors.append(f"task2_8j_6b_missing_columns:{name}:" + ",".join(missing))
            continue
        for col in ["validation_only", "incomplete_observation_assumption", "observable_state_proxy_only"]:
            if not bool(table[col].astype(bool).all()):
                errors.append(f"task2_8j_6b_required_true_not_all_true:{name}:{col}")
        if set(table["gt_main_map_name"].astype(str)) != {"static_pca_7"}:
            errors.append(f"task2_8j_6b_wrong_gt_main_map_name:{name}")
        if set(table["gt_main_component_count"].astype(int)) != {7}:
            errors.append(f"task2_8j_6b_wrong_gt_main_component_count:{name}")
        for col in forbidden_true:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_6b_forbidden_true:{name}:{col}")
    if assignment is not None and not assignment.empty:
        observed_labels = set(assignment["observed_state_label"].astype(str))
        if len(observed_labels) < 2:
            errors.append("task2_8j_6b_too_few_observed_state_labels")
    if edge_consistency is not None and not edge_consistency.empty:
        if not bool(edge_consistency["relation_sign_match"].isin([True, False]).all()):
            errors.append("task2_8j_6b_invalid_relation_sign_match")
    return errors


def build_and_validate_v2_state_relation_field_reproduction(
    feature_cfg: CandidateFeatureLogConfig | None = None,
    macro_cfg: MacroGameRelationFieldConfig | None = None,
    cfg: V2StateRelationFieldReproductionConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    cfg = cfg or V2StateRelationFieldReproductionConfig()
    macro_cfg = macro_cfg or MacroGameRelationFieldConfig()
    model, upstream_errors = _fit_fixed7_model(feature_cfg)
    signal_table, macro_state_table, predicted = build_macro_signal_extraction_table(model, macro_cfg)
    relation_field = build_relation_field_table(model, predicted, macro_cfg)
    assignment, state_metrics, observed_signals = build_state_assignment_table(macro_state_table, cfg)
    transition = build_transition_reproduction_table(assignment)
    edge_consistency = build_relation_edge_consistency_table(observed_signals, relation_field, cfg)
    final_summary = build_final_summary(state_metrics, assignment, transition, edge_consistency, cfg)
    errors = [f"task2_8j_6b_upstream_error:{e}" for e in upstream_errors]
    errors.extend(validate_v2_state_reproduction_tables(state_metrics, assignment, transition, edge_consistency, final_summary))
    summary = {
        "gt_main_map_name": "static_pca_7",
        "gt_main_component_count": 7,
        "state_label_count": int(final_summary["state_label_count"].iloc[0]) if not final_summary.empty else 0,
        "state_assignment_count": int(final_summary["state_assignment_count"].iloc[0]) if not final_summary.empty else 0,
        "mean_state_f1": _safe_float(final_summary["mean_state_f1"].iloc[0]) if not final_summary.empty else 0.0,
        "mean_transition_f1": _safe_float(final_summary["mean_transition_f1"].iloc[0]) if not final_summary.empty else 0.0,
        "edge_sign_match_rate": _safe_float(final_summary["edge_sign_match_rate"].iloc[0]) if not final_summary.empty else 0.0,
        "v2_state_reproduction_decision": str(final_summary["v2_state_reproduction_decision"].iloc[0]) if not final_summary.empty else "empty",
        "validation_errors": errors,
    }
    return state_metrics, assignment, transition, edge_consistency, final_summary, errors, summary
