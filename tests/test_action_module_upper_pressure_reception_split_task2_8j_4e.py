from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_1_candidate_feature_log import (
    CandidateFeatureLogConfig,
)
from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_4b_4c_4d_4e_prefreeze_validations import (
    PreFreezeValidationConfig,
    build_and_validate_4e_negative_control_leakage_audit,
)


def test_task2_8j_4e_negative_control_contract_and_boundaries():
    feature_cfg = CandidateFeatureLogConfig(steps=18, seeds=(501, 502), window_sizes=(1, 6, 12))
    cfg = PreFreezeValidationConfig(component_counts=(7,), standard_component_count=6, shadow_component_count=7)
    control, leakage, final, errors, summary = build_and_validate_4e_negative_control_leakage_audit(feature_cfg, cfg)

    assert errors == []
    assert not control.empty
    assert not leakage.empty
    assert not final.empty
    assert summary["adoption_performed"] is False
    assert summary["freeze_performed"] is False
    for frame in [control, leakage, final]:
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


def test_task2_8j_4e_reports_negative_controls_and_no_leakage():
    feature_cfg = CandidateFeatureLogConfig(steps=18, seeds=(501, 502), window_sizes=(1, 6, 12))
    cfg = PreFreezeValidationConfig(component_counts=(7,), standard_component_count=6, shadow_component_count=7)
    control, leakage, final, _errors, _summary = build_and_validate_4e_negative_control_leakage_audit(feature_cfg, cfg)

    assert "coordination_lag_high" in set(control["event_name"].astype(str))
    assert control["true_balanced_accuracy"].astype(float).between(0.0, 1.0).all()
    assert control["shuffled_balanced_accuracy"].astype(float).between(0.0, 1.0).all()
    assert set(leakage["component_count"].astype(int)) == {7}
    assert set(leakage["hidden_truth_input_detected"].astype(bool)) == {False}
    assert str(leakage["leakage_audit_status"].iloc[0]) == "pass"
    assert bool(final["hidden_truth_input_detected"].iloc[0]) is False
    assert str(final["next_task"].iloc[0]).startswith("Task 2-8j-5")
