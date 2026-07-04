from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_7c_light_strength_trend_validation import (
    HORIZON,
    STRENGTH_MULTIPLIERS,
    TASK2_7C_LIGHT_VERSION,
    build_and_validate_strength_trend_light_validation_table,
    build_strength_trend_light_validation_table,
    summarize_strength_trend_light_validation,
    validate_strength_trend_light_validation_table,
)


def test_task2_7c_contract_and_boundaries():
    table, errors, summary = build_and_validate_strength_trend_light_validation_table()

    assert errors == []
    assert not table.empty
    assert set(table["task2_7c_version"]) == {TASK2_7C_LIGHT_VERSION}
    assert set(table["validation_only"]) == {True}
    assert set(table["runtime_policy_input"]) == {False}
    assert set(table["action_frame_created"]) == {False}
    assert set(table["actionmodule_called"]) == {False}
    assert set(table["world_runtime_called"]) == {False}
    assert set(table["canonical_write_performed"]) == {False}
    assert summary["rows"] == len(table)


def test_task2_7c_strength_multipliers_and_horizon_are_present():
    table = build_strength_trend_light_validation_table()

    assert set(table["strength_multiplier"].astype(float)) == set(float(x) for x in STRENGTH_MULTIPLIERS)
    assert set(table["horizon"].astype(int)) == {HORIZON}
    assert table["effective_strength"].ge(0.0).all()
    assert table["effective_strength"].le(0.40).all()


def test_task2_7c_improvement_side_effect_and_trend_are_measured():
    table = build_strength_trend_light_validation_table()

    assert table["risk_auc_reduction"].notna().all()
    assert table["gain_auc_delta_vs_no_op"].notna().all()
    assert table["side_effect_auc"].ge(0.0).all()
    assert table["long_term_net_benefit"].notna().all()
    assert table["risk_slope_delta_vs_no_op"].notna().all()
    assert table["risk_trend_class"].astype(str).str.len().gt(0).all()
    assert table["risk_trend_class"].isin({"trend_reversal", "trend_damping", "temporary_relief", "side_effect_dominant", "no_effect"}).all()
    assert table["risk_trend_class"].isin({"trend_reversal", "trend_damping", "temporary_relief"}).any()


def test_task2_7c_summary_identifies_best_multiplier():
    table = build_strength_trend_light_validation_table()
    summary = summarize_strength_trend_light_validation(table)

    assert summary["horizon"] == HORIZON
    assert set(summary["strength_multipliers"]) == set(float(x) for x in STRENGTH_MULTIPLIERS)
    assert summary["best_multiplier_by_mean_net"] in set(float(x) for x in STRENGTH_MULTIPLIERS)
    assert len(summary["by_multiplier"]) == len(STRENGTH_MULTIPLIERS)


def test_task2_7c_validator_detects_actionmodule_mislabel():
    table = build_strength_trend_light_validation_table()
    table.loc[table.index[0], "actionmodule_called"] = True

    errors = validate_strength_trend_light_validation_table(table)
    assert "task2_7c_forbidden_true:actionmodule_called" in errors
