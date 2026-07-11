from __future__ import annotations
from itertools import combinations
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
from .models import match_components
from .stage_bc_run import PRIMARY, validation_mean_js, weighted_quantile

def representative_runs(matches: pd.DataFrame, runs: pd.DataFrame, metrics: pd.DataFrame) -> dict[int, str]:
    representatives: dict[int, str] = {}
    converged = runs[(runs["method"] == PRIMARY) & (runs["status"] == "completed") & (runs["converged"] == True)]
    for rank, group in converged.groupby("rank"):
        run_ids = group["run_id"].astype(str).tolist()
        if not run_ids:
            continue
        candidates: list[tuple[str, float, float, int]] = []
        for run_id in run_ids:
            similarities = matches[(matches["rank"] == rank) & ((matches["run_id_a"] == run_id) | (matches["run_id_b"] == run_id))]["js_similarity"].to_numpy(dtype=np.float64)
            mean_similarity = float(np.mean(similarities)) if len(similarities) else 1.0 if len(run_ids) == 1 else -1.0
            seed = int(group[group["run_id"] == run_id].iloc[0]["init_seed"])
            candidates.append((run_id, mean_similarity, validation_mean_js(metrics, run_id), seed))
        candidates.sort(key=lambda item: (-item[1], item[2], item[3]))
        representatives[int(rank)] = candidates[0][0]
    return representatives

def _internal_structure_quality(root: Path, run: pd.Series, fit_weights: np.ndarray, contract: dict[str, Any]) -> tuple[pd.DataFrame, pd.DataFrame, float, float]:
    basis = np.load(root / str(run["basis_path"]), allow_pickle=False)
    activations = np.load(root / str(run["fit_activation_path"]), allow_pickle=False)
    activation_sums = activations.sum(axis=1, keepdims=True)
    if np.any(activation_sums <= 0.0):
        raise ValueError(f"zero activation sum for {run['run_id']}")
    shares = activations / activation_sums
    duplicate_components: set[int] = set()
    similarity_rows: list[dict[str, Any]] = []
    for left, right in combinations(range(len(basis)), 2):
        match = match_components(basis[[left]], basis[[right]])[0]
        duplicate = float(match["js_similarity"]) >= float(contract["structure_quality"]["duplicate_if_js_similarity_gte"]) or float(match["cosine_similarity"]) >= float(contract["structure_quality"]["duplicate_if_cosine_similarity_gte"])
        if duplicate:
            duplicate_components.update((left, right))
        similarity_rows.append({"rank": int(run["rank"]), "structure_id_a": f"S{left + 1:03d}", "structure_id_b": f"S{right + 1:03d}", "js_distance": float(match["js_distance"]), "js_similarity": float(match["js_similarity"]), "cosine_similarity": float(match["cosine_similarity"]), "duplicate_pair": bool(duplicate)})
    summaries: list[dict[str, Any]] = []
    inactive_count = 0
    for component in range(len(basis)):
        p95 = weighted_quantile(shares[:, component], fit_weights, 0.95)
        maximum = float(np.max(shares[:, component]))
        inactive = p95 < float(contract["structure_quality"]["inactive_if_weighted_activation_share_p95_lt"])
        inactive_count += int(inactive)
        distribution = np.maximum(basis[component], 1e-12)
        distribution /= distribution.sum(dtype=np.float64)
        entropy = float(-np.sum(distribution * np.log(distribution)))
        summaries.append({"structure_id": f"S{component + 1:03d}", "rank": int(run["rank"]), "representative_run_id": str(run["run_id"]), "basis_row_index": component, "basis_mass_sum": float(basis[component].sum(dtype=np.float64)), "basis_min": float(np.min(basis[component])), "basis_max": float(np.max(basis[component])), "effective_cell_count": float(np.exp(entropy)), "basis_entropy": entropy, "fit_weighted_mean_activation_share": float(np.average(shares[:, component], weights=fit_weights)), "fit_weighted_p95_activation_share": p95, "fit_max_activation_share": maximum, "duplicate_flag": component in duplicate_components, "inactive_flag": bool(inactive)})
    return pd.DataFrame(summaries), pd.DataFrame(similarity_rows), len(duplicate_components) / len(basis), inactive_count / len(basis)

def _representative_component_survival(rank: int, representative_run_id: str, run_ids: list[str], matches: pd.DataFrame, contract: dict[str, Any]) -> tuple[list[dict[str, Any]], int, float]:
    other_runs = [run_id for run_id in run_ids if run_id != representative_run_id]
    rows: list[dict[str, Any]] = []
    stable_count = 0
    threshold = float(contract["matching_and_stability"]["component_survival_similarity_min"])
    required_rate = float(contract["matching_and_stability"]["component_survival_rate_min"])
    for component in range(int(rank)):
        similarities: list[float] = []
        for other_run in other_runs:
            direct = matches[(matches["rank"] == rank) & (matches["run_id_a"] == representative_run_id) & (matches["run_id_b"] == other_run) & (matches["component_index_a"] == component)]
            reverse = matches[(matches["rank"] == rank) & (matches["run_id_a"] == other_run) & (matches["run_id_b"] == representative_run_id) & (matches["component_index_b"] == component)]
            selected = direct if len(direct) else reverse
            if len(selected) != 1:
                raise ValueError(f"missing representative component match for rank {rank}, component {component}")
            similarities.append(float(selected.iloc[0]["js_similarity"]))
        survival_rate = float(np.mean(np.asarray(similarities) >= threshold)) if similarities else 0.0
        stable = survival_rate >= required_rate
        stable_count += int(stable)
        rows.append({"rank": rank, "representative_run_id": representative_run_id, "structure_id": f"S{component + 1:03d}", "initial_survival_rate": survival_rate, "initial_similarity_median": float(np.median(similarities)) if similarities else 0.0, "initial_stable": bool(stable)})
    return rows, stable_count, stable_count / int(rank)
