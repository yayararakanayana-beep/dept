"""Task 2-8j-12: new-G_t upper-layer revalidation RC1.

Purpose:
    Revalidate the upper-pressure route after the G_t main map was updated to
    fixed static_pca_7.  The validation checks whether G_t / K_t global summary
    can be accepted, projected into an M_t compatibility view, and converted into
    bounded / weak / reversible upper-pressure candidates.

Position:
    Tasks 2-8j-7 through 2-8j-11 validated the O_t / game-structure route.
    Before entering the action-module side action-axis material contract, this
    task rechecks the sibling upper-pressure route:

        G_t / K_t global -> M_t -> upper pressure

    This is a health-check for the upper layer after the new G_t map update.
    It is not an O_t route validation, not an action-axis generation step, and
    not an ActionModule call.

Boundary:
    - upper-layer revalidation only
    - fixed static_pca_7 G_t main map
    - G_t / K_t global summary may be used
    - M_t compatibility view is projected as 15 bounded components
    - upper-pressure candidates must stay weak / bounded / reversible / NO_OP-capable
    - no O_t route input, no game-structure prediction envelope input
    - no action-axis generation, action candidate, ActionModule call, runtime call, writeback, hidden-truth / future-information input, or axis mutation
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .pressure_action_task2_8j_6c_v2_structure_change_relation_field_tracking import (
    V2StructureChangeTrackingConfig,
    build_and_validate_v2_structure_change_relation_field_tracking,
)

TASK2_8J_12_VERSION = "new_gt_upper_layer_revalidation_rc1"
TASK2_8J_12_CONTRACT = (
    "Task2_8j_12_new_Gt_upper_layer_revalidation__"
    "fixed_static_pca_7_Gt_Kt_global_to_Mt15_to_bounded_upper_pressure__"
    "no_Ot_no_prediction_envelope_no_actionmodule_no_runtime_no_writeback"
)

MT_COMPONENTS_15 = [
    "stability",
    "adaptability",
    "exploration",
    "efficiency",
    "robustness",
    "structural_diversity",
    "trajectory_dynamics",
    "predictability",
    "coherence",
    "recoverability",
    "novelty_quality",
    "relation_lock_risk_control",
    "information_integrity",
    "reversibility",
    "resource_balance",
]

BOUNDARY = {
    "task2_8j_12_version": TASK2_8J_12_VERSION,
    "task2_8j_12_contract": TASK2_8J_12_CONTRACT,
    "validation_only": True,
    "upper_layer_revalidation_only": True,
    "gt_main_map_name": "static_pca_7",
    "gt_main_component_count": 7,
    "kt_global_summary_used": True,
    "mt_compatibility_component_count": 15,
    "upper_pressure_route_checked": True,
    "bounded_upper_pressure_required": True,
    "weak_pressure_required": True,
    "reversible_pressure_required": True,
    "no_op_allowed_required": True,
    "rollback_required": True,
    "ot_route_input_used": False,
    "ot_observation_map_used": False,
    "game_structure_prediction_envelope_used": False,
    "action_axis_generated": False,
    "action_candidate_generated": False,
    "action_translation_performed": False,
    "action_input_converted": False,
    "action_frame_created": False,
    "real_actionmodule_called": False,
    "actionmodule_called": False,
    "runtime_policy_input": False,
    "fullspec_runtime_connected": False,
    "canonical_write_performed": False,
    "gk_writeback_performed": False,
    "ot_writeback_performed": False,
    "effective_dimension_refit_performed": False,
    "axis_mutation_performed": False,
    "residual_auxiliary_injected_into_gt_main": False,
    "hidden_truth_input": False,
    "future_information_used": False,
}

FORBIDDEN_TRUE = [
    "ot_route_input_used",
    "ot_observation_map_used",
    "game_structure_prediction_envelope_used",
    "action_axis_generated",
    "action_candidate_generated",
    "action_translation_performed",
    "action_input_converted",
    "action_frame_created",
    "real_actionmodule_called",
    "actionmodule_called",
    "runtime_policy_input",
    "fullspec_runtime_connected",
    "canonical_write_performed",
    "gk_writeback_performed",
    "ot_writeback_performed",
    "effective_dimension_refit_performed",
    "axis_mutation_performed",
    "residual_auxiliary_injected_into_gt_main",
    "hidden_truth_input",
    "future_information_used",
]

REQUIRED_GK_COLUMNS = list(BOUNDARY) + [
    "phase_name",
    "phase_order",
    "gt_input_status",
    "kt_input_status",
    "state_count",
    "reproduced_state_count",
    "mean_state_r2",
    "mean_state_correlation",
    "mean_state_event_accuracy",
    "weak_state_names",
    "kt_updated_minus_stale_event_accuracy",
    "kt_updated_minus_stale_correlation",
    "gk_global_acceptance_status",
]

REQUIRED_MT_COLUMNS = list(BOUNDARY) + [
    "phase_name",
    "phase_order",
    "mt_component_name",
    "mt_component_value",
    "mt_source_fields",
    "mt_value_finite",
    "mt_value_bounded_0_1",
    "mt_component_status",
]

REQUIRED_PRESSURE_COLUMNS = list(BOUNDARY) + [
    "phase_name",
    "phase_order",
    "pressure_candidate_id",
    "pressure_family",
    "source_mt_component",
    "source_mt_value",
    "pressure_polarity",
    "raw_pressure_magnitude",
    "bounded_pressure_magnitude",
    "pressure_time_scale",
    "reversible",
    "no_op_allowed",
    "rollback_policy",
    "safety_projection_status",
    "upper_pressure_candidate_status",
]

REQUIRED_SAFETY_COLUMNS = list(BOUNDARY) + [
    "safety_check_id",
    "phase_name",
    "check_description",
    "expected_value",
    "observed_value",
    "safety_check_status",
]

REQUIRED_SUMMARY_COLUMNS = list(BOUNDARY) + [
    "gk_input_phase_count",
    "mt_component_total_count",
    "mt_phase_count",
    "mt_component_count_per_phase",
    "mt_finite_count",
    "mt_bounded_count",
    "upper_pressure_candidate_count",
    "safety_check_count",
    "safety_check_pass_count",
    "max_bounded_pressure_magnitude",
    "no_op_candidate_count",
    "new_gt_upper_layer_revalidation_decision",
    "next_task",
]


@dataclass(frozen=True)
class NewGtUpperLayerRevalidationConfig:
    weak_pressure_max: float = 0.20
    no_op_magnitude_threshold: float = 0.015
    mt_low_component_threshold: float = 0.60


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return float(default)
    if not np.isfinite(out):
        return float(default)
    return float(out)


def _clip01(value: float) -> float:
    return float(min(1.0, max(0.0, value)))


def _phase_kt_lookup(stale_updated: pd.DataFrame) -> dict[str, tuple[float, float]]:
    if stale_updated is None or stale_updated.empty:
        return {}
    out: dict[str, tuple[float, float]] = {}
    for row in stale_updated.itertuples(index=False):
        out[str(row.target_state_phase)] = (
            _safe_float(row.updated_minus_stale_event_accuracy),
            _safe_float(row.updated_minus_stale_correlation),
        )
    return out


def build_gk_global_input_table(phase_table: pd.DataFrame, stale_updated: pd.DataFrame) -> pd.DataFrame:
    if phase_table is None or phase_table.empty:
        return pd.DataFrame(columns=REQUIRED_GK_COLUMNS)
    kt_lookup = _phase_kt_lookup(stale_updated)
    rows: list[dict] = []
    for row in phase_table.itertuples(index=False):
        phase = str(row.phase_name)
        kt_acc, kt_corr = kt_lookup.get(phase, (0.0, 0.0))
        state_count = int(row.state_count)
        reproduced = int(row.reproduced_state_count)
        finite_ok = all(np.isfinite([_safe_float(row.mean_state_r2), _safe_float(row.mean_state_correlation), _safe_float(row.mean_state_event_accuracy)]))
        gk_ok = bool(state_count > 0 and reproduced > 0 and finite_ok)
        rows.append({
            **BOUNDARY,
            "phase_name": phase,
            "phase_order": int(row.phase_order),
            "gt_input_status": "accepted_fixed_static_pca_7_global_summary" if gk_ok else "gt_input_needs_review",
            "kt_input_status": "accepted_global_history_delta_summary" if phase in kt_lookup or int(row.phase_order) == 0 else "kt_input_needs_review",
            "state_count": state_count,
            "reproduced_state_count": reproduced,
            "mean_state_r2": _safe_float(row.mean_state_r2),
            "mean_state_correlation": _safe_float(row.mean_state_correlation),
            "mean_state_event_accuracy": _safe_float(row.mean_state_event_accuracy),
            "weak_state_names": str(row.weak_state_names),
            "kt_updated_minus_stale_event_accuracy": kt_acc,
            "kt_updated_minus_stale_correlation": kt_corr,
            "gk_global_acceptance_status": "gk_global_summary_accepted_for_upper_layer" if gk_ok else "gk_global_summary_needs_review",
        })
    return pd.DataFrame(rows, columns=REQUIRED_GK_COLUMNS)


def _mt_component_values(row) -> dict[str, tuple[float, str]]:
    state_count = max(1, int(row.state_count))
    reproduced = max(0, int(row.reproduced_state_count))
    event_acc = _clip01(_safe_float(row.mean_state_event_accuracy))
    corr = _clip01((_safe_float(row.mean_state_correlation) + 1.0) / 2.0)
    r2 = _clip01((_safe_float(row.mean_state_r2) + 1.0) / 2.0)
    weak_names = str(row.weak_state_names)
    weak_count = 0 if not weak_names else len([p for p in weak_names.split(";") if p])
    weak_ratio = _clip01(weak_count / state_count)
    kt_acc_delta = _safe_float(row.kt_updated_minus_stale_event_accuracy)
    kt_corr_delta = _safe_float(row.kt_updated_minus_stale_correlation)
    kt_positive = _clip01(0.50 + kt_acc_delta + 0.50 * kt_corr_delta)
    has_info_weak = "information" in weak_names or "degradation" in weak_names
    has_resource_weak = "resource" in weak_names
    efficiency = _clip01(reproduced / state_count)
    return {
        "stability": (event_acc, "mean_state_event_accuracy"),
        "adaptability": (kt_positive, "kt_updated_minus_stale_event_accuracy;kt_updated_minus_stale_correlation"),
        "exploration": (_clip01(1.0 - 0.50 * weak_ratio), "weak_state_names"),
        "efficiency": (efficiency, "reproduced_state_count;state_count"),
        "robustness": (_clip01(0.60 * event_acc + 0.40 * efficiency), "mean_state_event_accuracy;reproduced_state_count"),
        "structural_diversity": (_clip01(0.65 + 0.25 * (1.0 - weak_ratio)), "weak_state_names;state_count"),
        "trajectory_dynamics": (_clip01(0.50 + 0.25 * abs(kt_acc_delta) + 0.25 * abs(kt_corr_delta)), "kt_updated_minus_stale_event_accuracy;kt_updated_minus_stale_correlation"),
        "predictability": (_clip01(0.60 * corr + 0.40 * event_acc), "mean_state_correlation;mean_state_event_accuracy"),
        "coherence": (_clip01(1.0 - weak_ratio), "weak_state_names;state_count"),
        "recoverability": (kt_positive, "kt_updated_minus_stale_event_accuracy;kt_updated_minus_stale_correlation"),
        "novelty_quality": (_clip01(0.50 + 0.25 * kt_acc_delta + 0.25 * efficiency), "kt_updated_minus_stale_event_accuracy;reproduced_state_count"),
        "relation_lock_risk_control": (_clip01(0.55 + 0.35 * efficiency - 0.15 * weak_ratio), "reproduced_state_count;weak_state_names"),
        "information_integrity": (_clip01(0.85 - (0.35 if has_info_weak else 0.0) + 0.10 * event_acc), "weak_state_names;mean_state_event_accuracy"),
        "reversibility": (_clip01(0.60 + 0.30 * kt_positive - 0.20 * weak_ratio), "kt_global_delta_summary;weak_state_names"),
        "resource_balance": (_clip01(0.85 - (0.35 if has_resource_weak else 0.0) + 0.10 * r2), "weak_state_names;mean_state_r2"),
    }


def build_mt_compatibility_projection_table(gk_input: pd.DataFrame) -> pd.DataFrame:
    if gk_input is None or gk_input.empty:
        return pd.DataFrame(columns=REQUIRED_MT_COLUMNS)
    rows: list[dict] = []
    for row in gk_input.itertuples(index=False):
        values = _mt_component_values(row)
        for component in MT_COMPONENTS_15:
            value, sources = values[component]
            finite = bool(np.isfinite(value))
            bounded = bool(0.0 <= value <= 1.0)
            rows.append({
                **BOUNDARY,
                "phase_name": str(row.phase_name),
                "phase_order": int(row.phase_order),
                "mt_component_name": component,
                "mt_component_value": float(value),
                "mt_source_fields": sources,
                "mt_value_finite": finite,
                "mt_value_bounded_0_1": bounded,
                "mt_component_status": "mt_component_projected_valid" if finite and bounded else "mt_component_needs_review",
            })
    return pd.DataFrame(rows, columns=REQUIRED_MT_COLUMNS)


def _pressure_family_for_component(component: str) -> tuple[str, str]:
    mapping = {
        "stability": ("stabilize_drift", "increase"),
        "adaptability": ("increase_adaptation_buffer", "increase"),
        "exploration": ("protect_exploration_margin", "increase"),
        "efficiency": ("reduce_wasteful_overhead", "increase"),
        "robustness": ("increase_robustness_buffer", "increase"),
        "structural_diversity": ("protect_structural_diversity", "increase"),
        "trajectory_dynamics": ("monitor_trajectory_dynamics", "increase"),
        "predictability": ("increase_predictability_margin", "increase"),
        "coherence": ("increase_coherence_margin", "increase"),
        "recoverability": ("increase_recovery_buffer", "increase"),
        "novelty_quality": ("protect_novelty_quality", "increase"),
        "relation_lock_risk_control": ("reduce_relation_lock_risk", "increase"),
        "information_integrity": ("reduce_information_degradation_risk", "increase"),
        "reversibility": ("increase_reversibility_margin", "increase"),
        "resource_balance": ("reduce_resource_pressure_risk", "increase"),
    }
    return mapping.get(component, ("upper_pressure_watch", "increase"))


def build_upper_pressure_candidate_table(mt_table: pd.DataFrame, cfg: NewGtUpperLayerRevalidationConfig | None = None) -> pd.DataFrame:
    cfg = cfg or NewGtUpperLayerRevalidationConfig()
    if mt_table is None or mt_table.empty:
        return pd.DataFrame(columns=REQUIRED_PRESSURE_COLUMNS)
    rows: list[dict] = []
    for phase, group in mt_table.groupby("phase_name", sort=False):
        ordered = group.copy()
        ordered["priority_gap"] = cfg.mt_low_component_threshold - pd.to_numeric(ordered["mt_component_value"], errors="coerce")
        candidates = ordered.sort_values("priority_gap", ascending=False).head(3)
        for i, row in enumerate(candidates.itertuples(index=False)):
            component = str(row.mt_component_name)
            value = _safe_float(row.mt_component_value)
            gap = max(0.0, cfg.mt_low_component_threshold - value)
            raw = float(gap * 0.40)
            bounded = min(cfg.weak_pressure_max, raw)
            family, polarity = _pressure_family_for_component(component)
            if bounded <= cfg.no_op_magnitude_threshold:
                status = "upper_pressure_no_op_candidate_due_to_low_gap"
                family = "NO_OP"
                polarity = "none"
                bounded = 0.0
            else:
                status = "bounded_reversible_upper_pressure_candidate"
            rows.append({
                **BOUNDARY,
                "phase_name": str(phase),
                "phase_order": int(row.phase_order),
                "pressure_candidate_id": f"upper_pressure_{phase}_{i:02d}",
                "pressure_family": family,
                "source_mt_component": component,
                "source_mt_value": value,
                "pressure_polarity": polarity,
                "raw_pressure_magnitude": raw,
                "bounded_pressure_magnitude": bounded,
                "pressure_time_scale": "slow_short_horizon_reversible",
                "reversible": True,
                "no_op_allowed": True,
                "rollback_policy": "rollback_if_m_t_component_worsens_or_audit_flags_strengthen",
                "safety_projection_status": "safety_projected_within_weak_bound" if bounded <= cfg.weak_pressure_max else "safety_projection_failed",
                "upper_pressure_candidate_status": status,
            })
    return pd.DataFrame(rows, columns=REQUIRED_PRESSURE_COLUMNS)


def build_upper_pressure_safety_check_table(pressure_table: pd.DataFrame, cfg: NewGtUpperLayerRevalidationConfig | None = None) -> pd.DataFrame:
    cfg = cfg or NewGtUpperLayerRevalidationConfig()
    rows: list[dict] = []
    if pressure_table is None or pressure_table.empty:
        return pd.DataFrame(columns=REQUIRED_SAFETY_COLUMNS)
    for phase, group in pressure_table.groupby("phase_name", sort=False):
        checks = [
            ("bounded_magnitude", "All pressure magnitudes are within weak bound.", True, bool((group["bounded_pressure_magnitude"].astype(float) <= cfg.weak_pressure_max).all())),
            ("reversible", "All pressure candidates are reversible.", True, bool(group["reversible"].astype(bool).all())),
            ("no_op_allowed", "NO_OP remains available for every candidate.", True, bool(group["no_op_allowed"].astype(bool).all())),
            ("rollback_policy_present", "Rollback policy is present for every candidate.", True, bool(group["rollback_policy"].astype(str).str.len().gt(0).all())),
            ("safety_projected", "Safety projection status is passed for every candidate.", True, bool(group["safety_projection_status"].astype(str).str.contains("within_weak_bound").all())),
        ]
        for check_id, desc, expected, observed in checks:
            rows.append({
                **BOUNDARY,
                "safety_check_id": f"{phase}_{check_id}",
                "phase_name": str(phase),
                "check_description": desc,
                "expected_value": bool(expected),
                "observed_value": bool(observed),
                "safety_check_status": "pass" if bool(expected) == bool(observed) else "fail",
            })
    return pd.DataFrame(rows, columns=REQUIRED_SAFETY_COLUMNS)


def build_final_summary(gk_input: pd.DataFrame, mt_table: pd.DataFrame, pressure_table: pd.DataFrame, safety_table: pd.DataFrame) -> pd.DataFrame:
    gk_count = int(len(gk_input)) if gk_input is not None else 0
    mt_count = int(len(mt_table)) if mt_table is not None else 0
    mt_phase_count = int(mt_table["phase_name"].nunique()) if mt_count else 0
    mt_per_phase = int(mt_count / mt_phase_count) if mt_phase_count else 0
    finite_count = int(mt_table["mt_value_finite"].astype(bool).sum()) if mt_count else 0
    bounded_count = int(mt_table["mt_value_bounded_0_1"].astype(bool).sum()) if mt_count else 0
    pressure_count = int(len(pressure_table)) if pressure_table is not None else 0
    safety_count = int(len(safety_table)) if safety_table is not None else 0
    safety_pass = int((safety_table["safety_check_status"].astype(str) == "pass").sum()) if safety_count else 0
    max_mag = float(pd.to_numeric(pressure_table["bounded_pressure_magnitude"], errors="coerce").max()) if pressure_count else 0.0
    no_op_count = int((pressure_table["pressure_family"].astype(str) == "NO_OP").sum()) if pressure_count else 0
    gk_ok = bool(gk_count > 0 and (gk_input["gk_global_acceptance_status"].astype(str) == "gk_global_summary_accepted_for_upper_layer").all()) if gk_count else False
    if gk_ok and mt_phase_count == gk_count and mt_per_phase == 15 and finite_count == mt_count and bounded_count == mt_count and pressure_count > 0 and safety_count == safety_pass:
        decision = "new_static_pca_7_gt_upper_layer_revalidated_from_gt_kt_to_mt15_to_bounded_upper_pressure"
    else:
        decision = "new_static_pca_7_gt_upper_layer_revalidation_needs_review"
    return pd.DataFrame([{
        **BOUNDARY,
        "gk_input_phase_count": gk_count,
        "mt_component_total_count": mt_count,
        "mt_phase_count": mt_phase_count,
        "mt_component_count_per_phase": mt_per_phase,
        "mt_finite_count": finite_count,
        "mt_bounded_count": bounded_count,
        "upper_pressure_candidate_count": pressure_count,
        "safety_check_count": safety_count,
        "safety_check_pass_count": safety_pass,
        "max_bounded_pressure_magnitude": max_mag,
        "no_op_candidate_count": no_op_count,
        "new_gt_upper_layer_revalidation_decision": decision,
        "next_task": "Task 2-8j-13: action-axis material contract after upper-layer revalidation",
    }], columns=REQUIRED_SUMMARY_COLUMNS)


def validate_new_gt_upper_layer_revalidation_tables(gk_input: pd.DataFrame, mt_table: pd.DataFrame, pressure_table: pd.DataFrame, safety_table: pd.DataFrame, final_summary: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    tables = {
        "gk_input": (gk_input, REQUIRED_GK_COLUMNS),
        "mt_table": (mt_table, REQUIRED_MT_COLUMNS),
        "pressure_table": (pressure_table, REQUIRED_PRESSURE_COLUMNS),
        "safety_table": (safety_table, REQUIRED_SAFETY_COLUMNS),
        "final_summary": (final_summary, REQUIRED_SUMMARY_COLUMNS),
    }
    for name, (table, required) in tables.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_12_empty_table:{name}")
            continue
        missing = [c for c in required if c not in table.columns]
        if missing:
            errors.append(f"task2_8j_12_missing_columns:{name}:" + ",".join(missing))
            continue
        for col in ["validation_only", "upper_layer_revalidation_only", "kt_global_summary_used", "upper_pressure_route_checked", "bounded_upper_pressure_required", "weak_pressure_required", "reversible_pressure_required", "no_op_allowed_required", "rollback_required"]:
            if not bool(table[col].astype(bool).all()):
                errors.append(f"task2_8j_12_required_true_not_all_true:{name}:{col}")
        if set(table["gt_main_map_name"].astype(str)) != {"static_pca_7"}:
            errors.append(f"task2_8j_12_wrong_gt_main_map_name:{name}")
        if set(table["gt_main_component_count"].astype(int)) != {7}:
            errors.append(f"task2_8j_12_wrong_gt_component_count:{name}")
        if set(table["mt_compatibility_component_count"].astype(int)) != {15}:
            errors.append(f"task2_8j_12_wrong_mt_component_count:{name}")
        for col in FORBIDDEN_TRUE:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_12_forbidden_true:{name}:{col}")
    if mt_table is not None and not mt_table.empty:
        if set(mt_table["mt_component_name"].astype(str)) != set(MT_COMPONENTS_15):
            errors.append("task2_8j_12_mt_component_set_mismatch")
        if not bool(mt_table["mt_value_finite"].astype(bool).all()):
            errors.append("task2_8j_12_mt_nonfinite_value")
        if not bool(mt_table["mt_value_bounded_0_1"].astype(bool).all()):
            errors.append("task2_8j_12_mt_out_of_bounds")
    if pressure_table is not None and not pressure_table.empty:
        if not bool(pressure_table["reversible"].astype(bool).all()):
            errors.append("task2_8j_12_pressure_not_all_reversible")
        if not bool(pressure_table["no_op_allowed"].astype(bool).all()):
            errors.append("task2_8j_12_no_op_not_allowed")
        if bool((pressure_table["bounded_pressure_magnitude"].astype(float) > 0.20).any()):
            errors.append("task2_8j_12_pressure_exceeds_weak_bound")
    if safety_table is not None and not safety_table.empty:
        if not bool((safety_table["safety_check_status"].astype(str) == "pass").all()):
            errors.append("task2_8j_12_safety_check_failed")
    return errors


def build_and_validate_new_gt_upper_layer_revalidation(
    tracking_cfg: V2StructureChangeTrackingConfig | None = None,
    cfg: NewGtUpperLayerRevalidationConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    cfg = cfg or NewGtUpperLayerRevalidationConfig()
    phase_table, _edge_change, stale_updated, _tracking_summary, tracking_errors, tracking_summary = build_and_validate_v2_structure_change_relation_field_tracking(
        tracking_cfg or V2StructureChangeTrackingConfig()
    )
    gk_input = build_gk_global_input_table(phase_table, stale_updated)
    mt_table = build_mt_compatibility_projection_table(gk_input)
    pressure_table = build_upper_pressure_candidate_table(mt_table, cfg)
    safety_table = build_upper_pressure_safety_check_table(pressure_table, cfg)
    final_summary = build_final_summary(gk_input, mt_table, pressure_table, safety_table)
    errors = [f"task2_8j_12_upstream_6c_error:{e}" for e in tracking_errors]
    errors.extend(validate_new_gt_upper_layer_revalidation_tables(gk_input, mt_table, pressure_table, safety_table, final_summary))
    summary = {
        "gt_main_map_name": "static_pca_7",
        "gt_main_component_count": 7,
        "mt_compatibility_component_count": 15,
        "upstream_6c_decision": tracking_summary.get("v2_structure_tracking_decision", ""),
        "gk_input_phase_count": _safe_float(final_summary["gk_input_phase_count"].iloc[0]) if not final_summary.empty else 0,
        "mt_component_total_count": _safe_float(final_summary["mt_component_total_count"].iloc[0]) if not final_summary.empty else 0,
        "mt_phase_count": _safe_float(final_summary["mt_phase_count"].iloc[0]) if not final_summary.empty else 0,
        "mt_component_count_per_phase": _safe_float(final_summary["mt_component_count_per_phase"].iloc[0]) if not final_summary.empty else 0,
        "upper_pressure_candidate_count": _safe_float(final_summary["upper_pressure_candidate_count"].iloc[0]) if not final_summary.empty else 0,
        "safety_check_count": _safe_float(final_summary["safety_check_count"].iloc[0]) if not final_summary.empty else 0,
        "safety_check_pass_count": _safe_float(final_summary["safety_check_pass_count"].iloc[0]) if not final_summary.empty else 0,
        "max_bounded_pressure_magnitude": _safe_float(final_summary["max_bounded_pressure_magnitude"].iloc[0]) if not final_summary.empty else 0.0,
        "new_gt_upper_layer_revalidation_decision": str(final_summary["new_gt_upper_layer_revalidation_decision"].iloc[0]) if not final_summary.empty else "empty",
        "ot_route_input_used": False,
        "game_structure_prediction_envelope_used": False,
        "action_axis_generated": False,
        "real_actionmodule_called": False,
        "validation_errors": errors,
    }
    return gk_input, mt_table, pressure_table, safety_table, final_summary, errors, summary
