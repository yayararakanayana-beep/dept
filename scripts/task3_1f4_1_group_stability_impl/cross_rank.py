from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .common import AXIS_NAMES, CROSS_RANK_PAIRS, TARGET_RANKS, sha256_file
from .matching import _cosine, _js_similarity, _normalize_basis, best_group_match
from .native import _activation_consistency, _axis_marginal, _pair_joint


def _load_representatives(source_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict[int, dict[str, Any]]]:
    runs = pd.read_csv(source_root / "model_runs.csv")
    rank_summary = pd.read_csv(source_root / "rank_summary.csv")
    representatives: dict[int, dict[str, Any]] = {}
    for rank in TARGET_RANKS:
        summary_rows = rank_summary[rank_summary["rank"] == rank]
        if len(summary_rows) != 1:
            raise ValueError(f"rank {rank} summary is missing")
        run_id = str(summary_rows.iloc[0]["representative_run_id"])
        run_rows = runs[runs["run_id"] == run_id]
        if len(run_rows) != 1:
            raise ValueError(f"representative run {run_id} is missing")
        row = run_rows.iloc[0]
        basis_path = source_root / str(row["basis_path"])
        fit_activation_path = source_root / str(row["fit_activation_path"])
        validation_activation_path = source_root / str(row["validation_activation_path"])
        for path, hash_column in (
            (basis_path, "basis_sha256"),
            (fit_activation_path, "fit_activation_sha256"),
            (validation_activation_path, "validation_activation_sha256"),
        ):
            if sha256_file(path) != str(row[hash_column]):
                raise ValueError(f"representative file hash mismatch: {path}")
        representatives[rank] = {
            "rank": rank,
            "run_id": run_id,
            "basis": _normalize_basis(np.load(basis_path, allow_pickle=False)),
            "fit_activations": np.load(fit_activation_path, allow_pickle=False),
            "validation_activations": np.load(validation_activation_path, allow_pickle=False),
            "run_row": row.to_dict(),
            "summary_row": summary_rows.iloc[0].to_dict(),
        }
    return runs, rank_summary, representatives


def _native_signature_similarity(source: np.ndarray, target: np.ndarray, n_bins: int) -> tuple[float, float]:
    marginal_similarities = []
    pair_similarities = []
    for axis_index in range(len(AXIS_NAMES)):
        _, similarity = _js_similarity(
            _axis_marginal(source, axis_index, n_bins),
            _axis_marginal(target, axis_index, n_bins),
        )
        marginal_similarities.append(similarity)
    for axis_a, axis_b in itertools.combinations(range(len(AXIS_NAMES)), 2):
        _, similarity = _js_similarity(
            _pair_joint(source, axis_a, axis_b, n_bins).reshape(-1),
            _pair_joint(target, axis_a, axis_b, n_bins).reshape(-1),
        )
        pair_similarities.append(similarity)
    return float(np.mean(marginal_similarities)), float(np.mean(pair_similarities))


def _cross_rank_tables(
    representatives: dict[int, dict[str, Any]],
    task_contract: dict[str, Any],
    n_bins: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    single_rows: list[dict[str, Any]] = []
    group_rows: list[dict[str, Any]] = []
    member_rows: list[dict[str, Any]] = []
    activation_rows: list[dict[str, Any]] = []
    matching = task_contract["group_matching"]
    for source_rank, target_rank in CROSS_RANK_PAIRS:
        source_data = representatives[source_rank]
        target_data = representatives[target_rank]
        source_basis = source_data["basis"]
        target_basis = target_data["basis"]
        for source_index, source_structure in enumerate(source_basis):
            individual = []
            for target_index, target_structure in enumerate(target_basis):
                distance, similarity = _js_similarity(source_structure, target_structure)
                individual.append((similarity, target_index, distance, _cosine(source_structure, target_structure)))
            individual.sort(key=lambda value: (-value[0], value[1]))
            best_single = individual[0]
            single_rows.append(
                {
                    "source_rank": source_rank,
                    "target_rank": target_rank,
                    "source_run_id": source_data["run_id"],
                    "target_run_id": target_data["run_id"],
                    "source_structure_id": f"R{source_rank:02d}-S{source_index + 1:03d}",
                    "source_basis_row_index": source_index,
                    "target_structure_id": f"R{target_rank:02d}-S{best_single[1] + 1:03d}",
                    "target_basis_row_index": best_single[1],
                    "js_distance": best_single[2],
                    "js_similarity": best_single[0],
                    "cosine_similarity": best_single[3],
                }
            )
            match = best_group_match(
                source_structure,
                target_basis,
                source_index=source_index,
                max_group_size=int(matching["max_group_size"]),
                similarity_threshold=float(matching["similarity_threshold"]),
                intermediate_threshold=float(matching["intermediate_threshold"]),
                minimum_weight=float(matching["minimum_member_weight"]),
                beam_width=int(matching["beam_width"]),
            )
            mixture = np.asarray(match.weights) @ target_basis[list(match.target_indices)]
            mixture /= mixture.sum(dtype=np.float64)
            marginal_similarity, pair_similarity = _native_signature_similarity(source_structure, mixture, n_bins)
            group_id = f"R{source_rank:02d}-S{source_index + 1:03d}__to__R{target_rank:02d}"
            group_rows.append(
                {
                    "group_id": group_id,
                    "source_rank": source_rank,
                    "target_rank": target_rank,
                    "source_run_id": source_data["run_id"],
                    "target_run_id": target_data["run_id"],
                    "source_structure_id": f"R{source_rank:02d}-S{source_index + 1:03d}",
                    "source_basis_row_index": source_index,
                    "group_size": len(match.target_indices),
                    "target_indices_json": json.dumps(list(match.target_indices)),
                    "weights_json": json.dumps(list(match.weights)),
                    "js_distance": match.js_distance,
                    "js_similarity": match.js_similarity,
                    "cosine_similarity": match.cosine_similarity,
                    "classification": match.classification,
                    "native_axis_marginal_similarity_mean": marginal_similarity,
                    "native_axis_pairwise_similarity_mean": pair_similarity,
                }
            )
            for member_order, (target_index, weight) in enumerate(zip(match.target_indices, match.weights), start=1):
                member_rows.append(
                    {
                        "group_id": group_id,
                        "member_order": member_order,
                        "target_structure_id": f"R{target_rank:02d}-S{target_index + 1:03d}",
                        "target_basis_row_index": target_index,
                        "weight": weight,
                    }
                )
            activation_rows.append(
                {
                    "group_id": group_id,
                    "source_rank": source_rank,
                    "target_rank": target_rank,
                    "source_structure_id": f"R{source_rank:02d}-S{source_index + 1:03d}",
                    **_activation_consistency(
                        source_data["fit_activations"][:, source_index],
                        source_data["validation_activations"][:, source_index],
                        target_data["fit_activations"],
                        target_data["validation_activations"],
                        match.target_indices,
                    ),
                }
            )
    return pd.DataFrame(single_rows), pd.DataFrame(group_rows), pd.DataFrame(member_rows), pd.DataFrame(activation_rows)


def _seed_stability_tables(
    source_root: Path,
    runs: pd.DataFrame,
    representatives: dict[int, dict[str, Any]],
    task_contract: dict[str, Any],
    n_bins: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    matching = task_contract["group_matching"]
    rows: list[dict[str, Any]] = []
    signature_rows: list[dict[str, Any]] = []
    for rank in TARGET_RANKS:
        representative = representatives[rank]
        rank_runs = runs[
            (runs["rank"] == rank)
            & (runs["method"] == "nmf_kl")
            & (runs["status"] == "completed")
            & (runs["converged"] == True)
            & (runs["run_id"] != representative["run_id"])
        ]
        for run in rank_runs.itertuples(index=False):
            target_basis = _normalize_basis(np.load(source_root / str(run.basis_path), allow_pickle=False))
            target_fit = np.load(source_root / str(run.fit_activation_path), allow_pickle=False)
            target_validation = np.load(source_root / str(run.validation_activation_path), allow_pickle=False)
            for source_index, source_structure in enumerate(representative["basis"]):
                match = best_group_match(
                    source_structure,
                    target_basis,
                    source_index=source_index,
                    max_group_size=int(matching["max_group_size"]),
                    similarity_threshold=float(matching["similarity_threshold"]),
                    intermediate_threshold=float(matching["intermediate_threshold"]),
                    minimum_weight=float(matching["minimum_member_weight"]),
                    beam_width=int(matching["beam_width"]),
                )
                mixture = np.asarray(match.weights) @ target_basis[list(match.target_indices)]
                mixture /= mixture.sum(dtype=np.float64)
                marginal_similarity, pair_similarity = _native_signature_similarity(source_structure, mixture, n_bins)
                source_structure_id = f"R{rank:02d}-S{source_index + 1:03d}"
                rows.append(
                    {
                        "rank": rank,
                        "representative_run_id": representative["run_id"],
                        "comparison_run_id": str(run.run_id),
                        "source_structure_id": source_structure_id,
                        "comparison_count_evidence": len(rank_runs),
                        "group_size": len(match.target_indices),
                        "target_indices_json": json.dumps(list(match.target_indices)),
                        "weights_json": json.dumps(list(match.weights)),
                        "js_similarity": match.js_similarity,
                        "classification": match.classification,
                        **_activation_consistency(
                            representative["fit_activations"][:, source_index],
                            representative["validation_activations"][:, source_index],
                            target_fit,
                            target_validation,
                            match.target_indices,
                        ),
                    }
                )
                signature_rows.append(
                    {
                        "rank": rank,
                        "representative_run_id": representative["run_id"],
                        "comparison_run_id": str(run.run_id),
                        "source_structure_id": source_structure_id,
                        "native_axis_marginal_similarity_mean": marginal_similarity,
                        "native_axis_pairwise_similarity_mean": pair_similarity,
                    }
                )
    seed_columns = [
        "rank", "representative_run_id", "comparison_run_id", "source_structure_id",
        "comparison_count_evidence", "group_size", "target_indices_json", "weights_json",
        "js_similarity", "classification", "fit_coefficient_sum",
        "validation_weighted_pearson", "validation_unweighted_pearson",
        "validation_spearman", "validation_cosine", "validation_normalized_mae",
        "validation_p95_absolute_error", "validation_top10_overlap", "fit_pearson",
    ]
    signature_columns = [
        "rank", "representative_run_id", "comparison_run_id", "source_structure_id",
        "native_axis_marginal_similarity_mean", "native_axis_pairwise_similarity_mean",
    ]
    return pd.DataFrame(rows, columns=seed_columns), pd.DataFrame(signature_rows, columns=signature_columns)
