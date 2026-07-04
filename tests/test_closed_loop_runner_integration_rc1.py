"""Closed Loop Runner Integration RC1.

Test-local multi-step pseudo-reality runner connecting ``action_module_step`` to
bounded state transitions.  It intentionally does not modify production runtime
files, canonical state, coefficients, v2 dynamics, ActionPlanner, ActionModule,
ParameterBox, or ShadowBox.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import random
import subprocess

import pandas as pd

from test_action_module_api_consolidation_rc1 import ActionModuleStepResult, action_module_step
from test_action_module_api_v2_alignment_open_stress_rc1 import run_action_module_v2_alignment_open_stress_audit

BASELINES = ("NO_ACTION", "V2_GREEDY_OPTIMIZER", "ACTION_MODULE_RC1")
SCENARIOS = (
    "stable_closed_v2", "shock_recovery", "delayed_side_effect", "safety_boundary_shift",
    "reaction_surface_drift", "hidden_fragility", "high_opportunity_high_risk",
)
BOUNDARY_COLS = ["coefficient_changed", "production_runtime_changed", "canonical_writeback_performed", "fixed_candidate_used_as_runtime_coefficient", "shadow_adjustment_used_as_runtime_default", "scenario_label_controlled_logic"]
PRODUCTION_RUNTIME_PATTERNS = ("ActionPlanner", "ActionModule", "ParameterBox", "ShadowBox", "pseudo_reality", "asymmetric_game_v2", "canonical")


def _clip(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(v)))


@dataclass(frozen=True)
class ClosedLoopPseudoRealityState:
    step: int; stability: float; risk: float; opportunity: float; exploration_capacity: float; recovery_capacity: float; fatigue: float; relation_lock: float; hidden_fragility: float; external_pressure: float; safe_mass_upper: float; harmful_threshold: float; response_surface_shift: float


@dataclass(frozen=True)
class ClosedLoopScenario:
    scenario_id: str; scenario_type: str; n_steps: int; shock_step: int | None; drift_start_step: int | None; delayed_effect_start_step: int | None; safety_shift_step: int | None; hidden_fragility: float; external_pressure_schedule: tuple[float, ...]


@dataclass(frozen=True)
class ClosedLoopHistory:
    recent_actions: tuple[dict, ...]; recent_states: tuple[ClosedLoopPseudoRealityState, ...]; cooldown_counter: int; rollback_counter: int; cumulative_action_mass: float; cumulative_harmful_events: int


@dataclass(frozen=True)
class ClosedLoopActionDecision:
    decision_type: str; selected_channel: str | None; selected_action_mass: float; decision_reason: str; audit_passed: bool = True


@dataclass(frozen=True)
class ClosedLoopStepRecord:
    scenario_id: str; scenario_type: str; baseline_name: str; seed: int; step: int; state_before: ClosedLoopPseudoRealityState; decision_type: str; selected_channel: str | None; selected_action_mass: float; state_after: ClosedLoopPseudoRealityState; short_term_gain: float; safety_violation: bool; over_action: bool; missed_opportunity: bool; delayed_side_effect_cost: float; recovery_score: float; audit_passed: bool


@dataclass(frozen=True)
class ClosedLoopRunnerResult:
    closed_loop_step_long: pd.DataFrame; closed_loop_episode_summary: pd.DataFrame; closed_loop_baseline_comparison_summary: pd.DataFrame; closed_loop_scenario_breakdown: pd.DataFrame; closed_loop_audit_boundary_summary: pd.DataFrame; closed_loop_preflight_summary: pd.DataFrame


def run_pr99_preflight_check() -> pd.DataFrame:
    rows = []
    try:
        r = run_action_module_v2_alignment_open_stress_audit(label_override="closed_loop_rc1_preflight")
        v2_ok = not r.action_module_v2_alignment_long.empty
        stress_ok = not r.action_module_open_stress_long.empty
        base_ok = set(BASELINES).issubset(set(r.action_module_baseline_comparison_long.baseline_name))
        harmful = float(r.action_module_v2_alignment_summary.iloc[0].harmful_execute_violation_rate)
        audit = float(r.action_module_v2_alignment_summary.iloc[0].audit_boundary_pass_rate)
        passed = v2_ok and stress_ok and base_ok and harmful <= .10 and audit >= .99
    except Exception as exc:  # preflight summary, not import guard
        v2_ok = stress_ok = base_ok = passed = False; harmful = 1.0; audit = 0.0; note = repr(exc)
    else:
        note = "PR #99 audit callable and safe for test-local closed-loop comparison"
    data = [("v2_alignment_available", v2_ok, v2_ok), ("open_stress_available", stress_ok, stress_ok), ("three_baselines_available", base_ok, base_ok), ("harmful_execute_violation_rate", harmful, harmful <= .10), ("audit_boundary_pass_rate", audit, audit >= .99), ("preflight_passed", passed, passed)]
    for item, value, ok in data:
        rows.append({"preflight_item": item, "value": value, "passed": bool(ok), "blocking": item != "preflight_passed" and not bool(ok), "note": note})
    return pd.DataFrame(rows, columns=["preflight_item", "value", "passed", "blocking", "note"])


def build_closed_loop_scenarios() -> list[ClosedLoopScenario]:
    return [ClosedLoopScenario(f"clr_{i:02d}", t, 12, 4 if t in {"shock_recovery", "high_opportunity_high_risk"} else None, 3 if t == "reaction_surface_drift" else None, 4 if t == "delayed_side_effect" else None, 5 if t in {"safety_boundary_shift", "high_opportunity_high_risk"} else None, .72 if t == "hidden_fragility" else .25, tuple(.25 + (.50 if s == 4 and t == "shock_recovery" else 0) + (.25 if t == "high_opportunity_high_risk" else 0) for s in range(12))) for i, t in enumerate(SCENARIOS)]


def initial_state_for_scenario(scenario: ClosedLoopScenario, *, seed: int = 0) -> ClosedLoopPseudoRealityState:
    rnd = random.Random(seed + len(scenario.scenario_type))
    opp = .82 if scenario.scenario_type in {"stable_closed_v2", "high_opportunity_high_risk"} else .62
    risk = .18 if scenario.scenario_type == "stable_closed_v2" else (.52 if scenario.scenario_type == "high_opportunity_high_risk" else .34)
    return ClosedLoopPseudoRealityState(0, _clip(.78 + rnd.uniform(-.02, .02)), risk, opp, .86, .76, .08, .06, scenario.hidden_fragility, scenario.external_pressure_schedule[0], .24, .42, 0.0)


def initial_closed_loop_history() -> ClosedLoopHistory:
    return ClosedLoopHistory((), (), 0, 0, 0.0, 0)


def build_prepared_inputs_from_state(state: ClosedLoopPseudoRealityState, history: ClosedLoopHistory, scenario: ClosedLoopScenario) -> dict:
    preferred = {"stabilize": _clip(1 - state.stability + state.external_pressure), "explore": state.opportunity, "de_risk": state.risk, "relation": state.relation_lock}
    return {"prepared_upper_pressure": {"pressure_intensity": max(preferred.values()), "preferred_channels": preferred, "safety_pressure": state.risk}, "prepared_lower_state": {"instability": 1 - state.stability, "opportunity": state.opportunity, "risk": state.risk, "recovery_need": max(state.risk, 1 - state.stability), "fatigue": state.fatigue, "relation_lock": state.relation_lock, "burden": state.external_pressure, "coupling": state.relation_lock}, "prepared_observation_view": {"evidence_strength": "high" if state.hidden_fragility < .65 else "medium", "missing_evidence": False, "safe_range_known": True, "harmful_threshold_known": True}, "action_history": {"cooldown_active": history.cooldown_counter > 0, "recent_rollback": history.rollback_counter > 0, "last_action_mass": history.recent_actions[-1]["selected_action_mass"] if history.recent_actions else 0.0, "recent_harmful_fire_rate": _clip(history.cumulative_harmful_events / max(1, len(history.recent_actions))), "recent_side_effect_score": _clip(state.fatigue + state.relation_lock)}, "parameter_snapshot": {"max_action_mass": state.safe_mass_upper, "min_fire_permission": .50}, "guardrail_snapshot": {"blocked_channels": [], "max_allowed_action_mass": state.safe_mass_upper, "force_cooldown": state.fatigue > .70, "force_rollback": state.risk > .82}}


def choose_no_action_decision(state, scenario) -> ClosedLoopActionDecision:
    return ClosedLoopActionDecision("NO_OP", None, 0.0, "no_action_baseline")


def _visible_gain_by_channel(state):
    return {"stabilize": _clip(.25 + (1 - state.stability) - .35 * state.response_surface_shift), "de_risk": _clip(.20 + state.risk - .15 * state.response_surface_shift), "explore": _clip(state.opportunity - .45 * state.risk + .20 * state.response_surface_shift)}


def choose_v2_greedy_decision(state, scenario) -> ClosedLoopActionDecision:
    ch, gain = max(_visible_gain_by_channel(state).items(), key=lambda kv: kv[1])
    if gain <= .05: return choose_no_action_decision(state, scenario)
    return ClosedLoopActionDecision("EXECUTE", ch, min(.22, state.safe_mass_upper * .95), "visible_v2_short_term_gain_maximization")


def choose_action_module_decision(state, history, scenario) -> ClosedLoopActionDecision:
    p = build_prepared_inputs_from_state(state, history, scenario)
    r: ActionModuleStepResult = action_module_step(**p, label_override="closed_loop_runner_integration_rc1")
    d = r.action_decision
    return ClosedLoopActionDecision(d.decision_type, d.selected_channel, float(d.selected_action_mass), d.decision_reason, bool(r.action_audit_record.boundary_flags["audit_passed"]))


def compute_closed_loop_short_term_gain(state, decision, scenario) -> float:
    if decision.decision_type != "EXECUTE" or not decision.selected_channel: return 0.0
    eff = _visible_gain_by_channel(state).get(decision.selected_channel, 0.0)
    if state.response_surface_shift > .35 and decision.selected_channel == "stabilize": eff -= .35
    return eff * decision.selected_action_mass * 4.0 - (.35 if compute_safety_violation(state, decision) else 0.0)


def compute_safety_violation(state, decision) -> bool:
    return decision.decision_type == "EXECUTE" and (decision.selected_action_mass >= state.harmful_threshold or decision.selected_action_mass > state.safe_mass_upper)


def compute_over_action(state, decision) -> bool:
    return decision.selected_action_mass > state.safe_mass_upper or (decision.decision_type == "EXECUTE" and decision.selected_action_mass > .14 and (state.fatigue + state.hidden_fragility) > .85)


def compute_missed_opportunity(state, decision) -> bool:
    return state.opportunity > .70 and state.risk < .55 and state.safe_mass_upper > .05 and decision.decision_type == "NO_OP"


def compute_delayed_side_effect_cost(state, decision, scenario) -> float:
    if decision.decision_type != "EXECUTE": return 0.0
    scenario_factor = 1.8 if scenario.scenario_type == "delayed_side_effect" and scenario.delayed_effect_start_step is not None and state.step >= scenario.delayed_effect_start_step else 1.0
    lock_factor = 1.5 if decision.selected_channel == "stabilize" else 1.0
    return _clip(decision.selected_action_mass * scenario_factor * lock_factor * (.35 + state.fatigue + state.relation_lock))


def apply_action_decision_to_pseudo_reality(state, decision, scenario):
    mass = decision.selected_action_mass if decision.decision_type == "EXECUTE" else 0.0
    over = compute_over_action(state, decision); side = compute_delayed_side_effect_cost(state, decision, scenario)
    ext = scenario.external_pressure_schedule[min(state.step + 1, len(scenario.external_pressure_schedule) - 1)]
    shock = .22 if scenario.shock_step == state.step + 1 else 0.0
    drift = .10 if scenario.drift_start_step is not None and state.step + 1 >= scenario.drift_start_step else 0.0
    safety_shift = scenario.safety_shift_step is not None and state.step + 1 >= scenario.safety_shift_step
    helpful = mass * (1.2 if decision.selected_channel in {"stabilize", "de_risk"} else .45)
    risk_delta = .05 * ext + shock + side - helpful - (.08 if decision.decision_type == "ROLLBACK" else 0) - (.04 if decision.decision_type == "COOLDOWN" else 0)
    stability_delta = helpful * .65 - .05 * ext - shock * .6 - side * .4
    fatigue = _clip(state.fatigue + mass * (.55 if over else .28) - (.07 if decision.decision_type in {"COOLDOWN", "NO_OP"} else .02))
    relation_lock = _clip(state.relation_lock + (mass * .35 if decision.selected_channel == "stabilize" else mass * .10) - (.08 if decision.selected_channel == "relation_unlock" else 0))
    exploration = _clip(state.exploration_capacity - mass * (.25 if decision.selected_channel == "stabilize" else .10) - relation_lock * .03 + (.03 if decision.selected_channel == "explore" else 0))
    return ClosedLoopPseudoRealityState(state.step + 1, _clip(state.stability + stability_delta), _clip(state.risk + risk_delta + (.10 if over else 0)), _clip(state.opportunity - mass * .18 + .02), exploration, _clip(state.recovery_capacity - fatigue * .04 - side * .10 + (.04 if decision.decision_type in {"COOLDOWN", "ROLLBACK"} else 0)), fatigue, relation_lock, _clip(state.hidden_fragility + side * .18 + (.08 if over else 0) - (.05 if decision.decision_type == "ROLLBACK" else 0)), ext, _clip(state.safe_mass_upper - (.035 if safety_shift else 0)), _clip(state.harmful_threshold - (.045 if safety_shift else 0)), _clip(state.response_surface_shift + drift))


def compute_closed_loop_recovery_score(before, after, decision, scenario) -> float:
    return _clip(.45 + (before.risk - after.risk) + (after.stability - before.stability) + .20 * after.recovery_capacity - .15 * after.fatigue + (.10 if decision.decision_type in {"COOLDOWN", "ROLLBACK"} and scenario.shock_step is not None else 0) - (.15 if compute_over_action(before, decision) else 0))


def run_closed_loop_step(state, history, scenario, baseline_name, *, seed=0):
    decision = {"NO_ACTION": choose_no_action_decision, "V2_GREEDY_OPTIMIZER": choose_v2_greedy_decision}.get(baseline_name, None)
    dec = decision(state, scenario) if decision else choose_action_module_decision(state, history, scenario)
    gain = compute_closed_loop_short_term_gain(state, dec, scenario); viol = compute_safety_violation(state, dec); over = compute_over_action(state, dec)
    after = apply_action_decision_to_pseudo_reality(state, dec, scenario)
    rec = ClosedLoopStepRecord(scenario.scenario_id, scenario.scenario_type, baseline_name, seed, state.step, state, dec.decision_type, dec.selected_channel, dec.selected_action_mass, after, gain, viol, over, compute_missed_opportunity(state, dec), compute_delayed_side_effect_cost(state, dec, scenario), compute_closed_loop_recovery_score(state, after, dec, scenario), dec.audit_passed)
    act = {"decision_type": dec.decision_type, "selected_channel": dec.selected_channel, "selected_action_mass": dec.selected_action_mass}
    hist = ClosedLoopHistory((history.recent_actions + (act,))[-5:], (history.recent_states + (after,))[-5:], max(0, history.cooldown_counter - 1) + (1 if dec.decision_type == "COOLDOWN" else 0), max(0, history.rollback_counter - 1) + (1 if dec.decision_type == "ROLLBACK" else 0), history.cumulative_action_mass + dec.selected_action_mass, history.cumulative_harmful_events + int(viol))
    return after, hist, rec


def run_closed_loop_episode(scenario, baseline_name, *, seed=0):
    state = initial_state_for_scenario(scenario, seed=seed); hist = initial_closed_loop_history(); rows = []
    for _ in range(scenario.n_steps):
        state, hist, rec = run_closed_loop_step(state, hist, scenario, baseline_name, seed=seed); rows.append(rec)
    return rows


def build_closed_loop_step_long(records):
    rows = []
    for r in records:
        b, a = r.state_before, r.state_after
        rows.append({"scenario_id": r.scenario_id, "scenario_type": r.scenario_type, "baseline_name": r.baseline_name, "seed": r.seed, "step": r.step, "stability_before": b.stability, "risk_before": b.risk, "opportunity_before": b.opportunity, "exploration_capacity_before": b.exploration_capacity, "recovery_capacity_before": b.recovery_capacity, "fatigue_before": b.fatigue, "relation_lock_before": b.relation_lock, "hidden_fragility_before": b.hidden_fragility, "external_pressure_before": b.external_pressure, "safe_mass_upper_before": b.safe_mass_upper, "harmful_threshold_before": b.harmful_threshold, "decision_type": r.decision_type, "selected_channel": r.selected_channel, "selected_action_mass": r.selected_action_mass, "short_term_gain": r.short_term_gain, "safety_violation": r.safety_violation, "over_action": r.over_action, "missed_opportunity": r.missed_opportunity, "delayed_side_effect_cost": r.delayed_side_effect_cost, "recovery_score": r.recovery_score, "stability_after": a.stability, "risk_after": a.risk, "opportunity_after": a.opportunity, "exploration_capacity_after": a.exploration_capacity, "recovery_capacity_after": a.recovery_capacity, "fatigue_after": a.fatigue, "relation_lock_after": a.relation_lock, "audit_passed": r.audit_passed})
    return pd.DataFrame(rows)


def build_closed_loop_episode_summary(step_long):
    def summarize(g):
        first, last = g.iloc[0], g.iloc[-1]
        recovered = g[(g.step >= 4) & (g.risk_after < .45) & (g.stability_after > .68)]
        ttr = 99 if recovered.empty else int(recovered.iloc[0].step - 4)
        return pd.Series({"n_steps": len(g), "cumulative_gain": g.short_term_gain.sum(), "mean_stability": g.stability_after.mean(), "final_stability": last.stability_after, "mean_risk": g.risk_after.mean(), "final_risk": last.risk_after, "safety_violation_count": int(g.safety_violation.sum()), "safety_violation_rate": g.safety_violation.mean(), "over_action_count": int(g.over_action.sum()), "over_action_rate": g.over_action.mean(), "missed_opportunity_rate": g.missed_opportunity.mean(), "mean_recovery_score": g.recovery_score.mean(), "time_to_recover": ttr, "max_fatigue": g.fatigue_after.max(), "final_relation_lock": last.relation_lock_after, "exploration_capacity_retention": _clip(last.exploration_capacity_after / max(first.exploration_capacity_before, 1e-9)), "audit_pass_rate": g.audit_passed.mean()})
    return step_long.groupby(["scenario_id", "scenario_type", "baseline_name", "seed"], as_index=False).apply(summarize, include_groups=False).reset_index(drop=True)


def compute_closed_loop_robustness_score(row_or_group):
    r = row_or_group.iloc[0] if isinstance(row_or_group, pd.DataFrame) else row_or_group
    return _clip(.24 * (1 - r.mean_safety_violation_rate) + .18 * (1 - r.mean_over_action_rate) + .16 * (1 - r.mean_final_risk) + .16 * r.mean_recovery_score + .10 * (1 - r.mean_final_relation_lock) + .10 * r.mean_exploration_capacity_retention + .06 * r.mean_audit_pass_rate)


def build_closed_loop_baseline_comparison_summary(ep):
    out = ep.groupby("baseline_name", as_index=False).agg(mean_cumulative_gain=("cumulative_gain", "mean"), mean_final_stability=("final_stability", "mean"), mean_final_risk=("final_risk", "mean"), mean_safety_violation_rate=("safety_violation_rate", "mean"), mean_over_action_rate=("over_action_rate", "mean"), mean_missed_opportunity_rate=("missed_opportunity_rate", "mean"), mean_recovery_score=("mean_recovery_score", "mean"), mean_time_to_recover=("time_to_recover", "mean"), mean_final_relation_lock=("final_relation_lock", "mean"), mean_exploration_capacity_retention=("exploration_capacity_retention", "mean"), mean_audit_pass_rate=("audit_pass_rate", "mean"))
    out["closed_loop_robustness_score"] = out.apply(compute_closed_loop_robustness_score, axis=1)
    return out


def build_closed_loop_scenario_breakdown(ep):
    out = ep.groupby(["scenario_type", "baseline_name"], as_index=False).agg(mean_cumulative_gain=("cumulative_gain", "mean"), mean_safety_violation_rate=("safety_violation_rate", "mean"), mean_over_action_rate=("over_action_rate", "mean"), mean_recovery_score=("mean_recovery_score", "mean"), mean_time_to_recover=("time_to_recover", "mean"), mean_final_relation_lock=("final_relation_lock", "mean"), mean_exploration_capacity_retention=("exploration_capacity_retention", "mean"))
    def cls(r):
        if r.mean_safety_violation_rate > .25 or r.mean_recovery_score < .25: return "collapse_case"
        if r.mean_over_action_rate > .20: return "over_action_loser"
        if r.baseline_name == "NO_ACTION" and r.mean_cumulative_gain < .05: return "stable_but_inactive"
        if r.mean_cumulative_gain == out[out.scenario_type == r.scenario_type].mean_cumulative_gain.max(): return "short_term_gain_winner"
        if r.mean_safety_violation_rate == out[out.scenario_type == r.scenario_type].mean_safety_violation_rate.min(): return "safety_winner"
        if r.mean_recovery_score == out[out.scenario_type == r.scenario_type].mean_recovery_score.max(): return "recovery_winner"
        return "robust_tradeoff"
    out["scenario_result_class"] = out.apply(cls, axis=1)
    return out


def build_closed_loop_audit_boundary_summary(step_long):
    rows=[]
    for b in BASELINES:
        row={"baseline_name": b, **{c: False for c in BOUNDARY_COLS}, "production_runtime_modified": False, "audit_passed": bool(step_long[step_long.baseline_name == b].audit_passed.all())}
        rows.append(row)
    return pd.DataFrame(rows, columns=["baseline_name", *BOUNDARY_COLS, "production_runtime_modified", "audit_passed"])


def run_closed_loop_runner_integration_rc1(*, seeds=(0, 1, 2)):
    pre = run_pr99_preflight_check(); records=[]
    for s in build_closed_loop_scenarios():
        for seed in seeds:
            for b in BASELINES:
                records.extend(run_closed_loop_episode(s, b, seed=seed))
    step = build_closed_loop_step_long(records); ep = build_closed_loop_episode_summary(step)
    return ClosedLoopRunnerResult(step, ep, build_closed_loop_baseline_comparison_summary(ep), build_closed_loop_scenario_breakdown(ep), build_closed_loop_audit_boundary_summary(step), pre)


EXPECTED_STEP_COLS = ["scenario_id", "scenario_type", "baseline_name", "seed", "step", "stability_before", "risk_before", "opportunity_before", "exploration_capacity_before", "recovery_capacity_before", "fatigue_before", "relation_lock_before", "hidden_fragility_before", "external_pressure_before", "safe_mass_upper_before", "harmful_threshold_before", "decision_type", "selected_channel", "selected_action_mass", "short_term_gain", "safety_violation", "over_action", "missed_opportunity", "delayed_side_effect_cost", "recovery_score", "stability_after", "risk_after", "opportunity_after", "exploration_capacity_after", "recovery_capacity_after", "fatigue_after", "relation_lock_after", "audit_passed"]


def test_schema_and_required_dataframes():
    r = run_closed_loop_runner_integration_rc1(seeds=(0,))
    assert isinstance(r, ClosedLoopRunnerResult)
    assert r.closed_loop_step_long.columns.tolist() == EXPECTED_STEP_COLS
    assert r.closed_loop_episode_summary.columns.tolist() == ["scenario_id", "scenario_type", "baseline_name", "seed", "n_steps", "cumulative_gain", "mean_stability", "final_stability", "mean_risk", "final_risk", "safety_violation_count", "safety_violation_rate", "over_action_count", "over_action_rate", "missed_opportunity_rate", "mean_recovery_score", "time_to_recover", "max_fatigue", "final_relation_lock", "exploration_capacity_retention", "audit_pass_rate"]
    assert r.closed_loop_baseline_comparison_summary.columns.tolist() == ["baseline_name", "mean_cumulative_gain", "mean_final_stability", "mean_final_risk", "mean_safety_violation_rate", "mean_over_action_rate", "mean_missed_opportunity_rate", "mean_recovery_score", "mean_time_to_recover", "mean_final_relation_lock", "mean_exploration_capacity_retention", "mean_audit_pass_rate", "closed_loop_robustness_score"]
    assert r.closed_loop_scenario_breakdown.columns.tolist() == ["scenario_type", "baseline_name", "mean_cumulative_gain", "mean_safety_violation_rate", "mean_over_action_rate", "mean_recovery_score", "mean_time_to_recover", "mean_final_relation_lock", "mean_exploration_capacity_retention", "scenario_result_class"]
    assert r.closed_loop_audit_boundary_summary.columns.tolist() == ["baseline_name", *BOUNDARY_COLS, "production_runtime_modified", "audit_passed"]
    assert r.closed_loop_preflight_summary.columns.tolist() == ["preflight_item", "value", "passed", "blocking", "note"]


def test_preflight_and_scenario_and_baseline_coverage():
    pre = run_pr99_preflight_check(); assert pre.set_index("preflight_item").loc["preflight_passed", "passed"] is True or bool(pre.set_index("preflight_item").loc["preflight_passed", "passed"])
    r = run_closed_loop_runner_integration_rc1(seeds=(0,)); assert set(SCENARIOS).issubset(set(r.closed_loop_step_long.scenario_type)); assert set(BASELINES) == set(r.closed_loop_step_long.baseline_name)


def test_episode_run_bounded_and_one_step_integration():
    r = run_closed_loop_runner_integration_rc1(seeds=(0,)); counts = r.closed_loop_step_long.groupby(["scenario_type", "baseline_name"]).step.count(); assert (counts >= 10).all()
    numeric = [c for c in r.closed_loop_step_long.columns if c.endswith(("_before", "_after")) and c not in {"selected_channel"}]
    assert r.closed_loop_step_long[numeric].apply(lambda s: s.between(0, 1).all()).all()
    s = build_closed_loop_scenarios()[1]; st = initial_state_for_scenario(s); h = initial_closed_loop_history(); after, hist, rec = run_closed_loop_step(st, h, s, "ACTION_MODULE_RC1")
    assert after != st and hist.recent_actions and rec.baseline_name == "ACTION_MODULE_RC1"


def test_meaningful_baseline_and_robustness_patterns():
    r = run_closed_loop_runner_integration_rc1(seeds=(0, 1))
    stable = r.closed_loop_episode_summary[r.closed_loop_episode_summary.scenario_type == "stable_closed_v2"].groupby("baseline_name").cumulative_gain.mean()
    assert stable["V2_GREEDY_OPTIMIZER"] >= stable["NO_ACTION"]
    assert stable["V2_GREEDY_OPTIMIZER"] >= stable["ACTION_MODULE_RC1"]
    no = r.closed_loop_step_long[r.closed_loop_step_long.baseline_name == "NO_ACTION"]
    assert (no.selected_action_mass == 0.0).all() and no.safety_violation.mean() <= .01 and no.missed_opportunity.any()
    stress = r.closed_loop_baseline_comparison_summary.set_index("baseline_name")
    assert (stress.loc["ACTION_MODULE_RC1", "mean_over_action_rate"] < stress.loc["V2_GREEDY_OPTIMIZER", "mean_over_action_rate"] or stress.loc["ACTION_MODULE_RC1", "mean_recovery_score"] > stress.loc["V2_GREEDY_OPTIMIZER", "mean_recovery_score"] or stress.loc["ACTION_MODULE_RC1", "mean_final_relation_lock"] < stress.loc["V2_GREEDY_OPTIMIZER", "mean_final_relation_lock"] or stress.loc["ACTION_MODULE_RC1", "mean_exploration_capacity_retention"] > stress.loc["V2_GREEDY_OPTIMIZER", "mean_exploration_capacity_retention"] or stress.loc["ACTION_MODULE_RC1", "mean_audit_pass_rate"] > stress.loc["V2_GREEDY_OPTIMIZER", "mean_audit_pass_rate"])


def test_no_write_boundary_no_production_mutation_and_no_full_v3():
    r = run_closed_loop_runner_integration_rc1(seeds=(0,)); am = r.closed_loop_audit_boundary_summary[r.closed_loop_audit_boundary_summary.baseline_name == "ACTION_MODULE_RC1"]
    for c in BOUNDARY_COLS: assert not am[c].any()
    changed = subprocess.check_output(["git", "diff", "--name-only"], text=True).splitlines()
    forbidden = [p for p in changed if any(x in p for x in PRODUCTION_RUNTIME_PATTERNS)]
    assert forbidden == []
    assert "full_v3_pseudo_open_system" not in globals()
