from __future__ import annotations

import csv
import hashlib
import shutil
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from relation_field_axis_coupling_innovation_rc1 import build_axis_coupling_innovation  # noqa: E402
from relation_field_grid_rc1 import build_grid_artifact, cell_id_from_indices  # noqa: E402
from relation_field_hodge_decomposition_rc1 import build_hodge_decomposition  # noqa: E402
from relation_field_risk_structure_rc1 import (  # noqa: E402
    RelationFieldRiskStructureError,
    build_risk_structure,
    compute_risk_structure,
    load_contract,
    validate_risk_structure,
)
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


def _empty_axis_flags() -> dict[str, list[bool]]:
    return {
        "same_direction_amplification_candidate": [False] * 5,
        "same_direction_attenuation_candidate": [False] * 5,
        "direction_reversal_candidate": [False] * 5,
        "axis_activation_candidate": [False] * 5,
        "axis_cessation_candidate": [False] * 5,
    }


def _shape_row(**updates: bool) -> dict[str, bool | int]:
    row: dict[str, bool | int] = {
        "transition_index": 0,
        "translation_without_detected_shape_change": False,
        "expansion_candidate": False,
        "contraction_candidate": False,
        "dispersion_candidate": False,
        "concentration_candidate": False,
        "split_candidate": False,
        "merge_candidate": False,
        "fragmentation_candidate": False,
        "coalescence_candidate": False,
        "boundary_sticking_candidate": False,
    }
    row.update(updates)
    return row


def _channel_row(**updates: bool) -> dict[str, bool | int]:
    row: dict[str, bool | int] = {
        "transition_index": 0,
        "flow_channel_narrowing_candidate": False,
        "flow_channel_widening_candidate": False,
    }
    row.update(updates)
    return row


def _synthetic_parent() -> dict[str, object]:
    lags = [_empty_axis_flags() for _ in range(3)]
    lags[0]["same_direction_amplification_candidate"][0] = True
    lags[1]["same_direction_attenuation_candidate"][0] = True
    return {
        "transition_count": 4,
        "transition_times": np.asarray([1, 2, 3, 4], dtype=np.int32),
        "shape_rows": [
            _shape_row(transition_index=0),
            _shape_row(
                transition_index=1,
                contraction_candidate=True,
                concentration_candidate=True,
                boundary_sticking_candidate=True,
            ),
            _shape_row(
                transition_index=2,
                expansion_candidate=True,
                dispersion_candidate=True,
                fragmentation_candidate=True,
            ),
            _shape_row(transition_index=3),
        ],
        "channel_rows": [
            _channel_row(transition_index=0),
            _channel_row(transition_index=1, flow_channel_narrowing_candidate=True),
            _channel_row(transition_index=2, flow_channel_widening_candidate=True),
            _channel_row(transition_index=3),
        ],
        "same_axis_lags": lags,
        "transition_arrays": {
            "total_variation_distance": np.asarray([0.5, 0.5, 0.5, 0.5], dtype=np.float64),
        },
        "flow_arrays": {
            "gradient_energy_minimum": np.asarray([1.0, 2.0, 0.1, 0.2]),
            "gradient_energy_maximum": np.asarray([1.0, 2.2, 0.2, 0.3]),
            "circulation_energy_minimum": np.asarray([0.0, 0.1, 1.0, 0.2]),
            "circulation_energy_maximum": np.asarray([0.0, 0.2, 1.2, 0.3]),
        },
        "boundary_arrays": {
            "boundary_mass_persistence": np.asarray([0.8, 0.8, 0.1, 0.0]),
            "mass_weighted_inward_flow_mean": np.asarray([0.2, 0.0, 0.3, 0.3]),
        },
        "axis_family": {
            "axis_signed_flow_ambiguity_width": np.zeros((4, 5), dtype=np.float64),
            "unique_candidate_count": np.ones(4, dtype=np.int32),
        },
        "innovation": {
            "history_conditioned_new_drive_candidate": np.asarray(
                [
                    [0, 0, 0, 0, 0],
                    [0, 0, 0, 0, 0],
                    [0, 0, 0, 0, 0],
                    [0, 1, 0, 0, 0],
                ],
                dtype=np.uint8,
            ),
        },
        "residual": {
            "residual_l1_minimum": np.asarray([0.0, 0.0, 0.0, 0.8]),
            "residual_l1_mean": np.asarray([0.0, 0.0, 0.0, 0.9]),
        },
    }


def test_rf9_contract_keeps_candidates_parallel_and_bounded() -> None:
    contract = load_contract()

    assert contract["status"] == "implemented_for_rf10_predictive_validation"
    assert contract["aggregation"]["single_scalar_risk_score_forbidden"] is True
    assert contract["semantic_limits"]["true_irreversibility_claim"] is False
    assert contract["semantic_limits"]["future_risk_prediction_claim"] is False
    assert contract["risk_structure"]["gradient_or_circulation_dominance_is_modifier_not_risk"] is True
    assert contract["acceptance"]["scientific_claim"] == "B_limited_structural_risk_candidates_without_prediction"


def test_rf9_recovers_overconvergence_fixation_divergence_and_residual_dominance() -> None:
    result = compute_risk_structure(_synthetic_parent(), load_contract())
    rows = result["candidates"]["rows"]

    assert rows[0]["overconvergence_candidate"] is True
    assert rows[0]["fixation_candidate"] is True
    assert rows[0]["observed_return_suppression_candidate"] is True
    assert rows[0]["gradient_dominance_consensus"] is True

    assert rows[1]["divergence_candidate"] is True
    assert rows[1]["fixation_candidate"] is False
    assert rows[1]["circulation_dominance_consensus"] is True

    assert rows[2]["unresolved_residual_dominance_candidate"] is True
    assert rows[2]["new_drive_coincident_candidate"] is False
    assert rows[2]["innovation_axes"] == [1]
    assert all("risk_score" not in row for row in rows)


def test_return_counterevidence_blocks_fixation_without_erasing_overconvergence() -> None:
    parent = _synthetic_parent()
    parent["channel_rows"][1]["flow_channel_widening_candidate"] = True
    parent["same_axis_lags"][0]["direction_reversal_candidate"][1] = True

    result = compute_risk_structure(parent, load_contract())
    row = result["candidates"]["rows"][0]
    counter = result["counterevidence"]["rows"][0]

    assert row["overconvergence_candidate"] is True
    assert row["observed_return_suppression_candidate"] is False
    assert row["fixation_candidate"] is False
    assert "flow_channel_widening" in counter["fixation_counterevidence"]
    assert "direction_reversal" in counter["fixation_counterevidence"]


def _point(indices: tuple[int, int, int, int, int]) -> np.ndarray:
    flat = np.zeros(3125, dtype=np.float64)
    flat[cell_id_from_indices(indices)] = 1.0
    return flat.reshape((5, 5, 5, 5, 5))


def _write_trajectory(
    root: Path,
    frames: list[np.ndarray],
    *,
    trajectory_id: str,
) -> Path:
    root.mkdir(parents=True)
    np.save(root / "gt_mass.npy", np.stack(frames), allow_pickle=False)
    rows: list[dict[str, object]] = []
    previous_gt_hash = ""
    history_chain_hash = GENESIS_HASH
    for t, frame in enumerate(frames):
        frame_digest = hashlib.sha256(np.ascontiguousarray(frame).tobytes()).hexdigest()
        source_state_hash = hashlib.sha256(f"rf9-source-{t}-{frame_digest}".encode()).hexdigest()
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
def rf9_fixture(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path, Path, Path, Path, Path, Path, Path, Path]:
    root = tmp_path_factory.mktemp("rf9-risk-structure")
    prefix = [
        _point((0, 2, 2, 2, 2)),
        _point((1, 2, 2, 2, 2)),
        _point((2, 2, 2, 2, 2)),
        _point((3, 2, 2, 2, 2)),
        _point((3, 3, 2, 2, 2)),
    ]
    trajectory_a = _write_trajectory(
        root / "trajectory_a",
        prefix + [_point((4, 4, 4, 4, 4))],
        trajectory_id="traj_rf9_prefix",
    )
    trajectory_b = _write_trajectory(
        root / "trajectory_b",
        prefix + [_point((0, 0, 0, 0, 0))],
        trajectory_id="traj_rf9_prefix",
    )
    grid = build_grid_artifact(root / "grid")
    rf5 = build_temporal_relation_field(trajectory_a, grid, root / "rf5", start_t=0, to_t=4)
    rf6 = build_hodge_decomposition(rf5, grid, root / "rf6")
    rf7 = build_shape_dynamics(trajectory_a, rf5, rf6, grid, root / "rf7")
    rf8 = build_axis_coupling_innovation(trajectory_a, grid, rf5, rf6, rf7, root / "rf8")
    source_hashes = {
        "trajectory_a": _tree_hashes(trajectory_a),
        "trajectory_b": _tree_hashes(trajectory_b),
        "rf5": _tree_hashes(rf5),
        "rf6": _tree_hashes(rf6),
        "rf7": _tree_hashes(rf7),
        "rf8": _tree_hashes(rf8),
    }
    first = build_risk_structure(trajectory_a, grid, rf5, rf6, rf7, rf8, root / "rf9_a")
    second = build_risk_structure(trajectory_b, grid, rf5, rf6, rf7, rf8, root / "rf9_b")
    assert source_hashes["trajectory_a"] == _tree_hashes(trajectory_a)
    assert source_hashes["trajectory_b"] == _tree_hashes(trajectory_b)
    assert source_hashes["rf5"] == _tree_hashes(rf5)
    assert source_hashes["rf6"] == _tree_hashes(rf6)
    assert source_hashes["rf7"] == _tree_hashes(rf7)
    assert source_hashes["rf8"] == _tree_hashes(rf8)
    return grid, trajectory_a, trajectory_b, rf5, rf6, rf7, rf8, first, second


def test_rf9_end_to_end_keeps_new_drive_separate_from_structural_risk(
    rf9_fixture: tuple[Path, Path, Path, Path, Path, Path, Path, Path, Path],
) -> None:
    _, _, _, _, _, _, _, artifact, _ = rf9_fixture
    with np.load(artifact / "risk_structure_metrics.npz", allow_pickle=False) as loaded:
        new_drive = loaded["history_conditioned_new_drive_present"]
        coincident = loaded["new_drive_coincident_candidate"]
        overconvergence = loaded["overconvergence_candidate"]
        divergence = loaded["divergence_candidate"]

    assert new_drive.tolist() == [0, 0, 1]
    assert coincident.tolist() == [0, 0, 0]
    assert overconvergence.tolist() == [0, 0, 0]
    assert divergence.tolist() == [0, 0, 0]


def test_rf9_is_deterministic_future_suffix_independent_and_valid(
    rf9_fixture: tuple[Path, Path, Path, Path, Path, Path, Path, Path, Path],
) -> None:
    grid, trajectory_a, _, rf5, rf6, rf7, rf8, first, second = rf9_fixture

    assert _tree_hashes(first) == _tree_hashes(second)
    validation = validate_risk_structure(first, trajectory_a, grid, rf5, rf6, rf7, rf8)
    assert validation["rf9_risk_structure_gate"] == "passed"
    assert validation["transition_alignment_gate"] is True
    assert validation["risk_score_absence_gate"] is True
    assert validation["innovation_residual_separation_gate"] is True
    assert validation["future_risk_prediction_performed"] is False


def test_rf9_manifest_tampering_and_overwrite_are_rejected(
    tmp_path: Path,
    rf9_fixture: tuple[Path, Path, Path, Path, Path, Path, Path, Path, Path],
) -> None:
    grid, trajectory_a, _, rf5, rf6, rf7, rf8, artifact, _ = rf9_fixture
    copied = tmp_path / "copied"
    shutil.copytree(artifact, copied)
    summary = copied / "summary.json"
    summary.write_text(summary.read_text(encoding="utf-8") + " ", encoding="utf-8")

    with pytest.raises(RelationFieldRiskStructureError, match="manifest"):
        validate_risk_structure(copied, trajectory_a, grid, rf5, rf6, rf7, rf8)
    with pytest.raises(RelationFieldRiskStructureError, match="already exists"):
        build_risk_structure(trajectory_a, grid, rf5, rf6, rf7, rf8, artifact)
