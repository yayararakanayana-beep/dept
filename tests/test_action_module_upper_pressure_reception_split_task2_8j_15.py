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
    build_and_validate_action_axis_dry_run_generation,
    validate_action_axis_dry_run_generation_tables,
)


def _small_tracking_cfg():
    return V2StructureChangeTrackingConfig(steps=18, seeds=(501, 502), window_sizes=(1, 6, 12))


def _small_prediction_cfg():
    return GameStructurePredictionEnvelopeDryRunConfig(max_relation_envelopes=4)


def _small_bundle_cfg():
    return ActionAxisMaterialBundleDryRunConfig(max_bundles=4)


def _small_axis_cfg():
    return ActionAxisDryRunGenerationConfig(max_axes=4)


def test_task2_8j_15_action_axis_dry_run_boundaries():
    axes, trace_table, checks, final_summary, errors, summary = (
        build_and_validate_action_axis_dry_run_generation(
            tracking_cfg=_small_tracking_cfg(),
            prediction_envelope_cfg=_small_prediction_cfg(),
            bundle_cfg=_small_bundle_cfg(),
            cfg=_small_axis_cfg(),
        )
    )

    assert errors == []
    assert not axes.empty
    assert not trace_table.empty
    assert not checks.empty
    assert not final_summary.empty
    assert summary["gt_main_map_name"] == "static_pca_7"
    assert summary["gt_main_component_count"] == 7
    assert summary["action_axis_dry_run_generated"] is True
    assert summary["concrete_action_generated"] is False
    assert summary["action_candidate_generated"] is False
    assert summary["action_effect_prediction_generated"] is False
    assert summary["axis_executed"] is False
    assert summary["real_actionmodule_called"] is False

    for table in [axes, trace_table, checks, final_summary]:
        assert set(table["validation_only"].astype(bool)) == {True}
        assert set(table["dry_run_only"].astype(bool)) == {True}
        assert set(table["action_axis_dry_run_generation_only"].astype(bool)) == {True}
        assert set(table["action_axis_dry_run_generated"].astype(bool)) == {True}
        assert set(table["source_material_bundle_required"].astype(bool)) == {True}
        assert set(table["direction_selection_required"].astype(bool)) == {True}
        assert set(table["state_dependent_trigger_required"].astype(bool)) == {True}
        assert set(table["immediate_release_required"].astype(bool)) == {True}
        assert set(table["weak_local_reversible_required"].astype(bool)) == {True}
        assert set(table["no_op_baseline_required"].astype(bool)) == {True}
        assert set(table["rollback_required"].astype(bool)) == {True}
        assert set(table["route_tags_preserved"].astype(bool)) == {True}
        assert set(table["source_traces_preserved"].astype(bool)) == {True}
        assert set(table["v8_local_audit_reserved_optional"].astype(bool)) == {True}
        assert set(table["exploration_axis_input_reserved_not_used"].astype(bool)) == {True}
        assert set(table["concrete_action_generated"].astype(bool)) == {False}
        assert set(table["action_candidate_generated"].astype(bool)) == {False}
        assert set(table["action_effect_prediction_generated"].astype(bool)) == {False}
        assert set(table["axis_executed"].astype(bool)) == {False}
        assert set(table["real_actionmodule_called"].astype(bool)) == {False}
        assert set(table["gt_main_map_name"].astype(str)) == {"static_pca_7"}
        assert set(table["gt_main_component_count"].astype(int)) == {7}


def test_task2_8j_15_axes_have_direction_state_release_no_op():
    axes, trace_table, checks, final_summary, _errors, summary = (
        build_and_validate_action_axis_dry_run_generation(
            tracking_cfg=_small_tracking_cfg(),
            prediction_envelope_cfg=_small_prediction_cfg(),
            bundle_cfg=_small_bundle_cfg(),
            cfg=_small_axis_cfg(),
        )
    )

    assert axes["direction_selector"].astype(str).str.contains("direction_selection_material").all()
    assert axes["timing_gate"].astype(str).str.contains("state_dependent_trigger_material").all()
    assert axes["release_condition"].astype(str).str.contains("immediate_release_material_required").all()
    assert axes["no_op_gate"].astype(str).str.contains("NO_OP_baseline_required").all()
    assert (axes["strength_bound"].astype(float) <= 0.20).all()
    assert set(trace_table["trace_status"].astype(str)) == {"axis_source_trace_preserved"}
    assert set(checks["check_status"].astype(str)) == {"pass"}
    assert int(final_summary["action_axis_count"].iloc[0]) == len(axes)
    assert int(final_summary["axis_check_count"].iloc[0]) == int(final_summary["axis_check_pass_count"].iloc[0])
    assert "without_execution" in summary["action_axis_dry_run_generation_decision"]


def test_task2_8j_15_validator_detects_execution():
    axes, trace_table, checks, final_summary, _errors, _summary = (
        build_and_validate_action_axis_dry_run_generation(
            tracking_cfg=_small_tracking_cfg(),
            prediction_envelope_cfg=_small_prediction_cfg(),
            bundle_cfg=_small_bundle_cfg(),
            cfg=_small_axis_cfg(),
        )
    )
    bad = axes.copy()
    bad.loc[bad.index[0], "axis_executed"] = True
    errors = validate_action_axis_dry_run_generation_tables(bad, trace_table, checks, final_summary)
    assert "task2_8j_15_forbidden_true:axes:axis_executed" in errors
