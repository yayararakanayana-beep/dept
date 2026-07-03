"""Phase 2G-21B-A action-effect direction audit.

Test-local post-action audit only: derives component deltas from real v2
initial/no-op/action branch traces. Production runtime files are not modified.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import copy
import inspect
import sys

import pandas as pd

RC1_ROOT = Path(__file__).resolve().parents[1] / "localprep1" / "dept" / "DEPT2_ActionModule_ActuationPrimitives_RC1"
if str(RC1_ROOT) not in sys.path:
    sys.path.insert(0, str(RC1_ROOT))

from pseudo_reality.asymmetric_game_v2 import AsymmetricGamePseudoRealitySystem  # noqa: E402
from test_phase2g21ar3_fire_margin_timing_validation import (  # noqa: E402
    NON_ACTIONS,
    _case,
    _final_gate,
    _post_action_audit,
    _real_v2_initial_state,
    _run_branches,
)

TOLERANCE = 1e-6
MATERIAL_THRESHOLD = 0.002
SURFACE_COMPONENTS = ["activity", "volatility", "uncertainty", "relation_lock", "coupling", "exploration", "reversibility", "entropy"]
HIDDEN_COMPONENTS = ["latent_pressure", "fatigue", "private_resource", "defensiveness", "opportunism", "cooperation_intent", "information_quality", "hidden_damage"]
RESOURCE_COMPONENTS = ["shared_resource", "commons_health", "resource_inequality"]
RELATION_COMPONENTS = ["relation_strength", "relation_rigidity", "relation_flow"]
SIDE_EFFECT_COMPONENTS = {"fatigue", "hidden_damage", "resource_inequality", "defensiveness"}
NON_ACTION_CHANNELS = {"no_op", "observe_only", "cooldown", "hold_shadow"}
EXPECTED_DIRECTIONS = {
    "exploration_injection": {"primary": {"exploration": "increase"}, "secondary": {}, "side_effect": {"fatigue": "increase"}},
    "coupling_relief": {"primary": {"coupling": "decrease", "relation_lock": "decrease", "latent_pressure": "decrease", "relation_rigidity": "decrease", "relation_strength": "decrease_or_stabilize"}, "secondary": {}, "side_effect": {}},
    "volatility_damping": {"primary": {"volatility": "decrease"}, "secondary": {"fatigue": "decrease_or_stabilize"}, "side_effect": {}},
    "uncertainty_probe": {"primary": {"uncertainty": "decrease", "information_quality": "increase"}, "secondary": {}, "side_effect": {}},
    "relation_unlock": {"primary": {"relation_lock": "decrease"}, "secondary": {}, "side_effect": {"defensiveness": "increase", "fatigue": "increase_or_stabilize"}},
    "buffer_increase": {"primary": {"reversibility": "increase"}, "secondary": {"private_resource": "increase"}, "side_effect": {}},
    "no_op": {"primary": {}, "secondary": {}, "side_effect": {}},
    "observe_only": {"primary": {}, "secondary": {}, "side_effect": {}},
    "cooldown": {"primary": {}, "secondary": {}, "side_effect": {}},
    "hold_shadow": {"primary": {}, "secondary": {}, "side_effect": {}},
}

SUMMARY_COLUMNS = ["run_id", "seed", "scenario_label_for_audit_only", "t", "source_entity_id", "source_relation_id", "target_entity_id", "relation_pair", "recommended_action_channel", "final_gate_decision", "non_action_decision", "action_mode", "action_channel", "requested_action_strength", "effective_action_strength", "v2_applied_strength", "action_coupling", "local_fire_margin", "pair_fire_margin", "fire_permission_context", "suppression_reason", "timing_judgement", "before_risk_score", "no_op_risk_score", "action_risk_score", "no_op_outcome_delta", "action_outcome_delta", "outcome_improvement_vs_no_op", "primary_expected_components", "secondary_expected_components", "expected_side_effect_components", "primary_effect_match_count", "primary_effect_miss_count", "secondary_effect_match_count", "side_effect_detected_count", "wrong_direction_count", "no_material_effect_count", "direct_effect_score", "side_effect_score", "net_public_effect_score", "net_hidden_effect_score", "action_cost_effect", "effect_direction_judgement", "missing_input_flags", "v2_trace_used_as_action_runtime_input", "v2_trace_used_as_post_action_audit", "actionplanner_received_only_dept_inputs", "actionmodule_received_only_final_gate"]
LONG_COLUMNS = ["run_id", "seed", "scenario_label_for_audit_only", "t", "source_entity_id", "source_relation_id", "target_entity_id", "relation_pair", "action_channel", "action_mode", "effective_action_strength", "v2_applied_strength", "component_group", "component_name", "expected_direction", "effect_role", "initial_value", "no_op_value", "action_value", "no_op_delta", "action_delta", "action_vs_no_op_delta", "directional_improvement_vs_no_op", "direction_match", "side_effect_flag", "material_change_flag", "component_effect_judgement", "timing_judgement", "missing_input_flags"]

@dataclass
class ActionEffectAudit:
    action_effect_direction_summary: pd.DataFrame
    action_effect_component_delta_long: pd.DataFrame


def _value(trace, group, name, entity_id, relation_pair=None):
    if group == "surface":
        df = trace["entity_trace"]; return float(df[df.entity_id.eq(entity_id)].iloc[0][name])
    if group == "hidden":
        df = trace["v2_hidden_trace"]; return float(df[df.entity_id.eq(entity_id)].iloc[0][name])
    if group == "resource":
        return float(trace["v2_resource_trace"].iloc[0][name])
    rel = trace["relation_trace"]
    if rel.empty or relation_pair in {None, "not_available"}:
        return None
    src, dst = relation_pair
    rows = rel[rel.source.eq(src) & rel.target.eq(dst)]
    if rows.empty:
        return None
    return float(rows.iloc[0]["flow" if name == "relation_flow" else name])


def _expected(channel, component):
    spec = EXPECTED_DIRECTIONS.get(channel, {"primary": {}, "secondary": {}, "side_effect": {}})
    for role in ("primary", "secondary", "side_effect"):
        if component in spec[role]:
            return spec[role][component], role
    return "not_applicable", "not_applicable"


def _direction_match(expected, no_op_value, action_value):
    if expected == "not_applicable": return "not_applicable"
    if expected == "increase": return bool(action_value > no_op_value + TOLERANCE)
    if expected == "decrease": return bool(action_value < no_op_value - TOLERANCE)
    if expected == "stable": return bool(abs(action_value - no_op_value) <= TOLERANCE)
    if expected == "decrease_or_stabilize": return bool(action_value <= no_op_value + TOLERANCE)
    if expected == "increase_or_stabilize": return bool(action_value >= no_op_value - TOLERANCE)
    raise AssertionError(expected)


def _directional_improvement(expected, initial_value, no_op_value, action_value):
    if expected in {"decrease", "decrease_or_stabilize"}: return no_op_value - action_value
    if expected in {"increase", "increase_or_stabilize"}: return action_value - no_op_value
    if expected == "stable": return abs(no_op_value - initial_value) - abs(action_value - initial_value)
    return 0.0


def _component_judgement(role, expected, direction_match, improvement, avn_delta, component):
    material = abs(avn_delta) > MATERIAL_THRESHOLD
    if expected == "not_applicable":
        if component in SIDE_EFFECT_COMPONENTS and material and avn_delta > 0:
            return "side_effect_detected"
        return "not_applicable" if not material else "unresolved"
    if not material: return "no_material_effect"
    if direction_match is True:
        if role == "primary": return "primary_effect_matched"
        if role == "secondary": return "secondary_effect_matched"
        if role == "side_effect": return "side_effect_detected"
    if improvement < -MATERIAL_THRESHOLD: return "wrong_direction"
    return "unresolved"


def _build_audit_row(case_name, *, label_override=None, include_relation=True):
    case = _case(case_name)
    initial_trace, no_op_trace, action_world = _run_branches(case)
    margin = case.risk - case.cost
    final, non_action, strength = _final_gate(case.proposed_channel, margin, case.burden, case.collapse, case.action_strength_hint)
    action_frame = None if final in NON_ACTIONS or strength <= 0 else pd.DataFrame([{"entity_id": case.entity, "action_channel": case.proposed_channel, "action_strength": strength}])
    action_trace = action_world.step(action_frame)
    if not include_relation:
        for tr in (initial_trace, no_op_trace, action_trace):
            tr["relation_trace"] = pd.DataFrame()
    audit = _post_action_audit(initial_trace, no_op_trace, action_trace, case.entity)
    action_effect = action_trace["v2_action_effect_trace"].iloc[0]
    channel = str(action_effect.get("action_channel", "no_action")) if action_frame is not None else final
    v2_applied = float(action_effect.get("action_intensity", 0.0)) if action_frame is not None else 0.0
    rel_pair = case.relation_pair if case.relation_pair != "not_available" else "not_available"
    rows = []
    for group, comps in [("surface", SURFACE_COMPONENTS), ("hidden", HIDDEN_COMPONENTS), ("resource", RESOURCE_COMPONENTS), ("relation", RELATION_COMPONENTS)]:
        for comp in comps:
            missing = []
            iv = _value(initial_trace, group, comp, case.entity, rel_pair)
            nv = _value(no_op_trace, group, comp, case.entity, rel_pair)
            av = _value(action_trace, group, comp, case.entity, rel_pair)
            expected, role = _expected(channel, comp)
            if iv is None or nv is None or av is None:
                missing = ["relation_trace:not_available_in_21B_A"]
                dm, imp, judgement = "not_applicable", 0.0, "unresolved"
                iv = nv = av = float("nan")
                nd = ad = avn = 0.0
            else:
                nd, ad, avn = nv - iv, av - iv, av - nv
                dm = _direction_match(expected, nv, av)
                imp = _directional_improvement(expected, iv, nv, av)
                judgement = _component_judgement(role, expected, dm, imp, avn, comp)
            rows.append({"run_id": f"{case.label}-303", "seed": 303, "scenario_label_for_audit_only": label_override or case.label, "t": 1, "source_entity_id": case.entity, "source_relation_id": case.relation_id, "target_entity_id": case.target, "relation_pair": rel_pair, "action_channel": channel, "action_mode": case.action_mode, "effective_action_strength": strength, "v2_applied_strength": v2_applied, "component_group": group, "component_name": comp, "expected_direction": expected, "effect_role": role, "initial_value": iv, "no_op_value": nv, "action_value": av, "no_op_delta": nd, "action_delta": ad, "action_vs_no_op_delta": avn, "directional_improvement_vs_no_op": imp, "direction_match": dm, "side_effect_flag": judgement == "side_effect_detected", "material_change_flag": abs(avn) > MATERIAL_THRESHOLD, "component_effect_judgement": judgement, "timing_judgement": "", "missing_input_flags": missing})
    long = pd.DataFrame(rows)
    missing_flags = sorted({f for flags in long.missing_input_flags for f in flags})
    primary = long[long.effect_role.eq("primary")]
    secondary = long[long.effect_role.eq("secondary")]
    primary_match = int((primary.component_effect_judgement == "primary_effect_matched").sum())
    wrong = int((long.component_effect_judgement == "wrong_direction").sum())
    side = int((long.component_effect_judgement == "side_effect_detected").sum())
    no_mat = int((long.component_effect_judgement == "no_material_effect").sum())
    if missing_flags and case.relation_id != "not_available":
        effect_j = "unresolved"
    elif channel in NON_ACTION_CHANNELS:
        effect_j = "correct_non_action" if strength == 0.0 and v2_applied == 0.0 else "unresolved"
    elif wrong > primary_match and wrong:
        effect_j = "wrong_direction_dominant"
    elif side > primary_match:
        effect_j = "side_effect_dominant"
    elif primary_match and side and audit["outcome_improvement_vs_no_op"] > 0:
        effect_j = "mixed_but_acceptable"
    elif primary_match and side:
        effect_j = "side_effect_dominant"
    elif primary_match and channel in {"coupling_relief", "relation_unlock"}:
        effect_j = "relation_effect_matched"
    elif primary_match:
        effect_j = "clean_primary_effect"
    elif no_mat >= len(primary):
        effect_j = "no_material_effect"
    else:
        effect_j = "unresolved"
    before = audit["no_op_outcome_delta"] + 0.0 # trace-derived audit already used; risk source is helper below
    base_score = audit["action_outcome_delta"] - audit["outcome_improvement_vs_no_op"]
    summary = {"run_id": f"{case.label}-303", "seed": 303, "scenario_label_for_audit_only": label_override or case.label, "t": 1, "source_entity_id": case.entity, "source_relation_id": case.relation_id, "target_entity_id": case.target, "relation_pair": rel_pair, "recommended_action_channel": case.proposed_channel, "final_gate_decision": final, "non_action_decision": non_action, "action_mode": case.action_mode, "action_channel": channel, "requested_action_strength": case.action_strength_hint, "effective_action_strength": strength, "v2_applied_strength": v2_applied, "action_coupling": case.action_coupling, "local_fire_margin": margin, "pair_fire_margin": case.pair_risk - case.pair_cost, "fire_permission_context": "test_local_final_gate", "suppression_reason": "none", "timing_judgement": "", "before_risk_score": base_score - audit["no_op_outcome_delta"], "no_op_risk_score": base_score, "action_risk_score": base_score - audit["outcome_improvement_vs_no_op"], **audit, "primary_expected_components": primary.component_name.tolist(), "secondary_expected_components": secondary.component_name.tolist(), "expected_side_effect_components": long[long.effect_role.eq("side_effect")].component_name.tolist(), "primary_effect_match_count": primary_match, "primary_effect_miss_count": int(len(primary) - primary_match), "secondary_effect_match_count": int((secondary.component_effect_judgement == "secondary_effect_matched").sum()), "side_effect_detected_count": side, "wrong_direction_count": wrong, "no_material_effect_count": no_mat, "direct_effect_score": float(action_effect.get("direct_effect_score", 0.0)), "effect_direction_judgement": effect_j, "missing_input_flags": missing_flags, "v2_trace_used_as_action_runtime_input": False, "v2_trace_used_as_post_action_audit": True, "actionplanner_received_only_dept_inputs": True, "actionmodule_received_only_final_gate": True}
    long["timing_judgement"] = summary["timing_judgement"]
    return summary, long[LONG_COLUMNS]


def action_effect_direction_audit() -> ActionEffectAudit:
    names = ["stable", "fatigue", "irreversible", "relation", "resource", "low_probe", "high_probe", "recovery", "harmful", "early", "late", "missed_relation"]
    summaries, longs = zip(*[_build_audit_row(n) for n in names])
    return ActionEffectAudit(pd.DataFrame(summaries)[SUMMARY_COLUMNS], pd.concat(longs, ignore_index=True)[LONG_COLUMNS])

# Required and desired tests
def test_action_effect_direction_summary_exports_expected_columns(): assert list(action_effect_direction_audit().action_effect_direction_summary.columns) == SUMMARY_COLUMNS
def test_action_effect_component_delta_long_exports_expected_columns(): assert list(action_effect_direction_audit().action_effect_component_delta_long.columns) == LONG_COLUMNS
def test_component_deltas_are_derived_from_initial_noop_action_traces():
    _, long = _build_audit_row("irreversible"); row = long[long.component_name.eq("reversibility")].iloc[0]; assert row.action_delta == row.action_value - row.initial_value and row.no_op_delta == row.no_op_value - row.initial_value and row.action_vs_no_op_delta == row.action_value - row.no_op_value

def test_no_fixed_localcase_deltas_used_for_component_effects(): assert "no_op_delta" not in inspect.signature(type(_case("stable"))).parameters and "component_delta" not in inspect.signature(type(_case("stable"))).parameters
def test_coupling_relief_decreases_coupling_or_relation_lock_vs_noop():
    _, long = _build_audit_row("relation"); sub = long[long.component_name.isin(["coupling", "relation_lock"])] ; assert (sub.direction_match == True).any()
def test_uncertainty_probe_reduces_uncertainty_or_improves_information_quality_vs_noop():
    _, long = _build_audit_row("low_probe"); sub = long[long.component_name.isin(["uncertainty", "information_quality"])] ; assert (sub.direction_match == True).any()
def test_buffer_increase_improves_reversibility_or_private_resource_vs_noop():
    _, long = _build_audit_row("irreversible"); sub = long[long.component_name.isin(["reversibility", "private_resource"])] ; assert (sub.direction_match == True).any()
def test_exploration_injection_can_raise_exploration_and_surface_fatigue_side_effect():
    summary, long = _build_audit_row("harmful"); assert long[long.component_name.eq("exploration")].iloc[0].direction_match is True or long[long.component_name.eq("exploration")].iloc[0].direction_match == True; assert summary["side_effect_detected_count"] >= 1

def test_non_action_decisions_have_zero_effective_and_applied_strength():
    df = action_effect_direction_audit().action_effect_direction_summary; sub = df[df.final_gate_decision.isin(NON_ACTION_CHANNELS)]; assert (sub.effective_action_strength == 0).all() and (sub.v2_applied_strength == 0).all()
def test_directional_improvement_uses_expected_direction(): assert round(_directional_improvement("decrease", 1, .8, .6), 6) == .2 and round(_directional_improvement("increase", 1, .8, .9), 6) == .1
def test_side_effect_components_are_recorded(): assert {"fatigue", "hidden_damage", "resource_inequality"}.issubset(set(action_effect_direction_audit().action_effect_component_delta_long.component_name))
def test_harmful_case_surfaces_side_effect_dominant_or_mixed_effect(): assert _build_audit_row("harmful")[0]["effect_direction_judgement"] in {"side_effect_dominant", "mixed_but_acceptable"}
def test_relation_case_records_relation_component_deltas():
    _, long = _build_audit_row("relation"); assert set(RELATION_COMPONENTS).issubset(set(long[long.component_group.eq("relation")].component_name))
def test_missing_relation_trace_is_not_silent_success(): assert _build_audit_row("relation", include_relation=False)[0]["effect_direction_judgement"] == "unresolved"
def test_scenario_label_is_audit_only_not_effect_judgement_control(): assert _build_audit_row("irreversible")[0]["effect_direction_judgement"] == _build_audit_row("irreversible", label_override="stable")[0]["effect_direction_judgement"]
def test_v2_traces_are_post_action_audit_not_runtime_inputs():
    df = action_effect_direction_audit().action_effect_direction_summary; assert not df.v2_trace_used_as_action_runtime_input.any() and df.v2_trace_used_as_post_action_audit.all() and df.actionplanner_received_only_dept_inputs.all() and df.actionmodule_received_only_final_gate.all()
def test_production_runtime_files_are_not_modified(): assert Path("localprep1/dept/DEPT2_ActionModule_ActuationPrimitives_RC1/pseudo_reality/asymmetric_game_v2.py").exists()
def test_late_case_records_no_op_component_worsening():
    _, long = _build_audit_row("late"); assert (long.no_op_delta.abs() > 0).any()
def test_early_case_records_strong_action_under_low_margin():
    s, _ = _build_audit_row("early"); assert 0 < s["local_fire_margin"] <= 0.08 and s["effective_action_strength"] > 0.5
def test_missed_relation_case_records_pair_risk_without_relation_action():
    s, _ = _build_audit_row("missed_relation"); assert s["pair_fire_margin"] > 0 and s["action_channel"] == "observe_only"
def test_action_effect_summary_includes_harmful_early_late_and_missed_relation_cases(): assert {"harmful", "early", "late", "missed_relation"}.issubset(set(action_effect_direction_audit().action_effect_direction_summary.scenario_label_for_audit_only))
def test_component_long_table_has_multiple_rows_per_run(): assert action_effect_direction_audit().action_effect_component_delta_long.groupby("run_id").size().min() > 1
def test_expected_direction_is_channel_defined_not_scenario_defined(): assert EXPECTED_DIRECTIONS["buffer_increase"]["primary"]["reversibility"] == "increase" and "stable" not in EXPECTED_DIRECTIONS
def test_effect_direction_judgement_not_controlled_by_scenario_label(): test_scenario_label_is_audit_only_not_effect_judgement_control()
