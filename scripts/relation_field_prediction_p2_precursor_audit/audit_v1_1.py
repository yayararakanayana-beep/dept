from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from . import audit as legacy
from .common import (
    RelationFieldPredictionP2PrecursorAuditError,
    canonical_digest,
    dump_json,
    load_json,
    resolve_case_manifest,
    sha256_file,
    tree_hash,
    write_manifest,
)
from .decision import phase3_decision, support_audit


def _scalar(arrays: Mapping[str, np.ndarray], key: str) -> float | None:
    """Read a registered scalar coordinate without rejecting shape-(1,) storage."""
    if key not in arrays:
        return None
    value = np.asarray(arrays[key], dtype=np.float64)
    if value.shape == ():
        scalar = value.item()
    elif value.shape == (1,):
        scalar = value[0]
    else:
        return None
    if not np.isfinite(scalar):
        return None
    return float(scalar)


def _coordinate_triplet(
    arrays: Mapping[str, np.ndarray],
    coordinate_id: str,
) -> dict[str, float] | None:
    values = {
        part: _scalar(arrays, f"{coordinate_id}__{part}")
        for part in ("lower", "center", "upper")
    }
    if any(value is None for value in values.values()):
        return None
    return {
        key: float(value)
        for key, value in values.items()
        if value is not None
    }


def _snapshot_case(
    case: Mapping[str, Any],
    contract: Mapping[str, Any],
    dependencies: Mapping[str, Any],
    validation_cache: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    p1_root = Path(case["p1_series_dir"])
    p2_root = Path(case["p2_series_dir"])
    cache_key = (str(p1_root), str(p2_root))
    if cache_key not in validation_cache:
        validation_cache[cache_key] = dependencies["validate_p2"](
            p2_root, p1_root
        )

    p2_contract = load_json(p2_root / "contract.json")
    if (
        p2_contract.get("contract_version")
        != contract["parents"]["p2_contract_version"]
    ):
        raise RelationFieldPredictionP2PrecursorAuditError(
            "P2-4 parent P2 contract mismatch"
        )

    origin = legacy._origin_dir(
        p2_root, int(case["cutoff_t"]), p2_contract
    )
    if not origin.is_dir():
        raise RelationFieldPredictionP2PrecursorAuditError(
            f"P2-4 cutoff origin missing: {case['case_id']}"
        )

    storage = p2_contract["storage"]
    coordinates = dependencies["load_npz"](
        origin / str(storage["coordinate_file"])
    )
    first = dependencies["load_npz"](
        origin / str(storage["first_difference_file"])
    )
    second = dependencies["load_npz"](
        origin / str(storage["second_difference_file"])
    )
    risk = load_json(origin / str(storage["risk_structure_file"]))
    risk_by_id = {
        str(row["risk_structure_id"]): row for row in risk["records"]
    }

    scores: dict[str, dict[str, float | None]] = {}
    intervals: dict[str, dict[str, float] | None] = {}
    for target_id, target in contract["targets"].items():
        coordinate_id = str(target["structure_coordinate_id"])
        intervals[target_id] = _coordinate_triplet(
            coordinates, coordinate_id
        )
        center = (
            None
            if intervals[target_id] is None
            else intervals[target_id]["center"]
        )
        component_values = [
            _scalar(coordinates, f"{component_id}__center")
            for component_id in target["component_coordinate_ids"]
        ]
        p1_record = risk_by_id.get(target_id)
        scores[target_id] = {
            "p2_structure_margin": center,
            "p2_structure_margin_first_difference": _scalar(
                first, f"{coordinate_id}__center"
            ),
            "p2_structure_margin_second_difference": _scalar(
                second, f"{coordinate_id}__center"
            ),
            "p2_component_only_margin": legacy._compose_components(
                component_values,
                str(target["component_composition"]),
            ),
            "p1_boolean_candidate": (
                None
                if p1_record is None
                else float(bool(p1_record["p1_current_candidate"]))
            ),
            "always_negative": 0.0,
        }

    applicability: dict[str, float | None] = {}
    for coordinate_id in contract["applicability_stratification"][
        "coordinate_ids"
    ]:
        applicability[coordinate_id] = _scalar(
            coordinates, f"{coordinate_id}__center"
        )

    prefix_root = Path(case["prefix_trajectory_dir"])
    return {
        "case_id": str(case["case_id"]),
        "partition": str(case["partition"]),
        "trajectory_group_id": str(case["trajectory_group_id"]),
        "cutoff_t": int(case["cutoff_t"]),
        "prediction_scores": scores,
        "structure_intervals": intervals,
        "applicability": applicability,
        "p1_tree_hash": tree_hash(p1_root),
        "p2_tree_hash": tree_hash(p2_root),
        "prefix_trajectory_tree_hash": tree_hash(prefix_root),
        "p2_origin_manifest_sha256": sha256_file(
            origin / "manifest.json"
        ),
        "future_suffix_read_before_snapshot": False,
    }


def freeze_prediction_snapshot(
    cases: Sequence[Mapping[str, Any]],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    dependencies = legacy._lazy_dependencies()
    validation_cache: dict[tuple[str, str], dict[str, Any]] = {}
    rows = [
        _snapshot_case(case, contract, dependencies, validation_cache)
        for case in cases
    ]
    payload = {
        "contract_version": contract["contract_version"],
        "prediction_snapshot_frozen_before_full_trajectory_read": True,
        "future_suffix_read_before_snapshot": False,
        "cases": rows,
    }
    payload["prediction_snapshot_hash"] = canonical_digest(payload)
    return payload


def assert_primary_score_availability(
    snapshot: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    missing: list[str] = []
    for case in snapshot["cases"]:
        for target_id in sorted(contract["targets"]):
            score = case["prediction_scores"][target_id].get(
                "p2_structure_margin"
            )
            interval = case["structure_intervals"].get(target_id)
            if score is None or interval is None:
                missing.append(f"{case['case_id']}:{target_id}")
    if missing:
        raise RelationFieldPredictionP2PrecursorAuditError(
            "P2-4 primary coordinate unavailable before future read: "
            f"{missing[:10]}"
        )
    return {
        "primary_score_availability_gate": "passed",
        "checked_before_future_read": True,
        "case_target_count": (
            len(snapshot["cases"]) * len(contract["targets"])
        ),
    }


def build_precursor_audit(
    case_manifest_path: str | Path,
    output: str | Path,
    *,
    contract: Mapping[str, Any],
) -> Path:
    target = Path(output)
    if target.exists():
        raise RelationFieldPredictionP2PrecursorAuditError(
            f"output already exists: {target}"
        )

    raw_manifest, cases = resolve_case_manifest(
        case_manifest_path, contract
    )
    source_roots = sorted(
        {
            str(Path(case[field]))
            for case in cases
            for field in (
                "prefix_trajectory_dir",
                "full_trajectory_dir",
                "grid_artifact_dir",
                "p1_series_dir",
                "p2_series_dir",
            )
        }
    )
    before = {path: tree_hash(Path(path)) for path in source_roots}

    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(
        tempfile.mkdtemp(
            prefix=f".{target.name}.tmp-", dir=target.parent
        )
    )
    try:
        dump_json(
            temporary / contract["storage"]["contract_file"],
            dict(contract),
        )
        dump_json(
            temporary / contract["storage"]["frozen_case_manifest_file"],
            raw_manifest,
        )

        snapshot = freeze_prediction_snapshot(cases, contract)
        availability = assert_primary_score_availability(
            snapshot, contract
        )
        dump_json(
            temporary / contract["storage"]["prediction_snapshot_file"],
            snapshot,
        )

        # The future suffix is intentionally unread until the primary P2
        # coordinates have been frozen and proven available.
        futures = legacy.read_future_outcomes(
            cases, snapshot, contract
        )
        dump_json(
            temporary / contract["storage"]["future_outcomes_file"],
            futures,
        )

        samples = legacy._sample_rows(snapshot, futures, contract)
        dump_json(
            temporary / contract["storage"]["sample_ledger_file"],
            {
                "sample_ledger_version": (
                    "relation_field_prediction_p2_precursor_samples_v1"
                ),
                "prediction_snapshot_hash": snapshot[
                    "prediction_snapshot_hash"
                ],
                "rows": samples,
            },
        )

        metrics = legacy._metrics(samples, contract)
        dump_json(
            temporary / contract["storage"]["metrics_file"],
            {
                "metrics_version": (
                    "relation_field_prediction_p2_precursor_metrics_v1"
                ),
                "cross_target_aggregation_performed": False,
                "rows": metrics,
            },
        )

        support = support_audit(samples, contract)
        dump_json(
            temporary / contract["storage"]["support_file"],
            support,
        )

        decision = phase3_decision(metrics, support, contract)
        decision.update(
            {
                "precursor_accuracy_claim": (
                    False
                    if decision["status"]
                    == "blocked_support_insufficient"
                    else None
                ),
                "p3_predictor_fitted": False,
                "true_irreversibility_claim": False,
            }
        )
        dump_json(
            temporary / contract["storage"]["decision_file"],
            decision,
        )
        dump_json(
            temporary / contract["storage"]["ablation_file"],
            legacy._ablation(metrics),
        )
        dump_json(
            temporary / contract["storage"]["stratification_file"],
            legacy._stratification(samples, contract),
        )
        dump_json(
            temporary / contract["storage"]["validation_file"],
            {
                "p2_4_audit_gate": "passed",
                "prediction_snapshot_frozen_before_future_read": True,
                "primary_score_availability_checked_before_future_read": True,
                "primary_score_availability": availability,
                "rf10_outcome_definitions_reused": True,
                "model_fitting_performed": False,
                "threshold_tuning_performed": False,
                "cross_target_aggregation_performed": False,
                "parent_writeback_performed": False,
                "independent_validator_available": True,
                "scientific_status": decision["status"],
            },
        )

        write_manifest(
            temporary,
            "relation_field_prediction_p2_precursor_audit_v1_1",
        )
        after = {path: tree_hash(Path(path)) for path in source_roots}
        if before != after:
            raise RelationFieldPredictionP2PrecursorAuditError(
                "P2-4 source artifact was modified"
            )

        temporary.rename(target)
        return target
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
