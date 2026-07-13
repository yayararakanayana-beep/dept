import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "task22b_controlled_canonical_parameter_update_hook_rc1"
SUMMARY_PATH = OUT / "update_hook_summary.json"
VALIDATION_PATH = OUT / "update_hook_validation.json"
SUMMARY_MD_PATH = OUT / "update_hook_summary.md"
VALIDATION_MD_PATH = OUT / "update_hook_validation.md"
CASE_IDS = ["update_off", "controlled_update_on", "forced_bad_update_rollback", "real_watch_only_candidates"]


def _load_artifacts():
    missing = [
        path.relative_to(ROOT).as_posix()
        for path in (SUMMARY_PATH, VALIDATION_PATH, SUMMARY_MD_PATH, VALIDATION_MD_PATH)
        if not path.is_file()
    ]
    if missing:
        message = (
            "Task22B Hook RC1 artifacts are missing. Run "
            "`python validation/task22b_controlled_canonical_parameter_update_hook_rc1.py` "
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


def test_task22b_hook_artifacts_exist(artifacts):
    summary, validation = artifacts
    assert SUMMARY_PATH.is_file()
    assert VALIDATION_PATH.is_file()
    assert SUMMARY_MD_PATH.is_file()
    assert VALIDATION_MD_PATH.is_file()
    assert validation["passed"] == summary["passed"]


def test_task22b_hook_artifact_schema_and_provenance(artifacts):
    summary, validation = artifacts
    for key in [
        "task",
        "task22b_status",
        "artifact_generated_by",
        "generated_at_utc",
        "commit_sha",
        "workflow_run_id",
        "heavy_validation_run_count",
        "case_ids",
        "execution_blocker",
        "synthetic_metrics_used_for_primary_validation",
        "boundary_audit",
        "rollback_audit",
        "canonical_update_audit",
        "pass_conditions",
        "passed",
    ]:
        assert key in summary
    assert summary["artifact_generated_by"] == "validation/task22b_controlled_canonical_parameter_update_hook_rc1.py"
    assert summary["heavy_validation_run_count"] == 1
    assert summary["case_ids"] == CASE_IDS
    assert validation["task"] == summary["task"]
    assert isinstance(validation["checks"], dict)


def test_task22b_hook_does_not_use_synthetic_success(artifacts):
    summary, validation = artifacts
    assert summary["synthetic_metrics_used_for_primary_validation"] is False
    assert validation["checks"].get("synthetic_metrics_not_primary_validation") is True
    if summary["passed"] is True:
        assert summary.get("existing_runner_executed") is True
        assert summary.get("bounded_canonical_update_hook_connected") is True


def test_task22b_hook_boundary_and_update_audits_remain_present(artifacts):
    summary, _ = artifacts
    assert isinstance(summary["boundary_audit"], dict)
    assert isinstance(summary["rollback_audit"], dict)
    assert isinstance(summary["canonical_update_audit"], dict)
    if summary["passed"] is False:
        assert summary["execution_blocker"]


def test_task22b_hook_blocker_report_remains_failed_when_validation_cannot_execute(artifacts):
    summary, validation = artifacts
    if summary.get("existing_runner_executed") is False or not summary.get("bounded_canonical_update_hook_connected"):
        assert summary["passed"] is False
        assert validation["passed"] is False
        assert summary["execution_blocker"]
