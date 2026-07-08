"""Task 2-8j-8: action-module input split contract RC1.

Purpose:
    Define the contract for passing two separate input routes to the action
    module: the H-DEPT upper-pressure route and the O_t observation-map route.

Position:
    Task 2-8j-7c confirmed that relation-field -> O_t coarse-graining keeps
    traceable evidence.  This task does not create pressure and does not call
    the action module.  It only freezes the interface contract: both routes may
    later enter the action module, but they must remain separate until the
    action module's system-dependent translation layer.

Boundary:
    - contract validation only
    - fixed static_pca_7 main map
    - upper-pressure route and O_t route are separate sibling inputs
    - O_t does not generate H-DEPT pressure
    - H-DEPT pressure does not rewrite O_t
    - action module is not called and no concrete action input is created
    - no runtime call, writeback, hidden-truth / future-information input, or axis mutation
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .pressure_action_task2_8j_6c_v2_structure_change_relation_field_tracking import V2StructureChangeTrackingConfig
from .pressure_action_task2_8j_7_ot_observation_map_from_relation_field import OtObservationMapConfig
from .pressure_action_task2_8j_7b_ot_audit_layering import OtAuditLayeringConfig
from .pressure_action_task2_8j_7c_relation_to_ot_information_preservation_audit import (
    RelationToOtInformationPreservationConfig,
    build_and_validate_relation_to_ot_information_preservation_audit,
)

TASK2_8J_8_VERSION = "action_module_input_split_contract_rc1"
TASK2_8J_8_CONTRACT = (
    "Task2_8j_8_action_module_input_split_contract__"
    "upper_pressure_route_and_Ot_observation_route_separate__"
    "contract_only_no_actionmodule_no_runtime_no_writeback"
)

BOUNDARY = {
    "task2_8j_8_version": TASK2_8J_8_VERSION,
    "task2_8j_8_contract": TASK2_8J_8_CONTRACT,
    "validation_only": True,
    "contract_only": True,
    "gt_main_map_name": "static_pca_7",
    "gt_main_component_count": 7,
    "upper_pressure_route_separate": True,
    "ot_observation_route_separate": True,
    "routes_may_meet_only_inside_action_module_translation": True,
    "upper_pressure_generated_here": False,
    "ot_generated_from_upper_pressure": False,
    "upper_pressure_rewrites_ot": False,
    "ot_generates_upper_pressure": False,
    "action_module_input_object_created": False,
    "action_input_converted": False,
    "action_frame_created": False,
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
    "upper_pressure_generated_here",
    "ot_generated_from_upper_pressure",
    "upper_pressure_rewrites_ot",
    "ot_generates_upper_pressure",
    "action_module_input_object_created",
    "action_input_converted",
    "action_frame_created",
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

REQUIRED_ROUTE_COLUMNS = list(BOUNDARY) + [
    "route_id",
    "route_name",
    "route_role",
    "route_source",
    "payload_status_in_this_task",
    "required_payload_fields",
    "forbidden_payload_fields",
    "action_module_port",
    "merge_policy",
    "route_contract_status",
]

REQUIRED_PORT_COLUMNS = list(BOUNDARY) + [
    "action_module_port",
    "accepted_route",
    "accepted_source",
    "required_input_kind",
    "action_module_may_read",
    "action_module_must_not_read",
    "translation_layer_responsibility",
    "port_contract_status",
]

REQUIRED_SEPARATION_COLUMNS = list(BOUNDARY) + [
    "separation_rule",
    "rule_description",
    "required_value",
    "observed_value",
    "separation_status",
]

REQUIRED_READINESS_COLUMNS = list(BOUNDARY) + [
    "readiness_source",
    "source_decision",
    "source_validation_error_count",
    "source_changed_relation_coverage_rate",
    "source_audit_trace_coverage_rate",
    "observation_route_ready",
    "upper_pressure_route_schema_ready",
    "action_module_input_split_ready",
    "readiness_status",
]

REQUIRED_SUMMARY_COLUMNS = list(BOUNDARY) + [
    "route_contract_count",
    "action_module_port_count",
    "separation_rule_count",
    "separation_pass_count",
    "readiness_row_count",
    "observation_route_ready_count",
    "upper_pressure_route_schema_ready_count",
    "action_module_input_split_contract_decision",
    "next_task",
]


@dataclass(frozen=True)
class ActionModuleInputSplitContractConfig:
    require_relation_to_ot_preservation: bool = True


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return float(default)
    if not np.isfinite(out):
        return float(default)
    return float(out)


def build_route_contract_table() -> pd.DataFrame:
    rows = [
        {
            **BOUNDARY,
            "route_id": "route_upper_pressure_001",
            "route_name": "upper_pressure_route",
            "route_role": "weak_directional_pressure_from_H_DEPT_or_bridge_route",
            "route_source": "G_t_global_plus_K_t_global_via_H_DEPT_or_bridge_not_generated_here",
            "payload_status_in_this_task": "schema_only_no_pressure_payload_created",
            "required_payload_fields": "pressure_bundle_id;pressure_axis_or_family;polarity;magnitude_bound;time_scale;reversibility;no_op_allowed;rollback_policy;provenance;confidence",
            "forbidden_payload_fields": "raw_relation_field;ot_observation_units;direct_action_weights;concrete_action;runtime_policy_input;hidden_truth;future_information",
            "action_module_port": "upper_pressure_input_port",
            "merge_policy": "may_meet_observation_route_only_inside_action_module_translation_layer",
            "route_contract_status": "upper_pressure_route_schema_ready_but_payload_not_created_here",
        },
        {
            **BOUNDARY,
            "route_id": "route_ot_observation_001",
            "route_name": "ot_observation_map_route",
            "route_role": "where_direction_intensity_confidence_evidence_audit_for_action_module_reference",
            "route_source": "Task2_8j_7c_traceable_O_t_observation_map",
            "payload_status_in_this_task": "schema_and_readiness_checked_from_O_t_evidence",
            "required_payload_fields": "observation_id;observation_kind;where_signal;direction_from;direction_to;direction_polarity;intensity;confidence;evidence_source;evidence_summary;lifecycle;audit_level;audit_reasons;source_trace_reference",
            "forbidden_payload_fields": "pressure_axis_or_family;pressure_magnitude;direct_action_weights;concrete_action;runtime_policy_input;hidden_truth;future_information",
            "action_module_port": "ot_observation_input_port",
            "merge_policy": "may_meet_upper_pressure_route_only_inside_action_module_translation_layer",
            "route_contract_status": "ot_observation_route_schema_ready_with_traceable_evidence",
        },
    ]
    return pd.DataFrame(rows, columns=REQUIRED_ROUTE_COLUMNS)


def build_action_module_port_contract_table() -> pd.DataFrame:
    rows = [
        {
            **BOUNDARY,
            "action_module_port": "upper_pressure_input_port",
            "accepted_route": "upper_pressure_route",
            "accepted_source": "prepared_H_DEPT_or_bridge_pressure_bundle",
            "required_input_kind": "bounded_weak_reversible_pressure_direction",
            "action_module_may_read": "pressure_axis_or_family;polarity;magnitude_bound;time_scale;reversibility;no_op_allowed;rollback_policy;provenance;confidence",
            "action_module_must_not_read": "raw_G_t;raw_K_t;raw_relation_field;O_t_internal_tables;hidden_truth;future_information",
            "translation_layer_responsibility": "translate_weak_pressure_direction_to_system_dependent_action_candidates_without_direct_DEPT_access",
            "port_contract_status": "upper_pressure_port_defined",
        },
        {
            **BOUNDARY,
            "action_module_port": "ot_observation_input_port",
            "accepted_route": "ot_observation_map_route",
            "accepted_source": "traceable_O_t_observation_units_and_audit_layers",
            "required_input_kind": "observation_map_reference_with_evidence_and_audit_level",
            "action_module_may_read": "where_signal;direction_from;direction_to;direction_polarity;intensity;confidence;evidence_summary;lifecycle;audit_level;audit_reasons;source_trace_reference",
            "action_module_must_not_read": "raw_G_t;raw_K_t;raw_relation_field;H_DEPT_internal_pressure_computation;hidden_truth;future_information",
            "translation_layer_responsibility": "use_observation_map_as_context_for_where_and_how_cautiously_to_apply_system_dependent_translation",
            "port_contract_status": "ot_observation_port_defined",
        },
    ]
    return pd.DataFrame(rows, columns=REQUIRED_PORT_COLUMNS)


def build_separation_rule_table(route_contract: pd.DataFrame, port_contract: pd.DataFrame) -> pd.DataFrame:
    checks = [
        (
            "upper_pressure_not_generated_here",
            "Task2-8j-8 defines schema only and does not create an upper-pressure payload.",
            False,
            bool(route_contract["upper_pressure_generated_here"].astype(bool).any()),
        ),
        (
            "ot_not_generated_from_upper_pressure",
            "O_t observation-map route is derived from relation-field evidence, not from upper pressure.",
            False,
            bool(route_contract["ot_generated_from_upper_pressure"].astype(bool).any()),
        ),
        (
            "upper_pressure_does_not_rewrite_ot",
            "Upper pressure must not rewrite O_t in this contract.",
            False,
            bool(route_contract["upper_pressure_rewrites_ot"].astype(bool).any()),
        ),
        (
            "ot_does_not_generate_upper_pressure",
            "O_t can inform downstream translation context but does not generate H-DEPT pressure.",
            False,
            bool(route_contract["ot_generates_upper_pressure"].astype(bool).any()),
        ),
        (
            "ports_are_distinct",
            "Upper-pressure and O_t observation routes enter distinct action-module ports.",
            True,
            len(set(port_contract["action_module_port"].astype(str))) == 2,
        ),
        (
            "routes_meet_only_inside_action_module_translation",
            "The two routes may meet only inside the action module's system-dependent translation layer.",
            True,
            bool(route_contract["routes_may_meet_only_inside_action_module_translation"].astype(bool).all()),
        ),
    ]
    rows: list[dict] = []
    for rule, description, required, observed in checks:
        rows.append({
            **BOUNDARY,
            "separation_rule": rule,
            "rule_description": description,
            "required_value": bool(required),
            "observed_value": bool(observed),
            "separation_status": "pass" if bool(required) == bool(observed) else "fail",
        })
    return pd.DataFrame(rows, columns=REQUIRED_SEPARATION_COLUMNS)


def build_readiness_table(
    preservation_summary: dict,
    preservation_errors: list[str],
    route_contract: pd.DataFrame,
) -> pd.DataFrame:
    decision = str(preservation_summary.get("information_preservation_decision", ""))
    changed_rate = _safe_float(preservation_summary.get("changed_relation_coverage_rate", 0.0))
    audit_rate = _safe_float(preservation_summary.get("audit_trace_coverage_rate", 0.0))
    observation_ready = (
        decision == "relation_to_ot_information_preserved_with_traceable_coarse_graining"
        and len(preservation_errors) == 0
        and changed_rate >= 1.0
        and audit_rate >= 1.0
    )
    upper_schema_ready = bool((route_contract["route_name"].astype(str) == "upper_pressure_route").any()) and bool(
        route_contract.loc[route_contract["route_name"].astype(str) == "upper_pressure_route", "payload_status_in_this_task"].astype(str).str.contains("schema_only").all()
    )
    split_ready = observation_ready and upper_schema_ready
    rows = [
        {
            **BOUNDARY,
            "readiness_source": "Task2_8j_7c_relation_to_ot_information_preservation",
            "source_decision": decision,
            "source_validation_error_count": int(len(preservation_errors)),
            "source_changed_relation_coverage_rate": changed_rate,
            "source_audit_trace_coverage_rate": audit_rate,
            "observation_route_ready": bool(observation_ready),
            "upper_pressure_route_schema_ready": bool(upper_schema_ready),
            "action_module_input_split_ready": bool(split_ready),
            "readiness_status": "ready" if split_ready else "not_ready",
        }
    ]
    return pd.DataFrame(rows, columns=REQUIRED_READINESS_COLUMNS)


def build_final_summary(
    route_contract: pd.DataFrame,
    port_contract: pd.DataFrame,
    separation_rules: pd.DataFrame,
    readiness: pd.DataFrame,
) -> pd.DataFrame:
    route_count = int(len(route_contract)) if route_contract is not None else 0
    port_count = int(len(port_contract)) if port_contract is not None else 0
    rule_count = int(len(separation_rules)) if separation_rules is not None else 0
    pass_count = int((separation_rules["separation_status"].astype(str) == "pass").sum()) if rule_count else 0
    ready_rows = int(len(readiness)) if readiness is not None else 0
    obs_ready = int(readiness["observation_route_ready"].astype(bool).sum()) if ready_rows else 0
    upper_ready = int(readiness["upper_pressure_route_schema_ready"].astype(bool).sum()) if ready_rows else 0
    if route_count == 2 and port_count == 2 and rule_count == pass_count and obs_ready == ready_rows and upper_ready == ready_rows:
        decision = "action_module_input_split_contract_ready_with_upper_pressure_and_ot_routes_separate"
    else:
        decision = "action_module_input_split_contract_needs_review"
    return pd.DataFrame([{
        **BOUNDARY,
        "route_contract_count": route_count,
        "action_module_port_count": port_count,
        "separation_rule_count": rule_count,
        "separation_pass_count": pass_count,
        "readiness_row_count": ready_rows,
        "observation_route_ready_count": obs_ready,
        "upper_pressure_route_schema_ready_count": upper_ready,
        "action_module_input_split_contract_decision": decision,
        "next_task": "Task 2-8j-9: action-module two-route reception dry-run contract validation",
    }], columns=REQUIRED_SUMMARY_COLUMNS)


def validate_action_module_input_split_contract_tables(
    route_contract: pd.DataFrame,
    port_contract: pd.DataFrame,
    separation_rules: pd.DataFrame,
    readiness: pd.DataFrame,
    final_summary: pd.DataFrame,
) -> list[str]:
    errors: list[str] = []
    tables = {
        "route_contract": (route_contract, REQUIRED_ROUTE_COLUMNS),
        "port_contract": (port_contract, REQUIRED_PORT_COLUMNS),
        "separation_rules": (separation_rules, REQUIRED_SEPARATION_COLUMNS),
        "readiness": (readiness, REQUIRED_READINESS_COLUMNS),
        "final_summary": (final_summary, REQUIRED_SUMMARY_COLUMNS),
    }
    for name, (table, required) in tables.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_8_empty_table:{name}")
            continue
        missing = [c for c in required if c not in table.columns]
        if missing:
            errors.append(f"task2_8j_8_missing_columns:{name}:" + ",".join(missing))
            continue
        for col in ["validation_only", "contract_only", "upper_pressure_route_separate", "ot_observation_route_separate", "routes_may_meet_only_inside_action_module_translation"]:
            if not bool(table[col].astype(bool).all()):
                errors.append(f"task2_8j_8_required_true_not_all_true:{name}:{col}")
        if set(table["gt_main_map_name"].astype(str)) != {"static_pca_7"}:
            errors.append(f"task2_8j_8_wrong_gt_main_map_name:{name}")
        if set(table["gt_main_component_count"].astype(int)) != {7}:
            errors.append(f"task2_8j_8_wrong_component_count:{name}")
        for col in FORBIDDEN_TRUE:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_8_forbidden_true:{name}:{col}")
    if route_contract is not None and not route_contract.empty:
        if set(route_contract["route_name"].astype(str)) != {"upper_pressure_route", "ot_observation_map_route"}:
            errors.append("task2_8j_8_route_names_not_exactly_two_routes")
        if len(set(route_contract["action_module_port"].astype(str))) != 2:
            errors.append("task2_8j_8_route_ports_not_distinct")
    if separation_rules is not None and not separation_rules.empty:
        if not bool((separation_rules["separation_status"].astype(str) == "pass").all()):
            errors.append("task2_8j_8_separation_rule_failure")
    if readiness is not None and not readiness.empty:
        if not bool(readiness["action_module_input_split_ready"].astype(bool).all()):
            errors.append("task2_8j_8_readiness_false")
    return errors


def build_and_validate_action_module_input_split_contract(
    tracking_cfg: V2StructureChangeTrackingConfig | None = None,
    ot_cfg: OtObservationMapConfig | None = None,
    audit_cfg: OtAuditLayeringConfig | None = None,
    preservation_cfg: RelationToOtInformationPreservationConfig | None = None,
    cfg: ActionModuleInputSplitContractConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    cfg = cfg or ActionModuleInputSplitContractConfig()
    _relation_trace, _coverage_audit, _audit_trace, _preservation_final, preservation_errors, preservation_summary = (
        build_and_validate_relation_to_ot_information_preservation_audit(
            tracking_cfg or V2StructureChangeTrackingConfig(),
            ot_cfg or OtObservationMapConfig(),
            audit_cfg or OtAuditLayeringConfig(),
            preservation_cfg or RelationToOtInformationPreservationConfig(),
        )
    )
    route_contract = build_route_contract_table()
    port_contract = build_action_module_port_contract_table()
    separation_rules = build_separation_rule_table(route_contract, port_contract)
    readiness = build_readiness_table(preservation_summary, preservation_errors if cfg.require_relation_to_ot_preservation else [], route_contract)
    final_summary = build_final_summary(route_contract, port_contract, separation_rules, readiness)
    errors: list[str] = []
    if cfg.require_relation_to_ot_preservation:
        errors.extend([f"task2_8j_8_upstream_7c_error:{e}" for e in preservation_errors])
    errors.extend(validate_action_module_input_split_contract_tables(route_contract, port_contract, separation_rules, readiness, final_summary))
    summary = {
        "gt_main_map_name": "static_pca_7",
        "gt_main_component_count": 7,
        "route_contract_count": int(final_summary["route_contract_count"].iloc[0]) if not final_summary.empty else 0,
        "action_module_port_count": int(final_summary["action_module_port_count"].iloc[0]) if not final_summary.empty else 0,
        "separation_rule_count": int(final_summary["separation_rule_count"].iloc[0]) if not final_summary.empty else 0,
        "separation_pass_count": int(final_summary["separation_pass_count"].iloc[0]) if not final_summary.empty else 0,
        "readiness_row_count": int(final_summary["readiness_row_count"].iloc[0]) if not final_summary.empty else 0,
        "observation_route_ready_count": int(final_summary["observation_route_ready_count"].iloc[0]) if not final_summary.empty else 0,
        "upper_pressure_route_schema_ready_count": int(final_summary["upper_pressure_route_schema_ready_count"].iloc[0]) if not final_summary.empty else 0,
        "action_module_input_split_contract_decision": str(final_summary["action_module_input_split_contract_decision"].iloc[0]) if not final_summary.empty else "empty",
        "upper_pressure_generated_here": False,
        "ot_generates_upper_pressure": False,
        "action_module_input_object_created": False,
        "actionmodule_called": False,
        "validation_errors": errors,
    }
    return route_contract, port_contract, separation_rules, readiness, final_summary, errors, summary
