"""Task 2-8j-24: terrain operator selection dry-run RC1.

Selects provisional terrain-operator material from Task23 action-direction
material.  This is still not action-candidate generation: no release/rollback/
audit shaping, no action-effect prediction, no expected-value final judgment,
and no execution are performed.

Review-band reclassification is not applied here.  Boundary guards from Task23c
remain active, so boundary-related rows can only receive guarded operator-review
material, not concrete action candidates.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from .pressure_action_task2_8j_23_risk_to_action_direction_shaping_dry_run import (
    RiskToActionDirectionShapingDryRunConfig,
    build_and_validate_risk_to_action_direction_shaping_dry_run,
)
from .pressure_action_task2_8j_23c_review_band_reclassification_validation_plan import (
    ReviewBandReclassificationValidationPlanConfig,
    build_and_validate_review_band_reclassification_validation_plan,
)

TASK2_8J_24_VERSION = "terrain_operator_selection_dry_run_rc1"
TASK23_ACCEPTED_DECISION = "risk_to_action_direction_shaping_dry_run_ready"
TASK23C_ACCEPTED_DECISION = "review_band_reclassification_validation_plan_ready"

BOUNDARY: dict[str, Any] = {
    "task2_8j_24_version": TASK2_8J_24_VERSION,
    "validation_only": True,
    "dry_run_only": True,
    "terrain_operator_selection_only": True,
    "action_direction_material_input_used": True,
    "terrain_operator_selected": True,
    "terrain_operator_material_only": True,
    "review_band_reclassified_now": False,
    "boundary_guard_retained": True,
    "source_task23_required": True,
    "source_task23c_required": True,
    "gt_main_map_name": "static_pca_7",
    "gt_main_component_count": 7,
    "safety_rules_fixed": True,
    "decision_thresholds_revisable": True,
    "threshold_values_are_provisional": True,
    "threshold_revision_requires_validation": True,
    "no_threshold_update_performed": True,
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
    "validation_only", "dry_run_only", "terrain_operator_selection_only", "action_direction_material_input_used",
    "terrain_operator_selected", "terrain_operator_material_only", "boundary_guard_retained", "source_task23_required",
    "source_task23c_required", "safety_rules_fixed", "decision_thresholds_revisable", "threshold_values_are_provisional",
    "threshold_revision_requires_validation", "no_threshold_update_performed",
]
FORBIDDEN_TRUE = [
    "review_band_reclassified_now", "release_rollback_audit_shaped", "action_candidate_generated",
    "concrete_action_generated", "action_effect_prediction_generated", "effect_prediction_model_executed",
    "expected_value_final_judgment_performed", "real_actionmodule_called", "axis_executed", "upper_pressure_coupled_now",
    "hidden_truth_input", "future_information_used", "canonical_write_performed",
]

SELECTION_COLUMNS = list(BOUNDARY) + [
    "operator_selection_id", "macro_state_id", "macro_state_name", "risk_name", "direction_use_class",
    "primary_action_direction", "selected_operator_family", "selected_operator_name", "secondary_operator_name",
    "operator_strength_band", "operator_duration_band", "operator_trigger_mode", "operator_release_requirement",
    "operator_rollback_requirement", "operator_selection_class", "boundary_guard_mode", "NO_OP_bias",
    "selection_reason", "operator_selection_status",
]
REVIEW_COLUMNS = list(BOUNDARY) + [
    "operator_review_id", "macro_state_id", "macro_state_name", "risk_name", "direction_use_class",
    "review_decision", "review_reason", "operator_material_emitted", "review_status",
]
CHECK_COLUMNS = list(BOUNDARY) + [
    "check_id", "check_scope", "check_description", "expected_value", "observed_value", "check_status",
]
SUMMARY_COLUMNS = list(BOUNDARY) + [
    "direction_material_count", "operator_selection_count", "primary_operator_family_count", "guarded_boundary_operator_count",
    "review_suppressed_count", "operator_review_count", "operator_check_count", "operator_check_pass_count",
    "task23_ready", "task23c_ready", "terrain_operator_selection_dry_run_decision", "next_task",
]


@dataclass(frozen=True)
class TerrainOperatorSelectionDryRunConfig:
    require_task23_ready: bool = True
    require_task23c_ready: bool = True
    include_review_band_operator_hints: bool = False


def _with_boundary(row: dict[str, Any]) -> dict[str, Any]:
    return {**BOUNDARY, **row}


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def _operator_pair(risk_name: str) -> tuple[str, str, str]:
    risk_name = str(risk_name)
    if risk_name == "relation_lock":
        return "lock_relief", "soft_resistance", "escape_channel"
    if risk_name == "resource_pressure":
        return "pressure_relief", "pressure_diffusion", "buffer_injection"
    if risk_name == "reversibility_loss":
        return "return_path_support", "reversibility_support", "escape_channel"
    if risk_name == "boundary_fragile":
        return "boundary_standoff", "buffer_injection", "reversibility_support"
    if risk_name == "oscillation":
        return "oscillation_damping", "damping", "gradient_smoothing"
    return "review_unknown", "review_only_no_operator", "review_only_no_secondary"


def _guard_mode(risk_name: str, forbidden_direction: str, direction_use_class: str) -> str:
    if str(direction_use_class) != "usable_direction_material_for_later_operator_review":
        return "review_band_guard_no_operator_selection"
    if str(risk_name) == "boundary_fragile" or "boundary" in str(forbidden_direction):
        return "boundary_guard_retained_no_push"
    return "standard_operator_review_guard"


def build_terrain_operator_selection(material: pd.DataFrame, cfg: TerrainOperatorSelectionDryRunConfig) -> pd.DataFrame:
    if cfg.include_review_band_operator_hints:
        source = material[material["direction_use_class"].astype(str).isin(["usable_direction_material_for_later_operator_review", "review_only_direction_material"])].copy()
    else:
        source = material[material["direction_use_class"].astype(str) == "usable_direction_material_for_later_operator_review"].copy()
    rows: list[dict[str, Any]] = []
    for _, r in source.iterrows():
        family, primary, secondary = _operator_pair(str(r["risk_name"]))
        guard = _guard_mode(str(r["risk_name"]), str(r["forbidden_action_direction"]), str(r["direction_use_class"]))
        if str(r["direction_use_class"]) == "review_only_direction_material":
            selection_class = "guarded_review_band_operator_hint_only"
        elif guard == "boundary_guard_retained_no_push":
            selection_class = "guarded_operator_material_for_later_review"
        else:
            selection_class = "operator_material_for_later_release_rollback_audit_review"
        rows.append(_with_boundary({
            "operator_selection_id": f"operator_{r['macro_state_id']}_{r['risk_name']}",
            "macro_state_id": str(r["macro_state_id"]),
            "macro_state_name": str(r["macro_state_name"]),
            "risk_name": str(r["risk_name"]),
            "direction_use_class": str(r["direction_use_class"]),
            "primary_action_direction": str(r["primary_action_direction"]),
            "selected_operator_family": family,
            "selected_operator_name": primary,
            "secondary_operator_name": secondary,
            "operator_strength_band": "weak_0_03_to_0_08",
            "operator_duration_band": "short_1_to_2_steps",
            "operator_trigger_mode": "early_warning_or_review_gate",
            "operator_release_requirement": "fast_release_required_later_not_shaped_now",
            "operator_rollback_requirement": "high_rollback_required_later_not_shaped_now",
            "operator_selection_class": selection_class,
            "boundary_guard_mode": guard,
            "NO_OP_bias": "NO_OP_remains_available_until_effect_review",
            "selection_reason": "risk_family_and_action_direction_mapped_to_terrain_operator_material",
            "operator_selection_status": "terrain_operator_selected_as_material_only_no_candidate_no_execution",
        }))
    return pd.DataFrame(rows, columns=SELECTION_COLUMNS)


def build_operator_review(material: pd.DataFrame, selection: pd.DataFrame) -> pd.DataFrame:
    selected_keys = set(zip(selection["macro_state_id"].astype(str), selection["risk_name"].astype(str))) if not selection.empty else set()
    rows: list[dict[str, Any]] = []
    for _, r in material.iterrows():
        key = (str(r["macro_state_id"]), str(r["risk_name"]))
        emitted = key in selected_keys
        if emitted:
            decision = "operator_material_emitted_not_candidate"
            reason = "usable_direction_material_allowed_operator_selection_dry_run"
        elif str(r["direction_use_class"]) == "review_only_direction_material":
            decision = "operator_selection_suppressed_for_review_band"
            reason = "review_band_not_reclassified_now_boundary_guard_retained"
        else:
            decision = "operator_selection_suppressed_by_policy"
            reason = "operator_material_not_emitted_under_current_policy"
        rows.append(_with_boundary({
            "operator_review_id": f"operator_review_{r['macro_state_id']}_{r['risk_name']}",
            "macro_state_id": str(r["macro_state_id"]),
            "macro_state_name": str(r["macro_state_name"]),
            "risk_name": str(r["risk_name"]),
            "direction_use_class": str(r["direction_use_class"]),
            "review_decision": decision,
            "review_reason": reason,
            "operator_material_emitted": bool(emitted),
            "review_status": "terrain_operator_selection_reviewed_without_action_candidate_generation",
        }))
    return pd.DataFrame(rows, columns=REVIEW_COLUMNS)


def build_operator_checks(selection: pd.DataFrame, review: pd.DataFrame, material: pd.DataFrame, task23_ready: bool, task23c_ready: bool) -> pd.DataFrame:
    checks = [
        ("check_task23_ready", "upstream", "Task23 direction shaping is ready.", True, task23_ready),
        ("check_task23c_ready", "upstream", "Task23c review-band plan is ready.", True, task23c_ready),
        ("check_selection_rows", "operator", "At least one terrain operator material row is selected.", True, len(selection) > 0),
        ("check_review_coverage", "review", "Every direction material row receives operator review.", True, len(review) == len(material) and len(review) > 0),
        ("check_review_band_not_selected", "review", "Review-band rows are not selected as operators now.", False, bool((selection["direction_use_class"].astype(str) == "review_only_direction_material").any()) if not selection.empty else True),
        ("check_boundary_guard_retained", "boundary", "Boundary guard remains represented in selection material.", True, bool(selection["boundary_guard_mode"].astype(str).str.contains("guard").all()) if not selection.empty else False),
        ("check_no_release_rollback", "boundary", "No release/rollback/audit shaping is performed.", False, bool(selection["release_rollback_audit_shaped"].astype(bool).any()) if not selection.empty else True),
        ("check_no_action_candidate", "boundary", "No action candidate is generated.", False, bool(selection["action_candidate_generated"].astype(bool).any()) if not selection.empty else True),
        ("check_no_effect_prediction", "boundary", "No action-effect prediction is executed.", False, bool(selection["effect_prediction_model_executed"].astype(bool).any()) if not selection.empty else True),
        ("check_no_execution", "boundary", "No real ActionModule call or axis execution occurs.", False, bool(selection["real_actionmodule_called"].astype(bool).any() or selection["axis_executed"].astype(bool).any()) if not selection.empty else True),
        ("check_no_hidden_future", "boundary", "No hidden truth or future information is used.", False, bool(selection["hidden_truth_input"].astype(bool).any() or selection["future_information_used"].astype(bool).any()) if not selection.empty else True),
    ]
    return pd.DataFrame([
        _with_boundary({"check_id": c[0], "check_scope": c[1], "check_description": c[2], "expected_value": bool(c[3]), "observed_value": bool(c[4]), "check_status": "pass" if bool(c[3]) == bool(c[4]) else "fail"})
        for c in checks
    ], columns=CHECK_COLUMNS)


def build_final_summary(selection: pd.DataFrame, review: pd.DataFrame, material: pd.DataFrame, checks: pd.DataFrame, task23_ready: bool, task23c_ready: bool) -> pd.DataFrame:
    pass_count = int((checks["check_status"].astype(str) == "pass").sum()) if not checks.empty else 0
    family_count = int(selection["selected_operator_family"].astype(str).nunique()) if not selection.empty else 0
    guarded_count = int(selection["boundary_guard_mode"].astype(str).str.contains("boundary_guard").sum()) if not selection.empty else 0
    review_suppressed = int((review["review_decision"].astype(str) == "operator_selection_suppressed_for_review_band").sum()) if not review.empty else 0
    decision = "terrain_operator_selection_dry_run_ready" if task23_ready and task23c_ready and len(checks) == pass_count else "terrain_operator_selection_dry_run_needs_review"
    return pd.DataFrame([_with_boundary({
        "direction_material_count": len(material),
        "operator_selection_count": len(selection),
        "primary_operator_family_count": family_count,
        "guarded_boundary_operator_count": guarded_count,
        "review_suppressed_count": review_suppressed,
        "operator_review_count": len(review),
        "operator_check_count": len(checks),
        "operator_check_pass_count": pass_count,
        "task23_ready": bool(task23_ready),
        "task23c_ready": bool(task23c_ready),
        "terrain_operator_selection_dry_run_decision": decision,
        "next_task": "Task 2-8j-25: release rollback audit shaping dry-run",
    })], columns=SUMMARY_COLUMNS)


def validate_terrain_operator_selection_dry_run_tables(selection: pd.DataFrame, review: pd.DataFrame, checks: pd.DataFrame, final_summary: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    tables = {"selection": (selection, SELECTION_COLUMNS), "review": (review, REVIEW_COLUMNS), "checks": (checks, CHECK_COLUMNS), "final_summary": (final_summary, SUMMARY_COLUMNS)}
    for name, (table, columns) in tables.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_24_empty_table:{name}"); continue
        missing = [c for c in columns if c not in table.columns]
        if missing:
            errors.append(f"task2_8j_24_missing_columns:{name}:" + ",".join(missing)); continue
        for col in REQUIRED_TRUE:
            if not bool(table[col].astype(bool).all()):
                errors.append(f"task2_8j_24_required_true_not_all_true:{name}:{col}")
        for col in FORBIDDEN_TRUE:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_24_forbidden_true:{name}:{col}")
        if set(table["gt_main_map_name"].astype(str)) != {"static_pca_7"}:
            errors.append(f"task2_8j_24_wrong_gt_main_map_name:{name}")
        if set(table["gt_main_component_count"].astype(int)) != {7}:
            errors.append(f"task2_8j_24_wrong_gt_component_count:{name}")
    if checks is not None and not checks.empty and not bool((checks["check_status"].astype(str) == "pass").all()):
        errors.append("task2_8j_24_check_failed")
    if selection is not None and not selection.empty:
        if bool((selection["direction_use_class"].astype(str) == "review_only_direction_material").any()):
            errors.append("task2_8j_24_review_band_operator_selected_now")
    return errors


def build_and_validate_terrain_operator_selection_dry_run(cfg: TerrainOperatorSelectionDryRunConfig | None = None, **_unused: object) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    cfg = cfg or TerrainOperatorSelectionDryRunConfig()
    material, _review23, _checks23, _final23, task23_errors, task23_summary = build_and_validate_risk_to_action_direction_shaping_dry_run(cfg=RiskToActionDirectionShapingDryRunConfig())
    _policy, _guards, _plan, _candidates, _checks23c, _final23c, task23c_errors, task23c_summary = build_and_validate_review_band_reclassification_validation_plan(cfg=ReviewBandReclassificationValidationPlanConfig())
    task23_ready = len(task23_errors) == 0 and str(task23_summary.get("risk_to_action_direction_shaping_dry_run_decision", "")).startswith(TASK23_ACCEPTED_DECISION)
    task23c_ready = len(task23c_errors) == 0 and str(task23c_summary.get("review_band_reclassification_validation_plan_decision", "")).startswith(TASK23C_ACCEPTED_DECISION)
    if not cfg.require_task23_ready:
        task23_ready = True
    if not cfg.require_task23c_ready:
        task23c_ready = True
    selection = build_terrain_operator_selection(material, cfg)
    review = build_operator_review(material, selection)
    checks = build_operator_checks(selection, review, material, task23_ready, task23c_ready)
    final_summary = build_final_summary(selection, review, material, checks, task23_ready, task23c_ready)
    errors: list[str] = []
    if cfg.require_task23_ready:
        errors += [f"task2_8j_24_upstream_23_error:{e}" for e in task23_errors]
    if cfg.require_task23c_ready:
        errors += [f"task2_8j_24_upstream_23c_error:{e}" for e in task23c_errors]
    errors += validate_terrain_operator_selection_dry_run_tables(selection, review, checks, final_summary)
    summary = {
        "gt_main_map_name": "static_pca_7",
        "gt_main_component_count": 7,
        "task23_decision": task23_summary.get("risk_to_action_direction_shaping_dry_run_decision", ""),
        "task23c_decision": task23c_summary.get("review_band_reclassification_validation_plan_decision", ""),
        "direction_material_count": _safe_int(final_summary["direction_material_count"].iloc[0]),
        "operator_selection_count": _safe_int(final_summary["operator_selection_count"].iloc[0]),
        "primary_operator_family_count": _safe_int(final_summary["primary_operator_family_count"].iloc[0]),
        "guarded_boundary_operator_count": _safe_int(final_summary["guarded_boundary_operator_count"].iloc[0]),
        "review_suppressed_count": _safe_int(final_summary["review_suppressed_count"].iloc[0]),
        "operator_review_count": _safe_int(final_summary["operator_review_count"].iloc[0]),
        "operator_check_count": _safe_int(final_summary["operator_check_count"].iloc[0]),
        "operator_check_pass_count": _safe_int(final_summary["operator_check_pass_count"].iloc[0]),
        "task23_ready": bool(task23_ready),
        "task23c_ready": bool(task23c_ready),
        "terrain_operator_selection_dry_run_decision": str(final_summary["terrain_operator_selection_dry_run_decision"].iloc[0]),
        "terrain_operator_selected": True,
        "terrain_operator_material_only": True,
        "review_band_reclassified_now": False,
        "boundary_guard_retained": True,
        "release_rollback_audit_shaped": False,
        "action_candidate_generated": False,
        "action_effect_prediction_generated": False,
        "axis_executed": False,
        "real_actionmodule_called": False,
        "validation_errors": errors,
    }
    return selection, review, checks, final_summary, errors, summary
