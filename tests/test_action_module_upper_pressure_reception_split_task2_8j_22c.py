from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_22c_provisional_threshold_policy_contract import (
    ProvisionalThresholdPolicyContractConfig,
    build_and_validate_provisional_threshold_policy_contract,
    validate_provisional_threshold_policy_contract_tables,
)


def test_task2_8j_22c_policy_boundaries():
    safety, thresholds, state_policy, upper, checks, final_summary, errors, summary = build_and_validate_provisional_threshold_policy_contract(
        cfg=ProvisionalThresholdPolicyContractConfig()
    )
    assert errors == []
    assert not safety.empty
    assert not thresholds.empty
    assert not state_policy.empty
    assert not upper.empty
    assert not checks.empty
    assert not final_summary.empty
    assert summary["gt_main_map_name"] == "static_pca_7"
    assert summary["gt_main_component_count"] == 7
    assert summary["task22b_ready"] is True
    assert summary["safety_rules_fixed"] is True
    assert summary["decision_thresholds_revisable"] is True
    assert summary["threshold_values_are_provisional"] is True
    assert summary["threshold_revision_requires_validation"] is True
    assert summary["system_state_sensitive_thresholds"] is True
    assert summary["future_upper_pressure_threshold_coupling_note"] is True
    assert summary["upper_pressure_coupling_is_future_only"] is True
    assert summary["upper_pressure_may_modulate_thresholds_not_direct_action"] is True
    assert summary["current_threshold_update_performed"] is False
    assert summary["upper_pressure_coupled_now"] is False
    assert summary["action_direction_generated"] is False
    assert summary["terrain_operator_selected"] is False
    assert summary["action_candidate_generated"] is False
    assert summary["action_effect_prediction_generated"] is False
    assert summary["axis_executed"] is False
    assert summary["real_actionmodule_called"] is False
    assert summary["validation_errors"] == []

    for table in [safety, thresholds, state_policy, upper, checks, final_summary]:
        assert set(table["validation_only"].astype(bool)) == {True}
        assert set(table["contract_only"].astype(bool)) == {True}
        assert set(table["threshold_policy_only"].astype(bool)) == {True}
        assert set(table["safety_rules_fixed"].astype(bool)) == {True}
        assert set(table["decision_thresholds_revisable"].astype(bool)) == {True}
        assert set(table["threshold_values_are_provisional"].astype(bool)) == {True}
        assert set(table["threshold_revision_requires_validation"].astype(bool)) == {True}
        assert set(table["system_state_sensitive_thresholds"].astype(bool)) == {True}
        assert set(table["future_upper_pressure_threshold_coupling_note"].astype(bool)) == {True}
        assert set(table["upper_pressure_coupling_is_future_only"].astype(bool)) == {True}
        assert set(table["upper_pressure_may_modulate_thresholds_not_direct_action"].astype(bool)) == {True}
        assert set(table["current_threshold_update_performed"].astype(bool)) == {False}
        assert set(table["upper_pressure_coupled_now"].astype(bool)) == {False}
        assert set(table["action_direction_generated"].astype(bool)) == {False}
        assert set(table["terrain_operator_selected"].astype(bool)) == {False}
        assert set(table["action_candidate_generated"].astype(bool)) == {False}
        assert set(table["hidden_truth_input"].astype(bool)) == {False}
        assert set(table["future_information_used"].astype(bool)) == {False}


def test_task2_8j_22c_fixed_vs_revisable_separation():
    safety, thresholds, state_policy, upper, checks, final_summary, errors, summary = build_and_validate_provisional_threshold_policy_contract()
    assert errors == []
    assert set(safety["fixed_status"].astype(str)) == {"fixed"}
    assert thresholds["revisable_status"].astype(str).str.contains("revisable").all()
    assert thresholds["validation_required"].astype(bool).all()
    assert not upper["allowed_now"].astype(bool).any()
    assert set(upper["coupling_mode"].astype(str)) == {"threshold_modulation_only"}
    assert set(checks["check_status"].astype(str)) == {"pass"}
    assert int(final_summary["policy_check_count"].iloc[0]) == int(final_summary["policy_check_pass_count"].iloc[0])
    assert summary["provisional_threshold_policy_contract_decision"] == "provisional_threshold_policy_contract_ready"
    assert summary["fixed_safety_count"] == len(safety)
    assert summary["revisable_threshold_count"] == len(thresholds)
    assert summary["upper_pressure_future_only_count"] == len(upper)


def test_task2_8j_22c_validator_detects_current_upper_pressure_coupling():
    safety, thresholds, state_policy, upper, checks, final_summary, _errors, _summary = build_and_validate_provisional_threshold_policy_contract()
    bad = upper.copy()
    bad.loc[bad.index[0], "allowed_now"] = True
    errors = validate_provisional_threshold_policy_contract_tables(safety, thresholds, state_policy, bad, checks, final_summary)
    assert "task2_8j_22c_required_true_not_all_true:upper:upper_pressure_coupling_is_future_only" not in errors
    assert "task2_8j_22c_upper_pressure_coupled_now" in errors
