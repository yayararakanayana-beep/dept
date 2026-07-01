#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT_FOR_IMPORTS = SCRIPT_DIR.parent
if str(REPO_ROOT_FOR_IMPORTS) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT_FOR_IMPORTS))

from dept2_fullspec_runner_rc1.runner.fullspec_integrated_closed_loop_runner import run_fullspec_task16

from scripts.profile_loader import (
    REPO_ROOT,
    build_runner_config,
    collect_metrics,
    acceptance_pass,
    dataframe_to_csv,
    load_json,
    write_json,
)


PER_RUN_EXPORTS = [
    # boundary / write / rollback audits
    "boundary_violation_report",
    "canonical_write_audit",
    "rollback_snapshot",
    "commit_gate_audit",
    "parameter_shadow_audit",
    "parameter_window_binding_audit",
    # exploration diagnostic chain
    "exploration_candidates",
    "exploration_sandbox",
    "exploration_decision",
    "exploration_local_audit",
    "local_audit",
    "exploration_sidecar",
    "exploration_projection",
    # planning / gate / action-side audits
    "action_surface_planning_audit",
    "coactivation_gate",
    "action_frame",
    "action_result",
    "action_execution_audit",
    "boundary_guard_audit",
    "cycle_audit_row",
    "world_transition_audit",
    "entity_trace",
    "relation_trace",
    "v2_hidden_trace",
    "v2_game_trace",
    "v2_resource_trace",
    "v2_information_trace",
    "v2_action_effect_trace",
]


def _df(out, name: str) -> pd.DataFrame:
    value = out.get(name)
    return value if value is not None else pd.DataFrame()


def _sum_numeric(frame: pd.DataFrame, column: str) -> float:
    if frame.empty or column not in frame.columns:
        return 0.0
    return float(pd.to_numeric(frame[column], errors="coerce").fillna(0.0).sum())


def _count_eq(frame: pd.DataFrame, column: str, value: str) -> int:
    if frame.empty or column not in frame.columns:
        return 0
    return int(frame[column].astype(str).eq(value).sum())


def _first_available_count(frame: pd.DataFrame, columns: list[str]) -> int | str:
    if frame.empty:
        return 0
    for column in columns:
        if column in frame.columns:
            return int(_sum_numeric(frame, column))
    return "not_available"


def build_module_thinning_audit(label: str, cfg, out: dict, metrics: dict) -> pd.DataFrame:
    planning = _df(out, "action_surface_planning_audit")
    gate = _df(out, "coactivation_gate")
    action_frame = _df(out, "action_frame")
    exec_audit = _df(out, "action_execution_audit")
    boundary = _df(out, "boundary_guard_audit")
    return pd.DataFrame([
        {
            "run_label": label,
            "seed": cfg.seed,
            "steps": cfg.steps,
            "intermediate_conservatism_mode": cfg.intermediate_conservatism_mode,
            "world_profile": cfg.world_profile_name,
            "action_profile": cfg.action_profile_name,
            "exploration_enabled": cfg.exploration_enabled,
            "projection_rows": metrics.get("projection_rows", 0),
            "action_candidate_rows": _first_available_count(planning, ["action_candidate_rows"]),
            "projected_candidate_rows": metrics.get("projection_rows", 0),
            "gate_input_rows": _first_available_count(gate, ["candidate_rows", "action_candidate_rows", "gate_input_rows"]),
            "gate_allow_count": metrics.get("gate_allow_count", 0),
            "gate_dampen_count": metrics.get("gate_dampen_count", 0),
            "gate_defer_count": metrics.get("gate_defer_count", 0),
            "gate_block_count": metrics.get("gate_block_count", 0),
            "gate_monitor_only_count": metrics.get("gate_monitor_only_count", 0),
            "action_frame_rows": metrics.get("action_frame_rows", 0),
            "action_mass": metrics.get("action_frame_strength_sum", 0.0),
            "action_source_audit_columns_present": metrics.get("action_source_audit_columns_present", False),
            "boundary_violation_total": metrics.get("boundary_violation_rows", 0),
            "dry_run_write_violation_count": int(bool(metrics.get("dry_run_write_violation", False))),
            "forbidden_write_count": int(bool(metrics.get("forbidden_write_detected", False))),
            "boundary_guard_failed_rows": _count_eq(boundary, "guard_status", "fail"),
            "source_action_candidate_rows": _first_available_count(exec_audit, ["source_action_candidate_rows"]),
        }
    ])


def build_gate_decision_summary(label: str, out: dict) -> pd.DataFrame:
    gate = _df(out, "coactivation_gate")
    action_frame = _df(out, "action_frame")
    decisions = ["allow", "dampen", "defer", "block", "monitor_only"]
    rows = []
    for decision in decisions:
        rows.append({
            "run_label": label,
            "gate_decision": decision,
            "decision_count": _count_eq(gate, "coactivation_gate_decision", decision),
            "action_frame_rows": int(len(action_frame)) if not action_frame.empty else 0,
            "action_loss": "not_available",
        })
    return pd.DataFrame(rows)


def build_candidate_retention_summary(label: str, out: dict) -> pd.DataFrame:
    planning = _df(out, "action_surface_planning_audit")
    projection = _df(out, "exploration_projection")
    gate = _df(out, "coactivation_gate")
    return pd.DataFrame([{
        "run_label": label,
        "candidate_stage": "planning_to_projection_to_gate",
        "action_candidate_rows": _first_available_count(planning, ["action_candidate_rows"]),
        "projected_candidate_rows": int(len(projection)) if not projection.empty else 0,
        "gate_input_rows": _first_available_count(gate, ["candidate_rows", "action_candidate_rows", "gate_input_rows"]),
        "retention_note": "observed_from_existing_artifacts_only",
    }])


def build_actionframe_retention_summary(label: str, out: dict) -> pd.DataFrame:
    exec_audit = _df(out, "action_execution_audit")
    action_frame = _df(out, "action_frame")
    action_result = _df(out, "action_result")
    return pd.DataFrame([{
        "run_label": label,
        "source_action_candidate_rows": _first_available_count(exec_audit, ["source_action_candidate_rows"]),
        "action_frame_rows": int(len(action_frame)) if not action_frame.empty else 0,
        "action_result_rows": int(len(action_result)) if not action_result.empty else 0,
        "action_mass": _sum_numeric(action_frame, "action_strength"),
        "retention_note": "observed_from_existing_artifacts_only",
    }])


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Task22C profile matrix validation.")
    parser.add_argument("--matrix", default=str(REPO_ROOT / "configs" / "matrices" / "matrix_basic.json"))
    parser.add_argument("--output-dir", default=str(REPO_ROOT / "validation_runs" / "latest"))
    args = parser.parse_args()

    matrix_path = Path(args.matrix)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    matrix = load_json(matrix_path)
    rows = []
    per_run_dir = output_dir / "runs"
    per_run_dir.mkdir(parents=True, exist_ok=True)

    for run in matrix["runs"]:
        label = run["label"]
        cfg = build_runner_config(
            validation_profile=run["validation_profile"],
            world_profile=run["world_profile"],
            action_profile=run["action_profile"],
            overrides=run.get("overrides", {}),
        )
        out = run_fullspec_task16(cfg)
        metrics = collect_metrics(label, cfg, out)
        metrics["overall_pass"] = acceptance_pass(metrics)
        rows.append(metrics)

        rd = per_run_dir / label
        rd.mkdir(parents=True, exist_ok=True)
        write_json(rd / "summary.json", metrics)
        for name in PER_RUN_EXPORTS:
            df = out.get(name)
            if df is not None:
                dataframe_to_csv(df, rd / f"{name}.csv")

        dataframe_to_csv(build_module_thinning_audit(label, cfg, out, metrics), rd / "module_thinning_audit.csv")
        dataframe_to_csv(build_gate_decision_summary(label, out), rd / "gate_decision_summary.csv")
        dataframe_to_csv(build_candidate_retention_summary(label, out), rd / "candidate_retention_summary.csv")
        dataframe_to_csv(build_actionframe_retention_summary(label, out), rd / "actionframe_retention_summary.csv")

    fieldnames = list(rows[0].keys())
    with (output_dir / "matrix_metrics.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    overall = {
        "matrix_name": matrix.get("name", matrix_path.stem),
        "runs": len(rows),
        "overall_pass": all(bool(r["overall_pass"]) for r in rows),
        "boundary_violation_total": sum(int(r["boundary_violation_rows"]) for r in rows),
        "dry_run_write_violation_count": sum(1 for r in rows if bool(r["dry_run_write_violation"])),
        "forbidden_write_count": sum(1 for r in rows if bool(r["forbidden_write_detected"])),
        "projection_min": min(int(r["projection_rows"]) for r in rows),
        "action_frame_min": min(int(r["action_frame_rows"]) for r in rows),
        "action_mass_min": min(float(r["action_frame_strength_sum"]) for r in rows),
        "gate_allow_total": sum(int(r["gate_allow_count"]) for r in rows),
        "gate_dampen_total": sum(int(r["gate_dampen_count"]) for r in rows),
        "gate_defer_total": sum(int(r["gate_defer_count"]) for r in rows),
        "gate_block_total": sum(int(r["gate_block_count"]) for r in rows),
        "action_source_audit_columns_present": all(bool(r.get("action_source_audit_columns_present", False)) for r in rows),
        "action_result_export_present": all((per_run_dir / r["label"] / "action_result.csv").exists() for r in rows),
        "boundary_guard_audit_export_present": all((per_run_dir / r["label"] / "boundary_guard_audit.csv").exists() for r in rows),
        "cycle_audit_row_export_present": all((per_run_dir / r["label"] / "cycle_audit_row.csv").exists() for r in rows),
        "module_thinning_audit_present": all((per_run_dir / r["label"] / "module_thinning_audit.csv").exists() for r in rows),
        "gate_decision_summary_present": all((per_run_dir / r["label"] / "gate_decision_summary.csv").exists() for r in rows),
        "candidate_retention_summary_present": all((per_run_dir / r["label"] / "candidate_retention_summary.csv").exists() for r in rows),
        "actionframe_retention_summary_present": all((per_run_dir / r["label"] / "actionframe_retention_summary.csv").exists() for r in rows),
        "labels": [r["label"] for r in rows],
    }
    write_json(output_dir / "matrix_summary.json", overall)
    write_json(output_dir / "run_manifest.json", {"matrix": matrix, "overall": overall})

    (output_dir / "README.md").write_text(
        "# Latest matrix validation\n\n"
        f"matrix: `{overall['matrix_name']}`\n\n"
        f"overall_pass: `{overall['overall_pass']}`\n\n"
        "See `matrix_summary.json`, `matrix_metrics.csv`, and per-run CSV files.\n",
        encoding="utf-8",
    )

    print(json.dumps(overall, ensure_ascii=False, indent=2))
    return 0 if overall["overall_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
