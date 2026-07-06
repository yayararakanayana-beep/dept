from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_24b2_v2_stateful_rollout_action_material_validation import (
    build_and_validate_v2_stateful_rollout_action_material_validation,
    validate_tables,
)


def test_task2_8j_24b2_stateful_rollout_validation_ready():
    starts, rollout, step_summary, threshold, checks, final_summary, errors, summary = build_and_validate_v2_stateful_rollout_action_material_validation()
    assert errors == []
    assert not starts.empty
    assert not rollout.empty
    assert not step_summary.empty
    assert not threshold.empty
    assert not checks.empty
    assert not final_summary.empty
    assert summary["task24_ready"] is True
    assert summary["task6b_ready"] is True
    assert summary["v2_stateful_rollout_action_material_validation_decision"] == "v2_stateful_rollout_action_material_validation_ready"
    assert summary["v2_start_count"] >= 20
    assert summary["unique_seed_count"] >= 3
    assert summary["rollout_row_count"] >= summary["operator_selection_count"] * 20
    assert summary["observable_v2_no_op_future_used_for_scoring"] is True
    assert summary["relation_field_counterfactual_rollout_used"] is True
    assert summary["negative_control_rollout_used"] is True
    assert summary["v2_window_not_runtime_oracle"] is True
    assert summary["no_threshold_update_performed"] is True
    assert summary["action_candidate_generated"] is False
    assert summary["real_actionmodule_called"] is False
    assert summary["axis_executed"] is False
    assert summary["validation_errors"] == []


def test_task2_8j_24b2_rollout_has_controls_and_step_coverage():
    starts, rollout, step_summary, threshold, checks, final_summary, errors, summary = build_and_validate_v2_stateful_rollout_action_material_validation()
    assert errors == []
    assert set(rollout["action_wait_step"].astype(int)) == set(range(6))
    assert rollout["action_beats_no_op"].astype(bool).any()
    assert rollout["action_beats_negative_control"].astype(bool).any()
    assert rollout["relative_ev_rollout"].astype(float).notna().all()
    assert step_summary["row_count"].astype(int).min() > 0
    assert threshold["requires_validation_before_update"].astype(bool).all()
    assert not threshold["may_update_threshold_now"].astype(bool).any()
    assert set(checks["check_status"].astype(str)) == {"pass"}
    assert int(final_summary["validation_check_count"].iloc[0]) == int(final_summary["validation_check_pass_count"].iloc[0])


def test_task2_8j_24b2_validator_detects_threshold_update_attempt():
    starts, rollout, step_summary, threshold, checks, final_summary, _errors, _summary = build_and_validate_v2_stateful_rollout_action_material_validation()
    bad = threshold.copy()
    bad.loc[bad.index[0], "may_update_threshold_now"] = True
    errors = validate_tables(starts, rollout, step_summary, bad, checks, final_summary)
    assert "task2_8j_24b2_threshold_update_attempted" in errors
