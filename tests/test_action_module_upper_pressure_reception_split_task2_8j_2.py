import pytest

from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_1_candidate_feature_log import (
    CandidateFeatureLogConfig,
)
from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_2_temporal_pca_validation import (
    PCA_MODES,
    TemporalPCAValidationConfig,
    build_and_validate_temporal_pca_validation,
    validate_temporal_pca_validation_tables,
)


@pytest.fixture(scope="module")
def task2_8j_2_result():
    feature_cfg = CandidateFeatureLogConfig(steps=18, seeds=(501, 502, 503), window_sizes=(1, 6, 12))
    pca_cfg = TemporalPCAValidationConfig(n_components=5, sparse_top_k=10, prediction_horizon=3)
    return build_and_validate_temporal_pca_validation(feature_cfg, pca_cfg)


@pytest.fixture(scope="module")
def task2_8j_2_tables(task2_8j_2_result):
    component_table, model_summary, stability_table, prediction_table, _errors, _summary = task2_8j_2_result
    return component_table, model_summary, stability_table, prediction_table


def test_task2_8j_2_contract_and_boundaries(task2_8j_2_result):
    component_table, model_summary, stability_table, prediction_table, errors, summary = task2_8j_2_result

    assert errors == []
    for table in [component_table, model_summary, stability_table, prediction_table]:
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
        assert set(table["dynamics_axis_extracted"].astype(bool)) == {False}
        assert set(table["action_weight_converted"].astype(bool)) == {False}
        assert set(table["hidden_truth_input"].astype(bool)) == {False}

    assert summary["component_rows"] == len(component_table)
    assert summary["model_summary_rows"] == len(model_summary)
    assert set(summary["modes"]) == set(PCA_MODES)


def test_task2_8j_2_contains_static_temporal_and_sparse_modes(task2_8j_2_tables):
    component_table, model_summary, _stability_table, _prediction_table = task2_8j_2_tables

    assert set(component_table["mode"].astype(str).unique()) == set(PCA_MODES)
    assert set(model_summary["mode"].astype(str).unique()) == set(PCA_MODES)
    assert component_table.groupby("mode")["component_index"].nunique().min() >= 3


def test_task2_8j_2_explained_variance_and_reconstruction_are_valid(task2_8j_2_tables):
    component_table, model_summary, _stability_table, _prediction_table = task2_8j_2_tables

    assert component_table["explained_variance_ratio"].astype(float).ge(0.0).all()
    assert component_table["cumulative_explained_variance_ratio"].astype(float).between(0.0, 1.0).all()
    assert model_summary["total_explained_variance_ratio"].astype(float).between(0.0, 1.0).all()
    assert model_summary["reconstruction_error_ratio"].astype(float).ge(0.0).all()
    assert model_summary["matrix_rank"].astype(int).gt(0).all()
    assert model_summary["effective_rank"].astype(float).gt(0.0).all()


def test_task2_8j_2_sparse_temporal_mode_is_sparse(task2_8j_2_tables):
    component_table, model_summary, _stability_table, _prediction_table = task2_8j_2_tables

    sparse = component_table[component_table["mode"].astype(str) == "sparse_temporal_pca"]
    temporal = component_table[component_table["mode"].astype(str) == "temporal_pca"]

    assert not sparse.empty
    assert sparse["active_feature_count"].astype(int).le(10).all()
    assert sparse["active_feature_count"].astype(int).lt(sparse["n_features"].astype(int)).all()
    assert temporal["active_feature_count"].astype(int).gt(sparse["active_feature_count"].astype(int).max()).all()
    assert int(model_summary[model_summary["mode"] == "sparse_temporal_pca"]["sparse_top_k"].iloc[0]) == 10


def test_task2_8j_2_stability_table_has_valid_similarity_scores(task2_8j_2_tables):
    _component_table, _model_summary, stability_table, _prediction_table = task2_8j_2_tables

    assert not stability_table.empty
    assert set(stability_table["mode"].astype(str).unique()).issubset(set(PCA_MODES))
    assert stability_table["subspace_similarity"].astype(float).between(0.0, 1.0).all()
    assert stability_table["principal_angle_proxy"].astype(float).between(0.0, 1.0).all()
    assert stability_table["n_components_compared"].astype(int).gt(0).all()


def test_task2_8j_2_prediction_table_has_observed_targets(task2_8j_2_tables):
    _component_table, _model_summary, _stability_table, prediction_table = task2_8j_2_tables

    assert not prediction_table.empty
    assert set(prediction_table["mode"].astype(str).unique()) == set(PCA_MODES)
    assert prediction_table["target_feature_key"].astype(str).str.contains("v2_hidden_trace").sum() == 0
    assert prediction_table["prediction_horizon"].astype(int).eq(3).all()
    assert prediction_table["train_rows"].astype(int).gt(0).all()
    assert prediction_table["test_rows"].astype(int).gt(0).all()
    assert prediction_table["rmse"].astype(float).ge(0.0).all()
    assert prediction_table["baseline_rmse"].astype(float).ge(0.0).all()


def test_task2_8j_2_validator_detects_forbidden_adoption(task2_8j_2_tables):
    component_table, model_summary, stability_table, prediction_table = task2_8j_2_tables
    bad_component = component_table.copy()
    bad_component.loc[bad_component.index[0], "effective_dimension_adopted"] = True

    errors = validate_temporal_pca_validation_tables(
        bad_component,
        model_summary,
        stability_table,
        prediction_table,
        feature_log_errors=[],
    )
    assert "task2_8j_2_forbidden_true:component:effective_dimension_adopted" in errors
