from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_1_candidate_feature_log import (
    CandidateFeatureLogConfig,
)
from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_4b_4c_4d_4e_prefreeze_validations import (
    PreFreezeValidationConfig,
    build_and_validate_4d_seventh_axis_meaning_residual_audit,
)


def test_task2_8j_4d_seventh_axis_residual_contract_and_boundaries():
    feature_cfg = CandidateFeatureLogConfig(steps=18, seeds=(501, 502), window_sizes=(1, 6, 12))
    cfg = PreFreezeValidationConfig(component_counts=(6, 7), standard_component_count=6, shadow_component_count=7)
    meaning, residual, final, errors, summary = build_and_validate_4d_seventh_axis_meaning_residual_audit(feature_cfg, cfg)

    assert errors == []
    assert not meaning.empty
    assert not residual.empty
    assert not final.empty
    assert summary["adoption_performed"] is False
    assert summary["freeze_performed"] is False
    for frame in [meaning, residual, final]:
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


def test_task2_8j_4d_reports_component_7_features_and_residual_deltas():
    feature_cfg = CandidateFeatureLogConfig(steps=18, seeds=(501, 502), window_sizes=(1, 6, 12))
    cfg = PreFreezeValidationConfig(component_counts=(6, 7), standard_component_count=6, shadow_component_count=7)
    meaning, residual, final, _errors, _summary = build_and_validate_4d_seventh_axis_meaning_residual_audit(feature_cfg, cfg)

    assert set(meaning["component_count"].astype(int)) == {7}
    assert set(meaning["component_index"].astype(int)) == {7}
    assert meaning["abs_feature_weight"].astype(float).ge(0.0).all()
    assert "coordination_lag_high" in set(residual["event_name"].astype(str))
    assert "r2_improvement_7_minus_6" in residual.columns
    assert int(final["top_feature_rows"].iloc[0]) == len(meaning)
    assert str(final["next_task"].iloc[0]).startswith("Task 2-8j-4e")
