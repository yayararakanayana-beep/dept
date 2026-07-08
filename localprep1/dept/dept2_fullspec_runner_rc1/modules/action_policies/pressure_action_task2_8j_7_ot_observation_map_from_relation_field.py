"""Task 2-8j-7: O_t observation map from the fixed-7-axis relation field RC1.

Purpose:
    Convert the verified fixed-7-axis G_t relation field into O_t-style
    observation-map units: where, direction, intensity, confidence, evidence,
    lifecycle, and audit / residual flags.

Position:
    Task 2-8j-6 built the relation field.
    Task 2-8j-6b verified that it reproduces observable v2 states.
    Task 2-8j-6c verified that it tracks v2 structure changes.
    This task does not create upper pressure and does not call the action module;
    it only creates the observation-map route that can later be provided to the
    action module beside, not through, the upper-pressure route.

Boundary:
    - observation-map validation only
    - fixed static_pca_7 main map
    - O_t reads relation-field / v2-state evidence only
    - H-DEPT / upper-pressure route is not connected here
    - no action conversion, ActionFrame creation, ActionModule call, runtime call, or writeback
    - no hidden-truth / future-information input
    - no effective-dimension re-fitting or axis mutation
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .pressure_action_task2_8j_6c_v2_structure_change_relation_field_tracking import (
    V2StructureChangeTrackingConfig,
    build_and_validate_v2_structure_change_relation_field_tracking,
)

TASK2_8J_7_VERSION = "ot_observation_map_from_relation_field_rc1"
TASK2_8J_7_CONTRACT = (
    "Task2_8j_7_Ot_observation_map_from_relation_field__"
    "fixed_static_pca_7__observation_map_route_only__"
    "upper_pressure_route_separate__no_actionmodule_no_writeback"
)

BOUNDARY = {
    "task2_8j_7_version": TASK2_8J_7_VERSION,
    "task2_8j_7_contract": TASK2_8J_7_CONTRACT,
    "validation_only": True,
    "observation_map_only": True,
    "gt_main_map_name": "static_pca_7",
    "gt_main_component_count": 7,
    "relation_field_source": "Task2_8j_6c_tracked_relation_field",
    "ot_route_connected": True,
    "upper_pressure_route_connected": False,
    "hdept_pressure_generated": False,
    "runtime_policy_input": False,
    "fullspec_runtime_connected": False,
    "action_frame_created": False,
    "actionmodule_called": False,
    "action_input_converted": False,
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
    "upper_pressure_route_connected",
    "hdept_pressure_generated",
    "runtime_policy_input",
    "fullspec_runtime_connected",
    "action_frame_created",
    "actionmodule_called",
    "action_input_converted",
    "canonical_write_performed",
    "gk_writeback_performed",
    "ot_writeback_performed",
    "effective_dimension_refit_performed",
    "axis_mutation_performed",
    "residual_auxiliary_injected_into_gt_main",
    "hidden_truth_input",
    "future_information_used",
]

REQUIRED_OBSERVATION_COLUMNS = list(BOUNDARY) + [
    "observation_id",
    "observation_kind",
    "map_layer",
    "where_signal",
    "direction_from",
    "direction_to",
    "direction_polarity",
    "intensity",
    "confidence",
    "evidence_source",
    "evidence_summary",
    "lifecycle",
    "residual_flag",
    "audit_target",
    "observation_status",
]

REQUIRED_ROUTE_COLUMNS = list(BOUNDARY) + [
    "route_name",
    "route_role",
    "route_output",
    "can_feed_action_module_later",
    "must_not_be_mixed_with_upper_pressure_inside_ot",
    "route_status",
]

REQUIRED_SUMMARY_COLUMNS = list(BOUNDARY) + [
    "observation_unit_count",
    "relation_change_observation_count",
    "state_reproduction_observation_count",
    "tracking_recovery_observation_count",
    "audit_target_count",
    "high_confidence_count",
    "active_or_emerging_count",
    "route_count",
    "ot_observation_map_decision",
    "next_task",
]


@dataclass(frozen=True)
class OtObservationMapConfig:
    high_confidence_threshold: float = 0.75
    relation_change_intensity_scale: float = 1.0
    audit_confidence_penalty: float = 0.20


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


def _mean(series: pd.Series, default: float = 0.0) -> float:
    arr = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if arr.empty:
        return float(default)
    return float(arr.mean())


def _polarity(delta: float, same_sign_changed: bool, lag_sign_changed: bool) -> str:
    if same_sign_changed or lag_sign_changed:
        return "sign_changed"
    if delta > 0.0:
        return "strengthening"
    if delta < 0.0:
        return "weakening"
    return "stable"


def _lifecycle(kind: str, intensity: float, polarity: str) -> str:
    if kind == "tracking_recovery":
        return "recovering"
    if kind == "state_reproduction" and intensity < 0.55:
        return "unresolved"
    if polarity == "sign_changed":
        return "emerging"
    if abs(intensity) >= 0.70:
        return "active"
    if polarity == "weakening":
        return "weakening"
    return "watch"


def _status(confidence: float, audit: bool) -> str:
    if audit:
        return "observation_with_audit_target"
    if confidence >= 0.75:
        return "observation_ready_for_downstream_reference"
    if confidence >= 0.45:
        return "watch_observation"
    return "low_confidence_observation"


def _relation_change_units(edge_change: pd.DataFrame, cfg: OtObservationMapConfig) -> list[dict]:
    rows: list[dict] = []
    if edge_change is None or edge_change.empty:
        return rows
    changed = edge_change[edge_change["structure_change_detected"].astype(bool)].copy()
    if changed.empty:
        changed = edge_change.copy()
    for i, row in enumerate(changed.itertuples(index=False)):
        delta = _safe_float(row.relation_strength_delta)
        same_changed = bool(row.same_time_sign_changed)
        lag_changed = bool(row.lagged_sign_changed)
        intensity = _clip01(abs(delta) * cfg.relation_change_intensity_scale + (0.20 if same_changed or lag_changed else 0.0))
        confidence = _clip01(0.55 + 0.35 * intensity)
        source = str(row.source_macro_signal)
        target = str(row.target_macro_signal)
        audit = "resource_pressure" in {source, target}
        if audit:
            confidence = _clip01(confidence - cfg.audit_confidence_penalty)
        polarity = _polarity(delta, same_changed, lag_changed)
        rows.append({
            **BOUNDARY,
            "observation_id": f"ot7_relation_change_{i:04d}",
            "observation_kind": "relation_change",
            "map_layer": "relation_field_change",
            "where_signal": f"{source}->{target}",
            "direction_from": source,
            "direction_to": target,
            "direction_polarity": polarity,
            "intensity": intensity,
            "confidence": confidence,
            "evidence_source": "Task2_8j_6c_phase_relation_field_edge_change",
            "evidence_summary": f"{row.source_phase}->{row.target_phase}; delta={delta:.6f}",
            "lifecycle": _lifecycle("relation_change", intensity, polarity),
            "residual_flag": False,
            "audit_target": bool(audit),
            "observation_status": _status(confidence, bool(audit)),
        })
    return rows


def _state_reproduction_units(phase_table: pd.DataFrame, cfg: OtObservationMapConfig) -> list[dict]:
    rows: list[dict] = []
    if phase_table is None or phase_table.empty:
        return rows
    for i, row in enumerate(phase_table.itertuples(index=False)):
        acc = _safe_float(row.mean_state_event_accuracy)
        corr = _safe_float(row.mean_state_correlation)
        weak = str(row.weak_state_names or "")
        audit = bool(weak)
        confidence = _clip01((acc + max(corr, 0.0)) / 2.0)
        if audit:
            confidence = _clip01(confidence - cfg.audit_confidence_penalty)
        direction_to = weak if weak else "phase_state_reproduction"
        rows.append({
            **BOUNDARY,
            "observation_id": f"ot7_state_reproduction_{i:04d}",
            "observation_kind": "state_reproduction",
            "map_layer": "phase_state_map",
            "where_signal": str(row.phase_name),
            "direction_from": str(row.phase_name),
            "direction_to": direction_to,
            "direction_polarity": "reproduced" if not audit else "watch_weak_state",
            "intensity": _clip01(acc),
            "confidence": confidence,
            "evidence_source": "Task2_8j_6c_phase_state_reproduction",
            "evidence_summary": f"states={int(row.reproduced_state_count)}/{int(row.state_count)}; weak={weak}",
            "lifecycle": _lifecycle("state_reproduction", acc, "stable" if not audit else "weakening"),
            "residual_flag": bool(audit),
            "audit_target": bool(audit),
            "observation_status": _status(confidence, bool(audit)),
        })
    return rows


def _tracking_recovery_units(stale_updated: pd.DataFrame, _cfg: OtObservationMapConfig) -> list[dict]:
    rows: list[dict] = []
    if stale_updated is None or stale_updated.empty:
        return rows
    for i, row in enumerate(stale_updated.itertuples(index=False)):
        delta = _safe_float(row.updated_minus_stale_event_accuracy)
        updated_acc = _safe_float(row.updated_mean_state_event_accuracy)
        confidence = _clip01(0.50 + 0.50 * updated_acc)
        rows.append({
            **BOUNDARY,
            "observation_id": f"ot7_tracking_recovery_{i:04d}",
            "observation_kind": "tracking_recovery",
            "map_layer": "stale_vs_updated_relation_field",
            "where_signal": str(row.target_state_phase),
            "direction_from": str(row.source_relation_phase),
            "direction_to": str(row.updated_relation_phase),
            "direction_polarity": "updated_preserves_or_recovers" if delta >= -0.02 else "updated_not_recovering",
            "intensity": _clip01(updated_acc),
            "confidence": confidence,
            "evidence_source": "Task2_8j_6c_stale_vs_updated_relation_field",
            "evidence_summary": f"updated_minus_stale_event_accuracy={delta:.6f}",
            "lifecycle": _lifecycle("tracking_recovery", updated_acc, "stable"),
            "residual_flag": False,
            "audit_target": False,
            "observation_status": _status(confidence, False),
        })
    return rows


def build_ot_observation_units(
    phase_table: pd.DataFrame,
    edge_change: pd.DataFrame,
    stale_updated: pd.DataFrame,
    cfg: OtObservationMapConfig | None = None,
) -> pd.DataFrame:
    cfg = cfg or OtObservationMapConfig()
    rows: list[dict] = []
    rows.extend(_relation_change_units(edge_change, cfg))
    rows.extend(_state_reproduction_units(phase_table, cfg))
    rows.extend(_tracking_recovery_units(stale_updated, cfg))
    return pd.DataFrame(rows, columns=REQUIRED_OBSERVATION_COLUMNS)


def build_route_table() -> pd.DataFrame:
    rows = [
        {
            **BOUNDARY,
            "route_name": "ot_observation_map_route",
            "route_role": "where_direction_intensity_confidence_evidence_for_downstream_reference",
            "route_output": "O_t_observation_units",
            "can_feed_action_module_later": True,
            "must_not_be_mixed_with_upper_pressure_inside_ot": True,
            "route_status": "separate_from_upper_pressure_route",
        },
        {
            **BOUNDARY,
            "route_name": "upper_pressure_route",
            "route_role": "separate_H_DEPT_pressure_direction_not_created_in_Task2_8j_7",
            "route_output": "not_created_here",
            "can_feed_action_module_later": True,
            "must_not_be_mixed_with_upper_pressure_inside_ot": True,
            "route_status": "explicitly_not_connected_in_this_task",
        },
    ]
    return pd.DataFrame(rows, columns=REQUIRED_ROUTE_COLUMNS)


def build_final_summary(observation_units: pd.DataFrame, route_table: pd.DataFrame) -> pd.DataFrame:
    count = int(len(observation_units)) if observation_units is not None else 0
    relation_count = int((observation_units["observation_kind"].astype(str) == "relation_change").sum()) if count else 0
    state_count = int((observation_units["observation_kind"].astype(str) == "state_reproduction").sum()) if count else 0
    recovery_count = int((observation_units["observation_kind"].astype(str) == "tracking_recovery").sum()) if count else 0
    audit_count = int(observation_units["audit_target"].astype(bool).sum()) if count else 0
    high_count = int((observation_units["confidence"].astype(float) >= 0.75).sum()) if count else 0
    active_count = int(observation_units["lifecycle"].astype(str).isin(["active", "emerging", "recovering"]).sum()) if count else 0
    route_count = int(len(route_table)) if route_table is not None else 0
    if count > 0 and relation_count > 0 and route_count >= 2:
        decision = "ot_observation_map_created_from_relation_field_with_upper_pressure_route_separate"
    else:
        decision = "ot_observation_map_not_confirmed"
    return pd.DataFrame([{
        **BOUNDARY,
        "observation_unit_count": count,
        "relation_change_observation_count": relation_count,
        "state_reproduction_observation_count": state_count,
        "tracking_recovery_observation_count": recovery_count,
        "audit_target_count": audit_count,
        "high_confidence_count": high_count,
        "active_or_emerging_count": active_count,
        "route_count": route_count,
        "ot_observation_map_decision": decision,
        "next_task": "Task 2-8j-8: action-module input split contract for upper-pressure route and O_t observation-map route",
    }], columns=REQUIRED_SUMMARY_COLUMNS)


def validate_ot_observation_map_tables(observation_units: pd.DataFrame, route_table: pd.DataFrame, final_summary: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    tables = {
        "observation_units": (observation_units, REQUIRED_OBSERVATION_COLUMNS),
        "route_table": (route_table, REQUIRED_ROUTE_COLUMNS),
        "final_summary": (final_summary, REQUIRED_SUMMARY_COLUMNS),
    }
    for name, (table, required) in tables.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_7_empty_table:{name}")
            continue
        missing = [c for c in required if c not in table.columns]
        if missing:
            errors.append(f"task2_8j_7_missing_columns:{name}:" + ",".join(missing))
            continue
        for col in ["validation_only", "observation_map_only", "ot_route_connected"]:
            if not bool(table[col].astype(bool).all()):
                errors.append(f"task2_8j_7_required_true_not_all_true:{name}:{col}")
        if set(table["gt_main_map_name"].astype(str)) != {"static_pca_7"}:
            errors.append(f"task2_8j_7_wrong_gt_main_map_name:{name}")
        if set(table["gt_main_component_count"].astype(int)) != {7}:
            errors.append(f"task2_8j_7_wrong_component_count:{name}")
        for col in FORBIDDEN_TRUE:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_7_forbidden_true:{name}:{col}")
    if observation_units is not None and not observation_units.empty:
        if not bool(observation_units["confidence"].astype(float).between(0.0, 1.0).all()):
            errors.append("task2_8j_7_confidence_out_of_range")
        if not bool(observation_units["intensity"].astype(float).between(0.0, 1.0).all()):
            errors.append("task2_8j_7_intensity_out_of_range")
        if not {"relation_change", "state_reproduction", "tracking_recovery"}.issubset(set(observation_units["observation_kind"].astype(str))):
            errors.append("task2_8j_7_missing_observation_kind")
    return errors


def build_and_validate_ot_observation_map_from_relation_field(
    tracking_cfg: V2StructureChangeTrackingConfig | None = None,
    cfg: OtObservationMapConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    cfg = cfg or OtObservationMapConfig()
    phase_table, edge_change, stale_updated, _tracking_summary, tracking_errors, _tracking_json = build_and_validate_v2_structure_change_relation_field_tracking(
        tracking_cfg or V2StructureChangeTrackingConfig()
    )
    observation_units = build_ot_observation_units(phase_table, edge_change, stale_updated, cfg)
    route_table = build_route_table()
    final_summary = build_final_summary(observation_units, route_table)
    errors = [f"task2_8j_7_upstream_6c_error:{e}" for e in tracking_errors]
    errors.extend(validate_ot_observation_map_tables(observation_units, route_table, final_summary))
    summary = {
        "gt_main_map_name": "static_pca_7",
        "gt_main_component_count": 7,
        "observation_unit_count": int(final_summary["observation_unit_count"].iloc[0]) if not final_summary.empty else 0,
        "relation_change_observation_count": int(final_summary["relation_change_observation_count"].iloc[0]) if not final_summary.empty else 0,
        "state_reproduction_observation_count": int(final_summary["state_reproduction_observation_count"].iloc[0]) if not final_summary.empty else 0,
        "tracking_recovery_observation_count": int(final_summary["tracking_recovery_observation_count"].iloc[0]) if not final_summary.empty else 0,
        "audit_target_count": int(final_summary["audit_target_count"].iloc[0]) if not final_summary.empty else 0,
        "high_confidence_count": int(final_summary["high_confidence_count"].iloc[0]) if not final_summary.empty else 0,
        "active_or_emerging_count": int(final_summary["active_or_emerging_count"].iloc[0]) if not final_summary.empty else 0,
        "route_count": int(final_summary["route_count"].iloc[0]) if not final_summary.empty else 0,
        "ot_observation_map_decision": str(final_summary["ot_observation_map_decision"].iloc[0]) if not final_summary.empty else "empty",
        "upper_pressure_route_connected": False,
        "hdept_pressure_generated": False,
        "actionmodule_called": False,
        "validation_errors": errors,
    }
    return observation_units, route_table, final_summary, errors, summary
