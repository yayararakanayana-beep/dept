from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_7_insurance_terrain_gate import (
    TASK2_7_INSURANCE_GATE_VERSION,
    build_and_validate_demo_insurance_terrain_action_gate_table,
    build_demo_pressure_inputs_for_insurance_gate,
    build_demo_terrain_map,
    build_insurance_terrain_action_gate_table,
    compute_terrain_gain,
    compute_terrain_risk,
    validate_insurance_terrain_action_gate_table,
)


def test_task2_7_insurance_gate_contract_and_boundaries():
    table, errors = build_and_validate_demo_insurance_terrain_action_gate_table()

    assert errors == []
    assert not table.empty
    assert set(table["task2_7_gate_version"]) == {TASK2_7_INSURANCE_GATE_VERSION}
    assert set(table["gate_type"]) == {"insurance_terrain_timing_location_gate"}
    assert set(table["pre_actionframe_only"]) == {True}
    assert set(table["candidate_only"]) == {True}
    assert set(table["runtime_policy_input"]) == {False}
    assert set(table["final_action_decision"]) == {False}
    assert set(table["action_frame_created"]) == {False}
    assert set(table["actionmodule_called"]) == {False}
    assert set(table["world_runtime_called"]) == {False}
    assert set(table["canonical_write_performed"]) == {False}
    assert set(table["pressure_information_preserved"]) == {True}
    assert set(table["pressure_route_split_performed"]) == {False}
    assert set(table["uses_six_action_vocabulary_only"]) == {True}


def test_task2_7_pressure_inputs_are_preserved_without_route_split():
    pressure = build_demo_pressure_inputs_for_insurance_gate()
    table = build_insurance_terrain_action_gate_table(pressure, build_demo_terrain_map())

    expected = set(pressure["pressure_input_id"].astype(str))
    observed = set(table["pressure_input_id"].astype(str))
    assert expected.issubset(observed)
    assert set(table["pressure_route_split_performed"]) == {False}


def test_task2_7_high_risk_terrain_surfaces_insurance_candidates():
    table, errors = build_and_validate_demo_insurance_terrain_action_gate_table()

    assert errors == []
    high = table[table["terrain_location_id"] == "terrain_high_boundary_instability"]
    assert not high.empty
    assert high["terrain_risk_band"].eq("high").any()
    surfaced = high[high["gate_decision"] == "surface_insurance_candidate"]
    assert not surfaced.empty
    assert set(surfaced["action_channel"]).issubset({"buffer_increase", "volatility_damping", "uncertainty_probe"})
    assert surfaced["insurance_fallback_used"].astype(bool).all()
    assert surfaced["recommended_action_strength_hint"].between(0.0, 0.18).all()


def test_task2_7_low_risk_high_gain_surfaces_safe_gain_probe():
    table, errors = build_and_validate_demo_insurance_terrain_action_gate_table()

    assert errors == []
    low = table[table["terrain_location_id"] == "terrain_low_risk_high_gain"]
    assert not low.empty
    assert low["terrain_risk_band"].eq("low").any()
    safe_gain = low[low["gate_decision"] == "surface_safe_gain_probe_candidate"]
    assert not safe_gain.empty
    assert safe_gain["safe_gain_probe_used"].astype(bool).all()
    assert set(safe_gain["action_channel"]).issubset({"exploration_injection", "uncertainty_probe", "buffer_increase"})


def test_task2_7_medium_or_uncertain_terrain_requires_audit_or_sandbox():
    table, errors = build_and_validate_demo_insurance_terrain_action_gate_table()

    assert errors == []
    assert table["requires_local_audit_before_action"].astype(bool).any()
    assert table["requires_sandbox_before_action"].astype(bool).any()
    medium = table[table["terrain_location_id"] == "terrain_medium_uncertain"]
    assert not medium.empty
    assert medium["gate_decision"].isin({"require_local_audit_or_sandbox", "hold_no_terrain_trigger", "hold_opening_action_high_risk"}).any()


def test_task2_7_terrain_scores_are_bounded_and_ordered_for_demo():
    terrain = build_demo_terrain_map()
    risks = {row["terrain_location_id"]: compute_terrain_risk(row) for _, row in terrain.iterrows()}
    gains = {row["terrain_location_id"]: compute_terrain_gain(row) for _, row in terrain.iterrows()}

    assert all(0.0 <= value <= 1.0 for value in risks.values())
    assert all(0.0 <= value <= 1.0 for value in gains.values())
    assert risks["terrain_high_boundary_instability"] > risks["terrain_medium_uncertain"] > risks["terrain_low_risk_high_gain"]
    assert gains["terrain_low_risk_high_gain"] > gains["terrain_medium_uncertain"] > gains["terrain_high_boundary_instability"]


def test_task2_7_validator_detects_actionmodule_call_mislabel():
    table, _ = build_and_validate_demo_insurance_terrain_action_gate_table()
    table.loc[table.index[0], "actionmodule_called"] = True

    errors = validate_insurance_terrain_action_gate_table(table, build_demo_pressure_inputs_for_insurance_gate())
    assert "task2_7_forbidden_true_field:actionmodule_called" in errors
