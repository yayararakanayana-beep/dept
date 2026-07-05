import pytest

from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8i_weighted_method_pattern_validation import (
    PREDICTION_ACCURACIES,
    WEIGHT_PATTERNS,
    build_and_validate_weight_pattern_validation_table,
    build_pattern_recommendation_table,
    summarize_weight_pattern_validation,
    validate_weight_pattern_validation,
)


@pytest.fixture(scope="module")
def task2_8i_result():
    return build_and_validate_weight_pattern_validation_table()


@pytest.fixture(scope="module")
def task2_8i_table(task2_8i_result):
    table, _errors, _summary = task2_8i_result
    return table


def test_task2_8i_contract_and_boundaries(task2_8i_result):
    table, errors, summary = task2_8i_result

    assert errors == []
    assert not table.empty
    assert set(table["validation_only"]) == {True}
    assert set(table["runtime_policy_input"]) == {False}
    assert set(table["action_frame_created"]) == {False}
    assert set(table["actionmodule_called"]) == {False}
    assert set(table["world_runtime_called"]) == {False}
    assert set(table["canonical_write_performed"]) == {False}
    assert set(table["upper_pressure_connected"]) == {False}
    assert set(table["exploration_axis_connected"]) == {False}
    assert set(table["synthetic_dynamics_only"]) == {True}
    assert set(table["weight_pattern_validation"]) == {True}
    assert summary["rows"] == len(table)


def test_task2_8i_contains_all_patterns_and_prediction_levels(task2_8i_table):
    expected_patterns = {p.pattern for p in WEIGHT_PATTERNS}

    assert set(task2_8i_table["pattern"].astype(str).unique()) == expected_patterns
    assert set(task2_8i_table["prediction_accuracy"].astype(float).unique()) == set(PREDICTION_ACCURACIES)


def test_task2_8i_finds_positive_weight_pattern_conditions(task2_8i_result):
    table, errors, summary = task2_8i_result
    positive = table[table["positive_weight_pattern_condition"].astype(bool)]

    assert errors == []
    assert not positive.empty
    assert positive["crash_cost_delta_vs_no_op"].gt(0.0).all()
    assert positive["risk_auc_delta_vs_no_op"].gt(0.0).all()
    assert summary["positive_weight_pattern_rows"] == len(positive)


def test_task2_8i_recommendation_table_returns_one_best_per_region(task2_8i_table):
    recommendation = build_pattern_recommendation_table(task2_8i_table)

    assert not recommendation.empty
    key_cols = ["risk_dynamics_type", "initial_risk_level", "prediction_accuracy"]
    assert not recommendation.duplicated(key_cols).any()
    assert recommendation["pattern"].notna().all()


def test_task2_8i_high_accuracy_rewards_direction_weight(task2_8i_table):
    high_acc = task2_8i_table[task2_8i_table["prediction_accuracy"].astype(float) == 1.0]
    mean_net = high_acc.groupby("pattern")["long_term_net_benefit"].mean().to_dict()

    assert mean_net["direction_heavy"] > mean_net["safe_thin"]
    assert mean_net["aggressive"] > mean_net["safe_thin"]


def test_task2_8i_safe_patterns_reduce_side_effects(task2_8i_table):
    mean_side = task2_8i_table.groupby("pattern")["side_effect_delta_vs_no_op"].mean().to_dict()

    assert mean_side["safe_thin"] < mean_side["direction_heavy"]
    assert mean_side["release_heavy"] < mean_side["aggressive"]


def test_task2_8i_side_effects_are_decomposed(task2_8i_table):
    side_sum = (
        task2_8i_table["short_gain_loss_auc"]
        + task2_8i_table["liquidity_loss_auc"]
        + task2_8i_table["overcooling_loss_auc"]
        + task2_8i_table["mismatch_cost_auc"]
        + task2_8i_table["complexity_cost_auc"]
    )

    assert (side_sum - task2_8i_table["side_effect_auc"]).abs().le(1e-9).all()


def test_task2_8i_validator_detects_upper_pressure_mislabel(task2_8i_table):
    table = task2_8i_table.copy()
    table.loc[table.index[0], "upper_pressure_connected"] = True

    errors = validate_weight_pattern_validation(table)
    assert "task2_8i_forbidden_true:upper_pressure_connected" in errors


def test_task2_8i_summary_exposes_best_pattern(task2_8i_table):
    summary = summarize_weight_pattern_validation(task2_8i_table)

    assert summary["positive_weight_pattern_rows"] > 0
    assert summary["best_positive_pattern"] in {p.pattern for p in WEIGHT_PATTERNS}
    assert summary["best_positive_dynamics"] != "none"
