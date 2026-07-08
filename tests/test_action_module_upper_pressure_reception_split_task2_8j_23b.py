from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_23b_review_only_cause_audit_direction_usability_threshold_sensitivity import (
    ReviewOnlyCauseAuditThresholdSensitivityConfig,
    build_and_validate_review_only_cause_audit_threshold_sensitivity,
    validate_review_only_cause_audit_threshold_sensitivity_tables,
)


def test_task2_8j_23b_audit_boundaries():
    cause_audit, cause_summary, sensitivity, checks, final_summary, errors, summary = build_and_validate_review_only_cause_audit_threshold_sensitivity(
        cfg=ReviewOnlyCauseAuditThresholdSensitivityConfig()
    )
    assert errors == []
    assert not cause_audit.empty
    assert not cause_summary.empty
    assert not sensitivity.empty
    assert not checks.empty
    assert not final_summary.empty
    assert summary["gt_main_map_name"] == "static_pca_7"
    assert summary["gt_main_component_count"] == 7
    assert summary["task23_ready"] is True
    assert summary["task22b_ready"] is True
    assert summary["no_threshold_update_performed"] is True
    assert summary["threshold_values_are_provisional"] is True
    assert summary["threshold_revision_requires_validation"] is True
    assert summary["new_action_direction_generated"] is False
    assert summary["terrain_operator_selected"] is False
    assert summary["action_candidate_generated"] is False
    assert summary["action_effect_prediction_generated"] is False
    assert summary["axis_executed"] is False
    assert summary["real_actionmodule_called"] is False
    assert summary["validation_errors"] == []

    for table in [cause_audit, cause_summary, sensitivity, checks, final_summary]:
        assert set(table["validation_only"].astype(bool)) == {True}
        assert set(table["audit_only"].astype(bool)) == {True}
        assert set(table["sensitivity_only"].astype(bool)) == {True}
        assert set(table["review_only_cause_audit"].astype(bool)) == {True}
        assert set(table["direction_usability_threshold_sensitivity"].astype(bool)) == {True}
        assert set(table["no_threshold_update_performed"].astype(bool)) == {True}
        assert set(table["threshold_values_are_provisional"].astype(bool)) == {True}
        assert set(table["threshold_revision_requires_validation"].astype(bool)) == {True}
        assert set(table["safety_rules_fixed"].astype(bool)) == {True}
        assert set(table["decision_thresholds_revisable"].astype(bool)) == {True}
        assert set(table["action_direction_material_input_used"].astype(bool)) == {True}
        assert set(table["new_action_direction_generated"].astype(bool)) == {False}
        assert set(table["terrain_operator_selected"].astype(bool)) == {False}
        assert set(table["action_candidate_generated"].astype(bool)) == {False}
        assert set(table["effect_prediction_model_executed"].astype(bool)) == {False}
        assert set(table["axis_executed"].astype(bool)) == {False}
        assert set(table["real_actionmodule_called"].astype(bool)) == {False}
        assert set(table["hidden_truth_input"].astype(bool)) == {False}
        assert set(table["future_information_used"].astype(bool)) == {False}


def test_task2_8j_23b_cause_and_sensitivity_shape():
    cause_audit, cause_summary, sensitivity, checks, final_summary, errors, summary = build_and_validate_review_only_cause_audit_threshold_sensitivity()
    assert errors == []
    assert len(cause_audit) == summary["review_only_direction_count"]
    assert summary["direction_material_count"] >= summary["review_only_direction_count"]
    assert summary["cause_summary_count"] == len(cause_summary)
    assert summary["sensitivity_row_count"] == len(sensitivity)
    assert summary["positive_sensitivity_row_count"] > 0
    assert summary["threshold_update_candidate_count"] == summary["positive_sensitivity_row_count"]
    assert summary["max_eligible_material_count"] > 0
    assert sensitivity["requires_validation_before_update"].astype(bool).all()
    assert not sensitivity["may_update_threshold_now"].astype(bool).any()
    assert cause_audit["would_need_validation_for_usability"].astype(bool).all()
    assert cause_audit["review_only_primary_cause"].astype(str).str.len().gt(0).all()
    assert set(checks["check_status"].astype(str)) == {"pass"}
    assert int(final_summary["audit_check_count"].iloc[0]) == int(final_summary["audit_check_pass_count"].iloc[0])
    assert summary["review_only_cause_audit_direction_usability_threshold_sensitivity_decision"] == "review_only_cause_audit_direction_usability_threshold_sensitivity_ready"


def test_task2_8j_23b_validator_detects_threshold_update_attempt():
    cause_audit, cause_summary, sensitivity, checks, final_summary, _errors, _summary = build_and_validate_review_only_cause_audit_threshold_sensitivity()
    bad = sensitivity.copy()
    bad.loc[bad.index[0], "may_update_threshold_now"] = True
    errors = validate_review_only_cause_audit_threshold_sensitivity_tables(cause_audit, cause_summary, bad, checks, final_summary)
    assert "task2_8j_23b_threshold_update_attempted" in errors
