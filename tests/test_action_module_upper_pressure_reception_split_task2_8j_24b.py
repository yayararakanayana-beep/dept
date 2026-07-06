from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_24b_v2_sandbox_action_material_timing_validation import (
    V2SandboxActionMaterialTimingValidationConfig,
    build_and_validate_v2_sandbox_action_material_timing_validation,
    validate_v2_sandbox_action_material_timing_validation_tables,
)


def test_task2_8j_24b_boundaries():
    sweep, noop, step_summary, tradeoff, threshold, checks, final_summary, errors, summary = build_and_validate_v2_sandbox_action_material_timing_validation(
        cfg=V2SandboxActionMaterialTimingValidationConfig()
    )
    assert errors == []
    assert not sweep.empty
    assert not noop.empty
    assert not step_summary.empty
    assert not tradeoff.empty
    assert not threshold.empty
    assert not checks.empty
    assert not final_summary.empty
    assert summary["gt_main_map_name"] == "static_pca_7"
    assert summary["gt_main_component_count"] == 7
    assert summary["task24_ready"] is True
    assert summary["v2_window_used_as_auxiliary_observation"] is True
    assert summary["v2_window_not_runtime_oracle"] is True
    assert summary["relative_expected_value_proxy_generated"] is True
    assert summary["sandbox_action_material_applied"] is True
    assert summary["sandbox_only_action"] is True
    assert summary["no_threshold_update_performed"] is True
    assert summary["action_candidate_generated"] is False
    assert summary["action_effect_prediction_generated"] is False
    assert summary["real_actionmodule_called"] is False
    assert summary["axis_executed"] is False
    assert summary["validation_errors"] == []

    for table in [sweep, noop, step_summary, tradeoff, threshold, checks, final_summary]:
        assert set(table["validation_only"].astype(bool)) == {True}
        assert set(table["dry_run_only"].astype(bool)) == {True}
        assert set(table["v2_sandbox_validation_only"].astype(bool)) == {True}
        assert set(table["v2_window_used_as_auxiliary_observation"].astype(bool)) == {True}
        assert set(table["v2_window_not_runtime_oracle"].astype(bool)) == {True}
        assert set(table["NO_OP_comparison_required"].astype(bool)) == {True}
        assert set(table["step_count_sensitivity"].astype(bool)) == {True}
        assert set(table["adoption_threshold_tradeoff_audit"].astype(bool)) == {True}
        assert set(table["relative_expected_value_proxy_generated"].astype(bool)) == {True}
        assert set(table["sandbox_action_material_applied"].astype(bool)) == {True}
        assert set(table["sandbox_only_action"].astype(bool)) == {True}
        assert set(table["no_threshold_update_performed"].astype(bool)) == {True}
        assert set(table["overfit_to_v2_forbidden"].astype(bool)) == {True}
        assert set(table["release_rollback_audit_shaped"].astype(bool)) == {False}
        assert set(table["action_candidate_generated"].astype(bool)) == {False}
        assert set(table["effect_prediction_model_executed"].astype(bool)) == {False}
        assert set(table["real_actionmodule_called"].astype(bool)) == {False}
        assert set(table["axis_executed"].astype(bool)) == {False}
        assert set(table["hidden_truth_input"].astype(bool)) == {False}
        assert set(table["future_information_used"].astype(bool)) == {False}


def test_task2_8j_24b_sweep_and_threshold_shape():
    sweep, noop, step_summary, tradeoff, threshold, checks, final_summary, errors, summary = build_and_validate_v2_sandbox_action_material_timing_validation()
    assert errors == []
    assert summary["operator_selection_count"] > 0
    assert summary["sweep_row_count"] == summary["operator_selection_count"] * 6
    assert summary["NO_OP_outcome_count"] == summary["operator_selection_count"]
    assert summary["tradeoff_row_count"] == summary["operator_selection_count"]
    assert summary["step_summary_count"] == 6
    assert summary["threshold_audit_count"] > 0
    assert summary["positive_ev_row_count"] > 0
    assert summary["best_action_beats_NO_OP_count"] > 0
    assert sweep["relative_expected_value_proxy"].astype(float).notna().all()
    assert sweep["timing_class"].astype(str).str.len().gt(0).all()
    assert threshold["requires_validation_before_update"].astype(bool).all()
    assert not threshold["may_update_threshold_now"].astype(bool).any()
    assert set(checks["check_status"].astype(str)) == {"pass"}
    assert int(final_summary["validation_check_count"].iloc[0]) == int(final_summary["validation_check_pass_count"].iloc[0])
    assert summary["v2_sandbox_action_material_timing_validation_decision"] == "v2_sandbox_action_material_timing_validation_ready"


def test_task2_8j_24b_validator_detects_action_candidate_generation():
    sweep, noop, step_summary, tradeoff, threshold, checks, final_summary, _errors, _summary = build_and_validate_v2_sandbox_action_material_timing_validation()
    bad = sweep.copy()
    bad.loc[bad.index[0], "action_candidate_generated"] = True
    errors = validate_v2_sandbox_action_material_timing_validation_tables(bad, noop, step_summary, tradeoff, threshold, checks, final_summary)
    assert "task2_8j_24b_forbidden_true:sweep:action_candidate_generated" in errors
