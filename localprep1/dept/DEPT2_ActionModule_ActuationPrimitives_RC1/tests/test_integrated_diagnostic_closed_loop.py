"""Tests for IntegratedDiagnosticClosedLoop RC1."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT.parent
if str(PARENT) not in sys.path:
    sys.path.insert(0, str(PARENT))

from DEPT2_ActionModule_ActuationPrimitives_RC1.action_module.integrated_diagnostic_closed_loop import (
    IntegratedDiagnosticConfig,
    RepairedDiagnosticActionPolicy,
    run_one,
    summarize_semantic_alignment,
)


def test_run_one_outputs_fresh_actions():
    cfg = IntegratedDiagnosticConfig(steps=2, run_isolated_semantic_shadow=True)
    outputs = run_one(seed=42, scenario="normal", cfg=cfg)
    assert len(outputs["integrated_action_frame"]) > 0
    assert len(outputs["integrated_loop_metrics"]) == 2
    assert "integrated_policy_contract" in outputs["integrated_action_frame"].columns


def test_probe_restraint_split_exists():
    cfg = IntegratedDiagnosticConfig(steps=2, run_isolated_semantic_shadow=True)
    outputs = run_one(seed=42, scenario="normal", cfg=cfg)
    actions = outputs["integrated_action_frame"]
    assert "sandbox_probe_entry_down" in set(actions["source_semantic_effect"])
    assert "sandbox_probe_entry_down_stabilization" in set(actions["semantic_effect"])
    assert "diagnostic_probe_restraint_direct" in set(actions["action_channel"])


def test_guarded_unlock_sequence_events_exist():
    cfg = IntegratedDiagnosticConfig(steps=3, run_isolated_semantic_shadow=True)
    outputs = run_one(seed=42, scenario="relation_lock", cfg=cfg)
    events = outputs["integrated_sequence_events"]
    assert len(events) > 0
    assert "schedule_guarded_relation_unlock" in set(events["event_type"])
    assert "execute_guarded_relation_unlock" in set(events["event_type"])


def test_semantic_summary_has_alignment_columns():
    cfg = IntegratedDiagnosticConfig(steps=2, run_isolated_semantic_shadow=True)
    outputs = run_one(seed=42, scenario="normal", cfg=cfg)
    summary = summarize_semantic_alignment(outputs["integrated_isolated_semantic_outcomes"])
    assert not summary.empty
    assert "alignment_pass_rate" in summary.columns
