from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_24_terrain_operator_selection_dry_run import (
    TerrainOperatorSelectionDryRunConfig,
    build_and_validate_terrain_operator_selection_dry_run,
    validate_terrain_operator_selection_dry_run_tables,
)


def test_task2_8j_24_operator_selection_boundaries():
    selection, review, checks, final_summary, errors, summary = build_and_validate_terrain_operator_selection_dry_run(
        cfg=TerrainOperatorSelectionDryRunConfig()
    )
    assert errors == []
    assert not selection.empty
    assert not review.empty
    assert not checks.empty
    assert not final_summary.empty
    assert summary["gt_main_map_name"] == "static_pca_7"
    assert summary["gt_main_component_count"] == 7
    assert summary["task23_ready"] is True
    assert summary["task23c_ready"] is True
    assert summary["terrain_operator_selected"] is True
    assert summary["terrain_operator_material_only"] is True
    assert summary["review_band_reclassified_now"] is False
    assert summary["boundary_guard_retained"] is True
    assert summary["release_rollback_audit_shaped"] is False
    assert summary["action_candidate_generated"] is False
    assert summary["action_effect_prediction_generated"] is False
    assert summary["axis_executed"] is False
    assert summary["real_actionmodule_called"] is False
    assert summary["validation_errors"] == []

    for table in [selection, review, checks, final_summary]:
        assert set(table["validation_only"].astype(bool)) == {True}
        assert set(table["dry_run_only"].astype(bool)) == {True}
        assert set(table["terrain_operator_selection_only"].astype(bool)) == {True}
        assert set(table["action_direction_material_input_used"].astype(bool)) == {True}
        assert set(table["terrain_operator_selected"].astype(bool)) == {True}
        assert set(table["terrain_operator_material_only"].astype(bool)) == {True}
        assert set(table["review_band_reclassified_now"].astype(bool)) == {False}
        assert set(table["boundary_guard_retained"].astype(bool)) == {True}
        assert set(table["release_rollback_audit_shaped"].astype(bool)) == {False}
        assert set(table["action_candidate_generated"].astype(bool)) == {False}
        assert set(table["effect_prediction_model_executed"].astype(bool)) == {False}
        assert set(table["axis_executed"].astype(bool)) == {False}
        assert set(table["real_actionmodule_called"].astype(bool)) == {False}
        assert set(table["hidden_truth_input"].astype(bool)) == {False}
        assert set(table["future_information_used"].astype(bool)) == {False}


def test_task2_8j_24_operator_selection_shape():
    selection, review, checks, final_summary, errors, summary = build_and_validate_terrain_operator_selection_dry_run()
    assert errors == []
    assert len(selection) > 0
    assert len(review) == summary["direction_material_count"]
    assert summary["operator_selection_count"] == len(selection)
    assert summary["operator_review_count"] == len(review)
    assert summary["primary_operator_family_count"] >= 3
    assert summary["review_suppressed_count"] > 0
    assert set(selection["direction_use_class"].astype(str)) == {"usable_direction_material_for_later_operator_review"}
    assert selection["selected_operator_name"].astype(str).str.len().gt(0).all()
    assert selection["secondary_operator_name"].astype(str).str.len().gt(0).all()
    assert selection["operator_selection_status"].astype(str).eq("terrain_operator_selected_as_material_only_no_candidate_no_execution").all()
    assert set(checks["check_status"].astype(str)) == {"pass"}
    assert int(final_summary["operator_check_count"].iloc[0]) == int(final_summary["operator_check_pass_count"].iloc[0])
    assert summary["terrain_operator_selection_dry_run_decision"] == "terrain_operator_selection_dry_run_ready"


def test_task2_8j_24_validator_detects_action_candidate_generation():
    selection, review, checks, final_summary, _errors, _summary = build_and_validate_terrain_operator_selection_dry_run()
    bad = selection.copy()
    bad.loc[bad.index[0], "action_candidate_generated"] = True
    errors = validate_terrain_operator_selection_dry_run_tables(bad, review, checks, final_summary)
    assert "task2_8j_24_forbidden_true:selection:action_candidate_generated" in errors
