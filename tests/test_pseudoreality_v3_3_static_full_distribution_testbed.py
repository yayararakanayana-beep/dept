from __future__ import annotations
import json
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
def valid_smoke_artifact(tmp_path_factory: pytest.TempPathFactory) -> Path:
    root = tmp_path_factory.mktemp("task3_1e_smoke")
    artifact = generator.build("smoke", root, generator.DEFAULT_CONFIG)
    audit.run_audit(artifact, "smoke", generator.DEFAULT_CONFIG)
    checks = validator.validate_artifacts(artifact, "smoke", generator.DEFAULT_CONFIG, write_outputs=True)
    assert all(payload["passed"] for payload in checks.values()), checks
    return artifact

def test_smoke_artifact_contract(valid_smoke_artifact: Path) -> None:
    artifact = valid_smoke_artifact
    mass = np.load(artifact / "mass_matrix.npy", allow_pickle=False)
    pool_mass = np.load(artifact / "adaptive_pool_mass_matrix.npy", allow_pickle=False)
    vectors = pd.read_csv(artifact / "external_vectors.csv")
    metadata = pd.read_csv(artifact / "snapshot_metadata.csv")
    pairs = pd.read_csv(artifact / "matched_pairs.csv")
    additions = pd.read_csv(artifact / "coverage_additions.csv")
    coverage = pd.read_csv(artifact / "coverage_summary.csv")
    assert mass.shape == (41, 3125)
    assert mass.dtype == np.float64
    assert pool_mass.shape == (8, 3125)
    assert len(vectors) == 19
    assert len(metadata) == 41
    assert len(pairs) == 32
    assert len(additions) == 2
    assert coverage["coverage_stage"].tolist() == ["before_adaptive", "after_adaptive"]
    assert coverage.loc[0, "nearest_neighbor_js_max"] > 0.0
    assert coverage.loc[1, "nearest_neighbor_js_max"] <= coverage.loc[0, "nearest_neighbor_js_max"] + 1e-12

def test_discovery_manifest_has_only_four_columns(valid_smoke_artifact: Path) -> None:
    discovery = pd.read_csv(valid_smoke_artifact / "discovery_manifest.csv")
    assert list(discovery.columns) == ["matrix_row_index", "snapshot_id", "dataset_split", "analysis_weight"]
    assert not set(generator.EXTERNAL_COLUMNS) & set(discovery.columns)

def test_configuration_is_execution_source(tmp_path: Path) -> None:
    config = json.loads(generator.DEFAULT_CONFIG.read_text(encoding="utf-8"))
    smoke = config["profiles"]["smoke"]
    smoke["capture_steps"]["external"] = [1]
    smoke["capture_steps"]["base"] = [0, 1]
    smoke["adaptive_reference_step"] = 1
    custom_config = tmp_path / "custom_config.json"
    custom_config.write_text(json.dumps(config), encoding="utf-8")
    artifact = generator.build("smoke", tmp_path / "artifacts", custom_config)
    metadata = pd.read_csv(artifact / "snapshot_metadata.csv")
    assert sorted(metadata.loc[metadata["distribution_group"] == "external_augmented", "source_step"].unique()) == [1]
    assert sorted(metadata.loc[metadata["distribution_group"] == "base_v3_3", "source_step"].unique()) == [0, 1]
    assert len(metadata) == 22

def test_same_source_run_id_spans_capture_steps(valid_smoke_artifact: Path) -> None:
    metadata = pd.read_csv(valid_smoke_artifact / "snapshot_metadata.csv")
    external = metadata[metadata["distribution_group"] == "external_augmented"]
    assert set(external.groupby("source_run_id")["source_step"].nunique()) == {2}
    base = metadata[metadata["distribution_group"] == "base_v3_3"]
    assert set(base.groupby("source_run_id")["source_step"].nunique()) == {3}

def test_quality_checks_contain_measured_evidence(valid_smoke_artifact: Path) -> None:
    checks = json.loads((valid_smoke_artifact / "quality_checks.json").read_text(encoding="utf-8"))
    assert checks["mass_matrix_valid"]["checked_rows"] == 41
    assert checks["mass_matrix_valid"]["evidence_source"] == "mass_matrix.npy"
    assert checks["coverage_summary_recomputed_valid"]["before_max"] > 0.0
    assert all(isinstance(payload, dict) and "passed" in payload for payload in checks.values())

def test_artifact_manifest_is_type_aware(valid_smoke_artifact: Path) -> None:
    manifest = json.loads((valid_smoke_artifact / "artifact_manifest.json").read_text(encoding="utf-8"))
    entries = {entry["path"]: entry for entry in manifest["files"]}
    assert entries["external_vectors.csv"]["row_count"] == 19
    assert entries["mass_matrix.npy"]["shape"] == [41, 3125]
    assert entries["terrain_reference.npz"]["members"]["short_payoff"]["shape"] == [41, 3125]
