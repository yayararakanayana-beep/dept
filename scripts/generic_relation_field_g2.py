"""汎用関係場 G2: 固定5軸接続層と識別子付き成果物基盤。

既存の固定5軸 G_t/K_t と RF-2/RF-6 を変更せず、固定条件を構造
プロファイルへ隔離する。予測、意味解釈、作用選択は行わない。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import itertools
import json
import math
import os
import shutil
import tempfile
import zipfile
from collections import deque
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "configs" / "generic_relation_field_g2_contract.json"
DEFAULT_FIXED_PROFILE = ROOT / "configs" / "fixed5axis_relation_structure_g2.json"


class GenericRelationFieldG2Error(ValueError):
    """G2構造、接続層、成果物契約の不整合。"""


def _json_load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _json_dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_repo_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise GenericRelationFieldG2Error("contract source path must stay inside repository")
    return ROOT / path


def _write_deterministic_npz(path: Path, arrays: Mapping[str, np.ndarray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(arrays):
            array = np.asarray(arrays[name])
            if array.dtype.hasobject:
                raise GenericRelationFieldG2Error(f"object array is forbidden: {name}")
            buffer = io.BytesIO()
            np.save(buffer, array, allow_pickle=False)
            info = zipfile.ZipInfo(f"{name}.npy", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(
                info,
                buffer.getvalue(),
                compress_type=zipfile.ZIP_DEFLATED,
                compresslevel=9,
            )


def _load_npz(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as loaded:
        return {name: loaded[name].copy() for name in loaded.files}


def _array_content_hash(arrays: Mapping[str, np.ndarray]) -> str:
    digest = hashlib.sha256()
    for name in sorted(arrays):
        array = np.ascontiguousarray(np.asarray(arrays[name]))
        if array.dtype.hasobject:
            raise GenericRelationFieldG2Error(f"object array is forbidden: {name}")
        digest.update(name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(array.dtype.str.encode("ascii"))
        digest.update(b"\0")
        digest.update(_canonical_json(list(array.shape)))
        digest.update(b"\0")
        digest.update(array.tobytes(order="C"))
        digest.update(b"\0")
    return digest.hexdigest()


def _manifest_entries(root: Path, *, exclude: Iterable[str] = ()) -> list[dict[str, Any]]:
    excluded = set(exclude)
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": _sha256_file(path),
            "size_bytes": path.stat().st_size,
        }
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.relative_to(root).as_posix() not in excluded
    ]


def _write_manifest(root: Path, artifact_version: str) -> None:
    _json_dump(
        root / "manifest.json",
        {
            "artifact_version": artifact_version,
            "hash_algorithm": "sha256",
            "files": _manifest_entries(root, exclude={"manifest.json"}),
        },
    )


def _verify_manifest(root: Path) -> None:
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise GenericRelationFieldG2Error("manifest.json is missing")
    manifest = _json_load(manifest_path)
    expected: set[str] = set()
    for entry in manifest.get("files", []):
        relative = str(entry.get("path", ""))
        if not relative or relative in expected:
            raise GenericRelationFieldG2Error("manifest contains an invalid path")
        expected.add(relative)
        path = root / relative
        if not path.is_file():
            raise GenericRelationFieldG2Error(f"manifest file missing: {relative}")
        if path.stat().st_size != int(entry.get("size_bytes", -1)):
            raise GenericRelationFieldG2Error(f"manifest size mismatch: {relative}")
        if _sha256_file(path) != entry.get("sha256"):
            raise GenericRelationFieldG2Error(f"manifest hash mismatch: {relative}")
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    if actual != expected:
        raise GenericRelationFieldG2Error("manifest file set mismatch")


def load_contract(path: str | Path = DEFAULT_CONTRACT) -> dict[str, Any]:
    contract = _json_load(Path(path))
    validate_contract(contract, require_source_files=True)
    return contract


def validate_contract(
    contract: Mapping[str, Any],
    *,
    require_source_files: bool = True,
) -> None:
    if contract.get("contract_version") != "generic_relation_field_g2":
        raise GenericRelationFieldG2Error("unsupported G2 contract_version")
    production = contract.get("production_scope", {})
    if production.get("topology_is_static_within_kt") is not True:
        raise GenericRelationFieldG2Error("G2 production topology must be static within K_t")
    if production.get("dynamic_topology_correspondence_implemented") is not False:
        raise GenericRelationFieldG2Error("G2 must not claim dynamic topology correspondence")
    if production.get("prediction_model_implemented") is not False:
        raise GenericRelationFieldG2Error("G2 must not claim a prediction model")
    incidence = contract.get("incidence", {})
    if incidence.get("edge_source_value") != -1.0 or incidence.get("edge_target_value") != 1.0:
        raise GenericRelationFieldG2Error("incidence sign convention mismatch")
    face_signs = contract.get("face_orientation", {}).get("elementary_square_edge_signs")
    if face_signs != [1, 1, -1, -1]:
        raise GenericRelationFieldG2Error("elementary-square face orientation mismatch")
    field = contract.get("field_records", {})
    if not field.get("required_fields") or not field.get("allowed_stages"):
        raise GenericRelationFieldG2Error("field-record contract is incomplete")
    if field.get("fixed_length_primary_storage_forbidden") is not True:
        raise GenericRelationFieldG2Error("fixed-length primary storage must remain forbidden")
    paths = contract.get("source_contract_paths", [])
    if not paths or len(paths) != len(set(str(value) for value in paths)):
        raise GenericRelationFieldG2Error("source contract paths must be unique and non-empty")
    for value in paths:
        source = _safe_repo_path(str(value))
        if require_source_files and not source.is_file():
            raise GenericRelationFieldG2Error(f"source contract is missing: {value}")


def load_fixed_profile(path: str | Path = DEFAULT_FIXED_PROFILE) -> dict[str, Any]:
    profile = _json_load(Path(path))
    validate_fixed_profile(profile)
    return _resolve_fixed_profile(profile)


def validate_fixed_profile(profile: Mapping[str, Any]) -> None:
    if profile.get("profile_id") != "fixed5axis_relation_structure_g2":
        raise GenericRelationFieldG2Error("unsupported fixed structure profile")
    if profile.get("structure_class") != "oriented_finite_cell_complex":
        raise GenericRelationFieldG2Error("fixed profile structure class mismatch")
    if profile.get("topology_time_policy") != "static_within_kt":
        raise GenericRelationFieldG2Error("fixed profile topology time policy mismatch")
    capabilities = profile.get("capabilities", {})
    if capabilities.get("dynamic_topology_correspondence") is not False:
        raise GenericRelationFieldG2Error("fixed profile must reject topology correspondence")
    for item in profile.get("source_contracts", {}).values():
        source = _safe_repo_path(str(item.get("path", "")))
        value = _json_load(source)
        if value.get("contract_version") != item.get("contract_version"):
            raise GenericRelationFieldG2Error(f"source contract version mismatch: {source.name}")


def _resolve_fixed_profile(profile: Mapping[str, Any]) -> dict[str, Any]:
    sources = profile["source_contracts"]
    gk = _json_load(_safe_repo_path(sources["gk"]["path"]))
    grid = _json_load(_safe_repo_path(sources["grid"]["path"]))
    transition = _json_load(_safe_repo_path(sources["transition_flow"]["path"]))
    faces = _json_load(_safe_repo_path(sources["faces"]["path"]))
    axes = gk["axes"]
    order = list(axes["order"])
    bins = [float(value) for value in axes["bins"]]
    shape = [int(value) for value in axes["shape"]]
    if not order or len(order) != len(shape) or len(set(order)) != len(order):
        raise GenericRelationFieldG2Error("resolved fixed profile axes are invalid")
    if any(size != len(bins) for size in shape):
        raise GenericRelationFieldG2Error("resolved fixed profile bins and shape mismatch")
    complex_contract = faces["cubical_complex"]
    resolved = dict(profile)
    resolved["axes"] = {
        "order": order,
        "bins": bins,
        "shape": shape,
        "flatten_order": grid["axes"]["flatten_order"],
    }
    resolved["expected_counts"] = {
        "axis_count": len(order),
        "cell_count": int(axes["cell_count"]),
        "edge_count": int(grid["connectivity"]["undirected_edge_count"]),
        "directed_neighbor_count": int(grid["connectivity"]["directed_neighbor_count"]),
        "face_count": int(complex_contract["face_count"]),
        "face_edge_membership_count": (
            int(complex_contract["face_count"])
            * int(complex_contract["face_boundary_entries"])
        ),
    }
    resolved["edge_policy"] = {
        "orientation": grid["connectivity"]["canonical_edge_orientation"],
        "topological_length": float(grid["connectivity"]["topological_edge_length"]),
        "coordinate_length": float(grid["connectivity"]["coordinate_edge_length"]),
        "transport_cost": float(transition["solver"]["coordinate_edge_cost"]),
        "source_incidence": float(grid["operators"]["incidence"]["source_value"]),
        "target_incidence": float(grid["operators"]["incidence"]["target_value"]),
    }
    if resolved["expected_counts"]["cell_count"] != math.prod(shape):
        raise GenericRelationFieldG2Error("resolved fixed profile cell count mismatch")
    return resolved


def _source_contract_hashes(contract: Mapping[str, Any]) -> dict[str, str]:
    return {
        str(value): _sha256_bytes(_canonical_json(_json_load(_safe_repo_path(str(value)))))
        for value in contract["source_contract_paths"]
    }


def _axis_registry(profile: Mapping[str, Any]) -> dict[str, Any]:
    axes = profile["axes"]
    bins = [float(value) for value in axes["bins"]]
    records = []
    for order, axis_id in enumerate(axes["order"]):
        records.append(
            {
                "axis_id": str(axis_id),
                "axis_order": order,
                "display_name": str(axis_id),
                "orientation": "lower_to_upper_bin",
                "bin_ids": [f"{axis_id}/bin/{index}" for index in range(len(bins))],
                "bin_values": bins,
                "normalization_definition": "fixed_profile_coordinate",
            }
        )
    return {
        "registry_version": "generic_relation_field_axis_registry_g2",
        "identity_field": "axis_id",
        "records": records,
    }


def _boundary_payload(
    axis_registry: Mapping[str, Any],
    cell_axis_indices: np.ndarray,
    shape: Sequence[int],
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    records: list[dict[str, Any]] = []
    memberships: list[np.ndarray] = []
    for axis_ordinal, axis in enumerate(axis_registry["records"]):
        for side, index in (("lower", 0), ("upper", int(shape[axis_ordinal]) - 1)):
            boundary_id = f"{axis['axis_id']}/{side}"
            records.append(
                {
                    "boundary_id": boundary_id,
                    "axis_id": axis["axis_id"],
                    "side": side,
                    "coordinate_bin_index": index,
                    "risk_semantics": "unassigned",
                }
            )
            memberships.append(np.flatnonzero(cell_axis_indices[:, axis_ordinal] == index).astype(np.int64))
    indptr = np.zeros(len(memberships) + 1, dtype=np.int64)
    for index, values in enumerate(memberships):
        indptr[index + 1] = indptr[index] + values.size
    cells = np.concatenate(memberships) if memberships else np.empty(0, dtype=np.int64)
    return (
        {
            "registry_version": "generic_relation_field_boundary_registry_g2",
            "identity_field": "boundary_id",
            "records": records,
        },
        {"boundary_indptr": indptr, "cell_ordinals": cells},
    )


def generate_product_faces(
    cell_axis_indices: np.ndarray,
    edge_source: np.ndarray,
    edge_target: np.ndarray,
    shape: Sequence[int],
    orientation_signs: Sequence[int],
) -> dict[str, np.ndarray]:
    """直積格子から、軸数を固定せず向き付き単位正方形を生成する。"""
    indices = np.asarray(cell_axis_indices, dtype=np.int64)
    source = np.asarray(edge_source, dtype=np.int64)
    target = np.asarray(edge_target, dtype=np.int64)
    if indices.ndim != 2 or len(shape) != indices.shape[1]:
        raise GenericRelationFieldG2Error("product-face cell coordinate shape mismatch")
    signs_contract = tuple(int(value) for value in orientation_signs)
    if signs_contract != (1, 1, -1, -1):
        raise GenericRelationFieldG2Error("unsupported product-face orientation signs")
    cell_lookup = {tuple(int(value) for value in row): ordinal for ordinal, row in enumerate(indices)}
    if len(cell_lookup) != indices.shape[0]:
        raise GenericRelationFieldG2Error("duplicate product-grid cell coordinates")
    edge_lookup = {
        (int(left), int(right)): edge_ordinal
        for edge_ordinal, (left, right) in enumerate(zip(source, target, strict=True))
    }
    if len(edge_lookup) != source.size:
        raise GenericRelationFieldG2Error("duplicate oriented edge endpoints")

    base_cells: list[int] = []
    axis_a_values: list[int] = []
    axis_b_values: list[int] = []
    edge_members: list[int] = []
    signs: list[int] = []
    indptr = [0]
    for base_cell, base_indices in enumerate(indices):
        for axis_a, axis_b in itertools.combinations(range(indices.shape[1]), 2):
            if int(base_indices[axis_a]) >= int(shape[axis_a]) - 1:
                continue
            if int(base_indices[axis_b]) >= int(shape[axis_b]) - 1:
                continue
            vertex_00 = base_cell
            index_10 = base_indices.copy()
            index_10[axis_a] += 1
            index_01 = base_indices.copy()
            index_01[axis_b] += 1
            index_11 = index_10.copy()
            index_11[axis_b] += 1
            try:
                vertex_10 = cell_lookup[tuple(int(value) for value in index_10)]
                vertex_01 = cell_lookup[tuple(int(value) for value in index_01)]
                vertex_11 = cell_lookup[tuple(int(value) for value in index_11)]
                face_edges = (
                    edge_lookup[(vertex_00, vertex_10)],
                    edge_lookup[(vertex_10, vertex_11)],
                    edge_lookup[(vertex_01, vertex_11)],
                    edge_lookup[(vertex_00, vertex_01)],
                )
            except KeyError as exc:
                raise GenericRelationFieldG2Error("product face references a missing cell or edge") from exc
            base_cells.append(base_cell)
            axis_a_values.append(axis_a)
            axis_b_values.append(axis_b)
            edge_members.extend(face_edges)
            signs.extend(signs_contract)
            indptr.append(len(edge_members))
    face_count = len(base_cells)
    return {
        "face_ids": np.asarray([f"face/{index}" for index in range(face_count)]),
        "legacy_face_id": np.arange(face_count, dtype=np.int64),
        "base_cell_ordinal": np.asarray(base_cells, dtype=np.int64),
        "axis_a_ordinal": np.asarray(axis_a_values, dtype=np.int32),
        "axis_b_ordinal": np.asarray(axis_b_values, dtype=np.int32),
        "face_indptr": np.asarray(indptr, dtype=np.int64),
        "edge_ordinals": np.asarray(edge_members, dtype=np.int64),
        "edge_signs": np.asarray(signs, dtype=np.int8),
    }


def _component_count(cell_count: int, source: np.ndarray, target: np.ndarray) -> int:
    neighbors: list[list[int]] = [[] for _ in range(cell_count)]
    for left, right in zip(source, target, strict=True):
        neighbors[int(left)].append(int(right))
        neighbors[int(right)].append(int(left))
    visited = np.zeros(cell_count, dtype=np.bool_)
    components = 0
    for start in range(cell_count):
        if visited[start]:
            continue
        components += 1
        visited[start] = True
        queue: deque[int] = deque([start])
        while queue:
            current = queue.popleft()
            for neighbor in neighbors[current]:
                if not visited[neighbor]:
                    visited[neighbor] = True
                    queue.append(neighbor)
    return components


def validate_structure_payload(
    profile: Mapping[str, Any],
    cell_arrays: Mapping[str, np.ndarray],
    edge_arrays: Mapping[str, np.ndarray],
    face_arrays: Mapping[str, np.ndarray],
    boundary_arrays: Mapping[str, np.ndarray],
) -> dict[str, Any]:
    """固定件数を仮定せず、向き付き有限セル複体の不変条件を検証する。"""
    cell_ids = np.asarray(cell_arrays["cell_ids"])
    axis_indices = np.asarray(cell_arrays["axis_bin_indices"], dtype=np.int64)
    coordinates = np.asarray(cell_arrays["coordinate_values"], dtype=np.float64)
    if (
        cell_ids.ndim != 1
        or cell_ids.size == 0
        or cell_ids.dtype.kind != "U"
        or any(not str(value) for value in cell_ids.tolist())
        or len(set(str(value) for value in cell_ids.tolist())) != cell_ids.size
    ):
        raise GenericRelationFieldG2Error("cell identities must be a non-empty unique vector")
    cell_count = cell_ids.size
    axis_count = axis_indices.shape[1] if axis_indices.ndim == 2 else -1
    if axis_indices.shape != (cell_count, axis_count) or coordinates.shape != axis_indices.shape:
        raise GenericRelationFieldG2Error("cell coordinate arrays mismatch")
    if not np.all(np.isfinite(coordinates)):
        raise GenericRelationFieldG2Error("cell coordinates contain non-finite values")

    edge_ids = np.asarray(edge_arrays["edge_ids"])
    source = np.asarray(edge_arrays["source_cell_ordinal"], dtype=np.int64)
    target = np.asarray(edge_arrays["target_cell_ordinal"], dtype=np.int64)
    edge_axis = np.asarray(edge_arrays["axis_ordinal"], dtype=np.int64)
    edge_count = edge_ids.size
    if (
        edge_count == 0
        or edge_ids.dtype.kind != "U"
        or any(not str(value) for value in edge_ids.tolist())
        or len(set(str(value) for value in edge_ids.tolist())) != edge_count
    ):
        raise GenericRelationFieldG2Error("edge identities must be a non-empty unique vector")
    if any(array.shape != (edge_count,) for array in (source, target, edge_axis)):
        raise GenericRelationFieldG2Error("edge registry shape mismatch")
    if np.any(source < 0) or np.any(source >= cell_count) or np.any(target < 0) or np.any(target >= cell_count):
        raise GenericRelationFieldG2Error("edge endpoint out of range")
    if np.any(source == target):
        raise GenericRelationFieldG2Error("self-loop edges are not allowed by this profile")
    if len(set(zip(source.tolist(), target.tolist()))) != edge_count:
        raise GenericRelationFieldG2Error("duplicate oriented edge endpoints")
    if axis_count and (np.any(edge_axis < 0) or np.any(edge_axis >= axis_count)):
        raise GenericRelationFieldG2Error("edge axis attribution out of range")
    for name in ("topological_length", "coordinate_length", "transport_cost"):
        values = np.asarray(edge_arrays[name], dtype=np.float64)
        if values.shape != (edge_count,) or not np.all(np.isfinite(values)) or np.any(values < 0):
            raise GenericRelationFieldG2Error(f"invalid edge metric: {name}")

    rows = np.asarray(edge_arrays["incidence_rows"], dtype=np.int64)
    cols = np.asarray(edge_arrays["incidence_cols"], dtype=np.int64)
    data = np.asarray(edge_arrays["incidence_data"], dtype=np.float64)
    shape = np.asarray(edge_arrays["incidence_shape"], dtype=np.int64)
    if shape.tolist() != [cell_count, edge_count]:
        raise GenericRelationFieldG2Error("incidence shape mismatch")
    if any(array.shape != (2 * edge_count,) for array in (rows, cols, data)):
        raise GenericRelationFieldG2Error("incidence COO payload length mismatch")
    expected_cols = np.arange(edge_count, dtype=np.int64)
    if not np.array_equal(rows[0::2], source) or not np.array_equal(rows[1::2], target):
        raise GenericRelationFieldG2Error("incidence endpoints mismatch")
    if not np.array_equal(cols[0::2], expected_cols) or not np.array_equal(cols[1::2], expected_cols):
        raise GenericRelationFieldG2Error("incidence columns mismatch")
    if not np.all(data[0::2] == -1.0) or not np.all(data[1::2] == 1.0):
        raise GenericRelationFieldG2Error("incidence signs mismatch")

    face_ids = np.asarray(face_arrays["face_ids"])
    face_indptr = np.asarray(face_arrays["face_indptr"], dtype=np.int64)
    face_edges = np.asarray(face_arrays["edge_ordinals"], dtype=np.int64)
    face_signs = np.asarray(face_arrays["edge_signs"], dtype=np.int64)
    face_count = face_ids.size
    if (
        face_ids.dtype.kind != "U"
        or any(not str(value) for value in face_ids.tolist())
        or len(set(str(value) for value in face_ids.tolist())) != face_count
        or face_indptr.shape != (face_count + 1,)
    ):
        raise GenericRelationFieldG2Error("face registry identity or offset mismatch")
    if int(face_indptr[0]) != 0 or int(face_indptr[-1]) != face_edges.size:
        raise GenericRelationFieldG2Error("face offsets do not cover edge memberships")
    if face_edges.shape != face_signs.shape or np.any(face_edges < 0) or np.any(face_edges >= edge_count):
        raise GenericRelationFieldG2Error("face edge membership mismatch")
    if np.any((face_signs != -1) & (face_signs != 1)):
        raise GenericRelationFieldG2Error("face orientation signs must be plus or minus one")
    for face_ordinal in range(face_count):
        boundary: dict[int, int] = {}
        start, end = int(face_indptr[face_ordinal]), int(face_indptr[face_ordinal + 1])
        if end <= start:
            raise GenericRelationFieldG2Error("empty face is forbidden")
        for edge_ordinal, sign in zip(face_edges[start:end], face_signs[start:end], strict=True):
            left, right = int(source[edge_ordinal]), int(target[edge_ordinal])
            boundary[left] = boundary.get(left, 0) - int(sign)
            boundary[right] = boundary.get(right, 0) + int(sign)
        if any(value != 0 for value in boundary.values()):
            raise GenericRelationFieldG2Error("boundary of boundary is non-zero")

    boundary_indptr = np.asarray(boundary_arrays["boundary_indptr"], dtype=np.int64)
    boundary_cells = np.asarray(boundary_arrays["cell_ordinals"], dtype=np.int64)
    if boundary_indptr.ndim != 1 or boundary_indptr.size == 0:
        raise GenericRelationFieldG2Error("boundary registry offsets are missing")
    if int(boundary_indptr[0]) != 0 or int(boundary_indptr[-1]) != boundary_cells.size:
        raise GenericRelationFieldG2Error("boundary membership offsets mismatch")
    if np.any(boundary_cells < 0) or np.any(boundary_cells >= cell_count):
        raise GenericRelationFieldG2Error("boundary cell ordinal out of range")

    component_count = _component_count(cell_count, source, target)
    counts = profile.get("counts")
    if counts is not None:
        actual_counts = {
            "axis_count": axis_count,
            "cell_count": cell_count,
            "edge_count": edge_count,
            "face_count": face_count,
            "face_edge_membership_count": int(face_edges.size),
            "boundary_set_count": int(boundary_indptr.size - 1),
            "connected_component_count": component_count,
        }
        for key, value in actual_counts.items():
            if int(counts.get(key, -1)) != value:
                raise GenericRelationFieldG2Error(f"structure profile count mismatch: {key}")
    capabilities = profile.get("capabilities", {})
    if capabilities.get("faces") is False and face_count != 0:
        raise GenericRelationFieldG2Error("face-disabled profile contains faces")
    if capabilities.get("coordinates") is False and axis_count != 0:
        raise GenericRelationFieldG2Error("coordinate-disabled profile contains axis coordinates")
    return {
        "structure_payload_gate": "passed",
        "axis_count": axis_count,
        "cell_count": cell_count,
        "edge_count": edge_count,
        "face_count": face_count,
        "face_edge_membership_count": int(face_edges.size),
        "boundary_set_count": int(boundary_indptr.size - 1),
        "connected_component_count": component_count,
        "incidence_orientation": "source_minus_one_target_plus_one",
        "boundary_of_boundary": "exact_zero",
    }


def _load_legacy_grid(grid_artifact: Path) -> dict[str, Any]:
    from relation_field_grid_rc1 import validate_grid_artifact

    validation = validate_grid_artifact(grid_artifact)
    nodes = _load_npz(grid_artifact / "nodes.npz")
    incidence = _load_npz(grid_artifact / "incidence.npz")
    return {
        "validation": validation,
        "contract": _json_load(grid_artifact / "contract.json"),
        "metadata": _json_load(grid_artifact / "metadata.json"),
        "node_indices": nodes["indices"],
        "node_values": nodes["values"],
        "lower_boundary_mask": nodes["lower_boundary_mask"],
        "upper_boundary_mask": nodes["upper_boundary_mask"],
        "edge_source": incidence["edge_source"],
        "edge_target": incidence["edge_target"],
        "edge_axis": incidence["edge_axis"],
        "incidence_rows": incidence["rows"],
        "incidence_cols": incidence["cols"],
        "incidence_data": incidence["data"],
        "incidence_shape": incidence["shape"],
        "manifest_hash": _sha256_file(grid_artifact / "manifest.json"),
    }


def _verify_fixed_sources(
    fixed_profile: Mapping[str, Any],
    legacy: Mapping[str, Any],
) -> None:
    axes = fixed_profile["axes"]
    gk_contract = _json_load(_safe_repo_path(fixed_profile["source_contracts"]["gk"]["path"]))
    relation_contract = _json_load(
        _safe_repo_path(fixed_profile["source_contracts"]["relation_field"]["path"])
    )
    grid_contract = legacy["contract"]
    for label, contract_axes in (
        ("G/K", gk_contract.get("axes", {})),
        ("RF-1", relation_contract.get("axes", {})),
        ("RF-2", grid_contract.get("axes", {})),
    ):
        if contract_axes.get("order") != axes["order"]:
            raise GenericRelationFieldG2Error(f"{label} axis order mismatch")
        if contract_axes.get("bins") != axes["bins"]:
            raise GenericRelationFieldG2Error(f"{label} axis bins mismatch")
        if contract_axes.get("shape") != axes["shape"]:
            raise GenericRelationFieldG2Error(f"{label} grid shape mismatch")
    expected = fixed_profile["expected_counts"]
    actual = {
        "axis_count": len(axes["order"]),
        "cell_count": int(legacy["node_indices"].shape[0]),
        "edge_count": int(legacy["edge_source"].size),
        "directed_neighbor_count": int(legacy["incidence_rows"].size),
    }
    for key, value in actual.items():
        if int(expected[key]) != value:
            raise GenericRelationFieldG2Error(f"fixed profile {key} mismatch")


def _legacy_rf6_face_gate(
    legacy: Mapping[str, Any],
    generated_faces: Mapping[str, np.ndarray],
) -> bool:
    from scipy.sparse import coo_matrix
    from relation_field_hodge_decomposition_rc1 import generate_face_complex

    rows = np.asarray(legacy["incidence_rows"], dtype=np.int32)
    cols = np.asarray(legacy["incidence_cols"], dtype=np.int32)
    data = np.asarray(legacy["incidence_data"], dtype=np.float64)
    shape = tuple(int(value) for value in legacy["incidence_shape"])
    grid = {
        "edge_source": np.asarray(legacy["edge_source"], dtype=np.int32),
        "edge_target": np.asarray(legacy["edge_target"], dtype=np.int32),
        "edge_axis": np.asarray(legacy["edge_axis"], dtype=np.int8),
        "node_indices": np.asarray(legacy["node_indices"], dtype=np.int16),
        "node_values": np.asarray(legacy["node_values"], dtype=np.float64),
        "incidence": coo_matrix((data, (rows, cols)), shape=shape).tocsr(),
    }
    expected = generate_face_complex(grid)
    face_count = generated_faces["legacy_face_id"].size
    if expected["face_edge_ids"].shape != (face_count, 4):
        return False
    starts = generated_faces["face_indptr"][:-1]
    ends = generated_faces["face_indptr"][1:]
    if not np.all(ends - starts == 4):
        return False
    edges = generated_faces["edge_ordinals"].reshape(face_count, 4)
    signs = generated_faces["edge_signs"].reshape(face_count, 4)
    return bool(
        np.array_equal(expected["face_base_cell"], generated_faces["base_cell_ordinal"])
        and np.array_equal(expected["face_axis_a"], generated_faces["axis_a_ordinal"])
        and np.array_equal(expected["face_axis_b"], generated_faces["axis_b_ordinal"])
        and np.array_equal(expected["face_edge_ids"], edges)
        and np.array_equal(expected["face_edge_signs"], signs)
        and float(expected["boundary_of_boundary_max_abs"]) == 0.0
    )


def _structure_hash(profile: Mapping[str, Any]) -> str:
    payload = dict(profile)
    payload.pop("structure_hash", None)
    return _sha256_bytes(_canonical_json(payload))


def build_fixed5_structure_artifact(
    grid_artifact_dir: str | Path,
    output: str | Path,
    *,
    contract_path: str | Path = DEFAULT_CONTRACT,
    fixed_profile_path: str | Path = DEFAULT_FIXED_PROFILE,
) -> Path:
    target = Path(output)
    if target.exists():
        raise GenericRelationFieldG2Error(f"output already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    contract = load_contract(contract_path)
    fixed_profile = load_fixed_profile(fixed_profile_path)
    legacy = _load_legacy_grid(Path(grid_artifact_dir))
    _verify_fixed_sources(fixed_profile, legacy)

    axis_registry = _axis_registry(fixed_profile)
    cell_arrays = {
        "cell_ids": np.asarray(
            [f"cell/{index}" for index in range(legacy["node_indices"].shape[0])]
        ),
        "legacy_cell_id": np.arange(legacy["node_indices"].shape[0], dtype=np.int64),
        "axis_bin_indices": np.asarray(legacy["node_indices"], dtype=np.int32),
        "coordinate_values": np.asarray(legacy["node_values"], dtype=np.float64),
    }
    source = np.asarray(legacy["edge_source"], dtype=np.int64)
    target_edge = np.asarray(legacy["edge_target"], dtype=np.int64)
    axis = np.asarray(legacy["edge_axis"], dtype=np.int32)
    coordinate_length = np.abs(
        cell_arrays["coordinate_values"][target_edge, axis]
        - cell_arrays["coordinate_values"][source, axis]
    )
    edge_count = source.size
    edge_arrays = {
        "edge_ids": np.asarray([f"edge/{index}" for index in range(edge_count)]),
        "legacy_edge_id": np.arange(edge_count, dtype=np.int64),
        "source_cell_ordinal": source,
        "target_cell_ordinal": target_edge,
        "axis_ordinal": axis,
        "topological_length": np.full(
            edge_count,
            float(fixed_profile["edge_policy"]["topological_length"]),
            dtype=np.float64,
        ),
        "coordinate_length": np.asarray(coordinate_length, dtype=np.float64),
        "transport_cost": np.full(
            edge_count,
            float(fixed_profile["edge_policy"]["transport_cost"]),
            dtype=np.float64,
        ),
        "incidence_rows": np.asarray(legacy["incidence_rows"], dtype=np.int64),
        "incidence_cols": np.asarray(legacy["incidence_cols"], dtype=np.int64),
        "incidence_data": np.asarray(legacy["incidence_data"], dtype=np.float64),
        "incidence_shape": np.asarray(legacy["incidence_shape"], dtype=np.int64),
    }
    face_arrays = generate_product_faces(
        cell_arrays["axis_bin_indices"],
        source,
        target_edge,
        fixed_profile["axes"]["shape"],
        contract["face_orientation"]["elementary_square_edge_signs"],
    )
    boundary_registry, boundary_arrays = _boundary_payload(
        axis_registry,
        cell_arrays["axis_bin_indices"],
        fixed_profile["axes"]["shape"],
    )
    validation = validate_structure_payload(
        fixed_profile,
        cell_arrays,
        edge_arrays,
        face_arrays,
        boundary_arrays,
    )
    expected_counts = fixed_profile["expected_counts"]
    for key in ("axis_count", "cell_count", "edge_count", "face_count", "face_edge_membership_count"):
        if int(validation[key]) != int(expected_counts[key]):
            raise GenericRelationFieldG2Error(f"generated fixed structure count mismatch: {key}")
    if validation["connected_component_count"] != 1:
        raise GenericRelationFieldG2Error("fixed structure must be connected")
    if not np.all(
        edge_arrays["coordinate_length"]
        == float(fixed_profile["edge_policy"]["coordinate_length"])
    ):
        raise GenericRelationFieldG2Error("fixed coordinate edge length mismatch")
    if not np.all(
        edge_arrays["transport_cost"]
        == float(fixed_profile["edge_policy"]["transport_cost"])
    ):
        raise GenericRelationFieldG2Error("fixed RF-3 transport cost mismatch")
    if not _legacy_rf6_face_gate(legacy, face_arrays):
        raise GenericRelationFieldG2Error("generic faces do not match legacy RF-6")

    source_hashes = _source_contract_hashes(contract)
    profile: dict[str, Any] = {
        "structure_schema_version": "generic_relation_structure_g2",
        "structure_profile_id": fixed_profile["profile_id"],
        "structure_profile_version": fixed_profile["profile_version"],
        "structure_class": fixed_profile["structure_class"],
        "topology_time_policy": fixed_profile["topology_time_policy"],
        "capabilities": fixed_profile["capabilities"],
        "identity_rules": fixed_profile["identity_rules"],
        "axis_registry_hash": _sha256_bytes(_canonical_json(axis_registry)),
        "boundary_registry_hash": _sha256_bytes(_canonical_json(boundary_registry)),
        "registry_content_hashes": {
            "cells": _array_content_hash(cell_arrays),
            "edges": _array_content_hash(edge_arrays),
            "faces": _array_content_hash(face_arrays),
            "boundary_membership": _array_content_hash(boundary_arrays),
        },
        "source_contract_hashes": source_hashes,
        "source_grid_manifest_hash": legacy["manifest_hash"],
        "counts": {key: validation[key] for key in (
            "axis_count",
            "cell_count",
            "edge_count",
            "face_count",
            "face_edge_membership_count",
            "boundary_set_count",
            "connected_component_count",
        )},
        "incidence_convention": "source_minus_one_target_plus_one",
        "compatibility": {
            "legacy_rf2_identity_exact": True,
            "legacy_rf2_incidence_exact": True,
            "legacy_rf3_edge_cost_exact": True,
            "legacy_rf6_faces_exact": True,
            "boundary_of_boundary_exact": True,
        },
        "prediction_performed": False,
        "canonical_gk_read": False,
        "canonical_writeback_performed": False,
    }
    profile["structure_hash"] = _structure_hash(profile)
    validation = {
        **validation,
        "g2_structure_gate": "passed",
        "structure_hash": profile["structure_hash"],
        "legacy_rf2_identity_exact": True,
        "legacy_rf2_incidence_exact": True,
        "legacy_rf3_edge_cost_exact": True,
        "legacy_rf6_faces_exact": True,
        "source_contract_count": len(source_hashes),
        "prediction_performed": False,
        "canonical_gk_read": False,
        "canonical_writeback_performed": False,
    }

    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp-", dir=target.parent))
    try:
        _json_dump(temporary / "contract.json", contract)
        _json_dump(temporary / "structure_profile.json", profile)
        _json_dump(temporary / "axis_registry.json", axis_registry)
        _write_deterministic_npz(temporary / "cell_registry.npz", cell_arrays)
        _write_deterministic_npz(temporary / "edge_registry.npz", edge_arrays)
        _write_deterministic_npz(temporary / "face_registry.npz", face_arrays)
        _json_dump(temporary / "boundary_registry.json", boundary_registry)
        _write_deterministic_npz(temporary / "boundary_membership.npz", boundary_arrays)
        _json_dump(
            temporary / "field_record_schema.json",
            {
                "schema_version": "generic_relation_field_records_g2",
                **contract["field_records"],
            },
        )
        _json_dump(temporary / "validation.json", validation)
        _write_manifest(temporary, "generic_relation_structure_g2")
        os.replace(temporary, target)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return target


def _load_structure_artifact(root: Path, *, verify_manifest: bool) -> dict[str, Any]:
    required = {
        "contract.json",
        "structure_profile.json",
        "axis_registry.json",
        "cell_registry.npz",
        "edge_registry.npz",
        "face_registry.npz",
        "boundary_registry.json",
        "boundary_membership.npz",
        "field_record_schema.json",
        "validation.json",
        "manifest.json",
    }
    missing = sorted(value for value in required if not (root / value).is_file())
    if missing:
        raise GenericRelationFieldG2Error(f"missing structure artifact files: {missing}")
    if verify_manifest:
        _verify_manifest(root)
    contract = _json_load(root / "contract.json")
    validate_contract(contract, require_source_files=False)
    profile = _json_load(root / "structure_profile.json")
    axis_registry = _json_load(root / "axis_registry.json")
    boundary_registry = _json_load(root / "boundary_registry.json")
    cell_arrays = _load_npz(root / "cell_registry.npz")
    edge_arrays = _load_npz(root / "edge_registry.npz")
    face_arrays = _load_npz(root / "face_registry.npz")
    boundary_arrays = _load_npz(root / "boundary_membership.npz")
    if len(axis_registry.get("records", [])) != int(profile.get("counts", {}).get("axis_count", -1)):
        raise GenericRelationFieldG2Error("axis registry count mismatch")
    if len(boundary_registry.get("records", [])) != int(
        profile.get("counts", {}).get("boundary_set_count", -1)
    ):
        raise GenericRelationFieldG2Error("boundary registry count mismatch")
    if profile.get("axis_registry_hash") != _sha256_bytes(_canonical_json(axis_registry)):
        raise GenericRelationFieldG2Error("axis registry hash mismatch")
    if profile.get("boundary_registry_hash") != _sha256_bytes(_canonical_json(boundary_registry)):
        raise GenericRelationFieldG2Error("boundary registry hash mismatch")
    expected_content = {
        "cells": _array_content_hash(cell_arrays),
        "edges": _array_content_hash(edge_arrays),
        "faces": _array_content_hash(face_arrays),
        "boundary_membership": _array_content_hash(boundary_arrays),
    }
    if profile.get("registry_content_hashes") != expected_content:
        raise GenericRelationFieldG2Error("structure registry content hash mismatch")
    if profile.get("structure_hash") != _structure_hash(profile):
        raise GenericRelationFieldG2Error("structure hash mismatch")
    validation = validate_structure_payload(
        profile,
        cell_arrays,
        edge_arrays,
        face_arrays,
        boundary_arrays,
    )
    return {
        "contract": contract,
        "profile": profile,
        "axis_registry": axis_registry,
        "boundary_registry": boundary_registry,
        "cell_arrays": cell_arrays,
        "edge_arrays": edge_arrays,
        "face_arrays": face_arrays,
        "boundary_arrays": boundary_arrays,
        "validation": validation,
    }


def validate_structure_artifact(input_path: str | Path) -> dict[str, Any]:
    root = Path(input_path)
    loaded = _load_structure_artifact(root, verify_manifest=True)
    persisted = _json_load(root / "validation.json")
    core = loaded["validation"]
    for key, value in core.items():
        if persisted.get(key) != value:
            raise GenericRelationFieldG2Error(f"persisted structure validation mismatch: {key}")
    if persisted.get("structure_hash") != loaded["profile"]["structure_hash"]:
        raise GenericRelationFieldG2Error("persisted structure hash mismatch")
    if persisted.get("g2_structure_gate") != "passed":
        raise GenericRelationFieldG2Error("G2 structure gate did not pass")
    return persisted


def _read_ledger_prefix(path: Path, to_t: int | None) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            current_t = int(row["t"])
            if to_t is not None and current_t > to_t:
                raise GenericRelationFieldG2Error("requested prediction time is absent from G/K")
            rows.append(row)
            if to_t is not None and current_t == to_t:
                break
    if not rows:
        raise GenericRelationFieldG2Error("history prefix contains no G_t frames")
    if to_t is not None and int(rows[-1]["t"]) != to_t:
        raise GenericRelationFieldG2Error("requested prediction time is absent from G/K")
    return rows


def _validate_gk_prefix(
    trajectory: Path,
    structure: Mapping[str, Any],
    to_t: int | None,
) -> tuple[np.memmap, list[dict[str, str]], dict[str, Any]]:
    from fixed5axis_gk_rc1 import (
        compute_gt_hash,
        compute_history_chain_hash,
        initial_history_chain_hash,
        load_contract as load_gk_contract,
        validate_distribution,
    )

    gk_contract = load_gk_contract()
    expected_hash = structure["profile"]["source_contract_hashes"].get(
        "configs/fixed5axis_gk_rc1_contract.json"
    )
    if expected_hash != _sha256_bytes(_canonical_json(gk_contract)):
        raise GenericRelationFieldG2Error("structure and G/K contract hashes differ")
    mass_path = trajectory / gk_contract["storage"]["gt_file"]
    ledger_path = trajectory / gk_contract["storage"]["history_ledger_file"]
    provenance_path = trajectory / gk_contract["storage"]["provenance_file"]
    if not mass_path.is_file() or not ledger_path.is_file() or not provenance_path.is_file():
        raise GenericRelationFieldG2Error("canonical G/K prefix source is incomplete")
    provenance = _json_load(provenance_path)
    axis_records = structure["axis_registry"]["records"]
    axis_order = [record["axis_id"] for record in axis_records]
    axis_bins = [float(value) for value in axis_records[0]["bin_values"]]
    if provenance.get("axis_order") != axis_order or provenance.get("axis_bins") != axis_bins:
        raise GenericRelationFieldG2Error("canonical G/K provenance and structure profile differ")
    mass = np.load(mass_path, mmap_mode="r", allow_pickle=False)
    shape = tuple(int(value) for value in provenance.get("gt_shape", []))
    expected_shape = tuple(len(record["bin_ids"]) for record in axis_records)
    if shape != expected_shape:
        raise GenericRelationFieldG2Error("canonical G/K shape and axis registry differ")
    if mass.ndim != len(shape) + 1 or tuple(mass.shape[1:]) != shape:
        raise GenericRelationFieldG2Error("canonical G/K storage shape mismatch")
    if math.prod(shape) != int(structure["profile"]["counts"]["cell_count"]):
        raise GenericRelationFieldG2Error("canonical G/K cell count and structure profile differ")
    rows = _read_ledger_prefix(ledger_path, to_t)
    previous_hash = ""
    chain_hash = initial_history_chain_hash()
    previous_t: int | None = None
    trajectory_id = rows[0]["trajectory_id"]
    for prefix_ordinal, row in enumerate(rows):
        index = int(row["gt_row_index"])
        current_t = int(row["t"])
        if index != prefix_ordinal:
            raise GenericRelationFieldG2Error("G/K prefix row indices must begin at zero and be contiguous")
        if row["trajectory_id"] != trajectory_id or row.get("source_trajectory_id", trajectory_id) != trajectory_id:
            raise GenericRelationFieldG2Error("G/K prefix trajectory identity mismatch")
        expected_status = "initial" if previous_t is None else "continuous"
        expected_delta = 0 if previous_t is None else current_t - previous_t
        if (
            row["continuity_status"] != expected_status
            or expected_delta != (0 if previous_t is None else 1)
            or int(row["delta_t"]) != expected_delta
            or row["phase"] != gk_contract["gt"]["phase"]
            or row.get("admissible_for_research", "").lower() != "true"
        ):
            raise GenericRelationFieldG2Error("G/K prediction prefix must be continuous")
        if row["previous_gt_hash"] != previous_hash:
            raise GenericRelationFieldG2Error("G/K prefix previous hash mismatch")
        distribution = validate_distribution(np.asarray(mass[index]), gk_contract)
        expected_gt_hash = compute_gt_hash(
            contract_version=gk_contract["contract_version"],
            trajectory_id=trajectory_id,
            t=current_t,
            distribution=distribution,
            source_state_hash=row["source_state_hash"],
        )
        if row["gt_hash"] != expected_gt_hash:
            raise GenericRelationFieldG2Error("G/K prefix G_t hash mismatch")
        chain_hash = compute_history_chain_hash(chain_hash, expected_gt_hash, current_t)
        if row["history_chain_hash"] != chain_hash:
            raise GenericRelationFieldG2Error("G/K prefix history chain mismatch")
        previous_hash, previous_t = expected_gt_hash, current_t
    return mass, rows, provenance


def build_fixed5_history_view(
    trajectory_dir: str | Path,
    structure_artifact_dir: str | Path,
    output: str | Path,
    *,
    to_t: int | None = None,
) -> Path:
    target = Path(output)
    if target.exists():
        raise GenericRelationFieldG2Error(f"output already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if to_t is not None and (
        isinstance(to_t, bool) or not isinstance(to_t, int) or to_t < 0
    ):
        raise GenericRelationFieldG2Error("to_t must be a non-negative integer")
    structure = _load_structure_artifact(Path(structure_artifact_dir), verify_manifest=True)
    mass, ledger, provenance = _validate_gk_prefix(Path(trajectory_dir), structure, to_t)
    cell_count = int(structure["profile"]["counts"]["cell_count"])
    frame_count = len(ledger)
    frame_offsets = np.arange(frame_count + 1, dtype=np.int64) * cell_count
    cell_ordinals = np.tile(np.arange(cell_count, dtype=np.int64), frame_count)
    mass_values = np.concatenate(
        [np.asarray(mass[int(row["gt_row_index"])]).reshape(-1, order="C") for row in ledger]
    ).astype(np.float64, copy=False)
    frame_records = [
        {
            "frame_id": f"{row['trajectory_id']}/t/{int(row['t'])}",
            "frame_ordinal": ordinal,
            "t": int(row["t"]),
            "source_gt_hash": row["gt_hash"],
            "source_history_chain_hash": row["history_chain_hash"],
            "mass_start_offset": int(frame_offsets[ordinal]),
            "mass_end_offset": int(frame_offsets[ordinal + 1]),
        }
        for ordinal, row in enumerate(ledger)
    ]
    identity = {
        "artifact_version": "generic_relation_history_view_g2",
        "canonical": False,
        "read_only": True,
        "trajectory_id": ledger[0]["trajectory_id"],
        "history_start_t": int(ledger[0]["t"]),
        "history_end_t": int(ledger[-1]["t"]),
        "frame_count": frame_count,
        "structure_profile_id": structure["profile"]["structure_profile_id"],
        "structure_hash": structure["profile"]["structure_hash"],
        "causal_prefix_hash": ledger[-1]["history_chain_hash"],
        "source_future_mass_values_read": False,
        "source_future_ledger_rows_parsed": False,
        "source_truth_read": False,
        "canonical_writeback_performed": False,
        "prediction_performed": False,
    }
    validation = {
        "g2_history_view_gate": "passed",
        "frame_count": frame_count,
        "mass_record_count": int(mass_values.size),
        "structure_hash": identity["structure_hash"],
        "causal_prefix_hash": identity["causal_prefix_hash"],
        "all_frame_mass_unit_total": bool(
            all(abs(float(mass_values[frame_offsets[i]:frame_offsets[i + 1]].sum()) - 1.0) <= 1e-10 for i in range(frame_count))
        ),
        "offset_keyed_cell_records": True,
        "source_future_mass_values_read": False,
        "source_future_ledger_rows_parsed": False,
        "canonical_writeback_performed": False,
        "prediction_performed": False,
    }
    if not validation["all_frame_mass_unit_total"]:
        raise GenericRelationFieldG2Error("history view frame mass is not unit total")
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp-", dir=target.parent))
    try:
        _json_dump(temporary / "identity.json", identity)
        with (temporary / "frame_registry.jsonl").open("w", encoding="utf-8") as handle:
            for record in frame_records:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        _write_deterministic_npz(
            temporary / "mass_records.npz",
            {
                "frame_offsets": frame_offsets,
                "cell_ordinals": cell_ordinals,
                "mass_values": mass_values,
            },
        )
        _json_dump(
            temporary / "provenance.json",
            {
                "source_contract_version": provenance.get("contract_version"),
                "source_trajectory_id": provenance.get("trajectory_id"),
                "source_structure_hash": identity["structure_hash"],
                "source_gt_hashes": [row["gt_hash"] for row in ledger],
                "causal_prefix_hash": identity["causal_prefix_hash"],
                "future_observations_used": False,
                "canonical_writeback_performed": False,
            },
        )
        _json_dump(temporary / "validation.json", validation)
        _write_manifest(temporary, "generic_relation_history_view_g2")
        os.replace(temporary, target)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return target


def validate_history_view(
    input_path: str | Path,
    structure_artifact_dir: str | Path,
) -> dict[str, Any]:
    root = Path(input_path)
    _verify_manifest(root)
    structure = _load_structure_artifact(Path(structure_artifact_dir), verify_manifest=True)
    identity = _json_load(root / "identity.json")
    provenance = _json_load(root / "provenance.json")
    validation = _json_load(root / "validation.json")
    arrays = _load_npz(root / "mass_records.npz")
    if identity.get("structure_hash") != structure["profile"]["structure_hash"]:
        raise GenericRelationFieldG2Error("history view structure hash mismatch")
    if identity.get("causal_prefix_hash") != provenance.get("causal_prefix_hash"):
        raise GenericRelationFieldG2Error("history view causal prefix hash mismatch")
    offsets = np.asarray(arrays["frame_offsets"], dtype=np.int64)
    cells = np.asarray(arrays["cell_ordinals"], dtype=np.int64)
    values = np.asarray(arrays["mass_values"], dtype=np.float64)
    frame_count = int(identity.get("frame_count", -1))
    cell_count = int(structure["profile"]["counts"]["cell_count"])
    if offsets.shape != (frame_count + 1,) or int(offsets[0]) != 0 or int(offsets[-1]) != values.size:
        raise GenericRelationFieldG2Error("history view frame offsets mismatch")
    if cells.shape != values.shape or np.any(cells < 0) or np.any(cells >= cell_count):
        raise GenericRelationFieldG2Error("history view cell records mismatch")
    for index in range(frame_count):
        start, end = int(offsets[index]), int(offsets[index + 1])
        if end - start != cell_count or not np.array_equal(cells[start:end], np.arange(cell_count)):
            raise GenericRelationFieldG2Error("history view frame is not keyed to the structure registry")
        if not np.all(np.isfinite(values[start:end])) or np.any(values[start:end] < 0):
            raise GenericRelationFieldG2Error("history view mass contains invalid values")
        if abs(float(values[start:end].sum()) - 1.0) > 1e-10:
            raise GenericRelationFieldG2Error("history view mass is not unit total")
    if validation.get("g2_history_view_gate") != "passed":
        raise GenericRelationFieldG2Error("history view gate did not pass")
    if identity.get("canonical_writeback_performed") is not False:
        raise GenericRelationFieldG2Error("history view performed canonical writeback")
    return validation


def _scope_identity_sets(structure: Mapping[str, Any]) -> dict[str, set[str]]:
    return {
        "axis": {str(record["axis_id"]) for record in structure["axis_registry"]["records"]},
        "cell": {str(value) for value in structure["cell_arrays"]["cell_ids"].tolist()},
        "edge": {str(value) for value in structure["edge_arrays"]["edge_ids"].tolist()},
        "face": {str(value) for value in structure["face_arrays"]["face_ids"].tolist()},
    }


def _validate_field_record(
    record: Mapping[str, Any],
    schema: Mapping[str, Any],
    scopes: Mapping[str, set[str]],
) -> dict[str, Any]:
    missing = [field for field in schema["required_fields"] if field not in record]
    if missing:
        raise GenericRelationFieldG2Error(f"field record is missing required fields: {missing}")
    normalized = dict(record)
    for name in ("record_id", "feature_id", "feature_group", "unit", "normalization_id"):
        if not isinstance(normalized[name], str) or not normalized[name]:
            raise GenericRelationFieldG2Error(f"field record {name} must be a non-empty string")
    scope_type = normalized["scope_type"]
    scope_ids = normalized["scope_ids"]
    if scope_type not in schema["allowed_scope_types"] or not isinstance(scope_ids, list):
        raise GenericRelationFieldG2Error("field record scope is invalid")
    if scope_type == "global":
        if scope_ids:
            raise GenericRelationFieldG2Error("global field record must not contain scope ids")
    elif not scope_ids or any(value not in scopes[scope_type] for value in scope_ids):
        raise GenericRelationFieldG2Error("field record references an unknown scope id")
    availability = normalized["availability_status"]
    evidence = normalized["evidence_status"]
    if availability not in schema["availability_statuses"]:
        raise GenericRelationFieldG2Error("field record availability status is invalid")
    if evidence not in schema["relation_field_evidence_statuses"]:
        raise GenericRelationFieldG2Error("field record evidence status is invalid")
    if not isinstance(normalized["source_refs"], list):
        raise GenericRelationFieldG2Error("field record source_refs must be a list")
    if any(not isinstance(value, str) or not value for value in normalized["source_refs"]):
        raise GenericRelationFieldG2Error("field record source_refs must contain non-empty strings")
    values = [normalized["value"], normalized["lower_bound"], normalized["upper_bound"]]
    if availability in {"valid", "limited"}:
        if values[0] is None or isinstance(values[0], bool) or not math.isfinite(float(values[0])):
            raise GenericRelationFieldG2Error("available field record requires a finite value")
        for value in values[1:]:
            if value is not None and (isinstance(value, bool) or not math.isfinite(float(value))):
                raise GenericRelationFieldG2Error("field record bound must be finite or null")
        if values[1] is not None and values[2] is not None and float(values[1]) > float(values[2]):
            raise GenericRelationFieldG2Error("field record lower bound exceeds upper bound")
        if values[1] is not None and float(values[0]) < float(values[1]):
            raise GenericRelationFieldG2Error("field record value is below its lower bound")
        if values[2] is not None and float(values[0]) > float(values[2]):
            raise GenericRelationFieldG2Error("field record value is above its upper bound")
    elif any(value is not None for value in values):
        raise GenericRelationFieldG2Error("withheld or invalid field record values must be null")
    normalized["scope_ids"] = [str(value) for value in scope_ids]
    return normalized


def build_field_records_artifact(
    structure_artifact_dir: str | Path,
    output: str | Path,
    *,
    stage: str,
    records: Sequence[Mapping[str, Any]],
    causal_prefix_hash: str,
    source_refs: Sequence[str],
) -> Path:
    target = Path(output)
    if target.exists():
        raise GenericRelationFieldG2Error(f"output already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    structure = _load_structure_artifact(Path(structure_artifact_dir), verify_manifest=True)
    schema = {
        "schema_version": "generic_relation_field_records_g2",
        **structure["contract"]["field_records"],
    }
    if stage not in schema["allowed_stages"]:
        raise GenericRelationFieldG2Error("unsupported relation-field record stage")
    if len(causal_prefix_hash) != 64 or any(value not in "0123456789abcdef" for value in causal_prefix_hash):
        raise GenericRelationFieldG2Error("causal_prefix_hash must be a lowercase SHA-256 digest")
    if not records:
        raise GenericRelationFieldG2Error("field record artifact cannot be empty")
    if any(not isinstance(value, str) or not value for value in source_refs):
        raise GenericRelationFieldG2Error("artifact source_refs must contain non-empty strings")
    scopes = _scope_identity_sets(structure)
    normalized = [_validate_field_record(record, schema, scopes) for record in records]
    record_ids = [record["record_id"] for record in normalized]
    if len(set(record_ids)) != len(record_ids):
        raise GenericRelationFieldG2Error("field record ids must be unique")
    normalized.sort(key=lambda record: record["record_id"])
    identity = {
        "artifact_version": "generic_relation_field_records_g2",
        "stage": stage,
        "structure_profile_id": structure["profile"]["structure_profile_id"],
        "structure_hash": structure["profile"]["structure_hash"],
        "causal_prefix_hash": causal_prefix_hash,
        "record_count": len(normalized),
        "fixed_length_primary_storage": False,
        "prediction_performed": False,
        "action_selection_performed": False,
        "canonical_writeback_performed": False,
    }
    validation = {
        "g2_field_records_gate": "passed",
        "stage": stage,
        "record_count": len(normalized),
        "unique_record_ids": True,
        "scope_ids_valid": True,
        "structure_hash": identity["structure_hash"],
        "causal_prefix_hash": causal_prefix_hash,
        "fixed_length_primary_storage": False,
        "prediction_performed": False,
        "action_selection_performed": False,
        "canonical_writeback_performed": False,
    }
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp-", dir=target.parent))
    try:
        _json_dump(temporary / "schema.json", schema)
        _json_dump(temporary / "identity.json", identity)
        with (temporary / "records.jsonl").open("w", encoding="utf-8") as handle:
            for record in normalized:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        _json_dump(
            temporary / "provenance.json",
            {
                "source_refs": list(source_refs),
                "causal_prefix_hash": causal_prefix_hash,
                "structure_hash": identity["structure_hash"],
                "future_information_used": False,
                "canonical_writeback_performed": False,
            },
        )
        _json_dump(temporary / "validation.json", validation)
        _write_manifest(temporary, "generic_relation_field_records_g2")
        os.replace(temporary, target)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return target


def validate_field_records_artifact(
    input_path: str | Path,
    structure_artifact_dir: str | Path,
) -> dict[str, Any]:
    root = Path(input_path)
    _verify_manifest(root)
    structure = _load_structure_artifact(Path(structure_artifact_dir), verify_manifest=True)
    schema = _json_load(root / "schema.json")
    identity = _json_load(root / "identity.json")
    provenance = _json_load(root / "provenance.json")
    validation = _json_load(root / "validation.json")
    expected_schema = {
        "schema_version": "generic_relation_field_records_g2",
        **structure["contract"]["field_records"],
    }
    if schema != expected_schema:
        raise GenericRelationFieldG2Error("field record schema and structure contract differ")
    if identity.get("structure_hash") != structure["profile"]["structure_hash"]:
        raise GenericRelationFieldG2Error("field records structure hash mismatch")
    if identity.get("causal_prefix_hash") != provenance.get("causal_prefix_hash"):
        raise GenericRelationFieldG2Error("field records causal prefix hash mismatch")
    scopes = _scope_identity_sets(structure)
    records: list[dict[str, Any]] = []
    with (root / "records.jsonl").open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(_validate_field_record(json.loads(line), schema, scopes))
    if len(records) != int(identity.get("record_count", -1)):
        raise GenericRelationFieldG2Error("field record count mismatch")
    record_ids = [record["record_id"] for record in records]
    if record_ids != sorted(record_ids) or len(set(record_ids)) != len(record_ids):
        raise GenericRelationFieldG2Error("field record ids are not unique sorted identities")
    if validation.get("g2_field_records_gate") != "passed":
        raise GenericRelationFieldG2Error("field record gate did not pass")
    if identity.get("prediction_performed") is not False:
        raise GenericRelationFieldG2Error("G2 field records must not perform prediction")
    return validation


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    structure = sub.add_parser("build-fixed5-structure")
    structure.add_argument("--grid-artifact", required=True)
    structure.add_argument("--output", required=True)
    structure.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    structure.add_argument("--fixed-profile", default=str(DEFAULT_FIXED_PROFILE))
    validate_structure = sub.add_parser("validate-structure")
    validate_structure.add_argument("--input", required=True)
    history = sub.add_parser("build-history-view")
    history.add_argument("--trajectory", required=True)
    history.add_argument("--structure", required=True)
    history.add_argument("--output", required=True)
    history.add_argument("--to-t", type=int)
    validate_history = sub.add_parser("validate-history-view")
    validate_history.add_argument("--input", required=True)
    validate_history.add_argument("--structure", required=True)
    field = sub.add_parser("build-field-records")
    field.add_argument("--structure", required=True)
    field.add_argument("--output", required=True)
    field.add_argument("--stage", required=True)
    field.add_argument("--records-json", required=True)
    field.add_argument("--causal-prefix-hash", required=True)
    field.add_argument("--source-ref", action="append", default=[])
    validate_field = sub.add_parser("validate-field-records")
    validate_field.add_argument("--input", required=True)
    validate_field.add_argument("--structure", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "build-fixed5-structure":
        result = build_fixed5_structure_artifact(
            args.grid_artifact,
            args.output,
            contract_path=args.contract,
            fixed_profile_path=args.fixed_profile,
        )
        print(json.dumps({"output": str(result), "status": "built"}, sort_keys=True))
    elif args.command == "validate-structure":
        print(json.dumps(validate_structure_artifact(args.input), sort_keys=True))
    elif args.command == "build-history-view":
        result = build_fixed5_history_view(
            args.trajectory,
            args.structure,
            args.output,
            to_t=args.to_t,
        )
        print(json.dumps({"output": str(result), "status": "built"}, sort_keys=True))
    elif args.command == "validate-history-view":
        print(json.dumps(validate_history_view(args.input, args.structure), sort_keys=True))
    elif args.command == "build-field-records":
        value = _json_load(Path(args.records_json))
        if not isinstance(value, list):
            raise GenericRelationFieldG2Error("records JSON must contain a list")
        result = build_field_records_artifact(
            args.structure,
            args.output,
            stage=args.stage,
            records=value,
            causal_prefix_hash=args.causal_prefix_hash,
            source_refs=args.source_ref,
        )
        print(json.dumps({"output": str(result), "status": "built"}, sort_keys=True))
    else:
        print(json.dumps(validate_field_records_artifact(args.input, args.structure), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
