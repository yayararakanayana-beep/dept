from __future__ import annotations
import shutil
import sys
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
import pseudoreality_v3_3_static_full_distribution_coverage_audit as audit
import pseudoreality_v3_3_static_full_distribution_testbed as generator
import pseudoreality_v3_3_static_full_distribution_validator as validator

@pytest.fixture(scope="module")
def source_artifact(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("task3_1e_negative_source")
    artifact = generator.build("smoke", root, generator.DEFAULT_CONFIG)
    audit.run_audit(artifact, "smoke", generator.DEFAULT_CONFIG)
    checks = validator.validate_artifacts(artifact, "smoke", generator.DEFAULT_CONFIG, write_outputs=True)
    assert all(payload["passed"] for payload in checks.values())
    return artifact

def copied(source: Path, tmp_path: Path) -> Path:
    target = tmp_path / generator.OUT_SUBDIR
    shutil.copytree(source, target)
    return target

def failed_checks(artifact: Path) -> set[str]:
    checks = validator.validate_artifacts(artifact, "smoke", generator.DEFAULT_CONFIG, write_outputs=False)
    return {name for name, payload in checks.items() if not payload["passed"]}

def test_rejects_mass_sum_corruption(source_artifact: Path, tmp_path: Path) -> None:
    artifact = copied(source_artifact, tmp_path)
    mass = np.load(artifact / "mass_matrix.npy", allow_pickle=False); mass[0] *= 0.9
    np.save(artifact / "mass_matrix.npy", mass)
    assert "mass_matrix_valid" in failed_checks(artifact)

def test_rejects_nonfinite_mass(source_artifact: Path, tmp_path: Path) -> None:
    artifact = copied(source_artifact, tmp_path)
    mass = np.load(artifact / "mass_matrix.npy", allow_pickle=False); mass[0, 0] = np.nan
    np.save(artifact / "mass_matrix.npy", mass)
    assert "mass_matrix_valid" in failed_checks(artifact)

def test_rejects_cross_split_duplicate_vector(source_artifact: Path, tmp_path: Path) -> None:
    artifact = copied(source_artifact, tmp_path)
    vectors = pd.read_csv(artifact / "external_vectors.csv")
    fit_index = vectors[(vectors["dataset_split"] == "fit") & (~vectors["is_base_vector"].astype(bool))].index[0]
    validation_index = vectors[(vectors["dataset_split"] == "validation") & (~vectors["is_base_vector"].astype(bool))].index[0]
    vectors.loc[validation_index, generator.EXTERNAL_COLUMNS] = vectors.loc[fit_index, generator.EXTERNAL_COLUMNS].to_numpy()
    vectors.to_csv(artifact / "external_vectors.csv", index=False)
    assert "split_vector_sets_disjoint" in failed_checks(artifact)

def test_rejects_missing_terrain_field(source_artifact: Path, tmp_path: Path) -> None:
    artifact = copied(source_artifact, tmp_path)
    with np.load(artifact / "terrain_reference.npz", allow_pickle=False) as archive:
        members = {name: archive[name] for name in archive.files if name != "short_payoff"}
    np.savez(artifact / "terrain_reference.npz", **members)
    assert "terrain_reference_valid" in failed_checks(artifact)

def test_rejects_zero_filled_coverage(source_artifact: Path, tmp_path: Path) -> None:
    artifact = copied(source_artifact, tmp_path)
    coverage = pd.read_csv(artifact / "coverage_summary.csv")
    for column in [name for name in coverage.columns if name.startswith("nearest_neighbor_js_")]:
        coverage[column] = 0.0
    coverage.to_csv(artifact / "coverage_summary.csv", index=False)
    assert "coverage_summary_recomputed_valid" in failed_checks(artifact)

def test_rejects_missing_adaptive_selection(source_artifact: Path, tmp_path: Path) -> None:
    artifact = copied(source_artifact, tmp_path)
    pd.read_csv(artifact / "coverage_additions.csv").iloc[:-1].to_csv(artifact / "coverage_additions.csv", index=False)
    assert "adaptive_selection_replay_valid" in failed_checks(artifact)

def test_rejects_mismatched_base_pair(source_artifact: Path, tmp_path: Path) -> None:
    artifact = copied(source_artifact, tmp_path)
    pairs = pd.read_csv(artifact / "matched_pairs.csv"); pairs.loc[0, "seed"] = int(pairs.loc[0, "seed"]) + 999
    pairs.to_csv(artifact / "matched_pairs.csv", index=False)
    assert "matched_base_relationships_valid" in failed_checks(artifact)

def test_rejects_discovery_information_leak(source_artifact: Path, tmp_path: Path) -> None:
    artifact = copied(source_artifact, tmp_path)
    discovery = pd.read_csv(artifact / "discovery_manifest.csv"); discovery[generator.EXTERNAL_COLUMNS[0]] = 0.0
    discovery.to_csv(artifact / "discovery_manifest.csv", index=False)
    assert "discovery_manifest_schema_valid" in failed_checks(artifact)
