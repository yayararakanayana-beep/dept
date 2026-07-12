from __future__ import annotations

import csv
import hashlib
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pytest
from scipy.sparse import csr_matrix

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from relation_field_grid_rc1 import build_grid_artifact  # noqa: E402
from relation_field_hodge_decomposition_rc1 import (  # noqa: E402
    FACE_COUNT,
    RelationFieldHodgeError,
    _load_grid_with_indices,
    build_hodge_decomposition,
    decompose_edge_flow,
    generate_face_complex,
    load_contract,
    validate_hodge_artifact,
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


def _point_mass(cell_id: int) -> np.ndarray:
    mass = np.zeros(3125, dtype=np.float64)
    mass[cell_id] = 1.0
    return mass.reshape((5, 5, 5, 5, 5))


def _write_trajectory(root: Path, cell_ids: list[int]) -> Path:
    root.mkdir(parents=True)
    trajectory_id = "traj_rf6_test"
    frames = [_point_mass(cell_id) for cell_id in cell_ids]
    np.save(root / "gt_mass.npy", np.stack(frames), allow_pickle=False)
    rows: list[dict[str, object]] = []
    previous_gt_hash = ""
    history_chain_hash = GENESIS_HASH
    for t, frame in enumerate(frames):
        source_state_hash = hashlib.sha256(f"rf6-source-{t}-{cell_ids[t]}".encode()).hexdigest()
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


@pytest.fixture(scope="module")
def rf6_fixture(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path, Path, Path, Path]:
    root = tmp_path_factory.mktemp("rf6-hodge")
    grid = build_grid_artifact(root / "grid")
    trajectory = _write_trajectory(root / "trajectory", [0, 6, 12])
    rf5 = build_temporal_relation_field(
        trajectory,
        grid,
        root / "rf5",
        start_t=0,
        to_t=2,
    )
    source_hashes = _tree_hashes(rf5)
    first = build_hodge_decomposition(rf5, grid, root / "rf6_a")
    second = build_hodge_decomposition(rf5, grid, root / "rf6_b")
    assert source_hashes == _tree_hashes(rf5)
    return grid, trajectory, rf5, first, second


def test_rf6_contract_fixes_contractible_hodge_boundary() -> None:
    contract = load_contract()

    assert contract["status"] == "implemented_for_rf7_shape_dynamics"
    assert contract["cubical_complex"]["face_count"] == 20000
    assert contract["cubical_complex"]["expected_first_betti_number"] == 0
    assert contract["decomposition"]["harmonic_component"] == "zero_under_fixed_contractible_full_complex"
    assert contract["candidate_family"]["representative_path_must_not_replace_family"] is True
    assert contract["acceptance"]["scientific_claim"] == (
        "B_limited_hodge_decomposition_on_fixed_contractible_grid"
    )


def test_face_complex_has_twenty_thousand_oriented_squares_and_boundary_squared_zero(tmp_path: Path) -> None:
    grid_path = build_grid_artifact(tmp_path / "grid")
    grid = _load_grid_with_indices(grid_path)
    topology = generate_face_complex(grid)

    assert topology["face_base_cell"].shape == (FACE_COUNT,)
    assert topology["face_edge_ids"].shape == (FACE_COUNT, 4)
    assert topology["face_edge_signs"].shape == (FACE_COUNT, 4)
    assert np.array_equal(topology["face_edge_signs"][0], np.asarray([1, 1, -1, -1]))
    assert topology["boundary_of_boundary_max_abs"] == 0.0


def test_pure_gradient_is_recovered_without_circulation(tmp_path: Path) -> None:
    grid_path = build_grid_artifact(tmp_path / "grid")
    grid = _load_grid_with_indices(grid_path)
    topology = generate_face_complex(grid)
    boundary_1 = csr_matrix(grid["incidence"], dtype=np.float64)
    boundary_2 = csr_matrix(topology["boundary_2"], dtype=np.float64)
    potential = np.asarray(grid["node_values"][:, 0], dtype=np.float64)
    flow = np.asarray(boundary_1.transpose() @ potential, dtype=np.float64)

    result = decompose_edge_flow(flow, boundary_1, boundary_2, load_contract())

    assert np.max(np.abs(result["gradient_flow"] - flow)) < 1e-9
    assert np.max(np.abs(result["circulation_flow"])) < 1e-9
    assert result["metrics"]["gradient_face_circulation_max_abs"] < 1e-9
    assert result["metrics"]["harmonic_max_abs"] == 0.0


def test_elementary_face_cycle_is_recovered_as_circulation(tmp_path: Path) -> None:
    grid_path = build_grid_artifact(tmp_path / "grid")
    grid = _load_grid_with_indices(grid_path)
    topology = generate_face_complex(grid)
    boundary_1 = csr_matrix(grid["incidence"], dtype=np.float64)
    boundary_2 = csr_matrix(topology["boundary_2"], dtype=np.float64)
    flow = np.asarray(boundary_2[:, 0].toarray(), dtype=np.float64).reshape(-1)

    result = decompose_edge_flow(flow, boundary_1, boundary_2, load_contract())

    assert np.max(np.abs(result["gradient_flow"])) < 1e-9
    assert np.max(np.abs(result["circulation_flow"] - flow)) < 1e-9
    assert result["metrics"]["circulation_divergence_max_abs"] < 1e-9
    assert result["metrics"]["face_circulation_max_abs"] > 0.0


def test_rf6_artifact_is_deterministic_and_valid(rf6_fixture: tuple[Path, Path, Path, Path, Path]) -> None:
    grid, _, rf5, first, second = rf6_fixture

    assert _tree_hashes(first) == _tree_hashes(second)
    validation = validate_hodge_artifact(first, rf5, grid)
    assert validation["rf6_hodge_decomposition_gate"] == "passed"
    assert validation["topology_gate"] is True
    assert validation["harmonic_gate"] is True
    assert validation["parent_writeback_performed"] is False


def test_same_delta_candidate_paths_share_gradient_and_differ_in_circulation(
    rf6_fixture: tuple[Path, Path, Path, Path, Path],
) -> None:
    _, _, _, artifact, _ = rf6_fixture
    with np.load(artifact / "candidate_components.npz", allow_pickle=False) as loaded:
        offsets = loaded["candidate_offsets"]
        gradient = loaded["gradient_flow"]
        circulation = loaded["circulation_flow"]
        harmonic = loaded["harmonic_flow"]
        residual = loaded["numerical_residual_flow"]
    first = slice(int(offsets[0]), int(offsets[1]))

    assert int(offsets[1] - offsets[0]) == 2
    assert np.max(np.ptp(gradient[first], axis=0)) < 1e-9
    assert np.max(np.ptp(circulation[first], axis=0)) > 1e-6
    assert np.max(np.abs(harmonic)) == 0.0
    assert np.max(np.abs(residual)) <= 1e-12


def test_path_family_outputs_keep_gradient_commonality_and_circulation_width(
    rf6_fixture: tuple[Path, Path, Path, Path, Path],
) -> None:
    _, _, _, artifact, _ = rf6_fixture
    diagnostics = json.loads((artifact / "decomposition_diagnostics.json").read_text(encoding="utf-8"))
    with np.load(artifact / "path_family_components.npz", allow_pickle=False) as loaded:
        gradient_width = loaded["gradient_max"] - loaded["gradient_min"]
        circulation_width = loaded["circulation_max"] - loaded["circulation_min"]

    assert diagnostics["ambiguous_transition_indices"] == [0, 1]
    assert np.max(np.abs(gradient_width)) < 1e-9
    assert np.max(np.abs(circulation_width)) > 1e-6
    assert diagnostics["gates"]["ambiguous_gradient_commonality_gate"] is True
    assert diagnostics["gates"]["ambiguous_circulation_separation_gate"] is True


def test_representative_components_reconstruct_input_and_report_local_face_circulation(
    rf6_fixture: tuple[Path, Path, Path, Path, Path],
) -> None:
    _, _, _, artifact, _ = rf6_fixture
    with np.load(artifact / "representative_components.npz", allow_pickle=False) as loaded:
        input_flow = loaded["input_flow"]
        reconstruction = (
            loaded["gradient_flow"]
            + loaded["circulation_flow"]
            + loaded["harmonic_flow"]
            + loaded["numerical_residual_flow"]
        )
        face_circulation = loaded["face_circulation"]

    assert np.max(np.abs(input_flow - reconstruction)) < 1e-9
    assert face_circulation.shape == (2, FACE_COUNT)
    assert np.max(np.abs(face_circulation)) > 0.0


def test_manifest_tampering_and_overwrite_are_rejected(
    tmp_path: Path,
    rf6_fixture: tuple[Path, Path, Path, Path, Path],
) -> None:
    grid, _, rf5, artifact, _ = rf6_fixture
    copied = tmp_path / "copied"
    shutil.copytree(artifact, copied)
    summary = copied / "summary.json"
    summary.write_text(summary.read_text(encoding="utf-8") + " ", encoding="utf-8")

    with pytest.raises(RelationFieldHodgeError, match="manifest"):
        validate_hodge_artifact(copied, rf5, grid)
    with pytest.raises(RelationFieldHodgeError, match="already exists"):
        build_hodge_decomposition(rf5, grid, artifact)
