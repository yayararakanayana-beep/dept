from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

import task4_1_rev1_1_focused_audit as module


def test_config_keeps_audit_zero_branch() -> None:
    config = module.load_config()
    assert config["boundaries"]["new_branch_execution"] is False
    assert config["boundaries"]["formal_truth_writeback"] is False
    assert config["boundaries"]["predictor_retraining"] is False


def test_aggregate_relapse_is_conditional_on_ever_safe() -> None:
    frame = pd.DataFrame([
        {
            "trajectory_id": "t", "scenario_id": "stable_continuation", "source_seed": 30,
            "source_split": "fit", "snapshot_step": 44,
            "continuation_condition": "C3_same_seed_stable_future_replay",
            "probe_family": "combined_relief", "strength": 1.0, "delay_steps": 4,
            "simultaneous_action_scale": 6, "recovered": 0, "ever_safe": 1,
            "relapse_after_recovery": 1, "total_escape_cost": 1.0,
        },
        {
            "trajectory_id": "t", "scenario_id": "stable_continuation", "source_seed": 30,
            "source_split": "fit", "snapshot_step": 44,
            "continuation_condition": "C3_same_seed_stable_future_replay",
            "probe_family": "combined_relief", "strength": 1.0, "delay_steps": 4,
            "simultaneous_action_scale": 6, "recovered": 1, "ever_safe": 1,
            "relapse_after_recovery": 0, "total_escape_cost": 1.0,
        },
    ])
    result = module.aggregate_branches(frame)
    assert result.iloc[0]["recovery_probability"] == 0.5
    assert result.iloc[0]["relapse_after_recovery_rate"] == 0.5


def test_low_cost_frontier_excludes_expensive_bad_action() -> None:
    config = module.load_config()
    aggregate = pd.DataFrame([
        {
            "trajectory_id": "t", "snapshot_step": 44,
            "continuation_condition": "C3_same_seed_stable_future_replay",
            "probe_family": "no_action", "strength": 0.0, "delay_steps": 0,
            "simultaneous_action_scale": 0, "recovery_probability": 1.0,
            "relapse_after_recovery_rate": 0.0, "mean_escape_cost": 0.18,
        },
        {
            "trajectory_id": "t", "snapshot_step": 44,
            "continuation_condition": "C3_same_seed_stable_future_replay",
            "probe_family": "combined_relief", "strength": 1.0, "delay_steps": 4,
            "simultaneous_action_scale": 6, "recovery_probability": 0.5,
            "relapse_after_recovery_rate": 1.0, "mean_escape_cost": 1.65,
        },
    ])
    metrics = module.relapse_metrics(aggregate, config).iloc[0]
    assert metrics["maximum_all_probe_relapse"] == 1.0
    assert metrics["best_success_path_relapse"] == 0.0
    assert metrics["low_cost_frontier_relapse"] == 0.0


def test_validate_rejects_truth_writeback(tmp_path: Path) -> None:
    config = module.load_config()
    config["boundaries"]["formal_truth_writeback"] = True
    path = tmp_path / "config.json"
    path.write_text(__import__("json").dumps(config), encoding="utf-8")
    with pytest.raises(module.AuditError):
        module.load_config(path)
