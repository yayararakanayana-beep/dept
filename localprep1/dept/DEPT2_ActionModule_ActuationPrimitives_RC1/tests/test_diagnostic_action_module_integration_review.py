"""Tests for DiagnosticActionModuleIntegrationReview RC1."""

import pandas as pd

from DEPT2_ActionModule_ActuationPrimitives_RC1.action_module.diagnostic_action_module_integration_review import (
    build_readiness_gate,
    build_next_action_plan,
    integration_review_summary_json,
)


def test_readiness_gate_passes_when_all_pass():
    milestones = pd.DataFrame({"status": ["pass", "pass", "pass"]})
    metrics = pd.DataFrame({"status": ["pass", "pass", "informational"]})
    readiness = build_readiness_gate(milestones, metrics)
    row = readiness[readiness.gate == "validation_action_module_coherence"].iloc[0]
    assert row["status"] == "pass"


def test_next_action_plan_starts_with_integrated_loop():
    plan = build_next_action_plan(pd.DataFrame())
    assert plan.iloc[0]["next_task"] == "IntegratedDiagnosticClosedLoop_RC1"


def test_summary_completed():
    outputs = {
        "diagnostic_action_module_integration_milestones": pd.DataFrame({"status": ["pass"] * 10}),
        "diagnostic_action_module_integration_metrics": pd.DataFrame({"status": ["pass"] * 8 + ["informational"]}),
        "diagnostic_action_module_integration_readiness": pd.DataFrame([
            {"gate": "validation_action_module_coherence", "status": "pass", "score": 1.0},
            {"gate": "pressure_tuning_readiness", "status": "not_ready", "score": 0.0},
        ]),
        "diagnostic_action_module_integration_risks": pd.DataFrame([
            {"risk": "pressure_generation_not_yet_validated_after_repairs", "severity": "high", "status": "open"}
        ]),
        "diagnostic_action_module_integration_next_plan": pd.DataFrame([
            {"priority": 1, "next_task": "IntegratedDiagnosticClosedLoop_RC1"}
        ]),
    }
    summary = integration_review_summary_json(outputs)
    assert summary["status"] == "completed"
    assert summary["coherence_gate_status"] == "pass"
    assert summary["recommended_next_task"] == "IntegratedDiagnosticClosedLoop_RC1"
