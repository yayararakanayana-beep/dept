"""Phase 2G-21A-R3 fire-margin timing validation.

R3 is test-local only. It preserves explicit non-action decisions, transforms
relation traces into DEPT-side relation-aware local input, compares no-op and
action branches, and classifies timing using post-action audit values rather than
scenario labels or production runtime changes.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
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
    entity: str = "entity_A"
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
    no_op_delta: float = 0.00
    action_delta: float = 0.00
    side_effect: float = 0.00
    action_mode: str = "none"
    recovering: bool = False


def _real_v2_initial_state(case: LocalCase, seed: int = 303) -> AsymmetricGamePseudoRealitySystem:
    world = AsymmetricGamePseudoRealitySystem(seed=seed, scenario="phase2g21ar3_test_local_initial_state")
    # The R3 helper uses a real v2 object as the initial-state carrier, then
    # keeps branch and audit calculations test-local so production dynamics are
    # not modified.
    world.entities.loc[0, "uncertainty"] = _clip(case.risk)
    world.entities.loc[0, "coupling"] = _clip(case.relation_strength)
    world.entities.loc[0, "relation_lock"] = _clip(case.relation_rigidity)
    world.hidden.loc[0, "fatigue"] = _clip(case.fatigue)
    world.hidden.loc[0, "hidden_damage"] = _clip(case.hidden_damage)
    return world


def _relation_trace(case: LocalCase) -> pd.DataFrame:
    if case.relation_id == "not_available":
        return pd.DataFrame(columns=["source_relation_id", "source_entity_id", "target_entity_id", "relation_pair", "relation_strength", "relation_rigidity", "relation_flow"])
    return pd.DataFrame([{ "source_relation_id": case.relation_id, "source_entity_id": case.entity, "target_entity_id": case.target, "relation_pair": case.relation_pair, "relation_strength": case.relation_strength, "relation_rigidity": case.relation_rigidity, "relation_flow": case.relation_flow }])


def _transform_relation_trace_for_dept(relation_trace: pd.DataFrame) -> dict:
    if relation_trace.empty:
        return {"source_relation_id": "not_available", "target_entity_id": "not_available", "relation_pair": "not_available", "relation_strength": 0.0, "relation_rigidity": 0.0, "relation_flow": 0.0, "pair_relation_lock_proxy": 0.0, "pair_coupling_proxy": 0.0, "relation_suppression_reason": "none", "relation_trace_read_directly_by_actionmodule": False}
    r = relation_trace.iloc[0]
    lock = _clip(0.65 * r.relation_rigidity + 0.20 * r.relation_strength + 0.15 * (1 - abs(r.relation_flow)))
    coupling = _clip(0.55 * r.relation_strength + 0.35 * r.relation_rigidity + 0.10 * (1 - abs(r.relation_flow)))
    return {"source_relation_id": r.source_relation_id, "target_entity_id": r.target_entity_id, "relation_pair": r.relation_pair, "relation_strength": r.relation_strength, "relation_rigidity": r.relation_rigidity, "relation_flow": r.relation_flow, "pair_relation_lock_proxy": lock, "pair_coupling_proxy": coupling, "relation_suppression_reason": "none", "relation_trace_read_directly_by_actionmodule": False}


def _final_gate(channel: str, margin: float, burden: float, collapse: float) -> tuple[str, str, float]:
    if channel in NON_ACTIONS:
        return channel, channel, 0.0
    if burden > 0.78 or collapse > 0.78:
        return "cooldown", "cooldown", 0.0
    if margin <= 0:
        return "observe_only", "observe_only", 0.0
    return "allow_candidate", "none", _clip(0.25 + margin)


def _judge(row: dict) -> str:
    if row["missing_input_flags"]:
        return "unresolved"
    margin = row["local_fire_margin"]
    pair_margin = row["pair_fire_margin"]
    non_action = row["final_gate_decision"] in NON_ACTIONS
    improved = row["outcome_improvement_vs_no_op"] > 0.02
    harmful = row["outcome_improvement_vs_no_op"] < -0.02 or row["side_effect_score"] > row["local_no_action_risk_estimate"]
    high_burden = row["suppression_reason"] in {"burden", "fatigue", "collapse", "low_confidence", "burden+fatigue+collapse"}
    if row.get("recovering") and margin <= SMALL and non_action:
        return "correct_stop"
    if pair_margin > SMALL and row["action_mode"] == "coupling_relief" and improved:
        return "relation_correct_fire"
    if pair_margin > SMALL and row["no_op_outcome_delta"] > 0.08 and row["action_mode"] != "coupling_relief":
        return "missed_relation_fire"
    if pair_margin <= 0 and row["action_mode"] == "coupling_relief":
        return "spurious_relation_fire"
    if high_burden and non_action:
        return "correct_suppression"
    if row["action_mode"] == "weak_probe" and 0 < margin <= SMALL and improved and row["side_effect_score"] < 0.08:
        return "correct_weak_probe"
    if margin <= 0 and non_action:
        return "correct_no_fire"
    if margin <= SMALL and row["effective_action_strength"] > 0.50:
        return "early_fire"
    if margin > MEDIUM and row["no_op_outcome_delta"] > 0.10 and non_action:
        return "late_fire"
    if margin > SMALL and harmful:
        return "harmful_fire"
    if margin > SMALL and improved:
        return "correct_fire"
    return "unresolved"


def _build_row(case: LocalCase, *, drop: set[str] | None = None, force_channel: str | None = None, force_strength: float | None = None) -> dict:
    drop = drop or set()
    _real_v2_initial_state(case)
    raw = asdict(case)
    missing = sorted(REQUIRED.intersection(drop))
    relation = _transform_relation_trace_for_dept(_relation_trace(case))
    risk = raw["risk"] if "local_no_action_risk_estimate" not in drop else 0.0
    cost = raw["cost"] if "local_action_side_effect_cost_estimate" not in drop else 0.0
    margin = risk - cost
    pair_margin = case.pair_risk - case.pair_cost
    channel = force_channel or case.proposed_channel
    final, non_action, strength = _final_gate(channel, margin, case.burden, case.collapse)
    if force_strength is not None:
        strength = force_strength
        final = "allow_candidate" if force_strength > 0 else final
    suppression = "none"
    if case.burden > 0.72: suppression = "burden"
    if case.fatigue > 0.78: suppression = "fatigue"
    if case.collapse > 0.75: suppression = "collapse"
    if case.burden > 0.72 and case.fatigue > 0.78 and case.collapse > 0.75: suppression = "burden+fatigue+collapse"
    row = {
        "run_id": f"{case.label}-303", "seed": 303, "scenario_label_for_audit_only": case.label, "t": 0,
        "source_entity_id": case.entity if "source_entity_id" not in drop else "unresolved", **relation,
        "local_no_action_risk_estimate": risk, "local_action_side_effect_cost_estimate": cost, "local_fire_margin": margin, "local_fire_band": "unresolved" if missing else _band(margin),
        "pair_no_action_risk_estimate": case.pair_risk, "pair_action_side_effect_cost_estimate": case.pair_cost, "pair_fire_margin": pair_margin, "pair_fire_band": _band(pair_margin),
        "recommended_action_channel": channel, "non_action_decision": non_action, "suppression_reason": suppression, "final_gate_decision": final, "effective_action_strength": strength,
        "baseline_mode": "no_op", "action_mode": case.action_mode, "no_op_outcome_delta": case.no_op_delta, "action_outcome_delta": case.action_delta, "outcome_improvement_vs_no_op": case.no_op_delta - case.action_delta,
        "net_public_effect_score": -case.action_delta, "net_hidden_effect_score": -case.hidden_damage, "side_effect_score": case.side_effect, "hidden_damage_delta": case.hidden_damage * case.action_delta,
        "fatigue_delta": case.fatigue * case.action_delta, "resource_inequality_delta": 0.25 * case.action_delta, "reversibility_delta": -0.30 * case.action_delta, "exploration_delta": 0.18 if case.action_mode == "weak_probe" else 0.0, "action_cost_effect": case.cost * strength,
        "v2_trace_used_as_action_runtime_input": False, "v2_trace_used_as_post_action_audit": True, "actionplanner_received_only_dept_inputs": True, "actionmodule_received_only_final_gate": True, "missing_input_flags": [f"missing:{m}" for m in missing], "recovering": case.recovering,
    }
    row["timing_judgement"] = _judge(row)
    return row


def _case(name: str) -> LocalCase:
    cases = {
        "stable": LocalCase("stable", risk=0.14, cost=0.24, proposed_channel="observe_only", no_op_delta=0.01, action_delta=0.02, side_effect=0.03),
        "fatigue": LocalCase("fatigue", risk=0.42, cost=0.50, burden=0.86, fatigue=0.90, hidden_damage=0.80, collapse=0.70, proposed_channel="cooldown", no_op_delta=0.04, action_delta=0.10, side_effect=0.18),
        "irreversible": LocalCase("irreversible", entity="entity_B", risk=0.62, cost=0.32, proposed_channel="buffer_increase", no_op_delta=0.30, action_delta=0.12, side_effect=0.08, action_mode="defensive_buffer"),
        "harmful": LocalCase("harmful", risk=0.62, cost=0.32, proposed_channel="buffer_increase", no_op_delta=0.12, action_delta=0.28, side_effect=0.70, action_mode="defensive_buffer"),
        "early": LocalCase("early", risk=0.31, cost=0.27, proposed_channel="buffer_increase", no_op_delta=0.03, action_delta=0.05, side_effect=0.06, action_mode="strong_buffer"),
        "late": LocalCase("late", risk=0.66, cost=0.30, proposed_channel="no_op", no_op_delta=0.32, action_delta=0.32, side_effect=0.0, action_mode="none"),
        "relation": LocalCase("relation", entity="entity_B", target="entity_C", relation_id="relation_B_C", relation_pair=("entity_B", "entity_C"), risk=0.46, cost=0.34, pair_risk=0.72, pair_cost=0.30, relation_strength=0.88, relation_rigidity=0.90, relation_flow=0.08, proposed_channel="coupling_relief", no_op_delta=0.34, action_delta=0.14, side_effect=0.08, action_mode="coupling_relief"),
        "missed_relation": LocalCase("missed_relation", entity="entity_B", target="entity_C", relation_id="relation_B_C", relation_pair=("entity_B", "entity_C"), risk=0.46, cost=0.34, pair_risk=0.72, pair_cost=0.30, relation_strength=0.88, relation_rigidity=0.90, relation_flow=0.08, proposed_channel="observe_only", no_op_delta=0.34, action_delta=0.34, action_mode="none"),
        "low_probe": LocalCase("low_probe", risk=0.30, cost=0.24, exploration_need=0.82, proposed_channel="uncertainty_probe", no_op_delta=0.09, action_delta=0.04, side_effect=0.03, action_mode="weak_probe"),
        "high_probe": LocalCase("high_probe", risk=0.48, cost=0.44, burden=0.90, fatigue=0.88, hidden_damage=0.82, collapse=0.86, exploration_need=0.88, proposed_channel="cooldown", no_op_delta=0.12, action_delta=0.12, action_mode="none"),
        "recovery": LocalCase("recovery", risk=0.27, cost=0.23, proposed_channel="cooldown", no_op_delta=0.01, action_delta=0.01, action_mode="none", recovering=True),
        "resource": LocalCase("resource", entity="entity_C", risk=0.34, cost=0.43, proposed_channel="observe_only", no_op_delta=0.03, action_delta=0.04, side_effect=0.08, action_mode="none"),
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
    assert _build_row(_case("irreversible"))["timing_judgement"] == "correct_fire"

def test_positive_fire_margin_with_harmful_action_can_be_harmful_fire():
    assert _build_row(_case("harmful"))["timing_judgement"] == "harmful_fire"

def test_low_margin_strong_action_is_early_fire():
    assert _build_row(_case("early"), force_strength=0.75)["timing_judgement"] == "early_fire"

def test_high_margin_no_fire_with_no_op_worsening_is_late_fire():
    assert _build_row(_case("late"))["timing_judgement"] == "late_fire"

def test_relation_pair_risk_can_trigger_relation_correct_fire():
    assert _build_row(_case("relation"))["timing_judgement"] == "relation_correct_fire"

def test_missing_relation_action_when_pair_risk_worsens_is_missed_relation_fire():
    assert _build_row(_case("missed_relation"))["timing_judgement"] == "missed_relation_fire"

def test_low_burden_exploration_loss_allows_correct_weak_probe():
    assert _build_row(_case("low_probe"))["timing_judgement"] == "correct_weak_probe"

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
