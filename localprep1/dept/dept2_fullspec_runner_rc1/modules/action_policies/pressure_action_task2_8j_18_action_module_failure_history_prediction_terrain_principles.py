"""Task 2-8j-18: action-module failure history review RC1.

This freezes the path from earlier action-module failures to the current design:
pressure must not be collapsed too early; direct action updates are too coarse;
primitive substitution alone is not enough for hard relation-field cases; hard
blocking / force-unlocking can create side effects; and semantic risk-label
recipes can overfit.  The next phase must therefore use terrain-first action
principles: direction selection, state dependence, immediate release, rollback,
audit, NO_OP preservation, and prediction before final expected-value judgment.

This task is review-only.  It does not generate action candidates, does not run
an effect-prediction model, does not execute actions, and does not call the real
ActionModule runtime.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

TASK2_8J_18_VERSION = "action_module_failure_history_prediction_terrain_principles_rc1"
TASK2_8J_18_CONTRACT = (
    "Task2_8j_18_failure_history_prediction_necessity_terrain_action_principles__"
    "review_only_no_candidate_no_effect_prediction_no_execution"
)

BOUNDARY = {
    "task2_8j_18_version": TASK2_8J_18_VERSION,
    "task2_8j_18_contract": TASK2_8J_18_CONTRACT,
    "validation_only": True,
    "failure_history_review_only": True,
    "prediction_necessity_review_only": True,
    "terrain_action_principle_freeze_only": True,
    "gt_main_map_name": "static_pca_7",
    "gt_main_component_count": 7,
    "semantic_recipe_primary_key_forbidden": True,
    "terrain_information_primary_required": True,
    "direction_selection_required": True,
    "state_dependence_required": True,
    "immediate_release_required": True,
    "rollback_required": True,
    "audit_required": True,
    "no_op_preserved": True,
    "meaning_labels_explanation_only": True,
    "v2_oracle_results_not_direct_action_input": True,
    "full_loop_action_must_use_system_visible_information": True,
    "prediction_required_before_final_expected_value_review": True,
    "action_candidate_generated": False,
    "concrete_action_generated": False,
    "action_effect_prediction_generated": False,
    "effect_prediction_model_executed": False,
    "expected_value_final_judgment_performed": False,
    "risk_final_judgment_performed": False,
    "terrain_sandbox_executed": False,
    "real_actionmodule_called": False,
    "actionmodule_called": False,
    "axis_executed": False,
    "runtime_policy_input": False,
    "writeback_performed": False,
    "effective_dimension_refit_performed": False,
    "axis_mutation_performed": False,
    "hidden_truth_input": False,
    "future_information_used": False,
}

FORBIDDEN_TRUE = [
    "action_candidate_generated",
    "concrete_action_generated",
    "action_effect_prediction_generated",
    "effect_prediction_model_executed",
    "expected_value_final_judgment_performed",
    "risk_final_judgment_performed",
    "terrain_sandbox_executed",
    "real_actionmodule_called",
    "actionmodule_called",
    "axis_executed",
    "runtime_policy_input",
    "writeback_performed",
    "effective_dimension_refit_performed",
    "axis_mutation_performed",
    "hidden_truth_input",
    "future_information_used",
]

REQUIRED_TRUE = [
    "validation_only",
    "failure_history_review_only",
    "prediction_necessity_review_only",
    "terrain_action_principle_freeze_only",
    "semantic_recipe_primary_key_forbidden",
    "terrain_information_primary_required",
    "direction_selection_required",
    "state_dependence_required",
    "immediate_release_required",
    "rollback_required",
    "audit_required",
    "no_op_preserved",
    "meaning_labels_explanation_only",
    "v2_oracle_results_not_direct_action_input",
    "full_loop_action_must_use_system_visible_information",
    "prediction_required_before_final_expected_value_review",
]

FAILURE_COLUMNS = list(BOUNDARY) + [
    "failure_id",
    "failure_stage",
    "observed_failure",
    "lesson",
    "required_shift",
    "review_status",
]
PREDICTION_COLUMNS = list(BOUNDARY) + [
    "prediction_need_id",
    "missing_without_prediction",
    "required_structure",
    "action_module_use",
    "review_status",
]
PRINCIPLE_COLUMNS = list(BOUNDARY) + [
    "principle_id",
    "principle_name",
    "principle_definition",
    "forbidden_regression",
    "next_phase_requirement",
    "principle_status",
]
CHECK_COLUMNS = list(BOUNDARY) + [
    "check_id",
    "check_scope",
    "expected_value",
    "observed_value",
    "check_status",
]
SUMMARY_COLUMNS = list(BOUNDARY) + [
    "failure_review_count",
    "prediction_need_count",
    "terrain_principle_count",
    "review_check_count",
    "review_check_pass_count",
    "action_module_failure_history_review_decision",
    "next_task",
]


@dataclass(frozen=True)
class ActionModuleFailureHistoryReviewConfig:
    min_failure_rows: int = 6
    min_prediction_rows: int = 4
    min_principle_rows: int = 7


def build_failure_history_review_table() -> pd.DataFrame:
    rows = [
        ("early_pressure_compression", "upper_pressure_translation", "Upper pressure was collapsed too early into coarse action labels.", "Keep pressure material until action-module terrain translation.", "preserve_pressure_material"),
        ("direct_action_channel", "planner_to_feature_update", "Direct feature update was too coarse for timing, place, direction, release, and rollback.", "Add action surface, scheduler, audit, and non-execution review before runtime touch.", "insert_stateful_intermediate_layers"),
        ("primitive_substitution_partial", "actuation_primitives", "Primitive names improved simple cases but were not enough for hard relation-field cases.", "Primitive libraries need terrain-guided direction selection and staged release.", "terrain_guided_primitive_selection"),
        ("wall_like_intervention", "hard_suppression", "Blocking or force-unlocking can reduce one symptom while creating side effects.", "Prefer soft resistance, escape, diffusion, damping, buffer, and reversibility support.", "soft_terrain_operator_default"),
        ("semantic_recipe_overfit", "risk_label_prescription", "Rules like risk label to fixed prescription can overfit and miss local geometry.", "Use labels for explanation, not as the action-generation primary key.", "terrain_first_semantics_later"),
        ("prediction_gap", "selection_without_forecast", "Logs and current observation cannot show whether action beats NO_OP in total expected value.", "Build relation-field and game-structure prediction materials first.", "prediction_before_final_judgment"),
    ]
    return pd.DataFrame([
        {**BOUNDARY, "failure_id": fid, "failure_stage": stage, "observed_failure": obs, "lesson": lesson, "required_shift": shift, "review_status": "reviewed"}
        for fid, stage, obs, lesson, shift in rows
    ], columns=FAILURE_COLUMNS)


def build_prediction_necessity_table() -> pd.DataFrame:
    rows = [
        ("no_op_counterfactual", "Whether doing nothing is better than acting.", "game_structure_prediction_and_NO_OP_baseline", "defer final expected-value judgment"),
        ("place_direction_timing", "Where, when, and in which direction a weak terrain action should apply.", "G_t_to_relation_field_to_O_t_observation_map", "choose candidates from system-visible terrain"),
        ("release_and_rollback", "When to release or rollback before side effects accumulate.", "state_dependent_observation_plus_audit_gates", "keep action short, weak, reversible"),
        ("overfit_guard", "Whether an apparent best action is fitted to one v2 seed or label.", "multi_seed_terrain_operator_robustness_review", "treat v2 oracle results as hints only"),
    ]
    return pd.DataFrame([
        {**BOUNDARY, "prediction_need_id": pid, "missing_without_prediction": missing, "required_structure": structure, "action_module_use": use, "review_status": "reviewed"}
        for pid, missing, structure, use in rows
    ], columns=PREDICTION_COLUMNS)


def build_terrain_action_principles_table() -> pd.DataFrame:
    rows = [
        ("terrain_first_semantics_later", "Generate action material from terrain; attach semantic labels afterward.", "risk_label_to_fixed_prescription", "Candidates must be explainable from terrain information."),
        ("direction_selection", "Select local transition direction or pressure gradient before acting.", "global_undirected_correction", "Expose target region, direction vector, and operator."),
        ("state_dependence", "Trigger only when the observed terrain state enters a condition band.", "always_on_action", "Thresholds are tunable; a state gate is mandatory."),
        ("immediate_release", "Release when improvement, uncertainty, side effect, or condition exit appears.", "long_duration_without_release", "Carry release condition and max duration."),
        ("soft_terrain_operator", "Prefer smooth resistance, escape channel, diffusion, smoothing, damping, buffer, and reversibility support.", "hard_block_or_force_unlock_default", "Explore operator families and parameter bands."),
        ("prediction_before_final_judgment", "Final expected-value and risk judgment require prediction and NO_OP comparison.", "proxy_score_adoption", "Do not finalize adoption without forecast review."),
        ("oracle_is_hint_not_input", "v2 ideal search may guide ranges, not runtime decisions.", "copy_v2_oracle_answer", "Record oracle-derived hints as sandbox priors only."),
    ]
    return pd.DataFrame([
        {**BOUNDARY, "principle_id": f"principle_{i:02d}", "principle_name": name, "principle_definition": definition, "forbidden_regression": forbidden, "next_phase_requirement": requirement, "principle_status": "frozen"}
        for i, (name, definition, forbidden, requirement) in enumerate(rows, start=1)
    ], columns=PRINCIPLE_COLUMNS)


def build_review_checks(failure_history: pd.DataFrame, prediction_needs: pd.DataFrame, principles: pd.DataFrame, cfg: ActionModuleFailureHistoryReviewConfig) -> pd.DataFrame:
    checks = [
        ("failure_history_rows", "history", True, len(failure_history) >= cfg.min_failure_rows),
        ("prediction_need_rows", "prediction", True, len(prediction_needs) >= cfg.min_prediction_rows),
        ("terrain_principle_rows", "principle", True, len(principles) >= cfg.min_principle_rows),
        ("semantic_recipe_forbidden", "regression_guard", True, bool(principles["semantic_recipe_primary_key_forbidden"].all())),
        ("terrain_primary_required", "regression_guard", True, bool(principles["terrain_information_primary_required"].all())),
        ("prediction_before_final_judgment", "prediction", True, bool(principles["prediction_required_before_final_expected_value_review"].all())),
        ("no_candidate_generation", "boundary", False, bool(principles["action_candidate_generated"].any())),
        ("no_effect_prediction_execution", "boundary", False, bool(principles["effect_prediction_model_executed"].any())),
        ("no_execution", "boundary", False, bool(principles["axis_executed"].any())),
        ("no_hidden_or_future", "boundary", False, bool(principles["hidden_truth_input"].any() or principles["future_information_used"].any())),
    ]
    return pd.DataFrame([
        {**BOUNDARY, "check_id": cid, "check_scope": scope, "expected_value": bool(expected), "observed_value": bool(observed), "check_status": "pass" if bool(expected) == bool(observed) else "fail"}
        for cid, scope, expected, observed in checks
    ], columns=CHECK_COLUMNS)


def build_final_summary(failure_history: pd.DataFrame, prediction_needs: pd.DataFrame, principles: pd.DataFrame, checks: pd.DataFrame) -> pd.DataFrame:
    check_count = len(checks)
    check_pass = int((checks["check_status"] == "pass").sum())
    decision = "action_module_failure_history_prediction_necessity_and_terrain_action_principles_frozen" if check_count == check_pass else "action_module_failure_history_review_needs_review"
    return pd.DataFrame([{**BOUNDARY, "failure_review_count": len(failure_history), "prediction_need_count": len(prediction_needs), "terrain_principle_count": len(principles), "review_check_count": check_count, "review_check_pass_count": check_pass, "action_module_failure_history_review_decision": decision, "next_task": "Task 2-8j-19: v2 terrain-action sandbox design"}], columns=SUMMARY_COLUMNS)


def validate_action_module_failure_history_review_tables(failure_history: pd.DataFrame, prediction_needs: pd.DataFrame, principles: pd.DataFrame, checks: pd.DataFrame, final_summary: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    for name, table, required_cols in [
        ("failure_history", failure_history, FAILURE_COLUMNS),
        ("prediction_needs", prediction_needs, PREDICTION_COLUMNS),
        ("principles", principles, PRINCIPLE_COLUMNS),
        ("checks", checks, CHECK_COLUMNS),
        ("final_summary", final_summary, SUMMARY_COLUMNS),
    ]:
        if table is None or table.empty:
            errors.append(f"task2_8j_18_empty_table:{name}")
            continue
        missing = [col for col in required_cols if col not in table.columns]
        if missing:
            errors.append(f"task2_8j_18_missing_columns:{name}:" + ",".join(missing))
        for col in REQUIRED_TRUE:
            if not bool(table[col].astype(bool).all()):
                errors.append(f"task2_8j_18_required_true_not_all_true:{name}:{col}")
        for col in FORBIDDEN_TRUE:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_18_forbidden_true:{name}:{col}")
        if set(table["gt_main_map_name"].astype(str)) != {"static_pca_7"}:
            errors.append(f"task2_8j_18_wrong_gt_map:{name}")
        if set(table["gt_main_component_count"].astype(int)) != {7}:
            errors.append(f"task2_8j_18_wrong_component_count:{name}")
    if not bool((checks["check_status"] == "pass").all()):
        errors.append("task2_8j_18_check_failed")
    regression_text = " ".join(principles["forbidden_regression"].astype(str).tolist())
    for token in ["risk_label_to_fixed_prescription", "hard_block", "copy_v2_oracle_answer"]:
        if token not in regression_text:
            errors.append(f"task2_8j_18_missing_regression_guard:{token}")
    return errors


def build_and_validate_action_module_failure_history_prediction_terrain_principles(
    cfg: ActionModuleFailureHistoryReviewConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    cfg = cfg or ActionModuleFailureHistoryReviewConfig()
    failure_history = build_failure_history_review_table()
    prediction_needs = build_prediction_necessity_table()
    principles = build_terrain_action_principles_table()
    checks = build_review_checks(failure_history, prediction_needs, principles, cfg)
    final_summary = build_final_summary(failure_history, prediction_needs, principles, checks)
    errors = validate_action_module_failure_history_review_tables(failure_history, prediction_needs, principles, checks, final_summary)
    summary = {
        "gt_main_map_name": "static_pca_7",
        "gt_main_component_count": 7,
        "failure_review_count": int(final_summary["failure_review_count"].iloc[0]),
        "prediction_need_count": int(final_summary["prediction_need_count"].iloc[0]),
        "terrain_principle_count": int(final_summary["terrain_principle_count"].iloc[0]),
        "review_check_count": int(final_summary["review_check_count"].iloc[0]),
        "review_check_pass_count": int(final_summary["review_check_pass_count"].iloc[0]),
        "action_module_failure_history_review_decision": str(final_summary["action_module_failure_history_review_decision"].iloc[0]),
        "semantic_recipe_primary_key_forbidden": True,
        "terrain_information_primary_required": True,
        "prediction_required_before_final_expected_value_review": True,
        "action_candidate_generated": False,
        "action_effect_prediction_generated": False,
        "effect_prediction_model_executed": False,
        "concrete_action_generated": False,
        "axis_executed": False,
        "real_actionmodule_called": False,
        "validation_errors": errors,
    }
    return failure_history, prediction_needs, principles, checks, final_summary, errors, summary
