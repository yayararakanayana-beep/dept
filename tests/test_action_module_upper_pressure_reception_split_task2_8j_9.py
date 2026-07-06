from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_6c_v2_structure_change_relation_field_tracking import (
    V2StructureChangeTrackingConfig,
)
from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_9_two_route_reception_dry_run import (
    build_and_validate_two_route_reception_dry_run,
    validate_two_route_reception_dry_run_tables,
)


def _small_tracking_cfg():
    return V2StructureChangeTrackingConfig(steps=18, seeds=(501, 502), window_sizes=(1, 6, 12))


def test_task2_8j_9_two_route_reception_dry_run_boundaries():
    envelopes, checks, receipt, final_summary, errors, summary = build_and_validate_two_route_reception_dry_run(
        _small_tracking_cfg()
    )

    assert errors == []
    assert not envelopes.empty
    assert not checks.empty
    assert not receipt.empty
    assert not final_summary.empty
    assert summary["gt_main_map_name"] == "static_pca_7"
    assert summary["gt_main_component_count"] == 7
    assert summary["real_actionmodule_called"] is False
    assert summary["action_translation_performed"] is False

    for table in [envelopes, checks, receipt, final_summary]:
        assert set(table["validation_only"].astype(bool)) == {True}
        assert set(table["dry_run_only"].astype(bool)) == {True}
        assert set(table["two_route_reception_envelope_created"].astype(bool)) == {True}
        assert set(table["routes_kept_separate"].astype(bool)) == {True}
        assert set(table["upper_pressure_generated_here"].astype(bool)) == {False}
        assert set(table["ot_generates_upper_pressure"].astype(bool)) == {False}
        assert set(table["action_translation_performed"].astype(bool)) == {False}
        assert set(table["real_actionmodule_called"].astype(bool)) == {False}
        assert set(table["actionmodule_called"].astype(bool)) == {False}
        assert set(table["gt_main_map_name"].astype(str)) == {"static_pca_7"}
        assert set(table["gt_main_component_count"].astype(int)) == {7}


def test_task2_8j_9_receives_two_routes_without_translation():
    envelopes, checks, receipt, final_summary, _errors, summary = build_and_validate_two_route_reception_dry_run(
        _small_tracking_cfg()
    )

    assert set(envelopes["route_name"].astype(str)) == {"upper_pressure_route", "ot_observation_map_route"}
    assert set(envelopes["action_module_port"].astype(str)) == {"upper_pressure_input_port", "ot_observation_input_port"}
    assert set(envelopes["payload_is_contract_stub"].astype(bool)) == {True}
    assert set(envelopes["payload_required_fields_present"].astype(bool)) == {True}
    assert set(checks["check_status"].astype(str)) == {"pass"}
    assert set(receipt["receipt_status"].astype(str)) == {"two_route_dry_run_reception_accepted_without_translation"}
    assert int(final_summary["envelope_count"].iloc[0]) == 2
    assert int(final_summary["received_route_count"].iloc[0]) == 2
    assert int(final_summary["received_port_count"].iloc[0]) == 2
    assert int(final_summary["separate_port_count"].iloc[0]) == 2
    assert "dry_run_contract_passed" in summary["two_route_reception_dry_run_decision"]


def test_task2_8j_9_validator_detects_real_actionmodule_call():
    envelopes, checks, receipt, final_summary, _errors, _summary = build_and_validate_two_route_reception_dry_run(
        _small_tracking_cfg()
    )
    bad = envelopes.copy()
    bad.loc[bad.index[0], "real_actionmodule_called"] = True
    errors = validate_two_route_reception_dry_run_tables(bad, checks, receipt, final_summary)
    assert "task2_8j_9_forbidden_true:envelopes:real_actionmodule_called" in errors
