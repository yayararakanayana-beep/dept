from __future__ import annotations

import hashlib
import io
import json
import zipfile
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np


class RelationFieldPredictionCoordinatesP2Error(ValueError):
    """P2契約、親P1成果物、座標または検証結果の不整合。"""


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_hash(root: Path) -> str:
    rows = [
        (p.relative_to(root).as_posix(), sha256_file(p), p.stat().st_size)
        for p in sorted(root.rglob("*")) if p.is_file()
    ]
    return canonical_digest(rows)


def write_deterministic_npz(path: Path, arrays: Mapping[str, np.ndarray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(arrays):
            buffer = io.BytesIO()
            np.save(buffer, np.asarray(arrays[name]), allow_pickle=False)
            info = zipfile.ZipInfo(f"{name}.npy", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, buffer.getvalue(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def load_npz(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as loaded:
        return {name: loaded[name].copy() for name in loaded.files}


def manifest_entries(root: Path, *, manifest_name: str = "manifest.json") -> list[dict[str, Any]]:
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
        }
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.relative_to(root).as_posix() != manifest_name
    ]


def write_manifest(root: Path, artifact_version: str) -> None:
    dump_json(root / "manifest.json", {
        "artifact_version": artifact_version,
        "hash_algorithm": "sha256",
        "files": manifest_entries(root),
    })


def verify_manifest(root: Path) -> None:
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise RelationFieldPredictionCoordinatesP2Error(f"manifest missing: {root}")
    manifest = load_json(manifest_path)
    expected: set[str] = set()
    for raw in manifest.get("files", []):
        relative = str(raw.get("path", ""))
        if not relative or relative == "manifest.json" or relative in expected:
            raise RelationFieldPredictionCoordinatesP2Error("manifest contains invalid path")
        expected.add(relative)
        path = root / relative
        if not path.is_file():
            raise RelationFieldPredictionCoordinatesP2Error(f"manifest file missing: {relative}")
        if path.stat().st_size != int(raw.get("size_bytes", -1)):
            raise RelationFieldPredictionCoordinatesP2Error(f"manifest size mismatch: {relative}")
        if sha256_file(path) != raw.get("sha256"):
            raise RelationFieldPredictionCoordinatesP2Error(f"manifest hash mismatch: {relative}")
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*") if path.is_file() and path != manifest_path
    }
    if actual != expected:
        raise RelationFieldPredictionCoordinatesP2Error("manifest file set mismatch")


def validate_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("contract_version") != "relation_field_prediction_coordinates_p2_v1":
        raise RelationFieldPredictionCoordinatesP2Error("unsupported P2 contract")
    scope = contract.get("scope", {})
    if scope.get("coordinate_builder_implementation") is not True:
        raise RelationFieldPredictionCoordinatesP2Error("P2 builder scope changed")
    if scope.get("independent_validator_implementation") is not True:
        raise RelationFieldPredictionCoordinatesP2Error("P2 independent validator scope changed")
    for key in ("precursor_validity_evaluation", "future_prediction_model_implementation", "action_evaluation_or_selection", "single_scalar_danger_score"):
        if scope.get(key) is not False:
            raise RelationFieldPredictionCoordinatesP2Error(f"P2 forbidden scope enabled: {key}")
    logic = contract.get("logic", {})
    if logic.get("AND") != "minimum" or logic.get("OR") != "maximum" or logic.get("NOT") != "sign_negation":
        raise RelationFieldPredictionCoordinatesP2Error("P2 logical composition changed")
    if contract.get("input", {}).get("required_parent_contract_version") != "relation_field_prediction_state_p1":
        raise RelationFieldPredictionCoordinatesP2Error("P2 parent contract changed")


def expand_registry(registry: Mapping[str, Any]) -> dict[str, Any]:
    value = dict(registry)
    if "entries" in value:
        return value
    columns = value.get("entry_columns")
    rows = value.get("entries_compact")
    defaults = value.get("entry_defaults", {})
    if not isinstance(columns, list) or not isinstance(rows, list):
        return value
    entries: list[dict[str, Any]] = []
    for raw in rows:
        if not isinstance(raw, list) or len(raw) != len(columns):
            raise RelationFieldPredictionCoordinatesP2Error("P2 compact registry row mismatch")
        entry = dict(defaults)
        entry.update(zip((str(column) for column in columns), raw))
        entries.append(entry)
    value["entries"] = entries
    return value


def validate_registry(registry: Mapping[str, Any]) -> None:
    registry = expand_registry(registry)
    if registry.get("registry_version") != "relation_field_prediction_coordinates_p2_registry_v1":
        raise RelationFieldPredictionCoordinatesP2Error("P2 registry version mismatch")
    if registry.get("extensible") is not True or registry.get("single_scalar_risk_score_forbidden") is not True:
        raise RelationFieldPredictionCoordinatesP2Error("P2 registry closure changed")
    entries = registry.get("entries")
    if not isinstance(entries, list) or not entries:
        raise RelationFieldPredictionCoordinatesP2Error("P2 registry is empty")
    ids = [str(row.get("coordinate_id", "")) for row in entries]
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        raise RelationFieldPredictionCoordinatesP2Error("P2 coordinate IDs must be unique")
    required = {
        "p2.risk.overconvergence.structure_margin",
        "p2.risk.fixation.structure_margin",
        "p2.risk.divergence.structure_margin",
        "p2.risk.recovery_margin_reduction.structure_margin",
    }
    if not required <= set(ids):
        raise RelationFieldPredictionCoordinatesP2Error("P2 primary risk coordinates are incomplete")


def load_contract(path: str | Path) -> dict[str, Any]:
    value = load_json(Path(path))
    validate_contract(value)
    return value


def load_registry(path: str | Path) -> dict[str, Any]:
    value = expand_registry(load_json(Path(path)))
    validate_registry(value)
    return value


def p1_origin_paths(p1_root: Path) -> tuple[dict[str, Any], list[tuple[int, Path, Path]]]:
    verify_manifest(p1_root)
    contract = load_json(p1_root / "contract.json")
    if contract.get("contract_version") != "relation_field_prediction_state_p1":
        raise RelationFieldPredictionCoordinatesP2Error("unsupported parent P1 contract")
    validation = load_json(p1_root / str(contract["storage"]["series_validation_file"]))
    if validation.get("p1_series_gate") != "passed":
        raise RelationFieldPredictionCoordinatesP2Error("parent P1 validation gate is not passed")
    storage = contract["storage"]
    index = load_json(p1_root / str(storage["series_index_file"]))
    rows = index.get("rows", [])
    result: list[tuple[int, Path, Path]] = []
    for row in rows:
        origin_t = int(row["origin_t"])
        name = str(storage["origin_name_format"]).format(origin_t=origin_t)
        origin = p1_root / str(storage["origin_container_dir"]) / name
        state = origin / str(storage["state_dir"])
        if not origin.is_dir() or not state.is_dir():
            raise RelationFieldPredictionCoordinatesP2Error(f"P1 origin is missing: {origin_t}")
        result.append((origin_t, origin, state))
    if not result or [x[0] for x in result] != sorted({x[0] for x in result}):
        raise RelationFieldPredictionCoordinatesP2Error("P1 origins are empty or unordered")
    return contract, result


def coordinate_arrays_from_records(records: Iterable[Mapping[str, Any]]) -> dict[str, np.ndarray]:
    arrays: dict[str, np.ndarray] = {}
    for row in records:
        if row.get("availability") != "available":
            continue
        cid = str(row["coordinate_id"])
        for part in ("lower", "center", "upper"):
            arrays[f"{cid}__{part}"] = np.ascontiguousarray(np.asarray(row[part], dtype=np.float64))
    return arrays


def arrays_close(expected: Mapping[str, np.ndarray], actual: Mapping[str, np.ndarray], name: str) -> None:
    if set(expected) != set(actual):
        raise RelationFieldPredictionCoordinatesP2Error(f"{name} array key mismatch")
    for key in expected:
        left = np.asarray(expected[key])
        right = np.asarray(actual[key])
        if left.shape != right.shape or not np.allclose(left, right, atol=1e-12, rtol=1e-12, equal_nan=False):
            raise RelationFieldPredictionCoordinatesP2Error(f"{name} array value mismatch: {key}")
