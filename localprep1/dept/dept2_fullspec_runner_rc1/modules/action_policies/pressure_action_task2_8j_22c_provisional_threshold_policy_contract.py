"""Task 2-8j-22c: provisional threshold policy contract RC1.

Separates fixed safety rules from revisable decision thresholds before
risk-to-action direction shaping.  The contract prevents Task22b calibration
bands from becoming absolute rules.

Safety boundaries are fixed.  Usable / review / monitor thresholds are
provisional, validation-revisable, system-state-sensitive, and may later be
coupled to upper pressure as threshold modulation only, not as direct action.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from .pressure_action_task2_8j_22b_v8_style_risk_confidence_calibration_audit import (
    V8StyleRiskConfidenceCalibrationAuditConfig,
    build_and_validate_v8_style_risk_confidence_calibration_audit,
)

TASK2_8J_22C_VERSION = "provisional_threshold_policy_contract_rc1"
TASK22B_ACCEPTED_DECISION = "v8_style_risk_confidence_calibration_audit_ready"

BOUNDARY: dict[str, Any] = {
    "task2_8j_22c_version": TASK2_8J_22C_VERSION,
    "validation_only": True,
    "contract_only": True,
    "threshold_policy_only": True,
    "safety_rules_fixed": True,
    "decision_thresholds_revisable": True,
    "threshold_values_are_provisional": True,
    "threshold_revision_requires_validation": True,
    "system_state_sensitive_thresholds": True,
    "future_upper_pressure_threshold_coupling_note": True,
    "upper_pressure_coupling_is_future_only": True,
    "upper_pressure_may_modulate_thresholds_not_direct_action": True,
    "source_task22b_required": True,
    "gt_main_map_name": "static_pca_7",
    "gt_main_component_count": 7,
    "raw_risk_confidence_treated_as_uncalibrated": True,
    "semantic_recipe_primary_key_forbidden": True,
    "terrain_information_primary_required": True,
    "risk_label_used_only_for_evaluation": True,
    "NO_OP_baseline_required": True,
    "current_threshold_update_performed": False,
    "upper_pressure_coupled_now": False,
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
    "validation_only", "contract_only", "threshold_policy_only", "safety_rules_fixed", "decision_thresholds_revisable",
    "threshold_values_are_provisional", "threshold_revision_requires_validation", "system_state_sensitive_thresholds",
    "future_upper_pressure_threshold_coupling_note", "upper_pressure_coupling_is_future_only",
    "upper_pressure_may_modulate_thresholds_not_direct_action", "source_task22b_required",
    "raw_risk_confidence_treated_as_uncalibrated", "semantic_recipe_primary_key_forbidden",
    "terrain_information_primary_required", "risk_label_used_only_for_evaluation", "NO_OP_baseline_required",
]
FORBIDDEN_TRUE = [
    "current_threshold_update_performed", "upper_pressure_coupled_now", "action_direction_generated", "terrain_operator_selected",
    "release_rollback_audit_shaped", "action_candidate_generated", "concrete_action_generated",
    "action_effect_prediction_generated", "effect_prediction_model_executed", "expected_value_final_judgment_performed",
    "real_actionmodule_called", "axis_executed", "hidden_truth_input", "future_information_used", "canonical_write_performed",
]

SAFETY_COLUMNS = list(BOUNDARY) + [
    "safety_rule_id", "safety_rule_name", "fixed_status", "rule_description", "cannot_be_overridden_by",
    "applies_to", "safety_status",
]
THRESHOLD_COLUMNS = list(BOUNDARY) + [
    "threshold_id", "threshold_name", "current_value", "threshold_role", "revisable_status", "revision_sources",
    "allowed_revision_direction", "safety_floor_or_ceiling", "validation_required", "threshold_status",
]
STATE_COLUMNS = list(BOUNDARY) + [
    "state_policy_id", "system_state_condition", "threshold_modulation_target", "modulation_direction",
    "reason", "requires_evidence", "state_policy_status",
]
UPPER_COLUMNS = list(BOUNDARY) + [
    "upper_coupling_id", "upper_pressure_family", "risk_family", "possible_threshold_effect", "coupling_mode",
    "allowed_now", "future_condition", "upper_coupling_status",
]
CHECK_COLUMNS = list(BOUNDARY) + [
    "check_id", "check_scope", "check_description", "expected_value", "observed_value", "check_status",
]
SUMMARY_COLUMNS = list(BOUNDARY) + [
    "safety_rule_count", "provisional_threshold_count", "system_state_policy_count", "future_upper_pressure_coupling_count",
    "fixed_safety_count", "revisable_threshold_count", "upper_pressure_future_only_count", "policy_check_count", "policy_check_pass_count",
    "task22b_ready", "provisional_threshold_policy_contract_decision", "next_task",
]


@dataclass(frozen=True)
class ProvisionalThresholdPolicyContractConfig:
    require_task22b_ready: bool = True


def _with_boundary(row: dict[str, Any]) -> dict[str, Any]:
    return {**BOUNDARY, **row}


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def build_safety_fixed_rules() -> pd.DataFrame:
    rows = [
        ("safety_01", "hidden_truth_future_information_forbidden", "fixed", "hidden truth and future information must never be used as runtime input", "threshold_revision;upper_pressure;validation_gain", "all_threshold_decisions"),
        ("safety_02", "no_direct_action_from_risk_confidence", "fixed", "risk confidence cannot directly create action candidates", "high_confidence;upper_pressure", "risk_to_action_path"),
        ("safety_03", "review_before_action_candidate", "fixed", "action material must pass review before becoming a candidate", "threshold_lowering;operator_priority", "candidate_generation"),
        ("safety_04", "release_rollback_audit_required", "fixed", "release, rollback, and audit conditions are required before concrete action", "system_state;urgency", "action_material"),
        ("safety_05", "high_uncertainty_blocks_strong_use", "fixed", "high uncertainty routes to review / monitor, not strong use", "raw_risk_confidence", "calibration_use"),
        ("safety_06", "fragile_boundary_no_push", "fixed", "fragile boundary direction must not be strengthened", "upper_pressure;local_operator", "direction_shaping"),
        ("safety_07", "threshold_update_cannot_weaken_safety", "fixed", "validation may revise decision thresholds but cannot weaken safety boundaries", "empirical_gain;upper_pressure", "threshold_update"),
    ]
    return pd.DataFrame([
        _with_boundary({
            "safety_rule_id": r[0], "safety_rule_name": r[1], "fixed_status": r[2], "rule_description": r[3],
            "cannot_be_overridden_by": r[4], "applies_to": r[5], "safety_status": "safety_rule_fixed",
        }) for r in rows
    ], columns=SAFETY_COLUMNS)


def build_provisional_threshold_policy() -> pd.DataFrame:
    rows = [
        ("thr_01", "usable_threshold", 0.66, "calibrated risk confidence enters later material review", "provisional_revisable", "delayed_observation;calibration_error;system_state;future_upper_pressure", "up_or_down_with_validation", "must_not_bypass_safety_rules"),
        ("thr_02", "review_threshold", 0.50, "calibrated risk confidence enters review", "provisional_revisable", "false_positive_rate;false_negative_rate;system_state", "up_or_down_with_validation", "must_not_bypass_review_before_candidate"),
        ("thr_03", "monitor_threshold", 0.00, "below review remains monitor or NO_OP", "provisional_revisable", "delayed_observation;low_risk_negative_control", "up_or_down_with_validation", "must_not_turn_low_info_into_action"),
        ("thr_04", "minimum_direction_clarity", 0.48, "direction must be clear enough for later action-direction shaping", "provisional_revisable", "direction_audit;side_effect_audit", "up_or_down_with_validation", "fragile_boundary_no_push"),
        ("thr_05", "minimum_information_sufficiency", 0.45, "enough internal information for calibration review", "provisional_revisable", "information_sufficiency_review;delayed_observation", "up_or_down_with_validation", "hidden_future_forbidden"),
        ("thr_06", "uncertainty_penalty_weight", 0.18, "penalty applied to raw risk confidence", "provisional_revisable", "calibration_error;system_state", "up_or_down_with_validation", "high_uncertainty_blocks_strong_use"),
        ("thr_07", "gate_open_threshold", 0.45, "observation gate threshold for simulator dry-run", "provisional_revisable", "negative_control;missed_risk_review", "up_or_down_with_validation", "simulator_runs_only_when_gate_open"),
    ]
    return pd.DataFrame([
        _with_boundary({
            "threshold_id": r[0], "threshold_name": r[1], "current_value": float(r[2]), "threshold_role": r[3],
            "revisable_status": r[4], "revision_sources": r[5], "allowed_revision_direction": r[6],
            "safety_floor_or_ceiling": r[7], "validation_required": True, "threshold_status": "provisional_threshold_not_absolute",
        }) for r in rows
    ], columns=THRESHOLD_COLUMNS)


def build_system_state_threshold_modulation_policy() -> pd.DataFrame:
    rows = [
        ("state_01", "fragile_boundary_or_low_boundary_distance", "boundary_fragile;reversibility_loss", "lower_review_threshold_but_keep_no_push_safety", "early review may be needed near irreversible boundary"),
        ("state_02", "high_reversibility_and_wide_escape_path", "relation_lock;resource_pressure", "raise_usable_threshold_or_prefer_monitor", "system can absorb risk without immediate action material"),
        ("state_03", "high_uncertainty_or_low_information_sufficiency", "all_risks", "raise_usable_threshold_and_route_to_review", "confidence may be misleading"),
        ("state_04", "oscillation_dominant_system", "oscillation", "lower_review_threshold_for_oscillation_only", "phase delay can amplify quickly"),
        ("state_05", "stable_NO_OP_recovery_observed", "all_risks", "raise_usable_threshold_and_prefer_NO_OP", "natural recovery should not be disturbed"),
        ("state_06", "repeated_missed_risk_after_delay", "matched_risk_family", "lower_relevant_review_threshold", "false negatives require earlier review"),
    ]
    return pd.DataFrame([
        _with_boundary({
            "state_policy_id": r[0], "system_state_condition": r[1], "threshold_modulation_target": r[2],
            "modulation_direction": r[3], "reason": r[4], "requires_evidence": True,
            "state_policy_status": "system_state_threshold_modulation_policy_ready",
        }) for r in rows
    ], columns=STATE_COLUMNS)


def build_future_upper_pressure_threshold_coupling_note() -> pd.DataFrame:
    rows = [
        ("upper_01", "irreversibility_avoidance_pressure", "reversibility_loss;boundary_fragile", "lower_review_threshold_for_irreversibility_risks", "threshold_modulation_only", False, "requires_validated_upper_pressure_route_and_threshold_audit"),
        ("upper_02", "exploration_preservation_pressure", "relation_lock", "lower_review_threshold_for_lock_risk_but_keep_overintervention_guard", "threshold_modulation_only", False, "requires_validated_upper_pressure_route_and_side_effect_audit"),
        ("upper_03", "stability_pressure", "oscillation;resource_pressure", "lower_review_threshold_for_instability_risks", "threshold_modulation_only", False, "requires_validated_upper_pressure_route_and_NO_OP_comparison"),
        ("upper_04", "efficiency_or_low_intervention_pressure", "all_risks", "raise_usable_threshold_when_NO_OP_recovery_is_likely", "threshold_modulation_only", False, "requires_delayed_observation_calibration"),
        ("upper_05", "uncertainty_pressure", "all_risks", "raise_usable_threshold_and_force_review_when_confidence_low", "threshold_modulation_only", False, "requires_information_sufficiency_review"),
    ]
    return pd.DataFrame([
        _with_boundary({
            "upper_coupling_id": r[0], "upper_pressure_family": r[1], "risk_family": r[2],
            "possible_threshold_effect": r[3], "coupling_mode": r[4], "allowed_now": bool(r[5]),
            "future_condition": r[6], "upper_coupling_status": "future_note_only_not_currently_coupled",
        }) for r in rows
    ], columns=UPPER_COLUMNS)


def build_policy_checks(safety: pd.DataFrame, thresholds: pd.DataFrame, state_policy: pd.DataFrame, upper: pd.DataFrame, task22b_ready: bool) -> pd.DataFrame:
    checks = [
        ("check_task22b_ready", "upstream", "Task22b calibration audit is ready.", True, task22b_ready),
        ("check_safety_fixed", "safety", "Every safety rule is fixed.", True, bool((safety["fixed_status"].astype(str) == "fixed").all()) if not safety.empty else False),
        ("check_thresholds_revisable", "threshold", "Every decision threshold is provisional and revisable.", True, bool(thresholds["revisable_status"].astype(str).str.contains("revisable").all()) if not thresholds.empty else False),
        ("check_validation_required", "threshold", "Every threshold revision requires validation.", True, bool(thresholds["validation_required"].astype(bool).all()) if not thresholds.empty else False),
        ("check_state_sensitive", "system_state", "System-state modulation policies exist.", True, len(state_policy) > 0),
        ("check_upper_future_only", "upper_pressure", "Upper pressure coupling is future note only.", False, bool(upper["allowed_now"].astype(bool).any()) if not upper.empty else True),
        ("check_upper_threshold_only", "upper_pressure", "Upper pressure coupling only modulates thresholds, not direct action.", True, bool((upper["coupling_mode"].astype(str) == "threshold_modulation_only").all()) if not upper.empty else False),
        ("check_no_current_threshold_update", "boundary", "No threshold update is performed in this task.", False, bool(thresholds["current_threshold_update_performed"].astype(bool).any()) if not thresholds.empty else True),
        ("check_no_action_direction", "boundary", "No action direction is generated.", False, bool(thresholds["action_direction_generated"].astype(bool).any()) if not thresholds.empty else True),
        ("check_no_operator", "boundary", "No terrain operator is selected.", False, bool(thresholds["terrain_operator_selected"].astype(bool).any()) if not thresholds.empty else True),
        ("check_no_action_candidate", "boundary", "No action candidate is generated.", False, bool(thresholds["action_candidate_generated"].astype(bool).any()) if not thresholds.empty else True),
        ("check_no_hidden_future", "boundary", "No hidden truth or future information is used.", False, bool(thresholds["hidden_truth_input"].astype(bool).any() or thresholds["future_information_used"].astype(bool).any()) if not thresholds.empty else True),
    ]
    return pd.DataFrame([
        _with_boundary({"check_id": c[0], "check_scope": c[1], "check_description": c[2], "expected_value": bool(c[3]), "observed_value": bool(c[4]), "check_status": "pass" if bool(c[3]) == bool(c[4]) else "fail"})
        for c in checks
    ], columns=CHECK_COLUMNS)


def build_final_summary(safety: pd.DataFrame, thresholds: pd.DataFrame, state_policy: pd.DataFrame, upper: pd.DataFrame, checks: pd.DataFrame, task22b_ready: bool) -> pd.DataFrame:
    pass_count = int((checks["check_status"].astype(str) == "pass").sum()) if not checks.empty else 0
    decision = "provisional_threshold_policy_contract_ready" if task22b_ready and len(checks) == pass_count else "provisional_threshold_policy_contract_needs_review"
    return pd.DataFrame([_with_boundary({
        "safety_rule_count": len(safety),
        "provisional_threshold_count": len(thresholds),
        "system_state_policy_count": len(state_policy),
        "future_upper_pressure_coupling_count": len(upper),
        "fixed_safety_count": int((safety["fixed_status"].astype(str) == "fixed").sum()) if not safety.empty else 0,
        "revisable_threshold_count": int(thresholds["revisable_status"].astype(str).str.contains("revisable").sum()) if not thresholds.empty else 0,
        "upper_pressure_future_only_count": int((~upper["allowed_now"].astype(bool)).sum()) if not upper.empty else 0,
        "policy_check_count": len(checks),
        "policy_check_pass_count": pass_count,
        "task22b_ready": bool(task22b_ready),
        "provisional_threshold_policy_contract_decision": decision,
        "next_task": "Task 2-8j-23: risk-to-action direction shaping dry-run",
    })], columns=SUMMARY_COLUMNS)


def validate_provisional_threshold_policy_contract_tables(safety: pd.DataFrame, thresholds: pd.DataFrame, state_policy: pd.DataFrame, upper: pd.DataFrame, checks: pd.DataFrame, final_summary: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    tables = {
        "safety": (safety, SAFETY_COLUMNS),
        "thresholds": (thresholds, THRESHOLD_COLUMNS),
        "state_policy": (state_policy, STATE_COLUMNS),
        "upper": (upper, UPPER_COLUMNS),
        "checks": (checks, CHECK_COLUMNS),
        "final_summary": (final_summary, SUMMARY_COLUMNS),
    }
    for name, (table, columns) in tables.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_22c_empty_table:{name}"); continue
        missing = [c for c in columns if c not in table.columns]
        if missing:
            errors.append(f"task2_8j_22c_missing_columns:{name}:" + ",".join(missing)); continue
        for col in REQUIRED_TRUE:
            if not bool(table[col].astype(bool).all()):
                errors.append(f"task2_8j_22c_required_true_not_all_true:{name}:{col}")
        for col in FORBIDDEN_TRUE:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_22c_forbidden_true:{name}:{col}")
        if set(table["gt_main_map_name"].astype(str)) != {"static_pca_7"}:
            errors.append(f"task2_8j_22c_wrong_gt_main_map_name:{name}")
        if set(table["gt_main_component_count"].astype(int)) != {7}:
            errors.append(f"task2_8j_22c_wrong_gt_component_count:{name}")
    if checks is not None and not checks.empty and not bool((checks["check_status"].astype(str) == "pass").all()):
        errors.append("task2_8j_22c_check_failed")
    if thresholds is not None and not thresholds.empty:
        if not bool(thresholds["validation_required"].astype(bool).all()):
            errors.append("task2_8j_22c_threshold_revision_without_validation")
        if not bool(thresholds["revisable_status"].astype(str).str.contains("revisable").all()):
            errors.append("task2_8j_22c_threshold_not_revisable")
    if upper is not None and not upper.empty:
        if bool(upper["allowed_now"].astype(bool).any()):
            errors.append("task2_8j_22c_upper_pressure_coupled_now")
        if not bool((upper["coupling_mode"].astype(str) == "threshold_modulation_only").all()):
            errors.append("task2_8j_22c_upper_pressure_not_threshold_only")
    return errors


def build_and_validate_provisional_threshold_policy_contract(cfg: ProvisionalThresholdPolicyContractConfig | None = None, **_unused: object) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    cfg = cfg or ProvisionalThresholdPolicyContractConfig()
    _cal, _info, _plan, _checks22b, _final22b, task22b_errors, task22b_summary = build_and_validate_v8_style_risk_confidence_calibration_audit(
        cfg=V8StyleRiskConfidenceCalibrationAuditConfig()
    )
    task22b_ready = len(task22b_errors) == 0 and str(task22b_summary.get("v8_style_risk_confidence_calibration_audit_decision", "")).startswith(TASK22B_ACCEPTED_DECISION)
    if not cfg.require_task22b_ready:
        task22b_ready = True
    safety = build_safety_fixed_rules()
    thresholds = build_provisional_threshold_policy()
    state_policy = build_system_state_threshold_modulation_policy()
    upper = build_future_upper_pressure_threshold_coupling_note()
    checks = build_policy_checks(safety, thresholds, state_policy, upper, task22b_ready)
    final_summary = build_final_summary(safety, thresholds, state_policy, upper, checks, task22b_ready)
    errors = ([f"task2_8j_22c_upstream_22b_error:{e}" for e in task22b_errors] if cfg.require_task22b_ready else []) + validate_provisional_threshold_policy_contract_tables(safety, thresholds, state_policy, upper, checks, final_summary)
    summary = {
        "gt_main_map_name": "static_pca_7",
        "gt_main_component_count": 7,
        "task22b_decision": task22b_summary.get("v8_style_risk_confidence_calibration_audit_decision", ""),
        "safety_rule_count": _safe_int(final_summary["safety_rule_count"].iloc[0]),
        "provisional_threshold_count": _safe_int(final_summary["provisional_threshold_count"].iloc[0]),
        "system_state_policy_count": _safe_int(final_summary["system_state_policy_count"].iloc[0]),
        "future_upper_pressure_coupling_count": _safe_int(final_summary["future_upper_pressure_coupling_count"].iloc[0]),
        "fixed_safety_count": _safe_int(final_summary["fixed_safety_count"].iloc[0]),
        "revisable_threshold_count": _safe_int(final_summary["revisable_threshold_count"].iloc[0]),
        "upper_pressure_future_only_count": _safe_int(final_summary["upper_pressure_future_only_count"].iloc[0]),
        "policy_check_count": _safe_int(final_summary["policy_check_count"].iloc[0]),
        "policy_check_pass_count": _safe_int(final_summary["policy_check_pass_count"].iloc[0]),
        "task22b_ready": bool(task22b_ready),
        "provisional_threshold_policy_contract_decision": str(final_summary["provisional_threshold_policy_contract_decision"].iloc[0]),
        "safety_rules_fixed": True,
        "decision_thresholds_revisable": True,
        "threshold_values_are_provisional": True,
        "threshold_revision_requires_validation": True,
        "system_state_sensitive_thresholds": True,
        "future_upper_pressure_threshold_coupling_note": True,
        "upper_pressure_coupling_is_future_only": True,
        "upper_pressure_may_modulate_thresholds_not_direct_action": True,
        "current_threshold_update_performed": False,
        "upper_pressure_coupled_now": False,
        "action_direction_generated": False,
        "terrain_operator_selected": False,
        "action_candidate_generated": False,
        "action_effect_prediction_generated": False,
        "axis_executed": False,
        "real_actionmodule_called": False,
        "validation_errors": errors,
    }
    return safety, thresholds, state_policy, upper, checks, final_summary, errors, summary
