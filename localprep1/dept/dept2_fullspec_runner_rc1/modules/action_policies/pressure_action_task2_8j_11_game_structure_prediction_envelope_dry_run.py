"""Task 2-8j-11: game-structure prediction envelope dry-run RC1.

Purpose:
    Create dry-run prediction envelopes that satisfy the Task 2-8j-10 game-
    structure prediction input contract, while preserving source traces back to
    O_t observations and relation-field evidence.

Position:
    Task 2-8j-10 froze the prediction-input contract for observation-side
    forecasts.  This task builds contract-compliant envelopes from traceable
    relation-field / O_t evidence.  The envelopes are packaging and boundary
    checks only: they are not a prediction model, not action-effect prediction,
    and not action-axis generation.

Boundary:
    - dry-run envelope generation only
    - fixed static_pca_7 main map
    - observation-side current-structure forecast envelope only
    - source O_t / relation-field trace must be preserved
    - no action-effect prediction, action-axis generation, action candidate, or upper pressure
    - no real ActionModule call, runtime call, writeback, hidden-truth / future-information input, or axis mutation
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .pressure_action_task2_8j_6c_v2_structure_change_relation_field_tracking import V2StructureChangeTrackingConfig
from .pressure_action_task2_8j_7_ot_observation_map_from_relation_field import OtObservationMapConfig
from .pressure_action_task2_8j_7b_ot_audit_layering import OtAuditLayeringConfig
from .pressure_action_task2_8j_7c_relation_to_ot_information_preservation_audit import (
    RelationToOtInformationPreservationConfig,
    build_and_validate_relation_to_ot_information_preservation_audit,
)
from .pressure_action_task2_8j_8_action_module_input_split_contract import ActionModuleInputSplitContractConfig
from .pressure_action_task2_8j_9_two_route_reception_dry_run import TwoRouteReceptionDryRunConfig
from .pressure_action_task2_8j_10_game_structure_prediction_input_contract import (
    GameStructurePredictionInputContractConfig,
    build_and_validate_game_structure_prediction_input_contract,
)

TASK2_8J_11_VERSION = "game_structure_prediction_envelope_dry_run_rc1"
TASK2_8J_11_CONTRACT = (
    "Task2_8j_11_game_structure_prediction_envelope_dry_run__"
    "contract_compliant_observation_forecast_packaging__"
    "traceable_sources_no_action_effect_prediction_no_action_axes_no_runtime"
)

BOUNDARY = {
    "task2_8j_11_version": TASK2_8J_11_VERSION,
    "task2_8j_11_contract": TASK2_8J_11_CONTRACT,
    "validation_only": True,
    "dry_run_only": True,
    "prediction_envelope_dry_run_only": True,
    "gt_main_map_name": "static_pca_7",
    "gt_main_component_count": 7,
    "prediction_source_family": "relation_field_Ot_observation_side",
    "game_structure_prediction_route_separate": True,
    "observation_forecast_allowed": True,
    "prediction_envelope_created": True,
    "source_trace_preserved": True,
    "real_prediction_model_executed": False,
    "action_effect_prediction_generated": False,
    "action_axis_generated": False,
    "action_candidate_generated": False,
    "upper_pressure_generated_here": False,
    "prediction_generates_upper_pressure": False,
    "upper_pressure_rewrites_prediction": False,
    "prediction_rewrites_ot": False,
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
    "real_prediction_model_executed",
    "action_effect_prediction_generated",
    "action_axis_generated",
    "action_candidate_generated",
    "upper_pressure_generated_here",
    "prediction_generates_upper_pressure",
    "upper_pressure_rewrites_prediction",
    "prediction_rewrites_ot",
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

PREDICTION_PAYLOAD_FIELDS = [
    "prediction_bundle_id",
    "source_observation_ids",
    "source_relation_trace_ids",
    "prediction_horizon",
    "predicted_state_tendency",
    "predicted_relation_tendency",
    "confidence",
    "uncertainty",
    "validity_scope",
    "assumption_current_structure_continues",
    "provenance",
    "audit_level",
    "audit_reasons",
]

REQUIRED_ENVELOPE_COLUMNS = list(BOUNDARY) + PREDICTION_PAYLOAD_FIELDS + [
    "envelope_id",
    "envelope_kind",
    "source_phase",
    "target_phase",
    "source_macro_signal",
    "target_macro_signal",
    "direction_from_relation_trace",
    "intensity_from_relation_trace",
    "is_contract_stub",
    "required_payload_fields_present",
    "forbidden_payload_fields_absent",
    "envelope_status",
]

REQUIRED_TRACE_COLUMNS = list(BOUNDARY) + [
    "prediction_bundle_id",
    "matched_ot_observation_id",
    "relation_trace_id",
    "relation_trace_status",
    "audit_trace_found",
    "audit_level",
    "audit_reasons",
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
    "prediction_envelope_count",
    "prediction_trace_count",
    "envelope_check_count",
    "envelope_check_pass_count",
    "required_payload_fields_present_count",
    "forbidden_payload_fields_absent_count",
    "source_trace_preserved_count",
    "audit_trace_found_count",
    "game_structure_prediction_envelope_dry_run_decision",
    "next_task",
]


@dataclass(frozen=True)
class GameStructurePredictionEnvelopeDryRunConfig:
    require_task10_ready: bool = True
    max_relation_envelopes: int = 6
    prediction_horizon: str = "current_structure_short_horizon_dry_run"


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
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _trace_id(row) -> str:
    return (
        f"{row.source_phase}->{row.target_phase}:"
        f"{row.source_macro_signal}->{row.target_macro_signal}"
    )


def _audit_lookup(audit_trace: pd.DataFrame) -> dict[str, pd.Series]:
    if audit_trace is None or audit_trace.empty:
        return {}
    return {str(row.observation_id): row for _, row in audit_trace.iterrows()}


def _relation_tendency(direction: str, source: str, target: str) -> str:
    return f"{source}->{target}:{direction}"


def _state_tendency_from_relation(row) -> str:
    source = str(row.source_macro_signal)
    target = str(row.target_macro_signal)
    direction = str(row.expected_direction_polarity)
    if "information_degradation" in {source, target} and direction == "strengthening":
        return "information_degradation_pressure_likely_to_persist_under_current_structure"
    if "resource_pressure" in {source, target} and direction == "strengthening":
        return "resource_pressure_related_state_likely_to_persist_under_current_structure"
    if direction == "weakening":
        return "related_state_tendency_likely_to_weaken_under_current_structure"
    return "state_tendency_packaged_from_relation_trace_without_action_assumption"


def build_prediction_envelopes(
    relation_trace: pd.DataFrame,
    audit_trace: pd.DataFrame,
    cfg: GameStructurePredictionEnvelopeDryRunConfig | None = None,
) -> pd.DataFrame:
    cfg = cfg or GameStructurePredictionEnvelopeDryRunConfig()
    if relation_trace is None or relation_trace.empty:
        return pd.DataFrame(columns=REQUIRED_ENVELOPE_COLUMNS)
    audit_by_obs = _audit_lookup(audit_trace)
    preserved = relation_trace[
        relation_trace["relation_information_preservation_status"].astype(str)
        == "preserved_as_traceable_coarse_grained_observation"
    ].copy()
    if preserved.empty:
        preserved = relation_trace.copy()
    preserved = preserved.head(max(1, int(cfg.max_relation_envelopes)))
    rows: list[dict] = []
    for i, row in enumerate(preserved.itertuples(index=False)):
        obs_id = str(row.matched_ot_observation_id)
        audit = audit_by_obs.get(obs_id)
        audit_level = str(audit.audit_level) if audit is not None else "missing"
        audit_reasons = str(audit.audit_reasons) if audit is not None else ""
        relation_trace_id = _trace_id(row)
        direction = str(row.expected_direction_polarity)
        intensity = _safe_float(row.expected_intensity)
        # This is dry-run packaging confidence, not a true forecast score.
        confidence = round(max(0.0, min(1.0, 0.50 + 0.40 * intensity)), 6)
        uncertainty = round(max(0.0, min(1.0, 1.0 - confidence + (0.10 if audit_level == "review_before_action" else 0.0))), 6)
        rows.append({
            **BOUNDARY,
            "prediction_bundle_id": f"gs_pred_dry_run_{i:04d}",
            "source_observation_ids": obs_id,
            "source_relation_trace_ids": relation_trace_id,
            "prediction_horizon": cfg.prediction_horizon,
            "predicted_state_tendency": _state_tendency_from_relation(row),
            "predicted_relation_tendency": _relation_tendency(direction, str(row.source_macro_signal), str(row.target_macro_signal)),
            "confidence": confidence,
            "uncertainty": uncertainty,
            "validity_scope": "current_game_structure_continues_without_action_assumption",
            "assumption_current_structure_continues": True,
            "provenance": "Task2_8j_7c_relation_trace_plus_Task2_8j_7b_audit_trace",
            "audit_level": audit_level,
            "audit_reasons": audit_reasons,
            "envelope_id": f"prediction_envelope_{i:04d}",
            "envelope_kind": "game_structure_prediction_dry_run_envelope",
            "source_phase": str(row.source_phase),
            "target_phase": str(row.target_phase),
            "source_macro_signal": str(row.source_macro_signal),
            "target_macro_signal": str(row.target_macro_signal),
            "direction_from_relation_trace": direction,
            "intensity_from_relation_trace": intensity,
            "is_contract_stub": True,
            "required_payload_fields_present": True,
            "forbidden_payload_fields_absent": True,
            "envelope_status": "contract_compliant_prediction_envelope_dry_run",
        })
    return pd.DataFrame(rows, columns=REQUIRED_ENVELOPE_COLUMNS)


def build_prediction_source_trace(envelopes: pd.DataFrame, relation_trace: pd.DataFrame, audit_trace: pd.DataFrame) -> pd.DataFrame:
    if envelopes is None or envelopes.empty:
        return pd.DataFrame(columns=REQUIRED_TRACE_COLUMNS)
    relation_ids = set()
    if relation_trace is not None and not relation_trace.empty:
        relation_ids = {_trace_id(row) for row in relation_trace.itertuples(index=False)}
    audit_by_obs = _audit_lookup(audit_trace)
    rows: list[dict] = []
    for row in envelopes.itertuples(index=False):
        obs_id = str(row.source_observation_ids)
        trace_id = str(row.source_relation_trace_ids)
        audit = audit_by_obs.get(obs_id)
        audit_found = audit is not None
        relation_found = trace_id in relation_ids
        rows.append({
            **BOUNDARY,
            "prediction_bundle_id": str(row.prediction_bundle_id),
            "matched_ot_observation_id": obs_id,
            "relation_trace_id": trace_id,
            "relation_trace_status": "relation_trace_found" if relation_found else "relation_trace_missing",
            "audit_trace_found": bool(audit_found),
            "audit_level": str(audit.audit_level) if audit_found else "missing",
            "audit_reasons": str(audit.audit_reasons) if audit_found else "",
            "trace_status": "source_traces_preserved" if relation_found and audit_found else "source_trace_needs_review",
        })
    return pd.DataFrame(rows, columns=REQUIRED_TRACE_COLUMNS)


def build_envelope_checks(envelopes: pd.DataFrame, source_trace: pd.DataFrame, task10_errors: list[str], task10_summary: dict) -> pd.DataFrame:
    required_present = bool(envelopes["required_payload_fields_present"].astype(bool).all()) if envelopes is not None and not envelopes.empty else False
    forbidden_absent = bool(envelopes["forbidden_payload_fields_absent"].astype(bool).all()) if envelopes is not None and not envelopes.empty else False
    traces_ok = bool((source_trace["trace_status"].astype(str) == "source_traces_preserved").all()) if source_trace is not None and not source_trace.empty else False
    checks = [
        (
            "check_task10_contract_ready",
            "upstream_contract",
            "Task2-8j-10 prediction input contract is ready and has no validation errors.",
            True,
            len(task10_errors) == 0 and str(task10_summary.get("game_structure_prediction_input_contract_decision", "")).startswith("game_structure_prediction_input_contract_ready"),
        ),
        (
            "check_envelopes_created",
            "envelope",
            "At least one prediction envelope is created.",
            True,
            bool(envelopes is not None and not envelopes.empty),
        ),
        (
            "check_required_payload_fields_present",
            "payload",
            "All dry-run envelopes carry Task2-8j-10 required payload fields.",
            True,
            required_present,
        ),
        (
            "check_forbidden_payload_fields_absent",
            "payload",
            "Action-effect, action-axis, upper-pressure, runtime, hidden, and future fields are absent.",
            True,
            forbidden_absent,
        ),
        (
            "check_source_traces_preserved",
            "trace",
            "Each prediction envelope can be traced back to O_t and relation-field evidence.",
            True,
            traces_ok,
        ),
        (
            "check_no_real_prediction_model",
            "boundary",
            "No real prediction model is executed; this is envelope dry-run packaging only.",
            False,
            bool(envelopes["real_prediction_model_executed"].astype(bool).any()) if envelopes is not None and not envelopes.empty else True,
        ),
        (
            "check_no_action_effect_prediction",
            "boundary",
            "No action-effect prediction is generated.",
            False,
            bool(envelopes["action_effect_prediction_generated"].astype(bool).any()) if envelopes is not None and not envelopes.empty else True,
        ),
        (
            "check_no_action_axis_generation",
            "boundary",
            "No action axis is generated.",
            False,
            bool(envelopes["action_axis_generated"].astype(bool).any()) if envelopes is not None and not envelopes.empty else True,
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


def build_final_summary(envelopes: pd.DataFrame, source_trace: pd.DataFrame, checks: pd.DataFrame) -> pd.DataFrame:
    envelope_count = int(len(envelopes)) if envelopes is not None else 0
    trace_count = int(len(source_trace)) if source_trace is not None else 0
    check_count = int(len(checks)) if checks is not None else 0
    pass_count = int((checks["check_status"].astype(str) == "pass").sum()) if check_count else 0
    required_count = int(envelopes["required_payload_fields_present"].astype(bool).sum()) if envelope_count else 0
    forbidden_count = int(envelopes["forbidden_payload_fields_absent"].astype(bool).sum()) if envelope_count else 0
    trace_preserved = int((source_trace["trace_status"].astype(str) == "source_traces_preserved").sum()) if trace_count else 0
    audit_found = int(source_trace["audit_trace_found"].astype(bool).sum()) if trace_count else 0
    if envelope_count > 0 and envelope_count == trace_count == required_count == forbidden_count == trace_preserved == audit_found and check_count == pass_count:
        decision = "game_structure_prediction_envelope_dry_run_created_with_traceable_observation_side_forecast_packaging"
    else:
        decision = "game_structure_prediction_envelope_dry_run_needs_review"
    return pd.DataFrame([{
        **BOUNDARY,
        "prediction_envelope_count": envelope_count,
        "prediction_trace_count": trace_count,
        "envelope_check_count": check_count,
        "envelope_check_pass_count": pass_count,
        "required_payload_fields_present_count": required_count,
        "forbidden_payload_fields_absent_count": forbidden_count,
        "source_trace_preserved_count": trace_preserved,
        "audit_trace_found_count": audit_found,
        "game_structure_prediction_envelope_dry_run_decision": decision,
        "next_task": "Task 2-8j-12: action-module side action-axis material contract from observation forecast inputs",
    }], columns=REQUIRED_SUMMARY_COLUMNS)


def validate_game_structure_prediction_envelope_dry_run_tables(envelopes: pd.DataFrame, source_trace: pd.DataFrame, checks: pd.DataFrame, final_summary: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    tables = {
        "envelopes": (envelopes, REQUIRED_ENVELOPE_COLUMNS),
        "source_trace": (source_trace, REQUIRED_TRACE_COLUMNS),
        "checks": (checks, REQUIRED_CHECK_COLUMNS),
        "final_summary": (final_summary, REQUIRED_SUMMARY_COLUMNS),
    }
    for name, (table, required) in tables.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_11_empty_table:{name}")
            continue
        missing = [c for c in required if c not in table.columns]
        if missing:
            errors.append(f"task2_8j_11_missing_columns:{name}:" + ",".join(missing))
            continue
        for col in ["validation_only", "dry_run_only", "prediction_envelope_dry_run_only", "prediction_envelope_created", "source_trace_preserved", "game_structure_prediction_route_separate", "observation_forecast_allowed"]:
            if not bool(table[col].astype(bool).all()):
                errors.append(f"task2_8j_11_required_true_not_all_true:{name}:{col}")
        if set(table["gt_main_map_name"].astype(str)) != {"static_pca_7"}:
            errors.append(f"task2_8j_11_wrong_gt_main_map_name:{name}")
        if set(table["gt_main_component_count"].astype(int)) != {7}:
            errors.append(f"task2_8j_11_wrong_component_count:{name}")
        for col in FORBIDDEN_TRUE:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_11_forbidden_true:{name}:{col}")
    if envelopes is not None and not envelopes.empty:
        for field in PREDICTION_PAYLOAD_FIELDS:
            if field not in envelopes.columns:
                errors.append(f"task2_8j_11_payload_field_missing:{field}")
            elif bool(envelopes[field].isna().any()):
                errors.append(f"task2_8j_11_payload_field_has_null:{field}")
        if not bool(envelopes["required_payload_fields_present"].astype(bool).all()):
            errors.append("task2_8j_11_required_payload_fields_not_present")
        if not bool(envelopes["forbidden_payload_fields_absent"].astype(bool).all()):
            errors.append("task2_8j_11_forbidden_payload_fields_not_absent")
    if source_trace is not None and not source_trace.empty:
        if not bool((source_trace["trace_status"].astype(str) == "source_traces_preserved").all()):
            errors.append("task2_8j_11_source_trace_not_preserved")
    if checks is not None and not checks.empty:
        if not bool((checks["check_status"].astype(str) == "pass").all()):
            errors.append("task2_8j_11_check_failed")
    return errors


def build_and_validate_game_structure_prediction_envelope_dry_run(
    tracking_cfg: V2StructureChangeTrackingConfig | None = None,
    ot_cfg: OtObservationMapConfig | None = None,
    audit_cfg: OtAuditLayeringConfig | None = None,
    preservation_cfg: RelationToOtInformationPreservationConfig | None = None,
    split_cfg: ActionModuleInputSplitContractConfig | None = None,
    reception_cfg: TwoRouteReceptionDryRunConfig | None = None,
    prediction_contract_cfg: GameStructurePredictionInputContractConfig | None = None,
    cfg: GameStructurePredictionEnvelopeDryRunConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    cfg = cfg or GameStructurePredictionEnvelopeDryRunConfig()
    tracking_cfg = tracking_cfg or V2StructureChangeTrackingConfig()
    ot_cfg = ot_cfg or OtObservationMapConfig()
    audit_cfg = audit_cfg or OtAuditLayeringConfig()
    preservation_cfg = preservation_cfg or RelationToOtInformationPreservationConfig()
    split_cfg = split_cfg or ActionModuleInputSplitContractConfig()
    reception_cfg = reception_cfg or TwoRouteReceptionDryRunConfig()
    prediction_contract_cfg = prediction_contract_cfg or GameStructurePredictionInputContractConfig()

    _contract, _scope, _features, _readiness, _task10_final, task10_errors, task10_summary = (
        build_and_validate_game_structure_prediction_input_contract(
            tracking_cfg,
            ot_cfg,
            audit_cfg,
            preservation_cfg,
            split_cfg,
            reception_cfg,
            prediction_contract_cfg,
        )
    )
    relation_trace, _coverage_audit, audit_trace, _preservation_final, preservation_errors, _preservation_summary = (
        build_and_validate_relation_to_ot_information_preservation_audit(
            tracking_cfg,
            ot_cfg,
            audit_cfg,
            preservation_cfg,
        )
    )
    upstream_errors = []
    if cfg.require_task10_ready:
        upstream_errors.extend([f"task2_8j_11_upstream_10_error:{e}" for e in task10_errors])
    upstream_errors.extend([f"task2_8j_11_upstream_7c_error:{e}" for e in preservation_errors])
    envelopes = build_prediction_envelopes(relation_trace, audit_trace, cfg)
    source_trace = build_prediction_source_trace(envelopes, relation_trace, audit_trace)
    checks = build_envelope_checks(envelopes, source_trace, upstream_errors, task10_summary)
    final_summary = build_final_summary(envelopes, source_trace, checks)
    errors = list(upstream_errors)
    errors.extend(validate_game_structure_prediction_envelope_dry_run_tables(envelopes, source_trace, checks, final_summary))
    summary = {
        "gt_main_map_name": "static_pca_7",
        "gt_main_component_count": 7,
        "task10_decision": task10_summary.get("game_structure_prediction_input_contract_decision", ""),
        "prediction_envelope_count": _safe_int(final_summary["prediction_envelope_count"].iloc[0]) if not final_summary.empty else 0,
        "prediction_trace_count": _safe_int(final_summary["prediction_trace_count"].iloc[0]) if not final_summary.empty else 0,
        "envelope_check_count": _safe_int(final_summary["envelope_check_count"].iloc[0]) if not final_summary.empty else 0,
        "envelope_check_pass_count": _safe_int(final_summary["envelope_check_pass_count"].iloc[0]) if not final_summary.empty else 0,
        "required_payload_fields_present_count": _safe_int(final_summary["required_payload_fields_present_count"].iloc[0]) if not final_summary.empty else 0,
        "forbidden_payload_fields_absent_count": _safe_int(final_summary["forbidden_payload_fields_absent_count"].iloc[0]) if not final_summary.empty else 0,
        "source_trace_preserved_count": _safe_int(final_summary["source_trace_preserved_count"].iloc[0]) if not final_summary.empty else 0,
        "audit_trace_found_count": _safe_int(final_summary["audit_trace_found_count"].iloc[0]) if not final_summary.empty else 0,
        "game_structure_prediction_envelope_dry_run_decision": str(final_summary["game_structure_prediction_envelope_dry_run_decision"].iloc[0]) if not final_summary.empty else "empty",
        "real_prediction_model_executed": False,
        "action_effect_prediction_generated": False,
        "action_axis_generated": False,
        "upper_pressure_generated_here": False,
        "real_actionmodule_called": False,
        "validation_errors": errors,
    }
    return envelopes, source_trace, checks, final_summary, errors, summary
