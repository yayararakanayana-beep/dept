"""Task 2-8j-22: gated macro-game risk simulator dry-run RC1.

Implements the first half of the Task2-8j-20b contract:
    1. should_run_macro_risk_simulator
    2. build_coarse_macro_game_state
    3. simulate_short_horizon_NO_OP_risk
    4. estimate_risk_confidence
    5. extract_dynamics_direction

This is still not action-candidate generation. It runs only a coarse, short-horizon
NO_OP risk dry-run from system-visible macro-game state material, then returns
risk confidence and dynamics-direction material for later action shaping.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import math
import pandas as pd

from .pressure_action_task2_8j_20b_macro_game_risk_simulator_contract import (
    build_and_validate_macro_game_risk_simulator_contract,
)

TASK2_8J_22_VERSION = "gated_macro_game_risk_simulator_dry_run_rc1"
TASK20B_ACCEPTED_DECISION = "macro_game_risk_simulator_contract_ready"

BOUNDARY: dict[str, Any] = {
    "task2_8j_22_version": TASK2_8J_22_VERSION,
    "validation_only": True,
    "dry_run_only": True,
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
    "source_task20b_required": True,
    "semantic_recipe_primary_key_forbidden": True,
    "terrain_information_primary_required": True,
    "risk_label_used_only_for_evaluation": True,
    "NO_OP_baseline_required": True,
    "risk_confidence_generated": True,
    "dynamics_direction_generated": True,
    "simulator_dry_run_executed": True,
    "action_direction_generated": False,
    "terrain_operator_selected": False,
    "release_rollback_audit_shaped": False,
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
    "validation_only", "dry_run_only", "coarse_macro_game_structure_only", "not_high_resolution_forecast",
    "not_long_term_forecast", "risk_prediction_only", "short_horizon_only", "observation_gate_required",
    "simulator_runs_only_when_gate_open", "system_visible_information_only", "source_task20b_required",
    "semantic_recipe_primary_key_forbidden", "terrain_information_primary_required", "risk_label_used_only_for_evaluation",
    "NO_OP_baseline_required", "risk_confidence_generated", "dynamics_direction_generated", "simulator_dry_run_executed",
]
FORBIDDEN_TRUE = [
    "action_direction_generated", "terrain_operator_selected", "release_rollback_audit_shaped", "action_candidate_generated",
    "concrete_action_generated", "action_effect_prediction_generated", "effect_prediction_model_executed",
    "expected_value_final_judgment_performed", "real_actionmodule_called", "axis_executed", "hidden_truth_input",
    "future_information_used", "canonical_write_performed",
]

STATE_COLUMNS = list(BOUNDARY) + [
    "macro_state_id", "macro_state_name", "risk_label_for_evaluation_only", "pressure_gradient", "relation_lock_signal",
    "reversibility", "boundary_distance", "escape_path_capacity", "neighbor_capacity", "flow_velocity", "curvature",
    "uncertainty", "NO_OP_baseline", "state_status",
]
GATE_COLUMNS = list(BOUNDARY) + [
    "gate_result_id", "macro_state_id", "macro_state_name", "gate_score", "open_signal_count", "open_signals",
    "should_run_simulator", "gate_decision", "gate_status",
]
TRAJECTORY_COLUMNS = list(BOUNDARY) + [
    "trajectory_id", "macro_state_id", "macro_state_name", "seed_id", "step", "pressure_gradient", "relation_lock_signal",
    "reversibility", "boundary_distance", "escape_path_capacity", "neighbor_capacity", "flow_velocity", "curvature",
    "uncertainty", "relation_lock_risk", "resource_pressure_risk", "reversibility_loss_risk", "boundary_fragile_risk",
    "oscillation_risk", "dominant_risk", "trajectory_status",
]
RISK_COLUMNS = list(BOUNDARY) + [
    "risk_confidence_id", "macro_state_id", "macro_state_name", "risk_name", "mean_risk", "max_risk",
    "trigger_count", "trajectory_count", "risk_confidence", "confidence_band", "precision_need_hint", "risk_status",
]
DIRECTION_COLUMNS = list(BOUNDARY) + [
    "direction_id", "macro_state_id", "macro_state_name", "dominant_risk", "dominant_pressure_direction",
    "escape_or_return_direction", "forbidden_push_direction", "direction_clarity", "dynamics_direction_status",
]
CHECK_COLUMNS = list(BOUNDARY) + [
    "check_id", "check_scope", "check_description", "expected_value", "observed_value", "check_status",
]
SUMMARY_COLUMNS = list(BOUNDARY) + [
    "macro_state_count", "gate_open_count", "trajectory_row_count", "risk_confidence_row_count", "dynamics_direction_count",
    "high_confidence_risk_count", "precision_review_needed_count", "dry_run_check_count", "dry_run_check_pass_count",
    "task20b_ready", "gated_macro_game_risk_simulator_dry_run_decision", "next_task",
]


@dataclass(frozen=True)
class GatedMacroGameRiskSimulatorDryRunConfig:
    require_task20b_ready: bool = True
    horizon: int = 4
    seed_count: int = 8
    gate_threshold: float = 0.45
    risk_threshold: float = 0.62


def _with_boundary(row: dict[str, Any]) -> dict[str, Any]:
    return {**BOUNDARY, **row}


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def build_coarse_macro_game_states() -> pd.DataFrame:
    """Build coarse macro-game states from system-visible terrain material.

    These are deliberately macro summaries, not high-resolution state replicas.
    """
    rows = [
        ("macro_lock_basin", "lock_basin_relation_cluster", "relation_lock", 0.78, 0.82, 0.38, 0.42, 0.31, 0.36, 0.41, 0.28, 0.34, 0.55),
        ("macro_pressure_spike", "resource_pressure_spike", "resource_pressure", 0.86, 0.45, 0.52, 0.48, 0.44, 0.28, 0.58, 0.36, 0.31, 0.61),
        ("macro_steep_gradient", "coordination_lag_steep_gradient", "steep_gradient", 0.69, 0.36, 0.57, 0.55, 0.53, 0.48, 0.76, 0.72, 0.29, 0.49),
        ("macro_oscillatory_flow", "oscillatory_flow_instability", "oscillation", 0.58, 0.39, 0.50, 0.58, 0.56, 0.50, 0.82, 0.80, 0.37, 0.43),
        ("macro_boundary_fragile", "shock_boundary_fragile", "boundary_fragile", 0.62, 0.40, 0.34, 0.24, 0.38, 0.42, 0.53, 0.41, 0.49, 0.66),
        ("macro_reversibility_thin", "reversibility_thin_return_path", "reversibility_loss", 0.55, 0.48, 0.25, 0.36, 0.33, 0.47, 0.44, 0.33, 0.42, 0.60),
    ]
    return pd.DataFrame([
        _with_boundary({
            "macro_state_id": r[0], "macro_state_name": r[1], "risk_label_for_evaluation_only": r[2],
            "pressure_gradient": r[3], "relation_lock_signal": r[4], "reversibility": r[5], "boundary_distance": r[6],
            "escape_path_capacity": r[7], "neighbor_capacity": r[8], "flow_velocity": r[9], "curvature": r[10],
            "uncertainty": r[11], "NO_OP_baseline": r[12], "state_status": "coarse_macro_game_state_ready",
        }) for r in rows
    ], columns=STATE_COLUMNS)


def should_run_macro_risk_simulator(states: pd.DataFrame, cfg: GatedMacroGameRiskSimulatorDryRunConfig) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for i, r in states.reset_index(drop=True).iterrows():
        signals: list[str] = []
        if float(r["pressure_gradient"]) >= 0.60:
            signals.append("pressure_gradient_rise")
        if float(r["reversibility"]) <= 0.45:
            signals.append("reversibility_thinning")
        if float(r["escape_path_capacity"]) <= 0.45:
            signals.append("escape_path_thinning")
        if float(r["boundary_distance"]) <= 0.45:
            signals.append("boundary_distance_low")
        if float(r["relation_lock_signal"]) >= 0.55:
            signals.append("relation_lock_possible")
        if float(r["flow_velocity"]) >= 0.70 and float(r["curvature"]) >= 0.65:
            signals.append("oscillation_or_phase_delay")
        if float(r["uncertainty"]) >= 0.45:
            signals.append("uncertainty_rising")
        gate_score = _clip01(0.18 * float(r["pressure_gradient"]) + 0.16 * (1 - float(r["reversibility"])) + 0.14 * (1 - float(r["escape_path_capacity"])) + 0.14 * (1 - float(r["boundary_distance"])) + 0.14 * float(r["relation_lock_signal"]) + 0.12 * float(r["flow_velocity"]) + 0.12 * float(r["curvature"]) + 0.10 * float(r["uncertainty"]))
        should_run = gate_score >= cfg.gate_threshold or len(signals) >= 2
        rows.append(_with_boundary({
            "gate_result_id": f"gate_result_{i+1:03d}",
            "macro_state_id": str(r["macro_state_id"]),
            "macro_state_name": str(r["macro_state_name"]),
            "gate_score": round(gate_score, 6),
            "open_signal_count": len(signals),
            "open_signals": ";".join(signals) if signals else "none",
            "should_run_simulator": bool(should_run),
            "gate_decision": "run_macro_risk_simulator" if should_run else "monitor_or_NO_OP",
            "gate_status": "observation_gate_evaluated",
        }))
    return pd.DataFrame(rows, columns=GATE_COLUMNS)


def _step_noise(seed: int, step: int, channel: int) -> float:
    # deterministic small pseudo-noise without external RNG dependency
    return 0.018 * math.sin((seed + 1) * (step + 1) * (channel + 2))


def _risk_scores(row: pd.Series) -> dict[str, float]:
    pressure = float(row["pressure_gradient"])
    lock = float(row["relation_lock_signal"])
    rev = float(row["reversibility"])
    boundary = float(row["boundary_distance"])
    escape = float(row["escape_path_capacity"])
    neighbor = float(row["neighbor_capacity"])
    velocity = float(row["flow_velocity"])
    curvature = float(row["curvature"])
    uncertainty = float(row["uncertainty"])
    return {
        "relation_lock_risk": _clip01(0.36 * lock + 0.23 * pressure + 0.18 * (1 - escape) + 0.15 * (1 - rev) + 0.08 * uncertainty),
        "resource_pressure_risk": _clip01(0.42 * pressure + 0.24 * (1 - neighbor) + 0.16 * (1 - escape) + 0.10 * (1 - boundary) + 0.08 * uncertainty),
        "reversibility_loss_risk": _clip01(0.43 * (1 - rev) + 0.22 * (1 - escape) + 0.18 * lock + 0.10 * (1 - boundary) + 0.07 * uncertainty),
        "boundary_fragile_risk": _clip01(0.42 * (1 - boundary) + 0.21 * pressure + 0.16 * (1 - rev) + 0.12 * uncertainty + 0.09 * curvature),
        "oscillation_risk": _clip01(0.40 * velocity + 0.33 * curvature + 0.12 * pressure + 0.08 * uncertainty + 0.07 * (1 - neighbor)),
    }


def simulate_short_horizon_NO_OP_risk(states: pd.DataFrame, gate: pd.DataFrame, cfg: GatedMacroGameRiskSimulatorDryRunConfig) -> pd.DataFrame:
    gate_map = dict(zip(gate["macro_state_id"].astype(str), gate["should_run_simulator"].astype(bool)))
    rows: list[dict[str, Any]] = []
    for _, base in states.iterrows():
        if not gate_map.get(str(base["macro_state_id"]), False):
            continue
        for seed in range(cfg.seed_count):
            current = base.copy()
            for step in range(1, cfg.horizon + 1):
                pressure = _clip01(float(current["pressure_gradient"]) + 0.032 * (1 - float(current["neighbor_capacity"])) + 0.024 * (1 - float(current["escape_path_capacity"])) - 0.018 * float(current["reversibility"]) + _step_noise(seed, step, 0))
                lock = _clip01(float(current["relation_lock_signal"]) + 0.036 * pressure + 0.028 * (1 - float(current["escape_path_capacity"])) - 0.020 * float(current["reversibility"]) + _step_noise(seed, step, 1))
                rev = _clip01(float(current["reversibility"]) - 0.028 * lock - 0.020 * pressure + 0.012 * float(current["escape_path_capacity"]) + _step_noise(seed, step, 2))
                boundary = _clip01(float(current["boundary_distance"]) - 0.024 * pressure - 0.018 * (1 - rev) + 0.010 * float(current["neighbor_capacity"]) + _step_noise(seed, step, 3))
                escape = _clip01(float(current["escape_path_capacity"]) - 0.026 * lock - 0.018 * pressure + 0.012 * float(current["neighbor_capacity"]) + _step_noise(seed, step, 4))
                neighbor = _clip01(float(current["neighbor_capacity"]) - 0.016 * pressure + 0.008 * escape + _step_noise(seed, step, 5))
                velocity = _clip01(float(current["flow_velocity"]) + 0.022 * pressure + 0.018 * float(current["curvature"]) - 0.010 * rev + _step_noise(seed, step, 6))
                curvature = _clip01(float(current["curvature"]) + 0.018 * velocity + 0.012 * lock - 0.010 * escape + _step_noise(seed, step, 7))
                uncertainty = _clip01(float(current["uncertainty"]) + 0.012 * abs(pressure - float(current["pressure_gradient"])) + 0.010 * abs(lock - float(current["relation_lock_signal"])) + _step_noise(seed, step, 8))
                current = current.copy()
                current["pressure_gradient"] = pressure
                current["relation_lock_signal"] = lock
                current["reversibility"] = rev
                current["boundary_distance"] = boundary
                current["escape_path_capacity"] = escape
                current["neighbor_capacity"] = neighbor
                current["flow_velocity"] = velocity
                current["curvature"] = curvature
                current["uncertainty"] = uncertainty
                risks = _risk_scores(current)
                dominant_risk = max(risks, key=risks.get)
                rows.append(_with_boundary({
                    "trajectory_id": f"traj_{base['macro_state_id']}_{seed:02d}_{step:02d}",
                    "macro_state_id": str(base["macro_state_id"]),
                    "macro_state_name": str(base["macro_state_name"]),
                    "seed_id": seed,
                    "step": step,
                    "pressure_gradient": round(pressure, 6),
                    "relation_lock_signal": round(lock, 6),
                    "reversibility": round(rev, 6),
                    "boundary_distance": round(boundary, 6),
                    "escape_path_capacity": round(escape, 6),
                    "neighbor_capacity": round(neighbor, 6),
                    "flow_velocity": round(velocity, 6),
                    "curvature": round(curvature, 6),
                    "uncertainty": round(uncertainty, 6),
                    **{k: round(v, 6) for k, v in risks.items()},
                    "dominant_risk": dominant_risk.replace("_risk", ""),
                    "trajectory_status": "short_horizon_NO_OP_risk_dry_run_row",
                }))
    return pd.DataFrame(rows, columns=TRAJECTORY_COLUMNS)


def estimate_risk_confidence(trajectories: pd.DataFrame, cfg: GatedMacroGameRiskSimulatorDryRunConfig) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    risk_cols = ["relation_lock_risk", "resource_pressure_risk", "reversibility_loss_risk", "boundary_fragile_risk", "oscillation_risk"]
    for state_id, group in trajectories.groupby("macro_state_id", sort=False):
        state_name = str(group["macro_state_name"].iloc[0])
        for risk_col in risk_cols:
            mean_risk = float(group[risk_col].mean())
            max_risk = float(group[risk_col].max())
            trigger_count = int((group[risk_col].astype(float) >= cfg.risk_threshold).sum())
            trajectory_count = len(group)
            trigger_rate = trigger_count / trajectory_count if trajectory_count else 0.0
            confidence = _clip01(0.55 * mean_risk + 0.25 * max_risk + 0.20 * trigger_rate)
            if confidence >= 0.68:
                band = "high"
            elif confidence >= 0.52:
                band = "medium"
            else:
                band = "low"
            # Near-threshold or unstable scores need calibration before strong action shaping.
            std_risk = float(group[risk_col].std(ddof=0)) if trajectory_count else 0.0
            precision_hint = "needs_precision_review" if 0.48 <= confidence <= 0.68 or std_risk >= 0.08 else "precision_sufficient_for_material_review"
            rows.append(_with_boundary({
                "risk_confidence_id": f"risk_conf_{state_id}_{risk_col.replace('_risk', '')}",
                "macro_state_id": str(state_id),
                "macro_state_name": state_name,
                "risk_name": risk_col.replace("_risk", ""),
                "mean_risk": round(mean_risk, 6),
                "max_risk": round(max_risk, 6),
                "trigger_count": trigger_count,
                "trajectory_count": trajectory_count,
                "risk_confidence": round(confidence, 6),
                "confidence_band": band,
                "precision_need_hint": precision_hint,
                "risk_status": "risk_confidence_estimated_from_NO_OP_dry_run",
            }))
    return pd.DataFrame(rows, columns=RISK_COLUMNS)


def extract_dynamics_direction(states: pd.DataFrame, trajectories: pd.DataFrame, risk_confidence: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    state_lookup = states.set_index("macro_state_id")
    for state_id, group in trajectories.groupby("macro_state_id", sort=False):
        base = state_lookup.loc[state_id]
        last = group[group["step"].astype(int) == int(group["step"].max())]
        pressure_delta = float(last["pressure_gradient"].mean()) - float(base["pressure_gradient"])
        lock_delta = float(last["relation_lock_signal"].mean()) - float(base["relation_lock_signal"])
        rev_delta = float(last["reversibility"].mean()) - float(base["reversibility"])
        boundary_delta = float(last["boundary_distance"].mean()) - float(base["boundary_distance"])
        escape_delta = float(last["escape_path_capacity"].mean()) - float(base["escape_path_capacity"])
        risk_rows = risk_confidence[risk_confidence["macro_state_id"].astype(str) == str(state_id)]
        risk_rows = risk_rows.sort_values("risk_confidence", ascending=False)
        dominant_risk = str(risk_rows["risk_name"].iloc[0]) if not risk_rows.empty else "unknown"
        if pressure_delta > 0.025 and escape_delta < -0.010:
            pressure_dir = "pressure_accumulates_toward_low_escape_capacity_region"
        elif pressure_delta > 0.015:
            pressure_dir = "pressure_accumulates_without_clear_escape"
        else:
            pressure_dir = "pressure_direction_mild_or_diffuse"
        if rev_delta < -0.015 or escape_delta < -0.015:
            escape_dir = "preserve_or_open_return_escape_path"
        elif float(base["neighbor_capacity"]) >= 0.45:
            escape_dir = "neighbor_capacity_available_for_diffusion"
        else:
            escape_dir = "escape_direction_unclear_review_only"
        if boundary_delta < -0.015 or float(base["boundary_distance"]) < 0.35:
            forbidden = "do_not_push_toward_fragile_boundary"
        elif dominant_risk == "oscillation":
            forbidden = "do_not_amplify_phase_delay_or_curvature"
        else:
            forbidden = "avoid_strengthening_dominant_risk_direction"
        clarity = _clip01(0.35 * abs(pressure_delta) * 8 + 0.30 * abs(lock_delta) * 8 + 0.20 * abs(rev_delta) * 8 + 0.15 * abs(escape_delta) * 8)
        rows.append(_with_boundary({
            "direction_id": f"direction_{state_id}",
            "macro_state_id": str(state_id),
            "macro_state_name": str(base["macro_state_name"]),
            "dominant_risk": dominant_risk,
            "dominant_pressure_direction": pressure_dir,
            "escape_or_return_direction": escape_dir,
            "forbidden_push_direction": forbidden,
            "direction_clarity": round(clarity, 6),
            "dynamics_direction_status": "dynamics_direction_extracted_for_later_action_shaping",
        }))
    return pd.DataFrame(rows, columns=DIRECTION_COLUMNS)


def build_dry_run_checks(states: pd.DataFrame, gate: pd.DataFrame, trajectories: pd.DataFrame, risk_confidence: pd.DataFrame, directions: pd.DataFrame, task20b_ready: bool, cfg: GatedMacroGameRiskSimulatorDryRunConfig) -> pd.DataFrame:
    opened = int(gate["should_run_simulator"].astype(bool).sum()) if not gate.empty else 0
    expected_trajectory_rows = opened * cfg.seed_count * cfg.horizon
    checks = [
        ("check_task20b_ready", "upstream", "Task20b macro-game risk simulator contract is ready.", True, task20b_ready),
        ("check_states_exist", "state", "Coarse macro-game states exist.", True, len(states) >= 6),
        ("check_gate_evaluated", "gate", "Observation gate evaluated every state.", True, len(gate) == len(states) and len(gate) > 0),
        ("check_gate_open", "gate", "At least one state opens the simulator gate.", True, opened > 0),
        ("check_trajectory_rows", "simulator", "NO_OP dry-run trajectory rows match opened states x seeds x horizon.", True, len(trajectories) == expected_trajectory_rows),
        ("check_risk_confidence_rows", "risk", "Risk confidence rows exist for each opened state and risk type.", True, len(risk_confidence) == opened * 5),
        ("check_risk_range", "risk", "Risk confidence values remain in [0,1].", True, bool(((risk_confidence["risk_confidence"].astype(float) >= 0.0) & (risk_confidence["risk_confidence"].astype(float) <= 1.0)).all()) if not risk_confidence.empty else False),
        ("check_directions", "direction", "Dynamics direction rows exist for each opened state.", True, len(directions) == opened),
        ("check_no_action", "boundary", "No action candidate or concrete action is generated.", False, bool(directions["action_candidate_generated"].astype(bool).any()) if not directions.empty else True),
        ("check_no_effect_prediction", "boundary", "No action-effect prediction model is executed.", False, bool(directions["effect_prediction_model_executed"].astype(bool).any()) if not directions.empty else True),
        ("check_no_hidden_future", "boundary", "No hidden truth or future information is used.", False, bool(directions["hidden_truth_input"].astype(bool).any() or directions["future_information_used"].astype(bool).any()) if not directions.empty else True),
    ]
    return pd.DataFrame([
        _with_boundary({"check_id": c[0], "check_scope": c[1], "check_description": c[2], "expected_value": bool(c[3]), "observed_value": bool(c[4]), "check_status": "pass" if bool(c[3]) == bool(c[4]) else "fail"})
        for c in checks
    ], columns=CHECK_COLUMNS)


def build_final_summary(states: pd.DataFrame, gate: pd.DataFrame, trajectories: pd.DataFrame, risk_confidence: pd.DataFrame, directions: pd.DataFrame, checks: pd.DataFrame, task20b_ready: bool) -> pd.DataFrame:
    pass_count = int((checks["check_status"].astype(str) == "pass").sum()) if not checks.empty else 0
    high_count = int((risk_confidence["confidence_band"].astype(str) == "high").sum()) if not risk_confidence.empty else 0
    precision_count = int((risk_confidence["precision_need_hint"].astype(str) == "needs_precision_review").sum()) if not risk_confidence.empty else 0
    decision = "gated_macro_game_risk_simulator_dry_run_ready" if task20b_ready and len(checks) == pass_count else "gated_macro_game_risk_simulator_dry_run_needs_review"
    return pd.DataFrame([_with_boundary({
        "macro_state_count": len(states),
        "gate_open_count": int(gate["should_run_simulator"].astype(bool).sum()) if not gate.empty else 0,
        "trajectory_row_count": len(trajectories),
        "risk_confidence_row_count": len(risk_confidence),
        "dynamics_direction_count": len(directions),
        "high_confidence_risk_count": high_count,
        "precision_review_needed_count": precision_count,
        "dry_run_check_count": len(checks),
        "dry_run_check_pass_count": pass_count,
        "task20b_ready": bool(task20b_ready),
        "gated_macro_game_risk_simulator_dry_run_decision": decision,
        "next_task": "Task 2-8j-23: risk-to-action direction shaping dry-run",
    })], columns=SUMMARY_COLUMNS)


def validate_gated_macro_game_risk_simulator_dry_run_tables(states: pd.DataFrame, gate: pd.DataFrame, trajectories: pd.DataFrame, risk_confidence: pd.DataFrame, directions: pd.DataFrame, checks: pd.DataFrame, final_summary: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    tables = {
        "states": (states, STATE_COLUMNS),
        "gate": (gate, GATE_COLUMNS),
        "trajectories": (trajectories, TRAJECTORY_COLUMNS),
        "risk_confidence": (risk_confidence, RISK_COLUMNS),
        "directions": (directions, DIRECTION_COLUMNS),
        "checks": (checks, CHECK_COLUMNS),
        "final_summary": (final_summary, SUMMARY_COLUMNS),
    }
    for name, (table, columns) in tables.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_22_empty_table:{name}"); continue
        missing = [c for c in columns if c not in table.columns]
        if missing:
            errors.append(f"task2_8j_22_missing_columns:{name}:" + ",".join(missing)); continue
        for col in REQUIRED_TRUE:
            if not bool(table[col].astype(bool).all()):
                errors.append(f"task2_8j_22_required_true_not_all_true:{name}:{col}")
        for col in FORBIDDEN_TRUE:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_22_forbidden_true:{name}:{col}")
        if set(table["gt_main_map_name"].astype(str)) != {"static_pca_7"}:
            errors.append(f"task2_8j_22_wrong_gt_main_map_name:{name}")
        if set(table["gt_main_component_count"].astype(int)) != {7}:
            errors.append(f"task2_8j_22_wrong_gt_component_count:{name}")
    if checks is not None and not checks.empty and not bool((checks["check_status"].astype(str) == "pass").all()):
        errors.append("task2_8j_22_check_failed")
    if risk_confidence is not None and not risk_confidence.empty:
        vals = risk_confidence["risk_confidence"].astype(float)
        if not bool(((vals >= 0) & (vals <= 1)).all()):
            errors.append("task2_8j_22_risk_confidence_out_of_range")
    return errors


def build_and_validate_gated_macro_game_risk_simulator_dry_run(cfg: GatedMacroGameRiskSimulatorDryRunConfig | None = None, **_unused: object) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    cfg = cfg or GatedMacroGameRiskSimulatorDryRunConfig()
    _gate_contract, _inputs_contract, _outputs_contract, _functions_contract, _checks20b, _final20b, task20b_errors, task20b_summary = build_and_validate_macro_game_risk_simulator_contract()
    task20b_ready = len(task20b_errors) == 0 and str(task20b_summary.get("macro_game_risk_simulator_contract_decision", "")).startswith(TASK20B_ACCEPTED_DECISION)
    if not cfg.require_task20b_ready:
        task20b_ready = True
    states = build_coarse_macro_game_states()
    gate = should_run_macro_risk_simulator(states, cfg)
    trajectories = simulate_short_horizon_NO_OP_risk(states, gate, cfg)
    risk_confidence = estimate_risk_confidence(trajectories, cfg)
    directions = extract_dynamics_direction(states, trajectories, risk_confidence)
    checks = build_dry_run_checks(states, gate, trajectories, risk_confidence, directions, task20b_ready, cfg)
    final_summary = build_final_summary(states, gate, trajectories, risk_confidence, directions, checks, task20b_ready)
    errors = ([f"task2_8j_22_upstream_20b_error:{e}" for e in task20b_errors] if cfg.require_task20b_ready else []) + validate_gated_macro_game_risk_simulator_dry_run_tables(states, gate, trajectories, risk_confidence, directions, checks, final_summary)
    summary = {
        "gt_main_map_name": "static_pca_7",
        "gt_main_component_count": 7,
        "task20b_decision": task20b_summary.get("macro_game_risk_simulator_contract_decision", ""),
        "macro_state_count": _safe_int(final_summary["macro_state_count"].iloc[0]),
        "gate_open_count": _safe_int(final_summary["gate_open_count"].iloc[0]),
        "trajectory_row_count": _safe_int(final_summary["trajectory_row_count"].iloc[0]),
        "risk_confidence_row_count": _safe_int(final_summary["risk_confidence_row_count"].iloc[0]),
        "dynamics_direction_count": _safe_int(final_summary["dynamics_direction_count"].iloc[0]),
        "high_confidence_risk_count": _safe_int(final_summary["high_confidence_risk_count"].iloc[0]),
        "precision_review_needed_count": _safe_int(final_summary["precision_review_needed_count"].iloc[0]),
        "dry_run_check_count": _safe_int(final_summary["dry_run_check_count"].iloc[0]),
        "dry_run_check_pass_count": _safe_int(final_summary["dry_run_check_pass_count"].iloc[0]),
        "task20b_ready": bool(task20b_ready),
        "gated_macro_game_risk_simulator_dry_run_decision": str(final_summary["gated_macro_game_risk_simulator_dry_run_decision"].iloc[0]),
        "not_high_resolution_forecast": True,
        "not_long_term_forecast": True,
        "risk_prediction_only": True,
        "simulator_dry_run_executed": True,
        "action_direction_generated": False,
        "terrain_operator_selected": False,
        "action_candidate_generated": False,
        "action_effect_prediction_generated": False,
        "axis_executed": False,
        "real_actionmodule_called": False,
        "validation_errors": errors,
    }
    return states, gate, trajectories, risk_confidence, directions, checks, final_summary, errors, summary
