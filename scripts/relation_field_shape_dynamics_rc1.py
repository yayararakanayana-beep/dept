"""固定5軸 動的関係場 RF-7: 分布形状と流路幅の時間変化。"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from relation_field_hodge_decomposition_rc1 import (
    _load_grid_with_indices,
    validate_hodge_artifact,
)
from relation_field_single_transition_rc1 import load_contract as load_rf3_contract
from relation_field_temporal_consistency_rc1 import (
    _load_history_window,
    validate_temporal_relation_field,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "configs" / "relation_field_shape_dynamics_rc1.json"
CELL_COUNT = 3125
EDGE_COUNT = 12500
AXIS_COUNT = 5


class RelationFieldShapeError(ValueError):
    """RF-7契約、親成果物、形状計測、成果物の不整合。"""


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_npz(path: Path, arrays: Mapping[str, np.ndarray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(arrays):
            buffer = io.BytesIO()
            np.save(buffer, np.asarray(arrays[name]), allow_pickle=False)
            info = zipfile.ZipInfo(f"{name}.npy", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, buffer.getvalue(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def _load_npz(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as loaded:
        return {name: loaded[name].copy() for name in loaded.files}


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


def load_contract(path: str | Path = DEFAULT_CONTRACT) -> dict[str, Any]:
    contract = _load_json(Path(path))
    validate_contract(contract)
    return contract


def validate_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("contract_version") != "relation_field_shape_dynamics_rc1":
        raise RelationFieldShapeError("unsupported RF-7 contract")
    frame = contract.get("frame_shape_metrics", {})
    if float(frame.get("active_cell_absolute_floor", 0.0)) <= 0.0:
        raise RelationFieldShapeError("RF-7 active-cell floor must be positive")
    if not 0.0 < float(frame.get("major_component_minimum_mass", 0.0)) <= 1.0:
        raise RelationFieldShapeError("RF-7 major-component mass threshold mismatch")
    flow = contract.get("flow_channel_metrics", {})
    if flow.get("duplicate_candidate_ids_must_be_removed_before_aggregation") is not True:
        raise RelationFieldShapeError("RF-7 candidate deduplication must be required")
    if contract.get("semantic_limits", {}).get("irreversibility_or_risk_not_assigned") is not True:
        raise RelationFieldShapeError("RF-7 must not assign risk semantics")


def _verify_manifest(root: Path) -> None:
    manifest = _load_json(root / "manifest.json")
    expected: set[str] = set()
    for entry in manifest.get("files", []):
        relative = str(entry["path"])
        expected.add(relative)
        path = root / relative
        if not path.is_file() or path.stat().st_size != int(entry["size_bytes"]) or _sha256_file(path) != entry["sha256"]:
            raise RelationFieldShapeError(f"manifest mismatch: {relative}")
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    if expected != actual:
        raise RelationFieldShapeError("manifest file set mismatch")


def _entropy(values: np.ndarray) -> float:
    positive = np.asarray(values, dtype=np.float64)
    positive = positive[positive > 0.0]
    return 0.0 if positive.size == 0 else float(-np.sum(positive * np.log(positive), dtype=np.float64))


def _component_rows(
    mass: np.ndarray,
    grid: Mapping[str, Any],
    settings: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    flat = np.asarray(mass, dtype=np.float64).reshape(-1, order="C")
    peak = float(np.max(flat))
    threshold = max(
        float(settings["active_cell_absolute_floor"]),
        peak * float(settings["active_cell_relative_to_peak_floor"]),
    )
    active = flat >= threshold
    parent = np.arange(CELL_COUNT, dtype=np.int32)
    rank = np.zeros(CELL_COUNT, dtype=np.int8)

    def find(value: int) -> int:
        root = value
        while int(parent[root]) != root:
            root = int(parent[root])
        while int(parent[value]) != value:
            next_value = int(parent[value])
            parent[value] = root
            value = next_value
        return root

    def union(left: int, right: int) -> None:
        root_left, root_right = find(left), find(right)
        if root_left == root_right:
            return
        if int(rank[root_left]) < int(rank[root_right]):
            root_left, root_right = root_right, root_left
        parent[root_right] = root_left
        if int(rank[root_left]) == int(rank[root_right]):
            rank[root_left] += 1

    sources = np.asarray(grid["edge_source"], dtype=np.int32)
    targets = np.asarray(grid["edge_target"], dtype=np.int32)
    for source, target in zip(sources, targets, strict=True):
        left, right = int(source), int(target)
        if bool(active[left]) and bool(active[right]):
            union(left, right)

    groups: dict[int, list[int]] = {}
    for cell_id in np.flatnonzero(active):
        groups.setdefault(find(int(cell_id)), []).append(int(cell_id))
    coordinates = np.asarray(grid["node_values"], dtype=np.float64)
    rows: list[dict[str, Any]] = []
    for cell_ids in groups.values():
        ids = np.asarray(sorted(cell_ids), dtype=np.int32)
        weights = flat[ids]
        component_mass = float(np.sum(weights, dtype=np.float64))
        centroid = (
            np.sum(weights[:, None] * coordinates[ids], axis=0) / component_mass
            if component_mass > 0.0
            else np.zeros(AXIS_COUNT, dtype=np.float64)
        )
        rows.append(
            {
                "minimum_cell_id": int(ids[0]),
                "cell_count": int(ids.size),
                "mass": component_mass,
                "centroid": centroid.tolist(),
            }
        )
    rows.sort(key=lambda item: (-float(item["mass"]), int(item["minimum_cell_id"])))
    major_threshold = float(settings["major_component_minimum_mass"])
    major = [row for row in rows if float(row["mass"]) >= major_threshold]
    component_masses = np.asarray([float(row["mass"]) for row in rows], dtype=np.float64)
    active_mass = float(np.sum(component_masses, dtype=np.float64))
    normalized = component_masses / active_mass if active_mass > 0.0 else component_masses
    metrics = {
        "active_threshold": threshold,
        "active_cell_count": int(np.count_nonzero(active)),
        "component_count": len(rows),
        "major_component_count": len(major),
        "largest_component_mass": 0.0 if not rows else float(rows[0]["mass"]),
        "component_mass_entropy": _entropy(normalized),
        "major_component_centroids": [row["centroid"] for row in major],
    }
    return metrics, rows


def compute_frame_shape_metrics(
    distribution: np.ndarray,
    grid: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    flat = np.asarray(distribution, dtype=np.float64).reshape(-1, order="C")
    if flat.shape != (CELL_COUNT,) or not np.all(np.isfinite(flat)) or float(np.min(flat)) < 0.0:
        raise RelationFieldShapeError("RF-7 frame distribution mismatch")
    total = float(np.sum(flat, dtype=np.float64))
    if abs(total - 1.0) > 1e-9:
        raise RelationFieldShapeError("RF-7 frame distribution must sum to one")
    coordinates = np.asarray(grid["node_values"], dtype=np.float64)
    centroid = np.sum(flat[:, None] * coordinates, axis=0)
    centered = coordinates - centroid
    covariance = (centered * flat[:, None]).T @ centered
    covariance = 0.5 * (covariance + covariance.T)
    eigenvalues = np.linalg.eigvalsh(covariance)[::-1]
    eigenvalues[np.abs(eigenvalues) < 1e-15] = 0.0
    entropy = _entropy(flat)
    l2 = float(np.dot(flat, flat))
    component_metrics, components = _component_rows(flat, grid, contract["frame_shape_metrics"])
    indices = np.asarray(grid["node_indices"], dtype=np.int16)
    lower = np.stack([indices[:, axis] == 0 for axis in range(AXIS_COUNT)], axis=1)
    upper = np.stack([indices[:, axis] == 4 for axis in range(AXIS_COUNT)], axis=1)
    any_boundary = np.any(lower | upper, axis=1)
    metrics = {
        "centroid": centroid,
        "covariance": covariance,
        "axis_variance": np.diag(covariance).copy(),
        "covariance_eigenvalues": eigenvalues,
        "total_variance": float(np.trace(covariance)),
        "entropy": entropy,
        "normalized_entropy": entropy / math.log(CELL_COUNT),
        "effective_support": float(math.exp(entropy)),
        "participation_number": 1.0 / l2,
        "l2_concentration": l2,
        "peak_mass": float(np.max(flat)),
        "lower_boundary_mass": np.sum(flat[:, None] * lower, axis=0),
        "upper_boundary_mass": np.sum(flat[:, None] * upper, axis=0),
        "any_boundary_mass": float(np.sum(flat[any_boundary], dtype=np.float64)),
        **component_metrics,
    }
    return metrics, components


def _stack_frame_metrics(
    frames: Sequence[np.ndarray],
    times: Sequence[int],
    grid: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> tuple[dict[str, np.ndarray], dict[str, Any], list[dict[str, Any]]]:
    computed: list[dict[str, Any]] = []
    component_payload: list[dict[str, Any]] = []
    for time_value, frame in zip(times, frames, strict=True):
        metrics, components = compute_frame_shape_metrics(frame, grid, contract)
        computed.append(metrics)
        component_payload.append(
            {
                "t": int(time_value),
                "active_threshold": float(metrics["active_threshold"]),
                "component_count": int(metrics["component_count"]),
                "major_component_count": int(metrics["major_component_count"]),
                "components": components,
            }
        )
    arrays = {
        "times": np.asarray(times, dtype=np.int32),
        "centroid": np.stack([item["centroid"] for item in computed]),
        "covariance": np.stack([item["covariance"] for item in computed]),
        "axis_variance": np.stack([item["axis_variance"] for item in computed]),
        "covariance_eigenvalues": np.stack([item["covariance_eigenvalues"] for item in computed]),
        "total_variance": np.asarray([item["total_variance"] for item in computed], dtype=np.float64),
        "entropy": np.asarray([item["entropy"] for item in computed], dtype=np.float64),
        "normalized_entropy": np.asarray([item["normalized_entropy"] for item in computed], dtype=np.float64),
        "effective_support": np.asarray([item["effective_support"] for item in computed], dtype=np.float64),
        "participation_number": np.asarray([item["participation_number"] for item in computed], dtype=np.float64),
        "l2_concentration": np.asarray([item["l2_concentration"] for item in computed], dtype=np.float64),
        "peak_mass": np.asarray([item["peak_mass"] for item in computed], dtype=np.float64),
        "active_threshold": np.asarray([item["active_threshold"] for item in computed], dtype=np.float64),
        "active_cell_count": np.asarray([item["active_cell_count"] for item in computed], dtype=np.int32),
        "lower_boundary_mass": np.stack([item["lower_boundary_mass"] for item in computed]),
        "upper_boundary_mass": np.stack([item["upper_boundary_mass"] for item in computed]),
        "any_boundary_mass": np.asarray([item["any_boundary_mass"] for item in computed], dtype=np.float64),
        "component_count": np.asarray([item["component_count"] for item in computed], dtype=np.int32),
        "major_component_count": np.asarray([item["major_component_count"] for item in computed], dtype=np.int32),
        "largest_component_mass": np.asarray([item["largest_component_mass"] for item in computed], dtype=np.float64),
        "component_mass_entropy": np.asarray([item["component_mass_entropy"] for item in computed], dtype=np.float64),
    }
    return arrays, {"frames": component_payload}, computed


def _transition_label(
    index: int,
    frame_arrays: Mapping[str, np.ndarray],
    contract: Mapping[str, Any],
) -> dict[str, bool]:
    settings = contract["transition_shape_metrics"]
    scalar_tolerance = float(settings["shape_scalar_tolerance"])
    support_tolerance = float(settings["effective_support_tolerance"])
    component_mass_minimum = float(settings["component_mass_change_minimum"])
    total_variance_delta = float(frame_arrays["total_variance"][index + 1] - frame_arrays["total_variance"][index])
    entropy_delta = float(frame_arrays["entropy"][index + 1] - frame_arrays["entropy"][index])
    effective_delta = float(frame_arrays["effective_support"][index + 1] - frame_arrays["effective_support"][index])
    participation_delta = float(frame_arrays["participation_number"][index + 1] - frame_arrays["participation_number"][index])
    l2_delta = float(frame_arrays["l2_concentration"][index + 1] - frame_arrays["l2_concentration"][index])
    peak_delta = float(frame_arrays["peak_mass"][index + 1] - frame_arrays["peak_mass"][index])
    major_delta = int(frame_arrays["major_component_count"][index + 1] - frame_arrays["major_component_count"][index])
    largest_delta = float(frame_arrays["largest_component_mass"][index + 1] - frame_arrays["largest_component_mass"][index])
    component_entropy_delta = float(frame_arrays["component_mass_entropy"][index + 1] - frame_arrays["component_mass_entropy"][index])
    centroid_shift = frame_arrays["centroid"][index + 1] - frame_arrays["centroid"][index]
    translation_only = (
        float(np.linalg.norm(centroid_shift)) > scalar_tolerance
        and abs(total_variance_delta) <= scalar_tolerance
        and abs(entropy_delta) <= scalar_tolerance
        and abs(effective_delta) <= support_tolerance
        and abs(participation_delta) <= support_tolerance
        and abs(l2_delta) <= scalar_tolerance
        and abs(peak_delta) <= scalar_tolerance
        and major_delta == 0
    )
    return {
        "translation_without_detected_shape_change": translation_only,
        "expansion_candidate": (
            total_variance_delta > scalar_tolerance
            and entropy_delta > scalar_tolerance
            and effective_delta > support_tolerance
            and participation_delta > support_tolerance
        ),
        "contraction_candidate": (
            total_variance_delta < -scalar_tolerance
            and entropy_delta < -scalar_tolerance
            and effective_delta < -support_tolerance
            and participation_delta < -support_tolerance
        ),
        "dispersion_candidate": (
            entropy_delta > scalar_tolerance
            and l2_delta < -scalar_tolerance
            and peak_delta < -scalar_tolerance
        ),
        "concentration_candidate": (
            entropy_delta < -scalar_tolerance
            and l2_delta > scalar_tolerance
            and peak_delta > scalar_tolerance
        ),
        "split_candidate": major_delta > 0 and largest_delta <= -component_mass_minimum,
        "merge_candidate": major_delta < 0 and largest_delta >= component_mass_minimum,
        "fragmentation_candidate": major_delta > 0 or component_entropy_delta > scalar_tolerance,
        "coalescence_candidate": major_delta < 0 or component_entropy_delta < -scalar_tolerance,
    }


def _stack_transition_metrics(
    frames: Sequence[np.ndarray],
    frame_arrays: Mapping[str, np.ndarray],
    grid: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    transition_count = len(frames) - 1
    indices = np.asarray(grid["node_indices"], dtype=np.int16)
    any_boundary = np.any((indices == 0) | (indices == 4), axis=1)
    labels: list[dict[str, Any]] = []
    metrics: dict[str, list[Any]] = {
        "centroid_shift": [],
        "centroid_shift_norm": [],
        "covariance_delta": [],
        "axis_variance_delta": [],
        "total_variance_delta": [],
        "entropy_delta": [],
        "effective_support_delta": [],
        "participation_delta": [],
        "l2_concentration_delta": [],
        "peak_mass_delta": [],
        "active_cell_count_delta": [],
        "distribution_overlap": [],
        "total_variation_distance": [],
        "boundary_mass_delta": [],
        "boundary_cell_overlap": [],
        "major_component_count_delta": [],
        "largest_component_mass_delta": [],
        "component_mass_entropy_delta": [],
    }
    for index in range(transition_count):
        before = np.asarray(frames[index], dtype=np.float64).reshape(-1, order="C")
        after = np.asarray(frames[index + 1], dtype=np.float64).reshape(-1, order="C")
        centroid_shift = frame_arrays["centroid"][index + 1] - frame_arrays["centroid"][index]
        metrics["centroid_shift"].append(centroid_shift)
        metrics["centroid_shift_norm"].append(float(np.linalg.norm(centroid_shift)))
        metrics["covariance_delta"].append(frame_arrays["covariance"][index + 1] - frame_arrays["covariance"][index])
        metrics["axis_variance_delta"].append(frame_arrays["axis_variance"][index + 1] - frame_arrays["axis_variance"][index])
        for key in (
            "total_variance", "entropy", "effective_support", "participation_number",
            "l2_concentration", "peak_mass", "active_cell_count", "any_boundary_mass",
            "major_component_count", "largest_component_mass", "component_mass_entropy",
        ):
            value = frame_arrays[key][index + 1] - frame_arrays[key][index]
            output_key = {
                "participation_number": "participation_delta",
                "any_boundary_mass": "boundary_mass_delta",
            }.get(key, f"{key}_delta")
            metrics[output_key].append(value)
        metrics["distribution_overlap"].append(float(np.sum(np.minimum(before, after), dtype=np.float64)))
        metrics["total_variation_distance"].append(float(0.5 * np.sum(np.abs(after - before), dtype=np.float64)))
        metrics["boundary_cell_overlap"].append(float(np.sum(np.minimum(before, after)[any_boundary], dtype=np.float64)))
        labels.append({"transition_index": index, **_transition_label(index, frame_arrays, contract)})
    arrays: dict[str, np.ndarray] = {
        "transition_times": np.asarray(frame_arrays["times"][1:], dtype=np.int32),
    }
    for key, values in metrics.items():
        dtype = np.int32 if key in {"active_cell_count_delta", "major_component_count_delta"} else np.float64
        arrays[key] = np.asarray(values, dtype=dtype)
    return arrays, {"classification_is_diagnostic_only": True, "transitions": labels}


def _load_parent_artifacts(
    rf5_root: Path,
    rf6_root: Path,
    grid_root: Path,
) -> dict[str, Any]:
    validate_temporal_relation_field(rf5_root, grid_root)
    validate_hodge_artifact(rf6_root, rf5_root, grid_root)
    rf5_identity = _load_json(rf5_root / "identity.json")
    rf5_paths = _load_json(rf5_root / "temporal_paths.json")
    rf6_identity = _load_json(rf6_root / "identity.json")
    if rf6_identity.get("rf5_relation_field_id") != rf5_identity.get("relation_field_id"):
        raise RelationFieldShapeError("RF-7 RF-5/RF-6 relation-field identity mismatch")
    rf5_manifest_hash = _sha256_file(rf5_root / "manifest.json")
    rf6_manifest_hash = _sha256_file(rf6_root / "manifest.json")
    if rf6_identity.get("rf5_manifest_hash") != rf5_manifest_hash:
        raise RelationFieldShapeError("RF-7 RF-6 does not reference the supplied RF-5 manifest")
    with np.load(rf5_root / "candidate_flows.npz", allow_pickle=False) as loaded:
        offsets = loaded["candidate_offsets"].copy().astype(np.int32)
        candidate_flow = loaded["candidate_net_flow"].copy().astype(np.float64)
    with np.load(rf5_root / "representative_flow.npz", allow_pickle=False) as loaded:
        transition_times = loaded["transition_times"].copy().astype(np.int32)
    with np.load(rf6_root / "candidate_components.npz", allow_pickle=False) as loaded:
        gradient = loaded["gradient_flow"].copy().astype(np.float64)
        circulation = loaded["circulation_flow"].copy().astype(np.float64)
        node_potential = loaded["node_potential"].copy().astype(np.float64)
        rf6_input = loaded["input_flow"].copy().astype(np.float64)
    if not np.array_equal(candidate_flow, rf6_input):
        raise RelationFieldShapeError("RF-7 RF-6 candidate inputs do not match RF-5")
    optimal_paths = [[int(value) for value in path] for path in rf5_paths["optimal_paths"]]
    transition_count = int(rf5_identity["transition_count"])
    if offsets.shape != (transition_count + 1,) or transition_times.shape != (transition_count,):
        raise RelationFieldShapeError("RF-7 RF-5 transition payload mismatch")
    if any(len(path) != transition_count for path in optimal_paths):
        raise RelationFieldShapeError("RF-7 RF-5 optimal path length mismatch")
    return {
        "rf5_identity": rf5_identity,
        "rf6_identity": rf6_identity,
        "rf5_manifest_hash": rf5_manifest_hash,
        "rf6_manifest_hash": rf6_manifest_hash,
        "offsets": offsets,
        "candidate_flow": candidate_flow,
        "gradient_flow": gradient,
        "circulation_flow": circulation,
        "node_potential": node_potential,
        "transition_times": transition_times,
        "optimal_paths": optimal_paths,
    }


def _single_flow_metrics(
    flow: np.ndarray,
    gradient: np.ndarray,
    circulation: np.ndarray,
    potential: np.ndarray,
    before: np.ndarray,
    after: np.ndarray,
    grid: Mapping[str, Any],
    threshold: float,
) -> dict[str, Any]:
    absolute = np.abs(flow)
    total = float(np.sum(absolute, dtype=np.float64))
    active = absolute > threshold
    if total > threshold:
        weights = absolute[active] / total
        edge_entropy = _entropy(weights)
        effective_edge_support = float(math.exp(edge_entropy))
        edge_participation = 1.0 / float(np.dot(weights, weights))
        maximum_edge_fraction = float(np.max(weights))
    else:
        edge_entropy = 0.0
        effective_edge_support = 0.0
        edge_participation = 0.0
        maximum_edge_fraction = 0.0
    axes = np.asarray(grid["edge_axis"], dtype=np.int8)
    sources = np.asarray(grid["edge_source"], dtype=np.int32)
    node_indices = np.asarray(grid["node_indices"], dtype=np.int16)
    axis_throughput = np.asarray([
        np.sum(absolute[axes == axis], dtype=np.float64) for axis in range(AXIS_COUNT)
    ])
    lower_inward = np.zeros(AXIS_COUNT, dtype=np.float64)
    upper_inward = np.zeros(AXIS_COUNT, dtype=np.float64)
    for axis in range(AXIS_COUNT):
        axis_edges = axes == axis
        source_bins = node_indices[sources, axis]
        lower_inward[axis] = float(np.sum(flow[axis_edges & (source_bins == 0)], dtype=np.float64))
        upper_inward[axis] = float(-np.sum(flow[axis_edges & (source_bins == 3)], dtype=np.float64))
    before_flat = np.asarray(before, dtype=np.float64).reshape(-1, order="C")
    after_flat = np.asarray(after, dtype=np.float64).reshape(-1, order="C")
    source_potential = float(np.dot(before_flat, potential))
    target_potential = float(np.dot(after_flat, potential))
    return {
        "total_absolute_flow": total,
        "active_edge_count": int(np.count_nonzero(active)),
        "edge_entropy": edge_entropy,
        "effective_edge_support": effective_edge_support,
        "edge_participation_number": edge_participation,
        "maximum_edge_fraction": maximum_edge_fraction,
        "axis_absolute_throughput": axis_throughput,
        "lower_boundary_inward_flow": lower_inward,
        "upper_boundary_inward_flow": upper_inward,
        "gradient_energy": float(np.dot(gradient, gradient)),
        "circulation_energy": float(np.dot(circulation, circulation)),
        "source_mass_weighted_potential": source_potential,
        "target_mass_weighted_potential": target_potential,
        "potential_transport_difference": target_potential - source_potential,
    }


def _aggregate_unique_candidate_metrics(
    frames: Sequence[np.ndarray],
    parent: Mapping[str, Any],
    frame_arrays: Mapping[str, np.ndarray],
    transition_arrays: Mapping[str, np.ndarray],
    grid: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray], dict[str, np.ndarray], dict[str, Any]]:
    transition_count = len(frames) - 1
    threshold = float(contract["flow_channel_metrics"]["flow_activation_threshold"])
    offsets = np.asarray(parent["offsets"], dtype=np.int32)
    scalar_keys = (
        "total_absolute_flow", "active_edge_count", "edge_entropy", "effective_edge_support",
        "edge_participation_number", "maximum_edge_fraction", "gradient_energy",
        "circulation_energy", "source_mass_weighted_potential", "target_mass_weighted_potential",
        "potential_transport_difference",
    )
    vector_keys = (
        "axis_absolute_throughput", "lower_boundary_inward_flow", "upper_boundary_inward_flow",
    )
    collected: dict[str, list[np.ndarray]] = {
        **{f"{key}_{stat}": [] for key in scalar_keys for stat in ("minimum", "maximum", "mean")},
        **{f"{key}_{stat}": [] for key in vector_keys for stat in ("minimum", "maximum", "mean")},
    }
    unique_counts: list[int] = []
    weighted_inward_minimum: list[float] = []
    weighted_inward_maximum: list[float] = []
    weighted_inward_mean: list[float] = []
    channel_rows: list[dict[str, Any]] = []
    per_transition_means: list[dict[str, float]] = []
    for transition in range(transition_count):
        local_ids = sorted({int(path[transition]) for path in parent["optimal_paths"]})
        flat_ids = [int(offsets[transition]) + local_id for local_id in local_ids]
        unique_counts.append(len(flat_ids))
        candidate_metrics = [
            _single_flow_metrics(
                parent["candidate_flow"][flat_id],
                parent["gradient_flow"][flat_id],
                parent["circulation_flow"][flat_id],
                parent["node_potential"][flat_id],
                frames[transition],
                frames[transition + 1],
                grid,
                threshold,
            )
            for flat_id in flat_ids
        ]
        for key in scalar_keys:
            values = np.asarray([metric[key] for metric in candidate_metrics], dtype=np.float64)
            collected[f"{key}_minimum"].append(np.min(values))
            collected[f"{key}_maximum"].append(np.max(values))
            collected[f"{key}_mean"].append(np.mean(values))
        for key in vector_keys:
            values = np.stack([metric[key] for metric in candidate_metrics])
            collected[f"{key}_minimum"].append(np.min(values, axis=0))
            collected[f"{key}_maximum"].append(np.max(values, axis=0))
            collected[f"{key}_mean"].append(np.mean(values, axis=0))
        lower_mass = frame_arrays["lower_boundary_mass"][transition]
        upper_mass = frame_arrays["upper_boundary_mass"][transition]
        weighted = np.asarray([
            float(np.dot(lower_mass, metric["lower_boundary_inward_flow"]) + np.dot(upper_mass, metric["upper_boundary_inward_flow"]))
            for metric in candidate_metrics
        ])
        weighted_inward_minimum.append(float(np.min(weighted)))
        weighted_inward_maximum.append(float(np.max(weighted)))
        weighted_inward_mean.append(float(np.mean(weighted)))
        per_transition_means.append(
            {
                "effective_edge_support": float(np.mean([metric["effective_edge_support"] for metric in candidate_metrics])),
                "maximum_edge_fraction": float(np.mean([metric["maximum_edge_fraction"] for metric in candidate_metrics])),
            }
        )
    change_tolerance = float(contract["flow_channel_metrics"]["channel_change_tolerance"])
    for transition, means in enumerate(per_transition_means):
        if transition == 0:
            narrowing = widening = False
        else:
            support_delta = means["effective_edge_support"] - per_transition_means[transition - 1]["effective_edge_support"]
            maximum_fraction_delta = means["maximum_edge_fraction"] - per_transition_means[transition - 1]["maximum_edge_fraction"]
            narrowing = support_delta < -change_tolerance and maximum_fraction_delta > change_tolerance
            widening = support_delta > change_tolerance and maximum_fraction_delta < -change_tolerance
        channel_rows.append(
            {
                "transition_index": transition,
                "flow_channel_narrowing_candidate": narrowing,
                "flow_channel_widening_candidate": widening,
            }
        )
    flow_arrays: dict[str, np.ndarray] = {
        "transition_times": np.asarray(parent["transition_times"], dtype=np.int32),
        "unique_candidate_count": np.asarray(unique_counts, dtype=np.int32),
    }
    for key, values in collected.items():
        flow_arrays[key] = np.asarray(values, dtype=np.float64)
    boundary_persistence = np.minimum(frame_arrays["any_boundary_mass"][:-1], frame_arrays["any_boundary_mass"][1:])
    boundary_settings = contract["boundary_dynamics"]
    sticking = (
        (boundary_persistence >= float(boundary_settings["boundary_persistence_mass_threshold"]))
        & (np.asarray(weighted_inward_mean) <= float(boundary_settings["maximum_inward_flow_for_sticking"]))
    )
    boundary_arrays = {
        "transition_times": np.asarray(parent["transition_times"], dtype=np.int32),
        "boundary_mass_persistence": boundary_persistence,
        "boundary_exact_cell_overlap": np.asarray(transition_arrays["boundary_cell_overlap"], dtype=np.float64),
        "mass_weighted_inward_flow_minimum": np.asarray(weighted_inward_minimum, dtype=np.float64),
        "mass_weighted_inward_flow_maximum": np.asarray(weighted_inward_maximum, dtype=np.float64),
        "mass_weighted_inward_flow_mean": np.asarray(weighted_inward_mean, dtype=np.float64),
        "boundary_sticking_candidate": sticking.astype(np.uint8),
    }
    alignment_arrays = {
        "transition_times": np.asarray(parent["transition_times"], dtype=np.int32),
        "total_variance_delta": np.asarray(transition_arrays["total_variance_delta"], dtype=np.float64),
        "entropy_delta": np.asarray(transition_arrays["entropy_delta"], dtype=np.float64),
        "major_component_count_delta": np.asarray(transition_arrays["major_component_count_delta"], dtype=np.int32),
        "boundary_mass_delta": np.asarray(transition_arrays["boundary_mass_delta"], dtype=np.float64),
        "gradient_energy_minimum": flow_arrays["gradient_energy_minimum"],
        "gradient_energy_maximum": flow_arrays["gradient_energy_maximum"],
        "gradient_energy_mean": flow_arrays["gradient_energy_mean"],
        "circulation_energy_minimum": flow_arrays["circulation_energy_minimum"],
        "circulation_energy_maximum": flow_arrays["circulation_energy_maximum"],
        "circulation_energy_mean": flow_arrays["circulation_energy_mean"],
        "potential_transport_difference_minimum": flow_arrays["potential_transport_difference_minimum"],
        "potential_transport_difference_maximum": flow_arrays["potential_transport_difference_maximum"],
        "potential_transport_difference_mean": flow_arrays["potential_transport_difference_mean"],
    }
    return flow_arrays, boundary_arrays, alignment_arrays, {
        "channel_labels_are_diagnostic_only": True,
        "candidate_aggregation": "unweighted_unique_candidate_set",
        "transitions": channel_rows,
    }


def _assert_array_payload(expected: Mapping[str, np.ndarray], actual: Mapping[str, np.ndarray], name: str) -> None:
    if set(expected) != set(actual):
        raise RelationFieldShapeError(f"{name} array key mismatch")
    for key in expected:
        left, right = np.asarray(expected[key]), np.asarray(actual[key])
        if left.shape != right.shape or left.dtype.kind != right.dtype.kind:
            raise RelationFieldShapeError(f"{name} array metadata mismatch: {key}")
        if left.dtype.kind in "iu":
            equal = np.array_equal(left, right)
        else:
            equal = np.allclose(left, right, atol=1e-12, rtol=1e-12, equal_nan=False)
        if not equal:
            raise RelationFieldShapeError(f"{name} array value mismatch: {key}")


def _compute_all(
    trajectory_dir: Path,
    rf5_root: Path,
    rf6_root: Path,
    grid_root: Path,
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    parent = _load_parent_artifacts(rf5_root, rf6_root, grid_root)
    grid = _load_grid_with_indices(grid_root)
    rf3_contract = load_rf3_contract()
    identity = parent["rf5_identity"]
    history = _load_history_window(
        trajectory_dir,
        start_t=int(identity["start_t"]),
        to_t=int(identity["to_t"]),
        mass_tolerance=float(rf3_contract["input"]["distribution_mass_tolerance"]),
        minimum_transition_count=2,
    )
    if history["trajectory_id"] != identity["trajectory_id"]:
        raise RelationFieldShapeError("RF-7 canonical trajectory does not match RF-5")
    if history["history_chain_hash"] != identity["source_history_chain_hash"]:
        raise RelationFieldShapeError("RF-7 canonical history hash does not match RF-5")
    times = list(range(int(identity["start_t"]), int(identity["to_t"]) + 1))
    frame_arrays, frame_components, _ = _stack_frame_metrics(history["frames"], times, grid, contract)
    transition_arrays, transition_labels = _stack_transition_metrics(history["frames"], frame_arrays, grid, contract)
    flow_arrays, boundary_arrays, alignment_arrays, channel_labels = _aggregate_unique_candidate_metrics(
        history["frames"], parent, frame_arrays, transition_arrays, grid, contract
    )
    transition_labels["channel_labels"] = channel_labels
    for row, sticking in zip(transition_labels["transitions"], boundary_arrays["boundary_sticking_candidate"], strict=True):
        row["boundary_sticking_candidate"] = bool(sticking)
    return {
        "parent": parent,
        "grid": grid,
        "history": history,
        "frame_arrays": frame_arrays,
        "frame_components": frame_components,
        "transition_arrays": transition_arrays,
        "transition_labels": transition_labels,
        "flow_arrays": flow_arrays,
        "boundary_arrays": boundary_arrays,
        "alignment_arrays": alignment_arrays,
    }


def build_shape_dynamics(
    trajectory_dir: str | Path,
    rf5_artifact_dir: str | Path,
    rf6_artifact_dir: str | Path,
    grid_artifact_dir: str | Path,
    output: str | Path,
    *,
    contract_path: str | Path = DEFAULT_CONTRACT,
) -> Path:
    contract = load_contract(contract_path)
    target = Path(output)
    if target.exists():
        raise RelationFieldShapeError(f"output already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    computed = _compute_all(
        Path(trajectory_dir), Path(rf5_artifact_dir), Path(rf6_artifact_dir), Path(grid_artifact_dir), contract
    )
    parent = computed["parent"]
    history = computed["history"]
    rf5_identity = parent["rf5_identity"]
    identity_basis = {
        "contract_version": contract["contract_version"],
        "trajectory_id": history["trajectory_id"],
        "start_t": int(rf5_identity["start_t"]),
        "to_t": int(rf5_identity["to_t"]),
        "source_history_chain_hash": history["history_chain_hash"],
        "rf5_relation_field_id": rf5_identity["relation_field_id"],
        "rf5_manifest_hash": parent["rf5_manifest_hash"],
        "rf6_decomposition_id": parent["rf6_identity"]["decomposition_id"],
        "rf6_manifest_hash": parent["rf6_manifest_hash"],
        "grid_manifest_hash": computed["grid"]["manifest_hash"],
    }
    shape_dynamics_id = hashlib.sha256(_canonical_json(identity_basis)).hexdigest()
    identity = {
        "shape_dynamics_id": shape_dynamics_id,
        **identity_basis,
        "frame_count": len(history["frames"]),
        "transition_count": len(history["frames"]) - 1,
        "max_source_t_read": int(rf5_identity["to_t"]),
        "risk_prediction_performed": False,
    }
    labels = computed["transition_labels"]["transitions"]
    label_counts = {
        key: sum(bool(row.get(key, False)) for row in labels)
        for key in labels[0]
        if key != "transition_index"
    } if labels else {}
    diagnostics = {
        "frame_count": len(history["frames"]),
        "transition_count": len(history["frames"]) - 1,
        "candidate_count_per_transition_after_deduplication": computed["flow_arrays"]["unique_candidate_count"].tolist(),
        "label_counts": label_counts,
        "maximum_total_variance": float(np.max(computed["frame_arrays"]["total_variance"])),
        "maximum_effective_support": float(np.max(computed["frame_arrays"]["effective_support"])),
        "maximum_major_component_count": int(np.max(computed["frame_arrays"]["major_component_count"])),
        "maximum_boundary_mass": float(np.max(computed["frame_arrays"]["any_boundary_mass"])),
        "future_suffix_read": False,
        "risk_prediction_performed": False,
    }
    gates = {
        "parent_identity_gate": True,
        "history_identity_gate": True,
        "candidate_deduplication_gate": bool(np.all(computed["flow_arrays"]["unique_candidate_count"] >= 1)),
        "finite_frame_metrics_gate": all(np.all(np.isfinite(value)) for value in computed["frame_arrays"].values()),
        "finite_transition_metrics_gate": all(np.all(np.isfinite(value)) for value in computed["transition_arrays"].values()),
        "finite_flow_metrics_gate": all(np.all(np.isfinite(value)) for value in computed["flow_arrays"].values()),
        "causal_cutoff_gate": int(history["max_t_read"]) == int(rf5_identity["to_t"]),
        "source_writeback_gate": True,
    }
    validation = {
        "rf7_shape_dynamics_gate": "passed" if all(gates.values()) else "failed",
        **gates,
        "scientific_claim": contract["acceptance"]["scientific_claim"],
        "risk_prediction_performed": False,
        "parent_writeback_performed": False,
        "canonical_writeback_performed": False,
    }
    if validation["rf7_shape_dynamics_gate"] != "passed":
        raise RelationFieldShapeError(f"RF-7 gates failed: {gates}")
    summary = {
        "contract_version": contract["contract_version"],
        "shape_dynamics_id": shape_dynamics_id,
        "frame_count": len(history["frames"]),
        "transition_count": len(history["frames"]) - 1,
        "label_counts": label_counts,
        "candidate_count_per_transition_after_deduplication": computed["flow_arrays"]["unique_candidate_count"].tolist(),
        "scientific_claim": contract["acceptance"]["scientific_claim"],
        "risk_prediction_performed": False,
    }
    uncertainty = {
        "support_topology": {
            "active_cell_threshold_is_model_choice": True,
            "major_component_mass_threshold": float(contract["frame_shape_metrics"]["major_component_minimum_mass"]),
            "split_merge_labels_are_diagnostic_only": True,
        },
        "flow_channel": {
            "saved_candidates_are_not_complete_solution_set": True,
            "candidate_path_multiplicity_is_not_probability": True,
            "edge_support_width_is_not_counterfactual_escape_capacity": True,
        },
        "field_semantics": {
            "RF6_potential_not_yet_interpreted_as_attraction": True,
            "basin_and_risk_semantics_not_assigned": True,
        },
        "prediction_performed": False,
        "risk_prediction_performed": False,
    }
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp-", dir=target.parent))
    try:
        storage = contract["storage"]
        _dump_json(temporary / storage["contract_file"], contract)
        _dump_json(temporary / storage["identity_file"], identity)
        _write_npz(temporary / storage["frame_metrics_file"], computed["frame_arrays"])
        _dump_json(temporary / storage["frame_components_file"], computed["frame_components"])
        _write_npz(temporary / storage["transition_metrics_file"], computed["transition_arrays"])
        _dump_json(temporary / storage["transition_labels_file"], computed["transition_labels"])
        _write_npz(temporary / storage["flow_channel_file"], computed["flow_arrays"])
        _write_npz(temporary / storage["boundary_dynamics_file"], computed["boundary_arrays"])
        _write_npz(temporary / storage["field_shape_alignment_file"], computed["alignment_arrays"])
        _dump_json(temporary / storage["diagnostics_file"], diagnostics)
        _dump_json(temporary / storage["uncertainty_file"], uncertainty)
        _dump_json(temporary / storage["provenance_file"], {
            "source_files_read": ["gt_mass.npy:selected_rows_only", "history_ledger.csv:prefix_through_RF5_to_t"],
            "parent_artifacts_read": ["RF-2", "RF-5", "RF-6"],
            "max_t_read": int(history["max_t_read"]),
            "future_suffix_read": False,
            "external_logs_read": False,
            "canonical_G_t_copied": False,
            "parent_writeback_performed": False,
            "canonical_writeback_performed": False,
        })
        _dump_json(temporary / storage["summary_file"], summary)
        _dump_json(temporary / storage["validation_file"], validation)
        _dump_json(temporary / storage["manifest_file"], {
            "contract_version": contract["contract_version"],
            "hash_algorithm": "sha256",
            "files": _manifest_entries(temporary, exclude={storage["manifest_file"]}),
        })
        os.replace(temporary, target)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return target


def validate_shape_dynamics(
    input_path: str | Path,
    trajectory_dir: str | Path,
    rf5_artifact_dir: str | Path,
    rf6_artifact_dir: str | Path,
    grid_artifact_dir: str | Path,
) -> dict[str, Any]:
    root = Path(input_path)
    contract = _load_json(root / "contract.json")
    validate_contract(contract)
    _verify_manifest(root)
    computed = _compute_all(
        Path(trajectory_dir), Path(rf5_artifact_dir), Path(rf6_artifact_dir), Path(grid_artifact_dir), contract
    )
    identity = _load_json(root / "identity.json")
    validation = _load_json(root / "validation.json")
    parent = computed["parent"]
    if identity.get("rf5_manifest_hash") != parent["rf5_manifest_hash"] or identity.get("rf6_manifest_hash") != parent["rf6_manifest_hash"]:
        raise RelationFieldShapeError("RF-7 parent manifest identity mismatch")
    if identity.get("source_history_chain_hash") != computed["history"]["history_chain_hash"]:
        raise RelationFieldShapeError("RF-7 history identity mismatch")
    if identity.get("max_source_t_read") != identity.get("to_t"):
        raise RelationFieldShapeError("RF-7 causal cutoff mismatch")
    forbidden_names = {"gt_mass.npy", "history_ledger.csv", "candidate_components.npz", "candidate_flows.npz"}
    if any(path.name in forbidden_names for path in root.rglob("*")):
        raise RelationFieldShapeError("RF-7 copied canonical or parent payload")
    storage = contract["storage"]
    _assert_array_payload(computed["frame_arrays"], _load_npz(root / storage["frame_metrics_file"]), "frame metrics")
    _assert_array_payload(computed["transition_arrays"], _load_npz(root / storage["transition_metrics_file"]), "transition metrics")
    _assert_array_payload(computed["flow_arrays"], _load_npz(root / storage["flow_channel_file"]), "flow metrics")
    _assert_array_payload(computed["boundary_arrays"], _load_npz(root / storage["boundary_dynamics_file"]), "boundary dynamics")
    _assert_array_payload(computed["alignment_arrays"], _load_npz(root / storage["field_shape_alignment_file"]), "field-shape alignment")
    if _load_json(root / storage["frame_components_file"]) != computed["frame_components"]:
        raise RelationFieldShapeError("RF-7 frame component payload mismatch")
    if _load_json(root / storage["transition_labels_file"]) != computed["transition_labels"]:
        raise RelationFieldShapeError("RF-7 transition label payload mismatch")
    if validation.get("rf7_shape_dynamics_gate") != "passed":
        raise RelationFieldShapeError("RF-7 validation gate did not pass")
    return validation


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--trajectory", required=True)
    build.add_argument("--rf5-artifact", required=True)
    build.add_argument("--rf6-artifact", required=True)
    build.add_argument("--grid-artifact", required=True)
    build.add_argument("--output", required=True)
    build.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    validate = commands.add_parser("validate")
    validate.add_argument("--input", required=True)
    validate.add_argument("--trajectory", required=True)
    validate.add_argument("--rf5-artifact", required=True)
    validate.add_argument("--rf6-artifact", required=True)
    validate.add_argument("--grid-artifact", required=True)
    args = parser.parse_args(argv)
    if args.command == "build":
        output = build_shape_dynamics(
            args.trajectory,
            args.rf5_artifact,
            args.rf6_artifact,
            args.grid_artifact,
            args.output,
            contract_path=args.contract,
        )
        print(json.dumps({"output": str(output), "status": "built"}, ensure_ascii=False, sort_keys=True))
    else:
        print(json.dumps(validate_shape_dynamics(
            args.input, args.trajectory, args.rf5_artifact, args.rf6_artifact, args.grid_artifact
        ), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
