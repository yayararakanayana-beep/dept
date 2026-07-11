from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import task3_2_4_macro_dynamics as module


def _write_entry(root: Path, trajectory_id: str, seed: int, split: str, state_count: int = 16) -> module.Entry:
    directory = root / trajectory_id
    states = directory / "states"
    states.mkdir(parents=True)
    step_rows = []
    rng = np.random.default_rng(seed)
    for step in range(state_count):
        distribution = rng.random((5, 5, 5, 5, 5)) + 0.001 * step
        distribution /= distribution.sum()
        damage = np.full_like(distribution, 0.1 + 0.01 * step)
        ref = f"states/step_{step:06d}.npz"
        np.savez_compressed(directory / ref, distribution=distribution, damage=damage)
        step_rows.append({"step": step, "state_ref": ref})
    (directory / "steps.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in step_rows), encoding="utf-8"
    )
    return module.Entry(
        trajectory_id=trajectory_id,
        scenario_id="stable_continuation",
        seed=seed,
        split=split,
        path=directory,
        total_steps=state_count - 1,
    )


def test_fit_only_preprocessors_generate_finite_latent_states(tmp_path: Path) -> None:
    config = module.load_config()
    entries = [
        _write_entry(tmp_path, "a", 1, "fit"),
        _write_entry(tmp_path, "b", 2, "fit"),
    ]
    for scope in ["distribution", "full_state"]:
        processor = module.MacroPreprocessor(scope, config, ["distribution", "damage"]).fit(entries)
        transformed = processor.transform(entries)
        assert set(transformed) == {"a", "b"}
        assert transformed["a"].shape == (16, 12)
        assert np.all(np.isfinite(transformed["a"]))
        assert processor.metadata()["fit_only"] is True


def _synthetic_latent_and_series():
    latent = {}
    series = {}
    for trajectory_index in range(6):
        trajectory_id = f"t{trajectory_index}"
        values = []
        external_rows = []
        state = np.asarray([0.1, 0.2, 0.3, 0.4], dtype=np.float64) + trajectory_index * 0.01
        for step in range(24):
            u = np.asarray([0.01 * (trajectory_index + 1), 0.0, 0.02, 0.0, 0.01, 0.02])
            values.append(np.pad(state, (0, 8)))
            external_rows.append({name: float(value) for name, value in zip(module.EXTERNAL_FIELDS, u)})
            state = 0.93 * state + np.asarray([u[0], u[2], u[4], u[5]])
        latent[trajectory_id] = np.asarray(values)
        series[trajectory_id] = SimpleNamespace(features=external_rows, hazard_onset_step=18)
    return latent, series


def test_all_four_dynamics_families_fit_and_forecast() -> None:
    config = module.load_config()
    latent, series = _synthetic_latent_and_series()
    for family in config["representation_candidates"]["dynamics_families"]:
        model = module.DynamicsModel(family, 4, config).fit(latent, series)
        external = np.asarray([series["t0"].features[-1][name] for name in module.EXTERNAL_FIELDS])
        forecast, path_length = model.forecast(latent["t0"][-8:, :4], external, 4)
        residual = model.residual_series(latent["t0"][:, :4], np.asarray(
            [[row[name] for name in module.EXTERNAL_FIELDS] for row in series["t0"].features]
        ))
        assert forecast.shape == (4,)
        assert np.all(np.isfinite(forecast))
        assert path_length >= 0.0
        assert residual.shape == (24,)
        assert np.all(residual >= 0.0)


def test_macro_features_keep_residual_and_external_response_separate() -> None:
    config = module.load_config()
    latent, series = _synthetic_latent_and_series()
    entries = [
        module.Entry(key, "audit", index, "fit", Path("."), 23)
        for index, key in enumerate(latent)
    ]
    model = module.DynamicsModel("dmdc", 4, config).fit(latent, series)
    frame, residual = module.macro_feature_frame(entries, series, latent, model, 4, 8)
    assert "macro_residual_current" in frame.columns
    assert "macro_external_response_norm" in frame.columns
    assert "macro_internal_response_norm" in frame.columns
    assert len(residual) == len(entries) * 24
    assert all("residual_norm" in row for row in residual)


def test_holdout_metadata_gate_requires_valid_lock(tmp_path: Path) -> None:
    config = module.load_config()
    trajectory_root = tmp_path / "corpus" / "trajectories"
    splits = {10: "fit", 11: "fit", 12: "fit", 13: "validation", 14: "holdout"}
    for seed, split in splits.items():
        for scenario in config["challenge"]["condition_groups"]:
            directory = trajectory_root / f"traj_{scenario}_{seed}"
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
    index = module.ChallengeIndex(tmp_path / "corpus", config)
    with pytest.raises(module.MacroDynamicsError, match="holdout read blocked"):
        index.entries_for("holdout")
    lock_path = tmp_path / "lock.json"
    validation_path = tmp_path / "validation.json"
    lock = module._create_lock(lock_path, {"candidate_id": "x"}, {}, config, "manifest")
    module._write_lock_validation(validation_path, lock)
    assert len(index.entries_for("holdout", lock_path=lock_path, validation_path=validation_path)) == 6


def test_near_state_pair_ordering_uses_predictions_not_metadata() -> None:
    config = module.load_config()
    rows = []
    for trajectory_index in range(5):
        for step in range(10):
            rows.append(
                {
                    "trajectory_id": f"t{trajectory_index}",
                    "scenario_id": "metadata_only",
                    "seed": trajectory_index,
                    "split": "validation",
                    "step": step,
                    "actual_event": int(step >= 6),
                    "actual_depth": 0.02 * trajectory_index + 0.01 * step,
                    "current__a": 0.1 * step,
                    "current__b": 0.01 * trajectory_index,
                }
            )
    frame = pd.DataFrame(rows)
    dataset = SimpleNamespace(frame=frame, current_feature_names=["current__a", "current__b"])
    pairs = module._near_state_pairs(dataset, config)
    assert pairs
    actual = frame["actual_depth"].to_numpy(dtype=float)
    assert module._pair_accuracy(pairs, actual, actual) == 1.0


def test_tampered_task4_lock_is_rejected(tmp_path: Path) -> None:
    config = module.load_config()
    lock_path = tmp_path / "lock.json"
    validation_path = tmp_path / "validation.json"
    lock = module._create_lock(lock_path, {"candidate_id": "x"}, {}, config, "manifest")
    module._write_lock_validation(validation_path, lock)
    value = json.loads(lock_path.read_text(encoding="utf-8"))
    value["selected_candidate"] = {"candidate_id": "changed"}
    lock_path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(module.MacroDynamicsError, match="hash mismatch"):
        module.validate_selection_lock(lock_path, validation_path)
