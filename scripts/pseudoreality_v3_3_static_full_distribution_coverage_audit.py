#!/usr/bin/env python3
"""Independent coverage audit for Task 3.1e persisted artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from pseudoreality_v3_3_static_full_distribution_testbed import (
    DEFAULT_CONFIG,
    EXTERNAL_COLUMNS,
    OUT_SUBDIR,
    js_distances,
    load_config,
)


def _artifact_dir(root: str | Path) -> Path:
    path = Path(root)
    return path if path.name == OUT_SUBDIR else path / OUT_SUBDIR


def _minimum_distances(evaluation: np.ndarray, references: np.ndarray) -> np.ndarray:
    return np.asarray(
        [float(js_distances(references, candidate).min()) for candidate in evaluation], dtype=np.float64
    )


def _stats(stage: str, evaluation: np.ndarray, references: np.ndarray) -> dict[str, Any]:
    distances = _minimum_distances(evaluation, references)
    return {
        "coverage_stage": stage,
        "evaluation_count": int(evaluation.shape[0]),
        "reference_count": int(references.shape[0]),
        "nearest_neighbor_js_min": float(np.min(distances)),
        "nearest_neighbor_js_median": float(np.median(distances)),
        "nearest_neighbor_js_p95": float(np.quantile(distances, 0.95)),
        "nearest_neighbor_js_max": float(np.max(distances)),
    }


def _canonical_reference_masses(
    artifact_dir: Path, profile_config: dict[str, Any]
) -> tuple[pd.DataFrame, np.ndarray]:
    vectors = pd.read_csv(artifact_dir / "external_vectors.csv")
    metadata = pd.read_csv(artifact_dir / "snapshot_metadata.csv")
    mass_matrix = np.load(artifact_dir / "mass_matrix.npy", allow_pickle=False)
    reference_seed = int(profile_config["adaptive_reference_seed"])
    reference_step = int(profile_config["adaptive_reference_step"])
    initial_fit = vectors[
        (vectors["dataset_split"] == "fit")
        & (~vectors["is_base_vector"].astype(bool))
        & (vectors["vector_origin"] != "adaptive_maximin")
    ].copy()
    rows: list[int] = []
    for vector_id in initial_fit["external_vector_id"]:
        matched = metadata[
            (metadata["external_vector_id"] == vector_id)
            & (metadata["seed"] == reference_seed)
            & (metadata["source_step"] == reference_step)
        ]
        if len(matched) != 1:
            raise ValueError(f"expected exactly one canonical snapshot for {vector_id}, found {len(matched)}")
        rows.append(int(matched.iloc[0]["matrix_row_index"]))
    return initial_fit, np.asarray(mass_matrix[rows], dtype=np.float64)


def replay_selection(
    artifact_dir: Path,
    profile_config: dict[str, Any],
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray, list[dict[str, Any]]]:
    pool = pd.read_csv(artifact_dir / "adaptive_pool.csv")
    pool_masses = np.load(artifact_dir / "adaptive_pool_mass_matrix.npy", allow_pickle=False)
    additions = pd.read_csv(artifact_dir / "coverage_additions.csv")
    _, references = _canonical_reference_masses(artifact_dir, profile_config)
    if pool_masses.shape[0] != len(pool):
        raise ValueError("adaptive pool metadata and mass rows differ")
    selected_count = int(profile_config["adaptive_selected_count"])
    if len(additions) != selected_count:
        raise ValueError(f"coverage_additions has {len(additions)} rows; expected {selected_count}")

    minimum_distances = _minimum_distances(pool_masses, references)
    remaining = list(range(len(pool)))
    replayed: list[dict[str, Any]] = []
    selected_indices: list[int] = []
    for rank in range(1, selected_count + 1):
        best_distance = max(float(minimum_distances[index]) for index in remaining)
        tied = [index for index in remaining if float(minimum_distances[index]) == best_distance]
        best_index = min(tied, key=lambda index: str(pool.iloc[index]["candidate_pool_id"]))
        replayed.append(
            {
                "selection_rank": rank,
                "candidate_pool_id": str(pool.iloc[best_index]["candidate_pool_id"]),
                "minimum_js_distance_at_selection": best_distance,
            }
        )
        selected_indices.append(best_index)
        remaining.remove(best_index)
        if remaining:
            new_distances = js_distances(pool_masses[remaining], pool_masses[best_index])
            for local_index, candidate_index in enumerate(remaining):
                minimum_distances[candidate_index] = min(
                    minimum_distances[candidate_index], float(new_distances[local_index])
                )

    additions_sorted = additions.sort_values("selection_rank").reset_index(drop=True)
    for expected, actual in zip(replayed, additions_sorted.to_dict(orient="records")):
        if int(actual["selection_rank"]) != expected["selection_rank"]:
            raise ValueError("adaptive selection rank mismatch")
        if str(actual["candidate_pool_id"]) != expected["candidate_pool_id"]:
            raise ValueError(
                f"adaptive selection mismatch at rank {expected['selection_rank']}: "
                f"expected {expected['candidate_pool_id']}, got {actual['candidate_pool_id']}"
            )
        if not np.isclose(
            float(actual["minimum_js_distance_at_selection"]),
            expected["minimum_js_distance_at_selection"],
            rtol=0.0,
            atol=1e-12,
        ):
            raise ValueError(f"adaptive selection distance mismatch at rank {expected['selection_rank']}")
        pool_row = pool[pool["candidate_pool_id"] == expected["candidate_pool_id"]]
        if len(pool_row) != 1:
            raise ValueError("candidate_pool_id is not unique")
        for column in EXTERNAL_COLUMNS:
            if not np.isclose(float(actual[column]), float(pool_row.iloc[0][column]), rtol=0.0, atol=1e-12):
                raise ValueError(f"adaptive selected value mismatch for {column}")
    return pool, pool_masses, references, replayed


def compute_coverage_summary(
    artifact_root: str | Path,
    profile: str,
    config_path: str | Path = DEFAULT_CONFIG,
) -> pd.DataFrame:
    _, profile_config = load_config(config_path, profile)
    artifact_dir = _artifact_dir(artifact_root)
    pool, pool_masses, references, replayed = replay_selection(artifact_dir, profile_config)
    selected_ids = [item["candidate_pool_id"] for item in replayed]
    index_by_id = {str(row.candidate_pool_id): index for index, row in pool.iterrows()}
    selected_indices = [index_by_id[candidate_id] for candidate_id in selected_ids]
    after_references = np.vstack([references, pool_masses[selected_indices]])
    rows = [
        _stats("before_adaptive", pool_masses, references),
        _stats("after_adaptive", pool_masses, after_references),
    ]
    return pd.DataFrame(rows)


def run_audit(
    artifact_root: str | Path,
    profile: str,
    config_path: str | Path = DEFAULT_CONFIG,
) -> Path:
    artifact_dir = _artifact_dir(artifact_root)
    summary = compute_coverage_summary(artifact_dir, profile, config_path)
    output = artifact_dir / "coverage_summary.csv"
    summary.to_csv(output, index=False)
    replay_info = {
        "profile": profile,
        "selection_replayed": True,
        "coverage_rows": int(len(summary)),
    }
    (artifact_dir / "coverage_audit_metadata.json").write_text(
        json.dumps(replay_info, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=("smoke", "formal"), required=True)
    parser.add_argument("--artifact-root", default="artifacts")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args()
    print(run_audit(args.artifact_root, args.profile, args.config))


if __name__ == "__main__":
    main()
