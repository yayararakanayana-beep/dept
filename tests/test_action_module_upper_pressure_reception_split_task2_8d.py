from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8d_terrain_reshaping_targeted_validation import (
    DURATION_BANDS,
    HORIZON,
    MODES,
    STRENGTH_BANDS,
    TASK2_8D_VERSION,
    build_and_validate_terrain_reshaping_targeted_validation_table,
    build_targeted_candidate_table,
    build_terrain_reshaping_targeted_validation_table,
    summarize_terrain_reshaping_targeted_validation,
    validate_terrain_reshaping_targeted_validation,
)


def test_task2_8d_contract_and_boundaries():
    table, errors, summary = build_and_validate_terrain_reshaping_targeted_validation_table()

    assert errors == []
    assert not table.empty
    assert set(table["task2_8d_version"]) == {TASK2_8D_VERSION}
    assert set(table["validation_only"]) == {True}
    assert set(table["runtime_policy_input"]) == {False}
    assert set(table["action_frame_created"]) == {False}
    assert set(table["actionmodule_called"]) == {False}
    assert set(table["world_runtime_called"]) == {False}
    assert set(table["canonical_write_performed"]) == {False}
    assert set(table["upper_pressure_connected"]) == {False}
    assert set(table["exploration_escape_connected"]) == {False}
    assert set(table["fixed_validation_settings"]) == {True}
    assert set(table["targeting_thresholds_arbitrary"]) == {True}
    assert summary["rows"] == len(table)


def test_task2_8d_targeted_candidates_exist():
    candidates = build_targeted_candidate_table()

    assert not candidates.empty
    assert "targeting_passed" in candidates.columns
    assert candidates["targeting_passed"].astype(bool).any()
    assert candidates["targeting_basis"].astype(str).str.contains("base_pass=").all()


def test_task2_8d_modes_strengths_durations_and_horizon():
    table = build_terrain_reshaping_targeted_validation_table()

    assert set(table["mode"].astype(str)) == set(MODES)
    assert set(table["strength_band"].astype(str)) == set(STRENGTH_BANDS)
    assert set(table["duration_band"].astype(str)) == set(DURATION_BANDS)
    assert set(table["horizon"].astype(int)) == {HORIZON}


def test_task2_8d_finds_positive_active_targeted_condition():
    table, errors, summary = build_and_validate_terrain_reshaping_targeted_validation_table()
    positive_targeted = table[
        table["mode"].astype(str).isin(["terrain_targeted", "combined_targeted"])
        & table["positive_net_condition"].astype(bool)
        & table["targeted_actions"].astype(str).ne("none")
    ]

    assert errors == []
    assert not positive_targeted.empty
    assert summary["positive_net_rows"] >= len(positive_targeted)
    assert positive_targeted["risk_auc_delta_vs_no_op"].gt(0.0).all()
    assert positive_targeted["side_effect_delta_vs_no_op"].gt(0.0).all()


def test_task2_8d_summary_exposes_best_bands():
    table = build_terrain_reshaping_targeted_validation_table()
    summary = summarize_terrain_reshaping_targeted_validation(table)

    assert summary["horizon"] == HORIZON
    assert summary["best_mode"] in set(MODES)
    assert summary["best_strength_band"] in set(STRENGTH_BANDS)
    assert summary["best_duration_band"] in set(DURATION_BANDS)
    assert summary["best_positive_mode"] in set(MODES)
    assert summary["best_positive_strength_band"] in set(STRENGTH_BANDS)
    assert summary["best_positive_duration_band"] in set(DURATION_BANDS)
    assert len(summary["by_mode"]) == len(MODES)


def test_task2_8d_validator_detects_exploration_escape_mislabel():
    table = build_terrain_reshaping_targeted_validation_table()
    table.loc[table.index[0], "exploration_escape_connected"] = True

    errors = validate_terrain_reshaping_targeted_validation(table)
    assert "task2_8d_forbidden_true:exploration_escape_connected" in errors
