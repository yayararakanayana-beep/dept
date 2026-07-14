from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from fixed5axis_gk_rc1 import AXIS_BINS, AXIS_NAMES, GENESIS_HASH, compute_gt_hash, compute_history_chain_hash
from relation_field_grid_rc1 import cell_id_from_indices
from relation_field_prediction_p2_precursor_audit.common import dump_json, load_json, target_horizon_required
from relation_field_prediction_p2_formal_audit_plan import FormalAuditDatasetError, _base_broad_points, _tuple5, transform_index

OUTCOME_FIELDS = (
    "future_concentration_outcome",
    "future_persistent_concentration_outcome",
    "future_dispersion_outcome",
    "future_recovery_failure_outcome",
    "future_recovery_failure_applicable",
)


def _distribution(
    points: Sequence[
        tuple[tuple[int, int, int, int, int], float]
    ]
) -> np.ndarray:
    flat = np.zeros(5**5, dtype=np.float64)
    for indices, mass in points:
        flat[cell_id_from_indices(indices)] += float(mass)
    total = float(np.sum(flat))
    if total <= 0.0:
        raise FormalAuditDatasetError("distribution mass is empty")
    flat /= total
    return flat.reshape((5, 5, 5, 5, 5))


def _point(indices: tuple[int, int, int, int, int]) -> np.ndarray:
    return _distribution([(indices, 1.0)])


def _equal_mix(
    indices: Sequence[tuple[int, int, int, int, int]]
) -> np.ndarray:
    if not indices:
        raise FormalAuditDatasetError("mixture must not be empty")
    return _distribution(
        [(value, 1.0 / len(indices)) for value in indices]
    )


def _transformed_geometry(
    plan: Mapping[str, Any],
    case: Mapping[str, Any],
) -> dict[str, Any]:
    permutation = case["permutation"]
    mirror_mask = int(case["mirror_mask"])
    base_centers = [
        _tuple5(value, "base center")
        for value in plan["geometry"]["base_centers"]
    ]
    transformed_centers = [
        transform_index(center, permutation, mirror_mask)
        for center in base_centers
    ]
    broad_frames = [
        sorted(
            transform_index(point, permutation, mirror_mask)
            for point in _base_broad_points(
                center, plan["geometry"]["broad_offsets"]
            )
        )
        for center in base_centers
    ]
    boundary = transform_index(
        plan["geometry"]["boundary_corner"],
        permutation,
        mirror_mask,
    )
    return {
        "point_prefix": [_point(value) for value in transformed_centers],
        "broad_prefix": [_equal_mix(value) for value in broad_frames],
        "point_anchor": _point(transformed_centers[-1]),
        "broad_anchor": _equal_mix(broad_frames[-1]),
        "boundary_corner": _point(boundary),
    }


def _write_trajectory(
    root: Path,
    frames: Sequence[np.ndarray],
    trajectory_id: str,
) -> Path:
    root.mkdir(parents=True, exist_ok=False)
    np.save(root / "gt_mass.npy", np.stack(frames), allow_pickle=False)
    fields = [
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
    rows: list[dict[str, Any]] = []
    previous = ""
    chain = GENESIS_HASH
    for t, frame in enumerate(frames):
        distribution_hash = hashlib.sha256(
            np.ascontiguousarray(frame).tobytes()
        ).hexdigest()
        source_hash = hashlib.sha256(
            (
                f"p2-4-formal-{trajectory_id}-{t}-"
                f"{distribution_hash}"
            ).encode()
        ).hexdigest()
        gt_hash = compute_gt_hash(
            contract_version="fixed5axis_gk_rc1",
            trajectory_id=trajectory_id,
            t=t,
            distribution=frame,
            source_state_hash=source_hash,
        )
        chain = compute_history_chain_hash(chain, gt_hash, t)
        rows.append(
            {
                "trajectory_id": trajectory_id,
                "source_trajectory_id": trajectory_id,
                "t": t,
                "phase": "pre_transition",
                "gt_row_index": t,
                "gt_hash": gt_hash,
                "previous_gt_hash": previous,
                "history_chain_hash": chain,
                "delta_t": 0 if t == 0 else 1,
                "continuity_status": (
                    "initial" if t == 0 else "continuous"
                ),
                "admissible_for_research": True,
                "source_state_ref": f"states/step_{t:06d}.npz",
                "source_state_hash": source_hash,
            }
        )
        previous = gt_hash

    with (root / "history_ledger.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(
            handle, fieldnames=fields, lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)

    dump_json(
        root / "provenance.json",
        {
            "contract_version": "fixed5axis_gk_rc1",
            "axis_order": list(AXIS_NAMES),
            "axis_bins": list(AXIS_BINS),
            "gt_shape": [5, 5, 5, 5, 5],
            "gt_dtype": "float64",
            "gt_phase": "pre_transition",
            "source_mode": "reference_full",
            "trajectory_id": trajectory_id,
            "total_gt_frames": len(frames),
            "forbidden_source_files_read": [],
            "source_writeback_performed": False,
            "canonical_history_is_complete_gt_sequence": True,
        },
    )
    return root


def _verify_expected_outcomes(
    plan: Mapping[str, Any], audit_dir: Path
) -> dict[str, Any]:
    actual_payload = load_json(audit_dir / "future_outcomes.json")
    actual_by_id = {
        str(row["case_id"]): row for row in actual_payload["cases"]
    }
    mismatch: list[dict[str, Any]] = []
    for case in plan["cases"]:
        case_id = str(case["case_id"])
        family = plan["families"][case["family_id"]]
        actual_case = actual_by_id[case_id]
        for horizon in ("1", "2", "4"):
            actual = actual_case["horizons"][horizon]
            expected = family["expected_rf10_outcomes"][horizon]
            for field in OUTCOME_FIELDS:
                if bool(actual[field]) != bool(expected[field]):
                    mismatch.append(
                        {
                            "case_id": case_id,
                            "family_id": case["family_id"],
                            "horizon": int(horizon),
                            "field": field,
                            "expected": bool(expected[field]),
                            "actual": bool(actual[field]),
                        }
                    )
    if mismatch:
        raise FormalAuditDatasetError(
            f"RF-10 expected outcome mismatch: {mismatch[:5]}"
        )
    return {
        "expected_outcome_gate": "passed",
        "checked_case_count": len(plan["cases"]),
        "checked_horizon_count": len(plan["cases"]) * 3,
        "checked_field_count": len(plan["cases"]) * 3 * len(OUTCOME_FIELDS),
    }


def _verify_primary_score_availability(
    audit_dir: Path, contract: Mapping[str, Any]
) -> dict[str, Any]:
    snapshot = load_json(audit_dir / "prediction_snapshot.json")
    missing: list[str] = []
    for case in snapshot["cases"]:
        for target_id in sorted(contract["targets"]):
            value = case["prediction_scores"][target_id].get(
                "p2_structure_margin"
            )
            if value is None:
                missing.append(f"{case['case_id']}:{target_id}")
    if missing:
        raise FormalAuditDatasetError(
            f"formal primary coordinate unavailable: {missing[:10]}"
        )
    return {
        "primary_score_availability_gate": "passed",
        "case_target_count": (
            len(snapshot["cases"]) * len(contract["targets"])
        ),
    }


def _primary_metric_summary(
    audit_dir: Path, contract: Mapping[str, Any]
) -> list[dict[str, Any]]:
    payload = load_json(audit_dir / "precursor_metrics.json")
    return [
        {
            "target_id": row["target_id"],
            "horizon": int(row["horizon"]),
            "sample_count": int(row["sample_count"]),
            "positive_outcome_count": int(
                row["positive_outcome_count"]
            ),
            "negative_outcome_count": int(
                row["negative_outcome_count"]
            ),
            "positive_prevalence": row["positive_prevalence"],
            "roc_auc": row["roc_auc"],
            "roc_auc_interval": row["bootstrap"][
                "roc_auc_interval"
            ],
            "average_precision": row["average_precision"],
            "average_precision_interval": row["bootstrap"][
                "average_precision_interval"
            ],
        }
        for row in payload["rows"]
        if row["partition"] == "test"
        and row["score_id"] == "p2_structure_margin"
        and target_horizon_required(
            contract, row["target_id"], int(row["horizon"])
        )
    ]


def _scientific_status(decision_status: str) -> str:
    mapping = {
        "eligible_for_full_phase3_model_comparison": (
            "B_limited_preregistered_synthetic_precursor_signal_all_targets"
        ),
        "eligible_for_partial_phase3_model_comparison": (
            "B_limited_preregistered_synthetic_precursor_signal_partial_targets"
        ),
        "blocked_no_supported_precursor_signal": (
            "C_no_supported_precursor_signal_in_preregistered_synthetic_test"
        ),
    }
    if decision_status not in mapping:
        raise FormalAuditDatasetError(
            f"formal audit ended before performance interpretation: "
            f"{decision_status}"
        )
    return mapping[decision_status]


