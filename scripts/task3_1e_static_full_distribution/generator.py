"""Raw artifact generation for Task 3.1e."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from itertools import product
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .core import (
    DEFAULT_CONFIG, EXTERNAL_COLUMNS, OUT_SUBDIR, TERRAIN_FIELDS,
    build_adaptive_pool, build_initial_vectors, load_config,
)
from .runtime import (
    _adaptive_pool_rows, _assign_selected_vectors, _external_vector_rows,
    canonical_mass, capture_run, select_adaptive_candidates, snapshot_id,
    source_run_id, write_csv,
)


def build(profile: str, output_root: str | Path, config_path: str | Path = DEFAULT_CONFIG) -> Path:
    config, profile_config = load_config(config_path, profile)
    n_bins = int(config["n_bins"])
    cell_count = int(config["cell_count"])
    capture_policy = str(config["capture_policy"])
    output_dir = Path(output_root) / OUT_SUBDIR
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)

    initial = build_initial_vectors(profile_config)
    pool = build_adaptive_pool(initial, profile_config)
    selected_count = int(profile_config["adaptive_selected_count"])
    reference_seed = int(profile_config["adaptive_reference_seed"])
    reference_step = int(profile_config["adaptive_reference_step"])
    initial_fit_nonbase = [v for v in initial["fit"] if not v.is_base_vector]
    reference_masses = np.vstack([
        canonical_mass(reference_seed, reference_step, v.values, n_bins, cell_count)
        for v in initial_fit_nonbase
    ]).astype(np.float64)
    candidate_masses = np.vstack([
        canonical_mass(reference_seed, reference_step, c.values, n_bins, cell_count)
        for c in pool
    ]).astype(np.float64)
    selected = select_adaptive_candidates(pool, candidate_masses, reference_masses, selected_count)
    selected_vectors = _assign_selected_vectors(initial["fit"], selected)
    initial["fit"] = initial["fit"] + selected_vectors
    vectors = initial["fit"] + initial["validation"] + initial["holdout"]

    external_rows = _external_vector_rows(vectors)
    write_csv(output_dir / "external_vectors.csv", external_rows, external_rows[0].keys())
    pool_rows = _adaptive_pool_rows(pool)
    write_csv(output_dir / "adaptive_pool.csv", pool_rows, pool_rows[0].keys())
    np.save(output_dir / "adaptive_pool_mass_matrix.npy", candidate_masses)

    additions: list[dict[str, Any]] = []
    assigned_by_rank = {v.adaptive_selection_rank: v for v in selected_vectors}
    for item in selected:
        vector = assigned_by_rank[item.selection_rank]
        row: dict[str, Any] = {
            "selection_rank": item.selection_rank,
            "external_vector_id": vector.external_vector_id,
            "candidate_pool_id": item.candidate.candidate_pool_id,
            "active_factor_count": item.candidate.active_factor_count,
            "mask_bits": item.candidate.mask_bits,
            "minimum_js_distance_at_selection": item.minimum_js_distance_at_selection,
        }
        row.update(dict(zip(EXTERNAL_COLUMNS, item.candidate.values)))
        additions.append(row)
    write_csv(output_dir / "coverage_additions.csv", additions, additions[0].keys())

    masses: list[np.ndarray] = []
    terrain_rows: dict[str, list[np.ndarray]] = {field: [] for field in TERRAIN_FIELDS}
    metadata_rows: list[dict[str, Any]] = []
    discovery_rows: list[dict[str, Any]] = []
    matched_pairs: list[dict[str, Any]] = []
    base_lookup: dict[tuple[str, int, int], str] = {}
    matrix_row_index = 0
    base_steps = profile_config["capture_steps"]["base"]
    external_steps = profile_config["capture_steps"]["external"]
    world_seeds = profile_config["world_seeds"]

    for split in ("fit", "validation", "holdout"):
        base_vector = next(v for v in initial[split] if v.is_base_vector)
        for seed in world_seeds[split]:
            captures = capture_run(seed=int(seed), values=base_vector.values, capture_steps=base_steps, n_bins=n_bins, cell_count=cell_count)
            run_id = source_run_id(capture_policy, split, base_vector.external_vector_id, int(seed))
            for step in base_steps:
                mass, terrain = captures[int(step)]
                sid = snapshot_id(capture_policy, split, base_vector.external_vector_id, int(seed), int(step))
                base_lookup[(split, int(seed), int(step))] = sid
                masses.append(mass)
                for field in TERRAIN_FIELDS:
                    terrain_rows[field].append(terrain[field])
                metadata_rows.append({
                    "matrix_row_index": matrix_row_index, "snapshot_id": sid,
                    "source_run_id": run_id, "dataset_split": split,
                    "distribution_group": "base_v3_3", "seed": int(seed),
                    "source_step": int(step), "capture_policy": capture_policy,
                    "external_vector_id": base_vector.external_vector_id,
                    "active_factor_count": 0, "matched_base_snapshot_id": sid,
                    "mass_sum": float(mass.sum(dtype=np.float64)),
                    "min_mass": float(mass.min()), "max_mass": float(mass.max()),
                })
                discovery_rows.append({
                    "matrix_row_index": matrix_row_index, "snapshot_id": sid,
                    "dataset_split": split, "analysis_weight": 1.0,
                })
                matrix_row_index += 1

    for vector in [v for v in vectors if not v.is_base_vector]:
        split = vector.dataset_split
        for seed in world_seeds[split]:
            captures = capture_run(seed=int(seed), values=vector.values, capture_steps=external_steps, n_bins=n_bins, cell_count=cell_count)
            run_id = source_run_id(capture_policy, split, vector.external_vector_id, int(seed))
            for step in external_steps:
                mass, terrain = captures[int(step)]
                sid = snapshot_id(capture_policy, split, vector.external_vector_id, int(seed), int(step))
                base_sid = base_lookup[(split, int(seed), int(step))]
                masses.append(mass)
                for field in TERRAIN_FIELDS:
                    terrain_rows[field].append(terrain[field])
                metadata_rows.append({
                    "matrix_row_index": matrix_row_index, "snapshot_id": sid,
                    "source_run_id": run_id, "dataset_split": split,
                    "distribution_group": "external_augmented", "seed": int(seed),
                    "source_step": int(step), "capture_policy": capture_policy,
                    "external_vector_id": vector.external_vector_id,
                    "active_factor_count": vector.active_factor_count,
                    "matched_base_snapshot_id": base_sid,
                    "mass_sum": float(mass.sum(dtype=np.float64)),
                    "min_mass": float(mass.min()), "max_mass": float(mass.max()),
                })
                discovery_rows.append({
                    "matrix_row_index": matrix_row_index, "snapshot_id": sid,
                    "dataset_split": split, "analysis_weight": 1.0,
                })
                matched_pairs.append({
                    "external_snapshot_id": sid, "base_snapshot_id": base_sid,
                    "dataset_split": split, "seed": int(seed),
                    "source_step": int(step), "pair_quality": "exact",
                })
                matrix_row_index += 1

    mass_matrix = np.vstack(masses).astype(np.float64)
    np.save(output_dir / "mass_matrix.npy", mass_matrix)
    np.savez(output_dir / "terrain_reference.npz", **{
        field: np.vstack(rows).astype(np.float32) for field, rows in terrain_rows.items()
    })
    metadata = pd.DataFrame(metadata_rows)
    discovery = pd.DataFrame(discovery_rows)
    group_columns = ["dataset_split", "distribution_group", "active_factor_count", "source_step"]
    group_counts = metadata.groupby(group_columns)["snapshot_id"].transform("count")
    weights = 1.0 / group_counts.astype(np.float64)
    for split in metadata["dataset_split"].unique():
        selector = metadata["dataset_split"] == split
        weights.loc[selector] = weights.loc[selector] / float(weights.loc[selector].mean())
    discovery["analysis_weight"] = weights.to_numpy(dtype=np.float64)
    metadata.to_csv(output_dir / "snapshot_metadata.csv", index=False)
    discovery.to_csv(output_dir / "discovery_manifest.csv", index=False)
    write_csv(output_dir / "matched_pairs.csv", matched_pairs, [
        "external_snapshot_id", "base_snapshot_id", "dataset_split", "seed",
        "source_step", "pair_quality",
    ])

    coordinates: list[dict[str, Any]] = []
    for cell_id, bins in enumerate(product(range(n_bins), repeat=int(config["axis_count"]))):
        row: dict[str, Any] = {"cell_id": cell_id}
        row.update({f"dim{d}_bin": bins[d] for d in range(int(config["axis_count"]))})
        row.update({f"dim{d}_value": bins[d] / (n_bins - 1) for d in range(int(config["axis_count"]))})
        coordinates.append(row)
    write_csv(output_dir / "cell_coordinates.csv", coordinates, coordinates[0].keys())
    terrain_catalog = [{
        "field_name": field, "storage_dtype": "float32",
        "reference_class": "stateful_reference" if field in {"information_memory", "viability_reserve", "route_support"} else "instantaneous_terrain",
        "included_in_discovery": False,
    } for field in TERRAIN_FIELDS]
    write_csv(output_dir / "terrain_field_catalog.csv", terrain_catalog, [
        "field_name", "storage_dtype", "reference_class", "included_in_discovery",
    ])
    generation_metadata = {
        "profile": profile,
        "config_sha256": hashlib.sha256(Path(config_path).read_bytes()).hexdigest(),
        "capture_policy": capture_policy,
        "axis_count": int(config["axis_count"]), "n_bins": n_bins,
        "cell_count": cell_count, "external_vector_count": len(vectors),
        "adaptive_pool_count": len(pool), "adaptive_selected_count": len(selected),
        "snapshot_count": int(mass_matrix.shape[0]),
    }
    (output_dir / "generation_metadata.json").write_text(
        json.dumps(generation_metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return output_dir


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=("smoke", "formal"), required=True)
    parser.add_argument("--output-root", default="artifacts")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args()
    print(build(args.profile, args.output_root, args.config))
