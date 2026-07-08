from dept2_fullspec_runner_rc1.contracts import FullSpecRunnerConfig
from dept2_fullspec_runner_rc1.runner.fullspec_integrated_closed_loop_runner import run_fullspec_task16


STATIC_PCA7_AXIS_COLUMNS = [
    "static_pca7_axis_1_activity_volatility",
    "static_pca7_axis_2_uncertainty_conflict",
    "static_pca7_axis_3_relation_lock_coupling",
    "static_pca7_axis_4_exploration",
    "static_pca7_axis_5_reversibility",
    "static_pca7_axis_6_entropy_overconvergence",
    "static_pca7_axis_7_relation_flow_curl",
]


def test_task2_8j_25_fullspec_static_pca7_gt_smoke_loop_runs():
    cfg = FullSpecRunnerConfig(
        steps=1,
        gt_route="static_pca_7_smoke",
        canonical_commit_enabled=False,
        canonical_commit_dry_run=True,
        run_baseline_shadow=False,
    )

    outputs = run_fullspec_task16(cfg)

    assert outputs["gt"] is not None
    assert not outputs["gt"].empty
    assert outputs["formal_packet"] is not None
    assert not outputs["formal_packet"].empty
    assert outputs["gk_build_audit"] is not None
    assert not outputs["gk_build_audit"].empty
    assert outputs["ot_observation_audit"] is not None
    assert not outputs["ot_observation_audit"].empty
    assert outputs["upper_pressure_audit"] is not None
    assert not outputs["upper_pressure_audit"].empty
    assert outputs["action_execution_audit"] is not None
    assert not outputs["action_execution_audit"].empty

    gt = outputs["gt"]
    for col in STATIC_PCA7_AXIS_COLUMNS:
        assert col in gt.columns
    assert set(gt["gt_route_selected"].astype(str)) == {"static_pca_7_smoke"}
    assert set(gt["gt_main_map_name"].astype(str)) == {"static_pca_7"}
    assert set(gt["gt_main_component_count"].astype(int)) == {7}
    assert set(gt["legacy_gt_columns_preserved"].astype(bool)) == {True}
    assert set(gt["static_pca7_view_attached"].astype(bool)) == {True}
    assert set(gt["canonical_write_performed_by_gt_route"].astype(bool)) == {False}
    assert set(gt["axis_execution_performed_by_gt_route"].astype(bool)) == {False}
    assert set(gt["legacy_gt_deleted_by_gt_route"].astype(bool)) == {False}

    gk_audit = outputs["gk_build_audit"]
    assert set(gk_audit["gt_route_selected"].astype(str)) == {"static_pca_7_smoke"}
    assert set(gk_audit["gt_main_map_name"].astype(str)) == {"static_pca_7"}
    assert set(gk_audit["gt_main_component_count"].astype(int)) == {7}
    assert set(gk_audit["legacy_gt_preserved"].astype(bool)) == {True}
    assert set(gk_audit["legacy_gt_deleted"].astype(bool)) == {False}
    assert set(gk_audit["static_pca7_view_attached"].astype(bool)) == {True}
    assert set(gk_audit["static_pca7_axis_count"].astype(int)) == {7}
    assert set(gk_audit["axis_execution_performed"].astype(bool)) == {False}
    assert set(gk_audit["gk_writeback_performed"].astype(bool)) == {False}
    assert set(gk_audit["canonical_world_write_performed"].astype(bool)) == {False}
    assert set(gk_audit["build_status"].astype(str)) == {"pass"}

    formal = outputs["formal_packet"]
    for col in STATIC_PCA7_AXIS_COLUMNS:
        assert col in formal.columns
    assert set(formal["gt_route_selected"].astype(str)) == {"static_pca_7_smoke"}
    assert set(formal["formal_contains_ot"].astype(bool)) == {False}
    assert set(formal["formal_contains_exploration"].astype(bool)) == {False}
    assert set(formal["formal_contains_action_surface"].astype(bool)) == {False}

    upper_audit = outputs["upper_pressure_audit"]
    assert set(upper_audit["formal_input_is_gk_only"].astype(bool)) == {True}
    assert set(upper_audit["formal_lower_leak_count"].astype(int)) == {0}
    assert set(upper_audit["audit_status"].astype(str)) == {"pass"}
