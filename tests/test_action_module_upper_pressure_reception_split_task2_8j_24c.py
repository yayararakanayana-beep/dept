from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_24c_provisional_action_module_design_lock import (
    build_and_validate_provisional_action_module_design_lock,
    validate_tables,
)

_CACHE = None


def _result():
    global _CACHE
    if _CACHE is None:
        _CACHE = build_and_validate_provisional_action_module_design_lock()
    return _CACHE


def test_task2_8j_24c_provisional_design_lock_ready():
    design, policy, gates, fallbacks, exclusions, checks, final_summary, errors, summary = _result()
    assert errors == []
    assert not design.empty
    assert not policy.empty
    assert not gates.empty
    assert not fallbacks.empty
    assert not exclusions.empty
    assert not checks.empty
    assert not final_summary.empty
    assert summary["source_task24b6_ready"] is True
    assert summary["provisional_policy_rule_count"] == 3
    assert summary["excluded_rule_count"] == 2
    assert summary["ready_risk_scope"] == "relation_lock,oscillation,reversibility_loss"
    assert summary["excluded_risk_scope"] == "boundary_fragile,resource_pressure"
    assert summary["primary_intensity_schedule"] == "fixed_medium"
    assert summary["primary_wait_window"] == "wait_0_2"
    assert summary["threshold_freeze_allowed_now"] is False
    assert summary["deployment_ready_claimed"] is False
    assert summary["canonical_write_performed"] is False
    assert summary["real_actionmodule_called"] is False
    assert summary["axis_executed"] is False
    assert summary["validation_errors"] == []
    assert summary["task24c_provisional_design_decision"] == "provisional_action_module_design_lock_ready"
    assert set(checks["check_status"].astype(str)) == {"pass"}


def test_task2_8j_24c_policy_scope_and_fallbacks():
    design, policy, gates, fallbacks, exclusions, checks, final_summary, errors, summary = _result()
    assert errors == []
    assert set(policy["risk_name"].astype(str)) == {"relation_lock", "oscillation", "reversibility_loss"}
    assert set(policy["intensity_schedule"].astype(str)) == {"fixed_medium"}
    assert set(policy["wait_window"].astype(str)) == {"wait_0_2"}
    assert set(exclusions["risk_name"].astype(str)) == {"boundary_fragile", "resource_pressure"}
    assert fallbacks["fallback_action"].astype(str).str.contains("NO_OP").all()
    assert policy["runtime_forbidden_inputs"].astype(str).str.contains("v2_future").all()
    assert not design["deployment_ready_claimed"].astype(bool).any()


def test_task2_8j_24c_validator_blocks_resource_admission():
    design, policy, gates, fallbacks, exclusions, checks, final_summary, _errors, _summary = _result()
    bad = policy.copy()
    bad.loc[bad.index[0], "risk_name"] = "resource_pressure"
    errors = validate_tables(design, bad, gates, fallbacks, exclusions, checks, final_summary)
    assert "task2_8j_24c_unallowed_policy_risk:resource_pressure" in errors
