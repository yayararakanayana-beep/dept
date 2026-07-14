from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_PATH = ROOT / "configs" / "fixed5axis_hdept_task4_2_whole_system_validation_preregistration_rc1.json"


def _protocol() -> dict[str, object]:
    return json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))


def _flatten_strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(_flatten_strings(item))
        return result
    if isinstance(value, dict):
        result = []
        for key, item in value.items():
            result.append(str(key))
            result.extend(_flatten_strings(item))
        return result
    return []


def test_task4_2_is_design_only_and_does_not_authorize_task5() -> None:
    protocol = _protocol()
    assert protocol["status"] == "preregistered_design_only_not_executed"
    authorization = protocol["authorization"]
    assert authorization["task4_3_execution_authorized_after_task4_2_freeze"] is True
    assert authorization["task5_authorized"] is False
    assert authorization["old_task4_eight_hypothesis_result_may_be_used"] is False
    assert protocol["decision_logic_after_execution"]["maximum_claim"] == (
        "B_limited_synthetic_fixed5_whole_system_observation_only"
    )
    assert protocol["decision_logic_after_execution"]["real_world_or_closed_loop_claim"] is False


def test_split_namespaces_and_reserved_seed_ranges_are_disjoint() -> None:
    splits = _protocol()["split_design"]
    ranges: list[set[int]] = []
    namespaces: list[str] = []
    for split in ("design_calibration", "validation", "final_confirmation"):
        definition = splits[split]
        namespaces.append(definition["seed_namespace"])
        start = int(definition["seed_start"])
        count = int(definition["seed_reservation_count"])
        assert count == 64
        ranges.append(set(range(start, start + count)))
    assert len(namespaces) == len(set(namespaces))
    assert ranges[0].isdisjoint(ranges[1])
    assert ranges[0].isdisjoint(ranges[2])
    assert ranges[1].isdisjoint(ranges[2])
    assert splits["validation"]["generated_only_after_sample_size_lock"] is True
    assert splits["final_confirmation"]["generated_only_after_validation_artifact_freeze"] is True


def test_sample_size_and_uncertainty_rules_are_frozen_before_evaluation() -> None:
    protocol = _protocol()
    lock = protocol["sample_size_lock"]
    assert lock["method"] == "calibration_only_power_planning"
    assert float(lock["familywise_alpha"]) == 0.01
    assert float(lock["target_power"]) == 0.90
    assert int(lock["minimum_seeds_per_transformation_family"]) >= 12
    assert int(lock["maximum_seeds_per_transformation_family"]) == 64
    assert lock["lock_artifact_required_before_validation_generation"] is True

    uncertainty = protocol["multiple_testing_and_uncertainty"]
    assert float(uncertainty["confidence_level"]) == 0.99
    assert uncertainty["resampling_unit"] == "seed-level matched group"
    assert uncertainty["case_level_pseudoreplication_forbidden"] is True
    assert "Holm" in uncertainty["familywise_control"]


def test_controlled_case_names_are_not_truth_labels_or_axis_direction_targets() -> None:
    protocol = _protocol()
    assert all(case["truth_label"] is False for case in protocol["controlled_distribution_families"])
    perturbations = protocol["local_to_global_matched_perturbations"]
    fractions = [float(value) for value in perturbations["mass_fractions"]]
    assert fractions == sorted(fractions)
    assert len(fractions) == len(set(fractions))
    assert 0.0 < fractions[0] < fractions[-1] < 1.0
    assert "complete available H11 profile" in perturbations["primary_expectation"]
    assert "every individual H11 axis" in perturbations["forbidden_expectation"]

    flattened = "\n".join(_flatten_strings(protocol))
    for old_gate in (
        "H1_false_stability_guard",
        "H2_structured_exploration",
        "H3_noise_guard",
        "H4_oscillation_detection",
        "H5_boundary_divergence",
        "H6_slow_fixation",
        "H7_recovery_contract_limit",
        "H8_non_neutral_collapse",
        "freeze_reproducibility_only_not_scientifically_approved",
    ):
        assert old_gate not in flattened


def test_information_target_is_bounded_to_task1_scored_feature_vocabulary() -> None:
    reference = _protocol()["independent_reference_vector"]
    excluded = reference["excluded_information"]
    assert "absolute centroid coordinates" in excluded
    assert any("mode_count" in item for item in excluded)
    assert any("cluster_balance" in item for item in excluded)
    assert "location" not in reference["groups"]
    assert set(reference["groups"]) == {
        "axis_participation_and_dependency",
        "effective_dimensionality",
        "spread_shape_and_density",
        "whole_system_motion_and_trajectory",
    }
    all_features = [
        feature
        for group in reference["groups"].values()
        for feature in group
    ]
    assert len(all_features) == len(set(all_features))
    assert "mode_count" not in all_features
    assert "cluster_balance" not in all_features
    assert "prediction_error" not in all_features
    assert "recovery_half_life" not in all_features


def test_all_critical_domains_and_random_baseline_are_explicit() -> None:
    protocol = _protocol()
    domains = protocol["evaluation_domains"]
    assert set(domains) == {
        "E1_engineering_and_causal_integrity",
        "E2_whole_system_information_preservation",
        "E3_local_to_global_scale_response",
        "E4_continuity_and_threshold_audit",
        "E5_calibration_health",
        "E6_axis_role_separation_and_compression",
        "E7_missing_evidence_and_claim_limits",
        "E8_auxiliary_basis_scope",
    }
    for domain in (
        "E1_engineering_and_causal_integrity",
        "E2_whole_system_information_preservation",
        "E3_local_to_global_scale_response",
        "E4_continuity_and_threshold_audit",
        "E5_calibration_health",
        "E6_axis_role_separation_and_compression",
        "E7_missing_evidence_and_claim_limits",
    ):
        assert domains[domain]["critical"] is True
    assert domains["E8_auxiliary_basis_scope"]["critical"] is False
    assert "fixed Random8 ensemble" in domains["E2_whole_system_information_preservation"]["mandatory_baselines"]
    assert domains["E8_auxiliary_basis_scope"]["mandatory_for_task4_3"] == ["fixed Random8 ensemble"]
    assert "PCA8" in domains["E8_auxiliary_basis_scope"]["optional_diagnostic_bases"]


def test_missing_evidence_and_continuity_fail_closed() -> None:
    domains = _protocol()["evaluation_domains"]
    evidence_requirements = domains["E7_missing_evidence_and_claim_limits"]["requirements"]
    assert any("Predictability" in item and "UNAVAILABLE" in item for item in evidence_requirements)
    assert any("Recoverability" in item and "UNAVAILABLE" in item for item in evidence_requirements)
    assert any("mode_count" in item and "non-scoring" in item for item in evidence_requirements)
    assert any("cluster_balance" in item and "non-scoring" in item for item in evidence_requirements)

    continuity_failures = domains["E4_continuity_and_threshold_audit"]["automatic_failures"]
    assert "non-finite H11 output" in continuity_failures
    assert "unlogged jump" in continuity_failures
    assert "neutral placeholder used as evidence" in continuity_failures
