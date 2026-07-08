from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_1_candidate_feature_log import (
    CandidateFeatureLogConfig,
)
from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_4b_4c_4d_4e_prefreeze_validations import (
    PreFreezeValidationConfig,
    build_and_validate_4c_seed_rolling_stability,
)


def test_task2_8j_4c_seed_rolling_stability_contract_and_boundaries():
    feature_cfg = CandidateFeatureLogConfig(steps=18, seeds=(501, 502), window_sizes=(1, 6, 12))
    cfg = PreFreezeValidationConfig(component_counts=(3, 6, 7), standard_component_count=6, shadow_component_count=7)
    table, final, errors, summary = build_and_validate_4c_seed_rolling_stability(feature_cfg, cfg)

    assert errors == []
    assert not table.empty
    assert not final.empty
    assert summary["adoption_performed"] is False
    assert summary["freeze_performed"] is False
    for frame in [table, final]:
        assert set(frame["validation_only"].astype(bool)) == {True}
        for col in [
            "runtime_policy_input",
            "fullspec_runtime_connected",
            "upper_pressure_connected",
            "action_frame_created",
            "actionmodule_called",
            "canonical_write_performed",
            "gk_writeback_performed",
            "ot_writeback_performed",
            "effective_dimension_adopted",
            "effective_dimension_frozen",
            "dynamics_axis_extracted",
            "action_weight_converted",
            "hidden_truth_input",
        ]:
            assert set(frame[col].astype(bool)) == {False}


def test_task2_8j_4c_scores_are_bounded_and_compare_6_7():
    feature_cfg = CandidateFeatureLogConfig(steps=18, seeds=(501, 502), window_sizes=(1, 6, 12))
    cfg = PreFreezeValidationConfig(component_counts=(3, 6, 7), standard_component_count=6, shadow_component_count=7)
    table, final, _errors, _summary = build_and_validate_4c_seed_rolling_stability(feature_cfg, cfg)

    assert set(table["component_count"].astype(int)) == {3, 6, 7}
    for col in ["mean_subspace_similarity", "projection_drift_score", "seed_score_consistency", "rolling_stability_score"]:
        assert table[col].astype(float).between(0.0, 1.0).all()
    assert int(final["standard_component_count"].iloc[0]) == 6
    assert int(final["shadow_component_count"].iloc[0]) == 7
    assert str(final["next_task"].iloc[0]).startswith("Task 2-8j-4d")
