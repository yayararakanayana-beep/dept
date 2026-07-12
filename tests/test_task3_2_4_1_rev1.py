from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import task3_2_4_1_rev1 as module


def test_config_freezes_new_seed_split_and_budget() -> None:
    config = module.load_config()
    challenge = config["challenge"]
    assert challenge["fit_seeds"] == [30, 31, 32]
    assert challenge["validation_seeds"] == [33]
    assert challenge["holdout_seeds"] == [34]
    assert config["budget"]["expected_coarse_branches"] == 3600
    assert (
        config["budget"]["expected_coarse_branches"]
        + config["budget"]["maximum_boundary_branches"]
        + config["budget"]["maximum_probability_branches"]
        <= config["budget"]["absolute_maximum_branches"]
    )


def test_branch_budget_is_global_across_phases() -> None:
    budget = module.BranchBudget(3)
    budget.reserve("coarse", 1)
    budget.reserve("boundary", 1)
    budget.reserve("probability", 1)
    assert (budget.coarse, budget.boundary, budget.probability, budget.used) == (1, 1, 1, 3)
    with pytest.raises(module.Rev1Error, match="budget exceeded"):
        budget.reserve("boundary", 1)


def test_c0_and_c1_continuations_are_distinct(tmp_path: Path) -> None:
    config = module.load_config()
    entry = module.Entry("t", "stable_continuation", 30, "fit", tmp_path, 64)
    record = {
        "step": 12,
        "observed_external_input": {name: 0.5 for name in module.t41.EXTERNAL_FIELDS},
    }
    c0 = module.continuation_schedule(
        "C0_current_input_fixed_then_neutral", entry, entry, record, 16, config
    )
    c1 = module.continuation_schedule(
        "C1_immediate_neutral", entry, entry, record, 16, config
    )
    assert all(any(abs(value) > 0.0 for value in row.values()) for row in c0[:8])
    assert all(all(abs(value) == 0.0 for value in row.values()) for row in c0[8:])
    assert all(all(abs(value) == 0.0 for value in row.values()) for row in c1)


def _aggregate_rows() -> pd.DataFrame:
    base = {
        "trajectory_id": "traj",
        "scenario_id": "audit",
        "source_seed": 30,
        "source_split": "fit",
        "snapshot_step": 28,
        "continuation_condition": "C3_same_seed_stable_future_replay",
        "probe_family": "combined_relief",
        "simultaneous_action_scale": 6,
        "replicate_count": 1,
        "ever_safe_probability": 1.0,
        "relapse_after_recovery_rate": 0.0,
        "mean_escape_cost": 0.2,
        "mean_recovery_time": 4.0,
        "mean_final_risk": 0.2,
        "mean_final_current_value": 0.5,
        "mean_final_route_support": 0.6,
        "mean_final_recovery_speed": 0.2,
        "mean_final_concentration": 0.05,
        "initial_risk": 0.4,
        "initial_current_value": 0.3,
        "replicate_disagreement": 0,
    }
    return pd.DataFrame(
        [
            {**base, "strength": 0.35, "delay_steps": 0, "recovery_probability": 0.0},
            {**base, "strength": 0.70, "delay_steps": 0, "recovery_probability": 1.0},
            {**base, "strength": 0.35, "delay_steps": 4, "recovery_probability": 1.0},
            {**base, "strength": 0.70, "delay_steps": 4, "recovery_probability": 0.0},
        ]
    )


def test_boundary_detection_keeps_nonmonotonic_results() -> None:
    boundaries, nonmonotonic = module.detect_boundaries(_aggregate_rows())
    assert boundaries
    assert {row["boundary_type"] for row in boundaries} == {"strength", "delay"}
    assert {row["nonmonotonic_type"] for row in nonmonotonic} == {
        "stronger_action_worse",
        "later_action_better",
    }


def test_condition_truth_separates_escape_observation_from_cost() -> None:
    config = module.load_config()
    failed = _aggregate_rows().copy()
    failed["recovery_probability"] = 0.0
    result = module._condition_truth(failed, config)
    assert result["escape_observed"] == 0
    assert np.isnan(result["conditional_escape_cost"])
    assert result["irreversibility_stage"] == 4


def test_feature_audit_blocks_time_and_truth_tokens() -> None:
    config = module.load_config()
    module.audit_feature_names(["macro_velocity", "history_curvature"], config)
    with pytest.raises(module.Rev1Error, match="leaked"):
        module.audit_feature_names(["snapshot_step"], config)
    with pytest.raises(module.Rev1Error, match="leaked"):
        module.audit_feature_names(["future_escape_observed"], config)
