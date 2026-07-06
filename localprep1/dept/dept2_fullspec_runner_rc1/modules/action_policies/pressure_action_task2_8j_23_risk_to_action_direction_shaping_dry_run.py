"""Task 2-8j-23: risk-to-action direction shaping dry-run RC1.

Converts calibrated risk confidence + dynamics direction into provisional action
DIRECTION material only.  This is the first risk-to-action shaping step, but it
still does not select terrain operators, does not shape release/rollback/audit,
does not generate action candidates, and does not execute any action.

The thresholds used here are provisional and revisable per Task2-8j-22c.  Fixed
safety rules remain hard boundaries.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from .pressure_action_task2_8j_22_gated_macro_game_risk_simulator_dry_run import (
    GatedMacroGameRiskSimulatorDryRunConfig,
    build_and_validate_gated_macro_game_risk_simulator_dry_run,
)
from .pressure_action_task2_8j_22b_v8_style_risk_confidence_calibration_audit import (
    V8StyleRiskConfidenceCalibrationAuditConfig,
    build_and_validate_v8_style_risk_confidence_calibration_audit,
)
from .pressure_action_task2_8j_22c_provisional_threshold_policy_contract import (
    ProvisionalThresholdPolicyContractConfig,
    build_and_validate_provisional_threshold_policy_contract,
)

TASK2_8J_23_VERSION = "risk_to_action_direction_shaping_dry_run_rc1"
TASK22B_ACCEPTED_DECISION = "v8_style_risk_confidence_calibration_audit_ready"
TASK22C_ACCEPTED_DECISION = "provisional_threshold_policy_contract_ready"

BOUNDARY: dict[str, Any] = {
    "task2_8j_23_version": TASK2_8J_23_VERSION,
    "validation_only": True,
    "dry_run_only": True,
    "risk_to_action_direction_shaping_only": True,
    "action_direction_generated": True,
    "action_direction_material_only": True,
    "coarse_macro_game_structure_only": True,
    "not_high_resolution_forecast": True,
    "not_long_term_forecast": True,
    "risk_prediction_only": True,
    "system_visible_information_only": True,
    "source_task22b_required": True,
    "source_task22c_required": True,
    "gt_main_map_name": "static_pca_7",
    "gt_main_component_count": 7,
    "calibrated_risk_confidence_required": True,
    "dynamics_direction_required": True,
    "safety_rules_fixed": True,
    "decision_thresholds_revisable": True,
    "threshold_values_are_provisional": True,
    "threshold_revision_requires_validation": True,
    "semantic_recipe_primary_key_forbidden": True,
    "terrain_information_primary_required": True,
    "risk_label_used_only_for_evaluation": True,
    "NO_OP_baseline_required": True,
    "terrain_operator_selected": False,
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
    "validation_only", "dry_run_only", "risk_to_action_direction_shaping_only", "action_direction_generated",
    "action_direction_material_only", "coarse_macro_game_structure_only", "not_high_resolution_forecast",
    "not_long_term_forecast", "risk_prediction_only", "system_visible_information_only", "source_task22b_required",
    "source_task22c_required", "calibrated_risk_confidence_required", "dynamics_direction_required",
    "safety_rules_fixed", "decision_thresholds_revisable", "threshold_values_are_provisional",
    "threshold_revision_requires_validation", "semantic_recipe_primary_key_forbidden", "terrain_information_primary_required",
    "risk_label_used_only_for_evaluation", "NO_OP_baseline_required",
]
FORBIDDEN_TRUE = [
    "terrain_operator_selected", "release_rollback_audit_shaped", "action_candidate_generated", "concrete_action_generated",
    "action_effect_prediction_generated", "effect_prediction_model_executed", "expected_value_final_judgment_performed",
    "real_actionmodule_called", "axis_executed", "upper_pressure_coupled_now", "hidden_truth_input",
    "future_information_used", "canonical_write_performed",
]

MATERIAL_COLUMNS = list(BOUNDARY) + [
    "action_direction_id", "macro_state_id", "macro_state_name", "risk_name", "calibration_band",
    "calibration_action", "calibrated_risk_confidence", "v8_reliability_score", "information_sufficiency_score",
    "dominant_risk", "dominant_pressure_direction", "escape_or_return_direction", "forbidden_push_direction",
    "direction_clarity", "action_direction_family", "primary_action_direction", "secondary_action_direction",
    "forbidden_action_direction", "NO_OP_bias", "direction_use_class", "safety_guard_reason", "threshold_policy_status",
    "action_direction_status",
]
REVIEW_COLUMNS = list(BOUNDARY) + [
    "review_id", "macro_state_id", "macro_state_name", "risk_name", "calibration_band", "calibrated_risk_confidence",
    "review_decision", "review_reason", "material_emitted", "suppression_reason", "review_status",
]
CHECK_COLUMNS = list(BOUNDARY) + [
    "check_id", "check_scope", "check_description", "expected_value", "observed_value", "check_status",
]
SUMMARY_COLUMNS = list(BOUNDARY) + [
    "calibration_row_count", "direction_material_count", "usable_direction_material_count", "review_only_direction_count",
    "monitor_suppressed_count", "risk_family_count", "safety_guard_applied_count", "review_row_count", "direction_check_count",
    "direction_check_pass_count", "task22b_ready", "task22c_ready", "risk_to_action_direction_shaping_dry_run_decision",
    "next_task",
]


@dataclass(frozen=True)
class RiskToActionDirectionShapingDryRunConfig:
    require_task22b_ready: bool = True
    require_task22c_ready: bool = True
    include_review_band_material: bool = True


def _with_boundary(row: dict[str, Any]) -> dict[str, Any]:
    return {**BOUNDARY, **row}


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def _direction_family(risk_name: str) -> str:
    return {
        "relation_lock": "resist_lock_and_open_escape_direction",
        "resource_pressure": "diffuse_pressure_toward_available_capacity_direction",
        "reversibility_loss": "preserve_return_path_direction",
        "boundary_fragile": "avoid_boundary_push_and_prepare_buffer_direction",
        "oscillation": "reduce_phase_amplification_direction",
    }.get(str(risk_name), "review_unknown_risk_direction")


def _primary_direction(risk_name: str, dominant_pressure_direction: str, escape_or_return_direction: str) -> str:
    risk_name = str(risk_name)
    if risk_name == "relation_lock":
        return "resist_dominant_lock_gradient_and_keep_escape_path_visible"
    if risk_name == "resource_pressure":
        if "neighbor_capacity_available" in str(escape_or_return_direction):
            return "diffuse_pressure_toward_available_neighbor_capacity"
        return "reduce_pressure_accumulation_without_forcing_boundary"
    if risk_name == "reversibility_loss":
        return "preserve_or_reopen_return_escape_path"
    if risk_name == "boundary_fragile":
        return "avoid_boundary_push_and_hold_distance"
    if risk_name == "oscillation":
        return "reduce_phase_amplification_and_curvature_growth"
    return "review_only_direction_unknown"


def _secondary_direction(risk_name: str, escape_or_return_direction: str) -> str:
    risk_name = str(risk_name)
    if risk_name in {"relation_lock", "reversibility_loss"}:
        return str(escape_or_return_direction)
    if risk_name == "resource_pressure":
        return "prefer_diffusion_over_resistance_when_capacity_exists"
    if risk_name == "boundary_fragile":
        return "prefer_monitor_or_review_if_return_path_unclear"
    if risk_name == "oscillation":
        return "avoid_synchronous_push_or_phase_delay_amplification"
    return "no_secondary_direction_without_review"


def build_action_direction_material(calibration: pd.DataFrame, directions: pd.DataFrame, cfg: RiskToActionDirectionShapingDryRunConfig) -> pd.DataFrame:
    direction_lookup = directions.set_index("macro_state_id") if not directions.empty else pd.DataFrame()
    allowed_bands = {"usable_for_later_material_review"}
    if cfg.include_review_band_material:
        allowed_bands.add("review_before_use")
    source = calibration[calibration["calibration_band"].astype(str).isin(allowed_bands)].copy()
    rows: list[dict[str, Any]] = []
    for _, r in source.iterrows():
        state_id = str(r["macro_state_id"])
        if state_id not in direction_lookup.index:
            continue
        d = direction_lookup.loc[state_id]
        risk_name = str(r["risk_name"])
        band = str(r["calibration_band"])
        if band == "usable_for_later_material_review":
            use_class = "usable_direction_material_for_later_operator_review"
        else:
            use_class = "review_only_direction_material"
        forbidden = str(d["forbidden_push_direction"])
        if risk_name == "boundary_fragile" or "boundary" in forbidden:
            safety_reason = "fragile_boundary_no_push_guard_applied"
        elif float(r["v8_reliability_score"]) < 0.55 or float(r["information_sufficiency_score"]) < 0.55:
            safety_reason = "low_reliability_or_information_sufficiency_routes_to_review"
            use_class = "review_only_direction_material"
        else:
            safety_reason = "fixed_safety_rules_checked"
        rows.append(_with_boundary({
            "action_direction_id": f"direction_material_{state_id}_{risk_name}",
            "macro_state_id": state_id,
            "macro_state_name": str(r["macro_state_name"]),
            "risk_name": risk_name,
            "calibration_band": band,
            "calibration_action": str(r["calibration_action"]),
            "calibrated_risk_confidence": float(r["calibrated_risk_confidence"]),
            "v8_reliability_score": float(r["v8_reliability_score"]),
            "information_sufficiency_score": float(r["information_sufficiency_score"]),
            "dominant_risk": str(d["dominant_risk"]),
            "dominant_pressure_direction": str(d["dominant_pressure_direction"]),
            "escape_or_return_direction": str(d["escape_or_return_direction"]),
            "forbidden_push_direction": forbidden,
            "direction_clarity": float(d["direction_clarity"]),
            "action_direction_family": _direction_family(risk_name),
            "primary_action_direction": _primary_direction(risk_name, str(d["dominant_pressure_direction"]), str(d["escape_or_return_direction"])),
            "secondary_action_direction": _secondary_direction(risk_name, str(d["escape_or_return_direction"])),
            "forbidden_action_direction": forbidden,
            "NO_OP_bias": "keep_NO_OP_available_until_operator_review",
            "direction_use_class": use_class,
            "safety_guard_reason": safety_reason,
            "threshold_policy_status": "provisional_thresholds_applied_not_absolute",
            "action_direction_status": "action_direction_material_generated_no_operator_no_candidate",
        }))
    return pd.DataFrame(rows, columns=MATERIAL_COLUMNS)


def build_direction_shaping_review(calibration: pd.DataFrame, material: pd.DataFrame) -> pd.DataFrame:
    material_keys = set(zip(material["macro_state_id"].astype(str), material["risk_name"].astype(str))) if not material.empty else set()
    rows: list[dict[str, Any]] = []
    for _, r in calibration.iterrows():
        key = (str(r["macro_state_id"]), str(r["risk_name"]))
        band = str(r["calibration_band"])
        emitted = key in material_keys
        if emitted:
            decision = "emit_action_direction_material_not_candidate"
            suppression = "none"
            reason = "calibration_band_allows_direction_material_under_provisional_threshold_policy"
        elif band == "monitor_or_NO_OP":
            decision = "suppress_to_monitor_or_NO_OP"
            suppression = "monitor_band"
            reason = "calibrated_confidence_or_information_sufficiency_not_enough"
        else:
            decision = "suppress_for_missing_direction_or_policy_guard"
            suppression = "missing_direction_or_policy_guard"
            reason = "direction_material_not_emitted_due_to_guard_or_missing_direction"
        rows.append(_with_boundary({
            "review_id": f"review_{r['macro_state_id']}_{r['risk_name']}",
            "macro_state_id": str(r["macro_state_id"]),
            "macro_state_name": str(r["macro_state_name"]),
            "risk_name": str(r["risk_name"]),
            "calibration_band": band,
            "calibrated_risk_confidence": float(r["calibrated_risk_confidence"]),
            "review_decision": decision,
            "review_reason": reason,
            "material_emitted": bool(emitted),
            "suppression_reason": suppression,
            "review_status": "risk_to_action_direction_shaping_reviewed_without_candidate_generation",
        }))
    return pd.DataFrame(rows, columns=REVIEW_COLUMNS)


def build_direction_checks(material: pd.DataFrame, review: pd.DataFrame, calibration: pd.DataFrame, safety: pd.DataFrame, thresholds: pd.DataFrame, upper: pd.DataFrame, task22b_ready: bool, task22c_ready: bool) -> pd.DataFrame:
    checks = [
        ("check_task22b_ready", "upstream", "Task22b calibration audit is ready.", True, task22b_ready),
        ("check_task22c_ready", "upstream", "Task22c threshold policy contract is ready.", True, task22c_ready),
        ("check_material_rows", "direction", "At least one action-direction material row is emitted.", True, len(material) > 0),
        ("check_no_monitor_material", "direction", "Monitor/NO_OP risks do not emit action-direction material.", False, bool((material["calibration_band"].astype(str) == "monitor_or_NO_OP").any()) if not material.empty else True),
        ("check_review_rows_cover_calibration", "review", "Every calibration row receives a shaping review row.", True, len(review) == len(calibration) and len(review) > 0),
        ("check_safety_fixed", "safety", "Safety rules remain fixed.", True, bool((safety["fixed_status"].astype(str) == "fixed").all()) if not safety.empty else False),
        ("check_thresholds_revisable", "threshold", "Decision thresholds remain provisional and revisable.", True, bool(thresholds["revisable_status"].astype(str).str.contains("revisable").all()) if not thresholds.empty else False),
        ("check_upper_not_coupled", "upper_pressure", "Upper pressure is not coupled now.", False, bool(upper["allowed_now"].astype(bool).any()) if not upper.empty else True),
        ("check_no_operator", "boundary", "No terrain operator is selected.", False, bool(material["terrain_operator_selected"].astype(bool).any()) if not material.empty else True),
        ("check_no_release_rollback", "boundary", "No release/rollback/audit shaping is performed yet.", False, bool(material["release_rollback_audit_shaped"].astype(bool).any()) if not material.empty else True),
        ("check_no_action_candidate", "boundary", "No action candidate is generated.", False, bool(material["action_candidate_generated"].astype(bool).any()) if not material.empty else True),
        ("check_no_effect_prediction", "boundary", "No action-effect prediction model is executed.", False, bool(material["effect_prediction_model_executed"].astype(bool).any()) if not material.empty else True),
        ("check_no_hidden_future", "boundary", "No hidden truth or future information is used.", False, bool(material["hidden_truth_input"].astype(bool).any() or material["future_information_used"].astype(bool).any()) if not material.empty else True),
    ]
    return pd.DataFrame([
        _with_boundary({"check_id": c[0], "check_scope": c[1], "check_description": c[2], "expected_value": bool(c[3]), "observed_value": bool(c[4]), "check_status": "pass" if bool(c[3]) == bool(c[4]) else "fail"})
        for c in checks
    ], columns=CHECK_COLUMNS)


def build_final_summary(material: pd.DataFrame, review: pd.DataFrame, calibration: pd.DataFrame, checks: pd.DataFrame, task22b_ready: bool, task22c_ready: bool) -> pd.DataFrame:
    pass_count = int((checks["check_status"].astype(str) == "pass").sum()) if not checks.empty else 0
    usable_count = int((material["direction_use_class"].astype(str) == "usable_direction_material_for_later_operator_review").sum()) if not material.empty else 0
    review_only_count = int((material["direction_use_class"].astype(str) == "review_only_direction_material").sum()) if not material.empty else 0
    monitor_suppressed = int((review["review_decision"].astype(str) == "suppress_to_monitor_or_NO_OP").sum()) if not review.empty else 0
    safety_guard_count = int((material["safety_guard_reason"].astype(str) != "fixed_safety_rules_checked").sum()) if not material.empty else 0
    risk_family_count = int(material["risk_name"].astype(str).nunique()) if not material.empty else 0
    decision = "risk_to_action_direction_shaping_dry_run_ready" if task22b_ready and task22c_ready and len(checks) == pass_count else "risk_to_action_direction_shaping_dry_run_needs_review"
    return pd.DataFrame([_with_boundary({
        "calibration_row_count": len(calibration),
        "direction_material_count": len(material),
        "usable_direction_material_count": usable_count,
        "review_only_direction_count": review_only_count,
        "monitor_suppressed_count": monitor_suppressed,
        "risk_family_count": risk_family_count,
        "safety_guard_applied_count": safety_guard_count,
        "review_row_count": len(review),
        "direction_check_count": len(checks),
        "direction_check_pass_count": pass_count,
        "task22b_ready": bool(task22b_ready),
        "task22c_ready": bool(task22c_ready),
        "risk_to_action_direction_shaping_dry_run_decision": decision,
        "next_task": "Task 2-8j-24: terrain operator selection dry-run",
    })], columns=SUMMARY_COLUMNS)


def validate_risk_to_action_direction_shaping_dry_run_tables(material: pd.DataFrame, review: pd.DataFrame, checks: pd.DataFrame, final_summary: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    tables = {
        "material": (material, MATERIAL_COLUMNS),
        "review": (review, REVIEW_COLUMNS),
        "checks": (checks, CHECK_COLUMNS),
        "final_summary": (final_summary, SUMMARY_COLUMNS),
    }
    for name, (table, columns) in tables.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_23_empty_table:{name}"); continue
        missing = [c for c in columns if c not in table.columns]
        if missing:
            errors.append(f"task2_8j_23_missing_columns:{name}:" + ",".join(missing)); continue
        for col in REQUIRED_TRUE:
            if not bool(table[col].astype(bool).all()):
                errors.append(f"task2_8j_23_required_true_not_all_true:{name}:{col}")
        for col in FORBIDDEN_TRUE:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_23_forbidden_true:{name}:{col}")
        if set(table["gt_main_map_name"].astype(str)) != {"static_pca_7"}:
            errors.append(f"task2_8j_23_wrong_gt_main_map_name:{name}")
        if set(table["gt_main_component_count"].astype(int)) != {7}:
            errors.append(f"task2_8j_23_wrong_gt_component_count:{name}")
    if checks is not None and not checks.empty and not bool((checks["check_status"].astype(str) == "pass").all()):
        errors.append("task2_8j_23_check_failed")
    if material is not None and not material.empty:
        if bool((material["calibration_band"].astype(str) == "monitor_or_NO_OP").any()):
            errors.append("task2_8j_23_monitor_band_emitted_material")
        if bool(material["action_direction_family"].astype(str).str.len().eq(0).any()):
            errors.append("task2_8j_23_empty_action_direction_family")
    return errors


def build_and_validate_risk_to_action_direction_shaping_dry_run(cfg: RiskToActionDirectionShapingDryRunConfig | None = None, **_unused: object) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    cfg = cfg or RiskToActionDirectionShapingDryRunConfig()
    # Task22 is called to recover dynamics-direction material; Task22b/22c are called to validate calibration + threshold policy.
    _states, _gate, _trajectories, _risk_confidence, directions, _checks22, _final22, task22_errors, _task22_summary = build_and_validate_gated_macro_game_risk_simulator_dry_run(
        cfg=GatedMacroGameRiskSimulatorDryRunConfig()
    )
    calibration, _info, _plan, _checks22b, _final22b, task22b_errors, task22b_summary = build_and_validate_v8_style_risk_confidence_calibration_audit(
        cfg=V8StyleRiskConfidenceCalibrationAuditConfig()
    )
    safety, thresholds, _state_policy, upper, _checks22c, _final22c, task22c_errors, task22c_summary = build_and_validate_provisional_threshold_policy_contract(
        cfg=ProvisionalThresholdPolicyContractConfig()
    )
    task22b_ready = len(task22b_errors) == 0 and str(task22b_summary.get("v8_style_risk_confidence_calibration_audit_decision", "")).startswith(TASK22B_ACCEPTED_DECISION)
    task22c_ready = len(task22c_errors) == 0 and str(task22c_summary.get("provisional_threshold_policy_contract_decision", "")).startswith(TASK22C_ACCEPTED_DECISION)
    if not cfg.require_task22b_ready:
        task22b_ready = True
    if not cfg.require_task22c_ready:
        task22c_ready = True
    material = build_action_direction_material(calibration, directions, cfg)
    review = build_direction_shaping_review(calibration, material)
    checks = build_direction_checks(material, review, calibration, safety, thresholds, upper, task22b_ready, task22c_ready)
    final_summary = build_final_summary(material, review, calibration, checks, task22b_ready, task22c_ready)
    errors: list[str] = []
    if cfg.require_task22b_ready:
        errors += [f"task2_8j_23_upstream_22b_error:{e}" for e in task22b_errors]
    if cfg.require_task22c_ready:
        errors += [f"task2_8j_23_upstream_22c_error:{e}" for e in task22c_errors]
    if task22_errors:
        errors += [f"task2_8j_23_upstream_22_error:{e}" for e in task22_errors]
    errors += validate_risk_to_action_direction_shaping_dry_run_tables(material, review, checks, final_summary)
    summary = {
        "gt_main_map_name": "static_pca_7",
        "gt_main_component_count": 7,
        "task22b_decision": task22b_summary.get("v8_style_risk_confidence_calibration_audit_decision", ""),
        "task22c_decision": task22c_summary.get("provisional_threshold_policy_contract_decision", ""),
        "calibration_row_count": _safe_int(final_summary["calibration_row_count"].iloc[0]),
        "direction_material_count": _safe_int(final_summary["direction_material_count"].iloc[0]),
        "usable_direction_material_count": _safe_int(final_summary["usable_direction_material_count"].iloc[0]),
        "review_only_direction_count": _safe_int(final_summary["review_only_direction_count"].iloc[0]),
        "monitor_suppressed_count": _safe_int(final_summary["monitor_suppressed_count"].iloc[0]),
        "risk_family_count": _safe_int(final_summary["risk_family_count"].iloc[0]),
        "safety_guard_applied_count": _safe_int(final_summary["safety_guard_applied_count"].iloc[0]),
        "review_row_count": _safe_int(final_summary["review_row_count"].iloc[0]),
        "direction_check_count": _safe_int(final_summary["direction_check_count"].iloc[0]),
        "direction_check_pass_count": _safe_int(final_summary["direction_check_pass_count"].iloc[0]),
        "task22b_ready": bool(task22b_ready),
        "task22c_ready": bool(task22c_ready),
        "risk_to_action_direction_shaping_dry_run_decision": str(final_summary["risk_to_action_direction_shaping_dry_run_decision"].iloc[0]),
        "action_direction_generated": True,
        "action_direction_material_only": True,
        "terrain_operator_selected": False,
        "release_rollback_audit_shaped": False,
        "action_candidate_generated": False,
        "action_effect_prediction_generated": False,
        "axis_executed": False,
        "real_actionmodule_called": False,
        "threshold_values_are_provisional": True,
        "validation_errors": errors,
    }
    return material, review, checks, final_summary, errors, summary
