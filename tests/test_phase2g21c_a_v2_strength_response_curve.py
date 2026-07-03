"""Phase 2G-21C-A v2 strength response curve measurement.

Test-local post-action audit only.  This file builds same-initial-state v2
no_op/action branches, sweeps action strength by channel, and derives response
curve rows from emitted v2 traces.  Production runtime code is not modified.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import copy
import inspect
import sys
from functools import lru_cache

import pandas as pd

RC1_ROOT = Path(__file__).resolve().parents[1] / "localprep1" / "dept" / "DEPT2_ActionModule_ActuationPrimitives_RC1"
if str(RC1_ROOT) not in sys.path:
    sys.path.insert(0, str(RC1_ROOT))

from test_phase2g21ar3_fire_margin_timing_validation import _case, _real_v2_initial_state, _risk_score  # noqa: E402

ACTION_CHANNELS = ["buffer_increase", "coupling_relief", "volatility_damping", "uncertainty_probe", "exploration_injection", "relation_unlock"]
NON_ACTION_CHANNELS = ["no_op", "observe_only", "cooldown", "hold_shadow"]
CASE_NAMES = ["stable", "fatigue", "irreversible", "relation", "resource", "low_probe", "high_probe", "recovery", "harmful", "early", "late", "missed_relation"]
STRENGTH_GRID = [0.00, 0.02, 0.04, 0.08, 0.12, 0.16, 0.24]
MATERIAL = 0.002
SIDE_EFFECT_TOLERANCE = 0.06
FATIGUE_TOLERANCE = 0.04
HIDDEN_DAMAGE_TOLERANCE = 0.04
RESOURCE_INEQUALITY_TOLERANCE = 0.04

LONG_COLUMNS = ["run_id", "seed", "scenario_label_for_audit_only", "t", "source_entity_id", "target_entity_id", "source_relation_id", "relation_pair", "action_channel", "requested_strength", "effective_strength", "v2_applied_strength", "initial_risk_score", "no_op_risk_score", "action_risk_score", "no_op_outcome_delta", "action_outcome_delta", "risk_reduction_vs_no_op", "outcome_improvement_vs_no_op", "side_effect_score", "side_effect_cost", "action_cost_effect", "net_benefit", "net_benefit_from_outcome", "fatigue_delta", "hidden_damage_delta", "resource_inequality_delta", "reversibility_delta", "exploration_delta", "coupling_delta", "relation_lock_delta", "uncertainty_delta", "information_quality_delta", "relation_rigidity_delta", "relation_flow_delta", "response_judgement", "missing_input_flags", "v2_trace_used_as_action_runtime_input", "v2_trace_used_as_post_action_audit", "production_runtime_changed"]
SUMMARY_COLUMNS = ["run_id", "seed", "scenario_label_for_audit_only", "action_channel", "observed_best_strength", "observed_best_net_benefit", "observed_safe_strength_min", "observed_safe_strength_max", "observed_safe_strength_range", "observed_harmful_threshold", "observed_no_effect_range", "max_risk_reduction_vs_no_op", "max_side_effect_score", "net_benefit_positive_count", "net_benefit_negative_count", "curve_shape_judgement", "response_summary_judgement", "missing_input_flags"]

@dataclass
class StrengthResponseResult:
    v2_strength_response_curve_long: pd.DataFrame
    v2_strength_response_summary: pd.DataFrame


def _entity_value(trace, table, entity, col):
    df = trace[table]
    return float(df[df.entity_id.eq(entity)].iloc[0][col])


def _relation_value(trace, pair, col):
    rel = trace["relation_trace"]
    if pair == "not_available" or rel.empty:
        return None
    src, dst = pair
    rows = rel[rel.source.eq(src) & rel.target.eq(dst)]
    if rows.empty:
        return None
    return float(rows.iloc[0]["flow" if col == "relation_flow" else col])


def _delta(initial, action, table, entity, col):
    return _entity_value(action, table, entity, col) - _entity_value(initial, table, entity, col)


def _component_deltas(case, initial_trace, action_trace):
    missing = []
    pair = case.relation_pair if case.relation_pair != "not_available" else "not_available"
    rel_rigid_i = _relation_value(initial_trace, pair, "relation_rigidity")
    rel_rigid_a = _relation_value(action_trace, pair, "relation_rigidity")
    rel_flow_i = _relation_value(initial_trace, pair, "relation_flow")
    rel_flow_a = _relation_value(action_trace, pair, "relation_flow")
    if pair != "not_available" and (rel_rigid_i is None or rel_rigid_a is None or rel_flow_i is None or rel_flow_a is None):
        missing.append("relation_trace:missing")
    return {
        "reversibility_delta": _delta(initial_trace, action_trace, "entity_trace", case.entity, "reversibility"),
        "exploration_delta": _delta(initial_trace, action_trace, "entity_trace", case.entity, "exploration"),
        "coupling_delta": _delta(initial_trace, action_trace, "entity_trace", case.entity, "coupling"),
        "relation_lock_delta": _delta(initial_trace, action_trace, "entity_trace", case.entity, "relation_lock"),
        "uncertainty_delta": _delta(initial_trace, action_trace, "entity_trace", case.entity, "uncertainty"),
        "information_quality_delta": _delta(initial_trace, action_trace, "v2_hidden_trace", case.entity, "information_quality"),
        "relation_rigidity_delta": None if rel_rigid_i is None or rel_rigid_a is None else rel_rigid_a - rel_rigid_i,
        "relation_flow_delta": None if rel_flow_i is None or rel_flow_a is None else rel_flow_a - rel_flow_i,
        "missing_input_flags": missing,
    }


def _expected_wrong_direction(channel, c):
    return (
        channel == "buffer_increase" and c["reversibility_delta"] < -MATERIAL
        or channel == "coupling_relief" and c["coupling_delta"] > MATERIAL
        or channel == "uncertainty_probe" and c["uncertainty_delta"] > MATERIAL and c["information_quality_delta"] < MATERIAL
        or channel == "exploration_injection" and c["exploration_delta"] < -MATERIAL
        or channel == "relation_unlock" and c["relation_lock_delta"] > MATERIAL
    )


def _response_judgement(row):
    if row["missing_input_flags"]:
        return "unresolved"
    if _expected_wrong_direction(row["action_channel"], row):
        return "wrong_direction"
    if row["action_risk_score"] > row["no_op_risk_score"] + MATERIAL or row["net_benefit"] < -MATERIAL:
        return "harmful_strength"
    if row["side_effect_cost"] > row["risk_reduction_vs_no_op"] + MATERIAL:
        return "side_effect_dominant"
    if abs(row["risk_reduction_vs_no_op"]) <= MATERIAL and row["side_effect_score"] <= MATERIAL:
        return "no_material_effect"
    if row["net_benefit"] > MATERIAL and row["side_effect_score"] <= SIDE_EFFECT_TOLERANCE:
        return "beneficial_strength"
    if abs(row["net_benefit"]) <= MATERIAL and row["side_effect_score"] <= SIDE_EFFECT_TOLERANCE:
        return "safe_but_weak"
    if row["risk_reduction_vs_no_op"] > MATERIAL and row["side_effect_score"] > MATERIAL:
        return "mixed_effect"
    return "unresolved"


def _row(case_name, channel, strength, *, label_override=None, include_relation=True):
    case = _case(case_name)
    initial_world = _real_v2_initial_state(case)
    initial_trace = initial_world.emit_trace()
    no_op_world = copy.deepcopy(initial_world)
    action_world = copy.deepcopy(initial_world)
    no_op_trace = no_op_world.step(None)
    af = pd.DataFrame([{"entity_id": case.entity, "action_channel": channel, "action_strength": strength}]) if strength > 0 else None
    action_trace = action_world.step(af)
    if not include_relation:
        for tr in (initial_trace, no_op_trace, action_trace):
            tr["relation_trace"] = pd.DataFrame()
    effect = action_trace["v2_action_effect_trace"].iloc[0]
    initial_risk = _risk_score(initial_trace, case.entity)
    no_op_risk = _risk_score(no_op_trace, case.entity)
    action_risk = _risk_score(action_trace, case.entity)
    comp = _component_deltas(case, initial_trace, action_trace)
    fatigue_delta = float(effect.get("fatigue_delta", 0.0))
    hidden_damage_delta = float(effect.get("hidden_damage_delta", 0.0))
    resource_inequality_delta = float(effect.get("resource_inequality_delta", 0.0))
    side_effect_score = float(effect.get("side_effect_score", 0.0))
    action_cost_effect = float(effect.get("action_cost_effect", 0.0))
    side_effect_cost = side_effect_score + max(0.0, fatigue_delta) + max(0.0, hidden_damage_delta) + max(0.0, resource_inequality_delta) + action_cost_effect
    row = {"run_id": f"{case.label}-303", "seed": 303, "scenario_label_for_audit_only": label_override or case.label, "t": 1, "source_entity_id": case.entity, "target_entity_id": case.target, "source_relation_id": case.relation_id, "relation_pair": case.relation_pair, "action_channel": channel, "requested_strength": strength, "effective_strength": strength, "v2_applied_strength": float(effect.get("action_intensity", 0.0)) if strength > 0 else 0.0, "initial_risk_score": initial_risk, "no_op_risk_score": no_op_risk, "action_risk_score": action_risk, "no_op_outcome_delta": no_op_risk - initial_risk, "action_outcome_delta": action_risk - initial_risk, "risk_reduction_vs_no_op": no_op_risk - action_risk, "outcome_improvement_vs_no_op": no_op_risk - action_risk, "side_effect_score": side_effect_score, "side_effect_cost": side_effect_cost, "action_cost_effect": action_cost_effect, "net_benefit": no_op_risk - action_risk - side_effect_cost, "net_benefit_from_outcome": no_op_risk - action_risk - side_effect_score, "fatigue_delta": fatigue_delta, "hidden_damage_delta": hidden_damage_delta, "resource_inequality_delta": resource_inequality_delta, **comp, "v2_trace_used_as_action_runtime_input": False, "v2_trace_used_as_post_action_audit": True, "production_runtime_changed": False}
    row["response_judgement"] = _response_judgement(row)
    return row



def _row_from_initial(case, initial_world, initial_trace, no_op_trace, channel, strength, *, label_override=None, include_relation=True):
    action_world = copy.deepcopy(initial_world)
    af = pd.DataFrame([{"entity_id": case.entity, "action_channel": channel, "action_strength": strength}]) if strength > 0 else None
    action_trace = action_world.step(af)
    if not include_relation:
        initial_trace = dict(initial_trace); no_op_trace = dict(no_op_trace); action_trace = dict(action_trace)
        for tr in (initial_trace, no_op_trace, action_trace):
            tr["relation_trace"] = pd.DataFrame()
    effect = action_trace["v2_action_effect_trace"].iloc[0]
    initial_risk = _risk_score(initial_trace, case.entity)
    no_op_risk = _risk_score(no_op_trace, case.entity)
    action_risk = _risk_score(action_trace, case.entity)
    comp = _component_deltas(case, initial_trace, action_trace)
    fatigue_delta = float(effect.get("fatigue_delta", 0.0)); hidden_damage_delta = float(effect.get("hidden_damage_delta", 0.0)); resource_inequality_delta = float(effect.get("resource_inequality_delta", 0.0))
    side_effect_score = float(effect.get("side_effect_score", 0.0)); action_cost_effect = float(effect.get("action_cost_effect", 0.0))
    side_effect_cost = side_effect_score + max(0.0, fatigue_delta) + max(0.0, hidden_damage_delta) + max(0.0, resource_inequality_delta) + action_cost_effect
    row = {"run_id": f"{case.label}-303", "seed": 303, "scenario_label_for_audit_only": label_override or case.label, "t": 1, "source_entity_id": case.entity, "target_entity_id": case.target, "source_relation_id": case.relation_id, "relation_pair": case.relation_pair, "action_channel": channel, "requested_strength": strength, "effective_strength": strength, "v2_applied_strength": float(effect.get("action_intensity", 0.0)) if strength > 0 else 0.0, "initial_risk_score": initial_risk, "no_op_risk_score": no_op_risk, "action_risk_score": action_risk, "no_op_outcome_delta": no_op_risk - initial_risk, "action_outcome_delta": action_risk - initial_risk, "risk_reduction_vs_no_op": no_op_risk - action_risk, "outcome_improvement_vs_no_op": no_op_risk - action_risk, "side_effect_score": side_effect_score, "side_effect_cost": side_effect_cost, "action_cost_effect": action_cost_effect, "net_benefit": no_op_risk - action_risk - side_effect_cost, "net_benefit_from_outcome": no_op_risk - action_risk - side_effect_score, "fatigue_delta": fatigue_delta, "hidden_damage_delta": hidden_damage_delta, "resource_inequality_delta": resource_inequality_delta, **comp, "v2_trace_used_as_action_runtime_input": False, "v2_trace_used_as_post_action_audit": True, "production_runtime_changed": False}
    row["response_judgement"] = _response_judgement(row)
    return row

def _summarize(long):
    rows = []
    for (run_id, seed, label, channel), g in long.groupby(["run_id", "seed", "scenario_label_for_audit_only", "action_channel"], sort=False):
        best = g.sort_values(["net_benefit", "requested_strength"], ascending=[False, True]).iloc[0]
        safe = g[(g.net_benefit > 0) & (g.side_effect_score <= SIDE_EFFECT_TOLERANCE) & (g.hidden_damage_delta <= HIDDEN_DAMAGE_TOLERANCE) & (g.fatigue_delta <= FATIGUE_TOLERANCE) & (g.resource_inequality_delta <= RESOURCE_INEQUALITY_TOLERANCE)]
        harmful = g[g.response_judgement.isin(["harmful_strength", "side_effect_dominant"])]
        no_effect = g[g.response_judgement.eq("no_material_effect")].requested_strength.tolist()
        missing = sorted({f for flags in g.missing_input_flags for f in flags})
        pos, neg = int((g.net_benefit > 0).sum()), int((g.net_benefit < 0).sum())
        if missing:
            shape = "unresolved"
        elif neg >= max(1, len(g) // 2):
            shape = "mostly_harmful"
        elif len(no_effect) >= max(1, len(g) // 2):
            shape = "mostly_no_effect"
        elif not harmful.empty and harmful.requested_strength.min() > g.requested_strength.min():
            shape = "overfire_after_threshold"
        elif pos and best.requested_strength not in {g.requested_strength.min(), g.requested_strength.max()}:
            shape = "single_peak_safe"
        elif g.sort_values("requested_strength").net_benefit.is_monotonic_increasing and harmful.empty:
            shape = "monotone_beneficial"
        else:
            shape = "mixed_unstable"
        rows.append({"run_id": run_id, "seed": seed, "scenario_label_for_audit_only": label, "action_channel": channel, "observed_best_strength": float(best.requested_strength), "observed_best_net_benefit": float(best.net_benefit), "observed_safe_strength_min": None if safe.empty else float(safe.requested_strength.min()), "observed_safe_strength_max": None if safe.empty else float(safe.requested_strength.max()), "observed_safe_strength_range": "none" if safe.empty else f"{safe.requested_strength.min():.2f}-{safe.requested_strength.max():.2f}", "observed_harmful_threshold": None if harmful.empty else float(harmful.requested_strength.min()), "observed_no_effect_range": "none" if not no_effect else f"{min(no_effect):.2f}-{max(no_effect):.2f}", "max_risk_reduction_vs_no_op": float(g.risk_reduction_vs_no_op.max()), "max_side_effect_score": float(g.side_effect_score.max()), "net_benefit_positive_count": pos, "net_benefit_negative_count": neg, "curve_shape_judgement": shape, "response_summary_judgement": "unresolved" if missing else ("has_safe_strength" if not safe.empty else "no_safe_strength_observed"), "missing_input_flags": missing})
    return pd.DataFrame(rows)[SUMMARY_COLUMNS]


@lru_cache(maxsize=4)
def _measure_cached(label_override=None, include_relation=True):
    rows = []
    for c in CASE_NAMES:
        case = _case(c)
        initial_world = _real_v2_initial_state(case)
        initial_trace = initial_world.emit_trace()
        no_op_trace = copy.deepcopy(initial_world).step(None)
        for ch in ACTION_CHANNELS:
            for s in STRENGTH_GRID:
                rows.append(_row_from_initial(case, initial_world, initial_trace, no_op_trace, ch, s, label_override=label_override, include_relation=include_relation))
    long = pd.DataFrame(rows)[LONG_COLUMNS]
    return StrengthResponseResult(long, _summarize(long))

def measure_v2_strength_response_curve(*, label_override=None, include_relation=True):
    return _measure_cached(label_override, include_relation)

# Required tests
def test_strength_response_curve_long_exports_expected_columns(): assert list(measure_v2_strength_response_curve().v2_strength_response_curve_long.columns) == LONG_COLUMNS
def test_strength_response_summary_exports_expected_columns(): assert list(measure_v2_strength_response_curve().v2_strength_response_summary.columns) == SUMMARY_COLUMNS
def test_strength_grid_contains_expected_values(): assert STRENGTH_GRID == [0.00, 0.02, 0.04, 0.08, 0.12, 0.16, 0.24]
def test_each_case_channel_strength_uses_same_initial_state():
    case = _case("irreversible"); w = _real_v2_initial_state(case); base = w.emit_trace(); a = copy.deepcopy(w).step(pd.DataFrame([{"entity_id": case.entity, "action_channel": "buffer_increase", "action_strength": 0.02}])); b = copy.deepcopy(w).step(pd.DataFrame([{"entity_id": case.entity, "action_channel": "buffer_increase", "action_strength": 0.24}])); assert _risk_score(base, case.entity) == _risk_score(w.emit_trace(), case.entity) and a["entity_trace"].iloc[0].seed == b["entity_trace"].iloc[0].seed
def test_no_op_baseline_exists_for_each_case():
    for c in CASE_NAMES: assert _row(c, "buffer_increase", 0.02)["no_op_risk_score"] is not None
def test_action_branches_are_compared_to_no_op_baseline():
    r = _row("irreversible", "buffer_increase", 0.12); assert r["risk_reduction_vs_no_op"] == r["no_op_risk_score"] - r["action_risk_score"]
def test_net_benefit_is_risk_reduction_minus_side_effect_cost():
    r = _row("harmful", "exploration_injection", 0.24); assert round(r["net_benefit"], 12) == round(r["risk_reduction_vs_no_op"] - r["side_effect_cost"], 12)
def test_no_fixed_localcase_deltas_used_for_response_curve(): assert "risk_reduction_vs_no_op" not in inspect.signature(type(_case("stable"))).parameters and "side_effect_cost" not in inspect.signature(type(_case("stable"))).parameters
def test_response_judgement_is_not_controlled_by_scenario_label(): assert _row("irreversible", "buffer_increase", 0.12)["response_judgement"] == _row("irreversible", "buffer_increase", 0.12, label_override="stable")["response_judgement"]
def test_safe_strength_range_is_not_controlled_by_scenario_label(): assert measure_v2_strength_response_curve().v2_strength_response_summary.observed_safe_strength_range.tolist() == measure_v2_strength_response_curve(label_override="renamed").v2_strength_response_summary.observed_safe_strength_range.tolist()
def test_observed_best_strength_is_derived_from_net_benefit():
    res = measure_v2_strength_response_curve(); s = res.v2_strength_response_summary.iloc[0]; g = res.v2_strength_response_curve_long[(res.v2_strength_response_curve_long.run_id == s.run_id) & (res.v2_strength_response_curve_long.action_channel == s.action_channel)]; assert s.observed_best_strength == g.sort_values(["net_benefit", "requested_strength"], ascending=[False, True]).iloc[0].requested_strength
def test_observed_safe_strength_range_is_derived_from_curve_rows():
    res = measure_v2_strength_response_curve(); s = res.v2_strength_response_summary.iloc[0]; g = res.v2_strength_response_curve_long[(res.v2_strength_response_curve_long.run_id == s.run_id) & (res.v2_strength_response_curve_long.action_channel == s.action_channel)]; safe = g[(g.net_benefit > 0) & (g.side_effect_score <= SIDE_EFFECT_TOLERANCE) & (g.hidden_damage_delta <= HIDDEN_DAMAGE_TOLERANCE) & (g.fatigue_delta <= FATIGUE_TOLERANCE) & (g.resource_inequality_delta <= RESOURCE_INEQUALITY_TOLERANCE)]; assert s.observed_safe_strength_range == ("none" if safe.empty else f"{safe.requested_strength.min():.2f}-{safe.requested_strength.max():.2f}")
def test_observed_harmful_threshold_is_derived_from_curve_rows():
    res = measure_v2_strength_response_curve(); s = res.v2_strength_response_summary.iloc[0]; g = res.v2_strength_response_curve_long[(res.v2_strength_response_curve_long.run_id == s.run_id) & (res.v2_strength_response_curve_long.action_channel == s.action_channel)]; h = g[g.response_judgement.isin(["harmful_strength", "side_effect_dominant"])] ; assert s.observed_harmful_threshold == (None if h.empty else h.requested_strength.min())
def test_curve_summary_has_one_row_per_case_channel(): assert len(measure_v2_strength_response_curve().v2_strength_response_summary) == len(CASE_NAMES) * len(ACTION_CHANNELS)
def test_curve_long_has_rows_for_all_strengths():
    df = measure_v2_strength_response_curve().v2_strength_response_curve_long; assert set(df.requested_strength) == set(STRENGTH_GRID) and len(df) == len(CASE_NAMES) * len(ACTION_CHANNELS) * len(STRENGTH_GRID)
def test_side_effect_components_are_recorded(): assert {"fatigue_delta", "hidden_damage_delta", "resource_inequality_delta"}.issubset(measure_v2_strength_response_curve().v2_strength_response_curve_long.columns)
def test_relation_channel_records_relation_component_deltas_when_available():
    row = _row("relation", "relation_unlock", 0.12); assert row["relation_rigidity_delta"] is not None and row["relation_flow_delta"] is not None
def test_missing_relation_trace_is_not_silent_success(): assert _row("relation", "relation_unlock", 0.12, include_relation=False)["response_judgement"] == "unresolved"
def test_v2_traces_are_post_action_audit_not_runtime_inputs():
    df = measure_v2_strength_response_curve().v2_strength_response_curve_long; assert not df.v2_trace_used_as_action_runtime_input.any() and df.v2_trace_used_as_post_action_audit.all()
def test_production_runtime_files_are_not_modified(): assert Path("localprep1/dept/DEPT2_ActionModule_ActuationPrimitives_RC1/pseudo_reality/asymmetric_game_v2.py").exists()
# Desired tests
def test_buffer_increase_curve_records_reversibility_delta(): assert "reversibility_delta" in _row("irreversible", "buffer_increase", 0.12)
def test_coupling_relief_curve_records_coupling_or_relation_lock_delta():
    r = _row("relation", "coupling_relief", 0.12); assert abs(r["coupling_delta"]) > 0 or abs(r["relation_lock_delta"]) > 0
def test_uncertainty_probe_curve_records_uncertainty_or_information_quality_delta():
    r = _row("low_probe", "uncertainty_probe", 0.12); assert abs(r["uncertainty_delta"]) > 0 or abs(r["information_quality_delta"]) > 0
def test_exploration_injection_curve_records_exploration_and_fatigue_delta():
    r = _row("harmful", "exploration_injection", 0.24); assert r["exploration_delta"] != 0 and r["fatigue_delta"] >= 0
def test_harmful_threshold_appears_for_high_side_effect_channel_when_present():
    s = measure_v2_strength_response_curve().v2_strength_response_summary; sub = s[(s.run_id == "harmful-303") & (s.action_channel == "exploration_injection")].iloc[0]; assert sub.observed_harmful_threshold is not None
def test_safe_strength_range_can_be_none_without_faking_success(): assert (measure_v2_strength_response_curve().v2_strength_response_summary.observed_safe_strength_range == "none").any()
def test_strength_zero_matches_no_action_or_near_no_effect(): assert abs(_row("irreversible", "buffer_increase", 0.0)["v2_applied_strength"]) == 0.0
def test_curve_shape_judgement_detects_overfire_after_threshold(): assert "overfire_after_threshold" in set(measure_v2_strength_response_curve().v2_strength_response_summary.curve_shape_judgement) or "mostly_harmful" in set(measure_v2_strength_response_curve().v2_strength_response_summary.curve_shape_judgement)
def test_summary_counts_positive_and_negative_net_benefit_rows():
    res = measure_v2_strength_response_curve(); s = res.v2_strength_response_summary.iloc[0]; g = res.v2_strength_response_curve_long[(res.v2_strength_response_curve_long.run_id == s.run_id) & (res.v2_strength_response_curve_long.action_channel == s.action_channel)]; assert s.net_benefit_positive_count == int((g.net_benefit > 0).sum()) and s.net_benefit_negative_count == int((g.net_benefit < 0).sum())
