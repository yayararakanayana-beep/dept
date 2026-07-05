from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_map_rc1 import (
    PRESSURE_ACTION_MAP_VERSION,
    build_and_validate_initial_pressure_action_map,
    build_initial_pressure_action_map,
    validate_initial_pressure_action_map,
)


def test_task2_1_initial_pressure_action_map_contract():
    pressure_action_map, errors = build_and_validate_initial_pressure_action_map()

    assert errors == []
    assert not pressure_action_map.empty
    assert set(pressure_action_map["pressure_action_map_version"]) == {PRESSURE_ACTION_MAP_VERSION}
    assert set(pressure_action_map["calibration_status"]) == {"uncalibrated"}
    assert set(pressure_action_map["mapping_source"]) == {
        "initial_hypothesis_from_pressure_intent_relevance_flags"
    }
    assert set(pressure_action_map["runtime_policy_input"]) == {False}
    assert set(pressure_action_map["requires_task2_2_calibration"]) == {True}
    assert set(pressure_action_map["diagnostic_compat_policy_used"]) == {False}
    assert set(pressure_action_map["repaired_diagnostic_policy_used"]) == {False}
    assert set(pressure_action_map["new_semantic_translation_layer_added"]) == {False}


def test_task2_1_initial_shares_are_normalized_by_intent():
    pressure_action_map = build_initial_pressure_action_map()
    grouped = pressure_action_map.groupby(
        ["pressure_component", "component_direction", "semantic_effect"],
        dropna=False,
    )["initial_action_share"].sum()

    assert ((grouped - 1.0).abs() <= 1e-9).all()


def test_task2_1_validator_detects_false_calibration_claim():
    pressure_action_map = build_initial_pressure_action_map()
    broken = pressure_action_map.copy()
    broken.loc[broken.index[0], "calibration_status"] = "calibrated"

    errors = validate_initial_pressure_action_map(broken)

    assert "pressure_action_map_not_all_uncalibrated" in errors
