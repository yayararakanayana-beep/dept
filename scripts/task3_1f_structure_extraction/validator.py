from __future__ import annotations

import argparse
import hashlib
import json
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

from .contract import DEFAULT_CONTRACT, canonical_contract_text, load_contract, sha256_file, sha256_text

METRIC_KEY_COLUMNS = [
    "run_id", "method", "rank", "split", "subgroup_type", "subgroup_value",
    "weighting", "metric", "aggregation",
]


class Recorder:
    def __init__(self) -> None:
        self.checks: dict[str, dict[str, Any]] = {}

    def add(self, name: str, passed: bool, **evidence: Any) -> None:
        self.checks[name] = {"passed": bool(passed), **_json_safe(evidence)}

    def guard(self, name: str, function) -> None:
        try:
            evidence = function()
            passed = bool(evidence.pop("passed"))
            self.add(name, passed, **evidence)
        except Exception as exc:
            self.add(name, False, error=f"{type(exc).__name__}: {exc}")

    @property
    def failed(self) -> list[str]:
        return [name for name, result in self.checks.items() if not result["passed"]]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def _load_bundle(bundle_path: Path, row_map_path: Path) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    with np.load(bundle_path, allow_pickle=False) as bundle:
        mass = np.asarray(bundle["mass_matrix"], dtype=np.float64)
        weights = np.asarray(bundle["analysis_weight"], dtype=np.float64)
        indices = np.asarray(bundle["matrix_row_index"], dtype=np.int64)
        hashes = np.asarray(bundle["snapshot_id_hash"])
    row_map = pd.read_csv(row_map_path)
    expected_hashes = np.asarray(
        [hashlib.sha256(str(value).encode("utf-8")).hexdigest().encode("ascii") for value in row_map["snapshot_id"]],
        dtype="S64",
    )
    if len(row_map) != len(mass) or weights.shape != (len(mass),):
        raise ValueError("bundle row counts differ")
    if not np.array_equal(indices, row_map["matrix_row_index"].to_numpy(dtype=np.int64)):
        raise ValueError("bundle indices differ from row map")
    if not np.array_equal(hashes, expected_hashes):
        raise ValueError("bundle snapshot hashes differ from row map")
    return mass, weights, row_map


def _weighted_quantile(values: np.ndarray, weights: np.ndarray, quantile: float) -> float:
    order = np.argsort(values, kind="mergesort")
    data = values[order]
    active_weights = weights[order]
    threshold = quantile * float(active_weights.sum())
    index = min(int(np.searchsorted(np.cumsum(active_weights), threshold, side="left")), len(data) - 1)
    return float(data[index])


def _aggregate(values: np.ndarray, weights: np.ndarray, aggregation: str, weighting: str) -> float:
    active = weights if weighting == "weighted" else np.ones(len(values), dtype=np.float64)
    if aggregation == "mean":
        return float(np.average(values, weights=active))
    if aggregation == "median":
        return _weighted_quantile(values, active, 0.5)
    if aggregation == "p95":
        return _weighted_quantile(values, active, 0.95)
    if aggregation == "max":
        return float(np.max(values))
    if aggregation == "sum":
        return float(np.sum(values))
    raise ValueError(f"unknown aggregation: {aggregation}")


def _project_simplex_rows(matrix: np.ndarray) -> np.ndarray:
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
        raise ValueError("metric matrices are invalid")
    raw_sums = raw.sum(axis=1, dtype=np.float64)
    if distribution is None:
        if np.any(raw_sums <= 0.0):
            raise ValueError("raw reconstruction contains non-positive row mass")
        dist = raw / raw_sums[:, None]
    else:
        dist = np.asarray(distribution, dtype=np.float64)
    if dist.shape != actual.shape or not np.isfinite(dist).all() or np.any(dist < 0.0):
        raise ValueError("distribution reconstruction is invalid")
    if np.max(np.abs(dist.sum(axis=1) - 1.0)) > 1e-10:
        raise ValueError("distribution reconstruction rows do not sum to one")
    epsilon = 1e-12
    p = np.maximum(actual, epsilon)
    p /= p.sum(axis=1, keepdims=True)
    q = np.maximum(dist, epsilon)
    q /= q.sum(axis=1, keepdims=True)
    midpoint = 0.5 * (p + q)
    divergence = 0.5 * np.sum(p * np.log(p / midpoint), axis=1)
    divergence += 0.5 * np.sum(q * np.log(q / midpoint), axis=1)
    return {
        "rmse_raw": np.sqrt(np.mean((actual - raw) ** 2, axis=1)),
        "mae_raw": np.mean(np.abs(actual - raw), axis=1),
        "js_distance": np.sqrt(np.maximum(divergence, 0.0)),
        "total_variation": 0.5 * np.sum(np.abs(actual - dist), axis=1),
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
        group_weights = weights[selector]
        for weighting in ("weighted", "unweighted"):
            for metric in ("rmse_raw", "mae_raw", "js_distance", "total_variation", "raw_row_sum_absolute_error"):
                values = measured[metric][selector]
                for aggregation in ("mean", "median", "p95", "max"):
                    rows.append({
                        "run_id": run.run_id, "method": run.method, "rank": int(run["rank"]),
                        "split": split, "subgroup_type": subgroup_type, "subgroup_value": subgroup_value,
                        "weighting": weighting, "metric": metric, "aggregation": aggregation,
                        "value": _aggregate(values, group_weights, aggregation, weighting),
                        "row_count": int(selector.sum()),
                        "weight_sum": float(group_weights.sum()) if weighting == "weighted" else int(selector.sum()),
                    })
            for metric in ("negative_value_count", "nonfinite_value_count"):
                rows.append({
                    "run_id": run.run_id, "method": run.method, "rank": int(run["rank"]),
                    "split": split, "subgroup_type": subgroup_type, "subgroup_value": subgroup_value,
                    "weighting": weighting, "metric": metric, "aggregation": "sum",
                    "value": float(np.sum(measured[metric][selector])),
                    "row_count": int(selector.sum()),
                    "weight_sum": float(group_weights.sum()) if weighting == "weighted" else int(selector.sum()),
                })
    return rows


def _component_matches(basis_a: np.ndarray, basis_b: np.ndarray) -> list[dict[str, Any]]:
    epsilon = 1e-12
    left = np.maximum(np.asarray(basis_a, dtype=np.float64), epsilon)
    right = np.maximum(np.asarray(basis_b, dtype=np.float64), epsilon)
    left /= left.sum(axis=1, keepdims=True)
    right /= right.sum(axis=1, keepdims=True)
    distances = np.empty((len(left), len(right)), dtype=np.float64)
    for index, row in enumerate(left):
        midpoint = 0.5 * (row[None, :] + right)
        divergence = 0.5 * np.sum(row[None, :] * np.log(row[None, :] / midpoint), axis=1)
        divergence += 0.5 * np.sum(right * np.log(right / midpoint), axis=1)
        distances[index] = np.sqrt(np.maximum(divergence, 0.0))
    row_indices, column_indices = linear_sum_assignment(distances)
    maximum = float(np.sqrt(np.log(2.0)))
    output = []
    for order, (row_index, column_index) in enumerate(zip(row_indices, column_indices), start=1):
        denominator = float(np.linalg.norm(left[row_index]) * np.linalg.norm(right[column_index]))
        output.append({
            "component_index_a": int(row_index),
            "component_index_b": int(column_index),
            "js_distance": float(distances[row_index, column_index]),
            "js_similarity": float(1.0 - distances[row_index, column_index] / maximum),
            "cosine_similarity": float(np.dot(left[row_index], right[column_index]) / denominator),
            "matching_cost_rank": order,
        })
    return output


def _compare_metric_frames(stored: pd.DataFrame, recomputed: pd.DataFrame) -> tuple[bool, float, list[str]]:
    sort_columns = METRIC_KEY_COLUMNS
    stored_sorted = stored.sort_values(sort_columns).reset_index(drop=True)
    recomputed_sorted = recomputed.sort_values(sort_columns).reset_index(drop=True)
    if len(stored_sorted) != len(recomputed_sorted):
        return False, float("inf"), [f"row_count {len(stored_sorted)} != {len(recomputed_sorted)}"]
    failures: list[str] = []
    for column in sort_columns + ["row_count"]:
        if stored_sorted[column].astype(str).tolist() != recomputed_sorted[column].astype(str).tolist():
            failures.append(f"column mismatch: {column}")
    max_error = 0.0
    for column in ("value", "weight_sum"):
        errors = np.abs(
            stored_sorted[column].to_numpy(dtype=np.float64) - recomputed_sorted[column].to_numpy(dtype=np.float64)
        )
        if len(errors):
            max_error = max(max_error, float(np.max(errors)))
        if not np.allclose(
            stored_sorted[column].to_numpy(dtype=np.float64),
            recomputed_sorted[column].to_numpy(dtype=np.float64),
            rtol=1e-9,
            atol=1e-12,
        ):
            failures.append(f"numeric mismatch: {column}")
    return not failures, max_error, failures


def _artifact_manifest(root: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "artifact_manifest.json":
            continue
        entry: dict[str, Any] = {
            "path": str(path.relative_to(root)),
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        if path.suffix == ".csv":
            frame = pd.read_csv(path)
            entry.update({"type": "csv", "row_count": len(frame), "columns": list(frame.columns)})
        elif path.suffix == ".npy":
            array = np.load(path, allow_pickle=False)
            entry.update({"type": "npy", "shape": list(array.shape), "dtype": str(array.dtype)})
        elif path.suffix == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            entry.update({"type": "json", "top_level_type": type(payload).__name__})
        else:
            entry.update({"type": "other"})
        files.append(entry)
    return {"artifact_root": root.name, "files": files}


def validate_smoke(
    artifact_dir: str | Path,
    fit_bundle: str | Path,
    fit_row_map: str | Path,
    validation_bundle: str | Path,
    validation_row_map: str | Path,
    contract_path: str | Path = DEFAULT_CONTRACT,
    *,
    write_outputs: bool = True,
) -> dict[str, dict[str, Any]]:
    root = Path(artifact_dir)
    contract = load_contract(contract_path)
    recorder = Recorder()
    required = [
        "model_runs.csv", "reconstruction_metrics.csv", "component_matches.csv",
        "contract_snapshot.json", "environment_manifest.json", "smoke_stage_manifest.json",
        "references/mean_distribution.npy", "references/pca_rank_5/weighted_mean.npy",
        "references/pca_rank_5/components.npy", "references/pca_rank_5/fit_scores.npy",
        "references/pca_rank_5/validation_scores.npy",
    ]
    missing = [name for name in required if not (root / name).is_file()]
    recorder.add("required_files_present", not missing, measured_value=len(required) - len(missing), threshold=len(required), checked_count=len(required), evidence_paths=missing)
    if missing:
        if write_outputs:
            (root / "quality_checks.json").write_text(json.dumps(recorder.checks, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return recorder.checks

    fit, fit_weights, fit_map = _load_bundle(Path(fit_bundle), Path(fit_row_map))
    validation, validation_weights, validation_map = _load_bundle(Path(validation_bundle), Path(validation_row_map))
    runs = pd.read_csv(root / "model_runs.csv")
    stored_metrics = pd.read_csv(root / "reconstruction_metrics.csv")
    stored_matches = pd.read_csv(root / "component_matches.csv")
    stage = json.loads((root / "smoke_stage_manifest.json").read_text(encoding="utf-8"))
    snapshot = json.loads((root / "contract_snapshot.json").read_text(encoding="utf-8"))

    recorder.add(
        "contract_snapshot_valid",
        snapshot == contract and stage.get("contract_sha256") == sha256_text(canonical_contract_text(contract_path)),
        measured_value=stage.get("contract_sha256"),
        threshold=sha256_text(canonical_contract_text(contract_path)),
        checked_count=1,
        evidence_paths=["contract_snapshot.json", "smoke_stage_manifest.json"],
    )
    holdout_clean = (
        stage.get("holdout_accessed") is False
        and stage.get("selection_lock_created") is False
        and not (root / "selection_lock.json").exists()
        and not any("holdout" in str(path.relative_to(root)).lower() for path in root.rglob("*") if path.is_file())
    )
    recorder.add("holdout_isolation_valid", holdout_clean, measured_value=stage.get("holdout_accessed"), threshold=False, checked_count=1, evidence_paths=["smoke_stage_manifest.json"])

    expected_nmf_ids = ["nmf_kl_rank05_anchor"] + [f"nmf_kl_rank05_seed{seed}" for seed in contract["primary_model"]["random_seeds"]]
    actual_nmf_ids = runs.loc[runs["method"] == "nmf_kl", "run_id"].tolist()
    recorder.add(
        "model_run_completeness",
        actual_nmf_ids == expected_nmf_ids and set(runs["method"]) == {"nmf_kl", "weighted_pca", "mean_baseline"},
        measured_value={"nmf_ids": actual_nmf_ids, "methods": sorted(set(runs["method"]))},
        threshold={"nmf_ids": expected_nmf_ids, "methods": ["mean_baseline", "nmf_kl", "weighted_pca"]},
        checked_count=len(runs),
        evidence_paths=["model_runs.csv"],
    )

    recomputed_rows: list[dict[str, Any]] = []
    basis_by_run: dict[str, np.ndarray] = {}
    invalid_models: list[str] = []
    hash_failures: list[str] = []
    for _, run in runs.iterrows():
        basis_path = root / str(run["basis_path"])
        if not basis_path.is_file() or sha256_file(basis_path) != str(run["basis_sha256"]):
            hash_failures.append(str(run["run_id"]))
            continue
        if run["method"] == "nmf_kl":
            basis = np.load(basis_path, allow_pickle=False)
            fit_path = root / str(run["fit_activation_path"])
            validation_path = root / str(run["validation_activation_path"])
            if sha256_file(fit_path) != str(run["fit_activation_sha256"]) or sha256_file(validation_path) != str(run["validation_activation_sha256"]):
                hash_failures.append(str(run["run_id"]))
                continue
            fit_activation = np.load(fit_path, allow_pickle=False)
            validation_activation = np.load(validation_path, allow_pickle=False)
            valid = (
                basis.shape == (5, fit.shape[1])
                and fit_activation.shape == (len(fit), 5)
                and validation_activation.shape == (len(validation), 5)
                and np.isfinite(basis).all() and np.isfinite(fit_activation).all() and np.isfinite(validation_activation).all()
                and np.all(basis >= 0.0) and np.all(fit_activation >= 0.0) and np.all(validation_activation >= 0.0)
                and np.max(np.abs(basis.sum(axis=1) - 1.0)) <= 1e-10
            )
            if not valid:
                invalid_models.append(str(run["run_id"]))
                continue
            basis_by_run[str(run["run_id"])] = basis
            recomputed_rows.extend(_metric_rows(run, "fit", fit, fit_activation @ basis, fit_weights, fit_map))
            recomputed_rows.extend(_metric_rows(run, "validation", validation, validation_activation @ basis, validation_weights, validation_map))
        elif run["method"] == "mean_baseline":
            mean = np.load(basis_path, allow_pickle=False)
            if mean.shape != (fit.shape[1],) or not np.isfinite(mean).all() or np.any(mean < 0.0) or abs(float(mean.sum()) - 1.0) > 1e-10:
                invalid_models.append(str(run["run_id"]))
                continue
            recomputed_rows.extend(_metric_rows(run, "fit", fit, np.repeat(mean[None, :], len(fit), axis=0), fit_weights, fit_map))
            recomputed_rows.extend(_metric_rows(run, "validation", validation, np.repeat(mean[None, :], len(validation), axis=0), validation_weights, validation_map))
        elif run["method"] == "weighted_pca":
            mean = np.load(root / "references/pca_rank_5/weighted_mean.npy", allow_pickle=False)
            components = np.load(basis_path, allow_pickle=False)
            fit_scores = np.load(root / str(run["fit_activation_path"]), allow_pickle=False)
            validation_scores = np.load(root / str(run["validation_activation_path"]), allow_pickle=False)
            if components.shape != (5, fit.shape[1]) or mean.shape != (fit.shape[1],):
                invalid_models.append(str(run["run_id"]))
                continue
            for split, actual, weights, row_map, scores in (
                ("fit", fit, fit_weights, fit_map, fit_scores),
                ("validation", validation, validation_weights, validation_map, validation_scores),
            ):
                raw = mean[None, :] + scores @ components
                projected = _project_simplex_rows(raw)
                recomputed_rows.extend(_metric_rows(run, split, actual, raw, weights, row_map, projected))

    recorder.add("model_hashes_valid", not hash_failures, measured_value=hash_failures, threshold=[], checked_count=len(runs), evidence_paths=["model_runs.csv", "models/", "references/"])
    recorder.add("basis_and_activations_valid", not invalid_models, measured_value=invalid_models, threshold=[], checked_count=len(runs), evidence_paths=["models/", "references/"])

    recomputed_metrics = pd.DataFrame(recomputed_rows)
    metric_ok, max_error, metric_failures = _compare_metric_frames(stored_metrics, recomputed_metrics)
    recorder.add("reconstruction_metrics_recomputed", metric_ok, measured_value=max_error, threshold=1e-9, checked_count=len(stored_metrics), evidence_paths=["reconstruction_metrics.csv", "models/", "references/"], failures=metric_failures)

    expected_matches: list[dict[str, Any]] = []
    nmf_ids = expected_nmf_ids
    for left_id, right_id in combinations(nmf_ids, 2):
        if left_id not in basis_by_run or right_id not in basis_by_run:
            continue
        for item in _component_matches(basis_by_run[left_id], basis_by_run[right_id]):
            expected_matches.append({"rank": 5, "run_id_a": left_id, "run_id_b": right_id, **item})
    expected_frame = pd.DataFrame(expected_matches).sort_values(["run_id_a", "run_id_b", "component_index_a"]).reset_index(drop=True)
    stored_frame = stored_matches.sort_values(["run_id_a", "run_id_b", "component_index_a"]).reset_index(drop=True)
    match_ok = len(expected_frame) == len(stored_frame)
    max_match_error = 0.0
    if match_ok:
        for column in ("rank", "run_id_a", "run_id_b", "component_index_a", "component_index_b", "matching_cost_rank"):
            match_ok = match_ok and expected_frame[column].astype(str).tolist() == stored_frame[column].astype(str).tolist()
        for column in ("js_distance", "js_similarity", "cosine_similarity"):
            error = np.abs(expected_frame[column].to_numpy(float) - stored_frame[column].to_numpy(float))
            max_match_error = max(max_match_error, float(np.max(error, initial=0.0)))
            match_ok = match_ok and np.allclose(expected_frame[column], stored_frame[column], rtol=1e-9, atol=1e-12)
    recorder.add("component_matching_recomputed", match_ok, measured_value=max_match_error, threshold=1e-9, checked_count=len(stored_frame), evidence_paths=["component_matches.csv", "models/*/basis.npy"])

    if write_outputs:
        quality_path = root / "quality_checks.json"
        quality_path.write_text(json.dumps(recorder.checks, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (root / "artifact_manifest.json").write_text(json.dumps(_artifact_manifest(root), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        results = [
            "# Task 3.1f-2 Smoke Results", "",
            f"- Result: `{'PASS' if not recorder.failed else 'FAIL'}`",
            f"- Checks: `{len(recorder.checks) - len(recorder.failed)} / {len(recorder.checks)}`",
            f"- NMF runs: `{len(actual_nmf_ids)}`",
            "- Rank: `5`", "- Holdout accessed: `false`", "",
            "This is a minimal implementation smoke test. It does not select a formal rank and does not create a selection lock.", "",
        ]
        if recorder.failed:
            results.extend(["## Failed checks", ""] + [f"- `{name}`" for name in recorder.failed])
        (root / "results.md").write_text("\n".join(results) + "\n", encoding="utf-8")
    return recorder.checks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--fit-bundle", required=True)
    parser.add_argument("--fit-row-map", required=True)
    parser.add_argument("--validation-bundle", required=True)
    parser.add_argument("--validation-row-map", required=True)
    parser.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    checks = validate_smoke(
        args.artifact_dir,
        args.fit_bundle,
        args.fit_row_map,
        args.validation_bundle,
        args.validation_row_map,
        args.contract,
        write_outputs=True,
    )
    failed = [name for name, result in checks.items() if not result["passed"]]
    print(json.dumps({"failed_checks": failed, "check_count": len(checks)}, indent=2))
    if failed and args.strict:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
