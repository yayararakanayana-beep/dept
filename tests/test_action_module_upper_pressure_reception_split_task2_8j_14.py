from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_6c_v2_structure_change_relation_field_tracking import (
    V2StructureChangeTrackingConfig,
)
from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_11_game_structure_prediction_envelope_dry_run import (
    GameStructurePredictionEnvelopeDryRunConfig,
)
from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_14_action_axis_material_bundle_dry_run import (
    ActionAxisMaterialBundleDryRunConfig,
    build_and_validate_action_axis_material_bundle_dry_run,
    validate_action_axis_material_bundle_dry_run_tables,
)


def _small_tracking_cfg():
    return V2StructureChangeTrackingConfig(steps=18, seeds=(501, 502), window_sizes=(1, 6, 12))


def _small_prediction_cfg():
    return GameStructurePredictionEnvelopeDryRunConfig(max_relation_envelopes=4)


def _small_bundle_cfg():
    return ActionAxisMaterialBundleDryRunConfig(max_bundles=4)


def test_task2_8j_14_material_bundle_boundaries():
    bundles, source_trace, checks, final_summary, errors, summary = (
        build_and_validate_action_axis_material_bundle_dry_run(
            tracking_cfg=_small_tracking_cfg(),
            prediction_envelope_cfg=_small_prediction_cfg(),
            cfg=_small_bundle_cfg(),
        )
    )

    assert errors == []
    assert not bundles.empty
    assert not source_trace.empty
    assert not checks.empty
    assert not final_summary.empty
    assert summary["gt_main_map_name"] == "static_pca_7"
    assert summary["gt_main_component_count"] == 7
    assert summary["action_axis_generated"] is False
    assert summary["action_candidate_generated"] is False
    assert summary["action_effect_prediction_generated"] is False
    assert summary["real_actionmodule_called"] is False

    for table in [bundles, source_trace, checks, final_summary]:
        assert set(table["validation_only"].astype(bool)) == {True}
        assert set(table["dry_run_only"].astype(bool)) == {True}
        assert set(table["material_bundle_dry_run_only"].astype(bool)) == {True}
        assert set(table["material_bundle_created"].astype(bool)) == {True}
        assert set(table["upper_pressure_material_included"].astype(bool)) == {True}
        assert set(table["ot_context_material_included"].astype(bool)) == {True}
        assert set(table["game_structure_prediction_material_included"].astype(bool)) == {True}
        assert set(table["audit_material_included"].astype(bool)) == {True}
        assert set(table["no_op_baseline_material_included"].astype(bool)) == {True}
        assert set(table["direction_selection_material_required"].astype(bool)) == {True}
        assert set(table["state_dependent_trigger_material_required"].astype(bool)) == {True}
        assert set(table["immediate_release_material_required"].astype(bool)) == {True}
        assert set(table["weak_local_reversible_material_required"].astype(bool)) == {True}
        assert set(table["route_tags_preserved"].astype(bool)) == {True}
        assert set(table["source_traces_preserved"].astype(bool)) == {True}
        assert set(table["v8_local_audit_reserved_optional"].astype(bool)) == {True}
        assert set(table["exploration_axis_input_reserved_not_used"].astype(bool)) == {True}
        assert set(table["action_axis_generated"].astype(bool)) == {False}
        assert set(table["action_candidate_generated"].astype(bool)) == {False}
        assert set(table["concrete_action_generated"].astype(bool)) == {False}
        assert set(table["action_effect_prediction_generated"].astype(bool)) == {False}
        assert set(table["real_actionmodule_called"].astype(bool)) == {False}
        assert set(table["gt_main_map_name"].astype(str)) == {"static_pca_7"}
        assert set(table["gt_main_component_count"].astype(int)) == {7}


def test_task2_8j_14_bundles_have_materials_and_source_traces():
    bundles, source_trace, checks, final_summary, _errors, summary = (
        build_and_validate_action_axis_material_bundle_dry_run(
            tracking_cfg=_small_tracking_cfg(),
            prediction_envelope_cfg=_small_prediction_cfg(),
            cfg=_small_bundle_cfg(),
        )
    )

    assert set(bundles["bundle_kind"].astype(str)) == {"action_axis_material_bundle_dry_run_without_axis_generation"}
    assert bundles["route_material_tags"].astype(str).str.contains("upper_pressure_route").all()
    assert bundles["route_material_tags"].astype(str).str.contains("game_structure_prediction").all()
    assert bundles["no_op_baseline_material"].astype(str).str.contains("NO_OP_baseline_required").all()
    assert bundles["release_material"].astype(str).str.contains("immediate_release_material_required").all()
    assert bundles["direction_material"].astype(str).str.contains("direction_selection_material").all()
    assert set(source_trace["trace_status"].astype(str)) == {"source_trace_preserved"}
    assert set(checks["check_status"].astype(str)) == {"pass"}
    assert int(final_summary["material_bundle_count"].iloc[0]) == len(bundles)
    assert int(final_summary["source_trace_preserved_bundle_count"].iloc[0]) == len(bundles)
    assert int(final_summary["bundle_check_count"].iloc[0]) == int(final_summary["bundle_check_pass_count"].iloc[0])
    assert "without_axis_generation" in summary["action_axis_material_bundle_dry_run_decision"]


def test_task2_8j_14_validator_detects_axis_generation():
    bundles, source_trace, checks, final_summary, _errors, _summary = (
        build_and_validate_action_axis_material_bundle_dry_run(
            tracking_cfg=_small_tracking_cfg(),
            prediction_envelope_cfg=_small_prediction_cfg(),
            cfg=_small_bundle_cfg(),
        )
    )
    bad = bundles.copy()
    bad.loc[bad.index[0], "action_axis_generated"] = True
    errors = validate_action_axis_material_bundle_dry_run_tables(bad, source_trace, checks, final_summary)
    assert "task2_8j_14_forbidden_true:bundles:action_axis_generated" in errors
