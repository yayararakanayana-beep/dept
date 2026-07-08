from dept2_fullspec_runner_rc1.contracts import FullSpecRunnerConfig
from dept2_fullspec_runner_rc1.runner.fullspec_integrated_closed_loop_runner import run_fullspec_task16


def test_task2_8j_27_primary_actionsurface_integration_runs_inside_fullspec_loop():
    cfg = FullSpecRunnerConfig(
        steps=1,
        gt_route="static_pca_7_smoke",
        task2_8j_bridge_enabled=True,
        action_planning_route="task2_8j_primary",
        canonical_commit_enabled=False,
        canonical_commit_dry_run=True,
        run_baseline_shadow=False,
    )

    outputs = run_fullspec_task16(cfg)

    assert outputs["gt"] is not None and not outputs["gt"].empty
    assert outputs["task2_8j_operator_selection"] is not None and not outputs["task2_8j_operator_selection"].empty
    assert outputs["task2_8j_bridge_audit"] is not None and not outputs["task2_8j_bridge_audit"].empty
    assert set(outputs["task2_8j_bridge_audit"]["bridge_status"].astype(str)) == {"pass"}

    audit = outputs["action_surface_planning_audit"]
    candidates = outputs["action_candidates"]
    needs = outputs["local_observation_needs"]
    action_execution = outputs["action_execution_audit"]

    assert audit is not None and not audit.empty
    assert candidates is not None and not candidates.empty
    assert needs is not None and not needs.empty
    assert action_execution is not None and not action_execution.empty

    assert set(audit["audit_status"].astype(str)) == {"pass"}
    assert set(audit["action_planning_route"].astype(str)) == {"task2_8j_primary"}
    assert set(audit["task2_8j_primary_route_requested"].astype(bool)) == {True}
    assert set(audit["task2_8j_primary_route_used"].astype(bool)) == {True}
    assert set(audit["task2_8j_material_promoted_to_action_candidates"].astype(bool)) == {True}
    assert int(audit["task2_8j_operator_material_rows"].iloc[0]) > 0
    assert int(audit["task2_8j_primary_candidate_rows"].iloc[0]) > 0
    assert int(audit["task2_8j_legacy_fallback_candidate_rows"].iloc[0]) >= 0

    assert "task2_8j_primary_candidate" in candidates.columns
    assert bool(candidates["task2_8j_primary_candidate"].fillna(False).astype(bool).any())
    primary = candidates[candidates["task2_8j_primary_candidate"].fillna(False).astype(bool)]
    assert not primary.empty
    assert set(primary["task2_8j_candidate_source"].astype(str)) == {"task2_8j_operator_selection_primary"}
    assert set(primary["task2_8j_operator_material_used_by_actionsurface"].astype(bool)) == {True}
    assert set(primary["action_frame_created_by_task2_8j_planning"].astype(bool)) == {False}
    assert set(primary["actionmodule_called_by_task2_8j_planning"].astype(bool)) == {False}
    assert set(primary["canonical_write_performed_by_task2_8j_planning"].astype(bool)) == {False}
    assert set(primary["axis_execution_performed_by_task2_8j_planning"].astype(bool)) == {False}
    assert set(primary["direct_dept_read_by_actionmodule"].astype(bool)) == {False}

    allowed_channels = {"coupling_relief", "relation_unlock", "buffer_increase", "volatility_damping", "no_op"}
    assert set(primary["action_channel"].astype(str)).issubset(allowed_channels)
    assert bool(primary["action_strength"].astype(float).between(0.0, 0.03).all())

    assert "task2_8j_primary_need_source" in needs.columns
    assert bool(needs["task2_8j_primary_need_source"].fillna(False).astype(bool).any())

    assert set(action_execution["audit_status"].astype(str)) == {"pass"}
    assert set(action_execution["direct_gk_input_to_actionmodule"].astype(bool)) == {False}
    assert set(action_execution["direct_ot_input_to_actionmodule"].astype(bool)) == {False}
    assert set(action_execution["direct_parameter_box_input_to_actionmodule"].astype(bool)) == {False}
    assert set(action_execution["canonical_parameter_write_performed"].astype(bool)) == {False}
