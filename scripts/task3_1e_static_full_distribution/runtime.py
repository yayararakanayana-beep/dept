"""World execution and adaptive selection primitives for Task 3.1e."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Sequence

import numpy as np
import pandas as pd

from .core import (
    AdaptiveCandidate, DistributionTerrainV322Config, DistributionTerrainV322World,
    EXTERNAL_COLUMNS, ExternalVector, JS_EPSILON, MASS_TOLERANCE,
    NEGATIVE_TOLERANCE, SelectedCandidate, TERRAIN_FIELDS,
    all_external_update,
)


def validate_mass(raw_mass: Any, cell_count: int) -> np.ndarray:
    mass = np.asarray(raw_mass, dtype=np.float64).reshape(-1)
    if mass.shape != (cell_count,):
        raise ValueError(f"mass shape {mass.shape} does not match {(cell_count,)}")
    if not np.isfinite(mass).all():
        raise ValueError("mass contains non-finite values")
    if float(mass.min()) < -NEGATIVE_TOLERANCE:
        raise ValueError(f"mass contains negative values: minimum={float(mass.min())}")
    total = float(mass.sum(dtype=np.float64))
    if abs(total - 1.0) > MASS_TOLERANCE:
        raise ValueError(f"mass sum {total} is outside tolerance {MASS_TOLERANCE}")
    return mass.copy()


def make_world(seed: int, n_bins: int) -> DistributionTerrainV322World:
    return DistributionTerrainV322World(DistributionTerrainV322Config(seed=seed, n_bins=n_bins))


def capture_run(*, seed: int, values: Sequence[float], capture_steps: Sequence[int], n_bins: int, cell_count: int) -> dict[int, tuple[np.ndarray, dict[str, np.ndarray]]]:
    steps = sorted(set(int(step) for step in capture_steps))
    world = make_world(seed, n_bins)
    update = all_external_update(values)
    world.set_external_factors(update)
    captures: dict[int, tuple[np.ndarray, dict[str, np.ndarray]]] = {}

    def snapshot(step: int) -> None:
        mass = validate_mass(world.distribution, cell_count)
        terrain: dict[str, np.ndarray] = {}
        for field in TERRAIN_FIELDS:
            if not hasattr(world, field):
                raise AttributeError(f"world is missing required terrain field: {field}")
            values_array = np.asarray(getattr(world, field), dtype=np.float64).reshape(-1)
            if values_array.shape != (cell_count,) or not np.isfinite(values_array).all():
                raise ValueError(f"invalid terrain field {field} at step {step}")
            terrain[field] = values_array.astype(np.float32)
        captures[step] = (mass, terrain)

    if 0 in steps:
        snapshot(0)
    for step in range(1, max(steps) + 1):
        world.set_external_factors(update)
        world.step()
        if step in steps:
            snapshot(step)
    return captures


def canonical_mass(seed: int, step: int, values: Sequence[float], n_bins: int, cell_count: int) -> np.ndarray:
    return capture_run(seed=seed, values=values, capture_steps=[step], n_bins=n_bins, cell_count=cell_count)[step][0]


def js_distances(reference_matrix: np.ndarray, candidate: np.ndarray) -> np.ndarray:
    references = np.asarray(reference_matrix, dtype=np.float64)
    point = np.asarray(candidate, dtype=np.float64)
    if references.ndim != 2 or point.ndim != 1 or references.shape[1] != point.shape[0]:
        raise ValueError("incompatible JS-distance inputs")
    p = np.maximum(point, JS_EPSILON)
    p = p / p.sum(dtype=np.float64)
    q = np.maximum(references, JS_EPSILON)
    q = q / q.sum(axis=1, keepdims=True, dtype=np.float64)
    midpoint = 0.5 * (q + p[None, :])
    divergence = 0.5 * np.sum(q * np.log(q / midpoint), axis=1)
    divergence += 0.5 * np.sum(p[None, :] * np.log(p[None, :] / midpoint), axis=1)
    return np.sqrt(np.maximum(divergence, 0.0))


def select_adaptive_candidates(candidates: Sequence[AdaptiveCandidate], candidate_masses: np.ndarray, reference_masses: np.ndarray, selected_count: int) -> list[SelectedCandidate]:
    if len(candidates) != candidate_masses.shape[0]:
        raise ValueError("candidate metadata and mass rows differ")
    if selected_count > len(candidates):
        raise ValueError("adaptive_selected_count exceeds candidate-pool size")
    minimum_distances = np.array([float(js_distances(reference_masses, mass).min()) for mass in candidate_masses], dtype=np.float64)
    remaining = list(range(len(candidates)))
    selected: list[SelectedCandidate] = []
    for rank in range(1, selected_count + 1):
        best_distance = max(float(minimum_distances[index]) for index in remaining)
        tied = [index for index in remaining if float(minimum_distances[index]) == best_distance]
        best_index = min(tied, key=lambda index: candidates[index].candidate_pool_id)
        selected.append(SelectedCandidate(candidates[best_index], rank, best_distance))
        remaining.remove(best_index)
        if remaining:
            distances_to_selected = js_distances(candidate_masses[remaining], candidate_masses[best_index])
            for local_index, candidate_index in enumerate(remaining):
                minimum_distances[candidate_index] = min(minimum_distances[candidate_index], float(distances_to_selected[local_index]))
    return selected


def _assign_selected_vectors(fit_vectors: list[ExternalVector], selected: Sequence[SelectedCandidate]) -> list[ExternalVector]:
    next_index = max(int(vector.external_vector_id.rsplit("_", 1)[1]) for vector in fit_vectors) + 1
    assigned: list[ExternalVector] = []
    for selected_item in selected:
        candidate = selected_item.candidate
        assigned.append(ExternalVector(
            f"vec_fit_{next_index:06d}", "fit", "adaptive_maximin", candidate.mask_bits,
            candidate.active_factor_count, False, candidate.sobol_scramble_seed,
            candidate.sobol_index, candidate.values, candidate.candidate_pool_id,
            selected_item.selection_rank,
        ))
        next_index += 1
    return assigned


def snapshot_id(capture_policy: str, split: str, vector_id: str, seed: int, step: int) -> str:
    payload = f"{capture_policy}|{split}|{vector_id}|{seed}|{step}".encode("utf-8")
    return "snap_" + hashlib.sha256(payload).hexdigest()[:16]


def source_run_id(capture_policy: str, split: str, vector_id: str, seed: int) -> str:
    payload = f"{capture_policy}|{split}|{vector_id}|{seed}".encode("utf-8")
    return "run_" + hashlib.sha256(payload).hexdigest()[:16]


def write_csv(path: Path, rows: Sequence[dict[str, Any]], columns: Sequence[str]) -> None:
    pd.DataFrame(list(rows), columns=list(columns)).to_csv(path, index=False)


def _external_vector_rows(vectors: Sequence[ExternalVector]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for vector in vectors:
        row: dict[str, Any] = {
            "external_vector_id": vector.external_vector_id,
            "dataset_split": vector.dataset_split,
            "vector_origin": vector.vector_origin,
            "mask_bits": vector.mask_bits,
            "active_factor_count": vector.active_factor_count,
            "is_base_vector": vector.is_base_vector,
            "sobol_scramble_seed": vector.sobol_scramble_seed,
            "sobol_index": vector.sobol_index,
            "candidate_pool_id": vector.candidate_pool_id,
            "adaptive_selection_rank": vector.adaptive_selection_rank,
        }
        row.update(dict(zip(EXTERNAL_COLUMNS, vector.values)))
        rows.append(row)
    return rows


def _adaptive_pool_rows(candidates: Sequence[AdaptiveCandidate]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        row: dict[str, Any] = {
            "candidate_pool_id": candidate.candidate_pool_id,
            "mask_bits": candidate.mask_bits,
            "active_factor_count": candidate.active_factor_count,
            "sobol_scramble_seed": candidate.sobol_scramble_seed,
            "sobol_index": candidate.sobol_index,
        }
        row.update(dict(zip(EXTERNAL_COLUMNS, candidate.values)))
        rows.append(row)
    return rows
