from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_5a_single_action_correspondence import (
    TASK2_5A_VERSION,
    build_and_validate_single_action_to_pressure_correspondence_table,
    build_single_action_to_pressure_correspondence_table,
    validate_single_action_to_pressure_correspondence_table,
)


def test_task2_5a_single_action_to_pressure_table_contract():
    table, errors = build_and_validate_single_action_to_pressure_correspondence_table()

    assert errors == []
    assert not table.empty
    assert set(table["task2_5a_version"]) == {TASK2_5A_VERSION}
    assert set(table["validation_type"]) == {"single_action_to_pressure_correspondence_summary"}
    assert set(table["validation_only"]) == {True}
    assert set(table["runtime_policy_input"]) == {False}
    assert set(table["pressure_to_action_converter_created"]) == {False}
    assert set(table["final_action_decision"]) == {False}
    assert set(table["action_frame_created"]) == {False}
    assert set(table["actionmodule_called"]) == {False}
    assert set(table["new_semantic_translation_layer_added"]) == {False}
    assert set(table["diagnostic_compat_policy_used"]) == {False}
    assert set(table["repaired_diagnostic_policy_used"]) == {False}
    assert table["action_name_ja"].astype(str).str.len().gt(0).all()
    assert table["pressure_intent_ja"].astype(str).str.len().gt(0).all()


def test_task2_5a_action_to_pressure_shares_are_normalized_by_action():
    table = build_single_action_to_pressure_correspondence_table()
    positive = table[table["basic_alignment_score"] > 0]

    assert not positive.empty
    grouped = positive.groupby("action_channel")["action_to_pressure_share"].sum()
    assert ((grouped - 1.0).abs() < 1e-9).all()


def test_task2_5a_ranks_and_roles_are_informative():
    table = build_single_action_to_pressure_correspondence_table()

    allowed_roles = {
        "primary_correspondence",
        "supporting_correspondence",
        "weak_or_unresolved",
    }
    assert set(table["primary_or_supporting_action"]).issubset(allowed_roles)
    assert table.groupby("action_channel")["basic_alignment_rank"].min().eq(1).all()
    assert "primary_correspondence" in set(table["primary_or_supporting_action"])


def test_task2_5a_preserves_state_and_interaction_review_flags():
    table = build_single_action_to_pressure_correspondence_table()

    assert "state_sensitivity_flag" in table.columns
    assert "interaction_sensitivity_flag" in table.columns
    assert table["state_dependence_status"].astype(str).str.len().gt(0).all()
    assert table["interaction_review_reason"].astype(str).str.len().gt(0).all()


def test_task2_5a_validator_detects_runtime_input_mislabel():
    table = build_single_action_to_pressure_correspondence_table()
    table.loc[table.index[0], "runtime_policy_input"] = True

    errors = validate_single_action_to_pressure_correspondence_table(table)
    assert "task2_5a_marked_as_runtime_policy_input" in errors
