"""Independent source/artifact recomputation for Task 4-3 whole-system bundle."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from fixed5axis_hdept_bridge_task2.contracts import (
    DEFAULT_BRIDGE_CONTRACT,
    DEFAULT_FEATURE_REGISTRY,
    DEFAULT_FIXED5_CONTRACT,
    _canonical_json,
    _write_json,
    load_bridge_contract,
    load_feature_registry,
    load_fixed5_contract,
)
from fixed5axis_hdept_bridge_task3.validator import validate_observation

from .whole_system import (
    CaseSpec,
    _decoder_lock,
    _evaluate_split,
    _hash_strings,
    _load_json,
    _read_artifact_summary,
    _read_jsonl,
)

class Task43IndependentValidationError(ValueError):
    """Task 4-3 independent validation failure."""

def _canonical_equal(left: Any, right: Any) -> bool:
    return _canonical_json(left) == _canonical_json(right)

def _recompute_rows(
    bundle: Path,
    split: str,
    calibration_path: Path,
    stored_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    registry = load_feature_registry(DEFAULT_FEATURE_REGISTRY)
    fixed5 = load_fixed5_contract(DEFAULT_FIXED5_CONTRACT)
    bridge = load_bridge_contract(DEFAULT_BRIDGE_CONTRACT)
    evaluation_t = int(_load_json(bundle / "execution_lock_snapshot.json")["generation"]["evaluation_t"])
    recomputed: list[dict[str, Any]] = []
    for stored in stored_rows:
        spec = CaseSpec(**stored["case_spec"])
        canonical_dir = bundle / stored["canonical_relative_path"]
        observation_dir = bundle / stored["observation_relative_path"]
        validation = validate_observation(
            canonical_dir,
            evaluation_t,
            observation_dir,
            calibration_path=calibration_path,
        )
        if validation["status"] != "pass":
            raise Task43IndependentValidationError(f"Task 3 validation failed for {spec.case_id}")
        summary = _read_artifact_summary(
            spec,
            canonical_dir,
            observation_dir,
            calibration_path,
            registry,
            fixed5,
            bridge,
            evaluation_t,
        )
        summary["canonical_relative_path"] = canonical_dir.relative_to(bundle).as_posix()
        summary["observation_relative_path"] = observation_dir.relative_to(bundle).as_posix()
        if not _canonical_equal(summary, stored):
            raise Task43IndependentValidationError(f"stored case summary mismatch: {spec.case_id}")
        recomputed.append(summary)
    return recomputed

def _validate_manifest_if_present(bundle: Path) -> dict[str, Any]:
    path = bundle / "task4_3_manifest.json"
    if not path.is_file():
        return {"present": False, "passed": True}
    manifest = _load_json(path)
    for item in manifest["files"]:
        target = bundle / item["path"]
        if not target.is_file():
            raise Task43IndependentValidationError(f"manifest file missing: {item['path']}")
        import hashlib
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if digest != item["sha256"] or target.stat().st_size != int(item["size_bytes"]):
            raise Task43IndependentValidationError(f"manifest mismatch: {item['path']}")
    return {"present": True, "passed": True, "file_count": manifest["file_count"]}

def validate_task4_3_bundle(bundle_dir: str | Path, *, write_report: bool = True) -> dict[str, Any]:
    bundle = Path(bundle_dir)
    protocol = _load_json(bundle / "protocol_snapshot.json")
    lock = _load_json(bundle / "execution_lock_snapshot.json")
    calibration = _load_json(bundle / "fixed5axis_hdept_task4_3_calibration_rc1.json")
    sample_lock = _load_json(bundle / "task4_3_sample_size_lock.json")
    decoder_stored = _load_json(bundle / "task4_3_decoder_lock.json")
    calibration_path = bundle / "fixed5axis_hdept_task4_3_calibration_rc1.json"

    stored_calibration = _read_jsonl(bundle / "case_summaries_design_calibration.jsonl")
    stored_validation = _read_jsonl(bundle / "case_summaries_validation.jsonl")
    stored_confirmation = _read_jsonl(bundle / "case_summaries_final_confirmation.jsonl")
    calibration_rows = _recompute_rows(bundle, "design_calibration", calibration_path, stored_calibration)
    validation_rows = _recompute_rows(bundle, "validation", calibration_path, stored_validation)
    confirmation_rows = _recompute_rows(bundle, "final_confirmation", calibration_path, stored_confirmation)

    selected_seed_count = int(sample_lock["selected_seed_count_per_split"])
    for split, rows in (
        ("design_calibration", calibration_rows),
        ("validation", validation_rows),
        ("final_confirmation", confirmation_rows),
    ):
        seeds = {int(row["case_spec"]["seed"]) for row in rows}
        if len(seeds) != selected_seed_count:
            raise Task43IndependentValidationError(f"{split} seed count mismatch")

    ids = {
        "design_calibration": {row["case_spec"]["case_id"] for row in calibration_rows},
        "validation": {row["case_spec"]["case_id"] for row in validation_rows},
        "final_confirmation": {row["case_spec"]["case_id"] for row in confirmation_rows},
    }
    split_disjoint = not (
        ids["design_calibration"] & ids["validation"]
        or ids["design_calibration"] & ids["final_confirmation"]
        or ids["validation"] & ids["final_confirmation"]
    )
    if not split_disjoint:
        raise Task43IndependentValidationError("split identity overlap")

    decoder_recomputed = _decoder_lock(calibration_rows, protocol, lock, calibration)
    if not _canonical_equal(decoder_recomputed, decoder_stored):
        raise Task43IndependentValidationError("decoder lock mismatch")

    validation_audit = _load_json(bundle / "validation_split_audit.json")
    confirmation_audit = _load_json(bundle / "final_confirmation_split_audit.json")
    validation_report = _evaluate_split(
        "validation",
        calibration_rows,
        validation_rows,
        protocol,
        lock,
        calibration,
        decoder_recomputed,
        bundle,
        validation_audit,
    )
    confirmation_report = _evaluate_split(
        "final_confirmation",
        calibration_rows,
        confirmation_rows,
        protocol,
        lock,
        calibration,
        decoder_recomputed,
        bundle,
        confirmation_audit,
    )
    if not _canonical_equal(validation_report, _load_json(bundle / "task4_3_validation_report.json")):
        raise Task43IndependentValidationError("validation report mismatch")
    if not _canonical_equal(confirmation_report, _load_json(bundle / "task4_3_final_confirmation_report.json")):
        raise Task43IndependentValidationError("final-confirmation report mismatch")

    decision_stored = _load_json(bundle / "task4_3_freeze_decision.json")
    scientific_pass = bool(
        validation_report["critical_domains_passed"]
        and confirmation_report["critical_domains_passed"]
        and split_disjoint
    )
    expected_decision = (
        "test_only_bundle_generated"
        if bool(decision_stored.get("test_mode"))
        else (
            "eligible_for_task5_diagnostic_only"
            if scientific_pass
            else "blocked_scientific_bridge_failure"
        )
    )
    checks = {
        "all_case_summaries_recomputed": True,
        "all_task3_validations_passed": True,
        "split_identity_disjoint": split_disjoint,
        "decoder_lock_recomputed": True,
        "validation_report_recomputed": True,
        "final_confirmation_report_recomputed": True,
        "decision_matches": decision_stored["decision"] == expected_decision,
        "task5_authorization_matches": bool(decision_stored["task5_authorized"]) == bool(
            scientific_pass and not bool(decision_stored.get("test_mode"))
        ),
        "calibration_case_hash_matches": decoder_stored["calibration_case_ids_hash"]
        == _hash_strings(row["case_spec"]["case_id"] for row in calibration_rows),
    }
    if not all(checks.values()):
        raise Task43IndependentValidationError(f"independent checks failed: {checks}")
    report = {
        "validator_id": "fixed5axis_hdept_task4_3_independent_validator_rc1",
        "status": "pass",
        "shared_statistical_formula_contract": True,
        "independent_source_and_artifact_recomputation": True,
        "selected_seed_count_per_split": selected_seed_count,
        "case_counts": {
            "design_calibration": len(calibration_rows),
            "validation": len(validation_rows),
            "final_confirmation": len(confirmation_rows),
        },
        "checks": checks,
        "recomputed_scientific_pass": scientific_pass,
        "recomputed_decision": expected_decision,
        "manifest": _validate_manifest_if_present(bundle),
    }
    if write_report:
        _write_json(bundle / "task4_3_independent_validation_report.json", report)
    return report

def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-dir", required=True)
    return parser

def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report = validate_task4_3_bundle(args.bundle_dir)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0
