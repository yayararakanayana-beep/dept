"""Task 2-8j-17: action-candidate minimal eligibility contract RC1.

Purpose:
    Freeze the minimal formal pass-through conditions for turning a dry-run
    action axis into a later action-candidate review object, without generating
    candidates.  This contract is intentionally not a full expected-value or
    risk judgment.

Position:
    Task 2-8j-16 reviewed dry-run action axes against the NO_OP baseline without
    execution.  Task 2-8j-17 defines only the minimum form conditions that must
    be preserved before a future candidate-generation step may even be prepared.

Core principle:
    Keep this as lightweight risk management, not early optimization.  A dry-run
    axis may become candidate-form-allowed only if trace, NO_OP carry-forward,
    release, rollback, audit, weak strength, and non-execution boundaries are
    intact.  Expected-value final judgment, risk final judgment, action-effect
    prediction, candidate generation, and execution remain explicitly out of
    scope.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .pressure_action_task2_8j_6c_v2_structure_change_relation_field_tracking import V2StructureChangeTrackingConfig
from .pressure_action_task2_8j_7_ot_observation_map_from_relation_field import OtObservationMapConfig
from .pressure_action_task2_8j_7b_ot_audit_layering import OtAuditLayeringConfig
from .pressure_action_task2_8j_7c_relation_to_ot_information_preservation_audit import RelationToOtInformationPreservationConfig
from .pressure_action_task2_8j_8_action_module_input_split_contract import ActionModuleInputSplitContractConfig
from .pressure_action_task2_8j_9_two_route_reception_dry_run import TwoRouteReceptionDryRunConfig
from .pressure_action_task2_8j_10_game_structure_prediction_input_contract import GameStructurePredictionInputContractConfig
from .pressure_action_task2_8j_11_game_structure_prediction_envelope_dry_run import GameStructurePredictionEnvelopeDryRunConfig
from .pressure_action_task2_8j_12_new_gt_upper_layer_revalidation import NewGtUpperLayerRevalidationConfig
from .pressure_action_task2_8j_13_action_axis_material_contract import ActionAxisMaterialContractConfig
from .pressure_action_task2_8j_14_action_axis_material_bundle_dry_run import ActionAxisMaterialBundleDryRunConfig
from .pressure_action_task2_8j_15_action_axis_dry_run_generation import ActionAxisDryRunGenerationConfig
from .pressure_action_task2_8j_16_action_axis_non_execution_review_no_op import (
    ActionAxisNonExecutionReviewConfig,
    build_and_validate_action_axis_non_execution_review,
)

TASK2_8J_17_VERSION = "action_candidate_minimal_eligibility_contract_rc1"
TASK2_8J_17_CONTRACT = (
    "Task2_8j_17_action_candidate_minimal_eligibility_contract__"
    "minimal_formal_passage_only__"
    "no_expected_value_final_judgment_no_risk_final_judgment__"
    "no_effect_prediction_no_candidate_generation_no_execution"
)

BOUNDARY = {
    "task2_8j_17_version": TASK2_8J_17_VERSION,
    "task2_8j_17_contract": TASK2_8J_17_CONTRACT,
    "validation_only": True,
    "minimal_eligibility_contract_only": True,
    "candidate_form_contract_only": True,
    "lightweight_risk_management_only": True,
    "gt_main_map_name": "static_pca_7",
    "gt_main_component_count": 7,
    "source_action_axis_review_required": True,
    "trace_required": True,
    "no_op_carry_forward_required": True,
    "release_required": True,
    "rollback_required": True,
    "audit_required": True,
    "weak_strength_required": True,
    "non_execution_required": True,
    "effect_prediction_required_later": True,
    "risk_review_required_later": True,
    "expected_value_review_required_later": True,
    "no_op_preserved": True,
    "expected_value_final_judgment_performed": False,
    "risk_final_judgment_performed": False,
    "action_effect_prediction_generated": False,
    "action_candidate_generated": False,
    "concrete_action_generated": False,
    "candidate_instantiated": False,
    "action_translation_performed": False,
    "action_input_converted": False,
    "action_frame_created": False,
    "real_actionmodule_called": False,
    "actionmodule_called": False,
    "axis_executed": False,
    "runtime_policy_input": False,
    "fullspec_runtime_connected": False,
    "canonical_write_performed": False,
    "gk_writeback_performed": False,
    "ot_writeback_performed": False,
    "effective_dimension_refit_performed": False,
    "axis_mutation_performed": False,
    "residual_auxiliary_injected_into_gt_main": False,
    "hidden_truth_input": False,
    "future_information_used": False,
}

FORBIDDEN_TRUE = [
    "expected_value_final_judgment_performed",
    "risk_final_judgment_performed",
    "action_effect_prediction_generated",
    "action_candidate_generated",
    "concrete_action_generated",
    "candidate_instantiated",
    "action_translation_performed",
    "action_input_converted",
    "action_frame_created",
    "real_actionmodule_called",
    "actionmodule_called",
    "axis_executed",
    "runtime_policy_input",
    "fullspec_runtime_connected",
    "canonical_write_performed",
    "gk_writeback_performed",
    "ot_writeback_performed",
    "effective_dimension_refit_performed",
    "axis_mutation_performed",
    "residual_auxiliary_injected_into_gt_main",
    "hidden_truth_input",
    "future_information_used",
]

REQUIRED_ELIGIBILITY_COLUMNS = list(BOUNDARY) + [
    "eligibility_id",
    "action_axis_id",
    "source_material_bundle_id",
    "trace_condition",
    "no_op_condition",
    "release_condition",
    "rollback_condition",
    "audit_condition",
    "weak_strength_condition",
    "non_execution_condition",
    "formal_minimum_passage_status",
    "candidate_form_allowed",
    "needs_effect_prediction",
    "needs_risk_review",
    "needs_expected_value_review",
    "no_op_preserved_status",
    "blocked_reason",
    "eligibility_status",
]

REQUIRED_CARRY_COLUMNS = list(BOUNDARY) + [
    "carry_forward_id",
    "action_axis_id",
    "source_review_id",
    "source_no_op_comparison_id",
    "non_execution_review_decision",
    "no_op_comparison_status",
    "no_op_default_preserved",
    "no_op_required_when_uncertain",
    "carry_forward_status",
]

REQUIRED_CHECK_COLUMNS = list(BOUNDARY) + [
    "check_id",
    "check_scope",
    "check_description",
    "expected_value",
    "observed_value",
    "check_status",
]

REQUIRED_SUMMARY_COLUMNS = list(BOUNDARY) + [
    "axis_review_count",
    "eligibility_row_count",
    "carry_forward_row_count",
    "candidate_form_allowed_count",
    "blocked_count",
    "needs_effect_prediction_count",
    "needs_risk_review_count",
    "needs_expected_value_review_count",
    "contract_check_count",
    "contract_check_pass_count",
    "action_candidate_minimal_eligibility_contract_decision",
    "next_task",
]


@dataclass(frozen=True)
class ActionCandidateMinimalEligibilityContractConfig:
    require_task16_ready: bool = True


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def build_eligibility_table(review: pd.DataFrame, no_op: pd.DataFrame) -> pd.DataFrame:
    if review is None or review.empty:
        return pd.DataFrame(columns=REQUIRED_ELIGIBILITY_COLUMNS)
    no_op_lookup = {str(r.action_axis_id): r for r in no_op.itertuples(index=False)} if no_op is not None and not no_op.empty else {}
    rows: list[dict] = []
    for row in review.itertuples(index=False):
        axis_id = str(row.action_axis_id)
        noop_row = no_op_lookup.get(axis_id)
        trace_ok = str(row.trace_review_status).startswith("pass")
        no_op_ok = bool(noop_row is not None and bool(noop_row.no_op_default_preserved) and bool(noop_row.no_op_required_when_uncertain))
        release_ok = str(row.release_review_status).startswith("pass")
        rollback_ok = str(row.rollback_review_status).startswith("pass")
        audit_ok = str(row.audit_review_status).startswith("pass")
        weak_ok = str(row.strength_review_status).startswith("pass")
        non_execution_ok = not bool(row.axis_executed) and not bool(row.action_candidate_generated) and not bool(row.concrete_action_generated)
        required = {
            "trace": trace_ok,
            "NO_OP": no_op_ok,
            "release": release_ok,
            "rollback": rollback_ok,
            "audit": audit_ok,
            "weak_strength": weak_ok,
            "non_execution": non_execution_ok,
        }
        missing = [name for name, ok in required.items() if not ok]
        candidate_form_allowed = len(missing) == 0
        rows.append({
            **BOUNDARY,
            "eligibility_id": f"minimal_eligibility_{axis_id}",
            "action_axis_id": axis_id,
            "source_material_bundle_id": str(row.source_material_bundle_id),
            "trace_condition": "pass_trace_present" if trace_ok else "blocked_trace_missing",
            "no_op_condition": "pass_NO_OP_carry_forward" if no_op_ok else "blocked_NO_OP_carry_forward_missing",
            "release_condition": "pass_release_present" if release_ok else "blocked_release_missing",
            "rollback_condition": "pass_rollback_present" if rollback_ok else "blocked_rollback_missing",
            "audit_condition": "pass_audit_present" if audit_ok else "blocked_audit_missing",
            "weak_strength_condition": "pass_weak_strength" if weak_ok else "blocked_strength_not_weak",
            "non_execution_condition": "pass_non_execution_boundary" if non_execution_ok else "blocked_execution_or_candidate_generation_detected",
            "formal_minimum_passage_status": "formal_minimum_passage_ready" if candidate_form_allowed else "formal_minimum_passage_blocked",
            "candidate_form_allowed": bool(candidate_form_allowed),
            "needs_effect_prediction": True,
            "needs_risk_review": True,
            "needs_expected_value_review": True,
            "no_op_preserved_status": "NO_OP_preserved_and_carried_forward" if no_op_ok else "NO_OP_not_preserved",
            "blocked_reason": "none" if candidate_form_allowed else ";".join(missing),
            "eligibility_status": "minimal_eligibility_completed_without_candidate_generation",
        })
    return pd.DataFrame(rows, columns=REQUIRED_ELIGIBILITY_COLUMNS)


def build_carry_forward_table(review: pd.DataFrame, no_op: pd.DataFrame) -> pd.DataFrame:
    if review is None or review.empty:
        return pd.DataFrame(columns=REQUIRED_CARRY_COLUMNS)
    no_op_lookup = {str(r.action_axis_id): r for r in no_op.itertuples(index=False)} if no_op is not None and not no_op.empty else {}
    rows: list[dict] = []
    for row in review.itertuples(index=False):
        axis_id = str(row.action_axis_id)
        noop = no_op_lookup.get(axis_id)
        rows.append({
            **BOUNDARY,
            "carry_forward_id": f"candidate_form_carry_forward_{axis_id}",
            "action_axis_id": axis_id,
            "source_review_id": str(row.review_id),
            "source_no_op_comparison_id": str(getattr(noop, "comparison_id", "missing_no_op_comparison")),
            "non_execution_review_decision": str(row.non_execution_review_decision),
            "no_op_comparison_status": str(getattr(noop, "no_op_comparison_decision", "NO_OP_missing")),
            "no_op_default_preserved": bool(getattr(noop, "no_op_default_preserved", False)),
            "no_op_required_when_uncertain": bool(getattr(noop, "no_op_required_when_uncertain", False)),
            "carry_forward_status": "NO_OP_and_review_carried_forward_without_final_judgment" if noop is not None else "carry_forward_missing_no_op",
        })
    return pd.DataFrame(rows, columns=REQUIRED_CARRY_COLUMNS)


def build_contract_checks(eligibility: pd.DataFrame, carry: pd.DataFrame, task16_errors: list[str], task16_summary: dict) -> pd.DataFrame:
    has_rows = bool(eligibility is not None and not eligibility.empty)
    has_carry = bool(carry is not None and not carry.empty)
    task16_ready = len(task16_errors) == 0 and str(task16_summary.get("action_axis_non_execution_review_decision", "")).startswith("action_axis_non_execution_review_and_NO_OP_comparison_ready")
    checks = [
        ("check_task16_ready", "upstream", "Task2-8j-16 non-execution review is ready.", True, task16_ready),
        ("check_eligibility_rows_created", "eligibility", "Eligibility rows are created for reviewed axes.", True, has_rows),
        ("check_carry_forward_rows_created", "NO_OP", "NO_OP carry-forward rows are created.", True, has_carry and len(carry) == len(eligibility)),
        ("check_candidate_form_allowed_or_blocked", "eligibility", "Every row is explicitly allowed or blocked at formal minimum level.", True, bool(eligibility["formal_minimum_passage_status"].astype(str).str.startswith("formal_minimum_passage_").all()) if has_rows else False),
        ("check_effect_prediction_deferred", "boundary", "Effect prediction is required later, not performed here.", True, bool(eligibility["needs_effect_prediction"].astype(bool).all()) if has_rows else False),
        ("check_risk_review_deferred", "boundary", "Risk review is required later, not finally judged here.", True, bool(eligibility["needs_risk_review"].astype(bool).all()) if has_rows else False),
        ("check_expected_value_review_deferred", "boundary", "Expected-value review is required later, not finally judged here.", True, bool(eligibility["needs_expected_value_review"].astype(bool).all()) if has_rows else False),
        ("check_no_op_preserved", "NO_OP", "NO_OP is preserved and carried forward.", True, bool(carry["no_op_default_preserved"].astype(bool).all() and carry["no_op_required_when_uncertain"].astype(bool).all()) if has_carry else False),
        ("check_no_final_expected_value_judgment", "boundary", "No expected-value final judgment is performed.", False, bool(eligibility["expected_value_final_judgment_performed"].astype(bool).any()) if has_rows else True),
        ("check_no_final_risk_judgment", "boundary", "No risk final judgment is performed.", False, bool(eligibility["risk_final_judgment_performed"].astype(bool).any()) if has_rows else True),
        ("check_no_effect_prediction", "boundary", "No action-effect prediction is generated.", False, bool(eligibility["action_effect_prediction_generated"].astype(bool).any()) if has_rows else True),
        ("check_no_candidate_generation", "boundary", "No action candidate is generated.", False, bool(eligibility["action_candidate_generated"].astype(bool).any()) if has_rows else True),
        ("check_no_execution", "boundary", "No execution occurs.", False, bool(eligibility["axis_executed"].astype(bool).any()) if has_rows else True),
    ]
    rows: list[dict] = []
    for check_id, scope, description, expected, observed in checks:
        rows.append({
            **BOUNDARY,
            "check_id": check_id,
            "check_scope": scope,
            "check_description": description,
            "expected_value": bool(expected),
            "observed_value": bool(observed),
            "check_status": "pass" if bool(expected) == bool(observed) else "fail",
        })
    return pd.DataFrame(rows, columns=REQUIRED_CHECK_COLUMNS)


def build_final_summary(review: pd.DataFrame, eligibility: pd.DataFrame, carry: pd.DataFrame, checks: pd.DataFrame) -> pd.DataFrame:
    review_count = int(len(review)) if review is not None else 0
    eligibility_count = int(len(eligibility)) if eligibility is not None else 0
    carry_count = int(len(carry)) if carry is not None else 0
    allowed = int(eligibility["candidate_form_allowed"].astype(bool).sum()) if eligibility_count else 0
    blocked = int((~eligibility["candidate_form_allowed"].astype(bool)).sum()) if eligibility_count else 0
    needs_effect = int(eligibility["needs_effect_prediction"].astype(bool).sum()) if eligibility_count else 0
    needs_risk = int(eligibility["needs_risk_review"].astype(bool).sum()) if eligibility_count else 0
    needs_expected = int(eligibility["needs_expected_value_review"].astype(bool).sum()) if eligibility_count else 0
    check_count = int(len(checks)) if checks is not None else 0
    check_pass = int((checks["check_status"].astype(str) == "pass").sum()) if check_count else 0
    if review_count > 0 and review_count == eligibility_count == carry_count == needs_effect == needs_risk == needs_expected and check_count == check_pass:
        decision = "action_candidate_minimal_eligibility_contract_ready_without_final_judgment_or_generation"
    else:
        decision = "action_candidate_minimal_eligibility_contract_needs_review"
    return pd.DataFrame([{
        **BOUNDARY,
        "axis_review_count": review_count,
        "eligibility_row_count": eligibility_count,
        "carry_forward_row_count": carry_count,
        "candidate_form_allowed_count": allowed,
        "blocked_count": blocked,
        "needs_effect_prediction_count": needs_effect,
        "needs_risk_review_count": needs_risk,
        "needs_expected_value_review_count": needs_expected,
        "contract_check_count": check_count,
        "contract_check_pass_count": check_pass,
        "action_candidate_minimal_eligibility_contract_decision": decision,
        "next_task": "Task 2-8j-18: action-candidate form dry-run without effect prediction or execution",
    }], columns=REQUIRED_SUMMARY_COLUMNS)


def validate_action_candidate_minimal_eligibility_tables(eligibility: pd.DataFrame, carry: pd.DataFrame, checks: pd.DataFrame, final_summary: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    tables = {
        "eligibility": (eligibility, REQUIRED_ELIGIBILITY_COLUMNS),
        "carry": (carry, REQUIRED_CARRY_COLUMNS),
        "checks": (checks, REQUIRED_CHECK_COLUMNS),
        "final_summary": (final_summary, REQUIRED_SUMMARY_COLUMNS),
    }
    for name, (table, required) in tables.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_17_empty_table:{name}")
            continue
        missing = [c for c in required if c not in table.columns]
        if missing:
            errors.append(f"task2_8j_17_missing_columns:{name}:" + ",".join(missing))
            continue
        for col in [
            "validation_only", "minimal_eligibility_contract_only", "candidate_form_contract_only", "lightweight_risk_management_only",
            "source_action_axis_review_required", "trace_required", "no_op_carry_forward_required", "release_required",
            "rollback_required", "audit_required", "weak_strength_required", "non_execution_required",
            "effect_prediction_required_later", "risk_review_required_later", "expected_value_review_required_later", "no_op_preserved",
        ]:
            if not bool(table[col].astype(bool).all()):
                errors.append(f"task2_8j_17_required_true_not_all_true:{name}:{col}")
        if set(table["gt_main_map_name"].astype(str)) != {"static_pca_7"}:
            errors.append(f"task2_8j_17_wrong_gt_main_map_name:{name}")
        if set(table["gt_main_component_count"].astype(int)) != {7}:
            errors.append(f"task2_8j_17_wrong_gt_component_count:{name}")
        for col in FORBIDDEN_TRUE:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_17_forbidden_true:{name}:{col}")
    if eligibility is not None and not eligibility.empty:
        if not bool(eligibility["needs_effect_prediction"].astype(bool).all()):
            errors.append("task2_8j_17_effect_prediction_not_deferred")
        if not bool(eligibility["needs_risk_review"].astype(bool).all()):
            errors.append("task2_8j_17_risk_review_not_deferred")
        if not bool(eligibility["needs_expected_value_review"].astype(bool).all()):
            errors.append("task2_8j_17_expected_value_review_not_deferred")
        if not bool((eligibility["eligibility_status"].astype(str) == "minimal_eligibility_completed_without_candidate_generation").all()):
            errors.append("task2_8j_17_eligibility_status_wrong")
    if carry is not None and not carry.empty:
        if not bool(carry["no_op_default_preserved"].astype(bool).all()):
            errors.append("task2_8j_17_no_op_default_not_preserved")
        if not bool(carry["no_op_required_when_uncertain"].astype(bool).all()):
            errors.append("task2_8j_17_no_op_uncertainty_not_preserved")
    if checks is not None and not checks.empty:
        if not bool((checks["check_status"].astype(str) == "pass").all()):
            errors.append("task2_8j_17_check_failed")
    return errors


def build_and_validate_action_candidate_minimal_eligibility_contract(
    tracking_cfg: V2StructureChangeTrackingConfig | None = None,
    ot_cfg: OtObservationMapConfig | None = None,
    audit_cfg: OtAuditLayeringConfig | None = None,
    preservation_cfg: RelationToOtInformationPreservationConfig | None = None,
    split_cfg: ActionModuleInputSplitContractConfig | None = None,
    reception_cfg: TwoRouteReceptionDryRunConfig | None = None,
    prediction_contract_cfg: GameStructurePredictionInputContractConfig | None = None,
    prediction_envelope_cfg: GameStructurePredictionEnvelopeDryRunConfig | None = None,
    upper_layer_cfg: NewGtUpperLayerRevalidationConfig | None = None,
    material_contract_cfg: ActionAxisMaterialContractConfig | None = None,
    bundle_cfg: ActionAxisMaterialBundleDryRunConfig | None = None,
    axis_cfg: ActionAxisDryRunGenerationConfig | None = None,
    review_cfg: ActionAxisNonExecutionReviewConfig | None = None,
    cfg: ActionCandidateMinimalEligibilityContractConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    cfg = cfg or ActionCandidateMinimalEligibilityContractConfig()
    tracking_cfg = tracking_cfg or V2StructureChangeTrackingConfig()
    review, no_op, _review_checks, _review_final, task16_errors, task16_summary = build_and_validate_action_axis_non_execution_review(
        tracking_cfg=tracking_cfg,
        ot_cfg=ot_cfg or OtObservationMapConfig(),
        audit_cfg=audit_cfg or OtAuditLayeringConfig(),
        preservation_cfg=preservation_cfg or RelationToOtInformationPreservationConfig(),
        split_cfg=split_cfg or ActionModuleInputSplitContractConfig(),
        reception_cfg=reception_cfg or TwoRouteReceptionDryRunConfig(),
        prediction_contract_cfg=prediction_contract_cfg or GameStructurePredictionInputContractConfig(),
        prediction_envelope_cfg=prediction_envelope_cfg or GameStructurePredictionEnvelopeDryRunConfig(),
        upper_layer_cfg=upper_layer_cfg or NewGtUpperLayerRevalidationConfig(),
        material_contract_cfg=material_contract_cfg or ActionAxisMaterialContractConfig(),
        bundle_cfg=bundle_cfg or ActionAxisMaterialBundleDryRunConfig(),
        axis_cfg=axis_cfg or ActionAxisDryRunGenerationConfig(),
        cfg=review_cfg or ActionAxisNonExecutionReviewConfig(),
    )
    upstream_errors = [f"task2_8j_17_upstream_16_error:{e}" for e in task16_errors] if cfg.require_task16_ready else []
    eligibility = build_eligibility_table(review, no_op)
    carry = build_carry_forward_table(review, no_op)
    checks = build_contract_checks(eligibility, carry, upstream_errors, task16_summary)
    final_summary = build_final_summary(review, eligibility, carry, checks)
    errors = list(upstream_errors)
    errors.extend(validate_action_candidate_minimal_eligibility_tables(eligibility, carry, checks, final_summary))
    summary = {
        "gt_main_map_name": "static_pca_7",
        "gt_main_component_count": 7,
        "task16_decision": task16_summary.get("action_axis_non_execution_review_decision", ""),
        "axis_review_count": _safe_int(final_summary["axis_review_count"].iloc[0]) if not final_summary.empty else 0,
        "eligibility_row_count": _safe_int(final_summary["eligibility_row_count"].iloc[0]) if not final_summary.empty else 0,
        "carry_forward_row_count": _safe_int(final_summary["carry_forward_row_count"].iloc[0]) if not final_summary.empty else 0,
        "candidate_form_allowed_count": _safe_int(final_summary["candidate_form_allowed_count"].iloc[0]) if not final_summary.empty else 0,
        "blocked_count": _safe_int(final_summary["blocked_count"].iloc[0]) if not final_summary.empty else 0,
        "needs_effect_prediction_count": _safe_int(final_summary["needs_effect_prediction_count"].iloc[0]) if not final_summary.empty else 0,
        "needs_risk_review_count": _safe_int(final_summary["needs_risk_review_count"].iloc[0]) if not final_summary.empty else 0,
        "needs_expected_value_review_count": _safe_int(final_summary["needs_expected_value_review_count"].iloc[0]) if not final_summary.empty else 0,
        "contract_check_count": _safe_int(final_summary["contract_check_count"].iloc[0]) if not final_summary.empty else 0,
        "contract_check_pass_count": _safe_int(final_summary["contract_check_pass_count"].iloc[0]) if not final_summary.empty else 0,
        "action_candidate_minimal_eligibility_contract_decision": str(final_summary["action_candidate_minimal_eligibility_contract_decision"].iloc[0]) if not final_summary.empty else "empty",
        "expected_value_final_judgment_performed": False,
        "risk_final_judgment_performed": False,
        "action_effect_prediction_generated": False,
        "action_candidate_generated": False,
        "concrete_action_generated": False,
        "axis_executed": False,
        "real_actionmodule_called": False,
        "validation_errors": errors,
    }
    return eligibility, carry, checks, final_summary, errors, summary
