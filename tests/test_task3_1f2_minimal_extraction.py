from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from task3_1f_structure_extraction import (
    match_components,
    normalize_basis_and_activations,
    transform_fixed_kl_basis,
)


def test_input_freeze_contract(valid_pipeline: dict[str, Path]) -> None:
    manifest = json.loads((valid_pipeline["frozen"] / "input_manifest.json").read_text(encoding="utf-8"))
    assert manifest["split_rows"] == {"fit": 23, "validation": 7, "holdout": 11}
    assert manifest["holdout_accessed_by_model_selection"] is False
    for split, count in (("fit", 23), ("validation", 7), ("holdout", 11)):
        with np.load(valid_pipeline["bundles"] / f"{split}_bundle.npz", allow_pickle=False) as bundle:
            assert bundle["mass_matrix"].shape == (count, 3125)
            assert bundle["analysis_weight"].shape == (count,)


def test_smoke_runs_frozen_initializations(valid_pipeline: dict[str, Path]) -> None:
    runs = pd.read_csv(valid_pipeline["output"] / "model_runs.csv")
    nmf = runs[runs["method"] == "nmf_kl"]
    assert len(nmf) == 7
    assert nmf["rank"].tolist() == [5] * 7
    assert nmf.iloc[0]["init_method"] == "nndsvda"
    assert nmf.iloc[1:]["init_seed"].astype(int).tolist() == [31011, 31012, 31013, 31014, 31015, 31016]


def test_basis_and_activations_are_valid(valid_pipeline: dict[str, Path]) -> None:
    runs = pd.read_csv(valid_pipeline["output"] / "model_runs.csv")
    for run in runs[runs["method"] == "nmf_kl"].itertuples(index=False):
        basis = np.load(valid_pipeline["output"] / run.basis_path, allow_pickle=False)
        fit_activation = np.load(valid_pipeline["output"] / run.fit_activation_path, allow_pickle=False)
        validation_activation = np.load(valid_pipeline["output"] / run.validation_activation_path, allow_pickle=False)
        assert basis.shape == (5, 3125)
        assert np.allclose(basis.sum(axis=1), 1.0, rtol=0.0, atol=1e-10)
        assert np.all(basis >= 0.0)
        assert fit_activation.shape == (23, 5)
        assert validation_activation.shape == (7, 5)
        assert np.all(fit_activation >= 0.0)
        assert np.all(validation_activation >= 0.0)


def test_holdout_not_opened(valid_pipeline: dict[str, Path]) -> None:
    stage = json.loads((valid_pipeline["output"] / "smoke_stage_manifest.json").read_text(encoding="utf-8"))
    assert stage["holdout_accessed"] is False
    assert stage["selection_lock_created"] is False
    assert not (valid_pipeline["output"] / "selection_lock.json").exists()
    assert not any("holdout" in path.name.lower() for path in valid_pipeline["output"].rglob("*"))


def test_independent_validator_writes_evidence(valid_pipeline: dict[str, Path]) -> None:
    checks = json.loads((valid_pipeline["output"] / "quality_checks.json").read_text(encoding="utf-8"))
    assert checks["reconstruction_metrics_recomputed"]["checked_count"] > 0
    assert checks["component_matching_recomputed"]["checked_count"] == 105
    assert all(isinstance(value, dict) and "passed" in value for value in checks.values())
    manifest = json.loads((valid_pipeline["output"] / "artifact_manifest.json").read_text(encoding="utf-8"))
    entries = {entry["path"]: entry for entry in manifest["files"]}
    assert entries["model_runs.csv"]["row_count"] == 9
    assert entries["models/nmf_kl_rank05_anchor/basis.npy"]["shape"] == [5, 3125]


def test_normalize_basis_preserves_reconstruction() -> None:
    rng = np.random.default_rng(4)
    basis = rng.random((3, 11))
    activations = rng.random((7, 3))
    before = activations @ basis
    normalized_basis, normalized_activations = normalize_basis_and_activations(basis, activations)
    assert np.allclose(before, normalized_activations @ normalized_basis, rtol=1e-10, atol=1e-12)
    assert np.allclose(normalized_basis.sum(axis=1), 1.0)


def test_fixed_basis_transform_does_not_mutate_basis() -> None:
    rng = np.random.default_rng(8)
    basis = rng.random((3, 15))
    basis /= basis.sum(axis=1, keepdims=True)
    activations = rng.random((12, 3))
    matrix = activations @ basis
    matrix /= matrix.sum(axis=1, keepdims=True)
    original = basis.copy()
    transformed, _, _ = transform_fixed_kl_basis(matrix, basis, max_iter=100, tolerance=1e-5, seed=9)
    assert transformed.shape == (12, 3)
    assert np.array_equal(basis, original)


def test_component_matching_is_permutation_invariant() -> None:
    rng = np.random.default_rng(10)
    basis = rng.random((5, 30))
    basis /= basis.sum(axis=1, keepdims=True)
    permutation = [3, 0, 4, 1, 2]
    matches = match_components(basis, basis[permutation])
    recovered = {item["component_index_a"]: permutation[item["component_index_b"]] for item in matches}
    assert recovered == {index: index for index in range(5)}
    assert max(item["js_distance"] for item in matches) < 1e-9
