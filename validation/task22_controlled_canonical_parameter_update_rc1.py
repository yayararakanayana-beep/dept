"""Task22 runner execution blocker validation.

Task22 must validate bounded canonical lower-ParameterBox updates by executing the
existing closed-loop runner.  This script therefore attempts to load and execute
that runner from the frozen RC1 archive.  If the runner cannot execute in the
active scaffold, the report is explicitly failed/blocked instead of using
synthetic metrics or fixed boundary flags to pass.
"""
from __future__ import annotations

import importlib
import json
import subprocess
import sys
import tempfile
import traceback
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "DEPT2_FullSpecIntegratedClosedLoopRunner_RC1_Freeze.zip"
TASK21_DECISIONS = ROOT / "results/task21_parameter_adoption_precheck_v0/precheck_decision_summary.json"
TASK21_VALIDATION = ROOT / "results/task21_parameter_adoption_precheck_v0/precheck_validation_summary.json"
TASK20J_CONTRACT = ROOT / "results/task20j_gate_contract_freeze/gate_contract_freeze.json"
OUT_DIR = ROOT / "results/task22_controlled_canonical_parameter_update_rc1"
MAX_STEP_DELTA = 0.05
REUSED_RUNNER_FILES = [
    "DEPT2_FullSpecIntegratedClosedLoopRunner_RC1_Freeze.zip::DEPT2_FullSpecIntegratedClosedLoopRunner_RC1_Freeze/dept2_fullspec_runner_rc1/runner/fullspec_integrated_closed_loop_runner.py",
    "DEPT2_FullSpecIntegratedClosedLoopRunner_RC1_Freeze.zip::DEPT2_FullSpecIntegratedClosedLoopRunner_RC1_Freeze/dept2_fullspec_runner_rc1/modules/parameter_shadow_box.py",
    "DEPT2_FullSpecIntegratedClosedLoopRunner_RC1_Freeze.zip::DEPT2_FullSpecIntegratedClosedLoopRunner_RC1_Freeze/DEPT2_ActionModule_ActuationPrimitives_RC1/dept2_system/parameter_box.py",
]
CASE_IDS = ["update_off", "controlled_update_on", "forced_bad_update_rollback", "real_watch_only_candidates"]
_PIP_INSTALL_RESULT: dict[str, Any] | None = None




def _summarize_stream(text: str, limit: int = 1200) -> str:
    compact = "\n".join(line for line in text.splitlines() if line.strip())
    if len(compact) <= limit:
        return compact
    return compact[:limit] + "...<truncated>"


def _classify_pip_failure(stdout: str, stderr: str) -> str | None:
    text = f"{stdout}\n{stderr}".lower()
    if "tunnel connection failed" in text or "403 forbidden" in text or "proxy" in text:
        return "package-index/network"
    if "permission denied" in text:
        return "permission"
    if "version" in text or "requires" in text or "conflict" in text:
        return "version_conflict"
    if "no matching distribution" in text or "from versions: none" in text:
        return "package-index/network"
    return None


def _attempt_pip_install() -> dict[str, Any]:
    global _PIP_INSTALL_RESULT
    if _PIP_INSTALL_RESULT is not None:
        return _PIP_INSTALL_RESULT
    cmd = [sys.executable, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")]
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)
    _PIP_INSTALL_RESULT = {
        "pip_install_attempted": True,
        "pip_install_command": "python -m pip install -r requirements.txt",
        "pip_install_exit_code": int(proc.returncode),
        "pip_install_stdout_or_summary": _summarize_stream(proc.stdout),
        "pip_install_stderr_or_summary": _summarize_stream(proc.stderr),
        "pip_install_failure_class": None if proc.returncode == 0 else _classify_pip_failure(proc.stdout, proc.stderr),
    }
    return _PIP_INSTALL_RESULT


def _dependency_runtime_status() -> dict[str, Any]:
    try:
        pandas = importlib.import_module("pandas")
    except ModuleNotFoundError as exc:
        return {"pandas_importable": False, "import_error": f"{type(exc).__name__}: {exc}"}
    return {"pandas_importable": True, "version": getattr(pandas, "__version__", "unknown")}

def _dependency_manifest() -> dict[str, Any]:
    manifest = ROOT / "requirements.txt"
    if not manifest.exists():
        return {"path": None, "pandas_declared": False}
    lines = [line.strip() for line in manifest.read_text(encoding="utf-8").splitlines()]
    return {
        "path": "requirements.txt",
        "pandas_declared": any(line and not line.startswith("#") and line.split("=", 1)[0].split(">", 1)[0].split("<", 1)[0].strip() == "pandas" for line in lines),
    }

def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _archive_required_files() -> list[str]:
    if not ARCHIVE.exists():
        raise FileNotFoundError(f"missing runner archive: {ARCHIVE}")
    required = [item.split("::", 1)[1] for item in REUSED_RUNNER_FILES]
    with zipfile.ZipFile(ARCHIVE) as zf:
        names = set(zf.namelist())
    return [name for name in required if name not in names]


def _missing_dependency_from_error(exc: BaseException) -> str | None:
    if isinstance(exc, ModuleNotFoundError):
        return exc.name
    text = "\n".join(traceback.format_exception_only(type(exc), exc))
    if "No module named" in text:
        return text.rsplit("No module named", 1)[-1].strip().strip("'").strip('"')
    return None


def _attempt_existing_runner_execution() -> dict[str, Any]:
    """Attempt to import and run the archived RC1 closed-loop runner.

    The archive is extracted to a temporary directory only.  Nothing from the
    archive is committed into the repository, and no parallel runner is created.
    """
    missing_files = _archive_required_files()
    if missing_files:
        return {
            "existing_runner_found": False,
            "existing_runner_executed": False,
            "execution_blocker": f"missing required runner files: {missing_files}",
            "missing_dependency": None,
            "traceback": None,
        }

    with tempfile.TemporaryDirectory(prefix="task22_runner_exec_") as tmp:
        with zipfile.ZipFile(ARCHIVE) as zf:
            zf.extractall(tmp)
        runner_root = Path(tmp) / "DEPT2_FullSpecIntegratedClosedLoopRunner_RC1_Freeze"
        sys.path.insert(0, str(runner_root))
        for module_name in list(sys.modules):
            if module_name == "dept2_fullspec_runner_rc1" or module_name.startswith("dept2_fullspec_runner_rc1."):
                del sys.modules[module_name]
        try:
            contracts = importlib.import_module("dept2_fullspec_runner_rc1.contracts")
            runner_mod = importlib.import_module("dept2_fullspec_runner_rc1.runner")
            cfg = contracts.FullSpecRunnerConfig(steps=1, seed=2200, scenario="normal", exploration_enabled=True)
            runner = runner_mod.FullSpecIntegratedClosedLoopRunner(cfg)
            outputs = runner.run()
            return {
                "existing_runner_found": True,
                "existing_runner_executed": True,
                "execution_blocker": None,
                "missing_dependency": None,
                "traceback": None,
                "smoke_output_tables": sorted(outputs.keys()) if isinstance(outputs, dict) else [],
            }
        except BaseException as exc:  # report blocker instead of fabricating pass data
            return {
                "existing_runner_found": True,
                "existing_runner_executed": False,
                "execution_blocker": f"{type(exc).__name__}: {exc}",
                "missing_dependency": _missing_dependency_from_error(exc),
                "traceback": traceback.format_exc(limit=8),
            }
        finally:
            try:
                sys.path.remove(str(runner_root))
            except ValueError:
                pass


def _blocked_case(case_id: str, seed: int, exec_result: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "description": {
            "update_off": "blocked before update_off runner execution completed",
            "controlled_update_on": "blocked before in-run bounded canonical update could be connected",
            "forced_bad_update_rollback": "blocked before forced bad update and measured rollback could execute",
            "real_watch_only_candidates": "blocked before Task21 watch_only non-update could be confirmed by runner execution",
        }[case_id],
        "seed": seed,
        "runner_executed": False,
        "runner_execution_path": "frozen_archive_import_and_smoke_run_attempt",
        "commit_enabled": case_id != "update_off",
        "forced_bad_update": case_id == "forced_bad_update_rollback",
        "source_candidate": None,
        "canonical_write_count": None,
        "rollback_count": None,
        "parameter_before": None,
        "parameter_after": None,
        "parameter_delta": None,
        "rollback_snapshot_id": None,
        "metrics_before": None,
        "metrics_after": None,
        "metrics_source": "not_available_existing_runner_not_executed",
        "performance_delta_source": "not_available_existing_runner_not_executed",
        "boundary_flags": {
            "canonical_write_count": None,
            "gk_writeback_count": None,
            "world_direct_write_count": None,
            "action_module_internal_connection_count": None,
            "actionframe_direct_generation_count": None,
            "boundary_violation_count": None,
            "audit_source": "not_available_existing_runner_not_executed",
        },
        "execution_blocker": exec_result["execution_blocker"],
        "missing_dependency": exec_result["missing_dependency"],
        "passed": False,
    }


def build_summary() -> tuple[dict[str, Any], dict[str, Any]]:
    task21_decisions = _read_json(TASK21_DECISIONS)
    _read_json(TASK21_VALIDATION)
    _read_json(TASK20J_CONTRACT)
    dependency_manifest = _dependency_manifest()
    pip_install_result = _attempt_pip_install()
    dependency_runtime_status = _dependency_runtime_status()
    if pip_install_result["pip_install_exit_code"] != 0 and not dependency_runtime_status.get("pandas_importable", False):
        exec_result = {
            "existing_runner_found": True,
            "existing_runner_executed": False,
            "execution_blocker": f"pip_install_failed: {pip_install_result.get('pip_install_failure_class') or 'unclassified'}",
            "missing_dependency": "pandas",
            "traceback": None,
        }
    else:
        exec_result = _attempt_existing_runner_execution()

    if not exec_result["existing_runner_executed"]:
        cases = [_blocked_case(case_id, 2201 + idx, exec_result) for idx, case_id in enumerate(CASE_IDS)]
        checks = {
            "existing_runner_found": exec_result["existing_runner_found"],
            "existing_runner_executed": False,
            "no_parallel_runner_created": True,
            "synthetic_metrics_not_primary_validation": True,
            "passed_requires_existing_runner_execution": True,
            "update_off_runner_executed": False,
            "controlled_update_on_runner_executed": False,
            "forced_bad_update_rollback_runner_executed": False,
            "real_watch_only_candidates_runner_executed": False,
            "performance_delta_from_real_runner_outputs": False,
            "boundary_audit_from_execution_path": False,
            "synthetic_improvement_cannot_pass_target_metric": True,
            "existing_runner_execution_blocker_recorded": bool(exec_result["execution_blocker"]),
            "missing_dependency_recorded_when_present": exec_result["missing_dependency"] is not None,
            "validation_failed_instead_of_synthetic_pass": True,
        }
        summary = {
            "task": "Task22 Runner Execution Blocker Report",
            "task22_status": "blocked_by_runner_execution",
            "scope": "attempt existing closed-loop runner execution before any bounded canonical ParameterBox update validation",
            "reused_runner": "FullSpecIntegratedClosedLoopRunner RC1 from frozen archive",
            "reused_runner_files": REUSED_RUNNER_FILES,
            "existing_runner_found": exec_result["existing_runner_found"],
            "existing_runner_executed": False,
            "execution_blocker": exec_result["execution_blocker"],
            "missing_dependency": exec_result["missing_dependency"],
            "runner_traceback": exec_result["traceback"],
            "no_parallel_runner_created": True,
            "dependency_manifest": dependency_manifest,
            "dependency_runtime_status": dependency_runtime_status,
            **pip_install_result,
            "synthetic_metrics_used_for_primary_validation": False,
            "task21_input_read": True,
            "task21_candidate_count": len(task21_decisions.get("decisions", [])) if isinstance(task21_decisions, dict) else None,
            "cases": cases,
            "comparison": {
                "cases_compared": CASE_IDS,
                "comparison_status": "not_computed_runner_execution_blocked",
            },
            "performance_delta": None,
            "performance_delta_source": "not_available_existing_runner_not_executed",
            "boundary_audit": {
                "canonical_write_count": None,
                "gk_writeback_count": None,
                "world_direct_write_count": None,
                "action_module_internal_connection_count": None,
                "actionframe_direct_generation_count": None,
                "boundary_violation_count": None,
                "audit_source": "not_available_existing_runner_not_executed",
            },
            "canonical_update_audit": {
                "max_writes_per_run": 1,
                "target_scope": "lower ParameterBox only",
                "controlled_write_count": None,
                "real_watch_only_write_count": None,
                "source_config_permanently_modified": False,
                "status": "not_executed_runner_blocked",
            },
            "rollback_audit": {
                "rollback_count": None,
                "rollback_reason": None,
                "rollback_snapshot_id": None,
                "parameter_before_update": None,
                "parameter_after_update": None,
                "parameter_after_rollback": None,
                "rollback_restored_original": None,
                "status": "not_executed_runner_blocked",
            },
            "pass_conditions": checks,
            "passed": False,
            "next_required_fix": [
                "Resolve the recorded pip install blocker so `python -m pip install -r requirements.txt` can install pandas into the active validation environment.",
                "Then connect the bounded canonical update hook to the runner-owned lower ParameterBox state during closed-loop execution.",
                "Compute performance_delta and boundary counts only from real runner outputs/audits.",
            ],
        }
        return summary, {"task": summary["task"], "checks": checks, "passed": False}

    # This branch is intentionally conservative.  Until the runner can execute
    # and a reviewed in-run canonical update hook is connected, Task22 must not
    # claim success.
    checks = {
        "existing_runner_found": True,
        "existing_runner_executed": True,
        "bounded_canonical_update_hook_connected": False,
        "performance_delta_from_real_runner_outputs": False,
        "boundary_audit_from_execution_path": False,
        "validation_failed_instead_of_incomplete_pass": True,
    }
    summary = {
        "task": "Task22 Runner Execution Blocker Report",
        "task22_status": "blocked_by_missing_in_run_update_hook",
        "scope": "runner smoke execution succeeded, but Task22 canonical update hook is not implemented in the existing runner",
        "reused_runner": "FullSpecIntegratedClosedLoopRunner RC1 from frozen archive",
        "reused_runner_files": REUSED_RUNNER_FILES,
        "existing_runner_found": True,
        "existing_runner_executed": True,
        "execution_blocker": "runner smoke executed, but no reviewed in-run canonical ParameterBox update hook is connected",
        "missing_dependency": None,
        "no_parallel_runner_created": True,
        "dependency_manifest": dependency_manifest,
        "dependency_runtime_status": dependency_runtime_status,
        **pip_install_result,
        "synthetic_metrics_used_for_primary_validation": False,
        "cases": [],
        "comparison": {"cases_compared": CASE_IDS, "comparison_status": "not_computed_update_hook_missing"},
        "performance_delta": None,
        "boundary_audit": {"audit_source": "not_available_update_hook_missing"},
        "canonical_update_audit": {"status": "not_executed_update_hook_missing"},
        "rollback_audit": {"status": "not_executed_update_hook_missing"},
        "pass_conditions": checks,
        "passed": False,
    }
    return summary, {"task": summary["task"], "checks": checks, "passed": False}


def _md(summary: dict[str, Any], validation: dict[str, Any]) -> tuple[str, str]:
    lines = [
        f"# {summary['task']}",
        "",
        f"task22_status: `{summary.get('task22_status')}`",
        f"passed: `{str(summary['passed']).lower()}`",
        f"existing_runner_executed: `{str(summary.get('existing_runner_executed')).lower()}`",
        f"execution_blocker: `{summary.get('execution_blocker')}`",
        f"missing_dependency: `{summary.get('missing_dependency')}`",
        "",
        "## Cases",
    ]
    for c in summary.get("cases", []):
        lines += [
            f"### {c['case_id']}",
            f"- runner_executed: `{str(c['runner_executed']).lower()}`",
            f"- metrics_source: `{c['metrics_source']}`",
            f"- execution_blocker: `{c['execution_blocker']}`",
            "",
        ]
    lines += ["## Next Required Fix"] + [f"- {item}" for item in summary.get("next_required_fix", [])]
    vlines = [f"# {validation['task']} Validation", "", f"passed: `{str(validation['passed']).lower()}`", "", "## Checks"]
    vlines += [f"- {k}: `{str(v).lower()}`" for k, v in validation["checks"].items()]
    return "\n".join(lines) + "\n", "\n".join(vlines) + "\n"


def write_outputs(summary: dict[str, Any], validation: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "update_comparison_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    (OUT_DIR / "update_validation_summary.json").write_text(json.dumps(validation, indent=2, sort_keys=True), encoding="utf-8")
    comp_md, val_md = _md(summary, validation)
    (OUT_DIR / "update_comparison_summary.md").write_text(comp_md, encoding="utf-8")
    (OUT_DIR / "update_validation_summary.md").write_text(val_md, encoding="utf-8")


def main() -> int:
    summary, validation = build_summary()
    write_outputs(summary, validation)
    print(json.dumps({
        "task": summary["task"],
        "task22_status": summary.get("task22_status"),
        "pip_install_attempted": summary.get("pip_install_attempted"),
        "pip_install_exit_code": summary.get("pip_install_exit_code"),
        "existing_runner_executed": summary.get("existing_runner_executed"),
        "missing_dependency": summary.get("missing_dependency"),
        "passed": summary["passed"],
        "output_dir": str(OUT_DIR),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
