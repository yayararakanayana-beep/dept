"""Tests for ExpectedEffectContractReview RC1."""

import pandas as pd

from DEPT2_ActionModule_ActuationPrimitives_RC1.action_module.expected_effect_contract_review import (
    parse_expected_contracts,
    build_expected_effect_contract_review,
    expected_contract_review_summary_json,
)


def _semantic_outcome():
    return pd.DataFrame([
        {
            "semantic_effect": "diagnostic_resolution_down",
            "intent_family": "observation_cost_saving",
            "semantic_outcome_details": "uncertainty:expected=1,observed=0,match=False; conflict:expected=1,observed=0,match=False; m_overall:expected=-1,observed=0,match=False",
        },
        {
            "semantic_effect": "update_frequency_up",
            "intent_family": "update_opening",
            "semantic_outcome_details": "exploration:expected=1,observed=0,match=False; overconvergence:expected=-1,observed=0,match=False; uncertainty:expected=1,observed=0,match=False",
        },
    ])


def _repaired_summary():
    return pd.DataFrame([
        {
            "semantic_effect": "diagnostic_resolution_down",
            "intent_family": "observation_cost_saving",
            "repaired_mean_delta_conflict": -0.1,
            "repaired_mean_delta_uncertainty": -0.1,
            "repaired_mean_delta_exploration": 0.0,
            "repaired_mean_delta_overconvergence": 0.0,
            "repaired_mean_delta_m_overall": 0.1,
        },
        {
            "semantic_effect": "update_frequency_up",
            "intent_family": "update_opening",
            "repaired_mean_delta_conflict": -0.1,
            "repaired_mean_delta_uncertainty": -0.1,
            "repaired_mean_delta_exploration": 0.1,
            "repaired_mean_delta_overconvergence": -0.1,
            "repaired_mean_delta_m_overall": 0.1,
        },
    ])


def test_parse_expected_contracts():
    parsed = parse_expected_contracts(_semantic_outcome())
    assert len(parsed) == 6
    assert set(parsed["semantic_effect"]) == {"diagnostic_resolution_down", "update_frequency_up"}


def test_contract_review_improves_candidate_score():
    outputs = build_expected_effect_contract_review(
        _semantic_outcome(),
        _repaired_summary(),
        targets=["diagnostic_resolution_down", "update_frequency_up"],
    )
    review = outputs["expected_effect_contract_review_table"]
    assert not review.empty
    assert (review["candidate_contract_alignment_score"] > review["old_contract_alignment_score"]).all()


def test_summary_completed():
    outputs = build_expected_effect_contract_review(
        _semantic_outcome(),
        _repaired_summary(),
        targets=["diagnostic_resolution_down", "update_frequency_up"],
    )
    summary = expected_contract_review_summary_json(outputs)
    assert summary["status"] == "completed"
    assert summary["mean_candidate_contract_alignment_score"] > summary["mean_old_contract_alignment_score"]
