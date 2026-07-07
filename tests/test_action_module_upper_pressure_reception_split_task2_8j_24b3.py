from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_24b3_multi_scenario_stateful_rollout_validation import (
    build_and_validate_multi_scenario_stateful_rollout_validation,
    validate_tables,
)


def test_task2_8j_24b3_multi_scenario_validation_ready():
    scenarios, policy, random_rollout, baseline, risk, step, threshold, checks, final_summary, errors, summary = build_and_validate_multi_scenario_stateful_rollout_validation()
    assert errors == []
    assert not scenarios.empty
    assert not policy.empty
    assert not random_rollout.empty
    assert not baseline.empty
    assert not risk.empty
    assert not step.empty
    assert not threshold.empty
    assert not checks.empty
    assert not final_summary.empty
    assert summary["task24_ready"] is True
    assert summary["scenario_count"] >= 4
    assert summary["unique_seed_count"] >= 3
    assert summary["policy_rollout_row_count"] >= 1200
    assert summary["random_rollout_row_count"] > 0
    assert summary["baseline_comparison_count"] > 0
    assert summary["risk_robustness_count"] > 0
    assert summary["randomized_operator_baseline_used"] is True
    assert summary["per_risk_robustness_audit"] is True
    assert summary["no_threshold_update_performed"] is True
    assert summary["action_candidate_generated"] is False
    assert summary["real_actionmodule_called"] is False
    assert summary["axis_executed"] is False
    assert summary["validation_errors"] == []
    assert summary["multi_scenario_stateful_rollout_validation_decision"] == "multi_scenario_stateful_rollout_validation_ready"


def test_task2_8j_24b3_controls_and_robustness_shape():
    scenarios, policy, random_rollout, baseline, risk, step, threshold, checks, final_summary, errors, summary = build_and_validate_multi_scenario_stateful_rollout_validation()
    assert errors == []
    assert set(policy["action_wait_step"].astype(int)) == set(range(6))
    assert set(random_rollout["action_wait_step"].astype(int)) == set(range(6))
    assert policy["action_beats_negative_control"].astype(bool).any()
    assert baseline["policy_minus_random_ev"].astype(float).notna().all()
    assert risk["risk_adoption_class"].astype(str).str.len().gt(0).all()
    assert step["policy_mean_ev"].astype(float).notna().all()
    assert threshold["requires_validation_before_update"].astype(bool).all()
    assert not threshold["may_update_threshold_now"].astype(bool).any()
    assert set(checks["check_status"].astype(str)) == {"pass"}
    assert int(final_summary["validation_check_count"].iloc[0]) == int(final_summary["validation_check_pass_count"].iloc[0])


def test_task2_8j_24b3_validator_detects_threshold_update_attempt():
    scenarios, policy, random_rollout, baseline, risk, step, threshold, checks, final_summary, _errors, _summary = build_and_validate_multi_scenario_stateful_rollout_validation()
    bad = threshold.copy()
    bad.loc[bad.index[0], "may_update_threshold_now"] = True
    errors = validate_tables(scenarios, policy, random_rollout, baseline, risk, step, bad, checks, final_summary)
    assert "task2_8j_24b3_threshold_update_attempted" in errors
