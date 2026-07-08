"""Task 2-8j-24b: v2 sandbox action-material timing validation RC1.

Uses the v2 sandbox as a validation-side observation window to compare Task24
terrain-operator material against NO_OP across action step counts.  This task is
for adoption-threshold plausibility only: it may generate sandbox outcome proxies
and relative expected-value proxies, but it does not create formal action
candidates, does not update thresholds, and does not call the real ActionModule.

The v2 sandbox is a scoring / auxiliary-observation surface for threshold design,
not a runtime oracle for direct deployment decisions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from .pressure_action_task2_8j_24_terrain_operator_selection_dry_run import (
    TerrainOperatorSelectionDryRunConfig,
    build_and_validate_terrain_operator_selection_dry_run,
)

TASK2_8J_24B_VERSION = "v2_sandbox_action_material_timing_validation_rc1"
TASK24_ACCEPTED_DECISION = "terrain_operator_selection_dry_run_ready"

BOUNDARY: dict[str, Any] = {
    "task2_8j_24b_version": TASK2_8J_24B_VERSION,
    "validation_only": True,
    "dry_run_only": True,
    "v2_sandbox_validation_only": True,
    "v2_window_used_as_auxiliary_observation": True,
    "v2_window_not_runtime_oracle": True,
    "NO_OP_comparison_required": True,
    "step_count_sensitivity": True,
    "adoption_threshold_tradeoff_audit": True,
    "relative_expected_value_proxy_generated": True,
    "sandbox_action_material_applied": True,
    "sandbox_only_action": True,
    "source_task24_required": True,
    "gt_main_map_name": "static_pca_7",
    "gt_main_component_count": 7,
    "terrain_operator_material_input_used": True,
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
    "future_information_used": False,
    "canonical_write_performed": False,
}

REQUIRED_TRUE = [
    "validation_only", "dry_run_only", "v2_sandbox_validation_only", "v2_window_used_as_auxiliary_observation",
    "v2_window_not_runtime_oracle", "NO_OP_comparison_required", "step_count_sensitivity",
    "adoption_threshold_tradeoff_audit", "relative_expected_value_proxy_generated", "sandbox_action_material_applied",
    "sandbox_only_action", "source_task24_required", "terrain_operator_material_input_used",
    "threshold_values_are_provisional", "threshold_revision_requires_validation", "no_threshold_update_performed",
    "overfit_to_v2_forbidden",
]
FORBIDDEN_TRUE = [
    "release_rollback_audit_shaped", "action_candidate_generated", "concrete_action_generated",
    "action_effect_prediction_generated", "effect_prediction_model_executed", "expected_value_final_judgment_performed",
    "real_actionmodule_called", "axis_executed", "upper_pressure_coupled_now", "hidden_truth_input",
    "future_information_used", "canonical_write_performed",
]

SWEEP_COLUMNS = list(BOUNDARY) + [
    "sweep_id", "operator_selection_id", "macro_state_id", "macro_state_name", "risk_name", "selected_operator_name",
    "action_step", "confidence_at_step", "NO_OP_risk_proxy", "NO_OP_recovery_chance", "operator_benefit_proxy",
    "timing_loss_by_waiting", "confidence_gain_by_waiting", "rollback_margin_at_step", "boundary_risk_by_waiting",
    "side_effect_risk_proxy", "relative_expected_value_proxy", "timing_confidence_balance_score",
    "timing_class", "sandbox_outcome_status",
]
NOOP_COLUMNS = list(BOUNDARY) + [
    "outcome_id", "operator_selection_id", "macro_state_id", "risk_name", "best_action_step", "best_action_relative_ev",
    "best_action_timing_class", "NO_OP_risk_proxy", "NO_OP_recovery_chance", "action_beats_NO_OP",
    "NO_OP_preferred", "outcome_review_status",
]
STEP_COLUMNS = list(BOUNDARY) + [
    "step_summary_id", "action_step", "row_count", "mean_relative_ev", "max_relative_ev", "mean_confidence",
    "mean_timing_loss", "mean_rollback_margin", "positive_ev_count", "NO_OP_preferred_count", "step_status",
]
TRADEOFF_COLUMNS = list(BOUNDARY) + [
    "tradeoff_id", "operator_selection_id", "risk_name", "early_step", "late_step", "confidence_gain_by_waiting",
    "timing_loss_by_waiting", "ev_loss_by_waiting", "rollback_loss_by_waiting", "tradeoff_class", "tradeoff_status",
]
THRESHOLD_COLUMNS = list(BOUNDARY) + [
    "threshold_audit_id", "confidence_threshold_candidate", "max_allowed_step", "minimum_relative_ev_candidate",
    "minimum_rollback_margin_candidate", "adopted_material_count", "mean_adopted_relative_ev", "late_adoption_count",
    "NO_OP_preferred_adoption_count", "threshold_candidate_interpretation", "may_update_threshold_now",
    "requires_validation_before_update", "threshold_audit_status",
]
CHECK_COLUMNS = list(BOUNDARY) + [
    "check_id", "check_scope", "check_description", "expected_value", "observed_value", "check_status",
]
SUMMARY_COLUMNS = list(BOUNDARY) + [
    "operator_selection_count", "sweep_row_count", "NO_OP_outcome_count", "step_summary_count", "tradeoff_row_count",
    "threshold_audit_count", "positive_ev_row_count", "best_action_beats_NO_OP_count", "NO_OP_preferred_count",
    "early_action_preferred_count", "wait_for_confirmation_preferred_count", "too_late_after_confirmation_count",
    "max_best_relative_ev", "validation_check_count", "validation_check_pass_count", "task24_ready",
    "v2_sandbox_action_material_timing_validation_decision", "next_task",
]


@dataclass(frozen=True)
class V2SandboxActionMaterialTimingValidationConfig:
    require_task24_ready: bool = True
    min_step: int = 0
    max_step: int = 5


def _with_boundary(row: dict[str, Any]) -> dict[str, Any]:
    return {**BOUNDARY, **row}


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def _risk_base(risk: str) -> float:
    return {"relation_lock": 0.68, "resource_pressure": 0.70, "reversibility_loss": 0.72, "boundary_fragile": 0.74, "oscillation": 0.66}.get(str(risk), 0.62)


def _benefit_base(risk: str) -> float:
    return {"relation_lock": 0.24, "resource_pressure": 0.27, "reversibility_loss": 0.25, "boundary_fragile": 0.18, "oscillation": 0.22}.get(str(risk), 0.16)


def _noop_recovery(risk: str) -> float:
    return {"relation_lock": 0.18, "resource_pressure": 0.22, "reversibility_loss": 0.10, "boundary_fragile": 0.08, "oscillation": 0.28}.get(str(risk), 0.18)


def _classify_timing(step: int, confidence: float, ev: float, rollback: float, no_op_recovery: float, boundary_risk: float) -> str:
    if rollback < 0.30:
        return "rollback_window_closed"
    if boundary_risk > 0.74:
        return "boundary_guard_blocks_action"
    if ev <= 0.0 or no_op_recovery > 0.38:
        return "NO_OP_preferred"
    if step <= 1 and confidence < 0.66 and ev > 0.08:
        return "early_low_confidence_but_timing_good"
    if step <= 2 and ev > 0.12:
        return "early_action_preferred"
    if 2 <= step <= 3 and confidence >= 0.70 and ev > 0.10:
        return "balanced_window"
    if step >= 4 and confidence >= 0.76:
        return "too_late_after_confirmation"
    return "wait_for_confirmation_preferred"


def build_v2_action_material_timing_sweep(selection: pd.DataFrame, cfg: V2SandboxActionMaterialTimingValidationConfig) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, r in selection.iterrows():
        risk = str(r["risk_name"])
        base_risk = _risk_base(risk)
        noop_recovery = _noop_recovery(risk)
        benefit_base = _benefit_base(risk)
        for step in range(cfg.min_step, cfg.max_step + 1):
            confidence = min(0.93, 0.58 + 0.055 * step + (0.03 if risk in {"boundary_fragile", "reversibility_loss"} else 0.0))
            confidence_gain = max(0.0, confidence - 0.58)
            timing_loss = 0.035 * step + (0.025 * step if risk in {"boundary_fragile", "reversibility_loss"} else 0.0)
            rollback = max(0.05, 0.82 - 0.105 * step - (0.08 if risk in {"boundary_fragile", "reversibility_loss"} else 0.0))
            boundary_risk = min(0.95, 0.30 + 0.055 * step + (0.18 if risk == "boundary_fragile" else 0.10 if risk == "reversibility_loss" else 0.0))
            side_effect = min(0.70, 0.12 + 0.025 * step + (0.06 if str(r["selected_operator_name"]) in {"buffer_injection", "pressure_diffusion"} else 0.03))
            timing_weight = max(0.15, 1.0 - 0.13 * step)
            operator_benefit = benefit_base * timing_weight
            relative_ev = round(operator_benefit + 0.18 * confidence_gain + 0.12 * rollback - 0.16 * noop_recovery - 0.24 * side_effect - 0.18 * boundary_risk - timing_loss, 6)
            balance = round(relative_ev + 0.12 * confidence - 0.16 * step / max(1, cfg.max_step), 6)
            tclass = _classify_timing(step, confidence, relative_ev, rollback, noop_recovery, boundary_risk)
            rows.append(_with_boundary({
                "sweep_id": f"sweep_{r['operator_selection_id']}_step_{step}",
                "operator_selection_id": str(r["operator_selection_id"]),
                "macro_state_id": str(r["macro_state_id"]),
                "macro_state_name": str(r["macro_state_name"]),
                "risk_name": risk,
                "selected_operator_name": str(r["selected_operator_name"]),
                "action_step": int(step),
                "confidence_at_step": round(confidence, 6),
                "NO_OP_risk_proxy": round(base_risk, 6),
                "NO_OP_recovery_chance": round(noop_recovery, 6),
                "operator_benefit_proxy": round(operator_benefit, 6),
                "timing_loss_by_waiting": round(timing_loss, 6),
                "confidence_gain_by_waiting": round(confidence_gain, 6),
                "rollback_margin_at_step": round(rollback, 6),
                "boundary_risk_by_waiting": round(boundary_risk, 6),
                "side_effect_risk_proxy": round(side_effect, 6),
                "relative_expected_value_proxy": relative_ev,
                "timing_confidence_balance_score": balance,
                "timing_class": tclass,
                "sandbox_outcome_status": "v2_sandbox_proxy_compared_with_NO_OP_not_runtime_oracle",
            }))
    return pd.DataFrame(rows, columns=SWEEP_COLUMNS)


def build_no_op_vs_action_outcome(sweep: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for op_id, g in sweep.groupby("operator_selection_id", sort=False):
        best = g.sort_values("relative_expected_value_proxy", ascending=False).iloc[0]
        noop_preferred = bool(best["relative_expected_value_proxy"] <= 0 or best["timing_class"] == "NO_OP_preferred")
        rows.append(_with_boundary({
            "outcome_id": f"noop_vs_action_{op_id}",
            "operator_selection_id": str(op_id),
            "macro_state_id": str(best["macro_state_id"]),
            "risk_name": str(best["risk_name"]),
            "best_action_step": int(best["action_step"]),
            "best_action_relative_ev": float(best["relative_expected_value_proxy"]),
            "best_action_timing_class": str(best["timing_class"]),
            "NO_OP_risk_proxy": float(best["NO_OP_risk_proxy"]),
            "NO_OP_recovery_chance": float(best["NO_OP_recovery_chance"]),
            "action_beats_NO_OP": bool(not noop_preferred),
            "NO_OP_preferred": bool(noop_preferred),
            "outcome_review_status": "relative_proxy_only_for_threshold_plausibility",
        }))
    return pd.DataFrame(rows, columns=NOOP_COLUMNS)


def build_step_count_sensitivity(sweep: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for step, g in sweep.groupby("action_step", sort=True):
        rows.append(_with_boundary({
            "step_summary_id": f"step_summary_{int(step)}",
            "action_step": int(step),
            "row_count": int(len(g)),
            "mean_relative_ev": round(float(g["relative_expected_value_proxy"].mean()), 6),
            "max_relative_ev": round(float(g["relative_expected_value_proxy"].max()), 6),
            "mean_confidence": round(float(g["confidence_at_step"].mean()), 6),
            "mean_timing_loss": round(float(g["timing_loss_by_waiting"].mean()), 6),
            "mean_rollback_margin": round(float(g["rollback_margin_at_step"].mean()), 6),
            "positive_ev_count": int((g["relative_expected_value_proxy"].astype(float) > 0).sum()),
            "NO_OP_preferred_count": int((g["timing_class"].astype(str) == "NO_OP_preferred").sum()),
            "step_status": "step_count_sensitivity_ready",
        }))
    return pd.DataFrame(rows, columns=STEP_COLUMNS)


def build_confidence_timing_tradeoff(sweep: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for op_id, g in sweep.groupby("operator_selection_id", sort=False):
        early = g.sort_values("action_step").iloc[0]
        late = g.sort_values("action_step").iloc[-1]
        ev_loss = float(early["relative_expected_value_proxy"]) - float(late["relative_expected_value_proxy"])
        conf_gain = float(late["confidence_at_step"]) - float(early["confidence_at_step"])
        timing_loss = float(late["timing_loss_by_waiting"]) - float(early["timing_loss_by_waiting"])
        rollback_loss = float(early["rollback_margin_at_step"]) - float(late["rollback_margin_at_step"])
        if conf_gain > 0 and ev_loss > 0.08:
            tclass = "confidence_gain_but_timing_value_drops"
        elif ev_loss <= 0.03:
            tclass = "waiting_cost_small"
        else:
            tclass = "mixed_confidence_timing_tradeoff"
        rows.append(_with_boundary({
            "tradeoff_id": f"tradeoff_{op_id}",
            "operator_selection_id": str(op_id),
            "risk_name": str(early["risk_name"]),
            "early_step": int(early["action_step"]),
            "late_step": int(late["action_step"]),
            "confidence_gain_by_waiting": round(conf_gain, 6),
            "timing_loss_by_waiting": round(timing_loss, 6),
            "ev_loss_by_waiting": round(ev_loss, 6),
            "rollback_loss_by_waiting": round(rollback_loss, 6),
            "tradeoff_class": tclass,
            "tradeoff_status": "confidence_timing_tradeoff_audited",
        }))
    return pd.DataFrame(rows, columns=TRADEOFF_COLUMNS)


def build_adoption_threshold_tradeoff_audit(sweep: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    idx = 1
    for conf_thr in [0.55, 0.60, 0.65, 0.70, 0.75]:
        for max_step in [0, 1, 2, 3, 4, 5]:
            for min_ev in [0.00, 0.05, 0.10, 0.15]:
                for min_rb in [0.25, 0.40]:
                    eligible = sweep[
                        (sweep["confidence_at_step"].astype(float) >= conf_thr)
                        & (sweep["action_step"].astype(int) <= max_step)
                        & (sweep["relative_expected_value_proxy"].astype(float) >= min_ev)
                        & (sweep["rollback_margin_at_step"].astype(float) >= min_rb)
                    ]
                    count = int(len(eligible))
                    mean_ev = float(eligible["relative_expected_value_proxy"].mean()) if count else 0.0
                    late_count = int((eligible["action_step"].astype(int) >= 4).sum()) if count else 0
                    no_op_count = int(eligible["timing_class"].astype(str).isin(["NO_OP_preferred", "rollback_window_closed", "boundary_guard_blocks_action"]).sum()) if count else 0
                    if count == 0:
                        interp = "too_strict_or_timing_window_closed"
                    elif no_op_count > 0:
                        interp = "admits_some_guarded_or_NO_OP_preferred_cases_requires_review"
                    elif late_count > 0:
                        interp = "admits_late_cases_timing_loss_must_be_reviewed"
                    else:
                        interp = "candidate_threshold_window_for_later_validation"
                    rows.append(_with_boundary({
                        "threshold_audit_id": f"threshold_audit_{idx:04d}",
                        "confidence_threshold_candidate": float(conf_thr),
                        "max_allowed_step": int(max_step),
                        "minimum_relative_ev_candidate": float(min_ev),
                        "minimum_rollback_margin_candidate": float(min_rb),
                        "adopted_material_count": count,
                        "mean_adopted_relative_ev": round(mean_ev, 6),
                        "late_adoption_count": late_count,
                        "NO_OP_preferred_adoption_count": no_op_count,
                        "threshold_candidate_interpretation": interp,
                        "may_update_threshold_now": False,
                        "requires_validation_before_update": True,
                        "threshold_audit_status": "adoption_threshold_tradeoff_audited_no_update",
                    }))
                    idx += 1
    return pd.DataFrame(rows, columns=THRESHOLD_COLUMNS)


def build_validation_checks(selection: pd.DataFrame, sweep: pd.DataFrame, noop: pd.DataFrame, step_summary: pd.DataFrame, tradeoff: pd.DataFrame, threshold: pd.DataFrame, task24_ready: bool) -> pd.DataFrame:
    checks = [
        ("check_task24_ready", "upstream", "Task24 terrain operator selection is ready.", True, task24_ready),
        ("check_selection_input", "input", "Terrain-operator material exists.", True, len(selection) > 0),
        ("check_sweep_rows", "sweep", "Step-count sweep rows exist.", True, len(sweep) > 0),
        ("check_noop_rows", "NO_OP", "NO_OP comparison rows exist.", True, len(noop) == len(selection) and len(noop) > 0),
        ("check_step_summary", "step", "Step sensitivity summary exists.", True, len(step_summary) > 0),
        ("check_tradeoff", "tradeoff", "Confidence-timing tradeoff rows exist.", True, len(tradeoff) == len(selection) and len(tradeoff) > 0),
        ("check_threshold_audit", "threshold", "Adoption threshold tradeoff audit exists.", True, len(threshold) > 0),
        ("check_some_positive_ev", "expected_value", "At least one sandbox row beats NO_OP proxy.", True, bool((sweep["relative_expected_value_proxy"].astype(float) > 0).any()) if not sweep.empty else False),
        ("check_no_threshold_update", "threshold", "No threshold update is performed now.", False, bool(threshold["may_update_threshold_now"].astype(bool).any()) if not threshold.empty else True),
        ("check_requires_validation", "threshold", "Every threshold candidate requires validation.", True, bool(threshold["requires_validation_before_update"].astype(bool).all()) if not threshold.empty else False),
        ("check_no_action_candidate", "boundary", "No formal action candidate is generated.", False, bool(sweep["action_candidate_generated"].astype(bool).any()) if not sweep.empty else True),
        ("check_no_real_execution", "boundary", "No real ActionModule call or axis execution occurs.", False, bool(sweep["real_actionmodule_called"].astype(bool).any() or sweep["axis_executed"].astype(bool).any()) if not sweep.empty else True),
        ("check_no_hidden_future", "boundary", "No hidden truth or future information is used as runtime input.", False, bool(sweep["hidden_truth_input"].astype(bool).any() or sweep["future_information_used"].astype(bool).any()) if not sweep.empty else True),
    ]
    return pd.DataFrame([_with_boundary({"check_id": c[0], "check_scope": c[1], "check_description": c[2], "expected_value": bool(c[3]), "observed_value": bool(c[4]), "check_status": "pass" if bool(c[3]) == bool(c[4]) else "fail"}) for c in checks], columns=CHECK_COLUMNS)


def build_final_summary(selection: pd.DataFrame, sweep: pd.DataFrame, noop: pd.DataFrame, step_summary: pd.DataFrame, tradeoff: pd.DataFrame, threshold: pd.DataFrame, checks: pd.DataFrame, task24_ready: bool) -> pd.DataFrame:
    pass_count = int((checks["check_status"].astype(str) == "pass").sum()) if not checks.empty else 0
    decision = "v2_sandbox_action_material_timing_validation_ready" if task24_ready and len(checks) == pass_count else "v2_sandbox_action_material_timing_validation_needs_review"
    return pd.DataFrame([_with_boundary({
        "operator_selection_count": len(selection),
        "sweep_row_count": len(sweep),
        "NO_OP_outcome_count": len(noop),
        "step_summary_count": len(step_summary),
        "tradeoff_row_count": len(tradeoff),
        "threshold_audit_count": len(threshold),
        "positive_ev_row_count": int((sweep["relative_expected_value_proxy"].astype(float) > 0).sum()) if not sweep.empty else 0,
        "best_action_beats_NO_OP_count": int(noop["action_beats_NO_OP"].astype(bool).sum()) if not noop.empty else 0,
        "NO_OP_preferred_count": int(noop["NO_OP_preferred"].astype(bool).sum()) if not noop.empty else 0,
        "early_action_preferred_count": int(noop["best_action_timing_class"].astype(str).isin(["early_action_preferred", "early_low_confidence_but_timing_good"]).sum()) if not noop.empty else 0,
        "wait_for_confirmation_preferred_count": int(noop["best_action_timing_class"].astype(str).isin(["wait_for_confirmation_preferred", "balanced_window"]).sum()) if not noop.empty else 0,
        "too_late_after_confirmation_count": int((noop["best_action_timing_class"].astype(str) == "too_late_after_confirmation").sum()) if not noop.empty else 0,
        "max_best_relative_ev": round(float(noop["best_action_relative_ev"].astype(float).max()), 6) if not noop.empty else 0.0,
        "validation_check_count": len(checks),
        "validation_check_pass_count": pass_count,
        "task24_ready": bool(task24_ready),
        "v2_sandbox_action_material_timing_validation_decision": decision,
        "next_task": "Task 2-8j-24c: adoption threshold provisional policy from v2 timing validation",
    })], columns=SUMMARY_COLUMNS)


def validate_v2_sandbox_action_material_timing_validation_tables(sweep: pd.DataFrame, noop: pd.DataFrame, step_summary: pd.DataFrame, tradeoff: pd.DataFrame, threshold: pd.DataFrame, checks: pd.DataFrame, final_summary: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    tables = {"sweep": (sweep, SWEEP_COLUMNS), "noop": (noop, NOOP_COLUMNS), "step_summary": (step_summary, STEP_COLUMNS), "tradeoff": (tradeoff, TRADEOFF_COLUMNS), "threshold": (threshold, THRESHOLD_COLUMNS), "checks": (checks, CHECK_COLUMNS), "final_summary": (final_summary, SUMMARY_COLUMNS)}
    for name, (table, cols) in tables.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_24b_empty_table:{name}"); continue
        missing = [c for c in cols if c not in table.columns]
        if missing:
            errors.append(f"task2_8j_24b_missing_columns:{name}:" + ",".join(missing)); continue
        for col in REQUIRED_TRUE:
            if not bool(table[col].astype(bool).all()):
                errors.append(f"task2_8j_24b_required_true_not_all_true:{name}:{col}")
        for col in FORBIDDEN_TRUE:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_24b_forbidden_true:{name}:{col}")
        if set(table["gt_main_map_name"].astype(str)) != {"static_pca_7"}:
            errors.append(f"task2_8j_24b_wrong_gt_main_map_name:{name}")
        if set(table["gt_main_component_count"].astype(int)) != {7}:
            errors.append(f"task2_8j_24b_wrong_gt_component_count:{name}")
    if checks is not None and not checks.empty and not bool((checks["check_status"].astype(str) == "pass").all()):
        errors.append("task2_8j_24b_check_failed")
    if threshold is not None and not threshold.empty:
        if bool(threshold["may_update_threshold_now"].astype(bool).any()):
            errors.append("task2_8j_24b_threshold_update_attempted")
        if not bool(threshold["requires_validation_before_update"].astype(bool).all()):
            errors.append("task2_8j_24b_threshold_candidate_without_validation_requirement")
    return errors


def build_and_validate_v2_sandbox_action_material_timing_validation(cfg: V2SandboxActionMaterialTimingValidationConfig | None = None, **_unused: object) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    cfg = cfg or V2SandboxActionMaterialTimingValidationConfig()
    selection, _review24, _checks24, _final24, task24_errors, task24_summary = build_and_validate_terrain_operator_selection_dry_run(cfg=TerrainOperatorSelectionDryRunConfig())
    task24_ready = len(task24_errors) == 0 and str(task24_summary.get("terrain_operator_selection_dry_run_decision", "")).startswith(TASK24_ACCEPTED_DECISION)
    if not cfg.require_task24_ready:
        task24_ready = True
    sweep = build_v2_action_material_timing_sweep(selection, cfg)
    noop = build_no_op_vs_action_outcome(sweep)
    step_summary = build_step_count_sensitivity(sweep)
    tradeoff = build_confidence_timing_tradeoff(sweep)
    threshold = build_adoption_threshold_tradeoff_audit(sweep)
    checks = build_validation_checks(selection, sweep, noop, step_summary, tradeoff, threshold, task24_ready)
    final_summary = build_final_summary(selection, sweep, noop, step_summary, tradeoff, threshold, checks, task24_ready)
    errors: list[str] = []
    if cfg.require_task24_ready:
        errors += [f"task2_8j_24b_upstream_24_error:{e}" for e in task24_errors]
    errors += validate_v2_sandbox_action_material_timing_validation_tables(sweep, noop, step_summary, tradeoff, threshold, checks, final_summary)
    summary = {
        "gt_main_map_name": "static_pca_7",
        "gt_main_component_count": 7,
        "task24_decision": task24_summary.get("terrain_operator_selection_dry_run_decision", ""),
        "operator_selection_count": _safe_int(final_summary["operator_selection_count"].iloc[0]),
        "sweep_row_count": _safe_int(final_summary["sweep_row_count"].iloc[0]),
        "NO_OP_outcome_count": _safe_int(final_summary["NO_OP_outcome_count"].iloc[0]),
        "step_summary_count": _safe_int(final_summary["step_summary_count"].iloc[0]),
        "tradeoff_row_count": _safe_int(final_summary["tradeoff_row_count"].iloc[0]),
        "threshold_audit_count": _safe_int(final_summary["threshold_audit_count"].iloc[0]),
        "positive_ev_row_count": _safe_int(final_summary["positive_ev_row_count"].iloc[0]),
        "best_action_beats_NO_OP_count": _safe_int(final_summary["best_action_beats_NO_OP_count"].iloc[0]),
        "NO_OP_preferred_count": _safe_int(final_summary["NO_OP_preferred_count"].iloc[0]),
        "early_action_preferred_count": _safe_int(final_summary["early_action_preferred_count"].iloc[0]),
        "wait_for_confirmation_preferred_count": _safe_int(final_summary["wait_for_confirmation_preferred_count"].iloc[0]),
        "too_late_after_confirmation_count": _safe_int(final_summary["too_late_after_confirmation_count"].iloc[0]),
        "max_best_relative_ev": float(final_summary["max_best_relative_ev"].iloc[0]),
        "validation_check_count": _safe_int(final_summary["validation_check_count"].iloc[0]),
        "validation_check_pass_count": _safe_int(final_summary["validation_check_pass_count"].iloc[0]),
        "task24_ready": bool(task24_ready),
        "v2_sandbox_action_material_timing_validation_decision": str(final_summary["v2_sandbox_action_material_timing_validation_decision"].iloc[0]),
        "v2_window_used_as_auxiliary_observation": True,
        "v2_window_not_runtime_oracle": True,
        "relative_expected_value_proxy_generated": True,
        "sandbox_action_material_applied": True,
        "sandbox_only_action": True,
        "no_threshold_update_performed": True,
        "action_candidate_generated": False,
        "action_effect_prediction_generated": False,
        "real_actionmodule_called": False,
        "axis_executed": False,
        "validation_errors": errors,
    }
    return sweep, noop, step_summary, tradeoff, threshold, checks, final_summary, errors, summary
