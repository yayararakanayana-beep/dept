from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_23_risk_to_action_direction_shaping_dry_run import (
    RiskToActionDirectionShapingDryRunConfig,
    build_and_validate_risk_to_action_direction_shaping_dry_run,
    validate_risk_to_action_direction_shaping_dry_run_tables,
)


def test_task2_8j_23_direction_shaping_boundaries():
    material, review, checks, final_summary, errors, summary = build_and_validate_risk_to_action_direction_shaping_dry_run(
        cfg=RiskToActionDirectionShapingDryRunConfig()
    )
    assert errors == []
    assert not material.empty
    assert not review.empty
    assert not checks.empty
    assert not final_summary.empty
    assert summary["gt_main_map_name"] == "static_pca_7"
    assert summary["gt_main_component_count"] == 7
    assert summary["task22b_ready"] is True
    assert summary["task22c_ready"] is True
    assert summary["action_direction_generated"] is True
    assert summary["action_direction_material_only"] is True
    assert summary["terrain_operator_selected"] is False
    assert summary["release_rollback_audit_shaped"] is False
    assert summary["action_candidate_generated"] is False
    assert summary["action_effect_prediction_generated"] is False
    assert summary["axis_executed"] is False
    assert summary["real_actionmodule_called"] is False
    assert summary["threshold_values_are_provisional"] is True
    assert summary["validation_errors"] == []

    for table in [material, review, checks, final_summary]:
        assert set(table["validation_only"].astype(bool)) == {True}
        assert set(table["dry_run_only"].astype(bool)) == {True}
        assert set(table["risk_to_action_direction_shaping_only"].astype(bool)) == {True}
        assert set(table["action_direction_generated"].astype(bool)) == {True}
        assert set(table["action_direction_material_only"].astype(bool)) == {True}
        assert set(table["coarse_macro_game_structure_only"].astype(bool)) == {True}
        assert set(table["not_high_resolution_forecast"].astype(bool)) == {True}
        assert set(table["not_long_term_forecast"].astype(bool)) == {True}
        assert set(table["risk_prediction_only"].astype(bool)) == {True}
        assert set(table["system_visible_information_only"].astype(bool)) == {True}
        assert set(table["safety_rules_fixed"].astype(bool)) == {True}
        assert set(table["decision_thresholds_revisable"].astype(bool)) == {True}
        assert set(table["threshold_values_are_provisional"].astype(bool)) == {True}
        assert set(table["terrain_operator_selected"].astype(bool)) == {False}
        assert set(table["release_rollback_audit_shaped"].astype(bool)) == {False}
        assert set(table["action_candidate_generated"].astype(bool)) == {False}
        assert set(table["effect_prediction_model_executed"].astype(bool)) == {False}
        assert set(table["axis_executed"].astype(bool)) == {False}
        assert set(table["real_actionmodule_called"].astype(bool)) == {False}
        assert set(table["hidden_truth_input"].astype(bool)) == {False}
        assert set(table["future_information_used"].astype(bool)) == {False}


def test_task2_8j_23_material_shape_and_review_suppression():
    material, review, checks, final_summary, errors, summary = build_and_validate_risk_to_action_direction_shaping_dry_run()
    assert errors == []
    assert len(material) > 0
    assert len(review) == summary["calibration_row_count"]
    assert summary["direction_material_count"] == len(material)
    assert summary["review_row_count"] == len(review)
    assert summary["monitor_suppressed_count"] > 0
    assert summary["risk_family_count"] >= 3
    assert set(material["calibration_band"].astype(str)).issubset({"usable_for_later_material_review", "review_before_use"})
    assert "monitor_or_NO_OP" not in set(material["calibration_band"].astype(str))
    assert material["action_direction_family"].astype(str).str.len().gt(0).all()
    assert material["primary_action_direction"].astype(str).str.len().gt(0).all()
    assert material["forbidden_action_direction"].astype(str).str.len().gt(0).all()
    assert set(checks["check_status"].astype(str)) == {"pass"}
    assert int(final_summary["direction_check_count"].iloc[0]) == int(final_summary["direction_check_pass_count"].iloc[0])
    assert summary["risk_to_action_direction_shaping_dry_run_decision"] == "risk_to_action_direction_shaping_dry_run_ready"


def test_task2_8j_23_validator_detects_operator_selection():
    material, review, checks, final_summary, _errors, _summary = build_and_validate_risk_to_action_direction_shaping_dry_run()
    bad = material.copy()
    bad.loc[bad.index[0], "terrain_operator_selected"] = True
    errors = validate_risk_to_action_direction_shaping_dry_run_tables(bad, review, checks, final_summary)
    assert "task2_8j_23_forbidden_true:material:terrain_operator_selected" in errors
