import pytest

from dept2_fullspec_runner_rc1.contracts import FullSpecRunnerConfig
from dept2_fullspec_runner_rc1.runner.fullspec_integrated_closed_loop_runner import run_fullspec_task16


TASK2_8J_28_STEPS = 4
EXPECTED_STEPS = set(range(TASK2_8J_28_STEPS))


def _steps(df):
    assert df is not None and not df.empty
    assert "loop_step" in df.columns
    return set(df["loop_step"].astype(int).unique())


@pytest.mark.parametrize("scenario", ["normal", "relation_lock"])
def test_task2_8j_28_primary_route_multistep_loop_stays_connected(scenario):
    cfg = FullSpecRunnerConfig(
        steps=TASK2_8J_28_STEPS,
        scenario=scenario,
        gt_route="static_pca_7_smoke",
        task2_8j_bridge_enabled=True,
        action_planning_route="task2_8j_primary",
        canonical_commit_enabled=False,
        canonical_commit_dry_run=True,
        run_baseline_shadow=False,
    )

    outputs = run_fullspec_task16(cfg)

    required_tables = [
        "gt",
        "formal_packet",
        "gk_build_audit",
        "task2_8j_bridge_audit",
        "task2_8j_operator_selection",
        "action_surface_planning_audit",
        "action_candidates",
        "local_observation_needs",
        "action_local_audit",
        "coactivation_gate",
        "action_execution_audit",
        "world_transition_audit",
    ]
    for name in required_tables:
        assert name in outputs, name
        assert outputs[name] is not None and not outputs[name].empty, name
        assert _steps(outputs[name]) == EXPECTED_STEPS, name

    gt = outputs["gt"]
    assert set(gt["gt_main_map_name"].astype(str)) == {"static_pca_7"}
    assert set(gt["gt_main_component_count"].astype(int)) == {7}
    assert set(gt["static_pca7_view_attached"].astype(bool)) == {True}
    assert set(gt["legacy_gt_columns_preserved"].astype(bool)) == {True}

    bridge = outputs["task2_8j_bridge_audit"]
    assert set(bridge["bridge_status"].astype(str)) == {"pass"}
    assert set(bridge["task2_8j_24_ready"].astype(bool)) == {True}
    assert set(bridge["task2_8j_24_checks_passed"].astype(bool)) == {True}
    assert set(bridge["canonical_write_performed_by_bridge"].astype(bool)) == {False}
    assert set(bridge["axis_execution_performed_by_bridge"].astype(bool)) == {False}

    planning = outputs["action_surface_planning_audit"]
    assert set(planning["audit_status"].astype(str)) == {"pass"}
    assert set(planning["action_planning_route"].astype(str)) == {"task2_8j_primary"}
    assert set(planning["task2_8j_primary_route_requested"].astype(bool)) == {True}
    assert set(planning["task2_8j_primary_route_used"].astype(bool)) == {True}
    assert set(planning["task2_8j_material_promoted_to_action_candidates"].astype(bool)) == {True}
    assert bool((planning["task2_8j_operator_material_rows"].astype(int) > 0).all())
    assert bool((planning["task2_8j_primary_candidate_rows"].astype(int) > 0).all())
    assert set(planning["action_frame_created_by_planning"].astype(bool)) == {False}
    assert set(planning["actionmodule_called_by_planning"].astype(bool)) == {False}
    assert set(planning["canonical_write_performed"].astype(bool)) == {False}
    assert set(planning["world_write_performed"].astype(bool)) == {False}
    assert set(planning["gk_writeback_performed"].astype(bool)) == {False}

    candidates = outputs["action_candidates"]
    assert "task2_8j_primary_candidate" in candidates.columns
    primary = candidates[candidates["task2_8j_primary_candidate"].fillna(False).astype(bool)]
    assert not primary.empty
    assert _steps(primary) == EXPECTED_STEPS
    assert set(primary["task2_8j_candidate_source"].astype(str)) == {"task2_8j_operator_selection_primary"}
    assert set(primary["task2_8j_operator_material_used_by_actionsurface"].astype(bool)) == {True}
    assert set(primary["action_frame_created_by_task2_8j_planning"].astype(bool)) == {False}
    assert set(primary["actionmodule_called_by_task2_8j_planning"].astype(bool)) == {False}
    assert set(primary["canonical_write_performed_by_task2_8j_planning"].astype(bool)) == {False}
    assert set(primary["axis_execution_performed_by_task2_8j_planning"].astype(bool)) == {False}
    assert set(primary["direct_dept_read_by_actionmodule"].astype(bool)) == {False}
    assert bool(primary["action_strength"].astype(float).between(0.0, 0.03).all())

    allowed_channels = {"coupling_relief", "relation_unlock", "buffer_increase", "volatility_damping", "no_op"}
    assert set(primary["action_channel"].astype(str)).issubset(allowed_channels)

    needs = outputs["local_observation_needs"]
    assert "task2_8j_primary_need_source" in needs.columns
    task2_need = needs[needs["task2_8j_primary_need_source"].fillna(False).astype(bool)]
    assert not task2_need.empty
    assert _steps(task2_need) == EXPECTED_STEPS

    gate = outputs["coactivation_gate"]
    assert set(gate["coactivation_gate_audit_status"].astype(str)) == {"pass"}
    assert set(gate["gate_required_before_actionframe"].astype(bool)) == {True}
    assert set(gate["action_frame_created_by_gate"].astype(bool)) == {False}
    assert set(gate["actionmodule_called_by_gate"].astype(bool)) == {False}
    assert set(gate["canonical_parameter_write_by_gate"].astype(bool)) == {False}

    execution = outputs["action_execution_audit"]
    assert set(execution["audit_status"].astype(str)) == {"pass"}
    assert set(execution["actionmodule_input_contract"].astype(str)) == {"ActionFrame_only"}
    assert set(execution["actionmodule_received_actionframe_only"].astype(bool)) == {True}
    assert set(execution["direct_gk_input_to_actionmodule"].astype(bool)) == {False}
    assert set(execution["direct_ot_input_to_actionmodule"].astype(bool)) == {False}
    assert set(execution["direct_parameter_box_input_to_actionmodule"].astype(bool)) == {False}
    assert set(execution["canonical_parameter_write_performed"].astype(bool)) == {False}
    assert bool((execution["world_t_after"].astype(int) == execution["world_t_before"].astype(int) + 1).all())

    transition = outputs["world_transition_audit"]
    assert bool((transition["world_t_after"].astype(int) == transition["world_t_before"].astype(int) + 1).all())
    assert set(transition["gk_writeback_performed"].astype(bool)) == {False}
    assert set(transition["ot_writeback_performed"].astype(bool)) == {False}
    assert set(transition["canonical_parameter_write_performed"].astype(bool)) == {False}
