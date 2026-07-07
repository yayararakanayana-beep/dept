"""Task 2-8j-23c: review-band reclassification validation plan RC1.

Defines when review-band action-direction material may later be reclassified as
usable material, while keeping boundary guards active.  This task is a validation
plan and contract only: it does not reclassify rows now, does not update
thresholds, does not select terrain operators, and does not generate action
candidates.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from .pressure_action_task2_8j_23b_review_only_cause_audit_direction_usability_threshold_sensitivity import (
    ReviewOnlyCauseAuditThresholdSensitivityConfig,
    build_and_validate_review_only_cause_audit_threshold_sensitivity,
)

TASK2_8J_23C_VERSION = "review_band_reclassification_validation_plan_rc1"
TASK23B_ACCEPTED_DECISION = "review_only_cause_audit_direction_usability_threshold_sensitivity_ready"

BOUNDARY: dict[str, Any] = {
    "task2_8j_23c_version": TASK2_8J_23C_VERSION,
    "validation_only": True,
    "plan_only": True,
    "contract_only": True,
    "review_band_reclassification_plan": True,
    "boundary_guard_retained": True,
    "no_reclassification_performed_now": True,
    "no_threshold_update_performed": True,
    "threshold_values_are_provisional": True,
    "threshold_revision_requires_validation": True,
    "safety_rules_fixed": True,
    "decision_thresholds_revisable": True,
    "source_task23b_required": True,
    "gt_main_map_name": "static_pca_7",
    "gt_main_component_count": 7,
    "action_direction_material_input_used": True,
    "review_band_may_be_reclassified_after_validation": True,
    "boundary_guard_may_not_be_removed_by_reclassification": True,
    "new_action_direction_generated": False,
    "review_band_reclassified_now": False,
    "terrain_operator_selected": False,
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
    "future_information_used": False,
    "canonical_write_performed": False,
}

REQUIRED_TRUE = [
    "validation_only", "plan_only", "contract_only", "review_band_reclassification_plan",
    "boundary_guard_retained", "no_reclassification_performed_now", "no_threshold_update_performed",
    "threshold_values_are_provisional", "threshold_revision_requires_validation", "safety_rules_fixed",
    "decision_thresholds_revisable", "source_task23b_required", "action_direction_material_input_used",
    "review_band_may_be_reclassified_after_validation", "boundary_guard_may_not_be_removed_by_reclassification",
]
FORBIDDEN_TRUE = [
    "new_action_direction_generated", "review_band_reclassified_now", "terrain_operator_selected",
    "release_rollback_audit_shaped", "action_candidate_generated", "concrete_action_generated",
    "action_effect_prediction_generated", "effect_prediction_model_executed", "expected_value_final_judgment_performed",
    "real_actionmodule_called", "axis_executed", "upper_pressure_coupled_now", "hidden_truth_input",
    "future_information_used", "canonical_write_performed",
]

POLICY_COLUMNS = list(BOUNDARY) + [
    "policy_id", "review_band_condition", "minimum_evidence_condition", "delayed_observation_condition",
    "boundary_guard_condition", "allowed_result_after_validation", "not_allowed_result", "policy_status",
]
BOUNDARY_COLUMNS = list(BOUNDARY) + [
    "boundary_guard_id", "guard_name", "retention_rule", "applies_to_risk", "allowed_after_reclassification",
    "forbidden_after_reclassification", "guard_status",
]
PLAN_COLUMNS = list(BOUNDARY) + [
    "validation_plan_id", "candidate_scope", "candidate_count", "validation_target", "success_condition",
    "failure_condition", "required_delay_observation", "minimum_validation_evidence", "plan_result_if_success",
    "plan_result_if_failure", "plan_status",
]
CANDIDATE_COLUMNS = list(BOUNDARY) + [
    "candidate_id", "macro_state_id", "macro_state_name", "risk_name", "primary_cause", "secondary_causes",
    "calibrated_risk_confidence", "v8_reliability_score", "information_sufficiency_score", "direction_clarity",
    "candidate_reclassification_path", "boundary_guard_retention", "candidate_status",
]
CHECK_COLUMNS = list(BOUNDARY) + [
    "check_id", "check_scope", "check_description", "expected_value", "observed_value", "check_status",
]
SUMMARY_COLUMNS = list(BOUNDARY) + [
    "policy_count", "boundary_guard_rule_count", "validation_plan_count", "candidate_count",
    "review_band_candidate_count", "boundary_guard_retained_count", "plan_check_count", "plan_check_pass_count",
    "task23b_ready", "review_band_reclassification_validation_plan_decision", "next_task",
]


@dataclass(frozen=True)
class ReviewBandReclassificationValidationPlanConfig:
    require_task23b_ready: bool = True


def _with_boundary(row: dict[str, Any]) -> dict[str, Any]:
    return {**BOUNDARY, **row}


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def build_review_band_reclassification_policy() -> pd.DataFrame:
    rows = [
        ("policy_01", "calibration_band_review_before_use", "internal evidence is not contradictory", "delayed proxy agrees with predicted risk family", "boundary guard remains active", "may_reclassify_to_usable_direction_material_for_later_operator_review", "direct_action_or_operator_selection"),
        ("policy_02", "v8_reliability_near_threshold", "reliability improves or remains stable after delayed observation", "false_positive not observed in delayed trace", "boundary guard remains active", "may_lower_review_bar_for_same_risk_family_after_validation", "threshold_update_without_validation"),
        ("policy_03", "boundary_guard_present", "risk direction is useful but boundary push remains forbidden", "boundary distance does not collapse after NO_OP trace", "no_boundary_push_even_if_reclassified", "usable_with_boundary_review_guard_only", "boundary_guard_removal"),
        ("policy_04", "information_sufficiency_mid_band", "missing information is recoverable by delayed observation", "future_O_t_and_relation_field_support_same_direction", "release_rollback_audit_still_required_later", "may_reclassify_after_information_recovery", "strong_use_without_audit"),
    ]
    return pd.DataFrame([
        _with_boundary({
            "policy_id": r[0], "review_band_condition": r[1], "minimum_evidence_condition": r[2],
            "delayed_observation_condition": r[3], "boundary_guard_condition": r[4],
            "allowed_result_after_validation": r[5], "not_allowed_result": r[6],
            "policy_status": "review_band_reclassification_policy_ready_no_current_reclassification",
        }) for r in rows
    ], columns=POLICY_COLUMNS)


def build_boundary_guard_retention_policy() -> pd.DataFrame:
    rows = [
        ("guard_01", "fragile_boundary_no_push", "boundary direction remains forbidden even after review-band reclassification", "boundary_fragile;reversibility_loss;all_boundary_tagged_rows", "usable_direction_material_for_later_operator_review_with_boundary_guard", "push_toward_fragile_boundary"),
        ("guard_02", "review_guard_retained", "reclassification changes usable/review label only, not safety guard", "all_review_band_rows", "operator_review_required_later", "direct_candidate_generation"),
        ("guard_03", "release_rollback_audit_later_required", "later operator stage must still shape release/rollback/audit", "all_reclassified_rows", "continue_to_operator_review_only", "concrete_action_without_release_rollback_audit"),
        ("guard_04", "NO_OP_bias_retained", "NO_OP remains available until operator and effect review pass", "all_reclassified_rows", "NO_OP_comparison_required_later", "NO_OP_suppression_by_reclassification"),
    ]
    return pd.DataFrame([
        _with_boundary({
            "boundary_guard_id": r[0], "guard_name": r[1], "retention_rule": r[2], "applies_to_risk": r[3],
            "allowed_after_reclassification": r[4], "forbidden_after_reclassification": r[5],
            "guard_status": "boundary_guard_retention_policy_ready",
        }) for r in rows
    ], columns=BOUNDARY_COLUMNS)


def build_reclassification_candidates(cause_audit: pd.DataFrame) -> pd.DataFrame:
    source = cause_audit[cause_audit["review_only_primary_cause"].astype(str) == "calibration_band_review_before_use"].copy()
    if source.empty:
        source = cause_audit.copy()
    rows: list[dict[str, Any]] = []
    for _, r in source.iterrows():
        boundary_present = "boundary_guard_present" in str(r["review_only_secondary_causes"])
        if boundary_present:
            boundary_retention = "reclassifiable_only_with_boundary_guard_retained"
        else:
            boundary_retention = "reclassifiable_with_standard_review_guard"
        rows.append(_with_boundary({
            "candidate_id": f"reclass_candidate_{r['macro_state_id']}_{r['risk_name']}",
            "macro_state_id": str(r["macro_state_id"]),
            "macro_state_name": str(r["macro_state_name"]),
            "risk_name": str(r["risk_name"]),
            "primary_cause": str(r["review_only_primary_cause"]),
            "secondary_causes": str(r["review_only_secondary_causes"]),
            "calibrated_risk_confidence": float(r["calibrated_risk_confidence"]),
            "v8_reliability_score": float(r["v8_reliability_score"]),
            "information_sufficiency_score": float(r["information_sufficiency_score"]),
            "direction_clarity": float(r["direction_clarity"]),
            "candidate_reclassification_path": "review_band_to_usable_direction_material_after_delayed_validation",
            "boundary_guard_retention": boundary_retention,
            "candidate_status": "candidate_for_validation_not_reclassified_now",
        }))
    return pd.DataFrame(rows, columns=CANDIDATE_COLUMNS)


def build_validation_plan(candidates: pd.DataFrame) -> pd.DataFrame:
    rows = [
        _with_boundary({
            "validation_plan_id": "plan_01_review_band_reclassification",
            "candidate_scope": "review_band_candidates_from_task23b",
            "candidate_count": len(candidates),
            "validation_target": "whether_review_band_rows_can_be_promoted_to_usable_direction_material",
            "success_condition": "delayed_observation_proxy_matches_predicted_risk_family_and_no_boundary_worsening",
            "failure_condition": "delayed_proxy_disagrees_or_boundary_distance_collapses_or_uncertainty_expands",
            "required_delay_observation": "future_O_t;future_relation_field;NO_OP_outcome_trace;boundary_distance_delta;actual_direction_change",
            "minimum_validation_evidence": "at_least_one_delayed_trace_per_candidate_family_before_threshold_update",
            "plan_result_if_success": "allow_candidate_policy_test_for_review_band_reclassification_without_removing_boundary_guard",
            "plan_result_if_failure": "keep_review_only_or_monitor_and_raise_information_requirement",
            "plan_status": "delayed_validation_plan_ready_no_reclassification_now",
        }),
        _with_boundary({
            "validation_plan_id": "plan_02_boundary_guard_retention",
            "candidate_scope": "boundary_guard_present_candidates",
            "candidate_count": int(candidates["boundary_guard_retention"].astype(str).str.contains("boundary_guard_retained").sum()) if not candidates.empty else 0,
            "validation_target": "confirm_boundary_guard_must_remain_even_when_review_band_reclassified",
            "success_condition": "direction_material_helpful_but_forbidden_boundary_push_remains_forbidden",
            "failure_condition": "any_reclassification_attempt_requires_boundary_push_or_suppresses_NO_OP",
            "required_delay_observation": "boundary_distance_delta;return_path_delta;uncertainty_delta",
            "minimum_validation_evidence": "no_boundary_guard_removal_allowed_without_separate_safety_review",
            "plan_result_if_success": "usable_with_boundary_review_guard_only",
            "plan_result_if_failure": "keep_boundary_related_rows_review_only",
            "plan_status": "boundary_guard_validation_plan_ready_no_guard_removal",
        }),
    ]
    return pd.DataFrame(rows, columns=PLAN_COLUMNS)


def build_plan_checks(policy: pd.DataFrame, guards: pd.DataFrame, plan: pd.DataFrame, candidates: pd.DataFrame, task23b_ready: bool) -> pd.DataFrame:
    checks = [
        ("check_task23b_ready", "upstream", "Task23b review-only cause audit is ready.", True, task23b_ready),
        ("check_policy_exists", "policy", "Review-band reclassification policy exists.", True, len(policy) > 0),
        ("check_guards_exist", "boundary", "Boundary guard retention rules exist.", True, len(guards) > 0),
        ("check_candidates_exist", "candidate", "Review-band reclassification candidates exist.", True, len(candidates) > 0),
        ("check_plan_exists", "plan", "Delayed validation plan exists.", True, len(plan) > 0),
        ("check_boundary_retained", "boundary", "Every candidate keeps a boundary/review guard path.", True, bool(candidates["boundary_guard_retention"].astype(str).str.contains("guard").all()) if not candidates.empty else False),
        ("check_no_reclassification_now", "boundary", "No review-band row is reclassified now.", False, bool(candidates["review_band_reclassified_now"].astype(bool).any()) if not candidates.empty else True),
        ("check_no_threshold_update", "threshold", "No threshold update is performed now.", False, bool(candidates["no_threshold_update_performed"].astype(bool).eq(False).any()) if not candidates.empty else True),
        ("check_no_operator", "boundary", "No terrain operator is selected.", False, bool(candidates["terrain_operator_selected"].astype(bool).any()) if not candidates.empty else True),
        ("check_no_action_candidate", "boundary", "No action candidate is generated.", False, bool(candidates["action_candidate_generated"].astype(bool).any()) if not candidates.empty else True),
        ("check_no_hidden_future", "boundary", "No hidden truth or future information is used.", False, bool(candidates["hidden_truth_input"].astype(bool).any() or candidates["future_information_used"].astype(bool).any()) if not candidates.empty else True),
    ]
    return pd.DataFrame([
        _with_boundary({"check_id": c[0], "check_scope": c[1], "check_description": c[2], "expected_value": bool(c[3]), "observed_value": bool(c[4]), "check_status": "pass" if bool(c[3]) == bool(c[4]) else "fail"})
        for c in checks
    ], columns=CHECK_COLUMNS)


def build_final_summary(policy: pd.DataFrame, guards: pd.DataFrame, plan: pd.DataFrame, candidates: pd.DataFrame, checks: pd.DataFrame, task23b_ready: bool) -> pd.DataFrame:
    pass_count = int((checks["check_status"].astype(str) == "pass").sum()) if not checks.empty else 0
    decision = "review_band_reclassification_validation_plan_ready" if task23b_ready and len(checks) == pass_count else "review_band_reclassification_validation_plan_needs_review"
    return pd.DataFrame([_with_boundary({
        "policy_count": len(policy),
        "boundary_guard_rule_count": len(guards),
        "validation_plan_count": len(plan),
        "candidate_count": len(candidates),
        "review_band_candidate_count": int((candidates["primary_cause"].astype(str) == "calibration_band_review_before_use").sum()) if not candidates.empty else 0,
        "boundary_guard_retained_count": int(candidates["boundary_guard_retention"].astype(str).str.contains("guard").sum()) if not candidates.empty else 0,
        "plan_check_count": len(checks),
        "plan_check_pass_count": pass_count,
        "task23b_ready": bool(task23b_ready),
        "review_band_reclassification_validation_plan_decision": decision,
        "next_task": "Task 2-8j-24: terrain operator selection dry-run",
    })], columns=SUMMARY_COLUMNS)


def validate_review_band_reclassification_validation_plan_tables(policy: pd.DataFrame, guards: pd.DataFrame, plan: pd.DataFrame, candidates: pd.DataFrame, checks: pd.DataFrame, final_summary: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    tables = {
        "policy": (policy, POLICY_COLUMNS),
        "guards": (guards, BOUNDARY_COLUMNS),
        "plan": (plan, PLAN_COLUMNS),
        "candidates": (candidates, CANDIDATE_COLUMNS),
        "checks": (checks, CHECK_COLUMNS),
        "final_summary": (final_summary, SUMMARY_COLUMNS),
    }
    for name, (table, columns) in tables.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_23c_empty_table:{name}"); continue
        missing = [c for c in columns if c not in table.columns]
        if missing:
            errors.append(f"task2_8j_23c_missing_columns:{name}:" + ",".join(missing)); continue
        for col in REQUIRED_TRUE:
            if not bool(table[col].astype(bool).all()):
                errors.append(f"task2_8j_23c_required_true_not_all_true:{name}:{col}")
        for col in FORBIDDEN_TRUE:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_23c_forbidden_true:{name}:{col}")
        if set(table["gt_main_map_name"].astype(str)) != {"static_pca_7"}:
            errors.append(f"task2_8j_23c_wrong_gt_main_map_name:{name}")
        if set(table["gt_main_component_count"].astype(int)) != {7}:
            errors.append(f"task2_8j_23c_wrong_gt_component_count:{name}")
    if checks is not None and not checks.empty and not bool((checks["check_status"].astype(str) == "pass").all()):
        errors.append("task2_8j_23c_check_failed")
    if candidates is not None and not candidates.empty:
        if bool(candidates["review_band_reclassified_now"].astype(bool).any()):
            errors.append("task2_8j_23c_reclassification_attempted")
        if not bool(candidates["boundary_guard_retention"].astype(str).str.contains("guard").all()):
            errors.append("task2_8j_23c_boundary_guard_not_retained")
    return errors


def build_and_validate_review_band_reclassification_validation_plan(cfg: ReviewBandReclassificationValidationPlanConfig | None = None, **_unused: object) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    cfg = cfg or ReviewBandReclassificationValidationPlanConfig()
    cause_audit, _cause_summary, _sensitivity, _checks23b, _final23b, task23b_errors, task23b_summary = build_and_validate_review_only_cause_audit_threshold_sensitivity(
        cfg=ReviewOnlyCauseAuditThresholdSensitivityConfig()
    )
    task23b_ready = len(task23b_errors) == 0 and str(task23b_summary.get("review_only_cause_audit_direction_usability_threshold_sensitivity_decision", "")).startswith(TASK23B_ACCEPTED_DECISION)
    if not cfg.require_task23b_ready:
        task23b_ready = True
    policy = build_review_band_reclassification_policy()
    guards = build_boundary_guard_retention_policy()
    candidates = build_reclassification_candidates(cause_audit)
    plan = build_validation_plan(candidates)
    checks = build_plan_checks(policy, guards, plan, candidates, task23b_ready)
    final_summary = build_final_summary(policy, guards, plan, candidates, checks, task23b_ready)
    errors: list[str] = []
    if cfg.require_task23b_ready:
        errors += [f"task2_8j_23c_upstream_23b_error:{e}" for e in task23b_errors]
    errors += validate_review_band_reclassification_validation_plan_tables(policy, guards, plan, candidates, checks, final_summary)
    summary = {
        "gt_main_map_name": "static_pca_7",
        "gt_main_component_count": 7,
        "task23b_decision": task23b_summary.get("review_only_cause_audit_direction_usability_threshold_sensitivity_decision", ""),
        "policy_count": _safe_int(final_summary["policy_count"].iloc[0]),
        "boundary_guard_rule_count": _safe_int(final_summary["boundary_guard_rule_count"].iloc[0]),
        "validation_plan_count": _safe_int(final_summary["validation_plan_count"].iloc[0]),
        "candidate_count": _safe_int(final_summary["candidate_count"].iloc[0]),
        "review_band_candidate_count": _safe_int(final_summary["review_band_candidate_count"].iloc[0]),
        "boundary_guard_retained_count": _safe_int(final_summary["boundary_guard_retained_count"].iloc[0]),
        "plan_check_count": _safe_int(final_summary["plan_check_count"].iloc[0]),
        "plan_check_pass_count": _safe_int(final_summary["plan_check_pass_count"].iloc[0]),
        "task23b_ready": bool(task23b_ready),
        "review_band_reclassification_validation_plan_decision": str(final_summary["review_band_reclassification_validation_plan_decision"].iloc[0]),
        "review_band_may_be_reclassified_after_validation": True,
        "boundary_guard_may_not_be_removed_by_reclassification": True,
        "no_reclassification_performed_now": True,
        "no_threshold_update_performed": True,
        "new_action_direction_generated": False,
        "terrain_operator_selected": False,
        "action_candidate_generated": False,
        "action_effect_prediction_generated": False,
        "axis_executed": False,
        "real_actionmodule_called": False,
        "validation_errors": errors,
    }
    return policy, guards, plan, candidates, checks, final_summary, errors, summary
