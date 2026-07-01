"""Tests for PressureOutcomeAlignmentAudit RC2."""

import pandas as pd

from DEPT2_ActionModule_ActuationPrimitives_RC1.action_module.pressure_outcome_alignment_audit_rc2 import (
    build_semantic_primary_alignment,
    build_primitive_primary_alignment,
    rc2_summary_json,
)


def test_semantic_primary_alignment_with_action_coverage():
    sem = pd.DataFrame([{
        "run_seed": 42,
        "run_scenario": "normal",
        "loop_step": 0,
        "pressure_component": "exploration_frequency",
        "component_direction": "increase",
        "semantic_effect": "exploration_attempt_frequency_up",
        "intent_family": "exploration_attempt",
        "expected_feature_count": 3,
        "semantic_outcome_match_rate": 2/3,
        "semantic_outcome_details": "x",
        "semantic_outcome_verdict": "semantic_aligned",
        "observed_delta_conflict": 0.0,
        "observed_delta_uncertainty": 0.01,
        "observed_delta_exploration": 0.01,
        "observed_delta_overconvergence": -0.01,
        "observed_delta_m_overall": 0.0,
    }])
    chain = pd.DataFrame([{
        "run_seed": 42,
        "run_scenario": "normal",
        "loop_step": 0,
        "pressure_component": "exploration_frequency",
        "component_direction": "increase",
        "semantic_effect": "exploration_attempt_frequency_up",
        "semantic_to_plan_present": True,
        "plan_to_action_present": True,
        "planned_rows": 2,
        "action_rows": 2,
        "action_mass": 0.3,
        "action_primitive": "peripheral_explore",
        "primitive_sequence": "explore",
        "action_channel": "exploration_injection",
        "suggested_control_route": "increase_trials",
    }])
    out = build_semantic_primary_alignment(sem, chain)
    assert len(out) == 1
    assert out.iloc[0]["primary_alignment_pass"]
    assert out.iloc[0]["rc2_alignment_verdict"] == "semantic_aligned_and_actuated"


def test_primitive_primary_alignment():
    prim = pd.DataFrame([{
        "run_seed": 42,
        "run_scenario": "normal",
        "loop_step": 0,
        "dominant_pressure_component": "exploration_frequency",
        "dominant_semantic_effect": "exploration_attempt_frequency_up",
        "action_primitive": "peripheral_explore",
        "primitive_sequence": "explore",
        "action_channel": "exploration_injection",
        "action_rows": 3,
        "action_mass": 0.4,
        "expected_feature_count": 3,
        "primitive_outcome_match_rate": 2/3,
        "primitive_outcome_details": "x",
        "primitive_outcome_verdict": "primitive_aligned",
        "observed_delta_conflict": 0.0,
        "observed_delta_uncertainty": 0.01,
        "observed_delta_exploration": 0.01,
        "observed_delta_overconvergence": -0.01,
        "observed_delta_m_overall": 0.0,
    }])
    out = build_primitive_primary_alignment(prim)
    assert len(out) == 1
    assert out.iloc[0]["primary_alignment_pass"]
    assert out.iloc[0]["rc2_alignment_verdict"] == "primitive_aligned_and_actuated"


def test_rc2_summary_json_completed():
    sem_primary = pd.DataFrame([{
        "primary_alignment_pass": True,
        "primary_alignment_score": 0.66,
        "semantic_to_plan_present": True,
        "plan_to_action_present": True,
    }])
    prim_primary = pd.DataFrame([{
        "primary_alignment_pass": False,
        "primary_alignment_score": 0.33,
    }])
    summary = rc2_summary_json({
        "pressure_outcome_alignment_rc2_semantic_primary": sem_primary,
        "pressure_outcome_alignment_rc2_primitive_primary": prim_primary,
        "pressure_outcome_alignment_rc2_chain_coverage": pd.DataFrame([{"x": 1}]),
        "pressure_outcome_alignment_rc2_semantic_summary": pd.DataFrame(),
        "pressure_outcome_alignment_rc2_primitive_summary": pd.DataFrame(),
        "pressure_outcome_alignment_rc2_review": pd.DataFrame([{"x": 1}]),
    })
    assert summary["status"] == "completed"
    assert summary["semantic_alignment_rate"] == 1.0
    assert summary["primitive_alignment_rate"] == 0.0
