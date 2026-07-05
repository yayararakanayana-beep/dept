"""Task 2-6: pressure-to-action candidate converter RC1.

Task: ActionModule UpperPressure Reception Split RC1 / Task 2-6.

This module converts pressure intents into action candidates using the validated
Task 2-5 evidence tables.  It intentionally does NOT boost action strength to
force the result to match the pressure magnitude.  If pressure 10 only maps to
an expected result signal of 7, that gap is preserved as information.

Boundary:
    - converts pressure intents into candidate actions when the 6-action
      vocabulary has a supported candidate
    - preserves unsupported pressure intents instead of silently dropping them
    - preserves pressure/result gaps as audit information
    - logs pressure-intent coverage and unresolved intent when the 6-action
      vocabulary is too coarse
    - does not apply action-strength correction
    - does not boost actions to match pressure
    - does not create final actions
    - does not create ActionFrame
    - does not call ActionPlanner, ActionModule, or world runtime
    - does not infer live lower-layer state
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Iterable

import pandas as pd

from .pressure_action_task2_5a_single_action_correspondence import (
    ACTION_CHANNEL_JA,
    build_single_action_to_pressure_correspondence_table,
)
from .pressure_action_task2_5b_state_modifier_validation import build_state_modifier_validation_table
from .pressure_action_task2_5c_interaction_modifier_validation import build_interaction_modifier_validation_table


TASK2_6_CONVERTER_VERSION = "pressure_action_candidate_converter_no_strength_boost_rc1"
TASK2_6_CONTRACT = (
    "pressure_action_candidate_converter__candidate_only__"
    "no_strength_correction__no_pressure_matching_boost__Task2_6_RC1"
)
TASK2_6_MAPPING_SOURCE = "task2_5a_5b_5c_evidence__no_strength_curve_applied"
TASK2_6_CALIBRATION_STATUS = "task2_6_candidate_converter_rc1_not_runtime_connected"

DEFAULT_CANDIDATE_THRESHOLD = 0.018
OPENING_ACTIONS = {"exploration_injection", "relation_unlock", "coupling_relief"}
SAFETY_ACTIONS = {"buffer_increase", "volatility_damping"}
PROBE_ACTIONS = {"uncertainty_probe"}
NO_ACTION_CANDIDATE = "no_action_candidate"

OPENING_INTENT_FAMILIES = {
    "exploration_attempt", "exploration_observation", "adoption_opening",
    "response_opening", "temporal_opening", "update_opening",
    "switching_flexibility", "commitment_relief", "capacity_opening",
}
SAFETY_INTENT_FAMILIES = {
    "safety_guard", "safety_cap", "persistence_guard", "commitment_guard",
    "temporal_brake", "adoption_guard", "response_restraint",
    "exploration_restraint", "probe_restraint", "observation_detail",
}

REQUIRED_PRESSURE_INPUT_COLUMNS = [
    "pressure_component",
    "component_direction",
    "pressure_strength",
]

REQUIRED_TASK2_6_COLUMNS = [
    "task2_6_converter_version",
    "task2_6_contract",
    "conversion_type",
    "candidate_only",
    "runtime_policy_input",
    "final_action_decision",
    "action_frame_created",
    "actionmodule_called",
    "world_runtime_called",
    "pressure_to_action_converter_created",
    "action_strength_correction_applied",
    "pressure_matching_boost_applied",
    "strength_curve_applied",
    "pressure_result_gap_preserved",
    "mapping_source",
    "calibration_status",
    "pressure_input_id",
    "pressure_component",
    "component_direction",
    "pressure_strength",
    "semantic_effect",
    "intent_family",
    "suggested_control_route",
    "action_channel",
    "action_name_ja",
    "basic_alignment_score",
    "action_to_pressure_share",
    "pressure_signal",
    "expected_result_signal",
    "pressure_result_gap",
    "pressure_intent_coverage_score",
    "action_vocabulary_fit_score",
    "action_granularity_insufficient_flag",
    "new_action_channel_candidate_flag",
    "unresolved_pressure_intent",
    "safety_fallback_used",
    "candidate_rank",
    "candidate_status",
    "state_audit_status",
    "state_audit_reason",
    "interaction_audit_status",
    "interaction_audit_reason",
    "unsafe_interaction_pairs",
    "requires_downstream_strength_handling",
    "requires_downstream_gate_review",
    "uses_existing_pressure_intent_semantics",
    "new_semantic_translation_layer_added",
    "diagnostic_compat_policy_used",
    "repaired_diagnostic_policy_used",
]


@dataclass(frozen=True)
class PressureActionConversionConfig:
    """Configuration for Task 2-6 candidate conversion.

    The threshold is a candidate-surfacing threshold only.  It is not an action
    strength rule and must not be used to boost an action.
    """

    candidate_threshold: float = DEFAULT_CANDIDATE_THRESHOLD
    expected_result_ratio: float = 0.70
    preserve_blocked_candidates: bool = True


def _clip01(value: float) -> float:
    return float(max(0.0, min(1.0, float(value))))


def _pressure_input_id(row: pd.Series, index: int) -> str:
    if "pressure_input_id" in row and pd.notna(row["pressure_input_id"]):
        return str(row["pressure_input_id"])
    return f"pressure_input_{index:04d}"


def _validate_pressure_inputs(pressure_inputs: pd.DataFrame) -> None:
    missing = sorted(set(REQUIRED_PRESSURE_INPUT_COLUMNS) - set(pressure_inputs.columns))
    if missing:
        raise ValueError("pressure_input_required_columns_missing:" + ",".join(missing))


def _state_audit_for_action(
    action: str,
    state_axes: Iterable[str],
    state_level: str,
    state_modifiers: pd.DataFrame,
) -> tuple[str, str]:
    if action == NO_ACTION_CANDIDATE:
        return "state_not_applicable_no_action_candidate", "対応する作用候補がないため、状態補正は適用しない。"
    axes = [str(axis) for axis in state_axes]
    if not axes:
        return "state_not_supplied", "状態軸が未指定のため、下位レイヤー未接続として候補強度補正は行わない。"
    rows = state_modifiers[
        (state_modifiers["action_channel"].astype(str) == str(action))
        & (state_modifiers["state_axis"].astype(str).isin(axes))
        & (state_modifiers["state_level"].astype(str) == str(state_level))
    ]
    if rows.empty:
        return "state_not_matched", "対応する状態補正行がないため、候補強度補正は行わない。"
    classes = set(rows["modifier_class"].astype(str))
    reasons = " / ".join(rows["modifier_reason"].astype(str).head(3).tolist())
    if "block" in classes:
        return "blocked_by_state_audit", reasons
    if "defer" in classes:
        return "deferred_by_state_audit", reasons
    if "dampen" in classes:
        return "state_warn_dampen_downstream_only", reasons
    if "boost" in classes:
        return "state_supports_candidate_no_strength_boost", reasons
    return "state_keeps_candidate", reasons


def _interaction_lookup(interactions: pd.DataFrame, action_a: str, action_b: str, state_band: str) -> pd.DataFrame:
    pair1 = f"{action_a}+{action_b}"
    pair2 = f"{action_b}+{action_a}"
    return interactions[
        interactions["scenario_or_state_band"].astype(str).eq(str(state_band))
        & interactions["action_pair"].astype(str).isin([pair1, pair2])
    ]


def _candidate_action_set_from_rows(rows: pd.DataFrame, threshold: float) -> set[str]:
    positive = rows[pd.to_numeric(rows["pressure_signal"], errors="coerce").fillna(0.0) >= float(threshold)]
    if positive.empty and not rows.empty:
        positive = rows.sort_values("pressure_signal", ascending=False).head(1)
    return set(positive["action_channel"].astype(str))


def _interaction_audit_for_action(
    action: str,
    candidate_actions: set[str],
    state_band: str,
    interactions: pd.DataFrame,
) -> tuple[str, str, list[str]]:
    if action == NO_ACTION_CANDIDATE:
        return "interaction_not_applicable_no_action_candidate", "対応する作用候補がないため、相互作用監査は適用しない。", []
    statuses: list[str] = []
    reasons: list[str] = []
    unsafe_pairs: list[str] = []
    for other in sorted(candidate_actions - {str(action)}):
        rows = _interaction_lookup(interactions, str(action), other, state_band)
        if rows.empty:
            continue
        row = rows.iloc[0]
        modifier_class = str(row.get("modifier_class", "keep"))
        interaction_type = str(row.get("interaction_type", "approximately_additive"))
        pair_ja = str(row.get("action_pair_ja", f"{action}+{other}"))
        reason = str(row.get("interaction_reason", "相互作用監査理由なし"))
        if modifier_class == "block":
            statuses.append("blocked_by_interaction_audit")
            unsafe_pairs.append(pair_ja)
        elif modifier_class == "defer":
            statuses.append("deferred_by_interaction_audit")
            unsafe_pairs.append(pair_ja)
        elif modifier_class == "dampen":
            statuses.append("interaction_warn_dampen_downstream_only")
            unsafe_pairs.append(pair_ja)
        elif modifier_class == "boost":
            statuses.append("interaction_supports_candidate_no_strength_boost")
        else:
            statuses.append("interaction_keeps_candidate")
        reasons.append(f"{pair_ja}:{interaction_type}:{reason}")
    if not statuses:
        return "interaction_not_applicable", "危険な相互作用行なし。", []
    if "blocked_by_interaction_audit" in statuses:
        return "blocked_by_interaction_audit", " / ".join(reasons[:3]), unsafe_pairs
    if "deferred_by_interaction_audit" in statuses:
        return "deferred_by_interaction_audit", " / ".join(reasons[:3]), unsafe_pairs
    if "interaction_warn_dampen_downstream_only" in statuses:
        return "interaction_warn_dampen_downstream_only", " / ".join(reasons[:3]), unsafe_pairs
    if "interaction_supports_candidate_no_strength_boost" in statuses:
        return "interaction_supports_candidate_no_strength_boost", " / ".join(reasons[:3]), unsafe_pairs
    return "interaction_keeps_candidate", " / ".join(reasons[:3]), unsafe_pairs


def _candidate_status(state_status: str, interaction_status: str) -> str:
    if "no_action_candidate" in state_status or "no_action_candidate" in interaction_status:
        return "unresolved_pressure_intent_no_action_candidate"
    if state_status.startswith("blocked") or interaction_status.startswith("blocked"):
        return "blocked_candidate_not_final_action"
    if state_status.startswith("deferred") or interaction_status.startswith("deferred"):
        return "deferred_candidate_not_final_action"
    if "warn" in state_status or "warn" in interaction_status:
        return "candidate_requires_downstream_gate_review"
    return "candidate_available_for_downstream_gate"


def _unresolved_payload(effect: str, family: str, route: str, reason: str) -> str:
    return json.dumps({
        "semantic_effect": str(effect),
        "intent_family": str(family),
        "suggested_control_route": str(route),
        "reason": str(reason),
    }, ensure_ascii=False, sort_keys=True)


def _pressure_intent_audit(match: pd.Series, action: str, status: str, pressure_signal: float) -> dict[str, object]:
    """Audit whether the 6-action vocabulary is too coarse for this pressure intent."""
    basic = float(match.get("basic_alignment_score", 0.0) or 0.0)
    share = float(match.get("action_to_pressure_share", 0.0) or 0.0)
    family = str(match.get("intent_family", "unknown"))
    effect = str(match.get("semantic_effect", "unknown"))
    route = str(match.get("suggested_control_route", "unknown"))
    action = str(action)

    if action == NO_ACTION_CANDIDATE:
        return {
            "pressure_intent_coverage_score": 0.0,
            "action_vocabulary_fit_score": 0.0,
            "action_granularity_insufficient_flag": True,
            "new_action_channel_candidate_flag": True,
            "unresolved_pressure_intent": _unresolved_payload(effect, family, route, "6作用語彙に対応する作用候補がない。"),
            "safety_fallback_used": False,
        }

    coverage = _clip01(0.60 * min(1.0, basic) + 0.40 * min(1.0, share * 3.0))
    direct_family_fit = 0.0
    if action == "exploration_injection" and family in {"exploration_attempt", "exploration_observation", "update_opening"}:
        direct_family_fit = 1.0
    elif action == "uncertainty_probe" and family in {"observation_detail", "exploration_observation", "response_opening", "safety_guard"}:
        direct_family_fit = 0.85
    elif action == "volatility_damping" and family in {"safety_guard", "safety_cap", "persistence_guard", "commitment_guard", "temporal_brake"}:
        direct_family_fit = 0.90
    elif action == "buffer_increase" and family in {"safety_guard", "safety_cap", "temporal_brake", "commitment_guard", "observation_detail"}:
        direct_family_fit = 0.90
    elif action == "relation_unlock" and family in {"commitment_relief", "switching_flexibility", "adoption_opening", "response_opening"}:
        direct_family_fit = 0.82
    elif action == "coupling_relief" and family in {"commitment_relief", "switching_flexibility", "adoption_opening", "response_opening", "safety_cap"}:
        direct_family_fit = 0.82
    elif family in OPENING_INTENT_FAMILIES and action in OPENING_ACTIONS:
        direct_family_fit = 0.65
    elif family in SAFETY_INTENT_FAMILIES and action in SAFETY_ACTIONS:
        direct_family_fit = 0.70
    elif action in PROBE_ACTIONS:
        direct_family_fit = 0.55
    elif action in SAFETY_ACTIONS:
        direct_family_fit = 0.45
    else:
        direct_family_fit = 0.35

    fit = _clip01(0.55 * coverage + 0.45 * direct_family_fit)
    safety_fallback = bool(action in SAFETY_ACTIONS and family in OPENING_INTENT_FAMILIES and fit < 0.72)
    granularity_insufficient = bool(fit < 0.62 or ("warn" in str(status) and fit < 0.72))
    new_channel_candidate = bool(fit < 0.50 or (granularity_insufficient and pressure_signal >= DEFAULT_CANDIDATE_THRESHOLD * 2.0))

    unresolved = ""
    if granularity_insufficient or new_channel_candidate or safety_fallback:
        unresolved = _unresolved_payload(effect, family, route, "6作用語彙では圧意味を十分に表現しきれない可能性がある。")

    return {
        "pressure_intent_coverage_score": float(coverage),
        "action_vocabulary_fit_score": float(fit),
        "action_granularity_insufficient_flag": bool(granularity_insufficient),
        "new_action_channel_candidate_flag": bool(new_channel_candidate),
        "unresolved_pressure_intent": unresolved,
        "safety_fallback_used": bool(safety_fallback),
    }


def _fallback_intent_fields(pressure_row: pd.Series, component: str, direction: str) -> tuple[str, str, str]:
    effect = str(pressure_row.get("semantic_effect", f"{component}_{direction}_unmapped"))
    family = str(pressure_row.get("intent_family", "unmapped_pressure_intent"))
    route = str(pressure_row.get("suggested_control_route", "no_supported_route"))
    return effect, family, route


def _unsupported_candidate_row(
    pressure_row: pd.Series,
    pressure_id: str,
    component: str,
    direction: str,
    strength: float,
) -> dict:
    effect, family, route = _fallback_intent_fields(pressure_row, component, direction)
    match = pd.Series({
        "basic_alignment_score": 0.0,
        "action_to_pressure_share": 0.0,
        "semantic_effect": effect,
        "intent_family": family,
        "suggested_control_route": route,
    })
    state_status = "state_not_applicable_no_action_candidate"
    interaction_status = "interaction_not_applicable_no_action_candidate"
    status = _candidate_status(state_status, interaction_status)
    intent_audit = _pressure_intent_audit(match, NO_ACTION_CANDIDATE, status, 0.0)
    return {
        "task2_6_converter_version": TASK2_6_CONVERTER_VERSION,
        "task2_6_contract": TASK2_6_CONTRACT,
        "conversion_type": "pressure_to_action_candidate_conversion_no_strength_boost",
        "candidate_only": True,
        "runtime_policy_input": False,
        "final_action_decision": False,
        "action_frame_created": False,
        "actionmodule_called": False,
        "world_runtime_called": False,
        "pressure_to_action_converter_created": True,
        "action_strength_correction_applied": False,
        "pressure_matching_boost_applied": False,
        "strength_curve_applied": False,
        "pressure_result_gap_preserved": True,
        "mapping_source": TASK2_6_MAPPING_SOURCE,
        "calibration_status": TASK2_6_CALIBRATION_STATUS,
        "pressure_input_id": pressure_id,
        "pressure_component": component,
        "component_direction": direction,
        "pressure_strength": strength,
        "semantic_effect": effect,
        "intent_family": family,
        "suggested_control_route": route,
        "action_channel": NO_ACTION_CANDIDATE,
        "action_name_ja": "対応する作用候補なし",
        "basic_alignment_score": 0.0,
        "action_to_pressure_share": 0.0,
        "pressure_signal": 0.0,
        "expected_result_signal": 0.0,
        "pressure_result_gap": float(abs(strength)),
        **intent_audit,
        "candidate_rank": 9999,
        "candidate_status": status,
        "state_audit_status": state_status,
        "state_audit_reason": "対応する作用候補がないため、状態補正は適用しない。",
        "interaction_audit_status": interaction_status,
        "interaction_audit_reason": "対応する作用候補がないため、相互作用監査は適用しない。",
        "unsafe_interaction_pairs": "[]",
        "requires_downstream_strength_handling": False,
        "requires_downstream_gate_review": True,
        "uses_existing_pressure_intent_semantics": True,
        "new_semantic_translation_layer_added": False,
        "diagnostic_compat_policy_used": False,
        "repaired_diagnostic_policy_used": False,
    }


def convert_pressure_inputs_to_action_candidates(
    pressure_inputs: pd.DataFrame,
    state_axes: Iterable[str] = (),
    state_level: str = "low",
    state_band: str = "stable",
    correspondence: pd.DataFrame | None = None,
    state_modifiers: pd.DataFrame | None = None,
    interactions: pd.DataFrame | None = None,
    config: PressureActionConversionConfig = PressureActionConversionConfig(),
) -> pd.DataFrame:
    """Convert pressure inputs to action candidates without strength boosting."""
    _validate_pressure_inputs(pressure_inputs)
    corr = build_single_action_to_pressure_correspondence_table() if correspondence is None else correspondence.copy()
    state_table = build_state_modifier_validation_table() if state_modifiers is None else state_modifiers.copy()
    interaction_table = build_interaction_modifier_validation_table() if interactions is None else interactions.copy()

    rows: list[dict] = []
    for idx, pressure_row in pressure_inputs.reset_index(drop=True).iterrows():
        pressure_id = _pressure_input_id(pressure_row, int(idx))
        component = str(pressure_row["pressure_component"])
        direction = str(pressure_row["component_direction"])
        strength = float(pressure_row["pressure_strength"])
        matches = corr[
            (corr["pressure_component"].astype(str) == component)
            & (corr["component_direction"].astype(str) == direction)
            & (pd.to_numeric(corr["basic_alignment_score"], errors="coerce").fillna(0.0) > 0.0)
        ].copy()
        if matches.empty:
            rows.append(_unsupported_candidate_row(pressure_row, pressure_id, component, direction, strength))
            continue
        matches["pressure_signal"] = strength * pd.to_numeric(matches["action_to_pressure_share"], errors="coerce").fillna(0.0)
        candidate_actions = _candidate_action_set_from_rows(matches, config.candidate_threshold)
        for _, match in matches.iterrows():
            action = str(match["action_channel"])
            pressure_signal = float(match["pressure_signal"])
            if action not in candidate_actions and pressure_signal < config.candidate_threshold:
                continue
            expected_result_signal = float(pressure_signal * config.expected_result_ratio)
            pressure_gap = float(max(0.0, pressure_signal - expected_result_signal))
            state_status, state_reason = _state_audit_for_action(action, state_axes, state_level, state_table)
            interaction_status, interaction_reason, unsafe_pairs = _interaction_audit_for_action(
                action, candidate_actions, state_band, interaction_table
            )
            status = _candidate_status(state_status, interaction_status)
            intent_audit = _pressure_intent_audit(match, action, status, pressure_signal)
            rows.append({
                "task2_6_converter_version": TASK2_6_CONVERTER_VERSION,
                "task2_6_contract": TASK2_6_CONTRACT,
                "conversion_type": "pressure_to_action_candidate_conversion_no_strength_boost",
                "candidate_only": True,
                "runtime_policy_input": False,
                "final_action_decision": False,
                "action_frame_created": False,
                "actionmodule_called": False,
                "world_runtime_called": False,
                "pressure_to_action_converter_created": True,
                "action_strength_correction_applied": False,
                "pressure_matching_boost_applied": False,
                "strength_curve_applied": False,
                "pressure_result_gap_preserved": True,
                "mapping_source": TASK2_6_MAPPING_SOURCE,
                "calibration_status": TASK2_6_CALIBRATION_STATUS,
                "pressure_input_id": pressure_id,
                "pressure_component": component,
                "component_direction": direction,
                "pressure_strength": strength,
                "semantic_effect": str(match["semantic_effect"]),
                "intent_family": str(match["intent_family"]),
                "suggested_control_route": str(match["suggested_control_route"]),
                "action_channel": action,
                "action_name_ja": ACTION_CHANNEL_JA.get(action, action),
                "basic_alignment_score": float(match["basic_alignment_score"]),
                "action_to_pressure_share": float(match["action_to_pressure_share"]),
                "pressure_signal": pressure_signal,
                "expected_result_signal": expected_result_signal,
                "pressure_result_gap": pressure_gap,
                **intent_audit,
                "candidate_rank": int(match["basic_alignment_rank"]),
                "candidate_status": status,
                "state_audit_status": state_status,
                "state_audit_reason": state_reason,
                "interaction_audit_status": interaction_status,
                "interaction_audit_reason": interaction_reason,
                "unsafe_interaction_pairs": json.dumps(unsafe_pairs, ensure_ascii=False),
                "requires_downstream_strength_handling": True,
                "requires_downstream_gate_review": bool(
                    status != "candidate_available_for_downstream_gate"
                    or bool(intent_audit["action_granularity_insufficient_flag"])
                    or bool(intent_audit["new_action_channel_candidate_flag"])
                ),
                "uses_existing_pressure_intent_semantics": True,
                "new_semantic_translation_layer_added": False,
                "diagnostic_compat_policy_used": False,
                "repaired_diagnostic_policy_used": False,
            })
    out = pd.DataFrame(rows)
    if out.empty:
        return pd.DataFrame(columns=REQUIRED_TASK2_6_COLUMNS)
    out = out.sort_values(["pressure_input_id", "pressure_signal", "candidate_rank"], ascending=[True, False, True]).reset_index(drop=True)
    return out[REQUIRED_TASK2_6_COLUMNS]


def validate_pressure_action_candidates_no_strength_boost(df: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    if df is None or df.empty:
        return ["task2_6_candidate_table_empty"]
    missing = sorted(set(REQUIRED_TASK2_6_COLUMNS) - set(df.columns))
    if missing:
        errors.append("task2_6_required_columns_missing:" + ",".join(missing))
        return errors

    false_fields = [
        "runtime_policy_input",
        "final_action_decision",
        "action_frame_created",
        "actionmodule_called",
        "world_runtime_called",
        "action_strength_correction_applied",
        "pressure_matching_boost_applied",
        "strength_curve_applied",
        "new_semantic_translation_layer_added",
        "diagnostic_compat_policy_used",
        "repaired_diagnostic_policy_used",
    ]
    for field in false_fields:
        if bool(df[field].astype(bool).any()):
            errors.append(f"task2_6_forbidden_true_field:{field}")

    true_fields = [
        "candidate_only",
        "pressure_to_action_converter_created",
        "pressure_result_gap_preserved",
        "uses_existing_pressure_intent_semantics",
    ]
    for field in true_fields:
        if not bool(df[field].astype(bool).all()):
            errors.append(f"task2_6_required_true_field_not_all_true:{field}")

    for col in ["pressure_strength", "pressure_signal", "expected_result_signal", "pressure_result_gap"]:
        values = pd.to_numeric(df[col], errors="coerce")
        if bool(values.isna().any() or (values < 0.0).any()):
            errors.append(f"task2_6_invalid_nonnegative_score:{col}")

    for col in ["pressure_intent_coverage_score", "action_vocabulary_fit_score"]:
        values = pd.to_numeric(df[col], errors="coerce")
        if bool(values.isna().any() or (values < 0.0).any() or (values > 1.0).any()):
            errors.append(f"task2_6_invalid_unit_score:{col}")

    if bool((pd.to_numeric(df["expected_result_signal"], errors="coerce") > pd.to_numeric(df["pressure_signal"], errors="coerce") + 1e-12).any()):
        errors.append("task2_6_expected_result_boosted_above_pressure_signal")
    if not bool((pd.to_numeric(df["pressure_result_gap"], errors="coerce") > 0.0).any()):
        errors.append("task2_6_no_pressure_result_gap_preserved")

    unresolved_required = df[
        df["action_granularity_insufficient_flag"].astype(bool)
        | df["new_action_channel_candidate_flag"].astype(bool)
        | df["safety_fallback_used"].astype(bool)
        | df["candidate_status"].astype(str).eq("unresolved_pressure_intent_no_action_candidate")
    ]
    if not unresolved_required.empty and bool(unresolved_required["unresolved_pressure_intent"].astype(str).str.len().eq(0).any()):
        errors.append("task2_6_unresolved_pressure_intent_missing_for_flagged_rows")

    allowed_status = {
        "candidate_available_for_downstream_gate",
        "candidate_requires_downstream_gate_review",
        "deferred_candidate_not_final_action",
        "blocked_candidate_not_final_action",
        "unresolved_pressure_intent_no_action_candidate",
    }
    if not set(df["candidate_status"].astype(str)).issubset(allowed_status):
        errors.append("task2_6_unknown_candidate_status")

    return errors


def build_demo_pressure_inputs() -> pd.DataFrame:
    """Small deterministic pressure input set for tests and workflow export."""
    return pd.DataFrame([
        {
            "pressure_input_id": "demo_exploration_up",
            "pressure_component": "exploration_frequency",
            "component_direction": "increase",
            "pressure_strength": 5.0,
        },
        {
            "pressure_input_id": "demo_commitment_down_high_pressure",
            "pressure_component": "commitment_strength",
            "component_direction": "decrease",
            "pressure_strength": 10.0,
        },
        {
            "pressure_input_id": "demo_rollback_up",
            "pressure_component": "rollback_sensitivity",
            "component_direction": "increase",
            "pressure_strength": 7.0,
        },
    ])


def build_and_validate_demo_pressure_action_candidates() -> tuple[pd.DataFrame, list[str]]:
    df = convert_pressure_inputs_to_action_candidates(
        build_demo_pressure_inputs(),
        state_axes=("exploration_deficit", "fixation_strength", "oscillation_strength"),
        state_level="high",
        state_band="high",
    )
    return df, validate_pressure_action_candidates_no_strength_boost(df)
