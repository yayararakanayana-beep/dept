from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_1_candidate_feature_log import (
    CandidateFeatureLogConfig,
)
from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_4b_4c_4d_4e_prefreeze_validations import (
    PreFreezeValidationConfig,
    build_and_validate_4b_multi_scenario_reidentification,
)


def test_task2_8j_4b_multi_scenario_contract_and_boundaries():
    feature_cfg = CandidateFeatureLogConfig(steps=18, seeds=(501, 502), window_sizes=(1, 6, 12))
    cfg = PreFreezeValidationConfig(component_counts=(3, 6, 7), standard_component_count=6, shadow_component_count=7)
    table, final, errors, summary = build_and_validate_4b_multi_scenario_reidentification(feature_cfg, cfg)

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


def test_task2_8j_4b_compares_3_6_7_and_has_multiple_derived_scenarios():
    feature_cfg = CandidateFeatureLogConfig(steps=18, seeds=(501, 502), window_sizes=(1, 6, 12))
    cfg = PreFreezeValidationConfig(component_counts=(3, 6, 7), standard_component_count=6, shadow_component_count=7)
    table, final, _errors, _summary = build_and_validate_4b_multi_scenario_reidentification(feature_cfg, cfg)

    assert set(table["component_count"].astype(int)) == {3, 6, 7}
    assert table["derived_scenario_count"].astype(int).max() >= 2
    assert table["derived_scenario_accuracy"].astype(float).between(0.0, 1.0).all()
    assert table["derived_scenario_balanced_accuracy"].astype(float).between(0.0, 1.0).all()
    assert int(final["standard_component_count"].iloc[0]) == 6
    assert int(final["shadow_component_count"].iloc[0]) == 7
    assert str(final["next_task"].iloc[0]).startswith("Task 2-8j-4c")
