"""Independent artifact checks for Task 3.1e."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from pseudoreality_v3_3_static_full_distribution_coverage_audit import compute_coverage_summary, replay_selection
from .core import DEFAULT_CONFIG, EXCLUDED_TRANSITION_FIELDS, EXTERNAL_COLUMNS, MASS_TOLERANCE, NEGATIVE_TOLERANCE, RANGES, TERRAIN_FIELDS, load_config
from .validation_common import RAW_REQUIRED_FILES, EXTERNAL_VECTOR_COLUMNS, DISCOVERY_COLUMNS, METADATA_COLUMNS, PAIR_COLUMNS, Recorder, _artifact_dir, _as_bool, expected_counts
from .validation_report import _write_outputs


def validate_artifacts(artifact_root: str | Path, profile: str, config_path: str | Path = DEFAULT_CONFIG, *, write_outputs: bool = True) -> dict[str, dict[str, Any]]:
    config, profile_config = load_config(config_path, profile)
    artifact_dir = _artifact_dir(artifact_root)
    counts = expected_counts(profile_config)
    recorder = Recorder()
    missing = [name for name in RAW_REQUIRED_FILES if not (artifact_dir / name).is_file()]
    recorder.add("required_files_present", not missing, missing_files=missing, required_file_count=len(RAW_REQUIRED_FILES))
    if missing:
        if write_outputs:
            artifact_dir.mkdir(parents=True, exist_ok=True)
            _write_outputs(artifact_dir, profile, counts, recorder, None)
        return recorder.checks

    vectors = pd.read_csv(artifact_dir / "external_vectors.csv")
    pool = pd.read_csv(artifact_dir / "adaptive_pool.csv")
    additions = pd.read_csv(artifact_dir / "coverage_additions.csv")
    metadata = pd.read_csv(artifact_dir / "snapshot_metadata.csv")
    discovery = pd.read_csv(artifact_dir / "discovery_manifest.csv")
    pairs = pd.read_csv(artifact_dir / "matched_pairs.csv")
    coordinates = pd.read_csv(artifact_dir / "cell_coordinates.csv")
    terrain_catalog = pd.read_csv(artifact_dir / "terrain_field_catalog.csv")
    mass = np.load(artifact_dir / "mass_matrix.npy", allow_pickle=False)
    pool_mass = np.load(artifact_dir / "adaptive_pool_mass_matrix.npy", allow_pickle=False)
    coverage = pd.read_csv(artifact_dir / "coverage_summary.csv")
    generation_metadata = json.loads((artifact_dir / "generation_metadata.json").read_text(encoding="utf-8"))

    recorder.add("schema_dimensions_valid", config["axis_count"] == 5 and config["n_bins"] == 5 and config["cell_count"] == 3125, axis_count=config["axis_count"], n_bins=config["n_bins"], cell_count=config["cell_count"])
    recorder.add("external_vector_schema_valid", list(vectors.columns) == EXTERNAL_VECTOR_COLUMNS, actual_columns=list(vectors.columns), expected_columns=EXTERNAL_VECTOR_COLUMNS)
    recorder.add("discovery_manifest_schema_valid", list(discovery.columns) == DISCOVERY_COLUMNS, actual_columns=list(discovery.columns), forbidden_external_columns=sorted(set(discovery.columns) & set(EXTERNAL_COLUMNS)))
    recorder.add("snapshot_metadata_schema_valid", list(metadata.columns) == METADATA_COLUMNS, actual_columns=list(metadata.columns))
    recorder.add("matched_pair_schema_valid", list(pairs.columns) == PAIR_COLUMNS, actual_columns=list(pairs.columns))

    def external_values_check() -> dict[str, Any]:
        invalid = 0
        for column in EXTERNAL_COLUMNS:
            values = pd.to_numeric(vectors[column], errors="coerce").to_numpy(dtype=np.float64)
            low, high = RANGES[column]
            invalid += int((~np.isfinite(values) | (values < low) | (values > high)).sum())
        return {"passed": invalid == 0, "checked_rows": len(vectors), "invalid_value_count": invalid}
    recorder.guard("external_values_valid", external_values_check)

    def base_external_check() -> dict[str, Any]:
        base = _as_bool(vectors["is_base_vector"])
        value_matrix = vectors[EXTERNAL_COLUMNS].to_numpy(dtype=np.float64)
        base_zero = np.all(np.isclose(value_matrix[base], 0.0, rtol=0.0, atol=0.0))
        nonbase_not_zero = np.all(~np.all(np.isclose(value_matrix[~base], 0.0, rtol=0.0, atol=0.0), axis=1))
        origins = set(vectors.loc[base, "vector_origin"])
        return {"passed": bool(base_zero and nonbase_not_zero and origins == {"base"} and int(base.sum()) == 3), "base_row_count": int(base.sum()), "base_origins": sorted(origins)}
    recorder.guard("base_external_separation_valid", base_external_check)

    def split_disjoint_check() -> dict[str, Any]:
        nonbase = vectors[~_as_bool(vectors["is_base_vector"])].copy()
        sets = {split: {tuple(round(float(value), 12) for value in row) for row in nonbase.loc[nonbase["dataset_split"] == split, EXTERNAL_COLUMNS].to_numpy()} for split in ("fit", "validation", "holdout")}
        overlaps = {"fit_validation": len(sets["fit"] & sets["validation"]), "fit_holdout": len(sets["fit"] & sets["holdout"]), "validation_holdout": len(sets["validation"] & sets["holdout"])}
        return {"passed": all(count == 0 for count in overlaps.values()), **overlaps, "rounding_digits": 12}
    recorder.guard("split_vector_sets_disjoint", split_disjoint_check)

    def vector_count_check() -> dict[str, Any]:
        base = _as_bool(vectors["is_base_vector"])
        actual = {
            "fit_nonbase_before_adaptive": int(((vectors["dataset_split"] == "fit") & ~base & (vectors["vector_origin"] != "adaptive_maximin")).sum()),
            "fit_nonbase": int(((vectors["dataset_split"] == "fit") & ~base).sum()),
            "validation_nonbase": int(((vectors["dataset_split"] == "validation") & ~base).sum()),
            "holdout_nonbase": int(((vectors["dataset_split"] == "holdout") & ~base).sum()),
            "adaptive_pool": len(pool), "adaptive_selected": len(additions), "external_vector_total": len(vectors),
        }
        expected = {key: counts[key] for key in actual}
        return {"passed": actual == expected, "actual": actual, "expected": expected}
    recorder.guard("configured_vector_counts_valid", vector_count_check)

    def config_application_check() -> dict[str, Any]:
        expected_seed_sets = {split: sorted(profile_config["world_seeds"][split]) for split in ("fit", "validation", "holdout")}
        actual_seed_sets = {split: sorted(int(value) for value in metadata.loc[metadata["dataset_split"] == split, "seed"].unique()) for split in ("fit", "validation", "holdout")}
        actual_base_steps = sorted(int(value) for value in metadata.loc[metadata["distribution_group"] == "base_v3_3", "source_step"].unique())
        actual_external_steps = sorted(int(value) for value in metadata.loc[metadata["distribution_group"] == "external_augmented", "source_step"].unique())
        passed = actual_seed_sets == expected_seed_sets and actual_base_steps == profile_config["capture_steps"]["base"] and actual_external_steps == profile_config["capture_steps"]["external"] and set(metadata["capture_policy"]) == {config["capture_policy"]}
        return {"passed": passed, "actual_seed_sets": actual_seed_sets, "expected_seed_sets": expected_seed_sets, "actual_base_steps": actual_base_steps, "actual_external_steps": actual_external_steps}
    recorder.guard("configuration_applied_to_artifacts", config_application_check)

    def mass_check() -> dict[str, Any]:
        sums = mass.sum(axis=1, dtype=np.float64) if mass.ndim == 2 else np.array([np.nan])
        errors = np.abs(sums - 1.0)
        invalid_rows = int((~np.isfinite(mass).all(axis=1)).sum()) if mass.ndim == 2 else 1
        negative_rows = int((np.min(mass, axis=1) < -NEGATIVE_TOLERANCE).sum()) if mass.ndim == 2 else 1
        passed = mass.shape == (counts["snapshot_total"], int(config["cell_count"])) and mass.dtype == np.float64 and invalid_rows == 0 and negative_rows == 0 and float(np.max(errors)) <= MASS_TOLERANCE
        return {"passed": passed, "shape": list(mass.shape), "dtype": str(mass.dtype), "checked_rows": int(mass.shape[0]) if mass.ndim == 2 else 0, "nonfinite_row_count": invalid_rows, "negative_row_count": negative_rows, "maximum_absolute_sum_error": float(np.nanmax(errors)), "tolerance": MASS_TOLERANCE, "evidence_source": "mass_matrix.npy"}
    recorder.guard("mass_matrix_valid", mass_check)

    def row_alignment_check() -> dict[str, Any]:
        indices = metadata["matrix_row_index"].to_numpy(dtype=int)
        aligned = len(metadata) == len(discovery) == mass.shape[0] == counts["snapshot_total"] and np.array_equal(indices, np.arange(len(metadata))) and np.array_equal(discovery["matrix_row_index"].to_numpy(dtype=int), indices) and metadata["snapshot_id"].tolist() == discovery["snapshot_id"].tolist()
        return {"passed": aligned, "metadata_rows": len(metadata), "discovery_rows": len(discovery), "mass_rows": int(mass.shape[0]), "expected_rows": counts["snapshot_total"]}
    recorder.guard("snapshot_row_alignment_valid", row_alignment_check)

    def terrain_check() -> dict[str, Any]:
        with np.load(artifact_dir / "terrain_reference.npz", allow_pickle=False) as archive:
            members = list(archive.files)
            member_info = {field: {"shape": list(archive[field].shape), "dtype": str(archive[field].dtype)} for field in members}
            valid_members = set(members) == set(TERRAIN_FIELDS)
            valid_arrays = all(archive[field].shape == (counts["snapshot_total"], int(config["cell_count"])) and archive[field].dtype == np.float32 and np.isfinite(archive[field]).all() for field in members)
            excluded = sorted(set(members) & set(EXCLUDED_TRANSITION_FIELDS))
        catalog_fields = terrain_catalog["field_name"].tolist()
        return {"passed": valid_members and valid_arrays and not excluded and catalog_fields == TERRAIN_FIELDS, "member_count": len(members), "members": members, "excluded_members_found": excluded, "member_info": member_info}
    recorder.guard("terrain_reference_valid", terrain_check)

    def pair_check() -> dict[str, Any]:
        metadata_by_id = metadata.set_index("snapshot_id", drop=False)
        invalid = 0
        for row in pairs.itertuples(index=False):
            if row.external_snapshot_id not in metadata_by_id.index or row.base_snapshot_id not in metadata_by_id.index:
                invalid += 1
                continue
            external_row = metadata_by_id.loc[row.external_snapshot_id]
            base_row = metadata_by_id.loc[row.base_snapshot_id]
            if external_row["distribution_group"] != "external_augmented" or base_row["distribution_group"] != "base_v3_3" or external_row["dataset_split"] != base_row["dataset_split"] or int(external_row["seed"]) != int(base_row["seed"]) or int(external_row["source_step"]) != int(base_row["source_step"]) or external_row["matched_base_snapshot_id"] != row.base_snapshot_id or row.dataset_split != external_row["dataset_split"] or int(row.seed) != int(external_row["seed"]) or int(row.source_step) != int(external_row["source_step"]) or row.pair_quality != "exact":
                invalid += 1
        return {"passed": len(pairs) == counts["nonbase_snapshots"] and invalid == 0, "pair_rows": len(pairs), "expected_pair_rows": counts["nonbase_snapshots"], "invalid_pair_rows": invalid}
    recorder.guard("matched_base_relationships_valid", pair_check)

    def weight_check() -> dict[str, Any]:
        weights = discovery["analysis_weight"].to_numpy(dtype=np.float64)
        means = discovery.groupby("dataset_split")["analysis_weight"].mean().to_dict()
        passed = np.isfinite(weights).all() and np.all(weights > 0.0) and all(np.isclose(float(value), 1.0, rtol=0.0, atol=1e-12) for value in means.values())
        return {"passed": bool(passed), "split_means": means, "minimum_weight": float(weights.min())}
    recorder.guard("analysis_weights_valid", weight_check)

    def coordinate_check() -> dict[str, Any]:
        expected_columns = ["cell_id"] + [f"dim{i}_bin" for i in range(5)] + [f"dim{i}_value" for i in range(5)]
        return {"passed": list(coordinates.columns) == expected_columns and len(coordinates) == int(config["cell_count"]) and coordinates["cell_id"].tolist() == list(range(int(config["cell_count"]))), "row_count": len(coordinates), "columns": list(coordinates.columns)}
    recorder.guard("cell_coordinates_valid", coordinate_check)

    def adaptive_check() -> dict[str, Any]:
        _, _, _, replayed = replay_selection(artifact_dir, profile_config)
        return {"passed": len(replayed) == counts["adaptive_selected"] and pool_mass.shape == (counts["adaptive_pool"], int(config["cell_count"])) and pool_mass.dtype == np.float64 and np.isfinite(pool_mass).all(), "candidate_pool_count": len(pool), "selected_count": len(replayed), "pool_mass_shape": list(pool_mass.shape)}
    recorder.guard("adaptive_selection_replay_valid", adaptive_check)

    recomputed_coverage: pd.DataFrame | None = None
    def coverage_check() -> dict[str, Any]:
        nonlocal recomputed_coverage
        recomputed_coverage = compute_coverage_summary(artifact_dir, profile, config_path)
        expected_columns = list(recomputed_coverage.columns)
        actual_sorted = coverage.sort_values("coverage_stage").reset_index(drop=True)
        expected_sorted = recomputed_coverage.sort_values("coverage_stage").reset_index(drop=True)
        schema_ok = list(coverage.columns) == expected_columns
        values_ok = schema_ok and len(actual_sorted) == len(expected_sorted)
        maximum_error = 0.0
        if values_ok:
            for column in expected_columns:
                if column == "coverage_stage":
                    values_ok = values_ok and actual_sorted[column].tolist() == expected_sorted[column].tolist()
                elif column in ("evaluation_count", "reference_count"):
                    values_ok = values_ok and np.array_equal(actual_sorted[column].to_numpy(dtype=int), expected_sorted[column].to_numpy(dtype=int))
                else:
                    errors = np.abs(actual_sorted[column].to_numpy(dtype=np.float64) - expected_sorted[column].to_numpy(dtype=np.float64))
                    maximum_error = max(maximum_error, float(errors.max(initial=0.0)))
                    values_ok = values_ok and bool(np.all(errors <= 1e-12))
        before = expected_sorted[expected_sorted["coverage_stage"] == "before_adaptive"].iloc[0]
        after = expected_sorted[expected_sorted["coverage_stage"] == "after_adaptive"].iloc[0]
        meaningful = float(before["nearest_neighbor_js_max"]) > 0.0 and float(before["nearest_neighbor_js_median"]) > 0.0
        improved = float(after["nearest_neighbor_js_max"]) <= float(before["nearest_neighbor_js_max"]) + 1e-12
        return {"passed": bool(values_ok and meaningful and improved), "maximum_recompute_error": maximum_error, "before_max": float(before["nearest_neighbor_js_max"]), "before_median": float(before["nearest_neighbor_js_median"]), "after_max": float(after["nearest_neighbor_js_max"]), "evidence_source": "coverage_summary.csv + persisted mass artifacts"}
    recorder.guard("coverage_summary_recomputed_valid", coverage_check)

    recorder.add("no_combined_full_stored", not any("combined_full" in column for column in metadata.columns) and not any("combined_full" in column for column in discovery.columns), inspected_files=["snapshot_metadata.csv", "discovery_manifest.csv"])
    recorder.add("generation_metadata_consistent", generation_metadata.get("profile") == profile and int(generation_metadata.get("snapshot_count", -1)) == counts["snapshot_total"] and int(generation_metadata.get("adaptive_pool_count", -1)) == counts["adaptive_pool"] and int(generation_metadata.get("adaptive_selected_count", -1)) == counts["adaptive_selected"], generation_metadata=generation_metadata)
    if write_outputs:
        _write_outputs(artifact_dir, profile, counts, recorder, recomputed_coverage)
    return recorder.checks
