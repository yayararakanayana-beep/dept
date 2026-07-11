from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .contract import (
    DEFAULT_CONTRACT,
    SMOKE_SPLIT_ROWS,
    canonical_contract_text,
    load_contract,
    sha256_file,
    sha256_text,
)
from .metrics import pca_reconstruction, reconstruction_metric_rows
from .models import transform_fixed_basis
from .runner import _load_bundle
from .stage_bc_metrics import _pair_deformation_rows
from .stage_bc_run import _load_evaluation_metadata


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_dump(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _metric_value(
    frame: pd.DataFrame,
    *,
    run_id: str,
    split: str,
    metric: str,
    aggregation: str,
) -> float:
    rows = frame[
        (frame["run_id"].astype(str) == str(run_id))
        & (frame["split"].astype(str) == split)
        & (frame["subgroup_type"].astype(str) == "all")
        & (frame["subgroup_value"].astype(str) == "all")
        & (frame["weighting"].astype(str) == "weighted")
        & (frame["metric"].astype(str) == metric)
        & (frame["aggregation"].astype(str) == aggregation)
    ]
    if len(rows) != 1:
        raise ValueError(
            f"missing unique {split} {aggregation} {metric} for {run_id}: {len(rows)} rows"
        )
    value = float(rows.iloc[0]["value"])
    if not np.isfinite(value):
        raise ValueError("selected metric is not finite")
    return value


def classify_holdout(
    contract: dict[str, Any],
    *,
    baseline_improvement_rate: float,
    mean_ratio: float,
    p95_ratio: float,
) -> tuple[str, list[str]]:
    confirmed = contract["holdout"]["confirmed"]
    conditional = contract["holdout"]["conditional"]
    if (
        baseline_improvement_rate >= float(confirmed["mean_baseline_improvement_min"])
        and mean_ratio <= float(confirmed["holdout_to_validation_mean_js_ratio_max"])
        and p95_ratio <= float(confirmed["holdout_to_validation_p95_js_ratio_max"])
    ):
        return "confirmed", []
    failed_conditions: list[str] = []
    if not (
        baseline_improvement_rate
        > float(conditional["mean_baseline_improvement_min_exclusive"])
    ):
        failed_conditions.append("mean_baseline_not_improved")
    if mean_ratio > float(conditional["holdout_to_validation_mean_js_ratio_max"]):
        failed_conditions.append("holdout_to_validation_mean_ratio")
    if p95_ratio > float(conditional["holdout_to_validation_p95_js_ratio_max"]):
        failed_conditions.append("holdout_to_validation_p95_ratio")
    if not failed_conditions:
        return "conditional", []
    return "failed", failed_conditions


def _validate_selection(
    selection_root: Path,
    contract_path: str | Path,
) -> tuple[dict[str, Any], pd.Series, pd.DataFrame]:
    required = [
        "selection_lock.json",
        "selection_audit.json",
        "selection_candidate.json",
        "model_runs.csv",
        "reconstruction_metrics.csv",
        "contract_snapshot.json",
    ]
    missing = [name for name in required if not (selection_root / name).is_file()]
    if missing:
        raise ValueError(f"selection artifact is incomplete: {missing}")
    contract = load_contract(contract_path)
    contract_hash = sha256_text(canonical_contract_text(contract_path))
    lock = json.loads((selection_root / "selection_lock.json").read_text(encoding="utf-8"))
    audit = json.loads((selection_root / "selection_audit.json").read_text(encoding="utf-8"))
    candidate = json.loads(
        (selection_root / "selection_candidate.json").read_text(encoding="utf-8")
    )
    snapshot = json.loads(
        (selection_root / "contract_snapshot.json").read_text(encoding="utf-8")
    )
    if snapshot != contract or lock.get("contract_sha256") != contract_hash:
        raise ValueError("selection lock contract does not match the frozen contract")
    if (
        lock.get("selection_lock_creator") != "independent_validator"
        or lock.get("independent_selection_audit") != "passed"
        or lock.get("holdout_accessed") is not False
        or audit.get("independent_selection_audit") != "passed"
        or audit.get("holdout_accessed") is not False
    ):
        raise ValueError("selection lock provenance or holdout isolation is invalid")
    if lock.get("candidate_sha256") != sha256_file(
        selection_root / "selection_candidate.json"
    ):
        raise ValueError("selection candidate hash differs from the lock")
    if lock.get("audit_sha256") != sha256_file(selection_root / "selection_audit.json"):
        raise ValueError("selection audit hash differs from the lock")
    if candidate.get("selected_rank") != lock.get("selected_rank"):
        raise ValueError("selection candidate and lock ranks differ")
    selected_rank = int(lock["selected_rank"])
    if selected_rank not in [int(value) for value in contract["rank_grid"]]:
        raise ValueError("selection lock rank is outside the frozen rank grid")
    runs = pd.read_csv(selection_root / "model_runs.csv")
    selected_run_id = str(lock["selected_representative_run"])
    selected_rows = runs[
        (runs["run_id"].astype(str) == selected_run_id)
        & (runs["method"].astype(str) == "nmf_kl")
        & (runs["status"].astype(str) == "completed")
    ]
    if len(selected_rows) != 1:
        raise ValueError("selection lock does not identify one completed primary run")
    selected_run = selected_rows.iloc[0]
    if int(selected_run["rank"]) != selected_rank:
        raise ValueError("selected run rank differs from selection lock")
    for item in lock.get("selected_model_paths_and_hashes", []):
        path = selection_root / str(item["path"])
        if not path.is_file() or sha256_file(path) != str(item["sha256"]):
            raise ValueError(f"selected model evidence is invalid: {item.get('path')}")
    return lock, selected_run, runs


def _copy_selection_evidence(
    selection_root: Path,
    output_root: Path,
    lock: dict[str, Any],
    selected_rank: int,
) -> None:
    target = output_root / "selection_artifact"
    target.mkdir(parents=True, exist_ok=False)
    for relative in (
        "selection_lock.json",
        "selection_audit.json",
        "selection_candidate.json",
        "model_runs.csv",
        "reconstruction_metrics.csv",
        "rank_summary.csv",
        "contract_snapshot.json",
    ):
        source = selection_root / relative
        if source.is_file():
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
    for item in lock.get("selected_model_paths_and_hashes", []):
        relative = Path(str(item["path"]))
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(selection_root / relative, destination)
    reference_paths = [
        Path("references/mean_distribution.npy"),
        Path(f"references/pca_rank_{selected_rank:02d}/weighted_mean.npy"),
        Path(f"references/pca_rank_{selected_rank:02d}/components.npy"),
        Path(f"references/pca_rank_{selected_rank:02d}/explained_variance_ratio.npy"),
    ]
    for relative in reference_paths:
        source = selection_root / relative
        if not source.is_file():
            raise ValueError(f"required selected-rank reference is missing: {relative}")
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def evaluate_holdout(
    *,
    selection_artifact_dir: str | Path,
    holdout_bundle: str | Path,
    holdout_row_map: str | Path,
    holdout_evaluation_metadata: str | Path,
    output_root: str | Path,
    contract_path: str | Path = DEFAULT_CONTRACT,
) -> Path:
    selection_root = Path(selection_artifact_dir)
    contract = load_contract(contract_path)

    # Verify the selection lock before opening holdout evidence.
    lock, selected_run, runs = _validate_selection(selection_root, contract_path)
    profile = str(lock.get("profile"))
    if profile not in {"smoke", "formal"}:
        raise ValueError("selection lock profile is invalid")
    selected_rank = int(lock["selected_rank"])
    selected_run_id = str(lock["selected_representative_run"])

    holdout, weights, row_map = _load_bundle(holdout_bundle, holdout_row_map)
    row_map = row_map.sort_values("bundle_row_index").reset_index(drop=True)
    metadata = _load_evaluation_metadata(
        holdout_evaluation_metadata, row_map, "holdout"
    )
    if set(row_map["dataset_split"].astype(str)) != {"holdout"}:
        raise ValueError("holdout bundle contains a non-holdout row")
    expected_rows = (
        int(contract["input"]["split_rows"]["holdout"])
        if profile == "formal"
        else int(SMOKE_SPLIT_ROWS["holdout"])
    )
    if len(holdout) != expected_rows:
        raise ValueError(
            f"holdout row count {len(holdout)} differs from {expected_rows}"
        )
    if holdout.shape[1] != int(contract["input"]["cell_count"]) and profile == "formal":
        raise ValueError("formal holdout cell count differs from the frozen contract")

    output_dir = Path(output_root) / f"task3_1f4_holdout_{profile}"
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)
    _copy_selection_evidence(selection_root, output_dir, lock, selected_rank)

    evidence = output_dir / "evidence"
    evidence.mkdir()
    evidence_sources = {
        "holdout_bundle.npz": Path(holdout_bundle),
        "holdout_row_map.csv": Path(holdout_row_map),
        "holdout_evaluation_metadata.csv": Path(holdout_evaluation_metadata),
    }
    for name, source in evidence_sources.items():
        shutil.copy2(source, evidence / name)
    contract_snapshot = output_dir / "contract_snapshot.json"
    contract_snapshot.write_text(
        json.dumps(contract, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    selected_artifact_root = output_dir / "selection_artifact"
    basis_item = next(
        (
            item
            for item in lock["selected_model_paths_and_hashes"]
            if str(item["path"]).endswith("/basis.npy")
        ),
        None,
    )
    if basis_item is None:
        raise ValueError("selection lock does not contain a selected basis")
    basis = np.load(
        selected_artifact_root / str(basis_item["path"]), allow_pickle=False
    )
    if basis.shape != (selected_rank, holdout.shape[1]):
        raise ValueError("selected basis shape is incompatible with holdout")

    max_iter = int(selected_run["max_iter"])
    tolerance = float(selected_run["tolerance"])
    activations, n_iter, converged = transform_fixed_basis(
        holdout,
        basis,
        solver=str(selected_run["solver"]),
        beta_loss=str(selected_run["loss"]),
        max_iter=max_iter,
        tolerance=tolerance,
        seed=int(selected_run["init_seed"]),
    )
    selected_model = output_dir / "selected_model"
    selected_model.mkdir()
    activation_path = selected_model / "holdout_activations.npy"
    np.save(activation_path, activations)

    nmf_raw = activations @ basis
    nmf_rows = reconstruction_metric_rows(
        run_id=selected_run_id,
        method="nmf_kl",
        rank=selected_rank,
        split="holdout",
        actual=holdout,
        raw_reconstruction=nmf_raw,
        weights=weights,
        row_map=row_map,
        evidence_basis_path=f"selection_artifact/{basis_item['path']}",
        evidence_activation_path="selected_model/holdout_activations.npy",
    )

    mean_run = runs[runs["method"].astype(str) == "mean_baseline"]
    if len(mean_run) != 1:
        raise ValueError("selection artifact must contain one mean baseline")
    mean_run = mean_run.iloc[0]
    mean_relative = Path(str(mean_run["basis_path"]))
    mean = np.load(selected_artifact_root / mean_relative, allow_pickle=False)
    mean_raw = np.repeat(mean[None, :], len(holdout), axis=0)
    baseline_rows = reconstruction_metric_rows(
        run_id=str(mean_run["run_id"]),
        method="mean_baseline",
        rank=0,
        split="holdout",
        actual=holdout,
        raw_reconstruction=mean_raw,
        weights=weights,
        row_map=row_map,
        evidence_basis_path=f"selection_artifact/{mean_relative}",
        evidence_activation_path="",
    )
    holdout_metrics = pd.DataFrame(nmf_rows + baseline_rows)
    holdout_metrics.to_csv(output_dir / "holdout_metrics.csv", index=False)

    pca_run = runs[
        (runs["method"].astype(str) == "weighted_pca")
        & (runs["rank"].astype(int) == selected_rank)
    ]
    if len(pca_run) != 1:
        raise ValueError("selection artifact must contain one selected-rank PCA run")
    pca_run = pca_run.iloc[0]
    pca_dir = selected_artifact_root / f"references/pca_rank_{selected_rank:02d}"
    pca_mean = np.load(pca_dir / "weighted_mean.npy", allow_pickle=False)
    pca_components = np.load(pca_dir / "components.npy", allow_pickle=False)
    pca_scores = (holdout - pca_mean[None, :]) @ pca_components.T
    pca_scores_path = selected_model / "pca_holdout_scores.npy"
    np.save(pca_scores_path, pca_scores)
    pca_raw, pca_distribution = pca_reconstruction(
        pca_mean, pca_components, pca_scores
    )
    pca_rows = reconstruction_metric_rows(
        run_id=str(pca_run["run_id"]),
        method="weighted_pca",
        rank=selected_rank,
        split="holdout",
        actual=holdout,
        raw_reconstruction=pca_raw,
        distribution_reconstruction=pca_distribution,
        weights=weights,
        row_map=row_map,
        evidence_basis_path=(
            f"selection_artifact/references/pca_rank_{selected_rank:02d}/components.npy"
        ),
        evidence_activation_path="selected_model/pca_holdout_scores.npy",
    )
    pd.DataFrame(pca_rows).to_csv(
        output_dir / "pca_holdout_metrics.csv", index=False
    )

    row_sums = nmf_raw.sum(axis=1, keepdims=True)
    if np.any(row_sums <= 0.0):
        raise ValueError("selected-model holdout reconstruction has non-positive mass")
    pair_rows = _pair_deformation_rows(
        run_id=selected_run_id,
        method="nmf_kl",
        rank=selected_rank,
        split="holdout",
        actual=holdout,
        reconstructed_distribution=nmf_raw / row_sums,
        metadata=metadata,
    )
    pd.DataFrame(pair_rows).to_csv(
        output_dir / "holdout_pair_deformation_metrics.csv", index=False
    )

    validation_metrics = pd.read_csv(
        selected_artifact_root / "reconstruction_metrics.csv"
    )
    holdout_mean = _metric_value(
        holdout_metrics,
        run_id=selected_run_id,
        split="holdout",
        metric="js_distance",
        aggregation="mean",
    )
    holdout_p95 = _metric_value(
        holdout_metrics,
        run_id=selected_run_id,
        split="holdout",
        metric="js_distance",
        aggregation="p95",
    )
    baseline_mean = _metric_value(
        holdout_metrics,
        run_id=str(mean_run["run_id"]),
        split="holdout",
        metric="js_distance",
        aggregation="mean",
    )
    validation_mean = _metric_value(
        validation_metrics,
        run_id=selected_run_id,
        split="validation",
        metric="js_distance",
        aggregation="mean",
    )
    validation_p95 = _metric_value(
        validation_metrics,
        run_id=selected_run_id,
        split="validation",
        metric="js_distance",
        aggregation="p95",
    )
    improvement = (
        (baseline_mean - holdout_mean) / baseline_mean
        if baseline_mean > 0.0
        else float("-inf")
    )
    mean_ratio = holdout_mean / validation_mean if validation_mean > 0.0 else float("inf")
    p95_ratio = holdout_p95 / validation_p95 if validation_p95 > 0.0 else float("inf")
    if not np.isfinite(
        [improvement, mean_ratio, p95_ratio, validation_mean, validation_p95]
    ).all():
        raise ValueError("holdout outcome inputs are not finite")
    outcome, failed_conditions = classify_holdout(
        contract,
        baseline_improvement_rate=improvement,
        mean_ratio=mean_ratio,
        p95_ratio=p95_ratio,
    )
    candidate = {
        "selected_rank": selected_rank,
        "selected_representative_run": selected_run_id,
        "selection_lock_sha256": sha256_file(
            selected_artifact_root / "selection_lock.json"
        ),
        "holdout_activation_sha256": sha256_file(activation_path),
        "nmf_holdout_weighted_mean_js": holdout_mean,
        "mean_baseline_holdout_weighted_mean_js": baseline_mean,
        "baseline_improvement_rate": improvement,
        "validation_weighted_mean_js": validation_mean,
        "holdout_to_validation_mean_ratio": mean_ratio,
        "validation_p95_js": validation_p95,
        "holdout_p95_js": holdout_p95,
        "holdout_to_validation_p95_ratio": p95_ratio,
        "holdout_transform_n_iter": n_iter,
        "holdout_transform_converged": converged,
        "integrity_audit_result": "pending_independent_final_validator",
        "outcome": outcome,
        "failed_conditions": failed_conditions,
    }
    _json_dump(output_dir / "holdout_outcome_candidate.json", candidate)
    manifest = {
        "stage": "task3.1f-4-holdout-evaluation",
        "profile": profile,
        "created_at": _utc_now(),
        "contract_sha256": sha256_text(canonical_contract_text(contract_path)),
        "selection_lock_sha256": candidate["selection_lock_sha256"],
        "selected_rank": selected_rank,
        "selected_representative_run": selected_run_id,
        "holdout_bundle_sha256": sha256_file(evidence / "holdout_bundle.npz"),
        "holdout_row_map_sha256": sha256_file(evidence / "holdout_row_map.csv"),
        "holdout_evaluation_metadata_sha256": sha256_file(
            evidence / "holdout_evaluation_metadata.csv"
        ),
        "basis_retrained": False,
        "rank_changed_after_lock": False,
        "holdout_accessed_after_selection_lock": True,
        "producer_created_final_outcome": False,
    }
    _json_dump(output_dir / "holdout_execution_manifest.json", manifest)
    return output_dir
