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


def test_output_files_are_generated_with_blocker_status():
    summary, validation, out = _run_and_load()
    assert (out / "update_comparison_summary.json").is_file()
    assert (out / "update_comparison_summary.md").is_file()
    assert (out / "update_validation_summary.json").is_file()
    assert (out / "update_validation_summary.md").is_file()
    persisted = json.loads((out / "update_validation_summary.json").read_text())
    assert persisted["passed"] is False
    assert summary["passed"] is False
    assert validation["passed"] is False


def test_synthetic_metrics_path_is_not_primary_validation():
    summary, validation, _ = _run_and_load()
    assert summary["synthetic_metrics_used_for_primary_validation"] is False
    assert validation["checks"].get("synthetic_metrics_not_primary_validation", True) is True
    assert "performance_delta_source" not in summary or summary["performance_delta_source"] != "synthetic"


def test_passed_true_requires_existing_runner_executed_true():
    summary, _, _ = _run_and_load()
    if summary["passed"] is True:
        assert summary["existing_runner_executed"] is True
    else:
        assert summary["existing_runner_executed"] is False or summary["task22_status"] == "blocked_by_missing_in_run_update_hook"


def test_existing_runner_execution_failure_is_failed_report():
    summary, validation, _ = _run_and_load()
    if summary["existing_runner_executed"] is False:
        assert summary["passed"] is False
        assert validation["passed"] is False
        assert summary["task22_status"] == "blocked_by_runner_execution"
        assert summary["execution_blocker"]
        assert "missing_dependency" in summary


def test_performance_delta_must_come_from_real_runner_outputs():
    summary, validation, _ = _run_and_load()
    if summary["existing_runner_executed"] is False:
        assert summary["performance_delta"] is None
        assert summary["performance_delta_source"] == "not_available_existing_runner_not_executed"
        assert validation["checks"]["performance_delta_from_real_runner_outputs"] is False
    else:
        assert validation["checks"]["performance_delta_from_real_runner_outputs"] is False


def test_boundary_audit_must_come_from_execution_path():
    summary, validation, _ = _run_and_load()
    audit = summary["boundary_audit"]
    if summary["existing_runner_executed"] is False:
        assert audit["audit_source"] == "not_available_existing_runner_not_executed"
        assert audit["gk_writeback_count"] is None
        assert audit["world_direct_write_count"] is None
        assert validation["checks"]["boundary_audit_from_execution_path"] is False


def test_cases_require_real_runner_or_wrapper_path():
    summary, validation, _ = _run_and_load()
    if summary["existing_runner_executed"] is False:
        cases = {c["case_id"]: c for c in summary["cases"]}
        for case_id in task22.CASE_IDS:
            assert cases[case_id]["runner_execution_path"] == "frozen_archive_import_and_smoke_run_attempt"
            assert cases[case_id]["runner_executed"] is False
            assert cases[case_id]["metrics_source"] == "not_available_existing_runner_not_executed"
        assert validation["checks"]["update_off_runner_executed"] is False
        assert validation["checks"]["controlled_update_on_runner_executed"] is False
        assert validation["checks"]["forced_bad_update_rollback_runner_executed"] is False


def test_synthetic_improvement_cannot_make_target_metric_pass():
    summary, validation, _ = _run_and_load()
    assert summary["synthetic_metrics_used_for_primary_validation"] is False
    if summary["existing_runner_executed"] is False:
        assert "target_metric_improved_or_explicitly_passed_by_existing_metric" not in validation["checks"]
        assert validation["checks"]["synthetic_improvement_cannot_pass_target_metric"] is True


def test_pandas_dependency_is_declared_for_runner_execution():
    summary, _, _ = _run_and_load()
    manifest = summary["dependency_manifest"]
    assert manifest["path"] == "requirements.txt"
    assert manifest["pandas_declared"] is True
    assert (ROOT / "requirements.txt").read_text().strip().startswith("pandas")
    assert summary["dependency_runtime_status"]["pandas_importable"] in {True, False}
