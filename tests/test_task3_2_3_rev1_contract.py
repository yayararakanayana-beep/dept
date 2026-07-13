from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import task3_2_3_rev1_contract as module  # noqa: E402


def _contract() -> dict:
    return json.loads(
        (ROOT / "configs" / "task3_2_3_rev1_contract.json").read_text(encoding="utf-8")
    )


def _selection_payload(config: dict) -> dict:
    return {
        "contract_hash": module.canonical_hash(config),
        "corpus_content_hash": "corpus-sha256",
        "feature_schema_hash": "feature-sha256",
        "information_level": "I3",
        "candidate_id": "candidate-a",
        "model_family": "regularized_logistic",
        "history_specification": {"widths": [2, 4, 8]},
        "prediction_horizon": 4,
        "alarm_threshold": 0.2,
        "alarm_persistence": 1,
        "fit_seed_configuration": [0, 1, 2],
    }


def _pilot_manifest(config: dict) -> dict:
    minimums = config["corpus_contract"]["sample_size_policy"][
        "pilot_minimum_per_outcome"
    ]
    outcomes = config["corpus_contract"]["required_outcome_families"]
    rows = []
    counter = 0
    for split in ("fit", "validation", "holdout"):
        for outcome in outcomes:
            for repetition in range(minimums[split]):
                counter += 1
                rows.append(
                    {
                        "trajectory_id": f"trajectory-{counter}",
                        "split": split,
                        "seed": repetition,
                        "schedule_template_id": f"{split}-schedule-{outcome}-{repetition}",
                        "background_regime_id": f"{split}-background-{outcome}-{repetition}",
                        "world_parameter_profile_id": f"{split}-world-{outcome}-{repetition}",
                        "outcome_family": outcome,
                    }
                )
    return {"trajectories": rows}


def test_contract_and_pilot_manifest_validate() -> None:
    config = module.load_contract()
    result = module.validate_contract(config)
    assert result["status"] == "valid"
    assert result["information_level_count"] == 5
    manifest_result = module.validate_split_manifest(_pilot_manifest(config), config)
    assert manifest_result["status"] == "valid"
    assert manifest_result["trajectory_count"] > 0


def test_contract_hash_and_selection_hash_ignore_mapping_order_only() -> None:
    config = module.load_contract()
    reversed_config = dict(reversed(list(config.items())))
    assert module.canonical_hash(config) == module.canonical_hash(reversed_config)
    payload = _selection_payload(config)
    reversed_payload = dict(reversed(list(payload.items())))
    assert module.stable_selection_hash(payload, config) == module.stable_selection_hash(
        reversed_payload, config
    )


def test_future_information_cannot_be_reintroduced() -> None:
    config = _contract()
    config["input_contract"]["forbidden_model_inputs"].remove("future_external_inputs")
    with pytest.raises(module.ContractError, match="mandatory forbidden inputs"):
        module.validate_contract(config)


def test_task4_1_truth_cannot_be_used_for_selection() -> None:
    config = _contract()
    config["target_contract"]["task4_1_truth_use"] = "model_selection"
    with pytest.raises(module.ContractError, match="Task 4.1 truth"):
        module.validate_contract(config)


def test_history_comparison_must_change_only_declared_information() -> None:
    config = _contract()
    config["input_contract"]["history_comparisons"][0]["added_feature_groups"] = [
        "internal_history",
        "observed_external_history",
    ]
    with pytest.raises(module.ContractError, match="changes groups other than"):
        module.validate_contract(config)


def test_cross_horizon_weighted_scalar_selection_is_rejected() -> None:
    config = _contract()
    config["evaluation_contract"]["weighted_cross_horizon_scalar_score_allowed"] = True
    with pytest.raises(module.ContractError, match="cross-horizon"):
        module.validate_contract(config)


def test_stable_selection_identity_rejects_metrics_and_runtime_ids() -> None:
    config = module.load_contract()
    payload = _selection_payload(config)
    payload["validation_metrics"] = {"event_recall": 1.0}
    with pytest.raises(module.ContractError, match="forbidden fields"):
        module.build_stable_selection_identity(payload, config)

    payload = _selection_payload(config)
    payload["workflow_run_id"] = 123
    with pytest.raises(module.ContractError, match="forbidden fields"):
        module.build_stable_selection_identity(payload, config)


def test_stable_selection_identity_rejects_unregistered_defaults() -> None:
    config = module.load_contract()
    payload = _selection_payload(config)
    payload["plausible_default"] = True
    with pytest.raises(module.ContractError, match="undeclared fields"):
        module.build_stable_selection_identity(payload, config)


def test_seed_only_or_reused_schedule_is_not_ood() -> None:
    config = module.load_contract()
    manifest = _pilot_manifest(config)
    fit_row = next(row for row in manifest["trajectories"] if row["split"] == "fit")
    validation_row = next(
        row for row in manifest["trajectories"] if row["split"] == "validation"
    )
    validation_row["schedule_template_id"] = fit_row["schedule_template_id"]
    with pytest.raises(module.ContractError, match="OOD axis overlap"):
        module.validate_split_manifest(manifest, config)


def test_missing_recovery_or_other_required_outcome_is_rejected() -> None:
    config = module.load_contract()
    manifest = _pilot_manifest(config)
    manifest["trajectories"] = [
        row
        for row in manifest["trajectories"]
        if not (row["split"] == "holdout" and row["outcome_family"] == "full_recovery")
    ]
    with pytest.raises(module.ContractError, match="holdout lacks pilot outcome coverage"):
        module.validate_split_manifest(manifest, config)


def test_formal_manifest_cannot_be_self_certified_in_phase1() -> None:
    config = module.load_contract()
    with pytest.raises(module.ContractError, match="pilot manifests only"):
        module.validate_split_manifest(_pilot_manifest(config), config, mode="formal")
