"""Task 2-8j-10: game-structure prediction input contract RC1.

Purpose:
    Define an observation-side prediction input contract derived from the game
    structure / relation-field / O_t route.  This is the contract for providing
    "what is likely to happen if the current game structure continues" to the
    action module later.

Position:
    Task 2-8j-9 confirmed that the future action-module boundary can dry-run
    receive the upper-pressure route and O_t observation-map route separately.
    This task adds the prediction-input contract as an observation-side sidecar:
    it may be read later by the action module, but it must not create action
    axes, action candidates, intervention forecasts, or upper pressure.

Boundary:
    - prediction-input contract only
    - fixed static_pca_7 main map
    - game-structure prediction is observation-side forecast only
    - no action-effect prediction and no action-axis generation
    - upper-pressure route remains separate and is not generated here
    - O_t / prediction does not generate upper pressure
    - no real ActionModule call, runtime call, writeback, hidden-truth / future-information input, or axis mutation
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
from .pressure_action_task2_8j_9_two_route_reception_dry_run import (
    TwoRouteReceptionDryRunConfig,
    build_and_validate_two_route_reception_dry_run,
)

TASK2_8J_10_VERSION = "game_structure_prediction_input_contract_rc1"
TASK2_8J_10_CONTRACT = (
    "Task2_8j_10_game_structure_prediction_input_contract__"
    "observation_side_forecast_only__"
    "no_action_effect_prediction_no_action_axes_no_upper_pressure_no_runtime"
)

BOUNDARY = {
    "task2_8j_10_version": TASK2_8J_10_VERSION,
    "task2_8j_10_contract": TASK2_8J_10_CONTRACT,
    "validation_only": True,
    "contract_only": True,
    "prediction_input_contract_only": True,
    "gt_main_map_name": "static_pca_7",
    "gt_main_component_count": 7,
    "prediction_source_family": "relation_field_Ot_observation_side",
    "game_structure_prediction_route_separate": True,
    "observation_forecast_allowed": True,
    "action_effect_prediction_generated": False,
    "action_axis_generated": False,
    "action_candidate_generated": False,
    "upper_pressure_generated_here": False,
    "prediction_generates_upper_pressure": False,
    "upper_pressure_rewrites_prediction": False,
    "prediction_rewrites_ot": False,
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
    "action_effect_prediction_generated",
    "action_axis_generated",
    "action_candidate_generated",
    "upper_pressure_generated_here",
    "prediction_generates_upper_pressure",
    "upper_pressure_rewrites_prediction",
    "prediction_rewrites_ot",
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

REQUIRED_CONTRACT_COLUMNS = list(BOUNDARY) + [
    "prediction_route_id",
    "prediction_route_name",
    "prediction_route_role",
    "prediction_route_source",
    "payload_status_in_this_task",
    "required_payload_fields",
    "forbidden_payload_fields",
    "action_module_port_later",
    "prediction_contract_status",
]

REQUIRED_SCOPE_COLUMNS = list(BOUNDARY) + [
    "scope_rule",
    "allowed_or_forbidden",
    "rule_description",
    "contract_value",
    "scope_status",
]

REQUIRED_FEATURE_COLUMNS = list(BOUNDARY) + [
    "prediction_feature_group",
    "source_table_or_route",
    "source_fields",
    "prediction_payload_field",
    "feature_role",
    "feature_status",
]

REQUIRED_READINESS_COLUMNS = list(BOUNDARY) + [
    "readiness_source",
    "task9_decision",
    "task9_validation_error_count",
    "received_route_count",
    "received_port_count",
    "separate_port_count",
    "upper_pressure_stub_received_count",
    "ot_observation_stub_received_count",
    "prediction_input_contract_ready",
    "readiness_status",
]

REQUIRED_SUMMARY_COLUMNS = list(BOUNDARY) + [
    "prediction_contract_count",
    "scope_rule_count",
    "scope_pass_count",
    "feature_group_count",
    "readiness_row_count",
    "prediction_input_contract_ready_count",
    "game_structure_prediction_input_contract_decision",
    "next_task",
]


@dataclass(frozen=True)
class GameStructurePredictionInputContractConfig:
    require_task9_ready: bool = True


def _safe_int(value: object, default: int = 0) -> int:
    try:
        out = int(value)
    except (TypeError, ValueError):
        return int(default)
    return int(out)


def build_prediction_contract_table() -> pd.DataFrame:
    rows = [
        {
            **BOUNDARY,
            "prediction_route_id": "game_structure_prediction_route_001",
            "prediction_route_name": "game_structure_prediction_route",
            "prediction_route_role": "observation_side_forecast_of_game_structure_tendency_without_action_assumption",
            "prediction_route_source": "relation_field_plus_traceable_Ot_observation_map_plus_audit_layers",
            "payload_status_in_this_task": "schema_only_no_prediction_values_generated",
            "required_payload_fields": "prediction_bundle_id;source_observation_ids;source_relation_trace_ids;prediction_horizon;predicted_state_tendency;predicted_relation_tendency;confidence;uncertainty;validity_scope;assumption_current_structure_continues;provenance;audit_level;audit_reasons",
            "forbidden_payload_fields": "action_effect_estimate;intervention_policy;direct_action_weights;concrete_action;upper_pressure_magnitude;pressure_axis_or_family;runtime_policy_input;hidden_truth;future_information",
            "action_module_port_later": "game_structure_prediction_input_port",
            "prediction_contract_status": "game_structure_prediction_input_schema_ready_observation_forecast_only",
        }
    ]
    return pd.DataFrame(rows, columns=REQUIRED_CONTRACT_COLUMNS)


def build_prediction_scope_table() -> pd.DataFrame:
    rows = [
        (
            "observation_forecast_allowed",
            "allowed",
            "Predict current-structure tendencies such as likely state drift, relation strengthening / weakening, persistence, and uncertainty.",
            True,
        ),
        (
            "action_effect_prediction_forbidden",
            "forbidden",
            "Do not predict effects of a concrete action or intervention in this contract.",
            False,
        ),
        (
            "action_axis_generation_forbidden",
            "forbidden",
            "Do not generate final action axes; this remains an action-module translation responsibility.",
            False,
        ),
        (
            "upper_pressure_generation_forbidden",
            "forbidden",
            "Do not create H-DEPT upper pressure from the prediction route.",
            False,
        ),
        (
            "ot_rewrite_forbidden",
            "forbidden",
            "Prediction must not rewrite O_t; it may only reference traceable O_t / relation-field evidence.",
            False,
        ),
        (
            "hidden_future_input_forbidden",
            "forbidden",
            "Prediction contract must not use hidden truth or future information.",
            False,
        ),
    ]
    out: list[dict] = []
    for rule, kind, description, value in rows:
        expected = True if kind == "allowed" else False
        out.append({
            **BOUNDARY,
            "scope_rule": rule,
            "allowed_or_forbidden": kind,
            "rule_description": description,
            "contract_value": bool(value),
            "scope_status": "pass" if bool(value) == expected else "fail",
        })
    return pd.DataFrame(out, columns=REQUIRED_SCOPE_COLUMNS)


def build_prediction_feature_contract_table() -> pd.DataFrame:
    rows = [
        (
            "state_tendency",
            "Task2_8j_6c_phase_state_reproduction + Task2_8j_7_Ot_state_observations",
            "phase_name;mean_state_event_accuracy;weak_state_names;observation_kind;confidence;lifecycle",
            "predicted_state_tendency",
            "estimate likely next-state or persistent-state tendency under current game structure",
        ),
        (
            "relation_tendency",
            "Task2_8j_6c_relation_edge_change + Task2_8j_7_Ot_relation_change_observations",
            "source_macro_signal;target_macro_signal;relation_strength_delta;direction_polarity;intensity;confidence",
            "predicted_relation_tendency",
            "estimate relation strengthening / weakening tendency without action assumption",
        ),
        (
            "tracking_recovery",
            "Task2_8j_6c_stale_vs_updated_relation_field + Task2_8j_7_tracking_recovery_observations",
            "source_relation_phase;target_state_phase;updated_minus_stale_event_accuracy;lifecycle;confidence",
            "prediction_reliability_context",
            "describe whether updated relation field preserves or recovers tracking",
        ),
        (
            "audit_context",
            "Task2_8j_7b_audit_layers",
            "audit_reasons;audit_level;risk_score;confidence_score;change_score;centrality_score;residual_score",
            "audit_level_and_reason_context",
            "carry caution level and reason split into the prediction input",
        ),
        (
            "source_trace",
            "Task2_8j_7c_relation_to_ot_information_preservation",
            "source_phase;target_phase;matched_ot_observation_id;evidence_source_present;evidence_delta_present;relation_information_preservation_status",
            "source_relation_trace_ids",
            "keep prediction input traceable back to relation-field evidence",
        ),
        (
            "uncertainty",
            "O_t confidence + audit confidence / residual components",
            "confidence;uncertainty;residual_flag;weak_state_reproduction;low_confidence",
            "confidence_and_uncertainty",
            "separate confidence from risk and residual concerns",
        ),
    ]
    out: list[dict] = []
    for group, source, source_fields, payload_field, role in rows:
        out.append({
            **BOUNDARY,
            "prediction_feature_group": group,
            "source_table_or_route": source,
            "source_fields": source_fields,
            "prediction_payload_field": payload_field,
            "feature_role": role,
            "feature_status": "feature_source_contract_ready",
        })
    return pd.DataFrame(out, columns=REQUIRED_FEATURE_COLUMNS)


def build_prediction_readiness_table(task9_summary: dict, task9_errors: list[str]) -> pd.DataFrame:
    decision = str(task9_summary.get("two_route_reception_dry_run_decision", ""))
    route_count = _safe_int(task9_summary.get("received_route_count", 0))
    port_count = _safe_int(task9_summary.get("received_port_count", 0))
    separate_count = _safe_int(task9_summary.get("separate_port_count", 0))
    upper_count = _safe_int(task9_summary.get("upper_pressure_stub_received_count", 0))
    ot_count = _safe_int(task9_summary.get("ot_observation_stub_received_count", 0))
    ready = (
        len(task9_errors) == 0
        and decision == "action_module_two_route_reception_dry_run_contract_passed"
        and route_count == 2
        and port_count == 2
        and separate_count == 2
        and upper_count == 1
        and ot_count == 1
    )
    return pd.DataFrame([{
        **BOUNDARY,
        "readiness_source": "Task2_8j_9_two_route_reception_dry_run",
        "task9_decision": decision,
        "task9_validation_error_count": int(len(task9_errors)),
        "received_route_count": route_count,
        "received_port_count": port_count,
        "separate_port_count": separate_count,
        "upper_pressure_stub_received_count": upper_count,
        "ot_observation_stub_received_count": ot_count,
        "prediction_input_contract_ready": bool(ready),
        "readiness_status": "ready" if ready else "not_ready",
    }], columns=REQUIRED_READINESS_COLUMNS)


def build_final_summary(contract: pd.DataFrame, scope: pd.DataFrame, features: pd.DataFrame, readiness: pd.DataFrame) -> pd.DataFrame:
    contract_count = int(len(contract)) if contract is not None else 0
    scope_count = int(len(scope)) if scope is not None else 0
    scope_pass = int((scope["scope_status"].astype(str) == "pass").sum()) if scope_count else 0
    feature_count = int(len(features)) if features is not None else 0
    readiness_count = int(len(readiness)) if readiness is not None else 0
    ready_count = int(readiness["prediction_input_contract_ready"].astype(bool).sum()) if readiness_count else 0
    if contract_count == 1 and scope_count == scope_pass and feature_count >= 5 and readiness_count == ready_count:
        decision = "game_structure_prediction_input_contract_ready_as_observation_side_forecast_without_action_prediction"
    else:
        decision = "game_structure_prediction_input_contract_needs_review"
    return pd.DataFrame([{
        **BOUNDARY,
        "prediction_contract_count": contract_count,
        "scope_rule_count": scope_count,
        "scope_pass_count": scope_pass,
        "feature_group_count": feature_count,
        "readiness_row_count": readiness_count,
        "prediction_input_contract_ready_count": ready_count,
        "game_structure_prediction_input_contract_decision": decision,
        "next_task": "Task 2-8j-11: game-structure prediction envelope dry-run without action translation",
    }], columns=REQUIRED_SUMMARY_COLUMNS)


def validate_game_structure_prediction_input_contract_tables(contract: pd.DataFrame, scope: pd.DataFrame, features: pd.DataFrame, readiness: pd.DataFrame, final_summary: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    tables = {
        "contract": (contract, REQUIRED_CONTRACT_COLUMNS),
        "scope": (scope, REQUIRED_SCOPE_COLUMNS),
        "features": (features, REQUIRED_FEATURE_COLUMNS),
        "readiness": (readiness, REQUIRED_READINESS_COLUMNS),
        "final_summary": (final_summary, REQUIRED_SUMMARY_COLUMNS),
    }
    for name, (table, required) in tables.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_10_empty_table:{name}")
            continue
        missing = [c for c in required if c not in table.columns]
        if missing:
            errors.append(f"task2_8j_10_missing_columns:{name}:" + ",".join(missing))
            continue
        for col in ["validation_only", "contract_only", "prediction_input_contract_only", "game_structure_prediction_route_separate", "observation_forecast_allowed"]:
            if not bool(table[col].astype(bool).all()):
                errors.append(f"task2_8j_10_required_true_not_all_true:{name}:{col}")
        if set(table["gt_main_map_name"].astype(str)) != {"static_pca_7"}:
            errors.append(f"task2_8j_10_wrong_gt_main_map_name:{name}")
        if set(table["gt_main_component_count"].astype(int)) != {7}:
            errors.append(f"task2_8j_10_wrong_component_count:{name}")
        for col in FORBIDDEN_TRUE:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_10_forbidden_true:{name}:{col}")
    if contract is not None and not contract.empty:
        required_fields = str(contract["required_payload_fields"].iloc[0])
        forbidden_fields = str(contract["forbidden_payload_fields"].iloc[0])
        if "predicted_state_tendency" not in required_fields or "predicted_relation_tendency" not in required_fields:
            errors.append("task2_8j_10_prediction_payload_missing_core_tendency_fields")
        if "action_effect_estimate" not in forbidden_fields or "direct_action_weights" not in forbidden_fields:
            errors.append("task2_8j_10_prediction_payload_missing_forbidden_action_fields")
    if scope is not None and not scope.empty:
        if not bool((scope["scope_status"].astype(str) == "pass").all()):
            errors.append("task2_8j_10_scope_rule_failure")
    if readiness is not None and not readiness.empty:
        if not bool(readiness["prediction_input_contract_ready"].astype(bool).all()):
            errors.append("task2_8j_10_readiness_false")
    return errors


def build_and_validate_game_structure_prediction_input_contract(
    tracking_cfg: V2StructureChangeTrackingConfig | None = None,
    ot_cfg: OtObservationMapConfig | None = None,
    audit_cfg: OtAuditLayeringConfig | None = None,
    preservation_cfg: RelationToOtInformationPreservationConfig | None = None,
    split_cfg: ActionModuleInputSplitContractConfig | None = None,
    reception_cfg: TwoRouteReceptionDryRunConfig | None = None,
    cfg: GameStructurePredictionInputContractConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    cfg = cfg or GameStructurePredictionInputContractConfig()
    _env, _checks, _receipt, _task9_final, task9_errors, task9_summary = build_and_validate_two_route_reception_dry_run(
        tracking_cfg or V2StructureChangeTrackingConfig(),
        ot_cfg or OtObservationMapConfig(),
        audit_cfg or OtAuditLayeringConfig(),
        preservation_cfg or RelationToOtInformationPreservationConfig(),
        split_cfg or ActionModuleInputSplitContractConfig(),
        reception_cfg or TwoRouteReceptionDryRunConfig(),
    )
    upstream_errors = task9_errors if cfg.require_task9_ready else []
    contract = build_prediction_contract_table()
    scope = build_prediction_scope_table()
    features = build_prediction_feature_contract_table()
    readiness = build_prediction_readiness_table(task9_summary, upstream_errors)
    final_summary = build_final_summary(contract, scope, features, readiness)
    errors = [f"task2_8j_10_upstream_9_error:{e}" for e in upstream_errors]
    errors.extend(validate_game_structure_prediction_input_contract_tables(contract, scope, features, readiness, final_summary))
    summary = {
        "gt_main_map_name": "static_pca_7",
        "gt_main_component_count": 7,
        "task9_decision": task9_summary.get("two_route_reception_dry_run_decision", ""),
        "prediction_contract_count": int(final_summary["prediction_contract_count"].iloc[0]) if not final_summary.empty else 0,
        "scope_rule_count": int(final_summary["scope_rule_count"].iloc[0]) if not final_summary.empty else 0,
        "scope_pass_count": int(final_summary["scope_pass_count"].iloc[0]) if not final_summary.empty else 0,
        "feature_group_count": int(final_summary["feature_group_count"].iloc[0]) if not final_summary.empty else 0,
        "readiness_row_count": int(final_summary["readiness_row_count"].iloc[0]) if not final_summary.empty else 0,
        "prediction_input_contract_ready_count": int(final_summary["prediction_input_contract_ready_count"].iloc[0]) if not final_summary.empty else 0,
        "game_structure_prediction_input_contract_decision": str(final_summary["game_structure_prediction_input_contract_decision"].iloc[0]) if not final_summary.empty else "empty",
        "action_effect_prediction_generated": False,
        "action_axis_generated": False,
        "upper_pressure_generated_here": False,
        "real_actionmodule_called": False,
        "validation_errors": errors,
    }
    return contract, scope, features, readiness, final_summary, errors, summary
