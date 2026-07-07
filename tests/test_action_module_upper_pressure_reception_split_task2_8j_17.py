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
from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_17_action_candidate_minimal_eligibility_contract import (
    ActionCandidateMinimalEligibilityContractConfig,
    build_and_validate_action_candidate_minimal_eligibility_contract,
    validate_action_candidate_minimal_eligibility_tables,
)


def _small_tracking_cfg():
    return V2StructureChangeTrackingConfig(steps=18, seeds=(501, 502), window_sizes=(1, 6, 12))


def _small_prediction_cfg():
    return GameStructurePredictionEnvelopeDryRunConfig(max_relation_envelopes=4)


def _small_bundle_cfg():
    return ActionAxisMaterialBundleDryRunConfig(max_bundles=4)


def _small_axis_cfg():
    return ActionAxisDryRunGenerationConfig(max_axes=4)


def test_task2_8j_17_minimal_eligibility_boundaries():
    eligibility, carry, checks, final_summary, errors, summary = (
        build_and_validate_action_candidate_minimal_eligibility_contract(
            tracking_cfg=_small_tracking_cfg(),
            prediction_envelope_cfg=_small_prediction_cfg(),
            bundle_cfg=_small_bundle_cfg(),
            axis_cfg=_small_axis_cfg(),
            cfg=ActionCandidateMinimalEligibilityContractConfig(),
        )
    )

    assert errors == []
    assert not eligibility.empty
    assert not carry.empty
    assert not checks.empty
    assert not final_summary.empty
    assert summary["gt_main_map_name"] == "static_pca_7"
    assert summary["gt_main_component_count"] == 7
    assert summary["expected_value_final_judgment_performed"] is False
    assert summary["risk_final_judgment_performed"] is False
    assert summary["action_effect_prediction_generated"] is False
    assert summary["action_candidate_generated"] is False
    assert summary["concrete_action_generated"] is False
    assert summary["axis_executed"] is False
    assert summary["real_actionmodule_called"] is False

    for table in [eligibility, carry, checks, final_summary]:
        assert set(table["validation_only"].astype(bool)) == {True}
        assert set(table["minimal_eligibility_contract_only"].astype(bool)) == {True}
        assert set(table["candidate_form_contract_only"].astype(bool)) == {True}
        assert set(table["lightweight_risk_management_only"].astype(bool)) == {True}
        assert set(table["trace_required"].astype(bool)) == {True}
        assert set(table["no_op_carry_forward_required"].astype(bool)) == {True}
        assert set(table["release_required"].astype(bool)) == {True}
        assert set(table["rollback_required"].astype(bool)) == {True}
        assert set(table["audit_required"].astype(bool)) == {True}
        assert set(table["weak_strength_required"].astype(bool)) == {True}
        assert set(table["non_execution_required"].astype(bool)) == {True}
        assert set(table["effect_prediction_required_later"].astype(bool)) == {True}
        assert set(table["risk_review_required_later"].astype(bool)) == {True}
        assert set(table["expected_value_review_required_later"].astype(bool)) == {True}
        assert set(table["expected_value_final_judgment_performed"].astype(bool)) == {False}
        assert set(table["risk_final_judgment_performed"].astype(bool)) == {False}
        assert set(table["action_effect_prediction_generated"].astype(bool)) == {False}
        assert set(table["action_candidate_generated"].astype(bool)) == {False}
        assert set(table["concrete_action_generated"].astype(bool)) == {False}
        assert set(table["axis_executed"].astype(bool)) == {False}
        assert set(table["gt_main_map_name"].astype(str)) == {"static_pca_7"}
        assert set(table["gt_main_component_count"].astype(int)) == {7}


def test_task2_8j_17_deferred_review_and_no_op_carry_forward():
    eligibility, carry, checks, final_summary, _errors, summary = (
        build_and_validate_action_candidate_minimal_eligibility_contract(
            tracking_cfg=_small_tracking_cfg(),
            prediction_envelope_cfg=_small_prediction_cfg(),
            bundle_cfg=_small_bundle_cfg(),
            axis_cfg=_small_axis_cfg(),
            cfg=ActionCandidateMinimalEligibilityContractConfig(),
        )
    )

    assert set(eligibility["eligibility_status"].astype(str)) == {"minimal_eligibility_completed_without_candidate_generation"}
    assert eligibility["needs_effect_prediction"].astype(bool).all()
    assert eligibility["needs_risk_review"].astype(bool).all()
    assert eligibility["needs_expected_value_review"].astype(bool).all()
    assert carry["no_op_default_preserved"].astype(bool).all()
    assert carry["no_op_required_when_uncertain"].astype(bool).all()
    assert set(checks["check_status"].astype(str)) == {"pass"}
    assert int(final_summary["eligibility_row_count"].iloc[0]) == len(eligibility)
    assert int(final_summary["carry_forward_row_count"].iloc[0]) == len(carry)
    assert int(final_summary["contract_check_count"].iloc[0]) == int(final_summary["contract_check_pass_count"].iloc[0])
    assert "without_final_judgment_or_generation" in summary["action_candidate_minimal_eligibility_contract_decision"]


def test_task2_8j_17_validator_detects_candidate_generation():
    eligibility, carry, checks, final_summary, _errors, _summary = (
        build_and_validate_action_candidate_minimal_eligibility_contract(
            tracking_cfg=_small_tracking_cfg(),
            prediction_envelope_cfg=_small_prediction_cfg(),
            bundle_cfg=_small_bundle_cfg(),
            axis_cfg=_small_axis_cfg(),
            cfg=ActionCandidateMinimalEligibilityContractConfig(),
        )
    )
    bad = eligibility.copy()
    bad.loc[bad.index[0], "action_candidate_generated"] = True
    errors = validate_action_candidate_minimal_eligibility_tables(bad, carry, checks, final_summary)
    assert "task2_8j_17_forbidden_true:eligibility:action_candidate_generated" in errors
