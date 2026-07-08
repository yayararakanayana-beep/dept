"""Task 2-8j-20: v2 terrain-action sandbox parameter sweep dry-run RC1.

Non-executing dry-run over the Task 2-8j-19 terrain-action sandbox design.
It creates terrain-state prototypes, balances operator x parameter coverage, and
computes readiness / priority diagnostics. The priority score is not an effect
prediction and not a final expected-value judgment.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Any

import pandas as pd

from .pressure_action_task2_8j_19_v2_terrain_action_sandbox_design import (
    V2TerrainActionSandboxDesignConfig,
    build_and_validate_v2_terrain_action_sandbox_design,
)

TASK2_8J_20_VERSION = "v2_terrain_action_parameter_sweep_dry_run_rc1"
TASK2_8J_20_CONTRACT = "Task2_8j_20_v2_terrain_action_parameter_sweep_dry_run__diagnostic_only_no_execution"
TASK19_ACCEPTED_DECISION = "v2_terrain_action_sandbox_design_ready_without_execution"

BOUNDARY = {
    "task2_8j_20_version": TASK2_8J_20_VERSION,
    "task2_8j_20_contract": TASK2_8J_20_CONTRACT,
    "validation_only": True,
    "sweep_dry_run_only": True,
    "readiness_priority_diagnostic_only": True,
    "v2_terrain_action_sandbox_only": True,
    "gt_main_map_name": "static_pca_7",
    "gt_main_component_count": 7,
    "source_task19_required": True,
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
    "sandbox_executed": False,
    "terrain_sandbox_executed": False,
    "terrain_operator_applied": False,
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
    "validation_only", "sweep_dry_run_only", "readiness_priority_diagnostic_only", "v2_terrain_action_sandbox_only",
    "source_task19_required", "semantic_recipe_primary_key_forbidden", "terrain_information_primary_required",
    "risk_label_used_only_for_evaluation", "meaning_labels_explanation_only", "v2_oracle_results_hint_only",
    "v2_oracle_results_not_direct_action_input", "full_loop_action_must_use_system_visible_information",
    "prediction_required_before_final_expected_value_review", "no_op_preserved", "direction_selection_required",
    "state_dependence_required", "immediate_release_required", "rollback_required", "audit_required",
    "multi_seed_robustness_required_later", "no_single_scenario_optimization",
]
FORBIDDEN_TRUE = [
    "sandbox_executed", "terrain_sandbox_executed", "terrain_operator_applied", "action_candidate_generated",
    "concrete_action_generated", "action_effect_prediction_generated", "effect_prediction_model_executed",
    "expected_value_final_judgment_performed", "risk_final_judgment_performed", "real_actionmodule_called",
    "actionmodule_called", "axis_executed", "runtime_policy_input", "fullspec_runtime_connected",
    "canonical_write_performed", "gk_writeback_performed", "ot_writeback_performed", "effective_dimension_refit_performed",
    "axis_mutation_performed", "hidden_truth_input", "future_information_used",
]

TERRAIN_STATE_COLUMNS = list(BOUNDARY) + ["terrain_state_id", "terrain_state_name", "risk_label_for_evaluation_only", "direction_clarity", "pressure_gradient", "reversibility", "uncertainty", "boundary_distance", "flow_velocity", "curvature", "neighbor_capacity", "state_status"]
DRY_RUN_COLUMNS = list(BOUNDARY) + ["dry_run_row_id", "terrain_state_id", "terrain_state_name", "risk_label_for_evaluation_only", "operator_family_name", "strength_band", "duration_band", "trigger_band", "release_band", "rollback_sensitivity_band", "audit_strictness_band", "precision_requirement_band", "direction_readiness", "state_gate_readiness", "release_readiness", "rollback_readiness", "audit_readiness", "no_op_comparison_readiness", "side_effect_caution", "overfit_caution", "dry_run_priority_score", "dry_run_priority_band", "dry_run_status"]
OPERATOR_SUMMARY_COLUMNS = list(BOUNDARY) + ["operator_family_name", "dry_run_row_count", "mean_priority_score", "max_priority_score", "high_priority_row_count", "operator_coverage_status"]
CHECK_COLUMNS = list(BOUNDARY) + ["check_id", "check_scope", "check_description", "expected_value", "observed_value", "check_status"]
FINAL_SUMMARY_COLUMNS = list(BOUNDARY) + ["terrain_state_count", "dry_run_row_count", "operator_summary_count", "high_priority_row_count", "sweep_check_count", "sweep_check_pass_count", "task19_ready", "v2_terrain_action_parameter_sweep_dry_run_decision", "next_task"]


@dataclass(frozen=True)
class V2TerrainActionParameterSweepDryRunConfig:
    require_task19_ready: bool = True
    max_rows_per_operator: int = 6


def _with_boundary(row: dict[str, Any]) -> dict[str, Any]:
    return {**BOUNDARY, **row}


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def build_v2_terrain_state_prototypes() -> pd.DataFrame:
    rows = [
        ("state_01_lock_basin", "lock_basin", "relation_lock", 0.78, 0.82, 0.34, 0.35, 0.41, 0.44, 0.72, 0.31),
        ("state_02_pressure_spike", "pressure_spike", "resource_pressure", 0.67, 0.91, 0.48, 0.42, 0.33, 0.51, 0.64, 0.56),
        ("state_03_steep_gradient", "steep_gradient", "coordination_lag", 0.72, 0.69, 0.55, 0.31, 0.45, 0.68, 0.88, 0.62),
        ("state_04_oscillatory_flow", "oscillatory_flow", "instability", 0.63, 0.47, 0.61, 0.50, 0.58, 0.92, 0.83, 0.71),
        ("state_05_boundary_fragile", "boundary_fragile", "shock_boundary", 0.57, 0.66, 0.39, 0.48, 0.22, 0.39, 0.59, 0.44),
        ("state_06_reversibility_thin", "reversibility_thin", "reversibility_loss", 0.69, 0.58, 0.24, 0.37, 0.38, 0.46, 0.53, 0.49),
    ]
    return pd.DataFrame([_with_boundary({
        "terrain_state_id": r[0], "terrain_state_name": r[1], "risk_label_for_evaluation_only": r[2],
        "direction_clarity": r[3], "pressure_gradient": r[4], "reversibility": r[5], "uncertainty": r[6],
        "boundary_distance": r[7], "flow_velocity": r[8], "curvature": r[9], "neighbor_capacity": r[10],
        "state_status": "terrain_state_prototype_ready_for_dry_run",
    }) for r in rows], columns=TERRAIN_STATE_COLUMNS)


def _band_weight(value: str) -> float:
    return {
        "weak_0_03_to_0_08": 0.18, "low_0_08_to_0_14": 0.34, "moderate_0_14_to_0_20": 0.52,
        "short_1_to_2_steps": 0.20, "mid_3_to_5_steps": 0.38, "bounded_6_to_8_steps": 0.50,
        "early_warning": 0.26, "confirmed_local_condition": 0.42, "fast_release": 0.52,
        "condition_clear_release": 0.38, "high": 0.50, "medium": 0.34, "review": 0.32,
        "strict_review": 0.48, "coarse_direction_ok": 0.28, "local_direction_required": 0.46,
    }.get(str(value), 0.25)


def _priority_band(score: float) -> str:
    return "high_priority_for_later_sandbox_execution" if score >= 0.72 else "medium_priority_for_later_sandbox_execution" if score >= 0.55 else "low_priority_or_guarded_review"


def _operator_affinity(operator_name: str, state: pd.Series) -> float:
    pressure = float(state["pressure_gradient"]); curvature = float(state["curvature"]); flow = float(state["flow_velocity"])
    reversibility = float(state["reversibility"]); neighbor = float(state["neighbor_capacity"]); boundary = float(state["boundary_distance"])
    direction = float(state["direction_clarity"]); uncertainty = float(state["uncertainty"])
    table = {
        "soft_resistance": 0.30 * direction + 0.35 * pressure + 0.20 * (1.0 - boundary) + 0.15 * (1.0 - uncertainty),
        "pressure_diffusion": 0.40 * pressure + 0.35 * neighbor + 0.25 * reversibility,
        "gradient_smoothing": 0.50 * curvature + 0.20 * pressure + 0.30 * flow,
        "escape_channel": 0.35 * direction + 0.30 * (1.0 - reversibility) + 0.20 * pressure + 0.15 * neighbor,
        "damping": 0.45 * flow + 0.35 * curvature + 0.20 * uncertainty,
        "buffer_injection": 0.35 * (1.0 - boundary) + 0.25 * pressure + 0.25 * (1.0 - reversibility) + 0.15 * uncertainty,
        "reversibility_support": 0.60 * (1.0 - reversibility) + 0.25 * (1.0 - boundary) + 0.15 * direction,
    }
    return float(table.get(str(operator_name), 0.35))


def build_parameter_sweep_dry_run_table(terrain_states: pd.DataFrame, operator_families: pd.DataFrame, cfg: V2TerrainActionParameterSweepDryRunConfig | None = None) -> pd.DataFrame:
    cfg = cfg or V2TerrainActionParameterSweepDryRunConfig()
    combos = list(product(
        ("weak_0_03_to_0_08", "low_0_08_to_0_14", "moderate_0_14_to_0_20"),
        ("short_1_to_2_steps", "mid_3_to_5_steps", "bounded_6_to_8_steps"),
        ("early_warning", "confirmed_local_condition"),
        ("fast_release", "condition_clear_release"),
        ("high", "medium"),
        ("review", "strict_review"),
        ("coarse_direction_ok", "local_direction_required"),
    ))[: cfg.max_rows_per_operator]
    rows = []
    row_id = 1
    for op in operator_families["operator_family_name"].astype(str).tolist():
        for _, state in terrain_states.iterrows():
            for strength, duration, trigger, release, rollback, audit, precision in combos:
                direction_ready = float(state["direction_clarity"]) * (0.65 + _band_weight(precision))
                state_ready = float(state["pressure_gradient"]) * (0.60 + _band_weight(trigger))
                release_ready = min(1.0, 0.45 + _band_weight(release) + 0.20 * float(state["boundary_distance"]))
                rollback_ready = min(1.0, 0.35 + _band_weight(rollback) + 0.35 * (1.0 - float(state["reversibility"])))
                audit_ready = min(1.0, 0.40 + _band_weight(audit) + 0.20 * float(state["uncertainty"]))
                side_caution = min(1.0, _band_weight(strength) + _band_weight(duration) + 0.30 * (1.0 - float(state["boundary_distance"])))
                overfit_caution = 0.32 if precision == "local_direction_required" else 0.44
                score = max(0.0, min(1.0, 0.22 * _operator_affinity(op, state) + 0.16 * direction_ready + 0.15 * state_ready + 0.13 * release_ready + 0.12 * rollback_ready + 0.10 * audit_ready + 0.06 - 0.08 * side_caution - 0.04 * overfit_caution))
                rows.append(_with_boundary({
                    "dry_run_row_id": f"v2_terrain_dry_run_{row_id:05d}", "terrain_state_id": str(state["terrain_state_id"]),
                    "terrain_state_name": str(state["terrain_state_name"]), "risk_label_for_evaluation_only": str(state["risk_label_for_evaluation_only"]),
                    "operator_family_name": op, "strength_band": strength, "duration_band": duration, "trigger_band": trigger, "release_band": release,
                    "rollback_sensitivity_band": rollback, "audit_strictness_band": audit, "precision_requirement_band": precision,
                    "direction_readiness": round(direction_ready, 6), "state_gate_readiness": round(state_ready, 6), "release_readiness": round(release_ready, 6),
                    "rollback_readiness": round(rollback_ready, 6), "audit_readiness": round(audit_ready, 6), "no_op_comparison_readiness": 1.0,
                    "side_effect_caution": round(side_caution, 6), "overfit_caution": round(overfit_caution, 6), "dry_run_priority_score": round(score, 6),
                    "dry_run_priority_band": _priority_band(score), "dry_run_status": "dry_run_diagnostic_only_not_executed",
                }))
                row_id += 1
    return pd.DataFrame(rows, columns=DRY_RUN_COLUMNS)


def build_operator_coverage_summary(sweep_dry_run: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for op, group in sweep_dry_run.groupby("operator_family_name", sort=True):
        rows.append(_with_boundary({
            "operator_family_name": str(op), "dry_run_row_count": int(len(group)),
            "mean_priority_score": round(float(group["dry_run_priority_score"].mean()), 6),
            "max_priority_score": round(float(group["dry_run_priority_score"].max()), 6),
            "high_priority_row_count": int((group["dry_run_priority_band"].astype(str) == "high_priority_for_later_sandbox_execution").sum()),
            "operator_coverage_status": "operator_covered_in_dry_run",
        }))
    return pd.DataFrame(rows, columns=OPERATOR_SUMMARY_COLUMNS)


def build_sweep_dry_run_checks(terrain_states: pd.DataFrame, sweep_dry_run: pd.DataFrame, operator_summary: pd.DataFrame, task19_ready: bool) -> pd.DataFrame:
    checks = [
        ("check_task19_ready", "upstream", "Task19 sandbox design is ready.", True, task19_ready),
        ("check_terrain_states", "terrain", "terrain-state prototypes exist", True, len(terrain_states) >= 6),
        ("check_sweep_rows", "sweep", "dry-run rows exist", True, len(sweep_dry_run) >= 100),
        ("check_operator_coverage", "coverage", "all operators covered", True, len(operator_summary) >= 7),
        ("check_no_op_ready", "NO_OP", "NO_OP readiness preserved", True, bool(sweep_dry_run["no_op_comparison_readiness"].astype(float).ge(1.0).all())),
        ("check_dry_run_status", "boundary", "diagnostic-only rows", True, set(sweep_dry_run["dry_run_status"].astype(str)) == {"dry_run_diagnostic_only_not_executed"}),
        ("check_no_operator_application", "boundary", "no operator applied", False, bool(sweep_dry_run["terrain_operator_applied"].astype(bool).any())),
        ("check_no_candidate_generation", "boundary", "no candidate generated", False, bool(sweep_dry_run["action_candidate_generated"].astype(bool).any())),
        ("check_no_effect_prediction", "boundary", "no effect prediction", False, bool(sweep_dry_run["effect_prediction_model_executed"].astype(bool).any())),
        ("check_no_execution", "boundary", "no execution", False, bool(sweep_dry_run["axis_executed"].astype(bool).any())),
        ("check_no_hidden_future", "boundary", "no hidden/future use", False, bool(sweep_dry_run["hidden_truth_input"].astype(bool).any() or sweep_dry_run["future_information_used"].astype(bool).any())),
    ]
    return pd.DataFrame([_with_boundary({"check_id": c[0], "check_scope": c[1], "check_description": c[2], "expected_value": bool(c[3]), "observed_value": bool(c[4]), "check_status": "pass" if bool(c[3]) == bool(c[4]) else "fail"}) for c in checks], columns=CHECK_COLUMNS)


def build_final_summary(terrain_states: pd.DataFrame, sweep_dry_run: pd.DataFrame, operator_summary: pd.DataFrame, checks: pd.DataFrame, task19_ready: bool) -> pd.DataFrame:
    high_count = int((sweep_dry_run["dry_run_priority_band"].astype(str) == "high_priority_for_later_sandbox_execution").sum())
    check_pass = int((checks["check_status"].astype(str) == "pass").sum())
    decision = "v2_terrain_action_parameter_sweep_dry_run_ready_without_execution" if task19_ready and len(terrain_states) >= 6 and len(sweep_dry_run) >= 100 and len(operator_summary) >= 7 and len(checks) == check_pass else "v2_terrain_action_parameter_sweep_dry_run_needs_review"
    return pd.DataFrame([_with_boundary({
        "terrain_state_count": len(terrain_states), "dry_run_row_count": len(sweep_dry_run), "operator_summary_count": len(operator_summary),
        "high_priority_row_count": high_count, "sweep_check_count": len(checks), "sweep_check_pass_count": check_pass, "task19_ready": bool(task19_ready),
        "v2_terrain_action_parameter_sweep_dry_run_decision": decision,
        "next_task": "Task 2-8j-21: G_t -> relation field -> O_t -> action module non-execution loop validation",
    })], columns=FINAL_SUMMARY_COLUMNS)


def validate_v2_terrain_action_parameter_sweep_dry_run_tables(terrain_states: pd.DataFrame, sweep_dry_run: pd.DataFrame, operator_summary: pd.DataFrame, checks: pd.DataFrame, final_summary: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    tables = {"terrain_states": (terrain_states, TERRAIN_STATE_COLUMNS), "sweep_dry_run": (sweep_dry_run, DRY_RUN_COLUMNS), "operator_summary": (operator_summary, OPERATOR_SUMMARY_COLUMNS), "checks": (checks, CHECK_COLUMNS), "final_summary": (final_summary, FINAL_SUMMARY_COLUMNS)}
    for name, (table, required_cols) in tables.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_20_empty_table:{name}"); continue
        missing = [c for c in required_cols if c not in table.columns]
        if missing:
            errors.append(f"task2_8j_20_missing_columns:{name}:" + ",".join(missing)); continue
        for col in REQUIRED_TRUE:
            if not bool(table[col].astype(bool).all()):
                errors.append(f"task2_8j_20_required_true_not_all_true:{name}:{col}")
        for col in FORBIDDEN_TRUE:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_20_forbidden_true:{name}:{col}")
        if set(table["gt_main_map_name"].astype(str)) != {"static_pca_7"}:
            errors.append(f"task2_8j_20_wrong_gt_main_map_name:{name}")
        if set(table["gt_main_component_count"].astype(int)) != {7}:
            errors.append(f"task2_8j_20_wrong_gt_component_count:{name}")
    if checks is not None and not checks.empty and not bool((checks["check_status"].astype(str) == "pass").all()):
        errors.append("task2_8j_20_check_failed")
    if sweep_dry_run is not None and not sweep_dry_run.empty and not sweep_dry_run["dry_run_priority_score"].astype(float).between(0.0, 1.0).all():
        errors.append("task2_8j_20_priority_score_out_of_bounds")
    return errors


def build_and_validate_v2_terrain_action_parameter_sweep_dry_run(cfg: V2TerrainActionParameterSweepDryRunConfig | None = None, **_unused: object) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    cfg = cfg or V2TerrainActionParameterSweepDryRunConfig()
    operator_families, _signals, _design_sweep, _guards, _design_checks, _task19_summary_table, task19_errors, task19_summary = build_and_validate_v2_terrain_action_sandbox_design(cfg=V2TerrainActionSandboxDesignConfig(max_sweep_rows=84))
    task19_ready = len(task19_errors) == 0 and str(task19_summary.get("v2_terrain_action_sandbox_design_decision", "")).startswith(TASK19_ACCEPTED_DECISION)
    if not cfg.require_task19_ready:
        task19_ready = True
    terrain_states = build_v2_terrain_state_prototypes()
    sweep_dry_run = build_parameter_sweep_dry_run_table(terrain_states, operator_families, cfg)
    operator_summary = build_operator_coverage_summary(sweep_dry_run)
    checks = build_sweep_dry_run_checks(terrain_states, sweep_dry_run, operator_summary, task19_ready)
    final_summary = build_final_summary(terrain_states, sweep_dry_run, operator_summary, checks, task19_ready)
    errors = ([f"task2_8j_20_upstream_19_error:{e}" for e in task19_errors] if cfg.require_task19_ready else []) + validate_v2_terrain_action_parameter_sweep_dry_run_tables(terrain_states, sweep_dry_run, operator_summary, checks, final_summary)
    summary = {
        "gt_main_map_name": "static_pca_7", "gt_main_component_count": 7,
        "task19_decision": task19_summary.get("v2_terrain_action_sandbox_design_decision", ""),
        "terrain_state_count": _safe_int(final_summary["terrain_state_count"].iloc[0]),
        "dry_run_row_count": _safe_int(final_summary["dry_run_row_count"].iloc[0]),
        "operator_summary_count": _safe_int(final_summary["operator_summary_count"].iloc[0]),
        "high_priority_row_count": _safe_int(final_summary["high_priority_row_count"].iloc[0]),
        "sweep_check_count": _safe_int(final_summary["sweep_check_count"].iloc[0]),
        "sweep_check_pass_count": _safe_int(final_summary["sweep_check_pass_count"].iloc[0]),
        "task19_ready": bool(task19_ready),
        "v2_terrain_action_parameter_sweep_dry_run_decision": str(final_summary["v2_terrain_action_parameter_sweep_dry_run_decision"].iloc[0]),
        "semantic_recipe_primary_key_forbidden": True, "terrain_information_primary_required": True,
        "v2_oracle_results_hint_only": True, "risk_label_used_only_for_evaluation": True,
        "sandbox_executed": False, "terrain_operator_applied": False, "action_candidate_generated": False,
        "action_effect_prediction_generated": False, "effect_prediction_model_executed": False, "concrete_action_generated": False,
        "axis_executed": False, "real_actionmodule_called": False, "validation_errors": errors,
    }
    return terrain_states, sweep_dry_run, operator_summary, checks, final_summary, errors, summary
