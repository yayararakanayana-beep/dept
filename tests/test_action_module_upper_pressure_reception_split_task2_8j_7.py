from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_6c_v2_structure_change_relation_field_tracking import (
    V2StructureChangeTrackingConfig,
)
from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_7_ot_observation_map_from_relation_field import (
    OtObservationMapConfig,
    build_and_validate_ot_observation_map_from_relation_field,
    validate_ot_observation_map_tables,
)


def _small_tracking_cfg():
    return V2StructureChangeTrackingConfig(steps=18, seeds=(501, 502), window_sizes=(1, 6, 12))


def test_task2_8j_7_ot_observation_map_boundaries():
    observation_units, route_table, final_summary, errors, summary = build_and_validate_ot_observation_map_from_relation_field(
        _small_tracking_cfg(),
        OtObservationMapConfig(),
    )

    assert errors == []
    assert not observation_units.empty
    assert not route_table.empty
    assert not final_summary.empty
    assert summary["gt_main_map_name"] == "static_pca_7"
    assert summary["gt_main_component_count"] == 7
    assert summary["upper_pressure_route_connected"] is False
    assert summary["hdept_pressure_generated"] is False
    assert summary["actionmodule_called"] is False

    for table in [observation_units, route_table, final_summary]:
        assert set(table["validation_only"].astype(bool)) == {True}
        assert set(table["observation_map_only"].astype(bool)) == {True}
        assert set(table["ot_route_connected"].astype(bool)) == {True}
        assert set(table["upper_pressure_route_connected"].astype(bool)) == {False}
        assert set(table["hdept_pressure_generated"].astype(bool)) == {False}
        assert set(table["actionmodule_called"].astype(bool)) == {False}
        assert set(table["action_input_converted"].astype(bool)) == {False}
        assert set(table["gt_main_map_name"].astype(str)) == {"static_pca_7"}
        assert set(table["gt_main_component_count"].astype(int)) == {7}


def test_task2_8j_7_observation_unit_schema_and_routes():
    observation_units, route_table, final_summary, _errors, summary = build_and_validate_ot_observation_map_from_relation_field(
        _small_tracking_cfg(),
        OtObservationMapConfig(),
    )

    kinds = set(observation_units["observation_kind"].astype(str))
    assert {"relation_change", "state_reproduction", "tracking_recovery"}.issubset(kinds)
    assert observation_units["confidence"].astype(float).between(0.0, 1.0).all()
    assert observation_units["intensity"].astype(float).between(0.0, 1.0).all()
    assert int(final_summary["observation_unit_count"].iloc[0]) == len(observation_units)
    assert int(final_summary["route_count"].iloc[0]) == len(route_table)
    assert set(route_table["route_name"].astype(str)) == {"ot_observation_map_route", "upper_pressure_route"}
    assert set(route_table["must_not_be_mixed_with_upper_pressure_inside_ot"].astype(bool)) == {True}
    assert "ot_observation_map" in summary["ot_observation_map_decision"]


def test_task2_8j_7_validator_detects_upper_pressure_route_mix():
    observation_units, route_table, final_summary, _errors, _summary = build_and_validate_ot_observation_map_from_relation_field(
        _small_tracking_cfg(),
        OtObservationMapConfig(),
    )
    bad = route_table.copy()
    bad.loc[bad.index[0], "upper_pressure_route_connected"] = True
    errors = validate_ot_observation_map_tables(observation_units, bad, final_summary)
    assert "task2_8j_7_forbidden_true:route_table:upper_pressure_route_connected" in errors
