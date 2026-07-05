import pytest

from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_1_candidate_feature_log import (
    ALLOWED_INPUT_TRACES,
    CandidateFeatureLogConfig,
    build_and_validate_candidate_feature_log,
    build_candidate_feature_schema,
    build_feature_input_audit,
    validate_candidate_feature_log,
)


@pytest.fixture(scope="module")
def task2_8j_1_result():
    cfg = CandidateFeatureLogConfig(steps=14, seeds=(501, 502), window_sizes=(1, 6, 12))
    return build_and_validate_candidate_feature_log(cfg)


@pytest.fixture(scope="module")
def task2_8j_1_log(task2_8j_1_result):
    feature_log, _audit, _errors, _summary = task2_8j_1_result
    return feature_log


def test_task2_8j_1_contract_and_boundaries(task2_8j_1_result):
    feature_log, input_audit, errors, summary = task2_8j_1_result

    assert errors == []
    assert not feature_log.empty
    assert not input_audit.empty
    assert set(feature_log["validation_only"].astype(bool)) == {True}
    assert set(feature_log["runtime_policy_input"].astype(bool)) == {False}
    assert set(feature_log["fullspec_runtime_connected"].astype(bool)) == {False}
    assert set(feature_log["upper_pressure_connected"].astype(bool)) == {False}
    assert set(feature_log["action_frame_created"].astype(bool)) == {False}
    assert set(feature_log["actionmodule_called"].astype(bool)) == {False}
    assert set(feature_log["canonical_write_performed"].astype(bool)) == {False}
    assert set(feature_log["gk_writeback_performed"].astype(bool)) == {False}
    assert set(feature_log["ot_writeback_performed"].astype(bool)) == {False}
    assert set(feature_log["effective_dimension_extracted"].astype(bool)) == {False}
    assert set(feature_log["dynamics_axis_extracted"].astype(bool)) == {False}
    assert set(feature_log["candidate_feature_log"].astype(bool)) == {True}
    assert summary["rows"] == len(feature_log)
    assert summary["input_audit_status"] == "pass"


def test_task2_8j_1_excludes_hidden_truth_and_raw_trace(task2_8j_1_log):
    assert "v2_hidden_trace" not in set(task2_8j_1_log["source_trace"].astype(str).unique())
    assert set(task2_8j_1_log["hidden_truth_input"].astype(bool)) == {False}
    assert set(task2_8j_1_log["raw_trace_passthrough"].astype(bool)) == {False}
    assert set(task2_8j_1_log["future_information_used"].astype(bool)) == {False}
    assert set(task2_8j_1_log["allowed_for_gt"].astype(bool)) == {True}
    assert set(task2_8j_1_log["source_trace"].astype(str)).issubset(ALLOWED_INPUT_TRACES)


def test_task2_8j_1_includes_required_trace_sources_and_feature_groups(task2_8j_1_log):
    required_sources = {
        "entity_trace",
        "relation_trace",
        "v2_game_trace",
        "v2_resource_trace",
        "v2_information_trace",
    }
    required_groups = {
        "public_state",
        "relation_structure",
        "role_payoff_tendency",
        "resource_structure",
        "information_structure",
        "action_effect_audit",
    }

    assert required_sources.issubset(set(task2_8j_1_log["source_trace"].astype(str).unique()))
    assert required_groups.issubset(set(task2_8j_1_log["feature_group"].astype(str).unique()))


def test_task2_8j_1_contains_temporal_windows(task2_8j_1_log):
    assert {1, 6, 12}.issubset(set(task2_8j_1_log["window_size"].astype(int).unique()))
    temporal = task2_8j_1_log[task2_8j_1_log["temporal_feature"].astype(bool)]
    assert not temporal.empty
    assert temporal["stat_name"].astype(str).str.contains("window_slope").any()
    assert temporal["stat_name"].astype(str).str.contains("window_delta").any()
    assert temporal["input_role"].astype(str).eq("temporal_candidate_feature").any()


def test_task2_8j_1_contains_role_payoff_resource_information_features(task2_8j_1_log):
    feature_names = set(task2_8j_1_log["feature_name"].astype(str).unique())

    assert "short_long_payoff_gap" in feature_names
    assert "cooperate_tendency" in feature_names
    assert "extract_tendency" in feature_names
    assert "resource_pressure" in feature_names
    assert "resource_inequality" in feature_names
    assert "information_distortion_mean" in feature_names
    assert "coordination_lag_mean" in feature_names
    assert "relation_density" in feature_names
    assert "degree_gini" in feature_names


def test_task2_8j_1_input_audit_passes_for_all_sources(task2_8j_1_log):
    audit = build_feature_input_audit(task2_8j_1_log)
    assert not audit.empty
    assert set(audit["audit_status"].astype(str)) == {"pass"}
    overall = audit[audit["source_trace"].astype(str) == "__overall__"].iloc[0]
    assert int(overall["hidden_truth_input_rows"]) == 0
    assert int(overall["raw_trace_passthrough_rows"]) == 0
    assert bool(overall["allowed_for_gt_all"])


def test_task2_8j_1_validator_detects_hidden_trace_mislabel(task2_8j_1_log):
    bad = task2_8j_1_log.copy()
    bad.loc[bad.index[0], "source_trace"] = "v2_hidden_trace"
    bad.loc[bad.index[0], "hidden_truth_input"] = True
    bad.loc[bad.index[0], "allowed_for_gt"] = False

    errors = validate_candidate_feature_log(bad)
    assert "task2_8j_1_hidden_truth_input_true" in errors
    assert "task2_8j_1_hidden_trace_used_as_input" in errors
    assert "task2_8j_1_allowed_for_gt_not_all_true" in errors


def test_task2_8j_1_schema_exposes_required_columns():
    schema = build_candidate_feature_schema()
    assert not schema.empty
    assert {"column", "role", "required"}.issubset(schema.columns)
    assert "feature_value" in set(schema["column"].astype(str))
    assert "hidden_truth_input" in set(schema["column"].astype(str))
