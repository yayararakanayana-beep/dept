from dept2_fullspec_runner_rc1.contracts import FullSpecRunnerConfig
from dept2_fullspec_runner_rc1.runner.fullspec_integrated_closed_loop_runner import run_fullspec_task16


def test_task2_8j_31_default_config_uses_task2_8j_primary_route():
    cfg = FullSpecRunnerConfig(
        steps=1,
        canonical_commit_enabled=False,
        canonical_commit_dry_run=True,
        run_baseline_shadow=False,
    )

    assert cfg.gt_route == "static_pca_7_smoke"
    assert cfg.task2_8j_bridge_enabled is True
    assert cfg.action_planning_route == "task2_8j_primary"

    outputs = run_fullspec_task16(cfg)

    gt = outputs["gt"]
    bridge = outputs["task2_8j_bridge_audit"]
    selection = outputs["task2_8j_operator_selection"]
    planning = outputs["action_surface_planning_audit"]
    candidates = outputs["action_candidates"]
    execution = outputs["action_execution_audit"]

    assert gt is not None and not gt.empty
    assert set(gt["gt_main_map_name"].astype(str)) == {"static_pca_7"}
    assert set(gt["gt_main_component_count"].astype(int)) == {7}
    assert set(gt["static_pca7_view_attached"].astype(bool)) == {True}
    assert set(gt["legacy_gt_columns_preserved"].astype(bool)) == {True}
    assert set(gt["legacy_gt_deleted_by_gt_route"].astype(bool)) == {False}

    assert bridge is not None and not bridge.empty
    assert selection is not None and not selection.empty
    assert set(bridge["bridge_status"].astype(str)) == {"pass"}
    assert set(bridge["task2_8j_24_ready"].astype(bool)) == {True}
    assert set(bridge["canonical_write_performed_by_bridge"].astype(bool)) == {False}
    assert set(bridge["axis_execution_performed_by_bridge"].astype(bool)) == {False}

    assert planning is not None and not planning.empty
    assert set(planning["audit_status"].astype(str)) == {"pass"}
    assert set(planning["action_planning_route"].astype(str)) == {"task2_8j_primary"}
    assert set(planning["task2_8j_primary_route_requested"].astype(bool)) == {True}
    assert set(planning["task2_8j_primary_route_used"].astype(bool)) == {True}
    assert set(planning["task2_8j_material_promoted_to_action_candidates"].astype(bool)) == {True}
    assert bool((planning["task2_8j_primary_candidate_rows"].astype(int) > 0).all())
    assert set(planning["action_frame_created_by_planning"].astype(bool)) == {False}
    assert set(planning["actionmodule_called_by_planning"].astype(bool)) == {False}
    assert set(planning["canonical_write_performed"].astype(bool)) == {False}
    assert set(planning["world_write_performed"].astype(bool)) == {False}
    assert set(planning["gk_writeback_performed"].astype(bool)) == {False}

    assert candidates is not None and not candidates.empty
    assert bool(candidates["task2_8j_primary_candidate"].fillna(False).astype(bool).any())
    primary = candidates[candidates["task2_8j_primary_candidate"].fillna(False).astype(bool)]
    assert set(primary["task2_8j_candidate_source"].astype(str)) == {"task2_8j_operator_selection_primary"}
    assert set(primary["task2_8j_operator_material_used_by_actionsurface"].astype(bool)) == {True}
    assert set(primary["action_frame_created_by_task2_8j_planning"].astype(bool)) == {False}
    assert set(primary["actionmodule_called_by_task2_8j_planning"].astype(bool)) == {False}
    assert set(primary["canonical_write_performed_by_task2_8j_planning"].astype(bool)) == {False}
    assert set(primary["axis_execution_performed_by_task2_8j_planning"].astype(bool)) == {False}
    assert set(primary["direct_dept_read_by_actionmodule"].astype(bool)) == {False}

    assert execution is not None and not execution.empty
    assert set(execution["audit_status"].astype(str)) == {"pass"}
    assert set(execution["actionmodule_input_contract"].astype(str)) == {"ActionFrame_only"}
    assert set(execution["actionmodule_received_actionframe_only"].astype(bool)) == {True}
    assert set(execution["direct_gk_input_to_actionmodule"].astype(bool)) == {False}
    assert set(execution["direct_ot_input_to_actionmodule"].astype(bool)) == {False}
    assert set(execution["direct_parameter_box_input_to_actionmodule"].astype(bool)) == {False}
    assert set(execution["canonical_parameter_write_performed"].astype(bool)) == {False}


def test_task2_8j_31_explicit_legacy_override_remains_available():
    cfg = FullSpecRunnerConfig(
        steps=1,
        gt_route="legacy",
        task2_8j_bridge_enabled=False,
        action_planning_route="legacy",
        canonical_commit_enabled=False,
        canonical_commit_dry_run=True,
        run_baseline_shadow=False,
    )

    outputs = run_fullspec_task16(cfg)

    gt = outputs["gt"]
    planning = outputs["action_surface_planning_audit"]
    candidates = outputs["action_candidates"]
    execution = outputs["action_execution_audit"]
    bridge = outputs.get("task2_8j_bridge_audit")

    assert gt is not None and not gt.empty
    assert set(gt["gt_route_selected"].astype(str)) == {"legacy"}
    assert set(gt["legacy_gt_deleted_by_gt_route"].astype(bool)) == {False}

    assert bridge is None or bridge.empty

    assert planning is not None and not planning.empty
    assert set(planning["audit_status"].astype(str)) == {"pass"}
    assert set(planning["action_planning_route"].astype(str)) == {"legacy"}
    assert set(planning["task2_8j_primary_route_requested"].astype(bool)) == {False}
    assert set(planning["task2_8j_primary_route_used"].astype(bool)) == {False}
    assert set(planning["task2_8j_material_promoted_to_action_candidates"].astype(bool)) == {False}

    assert candidates is not None and not candidates.empty
    assert set(candidates["task2_8j_primary_candidate"].fillna(False).astype(bool)) == {False}
    assert set(candidates["task2_8j_candidate_source"].astype(str)) == {"legacy_repaired_policy_primary"}

    assert execution is not None and not execution.empty
    assert set(execution["audit_status"].astype(str)) == {"pass"}
    assert set(execution["actionmodule_input_contract"].astype(str)) == {"ActionFrame_only"}
    assert set(execution["actionmodule_received_actionframe_only"].astype(bool)) == {True}
    assert set(execution["direct_gk_input_to_actionmodule"].astype(bool)) == {False}
    assert set(execution["direct_ot_input_to_actionmodule"].astype(bool)) == {False}
    assert set(execution["direct_parameter_box_input_to_actionmodule"].astype(bool)) == {False}
    assert set(execution["canonical_parameter_write_performed"].astype(bool)) == {False}
