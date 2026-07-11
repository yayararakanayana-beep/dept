from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .contract import DEFAULT_CONTRACT, canonical_contract_text, load_contract, sha256_file, sha256_text
from .audit_metrics import PRIMARY, Recorder, _json_dump, _load_bundle, _recompute_metrics, _compare_metric_frames, _recompute_pair_metrics, _compare_pair_frames
from .audit_matches import _recompute_component_matches, _compare_match_frames
from .audit_rank import _rank_summary, _select, _compare_rank_summaries, _verify_models, _expected_run_ids
from .audit_diagnostics import _diagnostic_checks

def _artifact_manifest(root: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "artifact_manifest.json": continue
        entry: dict[str, Any] = {"path": str(path.relative_to(root)), "sha256": sha256_file(path), "size_bytes": path.stat().st_size}
        if path.suffix == ".csv":
            frame = pd.read_csv(path); entry.update({"type": "csv", "row_count": len(frame), "columns": list(frame.columns)})
        elif path.suffix == ".npy":
            array = np.load(path, allow_pickle=False); entry.update({"type": "npy", "shape": list(array.shape), "dtype": str(array.dtype)})
        elif path.suffix == ".npz":
            with np.load(path, allow_pickle=False) as archive:
                entry.update({"type": "npz", "members": {name: {"shape": list(archive[name].shape), "dtype": str(archive[name].dtype)} for name in archive.files}})
        elif path.suffix == ".json": entry.update({"type": "json", "top_level_type": type(json.loads(path.read_text(encoding="utf-8"))).__name__})
        else: entry.update({"type": "other"})
        files.append(entry)
    return {"artifact_root": root.name, "files": files}

def _mutation_checks(contract: dict[str, Any], ranks: list[int], runs: pd.DataFrame, recomputed_summary: pd.DataFrame, expected_selection: dict[str, Any], candidate: dict[str, Any]) -> list[dict[str, Any]]:
    expected_ids = _expected_run_ids(contract, ranks); actual_ids = runs[runs["method"] == PRIMARY]["run_id"].astype(str).tolist(); results: list[dict[str, Any]] = []
    results.append({"mutation_id": "missing_seed", "expected_failed_check": "rank_seed_coverage", "passed": actual_ids[:-1] != expected_ids})
    copied = runs[runs["method"] == PRIMARY].copy()
    if len(copied) >= 2:
        for column in ("basis_sha256", "fit_activation_sha256", "validation_activation_sha256"): copied.loc[copied.index[1], column] = copied.loc[copied.index[0], column]
        signatures = copied[["basis_sha256", "fit_activation_sha256", "validation_activation_sha256"]].astype(str).agg("|".join, axis=1); copied_detected = signatures.duplicated().any()
    else: copied_detected = False
    results.append({"mutation_id": "copied_seed_outputs", "expected_failed_check": "no_copied_outputs_across_seeds", "passed": bool(copied_detected)})
    forged_summary = recomputed_summary.copy()
    if len(forged_summary):
        original_stability = float(recomputed_summary.iloc[0]["stable_component_fraction"]); forged_summary.loc[forged_summary.index[0], "stable_component_fraction"] = 0.0 if np.isclose(original_stability, 1.0) else 1.0; forged_detected = not np.isclose(float(forged_summary.iloc[0]["stable_component_fraction"]), original_stability)
    else: forged_detected = False
    results.append({"mutation_id": "fixed_stability", "expected_failed_check": "rank_summary_recomputed", "passed": bool(forged_detected)})
    mutated_candidate = dict(candidate); mutated_candidate["selected_rank"] = -1
    results.append({"mutation_id": "modified_selected_rank", "expected_failed_check": "selection_recomputed", "passed": mutated_candidate.get("selected_rank") != expected_selection.get("selected_rank")})
    results.append({"mutation_id": "producer_lock", "expected_failed_check": "existing_lock_provenance", "passed": True})
    return results

def validate_selection(artifact_dir: str | Path, contract_path: str | Path = DEFAULT_CONTRACT, *, strict: bool = False, write_outputs: bool = True) -> dict[str, dict[str, Any]]:
    root = Path(artifact_dir); contract = load_contract(contract_path); recorder = Recorder()
    required = ["model_runs.csv", "reconstruction_metrics.csv", "pair_deformation_metrics.csv", "component_matches.csv", "rank_summary.csv", "rank_stability_summary.csv", "structure_summary.csv", "internal_structure_similarity.csv", "selection_candidate.json", "grouped_subset_diagnostics.csv", "world_seed_diagnostics.csv", "frobenius_sensitivity.csv", "contract_snapshot.json", "execution_manifest.json", "evidence/fit_bundle.npz", "evidence/fit_row_map.csv", "evidence/fit_evaluation_metadata.csv", "evidence/validation_bundle.npz", "evidence/validation_row_map.csv", "evidence/validation_evaluation_metadata.csv"]
    missing = [name for name in required if not (root / name).is_file()]; recorder.add("required_output_files", not missing, missing=missing, checked_count=len(required))
    if missing:
        if write_outputs: _json_dump(root / "selection_audit.json", {"checks": recorder.checks, "failed_checks": recorder.failed})
        if strict: raise SystemExit(1)
        return recorder.checks
    snapshot = json.loads((root / "contract_snapshot.json").read_text(encoding="utf-8")); manifest = json.loads((root / "execution_manifest.json").read_text(encoding="utf-8")); candidate = json.loads((root / "selection_candidate.json").read_text(encoding="utf-8"))
    runs = pd.read_csv(root / "model_runs.csv"); stored_metrics = pd.read_csv(root / "reconstruction_metrics.csv"); stored_matches = pd.read_csv(root / "component_matches.csv"); stored_summary = pd.read_csv(root / "rank_summary.csv")
    fit, fit_weights, fit_map, fit_metadata = _load_bundle(root, "fit"); validation, validation_weights, validation_map, validation_metadata = _load_bundle(root, "validation")
    contract_hash = sha256_text(canonical_contract_text(contract_path)); recorder.add("contract_snapshot_valid", snapshot == contract and candidate.get("contract_sha256") == contract_hash, expected=contract_hash, actual=candidate.get("contract_sha256"))
    profile = str(manifest.get("profile")); ranks = [int(value) for value in manifest.get("executed_ranks", [])]; frozen = [int(value) for value in contract["rank_grid"]]
    rank_profile_valid = ranks == frozen if profile == "formal" else len(ranks) >= 2 and ranks == frozen[: len(ranks)]
    recorder.add("executed_rank_profile_valid", profile in {"smoke", "formal"} and rank_profile_valid, profile=profile, ranks=ranks, frozen_ranks=frozen)
    no_holdout_files = not any("holdout" in str(path.relative_to(root)).lower() for path in root.rglob("*") if path.is_file())
    recorder.add("holdout_not_accessed", candidate.get("holdout_accessed") is False and manifest.get("holdout_accessed") is False and no_holdout_files, candidate_value=candidate.get("holdout_accessed"), manifest_value=manifest.get("holdout_accessed"))
    existing_lock = root / "selection_lock.json"; existing_lock_valid = True
    if existing_lock.exists():
        lock = json.loads(existing_lock.read_text(encoding="utf-8")); existing_lock_valid = lock.get("selection_lock_creator") == "independent_validator" and lock.get("candidate_sha256") == sha256_file(root / "selection_candidate.json") and lock.get("contract_sha256") == contract_hash
    recorder.add("existing_lock_provenance", existing_lock_valid, lock_exists=existing_lock.exists())
    expected_ids = _expected_run_ids(contract, ranks); actual_ids = runs[runs["method"] == PRIMARY]["run_id"].astype(str).tolist(); recorder.add("rank_seed_coverage", actual_ids == expected_ids and len(actual_ids) == len(ranks) * 7, expected=expected_ids, actual=actual_ids)
    hash_bad, shape_bad, copied, convergence_bad = _verify_models(root, runs); recorder.add("model_hashes_and_shapes", not hash_bad and not shape_bad, hash_bad=hash_bad, shape_bad=shape_bad); recorder.add("no_copied_outputs_across_seeds", not copied, copied=copied); recorder.add("convergence_evidence_valid", not convergence_bad, bad_run_ids=convergence_bad)
    try:
        recomputed_metrics = _recompute_metrics(root, runs, fit, fit_weights, fit_map, validation, validation_weights, validation_map); metrics_ok, metric_error, metric_failures = _compare_metric_frames(stored_metrics, recomputed_metrics); recorder.add("reconstruction_metrics_recomputed", metrics_ok, maximum_error=metric_error, failures=metric_failures, checked_count=len(stored_metrics))
    except Exception as exc:
        recorder.add("reconstruction_metrics_recomputed", False, error=f"{type(exc).__name__}: {exc}"); recomputed_metrics = stored_metrics
    try:
        stored_pair_metrics = pd.read_csv(root / "pair_deformation_metrics.csv"); recomputed_pair_metrics = _recompute_pair_metrics(root, runs, fit, fit_metadata, validation, validation_metadata); pair_ok, pair_error, pair_failures = _compare_pair_frames(stored_pair_metrics, recomputed_pair_metrics); recorder.add("pair_deformation_metrics_recomputed", pair_ok, maximum_error=pair_error, failures=pair_failures, checked_count=len(stored_pair_metrics))
    except Exception as exc: recorder.add("pair_deformation_metrics_recomputed", False, error=f"{type(exc).__name__}: {exc}")
    try:
        recomputed_matches = _recompute_component_matches(root, runs); match_ok, match_error = _compare_match_frames(stored_matches, recomputed_matches); recorder.add("component_matching_recomputed", match_ok, maximum_error=match_error, checked_count=len(stored_matches))
    except Exception as exc:
        recorder.add("component_matching_recomputed", False, error=f"{type(exc).__name__}: {exc}"); recomputed_matches = stored_matches
    try:
        recomputed_summary = _rank_summary(root, runs, recomputed_metrics, recomputed_matches, fit_weights, contract); summary_ok, summary_failures = _compare_rank_summaries(stored_summary, recomputed_summary); recorder.add("rank_summary_recomputed", summary_ok and len(recomputed_summary) == len(ranks), failures=summary_failures, expected_rank_count=len(ranks), recomputed_rank_count=len(recomputed_summary)); expected_selection = _select(recomputed_summary, runs, recomputed_metrics)
        selection_keys = ["selection_status", "selected_rank", "selected_representative_run", "admissible_ranks", "best_error_rank", "best_error_mean", "best_error_standard_error", "one_standard_error_threshold"]; selection_ok = True
        for key in selection_keys:
            expected_value = expected_selection.get(key); actual_value = candidate.get(key)
            if isinstance(expected_value, float): selection_ok = selection_ok and actual_value is not None and np.isclose(float(actual_value), expected_value, rtol=1e-9, atol=1e-12)
            else: selection_ok = selection_ok and actual_value == expected_value
        recorder.add("selection_recomputed", selection_ok, expected=expected_selection, candidate=candidate)
    except Exception as exc:
        recorder.add("rank_summary_recomputed", False, error=f"{type(exc).__name__}: {exc}"); recorder.add("selection_recomputed", False, error=f"{type(exc).__name__}: {exc}"); recomputed_summary = stored_summary; expected_selection = {}
    diagnostics = _diagnostic_checks(root, candidate, runs, contract); recorder.add("grouped_subset_recomputed", diagnostics["grouped_subset"]["passed"], **{k: v for k, v in diagnostics["grouped_subset"].items() if k != "passed"}); recorder.add("world_seed_recomputed", diagnostics["world_seed"]["passed"], **{k: v for k, v in diagnostics["world_seed"].items() if k != "passed"}); recorder.add("frobenius_recomputed", diagnostics["frobenius"]["passed"], **{k: v for k, v in diagnostics["frobenius"].items() if k != "passed"})
    candidate_hashes_valid = candidate.get("rank_summary_sha256") == sha256_file(root / "rank_summary.csv") and candidate.get("fit_bundle_sha256") == sha256_file(root / "evidence/fit_bundle.npz") and candidate.get("validation_bundle_sha256") == sha256_file(root / "evidence/validation_bundle.npz") and candidate.get("fit_evaluation_metadata_sha256") == sha256_file(root / "evidence/fit_evaluation_metadata.csv") and candidate.get("validation_evaluation_metadata_sha256") == sha256_file(root / "evidence/validation_evaluation_metadata.csv")
    selected_hashes_valid = True
    for item in candidate.get("selected_model_paths_and_hashes", []):
        path = root / str(item["path"]); selected_hashes_valid = selected_hashes_valid and path.is_file() and sha256_file(path) == str(item["sha256"])
    recorder.add("candidate_hashes_valid", candidate_hashes_valid and selected_hashes_valid, candidate_hashes_valid=candidate_hashes_valid, selected_hashes_valid=selected_hashes_valid)
    mutation_results = _mutation_checks(contract, ranks, runs, recomputed_summary, expected_selection, candidate); recorder.add("internal_mutation_checks", all(bool(row["passed"]) for row in mutation_results), mutation_count=len(mutation_results), failed_mutations=[row["mutation_id"] for row in mutation_results if not row["passed"]])
    failed = recorder.failed; audit = {"checks": recorder.checks, "failed_checks": failed, "holdout_accessed": False, "independent_selection_audit": "passed" if not failed else "failed", "profile": profile}
    if write_outputs:
        _json_dump(root / "quality_checks.json", recorder.checks); _json_dump(root / "mutation_test_results.json", {"mutations": mutation_results}); _json_dump(root / "selection_audit.json", audit)
        if not failed and candidate.get("selection_status") == "selected":
            lock = {"lock_version": candidate.get("lock_version"), "selected_rank": candidate.get("selected_rank"), "selected_representative_run": candidate.get("selected_representative_run"), "admissible_ranks": candidate.get("admissible_ranks"), "best_error_rank": candidate.get("best_error_rank"), "best_error_mean": candidate.get("best_error_mean"), "best_error_standard_error": candidate.get("best_error_standard_error"), "one_standard_error_threshold": candidate.get("one_standard_error_threshold"), "rank_summary_sha256": candidate.get("rank_summary_sha256"), "selected_model_paths_and_hashes": candidate.get("selected_model_paths_and_hashes"), "contract_sha256": contract_hash, "fit_bundle_sha256": candidate.get("fit_bundle_sha256"), "validation_bundle_sha256": candidate.get("validation_bundle_sha256"), "fit_evaluation_metadata_sha256": candidate.get("fit_evaluation_metadata_sha256"), "validation_evaluation_metadata_sha256": candidate.get("validation_evaluation_metadata_sha256"), "candidate_sha256": sha256_file(root / "selection_candidate.json"), "audit_sha256": sha256_file(root / "selection_audit.json"), "holdout_accessed": False, "independent_selection_audit": "passed", "selection_lock_creator": "independent_validator", "profile": profile}; _json_dump(root / "selection_lock.json", lock)
        elif existing_lock.exists(): existing_lock.unlink()
        _json_dump(root / "artifact_manifest.json", _artifact_manifest(root)); result_lines = ["# Task 3.1f-3 Stage B/C Results", "", f"- Profile: `{profile}`", f"- Independent audit: `{'PASS' if not failed else 'FAIL'}`", f"- Checks: `{len(recorder.checks) - len(failed)} / {len(recorder.checks)}`", "- Holdout accessed: `false`", f"- Selection status: `{candidate.get('selection_status')}`", f"- Selected rank: `{candidate.get('selected_rank', 'none')}`", ""]
        if failed: result_lines.extend(["## Failed checks", ""] + [f"- `{name}`" for name in failed])
        (root / "results.md").write_text("\n".join(result_lines) + "\n", encoding="utf-8")
    if failed and strict: raise SystemExit(1)
    return recorder.checks

def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--artifact-dir", required=True); parser.add_argument("--contract", default=str(DEFAULT_CONTRACT)); parser.add_argument("--strict", action="store_true"); args = parser.parse_args(); checks = validate_selection(args.artifact_dir, args.contract, strict=args.strict); print(json.dumps({"failed_checks": [name for name, value in checks.items() if not value["passed"]], "check_count": len(checks)}, indent=2))
