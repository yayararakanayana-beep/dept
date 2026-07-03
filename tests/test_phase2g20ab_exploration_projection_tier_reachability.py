"""Phase 2G-20AB exploration projection tier reachability tests.

These tests verify that the exploration bridge no longer behaves as an all-or-
nothing sandbox_pass gate.  Safe watch/pass candidates should reach the action
side as thin, tiered candidates, while blocked, failed, or unverified-danger
candidates must not become action-readable projections.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

RC1_ROOT = Path("localprep1/dept/dept2_fullspec_runner_rc1")
if str(RC1_ROOT) not in sys.path:
    sys.path.insert(0, str(RC1_ROOT))

from modules.exploration_bridge_module import ExplorationBridgeModule  # noqa: E402


def _sample_tables() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    decision = pd.DataFrame([
        {"seed": 20, "scenario": "phase2g20ab", "t": 3, "candidate_axis_id": "axis_pass", "decision_status": "sandbox_pass", "decision_score": 0.84, "unverified_candidate_can_pass": False},
        {"seed": 20, "scenario": "phase2g20ab", "t": 3, "candidate_axis_id": "axis_watch", "decision_status": "watch", "decision_score": 0.42, "unverified_candidate_can_pass": False},
        {"seed": 20, "scenario": "phase2g20ab", "t": 3, "candidate_axis_id": "axis_weak", "decision_status": "sandbox_pass", "decision_score": 0.42, "unverified_candidate_can_pass": False},
        {"seed": 20, "scenario": "phase2g20ab", "t": 3, "candidate_axis_id": "axis_block", "decision_status": "block", "decision_score": 0.90, "unverified_candidate_can_pass": False},
        {"seed": 20, "scenario": "phase2g20ab", "t": 3, "candidate_axis_id": "axis_unverified", "decision_status": "sandbox_pass", "decision_score": 0.92, "unverified_candidate_can_pass": False},
        {"seed": 20, "scenario": "phase2g20ab", "t": 3, "candidate_axis_id": "axis_audit_fail", "decision_status": "sandbox_pass", "decision_score": 0.91, "unverified_candidate_can_pass": False},
        {"seed": 20, "scenario": "phase2g20ab", "t": 3, "candidate_axis_id": "axis_v8_fail", "decision_status": "sandbox_pass", "decision_score": 0.91, "unverified_candidate_can_pass": False},
        {"seed": 20, "scenario": "phase2g20ab", "t": 3, "candidate_axis_id": "axis_unverified_flag", "decision_status": "sandbox_pass", "decision_score": 0.91, "unverified_candidate_can_pass": True},
    ])
    sandbox = pd.DataFrame([
        {"candidate_axis_id": "axis_pass", "sandbox_verified": True, "sandbox_status": "pass", "dispersion_gain": 0.30, "residual_reduction": 0.24, "information_gain": 0.28, "stability_cost": 0.06, "noise_risk": 0.12, "adoption_risk": 0.20, "topology_preservation_score": 0.92, "topology_break_risk": 0.08},
        {"candidate_axis_id": "axis_watch", "sandbox_verified": True, "sandbox_status": "watch", "dispersion_gain": 0.18, "residual_reduction": 0.10, "information_gain": 0.16, "stability_cost": 0.10, "noise_risk": 0.20, "adoption_risk": 0.34, "topology_preservation_score": 0.80, "topology_break_risk": 0.20},
        {"candidate_axis_id": "axis_weak", "sandbox_verified": True, "sandbox_status": "pass", "dispersion_gain": 0.20, "residual_reduction": 0.12, "information_gain": 0.18, "stability_cost": 0.08, "noise_risk": 0.18, "adoption_risk": 0.30, "topology_preservation_score": 0.84, "topology_break_risk": 0.16},
        {"candidate_axis_id": "axis_block", "sandbox_verified": True, "sandbox_status": "block", "dispersion_gain": 0.35, "residual_reduction": 0.22, "information_gain": 0.30, "stability_cost": 0.35, "noise_risk": 0.80, "adoption_risk": 0.90, "topology_preservation_score": 0.20, "topology_break_risk": 0.80},
        {"candidate_axis_id": "axis_unverified", "sandbox_verified": False, "sandbox_status": "pass", "dispersion_gain": 0.35, "residual_reduction": 0.26, "information_gain": 0.30, "stability_cost": 0.05, "noise_risk": 0.10, "adoption_risk": 0.18, "topology_preservation_score": 0.94, "topology_break_risk": 0.06},
        {"candidate_axis_id": "axis_audit_fail", "sandbox_verified": True, "sandbox_status": "pass", "dispersion_gain": 0.35, "residual_reduction": 0.26, "information_gain": 0.30, "stability_cost": 0.05, "noise_risk": 0.10, "adoption_risk": 0.18, "topology_preservation_score": 0.94, "topology_break_risk": 0.06},
        {"candidate_axis_id": "axis_v8_fail", "sandbox_verified": True, "sandbox_status": "pass", "dispersion_gain": 0.35, "residual_reduction": 0.26, "information_gain": 0.30, "stability_cost": 0.05, "noise_risk": 0.10, "adoption_risk": 0.18, "topology_preservation_score": 0.94, "topology_break_risk": 0.06},
        {"candidate_axis_id": "axis_unverified_flag", "sandbox_verified": True, "sandbox_status": "pass", "dispersion_gain": 0.35, "residual_reduction": 0.26, "information_gain": 0.30, "stability_cost": 0.05, "noise_risk": 0.10, "adoption_risk": 0.18, "topology_preservation_score": 0.94, "topology_break_risk": 0.06},
    ])
    local_audit = pd.DataFrame([
        {"candidate_axis_id": "axis_pass", "entity_id": "E001", "graph_object_id": "GO_E001", "ot_id": "OT1", "axis_type": "coverage_gap_axis", "action_channel": "exploration_injection", "target_need": 0.70, "v8_confidence": 0.82, "v8_conflict": 0.05, "v8_unresolved": 0.04, "local_audit_passed": True, "v8_support_status": "pass"},
        {"candidate_axis_id": "axis_watch", "entity_id": "E002", "graph_object_id": "GO_E002", "ot_id": "OT2", "axis_type": "residual_gap_axis", "action_channel": "exploration_probe", "target_need": 0.45, "v8_confidence": 0.64, "v8_conflict": 0.08, "v8_unresolved": 0.07, "local_audit_passed": True, "v8_support_status": "pass"},
        {"candidate_axis_id": "axis_weak", "entity_id": "E003", "graph_object_id": "GO_E003", "ot_id": "OT3", "axis_type": "novelty_counter_bias_axis", "action_channel": "exploration_probe", "target_need": 0.46, "v8_confidence": 0.66, "v8_conflict": 0.07, "v8_unresolved": 0.06, "local_audit_passed": True, "v8_support_status": "pass"},
        {"candidate_axis_id": "axis_block", "entity_id": "E004", "graph_object_id": "GO_E004", "ot_id": "OT4", "axis_type": "coverage_gap_axis", "action_channel": "exploration_injection", "target_need": 0.90, "v8_confidence": 0.70, "v8_conflict": 0.12, "v8_unresolved": 0.10, "local_audit_passed": True, "v8_support_status": "pass"},
        {"candidate_axis_id": "axis_unverified", "entity_id": "E005", "graph_object_id": "GO_E005", "ot_id": "OT5", "axis_type": "coverage_gap_axis", "action_channel": "exploration_injection", "target_need": 0.88, "v8_confidence": 0.80, "v8_conflict": 0.04, "v8_unresolved": 0.04, "local_audit_passed": True, "v8_support_status": "pass"},
        {"candidate_axis_id": "axis_audit_fail", "entity_id": "E006", "graph_object_id": "GO_E006", "ot_id": "OT6", "axis_type": "coverage_gap_axis", "action_channel": "exploration_injection", "target_need": 0.88, "v8_confidence": 0.80, "v8_conflict": 0.04, "v8_unresolved": 0.04, "local_audit_passed": False, "v8_support_status": "pass"},
        {"candidate_axis_id": "axis_v8_fail", "entity_id": "E007", "graph_object_id": "GO_E007", "ot_id": "OT7", "axis_type": "coverage_gap_axis", "action_channel": "exploration_injection", "target_need": 0.88, "v8_confidence": 0.80, "v8_conflict": 0.04, "v8_unresolved": 0.04, "local_audit_passed": True, "v8_support_status": "fail"},
        {"candidate_axis_id": "axis_unverified_flag", "entity_id": "E008", "graph_object_id": "GO_E008", "ot_id": "OT8", "axis_type": "coverage_gap_axis", "action_channel": "exploration_injection", "target_need": 0.88, "v8_confidence": 0.80, "v8_conflict": 0.04, "v8_unresolved": 0.04, "local_audit_passed": True, "v8_support_status": "pass"},
    ])
    return decision, sandbox, local_audit


def _project() -> dict[str, pd.DataFrame]:
    decision, sandbox, audit = _sample_tables()
    return ExplorationBridgeModule().project(
        decision,
        sandbox,
        audit,
        parameter_windows={"projection_adoption_threshold": 0.50, "watch_projection_threshold": 0.30},
    )


def test_pass_watch_and_weak_candidates_reach_action_side_as_tiered_projection():
    result = _project()
    projection = result["exploration_projection"]
    assert set(projection["candidate_axis_id"]) == {"axis_pass", "axis_watch", "axis_weak"}
    tier = projection.set_index("candidate_axis_id")["projection_tier"].to_dict()
    assert tier["axis_pass"] == "strong_candidate"
    assert tier["axis_watch"] == "probe_only"
    assert tier["axis_weak"] == "weak_candidate"


def test_candidate_permissions_are_not_all_or_nothing():
    projection = _project()["exploration_projection"]
    permission = projection.set_index("candidate_axis_id")["candidate_use_permission"].to_dict()
    assert permission["axis_pass"] == "action_allowed"
    assert permission["axis_watch"] == "probe_only"
    assert permission["axis_weak"] == "probe_only"


def test_block_failed_and_unverified_candidates_do_not_project():
    result = _project()
    projection_ids = set(result["exploration_projection"]["candidate_axis_id"])
    assert "axis_block" not in projection_ids
    assert "axis_unverified" not in projection_ids
    assert "axis_audit_fail" not in projection_ids
    assert "axis_v8_fail" not in projection_ids
    assert "axis_unverified_flag" not in projection_ids


def test_sidecar_retains_all_candidates_and_explains_blocking():
    sidecar = _project()["exploration_sidecar"]
    assert len(sidecar) == 8
    tier = sidecar.set_index("candidate_axis_id")["projection_tier"].to_dict()
    assert tier["axis_block"] == "blocked"
    assert tier["axis_audit_fail"] == "blocked"
    assert tier["axis_v8_fail"] == "blocked"
    assert tier["axis_unverified_flag"] == "blocked"
    assert tier["axis_unverified"] == "monitor_only"


def test_projection_carries_budget_strength_and_cooldown_hints():
    projection = _project()["exploration_projection"]
    required = {
        "frontier_expectation_score",
        "side_effect_budget",
        "max_start_strength",
        "max_escalated_strength",
        "cooldown_steps",
        "execution_decision_owner",
        "action_module_final_decision_required",
    }
    assert required.issubset(projection.columns)
    by_id = projection.set_index("candidate_axis_id")
    assert by_id.loc["axis_pass", "max_start_strength"] > by_id.loc["axis_weak", "max_start_strength"]
    assert by_id.loc["axis_weak", "max_start_strength"] > by_id.loc["axis_watch", "max_start_strength"]
    assert (projection["max_escalated_strength"] >= projection["max_start_strength"]).all()
    assert projection["side_effect_budget"].between(0.005, 0.080).all()


def test_action_module_owns_final_execution_decision():
    projection = _project()["exploration_projection"]
    assert set(projection["execution_decision_owner"]) == {"action_module"}
    assert projection["action_module_final_decision_required"].all()
    assert not projection["projection_creates_actionframe"].any()
    assert not projection["projection_calls_actionmodule"].any()
    assert not projection["projection_writes_world"].any()
    assert not projection["projection_updates_parameter_box"].any()


def test_projected_candidates_remain_verified_and_audited():
    result = _project()
    projection = result["exploration_projection"]
    sidecar = result["exploration_sidecar"]
    assert projection["projection_source_verified"].all()
    assert projection["projection_source_local_audit_passed"].all()
    assert set(projection["projection_source_v8_status"]) == {"pass"}
    assert not sidecar["unverified_candidate_projected"].any()
    assert sidecar["all_projected_candidates_verified"].all()


def test_empty_projection_schema_contains_new_tier_columns():
    empty = ExplorationBridgeModule().project(pd.DataFrame(), pd.DataFrame(), pd.DataFrame())["exploration_projection"]
    expected = {
        "projection_tier",
        "candidate_use_permission",
        "frontier_expectation_score",
        "side_effect_budget",
        "max_start_strength",
        "max_escalated_strength",
        "cooldown_steps",
        "execution_decision_owner",
        "action_module_final_decision_required",
    }
    assert expected.issubset(empty.columns)
