"""Tests for ExpectedEffectContractPatch RC1."""

import pandas as pd

from DEPT2_ActionModule_ActuationPrimitives_RC1.action_module.expected_effect_contract_patch import (
    build_patched_contracts,
    evaluate_patched_alignment,
    summarize_patched_alignment,
    patch_summary_json,
)


def _semantic_outcome():
    return pd.DataFrame([
        {
            "semantic_effect": "diagnostic_resolution_down",
            "intent_family": "observation_cost_saving",
            "semantic_outcome_details": "conflict:expected=1,observed=0,match=False; uncertainty:expected=1,observed=0,match=False; m_overall:expected=-1,observed=0,match=False",
        },
        {
            "semantic_effect": "sandbox_probe_entry_up",
            "intent_family": "exploration_observation",
            "semantic_outcome_details": "exploration:expected=1,observed=0,match=False",
        },
    ])


def _candidates():
    return pd.DataFrame([
        {
            "semantic_effect": "diagnostic_resolution_down",
            "intent_family": "observation_cost_saving",
            "candidate_contract": "conflict:-1;uncertainty:-1;m_overall:+1",
            "candidate_reason": "test candidate",
            "contract_review_class": "contract_inverted_or_wrong_direction",
        }
    ])


def _alignment():
    return pd.DataFrame([
        {
            "semantic_effect": "diagnostic_resolution_down",
            "intent_family": "observation_cost_saving",
            "repaired_alignment_score": 0.0,
            "repaired_alignment_pass": False,
            "action_mass": 0.01,
            "observed_delta_conflict": -0.1,
            "observed_delta_uncertainty": -0.1,
            "observed_delta_m_overall": 0.1,
        },
        {
            "semantic_effect": "sandbox_probe_entry_up",
            "intent_family": "exploration_observation",
            "repaired_alignment_score": 1.0,
            "repaired_alignment_pass": True,
            "action_mass": 0.01,
            "observed_delta_exploration": 0.1,
        },
    ])


def test_patch_freezes_candidate_and_retains_old():
    patched = build_patched_contracts(_semantic_outcome(), _candidates())
    assert len(patched) == 2
    assert patched.loc[patched.semantic_effect == "diagnostic_resolution_down", "patch_source"].iloc[0] == "candidate_contract_frozen"
    assert patched.loc[patched.semantic_effect == "sandbox_probe_entry_up", "patch_source"].iloc[0] == "old_contract_retained"


def test_patched_alignment_scores_candidate():
    patched = build_patched_contracts(_semantic_outcome(), _candidates())
    alignment = evaluate_patched_alignment(_alignment(), patched)
    row = alignment[alignment.semantic_effect == "diagnostic_resolution_down"].iloc[0]
    assert row["patched_alignment_pass"] is True or bool(row["patched_alignment_pass"])


def test_summary_completed():
    patched = build_patched_contracts(_semantic_outcome(), _candidates())
    alignment = evaluate_patched_alignment(_alignment(), patched)
    sem = summarize_patched_alignment(alignment)
    summary = patch_summary_json({
        "expected_effect_contract_patch_table": patched,
        "expected_effect_contract_patch_alignment": alignment,
        "expected_effect_contract_patch_semantic_summary": sem,
        "expected_effect_contract_patch_comparison": sem,
        "expected_effect_contract_patch_target_comparison": sem[sem.patch_source.str.contains("candidate_contract_frozen", na=False)],
    })
    assert summary["status"] == "completed"
    assert summary["patched_contract_count"] == 1
