import pandas as pd

from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_6_converter_rc1 import (
    TASK2_6_CONVERTER_VERSION,
    build_and_validate_demo_pressure_action_candidates,
    build_demo_pressure_inputs,
    convert_pressure_inputs_to_action_candidates,
    validate_pressure_action_candidates_no_strength_boost,
)


def test_task2_6_converter_contract_and_no_strength_boost_flags():
    table, errors = build_and_validate_demo_pressure_action_candidates()

    assert errors == []
    assert not table.empty
    assert set(table["task2_6_converter_version"]) == {TASK2_6_CONVERTER_VERSION}
    assert set(table["conversion_type"]) == {"pressure_to_action_candidate_conversion_no_strength_boost"}
    assert set(table["candidate_only"]) == {True}
    assert set(table["runtime_policy_input"]) == {False}
    assert set(table["final_action_decision"]) == {False}
    assert set(table["action_frame_created"]) == {False}
    assert set(table["actionmodule_called"]) == {False}
    assert set(table["world_runtime_called"]) == {False}
    assert set(table["pressure_to_action_converter_created"]) == {True}
    assert set(table["action_strength_correction_applied"]) == {False}
    assert set(table["pressure_matching_boost_applied"]) == {False}
    assert set(table["strength_curve_applied"]) == {False}
    assert set(table["pressure_result_gap_preserved"]) == {True}


def test_task2_6_preserves_pressure_result_gap_instead_of_boosting():
    table, errors = build_and_validate_demo_pressure_action_candidates()

    assert errors == []
    assert (table["expected_result_signal"] <= table["pressure_signal"] + 1e-12).all()
    assert table["pressure_result_gap"].gt(0.0).any()
    high_pressure = table[table["pressure_input_id"] == "demo_commitment_down_high_pressure"]
    assert not high_pressure.empty
    assert (high_pressure["pressure_result_gap"] > 0.0).all()
    assert set(high_pressure["pressure_matching_boost_applied"]) == {False}


def test_task2_6_custom_pressure_10_can_map_to_lower_expected_result():
    pressure = pd.DataFrame([
        {
            "pressure_input_id": "pressure_10_example",
            "pressure_component": "exploration_frequency",
            "component_direction": "increase",
            "pressure_strength": 10.0,
        }
    ])
    table = convert_pressure_inputs_to_action_candidates(pressure)

    assert not table.empty
    assert table["pressure_strength"].max() == 10.0
    assert (table["expected_result_signal"] < table["pressure_signal"]).all()
    assert table["pressure_result_gap"].gt(0.0).all()
    assert set(table["action_strength_correction_applied"]) == {False}


def test_task2_6_state_and_interaction_audit_do_not_create_final_actions():
    table, errors = build_and_validate_demo_pressure_action_candidates()

    assert errors == []
    assert table["state_audit_status"].astype(str).str.len().gt(0).all()
    assert table["interaction_audit_status"].astype(str).str.len().gt(0).all()
    assert table["candidate_status"].astype(str).str.endswith("not_final_action").any() or table["requires_downstream_gate_review"].any()
    assert set(table["final_action_decision"]) == {False}


def test_task2_6_unresolved_pressure_intent_audit_columns_exist_and_are_bounded():
    table, errors = build_and_validate_demo_pressure_action_candidates()

    assert errors == []
    for col in [
        "pressure_intent_coverage_score",
        "action_vocabulary_fit_score",
        "action_granularity_insufficient_flag",
        "new_action_channel_candidate_flag",
        "unresolved_pressure_intent",
        "safety_fallback_used",
    ]:
        assert col in table.columns

    assert table["pressure_intent_coverage_score"].between(0.0, 1.0).all()
    assert table["action_vocabulary_fit_score"].between(0.0, 1.0).all()
    assert table["action_granularity_insufficient_flag"].astype(bool).any()
    flagged = table[
        table["action_granularity_insufficient_flag"].astype(bool)
        | table["new_action_channel_candidate_flag"].astype(bool)
        | table["safety_fallback_used"].astype(bool)
    ]
    assert not flagged.empty
    assert flagged["unresolved_pressure_intent"].astype(str).str.len().gt(0).all()


def test_task2_6_unresolved_audit_does_not_change_no_boost_invariant():
    table, errors = build_and_validate_demo_pressure_action_candidates()

    assert errors == []
    assert set(table["action_strength_correction_applied"]) == {False}
    assert set(table["pressure_matching_boost_applied"]) == {False}
    assert (table["expected_result_signal"] <= table["pressure_signal"] + 1e-12).all()
    assert table["pressure_result_gap"].gt(0.0).any()


def test_task2_6_validator_detects_strength_boost_mislabel():
    table, _ = build_and_validate_demo_pressure_action_candidates()
    table.loc[table.index[0], "pressure_matching_boost_applied"] = True

    errors = validate_pressure_action_candidates_no_strength_boost(table)
    assert "task2_6_forbidden_true_field:pressure_matching_boost_applied" in errors
