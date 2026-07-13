from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .common import TARGET_RANKS
from .cross_rank import _native_signature_similarity
from .matching import _normalize_basis, best_group_match
from .native import _activation_consistency
from .subsets import _weighted_mean_js


def _subset_stability_tables(
    output_root: Path,
    model_records: dict[tuple[int, str], dict[str, Any]],
    representatives: dict[int, dict[str, Any]],
    validation: np.ndarray,
    validation_weights: np.ndarray,
    task_contract: dict[str, Any],
    n_bins: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    matching = task_contract["group_matching"]
    match_rows: list[dict[str, Any]] = []
    signature_rows: list[dict[str, Any]] = []
    activation_rows: list[dict[str, Any]] = []
    diagnostic_rows: list[dict[str, Any]] = []
    for rank in TARGET_RANKS:
        representative = representatives[rank]
        rank_records = [(subset_id, record) for (record_rank, subset_id), record in model_records.items() if record_rank == rank]
        for subset_id, record in sorted(rank_records):
            basis = _normalize_basis(np.load(output_root / record["basis_path"], allow_pickle=False))
            fit_activations = np.load(output_root / record["fit_activation_path"], allow_pickle=False)
            validation_activations = np.load(output_root / record["validation_activation_path"], allow_pickle=False)
            similarities: list[float] = []
            for source_index, source_structure in enumerate(representative["basis"]):
                match = best_group_match(
                    source_structure,
                    basis,
                    source_index=source_index,
                    max_group_size=int(matching["max_group_size"]),
                    similarity_threshold=float(matching["similarity_threshold"]),
                    intermediate_threshold=float(matching["intermediate_threshold"]),
                    minimum_weight=float(matching["minimum_member_weight"]),
                    beam_width=int(matching["beam_width"]),
                )
                similarities.append(match.js_similarity)
                mixture = np.asarray(match.weights) @ basis[list(match.target_indices)]
                mixture /= mixture.sum(dtype=np.float64)
                marginal_similarity, pair_similarity = _native_signature_similarity(source_structure, mixture, n_bins)
                source_structure_id = f"R{rank:02d}-S{source_index + 1:03d}"
                match_rows.append(
                    {
                        "rank": rank,
                        "subset_id": subset_id,
                        "source_structure_id": source_structure_id,
                        "group_size": len(match.target_indices),
                        "target_indices_json": json.dumps(list(match.target_indices)),
                        "weights_json": json.dumps(list(match.weights)),
                        "js_distance": match.js_distance,
                        "js_similarity": match.js_similarity,
                        "cosine_similarity": match.cosine_similarity,
                        "classification": match.classification,
                        "survived_group_threshold": match.js_similarity >= float(matching["similarity_threshold"]),
                    }
                )
                signature_rows.append(
                    {
                        "rank": rank,
                        "subset_id": subset_id,
                        "source_structure_id": source_structure_id,
                        "native_axis_marginal_similarity_mean": marginal_similarity,
                        "native_axis_pairwise_similarity_mean": pair_similarity,
                    }
                )
                activation_rows.append(
                    {
                        "rank": rank,
                        "subset_id": subset_id,
                        "source_structure_id": source_structure_id,
                        **_activation_consistency(
                            representative["fit_activations"][
                                np.asarray(record["included_row_indices"], dtype=np.int64), source_index
                            ],
                            representative["validation_activations"][:, source_index],
                            fit_activations,
                            validation_activations,
                            match.target_indices,
                        ),
                    }
                )
            diagnostic_rows.append(
                {
                    "rank": rank,
                    "subset_id": subset_id,
                    "model_status": "completed",
                    "converged": bool(record.get("converged", False)),
                    "reused_rank5_source_model": bool(record.get("reused_rank5_source_model", False)),
                    "median_group_similarity": float(np.median(similarities)),
                    "group_surviving_component_fraction": float(
                        np.mean(np.asarray(similarities) >= float(matching["similarity_threshold"]))
                    ),
                    "validation_weighted_mean_js": _weighted_mean_js(
                        validation, validation_activations, basis, validation_weights
                    ),
                    "basis_path": record["basis_path"],
                    "basis_sha256": record["basis_sha256"],
                }
            )
    return (
        pd.DataFrame(diagnostic_rows),
        pd.DataFrame(match_rows),
        pd.DataFrame(signature_rows),
        pd.DataFrame(activation_rows),
    )


def _aggregate_stability(
    rank_summary: pd.DataFrame,
    seed_matches: pd.DataFrame,
    subset_matches: pd.DataFrame,
    subset_diagnostics: pd.DataFrame,
    task_contract: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame, list[dict[str, Any]]]:
    threshold = float(task_contract["group_matching"]["similarity_threshold"])
    required_subset_count = int(task_contract["stability"]["required_subset_survival_count"])
    seed_survival_rate = float(task_contract["stability"]["seed_survival_rate"])
    rows: list[dict[str, Any]] = []
    operational_rows: list[dict[str, Any]] = []
    recommendations: list[dict[str, Any]] = []
    base_error = float(rank_summary[rank_summary["rank"] == 5].iloc[0]["validation_weighted_mean_js"])
    previous_error: float | None = None
    for rank in TARGET_RANKS:
        summary = rank_summary[rank_summary["rank"] == rank].iloc[0]
        rank_seed = seed_matches[seed_matches["rank"] == rank]
        compare_count = int(rank_seed["comparison_run_id"].nunique()) if not rank_seed.empty else 0
        seed_component_rates: list[float] = []
        if compare_count > 0:
            for _, group in rank_seed.groupby("source_structure_id"):
                seed_component_rates.append(float(np.mean(group["js_similarity"].to_numpy(dtype=float) >= threshold)))
        seed_group_stable_fraction = float(np.mean(np.asarray(seed_component_rates) >= seed_survival_rate)) if seed_component_rates else 0.0
        seed_group_median = float(rank_seed["js_similarity"].median()) if not rank_seed.empty else 0.0
        rank_subset = subset_matches[subset_matches["rank"] == rank]
        subset_component_counts: list[int] = []
        if not rank_subset.empty:
            for _, group in rank_subset.groupby("source_structure_id"):
                subset_component_counts.append(int(np.sum(group["js_similarity"].to_numpy(dtype=float) >= threshold)))
        subset_group_stable_fraction = float(np.mean(np.asarray(subset_component_counts) >= required_subset_count)) if subset_component_counts else 0.0
        subset_group_median = float(rank_subset["js_similarity"].median()) if not rank_subset.empty else 0.0
        rank_subset_diag = subset_diagnostics[subset_diagnostics["rank"] == rank]
        subset_converged_count = int(rank_subset_diag["converged"].sum()) if not rank_subset_diag.empty else 0
        validation_error = float(summary["validation_weighted_mean_js"])
        improvement_from_rank5 = (base_error - validation_error) / base_error
        previous_improvement = None if previous_error is None else (previous_error - validation_error) / previous_error
        rows.append(
            {
                "rank": rank,
                "validation_weighted_mean_js": validation_error,
                "mean_baseline_improvement_rate": float(summary["mean_baseline_improvement_rate"]),
                "improvement_from_rank5": improvement_from_rank5,
                "improvement_from_previous_target_rank": previous_improvement,
                "improvement_per_added_structure_from_rank5": improvement_from_rank5 / max(rank - 5, 1),
                "original_one_to_one_median_similarity": float(summary["median_matched_js_similarity"]),
                "original_one_to_one_stable_component_fraction": float(summary["stable_component_fraction"]),
                "seed_group_comparison_run_count": compare_count,
                "seed_group_median_similarity": seed_group_median,
                "seed_group_stable_component_fraction": seed_group_stable_fraction,
                "subset_group_median_similarity": subset_group_median,
                "subset_group_stable_component_fraction": subset_group_stable_fraction,
                "subset_converged_count": subset_converged_count,
                "evidence_limited": compare_count < int(task_contract["stability"]["minimum_seed_comparison_runs"]),
            }
        )
        roles: list[str] = []
        reasons: list[str] = []
        if rank == 5:
            roles.append("compact_macro_candidate")
            reasons.append("lowest-rank macro reference")
        if (
            compare_count >= int(task_contract["stability"]["minimum_seed_comparison_runs"])
            and seed_group_stable_fraction >= 0.80
            and subset_group_stable_fraction >= 0.80
            and seed_group_median >= 0.80
            and subset_group_median >= 0.80
        ):
            roles.append("normal_operation_dictionary_candidate")
            reasons.append("group stability is strong across seeds and grouped subsets")
        elif improvement_from_rank5 >= 0.10 and subset_group_median >= 0.75:
            roles.append("conditional_dictionary_candidate")
            reasons.append("information retention improves but stability evidence remains conditional")
        else:
            roles.append("diagnostic_only")
            reasons.append("insufficient group-stability evidence for fixed operation")
        if rank == 15 and improvement_from_rank5 >= 0.15:
            roles.append("detailed_dictionary_candidate")
            reasons.append("high-detail rank retains substantially more validation information than rank 5")
        operational_rows.append(
            {
                "rank": rank,
                "roles_json": json.dumps(roles),
                "reasons_json": json.dumps(reasons),
                "automatic_selection": False,
                "holdout_accessed": False,
            }
        )
        recommendations.append(
            {
                "rank": rank,
                "roles": roles,
                "reasons": reasons,
                "automatic_selection": False,
                "metrics": rows[-1],
            }
        )
        previous_error = validation_error
    return pd.DataFrame(rows), pd.DataFrame(operational_rows), recommendations
