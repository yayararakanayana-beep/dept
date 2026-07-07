from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_24c0_actionmodule_information_intake_bridge import (
    build_and_validate_actionmodule_information_intake_bridge,
    validate_tables,
)

_CACHE = None


def _result():
    global _CACHE
    if _CACHE is None:
        _CACHE = build_and_validate_actionmodule_information_intake_bridge()
    return _CACHE


def test_task2_8j_24c0_information_intake_bridge_ready():
    contract, channels, packets, checks, final_summary, errors, summary = _result()
    assert errors == []
    assert not contract.empty
    assert not channels.empty
    assert not packets.empty
    assert not checks.empty
    assert not final_summary.empty
    assert summary["actionmodule_information_intake_bridge_decision"] == "actionmodule_information_intake_bridge_ready_non_execution"
    assert summary["intake_packet_count"] == 5
    assert summary["stable_evidence_risk_count"] == 3
    assert summary["non_stable_evidence_risk_count"] == 2
    assert summary["risk_names_carried"] == "boundary_fragile,oscillation,relation_lock,resource_pressure,reversibility_loss"
    assert summary["validation_errors"] == []
    assert set(checks["check_status"].astype(str)) == {"pass"}


def test_task2_8j_24c0_channels_are_correctly_separated():
    _contract, channels, packets, _checks, _final_summary, errors, _summary = _result()
    assert errors == []
    channel_status = dict(zip(channels["input_channel"].astype(str), channels["channel_status"].astype(str)))
    used_now = dict(zip(channels["input_channel"].astype(str), channels["used_now"].astype(bool)))
    assert channel_status["ot_information"] == "primary_current_route"
    assert used_now["ot_information"] is True
    assert channel_status["v8_local_observation_information"] == "auxiliary_current_route"
    assert used_now["v8_local_observation_information"] is True
    assert channel_status["upper_pressure_information"] == "reserved_not_used_now"
    assert used_now["upper_pressure_information"] is False
    assert channel_status["exploration_axis_information"] == "deferred_not_used_now"
    assert used_now["exploration_axis_information"] is False
    assert packets["upper_pressure_channel_status"].astype(str).eq("reserved_not_used_now").all()
    assert packets["exploration_axis_channel_status"].astype(str).eq("deferred_not_used_now").all()


def test_task2_8j_24c0_carries_risk_evidence_without_admission_lock():
    _contract, _channels, packets, _checks, _final_summary, errors, _summary = _result()
    assert errors == []
    assert set(packets["risk_name"].astype(str)) == {
        "relation_lock",
        "oscillation",
        "reversibility_loss",
        "boundary_fragile",
        "resource_pressure",
    }
    assert packets["risk_evidence_status_is_mutable"].astype(bool).all()
    assert packets["candidate_admission_status"].astype(str).eq("not_evaluated_at_intake").all()
    assert packets.loc[packets["risk_name"] == "boundary_fragile", "risk_evidence_status"].astype(str).iloc[0] == "needs_more_prediction_precision_before_action_admission"
    assert packets.loc[packets["risk_name"] == "resource_pressure", "risk_evidence_status"].astype(str).iloc[0] == "currently_noop_preferred_but_possibility_retained_for_redesign"


def test_task2_8j_24c0_does_not_fix_action_or_execute():
    _contract, _channels, packets, _checks, _final_summary, errors, _summary = _result()
    assert errors == []
    forbidden_action_columns = [
        "action_direction_determined",
        "action_operator_family_fixed",
        "action_type_fixed",
        "action_strength_fixed",
        "action_duration_fixed",
        "action_timing_fixed",
        "simulation_prediction_performed",
        "noop_comparison_performed",
        "tail_loss_review_performed",
        "action_candidate_generated",
        "concrete_action_generated",
        "actionframe_created",
        "real_actionmodule_called",
        "axis_executed",
        "canonical_write_performed",
        "gk_writeback_performed",
        "ot_writeback_performed",
    ]
    assert not packets[forbidden_action_columns].astype(bool).any().any()
    assert packets["actionmodule_intake_port"].astype(str).eq("information_intake_port_non_execution").all()


def test_task2_8j_24c0_validator_blocks_accidental_action_fixing():
    contract, channels, packets, checks, final_summary, _errors, _summary = _result()
    bad = packets.copy()
    bad.loc[bad.index[0], "action_type_fixed"] = True
    errors = validate_tables(contract, channels, bad, checks, final_summary)
    assert "task2_8j_24c0_forbidden_true_failed:packets:action_type_fixed" in errors


def test_task2_8j_24c0_validator_blocks_premature_admission():
    contract, channels, packets, checks, final_summary, _errors, _summary = _result()
    bad = packets.copy()
    bad.loc[bad.index[0], "candidate_admission_status"] = "admitted"
    errors = validate_tables(contract, channels, bad, checks, final_summary)
    assert "task2_8j_24c0_candidate_admission_evaluated_too_early" in errors
