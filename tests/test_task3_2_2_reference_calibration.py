from __future__ import annotations

import json
from pathlib import Path

import pytest

import task3_2_2_continuous_trajectory as trajectory
import task3_2_2_reference_calibration as calibration


@pytest.fixture(scope="module")
def calibrated_corpus(tmp_path_factory: pytest.TempPathFactory) -> Path:
    output = tmp_path_factory.mktemp("task3_2_2_calibrated") / "corpus"
    trajectory.generate_corpus(
        output,
        "smoke",
        scenarios=["stable_continuation", "natural_recovery"],
        seeds=[0, 1],
        transitions_override=10,
        reproducibility_check=False,
    )
    result = calibration.calibrate_corpus(output)
    assert result["validation"]["stable_reference_calibration"] == "passed"
    return output


def test_stable_reference_is_not_mislabeled_as_deterioration(calibrated_corpus: Path) -> None:
    summary = json.loads((calibrated_corpus / "corpus_summary.json").read_text(encoding="utf-8"))
    stable = [item for item in summary["summaries"] if item["scenario_id"] == "stable_continuation"]
    assert len(stable) == 2
    assert {item["outcome"]["coarse_outcome"] for item in stable} == {"stable"}
    assert {item["outcome"]["future_risk_event"] for item in stable} == {"none"}
    assert all(
        item["outcome"]["label_source"]
        == "measured_trajectory_relative_to_same_seed_stable_reference"
        for item in stable
    )


def test_calibration_rewrites_truth_without_future_input_leakage(calibrated_corpus: Path) -> None:
    stable_dir = sorted(
        path for path in (calibrated_corpus / "trajectories").glob("traj_*stable_continuation*")
    )[0]
    truth = [json.loads(line) for line in (stable_dir / "truth.jsonl").read_text(encoding="utf-8").splitlines()]
    steps = [json.loads(line) for line in (stable_dir / "steps.jsonl").read_text(encoding="utf-8").splitlines()]
    assert all(row["future_risk_event"] == "none" for row in truth)
    assert all("future_risk_event" not in json.dumps(row["model_input"]) for row in steps)
    validation = json.loads((stable_dir / "validation.json").read_text(encoding="utf-8"))
    assert validation["future_leakage_check"] == "passed"
    assert validation["stable_reference_calibration"] == "passed"


def test_relative_classifier_distinguishes_stable_fixation_and_collapse() -> None:
    config = calibration.load_calibration_config()
    rules = config["rules"]
    reference = []
    stable = []
    fixation = []
    collapse = []
    for step in range(20):
        reference_row = {
            "risk_score": 0.25 + 0.001 * step,
            "concentration": 0.002,
            "moved_mass": 0.05,
            "weighted_rigidity": 0.08,
        }
        reference.append(reference_row)
        stable.append(dict(reference_row))
        fixation.append(
            {
                "risk_score": reference_row["risk_score"] + (0.0 if step < 6 else 0.12),
                "concentration": reference_row["concentration"] * (1.0 if step < 6 else 1.15),
                "moved_mass": reference_row["moved_mass"] * (1.0 if step < 6 else 0.6),
                "weighted_rigidity": reference_row["weighted_rigidity"] + (0.0 if step < 6 else 0.30),
            }
        )
        collapse.append(
            {
                "risk_score": reference_row["risk_score"] + (0.0 if step < 6 else 0.30),
                "concentration": reference_row["concentration"] * (1.0 if step < 6 else 1.30),
                "moved_mass": reference_row["moved_mass"] * (1.0 if step < 6 else 0.3),
                "weighted_rigidity": reference_row["weighted_rigidity"] + (0.0 if step < 6 else 0.40),
            }
        )
    assert calibration.analyse_relative_outcome(stable, reference, rules)["coarse_outcome"] == "stable"
    assert calibration.analyse_relative_outcome(fixation, reference, rules)["coarse_outcome"] == "fixation_candidate"
    assert (
        calibration.analyse_relative_outcome(collapse, reference, rules)["coarse_outcome"]
        == "collapse_or_divergence_candidate"
    )


def test_calibration_requires_same_seed_stable_reference(tmp_path: Path) -> None:
    output = tmp_path / "missing_reference"
    trajectory.generate_corpus(
        output,
        "smoke",
        scenarios=["natural_recovery"],
        seeds=[0],
        transitions_override=4,
        reproducibility_check=False,
    )
    with pytest.raises(calibration.CalibrationError, match="stable_continuation"):
        calibration.calibrate_corpus(output)
