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
            similarities = matches[
                (matches["rank"] == rank)
                & ((matches["run_id_a"] == run_id) | (matches["run_id_b"] == run_id))
            ]["js_similarity"].to_numpy(dtype=np.float64)
            mean_similarity = float(np.mean(similarities)) if len(similarities) else 1.0 if len(run_ids) == 1 else -1.0
            seed = int(group[group["run_id"] == run_id].iloc[0]["init_seed"])
            candidates.append((run_id, mean_similarity, validation_mean_js(metrics, run_id), seed))
        candidates.sort(key=lambda item: (-item[1], item[2], item[3]))
        representatives[int(rank)] = candidates[0][0]
    return representatives

def _internal_structure_quality(
    root: Path,
    run: pd.Series,
    fit_weights: np.ndarray,
    contract: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, float, float]:
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
        duplicate = (
            float(match["js_similarity"]) >= float(contract["structure_quality"]["duplicate_if_js_similarity_gte"])
            or float(match["cosine_similarity"]) >= float(contract["structure_quality"]["duplicate_if_cosine_similarity_gte"])
        )
        if duplicate:
            duplicate_components.update((left, right))
        similarity_rows.append(
            {
                "rank": int(run["rank"]),
                "structure_id_a": f"S{left + 1:03d}",
                "structure_id_b": f"S{right + 1:03d}",
                "js_distance": float(match["js_distance"]),
                "js_similarity": float(match["js_similarity"]),
                "cosine_similarity": float(match["cosine_similarity"]),
                "duplicate_pair": bool(duplicate),
            }
        )
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
        summaries.append(
            {
                "structure_id": f"S{component + 1:03d}",
                "rank": int(run["rank"]),
                "representative_run_id": str(run["run_id"]),
                "basis_row_index": component,
                "basis_mass_sum": float(basis[component].sum(dtype=np.float64)),
                "basis_min": float(np.min(basis[component])),
                "basis_max": float(np.max(basis[component])),
                "effective_cell_count": float(np.exp(entropy)),
                "basis_entropy": entropy,
                "fit_weighted_mean_activation_share": float(np.average(shares[:, component], weights=fit_weights)),
                "fit_weighted_p95_activation_share": p95,
                "fit_max_activation_share": maximum,
                "duplicate_flag": component in duplicate_components,
                "inactive_flag": bool(inactive),
            }
        )
    duplicate_fraction = len(duplicate_components) / len(basis)
    inactive_fraction = inactive_count / len(basis)
    return pd.DataFrame(summaries), pd.DataFrame(similarity_rows), duplicate_fraction, inactive_fraction

def _representative_component_survival(
    rank: int,
    representative_run_id: str,
    run_ids: list[str],
    matches: pd.DataFrame,
    contract: dict[str, Any],
) -> tuple[list[dict[str, Any]], int, float]:
    other_runs = [run_id for run_id in run_ids if run_id != representative_run_id]
    component_count = int(rank)
    rows: list[dict[str, Any]] = []
    stable_count = 0
    threshold = float(contract["matching_and_stability"]["component_survival_similarity_min"])
    required_rate = float(contract["matching_and_stability"]["component_survival_rate_min"])
    for component in range(component_count):
        similarities: list[float] = []
        for other_run in other_runs:
            direct = matches[
                (matches["rank"] == rank)
                & (matches["run_id_a"] == representative_run_id)
                & (matches["run_id_b"] == other_run)
                & (matches["component_index_a"] == component)
            ]
            reverse = matches[
                (matches["rank"] == rank)
                & (matches["run_id_a"] == other_run)
                & (matches["run_id_b"] == representative_run_id)
                & (matches["component_index_b"] == component)
            ]
            selected = direct if len(direct) else reverse
            if len(selected) != 1:
                raise ValueError(f"missing representative component match for rank {rank}, component {component}")
            similarities.append(float(selected.iloc[0]["js_similarity"]))
        survival_rate = float(np.mean(np.asarray(similarities) >= threshold)) if similarities else 0.0
        stable = survival_rate >= required_rate
        stable_count += int(stable)
        rows.append(
            {
                "rank": rank,
                "representative_run_id": representative_run_id,
                "structure_id": f"S{component + 1:03d}",
                "initial_survival_rate": survival_rate,
                "initial_similarity_median": float(np.median(similarities)) if similarities else 0.0,
                "initial_stable": bool(stable),
            }
        )
    return rows, stable_count, stable_count / component_count

def _validation_group_integrity(metrics: pd.DataFrame, run_id: str) -> bool:
    subset = metrics[(metrics["run_id"] == run_id) & (metrics["split"] == "validation")]
    if subset.empty or not np.isfinite(subset["value"].to_numpy(dtype=np.float64)).all():
        return False
    expected_groups = {"all", "distribution_group", "source_step", "active_factor_count", "vector_origin"}
    if not expected_groups.issubset(set(subset["subgroup_type"].astype(str)):
        return False
    invalid = subset[
        (subset["metric"].isin(["negative_value_count", "nonfinite_value_count"]))
        & (subset["value"].astype(float) != 0.0)
    ]
    return invalid.empty and bool((subset["row_count"].astype(int) > 0).all())

def _external_base_ratio(metrics: pd.DataFrame, run_id: str) -> float:
    common = (
        (metrics["run_id"] == run_id)
        & (metrics["split"] == "validation")
        & (metrics["subgroup_type"] == "distribution_group")
        & (metrics["weighting"] == "weighted")
        & (metrics["metric"] == "js_distance")
        & (metrics["aggregation"] == "mean")
    )
    external = metrics[common & (metrics["subgroup_value"].astype(str) == "external_augmented")]
    base = metrics[common & (metrics["subgroup_value"].astype(str) == "base_v3_3")]
    if len(external) != 1 or len(base) != 1:
        return float("inf")
    external_value = float(external.iloc[0]["value"])
    base_value = float(base.iloc[0]["value"])
    if base_value <= 0.0:
        return 1.0 if external_value <= 0.0 else float("inf")
    return external_value / base_value

def rank_summaries(
    root: Path,
    runs: pd.DataFrame,
    metrics: pd.DataFrame,
    matches: pd.DataFrame,
    fit_weights: np.ndarray,
    contract: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    representatives = representative_runs(matches, runs, metrics)
    baseline_js = validation_mean_js(metrics, "mean_distribution_baseline")
    rank_rows: list[dict[str, Any]] = []
    structure_rows: list[dict[str, Any]] = []
    internal_rows: list[dict[str, Any]] = []
    primary = runs[runs["method"] == PRIMARY]
    for rank in sorted(primary["rank"].astype(int).unique()):
        group = primary[primary["rank"] == rank]
        random_runs = group[group["run_role"] == "random_init"]
        converged = group[(group["status"] == "completed") & (group["converged"] == True)]
        converged_ids = converged["run_id"].astype(str).tolist()
        representative_id = representatives.get(rank, "")
        rank_matches = matches[
            (matches["rank"] == rank)
            & (matches["run_id_a"].isin(converged_ids))
            & (matches["run_id_b"].isin(converged_ids))
        ]
        similarities = rank_matches["js_similarity"].to_numpy(dtype=np.float64)
        stable_count = 0
        stable_fraction = 0.0
        duplicate_fraction = 1.0
        inactive_fraction = 1.0
        if representative_id:
            representative = group[group["run_id"] == representative_id].iloc[0]
            quality, internal, survival_dup, inactive_fraction = _internal_structure_quality(root, representative, fit_weights, contract)
            duplicate_fraction = survival_dup
            survival_rows, stable_count, stable_fraction = _representative_component_survival(
                rank, representative_id, converged_ids, matches, contract
            )
            quality = quality.merge(pd.DataFrame(survival_rows), on=["rank", "representative_run_id", "structure_id"], how="left")
            structure_rows.extend(quality.to_dict("records"))
            internal_rows.extend(internal.to_dict("records"))
        converged_random_count = int(((random_runs["status"] == "completed") & (random_runs["converged"] == True)).sum())
        completed_random_count = int((random_runs["status"] == "completed").sum())
        validation_values = [validation_mean_js(metrics, run_id) for run_id in converged_ids]
        rank_validation_mean = float(np.mean(validation_values)) if validation_values else float("inf")
        median_similarity = float(np.median(similarities)) if len(similarities) else 0.0
        p10_similarity = float(np.quantile(similarities, 0.10)) if len(similarities) else 0.0
        group_integrity = bool(representative_id) and _validation_group_integrity(metrics, representative_id)
        external_base_ratio = _external_base_ratio(metrics, representative_id) if representative_id else float("inf")
        gates = {
            "random_convergence": converged_random_count >= int(contract["primary_model"]["minimum_converged_random_runs"]),
            "initialization_median_similarity": median_similarity >= float(contract["matching_and_stability"]["initialization_median_similarity_min"]),
            "stable_component_fraction": stable_fraction >= float(contract["matching_and_stability"]["stable_component_fraction_min"]),
            "duplicate_fraction": duplicate_fraction <= float(contract["structure_quality"]["duplicate_structure_fraction_max"]),
            "inactive_fraction": inactive_fraction <= float(contract["structure_quality"]["inactive_structure_fraction_max"]),
            "mean_baseline_improvement": rank_validation_mean < baseline_js,
            "validation_group_integrity": group_integrity,
            "external_base_ratio": external_base_ratio <= float(contract["admissibility"]["external_to_base_weighted_mean_js_ratio_max"]),
        }
        rejection_reasons = [name for name, passed in gates.items() if not passed]
        rank_rows.append(
            {
                "rank": rank,
                "required_run_count": 7,
                "completed_run_count": int((group["status"] == "completed").sum()),
                "converged_random_run_count": converged_random_count,
                "completed_random_run_count": completed_random_count,
                "convergence_rate": converged_random_count / 6.0,
                "representative_run_id": representative_id,
                "median_matched_js_similarity": median_similarity,
                "p10_matched_js_similarity": p10_similarity,
                "stable_component_count": stable_count,
                "component_count": rank,
                "stable_component_fraction": stable_fraction,
                "redundancy_rate": duplicate_fraction,
                "inactive_rate": inactive_fraction,
                "validation_weighted_mean_js": rank_validation_mean,
                "validation_weighted_mean_js_standard_error": float(np.std(validation_values, ddof=1) / np.sqrt(len(validation_values))) if len(validation_values) > 1 else 0.0,
                "validation_weighted_median_js": float(np.median(validation_values)) if validation_values else float("inf"),
                "validation_weighted_p95_js": float(np.quantile(validation_values, 0.95)) if validation_values else float("inf"),
                "mean_baseline_improvement_rate": (baseline_js - rank_validation_mean) / max(baseline_js, 1e-12),
                "external_base_error_ratio": external_base_ratio,
                "validation_group_integrity": group_integrity,
                "admissible": not rejection_reasons,
                "rejection_reasons": ";".join(rejection_reasons),
            }
        )
    return pd.DataFrame(rank_rows), pd.DataFrame(structure_rows), pd.DataFrame(internal_rows)

def select_rank(summary: pd.DataFrame, runs: pd.DataFrame, metrics: pd.DataFrame) -> dict[str, Any]:
    admissible = summary[summary["admissible"] == True].copy()
    if admissible.empty:
        return {"selection_status": "no_admissible_rank", "admissible_ranks": [], "holdout_accessed": False}
    rows: list[tuple[int, float, float]] = []
    for rank in admissible["rank"].astype(int):
        run_ids = runs[(runs["method"] == PRIMARY) & (runs["rank"] == rank) & (runs["status"] == "completed") & (runs["converged"] == True)]["run_id"].astype(str)
        values = [validation_mean_js(metrics, run_id) for run_id in run_ids]
        if not values:
            raise ValueError(f"admissible rank {rank} has no converged runs")
        standard_error = float(np.std(values, ddof=1) / np.sqrt(len(values))) if len(values) > 1 else 0.0
        rows.append((rank, float(np.mean(values)), standard_error))
    best = min(rows, key=lambda item: item[1])
    threshold = best[1] + best[2]
    selected_rank = min(rank for rank, mean, _ in rows if mean <= threshold)
    representative = str(summary[summary["rank"] == selected_rank].iloc[0]["representative_run_id"])
    return {
        "selection_status": "selected",
        "selected_rank": selected_rank,
        "selected_representative_run": representative,
        "admissible_ranks": [rank for rank, _, _ in rows],
        "best_error_rank": best[0],
        "best_error_mean": best[1],
        "best_error_standard_error": best[2],
        "one_standard_error_threshold": threshold,
        "holdout_accessed": False,
    }
