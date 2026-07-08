from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_6c_v2_structure_change_relation_field_tracking import (
    V2StructureChangeTrackingConfig,
)
from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_11_game_structure_prediction_envelope_dry_run import (
    GameStructurePredictionEnvelopeDryRunConfig,
)
from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_13_action_axis_material_contract import (
    build_and_validate_action_axis_material_contract,
    validate_action_axis_material_contract_tables,
)


def _small_tracking_cfg():
    return V2StructureChangeTrackingConfig(steps=18, seeds=(501, 502), window_sizes=(1, 6, 12))


def _small_prediction_cfg():
    return GameStructurePredictionEnvelopeDryRunConfig(max_relation_envelopes=4)


def test_task2_8j_13_action_axis_material_contract_boundaries():
    materials, principles, readiness, checks, final_summary, errors, summary = (
        build_and_validate_action_axis_material_contract(
            tracking_cfg=_small_tracking_cfg(),
            prediction_envelope_cfg=_small_prediction_cfg(),
        )
    )

    assert errors == []
    assert not materials.empty
    assert not principles.empty
    assert not readiness.empty
    assert not checks.empty
    assert not final_summary.empty
    assert summary["gt_main_map_name"] == "static_pca_7"
    assert summary["gt_main_component_count"] == 7
    assert summary["action_axis_generated"] is False
    assert summary["action_candidate_generated"] is False
    assert summary["action_effect_prediction_generated"] is False
    assert summary["real_actionmodule_called"] is False

    for table in [materials, principles, readiness, checks, final_summary]:
        assert set(table["validation_only"].astype(bool)) == {True}
        assert set(table["material_contract_only"].astype(bool)) == {True}
        assert set(table["action_axis_material_contract_only"].astype(bool)) == {True}
        assert set(table["upper_pressure_route_material_allowed"].astype(bool)) == {True}
        assert set(table["ot_observation_context_material_allowed"].astype(bool)) == {True}
        assert set(table["game_structure_prediction_material_allowed"].astype(bool)) == {True}
        assert set(table["audit_material_allowed"].astype(bool)) == {True}
        assert set(table["no_op_baseline_material_required"].astype(bool)) == {True}
        assert set(table["direction_selection_required"].astype(bool)) == {True}
        assert set(table["state_dependent_trigger_required"].astype(bool)) == {True}
        assert set(table["immediate_release_required"].astype(bool)) == {True}
        assert set(table["weak_local_reversible_required"].astype(bool)) == {True}
        assert set(table["v8_local_audit_reserved_optional"].astype(bool)) == {True}
        assert set(table["exploration_axis_input_reserved_not_used"].astype(bool)) == {True}
        assert set(table["action_axis_generated"].astype(bool)) == {False}
        assert set(table["action_candidate_generated"].astype(bool)) == {False}
        assert set(table["concrete_action_generated"].astype(bool)) == {False}
        assert set(table["action_effect_prediction_generated"].astype(bool)) == {False}
        assert set(table["real_actionmodule_called"].astype(bool)) == {False}
        assert set(table["gt_main_map_name"].astype(str)) == {"static_pca_7"}
        assert set(table["gt_main_component_count"].astype(int)) == {7}


def test_task2_8j_13_core_materials_and_principles_ready():
    materials, principles, readiness, checks, final_summary, _errors, summary = (
        build_and_validate_action_axis_material_contract(
            tracking_cfg=_small_tracking_cfg(),
            prediction_envelope_cfg=_small_prediction_cfg(),
        )
    )

    material_names = set(materials["material_source_name"].astype(str))
    assert "upper_pressure_route_material" in material_names
    assert "ot_observation_context_material" in material_names
    assert "game_structure_prediction_material" in material_names
    assert "audit_material" in material_names
    assert "NO_OP_baseline_material" in material_names
    assert "v8_local_audit_reserved_optional_material" in material_names
    assert "exploration_axis_reserved_material" in material_names
    assert int(final_summary["active_material_source_count"].iloc[0]) >= 5
    assert int(final_summary["reserved_material_source_count"].iloc[0]) >= 2

    principle_names = set(principles["principle_name"].astype(str))
    assert {"direction_selection", "state_dependent_trigger", "immediate_release", "NO_OP_comparison_required"}.issubset(principle_names)
    assert set(principles["principle_status"].astype(str)) == {"principle_required_and_ready"}
    assert set(readiness["readiness_status"].astype(str)) == {"ready"}
    assert set(checks["check_status"].astype(str)) == {"pass"}
    assert int(final_summary["contract_check_count"].iloc[0]) == int(final_summary["contract_check_pass_count"].iloc[0])
    assert "direction_selection_state_dependence_immediate_release" in summary["action_axis_material_contract_decision"]


def test_task2_8j_13_validator_detects_action_axis_generation():
    materials, principles, readiness, checks, final_summary, _errors, _summary = (
        build_and_validate_action_axis_material_contract(
            tracking_cfg=_small_tracking_cfg(),
            prediction_envelope_cfg=_small_prediction_cfg(),
        )
    )
    bad = materials.copy()
    bad.loc[bad.index[0], "action_axis_generated"] = True
    errors = validate_action_axis_material_contract_tables(bad, principles, readiness, checks, final_summary)
    assert "task2_8j_13_forbidden_true:materials:action_axis_generated" in errors
