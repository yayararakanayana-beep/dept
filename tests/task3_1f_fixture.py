from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


def build_smoke_task3_1e_artifact(root: Path) -> Path:
    artifact = root / "pseudoreality_v3_3_task3_1e_static_full_distribution"
    artifact.mkdir(parents=True, exist_ok=False)
    rng = np.random.default_rng(12345)
    cell_count = 3125
    latent = rng.gamma(shape=1.5, scale=1.0, size=(5, cell_count))
    latent /= latent.sum(axis=1, keepdims=True)

    vector_rows = []
    split_vector_counts = {"fit": 11, "validation": 3, "holdout": 5}
    base_vector_ids = {}
    for split, count in split_vector_counts.items():
        for index in range(count):
            vector_id = f"vec_{split}_{index + 1:06d}"
            is_base = index == count - 1
            if is_base:
                base_vector_ids[split] = vector_id
            vector_rows.append({
                "external_vector_id": vector_id,
                "dataset_split": split,
                "vector_origin": "base" if is_base else ("sobol_stratified" if split != "holdout" else "boundary_corner"),
                "mask_bits": "000000" if is_base else "111111",
                "active_factor_count": 0 if is_base else 6,
                "is_base_vector": is_base,
                "sobol_scramble_seed": np.nan if is_base else 3101,
                "sobol_index": np.nan if is_base else index,
                "candidate_pool_id": np.nan,
                "adaptive_selection_rank": np.nan,
                "external_resource_supply": 0.0 if is_base else float(rng.uniform(-1, 1)),
                "external_demand": 0.0 if is_base else float(rng.uniform(-1, 1)),
                "external_competition_pressure": 0.0 if is_base else float(rng.uniform()),
                "external_information_noise": 0.0 if is_base else float(rng.uniform()),
                "external_shock": 0.0 if is_base else float(rng.uniform()),
                "external_constraint_pressure": 0.0 if is_base else float(rng.uniform()),
            })
    pd.DataFrame(vector_rows).to_csv(artifact / "external_vectors.csv", index=False)

    rows = []
    discovery = []
    pairs = []
    masses = []
    row_index = 0
    split_nonbase_vectors = {"fit": 10, "validation": 2, "holdout": 4}
    split_seed = {"fit": 0, "validation": 10, "holdout": 20}
    base_lookup = {}

    def make_mass(split_index: int, step: int, vector_index: int, is_base: bool) -> np.ndarray:
        coefficients = np.array([
            1.0 + 0.12 * split_index,
            0.7 + 0.08 * step,
            0.45 + 0.04 * vector_index,
            0.35 + (0.0 if is_base else 0.2),
            0.2 + 0.03 * ((vector_index + step) % 5),
        ])
        noise = rng.gamma(shape=1.0, scale=1e-5, size=cell_count)
        mass = coefficients @ latent + noise
        mass /= mass.sum(dtype=np.float64)
        return mass.astype(np.float64)

    for split_index, split in enumerate(("fit", "validation", "holdout")):
        seed = split_seed[split]
        base_vector = base_vector_ids[split]
        run_id = f"run_{split}_base"
        for step in (0, 1, 2):
            snapshot_id = f"snap_{split}_base_{step}"
            mass = make_mass(split_index, step, 0, True)
            masses.append(mass)
            base_lookup[(split, seed, step)] = snapshot_id
            rows.append({
                "matrix_row_index": row_index,
                "snapshot_id": snapshot_id,
                "source_run_id": run_id,
                "dataset_split": split,
                "distribution_group": "base_v3_3",
                "seed": seed,
                "source_step": step,
                "capture_policy": "provisional_fixed_exposure_v1",
                "external_vector_id": base_vector,
                "active_factor_count": 0,
                "matched_base_snapshot_id": snapshot_id,
                "mass_sum": float(mass.sum()),
                "min_mass": float(mass.min()),
                "max_mass": float(mass.max()),
            })
            discovery.append({"matrix_row_index": row_index, "snapshot_id": snapshot_id, "dataset_split": split, "analysis_weight": 1.0})
            row_index += 1

    for split_index, split in enumerate(("fit", "validation", "holdout")):
        seed = split_seed[split]
        vector_ids = [row["external_vector_id"] for row in vector_rows if row["dataset_split"] == split and not row["is_base_vector"]]
        assert len(vector_ids) == split_nonbase_vectors[split]
        for vector_index, vector_id in enumerate(vector_ids, start=1):
            run_id = f"run_{split}_{vector_index:03d}"
            for step in (1, 2):
                snapshot_id = f"snap_{split}_{vector_index:03d}_{step}"
                mass = make_mass(split_index, step, vector_index, False)
                masses.append(mass)
                base_id = base_lookup[(split, seed, step)]
                rows.append({
                    "matrix_row_index": row_index,
                    "snapshot_id": snapshot_id,
                    "source_run_id": run_id,
                    "dataset_split": split,
                    "distribution_group": "external_augmented",
                    "seed": seed,
                    "source_step": step,
                    "capture_policy": "provisional_fixed_exposure_v1",
                    "external_vector_id": vector_id,
                    "active_factor_count": 6,
                    "matched_base_snapshot_id": base_id,
                    "mass_sum": float(mass.sum()),
                    "min_mass": float(mass.min()),
                    "max_mass": float(mass.max()),
                })
                discovery.append({"matrix_row_index": row_index, "snapshot_id": snapshot_id, "dataset_split": split, "analysis_weight": 1.0})
                pairs.append({
                    "external_snapshot_id": snapshot_id,
                    "base_snapshot_id": base_id,
                    "dataset_split": split,
                    "seed": seed,
                    "source_step": step,
                    "pair_quality": "exact",
                })
                row_index += 1

    assert row_index == 41
    np.save(artifact / "mass_matrix.npy", np.vstack(masses).astype(np.float64))
    pd.DataFrame(rows).to_csv(artifact / "snapshot_metadata.csv", index=False)
    pd.DataFrame(discovery).to_csv(artifact / "discovery_manifest.csv", index=False)
    pd.DataFrame(pairs).to_csv(artifact / "matched_pairs.csv", index=False)
    (artifact / "generation_metadata.json").write_text(json.dumps({
        "profile": "smoke",
        "config_sha256": "smoke-fixture",
        "cell_count": 3125,
        "snapshot_count": 41,
    }, indent=2) + "\n", encoding="utf-8")
    return artifact
