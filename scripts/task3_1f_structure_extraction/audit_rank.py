from __future__ import annotations
from itertools import combinations
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
from .contract import sha256_file
from .audit_metrics import PRIMARY, _weighted_quantile
from .audit_matches import _component_matches

def _validation_mean_js(metrics: pd.DataFrame, run_id: str) -> float:
    rows = metrics[(metrics["run_id"] == run_id) & (metrics["split"] == "validation") & (metrics["subgroup_type"] == "all") & (metrics["subgroup_value"].astype(str) == "all") & (metrics["weighting"] == "weighted") & (metrics["metric"] == "js_distance") & (metrics["aggregation"] == "mean")]
    if len(rows) != 1: raise ValueError(f"missing validation mean JS for {run_id}")
    return float(rows.iloc[0]["value"])

def _representatives(matches: pd.DataFrame, runs: pd.DataFrame, metrics: pd.DataFrame) -> dict[int, str]:
    representatives: dict[int, str] = {}
    converged = runs[(runs["method"] == PRIMARY) & (runs["status"] == "completed") & (runs["converged"] == True)]
    for rank, group in converged.groupby("rank"):
        candidates: list[tuple[str, float, float, int]] = []
        run_ids = group["run_id"].astype(str).tolist()
        for run_id in run_ids:
            similarities = matches[(matches["rank"] == rank) & ((matches["run_id_a"] == run_id) | (matches["run_id_b"] == run_id))]["js_similarity"].to_numpy(dtype=np.float64)
            mean_similarity = float(np.mean(similarities)) if len(similarities) else 1.0 if len(run_ids) == 1 else -1.0
            seed = int(group[group["run_id"] == run_id].iloc[0]["init_seed"])
            candidates.append((run_id, mean_similarity, _validation_mean_js(metrics, run_id), seed))
        candidates.sort(key=lambda item: (-item[1], item[2], item[3])); representatives[int(rank)] = candidates[0][0]
    return representatives

def _component_survival(rank: int, representative: str, converged_ids: list[str], matches: pd.DataFrame, threshold: float, required_rate: float) -> tuple[int, float]:
    stable_count = 0; others = [run_id for run_id in converged_ids if run_id != representative]
    for component in range(rank):
        similarities: list[float] = []
        for other in others:
            direct = matches[(matches["rank"] == rank) & (matches["run_id_a"] == representative) & (matches["run_id_b"] == other) & (matches["component_index_a"] == component)]
            reverse = matches[(matches["rank"] == rank) & (matches["run_id_a"] == other) & (matches["run_id_b"] == representative) & (matches["component_index_b"] == component)]
            row = direct if len(direct) else reverse
            if len(row) != 1: raise ValueError("missing representative component match")
            similarities.append(float(row.iloc[0]["js_similarity"]))
        survival_rate = float(np.mean(np.asarray(similarities) >= threshold)) if similarities else 0.0
        stable_count += int(survival_rate >= required_rate)
    return stable_count, stable_count / rank

def _quality(root: Path, run: pd.Series, fit_weights: np.ndarray, contract: dict[str, Any]) -> tuple[float, float]:
    basis = np.load(root / str(run["basis_path"]), allow_pickle=False); activations = np.load(root / str(run["fit_activation_path"]), allow_pickle=False)
    sums = activations.sum(axis=1, keepdims=True)
    if np.any(sums <= 0.0): raise ValueError("zero activation sum")
    shares = activations / sums; duplicate: set[int] = set()
    for left, right in combinations(range(len(basis)), 2):
        match = _component_matches(basis[[left]], basis[[right]])[0]
        if match["js_similarity"] >= contract["structure_quality"]["duplicate_if_js_similarity_gte"] or match["cosine_similarity"] >= contract["structure_quality"]["duplicate_if_cosine_similarity_gte"]: duplicate.update((left, right))
    inactive = [_weighted_quantile(shares[:, component], fit_weights, 0.95) < contract["structure_quality"]["inactive_if_weighted_activation_share_p95_lt"] for component in range(len(basis))]
    return len(duplicate) / len(basis), float(np.mean(inactive))

def _group_integrity(metrics: pd.DataFrame, run_id: str) -> bool:
    subset = metrics[(metrics["run_id"] == run_id) & (metrics["split"] == "validation")]
    expected = {"all", "distribution_group", "source_step", "active_factor_count", "vector_origin"}
    invalid = subset[subset["metric"].isin(["negative_value_count", "nonfinite_value_count"]) & (subset["value"].astype(float) != 0.0)]
    return not subset.empty and np.isfinite(subset["value"].to_numpy(dtype=np.float64)).all() and expected.issubset(set(subset["subgroup_type"].astype(str))) and invalid.empty and bool((subset["row_count"].astype(int) > 0).all())

def _external_base_ratio(metrics: pd.DataFrame, run_id: str) -> float:
    common = (metrics["run_id"] == run_id) & (metrics["split"] == "validation") & (metrics["subgroup_type"] == "distribution_group") & (metrics["weighting"] == "weighted") & (metrics["metric"] == "js_distance") & (metrics["aggregation"] == "mean")
    external = metrics[common & (metrics["subgroup_value"].astype(str) == "external_augmented")]; base = metrics[common & (metrics["subgroup_value"].astype(str) == "base_v3_3")]
    if len(external) != 1 or len(base) != 1: return float("inf")
    external_value = float(external.iloc[0]["value"]); base_value = float(base.iloc[0]["value"])
    return external_value / base_value if base_value > 0.0 else 1.0 if external_value <= 0.0 else float("inf")

def _rank_summary(root: Path, runs: pd.DataFrame, metrics: pd.DataFrame, matches: pd.DataFrame, fit_weights: np.ndarray, contract: dict[str, Any]) -> pd.DataFrame:
    representatives = _representatives(matches, runs, metrics); baseline = _validation_mean_js(metrics, "mean_distribution_baseline"); rows: list[dict[str, Any]] = []
    for rank in sorted(runs[runs["method"] == PRIMARY]["rank"].astype(int).unique()):
        group = runs[(runs["method"] == PRIMARY) & (runs["rank"] == rank)]; randoms = group[group["run_role"] == "random_init"]
        converged = group[(group["status"] == "completed") & (group["converged"] == True)]; converged_ids = converged["run_id"].astype(str).tolist(); representative = representatives.get(rank, "")
        rank_matches = matches[(matches["rank"] == rank) & (matches["run_id_a"].isin(converged_ids)) & (matches["run_id_b"].isin(converged_ids))]; similarities = rank_matches["js_similarity"].to_numpy(dtype=np.float64)
        stable_count, stable_fraction = (0, 0.0); duplicate_fraction, inactive_fraction = (1.0, 1.0)
        if representative:
            stable_count, stable_fraction = _component_survival(rank, representative, converged_ids, matches, contract["matching_and_stability"]["component_survival_similarity_min"], contract["matching_and_stability"]["component_survival_rate_min"])
            duplicate_fraction, inactive_fraction = _quality(root, group[group["run_id"] == representative].iloc[0], fit_weights, contract)
        values = [_validation_mean_js(metrics, run_id) for run_id in converged_ids]; mean_value = float(np.mean(values)) if values else float("inf"); ratio = _external_base_ratio(metrics, representative) if representative else float("inf")
        gates = {"random_convergence": int(((randoms["status"] == "completed") & (randoms["converged"] == True)).sum()) >= contract["primary_model"]["minimum_converged_random_runs"], "initialization_median_similarity": (float(np.median(similarities)) if len(similarities) else 0.0) >= contract["matching_and_stability"]["initialization_median_similarity_min"], "stable_component_fraction": stable_fraction >= contract["matching_and_stability"]["stable_component_fraction_min"], "duplicate_fraction": duplicate_fraction <= contract["structure_quality"]["duplicate_structure_fraction_max"], "inactive_fraction": inactive_fraction <= contract["structure_quality"]["inactive_structure_fraction_max"], "mean_baseline_improvement": mean_value < baseline, "validation_group_integrity": bool(representative) and _group_integrity(metrics, representative), "external_base_ratio": ratio <= contract["admissibility"]["external_to_base_weighted_mean_js_ratio_max"]}
        rows.append({"rank": rank, "required_run_count": 7, "completed_run_count": int((group["status"] == "completed").sum()), "converged_random_run_count": int(((randoms["status"] == "completed") & (randoms["converged"] == True)).sum()), "completed_random_run_count": int((randoms["status"] == "completed").sum()), "convergence_rate": float(((randoms["status"] == "completed") & (randoms["converged"] == True)).sum() / 6.0), "representative_run_id": representative, "median_matched_js_similarity": float(np.median(similarities)) if len(similarities) else 0.0, "p10_matched_js_similarity": float(np.quantile(similarities, 0.10)) if len(similarities) else 0.0, "stable_component_count": stable_count, "component_count": rank, "stable_component_fraction": stable_fraction, "redundancy_rate": duplicate_fraction, "inactive_rate": inactive_fraction, "validation_weighted_mean_js": mean_value, "validation_weighted_mean_js_standard_error": float(np.std(values, ddof=1) / np.sqrt(len(values))) if len(values) > 1 else 0.0, "validation_weighted_median_js": float(np.median(values)) if values else float("inf"), "validation_weighted_p95_js": float(np.quantile(values, 0.95)) if values else float("inf"), "mean_baseline_improvement_rate": (baseline - mean_value) / max(baseline, 1e-12), "external_base_error_ratio": ratio, "validation_group_integrity": bool(representative) and _group_integrity(metrics, representative), "admissible": all(gates.values()), "rejection_reasons": ";".join(name for name, passed in gates.items() if not passed)})
    return pd.DataFrame(rows)

def _select(summary: pd.DataFrame, runs: pd.DataFrame, metrics: pd.DataFrame) -> dict[str, Any]:
    admissible = summary[summary["admissible"] == True]
    if admissible.empty: return {"selection_status": "no_admissible_rank", "admissible_ranks": [], "holdout_accessed": False}
    rows: list[tuple[int, float, float]] = []
    for rank in admissible["rank"].astype(int):
        run_ids = runs[(runs["method"] == PRIMARY) & (runs["rank"] == rank) & (runs["status"] == "completed") & (runs["converged"] == True)]["run_id"].astype(str)
        values = [_validation_mean_js(metrics, run_id) for run_id in run_ids]; standard_error = float(np.std(values, ddof=1) / np.sqrt(len(values))) if len(values) > 1 else 0.0; rows.append((rank, float(np.mean(values)), standard_error))
    best = min(rows, key=lambda item: item[1]); threshold = best[1] + best[2]; selected_rank = min(rank for rank, mean, _ in rows if mean <= threshold); representative = str(summary[summary["rank"] == selected_rank].iloc[0]["representative_run_id"])
    return {"selection_status": "selected", "selected_rank": selected_rank, "selected_representative_run": representative, "admissible_ranks": [rank for rank, _, _ in rows], "best_error_rank": best[0], "best_error_mean": best[1], "best_error_standard_error": best[2], "one_standard_error_threshold": threshold, "holdout_accessed": False}

def _compare_rank_summaries(stored: pd.DataFrame, recomputed: pd.DataFrame) -> tuple[bool, list[str]]:
    stored = stored.sort_values("rank").reset_index(drop=True); recomputed = recomputed.sort_values("rank").reset_index(drop=True)
    if len(stored) != len(recomputed): return False, ["row count"]
    failures: list[str] = []
    exact = ["rank", "required_run_count", "completed_run_count", "converged_random_run_count", "completed_random_run_count", "representative_run_id", "stable_component_count", "component_count", "validation_group_integrity", "admissible", "rejection_reasons"]
    numeric = ["convergence_rate", "median_matched_js_similarity", "p10_matched_js_similarity", "stable_component_fraction", "redundancy_rate", "inactive_rate", "validation_weighted_mean_js", "validation_weighted_mean_js_standard_error", "validation_weighted_median_js", "validation_weighted_p95_js", "mean_baseline_improvement_rate", "external_base_error_ratio"]
    for column in exact:
        if stored[column].fillna("").astype(str).tolist() != recomputed[column].fillna("").astype(str).tolist(): failures.append(column)
    for column in numeric:
        if not np.allclose(stored[column].to_numpy(dtype=np.float64), recomputed[column].to_numpy(dtype=np.float64), rtol=1e-9, atol=1e-12, equal_nan=True): failures.append(column)
    return not failures, failures

def _verify_models(root: Path, runs: pd.DataFrame) -> tuple[list[str], list[str], list[tuple[str, str]], list[str]]:
    hash_bad: list[str] = []; shape_bad: list[str] = []; copied: list[tuple[str, str]] = []; convergence_bad: list[str] = []; signatures: dict[tuple[str, str, str], str] = {}
    for _, run in runs[runs["method"] == PRIMARY].iterrows():
        if run["status"] != "completed": continue
        basis_path = root / str(run["basis_path"]); fit_path = root / str(run["fit_activation_path"]); validation_path = root / str(run["validation_activation_path"])
        if not basis_path.is_file() or not fit_path.is_file() or not validation_path.is_file() or sha256_file(basis_path) != str(run["basis_sha256"]) or sha256_file(fit_path) != str(run["fit_activation_sha256"]) or sha256_file(validation_path) != str(run["validation_activation_sha256"]): hash_bad.append(str(run["run_id"])); continue
        basis = np.load(basis_path, allow_pickle=False); fit_activations = np.load(fit_path, allow_pickle=False); validation_activations = np.load(validation_path, allow_pickle=False); rank = int(run["rank"])
        if basis.shape[0] != rank or fit_activations.shape[1] != rank or validation_activations.shape[1] != rank or not np.isfinite(basis).all() or not np.isfinite(fit_activations).all() or not np.isfinite(validation_activations).all() or np.any(basis < 0.0) or np.any(fit_activations < 0.0) or np.any(validation_activations < 0.0) or not np.allclose(basis.sum(axis=1), 1.0, rtol=0.0, atol=1e-10): shape_bad.append(str(run["run_id"]))
        signature = (str(run["basis_sha256"]), str(run["fit_activation_sha256"]), str(run["validation_activation_sha256"]))
        if signature in signatures: copied.append((signatures[signature], str(run["run_id"])))
        signatures[signature] = str(run["run_id"])
        if int(run["n_iter"]) < 0 or int(run["n_iter"]) > int(run["max_iter"]): convergence_bad.append(str(run["run_id"]))
        if bool(run["converged"]) and int(run["n_iter"]) >= int(run["max_iter"]): convergence_bad.append(str(run["run_id"]))
    return hash_bad, shape_bad, copied, convergence_bad

def _expected_run_ids(contract: dict[str, Any], ranks: list[int]) -> list[str]:
    output: list[str] = []
    for rank in ranks:
        output.append(f"nmf_kl_rank{rank:02d}_anchor"); output.extend(f"nmf_kl_rank{rank:02d}_seed{int(seed)}" for seed in contract["primary_model"]["random_seeds"])
    return output
