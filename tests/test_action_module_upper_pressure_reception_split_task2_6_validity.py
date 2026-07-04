from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_6_validity_validation import (
    TASK2_6_VALIDITY_VERSION,
    build_and_validate_pressure_action_converter_validity_validation_table,
    build_pressure_action_converter_validity_validation_table,
    validate_pressure_action_converter_validity_validation_table,
)


def test_task2_6_validity_table_contract():
    table, errors = build_and_validate_pressure_action_converter_validity_validation_table()

    assert errors == []
    assert not table.empty
    assert set(table["task2_6_validity_version"]) == {TASK2_6_VALIDITY_VERSION}
    assert set(table["validation_type"]) == {"pressure_action_converter_validity_validation"}
    assert set(table["validation_only"]) == {True}
    assert set(table["runtime_policy_input"]) == {False}
    assert set(table["pressure_to_action_converter_created"]) == {True}
    assert set(table["action_strength_correction_applied"]) == {False}
    assert set(table["pressure_matching_boost_applied"]) == {False}
    assert set(table["final_action_decision"]) == {False}
    assert set(table["action_frame_created"]) == {False}
    assert set(table["actionmodule_called"]) == {False}
    assert set(table["world_runtime_called"]) == {False}


def test_task2_6_validity_covers_22_pressure_direction_pairs():
    table = build_pressure_action_converter_validity_validation_table()

    pair_count = table[["pressure_component", "component_direction"]].drop_duplicates().shape[0]
    assert pair_count >= 22
    assert set(table["component_direction"]) >= {"increase", "decrease"}
    assert set(table["state_case_id"]) == {"stable_no_state_supplied", "high_opening_risk_state"}


def test_task2_6_validity_core_invariants_pass_for_all_rows():
    table = build_pressure_action_converter_validity_validation_table()

    for col in [
        "all_strengths_produced_candidates",
        "no_strength_boost_invariant_pass",
        "gap_preserved_invariant_pass",
        "monotonic_pressure_signal_pass",
        "direction_semantics_preserved",
        "unresolved_intent_audit_columns_present",
    ]:
        assert table[col].astype(bool).all(), col
    assert set(table["validity_status"]) == {"pass"}


def test_task2_6_validity_unresolved_audit_and_gate_review_are_active():
    table = build_pressure_action_converter_validity_validation_table()

    assert table["unresolved_intent_audit_active"].astype(bool).any()
    assert table["downstream_gate_review_rows"].gt(0).any()
    assert table["min_pressure_intent_coverage_score"].between(0.0, 1.0).all()
    assert table["min_action_vocabulary_fit_score"].between(0.0, 1.0).all()
    assert table["max_pressure_result_gap"].gt(0.0).all()


def test_task2_6_validity_validator_detects_boost_mislabel():
    table = build_pressure_action_converter_validity_validation_table()
    table.loc[table.index[0], "pressure_matching_boost_applied"] = True

    errors = validate_pressure_action_converter_validity_validation_table(table)
    assert "task2_6_validity_forbidden_true_field:pressure_matching_boost_applied" in errors
