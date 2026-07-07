import pytest

from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_1_candidate_feature_log import (
    CandidateFeatureLogConfig,
)
from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_4_game_structure_reidentification import (
    GameStructureReidentificationConfig,
    build_and_validate_game_structure_reidentification,
    validate_game_structure_reidentification_tables,
)


@pytest.fixture(scope="module")
def task2_8j_4_result():
    feature_cfg = CandidateFeatureLogConfig(steps=18, seeds=(501, 502), window_sizes=(1, 6, 12))
    reid_cfg = GameStructureReidentificationConfig(component_counts=(3, 6, 7), standard_component_count=6, shadow_component_count=7)
    return build_and_validate_game_structure_reidentification(feature_cfg=feature_cfg, reid_cfg=reid_cfg)


@pytest.fixture(scope="module")
def task2_8j_4_tables(task2_8j_4_result):
    scenario_table, event_table, comparison_table, final_summary, _errors, _summary = task2_8j_4_result
    return scenario_table, event_table, comparison_table, final_summary


def test_task2_8j_4_contract_and_boundaries(task2_8j_4_result):
    scenario_table, event_table, comparison_table, final_summary, errors, summary = task2_8j_4_result

    assert errors == []
    for table in [scenario_table, event_table, comparison_table, final_summary]:
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

    assert summary["adoption_performed"] is False
    assert summary["freeze_performed"] is False


def test_task2_8j_4_compares_lightweight_standard_and_shadow_maps(task2_8j_4_tables):
    _scenario_table, _event_table, comparison_table, final_summary = task2_8j_4_tables

    assert set(comparison_table["component_count"].astype(int)) == {3, 6, 7}
    roles = set(comparison_table["map_role"].astype(str))
    assert "lightweight_coarse_map" in roles
    assert "standard_6_axis_map" in roles
    assert "shadow_7_axis_expansion_map" in roles
    assert int(final_summary["standard_component_count"].iloc[0]) == 6
    assert int(final_summary["shadow_component_count"].iloc[0]) == 7


def test_task2_8j_4_reidentification_scores_are_bounded(task2_8j_4_tables):
    scenario_table, event_table, comparison_table, _final_summary = task2_8j_4_tables

    assert scenario_table["scenario_reidentification_accuracy"].astype(float).between(0.0, 1.0).all()
    for col in ["event_accuracy", "event_balanced_accuracy", "event_f1", "event_prevalence"]:
        assert event_table[col].astype(float).between(0.0, 1.0).all()
    for col in [
        "scenario_accuracy",
        "mean_event_balanced_accuracy",
        "mean_event_f1",
        "information_quality_balanced_accuracy",
        "coordination_lag_balanced_accuracy",
        "structure_reidentification_score",
    ]:
        assert comparison_table[col].astype(float).between(0.0, 1.0).all()


def test_task2_8j_4_information_and_coordination_events_are_present(task2_8j_4_tables):
    _scenario_table, event_table, comparison_table, _final_summary = task2_8j_4_tables

    names = set(event_table["event_name"].astype(str))
    assert "information_quality_low" in names
    assert "coordination_lag_high" in names
    assert "relation_lock_high" in names
    assert comparison_table["information_quality_balanced_accuracy"].notna().all()
    assert comparison_table["coordination_lag_balanced_accuracy"].notna().all()


def test_task2_8j_4_final_summary_is_non_adopting(task2_8j_4_tables):
    _scenario_table, _event_table, comparison_table, final_summary = task2_8j_4_tables

    assert bool(final_summary["adoption_performed"].iloc[0]) is False
    assert bool(final_summary["freeze_performed"].iloc[0]) is False
    assert str(final_summary["next_task"].iloc[0]).startswith("Task 2-8j-5")
    assert str(final_summary["baseline_update_worth_check"].iloc[0]) in {
        "yes_shadow_7_beats_standard_6",
        "weak_shadow_7_advantage",
        "no_clear_replacement_value_yet",
        "insufficient_rows",
    }
    assert int(comparison_table.sort_values("structure_reidentification_score", ascending=False)["component_count"].iloc[0]) in {3, 6, 7}


def test_task2_8j_4_validator_detects_forbidden_freeze(task2_8j_4_tables):
    scenario_table, event_table, comparison_table, final_summary = task2_8j_4_tables
    bad_summary = final_summary.copy()
    bad_summary.loc[bad_summary.index[0], "freeze_performed"] = True
    bad_summary.loc[bad_summary.index[0], "effective_dimension_frozen"] = True

    errors = validate_game_structure_reidentification_tables(
        scenario_table,
        event_table,
        comparison_table,
        bad_summary,
        GameStructureReidentificationConfig(component_counts=(3, 6, 7), standard_component_count=6, shadow_component_count=7),
    )
    assert "task2_8j_4_forbidden_true:final_summary:effective_dimension_frozen" in errors
    assert "task2_8j_4_freeze_performed_true" in errors
