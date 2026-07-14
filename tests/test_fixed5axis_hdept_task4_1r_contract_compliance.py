from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
for path in (ROOT / "scripts", ROOT / "tests"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from fixed5axis_hdept_bridge_task2.builder import build_observation  # noqa: E402
from fixed5axis_hdept_bridge_task2.contracts import (  # noqa: E402
    DEFAULT_MEANING_PATCH,
    Fixed5AxisHDEPTBridgeError,
    load_evidence_map,
    load_feature_registry,
)
from fixed5axis_hdept_bridge_task3.validator import validate_observation  # noqa: E402
from test_fixed5axis_hdept_observation_bridge_rc1 import _make_canonical  # noqa: E402

REGISTRY_PATH = ROOT / "configs" / "fixed5axis_hdept_feature_registry_rc1.json"


def _dump(path: Path, value: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return path


def _strict_calibration(
    path: Path,
    *,
    non_scoring: set[str] | None = None,
    omit_new_fields: bool = False,
    synthesize_numeric_for_non_scoring: bool = False,
    synthesize_numeric_for_contract_non_scoring: bool = False,
) -> Path:
    registry = load_feature_registry(REGISTRY_PATH)
    non_scoring = set() if non_scoring is None else set(non_scoring)
    centers: list[float | None] = []
    scales: list[float | None] = []
    lower: list[float | None] = []
    upper: list[float | None] = []
    for entry in registry["features"]:
        feature_id = entry["id"]
        contract_scoring = bool(entry.get("score", True)) and float(entry["cap"]) > 0.0
        calibration_non_scoring = feature_id in non_scoring
        force_numeric = (
            calibration_non_scoring and synthesize_numeric_for_non_scoring
        ) or (
            (not contract_scoring)
            and synthesize_numeric_for_contract_non_scoring
            and feature_id == "mode_count"
        )
        if force_numeric or (contract_scoring and not calibration_non_scoring):
            centers.append(0.0)
            scales.append(1.0)
            lower.append(-3.0)
            upper.append(3.0)
        else:
            centers.append(None)
            scales.append(None)
            lower.append(None)
            upper.append(None)
    value = {
        "calibration_version": "task4_1r_strict_test_calibration",
        "feature_registry_hash": hashlib.sha256(REGISTRY_PATH.read_bytes()).hexdigest(),
        "feature_order": [entry["id"] for entry in registry["features"]],
        "center": centers,
        "scale": scales,
        "clip_lower": lower,
        "clip_upper": upper,
        "fit_dataset_ids": ["task4_1r_contract_test"],
        "fit_trajectory_ids_hash": "a" * 64,
        "fit_time_boundary": {"maximum_t": 4, "future_suffix_used": False},
        "normalization_method": "zscore",
        "creation_code_hash": "b" * 64,
        "non_scoring_feature_ids": sorted(non_scoring),
        "meaning_patch_hash": hashlib.sha256(DEFAULT_MEANING_PATCH.read_bytes()).hexdigest(),
    }
    if omit_new_fields:
        value.pop("non_scoring_feature_ids")
        value.pop("meaning_patch_hash")
    return _dump(path, value)


def _load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_task4_1r_patch_withholds_invalid_mode_evidence_and_revises_axes() -> None:
    registry = load_feature_registry(REGISTRY_PATH)
    feature_by_id = {entry["id"]: entry for entry in registry["features"]}
    for feature_id in ("mode_count", "cluster_balance"):
        assert feature_by_id[feature_id]["score"] is False
        assert feature_by_id[feature_id]["cap"] == 0.0

    evidence = load_evidence_map()
    exploration = evidence["base_components"]["Exploration"]
    assert "mode_count" not in exploration["positive"]
    assert "cluster_balance" not in exploration["positive"]
    assert "jsd_velocity" not in exploration["positive"]
    assert "wasserstein_velocity" not in exploration["positive"]

    coherence = evidence["base_components"]["Coherence"]
    assert "tail_mass" not in coherence["negative"]
    assert "trajectory_curvature" not in coherence["negative"]
    assert "cluster_balance" not in coherence["positive"]

    structural = evidence["h11_axes"]["StructuralDiversity"]
    assert structural["construction"] == {"component": "Diversity", "type": "base_component"}
    assert structural["maximum_scientific_status"] == "LIMITED"
    assert evidence["h11_axes"]["Exploration"]["maximum_scientific_status"] == "LIMITED"
    assert evidence["h11_axes"]["Coherence"]["maximum_scientific_status"] == "LIMITED"


def test_calibration_specific_constant_is_excluded_but_raw_feature_is_preserved(tmp_path: Path) -> None:
    source = _make_canonical(tmp_path / "canonical")
    full_calibration = _strict_calibration(tmp_path / "full.json")
    constant_calibration = _strict_calibration(tmp_path / "constant.json", non_scoring={"entropy"})

    full_artifact = build_observation(source, 4, tmp_path / "full_artifact", calibration_path=full_calibration)
    constant_artifact = build_observation(source, 4, tmp_path / "constant_artifact", calibration_path=constant_calibration)

    features = _load(constant_artifact / "features.json")["features"]
    entropy_record = next(item for item in features if item["feature_id"] == "entropy")
    assert entropy_record["available"] is True
    assert entropy_record["value"] is not None

    full_observation = _load(full_artifact / "m_observation.json")
    constant_observation = _load(constant_artifact / "m_observation.json")
    assert (
        constant_observation["h11"]["Exploration"]["evidence_coverage"]
        < full_observation["h11"]["Exploration"]["evidence_coverage"]
    )
    assert (
        constant_observation["h11"]["StructuralDiversity"]["evidence_coverage"]
        < full_observation["h11"]["StructuralDiversity"]["evidence_coverage"]
    )

    assert validate_observation(source, 4, full_artifact, calibration_path=full_calibration)["status"] == "pass"
    assert validate_observation(source, 4, constant_artifact, calibration_path=constant_calibration)["status"] == "pass"


def test_numeric_evidence_for_calibration_non_scoring_constant_is_rejected(tmp_path: Path) -> None:
    source = _make_canonical(tmp_path / "canonical")
    calibration = _strict_calibration(
        tmp_path / "bad.json",
        non_scoring={"entropy"},
        synthesize_numeric_for_non_scoring=True,
    )
    with pytest.raises(Fixed5AxisHDEPTBridgeError, match="non-scoring constant entropy must have null"):
        build_observation(source, 4, tmp_path / "artifact", calibration_path=calibration)


def test_numeric_evidence_for_contract_non_scoring_mode_feature_is_rejected(tmp_path: Path) -> None:
    source = _make_canonical(tmp_path / "canonical")
    calibration = _strict_calibration(
        tmp_path / "bad_mode.json",
        synthesize_numeric_for_contract_non_scoring=True,
    )
    with pytest.raises(Fixed5AxisHDEPTBridgeError, match="contract non-scoring feature mode_count must have null"):
        build_observation(source, 4, tmp_path / "artifact", calibration_path=calibration)


def test_production_calibration_requires_task4_1r_fields(tmp_path: Path) -> None:
    source = _make_canonical(tmp_path / "canonical")
    calibration = _strict_calibration(tmp_path / "missing.json", omit_new_fields=True)
    with pytest.raises(Fixed5AxisHDEPTBridgeError, match="calibration missing fields"):
        build_observation(source, 4, tmp_path / "artifact", calibration_path=calibration)


def test_task3_rejects_artifact_when_different_constant_exclusion_contract_is_supplied(tmp_path: Path) -> None:
    source = _make_canonical(tmp_path / "canonical")
    full_calibration = _strict_calibration(tmp_path / "full.json")
    constant_calibration = _strict_calibration(tmp_path / "constant.json", non_scoring={"entropy"})
    artifact = build_observation(source, 4, tmp_path / "artifact", calibration_path=full_calibration)
    with pytest.raises(ValueError):
        validate_observation(source, 4, artifact, calibration_path=constant_calibration)
