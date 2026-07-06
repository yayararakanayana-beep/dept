"""Task 2-8j-19: v2 terrain-action sandbox design RC1.

Purpose:
    Design a lightweight v2 sandbox for testing terrain-action operator families
    before full G_t -> relation field -> O_t -> action-module dry-run loops.
    This task defines the sandbox inputs, terrain signals, operator families,
    parameter sweep bands, and regression guards.  It does not run the sandbox,
    generate action candidates, predict effects, or execute actions.

Position:
    Task 2-8j-18 froze the failure-history lesson: avoid risk-label -> semantic
    prescription -> action.  Task 2-8j-19 turns that lesson into a v2 sandbox
    design where terrain operators are explored against observed terrain
    conditions, while v2 oracle/ideal-action information is allowed only as a
    sandbox hint, never as runtime action input.

Core principle:
    Explore smooth terrain transformations: soft resistance, pressure diffusion,
    gradient smoothing, escape channels, damping, buffer injection, and
    reversibility support.  The sandbox varies strength, duration, trigger,
    release, rollback sensitivity, audit strictness, and precision requirements;
    it preserves NO_OP and remains non-executing.
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product

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
from .pressure_action_task2_8j_14_action_axis_material_bundle_dry_run import ActionAxisMaterialBundleDryRunConfig
from .pressure_action_task2_8j_15_action_axis_dry_run_generation import ActionAxisDryRunGenerationConfig
from .pressure_action_task2_8j_16_action_axis_non_execution_review_no_op import ActionAxisNonExecutionReviewConfig
from .pressure_action_task2_8j_17_action_candidate_minimal_eligibility_contract import ActionCandidateMinimalEligibilityContractConfig
from .pressure_action_task2_8j_18_action_module_failure_history_prediction_terrain_principles import (
    ActionModuleFailureHistoryPredictionTerrainPrinciplesConfig,
    build_and_validate_action_module_failure_history_prediction_terrain_principles,
)

TASK2_8J_19_VERSION = "v2_terrain_action_sandbox_design_rc1"
TASK2_8J_19_CONTRACT = (
    "Task2_8j_19_v2_terrain_action_sandbox_design__terrain_operator_parameter_sweep_design_only__"
    "no_sandbox_execution_no_effect_prediction_no_candidate_generation_no_runtime"
)

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


def build_terrain_operator_family_table() -> pd.DataFrame:
    rows = [
        (
            "operator_01_soft_resistance",
            "soft_resistance",
            "Add a smooth opposing slope only along the observed dangerous transition direction.",
            "direction_vector;pressure_gradient;boundary_distance;uncertainty",
            "slow dangerous drift without blocking the whole trajectory",
            "hard_blocking_or_global_stop",
            "relation_lock->unlock",
        ),
        (
            "operator_02_pressure_diffusion",
            "pressure_diffusion",
            "Spread local pressure into nearby reversible regions to avoid sharp accumulation.",
            "local_pressure;neighbor_capacity;reversibility;volatility",
            "reduce local burst risk while preserving exploration space",
            "single_point_pressure_suppression",
            "resource_pressure->buffer",
        ),
        (
            "operator_03_gradient_smoothing",
            "gradient_smoothing",
            "Smooth abrupt terrain gradients that create unstable jumps or over-attraction.",
            "curvature;gradient_steepness;flow;oscillation_marker",
            "make transitions gentler and more predictable",
            "flattening_all_structure",
            "coordination_lag->speed_up",
        ),
        (
            "operator_04_escape_channel",
            "escape_channel",
            "Open a narrow reversible path away from a local attractor or lock basin.",
            "attractor_strength;escape_direction;reversibility;uncertainty",
            "provide non-destructive exit from overconverged state",
            "force_unlock_without_state_gate",
            "relation_lock->force_release",
        ),
        (
            "operator_05_damping",
            "damping",
            "Dampen excessive oscillation or overreaction while preserving trend information.",
            "oscillation_marker;velocity;acceleration;uncertainty",
            "avoid unstable back-and-forth amplification",
            "permanent_slowdown",
            "instability->slow_everything",
        ),
        (
            "operator_06_buffer_injection",
            "buffer_injection",
            "Add temporary local slack around a fragile transition or boundary.",
            "boundary_distance;fragility;local_variance;rollback_capacity",
            "absorb shock without committing to a permanent correction",
            "global_buffer_growth",
            "shock->increase_all_buffers",
        ),
        (
            "operator_07_reversibility_support",
            "reversibility_support",
            "Strengthen return paths and rollback-compatible local transitions.",
            "reversibility;rollback_trigger;path_memory;side_effect_marker",
            "keep actions undoable and prevent one-way lock-in",
            "late_rollback_after_damage",
            "reversibility_loss->rollback_always",
        ),
    ]
    return pd.DataFrame([
        {
            **BOUNDARY,
            "operator_family_id": operator_id,
            "operator_family_name": name,
            "terrain_transformation": transformation,
            "primary_terrain_signals": signals,
            "intended_use": intended,
            "known_failure_to_avoid": failure,
            "forbidden_semantic_recipe": forbidden,
            "operator_status": "terrain_operator_family_designed_not_applied",
        }
        for operator_id, name, transformation, signals, intended, failure, forbidden in rows
    ], columns=REQUIRED_OPERATOR_COLUMNS)


def build_terrain_signal_contract_table() -> pd.DataFrame:
    rows = [
        ("signal_01_target_region", "target_region", "O_t", "where", "Locate the region to alter; prevents global action.", True),
        ("signal_02_direction_vector", "direction_vector", "relation_field", "direction", "Select the local direction of resistance, diffusion, or escape.", True),
        ("signal_03_pressure_gradient", "pressure_gradient", "relation_field", "intensity", "Estimate where pressure accumulates and where soft resistance may help.", True),
        ("signal_04_reversibility", "reversibility", "G_t/K_t/O_t", "safety", "Require return path and rollback compatibility.", True),
        ("signal_05_uncertainty", "uncertainty", "O_t/audit", "confidence", "Trigger review, fast release, or NO_OP when observation confidence is low.", True),
        ("signal_06_boundary_distance", "boundary_distance", "O_t/audit", "risk", "Avoid acting too close to failure boundaries without stronger audit.", True),
        ("signal_07_flow_velocity", "flow_velocity", "relation_field", "timing", "Choose timing and damping band.", True),
        ("signal_08_curvature", "curvature", "relation_field", "shape", "Detect sharp turns or unstable gradients needing smoothing.", True),
        ("signal_09_neighbor_capacity", "neighbor_capacity", "relation_field", "escape", "Check whether pressure can diffuse into nearby terrain without overload.", True),
        ("signal_10_no_op_baseline", "NO_OP_baseline", "NO_OP", "comparison", "Preserve do-nothing baseline for later effect and risk review.", True),
    ]
    return pd.DataFrame([
        {
            **BOUNDARY,
            "terrain_signal_id": signal_id,
            "signal_name": name,
            "source_route": route,
            "signal_role": role,
            "why_needed_for_action": why,
            "not_a_semantic_label": bool(not_semantic),
            "signal_status": "terrain_signal_contract_ready",
        }
        for signal_id, name, route, role, why, not_semantic in rows
    ], columns=REQUIRED_SIGNAL_COLUMNS)


def build_parameter_sweep_design_table(
    operator_families: pd.DataFrame,
    cfg: V2TerrainActionSandboxDesignConfig | None = None,
) -> pd.DataFrame:
    cfg = cfg or V2TerrainActionSandboxDesignConfig()
    if operator_families is None or operator_families.empty:
        return pd.DataFrame(columns=REQUIRED_SWEEP_COLUMNS)
    rows: list[dict] = []
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
    for idx, (op, strength, duration, trigger, release, rollback, audit, precision) in enumerate(combinations, start=1):
        if idx > cfg.max_sweep_rows:
            break
        rows.append({
            **BOUNDARY,
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
        })
    return pd.DataFrame(rows, columns=REQUIRED_SWEEP_COLUMNS)


def build_sandbox_guards_table() -> pd.DataFrame:
    rows = [
        ("guard_01_no_semantic_recipe", "no_semantic_recipe_primary_key", "Risk labels cannot directly choose operators.", "risk_label_to_prescription_table"),
        ("guard_02_no_hidden_truth", "no_hidden_truth_or_future", "Sandbox design cannot use hidden truth or future labels for action generation.", "oracle_leakage"),
        ("guard_03_oracle_hint_only", "oracle_hint_only", "v2 ideal-action search can set sweep ranges, not runtime decisions.", "copy_v2_answer_into_action_module"),
        ("guard_04_no_execution", "non_execution", "No terrain operator is applied in this task.", "premature_runtime_action"),
        ("guard_05_no_effect_prediction", "no_effect_prediction_execution", "Effect prediction is required later but not run here.", "proxy_score_as_final_expected_value"),
        ("guard_06_no_single_seed_tuning", "multi_seed_required_later", "Future sandbox execution must use seed and scenario variation.", "single_scenario_overfit"),
        ("guard_07_no_op_preserved", "NO_OP_preserved", "Every design path preserves NO_OP comparison for later review.", "acting_without_baseline"),
        ("guard_08_release_rollback_audit", "release_rollback_audit_required", "Every operator sweep must carry release, rollback, and audit dimensions.", "unbounded_action_duration"),
    ]
    return pd.DataFrame([
        {
            **BOUNDARY,
            "guard_id": guard_id,
            "guard_name": name,
            "guard_definition": definition,
            "regression_prevented": regression,
            "guard_status": "sandbox_guard_ready",
        }
        for guard_id, name, definition, regression in rows
    ], columns=REQUIRED_GUARD_COLUMNS)


def build_sandbox_design_checks(
    operator_families: pd.DataFrame,
    signals: pd.DataFrame,
    sweep: pd.DataFrame,
    guards: pd.DataFrame,
    task18_errors: list[str],
    task18_summary: dict,
) -> pd.DataFrame:
    has_ops = bool(operator_families is not None and not operator_families.empty)
    has_signals = bool(signals is not None and not signals.empty)
    has_sweep = bool(sweep is not None and not sweep.empty)
    has_guards = bool(guards is not None and not guards.empty)
    task18_ready = len(task18_errors) == 0 and str(task18_summary.get("action_module_failure_history_review_decision", "")).startswith("action_module_failure_history_prediction_necessity_and_terrain_action_principles_frozen")
    checks = [
        ("check_task18_ready", "upstream", "Task2-8j-18 failure-history / terrain principles are ready.", True, task18_ready),
        ("check_operator_families", "operator", "Terrain operator families are designed.", True, has_ops and len(operator_families) >= 7),
        ("check_terrain_signals", "signals", "Terrain signal contract is designed.", True, has_signals and len(signals) >= 8),
        ("check_parameter_sweep", "sweep", "Parameter sweep design rows are created.", True, has_sweep and len(sweep) >= 21),
        ("check_sandbox_guards", "guards", "Regression guards are created.", True, has_guards and len(guards) >= 7),
        ("check_no_semantic_recipe", "regression_guard", "Semantic recipe primary key is forbidden.", True, bool(operator_families["semantic_recipe_primary_key_forbidden"].astype(bool).all()) if has_ops else False),
        ("check_terrain_primary", "regression_guard", "Terrain information remains primary.", True, bool(signals["terrain_information_primary_required"].astype(bool).all()) if has_signals else False),
        ("check_no_op_later", "NO_OP", "NO_OP comparison is required later for every sweep row.", True, bool(sweep["no_op_comparison_required_later"].astype(bool).all()) if has_sweep else False),
        ("check_effect_prediction_deferred", "boundary", "Effect prediction is deferred for every sweep row.", True, bool(sweep["effect_prediction_required_later"].astype(bool).all()) if has_sweep else False),
        ("check_risk_review_deferred", "boundary", "Risk review is deferred for every sweep row.", True, bool(sweep["risk_review_required_later"].astype(bool).all()) if has_sweep else False),
        ("check_no_sandbox_execution", "boundary", "Sandbox is not executed.", False, bool(sweep["sandbox_executed"].astype(bool).any()) if has_sweep else True),
        ("check_no_action_candidate", "boundary", "No action candidate is generated.", False, bool(sweep["action_candidate_generated"].astype(bool).any()) if has_sweep else True),
        ("check_no_effect_prediction_execution", "boundary", "No effect prediction model is executed.", False, bool(sweep["effect_prediction_model_executed"].astype(bool).any()) if has_sweep else True),
        ("check_no_hidden_future", "boundary", "No hidden-truth or future information is used.", False, bool(sweep["hidden_truth_input"].astype(bool).any() or sweep["future_information_used"].astype(bool).any()) if has_sweep else True),
    ]
    rows = []
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


def build_final_summary(
    operator_families: pd.DataFrame,
    signals: pd.DataFrame,
    sweep: pd.DataFrame,
    guards: pd.DataFrame,
    checks: pd.DataFrame,
    task18_ready: bool,
) -> pd.DataFrame:
    op_count = int(len(operator_families)) if operator_families is not None else 0
    signal_count = int(len(signals)) if signals is not None else 0
    sweep_count = int(len(sweep)) if sweep is not None else 0
    guard_count = int(len(guards)) if guards is not None else 0
    check_count = int(len(checks)) if checks is not None else 0
    check_pass = int((checks["check_status"].astype(str) == "pass").sum()) if check_count else 0
    if task18_ready and op_count >= 7 and signal_count >= 8 and sweep_count >= 21 and guard_count >= 7 and check_count == check_pass:
        decision = "v2_terrain_action_sandbox_design_ready_without_execution"
    else:
        decision = "v2_terrain_action_sandbox_design_needs_review"
    return pd.DataFrame([{
        **BOUNDARY,
        "operator_family_count": op_count,
        "terrain_signal_count": signal_count,
        "sweep_design_row_count": sweep_count,
        "sandbox_guard_count": guard_count,
        "sandbox_check_count": check_count,
        "sandbox_check_pass_count": check_pass,
        "task18_ready": bool(task18_ready),
        "v2_terrain_action_sandbox_design_decision": decision,
        "next_task": "Task 2-8j-20: v2 terrain-action sandbox parameter sweep dry-run",
    }], columns=REQUIRED_SUMMARY_COLUMNS)


def validate_v2_terrain_action_sandbox_design_tables(
    operator_families: pd.DataFrame,
    signals: pd.DataFrame,
    sweep: pd.DataFrame,
    guards: pd.DataFrame,
    checks: pd.DataFrame,
    final_summary: pd.DataFrame,
) -> list[str]:
    errors: list[str] = []
    tables = {
        "operator_families": (operator_families, REQUIRED_OPERATOR_COLUMNS),
        "signals": (signals, REQUIRED_SIGNAL_COLUMNS),
        "sweep": (sweep, REQUIRED_SWEEP_COLUMNS),
        "guards": (guards, REQUIRED_GUARD_COLUMNS),
        "checks": (checks, REQUIRED_CHECK_COLUMNS),
        "final_summary": (final_summary, REQUIRED_SUMMARY_COLUMNS),
    }
    required_true = [
        "validation_only", "sandbox_design_only", "v2_terrain_action_sandbox_only", "terrain_operator_design_only",
        "parameter_sweep_design_only", "source_task18_required", "semantic_recipe_primary_key_forbidden",
        "terrain_information_primary_required", "risk_label_used_only_for_evaluation", "meaning_labels_explanation_only",
        "v2_oracle_results_hint_only", "v2_oracle_results_not_direct_action_input",
        "full_loop_action_must_use_system_visible_information", "prediction_required_before_final_expected_value_review",
        "no_op_preserved", "direction_selection_required", "state_dependence_required", "immediate_release_required",
        "rollback_required", "audit_required", "multi_seed_robustness_required_later", "no_single_scenario_optimization",
    ]
    for name, (table, required_cols) in tables.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_19_empty_table:{name}")
            continue
        missing = [c for c in required_cols if c not in table.columns]
        if missing:
            errors.append(f"task2_8j_19_missing_columns:{name}:" + ",".join(missing))
            continue
        for col in required_true:
            if not bool(table[col].astype(bool).all()):
                errors.append(f"task2_8j_19_required_true_not_all_true:{name}:{col}")
        if set(table["gt_main_map_name"].astype(str)) != {"static_pca_7"}:
            errors.append(f"task2_8j_19_wrong_gt_main_map_name:{name}")
        if set(table["gt_main_component_count"].astype(int)) != {7}:
            errors.append(f"task2_8j_19_wrong_gt_component_count:{name}")
        for col in FORBIDDEN_TRUE:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_19_forbidden_true:{name}:{col}")
    if checks is not None and not checks.empty:
        if not bool((checks["check_status"].astype(str) == "pass").all()):
            errors.append("task2_8j_19_check_failed")
    if operator_families is not None and not operator_families.empty:
        forbidden = " ".join(operator_families["forbidden_semantic_recipe"].astype(str).tolist())
        for token in ["relation_lock->", "resource_pressure->", "coordination_lag->"]:
            if token not in forbidden:
                errors.append(f"task2_8j_19_missing_semantic_recipe_regression_example:{token}")
    if signals is not None and not signals.empty:
        if not bool(signals["not_a_semantic_label"].astype(bool).all()):
            errors.append("task2_8j_19_signal_marked_semantic")
    return errors


def build_and_validate_v2_terrain_action_sandbox_design(
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
    axis_cfg: ActionAxisDryRunGenerationConfig | None = None,
    review_cfg: ActionAxisNonExecutionReviewConfig | None = None,
    eligibility_cfg: ActionCandidateMinimalEligibilityContractConfig | None = None,
    failure_history_cfg: ActionModuleFailureHistoryPredictionTerrainPrinciplesConfig | None = None,
    cfg: V2TerrainActionSandboxDesignConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    cfg = cfg or V2TerrainActionSandboxDesignConfig()
    _failures, _prediction_needs, _principles, _task18_checks, _task18_final, task18_errors, task18_summary = build_and_validate_action_module_failure_history_prediction_terrain_principles(
        tracking_cfg=tracking_cfg or V2StructureChangeTrackingConfig(),
        ot_cfg=ot_cfg or OtObservationMapConfig(),
        audit_cfg=audit_cfg or OtAuditLayeringConfig(),
        preservation_cfg=preservation_cfg or RelationToOtInformationPreservationConfig(),
        split_cfg=split_cfg or ActionModuleInputSplitContractConfig(),
        reception_cfg=reception_cfg or TwoRouteReceptionDryRunConfig(),
        prediction_contract_cfg=prediction_contract_cfg or GameStructurePredictionInputContractConfig(),
        prediction_envelope_cfg=prediction_envelope_cfg or GameStructurePredictionEnvelopeDryRunConfig(),
        upper_layer_cfg=upper_layer_cfg or NewGtUpperLayerRevalidationConfig(),
        material_contract_cfg=material_contract_cfg or ActionAxisMaterialContractConfig(),
        bundle_cfg=bundle_cfg or ActionAxisMaterialBundleDryRunConfig(),
        axis_cfg=axis_cfg or ActionAxisDryRunGenerationConfig(),
        review_cfg=review_cfg or ActionAxisNonExecutionReviewConfig(),
        eligibility_cfg=eligibility_cfg or ActionCandidateMinimalEligibilityContractConfig(),
        cfg=failure_history_cfg or ActionModuleFailureHistoryPredictionTerrainPrinciplesConfig(),
    )
    task18_ready = len(task18_errors) == 0 and str(task18_summary.get("action_module_failure_history_review_decision", "")).startswith("action_module_failure_history_prediction_necessity_and_terrain_action_principles_frozen")
    upstream_errors = [f"task2_8j_19_upstream_18_error:{e}" for e in task18_errors] if cfg.require_task18_ready else []
    operator_families = build_terrain_operator_family_table()
    signals = build_terrain_signal_contract_table()
    sweep = build_parameter_sweep_design_table(operator_families, cfg)
    guards = build_sandbox_guards_table()
    checks = build_sandbox_design_checks(operator_families, signals, sweep, guards, upstream_errors, task18_summary)
    final_summary = build_final_summary(operator_families, signals, sweep, guards, checks, task18_ready)
    errors = list(upstream_errors)
    errors.extend(validate_v2_terrain_action_sandbox_design_tables(operator_families, signals, sweep, guards, checks, final_summary))
    summary = {
        "gt_main_map_name": "static_pca_7",
        "gt_main_component_count": 7,
        "task18_decision": task18_summary.get("action_module_failure_history_review_decision", ""),
        "operator_family_count": _safe_int(final_summary["operator_family_count"].iloc[0]) if not final_summary.empty else 0,
        "terrain_signal_count": _safe_int(final_summary["terrain_signal_count"].iloc[0]) if not final_summary.empty else 0,
        "sweep_design_row_count": _safe_int(final_summary["sweep_design_row_count"].iloc[0]) if not final_summary.empty else 0,
        "sandbox_guard_count": _safe_int(final_summary["sandbox_guard_count"].iloc[0]) if not final_summary.empty else 0,
        "sandbox_check_count": _safe_int(final_summary["sandbox_check_count"].iloc[0]) if not final_summary.empty else 0,
        "sandbox_check_pass_count": _safe_int(final_summary["sandbox_check_pass_count"].iloc[0]) if not final_summary.empty else 0,
        "task18_ready": bool(task18_ready),
        "v2_terrain_action_sandbox_design_decision": str(final_summary["v2_terrain_action_sandbox_design_decision"].iloc[0]) if not final_summary.empty else "empty",
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
