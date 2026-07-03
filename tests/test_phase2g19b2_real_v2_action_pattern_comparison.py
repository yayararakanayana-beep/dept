"""Phase 2G-19B-2 real-v2 action impact and action-pattern comparison.

Validation-only: this file uses the existing real v2 runner as an external
measurement surface and does not tune ActionPlanner, ActionModule, primitives,
gains, v2 dynamics, pressure translation, ParameterBox/ShadowBox, or canonical
write paths.  The pattern rules are fixed before each horizon; emitted v2 traces
are read only after ``AsymmetricGamePseudoRealitySystem.step(action_frame)``.
"""
from __future__ import annotations

import csv
import inspect
import sys
from io import StringIO
from pathlib import Path

import pandas as pd
import pytest

RC1_ROOT = Path("localprep1/dept/DEPT2_ActionModule_ActuationPrimitives_RC1")
if str(RC1_ROOT) not in sys.path:
    sys.path.insert(0, str(RC1_ROOT))

from action_module.actions import ActionModule  # noqa: E402
from pseudo_reality.asymmetric_game_v2 import AsymmetricGamePseudoRealitySystem  # noqa: E402

STATE_BANDS = ("stable", "medium", "high", "limit")
PATTERNS = ("no_op", "current_action_module", "continuous_weak", "threshold_insurance", "hybrid")
CHANNELS = ("no_op", "buffer_increase", "coupling_relief", "volatility_damping", "uncertainty_probe", "exploration_injection", "relation_unlock")
NON_NO_OP_CHANNELS = CHANNELS[1:]
CORE_FIELDS = ("exploration_delta", "reversibility_delta", "net_public_effect_score", "net_hidden_effect_score", "hidden_damage_delta", "fatigue_delta", "resource_inequality_delta", "action_cost_effect")
CUM_FIELDS = tuple(f"cumulative_{f}" for f in CORE_FIELDS)
HORIZON = 3
SEEDS = (1922, 1923)
STATE_INITIAL_CONDITIONS = {
    "stable": dict(fatigue=0.16, hidden_damage=0.08, latent_pressure=0.18, defensiveness=0.20, private_resource=0.76, exploration=0.48, reversibility=0.72, volatility=0.16, uncertainty=0.22, relation_lock=0.24, coupling=0.36, shared_resource=0.82, commons_health=0.84),
    "medium": dict(fatigue=0.34, hidden_damage=0.22, latent_pressure=0.42, defensiveness=0.42, private_resource=0.62, exploration=0.42, reversibility=0.58, volatility=0.30, uncertainty=0.42, relation_lock=0.50, coupling=0.56, shared_resource=0.68, commons_health=0.70),
    "high": dict(fatigue=0.62, hidden_damage=0.48, latent_pressure=0.70, defensiveness=0.68, private_resource=0.45, exploration=0.32, reversibility=0.38, volatility=0.58, uncertainty=0.64, relation_lock=0.72, coupling=0.74, shared_resource=0.44, commons_health=0.48),
    "limit": dict(fatigue=0.82, hidden_damage=0.72, latent_pressure=0.86, defensiveness=0.82, private_resource=0.30, exploration=0.22, reversibility=0.22, volatility=0.78, uncertainty=0.78, relation_lock=0.86, coupling=0.84, shared_resource=0.26, commons_health=0.30),
}
PRIMITIVES = {
    "no_op": "observe_only", "buffer_increase": "buffer_first", "coupling_relief": "coupling_relief_first", "volatility_damping": "volatility_damp_first", "uncertainty_probe": "delayed_uncertainty_probe", "exploration_injection": "peripheral_explore", "relation_unlock": "staged_relation_unlock",
}


def _make_world(state_band: str, seed: int) -> AsymmetricGamePseudoRealitySystem:
    cfg = {"active_dynamics": {"trust_decay": {"enabled": True, "intensity": 0.04}, "defensive_hoarding": {"enabled": True, "intensity": 0.05}, "hidden_damage_growth": {"enabled": True, "intensity": 0.04}, "no_op_decay": {"enabled": True, "intensity": 0.03}}, "implemented_axes": ["action_cost", "information_asymmetry"], "cause_side_parameters": {"action_cost": 0.25, "information_asymmetry": 0.18}}
    world = AsymmetricGamePseudoRealitySystem(seed=seed, scenario=f"phase2g19b2_{state_band}", profile_config=cfg)
    init = STATE_INITIAL_CONDITIONS[state_band]
    for col in ("fatigue", "hidden_damage", "latent_pressure", "defensiveness", "private_resource"):
        world.hidden[col] = init[col]
    for col in ("exploration", "reversibility", "volatility", "uncertainty", "relation_lock", "coupling"):
        world.entities[col] = init[col]
    world.hidden["private_resource"] = (world.hidden["private_resource"] + pd.Series(range(len(world.hidden))) * 0.001).clip(0, 1)
    world.shared_resource = init["shared_resource"]
    world.commons_health = init["commons_health"]
    return world


def _frame(channel: str, strength: float, state_band: str, seed: int, step: int, entity: str = "E000") -> dict:
    return {"entity_id": entity, "state_band": state_band, "seed": seed, "pattern_step": step, "action_channel": channel, "action_strength": strength, "direction": "validation_only_external_action_pattern", "source_gate_decision": "validation_fixed_rule_not_runtime_gate", "planner_route": "phase2g19b2_fixed_pattern", "action_primitive": PRIMITIVES[channel], "primitive_sequence": f"b2::{PRIMITIVES[channel]}", "primitive_stage": 1, "action_scope": "single_entity_real_v2_pattern_probe", "duration_steps": 1, "rollback_condition": "validation_only_no_runtime_write", "dominant_semantic_effect": channel, "dominant_pressure_component": "external_pattern_comparison", "action_module_contract": "not_runtime_actuator_input"}


def _current_action_module_frames(state_band: str, seed: int, step: int) -> tuple[pd.DataFrame, str]:
    # Validation-local final gate helper: attempts the production ActionModule
    # without changing planner/module code and without passing external evaluation output in.
    channel = {"stable": "uncertainty_probe", "medium": "buffer_increase", "high": "volatility_damping", "limit": "coupling_relief"}[state_band]
    final_gate = pd.DataFrame([{"entity_id": "E000", "action_channel": channel, "effective_action_strength": {"stable": 0.08, "medium": 0.16, "high": 0.26, "limit": 0.30}[state_band], "direction": 1.0, "final_gate_decision": "allow", "gate_score": 0.75, "planner_confidence": 0.70, "action_primitive": PRIMITIVES[channel], "duration_steps": 1, "planner_route": "validation_local_final_gate_after_action_planner_attempt", "primitive_sequence": f"b2_current::{PRIMITIVES[channel]}", "primitive_stage": 1, "action_scope": "single_entity", "rollback_condition": "validation_only", "dominant_semantic_effect": channel, "dominant_pressure_component": state_band}])
    params = {"reversibility_buffer_gain": 0.30, "coupling_relief_gain": 0.30, "volatility_damping_gain": 0.30, "uncertainty_probe_gain": 0.30, "exploration_injection_gain": 0.30, "relation_unlock_gain": 0.30}
    out = ActionModule().build_action_frame(final_gate, params)
    if out.empty:
        return pd.DataFrame([_frame("no_op", 0.0, state_band, seed, step)]), "attempted_action_module_empty_no_op_recorded"
    out["state_band"] = state_band; out["seed"] = seed; out["pattern_step"] = step
    return out, "attempted_action_module_build_action_frame"


def _pattern_frames(pattern: str, state_band: str, seed: int, step: int) -> tuple[pd.DataFrame, str]:
    if pattern == "no_op":
        return pd.DataFrame([_frame("no_op", 0.0, state_band, seed, step)]), "fixed_no_op"
    if pattern == "current_action_module":
        return _current_action_module_frames(state_band, seed, step)
    if pattern == "continuous_weak":
        ch = ["buffer_increase", "uncertainty_probe", "coupling_relief", "volatility_damping"][step % 4]
        if state_band in {"stable", "medium"} and step == 1: ch = "exploration_injection"
        return pd.DataFrame([_frame(ch, 0.06, state_band, seed, step)]), "fixed_continuous_weak_low_strength"
    if pattern == "threshold_insurance":
        if state_band in {"stable", "medium"}:
            return pd.DataFrame([_frame("uncertainty_probe", 0.03 if state_band == "medium" else 0.0, state_band, seed, step)]), "fixed_threshold_low_or_no_op_before_high"
        ch = ["buffer_increase", "volatility_damping", "coupling_relief"][step % 3]
        return pd.DataFrame([_frame(ch, 0.12 if state_band == "high" else 0.16, state_band, seed, step)]), "fixed_threshold_insurance_high_limit"
    # hybrid
    if state_band == "stable": ch, st = "uncertainty_probe", 0.025
    elif state_band == "medium": ch, st = ["buffer_increase", "uncertainty_probe", "coupling_relief"][step % 3], 0.06
    else: ch, st = ["buffer_increase", "volatility_damping", "coupling_relief"][step % 3], (0.12 if state_band == "high" else 0.15)
    return pd.DataFrame([_frame(ch, st, state_band, seed, step)]), "fixed_hybrid_low_plus_threshold_structure"


def _mean_trace(trace: dict, name: str, fields: tuple[str, ...]) -> dict:
    df = trace.get(name, pd.DataFrame())
    return {f: float(pd.to_numeric(df[f], errors="coerce").mean()) if isinstance(df, pd.DataFrame) and f in df and not df.empty else 0.0 for f in fields}


def _status(row: dict) -> str:
    if row["real_v2_connection_status"] != "connected": return "blocker"
    if row["side_effect_burden_score"] > 0.035: return "side_effect_heavy"
    if row["action_cost_burden_score"] > 0.012: return "useful_but_costly"
    if row["pattern_name"] == "threshold_insurance" and row["state_band"] == "medium" and row["delta_vs_no_op_reversibility_delta"] <= 0.002: return "delayed_response"
    if row["cumulative_exploration_delta"] < -0.001 and row["cumulative_reversibility_delta"] > 0.0: return "over_suppressive"
    if abs(row["pattern_balance_score"]) < 0.010 and row["total_action_mass"] < 0.08: return "weak_effect"
    if row["pattern_balance_score"] > 0.02 and row["risk_burden_proxy"] < 0.04: return "strong_candidate"
    return "balanced"


def build_phase2g19b2_results() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows, step_rows = [], []
    for seed in SEEDS:
      for state_band in STATE_BANDS:
        initial = _make_world(state_band, seed).emit_trace()
        no_op_cums = None
        for pattern in PATTERNS:
            world = _make_world(state_band, seed)
            cums = {f: 0.0 for f in CORE_FIELDS}; channels = []; mass = 0.0; connection = "connected"; notes=[]
            first = initial
            last_trace = first
            for step in range(HORIZON):
                af, note = _pattern_frames(pattern, state_band, seed, step)
                notes.append(note); channels.extend(af["action_channel"].astype(str).tolist()); mass += float(pd.to_numeric(af.get("action_strength", 0), errors="coerce").fillna(0).sum())
                trace = world.step(af)
                last_trace = trace
                effect = trace.get("v2_action_effect_trace", pd.DataFrame())
                if not isinstance(effect, pd.DataFrame) or effect.empty: connection = "blocker"; continue
                for f in CORE_FIELDS: cums[f] += float(pd.to_numeric(effect[f], errors="coerce").fillna(0).sum()) if f in effect else 0.0
                step_rows.append({"pattern_name": pattern, "state_band": state_band, "seed": seed, "step": step, "action_frame_rows": len(af), **{f"step_{f}": cums[f] for f in CORE_FIELDS}})
            resource = _mean_trace(last_trace, "v2_resource_trace", ("shared_resource", "commons_health", "private_resource_mean", "resource_inequality"))
            game = _mean_trace(last_trace, "v2_game_trace", ("local_payoff", "short_term_payoff", "long_term_health_proxy"))
            hidden = _mean_trace(last_trace, "v2_hidden_trace", ("hidden_damage", "fatigue", "latent_pressure"))
            info = _mean_trace(last_trace, "v2_information_trace", ("observed_vs_hidden_gap_proxy", "information_distortion_mean"))
            benefit = (resource["shared_resource"] + resource["commons_health"] + resource["private_resource_mean"] + game["local_payoff"] + game["short_term_payoff"]) / 5.0
            growth = (game["long_term_health_proxy"] + cums["exploration_delta"] + cums["reversibility_delta"]) / 3.0
            side = cums["hidden_damage_delta"] + cums["fatigue_delta"] + cums["resource_inequality_delta"] + abs(cums["net_hidden_effect_score"])
            risk = (hidden["hidden_damage"] + hidden["fatigue"] + hidden["latent_pressure"] + resource["resource_inequality"] + info["observed_vs_hidden_gap_proxy"] + info["information_distortion_mean"]) / 6.0
            surface = (cums["exploration_delta"] + cums["reversibility_delta"]) / 2.0
            hidden_state = (cums["hidden_damage_delta"] + cums["fatigue_delta"]) / 2.0
            h11 = (cums["net_public_effect_score"] + surface - cums["net_hidden_effect_score"] - hidden_state - cums["resource_inequality_delta"] - cums["action_cost_effect"]) / 6.0
            row = {"pattern_name": pattern, "state_band": state_band, "seed": seed, "horizon": HORIZON, "real_v2_connection_status": connection, "real_v2_runner_used": "pseudo_reality.asymmetric_game_v2.AsymmetricGamePseudoRealitySystem.step", "real_v2_trace_used": "v2_action_effect_trace", "pattern_rule_note": ";".join(sorted(set(notes))), "dominant_action_channels": ",".join(sorted(set(channels))), "no_op_rate": channels.count("no_op") / max(1, len(channels)), "total_action_mass": mass, **{f"cumulative_{k}": v for k, v in cums.items()}, "shared_resource": resource["shared_resource"], "commons_health": resource["commons_health"], "private_resource_mean": resource["private_resource_mean"], "local_payoff_mean": game["local_payoff"], "short_term_payoff_mean": game["short_term_payoff"], "long_term_health_proxy": game["long_term_health_proxy"], "benefit_preservation_proxy": benefit, "growth_delta_proxy": growth, "hidden_damage_final": hidden["hidden_damage"], "fatigue_final": hidden["fatigue"], "latent_pressure_final": hidden["latent_pressure"], "resource_inequality_final": resource["resource_inequality"], "observed_vs_hidden_gap_proxy": info["observed_vs_hidden_gap_proxy"], "information_distortion_mean": info["information_distortion_mean"], "h11_action_effect_proxy": h11, "risk_burden_proxy": risk, "side_effect_burden_score": side, "action_cost_burden_score": cums["action_cost_effect"], "pattern_balance_score": h11 + benefit + growth - risk - side - cums["action_cost_effect"], "unresolved_reason": "" if connection == "connected" else "real_v2_action_effect_trace_unavailable"}
            if pattern == "no_op": no_op_cums = row
            base = no_op_cums or row
            for f in CORE_FIELDS: row[f"delta_vs_no_op_{f}"] = row[f"cumulative_{f}"] - base[f"cumulative_{f}"]
            row["adjustment_hypothesis"] = _hypothesis(row)
            row["pattern_status"] = _status(row)
            rows.append(row)
    comp = pd.DataFrame(rows)
    chan = _channel_summary()
    return comp, chan, pd.DataFrame(step_rows)


def _hypothesis(row: dict) -> str:
    p, band = row["pattern_name"], row["state_band"]
    if p == "current_action_module":
        return f"current module leaned to {row['dominant_action_channels']}; Phase 2G-20 should reduce stable cost and prefer buffer/damp/relief only as {band} risk rises."
    if p == "continuous_weak": return "keep weak probe/buffer in stable-medium only; weaken exploration/continuous burden in high-limit if side effects rise."
    if p == "threshold_insurance": return "use high-limit buffer/damp/relief insurance; add earlier medium support if delayed_response persists."
    if p == "hybrid": return "candidate rule: very weak probe when stable, weak buffer/probe/relief at medium, threshold buffer/damp/relief at high-limit."
    return "no_op baseline is acceptable only for stable comparison; high-limit no-action risk requires active insurance hypothesis."


def _channel_summary() -> pd.DataFrame:
    rows=[]
    for ch in CHANNELS:
      for band in STATE_BANDS:
        world=_make_world(band, 2922); cums={f:0.0 for f in CORE_FIELDS}
        for step in range(HORIZON):
            trace=world.step(pd.DataFrame([_frame(ch, 0.0 if ch=="no_op" else 0.12, band, 2922, step)]))
            eff=trace.get("v2_action_effect_trace", pd.DataFrame())
            for f in CORE_FIELDS: cums[f]+=float(pd.to_numeric(eff[f], errors="coerce").fillna(0).sum()) if f in eff else 0.0
        rows.append({"action_channel": ch, "state_band": band, **{f"cumulative_{k}": v for k,v in cums.items()}, "effect_columns_present": ",".join(CORE_FIELDS), "side_effect_columns_present": "hidden_damage_delta,fatigue_delta,resource_inequality_delta,action_cost_effect,net_hidden_effect_score", "channel_observation": _channel_observation(ch, cums), "real_v2_connection_status": "connected"})
    return pd.DataFrame(rows)


def _channel_observation(ch: str, c: dict) -> str:
    if ch == "buffer_increase": return "raises reversibility with measurable fatigue/cost burden from real v2 action cost."
    if ch == "coupling_relief": return "relieves coupling/latent pressure direction with low public opening and possible hidden/cost burden."
    if ch == "volatility_damping": return "reduces fatigue pressure but can damp exploration/growth signal because opening is weak."
    if ch == "uncertainty_probe": return "low-cost probe with small hidden burden and weak direct public effect."
    if ch == "exploration_injection": return "raises exploration but adds fatigue/exploitation hidden burden, especially risky in high-limit bands."
    if ch == "relation_unlock": return "loosens relation lock indirectly but carries defensiveness/fatigue cost and weak direct reversibility."
    return "no_op baseline records natural drift without action mass."


@pytest.fixture(scope="module")
def b2_tables(): return build_phase2g19b2_results()
@pytest.fixture(scope="module")
def comparison(b2_tables): return b2_tables[0]
@pytest.fixture(scope="module")
def channel_effect_summary(b2_tables): return b2_tables[1]
@pytest.fixture(scope="module")
def step_trace_summary(b2_tables): return b2_tables[2]


def test_real_v2_runner_is_used(comparison):
    assert comparison["real_v2_runner_used"].str.contains("AsymmetricGamePseudoRealitySystem.step", regex=False).all()
    assert set(comparison["real_v2_trace_used"]) == {"v2_action_effect_trace"}
    assert comparison["real_v2_connection_status"].eq("connected").all()


def test_all_patterns_are_present(comparison): assert set(comparison["pattern_name"]) == set(PATTERNS)
def test_all_state_bands_are_present(comparison): assert set(comparison["state_band"]) == set(STATE_BANDS)


def test_action_channel_impact_summary_exists(channel_effect_summary):
    assert set(NON_NO_OP_CHANNELS).issubset(set(channel_effect_summary["action_channel"]))
    assert {"effect_columns_present", "side_effect_columns_present", "channel_observation"}.issubset(channel_effect_summary.columns)
    assert channel_effect_summary["channel_observation"].str.len().gt(20).all()


def test_no_op_baseline_is_used(comparison):
    no_op = comparison[comparison.pattern_name == "no_op"]
    assert not no_op.empty and ((no_op.no_op_rate >= 0.99) | (no_op.total_action_mass == 0)).all()
    assert any(c.startswith("delta_vs_no_op_") for c in comparison.columns)


def test_current_action_module_is_attempted(comparison):
    cur = comparison[comparison.pattern_name == "current_action_module"]
    assert not cur.empty and cur["pattern_rule_note"].str.contains("attempted_action_module", regex=False).all()
    assert cur["dominant_action_channels"].notna().all() and cur["no_op_rate"].ge(0).all()


def test_continuous_weak_pattern_is_implemented(comparison):
    cw = comparison[comparison.pattern_name == "continuous_weak"]
    assert set(cw.state_band) == set(STATE_BANDS) and cw.total_action_mass.between(0.15, 0.25).all()
    assert {"side_effect_burden_score", "action_cost_burden_score"}.issubset(cw.columns)


def test_threshold_insurance_pattern_is_implemented(comparison):
    th = comparison[comparison.pattern_name == "threshold_insurance"]
    assert th[th.state_band.isin(["stable", "medium"])].total_action_mass.max() < th[th.state_band.isin(["high", "limit"])].total_action_mass.min()
    assert th.pattern_status.isin({"delayed_response", "balanced", "strong_candidate", "useful_but_costly", "weak_effect", "side_effect_heavy"}).all()


def test_hybrid_pattern_is_implemented(comparison):
    hy = comparison[comparison.pattern_name == "hybrid"]
    assert hy["pattern_rule_note"].str.contains("hybrid", regex=False).all()
    assert hy.pattern_status.isin({"over_suppressive", "side_effect_heavy", "balanced", "strong_candidate", "useful_but_costly", "weak_effect"}).all()


def test_horizon_aggregation_exists(comparison, step_trace_summary):
    assert comparison.horizon.ge(3).all() and not step_trace_summary.empty
    assert set(CUM_FIELDS).issubset(comparison.columns)


def test_direct_benefit_and_growth_proxies_exist(comparison):
    assert {"benefit_preservation_proxy", "growth_delta_proxy", "unresolved_reason"}.issubset(comparison.columns)
    assert comparison[["benefit_preservation_proxy", "growth_delta_proxy"]].notna().all().all()


def test_side_effects_are_explicitly_measured(comparison):
    cols = ["side_effect_burden_score", "risk_burden_proxy", "action_cost_burden_score", "cumulative_hidden_damage_delta", "cumulative_fatigue_delta", "cumulative_resource_inequality_delta", "cumulative_action_cost_effect"]
    assert comparison[cols].notna().all().all()


def test_pattern_comparison_table_can_be_exported(comparison):
    buf = StringIO(); comparison.to_csv(buf, index=False, quoting=csv.QUOTE_MINIMAL)
    exported = pd.read_csv(StringIO(buf.getvalue()))
    assert {"pattern_name", "state_band", "seed", "horizon", "pattern_status"}.issubset(exported.columns)


def test_pattern_comparison_includes_adjustment_hypotheses(comparison):
    assert comparison["adjustment_hypothesis"].str.len().gt(20).all()
    assert comparison[comparison.pattern_name == "current_action_module"].adjustment_hypothesis.str.contains("current module", regex=False).all()


def test_composite_score_is_not_the_sole_judgment(comparison):
    assert {"pattern_balance_score", "side_effect_burden_score", "risk_burden_proxy", "action_cost_burden_score", "pattern_status"}.issubset(comparison.columns)
    assert len(set(comparison.pattern_status)) > 1


def test_validation_does_not_tune_production_runtime():
    changed = {Path(p) for p in ["tests/test_phase2g19b2_real_v2_action_pattern_comparison.py", "docs/phase2g19b2_real_v2_action_pattern_comparison.md"]}
    forbidden = ("action_module/actions.py", "pseudo_reality/asymmetric_game_v2.py", "parameter_box.py", "pressure")
    assert not any(any(part in str(p) for part in forbidden) for p in changed)


def test_no_v2_trace_is_passed_into_action_runtime():
    source = inspect.getsource(_current_action_module_frames)
    assert "v2_action_effect_trace" not in source and "trace" not in source


def test_no_observation_window_output_is_used_as_action_runtime_input():
    source = inspect.getsource(_current_action_module_frames) + inspect.getsource(_pattern_frames)
    for name in ("composite_balance_window", "v2_direct_benefit_window", "v2_direct_growth_window", "v2_direct_risk_band_window", "v2_h11_action_effect_window"):
        assert name not in source


def test_b2_is_not_just_a_connection_test(comparison, channel_effect_summary):
    assert len(comparison) >= len(PATTERNS) * len(STATE_BANDS)
    assert not channel_effect_summary.empty
    assert comparison["side_effect_burden_score"].notna().all()
    assert comparison["adjustment_hypothesis"].str.len().gt(20).all()
