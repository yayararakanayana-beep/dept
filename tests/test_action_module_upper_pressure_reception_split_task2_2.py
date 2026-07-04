from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_calibration_rc1 import (
    TASK2_2_CALIBRATION_VERSION,
    STATE_BANDS,
    build_and_validate_calibrated_pressure_action_map,
    build_single_action_probe_response_map,
    calibrate_pressure_action_map,
    validate_calibrated_pressure_action_map,
)


def test_task2_2_single_action_probe_response_map_is_validation_only():
    response_map = build_single_action_probe_response_map()

    assert not response_map.empty
    assert set(response_map["state_band"]) == set(STATE_BANDS)
    assert "no_op" in set(response_map["action_channel"])
    assert set(response_map["validation_only"]) == {True}
    assert set(response_map["runtime_policy_input"]) == {False}
    assert response_map[response_map["action_channel"] != "no_op"][
        [
            "delta_vs_no_op_exploration",
            "delta_vs_no_op_reversibility",
            "delta_vs_no_op_public_effect",
            "delta_vs_no_op_hidden_effect",
            "delta_vs_no_op_cost",
        ]
    ].abs().sum(axis=1).gt(0).any()


def test_task2_2_calibrated_pressure_action_map_contract():
    calibrated_map, errors = build_and_validate_calibrated_pressure_action_map()

    assert errors == []
    assert not calibrated_map.empty
    assert set(calibrated_map["pressure_action_map_version"]) == {TASK2_2_CALIBRATION_VERSION}
    assert set(calibrated_map["calibration_status"]) == {"single_action_probe_calibrated"}
    assert set(calibrated_map["mapping_source"]) == {
        "single_action_probe_estimated_action_to_pressure_contribution"
    }
    assert set(calibrated_map["runtime_policy_input"]) == {False}
    assert set(calibrated_map["requires_task2_3_candidate_generation"]) == {True}
    assert set(calibrated_map["diagnostic_compat_policy_used"]) == {False}
    assert set(calibrated_map["repaired_diagnostic_policy_used"]) == {False}
    assert set(calibrated_map["new_semantic_translation_layer_added"]) == {False}


def test_task2_2_calibrated_shares_normalized_by_intent_and_band():
    calibrated_map = calibrate_pressure_action_map()
    grouped = calibrated_map.groupby(
        ["pressure_component", "component_direction", "semantic_effect", "scenario_or_state_band"],
        dropna=False,
    )["calibrated_action_share"].sum()

    assert ((grouped - 1.0).abs() <= 1e-9).all()


def test_task2_2_calibration_changes_at_least_some_initial_shares():
    calibrated_map = calibrate_pressure_action_map()
    changed = (
        calibrated_map["calibrated_action_share"] - calibrated_map["initial_action_share"]
    ).abs() > 1e-12

    assert changed.any()


def test_task2_2_validator_detects_runtime_input_mislabel():
    calibrated_map = calibrate_pressure_action_map()
    broken = calibrated_map.copy()
    broken.loc[broken.index[0], "runtime_policy_input"] = True

    errors = validate_calibrated_pressure_action_map(broken)

    assert "calibrated_pressure_action_map_marked_as_runtime_policy_input_before_task2_3" in errors
