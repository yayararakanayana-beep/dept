from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from .contract import DEFAULT_CONTRACT, canonical_contract_text, load_contract, sha256_file, sha256_text
from .runner import _load_bundle
from .stage_bc_run import _json_dump, _load_evaluation_metadata, _execute_primary_runs, _reference_runs, run_plan
from .stage_bc_metrics import _all_reconstruction_metrics, _all_pair_metrics, _component_matches
from .stage_bc_selection_core import rank_summaries, select_rank
from .stage_bc_diagnostics import _run_grouped_subset_diagnostics, _run_world_seed_diagnostics, _run_frobenius_sensitivity

def _copy_evidence(root: Path, paths: dict[str, str | Path]) -> dict[str, str]:
    evidence = root / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)
    hashes: dict[str, str] = {}
    for name, source in paths.items():
        source_path = Path(source)
        target = evidence / name
        shutil.copy2(source_path, target)
        hashes[name] = sha256_file(target)
    return hashes

def _write_empty_csv(path: Path, columns: Iterable[str]) -> None:
    pd.DataFrame(columns=list(columns)).to_csv(path, index=False)

def run_stage_bc(
    fit_bundle: str | Path,
    fit_row_map: str | Path,
    fit_evaluation_metadata: str | Path,
    validation_bundle: str | Path,
    validation_row_map: str | Path,
    validation_evaluation_metadata: str | Path,
    output_root: str | Path,
    contract_path: str | Path = DEFAULT_CONTRACT,
    *,
    profile: str,
    smoke_rank_count: int = 2,
    smoke_max_iter: int = 500,
) -> Path:
    if profile not in {"smoke", "formal"}:
        raise ValueError("profile must be smoke or formal")
    contract = load_contract(contract_path)
    fit, fit_weights, fit_map = _load_bundle(fit_bundle, fit_row_map)
    validation, validation_weights, validation_map = _load_bundle(validation_bundle, validation_row_map)
    if set(fit_map["dataset_split"].astype(str)) != {"fit"}:
        raise ValueError("Stage B/C fit input contains a non-fit row")
    if set(validation_map["dataset_split"].astype(str)) != {"validation"}:
        raise ValueError("Stage B/C validation input contains a non-validation row")
    fit_metadata = _load_evaluation_metadata(fit_evaluation_metadata, fit_map, "fit")
    validation_metadata = _load_evaluation_metadata(validation_evaluation_metadata, validation_map, "validation")
    frozen_ranks = [int(value) for value in contract["rank_grid"]]
    if profile == "formal":
        ranks = frozen_ranks
        max_iter = int(contract["primary_model"]["max_iter"])
        root_name = "task3_1f3_stage_bc_formal"
    else:
        if smoke_rank_count < 2 or smoke_rank_count > len(frozen_ranks):
            raise ValueError("smoke_rank_count must exercise at least two frozen ranks")
        ranks = frozen_ranks[:smoke_rank_count]
        max_iter = int(smoke_max_iter)
        root_name = "task3_1f3_stage_bc_smoke"
    root = Path(output_root) / root_name
    shutil.rmtree(root, ignore_errors=True)
    (root / "models").mkdir(parents=True, exist_ok=False)
    evidence_hashes = _copy_evidence(
        root,
        {
            "fit_bundle.npz": fit_bundle,
            "fit_row_map.csv": fit_row_map,
            "fit_evaluation_metadata.csv": fit_evaluation_metadata,
            "validation_bundle.npz": validation_bundle,
            "validation_row_map.csv": validation_row_map,
            "validation_evaluation_metadata.csv": validation_evaluation_metadata,
        },
    )
    plans = run_plan(contract, ranks=ranks)
    _json_dump(root / "run_plan.json", plans)
    primary_rows = _execute_primary_runs(root, plans, fit, fit_weights, validation, contract, max_iter)
    reference_rows = _reference_runs(root, ranks, fit, fit_weights, validation)
    runs = pd.DataFrame(primary_rows + reference_rows)
    metrics = _all_reconstruction_metrics(root, runs, fit, fit_weights, fit_map, validation, validation_weights, validation_map)
    pair_metrics = _all_pair_metrics(root, runs, fit, fit_metadata, validation, validation_metadata)
    matches = _component_matches(root, runs)
    rank_summary, structure_summary, internal_similarity = rank_summaries(root, runs, metrics, matches, fit_weights, contract)
    selection = select_rank(rank_summary, runs, metrics)
    rank_summary["one_standard_error_eligible"] = False
    rank_summary["selected"] = False
    if selection["selection_status"] == "selected":
        threshold = float(selection["one_standard_error_threshold"])
        rank_summary.loc[(rank_summary["admissible"] == True) & (rank_summary["validation_weighted_mean_js"].astype(float) <= threshold), "one_standard_error_eligible"] = True
        rank_summary.loc[rank_summary["rank"] == int(selection["selected_rank"]), "selected"] = True

    runs.to_csv(root / "model_runs.csv", index=False)
    metrics.to_csv(root / "reconstruction_metrics.csv", index=False)
    pair_metrics.to_csv(root / "pair_deformation_metrics.csv", index=False)
    matches.to_csv(root / "component_matches.csv", index=False)

    grouped_overall: dict[str, Any] = {"passed": False, "status": "not_run_no_admissible_rank"}
    subset_matches = pd.DataFrame(); world_seed = pd.DataFrame(); world_seed_matches = pd.DataFrame()
    if selection["selection_status"] == "selected":
        subset_summary, subset_matches, grouped_overall = _run_grouped_subset_diagnostics(root, fit, fit_weights, fit_map, validation, selection, runs, contract, max_iter)
        subset_summary.to_csv(root / "grouped_subset_diagnostics.csv", index=False)
        subset_matches.to_csv(root / "grouped_subset_structure_matches.csv", index=False)
        world_seed, world_seed_matches = _run_world_seed_diagnostics(root, fit, fit_weights, fit_map, validation, selection, runs, contract, max_iter)
        world_seed.to_csv(root / "world_seed_diagnostics.csv", index=False)
        world_seed_matches.to_csv(root / "world_seed_structure_matches.csv", index=False)
        frobenius = _run_frobenius_sensitivity(root, fit, fit_weights, validation, selection, runs, contract, max_iter)
        frobenius.to_csv(root / "frobenius_sensitivity.csv", index=False)
        selected_mask = rank_summary["rank"] == int(selection["selected_rank"])
        rank_summary.loc[selected_mask, "grouped_subset_median_similarity"] = grouped_overall.get("median_similarity", 0.0)
        rank_summary.loc[selected_mask, "grouped_subset_surviving_component_fraction"] = grouped_overall.get("stable_component_fraction", 0.0)
        rank_summary.loc[selected_mask, "grouped_subset_passed"] = bool(grouped_overall.get("passed", False))
        for seed in contract["matching_and_stability"]["world_seed_sensitivity"]["fit_world_seeds"]:
            rows_for_seed = world_seed[world_seed["world_seed"] == int(seed)]
            value = float(rows_for_seed.iloc[0]["median_similarity"]) if len(rows_for_seed) == 1 else 0.0
            rank_summary.loc[selected_mask, f"world_seed_{int(seed)}_median_similarity"] = value
        if not structure_summary.empty:
            subset_counts = subset_matches[subset_matches["survived"] == True].groupby("representative_structure_id")["subset_id"].nunique().to_dict() if not subset_matches.empty else {}
            structure_summary["subset_survival_count"] = structure_summary["structure_id"].map(lambda structure_id: int(subset_counts.get(structure_id, 0)))
            for seed in contract["matching_and_stability"]["world_seed_sensitivity"]["fit_world_seeds"]:
                seed_matches = world_seed_matches[world_seed_matches["world_seed"] == int(seed)]
                similarity_map = seed_matches.set_index("representative_structure_id")["js_similarity"].to_dict() if not seed_matches.empty else {}
                structure_summary[f"world_seed_{int(seed)}_similarity"] = structure_summary["structure_id"].map(lambda structure_id: float(similarity_map.get(structure_id, 0.0)))
            conditional_threshold = float(contract["matching_and_stability"]["world_seed_sensitivity"]["median_similarity_conditional_threshold"])
            required_subset_count = int(contract["matching_and_stability"]["grouped_subset"]["required_subset_survival_count"])
            def handoff_status(row: pd.Series) -> str:
                if bool(row.get("duplicate_flag", False)): return "excluded_duplicate"
                if bool(row.get("inactive_flag", False)): return "excluded_inactive"
                if not bool(row.get("initial_stable", False)) or int(row.get("subset_survival_count", 0)) < required_subset_count: return "unstable"
                world_values = [float(row.get(f"world_seed_{int(seed)}_similarity", 0.0)) for seed in contract["matching_and_stability"]["world_seed_sensitivity"]["fit_world_seeds"]]
                if any(value < conditional_threshold for value in world_values): return "conditional_structure"
                return "stable_structure"
            structure_summary["handoff_status"] = structure_summary.apply(handoff_status, axis=1)
    else:
        _write_empty_csv(root / "grouped_subset_diagnostics.csv", ["subset_id", "included_row_count", "included_fraction", "included_row_indices_json", "included_group_keys_json", "excluded_group_keys_json", "group_preserving", "model_status", "failure_reason", "converged", "basis_path", "basis_sha256", "median_similarity", "surviving_component_fraction"])
        _write_empty_csv(root / "grouped_subset_structure_matches.csv", ["subset_id", "rank"])
        _write_empty_csv(root / "world_seed_diagnostics.csv", ["world_seed", "selected_rank", "selected_rank_unchanged", "model_status", "median_similarity"])
        _write_empty_csv(root / "world_seed_structure_matches.csv", ["world_seed", "rank"])
        _write_empty_csv(root / "frobenius_sensitivity.csv", ["rank", "seed", "model_status", "influenced_primary_selection"])

    rank_summary.to_csv(root / "rank_summary.csv", index=False)
    rank_summary.to_csv(root / "rank_stability_summary.csv", index=False)
    structure_summary.to_csv(root / "structure_summary.csv", index=False)
    internal_similarity.to_csv(root / "internal_structure_similarity.csv", index=False)

    selected_paths: list[dict[str, str]] = []
    if selection["selection_status"] == "selected":
        selected_run = runs[runs["run_id"] == selection["selected_representative_run"]].iloc[0]
        for key in ("basis_path", "fit_activation_path", "validation_activation_path"):
            selected_paths.append({"kind": key, "path": str(selected_run[key]), "sha256": sha256_file(root / str(selected_run[key]))})
    candidate = {
        **selection,
        "lock_version": "task3.1f-selection-v1",
        "profile": profile,
        "formal_scientific_result": profile == "formal",
        "executed_ranks": ranks,
        "primary_run_count": len(plans),
        "rank_summary_sha256": sha256_file(root / "rank_summary.csv"),
        "selected_model_paths_and_hashes": selected_paths,
        "contract_sha256": sha256_text(canonical_contract_text(contract_path)),
        "fit_bundle_sha256": evidence_hashes["fit_bundle.npz"],
        "validation_bundle_sha256": evidence_hashes["validation_bundle.npz"],
        "fit_evaluation_metadata_sha256": evidence_hashes["fit_evaluation_metadata.csv"],
        "validation_evaluation_metadata_sha256": evidence_hashes["validation_evaluation_metadata.csv"],
        "grouped_subset_overall": grouped_overall,
        "holdout_accessed": False,
        "producer_created_selection_lock": False,
    }
    _json_dump(root / "selection_candidate.json", candidate)
    _json_dump(root / "contract_snapshot.json", contract)
    _json_dump(root / "execution_manifest.json", {"profile": profile, "executed_ranks": ranks, "max_iter": max_iter, "formal_contract_max_iter": int(contract["primary_model"]["max_iter"]), "holdout_accessed": False, "selection_lock_created_by_producer": False, "evidence_hashes": evidence_hashes})
    _json_dump(root / "quality_checks.json", {"status": "pending_independent_selection_validator", "producer_self_certification": False, "holdout_accessed": False})
    _json_dump(root / "mutation_test_results.json", {"status": "pending_independent_selection_validator", "mutations": []})
    (root / "results.md").write_text("# Task 3.1f-3 Stage B/C Results\n\n" f"- Profile: `{profile}`\n" f"- Formal scientific result: `{'true' if profile == 'formal' else 'false'}`\n" "- Holdout accessed: `false`\n" f"- Ranks executed: `{ranks}`\n" f"- Selection status: `{selection['selection_status']}`\n" "- Independent audit: `pending`\n", encoding="utf-8")
    return root

def run_stage_bc_smoke(fit_bundle: str | Path, fit_row_map: str | Path, validation_bundle: str | Path, validation_row_map: str | Path, output_root: str | Path, contract_path: str | Path = DEFAULT_CONTRACT, *, smoke_ranks: int = 2, fit_evaluation_metadata: str | Path | None = None, validation_evaluation_metadata: str | Path | None = None) -> Path:
    fit_evaluation_metadata = fit_evaluation_metadata or Path(fit_row_map).with_name("fit_evaluation_metadata.csv")
    validation_evaluation_metadata = validation_evaluation_metadata or Path(validation_row_map).with_name("validation_evaluation_metadata.csv")
    return run_stage_bc(fit_bundle, fit_row_map, fit_evaluation_metadata, validation_bundle, validation_row_map, validation_evaluation_metadata, output_root, contract_path, profile="smoke", smoke_rank_count=smoke_ranks)

def run_stage_bc_formal(fit_bundle: str | Path, fit_row_map: str | Path, fit_evaluation_metadata: str | Path, validation_bundle: str | Path, validation_row_map: str | Path, validation_evaluation_metadata: str | Path, output_root: str | Path, contract_path: str | Path = DEFAULT_CONTRACT) -> Path:
    return run_stage_bc(fit_bundle, fit_row_map, fit_evaluation_metadata, validation_bundle, validation_row_map, validation_evaluation_metadata, output_root, contract_path, profile="formal")
