from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .models import project_probability_simplex_rows

DISTANCE_METRICS = ("rmse_raw", "mae_raw", "js_distance", "total_variation", "raw_row_sum_absolute_error")


def row_metrics(actual: np.ndarray, raw_reconstruction: np.ndarray, distribution_reconstruction: np.ndarray | None = None) -> dict[str, np.ndarray]:
    x = np.asarray(actual, dtype=np.float64)
    raw = np.asarray(raw_reconstruction, dtype=np.float64)
    if x.shape != raw.shape or x.ndim != 2:
        raise ValueError("actual and reconstruction matrices must have identical two-dimensional shapes")
    if not np.isfinite(x).all() or not np.isfinite(raw).all():
        raise ValueError("metric inputs contain non-finite values")
    row_sums = raw.sum(axis=1, dtype=np.float64)
    if distribution_reconstruction is None:
        if np.any(row_sums <= 0.0):
            raise ValueError("reconstruction rows must have positive mass")
        distribution = raw / row_sums[:, None]
    else:
        distribution = np.asarray(distribution_reconstruction, dtype=np.float64)
        if distribution.shape != raw.shape or not np.isfinite(distribution).all() or np.any(distribution < 0.0):
            raise ValueError("distribution reconstruction is invalid")
        if np.max(np.abs(distribution.sum(axis=1) - 1.0)) > 1e-10:
            raise ValueError("distribution reconstruction rows must sum to one")
    epsilon = 1e-12
    p = np.maximum(x, epsilon)
    p /= p.sum(axis=1, keepdims=True)
    q = np.maximum(distribution, epsilon)
    q /= q.sum(axis=1, keepdims=True)
    midpoint = 0.5 * (p + q)
    js = 0.5 * np.sum(p * np.log(p / midpoint), axis=1)
    js += 0.5 * np.sum(q * np.log(q / midpoint), axis=1)
    return {
        "rmse_raw": np.sqrt(np.mean((x - raw) ** 2, axis=1)),
        "mae_raw": np.mean(np.abs(x - raw), axis=1),
        "js_distance": np.sqrt(np.maximum(js, 0.0)),
        "total_variation": 0.5 * np.sum(np.abs(x - distribution), axis=1),
        "raw_row_sum_absolute_error": np.abs(row_sums - 1.0),
        "negative_value_count": np.sum(raw < 0.0, axis=1).astype(np.float64),
        "nonfinite_value_count": np.sum(~np.isfinite(raw), axis=1).astype(np.float64),
    }


def weighted_quantile(values: np.ndarray, weights: np.ndarray, quantile: float) -> float:
    data = np.asarray(values, dtype=np.float64).reshape(-1)
    w = np.asarray(weights, dtype=np.float64).reshape(-1)
    if data.shape != w.shape or not np.isfinite(data).all() or not np.isfinite(w).all() or np.any(w <= 0.0):
        raise ValueError("invalid weighted-quantile inputs")
    order = np.argsort(data, kind="mergesort")
    sorted_values = data[order]
    sorted_weights = w[order]
    cumulative = np.cumsum(sorted_weights)
    threshold = quantile * float(sorted_weights.sum(dtype=np.float64))
    index = min(int(np.searchsorted(cumulative, threshold, side="left")), len(sorted_values) - 1)
    return float(sorted_values[index])


def aggregate(values: np.ndarray, weights: np.ndarray, aggregation: str, weighting: str) -> float:
    data = np.asarray(values, dtype=np.float64)
    if weighting == "unweighted":
        active_weights = np.ones_like(data)
    elif weighting == "weighted":
        active_weights = np.asarray(weights, dtype=np.float64)
    else:
        raise ValueError("weighting must be weighted or unweighted")
    if aggregation == "mean":
        return float(np.average(data, weights=active_weights))
    if aggregation == "median":
        return weighted_quantile(data, active_weights, 0.5)
    if aggregation == "p95":
        return weighted_quantile(data, active_weights, 0.95)
    if aggregation == "max":
        return float(np.max(data))
    if aggregation == "sum":
        return float(np.sum(data))
    raise ValueError(f"unknown aggregation {aggregation}")


def reconstruction_metric_rows(
    *, run_id: str, method: str, rank: int, split: str,
    actual: np.ndarray, raw_reconstruction: np.ndarray, weights: np.ndarray,
    row_map: pd.DataFrame, evidence_basis_path: str, evidence_activation_path: str,
    distribution_reconstruction: np.ndarray | None = None,
) -> list[dict[str, Any]]:
    metrics = row_metrics(actual, raw_reconstruction, distribution_reconstruction)
    groups: list[tuple[str, str, np.ndarray]] = [("all", "all", np.ones(len(row_map), dtype=bool))]
    for column in ("distribution_group", "source_step", "active_factor_count", "vector_origin"):
        for value in sorted(row_map[column].drop_duplicates().tolist(), key=str):
            groups.append((column, str(value), row_map[column].astype(str).to_numpy() == str(value)))
    rows: list[dict[str, Any]] = []
    for subgroup_type, subgroup_value, selector in groups:
        selected_weights = np.asarray(weights[selector], dtype=np.float64)
        for weighting in ("weighted", "unweighted"):
            for metric_name in DISTANCE_METRICS:
                selected_values = metrics[metric_name][selector]
                for aggregation_name in ("mean", "median", "p95", "max"):
                    rows.append({
                        "run_id": run_id, "method": method, "rank": rank, "split": split,
                        "subgroup_type": subgroup_type, "subgroup_value": subgroup_value,
                        "weighting": weighting, "metric": metric_name, "aggregation": aggregation_name,
                        "value": aggregate(selected_values, selected_weights, aggregation_name, weighting),
                        "row_count": int(selector.sum()),
                        "weight_sum": float(selected_weights.sum()) if weighting == "weighted" else int(selector.sum()),
                        "evidence_basis_path": evidence_basis_path,
                        "evidence_activation_path": evidence_activation_path,
                        "independently_recomputed": False,
                    })
            for metric_name in ("negative_value_count", "nonfinite_value_count"):
                rows.append({
                    "run_id": run_id, "method": method, "rank": rank, "split": split,
                    "subgroup_type": subgroup_type, "subgroup_value": subgroup_value,
                    "weighting": weighting, "metric": metric_name, "aggregation": "sum",
                    "value": aggregate(metrics[metric_name][selector], selected_weights, "sum", weighting),
                    "row_count": int(selector.sum()),
                    "weight_sum": float(selected_weights.sum()) if weighting == "weighted" else int(selector.sum()),
                    "evidence_basis_path": evidence_basis_path,
                    "evidence_activation_path": evidence_activation_path,
                    "independently_recomputed": False,
                })
    return rows


def pca_reconstruction(mean: np.ndarray, components: np.ndarray, scores: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    raw = np.asarray(mean, dtype=np.float64)[None, :] + np.asarray(scores, dtype=np.float64) @ np.asarray(components, dtype=np.float64)
    return raw, project_probability_simplex_rows(raw)
