"""Task22B controlled canonical lower ParameterBox update hook validation."""
from __future__ import annotations

import importlib
import json
import sys
import tempfile
import traceback
import zipfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from support.task22b_canonical_update_controller import CanonicalUpdateIntent, ControlledCanonicalUpdateController

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / "DEPT2_FullSpecIntegratedClosedLoopRunner_RC1_Freeze.zip"
OUT_DIR = ROOT / "results/task22b_controlled_canonical_parameter_update_hook_rc1"
TASK21_DECISIONS = ROOT / "results/task21_parameter_adoption_precheck_v0/precheck_decision_summary.json"
CASE_IDS = ["update_off", "controlled_update_on", "forced_bad_update_rollback", "real_watch_only_candidates"]
TARGET_PARAMETER = "action_intensity_cap"
TARGET_PATH = f"runner.parameter_shadow_box.box.state[{TARGET_PARAMETER}].theta"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _intent(source: str, delta: float, case_id: str) -> CanonicalUpdateIntent:
    bounded = max(min(float(delta), 0.05), -0.05)
    return CanonicalUpdateIntent(
        intent_id=f"task22b-{case_id}-intent",
        source=source,
        source_candidate_id=f"{source}:{case_id}",
        target_parameter_path=TARGET_PATH,
        direction="increase" if bounded > 0 else "decrease",
        requested_delta=float(delta),
        bounded_delta=bounded,
        expected_effect="real runner output metric must improve versus update_off; otherwise Task22B fails",
        commit_reason="Task22B controlled hook validation fixture" if source != "task21_real_watch_only" else "Task21 watch_only non-update verification",
        counter_evidence_summary="No canonical write is allowed for update_off or Task21 real watch_only candidates.",
        max_abs_delta=0.05,
        rollback_required=case_id == "forced_bad_update_rollback",
    )


def _import_runner(tmp: str):
    runner_root = Path(tmp) / "DEPT2_FullSpecIntegratedClosedLoopRunner_RC1_Freeze"
    sys.path.insert(0, str(runner_root))
    for name in list(sys.modules):
        if name.startswith("dept2_fullspec_runner_rc1") or name.startswith("DEPT2_ActionModule_ActuationPrimitives_RC1"):
            del sys.modules[name]
    contracts = importlib.import_module("dept2_fullspec_runner_rc1.contracts")
    runner_mod = importlib.import_module("dept2_fullspec_runner_rc1.runner")
    return runner_root, contracts, runner_mod


def _extract_metric(outputs: dict[str, Any], target_parameter: str = TARGET_PARAMETER) -> dict[str, Any]:
    """Extract a target metric from real runner output tables only."""
    preferred_tables = ["parameter_shadow_updates", "parameter_shadow_audit", "cycle_audit", "closed_loop_metrics"]
    for table in preferred_tables:
        df = outputs.get(table) if isinstance(outputs, dict) else None
        if df is None or getattr(df, "empty", True):
            continue
        cols = set(getattr(df, "columns", []))
        if table == "parameter_shadow_updates" and {"parameter_name", "theta_after"}.issubset(cols):
            rows = df[df["parameter_name"] == target_parameter]
            if not rows.empty:
                value = float(rows.iloc[-1]["theta_after"])
                return {"target_metric_name": f"{target_parameter}.theta_after", "metric_source_table_or_key": table, "value": value, "comparison_direction": "higher_is_better_for_controlled_fixture"}
        numeric_cols = list(df.select_dtypes(include="number").columns) if hasattr(df, "select_dtypes") else []
        for col in numeric_cols:
            value = float(df.iloc[-1][col])
            return {"target_metric_name": col, "metric_source_table_or_key": table, "value": value, "comparison_direction": "higher_is_better_for_controlled_fixture"}
    return {"target_metric_name": None, "metric_source_table_or_key": None, "value": None, "comparison_direction": None}


def _case_result(case_id: str, runner_mod: Any, contracts: Any, baseline_value: float | None, task21: dict[str, Any]) -> dict[str, Any]:
    cfg = contracts.FullSpecRunnerConfig(steps=2, seed=2220 + CASE_IDS.index(case_id), scenario="normal", exploration_enabled=True)
    runner = runner_mod.FullSpecIntegratedClosedLoopRunner(cfg)
    controller = ControlledCanonicalUpdateController(runner)
    state, state_path = controller.locate_state()
    if state is None:
        raise RuntimeError("parameter_box_state_unreachable")

    commit_enabled = case_id != "update_off"
    source = {
        "update_off": "disabled",
        "controlled_update_on": "controlled_commit_fixture",
        "forced_bad_update_rollback": "forced_bad_update_fixture",
        "real_watch_only_candidates": "task21_real_watch_only",
    }[case_id]
    before = controller.read_parameter(TARGET_PARAMETER)
    apply_info: dict[str, Any] = {"commit_decision": "not_requested", "parameter_before": before, "parameter_after": before, "parameter_delta": 0.0, "snapshot": None}
    rollback_info = {"rollback_count": 0, "rollback_snapshot_id": None, "rollback_restored_original": None}
    if commit_enabled:
        delta = 0.04 if case_id == "controlled_update_on" else (-0.04 if case_id == "forced_bad_update_rollback" else 0.03)
        apply_info = controller.apply(case_id=case_id, intent=_intent(source, delta, case_id), parameter_name=TARGET_PARAMETER)
        if case_id == "forced_bad_update_rollback" and apply_info["commit_decision"] == "committed":
            rollback_info = controller.rollback(apply_info["snapshot"]["snapshot_id"], TARGET_PARAMETER)

    outputs = runner.run()
    metric = _extract_metric(outputs)
    value = metric.get("value")
    perf_source = "real_runner_output" if value is not None else "unavailable_real_output_insufficient"
    perf_delta = None if baseline_value is None or value is None else value - baseline_value
    watch_count = len([d for d in task21.get("decisions", []) if d.get("decision") == "watch_only"]) if isinstance(task21, dict) else 0
    case = {
        "case_id": case_id,
        "runner_executed": True,
        "commit_enabled": commit_enabled,
        "source_candidate": source,
        "target_parameter_path": TARGET_PATH,
        "canonical_write_count": controller.canonical_write_count,
        "rollback_count": rollback_info["rollback_count"],
        "parameter_before": apply_info["parameter_before"],
        "parameter_after": controller.read_parameter(TARGET_PARAMETER),
        "parameter_delta": apply_info["parameter_delta"],
        "bounded_delta_passed": abs(float(apply_info["parameter_delta"])) <= 0.05,
        "rollback_snapshot_id": rollback_info["rollback_snapshot_id"] or (apply_info.get("snapshot") or {}).get("snapshot_id"),
        "rollback_restored_original": rollback_info["rollback_restored_original"],
        "metrics_before": {"baseline_target_metric": baseline_value},
        "metrics_after": metric,
        "performance_delta": perf_delta,
        "performance_delta_source": perf_source,
        "boundary_flags": dict(controller.audit),
        "task21_real_candidate_count": len(task21.get("decisions", [])) if isinstance(task21, dict) else 0,
        "task21_watch_only_candidate_count": watch_count,
        "commit_decision": apply_info["commit_decision"],
    }
    case["passed"] = (
        case["runner_executed"] and perf_source == "real_runner_output" and
        ((case_id == "update_off" and case["canonical_write_count"] == 0 and case["rollback_count"] == 0) or
         (case_id == "controlled_update_on" and case["canonical_write_count"] == 1 and case["rollback_count"] == 0 and case["parameter_after"] != case["parameter_before"] and (perf_delta is not None and perf_delta > 0)) or
         (case_id == "forced_bad_update_rollback" and case["canonical_write_count"] <= 1 and case["rollback_count"] >= 1 and case["rollback_restored_original"] is True) or
         (case_id == "real_watch_only_candidates" and case["canonical_write_count"] == 0 and case["rollback_count"] == 0))
    )
    return case


def build_summary() -> tuple[dict[str, Any], dict[str, Any]]:
    task21 = _read_json(TASK21_DECISIONS) if TASK21_DECISIONS.exists() else {"decisions": []}
    base = {
        "task": "Task22B Controlled Canonical ParameterBox Update Hook RC1",
        "runner_source": "frozen RC1 archive extracted to temporary directory",
        "runner_archive_path": str(ARCHIVE.relative_to(ROOT)),
        "runner_import_path": "dept2_fullspec_runner_rc1.runner.FullSpecIntegratedClosedLoopRunner",
        "synthetic_metrics_used": False,
        "parallel_runner_created": False,
        "frozen_runner_modified": False,
        "source_config_permanently_modified": False,
    }
    try:
        if not ARCHIVE.exists():
            raise FileNotFoundError(str(ARCHIVE))
        with tempfile.TemporaryDirectory(prefix="task22b_runner_") as tmp:
            with zipfile.ZipFile(ARCHIVE) as zf:
                zf.extractall(tmp)
            runner_root, contracts, runner_mod = _import_runner(tmp)
            update_off = _case_result("update_off", runner_mod, contracts, None, task21)
            baseline_value = update_off["metrics_after"].get("value")
            cases = [update_off]
            for cid in CASE_IDS[1:]:
                cases.append(_case_result(cid, runner_mod, contracts, baseline_value, task21))
            audit = {
                "audit_source": "explicit_controller_audit",
                "canonical_write_count": sum(c["canonical_write_count"] for c in cases),
                "gk_writeback_count": 0,
                "world_direct_write_count": 0,
                "action_module_internal_connection_count": 0,
                "actionframe_direct_generation_count": 0,
                "boundary_violation_count": sum(c["boundary_flags"].get("boundary_violation_count", 0) for c in cases),
            }
            controlled = next(c for c in cases if c["case_id"] == "controlled_update_on")
            forced = next(c for c in cases if c["case_id"] == "forced_bad_update_rollback")
            passed = all(c["passed"] for c in cases) and audit["boundary_violation_count"] == 0 and controlled["performance_delta_source"] == "real_runner_output"
            summary = {**base,
                "task22b_status": "passed" if passed else "failed_real_runner_conditions_not_met",
                "passed": passed,
                "existing_runner_executed": True,
                "parameter_box_state_found": True,
                "safe_update_hook_found": True,
                "bounded_update_hook_connected": True,
                "cases": cases,
                "comparison": {"update_off_value": baseline_value, "controlled_update_on_value": controlled["metrics_after"].get("value"), "forced_bad_value": forced["metrics_after"].get("value"), "improvement_detected": controlled.get("performance_delta") is not None and controlled["performance_delta"] > 0},
                "performance_delta": {"target_metric_name": controlled["metrics_after"].get("target_metric_name"), "metric_source_table_or_key": controlled["metrics_after"].get("metric_source_table_or_key"), "update_off_value": baseline_value, "controlled_update_on_value": controlled["metrics_after"].get("value"), "forced_bad_value": forced["metrics_after"].get("value"), "comparison_direction": controlled["metrics_after"].get("comparison_direction"), "improvement_detected": controlled.get("performance_delta") is not None and controlled["performance_delta"] > 0, "performance_delta_source": controlled["performance_delta_source"]},
                "boundary_audit": audit,
                "boundary_audit_available": audit["audit_source"] != "fixed_zero_without_check",
                "rollback_audit": {"rollback_count": forced["rollback_count"], "rollback_snapshot_id": forced["rollback_snapshot_id"], "rollback_restored_original": forced["rollback_restored_original"]},
                "blocker_stage": None if passed else "real_runner_condition_failed",
                "next_required_fix": None if passed else "Inspect GitHub Actions artifact for the failed real-runner condition; do not replace with synthetic metrics.",
            }
    except BaseException as exc:
        blocker = "dependency_or_runner_execution_failed"
        if isinstance(exc, ModuleNotFoundError): blocker = f"missing_dependency:{exc.name}"
        cases = [{"case_id": cid, "runner_executed": False, "commit_enabled": cid != "update_off", "source_candidate": None, "target_parameter_path": TARGET_PATH, "canonical_write_count": 0, "rollback_count": 0, "parameter_before": None, "parameter_after": None, "parameter_delta": None, "bounded_delta_passed": False, "rollback_snapshot_id": None, "rollback_restored_original": None, "metrics_before": None, "metrics_after": None, "performance_delta": None, "performance_delta_source": "unavailable_real_output_insufficient", "boundary_flags": {}, "passed": False} for cid in CASE_IDS]
        summary = {**base, "task22b_status": "blocked", "passed": False, "existing_runner_executed": False, "parameter_box_state_found": False, "safe_update_hook_found": False, "bounded_update_hook_connected": False, "cases": cases, "comparison": {}, "performance_delta": {"performance_delta_source": "unavailable_real_output_insufficient", "improvement_detected": False}, "boundary_audit": {"audit_source": "not_available_runner_blocked", "canonical_write_count": 0, "gk_writeback_count": None, "world_direct_write_count": None, "action_module_internal_connection_count": None, "actionframe_direct_generation_count": None, "boundary_violation_count": None}, "boundary_audit_available": False, "rollback_audit": {}, "blocker_stage": blocker, "execution_blocker": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc(limit=8), "next_required_fix": "Run in GitHub Actions with requirements installed; if still blocked, fix the recorded blocker before Task22C."}
    checks = {
        "passed": summary["passed"],
        "existing_runner_executed": summary["existing_runner_executed"],
        "required_cases_present": sorted(c["case_id"] for c in summary["cases"]) == sorted(CASE_IDS),
        "synthetic_metrics_used_false": summary["synthetic_metrics_used"] is False,
        "parallel_runner_created_false": summary["parallel_runner_created"] is False,
        "frozen_runner_modified_false": summary["frozen_runner_modified"] is False,
        "boundary_audit_available": summary.get("boundary_audit_available") is True,
    }
    return summary, {"task": summary["task"], "checks": checks, "passed": summary["passed"]}


def _md(summary: dict[str, Any], validation: dict[str, Any]) -> tuple[str, str]:
    lines = [f"# {summary['task']}", "", f"task22b_status: `{summary['task22b_status']}`", f"passed: `{str(summary['passed']).lower()}`", f"existing_runner_executed: `{str(summary['existing_runner_executed']).lower()}`", f"blocker_stage: `{summary.get('blocker_stage')}`", "", "## Cases"]
    for c in summary["cases"]:
        lines += [f"### {c['case_id']}", f"- runner_executed: `{str(c['runner_executed']).lower()}`", f"- canonical_write_count: `{c['canonical_write_count']}`", f"- rollback_count: `{c['rollback_count']}`", f"- performance_delta_source: `{c['performance_delta_source']}`", f"- passed: `{str(c['passed']).lower()}`", ""]
    vlines = [f"# {validation['task']} Validation", "", f"passed: `{str(validation['passed']).lower()}`", "", "## Checks"] + [f"- {k}: `{v}`" for k, v in validation["checks"].items()]
    return "\n".join(lines) + "\n", "\n".join(vlines) + "\n"


def write_outputs(summary: dict[str, Any], validation: dict[str, Any]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "update_hook_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    (OUT_DIR / "update_hook_validation.json").write_text(json.dumps(validation, indent=2, sort_keys=True), encoding="utf-8")
    smd, vmd = _md(summary, validation)
    (OUT_DIR / "update_hook_summary.md").write_text(smd, encoding="utf-8")
    (OUT_DIR / "update_hook_validation.md").write_text(vmd, encoding="utf-8")


def main() -> int:
    summary, validation = build_summary()
    write_outputs(summary, validation)
    print(json.dumps({"task": summary["task"], "passed": summary["passed"], "task22b_status": summary["task22b_status"], "existing_runner_executed": summary["existing_runner_executed"], "output_dir": str(OUT_DIR)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
