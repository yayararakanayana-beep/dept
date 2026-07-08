"""Task 2-8j-20b: macro game risk simulator contract RC1.

This freezes the missing bridge before action-candidate generation:
light observation gate -> coarse macro-game risk simulator contract -> risk
confidence and dynamics-direction output -> action-module shaping functions.

The contract is deliberately not a high-resolution forecaster and not a long-term
prediction engine. It is a short-horizon, coarse, risk-confidence simulator that
is invoked only when observation indicates meaningful risk. This file validates
schemas and boundary rules only; it does not run a simulator and does not execute
or generate concrete actions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from .pressure_action_task2_8j_20_v2_terrain_action_parameter_sweep_dry_run import (
    V2TerrainActionParameterSweepDryRunConfig,
    build_and_validate_v2_terrain_action_parameter_sweep_dry_run,
)

TASK2_8J_20B_VERSION = "macro_game_risk_simulator_contract_rc1"
TASK20_ACCEPTED_DECISION = "v2_terrain_action_parameter_sweep_dry_run_ready_without_execution"

BOUNDARY: dict[str, Any] = {
    "task2_8j_20b_version": TASK2_8J_20B_VERSION,
    "validation_only": True,
    "contract_only": True,
    "coarse_macro_game_structure_only": True,
    "not_high_resolution_forecast": True,
    "not_long_term_forecast": True,
    "risk_prediction_only": True,
    "short_horizon_only": True,
    "observation_gate_required": True,
    "simulator_runs_only_when_gate_open": True,
    "system_visible_information_only": True,
    "gt_main_map_name": "static_pca_7",
    "gt_main_component_count": 7,
    "source_task20_required": True,
    "semantic_recipe_primary_key_forbidden": True,
    "terrain_information_primary_required": True,
    "risk_label_used_only_for_evaluation": True,
    "v2_oracle_results_hint_only": True,
    "v2_oracle_results_not_direct_action_input": True,
    "no_op_baseline_required": True,
    "risk_confidence_required": True,
    "dynamics_direction_required": True,
    "action_direction_required_after_risk": True,
    "release_rollback_audit_required": True,
    "simulator_executed": False,
    "high_resolution_state_generated": False,
    "long_term_forecast_generated": False,
    "action_candidate_generated": False,
    "concrete_action_generated": False,
    "action_effect_prediction_generated": False,
    "effect_prediction_model_executed": False,
    "expected_value_final_judgment_performed": False,
    "real_actionmodule_called": False,
    "axis_executed": False,
    "hidden_truth_input": False,
    "future_information_used": False,
    "canonical_write_performed": False,
}

REQUIRED_TRUE = [
    "validation_only", "contract_only", "coarse_macro_game_structure_only", "not_high_resolution_forecast",
    "not_long_term_forecast", "risk_prediction_only", "short_horizon_only", "observation_gate_required",
    "simulator_runs_only_when_gate_open", "system_visible_information_only", "source_task20_required",
    "semantic_recipe_primary_key_forbidden", "terrain_information_primary_required", "risk_label_used_only_for_evaluation",
    "v2_oracle_results_hint_only", "v2_oracle_results_not_direct_action_input", "no_op_baseline_required",
    "risk_confidence_required", "dynamics_direction_required", "action_direction_required_after_risk",
    "release_rollback_audit_required",
]

FORBIDDEN_TRUE = [
    "simulator_executed", "high_resolution_state_generated", "long_term_forecast_generated", "action_candidate_generated",
    "concrete_action_generated", "action_effect_prediction_generated", "effect_prediction_model_executed",
    "expected_value_final_judgment_performed", "real_actionmodule_called", "axis_executed", "hidden_truth_input",
    "future_information_used", "canonical_write_performed",
]

GATE_COLUMNS = list(BOUNDARY) + [
    "gate_signal_id", "gate_signal_name", "signal_source", "gate_threshold_rule", "gate_output", "gate_status",
]
GAME_INPUT_COLUMNS = list(BOUNDARY) + [
    "input_id", "input_group", "input_name", "description", "required_for", "input_status",
]
SIM_OUTPUT_COLUMNS = list(BOUNDARY) + [
    "output_id", "output_group", "output_name", "output_meaning", "consumer_function", "output_status",
]
FUNCTION_COLUMNS = list(BOUNDARY) + [
    "function_id", "function_name", "function_role", "input_contract", "output_contract", "call_order", "function_status",
]
CHECK_COLUMNS = list(BOUNDARY) + [
    "check_id", "check_scope", "check_description", "expected_value", "observed_value", "check_status",
]
SUMMARY_COLUMNS = list(BOUNDARY) + [
    "gate_signal_count", "game_input_count", "sim_output_count", "function_contract_count",
    "contract_check_count", "contract_check_pass_count", "task20_ready",
    "macro_game_risk_simulator_contract_decision", "next_task",
]


@dataclass(frozen=True)
class MacroGameRiskSimulatorContractConfig:
    require_task20_ready: bool = True


def _with_boundary(row: dict[str, Any]) -> dict[str, Any]:
    return {**BOUNDARY, **row}


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def build_observation_gate_contract() -> pd.DataFrame:
    rows = [
        ("gate_01_pressure_gradient", "pressure_gradient_rise", "relation_field", "open_if_mid_or_high_and_persistent", "run_macro_risk_simulator"),
        ("gate_02_reversibility", "reversibility_thinning", "O_t", "open_if_return_path_is_thinning", "run_macro_risk_simulator"),
        ("gate_03_escape_path", "escape_path_thinning", "relation_field", "open_if_escape_capacity_falls", "run_macro_risk_simulator"),
        ("gate_04_boundary", "boundary_distance_low", "O_t", "open_if_boundary_is_close_or_fragile", "run_macro_risk_simulator"),
        ("gate_05_lock", "relation_lock_possible", "O_t", "open_if_lock_signal_and_direction_exist", "run_macro_risk_simulator"),
        ("gate_06_oscillation", "oscillation_or_phase_delay", "O_t", "open_if_oscillation_increases", "run_macro_risk_simulator"),
        ("gate_07_uncertainty", "uncertainty_rising", "audit", "open_for_review_not_direct_action", "run_macro_risk_simulator_for_confidence_only"),
    ]
    return pd.DataFrame([
        _with_boundary({
            "gate_signal_id": r[0], "gate_signal_name": r[1], "signal_source": r[2],
            "gate_threshold_rule": r[3], "gate_output": r[4], "gate_status": "gate_contract_ready",
        }) for r in rows
    ], columns=GATE_COLUMNS)


def build_macro_game_input_contract() -> pd.DataFrame:
    rows = [
        ("input_01", "coarse_game_structure", "nodes_and_regions", "coarse actors, regions, or macro loci", "structure_state"),
        ("input_02", "coarse_game_structure", "relation_edges", "dependency, coordination, pressure, and escape edges", "structure_state"),
        ("input_03", "state", "pressure_gradient", "macro pressure accumulation direction", "risk_confidence"),
        ("input_04", "state", "reversibility", "return-path thickness at macro scale", "risk_confidence"),
        ("input_05", "state", "boundary_distance", "coarse distance to fragile boundary", "risk_confidence"),
        ("input_06", "state", "neighbor_capacity", "available coarse absorption capacity", "dynamics_direction"),
        ("input_07", "state", "escape_path_capacity", "whether pressure can leave the lock basin", "dynamics_direction"),
        ("input_08", "state", "flow_velocity_and_curvature", "oscillation or steep-gradient proxy", "risk_confidence"),
        ("input_09", "audit", "uncertainty", "confidence penalty and review gate", "risk_confidence"),
        ("input_10", "baseline", "NO_OP_baseline", "what the coarse structure tends to do without action", "risk_comparison"),
    ]
    return pd.DataFrame([
        _with_boundary({
            "input_id": r[0], "input_group": r[1], "input_name": r[2], "description": r[3],
            "required_for": r[4], "input_status": "macro_game_input_contract_ready",
        }) for r in rows
    ], columns=GAME_INPUT_COLUMNS)


def build_simulator_output_contract() -> pd.DataFrame:
    rows = [
        ("output_01", "risk_confidence", "relation_lock_confidence", "probability-like risk confidence, not a truth label", "risk_to_direction"),
        ("output_02", "risk_confidence", "resource_pressure_confidence", "pressure accumulation risk confidence", "risk_to_direction"),
        ("output_03", "risk_confidence", "reversibility_loss_confidence", "return-path loss confidence", "risk_to_direction"),
        ("output_04", "risk_confidence", "boundary_fragile_confidence", "fragile boundary approach confidence", "risk_to_direction"),
        ("output_05", "risk_confidence", "oscillation_confidence", "oscillation or phase-delay risk confidence", "risk_to_direction"),
        ("output_06", "dynamics_direction", "dominant_pressure_direction", "where coarse pressure accumulates", "action_direction"),
        ("output_07", "dynamics_direction", "escape_or_return_direction", "where escape or return path exists", "action_direction"),
        ("output_08", "dynamics_direction", "forbidden_push_direction", "direction that would worsen boundary or irreversibility", "action_direction"),
        ("output_09", "comparison", "NO_OP_risk_summary", "short-horizon risk under no action", "NO_OP_review"),
    ]
    return pd.DataFrame([
        _with_boundary({
            "output_id": r[0], "output_group": r[1], "output_name": r[2], "output_meaning": r[3],
            "consumer_function": r[4], "output_status": "simulator_output_contract_ready_not_executed",
        }) for r in rows
    ], columns=SIM_OUTPUT_COLUMNS)


def build_actionmodule_function_contract() -> pd.DataFrame:
    rows = [
        ("fn_01", "should_run_macro_risk_simulator", "observed risk gate", "O_t + relation_field + audit", "run_or_monitor", 1),
        ("fn_02", "build_coarse_macro_game_state", "coarse game-state builder", "G_t + relation_field + O_t", "macro_game_state", 2),
        ("fn_03", "simulate_short_horizon_NO_OP_risk", "short-horizon risk simulator", "macro_game_state + NO_OP", "risk_confidence + dynamics_direction", 3),
        ("fn_04", "estimate_risk_confidence", "risk confidence shaper", "simulator_output", "risk_confidence_distribution", 4),
        ("fn_05", "extract_dynamics_direction", "direction extractor", "simulator_output", "dominant / escape / forbidden directions", 5),
        ("fn_06", "infer_action_direction", "action-direction selector", "risk_confidence + dynamics_direction", "action_direction_material", 6),
        ("fn_07", "select_terrain_operator", "operator selector", "action_direction_material + Task20 operator priorities", "operator_material", 7),
        ("fn_08", "shape_release_rollback_audit", "safety shaping", "operator_material + uncertainty + NO_OP", "release / rollback / audit material", 8),
        ("fn_09", "review_against_NO_OP", "candidate gate review", "shaped_material + NO_OP_risk_summary", "candidate_material_or_NO_OP_or_review", 9),
    ]
    return pd.DataFrame([
        _with_boundary({
            "function_id": r[0], "function_name": r[1], "function_role": r[2], "input_contract": r[3],
            "output_contract": r[4], "call_order": int(r[5]), "function_status": "function_contract_ready_not_runtime",
        }) for r in rows
    ], columns=FUNCTION_COLUMNS)


def build_contract_checks(gate: pd.DataFrame, inputs: pd.DataFrame, outputs: pd.DataFrame, functions: pd.DataFrame, task20_ready: bool) -> pd.DataFrame:
    checks = [
        ("check_task20_ready", "upstream", "Task20 parameter sweep dry-run is available.", True, task20_ready),
        ("check_gate_exists", "gate", "Observation gate signals exist.", True, len(gate) >= 6),
        ("check_inputs_exist", "input", "Coarse macro-game inputs exist.", True, len(inputs) >= 9),
        ("check_outputs_exist", "output", "Risk confidence and dynamics outputs exist.", True, len(outputs) >= 8),
        ("check_functions_exist", "function", "Action-module shaping function contracts exist.", True, len(functions) >= 8),
        ("check_gate_before_simulator", "order", "Gate precedes simulator call.", True, int(functions.loc[functions["function_name"] == "should_run_macro_risk_simulator", "call_order"].iloc[0]) < int(functions.loc[functions["function_name"] == "simulate_short_horizon_NO_OP_risk", "call_order"].iloc[0])),
        ("check_risk_before_action_direction", "order", "Risk confidence precedes action direction.", True, int(functions.loc[functions["function_name"] == "estimate_risk_confidence", "call_order"].iloc[0]) < int(functions.loc[functions["function_name"] == "infer_action_direction", "call_order"].iloc[0])),
        ("check_direction_before_operator", "order", "Action direction precedes operator selection.", True, int(functions.loc[functions["function_name"] == "infer_action_direction", "call_order"].iloc[0]) < int(functions.loc[functions["function_name"] == "select_terrain_operator", "call_order"].iloc[0])),
        ("check_no_execution", "boundary", "Simulator/action execution is not performed in this contract.", False, bool(functions["simulator_executed"].astype(bool).any() or functions["axis_executed"].astype(bool).any())),
        ("check_no_high_resolution", "boundary", "No high-resolution state is generated.", False, bool(functions["high_resolution_state_generated"].astype(bool).any())),
        ("check_no_long_term", "boundary", "No long-term forecast is generated.", False, bool(functions["long_term_forecast_generated"].astype(bool).any())),
        ("check_no_hidden_future", "boundary", "No hidden truth or future information is used.", False, bool(functions["hidden_truth_input"].astype(bool).any() or functions["future_information_used"].astype(bool).any())),
    ]
    return pd.DataFrame([
        _with_boundary({"check_id": c[0], "check_scope": c[1], "check_description": c[2], "expected_value": bool(c[3]), "observed_value": bool(c[4]), "check_status": "pass" if bool(c[3]) == bool(c[4]) else "fail"})
        for c in checks
    ], columns=CHECK_COLUMNS)


def build_final_summary(gate: pd.DataFrame, inputs: pd.DataFrame, outputs: pd.DataFrame, functions: pd.DataFrame, checks: pd.DataFrame, task20_ready: bool) -> pd.DataFrame:
    pass_count = int((checks["check_status"].astype(str) == "pass").sum()) if not checks.empty else 0
    decision = "macro_game_risk_simulator_contract_ready" if task20_ready and len(checks) == pass_count else "macro_game_risk_simulator_contract_needs_review"
    return pd.DataFrame([_with_boundary({
        "gate_signal_count": len(gate),
        "game_input_count": len(inputs),
        "sim_output_count": len(outputs),
        "function_contract_count": len(functions),
        "contract_check_count": len(checks),
        "contract_check_pass_count": pass_count,
        "task20_ready": bool(task20_ready),
        "macro_game_risk_simulator_contract_decision": decision,
        "next_task": "Task 2-8j-22: implement gated macro-game risk simulator dry-run",
    })], columns=SUMMARY_COLUMNS)


def validate_macro_game_risk_simulator_contract_tables(gate: pd.DataFrame, inputs: pd.DataFrame, outputs: pd.DataFrame, functions: pd.DataFrame, checks: pd.DataFrame, final_summary: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    tables = {
        "gate": (gate, GATE_COLUMNS),
        "inputs": (inputs, GAME_INPUT_COLUMNS),
        "outputs": (outputs, SIM_OUTPUT_COLUMNS),
        "functions": (functions, FUNCTION_COLUMNS),
        "checks": (checks, CHECK_COLUMNS),
        "final_summary": (final_summary, SUMMARY_COLUMNS),
    }
    for name, (table, columns) in tables.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_20b_empty_table:{name}"); continue
        missing = [c for c in columns if c not in table.columns]
        if missing:
            errors.append(f"task2_8j_20b_missing_columns:{name}:" + ",".join(missing)); continue
        for col in REQUIRED_TRUE:
            if not bool(table[col].astype(bool).all()):
                errors.append(f"task2_8j_20b_required_true_not_all_true:{name}:{col}")
        for col in FORBIDDEN_TRUE:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_20b_forbidden_true:{name}:{col}")
        if set(table["gt_main_map_name"].astype(str)) != {"static_pca_7"}:
            errors.append(f"task2_8j_20b_wrong_gt_main_map_name:{name}")
        if set(table["gt_main_component_count"].astype(int)) != {7}:
            errors.append(f"task2_8j_20b_wrong_gt_component_count:{name}")
    if checks is not None and not checks.empty and not bool((checks["check_status"].astype(str) == "pass").all()):
        errors.append("task2_8j_20b_check_failed")
    if functions is not None and not functions.empty:
        order = dict(zip(functions["function_name"].astype(str), functions["call_order"].astype(int)))
        if not (order["should_run_macro_risk_simulator"] < order["simulate_short_horizon_NO_OP_risk"] < order["estimate_risk_confidence"] < order["infer_action_direction"] < order["select_terrain_operator"]):
            errors.append("task2_8j_20b_wrong_function_order")
    return errors


def build_and_validate_macro_game_risk_simulator_contract(cfg: MacroGameRiskSimulatorContractConfig | None = None, **_unused: object) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    cfg = cfg or MacroGameRiskSimulatorContractConfig()
    _states, _sweep, _op_summary, _checks20, _final20, task20_errors, task20_summary = build_and_validate_v2_terrain_action_parameter_sweep_dry_run(cfg=V2TerrainActionParameterSweepDryRunConfig(max_rows_per_operator=4))
    task20_ready = len(task20_errors) == 0 and str(task20_summary.get("v2_terrain_action_parameter_sweep_dry_run_decision", "")).startswith(TASK20_ACCEPTED_DECISION)
    if not cfg.require_task20_ready:
        task20_ready = True
    gate = build_observation_gate_contract()
    inputs = build_macro_game_input_contract()
    outputs = build_simulator_output_contract()
    functions = build_actionmodule_function_contract()
    checks = build_contract_checks(gate, inputs, outputs, functions, task20_ready)
    final_summary = build_final_summary(gate, inputs, outputs, functions, checks, task20_ready)
    errors = ([f"task2_8j_20b_upstream_20_error:{e}" for e in task20_errors] if cfg.require_task20_ready else []) + validate_macro_game_risk_simulator_contract_tables(gate, inputs, outputs, functions, checks, final_summary)
    summary = {
        "gt_main_map_name": "static_pca_7",
        "gt_main_component_count": 7,
        "task20_decision": task20_summary.get("v2_terrain_action_parameter_sweep_dry_run_decision", ""),
        "gate_signal_count": _safe_int(final_summary["gate_signal_count"].iloc[0]),
        "game_input_count": _safe_int(final_summary["game_input_count"].iloc[0]),
        "sim_output_count": _safe_int(final_summary["sim_output_count"].iloc[0]),
        "function_contract_count": _safe_int(final_summary["function_contract_count"].iloc[0]),
        "contract_check_count": _safe_int(final_summary["contract_check_count"].iloc[0]),
        "contract_check_pass_count": _safe_int(final_summary["contract_check_pass_count"].iloc[0]),
        "task20_ready": bool(task20_ready),
        "macro_game_risk_simulator_contract_decision": str(final_summary["macro_game_risk_simulator_contract_decision"].iloc[0]),
        "not_high_resolution_forecast": True,
        "not_long_term_forecast": True,
        "risk_prediction_only": True,
        "simulator_runs_only_when_gate_open": True,
        "simulator_executed": False,
        "action_candidate_generated": False,
        "action_effect_prediction_generated": False,
        "axis_executed": False,
        "real_actionmodule_called": False,
        "validation_errors": errors,
    }
    return gate, inputs, outputs, functions, checks, final_summary, errors, summary
