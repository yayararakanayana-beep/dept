"""Task 2 共通契約、固定値、JSON、校正読込み。"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BRIDGE_CONTRACT = ROOT / "configs" / "fixed5axis_hdept_observation_bridge_rc1_contract.json"
DEFAULT_FEATURE_REGISTRY = ROOT / "configs" / "fixed5axis_hdept_feature_registry_rc1.json"
DEFAULT_EVIDENCE_MAP = ROOT / "configs" / "fixed5axis_hdept_h11_evidence_map_rc1.json"
DEFAULT_MEANING_PATCH = ROOT / "configs" / "fixed5axis_hdept_task4_1r_contract_patch_rc1.json"
DEFAULT_FIXED5_CONTRACT = ROOT / "configs" / "fixed5axis_gk_rc1_contract.json"
DEFAULT_SCHEMA = ROOT / "schemas" / "fixed5axis_hdept_observation_bridge_rc1.schema.json"

AXIS_NAMES = ("resource_slack", "information_quality", "pressure", "exploration_room", "reversibility")
AXIS_BINS = (0.0, 0.25, 0.5, 0.75, 1.0)
GT_SHAPE = (5, 5, 5, 5, 5)
CELL_COUNT = 3125
OUTPUT_FILES = ("identity.json", "features.json", "m_observation.json", "audit.json", "provenance.json")


class Fixed5AxisHDEPTBridgeError(ValueError):
    """固定5軸上位観測翻訳層 Task 2 の契約違反。"""


def _json_load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n").encode("utf-8")


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_json_bytes(value))


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bool_text(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def _finite_float(value: Any, name: str) -> float:
    if isinstance(value, bool):
        raise Fixed5AxisHDEPTBridgeError(f"{name} must be a finite number")
    result = float(value)
    if not math.isfinite(result):
        raise Fixed5AxisHDEPTBridgeError(f"{name} must be a finite number")
    return result


def _sigmoid(value: float) -> float:
    if value >= 0.0:
        exp = math.exp(-value)
        return 1.0 / (1.0 + exp)
    exp = math.exp(value)
    return exp / (1.0 + exp)


def load_meaning_patch(path: str | Path = DEFAULT_MEANING_PATCH) -> dict[str, Any]:
    value = _json_load(Path(path))
    if value.get("patch_id") != "fixed5axis_hdept_task4_1r_contract_patch_rc1":
        raise Fixed5AxisHDEPTBridgeError("unsupported Task 4-1R meaning patch")
    if value.get("status") != "frozen_for_targeted_task1_task2_task3_revision":
        raise Fixed5AxisHDEPTBridgeError("Task 4-1R meaning patch is not frozen")
    return value


def _apply_registry_patch(value: Mapping[str, Any], patch: Mapping[str, Any]) -> dict[str, Any]:
    output = copy.deepcopy(dict(value))
    features = output.get("features")
    if not isinstance(features, list):
        raise Fixed5AxisHDEPTBridgeError("feature registry features must be a list")
    by_id = {str(entry.get("id", "")): entry for entry in features}
    overrides = patch.get("registry_feature_overrides", {})
    if not isinstance(overrides, dict):
        raise Fixed5AxisHDEPTBridgeError("registry_feature_overrides must be an object")
    unknown = sorted(set(overrides) - set(by_id))
    if unknown:
        raise Fixed5AxisHDEPTBridgeError(f"meaning patch references unknown registry features: {unknown}")
    for feature_id, fields in overrides.items():
        if not isinstance(fields, dict):
            raise Fixed5AxisHDEPTBridgeError(f"registry override for {feature_id} must be an object")
        by_id[feature_id].update(copy.deepcopy(fields))
    output["registry_version"] = patch["effective_registry_version"]
    output["meaning_patch_id"] = patch["patch_id"]
    output["meaning_patch_version"] = patch["patch_version"]
    output["status"] = "frozen_for_task4_1r_builder_implementation"
    return output


def _apply_evidence_patch(value: Mapping[str, Any], patch: Mapping[str, Any]) -> dict[str, Any]:
    output = copy.deepcopy(dict(value))
    components = output.get("base_components")
    axes = output.get("h11_axes")
    if not isinstance(components, dict) or not isinstance(axes, dict):
        raise Fixed5AxisHDEPTBridgeError("H11 evidence map structure is invalid")
    component_replacements = patch.get("base_component_replacements", {})
    if not isinstance(component_replacements, dict):
        raise Fixed5AxisHDEPTBridgeError("base_component_replacements must be an object")
    unknown_components = sorted(set(component_replacements) - set(components))
    if unknown_components:
        raise Fixed5AxisHDEPTBridgeError(f"meaning patch references unknown components: {unknown_components}")
    for component_id, replacement in component_replacements.items():
        if not isinstance(replacement, dict) or set(replacement) != {"positive", "negative"}:
            raise Fixed5AxisHDEPTBridgeError(f"component replacement for {component_id} is invalid")
        components[component_id] = copy.deepcopy(replacement)
    axis_overrides = patch.get("h11_axis_overrides", {})
    if not isinstance(axis_overrides, dict):
        raise Fixed5AxisHDEPTBridgeError("h11_axis_overrides must be an object")
    unknown_axes = sorted(set(axis_overrides) - set(axes))
    if unknown_axes:
        raise Fixed5AxisHDEPTBridgeError(f"meaning patch references unknown H11 axes: {unknown_axes}")
    for axis_id, fields in axis_overrides.items():
        if not isinstance(fields, dict):
            raise Fixed5AxisHDEPTBridgeError(f"H11 override for {axis_id} must be an object")
        axes[axis_id].update(copy.deepcopy(fields))
    output["map_version"] = patch["effective_evidence_map_version"]
    output["meaning_patch_id"] = patch["patch_id"]
    output["meaning_patch_version"] = patch["patch_version"]
    output["status"] = "frozen_for_task4_1r_builder_implementation"
    return output


def load_bridge_contract(path: str | Path = DEFAULT_BRIDGE_CONTRACT) -> dict[str, Any]:
    value = _json_load(Path(path))
    if value.get("contract_version") != "fixed5axis_hdept_observation_bridge_rc1":
        raise Fixed5AxisHDEPTBridgeError("unsupported bridge contract_version")
    if value.get("status") != "frozen_for_builder_implementation":
        raise Fixed5AxisHDEPTBridgeError("bridge contract is not frozen for builder implementation")
    return value


def load_feature_registry(
    path: str | Path = DEFAULT_FEATURE_REGISTRY,
    *,
    meaning_patch_path: str | Path = DEFAULT_MEANING_PATCH,
) -> dict[str, Any]:
    value = _json_load(Path(path))
    if value.get("registry_id") != "fixed5axis_hdept_feature_registry_rc1":
        raise Fixed5AxisHDEPTBridgeError("unsupported feature registry")
    value = _apply_registry_patch(value, load_meaning_patch(meaning_patch_path))
    features = value.get("features")
    if not isinstance(features, list) or len(features) != 47:
        raise Fixed5AxisHDEPTBridgeError("feature registry must contain exactly 47 features")
    ids = [str(item.get("id", "")) for item in features]
    if len(set(ids)) != 47 or any(not item for item in ids):
        raise Fixed5AxisHDEPTBridgeError("feature registry IDs must be non-empty and unique")
    return value


def load_evidence_map(
    path: str | Path = DEFAULT_EVIDENCE_MAP,
    *,
    meaning_patch_path: str | Path = DEFAULT_MEANING_PATCH,
) -> dict[str, Any]:
    value = _json_load(Path(path))
    if value.get("map_id") != "fixed5axis_hdept_h11_evidence_map_rc1":
        raise Fixed5AxisHDEPTBridgeError("unsupported H11 evidence map")
    value = _apply_evidence_patch(value, load_meaning_patch(meaning_patch_path))
    axes = value.get("axis_order")
    if not isinstance(axes, list) or len(axes) != 11 or set(axes) != set(value.get("h11_axes", {})):
        raise Fixed5AxisHDEPTBridgeError("H11 evidence map must define the ordered 11 axes")
    return value


def load_fixed5_contract(path: str | Path = DEFAULT_FIXED5_CONTRACT) -> dict[str, Any]:
    value = _json_load(Path(path))
    if value.get("contract_version") != "fixed5axis_gk_rc1":
        raise Fixed5AxisHDEPTBridgeError("unsupported fixed5 G/K contract")
    axes = value.get("axes", {})
    if tuple(axes.get("order", ())) != AXIS_NAMES:
        raise Fixed5AxisHDEPTBridgeError("fixed5 axis order mismatch")
    if tuple(float(item) for item in axes.get("bins", ())) != AXIS_BINS:
        raise Fixed5AxisHDEPTBridgeError("fixed5 axis bins mismatch")
    if tuple(int(item) for item in axes.get("shape", ())) != GT_SHAPE:
        raise Fixed5AxisHDEPTBridgeError("fixed5 G_t shape mismatch")
    return value


def load_calibration(
    path: str | Path,
    registry: Mapping[str, Any],
    *,
    registry_hash: str,
    meaning_patch_path: str | Path = DEFAULT_MEANING_PATCH,
) -> dict[str, Any]:
    calibration_path = Path(path)
    value = _json_load(calibration_path)
    required = {
        "calibration_version",
        "feature_registry_hash",
        "feature_order",
        "center",
        "scale",
        "clip_lower",
        "clip_upper",
        "fit_dataset_ids",
        "fit_trajectory_ids_hash",
        "fit_time_boundary",
        "normalization_method",
        "creation_code_hash",
    }
    fixture_only = value.get("calibration_version") == "task2_test_fixture_only"
    if fixture_only:
        value.setdefault("non_scoring_feature_ids", [])
        value.setdefault("meaning_patch_hash", _sha256_file(Path(meaning_patch_path)))
    else:
        required.update({"non_scoring_feature_ids", "meaning_patch_hash"})
    missing = sorted(required - set(value))
    if missing:
        raise Fixed5AxisHDEPTBridgeError(f"calibration missing fields: {missing}")
    ids = [entry["id"] for entry in registry["features"]]
    if value["feature_registry_hash"] != registry_hash or value["feature_order"] != ids:
        raise Fixed5AxisHDEPTBridgeError("calibration feature registry identity mismatch")
    expected_patch_hash = _sha256_file(Path(meaning_patch_path))
    if value["meaning_patch_hash"] != expected_patch_hash:
        raise Fixed5AxisHDEPTBridgeError("calibration meaning patch identity mismatch")
    if value["normalization_method"] not in {"zscore", "robust_zscore"}:
        raise Fixed5AxisHDEPTBridgeError("unsupported calibration normalization_method")
    for key in ("center", "scale", "clip_lower", "clip_upper"):
        if not isinstance(value[key], list) or len(value[key]) != len(ids):
            raise Fixed5AxisHDEPTBridgeError(f"calibration {key} length mismatch")
    non_scoring_raw = value["non_scoring_feature_ids"]
    if not isinstance(non_scoring_raw, list) or any(not isinstance(item, str) for item in non_scoring_raw):
        raise Fixed5AxisHDEPTBridgeError("calibration non_scoring_feature_ids must be a string list")
    if len(non_scoring_raw) != len(set(non_scoring_raw)):
        raise Fixed5AxisHDEPTBridgeError("calibration non_scoring_feature_ids must be unique")
    unknown_non_scoring = sorted(set(non_scoring_raw) - set(ids))
    if unknown_non_scoring:
        raise Fixed5AxisHDEPTBridgeError(f"calibration references unknown non-scoring features: {unknown_non_scoring}")
    non_scoring = set(non_scoring_raw)
    for index, entry in enumerate(registry["features"]):
        feature_id = entry["id"]
        contract_scoring = bool(entry.get("score", True)) and float(entry["cap"]) > 0.0
        calibration_non_scoring = feature_id in non_scoring
        if calibration_non_scoring:
            if any(value[key][index] is not None for key in ("center", "scale", "clip_lower", "clip_upper")):
                raise Fixed5AxisHDEPTBridgeError(
                    f"calibration non-scoring constant {feature_id} must have null numeric calibration fields"
                )
            entry["score"] = False
            entry["calibration_non_scoring_constant"] = True
            continue
        if not contract_scoring:
            if any(value[key][index] is not None for key in ("center", "scale", "clip_lower", "clip_upper")):
                raise Fixed5AxisHDEPTBridgeError(
                    f"contract non-scoring feature {feature_id} must have null numeric calibration fields"
                )
            continue
        center = _finite_float(value["center"][index], f"center[{index}]")
        scale = _finite_float(value["scale"][index], f"scale[{index}]")
        lower = _finite_float(value["clip_lower"][index], f"clip_lower[{index}]")
        upper = _finite_float(value["clip_upper"][index], f"clip_upper[{index}]")
        if scale <= 0.0 or upper < lower:
            raise Fixed5AxisHDEPTBridgeError("invalid scoring calibration scale or clip bounds")
        value["center"][index], value["scale"][index] = center, scale
        value["clip_lower"][index], value["clip_upper"][index] = lower, upper
    value["non_scoring_feature_ids"] = sorted(non_scoring)
    value["calibration_file_hash"] = _sha256_file(calibration_path)
    return value
