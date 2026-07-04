from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_5f_inverse_validation import (
    TASK2_5F_VERSION,
    build_and_validate_inverse_pressure_action_validation_table,
    build_inverse_pressure_action_validation_table,
    validate_inverse_pressure_action_validation_table,
)


def test_task2_5f_inverse_validation_table_contract():
    table, errors = build_and_validate_inverse_pressure_action_validation_table()

    assert errors == []
    assert not table.empty
    assert set(table["task2_5f_version"]) == {TASK2_5F_VERSION}
    assert set(table["validation_type"]) == {"inverse_pressure_action_validation"}
    assert set(table["validation_only"]) == {True}
    assert set(table["runtime_policy_input"]) == {False}
    assert set(table["validation_synthesis_only"]) == {True}
    assert set(table["pressure_to_action_converter_created"]) == {False}
    assert set(table["final_action_decision"]) == {False}
    assert set(table["action_frame_created"]) == {False}
    assert set(table["actionmodule_called"]) == {False}
    assert set(table["world_runtime_called"]) == {False}
    assert set(table["new_semantic_translation_layer_added"]) == {False}
    assert set(table["diagnostic_compat_policy_used"]) == {False}
    assert set(table["repaired_diagnostic_policy_used"]) == {False}


def test_task2_5f_scores_are_bounded_and_nonempty():
    table = build_inverse_pressure_action_validation_table()

    bounded = [
        "intent_alignment_score",
        "recoverability_score",
        "exploration_preservation_score",
        "overfixation_risk",
        "divergence_risk",
    ]
    for col in bounded:
        assert table[col].between(0.0, 1.0).all()
    assert table["side_effect_burden"].ge(0.0).all()
    assert table["applied_action_set_ja"].astype(str).str.contains("作用").any()
    assert table["reconstructed_pressure_effect_json"].astype(str).str.contains(":").all()


def test_task2_5f_surfaces_converter_caution_and_rollback_rows():
    table = build_inverse_pressure_action_validation_table()

    assert table["requires_task2_6_converter_caution"].any()
    assert table["rollback_required"].any()
    assert set(table["inverse_validation_status"]).issubset(
        {
            "aligned_within_validation_scope",
            "aligned_but_requires_rollback_guard",
            "weak_alignment",
            "risky_misalignment",
        }
    )


def test_task2_5f_risky_pressure_mixes_are_not_silently_accepted():
    table = build_inverse_pressure_action_validation_table()
    risky = table[
        table["pressure_input_id"].isin(
            [
                "exploration_up__commitment_down",
                "commitment_down__adoption_threshold_down",
            ]
        )
        & table["scenario_or_state_band"].isin(["high", "limit"])
    ]

    assert not risky.empty
    assert risky["requires_task2_6_converter_caution"].any()
    assert risky["recommended_post_filtering"].astype(str).str.len().gt(0).all()


def test_task2_5f_validator_detects_runtime_input_mislabel():
    table = build_inverse_pressure_action_validation_table()
    table.loc[table.index[0], "runtime_policy_input"] = True

    errors = validate_inverse_pressure_action_validation_table(table)
    assert "task2_5f_forbidden_true_field:runtime_policy_input" in errors
