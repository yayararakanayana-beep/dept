"""Tests for DiagnosticActionTranslationPolicy RC1."""

import pandas as pd

from DEPT2_ActionModule_ActuationPrimitives_RC1.action_module.diagnostic_action_translation_policy import (
    build_diagnostic_translation_policy,
    diagnostic_policy_summary_json,
)


def test_policy_rescues_missing_semantic_effect():
    semantic = pd.DataFrame([
        {
            "run_seed": 42,
            "run_scenario": "normal",
            "loop_step": 0,
            "pressure_component": "sandbox_entry_rate",
            "component_direction": "increase",
            "semantic_effect": "sandbox_probe_entry_up",
            "intent_family": "exploration_observation",
            "suggested_control_route": "sandbox_probe",
            "max_component_magnitude": 0.05,
            "total_received_abs_pressure": 0.2,
            "intent_rows": 3,
        }
    ])
    outputs = build_diagnostic_translation_policy(semantic, pd.DataFrame())
    action = outputs["diagnostic_policy_action_frame"]
    drop = outputs["diagnostic_policy_drop_reason"]
    assert len(action) == 1
    assert action.iloc[0]["semantic_retained_to_action_by_policy"]
    assert action.iloc[0]["diagnostic_action_primitive"] == "diagnostic_sandbox_probe"
    assert drop.iloc[0]["policy_resolution"] == "rescued_by_validation_policy"


def test_policy_retains_buffer_positive_control():
    semantic = pd.DataFrame([
        {
            "run_seed": 42,
            "run_scenario": "normal",
            "loop_step": 0,
            "pressure_component": "pressure_cap",
            "component_direction": "increase",
            "semantic_effect": "intensity_cap_brake",
            "intent_family": "safety_cap",
            "suggested_control_route": "buffer_first",
            "max_component_magnitude": 0.05,
            "total_received_abs_pressure": 0.2,
            "intent_rows": 3,
        }
    ])
    chain = pd.DataFrame([
        {
            "run_seed": 42,
            "run_scenario": "normal",
            "loop_step": 0,
            "semantic_effect": "intensity_cap_brake",
            "semantic_to_plan_present": True,
            "plan_to_action_present": False,
            "planned_rows": 2,
            "action_rows": 0,
            "action_mass": 0,
        }
    ])
    outputs = build_diagnostic_translation_policy(semantic, chain)
    action = outputs["diagnostic_policy_action_frame"]
    assert action.iloc[0]["diagnostic_action_primitive"] == "buffer_first"
    assert action.iloc[0]["diagnostic_primitive_sequence"] == "buffer -> replan"
    assert bool(action.iloc[0]["positive_control_flag"])


def test_policy_summary_completed():
    semantic = pd.DataFrame([
        {
            "run_seed": 42,
            "run_scenario": "normal",
            "loop_step": 0,
            "pressure_component": "sandbox_entry_rate",
            "component_direction": "increase",
            "semantic_effect": "sandbox_probe_entry_up",
            "intent_family": "exploration_observation",
            "suggested_control_route": "sandbox_probe",
            "max_component_magnitude": 0.05,
            "total_received_abs_pressure": 0.2,
            "intent_rows": 3,
        },
        {
            "run_seed": 42,
            "run_scenario": "normal",
            "loop_step": 0,
            "pressure_component": "pressure_cap",
            "component_direction": "increase",
            "semantic_effect": "intensity_cap_brake",
            "intent_family": "safety_cap",
            "suggested_control_route": "buffer_first",
            "max_component_magnitude": 0.05,
            "total_received_abs_pressure": 0.2,
            "intent_rows": 3,
        },
    ])
    outputs = build_diagnostic_translation_policy(semantic, pd.DataFrame())
    summary = diagnostic_policy_summary_json(outputs)
    assert summary["status"] == "completed"
    assert summary["policy_semantic_to_plan_rate"] == 1.0
    assert summary["policy_plan_to_action_rate"] == 1.0
