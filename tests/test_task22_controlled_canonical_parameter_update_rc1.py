from pathlib import Path
import importlib.util
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "validation" / "task22_controlled_canonical_parameter_update_rc1.py"
spec = importlib.util.spec_from_file_location("task22", MODULE_PATH)
task22 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = task22
spec.loader.exec_module(task22)


def _run_and_load():
    summary, validation = task22.build_summary()
    task22.write_outputs(summary, validation)
    out = ROOT / "results" / "task22_controlled_canonical_parameter_update_rc1"
    return summary, validation, out


def test_output_files_are_generated_and_validation_passes():
    summary, validation, out = _run_and_load()
    assert (out / "update_comparison_summary.json").is_file()
    assert (out / "update_comparison_summary.md").is_file()
    assert (out / "update_validation_summary.json").is_file()
    assert (out / "update_validation_summary.md").is_file()
    assert json.loads((out / "update_validation_summary.json").read_text())["passed"] is True
    assert summary["passed"] is True
    assert validation["passed"] is True


def test_existing_runner_reused_and_no_parallel_runner_created():
    summary, validation, _ = _run_and_load()
    assert summary["reused_runner"]
    assert summary["reused_runner_files"]
    assert validation["checks"]["existing_runner_reused"] is True
    assert validation["checks"]["no_parallel_runner_created"] is True


def test_case_write_counts_and_watch_only_behavior():
    summary, _, _ = _run_and_load()
    cases = {c["case_id"]: c for c in summary["cases"]}
    assert cases["update_off"]["canonical_write_count"] == 0
    assert cases["real_watch_only_candidates"]["canonical_write_count"] == 0
    assert cases["controlled_update_on"]["canonical_write_count"] >= 1
    assert cases["controlled_update_on"]["canonical_write_count"] <= 1


def test_update_delta_bounded_and_rollback_snapshot_exists():
    summary, _, _ = _run_and_load()
    cases = {c["case_id"]: c for c in summary["cases"]}
    controlled = cases["controlled_update_on"]
    forced = cases["forced_bad_update_rollback"]
    assert abs(controlled["parameter_delta"]) <= controlled["max_step_delta"]
    assert forced["rollback_snapshot_id"]
    assert forced["rollback_count"] >= 1
    assert forced["rollback_restored_original"] is True
    assert forced["parameter_before"] == forced["parameter_after"]


def test_boundary_counts_remain_zero():
    summary, validation, _ = _run_and_load()
    for case in summary["cases"]:
        flags = case["boundary_flags"]
        assert flags["gk_writeback_count"] == 0
        assert flags["world_direct_write_count"] == 0
        assert flags["action_module_internal_connection_count"] == 0
        assert flags["actionframe_direct_generation_count"] == 0
        assert flags["boundary_violation_count"] == 0
    assert validation["checks"]["no_gk_writeback"] is True
    assert validation["checks"]["no_world_direct_write"] is True
    assert validation["checks"]["no_action_module_internal_connection"] is True
    assert validation["checks"]["no_actionframe_direct_generation"] is True
    assert validation["checks"]["no_boundary_violation"] is True


def test_performance_delta_improves_target_metric_and_safety_ok():
    summary, validation, _ = _run_and_load()
    delta = summary["performance_delta"]["update_off_vs_controlled_update_on"]
    assert delta
    assert delta["residual"] < 0 or delta["noise"] < 0 or delta["action_quality"] > 0
    assert validation["checks"]["target_metric_improved_or_explicitly_passed_by_existing_metric"] is True
    assert validation["checks"]["safety_metrics_not_materially_worse"] is True
    assert validation["checks"]["performance_delta_recorded"] is True
