from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

import task3_2_3_simple_early_warning as module


def _feature_row(risk: float, concentration: float = 0.01, mobility: float = 0.1, rigidity: float = 0.1) -> dict[str, float]:
    config = module.load_config()
    row = {
        "risk_score": risk,
        "entropy": 1.0,
        "concentration": concentration,
        "max_mass": 0.02,
        "moved_mass": mobility,
    }
    for axis in ("resource_slack", "information_quality", "pressure", "exploration_room", "reversibility"):
        row[f"center_{axis}"] = 0.5
        row[f"spread_{axis}"] = 0.2
    for name in config["current_weighted_arrays"]:
        row[f"weighted_{name}"] = rigidity if name == "rigidity" else 0.1
    for name in config["transition_weighted_arrays"]:
        row[f"weighted_{name}"] = 0.01
    for name in config["transition_scalar_fields"]:
        row[name] = 0.0
    for name in module.EXTERNAL_FIELDS:
        row[name] = 0.0
    return row


def _series(seed: int, split: str, scenario: str, risks: list[float]) -> module.TrajectorySeries:
    entry = module.CorpusEntry(
        trajectory_id=f"traj_{scenario}_{seed}",
        scenario_id=scenario,
        seed=seed,
        split=split,
        path=Path("."),
        total_steps=len(risks) - 1,
    )
    return module.TrajectorySeries(entry=entry, features=[_feature_row(value) for value in risks])


def test_config_and_feature_boundary() -> None:
    config = module.load_config()
    assert config["history_widths"] == [2, 4, 8]
    assert config["prediction_horizons"] == [4, 8, 16]
    module.audit_feature_names(["current__risk_score", "history__risk_score__slope"], config)
    with pytest.raises(module.BaselineError, match="forbidden"):
        module.audit_feature_names(["current__scenario_id"], config)


def test_future_truth_uses_same_seed_reference_and_not_scenario_name() -> None:
    config = module.load_config()
    calibration = json.loads((module.ROOT / config["calibration_config_path"]).read_text(encoding="utf-8"))
    reference = _series(0, "fit", "stable_continuation", [0.2] * 12)
    target = _series(0, "fit", "natural_recovery", [0.2] * 5 + [0.23, 0.24, 0.25, 0.26, 0.27, 0.28, 0.29])
    module.attach_future_truth([reference, target], config, calibration)
    assert reference.hazard_onset_step is None
    assert target.hazard_onset_step is not None
    assert target.relative_risk is not None
    assert target.relative_risk[-1] == pytest.approx(0.09)


def test_windows_exclude_current_or_post_onset_hazard() -> None:
    config = module.load_config()
    calibration = json.loads((module.ROOT / config["calibration_config_path"]).read_text(encoding="utf-8"))
    reference = _series(0, "fit", "stable_continuation", [0.2] * 16)
    target = _series(0, "fit", "persistent_deterioration", [0.2] * 6 + [0.23 + 0.01 * i for i in range(10)])
    module.attach_future_truth([reference, target], config, calibration)
    dataset = module.build_window_dataset([target], history_width=2, horizon=4, config=config)
    assert target.hazard_onset_step is not None
    assert int(dataset.frame["step"].max()) < int(target.hazard_onset_step)
    assert dataset.frame["actual_event"].sum() > 0


def test_holdout_read_is_blocked_until_lock_validation(tmp_path: Path) -> None:
    config = module.load_config()
    corpus = tmp_path / "corpus" / "trajectories"
    split_by_seed = {0: "fit", 1: "fit", 2: "fit", 3: "validation", 4: "holdout"}
    for seed, split in split_by_seed.items():
        directory = corpus / f"traj_stable_{seed}"
        directory.mkdir(parents=True)
        (directory / "metadata.json").write_text(
            json.dumps(
                {
                    "trajectory_id": f"traj_stable_{seed}",
                    "scenario_id": "stable_continuation",
                    "seed": seed,
                    "dataset_split": split,
                    "total_steps": 8,
                }
            ),
            encoding="utf-8",
        )
    index = module.CorpusIndex(tmp_path / "corpus", config)
    with pytest.raises(module.BaselineError, match="holdout read blocked"):
        index.entries_for("holdout")
    lock_path = tmp_path / "selection_lock.json"
    validation_path = tmp_path / "selection_lock_validation.json"
    lock = module.create_selection_lock(
        lock_path,
        "candidate",
        {"selected_overall": {}, "best_current": {}, "best_history": {}},
        config,
        "feature-hash",
        "corpus-hash",
        {},
    )
    module.write_selection_validation(validation_path, lock)
    assert len(index.entries_for("holdout", selection_lock_path=lock_path, selection_validation_path=validation_path)) == 1


def test_tampered_selection_lock_is_rejected(tmp_path: Path) -> None:
    config = module.load_config()
    lock_path = tmp_path / "selection_lock.json"
    validation_path = tmp_path / "selection_lock_validation.json"
    lock = module.create_selection_lock(
        lock_path,
        "candidate",
        {"selected_overall": {}, "best_current": {}, "best_history": {}},
        config,
        "feature-hash",
        "corpus-hash",
        {},
    )
    module.write_selection_validation(validation_path, lock)
    value = json.loads(lock_path.read_text(encoding="utf-8"))
    value["selected_overall"] = "changed-after-lock"
    lock_path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(module.BaselineError, match="hash mismatch"):
        module.validate_selection_lock(lock_path, validation_path)


def _window_dataset() -> module.WindowDataset:
    rows = []
    for trajectory_index in range(4):
        for step in range(8):
            risk = 0.1 + 0.03 * step + 0.02 * trajectory_index
            rows.append(
                {
                    "trajectory_id": f"t{trajectory_index}",
                    "scenario_id": "audit_only",
                    "seed": trajectory_index,
                    "split": "fit",
                    "step": step,
                    "history_width": 2,
                    "horizon": 4,
                    "actual_event": int(step >= 4),
                    "actual_depth": max(0.0, risk - 0.2),
                    "actual_hazard_duration": max(0, step - 3),
                    "actual_recovery_difficulty": int(step >= 5),
                    "hazard_onset_step": 5,
                    "next_hazard_step": 5 if step < 5 else None,
                    "current__risk_score": risk,
                    "current__entropy": 1.0 - 0.01 * step,
                    "history__risk_score__slope": 0.03,
                }
            )
    frame = pd.DataFrame(rows)
    return module.WindowDataset(
        frame=frame,
        feature_names=["current__risk_score", "current__entropy", "history__risk_score__slope"],
        current_feature_names=["current__risk_score", "current__entropy"],
        history_width=2,
        horizon=4,
    )


def test_five_model_families_fit_deterministically() -> None:
    config = module.load_config()
    dataset = _window_dataset()
    for family in config["model_families"]:
        first = module.fit_model(dataset, family, config)
        second = module.fit_model(dataset, family, config)
        probability_first, depth_first = module.predict_model(first, dataset)
        probability_second, depth_second = module.predict_model(second, dataset)
        assert np.allclose(probability_first, probability_second)
        assert np.allclose(depth_first, depth_second)
        assert np.all((probability_first >= 0.0) & (probability_first <= 1.0))
        assert np.all(depth_first >= 0.0)


def test_alarm_persistence_requires_consecutive_threshold_crossings() -> None:
    config = module.load_config()
    dataset = _window_dataset()
    probability = np.asarray([0.9, 0.1, 0.9, 0.9, 0.1, 0.9, 0.9, 0.9] * 4, dtype=np.float64)
    depth = np.zeros(len(dataset.frame), dtype=np.float64)
    _, predictions, _ = module.evaluate_predictions(
        dataset,
        probability,
        depth,
        threshold=0.8,
        persistence=2,
        config=config,
    )
    first = predictions[predictions["trajectory_id"] == "t0"].sort_values("step")
    assert first["alarm"].tolist() == [0, 0, 0, 1, 0, 0, 1, 1]


def test_candidate_identifiers_keep_current_and_history_scopes_distinct() -> None:
    assert module.candidate_id("current_state_logistic", 8, 4) == "current_state_logistic__H04"
    assert module.candidate_id("history_logistic", 4, 8) == "history_logistic__W04__H08"
