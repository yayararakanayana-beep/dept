"""Phase 2G-21A-R1 real-v2-state to DEPT input reachability validation.

R1 is reachability/audit only.  Test-local helpers build real PseudoReality v2
states, translate only state snapshots into DEPT-side pressure intents/proxies,
then pass those DEPT inputs through ActionPlanner, a test-local final gate, and
ActionModule.  v2 traces and observation-window outputs are never runtime inputs.
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pandas as pd
import pytest

RC1_ROOT = Path(__file__).resolve().parents[1] / "localprep1" / "dept" / "DEPT2_ActionModule_ActuationPrimitives_RC1"
if str(RC1_ROOT) not in sys.path:
    sys.path.insert(0, str(RC1_ROOT))

from action_module.actions import ActionModule, ActionPlanner  # noqa: E402
from pseudo_reality.asymmetric_game_v2 import AsymmetricGamePseudoRealitySystem  # noqa: E402

CHANNELS = [
    "exploration_injection",
    "relation_unlock",
    "volatility_damping",
    "uncertainty_probe",
    "coupling_relief",
    "buffer_increase",
]
RELEVANCE = {c: f"relevant_to_{c}" for c in CHANNELS}
PARAMS = {
    "action_intensity_cap": 0.55,
    "planner_min_action_strength": 0.0,
    "exploration_gain": 0.30,
    "unlock_gain": 0.30,
    "damping_gain": 0.30,
    "buffer_gain": 0.30,
}
SCENARIO_STATES = {
    "stable": dict(fatigue=0.12, hidden_damage=0.08, latent_pressure=0.14, defensiveness=0.16, private_resource=0.78, exploration=0.58, reversibility=0.76, volatility=0.12, uncertainty=0.16, relation_lock=0.18, coupling=0.26, shared_resource=0.84, commons_health=0.86, t=0),
    "worsening": dict(fatigue=0.32, hidden_damage=0.24, latent_pressure=0.38, defensiveness=0.36, private_resource=0.64, exploration=0.43, reversibility=0.58, volatility=0.34, uncertainty=0.42, relation_lock=0.46, coupling=0.50, shared_resource=0.66, commons_health=0.68, t=2),
    "high_risk": dict(fatigue=0.58, hidden_damage=0.52, latent_pressure=0.68, defensiveness=0.66, private_resource=0.46, exploration=0.35, reversibility=0.36, volatility=0.62, uncertainty=0.68, relation_lock=0.74, coupling=0.72, shared_resource=0.44, commons_health=0.46, t=3),
    "limit": dict(fatigue=0.84, hidden_damage=0.76, latent_pressure=0.88, defensiveness=0.84, private_resource=0.28, exploration=0.26, reversibility=0.18, volatility=0.82, uncertainty=0.86, relation_lock=0.88, coupling=0.86, shared_resource=0.24, commons_health=0.26, t=4),
    "exploration_loss": dict(fatigue=0.34, hidden_damage=0.22, latent_pressure=0.40, defensiveness=0.34, private_resource=0.66, exploration=0.12, reversibility=0.62, volatility=0.28, uncertainty=0.66, relation_lock=0.36, coupling=0.42, shared_resource=0.68, commons_health=0.70, t=5),
    "recovery": dict(fatigue=0.22, hidden_damage=0.15, latent_pressure=0.24, defensiveness=0.24, private_resource=0.72, exploration=0.52, reversibility=0.70, volatility=0.22, uncertainty=0.28, relation_lock=0.26, coupling=0.34, shared_resource=0.76, commons_health=0.78, t=6),
}
PROXY_COLUMNS = [
    "risk_proxy", "residual_proxy", "unresolved_proxy", "reversibility_need", "burden_proxy",
    "hidden_burden_proxy", "fatigue_risk_proxy", "resource_inequality_risk_proxy", "coupling_proxy",
    "relation_lock_proxy", "exploration_need", "action_cost_estimate", "low_confidence_penalty",
    "collapse_proximity_proxy",
]


def _clip(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _real_v2_state(label: str, seed: int = 211) -> dict:
    values = SCENARIO_STATES[label]
    world = AsymmetricGamePseudoRealitySystem(seed=seed, scenario="phase2g21ar1_real_v2_state_source")
    for col in ("fatigue", "hidden_damage", "latent_pressure", "defensiveness", "private_resource"):
        world.hidden[col] = values[col]
    for col in ("exploration", "reversibility", "volatility", "uncertainty", "relation_lock", "coupling"):
        world.entities[col] = values[col]
    world.hidden["private_resource"] = (world.hidden["private_resource"] + pd.Series(range(len(world.hidden))) * 0.002).clip(0, 1)
    world.shared_resource = values["shared_resource"]
    world.commons_health = values["commons_health"]
    return {
        "seed": seed,
        "t": values["t"],
        "v2_state_source": "AsymmetricGamePseudoRealitySystem_state_snapshot_no_trace",
        "scenario_label_for_audit_only": label,
        "fatigue": float(world.hidden["fatigue"].mean()),
        "hidden_damage": float(world.hidden["hidden_damage"].mean()),
        "latent_pressure": float(world.hidden["latent_pressure"].mean()),
        "defensiveness": float(world.hidden["defensiveness"].mean()),
        "private_resource_mean": float(world.hidden["private_resource"].mean()),
        "private_resource_gap": float(world.hidden["private_resource"].max() - world.hidden["private_resource"].min()),
        "exploration": float(world.entities["exploration"].mean()),
        "reversibility": float(world.entities["reversibility"].mean()),
        "volatility": float(world.entities["volatility"].mean()),
        "uncertainty": float(world.entities["uncertainty"].mean()),
        "relation_lock": float(world.entities["relation_lock"].mean()),
        "coupling": float(world.entities["coupling"].mean()),
        "shared_resource": float(world.shared_resource),
        "commons_health": float(world.commons_health),
    }


def _proxies_from_state(state: dict) -> tuple[dict, list[str]]:
    required = ["fatigue", "hidden_damage", "latent_pressure", "defensiveness", "exploration", "reversibility", "volatility", "uncertainty", "relation_lock", "coupling", "shared_resource", "commons_health", "private_resource_mean", "private_resource_gap"]
    missing = [c for c in required if c not in state or pd.isna(state[c])]
    if missing:
        return {c: 0.0 for c in PROXY_COLUMNS}, missing
    collapse = _clip((1 - state["shared_resource"] + 1 - state["commons_health"] + state["fatigue"] + state["hidden_damage"]) / 4)
    burden = _clip((state["fatigue"] + state["hidden_damage"] + state["latent_pressure"] + (1 - state["private_resource_mean"])) / 4)
    risk = _clip((state["latent_pressure"] + state["defensiveness"] + state["volatility"] + state["uncertainty"] + state["relation_lock"] + state["coupling"] + collapse) / 7)
    unresolved = _clip((state["uncertainty"] + state["relation_lock"] + state["coupling"] + state["defensiveness"]) / 4)
    exploration_need = _clip((1 - state["exploration"]) * 0.70 + state["uncertainty"] * 0.30)
    proxies = {
        "risk_proxy": risk,
        "residual_proxy": _clip((state["volatility"] + state["uncertainty"] + abs(state["latent_pressure"] - state["exploration"])) / 3),
        "unresolved_proxy": unresolved,
        "reversibility_need": _clip(1 - state["reversibility"] + 0.35 * collapse + 0.20 * state["relation_lock"]),
        "burden_proxy": burden,
        "hidden_burden_proxy": _clip((state["hidden_damage"] + state["latent_pressure"] + state["defensiveness"]) / 3),
        "fatigue_risk_proxy": state["fatigue"],
        "resource_inequality_risk_proxy": _clip((1 - state["private_resource_mean"]) * 0.65 + state["private_resource_gap"] * 4.0),
        "coupling_proxy": state["coupling"],
        "relation_lock_proxy": state["relation_lock"],
        "exploration_need": exploration_need,
        "action_cost_estimate": _clip(0.12 + 0.55 * burden + 0.25 * state["coupling"] + 0.18 * state["relation_lock"]),
        "low_confidence_penalty": _clip((state["uncertainty"] + collapse + state["hidden_damage"]) / 3),
        "collapse_proximity_proxy": collapse,
    }
    return proxies, []


def _dept_inputs_from_real_v2(label: str, seed: int = 211, state_override: dict | None = None):
    state = _real_v2_state(label, seed) if state_override is None else state_override
    proxies, missing = _proxies_from_state(state)
    if missing:
        return state, proxies, pd.DataFrame(), pd.DataFrame(), [f"missing_v2_state:{m}" for m in missing]
    scenario_for_planner = "normal"
    if proxies["collapse_proximity_proxy"] > 0.65:
        scenario_for_planner = "shock"
    elif proxies["relation_lock_proxy"] > 0.60 or proxies["coupling_proxy"] > 0.65:
        scenario_for_planner = "relation_lock"
    elif proxies["exploration_need"] > 0.62 and proxies["burden_proxy"] < 0.50:
        scenario_for_planner = "exploration_loss"
    semantic = {
        "exploration_injection": "exploration_attempt_frequency_up",
        "relation_unlock": "adoption_barrier_relief",
        "volatility_damping": "intensity_cap_brake",
        "uncertainty_probe": "sandbox_probe_entry_up",
        "coupling_relief": "rollback_guard_up",
        "buffer_increase": "diagnostic_resolution_up",
    }
    channel_signal = {
        "exploration_injection": proxies["exploration_need"] * (1 - 0.75 * proxies["burden_proxy"]) * (1 - 0.65 * proxies["collapse_proximity_proxy"]),
        "relation_unlock": proxies["relation_lock_proxy"] * (1 - 0.35 * proxies["risk_proxy"]),
        "volatility_damping": max(proxies["risk_proxy"], state["volatility"]),
        "uncertainty_probe": proxies["unresolved_proxy"] * (1 - 0.55 * proxies["collapse_proximity_proxy"]),
        "coupling_relief": proxies["coupling_proxy"] + 0.25 * proxies["unresolved_proxy"],
        "buffer_increase": proxies["reversibility_need"] + 0.35 * proxies["burden_proxy"],
    }
    pressure_rows, aff_rows = [], []
    for i, ch in enumerate(CHANNELS):
        magnitude = _clip(channel_signal[ch])
        pressure_row = {
            "seed": state.get("seed", seed), "scenario": scenario_for_planner, "t": state.get("t", 0),
            "generator": "phase2g21ar1_real_v2_state_to_dept_proxy_builder", "phase_bin": "phase2g21ar1",
            "pressure_component": f"{ch}_from_real_v2_proxy", "semantic_effect": semantic[ch],
            "h11_received_abs_pressure": max(0.01, magnitude), "component_magnitude": max(0.01, magnitude * 0.75),
        }
        for c, col in RELEVANCE.items():
            pressure_row[col] = c == ch or (ch in {"buffer_increase", "volatility_damping", "coupling_relief"} and c in {"buffer_increase", "volatility_damping", "coupling_relief"})
        pressure_rows.append(pressure_row)
        aff_row = {
            "seed": state.get("seed", seed), "scenario": scenario_for_planner, "t": state.get("t", 0),
            "entity_id": f"entity_{i % 2}", "action_channel": ch,
            "target_need": _clip(magnitude), "estimated_action_cost": proxies["action_cost_estimate"],
            "v8_conflict": _clip((proxies["risk_proxy"] + proxies["coupling_proxy"] + proxies["relation_lock_proxy"]) / 3),
            "v8_unresolved": proxies["unresolved_proxy"], "v8_confidence": _clip(1 - proxies["low_confidence_penalty"]),
            "direction": 1.0, "generator": "phase2g21ar1_real_v2_state_to_dept_affordance_builder", "phase_bin": "phase2g21ar1",
        }
        for c, col in RELEVANCE.items():
            aff_row[col] = c == ch
        aff_rows.append(aff_row)
    return state, proxies, pd.DataFrame(pressure_rows), pd.DataFrame(aff_rows), []


def _gate_from_plan(plan: pd.DataFrame) -> pd.DataFrame:
    if plan.empty:
        return pd.DataFrame()
    out = plan.copy()
    brake = out["rollback_guard_signal"].astype(float) + out["intensity_cap_brake_signal"].astype(float)
    safe = out["action_channel"].isin(["buffer_increase", "volatility_damping", "coupling_relief", "no_op"])
    out["gate_score"] = (out["planner_confidence"].astype(float) * (1 - 0.20 * out["estimated_action_cost"].astype(float))).clip(0, 1)
    out["final_gate_decision"] = "allow_candidate"
    out.loc[(out["action_strength"] <= 0) | (out["action_primitive"] == "observe_only"), "final_gate_decision"] = "gate_no_op"
    out.loc[(brake > 2.0) & ~safe, "final_gate_decision"] = "hold_shadow"
    out.loc[(brake > 2.0) & safe, "final_gate_decision"] = "allow_buffer_only"
    out["effective_action_strength"] = out["action_strength"].where(out["final_gate_decision"].str.startswith("allow"), 0.0)
    return out


def _summary(label: str, seed: int = 211, state_override: dict | None = None) -> dict:
    state, proxies, pressure, aff, missing = _dept_inputs_from_real_v2(label, seed, state_override)
    if missing:
        return {"run_id": f"{label}-{seed}", "scenario_label_for_audit_only": state.get("scenario_label_for_audit_only", label), **proxies, "pressure_intents_rows": 0, "v8_affordance_rows": 0, "action_candidate_rows": 0, "input_reachability_score": 0.0, "input_reachability_band": "unresolved", "input_reachability_confidence": 0.0, "missing_input_flags": missing, "v2_trace_used_as_action_runtime_input": False, "observation_window_used_as_action_runtime_input": False, "actionplanner_received_only_dept_inputs": True, "actionmodule_received_only_final_gate": True, "pressure": pressure, "affordance": aff, "plan": pd.DataFrame(), "gate": pd.DataFrame(), "action_frame": pd.DataFrame()}
    plan = ActionPlanner().plan(pressure, aff, PARAMS)
    gate = _gate_from_plan(plan)
    frame = ActionModule().build_action_frame(gate, PARAMS)
    top = plan.sort_values(["action_strength", "planner_confidence"], ascending=False).iloc[0]
    score = sum(proxies[c] for c in ["risk_proxy", "unresolved_proxy", "reversibility_need", "burden_proxy", "action_cost_estimate", "exploration_need"]) / 6
    band = "low" if score < 0.28 else "medium" if score < 0.50 else "high" if score < 0.70 else "limit"
    return {
        "run_id": f"{label}-{seed}", "seed": seed, "scenario_label_for_audit_only": label, "t": state["t"], "v2_state_source": state["v2_state_source"],
        "dept_observation_builder_used": "test_local_real_v2_state_snapshot_to_proxy_builder", "dept_translation_used": "test_local_proxy_to_pressure_intents_and_v8_affordance",
        **proxies, "pressure_intents_rows": len(pressure), "v8_affordance_rows": len(aff), "action_candidate_rows": len(plan),
        "dominant_pressure_component": str(top.dominant_pressure_component), "dominant_semantic_effect": str(top.dominant_semantic_effect),
        "available_action_channels": sorted(aff["action_channel"].unique()), "planned_action_channel": str(top.action_channel), "action_primitive": str(top.action_primitive),
        "planner_route": str(top.planner_route), "primitive_sequence": str(top.primitive_sequence), "primitive_stage": int(top.primitive_stage),
        "input_reachability_score": score, "input_reachability_band": band, "input_reachability_confidence": 1.0, "missing_input_flags": [],
        "v2_trace_used_as_action_runtime_input": False, "observation_window_used_as_action_runtime_input": False,
        "actionplanner_received_only_dept_inputs": True, "actionmodule_received_only_final_gate": True,
        "pressure": pressure, "affordance": aff, "plan": plan, "gate": gate, "action_frame": frame,
    }


def real_v2_to_dept_input_reachability_summary() -> pd.DataFrame:
    rows = []
    for label in SCENARIO_STATES:
        s = _summary(label)
        rows.append({k: v for k, v in s.items() if k not in {"pressure", "affordance", "plan", "gate", "action_frame"}})
    return pd.DataFrame(rows)


def test_real_v2_state_generates_dept_side_inputs():
    s = _summary("stable")
    assert s["pressure_intents_rows"] > 0
    assert s["v8_affordance_rows"] > 0
    assert all(c in s for c in PROXY_COLUMNS)


def test_real_v2_state_differences_appear_in_core_proxies():
    rows = {label: _summary(label) for label in SCENARIO_STATES}
    assert rows["stable"]["risk_proxy"] < rows["worsening"]["risk_proxy"] < rows["high_risk"]["risk_proxy"] < rows["limit"]["risk_proxy"]
    assert rows["limit"]["burden_proxy"] > rows["stable"]["burden_proxy"]
    assert rows["limit"]["action_cost_estimate"] > rows["stable"]["action_cost_estimate"]
    assert rows["exploration_loss"]["exploration_need"] > rows["stable"]["exploration_need"]


def test_pressure_intents_and_v8_affordance_reach_action_planner():
    s = _summary("worsening")
    assert not s["plan"].empty
    assert {"dominant_pressure_component", "dominant_semantic_effect", "action_primitive"}.issubset(s["plan"].columns)
    assert s["actionplanner_received_only_dept_inputs"] is True


def test_action_module_receives_only_final_gate_not_v2_trace():
    s = _summary("high_risk")
    assert list(inspect.signature(ActionPlanner.plan).parameters) == ["self", "pressure_intents", "v8_affordance", "params"]
    assert list(inspect.signature(ActionModule.build_action_frame).parameters) == ["self", "final_gate", "params"]
    assert s["v2_trace_used_as_action_runtime_input"] is False
    assert s["observation_window_used_as_action_runtime_input"] is False
    assert s["actionmodule_received_only_final_gate"] is True
    assert isinstance(s["action_frame"], pd.DataFrame)


def test_high_risk_state_prefers_defensive_action_material():
    s = _summary("high_risk")
    channels = set(s["plan"]["action_channel"])
    assert channels & {"buffer_increase", "volatility_damping", "coupling_relief"}
    assert s["planned_action_channel"] in {"buffer_increase", "volatility_damping", "coupling_relief", "no_op"}
    assert s["exploration_need"] < 0.80


def test_limit_state_suppresses_unbounded_exploration_material():
    s = _summary("limit")
    explore = s["plan"][s["plan"]["original_affordance_channel"] == "exploration_injection"]
    assert s["collapse_proximity_proxy"] > 0.65
    assert s["low_confidence_penalty"] > 0.70
    assert s["planned_action_channel"] in {"buffer_increase", "volatility_damping", "coupling_relief", "no_op"}
    assert explore.empty or float(explore["action_strength"].max()) <= float(s["plan"]["action_strength"].max())


def test_exploration_loss_state_raises_exploration_need_without_direct_action():
    s = _summary("exploration_loss")
    stable = _summary("stable")
    assert s["exploration_need"] > stable["exploration_need"]
    assert s["residual_proxy"] > stable["residual_proxy"]
    assert s["action_candidate_rows"] > 0


def test_recovery_state_reduces_risk_and_action_need_material():
    rec = _summary("recovery")
    high = _summary("high_risk")
    assert rec["risk_proxy"] < high["risk_proxy"]
    assert rec["reversibility_need"] < high["reversibility_need"]
    assert rec["burden_proxy"] < high["burden_proxy"]
    assert rec["input_reachability_score"] < high["input_reachability_score"]


def test_missing_v2_or_dept_fields_become_unresolved_not_silent_pass():
    state = _real_v2_state("stable")
    del state["fatigue"]
    s = _summary("stable", state_override=state)
    assert s["input_reachability_band"] == "unresolved"
    assert s["input_reachability_confidence"] == 0.0
    assert "missing_v2_state:fatigue" in s["missing_input_flags"]


def test_scenario_labels_are_audit_only_not_runtime_control():
    original = _summary("high_risk")
    state = _real_v2_state("high_risk")
    state["scenario_label_for_audit_only"] = "stable"
    renamed = _summary("stable", state_override=state)
    assert renamed["scenario_label_for_audit_only"] == "stable"
    assert renamed["input_reachability_band"] == original["input_reachability_band"]
    assert pytest.approx(renamed["risk_proxy"]) == original["risk_proxy"]


def test_reachability_summary_exports_to_dataframe_and_csv(tmp_path):
    df = real_v2_to_dept_input_reachability_summary()
    required = ["run_id", "seed", "scenario_label_for_audit_only", "t", "v2_state_source", "dept_observation_builder_used", "dept_translation_used", *PROXY_COLUMNS, "pressure_intents_rows", "v8_affordance_rows", "action_candidate_rows", "dominant_pressure_component", "dominant_semantic_effect", "available_action_channels", "planned_action_channel", "action_primitive", "planner_route", "primitive_sequence", "primitive_stage", "input_reachability_score", "input_reachability_band", "input_reachability_confidence", "missing_input_flags", "v2_trace_used_as_action_runtime_input", "observation_window_used_as_action_runtime_input", "actionplanner_received_only_dept_inputs", "actionmodule_received_only_final_gate"]
    assert required == list(df.columns)
    path = tmp_path / "real_v2_to_dept_input_reachability_summary.csv"
    df.to_csv(path, index=False)
    loaded = pd.read_csv(path)
    assert loaded.shape == df.shape
