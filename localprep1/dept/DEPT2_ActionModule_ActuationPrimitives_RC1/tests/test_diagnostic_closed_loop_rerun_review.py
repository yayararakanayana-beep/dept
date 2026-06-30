"""Tests for DiagnosticClosedLoopRerunReview RC1."""

import pandas as pd

from DEPT2_ActionModule_ActuationPrimitives_RC1.action_module.diagnostic_closed_loop_rerun_review import (
    build_semantic_family_review,
    build_scenario_review,
    build_next_action_plan,
    review_summary_json,
)


def _semantic_summary():
    return pd.DataFrame([
        {
            "semantic_effect": "adoption_barrier_relief",
            "intent_family": "adoption_opening",
            "mean_alignment_score": 1.0,
            "alignment_pass_rate": 1.0,
            "mean_delta_conflict": 0.0,
            "mean_delta_uncertainty": 0.1,
            "mean_delta_exploration": 0.1,
            "mean_delta_overconvergence": -0.1,
            "mean_delta_m_overall": 0.1,
            "action_primitives": "diagnostic_adoption_opening_probe",
            "action_channels": "exploration_injection",
        },
        {
            "semantic_effect": "rollback_guard_down",
            "intent_family": "safety_relaxation",
            "mean_alignment_score": 0.0,
            "alignment_pass_rate": 0.0,
            "mean_delta_conflict": -0.1,
            "mean_delta_uncertainty": -0.1,
            "mean_delta_exploration": 0.0,
            "mean_delta_overconvergence": 0.0,
            "mean_delta_m_overall": 0.1,
            "action_primitives": "diagnostic_rollback_relaxation_probe",
            "action_channels": "buffer_increase",
        },
        {
            "semantic_effect": "sensitivity_opening",
            "intent_family": "response_opening",
            "mean_alignment_score": 0.33,
            "alignment_pass_rate": 0.0,
            "mean_delta_conflict": -0.1,
            "mean_delta_uncertainty": 0.0,
            "mean_delta_exploration": 0.0,
            "mean_delta_overconvergence": -0.1,
            "mean_delta_m_overall": 0.1,
            "action_primitives": "diagnostic_sensitivity_opening",
            "action_channels": "coupling_relief",
        },
        {
            "semantic_effect": "intensity_cap_brake",
            "intent_family": "safety_cap",
            "mean_alignment_score": 0.66,
            "alignment_pass_rate": 1.0,
            "mean_delta_conflict": -0.1,
            "mean_delta_uncertainty": -0.1,
            "mean_delta_exploration": 0.0,
            "mean_delta_overconvergence": 0.0,
            "mean_delta_m_overall": 0.1,
            "action_primitives": "buffer_first",
            "action_channels": "buffer_increase",
        },
    ])


def test_semantic_family_review_classifies():
    review = build_semantic_family_review(_semantic_summary())
    classes = set(review["review_class"])
    assert "ready_current_mapping" in classes
    assert "positive_control_keep" in classes
    assert "expected_effect_contract_review" in classes
    assert "primitive_mapping_repair" in classes


def test_next_action_plan_has_mapping_repair():
    review = build_semantic_family_review(_semantic_summary())
    plan = build_next_action_plan(review, pd.DataFrame())
    assert plan.iloc[0]["next_task"] == "DiagnosticPrimitiveMappingRepair_RC1"


def test_review_summary_completed():
    semantic_review = build_semantic_family_review(_semantic_summary())
    outputs = {
        "diagnostic_rerun_semantic_family_review": semantic_review,
        "diagnostic_rerun_scenario_review": pd.DataFrame({"scenario_review_class": ["scenario_direction_good_alignment_mixed"]}),
        "diagnostic_rerun_review_class_summary": pd.DataFrame(),
        "diagnostic_rerun_next_action_plan": build_next_action_plan(semantic_review, pd.DataFrame()),
    }
    summary = review_summary_json(outputs, rerun_summary={"task": "DiagnosticClosedLoopRerun_RC1", "mean_isolated_alignment_score": 0.5, "isolated_alignment_pass_rate": 0.5})
    assert summary["status"] == "completed"
    assert summary["recommended_next_task"] == "DiagnosticPrimitiveMappingRepair_RC1"
