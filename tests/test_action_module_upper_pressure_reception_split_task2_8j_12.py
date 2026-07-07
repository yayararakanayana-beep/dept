from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_6c_v2_structure_change_relation_field_tracking import (
    V2StructureChangeTrackingConfig,
)
from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_12_new_gt_upper_layer_revalidation import (
    MT_COMPONENTS_15,
    build_and_validate_new_gt_upper_layer_revalidation,
    validate_new_gt_upper_layer_revalidation_tables,
)


def _small_tracking_cfg():
    return V2StructureChangeTrackingConfig(steps=18, seeds=(501, 502), window_sizes=(1, 6, 12))


def test_task2_8j_12_new_gt_upper_layer_boundaries():
    gk_input, mt_table, pressure_table, safety_table, final_summary, errors, summary = (
        build_and_validate_new_gt_upper_layer_revalidation(_small_tracking_cfg())
    )

    assert errors == []
    assert not gk_input.empty
    assert not mt_table.empty
    assert not pressure_table.empty
    assert not safety_table.empty
    assert not final_summary.empty
    assert summary["gt_main_map_name"] == "static_pca_7"
    assert summary["gt_main_component_count"] == 7
    assert summary["mt_compatibility_component_count"] == 15
    assert summary["ot_route_input_used"] is False
    assert summary["game_structure_prediction_envelope_used"] is False
    assert summary["action_axis_generated"] is False
    assert summary["real_actionmodule_called"] is False

    for table in [gk_input, mt_table, pressure_table, safety_table, final_summary]:
        assert set(table["validation_only"].astype(bool)) == {True}
        assert set(table["upper_layer_revalidation_only"].astype(bool)) == {True}
        assert set(table["kt_global_summary_used"].astype(bool)) == {True}
        assert set(table["upper_pressure_route_checked"].astype(bool)) == {True}
        assert set(table["bounded_upper_pressure_required"].astype(bool)) == {True}
        assert set(table["weak_pressure_required"].astype(bool)) == {True}
        assert set(table["reversible_pressure_required"].astype(bool)) == {True}
        assert set(table["no_op_allowed_required"].astype(bool)) == {True}
        assert set(table["rollback_required"].astype(bool)) == {True}
        assert set(table["ot_route_input_used"].astype(bool)) == {False}
        assert set(table["ot_observation_map_used"].astype(bool)) == {False}
        assert set(table["game_structure_prediction_envelope_used"].astype(bool)) == {False}
        assert set(table["action_axis_generated"].astype(bool)) == {False}
        assert set(table["action_candidate_generated"].astype(bool)) == {False}
        assert set(table["real_actionmodule_called"].astype(bool)) == {False}
        assert set(table["gt_main_map_name"].astype(str)) == {"static_pca_7"}
        assert set(table["gt_main_component_count"].astype(int)) == {7}
        assert set(table["mt_compatibility_component_count"].astype(int)) == {15}


def test_task2_8j_12_projects_mt15_and_bounded_pressure():
    gk_input, mt_table, pressure_table, safety_table, final_summary, _errors, summary = (
        build_and_validate_new_gt_upper_layer_revalidation(_small_tracking_cfg())
    )

    assert int(final_summary["gk_input_phase_count"].iloc[0]) == len(gk_input)
    assert set(mt_table["mt_component_name"].astype(str)) == set(MT_COMPONENTS_15)
    assert int(final_summary["mt_component_count_per_phase"].iloc[0]) == 15
    assert set(mt_table["mt_value_finite"].astype(bool)) == {True}
    assert set(mt_table["mt_value_bounded_0_1"].astype(bool)) == {True}
    assert set(pressure_table["reversible"].astype(bool)) == {True}
    assert set(pressure_table["no_op_allowed"].astype(bool)) == {True}
    assert float(final_summary["max_bounded_pressure_magnitude"].iloc[0]) <= 0.20
    assert set(safety_table["safety_check_status"].astype(str)) == {"pass"}
    assert int(final_summary["safety_check_count"].iloc[0]) == int(final_summary["safety_check_pass_count"].iloc[0])
    assert "upper_layer_revalidated" in summary["new_gt_upper_layer_revalidation_decision"]


def test_task2_8j_12_validator_detects_ot_route_input():
    gk_input, mt_table, pressure_table, safety_table, final_summary, _errors, _summary = (
        build_and_validate_new_gt_upper_layer_revalidation(_small_tracking_cfg())
    )
    bad = gk_input.copy()
    bad.loc[bad.index[0], "ot_route_input_used"] = True
    errors = validate_new_gt_upper_layer_revalidation_tables(bad, mt_table, pressure_table, safety_table, final_summary)
    assert "task2_8j_12_forbidden_true:gk_input:ot_route_input_used" in errors
