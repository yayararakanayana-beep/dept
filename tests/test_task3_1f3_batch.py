from __future__ import annotations

import json, shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from task3_1f_structure_extraction import formal_run_plan, grouped_subsets, run_stage_bc_smoke, validate_selection
from task3_1f_structure_extraction.batch import select_rank
from task3_1f_structure_extraction.contract import DEFAULT_CONTRACT, load_contract


def test_formal_run_plan_contains_49_primary_runs() -> None:
    plan = formal_run_plan(DEFAULT_CONTRACT)
    assert len(plan) == 49
    assert [p["rank"] for p in plan].count(5) == 7
    assert [p["init_seed"] for p in plan[:7]] == [0, 31011, 31012, 31013, 31014, 31015, 31016]
    assert sorted(set(p["rank"] for p in plan)) == [5, 8, 10, 12, 15, 20, 25]


@pytest.fixture(scope="session")
def stage_bc_pipeline(valid_pipeline: dict[str, Path], tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    root = tmp_path_factory.mktemp("task3_1f3")
    bundles = valid_pipeline["bundles"]
    out = run_stage_bc_smoke(
        bundles / "fit_bundle.npz",
        bundles / "fit_row_map.csv",
        bundles / "validation_bundle.npz",
        bundles / "validation_row_map.csv",
        root / "run",
        DEFAULT_CONTRACT,
    )
    checks = validate_selection(out, DEFAULT_CONTRACT, strict=True)
    assert all(c["passed"] for c in checks.values()), checks
    return {"root": root, "output": out, "bundles": bundles}


def test_smoke_uses_multiple_ranks_all_initializations(stage_bc_pipeline: dict[str, Path]) -> None:
    runs = pd.read_csv(stage_bc_pipeline["output"] / "model_runs.csv")
    nmf = runs[runs.method == "nmf_kl"]
    assert sorted(nmf["rank"].unique().tolist()) == [5, 8]
    assert nmf.groupby("rank").size().tolist() == [7, 7]
    assert nmf[nmf.run_role == "random_init"].groupby("rank")["init_seed"].apply(list).iloc[0] == [31011, 31012, 31013, 31014, 31015, 31016]


def test_independent_validator_creates_lock_after_recompute(stage_bc_pipeline: dict[str, Path]) -> None:
    out = stage_bc_pipeline["output"]
    lock = json.loads((out / "selection_lock.json").read_text())
    audit = json.loads((out / "selection_audit.json").read_text())
    assert lock["selection_lock_creator"] == "independent_validator"
    assert lock["holdout_accessed"] is False
    assert audit["independent_selection_audit"] == "passed"
    assert audit["checks"]["selection_recomputed"]["passed"] is True


def test_selection_rule_smallest_rank_within_one_standard_error() -> None:
    summary = pd.DataFrame({"rank": [5, 8, 10], "admissible": [True, True, True], "representative_run_id": ["r5a", "r8a", "r10a"]})
    runs = pd.DataFrame({"method": ["nmf_kl"] * 6, "rank": [5, 5, 8, 8, 10, 10], "run_id": ["r5a", "r5b", "r8a", "r8b", "r10a", "r10b"], "converged": [True] * 6})
    rows = []
    vals = {"r5a": .111, "r5b": .109, "r8a": .100, "r8b": .120, "r10a": .080, "r10b": .120}
    for rid, val in vals.items():
        rows.append({"run_id": rid, "split": "validation", "subgroup_type": "all", "subgroup_value": "all", "weighting": "weighted", "metric": "js_distance", "aggregation": "mean", "value": val})
    selected = select_rank(summary, runs, pd.DataFrame(rows))
    assert selected["best_error_rank"] == 10
    assert selected["selected_rank"] == 5


def test_grouped_subsets_are_deterministic_and_group_preserving(valid_pipeline: dict[str, Path]) -> None:
    fit_map = pd.read_csv(valid_pipeline["bundles"] / "fit_row_map.csv")
    contract = load_contract(DEFAULT_CONTRACT)
    a = grouped_subsets(fit_map, contract)
    b = grouped_subsets(fit_map, contract)
    assert a == b
    assert len(a) == 5
    assert all(item["group_preserving"] for item in a)


def test_no_admissible_rank_produces_no_lock(tmp_path: Path) -> None:
    summary = pd.DataFrame({"rank": [5], "admissible": [False], "representative_run_id": [""]})
    assert select_rank(summary, pd.DataFrame(), pd.DataFrame())["selection_status"] == "no_admissible_rank"


@pytest.mark.parametrize("mutation,check", [
    ("missing_seed", "rank_seed_coverage"),
    ("forged_convergence", "convergence_evidence_valid"),
    ("modified_basis_hash", "model_hashes_and_shapes"),
    ("producer_lock", "producer_did_not_create_lock"),
])
def test_independent_validator_rejects_mutations(stage_bc_pipeline: dict[str, Path], tmp_path: Path, mutation: str, check: str) -> None:
    src = stage_bc_pipeline["output"]
    dst = tmp_path / mutation
    shutil.copytree(src, dst)
    if mutation == "missing_seed":
        runs = pd.read_csv(dst / "model_runs.csv")
        runs = runs[runs.run_id != "nmf_kl_rank05_seed31016"]
        runs.to_csv(dst / "model_runs.csv", index=False)
    elif mutation == "forged_convergence":
        runs = pd.read_csv(dst / "model_runs.csv")
        idx = runs[runs.method == "nmf_kl"].index[0]
        runs.loc[idx, "converged"] = True
        runs.loc[idx, "n_iter"] = runs.loc[idx, "max_iter"]
        runs.to_csv(dst / "model_runs.csv", index=False)
    elif mutation == "modified_basis_hash":
        runs = pd.read_csv(dst / "model_runs.csv")
        idx = runs[runs.method == "nmf_kl"].index[0]
        runs.loc[idx, "basis_sha256"] = "0" * 64
        runs.to_csv(dst / "model_runs.csv", index=False)
    elif mutation == "producer_lock":
        (dst / "selection_lock.json").write_text(json.dumps({"independent_selection_audit": "passed", "selection_lock_creator": "producer"}))
    checks = validate_selection(dst, DEFAULT_CONTRACT, strict=False, write_outputs=False)
    assert checks[check]["passed"] is False


def test_smoke_contains_required_stage_bc_artifacts(stage_bc_pipeline: dict[str, Path]) -> None:
    out = stage_bc_pipeline["output"]
    required = [
        "model_runs.csv", "reconstruction_metrics.csv", "pair_deformation_metrics.csv", "component_matches.csv",
        "rank_stability_summary.csv", "rank_summary.csv", "internal_structure_similarity.csv", "structure_summary.csv",
        "selection_candidate.json", "selection_audit.json", "selection_lock.json", "quality_checks.json",
        "mutation_test_results.json", "artifact_manifest.json", "results.md", "frobenius_sensitivity.csv",
        "grouped_subset_diagnostics.csv", "world_seed_diagnostics.csv",
    ]
    assert all((out / name).is_file() for name in required)
    candidate = json.loads((out / "selection_candidate.json").read_text())
    assert candidate["profile"] == "smoke"
    assert candidate["formal_scientific_result"] is False
    assert candidate["holdout_accessed"] is False
