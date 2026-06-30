"""Tests for DiagnosticPrimitiveMappingRepair RC1."""

import pandas as pd

from DEPT2_ActionModule_ActuationPrimitives_RC1.action_module.diagnostic_primitive_mapping_repair import (
    repair_action_frame,
    run_repaired_isolated_replay,
    MappingRepairConfig,
    repair_summary_json,
    summarize_repaired_alignment,
    build_comparison,
)


def _action_frame():
    return pd.DataFrame([
        {
            "run_seed": 42,
            "run_scenario": "normal",
            "loop_step": 0,
            "semantic_effect": "sensitivity_opening",
            "intent_family": "response_opening",
            "action_primitive": "diagnostic_sensitivity_opening",
            "primitive_sequence": "sensitivity_opening -> observe -> report",
            "action_channel": "coupling_relief",
            "action_strength": 0.03,
        },
        {
            "run_seed": 42,
            "run_scenario": "normal",
            "loop_step": 0,
            "semantic_effect": "update_frequency_down",
            "intent_family": "update_restraint",
            "action_primitive": "diagnostic_update_restraint",
            "primitive_sequence": "update_restraint -> observe",
            "action_channel": "buffer_increase",
            "action_strength": 0.03,
        },
    ])


def _semantic_outcome():
    return pd.DataFrame([
        {
            "semantic_effect": "sensitivity_opening",
            "semantic_outcome_details": "exploration:expected=1,observed=0,match=False; uncertainty:expected=1,observed=0,match=False; overconvergence:expected=-1,observed=0,match=False",
        },
        {
            "semantic_effect": "update_frequency_down",
            "semantic_outcome_details": "exploration:expected=-1,observed=0,match=False; uncertainty:expected=-1,observed=0,match=False; overconvergence:expected=1,observed=0,match=False",
        },
    ])


def test_repair_action_frame_changes_targets():
    repaired, table = repair_action_frame(_action_frame())
    assert len(table) == 2
    assert repaired.loc[repaired.semantic_effect == "sensitivity_opening", "action_channel"].iloc[0] == "exploration_injection"
    assert repaired.loc[repaired.semantic_effect == "update_frequency_down", "action_channel"].iloc[0] == "diagnostic_update_restraint"


def test_repaired_replay_outputs_alignment():
    repaired, _ = repair_action_frame(_action_frame())
    isolated = run_repaired_isolated_replay(repaired, _semantic_outcome(), MappingRepairConfig(noise_scale=0.0))
    assert len(isolated) == 2
    assert "repaired_alignment_score" in isolated.columns
    assert isolated["mapping_repair_applied"].all()


def test_summary_completed():
    repaired, table = repair_action_frame(_action_frame())
    isolated = run_repaired_isolated_replay(repaired, _semantic_outcome(), MappingRepairConfig(noise_scale=0.0))
    sem = summarize_repaired_alignment(isolated)
    old = pd.DataFrame({
        "semantic_effect": ["sensitivity_opening", "update_frequency_down"],
        "alignment_pass_rate": [0.0, 0.0],
        "mean_alignment_score": [0.33, 0.33],
        "action_channels": ["coupling_relief", "buffer_increase"],
        "action_primitives": ["old", "old"],
    })
    comp = build_comparison(old, sem)
    summary = repair_summary_json({
        "diagnostic_primitive_mapping_repair_table": table,
        "diagnostic_primitive_mapping_repaired_action_frame": repaired,
        "diagnostic_primitive_mapping_repair_isolated_alignment": isolated,
        "diagnostic_primitive_mapping_repair_semantic_summary": sem,
        "diagnostic_primitive_mapping_repair_comparison": comp,
        "diagnostic_primitive_mapping_repair_target_comparison": comp[comp.mapping_repair_applied_rate > 0],
    })
    assert summary["status"] == "completed"
    assert summary["target_count"] == 2
