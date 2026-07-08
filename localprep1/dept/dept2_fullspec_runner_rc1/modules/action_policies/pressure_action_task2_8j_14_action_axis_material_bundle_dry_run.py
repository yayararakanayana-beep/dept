"""Task 2-8j-14: action-axis material bundle dry-run RC1.

Purpose:
    Dry-run package the allowed Task 2-8j-13 action-axis material sources into
    traceable material bundles for a later action-axis generation step, without
    generating action axes, action candidates, concrete actions, or action-effect
    predictions.

Position:
    Task 2-8j-13 froze the material contract: upper pressure, O_t context,
    game-structure prediction envelopes, audit material, and NO_OP baseline are
    allowed as prepared inputs.  This task checks that those materials can be
    bundled while preserving route tags and source traces.

Core design principle carried forward:
    direction selection + state dependence + immediate release, constrained by
    weak / local / reversible pressure and NO_OP baseline comparison.

Boundary:
    - material-bundle dry-run only
    - fixed static_pca_7 upstream assumption
    - no action-axis generation, action candidate, concrete action, or action-
      effect prediction
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
from .pressure_action_task2_8j_11_game_structure_prediction_envelope_dry_run import (
    GameStructurePredictionEnvelopeDryRunConfig,
    build_and_validate_game_structure_prediction_envelope_dry_run,
)
from .pressure_action_task2_8j_12_new_gt_upper_layer_revalidation import (
    NewGtUpperLayerRevalidationConfig,
    build_and_validate_new_gt_upper_layer_revalidation,
)
from .pressure_action_task2_8j_13_action_axis_material_contract import (
    ActionAxisMaterialContractConfig,
    build_and_validate_action_axis_material_contract,
)

TASK2_8J_14_VERSION = "action_axis_material_bundle_dry_run_rc1"
TASK2_8J_14_CONTRACT = (
    "Task2_8j_14_action_axis_material_bundle_dry_run__"
    "package_allowed_materials_with_route_tags_and_source_traces__"
    "direction_selection_state_dependence_immediate_release_material_only__"
    "no_action_axes_no_candidates_no_runtime"
)

BOUNDARY = {
    "task2_8j_14_version": TASK2_8J_14_VERSION,
    "task2_8j_14_contract": TASK2_8J_14_CONTRACT,
    "validation_only": True,
    "dry_run_only": True,
    "material_bundle_dry_run_only": True,
    "material_bundle_created": True,
    "gt_main_map_name": "static_pca_7",
    "gt_main_component_count": 7,
    "upper_pressure_material_included": True,
    "ot_context_material_included": True,
    "game_structure_prediction_material_included": True,
    "audit_material_included": True,
    "no_op_baseline_material_included": True,
    "direction_selection_material_required": True,
    "state_dependent_trigger_material_required": True,
    "immediate_release_material_required": True,
    "weak_local_reversible_material_required": True,
    "route_tags_preserved": True,
    "source_traces_preserved": True,
    "v8_local_audit_reserved_optional": True,
    "exploration_axis_input_reserved_not_used": True,
    "action_axis_generated": False,
    "action_candidate_generated": False,
    "concrete_action_generated": False,
    "action_effect_prediction_generated": False,
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
    "action_axis_generated",
    "action_candidate_generated",
    "concrete_action_generated",
    "action_effect_prediction_generated",
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

REQUIRED_BUNDLE_COLUMNS = list(BOUNDARY) + [
    "material_bundle_id",
    "bundle_kind",
    "upper_pressure_candidate_id",
    "pressure_family",
    "source_mt_component",
    "bounded_pressure_magnitude",
    "pressure_polarity",
    "prediction_bundle_id",
    "source_observation_ids",
    "source_relation_trace_ids",
    "predicted_state_tendency",
    "predicted_relation_tendency",
    "prediction_confidence",
    "prediction_uncertainty",
    "audit_level",
    "audit_reasons",
    "timing_material",
    "place_material",
    "direction_material",
    "strength_material",
    "duration_material",
    "release_material",
    "no_op_baseline_material",
    "rollback_material",
    "route_material_tags",
    "later_axis_generation_input_status",
    "bundle_status",
]

REQUIRED_SOURCE_TRACE_COLUMNS = list(BOUNDARY) + [
    "material_bundle_id",
    "source_type",
    "source_id",
    "source_task",
    "source_role",
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
    "material_bundle_count",
    "source_trace_row_count",
    "bundle_check_count",
    "bundle_check_pass_count",
    "route_tagged_bundle_count",
    "source_trace_preserved_bundle_count",
    "no_op_baseline_bundle_count",
    "release_material_bundle_count",
    "action_axis_material_bundle_dry_run_decision",
    "next_task",
]


@dataclass(frozen=True)
class ActionAxisMaterialBundleDryRunConfig:
    require_task13_ready: bool = True
    max_bundles: int = 9


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return float(default)
    if not np.isfinite(out):
        return float(default)
    return float(out)


def _direction_material(pressure_row, envelope_row) -> str:
    pressure_family = str(pressure_row.pressure_family)
    pressure_polarity = str(pressure_row.pressure_polarity)
    predicted_relation = str(envelope_row.predicted_relation_tendency)
    return (
        "direction_selection_material_from_upper_pressure_and_current_structure_forecast:"
        f"pressure_family={pressure_family};polarity={pressure_polarity};predicted_relation={predicted_relation}"
    )


def _timing_material(envelope_row) -> str:
    confidence = _safe_float(envelope_row.confidence)
    uncertainty = _safe_float(envelope_row.uncertainty)
    if confidence >= 0.70 and uncertainty <= 0.40:
        return "state_dependent_trigger_material:eligible_when_current_structure_forecast_and_audit_condition_hold"
    return "state_dependent_trigger_material:review_or_NO_OP_when_confidence_uncertainty_gate_not_clear"


def _place_material(envelope_row) -> str:
    obs = str(envelope_row.source_observation_ids)
    trace = str(envelope_row.source_relation_trace_ids)
    return f"place_material_from_traceable_Ot_and_relation_evidence:observation={obs};relation_trace={trace}"


def _strength_material(pressure_row, envelope_row) -> str:
    magnitude = _safe_float(pressure_row.bounded_pressure_magnitude)
    confidence = _safe_float(envelope_row.confidence)
    uncertainty = _safe_float(envelope_row.uncertainty)
    return (
        "weak_strength_material_only:"
        f"bounded_pressure={magnitude:.6f};prediction_confidence={confidence:.6f};uncertainty={uncertainty:.6f};"
        "later_axis_generation_must_recheck_NO_OP"
    )


def build_action_axis_material_bundles(
    pressure_table: pd.DataFrame,
    envelopes: pd.DataFrame,
    cfg: ActionAxisMaterialBundleDryRunConfig | None = None,
) -> pd.DataFrame:
    cfg = cfg or ActionAxisMaterialBundleDryRunConfig()
    if pressure_table is None or pressure_table.empty or envelopes is None or envelopes.empty:
        return pd.DataFrame(columns=REQUIRED_BUNDLE_COLUMNS)
    pressure_rows = list(pressure_table.itertuples(index=False))[: max(1, int(cfg.max_bundles))]
    envelope_rows = list(envelopes.itertuples(index=False))
    rows: list[dict] = []
    for i, pressure_row in enumerate(pressure_rows):
        envelope_row = envelope_rows[i % len(envelope_rows)]
        pressure_id = str(pressure_row.pressure_candidate_id)
        prediction_id = str(envelope_row.prediction_bundle_id)
        audit_level = str(envelope_row.audit_level)
        status = "material_bundle_ready_for_later_axis_generation"
        if str(pressure_row.pressure_family) == "NO_OP" or audit_level == "block_direct_action":
            status = "material_bundle_routes_to_NO_OP_or_review_before_axis_generation"
        rows.append({
            **BOUNDARY,
            "material_bundle_id": f"action_axis_material_bundle_{i:04d}",
            "bundle_kind": "action_axis_material_bundle_dry_run_without_axis_generation",
            "upper_pressure_candidate_id": pressure_id,
            "pressure_family": str(pressure_row.pressure_family),
            "source_mt_component": str(pressure_row.source_mt_component),
            "bounded_pressure_magnitude": _safe_float(pressure_row.bounded_pressure_magnitude),
            "pressure_polarity": str(pressure_row.pressure_polarity),
            "prediction_bundle_id": prediction_id,
            "source_observation_ids": str(envelope_row.source_observation_ids),
            "source_relation_trace_ids": str(envelope_row.source_relation_trace_ids),
            "predicted_state_tendency": str(envelope_row.predicted_state_tendency),
            "predicted_relation_tendency": str(envelope_row.predicted_relation_tendency),
            "prediction_confidence": _safe_float(envelope_row.confidence),
            "prediction_uncertainty": _safe_float(envelope_row.uncertainty),
            "audit_level": audit_level,
            "audit_reasons": str(envelope_row.audit_reasons),
            "timing_material": _timing_material(envelope_row),
            "place_material": _place_material(envelope_row),
            "direction_material": _direction_material(pressure_row, envelope_row),
            "strength_material": _strength_material(pressure_row, envelope_row),
            "duration_material": "duration_material_pending_later_axis_generation:short_reversible_only",
            "release_material": "immediate_release_material_required_when_trigger_condition_fades_or_audit_worsens",
            "no_op_baseline_material": "NO_OP_baseline_required_before_any_later_axis_generation",
            "rollback_material": str(pressure_row.rollback_policy),
            "route_material_tags": "upper_pressure_route|ot_observation_context|game_structure_prediction|audit|NO_OP_baseline",
            "later_axis_generation_input_status": "ready_as_material_only_no_axis_generated",
            "bundle_status": status,
        })
    return pd.DataFrame(rows, columns=REQUIRED_BUNDLE_COLUMNS)


def build_bundle_source_trace_table(bundles: pd.DataFrame) -> pd.DataFrame:
    if bundles is None or bundles.empty:
        return pd.DataFrame(columns=REQUIRED_SOURCE_TRACE_COLUMNS)
    rows: list[dict] = []
    for row in bundles.itertuples(index=False):
        bundle_id = str(row.material_bundle_id)
        sources = [
            (
                "upper_pressure",
                str(row.upper_pressure_candidate_id),
                "Task2_8j_12_new_gt_upper_layer_revalidation",
                "what_to_weakly_bias",
            ),
            (
                "game_structure_prediction",
                str(row.prediction_bundle_id),
                "Task2_8j_11_game_structure_prediction_envelope_dry_run",
                "where_the_current_structure_is_likely_to_drift",
            ),
            (
                "ot_relation_trace",
                str(row.source_relation_trace_ids),
                "Task2_8j_7c_relation_to_Ot_information_preservation",
                "traceable_evidence_location_and_relation",
            ),
            (
                "audit",
                f"{row.audit_level}:{row.audit_reasons}",
                "Task2_8j_7b_Ot_audit_layering",
                "review_gate_and_NO_OP_support",
            ),
            (
                "NO_OP_baseline",
                str(row.no_op_baseline_material),
                "Task2_8j_13_action_axis_material_contract",
                "baseline_comparison_requirement",
            ),
        ]
        for source_type, source_id, source_task, role in sources:
            rows.append({
                **BOUNDARY,
                "material_bundle_id": bundle_id,
                "source_type": source_type,
                "source_id": source_id,
                "source_task": source_task,
                "source_role": role,
                "trace_status": "source_trace_preserved",
            })
    return pd.DataFrame(rows, columns=REQUIRED_SOURCE_TRACE_COLUMNS)


def build_bundle_checks(bundles: pd.DataFrame, source_trace: pd.DataFrame, task13_errors: list[str], task13_summary: dict) -> pd.DataFrame:
    has_bundles = bool(bundles is not None and not bundles.empty)
    checks = [
        (
            "check_task13_contract_ready",
            "upstream_contract",
            "Task2-8j-13 material contract is ready and has no validation errors.",
            True,
            len(task13_errors) == 0 and str(task13_summary.get("action_axis_material_contract_decision", "")).startswith("action_axis_material_contract_ready"),
        ),
        (
            "check_bundles_created",
            "bundle",
            "At least one material bundle is created.",
            True,
            has_bundles,
        ),
        (
            "check_route_tags_preserved",
            "route_tags",
            "Every bundle keeps upper-pressure, O_t, prediction, audit, and NO_OP route tags.",
            True,
            bool(bundles["route_material_tags"].astype(str).str.contains("upper_pressure_route").all()) if has_bundles else False,
        ),
        (
            "check_source_traces_preserved",
            "trace",
            "Every trace row is preserved and every bundle has source trace rows.",
            True,
            bool(source_trace is not None and not source_trace.empty and (source_trace["trace_status"].astype(str) == "source_trace_preserved").all()),
        ),
        (
            "check_no_op_baseline_included",
            "NO_OP",
            "NO_OP baseline material is included in every bundle.",
            True,
            bool(bundles["no_op_baseline_material"].astype(str).str.contains("NO_OP_baseline_required").all()) if has_bundles else False,
        ),
        (
            "check_release_material_included",
            "release",
            "Immediate release material is included in every bundle.",
            True,
            bool(bundles["release_material"].astype(str).str.contains("immediate_release_material_required").all()) if has_bundles else False,
        ),
        (
            "check_no_action_axis_generated",
            "boundary",
            "No action axis is generated in the bundle dry-run.",
            False,
            bool(bundles["action_axis_generated"].astype(bool).any()) if has_bundles else True,
        ),
        (
            "check_no_action_candidate_generated",
            "boundary",
            "No action candidate is generated in the bundle dry-run.",
            False,
            bool(bundles["action_candidate_generated"].astype(bool).any()) if has_bundles else True,
        ),
        (
            "check_no_action_effect_prediction",
            "boundary",
            "No action-effect prediction is generated in the bundle dry-run.",
            False,
            bool(bundles["action_effect_prediction_generated"].astype(bool).any()) if has_bundles else True,
        ),
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


def build_final_summary(bundles: pd.DataFrame, source_trace: pd.DataFrame, checks: pd.DataFrame) -> pd.DataFrame:
    bundle_count = int(len(bundles)) if bundles is not None else 0
    trace_rows = int(len(source_trace)) if source_trace is not None else 0
    check_count = int(len(checks)) if checks is not None else 0
    check_pass = int((checks["check_status"].astype(str) == "pass").sum()) if check_count else 0
    route_tagged = int(bundles["route_material_tags"].astype(str).str.contains("upper_pressure_route").sum()) if bundle_count else 0
    source_trace_preserved = 0
    if source_trace is not None and not source_trace.empty:
        preserved = source_trace[source_trace["trace_status"].astype(str) == "source_trace_preserved"]
        source_trace_preserved = int(preserved["material_bundle_id"].nunique())
    no_op_count = int(bundles["no_op_baseline_material"].astype(str).str.contains("NO_OP_baseline_required").sum()) if bundle_count else 0
    release_count = int(bundles["release_material"].astype(str).str.contains("immediate_release_material_required").sum()) if bundle_count else 0
    if bundle_count > 0 and route_tagged == bundle_count and source_trace_preserved == bundle_count and no_op_count == bundle_count and release_count == bundle_count and check_count == check_pass:
        decision = "action_axis_material_bundle_dry_run_ready_without_axis_generation"
    else:
        decision = "action_axis_material_bundle_dry_run_needs_review"
    return pd.DataFrame([{
        **BOUNDARY,
        "material_bundle_count": bundle_count,
        "source_trace_row_count": trace_rows,
        "bundle_check_count": check_count,
        "bundle_check_pass_count": check_pass,
        "route_tagged_bundle_count": route_tagged,
        "source_trace_preserved_bundle_count": source_trace_preserved,
        "no_op_baseline_bundle_count": no_op_count,
        "release_material_bundle_count": release_count,
        "action_axis_material_bundle_dry_run_decision": decision,
        "next_task": "Task 2-8j-15: action-axis dry-run generation with no execution",
    }], columns=REQUIRED_SUMMARY_COLUMNS)


def validate_action_axis_material_bundle_dry_run_tables(bundles: pd.DataFrame, source_trace: pd.DataFrame, checks: pd.DataFrame, final_summary: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    tables = {
        "bundles": (bundles, REQUIRED_BUNDLE_COLUMNS),
        "source_trace": (source_trace, REQUIRED_SOURCE_TRACE_COLUMNS),
        "checks": (checks, REQUIRED_CHECK_COLUMNS),
        "final_summary": (final_summary, REQUIRED_SUMMARY_COLUMNS),
    }
    for name, (table, required) in tables.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_14_empty_table:{name}")
            continue
        missing = [c for c in required if c not in table.columns]
        if missing:
            errors.append(f"task2_8j_14_missing_columns:{name}:" + ",".join(missing))
            continue
        for col in [
            "validation_only",
            "dry_run_only",
            "material_bundle_dry_run_only",
            "material_bundle_created",
            "upper_pressure_material_included",
            "ot_context_material_included",
            "game_structure_prediction_material_included",
            "audit_material_included",
            "no_op_baseline_material_included",
            "direction_selection_material_required",
            "state_dependent_trigger_material_required",
            "immediate_release_material_required",
            "weak_local_reversible_material_required",
            "route_tags_preserved",
            "source_traces_preserved",
            "v8_local_audit_reserved_optional",
            "exploration_axis_input_reserved_not_used",
        ]:
            if not bool(table[col].astype(bool).all()):
                errors.append(f"task2_8j_14_required_true_not_all_true:{name}:{col}")
        if set(table["gt_main_map_name"].astype(str)) != {"static_pca_7"}:
            errors.append(f"task2_8j_14_wrong_gt_main_map_name:{name}")
        if set(table["gt_main_component_count"].astype(int)) != {7}:
            errors.append(f"task2_8j_14_wrong_gt_component_count:{name}")
        for col in FORBIDDEN_TRUE:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_14_forbidden_true:{name}:{col}")
    if bundles is not None and not bundles.empty:
        if not bool(bundles["route_material_tags"].astype(str).str.contains("upper_pressure_route").all()):
            errors.append("task2_8j_14_route_tags_not_preserved")
        if not bool(bundles["no_op_baseline_material"].astype(str).str.contains("NO_OP_baseline_required").all()):
            errors.append("task2_8j_14_no_op_baseline_missing")
        if not bool(bundles["release_material"].astype(str).str.contains("immediate_release_material_required").all()):
            errors.append("task2_8j_14_release_material_missing")
    if source_trace is not None and not source_trace.empty:
        if not bool((source_trace["trace_status"].astype(str) == "source_trace_preserved").all()):
            errors.append("task2_8j_14_source_trace_not_preserved")
    if checks is not None and not checks.empty:
        if not bool((checks["check_status"].astype(str) == "pass").all()):
            errors.append("task2_8j_14_check_failed")
    return errors


def build_and_validate_action_axis_material_bundle_dry_run(
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
    cfg: ActionAxisMaterialBundleDryRunConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    cfg = cfg or ActionAxisMaterialBundleDryRunConfig()
    tracking_cfg = tracking_cfg or V2StructureChangeTrackingConfig()
    _materials, _principles, _readiness, _contract_checks, _contract_summary, task13_errors, task13_summary = build_and_validate_action_axis_material_contract(
        tracking_cfg=tracking_cfg,
        ot_cfg=ot_cfg or OtObservationMapConfig(),
        audit_cfg=audit_cfg or OtAuditLayeringConfig(),
        preservation_cfg=preservation_cfg or RelationToOtInformationPreservationConfig(),
        split_cfg=split_cfg or ActionModuleInputSplitContractConfig(),
        reception_cfg=reception_cfg or TwoRouteReceptionDryRunConfig(),
        prediction_contract_cfg=prediction_contract_cfg or GameStructurePredictionInputContractConfig(),
        prediction_envelope_cfg=prediction_envelope_cfg or GameStructurePredictionEnvelopeDryRunConfig(),
        upper_layer_cfg=upper_layer_cfg or NewGtUpperLayerRevalidationConfig(),
        cfg=material_contract_cfg or ActionAxisMaterialContractConfig(),
    )
    envelopes, _source_trace11, _checks11, _final11, task11_errors, _task11_summary = build_and_validate_game_structure_prediction_envelope_dry_run(
        tracking_cfg,
        ot_cfg or OtObservationMapConfig(),
        audit_cfg or OtAuditLayeringConfig(),
        preservation_cfg or RelationToOtInformationPreservationConfig(),
        split_cfg or ActionModuleInputSplitContractConfig(),
        reception_cfg or TwoRouteReceptionDryRunConfig(),
        prediction_contract_cfg or GameStructurePredictionInputContractConfig(),
        prediction_envelope_cfg or GameStructurePredictionEnvelopeDryRunConfig(),
    )
    _gk, _mt, pressure_table, _safety, _final12, task12_errors, _task12_summary = build_and_validate_new_gt_upper_layer_revalidation(
        tracking_cfg,
        upper_layer_cfg or NewGtUpperLayerRevalidationConfig(),
    )
    upstream_errors = []
    if cfg.require_task13_ready:
        upstream_errors.extend([f"task2_8j_14_upstream_13_error:{e}" for e in task13_errors])
        upstream_errors.extend([f"task2_8j_14_upstream_11_error:{e}" for e in task11_errors])
        upstream_errors.extend([f"task2_8j_14_upstream_12_error:{e}" for e in task12_errors])
    bundles = build_action_axis_material_bundles(pressure_table, envelopes, cfg)
    source_trace = build_bundle_source_trace_table(bundles)
    checks = build_bundle_checks(bundles, source_trace, upstream_errors, task13_summary)
    final_summary = build_final_summary(bundles, source_trace, checks)
    errors = list(upstream_errors)
    errors.extend(validate_action_axis_material_bundle_dry_run_tables(bundles, source_trace, checks, final_summary))
    summary = {
        "gt_main_map_name": "static_pca_7",
        "gt_main_component_count": 7,
        "task13_decision": task13_summary.get("action_axis_material_contract_decision", ""),
        "material_bundle_count": _safe_int(final_summary["material_bundle_count"].iloc[0]) if not final_summary.empty else 0,
        "source_trace_row_count": _safe_int(final_summary["source_trace_row_count"].iloc[0]) if not final_summary.empty else 0,
        "bundle_check_count": _safe_int(final_summary["bundle_check_count"].iloc[0]) if not final_summary.empty else 0,
        "bundle_check_pass_count": _safe_int(final_summary["bundle_check_pass_count"].iloc[0]) if not final_summary.empty else 0,
        "route_tagged_bundle_count": _safe_int(final_summary["route_tagged_bundle_count"].iloc[0]) if not final_summary.empty else 0,
        "source_trace_preserved_bundle_count": _safe_int(final_summary["source_trace_preserved_bundle_count"].iloc[0]) if not final_summary.empty else 0,
        "no_op_baseline_bundle_count": _safe_int(final_summary["no_op_baseline_bundle_count"].iloc[0]) if not final_summary.empty else 0,
        "release_material_bundle_count": _safe_int(final_summary["release_material_bundle_count"].iloc[0]) if not final_summary.empty else 0,
        "action_axis_material_bundle_dry_run_decision": str(final_summary["action_axis_material_bundle_dry_run_decision"].iloc[0]) if not final_summary.empty else "empty",
        "action_axis_generated": False,
        "action_candidate_generated": False,
        "action_effect_prediction_generated": False,
        "real_actionmodule_called": False,
        "validation_errors": errors,
    }
    return bundles, source_trace, checks, final_summary, errors, summary
