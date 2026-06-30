"""Tests for ProbeRestraintPrimitivePatch RC1."""

import pandas as pd

from DEPT2_ActionModule_ActuationPrimitives_RC1.action_module.probe_restraint_primitive_patch import (
    patch_probe_restraint_action_frame,
    run_role_split_replay,
    summarize_role_split,
    patch_summary_json,
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


def test_patch_splits_roles():
    patched, table = patch_probe_restraint_action_frame(_action_frame())
    assert len(table) == 2
    assert set(patched["probe_role"]) == {"stabilization_guard", "direct_probe_restraint"}
    assert "sandbox_probe_entry_down_stabilization" in set(patched["semantic_effect"])


def test_role_split_replay_passes_each_role():
    patched, _ = patch_probe_restraint_action_frame(_action_frame())
    old_contract = {"exploration": -1, "overconvergence": 1}
    patched_contract = {"conflict": -1, "uncertainty": -1, "m_overall": 1}
    alignment = run_role_split_replay(patched, old_contract, patched_contract)
    summary = summarize_role_split(alignment)
    assert set(summary["probe_role"]) == {"stabilization_guard", "direct_probe_restraint"}
    assert (summary["role_contract_pass_rate"] >= 1.0).all()


def test_summary_completed():
    patched, table = patch_probe_restraint_action_frame(_action_frame())
    old_contract = {"exploration": -1, "overconvergence": 1}
    patched_contract = {"conflict": -1, "uncertainty": -1, "m_overall": 1}
    alignment = run_role_split_replay(patched, old_contract, patched_contract)
    summary = summarize_role_split(alignment)
    js = patch_summary_json({
        "probe_restraint_primitive_patch_table": table,
        "probe_restraint_primitive_patched_action_frame": patched,
        "probe_restraint_primitive_patch_alignment": alignment,
        "probe_restraint_primitive_patch_summary": summary,
    })
    assert js["status"] == "completed"
    assert js["all_sanity_checks_passed"]
