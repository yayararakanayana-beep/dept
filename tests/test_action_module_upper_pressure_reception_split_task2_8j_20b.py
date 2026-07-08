from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_20b_macro_game_risk_simulator_contract import (
    MacroGameRiskSimulatorContractConfig,
    build_and_validate_macro_game_risk_simulator_contract,
    validate_macro_game_risk_simulator_contract_tables,
)


def test_task2_8j_20b_contract_boundaries():
    gate, inputs, outputs, functions, checks, final_summary, errors, summary = build_and_validate_macro_game_risk_simulator_contract(
        cfg=MacroGameRiskSimulatorContractConfig()
    )
    assert errors == []
    assert not gate.empty
    assert not inputs.empty
    assert not outputs.empty
    assert not functions.empty
    assert not checks.empty
    assert not final_summary.empty
    assert summary["gt_main_map_name"] == "static_pca_7"
    assert summary["gt_main_component_count"] == 7
    assert summary["task20_ready"] is True
    assert summary["not_high_resolution_forecast"] is True
    assert summary["not_long_term_forecast"] is True
    assert summary["risk_prediction_only"] is True
    assert summary["simulator_runs_only_when_gate_open"] is True
    assert summary["simulator_executed"] is False
    assert summary["action_candidate_generated"] is False
    assert summary["action_effect_prediction_generated"] is False
    assert summary["axis_executed"] is False
    assert summary["real_actionmodule_called"] is False
    assert summary["validation_errors"] == []

    for table in [gate, inputs, outputs, functions, checks, final_summary]:
        assert set(table["validation_only"].astype(bool)) == {True}
        assert set(table["contract_only"].astype(bool)) == {True}
        assert set(table["coarse_macro_game_structure_only"].astype(bool)) == {True}
        assert set(table["not_high_resolution_forecast"].astype(bool)) == {True}
        assert set(table["not_long_term_forecast"].astype(bool)) == {True}
        assert set(table["risk_prediction_only"].astype(bool)) == {True}
        assert set(table["observation_gate_required"].astype(bool)) == {True}
        assert set(table["simulator_runs_only_when_gate_open"].astype(bool)) == {True}
        assert set(table["system_visible_information_only"].astype(bool)) == {True}
        assert set(table["risk_confidence_required"].astype(bool)) == {True}
        assert set(table["dynamics_direction_required"].astype(bool)) == {True}
        assert set(table["action_direction_required_after_risk"].astype(bool)) == {True}
        assert set(table["release_rollback_audit_required"].astype(bool)) == {True}
        assert set(table["simulator_executed"].astype(bool)) == {False}
        assert set(table["high_resolution_state_generated"].astype(bool)) == {False}
        assert set(table["long_term_forecast_generated"].astype(bool)) == {False}
        assert set(table["action_candidate_generated"].astype(bool)) == {False}
        assert set(table["effect_prediction_model_executed"].astype(bool)) == {False}
        assert set(table["axis_executed"].astype(bool)) == {False}
        assert set(table["hidden_truth_input"].astype(bool)) == {False}
        assert set(table["future_information_used"].astype(bool)) == {False}


def test_task2_8j_20b_function_order_and_content():
    gate, inputs, outputs, functions, checks, final_summary, errors, summary = build_and_validate_macro_game_risk_simulator_contract()
    assert errors == []
    names = functions.sort_values("call_order")["function_name"].astype(str).tolist()
    assert names.index("should_run_macro_risk_simulator") < names.index("simulate_short_horizon_NO_OP_risk")
    assert names.index("simulate_short_horizon_NO_OP_risk") < names.index("estimate_risk_confidence")
    assert names.index("estimate_risk_confidence") < names.index("extract_dynamics_direction")
    assert names.index("extract_dynamics_direction") < names.index("infer_action_direction")
    assert names.index("infer_action_direction") < names.index("select_terrain_operator")
    assert set(checks["check_status"].astype(str)) == {"pass"}
    assert int(final_summary["contract_check_count"].iloc[0]) == int(final_summary["contract_check_pass_count"].iloc[0])
    assert "macro_game_risk_simulator_contract_ready" == summary["macro_game_risk_simulator_contract_decision"]
    assert {"risk_confidence", "dynamics_direction", "comparison"}.issubset(set(outputs["output_group"].astype(str)))
    assert "NO_OP_baseline" in set(inputs["input_name"].astype(str))


def test_task2_8j_20b_validator_detects_forbidden_simulator_execution():
    gate, inputs, outputs, functions, checks, final_summary, _errors, _summary = build_and_validate_macro_game_risk_simulator_contract()
    bad = functions.copy()
    bad.loc[bad.index[0], "simulator_executed"] = True
    errors = validate_macro_game_risk_simulator_contract_tables(gate, inputs, outputs, bad, checks, final_summary)
    assert "task2_8j_20b_forbidden_true:functions:simulator_executed" in errors
