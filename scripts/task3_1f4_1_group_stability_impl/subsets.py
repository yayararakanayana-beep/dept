from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.decomposition import NMF, non_negative_factorization

from .common import TARGET_RANKS, _json_dump, sha256_file
from .matching import _normalize_basis, _sqrt_js_distance


def _grouped_subsets(fit_map: pd.DataFrame, stage_contract: dict[str, Any]) -> list[dict[str, Any]]:
    config = stage_contract["matching_and_stability"]["grouped_subset"]
    required = {"distribution_group", "external_vector_id", "source_run_id", "active_factor_count", "vector_origin"}
    if not required.issubset(fit_map.columns):
        raise ValueError(f"fit map missing subset columns: {sorted(required - set(fit_map.columns))}")
    group_rows: list[dict[str, Any]] = []
    for row_index, row in fit_map.reset_index(drop=True).iterrows():
        if str(row["distribution_group"]) == "external_augmented":
            group_key = f"external|{int(row['active_factor_count'])}|{row['vector_origin']}|{row['external_vector_id']}"
            stratum = f"{int(row['active_factor_count'])}|{row['vector_origin']}"
        else:
            group_key = f"base|{row['source_run_id']}"
            stratum = "base"
        group_rows.append({"row_index": row_index, "group_key": group_key, "stratum": stratum})
    groups = pd.DataFrame(group_rows).groupby(["stratum", "group_key"])["row_index"].apply(list).reset_index()
    definitions: list[dict[str, Any]] = []
    for salt in config["salts"]:
        included: list[int] = []
        included_groups: list[str] = []
        excluded_groups: list[str] = []
        for group in groups.itertuples(index=False):
            value = int(hashlib.sha256(f"{salt}|{group.stratum}|{group.group_key}".encode()).hexdigest(), 16) / 2**256
            if value < float(config["fit_fraction"]):
                included.extend(int(index) for index in group.row_index)
                included_groups.append(str(group.group_key))
            else:
                excluded_groups.append(str(group.group_key))
        included = sorted(included)
        membership = set(included)
        preserving = all(
            all(int(index) in membership for index in group.row_index)
            or all(int(index) not in membership for index in group.row_index)
            for group in groups.itertuples(index=False)
        )
        definitions.append(
            {
                "subset_id": str(salt),
                "included_row_indices": included,
                "included_group_keys": included_groups,
                "excluded_group_keys": excluded_groups,
                "included_fraction": len(included) / len(fit_map),
                "group_preserving": bool(preserving),
            }
        )
    return definitions


def _fit_weighted_kl_nmf(
    fit: np.ndarray,
    fit_weights: np.ndarray,
    validation: np.ndarray,
    *,
    rank: int,
    max_iter: int,
    tolerance: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, int, bool]:
    row_scale = np.asarray(fit_weights, dtype=np.float64)
    weighted_fit = fit * row_scale[:, None]
    model = NMF(
        n_components=rank,
        init="nndsvda",
        solver="mu",
        beta_loss="kullback-leibler",
        tol=tolerance,
        max_iter=max_iter,
        random_state=None,
        alpha_W=0.0,
        alpha_H=0.0,
        l1_ratio=0.0,
        shuffle=False,
    )
    weighted_activations = model.fit_transform(weighted_fit)
    basis = np.asarray(model.components_, dtype=np.float64)
    sums = basis.sum(axis=1, dtype=np.float64)
    if np.any(sums <= 0.0):
        raise ValueError("subset model contains zero-mass basis rows")
    basis /= sums[:, None]
    weighted_activations *= sums[None, :]
    fit_activations = weighted_activations / row_scale[:, None]
    validation_activations, returned_basis, _ = non_negative_factorization(
        validation,
        H=basis.copy(),
        n_components=rank,
        init="custom",
        update_H=False,
        solver="mu",
        beta_loss="kullback-leibler",
        tol=tolerance,
        max_iter=max_iter,
        alpha_W=0.0,
        alpha_H=0.0,
        l1_ratio=0.0,
        random_state=0,
        shuffle=False,
    )
    if not np.allclose(returned_basis, basis, rtol=0.0, atol=0.0):
        raise ValueError("fixed validation transform modified subset basis")
    return basis, fit_activations, validation_activations, int(model.n_iter_), bool(model.n_iter_ < max_iter)


def _weighted_mean_js(actual: np.ndarray, activations: np.ndarray, basis: np.ndarray, weights: np.ndarray) -> float:
    reconstructed = np.asarray(activations, dtype=np.float64) @ np.asarray(basis, dtype=np.float64)
    reconstructed = np.maximum(reconstructed, 0.0)
    reconstructed /= reconstructed.sum(axis=1, keepdims=True)
    distances = np.asarray([_sqrt_js_distance(a, b) for a, b in zip(actual, reconstructed)], dtype=np.float64)
    return float(np.average(distances, weights=weights))


def _copy_or_fit_subset_models(
    *,
    source_root: Path,
    output_root: Path,
    fit: np.ndarray,
    fit_weights: np.ndarray,
    fit_map: pd.DataFrame,
    validation: np.ndarray,
    rank_representatives: dict[int, dict[str, Any]],
    stage_contract: dict[str, Any],
    task_contract: dict[str, Any],
    profile: str,
) -> tuple[pd.DataFrame, dict[tuple[int, str], dict[str, Any]]]:
    definitions = _grouped_subsets(fit_map, stage_contract)
    model_records: dict[tuple[int, str], dict[str, Any]] = {}
    diagnostics: list[dict[str, Any]] = []
    max_iter = int(stage_contract["primary_model"]["max_iter"])
    if profile == "smoke":
        max_iter = min(max_iter, int(task_contract["execution"]["smoke_max_iter"]))
    tolerance = float(stage_contract["primary_model"]["tolerance"])
    existing_diag_path = source_root / "grouped_subset_diagnostics.csv"
    existing_diag = pd.read_csv(existing_diag_path) if existing_diag_path.exists() else pd.DataFrame()
    for rank in TARGET_RANKS:
        for definition in definitions:
            subset_id = definition["subset_id"]
            target_dir = output_root / "subset_models" / f"rank{rank:02d}" / subset_id
            target_dir.mkdir(parents=True, exist_ok=False)
            indices = np.asarray(definition["included_row_indices"], dtype=np.int64)
            status = "completed"
            failure_reason = ""
            reused = False
            converged = False
            n_iter = 0
            basis_path = target_dir / "basis.npy"
            fit_path = target_dir / "fit_activations.npy"
            validation_path = target_dir / "validation_activations.npy"
            try:
                if rank == 5 and not existing_diag.empty:
                    row = existing_diag[existing_diag["subset_id"] == subset_id]
                    if len(row) == 1 and str(row.iloc[0].get("basis_path", "")):
                        source_basis_path = source_root / str(row.iloc[0]["basis_path"])
                        source_model_dir = source_basis_path.parent
                        shutil.copy2(source_basis_path, basis_path)
                        shutil.copy2(source_model_dir / "fit_activations.npy", fit_path)
                        shutil.copy2(source_model_dir / "validation_activations.npy", validation_path)
                        basis = _normalize_basis(np.load(basis_path, allow_pickle=False))
                        fit_activations = np.load(fit_path, allow_pickle=False)
                        validation_activations = np.load(validation_path, allow_pickle=False)
                        if fit_activations.shape[0] != len(indices):
                            raise ValueError("rank-5 subset activation rows differ from included rows")
                        metadata_path = source_model_dir / "run_metadata.json"
                        if metadata_path.exists():
                            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
                            n_iter = int(metadata.get("n_iter", 0))
                            converged = bool(metadata.get("converged", False))
                        reused = True
                    else:
                        raise ValueError("rank-5 source subset model is missing")
                else:
                    if len(indices) < rank:
                        raise ValueError("subset has fewer rows than rank")
                    basis, fit_activations, validation_activations, n_iter, converged = _fit_weighted_kl_nmf(
                        fit[indices],
                        fit_weights[indices],
                        validation,
                        rank=rank,
                        max_iter=max_iter,
                        tolerance=tolerance,
                    )
                    np.save(basis_path, basis)
                    np.save(fit_path, fit_activations)
                    np.save(validation_path, validation_activations)
                metadata = {
                    "rank": rank,
                    "subset_id": subset_id,
                    "included_row_count": len(indices),
                    "included_fraction": definition["included_fraction"],
                    "included_row_indices": definition["included_row_indices"],
                    "group_preserving": definition["group_preserving"],
                    "init_method": "nndsvda",
                    "solver": "mu",
                    "loss": "kullback-leibler",
                    "max_iter": max_iter,
                    "tolerance": tolerance,
                    "n_iter": n_iter,
                    "converged": converged,
                    "reused_rank5_source_model": reused,
                    "basis_sha256": sha256_file(basis_path),
                    "fit_activation_sha256": sha256_file(fit_path),
                    "validation_activation_sha256": sha256_file(validation_path),
                }
                _json_dump(target_dir / "run_metadata.json", metadata)
                model_records[(rank, subset_id)] = {
                    **metadata,
                    "basis_path": str(basis_path.relative_to(output_root)),
                    "fit_activation_path": str(fit_path.relative_to(output_root)),
                    "validation_activation_path": str(validation_path.relative_to(output_root)),
                }
            except Exception as exc:
                status = "failed"
                failure_reason = f"{type(exc).__name__}: {exc}"
            diagnostics.append(
                {
                    "rank": rank,
                    "subset_id": subset_id,
                    "included_row_count": len(indices),
                    "included_fraction": definition["included_fraction"],
                    "group_preserving": definition["group_preserving"],
                    "model_status": status,
                    "failure_reason": failure_reason,
                    "converged": converged,
                    "reused_rank5_source_model": reused,
                    "n_iter": n_iter,
                    "basis_path": model_records.get((rank, subset_id), {}).get("basis_path", ""),
                    "basis_sha256": model_records.get((rank, subset_id), {}).get("basis_sha256", ""),
                }
            )
    return pd.DataFrame(diagnostics), model_records
