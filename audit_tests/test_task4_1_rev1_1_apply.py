from __future__ import annotations

import numpy as np
import pandas as pd

import task4_1_rev1_1_apply as module


def test_config_keeps_zero_branch_and_fixed_selection() -> None:
    config = module.load_config()
    assert config["boundaries"]["new_branch_execution"] is False
    assert config["selection_contract"]["candidate_family"] == "task4"
    assert config["selection_contract"]["post_holdout_reselection_forbidden"] is True


def test_low_cost_frontier_excludes_expensive_relapsing_probe() -> None:
    aggregate = pd.DataFrame([
        {
            "trajectory_id": "t", "snapshot_step": 44,
            "continuation_condition": "C3_same_seed_stable_future_replay",
            "recovery_probability": 1.0, "mean_escape_cost": 0.18,
            "relapse_after_recovery_rate": 0.0,
        },
        {
            "trajectory_id": "t", "snapshot_step": 44,
            "continuation_condition": "C3_same_seed_stable_future_replay",
            "recovery_probability": 0.5, "mean_escape_cost": 1.60,
            "relapse_after_recovery_rate": 1.0,
        },
    ])
    result = module.low_cost_relapse_metrics(aggregate, module.load_config()).iloc[0]
    assert result["all_probe_relapse_after_recovery_rate"] == 1.0
    assert result["low_cost_relapse_after_recovery_rate"] == 0.0
    assert result["low_cost_frontier_setting_count"] == 1


def _frame(rows: int = 12) -> pd.DataFrame:
    base = module.common.load_config(module.ROOT / "configs/task3_2_4_1_rev1.json")
    data = {
        "trajectory_id": [f"t{i}" for i in range(rows)],
        "scenario_id": ["audit"] * rows,
        "seed": [30] * rows,
        "split": ["fit"] * rows,
        "snapshot_step": [12] * rows,
        "f0": np.linspace(-1.0, 1.0, rows),
        "f1": np.linspace(1.0, -1.0, rows),
    }
    for target in base["prediction"]["binary_targets"]:
        data[target] = np.asarray([(i % 2) for i in range(rows)], dtype=int)
    data["c2_active_intervention_required"] = np.asarray([0] * 8 + [1] * 4, dtype=int)
    for target in base["prediction"]["continuous_targets"]:
        data[target] = np.linspace(0.1, 0.3, rows)
    data["c2_conditional_escape_cost"] = np.asarray(
        [0.15 + 0.005 * i for i in range(8)] + [0.40, 0.50, 0.60, 0.70]
    )
    data["c2_best_probe_strength"] = np.asarray([0.0] * 8 + [0.35, 0.50, 0.65, 0.80])
    return pd.DataFrame(data)


def test_two_stage_c2_model_emits_gate_strength_and_cost() -> None:
    frame = _frame()
    base = module.common.load_config(module.ROOT / "configs/task3_2_4_1_rev1.json")
    apply = module.load_config()
    model = module.fit_fixed_task4_predictor(frame, ["f0", "f1"], base, apply)
    output = module.predict_fixed(model, frame, apply)
    assert "predicted__c2_active_gate" in output
    assert "predicted__c2_required_strength" in output
    assert "predicted__c2_conditional_escape_cost" in output
    assert np.isfinite(output["predicted__c2_conditional_escape_cost"]).all()
    assert model["models"]["c2_cost_two_stage"]["active_training_count"] == 4
