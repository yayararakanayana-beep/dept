"""Task 2-8j-7c: relation-field -> O_t information-preservation audit RC1.

Purpose:
    Audit whether the relation-field information used to build O_t observation
    units is preserved as traceable evidence after necessary coarse-graining.

Position:
    Task 2-8j-7 converts relation-field evidence into O_t observation-map units.
    Task 2-8j-7b splits audit targets by reason and strength.  This task checks
    the interface between the relation field and O_t: which information is
    preserved, which information is intentionally compressed, and whether each
    O_t unit can be traced back to its source table.

Boundary:
    - information-preservation audit only
    - fixed static_pca_7 main map
    - O_t may coarse-grain relation-field details, but must keep source evidence
    - upper-pressure route remains separate and unconnected
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
from .pressure_action_task2_8j_7_ot_observation_map_from_relation_field import (
    OtObservationMapConfig,
    build_ot_observation_units,
    build_route_table,
    validate_ot_observation_map_tables,
    build_final_summary as build_ot_final_summary,
)
from .pressure_action_task2_8j_7b_ot_audit_layering import (
    OtAuditLayeringConfig,
    build_audit_layer_table,
    build_reason_summary,
    validate_ot_audit_layering_tables,
    build_final_summary as build_audit_final_summary,
)

TASK2_8J_7C_VERSION = "relation_to_ot_information_preservation_audit_rc1"
TASK2_8J_7C_CONTRACT = (
    "Task2_8j_7c_relation_field_to_Ot_information_preservation__"
    "traceability_and_coarse_graining_audit__"
    "upper_pressure_route_separate__no_actionmodule_no_writeback"
)

BOUNDARY = {
    "task2_8j_7c_version": TASK2_8J_7C_VERSION,
    "task2_8j_7c_contract": TASK2_8J_7C_CONTRACT,
    "validation_only": True,
    "information_preservation_audit_only": True,
    "gt_main_map_name": "static_pca_7",
    "gt_main_component_count": 7,
    "source_relation_field": "Task2_8j_6c_phase_relation_field_edge_change",
    "target_observation_map": "Task2_8j_7_ot_observation_units",
    "coarse_graining_allowed": True,
    "source_evidence_required": True,
    "upper_pressure_route_connected": False,
    "hdept_pressure_generated": False,
    "action_input_converted": False,
    "action_frame_created": False,
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
    "upper_pressure_route_connected",
    "hdept_pressure_generated",
    "action_input_converted",
    "action_frame_created",
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

REQUIRED_RELATION_TRACE_COLUMNS = list(BOUNDARY) + [
    "source_phase",
    "target_phase",
    "source_macro_signal",
    "target_macro_signal",
    "source_relation_strength",
    "target_relation_strength",
    "relation_strength_delta",
    "structure_change_detected",
    "matched_ot_observation_id",
    "ot_where_signal",
    "ot_direction_polarity",
    "expected_direction_polarity",
    "ot_intensity",
    "expected_intensity",
    "intensity_abs_error",
    "evidence_source_present",
    "evidence_delta_present",
    "relation_information_preservation_status",
]

REQUIRED_COVERAGE_COLUMNS = list(BOUNDARY) + [
    "coverage_area",
    "source_count",
    "target_count",
    "covered_count",
    "coverage_rate",
    "compressed_out_count",
    "compression_status",
]

REQUIRED_AUDIT_TRACE_COLUMNS = list(BOUNDARY) + [
    "observation_id",
    "observation_kind",
    "audit_layer_found",
    "audit_reason_count",
    "audit_reasons",
    "audit_level",
    "audit_trace_status",
]

REQUIRED_SUMMARY_COLUMNS = list(BOUNDARY) + [
    "source_relation_edge_count",
    "source_changed_relation_count",
    "ot_observation_unit_count",
    "ot_relation_change_observation_count",
    "covered_changed_relation_count",
    "changed_relation_coverage_rate",
    "state_phase_coverage_rate",
    "tracking_recovery_coverage_rate",
    "audit_trace_coverage_rate",
    "compressed_out_relation_edge_count",
    "relation_trace_mismatch_count",
    "information_preservation_decision",
    "next_task",
]


@dataclass(frozen=True)
class RelationToOtInformationPreservationConfig:
    intensity_tolerance: float = 1e-9


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


def _expected_polarity(delta: float, same_changed: bool, lag_changed: bool) -> str:
    if same_changed or lag_changed:
        return "sign_changed"
    if delta > 0:
        return "strengthening"
    if delta < 0:
        return "weakening"
    return "stable"


def _parse_phase_pair(evidence_summary: str) -> tuple[str, str]:
    head = str(evidence_summary).split(";", 1)[0]
    if "->" not in head:
        return "", ""
    left, right = head.split("->", 1)
    return left.strip(), right.strip()


def _relation_observation_lookup(observation_units: pd.DataFrame) -> dict[tuple[str, str, str, str], pd.Series]:
    lookup: dict[tuple[str, str, str, str], pd.Series] = {}
    rel = observation_units[observation_units["observation_kind"].astype(str) == "relation_change"] if not observation_units.empty else pd.DataFrame()
    for _, row in rel.iterrows():
        source_phase, target_phase = _parse_phase_pair(str(row.get("evidence_summary", "")))
        key = (source_phase, target_phase, str(row.get("direction_from", "")), str(row.get("direction_to", "")))
        lookup[key] = row
    return lookup


def build_relation_trace_audit(
    edge_change: pd.DataFrame,
    observation_units: pd.DataFrame,
    ot_cfg: OtObservationMapConfig | None = None,
    cfg: RelationToOtInformationPreservationConfig | None = None,
) -> pd.DataFrame:
    ot_cfg = ot_cfg or OtObservationMapConfig()
    cfg = cfg or RelationToOtInformationPreservationConfig()
    if edge_change is None or edge_change.empty:
        return pd.DataFrame(columns=REQUIRED_RELATION_TRACE_COLUMNS)
    lookup = _relation_observation_lookup(observation_units)
    rows: list[dict] = []
    changed = edge_change[edge_change["structure_change_detected"].astype(bool)].copy()
    for row in changed.itertuples(index=False):
        key = (str(row.source_phase), str(row.target_phase), str(row.source_macro_signal), str(row.target_macro_signal))
        ot_row = lookup.get(key)
        delta = _safe_float(row.relation_strength_delta)
        same_changed = bool(row.same_time_sign_changed)
        lag_changed = bool(row.lagged_sign_changed)
        expected_intensity = _clip01(abs(delta) * ot_cfg.relation_change_intensity_scale + (0.20 if same_changed or lag_changed else 0.0))
        expected_polarity = _expected_polarity(delta, same_changed, lag_changed)
        if ot_row is None:
            ot_id = ""
            ot_where = ""
            ot_polarity = ""
            ot_intensity = float("nan")
            intensity_err = float("nan")
            evidence_source_present = False
            evidence_delta_present = False
            status = "missing_from_ot_observation_map"
        else:
            ot_id = str(ot_row["observation_id"])
            ot_where = str(ot_row["where_signal"])
            ot_polarity = str(ot_row["direction_polarity"])
            ot_intensity = _safe_float(ot_row["intensity"])
            intensity_err = abs(ot_intensity - expected_intensity)
            evidence_source_present = str(ot_row["evidence_source"]) == "Task2_8j_6c_phase_relation_field_edge_change"
            evidence_delta_present = f"delta={delta:.6f}" in str(ot_row["evidence_summary"])
            if ot_polarity == expected_polarity and intensity_err <= cfg.intensity_tolerance and evidence_source_present and evidence_delta_present:
                status = "preserved_as_traceable_coarse_grained_observation"
            else:
                status = "traceable_but_value_mapping_mismatch"
        rows.append({
            **BOUNDARY,
            "source_phase": str(row.source_phase),
            "target_phase": str(row.target_phase),
            "source_macro_signal": str(row.source_macro_signal),
            "target_macro_signal": str(row.target_macro_signal),
            "source_relation_strength": _safe_float(row.source_relation_strength),
            "target_relation_strength": _safe_float(row.target_relation_strength),
            "relation_strength_delta": delta,
            "structure_change_detected": True,
            "matched_ot_observation_id": ot_id,
            "ot_where_signal": ot_where,
            "ot_direction_polarity": ot_polarity,
            "expected_direction_polarity": expected_polarity,
            "ot_intensity": ot_intensity,
            "expected_intensity": expected_intensity,
            "intensity_abs_error": intensity_err,
            "evidence_source_present": bool(evidence_source_present),
            "evidence_delta_present": bool(evidence_delta_present),
            "relation_information_preservation_status": status,
        })
    return pd.DataFrame(rows, columns=REQUIRED_RELATION_TRACE_COLUMNS)


def build_coverage_audit(
    phase_table: pd.DataFrame,
    edge_change: pd.DataFrame,
    stale_updated: pd.DataFrame,
    observation_units: pd.DataFrame,
    relation_trace: pd.DataFrame,
) -> pd.DataFrame:
    rows: list[dict] = []
    total_edges = int(len(edge_change)) if edge_change is not None else 0
    changed_edges = int(edge_change["structure_change_detected"].astype(bool).sum()) if total_edges else 0
    covered_changed = int((relation_trace["relation_information_preservation_status"].astype(str) == "preserved_as_traceable_coarse_grained_observation").sum()) if relation_trace is not None and not relation_trace.empty else 0
    relation_obs = int((observation_units["observation_kind"].astype(str) == "relation_change").sum()) if observation_units is not None and not observation_units.empty else 0
    rows.append({
        **BOUNDARY,
        "coverage_area": "changed_relation_edges_to_ot_relation_observations",
        "source_count": changed_edges,
        "target_count": relation_obs,
        "covered_count": covered_changed,
        "coverage_rate": covered_changed / changed_edges if changed_edges else 0.0,
        "compressed_out_count": max(0, total_edges - changed_edges),
        "compression_status": "unchanged_relation_edges_compressed_out_by_design_with_source_table_retained",
    })
    phase_count = int(len(phase_table)) if phase_table is not None else 0
    state_obs = int((observation_units["observation_kind"].astype(str) == "state_reproduction").sum()) if observation_units is not None and not observation_units.empty else 0
    rows.append({
        **BOUNDARY,
        "coverage_area": "phase_state_reproduction_to_ot_state_observations",
        "source_count": phase_count,
        "target_count": state_obs,
        "covered_count": min(phase_count, state_obs),
        "coverage_rate": min(phase_count, state_obs) / phase_count if phase_count else 0.0,
        "compressed_out_count": 0,
        "compression_status": "phase_state_summary_preserved_as_ot_observation",
    })
    tracking_count = int(len(stale_updated)) if stale_updated is not None else 0
    tracking_obs = int((observation_units["observation_kind"].astype(str) == "tracking_recovery").sum()) if observation_units is not None and not observation_units.empty else 0
    rows.append({
        **BOUNDARY,
        "coverage_area": "tracking_recovery_to_ot_tracking_observations",
        "source_count": tracking_count,
        "target_count": tracking_obs,
        "covered_count": min(tracking_count, tracking_obs),
        "coverage_rate": min(tracking_count, tracking_obs) / tracking_count if tracking_count else 0.0,
        "compressed_out_count": 0,
        "compression_status": "tracking_recovery_summary_preserved_as_ot_observation",
    })
    return pd.DataFrame(rows, columns=REQUIRED_COVERAGE_COLUMNS)


def build_audit_trace_table(observation_units: pd.DataFrame, audit_layers: pd.DataFrame) -> pd.DataFrame:
    if observation_units is None or observation_units.empty:
        return pd.DataFrame(columns=REQUIRED_AUDIT_TRACE_COLUMNS)
    lookup = {str(row.observation_id): row for row in audit_layers.itertuples(index=False)} if audit_layers is not None and not audit_layers.empty else {}
    rows: list[dict] = []
    for row in observation_units.itertuples(index=False):
        obs_id = str(row.observation_id)
        layer = lookup.get(obs_id)
        found = layer is not None
        rows.append({
            **BOUNDARY,
            "observation_id": obs_id,
            "observation_kind": str(row.observation_kind),
            "audit_layer_found": bool(found),
            "audit_reason_count": int(layer.audit_reason_count) if found else 0,
            "audit_reasons": str(layer.audit_reasons) if found else "",
            "audit_level": str(layer.audit_level) if found else "missing",
            "audit_trace_status": "audit_layer_trace_preserved" if found else "missing_audit_layer_trace",
        })
    return pd.DataFrame(rows, columns=REQUIRED_AUDIT_TRACE_COLUMNS)


def build_final_summary(
    edge_change: pd.DataFrame,
    observation_units: pd.DataFrame,
    relation_trace: pd.DataFrame,
    coverage_audit: pd.DataFrame,
    audit_trace: pd.DataFrame,
) -> pd.DataFrame:
    source_edges = int(len(edge_change)) if edge_change is not None else 0
    changed_edges = int(edge_change["structure_change_detected"].astype(bool).sum()) if source_edges else 0
    ot_count = int(len(observation_units)) if observation_units is not None else 0
    ot_relation = int((observation_units["observation_kind"].astype(str) == "relation_change").sum()) if ot_count else 0
    covered_changed = int((relation_trace["relation_information_preservation_status"].astype(str) == "preserved_as_traceable_coarse_grained_observation").sum()) if relation_trace is not None and not relation_trace.empty else 0
    mismatch = int((relation_trace["relation_information_preservation_status"].astype(str) != "preserved_as_traceable_coarse_grained_observation").sum()) if relation_trace is not None and not relation_trace.empty else changed_edges
    coverage_lookup = {str(row.coverage_area): _safe_float(row.coverage_rate) for row in coverage_audit.itertuples(index=False)} if coverage_audit is not None and not coverage_audit.empty else {}
    audit_coverage = float(audit_trace["audit_layer_found"].astype(bool).mean()) if audit_trace is not None and not audit_trace.empty else 0.0
    compressed_out = max(0, source_edges - changed_edges)
    changed_rate = covered_changed / changed_edges if changed_edges else 0.0
    state_rate = coverage_lookup.get("phase_state_reproduction_to_ot_state_observations", 0.0)
    tracking_rate = coverage_lookup.get("tracking_recovery_to_ot_tracking_observations", 0.0)
    if changed_rate >= 1.0 and state_rate >= 1.0 and tracking_rate >= 1.0 and audit_coverage >= 1.0 and mismatch == 0:
        decision = "relation_to_ot_information_preserved_with_traceable_coarse_graining"
    else:
        decision = "relation_to_ot_information_preservation_needs_review"
    return pd.DataFrame([{
        **BOUNDARY,
        "source_relation_edge_count": source_edges,
        "source_changed_relation_count": changed_edges,
        "ot_observation_unit_count": ot_count,
        "ot_relation_change_observation_count": ot_relation,
        "covered_changed_relation_count": covered_changed,
        "changed_relation_coverage_rate": changed_rate,
        "state_phase_coverage_rate": state_rate,
        "tracking_recovery_coverage_rate": tracking_rate,
        "audit_trace_coverage_rate": audit_coverage,
        "compressed_out_relation_edge_count": compressed_out,
        "relation_trace_mismatch_count": mismatch,
        "information_preservation_decision": decision,
        "next_task": "Task 2-8j-8: action-module input split contract for upper-pressure route and O_t observation-map route",
    }], columns=REQUIRED_SUMMARY_COLUMNS)


def validate_relation_to_ot_information_preservation_tables(
    relation_trace: pd.DataFrame,
    coverage_audit: pd.DataFrame,
    audit_trace: pd.DataFrame,
    final_summary: pd.DataFrame,
) -> list[str]:
    errors: list[str] = []
    tables = {
        "relation_trace": (relation_trace, REQUIRED_RELATION_TRACE_COLUMNS),
        "coverage_audit": (coverage_audit, REQUIRED_COVERAGE_COLUMNS),
        "audit_trace": (audit_trace, REQUIRED_AUDIT_TRACE_COLUMNS),
        "final_summary": (final_summary, REQUIRED_SUMMARY_COLUMNS),
    }
    for name, (table, required) in tables.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_7c_empty_table:{name}")
            continue
        missing = [c for c in required if c not in table.columns]
        if missing:
            errors.append(f"task2_8j_7c_missing_columns:{name}:" + ",".join(missing))
            continue
        for col in ["validation_only", "information_preservation_audit_only", "coarse_graining_allowed", "source_evidence_required"]:
            if not bool(table[col].astype(bool).all()):
                errors.append(f"task2_8j_7c_required_true_not_all_true:{name}:{col}")
        if set(table["gt_main_map_name"].astype(str)) != {"static_pca_7"}:
            errors.append(f"task2_8j_7c_wrong_gt_main_map_name:{name}")
        if set(table["gt_main_component_count"].astype(int)) != {7}:
            errors.append(f"task2_8j_7c_wrong_component_count:{name}")
        for col in FORBIDDEN_TRUE:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_7c_forbidden_true:{name}:{col}")
    if relation_trace is not None and not relation_trace.empty:
        bad = relation_trace["relation_information_preservation_status"].astype(str) != "preserved_as_traceable_coarse_grained_observation"
        if bool(bad.any()):
            errors.append("task2_8j_7c_relation_trace_not_fully_preserved")
    if final_summary is not None and not final_summary.empty:
        if _safe_float(final_summary["changed_relation_coverage_rate"].iloc[0]) < 1.0:
            errors.append("task2_8j_7c_changed_relation_coverage_below_1")
        if _safe_float(final_summary["audit_trace_coverage_rate"].iloc[0]) < 1.0:
            errors.append("task2_8j_7c_audit_trace_coverage_below_1")
    return errors


def build_and_validate_relation_to_ot_information_preservation_audit(
    tracking_cfg: V2StructureChangeTrackingConfig | None = None,
    ot_cfg: OtObservationMapConfig | None = None,
    audit_cfg: OtAuditLayeringConfig | None = None,
    cfg: RelationToOtInformationPreservationConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    tracking_cfg = tracking_cfg or V2StructureChangeTrackingConfig()
    ot_cfg = ot_cfg or OtObservationMapConfig()
    audit_cfg = audit_cfg or OtAuditLayeringConfig()
    phase_table, edge_change, stale_updated, _tracking_summary, tracking_errors, _tracking_json = build_and_validate_v2_structure_change_relation_field_tracking(tracking_cfg)
    observation_units = build_ot_observation_units(phase_table, edge_change, stale_updated, ot_cfg)
    route_table = build_route_table()
    ot_summary = build_ot_final_summary(observation_units, route_table)
    ot_errors = validate_ot_observation_map_tables(observation_units, route_table, ot_summary)
    audit_layers = build_audit_layer_table(observation_units, audit_cfg)
    reason_summary = build_reason_summary(audit_layers)
    audit_summary = build_audit_final_summary(audit_layers, reason_summary)
    audit_errors = validate_ot_audit_layering_tables(audit_layers, reason_summary, audit_summary)
    relation_trace = build_relation_trace_audit(edge_change, observation_units, ot_cfg, cfg)
    coverage_audit = build_coverage_audit(phase_table, edge_change, stale_updated, observation_units, relation_trace)
    audit_trace = build_audit_trace_table(observation_units, audit_layers)
    final_summary = build_final_summary(edge_change, observation_units, relation_trace, coverage_audit, audit_trace)
    errors = [f"task2_8j_7c_upstream_6c_error:{e}" for e in tracking_errors]
    errors.extend([f"task2_8j_7c_upstream_7_error:{e}" for e in ot_errors])
    errors.extend([f"task2_8j_7c_upstream_7b_error:{e}" for e in audit_errors])
    errors.extend(validate_relation_to_ot_information_preservation_tables(relation_trace, coverage_audit, audit_trace, final_summary))
    summary = {
        "gt_main_map_name": "static_pca_7",
        "gt_main_component_count": 7,
        "source_relation_edge_count": int(final_summary["source_relation_edge_count"].iloc[0]) if not final_summary.empty else 0,
        "source_changed_relation_count": int(final_summary["source_changed_relation_count"].iloc[0]) if not final_summary.empty else 0,
        "ot_observation_unit_count": int(final_summary["ot_observation_unit_count"].iloc[0]) if not final_summary.empty else 0,
        "ot_relation_change_observation_count": int(final_summary["ot_relation_change_observation_count"].iloc[0]) if not final_summary.empty else 0,
        "covered_changed_relation_count": int(final_summary["covered_changed_relation_count"].iloc[0]) if not final_summary.empty else 0,
        "changed_relation_coverage_rate": _safe_float(final_summary["changed_relation_coverage_rate"].iloc[0]) if not final_summary.empty else 0.0,
        "state_phase_coverage_rate": _safe_float(final_summary["state_phase_coverage_rate"].iloc[0]) if not final_summary.empty else 0.0,
        "tracking_recovery_coverage_rate": _safe_float(final_summary["tracking_recovery_coverage_rate"].iloc[0]) if not final_summary.empty else 0.0,
        "audit_trace_coverage_rate": _safe_float(final_summary["audit_trace_coverage_rate"].iloc[0]) if not final_summary.empty else 0.0,
        "compressed_out_relation_edge_count": int(final_summary["compressed_out_relation_edge_count"].iloc[0]) if not final_summary.empty else 0,
        "relation_trace_mismatch_count": int(final_summary["relation_trace_mismatch_count"].iloc[0]) if not final_summary.empty else 0,
        "information_preservation_decision": str(final_summary["information_preservation_decision"].iloc[0]) if not final_summary.empty else "empty",
        "upper_pressure_route_connected": False,
        "actionmodule_called": False,
        "validation_errors": errors,
    }
    return relation_trace, coverage_audit, audit_trace, final_summary, errors, summary
