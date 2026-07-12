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

from relation_field_axis_coupling_innovation_rc1 import build_axis_coupling_innovation  # noqa: E402
from relation_field_grid_rc1 import build_grid_artifact, cell_id_from_indices  # noqa: E402
from relation_field_hodge_decomposition_rc1 import build_hodge_decomposition  # noqa: E402
from relation_field_predictive_validation_rc1 import (  # noqa: E402
    RelationFieldPredictiveValidationError,
    build_predictive_validation,
    classification_metrics,
    compute_future_outcomes,
    load_contract,
    validate_predictive_validation,
)
from relation_field_risk_structure_rc1 import build_risk_structure  # noqa: E402
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


def _metrics(
    entropy: float,
    support: float,
    peak: float,
    variance: float,
    boundary: float = 0.0,
) -> dict[str, float]:
    return {
        "normalized_entropy": entropy,
        "effective_support": support,
        "peak_mass": peak,
        "total_variance": variance,
        "boundary_mass": boundary,
    }


def test_rf10_contract_freezes_final_row_and_accuracy_claim_gates() -> None:
    contract = load_contract()

    assert contract["status"] == "implemented_for_multitrajectory_validation"
    assert contract["input"]["only_final_RF9_row_is_prediction_sample"] is True
    assert contract["input"]["prediction_snapshot_must_be_frozen_before_future_suffix_read"] is True
    assert contract["future_outcomes"]["future_outcomes_are_operational_observation_labels_not_true_irreversibility"] is True
    assert contract["support_gates"]["minimum_test_cases_for_accuracy_claim"] == 30
    assert contract["acceptance"]["scientific_claim"] == "B_limited_leakage_safe_predictive_validation_harness"


def test_future_outcome_rules_recover_concentration_dispersion_and_recovery_failure() -> None:
    settings = load_contract()["future_outcomes"]
    anchor = _metrics(0.30, 10.0, 0.20, 0.08)
    concentrated = _metrics(0.20, 6.0, 0.40, 0.03)
    concentration = compute_future_outcomes([anchor, concentrated], 1, settings)

    assert concentration["future_concentration_outcome"] is True
    assert concentration["future_persistent_concentration_outcome"] is True
    assert concentration["future_dispersion_outcome"] is False
    assert concentration["future_recovery_failure_applicable"] is False

    dispersed = _metrics(0.42, 16.0, 0.10, 0.16)
    dispersion = compute_future_outcomes([anchor, dispersed], 1, settings)
    assert dispersion["future_dispersion_outcome"] is True
    assert dispersion["future_concentration_outcome"] is False

    event = _metrics(0.18, 5.0, 0.50, 0.02, 0.50)
    still_stuck = _metrics(0.19, 5.2, 0.48, 0.022, 0.48)
    failed = compute_future_outcomes([anchor, event, still_stuck], 2, settings)
    assert failed["future_recovery_failure_applicable"] is True
    assert failed["future_recovery_failure_outcome"] is True

    recovered = _metrics(0.30, 9.0, 0.28, 0.06, 0.15)
    success = compute_future_outcomes([anchor, event, recovered], 2, settings)
    assert success["future_recovery_failure_applicable"] is True
    assert success["future_recovery_failure_outcome"] is False
    assert success["recovery_signal_count"] >= 2


def test_classification_metrics_recovers_confusion_arithmetic_and_nulls() -> None:
    metrics = classification_metrics(
        [True, True, False, False],
        [True, False, True, False],
    )

    assert metrics["true_positive"] == 1
    assert metrics["false_positive"] == 1
    assert metrics["true_negative"] == 1
    assert metrics["false_negative"] == 1
    assert metrics["precision"] == pytest.approx(0.5)
    assert metrics["recall"] == pytest.approx(0.5)
    assert metrics["specificity"] == pytest.approx(0.5)
    assert metrics["accuracy"] == pytest.approx(0.5)
    assert metrics["balanced_accuracy"] == pytest.approx(0.5)
    assert metrics["f1"] == pytest.approx(0.5)
    assert metrics["matthews_correlation"] == pytest.approx(0.0)
    assert metrics["brier_score"] == pytest.approx(0.5)

    empty = classification_metrics([False], [False], [False])
    assert empty["sample_count"] == 0
    assert empty["precision"] is None
    assert empty["recall"] is None
    assert empty["accuracy"] is None


def _point(indices: tuple[int, int, int, int, int]) -> np.ndarray:
    flat = np.zeros(3125, dtype=np.float64)
    flat[cell_id_from_indices(indices)] = 1.0
    return flat.reshape((5, 5, 5, 5, 5))


def _mixture(items: list[tuple[tuple[int, int, int, int, int], float]]) -> np.ndarray:
    flat = np.zeros(3125, dtype=np.float64)
    for indices, mass in items:
        flat[cell_id_from_indices(indices)] += float(mass)
    assert np.isclose(np.sum(flat), 1.0)
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
        source_state_hash = hashlib.sha256(f"rf10-source-{t}-{frame_digest}".encode()).hexdigest()
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


def _write_case_manifest(
    path: Path,
    cases: list[dict[str, str]],
) -> Path:
    path.write_text(
        json.dumps(
            {
                "manifest_version": "relation_field_predictive_validation_case_manifest_rc1",
                "cases": cases,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


@pytest.fixture(scope="module")
def rf10_fixture(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    root = tmp_path_factory.mktemp("rf10-predictive-validation")
    prefix = [
        _point((0, 2, 2, 2, 2)),
        _point((1, 2, 2, 2, 2)),
        _point((2, 2, 2, 2, 2)),
        _point((3, 2, 2, 2, 2)),
        _point((3, 3, 2, 2, 2)),
    ]
    neutral_future = [
        _point((2, 3, 2, 2, 2)),
        _point((2, 2, 2, 2, 2)),
        _point((3, 2, 2, 2, 2)),
        _point((3, 3, 2, 2, 2)),
    ]
    spread_cells_2 = [((3, 3, 2, 2, 2), 0.5), ((2, 3, 2, 2, 2), 0.5)]
    spread_cells_4 = [
        ((3, 3, 2, 2, 2), 0.25),
        ((2, 3, 2, 2, 2), 0.25),
        ((3, 2, 2, 2, 2), 0.25),
        ((2, 2, 2, 2, 2), 0.25),
    ]
    spread_cells_8 = [
        ((a, b, c, 2, 2), 0.125)
        for a in (2, 3)
        for b in (2, 3)
        for c in (1, 2)
    ]
    spread_cells_16 = [
        ((a, b, c, d, 2), 0.0625)
        for a in (2, 3)
        for b in (2, 3)
        for c in (1, 2)
        for d in (1, 2)
    ]
    divergent_future = [
        _mixture(spread_cells_2),
        _mixture(spread_cells_4),
        _mixture(spread_cells_8),
        _mixture(spread_cells_16),
    ]
    trajectory_neutral = _write_trajectory(
        root / "trajectory_neutral",
        prefix + neutral_future,
        trajectory_id="traj_rf10_shared_prefix",
    )
    trajectory_divergent = _write_trajectory(
        root / "trajectory_divergent",
        prefix + divergent_future,
        trajectory_id="traj_rf10_shared_prefix",
    )
    grid = build_grid_artifact(root / "grid")
    rf5 = build_temporal_relation_field(
        trajectory_neutral,
        grid,
        root / "rf5",
        start_t=0,
        to_t=4,
    )
    rf6 = build_hodge_decomposition(rf5, grid, root / "rf6")
    rf7 = build_shape_dynamics(trajectory_neutral, rf5, rf6, grid, root / "rf7")
    rf8 = build_axis_coupling_innovation(
        trajectory_neutral,
        grid,
        rf5,
        rf6,
        rf7,
        root / "rf8",
    )
    rf9 = build_risk_structure(
        trajectory_neutral,
        grid,
        rf5,
        rf6,
        rf7,
        rf8,
        root / "rf9",
    )
    manifest = _write_case_manifest(
        root / "cases.json",
        [
            {
                "case_id": "neutral_suffix",
                "partition": "development",
                "trajectory_dir": str(trajectory_neutral),
                "grid_artifact_dir": str(grid),
                "rf5_artifact_dir": str(rf5),
                "rf6_artifact_dir": str(rf6),
                "rf7_artifact_dir": str(rf7),
                "rf8_artifact_dir": str(rf8),
                "rf9_artifact_dir": str(rf9),
            },
            {
                "case_id": "divergent_suffix",
                "partition": "development",
                "trajectory_dir": str(trajectory_divergent),
                "grid_artifact_dir": str(grid),
                "rf5_artifact_dir": str(rf5),
                "rf6_artifact_dir": str(rf6),
                "rf7_artifact_dir": str(rf7),
                "rf8_artifact_dir": str(rf8),
                "rf9_artifact_dir": str(rf9),
            },
        ],
    )
    source_hashes = {
        "trajectory_neutral": _tree_hashes(trajectory_neutral),
        "trajectory_divergent": _tree_hashes(trajectory_divergent),
        "rf5": _tree_hashes(rf5),
        "rf6": _tree_hashes(rf6),
        "rf7": _tree_hashes(rf7),
        "rf8": _tree_hashes(rf8),
        "rf9": _tree_hashes(rf9),
    }
    first = build_predictive_validation(manifest, root / "rf10_a")
    second = build_predictive_validation(manifest, root / "rf10_b")
    assert source_hashes["trajectory_neutral"] == _tree_hashes(trajectory_neutral)
    assert source_hashes["trajectory_divergent"] == _tree_hashes(trajectory_divergent)
    assert source_hashes["rf5"] == _tree_hashes(rf5)
    assert source_hashes["rf6"] == _tree_hashes(rf6)
    assert source_hashes["rf7"] == _tree_hashes(rf7)
    assert source_hashes["rf8"] == _tree_hashes(rf8)
    assert source_hashes["rf9"] == _tree_hashes(rf9)
    return {
        "root": root,
        "manifest": manifest,
        "first": first,
        "second": second,
    }


def test_rf10_future_suffix_changes_outcomes_but_not_predictions(
    rf10_fixture: dict[str, Path],
) -> None:
    artifact = rf10_fixture["first"]
    snapshot = json.loads((artifact / "prediction_snapshot.json").read_text(encoding="utf-8"))
    assert len(snapshot["cases"]) == 2
    left, right = snapshot["cases"]
    assert left["rf9_risk_structure_id"] == right["rf9_risk_structure_id"]
    assert left["candidate"] == right["candidate"]
    assert left["component_baseline"] == right["component_baseline"]
    assert left["cutoff_t"] == right["cutoff_t"] == 4
    assert left["prediction_row_index"] == right["prediction_row_index"]
    assert left["nonfinal_RF9_rows_evaluated"] is False

    ledger = json.loads((artifact / "sample_ledger.json").read_text(encoding="utf-8"))["rows"]
    neutral_h4 = next(row for row in ledger if row["case_id"] == "neutral_suffix" and row["horizon"] == 4)
    divergent_h4 = next(row for row in ledger if row["case_id"] == "divergent_suffix" and row["horizon"] == 4)
    assert neutral_h4["outcomes"]["future_dispersion_outcome"] is False
    assert divergent_h4["outcomes"]["future_dispersion_outcome"] is True


def test_rf10_artifact_is_deterministic_valid_and_accuracy_claim_is_blocked(
    rf10_fixture: dict[str, Path],
) -> None:
    first = rf10_fixture["first"]
    second = rf10_fixture["second"]
    manifest = rf10_fixture["manifest"]

    assert _tree_hashes(first) == _tree_hashes(second)
    validation = validate_predictive_validation(first, manifest)
    assert validation["rf10_predictive_validation_gate"] == "passed"
    assert validation["final_row_only_gate"] is True
    assert validation["prediction_snapshot_order_gate"] is True
    assert validation["partition_group_leakage_gate"] is True
    assert validation["predictive_accuracy_claim_allowed"] is False

    leakage = json.loads((first / "leakage_audit.json").read_text(encoding="utf-8"))
    assert leakage["nonfinal_RF9_rows_evaluated"] is False
    assert leakage["future_suffix_used_as_prediction_feature"] is False
    assert leakage["trajectory_group_cross_partition_count"] == 0


def test_rf10_manifest_tampering_and_overwrite_are_rejected(
    tmp_path: Path,
    rf10_fixture: dict[str, Path],
) -> None:
    artifact = rf10_fixture["first"]
    manifest = rf10_fixture["manifest"]
    copied = tmp_path / "copied"
    shutil.copytree(artifact, copied)
    summary = copied / "summary.json"
    summary.write_text(summary.read_text(encoding="utf-8") + " ", encoding="utf-8")

    with pytest.raises(RelationFieldPredictiveValidationError, match="manifest"):
        validate_predictive_validation(copied, manifest)
    with pytest.raises(RelationFieldPredictiveValidationError, match="already exists"):
        build_predictive_validation(manifest, artifact)
