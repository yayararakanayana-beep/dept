from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

import task3_2_2_continuous_trajectory as module
from task3_2_1_macro_dynamics_contract import load_contract


@pytest.fixture()
def generated(tmp_path: Path) -> tuple[Path, dict, dict]:
    config = module.load_generation_config()
    output = tmp_path / "corpus"
    result = module.generate_corpus(
        output,
        "smoke",
        scenarios=["stable_continuation", "natural_recovery"],
        seeds=[0, 1],
        transitions_override=10,
        reproducibility_check=False,
    )
    return output, result, config


def test_small_corpus_generation_and_validation(generated: tuple[Path, dict, dict]) -> None:
    output, result, config = generated
    assert result["trajectory_count"] == 4
    assert result["validation"]["status"] == "valid"
    assert result["validation"]["scenario_difference_check"] == "passed"
    assert result["validation"]["seed_difference_check"] == "passed"
    assert (output / "corpus_summary.json").is_file()
    assert (output / "scenario_comparison.csv").is_file()
    assert (output / "trajectory_overview.svg").is_file()
    assert (output / "manifest.json").is_file()
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["file_count"] > 0
    assert manifest["total_size_bytes"] > 0


def test_state_snapshots_contain_all_required_arrays(generated: tuple[Path, dict, dict]) -> None:
    output, _, config = generated
    contract = load_contract(Path(module.ROOT) / config["contract_path"])
    trajectory = sorted((output / "trajectories").glob("traj_*"))[0]
    state_files = sorted((trajectory / "states").glob("*.npz"))
    assert len(state_files) == 11
    with np.load(state_files[0], allow_pickle=False) as bundle:
        required = set(contract["step_record"]["required_state_arrays"])
        assert required.issubset(bundle.files)
        for name in required:
            assert bundle[name].shape == (5, 5, 5, 5, 5)
            assert np.all(np.isfinite(bundle[name]))
        assert np.min(bundle["distribution"]) >= 0.0
        assert np.sum(bundle["distribution"]) == pytest.approx(1.0, abs=1e-5)


def test_model_input_contains_no_scenario_or_future_truth(generated: tuple[Path, dict, dict]) -> None:
    output, _, _ = generated
    trajectory = sorted((output / "trajectories").glob("traj_*"))[0]
    rows = [json.loads(line) for line in (trajectory / "steps.jsonl").read_text(encoding="utf-8").splitlines()]
    for row in rows:
        serialized = json.dumps(row["model_input"], sort_keys=True)
        assert "scenario_id" not in row["model_input"]
        assert "future_risk_event" not in serialized
        assert "next_state_ref" not in serialized
        assert "irreversibility_level" not in serialized


def test_scenario_name_is_not_used_by_outcome_classifier() -> None:
    config = module.load_generation_config()
    metrics = []
    for step in range(12):
        metrics.append(
            {
                "risk_score": 0.20 + 0.001 * step,
                "concentration": 0.002,
                "moved_mass": 0.04,
                "weighted_rigidity": 0.05,
            }
        )
    first = module._analyse_outcome(metrics, config["provisional_outcome_rules"])
    second = module._analyse_outcome(metrics, config["provisional_outcome_rules"])
    assert first == second
    assert first["label_source"] == "measured_trajectory_not_scenario_id"


def test_same_seed_and_scenario_are_deterministic(tmp_path: Path) -> None:
    config = module.load_generation_config()
    contract = load_contract(Path(module.ROOT) / config["contract_path"])
    scenario = config["scenarios"]["stable_continuation"]
    first = module.generate_trajectory(
        tmp_path / "first",
        "smoke",
        "stable_continuation",
        scenario,
        0,
        4,
        "exploratory",
        config,
        contract,
    )
    second = module.generate_trajectory(
        tmp_path / "second",
        "smoke",
        "stable_continuation",
        scenario,
        0,
        4,
        "exploratory",
        config,
        contract,
    )
    assert first["trajectory_fingerprint"] == second["trajectory_fingerprint"]
    assert first["outcome"] == second["outcome"]


def test_mutated_distribution_is_rejected(generated: tuple[Path, dict, dict]) -> None:
    output, _, config = generated
    contract = load_contract(Path(module.ROOT) / config["contract_path"])
    trajectory = sorted((output / "trajectories").glob("traj_*"))[0]
    state_path = trajectory / "states" / "step_000001.npz"
    with np.load(state_path, allow_pickle=False) as original:
        payload = {name: np.asarray(original[name]).copy() for name in original.files}
    payload["distribution"].flat[0] = -0.5
    np.savez_compressed(state_path, **payload)
    with pytest.raises(module.TrajectoryError, match="negative mass"):
        module.validate_trajectory_directory(trajectory, contract, config)


def test_generation_config_has_six_contiguous_scenarios() -> None:
    config = module.load_generation_config()
    assert len(config["scenario_order"]) == 6
    for scenario_id in config["scenario_order"]:
        segments = config["scenarios"][scenario_id]["segments"]
        assert segments[0]["start"] == 0
        assert segments[-1]["end"] is None
        for left, right in zip(segments, segments[1:], strict=True):
            assert left["end"] == right["start"]
