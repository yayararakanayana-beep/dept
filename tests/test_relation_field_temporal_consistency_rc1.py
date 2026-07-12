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

from relation_field_grid_rc1 import build_grid_artifact  # noqa: E402
from relation_field_single_transition_rc1 import (  # noqa: E402
    GENESIS_HASH,
    _compute_gt_hash,
    _compute_history_chain_hash,
)
from relation_field_temporal_consistency_rc1 import (  # noqa: E402
    RelationFieldTemporalError,
    build_temporal_relation_field,
    infer_temporal_paths,
    load_contract,
    validate_temporal_relation_field,
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


def _point_mass(cell_id: int) -> np.ndarray:
    mass = np.zeros(3125, dtype=np.float64)
    mass[cell_id] = 1.0
    return mass.reshape((5, 5, 5, 5, 5))


def _write_trajectory(
    root: Path,
    cell_ids: list[int],
    *,
    trajectory_id: str = "traj_rf5_test",
) -> Path:
    root.mkdir(parents=True)
    frames = [_point_mass(cell_id) for cell_id in cell_ids]
    np.save(root / "gt_mass.npy", np.stack(frames), allow_pickle=False)
    rows: list[dict[str, object]] = []
    previous_gt_hash = ""
    history_chain_hash = GENESIS_HASH
    for t, frame in enumerate(frames):
        source_state_hash = hashlib.sha256(f"rf5-source-{t}-{cell_ids[t]}".encode()).hexdigest()
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
def temporal_artifacts(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path, Path, Path, Path]:
    root = tmp_path_factory.mktemp("rf5-temporal")
    grid = build_grid_artifact(root / "grid")
    trajectory_a = _write_trajectory(root / "trajectory_a", [0, 6, 12, 18])
    trajectory_b = _write_trajectory(root / "trajectory_b", [0, 6, 12, 100])
    source_a_before = _tree_hashes(trajectory_a)
    source_b_before = _tree_hashes(trajectory_b)
    artifact_a = build_temporal_relation_field(
        trajectory_a,
        grid,
        root / "artifact_a",
        start_t=0,
        to_t=2,
    )
    artifact_b = build_temporal_relation_field(
        trajectory_b,
        grid,
        root / "artifact_b",
        start_t=0,
        to_t=2,
    )
    assert source_a_before == _tree_hashes(trajectory_a)
    assert source_b_before == _tree_hashes(trajectory_b)
    return grid, trajectory_a, trajectory_b, artifact_a, artifact_b


def test_rf5_contract_preserves_candidate_families_and_causal_boundary() -> None:
    contract = load_contract()

    assert contract["status"] == "implemented_for_rf6_decomposition"
    assert contract["input"]["minimum_transition_count"] == 2
    assert contract["input"]["future_suffix_read_forbidden"] is True
    assert contract["candidate_generation"]["candidate_search_is_exhaustive"] is False
    assert contract["translation_invariant_descriptor"]["dimension"] == 31
    assert contract["temporal_path_inference"]["primary_excess_weight"] == 1.0
    assert contract["common_structure"]["ambiguity_must_be_preserved"] is True
    assert "select_one_candidate_and_discard_equal_score_alternatives" in contract["prohibitions"]


def test_future_suffix_independence_and_deterministic_artifact(
    temporal_artifacts: tuple[Path, Path, Path, Path, Path],
) -> None:
    grid, _, _, artifact_a, artifact_b = temporal_artifacts

    assert _tree_hashes(artifact_a) == _tree_hashes(artifact_b)
    validation = validate_temporal_relation_field(artifact_a, grid)
    assert validation["rf5_temporal_consistency_gate"] == "passed"
    assert validation["causal_cutoff_respected"] is True
    assert validation["source_writeback_performed"] is False


def test_ambiguous_square_transitions_preserve_two_temporally_consistent_families(
    temporal_artifacts: tuple[Path, Path, Path, Path, Path],
) -> None:
    _, _, _, artifact, _ = temporal_artifacts
    paths = json.loads((artifact / "temporal_paths.json").read_text(encoding="utf-8"))
    diagnostics = json.loads((artifact / "temporal_diagnostics.json").read_text(encoding="utf-8"))

    assert diagnostics["candidate_count_per_transition"] == [2, 2]
    assert paths["optimal_path_count"] == 2
    assert len(paths["optimal_paths"]) == 2
    assert paths["best_score"] <= paths["independent_baseline_score"] + 1e-12
    assert paths["path_search_exhaustive"] is True
    assert diagnostics["edge_common_fraction"] == pytest.approx([0.0, 0.0])


def test_translation_invariant_descriptors_match_for_translated_flow_patterns(
    temporal_artifacts: tuple[Path, Path, Path, Path, Path],
) -> None:
    _, _, _, artifact, _ = temporal_artifacts
    with np.load(artifact / "candidate_flows.npz", allow_pickle=False) as loaded:
        offsets = loaded["candidate_offsets"]
        descriptors = loaded["candidate_descriptor"]

    first = descriptors[int(offsets[0]):int(offsets[1])]
    second = descriptors[int(offsets[1]):int(offsets[2])]
    first_set = sorted(tuple(np.round(row, 12)) for row in first)
    second_set = sorted(tuple(np.round(row, 12)) for row in second)

    assert first_set == second_set
    assert all(tuple(row[:5]) == (0.0, 0.0, 0.0, 1.0, 1.0) for row in first)


def test_common_axis_structure_survives_edge_path_ambiguity(
    temporal_artifacts: tuple[Path, Path, Path, Path, Path],
) -> None:
    _, _, _, artifact, _ = temporal_artifacts
    with np.load(artifact / "common_structure.npz", allow_pickle=False) as loaded:
        common_flow = loaded["common_net_flow"]
        union_mask = loaded["union_edge_mask"]
        axis_min = loaded["axis_flow_min"]
        axis_max = loaded["axis_flow_max"]
        axis_mean = loaded["axis_flow_mean"]

    assert np.count_nonzero(common_flow) == 0
    assert np.count_nonzero(union_mask) == 8
    expected = np.asarray([[0.0, 0.0, 0.0, 1.0, 1.0]] * 2)
    assert np.array_equal(axis_min, expected)
    assert np.array_equal(axis_max, expected)
    assert np.array_equal(axis_mean, expected)


def test_true_axis_direction_reversal_is_not_erased(tmp_path: Path) -> None:
    grid = build_grid_artifact(tmp_path / "grid")
    trajectory = _write_trajectory(tmp_path / "trajectory", [0, 6, 0])
    artifact = build_temporal_relation_field(
        trajectory,
        grid,
        tmp_path / "artifact",
        start_t=0,
        to_t=2,
    )

    with np.load(artifact / "representative_flow.npz", allow_pickle=False) as loaded:
        axis_flow = loaded["axis_signed_flow"]
    diagnostics = json.loads((artifact / "temporal_diagnostics.json").read_text(encoding="utf-8"))

    assert tuple(axis_flow[0]) == (0.0, 0.0, 0.0, 1.0, 1.0)
    assert tuple(axis_flow[1]) == (0.0, 0.0, 0.0, -1.0, -1.0)
    assert diagnostics["axis_direction_reversal"][1][3:] == [1, 1]
    assert diagnostics["field_change_candidate"][1] is True


def test_history_order_changes_temporal_score() -> None:
    contract = load_contract()
    zero_flow = np.zeros(1, dtype=np.float64)
    descriptor_a = np.zeros(31, dtype=np.float64)
    descriptor_b = np.zeros(31, dtype=np.float64)
    descriptor_b[0] = 1.0

    def candidate(descriptor: np.ndarray) -> dict[str, object]:
        return {
            "descriptor": descriptor,
            "net_flow": zero_flow,
            "primary_excess": 0.0,
        }

    ordered = infer_temporal_paths(
        [[candidate(descriptor_a)], [candidate(descriptor_a)], [candidate(descriptor_b)]],
        contract,
    )
    scrambled = infer_temporal_paths(
        [[candidate(descriptor_a)], [candidate(descriptor_b)], [candidate(descriptor_a)]],
        contract,
    )

    assert ordered["best_score"] == pytest.approx(1.0)
    assert scrambled["best_score"] == pytest.approx(2.0)


def test_manifest_tampering_and_overwrite_are_rejected(
    tmp_path: Path,
    temporal_artifacts: tuple[Path, Path, Path, Path, Path],
) -> None:
    grid, trajectory, _, artifact, _ = temporal_artifacts
    copied = tmp_path / "copied"
    shutil.copytree(artifact, copied)
    summary = copied / "summary.json"
    summary.write_text(summary.read_text(encoding="utf-8") + " ", encoding="utf-8")

    with pytest.raises(RelationFieldTemporalError, match="manifest"):
        validate_temporal_relation_field(copied, grid)
    with pytest.raises(RelationFieldTemporalError, match="already exists"):
        build_temporal_relation_field(
            trajectory,
            grid,
            artifact,
            start_t=0,
            to_t=2,
        )


def test_short_or_noncontinuous_history_is_rejected(tmp_path: Path) -> None:
    grid = build_grid_artifact(tmp_path / "grid")
    short = _write_trajectory(tmp_path / "short", [0, 6])
    with pytest.raises(RelationFieldTemporalError, match="too short"):
        build_temporal_relation_field(short, grid, tmp_path / "short_output", start_t=0, to_t=1)

    broken = _write_trajectory(tmp_path / "broken", [0, 6, 12])
    rows = list(csv.DictReader((broken / "history_ledger.csv").open("r", encoding="utf-8", newline="")))
    rows[2]["continuity_status"] = "gap"
    with (broken / "history_ledger.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEDGER_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    with pytest.raises(RelationFieldTemporalError, match="continuous"):
        build_temporal_relation_field(broken, grid, tmp_path / "broken_output", start_t=0, to_t=2)
