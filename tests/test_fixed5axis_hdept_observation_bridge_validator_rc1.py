from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "scripts", ROOT / "tests"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from fixed5axis_hdept_bridge_task2.builder import build_observation  # noqa: E402
from fixed5axis_hdept_bridge_task3.validator import (  # noqa: E402
    Fixed5AxisHDEPTValidationError,
    validate_observation,
)
from test_fixed5axis_hdept_observation_bridge_rc1 import (  # noqa: E402
    _make_calibration,
    _make_canonical,
    _tree_hash,
)

PAYLOAD_FILES = ("identity.json", "features.json", "m_observation.json", "audit.json", "provenance.json")


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _refresh_manifest(artifact: Path) -> None:
    manifest = _load(artifact / "manifest.json")
    manifest["files"] = [
        {
            "path": name,
            "sha256": hashlib.sha256((artifact / name).read_bytes()).hexdigest(),
            "size_bytes": (artifact / name).stat().st_size,
        }
        for name in PAYLOAD_FILES
    ]
    _dump(artifact / "manifest.json", manifest)


def _build_pair(tmp_path: Path, *, calibrated: bool = True, frames: int = 6, current_t: int = 4) -> tuple[Path, Path, Path | None]:
    source = _make_canonical(tmp_path / "canonical", frames=frames)
    calibration = _make_calibration(tmp_path / "calibration.json") if calibrated else None
    artifact = build_observation(source, current_t, tmp_path / "artifact", calibration_path=calibration)
    return source, artifact, calibration


def test_validator_accepts_calibrated_and_uncalibrated_artifacts(tmp_path: Path) -> None:
    source, artifact, calibration = _build_pair(tmp_path / "calibrated")
    report = validate_observation(source, 4, artifact, calibration_path=calibration)
    assert report["status"] == "pass"
    assert report["checked_feature_count"] == 47
    assert report["checked_h11_axis_count"] == 11
    assert report["global_observation_status"] == "LIMITED"
    assert all(value == "passed" for value in report["gates"].values())

    source_u, artifact_u, _ = _build_pair(tmp_path / "uncalibrated", calibrated=False)
    report_u = validate_observation(source_u, 4, artifact_u)
    assert report_u["status"] == "pass"
    assert report_u["global_observation_status"] == "HOLD_RECOMMENDED"


def test_same_prefix_different_future_is_accepted(tmp_path: Path) -> None:
    source_a = _make_canonical(tmp_path / "canonical_a", future_variant=0.0)
    source_b = _make_canonical(tmp_path / "canonical_b", future_variant=0.22)
    calibration = _make_calibration(tmp_path / "calibration.json")
    artifact = build_observation(source_a, 4, tmp_path / "artifact", calibration_path=calibration)
    report = validate_observation(source_b, 4, artifact, calibration_path=calibration)
    assert report["status"] == "pass"
    assert report["current_t"] == 4


def test_single_frame_insufficient_history_is_valid_but_not_evidence(tmp_path: Path) -> None:
    source, artifact, _ = _build_pair(tmp_path, calibrated=False, frames=1, current_t=0)
    report = validate_observation(source, 0, artifact)
    assert report["status"] == "pass"
    assert report["global_observation_status"] == "INSUFFICIENT_HISTORY"
    assert report["critical_raw_invariants"]["neutral_placeholder_non_evidence"] is True


def test_source_is_not_modified_by_validator(tmp_path: Path) -> None:
    source, artifact, calibration = _build_pair(tmp_path)
    before = _tree_hash(source)
    validate_observation(source, 4, artifact, calibration_path=calibration)
    after = _tree_hash(source)
    assert before == after


def test_extra_or_missing_artifact_file_is_rejected(tmp_path: Path) -> None:
    source, artifact, calibration = _build_pair(tmp_path / "extra")
    (artifact / "unexpected.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(Fixed5AxisHDEPTValidationError, match="exact file set"):
        validate_observation(source, 4, artifact, calibration_path=calibration)

    source_m, artifact_m, calibration_m = _build_pair(tmp_path / "missing")
    (artifact_m / "audit.json").unlink()
    with pytest.raises(Fixed5AxisHDEPTValidationError, match="exact file set"):
        validate_observation(source_m, 4, artifact_m, calibration_path=calibration_m)


def test_manifest_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    source, artifact, calibration = _build_pair(tmp_path)
    features = _load(artifact / "features.json")
    features["features"][0]["support_count"] = 999
    _dump(artifact / "features.json", features)
    with pytest.raises(Fixed5AxisHDEPTValidationError, match="manifest integrity"):
        validate_observation(source, 4, artifact, calibration_path=calibration)


def test_regenerated_manifest_does_not_hide_reserved_feature_zero_fill(tmp_path: Path) -> None:
    source, artifact, calibration = _build_pair(tmp_path)
    features = _load(artifact / "features.json")
    reserved = next(item for item in features["features"] if item["derivation_status"].startswith("reserved_"))
    reserved["value"] = 0.0
    _dump(artifact / "features.json", features)
    _refresh_manifest(artifact)
    with pytest.raises(Fixed5AxisHDEPTValidationError, match="features"):
        validate_observation(source, 4, artifact, calibration_path=calibration)


def test_regenerated_manifest_does_not_hide_neutral_placeholder_misuse(tmp_path: Path) -> None:
    source, artifact, calibration = _build_pair(tmp_path)
    observation = _load(artifact / "m_observation.json")
    axis = observation["h11"]["Predictability"]
    assert axis["available"] is False
    axis["transport_value"] = 0.63
    axis["transport_value_is_neutral_placeholder"] = False
    _dump(artifact / "m_observation.json", observation)
    _refresh_manifest(artifact)
    with pytest.raises(Fixed5AxisHDEPTValidationError, match="m_observation"):
        validate_observation(source, 4, artifact, calibration_path=calibration)


def test_unknown_artifact_contract_version_is_rejected(tmp_path: Path) -> None:
    source, artifact, calibration = _build_pair(tmp_path)
    identity = _load(artifact / "identity.json")
    identity["contract_version"] = "unknown_contract"
    _dump(artifact / "identity.json", identity)
    _refresh_manifest(artifact)
    with pytest.raises(Fixed5AxisHDEPTValidationError, match="contract_version"):
        validate_observation(source, 4, artifact, calibration_path=calibration)


def test_source_axis_order_mismatch_is_rejected(tmp_path: Path) -> None:
    source, artifact, calibration = _build_pair(tmp_path)
    provenance = _load(source / "provenance.json")
    provenance["axis_order"][0], provenance["axis_order"][1] = provenance["axis_order"][1], provenance["axis_order"][0]
    _dump(source / "provenance.json", provenance)
    with pytest.raises(Fixed5AxisHDEPTValidationError, match="axis order"):
        validate_observation(source, 4, artifact, calibration_path=calibration)


@pytest.mark.parametrize("mutation, message", [
    ("negative", "negative mass"),
    ("non_finite", "non-finite"),
    ("non_normalized", "does not sum to one"),
])
def test_invalid_current_mass_is_rejected(tmp_path: Path, mutation: str, message: str) -> None:
    source, artifact, calibration = _build_pair(tmp_path)
    mass = np.load(source / "gt_mass.npy", allow_pickle=False)
    broken = mass.copy()
    if mutation == "negative":
        broken[4].flat[0] = -1e-4
    elif mutation == "non_finite":
        broken[4].flat[0] = np.nan
    else:
        broken[4] *= 0.99
    np.save(source / "gt_mass.npy", broken, allow_pickle=False)
    with pytest.raises(Fixed5AxisHDEPTValidationError, match=message):
        validate_observation(source, 4, artifact, calibration_path=calibration)


def test_history_continuity_and_hash_tampering_are_rejected(tmp_path: Path) -> None:
    source, artifact, calibration = _build_pair(tmp_path / "continuity")
    with (source / "history_ledger.csv").open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fields = list(rows[0])
    rows[4]["continuity_status"] = "duplicate"
    rows[4]["delta_t"] = "0"
    with (source / "history_ledger.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    with pytest.raises(Fixed5AxisHDEPTValidationError, match="continuity metadata"):
        validate_observation(source, 4, artifact, calibration_path=calibration)

    source_h, artifact_h, calibration_h = _build_pair(tmp_path / "hash")
    with (source_h / "history_ledger.csv").open("r", encoding="utf-8", newline="") as handle:
        rows_h = list(csv.DictReader(handle)); fields_h = list(rows_h[0])
    rows_h[4]["history_chain_hash"] = "0" * 64
    with (source_h / "history_ledger.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields_h); writer.writeheader(); writer.writerows(rows_h)
    with pytest.raises(Fixed5AxisHDEPTValidationError, match="history chain"):
        validate_observation(source_h, 4, artifact_h, calibration_path=calibration_h)


def test_calibration_registry_or_version_mismatch_is_rejected(tmp_path: Path) -> None:
    source, artifact, calibration = _build_pair(tmp_path / "registry")
    broken = _load(calibration)
    broken["feature_registry_hash"] = "0" * 64
    _dump(tmp_path / "registry" / "broken_calibration.json", broken)
    with pytest.raises(ValueError, match="registry identity"):
        validate_observation(source, 4, artifact, calibration_path=tmp_path / "registry" / "broken_calibration.json")

    source_v, artifact_v, calibration_v = _build_pair(tmp_path / "version")
    changed = _load(calibration_v)
    changed["calibration_version"] = "different_version"
    changed_path = tmp_path / "version" / "changed_calibration.json"
    _dump(changed_path, changed)
    with pytest.raises(Fixed5AxisHDEPTValidationError, match="calibration_version"):
        validate_observation(source_v, 4, artifact_v, calibration_path=changed_path)


def test_validator_cli_success_and_fail_closed_exit_codes(tmp_path: Path) -> None:
    source, artifact, calibration = _build_pair(tmp_path)
    script = ROOT / "scripts" / "fixed5axis_hdept_observation_bridge_validator_rc1.py"
    report_path = tmp_path / "validation.json"
    success = subprocess.run(
        [
            sys.executable, str(script),
            "--trajectory-dir", str(source),
            "--current-t", "4",
            "--artifact-dir", str(artifact),
            "--calibration", str(calibration),
            "--output", str(report_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert success.returncode == 0
    assert _load(report_path)["status"] == "pass"

    identity = _load(artifact / "identity.json")
    identity["current_t"] = 99
    _dump(artifact / "identity.json", identity)
    _refresh_manifest(artifact)
    failure = subprocess.run(
        [
            sys.executable, str(script),
            "--trajectory-dir", str(source),
            "--current-t", "4",
            "--artifact-dir", str(artifact),
            "--calibration", str(calibration),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert failure.returncode == 2
    assert json.loads(failure.stderr)["status"] == "fail"
