from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_22_gated_macro_game_risk_simulator_dry_run import (
    GatedMacroGameRiskSimulatorDryRunConfig,
    build_and_validate_gated_macro_game_risk_simulator_dry_run,
    validate_gated_macro_game_risk_simulator_dry_run_tables,
)


def test_task2_8j_22_dry_run_boundaries():
    states, gate, trajectories, risk_confidence, directions, checks, final_summary, errors, summary = build_and_validate_gated_macro_game_risk_simulator_dry_run(
        cfg=GatedMacroGameRiskSimulatorDryRunConfig(horizon=4, seed_count=6)
    )
    assert errors == []
    assert not states.empty
    assert not gate.empty
    assert not trajectories.empty
    assert not risk_confidence.empty
    assert not directions.empty
    assert not checks.empty
    assert not final_summary.empty
    assert summary["gt_main_map_name"] == "static_pca_7"
    assert summary["gt_main_component_count"] == 7
    assert summary["task20b_ready"] is True
    assert summary["not_high_resolution_forecast"] is True
    assert summary["not_long_term_forecast"] is True
    assert summary["risk_prediction_only"] is True
    assert summary["simulator_dry_run_executed"] is True
    assert summary["action_direction_generated"] is False
    assert summary["terrain_operator_selected"] is False
    assert summary["action_candidate_generated"] is False
    assert summary["action_effect_prediction_generated"] is False
    assert summary["axis_executed"] is False
    assert summary["real_actionmodule_called"] is False
    assert summary["validation_errors"] == []

    for table in [states, gate, trajectories, risk_confidence, directions, checks, final_summary]:
        assert set(table["validation_only"].astype(bool)) == {True}
        assert set(table["dry_run_only"].astype(bool)) == {True}
        assert set(table["coarse_macro_game_structure_only"].astype(bool)) == {True}
        assert set(table["not_high_resolution_forecast"].astype(bool)) == {True}
        assert set(table["not_long_term_forecast"].astype(bool)) == {True}
        assert set(table["risk_prediction_only"].astype(bool)) == {True}
        assert set(table["simulator_runs_only_when_gate_open"].astype(bool)) == {True}
        assert set(table["system_visible_information_only"].astype(bool)) == {True}
        assert set(table["risk_confidence_generated"].astype(bool)) == {True}
        assert set(table["dynamics_direction_generated"].astype(bool)) == {True}
        assert set(table["simulator_dry_run_executed"].astype(bool)) == {True}
        assert set(table["action_direction_generated"].astype(bool)) == {False}
        assert set(table["terrain_operator_selected"].astype(bool)) == {False}
        assert set(table["action_candidate_generated"].astype(bool)) == {False}
        assert set(table["effect_prediction_model_executed"].astype(bool)) == {False}
        assert set(table["axis_executed"].astype(bool)) == {False}
        assert set(table["hidden_truth_input"].astype(bool)) == {False}
        assert set(table["future_information_used"].astype(bool)) == {False}


def test_task2_8j_22_gate_trajectory_risk_direction_shape():
    cfg = GatedMacroGameRiskSimulatorDryRunConfig(horizon=3, seed_count=5)
    states, gate, trajectories, risk_confidence, directions, checks, final_summary, errors, summary = build_and_validate_gated_macro_game_risk_simulator_dry_run(cfg=cfg)
    assert errors == []
    opened = int(gate["should_run_simulator"].astype(bool).sum())
    assert opened > 0
    assert len(trajectories) == opened * cfg.seed_count * cfg.horizon
    assert len(risk_confidence) == opened * 5
    assert len(directions) == opened
    assert ((risk_confidence["risk_confidence"].astype(float) >= 0.0) & (risk_confidence["risk_confidence"].astype(float) <= 1.0)).all()
    assert set(checks["check_status"].astype(str)) == {"pass"}
    assert int(final_summary["dry_run_check_count"].iloc[0]) == int(final_summary["dry_run_check_pass_count"].iloc[0])
    assert summary["gated_macro_game_risk_simulator_dry_run_decision"] == "gated_macro_game_risk_simulator_dry_run_ready"
    assert summary["risk_confidence_row_count"] == opened * 5
    assert summary["dynamics_direction_count"] == opened
    assert set(directions["dominant_risk"].astype(str)).issubset({"relation_lock", "resource_pressure", "reversibility_loss", "boundary_fragile", "oscillation"})


def test_task2_8j_22_validator_detects_forbidden_action_candidate_generation():
    states, gate, trajectories, risk_confidence, directions, checks, final_summary, _errors, _summary = build_and_validate_gated_macro_game_risk_simulator_dry_run()
    bad = directions.copy()
    bad.loc[bad.index[0], "action_candidate_generated"] = True
    errors = validate_gated_macro_game_risk_simulator_dry_run_tables(states, gate, trajectories, risk_confidence, bad, checks, final_summary)
    assert "task2_8j_22_forbidden_true:directions:action_candidate_generated" in errors
