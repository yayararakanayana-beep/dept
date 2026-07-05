"""Task 2-5f: inverse validation for pressure-action conversion.

Task: ActionModule UpperPressure Reception Split RC1 / Task 2-5f.

This module closes the validation loop locally:

    pressure input -> candidate action set -> validation-local result synthesis
    -> reconstructed pressure effect -> pressure-intent alignment audit

It uses Task 2-5d pressure-mix rows and Task 2-5e strength-curve rows.  It does
not build the runtime pressure-to-action conversion function and does not call
ActionModule or the world runtime.

Boundary:
    - validates whether generated candidate sets reconstruct the input pressure intent
    - uses validation-local synthetic response signatures only
    - does not create final actions
    - does not create ActionFrame
    - does not call ActionPlanner, ActionModule, or world runtime
    - marks output as validation evidence, not runtime policy input
"""
from __future__ import annotations

import json
from itertools import combinations

import pandas as pd

from .pressure_action_calibration_rc1 import (
    _pressure_alignment_for_effect,
    _probe_action_effect,
    _side_effect_burden,
    _synthetic_action_frame,
)
from .pressure_action_task2_5a_single_action_correspondence import (
    ACTION_CHANNEL_JA,
    PRESSURE_COMPONENT_JA,
    build_single_action_to_pressure_correspondence_table,
)
from .pressure_action_task2_5c_interaction_modifier_validation import build_interaction_modifier_validation_table
from .pressure_action_task2_5d_pressure_mix_validation import build_pressure_mix_validation_table
from .pressure_action_task2_5e_strength_curve_validation import build_action_strength_curve_validation_table


TASK2_5F_VERSION = "inverse_pressure_action_validation_rc1"
TASK2_5F_MAPPING_SOURCE = "task2_5d_pressure_mix_plus_task2_5e_strength_curve_validation"
TASK2_5F_CALIBRATION_STATUS = "task2_5f_inverse_validation_evidence"
TASK2_5F_CONTRACT = (
    "inverse_pressure_action_validation__pressure_to_candidates_to_result_to_pressure__"
    "not_pressure_to_action_converter__not_runtime_policy_input__Task2_5f_RC1"
)

STATE_BAND_JA = {"stable": "通常", "medium": "中負荷", "high": "高負荷", "limit": "限界"}
STATE_RISK = {"stable": 0.20, "medium": 0.50, "high": 0.78, "limit": 1.00}

OPENING_ACTIONS = {"exploration_injection", "relation_unlock", "coupling_relief"}
SAFETY_ACTIONS = {"buffer_increase", "volatility_damping"}
PROBE_ACTIONS = {"uncertainty_probe"}

AGGREGATE_RESPONSE_FIELDS = (
    "delta_vs_no_op_exploration",
    "delta_vs_no_op_reversibility",
    "delta_vs_no_op_public_effect",
    "delta_vs_no_op_hidden_effect",
    "delta_vs_no_op_hidden_damage",
    "delta_vs_no_op_fatigue",
    "delta_vs_no_op_resource_inequality",
    "delta_vs_no_op_cost",
    "delta_vs_no_op_trust",
    "net_hidden_effect_score",
    "hidden_damage_delta",
    "fatigue_delta",
    "resource_inequality_delta",
    "action_cost_effect",
    "reversibility_delta",
    "exploration_delta",
)

REQUIRED_TASK2_5F_COLUMNS = [
    "task2_5f_version",
    "task2_5f_contract",
    "validation_type",
    "validation_only",
    "runtime_policy_input",
    "validation_synthesis_only",
    "pressure_to_action_converter_created",
    "final_action_decision",
    "action_frame_created",
    "actionmodule_called",
    "world_runtime_called",
    "mapping_source",
    "calibration_status",
    "pressure_input_id",
    "pressure_mix_ja",
    "scenario_or_state_band",
    "state_band_ja",
    "pressure_components",
    "candidate_action_set",
    "candidate_action_set_ja",
    "applied_action_set",
    "applied_action_set_ja",
    "applied_action_strength_json",
    "result_trace_json",
    "reconstructed_pressure_effect_json",
    "intent_alignment_score",
    "side_effect_burden",
    "recoverability_score",
    "exploration_preservation_score",
    "overfixation_risk",
    "divergence_risk",
    "rollback_required",
    "inverse_validation_status",
    "recommended_post_filtering",
    "unsafe_interaction_pairs",
    "requires_task2_6_converter_caution",
    "uses_existing_pressure_intent_semantics",
    "new_semantic_translation_layer_added",
    "diagnostic_compat_policy_used",
    "repaired_diagnostic_policy_used",
]


def _parse_json_list(value: object) -> list[str]:
    try:
        parsed = json.loads(str(value))
        if isinstance(parsed, list):
            return [str(x) for x in parsed]
    except Exception:
        return []
    return []


def _parse_json_dict(value: object) -> dict[str, float]:
    try:
        parsed = json.loads(str(value))
        if isinstance(parsed, dict):
            return {str(k): float(v) for k, v in parsed.items()}
    except Exception:
        return {}
    return {}


def _pressure_key(component: str, direction: str) -> str:
    return f"{component}:{direction}"


def _nearest_pressure_strength_band(strength: float) -> str:
    bands = {
        "very_low": 0.10,
        "low": 0.25,
        "medium": 0.50,
        "high": 0.80,
        "limit": 1.00,
    }
    return min(bands, key=lambda name: abs(float(strength) - bands[name]))


def _choose_action_strengths(
    mix_row: pd.Series,
    strength_curves: pd.DataFrame,
    correspondence: pd.DataFrame,
) -> dict[str, float]:
    actions = _parse_json_list(mix_row.get("candidate_action_set", "[]"))
    strengths = _parse_json_dict(mix_row.get("pressure_strength_vector", "{}"))
    state_band = str(mix_row["scenario_or_state_band"])
    chosen: dict[str, float] = {}
    for action in actions:
        action_rows: list[pd.DataFrame] = []
        for key, pressure_strength in strengths.items():
            if ":" not in key:
                continue
            component, direction = key.split(":", 1)
            pressure_band = _nearest_pressure_strength_band(float(pressure_strength))
            rows = strength_curves[
                (strength_curves["scenario_or_state_band"].astype(str) == state_band)
                & (strength_curves["pressure_component"].astype(str) == component)
                & (strength_curves["component_direction"].astype(str) == direction)
                & (strength_curves["action_channel"].astype(str) == action)
                & (strength_curves["pressure_strength_band"].astype(str) == pressure_band)
            ]
            if not rows.empty:
                action_rows.append(rows)
        if action_rows:
            all_rows = pd.concat(action_rows, ignore_index=True)
            chosen[action] = float(pd.to_numeric(all_rows["recommended_action_strength"], errors="coerce").fillna(0.0).max())
        else:
            # Fallback for weak audit candidates that were surfaced by Task 2-5d
            # but do not have a direct curve row for the exact pressure component.
            candidate_scores = _parse_json_dict(mix_row.get("candidate_score_json", "{}"))
            chosen[action] = float(min(0.045, max(0.015, candidate_scores.get(action, 0.018))))
    return chosen


def _response_for_action(action: str, state_band: str, strength: float) -> dict:
    baseline = _probe_action_effect(_synthetic_action_frame(str(state_band), "no_op", 31, float(strength)))
    effect = _probe_action_effect(_synthetic_action_frame(str(state_band), str(action), 31, float(strength)))
    return {
        "delta_vs_no_op_exploration": float(effect["exploration_delta"] - baseline["exploration_delta"]),
        "delta_vs_no_op_reversibility": float(effect["reversibility_delta"] - baseline["reversibility_delta"]),
        "delta_vs_no_op_public_effect": float(effect["net_public_effect_score"] - baseline["net_public_effect_score"]),
        "delta_vs_no_op_hidden_effect": float(effect["net_hidden_effect_score"] - baseline["net_hidden_effect_score"]),
        "delta_vs_no_op_hidden_damage": float(effect["hidden_damage_delta"] - baseline["hidden_damage_delta"]),
        "delta_vs_no_op_fatigue": float(effect["fatigue_delta"] - baseline["fatigue_delta"]),
        "delta_vs_no_op_resource_inequality": float(effect["resource_inequality_delta"] - baseline["resource_inequality_delta"]),
        "delta_vs_no_op_cost": float(effect["action_cost_effect"] - baseline["action_cost_effect"]),
        "delta_vs_no_op_trust": float(effect["trust_delta"] - baseline["trust_delta"]),
        "net_hidden_effect_score": float(effect["net_hidden_effect_score"]),
        "hidden_damage_delta": float(effect["hidden_damage_delta"]),
        "fatigue_delta": float(effect["fatigue_delta"]),
        "resource_inequality_delta": float(effect["resource_inequality_delta"]),
        "action_cost_effect": float(effect["action_cost_effect"]),
        "reversibility_delta": float(effect["reversibility_delta"]),
        "exploration_delta": float(effect["exploration_delta"]),
    }


def _interaction_penalty_and_pairs(actions: list[str], state_band: str, interactions: pd.DataFrame) -> tuple[float, list[str]]:
    penalty = 0.0
    pairs: list[str] = []
    for a, b in combinations(sorted(actions), 2):
        rows = interactions[
            (interactions["scenario_or_state_band"].astype(str) == state_band)
            & interactions["action_pair"].astype(str).isin([f"{a}+{b}", f"{b}+{a}"])
        ]
        if rows.empty:
            continue
        row = rows.iloc[0]
        modifier = float(row.get("interaction_modifier", 1.0))
        side = float(row.get("side_effect_amplification_score", 0.0))
        if modifier < 1.0:
            penalty += 1.0 - modifier
            pairs.append(str(row.get("action_pair_ja", f"{a}+{b}")))
        penalty += side
    return float(penalty), pairs


def _synthesize_result_trace(
    action_strengths: dict[str, float],
    state_band: str,
    interactions: pd.DataFrame,
) -> tuple[dict[str, float], list[str], float]:
    aggregate = {field: 0.0 for field in AGGREGATE_RESPONSE_FIELDS}
    for action, strength in action_strengths.items():
        response = _response_for_action(action, state_band, strength)
        for field in AGGREGATE_RESPONSE_FIELDS:
            aggregate[field] += float(response.get(field, 0.0))
    interaction_penalty, unsafe_pairs = _interaction_penalty_and_pairs(list(action_strengths), state_band, interactions)
    if interaction_penalty > 0.0:
        aggregate["delta_vs_no_op_hidden_effect"] += 0.018 * interaction_penalty
        aggregate["delta_vs_no_op_hidden_damage"] += 0.012 * interaction_penalty
        aggregate["delta_vs_no_op_fatigue"] += 0.012 * interaction_penalty
        aggregate["net_hidden_effect_score"] += 0.018 * interaction_penalty
        aggregate["hidden_damage_delta"] += 0.012 * interaction_penalty
        aggregate["fatigue_delta"] += 0.012 * interaction_penalty
        aggregate["delta_vs_no_op_trust"] -= 0.010 * interaction_penalty
    return aggregate, unsafe_pairs, float(interaction_penalty)


def _reconstruct_pressure_effects(
    mix_row: pd.Series,
    correspondence: pd.DataFrame,
    aggregate_response: dict[str, float],
) -> dict[str, float]:
    strengths = _parse_json_dict(mix_row.get("pressure_strength_vector", "{}"))
    reconstructed: dict[str, float] = {}
    for key, pressure_strength in strengths.items():
        if ":" not in key:
            continue
        component, direction = key.split(":", 1)
        rows = correspondence[
            (correspondence["pressure_component"].astype(str) == component)
            & (correspondence["component_direction"].astype(str) == direction)
        ]
        if rows.empty:
            reconstructed[key] = 0.0
            continue
        row = rows.sort_values("basic_alignment_score", ascending=False).iloc[0]
        raw_alignment = _pressure_alignment_for_effect(
            str(row["semantic_effect"]),
            str(row["intent_family"]),
            pd.Series(aggregate_response),
        )
        # Normalize against pressure demand while keeping the score bounded.  This
        # is a validation-local comparison, not a runtime acceptance rule.
        demand = 0.018 + 0.080 * float(pressure_strength)
        reconstructed[key] = float(max(0.0, min(1.0, raw_alignment / demand)))
    return reconstructed


def _result_metrics(
    aggregate: dict[str, float],
    actions: list[str],
    state_band: str,
    interaction_penalty: float,
    alignment: float,
) -> tuple[float, float, float, float, bool, str, str, bool]:
    burden = _side_effect_burden(aggregate)
    reversibility = float(aggregate.get("delta_vs_no_op_reversibility", 0.0))
    exploration = float(aggregate.get("delta_vs_no_op_exploration", 0.0))
    recoverability = float(max(0.0, min(1.0, 0.50 + 3.0 * reversibility - 2.0 * burden)))
    exploration_preservation = float(max(0.0, min(1.0, 0.50 + 2.0 * exploration - 0.40 * len(set(actions) & SAFETY_ACTIONS))))
    safety_count = len(set(actions) & SAFETY_ACTIONS)
    opening_count = len(set(actions) & OPENING_ACTIONS)
    overfixation = float(max(0.0, min(1.0, 0.18 * safety_count + 0.35 * max(-exploration, 0.0) - 0.10 * opening_count)))
    divergence = float(max(0.0, min(1.0, 1.6 * burden + 0.25 * interaction_penalty + 0.12 * opening_count * STATE_RISK[str(state_band)])))
    rollback_required = bool(divergence >= 0.45 or (alignment < 0.45 and burden > 0.025) or recoverability < 0.25)
    if divergence >= 0.55:
        status = "risky_misalignment"
        filtering = "remove_or_defer_high_risk_interactions_then_recompute"
    elif alignment < 0.45:
        status = "weak_alignment"
        filtering = "increase_coverage_or_add_probe_before_runtime_conversion"
    elif rollback_required:
        status = "aligned_but_requires_rollback_guard"
        filtering = "keep_only_with_rollback_guard_and_strength_cap"
    else:
        status = "aligned_within_validation_scope"
        filtering = "candidate_set_can_feed_task2_6_design"
    return burden, recoverability, exploration_preservation, overfixation, rollback_required, status, filtering, bool(divergence >= 0.35)


def _pressure_components_ja(mix_row: pd.Series) -> str:
    parsed = _parse_json_dict(mix_row.get("pressure_strength_vector", "{}"))
    labels = []
    for key in parsed:
        if ":" not in key:
            continue
        component, direction = key.split(":", 1)
        comp_ja = PRESSURE_COMPONENT_JA.get(component, component)
        dir_ja = "上げる" if direction == "increase" else "下げる"
        labels.append(f"{comp_ja}を{dir_ja}圧")
    return json.dumps(labels, ensure_ascii=False)


def build_inverse_pressure_action_validation_table(
    pressure_mix_table: pd.DataFrame | None = None,
    strength_curves: pd.DataFrame | None = None,
    correspondence: pd.DataFrame | None = None,
    interactions: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build Task 2-5f inverse validation rows."""
    mix_table = build_pressure_mix_validation_table() if pressure_mix_table is None else pressure_mix_table.copy()
    curves = build_action_strength_curve_validation_table() if strength_curves is None else strength_curves.copy()
    corr = build_single_action_to_pressure_correspondence_table() if correspondence is None else correspondence.copy()
    inter = build_interaction_modifier_validation_table() if interactions is None else interactions.copy()
    if mix_table.empty or curves.empty or corr.empty or inter.empty:
        return pd.DataFrame(columns=REQUIRED_TASK2_5F_COLUMNS)

    rows: list[dict] = []
    for _, mix_row in mix_table.iterrows():
        state_band = str(mix_row["scenario_or_state_band"])
        action_strengths = _choose_action_strengths(mix_row, curves, corr)
        actions = list(action_strengths.keys())
        aggregate, unsafe_pairs, interaction_penalty = _synthesize_result_trace(action_strengths, state_band, inter)
        reconstructed = _reconstruct_pressure_effects(mix_row, corr, aggregate)
        intent_alignment = float(sum(reconstructed.values()) / max(len(reconstructed), 1))
        burden, recoverability, exploration_preservation, overfixation, rollback_required, status, filtering, high_divergence = _result_metrics(
            aggregate, actions, state_band, interaction_penalty, intent_alignment
        )
        divergence = float(max(0.0, min(1.0, 1.6 * burden + 0.25 * interaction_penalty + 0.12 * len(set(actions) & OPENING_ACTIONS) * STATE_RISK[state_band])))
        rows.append({
            "task2_5f_version": TASK2_5F_VERSION,
            "task2_5f_contract": TASK2_5F_CONTRACT,
            "validation_type": "inverse_pressure_action_validation",
            "validation_only": True,
            "runtime_policy_input": False,
            "validation_synthesis_only": True,
            "pressure_to_action_converter_created": False,
            "final_action_decision": False,
            "action_frame_created": False,
            "actionmodule_called": False,
            "world_runtime_called": False,
            "mapping_source": TASK2_5F_MAPPING_SOURCE,
            "calibration_status": TASK2_5F_CALIBRATION_STATUS,
            "pressure_input_id": str(mix_row["pressure_mix_id"]),
            "pressure_mix_ja": str(mix_row["pressure_mix_ja"]),
            "scenario_or_state_band": state_band,
            "state_band_ja": STATE_BAND_JA.get(state_band, state_band),
            "pressure_components": _pressure_components_ja(mix_row),
            "candidate_action_set": str(mix_row["candidate_action_set"]),
            "candidate_action_set_ja": str(mix_row["candidate_action_set_ja"]),
            "applied_action_set": json.dumps(actions, ensure_ascii=False),
            "applied_action_set_ja": json.dumps([ACTION_CHANNEL_JA.get(a, a) for a in actions], ensure_ascii=False),
            "applied_action_strength_json": json.dumps(action_strengths, ensure_ascii=False, sort_keys=True),
            "result_trace_json": json.dumps(aggregate, ensure_ascii=False, sort_keys=True),
            "reconstructed_pressure_effect_json": json.dumps(reconstructed, ensure_ascii=False, sort_keys=True),
            "intent_alignment_score": intent_alignment,
            "side_effect_burden": float(burden),
            "recoverability_score": float(recoverability),
            "exploration_preservation_score": float(exploration_preservation),
            "overfixation_risk": float(overfixation),
            "divergence_risk": float(divergence),
            "rollback_required": bool(rollback_required),
            "inverse_validation_status": status,
            "recommended_post_filtering": filtering,
            "unsafe_interaction_pairs": json.dumps(unsafe_pairs, ensure_ascii=False),
            "requires_task2_6_converter_caution": bool(status != "aligned_within_validation_scope" or high_divergence or unsafe_pairs),
            "uses_existing_pressure_intent_semantics": True,
            "new_semantic_translation_layer_added": False,
            "diagnostic_compat_policy_used": False,
            "repaired_diagnostic_policy_used": False,
        })
    out = pd.DataFrame(rows)
    return out[REQUIRED_TASK2_5F_COLUMNS]


def validate_inverse_pressure_action_validation_table(df: pd.DataFrame) -> list[str]:
    """Return validation errors for Task 2-5f inverse validation."""
    errors: list[str] = []
    if df is None or df.empty:
        return ["task2_5f_inverse_validation_table_empty"]
    missing = sorted(set(REQUIRED_TASK2_5F_COLUMNS) - set(df.columns))
    if missing:
        errors.append(f"task2_5f_required_columns_missing:{','.join(missing)}")
        return errors

    false_fields = [
        "runtime_policy_input",
        "pressure_to_action_converter_created",
        "final_action_decision",
        "action_frame_created",
        "actionmodule_called",
        "world_runtime_called",
        "new_semantic_translation_layer_added",
        "diagnostic_compat_policy_used",
        "repaired_diagnostic_policy_used",
    ]
    for field in false_fields:
        if bool(df[field].astype(bool).any()):
            errors.append(f"task2_5f_forbidden_true_field:{field}")

    if not bool(df["validation_only"].astype(bool).all()):
        errors.append("task2_5f_not_all_validation_only")
    if not bool(df["validation_synthesis_only"].astype(bool).all()):
        errors.append("task2_5f_not_marked_validation_synthesis_only")
    if not bool(df["uses_existing_pressure_intent_semantics"].astype(bool).all()):
        errors.append("task2_5f_pressure_intent_semantics_not_preserved")

    for col in [
        "intent_alignment_score",
        "side_effect_burden",
        "recoverability_score",
        "exploration_preservation_score",
        "overfixation_risk",
        "divergence_risk",
    ]:
        values = pd.to_numeric(df[col], errors="coerce")
        if bool(values.isna().any() or (values < 0.0).any()):
            errors.append(f"task2_5f_invalid_nonnegative_score:{col}")
        if col != "side_effect_burden" and bool((values > 1.0 + 1e-12).any()):
            errors.append(f"task2_5f_score_above_one:{col}")

    allowed_status = {
        "aligned_within_validation_scope",
        "aligned_but_requires_rollback_guard",
        "weak_alignment",
        "risky_misalignment",
    }
    if not set(df["inverse_validation_status"].astype(str)).issubset(allowed_status):
        errors.append("task2_5f_unknown_inverse_validation_status")

    if bool(pd.to_numeric(df["intent_alignment_score"], errors="coerce").fillna(0.0).le(0.0).all()):
        errors.append("task2_5f_all_intent_alignment_zero")
    if not bool(df["requires_task2_6_converter_caution"].astype(bool).any()):
        errors.append("task2_5f_no_task2_6_caution_rows")
    if not bool(df["rollback_required"].astype(bool).any()):
        errors.append("task2_5f_no_rollback_required_rows")

    return errors


def build_and_validate_inverse_pressure_action_validation_table() -> tuple[pd.DataFrame, list[str]]:
    df = build_inverse_pressure_action_validation_table()
    return df, validate_inverse_pressure_action_validation_table(df)
