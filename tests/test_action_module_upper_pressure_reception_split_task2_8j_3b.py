import pytest

from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_1_candidate_feature_log import (
    CandidateFeatureLogConfig,
)
from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_3b_component_count_sweep import (
    ComponentCountSweepConfig,
    build_and_validate_component_count_sweep,
    validate_component_count_sweep_tables,
)


@pytest.fixture(scope="module")
def task2_8j_3b_result():
    feature_cfg = CandidateFeatureLogConfig(steps=18, seeds=(501, 502), window_sizes=(1, 6, 12))
    sweep_cfg = ComponentCountSweepConfig(component_counts=(3, 4, 5, 6, 7, 8), standard_component_count=6)
    return build_and_validate_component_count_sweep(feature_cfg=feature_cfg, sweep_cfg=sweep_cfg)


@pytest.fixture(scope="module")
def task2_8j_3b_tables(task2_8j_3b_result):
    sweep_table, target_prediction_table, static_component_table, final_summary, _errors, _summary = task2_8j_3b_result
    return sweep_table, target_prediction_table, static_component_table, final_summary


def test_task2_8j_3b_contract_and_boundaries(task2_8j_3b_result):
    sweep_table, target_prediction_table, static_component_table, final_summary, errors, summary = task2_8j_3b_result

    assert errors == []
    for table in [sweep_table, target_prediction_table, static_component_table, final_summary]:
        assert not table.empty
        assert set(table["validation_only"].astype(bool)) == {True}
        assert set(table["runtime_policy_input"].astype(bool)) == {False}
        assert set(table["fullspec_runtime_connected"].astype(bool)) == {False}
        assert set(table["upper_pressure_connected"].astype(bool)) == {False}
        assert set(table["action_frame_created"].astype(bool)) == {False}
        assert set(table["actionmodule_called"].astype(bool)) == {False}
        assert set(table["canonical_write_performed"].astype(bool)) == {False}
        assert set(table["gk_writeback_performed"].astype(bool)) == {False}
        assert set(table["ot_writeback_performed"].astype(bool)) == {False}
        assert set(table["effective_dimension_adopted"].astype(bool)) == {False}
        assert set(table["effective_dimension_frozen"].astype(bool)) == {False}
        assert set(table["dynamics_axis_extracted"].astype(bool)) == {False}
        assert set(table["action_weight_converted"].astype(bool)) == {False}
        assert set(table["hidden_truth_input"].astype(bool)) == {False}

    assert summary["rows"] == len(sweep_table)
    assert summary["adoption_performed"] is False
    assert summary["freeze_performed"] is False


def test_task2_8j_3b_sweeps_static_three_to_eight_axes(task2_8j_3b_tables):
    sweep_table, _target_prediction_table, static_component_table, final_summary = task2_8j_3b_tables

    static_rows = sweep_table[sweep_table["mode"].astype(str) == "static_pca"]
    assert set(static_rows["requested_component_count"].astype(int)) == {3, 4, 5, 6, 7, 8}
    assert bool(final_summary["seven_axis_tested"].iloc[0]) is True
    assert bool(final_summary["eight_axis_tested"].iloc[0]) is True

    expansion_rows = static_rows[static_rows["requested_component_count"].astype(int).isin([7, 8])]
    assert set(expansion_rows["component_count_role"].astype(str)) == {"expansion_watch"}
    assert "expansion_component" in set(static_component_table["component_role"].astype(str))


def test_task2_8j_3b_scores_are_bounded(task2_8j_3b_tables):
    sweep_table, _target_prediction_table, _static_component_table, _final_summary = task2_8j_3b_tables

    score_cols = [
        "usefulness_score",
        "information_retention_score",
        "prediction_usefulness_score",
        "stability_score",
        "nonredundancy_score",
        "usability_score",
        "overall_evaluation_score",
    ]
    for col in score_cols:
        assert sweep_table[col].astype(float).between(0.0, 1.0).all()

    assert sweep_table["requested_component_count"].astype(int).min() == 3
    assert sweep_table["requested_component_count"].astype(int).max() == 8


def test_task2_8j_3b_target_prediction_deltas_use_static_6_baseline(task2_8j_3b_tables):
    _sweep_table, target_prediction_table, _static_component_table, _final_summary = task2_8j_3b_tables

    assert "r2_delta_from_static_6" in target_prediction_table.columns
    baseline_rows = target_prediction_table[
        (target_prediction_table["mode"].astype(str) == "static_pca")
        & (target_prediction_table["requested_component_count"].astype(int) == 6)
    ]
    assert not baseline_rows.empty
    assert baseline_rows["r2_delta_from_static_6"].astype(float).abs().max() == pytest.approx(0.0)


def test_task2_8j_3b_final_summary_is_non_adopting(task2_8j_3b_tables):
    sweep_table, _target_prediction_table, _static_component_table, final_summary = task2_8j_3b_tables

    assert bool(final_summary["adoption_performed"].iloc[0]) is False
    assert bool(final_summary["freeze_performed"].iloc[0]) is False
    assert int(final_summary["standard_component_count"].iloc[0]) == 6
    assert str(final_summary["next_task"].iloc[0]).startswith("Task 2-8j-4")
    assert int(final_summary["best_static_component_count_by_overall"].iloc[0]) in {3, 4, 5, 6, 7, 8}
    assert set(sweep_table["candidate_status"].astype(str)).issubset({"candidate_strong", "candidate_watch", "candidate_weak"})


def test_task2_8j_3b_validator_detects_forbidden_adoption(task2_8j_3b_tables):
    sweep_table, target_prediction_table, static_component_table, final_summary = task2_8j_3b_tables
    bad_summary = final_summary.copy()
    bad_summary.loc[bad_summary.index[0], "adoption_performed"] = True
    bad_summary.loc[bad_summary.index[0], "effective_dimension_adopted"] = True

    errors = validate_component_count_sweep_tables(
        sweep_table,
        target_prediction_table,
        static_component_table,
        bad_summary,
        ComponentCountSweepConfig(component_counts=(3, 4, 5, 6, 7, 8), standard_component_count=6),
    )
    assert "task2_8j_3b_forbidden_true:final_summary:effective_dimension_adopted" in errors
    assert "task2_8j_3b_adoption_performed_true" in errors
