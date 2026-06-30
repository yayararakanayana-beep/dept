import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/task22a_existing_runner_execution_environment_recovery_rc1"
SUMMARY = OUT / "environment_recovery_summary.json"
VALIDATION = OUT / "environment_recovery_validation.json"


def load():
    assert SUMMARY.exists()
    assert VALIDATION.exists()
    return json.loads(SUMMARY.read_text()), json.loads(VALIDATION.read_text())


def test_task22a_result_files_and_required_field_groups_exist():
    summary, validation = load()
    for key in ["archive_path", "archive_exists", "zipfile_is_zipfile", "zip_member_count", "required_runner_files", "required_runner_files_present", "archive_integrity_passed"]:
        assert key in summary
    for key in ["extraction_attempted", "extraction_succeeded", "extraction_error", "extracted_root_exists", "package_root_exists", "import_path_added", "extraction_check_passed"]:
        assert key in summary
    for key in ["pip_install_attempted", "pip_install_command", "pip_install_exit_code", "pip_install_stdout_or_summary", "pip_install_stderr_or_summary", "pip_install_failure_class"]:
        assert key in summary
    for key in ["pandas_importable", "pandas_version", "pandas_import_error"]:
        assert key in summary
    for key in ["existing_runner_smoke_attempted", "existing_runner_found", "existing_runner_executed", "runner_smoke_exit_status", "runner_smoke_error", "smoke_output_type", "smoke_output_keys", "smoke_output_summary", "runner_traceback"]:
        assert key in summary
    assert "passed" in validation


def test_task22a_pass_requires_real_runner_and_dependency_success():
    summary, validation = load()
    if summary["passed"] or validation["passed"]:
        assert summary["existing_runner_executed"] is True
        assert summary["pandas_importable"] is True
        assert summary["synthetic_metrics_used"] is False
        assert summary["parallel_runner_created"] is False
        assert summary["bounded_update_hook_connected"] is False


def test_task22a_failures_remain_failed_without_substitutes():
    summary, validation = load()
    if summary["pip_install_exit_code"] != 0:
        assert summary["passed"] is False
        assert validation["passed"] is False
    if not summary["existing_runner_executed"]:
        assert summary["passed"] is False
        assert validation["passed"] is False
    assert summary["synthetic_metrics_used"] is False
    assert summary["parallel_runner_created"] is False
    assert summary["bounded_update_hook_connected"] is False
    assert "mock" not in str(summary.get("smoke_output_summary", "")).lower()
