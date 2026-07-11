from __future__ import annotations
import json, math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
from .contract import DEFAULT_CONTRACT, load_contract, sha256_file
from .models import fit_weighted_kl_nmf, fit_weighted_pca
PRIMARY="nmf_kl"
REQUIRED_EVALUATION_COLUMNS={"bundle_row_index","matrix_row_index","snapshot_id","dataset_split","distribution_group","source_run_id","external_vector_id","seed","source_step","active_factor_count","vector_origin","analysis_weight","matched_base_snapshot_id"}
def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _json_dump(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

def run_plan(contract: dict[str, Any], *, ranks: list[int] | None = None) -> list[dict[str, Any]]:
    frozen = [int(value) for value in contract["rank_grid"]]
    selected = frozen if ranks is None else [int(value) for value in ranks]
    if not selected or any(rank not in frozen for rank in selected) or len(set(selected)) != len(selected):
        raise ValueError("run-plan ranks must be unique values from the frozen rank grid")
    rows: list[dict[str, Any]] = []
    for rank in selected:
        rows.append(
            {
                "run_id": f"nmf_kl_rank{rank:02d}_anchor",
                "rank": rank,
                "run_role": "anchor",
                "init_method": contract["primary_model"]["anchor_initialization"],
                "init_seed": 0,
            }
        )
        for seed in contract["primary_model"]["random_seeds"]:
            rows.append(
                {
                    "run_id": f"nmf_kl_rank{rank:02d}_seed{int(seed)}",
                    "rank": rank,
                    "run_role": "random_init",
                    "init_method": contract["primary_model"]["random_initialization"],
                    "init_seed": int(seed),
                }
            )
    return rows

def formal_run_plan(contract_path: str | Path = DEFAULT_CONTRACT) -> list[dict[str, Any]]:
    return run_plan(load_contract(contract_path))

def weighted_quantile(values: np.ndarray, weights: np.ndarray, quantile: float) -> float:
    data = np.asarray(values, dtype=np.float64).reshape(-1)
    active_weights = np.asarray(weights, dtype=np.float64).reshape(-1)
    if data.shape != active_weights.shape or not len(data):
        raise ValueError("weighted quantile inputs are empty or misaligned")
    if not np.isfinite(data).all() or not np.isfinite(active_weights).all() or np.any(active_weights <= 0.0):
        raise ValueError("weighted quantile inputs must be finite with positive weights")
    order = np.argsort(data, kind="mergesort")
    sorted_data = data[order]
    sorted_weights = active_weights[order]
    threshold = float(quantile) * float(sorted_weights.sum(dtype=np.float64))
    index = min(int(np.searchsorted(np.cumsum(sorted_weights), threshold, side="left")), len(sorted_data) - 1)
    return float(sorted_data[index])

def validation_mean_js(metrics: pd.DataFrame, run_id: str) -> float:
    rows = metrics[
        (metrics["run_id"] == run_id)
        & (metrics["split"] == "validation")
        & (metrics["subgroup_type"] == "all")
        & (metrics["subgroup_value"].astype(str) == "all")
        & (metrics["weighting"] == "weighted")
        & (metrics["metric"] == "js_distance")
        & (metrics["aggregation"] == "mean")
    ]
    if len(rows) != 1:
        raise ValueError(f"missing unique validation mean JS for {run_id}")
    value = float(rows.iloc[0]["value"])
    if not math.isfinite(value):
        raise ValueError(f"validation mean JS is not finite for {run_id}")
    return value

def _load_evaluation_metadata(path: str | Path, row_map: pd.DataFrame, split: str) -> pd.DataFrame:
    metadata = pd.read_csv(path)
    missing = REQUIRED_EVALUATION_COLUMNS - set(metadata.columns)
    if missing:
        raise ValueError(f"evaluation metadata missing columns: {sorted(missing)}")
    metadata = metadata.sort_values("bundle_row_index").reset_index(drop=True)
    if len(metadata) != len(row_map):
        raise ValueError("evaluation metadata row count differs from row map")
    if set(metadata["dataset_split"].astype(str)) != {split}:
        raise ValueError(f"evaluation metadata must contain only {split} rows")
    for column in ("bundle_row_index", "matrix_row_index", "snapshot_id", "analysis_weight"):
        left = metadata[column].astype(str).tolist()
        right = row_map.sort_values("bundle_row_index")[column].astype(str).tolist()
        if left != right:
            raise ValueError(f"evaluation metadata and row map differ in {column}")
    return metadata

def _save_nmf_result(
    root: Path,
    relative_dir: str,
    *,
    run_id: str,
    method: str,
    rank: int,
    role: str,
    init_method: str,
    init_seed: int,
    solver: str,
    loss: str,
    result: Any,
    max_iter: int,
    tolerance: float,
    subset_id: str = "",
    world_seed_filter: str = "",
) -> dict[str, Any]:
    run_dir = root / relative_dir
    run_dir.mkdir(parents=True, exist_ok=False)
    basis_path = run_dir / "basis.npy"
    fit_path = run_dir / "fit_activations.npy"
    validation_path = run_dir / "validation_activations.npy"
    np.save(basis_path, np.asarray(result.basis, dtype=np.float64))
    np.save(fit_path, np.asarray(result.fit_activations, dtype=np.float64))
    np.save(validation_path, np.asarray(result.validation_activations, dtype=np.float64))
    metadata = {
        "run_id": run_id,
        "method": method,
        "rank": rank,
        "run_role": role,
        "init_method": init_method,
        "init_seed": init_seed,
        "solver": solver,
        "loss": loss,
        "max_iter": max_iter,
        "tolerance": tolerance,
        "n_iter": int(result.n_iter),
        "converged": bool(result.converged),
        "basis_sha256": sha256_file(basis_path),
        "fit_activation_sha256": sha256_file(fit_path),
        "validation_activation_sha256": sha256_file(validation_path),
    }
    _json_dump(run_dir / "run_metadata.json", metadata)
    return {
        **metadata,
        "subset_id": subset_id,
        "world_seed_filter": world_seed_filter,
        "status": "completed",
        "failure_reason": "",
        "fit_started_at": "",
        "fit_completed_at": _utc_now(),
        "basis_path": str(basis_path.relative_to(root)),
        "fit_activation_path": str(fit_path.relative_to(root)),
        "validation_activation_path": str(validation_path.relative_to(root)),
    }

def _failed_run(plan: dict[str, Any], max_iter: int, tolerance: float, error: Exception) -> dict[str, Any]:
    return {
        "run_id": plan["run_id"],
        "method": PRIMARY,
        "rank": int(plan["rank"]),
        "run_role": plan["run_role"],
        "init_method": plan["init_method"],
        "init_seed": int(plan["init_seed"]),
        "subset_id": "",
        "world_seed_filter": "",
        "solver": "mu",
        "loss": "kullback-leibler",
        "max_iter": max_iter,
        "tolerance": tolerance,
        "n_iter": -1,
        "converged": False,
        "status": "failed",
        "failure_reason": f"{type(error).__name__}: {error}",
        "fit_started_at": "",
        "fit_completed_at": _utc_now(),
        "basis_path": "",
        "fit_activation_path": "",
        "validation_activation_path": "",
        "basis_sha256": "",
        "fit_activation_sha256": "",
        "validation_activation_sha256": "",
    }

def _execute_primary_runs(
    root: Path,
    plans: list[dict[str, Any]],
    fit: np.ndarray,
    fit_weights: np.ndarray,
    validation: np.ndarray,
    contract: dict[str, Any],
    max_iter: int,
) -> list[dict[str, Any]]:
    tolerance = float(contract["primary_model"]["tolerance"])
    rows: list[dict[str, Any]] = []
    for plan in plans:
        try:
            result = fit_weighted_kl_nmf(
                fit,
                fit_weights,
                validation,
                rank=int(plan["rank"]),
                init_method=str(plan["init_method"]),
                init_seed=int(plan["init_seed"]),
                max_iter=max_iter,
                tolerance=tolerance,
            )
            rows.append(
                _save_nmf_result(
                    root,
                    f"models/{plan['run_id']}",
                    run_id=plan["run_id"],
                    method=PRIMARY,
                    rank=int(plan["rank"]),
                    role=plan["run_role"],
                    init_method=plan["init_method"],
                    init_seed=int(plan["init_seed"]),
                    solver="mu",
                    loss="kullback-leibler",
                    result=result,
                    max_iter=max_iter,
                    tolerance=tolerance,
                )
            )
        except Exception as exc:
            rows.append(_failed_run(plan, max_iter, tolerance, exc))
    return rows

def _reference_runs(
    root: Path,
    ranks: list[int],
    fit: np.ndarray,
    fit_weights: np.ndarray,
    validation: np.ndarray,
) -> list[dict[str, Any]]:
    references = root / "references"
    references.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    mean = np.average(fit, axis=0, weights=fit_weights)
    mean /= mean.sum(dtype=np.float64)
    mean_path = references / "mean_distribution.npy"
    np.save(mean_path, mean)
    rows.append(
        {
            "run_id": "mean_distribution_baseline",
            "method": "mean_baseline",
            "rank": 0,
            "run_role": "reference",
            "init_method": "none",
            "init_seed": 0,
            "subset_id": "",
            "world_seed_filter": "",
            "solver": "weighted_mean",
            "loss": "none",
            "max_iter": 0,
            "tolerance": 0.0,
            "n_iter": 0,
            "converged": True,
            "status": "completed",
            "failure_reason": "",
            "fit_started_at": "",
            "fit_completed_at": _utc_now(),
            "basis_path": str(mean_path.relative_to(root)),
            "fit_activation_path": "",
            "validation_activation_path": "",
            "basis_sha256": sha256_file(mean_path),
            "fit_activation_sha256": "",
            "validation_activation_sha256": "",
        }
    )
    for rank in ranks:
        pca = fit_weighted_pca(fit, fit_weights, validation, rank)
        run_dir = references / f"pca_rank_{rank:02d}"
        run_dir.mkdir(parents=True, exist_ok=False)
        arrays = {
            "weighted_mean": pca.weighted_mean,
            "components": pca.components,
            "fit_scores": pca.fit_scores,
            "validation_scores": pca.validation_scores,
            "explained_variance_ratio": pca.explained_variance_ratio,
        }
        for name, array in arrays.items():
            np.save(run_dir / f"{name}.npy", np.asarray(array, dtype=np.float64))
        rows.append(
            {
                "run_id": f"weighted_pca_rank{rank:02d}",
                "method": "weighted_pca",
                "rank": rank,
                "run_role": "reference",
                "init_method": "svd",
                "init_seed": 0,
                "subset_id": "",
                "world_seed_filter": "",
                "solver": "weighted_centered_svd",
                "loss": "frobenius",
                "max_iter": 0,
                "tolerance": 0.0,
                "n_iter": 1,
                "converged": True,
                "status": "completed",
                "failure_reason": "",
                "fit_started_at": "",
                "fit_completed_at": _utc_now(),
                "basis_path": str((run_dir / "components.npy").relative_to(root)),
                "fit_activation_path": str((run_dir / "fit_scores.npy").relative_to(root)),
                "validation_activation_path": str((run_dir / "validation_scores.npy").relative_to(root)),
                "basis_sha256": sha256_file(run_dir / "components.npy"),
                "fit_activation_sha256": sha256_file(run_dir / "fit_scores.npy"),
                "validation_activation_sha256": sha256_file(run_dir / "validation_scores.npy"),
            }
        )
    return rows
