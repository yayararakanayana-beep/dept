from dept2_fullspec_runner_rc1.contracts import FullSpecRunnerConfig
from dept2_fullspec_runner_rc1.runner.fullspec_integrated_closed_loop_runner import run_fullspec_task16


def test_task2_8j_26_fullspec_integration_bridge_runs_inside_loop():
    cfg = FullSpecRunnerConfig(
        steps=1,
        gt_route="static_pca_7_smoke",
        task2_8j_bridge_enabled=True,
        canonical_commit_enabled=False,
        canonical_commit_dry_run=True,
        run_baseline_shadow=False,
    )

    outputs = run_fullspec_task16(cfg)

    assert outputs["gt"] is not None and not outputs["gt"].empty
    assert outputs["ot_action_view"] is not None and not outputs["ot_action_view"].empty
    assert outputs["pressure_intent_bundle"] is not None and not outputs["pressure_intent_bundle"].empty
    assert outputs["action_execution_audit"] is not None and not outputs["action_execution_audit"].empty

    bridge = outputs["task2_8j_bridge_audit"]
    selection = outputs["task2_8j_operator_selection"]
    review = outputs["task2_8j_operator_review"]
    checks = outputs["task2_8j_operator_checks"]
    summary = outputs["task2_8j_operator_summary"]

    assert bridge is not None and not bridge.empty
    assert selection is not None and not selection.empty
    assert review is not None and not review.empty
    assert checks is not None and not checks.empty
    assert summary is not None and not summary.empty

    assert set(bridge["bridge_status"].astype(str)) == {"pass"}
    assert set(bridge["fullspec_loop_connected"].astype(bool)) == {True}
    assert set(bridge["task2_8j_24_material_connected_inside_fullspec_cycle"].astype(bool)) == {True}
    assert set(bridge["gt_main_map_name"].astype(str)) == {"static_pca_7"}
    assert set(bridge["gt_main_component_count"].astype(int)) == {7}
    assert set(bridge["static_pca7_view_attached"].astype(bool)) == {True}
    assert set(bridge["legacy_gt_deleted"].astype(bool)) == {False}
    assert set(bridge["task2_8j_24_ready"].astype(bool)) == {True}
    assert set(bridge["task2_8j_24_checks_passed"].astype(bool)) == {True}
    assert set(bridge["task2_8j_24_error_count"].astype(int)) == {0}
    assert set(bridge["action_surface_replaced_by_task2_8j"].astype(bool)) == {False}
    assert set(bridge["action_candidates_replaced_by_task2_8j"].astype(bool)) == {False}
    assert set(bridge["action_frame_replaced_by_task2_8j"].astype(bool)) == {False}
    assert set(bridge["canonical_write_performed_by_bridge"].astype(bool)) == {False}
    assert set(bridge["axis_execution_performed_by_bridge"].astype(bool)) == {False}
    assert set(bridge["real_actionmodule_called_by_bridge"].astype(bool)) == {False}
    assert set(bridge["direct_dept_read_by_actionmodule"].astype(bool)) == {False}

    assert int(bridge["operator_selection_rows"].iloc[0]) == len(selection)
    assert int(bridge["operator_review_rows"].iloc[0]) == len(review)
    assert int(bridge["operator_check_rows"].iloc[0]) == len(checks)
    assert bool((checks["check_status"].astype(str) == "pass").all())

    assert set(selection["fullspec_loop_connected"].astype(bool)) == {True}
    assert set(selection["fullspec_gt_main_map_name"].astype(str)) == {"static_pca_7"}
    assert set(selection["fullspec_static_pca7_view_attached"].astype(bool)) == {True}
    assert set(selection["legacy_gt_deleted_by_bridge"].astype(bool)) == {False}
    assert set(selection["canonical_write_performed_by_bridge"].astype(bool)) == {False}
    assert set(selection["axis_execution_performed_by_bridge"].astype(bool)) == {False}
