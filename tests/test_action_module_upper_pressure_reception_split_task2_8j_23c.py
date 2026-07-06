from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_23c_review_band_reclassification_validation_plan import (
    ReviewBandReclassificationValidationPlanConfig,
    build_and_validate_review_band_reclassification_validation_plan,
    validate_review_band_reclassification_validation_plan_tables,
)


def test_task2_8j_23c_plan_boundaries():
    policy, guards, plan, candidates, checks, final_summary, errors, summary = build_and_validate_review_band_reclassification_validation_plan(
        cfg=ReviewBandReclassificationValidationPlanConfig()
    )
    assert errors == []
    assert not policy.empty
    assert not guards.empty
    assert not plan.empty
    assert not candidates.empty
    assert not checks.empty
    assert not final_summary.empty
    assert summary["gt_main_map_name"] == "static_pca_7"
    assert summary["gt_main_component_count"] == 7
    assert summary["task23b_ready"] is True
    assert summary["review_band_may_be_reclassified_after_validation"] is True
    assert summary["boundary_guard_may_not_be_removed_by_reclassification"] is True
    assert summary["no_reclassification_performed_now"] is True
    assert summary["no_threshold_update_performed"] is True
    assert summary["new_action_direction_generated"] is False
    assert summary["terrain_operator_selected"] is False
    assert summary["action_candidate_generated"] is False
    assert summary["action_effect_prediction_generated"] is False
    assert summary["axis_executed"] is False
    assert summary["real_actionmodule_called"] is False
    assert summary["validation_errors"] == []

    for table in [policy, guards, plan, candidates, checks, final_summary]:
        assert set(table["validation_only"].astype(bool)) == {True}
        assert set(table["plan_only"].astype(bool)) == {True}
        assert set(table["contract_only"].astype(bool)) == {True}
        assert set(table["review_band_reclassification_plan"].astype(bool)) == {True}
        assert set(table["boundary_guard_retained"].astype(bool)) == {True}
        assert set(table["no_reclassification_performed_now"].astype(bool)) == {True}
        assert set(table["no_threshold_update_performed"].astype(bool)) == {True}
        assert set(table["threshold_values_are_provisional"].astype(bool)) == {True}
        assert set(table["threshold_revision_requires_validation"].astype(bool)) == {True}
        assert set(table["safety_rules_fixed"].astype(bool)) == {True}
        assert set(table["decision_thresholds_revisable"].astype(bool)) == {True}
        assert set(table["review_band_may_be_reclassified_after_validation"].astype(bool)) == {True}
        assert set(table["boundary_guard_may_not_be_removed_by_reclassification"].astype(bool)) == {True}
        assert set(table["new_action_direction_generated"].astype(bool)) == {False}
        assert set(table["review_band_reclassified_now"].astype(bool)) == {False}
        assert set(table["terrain_operator_selected"].astype(bool)) == {False}
        assert set(table["action_candidate_generated"].astype(bool)) == {False}
        assert set(table["effect_prediction_model_executed"].astype(bool)) == {False}
        assert set(table["axis_executed"].astype(bool)) == {False}
        assert set(table["real_actionmodule_called"].astype(bool)) == {False}
        assert set(table["hidden_truth_input"].astype(bool)) == {False}
        assert set(table["future_information_used"].astype(bool)) == {False}


def test_task2_8j_23c_candidate_and_guard_shape():
    policy, guards, plan, candidates, checks, final_summary, errors, summary = build_and_validate_review_band_reclassification_validation_plan()
    assert errors == []
    assert summary["candidate_count"] == len(candidates)
    assert summary["review_band_candidate_count"] == len(candidates)
    assert summary["boundary_guard_retained_count"] == len(candidates)
    assert candidates["candidate_status"].astype(str).eq("candidate_for_validation_not_reclassified_now").all()
    assert candidates["boundary_guard_retention"].astype(str).str.contains("guard").all()
    assert guards["forbidden_after_reclassification"].astype(str).str.len().gt(0).all()
    assert plan["plan_status"].astype(str).str.contains("no_").any()
    assert set(checks["check_status"].astype(str)) == {"pass"}
    assert int(final_summary["plan_check_count"].iloc[0]) == int(final_summary["plan_check_pass_count"].iloc[0])
    assert summary["review_band_reclassification_validation_plan_decision"] == "review_band_reclassification_validation_plan_ready"


def test_task2_8j_23c_validator_detects_reclassification_attempt():
    policy, guards, plan, candidates, checks, final_summary, _errors, _summary = build_and_validate_review_band_reclassification_validation_plan()
    bad = candidates.copy()
    bad.loc[bad.index[0], "review_band_reclassified_now"] = True
    errors = validate_review_band_reclassification_validation_plan_tables(policy, guards, plan, bad, checks, final_summary)
    assert "task2_8j_23c_forbidden_true:candidates:review_band_reclassified_now" in errors
    assert "task2_8j_23c_reclassification_attempted" in errors
