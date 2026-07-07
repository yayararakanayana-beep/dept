"""Task 2-8j-24c: provisional action-module design lock RC1.

Builds a provisional action-module design from the validated Task24b evidence.

This is a design lock, not a final deployment freeze.  It fixes the current
provisional action-module scope for the three validated risk families and keeps
boundary_fragile and resource_pressure outside adoption.

The locked provisional design is:

- relation_lock -> lock_relief / soft_resistance, fixed_medium, wait 0-2
- oscillation -> oscillation_damping / damping, fixed_medium, wait 0-2
- reversibility_loss -> return_path_support / reversibility_support, fixed_medium, wait 0-2

NO_OP remains a formal fallback.  v2 future information remains scoring-only and
is not a runtime input.  No real ActionModule is called, no axis is executed, no
canonical parameter write is performed, and no deployment threshold is frozen.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from .pressure_action_task2_8j_24b6_final_triage_before_24c import (
    build_and_validate_final_triage_before_24c,
)

TASK2_8J_24C_VERSION = "provisional_action_module_design_lock_rc1"
READY_RISKS = ("relation_lock", "oscillation", "reversibility_loss")
EXCLUDED_RISKS = ("boundary_fragile", "resource_pressure")

BOUNDARY: dict[str, Any] = {
    "task2_8j_24c_version": TASK2_8J_24C_VERSION,
    "provisional_design_lock": True,
    "not_final_deployment_freeze": True,
    "source_task24b6_required": True,
    "uses_task24b_validation_evidence": True,
    "runtime_scoring_information_separation_inherited": True,
    "v2_used_for_scoring_only": True,
    "NO_OP_used_for_scoring_only": True,
    "NO_OP_retained_as_formal_fallback": True,
    "ready_risks_only": True,
    "excluded_risks_blocked_from_adoption": True,
    "fixed_medium_primary_intensity": True,
    "wait_0_2_primary_window": True,
    "gt_main_map_name": "static_pca_7",
    "gt_main_component_count": 7,
    "threshold_freeze_allowed_now": False,
    "deployment_ready_claimed": False,
    "canonical_write_performed": False,
    "real_actionmodule_called": False,
    "axis_executed": False,
    "v2_future_used_by_runtime": False,
    "validation_score_used_as_runtime_input": False,
}

REQUIRED_TRUE = [
    "provisional_design_lock", "not_final_deployment_freeze", "source_task24b6_required",
    "uses_task24b_validation_evidence", "runtime_scoring_information_separation_inherited",
    "v2_used_for_scoring_only", "NO_OP_used_for_scoring_only", "NO_OP_retained_as_formal_fallback",
    "ready_risks_only", "excluded_risks_blocked_from_adoption", "fixed_medium_primary_intensity",
    "wait_0_2_primary_window",
]
FORBIDDEN_TRUE = [
    "threshold_freeze_allowed_now", "deployment_ready_claimed", "canonical_write_performed",
    "real_actionmodule_called", "axis_executed", "v2_future_used_by_runtime", "validation_score_used_as_runtime_input",
]

DESIGN_COLUMNS = list(BOUNDARY) + [
    "design_id", "design_scope", "design_status", "ready_risk_count", "excluded_risk_count",
    "primary_intensity_schedule", "primary_wait_window", "formal_fallback", "design_reason",
]
POLICY_COLUMNS = list(BOUNDARY) + [
    "policy_rule_id", "risk_name", "operator_family", "operator_name", "intensity_schedule",
    "wait_window", "minimum_mean_ev_reference", "maximum_large_loss_rate_reference", "admission_status",
    "runtime_allowed_inputs", "runtime_forbidden_inputs", "policy_rule_reason",
]
GATE_COLUMNS = list(BOUNDARY) + [
    "gate_rule_id", "gate_order", "gate_type", "gate_condition", "gate_action", "gate_status",
]
FALLBACK_COLUMNS = list(BOUNDARY) + [
    "fallback_rule_id", "fallback_condition", "fallback_action", "fallback_reason", "fallback_status",
]
EXCLUSION_COLUMNS = list(BOUNDARY) + [
    "excluded_rule_id", "risk_name", "exclusion_class", "interim_allowed_state", "required_next_work", "exclusion_reason",
]
CHECK_COLUMNS = list(BOUNDARY) + ["check_id", "check_scope", "check_description", "expected_value", "observed_value", "check_status"]
SUMMARY_COLUMNS = list(BOUNDARY) + [
    "source_task24b6_ready", "provisional_policy_rule_count", "gate_rule_count", "fallback_rule_count",
    "excluded_rule_count", "ready_risk_scope", "excluded_risk_scope", "primary_intensity_schedule",
    "primary_wait_window", "validation_check_count", "validation_check_pass_count",
    "task24c_provisional_design_decision", "next_task",
]


@dataclass(frozen=True)
class ProvisionalActionModuleDesignLockConfig:
    require_task24b6_ready: bool = True
    min_ev_reference: float = 0.20
    max_large_loss_reference: float = 0.03


def _with_boundary(row: dict[str, Any]) -> dict[str, Any]:
    return {**BOUNDARY, **row}


def _safe_float(v: object, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def _operator_pair(risk: str) -> tuple[str, str]:
    mapping = {
        "relation_lock": ("lock_relief", "soft_resistance"),
        "oscillation": ("oscillation_damping", "damping"),
        "reversibility_loss": ("return_path_support", "reversibility_support"),
    }
    return mapping[str(risk)]


def _lookup_metric(matrix: pd.DataFrame, risk: str, column: str, default: float = 0.0) -> float:
    if matrix is None or matrix.empty or column not in matrix.columns:
        return float(default)
    row = matrix[matrix["risk_name"].astype(str).eq(str(risk))]
    if row.empty:
        return float(default)
    return _safe_float(row.iloc[0][column], default)


def build_design_contract(source_ready: bool) -> pd.DataFrame:
    status = "provisional_action_module_design_locked" if source_ready else "provisional_action_module_design_needs_upstream_review"
    return pd.DataFrame([_with_boundary({
        "design_id": "task24c_provisional_action_module_design_lock",
        "design_scope": "ready_risks_only_with_NO_OP_fallback_and_exclusion_tracks",
        "design_status": status,
        "ready_risk_count": len(READY_RISKS),
        "excluded_risk_count": len(EXCLUDED_RISKS),
        "primary_intensity_schedule": "fixed_medium",
        "primary_wait_window": "wait_0_2",
        "formal_fallback": "NO_OP",
        "design_reason": "Task24b4/24b5/24b6 support fixed_medium early-window provisional policy for three risks only",
    })], columns=DESIGN_COLUMNS)


def build_policy_rules(matrix_b6: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for risk in READY_RISKS:
        family, operator = _operator_pair(risk)
        ev = _lookup_metric(matrix_b6, risk, "fixed_medium_mean_ev")
        large = _lookup_metric(matrix_b6, risk, "fixed_medium_large_loss_rate", 1.0)
        rows.append(_with_boundary({
            "policy_rule_id": f"policy_{risk}_fixed_medium_wait_0_2",
            "risk_name": risk,
            "operator_family": family,
            "operator_name": operator,
            "intensity_schedule": "fixed_medium",
            "wait_window": "wait_0_2",
            "minimum_mean_ev_reference": round(ev, 6),
            "maximum_large_loss_rate_reference": round(large, 6),
            "admission_status": "provisional_policy_admitted_for_design_lock",
            "runtime_allowed_inputs": "risk_name,operator_name,wait_step,prepared_action_material,runtime_margin_proxies",
            "runtime_forbidden_inputs": "v2_future,NO_OP_future,observed_outcome,negative_control_outcome,validation_score",
            "policy_rule_reason": "validated_as_ready_for_task24c_by_final_triage_before_24c",
        }))
    return pd.DataFrame(rows, columns=POLICY_COLUMNS)


def build_gate_rules() -> pd.DataFrame:
    rules = [
        (1, "scope_gate", "risk_name in {relation_lock, oscillation, reversibility_loss}", "continue_to_policy_gate"),
        (2, "exclusion_gate", "risk_name in {boundary_fragile, resource_pressure}", "route_to_review_or_redesign_track_and_prefer_NO_OP"),
        (3, "timing_gate", "wait_step in 0..2", "allow_provisional_policy_evaluation"),
        (4, "late_wait_gate", "wait_step >= 3", "prefer_NO_OP_or_manual_review"),
        (5, "intensity_gate", "intensity_schedule == fixed_medium", "allow_design_locked_intensity"),
        (6, "runtime_information_gate", "runtime_inputs_exclude_v2_future_and_validation_score", "allow_runtime_policy_view"),
        (7, "margin_gate", "runtime_margin_proxy_missing_or_below_guard", "NO_OP"),
        (8, "fallback_gate", "any_required_material_missing", "NO_OP"),
    ]
    return pd.DataFrame([_with_boundary({
        "gate_rule_id": f"gate_{order}_{kind}",
        "gate_order": order,
        "gate_type": kind,
        "gate_condition": condition,
        "gate_action": action,
        "gate_status": "provisional_design_gate_locked",
    }) for order, kind, condition, action in rules], columns=GATE_COLUMNS)


def build_fallback_rules() -> pd.DataFrame:
    rules = [
        ("fallback_missing_information", "prepared_action_material_or_runtime_proxy_missing", "NO_OP", "do_not_act_when_runtime_information_is_incomplete"),
        ("fallback_late_timing", "wait_step_outside_0_2_primary_window", "NO_OP_or_review", "late_action_showed_timing_loss_risk"),
        ("fallback_excluded_risk", "boundary_fragile_or_resource_pressure_requested", "NO_OP_or_separate_review_track", "not_in_task24c_adoption_scope"),
        ("fallback_margin_guard", "rollback_or_boundary_proxy_below_guard", "NO_OP", "preserve_reversibility_and_boundary_margin"),
        ("fallback_unknown_risk", "risk_name_not_in_design_locked_scope", "NO_OP", "avoid_unvalidated_action_family"),
    ]
    return pd.DataFrame([_with_boundary({
        "fallback_rule_id": rid,
        "fallback_condition": condition,
        "fallback_action": action,
        "fallback_reason": reason,
        "fallback_status": "formal_NO_OP_fallback_locked",
    }) for rid, condition, action, reason in rules], columns=FALLBACK_COLUMNS)


def build_exclusion_rules() -> pd.DataFrame:
    rows = [
        _with_boundary({
            "excluded_rule_id": "exclude_boundary_fragile_until_baseline_separation",
            "risk_name": "boundary_fragile",
            "exclusion_class": "guarded_review_not_adoption",
            "interim_allowed_state": "fixed_medium_or_fixed_weak_review_only_with_NO_OP_default",
            "required_next_work": "boundary_fragile_baseline_separation_and_guard_condition_audit",
            "exclusion_reason": "large_loss_tail_low_but_operator_specific_advantage_over_random_baseline_is_weak",
        }),
        _with_boundary({
            "excluded_rule_id": "exclude_resource_pressure_until_operator_redesign",
            "risk_name": "resource_pressure",
            "exclusion_class": "operator_redesign_required",
            "interim_allowed_state": "fixed_weak_monitor_only_or_NO_OP_default",
            "required_next_work": "resource_pressure_operator_redesign_with_alternative_targets_and_tail_risk_audit",
            "exclusion_reason": "pressure_diffusion_family_has_unacceptable_large_loss_tail_under_current_design",
        }),
    ]
    return pd.DataFrame(rows, columns=EXCLUSION_COLUMNS)


def build_checks(design: pd.DataFrame, policy: pd.DataFrame, gates: pd.DataFrame, fallbacks: pd.DataFrame, exclusions: pd.DataFrame, source_ready: bool) -> pd.DataFrame:
    checks = [
        ("check_source_ready", "upstream", "Task24b6 final triage is ready.", True, source_ready),
        ("check_ready_risks_only", "scope", "Only the three ready risks are admitted to policy rules.", True, set(policy["risk_name"].astype(str)) == set(READY_RISKS)),
        ("check_excluded_risks_blocked", "scope", "boundary_fragile and resource_pressure are excluded from adoption.", True, set(exclusions["risk_name"].astype(str)) == set(EXCLUDED_RISKS)),
        ("check_fixed_medium_only", "intensity", "All admitted policy rules use fixed_medium.", True, set(policy["intensity_schedule"].astype(str)) == {"fixed_medium"}),
        ("check_wait_0_2_only", "timing", "All admitted policy rules use wait_0_2.", True, set(policy["wait_window"].astype(str)) == {"wait_0_2"}),
        ("check_NO_OP_fallback", "fallback", "NO_OP fallback rules exist.", True, not fallbacks.empty and bool(fallbacks["fallback_action"].astype(str).str.contains("NO_OP").all())),
        ("check_gate_rules", "gate", "Gate rules include scope, timing, intensity, information and fallback guards.", True, len(gates) >= 8),
        ("check_no_deployment_claim", "boundary", "No deployment-ready claim is made.", False, bool(design["deployment_ready_claimed"].astype(bool).any())),
        ("check_no_execution", "boundary", "No real ActionModule call or axis execution occurs.", False, bool(design["real_actionmodule_called"].astype(bool).any() or design["axis_executed"].astype(bool).any())),
        ("check_no_threshold_freeze", "boundary", "No deployment threshold freeze is allowed now.", False, bool(design["threshold_freeze_allowed_now"].astype(bool).any())),
    ]
    return pd.DataFrame([_with_boundary({"check_id": cid, "check_scope": scope, "check_description": desc, "expected_value": bool(exp), "observed_value": bool(obs), "check_status": "pass" if bool(exp) == bool(obs) else "fail"}) for cid, scope, desc, exp, obs in checks], columns=CHECK_COLUMNS)


def build_final_summary(design: pd.DataFrame, policy: pd.DataFrame, gates: pd.DataFrame, fallbacks: pd.DataFrame, exclusions: pd.DataFrame, checks: pd.DataFrame, source_ready: bool) -> pd.DataFrame:
    pass_count = int((checks["check_status"].astype(str) == "pass").sum()) if checks is not None and not checks.empty else 0
    decision = "provisional_action_module_design_lock_ready" if source_ready and len(checks) == pass_count else "provisional_action_module_design_lock_needs_review"
    return pd.DataFrame([_with_boundary({
        "source_task24b6_ready": bool(source_ready),
        "provisional_policy_rule_count": int(len(policy)),
        "gate_rule_count": int(len(gates)),
        "fallback_rule_count": int(len(fallbacks)),
        "excluded_rule_count": int(len(exclusions)),
        "ready_risk_scope": ",".join(READY_RISKS),
        "excluded_risk_scope": ",".join(EXCLUDED_RISKS),
        "primary_intensity_schedule": "fixed_medium",
        "primary_wait_window": "wait_0_2",
        "validation_check_count": int(len(checks)),
        "validation_check_pass_count": pass_count,
        "task24c_provisional_design_decision": decision,
        "next_task": "Use this locked provisional design to draft the action-module policy skeleton; still no real execution or canonical write.",
    })], columns=SUMMARY_COLUMNS)


def validate_tables(design: pd.DataFrame, policy: pd.DataFrame, gates: pd.DataFrame, fallbacks: pd.DataFrame, exclusions: pd.DataFrame, checks: pd.DataFrame, final_summary: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    tables = {"design": (design, DESIGN_COLUMNS), "policy": (policy, POLICY_COLUMNS), "gates": (gates, GATE_COLUMNS), "fallbacks": (fallbacks, FALLBACK_COLUMNS), "exclusions": (exclusions, EXCLUSION_COLUMNS), "checks": (checks, CHECK_COLUMNS), "final_summary": (final_summary, SUMMARY_COLUMNS)}
    for name, (table, columns) in tables.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_24c_empty_table:{name}")
            continue
        missing = [c for c in columns if c not in table.columns]
        if missing:
            errors.append(f"task2_8j_24c_missing_columns:{name}:" + ",".join(missing))
            continue
        for col in REQUIRED_TRUE:
            if not bool(table[col].astype(bool).all()):
                errors.append(f"task2_8j_24c_required_true_not_all_true:{name}:{col}")
        for col in FORBIDDEN_TRUE:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_24c_forbidden_true:{name}:{col}")
    if policy is not None and not policy.empty:
        extra = set(policy["risk_name"].astype(str)) - set(READY_RISKS)
        if extra:
            errors.append("task2_8j_24c_unallowed_policy_risk:" + ",".join(sorted(extra)))
    if checks is not None and not checks.empty and not bool((checks["check_status"].astype(str) == "pass").all()):
        errors.append("task2_8j_24c_check_failed")
    return errors


def build_and_validate_provisional_action_module_design_lock(cfg: ProvisionalActionModuleDesignLockConfig | None = None, **_unused: object) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    cfg = cfg or ProvisionalActionModuleDesignLockConfig()
    _policy6, _review6, matrix6, _checks6, _final6, errors6, summary6 = build_and_validate_final_triage_before_24c()
    source_ready = len(errors6) == 0 and str(summary6.get("task24b6_final_triage_decision", "")) == "final_triage_before_24c_ready"
    if not cfg.require_task24b6_ready:
        source_ready = True
    design = build_design_contract(source_ready)
    policy = build_policy_rules(matrix6)
    gates = build_gate_rules()
    fallbacks = build_fallback_rules()
    exclusions = build_exclusion_rules()
    checks = build_checks(design, policy, gates, fallbacks, exclusions, source_ready)
    final_summary = build_final_summary(design, policy, gates, fallbacks, exclusions, checks, source_ready)
    errors: list[str] = []
    if cfg.require_task24b6_ready:
        errors += [f"task2_8j_24c_upstream_24b6_error:{e}" for e in errors6]
    errors += validate_tables(design, policy, gates, fallbacks, exclusions, checks, final_summary)
    summary = {
        "gt_main_map_name": "static_pca_7",
        "gt_main_component_count": 7,
        "source_task24b6_decision": summary6.get("task24b6_final_triage_decision", ""),
        "source_task24b6_ready": bool(source_ready),
        "provisional_policy_rule_count": int(final_summary["provisional_policy_rule_count"].iloc[0]),
        "gate_rule_count": int(final_summary["gate_rule_count"].iloc[0]),
        "fallback_rule_count": int(final_summary["fallback_rule_count"].iloc[0]),
        "excluded_rule_count": int(final_summary["excluded_rule_count"].iloc[0]),
        "ready_risk_scope": str(final_summary["ready_risk_scope"].iloc[0]),
        "excluded_risk_scope": str(final_summary["excluded_risk_scope"].iloc[0]),
        "primary_intensity_schedule": str(final_summary["primary_intensity_schedule"].iloc[0]),
        "primary_wait_window": str(final_summary["primary_wait_window"].iloc[0]),
        "threshold_freeze_allowed_now": False,
        "deployment_ready_claimed": False,
        "canonical_write_performed": False,
        "real_actionmodule_called": False,
        "axis_executed": False,
        "validation_check_count": int(final_summary["validation_check_count"].iloc[0]),
        "validation_check_pass_count": int(final_summary["validation_check_pass_count"].iloc[0]),
        "task24c_provisional_design_decision": str(final_summary["task24c_provisional_design_decision"].iloc[0]),
        "validation_errors": errors,
    }
    return design, policy, gates, fallbacks, exclusions, checks, final_summary, errors, summary
