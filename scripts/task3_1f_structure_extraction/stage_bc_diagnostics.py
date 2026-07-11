from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .models import fit_weighted_frobenius_nmf, fit_weighted_kl_nmf, match_components
from .stage_bc_run import PRIMARY, _save_nmf_result
from .stage_bc_metrics import _sqrt_js_rows
from .stage_bc_subsets import grouped_subsets, _selected_representative

def _run_grouped_subset_diagnostics(
    root: Path,
    fit: np.ndarray,
    fit_weights: np.ndarray,
    fit_map: pd.DataFrame,
    validation: np.ndarray,
    selection: dict[str, Any],
    runs: pd.DataFrame,
    contract: dict[str, Any],
    max_iter: int,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    representative_run, representative_basis = _selected_representative(root, runs, selection)
    rank = int(selection["selected_rank"])
    definitions = grouped_subsets(fit_map, contract)
    tolerance = float(contract["primary_model"]["tolerance"])
    summary_rows: list[dict[str, Any]] = []
    match_rows: list[dict[str, Any]] = []
    per_component_counts = np.zeros(rank, dtype=np.int64)
    similarity_threshold = float(contract["matching_and_stability"]["grouped_subset"]["component_similarity_min"])
    for definition in definitions:
        indices = np.asarray(definition["included_row_indices"], dtype=np.int64)
        status = "completed"
        failure_reason = ""
        median_similarity = 0.0
        surviving_fraction = 0.0
        model_path = ""
        model_hash = ""
        converged = False
        try:
            if len(indices) < rank:
                raise ValueError("subset has fewer rows than selected rank")
            result = fit_weighted_kl_nmf(
                fit[indices],
                fit_weights[indices],
                validation,
                rank=rank,
                init_method=contract["primary_model"]["anchor_initialization"],
                init_seed=0,
                max_iter=max_iter,
                tolerance=tolerance,
            )
            run_id = f"subset_{definition['subset_id']}"
            saved = _save_nmf_result(
                root,
                f"sensitivity/subset_models/{definition['subset_id']}",
                run_id=run_id,
                method=PRIMARY,
                rank=rank,
                role="subset",
                init_method=contract["primary_model"]["anchor_initialization"],
                init_seed=0,
                solver="mu",
                loss="kullback-leibler",
                result=result,
                max_iter=max_iter,
                tolerance=tolerance,
                subset_id=definition["subset_id"],
            )
            converged = bool(result.converged)
            model_path = saved["basis_path"]
            model_hash = saved["basis_sha256"]
            matches = match_components(representative_basis, result.basis)
            similarities = np.asarray([float(item["js_similarity"]) for item in matches])
            median_similarity = float(np.median(similarities))
            survived = similarities >= similarity_threshold
            per_component_counts += survived.astype(np.int64)
            surviving_fraction = float(np.mean(survived))
            for component, item in enumerate(matches):
                match_rows.append(
                    {
                        "subset_id": definition["subset_id"],
                        "rank": rank,
                        "representative_run_id": str(representative_run["run_id"]),
                        "representative_structure_id": f"S{component + 1:03d}",
                        **item,
                        "survived": bool(float(item["js_similarity"]) >= similarity_threshold),
                    }
                )
        except Exception as exc:
            status = "failed"
            failure_reason = f"{type(exc).__name__}: {exc}"
        summary_rows.append(
            {
                "subset_id": definition["subset_id"],
                "included_row_count": len(indices),
                "included_fraction": definition["included_fraction"],
                "included_row_indices_json": json.dumps(definition["included_row_indices"]),
                "included_group_keys_json": json.dumps(definition["included_group_keys"]),
                "excluded_group_keys_json": json.dumps(definition["excluded_group_keys"]),
                "group_preserving": definition["group_preserving"],
                "model_status": status,
                "failure_reason": failure_reason,
                "converged": converged,
                "basis_path": model_path,
                "basis_sha256": model_hash,
                "median_similarity": median_similarity,
                "surviving_component_fraction": surviving_fraction,
            }
        )
    required_count = int(contract["matching_and_stability"]["grouped_subset"]["required_subset_survival_count"])
    stable_fraction = float(np.mean(per_component_counts >= required_count))
    all_similarities = [float(row["js_similarity"]) for row in match_rows]
    overall = {
        "median_similarity": float(np.median(all_similarities)) if all_similarities else 0.0,
        "stable_component_fraction": stable_fraction,
        "component_survival_counts": per_component_counts.tolist(),
        "passed": bool(
            all(row["model_status"] == "completed" for row in summary_rows)
            and all(row["group_preserving"] for row in summary_rows)
            and (float(np.median(all_similarities)) if all_similarities else 0.0)
            >= float(contract["matching_and_stability"]["grouped_subset"]["median_similarity_min"])
            and stable_fraction
            >= float(contract["matching_and_stability"]["grouped_subset"]["stable_component_fraction_min"])
        ),
    }
    return pd.DataFrame(summary_rows), pd.DataFrame(match_rows), overall

def _run_world_seed_diagnostics(
    root: Path,
    fit: np.ndarray,
    fit_weights: np.ndarray,
    fit_map: pd.DataFrame,
    validation: np.ndarray,
    selection: dict[str, Any],
    runs: pd.DataFrame,
    contract: dict[str, Any],
    max_iter: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    representative_run, representative_basis = _selected_representative(root, runs, selection)
    rank = int(selection["selected_rank"])
    tolerance = float(contract["primary_model"]["tolerance"])
    rows: list[dict[str, Any]] = []
    match_rows: list[dict[str, Any]] = []
    for seed in contract["matching_and_stability"]["world_seed_sensitivity"]["fit_world_seeds"]:
        indices = np.flatnonzero(fit_map["seed"].to_numpy(dtype=np.int64) == int(seed))
        status = "completed"
        failure_reason = ""
        median_similarity = 0.0
        basis_path = ""
        basis_hash = ""
        converged = False
        try:
            if len(indices) < rank:
                raise ValueError(f"world seed {seed} has fewer rows than selected rank")
            result = fit_weighted_kl_nmf(
                fit[indices],
                fit_weights[indices],
                validation,
                rank=rank,
                init_method=contract["primary_model"]["anchor_initialization"],
                init_seed=0,
                max_iter=max_iter,
                tolerance=tolerance,
            )
            saved = _save_nmf_result(
                root,
                f"sensitivity/world_seed_models/{int(seed)}",
                run_id=f"world_seed_{int(seed)}",
                method=PRIMARY,
                rank=rank,
                role="world_seed_sensitivity",
                init_method=contract["primary_model"]["anchor_initialization"],
                init_seed=0,
                solver="mu",
                loss="kullback-leibler",
                result=result,
                max_iter=max_iter,
                tolerance=tolerance,
                world_seed_filter=str(int(seed)),
            )
            converged = bool(result.converged)
            basis_path = saved["basis_path"]
            basis_hash = saved["basis_sha256"]
            component_matches = match_components(representative_basis, result.basis)
            median_similarity = float(np.median([item["js_similarity"] for item in component_matches]))
            for component, item in enumerate(component_matches):
                match_rows.append(
                    {
                        "world_seed": int(seed),
                        "rank": rank,
                        "representative_run_id": str(representative_run["run_id"]),
                        "representative_structure_id": f"S{component + 1:03d}",
                        **item,
                    }
                )
        except Exception as exc:
            status = "failed"
            failure_reason = f"{type(exc).__name__}: {exc}"
        threshold = float(contract["matching_and_stability"]["world_seed_sensitivity"]["median_similarity_conditional_threshold"])
        rows.append(
            {
                "world_seed": int(seed),
                "selected_rank": rank,
                "selected_rank_unchanged": True,
                "representative_run_id": str(representative_run["run_id"]),
                "row_count": len(indices),
                "model_status": status,
                "failure_reason": failure_reason,
                "converged": converged,
                "basis_path": basis_path,
                "basis_sha256": basis_hash,
                "median_similarity": median_similarity,
                "diagnostic_status": "stable" if status == "completed" and median_similarity >= threshold else "conditional",
            }
        )
    return pd.DataFrame(rows), pd.DataFrame(match_rows)

def _run_frobenius_sensitivity(
    root: Path,
    fit: np.ndarray,
    fit_weights: np.ndarray,
    validation: np.ndarray,
    selection: dict[str, Any],
    runs: pd.DataFrame,
    contract: dict[str, Any],
    max_iter: int,
) -> pd.DataFrame:
    representative_run, representative_basis = _selected_representative(root, runs, selection)
    grid = [int(value) for value in contract["rank_grid"]]
    selected_rank = int(selection["selected_rank"])
    selected_index = grid.index(selected_rank)
    ranks = grid[max(0, selected_index - 1) : selected_index + 2]
    config = contract["references"]["frobenius_nmf"]
    rows: list[dict[str, Any]] = []
    for rank in ranks:
        for seed in config["seeds"]:
            status = "completed"
            failure_reason = ""
            validation_js = float("inf")
            median_primary_similarity: float | str = ""
            basis_path = ""
            basis_hash = ""
            converged = False
            try:
                result = fit_weighted_frobenius_nmf(
                    fit,
                    fit_weights,
                    validation,
                    rank=rank,
                    init_seed=int(seed),
                    max_iter=max_iter,
                    tolerance=float(config["tolerance"]),
                )
                run_id = f"nmf_frobenius_rank{rank:02d}_seed{int(seed)}"
                saved = _save_nmf_result(
                    root,
                    f"sensitivity/frobenius_models/{run_id}",
                    run_id=run_id,
                    method="nmf_frobenius",
                    rank=rank,
                    role="reference",
                    init_method="random",
                    init_seed=int(seed),
                    solver="cd",
                    loss="frobenius",
                    result=result,
                    max_iter=max_iter,
                    tolerance=float(config["tolerance"]),
                )
                converged = bool(result.converged)
                basis_path = saved["basis_path"]
                basis_hash = saved["basis_sha256"]
                raw = result.validation_activations @ result.basis
                row_sums = raw.sum(axis=1, keepdims=True)
                distribution = raw / row_sums
                validation_js = float(np.mean(_sqrt_js_rows(validation, distribution)))
                if rank == selected_rank:
                    median_primary_similarity = float(np.median([item["js_similarity"] for item in match_components(representative_basis, result.basis)]))
            except Exception as exc:
                status = "failed"
                failure_reason = f"{type(exc).__name__}: {exc}"
            rows.append(
                {
                    "rank": rank,
                    "seed": int(seed),
                    "model_status": status,
                    "failure_reason": failure_reason,
                    "converged": converged,
                    "basis_path": basis_path,
                    "basis_sha256": basis_hash,
                    "validation_weighted_mean_js": validation_js,
                    "median_primary_structure_similarity": median_primary_similarity,
                    "influenced_primary_selection": False,
                    "primary_selected_rank_before_sensitivity": selected_rank,
                    "primary_selected_rank_after_sensitivity": selected_rank,
                    "representative_run_id": str(representative_run["run_id"]),
                }
            )
    return pd.DataFrame(rows)
