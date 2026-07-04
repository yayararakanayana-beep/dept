"""Task 2-5a: single-action -> pressure correspondence summary.

Task: ActionModule UpperPressure Reception Split RC1 / Task 2-5a.

This module does not build the pressure-to-action conversion function.  It only
summarizes validation evidence from Task 2-4 into an Action -> pressure table so
Task 2-6 can later use it as one input to a candidate-generation function.

Boundary:
    - summarizes Action -> result -> pressure-component correspondence
    - preserves PressureIntentBundle pressure meanings
    - does not create final actions
    - does not create ActionFrame
    - does not call ActionPlanner, ActionModule, or world runtime
    - does not perform state detection from lower-layer signals
    - marks output as validation evidence, not runtime policy input
"""
from __future__ import annotations

import pandas as pd

from .pressure_action_validation_suite_rc1 import (
    build_single_action_pressure_alignment_validation,
    summarize_state_dependence,
)


TASK2_5A_VERSION = "single_action_to_pressure_correspondence_summary_rc1"
TASK2_5A_MAPPING_SOURCE = "task2_4_single_action_pressure_alignment_validation"
TASK2_5A_CALIBRATION_STATUS = "task2_5a_summarized_validation_evidence"
TASK2_5A_CONTRACT = (
    "single_action_to_pressure_correspondence__summary_only__"
    "not_pressure_to_action_converter__not_runtime_policy_input__Task2_5a_RC1"
)

ACTION_CHANNEL_JA = {
    "exploration_injection": "探索を増やす作用",
    "coupling_relief": "結合を緩める作用",
    "volatility_damping": "揺れを抑える作用",
    "uncertainty_probe": "不確実性を探る作用",
    "relation_unlock": "関係固定を外す作用",
    "buffer_increase": "余裕枠を増やす作用",
    "no_op": "無作用",
}

PRESSURE_COMPONENT_JA = {
    "diagnostic_depth": "診断深度",
    "exploration_frequency": "探索頻度",
    "sandbox_entry_rate": "サンドボックス投入率",
    "adoption_threshold": "採用ハードル",
    "rollback_sensitivity": "巻き戻し感度",
    "deadzone_width": "不感帯幅",
    "cooldown_length": "待機時間",
    "hysteresis_strength": "履歴固定強度",
    "update_frequency": "更新頻度",
    "pressure_cap": "圧上限",
    "commitment_strength": "固定強度",
}

DIRECTION_JA = {
    "increase": "上げる",
    "decrease": "下げる",
    "neutral": "中立",
}

# This flag means "must be reviewed by Task 2-5c interaction validation".  It
# does not by itself mean the action is unsafe.
INTERACTION_REVIEW_REASON = {
    "exploration_injection": "探索を増やす作用は、関係固定を外す作用と重なると副作用が増幅し得るため、相互作用補正が必要。",
    "relation_unlock": "関係固定を外す作用は、探索を増やす作用や結合を緩める作用と重なると意図しない解除になり得るため、相互作用補正が必要。",
    "buffer_increase": "余裕枠を増やす作用は、揺れを抑える作用と重なると単純加算ではない安全側の非線形が出るため、相互作用補正が必要。",
    "volatility_damping": "揺れを抑える作用は、探索を増やす作用や余裕枠を増やす作用と重なると作用量が変わるため、相互作用補正が必要。",
    "coupling_relief": "結合を緩める作用は、関係固定を外す作用や不確実性を探る作用と重なるため、相互作用補正が必要。",
    "uncertainty_probe": "不確実性を探る作用は、結合を緩める作用と重なると観測・緩和の配分が変わるため、相互作用補正が必要。",
}

REQUIRED_TASK2_5A_COLUMNS = [
    "task2_5a_version",
    "task2_5a_contract",
    "validation_type",
    "validation_only",
    "runtime_policy_input",
    "pressure_to_action_converter_created",
    "final_action_decision",
    "action_frame_created",
    "actionmodule_called",
    "mapping_source",
    "calibration_status",
    "action_channel",
    "action_name_ja",
    "pressure_component",
    "pressure_component_ja",
    "component_direction",
    "component_direction_ja",
    "pressure_intent_ja",
    "control_domain",
    "semantic_effect",
    "intent_family",
    "suggested_control_route",
    "basic_alignment_score",
    "action_to_pressure_share",
    "basic_alignment_rank",
    "primary_or_supporting_action",
    "side_effect_burden",
    "confidence",
    "state_sensitivity_flag",
    "state_dependence_status",
    "relative_pressure_alignment_spread",
    "interaction_sensitivity_flag",
    "interaction_review_reason",
    "state_band_count",
    "sample_count",
    "result_to_pressure_direction_used",
    "uses_existing_pressure_intent_semantics",
    "new_semantic_translation_layer_added",
    "diagnostic_compat_policy_used",
    "repaired_diagnostic_policy_used",
]


def _pressure_intent_label(component: str, direction: str) -> str:
    component_ja = PRESSURE_COMPONENT_JA.get(str(component), str(component))
    direction_ja = DIRECTION_JA.get(str(direction), str(direction))
    return f"{component_ja}を{direction_ja}圧"


def _confidence(score: float, state_sensitive: bool, interaction_sensitive: bool) -> str:
    if score <= 1e-12:
        return "low"
    if state_sensitive or interaction_sensitive:
        return "medium_low"
    return "medium"


def _role(rank: int, score: float) -> str:
    if score <= 1e-12:
        return "weak_or_unresolved"
    if rank <= 3:
        return "primary_correspondence"
    return "supporting_correspondence"


def build_single_action_to_pressure_correspondence_table(
    alignment_validation: pd.DataFrame | None = None,
    state_dependence_summary: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build the Task 2-5a Action -> pressure correspondence table.

    The table answers the question: when a single action is applied and its
    result is interpreted back into pressure-intent space, which pressure
    components does it support most strongly?
    """
    alignment = (
        build_single_action_pressure_alignment_validation()
        if alignment_validation is None
        else alignment_validation.copy()
    )
    if alignment.empty:
        return pd.DataFrame(columns=REQUIRED_TASK2_5A_COLUMNS)

    state_dep = (
        summarize_state_dependence(alignment)
        if state_dependence_summary is None
        else state_dependence_summary.copy()
    )

    group_cols = [
        "action_channel",
        "pressure_component",
        "component_direction",
        "control_domain",
        "semantic_effect",
        "intent_family",
        "suggested_control_route",
    ]

    numeric_score = pd.to_numeric(alignment["pressure_alignment_score"], errors="coerce").fillna(0.0)
    numeric_side = pd.to_numeric(alignment["side_effect_burden_score"], errors="coerce").fillna(0.0)
    work = alignment.copy()
    work["_score"] = numeric_score
    work["_side"] = numeric_side

    summary = (
        work.groupby(group_cols, dropna=False)
        .agg(
            basic_alignment_score=("_score", "mean"),
            min_alignment_score=("_score", "min"),
            max_alignment_score=("_score", "max"),
            side_effect_burden=("_side", "mean"),
            state_band_count=("scenario_or_state_band", "nunique"),
            sample_count=("_score", "count"),
        )
        .reset_index()
    )

    dep_cols = [
        "pressure_component",
        "component_direction",
        "semantic_effect",
        "action_channel",
        "state_dependence_status",
        "relative_pressure_alignment_spread",
    ]
    if not state_dep.empty and set(dep_cols).issubset(state_dep.columns):
        summary = summary.merge(state_dep[dep_cols], on=dep_cols[:4], how="left")
    else:
        summary["state_dependence_status"] = "state_dependence_not_evaluated"
        summary["relative_pressure_alignment_spread"] = pd.NA

    summary["basic_alignment_score"] = pd.to_numeric(summary["basic_alignment_score"], errors="coerce").fillna(0.0)
    positive = summary["basic_alignment_score"].clip(lower=0.0)
    totals = positive.groupby(summary["action_channel"]).transform("sum")
    summary["action_to_pressure_share"] = (positive / totals.where(totals > 1e-12, 1.0)).fillna(0.0)

    # Rank pressure intents for each action: the top rows show which pressure
    # intents this action most directly supports.
    summary = summary.sort_values(
        ["action_channel", "basic_alignment_score", "action_to_pressure_share"],
        ascending=[True, False, False],
    ).reset_index(drop=True)
    summary["basic_alignment_rank"] = (
        summary.groupby("action_channel")["basic_alignment_score"]
        .rank(method="first", ascending=False)
        .astype(int)
    )

    rows: list[dict] = []
    for _, row in summary.iterrows():
        action = str(row["action_channel"])
        component = str(row["pressure_component"])
        direction = str(row["component_direction"])
        score = float(row["basic_alignment_score"])
        state_status = str(row.get("state_dependence_status", "state_dependence_not_evaluated"))
        state_sensitive = state_status == "state_dependent"
        interaction_reason = INTERACTION_REVIEW_REASON.get(action, "Task 2-5cで相互作用補正を確認する。")
        interaction_sensitive = action in INTERACTION_REVIEW_REASON
        rank = int(row["basic_alignment_rank"])
        rows.append({
            "task2_5a_version": TASK2_5A_VERSION,
            "task2_5a_contract": TASK2_5A_CONTRACT,
            "validation_type": "single_action_to_pressure_correspondence_summary",
            "validation_only": True,
            "runtime_policy_input": False,
            "pressure_to_action_converter_created": False,
            "final_action_decision": False,
            "action_frame_created": False,
            "actionmodule_called": False,
            "mapping_source": TASK2_5A_MAPPING_SOURCE,
            "calibration_status": TASK2_5A_CALIBRATION_STATUS,
            "action_channel": action,
            "action_name_ja": ACTION_CHANNEL_JA.get(action, action),
            "pressure_component": component,
            "pressure_component_ja": PRESSURE_COMPONENT_JA.get(component, component),
            "component_direction": direction,
            "component_direction_ja": DIRECTION_JA.get(direction, direction),
            "pressure_intent_ja": _pressure_intent_label(component, direction),
            "control_domain": row["control_domain"],
            "semantic_effect": row["semantic_effect"],
            "intent_family": row["intent_family"],
            "suggested_control_route": row["suggested_control_route"],
            "basic_alignment_score": score,
            "action_to_pressure_share": float(row["action_to_pressure_share"]),
            "basic_alignment_rank": rank,
            "primary_or_supporting_action": _role(rank, score),
            "side_effect_burden": float(row["side_effect_burden"]),
            "confidence": _confidence(score, state_sensitive, interaction_sensitive),
            "state_sensitivity_flag": bool(state_sensitive),
            "state_dependence_status": state_status,
            "relative_pressure_alignment_spread": row.get("relative_pressure_alignment_spread", pd.NA),
            "interaction_sensitivity_flag": bool(interaction_sensitive),
            "interaction_review_reason": interaction_reason,
            "state_band_count": int(row["state_band_count"]),
            "sample_count": int(row["sample_count"]),
            "result_to_pressure_direction_used": True,
            "uses_existing_pressure_intent_semantics": True,
            "new_semantic_translation_layer_added": False,
            "diagnostic_compat_policy_used": False,
            "repaired_diagnostic_policy_used": False,
        })

    out = pd.DataFrame(rows)
    return out[REQUIRED_TASK2_5A_COLUMNS]


def validate_single_action_to_pressure_correspondence_table(df: pd.DataFrame) -> list[str]:
    """Return validation errors for the Task 2-5a summary table."""
    errors: list[str] = []
    if df is None or df.empty:
        return ["task2_5a_single_action_to_pressure_table_empty"]
    missing = sorted(set(REQUIRED_TASK2_5A_COLUMNS) - set(df.columns))
    if missing:
        errors.append(f"task2_5a_required_columns_missing:{','.join(missing)}")
        return errors
    if not bool(df["validation_only"].astype(bool).all()):
        errors.append("task2_5a_not_all_validation_only")
    if bool(df["runtime_policy_input"].astype(bool).any()):
        errors.append("task2_5a_marked_as_runtime_policy_input")
    if bool(df["pressure_to_action_converter_created"].astype(bool).any()):
        errors.append("task2_5a_created_converter_too_early")
    if bool(df["final_action_decision"].astype(bool).any()):
        errors.append("task2_5a_made_final_action_decision")
    if bool(df["action_frame_created"].astype(bool).any()):
        errors.append("task2_5a_created_action_frame")
    if bool(df["actionmodule_called"].astype(bool).any()):
        errors.append("task2_5a_called_actionmodule")
    if bool(df["new_semantic_translation_layer_added"].astype(bool).any()):
        errors.append("task2_5a_added_new_semantic_translation_layer")
    if bool(df["diagnostic_compat_policy_used"].astype(bool).any()):
        errors.append("task2_5a_used_diagnostic_compat_policy")
    if bool(df["repaired_diagnostic_policy_used"].astype(bool).any()):
        errors.append("task2_5a_used_repaired_diagnostic_policy")

    scores = pd.to_numeric(df["basic_alignment_score"], errors="coerce")
    shares = pd.to_numeric(df["action_to_pressure_share"], errors="coerce")
    if bool(scores.isna().any() or (scores < 0).any()):
        errors.append("task2_5a_basic_alignment_score_invalid")
    if bool(shares.isna().any() or (shares < -1e-12).any() or (shares > 1.0 + 1e-12).any()):
        errors.append("task2_5a_action_to_pressure_share_out_of_bounds")

    allowed_roles = {"primary_correspondence", "supporting_correspondence", "weak_or_unresolved"}
    roles = set(df["primary_or_supporting_action"].astype(str))
    if not roles.issubset(allowed_roles):
        errors.append("task2_5a_unknown_primary_or_supporting_role")

    positive = df[pd.to_numeric(df["basic_alignment_score"], errors="coerce").fillna(0.0) > 1e-12]
    if not positive.empty:
        grouped = positive.groupby("action_channel", dropna=False)["action_to_pressure_share"].sum()
        if bool(((grouped - 1.0).abs() > 1e-9).any()):
            errors.append("task2_5a_action_to_pressure_shares_not_normalized_by_action")

    return errors


def build_and_validate_single_action_to_pressure_correspondence_table() -> tuple[pd.DataFrame, list[str]]:
    df = build_single_action_to_pressure_correspondence_table()
    return df, validate_single_action_to_pressure_correspondence_table(df)
