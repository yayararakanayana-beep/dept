"""Task22A existing runner execution environment recovery RC1.

This diagnostic validates only whether the frozen RC1 runner archive can be
found, extracted, supplied with dependencies, and smoke-run for one step.  It
must not connect bounded canonical ParameterBox update hooks or substitute
synthetic/mock metrics for runner execution.
"""
from __future__ import annotations

import importlib
import json
import os
import platform
import subprocess
import sys
import tempfile
import traceback
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "DEPT2_FullSpecIntegratedClosedLoopRunner_RC1_Freeze.zip"
OUT_DIR = ROOT / "results/task22a_existing_runner_execution_environment_recovery_rc1"
REQUIRED_RUNNER_FILES = [
    "dept2_fullspec_runner_rc1/runner/fullspec_integrated_closed_loop_runner.py",
    "dept2_fullspec_runner_rc1/modules/parameter_shadow_box.py",
    "DEPT2_ActionModule_ActuationPrimitives_RC1/dept2_system/parameter_box.py",
]


def _summarize(text: str, limit: int = 1600) -> str:
    compact = "\n".join(line for line in text.splitlines() if line.strip())
    return compact if len(compact) <= limit else compact[:limit] + "...<truncated>"


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False)


def _classify_pip_failure(code: int, stdout: str, stderr: str) -> str:
    if code == 0:
        return "none"
    text = f"{stdout}\n{stderr}".lower()
    if "no module named pip" in text or "pip" in text and "not found" in text:
        return "pip-not-found"
    if "tunnel connection failed" in text or "403 forbidden" in text or "proxy" in text or "connection" in text or "timed out" in text:
        return "package-index/network"
    if "permission denied" in text or "not permitted" in text:
        return "permission"
    if "resolutionimpossible" in text or "conflict" in text:
        return "version-conflict"
    if "no matching distribution" in text or "from versions: none" in text:
        return "no-matching-distribution"
    return "unknown"


def _requirements() -> dict[str, Any]:
    path = ROOT / "requirements.txt"
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    relevant = [line.strip() for line in lines if "pandas" in line.lower()]
    return {
        "requirements_exists": path.exists(),
        "pandas_declared": any(line and not line.startswith("#") and line.split("#", 1)[0].strip().lower().startswith("pandas") for line in relevant),
        "requirements_lines_relevant": relevant,
    }


def _pip_config() -> dict[str, Any]:
    proc = _run([sys.executable, "-m", "pip", "config", "list"])
    text = f"{proc.stdout}\n{proc.stderr}"
    env_index = os.environ.get("PIP_INDEX_URL") or os.environ.get("UV_INDEX_URL")
    no_index = os.environ.get("PIP_NO_INDEX")
    return {
        "python_version": sys.version.replace("\n", " "),
        "pip_version": _summarize(_run([sys.executable, "-m", "pip", "--version"]).stdout + _run([sys.executable, "-m", "pip", "--version"]).stderr, 300),
        "pip_config_summary": _summarize(text, 1000),
        "pip_index_url_detected": env_index or ("index-url" in text.lower()),
        "pip_no_index_detected": bool(no_index) or "no-index" in text.lower(),
    }


def _archive_check() -> dict[str, Any]:
    exists = ARCHIVE.exists()
    is_zip = zipfile.is_zipfile(ARCHIVE) if exists else False
    names: list[str] = []
    if is_zip:
        with zipfile.ZipFile(ARCHIVE) as zf:
            names = zf.namelist()
    missing = [r for r in REQUIRED_RUNNER_FILES if not any(n.endswith(r) for n in names)]
    return {
        "archive_path": str(ARCHIVE.relative_to(ROOT)),
        "archive_exists": exists,
        "archive_size_bytes": ARCHIVE.stat().st_size if exists else 0,
        "zipfile_is_zipfile": is_zip,
        "zip_member_count": len(names),
        "required_runner_files": REQUIRED_RUNNER_FILES,
        "required_runner_files_present": not missing,
        "missing_required_runner_files": missing,
        "archive_integrity_passed": exists and is_zip and not missing,
    }


def _extract_check() -> tuple[dict[str, Any], str | None]:
    with tempfile.TemporaryDirectory(prefix="task22a_extract_") as tmp:
        root = Path(tmp)
        attempted = ARCHIVE.exists() and zipfile.is_zipfile(ARCHIVE)
        succeeded = False; err = None; import_path = None
        try:
            if attempted:
                with zipfile.ZipFile(ARCHIVE) as zf:
                    zf.extractall(root)
                succeeded = True
        except BaseException as exc:
            err = f"{type(exc).__name__}: {exc}"
        extracted_root = root / "DEPT2_FullSpecIntegratedClosedLoopRunner_RC1_Freeze"
        package_root = extracted_root / "dept2_fullspec_runner_rc1"
        if package_root.exists():
            import_path = str(extracted_root)
        return ({
            "extraction_attempted": attempted,
            "extraction_succeeded": succeeded,
            "extraction_error": err,
            "extracted_root_exists": extracted_root.exists(),
            "package_root_exists": package_root.exists(),
            "import_path_added": import_path is not None,
            "extraction_check_passed": succeeded and extracted_root.exists() and package_root.exists(),
        }, import_path)


def _pandas_check() -> dict[str, Any]:
    proc = _run([sys.executable, "-c", "import pandas; print(pandas.__version__)"])
    return {
        "pandas_importable": proc.returncode == 0,
        "pandas_version": proc.stdout.strip() if proc.returncode == 0 else None,
        "pandas_import_error": _summarize(proc.stderr or proc.stdout) if proc.returncode != 0 else None,
    }


def _smoke_run() -> dict[str, Any]:
    base = {
        "existing_runner_smoke_attempted": False,
        "existing_runner_found": False,
        "existing_runner_executed": False,
        "runner_smoke_exit_status": None,
        "runner_smoke_error": None,
        "smoke_output_type": None,
        "smoke_output_keys": [],
        "smoke_output_summary": None,
        "runner_traceback": None,
    }
    if not ARCHIVE.exists() or not zipfile.is_zipfile(ARCHIVE):
        base["runner_smoke_error"] = "archive unavailable"
        return base
    with tempfile.TemporaryDirectory(prefix="task22a_smoke_") as tmp:
        try:
            with zipfile.ZipFile(ARCHIVE) as zf:
                zf.extractall(tmp)
            runner_root = Path(tmp) / "DEPT2_FullSpecIntegratedClosedLoopRunner_RC1_Freeze"
            base["existing_runner_found"] = (runner_root / "dept2_fullspec_runner_rc1/runner/fullspec_integrated_closed_loop_runner.py").exists()
            base["existing_runner_smoke_attempted"] = True
            sys.path.insert(0, str(runner_root))
            for name in list(sys.modules):
                if name == "dept2_fullspec_runner_rc1" or name.startswith("dept2_fullspec_runner_rc1."):
                    del sys.modules[name]
            contracts = importlib.import_module("dept2_fullspec_runner_rc1.contracts")
            runner_mod = importlib.import_module("dept2_fullspec_runner_rc1.runner")
            cfg = contracts.FullSpecRunnerConfig(steps=1, seed=2200, scenario="normal", exploration_enabled=True)
            outputs = runner_mod.FullSpecIntegratedClosedLoopRunner(cfg).run()
            base.update({
                "existing_runner_executed": True,
                "runner_smoke_exit_status": 0,
                "smoke_output_type": type(outputs).__name__,
                "smoke_output_keys": sorted(outputs.keys()) if isinstance(outputs, dict) else [],
                "smoke_output_summary": {k: {"type": type(v).__name__, "rows": int(len(v)) if hasattr(v, "__len__") else None} for k, v in outputs.items()} if isinstance(outputs, dict) else str(outputs)[:500],
            })
        except BaseException as exc:
            base.update({"runner_smoke_exit_status": 1, "runner_smoke_error": f"{type(exc).__name__}: {exc}", "runner_traceback": traceback.format_exc(limit=10)})
        finally:
            try:
                sys.path.remove(str(Path(tmp) / "DEPT2_FullSpecIntegratedClosedLoopRunner_RC1_Freeze"))
            except ValueError:
                pass
        return base


def _blocker(summary: dict[str, Any]) -> str | None:
    if not summary["archive_exists"]: return "archive_missing"
    if not summary["zipfile_is_zipfile"]: return "archive_bad_zip"
    if not summary["required_runner_files_present"]: return "required_files_missing"
    if not summary["extraction_succeeded"]: return "extraction_failed"
    if not summary["requirements_exists"]: return "dependency_manifest_missing"
    if summary["pip_install_exit_code"] != 0:
        return "codex_network_blocked" if summary["pip_install_failure_class"] == "package-index/network" else "dependency_install_failed"
    if not summary["pandas_importable"]: return "dependency_import_failed"
    if summary["runner_smoke_exit_status"] == 1: return "runner_runtime_failed"
    if not summary["existing_runner_executed"]: return "runner_import_failed"
    return None


def build() -> tuple[dict[str, Any], dict[str, Any]]:
    summary: dict[str, Any] = {"task": "Task22A Existing Runner Execution Environment Recovery RC1"}
    summary.update(_archive_check())
    extract, _ = _extract_check(); summary.update(extract)
    summary.update(_requirements()); summary.update(_pip_config())
    cmd = [sys.executable, "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")]
    proc = _run(cmd)
    summary.update({
        "pip_install_attempted": True,
        "pip_install_command": "python -m pip install -r requirements.txt",
        "pip_install_exit_code": proc.returncode,
        "pip_install_stdout_or_summary": _summarize(proc.stdout),
        "pip_install_stderr_or_summary": _summarize(proc.stderr),
        "pip_install_failure_class": _classify_pip_failure(proc.returncode, proc.stdout, proc.stderr),
    })
    summary.update(_pandas_check())
    if summary["pandas_importable"]:
        summary.update(_smoke_run())
    else:
        summary.update({
            "existing_runner_smoke_attempted": False, "existing_runner_found": summary["required_runner_files_present"], "existing_runner_executed": False,
            "runner_smoke_exit_status": None, "runner_smoke_error": "pandas not importable; smoke run skipped", "smoke_output_type": None,
            "smoke_output_keys": [], "smoke_output_summary": None, "runner_traceback": None,
        })
    summary.update({
        "synthetic_metrics_used": False,
        "parallel_runner_created": False,
        "frozen_runner_modified": False,
        "bounded_update_hook_connected": False,
        "boundary_prohibited_write_action_added": False,
    })
    passed = all([summary["archive_exists"], summary["zipfile_is_zipfile"], summary["required_runner_files_present"], summary["extraction_succeeded"], summary["pandas_declared"], summary["pip_install_exit_code"] == 0, summary["pandas_importable"], summary["existing_runner_executed"], not summary["synthetic_metrics_used"], not summary["parallel_runner_created"], not summary["frozen_runner_modified"], not summary["bounded_update_hook_connected"], not summary["boundary_prohibited_write_action_added"]])
    summary["passed"] = passed
    summary["blocker_stage"] = None if passed else _blocker(summary)
    summary["codex_environment_pip_install_supported"] = summary["pip_install_exit_code"] == 0
    summary["codex_environment_blocker"] = None if summary["pip_install_exit_code"] == 0 else summary["pip_install_failure_class"]
    summary["external_validation_environment_required"] = not passed
    summary["recommended_next_step"] = "Task22B may start only after existing_runner_executed == true." if passed else "Do not start Task22B; rerun Task22A in an environment where requirements install and the frozen runner smoke run succeed."
    checks = {k: (k in summary) for k in ["archive_path", "extraction_attempted", "pip_install_attempted", "pandas_importable", "existing_runner_executed"]}
    checks.update({
        "passed_requires_existing_runner_executed": (not passed) or summary["existing_runner_executed"],
        "passed_requires_pandas_importable": (not passed) or summary["pandas_importable"],
        "passed_requires_no_synthetic_metrics": (not passed) or not summary["synthetic_metrics_used"],
        "passed_requires_no_parallel_runner": (not passed) or not summary["parallel_runner_created"],
        "passed_requires_no_update_hook": (not passed) or not summary["bounded_update_hook_connected"],
        "pip_failure_forces_failed": summary["passed"] is False if summary["pip_install_exit_code"] != 0 else True,
        "runner_not_executed_forces_failed": summary["passed"] is False if not summary["existing_runner_executed"] else True,
        "fixed_synthetic_mock_success_forbidden": not summary["synthetic_metrics_used"],
    })
    validation = {"task": summary["task"], "checks": checks, "passed": passed}
    return summary, validation


def _md(summary: dict[str, Any], validation: dict[str, Any]) -> tuple[str, str]:
    lines = [f"# {summary['task']}", "", f"passed: `{str(summary['passed']).lower()}`", f"blocker_stage: `{summary.get('blocker_stage')}`", "", "## Summary Fields"]
    for key in ["archive_exists", "zipfile_is_zipfile", "required_runner_files_present", "extraction_succeeded", "pandas_declared", "pip_install_exit_code", "pip_install_failure_class", "pandas_importable", "pandas_version", "existing_runner_executed", "runner_smoke_error", "codex_environment_blocker", "recommended_next_step"]:
        lines.append(f"- {key}: `{summary.get(key)}`")
    vlines = [f"# {summary['task']} Validation", "", f"passed: `{str(validation['passed']).lower()}`", "", "## Checks"] + [f"- {k}: `{str(v).lower()}`" for k, v in validation["checks"].items()]
    return "\n".join(lines) + "\n", "\n".join(vlines) + "\n"


def main() -> int:
    summary, validation = build()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "environment_recovery_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    (OUT_DIR / "environment_recovery_validation.json").write_text(json.dumps(validation, indent=2, sort_keys=True), encoding="utf-8")
    smd, vmd = _md(summary, validation)
    (OUT_DIR / "environment_recovery_summary.md").write_text(smd, encoding="utf-8")
    (OUT_DIR / "environment_recovery_validation.md").write_text(vmd, encoding="utf-8")
    print(json.dumps({"passed": summary["passed"], "blocker_stage": summary["blocker_stage"], "existing_runner_executed": summary["existing_runner_executed"], "pip_install_exit_code": summary["pip_install_exit_code"], "output_dir": str(OUT_DIR)}, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
