from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_5e_strength_curve_validation import (
    PRESSURE_STRENGTH_BANDS,
    STATE_BANDS,
    TASK2_5E_VERSION,
    build_action_strength_curve_validation_table,
    build_and_validate_action_strength_curve_validation_table,
    validate_action_strength_curve_validation_table,
)


def test_task2_5e_strength_curve_table_contract():
    table, errors = build_and_validate_action_strength_curve_validation_table()

    assert errors == []
    assert not table.empty
    assert set(table["task2_5e_version"]) == {TASK2_5E_VERSION}
    assert set(table["validation_type"]) == {"action_strength_curve_validation"}
    assert set(table["validation_only"]) == {True}
    assert set(table["runtime_policy_input"]) == {False}
    assert set(table["pressure_to_action_converter_created"]) == {False}
    assert set(table["final_action_decision"]) == {False}
    assert set(table["action_frame_created"]) == {False}
    assert set(table["actionmodule_called"]) == {False}
    assert set(table["new_semantic_translation_layer_added"]) == {False}
    assert set(table["diagnostic_compat_policy_used"]) == {False}
    assert set(table["repaired_diagnostic_policy_used"]) == {False}


def test_task2_5e_contains_all_strength_bands_and_state_bands():
    table = build_action_strength_curve_validation_table()

    assert set(PRESSURE_STRENGTH_BANDS).issubset(set(table["pressure_strength_band"]))
    assert set(STATE_BANDS).issubset(set(table["scenario_or_state_band"]))
    assert table["recommended_action_strength"].ge(0.0).all()
    assert (table["recommended_action_strength"] <= table["action_strength_cap"] + 1e-12).all()
    assert table["recommended_strength_curve"].astype(str).str.len().gt(0).all()


def test_task2_5e_high_limit_opening_actions_are_clipped_or_safety_mixed():
    table = build_action_strength_curve_validation_table()
    rows = table[
        table["action_channel"].isin(["exploration_injection", "relation_unlock", "coupling_relief"])
        & table["scenario_or_state_band"].isin(["high", "limit"])
        & table["pressure_strength_band"].isin(["high", "limit"])
    ]

    assert not rows.empty
    assert rows["clipping_required"].any()
    assert rows["safe_action_mixing_required"].any()
    assert rows["requires_task2_5f_inverse_validation"].any()


def test_task2_5e_has_clipping_saturation_and_inverse_validation_flags():
    table = build_action_strength_curve_validation_table()

    assert table["clipping_required"].any()
    assert table["saturation_flag"].any()
    assert table["safe_action_mixing_required"].any()
    assert table["requires_task2_5f_inverse_validation"].any()


def test_task2_5e_validator_detects_runtime_input_mislabel():
    table = build_action_strength_curve_validation_table()
    table.loc[table.index[0], "runtime_policy_input"] = True

    errors = validate_action_strength_curve_validation_table(table)
    assert "task2_5e_forbidden_true_field:runtime_policy_input" in errors
