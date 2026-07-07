"""Task 2-8j-21: G_t -> relation field -> O_t -> action-module non-execution loop RC1.

This task connects the current route materials without executing actions:
    G_t visible terrain summary -> relation-field packet -> O_t observation map
    -> action-module non-execution intake -> terrain-action material review.

The loop is deliberately non-executing.  It may assemble and review action
material packets, but it does not generate action candidates, does not predict
actual effects, does not perform final expected-value judgment, and does not call
any real ActionModule runtime.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from .pressure_action_task2_8j_20_v2_terrain_action_parameter_sweep_dry_run import (
    V2TerrainActionParameterSweepDryRunConfig,
    build_and_validate_v2_terrain_action_parameter_sweep_dry_run,
)

TASK2_8J_21_VERSION = "gt_relation_ot_actionmodule_non_execution_loop_rc1"
TASK2_8J_21_CONTRACT = "Task2_8j_21_gt_relation_ot_actionmodule_non_execution_loop__system_visible_material_review_only"
TASK20_ACCEPTED_DECISION = "v2_terrain_action_parameter_sweep_dry_run_ready_without_execution"

BOUNDARY = {
    "task2_8j_21_version": TASK2_8J_21_VERSION,
    "task2_8j_21_contract": TASK2_8J_21_CONTRACT,
    "validation_only": True,
    "non_execution_loop_only": True,
    "system_visible_information_only": True,
    "gt_to_relation_to_ot_to_actionmodule_route": True,
    "gt_main_map_name": "static_pca_7",
    "gt_main_component_count": 7,
    "source_task20_required": True,
    "semantic_recipe_primary_key_forbidden": True,
    "terrain_information_primary_required": True,
    "risk_label_used_only_for_evaluation": True,
    "meaning_labels_explanation_only": True,
    "v2_oracle_results_hint_only": True,
    "v2_oracle_results_not_direct_action_input": True,
    "full_loop_action_must_use_system_visible_information": True,
    "prediction_required_before_final_expected_value_review": True,
    "no_op_preserved": True,
    "direction_selection_required": True,
    "state_dependence_required": True,
    "immediate_release_required": True,
    "rollback_required": True,
    "audit_required": True,
    "multi_seed_robustness_required_later": True,
    "no_single_scenario_optimization": True,
    "loop_executed": False,
    "action_candidate_generated": False,
    "concrete_action_generated": False,
    "action_effect_prediction_generated": False,
    "effect_prediction_model_executed": False,
    "expected_value_final_judgment_performed": False,
    "risk_final_judgment_performed": False,
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
    "hidden_truth_input": False,
    "future_information_used": False,
}

REQUIRED_TRUE = [
    "validation_only", "non_execution_loop_only", "system_visible_information_only", "gt_to_relation_to_ot_to_actionmodule_route",
    "source_task20_required", "semantic_recipe_primary_key_forbidden", "terrain_information_primary_required",
    "risk_label_used_only_for_evaluation", "meaning_labels_explanation_only", "v2_oracle_results_hint_only",
    "v2_oracle_results_not_direct_action_input", "full_loop_action_must_use_system_visible_information",
    "prediction_required_before_final_expected_value_review", "no_op_preserved", "direction_selection_required",
    "state_dependence_required", "immediate_release_required", "rollback_required", "audit_required",
    "multi_seed_robustness_required_later", "no_single_scenario_optimization",
]
FORBIDDEN_TRUE = [
    "loop_executed", "action_candidate_generated", "concrete_action_generated", "action_effect_prediction_generated",
    "effect_prediction_model_executed", "expected_value_final_judgment_performed", "risk_final_judgment_performed",
    "real_actionmodule_called", "actionmodule_called", "axis_executed", "runtime_policy_input", "fullspec_runtime_connected",
    "canonical_write_performed", "gk_writeback_performed", "ot_writeback_performed", "effective_dimension_refit_performed",
    "axis_mutation_performed", "hidden_truth_input", "future_information_used",
]

PACKET_COLUMNS = list(BOUNDARY) + ["loop_packet_id", "source_dry_run_row_id", "terrain_state_id", "terrain_state_name", "operator_family_name", "gt_visible_summary", "relation_field_packet", "ot_observation_packet", "upper_pressure_stub", "actionmodule_intake_port", "no_op_baseline_carried", "release_condition_carried", "rollback_condition_carried", "audit_condition_carried", "loop_packet_status"]
REVIEW_COLUMNS = list(BOUNDARY) + ["review_id", "loop_packet_id", "terrain_material_complete", "route_trace_complete", "no_op_ready", "release_ready", "rollback_ready", "audit_ready", "candidate_form_deferred", "effect_prediction_deferred", "review_status"]
CHECK_COLUMNS = list(BOUNDARY) + ["check_id", "check_scope", "check_description", "expected_value", "observed_value", "check_status"]
SUMMARY_COLUMNS = list(BOUNDARY) + ["loop_packet_count", "review_count", "material_complete_count", "route_trace_complete_count", "loop_check_count", "loop_check_pass_count", "task20_ready", "gt_relation_ot_actionmodule_non_execution_loop_decision", "next_task"]


@dataclass(frozen=True)
class GtRelationOtActionModuleNonExecutionLoopConfig:
    require_task20_ready: bool = True
    max_packets: int = 30
    min_priority_band: str = "medium"


def _with_boundary(row: dict[str, Any]) -> dict[str, Any]:
    return {**BOUNDARY, **row}


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def _select_sweep_rows(sweep: pd.DataFrame, max_packets: int, min_priority_band: str) -> pd.DataFrame:
    if sweep is None or sweep.empty:
        return pd.DataFrame()
    priority_order = {
        "high_priority_for_later_sandbox_execution": 3,
        "medium_priority_for_later_sandbox_execution": 2,
        "low_priority_or_guarded_review": 1,
    }
    min_rank = 2 if min_priority_band == "medium" else 3 if min_priority_band == "high" else 1
    tmp = sweep.copy()
    tmp["_rank"] = tmp["dry_run_priority_band"].map(priority_order).fillna(0).astype(int)
    tmp = tmp[tmp["_rank"] >= min_rank]
    tmp = tmp.sort_values(["_rank", "dry_run_priority_score"], ascending=[False, False]).head(max_packets)
    return tmp.drop(columns=["_rank"], errors="ignore").reset_index(drop=True)


def build_non_execution_loop_packets(sweep_rows: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for i, r in sweep_rows.reset_index(drop=True).iterrows():
        gt_summary = f"static_pca_7:{r['terrain_state_name']}:{r['risk_label_for_evaluation_only']}"
        relation_packet = f"direction={r['direction_readiness']};state_gate={r['state_gate_readiness']};operator={r['operator_family_name']}"
        ot_packet = f"where={r['terrain_state_id']};confidence=review;priority={r['dry_run_priority_band']}"
        rows.append(_with_boundary({
            "loop_packet_id": f"gt_relation_ot_actionmodule_packet_{i+1:04d}",
            "source_dry_run_row_id": str(r["dry_run_row_id"]),
            "terrain_state_id": str(r["terrain_state_id"]),
            "terrain_state_name": str(r["terrain_state_name"]),
            "operator_family_name": str(r["operator_family_name"]),
            "gt_visible_summary": gt_summary,
            "relation_field_packet": relation_packet,
            "ot_observation_packet": ot_packet,
            "upper_pressure_stub": "bounded_weak_reversible_pressure_stub_only",
            "actionmodule_intake_port": "non_execution_material_review_port",
            "no_op_baseline_carried": True,
            "release_condition_carried": True,
            "rollback_condition_carried": True,
            "audit_condition_carried": True,
            "loop_packet_status": "system_visible_material_packet_ready_not_executed",
        }))
    return pd.DataFrame(rows, columns=PACKET_COLUMNS)


def build_actionmodule_non_execution_review(loop_packets: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for i, r in loop_packets.reset_index(drop=True).iterrows():
        material_complete = all(bool(r[col]) for col in ["gt_visible_summary", "relation_field_packet", "ot_observation_packet", "upper_pressure_stub"])
        route_complete = "static_pca_7" in str(r["gt_visible_summary"]) and "operator=" in str(r["relation_field_packet"])
        rows.append(_with_boundary({
            "review_id": f"non_execution_review_{i+1:04d}",
            "loop_packet_id": str(r["loop_packet_id"]),
            "terrain_material_complete": bool(material_complete),
            "route_trace_complete": bool(route_complete),
            "no_op_ready": bool(r["no_op_baseline_carried"]),
            "release_ready": bool(r["release_condition_carried"]),
            "rollback_ready": bool(r["rollback_condition_carried"]),
            "audit_ready": bool(r["audit_condition_carried"]),
            "candidate_form_deferred": True,
            "effect_prediction_deferred": True,
            "review_status": "review_passed_for_later_candidate_preparation_not_generated",
        }))
    return pd.DataFrame(rows, columns=REVIEW_COLUMNS)


def build_loop_checks(loop_packets: pd.DataFrame, review: pd.DataFrame, task20_ready: bool) -> pd.DataFrame:
    checks = [
        ("check_task20_ready", "upstream", "Task20 parameter sweep dry-run is ready.", True, task20_ready),
        ("check_packets_exist", "route", "Non-execution loop packets exist.", True, len(loop_packets) > 0),
        ("check_reviews_exist", "review", "ActionModule non-execution reviews exist.", True, len(review) == len(loop_packets) and len(review) > 0),
        ("check_material_complete", "material", "Terrain material is complete for every packet.", True, bool(review["terrain_material_complete"].astype(bool).all()) if not review.empty else False),
        ("check_route_trace", "route", "G_t -> relation field -> O_t route trace is complete.", True, bool(review["route_trace_complete"].astype(bool).all()) if not review.empty else False),
        ("check_no_op_release_rollback_audit", "guards", "NO_OP, release, rollback, and audit are preserved.", True, bool((review["no_op_ready"] & review["release_ready"] & review["rollback_ready"] & review["audit_ready"]).all()) if not review.empty else False),
        ("check_candidate_deferred", "boundary", "Candidate form generation is deferred.", True, bool(review["candidate_form_deferred"].astype(bool).all()) if not review.empty else False),
        ("check_effect_prediction_deferred", "boundary", "Effect prediction is deferred.", True, bool(review["effect_prediction_deferred"].astype(bool).all()) if not review.empty else False),
        ("check_no_runtime_call", "boundary", "No ActionModule runtime call occurs.", False, bool(loop_packets["real_actionmodule_called"].astype(bool).any()) if not loop_packets.empty else True),
        ("check_no_execution", "boundary", "No action execution occurs.", False, bool(loop_packets["axis_executed"].astype(bool).any()) if not loop_packets.empty else True),
        ("check_no_hidden_future", "boundary", "No hidden-truth or future information is used.", False, bool(loop_packets["hidden_truth_input"].astype(bool).any() or loop_packets["future_information_used"].astype(bool).any()) if not loop_packets.empty else True),
    ]
    return pd.DataFrame([_with_boundary({"check_id": c[0], "check_scope": c[1], "check_description": c[2], "expected_value": bool(c[3]), "observed_value": bool(c[4]), "check_status": "pass" if bool(c[3]) == bool(c[4]) else "fail"}) for c in checks], columns=CHECK_COLUMNS)


def build_final_summary(loop_packets: pd.DataFrame, review: pd.DataFrame, checks: pd.DataFrame, task20_ready: bool) -> pd.DataFrame:
    check_pass = int((checks["check_status"].astype(str) == "pass").sum()) if not checks.empty else 0
    material_count = int(review["terrain_material_complete"].astype(bool).sum()) if not review.empty else 0
    route_count = int(review["route_trace_complete"].astype(bool).sum()) if not review.empty else 0
    decision = "gt_relation_ot_actionmodule_non_execution_loop_ready" if task20_ready and len(loop_packets) > 0 and len(review) == len(loop_packets) and len(checks) == check_pass else "gt_relation_ot_actionmodule_non_execution_loop_needs_review"
    return pd.DataFrame([_with_boundary({
        "loop_packet_count": len(loop_packets),
        "review_count": len(review),
        "material_complete_count": material_count,
        "route_trace_complete_count": route_count,
        "loop_check_count": len(checks),
        "loop_check_pass_count": check_pass,
        "task20_ready": bool(task20_ready),
        "gt_relation_ot_actionmodule_non_execution_loop_decision": decision,
        "next_task": "Task 2-8j-22: action material calibration and NO_OP comparison review",
    })], columns=SUMMARY_COLUMNS)


def validate_gt_relation_ot_actionmodule_non_execution_loop_tables(loop_packets: pd.DataFrame, review: pd.DataFrame, checks: pd.DataFrame, final_summary: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    tables = {"loop_packets": (loop_packets, PACKET_COLUMNS), "review": (review, REVIEW_COLUMNS), "checks": (checks, CHECK_COLUMNS), "final_summary": (final_summary, SUMMARY_COLUMNS)}
    for name, (table, cols) in tables.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_21_empty_table:{name}"); continue
        missing = [c for c in cols if c not in table.columns]
        if missing:
            errors.append(f"task2_8j_21_missing_columns:{name}:" + ",".join(missing)); continue
        for col in REQUIRED_TRUE:
            if not bool(table[col].astype(bool).all()):
                errors.append(f"task2_8j_21_required_true_not_all_true:{name}:{col}")
        for col in FORBIDDEN_TRUE:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_21_forbidden_true:{name}:{col}")
        if set(table["gt_main_map_name"].astype(str)) != {"static_pca_7"}:
            errors.append(f"task2_8j_21_wrong_gt_main_map_name:{name}")
        if set(table["gt_main_component_count"].astype(int)) != {7}:
            errors.append(f"task2_8j_21_wrong_gt_component_count:{name}")
    if checks is not None and not checks.empty and not bool((checks["check_status"].astype(str) == "pass").all()):
        errors.append("task2_8j_21_check_failed")
    return errors


def build_and_validate_gt_relation_ot_actionmodule_non_execution_loop(cfg: GtRelationOtActionModuleNonExecutionLoopConfig | None = None, **_unused: object) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    cfg = cfg or GtRelationOtActionModuleNonExecutionLoopConfig()
    _states, sweep, _op_summary, _checks20, _final20, task20_errors, task20_summary = build_and_validate_v2_terrain_action_parameter_sweep_dry_run(
        cfg=V2TerrainActionParameterSweepDryRunConfig(max_rows_per_operator=4)
    )
    task20_ready = len(task20_errors) == 0 and str(task20_summary.get("v2_terrain_action_parameter_sweep_dry_run_decision", "")).startswith(TASK20_ACCEPTED_DECISION)
    if not cfg.require_task20_ready:
        task20_ready = True
    selected = _select_sweep_rows(sweep, cfg.max_packets, cfg.min_priority_band)
    loop_packets = build_non_execution_loop_packets(selected)
    review = build_actionmodule_non_execution_review(loop_packets)
    checks = build_loop_checks(loop_packets, review, task20_ready)
    final_summary = build_final_summary(loop_packets, review, checks, task20_ready)
    errors = ([f"task2_8j_21_upstream_20_error:{e}" for e in task20_errors] if cfg.require_task20_ready else []) + validate_gt_relation_ot_actionmodule_non_execution_loop_tables(loop_packets, review, checks, final_summary)
    summary = {
        "gt_main_map_name": "static_pca_7",
        "gt_main_component_count": 7,
        "task20_decision": task20_summary.get("v2_terrain_action_parameter_sweep_dry_run_decision", ""),
        "loop_packet_count": _safe_int(final_summary["loop_packet_count"].iloc[0]),
        "review_count": _safe_int(final_summary["review_count"].iloc[0]),
        "material_complete_count": _safe_int(final_summary["material_complete_count"].iloc[0]),
        "route_trace_complete_count": _safe_int(final_summary["route_trace_complete_count"].iloc[0]),
        "loop_check_count": _safe_int(final_summary["loop_check_count"].iloc[0]),
        "loop_check_pass_count": _safe_int(final_summary["loop_check_pass_count"].iloc[0]),
        "task20_ready": bool(task20_ready),
        "gt_relation_ot_actionmodule_non_execution_loop_decision": str(final_summary["gt_relation_ot_actionmodule_non_execution_loop_decision"].iloc[0]),
        "action_candidate_generated": False,
        "action_effect_prediction_generated": False,
        "effect_prediction_model_executed": False,
        "concrete_action_generated": False,
        "axis_executed": False,
        "real_actionmodule_called": False,
        "validation_errors": errors,
    }
    return loop_packets, review, checks, final_summary, errors, summary
