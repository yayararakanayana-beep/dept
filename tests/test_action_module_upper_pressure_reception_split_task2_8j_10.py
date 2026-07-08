from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_6c_v2_structure_change_relation_field_tracking import (
    V2StructureChangeTrackingConfig,
)
from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_10_game_structure_prediction_input_contract import (
    build_and_validate_game_structure_prediction_input_contract,
    validate_game_structure_prediction_input_contract_tables,
)


def _small_tracking_cfg():
    return V2StructureChangeTrackingConfig(steps=18, seeds=(501, 502), window_sizes=(1, 6, 12))


def test_task2_8j_10_prediction_input_contract_boundaries():
    contract, scope, features, readiness, final_summary, errors, summary = (
        build_and_validate_game_structure_prediction_input_contract(_small_tracking_cfg())
    )

    assert errors == []
    assert not contract.empty
    assert not scope.empty
    assert not features.empty
    assert not readiness.empty
    assert not final_summary.empty
    assert summary["gt_main_map_name"] == "static_pca_7"
    assert summary["gt_main_component_count"] == 7
    assert summary["action_effect_prediction_generated"] is False
    assert summary["action_axis_generated"] is False
    assert summary["upper_pressure_generated_here"] is False
    assert summary["real_actionmodule_called"] is False

    for table in [contract, scope, features, readiness, final_summary]:
        assert set(table["validation_only"].astype(bool)) == {True}
        assert set(table["contract_only"].astype(bool)) == {True}
        assert set(table["prediction_input_contract_only"].astype(bool)) == {True}
        assert set(table["game_structure_prediction_route_separate"].astype(bool)) == {True}
        assert set(table["observation_forecast_allowed"].astype(bool)) == {True}
        assert set(table["action_effect_prediction_generated"].astype(bool)) == {False}
        assert set(table["action_axis_generated"].astype(bool)) == {False}
        assert set(table["action_candidate_generated"].astype(bool)) == {False}
        assert set(table["upper_pressure_generated_here"].astype(bool)) == {False}
        assert set(table["prediction_generates_upper_pressure"].astype(bool)) == {False}
        assert set(table["real_actionmodule_called"].astype(bool)) == {False}
        assert set(table["gt_main_map_name"].astype(str)) == {"static_pca_7"}
        assert set(table["gt_main_component_count"].astype(int)) == {7}


def test_task2_8j_10_defines_prediction_without_action_effects():
    contract, scope, features, readiness, final_summary, _errors, summary = (
        build_and_validate_game_structure_prediction_input_contract(_small_tracking_cfg())
    )

    assert set(contract["prediction_route_name"].astype(str)) == {"game_structure_prediction_route"}
    required = str(contract["required_payload_fields"].iloc[0])
    forbidden = str(contract["forbidden_payload_fields"].iloc[0])
    assert "predicted_state_tendency" in required
    assert "predicted_relation_tendency" in required
    assert "action_effect_estimate" in forbidden
    assert "direct_action_weights" in forbidden
    assert set(scope["scope_status"].astype(str)) == {"pass"}
    assert set(features["feature_status"].astype(str)) == {"feature_source_contract_ready"}
    assert bool(readiness["prediction_input_contract_ready"].iloc[0]) is True
    assert int(final_summary["prediction_contract_count"].iloc[0]) == 1
    assert int(final_summary["scope_rule_count"].iloc[0]) == int(final_summary["scope_pass_count"].iloc[0])
    assert int(final_summary["feature_group_count"].iloc[0]) >= 5
    assert "observation_side_forecast" in summary["game_structure_prediction_input_contract_decision"]


def test_task2_8j_10_validator_detects_action_axis_generation():
    contract, scope, features, readiness, final_summary, _errors, _summary = (
        build_and_validate_game_structure_prediction_input_contract(_small_tracking_cfg())
    )
    bad = contract.copy()
    bad.loc[bad.index[0], "action_axis_generated"] = True
    errors = validate_game_structure_prediction_input_contract_tables(bad, scope, features, readiness, final_summary)
    assert "task2_8j_10_forbidden_true:contract:action_axis_generated" in errors
