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

from relation_field_grid_rc1 import build_grid_artifact  # noqa: E402
from relation_field_single_transition_rc1 import (  # noqa: E402
    GENESIS_HASH,
    RelationFieldTransitionError,
    _compute_gt_hash,
    _compute_history_chain_hash,
    build_transition_field,
    load_contract,
    validate_transition_artifact,
)

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


def _hex_hash(index: int) -> str:
    return "0123456789abcdef"[index % 16] * 64


def _write_trajectory(
    root: Path,
    frames: list[np.ndarray],
    *,
    statuses: list[str] | None = None,
    trajectory_id: str = "traj_test",
) -> Path:
    root.mkdir(parents=True)
    np.save(root / "gt_mass.npy", np.stack(frames).astype(np.float64), allow_pickle=False)
    active_statuses = statuses or ["initial"] + ["continuous"] * (len(frames) - 1)
    rows: list[dict[str, object]] = []
    previous_gt_hash = ""
    chain_hash = GENESIS_HASH
    for t, status in enumerate(active_statuses):
        source_state_hash = _hex_hash(t)
        gt_hash = _compute_gt_hash(
            trajectory_id=trajectory_id,
            t=t,
            distribution=frames[t],
            source_state_hash=source_state_hash,
        )
        chain_hash = _compute_history_chain_hash(chain_hash, gt_hash, t)
        rows.append(
            {
                "trajectory_id": trajectory_id,
                "source_trajectory_id": trajectory_id,
                "t": t,
                "phase": "pre_transition",
                "gt_row_index": t,
                "gt_hash": gt_hash,
                "previous_gt_hash": previous_gt_hash,
                "history_chain_hash": chain_hash,
                "delta_t": 0 if t == 0 else 1,
                "continuity_status": status,
                "admissible_for_research": str(status in {"initial", "continuous"}),
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


def _point_mix(first: int, second: int, first_weight: float) -> np.ndarray:
    mass = np.zeros(3125, dtype=np.float64)
    mass[first] = first_weight
    mass[second] = 1.0 - first_weight
    return mass.reshape((5, 5, 5, 5, 5))


def _field_root(output: Path) -> Path:
    return output / "trajectories" / "traj_test" / "fields" / "t_000001"


def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


@pytest.fixture(scope="module")
def grid_artifact(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return build_grid_artifact(tmp_path_factory.mktemp("rf3-grid") / "grid")


def test_contract_fixes_representative_minimum_cost_and_residual_boundaries() -> None:
    contract = load_contract()

    assert contract["solver"]["residual_penalty"] > contract["solver"]["maximum_grid_path_cost"]
    assert contract["solver"]["representative_solution_only"] is True
    assert contract["solver"]["uniqueness_claim"] is False
    assert contract["input"]["read_after_to_t_forbidden"] is True
    assert contract["residual"]["must_not_be_labeled_external"] is True
    assert contract["rf3_acceptance"]["alternative_solution_robustness"] == "deferred_to_rf4"


def test_forward_adjacent_transition_is_reconstructed_by_one_directed_edge(
    tmp_path: Path,
    grid_artifact: Path,
) -> None:
    trajectory = _write_trajectory(
        tmp_path / "trajectory",
        [_point_mix(0, 1, 0.6), _point_mix(0, 1, 0.4)],
    )
    before = _tree_hashes(trajectory)
    output = build_transition_field(trajectory, grid_artifact, tmp_path / "output", from_t=0, to_t=1)
    after = _tree_hashes(trajectory)

    assert before == after
    validation = validate_transition_artifact(output, grid_artifact)
    assert validation["rf3_single_transition_gate"] == "passed"
    assert validation["active_directed_edge_count"] == 1
    field = _field_root(output)
    with (field / "local_flow_edges.csv").open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["source_cell_id"] == "0"
    assert rows[0]["target_cell_id"] == "1"
    assert rows[0]["direction"] == "1"
    assert float(rows[0]["flow_amount"]) == pytest.approx(0.2)
    assert rows[0]["confidence"] == ""
    assert rows[0]["confidence_status"] == "not_calibrated_rf3"
    reconstruction = json.loads((field / "reconstruction.json").read_text(encoding="utf-8"))
    assert reconstruction["coordinate_transport_cost"] == pytest.approx(0.05)
    assert reconstruction["reconstruction_max_abs_error"] < 1e-12
    assert reconstruction["residual_l1"] < 1e-12


def test_reverse_and_two_step_flows_use_local_edges(
    tmp_path: Path,
    grid_artifact: Path,
) -> None:
    reverse_trajectory = _write_trajectory(
        tmp_path / "reverse_trajectory",
        [_point_mix(0, 1, 0.4), _point_mix(0, 1, 0.6)],
    )
    reverse_output = build_transition_field(
        reverse_trajectory,
        grid_artifact,
        tmp_path / "reverse_output",
        from_t=0,
        to_t=1,
    )
    with (_field_root(reverse_output) / "local_flow_edges.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        reverse_rows = list(csv.DictReader(handle))
    assert len(reverse_rows) == 1
    assert reverse_rows[0]["source_cell_id"] == "1"
    assert reverse_rows[0]["target_cell_id"] == "0"
    assert reverse_rows[0]["direction"] == "-1"

    first = np.zeros(3125, dtype=np.float64)
    second = np.zeros(3125, dtype=np.float64)
    first[0], first[2] = 0.8, 0.2
    second[0], second[2] = 0.7, 0.3
    path_trajectory = _write_trajectory(
        tmp_path / "path_trajectory",
        [first.reshape((5, 5, 5, 5, 5)), second.reshape((5, 5, 5, 5, 5))],
    )
    path_output = build_transition_field(
        path_trajectory,
        grid_artifact,
        tmp_path / "path_output",
        from_t=0,
        to_t=1,
    )
    with (_field_root(path_output) / "local_flow_edges.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        path_rows = list(csv.DictReader(handle))
    assert len(path_rows) == 2
    assert sum(float(row["flow_amount"]) for row in path_rows) == pytest.approx(0.2)
    reconstruction = json.loads(
        (_field_root(path_output) / "reconstruction.json").read_text(encoding="utf-8")
    )
    assert reconstruction["coordinate_transport_cost"] == pytest.approx(0.05)


def test_zero_transition_is_deterministic_and_keeps_uncertainty_explicit(
    tmp_path: Path,
    grid_artifact: Path,
) -> None:
    frame = _point_mix(0, 1, 0.5)
    trajectory = _write_trajectory(tmp_path / "trajectory", [frame, frame.copy()])
    first = build_transition_field(trajectory, grid_artifact, tmp_path / "first", from_t=0, to_t=1)
    second = build_transition_field(trajectory, grid_artifact, tmp_path / "second", from_t=0, to_t=1)

    assert _tree_hashes(first) == _tree_hashes(second)
    validation = validate_transition_artifact(first, grid_artifact)
    assert validation["active_directed_edge_count"] == 0
    uncertainty = json.loads((_field_root(first) / "uncertainty.json").read_text(encoding="utf-8"))
    assert uncertainty["identifiability"]["uniqueness_claim"] is False
    assert uncertainty["identifiability"]["alternative_solution_audit"] == "deferred_to_rf4"
    assert uncertainty["temporal_stability"]["status"] == "not_evaluated_in_rf3"


def test_future_frame_and_future_ledger_suffix_do_not_change_field(
    tmp_path: Path,
    grid_artifact: Path,
) -> None:
    first = _point_mix(0, 1, 0.6)
    second = _point_mix(0, 1, 0.4)
    trajectory_a = _write_trajectory(
        tmp_path / "trajectory_a",
        [first, second, _point_mix(20, 21, 0.9)],
    )
    trajectory_b = _write_trajectory(
        tmp_path / "trajectory_b",
        [first, second, _point_mix(100, 101, 0.1)],
    )
    output_a = build_transition_field(
        trajectory_a, grid_artifact, tmp_path / "output_a", from_t=0, to_t=1
    )
    output_b = build_transition_field(
        trajectory_b, grid_artifact, tmp_path / "output_b", from_t=0, to_t=1
    )

    assert _tree_hashes(output_a) == _tree_hashes(output_b)
    provenance = json.loads(
        (output_a / "trajectories" / "traj_test" / "provenance.json").read_text(encoding="utf-8")
    )
    assert provenance["max_t_read"] == 1
    assert provenance["history_prefix_rows_read"] == 2
    assert provenance["observed_logs_read"] is False
    assert provenance["truth_files_read"] is False


def test_noncontinuous_or_hash_invalid_transition_is_rejected(
    tmp_path: Path,
    grid_artifact: Path,
) -> None:
    broken_continuity = _write_trajectory(
        tmp_path / "broken_continuity",
        [_point_mix(0, 1, 0.6), _point_mix(0, 1, 0.4)],
        statuses=["initial", "gap"],
    )
    with pytest.raises(RelationFieldTransitionError, match="continuous"):
        build_transition_field(
            broken_continuity,
            grid_artifact,
            tmp_path / "continuity_output",
            from_t=0,
            to_t=1,
        )

    broken_hash = _write_trajectory(
        tmp_path / "broken_hash",
        [_point_mix(0, 1, 0.6), _point_mix(0, 1, 0.4)],
    )
    mass = np.load(broken_hash / "gt_mass.npy", allow_pickle=False)
    mass[1].flat[0] -= 0.01
    mass[1].flat[1] += 0.01
    np.save(broken_hash / "gt_mass.npy", mass, allow_pickle=False)
    with pytest.raises(RelationFieldTransitionError, match="selected G_t hash mismatch"):
        build_transition_field(
            broken_hash,
            grid_artifact,
            tmp_path / "hash_output",
            from_t=0,
            to_t=1,
        )


def test_manifest_tampering_and_overwrite_are_rejected(
    tmp_path: Path,
    grid_artifact: Path,
) -> None:
    trajectory = _write_trajectory(
        tmp_path / "trajectory",
        [_point_mix(0, 1, 0.6), _point_mix(0, 1, 0.4)],
    )
    output = build_transition_field(trajectory, grid_artifact, tmp_path / "output", from_t=0, to_t=1)
    with pytest.raises(RelationFieldTransitionError, match="already exists"):
        build_transition_field(trajectory, grid_artifact, output, from_t=0, to_t=1)

    flow_csv = _field_root(output) / "local_flow_edges.csv"
    flow_csv.write_text(flow_csv.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
    with pytest.raises(RelationFieldTransitionError, match="manifest"):
        validate_transition_artifact(output, grid_artifact)
