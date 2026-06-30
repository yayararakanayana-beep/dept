import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "task22b_controlled_canonical_parameter_update_hook_rc1"
SUMMARY_JSON = OUT / "update_hook_summary.json"
VALIDATION_JSON = OUT / "update_hook_validation.json"
SUMMARY_MD = OUT / "update_hook_summary.md"
VALIDATION_MD = OUT / "update_hook_validation.md"
EXPECTED_CASE_IDS = {
    "update_off",
    "controlled_update_on",
    "forced_bad_update_rollback",
    "real_watch_only_candidates",
}


def _require_artifacts() -> tuple[dict, dict, str, str]:
    paths = [SUMMARY_JSON, VALIDATION_JSON, SUMMARY_MD, VALIDATION_MD]
    missing = [str(path.relative_to(ROOT)) for path in paths if not path.is_file()]
    if missing:
        message = "Task22B Hook RC1 artifacts are missing; run validation/task22b_controlled_canonical_parameter_update_hook_rc1.py first: " + ", ".join(missing)
        if os.environ.get("GITHUB_ACTIONS") == "true":
            pytest.fail(message)
        pytest.skip(message)
    return (
        json.loads(SUMMARY_JSON.read_text(encoding="utf-8")),
        json.loads(VALIDATION_JSON.read_text(encoding="utf-8")),
        SUMMARY_MD.read_text(encoding="utf-8"),
        VALIDATION_MD.read_text(encoding="utf-8"),
    )


@pytest.fixture(scope="module")
def artifacts() -> tuple[dict, dict, str, str]:
    return _require_artifacts()


def test_required_artifacts_exist_and_json_agrees(artifacts):
    summary, validation, summary_md, validation_md = artifacts
    assert SUMMARY_JSON.is_file()
    assert VALIDATION_JSON.is_file()
    assert SUMMARY_MD.is_file()
    assert VALIDATION_MD.is_file()
    assert validation["passed"] == summary["passed"]
    assert summary["task"] in summary_md
    assert validation["task"] in validation_md


def test_required_four_cases_exist(artifacts):
    summary, _, _, _ = artifacts
    assert {case["case_id"] for case in summary["cases"]} == EXPECTED_CASE_IDS
    assert set(summary.get("case_ids", EXPECTED_CASE_IDS)) == EXPECTED_CASE_IDS


def test_primary_validation_uses_real_metrics_not_synthetic(artifacts):
    summary, _, _, _ = artifacts
    assert summary.get("synthetic_metrics_used_for_primary_validation", summary.get("synthetic_metrics_used")) is False
    if summary["passed"]:
        source = summary["performance_delta"]["performance_delta_source"]
        assert source == "real_runner_output"
        assert not any(token in source for token in ["synthetic", "fixed", "mock", "stub"])


def test_required_audits_are_recorded(artifacts):
    summary, _, _, _ = artifacts
    assert isinstance(summary.get("boundary_audit"), dict)
    assert isinstance(summary.get("rollback_audit"), dict)
    assert isinstance(summary.get("canonical_update_audit", summary.get("boundary_audit")), dict)


def test_passed_true_requires_runner_execution_and_bounded_hook_connection(artifacts):
    summary, _, _, _ = artifacts
    cases = {case["case_id"]: case for case in summary["cases"]}
    if summary["passed"]:
        assert summary["existing_runner_executed"] is True
        assert summary["bounded_update_hook_connected"] is True
        assert summary["safe_update_hook_found"] is True
        assert all(case["runner_executed"] for case in cases.values())
        assert cases["controlled_update_on"]["canonical_write_count"] == 1
        assert cases["update_off"]["canonical_write_count"] == 0
        assert cases["real_watch_only_candidates"]["canonical_write_count"] == 0
        assert cases["forced_bad_update_rollback"]["rollback_count"] >= 1
        assert cases["forced_bad_update_rollback"]["rollback_restored_original"] is True


def test_passed_false_records_blocker_or_fail_reason(artifacts):
    summary, validation, _, _ = artifacts
    if not summary["passed"]:
        blocker_fields = [
            summary.get("blocker_stage"),
            summary.get("execution_blocker"),
            summary.get("next_required_fix"),
            summary.get("task22b_status"),
            validation.get("blocker_stage"),
            validation.get("execution_blocker"),
        ]
        assert any(field for field in blocker_fields)


def test_repository_boundary_flags_remain_closed_on_pass(artifacts):
    summary, _, _, _ = artifacts
    assert summary["parallel_runner_created"] is False
    assert summary["frozen_runner_modified"] is False
    audit = summary["boundary_audit"]
    if summary["passed"]:
        assert audit["gk_writeback_count"] == 0
        assert audit["world_direct_write_count"] == 0
        assert audit["action_module_internal_connection_count"] == 0
        assert audit["actionframe_direct_generation_count"] == 0


def test_boundary_and_rollback_failure_conditions_remain_visible(artifacts):
    summary, _, _, _ = artifacts
    if not summary["existing_runner_executed"]:
        assert summary["passed"] is False
    if summary["performance_delta"].get("performance_delta_source") == "unavailable_real_output_insufficient":
        assert summary["passed"] is False
    if summary.get("boundary_audit_available") is False:
        assert summary["passed"] is False
    if summary.get("real_runner_effect_audit", {}).get("controlled_boundary_regression_detected") is True:
        assert summary["passed"] is False
