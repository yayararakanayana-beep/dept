from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.decomposition import non_negative_factorization

from .audit_metrics import (
    Recorder,
    _compare_metric_frames,
    _compare_pair_frames,
    _load_bundle,
    _metric_rows,
    _pair_rows_for_run,
    _simplex_projection,
)
from .contract import (
    DEFAULT_CONTRACT,
    canonical_contract_text,
    load_contract,
    sha256_file,
    sha256_text,
)


def _json_dump(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _artifact_manifest(root: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "artifact_manifest.json":
            continue
        entry: dict[str, Any] = {
            "path": str(path.relative_to(root)),
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
        }
        if path.suffix == ".csv":
            frame = pd.read_csv(path)
            entry.update(
                {"type": "csv", "row_count": len(frame), "columns": list(frame.columns)}
            )
        elif path.suffix == ".npy":
            array = np.load(path, allow_pickle=False)
            entry.update(
                {"type": "npy", "shape": list(array.shape), "dtype": str(array.dtype)}
            )
        elif path.suffix == ".npz":
            with np.load(path, allow_pickle=False) as archive:
                entry.update(
                    {
                        "type": "npz",
                        "members": {
                            name: {
                                "shape": list(archive[name].shape),
                                "dtype": str(archive[name].dtype),
                            }
                            for name in archive.files
                        },
                    }
                )
        elif path.suffix == ".json":
            entry.update(
                {
                    "type": "json",
                    "top_level_type": type(
                        json.loads(path.read_text(encoding="utf-8"))
                    ).__name__,
                }
            )
        else:
            entry["type"] = "other"
        files.append(entry)
    return {"artifact_root": root.name, "files": files}


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
        raise ValueError("required aggregate metric is not unique")
    value = float(rows.iloc[0]["value"])
    if not np.isfinite(value):
        raise ValueError("required aggregate metric is not finite")
    return value


def _classify(
    contract: dict[str, Any],
    *,
    improvement: float,
    mean_ratio: float,
    p95_ratio: float,
) -> tuple[str, list[str]]:
    confirmed = contract["holdout"]["confirmed"]
    conditional = contract["holdout"]["conditional"]
    if (
        improvement >= float(confirmed["mean_baseline_improvement_min"])
        and mean_ratio <= float(confirmed["holdout_to_validation_mean_js_ratio_max"])
        and p95_ratio <= float(confirmed["holdout_to_validation_p95_js_ratio_max"])
    ):
        return "confirmed", []
    failures: list[str] = []
    if not (
        improvement
        > float(conditional["mean_baseline_improvement_min_exclusive"])
    ):
        failures.append("mean_baseline_not_improved")
    if mean_ratio > float(conditional["holdout_to_validation_mean_js_ratio_max"]):
        failures.append("holdout_to_validation_mean_ratio")
    if p95_ratio > float(conditional["holdout_to_validation_p95_js_ratio_max"]):
        failures.append("holdout_to_validation_p95_ratio")
    return ("conditional", []) if not failures else ("failed", failures)


def _compare_outcome(
    candidate: dict[str, Any],
    recomputed: dict[str, Any],
) -> tuple[bool, list[str]]:
    failures: list[str] = []
    exact_keys = [
        "selected_rank",
        "selected_representative_run",
        "selection_lock_sha256",
        "holdout_activation_sha256",
        "outcome",
        "failed_conditions",
    ]
    numeric_keys = [
        "nmf_holdout_weighted_mean_js",
        "mean_baseline_holdout_weighted_mean_js",
        "baseline_improvement_rate",
        "validation_weighted_mean_js",
        "holdout_to_validation_mean_ratio",
        "validation_p95_js",
        "holdout_p95_js",
        "holdout_to_validation_p95_ratio",
    ]
    for key in exact_keys:
        if candidate.get(key) != recomputed.get(key):
            failures.append(key)
    for key in numeric_keys:
        left = candidate.get(key)
        right = recomputed.get(key)
        if left is None or right is None or not np.isclose(
            float(left), float(right), rtol=1e-9, atol=1e-12
        ):
            failures.append(key)
    if candidate.get("integrity_audit_result") != "pending_independent_final_validator":
        failures.append("integrity_audit_result")
    return not failures, failures


def validate_final(
    artifact_dir: str | Path,
    contract_path: str | Path = DEFAULT_CONTRACT,
    *,
    strict: bool = False,
    write_outputs: bool = True,
) -> dict[str, dict[str, Any]]:
    root = Path(artifact_dir)
    recorder = Recorder()
    required = [
        "selection_artifact/selection_lock.json",
        "selection_artifact/selection_audit.json",
        "selection_artifact/selection_candidate.json",
        "selection_artifact/model_runs.csv",
        "selection_artifact/reconstruction_metrics.csv",
        "selection_artifact/contract_snapshot.json",
        "evidence/holdout_bundle.npz",
        "evidence/holdout_row_map.csv",
        "evidence/holdout_evaluation_metadata.csv",
        "selected_model/holdout_activations.npy",
        "selected_model/pca_holdout_scores.npy",
        "holdout_metrics.csv",
        "pca_holdout_metrics.csv",
        "holdout_pair_deformation_metrics.csv",
        "holdout_outcome_candidate.json",
        "holdout_execution_manifest.json",
        "contract_snapshot.json",
    ]
    missing = [name for name in required if not (root / name).is_file()]
    recorder.add(
        "required_output_files",
        not missing,
        missing=missing,
        checked_count=len(required),
    )
    if missing:
        return _finish(root, recorder, None, strict, write_outputs)

    contract = load_contract(contract_path)
    contract_hash = sha256_text(canonical_contract_text(contract_path))
    selection_root = root / "selection_artifact"
    try:
        snapshot = json.loads((root / "contract_snapshot.json").read_text(encoding="utf-8"))
        selection_snapshot = json.loads(
            (selection_root / "contract_snapshot.json").read_text(encoding="utf-8")
        )
        recorder.add(
            "contract_snapshot_valid",
            snapshot == contract and selection_snapshot == contract,
            expected_sha256=contract_hash,
        )
    except Exception as exc:
        recorder.add(
            "contract_snapshot_valid", False, error=f"{type(exc).__name__}: {exc}"
        )

    try:
        lock_path = selection_root / "selection_lock.json"
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        audit = json.loads(
            (selection_root / "selection_audit.json").read_text(encoding="utf-8")
        )
        selection_candidate = json.loads(
            (selection_root / "selection_candidate.json").read_text(encoding="utf-8")
        )
        lock_valid = (
            lock.get("contract_sha256") == contract_hash
            and lock.get("selection_lock_creator") == "independent_validator"
            and lock.get("independent_selection_audit") == "passed"
            and lock.get("holdout_accessed") is False
            and audit.get("independent_selection_audit") == "passed"
            and audit.get("holdout_accessed") is False
            and lock.get("candidate_sha256")
            == sha256_file(selection_root / "selection_candidate.json")
            and lock.get("audit_sha256")
            == sha256_file(selection_root / "selection_audit.json")
            and lock.get("selected_rank") == selection_candidate.get("selected_rank")
            and lock.get("selected_representative_run")
            == selection_candidate.get("selected_representative_run")
        )
        selected_rank = int(lock["selected_rank"])
        selected_run_id = str(lock["selected_representative_run"])
        recorder.add(
            "selection_lock_valid",
            lock_valid
            and selected_rank in [int(value) for value in contract["rank_grid"]],
            selected_rank=selected_rank,
            selected_run=selected_run_id,
        )
    except Exception as exc:
        recorder.add("selection_lock_valid", False, error=f"{type(exc).__name__}: {exc}")
        return _finish(root, recorder, None, strict, write_outputs)

    try:
        runs = pd.read_csv(selection_root / "model_runs.csv")
        selected_rows = runs[
            (runs["run_id"].astype(str) == selected_run_id)
            & (runs["method"].astype(str) == "nmf_kl")
            & (runs["status"].astype(str) == "completed")
        ]
        if len(selected_rows) != 1:
            raise ValueError("selected primary run is not unique")
        selected_run = selected_rows.iloc[0]
        if int(selected_run["rank"]) != selected_rank:
            raise ValueError("selected run rank differs from lock")
        bad_models: list[str] = []
        for item in lock.get("selected_model_paths_and_hashes", []):
            path = selection_root / str(item["path"])
            if not path.is_file() or sha256_file(path) != str(item["sha256"]):
                bad_models.append(str(item.get("path")))
        recorder.add(
            "selected_model_evidence_valid",
            not bad_models,
            bad_paths=bad_models,
            checked_count=len(lock.get("selected_model_paths_and_hashes", [])),
        )
    except Exception as exc:
        recorder.add(
            "selected_model_evidence_valid",
            False,
            error=f"{type(exc).__name__}: {exc}",
        )
        return _finish(root, recorder, None, strict, write_outputs)

    try:
        manifest = json.loads(
            (root / "holdout_execution_manifest.json").read_text(encoding="utf-8")
        )
        manifest_valid = (
            manifest.get("contract_sha256") == contract_hash
            and manifest.get("selection_lock_sha256")
            == sha256_file(selection_root / "selection_lock.json")
            and manifest.get("selected_rank") == selected_rank
            and manifest.get("selected_representative_run") == selected_run_id
            and manifest.get("holdout_bundle_sha256")
            == sha256_file(root / "evidence/holdout_bundle.npz")
            and manifest.get("holdout_row_map_sha256")
            == sha256_file(root / "evidence/holdout_row_map.csv")
            and manifest.get("holdout_evaluation_metadata_sha256")
            == sha256_file(root / "evidence/holdout_evaluation_metadata.csv")
            and manifest.get("basis_retrained") is False
            and manifest.get("rank_changed_after_lock") is False
            and manifest.get("holdout_accessed_after_selection_lock") is True
            and manifest.get("producer_created_final_outcome") is False
        )
        recorder.add("holdout_execution_manifest_valid", manifest_valid)
    except Exception as exc:
        recorder.add(
            "holdout_execution_manifest_valid",
            False,
            error=f"{type(exc).__name__}: {exc}",
        )

    try:
        holdout, weights, row_map, metadata = _load_bundle(root, "holdout")
        profile = str(manifest.get("profile"))
        expected_rows = (
            int(contract["input"]["split_rows"]["holdout"])
            if profile == "formal"
            else 11
        )
        expected_cells = (
            int(contract["input"]["cell_count"])
            if profile == "formal"
            else holdout.shape[1]
        )
        evidence_valid = (
            profile in {"smoke", "formal"}
            and len(holdout) == expected_rows
            and holdout.shape[1] == expected_cells
            and set(row_map["dataset_split"].astype(str)) == {"holdout"}
            and set(metadata["dataset_split"].astype(str)) == {"holdout"}
            and np.isfinite(holdout).all()
            and np.all(holdout >= 0.0)
            and np.max(np.abs(holdout.sum(axis=1) - 1.0)) <= 1e-8
            and np.isfinite(weights).all()
            and np.all(weights > 0.0)
        )
        recorder.add(
            "holdout_evidence_valid",
            evidence_valid,
            row_count=len(holdout),
            cell_count=holdout.shape[1],
        )
    except Exception as exc:
        recorder.add("holdout_evidence_valid", False, error=f"{type(exc).__name__}: {exc}")
        return _finish(root, recorder, None, strict, write_outputs)

    basis_item = next(
        (
            item
            for item in lock.get("selected_model_paths_and_hashes", [])
            if str(item["path"]).endswith("/basis.npy")
        ),
        None,
    )
    if basis_item is None:
        recorder.add("selected_basis_valid", False, error="selected basis is absent")
        return _finish(root, recorder, None, strict, write_outputs)
    try:
        basis = np.load(selection_root / str(basis_item["path"]), allow_pickle=False)
        basis_valid = (
            basis.shape == (selected_rank, holdout.shape[1])
            and np.isfinite(basis).all()
            and np.all(basis >= 0.0)
            and np.max(np.abs(basis.sum(axis=1) - 1.0)) <= 1e-10
        )
        recorder.add("selected_basis_valid", basis_valid, shape=list(basis.shape))
    except Exception as exc:
        recorder.add("selected_basis_valid", False, error=f"{type(exc).__name__}: {exc}")
        return _finish(root, recorder, None, strict, write_outputs)

    try:
        saved_activations = np.load(
            root / "selected_model/holdout_activations.npy", allow_pickle=False
        )
        recomputed_activations, returned_basis, n_iter = non_negative_factorization(
            holdout,
            H=basis.copy(),
            n_components=selected_rank,
            init="custom",
            update_H=False,
            solver=str(selected_run["solver"]),
            beta_loss=str(selected_run["loss"]),
            tol=float(selected_run["tolerance"]),
            max_iter=int(selected_run["max_iter"]),
            alpha_W=0.0,
            alpha_H=0.0,
            l1_ratio=0.0,
            random_state=int(selected_run["init_seed"]),
            shuffle=False,
        )
        activation_valid = (
            saved_activations.shape == (len(holdout), selected_rank)
            and np.isfinite(saved_activations).all()
            and np.all(saved_activations >= 0.0)
            and np.array_equal(returned_basis, basis)
            and np.allclose(
                saved_activations,
                recomputed_activations,
                rtol=float(contract["numeric"]["reconstruction_rtol"]),
                atol=float(contract["numeric"]["reconstruction_atol"]),
            )
        )
        recorder.add(
            "holdout_activation_recomputed",
            activation_valid,
            shape=list(saved_activations.shape),
            n_iter=int(n_iter),
            maximum_error=float(
                np.max(np.abs(saved_activations - recomputed_activations), initial=0.0)
            )
            if saved_activations.shape == recomputed_activations.shape
            else float("inf"),
        )
    except Exception as exc:
        recorder.add(
            "holdout_activation_recomputed",
            False,
            error=f"{type(exc).__name__}: {exc}",
        )
        return _finish(root, recorder, None, strict, write_outputs)

    try:
        selected_series = pd.Series(
            {"run_id": selected_run_id, "method": "nmf_kl", "rank": selected_rank}
        )
        mean_rows = runs[runs["method"].astype(str) == "mean_baseline"]
        if len(mean_rows) != 1:
            raise ValueError("mean baseline is not unique")
        mean_run = mean_rows.iloc[0]
        mean = np.load(
            selection_root / str(mean_run["basis_path"]), allow_pickle=False
        )
        recomputed_main = pd.DataFrame(
            _metric_rows(
                selected_series,
                "holdout",
                holdout,
                recomputed_activations @ basis,
                weights,
                row_map,
            )
            + _metric_rows(
                mean_run,
                "holdout",
                holdout,
                np.repeat(mean[None, :], len(holdout), axis=0),
                weights,
                row_map,
            )
        )
        stored_main = pd.read_csv(root / "holdout_metrics.csv")
        metrics_ok, metric_error, metric_failures = _compare_metric_frames(
            stored_main, recomputed_main
        )
        recorder.add(
            "holdout_metrics_recomputed",
            metrics_ok,
            maximum_error=metric_error,
            failures=metric_failures,
            checked_count=len(stored_main),
        )
    except Exception as exc:
        recorder.add(
            "holdout_metrics_recomputed",
            False,
            error=f"{type(exc).__name__}: {exc}",
        )
        return _finish(root, recorder, None, strict, write_outputs)

    try:
        pca_rows = runs[
            (runs["method"].astype(str) == "weighted_pca")
            & (runs["rank"].astype(int) == selected_rank)
        ]
        if len(pca_rows) != 1:
            raise ValueError("selected-rank PCA run is not unique")
        pca_run = pca_rows.iloc[0]
        pca_dir = selection_root / f"references/pca_rank_{selected_rank:02d}"
        pca_mean = np.load(pca_dir / "weighted_mean.npy", allow_pickle=False)
        pca_components = np.load(pca_dir / "components.npy", allow_pickle=False)
        recomputed_scores = (holdout - pca_mean[None, :]) @ pca_components.T
        saved_scores = np.load(
            root / "selected_model/pca_holdout_scores.npy", allow_pickle=False
        )
        score_ok = saved_scores.shape == recomputed_scores.shape and np.allclose(
            saved_scores,
            recomputed_scores,
            rtol=float(contract["numeric"]["reconstruction_rtol"]),
            atol=float(contract["numeric"]["reconstruction_atol"]),
        )
        recorder.add(
            "pca_holdout_scores_recomputed",
            score_ok,
            maximum_error=float(
                np.max(np.abs(saved_scores - recomputed_scores), initial=0.0)
            )
            if saved_scores.shape == recomputed_scores.shape
            else float("inf"),
        )
        pca_raw = pca_mean[None, :] + recomputed_scores @ pca_components
        pca_distribution = _simplex_projection(pca_raw)
        recomputed_pca = pd.DataFrame(
            _metric_rows(
                pca_run,
                "holdout",
                holdout,
                pca_raw,
                weights,
                row_map,
                pca_distribution,
            )
        )
        stored_pca = pd.read_csv(root / "pca_holdout_metrics.csv")
        pca_ok, pca_error, pca_failures = _compare_metric_frames(
            stored_pca, recomputed_pca
        )
        recorder.add(
            "pca_holdout_metrics_recomputed",
            pca_ok,
            maximum_error=pca_error,
            failures=pca_failures,
            checked_count=len(stored_pca),
        )
    except Exception as exc:
        recorder.add(
            "pca_holdout_metrics_recomputed",
            False,
            error=f"{type(exc).__name__}: {exc}",
        )

    try:
        recomputed_pair = pd.DataFrame(
            _pair_rows_for_run(
                selected_series,
                "holdout",
                holdout,
                recomputed_activations @ basis,
                metadata,
            )
        )
        stored_pair = pd.read_csv(root / "holdout_pair_deformation_metrics.csv")
        pair_ok, pair_error, pair_failures = _compare_pair_frames(
            stored_pair, recomputed_pair
        )
        recorder.add(
            "holdout_pair_metrics_recomputed",
            pair_ok,
            maximum_error=pair_error,
            failures=pair_failures,
            checked_count=len(stored_pair),
        )
    except Exception as exc:
        recorder.add(
            "holdout_pair_metrics_recomputed",
            False,
            error=f"{type(exc).__name__}: {exc}",
        )

    official_outcome: dict[str, Any] | None = None
    try:
        validation_metrics = pd.read_csv(
            selection_root / "reconstruction_metrics.csv"
        )
        holdout_mean = _metric_value(
            recomputed_main,
            run_id=selected_run_id,
            split="holdout",
            metric="js_distance",
            aggregation="mean",
        )
        holdout_p95 = _metric_value(
            recomputed_main,
            run_id=selected_run_id,
            split="holdout",
            metric="js_distance",
            aggregation="p95",
        )
        baseline_mean = _metric_value(
            recomputed_main,
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
        improvement = (baseline_mean - holdout_mean) / baseline_mean
        mean_ratio = holdout_mean / validation_mean
        p95_ratio = holdout_p95 / validation_p95
        if not np.isfinite(
            [improvement, mean_ratio, p95_ratio, validation_mean, validation_p95]
        ).all():
            raise ValueError("outcome inputs are not finite")
        outcome, failed_conditions = _classify(
            contract,
            improvement=improvement,
            mean_ratio=mean_ratio,
            p95_ratio=p95_ratio,
        )
        recomputed_outcome = {
            "selected_rank": selected_rank,
            "selected_representative_run": selected_run_id,
            "selection_lock_sha256": sha256_file(
                selection_root / "selection_lock.json"
            ),
            "holdout_activation_sha256": sha256_file(
                root / "selected_model/holdout_activations.npy"
            ),
            "nmf_holdout_weighted_mean_js": holdout_mean,
            "mean_baseline_holdout_weighted_mean_js": baseline_mean,
            "baseline_improvement_rate": improvement,
            "validation_weighted_mean_js": validation_mean,
            "holdout_to_validation_mean_ratio": mean_ratio,
            "validation_p95_js": validation_p95,
            "holdout_p95_js": holdout_p95,
            "holdout_to_validation_p95_ratio": p95_ratio,
            "outcome": outcome,
            "failed_conditions": failed_conditions,
        }
        candidate = json.loads(
            (root / "holdout_outcome_candidate.json").read_text(encoding="utf-8")
        )
        outcome_ok, outcome_failures = _compare_outcome(candidate, recomputed_outcome)
        recorder.add(
            "holdout_outcome_recomputed",
            outcome_ok,
            failures=outcome_failures,
            outcome=outcome,
        )
        official_outcome = {
            **recomputed_outcome,
            "holdout_transform_n_iter": int(candidate["holdout_transform_n_iter"]),
            "holdout_transform_converged": bool(
                candidate["holdout_transform_converged"]
            ),
            "integrity_audit_result": "passed",
        }
    except Exception as exc:
        recorder.add(
            "holdout_outcome_recomputed",
            False,
            error=f"{type(exc).__name__}: {exc}",
        )

    return _finish(root, recorder, official_outcome, strict, write_outputs)


def _finish(
    root: Path,
    recorder: Recorder,
    official_outcome: dict[str, Any] | None,
    strict: bool,
    write_outputs: bool,
) -> dict[str, dict[str, Any]]:
    failed = recorder.failed
    if write_outputs:
        _json_dump(root / "quality_checks.json", recorder.checks)
        _json_dump(
            root / "final_audit.json",
            {
                "checks": recorder.checks,
                "failed_checks": failed,
                "independent_final_audit": "passed" if not failed else "failed",
            },
        )
        outcome_path = root / "holdout_outcome.json"
        if not failed and official_outcome is not None:
            _json_dump(outcome_path, official_outcome)
        elif outcome_path.exists():
            outcome_path.unlink()
        lines = [
            "# Task 3.1f-4 Holdout Results",
            "",
            f"- Independent final audit: `{'PASS' if not failed else 'FAIL'}`",
            f"- Checks: `{len(recorder.checks) - len(failed)} / {len(recorder.checks)}`",
        ]
        if official_outcome is not None:
            lines.extend(
                [
                    f"- Selected rank: `{official_outcome['selected_rank']}`",
                    f"- Holdout outcome: `{official_outcome['outcome']}`",
                ]
            )
        if failed:
            lines.extend(["", "## Failed checks", ""] + [f"- `{name}`" for name in failed])
        (root / "results.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        _json_dump(root / "artifact_manifest.json", _artifact_manifest(root))
    if failed and strict:
        raise SystemExit(1)
    return recorder.checks
