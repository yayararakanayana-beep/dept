from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_1_candidate_feature_log import (
    CandidateFeatureLogConfig,
)
from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_6_macro_game_relation_field_validation import (
    MacroGameRelationFieldConfig,
)
from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_6b_v2_state_relation_field_reproduction import (
    V2StateRelationFieldReproductionConfig,
    build_and_validate_v2_state_relation_field_reproduction,
    validate_v2_state_reproduction_tables,
)


def test_task2_8j_6b_v2_state_reproduction_boundaries():
    feature_cfg = CandidateFeatureLogConfig(steps=18, seeds=(501, 502), window_sizes=(1, 6, 12))
    state_metrics, assignment, transition, edge_consistency, final_summary, errors, summary = build_and_validate_v2_state_relation_field_reproduction(
        feature_cfg,
        MacroGameRelationFieldConfig(),
        V2StateRelationFieldReproductionConfig(),
    )

    assert errors == []
    assert not state_metrics.empty
    assert not assignment.empty
    assert not transition.empty
    assert not edge_consistency.empty
    assert not final_summary.empty
    assert summary["gt_main_map_name"] == "static_pca_7"
    assert summary["gt_main_component_count"] == 7

    for table in [state_metrics, assignment, transition, edge_consistency, final_summary]:
        assert set(table["validation_only"].astype(bool)) == {True}
        assert set(table["incomplete_observation_assumption"].astype(bool)) == {True}
        assert set(table["observable_state_proxy_only"].astype(bool)) == {True}
        assert set(table["gt_main_map_name"].astype(str)) == {"static_pca_7"}
        assert set(table["gt_main_component_count"].astype(int)) == {7}
        for col in [
            "runtime_policy_input",
            "fullspec_runtime_connected",
            "upper_pressure_connected",
            "action_frame_created",
            "actionmodule_called",
            "canonical_write_performed",
            "gk_writeback_performed",
            "ot_writeback_performed",
            "effective_dimension_refit_performed",
            "axis_mutation_performed",
            "residual_auxiliary_injected_into_gt_main",
            "dynamics_axis_extracted_for_action",
            "action_weight_converted",
            "hidden_truth_input",
            "future_information_used",
        ]:
            assert set(table[col].astype(bool)) == {False}


def test_task2_8j_6b_reproduces_observable_v2_state_structure():
    feature_cfg = CandidateFeatureLogConfig(steps=18, seeds=(501, 502), window_sizes=(1, 6, 12))
    state_metrics, assignment, transition, edge_consistency, final_summary, _errors, summary = build_and_validate_v2_state_relation_field_reproduction(
        feature_cfg,
        MacroGameRelationFieldConfig(),
        V2StateRelationFieldReproductionConfig(),
    )

    assert len(set(assignment["observed_state_label"].astype(str))) >= 2
    assert state_metrics["f1"].astype(float).between(0.0, 1.0).all()
    assert transition["transition_f1"].astype(float).between(0.0, 1.0).all()
    assert edge_consistency["relation_sign_match"].isin([True, False]).all()
    assert int(final_summary["state_assignment_count"].iloc[0]) == len(assignment)
    assert int(final_summary["edge_count"].iloc[0]) == len(edge_consistency)
    assert "v2_state_structure" in str(final_summary["v2_state_reproduction_decision"].iloc[0])
    assert "v2_state_structure" in summary["v2_state_reproduction_decision"]


def test_task2_8j_6b_validator_detects_hidden_truth_input():
    feature_cfg = CandidateFeatureLogConfig(steps=18, seeds=(501, 502), window_sizes=(1, 6, 12))
    state_metrics, assignment, transition, edge_consistency, final_summary, _errors, _summary = build_and_validate_v2_state_relation_field_reproduction(
        feature_cfg,
        MacroGameRelationFieldConfig(),
        V2StateRelationFieldReproductionConfig(),
    )
    bad = state_metrics.copy()
    bad.loc[bad.index[0], "hidden_truth_input"] = True

    errors = validate_v2_state_reproduction_tables(bad, assignment, transition, edge_consistency, final_summary)
    assert "task2_8j_6b_forbidden_true:state_metrics:hidden_truth_input" in errors
