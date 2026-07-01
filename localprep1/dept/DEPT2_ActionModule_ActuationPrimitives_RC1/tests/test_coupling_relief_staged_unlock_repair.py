"""Tests for CouplingReliefStagedUnlockRepair RC1."""

import pandas as pd

from DEPT2_ActionModule_ActuationPrimitives_RC1.action_module.coupling_relief_staged_unlock_repair import (
    build_staged_unlock_targets,
    run_sequence_variant_replay,
    summarize_sequence_variants,
    build_repaired_sequence_policy,
    sequence_repair_summary_json,
)


def _chain():
    return pd.DataFrame([
        {
            "run_seed": 42,
            "run_scenario": "normal",
            "loop_step": 0,
            "semantic_effect": "hysteresis_guard_down",
            "intent_family": "switching_flexibility",
            "primitive_sequence": "coupling_relief -> staged_unlock",
            "action_primitive": "coupling_relief_first",
            "action_channel": "coupling_relief",
            "max_component_magnitude": 0.08,
            "mean_planned_strength": 0.5,
        },
        {
            "run_seed": 42,
            "run_scenario": "normal",
            "loop_step": 0,
            "semantic_effect": "hysteresis_guard_down",
            "intent_family": "switching_flexibility",
            "primitive_sequence": "coupling_relief -> staged_unlock",
            "action_primitive": "staged_relation_unlock",
            "action_channel": "relation_unlock",
            "max_component_magnitude": 0.08,
            "mean_planned_strength": 0.5,
        },
    ])


def test_targets_extract_staged_unlock():
    targets = build_staged_unlock_targets(_chain())
    assert len(targets) == 1
    assert targets.iloc[0]["semantic_effect"] == "hysteresis_guard_down"


def test_variant_replay_runs():
    targets = build_staged_unlock_targets(_chain())
    alignment = run_sequence_variant_replay(targets)
    assert set(alignment["sequence_variant"]) == {
        "old_immediate_unlock",
        "relief_observe_only",
        "delayed_guarded_unlock",
        "buffered_delayed_guarded_unlock",
    }


def test_summary_completed():
    targets = build_staged_unlock_targets(_chain())
    alignment = run_sequence_variant_replay(targets)
    summary = summarize_sequence_variants(alignment)
    policy = build_repaired_sequence_policy(summary)
    js = sequence_repair_summary_json({
        "coupling_relief_staged_unlock_targets": targets,
        "coupling_relief_staged_unlock_variant_alignment": alignment,
        "coupling_relief_staged_unlock_variant_summary": summary,
        "coupling_relief_staged_unlock_repaired_policy": policy,
        "coupling_relief_staged_unlock_prior_rc2": pd.DataFrame(),
    })
    assert js["status"] == "completed"
    assert js["variant_count"] == 4
