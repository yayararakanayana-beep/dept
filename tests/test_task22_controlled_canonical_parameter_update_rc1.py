import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "task22_controlled_canonical_parameter_update_rc1"
SUMMARY_PATH = OUT / "update_comparison_summary.json"
VALIDATION_PATH = OUT / "update_validation_summary.json"
SUMMARY_MD_PATH = OUT / "update_comparison_summary.md"
VALIDATION_MD_PATH = OUT / "update_validation_summary.md"
CASE_IDS = ["update_off", "controlled_update_on", "forced_bad_update_rollback", "real_watch_only_candidates"]


def _load_artifacts():
    missing = [
        path.relative_to(ROOT).as_posix()
        for path in (SUMMARY_PATH, VALIDATION_PATH, SUMMARY_MD_PATH, VALIDATION_MD_PATH)
        if not path.is_file()
    ]
    if missing:
        message = (
            "Task22B validation artifacts are missing. Run "
            "`python validation/task22_controlled_canonical_parameter_update_rc1.py` "
            "before this artifact/schema test. Missing: " + ", ".join(missing)
        )
        if os.environ.get("GITHUB_ACTIONS") == "true":
            pytest.fail(message)
        pytest.skip(message)

    return (
        json.loads(SUMMARY_PATH.read_text(encoding="utf-8")),
        json.loads(VALIDATION_PATH.read_text(encoding="utf-8")),
    )


@pytest.fixture(scope="module")
def artifacts():
    return _load_artifacts()


def test_output_artifacts_exist_and_report_blocker_status(artifacts):
    summary, validation = artifacts
    assert SUMMARY_PATH.is_file()
    assert SUMMARY_MD_PATH.is_file()
    assert VALIDATION_PATH.is_file()
    assert VALIDATION_MD_PATH.is_file()
    assert validation["passed"] is False
    assert summary["passed"] is False


def test_artifact_schema_contains_task22b_core_fields(artifacts):
    summary, validation = artifacts
    for key in [
        "task",
        "task22_status",
        "existing_runner_executed",
        "execution_blocker",
        "dependency_manifest",
        "dependency_runtime_status",
        "synthetic_metrics_used_for_primary_validation",
        "cases",
        "comparison",
        "performance_delta",
        "performance_delta_source",
        "boundary_audit",
        "canonical_update_audit",
        "rollback_audit",
        "pass_conditions",
        "passed",
    ]:
        assert key in summary
    assert validation["task"] == summary["task"]
    assert isinstance(validation["checks"], dict)
    assert validation["passed"] == summary["passed"]


def test_synthetic_metrics_path_is_not_primary_validation(artifacts):
    summary, validation = artifacts
    assert summary["synthetic_metrics_used_for_primary_validation"] is False
    assert validation["checks"].get("synthetic_metrics_not_primary_validation", True) is True
    assert summary.get("performance_delta_source") != "synthetic"


def test_passed_true_requires_existing_runner_executed_true(artifacts):
    summary, _ = artifacts
    if summary["passed"] is True:
        assert summary["existing_runner_executed"] is True
    else:
        assert summary["existing_runner_executed"] is False or summary["task22_status"] == "blocked_by_missing_in_run_update_hook"


def test_existing_runner_execution_failure_is_failed_report(artifacts):
    summary, validation = artifacts
    if summary["existing_runner_executed"] is False:
        assert summary["passed"] is False
        assert validation["passed"] is False
        assert summary["task22_status"] == "blocked_by_runner_execution"
        assert summary["execution_blocker"]
        assert "missing_dependency" in summary


def test_performance_delta_must_come_from_real_runner_outputs(artifacts):
    summary, validation = artifacts
    if summary["existing_runner_executed"] is False:
        assert summary["performance_delta"] is None
        assert summary["performance_delta_source"] == "not_available_existing_runner_not_executed"
        assert validation["checks"]["performance_delta_from_real_runner_outputs"] is False
    else:
        assert validation["checks"]["performance_delta_from_real_runner_outputs"] is False


def test_boundary_audit_must_come_from_execution_path(artifacts):
    summary, validation = artifacts
    audit = summary["boundary_audit"]
    if summary["existing_runner_executed"] is False:
        assert audit["audit_source"] == "not_available_existing_runner_not_executed"
        assert audit["gk_writeback_count"] is None
        assert audit["world_direct_write_count"] is None
        assert validation["checks"]["boundary_audit_from_execution_path"] is False


def test_cases_require_real_runner_or_wrapper_path(artifacts):
    summary, validation = artifacts
    if summary["existing_runner_executed"] is False:
        cases = {c["case_id"]: c for c in summary["cases"]}
        assert set(cases) == set(CASE_IDS)
        for case_id in CASE_IDS:
            assert cases[case_id]["runner_execution_path"] == "frozen_archive_import_and_smoke_run_attempt"
            assert cases[case_id]["runner_executed"] is False
            assert cases[case_id]["metrics_source"] == "not_available_existing_runner_not_executed"
        assert validation["checks"]["update_off_runner_executed"] is False
        assert validation["checks"]["controlled_update_on_runner_executed"] is False
        assert validation["checks"]["forced_bad_update_rollback_runner_executed"] is False


def test_synthetic_improvement_cannot_make_target_metric_pass(artifacts):
    summary, validation = artifacts
    assert summary["synthetic_metrics_used_for_primary_validation"] is False
    if summary["existing_runner_executed"] is False:
        assert "target_metric_improved_or_explicitly_passed_by_existing_metric" not in validation["checks"]
        assert validation["checks"]["synthetic_improvement_cannot_pass_target_metric"] is True


def test_pandas_dependency_is_declared_for_runner_execution(artifacts):
    summary, _ = artifacts
    manifest = summary["dependency_manifest"]
    assert manifest["path"] == "requirements.txt"
    assert manifest["pandas_declared"] is True
    assert (ROOT / "requirements.txt").read_text(encoding="utf-8").strip().startswith("pandas")
    assert summary["dependency_runtime_status"]["pandas_importable"] in {True, False}


def test_pip_install_attempt_is_recorded(artifacts):
    summary, _ = artifacts
    assert summary["pip_install_attempted"] is True
    assert isinstance(summary["pip_install_exit_code"], int)
    assert "pip_install_stdout_or_summary" in summary
    assert "pip_install_stderr_or_summary" in summary
    if summary["pip_install_exit_code"] != 0:
        assert summary["execution_blocker"].startswith("pip_install_failed")
        assert summary["pip_install_failure_class"] in {"package-index/network", "permission", "version_conflict", None}
        assert summary["passed"] is False
