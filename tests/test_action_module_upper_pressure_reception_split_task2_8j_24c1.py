from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_22_gated_macro_game_risk_simulator_dry_run import (
    GatedMacroGameRiskSimulatorDryRunConfig,
    estimate_risk_confidence,
    should_run_macro_risk_simulator,
    simulate_short_horizon_NO_OP_risk,
)
from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_24c0_actionmodule_information_intake_bridge import (
    build_actionmodule_information_intake_packets,
)
from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_24c1_ot_v8_to_risk_sensing_state import (
    SOURCE_INFORMATION_COLUMNS,
    SIMULATOR_NUMERIC_COLUMNS,
    build_and_validate_ot_v8_risk_sensing_state,
    validate_tables,
)

_CACHE = None


def _result():
    global _CACHE
    if _CACHE is None:
        _CACHE = build_and_validate_ot_v8_risk_sensing_state()
    return _CACHE


def _state_for(states, risk_name: str):
    rows = states[states["risk_name"].astype(str) == risk_name]
    assert len(rows) == 1
    return rows.iloc[0]


def test_task2_8j_24c1_builds_risk_sensing_states_without_information_loss():
    states, quality, final_summary, errors, summary = _result()
    assert errors == []
    assert not states.empty
    assert not quality.empty
    assert not final_summary.empty
    assert len(states) == 5
    assert summary["risk_sensing_state_count"] == 5
    assert summary["simulator_ready_state_count"] == 5
    assert summary["source_information_preserved_state_count"] == 5
    assert summary["numeric_complete_state_count"] == 5
    assert summary["task2_8j_24c1_decision"] == "ot_v8_risk_sensing_states_ready_for_task22_noop_simulator"
    assert set(quality["simulator_ready"].astype(bool)) == {True}
    assert set(states["source_information_preservation_status"].astype(str)) == {"all_required_source_information_preserved"}
    assert set(states["numeric_state_status"].astype(str)) == {"task22_simulator_numeric_state_ready"}


def test_task2_8j_24c1_preserves_ot_and_v8_source_columns_exactly():
    packets = build_actionmodule_information_intake_packets()
    states, quality, final_summary, errors, summary = _result()
    assert errors == []
    for risk_name in packets["risk_name"].astype(str):
        source = packets[packets["risk_name"].astype(str) == risk_name].iloc[0]
        state = _state_for(states, risk_name)
        for col in SOURCE_INFORMATION_COLUMNS:
            assert str(state[col]) == str(source[col])


def test_task2_8j_24c1_maps_risks_to_prediction_relevant_numeric_features():
    states, quality, final_summary, errors, summary = _result()
    assert errors == []

    relation_lock = _state_for(states, "relation_lock")
    assert float(relation_lock["relation_lock_signal"]) >= 0.80
    assert float(relation_lock["escape_path_capacity"]) <= 0.35
    assert float(relation_lock["reversibility"]) <= 0.40

    oscillation = _state_for(states, "oscillation")
    assert float(oscillation["flow_velocity"]) >= 0.80
    assert float(oscillation["curvature"]) >= 0.75

    reversibility_loss = _state_for(states, "reversibility_loss")
    assert float(reversibility_loss["reversibility"]) <= 0.30
    assert float(reversibility_loss["escape_path_capacity"]) <= 0.35

    boundary_fragile = _state_for(states, "boundary_fragile")
    assert float(boundary_fragile["boundary_distance"]) <= 0.30
    assert float(boundary_fragile["uncertainty"]) >= 0.45

    resource_pressure = _state_for(states, "resource_pressure")
    assert float(resource_pressure["pressure_gradient"]) >= 0.80
    assert float(resource_pressure["neighbor_capacity"]) <= 0.30


def test_task2_8j_24c1_states_are_numeric_and_task22_shape_compatible():
    states, quality, final_summary, errors, summary = _result()
    assert errors == []
    required_task22_inputs = {
        "macro_state_id",
        "macro_state_name",
        "risk_label_for_evaluation_only",
        "pressure_gradient",
        "relation_lock_signal",
        "reversibility",
        "boundary_distance",
        "escape_path_capacity",
        "neighbor_capacity",
        "flow_velocity",
        "curvature",
        "uncertainty",
        "NO_OP_baseline",
    }
    assert required_task22_inputs.issubset(set(states.columns))
    for col in SIMULATOR_NUMERIC_COLUMNS:
        assert states[col].astype(float).between(0.0, 1.0).all()


def test_task2_8j_24c1_output_flows_into_existing_task22_noop_simulator():
    states, quality, final_summary, errors, summary = _result()
    assert errors == []
    cfg = GatedMacroGameRiskSimulatorDryRunConfig(horizon=3, seed_count=3, gate_threshold=0.45, risk_threshold=0.62)
    gate = should_run_macro_risk_simulator(states, cfg)
    assert not gate.empty
    assert gate["should_run_simulator"].astype(bool).any()

    trajectories = simulate_short_horizon_NO_OP_risk(states, gate, cfg)
    assert not trajectories.empty
    assert set(trajectories["macro_state_id"].astype(str)).issubset(set(states["macro_state_id"].astype(str)))
    for risk_col in [
        "relation_lock_risk",
        "resource_pressure_risk",
        "reversibility_loss_risk",
        "boundary_fragile_risk",
        "oscillation_risk",
    ]:
        assert trajectories[risk_col].astype(float).between(0.0, 1.0).all()

    risk_confidence = estimate_risk_confidence(trajectories, cfg)
    assert not risk_confidence.empty
    assert {"relation_lock", "resource_pressure", "reversibility_loss", "boundary_fragile", "oscillation"}.issubset(
        set(risk_confidence["risk_name"].astype(str))
    )


def test_task2_8j_24c1_validator_detects_information_loss():
    states, quality, final_summary, _errors, _summary = _result()
    bad = states.copy()
    bad.loc[bad.index[0], "terrain_map_summary"] = ""
    errors = validate_tables(bad, quality, final_summary)
    assert "task2_8j_24c1_source_information_lost:terrain_map_summary" in errors


def test_task2_8j_24c1_validator_detects_numeric_loss():
    states, quality, final_summary, _errors, _summary = _result()
    bad = states.copy()
    bad.loc[bad.index[0], "pressure_gradient"] = 1.5
    errors = validate_tables(bad, quality, final_summary)
    assert "task2_8j_24c1_numeric_out_of_range:pressure_gradient" in errors
