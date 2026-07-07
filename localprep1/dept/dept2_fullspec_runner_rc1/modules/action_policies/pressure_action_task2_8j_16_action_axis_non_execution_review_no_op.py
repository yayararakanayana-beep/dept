"""Task 2-8j-16: action-axis non-execution review and NO_OP comparison RC1.

Purpose:
    Review Task 2-8j-15 dry-run action axes without execution and compare each
    axis against the NO_OP baseline.  The review decides whether a dry-run axis
    may proceed to later candidate-review preparation, or should remain NO_OP /
    review-only, while preserving traceability and all safety gates.

Position:
    Task 2-8j-15 created non-executable dry-run action-axis records.  This task
    reviews those axes; it does not create concrete actions, action candidates,
    action-effect predictions, runtime inputs, or ActionModule calls.

Core design principle:
    direction selection + state dependence + immediate release, with weak / local
    / reversible strength, rollback compatibility, audit gating, and explicit
    total expected-value comparison against the NO_OP baseline.

Boundary:
    - non-execution review only
    - NO_OP comparison only
    - fixed static_pca_7 upstream assumption
    - source action-axis traces must remain preserved
    - no concrete action, no action candidate, no action-effect prediction
    - no ActionModule call, runtime call, writeback, hidden-truth / future-
      information input, or axis mutation
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
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
from .pressure_action_task2_8j_15_action_axis_dry_run_generation import (
    ActionAxisDryRunGenerationConfig,
    build_and_validate_action_axis_dry_run_generation,
)

TASK2_8J_16_VERSION = "action_axis_non_execution_review_no_op_rc1"
TASK2_8J_16_CONTRACT = (
    "Task2_8j_16_action_axis_non_execution_review_and_NO_OP_comparison__"
    "expected_value_gate_audit_gate_release_rollback_review__"
    "no_execution_no_concrete_action_no_action_candidate_no_runtime"
)

BOUNDARY = {
    "task2_8j_16_version": TASK2_8J_16_VERSION,
    "task2_8j_16_contract": TASK2_8J_16_CONTRACT,
    "validation_only": True,
    "non_execution_review_only": True,
    "no_op_comparison_only": True,
    "action_axis_review_only": True,
    "gt_main_map_name": "static_pca_7",
    "gt_main_component_count": 7,
    "source_action_axis_required": True,
    "direction_selection_review_required": True,
    "state_dependent_trigger_review_required": True,
    "immediate_release_review_required": True,
    "weak_local_reversible_review_required": True,
    "no_op_baseline_comparison_required": True,
    "rollback_review_required": True,
    "audit_gate_review_required": True,
    "route_tags_preserved": True,
    "source_traces_preserved": True,
    "v8_local_audit_reserved_optional": True,
    "exploration_axis_input_reserved_not_used": True,
    "concrete_action_generated": False,
    "action_candidate_generated": False,
    "action_effect_prediction_generated": False,
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
    "concrete_action_generated",
    "action_candidate_generated",
    "action_effect_prediction_generated",
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

REQUIRED_REVIEW_COLUMNS = list(BOUNDARY) + [
    "review_id",
    "action_axis_id",
    "source_material_bundle_id",
    "axis_kind",
    "axis_status",
    "direction_review_status",
    "state_trigger_review_status",
    "release_review_status",
    "rollback_review_status",
    "audit_review_status",
    "strength_review_status",
    "trace_review_status",
    "expected_value_gate_status",
    "no_op_comparison_status",
    "non_execution_review_decision",
    "later_candidate_review_allowed",
    "review_status",
]

REQUIRED_NO_OP_COLUMNS = list(BOUNDARY) + [
    "comparison_id",
    "action_axis_id",
    "no_op_baseline_score",
    "axis_expected_value_proxy",
    "axis_minus_no_op_margin",
    "no_op_default_preserved",
    "no_op_required_when_uncertain",
    "comparison_basis",
    "no_op_comparison_decision",
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
    "reviewed_axis_count",
    "no_op_comparison_count",
    "review_check_count",
    "review_check_pass_count",
    "later_candidate_review_allowed_count",
    "no_op_preferred_or_required_count",
    "release_review_pass_count",
    "rollback_review_pass_count",
    "audit_review_pass_count",
    "strength_review_pass_count",
    "action_axis_non_execution_review_decision",
    "next_task",
]


@dataclass(frozen=True)
class ActionAxisNonExecutionReviewConfig:
    require_task15_ready: bool = True
    max_strength_bound: float = 0.20
    no_op_baseline_score: float = 0.50
    min_expected_value_margin: float = 0.02


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return float(default)
    if not np.isfinite(out):
        return float(default)
    return float(out)


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def _axis_expected_value_proxy(axis_row, cfg: ActionAxisNonExecutionReviewConfig) -> float:
    eligible = bool(axis_row.dry_run_axis_eligible_for_later_candidate_generation)
    strength = min(cfg.max_strength_bound, max(0.0, _safe_float(axis_row.strength_bound)))
    gate_bonus = 0.10 if "pass" in str(axis_row.expected_value_gate_status) else 0.0
    direction_bonus = 0.06 if "direction_selection_material" in str(axis_row.direction_selector) else 0.0
    release_bonus = 0.04 if "immediate_release_material_required" in str(axis_row.release_condition) else 0.0
    weak_penalty = 0.00 if strength <= cfg.max_strength_bound else 0.30
    eligible_bonus = 0.10 if eligible else -0.08
    return float(max(0.0, min(1.0, cfg.no_op_baseline_score + gate_bonus + direction_bonus + release_bonus + eligible_bonus - weak_penalty)))


def build_no_op_comparison_table(axes: pd.DataFrame, cfg: ActionAxisNonExecutionReviewConfig | None = None) -> pd.DataFrame:
    cfg = cfg or ActionAxisNonExecutionReviewConfig()
    if axes is None or axes.empty:
        return pd.DataFrame(columns=REQUIRED_NO_OP_COLUMNS)
    rows: list[dict] = []
    for row in axes.itertuples(index=False):
        baseline = float(cfg.no_op_baseline_score)
        axis_score = _axis_expected_value_proxy(row, cfg)
        margin = axis_score - baseline
        eligible = bool(row.dry_run_axis_eligible_for_later_candidate_generation)
        if eligible and margin >= cfg.min_expected_value_margin:
            decision = "axis_expected_value_proxy_exceeds_NO_OP_for_later_review"
        else:
            decision = "NO_OP_or_review_preferred_before_later_candidate_generation"
        rows.append({
            **BOUNDARY,
            "comparison_id": f"no_op_comparison_{row.action_axis_id}",
            "action_axis_id": str(row.action_axis_id),
            "no_op_baseline_score": baseline,
            "axis_expected_value_proxy": axis_score,
            "axis_minus_no_op_margin": margin,
            "no_op_default_preserved": True,
            "no_op_required_when_uncertain": True,
            "comparison_basis": "dry_run_axis_material_only_no_action_effect_prediction",
            "no_op_comparison_decision": decision,
        })
    return pd.DataFrame(rows, columns=REQUIRED_NO_OP_COLUMNS)


def build_axis_non_execution_review_table(axes: pd.DataFrame, no_op: pd.DataFrame, trace_table: pd.DataFrame, cfg: ActionAxisNonExecutionReviewConfig | None = None) -> pd.DataFrame:
    cfg = cfg or ActionAxisNonExecutionReviewConfig()
    if axes is None or axes.empty:
        return pd.DataFrame(columns=REQUIRED_REVIEW_COLUMNS)
    no_op_lookup = {str(r.action_axis_id): str(r.no_op_comparison_decision) for r in no_op.itertuples(index=False)} if no_op is not None and not no_op.empty else {}
    trace_ids = set(trace_table["action_axis_id"].astype(str)) if trace_table is not None and not trace_table.empty else set()
    rows: list[dict] = []
    for row in axes.itertuples(index=False):
        axis_id = str(row.action_axis_id)
        direction_ok = "direction_selection_material" in str(row.direction_selector)
        trigger_ok = "state_dependent_trigger_material" in str(row.timing_gate)
        release_ok = "immediate_release_material_required" in str(row.release_condition)
        rollback_ok = bool(str(row.rollback_condition))
        audit_ok = "audit_level=" in str(row.audit_gate)
        strength_ok = _safe_float(row.strength_bound) <= cfg.max_strength_bound
        trace_ok = axis_id in trace_ids
        no_op_decision = no_op_lookup.get(axis_id, "NO_OP_or_review_preferred_before_later_candidate_generation")
        allow = bool(
            direction_ok
            and trigger_ok
            and release_ok
            and rollback_ok
            and audit_ok
            and strength_ok
            and trace_ok
            and no_op_decision.startswith("axis_expected_value_proxy_exceeds_NO_OP")
        )
        rows.append({
            **BOUNDARY,
            "review_id": f"non_execution_review_{axis_id}",
            "action_axis_id": axis_id,
            "source_material_bundle_id": str(row.source_material_bundle_id),
            "axis_kind": str(row.axis_kind),
            "axis_status": str(row.axis_status),
            "direction_review_status": "pass_direction_selection_material" if direction_ok else "review_direction_missing",
            "state_trigger_review_status": "pass_state_dependent_trigger_material" if trigger_ok else "review_state_trigger_missing",
            "release_review_status": "pass_immediate_release_material" if release_ok else "review_release_missing",
            "rollback_review_status": "pass_rollback_material" if rollback_ok else "review_rollback_missing",
            "audit_review_status": "pass_audit_gate_material" if audit_ok else "review_audit_gate_missing",
            "strength_review_status": "pass_weak_strength_bound" if strength_ok else "review_strength_too_high",
            "trace_review_status": "pass_axis_trace_preserved" if trace_ok else "review_trace_missing",
            "expected_value_gate_status": str(row.expected_value_gate_status),
            "no_op_comparison_status": no_op_decision,
            "non_execution_review_decision": "allow_later_candidate_review_non_executable" if allow else "keep_NO_OP_or_review_non_executable",
            "later_candidate_review_allowed": bool(allow),
            "review_status": "review_completed_non_executable",
        })
    return pd.DataFrame(rows, columns=REQUIRED_REVIEW_COLUMNS)


def build_review_checks(review: pd.DataFrame, no_op: pd.DataFrame, task15_errors: list[str], task15_summary: dict) -> pd.DataFrame:
    has_reviews = bool(review is not None and not review.empty)
    has_no_op = bool(no_op is not None and not no_op.empty)
    task15_ready = len(task15_errors) == 0 and str(task15_summary.get("action_axis_dry_run_generation_decision", "")).startswith("action_axis_dry_run_generation_ready")
    checks = [
        ("check_task15_ready", "upstream", "Task2-8j-15 dry-run axes are ready.", True, task15_ready),
        ("check_reviews_created", "review", "Every axis receives a non-execution review row.", True, has_reviews),
        ("check_no_op_comparisons_created", "NO_OP", "Every axis receives a NO_OP comparison row.", True, has_no_op and len(no_op) == len(review)),
        ("check_release_review", "release", "Immediate-release review passes for every axis.", True, bool(review["release_review_status"].astype(str).str.startswith("pass").all()) if has_reviews else False),
        ("check_rollback_review", "rollback", "Rollback review passes for every axis.", True, bool(review["rollback_review_status"].astype(str).str.startswith("pass").all()) if has_reviews else False),
        ("check_audit_review", "audit", "Audit gate review passes for every axis.", True, bool(review["audit_review_status"].astype(str).str.startswith("pass").all()) if has_reviews else False),
        ("check_strength_review", "strength", "Strength review stays weak for every axis.", True, bool(review["strength_review_status"].astype(str).str.startswith("pass").all()) if has_reviews else False),
        ("check_no_op_default_preserved", "NO_OP", "NO_OP remains explicitly preserved.", True, bool(no_op["no_op_default_preserved"].astype(bool).all()) if has_no_op else False),
        ("check_no_concrete_action", "boundary", "No concrete action is generated.", False, bool(review["concrete_action_generated"].astype(bool).any()) if has_reviews else True),
        ("check_no_action_candidate", "boundary", "No action candidate is generated.", False, bool(review["action_candidate_generated"].astype(bool).any()) if has_reviews else True),
        ("check_no_action_effect_prediction", "boundary", "No action-effect prediction is generated.", False, bool(review["action_effect_prediction_generated"].astype(bool).any()) if has_reviews else True),
        ("check_no_execution", "boundary", "No axis is executed.", False, bool(review["axis_executed"].astype(bool).any()) if has_reviews else True),
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


def build_final_summary(review: pd.DataFrame, no_op: pd.DataFrame, checks: pd.DataFrame) -> pd.DataFrame:
    review_count = int(len(review)) if review is not None else 0
    no_op_count = int(len(no_op)) if no_op is not None else 0
    check_count = int(len(checks)) if checks is not None else 0
    check_pass = int((checks["check_status"].astype(str) == "pass").sum()) if check_count else 0
    allowed_count = int(review["later_candidate_review_allowed"].astype(bool).sum()) if review_count else 0
    no_op_required = int(no_op["no_op_comparison_decision"].astype(str).str.contains("NO_OP_or_review").sum()) if no_op_count else 0
    release_pass = int(review["release_review_status"].astype(str).str.startswith("pass").sum()) if review_count else 0
    rollback_pass = int(review["rollback_review_status"].astype(str).str.startswith("pass").sum()) if review_count else 0
    audit_pass = int(review["audit_review_status"].astype(str).str.startswith("pass").sum()) if review_count else 0
    strength_pass = int(review["strength_review_status"].astype(str).str.startswith("pass").sum()) if review_count else 0
    if review_count > 0 and review_count == no_op_count == release_pass == rollback_pass == audit_pass == strength_pass and check_count == check_pass:
        decision = "action_axis_non_execution_review_and_NO_OP_comparison_ready_without_execution"
    else:
        decision = "action_axis_non_execution_review_and_NO_OP_comparison_needs_review"
    return pd.DataFrame([{
        **BOUNDARY,
        "reviewed_axis_count": review_count,
        "no_op_comparison_count": no_op_count,
        "review_check_count": check_count,
        "review_check_pass_count": check_pass,
        "later_candidate_review_allowed_count": allowed_count,
        "no_op_preferred_or_required_count": no_op_required,
        "release_review_pass_count": release_pass,
        "rollback_review_pass_count": rollback_pass,
        "audit_review_pass_count": audit_pass,
        "strength_review_pass_count": strength_pass,
        "action_axis_non_execution_review_decision": decision,
        "next_task": "Task 2-8j-17: action-candidate pre-generation contract without execution",
    }], columns=REQUIRED_SUMMARY_COLUMNS)


def validate_action_axis_non_execution_review_tables(review: pd.DataFrame, no_op: pd.DataFrame, checks: pd.DataFrame, final_summary: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    tables = {
        "review": (review, REQUIRED_REVIEW_COLUMNS),
        "no_op": (no_op, REQUIRED_NO_OP_COLUMNS),
        "checks": (checks, REQUIRED_CHECK_COLUMNS),
        "final_summary": (final_summary, REQUIRED_SUMMARY_COLUMNS),
    }
    for name, (table, required) in tables.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_16_empty_table:{name}")
            continue
        missing = [c for c in required if c not in table.columns]
        if missing:
            errors.append(f"task2_8j_16_missing_columns:{name}:" + ",".join(missing))
            continue
        for col in [
            "validation_only", "non_execution_review_only", "no_op_comparison_only", "action_axis_review_only",
            "source_action_axis_required", "direction_selection_review_required", "state_dependent_trigger_review_required",
            "immediate_release_review_required", "weak_local_reversible_review_required", "no_op_baseline_comparison_required",
            "rollback_review_required", "audit_gate_review_required", "route_tags_preserved", "source_traces_preserved",
            "v8_local_audit_reserved_optional", "exploration_axis_input_reserved_not_used",
        ]:
            if not bool(table[col].astype(bool).all()):
                errors.append(f"task2_8j_16_required_true_not_all_true:{name}:{col}")
        if set(table["gt_main_map_name"].astype(str)) != {"static_pca_7"}:
            errors.append(f"task2_8j_16_wrong_gt_main_map_name:{name}")
        if set(table["gt_main_component_count"].astype(int)) != {7}:
            errors.append(f"task2_8j_16_wrong_gt_component_count:{name}")
        for col in FORBIDDEN_TRUE:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_16_forbidden_true:{name}:{col}")
    if review is not None and not review.empty:
        for col in ["release_review_status", "rollback_review_status", "audit_review_status", "strength_review_status", "trace_review_status"]:
            if not bool(review[col].astype(str).str.startswith("pass").all()):
                errors.append(f"task2_8j_16_review_not_pass:{col}")
        if not bool((review["review_status"].astype(str) == "review_completed_non_executable").all()):
            errors.append("task2_8j_16_review_not_completed")
    if no_op is not None and not no_op.empty:
        if not bool(no_op["no_op_default_preserved"].astype(bool).all()):
            errors.append("task2_8j_16_no_op_default_not_preserved")
        if not bool(no_op["no_op_required_when_uncertain"].astype(bool).all()):
            errors.append("task2_8j_16_no_op_uncertainty_gate_missing")
    if checks is not None and not checks.empty:
        if not bool((checks["check_status"].astype(str) == "pass").all()):
            errors.append("task2_8j_16_check_failed")
    return errors


def build_and_validate_action_axis_non_execution_review(
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
    cfg: ActionAxisNonExecutionReviewConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    cfg = cfg or ActionAxisNonExecutionReviewConfig()
    tracking_cfg = tracking_cfg or V2StructureChangeTrackingConfig()
    axes, trace_table, _axis_checks, _axis_final, task15_errors, task15_summary = build_and_validate_action_axis_dry_run_generation(
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
        cfg=axis_cfg or ActionAxisDryRunGenerationConfig(),
    )
    upstream_errors = [f"task2_8j_16_upstream_15_error:{e}" for e in task15_errors] if cfg.require_task15_ready else []
    no_op = build_no_op_comparison_table(axes, cfg)
    review = build_axis_non_execution_review_table(axes, no_op, trace_table, cfg)
    checks = build_review_checks(review, no_op, upstream_errors, task15_summary)
    final_summary = build_final_summary(review, no_op, checks)
    errors = list(upstream_errors)
    errors.extend(validate_action_axis_non_execution_review_tables(review, no_op, checks, final_summary))
    summary = {
        "gt_main_map_name": "static_pca_7",
        "gt_main_component_count": 7,
        "task15_decision": task15_summary.get("action_axis_dry_run_generation_decision", ""),
        "reviewed_axis_count": _safe_int(final_summary["reviewed_axis_count"].iloc[0]) if not final_summary.empty else 0,
        "no_op_comparison_count": _safe_int(final_summary["no_op_comparison_count"].iloc[0]) if not final_summary.empty else 0,
        "review_check_count": _safe_int(final_summary["review_check_count"].iloc[0]) if not final_summary.empty else 0,
        "review_check_pass_count": _safe_int(final_summary["review_check_pass_count"].iloc[0]) if not final_summary.empty else 0,
        "later_candidate_review_allowed_count": _safe_int(final_summary["later_candidate_review_allowed_count"].iloc[0]) if not final_summary.empty else 0,
        "no_op_preferred_or_required_count": _safe_int(final_summary["no_op_preferred_or_required_count"].iloc[0]) if not final_summary.empty else 0,
        "action_axis_non_execution_review_decision": str(final_summary["action_axis_non_execution_review_decision"].iloc[0]) if not final_summary.empty else "empty",
        "concrete_action_generated": False,
        "action_candidate_generated": False,
        "action_effect_prediction_generated": False,
        "axis_executed": False,
        "real_actionmodule_called": False,
        "validation_errors": errors,
    }
    return review, no_op, checks, final_summary, errors, summary
