from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8g_sensitivity_boundary_search import (
    CRASH_THRESHOLDS,
    INITIAL_RISK_LEVELS,
    build_and_validate_sensitivity_boundary_search_table,
    build_boundary_summary,
    build_sensitivity_boundary_search_table,
    summarize_sensitivity_boundary_search,
    validate_sensitivity_boundary_search,
)


def test_task2_8g_contract_and_boundaries():
    table, errors, summary = build_and_validate_sensitivity_boundary_search_table()

    assert errors == []
    assert not table.empty
    assert set(table["validation_only"]) == {True}
    assert set(table["runtime_policy_input"]) == {False}
    assert set(table["action_frame_created"]) == {False}
    assert set(table["actionmodule_called"]) == {False}
    assert set(table["world_runtime_called"]) == {False}
    assert set(table["canonical_write_performed"]) == {False}
    assert set(table["upper_pressure_connected"]) == {False}
    assert set(table["exploration_escape_connected"]) == {False}
    assert set(table["synthetic_dynamics_only"]) == {True}
    assert set(table["sensitivity_search"]) == {True}
    assert summary["rows"] == len(table)


def test_task2_8g_has_risk_and_crash_boundary_sweeps():
    table = build_sensitivity_boundary_search_table()

    assert table["risk_dynamics_type"].nunique() >= 4
    assert set(table["initial_risk_level"].astype(float).unique()) == set(INITIAL_RISK_LEVELS)
    assert set(table["crash_threshold"].astype(float).unique()) == set(CRASH_THRESHOLDS)
    assert (table["policy"].astype(str) == "no_op").any()


def test_task2_8g_finds_positive_tail_insurance_boundary():
    table, errors, summary = build_and_validate_sensitivity_boundary_search_table()
    positive = table[table["positive_tail_insurance_condition"].astype(bool)]

    assert errors == []
    assert not positive.empty
    assert positive["action_matches_dynamics"].astype(bool).all()
    assert positive["crash_cost_delta_vs_no_op"].gt(0.0).all()
    assert positive["risk_auc_delta_vs_no_op"].gt(0.0).all()
    assert summary["positive_tail_insurance_rows"] == len(positive)


def test_task2_8g_boundary_summary_exposes_break_even_risk():
    table = build_sensitivity_boundary_search_table()
    boundary = build_boundary_summary(table)

    assert not boundary.empty
    assert "break_even_risk_level" in boundary.columns
    assert boundary["break_even_risk_level"].between(min(INITIAL_RISK_LEVELS), max(INITIAL_RISK_LEVELS)).all()
    assert boundary["positive_rows"].gt(0).all()


def test_task2_8g_prediction_accuracy_dimension_exists():
    table = build_sensitivity_boundary_search_table()
    pred = table[table["prediction_required"].astype(bool)]

    assert not pred.empty
    assert set(pred["prediction_accuracy"].astype(float).unique()) >= {1.0, 0.8, 0.6, 0.4}
    assert pred["prediction_correct"].isin([True, False]).all()


def test_task2_8g_side_effects_are_decomposed():
    table = build_sensitivity_boundary_search_table()
    side_sum = (
        table["short_gain_loss_auc"]
        + table["liquidity_loss_auc"]
        + table["overcooling_loss_auc"]
        + table["mismatch_cost_auc"]
        + table["complexity_cost_auc"]
    )

    assert (side_sum - table["side_effect_auc"]).abs().le(1e-9).all()


def test_task2_8g_validator_detects_upper_pressure_mislabel():
    table = build_sensitivity_boundary_search_table()
    table.loc[table.index[0], "upper_pressure_connected"] = True

    errors = validate_sensitivity_boundary_search(table)
    assert "task2_8g_forbidden_true:upper_pressure_connected" in errors


def test_task2_8g_summary_exposes_best_condition():
    table = build_sensitivity_boundary_search_table()
    summary = summarize_sensitivity_boundary_search(table)

    assert summary["positive_tail_insurance_rows"] > 0
    assert summary["best_positive_dynamics"] != "none"
    assert summary["best_positive_policy"] in {"single_predicted", "pair_predicted", "all_cover"}
    assert summary["best_positive_initial_risk"] in INITIAL_RISK_LEVELS
    assert summary["best_positive_crash_threshold"] in CRASH_THRESHOLDS
