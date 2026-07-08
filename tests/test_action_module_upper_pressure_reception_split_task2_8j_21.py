from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_21_gt_relation_ot_actionmodule_non_execution_loop import (
    GtRelationOtActionModuleNonExecutionLoopConfig,
    build_and_validate_gt_relation_ot_actionmodule_non_execution_loop,
    validate_gt_relation_ot_actionmodule_non_execution_loop_tables,
)


def test_task2_8j_21_non_execution_loop_boundaries():
    packets, review, checks, final_summary, errors, summary = build_and_validate_gt_relation_ot_actionmodule_non_execution_loop(
        cfg=GtRelationOtActionModuleNonExecutionLoopConfig(max_packets=12)
    )
    assert errors == []
    assert not packets.empty
    assert not review.empty
    assert not checks.empty
    assert not final_summary.empty
    assert summary["gt_main_map_name"] == "static_pca_7"
    assert summary["gt_main_component_count"] == 7
    assert summary["task20_ready"] is True
    assert summary["action_candidate_generated"] is False
    assert summary["action_effect_prediction_generated"] is False
    assert summary["effect_prediction_model_executed"] is False
    assert summary["concrete_action_generated"] is False
    assert summary["axis_executed"] is False
    assert summary["real_actionmodule_called"] is False
    assert summary["validation_errors"] == []

    for table in [packets, review, checks, final_summary]:
        assert set(table["validation_only"].astype(bool)) == {True}
        assert set(table["non_execution_loop_only"].astype(bool)) == {True}
        assert set(table["system_visible_information_only"].astype(bool)) == {True}
        assert set(table["gt_to_relation_to_ot_to_actionmodule_route"].astype(bool)) == {True}
        assert set(table["semantic_recipe_primary_key_forbidden"].astype(bool)) == {True}
        assert set(table["terrain_information_primary_required"].astype(bool)) == {True}
        assert set(table["risk_label_used_only_for_evaluation"].astype(bool)) == {True}
        assert set(table["no_op_preserved"].astype(bool)) == {True}
        assert set(table["direction_selection_required"].astype(bool)) == {True}
        assert set(table["state_dependence_required"].astype(bool)) == {True}
        assert set(table["immediate_release_required"].astype(bool)) == {True}
        assert set(table["rollback_required"].astype(bool)) == {True}
        assert set(table["audit_required"].astype(bool)) == {True}
        assert set(table["loop_executed"].astype(bool)) == {False}
        assert set(table["action_candidate_generated"].astype(bool)) == {False}
        assert set(table["action_effect_prediction_generated"].astype(bool)) == {False}
        assert set(table["effect_prediction_model_executed"].astype(bool)) == {False}
        assert set(table["axis_executed"].astype(bool)) == {False}
        assert set(table["real_actionmodule_called"].astype(bool)) == {False}
        assert set(table["hidden_truth_input"].astype(bool)) == {False}
        assert set(table["future_information_used"].astype(bool)) == {False}


def test_task2_8j_21_loop_packet_and_review_content():
    packets, review, checks, final_summary, errors, summary = build_and_validate_gt_relation_ot_actionmodule_non_execution_loop(
        cfg=GtRelationOtActionModuleNonExecutionLoopConfig(max_packets=18)
    )
    assert errors == []
    assert len(packets) == len(review)
    assert packets["no_op_baseline_carried"].astype(bool).all()
    assert packets["release_condition_carried"].astype(bool).all()
    assert packets["rollback_condition_carried"].astype(bool).all()
    assert packets["audit_condition_carried"].astype(bool).all()
    assert review["terrain_material_complete"].astype(bool).all()
    assert review["route_trace_complete"].astype(bool).all()
    assert review["candidate_form_deferred"].astype(bool).all()
    assert review["effect_prediction_deferred"].astype(bool).all()
    assert set(checks["check_status"].astype(str)) == {"pass"}
    assert int(final_summary["loop_packet_count"].iloc[0]) == len(packets)
    assert int(final_summary["loop_check_count"].iloc[0]) == int(final_summary["loop_check_pass_count"].iloc[0])
    assert "ready" in summary["gt_relation_ot_actionmodule_non_execution_loop_decision"]


def test_task2_8j_21_validator_detects_runtime_call():
    packets, review, checks, final_summary, _errors, _summary = build_and_validate_gt_relation_ot_actionmodule_non_execution_loop(
        cfg=GtRelationOtActionModuleNonExecutionLoopConfig(max_packets=8)
    )
    bad = packets.copy()
    bad.loc[bad.index[0], "real_actionmodule_called"] = True
    errors = validate_gt_relation_ot_actionmodule_non_execution_loop_tables(bad, review, checks, final_summary)
    assert "task2_8j_21_forbidden_true:loop_packets:real_actionmodule_called" in errors
