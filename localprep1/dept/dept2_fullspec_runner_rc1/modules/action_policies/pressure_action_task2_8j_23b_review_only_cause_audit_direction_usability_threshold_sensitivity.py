"""Task 2-8j-23b: review-only cause audit + direction usability threshold sensitivity RC1.

Audits why Task2-8j-23 action-direction material is routed to review-only and
runs a provisional threshold-sensitivity table.  This task does not update any
thresholds.  It only identifies candidate causes and candidate threshold ranges
that should be tested later through delayed observation / validation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from .pressure_action_task2_8j_22b_v8_style_risk_confidence_calibration_audit import (
    V8StyleRiskConfidenceCalibrationAuditConfig,
    build_and_validate_v8_style_risk_confidence_calibration_audit,
)
from .pressure_action_task2_8j_23_risk_to_action_direction_shaping_dry_run import (
    RiskToActionDirectionShapingDryRunConfig,
    build_and_validate_risk_to_action_direction_shaping_dry_run,
)

TASK2_8J_23B_VERSION = "review_only_cause_audit_direction_usability_threshold_sensitivity_rc1"
TASK23_ACCEPTED_DECISION = "risk_to_action_direction_shaping_dry_run_ready"
TASK22B_ACCEPTED_DECISION = "v8_style_risk_confidence_calibration_audit_ready"

BOUNDARY: dict[str, Any] = {
    "task2_8j_23b_version": TASK2_8J_23B_VERSION,
    "validation_only": True,
    "audit_only": True,
    "sensitivity_only": True,
    "review_only_cause_audit": True,
    "direction_usability_threshold_sensitivity": True,
    "no_threshold_update_performed": True,
    "threshold_values_are_provisional": True,
    "threshold_revision_requires_validation": True,
    "safety_rules_fixed": True,
    "decision_thresholds_revisable": True,
    "system_state_sensitive_thresholds": True,
    "source_task23_required": True,
    "source_task22b_required": True,
    "gt_main_map_name": "static_pca_7",
    "gt_main_component_count": 7,
    "action_direction_material_input_used": True,
    "new_action_direction_generated": False,
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
    "validation_only", "audit_only", "sensitivity_only", "review_only_cause_audit",
    "direction_usability_threshold_sensitivity", "no_threshold_update_performed", "threshold_values_are_provisional",
    "threshold_revision_requires_validation", "safety_rules_fixed", "decision_thresholds_revisable",
    "system_state_sensitive_thresholds", "source_task23_required", "source_task22b_required", "action_direction_material_input_used",
]
FORBIDDEN_TRUE = [
    "new_action_direction_generated", "terrain_operator_selected", "release_rollback_audit_shaped", "action_candidate_generated",
    "concrete_action_generated", "action_effect_prediction_generated", "effect_prediction_model_executed",
    "expected_value_final_judgment_performed", "real_actionmodule_called", "axis_executed", "upper_pressure_coupled_now",
    "hidden_truth_input", "future_information_used", "canonical_write_performed",
]

CAUSE_COLUMNS = list(BOUNDARY) + [
    "cause_audit_id", "macro_state_id", "macro_state_name", "risk_name", "calibration_band",
    "calibrated_risk_confidence", "v8_reliability_score", "information_sufficiency_score", "direction_clarity",
    "direction_use_class", "safety_guard_reason", "review_only_primary_cause", "review_only_secondary_causes",
    "would_need_validation_for_usability", "cause_audit_status",
]
SENSITIVITY_COLUMNS = list(BOUNDARY) + [
    "sensitivity_id", "sensitivity_mode", "usable_threshold_candidate", "minimum_reliability_candidate",
    "minimum_information_sufficiency_candidate", "minimum_direction_clarity_candidate", "boundary_guard_mode",
    "eligible_material_count", "newly_eligible_count", "still_review_or_monitor_count", "sensitivity_interpretation",
    "may_update_threshold_now", "requires_validation_before_update", "sensitivity_status",
]
SUMMARY_CAUSE_COLUMNS = list(BOUNDARY) + [
    "cause_summary_id", "review_only_primary_cause", "cause_count", "cause_share", "dominant_risk_families",
    "cause_summary_status",
]
CHECK_COLUMNS = list(BOUNDARY) + [
    "check_id", "check_scope", "check_description", "expected_value", "observed_value", "check_status",
]
SUMMARY_COLUMNS = list(BOUNDARY) + [
    "direction_material_count", "review_only_direction_count", "cause_audit_count", "cause_summary_count",
    "sensitivity_row_count", "positive_sensitivity_row_count", "max_eligible_material_count", "threshold_update_candidate_count",
    "audit_check_count", "audit_check_pass_count", "task23_ready", "task22b_ready",
    "review_only_cause_audit_direction_usability_threshold_sensitivity_decision", "next_task",
]


@dataclass(frozen=True)
class ReviewOnlyCauseAuditThresholdSensitivityConfig:
    require_task23_ready: bool = True
    require_task22b_ready: bool = True


def _with_boundary(row: dict[str, Any]) -> dict[str, Any]:
    return {**BOUNDARY, **row}


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def _primary_cause(row: pd.Series) -> tuple[str, str]:
    secondary: list[str] = []
    if str(row["calibration_band"]) == "review_before_use":
        secondary.append("calibration_band_review_before_use")
    if float(row["v8_reliability_score"]) < 0.55:
        secondary.append("v8_reliability_below_current_provisional_cut")
    if float(row["information_sufficiency_score"]) < 0.55:
        secondary.append("information_sufficiency_below_current_provisional_cut")
    if float(row["direction_clarity"]) < 0.48:
        secondary.append("direction_clarity_below_current_provisional_cut")
    if "boundary" in str(row["safety_guard_reason"]) or "boundary" in str(row["forbidden_action_direction"]):
        secondary.append("boundary_guard_present")
    if str(row["direction_use_class"]) == "review_only_direction_material":
        secondary.append("task23_review_only_route")
    if "calibration_band_review_before_use" in secondary:
        primary = "calibration_band_review_before_use"
    elif "v8_reliability_below_current_provisional_cut" in secondary:
        primary = "v8_reliability_below_current_provisional_cut"
    elif "information_sufficiency_below_current_provisional_cut" in secondary:
        primary = "information_sufficiency_below_current_provisional_cut"
    elif "direction_clarity_below_current_provisional_cut" in secondary:
        primary = "direction_clarity_below_current_provisional_cut"
    elif "boundary_guard_present" in secondary:
        primary = "boundary_guard_present"
    else:
        primary = "review_only_route_without_single_numeric_blocker"
    return primary, ";".join(secondary) if secondary else "none"


def build_review_only_cause_audit(material: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    review_only = material[material["direction_use_class"].astype(str) == "review_only_direction_material"].copy()
    if review_only.empty and not material.empty:
        review_only = material.copy()
    for _, r in review_only.iterrows():
        primary, secondary = _primary_cause(r)
        rows.append(_with_boundary({
            "cause_audit_id": f"cause_{r['macro_state_id']}_{r['risk_name']}",
            "macro_state_id": str(r["macro_state_id"]),
            "macro_state_name": str(r["macro_state_name"]),
            "risk_name": str(r["risk_name"]),
            "calibration_band": str(r["calibration_band"]),
            "calibrated_risk_confidence": float(r["calibrated_risk_confidence"]),
            "v8_reliability_score": float(r["v8_reliability_score"]),
            "information_sufficiency_score": float(r["information_sufficiency_score"]),
            "direction_clarity": float(r["direction_clarity"]),
            "direction_use_class": str(r["direction_use_class"]),
            "safety_guard_reason": str(r["safety_guard_reason"]),
            "review_only_primary_cause": primary,
            "review_only_secondary_causes": secondary,
            "would_need_validation_for_usability": True,
            "cause_audit_status": "review_only_cause_audited_no_threshold_update",
        }))
    return pd.DataFrame(rows, columns=CAUSE_COLUMNS)


def build_cause_summary(cause_audit: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    total = max(1, len(cause_audit))
    for i, (cause, group) in enumerate(cause_audit.groupby("review_only_primary_cause", sort=False), start=1):
        families = ";".join(sorted(set(group["risk_name"].astype(str))))
        rows.append(_with_boundary({
            "cause_summary_id": f"cause_summary_{i:03d}",
            "review_only_primary_cause": str(cause),
            "cause_count": int(len(group)),
            "cause_share": round(len(group) / total, 6),
            "dominant_risk_families": families,
            "cause_summary_status": "cause_summary_ready",
        }))
    return pd.DataFrame(rows, columns=SUMMARY_CAUSE_COLUMNS)


def _eligible_count(material: pd.DataFrame, usable_thr: float, rel_thr: float, info_thr: float, clarity_thr: float, mode: str, boundary_guard_mode: str) -> int:
    if material.empty:
        return 0
    source = material.copy()
    if mode == "current_band_only":
        source = source[source["calibration_band"].astype(str) == "usable_for_later_material_review"]
    elif mode == "allow_review_band_reclassification":
        source = source[source["calibration_band"].astype(str).isin(["usable_for_later_material_review", "review_before_use"])]
    if boundary_guard_mode == "strict_no_boundary_guard":
        source = source[~source["forbidden_action_direction"].astype(str).str.contains("boundary", na=False)]
    elif boundary_guard_mode == "boundary_allowed_as_review_material_only":
        # Boundary risk may be direction material, but not automatic usability unless other evidence is strong.
        source = source[(source["calibrated_risk_confidence"].astype(float) >= max(usable_thr, 0.70)) | (~source["forbidden_action_direction"].astype(str).str.contains("boundary", na=False))]
    eligible = source[
        (source["calibrated_risk_confidence"].astype(float) >= usable_thr)
        & (source["v8_reliability_score"].astype(float) >= rel_thr)
        & (source["information_sufficiency_score"].astype(float) >= info_thr)
        & (source["direction_clarity"].astype(float) >= clarity_thr)
    ]
    return int(len(eligible))


def build_direction_usability_threshold_sensitivity(material: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    current_usable = int((material["direction_use_class"].astype(str) == "usable_direction_material_for_later_operator_review").sum()) if not material.empty else 0
    usable_candidates = [0.66, 0.62, 0.58, 0.54]
    rel_candidates = [0.55, 0.50, 0.45]
    info_candidates = [0.55, 0.50, 0.45]
    clarity_candidates = [0.48, 0.36, 0.24]
    modes = ["current_band_only", "allow_review_band_reclassification"]
    boundary_modes = ["strict_no_boundary_guard", "boundary_allowed_as_review_material_only", "boundary_guard_kept_as_review_guard"]
    idx = 1
    for mode in modes:
        for boundary_mode in boundary_modes:
            for usable_thr in usable_candidates:
                for rel_thr in rel_candidates:
                    for info_thr in info_candidates:
                        for clarity_thr in clarity_candidates:
                            eligible = _eligible_count(material, usable_thr, rel_thr, info_thr, clarity_thr, mode, boundary_mode)
                            newly = max(0, eligible - current_usable)
                            still = max(0, len(material) - eligible)
                            if eligible == 0:
                                interpretation = "still_review_only_under_this_candidate_policy"
                            elif newly > 0:
                                interpretation = "candidate_policy_would_increase_usable_material_but_requires_validation"
                            else:
                                interpretation = "candidate_policy_matches_current_or_no_gain"
                            rows.append(_with_boundary({
                                "sensitivity_id": f"sens_{idx:04d}",
                                "sensitivity_mode": mode,
                                "usable_threshold_candidate": usable_thr,
                                "minimum_reliability_candidate": rel_thr,
                                "minimum_information_sufficiency_candidate": info_thr,
                                "minimum_direction_clarity_candidate": clarity_thr,
                                "boundary_guard_mode": boundary_mode,
                                "eligible_material_count": eligible,
                                "newly_eligible_count": newly,
                                "still_review_or_monitor_count": still,
                                "sensitivity_interpretation": interpretation,
                                "may_update_threshold_now": False,
                                "requires_validation_before_update": True,
                                "sensitivity_status": "threshold_sensitivity_audited_no_update",
                            }))
                            idx += 1
    return pd.DataFrame(rows, columns=SENSITIVITY_COLUMNS)


def build_audit_checks(cause_audit: pd.DataFrame, cause_summary: pd.DataFrame, sensitivity: pd.DataFrame, material: pd.DataFrame, task23_ready: bool, task22b_ready: bool) -> pd.DataFrame:
    checks = [
        ("check_task23_ready", "upstream", "Task23 direction shaping dry-run is ready.", True, task23_ready),
        ("check_task22b_ready", "upstream", "Task22b calibration audit is ready.", True, task22b_ready),
        ("check_cause_audit_rows", "cause", "Review-only cause audit rows exist.", True, len(cause_audit) > 0),
        ("check_cause_summary", "cause", "Cause summary rows exist.", True, len(cause_summary) > 0),
        ("check_sensitivity_rows", "sensitivity", "Threshold sensitivity rows exist.", True, len(sensitivity) > 0),
        ("check_no_threshold_update", "threshold", "No threshold update is performed now.", False, bool(sensitivity["may_update_threshold_now"].astype(bool).any()) if not sensitivity.empty else True),
        ("check_requires_validation", "threshold", "Every sensitivity update candidate requires validation.", True, bool(sensitivity["requires_validation_before_update"].astype(bool).all()) if not sensitivity.empty else False),
        ("check_has_positive_sensitivity", "sensitivity", "At least one candidate policy increases eligible material, for later testing.", True, bool((sensitivity["newly_eligible_count"].astype(int) > 0).any()) if not sensitivity.empty else False),
        ("check_material_input", "direction", "Task23 action-direction material is used only as input.", True, len(material) > 0),
        ("check_no_new_direction", "boundary", "No new action direction is generated in Task23b.", False, bool(cause_audit["new_action_direction_generated"].astype(bool).any()) if not cause_audit.empty else True),
        ("check_no_operator", "boundary", "No terrain operator is selected.", False, bool(cause_audit["terrain_operator_selected"].astype(bool).any()) if not cause_audit.empty else True),
        ("check_no_action_candidate", "boundary", "No action candidate is generated.", False, bool(cause_audit["action_candidate_generated"].astype(bool).any()) if not cause_audit.empty else True),
        ("check_no_hidden_future", "boundary", "No hidden truth or future information is used.", False, bool(cause_audit["hidden_truth_input"].astype(bool).any() or cause_audit["future_information_used"].astype(bool).any()) if not cause_audit.empty else True),
    ]
    return pd.DataFrame([
        _with_boundary({"check_id": c[0], "check_scope": c[1], "check_description": c[2], "expected_value": bool(c[3]), "observed_value": bool(c[4]), "check_status": "pass" if bool(c[3]) == bool(c[4]) else "fail"})
        for c in checks
    ], columns=CHECK_COLUMNS)


def build_final_summary(material: pd.DataFrame, cause_audit: pd.DataFrame, cause_summary: pd.DataFrame, sensitivity: pd.DataFrame, checks: pd.DataFrame, task23_ready: bool, task22b_ready: bool) -> pd.DataFrame:
    pass_count = int((checks["check_status"].astype(str) == "pass").sum()) if not checks.empty else 0
    positive = int((sensitivity["newly_eligible_count"].astype(int) > 0).sum()) if not sensitivity.empty else 0
    max_eligible = int(sensitivity["eligible_material_count"].astype(int).max()) if not sensitivity.empty else 0
    update_candidate_count = int(((sensitivity["newly_eligible_count"].astype(int) > 0) & sensitivity["requires_validation_before_update"].astype(bool)).sum()) if not sensitivity.empty else 0
    decision = "review_only_cause_audit_direction_usability_threshold_sensitivity_ready" if task23_ready and task22b_ready and len(checks) == pass_count else "review_only_cause_audit_direction_usability_threshold_sensitivity_needs_review"
    return pd.DataFrame([_with_boundary({
        "direction_material_count": len(material),
        "review_only_direction_count": len(cause_audit),
        "cause_audit_count": len(cause_audit),
        "cause_summary_count": len(cause_summary),
        "sensitivity_row_count": len(sensitivity),
        "positive_sensitivity_row_count": positive,
        "max_eligible_material_count": max_eligible,
        "threshold_update_candidate_count": update_candidate_count,
        "audit_check_count": len(checks),
        "audit_check_pass_count": pass_count,
        "task23_ready": bool(task23_ready),
        "task22b_ready": bool(task22b_ready),
        "review_only_cause_audit_direction_usability_threshold_sensitivity_decision": decision,
        "next_task": "Task 2-8j-24: terrain operator selection dry-run",
    })], columns=SUMMARY_COLUMNS)


def validate_review_only_cause_audit_threshold_sensitivity_tables(cause_audit: pd.DataFrame, cause_summary: pd.DataFrame, sensitivity: pd.DataFrame, checks: pd.DataFrame, final_summary: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    tables = {
        "cause_audit": (cause_audit, CAUSE_COLUMNS),
        "cause_summary": (cause_summary, SUMMARY_CAUSE_COLUMNS),
        "sensitivity": (sensitivity, SENSITIVITY_COLUMNS),
        "checks": (checks, CHECK_COLUMNS),
        "final_summary": (final_summary, SUMMARY_COLUMNS),
    }
    for name, (table, columns) in tables.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_23b_empty_table:{name}"); continue
        missing = [c for c in columns if c not in table.columns]
        if missing:
            errors.append(f"task2_8j_23b_missing_columns:{name}:" + ",".join(missing)); continue
        for col in REQUIRED_TRUE:
            if not bool(table[col].astype(bool).all()):
                errors.append(f"task2_8j_23b_required_true_not_all_true:{name}:{col}")
        for col in FORBIDDEN_TRUE:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_23b_forbidden_true:{name}:{col}")
        if set(table["gt_main_map_name"].astype(str)) != {"static_pca_7"}:
            errors.append(f"task2_8j_23b_wrong_gt_main_map_name:{name}")
        if set(table["gt_main_component_count"].astype(int)) != {7}:
            errors.append(f"task2_8j_23b_wrong_gt_component_count:{name}")
    if checks is not None and not checks.empty and not bool((checks["check_status"].astype(str) == "pass").all()):
        errors.append("task2_8j_23b_check_failed")
    if sensitivity is not None and not sensitivity.empty:
        if bool(sensitivity["may_update_threshold_now"].astype(bool).any()):
            errors.append("task2_8j_23b_threshold_update_attempted")
        if not bool(sensitivity["requires_validation_before_update"].astype(bool).all()):
            errors.append("task2_8j_23b_sensitivity_without_validation_requirement")
    return errors


def build_and_validate_review_only_cause_audit_threshold_sensitivity(cfg: ReviewOnlyCauseAuditThresholdSensitivityConfig | None = None, **_unused: object) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    cfg = cfg or ReviewOnlyCauseAuditThresholdSensitivityConfig()
    material, _review, _checks23, _final23, task23_errors, task23_summary = build_and_validate_risk_to_action_direction_shaping_dry_run(
        cfg=RiskToActionDirectionShapingDryRunConfig()
    )
    _cal, _info, _plan, _checks22b, _final22b, task22b_errors, task22b_summary = build_and_validate_v8_style_risk_confidence_calibration_audit(
        cfg=V8StyleRiskConfidenceCalibrationAuditConfig()
    )
    task23_ready = len(task23_errors) == 0 and str(task23_summary.get("risk_to_action_direction_shaping_dry_run_decision", "")).startswith(TASK23_ACCEPTED_DECISION)
    task22b_ready = len(task22b_errors) == 0 and str(task22b_summary.get("v8_style_risk_confidence_calibration_audit_decision", "")).startswith(TASK22B_ACCEPTED_DECISION)
    if not cfg.require_task23_ready:
        task23_ready = True
    if not cfg.require_task22b_ready:
        task22b_ready = True
    cause_audit = build_review_only_cause_audit(material)
    cause_summary = build_cause_summary(cause_audit)
    sensitivity = build_direction_usability_threshold_sensitivity(material)
    checks = build_audit_checks(cause_audit, cause_summary, sensitivity, material, task23_ready, task22b_ready)
    final_summary = build_final_summary(material, cause_audit, cause_summary, sensitivity, checks, task23_ready, task22b_ready)
    errors: list[str] = []
    if cfg.require_task23_ready:
        errors += [f"task2_8j_23b_upstream_23_error:{e}" for e in task23_errors]
    if cfg.require_task22b_ready:
        errors += [f"task2_8j_23b_upstream_22b_error:{e}" for e in task22b_errors]
    errors += validate_review_only_cause_audit_threshold_sensitivity_tables(cause_audit, cause_summary, sensitivity, checks, final_summary)
    summary = {
        "gt_main_map_name": "static_pca_7",
        "gt_main_component_count": 7,
        "task23_decision": task23_summary.get("risk_to_action_direction_shaping_dry_run_decision", ""),
        "task22b_decision": task22b_summary.get("v8_style_risk_confidence_calibration_audit_decision", ""),
        "direction_material_count": _safe_int(final_summary["direction_material_count"].iloc[0]),
        "review_only_direction_count": _safe_int(final_summary["review_only_direction_count"].iloc[0]),
        "cause_audit_count": _safe_int(final_summary["cause_audit_count"].iloc[0]),
        "cause_summary_count": _safe_int(final_summary["cause_summary_count"].iloc[0]),
        "sensitivity_row_count": _safe_int(final_summary["sensitivity_row_count"].iloc[0]),
        "positive_sensitivity_row_count": _safe_int(final_summary["positive_sensitivity_row_count"].iloc[0]),
        "max_eligible_material_count": _safe_int(final_summary["max_eligible_material_count"].iloc[0]),
        "threshold_update_candidate_count": _safe_int(final_summary["threshold_update_candidate_count"].iloc[0]),
        "audit_check_count": _safe_int(final_summary["audit_check_count"].iloc[0]),
        "audit_check_pass_count": _safe_int(final_summary["audit_check_pass_count"].iloc[0]),
        "task23_ready": bool(task23_ready),
        "task22b_ready": bool(task22b_ready),
        "review_only_cause_audit_direction_usability_threshold_sensitivity_decision": str(final_summary["review_only_cause_audit_direction_usability_threshold_sensitivity_decision"].iloc[0]),
        "no_threshold_update_performed": True,
        "threshold_values_are_provisional": True,
        "threshold_revision_requires_validation": True,
        "new_action_direction_generated": False,
        "terrain_operator_selected": False,
        "action_candidate_generated": False,
        "action_effect_prediction_generated": False,
        "axis_executed": False,
        "real_actionmodule_called": False,
        "validation_errors": errors,
    }
    return cause_audit, cause_summary, sensitivity, checks, final_summary, errors, summary
