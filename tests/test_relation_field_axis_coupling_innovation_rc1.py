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

from relation_field_axis_coupling_innovation_rc1 import (  # noqa: E402
    RelationFieldAxisCouplingError,
    build_axis_coupling_innovation,
    compute_axis_flow_family,
    compute_history_innovation,
    compute_lag_feedback,
    compute_position_flow_coupling,
    load_contract,
    validate_axis_coupling_innovation,
)
from relation_field_grid_rc1 import build_grid_artifact, cell_id_from_indices  # noqa: E402
from relation_field_hodge_decomposition_rc1 import build_hodge_decomposition  # noqa: E402
from relation_field_shape_dynamics_rc1 import build_shape_dynamics  # noqa: E402
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


def _point(indices: tuple[int, int, int, int, int]) -> np.ndarray:
    flat = np.zeros(3125, dtype=np.float64)
    flat[cell_id_from_indices(indices)] = 1.0
    return flat.reshape((5, 5, 5, 5, 5))


def _write_trajectory(
    root: Path,
    frames: list[np.ndarray],
    *,
    trajectory_id: str = "traj_rf8_test",
) -> Path:
    root.mkdir(parents=True)
    np.save(root / "gt_mass.npy", np.stack(frames), allow_pickle=False)
    rows: list[dict[str, object]] = []
    previous_gt_hash = ""
    history_chain_hash = GENESIS_HASH
    for t, frame in enumerate(frames):
        frame_digest = hashlib.sha256(np.ascontiguousarray(frame).tobytes()).hexdigest()
        source_state_hash = hashlib.sha256(f"rf8-source-{t}-{frame_digest}".encode()).hexdigest()
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


def _build_chain(
    root: Path,
    frames: list[np.ndarray],
    *,
    trajectory_id: str = "traj_rf8_test",
) -> tuple[Path, Path, Path, Path, Path]:
    grid = build_grid_artifact(root / "grid")
    trajectory = _write_trajectory(root / "trajectory", frames, trajectory_id=trajectory_id)
    rf5 = build_temporal_relation_field(trajectory, grid, root / "rf5", start_t=0, to_t=4)
    rf6 = build_hodge_decomposition(rf5, grid, root / "rf6")
    rf7 = build_shape_dynamics(trajectory, rf5, rf6, grid, root / "rf7")
    return grid, trajectory, rf5, rf6, rf7


@pytest.fixture(scope="module")
def rf8_fixture(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path, Path, Path, Path, Path, Path]:
    root = tmp_path_factory.mktemp("rf8-axis-coupling")
    frames = [
        _point((0, 2, 2, 2, 2)),
        _point((1, 2, 2, 2, 2)),
        _point((2, 2, 2, 2, 2)),
        _point((3, 2, 2, 2, 2)),
        _point((3, 3, 2, 2, 2)),
    ]
    grid, trajectory, rf5, rf6, rf7 = _build_chain(root, frames)
    source_hashes = {
        "trajectory": _tree_hashes(trajectory),
        "rf5": _tree_hashes(rf5),
        "rf6": _tree_hashes(rf6),
        "rf7": _tree_hashes(rf7),
    }
    first = build_axis_coupling_innovation(trajectory, grid, rf5, rf6, rf7, root / "rf8_a")
    second = build_axis_coupling_innovation(trajectory, grid, rf5, rf6, rf7, root / "rf8_b")
    assert source_hashes["trajectory"] == _tree_hashes(trajectory)
    assert source_hashes["rf5"] == _tree_hashes(rf5)
    assert source_hashes["rf6"] == _tree_hashes(rf6)
    assert source_hashes["rf7"] == _tree_hashes(rf7)
    return grid, trajectory, rf5, rf6, rf7, first, second


def test_rf8_contract_keeps_coupling_innovation_residual_and_risk_separate() -> None:
    contract = load_contract()

    assert contract["status"] == "implemented_for_rf9_risk_structure"
    assert contract["position_conditioned_coupling"]["causal_claim"] is False
    assert contract["same_axis_dynamics"]["attraction_or_repulsion_semantics_not_assigned"] is True
    assert contract["history_conditioned_innovation"]["new_drive_is_not_external_factor"] is True
    assert contract["unresolved_residual"]["history_innovation_must_remain_separate_from_transport_residual"] is True
    assert contract["acceptance"]["scientific_claim"] == "B_limited_axis_coupling_and_history_innovation"


def test_position_conditioned_pairwise_slope_recovers_synthetic_relation() -> None:
    source = np.zeros((4, 5), dtype=np.float64)
    source[:, 0] = np.asarray([0.0, 0.25, 0.5, 0.75])
    flow = np.zeros((4, 5), dtype=np.float64)
    flow[:, 1] = 1.0 + 2.0 * source[:, 0]

    result = compute_position_flow_coupling(
        source,
        flow,
        flow,
        flow,
        ridge=1e-8,
        variation_minimum=1e-8,
    )

    assert result["source_axis_identifiable"].tolist() == [1, 0, 0, 0, 0]
    assert result["slope_mean"][0, 1] == pytest.approx(2.0, rel=1e-6)
    assert result["slope_minimum"][0, 1] == pytest.approx(result["slope_maximum"][0, 1])
    assert result["fit_rmse"][0, 1] < 1e-7


def test_axis_flow_family_preserves_candidate_interval_and_deduplicates_saved_paths() -> None:
    descriptors = np.zeros((4, 31), dtype=np.float64)
    descriptors[0, :5] = [1, 0, 0, 0, 0]
    descriptors[1, :5] = [2, 0, 0, 0, 0]
    descriptors[2, :5] = [0, 1, 0, 0, 0]
    descriptors[3, :5] = [0, 2, 0, 0, 0]
    parent = {
        "rf5_identity": {"transition_count": 2},
        "offsets": np.asarray([0, 2, 4], dtype=np.int32),
        "candidate_axis_flow": descriptors[:, :5],
        "transition_times": np.asarray([1, 2], dtype=np.int32),
        "optimal_paths": [[0, 0], [1, 1], [1, 1], [0, 0]],
    }

    family, candidate_sets = compute_axis_flow_family(parent, 0.25)

    assert family["unique_candidate_count"].tolist() == [2, 2]
    assert family["axis_signed_flow_minimum"][0, 0] == 1.0
    assert family["axis_signed_flow_maximum"][0, 0] == 2.0
    assert family["axis_signed_flow_ambiguity_width"][0, 0] == 1.0
    assert family["axis_coordinate_displacement_mean"][1, 1] == pytest.approx(0.375)
    assert candidate_sets[0].shape == (2, 5)


def test_same_axis_amplification_attenuation_reversal_activation_and_cessation() -> None:
    current = np.asarray([[1.0, 1.0, 1.0, 0.0, 1.0]])
    following = np.asarray([[2.0, 0.5, -1.0, 1.0, 0.0]])

    feedback, dynamics = compute_lag_feedback(
        [current, following],
        tolerance=1e-9,
        magnitude_tolerance=1e-9,
    )
    row = dynamics["lags"][0]

    assert row["same_direction_amplification_candidate"] == [True, False, False, False, False]
    assert row["same_direction_attenuation_candidate"] == [False, True, False, False, False]
    assert row["direction_reversal_candidate"] == [False, False, True, False, False]
    assert row["axis_activation_candidate"] == [False, False, False, True, False]
    assert row["axis_cessation_candidate"] == [False, False, False, False, True]
    assert feedback["candidate_pair_count"].tolist() == [1]


def test_history_conditioned_innovation_detects_surprise_axis_without_external_claim() -> None:
    source = np.zeros((4, 5), dtype=np.float64)
    flow = np.asarray([
        [1.0, 0.0, 0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0, 0.0, 0.0],
        [1.0, 0.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0, 0.0],
    ])

    arrays, labels = compute_history_innovation(source, flow, flow, flow, load_contract()["history_conditioned_innovation"])

    assert arrays["baseline_available"].tolist() == [0, 1, 1, 1]
    assert arrays["history_conditioned_new_drive_candidate"][3, :2].tolist() == [1, 1]
    assert arrays["normalized_innovation_score"][3, 0] > 2.0
    assert arrays["normalized_innovation_score"][3, 1] > 2.0
    assert labels["new_drive_is_not_external_factor"] is True
    assert labels["new_drive_is_not_causal_explanation"] is True


def test_rf8_end_to_end_detects_axis_switch_and_keeps_transport_residual_separate(
    rf8_fixture: tuple[Path, Path, Path, Path, Path, Path, Path],
) -> None:
    _, _, _, _, _, artifact, _ = rf8_fixture
    with np.load(artifact / "axis_flow_family.npz", allow_pickle=False) as loaded:
        flow_mean = loaded["axis_signed_flow_mean"]
        candidate_count = loaded["unique_candidate_count"]
    with np.load(artifact / "history_conditioned_innovation.npz", allow_pickle=False) as loaded:
        innovation = loaded["innovation_axis_flow"]
        labels = loaded["history_conditioned_new_drive_candidate"]
    with np.load(artifact / "unresolved_residual_ledger.npz", allow_pickle=False) as loaded:
        residual_l1 = loaded["residual_l1_maximum"]

    assert np.array_equal(candidate_count, np.ones(4, dtype=np.int32))
    assert np.array_equal(flow_mean[:3, 0], np.ones(3))
    assert flow_mean[3, 0] == 0.0 and flow_mean[3, 1] == 1.0
    assert innovation[3, 0] < 0.0 and innovation[3, 1] > 0.0
    assert labels[3, :2].tolist() == [1, 1]
    assert np.max(residual_l1) < 1e-9
    assert (artifact / "history_conditioned_innovation.npz").is_file()
    assert (artifact / "unresolved_residual_ledger.npz").is_file()


def test_rf8_artifact_is_deterministic_and_valid(
    rf8_fixture: tuple[Path, Path, Path, Path, Path, Path, Path],
) -> None:
    grid, trajectory, rf5, rf6, rf7, first, second = rf8_fixture

    assert _tree_hashes(first) == _tree_hashes(second)
    validation = validate_axis_coupling_innovation(first, trajectory, grid, rf5, rf6, rf7)
    assert validation["rf8_axis_coupling_innovation_gate"] == "passed"
    assert validation["candidate_deduplication_gate"] is True
    assert validation["innovation_residual_separation_gate"] is True
    assert validation["causal_cutoff_gate"] is True
    assert validation["external_factor_claim"] is False
    assert validation["risk_prediction_performed"] is False


def test_future_suffix_does_not_change_rf8_prefix_artifact(tmp_path: Path) -> None:
    prefix = [
        _point((0, 2, 2, 2, 2)),
        _point((1, 2, 2, 2, 2)),
        _point((2, 2, 2, 2, 2)),
        _point((3, 2, 2, 2, 2)),
        _point((3, 3, 2, 2, 2)),
    ]
    grid = build_grid_artifact(tmp_path / "grid")
    trajectory_a = _write_trajectory(
        tmp_path / "trajectory_a", prefix + [_point((4, 4, 4, 4, 4))], trajectory_id="traj_rf8_prefix"
    )
    trajectory_b = _write_trajectory(
        tmp_path / "trajectory_b", prefix + [_point((0, 0, 0, 0, 0))], trajectory_id="traj_rf8_prefix"
    )

    def chain(label: str, trajectory: Path) -> tuple[Path, Path, Path, Path]:
        rf5 = build_temporal_relation_field(trajectory, grid, tmp_path / f"rf5_{label}", start_t=0, to_t=4)
        rf6 = build_hodge_decomposition(rf5, grid, tmp_path / f"rf6_{label}")
        rf7 = build_shape_dynamics(trajectory, rf5, rf6, grid, tmp_path / f"rf7_{label}")
        rf8 = build_axis_coupling_innovation(
            trajectory, grid, rf5, rf6, rf7, tmp_path / f"rf8_{label}"
        )
        return rf5, rf6, rf7, rf8

    chain_a = chain("a", trajectory_a)
    chain_b = chain("b", trajectory_b)
    for left, right in zip(chain_a, chain_b, strict=True):
        assert _tree_hashes(left) == _tree_hashes(right)


def test_manifest_tampering_and_overwrite_are_rejected(
    tmp_path: Path,
    rf8_fixture: tuple[Path, Path, Path, Path, Path, Path, Path],
) -> None:
    grid, trajectory, rf5, rf6, rf7, artifact, _ = rf8_fixture
    copied = tmp_path / "copied"
    shutil.copytree(artifact, copied)
    summary = copied / "summary.json"
    summary.write_text(summary.read_text(encoding="utf-8") + " ", encoding="utf-8")

    with pytest.raises(RelationFieldAxisCouplingError, match="manifest"):
        validate_axis_coupling_innovation(copied, trajectory, grid, rf5, rf6, rf7)
    with pytest.raises(RelationFieldAxisCouplingError, match="already exists"):
        build_axis_coupling_innovation(trajectory, grid, rf5, rf6, rf7, artifact)
