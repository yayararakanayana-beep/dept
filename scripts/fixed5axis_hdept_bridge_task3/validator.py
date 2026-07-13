"""固定5軸上位観測翻訳層 Task 3 の独立validator。"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
from collections import deque
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from fixed5axis_hdept_bridge_task2.contracts import (
    AXIS_BINS,
    AXIS_NAMES,
    CELL_COUNT,
    DEFAULT_BRIDGE_CONTRACT,
    DEFAULT_EVIDENCE_MAP,
    DEFAULT_FEATURE_REGISTRY,
    DEFAULT_FIXED5_CONTRACT,
    DEFAULT_SCHEMA,
    GT_SHAPE,
    _json_load,
    _sha256_file,
    _write_json,
    load_bridge_contract,
    load_calibration,
    load_evidence_map,
    load_feature_registry,
    load_fixed5_contract,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_VALIDATOR_PROFILE = ROOT / "configs" / "fixed5axis_hdept_observation_bridge_validator_rc1.json"
EXPECTED_OUTPUT_FILES = {
    "identity.json",
    "features.json",
    "m_observation.json",
    "audit.json",
    "provenance.json",
    "manifest.json",
}
GENESIS_HASH = hashlib.sha256(b"fixed5axis_gk_rc1_history_genesis").hexdigest()
GT_DTYPE = np.dtype("<f8")


class Fixed5AxisHDEPTValidationError(ValueError):
    """Task 3 validator が検出した契約違反。"""


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _load_profile(path: str | Path = DEFAULT_VALIDATOR_PROFILE) -> dict[str, Any]:
    value = _json_load(Path(path))
    if value.get("profile_id") != "fixed5axis_hdept_observation_bridge_validator_rc1":
        raise Fixed5AxisHDEPTValidationError("unsupported validator profile")
    if value.get("status") != "frozen_for_task3_validator":
        raise Fixed5AxisHDEPTValidationError("validator profile is not frozen")
    return value


def _source_metadata_snapshot(root: Path) -> dict[str, tuple[int, int, int]]:
    snapshot: dict[str, tuple[int, int, int]] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            stat = path.stat()
            snapshot[path.relative_to(root).as_posix()] = (int(stat.st_size), int(stat.st_mtime_ns), int(stat.st_mode))
    return snapshot


def _reference_gt_hash(*, contract_version: str, trajectory_id: str, t: int, distribution: np.ndarray, source_state_hash: str) -> str:
    digest = hashlib.sha256()
    for value in (contract_version, trajectory_id, str(int(t))):
        digest.update(value.encode("utf-8"))
        digest.update(b"\x00")
    digest.update(_canonical_json({"axes": AXIS_NAMES, "bins": AXIS_BINS}))
    digest.update(b"\x00")
    digest.update(np.ascontiguousarray(distribution, dtype=GT_DTYPE).tobytes(order="C"))
    digest.update(b"\x00")
    digest.update(source_state_hash.encode("ascii"))
    return digest.hexdigest()


def _reference_chain_hash(previous: str, gt_hash: str, t: int) -> str:
    return hashlib.sha256(f"{previous}\x00{gt_hash}\x00{int(t)}".encode("ascii")).hexdigest()


def _validate_distribution(array: np.ndarray, fixed5: Mapping[str, Any]) -> np.ndarray:
    value = np.ascontiguousarray(np.asarray(array), dtype=GT_DTYPE)
    if value.shape != GT_SHAPE:
        raise Fixed5AxisHDEPTValidationError(f"G_t shape {value.shape} != {GT_SHAPE}")
    if not np.all(np.isfinite(value)):
        raise Fixed5AxisHDEPTValidationError("G_t contains non-finite values")
    if float(np.min(value)) < -float(fixed5["gt"]["negative_tolerance"]):
        raise Fixed5AxisHDEPTValidationError("G_t contains negative mass")
    if abs(float(np.sum(value, dtype=np.float64)) - 1.0) > float(fixed5["gt"]["mass_tolerance"]):
        raise Fixed5AxisHDEPTValidationError("G_t mass does not sum to one")
    return value


def _read_reference_source(trajectory_dir: Path, current_t: int, fixed5: Mapping[str, Any], bridge: Mapping[str, Any]) -> dict[str, Any]:
    storage = fixed5["storage"]
    required_names = [storage["gt_file"], storage["history_ledger_file"], storage["provenance_file"], storage["manifest_file"]]
    for name in required_names:
        if not (trajectory_dir / name).is_file():
            raise Fixed5AxisHDEPTValidationError(f"missing canonical artifact file: {name}")
    for forbidden in ("truth.jsonl", "summary.json", "metrics.jsonl"):
        if (trajectory_dir / forbidden).exists():
            raise Fixed5AxisHDEPTValidationError(f"forbidden canonical file present: {forbidden}")
    provenance = _json_load(trajectory_dir / storage["provenance_file"])
    manifest = _json_load(trajectory_dir / storage["manifest_file"])
    if provenance.get("contract_version") != fixed5["contract_version"]:
        raise Fixed5AxisHDEPTValidationError("fixed5 provenance contract mismatch")
    if tuple(provenance.get("axis_order", ())) != AXIS_NAMES:
        raise Fixed5AxisHDEPTValidationError("fixed5 provenance axis order mismatch")
    if tuple(float(item) for item in provenance.get("axis_bins", ())) != AXIS_BINS:
        raise Fixed5AxisHDEPTValidationError("fixed5 provenance axis bins mismatch")
    if provenance.get("gt_phase") != fixed5["gt"]["phase"]:
        raise Fixed5AxisHDEPTValidationError("fixed5 provenance phase mismatch")
    if provenance.get("forbidden_source_files_read"):
        raise Fixed5AxisHDEPTValidationError("fixed5 provenance reports forbidden source reads")
    if manifest.get("contract_version") != fixed5["contract_version"]:
        raise Fixed5AxisHDEPTValidationError("fixed5 manifest contract mismatch")
    trajectory_id = str(provenance.get("trajectory_id", ""))
    if not trajectory_id:
        raise Fixed5AxisHDEPTValidationError("fixed5 trajectory identity missing")

    ledger_rows: list[dict[str, str]] = []
    found = False
    with (trajectory_dir / storage["history_ledger_file"]).open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            t = int(row["t"])
            ledger_rows.append(dict(row))
            if t == current_t:
                found = True
                break
            if t > current_t:
                break
    if not found:
        raise Fixed5AxisHDEPTValidationError(f"current_t={current_t} not found in causal ledger prefix")

    mass = np.load(trajectory_dir / storage["gt_file"], mmap_mode="r", allow_pickle=False)
    if mass.ndim != 6 or tuple(mass.shape[1:]) != GT_SHAPE or mass.dtype != np.dtype("float64"):
        raise Fixed5AxisHDEPTValidationError("canonical gt_mass.npy shape or dtype mismatch")
    if len(ledger_rows) > mass.shape[0]:
        raise Fixed5AxisHDEPTValidationError("ledger prefix exceeds stored G_t frames")

    previous_t: int | None = None
    previous_gt_hash = ""
    chain_hash = GENESIS_HASH
    frames: list[np.ndarray] = []
    for index, row in enumerate(ledger_rows):
        if int(row["gt_row_index"]) != index:
            raise Fixed5AxisHDEPTValidationError("G/K row index mismatch")
        t = int(row["t"])
        if row["trajectory_id"] != trajectory_id:
            raise Fixed5AxisHDEPTValidationError("multiple trajectory IDs in causal prefix")
        if row["phase"] != fixed5["gt"]["phase"]:
            raise Fixed5AxisHDEPTValidationError("non-pre-transition G_t in causal prefix")
        source_matches = row.get("source_trajectory_id", trajectory_id) == trajectory_id
        if previous_t is None:
            expected_status, expected_delta = ("initial" if source_matches else "source_mismatch", 0)
        else:
            expected_delta = t - previous_t
            if not source_matches:
                expected_status = "source_mismatch"
            elif t == previous_t:
                expected_status = "duplicate"
            elif t < previous_t:
                expected_status = "out_of_order"
            elif t > previous_t + 1:
                expected_status = "gap"
            else:
                expected_status = "continuous"
        if row["continuity_status"] != expected_status or int(row["delta_t"]) != expected_delta:
            raise Fixed5AxisHDEPTValidationError("continuity metadata mismatch")
        admissible = str(row.get("admissible_for_research", "")).strip().lower() == "true"
        if admissible != (expected_status in set(fixed5["kt"]["admissible_continuity_status"])):
            raise Fixed5AxisHDEPTValidationError("admissibility metadata mismatch")
        frame = _validate_distribution(np.asarray(mass[index]), fixed5)
        expected_hash = _reference_gt_hash(
            contract_version=fixed5["contract_version"],
            trajectory_id=trajectory_id,
            t=t,
            distribution=frame,
            source_state_hash=row["source_state_hash"],
        )
        if row["gt_hash"] != expected_hash or row["previous_gt_hash"] != previous_gt_hash:
            raise Fixed5AxisHDEPTValidationError("G_t hash chain mismatch")
        chain_hash = _reference_chain_hash(chain_hash, expected_hash, t)
        if row["history_chain_hash"] != chain_hash:
            raise Fixed5AxisHDEPTValidationError("history chain mismatch")
        frames.append(frame)
        previous_t, previous_gt_hash = t, expected_hash

    current_row = ledger_rows[-1]
    accepted = set(bridge["formal_input"]["accepted_current_continuity_status"])
    if current_row["continuity_status"] not in accepted or str(current_row.get("admissible_for_research", "")).lower() != "true":
        raise Fixed5AxisHDEPTValidationError("current G_t is not admissible for research")

    start = len(ledger_rows) - 1
    while start > 0 and ledger_rows[start]["continuity_status"] == "continuous":
        if ledger_rows[start - 1]["continuity_status"] not in {"initial", "continuous"}:
            break
        start -= 1
    suffix_rows = ledger_rows[start:]
    suffix_frames = frames[start:]
    if suffix_rows[0]["continuity_status"] not in {"initial", "continuous"}:
        suffix_rows = suffix_rows[1:]
        suffix_frames = suffix_frames[1:]
    if not suffix_rows:
        suffix_rows = [current_row]
        suffix_frames = [frames[-1]]

    return {
        "trajectory_id": trajectory_id,
        "current_t": current_t,
        "frames": np.stack(suffix_frames).astype(np.float64, copy=False),
        "ledger": suffix_rows,
        "gt_hash": current_row["gt_hash"],
        "history_chain_hash": current_row["history_chain_hash"],
        "history_start_t": int(suffix_rows[0]["t"]),
        "history_end_t": int(suffix_rows[-1]["t"]),
        "history_frame_count": len(suffix_rows),
    }


@lru_cache(maxsize=1)
def _reference_grid() -> dict[str, np.ndarray]:
    indices = np.indices(GT_SHAPE, dtype=np.int16).reshape(5, -1).T
    coordinates = np.asarray(AXIS_BINS, dtype=np.float64)[indices]
    return {"indices": indices, "coordinates": coordinates}


@lru_cache(maxsize=1)
def _reference_distance_matrix() -> np.ndarray:
    coordinates = _reference_grid()["coordinates"].astype(np.float32)
    squared = np.sum(coordinates * coordinates, axis=1)
    distance2 = squared[:, None] + squared[None, :] - 2.0 * (coordinates @ coordinates.T)
    np.maximum(distance2, 0.0, out=distance2)
    return np.sqrt(distance2, dtype=np.float32)


def _reference_entropy(values: np.ndarray) -> float:
    positive = np.asarray(values, dtype=np.float64).reshape(-1)
    positive = positive[positive > 0.0]
    return 0.0 if positive.size == 0 else float(-np.sum(positive * np.log(positive), dtype=np.float64))


def _reference_js_distance(left: np.ndarray, right: np.ndarray) -> float:
    p = np.asarray(left, dtype=np.float64).reshape(-1)
    q = np.asarray(right, dtype=np.float64).reshape(-1)
    middle = 0.5 * (p + q)

    def kl(a: np.ndarray, b: np.ndarray) -> float:
        mask = a > 0.0
        return float(np.sum(a[mask] * np.log(a[mask] / b[mask]), dtype=np.float64))

    return math.sqrt(max(0.5 * kl(p, middle) + 0.5 * kl(q, middle), 0.0))


def _reference_axis_marginals(frame: np.ndarray) -> np.ndarray:
    rows = []
    for axis in range(5):
        summed = tuple(index for index in range(5) if index != axis)
        rows.append(np.sum(frame, axis=summed, dtype=np.float64))
    return np.stack(rows)


def _reference_one_hop_density(frame: np.ndarray) -> np.ndarray:
    density = np.asarray(frame, dtype=np.float64).copy()
    for axis in range(5):
        low_source = [slice(None)] * 5
        low_target = [slice(None)] * 5
        low_source[axis] = slice(0, -1)
        low_target[axis] = slice(1, None)
        density[tuple(low_target)] += frame[tuple(low_source)]
        high_source = [slice(None)] * 5
        high_target = [slice(None)] * 5
        high_source[axis] = slice(1, None)
        high_target[axis] = slice(0, -1)
        density[tuple(high_target)] += frame[tuple(high_source)]
    return density


def _reference_component_masses(frame: np.ndarray, registry: Mapping[str, Any]) -> list[float]:
    parameters = registry["builder_parameters"]
    flat = frame.reshape(-1)
    threshold = max(
        float(parameters["active_cell_absolute_floor"]),
        float(np.max(flat)) * float(parameters["active_cell_relative_to_peak_floor"]),
    )
    active = flat >= threshold
    indices = _reference_grid()["indices"]
    lookup = {tuple(int(value) for value in row): index for index, row in enumerate(indices)}
    seen = np.zeros(CELL_COUNT, dtype=bool)
    masses: list[float] = []
    for cell in np.flatnonzero(active):
        if seen[cell]:
            continue
        queue: deque[int] = deque([int(cell)])
        seen[cell] = True
        members: list[int] = []
        while queue:
            current = queue.popleft()
            members.append(current)
            coordinate = indices[current]
            for axis in range(5):
                for step in (-1, 1):
                    neighbor = coordinate.copy()
                    neighbor[axis] += step
                    if neighbor[axis] < 0 or neighbor[axis] > 4:
                        continue
                    neighbor_id = lookup[tuple(int(value) for value in neighbor)]
                    if active[neighbor_id] and not seen[neighbor_id]:
                        seen[neighbor_id] = True
                        queue.append(neighbor_id)
        masses.append(float(np.sum(flat[np.asarray(members, dtype=np.int32)], dtype=np.float64)))
    masses.sort(reverse=True)
    return [mass for mass in masses if mass >= float(parameters["major_component_minimum_mass"])]


def _reference_state(frame: np.ndarray, registry: Mapping[str, Any], *, expensive: bool) -> dict[str, Any]:
    flat = frame.reshape(-1)
    coordinates = _reference_grid()["coordinates"]
    centroid = np.sum(flat[:, None] * coordinates, axis=0)
    centered = coordinates - centroid
    covariance = (centered * flat[:, None]).T @ centered
    covariance = 0.5 * (covariance + covariance.T)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues = np.maximum(eigenvalues[order], 0.0)
    eigenvectors = eigenvectors[:, order]
    state: dict[str, Any] = {
        "centroid": centroid,
        "covariance": covariance,
        "eigenvalues": eigenvalues,
        "eigenvectors": eigenvectors,
        "entropy": _reference_entropy(flat) / math.log(CELL_COUNT),
        "density": _reference_one_hop_density(frame).reshape(-1),
        "marginals": _reference_axis_marginals(frame),
    }
    if expensive:
        major = _reference_component_masses(frame, registry)
        distance = _reference_distance_matrix()
        mean_pairwise = float(flat.astype(np.float32) @ distance @ flat.astype(np.float32))
        trace = float(np.trace(covariance))
        state.update(
            major_masses=major,
            mean_pairwise_distance=mean_pairwise,
            pairwise_distance_variance=max(2.0 * trace - mean_pairwise * mean_pairwise, 0.0),
        )
    return state


def _reference_w1(previous: np.ndarray, current: np.ndarray) -> float:
    values = []
    for axis in range(5):
        cdf_delta = np.cumsum(previous[axis] - current[axis])[:-1]
        values.append(float(np.sum(np.abs(cdf_delta), dtype=np.float64) * 0.25))
    return float(np.linalg.norm(np.asarray(values, dtype=np.float64)))


def _unavailable(entry: Mapping[str, Any], reason: str, support_count: int) -> dict[str, Any]:
    return {
        "feature_id": entry["id"],
        "group": entry["g"],
        "value": None,
        "available": False,
        "confidence": 0.0,
        "support_count": int(max(support_count, 0)),
        "minimum_history_frames": int(entry["n"]),
        "derivation_status": entry["s"],
        "evidence_source": entry["src"],
        "reason_unavailable": reason,
    }


def _available(entry: Mapping[str, Any], value: float, support_count: int) -> dict[str, Any]:
    return {
        "feature_id": entry["id"],
        "group": entry["g"],
        "value": float(value),
        "available": True,
        "confidence": float(entry["cap"]),
        "support_count": int(support_count),
        "minimum_history_frames": int(entry["n"]),
        "derivation_status": entry["s"],
        "evidence_source": entry["src"],
        "reason_unavailable": None,
    }


def _reference_features(frames: np.ndarray, ledger: Sequence[Mapping[str, str]], registry: Mapping[str, Any]) -> list[dict[str, Any]]:
    recent_count = min(len(frames), max(5, int(registry["builder_parameters"]["oscillation_window"])))
    recent_frames = frames[-recent_count:]
    recent_ledger = ledger[-recent_count:]
    states = [_reference_state(frame, registry, expensive=index == len(recent_frames) - 1) for index, frame in enumerate(recent_frames)]
    current = states[-1]
    parameters = registry["builder_parameters"]
    axis_floor = float(parameters["axis_variance_floor"])
    trace = float(np.trace(current["covariance"]))
    eigenvalues = current["eigenvalues"]
    variances = np.diag(current["covariance"]).copy()
    values: dict[str, float] = {"raw_dimension": 5.0, "active_axis_count": float(np.count_nonzero(variances > axis_floor))}
    reasons: dict[str, str] = {}

    if float(np.sum(variances)) > axis_floor:
        weights = variances / float(np.sum(variances))
        values["axis_weight_entropy"] = _reference_entropy(weights) / math.log(5.0)
        l1 = float(np.sum(np.abs(variances)))
        l2 = float(np.linalg.norm(variances))
        values["axis_weight_sparsity"] = float((math.sqrt(5.0) - l1 / max(l2, 1e-30)) / (math.sqrt(5.0) - 1.0))
    else:
        reasons["axis_weight_entropy"] = "zero_total_axis_variance"
        reasons["axis_weight_sparsity"] = "zero_axis_variance_vector"

    correlations: list[float] = []
    for left in range(5):
        for right in range(left + 1, 5):
            if variances[left] > axis_floor and variances[right] > axis_floor:
                correlations.append(float(current["covariance"][left, right] / math.sqrt(variances[left] * variances[right])))
    if correlations:
        values["axis_redundancy"] = float(np.mean(np.abs(correlations)))
        values["mean_axis_correlation"] = float(np.mean(correlations))
    else:
        reasons["axis_redundancy"] = "fewer_than_two_active_axes"
        reasons["mean_axis_correlation"] = "fewer_than_two_active_axes"

    if trace > axis_floor:
        spectrum = eigenvalues / trace
        values["effective_rank"] = math.exp(_reference_entropy(spectrum))
        values["participation_ratio"] = trace * trace / float(np.sum(eigenvalues * eigenvalues))
        values["spectral_entropy"] = _reference_entropy(spectrum) / math.log(5.0)
        values["dominant_eigen_share"] = float(eigenvalues[0] / trace)
        values["spectral_gap"] = float((eigenvalues[0] - eigenvalues[1]) / trace)
        values["anisotropy"] = float(1.0 - eigenvalues[-1] / eigenvalues[0]) if eigenvalues[0] > axis_floor else 0.0
    else:
        for key in ("effective_rank", "participation_ratio", "spectral_entropy", "dominant_eigen_share", "spectral_gap", "anisotropy"):
            reasons[key] = "zero_total_covariance"

    values["covariance_trace"] = trace
    epsilon = float(parameters["covariance_regularization_epsilon"])
    sign, logdet = np.linalg.slogdet(current["covariance"] + epsilon * np.eye(5))
    if sign > 0:
        values["covariance_logdet"] = float(logdet)
    else:
        reasons["covariance_logdet"] = "regularized_covariance_not_positive_definite"
    values["compactness"] = float(np.clip(1.0 - trace / 1.25, 0.0, 1.0))
    values["mean_pairwise_distance"] = float(current["mean_pairwise_distance"])
    values["pairwise_distance_variance"] = float(current["pairwise_distance_variance"])
    values["entropy"] = float(current["entropy"])

    flat = recent_frames[-1].reshape(-1)
    peak = float(np.max(flat))
    active_threshold = max(float(parameters["active_cell_absolute_floor"]), peak * float(parameters["active_cell_relative_to_peak_floor"]))
    active = flat >= active_threshold
    active_density = current["density"][active]
    if active_density.size:
        density_mean = float(np.mean(active_density))
        density_peak = float(np.max(active_density))
        values["knn_density_variance"] = float(np.var(active_density) / max(density_mean * density_mean, 1e-30))
        values["density_peak_ratio"] = density_peak / max(density_mean, 1e-30)
        values["outlier_ratio"] = float(np.mean(active_density < float(parameters["outlier_density_fraction_of_peak"]) * density_peak))
    else:
        for key in ("knn_density_variance", "density_peak_ratio", "outlier_ratio"):
            reasons[key] = "no_active_cells"

    boundary = np.any((_reference_grid()["indices"] == 0) | (_reference_grid()["indices"] == 4), axis=1)
    values["tail_mass"] = float(np.sum(flat[boundary], dtype=np.float64))
    major = list(current["major_masses"])
    values["mode_count"] = float(len(major))
    if len(major) == 1:
        values["cluster_balance"] = 1.0
    elif len(major) > 1:
        normalized = np.asarray(major, dtype=np.float64)
        normalized /= float(np.sum(normalized))
        values["cluster_balance"] = _reference_entropy(normalized) / math.log(len(major))
    else:
        reasons["cluster_balance"] = "no_major_components"

    times = [int(row["t"]) for row in recent_ledger]
    velocities: list[np.ndarray] = []
    step_lengths: list[float] = []
    if len(states) >= 2:
        delta_t = times[-1] - times[-2]
        if delta_t <= 0:
            raise Fixed5AxisHDEPTValidationError("non-positive delta_t in causal history")
        centroid_delta = states[-1]["centroid"] - states[-2]["centroid"]
        values["mean_drift_norm"] = float(np.linalg.norm(centroid_delta) / delta_t)
        values["covariance_drift_norm"] = float(np.linalg.norm(states[-1]["covariance"] - states[-2]["covariance"], ord="fro") / delta_t)
        values["wasserstein_velocity"] = _reference_w1(states[-2]["marginals"], states[-1]["marginals"]) / delta_t
        values["jsd_velocity"] = _reference_js_distance(recent_frames[-2], recent_frames[-1]) / delta_t
        values["entropy_velocity"] = abs(states[-1]["entropy"] - states[-2]["entropy"]) / delta_t
        values["density_velocity"] = float(np.linalg.norm(states[-1]["density"] - states[-2]["density"]) / delta_t)
        if trace > axis_floor:
            previous_trace = float(np.sum(states[-2]["eigenvalues"]))
            if previous_trace > axis_floor:
                previous_rank = math.exp(_reference_entropy(states[-2]["eigenvalues"] / previous_trace))
                values["effective_rank_velocity"] = abs(values["effective_rank"] - previous_rank) / delta_t
            else:
                reasons["effective_rank_velocity"] = "previous_zero_total_covariance"
        else:
            reasons["effective_rank_velocity"] = "current_zero_total_covariance"
        for index in range(1, len(states)):
            step_delta = times[index] - times[index - 1]
            velocity = (states[index]["centroid"] - states[index - 1]["centroid"]) / step_delta
            velocities.append(velocity)
            step_lengths.append(float(np.linalg.norm(states[index]["centroid"] - states[index - 1]["centroid"])))
        previous_values = states[-2]["eigenvalues"]
        current_values = states[-1]["eigenvalues"]
        previous_total = float(np.sum(previous_values))
        current_total = float(np.sum(current_values))
        if previous_total > axis_floor and current_total > axis_floor:
            threshold = float(parameters["principal_subspace_explained_variance_floor"])
            previous_k = int(np.searchsorted(np.cumsum(previous_values) / previous_total, threshold) + 1)
            current_k = int(np.searchsorted(np.cumsum(current_values) / current_total, threshold) + 1)
            tolerance = float(parameters["eigenvalue_degeneracy_tolerance"])

            def degenerate(values_: np.ndarray, k: int, total: float) -> bool:
                return k < len(values_) and abs(float(values_[k - 1] - values_[k])) <= tolerance * max(total, 1.0)

            if not degenerate(previous_values, previous_k, previous_total) and not degenerate(current_values, current_k, current_total):
                left = states[-2]["eigenvectors"][:, :previous_k]
                right = states[-1]["eigenvectors"][:, :current_k]
                singular = np.clip(np.linalg.svd(left.T @ right, compute_uv=False), -1.0, 1.0)
                values["principal_subspace_angle"] = float(np.max(np.arccos(singular)) / (0.5 * math.pi))
            else:
                reasons["principal_subspace_angle"] = "eigenvalue_degeneracy_at_subspace_cutoff"
        else:
            reasons["principal_subspace_angle"] = "zero_covariance_subspace"
    else:
        for key in ("mean_drift_norm", "covariance_drift_norm", "wasserstein_velocity", "jsd_velocity", "entropy_velocity", "density_velocity", "effective_rank_velocity", "principal_subspace_angle"):
            reasons[key] = "requires_at_least_two_contiguous_frames"

    velocity_floor = float(parameters["velocity_norm_floor"])
    if len(velocities) >= 2:
        previous_velocity, current_velocity = velocities[-2], velocities[-1]
        previous_norm = float(np.linalg.norm(previous_velocity))
        current_norm = float(np.linalg.norm(current_velocity))
        if previous_norm > velocity_floor and current_norm > velocity_floor:
            cosine = float(np.clip(np.dot(previous_velocity, current_velocity) / (previous_norm * current_norm), -1.0, 1.0))
            angle = math.acos(cosine) / math.pi
            values["direction_cosine"] = cosine
            values["motion_angle"] = angle
            values["acceleration_norm"] = float(np.linalg.norm(current_velocity - previous_velocity) / (times[-1] - times[-2]))
            mean_length = 0.5 * (step_lengths[-1] + step_lengths[-2])
            values["trajectory_curvature"] = angle / max(mean_length, float(parameters["curvature_length_floor"]))
        else:
            for key in ("direction_cosine", "motion_angle", "acceleration_norm", "trajectory_curvature"):
                reasons[key] = "consecutive_centroid_velocity_below_floor"
    else:
        for key in ("direction_cosine", "motion_angle", "acceleration_norm", "trajectory_curvature"):
            reasons[key] = "requires_at_least_three_contiguous_frames"

    if len(recent_frames) >= int(parameters["oscillation_window"]) and len(velocities) >= 2:
        comparisons = 0
        reversals = 0
        for previous_velocity, current_velocity in zip(velocities, velocities[1:]):
            for axis in range(5):
                if abs(float(previous_velocity[axis])) <= velocity_floor or abs(float(current_velocity[axis])) <= velocity_floor:
                    continue
                comparisons += 1
                reversals += int(previous_velocity[axis] * current_velocity[axis] < 0.0)
        if comparisons:
            values["oscillation_index"] = reversals / comparisons
        else:
            reasons["oscillation_index"] = "no_eligible_axis_velocity_comparisons"
    else:
        reasons["oscillation_index"] = "requires_full_causal_oscillation_window"

    records: list[dict[str, Any]] = []
    for entry in registry["features"]:
        feature_id = entry["id"]
        if entry["s"] in {"reserved_prediction_subcontract", "reserved_recovery_subcontract"}:
            records.append(_unavailable(entry, f"{entry['s']}_not_implemented_in_task2", len(frames)))
        elif feature_id in values and math.isfinite(float(values[feature_id])):
            records.append(_available(entry, float(values[feature_id]), min(len(frames), max(int(entry["n"]), 1))))
        elif feature_id in values:
            records.append(_unavailable(entry, "derived_non_finite_value", len(frames)))
        else:
            records.append(_unavailable(entry, reasons.get(feature_id, "required_evidence_unavailable"), len(frames)))
    return records


def _reference_sigmoid(value: float) -> float:
    if value >= 0.0:
        exp = math.exp(-value)
        return 1.0 / (1.0 + exp)
    exp = math.exp(value)
    return exp / (1.0 + exp)


def _reference_h11(records: Sequence[Mapping[str, Any]], registry: Mapping[str, Any], evidence_map: Mapping[str, Any], calibration: Mapping[str, Any] | None, history_count: int) -> tuple[dict[str, Any], str]:
    calibrated: dict[str, float] = {}
    if calibration is not None:
        for index, (entry, record) in enumerate(zip(registry["features"], records, strict=True)):
            if not bool(entry.get("score", True)) or float(entry["cap"]) <= 0.0 or not record["available"]:
                continue
            value = (float(record["value"]) - float(calibration["center"][index])) / float(calibration["scale"][index])
            calibrated[entry["id"]] = float(np.clip(value, float(calibration["clip_lower"][index]), float(calibration["clip_upper"][index])))

    record_by_id = {record["feature_id"]: record for record in records}
    registry_order = {entry["id"]: index for index, entry in enumerate(registry["features"])}
    axes: dict[str, Any] = {}
    available_axis_count = 0
    for axis_id in evidence_map["axis_order"]:
        axis = evidence_map["h11_axes"][axis_id]
        construction = axis["construction"]
        component_weights = {construction["component"]: 1.0} if construction["type"] == "base_component" else {str(key): float(value) for key, value in construction["components"].items()}
        raw = 0.0
        all_components = True
        feature_weights: dict[str, float] = {}
        referenced: set[str] = set()
        for component_id, component_weight in component_weights.items():
            definition = evidence_map["base_components"][component_id]
            positive = list(definition["positive"])
            negative = list(definition["negative"])
            referenced.update(positive)
            referenced.update(negative)
            available_positive = [feature for feature in positive if feature in calibrated]
            available_negative = [feature for feature in negative if feature in calibrated]
            if (positive and not available_positive) or (negative and not available_negative):
                all_components = False
                continue
            score = 0.0
            if available_positive:
                score += float(np.mean([calibrated[feature] for feature in available_positive]))
                for feature in available_positive:
                    feature_weights[feature] = feature_weights.get(feature, 0.0) + abs(component_weight) / len(available_positive)
            if available_negative:
                score -= float(np.mean([calibrated[feature] for feature in available_negative]))
                for feature in available_negative:
                    feature_weights[feature] = feature_weights.get(feature, 0.0) + abs(component_weight) / len(available_negative)
            raw += component_weight * score
        ordered_refs = sorted(referenced, key=registry_order.__getitem__)
        available_refs = [feature for feature in ordered_refs if feature in calibrated]
        coverage = len(available_refs) / len(ordered_refs) if ordered_refs else 1.0
        available = bool(calibration is not None and history_count >= int(axis["minimum_history_frames"]) and all_components and coverage >= float(axis["limited_coverage_min"]))
        if available:
            value = _reference_sigmoid(float(evidence_map["scoring"].get("gamma", 1.0)) * raw)
            denominator = sum(feature_weights.get(feature, 0.0) for feature in available_refs)
            weighted_confidence = 0.0 if denominator <= 0.0 else sum(feature_weights.get(feature, 0.0) * float(record_by_id[feature]["confidence"]) for feature in available_refs) / denominator
            confidence = float(np.clip(coverage * weighted_confidence, 0.0, 1.0))
            available_axis_count += 1
            result = {
                "value": value,
                "transport_value": value,
                "transport_value_is_neutral_placeholder": False,
                "available": True,
                "confidence": confidence,
                "evidence_coverage": float(coverage),
                "status": "LIMITED",
                "evidence_feature_ids": ordered_refs,
                "claim_limit": axis["claim"],
                "watchpoints": list(axis["watchpoints"]),
            }
        else:
            result = {
                "value": None,
                "transport_value": 0.5,
                "transport_value_is_neutral_placeholder": True,
                "available": False,
                "confidence": 0.0,
                "evidence_coverage": float(coverage),
                "status": "UNAVAILABLE",
                "evidence_feature_ids": ordered_refs,
                "claim_limit": axis["claim"],
                "watchpoints": list(axis["watchpoints"]),
            }
        axes[axis_id] = result
    if history_count < 2:
        status = "INSUFFICIENT_HISTORY"
    elif calibration is None or available_axis_count == 0:
        status = "HOLD_RECOMMENDED"
    else:
        status = "LIMITED"
    return axes, status


def _compare(path: str, actual: Any, expected: Any, *, atol: float, rtol: float) -> None:
    if isinstance(expected, bool) or expected is None or isinstance(expected, str):
        if actual != expected:
            raise Fixed5AxisHDEPTValidationError(f"{path} mismatch: {actual!r} != {expected!r}")
        return
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        if not isinstance(actual, (int, float)) or isinstance(actual, bool):
            raise Fixed5AxisHDEPTValidationError(f"{path} numeric type mismatch")
        if not math.isfinite(float(actual)) or not math.isfinite(float(expected)):
            raise Fixed5AxisHDEPTValidationError(f"{path} non-finite numeric value")
        if not math.isclose(float(actual), float(expected), abs_tol=atol, rel_tol=rtol):
            raise Fixed5AxisHDEPTValidationError(f"{path} numeric mismatch: {actual!r} != {expected!r}")
        return
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            raise Fixed5AxisHDEPTValidationError(f"{path} list shape mismatch")
        for index, (actual_item, expected_item) in enumerate(zip(actual, expected, strict=True)):
            _compare(f"{path}[{index}]", actual_item, expected_item, atol=atol, rtol=rtol)
        return
    if isinstance(expected, dict):
        if not isinstance(actual, dict) or set(actual) != set(expected):
            missing = sorted(set(expected) - set(actual)) if isinstance(actual, dict) else sorted(expected)
            extra = sorted(set(actual) - set(expected)) if isinstance(actual, dict) else []
            raise Fixed5AxisHDEPTValidationError(f"{path} object keys mismatch missing={missing} extra={extra}")
        for key in expected:
            _compare(f"{path}.{key}", actual[key], expected[key], atol=atol, rtol=rtol)
        return
    if actual != expected:
        raise Fixed5AxisHDEPTValidationError(f"{path} mismatch")


def _load_artifact(artifact_dir: Path, profile: Mapping[str, Any]) -> dict[str, Any]:
    files = {path.relative_to(artifact_dir).as_posix() for path in artifact_dir.rglob("*") if path.is_file()}
    directories = [path for path in artifact_dir.rglob("*") if path.is_dir()]
    expected_files = set(profile["artifact"]["exact_file_set"])
    if files != expected_files:
        raise Fixed5AxisHDEPTValidationError(f"artifact exact file set mismatch missing={sorted(expected_files - files)} extra={sorted(files - expected_files)}")
    if directories:
        raise Fixed5AxisHDEPTValidationError("artifact contains unexpected directories")
    documents = {name: _json_load(artifact_dir / name) for name in expected_files}
    manifest = documents["manifest.json"]
    if manifest.get("contract_version") != profile["contract_version"]:
        raise Fixed5AxisHDEPTValidationError("artifact manifest contract mismatch")
    entries = manifest.get("files")
    if not isinstance(entries, list):
        raise Fixed5AxisHDEPTValidationError("artifact manifest files must be a list")
    expected_payload = set(profile["artifact"]["manifest_payload_files"])
    entry_paths = [str(entry.get("path", "")) for entry in entries]
    if len(entry_paths) != len(set(entry_paths)) or set(entry_paths) != expected_payload:
        raise Fixed5AxisHDEPTValidationError("artifact manifest payload file set mismatch")
    for entry in entries:
        path = artifact_dir / entry["path"]
        if entry.get("sha256") != _sha256_file(path) or int(entry.get("size_bytes", -1)) != path.stat().st_size:
            raise Fixed5AxisHDEPTValidationError(f"artifact manifest integrity mismatch: {entry['path']}")
    return documents


def validate_observation(
    trajectory_dir: str | Path,
    current_t: int,
    artifact_dir: str | Path,
    *,
    calibration_path: str | Path | None = None,
    validator_profile_path: str | Path = DEFAULT_VALIDATOR_PROFILE,
    bridge_contract_path: str | Path = DEFAULT_BRIDGE_CONTRACT,
    feature_registry_path: str | Path = DEFAULT_FEATURE_REGISTRY,
    evidence_map_path: str | Path = DEFAULT_EVIDENCE_MAP,
    fixed5_contract_path: str | Path = DEFAULT_FIXED5_CONTRACT,
    schema_path: str | Path = DEFAULT_SCHEMA,
) -> dict[str, Any]:
    if isinstance(current_t, bool) or not isinstance(current_t, int) or current_t < 0:
        raise Fixed5AxisHDEPTValidationError("current_t must be a non-negative integer")
    trajectory = Path(trajectory_dir)
    artifact = Path(artifact_dir)
    before = _source_metadata_snapshot(trajectory)
    profile = _load_profile(validator_profile_path)
    bridge = load_bridge_contract(bridge_contract_path)
    registry = load_feature_registry(feature_registry_path)
    evidence_map = load_evidence_map(evidence_map_path)
    fixed5 = load_fixed5_contract(fixed5_contract_path)
    if not Path(schema_path).is_file():
        raise Fixed5AxisHDEPTValidationError("bridge output schema is missing")
    registry_hash = _sha256_file(Path(feature_registry_path))
    evidence_hash = _sha256_file(Path(evidence_map_path))
    calibration = None if calibration_path is None else load_calibration(calibration_path, registry, registry_hash=registry_hash)
    documents = _load_artifact(artifact, profile)
    source = _read_reference_source(trajectory, current_t, fixed5, bridge)

    identity = documents["identity.json"]
    features_document = documents["features.json"]
    observation_document = documents["m_observation.json"]
    audit = documents["audit.json"]
    provenance = documents["provenance.json"]
    for name, document in (("identity", identity), ("features", features_document), ("m_observation", observation_document)):
        if document.get("contract_version") != bridge["contract_version"]:
            raise Fixed5AxisHDEPTValidationError(f"{name} contract_version mismatch")
    if identity.get("trajectory_id") != source["trajectory_id"] or int(identity.get("current_t", -1)) != current_t:
        raise Fixed5AxisHDEPTValidationError("artifact trajectory/current_t identity mismatch")
    expected_input_identity = {
        "fixed5_contract_version": fixed5["contract_version"],
        "gt_hash": source["gt_hash"],
        "history_chain_hash": source["history_chain_hash"],
        "history_start_t": source["history_start_t"],
        "history_end_t": source["history_end_t"],
        "history_frame_count": source["history_frame_count"],
        "feature_registry_hash": registry_hash,
        "evidence_map_hash": evidence_hash,
        "calibration_version": None if calibration is None else calibration["calibration_version"],
    }
    _compare("identity.input_identity", identity.get("input_identity"), expected_input_identity, atol=0.0, rtol=0.0)

    reference_records = _reference_features(source["frames"], source["ledger"], registry)
    actual_records = features_document.get("features")
    tolerances = profile["numeric_comparison"]
    atol, rtol = float(tolerances["absolute_tolerance"]), float(tolerances["relative_tolerance"])
    _compare("features", actual_records, reference_records, atol=atol, rtol=rtol)

    reference_h11, reference_status = _reference_h11(reference_records, registry, evidence_map, calibration, source["history_frame_count"])
    if list(observation_document.get("h11", {})) != list(evidence_map["axis_order"]):
        raise Fixed5AxisHDEPTValidationError("H11 axis order mismatch")
    _compare("m_observation.h11", observation_document.get("h11"), reference_h11, atol=atol, rtol=rtol)
    _compare("m_observation.global_observation_status", observation_document.get("global_observation_status"), reference_status, atol=0.0, rtol=0.0)
    if reference_status == "READY" or any(axis["status"] == "READY" for axis in reference_h11.values()):
        raise Fixed5AxisHDEPTValidationError("Task 2 artifact emitted READY")

    expected_audit = {
        "future_suffix_read": False,
        "truth_used": False,
        "external_log_used_as_numeric_evidence": False,
        "ot_used": False,
        "pressure_used_as_input": False,
        "source_writeback_performed": False,
        "neutral_placeholder_used_as_evidence": False,
        "contract_status": "pass",
        "feature_count": 47,
        "available_feature_count": sum(bool(item["available"]) for item in reference_records),
        "proxy_feature_count": sum(item["derivation_status"] == "adapted_fixed_grid_proxy" for item in reference_records),
        "reserved_feature_count": sum(item["derivation_status"].startswith("reserved_") for item in reference_records),
        "available_h11_axis_count": sum(bool(item["available"]) for item in reference_h11.values()),
        "global_ready_emitted": False,
        "full_source_manifest_hash_verification_skipped_to_preserve_prefix_causality": True,
    }
    _compare("audit", audit, expected_audit, atol=0.0, rtol=0.0)

    expected_provenance = {
        "builder_version": "fixed5axis_hdept_observation_bridge_task2_rc1",
        "bridge_contract_hash": _sha256_file(Path(bridge_contract_path)),
        "feature_registry_hash": registry_hash,
        "evidence_map_hash": evidence_hash,
        "schema_hash": _sha256_file(Path(schema_path)),
        "calibration_file_hash": None if calibration is None else calibration["calibration_file_hash"],
        "formal_source_files_read": ["gt_mass.npy prefix frames", "history_ledger.csv through current_t", "provenance.json", "manifest.json"],
        "source_manifest_declared_file_count": int(_json_load(trajectory / fixed5["storage"]["manifest_file"]).get("file_count", -1)),
        "history_selector": bridge["formal_input"]["history_selector"],
        "scientific_claim": "B_limited_task2_builder_implementation_without_calibration_or_scientific_validation",
    }
    _compare("provenance", provenance, expected_provenance, atol=0.0, rtol=0.0)

    after = _source_metadata_snapshot(trajectory)
    if before != after:
        raise Fixed5AxisHDEPTValidationError("source tree metadata changed during validation")

    feature_by_id = {item["feature_id"]: item for item in reference_records}
    critical = {
        "mass_sum": float(np.sum(source["frames"][-1], dtype=np.float64)),
        "covariance_trace": feature_by_id["covariance_trace"]["value"],
        "normalized_entropy": feature_by_id["entropy"]["value"],
        "centroid_drift": feature_by_id["mean_drift_norm"]["value"],
        "jensen_shannon_velocity": feature_by_id["jsd_velocity"]["value"],
        "reserved_feature_unavailability": all(not item["available"] and item["value"] is None and item["confidence"] == 0.0 for item in reference_records if item["derivation_status"].startswith("reserved_")),
        "neutral_placeholder_non_evidence": all((axis["available"] or (axis["transport_value"] == 0.5 and axis["transport_value_is_neutral_placeholder"] and axis["confidence"] == 0.0)) for axis in reference_h11.values()),
    }
    return {
        "validator_version": profile["validator_version"],
        "contract_version": bridge["contract_version"],
        "trajectory_id": source["trajectory_id"],
        "current_t": current_t,
        "status": "pass",
        "gates": {gate: "passed" for gate in profile["gates"]},
        "checked_feature_count": len(reference_records),
        "checked_h11_axis_count": len(reference_h11),
        "global_observation_status": reference_status,
        "critical_raw_invariants": critical,
        "engineering_claim": profile["claim_boundary"]["engineering_claim"],
        "scientific_claim": profile["claim_boundary"]["scientific_claim"],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trajectory-dir", required=True)
    parser.add_argument("--current-t", required=True, type=int)
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--calibration")
    parser.add_argument("--output")
    parser.add_argument("--validator-profile", default=str(DEFAULT_VALIDATOR_PROFILE))
    parser.add_argument("--bridge-contract", default=str(DEFAULT_BRIDGE_CONTRACT))
    parser.add_argument("--feature-registry", default=str(DEFAULT_FEATURE_REGISTRY))
    parser.add_argument("--evidence-map", default=str(DEFAULT_EVIDENCE_MAP))
    parser.add_argument("--fixed5-contract", default=str(DEFAULT_FIXED5_CONTRACT))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = validate_observation(
            args.trajectory_dir,
            args.current_t,
            args.artifact_dir,
            calibration_path=args.calibration,
            validator_profile_path=args.validator_profile,
            bridge_contract_path=args.bridge_contract,
            feature_registry_path=args.feature_registry,
            evidence_map_path=args.evidence_map,
            fixed5_contract_path=args.fixed5_contract,
            schema_path=args.schema,
        )
    except (Fixed5AxisHDEPTValidationError, ValueError, OSError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "fail", "error": str(error)}, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2
    if args.output:
        _write_json(Path(args.output), report)
        print(args.output)
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0
