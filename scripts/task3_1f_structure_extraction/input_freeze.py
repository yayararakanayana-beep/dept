from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .contract import (
    DEFAULT_CONTRACT,
    OUTPUT_SUBDIR,
    REQUIRED_INPUT_FILES,
    SMOKE_SPLIT_ROWS,
    canonical_contract_text,
    load_contract,
    sha256_file,
    sha256_text,
)

MASS_SUM_TOLERANCE = 1e-8
NEGATIVE_TOLERANCE = 1e-12
ROW_MAP_COLUMNS = [
    "bundle_row_index",
    "matrix_row_index",
    "snapshot_id",
    "dataset_split",
    "distribution_group",
    "source_run_id",
    "external_vector_id",
    "seed",
    "source_step",
    "active_factor_count",
    "vector_origin",
    "analysis_weight",
]


def _snapshot_hashes(snapshot_ids: pd.Series) -> np.ndarray:
    return np.asarray(
        [hashlib.sha256(str(value).encode("utf-8")).hexdigest().encode("ascii") for value in snapshot_ids],
        dtype="S64",
    )


def _validate_mass(matrix: np.ndarray, expected_rows: int, expected_cells: int) -> dict[str, Any]:
    if matrix.shape != (expected_rows, expected_cells):
        raise ValueError(f"mass matrix shape {matrix.shape} != {(expected_rows, expected_cells)}")
    if matrix.dtype != np.float64:
        raise ValueError(f"mass matrix dtype must be float64, got {matrix.dtype}")
    if not np.isfinite(matrix).all():
        raise ValueError("mass matrix contains non-finite values")
    minimum = float(matrix.min())
    if minimum < -NEGATIVE_TOLERANCE:
        raise ValueError(f"mass matrix contains negative values: {minimum}")
    sums = matrix.sum(axis=1, dtype=np.float64)
    max_error = float(np.max(np.abs(sums - 1.0)))
    if max_error > MASS_SUM_TOLERANCE:
        raise ValueError(f"mass row sum error {max_error} exceeds {MASS_SUM_TOLERANCE}")
    return {
        "shape": list(matrix.shape),
        "dtype": str(matrix.dtype),
        "minimum": minimum,
        "maximum_row_sum_error": max_error,
    }


def _load_and_align(input_dir: Path) -> tuple[np.ndarray, pd.DataFrame, pd.DataFrame]:
    mass = np.load(input_dir / "mass_matrix.npy", allow_pickle=False)
    metadata = pd.read_csv(input_dir / "snapshot_metadata.csv")
    discovery = pd.read_csv(input_dir / "discovery_manifest.csv")
    vectors = pd.read_csv(input_dir / "external_vectors.csv")

    required_metadata = {
        "matrix_row_index",
        "snapshot_id",
        "source_run_id",
        "dataset_split",
        "distribution_group",
        "seed",
        "source_step",
        "external_vector_id",
        "active_factor_count",
    }
    required_discovery = {"matrix_row_index", "snapshot_id", "dataset_split", "analysis_weight"}
    if not required_metadata.issubset(metadata.columns):
        raise ValueError(f"snapshot_metadata.csv missing {sorted(required_metadata - set(metadata.columns))}")
    if set(discovery.columns) != required_discovery:
        raise ValueError("discovery_manifest.csv must have exactly four frozen columns")
    if vectors["external_vector_id"].duplicated().any():
        raise ValueError("external_vector_id is not unique")
    if metadata["matrix_row_index"].duplicated().any() or discovery["matrix_row_index"].duplicated().any():
        raise ValueError("matrix_row_index is duplicated")
    expected_indices = np.arange(len(metadata), dtype=np.int64)
    metadata = metadata.sort_values("matrix_row_index").reset_index(drop=True)
    discovery = discovery.sort_values("matrix_row_index").reset_index(drop=True)
    if not np.array_equal(metadata["matrix_row_index"].to_numpy(dtype=np.int64), expected_indices):
        raise ValueError("snapshot metadata indices are not contiguous from zero")
    if not np.array_equal(discovery["matrix_row_index"].to_numpy(dtype=np.int64), expected_indices):
        raise ValueError("discovery indices are not contiguous from zero")
    if metadata["snapshot_id"].duplicated().any():
        raise ValueError("snapshot_id is duplicated")
    if metadata["snapshot_id"].tolist() != discovery["snapshot_id"].tolist():
        raise ValueError("metadata and discovery snapshot IDs are misaligned")
    if metadata["dataset_split"].tolist() != discovery["dataset_split"].tolist():
        raise ValueError("metadata and discovery splits are misaligned")

    weight = pd.to_numeric(discovery["analysis_weight"], errors="coerce").to_numpy(dtype=np.float64)
    if not np.isfinite(weight).all() or np.any(weight <= 0.0):
        raise ValueError("analysis weights must be finite and positive")
    joined = metadata.merge(
        discovery[["matrix_row_index", "analysis_weight"]],
        on="matrix_row_index",
        how="left",
        validate="one_to_one",
    ).merge(
        vectors[["external_vector_id", "vector_origin"]],
        on="external_vector_id",
        how="left",
        validate="many_to_one",
    )
    if joined["vector_origin"].isna().any():
        raise ValueError("one or more snapshots have no external-vector metadata")
    return mass, joined, vectors


def _validate_pairs(input_dir: Path, aligned: pd.DataFrame) -> dict[str, Any]:
    pairs = pd.read_csv(input_dir / "matched_pairs.csv")
    required = {
        "external_snapshot_id",
        "base_snapshot_id",
        "dataset_split",
        "seed",
        "source_step",
        "pair_quality",
    }
    if set(pairs.columns) != required:
        raise ValueError("matched_pairs.csv schema differs from Task 3.1e")
    index = aligned.set_index("snapshot_id", drop=False)
    invalid = 0
    for row in pairs.itertuples(index=False):
        if row.external_snapshot_id not in index.index or row.base_snapshot_id not in index.index:
            invalid += 1
            continue
        external = index.loc[row.external_snapshot_id]
        base = index.loc[row.base_snapshot_id]
        if (
            external["distribution_group"] != "external_augmented"
            or base["distribution_group"] != "base_v3_3"
            or external["dataset_split"] != base["dataset_split"]
            or int(external["seed"]) != int(base["seed"])
            or int(external["source_step"]) != int(base["source_step"])
            or row.dataset_split != external["dataset_split"]
            or int(row.seed) != int(external["seed"])
            or int(row.source_step) != int(external["source_step"])
            or row.pair_quality != "exact"
        ):
            invalid += 1
    external_rows = int((aligned["distribution_group"] == "external_augmented").sum())
    if len(pairs) != external_rows or invalid:
        raise ValueError(f"matched-pair contract failed: rows={len(pairs)}, external={external_rows}, invalid={invalid}")
    return {"pair_count": len(pairs), "invalid_pair_count": invalid}


def _write_bundle(output_dir: Path, split: str, mass: np.ndarray, rows: pd.DataFrame) -> dict[str, Any]:
    selector = rows["dataset_split"] == split
    split_rows = rows.loc[selector].copy().sort_values("matrix_row_index").reset_index(drop=True)
    split_mass = np.asarray(mass[split_rows["matrix_row_index"].to_numpy(dtype=np.int64)], dtype=np.float64)
    split_rows.insert(0, "bundle_row_index", np.arange(len(split_rows), dtype=np.int64))
    row_map = split_rows[ROW_MAP_COLUMNS]
    bundle_path = output_dir / "bundles" / f"{split}_bundle.npz"
    map_path = output_dir / "bundles" / f"{split}_row_map.csv"
    np.savez(
        bundle_path,
        mass_matrix=split_mass,
        analysis_weight=row_map["analysis_weight"].to_numpy(dtype=np.float64),
        matrix_row_index=row_map["matrix_row_index"].to_numpy(dtype=np.int64),
        snapshot_id_hash=_snapshot_hashes(row_map["snapshot_id"]),
    )
    row_map.to_csv(map_path, index=False)
    return {
        "split": split,
        "row_count": len(row_map),
        "bundle_path": str(bundle_path.relative_to(output_dir)),
        "bundle_sha256": sha256_file(bundle_path),
        "row_map_path": str(map_path.relative_to(output_dir)),
        "row_map_sha256": sha256_file(map_path),
    }


def freeze_input(
    input_artifact: str | Path,
    output_root: str | Path,
    profile: str,
    contract_path: str | Path = DEFAULT_CONTRACT,
    input_archive_sha256: str | None = None,
) -> Path:
    if profile not in {"smoke", "formal"}:
        raise ValueError("profile must be smoke or formal")
    contract = load_contract(contract_path)
    input_dir = Path(input_artifact)
    missing = [name for name in REQUIRED_INPUT_FILES if not (input_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(f"missing Task 3.1e input files: {missing}")
    generation = json.loads((input_dir / "generation_metadata.json").read_text(encoding="utf-8"))
    if generation.get("profile") != profile:
        raise ValueError("Task 3.1e generation profile does not match requested profile")
    if profile == "formal":
        expected_archive = contract["input"]["formal_artifact_sha256"]
        if input_archive_sha256 != expected_archive:
            raise ValueError("formal Task 3.1e archive digest was not supplied or does not match the frozen contract")
        if generation.get("config_sha256") != contract["input"]["task3_1e_config_sha256"]:
            raise ValueError("formal Task 3.1e config digest differs from the frozen contract")
        expected_rows = contract["input"]["split_rows"]
    else:
        expected_rows = SMOKE_SPLIT_ROWS

    mass, aligned, _ = _load_and_align(input_dir)
    actual_rows = {split: int((aligned["dataset_split"] == split).sum()) for split in ("fit", "validation", "holdout")}
    if actual_rows != expected_rows:
        raise ValueError(f"split row counts {actual_rows} != expected {expected_rows}")
    mass_evidence = _validate_mass(mass, sum(expected_rows.values()), int(contract["input"]["cell_count"]))
    split_weight_means = aligned.groupby("dataset_split")["analysis_weight"].mean().to_dict()
    if not all(np.isclose(float(value), 1.0, rtol=0.0, atol=1e-12) for value in split_weight_means.values()):
        raise ValueError(f"analysis weight split means are not one: {split_weight_means}")
    pair_evidence = _validate_pairs(input_dir, aligned)

    output_dir = Path(output_root) / OUTPUT_SUBDIR
    if output_dir.exists():
        shutil.rmtree(output_dir)
    (output_dir / "bundles").mkdir(parents=True, exist_ok=False)
    bundle_entries = [_write_bundle(output_dir, split, mass, aligned) for split in ("fit", "validation", "holdout")]
    contract_text = canonical_contract_text(contract_path)
    (output_dir / "contract_snapshot.json").write_text(
        json.dumps(json.loads(Path(contract_path).read_text(encoding="utf-8")), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    input_files = {
        name: {"sha256": sha256_file(input_dir / name), "size_bytes": (input_dir / name).stat().st_size}
        for name in REQUIRED_INPUT_FILES
    }
    manifest = {
        "stage": "task3.1f-2-input-freeze",
        "profile": profile,
        "contract_sha256": sha256_text(contract_text),
        "input_archive_sha256": input_archive_sha256,
        "input_files": input_files,
        "mass_evidence": mass_evidence,
        "split_rows": actual_rows,
        "split_weight_means": {key: float(value) for key, value in split_weight_means.items()},
        "pair_evidence": pair_evidence,
        "bundles": bundle_entries,
        "holdout_bundle_created": True,
        "holdout_accessed_by_model_selection": False,
    }
    (output_dir / "input_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return output_dir


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-artifact", required=True)
    parser.add_argument("--output-root", default="artifacts")
    parser.add_argument("--profile", choices=("smoke", "formal"), required=True)
    parser.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    parser.add_argument("--input-archive-sha256")
    args = parser.parse_args()
    print(
        freeze_input(
            args.input_artifact,
            args.output_root,
            args.profile,
            args.contract,
            args.input_archive_sha256,
        )
    )
