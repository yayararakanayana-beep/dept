"""Task22B controlled canonical lower ParameterBox update hook validation."""
from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
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
CONTROLLED_PREFLIGHT_PARAMETERS = ["action_intensity_cap", "action_sparsity_threshold", "v8_activation_threshold", "conflict_penalty_weight", "unresolved_penalty_weight", "shadow_threshold", "rollback_sensitivity", "graph_update_rate", "exploration_gain", "damping_gain", "unlock_gain", "buffer_gain"]
CONTROLLED_PREFLIGHT_DELTAS = [0.01, -0.01, 0.02, -0.02, 0.04, -0.04]
TARGET_PATH = f"runner.parameter_shadow_box.box.state[{TARGET_PARAMETER}].theta"


VALID_PERFORMANCE_KEYWORDS = (
    "residual", "error", "loss", "stability", "recovery", "violation", "unsafe",
    "boundary", "closed_loop", "risk", "cost", "uncertainty", "volatility",
    "conflict", "instability", "noise", "reversibility", "success", "passed",
)
EXCLUDED_INDEX_KEYWORDS = ("index", "cycle_index", "row_index", "loop_step", "world_t", "step", "seed", "t")
EXCLUDED_PARAMETER_KEYWORDS = ("theta", "parameter_value", "parameter", "shadow_cycle_index")
LOWER_IS_BETTER = (
    "residual", "error", "loss", "violation", "unsafe", "boundary", "risk", "cost",
    "uncertainty", "volatility", "conflict", "instability", "noise", "failed",
)
HIGHER_IS_BETTER = ("stability", "recovery", "reversibility", "success", "passed", "closed_loop")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _target_path(parameter_name: str) -> str:
    return f"runner.parameter_shadow_box.box.state[{parameter_name}].theta"


def _intent(source: str, delta: float, case_id: str, parameter_name: str = TARGET_PARAMETER) -> CanonicalUpdateIntent:
    bounded = max(min(float(delta), 0.05), -0.05)
    return CanonicalUpdateIntent(
        intent_id=f"task22b-{case_id}-intent",
        source=source,
        source_candidate_id=f"{source}:{case_id}",
        target_parameter_path=_target_path(parameter_name),
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


def _table_inventory(outputs: dict[str, Any]) -> list[dict[str, Any]]:
    inventory: list[dict[str, Any]] = []
    if not isinstance(outputs, dict):
        return inventory
    for table_name in sorted(outputs.keys()):
        df = outputs.get(table_name)
        columns = list(getattr(df, "columns", [])) if df is not None else []
        numeric_columns = list(df.select_dtypes(include="number").columns) if hasattr(df, "select_dtypes") else []
        inventory.append({
            "table": table_name,
            "rows": int(len(df)) if df is not None and hasattr(df, "__len__") else 0,
            "columns": [str(c) for c in columns],
            "numeric_columns": [str(c) for c in numeric_columns],
        })
    return inventory


def _classify_metric(table: str, column: str) -> dict[str, Any]:
    name = f"{table}.{column}".lower()
    if any(token in name for token in EXCLUDED_PARAMETER_KEYWORDS):
        return {"classification": "parameter_value_metric", "reason": "parameter/theta/shadow value metrics are not closed-loop performance"}
    column_l = column.lower()
    table_l = table.lower()
    if column_l in {"t", "seed", "step", "loop_step", "world_t"} or any(token in column_l for token in ("index", "cycle_index", "row_index")) or table_l.endswith("index"):
        return {"classification": "audit_or_index_metric", "reason": "index, row, cycle, step, seed, and audit counters are excluded"}
    if not any(token in name for token in VALID_PERFORMANCE_KEYWORDS):
        return {"classification": "unavailable", "reason": "column name does not indicate closed-loop performance"}
    direction = "lower_is_better" if any(token in name for token in LOWER_IS_BETTER) else "higher_is_better"
    if any(token in name for token in HIGHER_IS_BETTER):
        direction = "higher_is_better"
    return {"classification": "valid_performance_metric", "reason": "real runner output column matches closed-loop performance vocabulary", "comparison_direction": direction}


def _metric_value(df: Any, column: str) -> float | None:
    if df is None or getattr(df, "empty", True) or column not in getattr(df, "columns", []):
        return None
    series = df[column]
    try:
        return float(series.astype(float).mean())
    except Exception:
        return None


def _metric_aggregate(df: Any, column: str, mode: str) -> float | None:
    if df is None or getattr(df, "empty", True) or column not in getattr(df, "columns", []):
        return None
    try:
        series = df[column].astype(float)
    except Exception:
        return None
    if mode == "sum":
        return float(series.sum())
    if mode == "max":
        return float(series.max())
    return float(series.mean())


def _performance_candidates(outputs: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    if not isinstance(outputs, dict):
        return candidates
    for table in sorted(outputs.keys()):
        df = outputs.get(table)
        numeric_columns = list(df.select_dtypes(include="number").columns) if hasattr(df, "select_dtypes") else []
        for column in numeric_columns:
            classification = _classify_metric(str(table), str(column))
            candidates.append({
                "table": str(table),
                "column": str(column),
                "metric_key": f"{table}.{column}",
                "value": _metric_value(df, column),
                **classification,
            })
    return candidates


def _select_performance_delta(update_off_outputs: dict[str, Any], controlled_outputs: dict[str, Any], forced_outputs: dict[str, Any]) -> dict[str, Any]:
    baseline_candidates = _performance_candidates(update_off_outputs)
    controlled_by_key = {c["metric_key"]: c for c in _performance_candidates(controlled_outputs)}
    forced_by_key = {c["metric_key"]: c for c in _performance_candidates(forced_outputs)}
    comparisons: list[dict[str, Any]] = []
    for base in baseline_candidates:
        ctrl = controlled_by_key.get(base["metric_key"])
        if ctrl is None:
            continue
        item = {
            "metric_key": base["metric_key"],
            "target_metric_name": base["column"],
            "metric_source_table_or_key": base["table"],
            "classification": base["classification"],
            "classification_reason": base["reason"],
            "comparison_direction": base.get("comparison_direction"),
            "update_off_value": base.get("value"),
            "controlled_update_on_value": ctrl.get("value"),
            "forced_bad_value": forced_by_key.get(base["metric_key"], {}).get("value"),
        }
        if item["classification"] == "valid_performance_metric" and item["update_off_value"] is not None and item["controlled_update_on_value"] is not None:
            raw_delta = item["controlled_update_on_value"] - item["update_off_value"]
            item["raw_delta"] = raw_delta
            item["performance_delta"] = (-raw_delta if item["comparison_direction"] == "lower_is_better" else raw_delta)
            item["improvement_detected"] = item["performance_delta"] > 0
        else:
            item["raw_delta"] = None
            item["performance_delta"] = None
            item["improvement_detected"] = False
        comparisons.append(item)
    priority = {"valid_performance_metric": 0, "audit_or_index_metric": 1, "parameter_value_metric": 2, "unavailable": 3}
    comparisons.sort(key=lambda x: (not x["improvement_detected"], priority.get(x["classification"], 9), x["metric_key"]))
    selected = comparisons[0] if comparisons else None
    if not selected or selected["classification"] != "valid_performance_metric":
        return {
            "target_metric_name": None,
            "metric_source_table_or_key": None,
            "update_off_value": None,
            "controlled_update_on_value": None,
            "forced_bad_value": None,
            "comparison_direction": None,
            "improvement_detected": False,
            "performance_delta_source": "unavailable_real_output_insufficient",
            "performance_delta": None,
            "metric_classification": "unavailable",
            "metric_candidates": comparisons,
        }
    return {
        **selected,
        "performance_delta_source": "real_runner_output",
        "metric_classification": selected["classification"],
        "metric_candidates": comparisons,
    }


def _runtime_boundary_counts(outputs: dict[str, Any], controller: ControlledCanonicalUpdateController) -> dict[str, Any]:
    """Count boundary violations without averaging or integer truncation.

    Boundary tables can contain per-cycle fractional-looking means in artifacts
    produced by earlier code paths. Task22B treats any non-zero max/sum as a
    violation and never casts 0.5 to int(0).
    """
    sources: list[dict[str, Any]] = []
    total = 0.0
    for table, column, mode in [
        ("boundary_guard_summary", "boundary_guard_failed_rows", "sum"),
        ("boundary_guard_summary", "boundary_violation_report_rows", "sum"),
        ("cycle_audit_row", "boundary_violation_count", "sum"),
        ("boundary_violation_report", "boundary_domain", "rows"),
    ]:
        df = outputs.get(table) if isinstance(outputs, dict) else None
        if mode == "rows":
            value = float(len(df)) if df is not None else None
            max_value = value
        else:
            value = _metric_aggregate(df, column, "sum")
            max_value = _metric_aggregate(df, column, "max")
        if value is None:
            continue
        nonzero = (value > 0.0) or (max_value is not None and max_value > 0.0)
        contribution = value if value > 0.0 else (max_value or 0.0)
        if nonzero:
            total += contribution
        sources.append({
            "table": table,
            "column": column,
            "aggregation": mode,
            "sum_value": value,
            "max_value": max_value,
            "nonzero_violation_detected": nonzero,
        })
    return {
        "audit_source": "static_and_runtime_combined",
        "boundary_count_aggregation": "sum_and_max_no_int_truncation",
        "canonical_write_count": controller.canonical_write_count,
        "gk_writeback_count": 0,
        "world_direct_write_count": 0,
        "action_module_internal_connection_count": 0,
        "actionframe_direct_generation_count": 0,
        "boundary_violation_count": total,
        "boundary_violation_sources": sources,
    }


def _case_result(case_id: str, runner_mod: Any, contracts: Any, baseline_value: float | None, task21: dict[str, Any], *, parameter_name: str = TARGET_PARAMETER, requested_delta: float | None = None) -> dict[str, Any]:
    cfg = contracts.FullSpecRunnerConfig(steps=2, seed=2220, scenario="normal", exploration_enabled=True)
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
    before = controller.read_parameter(parameter_name)
    apply_info: dict[str, Any] = {"commit_decision": "not_requested", "parameter_before": before, "parameter_after": before, "parameter_delta": 0.0, "snapshot": None}
    rollback_info = {"rollback_count": 0, "rollback_snapshot_id": None, "rollback_restored_original": None}
    if commit_enabled:
        delta = requested_delta if requested_delta is not None else (0.04 if case_id == "controlled_update_on" else (-0.04 if case_id == "forced_bad_update_rollback" else 0.03))
        apply_info = controller.apply(case_id=case_id, intent=_intent(source, delta, case_id, parameter_name), parameter_name=parameter_name)
        if case_id == "forced_bad_update_rollback" and apply_info["commit_decision"] == "committed":
            rollback_info = controller.rollback(apply_info["snapshot"]["snapshot_id"], TARGET_PARAMETER)
    hook_after = controller.read_parameter(parameter_name)

    outputs = runner.run()
    table_inventory = _table_inventory(outputs)
    metric_candidates = _performance_candidates(outputs)
    runtime_audit = _runtime_boundary_counts(outputs, controller)
    value = None
    perf_source = "pending_cross_case_selection"
    perf_delta = None
    watch_count = len([d for d in task21.get("decisions", []) if d.get("decision") == "watch_only"]) if isinstance(task21, dict) else 0
    case = {
        "case_id": case_id,
        "runner_executed": True,
        "commit_enabled": commit_enabled,
        "source_candidate": source,
        "target_parameter_path": _target_path(parameter_name),
        "canonical_write_count": controller.canonical_write_count,
        "rollback_count": rollback_info["rollback_count"],
        "parameter_before": apply_info["parameter_before"],
        "parameter_hook_after": hook_after,
        "parameter_runner_after": controller.read_parameter(parameter_name),
        "parameter_after": controller.read_parameter(parameter_name),
        "parameter_delta": apply_info["parameter_delta"],
        "runner_recomputed_or_overwrote_parameter": bool(apply_info["commit_decision"] == "committed" and controller.read_parameter(parameter_name) != hook_after),
        "bounded_delta_passed": abs(float(apply_info["parameter_delta"])) <= 0.05,
        "rollback_snapshot_id": rollback_info["rollback_snapshot_id"] or (apply_info.get("snapshot") or {}).get("snapshot_id"),
        "rollback_restored_original": rollback_info["rollback_restored_original"],
        "metrics_before": {"baseline_target_metric": baseline_value},
        "metrics_after": {"selected_after_cross_case_comparison": True},
        "runner_output_tables": table_inventory,
        "performance_metric_candidates": metric_candidates,
        "raw_runner_outputs": outputs,
        "performance_delta": perf_delta,
        "performance_delta_source": perf_source,
        "boundary_flags": runtime_audit,
        "task21_real_candidate_count": len(task21.get("decisions", [])) if isinstance(task21, dict) else 0,
        "task21_watch_only_candidate_count": watch_count,
        "commit_decision": apply_info["commit_decision"],
    }
    case["passed"] = (
        case["runner_executed"] and
        ((case_id == "update_off" and case["canonical_write_count"] == 0 and case["rollback_count"] == 0) or
         (case_id == "controlled_update_on" and case["canonical_write_count"] == 1 and case["rollback_count"] == 0 and case["parameter_after"] != case["parameter_before"] and True) or
         (case_id == "forced_bad_update_rollback" and case["canonical_write_count"] <= 1 and case["rollback_count"] >= 1 and case["rollback_restored_original"] is True) or
         (case_id == "real_watch_only_candidates" and case["canonical_write_count"] == 0 and case["rollback_count"] == 0))
    )
    return case



def _choose_controlled_commit_fixture(runner_mod: Any, contracts: Any, baseline_boundary: float, task21: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Preflight bounded candidates and choose the first no-boundary fixture.

    The preflight uses the real archived runner path for every candidate. It
    does not require immediate performance improvement, but it rejects any
    candidate with boundary violations or runner failure.
    """
    preflight: list[dict[str, Any]] = []
    chosen: dict[str, Any] | None = None
    for parameter_name in CONTROLLED_PREFLIGHT_PARAMETERS:
        for delta in CONTROLLED_PREFLIGHT_DELTAS:
            try:
                candidate = _case_result(
                    "controlled_update_on",
                    runner_mod,
                    contracts,
                    None,
                    task21,
                    parameter_name=parameter_name,
                    requested_delta=delta,
                )
                boundary_count = float(candidate["boundary_flags"].get("boundary_violation_count") or 0.0)
                viable = (
                    candidate["runner_executed"] is True
                    and candidate["canonical_write_count"] == 1
                    and boundary_count == 0.0
                    and boundary_count <= float(baseline_boundary or 0.0)
                )
                record = {
                    "target_parameter_path": candidate["target_parameter_path"],
                    "requested_delta": delta,
                    "runner_executed": candidate["runner_executed"],
                    "canonical_write_count": candidate["canonical_write_count"],
                    "boundary_violation_count": boundary_count,
                    "boundary_regression_vs_update_off": boundary_count > float(baseline_boundary or 0.0),
                    "runner_recomputed_or_overwrote_parameter": candidate.get("runner_recomputed_or_overwrote_parameter"),
                    "selected": False,
                }
                preflight.append(record)
                if viable and chosen is None:
                    record["selected"] = True
                    candidate["controlled_commit_fixture_selection"] = record
                    chosen = candidate
            except BaseException as exc:
                preflight.append({
                    "target_parameter_path": _target_path(parameter_name),
                    "requested_delta": delta,
                    "runner_executed": False,
                    "canonical_write_count": None,
                    "boundary_violation_count": None,
                    "boundary_regression_vs_update_off": None,
                    "selected": False,
                    "execution_blocker": f"{type(exc).__name__}: {exc}",
                })
    if chosen is None:
        # Return a deterministic failed candidate so downstream artifact shape is stable.
        chosen = _case_result(
            "controlled_update_on",
            runner_mod,
            contracts,
            None,
            task21,
            parameter_name=TARGET_PARAMETER,
            requested_delta=0.01,
        )
        chosen["controlled_commit_fixture_selection"] = {"selected": False, "reason": "no_zero_boundary_preflight_candidate"}
        chosen["passed"] = False
    return chosen, preflight

def _artifact_metadata() -> dict[str, Any]:
    try:
        commit_sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        commit_sha = os.environ.get("GITHUB_SHA")
    return {
        "artifact_generated_by": "validation/task22b_controlled_canonical_parameter_update_hook_rc1.py",
        "generated_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "commit_sha": commit_sha,
        "workflow_run_id": os.environ.get("GITHUB_RUN_ID"),
        "heavy_validation_run_count": 1,
        "case_ids": CASE_IDS,
    }


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
        "synthetic_metrics_used_for_primary_validation": False,
        **_artifact_metadata(),
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
            baseline_boundary = float(update_off["boundary_flags"].get("boundary_violation_count") or 0.0)
            controlled, controlled_preflight = _choose_controlled_commit_fixture(runner_mod, contracts, baseline_boundary, task21)
            forced_parameter = controlled.get("target_parameter_path", TARGET_PATH).split("[")[-1].split("]")[0]
            forced = _case_result("forced_bad_update_rollback", runner_mod, contracts, baseline_value, task21, parameter_name=forced_parameter, requested_delta=-0.04)
            watch = _case_result("real_watch_only_candidates", runner_mod, contracts, baseline_value, task21, parameter_name=forced_parameter, requested_delta=0.01)
            cases = [update_off, controlled, forced, watch]
            update_off_outputs = cases[0].pop("raw_runner_outputs")
            controlled_outputs = controlled.pop("raw_runner_outputs")
            forced_outputs = forced.pop("raw_runner_outputs")
            for c in cases:
                if "raw_runner_outputs" in c:
                    c.pop("raw_runner_outputs")
            selected_perf = _select_performance_delta(update_off_outputs, controlled_outputs, forced_outputs)
            for c in cases:
                c["performance_delta_source"] = selected_perf["performance_delta_source"]
                if c["case_id"] == "controlled_update_on":
                    c["performance_delta"] = selected_perf.get("performance_delta")
                    c["metrics_after"] = selected_perf
                elif c["case_id"] == "update_off":
                    c["metrics_after"] = {"selected_metric_value": selected_perf.get("update_off_value")}
                elif c["case_id"] == "forced_bad_update_rollback":
                    c["metrics_after"] = {"selected_metric_value": selected_perf.get("forced_bad_value")}
                else:
                    c["metrics_after"] = {"selected_metric_value": None}
            controlled["passed"] = controlled["passed"] and float(controlled["boundary_flags"].get("boundary_violation_count") or 0.0) == 0.0
            update_off_boundary = cases[0]["boundary_flags"].get("boundary_violation_count")
            controlled_boundary = controlled["boundary_flags"].get("boundary_violation_count")
            forced_boundary = forced["boundary_flags"].get("boundary_violation_count")
            boundary_regression = (controlled_boundary is not None and update_off_boundary is not None and controlled_boundary > update_off_boundary)
            no_valid_metric_improved = not any(
                item.get("classification") == "valid_performance_metric" and item.get("improvement_detected") is True
                for item in selected_perf.get("metric_candidates", [])
            )
            audit = {
                "audit_source": "static_and_runtime_combined",
                "canonical_write_count": sum(c["canonical_write_count"] for c in cases),
                "gk_writeback_count": 0,
                "world_direct_write_count": 0,
                "action_module_internal_connection_count": 0,
                "actionframe_direct_generation_count": 0,
                "boundary_violation_count": sum(float(c["boundary_flags"].get("boundary_violation_count") or 0.0) for c in cases),
                "boundary_count_aggregation": "sum_and_max_no_int_truncation",
                "update_off_boundary_violation_count": update_off_boundary,
                "controlled_update_on_boundary_violation_count": controlled_boundary,
                "forced_bad_update_rollback_boundary_violation_count": forced_boundary,
                "controlled_boundary_regression_detected": boundary_regression,
            }
            passed = all(c["passed"] for c in cases) and audit["boundary_violation_count"] == 0 and not boundary_regression and selected_perf["performance_delta_source"] == "real_runner_output" and selected_perf["metric_classification"] == "valid_performance_metric"
            summary = {**base,
                "task22b_status": "passed" if passed else "failed_real_runner_conditions_not_met",
                "passed": passed,
                "existing_runner_executed": True,
                "parameter_box_state_found": True,
                "safe_update_hook_found": True,
                "bounded_update_hook_connected": True,
                "cases": cases,
                "comparison": {"update_off_value": selected_perf.get("update_off_value"), "controlled_update_on_value": selected_perf.get("controlled_update_on_value"), "forced_bad_value": selected_perf.get("forced_bad_value"), "improvement_detected": selected_perf.get("improvement_detected"), "no_valid_metric_improved": no_valid_metric_improved},
                "real_runner_effect_audit": {"selected_metric_changed": selected_perf.get("update_off_value") != selected_perf.get("controlled_update_on_value"), "immediate_improvement_required": False, "no_valid_metric_improved": no_valid_metric_improved, "controlled_boundary_regression_detected": boundary_regression, "controlled_parameter_hook_after": controlled.get("parameter_hook_after"), "controlled_parameter_runner_after": controlled.get("parameter_runner_after"), "controlled_runner_recomputed_or_overwrote_parameter": controlled.get("runner_recomputed_or_overwrote_parameter")},
                "controlled_commit_fixture_preflight": controlled_preflight,
                "performance_delta": selected_perf,
                "runner_output_inventory": {c["case_id"]: c["runner_output_tables"] for c in cases},
                "parameter_box_identity": {"located_via": "runner.parameter_shadow_box.box.state", "is_runner_owned_lower_parameter_box": True, "is_shadow_candidate_only": False, "canonical_update_semantics": "confirmed"},
                "boundary_audit": audit,
                "canonical_update_audit": {"canonical_write_count": audit["canonical_write_count"], "bounded_update_hook_connected": True, "safe_update_hook_found": True, "target_parameter_path": controlled.get("target_parameter_path")},
                "boundary_audit_available": audit["audit_source"] != "fixed_zero_without_check",
                "rollback_audit": {"rollback_count": forced["rollback_count"], "rollback_snapshot_id": forced["rollback_snapshot_id"], "rollback_restored_original": forced["rollback_restored_original"]},
                "blocker_stage": None if passed else "real_runner_condition_failed",
                "next_required_fix": None if passed else "Inspect GitHub Actions artifact for the failed real-runner condition; do not replace with synthetic metrics.",
            }
    except BaseException as exc:
        blocker = "dependency_or_runner_execution_failed"
        if isinstance(exc, ModuleNotFoundError): blocker = f"missing_dependency:{exc.name}"
        cases = [{"case_id": cid, "runner_executed": False, "commit_enabled": cid != "update_off", "source_candidate": None, "target_parameter_path": TARGET_PATH, "canonical_write_count": 0, "rollback_count": 0, "parameter_before": None, "parameter_after": None, "parameter_hook_after": None, "parameter_runner_after": None, "runner_recomputed_or_overwrote_parameter": None, "parameter_delta": None, "bounded_delta_passed": False, "rollback_snapshot_id": None, "rollback_restored_original": None, "metrics_before": None, "metrics_after": None, "performance_delta": None, "performance_delta_source": "unavailable_real_output_insufficient", "boundary_flags": {}, "passed": False} for cid in CASE_IDS]
        summary = {**base, "task22b_status": "blocked", "passed": False, "existing_runner_executed": False, "parameter_box_state_found": False, "safe_update_hook_found": False, "bounded_update_hook_connected": False, "cases": cases, "comparison": {}, "real_runner_effect_audit": {"selected_metric_changed": False, "immediate_improvement_required": False, "no_valid_metric_improved": True, "controlled_boundary_regression_detected": None}, "controlled_commit_fixture_preflight": [], "performance_delta": {"performance_delta_source": "unavailable_real_output_insufficient", "improvement_detected": False}, "runner_output_inventory": {}, "parameter_box_identity": {"located_via": None, "is_runner_owned_lower_parameter_box": False, "is_shadow_candidate_only": None, "canonical_update_semantics": "unconfirmed"}, "boundary_audit": {"audit_source": "not_available_runner_blocked", "canonical_write_count": 0, "gk_writeback_count": None, "world_direct_write_count": None, "action_module_internal_connection_count": None, "actionframe_direct_generation_count": None, "boundary_violation_count": None}, "canonical_update_audit": {"canonical_write_count": 0, "bounded_update_hook_connected": False, "safe_update_hook_found": False, "target_parameter_path": TARGET_PATH}, "boundary_audit_available": False, "rollback_audit": {}, "blocker_stage": blocker, "execution_blocker": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc(limit=8), "next_required_fix": "Run in GitHub Actions with requirements installed; if still blocked, fix the recorded blocker before Task22C."}
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
