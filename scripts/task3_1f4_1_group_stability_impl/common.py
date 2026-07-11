from __future__ import annotations

import hashlib
import json
import math
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

AXIS_NAMES = (
    "resource_slack",
    "information_quality",
    "pressure",
    "exploration_room",
    "reversibility",
)
TARGET_RANKS = (5, 8, 10, 15)
CROSS_RANK_PAIRS = ((5, 8), (5, 10), (5, 15), (8, 10), (8, 15), (10, 15))
OUTPUT_DIR_NAME = "task3_1f4_1_group_stability"
EPSILON = 1e-12
MAX_JS_DISTANCE = math.sqrt(math.log(2.0))


@dataclass(frozen=True)
class GroupMatch:
    source_index: int
    target_indices: tuple[int, ...]
    weights: tuple[float, ...]
    js_distance: float
    js_similarity: float
    cosine_similarity: float
    classification: str
    beam_rank: int


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _ensure_probability_rows(matrix: np.ndarray, name: str) -> np.ndarray:
    values = np.asarray(matrix, dtype=np.float64)
    if values.ndim != 2 or values.shape[0] == 0 or values.shape[1] == 0:
        raise ValueError(f"{name} must be a non-empty 2D array")
    if not np.isfinite(values).all() or np.any(values < -1e-12):
        raise ValueError(f"{name} must be finite and non-negative")
    sums = values.sum(axis=1, dtype=np.float64)
    if np.any(sums <= 0.0):
        raise ValueError(f"{name} contains zero-mass rows")
    values = np.maximum(values, 0.0)
    values /= values.sum(axis=1, keepdims=True)
    return values


def _load_bundle(bundle_path: Path, row_map_path: Path) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    with np.load(bundle_path, allow_pickle=False) as bundle:
        required = {"mass_matrix", "analysis_weight", "matrix_row_index", "snapshot_id_hash"}
        if set(bundle.files) != required:
            raise ValueError(f"bundle members differ from frozen schema: {bundle.files}")
        mass = np.asarray(bundle["mass_matrix"], dtype=np.float64)
        weights = np.asarray(bundle["analysis_weight"], dtype=np.float64)
        indices = np.asarray(bundle["matrix_row_index"], dtype=np.int64)
        snapshot_hashes = np.asarray(bundle["snapshot_id_hash"])
    row_map = pd.read_csv(row_map_path)
    if len(row_map) != mass.shape[0] or weights.shape != (mass.shape[0],):
        raise ValueError("bundle arrays and row map are not aligned")
    if not np.array_equal(indices, row_map["matrix_row_index"].to_numpy(dtype=np.int64)):
        raise ValueError("bundle indices and row map differ")
    expected_hashes = np.asarray(
        [hashlib.sha256(str(value).encode("utf-8")).hexdigest().encode("ascii") for value in row_map["snapshot_id"]],
        dtype="S64",
    )
    if not np.array_equal(snapshot_hashes, expected_hashes):
        raise ValueError("bundle snapshot hashes and row map differ")
    mass = _ensure_probability_rows(mass, "bundle mass matrix")
    if not np.isfinite(weights).all() or np.any(weights <= 0.0):
        raise ValueError("analysis weights must be finite and positive")
    return mass, weights, row_map


def _assert_no_holdout(root: Path) -> None:
    forbidden = [path for path in root.rglob("*") if "holdout" in path.name.lower()]
    if forbidden:
        raise ValueError(f"holdout material is forbidden: {forbidden[0]}")


def _load_contract(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("contract_version") != "task3.1f-4.1-rc1":
        raise ValueError("unexpected Task 3.1f-4.1 contract version")
    if payload.get("status") != "frozen":
        raise ValueError("Task 3.1f-4.1 contract is not frozen")
    if tuple(payload.get("ranks", [])) != TARGET_RANKS:
        raise ValueError("Task 3.1f-4.1 rank set differs from frozen contract")
    if tuple(payload.get("native_axes", [])) != AXIS_NAMES:
        raise ValueError("native axis order differs from frozen contract")
    matching = payload.get("group_matching", {})
    if matching.get("max_group_size") != 4 or matching.get("similarity_threshold") != 0.85:
        raise ValueError("group matching contract differs from frozen values")
    if matching.get("intermediate_threshold") != 0.80 or matching.get("minimum_member_weight") != 0.10:
        raise ValueError("group matching threshold contract differs from frozen values")
    if not payload.get("holdout", {}).get("access_prohibited", False):
        raise ValueError("holdout prohibition is not enabled")
    return payload
