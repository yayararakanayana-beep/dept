from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_5b_state_modifier_validation import (
    TASK2_5B_VERSION,
    STATE_AXIS_SPECS,
    STATE_LEVELS,
    build_and_validate_state_modifier_validation_table,
    build_state_modifier_validation_table,
    validate_state_modifier_validation_table,
)


def test_task2_5b_state_modifier_table_contract():
    table, errors = build_and_validate_state_modifier_validation_table()

    assert errors == []
    assert not table.empty
    assert set(table["task2_5b_version"]) == {TASK2_5B_VERSION}
    assert set(table["validation_type"]) == {"state_modifier_validation"}
    assert set(table["validation_only"]) == {True}
    assert set(table["runtime_policy_input"]) == {False}
    assert set(table["state_detector_created"]) == {False}
    assert set(table["lower_layer_state_connected"]) == {False}
    assert set(table["pressure_to_action_converter_created"]) == {False}
    assert set(table["final_action_decision"]) == {False}
    assert set(table["action_frame_created"]) == {False}
    assert set(table["actionmodule_called"]) == {False}
    assert set(table["new_semantic_translation_layer_added"]) == {False}
    assert set(table["diagnostic_compat_policy_used"]) == {False}
    assert set(table["repaired_diagnostic_policy_used"]) == {False}


def test_task2_5b_contains_all_state_axes_levels_and_actions():
    table = build_state_modifier_validation_table()

    expected_axes = {spec.state_axis for spec in STATE_AXIS_SPECS}
    assert expected_axes.issubset(set(table["state_axis"]))
    assert set(STATE_LEVELS).issubset(set(table["state_level"]))
    assert set(table["action_channel"]) == {
        "buffer_increase",
        "coupling_relief",
        "exploration_injection",
        "relation_unlock",
        "uncertainty_probe",
        "volatility_damping",
    }
    assert table["required_lower_layer_signal"].astype(str).str.len().gt(0).all()
    assert table["expected_source_layer"].astype(str).str.len().gt(0).all()
    assert table["expected_source_artifact"].astype(str).str.len().gt(0).all()
    assert set(table["lower_layer_connection_status"]) == {"placeholder_until_lower_layer_connection"}


def test_task2_5b_oscillation_dampens_opening_actions_and_boosts_safety_actions():
    table = build_state_modifier_validation_table()
    high = table[(table["state_axis"] == "oscillation_strength") & (table["state_level"].isin(["high", "limit"]))]

    opening = high[high["action_channel"].isin(["exploration_injection", "relation_unlock", "coupling_relief"])]
    safety = high[high["action_channel"].isin(["buffer_increase", "volatility_damping"])]

    assert not opening.empty
    assert not safety.empty
    assert opening["state_modifier"].lt(1.0).all()
    assert safety["state_modifier"].gt(1.0).all()


def test_task2_5b_exploration_deficit_boosts_exploration_action():
    table = build_state_modifier_validation_table()
    rows = table[
        (table["state_axis"] == "exploration_deficit")
        & (table["state_level"].isin(["high", "limit"]))
        & (table["action_channel"] == "exploration_injection")
    ]

    assert not rows.empty
    assert rows["boost_flag"].all()
    assert rows["state_modifier"].gt(1.0).all()


def test_task2_5b_low_recoverability_defers_opening_actions():
    table = build_state_modifier_validation_table()
    rows = table[
        (table["state_axis"] == "recoverability_level")
        & (table["state_level"] == "low")
        & (table["action_channel"].isin(["exploration_injection", "relation_unlock", "coupling_relief"]))
    ]

    assert not rows.empty
    assert set(rows["modifier_class"]) == {"defer"}
    assert rows["defer_flag"].all()


def test_task2_5b_validator_detects_runtime_input_mislabel():
    table = build_state_modifier_validation_table()
    table.loc[table.index[0], "runtime_policy_input"] = True

    errors = validate_state_modifier_validation_table(table)
    assert "task2_5b_forbidden_true_field:runtime_policy_input" in errors
