from __future__ import annotations

import argparse
import json
import platform
import shutil
import sys
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import scipy
import sklearn

from .contract import DEFAULT_CONTRACT, canonical_contract_text, load_contract, sha256_file, sha256_text
from .metrics import pca_reconstruction, reconstruction_metric_rows
from .models import fit_weighted_kl_nmf, fit_weighted_pca, match_components


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_bundle(bundle_path: str | Path, row_map_path: str | Path) -> tuple[np.ndarray, np.ndarray, pd.DataFrame]:
    with np.load(bundle_path, allow_pickle=False) as bundle:
        required = {"mass_matrix", "analysis_weight", "matrix_row_index", "snapshot_id_hash"}
        if set(bundle.files) != required:
            raise ValueError(f"bundle members differ from frozen schema: {bundle.files}")
        mass = np.asarray(bundle["mass_matrix"], dtype=np.float64)
        weights = np.asarray(bundle["analysis_weight"], dtype=np.float64)
        indices = np.asarray(bundle["matrix_row_index"], dtype=np.int64)
        hashes = np.asarray(bundle["snapshot_id_hash"])
    row_map = pd.read_csv(row_map_path)
    if len(row_map) != mass.shape[0] or weights.shape != (mass.shape[0],):
        raise ValueError("bundle arrays and row map are not aligned")
    if not np.array_equal(indices, row_map["matrix_row_index"].to_numpy(dtype=np.int64)):
        raise ValueError("bundle matrix indices and row map differ")
    import hashlib
    expected_hashes = np.asarray(
        [hashlib.sha256(str(value).encode("utf-8")).hexdigest().encode("ascii") for value in row_map["snapshot_id"]],
        dtype="S64",
    )
    if not np.array_equal(hashes, expected_hashes):
        raise ValueError("bundle snapshot hashes and row map differ")
    return mass, weights, row_map


def _save_nmf_run(
    output_dir: Path, *, run_id: str, rank: int, init_method: str, init_seed: int,
    fit: np.ndarray, fit_weights: np.ndarray, validation: np.ndarray,
    contract: dict[str, Any], max_iter_override: int | None = None,
) -> dict[str, Any]:
    started = _utc_now()
    model = contract["primary_model"]
    effective_max_iter = int(max_iter_override if max_iter_override is not None else model["max_iter"])
    result = fit_weighted_kl_nmf(
        fit, fit_weights, validation, rank=rank, init_method=init_method, init_seed=init_seed,
        max_iter=effective_max_iter, tolerance=float(model["tolerance"]),
    )
    run_dir = output_dir / "models" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    basis_path = run_dir / "basis.npy"
    fit_path = run_dir / "fit_activations.npy"
    validation_path = run_dir / "validation_activations.npy"
    np.save(basis_path, result.basis)
    np.save(fit_path, result.fit_activations)
    np.save(validation_path, result.validation_activations)
    metadata = {
        "run_id": run_id, "method": "nmf_kl", "rank": rank, "init_method": init_method,
        "init_seed": init_seed, "solver": "mu", "loss": "kullback-leibler",
        "max_iter": effective_max_iter, "tolerance": float(model["tolerance"]),
        "n_iter": result.n_iter, "converged": result.converged,
        "basis_sha256": sha256_file(basis_path), "fit_activation_sha256": sha256_file(fit_path),
        "validation_activation_sha256": sha256_file(validation_path),
    }
    (run_dir / "run_metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "run_id": run_id, "method": "nmf_kl", "rank": rank,
        "run_role": "anchor" if init_method == "nndsvda" else "random_init",
        "init_method": init_method, "init_seed": init_seed, "subset_id": "", "world_seed_filter": "",
        "solver": "mu", "loss": "kullback-leibler", "max_iter": effective_max_iter,
        "tolerance": float(model["tolerance"]), "n_iter": result.n_iter,
        "converged": result.converged, "status": "completed", "failure_reason": "",
        "fit_started_at": started, "fit_completed_at": _utc_now(),
        "basis_path": str(basis_path.relative_to(output_dir)),
        "fit_activation_path": str(fit_path.relative_to(output_dir)),
        "validation_activation_path": str(validation_path.relative_to(output_dir)),
        "basis_sha256": sha256_file(basis_path), "fit_activation_sha256": sha256_file(fit_path),
        "validation_activation_sha256": sha256_file(validation_path),
    }


def run_smoke(
    fit_bundle: str | Path, fit_row_map: str | Path,
    validation_bundle: str | Path, validation_row_map: str | Path,
    output_root: str | Path, contract_path: str | Path = DEFAULT_CONTRACT,
) -> Path:
    contract = load_contract(contract_path)
    fit, fit_weights, fit_map = _load_bundle(fit_bundle, fit_row_map)
    validation, validation_weights, validation_map = _load_bundle(validation_bundle, validation_row_map)
    if set(fit_map["dataset_split"]) != {"fit"} or set(validation_map["dataset_split"]) != {"validation"}:
        raise ValueError("smoke runner accepts only fit and validation bundles")
    rank = int(contract["rank_grid"][0])
    if rank > min(fit.shape):
        raise ValueError("smoke fit bundle is too small for the frozen first rank")
    output_dir = Path(output_root) / "smoke_minimal_extraction"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    (output_dir / "models").mkdir(parents=True, exist_ok=False)
    (output_dir / "references" / "pca_rank_5").mkdir(parents=True, exist_ok=False)

    run_rows: list[dict[str, Any]] = [
        _save_nmf_run(
            output_dir, run_id="nmf_kl_rank05_anchor", rank=rank,
            init_method=contract["primary_model"]["anchor_initialization"], init_seed=0,
            fit=fit, fit_weights=fit_weights, validation=validation, contract=contract,
            max_iter_override=50,
        )
    ]
    for seed in contract["primary_model"]["random_seeds"]:
        run_rows.append(_save_nmf_run(
            output_dir, run_id=f"nmf_kl_rank05_seed{seed}", rank=rank,
            init_method=contract["primary_model"]["random_initialization"], init_seed=int(seed),
            fit=fit, fit_weights=fit_weights, validation=validation, contract=contract,
            max_iter_override=50,
        ))

    metrics: list[dict[str, Any]] = []
    for run in run_rows:
        basis = np.load(output_dir / run["basis_path"], allow_pickle=False)
        fit_activation = np.load(output_dir / run["fit_activation_path"], allow_pickle=False)
        validation_activation = np.load(output_dir / run["validation_activation_path"], allow_pickle=False)
        metrics.extend(reconstruction_metric_rows(
            run_id=run["run_id"], method="nmf_kl", rank=rank, split="fit",
            actual=fit, raw_reconstruction=fit_activation @ basis, weights=fit_weights,
            row_map=fit_map, evidence_basis_path=run["basis_path"],
            evidence_activation_path=run["fit_activation_path"],
        ))
        metrics.extend(reconstruction_metric_rows(
            run_id=run["run_id"], method="nmf_kl", rank=rank, split="validation",
            actual=validation, raw_reconstruction=validation_activation @ basis, weights=validation_weights,
            row_map=validation_map, evidence_basis_path=run["basis_path"],
            evidence_activation_path=run["validation_activation_path"],
        ))

    mean_distribution = np.average(fit, axis=0, weights=fit_weights)
    mean_distribution /= mean_distribution.sum(dtype=np.float64)
    mean_path = output_dir / "references" / "mean_distribution.npy"
    np.save(mean_path, mean_distribution)
    baseline_run = {
        "run_id": "mean_distribution_baseline", "method": "mean_baseline", "rank": 0,
        "run_role": "reference", "init_method": "none", "init_seed": 0,
        "subset_id": "", "world_seed_filter": "", "solver": "weighted_mean", "loss": "none",
        "max_iter": 0, "tolerance": 0.0, "n_iter": 0, "converged": True,
        "status": "completed", "failure_reason": "", "fit_started_at": _utc_now(),
        "fit_completed_at": _utc_now(), "basis_path": str(mean_path.relative_to(output_dir)),
        "fit_activation_path": "", "validation_activation_path": "",
        "basis_sha256": sha256_file(mean_path), "fit_activation_sha256": "",
        "validation_activation_sha256": "",
    }
    run_rows.append(baseline_run)
    for split, actual, weights, row_map in (
        ("fit", fit, fit_weights, fit_map),
        ("validation", validation, validation_weights, validation_map),
    ):
        reconstruction = np.repeat(mean_distribution[None, :], len(actual), axis=0)
        metrics.extend(reconstruction_metric_rows(
            run_id=baseline_run["run_id"], method="mean_baseline", rank=0, split=split,
            actual=actual, raw_reconstruction=reconstruction, weights=weights, row_map=row_map,
            evidence_basis_path=baseline_run["basis_path"], evidence_activation_path="",
        ))

    pca = fit_weighted_pca(fit, fit_weights, validation, rank)
    pca_dir = output_dir / "references" / "pca_rank_5"
    mean_pca_path = pca_dir / "weighted_mean.npy"
    components_path = pca_dir / "components.npy"
    fit_scores_path = pca_dir / "fit_scores.npy"
    validation_scores_path = pca_dir / "validation_scores.npy"
    explained_path = pca_dir / "explained_variance_ratio.npy"
    np.save(mean_pca_path, pca.weighted_mean)
    np.save(components_path, pca.components)
    np.save(fit_scores_path, pca.fit_scores)
    np.save(validation_scores_path, pca.validation_scores)
    np.save(explained_path, pca.explained_variance_ratio)
    pca_run = {
        "run_id": "weighted_pca_rank05", "method": "weighted_pca", "rank": rank,
        "run_role": "reference", "init_method": "svd", "init_seed": 0,
        "subset_id": "", "world_seed_filter": "", "solver": "weighted_centered_svd", "loss": "frobenius",
        "max_iter": 0, "tolerance": 0.0, "n_iter": 1, "converged": True,
        "status": "completed", "failure_reason": "", "fit_started_at": _utc_now(),
        "fit_completed_at": _utc_now(), "basis_path": str(components_path.relative_to(output_dir)),
        "fit_activation_path": str(fit_scores_path.relative_to(output_dir)),
        "validation_activation_path": str(validation_scores_path.relative_to(output_dir)),
        "basis_sha256": sha256_file(components_path), "fit_activation_sha256": sha256_file(fit_scores_path),
        "validation_activation_sha256": sha256_file(validation_scores_path),
    }
    run_rows.append(pca_run)
    for split, actual, weights, row_map, scores, score_path in (
        ("fit", fit, fit_weights, fit_map, pca.fit_scores, fit_scores_path),
        ("validation", validation, validation_weights, validation_map, pca.validation_scores, validation_scores_path),
    ):
        raw, projected = pca_reconstruction(pca.weighted_mean, pca.components, scores)
        metrics.extend(reconstruction_metric_rows(
            run_id=pca_run["run_id"], method="weighted_pca", rank=rank, split=split,
            actual=actual, raw_reconstruction=raw, distribution_reconstruction=projected,
            weights=weights, row_map=row_map, evidence_basis_path=pca_run["basis_path"],
            evidence_activation_path=str(score_path.relative_to(output_dir)),
        ))

    matches: list[dict[str, Any]] = []
    nmf_rows = [row for row in run_rows if row["method"] == "nmf_kl"]
    for left, right in combinations(nmf_rows, 2):
        basis_left = np.load(output_dir / left["basis_path"], allow_pickle=False)
        basis_right = np.load(output_dir / right["basis_path"], allow_pickle=False)
        for item in match_components(basis_left, basis_right):
            matches.append({"rank": rank, "run_id_a": left["run_id"], "run_id_b": right["run_id"], **item})

    pd.DataFrame(run_rows).to_csv(output_dir / "model_runs.csv", index=False)
    pd.DataFrame(metrics).to_csv(output_dir / "reconstruction_metrics.csv", index=False)
    pd.DataFrame(matches).to_csv(output_dir / "component_matches.csv", index=False)
    (output_dir / "contract_snapshot.json").write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "environment_manifest.json").write_text(json.dumps({
        "python": sys.version, "platform": platform.platform(), "architecture": platform.machine(),
        "numpy": np.__version__, "scipy": scipy.__version__, "pandas": pd.__version__,
        "scikit_learn": sklearn.__version__,
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    summary = {
        "stage": "task3.1f-2-smoke-minimal-extraction", "profile": "smoke", "rank": rank,
        "nmf_run_count": len(nmf_rows), "random_seeds": contract["primary_model"]["random_seeds"],
        "fit_rows": len(fit), "validation_rows": len(validation), "holdout_accessed": False,
        "selection_lock_created": False, "full_rank_grid_executed": False,
        "formal_scientific_selection": False, "smoke_max_iter": 50,
        "formal_contract_max_iter": int(contract["primary_model"]["max_iter"]),
        "contract_sha256": sha256_text(canonical_contract_text(contract_path)),
    }
    (output_dir / "smoke_stage_manifest.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return output_dir


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fit-bundle", required=True)
    parser.add_argument("--fit-row-map", required=True)
    parser.add_argument("--validation-bundle", required=True)
    parser.add_argument("--validation-row-map", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    args = parser.parse_args()
    print(run_smoke(
        args.fit_bundle, args.fit_row_map, args.validation_bundle,
        args.validation_row_map, args.output_root, args.contract,
    ))
