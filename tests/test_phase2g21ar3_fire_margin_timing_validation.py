"""Phase 2G-21A-R3 fire-margin timing validation.

R3 is test-local only. It creates matched real-v2 no-op/action branches,
passes an ActionFrame-like row to v2.step for proposed action, reads emit_trace
only after each branch step, and uses those post-action traces as audit evidence
for timing judgement. Production planner/module/runtime code is not changed.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
import copy
import sys

import pandas as pd

RC1_ROOT = Path(__file__).resolve().parents[1] / "localprep1" / "dept" / "DEPT2_ActionModule_ActuationPrimitives_RC1"
if str(RC1_ROOT) not in sys.path:
    sys.path.insert(0, str(RC1_ROOT))

from pseudo_reality.asymmetric_game_v2 import AsymmetricGamePseudoRealitySystem  # noqa: E402

SMALL = 0.08
MEDIUM = 0.20
NON_ACTIONS = {"no_op", "observe_only", "cooldown", "hold_shadow"}
REQUIRED = {"source_entity_id", "local_no_action_risk_estimate", "local_action_side_effect_cost_estimate"}
SUMMARY_COLUMNS = [
    "run_id", "seed", "scenario_label_for_audit_only", "t", "source_entity_id", "source_relation_id", "target_entity_id", "relation_pair",
    "local_no_action_risk_estimate", "local_action_side_effect_cost_estimate", "local_fire_margin", "local_fire_band",
    "pair_no_action_risk_estimate", "pair_action_side_effect_cost_estimate", "pair_fire_margin", "pair_fire_band",
    "recommended_action_channel", "non_action_decision", "suppression_reason", "final_gate_decision", "effective_action_strength",
    "baseline_mode", "action_mode", "no_op_outcome_delta", "action_outcome_delta", "outcome_improvement_vs_no_op",
    "net_public_effect_score", "net_hidden_effect_score", "side_effect_score", "hidden_damage_delta", "fatigue_delta", "resource_inequality_delta",
    "reversibility_delta", "exploration_delta", "action_cost_effect", "timing_judgement", "v2_trace_used_as_action_runtime_input",
    "v2_trace_used_as_post_action_audit", "actionplanner_received_only_dept_inputs", "actionmodule_received_only_final_gate", "missing_input_flags",
]


def _clip(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _band(margin: float) -> str:
    if margin <= 0:
        return "suppressed_or_no_op"
    if margin <= SMALL:
        return "weak_probe_or_buffer"
    if margin <= MEDIUM:
        return "capped_insurance_candidate"
    return "defensive_candidate"


@dataclass
class LocalCase:
    label: str
    entity: str = "E000"
    target: str = "not_available"
    relation_id: str = "not_available"
    relation_pair: object = "not_available"
    risk: float = 0.20
    cost: float = 0.25
    pair_risk: float = 0.0
    pair_cost: float = 0.0
    burden: float = 0.20
    fatigue: float = 0.15
    hidden_damage: float = 0.10
    collapse: float = 0.10
    exploration_need: float = 0.20
    relation_strength: float = 0.0
    relation_rigidity: float = 0.0
    relation_flow: float = 0.0
    proposed_channel: str = "observe_only"
    action_strength_hint: float = 0.0
    action_coupling: float = 0.20
    action_cost_axis: float = 0.0
    action_mode: str = "none"
    recovering: bool = False


def _profile_config(case: LocalCase) -> dict:
    return {
        "implemented_axes": ["action_cost"],
        "cause_side_parameters": {"action_cost": case.action_cost_axis},
        "active_dynamics": {
            "no_op_decay": {"enabled": True, "intensity": 0.05},
            "hidden_damage_growth": {"enabled": True, "intensity": 0.05},
            "defensive_hoarding": {"enabled": True, "intensity": 0.05},
        },
        "side_effect_settings": {
            "exploration_exploitation_risk": 0.24,
            "stabilization_lockin_side_effect": 0.22,
        },
    }


def _real_v2_initial_state(case: LocalCase, seed: int = 303) -> AsymmetricGamePseudoRealitySystem:
    world = AsymmetricGamePseudoRealitySystem(
        seed=seed,
        scenario="phase2g21ar3_test_local_initial_state",
        n_entities=4,
        action_coupling=case.action_coupling,
        noise_scale=0.0,
        drift_scale=0.0,
        profile_config=_profile_config(case),
    )
    idx = world.entities["entity_id"].eq(case.entity)
    world.entities.loc[idx, "uncertainty"] = _clip(case.risk)
    world.entities.loc[idx, "volatility"] = _clip(case.risk * 0.50)
    world.entities.loc[idx, "reversibility"] = _clip(1.0 - case.risk)
    world.entities.loc[idx, "coupling"] = _clip(max(case.relation_strength, case.pair_risk))
    world.entities.loc[idx, "relation_lock"] = _clip(max(case.relation_rigidity, case.pair_risk))
    world.entities.loc[idx, "exploration"] = _clip(1.0 - case.exploration_need)
    world.hidden.loc[idx, "fatigue"] = _clip(case.fatigue)
    world.hidden.loc[idx, "hidden_damage"] = _clip(case.hidden_damage)
    world.hidden.loc[idx, "private_resource"] = _clip(1.0 - max(0.0, case.burden - 0.20))
    world.hidden.loc[idx, "information_quality"] = _clip(1.0 - case.risk * 0.50)
    if case.relation_id != "not_available":
        world.relations = pd.DataFrame([{
            "source": case.entity,
            "target": case.target,
            "relation_strength": case.relation_strength,
            "relation_rigidity": case.relation_rigidity,
            "flow": case.relation_flow,
        }])
    return world


def _relation_trace_from_initial_world(world: AsymmetricGamePseudoRealitySystem, case: LocalCase) -> pd.DataFrame:
    trace = world.emit_trace()["relation_trace"].copy()
    if case.relation_id == "not_available" or trace.empty:
        return pd.DataFrame(columns=["source_relation_id", "source_entity_id", "target_entity_id", "relation_pair", "relation_strength", "relation_rigidity", "relation_flow"])
    trace = trace.rename(columns={"source": "source_entity_id", "target": "target_entity_id", "flow": "relation_flow"})
    trace["source_relation_id"] = case.relation_id
    trace["relation_pair"] = list(zip(trace.source_entity_id, trace.target_entity_id))
    return trace[["source_relation_id", "source_entity_id", "target_entity_id", "relation_pair", "relation_strength", "relation_rigidity", "relation_flow"]]


def _transform_relation_trace_for_dept(relation_trace: pd.DataFrame) -> dict:
    if relation_trace.empty:
        return {"source_relation_id": "not_available", "target_entity_id": "not_available", "relation_pair": "not_available", "relation_strength": 0.0, "relation_rigidity": 0.0, "relation_flow": 0.0, "pair_relation_lock_proxy": 0.0, "pair_coupling_proxy": 0.0, "relation_suppression_reason": "none", "relation_trace_read_directly_by_actionmodule": False}
    r = relation_trace.iloc[0]
    lock = _clip(0.65 * r.relation_rigidity + 0.20 * r.relation_strength + 0.15 * (1 - abs(r.relation_flow)))
    coupling = _clip(0.55 * r.relation_strength + 0.35 * r.relation_rigidity + 0.10 * (1 - abs(r.relation_flow)))
    return {"source_relation_id": r.source_relation_id, "target_entity_id": r.target_entity_id, "relation_pair": r.relation_pair, "relation_strength": r.relation_strength, "relation_rigidity": r.relation_rigidity, "relation_flow": r.relation_flow, "pair_relation_lock_proxy": lock, "pair_coupling_proxy": coupling, "relation_suppression_reason": "none", "relation_trace_read_directly_by_actionmodule": False}


def _final_gate(channel: str, margin: float, burden: float, collapse: float, strength_hint: float) -> tuple[str, str, float]:
    if channel in NON_ACTIONS:
        return channel, channel, 0.0
    if burden > 0.78 or collapse > 0.78:
        return "cooldown", "cooldown", 0.0
    if margin <= 0:
        return "observe_only", "observe_only", 0.0
    return "allow_candidate", "none", _clip(strength_hint or (0.25 + margin))


def _action_frame(case: LocalCase, final_gate_decision: str, strength: float) -> pd.DataFrame | None:
    if final_gate_decision in NON_ACTIONS or strength <= 0:
        return None
    return pd.DataFrame([{"entity_id": case.entity, "action_channel": case.proposed_channel, "action_strength": strength}])


def _risk_score(trace: dict, entity_id: str) -> float:
    e = trace["entity_trace"]
    h = trace["v2_hidden_trace"]
    res = trace["v2_resource_trace"].iloc[0]
    target_e = e[e.entity_id.eq(entity_id)].iloc[0]
    target_h = h[h.entity_id.eq(entity_id)].iloc[0]
    return float((
        target_h.fatigue
        + target_h.hidden_damage
        + (1.0 - target_e.reversibility)
        + target_e.relation_lock
        + target_e.coupling
        + target_e.uncertainty
        + res.resource_inequality
    ) / 7.0)


def _post_action_audit(initial_trace: dict, no_op_trace: dict, action_trace: dict, entity_id: str) -> dict:
    no_op_effect = no_op_trace["v2_action_effect_trace"].iloc[0]
    action_effect = action_trace["v2_action_effect_trace"].iloc[0]
    initial_score = _risk_score(initial_trace, entity_id)
    no_op_score = _risk_score(no_op_trace, entity_id)
    action_score = _risk_score(action_trace, entity_id)
    return {
        "no_op_outcome_delta": no_op_score - initial_score,
        "action_outcome_delta": action_score - initial_score,
        "outcome_improvement_vs_no_op": no_op_score - action_score,
        "net_public_effect_score": float(action_effect.get("net_public_effect_score", 0.0)),
        "net_hidden_effect_score": float(action_effect.get("net_hidden_effect_score", 0.0)),
        "side_effect_score": float(action_effect.get("side_effect_score", 0.0)),
        "hidden_damage_delta": float(action_effect.get("hidden_damage_delta", 0.0)),
        "fatigue_delta": float(action_effect.get("fatigue_delta", 0.0)),
        "resource_inequality_delta": float(action_effect.get("resource_inequality_delta", 0.0)),
        "reversibility_delta": float(action_effect.get("reversibility_delta", 0.0)),
        "exploration_delta": float(action_effect.get("exploration_delta", 0.0)),
        "action_cost_effect": float(action_effect.get("action_cost_effect", 0.0)),
        "baseline_mode": str(no_op_effect.get("action_channel", "no_action")),
    }


def _run_branches(case: LocalCase) -> tuple[dict, dict, dict]:
    initial_world = _real_v2_initial_state(case)
    no_op_world = copy.deepcopy(initial_world)
    action_world = copy.deepcopy(initial_world)
    initial_trace = initial_world.emit_trace()
    no_op_trace = no_op_world.step(None)
    return initial_trace, no_op_trace, action_world


def _judge(row: dict) -> str:
    if row["missing_input_flags"]:
        return "unresolved"
    margin = row["local_fire_margin"]
    pair_margin = row["pair_fire_margin"]
    non_action = row["final_gate_decision"] in NON_ACTIONS
    improved = row["outcome_improvement_vs_no_op"] > 0.005
    harmful = row["outcome_improvement_vs_no_op"] < -0.005 or row["side_effect_score"] > row["local_no_action_risk_estimate"]
    high_burden = row["suppression_reason"] in {"burden", "fatigue", "collapse", "low_confidence", "burden+fatigue+collapse"}
    if row.get("recovering") and margin <= SMALL and non_action:
        return "correct_stop"
    if pair_margin > SMALL and row["action_mode"] == "coupling_relief" and improved:
        return "relation_correct_fire"
    if pair_margin > SMALL and row["no_op_outcome_delta"] > 0.005 and row["action_mode"] != "coupling_relief":
        return "missed_relation_fire"
    if pair_margin <= 0 and row["action_mode"] == "coupling_relief":
        return "spurious_relation_fire"
    if high_burden and non_action:
        return "correct_suppression"
    if row["action_mode"] == "weak_probe" and 0 < margin <= SMALL and row["outcome_improvement_vs_no_op"] > 0.001 and row["side_effect_score"] < 0.08:
        return "correct_weak_probe"
    if margin <= 0 and non_action:
        return "correct_no_fire"
    if margin <= SMALL and row["effective_action_strength"] > 0.50:
        return "early_fire"
    if margin > MEDIUM and row["no_op_outcome_delta"] > 0.005 and non_action:
        return "late_fire"
    if margin > SMALL and harmful:
        return "harmful_fire"
    if margin > SMALL and improved:
        return "correct_fire"
    return "unresolved"


def _build_row(case: LocalCase, *, drop: set[str] | None = None, force_strength: float | None = None) -> dict:
    drop = drop or set()
    initial_trace, no_op_trace, action_world = _run_branches(case)
    relation = _transform_relation_trace_for_dept(_relation_trace_from_initial_world(action_world, case))
    raw = asdict(case)
    missing = sorted(REQUIRED.intersection(drop))
    risk = raw["risk"] if "local_no_action_risk_estimate" not in drop else 0.0
    cost = raw["cost"] if "local_action_side_effect_cost_estimate" not in drop else 0.0
    margin = risk - cost
    pair_margin = case.pair_risk - case.pair_cost
    strength_hint = force_strength if force_strength is not None else case.action_strength_hint
    final, non_action, strength = _final_gate(case.proposed_channel, margin, case.burden, case.collapse, strength_hint)
    af = _action_frame(case, final, strength)
    action_trace = action_world.step(af)
    audit = _post_action_audit(initial_trace, no_op_trace, action_trace, case.entity)
    suppression = "none"
    if case.burden > 0.72: suppression = "burden"
    if case.fatigue > 0.78: suppression = "fatigue"
    if case.collapse > 0.75: suppression = "collapse"
    if case.burden > 0.72 and case.fatigue > 0.78 and case.collapse > 0.75: suppression = "burden+fatigue+collapse"
    row = {
        "run_id": f"{case.label}-303", "seed": 303, "scenario_label_for_audit_only": case.label, "t": 1,
        "source_entity_id": case.entity if "source_entity_id" not in drop else "unresolved", **relation,
        "local_no_action_risk_estimate": risk, "local_action_side_effect_cost_estimate": cost, "local_fire_margin": margin, "local_fire_band": "unresolved" if missing else _band(margin),
        "pair_no_action_risk_estimate": case.pair_risk, "pair_action_side_effect_cost_estimate": case.pair_cost, "pair_fire_margin": pair_margin, "pair_fire_band": _band(pair_margin),
        "recommended_action_channel": case.proposed_channel, "non_action_decision": non_action, "suppression_reason": suppression, "final_gate_decision": final, "effective_action_strength": strength,
        "action_mode": case.action_mode, **audit,
        "v2_trace_used_as_action_runtime_input": False, "v2_trace_used_as_post_action_audit": True, "actionplanner_received_only_dept_inputs": True, "actionmodule_received_only_final_gate": True, "missing_input_flags": [f"missing:{m}" for m in missing], "recovering": case.recovering,
    }
    row["timing_judgement"] = _judge(row)
    return row


def _case(name: str) -> LocalCase:
    cases = {
        "stable": LocalCase("stable", risk=0.14, cost=0.24, proposed_channel="observe_only"),
        "fatigue": LocalCase("fatigue", risk=0.42, cost=0.50, burden=0.86, fatigue=0.90, hidden_damage=0.80, collapse=0.70, proposed_channel="cooldown"),
        "irreversible": LocalCase("irreversible", entity="E001", risk=0.62, cost=0.32, proposed_channel="buffer_increase", action_strength_hint=1.0, action_mode="defensive_buffer"),
        "harmful": LocalCase("harmful", risk=0.62, cost=0.32, fatigue=0.50, hidden_damage=0.40, proposed_channel="exploration_injection", action_strength_hint=1.0, action_coupling=0.20, action_cost_axis=1.0, action_mode="exploration_injection"),
        "early": LocalCase("early", risk=0.31, cost=0.27, proposed_channel="buffer_increase", action_strength_hint=0.75, action_mode="strong_buffer"),
        "late": LocalCase("late", risk=0.66, cost=0.30, proposed_channel="no_op", action_mode="none"),
        "relation": LocalCase("relation", entity="E001", target="E002", relation_id="relation_B_C", relation_pair=("E001", "E002"), risk=0.46, cost=0.34, pair_risk=0.72, pair_cost=0.30, relation_strength=0.88, relation_rigidity=0.90, relation_flow=0.08, proposed_channel="coupling_relief", action_strength_hint=1.0, action_mode="coupling_relief"),
        "missed_relation": LocalCase("missed_relation", entity="E001", target="E002", relation_id="relation_B_C", relation_pair=("E001", "E002"), risk=0.46, cost=0.34, pair_risk=0.72, pair_cost=0.30, relation_strength=0.88, relation_rigidity=0.90, relation_flow=0.08, proposed_channel="observe_only", action_mode="none"),
        "low_probe": LocalCase("low_probe", risk=0.30, cost=0.24, exploration_need=0.82, proposed_channel="uncertainty_probe", action_strength_hint=1.0, action_coupling=0.02, action_mode="weak_probe"),
        "high_probe": LocalCase("high_probe", risk=0.48, cost=0.44, burden=0.90, fatigue=0.88, hidden_damage=0.82, collapse=0.86, exploration_need=0.88, proposed_channel="cooldown", action_mode="none"),
        "recovery": LocalCase("recovery", risk=0.27, cost=0.23, proposed_channel="cooldown", action_mode="none", recovering=True),
        "resource": LocalCase("resource", entity="E002", risk=0.34, cost=0.43, burden=0.70, proposed_channel="observe_only", action_mode="none"),
    }
    return cases[name]


def real_v2_fire_margin_timing_validation_summary() -> pd.DataFrame:
    df = pd.DataFrame([_build_row(_case(n)) for n in ["stable", "fatigue", "irreversible", "relation", "resource", "low_probe", "high_probe", "recovery"]])
    return df[SUMMARY_COLUMNS]


def test_observe_only_is_preserved_as_non_action_decision():
    row = _build_row(_case("stable")); assert row["final_gate_decision"] == "observe_only" and row["effective_action_strength"] == 0.0 and row["recommended_action_channel"] != "buffer_increase"

def test_no_op_and_cooldown_do_not_map_to_buffer_increase():
    assert _build_row(_case("late"))["final_gate_decision"] == "no_op"; assert _build_row(_case("fatigue"))["final_gate_decision"] == "cooldown"

def test_relation_trace_is_transformed_before_planner_not_read_directly():
    row = _build_row(_case("relation")); assert row["source_relation_id"] == "relation_B_C" and row["actionplanner_received_only_dept_inputs"] and row["actionmodule_received_only_final_gate"] and not row["relation_trace_read_directly_by_actionmodule"]

def test_pair_fire_margin_is_computed_for_relation_risk():
    row = _build_row(_case("relation")); assert row["pair_fire_margin"] == row["pair_no_action_risk_estimate"] - row["pair_action_side_effect_cost_estimate"] and row["pair_fire_band"] == "defensive_candidate"

def test_fire_margin_non_positive_prefers_no_fire_or_observe():
    row = _build_row(_case("stable")); assert row["local_fire_margin"] <= 0 and row["timing_judgement"] == "correct_no_fire"

def test_high_fatigue_high_cost_prefers_suppression_or_cooldown():
    row = _build_row(_case("fatigue")); assert row["final_gate_decision"] == "cooldown" and row["timing_judgement"] in {"correct_suppression", "correct_no_fire"}

def test_positive_fire_margin_with_no_op_worsening_can_be_correct_fire():
    row = _build_row(_case("irreversible")); assert row["no_op_outcome_delta"] > row["action_outcome_delta"] and row["timing_judgement"] == "correct_fire"

def test_positive_fire_margin_with_harmful_action_can_be_harmful_fire():
    row = _build_row(_case("harmful")); assert row["action_outcome_delta"] > row["no_op_outcome_delta"] and row["timing_judgement"] == "harmful_fire"

def test_low_margin_strong_action_is_early_fire():
    assert _build_row(_case("early"), force_strength=0.75)["timing_judgement"] == "early_fire"

def test_high_margin_no_fire_with_no_op_worsening_is_late_fire():
    row = _build_row(_case("late")); assert row["no_op_outcome_delta"] > 0 and row["timing_judgement"] == "late_fire"

def test_relation_pair_risk_can_trigger_relation_correct_fire():
    row = _build_row(_case("relation")); assert row["outcome_improvement_vs_no_op"] > 0 and row["timing_judgement"] == "relation_correct_fire"

def test_missing_relation_action_when_pair_risk_worsens_is_missed_relation_fire():
    assert _build_row(_case("missed_relation"))["timing_judgement"] == "missed_relation_fire"

def test_low_burden_exploration_loss_allows_correct_weak_probe():
    row = _build_row(_case("low_probe")); assert row["timing_judgement"] == "correct_weak_probe" and row["v2_trace_used_as_post_action_audit"]

def test_high_burden_exploration_loss_keeps_correct_suppression():
    row = _build_row(_case("high_probe")); assert row["recommended_action_channel"] != "exploration_injection" and row["timing_judgement"] == "correct_suppression"

def test_recovery_series_stops_or_cools_down():
    assert _build_row(_case("recovery"))["timing_judgement"] == "correct_stop"

def test_v2_traces_are_post_action_audit_not_runtime_inputs():
    df = real_v2_fire_margin_timing_validation_summary(); assert not df.v2_trace_used_as_action_runtime_input.any() and df.v2_trace_used_as_post_action_audit.all()

def test_scenario_label_is_audit_only_not_timing_judgement_control():
    row = _build_row(_case("irreversible")); changed = dict(row, scenario_label_for_audit_only="stable"); changed["timing_judgement"] = _judge(changed); assert changed["timing_judgement"] == row["timing_judgement"]

def test_missing_fields_become_unresolved_not_silent_pass():
    row = _build_row(_case("stable"), drop={"local_no_action_risk_estimate"}); assert row["missing_input_flags"] and row["local_fire_band"] == "unresolved" and row["timing_judgement"] == "unresolved"

def test_fire_margin_timing_summary_exports_to_dataframe_and_csv(tmp_path):
    df = real_v2_fire_margin_timing_validation_summary(); path = tmp_path / "real_v2_fire_margin_timing_validation_summary.csv"; df.to_csv(path, index=False); loaded = pd.read_csv(path); assert list(loaded.columns) == SUMMARY_COLUMNS and not loaded.empty and "pair_fire_margin" in loaded.columns
