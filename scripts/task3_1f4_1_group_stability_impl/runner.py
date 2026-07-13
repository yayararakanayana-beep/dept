from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import pandas as pd

from .common import (
    AXIS_NAMES,
    CROSS_RANK_PAIRS,
    OUTPUT_DIR_NAME,
    TARGET_RANKS,
    _assert_no_holdout,
    _json_dump,
    _load_bundle,
    _load_contract,
    _utc_now,
    sha256_file,
)
from .cross_rank import _cross_rank_tables, _load_representatives, _seed_stability_tables
from .native import _weighted_global_distribution, native_signature_tables
from .subset_analysis import _aggregate_stability, _subset_stability_tables
from .subsets import _copy_or_fit_subset_models


def _artifact_manifest(root: Path) -> dict[str, Any]:
    entries = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "artifact_manifest.json":
            continue
        entries.append(
            {
                "path": str(path.relative_to(root)),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    return {"schema_version": "task3.1f-4.1-artifact-manifest-v1", "files": entries}


def run_group_stability_audit(
    source_artifact_dir: str | Path,
    output_root: str | Path,
    contract_path: str | Path,
    *,
    source_artifact_id: int,
    source_artifact_digest: str,
    profile: str = "formal",
) -> Path:
    if profile not in {"formal", "smoke"}:
        raise ValueError("profile must be formal or smoke")
    source_root = Path(source_artifact_dir)
    _assert_no_holdout(source_root)
    task_contract = _load_contract(Path(contract_path))
    expected_id = int(task_contract["input"]["stage_bc_artifact_id"])
    expected_digest = str(task_contract["input"]["stage_bc_artifact_digest"])
    if profile == "formal" and source_artifact_id != expected_id:
        raise ValueError("formal source Artifact ID differs from frozen contract")
    if profile == "formal" and source_artifact_digest != expected_digest:
        raise ValueError("formal source Artifact digest differs from frozen contract")
    required = [
        "model_runs.csv",
        "rank_summary.csv",
        "contract_snapshot.json",
        "evidence/fit_bundle.npz",
        "evidence/fit_row_map.csv",
        "evidence/validation_bundle.npz",
        "evidence/validation_row_map.csv",
    ]
    for relative in required:
        if not (source_root / relative).is_file():
            raise ValueError(f"required Stage B/C file is missing: {relative}")
    stage_contract = json.loads((source_root / "contract_snapshot.json").read_text(encoding="utf-8"))
    if stage_contract.get("contract_version") != "task3.1f-1-rc1":
        raise ValueError("unexpected source Stage B/C contract")
    fit, fit_weights, fit_map = _load_bundle(
        source_root / "evidence/fit_bundle.npz", source_root / "evidence/fit_row_map.csv"
    )
    validation, validation_weights, validation_map = _load_bundle(
        source_root / "evidence/validation_bundle.npz", source_root / "evidence/validation_row_map.csv"
    )
    if set(fit_map["dataset_split"].astype(str)) != {"fit"}:
        raise ValueError("fit bundle contains non-fit rows")
    if set(validation_map["dataset_split"].astype(str)) != {"validation"}:
        raise ValueError("validation bundle contains non-validation rows")
    n_bins = int(task_contract["native_grid"]["n_bins"])
    expected_cells = n_bins ** len(AXIS_NAMES)
    if profile == "formal" and fit.shape != (1082, expected_cells):
        raise ValueError(f"formal fit shape differs from frozen contract: {fit.shape}")
    if profile == "formal" and validation.shape != (256, expected_cells):
        raise ValueError(f"formal validation shape differs from frozen contract: {validation.shape}")
    if fit.shape[1] != expected_cells or validation.shape[1] != expected_cells:
        raise ValueError("input cell count differs from native 5-axis grid")

    output = Path(output_root) / OUTPUT_DIR_NAME
    shutil.rmtree(output, ignore_errors=True)
    output.mkdir(parents=True, exist_ok=False)
    started = _utc_now()
    runs, rank_summary, representatives = _load_representatives(source_root)
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
    native_marginals = pd.concat(marginal_frames, ignore_index=True)
    native_contributions = pd.concat(contribution_frames, ignore_index=True)
    native_pair_joint = pd.concat(pair_joint_frames, ignore_index=True)
    native_pair_summary = pd.concat(pair_summary_frames, ignore_index=True)

    cross_single, cross_group, cross_members, cross_activation = _cross_rank_tables(
        representatives, task_contract, n_bins
    )
    seed_group, seed_signature = _seed_stability_tables(
        source_root, runs, representatives, task_contract, n_bins
    )
    subset_run_diagnostics, subset_model_records = _copy_or_fit_subset_models(
        source_root=source_root,
        output_root=output,
        fit=fit,
        fit_weights=fit_weights,
        fit_map=fit_map,
        validation=validation,
        rank_representatives=representatives,
        stage_contract=stage_contract,
        task_contract=task_contract,
        profile=profile,
    )
    subset_diagnostics, subset_matches, subset_signature, subset_activation = _subset_stability_tables(
        output,
        subset_model_records,
        representatives,
        validation,
        validation_weights,
        task_contract,
        n_bins,
    )
    subset_run_diagnostics.to_csv(output / "subset_run_diagnostics.csv", index=False)
    subset_diagnostics.to_csv(output / "subset_group_diagnostics.csv", index=False)

    rank_efficiency, rank_operational, recommendations = _aggregate_stability(
        rank_summary, seed_group, subset_matches, subset_diagnostics, task_contract
    )

    outputs = {
        "native_axis_marginals.csv": native_marginals,
        "native_axis_contribution_shares.csv": native_contributions,
        "native_axis_pairwise_joint.csv": native_pair_joint,
        "native_axis_relation_summary.csv": native_pair_summary,
        "cross_rank_single_matches.csv": cross_single,
        "cross_rank_group_matches.csv": cross_group,
        "cross_rank_group_members.csv": cross_members,
        "cross_rank_activation_consistency.csv": cross_activation,
        "seed_group_stability.csv": seed_group,
        "seed_native_signature_stability.csv": seed_signature,
        "subset_group_matches.csv": subset_matches,
        "subset_native_signature_stability.csv": subset_signature,
        "subset_activation_consistency.csv": subset_activation,
        "rank_information_efficiency.csv": rank_efficiency,
        "rank_operational_comparison.csv": rank_operational,
    }
    for filename, frame in outputs.items():
        frame.to_csv(output / filename, index=False)

    source_provenance = {
        "stage_bc_artifact_id": source_artifact_id,
        "stage_bc_artifact_digest": source_artifact_digest,
        "source_contract_sha256": sha256_file(source_root / "contract_snapshot.json"),
        "source_rank_summary_sha256": sha256_file(source_root / "rank_summary.csv"),
        "source_model_runs_sha256": sha256_file(source_root / "model_runs.csv"),
        "fit_bundle_sha256": sha256_file(source_root / "evidence/fit_bundle.npz"),
        "validation_bundle_sha256": sha256_file(source_root / "evidence/validation_bundle.npz"),
        "holdout_accessed": False,
    }
    _json_dump(output / "input_provenance.json", source_provenance)
    shutil.copy2(contract_path, output / "contract.json")
    candidate = {
        "schema_version": "task3.1f-4.1-comparative-recommendation-v1",
        "status": "candidate_pending_independent_validation",
        "automatic_rank_selection": False,
        "selected_rank": None,
        "holdout_accessed": False,
        "recommendations": recommendations,
        "producer_created_final_recommendation": False,
    }
    _json_dump(output / "comparative_recommendation_candidate.json", candidate)
    _json_dump(
        output / "execution_manifest.json",
        {
            "task": "Task 3.1f-4.1",
            "profile": profile,
            "started_at": started,
            "completed_at": _utc_now(),
            "ranks": list(TARGET_RANKS),
            "cross_rank_pairs": [list(pair) for pair in CROSS_RANK_PAIRS],
            "fit_rows": len(fit),
            "validation_rows": len(validation),
            "cell_count": fit.shape[1],
            "n_bins": n_bins,
            "holdout_accessed": False,
            "selection_lock_created": False,
            "final_recommendation_created_by_producer": False,
            "python": sys.version,
        },
    )
    (output / "results.md").write_text(
        "# Task 3.1f-4.1 Structure-Group Stability Audit\n\n"
        f"- Profile: `{profile}`\n"
        "- Holdout accessed: `false`\n"
        "- Automatic rank selection: `false`\n"
        f"- Ranks compared: `{list(TARGET_RANKS)}`\n"
        "- Independent validation: `pending`\n",
        encoding="utf-8",
    )
    _json_dump(output / "quality_checks.json", {"status": "pending_independent_validation", "holdout_accessed": False})
    _json_dump(output / "artifact_manifest.json", _artifact_manifest(output))
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Task 3.1f-4.1 cross-rank structure-group stability audit.")
    parser.add_argument("--source-artifact-dir", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--contract", default="configs/task3_1f4_1_group_stability_contract.json")
    parser.add_argument("--source-artifact-id", type=int, required=True)
    parser.add_argument("--source-artifact-digest", required=True)
    parser.add_argument("--profile", choices=("formal", "smoke"), default="formal")
    args = parser.parse_args()
    output = run_group_stability_audit(
        args.source_artifact_dir,
        args.output_root,
        args.contract,
        source_artifact_id=args.source_artifact_id,
        source_artifact_digest=args.source_artifact_digest,
        profile=args.profile,
    )
    print(output)


if __name__ == "__main__":
    main()
