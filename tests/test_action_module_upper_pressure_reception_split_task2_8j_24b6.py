from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_24b6_final_triage_before_24c import (
    build_and_validate_final_triage_before_24c,
    validate_tables,
)

_CACHE = None


def _result():
    global _CACHE
    if _CACHE is None:
        _CACHE = build_and_validate_final_triage_before_24c()
    return _CACHE


def test_task2_8j_24b6_final_triage_ready():
    policy, review, matrix, checks, final_summary, errors, summary = _result()
    assert errors == []
    assert not policy.empty
    assert not review.empty
    assert not matrix.empty
    assert not checks.empty
    assert not final_summary.empty
    assert summary["source_task24b4_ready"] is True
    assert summary["source_task24b5_ready"] is True
    assert summary["ready_for_24c_count"] == 3
    assert summary["guarded_review_count"] == 1
    assert summary["redesign_required_count"] == 1
    assert summary["blocked_from_adoption_count"] == 2
    assert summary["recommended_24c_scope"] == "relation_lock,oscillation,reversibility_loss"
    assert summary["threshold_freeze_allowed_now"] is False
    assert summary["action_candidate_generated"] is False
    assert summary["real_actionmodule_called"] is False
    assert summary["axis_executed"] is False
    assert summary["validation_errors"] == []
    assert summary["task24b6_final_triage_decision"] == "final_triage_before_24c_ready"
    assert set(checks["check_status"].astype(str)) == {"pass"}


def test_task2_8j_24b6_policy_and_review_split():
    policy, review, matrix, checks, final_summary, errors, summary = _result()
    assert errors == []
    assert set(policy["risk_name"].astype(str)) == {"relation_lock", "oscillation", "reversibility_loss"}
    assert set(policy["recommended_intensity_schedule"].astype(str)) == {"fixed_medium"}
    assert policy["policy_readiness_class"].astype(str).eq("ready_for_task24c_provisional_policy").all()
    assert set(review["risk_name"].astype(str)) == {"boundary_fragile", "resource_pressure"}
    assert review["blocked_from_24c_adoption"].astype(bool).all()
    assert set(matrix["matrix_decision"].astype(str)).issuperset({"enter_task24c_scope", "additional_validation_before_adoption", "operator_redesign_before_adoption"})


def test_task2_8j_24b6_validator_detects_action_candidate():
    policy, review, matrix, checks, final_summary, _errors, _summary = _result()
    bad = matrix.copy()
    bad.loc[bad.index[0], "action_candidate_generated"] = True
    errors = validate_tables(policy, review, bad, checks, final_summary)
    assert "task2_8j_24b6_forbidden_true:matrix:action_candidate_generated" in errors
