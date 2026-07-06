from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_20_v2_terrain_action_parameter_sweep_dry_run import (
    V2TerrainActionParameterSweepDryRunConfig,
    build_and_validate_v2_terrain_action_parameter_sweep_dry_run,
    validate_v2_terrain_action_parameter_sweep_dry_run_tables,
)


def test_task2_8j_20_parameter_sweep_dry_run_boundaries():
    terrain_states, sweep, operator_summary, checks, final_summary, errors, summary = build_and_validate_v2_terrain_action_parameter_sweep_dry_run(
        cfg=V2TerrainActionParameterSweepDryRunConfig(max_rows_per_operator=3)
    )

    assert errors == []
    assert not terrain_states.empty
    assert not sweep.empty
    assert not operator_summary.empty
    assert not checks.empty
    assert not final_summary.empty
    assert summary["gt_main_map_name"] == "static_pca_7"
    assert summary["gt_main_component_count"] == 7
    assert summary["task19_ready"] is True
    assert summary["sandbox_executed"] is False
    assert summary["terrain_operator_applied"] is False
    assert summary["action_candidate_generated"] is False
    assert summary["action_effect_prediction_generated"] is False
    assert summary["effect_prediction_model_executed"] is False
    assert summary["concrete_action_generated"] is False
    assert summary["axis_executed"] is False
    assert summary["real_actionmodule_called"] is False
    assert summary["validation_errors"] == []

    for table in [terrain_states, sweep, operator_summary, checks, final_summary]:
        assert set(table["validation_only"].astype(bool)) == {True}
        assert set(table["sweep_dry_run_only"].astype(bool)) == {True}
        assert set(table["readiness_priority_diagnostic_only"].astype(bool)) == {True}
        assert set(table["v2_terrain_action_sandbox_only"].astype(bool)) == {True}
        assert set(table["semantic_recipe_primary_key_forbidden"].astype(bool)) == {True}
        assert set(table["terrain_information_primary_required"].astype(bool)) == {True}
        assert set(table["risk_label_used_only_for_evaluation"].astype(bool)) == {True}
        assert set(table["v2_oracle_results_hint_only"].astype(bool)) == {True}
        assert set(table["no_op_preserved"].astype(bool)) == {True}
        assert set(table["direction_selection_required"].astype(bool)) == {True}
        assert set(table["state_dependence_required"].astype(bool)) == {True}
        assert set(table["immediate_release_required"].astype(bool)) == {True}
        assert set(table["rollback_required"].astype(bool)) == {True}
        assert set(table["audit_required"].astype(bool)) == {True}
        assert set(table["sandbox_executed"].astype(bool)) == {False}
        assert set(table["terrain_operator_applied"].astype(bool)) == {False}
        assert set(table["action_candidate_generated"].astype(bool)) == {False}
        assert set(table["effect_prediction_model_executed"].astype(bool)) == {False}
        assert set(table["axis_executed"].astype(bool)) == {False}
        assert set(table["hidden_truth_input"].astype(bool)) == {False}
        assert set(table["future_information_used"].astype(bool)) == {False}


def test_task2_8j_20_sweep_content_and_coverage():
    terrain_states, sweep, operator_summary, checks, final_summary, errors, summary = build_and_validate_v2_terrain_action_parameter_sweep_dry_run(
        cfg=V2TerrainActionParameterSweepDryRunConfig(max_rows_per_operator=4)
    )
    assert errors == []
    assert len(terrain_states) >= 6
    assert len(operator_summary) >= 7
    assert len(sweep) == 6 * 7 * 4
    assert sweep["dry_run_priority_score"].astype(float).between(0.0, 1.0).all()
    assert set(sweep["dry_run_status"].astype(str)) == {"dry_run_diagnostic_only_not_executed"}
    assert sweep["no_op_comparison_readiness"].astype(float).ge(1.0).all()
    assert set(checks["check_status"].astype(str)) == {"pass"}
    assert int(final_summary["dry_run_row_count"].iloc[0]) == len(sweep)
    assert int(final_summary["operator_summary_count"].iloc[0]) == len(operator_summary)
    assert int(final_summary["sweep_check_count"].iloc[0]) == int(final_summary["sweep_check_pass_count"].iloc[0])
    assert "ready_without_execution" in summary["v2_terrain_action_parameter_sweep_dry_run_decision"]


def test_task2_8j_20_validator_detects_forbidden_execution():
    terrain_states, sweep, operator_summary, checks, final_summary, _errors, _summary = build_and_validate_v2_terrain_action_parameter_sweep_dry_run(
        cfg=V2TerrainActionParameterSweepDryRunConfig(max_rows_per_operator=3)
    )
    bad = sweep.copy()
    bad.loc[bad.index[0], "terrain_operator_applied"] = True
    errors = validate_v2_terrain_action_parameter_sweep_dry_run_tables(terrain_states, bad, operator_summary, checks, final_summary)
    assert "task2_8j_20_forbidden_true:sweep_dry_run:terrain_operator_applied" in errors
