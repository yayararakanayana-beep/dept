"""Tests for ProbeRestraintPrimitiveCheck RC1."""

import pandas as pd

from DEPT2_ActionModule_ActuationPrimitives_RC1.action_module.probe_restraint_primitive_check import (
    make_probe_variants,
    run_probe_variant_replay,
    summarize_probe_variants,
    decide_probe_policy,
    probe_check_summary_json,
)


def _action_frame():
    return pd.DataFrame([
        {
            "run_seed": 42,
            "run_scenario": "normal",
            "loop_step": 0,
            "semantic_effect": "sandbox_probe_entry_down",
            "intent_family": "probe_restraint",
            "action_primitive": "diagnostic_probe_restraint",
            "primitive_sequence": "probe_restraint -> observe",
            "action_channel": "buffer_increase",
            "action_strength": 0.03,
        }
    ])


def test_make_probe_variants():
    variants = make_probe_variants(_action_frame())
    assert set(variants["probe_variant"]) == {
        "current_buffer_style",
        "direct_probe_restraint",
        "hybrid_probe_restraint",
    }


def test_probe_variant_replay_runs():
    variants = make_probe_variants(_action_frame())
    old_contract = {"exploration": -1, "overconvergence": 1}
    patched_contract = {"conflict": -1, "uncertainty": -1, "m_overall": 1}
    alignment = run_probe_variant_replay(variants, old_contract, patched_contract)
    assert len(alignment) == 3
    assert "old_contract_alignment_score" in alignment.columns
    assert "patched_contract_alignment_score" in alignment.columns


def test_summary_completed():
    variants = make_probe_variants(_action_frame())
    old_contract = {"exploration": -1, "overconvergence": 1}
    patched_contract = {"conflict": -1, "uncertainty": -1, "m_overall": 1}
    alignment = run_probe_variant_replay(variants, old_contract, patched_contract)
    summary = summarize_probe_variants(alignment)
    decision = decide_probe_policy(summary)
    js = probe_check_summary_json({
        "probe_restraint_variant_action_frame": variants,
        "probe_restraint_variant_alignment": alignment,
        "probe_restraint_variant_summary": summary,
        "probe_restraint_policy_decision": decision,
    })
    assert js["status"] == "completed"
    assert js["variant_count"] == 3
