from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_1_candidate_feature_log import (
    CandidateFeatureLogConfig,
)
from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_6b_v2_state_relation_field_reproduction import (
    V2StateRelationFieldReproductionConfig,
    build_and_validate_v2_state_relation_field_reproduction,
    validate_v2_state_relation_field_reproduction_tables,
)


def _small_feature_cfg():
    return CandidateFeatureLogConfig(steps=18, seeds=(501, 502), window_sizes=(1, 6, 12))


def test_task2_8j_6b_v2_state_relation_field_boundaries():
    state_reproduction, state_timeline, transition_reproduction, relation_consistency, final_summary, errors, summary = (
        build_and_validate_v2_state_relation_field_reproduction(
            _small_feature_cfg(),
            cfg=V2StateRelationFieldReproductionConfig(),
        )
    )

    assert errors == []
    assert not state_reproduction.empty
    assert not state_timeline.empty
    assert not transition_reproduction.empty
    assert not relation_consistency.empty
    assert not final_summary.empty
    assert summary["gt_main_map_name"] == "static_pca_7"
    assert summary["gt_main_component_count"] == 7

    for table in [state_reproduction, state_timeline, transition_reproduction, relation_consistency, final_summary]:
        assert set(table["validation_only"].astype(bool)) == {True}
        assert set(table["incomplete_observation_assumption"].astype(bool)) == {True}
        assert set(table["observable_v2_state_only"].astype(bool)) == {True}
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


def test_task2_8j_6b_reproduces_core_v2_states_and_relations():
    state_reproduction, state_timeline, transition_reproduction, relation_consistency, final_summary, _errors, summary = (
        build_and_validate_v2_state_relation_field_reproduction(
            _small_feature_cfg(),
            cfg=V2StateRelationFieldReproductionConfig(),
        )
    )

    states = set(state_reproduction["macro_signal"].astype(str))
    assert {"relation_lock", "coordination_lag", "information_degradation", "resource_pressure"}.issubset(states)
    assert state_reproduction["state_event_accuracy"].astype(float).between(0.0, 1.0).all()
    assert transition_reproduction["direction_match_rate"].astype(float).between(0.0, 1.0).all()
    assert relation_consistency["relation_strength_gap"].astype(float).ge(0.0).all()
    assert int(final_summary["state_count"].iloc[0]) >= 4
    assert int(final_summary["reproduced_state_count"].iloc[0]) >= 3
    assert int(final_summary["relation_consistency_count"].iloc[0]) > 0
    assert "relation_field" in str(final_summary["v2_state_reproduction_decision"].iloc[0])
    assert "relation_field" in summary["v2_state_reproduction_decision"]


def test_task2_8j_6b_validator_detects_axis_mutation():
    state_reproduction, state_timeline, transition_reproduction, relation_consistency, final_summary, _errors, _summary = (
        build_and_validate_v2_state_relation_field_reproduction(
            _small_feature_cfg(),
            cfg=V2StateRelationFieldReproductionConfig(),
        )
    )
    bad = state_reproduction.copy()
    bad.loc[bad.index[0], "axis_mutation_performed"] = True

    errors = validate_v2_state_relation_field_reproduction_tables(
        bad,
        state_timeline,
        transition_reproduction,
        relation_consistency,
        final_summary,
    )
    assert "task2_8j_6b_forbidden_true:state_reproduction:axis_mutation_performed" in errors


# Touch marker: rerun after stale pre-fix workflow attempt.
