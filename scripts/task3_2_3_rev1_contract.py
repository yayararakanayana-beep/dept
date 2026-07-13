"""Validate the Task 3.2-3 Rev1 Phase 1 research contract.

This module validates boundaries and future corpus manifests only. It does not
generate trajectories, implement predictors, select candidates, or read
validation/holdout state data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "configs" / "task3_2_3_rev1_contract.json"


class ContractError(ValueError):
    """Raised when the Rev1 contract or a proposed corpus violates a boundary."""


MANDATORY_FORBIDDEN_INPUTS = {
    "scenario_id",
    "seed",
    "dataset_split",
    "absolute_step_or_time_index",
    "generator_event_or_regime_name",
    "future_external_inputs",
    "future_states",
    "future_events",
    "truth_labels",
    "final_outcomes",
    "same_seed_reference_features",
    "task4_macro_features",
    "task4_1_counterfactual_truth",
    "formal_gt_features",
    "relation_field_features",
    "game_structure_labels",
    "irreversibility_labels",
}

MANDATORY_PHASE_PROHIBITIONS = {
    "new_corpus_generation",
    "model_implementation",
    "model_training",
    "model_selection",
    "validation_data_read",
    "holdout_data_read",
    "task4_feature_import",
    "task4_1_truth_use_for_model_selection",
    "formal_gt_or_relation_field_use",
    "action_module_connection",
}


def _load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _require_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractError(f"{name} must be an object")
    return value


def _require_nonempty_list(value: Any, name: str) -> list[Any]:
    if not isinstance(value, list) or not value:
        raise ContractError(f"{name} must be a non-empty list")
    return value


def _finite_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError(f"{name} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ContractError(f"{name} must be finite")
    return number


def validate_contract(config: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "task_identity",
        "source_of_truth",
        "role_contract",
        "phase_boundaries",
        "input_contract",
        "target_contract",
        "corpus_contract",
        "evaluation_contract",
        "reproducibility_contract",
        "stop_conditions",
    }
    missing = sorted(required - set(config))
    if missing:
        raise ContractError(f"contract missing top-level sections: {missing}")

    identity = _require_mapping(config["task_identity"], "task_identity")
    if identity.get("status") != "contract_only_frozen_before_corpus_generation":
        raise ContractError("Phase 1 status must remain contract-only")

    phase = _require_mapping(config["phase_boundaries"], "phase_boundaries")
    allowed = set(_require_nonempty_list(phase.get("allowed_work"), "allowed_work"))
    prohibited = set(_require_nonempty_list(phase.get("prohibited_work"), "prohibited_work"))
    if allowed & prohibited:
        raise ContractError("allowed_work and prohibited_work overlap")
    missing_prohibitions = sorted(MANDATORY_PHASE_PROHIBITIONS - prohibited)
    if missing_prohibitions:
        raise ContractError(f"Phase 1 missing prohibitions: {missing_prohibitions}")

    role = _require_mapping(config["role_contract"], "role_contract")
    if role.get("fixed_role") != "local_history_early_warning":
        raise ContractError("Task 3 Rev1 must remain local/history early warning")
    prohibited_roles = set(_require_nonempty_list(role.get("prohibited_roles"), "prohibited_roles"))
    for required_role in (
        "macro_dynamics_extraction",
        "counterfactual_truth_generation",
        "game_structure_classification",
        "irreversibility_proof",
        "action_selection",
    ):
        if required_role not in prohibited_roles:
            raise ContractError(f"prohibited role missing: {required_role}")

    inputs = _require_mapping(config["input_contract"], "input_contract")
    if inputs.get("time_boundary") != "observed_through_t_only":
        raise ContractError("input time boundary must stop at t")
    forbidden = set(_require_nonempty_list(inputs.get("forbidden_model_inputs"), "forbidden_model_inputs"))
    missing_forbidden = sorted(MANDATORY_FORBIDDEN_INPUTS - forbidden)
    if missing_forbidden:
        raise ContractError(f"mandatory forbidden inputs missing: {missing_forbidden}")
    _validate_information_ladder(inputs)

    targets = _require_mapping(config["target_contract"], "target_contract")
    if targets.get("task4_1_truth_use") != "blind_post_selection_audit_only_not_phase1_or_model_selection":
        raise ContractError("Task 4.1 truth must remain blind and post-selection only")
    target_rows = _require_nonempty_list(targets.get("targets"), "targets")
    target_ids = {str(_require_mapping(row, "target").get("id")) for row in target_rows}
    required_targets = {
        "hazard_onset_within_horizon",
        "time_to_hazard_onset",
        "maximum_relative_risk_depth",
        "risk_direction",
        "persistence_or_recovery_difficulty_candidate",
        "predictive_uncertainty",
    }
    if not required_targets <= target_ids:
        raise ContractError(f"targets missing: {sorted(required_targets - target_ids)}")

    corpus = _require_mapping(config["corpus_contract"], "corpus_contract")
    if corpus.get("split_unit") != "trajectory":
        raise ContractError("corpus split unit must be trajectory")
    if corpus.get("seed_only_split_is_valid_ood") is not False:
        raise ContractError("seed-only split must not count as OOD")
    if corpus.get("require_each_ood_axis_disjoint_across_splits") is not True:
        raise ContractError("every OOD axis must be disjoint across splits")
    for key in (
        "out_of_distribution_axes",
        "required_schedule_variations",
        "required_background_variations",
        "required_hard_negative_families",
        "required_hard_positive_families",
        "required_outcome_families",
    ):
        _require_nonempty_list(corpus.get(key), key)
    sample = _require_mapping(corpus.get("sample_size_policy"), "sample_size_policy")
    if sample.get("windows_do_not_count_as_independent_samples") is not True:
        raise ContractError("windows must not count as independent samples")
    if sample.get("formal_count_frozen_in_phase1") is not False:
        raise ContractError("formal sample count must wait for the pre-model pilot audit")

    evaluation = _require_mapping(config["evaluation_contract"], "evaluation_contract")
    if evaluation.get("compare_information_levels_on_identical_eligible_windows") is not True:
        raise ContractError("information levels require identical eligible windows")
    if evaluation.get("evaluate_each_horizon_separately") is not True:
        raise ContractError("prediction horizons must be evaluated separately")
    if evaluation.get("weighted_cross_horizon_scalar_score_allowed") is not False:
        raise ContractError("weighted cross-horizon scalar selection is forbidden")
    if evaluation.get("selection_strategy") != "pareto_then_preregistered_lexicographic":
        raise ContractError("selection must use the frozen Pareto/lexicographic strategy")
    horizons = _require_nonempty_list(evaluation.get("prediction_horizons"), "prediction_horizons")
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 1 for value in horizons):
        raise ContractError("prediction horizons must be positive integers")
    thresholds = _require_mapping(evaluation.get("history_success_thresholds"), "history_success_thresholds")
    for name, value in thresholds.items():
        number = _finite_number(value, name)
        if "fraction" in name or "confidence" in name:
            if not 0.0 < number <= 1.0:
                raise ContractError(f"{name} must be inside (0, 1]")
        elif number < 0.0:
            raise ContractError(f"{name} must be non-negative")

    reproducibility = _require_mapping(config["reproducibility_contract"], "reproducibility_contract")
    required_identity = set(
        _require_nonempty_list(
            reproducibility.get("stable_selection_identity_required_fields"),
            "stable_selection_identity_required_fields",
        )
    )
    forbidden_identity = set(
        _require_nonempty_list(
            reproducibility.get("stable_selection_identity_forbidden_fields"),
            "stable_selection_identity_forbidden_fields",
        )
    )
    if required_identity & forbidden_identity:
        raise ContractError("stable selection required and forbidden fields overlap")
    if "validation_metrics" not in forbidden_identity or "holdout_metrics" not in forbidden_identity:
        raise ContractError("metrics must not enter the stable selection identity")
    for flag in (
        "metrics_artifact_hash_separate_from_selection_identity",
        "two_identical_pre_holdout_reruns_must_match_selection_identity",
        "holdout_requires_independently_validated_selection_identity",
        "main_documentation_generated_from_final_artifact",
    ):
        if reproducibility.get(flag) is not True:
            raise ContractError(f"reproducibility requirement disabled: {flag}")

    _require_nonempty_list(config["stop_conditions"], "stop_conditions")
    return {
        "status": "valid",
        "contract_hash": canonical_hash(config),
        "information_level_count": len(inputs["information_levels"]),
        "history_comparison_count": len(inputs["history_comparisons"]),
        "required_outcome_family_count": len(corpus["required_outcome_families"]),
    }


def _validate_information_ladder(inputs: Mapping[str, Any]) -> None:
    feature_groups = _require_mapping(inputs.get("feature_groups"), "feature_groups")
    rows = _require_nonempty_list(inputs.get("information_levels"), "information_levels")
    levels: dict[str, set[str]] = {}
    for value in rows:
        row = _require_mapping(value, "information level")
        level_id = str(row.get("id"))
        if not level_id or level_id in levels:
            raise ContractError("information level IDs must be unique and non-empty")
        groups = set(_require_nonempty_list(row.get("feature_groups"), f"{level_id}.feature_groups"))
        unknown = sorted(groups - set(feature_groups))
        if unknown:
            raise ContractError(f"{level_id} uses unknown feature groups: {unknown}")
        parent_ids = list(row.get("parents", []))
        for parent in parent_ids:
            if parent not in levels:
                raise ContractError(f"{level_id} parent {parent} must appear earlier")
            if not levels[parent] < groups:
                raise ContractError(f"{level_id} must strictly extend parent {parent}")
        levels[level_id] = groups

    comparisons = _require_nonempty_list(inputs.get("history_comparisons"), "history_comparisons")
    for value in comparisons:
        comparison = _require_mapping(value, "history comparison")
        baseline = str(comparison.get("baseline"))
        history = str(comparison.get("history"))
        if baseline not in levels or history not in levels:
            raise ContractError("history comparison references an unknown level")
        added = set(_require_nonempty_list(comparison.get("added_feature_groups"), "added_feature_groups"))
        actual_added = levels[history] - levels[baseline]
        if levels[baseline] - levels[history] or actual_added != added:
            raise ContractError(
                f"history comparison {comparison.get('id')} changes groups other than {sorted(added)}"
            )


def build_stable_selection_identity(
    payload: Mapping[str, Any], config: Mapping[str, Any]
) -> dict[str, Any]:
    validate_contract(config)
    reproduction = config["reproducibility_contract"]
    required = set(reproduction["stable_selection_identity_required_fields"])
    forbidden = set(reproduction["stable_selection_identity_forbidden_fields"])
    supplied = set(payload)
    missing = sorted(required - supplied)
    forbidden_supplied = sorted(forbidden & supplied)
    extra = sorted(supplied - required)
    if missing:
        raise ContractError(f"stable selection identity missing fields: {missing}")
    if forbidden_supplied:
        raise ContractError(f"stable selection identity contains forbidden fields: {forbidden_supplied}")
    if extra:
        raise ContractError(f"stable selection identity contains undeclared fields: {extra}")
    return {key: payload[key] for key in sorted(required)}


def stable_selection_hash(payload: Mapping[str, Any], config: Mapping[str, Any]) -> str:
    return canonical_hash(build_stable_selection_identity(payload, config))


def validate_split_manifest(
    manifest: Mapping[str, Any], config: Mapping[str, Any], *, mode: str = "pilot"
) -> dict[str, Any]:
    validate_contract(config)
    if mode != "pilot":
        raise ContractError("Phase 1 validates pilot manifests only; formal counts are not frozen")
    rows = _require_nonempty_list(manifest.get("trajectories"), "manifest.trajectories")
    corpus = config["corpus_contract"]
    ood_axes = list(corpus["out_of_distribution_axes"])
    required_outcomes = set(corpus["required_outcome_families"])
    minimums = corpus["sample_size_policy"]["pilot_minimum_per_outcome"]
    split_names = ("fit", "validation", "holdout")
    seen_ids: set[str] = set()
    axis_splits: dict[str, dict[str, str]] = {axis: {} for axis in ood_axes}
    outcome_counts = {split: {outcome: 0 for outcome in required_outcomes} for split in split_names}
    for value in rows:
        row = _require_mapping(value, "trajectory row")
        trajectory_id = str(row.get("trajectory_id", ""))
        split = str(row.get("split", ""))
        outcome = str(row.get("outcome_family", ""))
        if not trajectory_id or trajectory_id in seen_ids:
            raise ContractError("trajectory IDs must be unique and non-empty")
        seen_ids.add(trajectory_id)
        if split not in split_names:
            raise ContractError(f"unsupported split: {split}")
        if outcome not in required_outcomes:
            raise ContractError(f"unsupported outcome family: {outcome}")
        outcome_counts[split][outcome] += 1
        for axis in ood_axes:
            axis_value = str(row.get(axis, ""))
            if not axis_value:
                raise ContractError(f"trajectory {trajectory_id} missing {axis}")
            previous = axis_splits[axis].setdefault(axis_value, split)
            if previous != split:
                raise ContractError(f"OOD axis overlap: {axis}={axis_value} appears in {previous} and {split}")
    for split in split_names:
        minimum = int(minimums[split])
        missing = sorted(
            outcome for outcome, count in outcome_counts[split].items() if count < minimum
        )
        if missing:
            raise ContractError(f"{split} lacks pilot outcome coverage: {missing}")
    return {
        "status": "valid",
        "mode": mode,
        "trajectory_count": len(rows),
        "split_counts": {
            split: sum(outcome_counts[split].values()) for split in split_names
        },
        "manifest_content_hash": canonical_hash(manifest),
    }


def load_contract(path: str | Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = _load_json(path)
    validate_contract(config)
    return config


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--manifest")
    args = parser.parse_args(argv)
    config = load_contract(args.config)
    result = (
        validate_split_manifest(_load_json(args.manifest), config)
        if args.manifest
        else validate_contract(config)
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ContractError",
    "build_stable_selection_identity",
    "canonical_hash",
    "load_contract",
    "stable_selection_hash",
    "validate_contract",
    "validate_split_manifest",
]
