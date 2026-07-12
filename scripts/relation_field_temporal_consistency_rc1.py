"""固定5軸 動的関係場 RF-5: K_tによる候補流れの時間整合。"""
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
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from scipy.optimize import linprog
from scipy.sparse import csr_matrix, eye, hstack

from relation_field_single_transition_rc1 import (
    GENESIS_HASH,
    _compute_gt_hash,
    _compute_history_chain_hash,
    _load_grid,
    _validate_distribution,
    load_contract as load_rf3_contract,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "configs" / "relation_field_temporal_consistency_rc1.json"
CELL_COUNT = 3125
AXIS_COUNT = 5
DESCRIPTOR_DIMENSION = 31


class RelationFieldTemporalError(ValueError):
    """RF-5契約、履歴、候補流れ、成果物の不整合。"""


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
    if contract.get("contract_version") != "relation_field_temporal_consistency_rc1":
        raise RelationFieldTemporalError("unsupported RF-5 contract")
    candidate = contract.get("candidate_generation", {})
    if candidate.get("primary_solver") != "highs-ds":
        raise RelationFieldTemporalError("RF-5 primary solver must match RF-3 highs-ds")
    if int(candidate.get("maximum_candidates_per_transition", 0)) < 2:
        raise RelationFieldTemporalError("RF-5 requires room for multiple candidates")
    descriptor = contract.get("translation_invariant_descriptor", {})
    if int(descriptor.get("dimension", -1)) != DESCRIPTOR_DIMENSION:
        raise RelationFieldTemporalError("RF-5 descriptor dimension mismatch")
    temporal = contract.get("temporal_path_inference", {})
    if int(temporal.get("beam_width", 0)) < 1:
        raise RelationFieldTemporalError("RF-5 beam width must be positive")
    if int(temporal.get("maximum_optimal_paths_saved", 0)) > int(temporal.get("beam_width", 0)):
        raise RelationFieldTemporalError("saved optimal paths cannot exceed beam width")


def _load_grid_with_nodes(root: Path) -> dict[str, Any]:
    grid = _load_grid(root)
    with np.load(root / "nodes.npz", allow_pickle=False) as loaded:
        node_values = loaded["values"].copy()
    if node_values.shape != (CELL_COUNT, AXIS_COUNT):
        raise RelationFieldTemporalError("RF-2 node coordinate payload mismatch")
    grid["node_values"] = np.asarray(node_values, dtype=np.float64)
    return grid


def _validate_sha256(value: str, name: str) -> None:
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise RelationFieldTemporalError(f"{name} must be a lowercase SHA-256 digest")


def _read_history_prefix(path: Path, to_t: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if int(row["t"]) > to_t:
                break
            rows.append(row)
    return rows


def _load_history_window(
    trajectory_dir: Path,
    *,
    start_t: int,
    to_t: int,
    mass_tolerance: float,
    minimum_transition_count: int,
) -> dict[str, Any]:
    if start_t < 0 or to_t - start_t < minimum_transition_count:
        raise RelationFieldTemporalError("RF-5 history window is too short")
    mass_path = trajectory_dir / "gt_mass.npy"
    ledger_path = trajectory_dir / "history_ledger.csv"
    if not mass_path.is_file() or not ledger_path.is_file():
        raise RelationFieldTemporalError("canonical trajectory requires gt_mass.npy and history_ledger.csv")
    prefix = _read_history_prefix(ledger_path, to_t)
    if not prefix:
        raise RelationFieldTemporalError("history prefix is empty")
    previous_gt_hash = ""
    chain_hash = GENESIS_HASH
    rows_by_t: dict[int, dict[str, str]] = {}
    for row in prefix:
        t = int(row["t"])
        if t in rows_by_t:
            raise RelationFieldTemporalError("history prefix contains duplicate t")
        rows_by_t[t] = row
        for field in ("gt_hash", "history_chain_hash", "source_state_hash"):
            _validate_sha256(row.get(field, ""), field)
        if row.get("previous_gt_hash"):
            _validate_sha256(row["previous_gt_hash"], "previous_gt_hash")
        if row.get("previous_gt_hash") != previous_gt_hash:
            raise RelationFieldTemporalError("history prefix previous_gt_hash mismatch")
        chain_hash = _compute_history_chain_hash(chain_hash, row["gt_hash"], t)
        if row.get("history_chain_hash") != chain_hash:
            raise RelationFieldTemporalError("history prefix chain hash mismatch")
        previous_gt_hash = row["gt_hash"]
    requested_times = list(range(start_t, to_t + 1))
    if any(t not in rows_by_t for t in requested_times):
        raise RelationFieldTemporalError("requested K_t window is incomplete")
    selected_rows = [rows_by_t[t] for t in requested_times]
    for index, row in enumerate(selected_rows):
        if row.get("phase") != "pre_transition":
            raise RelationFieldTemporalError("RF-5 requires pre_transition G_t frames")
        if row.get("admissible_for_research", "").lower() != "true":
            raise RelationFieldTemporalError("RF-5 selected row is not research-admissible")
        if index > 0:
            previous = selected_rows[index - 1]
            if row.get("continuity_status") != "continuous" or int(row.get("delta_t", 0)) != 1:
                raise RelationFieldTemporalError("RF-5 requires continuous selected links")
            if row.get("previous_gt_hash") != previous.get("gt_hash"):
                raise RelationFieldTemporalError("RF-5 selected history link hash mismatch")
    trajectory_id = selected_rows[0].get("trajectory_id", "")
    if not trajectory_id or any(row.get("trajectory_id") != trajectory_id for row in selected_rows):
        raise RelationFieldTemporalError("RF-5 trajectory identity mismatch")
    mass = np.load(mass_path, mmap_mode="r", allow_pickle=False)
    if mass.ndim != 6 or tuple(mass.shape[1:]) != (5, 5, 5, 5, 5) or mass.dtype != np.dtype("float64"):
        raise RelationFieldTemporalError("canonical gt_mass.npy shape or dtype mismatch")
    frames: list[np.ndarray] = []
    for row in selected_rows:
        row_index = int(row["gt_row_index"])
        if row_index < 0 or row_index >= mass.shape[0]:
            raise RelationFieldTemporalError("history row index is outside gt_mass.npy")
        frame = _validate_distribution(np.asarray(mass[row_index]), mass_tolerance)
        expected_hash = _compute_gt_hash(
            trajectory_id=trajectory_id,
            t=int(row["t"]),
            distribution=frame,
            source_state_hash=row["source_state_hash"],
        )
        if row.get("gt_hash") != expected_hash:
            raise RelationFieldTemporalError("selected G_t hash mismatch")
        frames.append(frame)
    return {
        "trajectory_id": trajectory_id,
        "frames": frames,
        "rows": selected_rows,
        "history_prefix_rows_read": len(prefix),
        "history_chain_hash": selected_rows[-1]["history_chain_hash"],
        "max_t_read": to_t,
    }


def _secondary_weights(size: int, edge_variable_count: int, seed: int) -> np.ndarray:
    indices = np.arange(edge_variable_count, dtype=np.uint64) + np.uint64(seed * 1000003 + 1)
    with np.errstate(over="ignore"):
        values = indices + np.uint64(0x9E3779B97F4A7C15)
        values = (values ^ (values >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
        values = (values ^ (values >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
        values = values ^ (values >> np.uint64(31))
    mask = np.uint64((1 << 53) - 1)
    weights = np.zeros(size, dtype=np.float64)
    weights[:edge_variable_count] = ((values & mask).astype(np.float64) / float(1 << 53)) * 2.0 - 1.0
    return weights


def _flow_signature(flow: np.ndarray, threshold: float, decimals: int) -> tuple[str, np.ndarray]:
    normalized = np.asarray(flow, dtype=np.float64).copy()
    normalized[np.abs(normalized) < threshold] = 0.0
    normalized = np.round(normalized, decimals=decimals)
    return hashlib.sha256(normalized.tobytes(order="C")).hexdigest(), normalized


def _solve_candidate_lp(
    delta: np.ndarray,
    incidence: csr_matrix,
    *,
    edge_cost: float,
    residual_penalty: float,
    method: str,
    primary_cap: float | None = None,
    secondary_objective: np.ndarray | None = None,
) -> tuple[Any, np.ndarray]:
    edge_count = int(incidence.shape[1])
    identity = eye(CELL_COUNT, format="csr", dtype=np.float64)
    equality = hstack([incidence, -incidence, identity, -identity], format="csr")
    primary = np.concatenate([
        np.full(edge_count * 2, edge_cost, dtype=np.float64),
        np.full(CELL_COUNT * 2, residual_penalty, dtype=np.float64),
    ])
    objective = primary if secondary_objective is None else np.asarray(secondary_objective, dtype=np.float64)
    inequality = None
    upper = None
    if primary_cap is not None:
        inequality = csr_matrix(primary.reshape(1, -1))
        upper = np.asarray([primary_cap], dtype=np.float64)
    result = linprog(
        objective,
        A_eq=equality,
        b_eq=np.asarray(delta, dtype=np.float64),
        A_ub=inequality,
        b_ub=upper,
        bounds=(0.0, None),
        method=method,
        options={
            "presolve": True,
            "primal_feasibility_tolerance": 1e-9,
            "dual_feasibility_tolerance": 1e-9,
        },
    )
    if not result.success or result.x is None:
        raise RelationFieldTemporalError(f"RF-5 candidate solver failed: {result.message}")
    return result, primary


def _extract_candidate(result: Any, incidence: csr_matrix) -> dict[str, np.ndarray]:
    edge_count = int(incidence.shape[1])
    vector = np.asarray(result.x, dtype=np.float64)
    forward = np.maximum(vector[:edge_count], 0.0)
    reverse = np.maximum(vector[edge_count:2 * edge_count], 0.0)
    positive = np.maximum(vector[2 * edge_count:2 * edge_count + CELL_COUNT], 0.0)
    negative = np.maximum(vector[2 * edge_count + CELL_COUNT:], 0.0)
    net = forward - reverse
    reconstructed = np.asarray(incidence @ net, dtype=np.float64)
    residual = positive - negative
    return {
        "forward": forward,
        "reverse": reverse,
        "net": net,
        "reconstructed": reconstructed,
        "residual": residual,
    }


def compute_translation_invariant_descriptor(
    net_flow: np.ndarray,
    observed_delta: np.ndarray,
    grid: Mapping[str, Any],
    *,
    threshold: float = 1e-12,
) -> np.ndarray:
    net = np.asarray(net_flow, dtype=np.float64)
    delta = np.asarray(observed_delta, dtype=np.float64)
    edge_count = int(grid["edge_count"])
    if net.shape != (edge_count,) or delta.shape != (CELL_COUNT,):
        raise RelationFieldTemporalError("RF-5 descriptor input shape mismatch")
    loss = np.maximum(-delta, 0.0)
    loss_total = float(loss.sum(dtype=np.float64))
    loss_centroid = (
        np.sum(loss[:, None] * grid["node_values"], axis=0) / loss_total
        if loss_total > threshold
        else np.zeros(AXIS_COUNT, dtype=np.float64)
    )
    axis_flow = np.zeros(AXIS_COUNT, dtype=np.float64)
    source_offsets = np.zeros((AXIS_COUNT, AXIS_COUNT), dtype=np.float64)
    for axis in range(AXIS_COUNT):
        edge_ids = np.flatnonzero((grid["edge_axis"] == axis) & (np.abs(net) > threshold))
        if edge_ids.size == 0:
            continue
        amounts = np.abs(net[edge_ids])
        axis_flow[axis] = float(net[edge_ids].sum(dtype=np.float64))
        actual_sources = np.where(
            net[edge_ids] > 0.0,
            grid["edge_source"][edge_ids],
            grid["edge_target"][edge_ids],
        )
        source_centroid = np.sum(
            amounts[:, None] * grid["node_values"][actual_sources], axis=0
        ) / float(amounts.sum(dtype=np.float64))
        source_offsets[axis] = source_centroid - loss_centroid
    total_flow = float(np.abs(net).sum(dtype=np.float64))
    descriptor = np.concatenate([axis_flow, source_offsets.reshape(-1), np.asarray([total_flow])])
    if descriptor.shape != (DESCRIPTOR_DIMENSION,):
        raise RelationFieldTemporalError("RF-5 descriptor construction mismatch")
    return descriptor


def generate_transition_candidates(
    observed_delta: np.ndarray,
    grid: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> list[dict[str, Any]]:
    settings = contract["candidate_generation"]
    delta = np.asarray(observed_delta, dtype=np.float64)
    edge_count = int(grid["edge_count"])
    if delta.shape != (CELL_COUNT,):
        raise RelationFieldTemporalError("RF-5 observed delta shape mismatch")
    if not np.any(delta):
        zero = np.zeros(edge_count, dtype=np.float64)
        return [{
            "signature": hashlib.sha256(zero.tobytes(order="C")).hexdigest(),
            "net_flow": zero,
            "residual": np.zeros(CELL_COUNT, dtype=np.float64),
            "reconstructed": np.zeros(CELL_COUNT, dtype=np.float64),
            "primary_objective": 0.0,
            "primary_excess": 0.0,
            "descriptor": compute_translation_invariant_descriptor(zero, delta, grid),
        }]
    baseline, primary = _solve_candidate_lp(
        delta,
        grid["incidence"],
        edge_cost=float(settings["coordinate_edge_cost"]),
        residual_penalty=float(settings["residual_penalty"]),
        method=str(settings["primary_solver"]),
    )
    baseline_objective = float(primary @ baseline.x)
    raw_results = [baseline]
    primary_cap = baseline_objective + float(settings["primary_objective_slack"])
    for seed in settings["secondary_objective_seeds"]:
        secondary = _secondary_weights(primary.size, edge_count * 2, int(seed))
        witness, _ = _solve_candidate_lp(
            delta,
            grid["incidence"],
            edge_cost=float(settings["coordinate_edge_cost"]),
            residual_penalty=float(settings["residual_penalty"]),
            method=str(settings["primary_solver"]),
            primary_cap=primary_cap,
            secondary_objective=secondary,
        )
        if float(primary @ witness.x) > primary_cap + 1e-9:
            raise RelationFieldTemporalError("RF-5 candidate violated primary objective cap")
        raw_results.append(witness)
    candidates_by_signature: dict[str, dict[str, Any]] = {}
    threshold = float(settings["candidate_flow_threshold"])
    decimals = int(settings["candidate_signature_decimals"])
    for result in raw_results:
        extracted = _extract_candidate(result, grid["incidence"])
        signature, normalized_net = _flow_signature(extracted["net"], threshold, decimals)
        primary_objective = float(primary @ result.x)
        residual = delta - extracted["reconstructed"]
        candidate = {
            "signature": signature,
            "net_flow": normalized_net,
            "residual": residual,
            "reconstructed": extracted["reconstructed"],
            "primary_objective": primary_objective,
            "primary_excess": max(primary_objective - baseline_objective, 0.0),
            "descriptor": compute_translation_invariant_descriptor(normalized_net, delta, grid),
        }
        existing = candidates_by_signature.get(signature)
        if existing is None or candidate["primary_objective"] < existing["primary_objective"]:
            candidates_by_signature[signature] = candidate
    candidates = [candidates_by_signature[key] for key in sorted(candidates_by_signature)]
    maximum = int(settings["maximum_candidates_per_transition"])
    if len(candidates) > maximum:
        candidates = candidates[:maximum]
    reconstruction_tolerance = 1e-9
    for candidate in candidates:
        if float(np.max(np.abs(delta - candidate["reconstructed"] - candidate["residual"]))) > reconstruction_tolerance:
            raise RelationFieldTemporalError("RF-5 candidate reconstruction mismatch")
    return candidates


def infer_temporal_paths(
    candidate_sets: Sequence[Sequence[Mapping[str, Any]]],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    if not candidate_sets or any(not candidates for candidates in candidate_sets):
        raise RelationFieldTemporalError("RF-5 temporal inference requires non-empty candidate sets")
    settings = contract["temporal_path_inference"]
    descriptor_weight = float(settings["descriptor_l1_weight"])
    primary_weight = float(settings["primary_excess_weight"])
    beam_width = int(settings["beam_width"])
    beam: list[tuple[float, tuple[int, ...]]] = [
        (primary_weight * float(candidate.get("primary_excess", 0.0)), (index,))
        for index, candidate in enumerate(candidate_sets[0])
    ]
    beam.sort(key=lambda item: (item[0], item[1]))
    beam_truncated = len(beam) > beam_width
    beam = beam[:beam_width]
    for transition_index in range(1, len(candidate_sets)):
        expanded: list[tuple[float, tuple[int, ...]]] = []
        for score, path in beam:
            previous = np.asarray(candidate_sets[transition_index - 1][path[-1]]["descriptor"], dtype=np.float64)
            for candidate_index, candidate in enumerate(candidate_sets[transition_index]):
                current = np.asarray(candidate["descriptor"], dtype=np.float64)
                temporal_cost = descriptor_weight * float(np.sum(np.abs(current - previous)))
                primary_cost = primary_weight * float(candidate.get("primary_excess", 0.0))
                expanded.append((score + temporal_cost + primary_cost, path + (candidate_index,)))
        expanded.sort(key=lambda item: (item[0], item[1]))
        if len(expanded) > beam_width:
            beam_truncated = True
        beam = expanded[:beam_width]
    best_score = float(beam[0][0])
    score_slack = float(settings["optimal_path_score_slack"])
    optimal = [item for item in beam if item[0] <= best_score + score_slack]
    maximum_saved = int(settings["maximum_optimal_paths_saved"])
    optimal_truncated = len(optimal) > maximum_saved
    optimal = optimal[:maximum_saved]
    baseline_score = primary_weight * sum(
        float(candidate_sets[index][0].get("primary_excess", 0.0)) for index in range(len(candidate_sets))
    )
    for index in range(1, len(candidate_sets)):
        previous = np.asarray(candidate_sets[index - 1][0]["descriptor"], dtype=np.float64)
        current = np.asarray(candidate_sets[index][0]["descriptor"], dtype=np.float64)
        baseline_score += descriptor_weight * float(np.sum(np.abs(current - previous)))
    return {
        "best_score": best_score,
        "independent_baseline_score": float(baseline_score),
        "representative_path": list(optimal[0][1]),
        "optimal_paths": [list(path) for _, path in optimal],
        "optimal_path_scores": [float(score) for score, _ in optimal],
        "optimal_path_count": len(optimal),
        "beam_truncated": beam_truncated,
        "optimal_path_family_truncated": optimal_truncated,
        "path_search_exhaustive": not beam_truncated,
    }


def compute_common_structure(
    candidate_sets: Sequence[Sequence[Mapping[str, Any]]],
    path_result: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, np.ndarray]:
    paths = [tuple(int(value) for value in path) for path in path_result["optimal_paths"]]
    transition_count = len(candidate_sets)
    edge_count = np.asarray(candidate_sets[0][0]["net_flow"]).size
    flow_cube = np.empty((len(paths), transition_count, edge_count), dtype=np.float64)
    descriptor_cube = np.empty((len(paths), transition_count, DESCRIPTOR_DIMENSION), dtype=np.float64)
    for path_index, path in enumerate(paths):
        for transition_index, candidate_index in enumerate(path):
            candidate = candidate_sets[transition_index][candidate_index]
            flow_cube[path_index, transition_index] = candidate["net_flow"]
            descriptor_cube[path_index, transition_index] = candidate["descriptor"]
    threshold = float(contract["candidate_generation"]["candidate_flow_threshold"])
    common = np.zeros((transition_count, edge_count), dtype=np.float64)
    union = np.any(np.abs(flow_cube) > threshold, axis=0)
    for transition_index in range(transition_count):
        values = flow_cube[:, transition_index, :]
        all_positive = np.all(values > threshold, axis=0)
        all_negative = np.all(values < -threshold, axis=0)
        if np.any(all_positive):
            common[transition_index, all_positive] = np.min(values[:, all_positive], axis=0)
        if np.any(all_negative):
            common[transition_index, all_negative] = np.max(values[:, all_negative], axis=0)
    axis_values = descriptor_cube[:, :, :AXIS_COUNT]
    representative_path = tuple(int(value) for value in path_result["representative_path"])
    representative_flow = np.stack([
        np.asarray(candidate_sets[index][candidate_index]["net_flow"], dtype=np.float64)
        for index, candidate_index in enumerate(representative_path)
    ])
    representative_descriptor = np.stack([
        np.asarray(candidate_sets[index][candidate_index]["descriptor"], dtype=np.float64)
        for index, candidate_index in enumerate(representative_path)
    ])
    return {
        "common_net_flow": common,
        "union_edge_mask": union.astype(np.uint8),
        "mean_net_flow": np.mean(flow_cube, axis=0),
        "axis_flow_min": np.min(axis_values, axis=0),
        "axis_flow_max": np.max(axis_values, axis=0),
        "axis_flow_mean": np.mean(axis_values, axis=0),
        "representative_net_flow": representative_flow,
        "representative_descriptor": representative_descriptor,
    }


def _temporal_diagnostics(
    candidate_sets: Sequence[Sequence[Mapping[str, Any]]],
    path_result: Mapping[str, Any],
    common: Mapping[str, np.ndarray],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    descriptors = np.asarray(common["representative_descriptor"], dtype=np.float64)
    axis_flow = descriptors[:, :AXIS_COUNT]
    change_scores = [0.0]
    for index in range(1, descriptors.shape[0]):
        change_scores.append(float(np.sum(np.abs(descriptors[index] - descriptors[index - 1]))))
    threshold = float(contract["temporal_path_inference"]["field_change_score_threshold"])
    change_flags = [score > threshold for score in change_scores]
    reversals = np.zeros_like(axis_flow, dtype=np.uint8)
    acceleration = np.zeros_like(axis_flow, dtype=np.float64)
    for index in range(1, axis_flow.shape[0]):
        reversals[index] = ((axis_flow[index] * axis_flow[index - 1]) < 0.0).astype(np.uint8)
        acceleration[index] = axis_flow[index] - axis_flow[index - 1]
    common_flow = np.asarray(common["common_net_flow"], dtype=np.float64)
    union = np.asarray(common["union_edge_mask"], dtype=np.uint8).astype(bool)
    edge_common_fraction: list[float] = []
    for index in range(common_flow.shape[0]):
        union_count = int(np.count_nonzero(union[index]))
        common_count = int(np.count_nonzero(np.abs(common_flow[index]) > 1e-12))
        edge_common_fraction.append(1.0 if union_count == 0 else common_count / union_count)
    axis_spread = np.asarray(common["axis_flow_max"] - common["axis_flow_min"], dtype=np.float64)
    return {
        "descriptor_change_score": change_scores,
        "field_change_candidate": change_flags,
        "field_change_flag_is_diagnostic_only": True,
        "axis_direction_reversal": reversals.tolist(),
        "axis_flow_acceleration": acceleration.tolist(),
        "candidate_count_per_transition": [len(candidates) for candidates in candidate_sets],
        "optimal_path_count": int(path_result["optimal_path_count"]),
        "beam_truncated": bool(path_result["beam_truncated"]),
        "optimal_path_family_truncated": bool(path_result["optimal_path_family_truncated"]),
        "edge_common_fraction": edge_common_fraction,
        "axis_flow_spread": axis_spread.tolist(),
        "best_temporal_score": float(path_result["best_score"]),
        "independent_baseline_score": float(path_result["independent_baseline_score"]),
    }


def _flatten_candidate_sets(
    candidate_sets: Sequence[Sequence[Mapping[str, Any]]],
    observed_deltas: np.ndarray,
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    offsets = [0]
    net_flows: list[np.ndarray] = []
    residuals: list[np.ndarray] = []
    reconstructions: list[np.ndarray] = []
    descriptors: list[np.ndarray] = []
    objectives: list[float] = []
    excesses: list[float] = []
    transition_index: list[int] = []
    index_rows: list[dict[str, Any]] = []
    for t_index, candidates in enumerate(candidate_sets):
        rows: list[dict[str, Any]] = []
        for local_index, candidate in enumerate(candidates):
            flat_index = len(net_flows)
            net_flows.append(np.asarray(candidate["net_flow"], dtype=np.float64))
            residuals.append(np.asarray(candidate["residual"], dtype=np.float64))
            reconstructions.append(np.asarray(candidate["reconstructed"], dtype=np.float64))
            descriptors.append(np.asarray(candidate["descriptor"], dtype=np.float64))
            objectives.append(float(candidate["primary_objective"]))
            excesses.append(float(candidate["primary_excess"]))
            transition_index.append(t_index)
            rows.append({
                "candidate_index": local_index,
                "flat_candidate_index": flat_index,
                "signature": candidate["signature"],
                "primary_objective": float(candidate["primary_objective"]),
                "primary_excess": float(candidate["primary_excess"]),
            })
        offsets.append(len(net_flows))
        index_rows.append({"transition_index": t_index, "candidates": rows})
    arrays = {
        "candidate_offsets": np.asarray(offsets, dtype=np.int32),
        "candidate_transition_index": np.asarray(transition_index, dtype=np.int32),
        "candidate_net_flow": np.stack(net_flows),
        "candidate_residual": np.stack(residuals),
        "candidate_reconstructed_delta": np.stack(reconstructions),
        "candidate_descriptor": np.stack(descriptors),
        "candidate_primary_objective": np.asarray(objectives, dtype=np.float64),
        "candidate_primary_excess": np.asarray(excesses, dtype=np.float64),
        "observed_delta": np.asarray(observed_deltas, dtype=np.float64),
    }
    return arrays, {"transitions": index_rows}


def build_temporal_relation_field(
    trajectory_dir: str | Path,
    grid_artifact_dir: str | Path,
    output: str | Path,
    *,
    start_t: int,
    to_t: int,
    contract_path: str | Path = DEFAULT_CONTRACT,
) -> Path:
    contract = load_contract(contract_path)
    rf3_contract = load_rf3_contract()
    target = Path(output)
    if target.exists():
        raise RelationFieldTemporalError(f"output already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    grid = _load_grid_with_nodes(Path(grid_artifact_dir))
    history = _load_history_window(
        Path(trajectory_dir),
        start_t=int(start_t),
        to_t=int(to_t),
        mass_tolerance=float(rf3_contract["input"]["distribution_mass_tolerance"]),
        minimum_transition_count=int(contract["input"]["minimum_transition_count"]),
    )
    observed_deltas = np.stack([
        (history["frames"][index + 1] - history["frames"][index]).reshape(-1, order="C")
        for index in range(len(history["frames"]) - 1)
    ])
    candidate_sets = [generate_transition_candidates(delta, grid, contract) for delta in observed_deltas]
    path_result = infer_temporal_paths(candidate_sets, contract)
    common = compute_common_structure(candidate_sets, path_result, contract)
    diagnostics = _temporal_diagnostics(candidate_sets, path_result, common, contract)
    candidate_arrays, candidate_index = _flatten_candidate_sets(candidate_sets, observed_deltas)
    transition_times = np.asarray(list(range(start_t + 1, to_t + 1)), dtype=np.int32)
    identity_basis = {
        "contract_version": contract["contract_version"],
        "trajectory_id": history["trajectory_id"],
        "start_t": int(start_t),
        "to_t": int(to_t),
        "source_history_chain_hash": history["history_chain_hash"],
        "grid_manifest_hash": grid["manifest_hash"],
    }
    relation_field_id = hashlib.sha256(_canonical_json(identity_basis)).hexdigest()
    identity = {
        "relation_field_id": relation_field_id,
        **identity_basis,
        "transition_count": int(observed_deltas.shape[0]),
        "max_source_t_read": int(to_t),
        "history_window_is_derived": True,
        "unique_true_flow_claim": False,
    }
    uncertainty = {
        "identifiability": {
            "candidate_search_exhaustive": False,
            "candidate_count_per_transition": [len(candidates) for candidates in candidate_sets],
            "optimal_path_count": int(path_result["optimal_path_count"]),
            "optimal_path_family_truncated": bool(path_result["optimal_path_family_truncated"]),
            "representative_path_is_not_unique_truth": True,
        },
        "evidence_sufficiency": {
            "history_start_t": int(start_t),
            "history_end_t": int(to_t),
            "transition_count": int(observed_deltas.shape[0]),
        },
        "temporal_stability": {
            "best_temporal_score": float(path_result["best_score"]),
            "independent_baseline_score": float(path_result["independent_baseline_score"]),
            "path_search_exhaustive": bool(path_result["path_search_exhaustive"]),
            "beam_truncated": bool(path_result["beam_truncated"]),
        },
        "out_of_range": {"status": "not_evaluated_without_reference_corpus"},
        "prediction_performed": False,
        "risk_prediction_performed": False,
    }
    summary = {
        "contract_version": contract["contract_version"],
        "relation_field_id": relation_field_id,
        "trajectory_id": history["trajectory_id"],
        "start_t": int(start_t),
        "to_t": int(to_t),
        "transition_count": int(observed_deltas.shape[0]),
        "candidate_count_per_transition": [len(candidates) for candidates in candidate_sets],
        "optimal_path_count": int(path_result["optimal_path_count"]),
        "best_temporal_score": float(path_result["best_score"]),
        "independent_baseline_score": float(path_result["independent_baseline_score"]),
        "temporal_score_improvement": float(path_result["independent_baseline_score"] - path_result["best_score"]),
        "scientific_relation_field_claim": "B_limited_temporal_candidate_field",
        "prediction_performed": False,
        "risk_prediction_performed": False,
    }
    validation = {
        "rf5_temporal_consistency_gate": "passed",
        "transition_count": int(observed_deltas.shape[0]),
        "candidate_reconstruction_gate": "passed",
        "temporal_score_not_worse_than_independent_baseline": bool(
            path_result["best_score"] <= path_result["independent_baseline_score"] + 1e-12
        ),
        "multiple_candidate_flow_detected": any(len(candidates) > 1 for candidates in candidate_sets),
        "optimal_path_family_preserved": int(path_result["optimal_path_count"]) >= 1,
        "causal_cutoff_respected": True,
        "source_writeback_performed": False,
        "prediction_performed": False,
        "risk_prediction_performed": False,
    }
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp-", dir=target.parent))
    try:
        storage = contract["storage"]
        _dump_json(temporary / storage["contract_file"], contract)
        _dump_json(temporary / storage["identity_file"], identity)
        _write_npz(temporary / storage["candidate_flows_file"], candidate_arrays)
        candidate_index.update({"transition_times": transition_times.tolist()})
        _dump_json(temporary / storage["candidate_index_file"], candidate_index)
        _dump_json(temporary / storage["temporal_paths_file"], path_result)
        _write_npz(temporary / storage["representative_flow_file"], {
            "transition_times": transition_times,
            "net_flow": common["representative_net_flow"],
            "descriptor": common["representative_descriptor"],
            "axis_signed_flow": common["representative_descriptor"][:, :AXIS_COUNT],
        })
        _write_npz(temporary / storage["common_structure_file"], {
            "transition_times": transition_times,
            "common_net_flow": common["common_net_flow"],
            "union_edge_mask": common["union_edge_mask"],
            "mean_net_flow": common["mean_net_flow"],
            "axis_flow_min": common["axis_flow_min"],
            "axis_flow_max": common["axis_flow_max"],
            "axis_flow_mean": common["axis_flow_mean"],
        })
        _dump_json(temporary / storage["temporal_diagnostics_file"], diagnostics)
        _dump_json(temporary / storage["uncertainty_file"], uncertainty)
        _dump_json(temporary / storage["provenance_file"], {
            "trajectory_id": history["trajectory_id"],
            "source_files_read": ["gt_mass.npy:selected_rows_only", "history_ledger.csv:prefix_through_to_t"],
            "history_prefix_rows_read": int(history["history_prefix_rows_read"]),
            "max_t_read": int(history["max_t_read"]),
            "observed_logs_read": False,
            "truth_files_read": False,
            "canonical_gt_kt_copied": False,
            "source_writeback_performed": False,
            "grid_manifest_hash": grid["manifest_hash"],
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


def _verify_manifest(root: Path) -> None:
    manifest = _load_json(root / "manifest.json")
    expected: set[str] = set()
    for entry in manifest.get("files", []):
        relative = str(entry["path"])
        expected.add(relative)
        path = root / relative
        if not path.is_file() or path.stat().st_size != int(entry["size_bytes"]) or _sha256_file(path) != entry["sha256"]:
            raise RelationFieldTemporalError(f"manifest mismatch: {relative}")
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    if expected != actual:
        raise RelationFieldTemporalError("manifest file set mismatch")


def validate_temporal_relation_field(input_path: str | Path, grid_artifact_dir: str | Path) -> dict[str, Any]:
    root = Path(input_path)
    contract = _load_json(root / "contract.json")
    validate_contract(contract)
    _verify_manifest(root)
    grid = _load_grid_with_nodes(Path(grid_artifact_dir))
    identity = _load_json(root / "identity.json")
    validation = _load_json(root / "validation.json")
    paths = _load_json(root / "temporal_paths.json")
    if identity.get("grid_manifest_hash") != grid["manifest_hash"]:
        raise RelationFieldTemporalError("RF-5 grid manifest identity mismatch")
    if identity.get("max_source_t_read") != identity.get("to_t"):
        raise RelationFieldTemporalError("RF-5 causal cutoff mismatch")
    if any(path.name in {"gt_mass.npy", "history_ledger.csv"} for path in root.rglob("*")):
        raise RelationFieldTemporalError("canonical G_t or K_t copied into RF-5 output")
    with np.load(root / "candidate_flows.npz", allow_pickle=False) as loaded:
        offsets = loaded["candidate_offsets"]
        net_flow = loaded["candidate_net_flow"]
        residual = loaded["candidate_residual"]
        reconstructed = loaded["candidate_reconstructed_delta"]
        descriptors = loaded["candidate_descriptor"]
        observed = loaded["observed_delta"]
    transition_count = int(identity["transition_count"])
    if offsets.shape != (transition_count + 1,) or int(offsets[0]) != 0 or int(offsets[-1]) != net_flow.shape[0]:
        raise RelationFieldTemporalError("RF-5 candidate offsets mismatch")
    if net_flow.shape[1] != int(grid["edge_count"]) or descriptors.shape != (net_flow.shape[0], DESCRIPTOR_DIMENSION):
        raise RelationFieldTemporalError("RF-5 candidate array shape mismatch")
    if residual.shape != (net_flow.shape[0], CELL_COUNT) or reconstructed.shape != residual.shape:
        raise RelationFieldTemporalError("RF-5 residual or reconstruction shape mismatch")
    if observed.shape != (transition_count, CELL_COUNT):
        raise RelationFieldTemporalError("RF-5 observed delta shape mismatch")
    tolerance = 1e-9
    for transition_index in range(transition_count):
        for flat_index in range(int(offsets[transition_index]), int(offsets[transition_index + 1])):
            expected_reconstruction = np.asarray(grid["incidence"] @ net_flow[flat_index], dtype=np.float64)
            if float(np.max(np.abs(expected_reconstruction - reconstructed[flat_index]))) > tolerance:
                raise RelationFieldTemporalError("RF-5 candidate incidence reconstruction mismatch")
            if float(np.max(np.abs(observed[transition_index] - reconstructed[flat_index] - residual[flat_index]))) > tolerance:
                raise RelationFieldTemporalError("RF-5 candidate observed delta mismatch")
            expected_descriptor = compute_translation_invariant_descriptor(
                net_flow[flat_index], observed[transition_index], grid
            )
            if float(np.max(np.abs(expected_descriptor - descriptors[flat_index]))) > tolerance:
                raise RelationFieldTemporalError("RF-5 candidate descriptor mismatch")
    candidate_counts = [int(offsets[index + 1] - offsets[index]) for index in range(transition_count)]
    for path in paths.get("optimal_paths", []):
        if len(path) != transition_count or any(
            int(candidate) < 0 or int(candidate) >= candidate_counts[index]
            for index, candidate in enumerate(path)
        ):
            raise RelationFieldTemporalError("RF-5 optimal path index mismatch")
    if float(paths["best_score"]) > float(paths["independent_baseline_score"]) + 1e-12:
        raise RelationFieldTemporalError("RF-5 temporal score is worse than the independent baseline")
    if validation.get("rf5_temporal_consistency_gate") != "passed":
        raise RelationFieldTemporalError("RF-5 validation gate did not pass")
    return validation


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--trajectory", required=True)
    build.add_argument("--grid-artifact", required=True)
    build.add_argument("--output", required=True)
    build.add_argument("--start-t", type=int, required=True)
    build.add_argument("--to-t", type=int, required=True)
    build.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    validate = commands.add_parser("validate")
    validate.add_argument("--input", required=True)
    validate.add_argument("--grid-artifact", required=True)
    args = parser.parse_args(argv)
    if args.command == "build":
        output = build_temporal_relation_field(
            args.trajectory,
            args.grid_artifact,
            args.output,
            start_t=args.start_t,
            to_t=args.to_t,
            contract_path=args.contract,
        )
        print(json.dumps({"output": str(output), "status": "built"}, ensure_ascii=False, sort_keys=True))
    else:
        print(json.dumps(validate_temporal_relation_field(args.input, args.grid_artifact), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
