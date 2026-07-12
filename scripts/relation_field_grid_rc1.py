"""固定5軸 動的関係場 RF-2: 決定論的な格子接続基盤。

3,125セルの識別子、局所隣接辺、CSR近傍、COO接続演算子を生成・検証する。
G_t・K_t、シナリオ、正解情報は読み取らず、流れ逆算や予測は行わない。
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import shutil
import tempfile
import zipfile
from collections import Counter, deque
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RELATION_CONTRACT = ROOT / "configs" / "relation_field_rc1_contract.json"
DEFAULT_GRID_CONTRACT = ROOT / "configs" / "relation_field_grid_rc1_contract.json"

AXIS_NAMES = (
    "resource_slack",
    "information_quality",
    "pressure",
    "exploration_room",
    "reversibility",
)
AXIS_BINS = np.asarray([0.0, 0.25, 0.5, 0.75, 1.0], dtype=np.float64)
GRID_SHAPE = (5, 5, 5, 5, 5)
AXIS_STRIDES = (625, 125, 25, 5, 1)
CELL_COUNT = 3125
UNDIRECTED_EDGE_COUNT = 12500
DIRECTED_NEIGHBOR_COUNT = 25000
DEGREE_DISTRIBUTION = {5: 32, 6: 240, 7: 720, 8: 1080, 9: 810, 10: 243}


class RelationFieldGridError(ValueError):
    """RF-2格子契約または成果物の不整合。"""


def _json_load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _json_dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _canonical_json_bytes(value: Any) -> bytes:
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


def _write_deterministic_npz(path: Path, arrays: Mapping[str, np.ndarray]) -> None:
    """固定ZIP時刻とキー順で、再構築時に同一バイト列となるNPZを書く。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(arrays):
            buffer = io.BytesIO()
            np.save(buffer, np.asarray(arrays[name]), allow_pickle=False)
            info = zipfile.ZipInfo(f"{name}.npy", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, buffer.getvalue(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def load_contracts(
    grid_contract_path: str | Path = DEFAULT_GRID_CONTRACT,
    relation_contract_path: str | Path = DEFAULT_RELATION_CONTRACT,
) -> tuple[dict[str, Any], dict[str, Any]]:
    grid_contract = _json_load(Path(grid_contract_path))
    relation_contract = _json_load(Path(relation_contract_path))
    validate_contracts(grid_contract, relation_contract)
    return grid_contract, relation_contract


def validate_contracts(grid_contract: Mapping[str, Any], relation_contract: Mapping[str, Any]) -> None:
    if grid_contract.get("contract_version") != "relation_field_grid_rc1":
        raise RelationFieldGridError("unsupported grid contract")
    if relation_contract.get("contract_version") != "relation_field_rc1":
        raise RelationFieldGridError("unsupported relation-field parent contract")
    axes = grid_contract.get("axes", {})
    parent_axes = relation_contract.get("axes", {})
    expected = {
        "order": list(AXIS_NAMES),
        "bins": AXIS_BINS.tolist(),
        "shape": list(GRID_SHAPE),
        "cell_count": CELL_COUNT,
    }
    for key, value in expected.items():
        if axes.get(key) != value or parent_axes.get(key) != value:
            raise RelationFieldGridError(f"axis contract mismatch: {key}")
    if axes.get("flatten_order") != "C":
        raise RelationFieldGridError("flatten order must be C")
    if axes.get("axis_strides") != list(AXIS_STRIDES):
        raise RelationFieldGridError("axis strides mismatch")
    connectivity = grid_contract.get("connectivity", {})
    if int(connectivity.get("undirected_edge_count", -1)) != UNDIRECTED_EDGE_COUNT:
        raise RelationFieldGridError("undirected edge count mismatch")
    if int(connectivity.get("directed_neighbor_count", -1)) != DIRECTED_NEIGHBOR_COUNT:
        raise RelationFieldGridError("directed neighbor count mismatch")
    incidence = grid_contract.get("operators", {}).get("incidence", {})
    if incidence.get("shape") != [CELL_COUNT, UNDIRECTED_EDGE_COUNT]:
        raise RelationFieldGridError("incidence shape mismatch")
    if incidence.get("source_value") != -1.0 or incidence.get("target_value") != 1.0:
        raise RelationFieldGridError("incidence orientation mismatch")


def cell_id_from_indices(indices: Sequence[int]) -> int:
    if len(indices) != len(GRID_SHAPE):
        raise RelationFieldGridError("cell indices must contain five values")
    normalized = tuple(int(value) for value in indices)
    if any(value < 0 or value >= GRID_SHAPE[axis] for axis, value in enumerate(normalized)):
        raise RelationFieldGridError("cell index out of range")
    return int(np.ravel_multi_index(normalized, GRID_SHAPE, order="C"))


def indices_from_cell_id(cell_id: int) -> tuple[int, int, int, int, int]:
    value = int(cell_id)
    if value < 0 or value >= CELL_COUNT:
        raise RelationFieldGridError("cell id out of range")
    return tuple(int(item) for item in np.unravel_index(value, GRID_SHAPE, order="C"))


def _boundary_masks(indices: Sequence[int]) -> tuple[int, int, int, int]:
    lower_mask = 0
    upper_mask = 0
    degree = 0
    boundary_axis_count = 0
    for axis, index in enumerate(indices):
        if index == 0:
            lower_mask |= 1 << axis
            degree += 1
            boundary_axis_count += 1
        elif index == GRID_SHAPE[axis] - 1:
            upper_mask |= 1 << axis
            degree += 1
            boundary_axis_count += 1
        else:
            degree += 2
    return lower_mask, upper_mask, boundary_axis_count, degree


def generate_grid_arrays() -> dict[str, np.ndarray]:
    node_indices = np.empty((CELL_COUNT, len(GRID_SHAPE)), dtype=np.int16)
    node_values = np.empty((CELL_COUNT, len(GRID_SHAPE)), dtype=np.float64)
    lower_masks = np.empty(CELL_COUNT, dtype=np.uint8)
    upper_masks = np.empty(CELL_COUNT, dtype=np.uint8)
    boundary_axis_counts = np.empty(CELL_COUNT, dtype=np.uint8)
    degrees = np.empty(CELL_COUNT, dtype=np.uint8)

    edge_sources: list[int] = []
    edge_targets: list[int] = []
    edge_axes: list[int] = []
    edge_source_bins: list[int] = []
    edge_target_bins: list[int] = []

    for cell_id in range(CELL_COUNT):
        indices = indices_from_cell_id(cell_id)
        node_indices[cell_id] = indices
        node_values[cell_id] = AXIS_BINS[np.asarray(indices, dtype=np.int64)]
        lower, upper, boundary_count, degree = _boundary_masks(indices)
        lower_masks[cell_id] = lower
        upper_masks[cell_id] = upper
        boundary_axis_counts[cell_id] = boundary_count
        degrees[cell_id] = degree
        for axis, index in enumerate(indices):
            if index >= GRID_SHAPE[axis] - 1:
                continue
            target_indices = list(indices)
            target_indices[axis] += 1
            edge_sources.append(cell_id)
            edge_targets.append(cell_id_from_indices(target_indices))
            edge_axes.append(axis)
            edge_source_bins.append(index)
            edge_target_bins.append(index + 1)

    sources = np.asarray(edge_sources, dtype=np.int32)
    targets = np.asarray(edge_targets, dtype=np.int32)
    axes = np.asarray(edge_axes, dtype=np.int8)
    source_bins = np.asarray(edge_source_bins, dtype=np.int8)
    target_bins = np.asarray(edge_target_bins, dtype=np.int8)
    if sources.size != UNDIRECTED_EDGE_COUNT:
        raise RelationFieldGridError("generated edge count mismatch")

    neighbors: list[list[tuple[int, int, int, int]]] = [[] for _ in range(CELL_COUNT)]
    for edge_id, (source, target, axis) in enumerate(zip(sources, targets, axes, strict=True)):
        neighbors[int(source)].append((int(target), edge_id, int(axis), 1))
        neighbors[int(target)].append((int(source), edge_id, int(axis), -1))

    indptr = np.zeros(CELL_COUNT + 1, dtype=np.int32)
    neighbor_indices: list[int] = []
    neighbor_edge_ids: list[int] = []
    neighbor_axes: list[int] = []
    neighbor_directions: list[int] = []
    for cell_id, entries in enumerate(neighbors):
        entries.sort(key=lambda item: (item[0], item[2], item[1]))
        for neighbor, edge_id, axis, direction in entries:
            neighbor_indices.append(neighbor)
            neighbor_edge_ids.append(edge_id)
            neighbor_axes.append(axis)
            neighbor_directions.append(direction)
        indptr[cell_id + 1] = len(neighbor_indices)

    incidence_rows = np.empty(DIRECTED_NEIGHBOR_COUNT, dtype=np.int32)
    incidence_cols = np.empty(DIRECTED_NEIGHBOR_COUNT, dtype=np.int32)
    incidence_data = np.empty(DIRECTED_NEIGHBOR_COUNT, dtype=np.float64)
    incidence_rows[0::2] = sources
    incidence_rows[1::2] = targets
    incidence_cols[0::2] = np.arange(UNDIRECTED_EDGE_COUNT, dtype=np.int32)
    incidence_cols[1::2] = np.arange(UNDIRECTED_EDGE_COUNT, dtype=np.int32)
    incidence_data[0::2] = -1.0
    incidence_data[1::2] = 1.0

    return {
        "node_indices": node_indices,
        "node_values": node_values,
        "lower_boundary_mask": lower_masks,
        "upper_boundary_mask": upper_masks,
        "boundary_axis_count": boundary_axis_counts,
        "degree": degrees,
        "edge_source": sources,
        "edge_target": targets,
        "edge_axis": axes,
        "edge_source_bin": source_bins,
        "edge_target_bin": target_bins,
        "neighbor_indptr": indptr,
        "neighbor_indices": np.asarray(neighbor_indices, dtype=np.int32),
        "neighbor_edge_ids": np.asarray(neighbor_edge_ids, dtype=np.int32),
        "neighbor_axis": np.asarray(neighbor_axes, dtype=np.int8),
        "neighbor_direction": np.asarray(neighbor_directions, dtype=np.int8),
        "incidence_rows": incidence_rows,
        "incidence_cols": incidence_cols,
        "incidence_data": incidence_data,
    }


def apply_incidence(edge_flow: np.ndarray, arrays: Mapping[str, np.ndarray]) -> np.ndarray:
    flow = np.asarray(edge_flow, dtype=np.float64)
    if flow.shape != (UNDIRECTED_EDGE_COUNT,):
        raise RelationFieldGridError("edge flow shape mismatch")
    if not np.all(np.isfinite(flow)):
        raise RelationFieldGridError("edge flow contains non-finite values")
    rows = np.asarray(arrays["incidence_rows"], dtype=np.int64)
    cols = np.asarray(arrays["incidence_cols"], dtype=np.int64)
    data = np.asarray(arrays["incidence_data"], dtype=np.float64)
    delta = np.zeros(CELL_COUNT, dtype=np.float64)
    np.add.at(delta, rows, data * flow[cols])
    return delta


def _write_nodes_csv(path: Path, arrays: Mapping[str, np.ndarray]) -> None:
    index_fields = [f"{name}_index" for name in AXIS_NAMES]
    value_fields = [f"{name}_value" for name in AXIS_NAMES]
    fields = [
        "cell_id",
        *index_fields,
        *value_fields,
        "lower_boundary_mask",
        "upper_boundary_mask",
        "boundary_axis_count",
        "degree",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for cell_id in range(CELL_COUNT):
            row: dict[str, Any] = {"cell_id": cell_id}
            for axis, name in enumerate(AXIS_NAMES):
                row[f"{name}_index"] = int(arrays["node_indices"][cell_id, axis])
                row[f"{name}_value"] = format(float(arrays["node_values"][cell_id, axis]), ".17g")
            row.update(
                {
                    "lower_boundary_mask": int(arrays["lower_boundary_mask"][cell_id]),
                    "upper_boundary_mask": int(arrays["upper_boundary_mask"][cell_id]),
                    "boundary_axis_count": int(arrays["boundary_axis_count"][cell_id]),
                    "degree": int(arrays["degree"][cell_id]),
                }
            )
            writer.writerow(row)


def _write_edges_csv(path: Path, arrays: Mapping[str, np.ndarray]) -> None:
    fields = [
        "edge_id",
        "source_cell_id",
        "target_cell_id",
        "axis_index",
        "axis_name",
        "direction",
        "source_bin_index",
        "target_bin_index",
        "source_value",
        "target_value",
        "topological_distance",
        "coordinate_distance",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for edge_id in range(UNDIRECTED_EDGE_COUNT):
            axis = int(arrays["edge_axis"][edge_id])
            source_bin = int(arrays["edge_source_bin"][edge_id])
            target_bin = int(arrays["edge_target_bin"][edge_id])
            writer.writerow(
                {
                    "edge_id": edge_id,
                    "source_cell_id": int(arrays["edge_source"][edge_id]),
                    "target_cell_id": int(arrays["edge_target"][edge_id]),
                    "axis_index": axis,
                    "axis_name": AXIS_NAMES[axis],
                    "direction": 1,
                    "source_bin_index": source_bin,
                    "target_bin_index": target_bin,
                    "source_value": format(float(AXIS_BINS[source_bin]), ".17g"),
                    "target_value": format(float(AXIS_BINS[target_bin]), ".17g"),
                    "topological_distance": 1,
                    "coordinate_distance": format(float(AXIS_BINS[target_bin] - AXIS_BINS[source_bin]), ".17g"),
                }
            )


def _manifest_entries(root: Path, *, exclude: Iterable[str] = ()) -> list[dict[str, Any]]:
    excluded = set(exclude)
    entries: list[dict[str, Any]] = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        if relative in excluded:
            continue
        entries.append({"path": relative, "sha256": _sha256_file(path), "size_bytes": path.stat().st_size})
    return entries


def build_grid_artifact(
    output: str | Path,
    *,
    grid_contract_path: str | Path = DEFAULT_GRID_CONTRACT,
    relation_contract_path: str | Path = DEFAULT_RELATION_CONTRACT,
) -> Path:
    target = Path(output)
    if target.exists():
        raise RelationFieldGridError(f"output already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    grid_contract, relation_contract = load_contracts(grid_contract_path, relation_contract_path)
    arrays = generate_grid_arrays()
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp-", dir=target.parent))
    try:
        _json_dump(temporary / "contract.json", grid_contract)
        _json_dump(
            temporary / "metadata.json",
            {
                "artifact_version": "relation_field_grid_rc1",
                "parent_contract_version": relation_contract["contract_version"],
                "grid_contract_hash": _sha256_bytes(_canonical_json_bytes(grid_contract)),
                "parent_contract_hash": _sha256_bytes(_canonical_json_bytes(relation_contract)),
                "axis_order": list(AXIS_NAMES),
                "axis_bins": AXIS_BINS.tolist(),
                "shape": list(GRID_SHAPE),
                "cell_count": CELL_COUNT,
                "undirected_edge_count": UNDIRECTED_EDGE_COUNT,
                "directed_neighbor_count": DIRECTED_NEIGHBOR_COUNT,
                "flatten_order": "C",
                "canonical_edge_orientation": "lower_bin_to_higher_bin",
                "incidence_equation": "delta_mass = incidence @ edge_flow",
                "reads_canonical_gt_kt": False,
                "prediction_output": False,
            },
        )
        _write_nodes_csv(temporary / "nodes.csv", arrays)
        _write_edges_csv(temporary / "edges.csv", arrays)
        _write_deterministic_npz(
            temporary / "nodes.npz",
            {
                "indices": arrays["node_indices"],
                "values": arrays["node_values"],
                "lower_boundary_mask": arrays["lower_boundary_mask"],
                "upper_boundary_mask": arrays["upper_boundary_mask"],
                "boundary_axis_count": arrays["boundary_axis_count"],
                "degree": arrays["degree"],
                "axis_strides": np.asarray(AXIS_STRIDES, dtype=np.int32),
            },
        )
        _write_deterministic_npz(
            temporary / "neighbors.npz",
            {
                "indptr": arrays["neighbor_indptr"],
                "indices": arrays["neighbor_indices"],
                "edge_ids": arrays["neighbor_edge_ids"],
                "axis": arrays["neighbor_axis"],
                "direction": arrays["neighbor_direction"],
                "coordinate_distance": np.full(DIRECTED_NEIGHBOR_COUNT, 0.25, dtype=np.float64),
            },
        )
        _write_deterministic_npz(
            temporary / "incidence.npz",
            {
                "rows": arrays["incidence_rows"],
                "cols": arrays["incidence_cols"],
                "data": arrays["incidence_data"],
                "shape": np.asarray([CELL_COUNT, UNDIRECTED_EDGE_COUNT], dtype=np.int32),
                "edge_source": arrays["edge_source"],
                "edge_target": arrays["edge_target"],
                "edge_axis": arrays["edge_axis"],
            },
        )
        pre_validation = _validate_grid_artifact(temporary, verify_manifest=False)
        _json_dump(temporary / "validation.json", pre_validation)
        manifest = {
            "artifact_version": "relation_field_grid_rc1",
            "hash_algorithm": "sha256",
            "files": _manifest_entries(temporary, exclude={"manifest.json"}),
        }
        _json_dump(temporary / "manifest.json", manifest)
        os.replace(temporary, target)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return target


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _validate_manifest(root: Path) -> None:
    manifest = _json_load(root / "manifest.json")
    expected_paths = set()
    for entry in manifest.get("files", []):
        relative = str(entry["path"])
        expected_paths.add(relative)
        path = root / relative
        if not path.is_file():
            raise RelationFieldGridError(f"manifest file missing: {relative}")
        if path.stat().st_size != int(entry["size_bytes"]):
            raise RelationFieldGridError(f"manifest size mismatch: {relative}")
        if _sha256_file(path) != entry["sha256"]:
            raise RelationFieldGridError(f"manifest hash mismatch: {relative}")
    actual_paths = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    if expected_paths != actual_paths:
        raise RelationFieldGridError("manifest file set mismatch")


def _validate_grid_artifact(root: Path, *, verify_manifest: bool) -> dict[str, Any]:
    required = {
        "contract.json",
        "metadata.json",
        "nodes.csv",
        "edges.csv",
        "nodes.npz",
        "neighbors.npz",
        "incidence.npz",
        "validation.json",
        "manifest.json",
    }
    if not verify_manifest:
        required -= {"validation.json", "manifest.json"}
    missing = sorted(path for path in required if not (root / path).is_file())
    if missing:
        raise RelationFieldGridError(f"missing artifact files: {missing}")
    if verify_manifest:
        _validate_manifest(root)

    contract = _json_load(root / "contract.json")
    relation_stub = {
        "contract_version": "relation_field_rc1",
        "axes": {
            "order": list(AXIS_NAMES),
            "bins": AXIS_BINS.tolist(),
            "shape": list(GRID_SHAPE),
            "cell_count": CELL_COUNT,
        },
    }
    validate_contracts(contract, relation_stub)
    metadata = _json_load(root / "metadata.json")
    if metadata.get("reads_canonical_gt_kt") is not False:
        raise RelationFieldGridError("grid artifact must not read canonical G_t or K_t")

    with np.load(root / "nodes.npz", allow_pickle=False) as loaded:
        node_indices = loaded["indices"]
        node_values = loaded["values"]
        lower_masks = loaded["lower_boundary_mask"]
        upper_masks = loaded["upper_boundary_mask"]
        boundary_counts = loaded["boundary_axis_count"]
        degrees = loaded["degree"]
        strides = loaded["axis_strides"]
    if node_indices.shape != (CELL_COUNT, 5) or node_values.shape != (CELL_COUNT, 5):
        raise RelationFieldGridError("node array shape mismatch")
    if strides.tolist() != list(AXIS_STRIDES):
        raise RelationFieldGridError("stored axis strides mismatch")
    for cell_id in range(CELL_COUNT):
        indices = tuple(int(value) for value in node_indices[cell_id])
        if cell_id_from_indices(indices) != cell_id or indices_from_cell_id(cell_id) != indices:
            raise RelationFieldGridError("cell id roundtrip mismatch")
        if not np.array_equal(node_values[cell_id], AXIS_BINS[np.asarray(indices, dtype=np.int64)]):
            raise RelationFieldGridError("node coordinate value mismatch")
        lower, upper, boundary_count, degree = _boundary_masks(indices)
        if (int(lower_masks[cell_id]), int(upper_masks[cell_id]), int(boundary_counts[cell_id]), int(degrees[cell_id])) != (
            lower,
            upper,
            boundary_count,
            degree,
        ):
            raise RelationFieldGridError("boundary metadata mismatch")
    if dict(sorted(Counter(int(value) for value in degrees).items())) != DEGREE_DISTRIBUTION:
        raise RelationFieldGridError("degree distribution mismatch")

    node_rows = _read_csv(root / "nodes.csv")
    edge_rows = _read_csv(root / "edges.csv")
    if len(node_rows) != CELL_COUNT or len(edge_rows) != UNDIRECTED_EDGE_COUNT:
        raise RelationFieldGridError("CSV row count mismatch")
    if [int(row["cell_id"]) for row in node_rows] != list(range(CELL_COUNT)):
        raise RelationFieldGridError("node ids are not contiguous")

    sources = np.empty(UNDIRECTED_EDGE_COUNT, dtype=np.int32)
    targets = np.empty(UNDIRECTED_EDGE_COUNT, dtype=np.int32)
    axes = np.empty(UNDIRECTED_EDGE_COUNT, dtype=np.int8)
    edge_pairs: set[tuple[int, int]] = set()
    for expected_edge_id, row in enumerate(edge_rows):
        edge_id = int(row["edge_id"])
        source = int(row["source_cell_id"])
        target = int(row["target_cell_id"])
        axis = int(row["axis_index"])
        if edge_id != expected_edge_id or row["axis_name"] != AXIS_NAMES[axis] or int(row["direction"]) != 1:
            raise RelationFieldGridError("edge identity mismatch")
        source_indices = tuple(int(value) for value in node_indices[source])
        target_indices = tuple(int(value) for value in node_indices[target])
        differences = [target_indices[i] - source_indices[i] for i in range(5)]
        if differences.count(1) != 1 or any(value not in (0, 1) for value in differences) or differences[axis] != 1:
            raise RelationFieldGridError("edge is not a one-axis one-bin positive step")
        if target - source != AXIS_STRIDES[axis]:
            raise RelationFieldGridError("edge stride mismatch")
        if (source, target) in edge_pairs:
            raise RelationFieldGridError("duplicate canonical edge")
        edge_pairs.add((source, target))
        if float(row["coordinate_distance"]) != 0.25 or int(row["topological_distance"]) != 1:
            raise RelationFieldGridError("edge distance mismatch")
        sources[edge_id] = source
        targets[edge_id] = target
        axes[edge_id] = axis

    with np.load(root / "neighbors.npz", allow_pickle=False) as loaded:
        indptr = loaded["indptr"]
        neighbor_indices = loaded["indices"]
        neighbor_edge_ids = loaded["edge_ids"]
        neighbor_axes = loaded["axis"]
        neighbor_directions = loaded["direction"]
        coordinate_distance = loaded["coordinate_distance"]
    if indptr.shape != (CELL_COUNT + 1,) or int(indptr[0]) != 0 or int(indptr[-1]) != DIRECTED_NEIGHBOR_COUNT:
        raise RelationFieldGridError("CSR indptr mismatch")
    if any(array.shape != (DIRECTED_NEIGHBOR_COUNT,) for array in (neighbor_indices, neighbor_edge_ids, neighbor_axes, neighbor_directions, coordinate_distance)):
        raise RelationFieldGridError("CSR payload shape mismatch")
    if not np.all(coordinate_distance == 0.25):
        raise RelationFieldGridError("CSR coordinate distance mismatch")
    for cell_id in range(CELL_COUNT):
        start, end = int(indptr[cell_id]), int(indptr[cell_id + 1])
        if end - start != int(degrees[cell_id]):
            raise RelationFieldGridError("CSR degree mismatch")
        segment_neighbors = neighbor_indices[start:end]
        if segment_neighbors.tolist() != sorted(int(value) for value in segment_neighbors):
            raise RelationFieldGridError("CSR neighbors are not sorted")
        for position in range(start, end):
            neighbor = int(neighbor_indices[position])
            edge_id = int(neighbor_edge_ids[position])
            axis = int(neighbor_axes[position])
            direction = int(neighbor_directions[position])
            if axis != int(axes[edge_id]):
                raise RelationFieldGridError("CSR edge axis mismatch")
            expected = (int(targets[edge_id]), 1) if cell_id == int(sources[edge_id]) else (int(sources[edge_id]), -1)
            if (neighbor, direction) != expected:
                raise RelationFieldGridError("CSR edge orientation mismatch")

    visited = np.zeros(CELL_COUNT, dtype=np.bool_)
    queue: deque[int] = deque([0])
    visited[0] = True
    while queue:
        cell_id = queue.popleft()
        for position in range(int(indptr[cell_id]), int(indptr[cell_id + 1])):
            neighbor = int(neighbor_indices[position])
            if not visited[neighbor]:
                visited[neighbor] = True
                queue.append(neighbor)
    if not bool(np.all(visited)):
        raise RelationFieldGridError("grid graph is disconnected")

    with np.load(root / "incidence.npz", allow_pickle=False) as loaded:
        rows = loaded["rows"]
        cols = loaded["cols"]
        data = loaded["data"]
        shape = loaded["shape"]
        stored_sources = loaded["edge_source"]
        stored_targets = loaded["edge_target"]
        stored_axes = loaded["edge_axis"]
    if shape.tolist() != [CELL_COUNT, UNDIRECTED_EDGE_COUNT]:
        raise RelationFieldGridError("incidence stored shape mismatch")
    if any(array.shape != (DIRECTED_NEIGHBOR_COUNT,) for array in (rows, cols, data)):
        raise RelationFieldGridError("incidence COO length mismatch")
    if not np.array_equal(stored_sources, sources) or not np.array_equal(stored_targets, targets) or not np.array_equal(stored_axes, axes):
        raise RelationFieldGridError("incidence edge payload mismatch")
    if not np.array_equal(rows[0::2], sources) or not np.array_equal(rows[1::2], targets):
        raise RelationFieldGridError("incidence rows mismatch")
    expected_cols = np.arange(UNDIRECTED_EDGE_COUNT, dtype=np.int32)
    if not np.array_equal(cols[0::2], expected_cols) or not np.array_equal(cols[1::2], expected_cols):
        raise RelationFieldGridError("incidence columns mismatch")
    if not np.all(data[0::2] == -1.0) or not np.all(data[1::2] == 1.0):
        raise RelationFieldGridError("incidence signs mismatch")
    if not np.allclose(np.bincount(cols, weights=data, minlength=UNDIRECTED_EDGE_COUNT), 0.0):
        raise RelationFieldGridError("incidence column sums are not zero")

    return {
        "rf2_grid_gate": "passed",
        "contract_version": contract["contract_version"],
        "cell_count": CELL_COUNT,
        "undirected_edge_count": UNDIRECTED_EDGE_COUNT,
        "directed_neighbor_count": DIRECTED_NEIGHBOR_COUNT,
        "degree_distribution": {str(key): value for key, value in DEGREE_DISTRIBUTION.items()},
        "graph_connected": True,
        "cell_id_roundtrip": True,
        "edge_locality": "single_axis_single_bin",
        "adjacency_storage": "CSR",
        "incidence_storage": "COO",
        "incidence_orientation": "source_minus_one_target_plus_one",
        "reads_canonical_gt_kt": False,
        "prediction_performed": False,
        "flow_inversion_performed": False,
    }


def validate_grid_artifact(input_path: str | Path) -> dict[str, Any]:
    root = Path(input_path)
    result = _validate_grid_artifact(root, verify_manifest=True)
    persisted = _json_load(root / "validation.json")
    if persisted != result:
        raise RelationFieldGridError("persisted validation result mismatch")
    return result


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="build the deterministic RF-2 grid artifact")
    build.add_argument("--output", required=True)
    build.add_argument("--grid-contract", default=str(DEFAULT_GRID_CONTRACT))
    build.add_argument("--relation-contract", default=str(DEFAULT_RELATION_CONTRACT))
    validate = subparsers.add_parser("validate", help="validate an RF-2 grid artifact")
    validate.add_argument("--input", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "build":
        output = build_grid_artifact(
            args.output,
            grid_contract_path=args.grid_contract,
            relation_contract_path=args.relation_contract,
        )
        print(json.dumps({"output": str(output), "status": "built"}, ensure_ascii=False, sort_keys=True))
        return 0
    result = validate_grid_artifact(args.input)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
