from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_6c_v2_structure_change_relation_field_tracking import (
    V2StructureChangeTrackingConfig,
)
from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_11_game_structure_prediction_envelope_dry_run import (
    GameStructurePredictionEnvelopeDryRunConfig,
)
from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_14_action_axis_material_bundle_dry_run import (
    ActionAxisMaterialBundleDryRunConfig,
)
from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_15_action_axis_dry_run_generation import (
    ActionAxisDryRunGenerationConfig,
)
from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_16_action_axis_non_execution_review_no_op import (
    ActionAxisNonExecutionReviewConfig,
    build_and_validate_action_axis_non_execution_review,
    validate_action_axis_non_execution_review_tables,
)


def _small_tracking_cfg():
    return V2StructureChangeTrackingConfig(steps=18, seeds=(501, 502), window_sizes=(1, 6, 12))


def _small_prediction_cfg():
    return GameStructurePredictionEnvelopeDryRunConfig(max_relation_envelopes=4)


def _small_bundle_cfg():
    return ActionAxisMaterialBundleDryRunConfig(max_bundles=4)


def _small_axis_cfg():
    return ActionAxisDryRunGenerationConfig(max_axes=4)


def _small_review_cfg():
    return ActionAxisNonExecutionReviewConfig()


def test_task2_8j_16_non_execution_review_boundaries():
    review, no_op, checks, final_summary, errors, summary = (
        build_and_validate_action_axis_non_execution_review(
            tracking_cfg=_small_tracking_cfg(),
            prediction_envelope_cfg=_small_prediction_cfg(),
            bundle_cfg=_small_bundle_cfg(),
            axis_cfg=_small_axis_cfg(),
            cfg=_small_review_cfg(),
        )
    )

    assert errors == []
    assert not review.empty
    assert not no_op.empty
    assert not checks.empty
    assert not final_summary.empty
    assert summary["gt_main_map_name"] == "static_pca_7"
    assert summary["gt_main_component_count"] == 7
    assert summary["concrete_action_generated"] is False
    assert summary["action_candidate_generated"] is False
    assert summary["action_effect_prediction_generated"] is False
    assert summary["axis_executed"] is False
    assert summary["real_actionmodule_called"] is False

    for table in [review, no_op, checks, final_summary]:
        assert set(table["validation_only"].astype(bool)) == {True}
        assert set(table["non_execution_review_only"].astype(bool)) == {True}
        assert set(table["no_op_comparison_only"].astype(bool)) == {True}
        assert set(table["action_axis_review_only"].astype(bool)) == {True}
        assert set(table["source_action_axis_required"].astype(bool)) == {True}
        assert set(table["direction_selection_review_required"].astype(bool)) == {True}
        assert set(table["state_dependent_trigger_review_required"].astype(bool)) == {True}
        assert set(table["immediate_release_review_required"].astype(bool)) == {True}
        assert set(table["weak_local_reversible_review_required"].astype(bool)) == {True}
        assert set(table["no_op_baseline_comparison_required"].astype(bool)) == {True}
        assert set(table["rollback_review_required"].astype(bool)) == {True}
        assert set(table["audit_gate_review_required"].astype(bool)) == {True}
        assert set(table["route_tags_preserved"].astype(bool)) == {True}
        assert set(table["source_traces_preserved"].astype(bool)) == {True}
        assert set(table["v8_local_audit_reserved_optional"].astype(bool)) == {True}
        assert set(table["exploration_axis_input_reserved_not_used"].astype(bool)) == {True}
        assert set(table["concrete_action_generated"].astype(bool)) == {False}
        assert set(table["action_candidate_generated"].astype(bool)) == {False}
        assert set(table["action_effect_prediction_generated"].astype(bool)) == {False}
        assert set(table["axis_executed"].astype(bool)) == {False}
        assert set(table["real_actionmodule_called"].astype(bool)) == {False}
        assert set(table["gt_main_map_name"].astype(str)) == {"static_pca_7"}
        assert set(table["gt_main_component_count"].astype(int)) == {7}


def test_task2_8j_16_review_and_no_op_content_ready():
    review, no_op, checks, final_summary, _errors, summary = (
        build_and_validate_action_axis_non_execution_review(
            tracking_cfg=_small_tracking_cfg(),
            prediction_envelope_cfg=_small_prediction_cfg(),
            bundle_cfg=_small_bundle_cfg(),
            axis_cfg=_small_axis_cfg(),
            cfg=_small_review_cfg(),
        )
    )

    assert set(review["review_status"].astype(str)) == {"review_completed_non_executable"}
    assert review["release_review_status"].astype(str).str.startswith("pass").all()
    assert review["rollback_review_status"].astype(str).str.startswith("pass").all()
    assert review["audit_review_status"].astype(str).str.startswith("pass").all()
    assert review["strength_review_status"].astype(str).str.startswith("pass").all()
    assert review["trace_review_status"].astype(str).str.startswith("pass").all()
    assert no_op["no_op_default_preserved"].astype(bool).all()
    assert no_op["no_op_required_when_uncertain"].astype(bool).all()
    assert set(checks["check_status"].astype(str)) == {"pass"}
    assert int(final_summary["reviewed_axis_count"].iloc[0]) == len(review)
    assert int(final_summary["no_op_comparison_count"].iloc[0]) == len(no_op)
    assert int(final_summary["review_check_count"].iloc[0]) == int(final_summary["review_check_pass_count"].iloc[0])
    assert "ready_without_execution" in summary["action_axis_non_execution_review_decision"]


def test_task2_8j_16_validator_detects_candidate_generation():
    review, no_op, checks, final_summary, _errors, _summary = (
        build_and_validate_action_axis_non_execution_review(
            tracking_cfg=_small_tracking_cfg(),
            prediction_envelope_cfg=_small_prediction_cfg(),
            bundle_cfg=_small_bundle_cfg(),
            axis_cfg=_small_axis_cfg(),
            cfg=_small_review_cfg(),
        )
    )
    bad = review.copy()
    bad.loc[bad.index[0], "action_candidate_generated"] = True
    errors = validate_action_axis_non_execution_review_tables(bad, no_op, checks, final_summary)
    assert "task2_8j_16_forbidden_true:review:action_candidate_generated" in errors
