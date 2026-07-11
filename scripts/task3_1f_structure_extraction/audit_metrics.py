from __future__ import annotations
import hashlib,json
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
PRIMARY="nmf_kl"
METRIC_KEY_COLUMNS=["run_id","method","rank","split","subgroup_type","subgroup_value","weighting","metric","aggregation"]
class Recorder:
    def __init__(self) -> None:
        self.checks: dict[str, dict[str, Any]] = {}

    def add(self, name: str, passed: bool, **evidence: Any) -> None:
        self.checks[name] = {"passed": bool(passed), **_json_safe(evidence)}

    @property
    def failed(self) -> list[str]:
        return [name for name, value in self.checks.items() if not value["passed"]]

def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value

def _json_dump(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(_json_safe(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")

def _load_bundle(root: Path, split: str) -> tuple[np.ndarray, np.ndarray, pd.DataFrame, pd.DataFrame]:
    evidence = root / "evidence"
    bundle_path = evidence / f"{split}_bundle.npz"
    row_map_path = evidence / f"{split}_row_map.csv"
    metadata_path = evidence / f"{split}_evaluation_metadata.csv"
    with np.load(bundle_path, allow_pickle=False) as bundle:
        mass = np.asarray(bundle["mass_matrix"], dtype=np.float64)
        weights = np.asarray(bundle["analysis_weight"], dtype=np.float64)
        indices = np.asarray(bundle["matrix_row_index"], dtype=np.int64)
        hashes = np.asarray(bundle["snapshot_id_hash"])
    row_map = pd.read_csv(row_map_path).sort_values("bundle_row_index").reset_index(drop=True)
    metadata = pd.read_csv(metadata_path).sort_values("bundle_row_index").reset_index(drop=True)
    expected_hashes = np.asarray(
        [hashlib.sha256(str(value).encode("utf-8")).hexdigest().encode("ascii") for value in row_map["snapshot_id"]],
        dtype="S64",
    )
    if len(row_map) != len(mass) or len(metadata) != len(mass):
        raise ValueError(f"{split} evidence row counts differ")
    if not np.array_equal(indices, row_map["matrix_row_index"].to_numpy(dtype=np.int64)):
        raise ValueError(f"{split} bundle indices differ")
    if not np.array_equal(hashes, expected_hashes):
        raise ValueError(f"{split} snapshot hashes differ")
    for column in ("bundle_row_index", "matrix_row_index", "snapshot_id", "analysis_weight"):
        if metadata[column].astype(str).tolist() != row_map[column].astype(str).tolist():
            raise ValueError(f"{split} evaluation metadata differs in {column}")
    return mass, weights, row_map, metadata

def _weighted_quantile(values: np.ndarray, weights: np.ndarray, quantile: float) -> float:
    data = np.asarray(values, dtype=np.float64).reshape(-1)
    active_weights = np.asarray(weights, dtype=np.float64).reshape(-1)
    if data.shape != active_weights.shape or not len(data):
        raise ValueError("weighted quantile inputs differ")
    order = np.argsort(data, kind="mergesort")
    data = data[order]
    active_weights = active_weights[order]
    threshold = quantile * float(active_weights.sum(dtype=np.float64))
    index = min(int(np.searchsorted(np.cumsum(active_weights), threshold, side="left")), len(data) - 1)
    return float(data[index])

def _aggregate(values: np.ndarray, weights: np.ndarray, aggregation: str, weighting: str) -> float:
    active_weights = weights if weighting == "weighted" else np.ones(len(values), dtype=np.float64)
    if aggregation == "mean":
        return float(np.average(values, weights=active_weights))
    if aggregation == "median":
        return _weighted_quantile(values, active_weights, 0.5)
    if aggregation == "p95":
        return _weighted_quantile(values, active_weights, 0.95)
    if aggregation == "max":
        return float(np.max(values))
    if aggregation == "sum":
        return float(np.sum(values))
    raise ValueError(aggregation)

def _simplex_projection(matrix: np.ndarray) -> np.ndarray:
    values = np.asarray(matrix, dtype=np.float64)
    output = np.empty_like(values)
    for row_index, row in enumerate(values):
        sorted_row = np.sort(row)[::-1]
        cumulative = np.cumsum(sorted_row) - 1.0
        candidates = np.nonzero(sorted_row - cumulative / np.arange(1, len(row) + 1) > 0.0)[0]
        rho = int(candidates[-1])
        theta = cumulative[rho] / float(rho + 1)
        output[row_index] = np.maximum(row - theta, 0.0)
    return output

def _row_metrics(actual: np.ndarray, raw: np.ndarray, distribution: np.ndarray | None = None) -> dict[str, np.ndarray]:
    if actual.shape != raw.shape or not np.isfinite(actual).all() or not np.isfinite(raw).all():
        raise ValueError("invalid reconstruction arrays")
    raw_sums = raw.sum(axis=1, dtype=np.float64)
    if distribution is None:
        if np.any(raw_sums <= 0.0):
            raise ValueError("non-positive reconstruction mass")
        distribution = raw / raw_sums[:, None]
    distribution = np.asarray(distribution, dtype=np.float64)
    if distribution.shape != actual.shape or not np.isfinite(distribution).all() or np.any(distribution < 0.0):
        raise ValueError("invalid distribution reconstruction")
    if np.max(np.abs(distribution.sum(axis=1) - 1.0)) > 1e-10:
        raise ValueError("distribution reconstruction does not sum to one")
    epsilon = 1e-12
    p = np.maximum(actual, epsilon)
    q = np.maximum(distribution, epsilon)
    p /= p.sum(axis=1, keepdims=True)
    q /= q.sum(axis=1, keepdims=True)
    midpoint = 0.5 * (p + q)
    divergence = 0.5 * np.sum(p * np.log(p / midpoint), axis=1)
    divergence += 0.5 * np.sum(q * np.log(q / midpoint), axis=1)
    return {
        "rmse_raw": np.sqrt(np.mean((actual - raw) ** 2, axis=1)),
        "mae_raw": np.mean(np.abs(actual - raw), axis=1),
        "js_distance": np.sqrt(np.maximum(divergence, 0.0)),
        "total_variation": 0.5 * np.sum(np.abs(actual - distribution), axis=1),
        "raw_row_sum_absolute_error": np.abs(raw_sums - 1.0),
        "negative_value_count": np.sum(raw < 0.0, axis=1).astype(np.float64),
        "nonfinite_value_count": np.sum(~np.isfinite(raw), axis=1).astype(np.float64),
    }

def _metric_rows(
    run: pd.Series,
    split: str,
    actual: np.ndarray,
    raw: np.ndarray,
    weights: np.ndarray,
    row_map: pd.DataFrame,
    distribution: np.ndarray | None = None,
) -> list[dict[str, Any]]:
    measured = _row_metrics(actual, raw, distribution)
    groups: list[tuple[str, str, np.ndarray]] = [("all", "all", np.ones(len(row_map), dtype=bool))]
    for column in ("distribution_group", "source_step", "active_factor_count", "vector_origin"):
        for value in sorted(row_map[column].drop_duplicates().tolist(), key=str):
            groups.append((column, str(value), row_map[column].astype(str).to_numpy() == str(value)))
    rows: list[dict[str, Any]] = []
    for subgroup_type, subgroup_value, selector in groups:
        selected_weights = weights[selector]
        for weighting in ("weighted", "unweighted"):
            for metric in ("rmse_raw", "mae_raw", "js_distance", "total_variation", "raw_row_sum_absolute_error"):
                values = measured[metric][selector]
                for aggregation in ("mean", "median", "p95", "max"):
                    rows.append({"run_id": str(run["run_id"]), "method": str(run["method"]), "rank": int(run["rank"]), "split": split, "subgroup_type": subgroup_type, "subgroup_value": subgroup_value, "weighting": weighting, "metric": metric, "aggregation": aggregation, "value": _aggregate(values, selected_weights, aggregation, weighting), "row_count": int(selector.sum()), "weight_sum": float(selected_weights.sum()) if weighting == "weighted" else int(selector.sum())})
            for metric in ("negative_value_count", "nonfinite_value_count"):
                rows.append({"run_id": str(run["run_id"]), "method": str(run["method"]), "rank": int(run["rank"]), "split": split, "subgroup_type": subgroup_type, "subgroup_value": subgroup_value, "weighting": weighting, "metric": metric, "aggregation": "sum", "value": float(np.sum(measured[metric][selector])), "row_count": int(selector.sum()), "weight_sum": float(selected_weights.sum()) if weighting == "weighted" else int(selector.sum())})
    return rows

def _reconstruction(root: Path, run: pd.Series, split: str, row_count: int) -> tuple[np.ndarray, np.ndarray | None]:
    method = str(run["method"])
    if method == PRIMARY:
        basis = np.load(root / str(run["basis_path"]), allow_pickle=False)
        activation_key = "fit_activation_path" if split == "fit" else "validation_activation_path"
        activations = np.load(root / str(run[activation_key]), allow_pickle=False)
        return activations @ basis, None
    if method == "mean_baseline":
        mean = np.load(root / str(run["basis_path"]), allow_pickle=False)
        return np.repeat(mean[None, :], row_count, axis=0), None
    if method == "weighted_pca":
        component_path = root / str(run["basis_path"])
        mean = np.load(component_path.parent / "weighted_mean.npy", allow_pickle=False)
        activation_key = "fit_activation_path" if split == "fit" else "validation_activation_path"
        scores = np.load(root / str(run[activation_key]), allow_pickle=False)
        raw = mean[None, :] + scores @ np.load(component_path, allow_pickle=False)
        return raw, _simplex_projection(raw)
    raise ValueError(method)

def _recompute_metrics(root: Path, runs: pd.DataFrame, fit: np.ndarray, fit_weights: np.ndarray, fit_map: pd.DataFrame, validation: np.ndarray, validation_weights: np.ndarray, validation_map: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, run in runs[runs["status"] == "completed"].iterrows():
        for split, actual, weights, row_map in (("fit", fit, fit_weights, fit_map), ("validation", validation, validation_weights, validation_map)):
            raw, distribution = _reconstruction(root, run, split, len(actual))
            rows.extend(_metric_rows(run, split, actual, raw, weights, row_map, distribution))
    return pd.DataFrame(rows)

def _compare_metric_frames(stored: pd.DataFrame, recomputed: pd.DataFrame) -> tuple[bool, float, list[str]]:
    stored = stored.copy(); recomputed = recomputed.copy()
    stored["subgroup_value"] = stored["subgroup_value"].astype(str); recomputed["subgroup_value"] = recomputed["subgroup_value"].astype(str)
    stored = stored.sort_values(METRIC_KEY_COLUMNS).reset_index(drop=True); recomputed = recomputed.sort_values(METRIC_KEY_COLUMNS).reset_index(drop=True)
    failures: list[str] = []
    if len(stored) != len(recomputed): return False, float("inf"), [f"row count {len(stored)} != {len(recomputed)}"]
    for column in METRIC_KEY_COLUMNS + ["row_count"]:
        if stored[column].astype(str).tolist() != recomputed[column].astype(str).tolist(): failures.append(f"column mismatch: {column}")
    maximum_error = 0.0
    for column in ("value", "weight_sum"):
        left = stored[column].to_numpy(dtype=np.float64); right = recomputed[column].to_numpy(dtype=np.float64)
        maximum_error = max(maximum_error, float(np.max(np.abs(left - right), initial=0.0)))
        if not np.allclose(left, right, rtol=1e-9, atol=1e-12): failures.append(f"numeric mismatch: {column}")
    return not failures, maximum_error, failures

def _sqrt_js_rows(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    epsilon = 1e-12
    p = np.maximum(np.asarray(left, dtype=np.float64), epsilon); q = np.maximum(np.asarray(right, dtype=np.float64), epsilon)
    p /= p.sum(axis=1, keepdims=True); q /= q.sum(axis=1, keepdims=True)
    midpoint = 0.5 * (p + q)
    divergence = 0.5 * np.sum(p * np.log(p / midpoint), axis=1); divergence += 0.5 * np.sum(q * np.log(q / midpoint), axis=1)
    return np.sqrt(np.maximum(divergence, 0.0))

def _pair_rows_for_run(run: pd.Series, split: str, actual: np.ndarray, reconstructed: np.ndarray, metadata: pd.DataFrame) -> list[dict[str, Any]]:
    row_sums = reconstructed.sum(axis=1, keepdims=True)
    if np.any(row_sums <= 0.0): raise ValueError("pair reconstruction has non-positive mass")
    distribution = reconstructed / row_sums
    index = {str(row.snapshot_id): int(row.bundle_row_index) for row in metadata.itertuples(index=False)}
    records: list[dict[str, Any]] = []
    external_rows = metadata[metadata["distribution_group"] == "external_augmented"]
    for row in external_rows.itertuples(index=False):
        external_index = int(row.bundle_row_index); base_id = str(row.matched_base_snapshot_id)
        if base_id not in index: raise ValueError("matched base snapshot is absent")
        base_index = index[base_id]; base = metadata.iloc[base_index]
        if str(base["distribution_group"]) != "base_v3_3" or str(base["dataset_split"]) != split or int(base["seed"]) != int(row.seed) or int(base["source_step"]) != int(row.source_step): raise ValueError("mismatched external/base pair")
        actual_external = actual[external_index : external_index + 1]; actual_base = actual[base_index : base_index + 1]
        reconstructed_external = distribution[external_index : external_index + 1]; reconstructed_base = distribution[base_index : base_index + 1]
        actual_js = float(_sqrt_js_rows(actual_external, actual_base)[0]); reconstructed_js = float(_sqrt_js_rows(reconstructed_external, reconstructed_base)[0])
        actual_delta = actual_external[0] - actual_base[0]; reconstructed_delta = reconstructed_external[0] - reconstructed_base[0]
        denominator = float(np.linalg.norm(actual_delta) * np.linalg.norm(reconstructed_delta)); cosine = float(np.dot(actual_delta, reconstructed_delta) / denominator) if denominator > 0.0 else 1.0
        relative_l1 = float(np.sum(np.abs(actual_delta - reconstructed_delta)) / max(np.sum(np.abs(actual_delta)), 1e-12))
        records.append({"source_step": int(row.source_step), "active_factor_count": int(row.active_factor_count), "analysis_weight": float(row.analysis_weight), "external_base_js_actual": actual_js, "external_base_js_reconstructed": reconstructed_js, "external_base_js_preservation_absolute_error": abs(actual_js - reconstructed_js), "signed_delta_cosine_similarity": cosine, "signed_delta_relative_l1_error": relative_l1})
    frame = pd.DataFrame(records)
    if frame.empty: raise ValueError("no external/base pairs")
    groups: list[tuple[int | str, int | str, pd.DataFrame]] = [("all", "all", frame)]
    for step, group in frame.groupby("source_step"): groups.append((int(step), "all", group))
    for factor_count, group in frame.groupby("active_factor_count"): groups.append(("all", int(factor_count), group))
    output: list[dict[str, Any]] = []
    for source_step, active_factor_count, group in groups:
        for weighting in ("weighted", "unweighted"):
            weights = group["analysis_weight"].to_numpy(dtype=np.float64) if weighting == "weighted" else np.ones(len(group), dtype=np.float64)
            for metric in ("external_base_js_actual", "external_base_js_reconstructed", "external_base_js_preservation_absolute_error", "signed_delta_cosine_similarity", "signed_delta_relative_l1_error"):
                values = group[metric].to_numpy(dtype=np.float64)
                for aggregation in ("mean", "median", "p95", "max"):
                    output.append({"run_id": str(run["run_id"]), "method": str(run["method"]), "rank": int(run["rank"]), "split": split, "source_step": source_step, "active_factor_count": active_factor_count, "weighting": weighting, "metric": metric, "aggregation": aggregation, "value": _aggregate(values, weights, aggregation, "weighted"), "pair_count": len(group)})
    return output

def _recompute_pair_metrics(root: Path, runs: pd.DataFrame, fit: np.ndarray, fit_metadata: pd.DataFrame, validation: np.ndarray, validation_metadata: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, run in runs[runs["status"] == "completed"].iterrows():
        for split, actual, metadata in (("fit", fit, fit_metadata), ("validation", validation, validation_metadata)):
            raw, distribution = _reconstruction(root, run, split, len(actual)); reconstructed = distribution if distribution is not None else raw
            rows.extend(_pair_rows_for_run(run, split, actual, reconstructed, metadata))
    return pd.DataFrame(rows)

def _compare_pair_frames(stored: pd.DataFrame, recomputed: pd.DataFrame) -> tuple[bool, float, list[str]]:
    keys = ["run_id", "method", "rank", "split", "source_step", "active_factor_count", "weighting", "metric", "aggregation"]
    stored = stored.copy(); recomputed = recomputed.copy()
    for column in ("source_step", "active_factor_count"):
        stored[column] = stored[column].astype(str); recomputed[column] = recomputed[column].astype(str)
    stored = stored.sort_values(keys).reset_index(drop=True); recomputed = recomputed.sort_values(keys).reset_index(drop=True)
    failures: list[str] = []
    if len(stored) != len(recomputed): return False, float("inf"), ["row_count"]
    for column in keys + ["pair_count"]:
        if stored[column].astype(str).tolist() != recomputed[column].astype(str).tolist(): failures.append(column)
    left = stored["value"].to_numpy(dtype=np.float64); right = recomputed["value"].to_numpy(dtype=np.float64)
    maximum = float(np.max(np.abs(left - right), initial=0.0))
    if not np.allclose(left, right, rtol=1e-9, atol=1e-12): failures.append("value")
    return not failures, maximum, failures
