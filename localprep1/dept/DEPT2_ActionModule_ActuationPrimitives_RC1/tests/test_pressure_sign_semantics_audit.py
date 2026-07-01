"""Tests for PressureSignSemanticsAudit RC1."""

import pandas as pd

from action_module.pressure_sign_semantics_audit import (
    sign_label,
    semantic_for,
    build_outcome_increment,
    build_sign_semantics_audit,
    audit_summary_json,
)


def test_sign_to_semantic_contract():
    assert sign_label(-0.1) == "decrease"
    effect, family, route = semantic_for("adoption_threshold", "decrease")
    assert effect == "adoption_barrier_relief"
    assert family == "adoption_opening"


def test_outcome_increment():
    metrics = pd.DataFrame([
        {
            "run_seed": 42,
            "run_scenario": "normal",
            "loop_step": 0,
            "gt_conflict_mean": 0.5,
            "gt_uncertainty_mean": 0.5,
            "gt_exploration_mean": 0.5,
            "gt_overconvergence_mean": 0.5,
            "m_mean_overall": 0.5,
        },
        {
            "run_seed": 42,
            "run_scenario": "normal",
            "loop_step": 1,
            "gt_conflict_mean": 0.4,
            "gt_uncertainty_mean": 0.45,
            "gt_exploration_mean": 0.6,
            "gt_overconvergence_mean": 0.4,
            "m_mean_overall": 0.55,
        },
    ])
    inc = build_outcome_increment(metrics)
    assert len(inc) == 1
    assert inc.iloc[0]["observed_delta_conflict"] < 0
    assert inc.iloc[0]["observed_delta_exploration"] > 0


def test_build_audit_minimal():
    pressure = pd.DataFrame([
        {
            "seed": 42,
            "scenario": "normal",
            "t": 0,
            "approved_adoption_threshold": -0.1,
        }
    ])
    intents = pd.DataFrame([
        {
            "seed": 42,
            "scenario": "normal",
            "t": 0,
            "pressure_component": "adoption_threshold",
            "component_direction": "decrease",
            "semantic_effect": "adoption_barrier_relief",
            "intent_family": "adoption_opening",
            "suggested_control_route": "lower_candidate_barrier",
            "component_signed_value": -0.1,
            "component_magnitude": 0.1,
            "h11_received_abs_pressure": 0.1,
            "relevant_to_exploration_injection": True,
            "relevant_to_relation_unlock": True,
            "relevant_to_volatility_damping": False,
            "relevant_to_uncertainty_probe": False,
            "relevant_to_coupling_relief": True,
            "relevant_to_buffer_increase": False,
        }
    ])
    plans = pd.DataFrame([
        {
            "run_seed": 42,
            "run_scenario": "normal",
            "loop_step": 0,
            "dominant_pressure_component": "adoption_threshold",
            "dominant_semantic_effect": "adoption_barrier_relief",
            "action_primitive": "peripheral_explore",
            "primitive_sequence": "peripheral_explore",
            "action_channel": "exploration_injection",
            "action_strength": 0.1,
            "planner_confidence": 0.8,
            "entity_id": "E000",
        }
    ])
    actions = pd.DataFrame([
        {
            "run_seed": 42,
            "run_scenario": "normal",
            "loop_step": 0,
            "dominant_pressure_component": "adoption_threshold",
            "dominant_semantic_effect": "adoption_barrier_relief",
            "action_primitive": "peripheral_explore",
            "primitive_sequence": "peripheral_explore",
            "action_channel": "exploration_injection",
            "action_strength": 0.1,
            "entity_id": "E000",
        }
    ])
    metrics = pd.DataFrame([
        {
            "run_seed": 42,
            "run_scenario": "normal",
            "loop_step": 0,
            "gt_conflict_mean": 0.5,
            "gt_uncertainty_mean": 0.5,
            "gt_exploration_mean": 0.5,
            "gt_overconvergence_mean": 0.5,
            "m_mean_overall": 0.5,
        },
        {
            "run_seed": 42,
            "run_scenario": "normal",
            "loop_step": 1,
            "gt_conflict_mean": 0.5,
            "gt_uncertainty_mean": 0.55,
            "gt_exploration_mean": 0.6,
            "gt_overconvergence_mean": 0.4,
            "m_mean_overall": 0.52,
        },
    ])
    outputs = build_sign_semantics_audit(pressure, intents, plans, actions, metrics)
    summary = audit_summary_json(outputs)
    assert summary["all_sanity_checks_passed"]
    assert summary["sign_to_intent_match_rate"] == 1.0
    assert summary["plan_to_action_present_rate"] == 1.0
