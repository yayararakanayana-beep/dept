"""Task 2-8j-19: v2 terrain-action sandbox design RC1.

This task designs the v2 terrain-action sandbox only.  It does not run the
sandbox, generate action candidates, predict effects, or execute actions.

Task 2-8j-18 already froze the failure-history lesson: avoid the regression
"risk label -> semantic prescription -> action".  This task turns that lesson
into a lightweight sandbox design: terrain signals, terrain-operator families,
parameter sweep bands, and regression guards.  v2 ideal-action/oracle material
may be used only as a sandbox hint, never as runtime action input.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Any

import pandas as pd

TASK2_8J_19_VERSION = "v2_terrain_action_sandbox_design_rc1"
TASK2_8J_19_CONTRACT = (
    "Task2_8j_19_v2_terrain_action_sandbox_design__"
    "terrain_operator_parameter_sweep_design_only__"
    "no_sandbox_execution_no_effect_prediction_no_candidate_generation_no_runtime"
)
TASK18_ACCEPTED_DECISION = "action_module_failure_history_prediction_necessity_and_terrain_action_principles_frozen"

BOUNDARY = {
    "task2_8j_19_version": TASK2_8J_19_VERSION,
    "task2_8j_19_contract": TASK2_8J_19_CONTRACT,
    "validation_only": True,
    "sandbox_design_only": True,
    "v2_terrain_action_sandbox_only": True,
    "terrain_operator_design_only": True,
    "parameter_sweep_design_only": True,
    "gt_main_map_name": "static_pca_7",
    "gt_main_component_count": 7,
    "source_task18_required": True,
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

FORBIDDEN_TRUE = [
    "sandbox_executed",
    "terrain_sandbox_executed",
    "terrain_operator_applied",
    "action_candidate_generated",
    "concrete_action_generated",
    "action_effect_prediction_generated",
    "effect_prediction_model_executed",
    "expected_value_final_judgment_performed",
    "risk_final_judgment_performed",
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
    "hidden_truth_input",
    "future_information_used",
]

REQUIRED_TRUE = [
    "validation_only",
    "sandbox_design_only",
    "v2_terrain_action_sandbox_only",
    "terrain_operator_design_only",
    "parameter_sweep_design_only",
    "source_task18_required",
    "semantic_recipe_primary_key_forbidden",
    "terrain_information_primary_required",
    "risk_label_used_only_for_evaluation",
    "meaning_labels_explanation_only",
    "v2_oracle_results_hint_only",
    "v2_oracle_results_not_direct_action_input",
    "full_loop_action_must_use_system_visible_information",
    "prediction_required_before_final_expected_value_review",
    "no_op_preserved",
    "direction_selection_required",
    "state_dependence_required",
    "immediate_release_required",
    "rollback_required",
    "audit_required",
    "multi_seed_robustness_required_later",
    "no_single_scenario_optimization",
]

REQUIRED_OPERATOR_COLUMNS = list(BOUNDARY) + [
    "operator_family_id",
    "operator_family_name",
    "terrain_transformation",
    "primary_terrain_signals",
    "intended_use",
    "known_failure_to_avoid",
    "forbidden_semantic_recipe",
    "operator_status",
]
REQUIRED_SIGNAL_COLUMNS = list(BOUNDARY) + [
    "terrain_signal_id",
    "signal_name",
    "source_route",
    "signal_role",
    "why_needed_for_action",
    "not_a_semantic_label",
    "signal_status",
]
REQUIRED_SWEEP_COLUMNS = list(BOUNDARY) + [
    "sweep_design_id",
    "operator_family_name",
    "strength_band",
    "duration_band",
    "trigger_band",
    "release_band",
    "rollback_sensitivity_band",
    "audit_strictness_band",
    "precision_requirement_band",
    "no_op_comparison_required_later",
    "effect_prediction_required_later",
    "risk_review_required_later",
    "design_row_status",
]
REQUIRED_GUARD_COLUMNS = list(BOUNDARY) + [
    "guard_id",
    "guard_name",
    "guard_definition",
    "regression_prevented",
    "guard_status",
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
    "operator_family_count",
    "terrain_signal_count",
    "sweep_design_row_count",
    "sandbox_guard_count",
    "sandbox_check_count",
    "sandbox_check_pass_count",
    "task18_ready",
    "v2_terrain_action_sandbox_design_decision",
    "next_task",
]


@dataclass(frozen=True)
class V2TerrainActionSandboxDesignConfig:
    require_task18_ready: bool = True
    strength_bands: tuple[str, ...] = ("weak_0_03_to_0_08", "low_0_08_to_0_14", "moderate_0_14_to_0_20")
    duration_bands: tuple[str, ...] = ("short_1_to_2_steps", "mid_3_to_5_steps", "bounded_6_to_8_steps")
    trigger_bands: tuple[str, ...] = ("early_warning", "confirmed_local_condition")
    release_bands: tuple[str, ...] = ("fast_release", "condition_clear_release")
    rollback_sensitivity_bands: tuple[str, ...] = ("high", "medium")
    audit_strictness_bands: tuple[str, ...] = ("review", "strict_review")
    precision_requirement_bands: tuple[str, ...] = ("coarse_direction_ok", "local_direction_required")
    max_sweep_rows: int = 84


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def _with_boundary(row: dict[str, Any]) -> dict[str, Any]:
    return {**BOUNDARY, **row}


def build_terrain_operator_family_table() -> pd.DataFrame:
    rows = [
        ("operator_01_soft_resistance", "soft_resistance", "smooth opposing slope along dangerous direction", "direction_vector;pressure_gradient;boundary_distance;uncertainty", "slow drift without blocking trajectory", "global_stop", "relation_lock->unlock"),
        ("operator_02_pressure_diffusion", "pressure_diffusion", "spread local pressure into nearby reversible regions", "local_pressure;neighbor_capacity;reversibility;volatility", "reduce burst risk while preserving exploration", "single_point_suppression", "resource_pressure->buffer"),
        ("operator_03_gradient_smoothing", "gradient_smoothing", "smooth abrupt terrain gradients", "curvature;gradient_steepness;flow;oscillation_marker", "make transitions gentler", "flatten_all_structure", "coordination_lag->speed_up"),
        ("operator_04_escape_channel", "escape_channel", "open a narrow reversible path away from attractor basin", "attractor_strength;escape_direction;reversibility;uncertainty", "provide non-destructive exit", "force_unlock_without_state_gate", "relation_lock->force_release"),
        ("operator_05_damping", "damping", "dampen excessive oscillation or overreaction", "oscillation_marker;velocity;acceleration;uncertainty", "avoid unstable amplification", "permanent_slowdown", "instability->slow_everything"),
        ("operator_06_buffer_injection", "buffer_injection", "add temporary local slack around fragile boundary", "boundary_distance;fragility;local_variance;rollback_capacity", "absorb shock without permanent correction", "global_buffer_growth", "shock->increase_all_buffers"),
        ("operator_07_reversibility_support", "reversibility_support", "strengthen return paths and rollback-compatible transitions", "reversibility;rollback_trigger;path_memory;side_effect_marker", "prevent one-way lock-in", "late_rollback_after_damage", "reversibility_loss->rollback_always"),
    ]
    return pd.DataFrame([
        _with_boundary({
            "operator_family_id": row[0],
            "operator_family_name": row[1],
            "terrain_transformation": row[2],
            "primary_terrain_signals": row[3],
            "intended_use": row[4],
            "known_failure_to_avoid": row[5],
            "forbidden_semantic_recipe": row[6],
            "operator_status": "terrain_operator_family_designed_not_applied",
        })
        for row in rows
    ], columns=REQUIRED_OPERATOR_COLUMNS)


def build_terrain_signal_contract_table() -> pd.DataFrame:
    rows = [
        ("signal_01_target_region", "target_region", "O_t", "where", "prevents global action"),
        ("signal_02_direction_vector", "direction_vector", "relation_field", "direction", "selects local action direction"),
        ("signal_03_pressure_gradient", "pressure_gradient", "relation_field", "intensity", "detects pressure accumulation"),
        ("signal_04_reversibility", "reversibility", "G_t/K_t/O_t", "safety", "requires return path"),
        ("signal_05_uncertainty", "uncertainty", "O_t/audit", "confidence", "triggers review or NO_OP"),
        ("signal_06_boundary_distance", "boundary_distance", "O_t/audit", "risk", "keeps action away from failure boundary"),
        ("signal_07_flow_velocity", "flow_velocity", "relation_field", "timing", "chooses timing and damping band"),
        ("signal_08_curvature", "curvature", "relation_field", "shape", "detects sharp turns"),
        ("signal_09_neighbor_capacity", "neighbor_capacity", "relation_field", "escape", "checks diffusion capacity"),
        ("signal_10_no_op_baseline", "NO_OP_baseline", "NO_OP", "comparison", "preserves do-nothing baseline"),
    ]
    return pd.DataFrame([
        _with_boundary({
            "terrain_signal_id": row[0],
            "signal_name": row[1],
            "source_route": row[2],
            "signal_role": row[3],
            "why_needed_for_action": row[4],
            "not_a_semantic_label": True,
            "signal_status": "terrain_signal_contract_ready",
        })
        for row in rows
    ], columns=REQUIRED_SIGNAL_COLUMNS)


def build_parameter_sweep_design_table(operator_families: pd.DataFrame, cfg: V2TerrainActionSandboxDesignConfig | None = None) -> pd.DataFrame:
    cfg = cfg or V2TerrainActionSandboxDesignConfig()
    rows = []
    combinations = product(
        operator_families["operator_family_name"].astype(str).tolist(),
        cfg.strength_bands,
        cfg.duration_bands,
        cfg.trigger_bands,
        cfg.release_bands,
        cfg.rollback_sensitivity_bands,
        cfg.audit_strictness_bands,
        cfg.precision_requirement_bands,
    )
    for idx, combo in enumerate(combinations, start=1):
        if idx > cfg.max_sweep_rows:
            break
        op, strength, duration, trigger, release, rollback, audit, precision = combo
        rows.append(_with_boundary({
            "sweep_design_id": f"v2_terrain_sweep_design_{idx:04d}",
            "operator_family_name": op,
            "strength_band": strength,
            "duration_band": duration,
            "trigger_band": trigger,
            "release_band": release,
            "rollback_sensitivity_band": rollback,
            "audit_strictness_band": audit,
            "precision_requirement_band": precision,
            "no_op_comparison_required_later": True,
            "effect_prediction_required_later": True,
            "risk_review_required_later": True,
            "design_row_status": "sandbox_design_row_ready_not_executed",
        }))
    return pd.DataFrame(rows, columns=REQUIRED_SWEEP_COLUMNS)


def build_sandbox_guards_table() -> pd.DataFrame:
    rows = [
        ("guard_01_no_semantic_recipe", "no_semantic_recipe_primary_key", "risk labels cannot choose operators", "risk_label_to_prescription_table"),
        ("guard_02_no_hidden_truth", "no_hidden_truth_or_future", "no hidden/future labels for generation", "oracle_leakage"),
        ("guard_03_oracle_hint_only", "oracle_hint_only", "v2 ideal action can set ranges only", "copy_v2_answer_into_action_module"),
        ("guard_04_no_execution", "non_execution", "no operator is applied", "premature_runtime_action"),
        ("guard_05_no_effect_prediction", "no_effect_prediction_execution", "effect prediction is deferred", "proxy_score_as_final_expected_value"),
        ("guard_06_no_single_seed_tuning", "multi_seed_required_later", "future run must vary seed/scenario", "single_scenario_overfit"),
        ("guard_07_no_op_preserved", "NO_OP_preserved", "NO_OP comparison is preserved", "acting_without_baseline"),
        ("guard_08_release_rollback_audit", "release_rollback_audit_required", "release, rollback, audit dimensions are mandatory", "unbounded_action_duration"),
    ]
    return pd.DataFrame([
        _with_boundary({"guard_id": row[0], "guard_name": row[1], "guard_definition": row[2], "regression_prevented": row[3], "guard_status": "sandbox_guard_ready"})
        for row in rows
    ], columns=REQUIRED_GUARD_COLUMNS)


def build_sandbox_design_checks(operator_families: pd.DataFrame, signals: pd.DataFrame, sweep: pd.DataFrame, guards: pd.DataFrame, task18_ready: bool = True) -> pd.DataFrame:
    checks = [
        ("check_task18_ready", "upstream", "Task18 principles are ready", True, task18_ready),
        ("check_operator_families", "operator", "operator families exist", True, len(operator_families) >= 7),
        ("check_terrain_signals", "signals", "terrain signals exist", True, len(signals) >= 8),
        ("check_parameter_sweep", "sweep", "sweep rows exist", True, len(sweep) >= 21),
        ("check_sandbox_guards", "guards", "guards exist", True, len(guards) >= 7),
        ("check_no_semantic_recipe", "regression_guard", "semantic recipe forbidden", True, bool(operator_families["semantic_recipe_primary_key_forbidden"].astype(bool).all())),
        ("check_terrain_primary", "regression_guard", "terrain primary", True, bool(signals["terrain_information_primary_required"].astype(bool).all())),
        ("check_no_op_later", "NO_OP", "NO_OP required later", True, bool(sweep["no_op_comparison_required_later"].astype(bool).all())),
        ("check_effect_prediction_deferred", "boundary", "effect prediction deferred", True, bool(sweep["effect_prediction_required_later"].astype(bool).all())),
        ("check_risk_review_deferred", "boundary", "risk review deferred", True, bool(sweep["risk_review_required_later"].astype(bool).all())),
        ("check_no_sandbox_execution", "boundary", "sandbox not executed", False, bool(sweep["sandbox_executed"].astype(bool).any())),
        ("check_no_action_candidate", "boundary", "candidate not generated", False, bool(sweep["action_candidate_generated"].astype(bool).any())),
        ("check_no_effect_prediction_execution", "boundary", "effect model not executed", False, bool(sweep["effect_prediction_model_executed"].astype(bool).any())),
        ("check_no_hidden_future", "boundary", "hidden/future not used", False, bool(sweep["hidden_truth_input"].astype(bool).any() or sweep["future_information_used"].astype(bool).any())),
    ]
    return pd.DataFrame([
        _with_boundary({"check_id": row[0], "check_scope": row[1], "check_description": row[2], "expected_value": bool(row[3]), "observed_value": bool(row[4]), "check_status": "pass" if bool(row[3]) == bool(row[4]) else "fail"})
        for row in checks
    ], columns=REQUIRED_CHECK_COLUMNS)


def build_final_summary(operator_families: pd.DataFrame, signals: pd.DataFrame, sweep: pd.DataFrame, guards: pd.DataFrame, checks: pd.DataFrame, task18_ready: bool = True) -> pd.DataFrame:
    check_count = len(checks)
    check_pass = int((checks["check_status"].astype(str) == "pass").sum())
    decision = "v2_terrain_action_sandbox_design_ready_without_execution" if task18_ready and len(operator_families) >= 7 and len(signals) >= 8 and len(sweep) >= 21 and len(guards) >= 7 and check_count == check_pass else "v2_terrain_action_sandbox_design_needs_review"
    return pd.DataFrame([_with_boundary({
        "operator_family_count": len(operator_families),
        "terrain_signal_count": len(signals),
        "sweep_design_row_count": len(sweep),
        "sandbox_guard_count": len(guards),
        "sandbox_check_count": check_count,
        "sandbox_check_pass_count": check_pass,
        "task18_ready": bool(task18_ready),
        "v2_terrain_action_sandbox_design_decision": decision,
        "next_task": "Task 2-8j-20: v2 terrain-action sandbox parameter sweep dry-run",
    })], columns=REQUIRED_SUMMARY_COLUMNS)


def validate_v2_terrain_action_sandbox_design_tables(operator_families: pd.DataFrame, signals: pd.DataFrame, sweep: pd.DataFrame, guards: pd.DataFrame, checks: pd.DataFrame, final_summary: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    tables = {
        "operator_families": (operator_families, REQUIRED_OPERATOR_COLUMNS),
        "signals": (signals, REQUIRED_SIGNAL_COLUMNS),
        "sweep": (sweep, REQUIRED_SWEEP_COLUMNS),
        "guards": (guards, REQUIRED_GUARD_COLUMNS),
        "checks": (checks, REQUIRED_CHECK_COLUMNS),
        "final_summary": (final_summary, REQUIRED_SUMMARY_COLUMNS),
    }
    for name, (table, required_cols) in tables.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_19_empty_table:{name}")
            continue
        missing = [c for c in required_cols if c not in table.columns]
        if missing:
            errors.append(f"task2_8j_19_missing_columns:{name}:" + ",".join(missing))
            continue
        for col in REQUIRED_TRUE:
            if not bool(table[col].astype(bool).all()):
                errors.append(f"task2_8j_19_required_true_not_all_true:{name}:{col}")
        for col in FORBIDDEN_TRUE:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_19_forbidden_true:{name}:{col}")
        if set(table["gt_main_map_name"].astype(str)) != {"static_pca_7"}:
            errors.append(f"task2_8j_19_wrong_gt_main_map_name:{name}")
        if set(table["gt_main_component_count"].astype(int)) != {7}:
            errors.append(f"task2_8j_19_wrong_gt_component_count:{name}")
    if checks is not None and not checks.empty and not bool((checks["check_status"].astype(str) == "pass").all()):
        errors.append("task2_8j_19_check_failed")
    if operator_families is not None and not operator_families.empty:
        forbidden = " ".join(operator_families["forbidden_semantic_recipe"].astype(str).tolist())
        for token in ["relation_lock->", "resource_pressure->", "coordination_lag->"]:
            if token not in forbidden:
                errors.append(f"task2_8j_19_missing_semantic_recipe_regression_example:{token}")
    if signals is not None and not signals.empty and not bool(signals["not_a_semantic_label"].astype(bool).all()):
        errors.append("task2_8j_19_signal_marked_semantic")
    return errors


def build_and_validate_v2_terrain_action_sandbox_design(cfg: V2TerrainActionSandboxDesignConfig | None = None, **_unused: object) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    cfg = cfg or V2TerrainActionSandboxDesignConfig()
    task18_ready = bool(cfg.require_task18_ready)
    operator_families = build_terrain_operator_family_table()
    signals = build_terrain_signal_contract_table()
    sweep = build_parameter_sweep_design_table(operator_families, cfg)
    guards = build_sandbox_guards_table()
    checks = build_sandbox_design_checks(operator_families, signals, sweep, guards, task18_ready)
    final_summary = build_final_summary(operator_families, signals, sweep, guards, checks, task18_ready)
    errors = validate_v2_terrain_action_sandbox_design_tables(operator_families, signals, sweep, guards, checks, final_summary)
    summary = {
        "gt_main_map_name": "static_pca_7",
        "gt_main_component_count": 7,
        "task18_decision": TASK18_ACCEPTED_DECISION,
        "operator_family_count": _safe_int(final_summary["operator_family_count"].iloc[0]),
        "terrain_signal_count": _safe_int(final_summary["terrain_signal_count"].iloc[0]),
        "sweep_design_row_count": _safe_int(final_summary["sweep_design_row_count"].iloc[0]),
        "sandbox_guard_count": _safe_int(final_summary["sandbox_guard_count"].iloc[0]),
        "sandbox_check_count": _safe_int(final_summary["sandbox_check_count"].iloc[0]),
        "sandbox_check_pass_count": _safe_int(final_summary["sandbox_check_pass_count"].iloc[0]),
        "task18_ready": bool(task18_ready),
        "v2_terrain_action_sandbox_design_decision": str(final_summary["v2_terrain_action_sandbox_design_decision"].iloc[0]),
        "semantic_recipe_primary_key_forbidden": True,
        "terrain_information_primary_required": True,
        "v2_oracle_results_hint_only": True,
        "risk_label_used_only_for_evaluation": True,
        "sandbox_executed": False,
        "action_candidate_generated": False,
        "action_effect_prediction_generated": False,
        "effect_prediction_model_executed": False,
        "concrete_action_generated": False,
        "axis_executed": False,
        "real_actionmodule_called": False,
        "validation_errors": errors,
    }
    return operator_families, signals, sweep, guards, checks, final_summary, errors, summary
