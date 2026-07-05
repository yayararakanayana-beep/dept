from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8b_terrain_reshaping_candidates import (
    TERRAIN_RESHAPING_ACTIONS,
    TASK2_8B_VERSION,
    build_and_validate_demo_terrain_reshaping_candidates,
    build_demo_exploration_efficiency_hints,
    build_demo_lower_risk_information,
    build_demo_upper_pressure_modulation,
    build_demo_v8_local_evidence,
    build_terrain_reshaping_candidates,
    validate_terrain_reshaping_candidates,
)


def test_task2_8b_candidate_contract_and_boundaries():
    table, errors, summary = build_and_validate_demo_terrain_reshaping_candidates()

    assert errors == []
    assert not table.empty
    assert set(table["task2_8b_version"]) == {TASK2_8B_VERSION}
    assert set(table["candidate_only"]) == {True}
    assert set(table["validation_only"]) == {True}
    assert set(table["runtime_policy_input"]) == {False}
    assert set(table["action_frame_created"]) == {False}
    assert set(table["actionmodule_called"]) == {False}
    assert set(table["world_runtime_called"]) == {False}
    assert set(table["canonical_write_performed"]) == {False}
    assert set(table["pressure_directly_selected_action"]) == {False}
    assert set(table["raw_v8_access_performed"]) == {False}
    assert summary["rows"] == len(table)


def test_task2_8b_minimal_three_actions_are_present():
    table, errors, _ = build_and_validate_demo_terrain_reshaping_candidates()

    assert errors == []
    assert set(table["terrain_reshaping_action"].astype(str)) == set(TERRAIN_RESHAPING_ACTIONS)
    assert set(table["terrain_reshaping_action_ja"].astype(str)) == set(TERRAIN_RESHAPING_ACTIONS.values())


def test_task2_8b_uses_lower_risk_v8_pressure_and_exploration_evidence():
    table, errors, _ = build_and_validate_demo_terrain_reshaping_candidates()

    assert errors == []
    assert table["lower_risk_basis"].astype(str).str.contains("risk_basis=").all()
    assert table["v8_local_evidence_basis"].astype(str).str.len().gt(0).all()
    assert table["upper_pressure_modulation_basis"].astype(str).str.len().gt(0).all()
    assert table["exploration_efficiency_basis"].astype(str).str.len().gt(0).all()


def test_task2_8b_ready_candidates_require_sandbox():
    table, errors, _ = build_and_validate_demo_terrain_reshaping_candidates()
    ready = table[table["candidate_status"] == "candidate_ready_for_sandbox"]

    assert errors == []
    assert not ready.empty
    assert ready["sandbox_required"].astype(bool).all()
    assert ready["candidate_score"].ge(ready["activation_threshold_after_pressure"]).all()


def test_task2_8b_scores_are_bounded():
    table, errors, _ = build_and_validate_demo_terrain_reshaping_candidates()

    assert errors == []
    for col in [
        "candidate_score",
        "activation_threshold_after_pressure",
        "expected_slope_effect",
        "expected_peak_effect",
        "expected_recovery_effect",
        "expected_persistence_effect",
        "side_effect_estimate",
    ]:
        assert table[col].between(0.0, 1.0).all()


def test_task2_8b_validator_detects_forbidden_actionmodule_call():
    table = build_terrain_reshaping_candidates(
        build_demo_lower_risk_information(),
        build_demo_v8_local_evidence(),
        build_demo_upper_pressure_modulation(),
        build_demo_exploration_efficiency_hints(),
    )
    table.loc[table.index[0], "actionmodule_called"] = True

    errors = validate_terrain_reshaping_candidates(table)
    assert "task2_8b_forbidden_true:actionmodule_called" in errors
