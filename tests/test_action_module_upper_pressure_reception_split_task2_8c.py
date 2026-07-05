from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8c_terrain_reshaping_minimal_validation import (
    HORIZON,
    MODES,
    TASK2_8C_VERSION,
    build_and_validate_terrain_reshaping_minimal_validation_table,
    build_terrain_reshaping_minimal_validation_table,
    summarize_terrain_reshaping_minimal_validation,
    validate_terrain_reshaping_minimal_validation,
)


def test_task2_8c_contract_and_boundaries():
    table, errors, summary = build_and_validate_terrain_reshaping_minimal_validation_table()

    assert errors == []
    assert not table.empty
    assert set(table["task2_8c_version"]) == {TASK2_8C_VERSION}
    assert set(table["validation_only"]) == {True}
    assert set(table["runtime_policy_input"]) == {False}
    assert set(table["action_frame_created"]) == {False}
    assert set(table["actionmodule_called"]) == {False}
    assert set(table["world_runtime_called"]) == {False}
    assert set(table["canonical_write_performed"]) == {False}
    assert set(table["upper_pressure_connected"]) == {False}
    assert set(table["fixed_validation_settings"]) == {True}
    assert summary["rows"] == len(table)


def test_task2_8c_modes_and_horizon_are_present():
    table = build_terrain_reshaping_minimal_validation_table()

    assert set(table["mode"].astype(str)) == set(MODES)
    assert set(table["horizon"].astype(int)) == {HORIZON}
    assert table["terrain_location_id"].nunique() >= 3


def test_task2_8c_measures_peak_auc_gain_side_effect_and_persistence():
    table = build_terrain_reshaping_minimal_validation_table()

    for col in [
        "risk_peak",
        "risk_auc",
        "gain_auc",
        "side_effect_auc",
        "post_action_persistence",
        "long_term_net_benefit",
        "risk_peak_delta_vs_no_op",
        "risk_auc_delta_vs_no_op",
        "gain_auc_delta_vs_no_op",
        "side_effect_delta_vs_no_op",
    ]:
        assert table[col].notna().all()
    assert table["trend_improvement_class"].astype(str).str.len().gt(0).all()
    assert table["risk_peak_delta_vs_no_op"].gt(0.0).any()
    assert table["risk_auc_delta_vs_no_op"].gt(0.0).any()


def test_task2_8c_summary_identifies_best_mode():
    table = build_terrain_reshaping_minimal_validation_table()
    summary = summarize_terrain_reshaping_minimal_validation(table)

    assert summary["horizon"] == HORIZON
    assert set(summary["modes"]) == set(MODES)
    assert summary["best_mode_by_mean_net"] in set(MODES)
    assert len(summary["by_mode"]) == len(MODES)


def test_task2_8c_validator_detects_actionmodule_mislabel():
    table = build_terrain_reshaping_minimal_validation_table()
    table.loc[table.index[0], "actionmodule_called"] = True

    errors = validate_terrain_reshaping_minimal_validation(table)
    assert "task2_8c_forbidden_true:actionmodule_called" in errors
