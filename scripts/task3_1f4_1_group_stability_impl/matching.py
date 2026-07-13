from __future__ import annotations

import math

import numpy as np
from scipy.optimize import nnls

from .common import EPSILON, MAX_JS_DISTANCE, GroupMatch


def _normalize_basis(basis: np.ndarray) -> np.ndarray:
    values = np.asarray(basis, dtype=np.float64)
    if values.ndim != 2 or not np.isfinite(values).all() or np.any(values < 0.0):
        raise ValueError("basis must be finite, non-negative, and 2D")
    sums = values.sum(axis=1, keepdims=True)
    if np.any(sums <= 0.0):
        raise ValueError("basis contains zero-mass structures")
    return values / sums


def _sqrt_js_distance(left: np.ndarray, right: np.ndarray) -> float:
    p = np.maximum(np.asarray(left, dtype=np.float64), EPSILON)
    q = np.maximum(np.asarray(right, dtype=np.float64), EPSILON)
    p /= p.sum(dtype=np.float64)
    q /= q.sum(dtype=np.float64)
    midpoint = 0.5 * (p + q)
    divergence = 0.5 * np.sum(p * np.log(p / midpoint)) + 0.5 * np.sum(q * np.log(q / midpoint))
    return float(math.sqrt(max(float(divergence), 0.0)))


def _js_similarity(left: np.ndarray, right: np.ndarray) -> tuple[float, float]:
    distance = _sqrt_js_distance(left, right)
    return distance, float(1.0 - distance / MAX_JS_DISTANCE)


def _cosine(left: np.ndarray, right: np.ndarray) -> float:
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    return float(np.dot(left, right) / denominator) if denominator > 0.0 else 0.0


def _fit_convex_weights(source: np.ndarray, target_basis: np.ndarray, indices: tuple[int, ...]) -> tuple[np.ndarray, np.ndarray]:
    if len(indices) == 1:
        weights = np.ones(1, dtype=np.float64)
    else:
        matrix = target_basis[list(indices)].T
        augmented = np.vstack([matrix, np.full((1, matrix.shape[1]), 25.0, dtype=np.float64)])
        target = np.concatenate([source, np.asarray([25.0], dtype=np.float64)])
        weights, _ = nnls(augmented, target)
        if not np.isfinite(weights).all() or weights.sum() <= 0.0:
            weights = np.full(len(indices), 1.0 / len(indices), dtype=np.float64)
    weights = np.maximum(weights, 0.0)
    weights /= weights.sum(dtype=np.float64)
    mixture = weights @ target_basis[list(indices)]
    mixture = np.maximum(mixture, 0.0)
    mixture /= mixture.sum(dtype=np.float64)
    return weights, mixture


def _prune_group(
    source: np.ndarray,
    target_basis: np.ndarray,
    indices: tuple[int, ...],
    weights: np.ndarray,
    minimum_weight: float,
) -> tuple[tuple[int, ...], np.ndarray, np.ndarray]:
    keep = np.flatnonzero(weights >= minimum_weight)
    if len(keep) == 0:
        keep = np.asarray([int(np.argmax(weights))], dtype=np.int64)
    pruned_indices = tuple(int(indices[index]) for index in keep)
    pruned_weights = weights[keep]
    pruned_weights /= pruned_weights.sum(dtype=np.float64)
    mixture = pruned_weights @ target_basis[list(pruned_indices)]
    mixture /= mixture.sum(dtype=np.float64)
    return pruned_indices, pruned_weights, mixture


def best_group_match(
    source: np.ndarray,
    target_basis: np.ndarray,
    *,
    source_index: int = 0,
    max_group_size: int = 4,
    similarity_threshold: float = 0.85,
    intermediate_threshold: float = 0.80,
    minimum_weight: float = 0.10,
    beam_width: int = 32,
) -> GroupMatch:
    source_values = np.asarray(source, dtype=np.float64)
    source_values /= source_values.sum(dtype=np.float64)
    targets = _normalize_basis(target_basis)
    if max_group_size < 1:
        raise ValueError("max_group_size must be positive")
    max_group_size = min(max_group_size, targets.shape[0])

    def evaluate(indices: tuple[int, ...]) -> tuple[float, float, float, np.ndarray, np.ndarray]:
        weights, mixture = _fit_convex_weights(source_values, targets, indices)
        pruned_indices, pruned_weights, pruned_mixture = _prune_group(
            source_values, targets, indices, weights, minimum_weight
        )
        distance, similarity = _js_similarity(source_values, pruned_mixture)
        cosine = _cosine(source_values, pruned_mixture)
        return distance, similarity, cosine, pruned_weights, np.asarray(pruned_indices, dtype=np.int64)

    candidates: dict[tuple[int, ...], tuple[float, float, float, np.ndarray, np.ndarray]] = {}
    for index in range(targets.shape[0]):
        key = (index,)
        candidates[key] = evaluate(key)

    best_key: tuple[int, ...] | None = None
    best_data: tuple[float, float, float, np.ndarray, np.ndarray] | None = None
    beam_rank = 0
    for group_size in range(1, max_group_size + 1):
        ordered = sorted(candidates.items(), key=lambda item: (-item[1][1], len(item[0]), item[0]))
        if not ordered:
            break
        current_key, current_data = ordered[0]
        if best_data is None or current_data[1] > best_data[1] + 1e-15 or (
            abs(current_data[1] - best_data[1]) <= 1e-15 and len(current_key) < len(best_key or ())
        ):
            best_key, best_data = current_key, current_data
            beam_rank = 1
        if current_data[1] >= similarity_threshold:
            best_key, best_data = current_key, current_data
            beam_rank = 1
            break
        if group_size == max_group_size:
            break
        next_candidates: dict[tuple[int, ...], tuple[float, float, float, np.ndarray, np.ndarray]] = {}
        for key, _ in ordered[:beam_width]:
            for new_index in range(targets.shape[0]):
                if new_index in key:
                    continue
                expanded = tuple(sorted((*key, new_index)))
                if len(expanded) != group_size + 1 or expanded in next_candidates:
                    continue
                next_candidates[expanded] = evaluate(expanded)
        candidates = next_candidates

    if best_key is None or best_data is None:
        raise RuntimeError("group search produced no candidate")
    distance, similarity, cosine, weights, pruned_indices = best_data
    final_indices = tuple(int(value) for value in pruned_indices.tolist())
    single_best = max(_js_similarity(source_values, target)[1] for target in targets)
    if len(final_indices) == 1 and similarity >= similarity_threshold:
        classification = "strong_single"
    elif single_best < intermediate_threshold and similarity >= similarity_threshold:
        classification = "group_rescued"
    elif single_best < similarity_threshold and similarity >= similarity_threshold:
        classification = "group_preserved"
    elif similarity >= intermediate_threshold:
        classification = "intermediate"
    else:
        classification = "unresolved"
    return GroupMatch(
        source_index=source_index,
        target_indices=final_indices,
        weights=tuple(float(value) for value in weights),
        js_distance=float(distance),
        js_similarity=float(similarity),
        cosine_similarity=float(cosine),
        classification=classification,
        beam_rank=beam_rank,
    )
