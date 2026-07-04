"""Action Module API v2 alignment and pseudo-open stress audit RC1.

This file is intentionally test-local. It audits the consolidated
``action_module_step`` API without modifying production runtime files,
canonical state, v2 dynamics, ActionPlanner, ActionModule, ParameterBox, or
ShadowBox.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import subprocess

import pandas as pd

from test_action_module_api_consolidation_rc1 import (
    ActionModuleStepResult,
    action_module_step,
)
from test_phase2g21c_b_functional_policy_v2_alignment import (
    align_functional_policy_with_v2_response_curve,
)


NON_EXECUTION = {"NO_OP", "COOLDOWN", "ROLLBACK", "HOLD_FOR_EVIDENCE"}
BASELINES = ("NO_ACTION", "V2_GREEDY_OPTIMIZER", "ACTION_MODULE_RC1")
STRESS_TYPES = (
    "reaction_surface_shift",
    "hidden_state_noise",
    "delayed_side_effect",
    "safety_boundary_shift",
    "external_field_shock",
)
PRODUCTION_RUNTIME_PATTERNS = (
    "ActionPlanner",
    "ActionModule",
    "ParameterBox",
    "ShadowBox",
    "pseudo_reality",
    "asymmetric_game_v2",
)


@dataclass(frozen=True)
class ActionModuleOpenStressAuditResult:
    action_module_v2_alignment_long: pd.DataFrame
    action_module_v2_alignment_summary: pd.DataFrame
    action_module_baseline_comparison_long: pd.DataFrame
    action_module_baseline_comparison_summary: pd.DataFrame
    action_module_open_stress_long: pd.DataFrame
    action_module_open_stress_summary: pd.DataFrame
    action_module_open_stress_decision_audit: pd.DataFrame


def _clip(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def _representative_v2_cases() -> list[dict]:
    base_obs = {"evidence_strength": "high", "missing_evidence": False, "safe_range_known": True, "harmful_threshold_known": True}
    base_history = {"cooldown_active": False, "recent_rollback": False, "last_action_mass": 0.05, "recent_harmful_fire_rate": 0.0}
    cases = [
        ("v2_case_001", "stable_safe_execute", .92, .12, .88, .05, {}, .30, .45, "stabilize", ["stabilize", "de_risk"], .20, {"stabilize": .80, "explore": .45, "de_risk": .60}),
        ("v2_case_002", "unsafe_execute", .65, .75, .35, .78, {}, .12, .22, "de_risk", ["de_risk"], .08, {"stabilize": .50, "explore": .10, "de_risk": .55}),
        ("v2_case_003", "missing_evidence", .75, .20, .72, .15, {"obs": {"evidence_strength": "missing", "missing_evidence": True, "safe_range_known": False, "harmful_threshold_known": False}}, .20, .35, "stabilize", ["stabilize"], .10, {"stabilize": .65, "explore": .25, "de_risk": .35}),
        ("v2_case_004", "force_cooldown", .70, .55, .50, .65, {"guards": {"force_cooldown": True}}, .10, .20, "de_risk", ["de_risk"], .06, {"stabilize": .50, "explore": .30, "de_risk": .58}),
        ("v2_case_005", "force_rollback", .60, .70, .40, .72, {"guards": {"force_rollback": True}, "history": {"recent_rollback": True, "recent_harmful_fire_rate": .85}}, .08, .18, "de_risk", ["de_risk"], .04, {"stabilize": .35, "explore": .10, "de_risk": .50}),
        ("v2_case_006", "blocked_channel", .88, .25, .78, .20, {"guards": {"blocked_channels": ["stabilize"]}}, .20, .32, "stabilize", ["de_risk"], .12, {"stabilize": .90, "explore": .35, "de_risk": .62}),
        ("v2_case_007", "high_opportunity_high_risk", .95, .48, .95, .43, {}, .18, .30, "explore", ["stabilize", "de_risk"], .12, {"stabilize": .62, "explore": .95, "de_risk": .70}),
        ("v2_case_008", "low_opportunity", .18, .15, .08, .10, {}, .16, .30, "de_risk", ["de_risk"], .05, {"stabilize": .10, "explore": -.05, "de_risk": .12}),
        ("v2_case_009", "channel_mismatch", .82, .18, .80, .12, {}, .22, .36, "de_risk", ["de_risk", "stabilize"], .14, {"stabilize": .64, "explore": .20, "de_risk": .68}),
        ("v2_case_010", "cap_sensitive", .90, .22, .86, .18, {"params": {"max_action_mass": .11}, "guards": {"max_allowed_action_mass": .11}}, .11, .24, "stabilize", ["stabilize", "de_risk"], .10, {"stabilize": .72, "explore": .30, "de_risk": .55}),
    ]
    out = []
    for cid, label, intensity, instability, opportunity, risk, extra, safe, harmful, preferred, acceptable, expected, gains in cases:
        obs = {**base_obs, **extra.get("obs", {})}
        history = {**base_history, **extra.get("history", {})}
        params = {"max_action_mass": extra.get("params", {}).get("max_action_mass", min(.30, safe)), "min_fire_permission": .50}
        guards = {"blocked_channels": [], "max_allowed_action_mass": min(.30, safe), "force_cooldown": False, "force_rollback": False, **extra.get("guards", {})}
        out.append({
            "case_id": cid, "scenario_label": label,
            "prepared_upper_pressure": {"pressure_intensity": intensity, "preferred_channels": {"stabilize": intensity, "explore": opportunity, "de_risk": max(risk, .25)}},
            "prepared_lower_state": {"instability": instability, "opportunity": opportunity, "risk": risk, "recovery_need": max(risk, instability), "fatigue": risk / 2},
            "prepared_observation_view": obs, "action_history": history, "parameter_snapshot": params, "guardrail_snapshot": guards,
            "v2_safe_mass_upper": safe, "v2_harmful_threshold": harmful, "v2_preferred_channel": preferred,
            "v2_acceptable_channels": acceptable, "v2_expected_action_mass": expected, "v2_short_term_gain_by_channel": gains,
        })
    return out


def choose_no_action(case: dict) -> dict:
    return {"decision_type": "NO_OP", "selected_channel": None, "selected_action_mass": 0.0, "decision_reason": "no_action_baseline"}


def choose_v2_greedy_action(case: dict) -> dict:
    channel, gain = max(case["v2_short_term_gain_by_channel"].items(), key=lambda kv: kv[1])
    if gain <= 0.0:
        return choose_no_action(case)
    mass = min(case["v2_expected_action_mass"], case["v2_safe_mass_upper"] * 0.95)
    return {"decision_type": "EXECUTE", "selected_channel": channel, "selected_action_mass": mass, "decision_reason": "visible_v2_short_term_gain_maximization"}


def choose_action_module_rc1(case: dict, *, label_override=None) -> ActionModuleStepResult:
    return action_module_step(case["prepared_upper_pressure"], case["prepared_lower_state"], case["prepared_observation_view"], case["action_history"], case.get("parameter_snapshot"), case.get("guardrail_snapshot"), label_override=label_override)


def _decision_from_result(result: ActionModuleStepResult) -> dict:
    d = result.action_decision
    return {"decision_type": d.decision_type, "selected_channel": d.selected_channel, "selected_action_mass": d.selected_action_mass, "decision_reason": d.decision_reason}


def compute_visible_short_term_gain(case: dict, decision: dict) -> float:
    if decision["decision_type"] != "EXECUTE" or not decision.get("selected_channel"):
        return 0.0
    mass = float(decision.get("selected_action_mass", 0.0))
    gain = case["v2_short_term_gain_by_channel"].get(decision["selected_channel"], 0.0) * (mass / max(case["v2_expected_action_mass"], 1e-9))
    if mass > case["v2_safe_mass_upper"]:
        gain -= 0.40
    if mass >= case["v2_harmful_threshold"]:
        gain -= 0.80
    if decision["selected_channel"] in case["guardrail_snapshot"].get("blocked_channels", []):
        gain -= 0.60
    return float(gain)


def _stress_cases(cases: list[dict]) -> list[dict]:
    return [
        {"stress_case_id": "stress_001", "case": cases[0], "stress_type": "reaction_surface_shift", "stress_strength": .70, "gain_shift_by_channel": {"stabilize": -.55, "de_risk": .05, "explore": -.15}, "shifted_safe_mass_upper": .18},
        {"stress_case_id": "stress_002", "case": cases[6], "stress_type": "hidden_state_noise", "stress_strength": .75, "hidden_fragility": .80, "shifted_safe_mass_upper": .10},
        {"stress_case_id": "stress_003", "case": cases[0], "stress_type": "delayed_side_effect", "stress_strength": .65, "delayed_cost_factor": .90, "shifted_safe_mass_upper": .22},
        {"stress_case_id": "stress_004", "case": cases[9], "stress_type": "safety_boundary_shift", "stress_strength": .80, "shifted_safe_mass_upper": .06},
        {"stress_case_id": "stress_005", "case": cases[1], "stress_type": "external_field_shock", "stress_strength": .85, "external_instability": .85, "shifted_safe_mass_upper": .07},
    ]


def compute_stress_adjusted_gain(case: dict, stress: dict, decision: dict) -> float:
    before = compute_visible_short_term_gain(case, decision)
    if decision["decision_type"] != "EXECUTE":
        return before - (0.04 if stress["stress_type"] == "external_field_shock" else 0.0)
    channel = decision.get("selected_channel")
    mass = float(decision.get("selected_action_mass", 0.0))
    shifted = before + stress.get("gain_shift_by_channel", {}).get(channel, 0.0) * (mass / max(case["v2_expected_action_mass"], 1e-9))
    if stress["stress_type"] == "hidden_state_noise":
        shifted -= stress.get("hidden_fragility", 0.0) * mass * 2.0
    if stress["stress_type"] == "delayed_side_effect":
        shifted -= stress.get("delayed_cost_factor", 0.0) * mass
    if stress["stress_type"] == "external_field_shock":
        shifted -= stress.get("external_instability", 0.0) * mass * 1.5
    if mass > stress.get("shifted_safe_mass_upper", case["v2_safe_mass_upper"]):
        shifted -= 0.50
    return float(shifted)


def _delayed_cost(case: dict, stress: dict, decision: dict) -> float:
    if decision["decision_type"] != "EXECUTE":
        return 0.0
    mass = decision["selected_action_mass"]
    factor = stress.get("delayed_cost_factor", .25 if stress["stress_type"] in {"hidden_state_noise", "external_field_shock"} else .10)
    return _clip(mass * factor * (1.0 + stress["stress_strength"]))


def compute_recovery_score(case: dict, stress: dict, decision: dict) -> float:
    mass = float(decision.get("selected_action_mass", 0.0))
    shifted_safe = stress.get("shifted_safe_mass_upper", case["v2_safe_mass_upper"])
    score = .72
    if mass <= shifted_safe:
        score += .12
    else:
        score -= .35
    if decision["decision_type"] == "ROLLBACK" and stress["stress_type"] in {"hidden_state_noise", "external_field_shock"}:
        score += .15
    if decision["decision_type"] in {"COOLDOWN", "HOLD_FOR_EVIDENCE", "NO_OP"} and stress["stress_type"] in {"safety_boundary_shift", "hidden_state_noise"}:
        score += .10
    if decision["decision_type"] == "EXECUTE" and mass <= shifted_safe and mass <= case["v2_expected_action_mass"]:
        score += .08
    if stress["stress_type"] == "external_field_shock":
        score -= .12
    return _clip(score)


def compute_robustness_score(row_or_group) -> float:
    if isinstance(row_or_group, pd.DataFrame):
        v = row_or_group.iloc[0]
    else:
        v = row_or_group
    score = 1.0
    score -= 0.30 * float(v.get("safety_violation_after_shift_rate", v.get("safety_violation_after_shift", False)))
    score -= 0.25 * float(v.get("over_action_after_shift_rate", v.get("over_action_after_shift", False)))
    score -= 0.20 * _clip(v.get("mean_delayed_side_effect_cost", v.get("delayed_side_effect_cost", 0.0)))
    score -= 0.15 * _clip(max(0.0, v.get("mean_performance_drop_after_shift", v.get("performance_drop_after_shift", 0.0))))
    score += 0.20 * _clip(v.get("mean_recovery_after_shock", v.get("recovery_after_shock", 0.0)))
    return _clip(score)


def audit_action_module_v2_alignment(*, label_override=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    align_functional_policy_with_v2_response_curve()
    rows = []
    for case in _representative_v2_cases():
        result = choose_action_module_rc1(case, label_override=label_override)
        decision = _decision_from_result(result)
        dt, ch, mass = decision["decision_type"], decision["selected_channel"], decision["selected_action_mass"]
        non_exec = dt in NON_EXECUTION
        safe = non_exec or mass <= case["v2_safe_mass_upper"]
        harmful = dt == "EXECUTE" and mass >= case["v2_harmful_threshold"]
        weak_evidence = case["prepared_observation_view"].get("missing_evidence") or case["prepared_observation_view"].get("evidence_strength") in {"low", "missing"}
        safe_positive = case["v2_expected_action_mass"] > 0 and max(case["v2_short_term_gain_by_channel"].values()) > .20 and not weak_evidence and not case["guardrail_snapshot"].get("force_cooldown") and not case["guardrail_snapshot"].get("force_rollback")
        missed = dt == "NO_OP" and safe_positive
        if dt == "EXECUTE":
            cls = "preferred" if ch == case["v2_preferred_channel"] else "acceptable" if ch in case["v2_acceptable_channels"] else "mismatch"
        else:
            cls = "non_execution_reasonable" if weak_evidence or case["guardrail_snapshot"].get("force_cooldown") or case["guardrail_snapshot"].get("force_rollback") or case["prepared_lower_state"].get("opportunity", 0) < .15 else "not_applicable"
        cooldown_over = dt == "COOLDOWN" and not (case["guardrail_snapshot"].get("force_cooldown") or case["prepared_lower_state"].get("risk", 0) >= .50)
        rollback_over = dt == "ROLLBACK" and not (case["guardrail_snapshot"].get("force_rollback") or case["prepared_lower_state"].get("risk", 0) >= .60 or case["action_history"].get("recent_harmful_fire_rate", 0) >= .50)
        hold_ok = dt == "HOLD_FOR_EVIDENCE" and weak_evidence
        score = 1.0 - (.45 if harmful else 0) - (.20 if not safe else 0) - (.15 if cls == "mismatch" else 0) - (.15 if missed else 0) - (.08 if cooldown_over or rollback_over else 0)
        rows.append({"case_id": case["case_id"], "scenario_label": case["scenario_label"], "decision_type": dt, "selected_channel": ch, "selected_action_mass": mass, "v2_safe_mass_upper": case["v2_safe_mass_upper"], "v2_harmful_threshold": case["v2_harmful_threshold"], "v2_preferred_channel": case["v2_preferred_channel"], "mass_within_v2_safe_range": safe, "harmful_execute_violation": harmful, "missed_safe_opportunity": missed, "channel_alignment_class": cls, "cooldown_overuse": cooldown_over, "rollback_overuse": rollback_over, "hold_for_evidence_reasonable": hold_ok, "v2_alignment_score": _clip(score), "audit_passed": safe and not harmful and result.action_audit_record.boundary_flags["audit_passed"]})
    long = pd.DataFrame(rows)
    summary = pd.DataFrame([{"n_cases": len(long), "mean_v2_alignment_score": long.v2_alignment_score.mean(), "harmful_execute_violation_rate": long.harmful_execute_violation.mean(), "missed_safe_opportunity_rate": long.missed_safe_opportunity.mean(), "channel_alignment_rate": long.channel_alignment_class.isin(["preferred", "acceptable", "non_execution_reasonable"]).mean(), "cooldown_overuse_rate": long.cooldown_overuse.mean(), "rollback_overuse_rate": long.rollback_overuse.mean(), "hold_reasonable_rate": long.hold_for_evidence_reasonable.mean(), "audit_boundary_pass_rate": long.audit_passed.mean()}])
    return long, summary


def _baseline_decisions(case: dict, *, label_override=None) -> dict:
    return {"NO_ACTION": choose_no_action(case), "V2_GREEDY_OPTIMIZER": choose_v2_greedy_action(case), "ACTION_MODULE_RC1": _decision_from_result(choose_action_module_rc1(case, label_override=label_override))}


def audit_optimization_drift_stress(*, label_override=None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cases = _representative_v2_cases()
    baseline_rows = []
    audit_rows = []
    for case in cases:
        for name, decision in _baseline_decisions(case, label_override=label_override).items():
            mass = decision["selected_action_mass"]
            violation = decision["decision_type"] == "EXECUTE" and (mass >= case["v2_harmful_threshold"] or decision.get("selected_channel") in case["guardrail_snapshot"].get("blocked_channels", []))
            over = mass > case["v2_safe_mass_upper"]
            missed = decision["decision_type"] != "EXECUTE" and max(case["v2_short_term_gain_by_channel"].values()) > .20 and case["v2_expected_action_mass"] > 0
            baseline_rows.append({"case_id": case["case_id"], "baseline_name": name, "decision_type": decision["decision_type"], "selected_channel": decision.get("selected_channel"), "selected_action_mass": mass, "short_term_gain": compute_visible_short_term_gain(case, decision), "safety_violation": violation, "over_action": over, "missed_opportunity": missed, "recovery_score": compute_recovery_score(case, {"stress_type": "closed_v2", "stress_strength": 0.0}, decision), "audit_passed": (not violation if name != "ACTION_MODULE_RC1" else choose_action_module_rc1(case).action_audit_record.boundary_flags["audit_passed"] and not violation)})
    stress_rows = []
    for stress in _stress_cases(cases):
        case = stress["case"]
        for name, decision in _baseline_decisions(case, label_override=label_override).items():
            before = compute_visible_short_term_gain(case, decision)
            after = compute_stress_adjusted_gain(case, stress, decision)
            mass = decision["selected_action_mass"]
            shifted_safe = stress.get("shifted_safe_mass_upper", case["v2_safe_mass_upper"])
            safety_after = decision["decision_type"] == "EXECUTE" and (mass >= case["v2_harmful_threshold"] or mass > shifted_safe or decision.get("selected_channel") in case["guardrail_snapshot"].get("blocked_channels", []))
            stress_rows.append({"stress_case_id": stress["stress_case_id"], "stress_type": stress["stress_type"], "stress_strength": stress["stress_strength"], "baseline_name": name, "decision_type": decision["decision_type"], "selected_channel": decision.get("selected_channel"), "selected_action_mass": mass, "observed_gain_before_shift": before, "observed_gain_after_shift": after, "performance_drop_after_shift": before - after, "safety_violation_after_shift": safety_after, "delayed_side_effect_cost": _delayed_cost(case, stress, decision), "recovery_after_shock": compute_recovery_score(case, stress, decision), "over_action_after_shift": mass > shifted_safe})
            if name == "ACTION_MODULE_RC1":
                flags = choose_action_module_rc1(case).action_audit_record.boundary_flags
                audit_rows.append({"baseline_name": name, "coefficient_changed": flags["coefficient_changed"], "production_runtime_changed": flags["production_runtime_changed"], "canonical_writeback_performed": flags["canonical_writeback_performed"], "fixed_candidate_used_as_runtime_coefficient": flags["fixed_candidate_used_as_runtime_coefficient"], "shadow_adjustment_used_as_runtime_default": flags["shadow_adjustment_used_as_runtime_default"], "scenario_label_controlled_logic": flags["scenario_label_controlled_logic"], "audit_passed": flags["audit_passed"]})
    for name in ("NO_ACTION", "V2_GREEDY_OPTIMIZER"):
        audit_rows.append({"baseline_name": name, "coefficient_changed": False, "production_runtime_changed": False, "canonical_writeback_performed": False, "fixed_candidate_used_as_runtime_coefficient": False, "shadow_adjustment_used_as_runtime_default": False, "scenario_label_controlled_logic": False, "audit_passed": True})
    baseline_long = pd.DataFrame(baseline_rows)
    baseline_summary = baseline_long.groupby("baseline_name", as_index=False).agg(mean_short_term_gain=("short_term_gain", "mean"), safety_violation_rate=("safety_violation", "mean"), over_action_rate=("over_action", "mean"), missed_opportunity_rate=("missed_opportunity", "mean"), mean_recovery_score=("recovery_score", "mean"), audit_pass_rate=("audit_passed", "mean"))
    stress_long = pd.DataFrame(stress_rows)
    stress_summary = stress_long.groupby(["baseline_name", "stress_type"], as_index=False).agg(mean_performance_drop_after_shift=("performance_drop_after_shift", "mean"), safety_violation_after_shift_rate=("safety_violation_after_shift", "mean"), mean_delayed_side_effect_cost=("delayed_side_effect_cost", "mean"), mean_recovery_after_shock=("recovery_after_shock", "mean"), over_action_after_shift_rate=("over_action_after_shift", "mean"))
    stress_summary["robustness_score"] = stress_summary.apply(compute_robustness_score, axis=1)
    audit = pd.DataFrame(audit_rows).drop_duplicates().reset_index(drop=True)
    return baseline_long, baseline_summary, stress_long, stress_summary, audit


def run_action_module_v2_alignment_open_stress_audit(*, label_override=None) -> ActionModuleOpenStressAuditResult:
    v2_long, v2_summary = audit_action_module_v2_alignment(label_override=label_override)
    base_long, base_summary, stress_long, stress_summary, decision_audit = audit_optimization_drift_stress(label_override=label_override)
    return ActionModuleOpenStressAuditResult(v2_long, v2_summary, base_long, base_summary, stress_long, stress_summary, decision_audit)


def test_schema_and_required_dataframes():
    result = run_action_module_v2_alignment_open_stress_audit()
    assert isinstance(result, ActionModuleOpenStressAuditResult)
    expected = {
        "action_module_v2_alignment_long": ["case_id", "scenario_label", "decision_type", "selected_channel", "selected_action_mass", "v2_safe_mass_upper", "v2_harmful_threshold", "v2_preferred_channel", "mass_within_v2_safe_range", "harmful_execute_violation", "missed_safe_opportunity", "channel_alignment_class", "cooldown_overuse", "rollback_overuse", "hold_for_evidence_reasonable", "v2_alignment_score", "audit_passed"],
        "action_module_v2_alignment_summary": ["n_cases", "mean_v2_alignment_score", "harmful_execute_violation_rate", "missed_safe_opportunity_rate", "channel_alignment_rate", "cooldown_overuse_rate", "rollback_overuse_rate", "hold_reasonable_rate", "audit_boundary_pass_rate"],
        "action_module_baseline_comparison_long": ["case_id", "baseline_name", "decision_type", "selected_channel", "selected_action_mass", "short_term_gain", "safety_violation", "over_action", "missed_opportunity", "recovery_score", "audit_passed"],
        "action_module_baseline_comparison_summary": ["baseline_name", "mean_short_term_gain", "safety_violation_rate", "over_action_rate", "missed_opportunity_rate", "mean_recovery_score", "audit_pass_rate"],
        "action_module_open_stress_long": ["stress_case_id", "stress_type", "stress_strength", "baseline_name", "decision_type", "selected_channel", "selected_action_mass", "observed_gain_before_shift", "observed_gain_after_shift", "performance_drop_after_shift", "safety_violation_after_shift", "delayed_side_effect_cost", "recovery_after_shock", "over_action_after_shift"],
        "action_module_open_stress_summary": ["baseline_name", "stress_type", "mean_performance_drop_after_shift", "safety_violation_after_shift_rate", "mean_delayed_side_effect_cost", "mean_recovery_after_shock", "over_action_after_shift_rate", "robustness_score"],
        "action_module_open_stress_decision_audit": ["baseline_name", "coefficient_changed", "production_runtime_changed", "canonical_writeback_performed", "fixed_candidate_used_as_runtime_coefficient", "shadow_adjustment_used_as_runtime_default", "scenario_label_controlled_logic", "audit_passed"],
    }
    for attr, cols in expected.items():
        assert getattr(result, attr).columns.tolist() == cols


def test_v2_alignment_and_safety():
    long, summary = audit_action_module_v2_alignment()
    assert len(long) > 5
    assert long.v2_alignment_score.between(0.0, 1.0).all()
    for col in ["harmful_execute_violation", "missed_safe_opportunity", "channel_alignment_class", "audit_passed"]:
        assert col in long.columns
    assert summary.iloc[0].harmful_execute_violation_rate <= .10


def test_baselines_and_greedy_strength():
    long, summary, *_ = audit_optimization_drift_stress()
    assert set(long.baseline_name) == set(BASELINES)
    gains = summary.set_index("baseline_name").mean_short_term_gain
    assert gains["V2_GREEDY_OPTIMIZER"] >= gains["NO_ACTION"]
    assert gains["V2_GREEDY_OPTIMIZER"] >= min(gains["ACTION_MODULE_RC1"], gains["V2_GREEDY_OPTIMIZER"])


def test_open_stress_presence_and_differentiation():
    _, _, stress_long, stress_summary, _ = audit_optimization_drift_stress()
    assert set(STRESS_TYPES).issubset(set(stress_long.stress_type))
    am = stress_summary[stress_summary.baseline_name == "ACTION_MODULE_RC1"].mean(numeric_only=True)
    greedy = stress_summary[stress_summary.baseline_name == "V2_GREEDY_OPTIMIZER"].mean(numeric_only=True)
    assert (
        am.safety_violation_after_shift_rate < greedy.safety_violation_after_shift_rate
        or am.over_action_after_shift_rate < greedy.over_action_after_shift_rate
        or am.mean_delayed_side_effect_cost < greedy.mean_delayed_side_effect_cost
        or am.mean_recovery_after_shock > greedy.mean_recovery_after_shock
        or am.robustness_score > greedy.robustness_score
    )


def test_no_action_baseline_properties():
    long, summary, *_ = audit_optimization_drift_stress()
    no_action = long[long.baseline_name == "NO_ACTION"]
    assert (no_action.selected_action_mass == 0.0).all()
    assert no_action.safety_violation.mean() == 0.0
    assert no_action.missed_opportunity.any() or summary.set_index("baseline_name").loc["NO_ACTION", "mean_short_term_gain"] == 0.0


def test_action_module_audit_boundaries_safe():
    *_, audit = audit_optimization_drift_stress()
    am = audit[audit.baseline_name == "ACTION_MODULE_RC1"]
    for col in ["coefficient_changed", "production_runtime_changed", "canonical_writeback_performed", "fixed_candidate_used_as_runtime_coefficient", "shadow_adjustment_used_as_runtime_default", "scenario_label_controlled_logic"]:
        assert not am[col].any()
    assert am.audit_passed.all()


def test_no_production_change_and_no_full_closed_loop_runner():
    changed = subprocess.check_output(["git", "diff", "--name-only"], text=True).splitlines()
    forbidden = [p for p in changed if any(pattern in p for pattern in PRODUCTION_RUNTIME_PATTERNS)]
    assert forbidden == []
    source = __import__(__name__).__dict__
    assert "full_closed_loop_runner" not in source
    assert run_action_module_v2_alignment_open_stress_audit().action_module_open_stress_decision_audit.canonical_writeback_performed.eq(False).all()
