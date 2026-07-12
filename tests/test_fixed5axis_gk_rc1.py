from __future__ import annotations

import csv
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from fixed5axis_gk_rc1 import (  # noqa: E402
    AXIS_NAMES,
    Fixed5AxisGKError,
    HistoryAccumulator,
    build_corpus,
    build_trajectory,
    classify_adoption,
    derive_transition_metrics,
    load_contract,
    load_history_window,
    validate_contract,
    validate_distribution,
    validate_trajectory_artifact,
)


def _json_dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _distribution(step: int) -> np.ndarray:
    grid = np.indices((5, 5, 5, 5, 5)).sum(axis=0).astype(np.float64)
    value = np.exp(-((grid - (8.0 + 0.15 * step)) ** 2) / 4.0)
    value += (step + 1) * 1e-6
    value /= value.sum()
    return value.astype(np.float64)


def _make_source_trajectory(
    root: Path,
    *,
    trajectory_id: str = "traj_test_seed000",
    scenario_id: str = "test_scenario",
    seed: int = 0,
    split: str = "fit",
    frames: int = 4,
    mutate_distribution=None,
) -> Path:
    trajectory = root / "trajectories" / trajectory_id
    states = trajectory / "states"
    states.mkdir(parents=True)
    metadata = {
        "trajectory_id": trajectory_id,
        "scenario_id": scenario_id,
        "seed": seed,
        "initial_state_id": "distribution_terrain_v3_2_2_default_reset",
        "world_module": "pseudo_reality.distribution_terrain_v3_2_2",
        "world_class": "DistributionTerrainV322World",
        "world_version": "PseudoReality v3.3",
        "config_version": "test",
        "total_steps": frames - 1,
        "dataset_split": split,
    }
    _json_dump(trajectory / "metadata.json", metadata)
    steps: list[dict[str, object]] = []
    for step in range(frames):
        distribution = _distribution(step)
        if mutate_distribution is not None:
            distribution = mutate_distribution(step, distribution)
        state_ref = f"states/step_{step:06d}.npz"
        np.savez_compressed(
            trajectory / state_ref,
            distribution=distribution,
            damage=np.zeros((5, 5, 5, 5, 5), dtype=np.float64),
        )
        steps.append(
            {
                "trajectory_id": trajectory_id,
                "step": step,
                "phase": "pre_transition",
                "state_ref": state_ref,
                "history_available_through_step": None if step == 0 else step - 1,
                "observed_external_input": {
                    "external_resource_supply": 0.1 * step,
                    "external_demand": 0.0,
                    "external_competition_pressure": 0.0,
                    "external_information_noise": 0.0,
                    "external_shock": 0.0,
                    "external_constraint_pressure": 0.0,
                },
                "observed_events": [f"event_{step}"],
                "observed_action": None,
            }
        )
    _write_jsonl(trajectory / "steps.jsonl", steps)
    # These files deliberately contain future information. The G/K builder must not read or copy them.
    _write_jsonl(trajectory / "truth.jsonl", [{"future_risk_event": "collapse"}])
    _json_dump(trajectory / "summary.json", {"scenario_final_outcome": "collapse"})
    _write_jsonl(trajectory / "metrics.jsonl", [{"risk_score": 999.0}])
    return trajectory


def _hash_tree(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for file in sorted(path.rglob("*")):
        if file.is_file():
            result[file.relative_to(path).as_posix()] = hashlib.sha256(file.read_bytes()).hexdigest()
    return result


def test_builds_canonical_gt_and_complete_kt_without_truth_leak_or_writeback(tmp_path: Path) -> None:
    contract = load_contract(ROOT / "configs" / "fixed5axis_gk_rc1_contract.json")
    source = _make_source_trajectory(tmp_path / "source")
    before = _hash_tree(source)

    target = build_trajectory(source, tmp_path / "output", contract)
    after = _hash_tree(source)

    assert before == after
    mass = np.load(target / "gt_mass.npy", allow_pickle=False)
    assert mass.shape == (4, 5, 5, 5, 5, 5)
    assert mass.dtype == np.float64
    assert np.allclose(mass.sum(axis=(1, 2, 3, 4, 5)), 1.0, atol=1e-10)

    with (target / "history_ledger.csv").open("r", encoding="utf-8", newline="") as handle:
        ledger = list(csv.DictReader(handle))
    assert [row["continuity_status"] for row in ledger] == ["initial", "continuous", "continuous", "continuous"]
    assert [int(row["t"]) for row in ledger] == [0, 1, 2, 3]
    assert all(len(row["gt_hash"]) == 64 for row in ledger)
    assert all(len(row["history_chain_hash"]) == 64 for row in ledger)

    provenance = json.loads((target / "provenance.json").read_text(encoding="utf-8"))
    assert provenance["axis_order"] == list(AXIS_NAMES)
    assert provenance["forbidden_source_files_read"] == []
    assert "truth.jsonl" not in provenance["source_files_read"]
    assert not (target / "truth.jsonl").exists()
    assert not (target / "summary.json").exists()
    assert not (target / "metrics.jsonl").exists()

    validation = validate_trajectory_artifact(target, contract)
    assert validation["artifact_integrity_gate"] == "passed"
    assert validation["representation_hard_gate"] == "partial"
    assert validation["adoption_judgement"].startswith("B_")


def test_invalid_mass_is_rejected_without_clipping_or_renormalization(tmp_path: Path) -> None:
    contract = load_contract(ROOT / "configs" / "fixed5axis_gk_rc1_contract.json")

    def invalid(_step: int, distribution: np.ndarray) -> np.ndarray:
        broken = distribution.copy()
        broken.flat[0] = -1e-4
        return broken

    source = _make_source_trajectory(tmp_path / "source", mutate_distribution=invalid)
    with pytest.raises(Fixed5AxisGKError, match="negative mass"):
        build_trajectory(source, tmp_path / "output", contract)
    assert not (tmp_path / "output" / "trajectories" / "traj_test_seed000").exists()


def test_history_accumulator_records_gap_duplicate_out_of_order_and_source_mismatch(tmp_path: Path) -> None:
    contract = load_contract(ROOT / "configs" / "fixed5axis_gk_rc1_contract.json")
    source_hash = "a" * 64
    accumulator = HistoryAccumulator(contract=contract, trajectory_id="traj")
    for t, source_id in [(0, "traj"), (0, "traj"), (3, "traj"), (2, "traj"), (3, "other")]:
        accumulator.append(
            t=t,
            phase="pre_transition",
            distribution=_distribution(len(accumulator.ledger_rows)),
            source_state_ref=f"states/row_{len(accumulator.ledger_rows):06d}.npz",
            source_state_hash=source_hash,
            source_trajectory_id=source_id,
        )
    assert [row["continuity_status"] for row in accumulator.ledger_rows] == [
        "initial",
        "duplicate",
        "gap",
        "out_of_order",
        "source_mismatch",
    ]
    assert [row["admissible_for_research"] for row in accumulator.ledger_rows] == [True, False, False, False, False]


def test_rebuild_is_deterministic_and_append_only_target_is_protected(tmp_path: Path) -> None:
    contract = load_contract(ROOT / "configs" / "fixed5axis_gk_rc1_contract.json")
    source = _make_source_trajectory(tmp_path / "source")
    first = build_trajectory(source, tmp_path / "out_a", contract)
    second = build_trajectory(source, tmp_path / "out_b", contract)
    assert (first / "gt_mass.npy").read_bytes() == (second / "gt_mass.npy").read_bytes()
    assert (first / "history_ledger.csv").read_text(encoding="utf-8") == (
        second / "history_ledger.csv"
    ).read_text(encoding="utf-8")
    with pytest.raises(Fixed5AxisGKError, match="already exists"):
        build_trajectory(source, tmp_path / "out_a", contract)


def test_history_windows_and_transition_metrics_are_recomputable(tmp_path: Path) -> None:
    contract = load_contract(ROOT / "configs" / "fixed5axis_gk_rc1_contract.json")
    source = _make_source_trajectory(tmp_path / "source", frames=5)
    target = build_trajectory(source, tmp_path / "output", contract)

    window_mass, window_ledger = load_history_window(target, last_n=2, contract=contract)
    assert window_mass.shape == (2, 5, 5, 5, 5, 5)
    assert [int(row["t"]) for row in window_ledger] == [3, 4]

    first = derive_transition_metrics(target, contract=contract)
    second = derive_transition_metrics(target, contract=contract)
    assert first == second
    assert len(first) == 4
    assert all(row["jensen_shannon_distance"] >= 0.0 for row in first)
    assert all(row["hellinger_distance"] >= 0.0 for row in first)

    written = derive_transition_metrics(target, contract=contract, write=True)
    assert written == first
    assert (target / "derived" / "transition_metrics" / "transition_metrics_rc1" / "transition_metrics.csv").is_file()
    with pytest.raises(Fixed5AxisGKError, match="already exists"):
        derive_transition_metrics(target, contract=contract, write=True)


def test_corpus_build_preserves_trajectory_level_split_metadata(tmp_path: Path) -> None:
    source_root = tmp_path / "source"
    _make_source_trajectory(source_root, trajectory_id="traj_fit_seed000", seed=0, split="fit")
    _make_source_trajectory(
        source_root,
        trajectory_id="traj_validation_seed001",
        scenario_id="test_scenario_validation",
        seed=1,
        split="validation",
    )
    output = build_corpus(
        source_root,
        tmp_path / "corpus",
        ROOT / "configs" / "fixed5axis_gk_rc1_contract.json",
    )
    manifest = json.loads((output / "dataset_manifest.json").read_text(encoding="utf-8"))
    validation = json.loads((output / "validation.json").read_text(encoding="utf-8"))
    assert manifest["trajectory_count"] == 2
    assert manifest["split_counts"] == {"fit": 1, "validation": 1}
    assert manifest["research_adoption_not_yet_claimed"] is True
    assert validation["artifact_integrity_gate"] == "passed"
    assert validation["representation_hard_gate"] == "partial"


def test_contract_axis_reordering_is_rejected() -> None:
    contract = load_contract(ROOT / "configs" / "fixed5axis_gk_rc1_contract.json")
    broken = json.loads(json.dumps(contract))
    broken["axes"]["order"][0], broken["axes"]["order"][1] = (
        broken["axes"]["order"][1],
        broken["axes"]["order"][0],
    )
    with pytest.raises(Fixed5AxisGKError, match="axis order"):
        validate_contract(broken)


def test_distribution_sum_is_not_silently_repaired() -> None:
    contract = load_contract(ROOT / "configs" / "fixed5axis_gk_rc1_contract.json")
    distribution = _distribution(0) * 0.99
    with pytest.raises(Fixed5AxisGKError, match="does not sum to one"):
        validate_distribution(distribution, contract)


def test_adoption_classifier_preserves_pending_research_as_limited() -> None:
    assert classify_adoption({"representation_hard_gate": "failed"})["judgement"] == "C_rejected"
    assert (
        classify_adoption(
            {
                "representation_hard_gate": "passed",
                "external_response_gate": "passed",
                "history_value_gate": "passed",
                "holdout_gate": "passed",
            }
        )["judgement"]
        == "A_formal_adoption"
    )
    assert (
        classify_adoption(
            {
                "representation_hard_gate": "passed",
                "external_response_gate": "not_evaluated",
                "history_value_gate": "not_evaluated",
                "holdout_gate": "not_evaluated",
            }
        )["judgement"]
        == "B_limited_adoption"
    )
    assert classify_adoption({"representation_hard_gate": "partial"})["judgement"] == "B_limited_adoption"
