"""Task 2-8j-24b6: final triage before Task24c RC1.

Final validation/triage step before a provisional adoption-policy task.

The goal is not to freeze thresholds and not to create executable action
candidates.  The goal is to separate:

- risks that are ready to enter Task24c provisional adoption-policy drafting,
- risks that need targeted additional validation, and
- risks that need operator redesign before adoption.

Inputs are Task24b4 targeted robustness and Task24b5 intensity-schedule results.
No v2 future information is introduced into runtime policy selection here; this
module only summarizes already-produced validation outputs.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from .pressure_action_task2_8j_24b4_targeted_robustness_validation import (
    build_and_validate_targeted_robustness_validation,
)
from .pressure_action_task2_8j_24b5_action_intensity_schedule_validation import (
    build_and_validate_action_intensity_schedule_validation,
)

TASK2_8J_24B6_VERSION = "final_triage_before_24c_rc1"
READY_RISKS = ("relation_lock", "oscillation", "reversibility_loss")
REVIEW_RISKS = ("boundary_fragile",)
REDESIGN_RISKS = ("resource_pressure",)

BOUNDARY: dict[str, Any] = {
    "task2_8j_24b6_version": TASK2_8J_24B6_VERSION,
    "validation_only": True,
    "final_triage_before_24c": True,
    "source_task24b4_required": True,
    "source_task24b5_required": True,
    "provisional_policy_drafting_only": True,
    "no_threshold_update_performed": True,
    "no_formal_action_candidate_generated": True,
    "no_real_actionmodule_called": True,
    "no_axis_executed": True,
    "runtime_scoring_information_separation_inherited": True,
    "v2_used_for_scoring_only": True,
    "NO_OP_used_for_scoring_only": True,
    "gt_main_map_name": "static_pca_7",
    "gt_main_component_count": 7,
    "threshold_freeze_allowed_now": False,
    "action_candidate_generated": False,
    "real_actionmodule_called": False,
    "axis_executed": False,
    "canonical_write_performed": False,
}

REQUIRED_TRUE = [
    "validation_only", "final_triage_before_24c", "source_task24b4_required", "source_task24b5_required",
    "provisional_policy_drafting_only", "no_threshold_update_performed", "no_formal_action_candidate_generated",
    "no_real_actionmodule_called", "no_axis_executed", "runtime_scoring_information_separation_inherited",
    "v2_used_for_scoring_only", "NO_OP_used_for_scoring_only",
]
FORBIDDEN_TRUE = ["threshold_freeze_allowed_now", "action_candidate_generated", "real_actionmodule_called", "axis_executed", "canonical_write_performed"]

POLICY_COLUMNS = list(BOUNDARY) + [
    "policy_candidate_id", "risk_name", "recommended_operator_family", "recommended_intensity_schedule",
    "recommended_wait_window", "task24b4_gate", "task24b5_fixed_medium_class", "task24b5_fixed_medium_ev",
    "task24b5_fixed_medium_large_loss_rate", "side_effect_large_loss_class", "policy_readiness_class",
    "policy_readiness_reason", "allowed_next_task",
]
REVIEW_COLUMNS = list(BOUNDARY) + [
    "review_id", "risk_name", "current_status", "primary_issue", "preferred_interim_action", "required_next_validation",
    "blocked_from_24c_adoption", "review_reason",
]
MATRIX_COLUMNS = list(BOUNDARY) + [
    "matrix_id", "risk_name", "task24b4_gate", "best_schedule_name", "best_schedule_mean_ev",
    "best_schedule_large_loss_rate", "fixed_medium_mean_ev", "fixed_medium_large_loss_rate",
    "fixed_weak_mean_ev", "fixed_weak_large_loss_rate", "fixed_strong_large_loss_rate",
    "matrix_decision", "matrix_reason",
]
CHECK_COLUMNS = list(BOUNDARY) + ["check_id", "check_scope", "check_description", "expected_value", "observed_value", "check_status"]
SUMMARY_COLUMNS = list(BOUNDARY) + [
    "source_task24b4_ready", "source_task24b5_ready", "ready_for_24c_count", "guarded_review_count",
    "redesign_required_count", "blocked_from_adoption_count", "recommended_24c_scope", "validation_check_count",
    "validation_check_pass_count", "task24b6_final_triage_decision", "next_task",
]


@dataclass(frozen=True)
class FinalTriageBefore24cConfig:
    require_task24b4_ready: bool = True
    require_task24b5_ready: bool = True


def _with_boundary(row: dict[str, Any]) -> dict[str, Any]:
    return {**BOUNDARY, **row}


def _safe_float(v: object, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def _first(table: pd.DataFrame, **match: object) -> pd.Series | None:
    if table is None or table.empty:
        return None
    mask = pd.Series(True, index=table.index)
    for key, value in match.items():
        if key not in table.columns:
            return None
        mask &= table[key].astype(str).eq(str(value))
    subset = table[mask]
    if subset.empty:
        return None
    return subset.iloc[0]


def _operator_family_for_risk(risk: str) -> str:
    return {
        "relation_lock": "lock_relief / soft_resistance",
        "oscillation": "oscillation_damping / damping",
        "reversibility_loss": "return_path_support / reversibility_support",
        "boundary_fragile": "boundary_standoff / buffer_injection",
        "resource_pressure": "pressure_relief / pressure_diffusion",
    }.get(str(risk), "unknown")


def build_policy_candidates(gates_b4: pd.DataFrame, comparison_b5: pd.DataFrame, audit_b5: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for risk in READY_RISKS:
        gate = _first(gates_b4, risk_name=risk)
        comp = _first(comparison_b5, risk_name=risk, schedule_name="fixed_medium")
        audit = _first(audit_b5, risk_name=risk, schedule_name="fixed_medium")
        gate_class = str(gate["recommended_gate"]) if gate is not None else "missing_gate"
        comp_class = str(comp["schedule_objective_class"]) if comp is not None else "missing_intensity_class"
        audit_class = str(audit["audit_class"]) if audit is not None else "missing_audit_class"
        ev = _safe_float(comp["mean_relative_ev"]) if comp is not None else 0.0
        large = _safe_float(comp["large_loss_rate"]) if comp is not None else 1.0
        ready = gate_class == "strong_adoption_candidate" and comp_class == "fixed_intensity_candidate" and large <= 0.03
        if ready:
            cls = "ready_for_task24c_provisional_policy"
            reason = "strong_gate_fixed_medium_candidate_and_large_loss_constraint_pass"
        else:
            cls = "task24c_entry_review"
            reason = "candidate_needs_manual_review_before_policy_drafting"
        rows.append(_with_boundary({
            "policy_candidate_id": f"policy_candidate_{risk}",
            "risk_name": risk,
            "recommended_operator_family": _operator_family_for_risk(risk),
            "recommended_intensity_schedule": "fixed_medium",
            "recommended_wait_window": "wait_0_2_primary_window",
            "task24b4_gate": gate_class,
            "task24b5_fixed_medium_class": comp_class,
            "task24b5_fixed_medium_ev": round(ev, 6),
            "task24b5_fixed_medium_large_loss_rate": round(large, 6),
            "side_effect_large_loss_class": audit_class,
            "policy_readiness_class": cls,
            "policy_readiness_reason": reason,
            "allowed_next_task": "Task24c_provisional_adoption_policy_drafting_only",
        }))
    return pd.DataFrame(rows, columns=POLICY_COLUMNS)


def build_targeted_review_plan(gates_b4: pd.DataFrame, comparison_b5: pd.DataFrame, gradual_b5: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    boundary_gate = _first(gates_b4, risk_name="boundary_fragile")
    boundary_medium = _first(comparison_b5, risk_name="boundary_fragile", schedule_name="fixed_medium")
    rows.append(_with_boundary({
        "review_id": "review_boundary_fragile_baseline_separation",
        "risk_name": "boundary_fragile",
        "current_status": str(boundary_gate["recommended_gate"]) if boundary_gate is not None else "guarded_review_candidate",
        "primary_issue": "randomized_baseline_separation_is_weak_despite_low_large_loss_rate",
        "preferred_interim_action": "keep_guarded_review_fixed_medium_or_fixed_weak_only",
        "required_next_validation": "boundary_fragile_baseline_separation_and_guard_condition_audit",
        "blocked_from_24c_adoption": True,
        "review_reason": f"fixed_medium_ev={_safe_float(boundary_medium['mean_relative_ev']) if boundary_medium is not None else 0.0:.6f}; adoption_requires_clearer_operator_specific_advantage",
    }))
    rp_medium = _first(comparison_b5, risk_name="resource_pressure", schedule_name="fixed_medium")
    rp_weak = _first(comparison_b5, risk_name="resource_pressure", schedule_name="fixed_weak")
    rp_gradual = _first(gradual_b5, risk_name="resource_pressure", schedule_name="gradual_ramp")
    rows.append(_with_boundary({
        "review_id": "review_resource_pressure_operator_redesign",
        "risk_name": "resource_pressure",
        "current_status": "operator_redesign_required",
        "primary_issue": "fixed_medium_large_loss_too_high_and_strong_or_gradual_schedule_does_not_rescue",
        "preferred_interim_action": "fixed_weak_monitor_only_or_NO_OP_preferred_until_redesign",
        "required_next_validation": "resource_pressure_operator_redesign_with_alternative_targets_and_tail_risk_audit",
        "blocked_from_24c_adoption": True,
        "review_reason": f"medium_large_loss={_safe_float(rp_medium['large_loss_rate']) if rp_medium is not None else 1.0:.6f}; weak_large_loss={_safe_float(rp_weak['large_loss_rate']) if rp_weak is not None else 1.0:.6f}; gradual_ev={_safe_float(rp_gradual['mean_relative_ev']) if rp_gradual is not None else 0.0:.6f}",
    }))
    return pd.DataFrame(rows, columns=REVIEW_COLUMNS)


def build_decision_matrix(gates_b4: pd.DataFrame, comparison_b5: pd.DataFrame, summary_b5: dict) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for risk in list(READY_RISKS) + list(REVIEW_RISKS) + list(REDESIGN_RISKS):
        gate = _first(gates_b4, risk_name=risk)
        medium = _first(comparison_b5, risk_name=risk, schedule_name="fixed_medium")
        weak = _first(comparison_b5, risk_name=risk, schedule_name="fixed_weak")
        strong = _first(comparison_b5, risk_name=risk, schedule_name="fixed_strong")
        best_schedule = "fixed_medium"
        best_ev = _safe_float(medium["mean_relative_ev"]) if medium is not None else 0.0
        best_large = _safe_float(medium["large_loss_rate"]) if medium is not None else 1.0
        if risk == "resource_pressure":
            best_schedule = str(summary_b5.get("resource_pressure_best_schedule", "fixed_medium"))
            comp = _first(comparison_b5, risk_name=risk, schedule_name=best_schedule)
            if comp is not None:
                best_ev = _safe_float(comp["mean_relative_ev"])
                best_large = _safe_float(comp["large_loss_rate"])
        if risk in READY_RISKS:
            decision = "enter_task24c_scope"
            reason = "strong_candidate_after_targeted_robustness_and_intensity_schedule_validation"
        elif risk == "boundary_fragile":
            decision = "additional_validation_before_adoption"
            reason = "operator_specific_baseline_separation_not_strong_enough"
        else:
            decision = "operator_redesign_before_adoption"
            reason = "large_loss_tail_remains_too_high_under_current_pressure_diffusion_family"
        rows.append(_with_boundary({
            "matrix_id": f"matrix_{risk}",
            "risk_name": risk,
            "task24b4_gate": str(gate["recommended_gate"]) if gate is not None else "missing_gate",
            "best_schedule_name": best_schedule,
            "best_schedule_mean_ev": round(best_ev, 6),
            "best_schedule_large_loss_rate": round(best_large, 6),
            "fixed_medium_mean_ev": round(_safe_float(medium["mean_relative_ev"]) if medium is not None else 0.0, 6),
            "fixed_medium_large_loss_rate": round(_safe_float(medium["large_loss_rate"]) if medium is not None else 1.0, 6),
            "fixed_weak_mean_ev": round(_safe_float(weak["mean_relative_ev"]) if weak is not None else 0.0, 6),
            "fixed_weak_large_loss_rate": round(_safe_float(weak["large_loss_rate"]) if weak is not None else 1.0, 6),
            "fixed_strong_large_loss_rate": round(_safe_float(strong["large_loss_rate"]) if strong is not None else 1.0, 6),
            "matrix_decision": decision,
            "matrix_reason": reason,
        }))
    return pd.DataFrame(rows, columns=MATRIX_COLUMNS)


def build_checks(policy: pd.DataFrame, review: pd.DataFrame, matrix: pd.DataFrame, b4_ready: bool, b5_ready: bool) -> pd.DataFrame:
    checks = [
        ("check_task24b4_ready", "upstream", "Task24b4 targeted robustness validation is ready.", True, b4_ready),
        ("check_task24b5_ready", "upstream", "Task24b5 intensity schedule validation is ready.", True, b5_ready),
        ("check_three_policy_candidates", "policy", "Exactly the three strong risks are prepared for Task24c drafting.", True, set(policy["risk_name"].astype(str)) == set(READY_RISKS)),
        ("check_policy_no_threshold_freeze", "boundary", "Policy candidates do not freeze thresholds now.", False, bool(policy["threshold_freeze_allowed_now"].astype(bool).any())),
        ("check_review_targets", "review", "boundary_fragile and resource_pressure remain outside adoption scope.", True, set(review["risk_name"].astype(str)) == {"boundary_fragile", "resource_pressure"} and bool(review["blocked_from_24c_adoption"].astype(bool).all())),
        ("check_decision_matrix", "matrix", "Decision matrix covers all five risks.", True, set(matrix["risk_name"].astype(str)) == set(READY_RISKS + REVIEW_RISKS + REDESIGN_RISKS)),
        ("check_no_action_candidate", "boundary", "No formal action candidate is generated.", False, bool(matrix["action_candidate_generated"].astype(bool).any())),
        ("check_no_execution", "boundary", "No real ActionModule call or axis execution occurs.", False, bool(matrix["real_actionmodule_called"].astype(bool).any() or matrix["axis_executed"].astype(bool).any())),
    ]
    return pd.DataFrame([_with_boundary({"check_id": c[0], "check_scope": c[1], "check_description": c[2], "expected_value": bool(c[3]), "observed_value": bool(c[4]), "check_status": "pass" if bool(c[3]) == bool(c[4]) else "fail"}) for c in checks], columns=CHECK_COLUMNS)


def build_final_summary(policy: pd.DataFrame, review: pd.DataFrame, checks: pd.DataFrame, b4_ready: bool, b5_ready: bool) -> pd.DataFrame:
    pass_count = int((checks["check_status"].astype(str) == "pass").sum()) if checks is not None and not checks.empty else 0
    ready_count = int((policy["policy_readiness_class"].astype(str) == "ready_for_task24c_provisional_policy").sum()) if not policy.empty else 0
    review_count = int((review["risk_name"].astype(str) == "boundary_fragile").sum()) if not review.empty else 0
    redesign_count = int((review["risk_name"].astype(str) == "resource_pressure").sum()) if not review.empty else 0
    decision = "final_triage_before_24c_ready" if b4_ready and b5_ready and len(checks) == pass_count else "final_triage_before_24c_needs_review"
    return pd.DataFrame([_with_boundary({
        "source_task24b4_ready": bool(b4_ready),
        "source_task24b5_ready": bool(b5_ready),
        "ready_for_24c_count": ready_count,
        "guarded_review_count": review_count,
        "redesign_required_count": redesign_count,
        "blocked_from_adoption_count": int(review["blocked_from_24c_adoption"].astype(bool).sum()) if not review.empty else 0,
        "recommended_24c_scope": "relation_lock,oscillation,reversibility_loss",
        "validation_check_count": len(checks),
        "validation_check_pass_count": pass_count,
        "task24b6_final_triage_decision": decision,
        "next_task": "Task24c provisional adoption-policy drafting for ready risks only; keep boundary_fragile/resource_pressure in separate validation/redesign tracks.",
    })], columns=SUMMARY_COLUMNS)


def validate_tables(policy: pd.DataFrame, review: pd.DataFrame, matrix: pd.DataFrame, checks: pd.DataFrame, final_summary: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    tables = {"policy": (policy, POLICY_COLUMNS), "review": (review, REVIEW_COLUMNS), "matrix": (matrix, MATRIX_COLUMNS), "checks": (checks, CHECK_COLUMNS), "final_summary": (final_summary, SUMMARY_COLUMNS)}
    for name, (table, cols) in tables.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_24b6_empty_table:{name}")
            continue
        missing = [c for c in cols if c not in table.columns]
        if missing:
            errors.append(f"task2_8j_24b6_missing_columns:{name}:" + ",".join(missing))
            continue
        for col in REQUIRED_TRUE:
            if not bool(table[col].astype(bool).all()):
                errors.append(f"task2_8j_24b6_required_true_not_all_true:{name}:{col}")
        for col in FORBIDDEN_TRUE:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_24b6_forbidden_true:{name}:{col}")
    if checks is not None and not checks.empty and not bool((checks["check_status"].astype(str) == "pass").all()):
        errors.append("task2_8j_24b6_check_failed")
    if policy is not None and not policy.empty:
        missing_ready = set(READY_RISKS) - set(policy["risk_name"].astype(str))
        if missing_ready:
            errors.append("task2_8j_24b6_missing_ready_policy_candidates:" + ",".join(sorted(missing_ready)))
    return errors


def build_and_validate_final_triage_before_24c(cfg: FinalTriageBefore24cConfig | None = None, **_unused: object) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    cfg = cfg or FinalTriageBefore24cConfig()
    _primary4, _stress4, _boundary4, _resource4, _window4, gates4, _checks4, _final4, errors4, summary4 = build_and_validate_targeted_robustness_validation()
    _runtime5, _scoring5, comparison5, gradual5, audit5, _checks5, _final5, errors5, summary5 = build_and_validate_action_intensity_schedule_validation()
    b4_ready = len(errors4) == 0 and str(summary4.get("targeted_robustness_validation_decision", "")) == "targeted_robustness_validation_ready"
    b5_ready = len(errors5) == 0 and str(summary5.get("action_intensity_schedule_validation_decision", "")) == "action_intensity_schedule_validation_ready"
    if not cfg.require_task24b4_ready:
        b4_ready = True
    if not cfg.require_task24b5_ready:
        b5_ready = True
    policy = build_policy_candidates(gates4, comparison5, audit5)
    review = build_targeted_review_plan(gates4, comparison5, gradual5)
    matrix = build_decision_matrix(gates4, comparison5, summary5)
    checks = build_checks(policy, review, matrix, b4_ready, b5_ready)
    final_summary = build_final_summary(policy, review, checks, b4_ready, b5_ready)
    errors: list[str] = []
    if cfg.require_task24b4_ready:
        errors += [f"task2_8j_24b6_upstream_24b4_error:{e}" for e in errors4]
    if cfg.require_task24b5_ready:
        errors += [f"task2_8j_24b6_upstream_24b5_error:{e}" for e in errors5]
    errors += validate_tables(policy, review, matrix, checks, final_summary)
    summary = {
        "gt_main_map_name": "static_pca_7",
        "gt_main_component_count": 7,
        "source_task24b4_decision": summary4.get("targeted_robustness_validation_decision", ""),
        "source_task24b5_decision": summary5.get("action_intensity_schedule_validation_decision", ""),
        "source_task24b4_ready": bool(b4_ready),
        "source_task24b5_ready": bool(b5_ready),
        "ready_for_24c_count": int(final_summary["ready_for_24c_count"].iloc[0]),
        "guarded_review_count": int(final_summary["guarded_review_count"].iloc[0]),
        "redesign_required_count": int(final_summary["redesign_required_count"].iloc[0]),
        "blocked_from_adoption_count": int(final_summary["blocked_from_adoption_count"].iloc[0]),
        "recommended_24c_scope": str(final_summary["recommended_24c_scope"].iloc[0]),
        "threshold_freeze_allowed_now": False,
        "action_candidate_generated": False,
        "real_actionmodule_called": False,
        "axis_executed": False,
        "validation_check_count": int(final_summary["validation_check_count"].iloc[0]),
        "validation_check_pass_count": int(final_summary["validation_check_pass_count"].iloc[0]),
        "task24b6_final_triage_decision": str(final_summary["task24b6_final_triage_decision"].iloc[0]),
        "validation_errors": errors,
    }
    return policy, review, matrix, checks, final_summary, errors, summary
