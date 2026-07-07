from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_22b_v8_style_risk_confidence_calibration_audit import (
    V8StyleRiskConfidenceCalibrationAuditConfig,
    build_and_validate_v8_style_risk_confidence_calibration_audit,
    validate_v8_style_risk_confidence_calibration_audit_tables,
)


def test_task2_8j_22b_calibration_audit_boundaries():
    calibration, info, plan, checks, final_summary, errors, summary = build_and_validate_v8_style_risk_confidence_calibration_audit(
        cfg=V8StyleRiskConfidenceCalibrationAuditConfig()
    )
    assert errors == []
    assert not calibration.empty
    assert not info.empty
    assert not plan.empty
    assert not checks.empty
    assert not final_summary.empty
    assert summary["gt_main_map_name"] == "static_pca_7"
    assert summary["gt_main_component_count"] == 7
    assert summary["task22_ready"] is True
    assert summary["raw_risk_confidence_treated_as_uncalibrated"] is True
    assert summary["internal_calibration_possible"] is True
    assert summary["delayed_observation_required_for_empirical_calibration"] is True
    assert summary["action_direction_generated"] is False
    assert summary["terrain_operator_selected"] is False
    assert summary["action_candidate_generated"] is False
    assert summary["action_effect_prediction_generated"] is False
    assert summary["axis_executed"] is False
    assert summary["real_actionmodule_called"] is False
    assert summary["validation_errors"] == []

    for table in [calibration, info, plan, checks, final_summary]:
        assert set(table["validation_only"].astype(bool)) == {True}
        assert set(table["audit_only"].astype(bool)) == {True}
        assert set(table["v8_style_confidence_layer"].astype(bool)) == {True}
        assert set(table["coarse_macro_game_structure_only"].astype(bool)) == {True}
        assert set(table["not_high_resolution_forecast"].astype(bool)) == {True}
        assert set(table["not_long_term_forecast"].astype(bool)) == {True}
        assert set(table["risk_prediction_only"].astype(bool)) == {True}
        assert set(table["system_visible_information_only"].astype(bool)) == {True}
        assert set(table["raw_risk_confidence_treated_as_uncalibrated"].astype(bool)) == {True}
        assert set(table["internal_calibration_possible"].astype(bool)) == {True}
        assert set(table["delayed_observation_required_for_empirical_calibration"].astype(bool)) == {True}
        assert set(table["action_direction_generated"].astype(bool)) == {False}
        assert set(table["terrain_operator_selected"].astype(bool)) == {False}
        assert set(table["action_candidate_generated"].astype(bool)) == {False}
        assert set(table["effect_prediction_model_executed"].astype(bool)) == {False}
        assert set(table["axis_executed"].astype(bool)) == {False}
        assert set(table["hidden_truth_input"].astype(bool)) == {False}
        assert set(table["future_information_used"].astype(bool)) == {False}


def test_task2_8j_22b_calibration_shape_and_plan():
    calibration, info, plan, checks, final_summary, errors, summary = build_and_validate_v8_style_risk_confidence_calibration_audit()
    assert errors == []
    assert len(calibration) == 30
    assert len(info) == 6
    assert len(plan) > 0
    assert ((calibration["calibrated_risk_confidence"].astype(float) >= 0.0) & (calibration["calibrated_risk_confidence"].astype(float) <= 1.0)).all()
    assert set(calibration["calibration_band"].astype(str)).issubset({"usable_for_later_material_review", "review_before_use", "monitor_or_NO_OP"})
    assert calibration["calibration_band"].astype(str).isin(["review_before_use", "monitor_or_NO_OP"]).any()
    assert info["empirical_calibration_possible_later"].astype(bool).all()
    assert info["needs_delayed_observation"].astype(bool).any()
    assert set(checks["check_status"].astype(str)) == {"pass"}
    assert int(final_summary["calibration_check_count"].iloc[0]) == int(final_summary["calibration_check_pass_count"].iloc[0])
    assert summary["v8_style_risk_confidence_calibration_audit_decision"] == "v8_style_risk_confidence_calibration_audit_ready"
    assert summary["delayed_plan_count"] == len(plan)
    assert summary["information_review_count"] == len(info)


def test_task2_8j_22b_validator_detects_forbidden_action_direction():
    calibration, info, plan, checks, final_summary, _errors, _summary = build_and_validate_v8_style_risk_confidence_calibration_audit()
    bad = calibration.copy()
    bad.loc[bad.index[0], "action_direction_generated"] = True
    errors = validate_v8_style_risk_confidence_calibration_audit_tables(bad, info, plan, checks, final_summary)
    assert "task2_8j_22b_forbidden_true:calibration:action_direction_generated" in errors
