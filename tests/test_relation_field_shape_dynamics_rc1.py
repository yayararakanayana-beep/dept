from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from relation_field_grid_rc1 import build_grid_artifact, cell_id_from_indices  # noqa: E402
from relation_field_hodge_decomposition_rc1 import build_hodge_decomposition  # noqa: E402
from relation_field_shape_dynamics_rc1 import (  # noqa: E402
    RelationFieldShapeError,
    _aggregate_unique_candidate_metrics,
    _load_grid_with_indices,
    _load_parent_artifacts,
    _stack_frame_metrics,
    _stack_transition_metrics,
    build_shape_dynamics,
    load_contract,
    validate_shape_dynamics,
)
from relation_field_single_transition_rc1 import (  # noqa: E402
    GENESIS_HASH,
    _compute_gt_hash,
    _compute_history_chain_hash,
)
from relation_field_temporal_consistency_rc1 import build_temporal_relation_field  # noqa: E402

LEDGER_FIELDS = [
    "trajectory_id",
    "source_trajectory_id",
    "t",
    "phase",
    "gt_row_index",
    "gt_hash",
    "previous_gt_hash",
    "history_chain_hash",
    "delta_t",
    "continuity_status",
    "admissible_for_research",
    "source_state_ref",
    "source_state_hash",
]


def _distribution(entries: dict[tuple[int, int, int, int, int], float]) -> np.ndarray:
    flat = np.zeros(3125, dtype=np.float64)
    for indices, mass in entries.items():
        flat[cell_id_from_indices(indices)] = float(mass)
    assert np.isclose(flat.sum(), 1.0)
    return flat.reshape((5, 5, 5, 5, 5))


def _write_trajectory(
    root: Path,
    frames: list[np.ndarray],
    *,
    trajectory_id: str = "traj_rf7_test",
) -> Path:
    root.mkdir(parents=True)
    np.save(root / "gt_mass.npy", np.stack(frames), allow_pickle=False)
    rows: list[dict[str, object]] = []
    previous_gt_hash = ""
    history_chain_hash = GENESIS_HASH
    for t, frame in enumerate(frames):
        frame_digest = hashlib.sha256(np.ascontiguousarray(frame).tobytes()).hexdigest()
        source_state_hash = hashlib.sha256(f"rf7-source-{t}-{frame_digest}".encode()).hexdigest()
        gt_hash = _compute_gt_hash(
            trajectory_id=trajectory_id,
            t=t,
            distribution=frame,
            source_state_hash=source_state_hash,
        )
        history_chain_hash = _compute_history_chain_hash(history_chain_hash, gt_hash, t)
        rows.append(
            {
                "trajectory_id": trajectory_id,
                "source_trajectory_id": trajectory_id,
                "t": t,
                "phase": "pre_transition",
                "gt_row_index": t,
                "gt_hash": gt_hash,
                "previous_gt_hash": previous_gt_hash,
                "history_chain_hash": history_chain_hash,
                "delta_t": 0 if t == 0 else 1,
                "continuity_status": "initial" if t == 0 else "continuous",
                "admissible_for_research": True,
                "source_state_ref": f"states/step_{t:06d}.npz",
                "source_state_hash": source_state_hash,
            }
        )
        previous_gt_hash = gt_hash
    with (root / "history_ledger.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEDGER_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return root


def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _build_parent_chain(root: Path, frames: list[np.ndarray], *, trajectory_id: str = "traj_rf7_test") -> tuple[Path, Path, Path, Path]:
    grid = build_grid_artifact(root / "grid")
    trajectory = _write_trajectory(root / "trajectory", frames, trajectory_id=trajectory_id)
    rf5 = build_temporal_relation_field(trajectory, grid, root / "rf5", start_t=0, to_t=2)
    rf6 = build_hodge_decomposition(rf5, grid, root / "rf6")
    return grid, trajectory, rf5, rf6


@pytest.fixture(scope="module")
def split_merge_fixture(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path, Path, Path, Path, Path]:
    root = tmp_path_factory.mktemp("rf7-split-merge")
    center = _distribution({(2, 2, 2, 2, 2): 1.0})
    split = _distribution({(2, 2, 2, 2, 1): 0.5, (2, 2, 2, 2, 3): 0.5})
    grid, trajectory, rf5, rf6 = _build_parent_chain(root, [center, split, center])
    source_hashes = {
        "trajectory": _tree_hashes(trajectory),
        "rf5": _tree_hashes(rf5),
        "rf6": _tree_hashes(rf6),
    }
    first = build_shape_dynamics(trajectory, rf5, rf6, grid, root / "rf7_a")
    second = build_shape_dynamics(trajectory, rf5, rf6, grid, root / "rf7_b")
    assert source_hashes["trajectory"] == _tree_hashes(trajectory)
    assert source_hashes["rf5"] == _tree_hashes(rf5)
    assert source_hashes["rf6"] == _tree_hashes(rf6)
    return grid, trajectory, rf5, rf6, first, second


def test_rf7_contract_keeps_shape_candidates_separate_from_risk() -> None:
    contract = load_contract()

    assert contract["status"] == "implemented_for_rf8_axis_coupling"
    assert contract["transition_shape_metrics"]["classification_is_diagnostic_only"] is True
    assert contract["flow_channel_metrics"]["duplicate_candidate_ids_must_be_removed_before_aggregation"] is True
    assert contract["semantic_limits"]["basin_or_attractor_semantics_not_assigned"] is True
    assert contract["semantic_limits"]["irreversibility_or_risk_not_assigned"] is True
    assert contract["acceptance"]["scientific_claim"] == "B_limited_shape_dynamics_on_fixed_grid"


def test_translation_is_not_mislabeled_as_expansion(tmp_path: Path) -> None:
    grid_path = build_grid_artifact(tmp_path / "grid")
    grid = _load_grid_with_indices(grid_path)
    before = _distribution({(2, 2, 2, 1, 1): 0.5, (2, 2, 2, 1, 2): 0.5})
    after = _distribution({(2, 2, 2, 2, 1): 0.5, (2, 2, 2, 2, 2): 0.5})
    frame_arrays, _, _ = _stack_frame_metrics([before, after], [0, 1], grid, load_contract())
    transition_arrays, labels = _stack_transition_metrics([before, after], frame_arrays, grid, load_contract())
    row = labels["transitions"][0]

    assert transition_arrays["centroid_shift_norm"][0] == pytest.approx(0.25)
    assert abs(transition_arrays["total_variance_delta"][0]) < 1e-12
    assert abs(transition_arrays["entropy_delta"][0]) < 1e-12
    assert row["translation_without_detected_shape_change"] is True
    assert row["expansion_candidate"] is False
    assert row["contraction_candidate"] is False


def test_split_then_merge_recovers_shape_consensus(
    split_merge_fixture: tuple[Path, Path, Path, Path, Path, Path],
) -> None:
    _, _, _, _, artifact, _ = split_merge_fixture
    labels = json.loads((artifact / "transition_labels.json").read_text(encoding="utf-8"))["transitions"]
    with np.load(artifact / "transition_shape_metrics.npz", allow_pickle=False) as loaded:
        variance_delta = loaded["total_variance_delta"]
        entropy_delta = loaded["entropy_delta"]
        major_delta = loaded["major_component_count_delta"]

    assert variance_delta[0] > 0.0 and entropy_delta[0] > 0.0 and major_delta[0] == 1
    assert labels[0]["expansion_candidate"] is True
    assert labels[0]["dispersion_candidate"] is True
    assert labels[0]["split_candidate"] is True
    assert labels[0]["fragmentation_candidate"] is True

    assert variance_delta[1] < 0.0 and entropy_delta[1] < 0.0 and major_delta[1] == -1
    assert labels[1]["contraction_candidate"] is True
    assert labels[1]["concentration_candidate"] is True
    assert labels[1]["merge_candidate"] is True
    assert labels[1]["coalescence_candidate"] is True


def test_frame_components_preserve_threshold_and_major_component_details(
    split_merge_fixture: tuple[Path, Path, Path, Path, Path, Path],
) -> None:
    _, _, _, _, artifact, _ = split_merge_fixture
    payload = json.loads((artifact / "frame_components.json").read_text(encoding="utf-8"))
    middle = payload["frames"][1]

    assert middle["component_count"] == 2
    assert middle["major_component_count"] == 2
    assert [component["mass"] for component in middle["components"]] == pytest.approx([0.5, 0.5])
    assert middle["active_threshold"] == pytest.approx(5e-7)


def test_rf7_artifact_is_deterministic_and_valid(
    split_merge_fixture: tuple[Path, Path, Path, Path, Path, Path],
) -> None:
    grid, trajectory, rf5, rf6, first, second = split_merge_fixture

    assert _tree_hashes(first) == _tree_hashes(second)
    validation = validate_shape_dynamics(first, trajectory, rf5, rf6, grid)
    assert validation["rf7_shape_dynamics_gate"] == "passed"
    assert validation["parent_identity_gate"] is True
    assert validation["candidate_deduplication_gate"] is True
    assert validation["causal_cutoff_gate"] is True
    assert validation["risk_prediction_performed"] is False


def test_saved_path_multiplicity_does_not_weight_candidate_statistics(
    split_merge_fixture: tuple[Path, Path, Path, Path, Path, Path],
) -> None:
    grid_path, trajectory, rf5, rf6, artifact, _ = split_merge_fixture
    parent = _load_parent_artifacts(rf5, rf6, grid_path)
    grid = _load_grid_with_indices(grid_path)
    contract = load_contract()
    with np.load(artifact / "frame_shape_metrics.npz", allow_pickle=False) as loaded:
        frame_arrays = {name: loaded[name].copy() for name in loaded.files}
    with np.load(artifact / "transition_shape_metrics.npz", allow_pickle=False) as loaded:
        transition_arrays = {name: loaded[name].copy() for name in loaded.files}
    frames = [np.asarray(frame) for frame in np.load(trajectory / "gt_mass.npy", allow_pickle=False)]

    baseline = _aggregate_unique_candidate_metrics(frames, parent, frame_arrays, transition_arrays, grid, contract)[0]
    duplicated_parent = dict(parent)
    duplicated_parent["optimal_paths"] = parent["optimal_paths"] * 5
    duplicated = _aggregate_unique_candidate_metrics(frames, duplicated_parent, frame_arrays, transition_arrays, grid, contract)[0]

    assert np.array_equal(baseline["unique_candidate_count"], duplicated["unique_candidate_count"])
    assert np.allclose(baseline["effective_edge_support_mean"], duplicated["effective_edge_support_mean"])
    assert np.allclose(baseline["gradient_energy_mean"], duplicated["gradient_energy_mean"])


def test_flow_channel_narrowing_is_detected_from_unique_candidate_support(tmp_path: Path) -> None:
    grid_path = build_grid_artifact(tmp_path / "grid")
    grid = _load_grid_with_indices(grid_path)
    contract = load_contract()
    frame = _distribution({(2, 2, 2, 2, 2): 1.0})
    frames = [frame, frame, frame]
    frame_arrays, _, _ = _stack_frame_metrics(frames, [0, 1, 2], grid, contract)
    transition_arrays, _ = _stack_transition_metrics(frames, frame_arrays, grid, contract)
    wide = np.zeros(12500, dtype=np.float64)
    wide[0] = 0.5
    wide[1] = 0.5
    narrow = np.zeros(12500, dtype=np.float64)
    narrow[0] = 1.0
    candidate_flow = np.stack([wide, narrow])
    parent = {
        "offsets": np.asarray([0, 1, 2], dtype=np.int32),
        "optimal_paths": [[0, 0]],
        "candidate_flow": candidate_flow,
        "gradient_flow": candidate_flow.copy(),
        "circulation_flow": np.zeros_like(candidate_flow),
        "node_potential": np.zeros((2, 3125), dtype=np.float64),
        "transition_times": np.asarray([1, 2], dtype=np.int32),
    }

    flow_arrays, _, _, labels = _aggregate_unique_candidate_metrics(
        frames, parent, frame_arrays, transition_arrays, grid, contract
    )

    assert flow_arrays["effective_edge_support_mean"].tolist() == pytest.approx([2.0, 1.0])
    assert flow_arrays["maximum_edge_fraction_mean"].tolist() == pytest.approx([0.5, 1.0])
    assert labels["transitions"][1]["flow_channel_narrowing_candidate"] is True
    assert labels["transitions"][1]["flow_channel_widening_candidate"] is False


def test_boundary_sticking_detects_persistent_boundary_mass_with_no_inward_flow(tmp_path: Path) -> None:
    boundary = _distribution({(0, 0, 0, 0, 0): 1.0})
    grid, trajectory, rf5, rf6 = _build_parent_chain(tmp_path, [boundary, boundary, boundary], trajectory_id="traj_rf7_boundary")
    artifact = build_shape_dynamics(trajectory, rf5, rf6, grid, tmp_path / "rf7")

    with np.load(artifact / "boundary_dynamics.npz", allow_pickle=False) as loaded:
        persistence = loaded["boundary_mass_persistence"]
        inward = loaded["mass_weighted_inward_flow_mean"]
        sticking = loaded["boundary_sticking_candidate"]

    assert np.array_equal(persistence, np.ones(2))
    assert np.array_equal(inward, np.zeros(2))
    assert np.array_equal(sticking, np.ones(2, dtype=np.uint8))


def test_future_suffix_does_not_change_rf7_prefix_artifact(tmp_path: Path) -> None:
    center = _distribution({(2, 2, 2, 2, 2): 1.0})
    split = _distribution({(2, 2, 2, 2, 1): 0.5, (2, 2, 2, 2, 3): 0.5})
    suffix_a = _distribution({(1, 1, 1, 1, 1): 1.0})
    suffix_b = _distribution({(3, 3, 3, 3, 3): 1.0})

    grid = build_grid_artifact(tmp_path / "grid")
    trajectory_a = _write_trajectory(tmp_path / "trajectory_a", [center, split, center, suffix_a], trajectory_id="traj_rf7_prefix")
    trajectory_b = _write_trajectory(tmp_path / "trajectory_b", [center, split, center, suffix_b], trajectory_id="traj_rf7_prefix")
    rf5_a = build_temporal_relation_field(trajectory_a, grid, tmp_path / "rf5_a", start_t=0, to_t=2)
    rf5_b = build_temporal_relation_field(trajectory_b, grid, tmp_path / "rf5_b", start_t=0, to_t=2)
    rf6_a = build_hodge_decomposition(rf5_a, grid, tmp_path / "rf6_a")
    rf6_b = build_hodge_decomposition(rf5_b, grid, tmp_path / "rf6_b")
    rf7_a = build_shape_dynamics(trajectory_a, rf5_a, rf6_a, grid, tmp_path / "rf7_a")
    rf7_b = build_shape_dynamics(trajectory_b, rf5_b, rf6_b, grid, tmp_path / "rf7_b")

    assert _tree_hashes(rf5_a) == _tree_hashes(rf5_b)
    assert _tree_hashes(rf6_a) == _tree_hashes(rf6_b)
    assert _tree_hashes(rf7_a) == _tree_hashes(rf7_b)


def test_manifest_tampering_and_overwrite_are_rejected(
    tmp_path: Path,
    split_merge_fixture: tuple[Path, Path, Path, Path, Path, Path],
) -> None:
    grid, trajectory, rf5, rf6, artifact, _ = split_merge_fixture
    copied = tmp_path / "copied"
    shutil.copytree(artifact, copied)
    summary = copied / "summary.json"
    summary.write_text(summary.read_text(encoding="utf-8") + " ", encoding="utf-8")

    with pytest.raises(RelationFieldShapeError, match="manifest"):
        validate_shape_dynamics(copied, trajectory, rf5, rf6, grid)
    with pytest.raises(RelationFieldShapeError, match="already exists"):
        build_shape_dynamics(trajectory, rf5, rf6, grid, artifact)
