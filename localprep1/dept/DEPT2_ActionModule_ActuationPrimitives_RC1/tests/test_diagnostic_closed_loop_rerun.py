"""Tests for DiagnosticClosedLoopRerun RC1."""

import pandas as pd

from DEPT2_ActionModule_ActuationPrimitives_RC1.action_module.diagnostic_closed_loop_rerun import (
    DiagnosticRerunConfig,
    run_combined_diagnostic_loop,
    run_isolated_semantic_replay,
    diagnostic_rerun_summary_json,
    summarize_isolated_alignment,
)


def _actions():
    return pd.DataFrame([
        {
            "run_seed": 42,
            "run_scenario": "normal",
            "loop_step": 0,
            "semantic_effect": "sandbox_probe_entry_up",
            "intent_family": "exploration_observation",
            "action_primitive": "diagnostic_sandbox_probe",
            "primitive_sequence": "sandbox_probe -> observe -> report",
            "action_channel": "exploration_injection",
            "action_strength": 0.03,
        }
    ])


def _semantic_outcome():
    return pd.DataFrame([
        {
            "semantic_effect": "sandbox_probe_entry_up",
            "semantic_outcome_details": "exploration:expected=1,observed=0.0,match=False; uncertainty:expected=1,observed=0.0,match=False",
        }
    ])


def test_combined_rerun_outputs_rows():
    combined, applied = run_combined_diagnostic_loop(_actions(), DiagnosticRerunConfig(noise_scale=0.0))
    assert len(combined) == 1
    assert len(applied) == 1
    assert "observed_delta_exploration" in combined.columns


def test_isolated_semantic_alignment_outputs_rows():
    isolated = run_isolated_semantic_replay(_actions(), _semantic_outcome(), DiagnosticRerunConfig(noise_scale=0.0))
    assert len(isolated) == 1
    assert isolated.iloc[0]["semantic_effect"] == "sandbox_probe_entry_up"
    assert "diagnostic_alignment_score" in isolated.columns


def test_summary_completed():
    combined, applied = run_combined_diagnostic_loop(_actions(), DiagnosticRerunConfig(noise_scale=0.0))
    isolated = run_isolated_semantic_replay(_actions(), _semantic_outcome(), DiagnosticRerunConfig(noise_scale=0.0))
    summary = diagnostic_rerun_summary_json({
        "diagnostic_closed_loop_combined_trace": combined,
        "diagnostic_closed_loop_action_application": applied,
        "diagnostic_closed_loop_semantic_isolated_alignment": isolated,
        "diagnostic_closed_loop_semantic_summary": summarize_isolated_alignment(isolated),
        "diagnostic_closed_loop_scenario_summary": pd.DataFrame(),
    })
    assert summary["status"] == "completed"
    assert summary["isolated_alignment_rows"] == 1
