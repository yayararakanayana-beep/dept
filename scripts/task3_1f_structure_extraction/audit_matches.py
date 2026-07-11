from __future__ import annotations
from itertools import combinations
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
PRIMARY="nmf_kl"
def _component_matches(basis_a: np.ndarray, basis_b: np.ndarray) -> list[dict[str, Any]]:
    epsilon = 1e-12
    left = np.maximum(np.asarray(basis_a, dtype=np.float64), epsilon)
    right = np.maximum(np.asarray(basis_b, dtype=np.float64), epsilon)
    left /= left.sum(axis=1, keepdims=True)
    right /= right.sum(axis=1, keepdims=True)
    distances = np.empty((len(left), len(right)), dtype=np.float64)
    for index, row in enumerate(left):
        midpoint = 0.5 * (row[None, :] + right)
        divergence = 0.5 * np.sum(row[None, :] * np.log(row[None, :] / midpoint), axis=1)
        divergence += 0.5 * np.sum(right * np.log(right / midpoint), axis=1)
        distances[index] = np.sqrt(np.maximum(divergence, 0.0))
    row_indices, column_indices = linear_sum_assignment(distances)
    maximum = float(np.sqrt(np.log(2.0)))
    rows: list[dict[str, Any]] = []
    for order, (row_index, column_index) in enumerate(zip(row_indices, column_indices), start=1):
        denominator = float(np.linalg.norm(left[row_index]) * np.linalg.norm(right[column_index]))
        rows.append(
            {
                "component_index_a": int(row_index),
                "component_index_b": int(column_index),
                "js_distance": float(distances[row_index, column_index]),
                "js_similarity": float(1.0 - distances[row_index, column_index] / maximum),
                "cosine_similarity": float(np.dot(left[row_index], right[column_index]) / denominator),
                "matching_cost_rank": order,
            }
        )
    return rows

def _recompute_component_matches(root: Path, runs: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    primary = runs[(runs["method"] == PRIMARY) & (runs["status"] == "completed")]
    for rank, group in primary.groupby("rank"):
        records = list(group.to_dict("records"))
        for left, right in combinations(records, 2):
            basis_left = np.load(root / left["basis_path"], allow_pickle=False)
            basis_right = np.load(root / right["basis_path"], allow_pickle=False)
            for item in _component_matches(basis_left, basis_right):
                rows.append(
                    {
                        "rank": int(rank),
                        "run_id_a": left["run_id"],
                        "run_id_b": right["run_id"],
                        **item,
                    }
                )
    return pd.DataFrame(rows)

def _compare_match_frames(stored: pd.DataFrame, recomputed: pd.DataFrame) -> tuple[bool, float]:
    keys = ["rank", "run_id_a", "run_id_b", "component_index_a", "component_index_b", "matching_cost_rank"]
    stored = stored.sort_values(keys).reset_index(drop=True)
    recomputed = recomputed.sort_values(keys).reset_index(drop=True)
    if len(stored) != len(recomputed):
        return False, float("inf")
    if any(stored[column].astype(str).tolist() != recomputed[column].astype(str).tolist() for column in keys):
        return False, float("inf")
    maximum = 0.0
    for column in ("js_distance", "js_similarity", "cosine_similarity"):
        left = stored[column].to_numpy(dtype=np.float64)
        right = recomputed[column].to_numpy(dtype=np.float64)
        maximum = max(maximum, float(np.max(np.abs(left - right), initial=0.0)))
        if not np.allclose(left, right, rtol=1e-9, atol=1e-12):
            return False, maximum
    return True, maximum
