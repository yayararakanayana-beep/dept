from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_7b_insurance_closed_validation import (
    TASK2_7B_VALIDATION_VERSION,
    build_and_validate_insurance_closed_validation_table,
    build_insurance_closed_validation_table,
    build_v2_danger_states,
    lower_observation_from_v2_state,
    summarize_insurance_closed_validation,
    upper_pressure_from_lower_observation,
    validate_insurance_closed_validation_table,
)


def test_task2_7b_v2_state_to_lower_observation_to_upper_pressure_chain():
    v2 = build_v2_danger_states()
    terrain = lower_observation_from_v2_state(v2)
    pressure = upper_pressure_from_lower_observation(terrain)

    assert not v2.empty
    assert not terrain.empty
    assert not pressure.empty
    assert set(v2["v2_state_id"]).issubset(set(terrain["v2_state_id"]))
    assert set(terrain["v2_state_id"]).issubset(set(pressure["v2_state_id"]))
    assert terrain["boundary_risk_score"].between(0.0, 1.0).all()
    assert terrain["instability_score"].between(0.0, 1.0).all()
    assert terrain["recovery_margin"].between(0.0, 1.0).all()
    assert pressure["pressure_strength"].gt(0.0).all()
    assert set(pressure["runtime_policy_input"]) == {False}


def test_task2_7b_closed_validation_contract_and_boundaries():
    table, errors, summary = build_and_validate_insurance_closed_validation_table()

    assert errors == []
    assert not table.empty
    assert set(table["task2_7b_validation_version"]) == {TASK2_7B_VALIDATION_VERSION}
    assert set(table["validation_only"]) == {True}
    assert set(table["runtime_policy_input"]) == {False}
    assert set(table["action_frame_created"]) == {False}
    assert set(table["actionmodule_called"]) == {False}
    assert set(table["world_runtime_called"]) == {False}
    assert set(table["canonical_write_performed"]) == {False}
    assert set(table["pressure_inputs_preserved"]) == {True}
    assert summary["rows"] == len(table)


def test_task2_7b_lower_observation_detects_danger():
    table = build_insurance_closed_validation_table()
    danger = table[table["v2_state_id"].isin(["v2_boundary_instability_danger", "v2_unresolved_medium_danger"])]

    assert not danger.empty
    assert danger["lower_observation_detected_risk"].astype(bool).any()
    assert danger["lower_observation_risk_score"].max() > 0.42


def test_task2_7b_activated_candidates_show_improvement_and_side_effects():
    table = build_insurance_closed_validation_table()
    activated = table[table["activated"].astype(bool)]

    assert not activated.empty
    assert activated["risk_improvement_vs_no_op"].ge(0.0).all()
    assert activated["recovery_improvement_vs_no_op"].ge(0.0).all()
    assert activated["gain_improvement_vs_no_op"].ge(0.0).all()
    assert activated["side_effect_burden"].ge(0.0).all()
    assert activated["net_validation_benefit"].gt(0.0).any()
    assert activated["benefit_pass"].astype(bool).any()


def test_task2_7b_threshold_reduction_changes_activation_count_and_flags_caution():
    table = build_insurance_closed_validation_table()
    summary = summarize_insurance_closed_validation(table)
    by_profile = {row["threshold_profile"]: row for row in summary["by_threshold_profile"]}

    assert by_profile["reduced"]["activated_rows"] >= by_profile["base"]["activated_rows"] >= by_profile["conservative"]["activated_rows"]
    assert table["threshold_reduction_triggered_more_actions"].astype(bool).any()
    # Lower thresholds may or may not be unacceptable, but the additional action
    # exposure is explicitly logged as a side-effect caution when it increases.
    assert "threshold_reduction_side_effect_caution" in table.columns


def test_task2_7b_validator_detects_actionmodule_call_mislabel():
    table = build_insurance_closed_validation_table()
    table.loc[table.index[0], "actionmodule_called"] = True

    errors = validate_insurance_closed_validation_table(table)
    assert "task2_7b_forbidden_true_field:actionmodule_called" in errors
