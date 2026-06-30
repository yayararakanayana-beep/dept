"""Tests for PressureOutcomeAlignmentAudit RC2b."""

import pandas as pd

from DEPT2_ActionModule_ActuationPrimitives_RC1.action_module.pressure_outcome_alignment_audit_rc2b import (
    build_rc2b_audit,
    rc2b_summary_json,
)


def _policy_action():
    return pd.DataFrame([
        {
            "run_seed": 42,
            "run_scenario": "normal",
            "loop_step": 0,
            "semantic_effect": "sandbox_probe_entry_up",
            "intent_family": "exploration_observation",
            "original_semantic_to_plan_present": False,
            "original_plan_to_action_present": False,
            "semantic_retained_to_plan_by_policy": True,
            "semantic_retained_to_action_by_policy": True,
            "diagnostic_action_primitive": "diagnostic_sandbox_probe",
            "diagnostic_primitive_sequence": "sandbox_probe -> observe -> report",
            "diagnostic_action_channel": "exploration_injection",
            "action_mass_after_policy": 0.01,
        },
        {
            "run_seed": 42,
            "run_scenario": "normal",
            "loop_step": 0,
            "semantic_effect": "hysteresis_guard_down",
            "intent_family": "switching_flexibility",
            "original_semantic_to_plan_present": True,
            "original_plan_to_action_present": True,
            "semantic_retained_to_plan_by_policy": True,
            "semantic_retained_to_action_by_policy": True,
            "diagnostic_action_primitive": "diagnostic_switching_flexibility",
            "diagnostic_primitive_sequence": "switching_flexibility -> observe",
            "diagnostic_action_channel": "coupling_relief",
            "action_mass_after_policy": 0.02,
        },
    ])


def _rc2_semantic():
    return pd.DataFrame([
        {
            "run_seed": 42,
            "run_scenario": "normal",
            "loop_step": 0,
            "semantic_effect": "sandbox_probe_entry_up",
            "primary_alignment_score": 0.1,
            "primary_alignment_pass": False,
            "semantic_outcome_verdict": "semantic_misaligned_not_planned",
            "rc2_alignment_verdict": "semantic_misaligned_not_planned",
        },
        {
            "run_seed": 42,
            "run_scenario": "normal",
            "loop_step": 0,
            "semantic_effect": "hysteresis_guard_down",
            "primary_alignment_score": 0.6,
            "primary_alignment_pass": True,
            "semantic_outcome_verdict": "semantic_aligned",
            "rc2_alignment_verdict": "semantic_aligned",
        },
    ])


def test_rc2b_separates_pending_from_observed():
    outputs = build_rc2b_audit(
        policy_action=_policy_action(),
        policy_plan=pd.DataFrame(),
        drop_reason=pd.DataFrame(),
        rc2_semantic=_rc2_semantic(),
        rc2_primitive=pd.DataFrame(),
    )
    audit = outputs["rc2b_semantic_policy_alignment"]
    assert set(audit["outcome_attribution_status"]) == {
        "diagnostic_action_created_outcome_pending",
        "observed_existing_action_attribution",
    }


def test_rc2b_summary_completed():
    outputs = build_rc2b_audit(
        policy_action=_policy_action(),
        policy_plan=pd.DataFrame(),
        drop_reason=pd.DataFrame(),
        rc2_semantic=_rc2_semantic(),
        rc2_primitive=pd.DataFrame(),
    )
    summary = rc2b_summary_json(outputs)
    assert summary["status"] == "completed"
    assert summary["policy_plan_rate"] == 1.0
    assert summary["policy_action_rate"] == 1.0
    assert summary["outcome_pending_rate"] > 0
