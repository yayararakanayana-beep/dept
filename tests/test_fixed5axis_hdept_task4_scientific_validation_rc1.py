from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from fixed5axis_hdept_bridge_task2.contracts import load_calibration, load_feature_registry  # noqa: E402
from fixed5axis_hdept_bridge_task4.scenarios import SCENARIOS, generate_trajectory  # noqa: E402

PROTOCOL = ROOT / "configs" / "fixed5axis_hdept_task4_scientific_validation_rc1.json"
REGISTRY = ROOT / "configs" / "fixed5axis_hdept_feature_registry_rc1.json"
FROZEN = ROOT / "artifacts" / "fixed5axis_hdept_task4_rc1"
EXPECTED_FILES = {
    "fixed5axis_hdept_task4_calibration_rc1.json",
    "task4_calibration_audit.json",
    "task4_validation_report.json",
    "task4_final_confirmation_report.json",
    "task4_freeze_decision.json",
    "task4_manifest.json",
}


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _bundle() -> Path:
    value = os.environ.get("TASK4_GENERATED_BUNDLE")
    if not value:
        raise AssertionError("TASK4_GENERATED_BUNDLE is required for Task 4 tests")
    path = Path(value)
    assert path.is_dir()
    return path


def test_protocol_splits_are_pre_registered_and_disjoint() -> None:
    protocol = _load(PROTOCOL)
    assert protocol["status"] == "pre_registered_before_task4_execution"
    identities = {}
    for split_name, split in protocol["splits"].items():
        ids = {
            f"task4_{scenario}_seed{seed}"
            for seed in range(split["seed_start"], split["seed_start"] + split["seed_count"])
            for scenario in split["scenario_families"]
        }
        identities[split_name] = ids
    assert not (identities["calibration"] & identities["validation"])
    assert not (identities["calibration"] & identities["final_confirmation"])
    assert not (identities["validation"] & identities["final_confirmation"])


def test_scenario_generator_is_deterministic_and_distinct() -> None:
    first = generate_trajectory("stable_broad", 1234, 14)
    second = generate_trajectory("stable_broad", 1234, 14)
    locked = generate_trajectory("locked_fixation", 1234, 14)
    assert np.array_equal(first, second)
    assert first.shape == (14, 5, 5, 5, 5, 5)
    assert first.dtype == np.float64
    assert np.allclose(first.sum(axis=(1, 2, 3, 4, 5)), 1.0, atol=1e-12)
    assert not np.array_equal(first, locked)
    assert set(SCENARIOS) == set(_load(PROTOCOL)["splits"]["validation"]["scenario_families"])


def test_generated_bundle_file_set_and_manifest_integrity() -> None:
    bundle = _bundle()
    assert {path.name for path in bundle.iterdir() if path.is_file()} == EXPECTED_FILES
    manifest = _load(bundle / "task4_manifest.json")
    assert {entry["path"] for entry in manifest["files"]} == EXPECTED_FILES - {"task4_manifest.json"}
    for entry in manifest["files"]:
        path = bundle / entry["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]
        assert path.stat().st_size == entry["size_bytes"]


def test_frozen_calibration_is_fit_only_and_loadable() -> None:
    bundle = _bundle()
    calibration = _load(bundle / "fixed5axis_hdept_task4_calibration_rc1.json")
    audit = _load(bundle / "task4_calibration_audit.json")
    registry = load_feature_registry(REGISTRY)
    registry_hash = hashlib.sha256(REGISTRY.read_bytes()).hexdigest()
    loaded = load_calibration(bundle / "fixed5axis_hdept_task4_calibration_rc1.json", registry, registry_hash=registry_hash)
    assert loaded["calibration_version"] == "fixed5axis_hdept_task4_synthetic_calibration_rc1"
    assert calibration["fit_split"] == "calibration"
    assert calibration["validation_or_confirmation_used_for_fit"] is False
    assert calibration["online_refit_allowed"] is False
    assert audit["fit_only_boundary_passed"] is True
    assert audit["status"] == "pass"
    assert audit["insufficient_scored_features"] == []


def test_validation_and_confirmation_are_complete_and_independently_validated() -> None:
    bundle = _bundle()
    for name, split in (
        ("task4_validation_report.json", "validation"),
        ("task4_final_confirmation_report.json", "final_confirmation"),
    ):
        report = _load(bundle / name)
        assert report["split"] == split
        assert report["all_task3_validations_passed"] is True
        assert report["hypothesis_count"] == 8
        assert len(report["hypotheses"]) == 8
        assert report["case_count"] == 33
        assert all(case["task3_validation_status"] == "pass" for case in report["case_summaries"])
        assert all(case["global_observation_status"] == "LIMITED" for case in report["case_summaries"])
        assert all(case["h11"]["Predictability"]["available"] is False for case in report["case_summaries"])
        assert all(case["h11"]["Recoverability"]["available"] is False for case in report["case_summaries"])


def test_freeze_decision_matches_pre_registered_gates() -> None:
    bundle = _bundle()
    decision = _load(bundle / "task4_freeze_decision.json")
    validation = _load(bundle / "task4_validation_report.json")
    confirmation = _load(bundle / "task4_final_confirmation_report.json")
    expected_pass = all(
        (
            decision["calibration_reproducible"],
            decision["split_identity_overlap_forbidden_passed"],
            decision["calibration_fit_only_passed"],
            decision["calibration_sample_coverage_passed"],
            decision["all_task3_validations_passed"],
            validation["all_critical_hypotheses_passed"],
            confirmation["all_critical_hypotheses_passed"],
        )
    )
    assert decision["scientific_gate_passed"] is expected_pass
    assert decision["scientific_status"] == "B_limited_synthetic_fixed5_only"
    if expected_pass:
        assert decision["decision"] == "freeze_as_B_limited_synthetic_scientific_baseline"
    else:
        assert decision["decision"] == "freeze_reproducibility_only_not_scientifically_approved"


def test_checked_in_freeze_bundle_matches_generated_bundle_when_present() -> None:
    if not FROZEN.is_dir():
        return
    generated = _bundle()
    assert {path.name for path in FROZEN.iterdir() if path.is_file()} == EXPECTED_FILES
    for name in EXPECTED_FILES:
        assert (FROZEN / name).read_bytes() == (generated / name).read_bytes()
