"""pressure_action_calibration_rc1: Task 2-2 pressure-action map calibration.

Task: ActionModule UpperPressure Reception Split RC1 / Task 2-2.

This module builds a validation-only single-action probe response map and uses
it to estimate how much each action channel contributes to each pressure
component direction.  It does not connect the result to the FullSpec runtime
path.  Task 2-3 is responsible for using a calibrated or explicitly
uncalibrated map to create action candidates.

Boundary:
    - validates Action -> result -> pressure-component contribution
    - keeps PressureIntentBundle meanings unchanged
    - does not call diagnostic compatibility policy
    - does not call ActionPlanner or ActionModule runtime
    - does not write world/G/K/O_t/canonical parameters
    - marks outputs as validation evidence, not runtime policy input
"""
from __future__ import annotations

from typing import Iterable

import pandas as pd

from .pressure_action_map_rc1 import build_initial_pressure_action_map


TASK2_2_CALIBRATION_VERSION = "pressure_action_map_single_action_probe_calibration_rc1"
TASK2_2_MAPPING_SOURCE = "single_action_probe_estimated_action_to_pressure_contribution"
TASK2_2_CALIBRATION_STATUS = "single_action_probe_calibrated"
TASK2_2_CONTRACT = (
    "single_action_probe__action_result_to_pressure_component_contribution__"
    "validation_only__not_runtime_policy_input__Task2_2_RC1"
)

STATE_BANDS = ("stable", "medium", "high", "limit")
CHANNELS = (
    "no_op",
    "buffer_increase",
    "coupling_relief",
    "volatility_damping",
    "uncertainty_probe",
    "exploration_injection",
    "relation_unlock",
)
ACTION_STRENGTHS = (0.12,)
CORE_RESPONSE_FIELDS = (
    "exploration_delta",
    "reversibility_delta",
    "net_public_effect_score",
    "net_hidden_effect_score",
    "hidden_damage_delta",
    "fatigue_delta",
    "resource_inequality_delta",
    "action_cost_effect",
)
STATE_RISK = {"stable": 0.20, "medium": 0.50, "high": 0.78, "limit": 1.00}


REQUIRED_CALIBRATED_MAP_COLUMNS = [
    "pressure_action_map_version",
    "mapping_source",
    "calibration_status",
    "calibration_method",
    "sample_count",
    "mapping_confidence",
    "scenario_or_state_band",
    "pressure_component",
    "component_direction",
    "control_domain",
    "semantic_effect",
    "intent_family",
    "suggested_control_route",
    "action_channel",
    "action_primitive",
    "primitive_selection_status",
    "initial_action_share",
    "calibrated_action_share",
    "estimated_pressure_alignment",
    "measured_pressure_alignment_raw",
    "measured_side_effect_burden",
    "measured_reversibility_effect",
    "measured_exploration_effect",
    "measured_public_effect",
    "measured_hidden_effect",
    "response_alignment_score",
    "calibration_fallback_used",
    "pre_calibration_mapping_source",
    "pre_calibration_status",
    "uses_existing_pressure_intent_semantics",
    "new_semantic_translation_layer_added",
    "diagnostic_compat_policy_used",
    "repaired_diagnostic_policy_used",
    "runtime_policy_input",
    "requires_task2_3_candidate_generation",
    "task2_2_contract",
]


def _synthetic_action_frame(state_band: str, channel: str, seed: int, strength: float) -> dict:
    action_strength = 0.0 if channel == "no_op" else float(strength)
    return {
        "entity_id": f"task2-2-{state_band}-{seed}",
        "state_band": state_band,
        "seed": int(seed),
        "action_channel": channel,
        "action_strength": action_strength,
        "direction": "single_action_probe_not_runtime_direction",
        "source_gate_decision": "synthetic_probe_not_runtime_gate",
        "planner_route": "single_action_probe_not_policy_selection",
        "action_primitive": f"probe::{channel}",
        "primitive_sequence": f"single_action_probe::{channel}",
        "primitive_stage": 1,
        "action_scope": "validation_probe_only",
        "duration_steps": 1,
        "rollback_condition": "validation_probe_only_no_runtime_write",
        "dominant_semantic_effect": "not_from_pressure_intent_runtime",
        "dominant_pressure_component": "not_from_pressure_intent_runtime",
        "action_module_contract": "not_ActionModule_runtime_input",
    }


def _probe_action_effect(action_frame: dict) -> dict:
    """Validation-only channel response signature.

    This mirrors the existing channel-level response-map idea but is packaged as
    Task 2-2 calibration input.  It is intentionally not ActionModule runtime.
    """
    channel = str(action_frame["action_channel"])
    risk = float(STATE_RISK[str(action_frame["state_band"])])
    strength = float(action_frame["action_strength"])
    if channel == "no_op":
        return {
            "action_channel": channel,
            "action_intensity": 0.0,
            "target_count": 0,
            "direct_effect_score": 0.0,
            "side_effect_score": 0.0,
            "exploitation_risk_delta": 0.0,
            "trust_delta": 0.0,
            **{field: 0.0 for field in CORE_RESPONSE_FIELDS},
        }

    s = strength
    signatures = {
        "buffer_increase": (0.01, 0.42 * s * (1.05 - 0.20 * risk), 0.10 * s, 0.09 * s * risk, 0.05 * s * risk, 0.06 * s, 0.04 * s, 0.22 * s),
        "coupling_relief": (0.06 * s, 0.18 * s * (1 - 0.10 * risk), 0.16 * s, 0.10 * s + 0.06 * s * risk, 0.05 * s * risk, 0.07 * s * risk, -0.06 * s + 0.16 * s * risk, 0.24 * s),
        "volatility_damping": (-0.08 * s * (1 - risk), 0.24 * s, 0.08 * s, 0.06 * s * (1 - risk), -0.08 * s * risk, -0.10 * s * risk, 0.02 * s, 0.20 * s),
        "uncertainty_probe": (0.05 * s * (1 - 0.30 * risk), 0.07 * s, 0.05 * s, 0.04 * s + 0.08 * s * risk, 0.03 * s * risk, 0.04 * s * risk, 0.02 * s, 0.11 * s),
        "exploration_injection": (0.55 * s * (1 - 0.45 * risk), -0.08 * s * risk, 0.18 * s, 0.10 * s + 0.30 * s * risk, 0.08 * s * risk, 0.12 * s * risk, 0.10 * s * risk, 0.28 * s),
        "relation_unlock": (0.08 * s, 0.12 * s - 0.25 * s * risk, 0.18 * s * (1 - 0.20 * risk), 0.12 * s + 0.34 * s * risk, 0.09 * s * risk, 0.13 * s * risk, 0.05 * s + 0.18 * s * risk, 0.30 * s),
    }
    exploration, reversibility, public, hidden, damage, fatigue, inequality, cost = signatures[channel]
    side_effect = abs(hidden) + max(damage, 0.0) + max(fatigue, 0.0) + max(inequality, 0.0)
    direct = public + max(exploration, 0.0) + max(reversibility, 0.0)
    return {
        "action_channel": channel,
        "action_intensity": s,
        "target_count": 1,
        "direct_effect_score": float(direct),
        "side_effect_score": float(side_effect),
        "net_public_effect_score": float(public),
        "net_hidden_effect_score": float(hidden),
        "exploitation_risk_delta": float(max(0.0, inequality + damage)),
        "trust_delta": float(public - hidden),
        "fatigue_delta": float(fatigue),
        "hidden_damage_delta": float(damage),
        "resource_inequality_delta": float(inequality),
        "reversibility_delta": float(reversibility),
        "exploration_delta": float(exploration),
        "action_cost_effect": float(cost),
    }


def _side_effect_burden(row: pd.Series | dict) -> float:
    return float(
        abs(float(row.get("net_hidden_effect_score", 0.0)))
        + max(float(row.get("hidden_damage_delta", 0.0)), 0.0)
        + max(float(row.get("fatigue_delta", 0.0)), 0.0)
        + max(float(row.get("resource_inequality_delta", 0.0)), 0.0)
        + abs(float(row.get("action_cost_effect", 0.0)))
    )


def _pressure_alignment_for_effect(effect: str, intent_family: str, response: pd.Series) -> float:
    """Estimate how well a channel response supports one pressure intent.

    This is a calibration heuristic over measured probe outputs, not a new
    semantic layer.  It maps already-existing PressureIntentBundle effects to
    observed response fields.
    """
    exploration = float(response.get("delta_vs_no_op_exploration", 0.0))
    reversibility = float(response.get("delta_vs_no_op_reversibility", 0.0))
    public = float(response.get("delta_vs_no_op_public_effect", 0.0))
    hidden = float(response.get("delta_vs_no_op_hidden_effect", 0.0))
    damage = float(response.get("delta_vs_no_op_hidden_damage", 0.0))
    fatigue = float(response.get("delta_vs_no_op_fatigue", 0.0))
    inequality = float(response.get("delta_vs_no_op_resource_inequality", 0.0))
    cost = float(response.get("delta_vs_no_op_cost", 0.0))
    trust = float(response.get("delta_vs_no_op_trust", 0.0))
    burden = _side_effect_burden(response)

    effect = str(effect)
    family = str(intent_family)
    if effect in {
        "exploration_attempt_frequency_up",
        "sandbox_probe_entry_up",
        "adoption_barrier_relief",
        "sensitivity_opening",
        "update_access_opening",
        "update_frequency_up",
    } or family in {"exploration_attempt", "exploration_observation", "adoption_opening", "response_opening", "temporal_opening", "update_opening"}:
        base = max(exploration, 0.0) + 0.25 * max(public, 0.0)
    elif effect in {"rollback_guard_up", "hysteresis_guard_up", "commitment_strength_up", "intensity_cap_brake", "update_waiting_longer", "sensitivity_deadzone_widen"} or family in {"safety_guard", "persistence_guard", "commitment_guard", "safety_cap", "temporal_brake", "response_restraint"}:
        base = max(reversibility, 0.0) + 0.20 * max(-damage, 0.0) + 0.20 * max(-fatigue, 0.0)
    elif effect in {"hysteresis_guard_down", "commitment_strength_down"} or family in {"switching_flexibility", "commitment_relief"}:
        base = max(public, 0.0) + 0.50 * max(reversibility, 0.0) - max(inequality, 0.0)
    elif effect in {"diagnostic_resolution_up", "sandbox_probe_entry_down"} or family in {"observation_detail", "probe_restraint"}:
        base = max(trust, 0.0) + 0.25 * max(reversibility, 0.0) + 0.20 * max(public, 0.0)
    elif effect in {"diagnostic_resolution_down", "exploration_attempt_frequency_down", "update_frequency_down", "rollback_guard_down", "intensity_cap_relief"}:
        base = 0.10 * max(public, 0.0) + 0.10 * max(exploration, 0.0)
    else:
        base = max(public, 0.0) + 0.25 * max(reversibility, 0.0) + 0.25 * max(exploration, 0.0)

    return float(max(0.0, base - 0.35 * burden - 0.20 * max(cost, 0.0)))


def build_single_action_probe_response_map(
    seeds: Iterable[int] = (19,),
    state_bands: Iterable[str] = STATE_BANDS,
    action_strengths: Iterable[float] = ACTION_STRENGTHS,
) -> pd.DataFrame:
    """Build validation-only Action -> result response rows."""
    rows: list[dict] = []
    for seed in seeds:
        for state_band in state_bands:
            for strength in action_strengths:
                baseline = _probe_action_effect(_synthetic_action_frame(str(state_band), "no_op", int(seed), float(strength)))
                for channel in CHANNELS:
                    frame = _synthetic_action_frame(str(state_band), channel, int(seed), float(strength))
                    effect = _probe_action_effect(frame)
                    row = {
                        **frame,
                        **effect,
                        "probe_contract": TASK2_2_CONTRACT,
                        "validation_only": True,
                        "runtime_policy_input": False,
                        "no_op_baseline_key": f"{state_band}:{seed}:{strength}:no_op",
                        "delta_vs_no_op_exploration": float(effect["exploration_delta"] - baseline["exploration_delta"]),
                        "delta_vs_no_op_reversibility": float(effect["reversibility_delta"] - baseline["reversibility_delta"]),
                        "delta_vs_no_op_public_effect": float(effect["net_public_effect_score"] - baseline["net_public_effect_score"]),
                        "delta_vs_no_op_hidden_effect": float(effect["net_hidden_effect_score"] - baseline["net_hidden_effect_score"]),
                        "delta_vs_no_op_hidden_damage": float(effect["hidden_damage_delta"] - baseline["hidden_damage_delta"]),
                        "delta_vs_no_op_fatigue": float(effect["fatigue_delta"] - baseline["fatigue_delta"]),
                        "delta_vs_no_op_resource_inequality": float(effect["resource_inequality_delta"] - baseline["resource_inequality_delta"]),
                        "delta_vs_no_op_cost": float(effect["action_cost_effect"] - baseline["action_cost_effect"]),
                        "delta_vs_no_op_trust": float(effect["trust_delta"] - baseline["trust_delta"]),
                    }
                    row["side_effect_burden_score"] = _side_effect_burden(row)
                    row["response_alignment_score"] = float(
                        max(row["delta_vs_no_op_public_effect"], 0.0)
                        + max(row["delta_vs_no_op_reversibility"], 0.0)
                        + max(row["delta_vs_no_op_exploration"], 0.0)
                        - row["side_effect_burden_score"]
                    )
                    rows.append(row)
    return pd.DataFrame(rows)


def calibrate_pressure_action_map(
    initial_map: pd.DataFrame | None = None,
    response_map: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Calibrate initial pressure-action map using single-action response rows."""
    base = build_initial_pressure_action_map() if initial_map is None else initial_map.copy()
    responses = build_single_action_probe_response_map() if response_map is None else response_map.copy()
    responses = responses[responses["action_channel"].astype(str) != "no_op"].copy()
    if base.empty or responses.empty:
        return pd.DataFrame(columns=REQUIRED_CALIBRATED_MAP_COLUMNS)

    rows: list[dict] = []
    for _, base_row in base.iterrows():
        channel_responses = responses[responses["action_channel"].astype(str) == str(base_row["action_channel"])].copy()
        for _, response in channel_responses.iterrows():
            measured = _pressure_alignment_for_effect(
                str(base_row["semantic_effect"]),
                str(base_row["intent_family"]),
                response,
            )
            row = base_row.to_dict()
            row.update({
                "pressure_action_map_version": TASK2_2_CALIBRATION_VERSION,
                "pre_calibration_mapping_source": row.get("mapping_source", "unknown"),
                "pre_calibration_status": row.get("calibration_status", "unknown"),
                "mapping_source": TASK2_2_MAPPING_SOURCE,
                "calibration_status": TASK2_2_CALIBRATION_STATUS,
                "calibration_method": "single_action_probe_vs_no_op_baseline",
                "scenario_or_state_band": str(response["state_band"]),
                "measured_pressure_alignment_raw": measured,
                "measured_side_effect_burden": float(response.get("side_effect_burden_score", 0.0)),
                "measured_reversibility_effect": float(response.get("delta_vs_no_op_reversibility", 0.0)),
                "measured_exploration_effect": float(response.get("delta_vs_no_op_exploration", 0.0)),
                "measured_public_effect": float(response.get("delta_vs_no_op_public_effect", 0.0)),
                "measured_hidden_effect": float(response.get("delta_vs_no_op_hidden_effect", 0.0)),
                "response_alignment_score": float(response.get("response_alignment_score", 0.0)),
                "sample_count": 1,
                "mapping_confidence": "medium_low",
                "calibration_fallback_used": False,
                "runtime_policy_input": False,
                "requires_task2_2_calibration": False,
                "requires_task2_3_candidate_generation": True,
                "task2_2_contract": TASK2_2_CONTRACT,
            })
            rows.append(row)

    out = pd.DataFrame(rows)
    group_cols = ["pressure_component", "component_direction", "semantic_effect", "scenario_or_state_band"]
    normalized: list[pd.DataFrame] = []
    for _, group in out.groupby(group_cols, dropna=False):
        g = group.copy()
        raw = pd.to_numeric(g["measured_pressure_alignment_raw"], errors="coerce").fillna(0.0)
        total = float(raw.sum())
        if total <= 1e-12:
            fallback = pd.to_numeric(g["initial_action_share"], errors="coerce").fillna(0.0)
            fallback_total = float(fallback.sum())
            if fallback_total <= 1e-12:
                g["calibrated_action_share"] = 1.0 / max(len(g), 1)
            else:
                g["calibrated_action_share"] = fallback / fallback_total
            g["calibration_fallback_used"] = True
        else:
            g["calibrated_action_share"] = raw / total
        g["estimated_pressure_alignment"] = g["calibrated_action_share"].astype(float)
        normalized.append(g)
    if not normalized:
        return pd.DataFrame(columns=REQUIRED_CALIBRATED_MAP_COLUMNS)
    result = pd.concat(normalized, ignore_index=True)
    return result[REQUIRED_CALIBRATED_MAP_COLUMNS]


def validate_calibrated_pressure_action_map(df: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    if df is None or df.empty:
        return ["calibrated_pressure_action_map_empty"]
    missing = sorted(set(REQUIRED_CALIBRATED_MAP_COLUMNS) - set(df.columns))
    if missing:
        errors.append(f"calibrated_pressure_action_map_required_columns_missing:{','.join(missing)}")
        return errors
    if not bool(df["calibration_status"].astype(str).eq(TASK2_2_CALIBRATION_STATUS).all()):
        errors.append("calibrated_pressure_action_map_status_not_task2_2")
    if not bool(df["mapping_source"].astype(str).eq(TASK2_2_MAPPING_SOURCE).all()):
        errors.append("calibrated_pressure_action_map_source_not_single_action_probe")
    if bool(df["new_semantic_translation_layer_added"].astype(bool).any()):
        errors.append("calibrated_pressure_action_map_added_new_semantic_translation_layer")
    if bool(df["diagnostic_compat_policy_used"].astype(bool).any()):
        errors.append("calibrated_pressure_action_map_used_diagnostic_compat_policy")
    if bool(df["repaired_diagnostic_policy_used"].astype(bool).any()):
        errors.append("calibrated_pressure_action_map_used_repaired_diagnostic_policy")
    if bool(df["runtime_policy_input"].astype(bool).any()):
        errors.append("calibrated_pressure_action_map_marked_as_runtime_policy_input_before_task2_3")
    shares = pd.to_numeric(df["calibrated_action_share"], errors="coerce")
    if bool(shares.isna().any() or (shares < -1e-12).any() or (shares > 1 + 1e-12).any()):
        errors.append("calibrated_pressure_action_map_share_out_of_bounds")
    grouped = df.groupby(["pressure_component", "component_direction", "semantic_effect", "scenario_or_state_band"], dropna=False)["calibrated_action_share"].sum()
    if bool(((grouped - 1.0).abs() > 1e-9).any()):
        errors.append("calibrated_pressure_action_map_shares_not_normalized_by_intent_and_band")
    if not bool(pd.to_numeric(df["sample_count"], errors="coerce").fillna(0).ge(1).all()):
        errors.append("calibrated_pressure_action_map_sample_count_missing")
    return errors


def build_and_validate_calibrated_pressure_action_map() -> tuple[pd.DataFrame, list[str]]:
    df = calibrate_pressure_action_map()
    return df, validate_calibrated_pressure_action_map(df)
