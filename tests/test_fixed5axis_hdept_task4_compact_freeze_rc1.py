from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from fixed5axis_hdept_bridge_task2.contracts import load_calibration, load_feature_registry  # noqa: E402

REGISTRY = ROOT / "configs" / "fixed5axis_hdept_feature_registry_rc1.json"
CHECKED_IN = ROOT / "artifacts" / "fixed5axis_hdept_task4_compact_freeze_rc1"
EXPECTED = {
    "fixed5axis_hdept_task4_calibration_rc1.json",
    "task4_diagnostic_findings.json",
    "task4_freeze_decision.json",
    "task4_freeze_manifest.json",
}


def _generated() -> Path:
    value = os.environ.get("TASK4_GENERATED_COMPACT_FREEZE")
    if not value:
        raise AssertionError("TASK4_GENERATED_COMPACT_FREEZE is required")
    path = Path(value)
    assert path.is_dir()
    return path


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_compact_freeze_manifest_and_file_set() -> None:
    root = _generated()
    assert {path.name for path in root.iterdir() if path.is_file()} == EXPECTED
    manifest = _load(root / "task4_freeze_manifest.json")
    assert manifest["bundle_id"] == "fixed5axis_hdept_task4_compact_freeze_rc1"
    assert {item["path"] for item in manifest["files"]} == EXPECTED - {"task4_freeze_manifest.json"}
    for item in manifest["files"]:
        path = root / item["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
        assert path.stat().st_size == item["size_bytes"]


def test_negative_scientific_result_is_frozen_without_threshold_relaxation() -> None:
    root = _generated()
    decision = _load(root / "task4_freeze_decision.json")
    diagnostic = _load(root / "task4_diagnostic_findings.json")
    validation = diagnostic["validation_summary"]
    confirmation = diagnostic["final_confirmation_summary"]
    assert validation["hypothesis_pass_count"] == 6
    assert validation["hypothesis_count"] == 8
    assert confirmation["hypothesis_pass_count"] == 6
    assert confirmation["hypothesis_count"] == 8
    assert validation["all_critical_hypotheses_passed"] is False
    assert confirmation["all_critical_hypotheses_passed"] is False
    assert decision["scientific_gate_passed"] is False
    assert decision["decision"] == "freeze_reproducibility_only_not_scientifically_approved"
    assert diagnostic["failed_hypothesis_ids"] == [
        "H2_structured_exploration",
        "H5_boundary_divergence",
    ]
    assert diagnostic["replicated_in_final_confirmation"] == diagnostic["failed_hypothesis_ids"]
    assert diagnostic["calibration_diagnostics"]["fit_only_boundary_passed"] is True
    assert "mode_count" in diagnostic["calibration_diagnostics"]["constant_features_on_validation_split"]
    assert "cluster_balance" in diagnostic["calibration_diagnostics"]["constant_features_on_validation_split"]


def test_compact_calibration_remains_contract_loadable_but_not_scientifically_approved() -> None:
    root = _generated()
    registry = load_feature_registry(REGISTRY)
    registry_hash = hashlib.sha256(REGISTRY.read_bytes()).hexdigest()
    calibration = load_calibration(
        root / "fixed5axis_hdept_task4_calibration_rc1.json",
        registry,
        registry_hash=registry_hash,
    )
    decision = _load(root / "task4_freeze_decision.json")
    assert calibration["calibration_version"] == "fixed5axis_hdept_task4_synthetic_calibration_rc1"
    assert calibration["online_refit_allowed"] is False
    assert decision["scientific_gate_passed"] is False


def test_checked_in_compact_freeze_is_byte_identical() -> None:
    generated = _generated()
    assert CHECKED_IN.is_dir()
    assert {path.name for path in CHECKED_IN.iterdir() if path.is_file()} == EXPECTED
    for name in EXPECTED:
        assert (CHECKED_IN / name).read_bytes() == (generated / name).read_bytes()
