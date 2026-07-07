from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_6c_v2_structure_change_relation_field_tracking import (
    V2StructureChangeTrackingConfig,
    build_and_validate_v2_structure_change_relation_field_tracking,
    validate_v2_structure_change_tracking_tables,
)


def _small_cfg():
    return V2StructureChangeTrackingConfig(steps=18, seeds=(501, 502), window_sizes=(1, 6, 12))


def test_task2_8j_6c_boundaries_and_outputs():
    phase_table, edge_change, stale_updated, final_summary, errors, summary = (
        build_and_validate_v2_structure_change_relation_field_tracking(_small_cfg())
    )

    assert errors == []
    assert not phase_table.empty
    assert not edge_change.empty
    assert not stale_updated.empty
    assert not final_summary.empty
    assert summary["gt_main_map_name"] == "static_pca_7"
    assert summary["gt_main_component_count"] == 7
    assert summary["phase_count"] == 3

    for table in [phase_table, edge_change, stale_updated, final_summary]:
        assert set(table["validation_only"].astype(bool)) == {True}
        assert set(table["incomplete_observation_assumption"].astype(bool)) == {True}
        assert set(table["observable_v2_state_only"].astype(bool)) == {True}
        assert set(table["relation_field_update_allowed"].astype(bool)) == {True}
        assert set(table["gt_main_map_name"].astype(str)) == {"static_pca_7"}
        assert set(table["gt_main_component_count"].astype(int)) == {7}
        for col in [
            "runtime_policy_input",
            "fullspec_runtime_connected",
            "upper_pressure_connected",
            "action_frame_created",
            "actionmodule_called",
            "canonical_write_performed",
            "gk_writeback_performed",
            "ot_writeback_performed",
            "effective_dimension_refit_performed",
            "axis_mutation_performed",
            "residual_auxiliary_injected_into_gt_main",
            "action_weight_converted",
            "hidden_truth_input",
            "future_information_used",
        ]:
            assert set(table[col].astype(bool)) == {False}


def test_task2_8j_6c_detects_structure_change_without_axis_mutation():
    phase_table, edge_change, stale_updated, final_summary, _errors, summary = (
        build_and_validate_v2_structure_change_relation_field_tracking(_small_cfg())
    )

    assert int(final_summary["phase_count"].iloc[0]) == 3
    assert int(final_summary["edge_comparison_count"].iloc[0]) > 0
    assert int(final_summary["changed_edge_count"].iloc[0]) >= 0
    assert phase_table["mean_state_event_accuracy"].astype(float).between(0.0, 1.0).all()
    assert stale_updated["updated_mean_state_event_accuracy"].astype(float).between(0.0, 1.0).all()
    assert "relation_field" in str(final_summary["v2_structure_tracking_decision"].iloc[0])
    assert "relation_field" in summary["v2_structure_tracking_decision"]


def test_task2_8j_6c_validator_detects_hidden_truth():
    phase_table, edge_change, stale_updated, final_summary, _errors, _summary = (
        build_and_validate_v2_structure_change_relation_field_tracking(_small_cfg())
    )
    bad = phase_table.copy()
    bad.loc[bad.index[0], "hidden_truth_input"] = True

    errors = validate_v2_structure_change_tracking_tables(bad, edge_change, stale_updated, final_summary)
    assert "task2_8j_6c_forbidden_true:phase_table:hidden_truth_input" in errors
