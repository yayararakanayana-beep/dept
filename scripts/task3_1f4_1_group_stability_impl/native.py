from __future__ import annotations

import itertools
import math
from typing import Any, Iterable

import numpy as np
import pandas as pd
from scipy.optimize import nnls

from .common import AXIS_NAMES, EPSILON
from .matching import _cosine, _normalize_basis, _sqrt_js_distance


def _weighted_global_distribution(fit: np.ndarray, fit_weights: np.ndarray) -> np.ndarray:
    distribution = np.average(fit, axis=0, weights=fit_weights)
    distribution = np.maximum(distribution, 0.0)
    distribution /= distribution.sum(dtype=np.float64)
    return distribution


def _axis_marginal(distribution: np.ndarray, axis_index: int, n_bins: int) -> np.ndarray:
    tensor = np.asarray(distribution, dtype=np.float64).reshape((n_bins,) * len(AXIS_NAMES), order="C")
    sum_axes = tuple(index for index in range(len(AXIS_NAMES)) if index != axis_index)
    values = tensor.sum(axis=sum_axes, dtype=np.float64)
    values /= values.sum(dtype=np.float64)
    return values


def _pair_joint(distribution: np.ndarray, axis_a: int, axis_b: int, n_bins: int) -> np.ndarray:
    tensor = np.asarray(distribution, dtype=np.float64).reshape((n_bins,) * len(AXIS_NAMES), order="C")
    sum_axes = tuple(index for index in range(len(AXIS_NAMES)) if index not in {axis_a, axis_b})
    joint = tensor.sum(axis=sum_axes, dtype=np.float64)
    if axis_a > axis_b:
        joint = joint.T
    joint /= joint.sum(dtype=np.float64)
    return joint


def _entropy(probabilities: np.ndarray) -> float:
    values = np.maximum(np.asarray(probabilities, dtype=np.float64), EPSILON)
    values /= values.sum(dtype=np.float64)
    return float(-np.sum(values * np.log(values)))


def _pair_relation(joint: np.ndarray) -> dict[str, float]:
    probabilities = np.asarray(joint, dtype=np.float64)
    probabilities /= probabilities.sum(dtype=np.float64)
    marginal_a = probabilities.sum(axis=1)
    marginal_b = probabilities.sum(axis=0)
    independence = marginal_a[:, None] * marginal_b[None, :]
    ratio = np.maximum(probabilities, EPSILON) / np.maximum(independence, EPSILON)
    mutual_information = float(np.sum(probabilities * np.log(ratio)))
    entropy_a = _entropy(marginal_a)
    entropy_b = _entropy(marginal_b)
    nmi_denominator = math.sqrt(max(entropy_a * entropy_b, 0.0))
    normalized_mi = mutual_information / nmi_denominator if nmi_denominator > 0.0 else 0.0
    bins_a = np.arange(len(marginal_a), dtype=np.float64)
    bins_b = np.arange(len(marginal_b), dtype=np.float64)
    mean_a = float(np.dot(bins_a, marginal_a))
    mean_b = float(np.dot(bins_b, marginal_b))
    centered_a = bins_a - mean_a
    centered_b = bins_b - mean_b
    covariance = float(np.sum(probabilities * centered_a[:, None] * centered_b[None, :]))
    variance_a = float(np.dot(centered_a**2, marginal_a))
    variance_b = float(np.dot(centered_b**2, marginal_b))
    correlation = covariance / math.sqrt(variance_a * variance_b) if variance_a > 0.0 and variance_b > 0.0 else 0.0
    return {
        "mutual_information": mutual_information,
        "normalized_mutual_information": float(normalized_mi),
        "signed_correlation": float(correlation),
        "independence_l1": float(np.sum(np.abs(probabilities - independence))),
    }


def native_signature_tables(
    *,
    rank: int,
    run_id: str,
    basis: np.ndarray,
    global_distribution: np.ndarray,
    n_bins: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    normalized = _normalize_basis(basis)
    expected_cell_count = n_bins ** len(AXIS_NAMES)
    if normalized.shape[1] != expected_cell_count:
        raise ValueError(f"cell count {normalized.shape[1]} does not match {n_bins}^{len(AXIS_NAMES)}")
    global_marginals = [_axis_marginal(global_distribution, index, n_bins) for index in range(len(AXIS_NAMES))]
    marginal_rows: list[dict[str, Any]] = []
    contribution_rows: list[dict[str, Any]] = []
    pair_joint_rows: list[dict[str, Any]] = []
    pair_summary_rows: list[dict[str, Any]] = []
    bin_values = np.arange(n_bins, dtype=np.float64)
    for structure_index, structure in enumerate(normalized):
        structure_id = f"R{rank:02d}-S{structure_index + 1:03d}"
        contrasts: list[float] = []
        for axis_index, axis_name in enumerate(AXIS_NAMES):
            marginal = _axis_marginal(structure, axis_index, n_bins)
            contrast = _sqrt_js_distance(marginal, global_marginals[axis_index])
            contrasts.append(contrast)
            mean = float(np.dot(bin_values, marginal))
            variance = float(np.dot((bin_values - mean) ** 2, marginal))
            for bin_index, probability in enumerate(marginal):
                marginal_rows.append(
                    {
                        "rank": rank,
                        "run_id": run_id,
                        "structure_id": structure_id,
                        "basis_row_index": structure_index,
                        "axis_index": axis_index,
                        "axis_name": axis_name,
                        "bin_index": bin_index,
                        "probability": float(probability),
                        "axis_mean_bin": mean,
                        "axis_variance": variance,
                        "axis_entropy": _entropy(marginal),
                        "axis_contrast_js_distance": contrast,
                    }
                )
        contrast_sum = float(sum(contrasts))
        for axis_index, axis_name in enumerate(AXIS_NAMES):
            contribution_rows.append(
                {
                    "rank": rank,
                    "run_id": run_id,
                    "structure_id": structure_id,
                    "axis_index": axis_index,
                    "axis_name": axis_name,
                    "axis_contrast_js_distance": contrasts[axis_index],
                    "native_axis_contribution_share": contrasts[axis_index] / contrast_sum if contrast_sum > 0.0 else 0.2,
                }
            )
        for axis_a, axis_b in itertools.combinations(range(len(AXIS_NAMES)), 2):
            joint = _pair_joint(structure, axis_a, axis_b, n_bins)
            relation = _pair_relation(joint)
            pair_id = f"{AXIS_NAMES[axis_a]}__{AXIS_NAMES[axis_b]}"
            for bin_a in range(n_bins):
                for bin_b in range(n_bins):
                    pair_joint_rows.append(
                        {
                            "rank": rank,
                            "run_id": run_id,
                            "structure_id": structure_id,
                            "pair_id": pair_id,
                            "axis_a_index": axis_a,
                            "axis_a_name": AXIS_NAMES[axis_a],
                            "axis_b_index": axis_b,
                            "axis_b_name": AXIS_NAMES[axis_b],
                            "bin_a": bin_a,
                            "bin_b": bin_b,
                            "probability": float(joint[bin_a, bin_b]),
                        }
                    )
            pair_summary_rows.append(
                {
                    "rank": rank,
                    "run_id": run_id,
                    "structure_id": structure_id,
                    "pair_id": pair_id,
                    "axis_a_index": axis_a,
                    "axis_a_name": AXIS_NAMES[axis_a],
                    "axis_b_index": axis_b,
                    "axis_b_name": AXIS_NAMES[axis_b],
                    **relation,
                }
            )
    pair_summary = pd.DataFrame(pair_summary_rows)
    if not pair_summary.empty:
        pair_summary["relation_strength_rank"] = pair_summary.groupby("structure_id")["normalized_mutual_information"].rank(
            method="first", ascending=False
        ).astype(int)
    return (
        pd.DataFrame(marginal_rows),
        pd.DataFrame(contribution_rows),
        pd.DataFrame(pair_joint_rows),
        pair_summary,
    )


def _pearson(left: np.ndarray, right: np.ndarray) -> float:
    x = np.asarray(left, dtype=np.float64)
    y = np.asarray(right, dtype=np.float64)
    if len(x) != len(y) or len(x) == 0 or np.std(x) <= 0.0 or np.std(y) <= 0.0:
        return float("nan")
    return float(np.corrcoef(x, y)[0, 1])


def _rankdata(values: np.ndarray) -> np.ndarray:
    return pd.Series(np.asarray(values, dtype=np.float64)).rank(method="average").to_numpy(dtype=np.float64)


def _activation_consistency(
    source_fit: np.ndarray,
    source_validation: np.ndarray,
    target_fit: np.ndarray,
    target_validation: np.ndarray,
    target_indices: Iterable[int],
) -> dict[str, float]:
    columns = list(target_indices)
    design_fit = np.asarray(target_fit[:, columns], dtype=np.float64)
    design_validation = np.asarray(target_validation[:, columns], dtype=np.float64)
    coefficients, _ = nnls(design_fit, np.asarray(source_fit, dtype=np.float64))
    predicted_fit = design_fit @ coefficients
    predicted_validation = design_validation @ coefficients
    validation_actual = np.asarray(source_validation, dtype=np.float64)
    scale = max(float(np.mean(np.abs(validation_actual))), EPSILON)
    top_count = max(1, int(math.ceil(0.10 * len(validation_actual))))
    actual_top = set(np.argsort(validation_actual)[-top_count:].tolist())
    predicted_top = set(np.argsort(predicted_validation)[-top_count:].tolist())
    return {
        "fit_coefficient_sum": float(coefficients.sum()),
        "validation_weighted_pearson": _pearson(validation_actual, predicted_validation),
        "validation_unweighted_pearson": _pearson(validation_actual, predicted_validation),
        "validation_spearman": _pearson(_rankdata(validation_actual), _rankdata(predicted_validation)),
        "validation_cosine": _cosine(validation_actual, predicted_validation),
        "validation_normalized_mae": float(np.mean(np.abs(validation_actual - predicted_validation)) / scale),
        "validation_p95_absolute_error": float(np.quantile(np.abs(validation_actual - predicted_validation), 0.95)),
        "validation_top10_overlap": float(len(actual_top & predicted_top) / top_count),
        "fit_pearson": _pearson(np.asarray(source_fit), predicted_fit),
    }
