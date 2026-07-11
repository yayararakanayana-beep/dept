from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd


def build_stage_bc_smoke_bundles(root: Path, cell_count: int = 125) -> dict[str, Path]:
    root.mkdir(parents=True, exist_ok=False)
    latent_count = 5
    latent = np.zeros((latent_count, cell_count), dtype=np.float64)
    for component, indices in enumerate(np.array_split(np.arange(cell_count), latent_count)):
        latent[component, indices] = 1.0 / len(indices)
    rng = np.random.default_rng(2026)

    def mass(coefficients: list[float] | np.ndarray) -> np.ndarray:
        values = np.asarray(coefficients, dtype=np.float64) @ latent + 0.02 * rng.random(cell_count)
        values /= values.sum(dtype=np.float64)
        return values.astype(np.float64)

    rows: list[dict[str, object]] = []
    matrices: list[np.ndarray] = []

    def add(
        split: str,
        seed: int,
        step: int,
        distribution_group: str,
        source_run_id: str,
        external_vector_id: str,
        vector_origin: str,
        active_factor_count: int,
        matched_base_snapshot_id: str | None,
        coefficients: list[float] | np.ndarray,
    ) -> str:
        matrix_row_index = len(rows)
        snapshot_id = f"{split}_{seed}_{source_run_id}_{step}_{matrix_row_index}"
        matrices.append(mass(coefficients))
        rows.append(
            {
                "bundle_row_index": -1,
                "matrix_row_index": matrix_row_index,
                "snapshot_id": snapshot_id,
                "dataset_split": split,
                "distribution_group": distribution_group,
                "source_run_id": source_run_id,
                "external_vector_id": external_vector_id,
                "seed": seed,
                "source_step": step,
                "active_factor_count": active_factor_count,
                "vector_origin": vector_origin,
                "analysis_weight": 1.0,
                "matched_base_snapshot_id": matched_base_snapshot_id or snapshot_id,
            }
        )
        return snapshot_id

    base: dict[tuple[str, int, int], str] = {}
    for seed, steps in ((0, (0, 1, 2)), (1, (1, 2))):
        for step in steps:
            base[("fit", seed, step)] = add(
                "fit", seed, step, "base_v3_3", f"base{seed}", f"basevec{seed}", "base", 0,
                None, [0.45, 0.25, 0.15, 0.10, 0.05],
            )
    for seed, vector_count in ((0, 5), (1, 4)):
        for vector_index in range(vector_count):
            for step in (1, 2):
                coefficients = np.full(latent_count, 0.02)
                coefficients[(vector_index + step + seed) % latent_count] = 0.80
                coefficients[(vector_index + 1) % latent_count] += 0.10
                add(
                    "fit", seed, step, "external_augmented", f"run{seed}_{vector_index}",
                    f"vec{seed}_{vector_index}", "sobol_stratified", 6,
                    base[("fit", seed, step)], coefficients,
                )
    for step in (0, 1, 2):
        base[("validation", 10, step)] = add(
            "validation", 10, step, "base_v3_3", "base10", "basevec10", "base", 0,
            None, [0.40, 0.25, 0.15, 0.10, 0.10],
        )
    for vector_index in range(2):
        for step in (1, 2):
            coefficients = np.full(latent_count, 0.03)
            coefficients[(vector_index + step + 2) % latent_count] = 0.75
            coefficients[(vector_index + 3) % latent_count] += 0.10
            add(
                "validation", 10, step, "external_augmented", f"vrun{vector_index}",
                f"vvec{vector_index}", "sobol_stratified", 6,
                base[("validation", 10, step)], coefficients,
            )

    assert sum(row["dataset_split"] == "fit" for row in rows) == 23
    assert sum(row["dataset_split"] == "validation" for row in rows) == 7
    all_matrix = np.vstack(matrices)
    output: dict[str, Path] = {}
    for split in ("fit", "validation"):
        indices = [index for index, row in enumerate(rows) if row["dataset_split"] == split]
        evaluation = pd.DataFrame([rows[index] for index in indices]).reset_index(drop=True)
        evaluation["bundle_row_index"] = np.arange(len(evaluation), dtype=np.int64)
        row_map = evaluation.drop(columns=["matched_base_snapshot_id"])
        matrix = all_matrix[indices]
        snapshot_hashes = np.asarray(
            [hashlib.sha256(str(value).encode("utf-8")).hexdigest().encode("ascii") for value in evaluation["snapshot_id"]],
            dtype="S64",
        )
        bundle_path = root / f"{split}_bundle.npz"
        row_map_path = root / f"{split}_row_map.csv"
        evaluation_path = root / f"{split}_evaluation_metadata.csv"
        np.savez(
            bundle_path,
            mass_matrix=matrix,
            analysis_weight=evaluation["analysis_weight"].to_numpy(dtype=np.float64),
            matrix_row_index=evaluation["matrix_row_index"].to_numpy(dtype=np.int64),
            snapshot_id_hash=snapshot_hashes,
        )
        row_map.to_csv(row_map_path, index=False)
        evaluation.to_csv(evaluation_path, index=False)
        output[f"{split}_bundle"] = bundle_path
        output[f"{split}_row_map"] = row_map_path
        output[f"{split}_evaluation_metadata"] = evaluation_path
    return output
