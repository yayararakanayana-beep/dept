"""Task 2-5c: interaction modifier validation for pressure-action conversion.

Task: ActionModule UpperPressure Reception Split RC1 / Task 2-5c.

This module summarizes pairwise action interaction evidence into coefficients for
later pressure-to-action candidate generation.  It treats relation-dependence and
action-combination effects as one interaction modifier, while keeping separate
audit columns for relation-derived and combination-derived reasons.

Boundary:
    - summarizes action-pair interaction evidence
    - does not build the pressure-to-action conversion function
    - does not create final actions
    - does not create ActionFrame
    - does not call ActionPlanner, ActionModule, or world runtime
    - does not infer live lower-layer relation state
    - marks output as validation evidence, not runtime policy input
"""
from __future__ import annotations

import pandas as pd

from .pressure_action_task2_5a_single_action_correspondence import ACTION_CHANNEL_JA
from .pressure_action_validation_suite_rc1 import build_action_combination_additivity_validation


TASK2_5C_VERSION = "interaction_modifier_validation_for_pressure_action_conversion_rc1"
TASK2_5C_MAPPING_SOURCE = "task2_4_combination_additivity_validation"
TASK2_5C_CALIBRATION_STATUS = "task2_5c_interaction_modifier_validation_evidence"
TASK2_5C_CONTRACT = (
    "interaction_modifier_validation__relation_and_combination_audit__"
    "not_pressure_to_action_converter__not_runtime_policy_input__Task2_5c_RC1"
)

STATE_BAND_JA = {
    "stable": "通常",
    "medium": "中負荷",
    "high": "高負荷",
    "limit": "限界",
}

RELATION_RELEVANT_ACTIONS = {"relation_unlock", "coupling_relief"}
OPENING_ACTIONS = {"exploration_injection", "relation_unlock", "coupling_relief"}
SAFETY_PAIR = {"buffer_increase", "volatility_damping"}
DANGEROUS_OPEN_PAIR = {"exploration_injection", "relation_unlock"}
RELIEF_UNLOCK_PAIR = {"coupling_relief", "relation_unlock"}

REQUIRED_TASK2_5C_COLUMNS = [
    "task2_5c_version",
    "task2_5c_contract",
    "validation_type",
    "validation_only",
    "runtime_policy_input",
    "pressure_to_action_converter_created",
    "final_action_decision",
    "action_frame_created",
    "actionmodule_called",
    "mapping_source",
    "calibration_status",
    "scenario_or_state_band",
    "state_band_ja",
    "action_channel_a",
    "action_channel_b",
    "action_name_a_ja",
    "action_name_b_ja",
    "action_pair",
    "action_pair_ja",
    "interaction_type",
    "interaction_modifier",
    "modifier_class",
    "boost_combination_flag",
    "dampen_combination_flag",
    "defer_combination_flag",
    "block_combination_flag",
    "useful_amplification_score",
    "cancellation_score",
    "side_effect_amplification_score",
    "non_additivity_score",
    "non_additivity_tolerance",
    "relation_dependency_flag",
    "combination_dependency_flag",
    "relation_dependency_reason",
    "combination_dependency_reason",
    "interaction_reason",
    "requires_task2_5d_mix_review",
    "requires_task2_5e_strength_review",
    "uses_existing_pressure_intent_semantics",
    "new_semantic_translation_layer_added",
    "diagnostic_compat_policy_used",
    "repaired_diagnostic_policy_used",
]


def _pair_set(row: pd.Series) -> set[str]:
    return {str(row["action_channel_a"]), str(row["action_channel_b"])}


def _pair_ja(a: str, b: str) -> str:
    return f"{ACTION_CHANNEL_JA.get(a, a)} + {ACTION_CHANNEL_JA.get(b, b)}"


def _cancellation_score(row: pd.Series) -> float:
    useful_fields = [
        "non_additive_delta_exploration_delta",
        "non_additive_delta_reversibility_delta",
        "non_additive_delta_net_public_effect_score",
        "non_additive_delta_trust_delta",
    ]
    burden_reduction_fields = [
        "non_additive_delta_net_hidden_effect_score",
        "non_additive_delta_hidden_damage_delta",
        "non_additive_delta_fatigue_delta",
        "non_additive_delta_resource_inequality_delta",
        "non_additive_delta_action_cost_effect",
    ]
    useful_loss = sum(max(0.0, -float(row.get(field, 0.0) or 0.0)) for field in useful_fields)
    burden_reduction = sum(max(0.0, -float(row.get(field, 0.0) or 0.0)) for field in burden_reduction_fields)
    return float(useful_loss + burden_reduction)


def _modifier_class(value: float) -> str:
    if value <= 0.0:
        return "block"
    if value <= 0.35:
        return "defer"
    if value < 0.90:
        return "dampen"
    if value > 1.10:
        return "boost"
    return "keep"


def _interaction_type(row: pd.Series, cancellation_score: float) -> str:
    status = str(row["combination_additivity_status"])
    pair = _pair_set(row)
    if pair == DANGEROUS_OPEN_PAIR and status == "side_effect_amplifying":
        return "dangerous_opening_side_effect_amplification"
    if pair == SAFETY_PAIR and status == "mixed_non_additive":
        return "safety_side_nonlinear_mixed"
    if pair == RELIEF_UNLOCK_PAIR and status != "approximately_additive":
        return "relation_release_non_additive"
    if status == "approximately_additive":
        return "approximately_additive"
    if status == "side_effect_amplifying":
        return "side_effect_amplifying"
    if status == "useful_amplifying":
        return "useful_amplifying"
    if cancellation_score > 0.0 and status == "mixed_non_additive":
        return "mixed_non_additive_with_cancellation"
    return "mixed_non_additive"


def _interaction_modifier(row: pd.Series, interaction_type: str) -> float:
    state = str(row["scenario_or_state_band"])
    risk = {"stable": 0.20, "medium": 0.50, "high": 0.78, "limit": 1.00}.get(state, 0.50)
    pair = _pair_set(row)
    side = float(row.get("side_effect_amplification_score", 0.0) or 0.0)
    useful = float(row.get("useful_amplification_score", 0.0) or 0.0)

    if pair == DANGEROUS_OPEN_PAIR:
        if state == "limit":
            return 0.0
        if state == "high":
            return 0.25
        if state == "medium":
            return 0.50
        return 0.70

    if pair == SAFETY_PAIR:
        if interaction_type == "safety_side_nonlinear_mixed":
            return 1.05 + 0.10 * risk
        return 1.0

    if pair == RELIEF_UNLOCK_PAIR:
        if side > useful:
            return max(0.25, 0.85 - 0.45 * risk)
        return 0.95

    if interaction_type == "approximately_additive":
        return 1.0
    if interaction_type == "useful_amplifying":
        return min(1.20, 1.0 + useful)
    if interaction_type == "side_effect_amplifying":
        return max(0.20, 0.90 - 0.55 * risk)
    if interaction_type in {"mixed_non_additive", "mixed_non_additive_with_cancellation"}:
        return 0.85
    return 1.0


def _relation_reason(pair: set[str]) -> tuple[bool, str]:
    if pair == DANGEROUS_OPEN_PAIR:
        return True, "探索を増やす作用と関係固定を外す作用が重なるため、関係解除と探索開口が同時に進みやすい。"
    if pair == RELIEF_UNLOCK_PAIR:
        return True, "結合を緩める作用と関係固定を外す作用が重なるため、関係解除の強度が過剰になり得る。"
    if bool(pair & RELATION_RELEVANT_ACTIONS):
        return True, "関係に触れる作用を含むため、関係由来の相互作用として監査する。"
    return False, "関係由来の強い相互作用は検出対象外。"


def _combination_reason(row: pd.Series, interaction_type: str) -> str:
    if interaction_type == "approximately_additive":
        return "この検証範囲ではほぼ足し算として扱える。"
    if interaction_type == "dangerous_opening_side_effect_amplification":
        return "探索開口と関係解除が同時に出るため、副作用増幅として弱化・延期・禁止を検討する。"
    if interaction_type == "safety_side_nonlinear_mixed":
        return "余裕確保と揺れ抑制の安全側非線形。単純加算ではないが安全側候補として扱える。"
    if interaction_type == "relation_release_non_additive":
        return "関係緩和と関係解除が同時に出るため、解除過多を避ける補正が必要。"
    if interaction_type == "side_effect_amplifying":
        return "副作用の非加法増幅が出ているため、状態が悪いほど弱化する。"
    if interaction_type == "useful_amplifying":
        return "有用側の非加法増幅が出ているため、上限つきで少し強める候補。"
    return "非加法の混合効果があるため、Task 2-5d/2-5eで混合入力と強度を確認する。"


def build_interaction_modifier_validation_table(
    combination_validation: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build Task 2-5c interaction modifier validation rows."""
    combo = (
        build_action_combination_additivity_validation()
        if combination_validation is None
        else combination_validation.copy()
    )
    if combo.empty:
        return pd.DataFrame(columns=REQUIRED_TASK2_5C_COLUMNS)

    rows: list[dict] = []
    for _, row in combo.iterrows():
        action_a = str(row["action_channel_a"])
        action_b = str(row["action_channel_b"])
        pair = {action_a, action_b}
        cancel = _cancellation_score(row)
        interaction_type = _interaction_type(row, cancel)
        modifier = float(_interaction_modifier(row, interaction_type))
        modifier_class = _modifier_class(modifier)
        relation_flag, relation_reason = _relation_reason(pair)
        combination_reason = _combination_reason(row, interaction_type)
        rows.append({
            "task2_5c_version": TASK2_5C_VERSION,
            "task2_5c_contract": TASK2_5C_CONTRACT,
            "validation_type": "interaction_modifier_validation",
            "validation_only": True,
            "runtime_policy_input": False,
            "pressure_to_action_converter_created": False,
            "final_action_decision": False,
            "action_frame_created": False,
            "actionmodule_called": False,
            "mapping_source": TASK2_5C_MAPPING_SOURCE,
            "calibration_status": TASK2_5C_CALIBRATION_STATUS,
            "scenario_or_state_band": str(row["scenario_or_state_band"]),
            "state_band_ja": STATE_BAND_JA.get(str(row["scenario_or_state_band"]), str(row["scenario_or_state_band"])),
            "action_channel_a": action_a,
            "action_channel_b": action_b,
            "action_name_a_ja": ACTION_CHANNEL_JA.get(action_a, action_a),
            "action_name_b_ja": ACTION_CHANNEL_JA.get(action_b, action_b),
            "action_pair": str(row.get("action_pair", f"{action_a}+{action_b}")),
            "action_pair_ja": _pair_ja(action_a, action_b),
            "interaction_type": interaction_type,
            "interaction_modifier": modifier,
            "modifier_class": modifier_class,
            "boost_combination_flag": modifier_class == "boost",
            "dampen_combination_flag": modifier_class == "dampen",
            "defer_combination_flag": modifier_class == "defer",
            "block_combination_flag": modifier_class == "block",
            "useful_amplification_score": float(row.get("useful_amplification_score", 0.0) or 0.0),
            "cancellation_score": float(cancel),
            "side_effect_amplification_score": float(row.get("side_effect_amplification_score", 0.0) or 0.0),
            "non_additivity_score": float(row.get("non_additivity_score", 0.0) or 0.0),
            "non_additivity_tolerance": float(row.get("non_additivity_tolerance", 0.0) or 0.0),
            "relation_dependency_flag": bool(relation_flag),
            "combination_dependency_flag": True,
            "relation_dependency_reason": relation_reason,
            "combination_dependency_reason": combination_reason,
            "interaction_reason": f"{relation_reason} / {combination_reason}",
            "requires_task2_5d_mix_review": interaction_type != "approximately_additive",
            "requires_task2_5e_strength_review": modifier_class in {"boost", "dampen", "defer", "block"},
            "uses_existing_pressure_intent_semantics": True,
            "new_semantic_translation_layer_added": False,
            "diagnostic_compat_policy_used": False,
            "repaired_diagnostic_policy_used": False,
        })
    out = pd.DataFrame(rows)
    return out[REQUIRED_TASK2_5C_COLUMNS]


def validate_interaction_modifier_validation_table(df: pd.DataFrame) -> list[str]:
    """Return validation errors for the Task 2-5c interaction table."""
    errors: list[str] = []
    if df is None or df.empty:
        return ["task2_5c_interaction_modifier_table_empty"]
    missing = sorted(set(REQUIRED_TASK2_5C_COLUMNS) - set(df.columns))
    if missing:
        errors.append(f"task2_5c_required_columns_missing:{','.join(missing)}")
        return errors

    false_fields = [
        "runtime_policy_input",
        "pressure_to_action_converter_created",
        "final_action_decision",
        "action_frame_created",
        "actionmodule_called",
        "new_semantic_translation_layer_added",
        "diagnostic_compat_policy_used",
        "repaired_diagnostic_policy_used",
    ]
    for field in false_fields:
        if bool(df[field].astype(bool).any()):
            errors.append(f"task2_5c_forbidden_true_field:{field}")

    if not bool(df["validation_only"].astype(bool).all()):
        errors.append("task2_5c_not_all_validation_only")
    if not bool(df["uses_existing_pressure_intent_semantics"].astype(bool).all()):
        errors.append("task2_5c_pressure_intent_semantics_not_preserved")
    if not bool(df["combination_dependency_flag"].astype(bool).all()):
        errors.append("task2_5c_combination_dependency_flag_missing")

    modifiers = pd.to_numeric(df["interaction_modifier"], errors="coerce")
    if bool(modifiers.isna().any() or (modifiers < 0.0).any() or (modifiers > 1.25).any()):
        errors.append("task2_5c_interaction_modifier_out_of_bounds")

    allowed_classes = {"boost", "keep", "dampen", "defer", "block"}
    if not set(df["modifier_class"].astype(str)).issubset(allowed_classes):
        errors.append("task2_5c_unknown_modifier_class")

    allowed_types = {
        "approximately_additive",
        "dangerous_opening_side_effect_amplification",
        "safety_side_nonlinear_mixed",
        "relation_release_non_additive",
        "side_effect_amplifying",
        "useful_amplifying",
        "mixed_non_additive",
        "mixed_non_additive_with_cancellation",
    }
    if not set(df["interaction_type"].astype(str)).issubset(allowed_types):
        errors.append("task2_5c_unknown_interaction_type")

    # The table must be informative: it should contain at least additive keep,
    # safety boost, and a dangerous open-pair block/defer/dampen rule.
    classes = set(df["modifier_class"].astype(str))
    if "keep" not in classes:
        errors.append("task2_5c_no_keep_rules")
    if "boost" not in classes:
        errors.append("task2_5c_no_boost_rules")
    if not ({"dampen", "defer", "block"} & classes):
        errors.append("task2_5c_no_dampen_defer_or_block_rules")

    dangerous = df[df["interaction_type"].astype(str) == "dangerous_opening_side_effect_amplification"]
    if dangerous.empty:
        errors.append("task2_5c_missing_dangerous_opening_pair")
    else:
        if not bool(dangerous["relation_dependency_flag"].astype(bool).all()):
            errors.append("task2_5c_dangerous_opening_pair_not_marked_relation_dependent")
        if not bool(dangerous["modifier_class"].astype(str).isin({"dampen", "defer", "block"}).all()):
            errors.append("task2_5c_dangerous_opening_pair_not_weakened")

    return errors


def build_and_validate_interaction_modifier_validation_table() -> tuple[pd.DataFrame, list[str]]:
    df = build_interaction_modifier_validation_table()
    return df, validate_interaction_modifier_validation_table(df)
