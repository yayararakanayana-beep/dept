from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import pandas as pd

from task3_1f4_1_group_stability_impl import (
    TARGET_RANKS,
    _aggregate_stability,
    _artifact_manifest,
    _assert_no_holdout,
    _cross_rank_tables,
    _load_bundle,
    _load_contract,
    _load_representatives,
    _seed_stability_tables,
    _subset_stability_tables,
    _weighted_global_distribution,
    native_signature_tables,
    sha256_file,
)


def _json_dump(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def _compare_frames(name: str, expected: pd.DataFrame, actual_path: Path) -> None:
    if not actual_path.is_file():
        raise ValueError(f"missing output table: {actual_path.name}")
    actual = pd.read_csv(actual_path)
    if list(expected.columns) != list(actual.columns):
        raise ValueError(f"{name} columns differ")
    pd.testing.assert_frame_equal(
        expected.reset_index(drop=True),
        actual.reset_index(drop=True),
        check_dtype=False,
        check_exact=False,
        rtol=1e-9,
        atol=1e-12,
        check_like=False,
    )


def _validate_manifest(output: Path) -> dict[str, Any]:
    manifest_path = output / "artifact_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "task3.1f-4.1-artifact-manifest-v1":
        raise ValueError("unexpected artifact manifest schema")
    seen: set[str] = set()
    for entry in manifest.get("files", []):
        relative = str(entry["path"])
        if relative in seen:
            raise ValueError(f"duplicate manifest entry: {relative}")
        seen.add(relative)
        path = output / relative
        if not path.is_file():
            raise ValueError(f"manifest file missing: {relative}")
        if int(entry["size_bytes"]) != path.stat().st_size:
            raise ValueError(f"manifest size mismatch: {relative}")
        if str(entry["sha256"]) != sha256_file(path):
            raise ValueError(f"manifest hash mismatch: {relative}")
    required = {
        "contract.json",
        "input_provenance.json",
        "execution_manifest.json",
        "native_axis_marginals.csv",
        "native_axis_contribution_shares.csv",
        "native_axis_pairwise_joint.csv",
        "native_axis_relation_summary.csv",
        "cross_rank_single_matches.csv",
        "cross_rank_group_matches.csv",
        "cross_rank_group_members.csv",
        "cross_rank_activation_consistency.csv",
        "seed_group_stability.csv",
        "seed_native_signature_stability.csv",
        "subset_run_diagnostics.csv",
        "subset_group_diagnostics.csv",
        "subset_group_matches.csv",
        "subset_native_signature_stability.csv",
        "subset_activation_consistency.csv",
        "rank_information_efficiency.csv",
        "rank_operational_comparison.csv",
        "comparative_recommendation_candidate.json",
        "quality_checks.json",
        "results.md",
    }
    missing = required - seen
    if missing:
        raise ValueError(f"manifest missing required files: {sorted(missing)}")
    return manifest


def _subset_records(output: Path) -> dict[tuple[int, str], dict[str, Any]]:
    diagnostics = pd.read_csv(output / "subset_run_diagnostics.csv")
    records: dict[tuple[int, str], dict[str, Any]] = {}
    for row in diagnostics.itertuples(index=False):
        if str(row.model_status) != "completed":
            continue
        basis_path = output / str(row.basis_path)
        model_dir = basis_path.parent
        metadata_path = model_dir / "run_metadata.json"
        fit_path = model_dir / "fit_activations.npy"
        validation_path = model_dir / "validation_activations.npy"
        for path in (basis_path, metadata_path, fit_path, validation_path):
            if not path.is_file():
                raise ValueError(f"subset model file missing: {path}")
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if sha256_file(basis_path) != str(metadata["basis_sha256"]):
            raise ValueError("subset basis hash mismatch")
        if sha256_file(fit_path) != str(metadata["fit_activation_sha256"]):
            raise ValueError("subset fit activation hash mismatch")
        if sha256_file(validation_path) != str(metadata["validation_activation_sha256"]):
            raise ValueError("subset validation activation hash mismatch")
        records[(int(row.rank), str(row.subset_id))] = {
            **metadata,
            "basis_path": str(basis_path.relative_to(output)),
            "fit_activation_path": str(fit_path.relative_to(output)),
            "validation_activation_path": str(validation_path.relative_to(output)),
        }
    expected_count = len(TARGET_RANKS) * 5
    if len(records) != expected_count:
        raise ValueError(f"expected {expected_count} completed subset models, found {len(records)}")
    return records


def validate_group_stability(
    artifact_dir: str | Path,
    source_artifact_dir: str | Path,
    *,
    strict: bool = False,
) -> dict[str, dict[str, Any]]:
    output = Path(artifact_dir)
    source = Path(source_artifact_dir)
    checks: dict[str, dict[str, Any]] = {}

    def run_check(name: str, function) -> None:
        try:
            detail = function()
            checks[name] = {"passed": True, "detail": detail if detail is not None else "ok"}
        except Exception as exc:
            checks[name] = {"passed": False, "detail": f"{type(exc).__name__}: {exc}"}

    run_check("holdout_absent", lambda: (_assert_no_holdout(output), _assert_no_holdout(source), "absent")[-1])
    run_check(
        "selection_lock_absent",
        lambda: "absent"
        if not (output / "selection_lock.json").exists()
        else (_ for _ in ()).throw(ValueError("selection lock is prohibited")),
    )
    run_check("artifact_manifest", lambda: len(_validate_manifest(output).get("files", [])))

    task_contract: dict[str, Any] = {}
    provenance: dict[str, Any] = {}

    def load_contract_and_provenance() -> str:
        nonlocal task_contract, provenance
        task_contract = _load_contract(output / "contract.json")
        provenance = json.loads((output / "input_provenance.json").read_text(encoding="utf-8"))
        if provenance.get("holdout_accessed") is not False:
            raise ValueError("input provenance does not preserve holdout=false")
        execution = json.loads((output / "execution_manifest.json").read_text(encoding="utf-8"))
        if execution.get("profile") == "formal":
            if int(provenance["stage_bc_artifact_id"]) != int(task_contract["input"]["stage_bc_artifact_id"]):
                raise ValueError("source artifact ID mismatch")
            if str(provenance["stage_bc_artifact_digest"]) != str(task_contract["input"]["stage_bc_artifact_digest"]):
                raise ValueError("source artifact digest mismatch")
        expected_hashes = {
            "source_contract_sha256": source / "contract_snapshot.json",
            "source_rank_summary_sha256": source / "rank_summary.csv",
            "source_model_runs_sha256": source / "model_runs.csv",
            "fit_bundle_sha256": source / "evidence/fit_bundle.npz",
            "validation_bundle_sha256": source / "evidence/validation_bundle.npz",
        }
        for key, path in expected_hashes.items():
            if str(provenance[key]) != sha256_file(path):
                raise ValueError(f"source provenance hash mismatch: {key}")
        return "verified"

    run_check("contract_and_provenance", load_contract_and_provenance)
    recomputed: dict[str, Any] = {}

    def recompute_core() -> str:
        if not task_contract:
            raise ValueError("contract check must pass first")
        fit, fit_weights, fit_map = _load_bundle(source / "evidence/fit_bundle.npz", source / "evidence/fit_row_map.csv")
        validation, validation_weights, validation_map = _load_bundle(
            source / "evidence/validation_bundle.npz", source / "evidence/validation_row_map.csv"
        )
        if set(fit_map["dataset_split"].astype(str)) != {"fit"} or set(validation_map["dataset_split"].astype(str)) != {"validation"}:
            raise ValueError("source split integrity failure")
        runs, rank_summary, representatives = _load_representatives(source)
        n_bins = int(task_contract["native_grid"]["n_bins"])
        global_distribution = _weighted_global_distribution(fit, fit_weights)
        marginal_frames = []
        contribution_frames = []
        pair_joint_frames = []
        pair_summary_frames = []
        for rank in TARGET_RANKS:
            tables = native_signature_tables(
                rank=rank,
                run_id=representatives[rank]["run_id"],
                basis=representatives[rank]["basis"],
                global_distribution=global_distribution,
                n_bins=n_bins,
            )
            marginal_frames.append(tables[0])
            contribution_frames.append(tables[1])
            pair_joint_frames.append(tables[2])
            pair_summary_frames.append(tables[3])
        expected_native = {
            "native_axis_marginals.csv": pd.concat(marginal_frames, ignore_index=True),
            "native_axis_contribution_shares.csv": pd.concat(contribution_frames, ignore_index=True),
            "native_axis_pairwise_joint.csv": pd.concat(pair_joint_frames, ignore_index=True),
            "native_axis_relation_summary.csv": pd.concat(pair_summary_frames, ignore_index=True),
        }
        for filename, frame in expected_native.items():
            _compare_frames(filename, frame, output / filename)
        cross = _cross_rank_tables(representatives, task_contract, n_bins)
        for filename, frame in zip(
            (
                "cross_rank_single_matches.csv",
                "cross_rank_group_matches.csv",
                "cross_rank_group_members.csv",
                "cross_rank_activation_consistency.csv",
            ),
            cross,
        ):
            _compare_frames(filename, frame, output / filename)
        seed = _seed_stability_tables(source, runs, representatives, task_contract, n_bins)
        _compare_frames("seed_group_stability.csv", seed[0], output / "seed_group_stability.csv")
        _compare_frames("seed_native_signature_stability.csv", seed[1], output / "seed_native_signature_stability.csv")
        records = _subset_records(output)
        subset = _subset_stability_tables(
            output,
            records,
            representatives,
            validation,
            validation_weights,
            task_contract,
            n_bins,
        )
        for filename, frame in zip(
            (
                "subset_group_diagnostics.csv",
                "subset_group_matches.csv",
                "subset_native_signature_stability.csv",
                "subset_activation_consistency.csv",
            ),
            subset,
        ):
            _compare_frames(filename, frame, output / filename)
        aggregate = _aggregate_stability(rank_summary, seed[0], subset[1], subset[0], task_contract)
        _compare_frames("rank_information_efficiency.csv", aggregate[0], output / "rank_information_efficiency.csv")
        _compare_frames("rank_operational_comparison.csv", aggregate[1], output / "rank_operational_comparison.csv")
        recomputed.update(
            {
                "recommendations": aggregate[2],
                "fit_rows": len(fit),
                "validation_rows": len(validation),
                "cell_count": fit.shape[1],
            }
        )
        return "all derived tables reproduced"

    run_check("independent_recomputation", recompute_core)

    def validate_candidate() -> str:
        candidate = json.loads((output / "comparative_recommendation_candidate.json").read_text(encoding="utf-8"))
        if candidate.get("automatic_rank_selection") is not False or candidate.get("selected_rank") is not None:
            raise ValueError("candidate performed prohibited automatic rank selection")
        if candidate.get("holdout_accessed") is not False:
            raise ValueError("candidate does not preserve holdout=false")
        if recomputed and candidate.get("recommendations") != recomputed["recommendations"]:
            raise ValueError("candidate recommendations differ from independent recomputation")
        return "verified"

    run_check("candidate_recommendation", validate_candidate)

    passed = all(check["passed"] for check in checks.values())
    _json_dump(
        output / "quality_checks.json",
        {
            "status": "passed" if passed else "failed",
            "independent_validator": True,
            "holdout_accessed": False,
            "checks": checks,
        },
    )
    if passed:
        candidate = json.loads((output / "comparative_recommendation_candidate.json").read_text(encoding="utf-8"))
        final = {
            **candidate,
            "status": "validated_comparative_recommendation",
            "producer_created_final_recommendation": False,
            "independent_validator_created_final_recommendation": True,
            "validation_checks": sorted(checks),
        }
        _json_dump(output / "comparative_recommendation.json", final)
        results = (output / "results.md").read_text(encoding="utf-8")
        results = results.replace("- Independent validation: `pending`", "- Independent validation: `passed`")
        (output / "results.md").write_text(results, encoding="utf-8")
        _json_dump(output / "artifact_manifest.json", _artifact_manifest(output))
    if strict and not passed:
        failed = {name: value for name, value in checks.items() if not value["passed"]}
        raise SystemExit(f"Task 3.1f-4.1 independent validation failed: {failed}")
    return checks


def main() -> None:
    parser = argparse.ArgumentParser(description="Independently validate Task 3.1f-4.1 artifacts.")
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--source-artifact-dir", required=True)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    checks = validate_group_stability(args.artifact_dir, args.source_artifact_dir, strict=args.strict)
    print(json.dumps(checks, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
