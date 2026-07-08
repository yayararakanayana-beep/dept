"""Task2-8j-29: legacy-primary vs Task2-8j-primary multi-step comparison.

This validation runs matched FullSpec loops for two action-planning routes:

- legacy: existing repaired-policy ActionSurfacePlanning primary route
- task2_8j_primary: Task2-8j operator material promoted to action candidates

The comparison is diagnostic-only.  It does not claim superiority; it checks that
both routes can be run on matched seeds/scenarios and produces readable
per-step comparison tables.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import json

import pandas as pd

from dept2_fullspec_runner_rc1.contracts import FullSpecRunnerConfig
from dept2_fullspec_runner_rc1.runner.fullspec_integrated_closed_loop_runner import run_fullspec_task16

TASK2_8J_29_VERSION = "task2_8j_29_legacy_vs_primary_multistep_comparison_rc1"
TASK2_8J_29_STEPS = 4
TASK2_8J_29_SEED = 42
TASK2_8J_29_SCENARIOS = ["normal", "relation_lock"]
TASK2_8J_29_ROUTES = ["legacy", "task2_8j_primary"]
STATE_DELTA_COLS = [
    "mean_delta_activity",
    "mean_delta_volatility",
    "mean_delta_uncertainty",
    "mean_delta_relation_lock",
    "mean_delta_coupling",
    "mean_delta_exploration",
    "mean_delta_reversibility",
    "mean_delta_entropy",
]


@dataclass(frozen=True)
class RouteRun:
    scenario: str
    route: str
    outputs: dict[str, pd.DataFrame]


def _rows(df: pd.DataFrame | None) -> int:
    return int(len(df)) if df is not None else 0


def _step_rows(df: pd.DataFrame | None, step: int) -> pd.DataFrame:
    if df is None or df.empty or "loop_step" not in df.columns:
        return pd.DataFrame()
    return df[df["loop_step"].astype(int) == int(step)].copy()


def _first_text(df: pd.DataFrame | None, col: str, default: str = "") -> str:
    if df is None or df.empty or col not in df.columns:
        return default
    return str(df[col].iloc[0])


def _first_bool(df: pd.DataFrame | None, col: str, default: bool = False) -> bool:
    if df is None or df.empty or col not in df.columns:
        return bool(default)
    try:
        return bool(df[col].iloc[0])
    except Exception:
        return bool(default)


def _first_float(df: pd.DataFrame | None, col: str, default: float = 0.0) -> float:
    if df is None or df.empty or col not in df.columns:
        return float(default)
    try:
        return float(df[col].iloc[0])
    except Exception:
        return float(default)


def _count_true(df: pd.DataFrame | None, col: str) -> int:
    if df is None or df.empty or col not in df.columns:
        return 0
    return int(df[col].fillna(False).astype(bool).sum())


def _count_text(df: pd.DataFrame | None, col: str, value: str) -> int:
    if df is None or df.empty or col not in df.columns:
        return 0
    return int((df[col].astype(str) == str(value)).sum())


def _safe_unique_join(df: pd.DataFrame | None, col: str) -> str:
    if df is None or df.empty or col not in df.columns:
        return ""
    return "|".join(sorted(set(df[col].dropna().astype(str))))


def _route_config(scenario: str, route: str) -> FullSpecRunnerConfig:
    return FullSpecRunnerConfig(
        steps=TASK2_8J_29_STEPS,
        seed=TASK2_8J_29_SEED,
        scenario=scenario,
        gt_route="static_pca_7_smoke",
        task2_8j_bridge_enabled=(route == "task2_8j_primary"),
        action_planning_route=route,
        canonical_commit_enabled=False,
        canonical_commit_dry_run=True,
        run_baseline_shadow=False,
    )


def run_route(scenario: str, route: str) -> RouteRun:
    cfg = _route_config(scenario, route)
    return RouteRun(scenario=scenario, route=route, outputs=run_fullspec_task16(cfg))


def _per_step_metrics(route_run: RouteRun) -> pd.DataFrame:
    out = route_run.outputs
    rows: list[dict[str, Any]] = []
    for step in range(TASK2_8J_29_STEPS):
        gt = _step_rows(out.get("gt"), step)
        bridge = _step_rows(out.get("task2_8j_bridge_audit"), step)
        planning = _step_rows(out.get("action_surface_planning_audit"), step)
        candidates = _step_rows(out.get("action_candidates"), step)
        gate = _step_rows(out.get("coactivation_gate"), step)
        execution = _step_rows(out.get("action_execution_audit"), step)
        transition = _step_rows(out.get("world_transition_audit"), step)
        action_frame = _step_rows(out.get("action_frame"), step)
        needs = _step_rows(out.get("local_observation_needs"), step)
        action_local_audit = _step_rows(out.get("action_local_audit"), step)

        row: dict[str, Any] = {
            "task2_8j_29_version": TASK2_8J_29_VERSION,
            "scenario": route_run.scenario,
            "route": route_run.route,
            "loop_step": step,
            "gt_route": _first_text(gt, "gt_route_selected"),
            "gt_main_map_name": _first_text(gt, "gt_main_map_name"),
            "gt_main_component_count": int(_first_float(gt, "gt_main_component_count", -1)),
            "static_pca7_view_attached": _first_bool(gt, "static_pca7_view_attached"),
            "legacy_gt_columns_preserved": _first_bool(gt, "legacy_gt_columns_preserved"),
            "bridge_rows": _rows(bridge),
            "bridge_status": _first_text(bridge, "bridge_status", "not_enabled"),
            "task2_8j_24_ready": _first_bool(bridge, "task2_8j_24_ready"),
            "task2_8j_operator_material_rows": int(_first_float(planning, "task2_8j_operator_material_rows", 0.0)),
            "action_planning_route": _first_text(planning, "action_planning_route", route_run.route),
            "planning_audit_status": _first_text(planning, "audit_status"),
            "task2_8j_primary_route_used": _first_bool(planning, "task2_8j_primary_route_used"),
            "task2_8j_material_promoted_to_action_candidates": _first_bool(planning, "task2_8j_material_promoted_to_action_candidates"),
            "action_candidate_rows": _rows(candidates),
            "task2_8j_primary_candidate_rows": _count_true(candidates, "task2_8j_primary_candidate"),
            "legacy_fallback_candidate_rows": _count_true(candidates, "task2_8j_legacy_fallback_candidate"),
            "legacy_primary_candidate_rows": _count_text(candidates, "task2_8j_candidate_source", "legacy_repaired_policy_primary"),
            "action_channels": _safe_unique_join(candidates, "action_channel"),
            "semantic_effects": _safe_unique_join(candidates, "semantic_effect"),
            "action_strength_sum": float(pd.to_numeric(candidates.get("action_strength", pd.Series(dtype=float)), errors="coerce").fillna(0.0).sum()) if not candidates.empty else 0.0,
            "local_observation_need_rows": _rows(needs),
            "task2_8j_primary_need_rows": _count_true(needs, "task2_8j_primary_need_source"),
            "action_local_audit_rows": _rows(action_local_audit),
            "gate_decision": _first_text(gate, "coactivation_gate_decision"),
            "gate_risk_score": _first_float(gate, "coactivation_risk_score"),
            "gate_audit_status": _first_text(gate, "coactivation_gate_audit_status"),
            "action_frame_rows": _rows(action_frame),
            "action_execution_audit_status": _first_text(execution, "audit_status"),
            "actionmodule_input_contract": _first_text(execution, "actionmodule_input_contract"),
            "actionmodule_received_actionframe_only": _first_bool(execution, "actionmodule_received_actionframe_only"),
            "direct_gk_input_to_actionmodule": _first_bool(execution, "direct_gk_input_to_actionmodule"),
            "direct_ot_input_to_actionmodule": _first_bool(execution, "direct_ot_input_to_actionmodule"),
            "direct_parameter_box_input_to_actionmodule": _first_bool(execution, "direct_parameter_box_input_to_actionmodule"),
            "canonical_parameter_write_performed": _first_bool(execution, "canonical_parameter_write_performed"),
            "world_t_before": int(_first_float(transition, "world_t_before", -1)),
            "world_t_after": int(_first_float(transition, "world_t_after", -1)),
            "transition_time_advanced_by_one": bool(int(_first_float(transition, "world_t_after", -1)) == int(_first_float(transition, "world_t_before", -2)) + 1),
            "transition_gk_writeback_performed": _first_bool(transition, "gk_writeback_performed"),
            "transition_ot_writeback_performed": _first_bool(transition, "ot_writeback_performed"),
            "transition_canonical_write_performed": _first_bool(transition, "canonical_parameter_write_performed"),
        }
        for col in STATE_DELTA_COLS:
            row[col] = _first_float(transition, col)
        rows.append(row)
    return pd.DataFrame(rows)


def _pivot_route_delta(per_step: pd.DataFrame) -> pd.DataFrame:
    left = per_step[per_step["route"] == "legacy"].copy()
    right = per_step[per_step["route"] == "task2_8j_primary"].copy()
    merged = left.merge(right, on=["scenario", "loop_step"], suffixes=("_legacy", "_task2_8j"))
    rows: list[dict[str, Any]] = []
    for _, r in merged.iterrows():
        row: dict[str, Any] = {
            "task2_8j_29_version": TASK2_8J_29_VERSION,
            "scenario": r["scenario"],
            "loop_step": int(r["loop_step"]),
            "legacy_candidate_rows": int(r["action_candidate_rows_legacy"]),
            "task2_8j_candidate_rows": int(r["action_candidate_rows_task2_8j"]),
            "candidate_row_delta_task2_minus_legacy": int(r["action_candidate_rows_task2_8j"] - r["action_candidate_rows_legacy"]),
            "legacy_primary_candidate_rows": int(r["legacy_primary_candidate_rows_legacy"]),
            "task2_8j_primary_candidate_rows": int(r["task2_8j_primary_candidate_rows_task2_8j"]),
            "legacy_gate_decision": str(r["gate_decision_legacy"]),
            "task2_8j_gate_decision": str(r["gate_decision_task2_8j"]),
            "gate_decision_changed": bool(str(r["gate_decision_legacy"]) != str(r["gate_decision_task2_8j"])),
            "legacy_gate_risk_score": float(r["gate_risk_score_legacy"]),
            "task2_8j_gate_risk_score": float(r["gate_risk_score_task2_8j"]),
            "gate_risk_delta_task2_minus_legacy": float(r["gate_risk_score_task2_8j"] - r["gate_risk_score_legacy"]),
            "legacy_action_strength_sum": float(r["action_strength_sum_legacy"]),
            "task2_8j_action_strength_sum": float(r["action_strength_sum_task2_8j"]),
            "action_strength_delta_task2_minus_legacy": float(r["action_strength_sum_task2_8j"] - r["action_strength_sum_legacy"]),
            "legacy_transition_time_ok": bool(r["transition_time_advanced_by_one_legacy"]),
            "task2_8j_transition_time_ok": bool(r["transition_time_advanced_by_one_task2_8j"]),
            "legacy_execution_status": str(r["action_execution_audit_status_legacy"]),
            "task2_8j_execution_status": str(r["action_execution_audit_status_task2_8j"]),
            "both_actionframe_only": bool(r["actionmodule_received_actionframe_only_legacy"] and r["actionmodule_received_actionframe_only_task2_8j"]),
        }
        for col in STATE_DELTA_COLS:
            row[f"{col}_legacy"] = float(r[f"{col}_legacy"])
            row[f"{col}_task2_8j"] = float(r[f"{col}_task2_8j"])
            row[f"{col}_delta_task2_minus_legacy"] = float(r[f"{col}_task2_8j"] - r[f"{col}_legacy"])
        rows.append(row)
    return pd.DataFrame(rows)


def _summary(per_step: pd.DataFrame, route_delta: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for scenario in TASK2_8J_29_SCENARIOS:
        ps = per_step[per_step["scenario"] == scenario]
        rd = route_delta[route_delta["scenario"] == scenario]
        legacy = ps[ps["route"] == "legacy"]
        primary = ps[ps["route"] == "task2_8j_primary"]
        rows.append({
            "task2_8j_29_version": TASK2_8J_29_VERSION,
            "scenario": scenario,
            "steps": TASK2_8J_29_STEPS,
            "legacy_steps_observed": int(len(legacy)),
            "task2_8j_steps_observed": int(len(primary)),
            "legacy_all_planning_pass": bool((legacy["planning_audit_status"].astype(str) == "pass").all()),
            "task2_8j_all_planning_pass": bool((primary["planning_audit_status"].astype(str) == "pass").all()),
            "legacy_all_execution_pass": bool((legacy["action_execution_audit_status"].astype(str) == "pass").all()),
            "task2_8j_all_execution_pass": bool((primary["action_execution_audit_status"].astype(str) == "pass").all()),
            "legacy_all_actionframe_only": bool(legacy["actionmodule_received_actionframe_only"].astype(bool).all()),
            "task2_8j_all_actionframe_only": bool(primary["actionmodule_received_actionframe_only"].astype(bool).all()),
            "legacy_total_candidate_rows": int(legacy["action_candidate_rows"].sum()),
            "task2_8j_total_candidate_rows": int(primary["action_candidate_rows"].sum()),
            "task2_8j_total_primary_candidate_rows": int(primary["task2_8j_primary_candidate_rows"].sum()),
            "task2_8j_total_primary_need_rows": int(primary["task2_8j_primary_need_rows"].sum()),
            "gate_decision_changed_steps": int(rd["gate_decision_changed"].astype(bool).sum()) if not rd.empty else 0,
            "mean_gate_risk_delta_task2_minus_legacy": float(rd["gate_risk_delta_task2_minus_legacy"].mean()) if not rd.empty else 0.0,
            "mean_action_strength_delta_task2_minus_legacy": float(rd["action_strength_delta_task2_minus_legacy"].mean()) if not rd.empty else 0.0,
            "comparison_status": "pass" if (
                len(legacy) == TASK2_8J_29_STEPS
                and len(primary) == TASK2_8J_29_STEPS
                and bool((legacy["planning_audit_status"].astype(str) == "pass").all())
                and bool((primary["planning_audit_status"].astype(str) == "pass").all())
                and bool((legacy["action_execution_audit_status"].astype(str) == "pass").all())
                and bool((primary["action_execution_audit_status"].astype(str) == "pass").all())
                and bool(primary["task2_8j_primary_route_used"].astype(bool).all())
                and int(primary["task2_8j_primary_candidate_rows"].sum()) > 0
            ) else "fail",
        })
    return pd.DataFrame(rows)


def build_task2_8j_29_comparison() -> dict[str, pd.DataFrame]:
    route_runs = [run_route(scenario, route) for scenario in TASK2_8J_29_SCENARIOS for route in TASK2_8J_29_ROUTES]
    per_step = pd.concat([_per_step_metrics(rr) for rr in route_runs], ignore_index=True)
    route_delta = _pivot_route_delta(per_step)
    summary = _summary(per_step, route_delta)
    return {
        "task2_8j_29_summary": summary,
        "task2_8j_29_per_step_metrics": per_step,
        "task2_8j_29_route_delta": route_delta,
    }


def write_task2_8j_29_comparison(out_dir: Path) -> dict[str, pd.DataFrame]:
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = build_task2_8j_29_comparison()
    for name, df in outputs.items():
        df.to_csv(out_dir / f"{name}.csv", index=False)
        df.to_json(out_dir / f"{name}.json", orient="records", indent=2, force_ascii=False)
    manifest = {
        "version": TASK2_8J_29_VERSION,
        "steps": TASK2_8J_29_STEPS,
        "seed": TASK2_8J_29_SEED,
        "scenarios": TASK2_8J_29_SCENARIOS,
        "routes": TASK2_8J_29_ROUTES,
        "tables": sorted(outputs),
    }
    (out_dir / "task2_8j_29_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return outputs


if __name__ == "__main__":
    write_task2_8j_29_comparison(Path("results/task2_8j_29_legacy_vs_primary_multistep_comparison"))
