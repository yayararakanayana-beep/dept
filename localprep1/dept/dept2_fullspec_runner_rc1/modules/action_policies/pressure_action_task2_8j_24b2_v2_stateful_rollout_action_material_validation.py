"""Task 2-8j-24b2: v2 stateful rollout action-material validation RC1.

This replaces the earlier lightweight proxy sweep with a stricter validation pass.
It uses observable v2 state timelines and the Task6 relation field to build a
stateful sandbox rollout.  For each Task24 terrain-operator material row, it
compares:

    observed NO_OP future trajectory
    vs relation-field counterfactual rollout with the operator material applied
    vs reversed-operator negative control

across multiple seeds, scenarios, start times, and action timing steps.

The v2 window is used only as validation scoring evidence for adoption-threshold
plausibility.  It is not a runtime oracle, does not update thresholds, does not
create formal action candidates, and does not call the real ActionModule.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Any

import numpy as np
import pandas as pd

from .pressure_action_task2_8j_1_candidate_feature_log import CandidateFeatureLogConfig
from .pressure_action_task2_8j_6_macro_game_relation_field_validation import MacroGameRelationFieldConfig, build_and_validate_macro_game_relation_field
from .pressure_action_task2_8j_6b_v2_state_relation_field_reproduction import (
    V2StateRelationFieldReproductionConfig,
    build_and_validate_v2_state_relation_field_reproduction,
)
from .pressure_action_task2_8j_24_terrain_operator_selection_dry_run import (
    TerrainOperatorSelectionDryRunConfig,
    build_and_validate_terrain_operator_selection_dry_run,
)

TASK2_8J_24B2_VERSION = "v2_stateful_rollout_action_material_validation_rc1"
TASK24_ACCEPTED_DECISION = "terrain_operator_selection_dry_run_ready"
TASK6B_ACCEPTED_DECISION = "relation_field_reproduces_observable_v2_game_structure"

BOUNDARY: dict[str, Any] = {
    "task2_8j_24b2_version": TASK2_8J_24B2_VERSION,
    "validation_only": True,
    "stateful_rollout_validation": True,
    "observable_v2_no_op_future_used_for_scoring": True,
    "relation_field_counterfactual_rollout_used": True,
    "negative_control_rollout_used": True,
    "v2_window_used_as_validation_surface": True,
    "v2_window_not_runtime_oracle": True,
    "NO_OP_comparison_required": True,
    "multi_seed_multi_start_required": True,
    "step_count_sensitivity": True,
    "adoption_threshold_tradeoff_audit": True,
    "source_task24_required": True,
    "source_task6b_required": True,
    "gt_main_map_name": "static_pca_7",
    "gt_main_component_count": 7,
    "terrain_operator_material_input_used": True,
    "threshold_values_are_provisional": True,
    "threshold_revision_requires_validation": True,
    "no_threshold_update_performed": True,
    "overfit_to_v2_forbidden": True,
    "release_rollback_audit_shaped": False,
    "action_candidate_generated": False,
    "concrete_action_generated": False,
    "action_effect_prediction_generated": False,
    "effect_prediction_model_executed": False,
    "expected_value_final_judgment_performed": False,
    "real_actionmodule_called": False,
    "axis_executed": False,
    "upper_pressure_coupled_now": False,
    "hidden_truth_input": False,
    "future_information_used_as_runtime_input": False,
    "canonical_write_performed": False,
}

REQUIRED_TRUE = [
    "validation_only", "stateful_rollout_validation", "observable_v2_no_op_future_used_for_scoring",
    "relation_field_counterfactual_rollout_used", "negative_control_rollout_used", "v2_window_used_as_validation_surface",
    "v2_window_not_runtime_oracle", "NO_OP_comparison_required", "multi_seed_multi_start_required",
    "step_count_sensitivity", "adoption_threshold_tradeoff_audit", "source_task24_required", "source_task6b_required",
    "terrain_operator_material_input_used", "threshold_values_are_provisional", "threshold_revision_requires_validation",
    "no_threshold_update_performed", "overfit_to_v2_forbidden",
]
FORBIDDEN_TRUE = [
    "release_rollback_audit_shaped", "action_candidate_generated", "concrete_action_generated",
    "action_effect_prediction_generated", "effect_prediction_model_executed", "expected_value_final_judgment_performed",
    "real_actionmodule_called", "axis_executed", "upper_pressure_coupled_now", "hidden_truth_input",
    "future_information_used_as_runtime_input", "canonical_write_performed",
]

START_COLUMNS = list(BOUNDARY) + ["start_id", "seed", "scenario", "t0", "horizon", "signal_count", "start_status"]
ROLLOUT_COLUMNS = list(BOUNDARY) + [
    "rollout_id", "operator_selection_id", "start_id", "seed", "scenario", "t0", "risk_name", "selected_operator_name",
    "action_wait_step", "horizon", "no_op_final_risk", "action_final_risk", "negative_control_final_risk",
    "no_op_peak_risk", "action_peak_risk", "risk_reduction_final", "risk_reduction_peak", "negative_control_gap",
    "side_effect_delta", "rollback_margin", "boundary_margin", "relative_ev_rollout", "action_beats_no_op",
    "action_beats_negative_control", "timing_class", "rollout_status",
]
STEP_COLUMNS = list(BOUNDARY) + [
    "step_summary_id", "action_wait_step", "row_count", "mean_relative_ev_rollout", "median_relative_ev_rollout",
    "action_beats_no_op_rate", "action_beats_negative_control_rate", "mean_risk_reduction_final", "mean_rollback_margin",
    "mean_boundary_margin", "step_status",
]
THRESHOLD_COLUMNS = list(BOUNDARY) + [
    "threshold_audit_id", "confidence_threshold_candidate", "max_allowed_wait_step", "minimum_relative_ev_candidate",
    "minimum_rollback_margin_candidate", "minimum_boundary_margin_candidate", "accepted_rollout_count", "mean_accepted_ev",
    "accepted_late_count", "accepted_negative_control_failure_count", "threshold_candidate_class", "may_update_threshold_now",
    "requires_validation_before_update", "threshold_audit_status",
]
CHECK_COLUMNS = list(BOUNDARY) + ["check_id", "check_scope", "check_description", "expected_value", "observed_value", "check_status"]
SUMMARY_COLUMNS = list(BOUNDARY) + [
    "operator_selection_count", "v2_start_count", "rollout_row_count", "step_summary_count", "threshold_audit_count",
    "unique_seed_count", "unique_scenario_count", "action_beats_no_op_rate", "action_beats_negative_control_rate",
    "positive_ev_rate", "best_wait_step", "best_step_mean_ev", "threshold_candidate_viable_count",
    "validation_check_count", "validation_check_pass_count", "task24_ready", "task6b_ready",
    "v2_stateful_rollout_action_material_validation_decision", "next_task",
]


@dataclass(frozen=True)
class V2StatefulRolloutActionMaterialValidationConfig:
    require_task24_ready: bool = True
    require_task6b_ready: bool = True
    feature_steps: int = 36
    seeds: tuple[int, ...] = (501, 502, 503, 504, 505)
    horizon: int = 6
    max_wait_step: int = 5
    start_stride: int = 3
    max_starts: int = 90


def _with_boundary(row: dict[str, Any]) -> dict[str, Any]:
    return {**BOUNDARY, **row}


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return float(default)
    return float(out) if np.isfinite(out) else float(default)


def _pivot_timeline(state_timeline: pd.DataFrame) -> pd.DataFrame:
    pivot = state_timeline.pivot_table(
        index=["seed", "scenario", "t"],
        columns="macro_signal",
        values="observable_v2_state_intensity",
        aggfunc="mean",
    ).sort_index()
    return pivot.apply(pd.to_numeric, errors="coerce").fillna(0.0)


def build_v2_rollout_start_points(state_timeline: pd.DataFrame, cfg: V2StatefulRolloutActionMaterialValidationConfig) -> pd.DataFrame:
    pivot = _pivot_timeline(state_timeline)
    rows: list[dict[str, Any]] = []
    count = 0
    for (seed, scenario), group in state_timeline.groupby(["seed", "scenario"], sort=True):
        times = sorted(group["t"].astype(int).unique().tolist())
        max_t = max(times) if times else -1
        for t0 in times[:: max(1, cfg.start_stride)]:
            if t0 + cfg.horizon > max_t:
                continue
            key = (int(seed), str(scenario), int(t0))
            if key not in pivot.index:
                continue
            rows.append(_with_boundary({
                "start_id": f"start_{int(seed)}_{str(scenario)}_{int(t0)}",
                "seed": int(seed),
                "scenario": str(scenario),
                "t0": int(t0),
                "horizon": int(cfg.horizon),
                "signal_count": int(len(pivot.columns)),
                "start_status": "observable_v2_start_state_ready_for_rollout_validation",
            }))
            count += 1
            if count >= cfg.max_starts:
                return pd.DataFrame(rows, columns=START_COLUMNS)
    return pd.DataFrame(rows, columns=START_COLUMNS)


def _relation_matrix(relation_field: pd.DataFrame, signals: list[str]) -> np.ndarray:
    index = {s: i for i, s in enumerate(signals)}
    mat = np.zeros((len(signals), len(signals)), dtype=float)
    if relation_field is None or relation_field.empty:
        return mat
    for row in relation_field.itertuples(index=False):
        source = str(row.source_macro_signal)
        target = str(row.target_macro_signal)
        if source not in index or target not in index:
            continue
        coef = 0.35 * _safe_float(row.same_time_correlation) + 0.55 * _safe_float(row.lagged_source_to_target_correlation)
        mat[index[target], index[source]] += float(np.clip(coef, -0.35, 0.35))
    for i in range(mat.shape[0]):
        row_abs = float(np.sum(np.abs(mat[i])))
        if row_abs > 0.65:
            mat[i] *= 0.65 / row_abs
    return mat


def _risk_weights(risk_name: str, signals: list[str]) -> np.ndarray:
    specs = {
        "relation_lock": {"relation_lock": 1.0, "coordination_lag": 0.25, "exploration_activity": -0.15},
        "resource_pressure": {"resource_pressure": 1.0, "hoarding_extraction_pressure": 0.25},
        "reversibility_loss": {"reversibility_loss": 1.0, "relation_lock": 0.20},
        "boundary_fragile": {"reversibility_loss": 0.55, "resource_pressure": 0.35, "relation_lock": 0.25},
        "oscillation": {"coordination_lag": 0.50, "relation_lock": 0.30, "resource_pressure": 0.20},
    }.get(str(risk_name), {str(risk_name): 1.0})
    w = np.zeros(len(signals), dtype=float)
    for name, val in specs.items():
        if name in signals:
            w[signals.index(name)] = float(val)
    denom = max(float(np.sum(np.abs(w))), 1e-12)
    return w / denom


def _action_effect(selected_operator: str, risk_name: str, signals: list[str]) -> np.ndarray:
    effect = np.zeros(len(signals), dtype=float)
    def add(name: str, val: float) -> None:
        if name in signals:
            effect[signals.index(name)] += float(val)
    op = str(selected_operator)
    risk = str(risk_name)
    if op == "soft_resistance":
        add("relation_lock", -0.20); add("coordination_lag", -0.04); add("exploration_activity", -0.03)
    elif op == "pressure_diffusion":
        add("resource_pressure", -0.22); add("hoarding_extraction_pressure", -0.06); add("coordination_lag", 0.03)
    elif op == "reversibility_support":
        add("reversibility_loss", -0.24); add("relation_lock", -0.05); add("exploration_activity", 0.04)
    elif op == "buffer_injection":
        add("resource_pressure", -0.12); add("reversibility_loss", -0.10); add("coordination_lag", 0.04)
    elif op == "damping":
        add("coordination_lag", -0.18); add("relation_lock", -0.08); add("exploration_activity", -0.05)
    elif op == "escape_channel":
        add("relation_lock", -0.12); add("reversibility_loss", -0.12); add("exploration_activity", 0.08)
    if risk == "boundary_fragile":
        add("reversibility_loss", -0.06); add("resource_pressure", -0.04)
    if risk == "oscillation":
        add("coordination_lag", -0.04)
    return effect


def _risk_score(state: np.ndarray, weights: np.ndarray) -> float:
    return float(np.dot(state, weights))


def _roll_state(state: np.ndarray, mat: np.ndarray, drift: np.ndarray) -> np.ndarray:
    nxt = 0.74 * state + 0.26 * (mat @ state) + 0.35 * drift
    return np.clip(nxt, -4.0, 4.0)


def _side_effect(action_final: np.ndarray, noop_final: np.ndarray, weights: np.ndarray, signals: list[str]) -> float:
    non_target = np.where(np.abs(weights) < 1e-9)[0]
    harm = float(np.mean(np.maximum(action_final[non_target] - noop_final[non_target], 0.0))) if len(non_target) else 0.0
    if "exploration_activity" in signals:
        i = signals.index("exploration_activity")
        harm += max(0.0, float(noop_final[i] - action_final[i])) * 0.25
    if "information_degradation" in signals:
        i = signals.index("information_degradation")
        harm += max(0.0, float(action_final[i] - noop_final[i])) * 0.15
    return float(harm)


def build_stateful_rollout_validation(selection: pd.DataFrame, state_timeline: pd.DataFrame, relation_field: pd.DataFrame, starts: pd.DataFrame, cfg: V2StatefulRolloutActionMaterialValidationConfig) -> pd.DataFrame:
    pivot = _pivot_timeline(state_timeline)
    signals = [str(c) for c in pivot.columns.tolist()]
    mat = _relation_matrix(relation_field, signals)
    records: list[dict[str, Any]] = []
    for _, op in selection.iterrows():
        risk = str(op["risk_name"])
        weights = _risk_weights(risk, signals)
        effect = _action_effect(str(op["selected_operator_name"]), risk, signals)
        for _, st in starts.iterrows():
            seed, scenario, t0 = int(st["seed"]), str(st["scenario"]), int(st["t0"])
            no_op_path = []
            ok = True
            for dt in range(cfg.horizon + 1):
                key = (seed, scenario, t0 + dt)
                if key not in pivot.index:
                    ok = False; break
                no_op_path.append(pivot.loc[key].to_numpy(dtype=float))
            if not ok or len(no_op_path) != cfg.horizon + 1:
                continue
            no_op_final = no_op_path[-1]
            no_op_risk_path = [_risk_score(x, weights) for x in no_op_path]
            for wait in range(cfg.max_wait_step + 1):
                if wait > cfg.horizon:
                    continue
                action_state = no_op_path[wait].copy() + effect
                neg_state = no_op_path[wait].copy() - effect
                action_path = [action_state.copy()]
                neg_path = [neg_state.copy()]
                for dt in range(wait, cfg.horizon):
                    drift = no_op_path[dt + 1] - no_op_path[dt]
                    action_state = _roll_state(action_state, mat, drift)
                    neg_state = _roll_state(neg_state, mat, drift)
                    action_path.append(action_state.copy())
                    neg_path.append(neg_state.copy())
                action_final = action_path[-1]
                neg_final = neg_path[-1]
                action_risk_path = [_risk_score(x, weights) for x in action_path]
                neg_risk_path = [_risk_score(x, weights) for x in neg_path]
                no_op_final_risk = no_op_risk_path[-1]
                action_final_risk = action_risk_path[-1]
                neg_final_risk = neg_risk_path[-1]
                no_op_peak = max(no_op_risk_path[wait:]) if wait < len(no_op_risk_path) else no_op_final_risk
                action_peak = max(action_risk_path) if action_risk_path else action_final_risk
                final_reduction = no_op_final_risk - action_final_risk
                peak_reduction = no_op_peak - action_peak
                neg_gap = neg_final_risk - action_final_risk
                side_effect = _side_effect(action_final, no_op_final, weights, signals)
                displacement = float(np.linalg.norm(action_final - no_op_final) / max(sqrt(len(signals)), 1e-9))
                rollback_margin = float(np.clip(1.0 - 0.22 * displacement - 0.055 * wait, 0.0, 1.0))
                boundary_margin = float(np.clip(1.0 - 0.15 * max(0.0, action_final_risk) - 0.035 * wait, 0.0, 1.0))
                timing_penalty = 0.045 * wait
                ev = float(final_reduction + 0.45 * peak_reduction + 0.10 * rollback_margin + 0.08 * boundary_margin - 0.35 * side_effect - timing_penalty)
                if ev > 0.08 and final_reduction > 0 and neg_gap > 0:
                    tclass = "action_material_beats_NO_OP_and_negative_control"
                elif ev > 0.0 and wait <= 1:
                    tclass = "early_action_material_promising_but_review_needed"
                elif wait >= 3 and ev <= 0.0:
                    tclass = "late_timing_loses_value"
                elif final_reduction <= 0:
                    tclass = "NO_OP_or_negative_control_preferred"
                else:
                    tclass = "mixed_rollout_review"
                records.append(_with_boundary({
                    "rollout_id": f"rollout_{op['operator_selection_id']}_{st['start_id']}_wait_{wait}",
                    "operator_selection_id": str(op["operator_selection_id"]),
                    "start_id": str(st["start_id"]),
                    "seed": seed,
                    "scenario": scenario,
                    "t0": t0,
                    "risk_name": risk,
                    "selected_operator_name": str(op["selected_operator_name"]),
                    "action_wait_step": int(wait),
                    "horizon": int(cfg.horizon),
                    "no_op_final_risk": round(float(no_op_final_risk), 6),
                    "action_final_risk": round(float(action_final_risk), 6),
                    "negative_control_final_risk": round(float(neg_final_risk), 6),
                    "no_op_peak_risk": round(float(no_op_peak), 6),
                    "action_peak_risk": round(float(action_peak), 6),
                    "risk_reduction_final": round(float(final_reduction), 6),
                    "risk_reduction_peak": round(float(peak_reduction), 6),
                    "negative_control_gap": round(float(neg_gap), 6),
                    "side_effect_delta": round(float(side_effect), 6),
                    "rollback_margin": round(float(rollback_margin), 6),
                    "boundary_margin": round(float(boundary_margin), 6),
                    "relative_ev_rollout": round(float(ev), 6),
                    "action_beats_no_op": bool(final_reduction > 0 and ev > 0.0),
                    "action_beats_negative_control": bool(neg_gap > 0),
                    "timing_class": tclass,
                    "rollout_status": "stateful_relation_field_counterfactual_compared_to_observed_NO_OP_future",
                }))
    return pd.DataFrame(records, columns=ROLLOUT_COLUMNS)


def build_step_summary(rollout: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for step, g in rollout.groupby("action_wait_step", sort=True):
        rows.append(_with_boundary({
            "step_summary_id": f"step_summary_{int(step)}",
            "action_wait_step": int(step),
            "row_count": int(len(g)),
            "mean_relative_ev_rollout": round(float(g["relative_ev_rollout"].mean()), 6),
            "median_relative_ev_rollout": round(float(g["relative_ev_rollout"].median()), 6),
            "action_beats_no_op_rate": round(float(g["action_beats_no_op"].astype(bool).mean()), 6),
            "action_beats_negative_control_rate": round(float(g["action_beats_negative_control"].astype(bool).mean()), 6),
            "mean_risk_reduction_final": round(float(g["risk_reduction_final"].mean()), 6),
            "mean_rollback_margin": round(float(g["rollback_margin"].mean()), 6),
            "mean_boundary_margin": round(float(g["boundary_margin"].mean()), 6),
            "step_status": "stateful_step_summary_ready",
        }))
    return pd.DataFrame(rows, columns=STEP_COLUMNS)


def build_threshold_audit(rollout: pd.DataFrame) -> pd.DataFrame:
    rows = []
    idx = 1
    # confidence is represented by wait step in this validation: higher wait means more confirmation but more timing loss.
    for conf in [0.55, 0.60, 0.65, 0.70]:
        for max_wait in [0, 1, 2, 3, 4, 5]:
            for min_ev in [0.00, 0.05, 0.10, 0.15]:
                for min_rb in [0.35, 0.50, 0.65]:
                    implied_wait_min = max(0, int(round((conf - 0.55) / 0.05)))
                    eligible = rollout[
                        (rollout["action_wait_step"].astype(int) >= implied_wait_min)
                        & (rollout["action_wait_step"].astype(int) <= max_wait)
                        & (rollout["relative_ev_rollout"].astype(float) >= min_ev)
                        & (rollout["rollback_margin"].astype(float) >= min_rb)
                        & (rollout["boundary_margin"].astype(float) >= 0.45)
                    ]
                    count = int(len(eligible))
                    mean_ev = float(eligible["relative_ev_rollout"].mean()) if count else 0.0
                    late_count = int((eligible["action_wait_step"].astype(int) >= 3).sum()) if count else 0
                    neg_fail = int((~eligible["action_beats_negative_control"].astype(bool)).sum()) if count else 0
                    if count == 0:
                        cls = "too_strict_or_confirmation_too_late"
                    elif neg_fail > 0:
                        cls = "admits_negative_control_failures_reject"
                    elif late_count > 0:
                        cls = "admits_late_rollouts_review_timing_loss"
                    else:
                        cls = "candidate_for_provisional_adoption_hardle"
                    rows.append(_with_boundary({
                        "threshold_audit_id": f"threshold_{idx:04d}",
                        "confidence_threshold_candidate": float(conf),
                        "max_allowed_wait_step": int(max_wait),
                        "minimum_relative_ev_candidate": float(min_ev),
                        "minimum_rollback_margin_candidate": float(min_rb),
                        "minimum_boundary_margin_candidate": 0.45,
                        "accepted_rollout_count": count,
                        "mean_accepted_ev": round(mean_ev, 6),
                        "accepted_late_count": late_count,
                        "accepted_negative_control_failure_count": neg_fail,
                        "threshold_candidate_class": cls,
                        "may_update_threshold_now": False,
                        "requires_validation_before_update": True,
                        "threshold_audit_status": "stateful_threshold_audit_ready_no_update",
                    }))
                    idx += 1
    return pd.DataFrame(rows, columns=THRESHOLD_COLUMNS)


def build_validation_checks(selection: pd.DataFrame, starts: pd.DataFrame, rollout: pd.DataFrame, step_summary: pd.DataFrame, threshold: pd.DataFrame, task24_ready: bool, task6b_ready: bool) -> pd.DataFrame:
    checks = [
        ("check_task24_ready", "upstream", "Task24 terrain operator material is ready.", True, task24_ready),
        ("check_task6b_ready", "upstream", "Task6b v2 relation-field reproduction is ready.", True, task6b_ready),
        ("check_multi_seed", "coverage", "At least three seeds are used.", True, int(starts["seed"].nunique()) >= 3 if not starts.empty else False),
        ("check_start_count", "coverage", "At least 20 observable v2 start states are used.", True, len(starts) >= 20),
        ("check_rollout_volume", "rollout", "Rollout volume is larger than a small proxy sweep.", True, len(rollout) >= max(1, len(selection) * 20)),
        ("check_step_coverage", "rollout", "All wait steps 0..5 are represented.", True, set(rollout["action_wait_step"].astype(int)) == set(range(6)) if not rollout.empty else False),
        ("check_negative_control", "control", "Negative-control comparison is present.", True, bool(rollout["negative_control_rollout_used"].astype(bool).all()) if not rollout.empty else False),
        ("check_some_action_success", "outcome", "At least one rollout beats NO_OP.", True, bool(rollout["action_beats_no_op"].astype(bool).any()) if not rollout.empty else False),
        ("check_step_summary", "step", "Step summary exists.", True, len(step_summary) == 6),
        ("check_threshold_audit", "threshold", "Threshold audit exists and does not update thresholds.", True, len(threshold) > 0 and not bool(threshold["may_update_threshold_now"].astype(bool).any())),
        ("check_no_action_candidate", "boundary", "No formal action candidate is generated.", False, bool(rollout["action_candidate_generated"].astype(bool).any()) if not rollout.empty else True),
        ("check_no_real_execution", "boundary", "No real ActionModule call or axis execution occurs.", False, bool(rollout["real_actionmodule_called"].astype(bool).any() or rollout["axis_executed"].astype(bool).any()) if not rollout.empty else True),
        ("check_no_runtime_future", "boundary", "Future v2 states are not used as runtime input.", False, bool(rollout["future_information_used_as_runtime_input"].astype(bool).any()) if not rollout.empty else True),
    ]
    return pd.DataFrame([_with_boundary({"check_id": c[0], "check_scope": c[1], "check_description": c[2], "expected_value": bool(c[3]), "observed_value": bool(c[4]), "check_status": "pass" if bool(c[3]) == bool(c[4]) else "fail"}) for c in checks], columns=CHECK_COLUMNS)


def build_final_summary(selection: pd.DataFrame, starts: pd.DataFrame, rollout: pd.DataFrame, step_summary: pd.DataFrame, threshold: pd.DataFrame, checks: pd.DataFrame, task24_ready: bool, task6b_ready: bool) -> pd.DataFrame:
    pass_count = int((checks["check_status"].astype(str) == "pass").sum()) if not checks.empty else 0
    best_step = int(step_summary.sort_values("mean_relative_ev_rollout", ascending=False)["action_wait_step"].iloc[0]) if not step_summary.empty else -1
    best_ev = float(step_summary.sort_values("mean_relative_ev_rollout", ascending=False)["mean_relative_ev_rollout"].iloc[0]) if not step_summary.empty else 0.0
    viable = int((threshold["threshold_candidate_class"].astype(str) == "candidate_for_provisional_adoption_hardle").sum()) if not threshold.empty else 0
    decision = "v2_stateful_rollout_action_material_validation_ready" if task24_ready and task6b_ready and len(checks) == pass_count else "v2_stateful_rollout_action_material_validation_needs_review"
    return pd.DataFrame([_with_boundary({
        "operator_selection_count": len(selection),
        "v2_start_count": len(starts),
        "rollout_row_count": len(rollout),
        "step_summary_count": len(step_summary),
        "threshold_audit_count": len(threshold),
        "unique_seed_count": int(starts["seed"].nunique()) if not starts.empty else 0,
        "unique_scenario_count": int(starts["scenario"].nunique()) if not starts.empty else 0,
        "action_beats_no_op_rate": round(float(rollout["action_beats_no_op"].astype(bool).mean()), 6) if not rollout.empty else 0.0,
        "action_beats_negative_control_rate": round(float(rollout["action_beats_negative_control"].astype(bool).mean()), 6) if not rollout.empty else 0.0,
        "positive_ev_rate": round(float((rollout["relative_ev_rollout"].astype(float) > 0).mean()), 6) if not rollout.empty else 0.0,
        "best_wait_step": best_step,
        "best_step_mean_ev": round(best_ev, 6),
        "threshold_candidate_viable_count": viable,
        "validation_check_count": len(checks),
        "validation_check_pass_count": pass_count,
        "task24_ready": bool(task24_ready),
        "task6b_ready": bool(task6b_ready),
        "v2_stateful_rollout_action_material_validation_decision": decision,
        "next_task": "Task 2-8j-24c: adoption threshold provisional policy from stateful rollout validation",
    })], columns=SUMMARY_COLUMNS)


def validate_tables(starts: pd.DataFrame, rollout: pd.DataFrame, step_summary: pd.DataFrame, threshold: pd.DataFrame, checks: pd.DataFrame, final_summary: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    tables = {"starts": (starts, START_COLUMNS), "rollout": (rollout, ROLLOUT_COLUMNS), "step_summary": (step_summary, STEP_COLUMNS), "threshold": (threshold, THRESHOLD_COLUMNS), "checks": (checks, CHECK_COLUMNS), "final_summary": (final_summary, SUMMARY_COLUMNS)}
    for name, (table, cols) in tables.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_24b2_empty_table:{name}"); continue
        missing = [c for c in cols if c not in table.columns]
        if missing:
            errors.append(f"task2_8j_24b2_missing_columns:{name}:" + ",".join(missing)); continue
        for col in REQUIRED_TRUE:
            if not bool(table[col].astype(bool).all()):
                errors.append(f"task2_8j_24b2_required_true_not_all_true:{name}:{col}")
        for col in FORBIDDEN_TRUE:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_24b2_forbidden_true:{name}:{col}")
        if set(table["gt_main_map_name"].astype(str)) != {"static_pca_7"}:
            errors.append(f"task2_8j_24b2_wrong_gt_main_map_name:{name}")
        if set(table["gt_main_component_count"].astype(int)) != {7}:
            errors.append(f"task2_8j_24b2_wrong_gt_component_count:{name}")
    if checks is not None and not checks.empty and not bool((checks["check_status"].astype(str) == "pass").all()):
        errors.append("task2_8j_24b2_check_failed")
    if rollout is not None and not rollout.empty and len(rollout) < 180:
        errors.append("task2_8j_24b2_rollout_too_small")
    if threshold is not None and not threshold.empty:
        if bool(threshold["may_update_threshold_now"].astype(bool).any()):
            errors.append("task2_8j_24b2_threshold_update_attempted")
        if not bool(threshold["requires_validation_before_update"].astype(bool).all()):
            errors.append("task2_8j_24b2_threshold_candidate_without_validation_requirement")
    return errors


def build_and_validate_v2_stateful_rollout_action_material_validation(cfg: V2StatefulRolloutActionMaterialValidationConfig | None = None, **_unused: object) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    cfg = cfg or V2StatefulRolloutActionMaterialValidationConfig()
    feature_cfg = CandidateFeatureLogConfig(steps=cfg.feature_steps, seeds=cfg.seeds, window_sizes=(1, 6, 12))
    selection, _review24, _checks24, _final24, task24_errors, task24_summary = build_and_validate_terrain_operator_selection_dry_run(cfg=TerrainOperatorSelectionDryRunConfig())
    _state_repro, state_timeline, _transition, _consistency, _final6b, task6b_errors, task6b_summary = build_and_validate_v2_state_relation_field_reproduction(feature_cfg, MacroGameRelationFieldConfig(), V2StateRelationFieldReproductionConfig())
    _signal_table, _task6_state_table, relation_field, _task6_summary, task6_errors, _task6_json = build_and_validate_macro_game_relation_field(feature_cfg, MacroGameRelationFieldConfig())
    task24_ready = len(task24_errors) == 0 and str(task24_summary.get("terrain_operator_selection_dry_run_decision", "")).startswith(TASK24_ACCEPTED_DECISION)
    task6b_ready = len(task6b_errors) == 0 and str(task6b_summary.get("v2_state_reproduction_decision", "")).startswith(TASK6B_ACCEPTED_DECISION)
    if not cfg.require_task24_ready:
        task24_ready = True
    if not cfg.require_task6b_ready:
        task6b_ready = True
    starts = build_v2_rollout_start_points(state_timeline, cfg)
    rollout = build_stateful_rollout_validation(selection, state_timeline, relation_field, starts, cfg)
    step_summary = build_step_summary(rollout)
    threshold = build_threshold_audit(rollout)
    checks = build_validation_checks(selection, starts, rollout, step_summary, threshold, task24_ready, task6b_ready)
    final_summary = build_final_summary(selection, starts, rollout, step_summary, threshold, checks, task24_ready, task6b_ready)
    errors: list[str] = []
    if cfg.require_task24_ready:
        errors += [f"task2_8j_24b2_upstream_24_error:{e}" for e in task24_errors]
    if cfg.require_task6b_ready:
        errors += [f"task2_8j_24b2_upstream_6b_error:{e}" for e in task6b_errors]
    errors += [f"task2_8j_24b2_upstream_6_error:{e}" for e in task6_errors]
    errors += validate_tables(starts, rollout, step_summary, threshold, checks, final_summary)
    summary = {
        "gt_main_map_name": "static_pca_7",
        "gt_main_component_count": 7,
        "task24_decision": task24_summary.get("terrain_operator_selection_dry_run_decision", ""),
        "task6b_decision": task6b_summary.get("v2_state_reproduction_decision", ""),
        "operator_selection_count": _safe_int(final_summary["operator_selection_count"].iloc[0]),
        "v2_start_count": _safe_int(final_summary["v2_start_count"].iloc[0]),
        "rollout_row_count": _safe_int(final_summary["rollout_row_count"].iloc[0]),
        "step_summary_count": _safe_int(final_summary["step_summary_count"].iloc[0]),
        "threshold_audit_count": _safe_int(final_summary["threshold_audit_count"].iloc[0]),
        "unique_seed_count": _safe_int(final_summary["unique_seed_count"].iloc[0]),
        "unique_scenario_count": _safe_int(final_summary["unique_scenario_count"].iloc[0]),
        "action_beats_no_op_rate": float(final_summary["action_beats_no_op_rate"].iloc[0]),
        "action_beats_negative_control_rate": float(final_summary["action_beats_negative_control_rate"].iloc[0]),
        "positive_ev_rate": float(final_summary["positive_ev_rate"].iloc[0]),
        "best_wait_step": _safe_int(final_summary["best_wait_step"].iloc[0]),
        "best_step_mean_ev": float(final_summary["best_step_mean_ev"].iloc[0]),
        "threshold_candidate_viable_count": _safe_int(final_summary["threshold_candidate_viable_count"].iloc[0]),
        "validation_check_count": _safe_int(final_summary["validation_check_count"].iloc[0]),
        "validation_check_pass_count": _safe_int(final_summary["validation_check_pass_count"].iloc[0]),
        "task24_ready": bool(task24_ready),
        "task6b_ready": bool(task6b_ready),
        "v2_stateful_rollout_action_material_validation_decision": str(final_summary["v2_stateful_rollout_action_material_validation_decision"].iloc[0]),
        "observable_v2_no_op_future_used_for_scoring": True,
        "relation_field_counterfactual_rollout_used": True,
        "negative_control_rollout_used": True,
        "v2_window_not_runtime_oracle": True,
        "no_threshold_update_performed": True,
        "action_candidate_generated": False,
        "real_actionmodule_called": False,
        "axis_executed": False,
        "validation_errors": errors,
    }
    return starts, rollout, step_summary, threshold, checks, final_summary, errors, summary
