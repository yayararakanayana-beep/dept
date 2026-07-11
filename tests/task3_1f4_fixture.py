from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd


def build_holdout_smoke_bundle(root: Path, cell_count: int = 125) -> dict[str, Path]:
    root.mkdir(parents=True, exist_ok=False)
    latent_count = 5
    latent = np.zeros((latent_count, cell_count), dtype=np.float64)
    for component, indices in enumerate(np.array_split(np.arange(cell_count), latent_count)):
        latent[component, indices] = 1.0 / len(indices)
    rng = np.random.default_rng(4040)

    def mass(coefficients: list[float] | np.ndarray) -> np.ndarray:
        values = np.asarray(coefficients, dtype=np.float64) @ latent + 0.02 * rng.random(cell_count)
        values /= values.sum(dtype=np.float64)
        return values

    rows: list[dict[str, object]] = []
    matrices: list[np.ndarray] = []

    def add(
        *,
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
        matrix_row_index = 1000 + len(rows)
        snapshot_id = f"holdout_{seed}_{source_run_id}_{step}_{matrix_row_index}"
        matrices.append(mass(coefficients))
        rows.append(
            {
                "bundle_row_index": len(rows),
                "matrix_row_index": matrix_row_index,
                "snapshot_id": snapshot_id,
                "dataset_split": "holdout",
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

    bases: dict[int, str] = {}
    for step in (0, 1, 2):
        bases[step] = add(
            seed=20,
            step=step,
            distribution_group="base_v3_3",
            source_run_id="base20",
            external_vector_id="basevec20",
            vector_origin="base",
            active_factor_count=0,
            matched_base_snapshot_id=None,
            coefficients=[0.42, 0.24, 0.16, 0.10, 0.08],
        )
    for vector_index in range(4):
        for step in (1, 2):
            coefficients = np.full(latent_count, 0.025)
            coefficients[(vector_index + step) % latent_count] = 0.78
            coefficients[(vector_index + 2) % latent_count] += 0.10
            add(
                seed=20,
                step=step,
                distribution_group="external_augmented",
                source_run_id=f"hrun{vector_index}",
                external_vector_id=f"hvec{vector_index}",
                vector_origin="sobol_stratified",
                active_factor_count=6,
                matched_base_snapshot_id=bases[step],
                coefficients=coefficients,
            )

    assert len(rows) == 11
    evaluation = pd.DataFrame(rows)
    row_map = evaluation.drop(columns=["matched_base_snapshot_id"])
    matrix = np.vstack(matrices)
    snapshot_hashes = np.asarray(
        [
            hashlib.sha256(str(value).encode("utf-8")).hexdigest().encode("ascii")
            for value in evaluation["snapshot_id"]
        ],
        dtype="S64",
    )
    bundle_path = root / "holdout_bundle.npz"
    row_map_path = root / "holdout_row_map.csv"
    metadata_path = root / "holdout_evaluation_metadata.csv"
    np.savez(
        bundle_path,
        mass_matrix=matrix,
        analysis_weight=evaluation["analysis_weight"].to_numpy(dtype=np.float64),
        matrix_row_index=evaluation["matrix_row_index"].to_numpy(dtype=np.int64),
        snapshot_id_hash=snapshot_hashes,
    )
    row_map.to_csv(row_map_path, index=False)
    evaluation.to_csv(metadata_path, index=False)
    return {
        "holdout_bundle": bundle_path,
        "holdout_row_map": row_map_path,
        "holdout_evaluation_metadata": metadata_path,
    }
