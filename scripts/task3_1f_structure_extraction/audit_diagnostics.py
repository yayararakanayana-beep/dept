from __future__ import annotations
from pathlib import Path
from typing import Any
import numpy as np
import pandas as pd
from .contract import sha256_file
from .audit_matches import _component_matches

def _diagnostic_checks(
    root: Path,
    candidate: dict[str, Any],
    runs: pd.DataFrame,
    contract: dict[str, Any],
) -> dict[str, Any]:
    if candidate.get("selection_status") != "selected":
        return {
            "grouped_subset": {"passed": not (root / "selection_lock.json").exists(), "status": "not_run"},
            "world_seed": {"passed": True, "status": "not_run"},
            "frobenius": {"passed": True, "status": "not_run"},
        }
    selected_run = runs[runs["run_id"] == candidate["selected_representative_run"]].iloc[0]
    representative_basis = np.load(root / str(selected_run["basis_path"]), allow_pickle=False)
    subset = pd.read_csv(root / "grouped_subset_diagnostics.csv")
    subset_matches = pd.read_csv(root / "grouped_subset_structure_matches.csv")
    subset_bad: list[str] = []
    counts = np.zeros(int(candidate["selected_rank"]), dtype=np.int64)
    all_similarities: list[float] = []
    for row in subset.itertuples(index=False):
        basis_path = root / str(row.basis_path)
        if row.model_status != "completed" or not basis_path.is_file() or sha256_file(basis_path) != str(row.basis_sha256):
            subset_bad.append(str(row.subset_id))
            continue
        basis = np.load(basis_path, allow_pickle=False)
        matches = _component_matches(representative_basis, basis)
        similarities = np.asarray([item["js_similarity"] for item in matches])
        all_similarities.extend(similarities.tolist())
        counts += (similarities >= contract["matching_and_stability"]["grouped_subset"]["component_similarity_min"]).astype(np.int64)
        if not np.isclose(float(np.median(similarities)), float(row.median_similarity), rtol=1e-9, atol=1e-12):
            subset_bad.append(str(row.subset_id))
    stable_fraction = float(
        np.mean(counts >= contract["matching_and_stability"]["grouped_subset"]["required_subset_survival_count"])
    )
    subset_passed = (
        len(subset) == contract["matching_and_stability"]["grouped_subset"]["count"]
        and subset["group_preserving"].astype(bool).all()
        and not subset_bad
        and (float(np.median(all_similarities)) if all_similarities else 0.0)
        >= contract["matching_and_stability"]["grouped_subset"]["median_similarity_min"]
        and stable_fraction >= contract["matching_and_stability"]["grouped_subset"]["stable_component_fraction_min"]
        and len(subset_matches) == len(subset) * int(candidate["selected_rank"])
    )
    worlds = pd.read_csv(root / "world_seed_diagnostics.csv")
    world_bad: list[int] = []
    for row in worlds.itertuples(index=False):
        basis_path = root / str(row.basis_path)
        if row.model_status != "completed" or not basis_path.is_file() or sha256_file(basis_path) != str(row.basis_sha256):
            world_bad.append(int(row.world_seed))
            continue
        median = float(np.median([item["js_similarity"] for item in _component_matches(representative_basis, np.load(basis_path, allow_pickle=False))]))
        if not np.isclose(median, float(row.median_similarity), rtol=1e-9, atol=1e-12):
            world_bad.append(int(row.world_seed))
    world_passed = (
        set(worlds["world_seed"].astype(int))
        == set(contract["matching_and_stability"]["world_seed_sensitivity"]["fit_world_seeds"])
        and worlds["selected_rank_unchanged"].astype(bool).all()
        and not world_bad
    )
    frobenius = pd.read_csv(root / "frobenius_sensitivity.csv")
    frobenius_bad: list[str] = []
    for row in frobenius.itertuples(index=False):
        basis_path = root / str(row.basis_path)
        if row.model_status != "completed" or not basis_path.is_file() or sha256_file(basis_path) != str(row.basis_sha256):
            frobenius_bad.append(f"{row.rank}:{row.seed}")
    grid = contract["rank_grid"]
    selected_index = grid.index(int(candidate["selected_rank"]))
    expected_ranks = grid[max(0, selected_index - 1) : selected_index + 2]
    expected_count = len(expected_ranks) * len(contract["references"]["frobenius_nmf"]["seeds"])
    frobenius_passed = (
        len(frobenius) == expected_count
        and not frobenius["influenced_primary_selection"].astype(bool).any()
        and (frobenius["primary_selected_rank_before_sensitivity"].astype(int) == int(candidate["selected_rank"])).all()
        and (frobenius["primary_selected_rank_after_sensitivity"].astype(int) == int(candidate["selected_rank"])).all()
        and not frobenius_bad
    )
    return {
        "grouped_subset": {
            "passed": subset_passed,
            "bad_subsets": subset_bad,
            "stable_component_fraction": stable_fraction,
        },
        "world_seed": {"passed": world_passed, "bad_world_seeds": world_bad},
        "frobenius": {"passed": frobenius_passed, "bad_models": frobenius_bad},
    }
