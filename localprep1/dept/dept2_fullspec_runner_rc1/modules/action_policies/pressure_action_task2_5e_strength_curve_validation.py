"""Task 2-5e: action-strength curve validation for pressure-action conversion.

Task: ActionModule UpperPressure Reception Split RC1 / Task 2-5e.

This module validates how pressure strength bands should map to candidate action
strengths.  It scans validation-only single-action response signatures across
strengths and state bands, then emits recommended strength curves, clipping
flags, saturation flags, side-effect thresholds, and safety-mixing requirements.

Boundary:
    - validates pressure-strength -> action-strength curves
    - uses Task 2-5a correspondence evidence and Task 2-2 response signatures
    - does not build the runtime pressure-to-action converter
    - does not create final actions
    - does not create ActionFrame
    - does not call ActionPlanner, ActionModule, or world runtime
    - marks output as validation evidence, not runtime policy input
"""
from __future__ import annotations

import json
import math

import pandas as pd

from .pressure_action_calibration_rc1 import (
    _pressure_alignment_for_effect,
    _probe_action_effect,
    _side_effect_burden,
    _synthetic_action_frame,
)
from .pressure_action_task2_5a_single_action_correspondence import (
    ACTION_CHANNEL_JA,
    build_single_action_to_pressure_correspondence_table,
)


TASK2_5E_VERSION = "action_strength_curve_validation_rc1"
TASK2_5E_MAPPING_SOURCE = "task2_5a_correspondence_plus_task2_2_strength_scan"
TASK2_5E_CALIBRATION_STATUS = "task2_5e_strength_curve_validation_evidence"
TASK2_5E_CONTRACT = (
    "action_strength_curve_validation__pressure_strength_to_action_strength__"
    "not_pressure_to_action_converter__not_runtime_policy_input__Task2_5e_RC1"
)

STATE_BANDS = ("stable", "medium", "high", "limit")
STATE_BAND_JA = {"stable": "通常", "medium": "中負荷", "high": "高負荷", "limit": "限界"}
STATE_RISK = {"stable": 0.20, "medium": 0.50, "high": 0.78, "limit": 1.00}

PRESSURE_STRENGTH_BANDS = {
    "very_low": 0.10,
    "low": 0.25,
    "medium": 0.50,
    "high": 0.80,
    "limit": 1.00,
}
PRESSURE_STRENGTH_BAND_JA = {
    "very_low": "とても弱い",
    "low": "弱い",
    "medium": "中くらい",
    "high": "強い",
    "limit": "限界",
}

ACTION_STRENGTH_SCAN = (0.015, 0.03, 0.06, 0.09, 0.12, 0.18, 0.24)
BASE_ACTION_STRENGTH_CAP = 0.24
OPENING_ACTIONS = {"exploration_injection", "relation_unlock", "coupling_relief"}
SAFETY_ACTIONS = {"buffer_increase", "volatility_damping"}
PROBE_ACTIONS = {"uncertainty_probe"}

REQUIRED_TASK2_5E_COLUMNS = [
    "task2_5e_version",
    "task2_5e_contract",
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
    "pressure_strength_band",
    "pressure_strength_band_ja",
    "pressure_strength_value",
    "pressure_component",
    "component_direction",
    "pressure_intent_ja",
    "semantic_effect",
    "intent_family",
    "action_channel",
    "action_name_ja",
    "basic_alignment_score",
    "action_to_pressure_share",
    "target_action_strength_unclipped",
    "recommended_action_strength",
    "recommended_strength_curve",
    "action_strength_cap",
    "alignment_score",
    "side_effect_burden",
    "net_strength_utility",
    "saturation_flag",
    "clipping_required",
    "side_effect_increase_point",
    "safe_action_mixing_required",
    "safe_action_mixing_reason",
    "strength_curve_reason",
    "requires_task2_5f_inverse_validation",
    "uses_existing_pressure_intent_semantics",
    "new_semantic_translation_layer_added",
    "diagnostic_compat_policy_used",
    "repaired_diagnostic_policy_used",
]


def _action_strength_cap(action_channel: str, state_band: str) -> float:
    risk = STATE_RISK[str(state_band)]
    action = str(action_channel)
    if action in OPENING_ACTIONS:
        return float(max(0.045, BASE_ACTION_STRENGTH_CAP * (1.0 - 0.62 * risk)))
    if action in SAFETY_ACTIONS:
        return float(BASE_ACTION_STRENGTH_CAP * (0.90 + 0.10 * risk))
    if action in PROBE_ACTIONS:
        return float(BASE_ACTION_STRENGTH_CAP * (0.70 + 0.05 * risk))
    return BASE_ACTION_STRENGTH_CAP


def _target_strength(pressure_strength: float, action_share: float, action_channel: str) -> float:
    action = str(action_channel)
    base = float(pressure_strength) * BASE_ACTION_STRENGTH_CAP
    # The share should influence strength, but must not erase weak-but-relevant
    # candidates entirely.  Task 2-5d already handles candidate-set filtering;
    # Task 2-5e focuses on strength shape once a candidate exists.
    share_gain = 0.55 + 0.45 * math.sqrt(max(float(action_share), 0.0))
    if action in SAFETY_ACTIONS:
        share_gain = max(share_gain, 0.78)
    if action in OPENING_ACTIONS:
        share_gain = min(share_gain, 0.92)
    return float(base * share_gain)


def _response_row(action_channel: str, state_band: str, strength: float) -> dict:
    baseline = _probe_action_effect(_synthetic_action_frame(str(state_band), "no_op", 25, float(strength)))
    effect = _probe_action_effect(_synthetic_action_frame(str(state_band), str(action_channel), 25, float(strength)))
    row = {
        **effect,
        "delta_vs_no_op_exploration": float(effect["exploration_delta"] - baseline["exploration_delta"]),
        "delta_vs_no_op_reversibility": float(effect["reversibility_delta"] - baseline["reversibility_delta"]),
        "delta_vs_no_op_public_effect": float(effect["net_public_effect_score"] - baseline["net_public_effect_score"]),
        "delta_vs_no_op_hidden_effect": float(effect["net_hidden_effect_score"] - baseline["net_hidden_effect_score"]),
        "delta_vs_no_op_hidden_damage": float(effect["hidden_damage_delta"] - baseline["hidden_damage_delta"]),
        "delta_vs_no_op_fatigue": float(effect["fatigue_delta"] - baseline["fatigue_delta"]),
        "delta_vs_no_op_resource_inequality": float(effect["resource_inequality_delta"] - baseline["resource_inequality_delta"]),
        "delta_vs_no_op_reversibility_effect": float(effect["reversibility_delta"] - baseline["reversibility_delta"]),
        "delta_vs_no_op_cost": float(effect["action_cost_effect"] - baseline["action_cost_effect"]),
        "delta_vs_no_op_trust": float(effect["trust_delta"] - baseline["trust_delta"]),
    }
    return row


def _scan_strengths(action_channel: str, state_band: str, semantic_effect: str, intent_family: str) -> pd.DataFrame:
    rows: list[dict] = []
    for strength in ACTION_STRENGTH_SCAN:
        response = _response_row(action_channel, state_band, strength)
        alignment = _pressure_alignment_for_effect(str(semantic_effect), str(intent_family), pd.Series(response))
        burden = _side_effect_burden(response)
        risk = STATE_RISK[str(state_band)]
        # Penalize burden more in high-risk states.  This is validation scoring,
        # not a runtime reward function.
        utility = float(alignment - (0.60 + 0.45 * risk) * burden)
        rows.append({
            "action_strength": float(strength),
            "alignment_score": float(alignment),
            "side_effect_burden": float(burden),
            "net_strength_utility": float(utility),
        })
    return pd.DataFrame(rows)


def _side_effect_increase_point(scan: pd.DataFrame, state_band: str, action_channel: str) -> float:
    risk = STATE_RISK[str(state_band)]
    if action_channel in OPENING_ACTIONS:
        threshold = 0.055 + 0.015 * (1.0 - risk)
    elif action_channel in SAFETY_ACTIONS:
        threshold = 0.075 + 0.020 * (1.0 - risk)
    else:
        threshold = 0.050 + 0.015 * (1.0 - risk)
    rows = scan[pd.to_numeric(scan["side_effect_burden"], errors="coerce") >= threshold]
    if rows.empty:
        return float(ACTION_STRENGTH_SCAN[-1])
    return float(rows.sort_values("action_strength")["action_strength"].iloc[0])


def _select_strength(scan: pd.DataFrame, target_unclipped: float, cap: float) -> pd.Series:
    allowed = scan[pd.to_numeric(scan["action_strength"], errors="coerce") <= float(cap) + 1e-12].copy()
    if allowed.empty:
        allowed = scan.sort_values("action_strength").head(1).copy()
    allowed["target_distance"] = (pd.to_numeric(allowed["action_strength"], errors="coerce") - float(target_unclipped)).abs()
    # Prefer positive utility. If all utility is negative, choose the smallest
    # burden and weakest action rather than maximizing harm.
    positive = allowed[pd.to_numeric(allowed["net_strength_utility"], errors="coerce") >= 0.0].copy()
    choice_pool = positive if not positive.empty else allowed.copy()
    choice_pool = choice_pool.sort_values(
        ["target_distance", "net_strength_utility", "side_effect_burden", "action_strength"],
        ascending=[True, False, True, True],
    )
    return choice_pool.iloc[0]


def _curve_name(action_channel: str, state_band: str, clipping_required: bool, saturation_flag: bool, safe_mix: bool) -> str:
    if safe_mix:
        return "saturating_with_safety_mixing"
    if action_channel in OPENING_ACTIONS and str(state_band) in {"high", "limit"}:
        return "opening_action_low_cap_saturation"
    if clipping_required:
        return "clipped_saturating_curve"
    if saturation_flag:
        return "soft_saturation_curve"
    if action_channel in SAFETY_ACTIONS:
        return "linear_to_safety_cap"
    return "bounded_near_linear_curve"


def _curve_reason(action_channel: str, state_band: str, pressure_band: str, clipping: bool, side_point: float, recommended: float) -> str:
    action_ja = ACTION_CHANNEL_JA.get(action_channel, action_channel)
    if clipping:
        return f"{action_ja}は{STATE_BAND_JA.get(state_band, state_band)}で強くしすぎると副作用または上限に近づくため、推奨強度を丸める。"
    if side_point <= recommended + 1e-12:
        return f"{action_ja}はこの強度帯で副作用増加点に近いため、Task 2-5fで逆変換確認が必要。"
    if pressure_band in {"high", "limit"}:
        return f"圧は強いが、{action_ja}を比例で強め切らず、有界な強度曲線として扱う。"
    return f"{action_ja}はこの圧強度帯では基本対応を保ったまま弱〜中程度で作用させる。"


def build_action_strength_curve_validation_table(
    correspondence: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build Task 2-5e pressure-strength -> action-strength validation rows."""
    corr = build_single_action_to_pressure_correspondence_table() if correspondence is None else correspondence.copy()
    if corr.empty:
        return pd.DataFrame(columns=REQUIRED_TASK2_5E_COLUMNS)
    positive = corr[pd.to_numeric(corr["basic_alignment_score"], errors="coerce").fillna(0.0) > 0.0].copy()

    rows: list[dict] = []
    for _, corr_row in positive.iterrows():
        action = str(corr_row["action_channel"])
        action_share = float(corr_row["action_to_pressure_share"])
        semantic_effect = str(corr_row["semantic_effect"])
        intent_family = str(corr_row["intent_family"])
        for state_band in STATE_BANDS:
            cap = _action_strength_cap(action, state_band)
            scan = _scan_strengths(action, state_band, semantic_effect, intent_family)
            side_point = _side_effect_increase_point(scan, state_band, action)
            for pressure_band, pressure_strength in PRESSURE_STRENGTH_BANDS.items():
                target = _target_strength(float(pressure_strength), action_share, action)
                choice = _select_strength(scan, target, cap)
                recommended = float(choice["action_strength"])
                clipping = bool(target > cap + 1e-12 or recommended < target * 0.82)
                saturation = bool(pressure_band in {"high", "limit"} and recommended >= min(cap, side_point) * 0.82)
                safe_mix = bool(action in OPENING_ACTIONS and state_band in {"high", "limit"} and pressure_band in {"high", "limit"})
                curve_name = _curve_name(action, state_band, clipping, saturation, safe_mix)
                rows.append({
                    "task2_5e_version": TASK2_5E_VERSION,
                    "task2_5e_contract": TASK2_5E_CONTRACT,
                    "validation_type": "action_strength_curve_validation",
                    "validation_only": True,
                    "runtime_policy_input": False,
                    "pressure_to_action_converter_created": False,
                    "final_action_decision": False,
                    "action_frame_created": False,
                    "actionmodule_called": False,
                    "mapping_source": TASK2_5E_MAPPING_SOURCE,
                    "calibration_status": TASK2_5E_CALIBRATION_STATUS,
                    "scenario_or_state_band": state_band,
                    "state_band_ja": STATE_BAND_JA[state_band],
                    "pressure_strength_band": pressure_band,
                    "pressure_strength_band_ja": PRESSURE_STRENGTH_BAND_JA[pressure_band],
                    "pressure_strength_value": float(pressure_strength),
                    "pressure_component": str(corr_row["pressure_component"]),
                    "component_direction": str(corr_row["component_direction"]),
                    "pressure_intent_ja": str(corr_row["pressure_intent_ja"]),
                    "semantic_effect": semantic_effect,
                    "intent_family": intent_family,
                    "action_channel": action,
                    "action_name_ja": ACTION_CHANNEL_JA.get(action, action),
                    "basic_alignment_score": float(corr_row["basic_alignment_score"]),
                    "action_to_pressure_share": action_share,
                    "target_action_strength_unclipped": float(target),
                    "recommended_action_strength": recommended,
                    "recommended_strength_curve": curve_name,
                    "action_strength_cap": float(cap),
                    "alignment_score": float(choice["alignment_score"]),
                    "side_effect_burden": float(choice["side_effect_burden"]),
                    "net_strength_utility": float(choice["net_strength_utility"]),
                    "saturation_flag": saturation,
                    "clipping_required": clipping,
                    "side_effect_increase_point": float(side_point),
                    "safe_action_mixing_required": safe_mix,
                    "safe_action_mixing_reason": (
                        "高負荷以上で開口系作用を強い圧に比例させないため、安全側作用の混入を確認する。"
                        if safe_mix else "安全側作用の混入はこの行では必須ではない。"
                    ),
                    "strength_curve_reason": _curve_reason(action, state_band, pressure_band, clipping, side_point, recommended),
                    "requires_task2_5f_inverse_validation": bool(clipping or saturation or safe_mix or float(choice["net_strength_utility"]) < 0.0),
                    "uses_existing_pressure_intent_semantics": True,
                    "new_semantic_translation_layer_added": False,
                    "diagnostic_compat_policy_used": False,
                    "repaired_diagnostic_policy_used": False,
                })
    out = pd.DataFrame(rows)
    return out[REQUIRED_TASK2_5E_COLUMNS]


def validate_action_strength_curve_validation_table(df: pd.DataFrame) -> list[str]:
    """Return validation errors for the Task 2-5e table."""
    errors: list[str] = []
    if df is None or df.empty:
        return ["task2_5e_strength_curve_table_empty"]
    missing = sorted(set(REQUIRED_TASK2_5E_COLUMNS) - set(df.columns))
    if missing:
        errors.append(f"task2_5e_required_columns_missing:{','.join(missing)}")
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
            errors.append(f"task2_5e_forbidden_true_field:{field}")

    if not bool(df["validation_only"].astype(bool).all()):
        errors.append("task2_5e_not_all_validation_only")
    if not bool(df["uses_existing_pressure_intent_semantics"].astype(bool).all()):
        errors.append("task2_5e_pressure_intent_semantics_not_preserved")

    for col in [
        "pressure_strength_value",
        "target_action_strength_unclipped",
        "recommended_action_strength",
        "action_strength_cap",
        "alignment_score",
        "side_effect_burden",
        "side_effect_increase_point",
    ]:
        values = pd.to_numeric(df[col], errors="coerce")
        if bool(values.isna().any() or (values < 0.0).any()):
            errors.append(f"task2_5e_invalid_nonnegative_score:{col}")

    if bool((pd.to_numeric(df["recommended_action_strength"], errors="coerce") > pd.to_numeric(df["action_strength_cap"], errors="coerce") + 1e-12).any()):
        errors.append("task2_5e_recommended_strength_above_cap")

    expected_bands = set(PRESSURE_STRENGTH_BANDS)
    observed_bands = set(df["pressure_strength_band"].astype(str))
    if expected_bands - observed_bands:
        errors.append("task2_5e_missing_pressure_strength_bands:" + ",".join(sorted(expected_bands - observed_bands)))
    if set(STATE_BANDS) - set(df["scenario_or_state_band"].astype(str)):
        errors.append("task2_5e_missing_state_bands")

    if not bool(df["clipping_required"].astype(bool).any()):
        errors.append("task2_5e_no_clipping_rules_detected")
    if not bool(df["saturation_flag"].astype(bool).any()):
        errors.append("task2_5e_no_saturation_rules_detected")
    if not bool(df["safe_action_mixing_required"].astype(bool).any()):
        errors.append("task2_5e_no_safe_action_mixing_requirements")
    if not bool(df["requires_task2_5f_inverse_validation"].astype(bool).any()):
        errors.append("task2_5e_no_inverse_validation_flags")

    high_limit_opening = df[
        df["action_channel"].astype(str).isin(OPENING_ACTIONS)
        & df["scenario_or_state_band"].astype(str).isin({"high", "limit"})
        & df["pressure_strength_band"].astype(str).isin({"high", "limit"})
    ]
    if high_limit_opening.empty:
        errors.append("task2_5e_missing_high_limit_opening_rows")
    elif not bool(high_limit_opening["clipping_required"].astype(bool).any()):
        errors.append("task2_5e_high_limit_opening_not_clipped")

    return errors


def build_and_validate_action_strength_curve_validation_table() -> tuple[pd.DataFrame, list[str]]:
    df = build_action_strength_curve_validation_table()
    return df, validate_action_strength_curve_validation_table(df)
