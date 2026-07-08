"""Task 2-8j-9: action-module two-route reception dry-run RC1.

Purpose:
    Validate, as a dry-run contract test, that the future action-module boundary
    can receive two sibling input routes without mixing them:
    (1) upper-pressure route and (2) O_t observation-map route.

Position:
    Task 2-8j-8 froze the two-route / two-port input split contract.  This task
    creates dry-run reception envelopes and checks that the future action-module
    boundary can accept the two ports as separate inputs.  It is not a real
    ActionModule call, not an action translation, and not a runtime execution.

Boundary:
    - dry-run reception validation only
    - fixed static_pca_7 main map
    - two input envelopes may be created as contract stubs only
    - upper pressure is not generated here
    - O_t does not generate upper pressure
    - no action conversion, ActionFrame creation, real ActionModule call, runtime call, or writeback
    - no hidden-truth / future-information input
    - no effective-dimension re-fitting or axis mutation
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .pressure_action_task2_8j_6c_v2_structure_change_relation_field_tracking import V2StructureChangeTrackingConfig
from .pressure_action_task2_8j_7_ot_observation_map_from_relation_field import OtObservationMapConfig
from .pressure_action_task2_8j_7b_ot_audit_layering import OtAuditLayeringConfig
from .pressure_action_task2_8j_7c_relation_to_ot_information_preservation_audit import RelationToOtInformationPreservationConfig
from .pressure_action_task2_8j_8_action_module_input_split_contract import (
    ActionModuleInputSplitContractConfig,
    build_and_validate_action_module_input_split_contract,
)

TASK2_8J_9_VERSION = "action_module_two_route_reception_dry_run_rc1"
TASK2_8J_9_CONTRACT = (
    "Task2_8j_9_action_module_two_route_reception_dry_run__"
    "receive_upper_pressure_and_Ot_observation_routes_as_separate_contract_stubs__"
    "no_real_actionmodule_no_translation_no_runtime_no_writeback"
)

BOUNDARY = {
    "task2_8j_9_version": TASK2_8J_9_VERSION,
    "task2_8j_9_contract": TASK2_8J_9_CONTRACT,
    "validation_only": True,
    "dry_run_only": True,
    "gt_main_map_name": "static_pca_7",
    "gt_main_component_count": 7,
    "contract_source": "Task2_8j_8_action_module_input_split_contract",
    "two_route_reception_envelope_created": True,
    "upper_pressure_route_received_as_stub": True,
    "ot_observation_route_received_as_stub": True,
    "routes_kept_separate": True,
    "routes_merge_inside_translation_layer": False,
    "upper_pressure_generated_here": False,
    "ot_generates_upper_pressure": False,
    "upper_pressure_rewrites_ot": False,
    "ot_rewrites_upper_pressure": False,
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
    "routes_merge_inside_translation_layer",
    "upper_pressure_generated_here",
    "ot_generates_upper_pressure",
    "upper_pressure_rewrites_ot",
    "ot_rewrites_upper_pressure",
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

REQUIRED_ENVELOPE_COLUMNS = list(BOUNDARY) + [
    "envelope_id",
    "route_name",
    "action_module_port",
    "payload_kind",
    "payload_origin",
    "payload_is_contract_stub",
    "payload_field_count",
    "payload_required_fields_present",
    "payload_forbidden_fields_absent",
    "route_role_preserved",
    "reception_status",
]

REQUIRED_CHECK_COLUMNS = list(BOUNDARY) + [
    "check_id",
    "check_scope",
    "check_description",
    "expected_value",
    "observed_value",
    "check_status",
]

REQUIRED_RECEIPT_COLUMNS = list(BOUNDARY) + [
    "receipt_id",
    "received_route_count",
    "received_port_count",
    "upper_pressure_stub_received",
    "ot_observation_stub_received",
    "separate_port_count",
    "real_actionmodule_called_in_receipt",
    "translation_performed_in_receipt",
    "receipt_status",
]

REQUIRED_SUMMARY_COLUMNS = list(BOUNDARY) + [
    "envelope_count",
    "reception_check_count",
    "reception_check_pass_count",
    "receipt_count",
    "received_route_count",
    "received_port_count",
    "separate_port_count",
    "upper_pressure_stub_received_count",
    "ot_observation_stub_received_count",
    "two_route_reception_dry_run_decision",
    "next_task",
]


@dataclass(frozen=True)
class TwoRouteReceptionDryRunConfig:
    require_task8_ready: bool = True


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _split_fields(value: object) -> list[str]:
    return [p.strip() for p in str(value or "").split(";") if p.strip()]


def build_dry_run_input_envelopes(route_contract: pd.DataFrame, readiness: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    readiness_ready = bool(readiness["action_module_input_split_ready"].astype(bool).all()) if readiness is not None and not readiness.empty else False
    for row in route_contract.itertuples(index=False):
        route_name = str(row.route_name)
        required = _split_fields(row.required_payload_fields)
        forbidden = _split_fields(row.forbidden_payload_fields)
        if route_name == "upper_pressure_route":
            payload_kind = "upper_pressure_contract_stub_no_pressure_generated"
            origin = "Task2_8j_8_upper_pressure_route_schema"
        elif route_name == "ot_observation_map_route":
            payload_kind = "ot_observation_contract_stub_traceable_evidence_ready"
            origin = "Task2_8j_7c_relation_to_ot_information_preservation"
        else:
            payload_kind = "unknown_route_stub"
            origin = "unknown"
        rows.append({
            **BOUNDARY,
            "envelope_id": f"dry_run_envelope_{route_name}",
            "route_name": route_name,
            "action_module_port": str(row.action_module_port),
            "payload_kind": payload_kind,
            "payload_origin": origin,
            "payload_is_contract_stub": True,
            "payload_field_count": int(len(required)),
            "payload_required_fields_present": bool(len(required) > 0 and readiness_ready),
            "payload_forbidden_fields_absent": bool(len(forbidden) > 0),
            "route_role_preserved": bool(str(row.route_role) != "" and str(row.merge_policy).startswith("may_meet")),
            "reception_status": "dry_run_reception_envelope_ready" if readiness_ready else "dry_run_reception_envelope_not_ready",
        })
    return pd.DataFrame(rows, columns=REQUIRED_ENVELOPE_COLUMNS)


def build_reception_checks(envelopes: pd.DataFrame, route_contract: pd.DataFrame, port_contract: pd.DataFrame, task8_errors: list[str]) -> pd.DataFrame:
    route_names = set(envelopes["route_name"].astype(str)) if envelopes is not None and not envelopes.empty else set()
    ports = set(envelopes["action_module_port"].astype(str)) if envelopes is not None and not envelopes.empty else set()
    checks = [
        (
            "check_two_routes_present",
            "route",
            "Dry-run reception includes upper-pressure and O_t observation routes.",
            True,
            route_names == {"upper_pressure_route", "ot_observation_map_route"},
        ),
        (
            "check_two_distinct_ports_present",
            "port",
            "The two dry-run envelopes use two distinct action-module ports.",
            True,
            ports == {"upper_pressure_input_port", "ot_observation_input_port"},
        ),
        (
            "check_required_fields_present",
            "payload",
            "Each envelope has required payload fields defined by the Task2-8j-8 contract.",
            True,
            bool(envelopes["payload_required_fields_present"].astype(bool).all()) if envelopes is not None and not envelopes.empty else False,
        ),
        (
            "check_forbidden_fields_absent",
            "payload",
            "Forbidden cross-route / action fields are absent from both envelopes.",
            True,
            bool(envelopes["payload_forbidden_fields_absent"].astype(bool).all()) if envelopes is not None and not envelopes.empty else False,
        ),
        (
            "check_route_roles_preserved",
            "route",
            "Each route keeps its role and does not become the other route.",
            True,
            bool(envelopes["route_role_preserved"].astype(bool).all()) if envelopes is not None and not envelopes.empty else False,
        ),
        (
            "check_task8_ready",
            "upstream_contract",
            "Task2-8j-8 split contract has no validation errors.",
            True,
            len(task8_errors) == 0,
        ),
        (
            "check_no_real_actionmodule_call",
            "boundary",
            "The dry run does not call the real ActionModule.",
            False,
            bool(envelopes["real_actionmodule_called"].astype(bool).any()) if envelopes is not None and not envelopes.empty else True,
        ),
        (
            "check_no_action_translation",
            "boundary",
            "The dry run does not translate the two inputs into action candidates.",
            False,
            bool(envelopes["action_translation_performed"].astype(bool).any()) if envelopes is not None and not envelopes.empty else True,
        ),
    ]
    rows: list[dict] = []
    for check_id, scope, desc, expected, observed in checks:
        rows.append({
            **BOUNDARY,
            "check_id": check_id,
            "check_scope": scope,
            "check_description": desc,
            "expected_value": bool(expected),
            "observed_value": bool(observed),
            "check_status": "pass" if bool(expected) == bool(observed) else "fail",
        })
    return pd.DataFrame(rows, columns=REQUIRED_CHECK_COLUMNS)


def build_dry_run_reception_receipt(envelopes: pd.DataFrame, checks: pd.DataFrame) -> pd.DataFrame:
    route_count = int(len(set(envelopes["route_name"].astype(str)))) if envelopes is not None and not envelopes.empty else 0
    port_count = int(len(set(envelopes["action_module_port"].astype(str)))) if envelopes is not None and not envelopes.empty else 0
    upper_received = bool((envelopes["route_name"].astype(str) == "upper_pressure_route").any()) if envelopes is not None and not envelopes.empty else False
    ot_received = bool((envelopes["route_name"].astype(str) == "ot_observation_map_route").any()) if envelopes is not None and not envelopes.empty else False
    separate_count = port_count
    real_called = bool(envelopes["real_actionmodule_called"].astype(bool).any()) if envelopes is not None and not envelopes.empty else False
    translated = bool(envelopes["action_translation_performed"].astype(bool).any()) if envelopes is not None and not envelopes.empty else False
    checks_pass = bool((checks["check_status"].astype(str) == "pass").all()) if checks is not None and not checks.empty else False
    status = "two_route_dry_run_reception_accepted_without_translation" if checks_pass and route_count == 2 and port_count == 2 and not real_called and not translated else "two_route_dry_run_reception_needs_review"
    return pd.DataFrame([{
        **BOUNDARY,
        "receipt_id": "task2_8j_9_dry_run_reception_receipt_001",
        "received_route_count": route_count,
        "received_port_count": port_count,
        "upper_pressure_stub_received": upper_received,
        "ot_observation_stub_received": ot_received,
        "separate_port_count": separate_count,
        "real_actionmodule_called_in_receipt": real_called,
        "translation_performed_in_receipt": translated,
        "receipt_status": status,
    }], columns=REQUIRED_RECEIPT_COLUMNS)


def build_final_summary(envelopes: pd.DataFrame, checks: pd.DataFrame, receipt: pd.DataFrame) -> pd.DataFrame:
    envelope_count = int(len(envelopes)) if envelopes is not None else 0
    check_count = int(len(checks)) if checks is not None else 0
    pass_count = int((checks["check_status"].astype(str) == "pass").sum()) if check_count else 0
    receipt_count = int(len(receipt)) if receipt is not None else 0
    received_routes = _safe_int(receipt["received_route_count"].iloc[0]) if receipt_count else 0
    received_ports = _safe_int(receipt["received_port_count"].iloc[0]) if receipt_count else 0
    separate_ports = _safe_int(receipt["separate_port_count"].iloc[0]) if receipt_count else 0
    upper_stub = int(receipt["upper_pressure_stub_received"].astype(bool).sum()) if receipt_count else 0
    ot_stub = int(receipt["ot_observation_stub_received"].astype(bool).sum()) if receipt_count else 0
    if envelope_count == 2 and check_count == pass_count and received_routes == 2 and received_ports == 2 and separate_ports == 2 and upper_stub == 1 and ot_stub == 1:
        decision = "action_module_two_route_reception_dry_run_contract_passed"
    else:
        decision = "action_module_two_route_reception_dry_run_contract_needs_review"
    return pd.DataFrame([{
        **BOUNDARY,
        "envelope_count": envelope_count,
        "reception_check_count": check_count,
        "reception_check_pass_count": pass_count,
        "receipt_count": receipt_count,
        "received_route_count": received_routes,
        "received_port_count": received_ports,
        "separate_port_count": separate_ports,
        "upper_pressure_stub_received_count": upper_stub,
        "ot_observation_stub_received_count": ot_stub,
        "two_route_reception_dry_run_decision": decision,
        "next_task": "Task 2-8j-10: action-module two-route translation sandbox without execution",
    }], columns=REQUIRED_SUMMARY_COLUMNS)


def validate_two_route_reception_dry_run_tables(envelopes: pd.DataFrame, checks: pd.DataFrame, receipt: pd.DataFrame, final_summary: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    tables = {
        "envelopes": (envelopes, REQUIRED_ENVELOPE_COLUMNS),
        "checks": (checks, REQUIRED_CHECK_COLUMNS),
        "receipt": (receipt, REQUIRED_RECEIPT_COLUMNS),
        "final_summary": (final_summary, REQUIRED_SUMMARY_COLUMNS),
    }
    for name, (table, required) in tables.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_9_empty_table:{name}")
            continue
        missing = [c for c in required if c not in table.columns]
        if missing:
            errors.append(f"task2_8j_9_missing_columns:{name}:" + ",".join(missing))
            continue
        for col in ["validation_only", "dry_run_only", "two_route_reception_envelope_created", "routes_kept_separate"]:
            if not bool(table[col].astype(bool).all()):
                errors.append(f"task2_8j_9_required_true_not_all_true:{name}:{col}")
        if set(table["gt_main_map_name"].astype(str)) != {"static_pca_7"}:
            errors.append(f"task2_8j_9_wrong_gt_main_map_name:{name}")
        if set(table["gt_main_component_count"].astype(int)) != {7}:
            errors.append(f"task2_8j_9_wrong_component_count:{name}")
        for col in FORBIDDEN_TRUE:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_9_forbidden_true:{name}:{col}")
    if envelopes is not None and not envelopes.empty:
        if set(envelopes["route_name"].astype(str)) != {"upper_pressure_route", "ot_observation_map_route"}:
            errors.append("task2_8j_9_missing_expected_routes")
        if len(set(envelopes["action_module_port"].astype(str))) != 2:
            errors.append("task2_8j_9_ports_not_distinct")
        if not bool(envelopes["payload_is_contract_stub"].astype(bool).all()):
            errors.append("task2_8j_9_payload_not_all_contract_stubs")
    if checks is not None and not checks.empty:
        if not bool((checks["check_status"].astype(str) == "pass").all()):
            errors.append("task2_8j_9_reception_check_failed")
    if receipt is not None and not receipt.empty:
        if set(receipt["receipt_status"].astype(str)) != {"two_route_dry_run_reception_accepted_without_translation"}:
            errors.append("task2_8j_9_receipt_not_accepted")
    return errors


def build_and_validate_two_route_reception_dry_run(
    tracking_cfg: V2StructureChangeTrackingConfig | None = None,
    ot_cfg: OtObservationMapConfig | None = None,
    audit_cfg: OtAuditLayeringConfig | None = None,
    preservation_cfg: RelationToOtInformationPreservationConfig | None = None,
    split_cfg: ActionModuleInputSplitContractConfig | None = None,
    cfg: TwoRouteReceptionDryRunConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    cfg = cfg or TwoRouteReceptionDryRunConfig()
    route_contract, port_contract, _separation_rules, readiness, _split_summary, split_errors, split_json = (
        build_and_validate_action_module_input_split_contract(
            tracking_cfg or V2StructureChangeTrackingConfig(),
            ot_cfg or OtObservationMapConfig(),
            audit_cfg or OtAuditLayeringConfig(),
            preservation_cfg or RelationToOtInformationPreservationConfig(),
            split_cfg or ActionModuleInputSplitContractConfig(),
        )
    )
    upstream_errors = split_errors if cfg.require_task8_ready else []
    envelopes = build_dry_run_input_envelopes(route_contract, readiness)
    checks = build_reception_checks(envelopes, route_contract, port_contract, upstream_errors)
    receipt = build_dry_run_reception_receipt(envelopes, checks)
    final_summary = build_final_summary(envelopes, checks, receipt)
    errors = [f"task2_8j_9_upstream_8_error:{e}" for e in upstream_errors]
    errors.extend(validate_two_route_reception_dry_run_tables(envelopes, checks, receipt, final_summary))
    summary = {
        "gt_main_map_name": "static_pca_7",
        "gt_main_component_count": 7,
        "task8_decision": split_json.get("action_module_input_split_contract_decision", ""),
        "envelope_count": int(final_summary["envelope_count"].iloc[0]) if not final_summary.empty else 0,
        "reception_check_count": int(final_summary["reception_check_count"].iloc[0]) if not final_summary.empty else 0,
        "reception_check_pass_count": int(final_summary["reception_check_pass_count"].iloc[0]) if not final_summary.empty else 0,
        "receipt_count": int(final_summary["receipt_count"].iloc[0]) if not final_summary.empty else 0,
        "received_route_count": int(final_summary["received_route_count"].iloc[0]) if not final_summary.empty else 0,
        "received_port_count": int(final_summary["received_port_count"].iloc[0]) if not final_summary.empty else 0,
        "separate_port_count": int(final_summary["separate_port_count"].iloc[0]) if not final_summary.empty else 0,
        "upper_pressure_stub_received_count": int(final_summary["upper_pressure_stub_received_count"].iloc[0]) if not final_summary.empty else 0,
        "ot_observation_stub_received_count": int(final_summary["ot_observation_stub_received_count"].iloc[0]) if not final_summary.empty else 0,
        "two_route_reception_dry_run_decision": str(final_summary["two_route_reception_dry_run_decision"].iloc[0]) if not final_summary.empty else "empty",
        "real_actionmodule_called": False,
        "action_translation_performed": False,
        "validation_errors": errors,
    }
    return envelopes, checks, receipt, final_summary, errors, summary
