"""Task 2-8j-13: action-axis material contract RC1.

Purpose:
    Freeze the contract for what the action-module side may read when it later
    generates action-axis material from upper pressure, O_t observation context,
    game-structure prediction envelopes, and audit / NO_OP baseline information.

Position:
    Task 2-8j-12 revalidated the upper-pressure route after the static_pca_7
    G_t update.  Task 2-8j-11 created traceable game-structure prediction
    envelopes.  This task does not generate action axes.  It only defines the
    allowed material sources and design principles that must constrain the later
    action-axis generation step.

Core design principle:
    direction selection + state dependence + immediate release.
    The later action module should aim to intervene only at a suitable timing,
    place, direction, strength, and duration, and only when the total expected
    value clearly exceeds the NO_OP baseline.

Boundary:
    - material contract only
    - fixed static_pca_7 G_t assumptions are inherited from upstream validation
    - upper-pressure, O_t context, game-structure forecast, audit, and NO_OP
      baseline may be used as prepared inputs
    - v8 local audit is reserved as an optional later detail-check input
    - exploration-axis input is reserved but not used in this task
    - no action-axis generation, action candidate, concrete action, action-effect
      prediction, ActionModule call, runtime call, writeback, hidden-truth /
      future-information input, or axis mutation
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
from .pressure_action_task2_8j_11_game_structure_prediction_envelope_dry_run import (
    GameStructurePredictionEnvelopeDryRunConfig,
    build_and_validate_game_structure_prediction_envelope_dry_run,
)
from .pressure_action_task2_8j_12_new_gt_upper_layer_revalidation import (
    NewGtUpperLayerRevalidationConfig,
    build_and_validate_new_gt_upper_layer_revalidation,
)

TASK2_8J_13_VERSION = "action_axis_material_contract_rc1"
TASK2_8J_13_CONTRACT = (
    "Task2_8j_13_action_axis_material_contract__"
    "direction_selection_state_dependence_immediate_release__"
    "NO_OP_comparison_required__no_action_axes_no_action_candidates_no_runtime"
)

BOUNDARY = {
    "task2_8j_13_version": TASK2_8J_13_VERSION,
    "task2_8j_13_contract": TASK2_8J_13_CONTRACT,
    "validation_only": True,
    "material_contract_only": True,
    "action_axis_material_contract_only": True,
    "gt_main_map_name": "static_pca_7",
    "gt_main_component_count": 7,
    "upper_pressure_route_material_allowed": True,
    "ot_observation_context_material_allowed": True,
    "game_structure_prediction_material_allowed": True,
    "audit_material_allowed": True,
    "no_op_baseline_material_required": True,
    "direction_selection_required": True,
    "state_dependent_trigger_required": True,
    "immediate_release_required": True,
    "weak_local_reversible_required": True,
    "v8_local_audit_reserved_optional": True,
    "exploration_axis_input_reserved_not_used": True,
    "action_axis_generated": False,
    "action_candidate_generated": False,
    "concrete_action_generated": False,
    "action_effect_prediction_generated": False,
    "action_translation_performed": False,
    "action_input_converted": False,
    "action_frame_created": False,
    "real_actionmodule_called": False,
    "actionmodule_called": False,
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
    "action_axis_generated",
    "action_candidate_generated",
    "concrete_action_generated",
    "action_effect_prediction_generated",
    "action_translation_performed",
    "action_input_converted",
    "action_frame_created",
    "real_actionmodule_called",
    "actionmodule_called",
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

REQUIRED_MATERIAL_COLUMNS = list(BOUNDARY) + [
    "material_source_id",
    "material_source_name",
    "upstream_task",
    "source_status",
    "active_in_this_contract",
    "allowed_read_role",
    "permitted_fields",
    "forbidden_interpretation",
    "later_action_axis_material_role",
    "material_contract_status",
]

REQUIRED_PRINCIPLE_COLUMNS = list(BOUNDARY) + [
    "principle_id",
    "principle_name",
    "principle_description",
    "required_for_later_axis_generation",
    "no_op_baseline_relevance",
    "principle_status",
]

REQUIRED_READINESS_COLUMNS = list(BOUNDARY) + [
    "readiness_id",
    "upstream_task",
    "upstream_decision",
    "upstream_validation_error_count",
    "key_count_name",
    "key_count_value",
    "readiness_status",
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
    "material_source_count",
    "active_material_source_count",
    "reserved_material_source_count",
    "principle_count",
    "principle_pass_count",
    "readiness_count",
    "readiness_pass_count",
    "contract_check_count",
    "contract_check_pass_count",
    "action_axis_material_contract_decision",
    "next_task",
]


@dataclass(frozen=True)
class ActionAxisMaterialContractConfig:
    require_upstream_ready: bool = True


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def build_material_source_contract_table() -> pd.DataFrame:
    rows = [
        {
            **BOUNDARY,
            "material_source_id": "material_upper_pressure_001",
            "material_source_name": "upper_pressure_route_material",
            "upstream_task": "Task2_8j_12_new_gt_upper_layer_revalidation",
            "source_status": "required_active",
            "active_in_this_contract": True,
            "allowed_read_role": "what_to_weakly_bias_and_pressure_family_boundary",
            "permitted_fields": "pressure_family;source_mt_component;bounded_pressure_magnitude;pressure_polarity;pressure_time_scale;reversible;no_op_allowed;rollback_policy;safety_projection_status",
            "forbidden_interpretation": "do_not_treat_as_concrete_action_or_direct_action_axis;do_not_bypass_NO_OP_or_safety_projection",
            "later_action_axis_material_role": "goal_pressure_material_for_later_axis_generation",
            "material_contract_status": "ready_required_active_material",
        },
        {
            **BOUNDARY,
            "material_source_id": "material_ot_context_001",
            "material_source_name": "ot_observation_context_material",
            "upstream_task": "Task2_8j_7_to_7c_observation_map_and_trace_audit",
            "source_status": "required_active",
            "active_in_this_contract": True,
            "allowed_read_role": "where_and_what_is_happening_with_traceable_evidence",
            "permitted_fields": "source_observation_ids;source_relation_trace_ids;where;direction;intensity;confidence;evidence_source;source_trace;provenance",
            "forbidden_interpretation": "do_not_let_Ot_generate_upper_pressure;do_not_rewrite_Ot_inside_action_module;do_not_use_untraceable_observation",
            "later_action_axis_material_role": "location_and_context_material_for_later_axis_generation",
            "material_contract_status": "ready_required_active_material",
        },
        {
            **BOUNDARY,
            "material_source_id": "material_prediction_001",
            "material_source_name": "game_structure_prediction_material",
            "upstream_task": "Task2_8j_11_game_structure_prediction_envelope_dry_run",
            "source_status": "required_active",
            "active_in_this_contract": True,
            "allowed_read_role": "current_structure_forecast_of_likely_state_and_relation_tendency_without_action_assumption",
            "permitted_fields": "prediction_bundle_id;prediction_horizon;predicted_state_tendency;predicted_relation_tendency;confidence;uncertainty;validity_scope;assumption_current_structure_continues;source_relation_trace_ids",
            "forbidden_interpretation": "do_not_treat_as_action_effect_prediction;do_not_infer_intervention_effect_or_direct_action_weights",
            "later_action_axis_material_role": "direction_and_timing_material_for_later_axis_generation",
            "material_contract_status": "ready_required_active_material",
        },
        {
            **BOUNDARY,
            "material_source_id": "material_audit_001",
            "material_source_name": "audit_material",
            "upstream_task": "Task2_8j_7b_and_7c_audit_layers_and_trace_coverage",
            "source_status": "required_active",
            "active_in_this_contract": True,
            "allowed_read_role": "risk_confidence_change_centrality_residual_reason_split_for_gating_and_review",
            "permitted_fields": "audit_level;audit_reasons;risk_reason;confidence_reason;change_reason;centrality_reason;residual_reason;trace_status",
            "forbidden_interpretation": "do_not_collapse_audit_into_single_danger_boolean;do_not_ignore_review_before_action",
            "later_action_axis_material_role": "gate_material_for_state_dependence_NO_OP_and_immediate_release",
            "material_contract_status": "ready_required_active_material",
        },
        {
            **BOUNDARY,
            "material_source_id": "material_no_op_baseline_001",
            "material_source_name": "NO_OP_baseline_material",
            "upstream_task": "Task2_8j_13_contract_internal_requirement",
            "source_status": "required_active",
            "active_in_this_contract": True,
            "allowed_read_role": "baseline_for_total_expected_value_comparison_before_later_action_axis_generation",
            "permitted_fields": "no_op_allowed;bounded_pressure_magnitude;confidence;uncertainty;audit_level;rollback_policy;release_condition_placeholder",
            "forbidden_interpretation": "do_not_generate_axis_when_NO_OP_expected_value_is_not_clearly_exceeded",
            "later_action_axis_material_role": "baseline_material_for_generate_or_NO_OP_decision",
            "material_contract_status": "ready_required_active_material",
        },
        {
            **BOUNDARY,
            "material_source_id": "material_v8_local_audit_reserved_001",
            "material_source_name": "v8_local_audit_reserved_optional_material",
            "upstream_task": "future_or_external_v8_local_audit_information",
            "source_status": "reserved_optional_not_required_for_this_task",
            "active_in_this_contract": False,
            "allowed_read_role": "later_local_detail_check_before_or_after_action_axis_generation",
            "permitted_fields": "local_detail_observation;calibrated_confidence;unresolved;conflict;residual;lineage;sequence_context",
            "forbidden_interpretation": "do_not_make_v8_mandatory_for_this_contract;do_not_use_as_upper_pressure_or_concrete_action",
            "later_action_axis_material_role": "optional_detail_audit_material_after_core_route_is_ready",
            "material_contract_status": "reserved_optional_material_not_required",
        },
        {
            **BOUNDARY,
            "material_source_id": "material_exploration_axis_reserved_001",
            "material_source_name": "exploration_axis_reserved_material",
            "upstream_task": "future_exploration_axis_module",
            "source_status": "reserved_not_used_in_this_task",
            "active_in_this_contract": False,
            "allowed_read_role": "future_exploration_direction_support_only",
            "permitted_fields": "candidate_exploration_axis;coverage_gap;residual_gap;ambiguity_cluster;sandbox_status",
            "forbidden_interpretation": "do_not_mix_exploration_axis_into_current_action_axis_material_contract;do_not_use_as_current_pressure",
            "later_action_axis_material_role": "future_optional_exploration_material_after_core_action_route",
            "material_contract_status": "reserved_not_used_material",
        },
    ]
    return pd.DataFrame(rows, columns=REQUIRED_MATERIAL_COLUMNS)


def build_design_principle_table() -> pd.DataFrame:
    rows = [
        (
            "principle_direction_selection",
            "direction_selection",
            "Later action-axis generation must choose a direction from upper pressure plus game-structure tendency, not from raw arbitrary preference.",
            True,
            "NO_OP remains preferred if direction is not identifiable.",
        ),
        (
            "principle_state_dependence",
            "state_dependent_trigger",
            "Later action-axis material must include conditions for when the axis is active; constant always-on pressure is not the default.",
            True,
            "NO_OP remains preferred when the state condition is not met.",
        ),
        (
            "principle_immediate_release",
            "immediate_release",
            "Later action-axis material must include release conditions so pressure disappears when the triggering condition disappears.",
            True,
            "NO_OP or release is required when the danger condition has faded.",
        ),
        (
            "principle_weak_local_reversible",
            "weak_local_reversible",
            "Later action-axis material must preserve weak, local, reversible, bounded pressure and rollback compatibility.",
            True,
            "NO_OP wins when only strong or irreversible action would be available.",
        ),
        (
            "principle_no_op_comparison",
            "NO_OP_comparison_required",
            "Later action-axis generation must require clear total expected value over doing nothing before becoming eligible.",
            True,
            "NO_OP is the default baseline, not a failure state.",
        ),
        (
            "principle_audit_gating",
            "audit_gated_material",
            "Audit level and reasons must be carried into the later gate, including review-before-action and block-direct-action cases.",
            True,
            "NO_OP is required when audit blocks direct action or uncertainty dominates.",
        ),
        (
            "principle_route_separation",
            "route_separation_preserved",
            "Upper-pressure, O_t context, and prediction materials remain tagged by source until the action-module translation layer.",
            True,
            "NO_OP remains available if route conflict cannot be resolved.",
        ),
    ]
    out: list[dict] = []
    for principle_id, name, description, required, no_op in rows:
        out.append({
            **BOUNDARY,
            "principle_id": principle_id,
            "principle_name": name,
            "principle_description": description,
            "required_for_later_axis_generation": bool(required),
            "no_op_baseline_relevance": no_op,
            "principle_status": "principle_required_and_ready" if required else "principle_optional",
        })
    return pd.DataFrame(out, columns=REQUIRED_PRINCIPLE_COLUMNS)


def build_material_readiness_table(task11_summary: dict, task11_errors: list[str], task12_summary: dict, task12_errors: list[str]) -> pd.DataFrame:
    task11_decision = str(task11_summary.get("game_structure_prediction_envelope_dry_run_decision", ""))
    task12_decision = str(task12_summary.get("new_gt_upper_layer_revalidation_decision", ""))
    rows = [
        {
            **BOUNDARY,
            "readiness_id": "readiness_upper_pressure_route",
            "upstream_task": "Task2_8j_12",
            "upstream_decision": task12_decision,
            "upstream_validation_error_count": int(len(task12_errors)),
            "key_count_name": "upper_pressure_candidate_count",
            "key_count_value": _safe_int(task12_summary.get("upper_pressure_candidate_count", 0)),
            "readiness_status": "ready" if len(task12_errors) == 0 and task12_decision.startswith("new_static_pca_7_gt_upper_layer_revalidated") else "not_ready",
        },
        {
            **BOUNDARY,
            "readiness_id": "readiness_prediction_envelopes",
            "upstream_task": "Task2_8j_11",
            "upstream_decision": task11_decision,
            "upstream_validation_error_count": int(len(task11_errors)),
            "key_count_name": "prediction_envelope_count",
            "key_count_value": _safe_int(task11_summary.get("prediction_envelope_count", 0)),
            "readiness_status": "ready" if len(task11_errors) == 0 and task11_decision.startswith("game_structure_prediction_envelope_dry_run_created") else "not_ready",
        },
        {
            **BOUNDARY,
            "readiness_id": "readiness_source_trace",
            "upstream_task": "Task2_8j_11",
            "upstream_decision": task11_decision,
            "upstream_validation_error_count": int(len(task11_errors)),
            "key_count_name": "source_trace_preserved_count",
            "key_count_value": _safe_int(task11_summary.get("source_trace_preserved_count", 0)),
            "readiness_status": "ready" if _safe_int(task11_summary.get("source_trace_preserved_count", 0)) > 0 and len(task11_errors) == 0 else "not_ready",
        },
        {
            **BOUNDARY,
            "readiness_id": "readiness_safety_checks",
            "upstream_task": "Task2_8j_12",
            "upstream_decision": task12_decision,
            "upstream_validation_error_count": int(len(task12_errors)),
            "key_count_name": "safety_check_pass_count",
            "key_count_value": _safe_int(task12_summary.get("safety_check_pass_count", 0)),
            "readiness_status": "ready" if _safe_int(task12_summary.get("safety_check_count", 0)) == _safe_int(task12_summary.get("safety_check_pass_count", -1)) and len(task12_errors) == 0 else "not_ready",
        },
    ]
    return pd.DataFrame(rows, columns=REQUIRED_READINESS_COLUMNS)


def build_contract_checks(materials: pd.DataFrame, principles: pd.DataFrame, readiness: pd.DataFrame) -> pd.DataFrame:
    active_count = int(materials["active_in_this_contract"].astype(bool).sum()) if materials is not None and not materials.empty else 0
    reserved_count = int((~materials["active_in_this_contract"].astype(bool)).sum()) if materials is not None and not materials.empty else 0
    principle_ok = bool((principles["principle_status"].astype(str) == "principle_required_and_ready").all()) if principles is not None and not principles.empty else False
    readiness_ok = bool((readiness["readiness_status"].astype(str) == "ready").all()) if readiness is not None and not readiness.empty else False
    checks = [
        ("check_core_material_sources", "materials", "At least five active core material sources are defined.", True, active_count >= 5),
        ("check_reserved_sources", "materials", "V8 and exploration inputs are reserved but not active in this task.", True, reserved_count >= 2),
        ("check_principles_ready", "principles", "All design principles required for later axis generation are ready.", True, principle_ok),
        ("check_upstream_ready", "readiness", "Task2-8j-11 and Task2-8j-12 upstream results are ready.", True, readiness_ok),
        ("check_no_axis_generated", "boundary", "No action axis is generated in material contract.", False, bool(materials["action_axis_generated"].astype(bool).any()) if materials is not None and not materials.empty else True),
        ("check_no_action_candidate", "boundary", "No action candidate is generated in material contract.", False, bool(materials["action_candidate_generated"].astype(bool).any()) if materials is not None and not materials.empty else True),
        ("check_no_action_effect_prediction", "boundary", "No action-effect prediction is generated in material contract.", False, bool(materials["action_effect_prediction_generated"].astype(bool).any()) if materials is not None and not materials.empty else True),
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


def build_final_summary(materials: pd.DataFrame, principles: pd.DataFrame, readiness: pd.DataFrame, checks: pd.DataFrame) -> pd.DataFrame:
    material_count = int(len(materials)) if materials is not None else 0
    active_count = int(materials["active_in_this_contract"].astype(bool).sum()) if material_count else 0
    reserved_count = int((~materials["active_in_this_contract"].astype(bool)).sum()) if material_count else 0
    principle_count = int(len(principles)) if principles is not None else 0
    principle_pass = int((principles["principle_status"].astype(str) == "principle_required_and_ready").sum()) if principle_count else 0
    readiness_count = int(len(readiness)) if readiness is not None else 0
    readiness_pass = int((readiness["readiness_status"].astype(str) == "ready").sum()) if readiness_count else 0
    check_count = int(len(checks)) if checks is not None else 0
    check_pass = int((checks["check_status"].astype(str) == "pass").sum()) if check_count else 0
    if active_count >= 5 and reserved_count >= 2 and principle_count == principle_pass and readiness_count == readiness_pass and check_count == check_pass:
        decision = "action_axis_material_contract_ready_with_direction_selection_state_dependence_immediate_release_and_NO_OP_baseline"
    else:
        decision = "action_axis_material_contract_needs_review"
    return pd.DataFrame([{
        **BOUNDARY,
        "material_source_count": material_count,
        "active_material_source_count": active_count,
        "reserved_material_source_count": reserved_count,
        "principle_count": principle_count,
        "principle_pass_count": principle_pass,
        "readiness_count": readiness_count,
        "readiness_pass_count": readiness_pass,
        "contract_check_count": check_count,
        "contract_check_pass_count": check_pass,
        "action_axis_material_contract_decision": decision,
        "next_task": "Task 2-8j-14: action-axis material bundle dry-run without axis generation",
    }], columns=REQUIRED_SUMMARY_COLUMNS)


def validate_action_axis_material_contract_tables(materials: pd.DataFrame, principles: pd.DataFrame, readiness: pd.DataFrame, checks: pd.DataFrame, final_summary: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    tables = {
        "materials": (materials, REQUIRED_MATERIAL_COLUMNS),
        "principles": (principles, REQUIRED_PRINCIPLE_COLUMNS),
        "readiness": (readiness, REQUIRED_READINESS_COLUMNS),
        "checks": (checks, REQUIRED_CHECK_COLUMNS),
        "final_summary": (final_summary, REQUIRED_SUMMARY_COLUMNS),
    }
    for name, (table, required) in tables.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_13_empty_table:{name}")
            continue
        missing = [c for c in required if c not in table.columns]
        if missing:
            errors.append(f"task2_8j_13_missing_columns:{name}:" + ",".join(missing))
            continue
        for col in [
            "validation_only",
            "material_contract_only",
            "action_axis_material_contract_only",
            "upper_pressure_route_material_allowed",
            "ot_observation_context_material_allowed",
            "game_structure_prediction_material_allowed",
            "audit_material_allowed",
            "no_op_baseline_material_required",
            "direction_selection_required",
            "state_dependent_trigger_required",
            "immediate_release_required",
            "weak_local_reversible_required",
            "v8_local_audit_reserved_optional",
            "exploration_axis_input_reserved_not_used",
        ]:
            if not bool(table[col].astype(bool).all()):
                errors.append(f"task2_8j_13_required_true_not_all_true:{name}:{col}")
        if set(table["gt_main_map_name"].astype(str)) != {"static_pca_7"}:
            errors.append(f"task2_8j_13_wrong_gt_main_map_name:{name}")
        if set(table["gt_main_component_count"].astype(int)) != {7}:
            errors.append(f"task2_8j_13_wrong_gt_component_count:{name}")
        for col in FORBIDDEN_TRUE:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_13_forbidden_true:{name}:{col}")
    if materials is not None and not materials.empty:
        if int(materials["active_in_this_contract"].astype(bool).sum()) < 5:
            errors.append("task2_8j_13_active_material_source_count_too_low")
        if "NO_OP_baseline_material" not in set(materials["material_source_name"].astype(str)):
            errors.append("task2_8j_13_missing_no_op_baseline_material")
    if principles is not None and not principles.empty:
        required_names = {"direction_selection", "state_dependent_trigger", "immediate_release", "NO_OP_comparison_required"}
        if not required_names.issubset(set(principles["principle_name"].astype(str))):
            errors.append("task2_8j_13_missing_core_design_principles")
        if not bool((principles["principle_status"].astype(str) == "principle_required_and_ready").all()):
            errors.append("task2_8j_13_principle_not_ready")
    if readiness is not None and not readiness.empty:
        if not bool((readiness["readiness_status"].astype(str) == "ready").all()):
            errors.append("task2_8j_13_upstream_not_ready")
    if checks is not None and not checks.empty:
        if not bool((checks["check_status"].astype(str) == "pass").all()):
            errors.append("task2_8j_13_contract_check_failed")
    return errors


def build_and_validate_action_axis_material_contract(
    tracking_cfg: V2StructureChangeTrackingConfig | None = None,
    ot_cfg: OtObservationMapConfig | None = None,
    audit_cfg: OtAuditLayeringConfig | None = None,
    preservation_cfg: RelationToOtInformationPreservationConfig | None = None,
    split_cfg: ActionModuleInputSplitContractConfig | None = None,
    reception_cfg: TwoRouteReceptionDryRunConfig | None = None,
    prediction_contract_cfg: GameStructurePredictionInputContractConfig | None = None,
    prediction_envelope_cfg: GameStructurePredictionEnvelopeDryRunConfig | None = None,
    upper_layer_cfg: NewGtUpperLayerRevalidationConfig | None = None,
    cfg: ActionAxisMaterialContractConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    cfg = cfg or ActionAxisMaterialContractConfig()
    tracking_cfg = tracking_cfg or V2StructureChangeTrackingConfig()
    _envelopes, _source_trace, _checks11, _final11, task11_errors, task11_summary = build_and_validate_game_structure_prediction_envelope_dry_run(
        tracking_cfg,
        ot_cfg or OtObservationMapConfig(),
        audit_cfg or OtAuditLayeringConfig(),
        preservation_cfg or RelationToOtInformationPreservationConfig(),
        split_cfg or ActionModuleInputSplitContractConfig(),
        reception_cfg or TwoRouteReceptionDryRunConfig(),
        prediction_contract_cfg or GameStructurePredictionInputContractConfig(),
        prediction_envelope_cfg or GameStructurePredictionEnvelopeDryRunConfig(),
    )
    _gk, _mt, _pressure, _safety, _final12, task12_errors, task12_summary = build_and_validate_new_gt_upper_layer_revalidation(
        tracking_cfg,
        upper_layer_cfg or NewGtUpperLayerRevalidationConfig(),
    )
    upstream_errors = []
    if cfg.require_upstream_ready:
        upstream_errors.extend([f"task2_8j_13_upstream_11_error:{e}" for e in task11_errors])
        upstream_errors.extend([f"task2_8j_13_upstream_12_error:{e}" for e in task12_errors])
    materials = build_material_source_contract_table()
    principles = build_design_principle_table()
    readiness = build_material_readiness_table(task11_summary, task11_errors, task12_summary, task12_errors)
    checks = build_contract_checks(materials, principles, readiness)
    final_summary = build_final_summary(materials, principles, readiness, checks)
    errors = list(upstream_errors)
    errors.extend(validate_action_axis_material_contract_tables(materials, principles, readiness, checks, final_summary))
    summary = {
        "gt_main_map_name": "static_pca_7",
        "gt_main_component_count": 7,
        "task11_decision": task11_summary.get("game_structure_prediction_envelope_dry_run_decision", ""),
        "task12_decision": task12_summary.get("new_gt_upper_layer_revalidation_decision", ""),
        "material_source_count": _safe_int(final_summary["material_source_count"].iloc[0]) if not final_summary.empty else 0,
        "active_material_source_count": _safe_int(final_summary["active_material_source_count"].iloc[0]) if not final_summary.empty else 0,
        "reserved_material_source_count": _safe_int(final_summary["reserved_material_source_count"].iloc[0]) if not final_summary.empty else 0,
        "principle_count": _safe_int(final_summary["principle_count"].iloc[0]) if not final_summary.empty else 0,
        "principle_pass_count": _safe_int(final_summary["principle_pass_count"].iloc[0]) if not final_summary.empty else 0,
        "readiness_count": _safe_int(final_summary["readiness_count"].iloc[0]) if not final_summary.empty else 0,
        "readiness_pass_count": _safe_int(final_summary["readiness_pass_count"].iloc[0]) if not final_summary.empty else 0,
        "contract_check_count": _safe_int(final_summary["contract_check_count"].iloc[0]) if not final_summary.empty else 0,
        "contract_check_pass_count": _safe_int(final_summary["contract_check_pass_count"].iloc[0]) if not final_summary.empty else 0,
        "action_axis_material_contract_decision": str(final_summary["action_axis_material_contract_decision"].iloc[0]) if not final_summary.empty else "empty",
        "action_axis_generated": False,
        "action_candidate_generated": False,
        "action_effect_prediction_generated": False,
        "real_actionmodule_called": False,
        "validation_errors": errors,
    }
    return materials, principles, readiness, checks, final_summary, errors, summary
