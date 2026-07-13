"""Task22B Hook RC1 execution blocker report.

This file is the CI entrypoint for Task22B Hook RC1 artifacts.  The active
checkout does not contain the Task22B Hook RC1 implementation branch, so this
script must not synthesize success or stand in for the real hook validation.
It emits a failed Execution Blocker Report until the PR #13 implementation is
present in the branch being validated.
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "results/task22b_controlled_canonical_parameter_update_hook_rc1"
CASE_IDS = ["update_off", "controlled_update_on", "forced_bad_update_rollback", "real_watch_only_candidates"]


def _commit_sha() -> str | None:
    env_sha = os.environ.get("GITHUB_SHA")
    if env_sha:
        return env_sha
    proc = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False)
    if proc.returncode == 0:
        return proc.stdout.strip()
    return None


def build_summary() -> tuple[dict[str, Any], dict[str, Any]]:
    checks = {
        "task22b_hook_implementation_present": False,
        "synthetic_metrics_not_primary_validation": True,
        "no_parallel_runner_created": True,
        "runner_not_duplicated": True,
        "validation_failed_instead_of_synthetic_pass": True,
    }
    summary = {
        "task": "Task22B Hook RC1 Execution Blocker Report",
        "task22b_status": "blocked_by_missing_task22b_hook_implementation_branch",
        "scope": "Task22B Hook RC1 controlled canonical ParameterBox update hook validation",
        "artifact_generated_by": "validation/task22b_controlled_canonical_parameter_update_hook_rc1.py",
        "generated_at_utc": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "commit_sha": _commit_sha(),
        "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
        "heavy_validation_run_count": 1,
        "case_ids": CASE_IDS,
        "execution_blocker": (
            "Task22B Hook RC1 implementation files from PR #13 are not present in this checkout; "
            "run this CI fix on branch 85vem4-codex/add-controlled-canonical-parameterbox-update-hook."
        ),
        "existing_runner_executed": False,
        "bounded_canonical_update_hook_connected": False,
        "synthetic_metrics_used_for_primary_validation": False,
        "cases": [],
        "boundary_audit": {"audit_source": "not_available_task22b_hook_implementation_missing"},
        "rollback_audit": {"status": "not_available_task22b_hook_implementation_missing"},
        "canonical_update_audit": {"status": "not_available_task22b_hook_implementation_missing"},
        "pass_conditions": checks,
        "passed": False,
    }
    validation = {"task": summary["task"], "checks": checks, "passed": False}
    return summary, validation


def _md(summary: dict[str, Any], validation: dict[str, Any]) -> tuple[str, str]:
    summary_lines = [
        f"# {summary['task']}",
        "",
        f"task22b_status: `{summary['task22b_status']}`",
        f"passed: `{str(summary['passed']).lower()}`",
        f"execution_blocker: `{summary['execution_blocker']}`",
        f"heavy_validation_run_count: `{summary['heavy_validation_run_count']}`",
        "",
        "## Cases",
    ] + [f"- {case_id}" for case_id in summary["case_ids"]]
    validation_lines = [
        f"# {validation['task']} Validation",
        "",
        f"passed: `{str(validation['passed']).lower()}`",
        "",
        "## Checks",
    ] + [f"- {key}: `{str(value).lower()}`" for key, value in validation["checks"].items()]
    return "\n".join(summary_lines) + "\n", "\n".join(validation_lines) + "\n"


def write_outputs(summary: dict[str, Any], validation: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "update_hook_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    (OUT_DIR / "update_hook_validation.json").write_text(json.dumps(validation, indent=2, sort_keys=True), encoding="utf-8")
    summary_md, validation_md = _md(summary, validation)
    (OUT_DIR / "update_hook_summary.md").write_text(summary_md, encoding="utf-8")
    (OUT_DIR / "update_hook_validation.md").write_text(validation_md, encoding="utf-8")


def main() -> int:
    summary, validation = build_summary()
    write_outputs(summary, validation)
    print(json.dumps({
        "task": summary["task"],
        "task22b_status": summary["task22b_status"],
        "heavy_validation_run_count": summary["heavy_validation_run_count"],
        "passed": summary["passed"],
        "execution_blocker": summary["execution_blocker"],
        "output_dir": str(OUT_DIR),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
