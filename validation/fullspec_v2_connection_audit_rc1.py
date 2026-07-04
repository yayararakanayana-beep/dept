#!/usr/bin/env python3
"""FullSpec-v2 connection audit RC1.

Runs the FullSpec integrated closed-loop runner with the v2 pseudo-reality
world engine and checks only connection/reversibility boundaries.  This file
is diagnostic-only: it does not change runner defaults, coefficients,
ParameterBox/ShadowBox defaults, canonical state, production runtime, or action
module logic.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
LOCALPREP_ROOT = REPO_ROOT / "localprep1" / "dept"
ACTION_MODULE_ROOT = LOCALPREP_ROOT / "DEPT2_ActionModule_ActuationPrimitives_RC1"
for path in (LOCALPREP_ROOT, ACTION_MODULE_ROOT, REPO_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from dept2_fullspec_runner_rc1.runner.fullspec_integrated_closed_loop_runner import (  # noqa: E402
    run_fullspec_task16,
)
from scripts.profile_loader import (  # noqa: E402
    build_runner_config,
    collect_metrics,
    dataframe_to_csv,
    write_json,
)

OUTPUT_DIR = REPO_ROOT / "results" / "fullspec_v2_connection_audit_rc1"
LABEL = "fullspec_v2_connection_audit_rc1"
VALIDATION_PROFILE = "smoke"
WORLD_PROFILE = "pseudo_reality_v2_shrinking_equilibrium"
ACTION_PROFILE = "action_default"

REVERSIBLE_OVERRIDES: dict[str, Any] = {
    "canonical_commit_enabled": False,
    "canonical_commit_dry_run": True,
    "canonical_binding_source": "shadow",
    "run_baseline_shadow": True,
    "output_prefix": LABEL,
}


def _frame(out: dict[str, Any], name: str) -> pd.DataFrame:
    df = out.get(name, pd.DataFrame())
    return df if isinstance(df, pd.DataFrame) else pd.DataFrame()


def _rows(out: dict[str, Any], name: str) -> int:
    return int(len(_frame(out, name)))


def _all_bool(df: pd.DataFrame, col: str, default: bool = False) -> bool:
    if df.empty or col not in df.columns:
        return bool(default)
    return bool(df[col].fillna(default).astype(bool).all())


def _any_bool(df: pd.DataFrame, col: str, default: bool = False) -> bool:
    if df.empty or col not in df.columns:
        return bool(default)
    return bool(df[col].fillna(default).astype(bool).any())


def _all_status(df: pd.DataFrame, col: str, status: str = "pass") -> bool:
    if df.empty or col not in df.columns:
        return False
    return bool(df[col].astype(str).eq(status).all())


def _check(name: str, passed: bool, detail: str, critical: bool = True) -> dict[str, Any]:
    return {
        "check_name": name,
        "passed": bool(passed),
        "critical": bool(critical),
        "detail": detail,
    }


def build_connection_checks(cfg, out: dict[str, Any], metrics: dict[str, Any]) -> list[dict[str, Any]]:
    cycle = _frame(out, "cycle_audit_row")
    upper = _frame(out, "upper_pressure_audit")
    gk = _frame(out, "gk_build_audit")
    translation = _frame(out, "pressure_translation_audit")
    write = _frame(out, "canonical_write_audit")
    rollback = _frame(out, "rollback_snapshot")
    commit = _frame(out, "commit_gate_audit")
    exec_audit = _frame(out, "action_execution_audit")
    transition = _frame(out, "world_transition_audit")

    no_canonical_write = not _any_bool(write, "canonical_write_performed", False)
    adapter_only = _all_bool(exec_audit, "actionmodule_received_actionframe_only", False)
    adapter_called = _all_bool(exec_audit, "actionmodule_called_by_adapter", False)
    no_direct_parameterbox = not _any_bool(exec_audit, "direct_parameter_box_input_to_actionmodule", False)
    no_gk_writeback = not _any_bool(transition, "gk_writeback_performed", False)
    no_ot_writeback = not _any_bool(transition, "ot_writeback_performed", False)
    no_canonical_world_write = not _any_bool(transition, "canonical_parameter_write_performed", False)

    return [
        _check("world_engine_is_v2", cfg.world_engine == "asymmetric_game_v2", f"world_engine={cfg.world_engine!r}"),
        _check("world_profile_is_v2", cfg.world_profile_name == WORLD_PROFILE, f"world_profile={cfg.world_profile_name!r}"),
        _check("canonical_commit_disabled", cfg.canonical_commit_enabled is False, f"canonical_commit_enabled={cfg.canonical_commit_enabled!r}"),
        _check("canonical_dry_run_enabled", cfg.canonical_commit_dry_run is True, f"canonical_commit_dry_run={cfg.canonical_commit_dry_run!r}"),
        _check("canonical_binding_source_shadow", cfg.canonical_binding_source == "shadow", f"canonical_binding_source={cfg.canonical_binding_source!r}"),
        _check("entity_trace_exported", _rows(out, "entity_trace") > 0, f"rows={_rows(out, 'entity_trace')}"),
        _check("relation_trace_exported", _rows(out, "relation_trace") > 0, f"rows={_rows(out, 'relation_trace')}"),
        _check("v2_hidden_trace_exported", _rows(out, "v2_hidden_trace") > 0, f"rows={_rows(out, 'v2_hidden_trace')}"),
        _check("v2_game_trace_exported", _rows(out, "v2_game_trace") > 0, f"rows={_rows(out, 'v2_game_trace')}"),
        _check("v2_resource_trace_exported", _rows(out, "v2_resource_trace") > 0, f"rows={_rows(out, 'v2_resource_trace')}"),
        _check("v2_information_trace_exported", _rows(out, "v2_information_trace") > 0, f"rows={_rows(out, 'v2_information_trace')}"),
        _check("v2_action_effect_trace_exported", _rows(out, "v2_action_effect_trace") > 0, f"rows={_rows(out, 'v2_action_effect_trace')}"),
        _check("world_transition_audit_per_step", _rows(out, "world_transition_audit") >= cfg.steps, f"rows={_rows(out, 'world_transition_audit')}, steps={cfg.steps}"),
        _check("gk_build_audit_per_step", _rows(out, "gk_build_audit") >= cfg.steps, f"rows={_rows(out, 'gk_build_audit')}, steps={cfg.steps}"),
        _check("formal_packet_exported", _rows(out, "formal_packet") > 0, f"rows={_rows(out, 'formal_packet')}"),
        _check("gk_build_status_pass", _all_status(gk, "build_status", "pass"), "G/K build_status should be pass for every row"),
        _check("upper_pressure_audit_per_step", _rows(out, "upper_pressure_audit") >= cfg.steps, f"rows={_rows(out, 'upper_pressure_audit')}, steps={cfg.steps}"),
        _check("upper_input_is_gk_only", _all_bool(upper, "formal_input_is_gk_only", False), "upper pressure must use formal G/K only"),
        _check("upper_pressure_status_pass", _all_status(upper, "audit_status", "pass"), "upper_pressure_audit.audit_status should be pass"),
        _check("weak_pressure_exported", _rows(out, "weak_pressure") > 0, f"rows={_rows(out, 'weak_pressure')}"),
        _check("pressure_translation_pass", _all_status(translation, "pressure_translation_audit_status", "pass"), "translation should preserve approved pressure components non-compressively"),
        _check("pressure_intent_bundle_exported", _rows(out, "pressure_intent_bundle") > 0, f"rows={_rows(out, 'pressure_intent_bundle')}"),
        _check("cycle_audit_rows_present", len(cycle) >= cfg.steps, f"rows={len(cycle)}, steps={cfg.steps}"),
        _check("boundary_violation_zero", int(metrics.get("boundary_violation_rows", -1)) == 0, f"boundary_violation_rows={metrics.get('boundary_violation_rows')!r}"),
        _check("canonical_write_not_performed", no_canonical_write, "canonical_write_performed must remain false"),
        _check("rollback_snapshot_per_step", len(rollback) >= cfg.steps, f"rows={len(rollback)}, steps={cfg.steps}"),
        _check("commit_gate_per_step", len(commit) >= cfg.steps, f"rows={len(commit)}, steps={cfg.steps}"),
        _check("action_execution_audit_per_step", len(exec_audit) >= cfg.steps, f"rows={len(exec_audit)}, steps={cfg.steps}"),
        _check("actionmodule_adapter_called", adapter_called, "ActionModule must be called only through adapter"),
        _check("actionmodule_received_actionframe_only", adapter_only, "ActionModule must receive ActionFrame only"),
        _check("no_direct_parameterbox_input_to_actionmodule", no_direct_parameterbox, "ParameterBox must not be direct ActionModule input"),
        _check("no_gk_writeback", no_gk_writeback, "G/K writeback must remain false"),
        _check("no_ot_writeback", no_ot_writeback, "O_t writeback must remain false"),
        _check("no_canonical_world_write", no_canonical_world_write, "canonical parameter world write must remain false"),
        _check("profile_loader_forbidden_write_not_detected", not bool(metrics.get("forbidden_write_detected", True)), f"forbidden_write_detected={metrics.get('forbidden_write_detected')!r}"),
    ]


def _write_all_outputs(out: dict[str, Any], output_dir: Path) -> None:
    tables_dir = output_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)
    for name, value in sorted(out.items()):
        if isinstance(value, pd.DataFrame):
            dataframe_to_csv(value, tables_dir / f"{name}.csv")


def _write_report(output_dir: Path, summary: dict[str, Any], checks: list[dict[str, Any]]) -> None:
    failed = [c for c in checks if c["critical"] and not c["passed"]]
    rows = [
        "# FullSpec-v2 Connection Audit RC1",
        "",
        "## Position",
        "",
        "This is a diagnostic-only validation run. It connects the FullSpec integrated runner to the v2 pseudo-reality world engine and checks connection/reversibility boundaries.",
        "",
        "## Reversibility guarantees",
        "",
        "- `canonical_commit_enabled` is forced to `False`.",
        "- `canonical_commit_dry_run` is forced to `True`.",
        "- `canonical_binding_source` is forced to `shadow`.",
        "- No production runtime, coefficients, ParameterBox/ShadowBox defaults, canonical state, or ActionModule logic are changed.",
        "- This validation only writes diagnostic result files under `results/fullspec_v2_connection_audit_rc1/` when executed.",
        "",
        "## Summary",
        "",
        f"- overall_pass: `{summary['overall_pass']}`",
        f"- failed_critical_checks: `{summary['failed_critical_check_count']}`",
        f"- world_engine: `{summary['world_engine']}`",
        f"- world_profile: `{summary['world_profile']}`",
        f"- steps: `{summary['steps']}`",
        "",
        "## Checks",
        "",
        "| check | passed | critical | detail |",
        "|---|---:|---:|---|",
    ]
    for c in checks:
        detail = str(c["detail"]).replace("|", "/")
        rows.append(f"| {c['check_name']} | {c['passed']} | {c['critical']} | {detail} |")
    rows.extend([
        "",
        "## Failed critical checks",
        "",
    ])
    if failed:
        for c in failed:
            rows.append(f"- `{c['check_name']}`: {c['detail']}")
    else:
        rows.append("None.")
    (output_dir / "FULLSPEC_V2_CONNECTION_AUDIT_RC1.md").write_text("\n".join(rows) + "\n", encoding="utf-8")


def run_validation(output_dir: Path = OUTPUT_DIR) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    cfg = build_runner_config(
        validation_profile=VALIDATION_PROFILE,
        world_profile=WORLD_PROFILE,
        action_profile=ACTION_PROFILE,
        overrides=REVERSIBLE_OVERRIDES,
    )
    out = run_fullspec_task16(cfg)
    metrics = collect_metrics(LABEL, cfg, out)
    checks = build_connection_checks(cfg, out, metrics)
    failed = [c for c in checks if c["critical"] and not c["passed"]]
    summary = {
        "label": LABEL,
        "overall_pass": len(failed) == 0,
        "failed_critical_check_count": len(failed),
        "failed_critical_checks": [c["check_name"] for c in failed],
        "world_engine": cfg.world_engine,
        "world_profile": cfg.world_profile_name,
        "validation_profile": cfg.validation_profile_name,
        "action_profile": cfg.action_profile_name,
        "steps": cfg.steps,
        "seed": cfg.seed,
        "scenario": cfg.scenario,
        "canonical_commit_enabled": cfg.canonical_commit_enabled,
        "canonical_commit_dry_run": cfg.canonical_commit_dry_run,
        "canonical_binding_source": cfg.canonical_binding_source,
        "metrics": metrics,
    }

    checks_df = pd.DataFrame(checks)
    dataframe_to_csv(checks_df, output_dir / "connection_checks.csv")
    write_json(output_dir / "summary.json", summary)
    write_json(output_dir / "run_manifest.json", {
        "label": LABEL,
        "validation_profile": VALIDATION_PROFILE,
        "world_profile": WORLD_PROFILE,
        "action_profile": ACTION_PROFILE,
        "reversible_overrides": REVERSIBLE_OVERRIDES,
        "config": cfg.__dict__,
    })
    _write_all_outputs(out, output_dir)
    _write_report(output_dir, summary, checks)
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
    return summary


def main() -> int:
    summary = run_validation()
    return 0 if summary["overall_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
