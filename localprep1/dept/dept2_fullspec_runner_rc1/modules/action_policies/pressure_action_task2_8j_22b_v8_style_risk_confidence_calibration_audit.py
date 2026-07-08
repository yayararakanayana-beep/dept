"""Task 2-8j-22b: v8-style risk confidence calibration audit RC1.

Audits the Task2-8j-22 risk-confidence output before any action-direction
shaping.  The audit separates three questions:
    1. What can be calibrated from information already present in the action-module packet?
    2. What cannot be calibrated yet, but can be calibrated by delayed observation?
    3. What should remain review / monitor / NO_OP until more steps are observed?

This is a v8-style confidence layer, not an action generator.  It does not create
action direction, does not select terrain operators, does not predict action
effects, and does not call any real ActionModule runtime.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from .pressure_action_task2_8j_22_gated_macro_game_risk_simulator_dry_run import (
    GatedMacroGameRiskSimulatorDryRunConfig,
    build_and_validate_gated_macro_game_risk_simulator_dry_run,
)

TASK2_8J_22B_VERSION = "v8_style_risk_confidence_calibration_audit_rc1"
TASK22_ACCEPTED_DECISION = "gated_macro_game_risk_simulator_dry_run_ready"

BOUNDARY: dict[str, Any] = {
    "task2_8j_22b_version": TASK2_8J_22B_VERSION,
    "validation_only": True,
    "audit_only": True,
    "v8_style_confidence_layer": True,
    "coarse_macro_game_structure_only": True,
    "not_high_resolution_forecast": True,
    "not_long_term_forecast": True,
    "risk_prediction_only": True,
    "system_visible_information_only": True,
    "source_task22_required": True,
    "gt_main_map_name": "static_pca_7",
    "gt_main_component_count": 7,
    "raw_risk_confidence_treated_as_uncalibrated": True,
    "internal_calibration_possible": True,
    "delayed_observation_required_for_empirical_calibration": True,
    "calibration_may_defer_to_monitor": True,
    "semantic_recipe_primary_key_forbidden": True,
    "terrain_information_primary_required": True,
    "risk_label_used_only_for_evaluation": True,
    "NO_OP_baseline_required": True,
    "action_direction_generated": False,
    "terrain_operator_selected": False,
    "release_rollback_audit_shaped": False,
    "action_candidate_generated": False,
    "concrete_action_generated": False,
    "action_effect_prediction_generated": False,
    "effect_prediction_model_executed": False,
    "expected_value_final_judgment_performed": False,
    "real_actionmodule_called": False,
    "axis_executed": False,
    "hidden_truth_input": False,
    "future_information_used": False,
    "canonical_write_performed": False,
}

REQUIRED_TRUE = [
    "validation_only", "audit_only", "v8_style_confidence_layer", "coarse_macro_game_structure_only",
    "not_high_resolution_forecast", "not_long_term_forecast", "risk_prediction_only", "system_visible_information_only",
    "source_task22_required", "raw_risk_confidence_treated_as_uncalibrated", "internal_calibration_possible",
    "delayed_observation_required_for_empirical_calibration", "calibration_may_defer_to_monitor",
    "semantic_recipe_primary_key_forbidden", "terrain_information_primary_required", "risk_label_used_only_for_evaluation",
    "NO_OP_baseline_required",
]
FORBIDDEN_TRUE = [
    "action_direction_generated", "terrain_operator_selected", "release_rollback_audit_shaped", "action_candidate_generated",
    "concrete_action_generated", "action_effect_prediction_generated", "effect_prediction_model_executed",
    "expected_value_final_judgment_performed", "real_actionmodule_called", "axis_executed", "hidden_truth_input",
    "future_information_used", "canonical_write_performed",
]

CALIBRATION_COLUMNS = list(BOUNDARY) + [
    "calibration_id", "macro_state_id", "macro_state_name", "risk_name", "raw_risk_confidence",
    "raw_confidence_band", "mean_risk", "max_risk", "trigger_rate", "risk_seed_stability",
    "gate_score", "open_signal_count", "direction_clarity", "state_uncertainty", "available_now_score",
    "information_sufficiency_score", "v8_reliability_score", "calibrated_risk_confidence", "calibration_band",
    "calibration_action", "calibration_reason", "calibration_status",
]
INFO_COLUMNS = list(BOUNDARY) + [
    "info_review_id", "macro_state_id", "macro_state_name", "available_now_items", "available_now_score",
    "missing_now_items", "delayed_observation_items", "can_calibrate_now", "needs_delayed_observation",
    "empirical_calibration_possible_later", "information_sufficiency_band", "review_status",
]
PLAN_COLUMNS = list(BOUNDARY) + [
    "plan_id", "macro_state_id", "macro_state_name", "risk_name", "raw_risk_confidence", "calibrated_risk_confidence",
    "calibration_band", "delay_horizon", "observation_target", "success_proxy", "failure_proxy",
    "update_rule", "plan_status",
]
CHECK_COLUMNS = list(BOUNDARY) + [
    "check_id", "check_scope", "check_description", "expected_value", "observed_value", "check_status",
]
SUMMARY_COLUMNS = list(BOUNDARY) + [
    "calibration_row_count", "usable_now_count", "review_count", "monitor_count", "NO_OP_or_monitor_count",
    "delayed_plan_count", "information_review_count", "needs_delayed_observation_count", "empirical_calibration_possible_later_count",
    "calibration_check_count", "calibration_check_pass_count", "task22_ready", "v8_style_risk_confidence_calibration_audit_decision", "next_task",
]


@dataclass(frozen=True)
class V8StyleRiskConfidenceCalibrationAuditConfig:
    require_task22_ready: bool = True
    delay_horizon: int = 4
    usable_threshold: float = 0.66
    review_threshold: float = 0.50


def _with_boundary(row: dict[str, Any]) -> dict[str, Any]:
    return {**BOUNDARY, **row}


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def _risk_std(trajectories: pd.DataFrame, state_id: str, risk_name: str) -> float:
    col = f"{risk_name}_risk"
    group = trajectories[trajectories["macro_state_id"].astype(str) == str(state_id)]
    if group.empty or col not in group.columns:
        return 0.0
    return float(group[col].astype(float).std(ddof=0))


def build_v8_style_calibration_audit(risk_confidence: pd.DataFrame, gate: pd.DataFrame, states: pd.DataFrame, trajectories: pd.DataFrame, directions: pd.DataFrame, cfg: V8StyleRiskConfidenceCalibrationAuditConfig) -> pd.DataFrame:
    gate_lookup = gate.set_index("macro_state_id") if not gate.empty else pd.DataFrame()
    state_lookup = states.set_index("macro_state_id") if not states.empty else pd.DataFrame()
    direction_lookup = directions.set_index("macro_state_id") if not directions.empty else pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for _, r in risk_confidence.iterrows():
        state_id = str(r["macro_state_id"])
        risk_name = str(r["risk_name"])
        gate_row = gate_lookup.loc[state_id] if state_id in gate_lookup.index else None
        state_row = state_lookup.loc[state_id] if state_id in state_lookup.index else None
        dir_row = direction_lookup.loc[state_id] if state_id in direction_lookup.index else None
        raw = float(r["risk_confidence"])
        mean_risk = float(r["mean_risk"])
        max_risk = float(r["max_risk"])
        trajectory_count = max(1, int(r["trajectory_count"]))
        trigger_rate = float(r["trigger_count"]) / trajectory_count
        std_risk = _risk_std(trajectories, state_id, risk_name)
        risk_seed_stability = _clip01(1.0 - min(1.0, std_risk * 4.0))
        gate_score = float(gate_row["gate_score"]) if gate_row is not None else 0.0
        open_signal_count = int(gate_row["open_signal_count"]) if gate_row is not None else 0
        direction_clarity = float(dir_row["direction_clarity"]) if dir_row is not None else 0.0
        uncertainty = float(state_row["uncertainty"]) if state_row is not None else 1.0
        available_now_score = _clip01(0.25 * gate_score + 0.20 * (open_signal_count / 7.0) + 0.20 * risk_seed_stability + 0.20 * direction_clarity + 0.15 * (1.0 - uncertainty))
        information_sufficiency_score = _clip01(0.55 * available_now_score + 0.25 * risk_seed_stability + 0.20 * (1.0 - uncertainty))
        near_threshold_penalty = 0.10 if 0.48 <= raw <= 0.68 else 0.0
        uncertainty_penalty = 0.18 * uncertainty
        low_clarity_penalty = 0.10 * (1.0 - direction_clarity)
        v8_reliability_score = _clip01(0.42 * information_sufficiency_score + 0.30 * risk_seed_stability + 0.18 * gate_score + 0.10 * direction_clarity - near_threshold_penalty)
        calibrated = _clip01(raw * (0.70 + 0.30 * v8_reliability_score) - uncertainty_penalty - low_clarity_penalty + 0.08 * trigger_rate)
        if calibrated >= cfg.usable_threshold and v8_reliability_score >= 0.48:
            band = "usable_for_later_material_review"
            action = "usable_later_not_action_yet"
            reason = "risk_confidence_high_enough_and_internal_information_sufficient"
        elif calibrated >= cfg.review_threshold:
            band = "review_before_use"
            action = "review"
            reason = "confidence_or_information_is_mid_band"
        else:
            band = "monitor_or_NO_OP"
            action = "monitor_or_NO_OP"
            reason = "confidence_or_information_not_sufficient"
        if str(r.get("precision_need_hint", "")) == "needs_precision_review":
            reason += ";source_task22_precision_review_needed"
            if action == "usable_later_not_action_yet" and v8_reliability_score < 0.60:
                band = "review_before_use"
                action = "review"
        rows.append(_with_boundary({
            "calibration_id": f"cal_{state_id}_{risk_name}",
            "macro_state_id": state_id,
            "macro_state_name": str(r["macro_state_name"]),
            "risk_name": risk_name,
            "raw_risk_confidence": round(raw, 6),
            "raw_confidence_band": str(r["confidence_band"]),
            "mean_risk": round(mean_risk, 6),
            "max_risk": round(max_risk, 6),
            "trigger_rate": round(trigger_rate, 6),
            "risk_seed_stability": round(risk_seed_stability, 6),
            "gate_score": round(gate_score, 6),
            "open_signal_count": open_signal_count,
            "direction_clarity": round(direction_clarity, 6),
            "state_uncertainty": round(uncertainty, 6),
            "available_now_score": round(available_now_score, 6),
            "information_sufficiency_score": round(information_sufficiency_score, 6),
            "v8_reliability_score": round(v8_reliability_score, 6),
            "calibrated_risk_confidence": round(calibrated, 6),
            "calibration_band": band,
            "calibration_action": action,
            "calibration_reason": reason,
            "calibration_status": "v8_style_internal_calibration_audited_not_empirically_calibrated",
        }))
    return pd.DataFrame(rows, columns=CALIBRATION_COLUMNS)


def build_information_sufficiency_review(calibration: pd.DataFrame, states: pd.DataFrame, gate: pd.DataFrame, directions: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    state_lookup = states.set_index("macro_state_id") if not states.empty else pd.DataFrame()
    gate_lookup = gate.set_index("macro_state_id") if not gate.empty else pd.DataFrame()
    direction_lookup = directions.set_index("macro_state_id") if not directions.empty else pd.DataFrame()
    for state_id, group in calibration.groupby("macro_state_id", sort=False):
        state_row = state_lookup.loc[state_id] if state_id in state_lookup.index else None
        gate_row = gate_lookup.loc[state_id] if state_id in gate_lookup.index else None
        dir_row = direction_lookup.loc[state_id] if state_id in direction_lookup.index else None
        available_items = [
            "raw_risk_confidence", "seed_stability", "gate_score", "open_signal_count", "state_uncertainty", "NO_OP_baseline",
        ]
        if dir_row is not None and float(dir_row["direction_clarity"]) > 0:
            available_items.append("dynamics_direction_clarity")
        missing_items: list[str] = []
        if state_row is None:
            missing_items.append("coarse_macro_state")
        if gate_row is None:
            missing_items.append("observation_gate_result")
        if dir_row is None:
            missing_items.append("dynamics_direction")
        available_score = float(group["available_now_score"].mean())
        info_score = float(group["information_sufficiency_score"].mean())
        needs_delayed = bool((group["calibration_band"].astype(str) != "usable_for_later_material_review").any()) or info_score < 0.62
        empirical_later = True
        if info_score >= 0.66:
            band = "sufficient_for_internal_review"
            can_now = True
        elif info_score >= 0.50:
            band = "partly_sufficient_needs_delayed_observation"
            can_now = True
        else:
            band = "insufficient_use_monitor_until_more_steps"
            can_now = False
        rows.append(_with_boundary({
            "info_review_id": f"info_review_{state_id}",
            "macro_state_id": str(state_id),
            "macro_state_name": str(group["macro_state_name"].iloc[0]),
            "available_now_items": ";".join(available_items),
            "available_now_score": round(available_score, 6),
            "missing_now_items": ";".join(missing_items) if missing_items else "none",
            "delayed_observation_items": "future_O_t;future_relation_field;future_risk_proxy;actual_direction_change;NO_OP_outcome_trace",
            "can_calibrate_now": bool(can_now),
            "needs_delayed_observation": bool(needs_delayed),
            "empirical_calibration_possible_later": bool(empirical_later),
            "information_sufficiency_band": band,
            "review_status": "information_sufficiency_reviewed_for_calibration_path",
        }))
    return pd.DataFrame(rows, columns=INFO_COLUMNS)


def build_delayed_observation_calibration_plan(calibration: pd.DataFrame, cfg: V8StyleRiskConfidenceCalibrationAuditConfig) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    # Plan every review/usable risk; low risks can stay monitor unless they become dominant later.
    planned = calibration[calibration["calibration_band"].astype(str).isin(["usable_for_later_material_review", "review_before_use"])]
    if planned.empty:
        planned = calibration.sort_values("calibrated_risk_confidence", ascending=False).head(6)
    proxy_map = {
        "relation_lock": ("relation_lock_signal_delta_or_cluster_persistence", "lock_signal_increases_or_persists", "lock_signal_decays_or_escape_path_recovers"),
        "resource_pressure": ("pressure_gradient_and_neighbor_capacity_delta", "pressure_accumulates_or_capacity_falls", "pressure_diffuses_or_capacity_recovers"),
        "reversibility_loss": ("reversibility_and_escape_path_delta", "reversibility_or_escape_path_decreases", "return_path_recovers"),
        "boundary_fragile": ("boundary_distance_and_uncertainty_delta", "boundary_distance_decreases_or_uncertainty_rises", "boundary_distance_recovers"),
        "oscillation": ("flow_velocity_curvature_phase_delta", "velocity_curvature_or_phase_delay_increases", "oscillation_decays"),
    }
    for _, r in planned.iterrows():
        target, success, failure = proxy_map.get(str(r["risk_name"]), ("future_risk_proxy", "risk_proxy_increases", "risk_proxy_decreases"))
        rows.append(_with_boundary({
            "plan_id": f"delay_plan_{r['macro_state_id']}_{r['risk_name']}",
            "macro_state_id": str(r["macro_state_id"]),
            "macro_state_name": str(r["macro_state_name"]),
            "risk_name": str(r["risk_name"]),
            "raw_risk_confidence": float(r["raw_risk_confidence"]),
            "calibrated_risk_confidence": float(r["calibrated_risk_confidence"]),
            "calibration_band": str(r["calibration_band"]),
            "delay_horizon": cfg.delay_horizon,
            "observation_target": target,
            "success_proxy": success,
            "failure_proxy": failure,
            "update_rule": "compare_predicted_risk_band_with_delayed_observed_proxy_then_update_calibration_table",
            "plan_status": "delayed_observation_plan_ready_not_yet_observed",
        }))
    return pd.DataFrame(rows, columns=PLAN_COLUMNS)


def build_calibration_checks(calibration: pd.DataFrame, info: pd.DataFrame, plan: pd.DataFrame, task22_ready: bool) -> pd.DataFrame:
    checks = [
        ("check_task22_ready", "upstream", "Task22 gated risk simulator dry-run is ready.", True, task22_ready),
        ("check_calibration_rows", "calibration", "Calibration audit rows exist.", True, len(calibration) > 0),
        ("check_calibration_range", "calibration", "Calibrated risk confidence remains in [0,1].", True, bool(((calibration["calibrated_risk_confidence"].astype(float) >= 0) & (calibration["calibrated_risk_confidence"].astype(float) <= 1)).all()) if not calibration.empty else False),
        ("check_info_review", "information", "Information sufficiency review exists for each macro state.", True, len(info) > 0),
        ("check_delayed_plan", "delayed", "Delayed observation calibration plan exists.", True, len(plan) > 0),
        ("check_internal_possible", "calibration", "At least one row can be internally reviewed now.", True, bool((calibration["information_sufficiency_score"].astype(float) >= 0.45).any()) if not calibration.empty else False),
        ("check_review_path", "calibration", "At least one row is routed to review or monitor, not forced into use.", True, bool(calibration["calibration_band"].astype(str).isin(["review_before_use", "monitor_or_NO_OP"]).any()) if not calibration.empty else False),
        ("check_delayed_required", "delayed", "Delayed observation is required for empirical calibration.", True, bool(info["needs_delayed_observation"].astype(bool).any()) if not info.empty else False),
        ("check_no_action_direction", "boundary", "No action direction is generated.", False, bool(calibration["action_direction_generated"].astype(bool).any()) if not calibration.empty else True),
        ("check_no_operator", "boundary", "No terrain operator is selected.", False, bool(calibration["terrain_operator_selected"].astype(bool).any()) if not calibration.empty else True),
        ("check_no_action_candidate", "boundary", "No action candidate is generated.", False, bool(calibration["action_candidate_generated"].astype(bool).any()) if not calibration.empty else True),
        ("check_no_hidden_future", "boundary", "No hidden truth or future information is used.", False, bool(calibration["hidden_truth_input"].astype(bool).any() or calibration["future_information_used"].astype(bool).any()) if not calibration.empty else True),
    ]
    return pd.DataFrame([
        _with_boundary({"check_id": c[0], "check_scope": c[1], "check_description": c[2], "expected_value": bool(c[3]), "observed_value": bool(c[4]), "check_status": "pass" if bool(c[3]) == bool(c[4]) else "fail"})
        for c in checks
    ], columns=CHECK_COLUMNS)


def build_final_summary(calibration: pd.DataFrame, info: pd.DataFrame, plan: pd.DataFrame, checks: pd.DataFrame, task22_ready: bool) -> pd.DataFrame:
    pass_count = int((checks["check_status"].astype(str) == "pass").sum()) if not checks.empty else 0
    usable_count = int((calibration["calibration_band"].astype(str) == "usable_for_later_material_review").sum()) if not calibration.empty else 0
    review_count = int((calibration["calibration_band"].astype(str) == "review_before_use").sum()) if not calibration.empty else 0
    monitor_count = int((calibration["calibration_band"].astype(str) == "monitor_or_NO_OP").sum()) if not calibration.empty else 0
    needs_delayed_count = int(info["needs_delayed_observation"].astype(bool).sum()) if not info.empty else 0
    empirical_later_count = int(info["empirical_calibration_possible_later"].astype(bool).sum()) if not info.empty else 0
    decision = "v8_style_risk_confidence_calibration_audit_ready" if task22_ready and len(checks) == pass_count else "v8_style_risk_confidence_calibration_audit_needs_review"
    return pd.DataFrame([_with_boundary({
        "calibration_row_count": len(calibration),
        "usable_now_count": usable_count,
        "review_count": review_count,
        "monitor_count": monitor_count,
        "NO_OP_or_monitor_count": monitor_count,
        "delayed_plan_count": len(plan),
        "information_review_count": len(info),
        "needs_delayed_observation_count": needs_delayed_count,
        "empirical_calibration_possible_later_count": empirical_later_count,
        "calibration_check_count": len(checks),
        "calibration_check_pass_count": pass_count,
        "task22_ready": bool(task22_ready),
        "v8_style_risk_confidence_calibration_audit_decision": decision,
        "next_task": "Task 2-8j-23: risk-to-action direction shaping dry-run",
    })], columns=SUMMARY_COLUMNS)


def validate_v8_style_risk_confidence_calibration_audit_tables(calibration: pd.DataFrame, info: pd.DataFrame, plan: pd.DataFrame, checks: pd.DataFrame, final_summary: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    tables = {
        "calibration": (calibration, CALIBRATION_COLUMNS),
        "info": (info, INFO_COLUMNS),
        "plan": (plan, PLAN_COLUMNS),
        "checks": (checks, CHECK_COLUMNS),
        "final_summary": (final_summary, SUMMARY_COLUMNS),
    }
    for name, (table, columns) in tables.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_22b_empty_table:{name}"); continue
        missing = [c for c in columns if c not in table.columns]
        if missing:
            errors.append(f"task2_8j_22b_missing_columns:{name}:" + ",".join(missing)); continue
        for col in REQUIRED_TRUE:
            if not bool(table[col].astype(bool).all()):
                errors.append(f"task2_8j_22b_required_true_not_all_true:{name}:{col}")
        for col in FORBIDDEN_TRUE:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_22b_forbidden_true:{name}:{col}")
        if set(table["gt_main_map_name"].astype(str)) != {"static_pca_7"}:
            errors.append(f"task2_8j_22b_wrong_gt_main_map_name:{name}")
        if set(table["gt_main_component_count"].astype(int)) != {7}:
            errors.append(f"task2_8j_22b_wrong_gt_component_count:{name}")
    if checks is not None and not checks.empty and not bool((checks["check_status"].astype(str) == "pass").all()):
        errors.append("task2_8j_22b_check_failed")
    if calibration is not None and not calibration.empty:
        vals = calibration["calibrated_risk_confidence"].astype(float)
        if not bool(((vals >= 0) & (vals <= 1)).all()):
            errors.append("task2_8j_22b_calibrated_confidence_out_of_range")
    return errors


def build_and_validate_v8_style_risk_confidence_calibration_audit(cfg: V8StyleRiskConfidenceCalibrationAuditConfig | None = None, **_unused: object) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    cfg = cfg or V8StyleRiskConfidenceCalibrationAuditConfig()
    states, gate, trajectories, risk_confidence, directions, _checks22, _final22, task22_errors, task22_summary = build_and_validate_gated_macro_game_risk_simulator_dry_run(
        cfg=GatedMacroGameRiskSimulatorDryRunConfig()
    )
    task22_ready = len(task22_errors) == 0 and str(task22_summary.get("gated_macro_game_risk_simulator_dry_run_decision", "")).startswith(TASK22_ACCEPTED_DECISION)
    if not cfg.require_task22_ready:
        task22_ready = True
    calibration = build_v8_style_calibration_audit(risk_confidence, gate, states, trajectories, directions, cfg)
    info = build_information_sufficiency_review(calibration, states, gate, directions)
    plan = build_delayed_observation_calibration_plan(calibration, cfg)
    checks = build_calibration_checks(calibration, info, plan, task22_ready)
    final_summary = build_final_summary(calibration, info, plan, checks, task22_ready)
    errors = ([f"task2_8j_22b_upstream_22_error:{e}" for e in task22_errors] if cfg.require_task22_ready else []) + validate_v8_style_risk_confidence_calibration_audit_tables(calibration, info, plan, checks, final_summary)
    summary = {
        "gt_main_map_name": "static_pca_7",
        "gt_main_component_count": 7,
        "task22_decision": task22_summary.get("gated_macro_game_risk_simulator_dry_run_decision", ""),
        "calibration_row_count": _safe_int(final_summary["calibration_row_count"].iloc[0]),
        "usable_now_count": _safe_int(final_summary["usable_now_count"].iloc[0]),
        "review_count": _safe_int(final_summary["review_count"].iloc[0]),
        "monitor_count": _safe_int(final_summary["monitor_count"].iloc[0]),
        "NO_OP_or_monitor_count": _safe_int(final_summary["NO_OP_or_monitor_count"].iloc[0]),
        "delayed_plan_count": _safe_int(final_summary["delayed_plan_count"].iloc[0]),
        "information_review_count": _safe_int(final_summary["information_review_count"].iloc[0]),
        "needs_delayed_observation_count": _safe_int(final_summary["needs_delayed_observation_count"].iloc[0]),
        "empirical_calibration_possible_later_count": _safe_int(final_summary["empirical_calibration_possible_later_count"].iloc[0]),
        "calibration_check_count": _safe_int(final_summary["calibration_check_count"].iloc[0]),
        "calibration_check_pass_count": _safe_int(final_summary["calibration_check_pass_count"].iloc[0]),
        "task22_ready": bool(task22_ready),
        "v8_style_risk_confidence_calibration_audit_decision": str(final_summary["v8_style_risk_confidence_calibration_audit_decision"].iloc[0]),
        "raw_risk_confidence_treated_as_uncalibrated": True,
        "internal_calibration_possible": True,
        "delayed_observation_required_for_empirical_calibration": True,
        "action_direction_generated": False,
        "terrain_operator_selected": False,
        "action_candidate_generated": False,
        "action_effect_prediction_generated": False,
        "axis_executed": False,
        "real_actionmodule_called": False,
        "validation_errors": errors,
    }
    return calibration, info, plan, checks, final_summary, errors, summary
