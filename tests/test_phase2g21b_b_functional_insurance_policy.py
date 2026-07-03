"""Phase 2G-21B-B functional insurance policy contract tests.

This module intentionally keeps the policy test-local.  It defines a small
functional insurance policy over upper pressures, lower distribution terrain,
and recent action history, then verifies monotonicity, boundary behavior,
non-action preservation, and scenario-label exclusion.  Production runtime code
is not imported or modified by this policy.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path
import inspect
import math
import subprocess

CHANNELS = [
    "buffer_increase",
    "coupling_relief",
    "volatility_damping",
    "uncertainty_probe",
    "exploration_injection",
    "relation_unlock",
    "observe_only",
    "cooldown",
    "no_op",
    "hold_shadow",
]
NON_ACTION_DECISIONS = {"no_op", "observe_only", "cooldown", "hold_shadow", "none"}
PRODUCTION_RUNTIME_PATHS = [
    Path("localprep1/dept/DEPT2_ActionModule_ActuationPrimitives_RC1/pseudo_reality/asymmetric_game_v2.py"),
    Path("localprep1/dept/DEPT2_ActionModule_ActuationPrimitives_RC1/action_module.py"),
    Path("localprep1/dept/DEPT2_ActionModule_ActuationPrimitives_RC1/action_planner.py"),
]


def _clip(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def _margin01(margin: float) -> float:
    return _clip((float(margin) + 1.0) / 2.0)


def _mean(*values: float) -> float:
    return sum(values) / len(values) if values else 0.0


@dataclass(frozen=True)
class UpperPressureBundle:
    stabilize_pressure: float = 0.0
    explore_pressure: float = 0.0
    buffer_pressure: float = 0.0
    relation_relief_pressure: float = 0.0
    reversibility_pressure: float = 0.0
    cooldown_pressure: float = 0.0
    observe_pressure: float = 0.0
    de_risk_pressure: float = 0.0
    overconvergence_avoidance_pressure: float = 0.0


@dataclass(frozen=True)
class LowerDistributionBundle:
    local_no_action_risk_estimate: float = 0.0
    local_action_side_effect_cost_estimate: float = 0.0
    local_fire_margin: float = 0.0
    pair_no_action_risk_estimate: float = 0.0
    pair_action_side_effect_cost_estimate: float = 0.0
    pair_fire_margin: float = 0.0
    confidence: float = 1.0
    burden: float = 0.0
    fatigue: float = 0.0
    collapse_proximity: float = 0.0
    reversibility_need: float = 0.0
    relation_lock_proxy: float = 0.0
    coupling_proxy: float = 0.0
    exploration_need: float = 0.0
    unresolved_proxy: float = 0.0
    side_effect_risk: float = 0.0


@dataclass(frozen=True)
class ActionHistoryBundle:
    recent_correct_fire_rate: float = 0.0
    recent_harmful_fire_rate: float = 0.0
    recent_side_effect_score: float = 0.0
    recent_cooldown_state: float = 0.0
    recent_no_op_worsening: float = 0.0
    recent_wrong_direction_rate: float = 0.0


@dataclass(frozen=True)
class InsurancePolicyOutput:
    fire_permission_score: float
    action_mass_cap: float
    channel_weights: dict[str, float]
    non_action_decision: str
    cooldown_score: float
    suppression_reason: str
    evidence_trace: dict
    input_boundary_flags: list[str]


def _validate_bundle(name: str, bundle: object, fire_margin_fields: set[str] | None = None) -> list[str]:
    flags: list[str] = []
    fire_margin_fields = fire_margin_fields or set()
    for field in fields(bundle):
        value = float(getattr(bundle, field.name))
        if not math.isfinite(value):
            flags.append(f"{name}.{field.name}:non_finite")
            continue
        if field.name in fire_margin_fields:
            if value < -1.0 or value > 1.0:
                flags.append(f"{name}.{field.name}:outside_-1_1")
        elif value < 0.0 or value > 1.0:
            flags.append(f"{name}.{field.name}:outside_0_1")
    return flags


def _reasons(lower: LowerDistributionBundle, history: ActionHistoryBundle, fire_permission: float) -> list[str]:
    reasons: list[str] = []
    if fire_permission < 0.28:
        reasons.append("low_fire_permission")
    if lower.confidence < 0.35:
        reasons.append("low_confidence")
    if lower.burden > 0.72:
        reasons.append("high_burden")
    if lower.fatigue > 0.72:
        reasons.append("high_fatigue")
    if lower.side_effect_risk > 0.70:
        reasons.append("high_side_effect_risk")
    if history.recent_harmful_fire_rate > 0.55:
        reasons.append("recent_harmful_fire")
    if history.recent_cooldown_state > 0.55:
        reasons.append("cooldown_state")
    if lower.unresolved_proxy > 0.70:
        reasons.append("unresolved_high")
    if fire_permission >= 0.35 and lower.side_effect_risk >= 0.55:
        reasons.append("mixed_risk")
    return reasons


def functional_insurance_policy(
    upper: UpperPressureBundle,
    lower: LowerDistributionBundle,
    history: ActionHistoryBundle,
) -> InsurancePolicyOutput:
    """Return a test-local functional insurance policy output.

    The function reads only upper pressure, lower distribution, and recent
    action-history bundles.  It has no scenario/case/run identifier parameter.
    """
    boundary_flags = []
    boundary_flags += _validate_bundle("upper", upper)
    boundary_flags += _validate_bundle("lower", lower, {"local_fire_margin", "pair_fire_margin"})
    boundary_flags += _validate_bundle("history", history)

    upper_need = _mean(
        upper.stabilize_pressure,
        upper.explore_pressure,
        upper.buffer_pressure,
        upper.relation_relief_pressure,
        upper.reversibility_pressure,
        upper.de_risk_pressure,
        upper.overconvergence_avoidance_pressure,
    )
    terrain_allowance = _clip(
        0.35 * _margin01(lower.local_fire_margin)
        + 0.22 * _margin01(lower.pair_fire_margin)
        + 0.18 * lower.local_no_action_risk_estimate
        + 0.08 * lower.pair_no_action_risk_estimate
        + 0.10 * lower.reversibility_need
        + 0.07 * history.recent_no_op_worsening
        - 0.17 * lower.local_action_side_effect_cost_estimate
        - 0.10 * lower.pair_action_side_effect_cost_estimate
    )
    negative_fire = _clip(
        0.28 * lower.side_effect_risk
        + 0.17 * lower.burden
        + 0.17 * lower.fatigue
        + 0.13 * lower.collapse_proximity
        + 0.18 * history.recent_harmful_fire_rate
        + 0.07 * history.recent_wrong_direction_rate
    )
    fire_permission_score = _clip(
        0.12 * upper_need
        + 0.78 * terrain_allowance * lower.confidence
        + 0.10 * history.recent_correct_fire_rate
        - 0.50 * negative_fire
    )

    cooldown_score = _clip(
        0.18 * upper.cooldown_pressure
        + 0.20 * lower.burden
        + 0.20 * lower.fatigue
        + 0.16 * lower.side_effect_risk
        + 0.17 * history.recent_harmful_fire_rate
        + 0.09 * history.recent_side_effect_score
        + 0.08 * history.recent_cooldown_state
    )
    danger = _clip(
        0.24 * lower.burden
        + 0.22 * lower.fatigue
        + 0.24 * lower.side_effect_risk
        + 0.16 * history.recent_harmful_fire_rate
        + 0.14 * lower.collapse_proximity
    )
    upper_mass_gate = _clip(upper_need)
    action_mass_cap = _clip(0.56 * fire_permission_score * upper_mass_gate * lower.confidence * (1.0 - 0.74 * danger))

    safe_gate = _clip(1.0 - _mean(lower.burden, lower.fatigue, lower.side_effect_risk, history.recent_harmful_fire_rate))
    relation_gate = _clip(0.25 + 0.75 * upper.relation_relief_pressure)
    channel_weights = {
        "buffer_increase": _clip(_mean(upper.buffer_pressure, upper.reversibility_pressure, lower.reversibility_need, lower.collapse_proximity, upper.de_risk_pressure) * (1.0 - 0.35 * danger)),
        "coupling_relief": _clip(_mean(upper.relation_relief_pressure, _margin01(lower.pair_fire_margin), lower.relation_lock_proxy, lower.coupling_proxy) * relation_gate),
        "volatility_damping": _clip(_mean(upper.stabilize_pressure, upper.de_risk_pressure, lower.burden, lower.collapse_proximity) * (1.0 - 0.25 * lower.side_effect_risk)),
        "uncertainty_probe": _clip(_mean(upper.observe_pressure, lower.unresolved_proxy, 1.0 - lower.confidence) * (1.0 - 0.45 * _mean(lower.burden, lower.fatigue)) * (1.0 - 0.35 * history.recent_harmful_fire_rate)),
        "exploration_injection": _clip(_mean(upper.explore_pressure, upper.overconvergence_avoidance_pressure, lower.exploration_need) * safe_gate * (1.0 - 0.55 * lower.collapse_proximity)),
        "relation_unlock": _clip(_mean(upper.relation_relief_pressure, lower.relation_lock_proxy, _margin01(lower.pair_fire_margin)) * relation_gate * (1.0 - 0.55 * lower.side_effect_risk)),
        "observe_only": _clip(_mean(upper.observe_pressure, 1.0 - lower.confidence, lower.unresolved_proxy) * (0.7 + 0.3 * (1.0 - fire_permission_score))),
        "cooldown": cooldown_score,
        "no_op": _clip(_mean(1.0 - fire_permission_score, 1.0 - _margin01(lower.local_fire_margin), 1.0 - _margin01(lower.pair_fire_margin))),
        "hold_shadow": _clip(_mean(lower.unresolved_proxy, 1.0 - abs(lower.confidence - 0.5) * 2.0, fire_permission_score, lower.side_effect_risk)),
    }

    reasons = _reasons(lower, history, fire_permission_score)
    suppression_reason = "+".join(reasons) if reasons else "none"

    if cooldown_score >= 0.62 or history.recent_cooldown_state >= 0.72:
        non_action_decision = "cooldown"
    elif lower.confidence <= 0.32 and lower.unresolved_proxy >= 0.62:
        non_action_decision = "observe_only" if upper.observe_pressure >= 0.45 else "hold_shadow"
    elif fire_permission_score >= 0.35 and lower.side_effect_risk >= 0.58:
        non_action_decision = "hold_shadow"
    elif fire_permission_score < 0.25:
        non_action_decision = "observe_only" if channel_weights["observe_only"] >= channel_weights["no_op"] else "no_op"
    else:
        non_action_decision = "none"

    if non_action_decision != "none":
        action_mass_cap = min(action_mass_cap, 0.08 if non_action_decision == "cooldown" else 0.12)
        channel_weights["buffer_increase"] = min(channel_weights["buffer_increase"], 0.45)

    evidence_trace = {
        "positive_fire_evidence": [
            name
            for name, present in {
                "local_fire_margin_positive": lower.local_fire_margin > 0,
                "pair_fire_margin_positive": lower.pair_fire_margin > 0,
                "upper_de_risk_pressure_high": upper.de_risk_pressure >= 0.55,
                "recent_no_op_worsening": history.recent_no_op_worsening >= 0.45,
            }.items()
            if present
        ],
        "negative_fire_evidence": [
            name
            for name, present in {
                "fatigue_high": lower.fatigue >= 0.65,
                "burden_high": lower.burden >= 0.65,
                "side_effect_risk_high": lower.side_effect_risk >= 0.65,
                "confidence_low": lower.confidence <= 0.35,
                "recent_harmful_fire": history.recent_harmful_fire_rate >= 0.55,
            }.items()
            if present
        ],
        "channel_evidence": {
            "buffer_increase": ["buffer_pressure", "reversibility_pressure", "reversibility_need", "collapse_proximity", "de_risk_pressure"],
            "coupling_relief": ["relation_relief_pressure", "pair_fire_margin", "relation_lock_proxy", "coupling_proxy"],
            "volatility_damping": ["stabilize_pressure", "de_risk_pressure", "burden", "collapse_proximity"],
            "uncertainty_probe": ["observe_pressure", "unresolved_proxy", "confidence_gap"],
            "exploration_injection": ["explore_pressure", "overconvergence_avoidance_pressure", "exploration_need", "safe_gate"],
            "relation_unlock": ["relation_relief_pressure", "relation_lock_proxy", "pair_fire_margin", "side_effect_risk_suppression"],
            "observe_only": ["observe_pressure", "low_confidence", "unresolved_proxy"],
            "cooldown": ["cooldown_pressure", "burden", "fatigue", "side_effect_risk", "recent_harmful_fire_rate", "recent_side_effect_score"],
            "no_op": ["low_fire_permission", "negative_local_or_pair_margin"],
            "hold_shadow": ["unresolved_proxy", "mid_confidence", "mixed_permission_and_side_effect"],
        },
        "suppression_evidence": reasons,
        "history_evidence": {
            "recent_correct_fire_rate": history.recent_correct_fire_rate,
            "recent_harmful_fire_rate": history.recent_harmful_fire_rate,
            "recent_side_effect_score": history.recent_side_effect_score,
            "recent_cooldown_state": history.recent_cooldown_state,
            "recent_no_op_worsening": history.recent_no_op_worsening,
            "recent_wrong_direction_rate": history.recent_wrong_direction_rate,
        },
    }
    return InsurancePolicyOutput(
        fire_permission_score=fire_permission_score,
        action_mass_cap=action_mass_cap,
        channel_weights=channel_weights,
        non_action_decision=non_action_decision,
        cooldown_score=cooldown_score,
        suppression_reason=suppression_reason,
        evidence_trace=evidence_trace,
        input_boundary_flags=boundary_flags,
    )


def bundle_from_21b_a_summary(row) -> tuple[UpperPressureBundle, LowerDistributionBundle, ActionHistoryBundle]:
    """Convert a 21B-A summary-like row without reading scenario labels."""
    get = row.get if hasattr(row, "get") else lambda key, default=0.0: getattr(row, key, default)
    side_effect_score = _clip(get("side_effect_score", 0.0))
    wrong_direction = _clip(get("wrong_direction_count", 0.0) / 4.0)
    primary_match = _clip(get("primary_effect_match_count", 0.0) / 4.0)
    improvement = _clip((get("outcome_improvement_vs_no_op", 0.0) + 1.0) / 2.0)
    missing_count = len(get("missing_input_flags", []) or [])
    upper = UpperPressureBundle(
        stabilize_pressure=0.35,
        explore_pressure=0.25,
        buffer_pressure=0.35,
        relation_relief_pressure=_clip(_margin01(get("pair_fire_margin", 0.0))),
        reversibility_pressure=0.35,
        cooldown_pressure=side_effect_score,
        observe_pressure=_clip(missing_count / 3.0),
        de_risk_pressure=_clip(_margin01(get("local_fire_margin", 0.0))),
        overconvergence_avoidance_pressure=0.20,
    )
    lower = LowerDistributionBundle(
        local_fire_margin=get("local_fire_margin", 0.0),
        pair_fire_margin=get("pair_fire_margin", 0.0),
        confidence=_clip(1.0 - 0.25 * missing_count),
        fatigue=_clip(get("fatigue_delta", 0.0)),
        reversibility_need=_clip(1.0 - get("reversibility_delta", 0.0)),
        relation_lock_proxy=_clip(_margin01(get("pair_fire_margin", 0.0))),
        coupling_proxy=_clip(_margin01(get("pair_fire_margin", 0.0))),
        unresolved_proxy=_clip(missing_count / 3.0),
        side_effect_risk=side_effect_score,
    )
    history = ActionHistoryBundle(
        recent_correct_fire_rate=primary_match,
        recent_harmful_fire_rate=_clip(side_effect_score + wrong_direction),
        recent_side_effect_score=side_effect_score,
        recent_no_op_worsening=_clip(1.0 - improvement),
        recent_wrong_direction_rate=wrong_direction,
    )
    return upper, lower, history


def safe_bundle() -> tuple[UpperPressureBundle, LowerDistributionBundle, ActionHistoryBundle]:
    return (
        UpperPressureBundle(stabilize_pressure=0.5, explore_pressure=0.45, buffer_pressure=0.55, relation_relief_pressure=0.5, reversibility_pressure=0.5, de_risk_pressure=0.55, overconvergence_avoidance_pressure=0.45),
        LowerDistributionBundle(local_no_action_risk_estimate=0.55, local_action_side_effect_cost_estimate=0.15, local_fire_margin=0.35, pair_no_action_risk_estimate=0.45, pair_action_side_effect_cost_estimate=0.15, pair_fire_margin=0.25, confidence=0.85, burden=0.20, fatigue=0.18, collapse_proximity=0.20, reversibility_need=0.45, relation_lock_proxy=0.45, coupling_proxy=0.42, exploration_need=0.45, unresolved_proxy=0.20, side_effect_risk=0.15),
        ActionHistoryBundle(recent_correct_fire_rate=0.50, recent_harmful_fire_rate=0.10, recent_side_effect_score=0.10, recent_no_op_worsening=0.20),
    )


def with_field(bundle, **updates):
    values = {field.name: getattr(bundle, field.name) for field in fields(bundle)}
    values.update(updates)
    return type(bundle)(**values)


def policy_with(**updates):
    upper, lower, history = safe_bundle()
    upper_updates = {k: v for k, v in updates.items() if hasattr(upper, k)}
    lower_updates = {k: v for k, v in updates.items() if hasattr(lower, k)}
    history_updates = {k: v for k, v in updates.items() if hasattr(history, k)}
    return functional_insurance_policy(with_field(upper, **upper_updates), with_field(lower, **lower_updates), with_field(history, **history_updates))


def test_functional_insurance_policy_exports_expected_fields():
    output = policy_with()
    assert set(output.__dataclass_fields__) == {"fire_permission_score", "action_mass_cap", "channel_weights", "non_action_decision", "cooldown_score", "suppression_reason", "evidence_trace", "input_boundary_flags"}
    assert set(output.channel_weights) == set(CHANNELS)
    assert output.non_action_decision in NON_ACTION_DECISIONS


def test_fire_permission_increases_with_local_fire_margin():
    assert policy_with(local_fire_margin=0.60).fire_permission_score >= policy_with(local_fire_margin=-0.20).fire_permission_score


def test_fire_permission_increases_with_pair_fire_margin():
    assert policy_with(pair_fire_margin=0.60).fire_permission_score >= policy_with(pair_fire_margin=-0.20).fire_permission_score


def test_fire_permission_decreases_with_side_effect_cost():
    assert policy_with(local_action_side_effect_cost_estimate=0.75).fire_permission_score <= policy_with(local_action_side_effect_cost_estimate=0.05).fire_permission_score


def test_fire_permission_decreases_with_side_effect_risk():
    assert policy_with(side_effect_risk=0.80).fire_permission_score <= policy_with(side_effect_risk=0.05).fire_permission_score


def test_action_mass_cap_decreases_with_low_confidence():
    assert policy_with(confidence=0.25).action_mass_cap <= policy_with(confidence=0.90).action_mass_cap


def test_action_mass_cap_decreases_with_high_burden():
    assert policy_with(burden=0.80).action_mass_cap <= policy_with(burden=0.10).action_mass_cap


def test_action_mass_cap_decreases_with_high_fatigue():
    assert policy_with(fatigue=0.80).action_mass_cap <= policy_with(fatigue=0.10).action_mass_cap


def test_cooldown_score_increases_with_recent_harmful_fire():
    assert policy_with(recent_harmful_fire_rate=0.80).cooldown_score >= policy_with(recent_harmful_fire_rate=0.05).cooldown_score


def test_cooldown_score_increases_with_recent_side_effect_score():
    assert policy_with(recent_side_effect_score=0.80).cooldown_score >= policy_with(recent_side_effect_score=0.05).cooldown_score


def test_pair_fire_margin_increases_coupling_relief_weight():
    assert policy_with(pair_fire_margin=0.80).channel_weights["coupling_relief"] >= policy_with(pair_fire_margin=-0.40).channel_weights["coupling_relief"]


def test_relation_lock_increases_relation_unlock_weight():
    assert policy_with(relation_lock_proxy=0.85).channel_weights["relation_unlock"] >= policy_with(relation_lock_proxy=0.10).channel_weights["relation_unlock"]


def test_reversibility_need_increases_buffer_weight():
    assert policy_with(reversibility_need=0.85).channel_weights["buffer_increase"] >= policy_with(reversibility_need=0.10).channel_weights["buffer_increase"]


def test_exploration_need_increases_exploration_weight_when_safe():
    assert policy_with(exploration_need=0.85, burden=0.05, fatigue=0.05, side_effect_risk=0.05).channel_weights["exploration_injection"] >= policy_with(exploration_need=0.10, burden=0.05, fatigue=0.05, side_effect_risk=0.05).channel_weights["exploration_injection"]


def test_fatigue_suppresses_exploration_weight():
    assert policy_with(fatigue=0.85).channel_weights["exploration_injection"] <= policy_with(fatigue=0.05).channel_weights["exploration_injection"]


def test_burden_suppresses_exploration_weight():
    assert policy_with(burden=0.85).channel_weights["exploration_injection"] <= policy_with(burden=0.05).channel_weights["exploration_injection"]


def test_side_effect_risk_suppresses_exploration_weight():
    assert policy_with(side_effect_risk=0.85).channel_weights["exploration_injection"] <= policy_with(side_effect_risk=0.05).channel_weights["exploration_injection"]


def test_zero_upper_pressure_suppresses_action_mass():
    lower = safe_bundle()[1]
    history = safe_bundle()[2]
    output = functional_insurance_policy(UpperPressureBundle(), lower, history)
    assert output.action_mass_cap <= 0.05


def test_dangerous_lower_terrain_suppresses_action_mass_even_with_high_upper_pressure():
    upper = UpperPressureBundle(stabilize_pressure=1, explore_pressure=1, buffer_pressure=1, relation_relief_pressure=1, reversibility_pressure=1, de_risk_pressure=1, overconvergence_avoidance_pressure=1)
    lower = with_field(safe_bundle()[1], burden=0.9, fatigue=0.9, collapse_proximity=0.85, side_effect_risk=0.9, confidence=0.55)
    output = functional_insurance_policy(upper, lower, safe_bundle()[2])
    assert output.action_mass_cap <= 0.12


def test_low_confidence_high_unresolved_prefers_observe_or_hold_shadow():
    assert policy_with(confidence=0.20, unresolved_proxy=0.85, observe_pressure=0.6).non_action_decision in {"observe_only", "hold_shadow"}


def test_high_harmful_history_prefers_cooldown():
    assert policy_with(recent_harmful_fire_rate=0.95, recent_side_effect_score=0.85, recent_cooldown_state=0.8).non_action_decision == "cooldown"


def test_non_action_decision_is_not_mapped_to_buffer_increase():
    for decision_output in [
        policy_with(confidence=0.2, unresolved_proxy=0.9, observe_pressure=0.7),
        policy_with(recent_harmful_fire_rate=0.95, recent_side_effect_score=0.9, recent_cooldown_state=0.8),
        policy_with(fire_permission_score=0.0) if False else policy_with(local_fire_margin=-0.9, pair_fire_margin=-0.9, confidence=0.4),
        policy_with(side_effect_risk=0.75, local_fire_margin=0.8, pair_fire_margin=0.8),
    ]:
        if decision_output.non_action_decision in {"observe_only", "cooldown", "hold_shadow", "no_op"}:
            assert decision_output.action_mass_cap <= 0.12
            assert decision_output.channel_weights[decision_output.non_action_decision] >= 0.0
            assert decision_output.channel_weights["buffer_increase"] < 0.8


def test_evidence_trace_records_positive_and_negative_reasons():
    output = policy_with(local_fire_margin=0.4, pair_fire_margin=0.3, fatigue=0.8, side_effect_risk=0.8)
    assert "positive_fire_evidence" in output.evidence_trace
    assert "negative_fire_evidence" in output.evidence_trace
    assert "channel_evidence" in output.evidence_trace
    assert "suppression_evidence" in output.evidence_trace
    assert "history_evidence" in output.evidence_trace
    assert output.evidence_trace["positive_fire_evidence"]
    assert output.evidence_trace["negative_fire_evidence"]


def test_scenario_label_is_not_policy_input():
    signature = inspect.signature(functional_insurance_policy)
    assert "scenario_label" not in signature.parameters
    assert "case_name" not in signature.parameters
    assert "run_id" not in signature.parameters


def test_policy_output_is_stable_under_scenario_label_change():
    row_a = {"scenario_label_for_audit_only": "irreversible", "local_fire_margin": 0.3, "pair_fire_margin": 0.2, "side_effect_score": 0.1, "primary_effect_match_count": 2, "wrong_direction_count": 0, "missing_input_flags": []}
    row_b = dict(row_a, scenario_label_for_audit_only="relation")
    assert bundle_from_21b_a_summary(row_a) == bundle_from_21b_a_summary(row_b)
    assert functional_insurance_policy(*bundle_from_21b_a_summary(row_a)) == functional_insurance_policy(*bundle_from_21b_a_summary(row_b))


def test_production_runtime_files_are_not_modified():
    changed = subprocess.run(["git", "diff", "--name-only", "--"] + [str(path) for path in PRODUCTION_RUNTIME_PATHS], check=True, text=True, capture_output=True).stdout.splitlines()
    assert changed == []
    policy_source = inspect.getsource(functional_insurance_policy)
    assert "ActionPlanner" not in policy_source
    assert "ActionModule" not in policy_source
    assert "ParameterBox" not in policy_source
    assert "ShadowBox" not in policy_source


def test_channel_weights_are_all_bounded_between_zero_and_one():
    output = policy_with(burden=1.0, fatigue=1.0, side_effect_risk=1.0, recent_harmful_fire_rate=1.0)
    assert all(0.0 <= value <= 1.0 for value in output.channel_weights.values())


def test_fire_permission_score_is_bounded_between_zero_and_one():
    assert 0.0 <= policy_with(local_fire_margin=1.0, confidence=1.0).fire_permission_score <= 1.0
    assert 0.0 <= policy_with(local_fire_margin=-1.0, confidence=0.0, side_effect_risk=1.0).fire_permission_score <= 1.0


def test_action_mass_cap_is_bounded_between_zero_and_one():
    assert 0.0 <= policy_with().action_mass_cap <= 1.0


def test_cooldown_score_is_bounded_between_zero_and_one():
    assert 0.0 <= policy_with(cooldown_pressure=1.0, burden=1.0, fatigue=1.0, side_effect_risk=1.0).cooldown_score <= 1.0


def test_history_harmful_fire_reduces_exploration_and_probe_mass():
    high = policy_with(recent_harmful_fire_rate=0.9)
    low = policy_with(recent_harmful_fire_rate=0.0)
    assert high.channel_weights["exploration_injection"] <= low.channel_weights["exploration_injection"]
    assert high.channel_weights["uncertainty_probe"] <= low.channel_weights["uncertainty_probe"]


def test_recent_no_op_worsening_increases_permission_when_side_effect_is_low():
    assert policy_with(recent_no_op_worsening=0.9, side_effect_risk=0.05).fire_permission_score >= policy_with(recent_no_op_worsening=0.0, side_effect_risk=0.05).fire_permission_score


def test_hold_shadow_for_mixed_risk_high_permission_and_high_side_effect():
    output = policy_with(local_fire_margin=0.9, pair_fire_margin=0.8, confidence=0.9, side_effect_risk=0.65, burden=0.1, fatigue=0.1)
    assert output.non_action_decision == "hold_shadow"


def test_bundle_from_21b_a_summary_does_not_use_scenario_label():
    source = inspect.getsource(bundle_from_21b_a_summary)
    body = source.split(":", 1)[1]
    assert "scenario_label" not in body
    assert "case_name" not in body
