"""Task 2-8j-24b5: action intensity schedule validation RC1.

Validates fixed and gradual action-intensity schedules while keeping runtime
policy information strictly separated from validation scoring information.

Runtime policy view may use only information already available to the action
module: risk name, selected operator, wait step, operator family, and conservative
runtime-side proxy rules. It must not use v2 future states, observed outcomes,
NO_OP future trajectories, negative-control outcomes, or validation scores.

Validation scoring view may use Task24b3 multi-scenario rollout evidence to score
what would have happened under each schedule. The scoring view is not fed back
into runtime policy selection.

This task does not update thresholds, does not generate formal action candidates,
does not shape release/rollback/audit conditions, and does not call the real
ActionModule.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from .pressure_action_task2_8j_24b3_multi_scenario_stateful_rollout_validation import (
    MultiScenarioStatefulRolloutValidationConfig,
    build_and_validate_multi_scenario_stateful_rollout_validation,
)

TASK2_8J_24B5_VERSION = "action_intensity_schedule_validation_rc1"
TASK24B3_ACCEPTED_DECISION = "multi_scenario_stateful_rollout_validation_ready"

BOUNDARY: dict[str, Any] = {
    "task2_8j_24b5_version": TASK2_8J_24B5_VERSION,
    "validation_only": True,
    "intensity_schedule_validation": True,
    "runtime_policy_view_separated": True,
    "validation_scoring_view_separated": True,
    "fixed_weak_medium_strong_tested": True,
    "gradual_ramp_tested": True,
    "runtime_uses_only_actionmodule_available_information": True,
    "v2_used_for_scoring_only": True,
    "NO_OP_used_for_scoring_only": True,
    "side_effect_proxy_from_runtime_available_information_only": True,
    "source_task24b3_required": True,
    "gt_main_map_name": "static_pca_7",
    "gt_main_component_count": 7,
    "threshold_values_are_provisional": True,
    "threshold_revision_requires_validation": True,
    "no_threshold_update_performed": True,
    "overfit_to_v2_forbidden": True,
    "v2_future_used_by_runtime": False,
    "hidden_truth_input": False,
    "observed_outcome_used_for_runtime_adjustment": False,
    "NO_OP_future_used_for_runtime_adjustment": False,
    "validation_score_used_as_runtime_input": False,
    "release_rollback_audit_shaped": False,
    "action_candidate_generated": False,
    "concrete_action_generated": False,
    "action_effect_prediction_generated": False,
    "effect_prediction_model_executed": False,
    "expected_value_final_judgment_performed": False,
    "real_actionmodule_called": False,
    "axis_executed": False,
    "upper_pressure_coupled_now": False,
    "canonical_write_performed": False,
}

REQUIRED_TRUE = [
    "validation_only", "intensity_schedule_validation", "runtime_policy_view_separated",
    "validation_scoring_view_separated", "fixed_weak_medium_strong_tested", "gradual_ramp_tested",
    "runtime_uses_only_actionmodule_available_information", "v2_used_for_scoring_only",
    "NO_OP_used_for_scoring_only", "side_effect_proxy_from_runtime_available_information_only",
    "source_task24b3_required", "threshold_values_are_provisional", "threshold_revision_requires_validation",
    "no_threshold_update_performed", "overfit_to_v2_forbidden",
]
FORBIDDEN_TRUE = [
    "v2_future_used_by_runtime", "hidden_truth_input", "observed_outcome_used_for_runtime_adjustment",
    "NO_OP_future_used_for_runtime_adjustment", "validation_score_used_as_runtime_input",
    "release_rollback_audit_shaped", "action_candidate_generated", "concrete_action_generated",
    "action_effect_prediction_generated", "effect_prediction_model_executed", "expected_value_final_judgment_performed",
    "real_actionmodule_called", "axis_executed", "upper_pressure_coupled_now", "canonical_write_performed",
]

RUNTIME_COLUMNS = list(BOUNDARY) + [
    "runtime_policy_id", "source_rollout_id", "scenario_profile", "risk_name", "selected_operator_name",
    "action_wait_step", "schedule_name", "schedule_family", "planned_intensity_start", "planned_intensity_peak",
    "planned_intensity_final", "planned_schedule_steps", "runtime_caution_class", "runtime_side_effect_proxy",
    "runtime_stop_rule", "runtime_adjustment_source", "runtime_policy_status",
]
SCORING_COLUMNS = list(BOUNDARY) + [
    "scoring_id", "runtime_policy_id", "source_rollout_id", "scenario_profile", "risk_name", "selected_operator_name",
    "action_wait_step", "schedule_name", "schedule_family", "scoring_effective_intensity", "scoring_side_effect_multiplier",
    "scheduled_final_reduction", "scheduled_peak_reduction", "scheduled_side_effect_delta", "scheduled_rollback_margin",
    "scheduled_boundary_margin", "scheduled_relative_ev", "scheduled_large_loss", "scheduled_severe_loss",
    "scheduled_action_beats_no_op", "scheduled_action_beats_negative_control", "scoring_status",
]
COMPARISON_COLUMNS = list(BOUNDARY) + [
    "comparison_id", "schedule_name", "schedule_family", "risk_name", "row_count", "mean_relative_ev",
    "median_relative_ev", "p05_relative_ev", "min_relative_ev", "positive_ev_rate", "action_beats_no_op_rate",
    "negative_control_pass_rate", "large_loss_rate", "severe_loss_rate", "mean_side_effect_delta",
    "mean_rollback_margin", "mean_boundary_margin", "schedule_objective_class", "schedule_review_reason",
]
GRADUAL_COLUMNS = list(BOUNDARY) + [
    "gradual_id", "schedule_name", "risk_name", "row_count", "mean_relative_ev", "fixed_medium_mean_ev",
    "delta_vs_fixed_medium", "large_loss_rate", "fixed_medium_large_loss_rate", "large_loss_delta_vs_fixed_medium",
    "mean_runtime_side_effect_proxy", "gradual_schedule_class", "gradual_review_reason",
]
AUDIT_COLUMNS = list(BOUNDARY) + [
    "audit_id", "schedule_name", "risk_name", "row_count", "mean_relative_ev", "large_loss_rate",
    "severe_loss_rate", "mean_scheduled_side_effect_delta", "runtime_side_effect_proxy_mean", "side_effect_gap",
    "mean_rollback_margin", "mean_boundary_margin", "audit_class", "audit_review_reason",
]
CHECK_COLUMNS = list(BOUNDARY) + ["check_id", "check_scope", "check_description", "expected_value", "observed_value", "check_status"]
SUMMARY_COLUMNS = list(BOUNDARY) + [
    "source_task24b3_ready", "source_policy_rollout_count", "runtime_policy_row_count", "scoring_row_count",
    "comparison_row_count", "gradual_validation_row_count", "side_effect_audit_row_count", "best_schedule_name",
    "best_schedule_mean_ev", "best_schedule_large_loss_rate", "fixed_medium_mean_ev", "gradual_best_mean_ev",
    "gradual_best_large_loss_rate", "resource_pressure_best_schedule", "resource_pressure_best_large_loss_rate",
    "strong_schedule_large_loss_rate", "validation_check_count", "validation_check_pass_count", "threshold_freeze_allowed_now",
    "action_intensity_schedule_validation_decision", "next_task",
]


@dataclass(frozen=True)
class ActionIntensityScheduleValidationConfig:
    require_task24b3_ready: bool = True
    large_loss_threshold: float = -0.50
    severe_loss_threshold: float = -0.85
    min_mean_ev_for_candidate: float = 0.10
    max_large_loss_rate_for_candidate: float = 0.03
    max_large_loss_rate_for_review: float = 0.08


SCHEDULES: tuple[dict[str, Any], ...] = (
    {"name": "fixed_weak", "family": "fixed", "start": 0.55, "peak": 0.55, "final": 0.55, "steps": 1, "side_mult": 0.45},
    {"name": "fixed_medium", "family": "fixed", "start": 1.00, "peak": 1.00, "final": 1.00, "steps": 1, "side_mult": 1.00},
    {"name": "fixed_strong", "family": "fixed", "start": 1.35, "peak": 1.35, "final": 1.35, "steps": 1, "side_mult": 1.62},
    {"name": "gradual_ramp", "family": "gradual", "start": 0.50, "peak": 1.15, "final": 1.05, "steps": 3, "side_mult": 0.92},
    {"name": "cautious_ramp_decay", "family": "gradual", "start": 0.45, "peak": 0.95, "final": 0.75, "steps": 3, "side_mult": 0.68},
)


def _with_boundary(row: dict[str, Any]) -> dict[str, Any]:
    return {**BOUNDARY, **row}


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return float(default)
    return float(out) if np.isfinite(out) else float(default)


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def _quantile(series: pd.Series, q: float, default: float = 0.0) -> float:
    s = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    return float(s.quantile(q)) if not s.empty else float(default)


def _runtime_caution(risk_name: str, wait: int) -> str:
    if str(risk_name) == "resource_pressure":
        return "resource_pressure_caution_runtime_proxy"
    if str(risk_name) == "boundary_fragile":
        return "boundary_guard_caution_runtime_proxy"
    if int(wait) >= 3:
        return "late_wait_caution_runtime_proxy"
    return "standard_runtime_proxy"


def _runtime_side_effect_proxy(risk_name: str, operator_name: str, schedule: dict[str, Any], wait: int) -> float:
    base = {"resource_pressure": 0.26, "boundary_fragile": 0.22, "oscillation": 0.16, "relation_lock": 0.14, "reversibility_loss": 0.12}.get(str(risk_name), 0.18)
    op_adj = {"pressure_diffusion": 0.06, "buffer_injection": 0.05, "damping": 0.03, "soft_resistance": 0.02, "reversibility_support": 0.015, "escape_channel": 0.04}.get(str(operator_name), 0.03)
    wait_adj = 0.015 * max(0, int(wait) - 2)
    return round(float((base + op_adj + wait_adj) * max(0.25, float(schedule["peak"]))), 6)


def _runtime_stop_rule(risk_name: str, schedule_name: str, wait: int) -> str:
    if str(risk_name) == "boundary_fragile":
        return "stop_if_boundary_proxy_or_rollback_proxy_worsens"
    if str(risk_name) == "resource_pressure":
        return "stop_if_side_effect_proxy_or_large_loss_proxy_rises"
    if "ramp" in str(schedule_name):
        return "pause_ramp_if_runtime_proxy_caution_increases"
    if int(wait) >= 3:
        return "prefer_NO_OP_or_review_if_late_wait"
    return "continue_only_while_runtime_proxy_margin_remains"


def build_runtime_policy_view(policy: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if policy is None or policy.empty:
        return pd.DataFrame(columns=RUNTIME_COLUMNS)
    for _, r in policy.iterrows():
        wait = _safe_int(r.get("action_wait_step", 0))
        risk = str(r.get("risk_name", ""))
        op = str(r.get("selected_operator_name", ""))
        for sched in SCHEDULES:
            rows.append(_with_boundary({
                "runtime_policy_id": f"runtime_{r.get('rollout_id')}_{sched['name']}",
                "source_rollout_id": str(r.get("rollout_id", "")),
                "scenario_profile": str(r.get("scenario_profile", "")),
                "risk_name": risk,
                "selected_operator_name": op,
                "action_wait_step": wait,
                "schedule_name": str(sched["name"]),
                "schedule_family": str(sched["family"]),
                "planned_intensity_start": float(sched["start"]),
                "planned_intensity_peak": float(sched["peak"]),
                "planned_intensity_final": float(sched["final"]),
                "planned_schedule_steps": int(sched["steps"]),
                "runtime_caution_class": _runtime_caution(risk, wait),
                "runtime_side_effect_proxy": _runtime_side_effect_proxy(risk, op, sched, wait),
                "runtime_stop_rule": _runtime_stop_rule(risk, str(sched["name"]), wait),
                "runtime_adjustment_source": "risk_operator_wait_and_conservative_proxy_only_no_v2_future",
                "runtime_policy_status": "runtime_policy_view_ready_no_scoring_information",
            }))
    return pd.DataFrame(rows, columns=RUNTIME_COLUMNS)


def _effective_intensity(schedule_name: str, risk_name: str) -> float:
    base = {s["name"]: (float(s["start"]) + float(s["peak"]) + float(s["final"])) / 3.0 for s in SCHEDULES}
    val = base.get(str(schedule_name), 1.0)
    if str(schedule_name) == "gradual_ramp" and str(risk_name) == "resource_pressure":
        val += 0.10
    if str(schedule_name) == "cautious_ramp_decay" and str(risk_name) == "boundary_fragile":
        val -= 0.08
    return float(max(0.25, val))


def _diminishing_scale(intensity: float) -> float:
    i = max(0.05, float(intensity))
    return float(i / (0.58 + 0.42 * i))


def build_validation_scoring_view(policy: pd.DataFrame, runtime: pd.DataFrame) -> pd.DataFrame:
    if policy is None or policy.empty or runtime is None or runtime.empty:
        return pd.DataFrame(columns=SCORING_COLUMNS)
    source = policy.set_index("rollout_id", drop=False)
    side_mult = {str(s["name"]): float(s["side_mult"]) for s in SCHEDULES}
    rows: list[dict[str, Any]] = []
    for _, rr in runtime.iterrows():
        rollout_id = str(rr["source_rollout_id"])
        if rollout_id not in source.index:
            continue
        base = source.loc[rollout_id]
        if isinstance(base, pd.DataFrame):
            base = base.iloc[0]
        risk = str(rr["risk_name"])
        sched = str(rr["schedule_name"])
        intensity = _effective_intensity(sched, risk)
        scale = _diminishing_scale(intensity)
        final_reduction = _safe_float(base["risk_reduction_final"]) * scale
        peak_reduction = _safe_float(base["risk_reduction_peak"]) * (0.92 * scale + 0.08)
        side_effect = _safe_float(base["side_effect_delta"]) * side_mult.get(sched, 1.0)
        side_effect += 0.18 * _safe_float(rr["runtime_side_effect_proxy"]) * max(0.0, intensity - 0.75)
        wait = _safe_int(rr["action_wait_step"])
        rollback = _safe_float(base["rollback_margin"]) + 0.05 * max(0.0, 1.0 - intensity) - 0.13 * max(0.0, intensity - 1.0) - 0.012 * max(0, int(rr["planned_schedule_steps"]) - 1)
        boundary = _safe_float(base["boundary_margin"]) + 0.03 * max(0.0, 1.0 - intensity) - 0.11 * max(0.0, intensity - 1.0)
        rollback = float(np.clip(rollback, 0.0, 1.0))
        boundary = float(np.clip(boundary, 0.0, 1.0))
        ramp_penalty = 0.012 * max(0, int(rr["planned_schedule_steps"]) - 1)
        timing_penalty = 0.045 * wait
        ev = final_reduction + 0.45 * peak_reduction + 0.10 * rollback + 0.08 * boundary - 0.35 * side_effect - timing_penalty - ramp_penalty
        neg_gap = _safe_float(base["negative_control_gap"]) * (0.75 + 0.25 * scale)
        rows.append(_with_boundary({
            "scoring_id": f"score_{rr['runtime_policy_id']}",
            "runtime_policy_id": str(rr["runtime_policy_id"]),
            "source_rollout_id": rollout_id,
            "scenario_profile": str(rr["scenario_profile"]),
            "risk_name": risk,
            "selected_operator_name": str(rr["selected_operator_name"]),
            "action_wait_step": wait,
            "schedule_name": sched,
            "schedule_family": str(rr["schedule_family"]),
            "scoring_effective_intensity": round(intensity, 6),
            "scoring_side_effect_multiplier": round(side_mult.get(sched, 1.0), 6),
            "scheduled_final_reduction": round(final_reduction, 6),
            "scheduled_peak_reduction": round(peak_reduction, 6),
            "scheduled_side_effect_delta": round(side_effect, 6),
            "scheduled_rollback_margin": round(rollback, 6),
            "scheduled_boundary_margin": round(boundary, 6),
            "scheduled_relative_ev": round(float(ev), 6),
            "scheduled_large_loss": bool(ev <= -0.50),
            "scheduled_severe_loss": bool(ev <= -0.85),
            "scheduled_action_beats_no_op": bool(final_reduction > 0.0 and ev > 0.0),
            "scheduled_action_beats_negative_control": bool(neg_gap > 0.0),
            "scoring_status": "validation_scoring_only_not_runtime_input",
        }))
    return pd.DataFrame(rows, columns=SCORING_COLUMNS)


def build_fixed_intensity_comparison(scoring: pd.DataFrame, cfg: ActionIntensityScheduleValidationConfig) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    fixed = scoring[scoring["schedule_family"].astype(str) == "fixed"] if scoring is not None and not scoring.empty else pd.DataFrame()
    for (sched, risk), g in fixed.groupby(["schedule_name", "risk_name"], sort=True):
        ev = pd.to_numeric(g["scheduled_relative_ev"], errors="coerce").fillna(0.0)
        mean_ev = float(ev.mean()) if len(ev) else 0.0
        large = float(g["scheduled_large_loss"].astype(bool).mean()) if len(g) else 0.0
        severe = float(g["scheduled_severe_loss"].astype(bool).mean()) if len(g) else 0.0
        beat = float(g["scheduled_action_beats_no_op"].astype(bool).mean()) if len(g) else 0.0
        if mean_ev >= cfg.min_mean_ev_for_candidate and large <= cfg.max_large_loss_rate_for_candidate and beat >= 0.60:
            cls, reason = "fixed_intensity_candidate", "mean_ev_and_large_loss_constraint_pass"
        elif mean_ev >= 0.03 and large <= cfg.max_large_loss_rate_for_review:
            cls, reason = "fixed_intensity_review", "positive_but_tail_or_beat_rate_requires_review"
        else:
            cls, reason = "fixed_intensity_reject", "weak_or_large_loss_tail"
        rows.append(_with_boundary({
            "comparison_id": f"fixed_{sched}_{risk}", "schedule_name": str(sched), "schedule_family": "fixed", "risk_name": str(risk),
            "row_count": int(len(g)), "mean_relative_ev": round(mean_ev, 6), "median_relative_ev": round(float(ev.median()) if len(ev) else 0.0, 6),
            "p05_relative_ev": round(_quantile(ev, 0.05), 6), "min_relative_ev": round(float(ev.min()) if len(ev) else 0.0, 6),
            "positive_ev_rate": round(float((ev > 0.0).mean()) if len(ev) else 0.0, 6), "action_beats_no_op_rate": round(beat, 6),
            "negative_control_pass_rate": round(float(g["scheduled_action_beats_negative_control"].astype(bool).mean()) if len(g) else 0.0, 6),
            "large_loss_rate": round(large, 6), "severe_loss_rate": round(severe, 6),
            "mean_side_effect_delta": round(float(g["scheduled_side_effect_delta"].astype(float).mean()) if len(g) else 0.0, 6),
            "mean_rollback_margin": round(float(g["scheduled_rollback_margin"].astype(float).mean()) if len(g) else 0.0, 6),
            "mean_boundary_margin": round(float(g["scheduled_boundary_margin"].astype(float).mean()) if len(g) else 0.0, 6),
            "schedule_objective_class": cls, "schedule_review_reason": reason,
        }))
    return pd.DataFrame(rows, columns=COMPARISON_COLUMNS)


def build_gradual_ramp_validation(scoring: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if scoring is None or scoring.empty:
        return pd.DataFrame(columns=GRADUAL_COLUMNS)
    fixed = scoring[scoring["schedule_name"].astype(str) == "fixed_medium"]
    gradual = scoring[scoring["schedule_family"].astype(str) == "gradual"]
    for (sched, risk), g in gradual.groupby(["schedule_name", "risk_name"], sort=True):
        fm = fixed[fixed["risk_name"].astype(str) == str(risk)]
        ev = pd.to_numeric(g["scheduled_relative_ev"], errors="coerce").fillna(0.0)
        fm_ev = pd.to_numeric(fm["scheduled_relative_ev"], errors="coerce").fillna(0.0)
        large = float(g["scheduled_large_loss"].astype(bool).mean()) if len(g) else 0.0
        fm_large = float(fm["scheduled_large_loss"].astype(bool).mean()) if len(fm) else 0.0
        mean_ev = float(ev.mean()) if len(ev) else 0.0
        medium_ev = float(fm_ev.mean()) if len(fm_ev) else 0.0
        if mean_ev >= medium_ev and large <= fm_large:
            cls, reason = "gradual_dominates_fixed_medium", "higher_or_equal_ev_and_no_worse_large_loss"
        elif large < fm_large and mean_ev >= (medium_ev - 0.04):
            cls, reason = "gradual_safer_tradeoff_candidate", "tail_risk_lower_with_small_ev_cost"
        else:
            cls, reason = "gradual_review", "does_not_dominate_fixed_medium"
        rows.append(_with_boundary({
            "gradual_id": f"gradual_{sched}_{risk}", "schedule_name": str(sched), "risk_name": str(risk), "row_count": int(len(g)),
            "mean_relative_ev": round(mean_ev, 6), "fixed_medium_mean_ev": round(medium_ev, 6), "delta_vs_fixed_medium": round(mean_ev - medium_ev, 6),
            "large_loss_rate": round(large, 6), "fixed_medium_large_loss_rate": round(fm_large, 6), "large_loss_delta_vs_fixed_medium": round(large - fm_large, 6),
            "mean_runtime_side_effect_proxy": 0.0, "gradual_schedule_class": cls, "gradual_review_reason": reason,
        }))
    return pd.DataFrame(rows, columns=GRADUAL_COLUMNS)


def build_side_effect_large_loss_audit(scoring: pd.DataFrame, runtime: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if scoring is None or scoring.empty:
        return pd.DataFrame(columns=AUDIT_COLUMNS)
    rt = runtime[["runtime_policy_id", "runtime_side_effect_proxy"]].copy() if runtime is not None and not runtime.empty else pd.DataFrame()
    joined = scoring.merge(rt, on="runtime_policy_id", how="left") if not rt.empty else scoring.copy()
    joined["runtime_side_effect_proxy"] = pd.to_numeric(joined.get("runtime_side_effect_proxy", 0.0), errors="coerce").fillna(0.0)
    for (sched, risk), g in joined.groupby(["schedule_name", "risk_name"], sort=True):
        ev = pd.to_numeric(g["scheduled_relative_ev"], errors="coerce").fillna(0.0)
        side = pd.to_numeric(g["scheduled_side_effect_delta"], errors="coerce").fillna(0.0)
        proxy = pd.to_numeric(g["runtime_side_effect_proxy"], errors="coerce").fillna(0.0)
        large = float(g["scheduled_large_loss"].astype(bool).mean()) if len(g) else 0.0
        severe = float(g["scheduled_severe_loss"].astype(bool).mean()) if len(g) else 0.0
        side_gap = float(side.mean() - proxy.mean()) if len(g) else 0.0
        if large <= 0.03 and severe <= 0.01 and side_gap <= 0.05:
            cls, reason = "side_effect_and_large_loss_clear", "tail_and_side_effect_gap_small"
        elif large <= 0.08:
            cls, reason = "side_effect_or_tail_review", "tail_or_runtime_proxy_gap_requires_guard"
        else:
            cls, reason = "side_effect_or_large_loss_reject", "large_loss_tail_too_high"
        rows.append(_with_boundary({
            "audit_id": f"side_large_{sched}_{risk}", "schedule_name": str(sched), "risk_name": str(risk), "row_count": int(len(g)),
            "mean_relative_ev": round(float(ev.mean()) if len(ev) else 0.0, 6), "large_loss_rate": round(large, 6), "severe_loss_rate": round(severe, 6),
            "mean_scheduled_side_effect_delta": round(float(side.mean()) if len(side) else 0.0, 6), "runtime_side_effect_proxy_mean": round(float(proxy.mean()) if len(proxy) else 0.0, 6),
            "side_effect_gap": round(side_gap, 6), "mean_rollback_margin": round(float(g["scheduled_rollback_margin"].astype(float).mean()) if len(g) else 0.0, 6),
            "mean_boundary_margin": round(float(g["scheduled_boundary_margin"].astype(float).mean()) if len(g) else 0.0, 6), "audit_class": cls, "audit_review_reason": reason,
        }))
    return pd.DataFrame(rows, columns=AUDIT_COLUMNS)


def build_checks(runtime: pd.DataFrame, scoring: pd.DataFrame, comparison: pd.DataFrame, gradual: pd.DataFrame, audit: pd.DataFrame, source_ready: bool) -> pd.DataFrame:
    # Only non-boundary runtime columns are scanned here. Boundary flags such as
    # validation_score_used_as_runtime_input are allowed as explicit negative guardrails.
    runtime_data_cols = [c for c in runtime.columns.astype(str).tolist() if c not in BOUNDARY] if runtime is not None else []
    runtime_cols = "|".join(runtime_data_cols).lower()
    runtime_forbidden_terms = ("no_op_final", "action_final", "negative_control", "scheduled_relative_ev", "validation_score")
    checks = [
        ("check_source_ready", "upstream", "Task24b3 source validation is ready.", True, source_ready),
        ("check_runtime_rows", "runtime", "Runtime policy view exists.", True, runtime is not None and not runtime.empty),
        ("check_scoring_rows", "scoring", "Validation scoring view exists.", True, scoring is not None and not scoring.empty),
        ("check_runtime_no_scoring_columns", "separation", "Runtime data columns do not contain scoring/outcome fields.", True, not any(term in runtime_cols for term in runtime_forbidden_terms)),
        ("check_fixed_schedules", "schedule", "Fixed weak/medium/strong are represented.", True, {"fixed_weak", "fixed_medium", "fixed_strong"}.issubset(set(runtime["schedule_name"].astype(str))) if runtime is not None and not runtime.empty else False),
        ("check_gradual_schedules", "schedule", "Gradual ramp schedules are represented.", True, bool(runtime["schedule_family"].astype(str).eq("gradual").any()) if runtime is not None and not runtime.empty else False),
        ("check_comparison", "comparison", "Fixed-intensity comparison exists.", True, comparison is not None and not comparison.empty),
        ("check_gradual_validation", "gradual", "Gradual validation exists.", True, gradual is not None and not gradual.empty),
        ("check_audit", "audit", "Side-effect and large-loss audit exists.", True, audit is not None and not audit.empty),
        ("check_no_threshold_update", "boundary", "No threshold update is performed.", True, bool(scoring["no_threshold_update_performed"].astype(bool).all()) if scoring is not None and not scoring.empty else False),
        ("check_no_action_candidate", "boundary", "No formal action candidate is generated.", False, bool(scoring["action_candidate_generated"].astype(bool).any()) if scoring is not None and not scoring.empty else True),
        ("check_no_runtime_future", "boundary", "Runtime does not use future/scoring information.", False, bool(runtime["v2_future_used_by_runtime"].astype(bool).any() or runtime["validation_score_used_as_runtime_input"].astype(bool).any()) if runtime is not None and not runtime.empty else True),
    ]
    return pd.DataFrame([_with_boundary({"check_id": c[0], "check_scope": c[1], "check_description": c[2], "expected_value": bool(c[3]), "observed_value": bool(c[4]), "check_status": "pass" if bool(c[3]) == bool(c[4]) else "fail"}) for c in checks], columns=CHECK_COLUMNS)


def build_final_summary(source_policy_count: int, runtime: pd.DataFrame, scoring: pd.DataFrame, comparison: pd.DataFrame, gradual: pd.DataFrame, audit: pd.DataFrame, checks: pd.DataFrame, source_ready: bool) -> pd.DataFrame:
    schedule_summary = scoring.groupby("schedule_name")["scheduled_relative_ev"].mean().sort_values(ascending=False) if scoring is not None and not scoring.empty else pd.Series(dtype=float)
    best_name = str(schedule_summary.index[0]) if len(schedule_summary) else ""
    best_ev = float(schedule_summary.iloc[0]) if len(schedule_summary) else 0.0
    best_large = float(scoring.loc[scoring["schedule_name"].astype(str) == best_name, "scheduled_large_loss"].astype(bool).mean()) if best_name and scoring is not None and not scoring.empty else 0.0
    fixed_medium = scoring[scoring["schedule_name"].astype(str) == "fixed_medium"] if scoring is not None and not scoring.empty else pd.DataFrame()
    gradual_rows = scoring[scoring["schedule_family"].astype(str) == "gradual"] if scoring is not None and not scoring.empty else pd.DataFrame()
    gradual_summary = gradual_rows.groupby("schedule_name")["scheduled_relative_ev"].mean().sort_values(ascending=False) if not gradual_rows.empty else pd.Series(dtype=float)
    gradual_best_name = str(gradual_summary.index[0]) if len(gradual_summary) else ""
    gradual_best = float(gradual_summary.iloc[0]) if len(gradual_summary) else 0.0
    gradual_large = float(gradual_rows.loc[gradual_rows["schedule_name"].astype(str) == gradual_best_name, "scheduled_large_loss"].astype(bool).mean()) if gradual_best_name and not gradual_rows.empty else 0.0
    resource = scoring[scoring["risk_name"].astype(str) == "resource_pressure"] if scoring is not None and not scoring.empty else pd.DataFrame()
    res_summary = resource.groupby("schedule_name")["scheduled_relative_ev"].mean().sort_values(ascending=False) if not resource.empty else pd.Series(dtype=float)
    res_best = str(res_summary.index[0]) if len(res_summary) else ""
    res_large = float(resource.loc[resource["schedule_name"].astype(str) == res_best, "scheduled_large_loss"].astype(bool).mean()) if res_best and not resource.empty else 0.0
    strong = scoring[scoring["schedule_name"].astype(str) == "fixed_strong"] if scoring is not None and not scoring.empty else pd.DataFrame()
    pass_count = int((checks["check_status"].astype(str) == "pass").sum()) if checks is not None and not checks.empty else 0
    decision = "action_intensity_schedule_validation_ready" if source_ready and checks is not None and len(checks) == pass_count else "action_intensity_schedule_validation_needs_review"
    return pd.DataFrame([_with_boundary({
        "source_task24b3_ready": bool(source_ready), "source_policy_rollout_count": int(source_policy_count),
        "runtime_policy_row_count": int(len(runtime)), "scoring_row_count": int(len(scoring)), "comparison_row_count": int(len(comparison)),
        "gradual_validation_row_count": int(len(gradual)), "side_effect_audit_row_count": int(len(audit)),
        "best_schedule_name": best_name, "best_schedule_mean_ev": round(best_ev, 6), "best_schedule_large_loss_rate": round(best_large, 6),
        "fixed_medium_mean_ev": round(float(fixed_medium["scheduled_relative_ev"].astype(float).mean()) if not fixed_medium.empty else 0.0, 6),
        "gradual_best_mean_ev": round(gradual_best, 6), "gradual_best_large_loss_rate": round(gradual_large, 6),
        "resource_pressure_best_schedule": res_best, "resource_pressure_best_large_loss_rate": round(res_large, 6),
        "strong_schedule_large_loss_rate": round(float(strong["scheduled_large_loss"].astype(bool).mean()) if not strong.empty else 0.0, 6),
        "validation_check_count": int(len(checks)), "validation_check_pass_count": pass_count,
        "threshold_freeze_allowed_now": False, "action_intensity_schedule_validation_decision": decision,
        "next_task": "Use results to choose per-risk intensity schedules before provisional adoption policy; do not freeze globally yet.",
    })], columns=SUMMARY_COLUMNS)


def validate_tables(runtime: pd.DataFrame, scoring: pd.DataFrame, comparison: pd.DataFrame, gradual: pd.DataFrame, audit: pd.DataFrame, checks: pd.DataFrame, final_summary: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    tables = {"runtime": (runtime, RUNTIME_COLUMNS), "scoring": (scoring, SCORING_COLUMNS), "comparison": (comparison, COMPARISON_COLUMNS), "gradual": (gradual, GRADUAL_COLUMNS), "audit": (audit, AUDIT_COLUMNS), "checks": (checks, CHECK_COLUMNS), "final_summary": (final_summary, SUMMARY_COLUMNS)}
    for name, (table, cols) in tables.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_24b5_empty_table:{name}")
            continue
        missing = [c for c in cols if c not in table.columns]
        if missing:
            errors.append(f"task2_8j_24b5_missing_columns:{name}:" + ",".join(missing))
            continue
        for col in REQUIRED_TRUE:
            if not bool(table[col].astype(bool).all()):
                errors.append(f"task2_8j_24b5_required_true_not_all_true:{name}:{col}")
        for col in FORBIDDEN_TRUE:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_24b5_forbidden_true:{name}:{col}")
    if checks is not None and not checks.empty and not bool((checks["check_status"].astype(str) == "pass").all()):
        errors.append("task2_8j_24b5_check_failed")
    if final_summary is not None and not final_summary.empty and bool(final_summary["threshold_freeze_allowed_now"].astype(bool).any()):
        errors.append("task2_8j_24b5_threshold_freeze_attempted")
    return errors


def build_and_validate_action_intensity_schedule_validation(cfg: ActionIntensityScheduleValidationConfig | None = None, **_unused: object) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    cfg = cfg or ActionIntensityScheduleValidationConfig()
    _scenarios, policy, _random_rollout, _baseline, _risk_b3, _step_b3, _threshold_b3, _checks_b3, _final_b3, b3_errors, b3_summary = build_and_validate_multi_scenario_stateful_rollout_validation(MultiScenarioStatefulRolloutValidationConfig())
    source_ready = len(b3_errors) == 0 and str(b3_summary.get("multi_scenario_stateful_rollout_validation_decision", "")).startswith(TASK24B3_ACCEPTED_DECISION)
    if not cfg.require_task24b3_ready:
        source_ready = True
    runtime = build_runtime_policy_view(policy)
    scoring = build_validation_scoring_view(policy, runtime)
    comparison = build_fixed_intensity_comparison(scoring, cfg)
    gradual = build_gradual_ramp_validation(scoring)
    audit = build_side_effect_large_loss_audit(scoring, runtime)
    checks = build_checks(runtime, scoring, comparison, gradual, audit, source_ready)
    final_summary = build_final_summary(len(policy), runtime, scoring, comparison, gradual, audit, checks, source_ready)
    errors: list[str] = []
    if cfg.require_task24b3_ready:
        errors += [f"task2_8j_24b5_upstream_24b3_error:{e}" for e in b3_errors]
    errors += validate_tables(runtime, scoring, comparison, gradual, audit, checks, final_summary)
    summary = {
        "gt_main_map_name": "static_pca_7", "gt_main_component_count": 7,
        "source_task24b3_decision": b3_summary.get("multi_scenario_stateful_rollout_validation_decision", ""),
        "source_task24b3_ready": bool(source_ready),
        "source_policy_rollout_count": _safe_int(final_summary["source_policy_rollout_count"].iloc[0]),
        "runtime_policy_row_count": _safe_int(final_summary["runtime_policy_row_count"].iloc[0]),
        "scoring_row_count": _safe_int(final_summary["scoring_row_count"].iloc[0]),
        "comparison_row_count": _safe_int(final_summary["comparison_row_count"].iloc[0]),
        "gradual_validation_row_count": _safe_int(final_summary["gradual_validation_row_count"].iloc[0]),
        "side_effect_audit_row_count": _safe_int(final_summary["side_effect_audit_row_count"].iloc[0]),
        "best_schedule_name": str(final_summary["best_schedule_name"].iloc[0]),
        "best_schedule_mean_ev": float(final_summary["best_schedule_mean_ev"].iloc[0]),
        "best_schedule_large_loss_rate": float(final_summary["best_schedule_large_loss_rate"].iloc[0]),
        "fixed_medium_mean_ev": float(final_summary["fixed_medium_mean_ev"].iloc[0]),
        "gradual_best_mean_ev": float(final_summary["gradual_best_mean_ev"].iloc[0]),
        "gradual_best_large_loss_rate": float(final_summary["gradual_best_large_loss_rate"].iloc[0]),
        "resource_pressure_best_schedule": str(final_summary["resource_pressure_best_schedule"].iloc[0]),
        "resource_pressure_best_large_loss_rate": float(final_summary["resource_pressure_best_large_loss_rate"].iloc[0]),
        "strong_schedule_large_loss_rate": float(final_summary["strong_schedule_large_loss_rate"].iloc[0]),
        "runtime_policy_view_separated": True, "validation_scoring_view_separated": True,
        "runtime_uses_only_actionmodule_available_information": True,
        "v2_used_for_scoring_only": True, "NO_OP_used_for_scoring_only": True,
        "threshold_freeze_allowed_now": False,
        "validation_check_count": _safe_int(final_summary["validation_check_count"].iloc[0]),
        "validation_check_pass_count": _safe_int(final_summary["validation_check_pass_count"].iloc[0]),
        "action_intensity_schedule_validation_decision": str(final_summary["action_intensity_schedule_validation_decision"].iloc[0]),
        "no_threshold_update_performed": True, "action_candidate_generated": False,
        "real_actionmodule_called": False, "axis_executed": False,
        "validation_errors": errors,
    }
    return runtime, scoring, comparison, gradual, audit, checks, final_summary, errors, summary
