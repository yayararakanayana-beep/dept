from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from task3_1f3_fixture import build_stage_bc_smoke_bundles
from task3_1f_structure_extraction import formal_run_plan, run_stage_bc_smoke, validate_selection
from task3_1f_structure_extraction.contract import DEFAULT_CONTRACT


def test_formal_run_plan_contains_exactly_49_primary_runs() -> None:
    plan = formal_run_plan(DEFAULT_CONTRACT)
    assert len(plan) == 49
    assert sorted({row["rank"] for row in plan}) == [5, 8, 10, 12, 15, 20, 25]
    assert all(sum(row["rank"] == rank for row in plan) == 7 for rank in [5, 8, 10, 12, 15, 20, 25])


@pytest.fixture(scope="session")
def stage_bc_pipeline(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    root = tmp_path_factory.mktemp("task3_1f3_repaired")
    bundles = build_stage_bc_smoke_bundles(root / "input")
    output = run_stage_bc_smoke(
        bundles["fit_bundle"],
        bundles["fit_row_map"],
        bundles["validation_bundle"],
        bundles["validation_row_map"],
        root / "run",
        DEFAULT_CONTRACT,
        smoke_ranks=2,
        fit_evaluation_metadata=bundles["fit_evaluation_metadata"],
        validation_evaluation_metadata=bundles["validation_evaluation_metadata"],
    )
    checks = validate_selection(output, DEFAULT_CONTRACT, strict=True, write_outputs=True)
    assert all(result["passed"] for result in checks.values()), checks
    return {"root": root, "output": output, **bundles}


def test_smoke_executes_two_ranks_and_all_initializations(stage_bc_pipeline: dict[str, Path]) -> None:
    runs = pd.read_csv(stage_bc_pipeline["output"] / "model_runs.csv")
    primary = runs[runs["method"] == "nmf_kl"]
    assert sorted(primary["rank"].unique().tolist()) == [5, 8]
    assert primary.groupby("rank").size().to_dict() == {5: 7, 8: 7}
    assert primary[primary["run_role"] == "random_init"].groupby("rank")["init_seed"].apply(list).iloc[0] == [31011, 31012, 31013, 31014, 31015, 31016]


def test_independent_validator_creates_complete_lock(stage_bc_pipeline: dict[str, Path]) -> None:
    output = stage_bc_pipeline["output"]
    lock = json.loads((output / "selection_lock.json").read_text(encoding="utf-8"))
    audit = json.loads((output / "selection_audit.json").read_text(encoding="utf-8"))
    assert lock["selection_lock_creator"] == "independent_validator"
    assert lock["holdout_accessed"] is False
    assert lock["selected_rank"] == 5
    assert lock["rank_summary_sha256"]
    assert len(lock["selected_model_paths_and_hashes"]) == 3
    assert audit["independent_selection_audit"] == "passed"


def test_real_pair_subset_world_and_frobenius_outputs(stage_bc_pipeline: dict[str, Path]) -> None:
    output = stage_bc_pipeline["output"]
    pair_metrics = pd.read_csv(output / "pair_deformation_metrics.csv")
    subsets = pd.read_csv(output / "grouped_subset_diagnostics.csv")
    worlds = pd.read_csv(output / "world_seed_diagnostics.csv")
    frobenius = pd.read_csv(output / "frobenius_sensitivity.csv")
    assert len(pair_metrics) > 0
    assert len(subsets) == 5
    assert subsets["group_preserving"].astype(bool).all()
    assert subsets["basis_path"].map(lambda path: (output / path).is_file()).all()
    assert set(worlds["world_seed"].astype(int)) == {0, 1}
    assert worlds["basis_path"].map(lambda path: (output / path).is_file()).all()
    assert len(frobenius) == 6
    assert frobenius["basis_path"].map(lambda path: (output / path).is_file()).all()
    assert not frobenius["influenced_primary_selection"].astype(bool).any()


def test_rank_and_structure_outputs_are_measured(stage_bc_pipeline: dict[str, Path]) -> None:
    output = stage_bc_pipeline["output"]
    ranks = pd.read_csv(output / "rank_summary.csv")
    structures = pd.read_csv(output / "structure_summary.csv")
    assert ranks["rank"].tolist() == [5, 8]
    assert bool(ranks.loc[ranks["rank"] == 5, "selected"].iloc[0]) is True
    assert "subset_survival_count" in structures.columns
    assert "world_seed_0_similarity" in structures.columns
    assert "world_seed_1_similarity" in structures.columns
    assert set(structures["handoff_status"]).issubset({"stable_structure", "conditional_structure", "excluded_duplicate", "excluded_inactive", "unstable"})


@pytest.mark.parametrize(
    "mutation,failed_check",
    [
        ("missing_seed", "rank_seed_coverage"),
        ("forged_convergence", "convergence_evidence_valid"),
        ("modified_basis_hash", "model_hashes_and_shapes"),
        ("fixed_rank_summary", "rank_summary_recomputed"),
        ("fixed_pair_metrics", "pair_deformation_metrics_recomputed"),
        ("producer_lock", "existing_lock_provenance"),
        ("holdout_file", "holdout_not_accessed"),
        ("broken_subset", "grouped_subset_recomputed"),
    ],
)
def test_independent_validator_rejects_mutations(
    stage_bc_pipeline: dict[str, Path], tmp_path: Path, mutation: str, failed_check: str
) -> None:
    source = stage_bc_pipeline["output"]
    target = tmp_path / mutation
    shutil.copytree(source, target)
    if mutation == "missing_seed":
        runs = pd.read_csv(target / "model_runs.csv")
        runs = runs[runs["run_id"] != "nmf_kl_rank05_seed31016"]
        runs.to_csv(target / "model_runs.csv", index=False)
    elif mutation == "forged_convergence":
        runs = pd.read_csv(target / "model_runs.csv")
        index = runs[runs["method"] == "nmf_kl"].index[0]
        runs.loc[index, "converged"] = True
        runs.loc[index, "n_iter"] = runs.loc[index, "max_iter"]
        runs.to_csv(target / "model_runs.csv", index=False)
    elif mutation == "modified_basis_hash":
        runs = pd.read_csv(target / "model_runs.csv")
        index = runs[runs["method"] == "nmf_kl"].index[0]
        runs.loc[index, "basis_sha256"] = "0" * 64
        runs.to_csv(target / "model_runs.csv", index=False)
    elif mutation == "fixed_rank_summary":
        summary = pd.read_csv(target / "rank_summary.csv")
        summary["stable_component_fraction"] = 1.0
        summary.to_csv(target / "rank_summary.csv", index=False)
    elif mutation == "fixed_pair_metrics":
        metrics = pd.read_csv(target / "pair_deformation_metrics.csv")
        metrics["value"] = 0.0
        metrics.to_csv(target / "pair_deformation_metrics.csv", index=False)
    elif mutation == "producer_lock":
        (target / "selection_lock.json").write_text(
            json.dumps({"selection_lock_creator": "producer", "contract_sha256": "x", "candidate_sha256": "x"}),
            encoding="utf-8",
        )
    elif mutation == "holdout_file":
        (target / "holdout_metrics.csv").write_text("x\n1\n", encoding="utf-8")
    elif mutation == "broken_subset":
        subsets = pd.read_csv(target / "grouped_subset_diagnostics.csv")
        subsets.loc[0, "group_preserving"] = False
        subsets.to_csv(target / "grouped_subset_diagnostics.csv", index=False)
    checks = validate_selection(target, DEFAULT_CONTRACT, strict=False, write_outputs=False)
    assert checks[failed_check]["passed"] is False
