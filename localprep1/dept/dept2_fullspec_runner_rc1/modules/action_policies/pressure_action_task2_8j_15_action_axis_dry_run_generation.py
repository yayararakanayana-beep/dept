"""Task 2-8j-15: action-axis dry-run generation RC1.

Purpose:
    Generate dry-run action axes from Task 2-8j-14 material bundles, without
    execution.  Each dry-run axis must carry timing, place, direction, strength,
    duration, immediate-release, rollback, audit, and NO_OP gates.

Position:
    Task 2-8j-14 bundled allowed material sources.  This task is the first step
    that creates action-axis records, but the records remain non-executable
    planning objects.  It does not create concrete actions, action candidates,
    action-effect predictions, runtime inputs, or ActionModule calls.

Core design principle:
    direction selection + state dependence + immediate release, with weak / local
    / reversible strength and explicit NO_OP comparison before any later action
    candidate generation.

Boundary:
    - dry-run action-axis generation only
    - fixed static_pca_7 upstream assumption
    - source material bundles must remain traceable
    - no concrete action, no action candidate, no action-effect prediction
    - no ActionModule call, runtime call, writeback, hidden-truth / future-
      information input, or axis mutation
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .pressure_action_task2_8j_6c_v2_structure_change_relation_field_tracking import V2StructureChangeTrackingConfig
from .pressure_action_task2_8j_7_ot_observation_map_from_relation_field import OtObservationMapConfig
from .pressure_action_task2_8j_7b_ot_audit_layering import OtAuditLayeringConfig
from .pressure_action_task2_8j_7c_relation_to_ot_information_preservation_audit import RelationToOtInformationPreservationConfig
from .pressure_action_task2_8j_8_action_module_input_split_contract import ActionModuleInputSplitContractConfig
from .pressure_action_task2_8j_9_two_route_reception_dry_run import TwoRouteReceptionDryRunConfig
from .pressure_action_task2_8j_10_game_structure_prediction_input_contract import GameStructurePredictionInputContractConfig
from .pressure_action_task2_8j_11_game_structure_prediction_envelope_dry_run import GameStructurePredictionEnvelopeDryRunConfig
from .pressure_action_task2_8j_12_new_gt_upper_layer_revalidation import NewGtUpperLayerRevalidationConfig
from .pressure_action_task2_8j_13_action_axis_material_contract import ActionAxisMaterialContractConfig
from .pressure_action_task2_8j_14_action_axis_material_bundle_dry_run import (
    ActionAxisMaterialBundleDryRunConfig,
    build_and_validate_action_axis_material_bundle_dry_run,
)

TASK2_8J_15_VERSION = "action_axis_dry_run_generation_rc1"
TASK2_8J_15_CONTRACT = (
    "Task2_8j_15_action_axis_dry_run_generation__"
    "direction_selection_state_dependence_immediate_release_NO_OP_gate__"
    "no_execution_no_concrete_action_no_action_effect_prediction_no_runtime"
)

BOUNDARY = {
    "task2_8j_15_version": TASK2_8J_15_VERSION,
    "task2_8j_15_contract": TASK2_8J_15_CONTRACT,
    "validation_only": True,
    "dry_run_only": True,
    "action_axis_dry_run_generation_only": True,
    "action_axis_dry_run_generated": True,
    "gt_main_map_name": "static_pca_7",
    "gt_main_component_count": 7,
    "source_material_bundle_required": True,
    "direction_selection_required": True,
    "state_dependent_trigger_required": True,
    "immediate_release_required": True,
    "weak_local_reversible_required": True,
    "no_op_baseline_required": True,
    "rollback_required": True,
    "route_tags_preserved": True,
    "source_traces_preserved": True,
    "v8_local_audit_reserved_optional": True,
    "exploration_axis_input_reserved_not_used": True,
    "concrete_action_generated": False,
    "action_candidate_generated": False,
    "action_effect_prediction_generated": False,
    "action_translation_performed": False,
    "action_input_converted": False,
    "action_frame_created": False,
    "real_actionmodule_called": False,
    "actionmodule_called": False,
    "axis_executed": False,
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
    "concrete_action_generated",
    "action_candidate_generated",
    "action_effect_prediction_generated",
    "action_translation_performed",
    "action_input_converted",
    "action_frame_created",
    "real_actionmodule_called",
    "actionmodule_called",
    "axis_executed",
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

REQUIRED_AXIS_COLUMNS = list(BOUNDARY) + [
    "action_axis_id",
    "source_material_bundle_id",
    "axis_kind",
    "axis_status",
    "timing_gate",
    "place_scope",
    "direction_selector",
    "strength_bound",
    "duration_rule",
    "release_condition",
    "rollback_condition",
    "no_op_gate",
    "audit_gate",
    "route_material_tags",
    "upper_pressure_candidate_id",
    "prediction_bundle_id",
    "source_observation_ids",
    "source_relation_trace_ids",
    "pressure_family",
    "predicted_relation_tendency",
    "expected_value_gate_status",
    "dry_run_axis_eligible_for_later_candidate_generation",
]

REQUIRED_TRACE_COLUMNS = list(BOUNDARY) + [
    "action_axis_id",
    "source_material_bundle_id",
    "trace_type",
    "trace_id",
    "trace_role",
    "trace_status",
]

REQUIRED_CHECK_COLUMNS = list(BOUNDARY) + [
    "check_id",
    "check_scope",
    "check_description",
    "expected_value",
    "observed_value",
    "check_status",
]

REQUIRED_SUMMARY_COLUMNS = list(BOUNDARY) + [
    "action_axis_count",
    "axis_trace_row_count",
    "axis_trace_preserved_count",
    "axis_check_count",
    "axis_check_pass_count",
    "direction_selection_axis_count",
    "state_dependent_axis_count",
    "immediate_release_axis_count",
    "no_op_gate_axis_count",
    "weak_local_reversible_axis_count",
    "later_candidate_eligible_axis_count",
    "action_axis_dry_run_generation_decision",
    "next_task",
]


@dataclass(frozen=True)
class ActionAxisDryRunGenerationConfig:
    require_task14_ready: bool = True
    max_axes: int = 9
    max_strength_bound: float = 0.20


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return float(default)
    if not np.isfinite(out):
        return float(default)
    return float(out)


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def _axis_kind(bundle_row) -> str:
    pressure_family = str(bundle_row.pressure_family)
    if pressure_family == "NO_OP":
        return "NO_OP_review_axis"
    if "information" in pressure_family:
        return "information_integrity_direction_axis"
    if "resource" in pressure_family:
        return "resource_balance_direction_axis"
    if "recovery" in pressure_family or "reversibility" in pressure_family:
        return "recovery_reversibility_direction_axis"
    if "exploration" in pressure_family:
        return "exploration_margin_protection_axis"
    return "bounded_direction_selection_axis"


def _expected_value_gate(bundle_row) -> tuple[str, bool]:
    confidence = _safe_float(bundle_row.prediction_confidence)
    uncertainty = _safe_float(bundle_row.prediction_uncertainty)
    audit_level = str(bundle_row.audit_level)
    pressure_family = str(bundle_row.pressure_family)
    if pressure_family == "NO_OP":
        return "NO_OP_preferred_by_pressure_family", False
    if audit_level == "block_direct_action":
        return "NO_OP_required_by_audit_block", False
    if confidence >= 0.55 and uncertainty <= 0.70:
        return "expected_value_gate_passes_for_later_non_execution_candidate_review", True
    return "expected_value_gate_requires_review_or_NO_OP", False


def build_action_axes_from_material_bundles(
    bundles: pd.DataFrame,
    cfg: ActionAxisDryRunGenerationConfig | None = None,
) -> pd.DataFrame:
    cfg = cfg or ActionAxisDryRunGenerationConfig()
    if bundles is None or bundles.empty:
        return pd.DataFrame(columns=REQUIRED_AXIS_COLUMNS)
    rows: list[dict] = []
    for i, row in enumerate(bundles.head(max(1, int(cfg.max_axes))).itertuples(index=False)):
        ev_status, eligible = _expected_value_gate(row)
        strength = min(cfg.max_strength_bound, max(0.0, _safe_float(row.bounded_pressure_magnitude)))
        status = "dry_run_action_axis_ready_no_execution" if eligible else "dry_run_action_axis_routes_to_NO_OP_or_review"
        rows.append({
            **BOUNDARY,
            "action_axis_id": f"action_axis_dry_run_{i:04d}",
            "source_material_bundle_id": str(row.material_bundle_id),
            "axis_kind": _axis_kind(row),
            "axis_status": status,
            "timing_gate": str(row.timing_material),
            "place_scope": str(row.place_material),
            "direction_selector": str(row.direction_material),
            "strength_bound": float(strength),
            "duration_rule": str(row.duration_material),
            "release_condition": str(row.release_material),
            "rollback_condition": str(row.rollback_material),
            "no_op_gate": str(row.no_op_baseline_material),
            "audit_gate": f"audit_level={row.audit_level};audit_reasons={row.audit_reasons}",
            "route_material_tags": str(row.route_material_tags),
            "upper_pressure_candidate_id": str(row.upper_pressure_candidate_id),
            "prediction_bundle_id": str(row.prediction_bundle_id),
            "source_observation_ids": str(row.source_observation_ids),
            "source_relation_trace_ids": str(row.source_relation_trace_ids),
            "pressure_family": str(row.pressure_family),
            "predicted_relation_tendency": str(row.predicted_relation_tendency),
            "expected_value_gate_status": ev_status,
            "dry_run_axis_eligible_for_later_candidate_generation": bool(eligible),
        })
    return pd.DataFrame(rows, columns=REQUIRED_AXIS_COLUMNS)


def build_axis_trace_table(axes: pd.DataFrame) -> pd.DataFrame:
    if axes is None or axes.empty:
        return pd.DataFrame(columns=REQUIRED_TRACE_COLUMNS)
    rows: list[dict] = []
    for row in axes.itertuples(index=False):
        traces = [
            ("material_bundle", str(row.source_material_bundle_id), "source bundle for dry-run action-axis generation"),
            ("upper_pressure", str(row.upper_pressure_candidate_id), "what to weakly bias"),
            ("game_structure_prediction", str(row.prediction_bundle_id), "current-structure drift material"),
            ("ot_observation", str(row.source_observation_ids), "where / state-dependent trigger evidence"),
            ("relation_trace", str(row.source_relation_trace_ids), "direction and place evidence"),
            ("NO_OP_gate", str(row.no_op_gate), "baseline comparison requirement"),
            ("release_condition", str(row.release_condition), "immediate release requirement"),
        ]
        for trace_type, trace_id, role in traces:
            rows.append({
                **BOUNDARY,
                "action_axis_id": str(row.action_axis_id),
                "source_material_bundle_id": str(row.source_material_bundle_id),
                "trace_type": trace_type,
                "trace_id": trace_id,
                "trace_role": role,
                "trace_status": "axis_source_trace_preserved" if str(trace_id) else "axis_source_trace_missing",
            })
    return pd.DataFrame(rows, columns=REQUIRED_TRACE_COLUMNS)


def build_axis_checks(axes: pd.DataFrame, trace_table: pd.DataFrame, task14_errors: list[str], task14_summary: dict, cfg: ActionAxisDryRunGenerationConfig | None = None) -> pd.DataFrame:
    cfg = cfg or ActionAxisDryRunGenerationConfig()
    has_axes = bool(axes is not None and not axes.empty)
    task14_ready = len(task14_errors) == 0 and str(task14_summary.get("action_axis_material_bundle_dry_run_decision", "")).startswith("action_axis_material_bundle_dry_run_ready")
    checks = [
        ("check_task14_ready", "upstream", "Task2-8j-14 material bundles are ready.", True, task14_ready),
        ("check_axes_created", "axis", "At least one dry-run action axis is created.", True, has_axes),
        ("check_direction_selection", "axis", "Every axis has direction-selection material.", True, bool(axes["direction_selector"].astype(str).str.contains("direction_selection_material").all()) if has_axes else False),
        ("check_state_dependence", "axis", "Every axis has state-dependent timing/place material.", True, bool(axes["timing_gate"].astype(str).str.contains("state_dependent_trigger_material").all()) if has_axes else False),
        ("check_immediate_release", "axis", "Every axis has immediate-release material.", True, bool(axes["release_condition"].astype(str).str.contains("immediate_release_material_required").all()) if has_axes else False),
        ("check_no_op_gate", "axis", "Every axis has a NO_OP gate.", True, bool(axes["no_op_gate"].astype(str).str.contains("NO_OP_baseline_required").all()) if has_axes else False),
        ("check_weak_strength", "axis", "Every axis strength is within the weak bound.", True, bool((axes["strength_bound"].astype(float) <= cfg.max_strength_bound).all()) if has_axes else False),
        ("check_trace_preserved", "trace", "Every trace row is preserved.", True, bool(trace_table is not None and not trace_table.empty and (trace_table["trace_status"].astype(str) == "axis_source_trace_preserved").all())),
        ("check_no_concrete_action", "boundary", "No concrete action is generated.", False, bool(axes["concrete_action_generated"].astype(bool).any()) if has_axes else True),
        ("check_no_action_candidate", "boundary", "No action candidate is generated.", False, bool(axes["action_candidate_generated"].astype(bool).any()) if has_axes else True),
        ("check_no_action_effect_prediction", "boundary", "No action-effect prediction is generated.", False, bool(axes["action_effect_prediction_generated"].astype(bool).any()) if has_axes else True),
        ("check_no_execution", "boundary", "No axis is executed.", False, bool(axes["axis_executed"].astype(bool).any()) if has_axes else True),
    ]
    rows: list[dict] = []
    for check_id, scope, description, expected, observed in checks:
        rows.append({
            **BOUNDARY,
            "check_id": check_id,
            "check_scope": scope,
            "check_description": description,
            "expected_value": bool(expected),
            "observed_value": bool(observed),
            "check_status": "pass" if bool(expected) == bool(observed) else "fail",
        })
    return pd.DataFrame(rows, columns=REQUIRED_CHECK_COLUMNS)


def build_final_summary(axes: pd.DataFrame, trace_table: pd.DataFrame, checks: pd.DataFrame) -> pd.DataFrame:
    axis_count = int(len(axes)) if axes is not None else 0
    trace_count = int(len(trace_table)) if trace_table is not None else 0
    trace_pass = int((trace_table["trace_status"].astype(str) == "axis_source_trace_preserved").sum()) if trace_count else 0
    check_count = int(len(checks)) if checks is not None else 0
    check_pass = int((checks["check_status"].astype(str) == "pass").sum()) if check_count else 0
    direction_count = int(axes["direction_selector"].astype(str).str.contains("direction_selection_material").sum()) if axis_count else 0
    state_count = int(axes["timing_gate"].astype(str).str.contains("state_dependent_trigger_material").sum()) if axis_count else 0
    release_count = int(axes["release_condition"].astype(str).str.contains("immediate_release_material_required").sum()) if axis_count else 0
    no_op_count = int(axes["no_op_gate"].astype(str).str.contains("NO_OP_baseline_required").sum()) if axis_count else 0
    weak_count = int((axes["strength_bound"].astype(float) <= 0.20).sum()) if axis_count else 0
    eligible_count = int(axes["dry_run_axis_eligible_for_later_candidate_generation"].astype(bool).sum()) if axis_count else 0
    if axis_count > 0 and direction_count == state_count == release_count == no_op_count == weak_count == axis_count and trace_count == trace_pass and check_count == check_pass:
        decision = "action_axis_dry_run_generation_ready_without_execution"
    else:
        decision = "action_axis_dry_run_generation_needs_review"
    return pd.DataFrame([{
        **BOUNDARY,
        "action_axis_count": axis_count,
        "axis_trace_row_count": trace_count,
        "axis_trace_preserved_count": trace_pass,
        "axis_check_count": check_count,
        "axis_check_pass_count": check_pass,
        "direction_selection_axis_count": direction_count,
        "state_dependent_axis_count": state_count,
        "immediate_release_axis_count": release_count,
        "no_op_gate_axis_count": no_op_count,
        "weak_local_reversible_axis_count": weak_count,
        "later_candidate_eligible_axis_count": eligible_count,
        "action_axis_dry_run_generation_decision": decision,
        "next_task": "Task 2-8j-16: action-axis non-execution review and NO_OP comparison",
    }], columns=REQUIRED_SUMMARY_COLUMNS)


def validate_action_axis_dry_run_generation_tables(axes: pd.DataFrame, trace_table: pd.DataFrame, checks: pd.DataFrame, final_summary: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    tables = {
        "axes": (axes, REQUIRED_AXIS_COLUMNS),
        "trace_table": (trace_table, REQUIRED_TRACE_COLUMNS),
        "checks": (checks, REQUIRED_CHECK_COLUMNS),
        "final_summary": (final_summary, REQUIRED_SUMMARY_COLUMNS),
    }
    for name, (table, required) in tables.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_15_empty_table:{name}")
            continue
        missing = [c for c in required if c not in table.columns]
        if missing:
            errors.append(f"task2_8j_15_missing_columns:{name}:" + ",".join(missing))
            continue
        for col in [
            "validation_only", "dry_run_only", "action_axis_dry_run_generation_only", "action_axis_dry_run_generated",
            "source_material_bundle_required", "direction_selection_required", "state_dependent_trigger_required",
            "immediate_release_required", "weak_local_reversible_required", "no_op_baseline_required", "rollback_required",
            "route_tags_preserved", "source_traces_preserved", "v8_local_audit_reserved_optional", "exploration_axis_input_reserved_not_used",
        ]:
            if not bool(table[col].astype(bool).all()):
                errors.append(f"task2_8j_15_required_true_not_all_true:{name}:{col}")
        if set(table["gt_main_map_name"].astype(str)) != {"static_pca_7"}:
            errors.append(f"task2_8j_15_wrong_gt_main_map_name:{name}")
        if set(table["gt_main_component_count"].astype(int)) != {7}:
            errors.append(f"task2_8j_15_wrong_gt_component_count:{name}")
        for col in FORBIDDEN_TRUE:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_15_forbidden_true:{name}:{col}")
    if axes is not None and not axes.empty:
        if not bool(axes["direction_selector"].astype(str).str.contains("direction_selection_material").all()):
            errors.append("task2_8j_15_direction_selector_missing")
        if not bool(axes["timing_gate"].astype(str).str.contains("state_dependent_trigger_material").all()):
            errors.append("task2_8j_15_state_dependent_timing_missing")
        if not bool(axes["release_condition"].astype(str).str.contains("immediate_release_material_required").all()):
            errors.append("task2_8j_15_release_condition_missing")
        if not bool(axes["no_op_gate"].astype(str).str.contains("NO_OP_baseline_required").all()):
            errors.append("task2_8j_15_no_op_gate_missing")
        if bool((axes["strength_bound"].astype(float) > 0.20).any()):
            errors.append("task2_8j_15_strength_bound_exceeded")
    if trace_table is not None and not trace_table.empty:
        if not bool((trace_table["trace_status"].astype(str) == "axis_source_trace_preserved").all()):
            errors.append("task2_8j_15_axis_trace_not_preserved")
    if checks is not None and not checks.empty:
        if not bool((checks["check_status"].astype(str) == "pass").all()):
            errors.append("task2_8j_15_check_failed")
    return errors


def build_and_validate_action_axis_dry_run_generation(
    tracking_cfg: V2StructureChangeTrackingConfig | None = None,
    ot_cfg: OtObservationMapConfig | None = None,
    audit_cfg: OtAuditLayeringConfig | None = None,
    preservation_cfg: RelationToOtInformationPreservationConfig | None = None,
    split_cfg: ActionModuleInputSplitContractConfig | None = None,
    reception_cfg: TwoRouteReceptionDryRunConfig | None = None,
    prediction_contract_cfg: GameStructurePredictionInputContractConfig | None = None,
    prediction_envelope_cfg: GameStructurePredictionEnvelopeDryRunConfig | None = None,
    upper_layer_cfg: NewGtUpperLayerRevalidationConfig | None = None,
    material_contract_cfg: ActionAxisMaterialContractConfig | None = None,
    bundle_cfg: ActionAxisMaterialBundleDryRunConfig | None = None,
    cfg: ActionAxisDryRunGenerationConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    cfg = cfg or ActionAxisDryRunGenerationConfig()
    tracking_cfg = tracking_cfg or V2StructureChangeTrackingConfig()
    bundles, _source_trace, _bundle_checks, _bundle_final, task14_errors, task14_summary = build_and_validate_action_axis_material_bundle_dry_run(
        tracking_cfg=tracking_cfg,
        ot_cfg=ot_cfg or OtObservationMapConfig(),
        audit_cfg=audit_cfg or OtAuditLayeringConfig(),
        preservation_cfg=preservation_cfg or RelationToOtInformationPreservationConfig(),
        split_cfg=split_cfg or ActionModuleInputSplitContractConfig(),
        reception_cfg=reception_cfg or TwoRouteReceptionDryRunConfig(),
        prediction_contract_cfg=prediction_contract_cfg or GameStructurePredictionInputContractConfig(),
        prediction_envelope_cfg=prediction_envelope_cfg or GameStructurePredictionEnvelopeDryRunConfig(),
        upper_layer_cfg=upper_layer_cfg or NewGtUpperLayerRevalidationConfig(),
        material_contract_cfg=material_contract_cfg or ActionAxisMaterialContractConfig(),
        cfg=bundle_cfg or ActionAxisMaterialBundleDryRunConfig(),
    )
    upstream_errors = [f"task2_8j_15_upstream_14_error:{e}" for e in task14_errors] if cfg.require_task14_ready else []
    axes = build_action_axes_from_material_bundles(bundles, cfg)
    trace_table = build_axis_trace_table(axes)
    checks = build_axis_checks(axes, trace_table, upstream_errors, task14_summary, cfg)
    final_summary = build_final_summary(axes, trace_table, checks)
    errors = list(upstream_errors)
    errors.extend(validate_action_axis_dry_run_generation_tables(axes, trace_table, checks, final_summary))
    summary = {
        "gt_main_map_name": "static_pca_7",
        "gt_main_component_count": 7,
        "task14_decision": task14_summary.get("action_axis_material_bundle_dry_run_decision", ""),
        "action_axis_count": _safe_int(final_summary["action_axis_count"].iloc[0]) if not final_summary.empty else 0,
        "axis_trace_row_count": _safe_int(final_summary["axis_trace_row_count"].iloc[0]) if not final_summary.empty else 0,
        "axis_trace_preserved_count": _safe_int(final_summary["axis_trace_preserved_count"].iloc[0]) if not final_summary.empty else 0,
        "axis_check_count": _safe_int(final_summary["axis_check_count"].iloc[0]) if not final_summary.empty else 0,
        "axis_check_pass_count": _safe_int(final_summary["axis_check_pass_count"].iloc[0]) if not final_summary.empty else 0,
        "later_candidate_eligible_axis_count": _safe_int(final_summary["later_candidate_eligible_axis_count"].iloc[0]) if not final_summary.empty else 0,
        "action_axis_dry_run_generation_decision": str(final_summary["action_axis_dry_run_generation_decision"].iloc[0]) if not final_summary.empty else "empty",
        "action_axis_dry_run_generated": True,
        "concrete_action_generated": False,
        "action_candidate_generated": False,
        "action_effect_prediction_generated": False,
        "axis_executed": False,
        "real_actionmodule_called": False,
        "validation_errors": errors,
    }
    return axes, trace_table, checks, final_summary, errors, summary
