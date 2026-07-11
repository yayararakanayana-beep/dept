from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy.optimize import linear_sum_assignment
try:
    from sklearn.decomposition import NMF, non_negative_factorization
except ModuleNotFoundError:  # pragma: no cover - exercised in minimal CI images
    NMF = None
    non_negative_factorization = None


@dataclass(frozen=True)
class NMFResult:
    basis: np.ndarray
    fit_activations: np.ndarray
    validation_activations: np.ndarray
    n_iter: int
    converged: bool
    init_method: str
    init_seed: int


@dataclass(frozen=True)
class PCAResult:
    weighted_mean: np.ndarray
    components: np.ndarray
    fit_scores: np.ndarray
    validation_scores: np.ndarray
    explained_variance_ratio: np.ndarray


def _validate_probability_matrix(matrix: np.ndarray, name: str) -> np.ndarray:
    values = np.asarray(matrix, dtype=np.float64)
    if values.ndim != 2 or values.shape[0] == 0 or values.shape[1] == 0:
        raise ValueError(f"{name} must be a non-empty two-dimensional matrix")
    if not np.isfinite(values).all() or np.any(values < -1e-12):
        raise ValueError(f"{name} must be finite and non-negative")
    if np.max(np.abs(values.sum(axis=1, dtype=np.float64) - 1.0)) > 1e-8:
        raise ValueError(f"{name} rows must sum to one")
    return values


def _validate_weights(weights: np.ndarray, row_count: int) -> np.ndarray:
    values = np.asarray(weights, dtype=np.float64).reshape(-1)
    if values.shape != (row_count,) or not np.isfinite(values).all() or np.any(values <= 0.0):
        raise ValueError("sample weights must be finite, positive, and row-aligned")
    return values


def normalize_basis_and_activations(basis: np.ndarray, activations: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    h = np.asarray(basis, dtype=np.float64)
    w = np.asarray(activations, dtype=np.float64)
    if h.ndim != 2 or w.ndim != 2 or w.shape[1] != h.shape[0]:
        raise ValueError("basis and activation shapes are incompatible")
    if not np.isfinite(h).all() or not np.isfinite(w).all() or np.any(h < 0.0) or np.any(w < 0.0):
        raise ValueError("basis and activations must be finite and non-negative")
    row_sums = h.sum(axis=1, dtype=np.float64)
    if not np.isfinite(row_sums).all() or np.any(row_sums <= 0.0):
        raise ValueError("every basis row must have positive finite mass")
    normalized_basis = h / row_sums[:, None]
    normalized_activations = w * row_sums[None, :]
    before = w @ h
    after = normalized_activations @ normalized_basis
    if not np.allclose(before, after, rtol=1e-10, atol=1e-12):
        raise ValueError("basis normalization changed the reconstruction")
    return normalized_basis, normalized_activations


def transform_fixed_kl_basis(
    matrix: np.ndarray,
    basis: np.ndarray,
    *,
    max_iter: int,
    tolerance: float,
    seed: int,
) -> tuple[np.ndarray, int, bool]:
    x = _validate_probability_matrix(matrix, "transform matrix")
    h = np.asarray(basis, dtype=np.float64)
    if h.ndim != 2 or h.shape[1] != x.shape[1] or not np.isfinite(h).all() or np.any(h < 0.0):
        raise ValueError("fixed basis is invalid")
    if non_negative_factorization is None:
        rng = np.random.default_rng(seed)
        w = rng.random((x.shape[0], h.shape[0])) + 1e-6
        for n_iter in range(1, max_iter + 1):
            reconstruction = np.maximum(w @ h, 1e-12)
            numerator = (x / reconstruction) @ h.T
            denominator = np.maximum(np.ones_like(x) @ h.T, 1e-12)
            updated = w * numerator / denominator
            if np.max(np.abs(updated - w)) < tolerance:
                w = updated
                break
            w = updated
        returned_h = h
    else:
        w, returned_h, n_iter = non_negative_factorization(
            x,
            H=h.copy(),
            n_components=h.shape[0],
            init="custom",
            update_H=False,
            solver="mu",
            beta_loss="kullback-leibler",
            tol=tolerance,
            max_iter=max_iter,
            alpha_W=0.0,
            alpha_H=0.0,
            l1_ratio=0.0,
            random_state=seed,
            shuffle=False,
        )
    if not np.allclose(returned_h, h, rtol=0.0, atol=0.0):
        raise ValueError("validation transform modified the fixed basis")
    if not np.isfinite(w).all() or np.any(w < 0.0):
        raise ValueError("validation activations are invalid")
    return np.asarray(w, dtype=np.float64), int(n_iter), bool(n_iter < max_iter)


def fit_weighted_kl_nmf(
    fit_matrix: np.ndarray,
    fit_weights: np.ndarray,
    validation_matrix: np.ndarray,
    *,
    rank: int,
    init_method: str,
    init_seed: int,
    max_iter: int,
    tolerance: float,
) -> NMFResult:
    fit = _validate_probability_matrix(fit_matrix, "fit matrix")
    validation = _validate_probability_matrix(validation_matrix, "validation matrix")
    weights = _validate_weights(fit_weights, fit.shape[0])
    if fit.shape[1] != validation.shape[1]:
        raise ValueError("fit and validation cell counts differ")
    if rank <= 0 or rank > min(fit.shape):
        raise ValueError("rank must be positive and no larger than min(fit shape)")
    if init_method not in {"nndsvda", "random"}:
        raise ValueError("unsupported frozen initialization")
    weighted_fit = fit * weights[:, None]
    if NMF is None:
        rng = np.random.default_rng(0 if init_method == "nndsvda" else init_seed)
        basis0 = fit[:rank].copy() + 1e-6 if init_method == "nndsvda" and fit.shape[0] >= rank else rng.random((rank, fit.shape[1])) + 1e-6
        weighted_activations = rng.random((fit.shape[0], rank)) + 1e-6
        for n_iter in range(1, max_iter + 1):
            recon = np.maximum(weighted_activations @ basis0, 1e-12)
            new_w = weighted_activations * ((weighted_fit / recon) @ basis0.T) / np.maximum(np.ones_like(weighted_fit) @ basis0.T, 1e-12)
            recon = np.maximum(new_w @ basis0, 1e-12)
            new_h = basis0 * (new_w.T @ (weighted_fit / recon)) / np.maximum(new_w.T @ np.ones_like(weighted_fit), 1e-12)
            delta = max(float(np.max(np.abs(new_w - weighted_activations))), float(np.max(np.abs(new_h - basis0))))
            weighted_activations, basis0 = new_w, new_h
            if delta < tolerance:
                break
        basis, weighted_activations = normalize_basis_and_activations(basis0, weighted_activations)
        model_n_iter = n_iter
    else:
        model = NMF(
            n_components=rank,
            init=init_method,
            solver="mu",
            beta_loss="kullback-leibler",
            tol=tolerance,
            max_iter=max_iter,
            random_state=None if init_method == "nndsvda" else init_seed,
            alpha_W=0.0,
            alpha_H=0.0,
            l1_ratio=0.0,
            shuffle=False,
        )
        weighted_activations = model.fit_transform(weighted_fit)
        basis, weighted_activations = normalize_basis_and_activations(model.components_, weighted_activations)
        model_n_iter = int(model.n_iter_)
    fit_activations = weighted_activations / weights[:, None]
    if not np.isfinite(fit_activations).all() or np.any(fit_activations < 0.0):
        raise ValueError("corrected fit activations are invalid")
    validation_activations, _, _ = transform_fixed_kl_basis(
        validation,
        basis,
        max_iter=max_iter,
        tolerance=tolerance,
        seed=init_seed,
    )
    return NMFResult(
        basis=basis,
        fit_activations=fit_activations,
        validation_activations=validation_activations,
        n_iter=int(model_n_iter),
        converged=bool(model_n_iter < max_iter),
        init_method=init_method,
        init_seed=init_seed,
    )


def fit_weighted_pca(
    fit_matrix: np.ndarray,
    fit_weights: np.ndarray,
    validation_matrix: np.ndarray,
    rank: int,
) -> PCAResult:
    fit = _validate_probability_matrix(fit_matrix, "fit matrix")
    validation = _validate_probability_matrix(validation_matrix, "validation matrix")
    weights = _validate_weights(fit_weights, fit.shape[0])
    if rank <= 0 or rank > min(fit.shape):
        raise ValueError("invalid PCA rank")
    mean = np.average(fit, axis=0, weights=weights)
    centered = fit - mean[None, :]
    weighted_centered = centered * np.sqrt(weights)[:, None]
    _, singular_values, vt = np.linalg.svd(weighted_centered, full_matrices=False)
    components = np.asarray(vt[:rank], dtype=np.float64)
    fit_scores = centered @ components.T
    validation_scores = (validation - mean[None, :]) @ components.T
    denominator = float(np.sum(singular_values**2))
    explained = (singular_values[:rank] ** 2) / denominator if denominator > 0.0 else np.zeros(rank)
    return PCAResult(
        weighted_mean=np.asarray(mean, dtype=np.float64),
        components=components,
        fit_scores=np.asarray(fit_scores, dtype=np.float64),
        validation_scores=np.asarray(validation_scores, dtype=np.float64),
        explained_variance_ratio=np.asarray(explained, dtype=np.float64),
    )


def project_probability_simplex_rows(matrix: np.ndarray) -> np.ndarray:
    values = np.asarray(matrix, dtype=np.float64)
    if values.ndim != 2 or not np.isfinite(values).all():
        raise ValueError("simplex projection input must be finite and two-dimensional")
    output = np.empty_like(values)
    for row_index, row in enumerate(values):
        sorted_row = np.sort(row)[::-1]
        cumulative = np.cumsum(sorted_row) - 1.0
        candidates = np.nonzero(sorted_row - cumulative / np.arange(1, len(row) + 1) > 0.0)[0]
        rho = int(candidates[-1])
        theta = cumulative[rho] / float(rho + 1)
        projected = np.maximum(row - theta, 0.0)
        output[row_index] = projected
    if np.max(np.abs(output.sum(axis=1) - 1.0)) > 1e-10 or np.any(output < 0.0):
        raise ValueError("simplex projection failed")
    return output


def sqrt_js_distance_matrix(a: np.ndarray, b: np.ndarray, epsilon: float = 1e-12) -> np.ndarray:
    left = np.asarray(a, dtype=np.float64)
    right = np.asarray(b, dtype=np.float64)
    if left.ndim != 2 or right.ndim != 2 or left.shape[1] != right.shape[1]:
        raise ValueError("component matrices are incompatible")
    left = np.maximum(left, epsilon)
    right = np.maximum(right, epsilon)
    left /= left.sum(axis=1, keepdims=True)
    right /= right.sum(axis=1, keepdims=True)
    output = np.empty((left.shape[0], right.shape[0]), dtype=np.float64)
    for index, row in enumerate(left):
        midpoint = 0.5 * (row[None, :] + right)
        divergence = 0.5 * np.sum(row[None, :] * np.log(row[None, :] / midpoint), axis=1)
        divergence += 0.5 * np.sum(right * np.log(right / midpoint), axis=1)
        output[index] = np.sqrt(np.maximum(divergence, 0.0))
    return output


def match_components(basis_a: np.ndarray, basis_b: np.ndarray) -> list[dict[str, Any]]:
    if basis_a.shape[0] != basis_b.shape[0]:
        raise ValueError("component matching requires equal ranks")
    distances = sqrt_js_distance_matrix(basis_a, basis_b)
    rows, columns = linear_sum_assignment(distances)
    maximum = float(np.sqrt(np.log(2.0)))
    matches: list[dict[str, Any]] = []
    for order, (row, column) in enumerate(zip(rows, columns), start=1):
        left = basis_a[row]
        right = basis_b[column]
        denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
        cosine = float(np.dot(left, right) / denominator) if denominator > 0.0 else 0.0
        distance = float(distances[row, column])
        matches.append(
            {
                "component_index_a": int(row),
                "component_index_b": int(column),
                "js_distance": distance,
                "js_similarity": float(1.0 - distance / maximum),
                "cosine_similarity": cosine,
                "matching_cost_rank": order,
            }
        )
    return matches
