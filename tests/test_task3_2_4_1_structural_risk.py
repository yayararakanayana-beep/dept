from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from pseudo_reality.distribution_terrain_v3_2_2 import (
    DistributionTerrainV322Config,
    DistributionTerrainV322World,
)
import task3_2_4_1_structural_risk as module


def test_config_has_disjoint_seed_splits_and_fixed_task4_candidate() -> None:
    config = module.load_config()
    challenge = config["challenge"]
    fit = set(challenge["fit_seeds"])
    validation = set(challenge["validation_seeds"])
    holdout = set(challenge["holdout_seeds"])
    assert fit and validation and holdout
    assert not fit & validation
    assert not fit & holdout
    assert not validation & holdout
    assert config["fixed_macro_candidate"] == {
        "input_scope": "distribution",
        "latent_dimension": 8,
        "dynamics_family": "dmdc",
        "prediction_horizon": 16,
        "history_width": 8,
    }


def test_action_input_moves_only_toward_relief() -> None:
    current = {
        "external_resource_supply": -0.5,
        "external_demand": 0.8,
        "external_competition_pressure": 0.9,
        "external_information_noise": 0.7,
        "external_shock": 0.8,
        "external_constraint_pressure": 0.9,
    }
    resource = module.action_input(current, "resource_relief", 0.5)
    assert resource["external_resource_supply"] > current["external_resource_supply"]
    assert resource["external_demand"] < current["external_demand"]
    assert resource["external_shock"] == current["external_shock"]
    combined = module.action_input(current, "combined_relief", 1.0)
    assert combined["external_resource_supply"] == 1.0
    assert combined["external_demand"] == -1.0
    assert combined["external_competition_pressure"] == 0.0
    assert combined["external_information_noise"] == 0.0
    assert combined["external_shock"] == 0.0
    assert combined["external_constraint_pressure"] == 0.0


def test_safe_state_requires_primary_and_supporting_conditions() -> None:
    safe = {
        "risk_max": 0.2,
        "current_value_min": 0.1,
        "damage_max": 0.2,
        "negative_pressure_max": 0.2,
        "route_support_min": 0.5,
        "recovery_speed_min": 0.05,
        "viability_reserve_min": 0.4,
    }
    metrics = {
        "risk_score": 0.1,
        "current_value": 0.2,
        "weighted_damage": 0.1,
        "weighted_negative_viability_pressure": 0.1,
        "weighted_route_support": 0.7,
        "weighted_recovery_speed": 0.1,
        "weighted_viability_reserve": 0.6,
    }
    assert module.safe_state(metrics, safe)
    assert not module.safe_state({**metrics, "risk_score": 0.3}, safe)
    assert not module.safe_state(
        {
            **metrics,
            "weighted_damage": 0.5,
            "weighted_negative_viability_pressure": 0.5,
            "weighted_route_support": 0.1,
        },
        safe,
    )


def test_label_shrinking_equilibrium_requires_stable_value_and_two_structural_losses() -> None:
    config = module.load_config()
    frame = pd.DataFrame(
        [
            {
                "trajectory_id": "t",
                "scenario_id": "audit",
                "seed": 1,
                "split": "fit",
                "snapshot_step": 12,
                "current_value": 0.30,
                "maintenance_cost": 0.10,
                "minimum_escape_cost": 0.20,
                "reachable_value": 0.50,
                "reachable_range": 1.00,
                "last_action_window": 8,
                "best_recovery_probability": 1.0,
                "refixation_probability": 0.0,
                "minimum_simultaneous_action_scale": 2,
                "provisional_irreversibility_level": 1,
            },
            {
                "trajectory_id": "t",
                "scenario_id": "audit",
                "seed": 1,
                "split": "fit",
                "snapshot_step": 28,
                "current_value": 0.299,
                "maintenance_cost": 0.12,
                "minimum_escape_cost": 0.25,
                "reachable_value": 0.47,
                "reachable_range": 0.95,
                "last_action_window": 4,
                "best_recovery_probability": 0.8,
                "refixation_probability": 0.1,
                "minimum_simultaneous_action_scale": 2,
                "provisional_irreversibility_level": 2,
            },
        ]
    )
    labelled = module.label_shrinking_equilibrium(frame, config)
    assert labelled.iloc[0]["shrinking_equilibrium_candidate"] == 0
    assert labelled.iloc[1]["shrinking_equilibrium_candidate"] == 1
    assert labelled.iloc[1]["shrinking_evidence_count"] >= 2


def _snapshot_entry(tmp_path: Path) -> tuple[module.Entry, dict]:
    world = DistributionTerrainV322World(DistributionTerrainV322Config(seed=7))
    trajectory = tmp_path / "trajectory"
    states = trajectory / "states"
    states.mkdir(parents=True)
    arrays = {}
    for name, value in vars(world).items():
        array = np.asarray(value) if isinstance(value, np.ndarray) else None
        if array is not None and array.shape == world.shape:
            arrays[name] = array
    for name in (
        "total_gain_delta_signal",
        "last_external_deformation_strength",
        "last_threshold_activation_strength",
        "last_distribution_weighted_threshold_activation_strength",
    ):
        arrays[name] = np.asarray(float(getattr(world, name)))
    np.savez_compressed(states / "step_000012.npz", **arrays)
    entry = module.Entry(
        trajectory_id="traj_test",
        scenario_id="stable_continuation",
        seed=7,
        split="fit",
        path=trajectory,
        total_steps=64,
    )
    step_record = {
        "trajectory_id": "traj_test",
        "step": 12,
        "state_ref": "states/step_000012.npz",
        "observed_external_input": {name: 0.0 for name in module.EXTERNAL_FIELDS},
    }
    return entry, step_record


def test_counterfactual_branch_uses_new_world_and_no_writeback(tmp_path: Path) -> None:
    config = module.load_config()
    entry, step_record = _snapshot_entry(tmp_path)
    original = (entry.path / step_record["state_ref"]).read_bytes()
    safe = {
        "risk_max": 1.0,
        "current_value_min": -1.0,
        "damage_max": 1.0,
        "negative_pressure_max": 1.0,
        "route_support_min": 0.0,
        "recovery_speed_min": 0.0,
        "viability_reserve_min": 0.0,
        "sustained_steps": 2,
        "post_action_followup_steps": 2,
    }
    result = module.run_branch(
        entry,
        step_record,
        safe,
        "combined_relief",
        0.7,
        0,
        0,
        config,
    )
    assert result["state_writeback"] == 0
    assert result["parameter_write"] == 0
    assert result["action_module_connection"] == 0
    assert result["recovered"] == 1
    assert (entry.path / step_record["state_ref"]).read_bytes() == original


def test_holdout_index_requires_validated_lock(tmp_path: Path) -> None:
    config = module.load_config()
    root = tmp_path / "corpus" / "trajectories"
    split_by_seed = {20: "fit", 21: "fit", 22: "fit", 23: "validation", 24: "holdout"}
    for seed, split in split_by_seed.items():
        for scenario in config["challenge"]["condition_groups"]:
            directory = root / f"traj_{scenario}_{seed}"
            directory.mkdir(parents=True)
            (directory / "metadata.json").write_text(
                json.dumps(
                    {
                        "trajectory_id": f"traj_{scenario}_{seed}",
                        "scenario_id": scenario,
                        "seed": seed,
                        "dataset_split": split,
                        "total_steps": 64,
                    }
                ),
                encoding="utf-8",
            )
    index = module.CorpusIndex(tmp_path / "corpus", config)
    with pytest.raises(module.StructuralRiskError, match="holdout state read blocked"):
        index.entries_for("holdout")
    lock_path = tmp_path / "lock.json"
    validation_path = tmp_path / "validation.json"
    lock = module._create_lock(
        lock_path,
        {"candidate_family": "current_risk"},
        {"fit_only": True},
        config,
        "truth_hash",
    )
    module._write_lock_validation(validation_path, lock)
    assert len(index.entries_for("holdout", lock_path=lock_path, validation_path=validation_path)) == 6


def test_tampered_lock_is_rejected(tmp_path: Path) -> None:
    config = module.load_config()
    lock_path = tmp_path / "lock.json"
    validation_path = tmp_path / "validation.json"
    lock = module._create_lock(
        lock_path,
        {"candidate_family": "task3"},
        {"fit_only": True},
        config,
        "truth_hash",
    )
    module._write_lock_validation(validation_path, lock)
    value = json.loads(lock_path.read_text(encoding="utf-8"))
    value["selected_candidate"] = {"candidate_family": "task4"}
    lock_path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(module.StructuralRiskError, match="hash mismatch"):
        module.validate_selection_lock(lock_path, validation_path)


def test_prediction_metrics_cover_structural_targets() -> None:
    rows = []
    for index in range(6):
        shrink = int(index >= 3)
        row = {
            "trajectory_id": f"t{index}",
            "scenario_id": "audit",
            "seed": index,
            "split": "validation",
            "snapshot_step": 12,
        }
        targets = {
            "minimum_escape_cost": 0.1 + 0.1 * index,
            "best_recovery_probability": 1.0 - 0.1 * index,
            "reachable_value": 0.6 - 0.05 * index,
            "reachable_range": 1.0 - 0.1 * index,
            "last_action_window": 8 - index,
            "refixation_probability": 0.1 * index,
            "minimum_simultaneous_action_scale": min(6, index + 1),
            "provisional_irreversibility_level": min(4, index),
            "shrinking_equilibrium_candidate": shrink,
        }
        for name, value in targets.items():
            row[f"actual__{name}"] = value
            row[f"predicted__{name}"] = value
        rows.append(row)
    metrics = module.evaluate_predictions(pd.DataFrame(rows))
    assert metrics["shrinking_average_precision"] == 1.0
    assert metrics["escape_cost_mae"] == 0.0
    assert metrics["irreversibility_exact_accuracy"] == 1.0
