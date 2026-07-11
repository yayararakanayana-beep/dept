from __future__ import annotations
from itertools import combinations
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
from .metrics import pca_reconstruction, reconstruction_metric_rows
from .models import match_components
from .stage_bc_run import PRIMARY, weighted_quantile

def _reconstruction_for_run(
    root: Path,
    run: pd.Series | dict[str, Any],
    split: str,
    row_count: int,
) -> tuple[np.ndarray, np.ndarray | None]:
    method = str(run["method"])
    if method in {PRIMARY, "nmf_frobenius"}:
        basis = np.load(root / str(run["basis_path"]), allow_pickle=False)
        activation_key = "fit_activation_path" if split == "fit" else "validation_activation_path"
        activations = np.load(root / str(run[activation_key]), allow_pickle=False)
        return activations @ basis, None
    if method == "mean_baseline":
        mean = np.load(root / str(run["basis_path"]), allow_pickle=False)
        return np.repeat(mean[None, :], row_count, axis=0), None
    if method == "weighted_pca":
        components_path = root / str(run["basis_path"])
        run_dir = components_path.parent
        mean = np.load(run_dir / "weighted_mean.npy", allow_pickle=False)
        score_key = "fit_activation_path" if split == "fit" else "validation_activation_path"
        scores = np.load(root / str(run[score_key]), allow_pickle=False)
        return pca_reconstruction(mean, np.load(components_path, allow_pickle=False), scores)
    raise ValueError(f"unsupported method {method}")

def _all_reconstruction_metrics(
    root: Path,
    runs: pd.DataFrame,
    fit: np.ndarray,
    fit_weights: np.ndarray,
    fit_map: pd.DataFrame,
    validation: np.ndarray,
    validation_weights: np.ndarray,
    validation_map: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, run in runs[runs["status"] == "completed"].iterrows():
        for split, actual, weights, row_map in (
            ("fit", fit, fit_weights, fit_map),
            ("validation", validation, validation_weights, validation_map),
        ):
            raw, distribution = _reconstruction_for_run(root, run, split, len(actual))
            activation_key = "fit_activation_path" if split == "fit" else "validation_activation_path"
            rows.extend(
                reconstruction_metric_rows(
                    run_id=str(run["run_id"]),
                    method=str(run["method"]),
                    rank=int(run["rank"]),
                    split=split,
                    actual=actual,
                    raw_reconstruction=raw,
                    distribution_reconstruction=distribution,
                    weights=weights,
                    row_map=row_map,
                    evidence_basis_path=str(run["basis_path"]),
                    evidence_activation_path=str(run[activation_key]),
                )
            )
    return pd.DataFrame(rows)

def _sqrt_js_rows(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    epsilon = 1e-12
    p = np.maximum(np.asarray(left, dtype=np.float64), epsilon)
    q = np.maximum(np.asarray(right, dtype=np.float64), epsilon)
    p /= p.sum(axis=1, keepdims=True)
    q /= q.sum(axis=1, keepdims=True)
    midpoint = 0.5 * (p + q)
    divergence = 0.5 * np.sum(p * np.log(p / midpoint), axis=1)
    divergence += 0.5 * np.sum(q * np.log(q / midpoint), axis=1)
    return np.sqrt(np.maximum(divergence, 0.0))

def _weighted_aggregate(values: np.ndarray, weights: np.ndarray, aggregation: str) -> float:
    if aggregation == "mean":
        return float(np.average(values, weights=weights))
    if aggregation == "median":
        return weighted_quantile(values, weights, 0.5)
    if aggregation == "p95":
        return weighted_quantile(values, weights, 0.95)
    if aggregation == "max":
        return float(np.max(values))
    raise ValueError(aggregation)

def _pair_deformation_rows(
    *,
    run_id: str,
    method: str,
    rank: int,
    split: str,
    actual: np.ndarray,
    reconstructed_distribution: np.ndarray,
    metadata: pd.DataFrame,
) -> list[dict[str, Any]]:
    index = {str(row.snapshot_id): int(row.bundle_row_index) for row in metadata.itertuples(index=False)}
    records: list[dict[str, Any]] = []
    for row in metadata[metadata["distribution_group"] == "external_augmented"].itertuples(index=False):
        external_index = int(row.bundle_row_index)
        base_id = str(row.matched_base_snapshot_id)
        if base_id not in index:
            raise ValueError(f"matched base snapshot missing for {row.snapshot_id}")
        base_index = index[base_id]
        base_row = metadata.iloc[base_index]
        if (
            str(base_row["distribution_group"]) != "base_v3_3"
            or str(base_row["dataset_split"]) != split
            or int(base_row["seed"]) != int(row.seed)
            or int(base_row["source_step"]) != int(row.source_step)
        ):
            raise ValueError(f"invalid external/base pair for {row.snapshot_id}")
        actual_external = actual[external_index : external_index + 1]
        actual_base = actual[base_index : base_index + 1]
        reconstructed_external = reconstructed_distribution[external_index : external_index + 1]
        reconstructed_base = reconstructed_distribution[base_index : base_index + 1]
        actual_js = float(_sqrt_js_rows(actual_external, actual_base)[0])
        reconstructed_js = float(_sqrt_js_rows(reconstructed_external, reconstructed_base)[0])
        actual_delta = actual_external[0] - actual_base[0]
        reconstructed_delta = reconstructed_external[0] - reconstructed_base[0]
        denominator = float(np.linalg.norm(actual_delta) * np.linalg.norm(reconstructed_delta))
        cosine = float(np.dot(actual_delta, reconstructed_delta) / denominator) if denominator > 0.0 else 1.0
        relative_l1 = float(
            np.sum(np.abs(actual_delta - reconstructed_delta)) / max(np.sum(np.abs(actual_delta)), 1e-12)
        )
        records.append(
            {
                "source_step": int(row.source_step),
                "active_factor_count": int(row.active_factor_count),
                "analysis_weight": float(row.analysis_weight),
                "external_base_js_actual": actual_js,
                "external_base_js_reconstructed": reconstructed_js,
                "external_base_js_preservation_absolute_error": abs(actual_js - reconstructed_js),
                "signed_delta_cosine_similarity": cosine,
                "signed_delta_relative_l1_error": relative_l1,
            }
        )
    frame = pd.DataFrame(records)
    if frame.empty:
        raise ValueError(f"no external/base pairs for {split}")
    output: list[dict[str, Any]] = []
    groups: list[tuple[int | str, int | str, pd.DataFrame]] = [("all", "all", frame)]
    for step, group in frame.groupby("source_step"):
        groups.append((int(step), "all", group))
    for factor_count, group in frame.groupby("active_factor_count"):
        groups.append(("all", int(factor_count), group))
    metric_names = [
        "external_base_js_actual",
        "external_base_js_reconstructed",
        "external_base_js_preservation_absolute_error",
        "signed_delta_cosine_similarity",
        "signed_delta_relative_l1_error",
    ]
    for source_step, active_factor_count, group in groups:
        for weighting in ("weighted", "unweighted"):
            weights = (
                group["analysis_weight"].to_numpy(dtype=np.float64)
                if weighting == "weighted"
                else np.ones(len(group), dtype=np.float64)
            )
            for metric in metric_names:
                values = group[metric].to_numpy(dtype=np.float64)
                for aggregation in ("mean", "median", "p95", "max"):
                    output.append(
                        {
                            "run_id": run_id,
                            "method": method,
                            "rank": rank,
                            "split": split,
                            "source_step": source_step,
                            "active_factor_count": active_factor_count,
                            "weighting": weighting,
                            "metric": metric,
                            "aggregation": aggregation,
                            "value": _weighted_aggregate(values, weights, aggregation),
                            "pair_count": len(group),
                        }
                    )
    return output

def _all_pair_metrics(
    root: Path,
    runs: pd.DataFrame,
    fit: np.ndarray,
    fit_metadata: pd.DataFrame,
    validation: np.ndarray,
    validation_metadata: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, run in runs[runs["status"] == "completed"].iterrows():
        for split, actual, metadata in (
            ("fit", fit, fit_metadata),
            ("validation", validation, validation_metadata),
        ):
            raw, distribution = _reconstruction_for_run(root, run, split, len(actual))
            if distribution is None:
                row_sums = raw.sum(axis=1, keepdims=True)
                if np.any(row_sums <= 0.0):
                    raise ValueError(f"non-positive reconstruction mass for {run['run_id']}")
                distribution = raw / row_sums
            rows.extend(
                _pair_deformation_rows(
                    run_id=str(run["run_id"]),
                    method=str(run["method"]),
                    rank=int(run["rank"]),
                    split=split,
                    actual=actual,
                    reconstructed_distribution=distribution,
                    metadata=metadata,
                )
            )
    return pd.DataFrame(rows)

def _component_matches(root: Path, runs: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    primary = runs[(runs["method"] == PRIMARY) & (runs["status"] == "completed")]
    for rank, group in primary.groupby("rank"):
        records = list(group.to_dict("records"))
        for left, right in combinations(records, 2):
            basis_left = np.load(root / left["basis_path"], allow_pickle=False)
            basis_right = np.load(root / right["basis_path"], allow_pickle=False)
            for item in match_components(basis_left, basis_right):
                rows.append(
                    {
                        "rank": int(rank),
                        "run_id_a": left["run_id"],
                        "run_id_b": right["run_id"],
                        **item,
                    }
                )
    return pd.DataFrame(rows)
