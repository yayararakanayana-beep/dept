from __future__ import annotations

import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from task3_1f3_fixture import build_stage_bc_smoke_bundles
from task3_1f4_fixture import build_holdout_smoke_bundle
from task3_1f_structure_extraction import (
    evaluate_holdout,
    run_stage_bc_smoke,
    validate_final,
    validate_selection,
)
from task3_1f_structure_extraction.contract import DEFAULT_CONTRACT


@pytest.fixture(scope="session")
def task3_1f4_pipeline(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    root = tmp_path_factory.mktemp("task3_1f4")
    bundles = build_stage_bc_smoke_bundles(root / "fit_validation")
    holdout = build_holdout_smoke_bundle(root / "holdout")
    selection = run_stage_bc_smoke(
        bundles["fit_bundle"],
        bundles["fit_row_map"],
        bundles["validation_bundle"],
        bundles["validation_row_map"],
        root / "selection_run",
        DEFAULT_CONTRACT,
        smoke_ranks=2,
        fit_evaluation_metadata=bundles["fit_evaluation_metadata"],
        validation_evaluation_metadata=bundles["validation_evaluation_metadata"],
    )
    selection_checks = validate_selection(
        selection, DEFAULT_CONTRACT, strict=True, write_outputs=True
    )
    assert all(check["passed"] for check in selection_checks.values())
    artifact = evaluate_holdout(
        selection_artifact_dir=selection,
        holdout_bundle=holdout["holdout_bundle"],
        holdout_row_map=holdout["holdout_row_map"],
        holdout_evaluation_metadata=holdout["holdout_evaluation_metadata"],
        output_root=root / "holdout_run",
        contract_path=DEFAULT_CONTRACT,
    )
    assert not (artifact / "holdout_outcome.json").exists()
    checks = validate_final(
        artifact, DEFAULT_CONTRACT, strict=True, write_outputs=True
    )
    assert all(check["passed"] for check in checks.values()), checks
    return {
        "root": root,
        "selection": selection,
        "artifact": artifact,
        **bundles,
        **holdout,
    }


def test_final_validator_creates_official_outcome(
    task3_1f4_pipeline: dict[str, Path],
) -> None:
    artifact = task3_1f4_pipeline["artifact"]
    outcome = json.loads((artifact / "holdout_outcome.json").read_text(encoding="utf-8"))
    audit = json.loads((artifact / "final_audit.json").read_text(encoding="utf-8"))
    assert outcome["integrity_audit_result"] == "passed"
    assert outcome["selected_rank"] == 5
    assert outcome["outcome"] in {"confirmed", "conditional", "failed"}
    assert audit["independent_final_audit"] == "passed"
    assert (artifact / "selected_model/holdout_activations.npy").is_file()
    assert (artifact / "holdout_pair_deformation_metrics.csv").is_file()


def test_holdout_evaluator_rejects_missing_selection_lock(
    task3_1f4_pipeline: dict[str, Path],
    tmp_path: Path,
) -> None:
    selection = tmp_path / "selection_without_lock"
    shutil.copytree(task3_1f4_pipeline["selection"], selection)
    (selection / "selection_lock.json").unlink()
    with pytest.raises(ValueError, match="selection artifact is incomplete"):
        evaluate_holdout(
            selection_artifact_dir=selection,
            holdout_bundle=task3_1f4_pipeline["holdout_bundle"],
            holdout_row_map=task3_1f4_pipeline["holdout_row_map"],
            holdout_evaluation_metadata=task3_1f4_pipeline[
                "holdout_evaluation_metadata"
            ],
            output_root=tmp_path / "rejected",
            contract_path=DEFAULT_CONTRACT,
        )


@pytest.mark.parametrize(
    "mutation,failed_check",
    [
        ("lock_rank", "selection_lock_valid"),
        ("activation", "holdout_activation_recomputed"),
        ("metrics", "holdout_metrics_recomputed"),
        ("outcome", "holdout_outcome_recomputed"),
        ("row_map", "holdout_evidence_valid"),
    ],
)
def test_final_validator_rejects_mutations(
    task3_1f4_pipeline: dict[str, Path],
    tmp_path: Path,
    mutation: str,
    failed_check: str,
) -> None:
    source = task3_1f4_pipeline["artifact"]
    target = tmp_path / mutation
    shutil.copytree(source, target)
    if mutation == "lock_rank":
        path = target / "selection_artifact/selection_lock.json"
        lock = json.loads(path.read_text(encoding="utf-8"))
        lock["selected_rank"] = 8
        path.write_text(json.dumps(lock, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    elif mutation == "activation":
        path = target / "selected_model/holdout_activations.npy"
        activation = np.load(path, allow_pickle=False)
        activation[0, 0] += 0.1
        np.save(path, activation)
    elif mutation == "metrics":
        path = target / "holdout_metrics.csv"
        frame = pd.read_csv(path)
        frame.loc[0, "value"] = float(frame.loc[0, "value"]) + 0.1
        frame.to_csv(path, index=False)
    elif mutation == "outcome":
        path = target / "holdout_outcome_candidate.json"
        outcome = json.loads(path.read_text(encoding="utf-8"))
        outcome["outcome"] = (
            "failed" if outcome["outcome"] != "failed" else "confirmed"
        )
        path.write_text(
            json.dumps(outcome, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    elif mutation == "row_map":
        path = target / "evidence/holdout_row_map.csv"
        frame = pd.read_csv(path)
        first = frame.loc[0, "snapshot_id"]
        frame.loc[0, "snapshot_id"] = frame.loc[1, "snapshot_id"]
        frame.loc[1, "snapshot_id"] = first
        frame.to_csv(path, index=False)
    checks = validate_final(
        target, DEFAULT_CONTRACT, strict=False, write_outputs=False
    )
    assert checks[failed_check]["passed"] is False
