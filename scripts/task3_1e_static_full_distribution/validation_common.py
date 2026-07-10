"""Shared validation helpers for Task 3.1e."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Callable

import numpy as np
import pandas as pd

from .core import EXTERNAL_COLUMNS, OUT_SUBDIR

RAW_REQUIRED_FILES = [
    "external_vectors.csv", "adaptive_pool.csv", "adaptive_pool_mass_matrix.npy",
    "coverage_additions.csv", "snapshot_metadata.csv", "discovery_manifest.csv",
    "matched_pairs.csv", "cell_coordinates.csv", "terrain_field_catalog.csv",
    "mass_matrix.npy", "terrain_reference.npz", "generation_metadata.json",
    "coverage_summary.csv", "coverage_audit_metadata.json",
]
EXTERNAL_VECTOR_COLUMNS = [
    "external_vector_id", "dataset_split", "vector_origin", "mask_bits",
    "active_factor_count", "is_base_vector", "sobol_scramble_seed", "sobol_index",
    "candidate_pool_id", "adaptive_selection_rank", *EXTERNAL_COLUMNS,
]
DISCOVERY_COLUMNS = ["matrix_row_index", "snapshot_id", "dataset_split", "analysis_weight"]
METADATA_COLUMNS = [
    "matrix_row_index", "snapshot_id", "source_run_id", "dataset_split",
    "distribution_group", "seed", "source_step", "capture_policy",
    "external_vector_id", "active_factor_count", "matched_base_snapshot_id",
    "mass_sum", "min_mass", "max_mass",
]
PAIR_COLUMNS = ["external_snapshot_id", "base_snapshot_id", "dataset_split", "seed", "source_step", "pair_quality"]


def _artifact_dir(root: str | Path) -> Path:
    path = Path(root)
    return path if path.name == OUT_SUBDIR else path / OUT_SUBDIR


def _mask_count(active_count: int) -> int:
    return 1 if active_count == 6 else math.comb(6, active_count)


def expected_counts(profile_config: dict[str, Any]) -> dict[str, Any]:
    fit_before = sum(_mask_count(k) * int(profile_config["fit_allocation"][str(k)]) for k in range(1, 7))
    validation_nonbase = sum(_mask_count(k) * int(profile_config["validation_allocation"][str(k)]) for k in range(1, 7))
    holdout_nonbase = int(profile_config["holdout"]["boundary_count"]) + int(profile_config["holdout"]["full6_count"])
    pool_count = sum(_mask_count(int(item["active_factor_count"])) * int(item["points_per_mask"]) for item in profile_config["adaptive_pool"])
    selected = int(profile_config["adaptive_selected_count"])
    fit_nonbase = fit_before + selected
    external_steps = len(profile_config["capture_steps"]["external"])
    base_steps = len(profile_config["capture_steps"]["base"])
    seeds = profile_config["world_seeds"]
    nonbase_snapshots = (
        fit_nonbase * len(seeds["fit"]) * external_steps
        + validation_nonbase * len(seeds["validation"]) * external_steps
        + holdout_nonbase * len(seeds["holdout"]) * external_steps
    )
    base_snapshots = sum(len(seeds[split]) * base_steps for split in ("fit", "validation", "holdout"))
    return {
        "fit_nonbase_before_adaptive": fit_before, "fit_nonbase": fit_nonbase,
        "validation_nonbase": validation_nonbase, "holdout_nonbase": holdout_nonbase,
        "adaptive_pool": pool_count, "adaptive_selected": selected,
        "external_vector_total": fit_nonbase + validation_nonbase + holdout_nonbase + 3,
        "nonbase_snapshots": nonbase_snapshots, "base_snapshots": base_snapshots,
        "snapshot_total": nonbase_snapshots + base_snapshots,
    }


def _as_bool(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series
    return series.astype(str).str.lower().map({"true": True, "false": False}).fillna(False)


class Recorder:
    def __init__(self) -> None:
        self.checks: dict[str, dict[str, Any]] = {}

    def add(self, name: str, passed: bool, **evidence: Any) -> None:
        payload = {"passed": bool(passed)}
        payload.update(_json_safe(evidence))
        self.checks[name] = payload

    def guard(self, name: str, function: Callable[[], dict[str, Any]]) -> None:
        try:
            evidence = function()
            passed = bool(evidence.pop("passed"))
            self.add(name, passed, **evidence)
        except Exception as exc:
            self.add(name, False, error=f"{type(exc).__name__}: {exc}")

    @property
    def failed(self) -> list[str]:
        return [name for name, payload in self.checks.items() if not payload["passed"]]


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(artifact_dir: Path) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for path in sorted(artifact_dir.iterdir()):
        if not path.is_file() or path.name == "artifact_manifest.json":
            continue
        entry: dict[str, Any] = {"path": path.name, "size_bytes": path.stat().st_size, "sha256": _sha256(path)}
        if path.suffix == ".csv":
            frame = pd.read_csv(path)
            entry.update({"type": "csv", "row_count": len(frame), "columns": list(frame.columns)})
        elif path.suffix == ".npy":
            array = np.load(path, allow_pickle=False)
            entry.update({"type": "npy", "shape": list(array.shape), "dtype": str(array.dtype)})
        elif path.suffix == ".npz":
            with np.load(path, allow_pickle=False) as archive:
                entry.update({"type": "npz", "members": {
                    name: {"shape": list(archive[name].shape), "dtype": str(archive[name].dtype)}
                    for name in archive.files
                }})
        elif path.suffix == ".json":
            payload = json.loads(path.read_text(encoding="utf-8"))
            entry.update({"type": "json", "top_level_type": type(payload).__name__})
        elif path.suffix == ".md":
            entry.update({"type": "markdown", "line_count": len(path.read_text(encoding="utf-8").splitlines())})
        else:
            entry.update({"type": "other"})
        entries.append(entry)
    return {"artifact_root": artifact_dir.name, "files": entries}
