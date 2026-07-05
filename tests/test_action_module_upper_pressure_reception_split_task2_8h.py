import pytest

from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8h_side_effect_reduction_methods import (
    METHODS,
    build_and_validate_side_effect_reduction_methods_table,
    summarize_side_effect_reduction_methods,
    validate_side_effect_reduction_methods,
)


@pytest.fixture(scope="module")
def task2_8h_result():
    return build_and_validate_side_effect_reduction_methods_table()


@pytest.fixture(scope="module")
def task2_8h_table(task2_8h_result):
    table, _errors, _summary = task2_8h_result
    return table


def test_task2_8h_contract_and_boundaries(task2_8h_result):
    table, errors, summary = task2_8h_result

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
    assert set(table["action_method_comparison"]) == {True}
    assert summary["rows"] == len(table)


def test_task2_8h_contains_all_methods(task2_8h_table):
    assert set(task2_8h_table["method"].astype(str).unique()) == set(METHODS)
    assert (task2_8h_table["method"].astype(str) == "no_op").any()


def test_task2_8h_finds_side_effect_reduced_positive_conditions(task2_8h_result):
    table, errors, summary = task2_8h_result
    positive = table[table["positive_side_effect_reduced_condition"].astype(bool)]

    assert errors == []
    assert not positive.empty
    assert positive["crash_cost_delta_vs_no_op"].gt(0.0).all()
    assert positive["risk_auc_delta_vs_no_op"].gt(0.0).all()
    assert summary["positive_side_effect_reduced_rows"] == len(positive)


def test_task2_8h_precise_methods_reduce_side_effect_vs_wall(task2_8h_table):
    by_method = task2_8h_table.groupby("method")["side_effect_delta_vs_no_op"].mean().to_dict()

    assert by_method["direction_selective"] < by_method["wall_global"]
    assert by_method["state_dependent"] < by_method["wall_global"]
    assert by_method["thin_film_release"] < by_method["wall_global"]
    assert by_method["selective_state_thin"] < by_method["wall_global"]


def test_task2_8h_side_effect_per_crash_reduction_exists(task2_8h_table):
    action_rows = task2_8h_table[task2_8h_table["method"].astype(str) != "no_op"]
    # Ignore microscopic crash reductions. Their ratio is numerically unstable and
    # not useful as an insurance-efficiency signal.
    useful = action_rows[action_rows["crash_cost_delta_vs_no_op"].gt(1e-4)]

    assert not useful.empty
    assert useful["side_effect_per_crash_reduction"].lt(999.0).all()
    assert useful["side_effect_per_crash_reduction"].notna().all()


def test_task2_8h_side_effects_are_decomposed(task2_8h_table):
    side_sum = (
        task2_8h_table["short_gain_loss_auc"]
        + task2_8h_table["liquidity_loss_auc"]
        + task2_8h_table["overcooling_loss_auc"]
        + task2_8h_table["mismatch_cost_auc"]
        + task2_8h_table["complexity_cost_auc"]
    )

    assert (side_sum - task2_8h_table["side_effect_auc"]).abs().le(1e-9).all()


def test_task2_8h_validator_detects_exploration_axis_mislabel(task2_8h_table):
    table = task2_8h_table.copy()
    table.loc[table.index[0], "exploration_axis_connected"] = True

    errors = validate_side_effect_reduction_methods(table)
    assert "task2_8h_forbidden_true:exploration_axis_connected" in errors


def test_task2_8h_summary_exposes_best_method(task2_8h_table):
    summary = summarize_side_effect_reduction_methods(task2_8h_table)

    assert summary["positive_side_effect_reduced_rows"] > 0
    assert summary["best_positive_method"] in set(METHODS) - {"no_op"}
    assert summary["best_positive_dynamics"] != "none"
