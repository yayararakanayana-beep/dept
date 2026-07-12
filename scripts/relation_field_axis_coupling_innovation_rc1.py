"""固定5軸 動的関係場 RF-8: 軸間結合・自己増強・履歴条件付き新規駆動・未解決残差。"""
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

from relation_field_hodge_decomposition_rc1 import validate_hodge_artifact
from relation_field_shape_dynamics_rc1 import (
    _load_grid_with_indices,
    validate_shape_dynamics,
)
from relation_field_single_transition_rc1 import load_contract as load_rf3_contract
from relation_field_temporal_consistency_rc1 import (
    _load_history_window,
    validate_temporal_relation_field,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "configs" / "relation_field_axis_coupling_innovation_rc1.json"
CELL_COUNT = 3125
EDGE_COUNT = 12500
AXIS_COUNT = 5


class RelationFieldAxisCouplingError(ValueError):
    """RF-8契約、親成果物、軸結合、新規駆動、残差成果物の不整合。"""


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
    if contract.get("contract_version") != "relation_field_axis_coupling_innovation_rc1":
        raise RelationFieldAxisCouplingError("unsupported RF-8 contract")
    if int(contract.get("input", {}).get("minimum_transition_count", -1)) < 3:
        raise RelationFieldAxisCouplingError("RF-8 requires at least three transitions")
    position = contract.get("position_conditioned_coupling", {})
    if list(position.get("matrix_shape", [])) != [5, 5] or float(position.get("ridge", 0.0)) <= 0.0:
        raise RelationFieldAxisCouplingError("RF-8 position-coupling contract mismatch")
    innovation = contract.get("history_conditioned_innovation", {})
    if innovation.get("new_drive_is_not_external_factor") is not True:
        raise RelationFieldAxisCouplingError("RF-8 innovation must not be called an external factor")
    if contract.get("unresolved_residual", {}).get("history_innovation_must_remain_separate_from_transport_residual") is not True:
        raise RelationFieldAxisCouplingError("RF-8 innovation and transport residual must remain separate")


def _verify_manifest(root: Path) -> None:
    manifest = _load_json(root / "manifest.json")
    expected: set[str] = set()
    for entry in manifest.get("files", []):
        relative = str(entry["path"])
        expected.add(relative)
        path = root / relative
        if not path.is_file() or path.stat().st_size != int(entry["size_bytes"]) or _sha256_file(path) != entry["sha256"]:
            raise RelationFieldAxisCouplingError(f"manifest mismatch: {relative}")
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    if expected != actual:
        raise RelationFieldAxisCouplingError("manifest file set mismatch")


def _load_parent_artifacts(
    trajectory_root: Path,
    grid_root: Path,
    rf5_root: Path,
    rf6_root: Path,
    rf7_root: Path,
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    validate_temporal_relation_field(rf5_root, grid_root)
    validate_hodge_artifact(rf6_root, rf5_root, grid_root)
    validate_shape_dynamics(rf7_root, trajectory_root, rf5_root, rf6_root, grid_root)
    rf5_identity = _load_json(rf5_root / "identity.json")
    rf6_identity = _load_json(rf6_root / "identity.json")
    rf7_identity = _load_json(rf7_root / "identity.json")
    if rf6_identity.get("rf5_relation_field_id") != rf5_identity.get("relation_field_id"):
        raise RelationFieldAxisCouplingError("RF-8 RF-6/RF-5 identity mismatch")
    if rf7_identity.get("rf5_relation_field_id") != rf5_identity.get("relation_field_id"):
        raise RelationFieldAxisCouplingError("RF-8 RF-7/RF-5 identity mismatch")
    if rf7_identity.get("rf6_decomposition_id") != rf6_identity.get("decomposition_id"):
        raise RelationFieldAxisCouplingError("RF-8 RF-7/RF-6 identity mismatch")
    transition_count = int(rf5_identity["transition_count"])
    if transition_count < int(contract["input"]["minimum_transition_count"]):
        raise RelationFieldAxisCouplingError("RF-8 history has too few transitions")
    rf3_contract = load_rf3_contract()
    history = _load_history_window(
        trajectory_root,
        start_t=int(rf5_identity["start_t"]),
        to_t=int(rf5_identity["to_t"]),
        mass_tolerance=float(rf3_contract["input"]["distribution_mass_tolerance"]),
        minimum_transition_count=int(contract["input"]["minimum_transition_count"]),
    )
    if history["trajectory_id"] != rf5_identity["trajectory_id"]:
        raise RelationFieldAxisCouplingError("RF-8 canonical trajectory identity mismatch")
    if history["history_chain_hash"] != rf5_identity["source_history_chain_hash"]:
        raise RelationFieldAxisCouplingError("RF-8 canonical history identity mismatch")
    paths = _load_json(rf5_root / "temporal_paths.json")
    with np.load(rf5_root / "candidate_flows.npz", allow_pickle=False) as loaded:
        offsets = loaded["candidate_offsets"].copy().astype(np.int32)
        candidate_flow = loaded["candidate_net_flow"].copy().astype(np.float64)
        candidate_residual = loaded["candidate_residual"].copy().astype(np.float64)
        candidate_descriptor = loaded["candidate_descriptor"].copy().astype(np.float64)
    with np.load(rf5_root / "representative_flow.npz", allow_pickle=False) as loaded:
        transition_times = loaded["transition_times"].copy().astype(np.int32)
    with np.load(rf7_root / "frame_shape_metrics.npz", allow_pickle=False) as loaded:
        frame_times = loaded["times"].copy().astype(np.int32)
        frame_centroid = loaded["centroid"].copy().astype(np.float64)
        frame_axis_variance = loaded["axis_variance"].copy().astype(np.float64)
    if offsets.shape != (transition_count + 1,) or candidate_flow.shape[1:] != (EDGE_COUNT,):
        raise RelationFieldAxisCouplingError("RF-8 RF-5 candidate shape mismatch")
    if candidate_residual.shape != (candidate_flow.shape[0], CELL_COUNT):
        raise RelationFieldAxisCouplingError("RF-8 RF-5 residual shape mismatch")
    if candidate_descriptor.shape[0] != candidate_flow.shape[0] or candidate_descriptor.shape[1] < AXIS_COUNT:
        raise RelationFieldAxisCouplingError("RF-8 RF-5 descriptor shape mismatch")
    if transition_times.shape != (transition_count,) or frame_centroid.shape != (transition_count + 1, AXIS_COUNT):
        raise RelationFieldAxisCouplingError("RF-8 temporal frame shape mismatch")
    optimal_paths = [[int(value) for value in path] for path in paths["optimal_paths"]]
    if not optimal_paths or any(len(path) != transition_count for path in optimal_paths):
        raise RelationFieldAxisCouplingError("RF-8 optimal path family mismatch")
    return {
        "rf5_identity": rf5_identity,
        "rf6_identity": rf6_identity,
        "rf7_identity": rf7_identity,
        "rf5_manifest_hash": _sha256_file(rf5_root / "manifest.json"),
        "rf6_manifest_hash": _sha256_file(rf6_root / "manifest.json"),
        "rf7_manifest_hash": _sha256_file(rf7_root / "manifest.json"),
        "history": history,
        "frames": history["frames"],
        "offsets": offsets,
        "candidate_flow": candidate_flow,
        "candidate_residual": candidate_residual,
        "candidate_axis_flow": candidate_descriptor[:, :AXIS_COUNT].copy(),
        "transition_times": transition_times,
        "frame_times": frame_times,
        "frame_centroid": frame_centroid,
        "frame_axis_variance": frame_axis_variance,
        "optimal_paths": optimal_paths,
        "optimal_path_family_truncated": bool(paths.get("optimal_path_family_truncated", False)),
    }


def _unique_candidate_ids(parent: Mapping[str, Any], transition: int) -> tuple[list[int], list[int]]:
    local_ids = sorted({int(path[transition]) for path in parent["optimal_paths"]})
    start, stop = int(parent["offsets"][transition]), int(parent["offsets"][transition + 1])
    if any(local < 0 or start + local >= stop for local in local_ids):
        raise RelationFieldAxisCouplingError("RF-8 candidate index outside transition block")
    return local_ids, [start + local for local in local_ids]


def compute_axis_flow_family(parent: Mapping[str, Any], coordinate_scale: float) -> tuple[dict[str, np.ndarray], list[np.ndarray]]:
    transition_count = int(parent["rf5_identity"]["transition_count"])
    minimum: list[np.ndarray] = []
    maximum: list[np.ndarray] = []
    mean: list[np.ndarray] = []
    unique_count: list[int] = []
    candidate_sets: list[np.ndarray] = []
    for transition in range(transition_count):
        _, flat_ids = _unique_candidate_ids(parent, transition)
        values = np.asarray(parent["candidate_axis_flow"][flat_ids], dtype=np.float64)
        candidate_sets.append(values)
        minimum.append(np.min(values, axis=0))
        maximum.append(np.max(values, axis=0))
        mean.append(np.mean(values, axis=0))
        unique_count.append(values.shape[0])
    minimum_array = np.stack(minimum)
    maximum_array = np.stack(maximum)
    mean_array = np.stack(mean)
    return {
        "transition_times": np.asarray(parent["transition_times"], dtype=np.int32),
        "unique_candidate_count": np.asarray(unique_count, dtype=np.int32),
        "axis_signed_flow_minimum": minimum_array,
        "axis_signed_flow_maximum": maximum_array,
        "axis_signed_flow_mean": mean_array,
        "axis_signed_flow_ambiguity_width": maximum_array - minimum_array,
        "axis_coordinate_displacement_minimum": minimum_array * coordinate_scale,
        "axis_coordinate_displacement_maximum": maximum_array * coordinate_scale,
        "axis_coordinate_displacement_mean": mean_array * coordinate_scale,
    }, candidate_sets


def compute_position_flow_coupling(
    source_centroid: np.ndarray,
    flow_minimum: np.ndarray,
    flow_mean: np.ndarray,
    flow_maximum: np.ndarray,
    *,
    ridge: float,
    variation_minimum: float,
) -> dict[str, np.ndarray]:
    source = np.asarray(source_centroid, dtype=np.float64)
    minimum = np.asarray(flow_minimum, dtype=np.float64)
    mean = np.asarray(flow_mean, dtype=np.float64)
    maximum = np.asarray(flow_maximum, dtype=np.float64)
    if source.ndim != 2 or source.shape[1] != AXIS_COUNT or mean.shape != source.shape:
        raise RelationFieldAxisCouplingError("RF-8 position coupling input shape mismatch")
    slope_mean = np.zeros((AXIS_COUNT, AXIS_COUNT), dtype=np.float64)
    slope_min = np.zeros_like(slope_mean)
    slope_max = np.zeros_like(slope_mean)
    intercept = np.zeros_like(slope_mean)
    rmse = np.zeros_like(slope_mean)
    variation = np.zeros(AXIS_COUNT, dtype=np.float64)
    identifiable = np.zeros(AXIS_COUNT, dtype=np.uint8)
    for source_axis in range(AXIS_COUNT):
        x = source[:, source_axis]
        centered = x - float(np.mean(x))
        variation[source_axis] = float(np.dot(centered, centered))
        identifiable[source_axis] = int(variation[source_axis] >= variation_minimum)
        denominator = variation[source_axis] + ridge
        for target_axis in range(AXIS_COUNT):
            y_mean = mean[:, target_axis]
            slope_mean[source_axis, target_axis] = float(np.dot(centered, y_mean) / denominator)
            lower_terms = np.where(centered >= 0.0, centered * minimum[:, target_axis], centered * maximum[:, target_axis])
            upper_terms = np.where(centered >= 0.0, centered * maximum[:, target_axis], centered * minimum[:, target_axis])
            slope_min[source_axis, target_axis] = float(np.sum(lower_terms, dtype=np.float64) / denominator)
            slope_max[source_axis, target_axis] = float(np.sum(upper_terms, dtype=np.float64) / denominator)
            intercept[source_axis, target_axis] = float(np.mean(y_mean) - slope_mean[source_axis, target_axis] * np.mean(x))
            fitted = intercept[source_axis, target_axis] + slope_mean[source_axis, target_axis] * x
            rmse[source_axis, target_axis] = float(np.sqrt(np.mean((y_mean - fitted) ** 2)))
    return {
        "slope_minimum": slope_min,
        "slope_maximum": slope_max,
        "slope_mean": slope_mean,
        "slope_ambiguity_width": slope_max - slope_min,
        "intercept_mean": intercept,
        "fit_rmse": rmse,
        "source_axis_variation": variation,
        "source_axis_identifiable": identifiable,
        "sample_count": np.asarray([source.shape[0]], dtype=np.int32),
    }


def compute_lag_feedback(
    candidate_sets: Sequence[np.ndarray],
    *,
    tolerance: float,
    magnitude_tolerance: float,
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    lag_count = len(candidate_sets) - 1
    if lag_count < 1:
        raise RelationFieldAxisCouplingError("RF-8 lag feedback requires at least two transitions")
    local_min: list[np.ndarray] = []
    local_max: list[np.ndarray] = []
    local_mean: list[np.ndarray] = []
    pair_count: list[int] = []
    positive: list[np.ndarray] = []
    negative: list[np.ndarray] = []
    dynamics_rows: list[dict[str, Any]] = []
    for lag in range(lag_count):
        current = np.asarray(candidate_sets[lag], dtype=np.float64)
        following = np.asarray(candidate_sets[lag + 1], dtype=np.float64)
        matrices: list[np.ndarray] = []
        axis_flags: dict[str, list[np.ndarray]] = {
            "same_direction_amplification_candidate": [],
            "same_direction_attenuation_candidate": [],
            "direction_reversal_candidate": [],
            "axis_activation_candidate": [],
            "axis_cessation_candidate": [],
        }
        for left in current:
            for right in following:
                acceleration = right - left
                matrices.append(np.outer(left, acceleration))
                left_active = np.abs(left) > magnitude_tolerance
                right_active = np.abs(right) > magnitude_tolerance
                same_direction = left * right > magnitude_tolerance ** 2
                axis_flags["same_direction_amplification_candidate"].append(
                    same_direction & (np.abs(right) > np.abs(left) + magnitude_tolerance)
                )
                axis_flags["same_direction_attenuation_candidate"].append(
                    same_direction & (np.abs(right) < np.abs(left) - magnitude_tolerance)
                )
                axis_flags["direction_reversal_candidate"].append(left * right < -(magnitude_tolerance ** 2))
                axis_flags["axis_activation_candidate"].append((~left_active) & right_active)
                axis_flags["axis_cessation_candidate"].append(left_active & (~right_active))
        matrix_array = np.stack(matrices)
        local_min.append(np.min(matrix_array, axis=0))
        local_max.append(np.max(matrix_array, axis=0))
        local_mean.append(np.mean(matrix_array, axis=0))
        pair_count.append(matrix_array.shape[0])
        positive.append(np.min(matrix_array, axis=0) > tolerance)
        negative.append(np.max(matrix_array, axis=0) < -tolerance)
        row: dict[str, Any] = {"lag_index": lag, "candidate_pair_count": matrix_array.shape[0]}
        for label, values in axis_flags.items():
            flags = np.stack(values)
            row[label] = np.all(flags, axis=0).tolist()
            row[f"{label}_candidate_pair_fraction"] = np.mean(flags, axis=0).tolist()
        dynamics_rows.append(row)
    local_mean_array = np.stack(local_mean)
    return {
        "lag_index": np.arange(lag_count, dtype=np.int32),
        "candidate_pair_count": np.asarray(pair_count, dtype=np.int32),
        "local_coupling_minimum": np.stack(local_min),
        "local_coupling_maximum": np.stack(local_max),
        "local_coupling_mean": local_mean_array,
        "positive_consensus": np.stack(positive).astype(np.uint8),
        "negative_consensus": np.stack(negative).astype(np.uint8),
        "aggregate_coupling_mean": np.mean(local_mean_array, axis=0),
        "positive_consensus_fraction": np.mean(np.stack(positive), axis=0),
        "negative_consensus_fraction": np.mean(np.stack(negative), axis=0),
    }, {
        "labels_are_diagnostic_only": True,
        "attraction_or_repulsion_semantics_assigned": False,
        "lags": dynamics_rows,
    }


def compute_history_innovation(
    source_centroid: np.ndarray,
    flow_minimum: np.ndarray,
    flow_mean: np.ndarray,
    flow_maximum: np.ndarray,
    settings: Mapping[str, Any],
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    source = np.asarray(source_centroid, dtype=np.float64)
    minimum = np.asarray(flow_minimum, dtype=np.float64)
    mean = np.asarray(flow_mean, dtype=np.float64)
    maximum = np.asarray(flow_maximum, dtype=np.float64)
    count = mean.shape[0]
    expected = np.zeros_like(mean)
    innovation = np.zeros_like(mean)
    scale = np.zeros_like(mean)
    score = np.zeros_like(mean)
    support = np.zeros(count, dtype=np.float64)
    prior_count = np.zeros(count, dtype=np.int32)
    available = np.zeros(count, dtype=np.uint8)
    label = np.zeros_like(mean, dtype=np.uint8)
    bandwidth = float(settings["state_bandwidth"])
    recency_decay = float(settings["recency_decay"])
    noise_floor = float(settings["noise_floor"])
    score_threshold = float(settings["normalized_score_threshold"])
    absolute_minimum = float(settings["absolute_innovation_minimum"])
    minimum_prior = int(settings["minimum_prior_transition_count_for_label"])
    minimum_support = float(settings["minimum_effective_support_for_label"])
    for transition in range(1, count):
        prior_indices = np.arange(transition, dtype=np.int32)
        distances = np.linalg.norm(source[:transition] - source[transition], axis=1)
        state_weight = np.exp(-0.5 * (distances / bandwidth) ** 2)
        ages = transition - 1 - prior_indices
        recency_weight = recency_decay ** ages
        raw = state_weight * recency_weight
        if not np.any(raw > 0.0):
            raw = np.ones_like(raw)
        weights = raw / np.sum(raw, dtype=np.float64)
        prior_count[transition] = transition
        available[transition] = 1
        support[transition] = 1.0 / float(np.dot(weights, weights))
        expected[transition] = np.sum(weights[:, None] * mean[:transition], axis=0)
        variance = np.sum(weights[:, None] * (mean[:transition] - expected[transition]) ** 2, axis=0)
        ambiguity = 0.5 * (maximum[transition] - minimum[transition])
        scale[transition] = np.sqrt(variance + ambiguity ** 2 + noise_floor ** 2)
        innovation[transition] = mean[transition] - expected[transition]
        score[transition] = np.abs(innovation[transition]) / scale[transition]
        eligible = transition >= minimum_prior and support[transition] >= minimum_support
        label[transition] = (
            eligible
            & (np.abs(innovation[transition]) >= absolute_minimum)
            & (score[transition] >= score_threshold)
        ).astype(np.uint8)
    rows = [
        {
            "transition_index": transition,
            "baseline_available": bool(available[transition]),
            "prior_transition_count": int(prior_count[transition]),
            "effective_support": float(support[transition]),
            "history_conditioned_new_drive_candidate": label[transition].astype(bool).tolist(),
        }
        for transition in range(count)
    ]
    return {
        "baseline_available": available,
        "prior_transition_count": prior_count,
        "effective_support": support,
        "expected_axis_flow": expected,
        "observed_axis_flow_mean": mean,
        "innovation_axis_flow": innovation,
        "innovation_scale": scale,
        "normalized_innovation_score": score,
        "history_conditioned_new_drive_candidate": label,
    }, {
        "new_drive_is_not_external_factor": True,
        "new_drive_is_not_causal_explanation": True,
        "baseline_is_not_future_prediction_validation": True,
        "transitions": rows,
    }


def compute_residual_ledger(
    parent: Mapping[str, Any],
    candidate_sets: Sequence[np.ndarray],
    source_centroid: np.ndarray,
    grid: Mapping[str, Any],
) -> dict[str, np.ndarray]:
    coordinates = np.asarray(grid["node_values"], dtype=np.float64)
    l1_min: list[float] = []
    l1_max: list[float] = []
    l1_mean: list[float] = []
    pos_min: list[float] = []
    pos_max: list[float] = []
    pos_mean: list[float] = []
    neg_min: list[float] = []
    neg_max: list[float] = []
    neg_mean: list[float] = []
    moment_min: list[np.ndarray] = []
    moment_max: list[np.ndarray] = []
    moment_mean: list[np.ndarray] = []
    for transition, _ in enumerate(candidate_sets):
        _, flat_ids = _unique_candidate_ids(parent, transition)
        residuals = np.asarray(parent["candidate_residual"][flat_ids], dtype=np.float64)
        l1 = np.sum(np.abs(residuals), axis=1)
        positive = np.sum(np.maximum(residuals, 0.0), axis=1)
        negative = np.sum(np.maximum(-residuals, 0.0), axis=1)
        centered = coordinates - source_centroid[transition]
        moments = residuals @ centered
        l1_min.append(float(np.min(l1))); l1_max.append(float(np.max(l1))); l1_mean.append(float(np.mean(l1)))
        pos_min.append(float(np.min(positive))); pos_max.append(float(np.max(positive))); pos_mean.append(float(np.mean(positive)))
        neg_min.append(float(np.min(negative))); neg_max.append(float(np.max(negative))); neg_mean.append(float(np.mean(negative)))
        moment_min.append(np.min(moments, axis=0)); moment_max.append(np.max(moments, axis=0)); moment_mean.append(np.mean(moments, axis=0))
    return {
        "transition_times": np.asarray(parent["transition_times"], dtype=np.int32),
        "residual_l1_minimum": np.asarray(l1_min),
        "residual_l1_maximum": np.asarray(l1_max),
        "residual_l1_mean": np.asarray(l1_mean),
        "positive_residual_mass_minimum": np.asarray(pos_min),
        "positive_residual_mass_maximum": np.asarray(pos_max),
        "positive_residual_mass_mean": np.asarray(pos_mean),
        "negative_residual_mass_minimum": np.asarray(neg_min),
        "negative_residual_mass_maximum": np.asarray(neg_max),
        "negative_residual_mass_mean": np.asarray(neg_mean),
        "residual_axis_moment_minimum": np.stack(moment_min),
        "residual_axis_moment_maximum": np.stack(moment_max),
        "residual_axis_moment_mean": np.stack(moment_mean),
    }


def _assert_array_payload(expected: Mapping[str, np.ndarray], actual: Mapping[str, np.ndarray], name: str) -> None:
    if set(expected) != set(actual):
        raise RelationFieldAxisCouplingError(f"{name} array key mismatch")
    for key in expected:
        left, right = np.asarray(expected[key]), np.asarray(actual[key])
        if left.shape != right.shape or left.dtype.kind != right.dtype.kind:
            raise RelationFieldAxisCouplingError(f"{name} array metadata mismatch: {key}")
        equal = np.array_equal(left, right) if left.dtype.kind in "iub" else np.allclose(left, right, atol=1e-12, rtol=1e-12)
        if not equal:
            raise RelationFieldAxisCouplingError(f"{name} array value mismatch: {key}")


def _compute_all(
    trajectory_root: Path,
    grid_root: Path,
    rf5_root: Path,
    rf6_root: Path,
    rf7_root: Path,
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    parent = _load_parent_artifacts(trajectory_root, grid_root, rf5_root, rf6_root, rf7_root, contract)
    grid = _load_grid_with_indices(grid_root)
    axis_family, candidate_sets = compute_axis_flow_family(
        parent, float(contract["axis_flow_family"]["coordinate_displacement_scale"])
    )
    source_centroid = np.asarray(parent["frame_centroid"][:-1], dtype=np.float64)
    position = compute_position_flow_coupling(
        source_centroid,
        axis_family["axis_signed_flow_minimum"],
        axis_family["axis_signed_flow_mean"],
        axis_family["axis_signed_flow_maximum"],
        ridge=float(contract["position_conditioned_coupling"]["ridge"]),
        variation_minimum=float(contract["position_conditioned_coupling"]["source_variation_minimum"]),
    )
    lag_feedback, same_axis = compute_lag_feedback(
        candidate_sets,
        tolerance=float(contract["lag_feedback_coupling"]["coupling_tolerance"]),
        magnitude_tolerance=float(contract["same_axis_dynamics"]["magnitude_tolerance"]),
    )
    innovation, innovation_labels = compute_history_innovation(
        source_centroid,
        axis_family["axis_signed_flow_minimum"],
        axis_family["axis_signed_flow_mean"],
        axis_family["axis_signed_flow_maximum"],
        contract["history_conditioned_innovation"],
    )
    residual = compute_residual_ledger(parent, candidate_sets, source_centroid, grid)
    return {
        "parent": parent,
        "grid": grid,
        "axis_family": axis_family,
        "candidate_sets": candidate_sets,
        "position": position,
        "lag_feedback": lag_feedback,
        "same_axis": same_axis,
        "innovation": innovation,
        "innovation_labels": innovation_labels,
        "residual": residual,
    }


def build_axis_coupling_innovation(
    trajectory_dir: str | Path,
    grid_artifact_dir: str | Path,
    rf5_artifact_dir: str | Path,
    rf6_artifact_dir: str | Path,
    rf7_artifact_dir: str | Path,
    output: str | Path,
    *,
    contract_path: str | Path = DEFAULT_CONTRACT,
) -> Path:
    contract = load_contract(contract_path)
    target = Path(output)
    if target.exists():
        raise RelationFieldAxisCouplingError(f"output already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    computed = _compute_all(
        Path(trajectory_dir), Path(grid_artifact_dir), Path(rf5_artifact_dir),
        Path(rf6_artifact_dir), Path(rf7_artifact_dir), contract,
    )
    parent = computed["parent"]
    identity_basis = {
        "contract_version": contract["contract_version"],
        "trajectory_id": parent["rf5_identity"]["trajectory_id"],
        "start_t": int(parent["rf5_identity"]["start_t"]),
        "to_t": int(parent["rf5_identity"]["to_t"]),
        "source_history_chain_hash": parent["history"]["history_chain_hash"],
        "rf5_relation_field_id": parent["rf5_identity"]["relation_field_id"],
        "rf5_manifest_hash": parent["rf5_manifest_hash"],
        "rf6_decomposition_id": parent["rf6_identity"]["decomposition_id"],
        "rf6_manifest_hash": parent["rf6_manifest_hash"],
        "rf7_shape_dynamics_id": parent["rf7_identity"]["shape_dynamics_id"],
        "rf7_manifest_hash": parent["rf7_manifest_hash"],
        "grid_manifest_hash": computed["grid"]["manifest_hash"],
    }
    relation_id = hashlib.sha256(_canonical_json(identity_basis)).hexdigest()
    identity = {
        "axis_coupling_innovation_id": relation_id,
        **identity_basis,
        "transition_count": int(parent["rf5_identity"]["transition_count"]),
        "lag_count": int(parent["rf5_identity"]["transition_count"]) - 1,
        "max_source_t_read": int(parent["rf5_identity"]["to_t"]),
        "causal_claim": False,
        "external_factor_claim": False,
        "risk_prediction_performed": False,
    }
    drive_count = int(np.count_nonzero(computed["innovation"]["history_conditioned_new_drive_candidate"]))
    self_counts: dict[str, int] = {}
    for label in contract["same_axis_dynamics"]["labels"]:
        self_counts[label] = sum(sum(bool(value) for value in row[label]) for row in computed["same_axis"]["lags"])
    diagnostics = {
        "transition_count": identity["transition_count"],
        "lag_count": identity["lag_count"],
        "unique_candidate_count_per_transition": computed["axis_family"]["unique_candidate_count"].tolist(),
        "position_identifiable_axis_count": int(np.count_nonzero(computed["position"]["source_axis_identifiable"])),
        "positive_lag_coupling_consensus_count": int(np.count_nonzero(computed["lag_feedback"]["positive_consensus"])),
        "negative_lag_coupling_consensus_count": int(np.count_nonzero(computed["lag_feedback"]["negative_consensus"])),
        "same_axis_label_counts": self_counts,
        "history_conditioned_new_drive_axis_count": drive_count,
        "transport_residual_l1_maximum": float(np.max(computed["residual"]["residual_l1_maximum"])),
        "history_innovation_kept_separate_from_transport_residual": True,
        "future_suffix_read": False,
        "causal_claim": False,
        "external_factor_claim": False,
        "risk_prediction_performed": False,
    }
    gates = {
        "parent_identity_gate": True,
        "history_identity_gate": True,
        "candidate_deduplication_gate": bool(np.all(computed["axis_family"]["unique_candidate_count"] >= 1)),
        "candidate_interval_gate": bool(np.all(computed["axis_family"]["axis_signed_flow_maximum"] >= computed["axis_family"]["axis_signed_flow_minimum"])),
        "position_interval_gate": bool(np.all(computed["position"]["slope_maximum"] >= computed["position"]["slope_minimum"] - 1e-15)),
        "innovation_residual_separation_gate": True,
        "finite_metrics_gate": all(
            np.all(np.isfinite(array))
            for payload in (computed["axis_family"], computed["position"], computed["lag_feedback"], computed["innovation"], computed["residual"])
            for array in payload.values()
        ),
        "causal_cutoff_gate": int(parent["history"]["max_t_read"]) == int(parent["rf5_identity"]["to_t"]),
        "source_writeback_gate": True,
    }
    validation = {
        "rf8_axis_coupling_innovation_gate": "passed" if all(gates.values()) else "failed",
        **gates,
        "scientific_claim": contract["acceptance"]["scientific_claim"],
        "causal_claim": False,
        "external_factor_claim": False,
        "risk_prediction_performed": False,
        "parent_writeback_performed": False,
        "canonical_writeback_performed": False,
    }
    if validation["rf8_axis_coupling_innovation_gate"] != "passed":
        raise RelationFieldAxisCouplingError(f"RF-8 gates failed: {gates}")
    summary = {
        "contract_version": contract["contract_version"],
        "axis_coupling_innovation_id": relation_id,
        "transition_count": identity["transition_count"],
        "lag_count": identity["lag_count"],
        "position_identifiable_axis_count": diagnostics["position_identifiable_axis_count"],
        "history_conditioned_new_drive_axis_count": drive_count,
        "transport_residual_l1_maximum": diagnostics["transport_residual_l1_maximum"],
        "scientific_claim": contract["acceptance"]["scientific_claim"],
        "risk_prediction_performed": False,
    }
    uncertainty = {
        "candidate_field": {
            "candidate_search_exhaustive": False,
            "optimal_path_family_truncated": parent["optimal_path_family_truncated"],
            "saved_path_multiplicity_is_probability": False,
            "candidate_interval_preserved": True,
        },
        "position_coupling": {
            "pairwise_not_multivariate": True,
            "causal_claim": False,
            "source_axis_identifiable": computed["position"]["source_axis_identifiable"].astype(bool).tolist(),
        },
        "feedback": {
            "time_local_outer_product_is_not_causal_coefficient": True,
            "attraction_or_repulsion_semantics_assigned": False,
        },
        "innovation": {
            "baseline_uses_past_only": True,
            "new_drive_is_not_external_factor": True,
            "new_drive_is_not_causal_explanation": True,
            "prediction_accuracy_not_evaluated": True,
        },
        "residual": {
            "RF5_transport_residual_preserved": True,
            "history_innovation_stored_separately": True,
        },
    }
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp-", dir=target.parent))
    try:
        storage = contract["storage"]
        _dump_json(temporary / storage["contract_file"], contract)
        _dump_json(temporary / storage["identity_file"], identity)
        _write_npz(temporary / storage["axis_flow_family_file"], computed["axis_family"])
        _write_npz(temporary / storage["position_coupling_file"], computed["position"])
        _write_npz(temporary / storage["lag_feedback_file"], computed["lag_feedback"])
        _dump_json(temporary / storage["same_axis_dynamics_file"], computed["same_axis"])
        _write_npz(temporary / storage["innovation_file"], computed["innovation"])
        _dump_json(temporary / storage["innovation_labels_file"], computed["innovation_labels"])
        _write_npz(temporary / storage["residual_ledger_file"], computed["residual"])
        _dump_json(temporary / storage["diagnostics_file"], diagnostics)
        _dump_json(temporary / storage["uncertainty_file"], uncertainty)
        _dump_json(temporary / storage["provenance_file"], {
            "source_files_read": ["gt_mass.npy:selected_rows_only", "history_ledger.csv:prefix_through_RF5_to_t"],
            "parent_artifacts_read": ["RF-2", "RF-5", "RF-6", "RF-7"],
            "max_t_read": int(parent["history"]["max_t_read"]),
            "future_suffix_read": False,
            "external_logs_read": False,
            "canonical_or_parent_payload_copied": False,
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


def validate_axis_coupling_innovation(
    input_path: str | Path,
    trajectory_dir: str | Path,
    grid_artifact_dir: str | Path,
    rf5_artifact_dir: str | Path,
    rf6_artifact_dir: str | Path,
    rf7_artifact_dir: str | Path,
) -> dict[str, Any]:
    root = Path(input_path)
    contract = _load_json(root / "contract.json")
    validate_contract(contract)
    _verify_manifest(root)
    computed = _compute_all(
        Path(trajectory_dir), Path(grid_artifact_dir), Path(rf5_artifact_dir),
        Path(rf6_artifact_dir), Path(rf7_artifact_dir), contract,
    )
    identity = _load_json(root / "identity.json")
    parent = computed["parent"]
    if identity.get("rf5_manifest_hash") != parent["rf5_manifest_hash"]:
        raise RelationFieldAxisCouplingError("RF-8 RF-5 manifest identity mismatch")
    if identity.get("rf6_manifest_hash") != parent["rf6_manifest_hash"]:
        raise RelationFieldAxisCouplingError("RF-8 RF-6 manifest identity mismatch")
    if identity.get("rf7_manifest_hash") != parent["rf7_manifest_hash"]:
        raise RelationFieldAxisCouplingError("RF-8 RF-7 manifest identity mismatch")
    if identity.get("source_history_chain_hash") != parent["history"]["history_chain_hash"]:
        raise RelationFieldAxisCouplingError("RF-8 source history identity mismatch")
    if identity.get("max_source_t_read") != identity.get("to_t"):
        raise RelationFieldAxisCouplingError("RF-8 causal cutoff mismatch")
    forbidden = {
        "gt_mass.npy", "history_ledger.csv", "candidate_flows.npz", "candidate_components.npz",
        "frame_shape_metrics.npz", "transition_shape_metrics.npz",
    }
    if any(path.name in forbidden for path in root.rglob("*")):
        raise RelationFieldAxisCouplingError("RF-8 copied canonical or parent payload")
    storage = contract["storage"]
    _assert_array_payload(computed["axis_family"], _load_npz(root / storage["axis_flow_family_file"]), "axis flow family")
    _assert_array_payload(computed["position"], _load_npz(root / storage["position_coupling_file"]), "position coupling")
    _assert_array_payload(computed["lag_feedback"], _load_npz(root / storage["lag_feedback_file"]), "lag feedback")
    _assert_array_payload(computed["innovation"], _load_npz(root / storage["innovation_file"]), "innovation")
    _assert_array_payload(computed["residual"], _load_npz(root / storage["residual_ledger_file"]), "residual ledger")
    if _load_json(root / storage["same_axis_dynamics_file"]) != computed["same_axis"]:
        raise RelationFieldAxisCouplingError("RF-8 same-axis payload mismatch")
    if _load_json(root / storage["innovation_labels_file"]) != computed["innovation_labels"]:
        raise RelationFieldAxisCouplingError("RF-8 innovation-label payload mismatch")
    validation = _load_json(root / storage["validation_file"])
    if validation.get("rf8_axis_coupling_innovation_gate") != "passed":
        raise RelationFieldAxisCouplingError("RF-8 validation gate did not pass")
    return validation


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--trajectory", required=True)
    build.add_argument("--grid-artifact", required=True)
    build.add_argument("--rf5-artifact", required=True)
    build.add_argument("--rf6-artifact", required=True)
    build.add_argument("--rf7-artifact", required=True)
    build.add_argument("--output", required=True)
    build.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    validate = commands.add_parser("validate")
    validate.add_argument("--input", required=True)
    validate.add_argument("--trajectory", required=True)
    validate.add_argument("--grid-artifact", required=True)
    validate.add_argument("--rf5-artifact", required=True)
    validate.add_argument("--rf6-artifact", required=True)
    validate.add_argument("--rf7-artifact", required=True)
    args = parser.parse_args(argv)
    if args.command == "build":
        output = build_axis_coupling_innovation(
            args.trajectory, args.grid_artifact, args.rf5_artifact, args.rf6_artifact,
            args.rf7_artifact, args.output, contract_path=args.contract,
        )
        print(json.dumps({"output": str(output), "status": "built"}, ensure_ascii=False, sort_keys=True))
    else:
        print(json.dumps(validate_axis_coupling_innovation(
            args.input, args.trajectory, args.grid_artifact, args.rf5_artifact,
            args.rf6_artifact, args.rf7_artifact,
        ), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
