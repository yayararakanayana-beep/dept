from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_24b5_action_intensity_schedule_validation import (
    build_and_validate_action_intensity_schedule_validation,
    validate_tables,
)

_CACHE = None


def _result():
    global _CACHE
    if _CACHE is None:
        _CACHE = build_and_validate_action_intensity_schedule_validation()
    return _CACHE


def test_task2_8j_24b5_intensity_schedule_validation_ready():
    runtime, scoring, comparison, gradual, audit, checks, final_summary, errors, summary = _result()
    assert errors == []
    assert not runtime.empty
    assert not scoring.empty
    assert not comparison.empty
    assert not gradual.empty
    assert not audit.empty
    assert not checks.empty
    assert not final_summary.empty
    assert summary["source_task24b3_ready"] is True
    assert summary["runtime_policy_view_separated"] is True
    assert summary["validation_scoring_view_separated"] is True
    assert summary["runtime_uses_only_actionmodule_available_information"] is True
    assert summary["v2_used_for_scoring_only"] is True
    assert summary["NO_OP_used_for_scoring_only"] is True
    assert summary["threshold_freeze_allowed_now"] is False
    assert summary["no_threshold_update_performed"] is True
    assert summary["action_candidate_generated"] is False
    assert summary["real_actionmodule_called"] is False
    assert summary["axis_executed"] is False
    assert summary["validation_errors"] == []
    assert summary["action_intensity_schedule_validation_decision"] == "action_intensity_schedule_validation_ready"
    assert set(checks["check_status"].astype(str)) == {"pass"}
    assert int(final_summary["validation_check_count"].iloc[0]) == int(final_summary["validation_check_pass_count"].iloc[0])


def test_task2_8j_24b5_schedule_coverage_and_separation():
    runtime, scoring, comparison, gradual, audit, checks, final_summary, errors, summary = _result()
    assert errors == []
    assert {"fixed_weak", "fixed_medium", "fixed_strong", "gradual_ramp", "cautious_ramp_decay"}.issubset(set(runtime["schedule_name"].astype(str)))
    assert {"fixed", "gradual"}.issubset(set(runtime["schedule_family"].astype(str)))
    forbidden_runtime_columns = {"no_op_final_risk", "action_final_risk", "negative_control_final_risk", "scheduled_relative_ev"}
    assert forbidden_runtime_columns.isdisjoint(set(runtime.columns))
    assert scoring["scoring_status"].astype(str).eq("validation_scoring_only_not_runtime_input").all()
    assert runtime["runtime_policy_status"].astype(str).eq("runtime_policy_view_ready_no_scoring_information").all()
    assert not runtime["v2_future_used_by_runtime"].astype(bool).any()
    assert not runtime["validation_score_used_as_runtime_input"].astype(bool).any()
    assert not scoring["action_candidate_generated"].astype(bool).any()


def test_task2_8j_24b5_validator_detects_threshold_freeze_attempt():
    runtime, scoring, comparison, gradual, audit, checks, final_summary, _errors, _summary = _result()
    bad = final_summary.copy()
    bad.loc[bad.index[0], "threshold_freeze_allowed_now"] = True
    errors = validate_tables(runtime, scoring, comparison, gradual, audit, checks, bad)
    assert "task2_8j_24b5_threshold_freeze_attempted" in errors
