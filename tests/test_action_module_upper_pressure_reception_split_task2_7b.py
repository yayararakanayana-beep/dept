from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_7b_insurance_closed_validation_v2 import (
    TASK2_7B_V2_VERSION,
    build_and_validate_insurance_closed_validation_v2_table,
    build_insurance_closed_validation_v2_table,
    build_v2_risk_states,
    lower_observation_from_v2_risk_state,
    summarize_insurance_closed_validation_v2,
    upper_pressure_from_lower_observation_v2,
    validate_insurance_closed_validation_v2_table,
)


def test_task2_7b_v2_state_to_lower_observation_to_upper_pressure_chain():
    v2 = build_v2_risk_states()
    terrain = lower_observation_from_v2_risk_state(v2)
    pressure = upper_pressure_from_lower_observation_v2(terrain)

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
    table, errors, summary = build_and_validate_insurance_closed_validation_v2_table()

    assert errors == []
    assert not table.empty
    assert set(table["task2_7b_v2_version"]) == {TASK2_7B_V2_VERSION}
    assert set(table["validation_only"]) == {True}
    assert set(table["runtime_policy_input"]) == {False}
    assert set(table["action_frame_created"]) == {False}
    assert set(table["actionmodule_called"]) == {False}
    assert set(table["world_runtime_called"]) == {False}
    assert set(table["canonical_write_performed"]) == {False}
    assert set(table["pressure_inputs_preserved"]) == {True}
    assert summary["rows"] == len(table)


def test_task2_7b_lower_observation_detects_risk():
    table = build_insurance_closed_validation_v2_table()
    risk_rows = table[table["v2_state_id"].isin(["v2_boundary_instability_risk", "v2_unresolved_medium_risk"])]

    assert not risk_rows.empty
    assert risk_rows["lower_observation_detected_risk"].astype(bool).any()
    assert risk_rows["lower_observation_risk_score"].max() > 0.42


def test_task2_7b_activated_candidates_show_improvement_and_side_effects():
    table = build_insurance_closed_validation_v2_table()
    activated = table[table["activated"].astype(bool)]

    assert not activated.empty
    assert activated["risk_improvement_vs_no_op"].ge(0.0).all()
    assert activated["recovery_improvement_vs_no_op"].ge(0.0).all()
    assert activated["gain_improvement_vs_no_op"].ge(0.0).all()
    assert activated["side_effect_burden"].ge(0.0).all()
    assert activated["net_validation_benefit"].gt(0.0).any()
    assert activated["benefit_pass"].astype(bool).any()


def test_task2_7b_threshold_reduction_is_measured_not_forced():
    table = build_insurance_closed_validation_v2_table()
    summary = summarize_insurance_closed_validation_v2(table)
    by_profile = {row["threshold_profile"]: row for row in summary["by_threshold_profile"]}

    assert set(by_profile) == {"conservative", "base", "reduced"}
    assert "threshold_reduction_activation_delta" in table.columns
    assert "threshold_reduction_side_effect_delta" in table.columns
    assert table["threshold_reduction_activation_delta"].notna().all()
    assert table["threshold_reduction_side_effect_delta"].notna().all()
    assert "threshold_reduction_triggered_more_actions" in table.columns
    assert "threshold_reduction_side_effect_caution" in table.columns


def test_task2_7b_validator_detects_actionmodule_call_mislabel():
    table = build_insurance_closed_validation_v2_table()
    table.loc[table.index[0], "actionmodule_called"] = True

    errors = validate_insurance_closed_validation_v2_table(table)
    assert "task2_7b_v2_forbidden_true_field:actionmodule_called" in errors
