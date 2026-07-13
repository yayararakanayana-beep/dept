"""固定5軸分布の幾何計算。"""
from __future__ import annotations

import math
from collections import deque
from functools import lru_cache
from typing import Any, Mapping

import numpy as np

from .contracts import AXIS_BINS, CELL_COUNT, GT_SHAPE

@lru_cache(maxsize=1)
def _grid() -> dict[str, np.ndarray]:
    indices = np.indices(GT_SHAPE, dtype=np.int16).reshape(5, -1).T
    coordinates = np.asarray(AXIS_BINS, dtype=np.float64)[indices]
    return {'indices': indices, 'coordinates': coordinates}


@lru_cache(maxsize=1)
def _distance_matrix() -> np.ndarray:
    coordinates = _grid()['coordinates'].astype(np.float32)
    squared = np.sum(coordinates * coordinates, axis=1)
    distance2 = squared[:, None] + squared[None, :] - 2.0 * (coordinates @ coordinates.T)
    np.maximum(distance2, 0.0, out=distance2)
    return np.sqrt(distance2, dtype=np.float32)


def _entropy(values: np.ndarray) -> float:
    positive = np.asarray(values, dtype=np.float64).reshape(-1)
    positive = positive[positive > 0.0]
    return 0.0 if positive.size == 0 else float(-np.sum(positive * np.log(positive), dtype=np.float64))


def _js_distance(left: np.ndarray, right: np.ndarray) -> float:
    p = np.asarray(left, dtype=np.float64).reshape(-1)
    q = np.asarray(right, dtype=np.float64).reshape(-1)
    middle = 0.5 * (p + q)

    def kl(a: np.ndarray, b: np.ndarray) -> float:
        mask = a > 0.0
        return float(np.sum(a[mask] * np.log(a[mask] / b[mask]), dtype=np.float64))
    return math.sqrt(max(0.5 * kl(p, middle) + 0.5 * kl(q, middle), 0.0))


def _axis_marginals(frame: np.ndarray) -> np.ndarray:
    result = []
    for axis in range(5):
        summed = tuple((index for index in range(5) if index != axis))
        result.append(np.sum(frame, axis=summed, dtype=np.float64))
    return np.stack(result)


def _one_hop_density(frame: np.ndarray) -> np.ndarray:
    density = np.asarray(frame, dtype=np.float64).copy()
    for axis in range(5):
        lower_src = [slice(None)] * 5
        lower_dst = [slice(None)] * 5
        lower_src[axis] = slice(0, -1)
        lower_dst[axis] = slice(1, None)
        density[tuple(lower_dst)] += frame[tuple(lower_src)]
        upper_src = [slice(None)] * 5
        upper_dst = [slice(None)] * 5
        upper_src[axis] = slice(1, None)
        upper_dst[axis] = slice(0, -1)
        density[tuple(upper_dst)] += frame[tuple(upper_src)]
    return density


def _component_masses(frame: np.ndarray, registry: Mapping[str, Any]) -> tuple[list[float], int]:
    settings = registry['builder_parameters']
    flat = frame.reshape(-1)
    peak = float(np.max(flat))
    threshold = max(float(settings['active_cell_absolute_floor']), peak * float(settings['active_cell_relative_to_peak_floor']))
    active = flat >= threshold
    indices = _grid()['indices']
    lookup = {tuple((int(v) for v in row)): index for index, row in enumerate(indices)}
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
            coord = indices[current]
            for axis in range(5):
                for step in (-1, 1):
                    neighbor = coord.copy()
                    neighbor[axis] += step
                    if neighbor[axis] < 0 or neighbor[axis] > 4:
                        continue
                    neighbor_id = lookup[tuple((int(v) for v in neighbor))]
                    if active[neighbor_id] and (not seen[neighbor_id]):
                        seen[neighbor_id] = True
                        queue.append(neighbor_id)
        masses.append(float(np.sum(flat[np.asarray(members, dtype=np.int32)], dtype=np.float64)))
    masses.sort(reverse=True)
    major = [mass for mass in masses if mass >= float(settings['major_component_minimum_mass'])]
    return (major, int(np.count_nonzero(active)))


def _frame_state(frame: np.ndarray, registry: Mapping[str, Any], *, expensive: bool) -> dict[str, Any]:
    flat = frame.reshape(-1)
    coordinates = _grid()['coordinates']
    centroid = np.sum(flat[:, None] * coordinates, axis=0)
    centered = coordinates - centroid
    covariance = (centered * flat[:, None]).T @ centered
    covariance = 0.5 * (covariance + covariance.T)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues = np.maximum(eigenvalues[order], 0.0)
    eigenvectors = eigenvectors[:, order]
    entropy = _entropy(flat) / math.log(CELL_COUNT)
    density = _one_hop_density(frame).reshape(-1)
    state: dict[str, Any] = {'centroid': centroid, 'covariance': covariance, 'eigenvalues': eigenvalues, 'eigenvectors': eigenvectors, 'entropy': entropy, 'density': density, 'marginals': _axis_marginals(frame)}
    if expensive:
        major_masses, active_count = _component_masses(frame, registry)
        distance = _distance_matrix()
        mean_pairwise = float(flat.astype(np.float32) @ distance @ flat.astype(np.float32))
        state.update(major_masses=major_masses, active_cell_count=active_count, mean_pairwise_distance=mean_pairwise, pairwise_distance_variance=max(2.0 * float(np.trace(covariance)) - mean_pairwise * mean_pairwise, 0.0))
    return state


def _w1_axis_marginals(previous: np.ndarray, current: np.ndarray) -> float:
    spacing = 0.25
    values = []
    for axis in range(5):
        cdf_delta = np.cumsum(previous[axis] - current[axis])[:-1]
        values.append(float(np.sum(np.abs(cdf_delta), dtype=np.float64) * spacing))
    return float(np.linalg.norm(np.asarray(values, dtype=np.float64)))
