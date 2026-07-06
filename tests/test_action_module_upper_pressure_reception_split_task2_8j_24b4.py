from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_24b4_targeted_robustness_validation import (
    build_and_validate_targeted_robustness_validation,
    validate_tables,
)


def test_task2_8j_24b4_targeted_robustness_ready():
    primary, stress, boundary, resource, window, gates, checks, final_summary, errors, summary = build_and_validate_targeted_robustness_validation()
    assert errors == []
    assert not primary.empty
    assert not stress.empty
    assert not boundary.empty
    assert not resource.empty
    assert not window.empty
    assert not gates.empty
    assert not checks.empty
    assert not final_summary.empty
    assert summary["source_task24b3_ready"] is True
    assert summary["policy_rollout_row_count"] > 0
    assert summary["primary_objective_row_count"] > 0
    assert summary["stress_audit_row_count"] > 0
    assert summary["boundary_fragile_audit_row_count"] > 0
    assert summary["resource_pressure_audit_row_count"] > 0
    assert summary["adoption_window_row_count"] > 0
    assert summary["gate_recommendation_count"] > 0
    assert summary["overall_mean_relative_ev"] > 0
    assert summary["overall_action_beats_no_op_rate"] > 0
    assert summary["overall_policy_beats_random_rate"] > 0
    assert summary["threshold_freeze_allowed_now"] is False
    assert summary["no_threshold_update_performed"] is True
    assert summary["action_candidate_generated"] is False
    assert summary["real_actionmodule_called"] is False
    assert summary["axis_executed"] is False
    assert summary["validation_errors"] == []
    assert summary["targeted_robustness_validation_decision"] == "targeted_robustness_validation_ready"
    assert set(checks["check_status"].astype(str)) == {"pass"}
    assert int(final_summary["validation_check_count"].iloc[0]) == int(final_summary["validation_check_pass_count"].iloc[0])


def test_task2_8j_24b4_gate_and_targeted_audits_exist():
    primary, stress, boundary, resource, window, gates, checks, final_summary, errors, summary = build_and_validate_targeted_robustness_validation()
    assert errors == []
    assert set(gates["risk_name"].astype(str)).issuperset({"boundary_fragile", "resource_pressure"})
    assert boundary["boundary_fragile_class"].astype(str).str.len().gt(0).all()
    assert resource["resource_pressure_class"].astype(str).str.len().gt(0).all()
    assert set(window["wait_window"].astype(str)).issuperset({"wait_0_2", "wait_3_5"})
    assert stress["secondary_stress_class"].astype(str).str.len().gt(0).all()
    assert not gates["may_freeze_threshold_now"].astype(bool).any()


def test_task2_8j_24b4_validator_detects_freeze_attempt():
    primary, stress, boundary, resource, window, gates, checks, final_summary, _errors, _summary = build_and_validate_targeted_robustness_validation()
    bad = gates.copy()
    bad.loc[bad.index[0], "may_freeze_threshold_now"] = True
    errors = validate_tables(primary, stress, boundary, resource, window, bad, checks, final_summary)
    assert "task2_8j_24b4_threshold_freeze_attempted" in errors
