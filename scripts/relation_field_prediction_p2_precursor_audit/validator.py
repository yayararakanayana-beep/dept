from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .common import (
    RelationFieldPredictionP2PrecursorAuditError,
    canonical_digest,
    load_json,
    resolve_case_manifest,
    tree_hash,
    verify_manifest,
)
from ._validator_recompute import _decision, _metric_rows, _reconstruct_samples, _support


def _equal(expected: Any, actual: Any, name: str) -> None:
    if canonical_digest(expected) != canonical_digest(actual):
        raise RelationFieldPredictionP2PrecursorAuditError(
            f"independent validator mismatch: {name}"
        )


def validate_precursor_audit(
    audit_dir: str | Path,
    case_manifest_path: str | Path,
    *,
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    root = Path(audit_dir).resolve()
    verify_manifest(root)
    if (
        load_json(root / contract["storage"]["contract_file"])
        != dict(contract)
    ):
        raise RelationFieldPredictionP2PrecursorAuditError(
            "stored P2-4 contract mismatch"
        )
    raw, cases = resolve_case_manifest(case_manifest_path, contract)
    _equal(
        raw,
        load_json(
            root / contract["storage"]["frozen_case_manifest_file"]
        ),
        "case manifest",
    )
    snapshot = load_json(
        root / contract["storage"]["prediction_snapshot_file"]
    )
    futures = load_json(
        root / contract["storage"]["future_outcomes_file"]
    )
    check = dict(snapshot)
    saved_hash = check.pop("prediction_snapshot_hash")
    if canonical_digest(check) != saved_hash:
        raise RelationFieldPredictionP2PrecursorAuditError(
            "prediction snapshot hash mismatch"
        )
    by_case = {
        str(row["case_id"]): row for row in snapshot["cases"]
    }
    future_by = {
        str(row["case_id"]): row for row in futures["cases"]
    }
    for case in cases:
        frozen = by_case[str(case["case_id"])]
        if (
            tree_hash(Path(case["p1_series_dir"]))
            != frozen["p1_tree_hash"]
            or tree_hash(Path(case["p2_series_dir"]))
            != frozen["p2_tree_hash"]
            or tree_hash(Path(case["prefix_trajectory_dir"]))
            != frozen["prefix_trajectory_tree_hash"]
        ):
            raise RelationFieldPredictionP2PrecursorAuditError(
                "prediction source hash mismatch"
            )
        if (
            tree_hash(Path(case["full_trajectory_dir"]))
            != future_by[str(case["case_id"])][
                "full_trajectory_tree_hash"
            ]
        ):
            raise RelationFieldPredictionP2PrecursorAuditError(
                "future source hash mismatch"
            )

    samples = _reconstruct_samples(snapshot, futures, contract)
    saved_samples = load_json(
        root / contract["storage"]["sample_ledger_file"]
    )
    _equal(samples, saved_samples["rows"], "sample ledger")

    metrics = _metric_rows(samples, contract)
    saved_metrics = load_json(
        root / contract["storage"]["metrics_file"]
    )
    _equal(metrics, saved_metrics["rows"], "metrics")

    support = _support(samples, contract)
    _equal(
        support,
        load_json(root / contract["storage"]["support_file"]),
        "support",
    )

    decision = _decision(metrics, support, contract)
    saved_decision = load_json(
        root / contract["storage"]["decision_file"]
    )
    for key, value in decision.items():
        if saved_decision.get(key) != value:
            raise RelationFieldPredictionP2PrecursorAuditError(
                f"independent validator mismatch: decision.{key}"
            )

    return {
        "p2_4_independent_validation_gate": "passed",
        "case_count": len(cases),
        "sample_count": len(samples),
        "metric_row_count": len(metrics),
        "decision_status": decision["status"],
        "builder_metric_module_imported": False,
        "rf10_outcome_redefinition_performed": False,
    }
