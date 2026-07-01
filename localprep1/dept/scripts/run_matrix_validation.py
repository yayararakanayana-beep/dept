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



def _rate(num: int | float | str, den: int | float | str) -> float | str:
    if isinstance(num, str) or isinstance(den, str):
        return "not_available"
    return float(num) / float(den) if float(den) else "not_available"


def _count_values(frame: pd.DataFrame, column: str) -> str:
    if frame.empty or column not in frame.columns:
        return "not_available"
    counts = frame[column].astype(str).value_counts().sort_index().to_dict()
    return json.dumps({str(k): int(v) for k, v in counts.items()}, sort_keys=True)


def _decision_frame(gate: pd.DataFrame, decision: str) -> pd.DataFrame:
    if gate.empty or "coactivation_gate_decision" not in gate.columns:
        return pd.DataFrame()
    return gate[gate["coactivation_gate_decision"].astype(str).eq(decision)]


def build_candidate_retention_decomposition(label: str, cfg, out: dict) -> pd.DataFrame:
    exploration_candidates = _df(out, "exploration_candidates")
    projection = _df(out, "exploration_projection")
    planning = _df(out, "action_surface_planning_audit")
    gate = _df(out, "coactivation_gate")
    action_frame = _df(out, "action_frame")
    action_result = _df(out, "action_result")
    planner_rows = _first_available_count(planning, ["action_candidate_rows"])
    gate_rows = _first_available_count(gate, ["action_candidate_rows", "candidate_rows", "gate_input_rows"])
    af_rows = int(len(action_frame)) if not action_frame.empty else 0
    exploration_candidate_rows = int(len(exploration_candidates)) if not exploration_candidates.empty else 0
    projection_rows = int(len(projection)) if not projection.empty else 0
    na = []
    if exploration_candidates.empty:
        na.append("exploration_candidate_stage_rows")
    if isinstance(planner_rows, str):
        na.append("planner_candidate_rows")
    if isinstance(gate_rows, str):
        na.append("gate_input_rows")
    return pd.DataFrame([{
        "run_label": label,
        "seed": cfg.seed,
        "steps": cfg.steps,
        "world_profile": cfg.world_profile_name,
        "action_profile": cfg.action_profile_name,
        "intermediate_conservatism_mode": cfg.intermediate_conservatism_mode,
        "exploration_enabled": cfg.exploration_enabled,
        "exploration_candidate_rows": exploration_candidate_rows,
        "exploration_projection_rows": projection_rows,
        "bridge_projection_rows": projection_rows,
        "planner_candidate_rows": planner_rows,
        "gate_input_rows": gate_rows,
        "action_frame_rows": af_rows,
        "action_result_rows": int(len(action_result)) if not action_result.empty else 0,
        "projection_to_planner_retention": _rate(planner_rows, projection_rows),
        "planner_to_gate_retention": _rate(gate_rows, planner_rows),
        "gate_to_actionframe_retention": _rate(af_rows, gate_rows),
        "total_candidate_to_actionframe_retention": _rate(af_rows, exploration_candidate_rows),
        "not_available_fields": ";".join(na),
    }])


def _steps_for_decision(gate: pd.DataFrame, decision: str) -> set:
    dg = _decision_frame(gate, decision)
    if dg.empty or "loop_step" not in dg.columns:
        return set()
    return set(dg["loop_step"].tolist())


def _filter_steps(frame: pd.DataFrame, steps: set) -> pd.DataFrame:
    if frame.empty or not steps or "loop_step" not in frame.columns:
        return pd.DataFrame()
    return frame[frame["loop_step"].isin(steps)]


def build_gate_decomposition_by_decision(label: str, out: dict) -> pd.DataFrame:
    gate = _df(out, "coactivation_gate")
    action_frame = _df(out, "action_frame")
    rows = []
    for decision in ["allow", "dampen", "defer", "block", "monitor_only"]:
        dg = _decision_frame(gate, decision)
        steps = _steps_for_decision(gate, decision)
        af = _filter_steps(action_frame, steps)
        rows.append({
            "run_label": label,
            "gate_decision": decision,
            "decision_count": int(len(dg)),
            "pre_gate_rows": _first_available_count(dg, ["action_candidate_rows", "candidate_rows", "gate_input_rows"]),
            "post_gate_rows": int(len(af)),
            "action_frame_rows": int(len(af)),
            "action_strength_sum": _sum_numeric(af, "action_strength"),
            "action_strength_mean": float(pd.to_numeric(af["action_strength"], errors="coerce").fillna(0.0).mean()) if not af.empty and "action_strength" in af.columns else 0.0,
            "action_channel_counts": _count_values(af, "action_channel"),
            "pressure_source_counts": _count_values(af, "pressure_source"),
            "planning_source_counts": _count_values(af, "planning_source"),
            "binding_source_counts": _count_values(af, "binding_source"),
        })
    return pd.DataFrame(rows)

def build_action_loss_by_gate_decision(label: str, out: dict) -> pd.DataFrame:
    gate = _df(out, "coactivation_gate")
    action_frame = _df(out, "action_frame")
    rows = []
    for decision in ["allow", "dampen", "defer", "block", "monitor_only"]:
        dg = _decision_frame(gate, decision)
        steps = _steps_for_decision(gate, decision)
        af = _filter_steps(action_frame, steps)
        pre = _first_available_count(dg, ["action_candidate_rows", "candidate_rows", "gate_input_rows"])
        post = int(len(af))
        if isinstance(pre, str) or int(len(dg)) == 0:
            loss = "not_available"
            reason = "decision_not_observed_or_pre_gate_rows_unavailable"
            exact = "not_available"
        else:
            loss = max(int(pre) - int(post), 0)
            reason = ""
            exact = "exact_for_rows_approx_for_mass"
        pre_mass = _sum_numeric(dg, "action_strength_mean") * (0 if isinstance(pre, str) else int(pre))
        post_mass = _sum_numeric(af, "action_strength")
        rows.append({
            "run_label": label,
            "gate_decision": decision,
            "estimated_candidate_loss_rows": loss,
            "estimated_action_mass_loss": max(pre_mass - post_mass, 0.0) if int(len(dg)) > 0 and not isinstance(pre, str) else "not_available",
            "loss_estimation_method": "loop_step gate action_candidate_rows minus same-step action_frame_rows; pre-gate mass approximated from gate action_strength_mean",
            "exact_or_approx": exact,
            "not_available_reason": reason,
        })
    return pd.DataFrame(rows)

def build_stage_retention_summary(label: str, out: dict) -> pd.DataFrame:
    decomp = build_candidate_retention_decomposition(label, type("C", (), {"seed":"","steps":"","world_profile_name":"","action_profile_name":"","intermediate_conservatism_mode":"","exploration_enabled":""})(), out).iloc[0].to_dict()
    action_frame = _df(out, "action_frame")
    rows = []
    stages = [
        ("exploration_to_bridge_projection", decomp["exploration_candidate_rows"], decomp["bridge_projection_rows"], "exploration_candidates.csv/exploration_projection.csv"),
        ("bridge_projection_to_planner", decomp["bridge_projection_rows"], decomp["planner_candidate_rows"], "exploration_projection.csv/action_surface_planning_audit.csv"),
        ("planner_to_gate", decomp["planner_candidate_rows"], decomp["gate_input_rows"], "action_surface_planning_audit.csv/coactivation_gate.csv"),
        ("gate_to_actionframe", decomp["gate_input_rows"], decomp["action_frame_rows"], "coactivation_gate.csv/action_frame.csv"),
        ("actionframe_to_actionresult", decomp["action_frame_rows"], decomp["action_result_rows"], "action_frame.csv/action_result.csv"),
    ]
    mass_out = _sum_numeric(action_frame, "action_strength")
    for name, inp, out_rows, artifact in stages:
        lost = "not_available" if isinstance(inp, str) or isinstance(out_rows, str) else max(int(inp) - int(out_rows), 0)
        rows.append({
            "run_label": label,
            "stage_name": name,
            "input_rows": inp,
            "output_rows": out_rows,
            "retained_rows": out_rows,
            "lost_rows": lost,
            "retention_rate": _rate(out_rows, inp),
            "action_mass_in": "not_available" if name != "actionframe_to_actionresult" else mass_out,
            "action_mass_out": mass_out if name in {"gate_to_actionframe", "actionframe_to_actionresult"} else "not_available",
            "action_mass_retention_rate": "not_available",
            "source_artifact": artifact,
        })
    return pd.DataFrame(rows)


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



def _numeric_min(frame: pd.DataFrame, column: str) -> float | str:
    if frame.empty or column not in frame.columns:
        return "not_available"
    s = pd.to_numeric(frame[column], errors="coerce").dropna()
    return float(s.min()) if len(s) else "not_available"


def _numeric_max(frame: pd.DataFrame, column: str) -> float | str:
    if frame.empty or column not in frame.columns:
        return "not_available"
    s = pd.to_numeric(frame[column], errors="coerce").dropna()
    return float(s.max()) if len(s) else "not_available"


def _not_available_count(frame: pd.DataFrame) -> int:
    if frame.empty:
        return 0
    return int(frame.astype(str).isin(["not_available"]).sum().sum())


def _relation_unlock_by_mode(rows: list[dict], metric: str) -> dict[str, float]:
    totals: dict[str, float] = {}
    for row in rows:
        label = str(row.get("label", ""))
        if "relation_unlock_pressure" not in label:
            continue
        mode = str(row.get("intermediate_conservatism_mode", ""))
        totals[mode] = totals.get(mode, 0.0) + float(row.get(metric, 0.0))
    return totals


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
    candidate_retention_rows = []
    gate_decomposition_rows = []
    action_loss_rows = []
    stage_retention_rows = []
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

        candidate_retention = build_candidate_retention_decomposition(label, cfg, out)
        gate_decomposition = build_gate_decomposition_by_decision(label, out)
        action_loss = build_action_loss_by_gate_decision(label, out)
        stage_retention = build_stage_retention_summary(label, out)
        candidate_retention_rows.append(candidate_retention)
        gate_decomposition_rows.append(gate_decomposition)
        action_loss_rows.append(action_loss)
        stage_retention_rows.append(stage_retention)
        dataframe_to_csv(candidate_retention, rd / "candidate_retention_decomposition.csv")
        dataframe_to_csv(gate_decomposition, rd / "gate_decomposition_by_decision.csv")
        dataframe_to_csv(action_loss, rd / "action_loss_by_gate_decision.csv")
        dataframe_to_csv(stage_retention, rd / "stage_retention_summary.csv")

    candidate_retention_all = pd.concat(candidate_retention_rows, ignore_index=True) if candidate_retention_rows else pd.DataFrame()
    gate_decomposition_all = pd.concat(gate_decomposition_rows, ignore_index=True) if gate_decomposition_rows else pd.DataFrame()
    action_loss_all = pd.concat(action_loss_rows, ignore_index=True) if action_loss_rows else pd.DataFrame()
    stage_retention_all = pd.concat(stage_retention_rows, ignore_index=True) if stage_retention_rows else pd.DataFrame()
    dataframe_to_csv(candidate_retention_all, output_dir / "candidate_retention_decomposition.csv")
    dataframe_to_csv(gate_decomposition_all, output_dir / "gate_decomposition_by_decision.csv")
    dataframe_to_csv(action_loss_all, output_dir / "action_loss_by_gate_decision.csv")
    dataframe_to_csv(stage_retention_all, output_dir / "stage_retention_summary.csv")

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
        "candidate_retention_decomposition_present": (output_dir / "candidate_retention_decomposition.csv").exists(),
        "gate_decomposition_by_decision_present": (output_dir / "gate_decomposition_by_decision.csv").exists(),
        "action_loss_by_gate_decision_present": (output_dir / "action_loss_by_gate_decision.csv").exists(),
        "stage_retention_summary_present": (output_dir / "stage_retention_summary.csv").exists(),
        "min_total_candidate_to_actionframe_retention": _numeric_min(candidate_retention_all, "total_candidate_to_actionframe_retention"),
        "min_gate_to_actionframe_retention": _numeric_min(candidate_retention_all, "gate_to_actionframe_retention"),
        "max_estimated_candidate_loss_rows": _numeric_max(action_loss_all, "estimated_candidate_loss_rows"),
        "max_estimated_action_mass_loss": _numeric_max(action_loss_all, "estimated_action_mass_loss"),
        "relation_unlock_action_mass_by_mode": _relation_unlock_by_mode(rows, "relation_unlock_family_action_mass"),
        "relation_unlock_action_frame_rows_by_mode": _relation_unlock_by_mode(rows, "relation_unlock_family_rows"),
        "not_available_field_count": _not_available_count(candidate_retention_all) + _not_available_count(action_loss_all) + _not_available_count(stage_retention_all),
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
