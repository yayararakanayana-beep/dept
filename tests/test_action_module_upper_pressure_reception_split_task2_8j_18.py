from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_18_action_module_failure_history_prediction_terrain_principles import (
    build_and_validate_action_module_failure_history_prediction_terrain_principles,
    validate_action_module_failure_history_review_tables,
)


def test_task2_8j_18_failure_history_review_boundaries():
    failure_history, prediction_needs, principles, checks, final_summary, errors, summary = (
        build_and_validate_action_module_failure_history_prediction_terrain_principles()
    )

    assert errors == []
    assert not failure_history.empty
    assert not prediction_needs.empty
    assert not principles.empty
    assert not checks.empty
    assert not final_summary.empty
    assert summary["gt_main_map_name"] == "static_pca_7"
    assert summary["gt_main_component_count"] == 7
    assert summary["action_candidate_generated"] is False
    assert summary["action_effect_prediction_generated"] is False
    assert summary["effect_prediction_model_executed"] is False
    assert summary["concrete_action_generated"] is False
    assert summary["axis_executed"] is False
    assert summary["real_actionmodule_called"] is False

    for table in [failure_history, prediction_needs, principles, checks, final_summary]:
        assert set(table["validation_only"].astype(bool)) == {True}
        assert set(table["failure_history_review_only"].astype(bool)) == {True}
        assert set(table["prediction_necessity_review_only"].astype(bool)) == {True}
        assert set(table["terrain_action_principle_freeze_only"].astype(bool)) == {True}
        assert set(table["semantic_recipe_primary_key_forbidden"].astype(bool)) == {True}
        assert set(table["terrain_information_primary_required"].astype(bool)) == {True}
        assert set(table["direction_selection_required"].astype(bool)) == {True}
        assert set(table["state_dependence_required"].astype(bool)) == {True}
        assert set(table["immediate_release_required"].astype(bool)) == {True}
        assert set(table["rollback_required"].astype(bool)) == {True}
        assert set(table["audit_required"].astype(bool)) == {True}
        assert set(table["no_op_preserved"].astype(bool)) == {True}
        assert set(table["meaning_labels_explanation_only"].astype(bool)) == {True}
        assert set(table["v2_oracle_results_not_direct_action_input"].astype(bool)) == {True}
        assert set(table["full_loop_action_must_use_system_visible_information"].astype(bool)) == {True}
        assert set(table["prediction_required_before_final_expected_value_review"].astype(bool)) == {True}
        assert set(table["action_candidate_generated"].astype(bool)) == {False}
        assert set(table["action_effect_prediction_generated"].astype(bool)) == {False}
        assert set(table["effect_prediction_model_executed"].astype(bool)) == {False}
        assert set(table["axis_executed"].astype(bool)) == {False}
        assert set(table["gt_main_map_name"].astype(str)) == {"static_pca_7"}
        assert set(table["gt_main_component_count"].astype(int)) == {7}


def test_task2_8j_18_failure_lessons_and_prediction_need_are_present():
    failure_history, prediction_needs, principles, checks, final_summary, _errors, summary = (
        build_and_validate_action_module_failure_history_prediction_terrain_principles()
    )

    failure_ids = set(failure_history["failure_id"].astype(str))
    assert "early_pressure_compression" in failure_ids
    assert "direct_action_channel" in failure_ids
    assert "primitive_substitution_partial" in failure_ids
    assert "wall_like_intervention" in failure_ids
    assert "semantic_recipe_overfit" in failure_ids
    assert "prediction_gap" in failure_ids

    principle_names = set(principles["principle_name"].astype(str))
    assert "terrain_first_semantics_later" in principle_names
    assert "direction_selection" in principle_names
    assert "state_dependence" in principle_names
    assert "immediate_release" in principle_names
    assert "soft_terrain_operator" in principle_names
    assert "prediction_before_final_judgment" in principle_names
    assert "oracle_is_hint_not_input" in principle_names

    assert set(checks["check_status"].astype(str)) == {"pass"}
    assert int(final_summary["failure_review_count"].iloc[0]) == len(failure_history)
    assert int(final_summary["prediction_need_count"].iloc[0]) == len(prediction_needs)
    assert int(final_summary["terrain_principle_count"].iloc[0]) == len(principles)
    assert int(final_summary["review_check_count"].iloc[0]) == int(final_summary["review_check_pass_count"].iloc[0])
    assert "terrain_action_principles_frozen" in summary["action_module_failure_history_review_decision"]


def test_task2_8j_18_validator_detects_semantic_recipe_regression():
    failure_history, prediction_needs, principles, checks, final_summary, _errors, _summary = (
        build_and_validate_action_module_failure_history_prediction_terrain_principles()
    )
    bad = principles.copy()
    bad.loc[bad.index[0], "semantic_recipe_primary_key_forbidden"] = False
    errors = validate_action_module_failure_history_review_tables(failure_history, prediction_needs, bad, checks, final_summary)
    assert "task2_8j_18_required_true_not_all_true:principles:semantic_recipe_primary_key_forbidden" in errors
