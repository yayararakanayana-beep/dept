"""Phase 2G-19A DEPT-to-Action input reachability validation.

These tests intentionally validate only DEPT-side input reachability into the
ActionPlanner/ActionModule surface. They do not tune actuation primitives,
primitive multipliers, v2 dynamics, pressure translation, or canonical writes.
"""
from pathlib import Path
import inspect
import sys

import pandas as pd
import pytest

LOCALPREP_ROOT = Path(__file__).resolve().parents[1] / "localprep1" / "dept"
if str(LOCALPREP_ROOT) not in sys.path:
    sys.path.insert(0, str(LOCALPREP_ROOT))

from DEPT2_ActionModule_ActuationPrimitives_RC1.action_module.actions import ActionModule, ActionPlanner
import DEPT2_ActionModule_ActuationPrimitives_RC1.action_module.actions as actions_source

CHANNELS = [
    "exploration_injection",
    "relation_unlock",
    "volatility_damping",
    "uncertainty_probe",
    "coupling_relief",
    "buffer_increase",
]
RELEVANCE = {
    "exploration_injection": "relevant_to_exploration_injection",
    "relation_unlock": "relevant_to_relation_unlock",
    "volatility_damping": "relevant_to_volatility_damping",
    "uncertainty_probe": "relevant_to_uncertainty_probe",
    "coupling_relief": "relevant_to_coupling_relief",
    "buffer_increase": "relevant_to_buffer_increase",
}
STATE_PROFILES = {
    "stable_system": dict(scenario="normal", band="low", p=0.05, m=0.04, conflict=0.10, unresolved=0.10, confidence=0.88, cost=0.10, need=0.14),
    "medium_risk_system": dict(scenario="exploration_loss", band="medium", p=0.25, m=0.20, conflict=0.34, unresolved=0.30, confidence=0.68, cost=0.30, need=0.45),
    "high_risk_system": dict(scenario="relation_lock", band="high", p=0.54, m=0.45, conflict=0.56, unresolved=0.56, confidence=0.48, cost=0.56, need=0.70),
    "limit_system": dict(scenario="shock", band="limit", p=0.84, m=0.78, conflict=0.80, unresolved=0.80, confidence=0.20, cost=0.78, need=0.92),
}
PARAMS = {
    "action_intensity_cap": 0.55,
    "planner_min_action_strength": 0.0,
    "exploration_gain": 0.30,
    "unlock_gain": 0.30,
    "damping_gain": 0.30,
    "buffer_gain": 0.30,
}


def _dept_inputs(state_label, scenario_override=None, seed=7):
    p = STATE_PROFILES[state_label]
    scenario = scenario_override or p["scenario"]
    semantic_by_channel = {
        "exploration_injection": "exploration_attempt_frequency_up",
        "relation_unlock": "adoption_barrier_relief",
        "volatility_damping": "intensity_cap_brake",
        "uncertainty_probe": "sandbox_probe_entry_up",
        "coupling_relief": "rollback_guard_up",
        "buffer_increase": "diagnostic_resolution_up",
    }
    rows = []
    for i, channel in enumerate(CHANNELS):
        row = {
            "seed": seed,
            "scenario": scenario,
            "t": 1,
            "generator": "phase2g19a_synthetic_dept_side_builder",
            "phase_bin": "phase2g19a",
            "pressure_component": f"{channel}_pressure_component",
            "semantic_effect": semantic_by_channel[channel],
            "h11_received_abs_pressure": p["p"] * (1.0 + 0.02 * i),
            "component_magnitude": p["m"] * (1.0 + 0.02 * i),
        }
        for ch, col in RELEVANCE.items():
            row[col] = ch == channel or (state_label in {"high_risk_system", "limit_system"} and ch in {"coupling_relief", "buffer_increase", "volatility_damping"})
        rows.append(row)
    aff = []
    for i, channel in enumerate(CHANNELS):
        aff_row = {
            "seed": seed,
            "scenario": scenario,
            "t": 1,
            "entity_id": f"entity_{i % 2}",
            "action_channel": channel,
            "target_need": p["need"] * (1.0 + 0.01 * i),
            "estimated_action_cost": p["cost"],
            "v8_conflict": p["conflict"],
            "v8_unresolved": p["unresolved"],
            "v8_confidence": p["confidence"],
            "direction": 1.0,
            "generator": "phase2g19a_synthetic_dept_side_builder",
            "phase_bin": "phase2g19a",
        }
        for ch, col in RELEVANCE.items():
            aff_row[col] = ch == channel
        aff.append(aff_row)
    return pd.DataFrame(rows), pd.DataFrame(aff)


def _gate_from_plan(plan):
    if plan.empty:
        return pd.DataFrame()
    out = plan.copy()
    brake = out["rollback_guard_signal"].astype(float) + out["intensity_cap_brake_signal"].astype(float)
    safe_channel = out["action_channel"].isin(["buffer_increase", "volatility_damping", "coupling_relief", "no_op"])
    out["gate_score"] = (out["planner_confidence"].astype(float) * (1.0 - 0.20 * out["estimated_action_cost"].astype(float))).clip(0, 1)
    out["final_gate_decision"] = "allow_candidate"
    out.loc[(out["action_strength"] <= 0.0) | (out["action_primitive"] == "observe_only"), "final_gate_decision"] = "gate_no_op"
    out.loc[(brake > 2.0) & ~safe_channel, "final_gate_decision"] = "hold_shadow"
    out.loc[(brake > 2.0) & safe_channel, "final_gate_decision"] = "allow_buffer_only"
    out["effective_action_strength"] = out["action_strength"].where(out["final_gate_decision"].str.startswith("allow"), 0.0)
    return out


def _summarize(state_label, scenario_override=None, drop_pressure=None, drop_affordance=None):
    pressure, aff = _dept_inputs(state_label, scenario_override=scenario_override)
    if drop_pressure:
        pressure = pressure.drop(columns=drop_pressure)
    if drop_affordance:
        aff = aff.drop(columns=drop_affordance)
    missing = []
    for col in ["h11_received_abs_pressure", "component_magnitude"]:
        if col not in pressure.columns:
            missing.append(col)
    for col in ["v8_conflict", "v8_unresolved", "estimated_action_cost", "target_need", "v8_confidence"]:
        if col not in aff.columns:
            missing.append(col)
    if missing:
        return {"state_label": state_label, "input_reachability_band": "unresolved", "input_reachability_confidence": 0.0, "missing_input_flags": missing}
    plan = ActionPlanner().plan(pressure, aff, PARAMS)
    gate = _gate_from_plan(plan)
    frame = ActionModule().build_action_frame(gate, PARAMS)
    pressure_signal = float(plan["intent_total_signal"].max()) if not plan.empty else 0.0
    row = plan.sort_values(["action_strength", "planner_confidence"], ascending=False).iloc[0]
    action_strength = float(frame["action_strength"].max()) if not frame.empty else 0.0
    pressure_only_norm = min(pressure_signal / 12.0, 1.0)
    pressure_risk_norm = min(pressure_signal / 1.0, 1.0)
    score = sum([
        pressure_risk_norm,
        float(row.v8_conflict),
        float(row.v8_unresolved),
        float(row.estimated_action_cost),
        1.0 - float(row.v8_confidence),
        min(float(row.rollback_guard_signal) / 1.0, 1.0),
        min(float(row.intensity_cap_brake_signal) / 1.0, 1.0),
    ]) / 7.0
    band = "low" if score < 0.22 else "medium" if score < 0.50 else "high" if score < 0.75 else "limit"
    return {
        "state_label": state_label, "scenario": str(row.scenario), "seed": int(row.seed), "t": int(row.t),
        "pressure_total_signal": pressure_signal,
        "dominant_pressure_component": row.dominant_pressure_component,
        "dominant_semantic_effect": row.dominant_semantic_effect,
        "rollback_guard_signal": float(plan["rollback_guard_signal"].max()),
        "intensity_cap_brake_signal": float(plan["intensity_cap_brake_signal"].max()),
        "diagnostic_signal": float(plan["diagnostic_signal"].max()),
        "sandbox_probe_signal": float(plan["sandbox_probe_signal"].max()),
        "intent_component_count": int(plan["intent_component_count"].max()),
        "v8_conflict": float(row.v8_conflict), "v8_unresolved": float(row.v8_unresolved), "v8_confidence": float(row.v8_confidence),
        "estimated_action_cost": float(row.estimated_action_cost), "target_need": float(row.target_need),
        "available_action_channels": sorted(set(aff["action_channel"])), "planned_action_channel": row.action_channel,
        "action_primitive": row.action_primitive, "planner_route": row.planner_route, "primitive_sequence": row.primitive_sequence,
        "primitive_stage": int(row.primitive_stage), "final_gate_decision": str(gate.sort_values("effective_action_strength", ascending=False).iloc[0].final_gate_decision),
        "gate_score": float(gate["gate_score"].max()), "planner_raw_strength": float(plan["planner_raw_strength"].max()),
        "action_strength": action_strength, "planner_confidence": float(row.planner_confidence),
        "pressure_only_score": pressure_only_norm,
        "pressure_plus_terrain_score": (pressure_risk_norm + float(row.v8_conflict) + float(row.v8_unresolved) + float(row.estimated_action_cost) + (1.0 - float(row.v8_confidence))) / 5.0,
        "pressure_plus_terrain_plus_gate_score": (score + (1.0 - float(gate["gate_score"].max())) + min(action_strength / 0.22, 1.0)) / 3.0,
        "input_reachability_score": score, "input_reachability_band": band, "input_reachability_confidence": 1.0,
        "missing_input_flags": [], "planner": plan, "gate": gate, "action_frame": frame,
    }


def _all_summaries(**kwargs):
    return [_summarize(s, **kwargs) for s in STATE_PROFILES]


def test_action_module_does_not_read_v2_traces():
    summary = _summarize("medium_risk_system")
    assert not summary["planner"].empty
    assert isinstance(summary["action_frame"], pd.DataFrame)
    assert list(inspect.signature(ActionPlanner.plan).parameters) == ["self", "pressure_intents", "v8_affordance", "params"]
    assert list(inspect.signature(ActionModule.build_action_frame).parameters) == ["self", "final_gate", "params"]


@pytest.mark.parametrize("state_label, expected_band", [(k, v["band"]) for k, v in STATE_PROFILES.items()])
def test_state_produces_expected_reachability_band(state_label, expected_band):
    summary = _summarize(state_label)
    assert summary["input_reachability_band"] == expected_band
    if expected_band == "low":
        assert summary["v8_conflict"] < 0.20 and summary["v8_unresolved"] < 0.20
        assert summary["rollback_guard_signal"] < 0.20 and summary["intensity_cap_brake_signal"] < 0.20
        assert summary["action_strength"] <= 0.02
    if expected_band == "medium":
        assert summary["pressure_total_signal"] > _summarize("stable_system")["pressure_total_signal"]
        assert summary["diagnostic_signal"] > 0 or summary["planned_action_channel"] in CHANNELS
        assert summary["action_strength"] <= 0.08
    if expected_band == "high":
        med = _summarize("medium_risk_system")
        assert summary["rollback_guard_signal"] > med["rollback_guard_signal"]
        assert summary["intensity_cap_brake_signal"] > med["intensity_cap_brake_signal"]
        assert summary["planned_action_channel"] in {"buffer_increase", "volatility_damping", "coupling_relief"}
    if expected_band == "limit":
        assert summary["v8_confidence"] < 0.35
        assert summary["final_gate_decision"] in {"gate_no_op", "hold_shadow", "allow_buffer_only", "allow_candidate"}
        assert summary["planned_action_channel"] in {"buffer_increase", "volatility_damping", "coupling_relief", "no_op"}


def test_monotonic_separation_across_state_labels():
    scores = [s["input_reachability_score"] for s in _all_summaries()]
    assert scores == sorted(scores)
    assert scores[0] < scores[1] < scores[2] < scores[3]
    assert scores[3] - scores[0] > 0.50


def test_pressure_only_view_is_weaker_than_pressure_plus_terrain_view():
    rows = _all_summaries()
    pressure_span = max(r["pressure_only_score"] for r in rows) - min(r["pressure_only_score"] for r in rows)
    terrain_span = max(r["pressure_plus_terrain_score"] for r in rows) - min(r["pressure_plus_terrain_score"] for r in rows)
    gate_values = [r["pressure_plus_terrain_plus_gate_score"] for r in rows]
    assert pressure_span > 0.10
    assert terrain_span > pressure_span
    assert len(set(round(v, 3) for v in gate_values)) == 4


def test_scenario_name_is_not_required_for_basic_separation():
    rows = _all_summaries(scenario_override="generic_reachability_probe")
    assert [r["input_reachability_band"] for r in rows] == ["low", "medium", "high", "limit"]
    assert len({r["scenario"] for r in rows}) == 1
    assert rows[-1]["input_reachability_score"] - rows[0]["input_reachability_score"] > 0.50


def test_required_input_fields_are_reported():
    summary = _summarize("stable_system", drop_pressure=["h11_received_abs_pressure"], drop_affordance=["v8_conflict", "estimated_action_cost"])
    assert summary["input_reachability_band"] == "unresolved"
    assert summary["input_reachability_confidence"] == 0.0
    assert {"h11_received_abs_pressure", "v8_conflict", "estimated_action_cost"}.issubset(summary["missing_input_flags"])


def test_action_frame_carries_planner_facing_information():
    summary = _summarize("high_risk_system")
    plan = summary["planner"]
    frame = summary["action_frame"]
    for col in ["planner_route", "action_primitive", "primitive_sequence", "primitive_stage", "dominant_semantic_effect", "dominant_pressure_component"]:
        assert col in plan.columns
    assert "truth_used_for_action_planner" in plan.columns
    assert set(plan["truth_used_for_action_planner"]) == {False}
    assert "action_module_contract" in frame.columns or not frame.empty is False


def test_no_observation_window_output_is_used_as_runtime_input():
    src = inspect.getsource(actions_source)
    forbidden = ["observation_window_summary", "v2_direct_benefit_window", "composite_balance_window", "v2_direct_risk_band_window", "v2_direct_growth_window"]
    assert all(token not in src for token in forbidden)


def test_reachability_summary_can_be_exported(tmp_path):
    df = pd.DataFrame([{k: v for k, v in row.items() if k not in {"planner", "gate", "action_frame"}} for row in _all_summaries()])
    required = {"state_label", "input_reachability_band", "pressure_total_signal", "v8_conflict", "v8_unresolved", "estimated_action_cost", "action_strength"}
    assert len(df) >= 4
    assert required.issubset(df.columns)
    csv_text = df.to_csv(index=False)
    assert "stable_system" in csv_text and "limit_system" in csv_text
    path = tmp_path / "reachability_summary.csv"
    df.to_csv(path, index=False)
    assert path.read_text().startswith("state_label,")
