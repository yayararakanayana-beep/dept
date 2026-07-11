from __future__ import annotations

import json
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

from task3_1f_structure_extraction import freeze_input, validate_smoke
from task3_1f_structure_extraction.contract import DEFAULT_CONTRACT


def clone_output(valid: dict[str, Path], tmp_path: Path) -> Path:
    target = tmp_path / "artifact"
    shutil.copytree(valid["output"], target)
    return target


def failures(valid: dict[str, Path], artifact: Path) -> set[str]:
    checks = validate_smoke(
        artifact,
        valid["bundles"] / "fit_bundle.npz", valid["bundles"] / "fit_row_map.csv",
        valid["bundles"] / "validation_bundle.npz", valid["bundles"] / "validation_row_map.csv",
        DEFAULT_CONTRACT, write_outputs=False,
    )
    return {name for name, result in checks.items() if not result["passed"]}


def test_rejects_negative_basis(valid_pipeline: dict[str, Path], tmp_path: Path) -> None:
    artifact = clone_output(valid_pipeline, tmp_path)
    path = artifact / "models/nmf_kl_rank05_anchor/basis.npy"
    basis = np.load(path, allow_pickle=False)
    basis[0, 0] = -0.1
    np.save(path, basis)
    assert {"model_hashes_valid", "basis_and_activations_valid"} & failures(valid_pipeline, artifact)


def test_rejects_corrupt_activation(valid_pipeline: dict[str, Path], tmp_path: Path) -> None:
    artifact = clone_output(valid_pipeline, tmp_path)
    path = artifact / "models/nmf_kl_rank05_anchor/fit_activations.npy"
    values = np.load(path, allow_pickle=False)
    values[0, 0] = np.nan
    np.save(path, values)
    assert {"model_hashes_valid", "basis_and_activations_valid"} & failures(valid_pipeline, artifact)


def test_rejects_forged_metrics(valid_pipeline: dict[str, Path], tmp_path: Path) -> None:
    artifact = clone_output(valid_pipeline, tmp_path)
    metrics = pd.read_csv(artifact / "reconstruction_metrics.csv")
    metrics["value"] = 0.0
    metrics.to_csv(artifact / "reconstruction_metrics.csv", index=False)
    assert "reconstruction_metrics_recomputed" in failures(valid_pipeline, artifact)


def test_rejects_forged_component_matches(valid_pipeline: dict[str, Path], tmp_path: Path) -> None:
    artifact = clone_output(valid_pipeline, tmp_path)
    matches = pd.read_csv(artifact / "component_matches.csv")
    matches["js_similarity"] = 1.0
    matches.to_csv(artifact / "component_matches.csv", index=False)
    assert "component_matching_recomputed" in failures(valid_pipeline, artifact)


def test_rejects_holdout_access_flag(valid_pipeline: dict[str, Path], tmp_path: Path) -> None:
    artifact = clone_output(valid_pipeline, tmp_path)
    path = artifact / "smoke_stage_manifest.json"
    stage = json.loads(path.read_text(encoding="utf-8"))
    stage["holdout_accessed"] = True
    path.write_text(json.dumps(stage), encoding="utf-8")
    assert "holdout_isolation_valid" in failures(valid_pipeline, artifact)


def test_rejects_missing_run(valid_pipeline: dict[str, Path], tmp_path: Path) -> None:
    artifact = clone_output(valid_pipeline, tmp_path)
    runs = pd.read_csv(artifact / "model_runs.csv")
    runs = runs[runs["run_id"] != "nmf_kl_rank05_seed31016"]
    runs.to_csv(artifact / "model_runs.csv", index=False)
    assert "model_run_completeness" in failures(valid_pipeline, artifact)


def test_input_freeze_rejects_nan(valid_pipeline: dict[str, Path], tmp_path: Path) -> None:
    artifact = tmp_path / "input"
    shutil.copytree(valid_pipeline["input"], artifact)
    mass = np.load(artifact / "mass_matrix.npy", allow_pickle=False)
    mass[0, 0] = np.nan
    np.save(artifact / "mass_matrix.npy", mass)
    with pytest.raises(ValueError, match="non-finite"):
        freeze_input(artifact, tmp_path / "frozen", "smoke", DEFAULT_CONTRACT)


def test_input_freeze_rejects_split_leak(valid_pipeline: dict[str, Path], tmp_path: Path) -> None:
    artifact = tmp_path / "input"
    shutil.copytree(valid_pipeline["input"], artifact)
    metadata = pd.read_csv(artifact / "snapshot_metadata.csv")
    discovery = pd.read_csv(artifact / "discovery_manifest.csv")
    metadata.loc[0, "dataset_split"] = "holdout"
    discovery.loc[0, "dataset_split"] = "holdout"
    metadata.to_csv(artifact / "snapshot_metadata.csv", index=False)
    discovery.to_csv(artifact / "discovery_manifest.csv", index=False)
    with pytest.raises(ValueError, match="split row counts"):
        freeze_input(artifact, tmp_path / "frozen", "smoke", DEFAULT_CONTRACT)
