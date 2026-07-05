from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_5c_interaction_modifier_validation import (
    TASK2_5C_VERSION,
    build_and_validate_interaction_modifier_validation_table,
    build_interaction_modifier_validation_table,
    validate_interaction_modifier_validation_table,
)


def test_task2_5c_interaction_modifier_table_contract():
    table, errors = build_and_validate_interaction_modifier_validation_table()

    assert errors == []
    assert not table.empty
    assert set(table["task2_5c_version"]) == {TASK2_5C_VERSION}
    assert set(table["validation_type"]) == {"interaction_modifier_validation"}
    assert set(table["validation_only"]) == {True}
    assert set(table["runtime_policy_input"]) == {False}
    assert set(table["pressure_to_action_converter_created"]) == {False}
    assert set(table["final_action_decision"]) == {False}
    assert set(table["action_frame_created"]) == {False}
    assert set(table["actionmodule_called"]) == {False}
    assert set(table["new_semantic_translation_layer_added"]) == {False}
    assert set(table["diagnostic_compat_policy_used"]) == {False}
    assert set(table["repaired_diagnostic_policy_used"]) == {False}
    assert set(table["combination_dependency_flag"]) == {True}


def test_task2_5c_contains_additive_safety_and_dangerous_classes():
    table = build_interaction_modifier_validation_table()

    assert "approximately_additive" in set(table["interaction_type"])
    assert "dangerous_opening_side_effect_amplification" in set(table["interaction_type"])
    assert "safety_side_nonlinear_mixed" in set(table["interaction_type"])
    assert "keep" in set(table["modifier_class"])
    assert "boost" in set(table["modifier_class"])
    assert {"dampen", "defer", "block"} & set(table["modifier_class"])


def test_task2_5c_exploration_plus_relation_unlock_is_weakened_and_relation_dependent():
    table = build_interaction_modifier_validation_table()
    rows = table[
        table["action_pair"].astype(str).isin(
            [
                "exploration_injection+relation_unlock",
                "relation_unlock+exploration_injection",
            ]
        )
    ]

    assert not rows.empty
    risky = rows[rows["scenario_or_state_band"].isin(["medium", "high", "limit"])]
    assert not risky.empty
    assert set(risky["interaction_type"]) == {"dangerous_opening_side_effect_amplification"}
    assert risky["relation_dependency_flag"].all()
    assert risky["interaction_modifier"].lt(1.0).all()
    assert set(risky["modifier_class"]).issubset({"dampen", "defer", "block"})
    assert (risky[risky["scenario_or_state_band"] == "limit"]["block_combination_flag"]).all()


def test_task2_5c_buffer_plus_volatility_can_be_safety_side_boost():
    table = build_interaction_modifier_validation_table()
    rows = table[
        table["action_pair"].astype(str).isin(
            [
                "buffer_increase+volatility_damping",
                "volatility_damping+buffer_increase",
            ]
        )
    ]

    assert not rows.empty
    nonlinear = rows[rows["interaction_type"] == "safety_side_nonlinear_mixed"]
    assert not nonlinear.empty
    assert nonlinear["interaction_modifier"].ge(1.0).all()
    assert nonlinear["requires_task2_5e_strength_review"].any()


def test_task2_5c_validator_detects_runtime_input_mislabel():
    table = build_interaction_modifier_validation_table()
    table.loc[table.index[0], "runtime_policy_input"] = True

    errors = validate_interaction_modifier_validation_table(table)
    assert "task2_5c_forbidden_true_field:runtime_policy_input" in errors
