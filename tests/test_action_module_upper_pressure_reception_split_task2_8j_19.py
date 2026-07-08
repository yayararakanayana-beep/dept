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
from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_19_v2_terrain_action_sandbox_design import (
    V2TerrainActionSandboxDesignConfig,
    build_and_validate_v2_terrain_action_sandbox_design,
    validate_v2_terrain_action_sandbox_design_tables,
)


def _small_tracking_cfg():
    return V2StructureChangeTrackingConfig(steps=18, seeds=(501, 502), window_sizes=(1, 6, 12))


def _small_prediction_cfg():
    return GameStructurePredictionEnvelopeDryRunConfig(max_relation_envelopes=4)


def _small_bundle_cfg():
    return ActionAxisMaterialBundleDryRunConfig(max_bundles=4)


def _small_axis_cfg():
    return ActionAxisDryRunGenerationConfig(max_axes=4)


def _small_sandbox_cfg():
    return V2TerrainActionSandboxDesignConfig(max_sweep_rows=28)


def test_task2_8j_19_v2_terrain_sandbox_design_boundaries():
    operator_families, signals, sweep, guards, checks, final_summary, errors, summary = (
        build_and_validate_v2_terrain_action_sandbox_design(
            tracking_cfg=_small_tracking_cfg(),
            prediction_envelope_cfg=_small_prediction_cfg(),
            bundle_cfg=_small_bundle_cfg(),
            axis_cfg=_small_axis_cfg(),
            cfg=_small_sandbox_cfg(),
        )
    )

    assert errors == []
    assert not operator_families.empty
    assert not signals.empty
    assert not sweep.empty
    assert not guards.empty
    assert not checks.empty
    assert not final_summary.empty
    assert summary["gt_main_map_name"] == "static_pca_7"
    assert summary["gt_main_component_count"] == 7
    assert summary["semantic_recipe_primary_key_forbidden"] is True
    assert summary["terrain_information_primary_required"] is True
    assert summary["v2_oracle_results_hint_only"] is True
    assert summary["risk_label_used_only_for_evaluation"] is True
    assert summary["sandbox_executed"] is False
    assert summary["action_candidate_generated"] is False
    assert summary["action_effect_prediction_generated"] is False
    assert summary["effect_prediction_model_executed"] is False
    assert summary["concrete_action_generated"] is False
    assert summary["axis_executed"] is False
    assert summary["real_actionmodule_called"] is False

    for table in [operator_families, signals, sweep, guards, checks, final_summary]:
        assert set(table["validation_only"].astype(bool)) == {True}
        assert set(table["sandbox_design_only"].astype(bool)) == {True}
        assert set(table["v2_terrain_action_sandbox_only"].astype(bool)) == {True}
        assert set(table["terrain_operator_design_only"].astype(bool)) == {True}
        assert set(table["parameter_sweep_design_only"].astype(bool)) == {True}
        assert set(table["semantic_recipe_primary_key_forbidden"].astype(bool)) == {True}
        assert set(table["terrain_information_primary_required"].astype(bool)) == {True}
        assert set(table["risk_label_used_only_for_evaluation"].astype(bool)) == {True}
        assert set(table["meaning_labels_explanation_only"].astype(bool)) == {True}
        assert set(table["v2_oracle_results_hint_only"].astype(bool)) == {True}
        assert set(table["v2_oracle_results_not_direct_action_input"].astype(bool)) == {True}
        assert set(table["no_op_preserved"].astype(bool)) == {True}
        assert set(table["direction_selection_required"].astype(bool)) == {True}
        assert set(table["state_dependence_required"].astype(bool)) == {True}
        assert set(table["immediate_release_required"].astype(bool)) == {True}
        assert set(table["rollback_required"].astype(bool)) == {True}
        assert set(table["audit_required"].astype(bool)) == {True}
        assert set(table["sandbox_executed"].astype(bool)) == {False}
        assert set(table["terrain_operator_applied"].astype(bool)) == {False}
        assert set(table["action_candidate_generated"].astype(bool)) == {False}
        assert set(table["action_effect_prediction_generated"].astype(bool)) == {False}
        assert set(table["effect_prediction_model_executed"].astype(bool)) == {False}
        assert set(table["axis_executed"].astype(bool)) == {False}
        assert set(table["gt_main_map_name"].astype(str)) == {"static_pca_7"}
        assert set(table["gt_main_component_count"].astype(int)) == {7}


def test_task2_8j_19_operator_and_sweep_design_content():
    operator_families, signals, sweep, guards, checks, final_summary, _errors, summary = (
        build_and_validate_v2_terrain_action_sandbox_design(
            tracking_cfg=_small_tracking_cfg(),
            prediction_envelope_cfg=_small_prediction_cfg(),
            bundle_cfg=_small_bundle_cfg(),
            axis_cfg=_small_axis_cfg(),
            cfg=_small_sandbox_cfg(),
        )
    )

    expected_ops = {
        "soft_resistance",
        "pressure_diffusion",
        "gradient_smoothing",
        "escape_channel",
        "damping",
        "buffer_injection",
        "reversibility_support",
    }
    assert expected_ops.issubset(set(operator_families["operator_family_name"].astype(str)))
    assert signals["not_a_semantic_label"].astype(bool).all()
    assert sweep["no_op_comparison_required_later"].astype(bool).all()
    assert sweep["effect_prediction_required_later"].astype(bool).all()
    assert sweep["risk_review_required_later"].astype(bool).all()
    assert set(sweep["design_row_status"].astype(str)) == {"sandbox_design_row_ready_not_executed"}
    assert set(guards["guard_status"].astype(str)) == {"sandbox_guard_ready"}
    assert set(checks["check_status"].astype(str)) == {"pass"}
    assert int(final_summary["operator_family_count"].iloc[0]) >= 7
    assert int(final_summary["terrain_signal_count"].iloc[0]) >= 8
    assert int(final_summary["sweep_design_row_count"].iloc[0]) == len(sweep)
    assert int(final_summary["sandbox_check_count"].iloc[0]) == int(final_summary["sandbox_check_pass_count"].iloc[0])
    assert "ready_without_execution" in summary["v2_terrain_action_sandbox_design_decision"]


def test_task2_8j_19_validator_detects_sandbox_execution():
    operator_families, signals, sweep, guards, checks, final_summary, _errors, _summary = (
        build_and_validate_v2_terrain_action_sandbox_design(
            tracking_cfg=_small_tracking_cfg(),
            prediction_envelope_cfg=_small_prediction_cfg(),
            bundle_cfg=_small_bundle_cfg(),
            axis_cfg=_small_axis_cfg(),
            cfg=_small_sandbox_cfg(),
        )
    )
    bad = sweep.copy()
    bad.loc[bad.index[0], "sandbox_executed"] = True
    errors = validate_v2_terrain_action_sandbox_design_tables(operator_families, signals, bad, guards, checks, final_summary)
    assert "task2_8j_19_forbidden_true:sweep:sandbox_executed" in errors
