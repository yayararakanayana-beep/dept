from __future__ import annotations
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd

def grouped_subsets(fit_map: pd.DataFrame, contract: dict[str, Any]) -> list[dict[str, Any]]:
    config = contract["matching_and_stability"]["grouped_subset"]
    required = {"distribution_group", "external_vector_id", "source_run_id", "active_factor_count", "vector_origin"}
    if not required.issubset(fit_map.columns):
        raise ValueError(f"fit map missing subset columns: {sorted(required - set(fit_map.columns))}")
    group_rows: list[dict[str, Any]] = []
    for index, row in fit_map.reset_index(drop=True).iterrows():
        if str(row["distribution_group"]) == "external_augmented":
            group_key = f"external|{int(row['active_factor_count'])}|{row['vector_origin']}|{row['external_vector_id']}"
            stratum = f"{int(row['active_factor_count'])}|{row['vector_origin']}"
        else:
            group_key = f"base|{row['source_run_id']}"
            stratum = "base"
        group_rows.append({"row_index": index, "group_key": group_key, "stratum": stratum})
    groups = pd.DataFrame(group_rows).groupby(["stratum", "group_key"])["row_index"].apply(list).reset_index()
    outputs: list[dict[str, Any]] = []
    import hashlib

    for salt in config["salts"]:
        included: list[int] = []
        included_groups: list[str] = []
        excluded_groups: list[str] = []
        for group in groups.itertuples(index=False):
            value = int(hashlib.sha256(f"{salt}|{group.stratum}|{group.group_key}".encode()).hexdigest(), 16) / 2**256
            if value < float(config["fit_fraction"]):
                included.extend(int(index) for index in group.row_index)
                included_groups.append(str(group.group_key))
            else:
                excluded_groups.append(str(group.group_key))
        included = sorted(included)
        membership = set(included)
        preserving = all(
            (all(int(index) in membership for index in group.row_index)
             or all(int(index) not in membership for index in group.row_index))
            for group in groups.itertuples(index=False)
        )
        outputs.append(
            {
                "subset_id": str(salt),
                "included_row_indices": included,
                "included_group_keys": included_groups,
                "excluded_group_keys": excluded_groups,
                "included_fraction": len(included) / len(fit_map),
                "group_preserving": bool(preserving),
            }
        )
    return outputs

def _selected_representative(root: Path, runs: pd.DataFrame, selection: dict[str, Any]) -> tuple[pd.Series, np.ndarray]:
    run_id = str(selection["selected_representative_run"])
    rows = runs[runs["run_id"] == run_id]
    if len(rows) != 1:
        raise ValueError("selected representative run is missing")
    run = rows.iloc[0]
    return run, np.load(root / str(run["basis_path"]), allow_pickle=False)
