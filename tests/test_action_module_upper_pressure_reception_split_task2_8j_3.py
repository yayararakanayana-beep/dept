import pytest

from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_1_candidate_feature_log import (
    CandidateFeatureLogConfig,
)
from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_2_temporal_pca_validation import (
    PCA_MODES,
    TemporalPCAValidationConfig,
)
from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_3_effective_dimension_evaluation import (
    EffectiveDimensionEvaluationConfig,
    build_and_validate_effective_dimension_evaluation,
    validate_effective_dimension_evaluation_tables,
)


@pytest.fixture(scope="module")
def task2_8j_3_result():
    feature_cfg = CandidateFeatureLogConfig(steps=18, seeds=(501, 502, 503), window_sizes=(1, 6, 12))
    pca_cfg = TemporalPCAValidationConfig(n_components=5, sparse_top_k=10, prediction_horizon=3)
    eval_cfg = EffectiveDimensionEvaluationConfig()
    return build_and_validate_effective_dimension_evaluation(feature_cfg, pca_cfg, eval_cfg)


@pytest.fixture(scope="module")
def task2_8j_3_tables(task2_8j_3_result):
    evaluation_table, component_count_table, overlap_table, final_summary, _errors, _summary = task2_8j_3_result
    return evaluation_table, component_count_table, overlap_table, final_summary


def test_task2_8j_3_contract_and_boundaries(task2_8j_3_result):
    evaluation_table, component_count_table, overlap_table, final_summary, errors, summary = task2_8j_3_result

    assert errors == []
    for table in [evaluation_table, component_count_table, overlap_table, final_summary]:
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

    assert summary["rows"] == len(evaluation_table)
    assert summary["adoption_performed"] is False
    assert summary["freeze_performed"] is False


def test_task2_8j_3_evaluates_all_pca_modes(task2_8j_3_tables):
    evaluation_table, component_count_table, overlap_table, final_summary = task2_8j_3_tables

    assert set(evaluation_table["mode"].astype(str).unique()) == set(PCA_MODES)
    assert set(component_count_table["mode"].astype(str).unique()) == set(PCA_MODES)
    assert set(overlap_table["mode"].astype(str).unique()) == set(PCA_MODES)
    assert str(final_summary["best_mode_by_overall_score"].iloc[0]) in set(PCA_MODES)


def test_task2_8j_3_scores_are_bounded_and_sorted(task2_8j_3_tables):
    evaluation_table, _component_count_table, _overlap_table, _final_summary = task2_8j_3_tables

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
        assert evaluation_table[col].astype(float).between(0.0, 1.0).all()

    scores = evaluation_table["overall_evaluation_score"].astype(float).tolist()
    assert scores == sorted(scores, reverse=True)


def test_task2_8j_3_component_count_candidates_are_non_adopted(task2_8j_3_tables):
    _evaluation_table, component_count_table, _overlap_table, _final_summary = task2_8j_3_tables

    assert component_count_table["candidate_component_count"].astype(int).ge(1).all()
    assert component_count_table["candidate_component_count"].astype(int).le(component_count_table["component_count"].astype(int).max()).all()
    assert component_count_table["component_count_reason"].astype(str).notna().all()
    assert set(component_count_table["effective_dimension_adopted"].astype(bool)) == {False}
    assert set(component_count_table["effective_dimension_frozen"].astype(bool)) == {False}


def test_task2_8j_3_overlap_table_reports_nonredundancy_pairs(task2_8j_3_tables):
    _evaluation_table, _component_count_table, overlap_table, _final_summary = task2_8j_3_tables

    assert not overlap_table.empty
    assert overlap_table["top_feature_overlap_jaccard"].astype(float).between(0.0, 1.0).all()
    assert overlap_table["overlap_feature_count"].astype(int).ge(0).all()
    assert set(overlap_table["component_pair_status"].astype(str)).issubset({"pass", "watch"})


def test_task2_8j_3_final_summary_is_candidate_only(task2_8j_3_tables):
    evaluation_table, _component_count_table, _overlap_table, final_summary = task2_8j_3_tables

    best_mode = str(final_summary["best_mode_by_overall_score"].iloc[0])
    best_row = evaluation_table[evaluation_table["mode"].astype(str) == best_mode].iloc[0]

    assert bool(final_summary["adoption_performed"].iloc[0]) is False
    assert bool(final_summary["freeze_performed"].iloc[0]) is False
    assert float(final_summary["best_mode_overall_score"].iloc[0]) == pytest.approx(float(best_row["overall_evaluation_score"]))
    assert str(final_summary["next_task"].iloc[0]).startswith("Task 2-8j-4")


def test_task2_8j_3_validator_detects_forbidden_freeze(task2_8j_3_tables):
    evaluation_table, component_count_table, overlap_table, final_summary = task2_8j_3_tables
    bad_summary = final_summary.copy()
    bad_summary.loc[bad_summary.index[0], "freeze_performed"] = True
    bad_summary.loc[bad_summary.index[0], "effective_dimension_frozen"] = True

    errors = validate_effective_dimension_evaluation_tables(
        evaluation_table,
        component_count_table,
        overlap_table,
        bad_summary,
        upstream_errors=[],
    )
    assert "task2_8j_3_forbidden_true:final_summary:effective_dimension_frozen" in errors
    assert "task2_8j_3_freeze_performed_true" in errors
