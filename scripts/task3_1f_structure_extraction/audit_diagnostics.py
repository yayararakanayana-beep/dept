from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .contract import sha256_file
from .audit_matches import _component_matches


def _expected_subset_indices(metadata: pd.DataFrame, contract: dict[str, Any]) -> dict[str, list[int]]:
    required = {
        "bundle_row_index",
        "distribution_group",
        "external_vector_id",
        "source_run_id",
        "active_factor_count",
        "vector_origin",
    }
    missing = required - set(metadata.columns)
    if missing:
        raise ValueError(f"fit metadata missing subset columns: {sorted(missing)}")
    grouped_rows: list[dict[str, Any]] = []
    for row in metadata.itertuples(index=False):
        if str(row.distribution_group) == "external_augmented":
            group_key = f"external|{int(row.active_factor_count)}|{row.vector_origin}|{row.external_vector_id}"
            stratum = f"{int(row.active_factor_count)}|{row.vector_origin}"
        else:
            group_key = f"base|{row.source_run_id}"
            stratum = "base"
        grouped_rows.append(
            {
                "row_index": int(row.bundle_row_index),
                "group_key": group_key,
                "stratum": stratum,
            }
        )
    groups = (
        pd.DataFrame(grouped_rows)
        .groupby(["stratum", "group_key"])["row_index"]
        .apply(list)
        .reset_index()
    )
    config = contract["matching_and_stability"]["grouped_subset"]
    expected: dict[str, list[int]] = {}
    for salt in config["salts"]:
        included: list[int] = []
        for group in groups.itertuples(index=False):
            value = int(
                hashlib.sha256(f"{salt}|{group.stratum}|{group.group_key}".encode()).hexdigest(),
                16,
            ) / 2**256
            if value < float(config["fit_fraction"]):
                included.extend(int(index) for index in group.row_index)
        expected[str(salt)] = sorted(included)
    return expected


def _load_activation_shape(basis_path: Path, name: str) -> tuple[int, ...]:
    activation_path = basis_path.with_name(name)
    if not activation_path.is_file():
        raise FileNotFoundError(activation_path)
    return tuple(np.load(activation_path, allow_pickle=False).shape)


def _diagnostic_checks(
    root: Path,
    candidate: dict[str, Any],
    runs: pd.DataFrame,
    contract: dict[str, Any],
) -> dict[str, Any]:
    if candidate.get("selection_status") != "selected":
        return {
            "grouped_subset": {
                "passed": not (root / "selection_lock.json").exists(),
                "status": "not_run",
            },
            "world_seed": {"passed": True, "status": "not_run"},
            "frobenius": {"passed": True, "status": "not_run"},
        }

    selected_run = runs[runs["run_id"] == candidate["selected_representative_run"]].iloc[0]
    representative_basis = np.load(root / str(selected_run["basis_path"]), allow_pickle=False)
    fit_metadata = pd.read_csv(root / "evidence/fit_evaluation_metadata.csv")
    validation_rows = len(pd.read_csv(root / "evidence/validation_row_map.csv"))

    subset = pd.read_csv(root / "grouped_subset_diagnostics.csv")
    subset_matches = pd.read_csv(root / "grouped_subset_structure_matches.csv")
    expected_subsets = _expected_subset_indices(fit_metadata, contract)
    subset_bad: list[str] = []
    counts = np.zeros(int(candidate["selected_rank"]), dtype=np.int64)
    all_similarities: list[float] = []
    seen_subset_ids: set[str] = set()
    for row in subset.itertuples(index=False):
        subset_id = str(row.subset_id)
        seen_subset_ids.add(subset_id)
        basis_path = root / str(row.basis_path)
        try:
            stored_indices = sorted(int(value) for value in json.loads(str(row.included_row_indices_json)))
        except Exception:
            subset_bad.append(subset_id)
            continue
        expected_indices = expected_subsets.get(subset_id)
        if expected_indices is None or stored_indices != expected_indices:
            subset_bad.append(subset_id)
            continue
        expected_group_preserving = True
        if bool(row.group_preserving) is not expected_group_preserving:
            subset_bad.append(subset_id)
            continue
        if (
            row.model_status != "completed"
            or not basis_path.is_file()
            or sha256_file(basis_path) != str(row.basis_sha256)
        ):
            subset_bad.append(subset_id)
            continue
        if _load_activation_shape(basis_path, "fit_activations.npy")[0] != len(expected_indices):
            subset_bad.append(subset_id)
            continue
        if _load_activation_shape(basis_path, "validation_activations.npy")[0] != validation_rows:
            subset_bad.append(subset_id)
            continue
        basis = np.load(basis_path, allow_pickle=False)
        matches = _component_matches(representative_basis, basis)
        similarities = np.asarray([item["js_similarity"] for item in matches])
        all_similarities.extend(similarities.tolist())
        counts += (
            similarities
            >= contract["matching_and_stability"]["grouped_subset"][
                "component_similarity_min"
            ]
        ).astype(np.int64)
        if not np.isclose(
            float(np.median(similarities)),
            float(row.median_similarity),
            rtol=1e-9,
            atol=1e-12,
        ):
            subset_bad.append(subset_id)

    stable_fraction = float(
        np.mean(
            counts
            >= contract["matching_and_stability"]["grouped_subset"][
                "required_subset_survival_count"
            ]
        )
    )
    expected_subset_ids = set(expected_subsets)
    subset_passed = (
        len(subset)
        == contract["matching_and_stability"]["grouped_subset"]["count"]
        and seen_subset_ids == expected_subset_ids
        and not subset_bad
        and (float(np.median(all_similarities)) if all_similarities else 0.0)
        >= contract["matching_and_stability"]["grouped_subset"][
            "median_similarity_min"
        ]
        and stable_fraction
        >= contract["matching_and_stability"]["grouped_subset"][
            "stable_component_fraction_min"
        ]
        and len(subset_matches) == len(subset) * int(candidate["selected_rank"])
    )

    worlds = pd.read_csv(root / "world_seed_diagnostics.csv")
    world_bad: list[int] = []
    for row in worlds.itertuples(index=False):
        world_seed = int(row.world_seed)
        basis_path = root / str(row.basis_path)
        expected_rows = int((fit_metadata["seed"].astype(int) == world_seed).sum())
        if (
            row.model_status != "completed"
            or not basis_path.is_file()
            or sha256_file(basis_path) != str(row.basis_sha256)
            or int(row.row_count) != expected_rows
            or int(row.selected_rank) != int(candidate["selected_rank"])
            or not bool(row.selected_rank_unchanged)
        ):
            world_bad.append(world_seed)
            continue
        if _load_activation_shape(basis_path, "fit_activations.npy")[0] != expected_rows:
            world_bad.append(world_seed)
            continue
        if _load_activation_shape(basis_path, "validation_activations.npy")[0] != validation_rows:
            world_bad.append(world_seed)
            continue
        median = float(
            np.median(
                [
                    item["js_similarity"]
                    for item in _component_matches(
                        representative_basis,
                        np.load(basis_path, allow_pickle=False),
                    )
                ]
            )
        )
        if not np.isclose(
            median,
            float(row.median_similarity),
            rtol=1e-9,
            atol=1e-12,
        ):
            world_bad.append(world_seed)
    world_passed = (
        set(worlds["world_seed"].astype(int))
        == set(
            contract["matching_and_stability"]["world_seed_sensitivity"][
                "fit_world_seeds"
            ]
        )
        and not world_bad
    )

    frobenius = pd.read_csv(root / "frobenius_sensitivity.csv")
    frobenius_bad: list[str] = []
    fit_rows = len(fit_metadata)
    for row in frobenius.itertuples(index=False):
        identifier = f"{row.rank}:{row.seed}"
        basis_path = root / str(row.basis_path)
        if (
            row.model_status != "completed"
            or not basis_path.is_file()
            or sha256_file(basis_path) != str(row.basis_sha256)
        ):
            frobenius_bad.append(identifier)
            continue
        if _load_activation_shape(basis_path, "fit_activations.npy")[0] != fit_rows:
            frobenius_bad.append(identifier)
            continue
        if _load_activation_shape(basis_path, "validation_activations.npy")[0] != validation_rows:
            frobenius_bad.append(identifier)
            continue
        if (
            int(row.primary_selected_rank_before_sensitivity)
            != int(candidate["selected_rank"])
            or int(row.primary_selected_rank_after_sensitivity)
            != int(candidate["selected_rank"])
            or bool(row.influenced_primary_selection)
        ):
            frobenius_bad.append(identifier)
    grid = contract["rank_grid"]
    selected_index = grid.index(int(candidate["selected_rank"]))
    expected_ranks = grid[max(0, selected_index - 1) : selected_index + 2]
    expected_pairs = {
        (int(rank), int(seed))
        for rank in expected_ranks
        for seed in contract["references"]["frobenius_nmf"]["seeds"]
    }
    actual_pairs = {
        (int(row.rank), int(row.seed)) for row in frobenius.itertuples(index=False)
    }
    frobenius_passed = actual_pairs == expected_pairs and not frobenius_bad

    return {
        "grouped_subset": {
            "passed": subset_passed,
            "bad_subsets": sorted(set(subset_bad)),
            "stable_component_fraction": stable_fraction,
        },
        "world_seed": {
            "passed": world_passed,
            "bad_world_seeds": sorted(set(world_bad)),
        },
        "frobenius": {
            "passed": frobenius_passed,
            "bad_models": sorted(set(frobenius_bad)),
        },
    }
