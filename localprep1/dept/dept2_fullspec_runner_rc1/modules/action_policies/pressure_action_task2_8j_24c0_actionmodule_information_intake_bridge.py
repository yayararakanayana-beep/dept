"""Task 2-8j-24c0: action-module information intake bridge RC1.

This task connects information to the action-module side without deciding or
executing actions.  It is deliberately an information-intake bridge only:

    upper-pressure route      -> reserved, not used now
    O_t terrain/game route    -> primary current input
    v8 local observation      -> auxiliary current input
    exploration-axis route    -> deferred, not used now

The bridge may carry risk readings, terrain locations, and game-structure
summaries to an action-module intake port.  It must not freeze an action type,
operator family, strength, duration, timing, NO_OP comparison, ActionFrame, or
real ActionModule call.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

TASK2_8J_24C0_VERSION = "actionmodule_information_intake_bridge_rc1"
TASK2_8J_24C0_CONTRACT = (
    "Task2_8j_24c0_actionmodule_information_intake_bridge__"
    "ot_primary_v8_auxiliary__upper_pressure_reserved__exploration_deferred__non_execution"
)

BOUNDARY = {
    "task2_8j_24c0_version": TASK2_8J_24C0_VERSION,
    "task2_8j_24c0_contract": TASK2_8J_24C0_CONTRACT,
    "validation_only": True,
    "information_intake_bridge_only": True,
    "ot_information_primary": True,
    "ot_terrain_map_required": True,
    "ot_game_structure_required": True,
    "v8_local_observation_auxiliary": True,
    "upper_pressure_route_reserved_not_used_now": True,
    "upper_pressure_later_connectable": True,
    "exploration_axis_route_deferred_not_used_now": True,
    "risk_reading_allowed": True,
    "risk_status_is_evidence_state_not_admission_rule": True,
    "simulation_required_later": True,
    "noop_comparison_required_later": True,
    "tail_loss_review_required_later": True,
    "release_required_later": True,
    "rollback_required_later": True,
    "audit_required_later": True,
    "no_runtime_future_input": True,
    "no_hidden_truth_input": True,
    "no_validation_score_runtime_input": True,
    "action_direction_determined": False,
    "action_operator_family_fixed": False,
    "action_type_fixed": False,
    "action_strength_fixed": False,
    "action_duration_fixed": False,
    "action_timing_fixed": False,
    "simulation_prediction_performed": False,
    "noop_comparison_performed": False,
    "tail_loss_review_performed": False,
    "action_candidate_generated": False,
    "concrete_action_generated": False,
    "actionframe_created": False,
    "real_actionmodule_called": False,
    "axis_executed": False,
    "canonical_write_performed": False,
    "gk_writeback_performed": False,
    "ot_writeback_performed": False,
    "exploration_axis_used": False,
    "upper_pressure_used_in_current_decision": False,
    "deployment_ready_claimed": False,
}

REQUIRED_TRUE = [
    "validation_only",
    "information_intake_bridge_only",
    "ot_information_primary",
    "ot_terrain_map_required",
    "ot_game_structure_required",
    "v8_local_observation_auxiliary",
    "upper_pressure_route_reserved_not_used_now",
    "upper_pressure_later_connectable",
    "exploration_axis_route_deferred_not_used_now",
    "risk_reading_allowed",
    "risk_status_is_evidence_state_not_admission_rule",
    "simulation_required_later",
    "noop_comparison_required_later",
    "tail_loss_review_required_later",
    "release_required_later",
    "rollback_required_later",
    "audit_required_later",
    "no_runtime_future_input",
    "no_hidden_truth_input",
    "no_validation_score_runtime_input",
]

FORBIDDEN_TRUE = [
    "action_direction_determined",
    "action_operator_family_fixed",
    "action_type_fixed",
    "action_strength_fixed",
    "action_duration_fixed",
    "action_timing_fixed",
    "simulation_prediction_performed",
    "noop_comparison_performed",
    "tail_loss_review_performed",
    "action_candidate_generated",
    "concrete_action_generated",
    "actionframe_created",
    "real_actionmodule_called",
    "axis_executed",
    "canonical_write_performed",
    "gk_writeback_performed",
    "ot_writeback_performed",
    "exploration_axis_used",
    "upper_pressure_used_in_current_decision",
    "deployment_ready_claimed",
]

CONTRACT_COLUMNS = list(BOUNDARY) + [
    "contract_id",
    "contract_scope",
    "contract_description",
    "current_decision",
    "next_required_task",
]

CHANNEL_COLUMNS = list(BOUNDARY) + [
    "input_channel",
    "channel_status",
    "used_now",
    "required_now",
    "later_connectable",
    "provided_information",
    "current_role",
]

PACKET_COLUMNS = list(BOUNDARY) + [
    "intake_packet_id",
    "source_ot_packet_id",
    "source_v8_local_observation_id",
    "terrain_location_id",
    "risk_name",
    "risk_evidence_status",
    "risk_evidence_status_is_mutable",
    "terrain_map_summary",
    "game_structure_summary",
    "v8_local_observation_summary",
    "upper_pressure_channel_status",
    "exploration_axis_channel_status",
    "actionmodule_intake_port",
    "actionmodule_intake_payload_status",
    "candidate_admission_status",
    "simulation_request_status",
    "noop_comparison_request_status",
    "release_rollback_audit_status",
]

CHECK_COLUMNS = list(BOUNDARY) + [
    "check_id",
    "check_scope",
    "check_description",
    "expected_value",
    "observed_value",
    "check_status",
]

SUMMARY_COLUMNS = list(BOUNDARY) + [
    "contract_count",
    "channel_count",
    "intake_packet_count",
    "risk_names_carried",
    "stable_evidence_risk_count",
    "non_stable_evidence_risk_count",
    "check_count",
    "check_pass_count",
    "actionmodule_information_intake_bridge_decision",
    "next_task",
]

RISK_EVIDENCE_ROWS = [
    {
        "risk_name": "relation_lock",
        "risk_evidence_status": "comparatively_stable_evidence_for_later_simulation",
        "terrain_location_id": "ot_relation_field_cluster",
        "terrain_map_summary": "static_pca_7_relation_lock_terrain_signal_visible",
        "game_structure_summary": "relation_fixation_game_structure_material_visible",
        "v8_local_observation_summary": "local_fixation_check_required_as_auxiliary_precision",
    },
    {
        "risk_name": "oscillation",
        "risk_evidence_status": "comparatively_stable_evidence_for_later_simulation",
        "terrain_location_id": "ot_oscillation_basin",
        "terrain_map_summary": "static_pca_7_oscillation_terrain_signal_visible",
        "game_structure_summary": "reversal_loop_game_structure_material_visible",
        "v8_local_observation_summary": "local_periodicity_and_boundary_check_required",
    },
    {
        "risk_name": "reversibility_loss",
        "risk_evidence_status": "comparatively_stable_evidence_for_later_simulation",
        "terrain_location_id": "ot_return_path_region",
        "terrain_map_summary": "static_pca_7_reversibility_loss_terrain_signal_visible",
        "game_structure_summary": "return_path_closing_game_structure_material_visible",
        "v8_local_observation_summary": "local_return_path_and_rollback_margin_check_required",
    },
    {
        "risk_name": "boundary_fragile",
        "risk_evidence_status": "needs_more_prediction_precision_before_action_admission",
        "terrain_location_id": "ot_boundary_region",
        "terrain_map_summary": "static_pca_7_boundary_fragility_signal_visible_but_not_action_ready",
        "game_structure_summary": "boundary_separation_weak_game_structure_material_visible",
        "v8_local_observation_summary": "local_boundary_precision_required_before_any_action",
    },
    {
        "risk_name": "resource_pressure",
        "risk_evidence_status": "currently_noop_preferred_but_possibility_retained_for_redesign",
        "terrain_location_id": "ot_resource_pressure_region",
        "terrain_map_summary": "static_pca_7_resource_pressure_signal_visible_but_current_action_not_preferred",
        "game_structure_summary": "pressure_diffusion_loss_tail_material_requires_redesign",
        "v8_local_observation_summary": "local_resource_pressure_pattern_check_required_before_redesign",
    },
]


@dataclass(frozen=True)
class ActionModuleInformationIntakeBridgeConfig:
    include_non_stable_risks: bool = True


def _with_boundary(row: dict[str, Any]) -> dict[str, Any]:
    return {**BOUNDARY, **row}


def build_intake_contract() -> pd.DataFrame:
    rows = [
        _with_boundary({
            "contract_id": "task2_8j_24c0_contract_0001",
            "contract_scope": "information_intake_only",
            "contract_description": (
                "Carry O_t terrain/game-structure information and v8 auxiliary local observation "
                "to an action-module-side intake port without deciding actions."
            ),
            "current_decision": "connect_information_to_actionmodule_side_not_action_execution",
            "next_required_task": "simulation_branch_contract_for_NO_OP_vs_action_candidate_later",
        })
    ]
    return pd.DataFrame(rows, columns=CONTRACT_COLUMNS)


def build_input_channel_contract() -> pd.DataFrame:
    rows = [
        _with_boundary({
            "input_channel": "upper_pressure_information",
            "channel_status": "reserved_not_used_now",
            "used_now": False,
            "required_now": False,
            "later_connectable": True,
            "provided_information": "bounded_upper_pressure_route_placeholder",
            "current_role": "kept_separate_for_later_connection",
        }),
        _with_boundary({
            "input_channel": "ot_information",
            "channel_status": "primary_current_route",
            "used_now": True,
            "required_now": True,
            "later_connectable": True,
            "provided_information": "terrain_map,game_structure,risk_reading,terrain_location",
            "current_role": "primary_information_for_later_risk_simulation",
        }),
        _with_boundary({
            "input_channel": "v8_local_observation_information",
            "channel_status": "auxiliary_current_route",
            "used_now": True,
            "required_now": False,
            "later_connectable": True,
            "provided_information": "local_precision,boundary_check,rollback_margin_check,confidence_support",
            "current_role": "auxiliary_precision_and_guard_information",
        }),
        _with_boundary({
            "input_channel": "exploration_axis_information",
            "channel_status": "deferred_not_used_now",
            "used_now": False,
            "required_now": False,
            "later_connectable": True,
            "provided_information": "exploration_axis_placeholder_only",
            "current_role": "explicitly_deferred_for_later_task",
        }),
    ]
    return pd.DataFrame(rows, columns=CHANNEL_COLUMNS)


def build_actionmodule_information_intake_packets(
    config: ActionModuleInformationIntakeBridgeConfig | None = None,
) -> pd.DataFrame:
    cfg = config or ActionModuleInformationIntakeBridgeConfig()
    risk_rows = RISK_EVIDENCE_ROWS if cfg.include_non_stable_risks else [
        r for r in RISK_EVIDENCE_ROWS if r["risk_evidence_status"].startswith("comparatively_stable")
    ]
    rows: list[dict[str, Any]] = []
    for i, risk in enumerate(risk_rows, start=1):
        rows.append(_with_boundary({
            "intake_packet_id": f"task2_8j_24c0_actionmodule_intake_packet_{i:04d}",
            "source_ot_packet_id": f"ot_terrain_game_packet_{i:04d}",
            "source_v8_local_observation_id": f"v8_local_observation_aux_{i:04d}",
            "terrain_location_id": risk["terrain_location_id"],
            "risk_name": risk["risk_name"],
            "risk_evidence_status": risk["risk_evidence_status"],
            "risk_evidence_status_is_mutable": True,
            "terrain_map_summary": risk["terrain_map_summary"],
            "game_structure_summary": risk["game_structure_summary"],
            "v8_local_observation_summary": risk["v8_local_observation_summary"],
            "upper_pressure_channel_status": "reserved_not_used_now",
            "exploration_axis_channel_status": "deferred_not_used_now",
            "actionmodule_intake_port": "information_intake_port_non_execution",
            "actionmodule_intake_payload_status": "information_packet_ready_for_later_simulation_not_action_candidate",
            "candidate_admission_status": "not_evaluated_at_intake",
            "simulation_request_status": "simulation_required_later_not_performed_here",
            "noop_comparison_request_status": "noop_comparison_required_later_not_performed_here",
            "release_rollback_audit_status": "required_later_not_detailed_here",
        }))
    return pd.DataFrame(rows, columns=PACKET_COLUMNS)


def build_intake_checks(
    contract: pd.DataFrame,
    channels: pd.DataFrame,
    packets: pd.DataFrame,
) -> pd.DataFrame:
    channel_status = dict(zip(channels["input_channel"].astype(str), channels["channel_status"].astype(str))) if not channels.empty else {}
    used_now = dict(zip(channels["input_channel"].astype(str), channels["used_now"].astype(bool))) if not channels.empty else {}
    checks = [
        ("check_contract_exists", "contract", "The information-intake contract exists.", True, not contract.empty),
        ("check_ot_primary", "channel", "O_t information is the primary current route.", True, channel_status.get("ot_information") == "primary_current_route" and bool(used_now.get("ot_information", False))),
        ("check_v8_auxiliary", "channel", "v8 local observation is auxiliary current information.", True, channel_status.get("v8_local_observation_information") == "auxiliary_current_route"),
        ("check_upper_pressure_reserved", "channel", "Upper-pressure route is reserved and not used now.", True, channel_status.get("upper_pressure_information") == "reserved_not_used_now" and not bool(used_now.get("upper_pressure_information", True))),
        ("check_exploration_deferred", "channel", "Exploration-axis route is deferred and not used now.", True, channel_status.get("exploration_axis_information") == "deferred_not_used_now" and not bool(used_now.get("exploration_axis_information", True))),
        ("check_packets_exist", "packet", "Information intake packets exist.", True, len(packets) > 0),
        ("check_non_stable_risk_possibility_retained", "risk", "Boundary/resource risks remain carried as evidence states, not permanent exclusions.", True, {"boundary_fragile", "resource_pressure"}.issubset(set(packets["risk_name"].astype(str))) if not packets.empty else False),
        ("check_risk_status_mutable", "risk", "Risk evidence status is mutable and not an admission lock.", True, bool(packets["risk_evidence_status_is_mutable"].astype(bool).all()) if not packets.empty else False),
        ("check_no_action_fixed", "boundary", "No action type/operator/strength/duration/timing is fixed.", False, bool(packets[["action_operator_family_fixed", "action_type_fixed", "action_strength_fixed", "action_duration_fixed", "action_timing_fixed"]].astype(bool).any().any()) if not packets.empty else True),
        ("check_no_simulation_or_noop_comparison", "boundary", "No simulation prediction or NO_OP comparison is performed in this bridge.", False, bool(packets[["simulation_prediction_performed", "noop_comparison_performed", "tail_loss_review_performed"]].astype(bool).any().any()) if not packets.empty else True),
        ("check_no_actionmodule_runtime", "boundary", "No ActionFrame or real ActionModule call occurs.", False, bool(packets[["actionframe_created", "real_actionmodule_called", "axis_executed"]].astype(bool).any().any()) if not packets.empty else True),
        ("check_no_writeback", "boundary", "No canonical/GK/O_t writeback occurs.", False, bool(packets[["canonical_write_performed", "gk_writeback_performed", "ot_writeback_performed"]].astype(bool).any().any()) if not packets.empty else True),
        ("check_no_forbidden_runtime_info", "boundary", "No hidden truth, future input, or validation-score runtime input is allowed.", True, bool(packets[["no_runtime_future_input", "no_hidden_truth_input", "no_validation_score_runtime_input"]].astype(bool).all().all()) if not packets.empty else False),
    ]
    return pd.DataFrame([
        _with_boundary({
            "check_id": check_id,
            "check_scope": scope,
            "check_description": description,
            "expected_value": bool(expected),
            "observed_value": bool(observed),
            "check_status": "pass" if bool(expected) == bool(observed) else "fail",
        })
        for check_id, scope, description, expected, observed in checks
    ], columns=CHECK_COLUMNS)


def build_final_summary(
    contract: pd.DataFrame,
    channels: pd.DataFrame,
    packets: pd.DataFrame,
    checks: pd.DataFrame,
) -> pd.DataFrame:
    check_pass = int((checks["check_status"].astype(str) == "pass").sum()) if not checks.empty else 0
    risk_names = sorted(packets["risk_name"].astype(str).unique()) if not packets.empty else []
    stable_count = int(packets["risk_evidence_status"].astype(str).str.startswith("comparatively_stable").sum()) if not packets.empty else 0
    non_stable_count = int(len(packets) - stable_count)
    decision = (
        "actionmodule_information_intake_bridge_ready_non_execution"
        if len(contract) == 1 and len(channels) == 4 and len(packets) > 0 and len(checks) == check_pass
        else "actionmodule_information_intake_bridge_needs_review"
    )
    rows = [_with_boundary({
        "contract_count": int(len(contract)),
        "channel_count": int(len(channels)),
        "intake_packet_count": int(len(packets)),
        "risk_names_carried": ",".join(risk_names),
        "stable_evidence_risk_count": stable_count,
        "non_stable_evidence_risk_count": non_stable_count,
        "check_count": int(len(checks)),
        "check_pass_count": check_pass,
        "actionmodule_information_intake_bridge_decision": decision,
        "next_task": "Task 2-8j-24c1: simulation branch contract for NO_OP vs action-candidate prediction",
    })]
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)


def validate_tables(
    contract: pd.DataFrame,
    channels: pd.DataFrame,
    packets: pd.DataFrame,
    checks: pd.DataFrame,
    final_summary: pd.DataFrame,
) -> list[str]:
    errors: list[str] = []
    tables = {
        "contract": (contract, CONTRACT_COLUMNS),
        "channels": (channels, CHANNEL_COLUMNS),
        "packets": (packets, PACKET_COLUMNS),
        "checks": (checks, CHECK_COLUMNS),
        "final_summary": (final_summary, SUMMARY_COLUMNS),
    }
    for name, (table, columns) in tables.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_24c0_empty_table:{name}")
            continue
        missing = [c for c in columns if c not in table.columns]
        if missing:
            errors.append(f"task2_8j_24c0_missing_columns:{name}:" + ",".join(missing))
            continue
        for col in REQUIRED_TRUE:
            if not bool(table[col].astype(bool).all()):
                errors.append(f"task2_8j_24c0_required_true_failed:{name}:{col}")
        for col in FORBIDDEN_TRUE:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_24c0_forbidden_true_failed:{name}:{col}")

    if not channels.empty:
        channel_status = dict(zip(channels["input_channel"].astype(str), channels["channel_status"].astype(str)))
        if channel_status.get("ot_information") != "primary_current_route":
            errors.append("task2_8j_24c0_ot_not_primary")
        if channel_status.get("upper_pressure_information") != "reserved_not_used_now":
            errors.append("task2_8j_24c0_upper_pressure_not_reserved")
        if channel_status.get("exploration_axis_information") != "deferred_not_used_now":
            errors.append("task2_8j_24c0_exploration_not_deferred")

    if not packets.empty:
        risk_names = set(packets["risk_name"].astype(str))
        if not {"boundary_fragile", "resource_pressure"}.issubset(risk_names):
            errors.append("task2_8j_24c0_non_stable_risk_possibility_not_carried")
        if packets["candidate_admission_status"].astype(str).ne("not_evaluated_at_intake").any():
            errors.append("task2_8j_24c0_candidate_admission_evaluated_too_early")
        if packets["actionmodule_intake_port"].astype(str).ne("information_intake_port_non_execution").any():
            errors.append("task2_8j_24c0_wrong_intake_port")

    if not checks.empty and set(checks["check_status"].astype(str)) != {"pass"}:
        errors.append("task2_8j_24c0_checks_not_all_pass")

    if not final_summary.empty:
        decision = str(final_summary["actionmodule_information_intake_bridge_decision"].iloc[0])
        if decision != "actionmodule_information_intake_bridge_ready_non_execution":
            errors.append("task2_8j_24c0_final_decision_not_ready")

    return errors


def build_and_validate_actionmodule_information_intake_bridge(
    config: ActionModuleInformationIntakeBridgeConfig | None = None,
):
    contract = build_intake_contract()
    channels = build_input_channel_contract()
    packets = build_actionmodule_information_intake_packets(config)
    checks = build_intake_checks(contract, channels, packets)
    final_summary = build_final_summary(contract, channels, packets, checks)
    errors = validate_tables(contract, channels, packets, checks, final_summary)
    summary = final_summary.iloc[0].to_dict() if not final_summary.empty else {}
    summary["validation_errors"] = errors
    summary["risk_evidence_statuses"] = sorted(packets["risk_evidence_status"].astype(str).unique()) if not packets.empty else []
    summary["channels"] = channels[["input_channel", "channel_status", "used_now"]].to_dict(orient="records") if not channels.empty else []
    return contract, channels, packets, checks, final_summary, errors, summary
