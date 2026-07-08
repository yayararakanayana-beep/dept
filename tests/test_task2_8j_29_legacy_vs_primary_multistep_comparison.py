from __future__ import annotations

import importlib.util
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "validation" / "task2_8j_29_legacy_vs_primary_multistep_comparison.py"
SPEC = importlib.util.spec_from_file_location("task2_8j_29_validation", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
TASK2_8J_29 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(TASK2_8J_29)


def test_task2_8j_29_builds_and_writes_legacy_vs_primary_comparison_tables(tmp_path: Path):
    outputs = TASK2_8J_29.write_task2_8j_29_comparison(tmp_path)

    summary = outputs["task2_8j_29_summary"]
    per_step = outputs["task2_8j_29_per_step_metrics"]
    route_delta = outputs["task2_8j_29_route_delta"]

    expected_files = [
        "task2_8j_29_summary.csv",
        "task2_8j_29_per_step_metrics.csv",
        "task2_8j_29_route_delta.csv",
        "task2_8j_29_manifest.json",
    ]
    for filename in expected_files:
        assert (tmp_path / filename).exists(), filename

    assert set(summary["scenario"].astype(str)) == set(TASK2_8J_29.TASK2_8J_29_SCENARIOS)
    assert set(summary["comparison_status"].astype(str)) == {"pass"}
    assert bool(summary["legacy_all_planning_pass"].astype(bool).all())
    assert bool(summary["task2_8j_all_planning_pass"].astype(bool).all())
    assert bool(summary["legacy_all_execution_pass"].astype(bool).all())
    assert bool(summary["task2_8j_all_execution_pass"].astype(bool).all())
    assert bool(summary["legacy_all_actionframe_only"].astype(bool).all())
    assert bool(summary["task2_8j_all_actionframe_only"].astype(bool).all())
    assert bool((summary["task2_8j_total_primary_candidate_rows"].astype(int) > 0).all())
    assert bool((summary["task2_8j_total_primary_need_rows"].astype(int) > 0).all())

    expected_rows = len(TASK2_8J_29.TASK2_8J_29_SCENARIOS) * 2 * TASK2_8J_29.TASK2_8J_29_STEPS
    assert len(per_step) == expected_rows
    assert set(per_step["route"].astype(str)) == {"legacy", "task2_8j_primary"}
    assert set(per_step["gt_main_map_name"].astype(str)) == {"static_pca_7"}
    assert set(per_step["static_pca7_view_attached"].astype(bool)) == {True}
    assert set(per_step["legacy_gt_columns_preserved"].astype(bool)) == {True}
    assert bool((per_step["action_candidate_rows"].astype(int) > 0).all())
    assert set(per_step["actionmodule_received_actionframe_only"].astype(bool)) == {True}
    assert set(per_step["direct_gk_input_to_actionmodule"].astype(bool)) == {False}
    assert set(per_step["direct_ot_input_to_actionmodule"].astype(bool)) == {False}
    assert set(per_step["direct_parameter_box_input_to_actionmodule"].astype(bool)) == {False}
    assert set(per_step["canonical_parameter_write_performed"].astype(bool)) == {False}
    assert set(per_step["transition_time_advanced_by_one"].astype(bool)) == {True}
    assert set(per_step["transition_gk_writeback_performed"].astype(bool)) == {False}
    assert set(per_step["transition_ot_writeback_performed"].astype(bool)) == {False}
    assert set(per_step["transition_canonical_write_performed"].astype(bool)) == {False}

    primary = per_step[per_step["route"].astype(str) == "task2_8j_primary"]
    legacy = per_step[per_step["route"].astype(str) == "legacy"]
    assert bool(primary["task2_8j_primary_route_used"].astype(bool).all())
    assert bool((primary["task2_8j_primary_candidate_rows"].astype(int) > 0).all())
    assert bool((primary["task2_8j_primary_need_rows"].astype(int) > 0).all())
    assert set(legacy["task2_8j_primary_route_used"].astype(bool)) == {False}
    assert set(legacy["task2_8j_primary_candidate_rows"].astype(int)) == {0}

    expected_delta_rows = len(TASK2_8J_29.TASK2_8J_29_SCENARIOS) * TASK2_8J_29.TASK2_8J_29_STEPS
    assert len(route_delta) == expected_delta_rows
    assert bool(route_delta["both_actionframe_only"].astype(bool).all())
    assert bool(route_delta["legacy_transition_time_ok"].astype(bool).all())
    assert bool(route_delta["task2_8j_transition_time_ok"].astype(bool).all())
    assert "gate_risk_delta_task2_minus_legacy" in route_delta.columns
    assert "mean_delta_relation_lock_delta_task2_minus_legacy" in route_delta.columns
