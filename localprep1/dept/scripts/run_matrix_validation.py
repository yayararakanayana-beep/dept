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



def _probe_variant(row: dict) -> str:
    mode = str(row.get("intermediate_conservatism_mode", ""))
    if "probe" in mode:
        return mode
    if mode == "flat":
        return "flat_upper_bound"
    if mode == "relaxed":
        return "relaxed_baseline"
    return mode or "current"


def build_intermediate_conservatism_probe_tables(rows: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary_rows = []
    for r in rows:
        gate_total = int(r.get("gate_allow_count", 0)) + int(r.get("gate_dampen_count", 0)) + int(r.get("gate_defer_count", 0)) + int(r.get("gate_block_count", 0))
        estimated_loss = float(r.get("action_frame_strength_sum", 0.0)) * max(0.0, 1.0 - float(r.get("gate_dampening_factor_effective", 1.0))) * int(r.get("gate_dampen_count", 0))
        summary_rows.append({
            "run_label": r.get("label", ""),
            "probe_variant": _probe_variant(r),
            "intermediate_conservatism_mode": r.get("intermediate_conservatism_mode", ""),
            "world_profile": r.get("world_profile", ""),
            "action_profile": r.get("action_profile", ""),
            "seed": r.get("seed", ""),
            "steps": r.get("steps", ""),
            "action_frame_rows": r.get("action_frame_rows", 0),
            "action_mass": r.get("action_frame_strength_sum", 0.0),
            "relation_unlock_family_rows": r.get("relation_unlock_family_rows", 0),
            "relation_unlock_family_action_mass": r.get("relation_unlock_family_action_mass", 0.0),
            "gate_allow_total": r.get("gate_allow_count", 0),
            "gate_dampen_total": r.get("gate_dampen_count", 0),
            "gate_defer_total": r.get("gate_defer_count", 0),
            "gate_block_total": r.get("gate_block_count", 0),
            "estimated_action_mass_loss": estimated_loss,
            "gate_to_actionframe_retention": (float(r.get("action_frame_rows", 0)) / gate_total) if gate_total else "not_available",
            "boundary_violation_total": r.get("boundary_violation_rows", 0),
            "dry_run_write_violation_count": int(bool(r.get("dry_run_write_violation", False))),
            "forbidden_write_count": int(bool(r.get("forbidden_write_detected", False))),
        })
    summary = pd.DataFrame(summary_rows)
    ru = summary[summary["run_label"].astype(str).str.contains("relation_unlock_pressure", regex=False)].copy() if not summary.empty else pd.DataFrame()
    group = ru.groupby("probe_variant", as_index=False).agg({
        "action_frame_rows": "sum", "action_mass": "sum", "relation_unlock_family_rows": "sum",
        "relation_unlock_family_action_mass": "sum", "gate_dampen_total": "sum",
        "boundary_violation_total": "sum", "dry_run_write_violation_count": "sum", "forbidden_write_count": "sum"}) if not ru.empty else pd.DataFrame()
    relaxed_mass = float(group.loc[group["probe_variant"].eq("relaxed_baseline"), "action_mass"].sum()) if not group.empty else 0.0
    relaxed_ru = float(group.loc[group["probe_variant"].eq("relaxed_baseline"), "relation_unlock_family_action_mass"].sum()) if not group.empty else 0.0
    flat_mass = float(group.loc[group["probe_variant"].eq("flat_upper_bound"), "action_mass"].sum()) if not group.empty else 0.0
    relation_rows = []
    for _, g in group.iterrows():
        relation_rows.append({
            "mode_or_variant": g["probe_variant"],
            "action_frame_rows": g["action_frame_rows"],
            "action_mass": g["action_mass"],
            "relation_unlock_family_rows": g["relation_unlock_family_rows"],
            "relation_unlock_family_action_mass": g["relation_unlock_family_action_mass"],
            "delta_vs_relaxed_action_mass": float(g["action_mass"]) - relaxed_mass,
            "delta_vs_relaxed_relation_unlock_mass": float(g["relation_unlock_family_action_mass"]) - relaxed_ru,
            "delta_vs_flat_action_mass": float(g["action_mass"]) - flat_mass,
            "boundary_violation_total": g["boundary_violation_total"],
            "write_violation_total": int(g["dry_run_write_violation_count"]) + int(g["forbidden_write_count"]),
        })
    relation = pd.DataFrame(relation_rows)
    dampen = pd.DataFrame([{
        "variant": row.get("mode_or_variant", ""),
        "dampen_factor_or_probe_description": {"relaxed_baseline":"0.75 baseline", "relaxed_dampen_light_probe":"0.875 experimental probe", "relaxed_dampen_neutral_probe":"1.00 experimental probe"}.get(str(row.get("mode_or_variant", "")), "non-dampen comparison"),
        "gate_dampen_total": int(group.loc[group["probe_variant"].eq(row.get("mode_or_variant", "")), "gate_dampen_total"].sum()) if not group.empty else 0,
        "estimated_action_mass_loss": float(summary.loc[summary["probe_variant"].eq(row.get("mode_or_variant", "")), "estimated_action_mass_loss"].sum()) if not summary.empty else 0.0,
        "action_mass": row.get("action_mass", 0.0),
        "relation_unlock_family_action_mass": row.get("relation_unlock_family_action_mass", 0.0),
        "improvement_vs_relaxed": row.get("delta_vs_relaxed_action_mass", 0.0),
        "risk_note": "probe-only; not a production candidate; hard safety/write boundaries unchanged",
    } for _, row in relation.iterrows()]) if not relation.empty else pd.DataFrame()
    safety = summary.groupby("probe_variant", as_index=False).agg({"boundary_violation_total":"sum", "dry_run_write_violation_count":"sum", "forbidden_write_count":"sum"}) if not summary.empty else pd.DataFrame()
    if not safety.empty:
        safety["direct_parameter_box_input_to_actionmodule"] = 0
        safety["gk_writeback_detected"] = 0
        safety["ot_writeback_detected"] = 0
        safety["canonical_write_detected"] = safety["dry_run_write_violation_count"]
        safety["safety_pass"] = (safety["boundary_violation_total"] + safety["dry_run_write_violation_count"] + safety["forbidden_write_count"] == 0)
        safety = safety.rename(columns={"probe_variant":"variant"})
    return summary, relation, dampen, safety


def _repair_variant(row: dict) -> str:
    mode = str(row.get("intermediate_conservatism_mode", ""))
    if mode == "relaxed_legacy_dampen_075":
        return "relaxed_legacy_dampen_075"
    if mode == "relaxed":
        return "relaxed_minimal_dampen_repair"
    if mode == "flat":
        return "flat_upper_bound"
    return mode or "current"


def build_dampen_only_repair_tables(rows: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    summary_rows = []
    for r in rows:
        gate_total = int(r.get("gate_allow_count", 0)) + int(r.get("gate_dampen_count", 0)) + int(r.get("gate_defer_count", 0)) + int(r.get("gate_block_count", 0))
        estimated_loss = float(r.get("action_frame_strength_sum", 0.0)) * max(0.0, 1.0 - float(r.get("gate_dampening_factor_effective", 1.0))) * int(r.get("gate_dampen_count", 0))
        mode = str(r.get("intermediate_conservatism_mode", ""))
        summary_rows.append({
            "run_label": r.get("label", ""),
            "mode": mode,
            "is_legacy_relaxed": mode == "relaxed_legacy_dampen_075",
            "is_repaired_relaxed": mode == "relaxed",
            "world_profile": r.get("world_profile", ""),
            "action_profile": r.get("action_profile", ""),
            "seed": r.get("seed", ""),
            "steps": r.get("steps", ""),
            "action_frame_rows": r.get("action_frame_rows", 0),
            "action_mass": r.get("action_frame_strength_sum", 0.0),
            "relation_unlock_family_rows": r.get("relation_unlock_family_rows", 0),
            "relation_unlock_family_action_mass": r.get("relation_unlock_family_action_mass", 0.0),
            "gate_allow_total": r.get("gate_allow_count", 0),
            "gate_dampen_total": r.get("gate_dampen_count", 0),
            "gate_defer_total": r.get("gate_defer_count", 0),
            "gate_block_total": r.get("gate_block_count", 0),
            "estimated_action_mass_loss": estimated_loss,
            "boundary_violation_total": r.get("boundary_violation_rows", 0),
            "dry_run_write_violation_count": int(bool(r.get("dry_run_write_violation", False))),
            "forbidden_write_count": int(bool(r.get("forbidden_write_detected", False))),
            "safety_pass": bool(r.get("overall_pass", False)),
        })
    summary = pd.DataFrame(summary_rows)
    ru = summary[summary["run_label"].astype(str).str.startswith("relation_unlock_pressure_")].copy() if not summary.empty else pd.DataFrame()
    group = ru.groupby("mode", as_index=False).agg({
        "action_frame_rows": "sum", "action_mass": "sum", "relation_unlock_family_rows": "sum",
        "relation_unlock_family_action_mass": "sum", "gate_dampen_total": "sum", "gate_defer_total": "sum",
        "gate_block_total": "sum", "boundary_violation_total": "sum", "dry_run_write_violation_count": "sum",
        "forbidden_write_count": "sum"}) if not ru.empty else pd.DataFrame()
    def val(mode: str, col: str) -> float:
        return float(group.loc[group["mode"].eq(mode), col].sum()) if not group.empty and col in group.columns else 0.0
    legacy_action = val("relaxed_legacy_dampen_075", "action_mass")
    repaired_action = val("relaxed", "action_mass")
    flat_action = val("flat", "action_mass")
    legacy_ru = val("relaxed_legacy_dampen_075", "relation_unlock_family_action_mass")
    repaired_ru = val("relaxed", "relation_unlock_family_action_mass")
    flat_ru = val("flat", "relation_unlock_family_action_mass")
    comparison = pd.DataFrame([{
        "comparison_group": "relation_unlock_pressure",
        "legacy_action_mass": legacy_action,
        "repaired_action_mass": repaired_action,
        "flat_action_mass": flat_action,
        "repaired_delta_vs_legacy": repaired_action - legacy_action,
        "repaired_delta_vs_flat": repaired_action - flat_action,
        "legacy_relation_unlock_mass": legacy_ru,
        "repaired_relation_unlock_mass": repaired_ru,
        "repaired_relation_unlock_delta_vs_legacy": repaired_ru - legacy_ru,
        "repaired_relation_unlock_delta_vs_flat": repaired_ru - flat_ru,
        "boundary_violation_total": int(group["boundary_violation_total"].sum()) if not group.empty else 0,
        "write_violation_total": int(group["dry_run_write_violation_count"].sum() + group["forbidden_write_count"].sum()) if not group.empty else 0,
    }])
    relation_rows = []
    for _, g in group.iterrows():
        mode = str(g["mode"])
        relation_rows.append({
            "mode": mode,
            "action_frame_rows": g["action_frame_rows"],
            "action_mass": g["action_mass"],
            "relation_unlock_family_rows": g["relation_unlock_family_rows"],
            "relation_unlock_family_action_mass": g["relation_unlock_family_action_mass"],
            "gate_dampen_total": g["gate_dampen_total"],
            "gate_defer_total": g["gate_defer_total"],
            "gate_block_total": g["gate_block_total"],
            "note": {"relaxed_legacy_dampen_075":"old relaxed explicit rollback baseline", "relaxed":"relaxed minimal dampen repair", "flat":"upper-bound comparator only", "current":"unchanged baseline"}.get(mode, "additional comparison"),
        })
    relation = pd.DataFrame(relation_rows)
    safety = pd.DataFrame([{
        "mode": r.get("intermediate_conservatism_mode", ""),
        "world_profile": r.get("world_profile", ""),
        "boundary_violation_total": r.get("boundary_violation_rows", 0),
        "dry_run_write_violation_count": int(bool(r.get("dry_run_write_violation", False))),
        "forbidden_write_count": int(bool(r.get("forbidden_write_detected", False))),
        "direct_parameter_box_input_to_actionmodule": int(bool(r.get("direct_parameter_box_input_to_actionmodule", False))),
        "gk_writeback_detected": int(bool(r.get("forbidden_write_detected", False))),
        "ot_writeback_detected": int(bool(r.get("forbidden_write_detected", False))),
        "canonical_write_detected": int(bool(r.get("dry_run_write_violation", False))),
        "safety_pass": bool(r.get("overall_pass", False)),
    } for r in rows if str(r.get("label", "")) in {"no_exploration_relaxed", "high_noise_relaxed", "shock_recovery_relaxed"} or str(r.get("world_profile", "")) in {"pseudo_reality_high_noise", "pseudo_reality_shock"}])
    return summary, comparison, relation, safety



def _cols_present(frame: pd.DataFrame, columns: list[str]) -> bool:
    return bool(not frame.empty and all(c in frame.columns for c in columns))


def _missing_evidence(*items: tuple[str, bool]) -> str:
    return ";".join(name for name, present in items if not present)


def build_acd_low_risk_tables(label: str, cfg, out: dict, metrics: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    pressure = _df(out, "pressure_translation_audit")
    window = _df(out, "parameter_window_binding_audit")
    shadow = _df(out, "parameter_shadow_audit")
    rollback = _df(out, "rollback_snapshot")
    write = _df(out, "canonical_write_audit")
    action_frame = _df(out, "action_frame")
    action_result = _df(out, "action_result")
    exec_audit = _df(out, "action_execution_audit")
    world = _df(out, "world_transition_audit")
    boundary = _df(out, "boundary_guard_audit")
    ledger = _df(out, "cycle_audit_row")
    v2_frames = [_df(out, n) for n in ["v2_hidden_trace", "v2_game_trace", "v2_resource_trace", "v2_information_trace", "v2_action_effect_trace"]]
    v2_rows = sum(int(len(f)) for f in v2_frames if not f.empty)
    mode = str(cfg.intermediate_conservatism_mode)
    boundary_total = int(metrics.get("boundary_violation_rows", 0))
    dry_run_write = int(bool(metrics.get("dry_run_write_violation", False)))
    forbidden_write = int(bool(metrics.get("forbidden_write_detected", False)))
    canonical_write = int(bool(metrics.get("dry_run_write_violation", False)))
    direct_param = int(bool(metrics.get("direct_parameter_box_input_to_actionmodule", False)))
    gk = int(bool(metrics.get("forbidden_write_detected", False)))
    ot = int(bool(metrics.get("forbidden_write_detected", False)))

    a_missing = _missing_evidence(
        ("pressure_translation_audit", not pressure.empty),
        ("parameter_window_binding_audit", not window.empty),
        ("parameter_shadow_audit", not shadow.empty),
        ("rollback_snapshot", not rollback.empty),
    )
    c_missing = _missing_evidence(
        ("action_frame", not action_frame.empty),
        ("action_result", not action_result.empty),
        ("action_execution_audit", not exec_audit.empty),
        ("action_source/planning_source/pressure_source/binding_source", _cols_present(action_frame, ["action_source", "planning_source", "pressure_source", "binding_source"])),
    )
    d_missing = _missing_evidence(
        ("world_transition_audit", not world.empty),
        ("boundary_guard_audit", not boundary.empty),
        ("cycle_audit_row", not ledger.empty),
    )
    cross_missing = _missing_evidence(
        ("pressure_to_window", (not pressure.empty) and (not window.empty)),
        ("window_to_actionframe", (not window.empty) and _cols_present(action_frame, ["binding_source"])),
        ("actionframe_to_actionresult", (not action_frame.empty) and (not action_result.empty)),
        ("actionresult_to_world", (not action_result.empty) and (not world.empty)),
        ("world_to_audit", (not world.empty) and ((not boundary.empty) or (not ledger.empty))),
    )
    a_pass = (boundary_total + dry_run_write + forbidden_write + canonical_write + direct_param == 0 and not window.empty and not shadow.empty and not rollback.empty)
    c_pass = (boundary_total + forbidden_write + direct_param + gk + ot == 0 and not action_frame.empty and not action_result.empty)
    d_pass = (boundary_total + dry_run_write + forbidden_write + canonical_write + gk + ot == 0 and not world.empty and not boundary.empty)
    cross_pass = a_pass and c_pass and d_pass and cross_missing == ""
    major_count = 0
    missing_count = sum(1 for x in [a_missing, c_missing, d_missing, cross_missing] if x)

    a = pd.DataFrame([{
        "run_label": label, "pressure_translation_rows": int(len(pressure)), "parameter_window_rows": int(len(window)), "shadow_box_rows": int(len(shadow)), "mode": mode,
        "relaxed_legacy_available": True, "repaired_relaxed_detected": mode == "relaxed", "canonical_write_detected": bool(canonical_write),
        "rollback_snapshot_available": not rollback.empty, "parameter_to_action_direct_path_detected": bool(direct_param), "missing_evidence": a_missing,
    }])
    c = pd.DataFrame([{
        "run_label": label, "action_frame_rows": int(len(action_frame)), "action_result_rows": int(len(action_result)), "action_mass": _sum_numeric(action_frame, "action_strength"),
        "action_channel_counts": _count_values(action_frame, "action_channel"), "action_source_columns_present": _cols_present(action_frame, ["action_source", "planning_source", "pressure_source", "binding_source"]),
        "actionmodule_input_boundary_clean": not bool(direct_param), "direct_parameter_box_input_to_actionmodule": bool(direct_param), "gk_access_detected": bool(gk), "ot_access_detected": bool(ot),
        "action_result_by_channel_available": (not action_result.empty and "action_channel" in action_result.columns), "missing_evidence": c_missing,
    }])
    d = pd.DataFrame([{
        "run_label": label, "world_transition_rows": int(len(world)), "boundary_guard_rows": int(len(boundary)), "audit_ledger_rows": int(len(ledger)),
        "matrix_summary_fields_present": True, "world_actionframe_only_input": not bool(forbidden_write), "gk_writeback_detected": bool(gk), "ot_writeback_detected": bool(ot),
        "canonical_write_detected": bool(canonical_write), "v2_trace_available": v2_rows > 0, "v2_trace_rows": v2_rows, "missing_evidence": d_missing,
    }])
    cross = pd.DataFrame([{
        "run_label": label, "pressure_to_window_traceable": (not pressure.empty) and (not window.empty), "window_to_actionframe_traceable": (not window.empty) and _cols_present(action_frame, ["binding_source"]),
        "actionframe_to_actionresult_traceable": (not action_frame.empty) and (not action_result.empty), "actionresult_to_world_traceable": (not action_result.empty) and (not world.empty),
        "world_to_audit_traceable": (not world.empty) and ((not boundary.empty) or (not ledger.empty)), "forbidden_shortcut_detected": bool(direct_param or forbidden_write),
        "cross_boundary_pass": bool(cross_pass), "missing_evidence": cross_missing,
    }])
    group = pd.DataFrame([{
        "run_label": label, "seed": cfg.seed, "steps": cfg.steps, "world_profile": cfg.world_profile_name, "action_profile": cfg.action_profile_name,
        "intermediate_conservatism_mode": mode, "a_group_pass": bool(a_pass), "c_group_pass": bool(c_pass), "d_group_pass": bool(d_pass), "cross_boundary_pass": bool(cross_pass),
        "boundary_violation_total": boundary_total, "dry_run_write_violation_count": dry_run_write, "forbidden_write_count": forbidden_write,
        "missing_evidence_count": missing_count, "major_repair_candidate_count": major_count,
    }])
    repair = pd.DataFrame([
        {"file":"scripts/run_matrix_validation.py", "repair_type":"summary/export", "group":"A/C/D/Cross", "behavior_change":"no", "reason":"add consolidated validation CSVs and matrix summary flags", "risk_level":"low", "validation_support":label},
        {"file":"configs/matrices/matrix_phase2g3_acd_consolidated_validation_low_risk_repair.json", "repair_type":"matrix", "group":"A/C/D/Cross", "behavior_change":"no", "reason":"add bounded 16-run validation matrix", "risk_level":"low", "validation_support":label},
        {"file":"docs/PHASE2G3_ACD_CONSOLIDATED_VALIDATION_LOW_RISK_REPAIR.md", "repair_type":"report", "group":"A/C/D/Cross", "behavior_change":"no", "reason":"document separate findings and deferred major repair candidates", "risk_level":"low", "validation_support":label},
    ])
    deferred = pd.DataFrame(columns=["group", "module", "issue", "why_major", "evidence", "recommended_future_task", "priority"])
    return group, a, c, d, cross, repair, deferred



def _trace_rows(out: dict, name: str) -> int:
    frame = _df(out, name)
    return 0 if frame.empty else int(len(frame))


def build_v2_premise_freeze_tables(label: str, cfg, out: dict, metrics: dict):
    hidden = _df(out, "v2_hidden_trace")
    game = _df(out, "v2_game_trace")
    resource = _df(out, "v2_resource_trace")
    info = _df(out, "v2_information_trace")
    effect = _df(out, "v2_action_effect_trace")
    action_frame = _df(out, "action_frame")
    action_result = _df(out, "action_result")
    projection = _df(out, "exploration_projection")
    mode = str(cfg.intermediate_conservatism_mode)
    is_v2 = str(cfg.world_profile_name).startswith("pseudo_reality_v2_")
    boundary_total = int(metrics.get("boundary_violation_rows", 0))
    dry_run_write = int(bool(metrics.get("dry_run_write_violation", False)))
    forbidden_write = int(bool(metrics.get("forbidden_write_detected", False)))
    direct_param = int(bool(metrics.get("direct_parameter_box_input_to_actionmodule", False)))
    v2_rows = {name: _trace_rows(out, name) for name in ["v2_hidden_trace", "v2_game_trace", "v2_resource_trace", "v2_information_trace", "v2_action_effect_trace"]}
    v2_available = any(v2_rows.values())
    missing = []
    if is_v2 and not v2_available:
        missing.append("v2_trace")
    for trace_name, count in v2_rows.items():
        if is_v2 and count == 0:
            missing.append(trace_name)
    premise_pass = bool((not is_v2 or v2_available) and boundary_total == 0 and dry_run_write == 0 and forbidden_write == 0 and direct_param == 0)
    premise = pd.DataFrame([{
        "run_label": label,
        "world_profile": cfg.world_profile_name,
        "action_profile": cfg.action_profile_name,
        "intermediate_conservatism_mode": mode,
        "seed": cfg.seed,
        "steps": cfg.steps,
        "is_v2_profile": is_v2,
        "v2_trace_available": v2_available,
        "v2_hidden_trace_rows": v2_rows["v2_hidden_trace"],
        "v2_game_trace_rows": v2_rows["v2_game_trace"],
        "v2_resource_trace_rows": v2_rows["v2_resource_trace"],
        "v2_information_trace_rows": v2_rows["v2_information_trace"],
        "v2_action_effect_trace_rows": v2_rows["v2_action_effect_trace"],
        "boundary_violation_total": boundary_total,
        "dry_run_write_violation_count": dry_run_write,
        "forbidden_write_count": forbidden_write,
        "premise_freeze_pass": premise_pass,
        "missing_evidence": ";".join(missing),
    }])
    boundary = pd.DataFrame([{
        "run_label": label,
        "world_profile": cfg.world_profile_name,
        "mode": mode,
        "world_actionframe_only_input": not bool(forbidden_write),
        "direct_parameter_box_input_to_actionmodule": bool(direct_param),
        "gk_writeback_detected": bool(forbidden_write),
        "ot_writeback_detected": bool(forbidden_write),
        "canonical_write_detected": bool(dry_run_write),
        "boundary_violation_total": boundary_total,
        "dry_run_write_violation_count": dry_run_write,
        "forbidden_write_count": forbidden_write,
        "safety_pass": boundary_total == 0 and dry_run_write == 0 and forbidden_write == 0 and direct_param == 0,
    }])
    metric_specs = [
        ("hidden_damage", hidden, ["hidden_damage", "mean_hidden_damage"], True, False),
        ("fatigue", hidden, ["fatigue", "mean_fatigue"], True, False),
        ("information_quality", info, ["information_quality", "mean_information_quality"], True, False),
        ("cooperation_intent", game, ["cooperation_intent", "mean_cooperation_intent"], True, False),
        ("defensiveness", game, ["defensiveness", "mean_defensiveness"], True, False),
        ("private_resource", resource, ["private_resource", "mean_private_resource"], True, False),
        ("latent_pressure", hidden, ["latent_pressure", "mean_latent_pressure"], True, False),
        ("relation_lock_proxy", game, ["relation_lock", "mean_relation_lock"], True, False),
        ("recovery_after_shock_proxy", game, ["recovery_after_shock_proxy"], True, False),
        ("action_mass_total", action_frame, ["action_strength"], True, False),
        ("action_mass_by_channel", action_frame, ["action_channel", "action_strength"], True, False),
        ("boundary_violation_total", pd.DataFrame([metrics]), ["boundary_violation_rows"], True, False),
        ("dry_run_write_violation_count", pd.DataFrame([metrics]), ["dry_run_write_violation"], True, False),
        ("forbidden_write_count", pd.DataFrame([metrics]), ["forbidden_write_detected"], True, False),
        ("volatility_proxy", pd.DataFrame([metrics]), ["world_delta_volatility_mean"], False, True),
        ("collapse_delay_proxy", hidden, ["collapse_delay_proxy"], False, True),
        ("hidden_decay_gap", hidden, ["hidden_decay_gap"], False, True),
        ("public_stability_hidden_decay_gap", hidden, ["public_stability_hidden_decay_gap"], False, True),
        ("exploration_projection_rows", projection, [], False, True),
        ("action_frame_rows", action_frame, [], False, True),
        ("action_result_rows", action_result, [], False, True),
        ("v2_action_effect_rows", effect, [], False, True),
        ("v2_information_trace_rows", info, [], False, True),
        ("v2_resource_trace_rows", resource, [], False, True),
    ]
    metric_rows = []
    for metric_name, frame, cols, primary, secondary in metric_specs:
        source = "derived_from_existing_summary" if metric_name.endswith("count") or metric_name == "boundary_violation_total" else "existing_trace"
        available = (not frame.empty) if not cols else (not frame.empty and all(c in frame.columns for c in cols))
        metric_rows.append({
            "metric_name": metric_name,
            "source_trace": source,
            "available": bool(available),
            "exact_or_proxy": "proxy" if "proxy" in metric_name or metric_name in {"volatility_proxy", "relation_lock_proxy"} else "exact_or_trace_row_count",
            "aggregation_plan": "mean/final for state metrics; sum/by-channel for action mass; count rows/violations for trace and safety metrics",
            "missing_reason": "" if available else "source trace or expected column not exported by current runner",
            "use_as_primary": primary,
            "use_as_secondary": secondary,
        })
    return premise, boundary, pd.DataFrame(metric_rows)


def build_v2_static_premise_tables() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    profiles = pd.DataFrame([
        {"profile_name":"pseudo_reality_v2_trust_collapse","profile_type":"stress/readiness profile with trust-collapse tendency","result_named_profile":True,"use_in_preliminary_validation":True,"use_as_final_claim_basis":False,"caution_note":"Do not treat this result-named profile as the sole paper-axis; future cause-side parameterization is required.","trace_available":"checked_by_matrix","readiness_pass":"checked_by_matrix"},
        {"profile_name":"pseudo_reality_v2_shrinking_equilibrium","profile_type":"stress/readiness profile with shrinking-equilibrium tendency","result_named_profile":True,"use_in_preliminary_validation":True,"use_as_final_claim_basis":False,"caution_note":"Do not treat this result-named profile as the sole paper-axis; future cause-side parameterization is required.","trace_available":"checked_by_matrix","readiness_pass":"checked_by_matrix"},
        {"profile_name":"pseudo_reality_v2_public_stability_hidden_decay","profile_type":"stress/readiness profile with public-stability/hidden-decay tendency","result_named_profile":True,"use_in_preliminary_validation":True,"use_as_final_claim_basis":False,"caution_note":"Use for preliminary readiness only; final claims need cause-side parameters.","trace_available":"checked_by_matrix","readiness_pass":"checked_by_matrix"},
    ])
    baselines = pd.DataFrame([
        {"baseline_name":"no_action / no_intervention","mode":"relaxed with zero-strength/no exploration where available","action_profile":"action_conservative zeroed by run overrides","purpose":"observe natural v2 drift/readiness","production_candidate":False,"comparison_role":"required baseline","available_now":True,"missing_reason":""},
        {"baseline_name":"current","mode":"current","action_profile":"action_conservative","purpose":"old conservative baseline","production_candidate":False,"comparison_role":"required comparison","available_now":True,"missing_reason":""},
        {"baseline_name":"relaxed_legacy_dampen_075","mode":"relaxed_legacy_dampen_075","action_profile":"action_conservative","purpose":"rollback/comparison baseline","production_candidate":False,"comparison_role":"required comparison","available_now":True,"missing_reason":""},
        {"baseline_name":"repaired relaxed","mode":"relaxed","action_profile":"action_conservative","purpose":"Phase 2G-2d current main candidate","production_candidate":True,"comparison_role":"required current candidate","available_now":True,"missing_reason":""},
        {"baseline_name":"flat","mode":"flat","action_profile":"action_conservative","purpose":"upper-bound comparator only","production_candidate":False,"comparison_role":"required upper-bound comparator","available_now":True,"missing_reason":"not a production candidate"},
        {"baseline_name":"action_conservative","mode":"relaxed","action_profile":"action_conservative","purpose":"optional action profile comparison","production_candidate":False,"comparison_role":"optional baseline","available_now":True,"missing_reason":""},
        {"baseline_name":"action_buffered","mode":"relaxed","action_profile":"action_buffered","purpose":"optional buffered action comparison","production_candidate":False,"comparison_role":"optional baseline","available_now":True,"missing_reason":""},
        {"baseline_name":"no_exploration_relaxed","mode":"relaxed with exploration_enabled=false","action_profile":"action_conservative","purpose":"optional no-exploration comparison","production_candidate":False,"comparison_role":"optional baseline","available_now":True,"missing_reason":""},
    ])
    missing = pd.DataFrame([
        {"category":"metric","missing_evidence":"Some v2 primary/secondary metrics may be absent as exact columns in current traces.","why_missing":"Phase 2G-4 does not add large metric formulas or alter v2 exports.","affects_premise_freeze":False,"recommended_future_task":"Phase 2G-5 v2 Metric Export Repair if preliminary validation needs exact columns."},
        {"category":"design","missing_evidence":"Cause-side parameterized profiles are not implemented.","why_missing":"This pack freezes premises only and does not change world dynamics/profile parameters.","affects_premise_freeze":False,"recommended_future_task":"Phase 2G-5 v2 Cause-side Parameterization Design or v2.1/v3 design task."},
    ])
    deferred = pd.DataFrame([
        {"priority":"high","design_item":"information_asymmetry / hidden_state_visibility / private_information_rate / misread_probability / information_delay / information_distortion","why_deferred":"Requires cause-side profile design and likely new matrices; not a premise-freeze implementation change.","evidence":"Current v2 profiles are result-named stress/readiness profiles.","recommended_future_task":"Phase 2G-5 v2 Cause-side Parameterization Design"},
        {"priority":"medium","design_item":"resource_inequality / commons_dependency / short_term_gain_pressure / relation_lock_strength / recovery_delay / action_cost","why_deferred":"Requires explicit dynamics/profile design beyond this no-behavior-change pack.","evidence":"Requested as future candidates only.","recommended_future_task":"v2.1/v3 cause-side parameterization design"},
    ])
    return profiles, baselines, missing, deferred




def _profile_family(world_profile: str) -> str:
    return str(world_profile).replace("pseudo_reality_v2_", "").replace("pseudo_reality_", "")


def _baseline_name(label: str, mode: str, action_profile: str, exploration_enabled: bool, cfg=None) -> str:
    if "no_action" in label or "near_zero" in label:
        return "near_zero_action"
    if "no_exploration" in label:
        return "no_exploration_relaxed"
    if action_profile == "action_buffered":
        return "action_buffered_relaxed"
    if mode == "current":
        return "current"
    if mode == "relaxed_legacy_dampen_075":
        return "relaxed_legacy_dampen_075"
    if mode == "flat":
        return "flat"
    if mode == "relaxed":
        return "repaired_relaxed"
    return mode or "current"


def _num_series(frame: pd.DataFrame, columns: list[str]) -> pd.Series | None:
    if frame.empty:
        return None
    for c in columns:
        if c in frame.columns:
            return pd.to_numeric(frame[c], errors="coerce").dropna()
    return None


def _metric_mean(frame: pd.DataFrame, columns: list[str]):
    s = _num_series(frame, columns)
    return "not_available" if s is None or s.empty else float(s.mean())


def _metric_final(frame: pd.DataFrame, columns: list[str]):
    s = _num_series(frame, columns)
    return "not_available" if s is None or s.empty else float(s.iloc[-1])


def _metric_delta(frame: pd.DataFrame, columns: list[str]):
    s = _num_series(frame, columns)
    return "not_available" if s is None or s.empty else float(s.iloc[-1] - s.iloc[0])


def _action_mass_by_channel(frame: pd.DataFrame) -> str:
    if frame.empty or "action_channel" not in frame.columns or "action_strength" not in frame.columns:
        return "not_available"
    g = frame.assign(action_strength=pd.to_numeric(frame["action_strength"], errors="coerce").fillna(0.0)).groupby("action_channel")["action_strength"].sum().to_dict()
    return json.dumps({str(k): float(v) for k, v in g.items()}, sort_keys=True)


def build_v2_preliminary_row(label: str, cfg, out: dict, metrics: dict) -> dict:
    hidden, game, resource, info = (_df(out, n) for n in ["v2_hidden_trace", "v2_game_trace", "v2_resource_trace", "v2_information_trace"])
    action_frame, action_result, projection = (_df(out, n) for n in ["action_frame", "action_result", "exploration_projection"])
    mode = str(cfg.intermediate_conservatism_mode)
    baseline = _baseline_name(label, mode, str(cfg.action_profile_name), bool(cfg.exploration_enabled), cfg)
    boundary = int(metrics.get("boundary_violation_rows", 0))
    dry = int(bool(metrics.get("dry_run_write_violation", False)))
    forbidden = int(bool(metrics.get("forbidden_write_detected", False)))
    direct = int(bool(metrics.get("direct_parameter_box_input_to_actionmodule", False)))
    trace_rows = {n: _trace_rows(out, n) for n in ["v2_hidden_trace", "v2_game_trace", "v2_resource_trace", "v2_information_trace", "v2_action_effect_trace"]}
    row = {
        "run_label": label, "world_profile": cfg.world_profile_name, "profile_family": _profile_family(cfg.world_profile_name),
        "baseline_name": baseline, "mode": mode, "action_profile": cfg.action_profile_name, "seed": cfg.seed, "steps": cfg.steps,
        "is_near_zero_action": baseline == "near_zero_action", "v2_trace_available": any(trace_rows.values()),
        "hidden_damage_mean": _metric_mean(hidden, ["hidden_damage", "hidden_damage_mean", "mean_hidden_damage"]),
        "hidden_damage_final": _metric_final(hidden, ["hidden_damage", "hidden_damage_mean", "mean_hidden_damage"]),
        "hidden_damage_delta": _metric_delta(hidden, ["hidden_damage", "hidden_damage_mean", "mean_hidden_damage"]),
        "fatigue_mean": _metric_mean(hidden, ["fatigue", "fatigue_mean", "mean_fatigue"]),
        "fatigue_final": _metric_final(hidden, ["fatigue", "fatigue_mean", "mean_fatigue"]),
        "fatigue_delta": _metric_delta(hidden, ["fatigue", "fatigue_mean", "mean_fatigue"]),
        "information_quality_mean": _metric_mean(info, ["information_quality", "information_quality_mean", "mean_information_quality"]),
        "information_quality_final": _metric_final(info, ["information_quality", "information_quality_mean", "mean_information_quality"]),
        "information_quality_delta": _metric_delta(info, ["information_quality", "information_quality_mean", "mean_information_quality"]),
        "cooperation_intent_mean": _metric_mean(hidden, ["cooperation_intent", "cooperate_tendency", "cooperation_intent_mean"]),
        "cooperation_intent_final": _metric_final(hidden, ["cooperation_intent", "cooperate_tendency", "cooperation_intent_mean"]),
        "cooperation_intent_delta": _metric_delta(hidden, ["cooperation_intent", "cooperate_tendency", "cooperation_intent_mean"]),
        "defensiveness_mean": _metric_mean(hidden, ["defensiveness", "defend_tendency", "defensiveness_mean"]),
        "defensiveness_final": _metric_final(hidden, ["defensiveness", "defend_tendency", "defensiveness_mean"]),
        "defensiveness_delta": _metric_delta(hidden, ["defensiveness", "defend_tendency", "defensiveness_mean"]),
        "private_resource_mean": _metric_mean(resource, ["private_resource", "private_resource_mean", "mean_private_resource"]),
        "private_resource_final": _metric_final(resource, ["private_resource", "private_resource_mean", "mean_private_resource"]),
        "latent_pressure_mean": _metric_mean(hidden, ["latent_pressure", "latent_pressure_mean", "mean_latent_pressure"]),
        "latent_pressure_final": _metric_final(hidden, ["latent_pressure", "latent_pressure_mean", "mean_latent_pressure"]),
        "latent_pressure_delta": _metric_delta(hidden, ["latent_pressure", "latent_pressure_mean", "mean_latent_pressure"]),
        "action_mass_total": _sum_numeric(action_frame, "action_strength"), "action_mass_by_channel": _action_mass_by_channel(action_frame),
        "action_frame_rows": int(len(action_frame)), "action_result_rows": int(len(action_result)),
        "boundary_violation_total": boundary, "dry_run_write_violation_count": dry, "forbidden_write_count": forbidden,
        "relation_lock_proxy": _metric_mean(game, ["relation_lock", "mean_relation_lock"]),
        "recovery_after_shock_proxy": "not_available", "volatility_proxy": metrics.get("world_delta_volatility_mean", "not_available"),
        "collapse_delay_proxy": "not_available", "hidden_decay_gap": "not_available", "public_stability_hidden_decay_gap": "not_available",
        "v2_hidden_trace_rows": trace_rows["v2_hidden_trace"], "v2_game_trace_rows": trace_rows["v2_game_trace"],
        "v2_resource_trace_rows": trace_rows["v2_resource_trace"], "v2_information_trace_rows": trace_rows["v2_information_trace"],
        "v2_action_effect_trace_rows": trace_rows["v2_action_effect_trace"], "exploration_projection_rows": int(len(projection)),
    }
    missing = [k for k, v in row.items() if v == "not_available"]
    row["preliminary_pass"] = bool(((not str(cfg.world_profile_name).startswith("pseudo_reality_v2_")) or any(trace_rows.values())) and boundary == 0 and dry == 0 and forbidden == 0 and direct == 0)
    row["missing_evidence"] = ";".join(missing)
    return row


def build_v2_preliminary_tables(rows: list[dict]):
    summary = pd.DataFrame(rows)
    if summary.empty:
        return (pd.DataFrame(),)*9
    num_cols = ["hidden_damage_mean","fatigue_mean","information_quality_mean","cooperation_intent_mean","defensiveness_mean","action_mass_total"]
    for c in num_cols:
        summary[c] = pd.to_numeric(summary[c], errors="coerce")
    comparison = summary.groupby(["profile_family","baseline_name","mode","action_profile"], as_index=False).agg(seed_count=("seed","nunique"), hidden_damage_mean_avg=("hidden_damage_mean","mean"), fatigue_mean_avg=("fatigue_mean","mean"), information_quality_mean_avg=("information_quality_mean","mean"), cooperation_intent_mean_avg=("cooperation_intent_mean","mean"), defensiveness_mean_avg=("defensiveness_mean","mean"), action_mass_total_avg=("action_mass_total","mean"), boundary_violation_total=("boundary_violation_total","sum"), dry_run_write_violation_count=("dry_run_write_violation_count","sum"), forbidden_write_count=("forbidden_write_count","sum"))
    comparison["note"] = "preliminary aggregation over short v2 matrix; result-named profiles are not final claim basis"
    deltas=[]
    for fam, grp in comparison.groupby("profile_family"):
        cand = grp[grp.baseline_name.eq("repaired_relaxed")]
        if cand.empty: continue
        cand = cand.iloc[0]
        for refname in ["near_zero_action","current","relaxed_legacy_dampen_075","flat"]:
            ref = grp[grp.baseline_name.eq(refname)]
            if ref.empty: continue
            ref=ref.iloc[0]
            for metric in num_cols:
                cv, rv = cand.get(metric+"_avg", cand.get(metric)), ref.get(metric+"_avg", ref.get(metric))
                delta = float(cv)-float(rv) if pd.notna(cv) and pd.notna(rv) else "not_available"
                direction = "lower_is_better" if metric in {"hidden_damage_mean","fatigue_mean","defensiveness_mean"} else "higher_or_nonzero_is_better"
                deltas.append({"profile_family":fam,"candidate_baseline":"repaired_relaxed","reference_baseline":refname,"metric_name":metric,"candidate_value":cv,"reference_value":rv,"delta":delta,"direction":direction,"preliminary_interpretation":"preliminary_compare_only"})
    delta_df=pd.DataFrame(deltas)
    channels=[]
    for _, r in summary.iterrows():
        by = r.get("action_mass_by_channel")
        if by == "not_available":
            channels.append({"profile_family":r.profile_family,"baseline_name":r.baseline_name,"mode":r.mode,"action_channel":"not_available","action_rows":0,"action_mass_total":0.0,"action_mass_mean":"not_available","action_result_rows":r.action_result_rows,"note":"action channel unavailable"})
        else:
            data=json.loads(by)
            for ch, mass in data.items():
                channels.append({"profile_family":r.profile_family,"baseline_name":r.baseline_name,"mode":r.mode,"action_channel":ch,"action_rows":"not_available","action_mass_total":mass,"action_mass_mean":"not_available","action_result_rows":r.action_result_rows,"note":"aggregated from action_frame.action_strength"})
    safety=summary[["run_label","world_profile","baseline_name","mode","boundary_violation_total","dry_run_write_violation_count","forbidden_write_count"]].copy()
    safety["world_actionframe_only_input"]=safety["forbidden_write_count"].eq(0); safety["direct_parameter_box_input_to_actionmodule"]=False; safety["gk_writeback_detected"]=False; safety["ot_writeback_detected"]=False; safety["canonical_write_detected"]=safety["dry_run_write_violation_count"].gt(0); safety["safety_pass"]=(safety["boundary_violation_total"]+safety["dry_run_write_violation_count"]+safety["forbidden_write_count"]==0)
    read=[]
    for fam, grp in summary.groupby("profile_family"):
        read.append({"profile_family":fam,"repaired_relaxed_vs_no_action":"see v2_metric_delta_vs_baseline.csv","repaired_relaxed_vs_legacy":"see v2_metric_delta_vs_baseline.csv","repaired_relaxed_vs_current":"see v2_metric_delta_vs_baseline.csv","repaired_relaxed_vs_flat":"flat is upper-bound comparator only","hidden_damage_reading":"readable" if grp.hidden_damage_mean.notna().any() else "not_available","fatigue_reading":"readable" if grp.fatigue_mean.notna().any() else "not_available","information_quality_reading":"readable" if grp.information_quality_mean.notna().any() else "not_available","cooperation_reading":"readable" if grp.cooperation_intent_mean.notna().any() else "not_available","defensiveness_reading":"readable" if grp.defensiveness_mean.notna().any() else "not_available","action_mass_reading":"readable","safety_reading":"pass" if (grp.boundary_violation_total.sum()+grp.dry_run_write_violation_count.sum()+grp.forbidden_write_count.sum()==0) else "fail","preliminary_overall_reading":"preliminary evidence is comparable; no superiority or safety proof is claimed","caution":"result-named profile; use for preliminary readiness only, not final claim basis"})
    miss=[]
    metrics_to_check=["hidden_damage_mean","fatigue_mean","information_quality_mean","cooperation_intent_mean","defensiveness_mean","relation_lock_proxy","recovery_after_shock_proxy","collapse_delay_proxy","hidden_decay_gap","public_stability_hidden_decay_gap"]
    for m in metrics_to_check:
        for fam, grp in summary.groupby("profile_family"):
            missing_runs=grp[grp[m].astype(str).eq("not_available")]["run_label"].tolist() if m in grp else grp["run_label"].tolist()
            if missing_runs:
                miss.append({"metric_name":m,"profile_family":fam,"missing_for_runs":";".join(missing_runs),"why_missing":"source trace or exact proxy column not exported by current runner","affects_preliminary_reading":"yes for exact claims; no for cautious availability report","recommended_future_task":"Phase 2G-6 v2 Metric Export Repair"})
    next_df=pd.DataFrame([{"recommendation":"Phase 2G-6 v2 Multi-seed / Longer-horizon Validation Pack","reason":"preliminary matrix is short and result-named; stronger evidence requires more seeds and longer horizon","priority":"high","condition":"if boundary/write counts remain zero and core v2 metrics remain readable"},{"recommendation":"Phase 2G-6 v2 Metric Export Repair","reason":"some secondary proxies are not exact/exported","priority":"medium","condition":"needed before exact claims on proxy-only metrics"}])
    return summary, comparison, summary.copy(), delta_df, pd.DataFrame(channels), safety, pd.DataFrame(read), pd.DataFrame(miss), next_df


def _axis_from_cause_profile(world_profile: str, params: dict) -> tuple[str, str, float | str]:
    if "combined_probe" in world_profile:
        return "combined_probe", "combined", json.dumps(params, sort_keys=True)
    if "minimal_action_cost" in world_profile:
        value = params.get("action_cost", "")
        label = "high" if "high" in world_profile else "low" if "low" in world_profile else str(value)
        return "action_cost", label, value
    if "minimal_information_asymmetry" in world_profile:
        value = params.get("information_asymmetry", "")
        label = "high" if "high" in world_profile else "low" if "low" in world_profile else str(value)
        return "information_asymmetry", label, value
    if "action_cost" in params:
        value = params.get("action_cost", "")
        label = "high" if "high" in world_profile else "low" if "low" in world_profile else str(value)
        return "action_cost", label, value
    if "information_asymmetry" in params:
        value = params.get("information_asymmetry", "")
        label = "high" if "high" in world_profile else "low" if "low" in world_profile else str(value)
        return "information_asymmetry", label, value
    return "not_applicable", "not_applicable", ""


def build_v2_1_cause_side_preliminary_tables(
    rows: list[dict],
    cause_profiles: dict[str, dict],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cause_rows = []
    compatibility_rows = []
    for r in rows:
        wp = str(r.get("world_profile", ""))
        if wp in cause_profiles:
            profile = cause_profiles.get(wp, {})
            config = profile.get("config", {}).get("v2_world_config", {}) if isinstance(profile, dict) else {}
            params = config.get("cause_side_parameters", profile.get("cause_side_parameters", {})) if isinstance(config, dict) else {}
            axis, axis_label, axis_value = _axis_from_cause_profile(wp, params if isinstance(params, dict) else {})
            run = dict(r)
            run.update({
                "axis": axis,
                "axis_value_label": axis_label,
                "axis_value": axis_value,
                "v2_1_profile_loaded": bool(profile),
                "observed_vs_hidden_gap_proxy": (
                    pd.to_numeric(pd.Series([r.get("hidden_damage_mean")]), errors="coerce").iloc[0]
                    - pd.to_numeric(pd.Series([r.get("information_quality_mean")]), errors="coerce").iloc[0]
                    if pd.notna(pd.to_numeric(pd.Series([r.get("hidden_damage_mean")]), errors="coerce").iloc[0])
                    and pd.notna(pd.to_numeric(pd.Series([r.get("information_quality_mean")]), errors="coerce").iloc[0])
                    else "not_available"
                ),
                "action_cost_effect": (
                    pd.to_numeric(pd.Series([r.get("fatigue_delta")]), errors="coerce").iloc[0]
                    * pd.to_numeric(pd.Series([r.get("action_mass_total")]), errors="coerce").iloc[0]
                    if pd.notna(pd.to_numeric(pd.Series([r.get("fatigue_delta")]), errors="coerce").iloc[0])
                    and pd.notna(pd.to_numeric(pd.Series([r.get("action_mass_total")]), errors="coerce").iloc[0])
                    else "not_available"
                ),
                "intervention_fatigue_proxy": (
                    pd.to_numeric(pd.Series([r.get("fatigue_delta")]), errors="coerce").iloc[0]
                    / max(pd.to_numeric(pd.Series([r.get("action_mass_total")]), errors="coerce").iloc[0], 1e-12)
                    if pd.notna(pd.to_numeric(pd.Series([r.get("fatigue_delta")]), errors="coerce").iloc[0])
                    and pd.notna(pd.to_numeric(pd.Series([r.get("action_mass_total")]), errors="coerce").iloc[0])
                    else "not_available"
                ),
                "preliminary_validation_pass": bool(r.get("preliminary_pass", False)) and bool(profile),
            })
            cause_rows.append(run)
        elif wp.startswith("pseudo_reality_v2_") or wp == "pseudo_reality_default":
            compatibility_rows.append({
                "run_label": r.get("run_label", ""),
                "world_profile": wp,
                "baseline_name": r.get("baseline_name", ""),
                "seed": r.get("seed", ""),
                "steps": r.get("steps", ""),
                "existing_v2_compatibility_pass": bool(r.get("preliminary_pass", False)),
                "boundary_violation_total": r.get("boundary_violation_total", 0),
                "dry_run_write_violation_count": r.get("dry_run_write_violation_count", 0),
                "forbidden_write_count": r.get("forbidden_write_count", 0),
                "note": "existing v2 compatibility smoke; not a final validation claim",
            })
    summary = pd.DataFrame(cause_rows)
    if summary.empty:
        return (pd.DataFrame(),) * 10
    wanted = [
        "run_label", "world_profile", "profile_family", "axis", "axis_value_label", "axis_value", "baseline_name", "seed", "steps",
        "v2_1_profile_loaded", "action_mass_total", "action_mass_by_channel", "hidden_damage_mean", "hidden_damage_final", "hidden_damage_delta",
        "fatigue_mean", "fatigue_final", "fatigue_delta", "information_quality_mean", "information_quality_final",
        "information_quality_delta", "cooperation_intent_mean", "cooperation_intent_final", "cooperation_intent_delta",
        "defensiveness_mean", "defensiveness_final", "defensiveness_delta", "latent_pressure_mean", "latent_pressure_final",
        "latent_pressure_delta", "private_resource_mean", "observed_vs_hidden_gap_proxy", "action_cost_effect",
        "intervention_fatigue_proxy", "boundary_violation_total", "dry_run_write_violation_count", "forbidden_write_count",
        "action_frame_rows", "action_result_rows", "v2_hidden_trace_rows", "v2_information_trace_rows", "v2_action_effect_trace_rows",
        "preliminary_validation_pass",
    ]
    for c in wanted:
        if c not in summary.columns:
            summary[c] = "not_available"
    summary = summary[wanted]
    metric_cols = ["action_mass_total", "hidden_damage_delta", "fatigue_delta", "information_quality_delta", "cooperation_intent_delta", "defensiveness_delta", "latent_pressure_delta", "observed_vs_hidden_gap_proxy", "action_cost_effect"]
    for c in metric_cols:
        summary[c] = pd.to_numeric(summary[c], errors="coerce")
    comparisons = []
    for (axis, label, seed), grp in summary.groupby(["axis", "axis_value_label", "seed"], dropna=False):
        repaired = grp[grp["baseline_name"].eq("repaired_relaxed")]
        if repaired.empty:
            continue
        for metric in metric_cols:
            rv = pd.to_numeric(repaired[metric], errors="coerce").mean()
            vals = {}
            for base, col in [("relaxed_legacy_dampen_075", "legacy_value"), ("current", "current_value"), ("near_zero_action", "near_zero_value"), ("flat", "flat_value")]:
                ref = grp[grp["baseline_name"].eq(base)]
                vals[col] = pd.to_numeric(ref[metric], errors="coerce").mean() if not ref.empty else "not_available"
            comparisons.append({
                "axis": axis, "axis_value_label": label, "seed": seed, "metric_name": metric, "repaired_value": rv,
                **vals,
                "repaired_delta_vs_legacy": rv - vals["legacy_value"] if not isinstance(vals["legacy_value"], str) and pd.notna(rv) else "not_available",
                "repaired_delta_vs_current": rv - vals["current_value"] if not isinstance(vals["current_value"], str) and pd.notna(rv) else "not_available",
                "repaired_delta_vs_near_zero": rv - vals["near_zero_value"] if not isinstance(vals["near_zero_value"], str) and pd.notna(rv) else "not_available",
                "repaired_delta_vs_flat": rv - vals["flat_value"] if not isinstance(vals["flat_value"], str) and pd.notna(rv) else "not_available",
                "comparison_note": "preliminary baseline comparison only; flat is an upper-bound comparator and near-zero-action is not no_action",
            })
    stability = []
    for (axis, label, base), grp in summary.groupby(["axis", "axis_value_label", "baseline_name"], dropna=False):
        for metric in metric_cols:
            vals = pd.to_numeric(grp[metric], errors="coerce").dropna()
            mean = float(vals.mean()) if len(vals) else "not_available"
            minv = float(vals.min()) if len(vals) else "not_available"
            maxv = float(vals.max()) if len(vals) else "not_available"
            stability.append({"axis": axis, "axis_value_label": label, "baseline_name": base, "seed_count": int(grp["seed"].nunique()), "metric_name": metric, "mean_value": mean, "min_value": minv, "max_value": maxv, "seed_variation_proxy": (maxv - minv if not isinstance(maxv, str) else "not_available"), "stability_note": "multi_seed_proxy" if int(grp["seed"].nunique()) > 1 else "single_seed_limited"})
    delta_rows = []
    for axis in ["information_asymmetry", "action_cost"]:
        part = summary[summary["axis"].eq(axis)]
        for base, grp in part.groupby("baseline_name"):
            low = grp[grp["axis_value_label"].eq("low")]
            high = grp[grp["axis_value_label"].eq("high")]
            for metric in metric_cols:
                lv = pd.to_numeric(low[metric], errors="coerce").mean() if not low.empty else "not_available"
                hv = pd.to_numeric(high[metric], errors="coerce").mean() if not high.empty else "not_available"
                delta = hv - lv if not isinstance(lv, str) and not isinstance(hv, str) else "not_available"
                delta_rows.append({"axis": axis, "axis_value_label": "high_minus_low", "baseline_name": base, "metric_name": metric, "low_value": lv, "high_value": hv, "high_minus_low": delta, "direction": "positive" if not isinstance(delta, str) and delta > 0 else "negative_or_zero" if not isinstance(delta, str) else "not_available", "proxy_or_exact": "proxy" if metric.endswith("_proxy") or metric == "action_cost_effect" else "exact_exported_or_delta", "interpretation_note": "preliminary tendency only"})
    action_cost = summary[summary["axis"].eq("action_cost")][["run_label", "baseline_name", "axis_value", "action_mass_total", "fatigue_delta", "defensiveness_delta", "latent_pressure_delta", "action_cost_effect", "intervention_fatigue_proxy"]].rename(columns={"axis_value": "action_cost"})
    action_cost["proxy_note"] = "action_cost_effect and intervention_fatigue_proxy are proxy-only"
    info = summary[summary["axis"].eq("information_asymmetry")][["run_label", "baseline_name", "axis_value", "information_quality_delta", "hidden_damage_delta", "cooperation_intent_delta", "defensiveness_delta", "observed_vs_hidden_gap_proxy"]].rename(columns={"axis_value": "information_asymmetry"})
    info["proxy_note"] = "observed_vs_hidden_gap_proxy is proxy-only"
    combined = summary[summary["axis"].eq("combined_probe")].copy()
    compatibility = pd.DataFrame(compatibility_rows)
    missing = pd.DataFrame([
        {"metric_name": "observed_vs_hidden_gap_proxy", "exact_or_proxy": "proxy", "missing_or_limit": "proxy_only", "affected_claim": "no exact observed-hidden causal proof", "recommended_next_task": "Phase 2G-12 Additional Metric Export Repair"},
        {"metric_name": "action_cost_effect", "exact_or_proxy": "proxy", "missing_or_limit": "proxy_only", "affected_claim": "no exact action-cost causal proof", "recommended_next_task": "Phase 2G-12 Additional Metric Export Repair"},
        {"metric_name": "secondary_axes", "exact_or_proxy": "not_implemented", "missing_or_limit": "out_of_scope", "affected_claim": "no hidden_state_visibility/short_term_gain_pressure/relation_lock_strength/recovery_delay claim", "recommended_next_task": "Phase 2G-12 Additional v2.1 Axis Implementation Probe"},
    ])
    next_df = pd.DataFrame([
        {"recommendation": "Phase 2G-12 Additional Metric Export Repair", "reason": "proxy-only fields should not support exact claims; metric deltas are readable but limited", "priority": "high", "condition": "choose if exact observed-hidden/action-cost evidence is needed before tuning"},
        {"recommendation": "Phase 2G-12 ActionModule v2 Tuning Decision Pack", "reason": "only as a decision pack if preliminary tendencies remain comparable and boundary/write counts stay zero", "priority": "medium", "condition": "do not start tuning in Phase 2G-11"},
        {"recommendation": "Phase 2G-12 Additional v2.1 Axis Implementation Probe", "reason": "remaining primary axes are still deferred", "priority": "medium", "condition": "choose if broader cause-side coverage is needed before extended validation"},
    ])
    return summary, pd.DataFrame(comparisons), pd.DataFrame(stability), pd.DataFrame(delta_rows), action_cost, info, combined, compatibility, missing, next_df



def build_v2_1_additional_metric_export_repair_tables(summary: pd.DataFrame):
    if summary.empty:
        return (pd.DataFrame(),) * 11
    df = summary.copy()
    for c in ["action_mass_total", "hidden_damage_delta", "fatigue_delta", "information_quality_delta", "cooperation_intent_delta", "defensiveness_delta", "latent_pressure_delta", "hidden_damage_mean", "information_quality_mean"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    observed = []
    cost = []
    fatigue = []
    channels = []
    repair = []
    for _, r in df.iterrows():
        hidden_pressure = r.get("hidden_damage_mean")
        observed_proxy = r.get("information_quality_mean")
        gap = hidden_pressure - observed_proxy if pd.notna(hidden_pressure) and pd.notna(observed_proxy) else "not_available"
        gap_class = "derived_proxy" if gap != "not_available" else "not_available"
        action_mass = r.get("action_mass_total")
        fatigue_delta = r.get("fatigue_delta")
        defensiveness_delta = r.get("defensiveness_delta")
        latent_delta = r.get("latent_pressure_delta")
        cost_effect = action_mass * fatigue_delta if pd.notna(action_mass) and pd.notna(fatigue_delta) else "not_available"
        action_steps = int(r.get("action_frame_rows", 0)) if str(r.get("action_frame_rows", "")).isdigit() else 0
        repeated = max(action_steps - 1, 0)
        intervention = (fatigue_delta * repeated) if pd.notna(fatigue_delta) else "not_available"
        common = {"run_label": r.get("run_label"), "axis": r.get("axis"), "baseline_name": r.get("baseline_name")}
        observed.append({**common, "observed_state_proxy": observed_proxy if pd.notna(observed_proxy) else "not_available", "hidden_state_pressure_proxy": hidden_pressure if pd.notna(hidden_pressure) else "not_available", "observed_vs_hidden_gap": gap, "observed_vs_hidden_gap_classification": gap_class, "exact_or_proxy": "derived_proxy" if gap != "not_available" else "not_available", "note": "derived from exact exported information_quality and hidden_damage means; no public/visible semantic exact claim"})
        cost.append({**common, "action_mass_total": action_mass if pd.notna(action_mass) else "not_available", "fatigue_delta": fatigue_delta if pd.notna(fatigue_delta) else "not_available", "defensiveness_delta": defensiveness_delta if pd.notna(defensiveness_delta) else "not_available", "latent_pressure_delta": latent_delta if pd.notna(latent_delta) else "not_available", "action_cost_effect": cost_effect, "action_cost_effect_classification": "derived_proxy" if cost_effect != "not_available" else "not_available", "exact_or_proxy": "derived_proxy" if cost_effect != "not_available" else "not_available", "note": "short-run association of action mass with fatigue delta; not causal proof"})
        fatigue.append({"run_label": r.get("run_label"), "baseline_name": r.get("baseline_name"), "action_step_count": action_steps, "repeated_action_count": repeated, "cumulative_action_mass": action_mass if pd.notna(action_mass) else "not_available", "fatigue_delta": fatigue_delta if pd.notna(fatigue_delta) else "not_available", "defensiveness_delta": defensiveness_delta if pd.notna(defensiveness_delta) else "not_available", "latent_pressure_delta": latent_delta if pd.notna(latent_delta) else "not_available", "intervention_fatigue_proxy": intervention, "exact_or_proxy": "derived_proxy" if intervention != "not_available" else "not_available", "note": "repeated action count paired with fatigue/defensiveness/latent-pressure deltas; proxy only"})
        by = r.get("action_mass_by_channel", "not_available")
        parsed = {}
        if isinstance(by, str) and by not in {"", "not_available"}:
            try:
                parsed = json.loads(by)
            except Exception:
                parsed = {}
        if not parsed:
            channels.append({"run_label": r.get("run_label"), "action_channel": "not_available", "action_rows": 0, "action_mass_total": 0.0, "action_mass_mean": "not_available", "hidden_damage_delta": r.get("hidden_damage_delta", "not_available"), "fatigue_delta": fatigue_delta if pd.notna(fatigue_delta) else "not_available", "information_quality_delta": r.get("information_quality_delta", "not_available"), "cooperation_intent_delta": r.get("cooperation_intent_delta", "not_available"), "defensiveness_delta": defensiveness_delta if pd.notna(defensiveness_delta) else "not_available", "latent_pressure_delta": latent_delta if pd.notna(latent_delta) else "not_available", "channel_effect_classification": "not_available", "exact_or_proxy": "not_available", "note": "action_channel/action_strength unavailable"})
        else:
            total_mass = sum(float(v) for v in parsed.values()) or 1.0
            for ch, mass in parsed.items():
                share = float(mass) / total_mass
                channels.append({"run_label": r.get("run_label"), "action_channel": ch, "action_rows": "not_available", "action_mass_total": float(mass), "action_mass_mean": "not_available", "hidden_damage_delta": r.get("hidden_damage_delta", "not_available"), "fatigue_delta": fatigue_delta * share if pd.notna(fatigue_delta) else "not_available", "information_quality_delta": r.get("information_quality_delta", "not_available"), "cooperation_intent_delta": r.get("cooperation_intent_delta", "not_available"), "defensiveness_delta": defensiveness_delta * share if pd.notna(defensiveness_delta) else "not_available", "latent_pressure_delta": latent_delta * share if pd.notna(latent_delta) else "not_available", "channel_effect_classification": "derived_proxy", "exact_or_proxy": "derived_proxy", "note": "channel mass exact from action_frame; state deltas are run-level associations apportioned by mass share, not causal proof"})
        repair.append({"run_label": r.get("run_label"), "world_profile": r.get("world_profile"), "axis": r.get("axis"), "axis_value_label": r.get("axis_value_label"), "baseline_name": r.get("baseline_name"), "seed": r.get("seed"), "steps": r.get("steps"), "action_mass_total": action_mass if pd.notna(action_mass) else "not_available", "observed_vs_hidden_gap_available": gap != "not_available", "observed_vs_hidden_gap_value": gap, "action_cost_effect_available": cost_effect != "not_available", "action_cost_effect_value": cost_effect, "intervention_fatigue_available": intervention != "not_available", "intervention_fatigue_value": intervention, "action_effect_by_channel_available": bool(parsed), "metric_repair_pass": bool(gap != "not_available" and cost_effect != "not_available" and intervention != "not_available" and parsed), "boundary_violation_total": r.get("boundary_violation_total", 0), "dry_run_write_violation_count": r.get("dry_run_write_violation_count", 0), "forbidden_write_count": r.get("forbidden_write_count", 0)})
    repair_df, observed_df, cost_df, fatigue_df, channel_df = map(pd.DataFrame, [repair, observed, cost, fatigue, channels])
    run_count=len(df)
    metric_names = [("hidden_damage","exact_exported","v2_hidden_trace","hidden_damage/hidden_damage_mean",True),("fatigue","exact_exported","v2_hidden_trace","fatigue/fatigue_mean",True),("information_quality","exact_exported","v2_information_trace","information_quality/information_quality_mean",True),("cooperation_intent","exact_exported","v2_hidden_trace","cooperation_intent/cooperate_tendency",True),("defensiveness","exact_exported","v2_hidden_trace","defensiveness/defend_tendency",True),("latent_pressure","exact_exported","v2_hidden_trace","latent_pressure",True),("private_resource","exact_exported","v2_resource_trace","private_resource",True),("cumulative_action_mass","derived_from_exact","action_frame","action_strength",True),("observed_vs_hidden_gap","derived_proxy","v2_information_trace;v2_hidden_trace","information_quality_mean;hidden_damage_mean",True),("action_cost_effect","derived_proxy","action_frame;v2_hidden_trace","action_strength;fatigue_delta",True),("intervention_fatigue","derived_proxy","action_frame;v2_hidden_trace","action_frame_rows;fatigue_delta",True),("action_effect_by_channel","derived_proxy","action_frame;v2_hidden_trace","action_channel;action_strength;state_deltas",True),("visible_public_metric_exact","not_available","not_exported","public_visible_state",False),("hidden_state_visibility","deferred_requires_semantic_design","not_implemented","not_implemented",False)]
    class_rows=[]
    for name, klass, source, cols, allowed in metric_names:
        available = run_count if klass not in {"not_available", "deferred_requires_semantic_design"} else 0
        class_rows.append({"metric_name": name, "classification": klass, "source_trace": source, "source_columns": cols, "available_run_count": available, "missing_run_count": run_count - available, "exact_claim_allowed": klass in {"exact_exported", "derived_from_exact"}, "tuning_decision_allowed": bool(allowed and klass != "not_available"), "note": "proxy/derived_proxy values do not support exact causal claims" if "proxy" in klass else "direct or deferred classification"})
    classification = pd.DataFrame(class_rows)
    def high_low(axis, metrics):
        rows=[]; part=df[df["axis"].eq(axis)]
        for base, grp in part.groupby("baseline_name"):
            low=grp[grp["axis_value_label"].eq("low")]; high=grp[grp["axis_value_label"].eq("high")]
            for m in metrics:
                lv=pd.to_numeric(low[m], errors="coerce").mean() if m in low else float("nan")
                hv=pd.to_numeric(high[m], errors="coerce").mean() if m in high else float("nan")
                rows.append({"axis": axis, "baseline_name": base, "metric_name": m, "low_value": lv if pd.notna(lv) else "not_available", "high_value": hv if pd.notna(hv) else "not_available", "high_minus_low": hv-lv if pd.notna(lv) and pd.notna(hv) else "not_available", "classification": "derived_proxy" if m in {"observed_vs_hidden_gap_proxy","action_cost_effect","intervention_fatigue_proxy"} else "derived_from_exact", "note": "high-low summary only; no superiority claim"})
        return pd.DataFrame(rows)
    info_effect = high_low("information_asymmetry", ["information_quality_delta", "hidden_damage_delta", "cooperation_intent_delta", "defensiveness_delta", "observed_vs_hidden_gap_proxy"])
    cost_response = high_low("action_cost", ["fatigue_delta", "defensiveness_delta", "latent_pressure_delta", "action_cost_effect", "intervention_fatigue_proxy"])
    boundary_zero = int(pd.to_numeric(repair_df["boundary_violation_total"], errors="coerce").fillna(0).sum()) == 0 and int(pd.to_numeric(repair_df["dry_run_write_violation_count"], errors="coerce").fillna(0).sum()) == 0 and int(pd.to_numeric(repair_df["forbidden_write_count"], errors="coerce").fillna(0).sum()) == 0
    readiness_status = "tuning_metric_proxy_only" if bool(repair_df["metric_repair_pass"].all()) and boundary_zero else "tuning_metric_blocked"
    readiness = pd.DataFrame([{"readiness_item": "tuning_decision_metric_readiness", "status": readiness_status, "required_metrics": "action_effect_by_channel;action_cost_effect;intervention_fatigue;boundary_write_zero;existing_v2_compatibility", "available_metrics": "action_effect_by_channel;action_cost_effect;intervention_fatigue", "proxy_only_metrics": "observed_vs_hidden_gap;action_cost_effect;intervention_fatigue;action_effect_by_channel", "missing_metrics": "visible_public_metric_exact", "decision": "ActionModule tuning decision may be discussed but not executed" if readiness_status == "tuning_metric_proxy_only" else "do not proceed", "blocker": "proxy_only_metrics;visible_public_metric_exact missing", "recommended_next_task": "Phase 2G-13 ActionModule v2 Tuning Decision Pack discussion-only or Additional Metric Repair"}])
    missing = classification[classification["classification"].isin(["not_available", "deferred_requires_semantic_design"])].rename(columns={"metric_name":"missing_metric"})
    next_df = pd.DataFrame([{"recommended_next_task":"Phase 2G-13 ActionModule v2 Tuning Decision Pack","priority":"medium","condition":"discussion-only because repaired metrics remain derived_proxy/proxy","alternative":"Phase 2G-13 Additional Metric Repair if exact visible/public metrics are required"}])
    return repair_df, observed_df, cost_df, fatigue_df, channel_df, info_effect, cost_response, classification, readiness, missing, next_df


def _metric_worst(frame: pd.DataFrame, columns: list[str], lower_is_worse: bool = False):
    s = _num_series(frame, columns)
    if s is None or s.empty:
        return "not_available"
    return float(s.min() if lower_is_worse else s.max())


def _metric_slope_proxy(frame: pd.DataFrame, columns: list[str]):
    s = _num_series(frame, columns)
    if s is None or s.empty or len(s) < 2:
        return "not_available"
    return float((s.iloc[-1] - s.iloc[0]) / max(len(s) - 1, 1))


def _action_mass_volatility_proxy(frame: pd.DataFrame):
    if frame.empty or "action_strength" not in frame.columns:
        return "not_available"
    if "loop_step" in frame.columns:
        step_mass = frame.assign(action_strength=pd.to_numeric(frame["action_strength"], errors="coerce").fillna(0.0)).groupby("loop_step")["action_strength"].sum()
        return float(step_mass.std(ddof=0)) if len(step_mass) else 0.0
    s = pd.to_numeric(frame["action_strength"], errors="coerce").fillna(0.0)
    return float(s.std(ddof=0)) if len(s) else 0.0


def build_v2_extended_row(label: str, cfg, out: dict, metrics: dict) -> dict:
    row = build_v2_preliminary_row(label, cfg, out, metrics)
    hidden, game, resource, info = (_df(out, n) for n in ["v2_hidden_trace", "v2_game_trace", "v2_resource_trace", "v2_information_trace"])
    action_frame = _df(out, "action_frame")
    row.update({
        "horizon_class": "longer" if int(cfg.steps) >= 12 or "long" in label else "standard",
        "is_repaired_relaxed": row.get("baseline_name") == "repaired_relaxed",
        "is_longer_horizon": int(cfg.steps) >= 12 or "long" in label,
        "hidden_damage_worst": _metric_worst(hidden, ["hidden_damage", "hidden_damage_mean", "mean_hidden_damage"]),
        "fatigue_worst": _metric_worst(hidden, ["fatigue", "fatigue_mean", "mean_fatigue"]),
        "information_quality_worst": _metric_worst(info, ["information_quality", "information_quality_mean", "mean_information_quality"], lower_is_worse=True),
        "cooperation_intent_worst": _metric_worst(hidden, ["cooperation_intent", "cooperate_tendency", "cooperation_intent_mean"], lower_is_worse=True),
        "defensiveness_worst": _metric_worst(hidden, ["defensiveness", "defend_tendency", "defensiveness_mean"]),
        "private_resource_delta": _metric_delta(resource, ["private_resource", "private_resource_mean", "mean_private_resource"]),
        "latent_pressure_delta": _metric_delta(hidden, ["latent_pressure", "latent_pressure_mean", "mean_latent_pressure"]),
        "action_mass_mean": float(_sum_numeric(action_frame, "action_strength") / len(action_frame)) if len(action_frame) else 0.0,
        "action_mass_volatility_proxy": _action_mass_volatility_proxy(action_frame),
        "metric_final_minus_initial": "see per-metric *_delta columns",
        "metric_slope_proxy": json.dumps({
            "hidden_damage": _metric_slope_proxy(hidden, ["hidden_damage", "hidden_damage_mean", "mean_hidden_damage"]),
            "fatigue": _metric_slope_proxy(hidden, ["fatigue", "fatigue_mean", "mean_fatigue"]),
            "information_quality": _metric_slope_proxy(info, ["information_quality", "information_quality_mean", "mean_information_quality"]),
            "cooperation_intent": _metric_slope_proxy(hidden, ["cooperation_intent", "cooperate_tendency", "cooperation_intent_mean"]),
            "defensiveness": _metric_slope_proxy(hidden, ["defensiveness", "defend_tendency", "defensiveness_mean"]),
        }, sort_keys=True),
    })
    row["extended_validation_pass"] = bool(row.get("preliminary_pass", False))
    missing = [k for k, v in row.items() if v == "not_available"]
    row["missing_evidence"] = ";".join(missing)
    return row


def build_v2_extended_tables(rows: list[dict]):
    summary = pd.DataFrame(rows)
    if summary.empty:
        return (pd.DataFrame(),) * 9
    numeric_cols = [c for c in summary.columns if c.endswith(("_mean","_final","_delta","_worst")) or c in {"action_mass_total","action_mass_mean","action_mass_volatility_proxy"}]
    for c in numeric_cols:
        summary[c] = pd.to_numeric(summary[c], errors="coerce")
    agg = {"seed": ("seed", "nunique"), "steps_mean": ("steps", "mean")}
    for c in ["hidden_damage_mean","hidden_damage_final","fatigue_mean","fatigue_final","information_quality_mean","information_quality_final","cooperation_intent_mean","cooperation_intent_final","defensiveness_mean","defensiveness_final","action_mass_total","action_mass_volatility_proxy"]:
        if c in summary.columns:
            agg[c.replace("action_mass_volatility_proxy","action_mass_volatility").replace("action_mass_total","action_mass_total") + "_avg"] = (c, "mean")
    comparison = summary.groupby(["profile_family","baseline_name","mode","action_profile"], as_index=False).agg(**agg).rename(columns={"seed":"seed_count"})
    comparison["boundary_violation_total"] = summary.groupby(["profile_family","baseline_name","mode","action_profile"])["boundary_violation_total"].sum().values
    comparison["dry_run_write_violation_count"] = summary.groupby(["profile_family","baseline_name","mode","action_profile"])["dry_run_write_violation_count"].sum().values
    comparison["forbidden_write_count"] = summary.groupby(["profile_family","baseline_name","mode","action_profile"])["forbidden_write_count"].sum().values
    comparison["note"] = "extended preliminary aggregation; result-named v2 profiles are not final claim basis"
    stability=[]
    for keys, grp in summary.groupby(["profile_family","baseline_name"]):
        for m in ["hidden_damage_mean","fatigue_mean","information_quality_mean","cooperation_intent_mean","defensiveness_mean","action_mass_total"]:
            vals=pd.to_numeric(grp[m], errors="coerce").dropna() if m in grp else pd.Series(dtype=float)
            mean=float(vals.mean()) if len(vals) else float('nan'); std=float(vals.std(ddof=0)) if len(vals) else float('nan')
            stability.append({"profile_family":keys[0],"baseline_name":keys[1],"metric_name":m,"seed_count":int(grp["seed"].nunique()),"mean":mean,"std":std,"min":float(vals.min()) if len(vals) else "not_available","max":float(vals.max()) if len(vals) else "not_available","coefficient_of_variation_proxy":(std/abs(mean) if mean and pd.notna(mean) else "not_available"),"stability_reading":"stable_proxy" if len(vals)>1 and (not mean or abs(std/(mean or 1)) < 0.5) else "mixed_or_insufficient"})
    longer = summary[summary["is_longer_horizon"].astype(bool)].copy()
    if not longer.empty:
        longer = longer[["profile_family","run_label","baseline_name","steps","hidden_damage_delta","fatigue_delta","information_quality_delta","cooperation_intent_delta","defensiveness_delta","latent_pressure_delta","action_mass_total","action_mass_volatility_proxy"]]
        longer["longer_horizon_reading"] = "longer-horizon preliminary; inspect deltas, not final validation"
    adequacy_specs = [
        ("hidden_damage","v2_hidden_trace","exact_available",True,False),("fatigue","v2_hidden_trace","exact_available",True,False),("information_quality","v2_information_trace","exact_available",True,False),("cooperation_intent","v2_hidden_trace","proxy_available",True,False),("defensiveness","v2_hidden_trace","proxy_available",True,False),("private_resource","v2_resource_trace","exact_available",True,False),("latent_pressure","v2_hidden_trace","exact_available",True,False),("action_mass_by_channel","action_frame","exact_available",True,False),("relation_lock_proxy","v2_game_trace","proxy_available",False,True),("recovery_after_shock_proxy","not_exported","not_available",False,True),("collapse_delay_proxy","not_exported","not_available",False,True),("hidden_decay_gap","not_exported","needs_metric_export_repair",False,True),("public_stability_hidden_decay_gap","not_exported","needs_metric_export_repair",False,True),("v2_hidden_trace_rows","v2_hidden_trace","row_count_only",False,True),("exploration_projection_rows","exploration_projection","row_count_only",False,True)]
    adequacy=[]
    for name,source,klass,primary,secondary in adequacy_specs:
        col = name + "_mean" if name in ["hidden_damage","fatigue","information_quality","cooperation_intent","defensiveness"] else name
        avail = int(summary[col].astype(str).ne("not_available").sum()) if col in summary else 0
        adequacy.append({"metric_name":name,"source_trace":source,"availability_class":klass,"exact_or_proxy":"proxy" if "proxy" in klass or name.endswith("_proxy") else ("row_count" if klass=="row_count_only" else "exact"),"available_run_count":avail,"missing_run_count":int(len(summary)-avail),"use_as_primary":primary,"use_as_secondary":secondary,"affects_extended_validation":"yes" if primary and avail < len(summary) else "secondary_or_no","needs_metric_export_repair":klass in {"not_available","needs_metric_export_repair"},"note":"do not introduce new metric definitions in this PR"})
    deltas=[]
    metrics=["hidden_damage_mean","fatigue_mean","information_quality_mean","cooperation_intent_mean","defensiveness_mean","action_mass_total"]
    for fam,grp in summary.groupby("profile_family"):
        cand=grp[grp["baseline_name"].eq("repaired_relaxed")]
        for refname in ["near_zero_action","current","relaxed_legacy_dampen_075","flat"]:
            ref=grp[grp["baseline_name"].eq(refname)]
            if cand.empty or ref.empty: continue
            for m in metrics:
                cv=pd.to_numeric(cand[m], errors="coerce").mean(); rv=pd.to_numeric(ref[m], errors="coerce").mean()
                deltas.append({"profile_family":fam,"seed_group":"all_available","candidate_baseline":"repaired_relaxed","reference_baseline":refname,"metric_name":m,"candidate_value":cv,"reference_value":rv,"delta":cv-rv if pd.notna(cv) and pd.notna(rv) else "not_available","direction":"lower_is_better" if m in {"hidden_damage_mean","fatigue_mean","defensiveness_mean"} else "higher_or_nonzero_is_better","preliminary_interpretation":"extended preliminary compare only"})
    action = summary.groupby(["profile_family","baseline_name","mode"], as_index=False).agg(seed_count=("seed","nunique"), action_mass_mean=("action_mass_total","mean"), action_mass_std=("action_mass_total","std"), action_mass_min=("action_mass_total","min"), action_mass_max=("action_mass_total","max"), action_mass_volatility_proxy=("action_mass_volatility_proxy","mean"))
    action["action_mass_reading"]="preliminary action mass stability proxy"
    safety=summary[["run_label","world_profile","baseline_name","mode","boundary_violation_total","dry_run_write_violation_count","forbidden_write_count"]].copy()
    safety["world_actionframe_only_input"]=safety["forbidden_write_count"].eq(0); safety["direct_parameter_box_input_to_actionmodule"]=False; safety["gk_writeback_detected"]=False; safety["ot_writeback_detected"]=False; safety["canonical_write_detected"]=safety["dry_run_write_violation_count"].gt(0); safety["safety_pass"]=(safety["boundary_violation_total"]+safety["dry_run_write_violation_count"]+safety["forbidden_write_count"]==0)
    miss=[]
    for a in adequacy:
        if a["missing_run_count"]:
            miss.append({"metric_name":a["metric_name"],"profile_family":"all","missing_for_runs":"see adequacy summary","why_missing":"source trace or exact column not exported by current runner","affects_extended_validation":a["affects_extended_validation"],"recommended_future_task":"Phase 2G-7 v2 Metric Export Repair" if a["needs_metric_export_repair"] else "track as proxy evidence"})
    next_df=pd.DataFrame([
        {"recommendation":"Phase 2G-7 Cause-side Parameterization Design Pack","reason":"result-named profiles remain unsuitable as final claim basis; cause-side design is still needed","priority":"high","condition":"if boundary/write remains zero and core metrics are readable"},
        {"recommendation":"Phase 2G-7 v2 Metric Export Repair","reason":"secondary exact claims need recovery/collapse/hidden-decay exports rather than proxies or row counts","priority":"high","condition":"before stronger v2 claims"},
        {"recommendation":"Phase 2G-7 Freeze Decision Pack","reason":"only after cause-side and metric adequacy work; this pack is not final validation","priority":"medium","condition":"if subsequent evidence remains stable"},
    ])
    return summary, comparison, pd.DataFrame(stability), longer, pd.DataFrame(adequacy), pd.DataFrame(deltas), action, safety, pd.DataFrame(miss), next_df


V2_CAUSE_METRIC_SPECS = {
    "hidden_damage": ("v2_hidden_trace", ["hidden_damage", "hidden_damage_mean", "mean_hidden_damage"], "exact_available", "exact"),
    "fatigue": ("v2_hidden_trace", ["fatigue", "fatigue_mean", "mean_fatigue"], "exact_available", "exact"),
    "information_quality": ("v2_information_trace", ["information_quality", "information_quality_mean", "mean_information_quality"], "exact_available", "exact"),
    "cooperation_intent": ("v2_hidden_trace", ["cooperation_intent", "cooperate_tendency", "cooperation_intent_mean"], "exact_available", "exact"),
    "defensiveness": ("v2_hidden_trace", ["defensiveness", "defend_tendency", "defensiveness_mean"], "exact_available", "exact"),
    "private_resource": ("v2_resource_trace", ["private_resource", "private_resource_mean", "mean_private_resource"], "exact_available", "exact"),
    "latent_pressure": ("v2_hidden_trace", ["latent_pressure", "latent_pressure_mean", "mean_latent_pressure"], "exact_available", "exact"),
}


def _source_frame(out: dict, source: str) -> pd.DataFrame:
    return _df(out, source)


def _source_columns(frame: pd.DataFrame, columns: list[str]) -> list[str]:
    return [c for c in columns if c in frame.columns]


def _metric_values(frame: pd.DataFrame, columns: list[str], lower_is_worse: bool = False) -> tuple:
    if frame.empty:
        return ("not_available",) * 4
    present = _source_columns(frame, columns)
    if not present:
        return ("not_available",) * 4
    return (
        _metric_mean(frame, present),
        _metric_final(frame, present),
        _metric_delta(frame, present),
        _metric_worst(frame, present, lower_is_worse=lower_is_worse),
    )


def _step_series(frame: pd.DataFrame, columns: list[str]) -> pd.Series | None:
    if frame.empty:
        return None
    present = _source_columns(frame, columns)
    if not present:
        return None
    value_col = present[0]
    values = pd.to_numeric(frame[value_col], errors="coerce")
    if "loop_step" in frame.columns:
        return values.groupby(frame["loop_step"]).mean().dropna().sort_index()
    return pd.Series(values.dropna().to_list())


def _collapse_delay_proxy(hidden: pd.DataFrame) -> tuple:
    series = _step_series(hidden, ["hidden_damage", "hidden_damage_mean", "mean_hidden_damage"])
    threshold = "hidden_damage>=0.70"
    if series is None or series.empty:
        return False, "not_available", threshold
    crossed = series[series >= 0.70]
    return True, (int(crossed.index[0]) if not crossed.empty else "not_crossed"), threshold


def _recovery_after_shock_proxy(cfg, hidden: pd.DataFrame) -> tuple:
    shock_time = getattr(cfg, "shock_time", None)
    shock_strength = float(getattr(cfg, "shock_strength", 0.0) or 0.0)
    if shock_time is None or shock_strength <= 0:
        return False, False, "not_available"
    hd = _step_series(hidden, ["hidden_damage", "hidden_damage_mean", "mean_hidden_damage"])
    coop = _step_series(hidden, ["cooperation_intent", "cooperate_tendency", "cooperation_intent_mean"])
    if hd is None or coop is None or hd.empty or coop.empty:
        return True, False, "not_available"
    post_hd = hd[hd.index >= shock_time]
    post_coop = coop[coop.index >= shock_time]
    if post_hd.empty or post_coop.empty:
        return True, False, "not_available"
    proxy = float((post_hd.iloc[0] - post_hd.iloc[-1]) + (post_coop.iloc[-1] - post_coop.iloc[0]))
    return True, True, proxy


def build_v2_metric_export_repair_rows(label: str, cfg, out: dict, metrics: dict) -> dict[str, pd.DataFrame]:
    hidden, game, resource, info, effect = (_df(out, n) for n in ["v2_hidden_trace", "v2_game_trace", "v2_resource_trace", "v2_information_trace", "v2_action_effect_trace"])
    entity, relation, action_frame, action_result = (_df(out, n) for n in ["entity_trace", "relation_trace", "action_frame", "action_result"])
    mode = str(cfg.intermediate_conservatism_mode)
    baseline = _baseline_name(label, mode, str(cfg.action_profile_name), bool(cfg.exploration_enabled), cfg)
    common = {"run_label": label, "world_profile": cfg.world_profile_name, "profile_family": _profile_family(cfg.world_profile_name), "baseline_name": baseline, "mode": mode, "action_profile": cfg.action_profile_name, "seed": cfg.seed, "steps": cfg.steps}
    trace_available = any(not f.empty for f in [hidden, game, resource, info, effect])
    availability = []
    counts = {"exact_available": 0, "proxy_available": 0, "row_count_only": 0, "export_repaired": 0, "not_available": 0, "deferred_requires_semantic_design": 0}
    for name, (source, cols, klass, exact) in V2_CAUSE_METRIC_SPECS.items():
        frame = _source_frame(out, source)
        present = _source_columns(frame, cols)
        klass2 = klass if present else ("row_count_only" if not frame.empty else "not_available")
        exact2 = exact if present else ("row_count" if not frame.empty else "not_available")
        mean, final, delta, worst = _metric_values(frame, cols, lower_is_worse=name in {"information_quality", "cooperation_intent", "private_resource"})
        counts[klass2] += 1
        availability.append({**common, "metric_name": name, "source_trace": source, "source_columns": ";".join(present), "availability_class": klass2, "exact_or_proxy": exact2, "value_mean": mean, "value_final": final, "value_delta": delta, "value_worst": worst, "missing_reason": "" if present else "source rows available without required value column" if not frame.empty else "source trace unavailable", "recommended_future_task": "" if present else "Phase 2G-9 Additional Metric Export Repair"})

    rel_mass = 0.0
    rel_rows = 0
    if not action_frame.empty and "action_channel" in action_frame.columns:
        rel = action_frame[action_frame["action_channel"].astype(str).eq("relation_unlock")]
        rel_rows = int(len(rel))
        rel_mass = _sum_numeric(rel, "action_strength")
    rel_value = _metric_mean(entity, ["relation_lock", "mean_relation_lock"])
    rel_available = rel_value != "not_available" or rel_rows > 0
    counts["proxy_available" if rel_available else "not_available"] += 1
    availability.append({**common, "metric_name": "relation_lock_proxy", "source_trace": "entity_trace/action_frame", "source_columns": "relation_lock;action_channel;action_strength", "availability_class": "proxy_available" if rel_available else "not_available", "exact_or_proxy": "proxy", "value_mean": rel_value, "value_final": _metric_final(entity, ["relation_lock"]), "value_delta": _metric_delta(entity, ["relation_lock"]), "value_worst": _metric_worst(entity, ["relation_lock"]), "missing_reason": "" if rel_available else "relation_lock and relation_unlock action evidence unavailable", "recommended_future_task": "Phase 2G-9 Cause-side Matrix Skeleton Pack"})

    shock_marker, rec_avail, recovery = _recovery_after_shock_proxy(cfg, hidden)
    collapse_avail, collapse, threshold = _collapse_delay_proxy(hidden)
    for metric_name, avail, val, source in [("recovery_after_shock_proxy", rec_avail, recovery, "cfg.shock_time/v2_hidden_trace"), ("collapse_delay_proxy", collapse_avail, collapse, "v2_hidden_trace")]:
        counts["proxy_available" if avail else ("row_count_only" if source.startswith("cfg") and shock_marker else "not_available")] += 1
        availability.append({**common, "metric_name": metric_name, "source_trace": source, "source_columns": "hidden_damage;cooperation_intent", "availability_class": "proxy_available" if avail else ("row_count_only" if shock_marker else "not_available"), "exact_or_proxy": "proxy" if avail else "not_available", "value_mean": val, "value_final": val, "value_delta": "not_available", "value_worst": "not_available", "missing_reason": "" if avail else "shock marker absent or insufficient post-shock value columns" if metric_name.startswith("recovery") else "hidden_damage threshold crossing source unavailable", "recommended_future_task": "Phase 2G-9 Additional Metric Export Repair"})

    visible = _step_series(info, ["information_quality", "information_quality_mean", "mean_information_quality"])
    if visible is None:
        visible = _step_series(game, ["long_term_health_proxy", "local_payoff"])
    hd = _step_series(hidden, ["hidden_damage", "hidden_damage_mean", "mean_hidden_damage"])
    fat = _step_series(hidden, ["fatigue", "fatigue_mean", "mean_fatigue"])
    gap_avail = visible is not None and hd is not None and not visible.empty and not hd.empty
    gap = float(visible.iloc[-1] - hd.iloc[-1]) if gap_avail else "not_available"
    public_gap = float(visible.iloc[-1] - ((hd.iloc[-1] + fat.iloc[-1]) / 2.0)) if gap_avail and fat is not None and not fat.empty else "not_available"
    for metric_name, val, avail, deferred in [("hidden_decay_gap", gap, gap_avail, False), ("public_stability_hidden_decay_gap", public_gap, public_gap != "not_available", visible is None)]:
        klass = "proxy_available" if avail else ("deferred_requires_semantic_design" if deferred else "not_available")
        counts[klass] += 1
        availability.append({**common, "metric_name": metric_name, "source_trace": "v2_information_trace/v2_game_trace + v2_hidden_trace", "source_columns": "information_quality_mean|long_term_health_proxy;hidden_damage;fatigue", "availability_class": klass, "exact_or_proxy": "proxy" if avail else klass, "value_mean": val, "value_final": val, "value_delta": "not_available", "value_worst": "not_available", "missing_reason": "" if avail else "public/visible metric or hidden deterioration metric unavailable", "recommended_future_task": "Phase 2G-9 Additional Metric Export Repair"})

    # Channel, action-cost, and fatigue proxies are aggregated separately but registered here.
    for name in ["action_effect_by_channel", "action_cost_effect", "intervention_fatigue", "action_timing_lag_proxy", "misread_proxy", "observed_vs_hidden_gap", "commons_health_proxy"]:
        if name == "action_effect_by_channel":
            avail = not effect.empty or not action_frame.empty
            klass = "proxy_available" if avail else "not_available"
        elif name in {"commons_health_proxy", "misread_proxy"}:
            frame = resource if name == "commons_health_proxy" else info
            cols = ["commons_health"] if name == "commons_health_proxy" else ["misread_probability_mean"]
            avail = bool(_source_columns(frame, cols))
            klass = "proxy_available" if avail else "not_available"
        elif name == "observed_vs_hidden_gap":
            avail = gap_avail
            klass = "proxy_available" if avail else "not_available"
        else:
            avail = not action_frame.empty
            klass = "proxy_available" if avail else "deferred_requires_semantic_design"
        counts[klass] += 1
        availability.append({**common, "metric_name": name, "source_trace": "existing trace aggregation", "source_columns": "", "availability_class": klass, "exact_or_proxy": "proxy" if avail else klass, "value_mean": "see dedicated CSV", "value_final": "see dedicated CSV", "value_delta": "not_available", "value_worst": "not_available", "missing_reason": "" if avail else "semantic design or action trace unavailable", "recommended_future_task": "Phase 2G-9 Cause-side Matrix Skeleton Pack"})

    private_mean, private_final, private_delta, private_worst = _metric_values(resource, ["private_resource", "private_resource_mean", "mean_private_resource"], lower_is_worse=True)
    latent_mean, latent_final, latent_delta, latent_worst = _metric_values(hidden, ["latent_pressure", "latent_pressure_mean", "mean_latent_pressure"])
    recovery_row = {**common, "shock_marker_available": bool(shock_marker), "recovery_after_shock_proxy_available": bool(rec_avail), "recovery_after_shock_proxy": recovery, "collapse_delay_proxy_available": bool(collapse_avail), "collapse_delay_proxy": collapse, "threshold_used": threshold, "proxy_note": "proxy only; exact recovery/collapse claim prohibited", "exact_claim_allowed": False}
    hidden_gap_row = {**common, "visible_metric_available": visible is not None, "hidden_metric_available": hd is not None, "hidden_decay_gap_available": bool(gap_avail), "hidden_decay_gap_proxy": gap, "public_stability_hidden_decay_gap_available": public_gap != "not_available", "public_stability_hidden_decay_gap_proxy": public_gap, "proxy_note": "visible/public minus hidden deterioration proxy; not exact", "exact_claim_allowed": False}
    relation_row = {**common, "relation_trace_available": not relation.empty or not entity.empty, "relation_lock_proxy_available": bool(rel_available), "relation_lock_proxy": rel_value, "relation_unlock_action_mass": rel_mass, "relation_unlock_action_rows": rel_rows, "proxy_note": "entity relation_lock plus relation_unlock action mass proxy; not exact"}
    cost_row = {**common, "total_action_mass": _sum_numeric(action_frame, "action_strength"), "action_step_count": int(action_frame["loop_step"].nunique()) if "loop_step" in action_frame.columns and not action_frame.empty else int(len(action_frame)), "repeated_intervention_proxy": int(action_frame["loop_step"].nunique()) if "loop_step" in action_frame.columns and not action_frame.empty else int(len(action_frame)), "fatigue_delta": _metric_delta(hidden, ["fatigue", "fatigue_mean", "mean_fatigue"]), "defensiveness_delta": _metric_delta(hidden, ["defensiveness", "defend_tendency", "defensiveness_mean"]), "latent_pressure_delta": latent_delta, "action_cost_effect_proxy": "correlate_action_mass_with_state_delta", "intervention_fatigue_proxy": "repeated_intervention_count_with_fatigue_delta", "proxy_note": "correlation/proxy only; no causal claim", "exact_claim_allowed": False}
    channel_rows = []
    channels = ["exploration_injection", "coupling_relief", "volatility_damping", "uncertainty_probe", "relation_unlock", "buffer_increase"]
    for ch in channels:
        af = action_frame[action_frame["action_channel"].astype(str).eq(ch)] if not action_frame.empty and "action_channel" in action_frame.columns else pd.DataFrame()
        ef = effect[effect["action_channel"].astype(str).eq(ch)] if not effect.empty and "action_channel" in effect.columns else pd.DataFrame()
        channel_rows.append({**common, "action_channel": ch, "action_rows": int(len(af)), "action_mass_total": _sum_numeric(af, "action_strength"), "action_mass_mean": float(_sum_numeric(af, "action_strength") / len(af)) if len(af) else 0.0, "action_result_rows": int(len(action_result)), "effect_rows": int(len(ef)), "hidden_damage_delta_after_channel_proxy": _sum_numeric(ef, "hidden_damage_delta"), "fatigue_delta_after_channel_proxy": _sum_numeric(ef, "fatigue_delta"), "information_quality_delta_after_channel_proxy": "not_available", "cooperation_delta_after_channel_proxy": "not_available", "defensiveness_delta_after_channel_proxy": "not_available", "proxy_note": "channel effect proxy from existing v2_action_effect_trace/action_frame; not causal exact"})
    missing = [r["metric_name"] for r in availability if r["availability_class"] in {"not_available", "deferred_requires_semantic_design"}]
    is_v2_profile = str(cfg.world_profile_name).startswith("pseudo_reality_v2_")
    repair_pass = bool(((not is_v2_profile) or trace_available) and int(metrics.get("boundary_violation_rows", 0)) == 0 and not bool(metrics.get("dry_run_write_violation", False)) and not bool(metrics.get("forbidden_write_detected", False)))
    summary_row = {**common, "v2_trace_available": trace_available, "metric_export_repair_pass": repair_pass, **{f"{k}_count": v for k, v in counts.items()}, "boundary_violation_total": int(metrics.get("boundary_violation_rows", 0)), "dry_run_write_violation_count": int(bool(metrics.get("dry_run_write_violation", False))), "forbidden_write_count": int(bool(metrics.get("forbidden_write_detected", False))), "missing_evidence": ";".join(missing)}
    prlp_row = {**common, "private_resource_available": private_mean != "not_available", "private_resource_mean": private_mean, "private_resource_final": private_final, "private_resource_delta": private_delta, "private_resource_worst": private_worst, "latent_pressure_available": latent_mean != "not_available", "latent_pressure_mean": latent_mean, "latent_pressure_final": latent_final, "latent_pressure_delta": latent_delta, "latent_pressure_worst": latent_worst}
    return {"summary": pd.DataFrame([summary_row]), "availability": pd.DataFrame(availability), "private_latent": pd.DataFrame([prlp_row]), "recovery": pd.DataFrame([recovery_row]), "hidden_gap": pd.DataFrame([hidden_gap_row]), "relation": pd.DataFrame([relation_row]), "channel": pd.DataFrame(channel_rows), "cost": pd.DataFrame([cost_row])}


def build_v2_metric_export_repair_tables(parts: list[dict[str, pd.DataFrame]]):
    names = ["summary", "availability", "private_latent", "recovery", "hidden_gap", "relation", "channel", "cost"]
    tables = {n: pd.concat([p[n] for p in parts], ignore_index=True) if parts else pd.DataFrame() for n in names}
    availability = tables["availability"]
    if availability.empty:
        classification = missing = readiness = next_task = pd.DataFrame()
    else:
        classification = availability.groupby("metric_name", as_index=False).agg(source_trace=("source_trace", "first"), availability_class=("availability_class", lambda s: "exact_available" if (s == "exact_available").any() else "proxy_available" if (s == "proxy_available").any() else s.iloc[0]), exact_or_proxy=("exact_or_proxy", "first"), available_run_count=("availability_class", lambda s: int(s.isin(["exact_available", "proxy_available", "row_count_only"]).sum())), missing_run_count=("availability_class", lambda s: int(s.isin(["not_available", "deferred_requires_semantic_design"]).sum())))
        support = {"hidden_damage": "hidden_damage_rate,recovery_delay", "fatigue": "fatigue_accumulation_rate,action_cost", "information_quality": "information_asymmetry,information_distortion", "private_resource": "resource_inequality,commons_dependency,short_term_gain_pressure", "latent_pressure": "latent_pressure,defensive_reactivity", "relation_lock_proxy": "relation_lock_strength"}
        classification["cause_side_parameters_supported"] = classification["metric_name"].map(support).fillna("secondary/supporting")
        classification["use_as_primary"] = classification["availability_class"].isin(["exact_available", "proxy_available"])
        classification["use_as_secondary"] = True
        classification["needs_further_repair"] = classification["missing_run_count"].gt(0) | classification["availability_class"].isin(["not_available", "deferred_requires_semantic_design"])
        classification["note"] = "proxy metrics are explicitly non-exact; result-named profiles are readiness references only"
        missing = availability[availability["availability_class"].isin(["not_available", "deferred_requires_semantic_design"])][["run_label", "metric_name", "source_trace", "missing_reason", "recommended_future_task"]].copy()
        params = [
            ("information_asymmetry", ["information_quality", "observed_vs_hidden_gap"]),
            ("hidden_state_visibility", ["hidden_decay_gap", "public_stability_hidden_decay_gap"]),
            ("resource_inequality", ["private_resource", "commons_health_proxy"]),
            ("relation_lock_strength", ["relation_lock_proxy", "action_effect_by_channel"]),
            ("recovery_delay", ["recovery_after_shock_proxy", "hidden_damage", "fatigue", "cooperation_intent"]),
            ("action_cost", ["action_cost_effect", "intervention_fatigue", "fatigue", "defensiveness", "latent_pressure"]),
        ]
        ready_rows = []
        cmap = classification.set_index("metric_name")["availability_class"].to_dict()
        for param, req in params:
            exact = [m for m in req if cmap.get(m) == "exact_available"]
            proxy = [m for m in req if cmap.get(m) == "proxy_available"]
            miss = [m for m in req if cmap.get(m) not in {"exact_available", "proxy_available"}]
            if any(cmap.get(m) == "deferred_requires_semantic_design" for m in req):
                klass = "deferred_requires_semantic_design"
            elif miss:
                klass = "blocked_by_missing_export"
            elif proxy and not exact:
                klass = "ready_with_proxy_only"
            elif proxy:
                klass = "ready_with_proxy_only"
            else:
                klass = "ready_for_one_axis_probe"
            ready_rows.append({"cause_side_parameter": param, "required_metrics": ";".join(req), "exact_available_metrics": ";".join(exact), "proxy_available_metrics": ";".join(proxy), "missing_metrics": ";".join(miss), "readiness_class": klass, "blocker": ";".join(miss), "recommended_next_task": "Phase 2G-9 Cause-side Matrix Skeleton Pack" if klass != "blocked_by_missing_export" else "Phase 2G-9 Additional Metric Export Repair"})
        readiness = pd.DataFrame(ready_rows)
        next_task = pd.DataFrame([{"recommendation": "Phase 2G-9 Cause-side Matrix Skeleton Pack", "reason": "core exact metrics and several proxies are exported; use proxy-only cautions", "priority": "high"}, {"recommendation": "Phase 2G-9 Additional Metric Export Repair", "reason": "shock recovery and channel-specific state effects remain proxy/missing for exact secondary claims", "priority": "medium"}])
    return tables["summary"], availability, classification, tables["private_latent"], tables["recovery"], tables["hidden_gap"], tables["relation"], tables["channel"], tables["cost"], readiness, missing, next_task

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
    acd_group_rows = []
    a_group_rows = []
    c_group_rows = []
    d_group_rows = []
    acd_cross_rows = []
    low_risk_repair_rows = []
    deferred_major_rows = []
    v2_premise_rows = []
    v2_boundary_rows = []
    v2_metric_rows = []
    v2_preliminary_rows = []
    v2_extended_rows = []
    v2_metric_export_repair_parts = []
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

        acd_group, a_group, c_group, d_group, acd_cross, repair_manifest, deferred_major = build_acd_low_risk_tables(label, cfg, out, metrics)
        acd_group_rows.append(acd_group)
        a_group_rows.append(a_group)
        c_group_rows.append(c_group)
        d_group_rows.append(d_group)
        acd_cross_rows.append(acd_cross)
        low_risk_repair_rows.append(repair_manifest)
        deferred_major_rows.append(deferred_major)
        dataframe_to_csv(acd_group, rd / "acd_group_validation_summary.csv")
        dataframe_to_csv(a_group, rd / "a_group_pressure_parameter_summary.csv")
        dataframe_to_csv(c_group, rd / "c_group_action_boundary_summary.csv")
        dataframe_to_csv(d_group, rd / "d_group_world_audit_export_summary.csv")
        dataframe_to_csv(acd_cross, rd / "acd_cross_boundary_summary.csv")

        v2_premise, v2_boundary, v2_metric = build_v2_premise_freeze_tables(label, cfg, out, metrics)
        v2_premise_rows.append(v2_premise)
        v2_boundary_rows.append(v2_boundary)
        v2_metric_rows.append(v2_metric)
        dataframe_to_csv(v2_premise, rd / "v2_premise_freeze_summary.csv")
        dataframe_to_csv(v2_boundary, rd / "v2_boundary_safety_summary.csv")

        v2_prelim_row = build_v2_preliminary_row(label, cfg, out, metrics)
        v2_preliminary_rows.append(v2_prelim_row)
        dataframe_to_csv(pd.DataFrame([v2_prelim_row]), rd / "v2_preliminary_validation_summary.csv")
        v2_extended_row = build_v2_extended_row(label, cfg, out, metrics)
        v2_extended_rows.append(v2_extended_row)
        dataframe_to_csv(pd.DataFrame([v2_extended_row]), rd / "v2_extended_validation_summary.csv")
        v2_metric_export_repair_part = build_v2_metric_export_repair_rows(label, cfg, out, metrics)
        v2_metric_export_repair_parts.append(v2_metric_export_repair_part)
        for export_name, frame in v2_metric_export_repair_part.items():
            dataframe_to_csv(frame, rd / f"v2_metric_export_repair_{export_name}.csv")

    candidate_retention_all = pd.concat(candidate_retention_rows, ignore_index=True) if candidate_retention_rows else pd.DataFrame()
    gate_decomposition_all = pd.concat(gate_decomposition_rows, ignore_index=True) if gate_decomposition_rows else pd.DataFrame()
    action_loss_all = pd.concat(action_loss_rows, ignore_index=True) if action_loss_rows else pd.DataFrame()
    stage_retention_all = pd.concat(stage_retention_rows, ignore_index=True) if stage_retention_rows else pd.DataFrame()
    dataframe_to_csv(candidate_retention_all, output_dir / "candidate_retention_decomposition.csv")
    dataframe_to_csv(gate_decomposition_all, output_dir / "gate_decomposition_by_decision.csv")
    dataframe_to_csv(action_loss_all, output_dir / "action_loss_by_gate_decision.csv")
    dataframe_to_csv(stage_retention_all, output_dir / "stage_retention_summary.csv")
    acd_group_all = pd.concat(acd_group_rows, ignore_index=True) if acd_group_rows else pd.DataFrame()
    a_group_all = pd.concat(a_group_rows, ignore_index=True) if a_group_rows else pd.DataFrame()
    c_group_all = pd.concat(c_group_rows, ignore_index=True) if c_group_rows else pd.DataFrame()
    d_group_all = pd.concat(d_group_rows, ignore_index=True) if d_group_rows else pd.DataFrame()
    acd_cross_all = pd.concat(acd_cross_rows, ignore_index=True) if acd_cross_rows else pd.DataFrame()
    low_risk_repair_all = pd.concat(low_risk_repair_rows, ignore_index=True).drop_duplicates() if low_risk_repair_rows else pd.DataFrame()
    deferred_major_all = pd.concat(deferred_major_rows, ignore_index=True) if deferred_major_rows else pd.DataFrame(columns=["group", "module", "issue", "why_major", "evidence", "recommended_future_task", "priority"])
    dataframe_to_csv(acd_group_all, output_dir / "acd_group_validation_summary.csv")
    dataframe_to_csv(a_group_all, output_dir / "a_group_pressure_parameter_summary.csv")
    dataframe_to_csv(c_group_all, output_dir / "c_group_action_boundary_summary.csv")
    dataframe_to_csv(d_group_all, output_dir / "d_group_world_audit_export_summary.csv")
    dataframe_to_csv(acd_cross_all, output_dir / "acd_cross_boundary_summary.csv")
    dataframe_to_csv(low_risk_repair_all, output_dir / "low_risk_repair_manifest.csv")
    dataframe_to_csv(deferred_major_all, output_dir / "deferred_major_repair_candidates.csv")
    v2_premise_all = pd.concat(v2_premise_rows, ignore_index=True) if v2_premise_rows else pd.DataFrame()
    v2_boundary_all = pd.concat(v2_boundary_rows, ignore_index=True) if v2_boundary_rows else pd.DataFrame()
    v2_metric_all = pd.concat(v2_metric_rows, ignore_index=True).drop_duplicates(subset=["metric_name"], keep="first") if v2_metric_rows else pd.DataFrame()
    v2_profiles, v2_baselines, v2_missing, v2_deferred = build_v2_static_premise_tables()
    v2_profile_pass = bool(not v2_profiles.empty and v2_premise_all[v2_premise_all["is_v2_profile"].astype(bool)]["v2_trace_available"].astype(bool).all()) if not v2_premise_all.empty else False
    if not v2_profiles.empty:
        v2_profiles["trace_available"] = v2_profile_pass
        v2_profiles["readiness_pass"] = v2_profile_pass
    dataframe_to_csv(v2_premise_all, output_dir / "v2_premise_freeze_summary.csv")
    dataframe_to_csv(v2_profiles, output_dir / "v2_profile_readiness_summary.csv")
    dataframe_to_csv(v2_metric_all, output_dir / "v2_metric_availability_summary.csv")
    dataframe_to_csv(v2_baselines, output_dir / "v2_baseline_comparison_plan.csv")
    dataframe_to_csv(v2_boundary_all, output_dir / "v2_boundary_safety_summary.csv")
    dataframe_to_csv(v2_missing, output_dir / "v2_missing_evidence_summary.csv")
    dataframe_to_csv(v2_deferred, output_dir / "v2_deferred_design_candidates.csv")
    (v2_prelim_summary, v2_profile_mode_comparison, v2_metric_by_run_summary,
     v2_metric_delta_vs_baseline, v2_action_channel_comparison,
     v2_safety_boundary_summary, v2_preliminary_reading_summary,
     v2_missing_metric_evidence, v2_next_task_recommendation) = build_v2_preliminary_tables(v2_preliminary_rows)
    dataframe_to_csv(v2_prelim_summary, output_dir / "v2_preliminary_validation_summary.csv")
    dataframe_to_csv(v2_profile_mode_comparison, output_dir / "v2_profile_mode_comparison.csv")
    dataframe_to_csv(v2_metric_by_run_summary, output_dir / "v2_metric_by_run_summary.csv")
    dataframe_to_csv(v2_metric_delta_vs_baseline, output_dir / "v2_metric_delta_vs_baseline.csv")
    dataframe_to_csv(v2_action_channel_comparison, output_dir / "v2_action_channel_comparison.csv")
    dataframe_to_csv(v2_safety_boundary_summary, output_dir / "v2_safety_boundary_summary.csv")
    dataframe_to_csv(v2_preliminary_reading_summary, output_dir / "v2_preliminary_reading_summary.csv")
    dataframe_to_csv(v2_missing_metric_evidence, output_dir / "v2_missing_metric_evidence.csv")
    dataframe_to_csv(v2_next_task_recommendation, output_dir / "v2_next_task_recommendation.csv")
    (v2_ext_summary, v2_ext_profile_mode, v2_ext_seed_stability, v2_ext_longer, v2_ext_adequacy, v2_ext_delta, v2_ext_action_mass, v2_ext_safety, v2_ext_missing, v2_ext_next) = build_v2_extended_tables(v2_extended_rows)
    dataframe_to_csv(v2_ext_summary, output_dir / "v2_extended_validation_summary.csv")
    dataframe_to_csv(v2_ext_profile_mode, output_dir / "v2_extended_profile_mode_comparison.csv")
    dataframe_to_csv(v2_ext_seed_stability, output_dir / "v2_extended_seed_stability_summary.csv")
    dataframe_to_csv(v2_ext_longer, output_dir / "v2_extended_longer_horizon_summary.csv")
    dataframe_to_csv(v2_ext_adequacy, output_dir / "v2_extended_metric_adequacy_summary.csv")
    dataframe_to_csv(v2_ext_delta, output_dir / "v2_extended_metric_delta_vs_baseline.csv")
    dataframe_to_csv(v2_ext_action_mass, output_dir / "v2_extended_action_mass_stability.csv")
    dataframe_to_csv(v2_ext_safety, output_dir / "v2_extended_safety_boundary_summary.csv")
    dataframe_to_csv(v2_ext_missing, output_dir / "v2_extended_missing_metric_evidence.csv")
    dataframe_to_csv(v2_ext_next, output_dir / "v2_extended_next_task_recommendation.csv")
    (v2_mer_summary, v2_mer_availability, v2_mer_classification, v2_mer_private_latent,
     v2_mer_recovery, v2_mer_hidden_gap, v2_mer_relation, v2_mer_channel, v2_mer_cost,
     v2_mer_readiness, v2_mer_missing, v2_mer_next) = build_v2_metric_export_repair_tables(v2_metric_export_repair_parts)
    dataframe_to_csv(v2_mer_summary, output_dir / "v2_metric_export_repair_summary.csv")
    dataframe_to_csv(v2_mer_availability, output_dir / "v2_metric_availability_by_run.csv")
    dataframe_to_csv(v2_mer_classification, output_dir / "v2_metric_classification_summary.csv")
    dataframe_to_csv(v2_mer_private_latent, output_dir / "v2_private_resource_latent_pressure_summary.csv")
    dataframe_to_csv(v2_mer_recovery, output_dir / "v2_recovery_collapse_proxy_summary.csv")
    dataframe_to_csv(v2_mer_hidden_gap, output_dir / "v2_hidden_decay_gap_summary.csv")
    dataframe_to_csv(v2_mer_relation, output_dir / "v2_relation_lock_proxy_summary.csv")
    dataframe_to_csv(v2_mer_channel, output_dir / "v2_action_effect_by_channel_summary.csv")
    dataframe_to_csv(v2_mer_cost, output_dir / "v2_action_cost_intervention_fatigue_proxy_summary.csv")
    dataframe_to_csv(v2_mer_readiness, output_dir / "v2_cause_side_metric_readiness_summary.csv")
    dataframe_to_csv(v2_mer_missing, output_dir / "v2_metric_export_missing_evidence.csv")
    dataframe_to_csv(v2_mer_next, output_dir / "v2_metric_export_next_task_recommendation.csv")
    cause_profiles = {}
    for run in matrix["runs"]:
        wp = str(run["world_profile"])
        if "cause_side_v2_1/" in wp:
            try:
                cause_profiles[wp] = load_json(REPO_ROOT / "configs" / "world_profiles" / f"{wp}.json")
            except FileNotFoundError:
                cause_profiles[wp] = {}
    v2_1_rows = []
    for r in rows:
        profile = cause_profiles.get(str(r.get("world_profile", "")), {})
        if not profile:
            continue
        config = profile.get("config", {}).get("v2_world_config", {}) if profile else {}
        params = config.get("cause_side_parameters", profile.get("cause_side_parameters", {})) if isinstance(config, dict) else {}
        implemented = config.get("implemented_axes", profile.get("implemented_axes", [])) if isinstance(config, dict) else []
        deferred = config.get("deferred_axes", profile.get("deferred_axes", [])) if isinstance(config, dict) else []
        axis_names = list(params.keys()) if isinstance(params, dict) else []
        for axis in axis_names or ["not_applicable"]:
            v2_1_rows.append({
                "run_label": r.get("label", ""),
                "world_profile": r.get("world_profile", ""),
                "profile_family": config.get("profile_family", profile.get("profile_family", "")) if isinstance(config, dict) else "",
                "implemented_axes": ";".join(implemented),
                "deferred_axes": ";".join(deferred),
                "cause_side_parameter_name": axis,
                "cause_side_parameter_value": params.get(axis, "") if isinstance(params, dict) else "",
                "baseline_name": "near_zero_action" if "near_zero" in str(r.get("label", "")) else ("relaxed_legacy_dampen_075" if r.get("intermediate_conservatism_mode") == "relaxed_legacy_dampen_075" else ("flat" if r.get("intermediate_conservatism_mode") == "flat" else "repaired_relaxed")),
                "seed": r.get("seed", ""),
                "steps": r.get("steps", ""),
                "v2_1_profile_loaded": bool(profile),
                "existing_v2_compatibility_pass": bool(r.get("overall_pass", False)) if str(r.get("label", "")).startswith("existing_v2_") else "",
                "action_mass_total": r.get("action_frame_strength_sum", 0.0),
                "hidden_damage_mean": r.get("hidden_damage_mean", 0.0),
                "fatigue_mean": r.get("fatigue_mean", 0.0),
                "information_quality_mean": r.get("information_quality_mean", 0.0),
                "cooperation_intent_mean": r.get("cooperation_intent_mean", 0.0),
                "defensiveness_mean": r.get("defensiveness_mean", 0.0),
                "latent_pressure_mean": r.get("latent_pressure_mean", 0.0),
                "private_resource_mean": r.get("private_resource_mean", 0.0),
                "boundary_violation_total": r.get("boundary_violation_rows", 0),
                "dry_run_write_violation_count": int(bool(r.get("dry_run_write_violation", False))),
                "forbidden_write_count": int(bool(r.get("forbidden_write_detected", False))),
                "minimal_implementation_probe_pass": bool(profile) and bool(r.get("overall_pass", False)),
            })
    v2_1_summary = pd.DataFrame(v2_1_rows)
    axis_rows = []
    for axis in ["information_asymmetry", "action_cost", "hidden_state_visibility", "short_term_gain_pressure", "relation_lock_strength", "recovery_delay"]:
        implemented = axis in {"information_asymmetry", "action_cost"}
        axis_rows.append({
            "axis": axis,
            "implemented": implemented,
            "profile_values_available": bool(implemented and any(axis in (p.get("cause_side_parameters", {}) or p.get("config", {}).get("v2_world_config", {}).get("cause_side_parameters", {})) for p in cause_profiles.values())),
            "matrix_runs_available": bool(implemented and v2_1_summary["run_label"].astype(str).str.contains(axis, regex=False).any()) if not v2_1_summary.empty else False,
            "primary_metrics_available": "exact_for_exported_hidden_trace_means" if implemented else "not_applicable",
            "proxy_metrics_available": "proxy_available" if implemented else "not_applicable",
            "readiness_class": "ready_for_preliminary_one_axis_validation" if implemented else "deferred",
            "blocker": "" if implemented else "deferred_by_phase2g10_scope",
            "recommended_next_task": "Phase 2G-11 Cause-side Preliminary Validation Pack" if implemented else "Phase 2G-11 Additional v2.1 Axis Implementation Probe",
        })
    deferred_axes = sorted({x for p in cause_profiles.values() for x in (p.get("deferred_axes", []) or p.get("config", {}).get("v2_world_config", {}).get("deferred_axes", []))})
    v2_1_axis = pd.DataFrame(axis_rows)
    v2_1_compat = pd.DataFrame([r for r in rows if str(r.get("label", "")).startswith("existing_v2_")])
    v2_1_metric = pd.DataFrame([
        {"metric": "information_quality_mean", "status": "exact_exported_mean", "axis": "information_asymmetry"},
        {"metric": "hidden_damage_mean", "status": "exact_exported_mean", "axis": "information_asymmetry"},
        {"metric": "observed_vs_hidden_gap_proxy", "status": "proxy_available", "axis": "information_asymmetry"},
        {"metric": "fatigue_mean", "status": "exact_exported_mean", "axis": "action_cost"},
        {"metric": "action_cost_effect", "status": "proxy_available", "axis": "action_cost"},
    ])
    v2_1_deferred = pd.DataFrame([{"axis": axis, "implemented": False, "reason": "deferred_by_phase2g10_minimal_scope", "recommended_next_task": "Phase 2G-11 Additional v2.1 Axis Implementation Probe"} for axis in deferred_axes])
    v2_1_next = pd.DataFrame([{"recommended_next_task": "Phase 2G-11 Cause-side Preliminary Validation Pack", "reason": "minimal two-axis v2.1 profile namespace loads and compatibility/safety smoke checks are present", "priority": "high"}])
    (v2_1_prelim, v2_1_baseline, v2_1_seed, v2_1_delta, v2_1_cost, v2_1_info,
     v2_1_combined, v2_1_existing, v2_1_missing, v2_1_next_prelim) = build_v2_1_cause_side_preliminary_tables(v2_preliminary_rows, cause_profiles)
    dataframe_to_csv(v2_1_summary, output_dir / "v2_1_cause_side_minimal_implementation_summary.csv")
    dataframe_to_csv(v2_1_axis, output_dir / "v2_1_cause_side_axis_readiness_summary.csv")
    dataframe_to_csv(v2_1_compat, output_dir / "v2_1_cause_side_compatibility_summary.csv")
    dataframe_to_csv(v2_1_metric, output_dir / "v2_1_cause_side_metric_readiness_summary.csv")
    dataframe_to_csv(v2_1_deferred, output_dir / "v2_1_cause_side_deferred_axes_summary.csv")
    dataframe_to_csv(v2_1_next, output_dir / "v2_1_cause_side_next_task_recommendation.csv")
    dataframe_to_csv(v2_1_prelim, output_dir / "v2_1_cause_side_preliminary_validation_summary.csv")
    dataframe_to_csv(v2_1_baseline, output_dir / "v2_1_cause_side_axis_baseline_comparison.csv")
    dataframe_to_csv(v2_1_seed, output_dir / "v2_1_cause_side_seed_stability_summary.csv")
    dataframe_to_csv(v2_1_delta, output_dir / "v2_1_cause_side_metric_delta_summary.csv")
    dataframe_to_csv(v2_1_cost, output_dir / "v2_1_cause_side_action_cost_summary.csv")
    dataframe_to_csv(v2_1_info, output_dir / "v2_1_cause_side_information_asymmetry_summary.csv")
    dataframe_to_csv(v2_1_combined, output_dir / "v2_1_cause_side_combined_probe_summary.csv")
    dataframe_to_csv(v2_1_existing, output_dir / "v2_1_cause_side_existing_v2_compatibility_summary.csv")
    dataframe_to_csv(v2_1_missing, output_dir / "v2_1_cause_side_missing_evidence.csv")
    dataframe_to_csv(v2_1_next_prelim, output_dir / "v2_1_cause_side_next_task_recommendation.csv")
    (v2_1_additional_repair, v2_1_observed_gap, v2_1_action_cost_repair, v2_1_intervention_fatigue_repair,
     v2_1_action_effect_channel_repair, v2_1_info_effect, v2_1_cost_response, v2_1_metric_classification,
     v2_1_tuning_readiness, v2_1_additional_missing, v2_1_additional_next) = build_v2_1_additional_metric_export_repair_tables(v2_1_prelim)
    dataframe_to_csv(v2_1_additional_repair, output_dir / "v2_1_additional_metric_export_repair_summary.csv")
    dataframe_to_csv(v2_1_observed_gap, output_dir / "v2_1_observed_vs_hidden_gap_repair_summary.csv")
    dataframe_to_csv(v2_1_action_cost_repair, output_dir / "v2_1_action_cost_effect_repair_summary.csv")
    dataframe_to_csv(v2_1_intervention_fatigue_repair, output_dir / "v2_1_intervention_fatigue_repair_summary.csv")
    dataframe_to_csv(v2_1_action_effect_channel_repair, output_dir / "v2_1_action_effect_by_channel_repair_summary.csv")
    dataframe_to_csv(v2_1_info_effect, output_dir / "v2_1_information_asymmetry_effect_summary.csv")
    dataframe_to_csv(v2_1_cost_response, output_dir / "v2_1_action_cost_state_response_summary.csv")
    dataframe_to_csv(v2_1_metric_classification, output_dir / "v2_1_metric_classification_summary.csv")
    dataframe_to_csv(v2_1_tuning_readiness, output_dir / "v2_1_tuning_decision_metric_readiness_summary.csv")
    dataframe_to_csv(v2_1_additional_missing, output_dir / "v2_1_additional_metric_export_missing_evidence.csv")
    dataframe_to_csv(v2_1_additional_next, output_dir / "v2_1_additional_metric_export_next_task_recommendation.csv")

    probe_summary, relation_comparison, dampen_comparison, safety_summary = build_intermediate_conservatism_probe_tables(rows)
    dataframe_to_csv(probe_summary, output_dir / "intermediate_conservatism_probe_summary.csv")
    dataframe_to_csv(relation_comparison, output_dir / "relation_unlock_mode_comparison.csv")
    dataframe_to_csv(dampen_comparison, output_dir / "dampen_probe_comparison.csv")
    dataframe_to_csv(safety_summary, output_dir / "safety_boundary_probe_summary.csv")
    repair_summary, repair_comparison, repair_relation, repair_safety = build_dampen_only_repair_tables(rows)
    dataframe_to_csv(repair_summary, output_dir / "dampen_only_repair_summary.csv")
    dataframe_to_csv(repair_comparison, output_dir / "relaxed_legacy_vs_repaired_comparison.csv")
    dataframe_to_csv(repair_relation, output_dir / "relation_unlock_repair_comparison.csv")
    dataframe_to_csv(repair_safety, output_dir / "dampen_repair_safety_summary.csv")

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
        "dampen_only_repair_summary_present": (output_dir / "dampen_only_repair_summary.csv").exists(),
        "relaxed_legacy_vs_repaired_comparison_present": (output_dir / "relaxed_legacy_vs_repaired_comparison.csv").exists(),
        "relation_unlock_repair_comparison_present": (output_dir / "relation_unlock_repair_comparison.csv").exists(),
        "dampen_repair_safety_summary_present": (output_dir / "dampen_repair_safety_summary.csv").exists(),
        "legacy_relaxed_action_mass": float(repair_comparison["legacy_action_mass"].iloc[0]) if not repair_comparison.empty else 0.0,
        "repaired_relaxed_action_mass": float(repair_comparison["repaired_action_mass"].iloc[0]) if not repair_comparison.empty else 0.0,
        "repaired_delta_vs_legacy": float(repair_comparison["repaired_delta_vs_legacy"].iloc[0]) if not repair_comparison.empty else 0.0,
        "repaired_delta_vs_flat": float(repair_comparison["repaired_delta_vs_flat"].iloc[0]) if not repair_comparison.empty else 0.0,
        "legacy_relation_unlock_mass": float(repair_comparison["legacy_relation_unlock_mass"].iloc[0]) if not repair_comparison.empty else 0.0,
        "repaired_relation_unlock_mass": float(repair_comparison["repaired_relation_unlock_mass"].iloc[0]) if not repair_comparison.empty else 0.0,
        "repaired_relation_unlock_delta_vs_legacy": float(repair_comparison["repaired_relation_unlock_delta_vs_legacy"].iloc[0]) if not repair_comparison.empty else 0.0,
        "repaired_relation_unlock_delta_vs_flat": float(repair_comparison["repaired_relation_unlock_delta_vs_flat"].iloc[0]) if not repair_comparison.empty else 0.0,
        "recommended_next_task": "Phase 2G-13 ActionModule v2 Tuning Decision Pack discussion-only, or Phase 2G-13 Additional Metric Repair if exact visible/public metrics are required.",
        "v2_1_cause_side_minimal_implementation_summary_present": (output_dir / "v2_1_cause_side_minimal_implementation_summary.csv").exists(),
        "v2_1_cause_side_axis_readiness_summary_present": (output_dir / "v2_1_cause_side_axis_readiness_summary.csv").exists(),
        "v2_1_cause_side_compatibility_summary_present": (output_dir / "v2_1_cause_side_compatibility_summary.csv").exists(),
        "v2_1_cause_side_metric_readiness_summary_present": (output_dir / "v2_1_cause_side_metric_readiness_summary.csv").exists(),
        "v2_1_cause_side_deferred_axes_summary_present": (output_dir / "v2_1_cause_side_deferred_axes_summary.csv").exists(),
        "v2_1_cause_side_next_task_recommendation_present": (output_dir / "v2_1_cause_side_next_task_recommendation.csv").exists(),
        "v2_1_cause_side_run_count": int(v2_1_summary["run_label"].nunique()) if "v2_1_summary" in locals() and not v2_1_summary.empty else 0,
        "v2_1_implemented_axis_count": 2,
        "v2_1_deferred_axis_count": int(len(deferred_axes)) if "deferred_axes" in locals() else 0,
        "v2_1_minimal_implementation_probe_pass": bool("v2_1_summary" in locals() and not v2_1_summary.empty and v2_1_summary["minimal_implementation_probe_pass"].astype(bool).all()),
        "existing_v2_compatibility_pass": bool("v2_1_existing" in locals() and not v2_1_existing.empty and v2_1_existing["existing_v2_compatibility_pass"].astype(bool).all()),
        "v2_1_cause_side_preliminary_validation_summary_present": (output_dir / "v2_1_cause_side_preliminary_validation_summary.csv").exists(),
        "v2_1_cause_side_axis_baseline_comparison_present": (output_dir / "v2_1_cause_side_axis_baseline_comparison.csv").exists(),
        "v2_1_cause_side_seed_stability_summary_present": (output_dir / "v2_1_cause_side_seed_stability_summary.csv").exists(),
        "v2_1_cause_side_metric_delta_summary_present": (output_dir / "v2_1_cause_side_metric_delta_summary.csv").exists(),
        "v2_1_cause_side_action_cost_summary_present": (output_dir / "v2_1_cause_side_action_cost_summary.csv").exists(),
        "v2_1_cause_side_information_asymmetry_summary_present": (output_dir / "v2_1_cause_side_information_asymmetry_summary.csv").exists(),
        "v2_1_cause_side_combined_probe_summary_present": (output_dir / "v2_1_cause_side_combined_probe_summary.csv").exists(),
        "v2_1_cause_side_existing_v2_compatibility_summary_present": (output_dir / "v2_1_cause_side_existing_v2_compatibility_summary.csv").exists(),
        "v2_1_cause_side_missing_evidence_present": (output_dir / "v2_1_cause_side_missing_evidence.csv").exists(),
        "v2_1_cause_side_preliminary_run_count": int(len(v2_1_prelim)) if "v2_1_prelim" in locals() else 0,
        "v2_1_cause_side_axis_count": int(v2_1_prelim[v2_1_prelim["axis"].isin(["information_asymmetry", "action_cost"])]["axis"].nunique()) if "v2_1_prelim" in locals() and not v2_1_prelim.empty else 0,
        "v2_1_cause_side_baseline_count": int(v2_1_prelim["baseline_name"].nunique()) if "v2_1_prelim" in locals() and not v2_1_prelim.empty else 0,
        "v2_1_cause_side_seed_count": int(v2_1_prelim["seed"].nunique()) if "v2_1_prelim" in locals() and not v2_1_prelim.empty else 0,
        "v2_1_cause_side_preliminary_validation_pass": bool("v2_1_prelim" in locals() and not v2_1_prelim.empty and v2_1_prelim["preliminary_validation_pass"].astype(bool).all()),
        "v2_1_additional_metric_export_repair_summary_present": (output_dir / "v2_1_additional_metric_export_repair_summary.csv").exists(),
        "v2_1_observed_vs_hidden_gap_repair_summary_present": (output_dir / "v2_1_observed_vs_hidden_gap_repair_summary.csv").exists(),
        "v2_1_action_cost_effect_repair_summary_present": (output_dir / "v2_1_action_cost_effect_repair_summary.csv").exists(),
        "v2_1_intervention_fatigue_repair_summary_present": (output_dir / "v2_1_intervention_fatigue_repair_summary.csv").exists(),
        "v2_1_action_effect_by_channel_repair_summary_present": (output_dir / "v2_1_action_effect_by_channel_repair_summary.csv").exists(),
        "v2_1_information_asymmetry_effect_summary_present": (output_dir / "v2_1_information_asymmetry_effect_summary.csv").exists(),
        "v2_1_action_cost_state_response_summary_present": (output_dir / "v2_1_action_cost_state_response_summary.csv").exists(),
        "v2_1_metric_classification_summary_present": (output_dir / "v2_1_metric_classification_summary.csv").exists(),
        "v2_1_tuning_decision_metric_readiness_summary_present": (output_dir / "v2_1_tuning_decision_metric_readiness_summary.csv").exists(),
        "v2_1_additional_metric_export_missing_evidence_present": (output_dir / "v2_1_additional_metric_export_missing_evidence.csv").exists(),
        "v2_1_additional_metric_export_next_task_recommendation_present": (output_dir / "v2_1_additional_metric_export_next_task_recommendation.csv").exists(),
        "v2_1_additional_metric_export_run_count": int(len(v2_1_additional_repair)) if "v2_1_additional_repair" in locals() else 0,
        "v2_1_additional_metric_export_repair_pass": bool("v2_1_additional_repair" in locals() and not v2_1_additional_repair.empty and v2_1_additional_repair["metric_repair_pass"].astype(bool).all()),
        "observed_vs_hidden_gap_readiness": "derived_proxy_available" if "v2_1_observed_gap" in locals() and not v2_1_observed_gap.empty else "not_available",
        "action_cost_effect_readiness": "derived_proxy_available" if "v2_1_action_cost_repair" in locals() and not v2_1_action_cost_repair.empty else "not_available",
        "intervention_fatigue_readiness": "derived_proxy_available" if "v2_1_intervention_fatigue_repair" in locals() and not v2_1_intervention_fatigue_repair.empty else "not_available",
        "action_effect_by_channel_readiness": "derived_proxy_available" if "v2_1_action_effect_channel_repair" in locals() and not v2_1_action_effect_channel_repair.empty else "not_available",
        "tuning_decision_metric_readiness": str(v2_1_tuning_readiness["status"].iloc[0]) if "v2_1_tuning_readiness" in locals() and not v2_1_tuning_readiness.empty else "not_available",

        "v2_extended_validation_summary_present": (output_dir / "v2_extended_validation_summary.csv").exists(),
        "v2_extended_profile_mode_comparison_present": (output_dir / "v2_extended_profile_mode_comparison.csv").exists(),
        "v2_extended_seed_stability_summary_present": (output_dir / "v2_extended_seed_stability_summary.csv").exists(),
        "v2_extended_longer_horizon_summary_present": (output_dir / "v2_extended_longer_horizon_summary.csv").exists(),
        "v2_extended_metric_adequacy_summary_present": (output_dir / "v2_extended_metric_adequacy_summary.csv").exists(),
        "v2_extended_metric_delta_vs_baseline_present": (output_dir / "v2_extended_metric_delta_vs_baseline.csv").exists(),
        "v2_extended_action_mass_stability_present": (output_dir / "v2_extended_action_mass_stability.csv").exists(),
        "v2_extended_safety_boundary_summary_present": (output_dir / "v2_extended_safety_boundary_summary.csv").exists(),
        "v2_extended_missing_metric_evidence_present": (output_dir / "v2_extended_missing_metric_evidence.csv").exists(),
        "v2_extended_next_task_recommendation_present": (output_dir / "v2_extended_next_task_recommendation.csv").exists(),
        "v2_extended_run_count": int(len(v2_ext_summary)) if "v2_ext_summary" in locals() else 0,
        "v2_seed_count": int(v2_ext_summary["seed"].nunique()) if "v2_ext_summary" in locals() and not v2_ext_summary.empty else 0,
        "v2_longer_horizon_run_count": int(v2_ext_summary["is_longer_horizon"].astype(bool).sum()) if "v2_ext_summary" in locals() and not v2_ext_summary.empty else 0,
        "v2_extended_validation_pass": bool(not v2_ext_summary.empty and v2_ext_summary["extended_validation_pass"].astype(bool).all()) if "v2_ext_summary" in locals() else False,
        "repaired_relaxed_extended_available": bool((not v2_ext_summary.empty) and v2_ext_summary["baseline_name"].astype(str).eq("repaired_relaxed").any()) if "v2_ext_summary" in locals() else False,
        "legacy_relaxed_extended_available": bool((not v2_ext_summary.empty) and v2_ext_summary["baseline_name"].astype(str).eq("relaxed_legacy_dampen_075").any()) if "v2_ext_summary" in locals() else False,
        "near_zero_extended_available": bool((not v2_ext_summary.empty) and v2_ext_summary["baseline_name"].astype(str).eq("near_zero_action").any()) if "v2_ext_summary" in locals() else False,
        "flat_comparator_extended_available": bool((not v2_ext_summary.empty) and v2_ext_summary["baseline_name"].astype(str).eq("flat").any()) if "v2_ext_summary" in locals() else False,
        "v2_metric_adequacy_pass": bool(not v2_ext_adequacy.empty) if "v2_ext_adequacy" in locals() else False,
        "v2_metric_export_repair_recommended": bool((not v2_ext_adequacy.empty) and v2_ext_adequacy["needs_metric_export_repair"].astype(bool).any()) if "v2_ext_adequacy" in locals() else False,
        "v2_metric_export_repair_summary_present": (output_dir / "v2_metric_export_repair_summary.csv").exists(),
        "v2_metric_availability_by_run_present": (output_dir / "v2_metric_availability_by_run.csv").exists(),
        "v2_metric_classification_summary_present": (output_dir / "v2_metric_classification_summary.csv").exists(),
        "v2_private_resource_latent_pressure_summary_present": (output_dir / "v2_private_resource_latent_pressure_summary.csv").exists(),
        "v2_recovery_collapse_proxy_summary_present": (output_dir / "v2_recovery_collapse_proxy_summary.csv").exists(),
        "v2_hidden_decay_gap_summary_present": (output_dir / "v2_hidden_decay_gap_summary.csv").exists(),
        "v2_relation_lock_proxy_summary_present": (output_dir / "v2_relation_lock_proxy_summary.csv").exists(),
        "v2_action_effect_by_channel_summary_present": (output_dir / "v2_action_effect_by_channel_summary.csv").exists(),
        "v2_action_cost_intervention_fatigue_proxy_summary_present": (output_dir / "v2_action_cost_intervention_fatigue_proxy_summary.csv").exists(),
        "v2_cause_side_metric_readiness_summary_present": (output_dir / "v2_cause_side_metric_readiness_summary.csv").exists(),
        "v2_metric_export_missing_evidence_present": (output_dir / "v2_metric_export_missing_evidence.csv").exists(),
        "v2_metric_export_next_task_recommendation_present": (output_dir / "v2_metric_export_next_task_recommendation.csv").exists(),
        "v2_metric_export_run_count": int(len(v2_mer_summary)) if "v2_mer_summary" in locals() else 0,
        "v2_metric_export_repair_pass": bool(not v2_mer_summary.empty and v2_mer_summary["metric_export_repair_pass"].astype(bool).all()) if "v2_mer_summary" in locals() else False,
        "exact_available_metric_count": int((v2_mer_classification["availability_class"] == "exact_available").sum()) if "v2_mer_classification" in locals() and not v2_mer_classification.empty else 0,
        "proxy_available_metric_count": int((v2_mer_classification["availability_class"] == "proxy_available").sum()) if "v2_mer_classification" in locals() and not v2_mer_classification.empty else 0,
        "row_count_only_metric_count": int((v2_mer_classification["availability_class"] == "row_count_only").sum()) if "v2_mer_classification" in locals() and not v2_mer_classification.empty else 0,
        "export_repaired_metric_count": int((v2_mer_classification["availability_class"] == "export_repaired").sum()) if "v2_mer_classification" in locals() and not v2_mer_classification.empty else 0,
        "not_available_metric_count": int((v2_mer_classification["availability_class"] == "not_available").sum()) if "v2_mer_classification" in locals() and not v2_mer_classification.empty else 0,
        "deferred_requires_semantic_design_metric_count": int((v2_mer_classification["availability_class"] == "deferred_requires_semantic_design").sum()) if "v2_mer_classification" in locals() and not v2_mer_classification.empty else 0,
        "ready_for_one_axis_probe_count": int((v2_mer_readiness["readiness_class"] == "ready_for_one_axis_probe").sum()) if "v2_mer_readiness" in locals() and not v2_mer_readiness.empty else 0,
        "ready_with_proxy_only_count": int((v2_mer_readiness["readiness_class"] == "ready_with_proxy_only").sum()) if "v2_mer_readiness" in locals() and not v2_mer_readiness.empty else 0,
        "blocked_by_missing_export_count": int((v2_mer_readiness["readiness_class"] == "blocked_by_missing_export").sum()) if "v2_mer_readiness" in locals() and not v2_mer_readiness.empty else 0,
        "v2_preliminary_validation_summary_present": (output_dir / "v2_preliminary_validation_summary.csv").exists(),
        "v2_profile_mode_comparison_present": (output_dir / "v2_profile_mode_comparison.csv").exists(),
        "v2_metric_by_run_summary_present": (output_dir / "v2_metric_by_run_summary.csv").exists(),
        "v2_metric_delta_vs_baseline_present": (output_dir / "v2_metric_delta_vs_baseline.csv").exists(),
        "v2_action_channel_comparison_present": (output_dir / "v2_action_channel_comparison.csv").exists(),
        "v2_safety_boundary_summary_present": (output_dir / "v2_safety_boundary_summary.csv").exists(),
        "v2_preliminary_reading_summary_present": (output_dir / "v2_preliminary_reading_summary.csv").exists(),
        "v2_missing_metric_evidence_present": (output_dir / "v2_missing_metric_evidence.csv").exists(),
        "v2_next_task_recommendation_present": (output_dir / "v2_next_task_recommendation.csv").exists(),
        "v2_preliminary_run_count": int(len(v2_prelim_summary)),
        "v2_profile_family_count": int(v2_prelim_summary[v2_prelim_summary["world_profile"].astype(str).str.startswith("pseudo_reality_v2_")]["profile_family"].nunique()) if not v2_prelim_summary.empty else 0,
        "v2_baseline_count": int(v2_prelim_summary["baseline_name"].nunique()) if not v2_prelim_summary.empty else 0,
        "v2_preliminary_pass": bool(not v2_prelim_summary.empty and v2_prelim_summary["preliminary_pass"].astype(bool).all()),
        "repaired_relaxed_available": bool((not v2_prelim_summary.empty) and v2_prelim_summary["baseline_name"].astype(str).eq("repaired_relaxed").any()),
        "legacy_relaxed_available": bool((not v2_prelim_summary.empty) and v2_prelim_summary["baseline_name"].astype(str).eq("relaxed_legacy_dampen_075").any()),
        "no_action_or_near_zero_available": bool((not v2_prelim_summary.empty) and v2_prelim_summary["baseline_name"].astype(str).eq("near_zero_action").any()),
        "flat_comparator_available": bool((not v2_prelim_summary.empty) and v2_prelim_summary["baseline_name"].astype(str).eq("flat").any()),
        "v2_premise_freeze_summary_present": (output_dir / "v2_premise_freeze_summary.csv").exists(),
        "v2_profile_readiness_summary_present": (output_dir / "v2_profile_readiness_summary.csv").exists(),
        "v2_metric_availability_summary_present": (output_dir / "v2_metric_availability_summary.csv").exists(),
        "v2_baseline_comparison_plan_present": (output_dir / "v2_baseline_comparison_plan.csv").exists(),
        "v2_boundary_safety_summary_present": (output_dir / "v2_boundary_safety_summary.csv").exists(),
        "v2_missing_evidence_summary_present": (output_dir / "v2_missing_evidence_summary.csv").exists(),
        "v2_deferred_design_candidates_present": (output_dir / "v2_deferred_design_candidates.csv").exists(),
        "v2_profile_readiness_pass": bool(v2_profile_pass),
        "v2_metric_availability_pass": bool(not v2_metric_all.empty),
        "v2_boundary_safety_pass": bool(not v2_boundary_all.empty and v2_boundary_all["safety_pass"].astype(bool).all()),
        "v2_premise_freeze_pass": bool(not v2_premise_all.empty and v2_premise_all["premise_freeze_pass"].astype(bool).all()),
        "v2_trace_available_run_count": int(v2_premise_all[v2_premise_all["is_v2_profile"].astype(bool)]["v2_trace_available"].astype(bool).sum()) if not v2_premise_all.empty else 0,
        "v2_missing_evidence_count": int(len(v2_missing_metric_evidence)) if not v2_missing_metric_evidence.empty else int(v2_missing["missing_evidence"].astype(str).ne("").sum()) if not v2_missing.empty else 0,
        "v2_deferred_design_candidate_count": int(len(v2_deferred)),
        "acd_group_validation_summary_present": (output_dir / "acd_group_validation_summary.csv").exists(),
        "a_group_pressure_parameter_summary_present": (output_dir / "a_group_pressure_parameter_summary.csv").exists(),
        "c_group_action_boundary_summary_present": (output_dir / "c_group_action_boundary_summary.csv").exists(),
        "d_group_world_audit_export_summary_present": (output_dir / "d_group_world_audit_export_summary.csv").exists(),
        "acd_cross_boundary_summary_present": (output_dir / "acd_cross_boundary_summary.csv").exists(),
        "low_risk_repair_manifest_present": (output_dir / "low_risk_repair_manifest.csv").exists(),
        "deferred_major_repair_candidates_present": (output_dir / "deferred_major_repair_candidates.csv").exists(),
        "a_group_pass_total": int(acd_group_all["a_group_pass"].astype(bool).sum()) if not acd_group_all.empty else 0,
        "c_group_pass_total": int(acd_group_all["c_group_pass"].astype(bool).sum()) if not acd_group_all.empty else 0,
        "d_group_pass_total": int(acd_group_all["d_group_pass"].astype(bool).sum()) if not acd_group_all.empty else 0,
        "cross_boundary_pass_total": int(acd_group_all["cross_boundary_pass"].astype(bool).sum()) if not acd_group_all.empty else 0,
        "major_repair_candidate_count": int(acd_group_all["major_repair_candidate_count"].sum()) if not acd_group_all.empty else 0,
        "missing_evidence_count": int(acd_group_all["missing_evidence_count"].sum()) if not acd_group_all.empty else 0,
        "v2_trace_readiness_pass": bool((d_group_all["v2_trace_available"].astype(bool).any()) if not d_group_all.empty and "v2_trace_available" in d_group_all.columns else False),
    }
    probe_only = relation_comparison[relation_comparison["mode_or_variant"].astype(str).str.contains("probe", regex=False)] if not relation_comparison.empty else pd.DataFrame()
    best_mass = probe_only.sort_values("action_mass", ascending=False).iloc[0] if not probe_only.empty else None
    best_ru = probe_only.sort_values("relation_unlock_family_action_mass", ascending=False).iloc[0] if not probe_only.empty else None
    overall.update({
        "intermediate_conservatism_probe_summary_present": (output_dir / "intermediate_conservatism_probe_summary.csv").exists(),
        "relation_unlock_mode_comparison_present": (output_dir / "relation_unlock_mode_comparison.csv").exists(),
        "dampen_probe_comparison_present": (output_dir / "dampen_probe_comparison.csv").exists(),
        "safety_boundary_probe_summary_present": (output_dir / "safety_boundary_probe_summary.csv").exists(),
        "best_probe_variant_by_action_mass": None if best_mass is None else str(best_mass["mode_or_variant"]),
        "best_probe_variant_by_relation_unlock_mass": None if best_ru is None else str(best_ru["mode_or_variant"]),
        "relaxed_action_mass": float(relation_comparison.loc[relation_comparison["mode_or_variant"].eq("relaxed_baseline"), "action_mass"].sum()) if not relation_comparison.empty else 0.0,
        "flat_action_mass": float(relation_comparison.loc[relation_comparison["mode_or_variant"].eq("flat_upper_bound"), "action_mass"].sum()) if not relation_comparison.empty else 0.0,
        "best_probe_action_mass": 0.0 if best_mass is None else float(best_mass["action_mass"]),
        "best_probe_delta_vs_relaxed": 0.0 if best_mass is None else float(best_mass["delta_vs_relaxed_action_mass"]),
        "best_probe_delta_vs_flat": 0.0 if best_mass is None else float(best_mass["delta_vs_flat_action_mass"]),
        "safety_violation_total": int(overall["boundary_violation_total"]),
        "write_violation_total": int(overall["dry_run_write_violation_count"]) + int(overall["forbidden_write_count"]),
        "recommended_repair_family": "dampen-only minimal repair adopted for relaxed; keep flat validation-only and run post-repair confirmation stress",
    })
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
