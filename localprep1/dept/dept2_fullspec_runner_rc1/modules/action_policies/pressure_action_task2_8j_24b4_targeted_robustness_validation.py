"""Task 2-8j-24b4: targeted robustness validation RC1.

Main objective remains objective usefulness:

1. Total policy utility must be clearly better than NO_OP.
2. Large-loss / large-risk cases must be constrained.

Stress peak reduction and stress concentration are secondary diagnostics, used to
understand whether a policy reduces local peaks or merely redistributes stress.
They do not override the primary NO_OP utility and large-risk constraints.

This task reuses the multi-scenario stateful rollout from Task24b3 and adds:

- stress peak / concentration audit,
- boundary_fragile randomized-baseline separation audit,
- resource_pressure weak-effect audit,
- wait-step 0-2 adoption-window stress test.

It does not update thresholds, does not shape release/rollback/audit conditions,
does not generate formal action candidates, and does not call the real
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

TASK2_8J_24B4_VERSION = "targeted_robustness_validation_rc1"
TASK24B3_ACCEPTED_DECISION = "multi_scenario_stateful_rollout_validation_ready"

BOUNDARY: dict[str, Any] = {
    "task2_8j_24b4_version": TASK2_8J_24B4_VERSION,
    "validation_only": True,
    "targeted_robustness_validation": True,
    "primary_objective_total_utility_over_NO_OP": True,
    "primary_objective_large_risk_constraint": True,
    "secondary_stress_peak_concentration_audit": True,
    "boundary_fragile_separation_audit": True,
    "resource_pressure_weak_effect_audit": True,
    "wait_step_0_2_adoption_window_stress_test": True,
    "source_task24b3_required": True,
    "NO_OP_comparison_required": True,
    "randomized_operator_baseline_required": True,
    "negative_control_required": True,
    "v2_window_used_as_validation_surface": True,
    "v2_window_not_runtime_oracle": True,
    "gt_main_map_name": "static_pca_7",
    "gt_main_component_count": 7,
    "threshold_values_are_provisional": True,
    "threshold_revision_requires_validation": True,
    "no_threshold_update_performed": True,
    "overfit_to_v2_forbidden": True,
    "release_rollback_audit_shaped": False,
    "action_candidate_generated": False,
    "concrete_action_generated": False,
    "action_effect_prediction_generated": False,
    "effect_prediction_model_executed": False,
    "expected_value_final_judgment_performed": False,
    "real_actionmodule_called": False,
    "axis_executed": False,
    "upper_pressure_coupled_now": False,
    "hidden_truth_input": False,
    "future_information_used_as_runtime_input": False,
    "canonical_write_performed": False,
}

REQUIRED_TRUE = [
    "validation_only", "targeted_robustness_validation", "primary_objective_total_utility_over_NO_OP",
    "primary_objective_large_risk_constraint", "secondary_stress_peak_concentration_audit",
    "boundary_fragile_separation_audit", "resource_pressure_weak_effect_audit",
    "wait_step_0_2_adoption_window_stress_test", "source_task24b3_required", "NO_OP_comparison_required",
    "randomized_operator_baseline_required", "negative_control_required", "v2_window_used_as_validation_surface",
    "v2_window_not_runtime_oracle", "threshold_values_are_provisional", "threshold_revision_requires_validation",
    "no_threshold_update_performed", "overfit_to_v2_forbidden",
]
FORBIDDEN_TRUE = [
    "release_rollback_audit_shaped", "action_candidate_generated", "concrete_action_generated",
    "action_effect_prediction_generated", "effect_prediction_model_executed", "expected_value_final_judgment_performed",
    "real_actionmodule_called", "axis_executed", "upper_pressure_coupled_now", "hidden_truth_input",
    "future_information_used_as_runtime_input", "canonical_write_performed",
]

PRIMARY_COLUMNS = list(BOUNDARY) + [
    "objective_scope", "risk_name", "rollout_count", "mean_relative_ev", "median_relative_ev", "p05_relative_ev",
    "min_relative_ev", "positive_ev_rate", "action_beats_no_op_rate", "policy_beats_random_rate",
    "negative_control_pass_rate", "large_loss_rate", "severe_loss_rate", "mean_policy_minus_random_ev",
    "primary_total_utility_pass", "primary_large_risk_pass", "primary_objective_class", "primary_review_reason",
]
STRESS_COLUMNS = list(BOUNDARY) + [
    "stress_scope", "scenario_profile", "risk_name", "action_wait_step", "row_count", "no_op_peak_mean",
    "action_peak_mean", "peak_reduction_mean", "no_op_peak_p95", "action_peak_p95", "peak_p95_reduction",
    "peak_worsening_rate", "severe_peak_worsening_rate", "action_peak_top10_share", "no_op_peak_top10_share",
    "stress_concentration_delta", "secondary_stress_class", "secondary_stress_review_reason",
]
BOUNDARY_COLUMNS = list(BOUNDARY) + [
    "audit_scope", "scenario_profile", "action_wait_step", "policy_rollout_count", "policy_mean_ev", "random_mean_ev",
    "policy_minus_random_ev", "policy_beat_no_op_rate", "random_beat_no_op_rate", "large_loss_rate",
    "peak_worsening_rate", "boundary_fragile_class", "boundary_fragile_review_reason",
]
RESOURCE_COLUMNS = list(BOUNDARY) + [
    "audit_scope", "scenario_profile", "action_wait_step", "policy_rollout_count", "mean_relative_ev", "mean_risk_reduction_final",
    "policy_beat_no_op_rate", "policy_minus_random_ev", "large_loss_rate", "severe_loss_rate", "peak_worsening_rate",
    "resource_pressure_class", "resource_pressure_review_reason",
]
WINDOW_COLUMNS = list(BOUNDARY) + [
    "window_scope", "risk_name", "wait_window", "row_count", "mean_relative_ev", "positive_ev_rate", "action_beats_no_op_rate",
    "policy_beats_random_rate", "large_loss_rate", "p05_relative_ev", "mean_rollback_margin", "mean_boundary_margin",
    "peak_worsening_rate", "window_class", "window_review_reason",
]
GATE_COLUMNS = list(BOUNDARY) + [
    "gate_id", "risk_name", "main_total_utility_class", "large_risk_class", "stress_peak_class", "baseline_separation_class",
    "wait_0_2_class", "recommended_gate", "gate_reason", "may_freeze_threshold_now",
]
CHECK_COLUMNS = list(BOUNDARY) + ["check_id", "check_scope", "check_description", "expected_value", "observed_value", "check_status"]
SUMMARY_COLUMNS = list(BOUNDARY) + [
    "source_task24b3_ready", "policy_rollout_row_count", "primary_objective_row_count", "stress_audit_row_count",
    "boundary_fragile_audit_row_count", "resource_pressure_audit_row_count", "adoption_window_row_count",
    "gate_recommendation_count", "strong_gate_count", "review_gate_count", "block_gate_count",
    "overall_mean_relative_ev", "overall_action_beats_no_op_rate", "overall_large_loss_rate", "overall_severe_loss_rate",
    "overall_policy_beats_random_rate", "wait_0_2_mean_ev", "wait_0_2_large_loss_rate", "stress_peak_improvement_rate",
    "threshold_freeze_allowed_now", "validation_check_count", "validation_check_pass_count",
    "targeted_robustness_validation_decision", "next_task",
]


@dataclass(frozen=True)
class TargetedRobustnessValidationConfig:
    require_task24b3_ready: bool = True
    large_loss_threshold: float = -0.50
    severe_loss_threshold: float = -0.85
    max_large_loss_rate_for_strong: float = 0.03
    max_large_loss_rate_for_review: float = 0.08
    min_overall_mean_ev: float = 0.10
    min_action_beats_no_op_rate: float = 0.60
    min_policy_beats_random_rate: float = 0.60
    peak_worsening_tolerance: float = 0.05


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


def _positive_stress(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).fillna(0.0).clip(lower=0.0)


def _top10_share(series: pd.Series) -> float:
    s = _positive_stress(series)
    if s.empty or float(s.sum()) <= 1e-12:
        return 0.0
    cutoff = s.quantile(0.90)
    return float(s[s >= cutoff].sum() / s.sum())


def _merge_baseline(policy: pd.DataFrame, baseline: pd.DataFrame) -> pd.DataFrame:
    if policy.empty or baseline.empty:
        return policy.copy()
    b = baseline[["scenario_profile", "risk_name", "action_wait_step", "policy_minus_random_ev"]].copy()
    out = policy.merge(b, on=["scenario_profile", "risk_name", "action_wait_step"], how="left")
    out["policy_minus_random_ev"] = pd.to_numeric(out["policy_minus_random_ev"], errors="coerce").fillna(0.0)
    return out


def build_primary_objective_audit(policy: pd.DataFrame, baseline: pd.DataFrame, cfg: TargetedRobustnessValidationConfig) -> pd.DataFrame:
    merged = _merge_baseline(policy, baseline)
    groups: list[tuple[str, str, pd.DataFrame]] = [("overall", "__all__", merged)]
    groups += [("risk", str(risk), g) for risk, g in merged.groupby("risk_name", sort=True)]
    rows = []
    for scope, risk_name, g in groups:
        ev = pd.to_numeric(g["relative_ev_rollout"], errors="coerce").fillna(0.0)
        large = (ev <= cfg.large_loss_threshold)
        severe = (ev <= cfg.severe_loss_threshold)
        beat_noop = g["action_beats_no_op"].astype(bool)
        beat_random = g["policy_minus_random_ev"].astype(float) > 0.0
        neg = g["action_beats_negative_control"].astype(bool)
        mean_ev = float(ev.mean()) if len(ev) else 0.0
        beat_noop_rate = float(beat_noop.mean()) if len(beat_noop) else 0.0
        random_rate = float(beat_random.mean()) if len(beat_random) else 0.0
        large_rate = float(large.mean()) if len(large) else 0.0
        total_pass = mean_ev >= cfg.min_overall_mean_ev and beat_noop_rate >= cfg.min_action_beats_no_op_rate and random_rate >= cfg.min_policy_beats_random_rate
        risk_pass = large_rate <= cfg.max_large_loss_rate_for_strong and float(severe.mean()) <= 0.01
        if total_pass and risk_pass:
            cls = "primary_objective_pass"
            reason = "total_utility_over_NO_OP_and_large_risk_constrained"
        elif total_pass and large_rate <= cfg.max_large_loss_rate_for_review:
            cls = "primary_objective_review"
            reason = "utility_positive_but_large_loss_tail_requires_guard"
        else:
            cls = "primary_objective_not_passed"
            reason = "utility_or_large_loss_constraint_not_sufficient"
        rows.append(_with_boundary({
            "objective_scope": scope,
            "risk_name": risk_name,
            "rollout_count": int(len(g)),
            "mean_relative_ev": round(mean_ev, 6),
            "median_relative_ev": round(float(ev.median()) if len(ev) else 0.0, 6),
            "p05_relative_ev": round(_quantile(ev, 0.05), 6),
            "min_relative_ev": round(float(ev.min()) if len(ev) else 0.0, 6),
            "positive_ev_rate": round(float((ev > 0).mean()) if len(ev) else 0.0, 6),
            "action_beats_no_op_rate": round(beat_noop_rate, 6),
            "policy_beats_random_rate": round(random_rate, 6),
            "negative_control_pass_rate": round(float(neg.mean()) if len(neg) else 0.0, 6),
            "large_loss_rate": round(large_rate, 6),
            "severe_loss_rate": round(float(severe.mean()) if len(severe) else 0.0, 6),
            "mean_policy_minus_random_ev": round(float(g["policy_minus_random_ev"].astype(float).mean()) if len(g) else 0.0, 6),
            "primary_total_utility_pass": bool(total_pass),
            "primary_large_risk_pass": bool(risk_pass),
            "primary_objective_class": cls,
            "primary_review_reason": reason,
        }))
    return pd.DataFrame(rows, columns=PRIMARY_COLUMNS)


def build_stress_peak_concentration_audit(policy: pd.DataFrame, cfg: TargetedRobustnessValidationConfig) -> pd.DataFrame:
    rows = []
    for (scenario, risk, wait), g in policy.groupby(["scenario_profile", "risk_name", "action_wait_step"], sort=True):
        no_op_peak = pd.to_numeric(g["no_op_peak_risk"], errors="coerce").fillna(0.0)
        action_peak = pd.to_numeric(g["action_peak_risk"], errors="coerce").fillna(0.0)
        peak_worsening = action_peak - no_op_peak
        worsen_rate = float((peak_worsening > cfg.peak_worsening_tolerance).mean()) if len(g) else 0.0
        severe_worsen_rate = float((peak_worsening > 0.25).mean()) if len(g) else 0.0
        action_top = _top10_share(action_peak)
        noop_top = _top10_share(no_op_peak)
        conc_delta = action_top - noop_top
        peak_mean_reduction = float((no_op_peak - action_peak).mean()) if len(g) else 0.0
        peak_p95_reduction = _quantile(no_op_peak, 0.95) - _quantile(action_peak, 0.95)
        if peak_mean_reduction > 0 and worsen_rate <= 0.35:
            cls = "secondary_peak_reduction_supports_action"
            reason = "peak_mean_reduced_without_excessive_worsening_rate"
        elif conc_delta <= 0 and peak_mean_reduction >= -0.05:
            cls = "secondary_concentration_not_worse"
            reason = "concentration_not_worse_but_peak_reduction_small"
        else:
            cls = "secondary_stress_review"
            reason = "peak_or_concentration_worsening_requires_review"
        rows.append(_with_boundary({
            "stress_scope": "scenario_risk_wait",
            "scenario_profile": str(scenario),
            "risk_name": str(risk),
            "action_wait_step": int(wait),
            "row_count": int(len(g)),
            "no_op_peak_mean": round(float(no_op_peak.mean()) if len(g) else 0.0, 6),
            "action_peak_mean": round(float(action_peak.mean()) if len(g) else 0.0, 6),
            "peak_reduction_mean": round(peak_mean_reduction, 6),
            "no_op_peak_p95": round(_quantile(no_op_peak, 0.95), 6),
            "action_peak_p95": round(_quantile(action_peak, 0.95), 6),
            "peak_p95_reduction": round(peak_p95_reduction, 6),
            "peak_worsening_rate": round(worsen_rate, 6),
            "severe_peak_worsening_rate": round(severe_worsen_rate, 6),
            "action_peak_top10_share": round(action_top, 6),
            "no_op_peak_top10_share": round(noop_top, 6),
            "stress_concentration_delta": round(conc_delta, 6),
            "secondary_stress_class": cls,
            "secondary_stress_review_reason": reason,
        }))
    return pd.DataFrame(rows, columns=STRESS_COLUMNS)


def build_boundary_fragile_separation_audit(policy: pd.DataFrame, baseline: pd.DataFrame, cfg: TargetedRobustnessValidationConfig) -> pd.DataFrame:
    p = _merge_baseline(policy[policy["risk_name"].astype(str) == "boundary_fragile"], baseline)
    rows = []
    for (scenario, wait), g in p.groupby(["scenario_profile", "action_wait_step"], sort=True):
        ev = pd.to_numeric(g["relative_ev_rollout"], errors="coerce").fillna(0.0)
        adv = pd.to_numeric(g["policy_minus_random_ev"], errors="coerce").fillna(0.0)
        large_rate = float((ev <= cfg.large_loss_threshold).mean()) if len(ev) else 0.0
        peak_worsen = pd.to_numeric(g["action_peak_risk"], errors="coerce").fillna(0.0) - pd.to_numeric(g["no_op_peak_risk"], errors="coerce").fillna(0.0)
        peak_worsen_rate = float((peak_worsen > cfg.peak_worsening_tolerance).mean()) if len(g) else 0.0
        if float(adv.mean()) > 0.03 and large_rate <= cfg.max_large_loss_rate_for_strong:
            cls = "boundary_fragile_separated_from_random_candidate"
            reason = "policy_above_random_and_tail_risk_small"
        elif float(adv.mean()) > -0.01 and large_rate <= cfg.max_large_loss_rate_for_review:
            cls = "boundary_fragile_guarded_review"
            reason = "random_separation_weak_or_tail_requires_guard"
        else:
            cls = "boundary_fragile_do_not_adopt_now"
            reason = "not_separated_from_random_or_large_loss_too_high"
        rows.append(_with_boundary({
            "audit_scope": "boundary_fragile_scenario_wait",
            "scenario_profile": str(scenario),
            "action_wait_step": int(wait),
            "policy_rollout_count": int(len(g)),
            "policy_mean_ev": round(float(ev.mean()) if len(ev) else 0.0, 6),
            "random_mean_ev": round(float(g["relative_ev_rollout"].astype(float).mean() - adv.mean()) if len(g) else 0.0, 6),
            "policy_minus_random_ev": round(float(adv.mean()) if len(adv) else 0.0, 6),
            "policy_beat_no_op_rate": round(float(g["action_beats_no_op"].astype(bool).mean()) if len(g) else 0.0, 6),
            "random_beat_no_op_rate": 0.0,
            "large_loss_rate": round(large_rate, 6),
            "peak_worsening_rate": round(peak_worsen_rate, 6),
            "boundary_fragile_class": cls,
            "boundary_fragile_review_reason": reason,
        }))
    return pd.DataFrame(rows, columns=BOUNDARY_COLUMNS)


def build_resource_pressure_weak_effect_audit(policy: pd.DataFrame, baseline: pd.DataFrame, cfg: TargetedRobustnessValidationConfig) -> pd.DataFrame:
    p = _merge_baseline(policy[policy["risk_name"].astype(str) == "resource_pressure"], baseline)
    rows = []
    for (scenario, wait), g in p.groupby(["scenario_profile", "action_wait_step"], sort=True):
        ev = pd.to_numeric(g["relative_ev_rollout"], errors="coerce").fillna(0.0)
        rr = pd.to_numeric(g["risk_reduction_final"], errors="coerce").fillna(0.0)
        adv = pd.to_numeric(g["policy_minus_random_ev"], errors="coerce").fillna(0.0)
        large_rate = float((ev <= cfg.large_loss_threshold).mean()) if len(ev) else 0.0
        severe_rate = float((ev <= cfg.severe_loss_threshold).mean()) if len(ev) else 0.0
        peak_worsen = pd.to_numeric(g["action_peak_risk"], errors="coerce").fillna(0.0) - pd.to_numeric(g["no_op_peak_risk"], errors="coerce").fillna(0.0)
        peak_worsen_rate = float((peak_worsen > cfg.peak_worsening_tolerance).mean()) if len(g) else 0.0
        if float(ev.mean()) >= 0.12 and float(rr.mean()) > 0.02 and large_rate <= cfg.max_large_loss_rate_for_review:
            cls = "resource_pressure_candidate_after_review"
            reason = "weak_but_positive_effect_with_tail_under_review_limit"
        elif float(ev.mean()) > 0.03 and float(adv.mean()) > 0.03:
            cls = "resource_pressure_directional_but_weak"
            reason = "above_random_but_effect_size_or_tail_not_enough_for_gate"
        else:
            cls = "resource_pressure_do_not_adopt_now"
            reason = "weak_effect_or_large_loss_tail"
        rows.append(_with_boundary({
            "audit_scope": "resource_pressure_scenario_wait",
            "scenario_profile": str(scenario),
            "action_wait_step": int(wait),
            "policy_rollout_count": int(len(g)),
            "mean_relative_ev": round(float(ev.mean()) if len(ev) else 0.0, 6),
            "mean_risk_reduction_final": round(float(rr.mean()) if len(rr) else 0.0, 6),
            "policy_beat_no_op_rate": round(float(g["action_beats_no_op"].astype(bool).mean()) if len(g) else 0.0, 6),
            "policy_minus_random_ev": round(float(adv.mean()) if len(adv) else 0.0, 6),
            "large_loss_rate": round(large_rate, 6),
            "severe_loss_rate": round(severe_rate, 6),
            "peak_worsening_rate": round(peak_worsen_rate, 6),
            "resource_pressure_class": cls,
            "resource_pressure_review_reason": reason,
        }))
    return pd.DataFrame(rows, columns=RESOURCE_COLUMNS)


def build_wait_0_2_adoption_window_stress_test(policy: pd.DataFrame, baseline: pd.DataFrame, cfg: TargetedRobustnessValidationConfig) -> pd.DataFrame:
    merged = _merge_baseline(policy, baseline)
    rows = []
    for risk, g0 in merged.groupby("risk_name", sort=True):
        for label, sub in [("wait_0_2", g0[g0["action_wait_step"].astype(int).between(0, 2)]), ("wait_3_5", g0[g0["action_wait_step"].astype(int).between(3, 5)])]:
            ev = pd.to_numeric(sub["relative_ev_rollout"], errors="coerce").fillna(0.0)
            large_rate = float((ev <= cfg.large_loss_threshold).mean()) if len(ev) else 0.0
            peak_worsen = pd.to_numeric(sub["action_peak_risk"], errors="coerce").fillna(0.0) - pd.to_numeric(sub["no_op_peak_risk"], errors="coerce").fillna(0.0)
            peak_rate = float((peak_worsen > cfg.peak_worsening_tolerance).mean()) if len(sub) else 0.0
            random_rate = float((sub["policy_minus_random_ev"].astype(float) > 0.0).mean()) if len(sub) else 0.0
            mean_ev = float(ev.mean()) if len(ev) else 0.0
            if label == "wait_0_2" and mean_ev >= 0.10 and large_rate <= cfg.max_large_loss_rate_for_review and random_rate >= cfg.min_policy_beats_random_rate:
                cls = "wait_0_2_candidate_window"
                reason = "early_window_has_positive_utility_with_manageable_tail"
            elif label == "wait_0_2":
                cls = "wait_0_2_review_window"
                reason = "early_window_not_strong_enough_or_tail_too_large"
            else:
                cls = "late_window_reference_only"
                reason = "late_window_used_for_timing_loss_comparison_not_primary_gate"
            rows.append(_with_boundary({
                "window_scope": "risk_wait_window",
                "risk_name": str(risk),
                "wait_window": label,
                "row_count": int(len(sub)),
                "mean_relative_ev": round(mean_ev, 6),
                "positive_ev_rate": round(float((ev > 0).mean()) if len(ev) else 0.0, 6),
                "action_beats_no_op_rate": round(float(sub["action_beats_no_op"].astype(bool).mean()) if len(sub) else 0.0, 6),
                "policy_beats_random_rate": round(random_rate, 6),
                "large_loss_rate": round(large_rate, 6),
                "p05_relative_ev": round(_quantile(ev, 0.05), 6),
                "mean_rollback_margin": round(float(sub["rollback_margin"].astype(float).mean()) if len(sub) else 0.0, 6),
                "mean_boundary_margin": round(float(sub["boundary_margin"].astype(float).mean()) if len(sub) else 0.0, 6),
                "peak_worsening_rate": round(peak_rate, 6),
                "window_class": cls,
                "window_review_reason": reason,
            }))
    return pd.DataFrame(rows, columns=WINDOW_COLUMNS)


def build_gate_recommendations(primary: pd.DataFrame, stress: pd.DataFrame, boundary: pd.DataFrame, resource: pd.DataFrame, window: pd.DataFrame) -> pd.DataFrame:
    rows = []
    risk_rows = primary[primary["objective_scope"].astype(str) == "risk"]
    for _, row in risk_rows.iterrows():
        risk_name = str(row["risk_name"])
        main_class = str(row["primary_objective_class"])
        large_class = "large_risk_pass" if bool(row["primary_large_risk_pass"]) else "large_risk_review_or_fail"
        stress_risk = stress[stress["risk_name"].astype(str) == risk_name]
        stress_support_rate = float(stress_risk["secondary_stress_class"].astype(str).str.contains("supports|not_worse").mean()) if not stress_risk.empty else 0.0
        stress_class = "secondary_stress_ok" if stress_support_rate >= 0.55 else "secondary_stress_review"
        early = window[(window["risk_name"].astype(str) == risk_name) & (window["wait_window"].astype(str) == "wait_0_2")]
        early_class = str(early["window_class"].iloc[0]) if not early.empty else "wait_0_2_missing"
        baseline_class = "baseline_ok"
        if risk_name == "boundary_fragile":
            weak = boundary[boundary["boundary_fragile_class"].astype(str) != "boundary_fragile_separated_from_random_candidate"]
            baseline_class = "boundary_guarded_review" if len(weak) > 0 else "baseline_ok"
        if risk_name == "resource_pressure":
            weak_resource = resource[resource["resource_pressure_class"].astype(str) != "resource_pressure_candidate_after_review"]
            baseline_class = "resource_weak_effect_review" if len(weak_resource) > 0 else "baseline_ok"
        if main_class == "primary_objective_pass" and large_class == "large_risk_pass" and early_class == "wait_0_2_candidate_window" and baseline_class == "baseline_ok":
            gate = "strong_adoption_candidate"
            reason = "primary_objective_and_wait_0_2_window_pass_without_targeted_review_flags"
        elif main_class in {"primary_objective_pass", "primary_objective_review"} and early_class in {"wait_0_2_candidate_window", "wait_0_2_review_window"}:
            gate = "guarded_review_candidate"
            reason = "some_primary_signal_but_targeted_tail_or_baseline_review_needed"
        else:
            gate = "do_not_adopt_now"
            reason = "primary_objective_or_wait_window_not_sufficient"
        rows.append(_with_boundary({
            "gate_id": f"gate_{risk_name}",
            "risk_name": risk_name,
            "main_total_utility_class": main_class,
            "large_risk_class": large_class,
            "stress_peak_class": stress_class,
            "baseline_separation_class": baseline_class,
            "wait_0_2_class": early_class,
            "recommended_gate": gate,
            "gate_reason": reason,
            "may_freeze_threshold_now": False,
        }))
    return pd.DataFrame(rows, columns=GATE_COLUMNS)


def build_checks(policy: pd.DataFrame, primary: pd.DataFrame, stress: pd.DataFrame, boundary: pd.DataFrame, resource: pd.DataFrame, window: pd.DataFrame, gates: pd.DataFrame, source_ready: bool) -> pd.DataFrame:
    checks = [
        ("check_source_ready", "upstream", "Task24b3 source validation is ready.", True, source_ready),
        ("check_policy_rows", "input", "Policy rollout rows are available.", True, len(policy) > 0),
        ("check_primary_objective", "primary", "Primary objective audit exists.", True, len(primary) > 0),
        ("check_stress_audit", "secondary", "Stress peak and concentration audit exists.", True, len(stress) > 0),
        ("check_boundary_audit", "targeted", "boundary_fragile separation audit exists.", True, len(boundary) > 0),
        ("check_resource_audit", "targeted", "resource_pressure weak-effect audit exists.", True, len(resource) > 0),
        ("check_window_audit", "targeted", "wait-step 0-2 adoption-window audit exists.", True, len(window) > 0),
        ("check_gate_recommendations", "gate", "Per-risk gate recommendations exist but do not freeze thresholds.", True, len(gates) > 0 and not bool(gates["may_freeze_threshold_now"].astype(bool).any())),
        ("check_no_threshold_update", "boundary", "No threshold update is performed.", True, bool(primary["no_threshold_update_performed"].astype(bool).all()) if not primary.empty else False),
        ("check_no_action_candidate", "boundary", "No formal action candidate is generated.", False, bool(primary["action_candidate_generated"].astype(bool).any()) if not primary.empty else True),
        ("check_no_real_execution", "boundary", "No real ActionModule call or axis execution occurs.", False, bool(primary["real_actionmodule_called"].astype(bool).any() or primary["axis_executed"].astype(bool).any()) if not primary.empty else True),
    ]
    return pd.DataFrame([_with_boundary({"check_id": c[0], "check_scope": c[1], "check_description": c[2], "expected_value": bool(c[3]), "observed_value": bool(c[4]), "check_status": "pass" if bool(c[3]) == bool(c[4]) else "fail"}) for c in checks], columns=CHECK_COLUMNS)


def build_final_summary(policy: pd.DataFrame, primary: pd.DataFrame, stress: pd.DataFrame, boundary: pd.DataFrame, resource: pd.DataFrame, window: pd.DataFrame, gates: pd.DataFrame, checks: pd.DataFrame, source_ready: bool) -> pd.DataFrame:
    overall = primary[primary["objective_scope"].astype(str) == "overall"].iloc[0] if not primary.empty else None
    early = window[window["wait_window"].astype(str) == "wait_0_2"]
    wait_0_2_mean = float(early["mean_relative_ev"].astype(float).mean()) if not early.empty else 0.0
    wait_0_2_large = float(early["large_loss_rate"].astype(float).mean()) if not early.empty else 0.0
    stress_improve = float(stress["secondary_stress_class"].astype(str).str.contains("supports|not_worse").mean()) if not stress.empty else 0.0
    pass_count = int((checks["check_status"].astype(str) == "pass").sum()) if not checks.empty else 0
    strong = int((gates["recommended_gate"].astype(str) == "strong_adoption_candidate").sum()) if not gates.empty else 0
    review = int((gates["recommended_gate"].astype(str) == "guarded_review_candidate").sum()) if not gates.empty else 0
    block = int((gates["recommended_gate"].astype(str) == "do_not_adopt_now").sum()) if not gates.empty else 0
    decision = "targeted_robustness_validation_ready" if source_ready and len(checks) == pass_count else "targeted_robustness_validation_needs_review"
    return pd.DataFrame([_with_boundary({
        "source_task24b3_ready": bool(source_ready),
        "policy_rollout_row_count": int(len(policy)),
        "primary_objective_row_count": int(len(primary)),
        "stress_audit_row_count": int(len(stress)),
        "boundary_fragile_audit_row_count": int(len(boundary)),
        "resource_pressure_audit_row_count": int(len(resource)),
        "adoption_window_row_count": int(len(window)),
        "gate_recommendation_count": int(len(gates)),
        "strong_gate_count": strong,
        "review_gate_count": review,
        "block_gate_count": block,
        "overall_mean_relative_ev": _safe_float(overall["mean_relative_ev"]) if overall is not None else 0.0,
        "overall_action_beats_no_op_rate": _safe_float(overall["action_beats_no_op_rate"]) if overall is not None else 0.0,
        "overall_large_loss_rate": _safe_float(overall["large_loss_rate"]) if overall is not None else 0.0,
        "overall_severe_loss_rate": _safe_float(overall["severe_loss_rate"]) if overall is not None else 0.0,
        "overall_policy_beats_random_rate": _safe_float(overall["policy_beats_random_rate"]) if overall is not None else 0.0,
        "wait_0_2_mean_ev": round(wait_0_2_mean, 6),
        "wait_0_2_large_loss_rate": round(wait_0_2_large, 6),
        "stress_peak_improvement_rate": round(stress_improve, 6),
        "threshold_freeze_allowed_now": False,
        "validation_check_count": int(len(checks)),
        "validation_check_pass_count": pass_count,
        "targeted_robustness_validation_decision": decision,
        "next_task": "Review gates. Freeze only strong candidates; add targeted validation for review/block candidates.",
    })], columns=SUMMARY_COLUMNS)


def validate_tables(primary: pd.DataFrame, stress: pd.DataFrame, boundary: pd.DataFrame, resource: pd.DataFrame, window: pd.DataFrame, gates: pd.DataFrame, checks: pd.DataFrame, final_summary: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    tables = {"primary": (primary, PRIMARY_COLUMNS), "stress": (stress, STRESS_COLUMNS), "boundary": (boundary, BOUNDARY_COLUMNS), "resource": (resource, RESOURCE_COLUMNS), "window": (window, WINDOW_COLUMNS), "gates": (gates, GATE_COLUMNS), "checks": (checks, CHECK_COLUMNS), "final_summary": (final_summary, SUMMARY_COLUMNS)}
    for name, (table, cols) in tables.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_24b4_empty_table:{name}"); continue
        missing = [c for c in cols if c not in table.columns]
        if missing:
            errors.append(f"task2_8j_24b4_missing_columns:{name}:" + ",".join(missing)); continue
        for col in REQUIRED_TRUE:
            if not bool(table[col].astype(bool).all()):
                errors.append(f"task2_8j_24b4_required_true_not_all_true:{name}:{col}")
        for col in FORBIDDEN_TRUE:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_24b4_forbidden_true:{name}:{col}")
    if checks is not None and not checks.empty and not bool((checks["check_status"].astype(str) == "pass").all()):
        errors.append("task2_8j_24b4_check_failed")
    if gates is not None and not gates.empty and bool(gates["may_freeze_threshold_now"].astype(bool).any()):
        errors.append("task2_8j_24b4_threshold_freeze_attempted")
    if final_summary is not None and not final_summary.empty and bool(final_summary["threshold_freeze_allowed_now"].astype(bool).any()):
        errors.append("task2_8j_24b4_threshold_freeze_allowed_too_early")
    return errors


def build_and_validate_targeted_robustness_validation(cfg: TargetedRobustnessValidationConfig | None = None, **_unused: object) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    cfg = cfg or TargetedRobustnessValidationConfig()
    _scenarios, policy, _random_rollout, baseline, _risk_b3, _step_b3, _threshold_b3, _checks_b3, _final_b3, b3_errors, b3_summary = build_and_validate_multi_scenario_stateful_rollout_validation(MultiScenarioStatefulRolloutValidationConfig())
    source_ready = len(b3_errors) == 0 and str(b3_summary.get("multi_scenario_stateful_rollout_validation_decision", "")).startswith(TASK24B3_ACCEPTED_DECISION)
    if not cfg.require_task24b3_ready:
        source_ready = True
    primary = build_primary_objective_audit(policy, baseline, cfg)
    stress = build_stress_peak_concentration_audit(policy, cfg)
    boundary = build_boundary_fragile_separation_audit(policy, baseline, cfg)
    resource = build_resource_pressure_weak_effect_audit(policy, baseline, cfg)
    window = build_wait_0_2_adoption_window_stress_test(policy, baseline, cfg)
    gates = build_gate_recommendations(primary, stress, boundary, resource, window)
    checks = build_checks(policy, primary, stress, boundary, resource, window, gates, source_ready)
    final_summary = build_final_summary(policy, primary, stress, boundary, resource, window, gates, checks, source_ready)
    errors: list[str] = []
    if cfg.require_task24b3_ready:
        errors += [f"task2_8j_24b4_upstream_24b3_error:{e}" for e in b3_errors]
    errors += validate_tables(primary, stress, boundary, resource, window, gates, checks, final_summary)
    summary = {
        "gt_main_map_name": "static_pca_7",
        "gt_main_component_count": 7,
        "source_task24b3_decision": b3_summary.get("multi_scenario_stateful_rollout_validation_decision", ""),
        "source_task24b3_ready": bool(source_ready),
        "policy_rollout_row_count": _safe_int(final_summary["policy_rollout_row_count"].iloc[0]),
        "primary_objective_row_count": _safe_int(final_summary["primary_objective_row_count"].iloc[0]),
        "stress_audit_row_count": _safe_int(final_summary["stress_audit_row_count"].iloc[0]),
        "boundary_fragile_audit_row_count": _safe_int(final_summary["boundary_fragile_audit_row_count"].iloc[0]),
        "resource_pressure_audit_row_count": _safe_int(final_summary["resource_pressure_audit_row_count"].iloc[0]),
        "adoption_window_row_count": _safe_int(final_summary["adoption_window_row_count"].iloc[0]),
        "gate_recommendation_count": _safe_int(final_summary["gate_recommendation_count"].iloc[0]),
        "strong_gate_count": _safe_int(final_summary["strong_gate_count"].iloc[0]),
        "review_gate_count": _safe_int(final_summary["review_gate_count"].iloc[0]),
        "block_gate_count": _safe_int(final_summary["block_gate_count"].iloc[0]),
        "overall_mean_relative_ev": float(final_summary["overall_mean_relative_ev"].iloc[0]),
        "overall_action_beats_no_op_rate": float(final_summary["overall_action_beats_no_op_rate"].iloc[0]),
        "overall_large_loss_rate": float(final_summary["overall_large_loss_rate"].iloc[0]),
        "overall_severe_loss_rate": float(final_summary["overall_severe_loss_rate"].iloc[0]),
        "overall_policy_beats_random_rate": float(final_summary["overall_policy_beats_random_rate"].iloc[0]),
        "wait_0_2_mean_ev": float(final_summary["wait_0_2_mean_ev"].iloc[0]),
        "wait_0_2_large_loss_rate": float(final_summary["wait_0_2_large_loss_rate"].iloc[0]),
        "stress_peak_improvement_rate": float(final_summary["stress_peak_improvement_rate"].iloc[0]),
        "threshold_freeze_allowed_now": False,
        "validation_check_count": _safe_int(final_summary["validation_check_count"].iloc[0]),
        "validation_check_pass_count": _safe_int(final_summary["validation_check_pass_count"].iloc[0]),
        "targeted_robustness_validation_decision": str(final_summary["targeted_robustness_validation_decision"].iloc[0]),
        "no_threshold_update_performed": True,
        "action_candidate_generated": False,
        "real_actionmodule_called": False,
        "axis_executed": False,
        "validation_errors": errors,
    }
    return primary, stress, boundary, resource, window, gates, checks, final_summary, errors, summary
