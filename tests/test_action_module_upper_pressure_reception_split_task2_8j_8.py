from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_6c_v2_structure_change_relation_field_tracking import (
    V2StructureChangeTrackingConfig,
)
from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_8_action_module_input_split_contract import (
    build_and_validate_action_module_input_split_contract,
    validate_action_module_input_split_contract_tables,
)


def _small_tracking_cfg():
    return V2StructureChangeTrackingConfig(steps=18, seeds=(501, 502), window_sizes=(1, 6, 12))


def test_task2_8j_8_split_contract_boundaries():
    route_contract, port_contract, separation_rules, readiness, final_summary, errors, summary = (
        build_and_validate_action_module_input_split_contract(_small_tracking_cfg())
    )

    assert errors == []
    assert not route_contract.empty
    assert not port_contract.empty
    assert not separation_rules.empty
    assert not readiness.empty
    assert not final_summary.empty
    assert summary["gt_main_map_name"] == "static_pca_7"
    assert summary["gt_main_component_count"] == 7
    assert summary["upper_pressure_generated_here"] is False
    assert summary["ot_generates_upper_pressure"] is False
    assert summary["action_module_input_object_created"] is False
    assert summary["actionmodule_called"] is False

    for table in [route_contract, port_contract, separation_rules, readiness, final_summary]:
        assert set(table["validation_only"].astype(bool)) == {True}
        assert set(table["contract_only"].astype(bool)) == {True}
        assert set(table["upper_pressure_route_separate"].astype(bool)) == {True}
        assert set(table["ot_observation_route_separate"].astype(bool)) == {True}
        assert set(table["routes_may_meet_only_inside_action_module_translation"].astype(bool)) == {True}
        assert set(table["upper_pressure_generated_here"].astype(bool)) == {False}
        assert set(table["ot_generated_from_upper_pressure"].astype(bool)) == {False}
        assert set(table["upper_pressure_rewrites_ot"].astype(bool)) == {False}
        assert set(table["ot_generates_upper_pressure"].astype(bool)) == {False}
        assert set(table["action_module_input_object_created"].astype(bool)) == {False}
        assert set(table["actionmodule_called"].astype(bool)) == {False}
        assert set(table["gt_main_map_name"].astype(str)) == {"static_pca_7"}
        assert set(table["gt_main_component_count"].astype(int)) == {7}


def test_task2_8j_8_defines_two_distinct_action_module_ports():
    route_contract, port_contract, separation_rules, readiness, final_summary, _errors, summary = (
        build_and_validate_action_module_input_split_contract(_small_tracking_cfg())
    )

    assert set(route_contract["route_name"].astype(str)) == {"upper_pressure_route", "ot_observation_map_route"}
    assert set(route_contract["action_module_port"].astype(str)) == {"upper_pressure_input_port", "ot_observation_input_port"}
    assert set(port_contract["action_module_port"].astype(str)) == {"upper_pressure_input_port", "ot_observation_input_port"}
    assert set(separation_rules["separation_status"].astype(str)) == {"pass"}
    assert bool(readiness["action_module_input_split_ready"].iloc[0]) is True
    assert int(final_summary["route_contract_count"].iloc[0]) == 2
    assert int(final_summary["action_module_port_count"].iloc[0]) == 2
    assert int(final_summary["separation_rule_count"].iloc[0]) == int(final_summary["separation_pass_count"].iloc[0])
    assert "split_contract_ready" in summary["action_module_input_split_contract_decision"]


def test_task2_8j_8_validator_detects_route_mixing():
    route_contract, port_contract, separation_rules, readiness, final_summary, _errors, _summary = (
        build_and_validate_action_module_input_split_contract(_small_tracking_cfg())
    )
    bad = route_contract.copy()
    bad.loc[bad.index[0], "ot_generates_upper_pressure"] = True
    errors = validate_action_module_input_split_contract_tables(bad, port_contract, separation_rules, readiness, final_summary)
    assert "task2_8j_8_forbidden_true:route_contract:ot_generates_upper_pressure" in errors
