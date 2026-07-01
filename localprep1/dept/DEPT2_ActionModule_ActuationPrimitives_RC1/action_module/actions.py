"""Action planner and actuator with environment-specific actuation primitives RC1.

This module keeps the non-compressed pressure contract:
  - H-DEPT approved components are not collapsed before the action module
  - ActionSurface only supplies affordances
  - ActionPlanner is the first compression point

RC1 change:
  The planner no longer maps a route directly to a single crude action. It first
  composes environment-specific actuation primitives for the current pseudo
  reality. The actuator then applies primitive-specific effects through the
  existing pseudo-reality action channels.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

CHANNEL_TO_RELEVANCE_COL = {
    "exploration_injection": "relevant_to_exploration_injection",
    "relation_unlock": "relevant_to_relation_unlock",
    "volatility_damping": "relevant_to_volatility_damping",
    "uncertainty_probe": "relevant_to_uncertainty_probe",
    "coupling_relief": "relevant_to_coupling_relief",
    "buffer_increase": "relevant_to_buffer_increase",
}

GAIN_BY_CHANNEL = {
    "exploration_injection": "exploration_gain",
    "coupling_relief": "unlock_gain",
    "volatility_damping": "damping_gain",
    "uncertainty_probe": "buffer_gain",
    "relation_unlock": "unlock_gain",
    "buffer_increase": "buffer_gain",
    "no_op": None,
}

PRIMITIVE_LIBRARY = [
    {
        "primitive_id": "observe_only",
        "purpose": "do not actuate; preserve information when local risk is too high",
        "actual_channel": "no_op",
        "scope": "local_observation",
        "reversibility_class": "maximal",
    },
    {
        "primitive_id": "buffer_first",
        "purpose": "increase reversibility/buffer before any disruptive action",
        "actual_channel": "buffer_increase",
        "scope": "local_entity",
        "reversibility_class": "high",
    },
    {
        "primitive_id": "coupling_relief_first",
        "purpose": "relieve coupled lock before direct relation unlock",
        "actual_channel": "coupling_relief",
        "scope": "relation_neighborhood_proxy",
        "reversibility_class": "high",
    },
    {
        "primitive_id": "staged_relation_unlock",
        "purpose": "direct unlock only after buffer/coupling relief is likely safe",
        "actual_channel": "relation_unlock",
        "scope": "local_relation_proxy",
        "reversibility_class": "medium",
    },
    {
        "primitive_id": "peripheral_explore",
        "purpose": "explore around locked structure rather than forcing the locked relation",
        "actual_channel": "exploration_injection",
        "scope": "local_periphery_proxy",
        "reversibility_class": "medium_high",
    },
    {
        "primitive_id": "exploration_cost_relief",
        "purpose": "increase attempts/cooldown access while keeping adoption conservative",
        "actual_channel": "exploration_injection",
        "scope": "local_entity",
        "reversibility_class": "medium_high",
    },
    {
        "primitive_id": "adoption_barrier_relief_guarded",
        "purpose": "lower adoption barrier only when local conflict is already low",
        "actual_channel": "exploration_injection",
        "scope": "local_entity",
        "reversibility_class": "medium",
    },
    {
        "primitive_id": "volatility_damp_first",
        "purpose": "dampen shock volatility before probing uncertainty",
        "actual_channel": "volatility_damping",
        "scope": "local_entity",
        "reversibility_class": "high",
    },
    {
        "primitive_id": "delayed_uncertainty_probe",
        "purpose": "probe only after shock/buffer gate is calm enough",
        "actual_channel": "uncertainty_probe",
        "scope": "local_entity",
        "reversibility_class": "medium_high",
    },
]


def _primitive_df() -> pd.DataFrame:
    df = pd.DataFrame(PRIMITIVE_LIBRARY)
    df["primitive_contract"] = "environment_specific_actuation_primitives__pseudo_reality_RC1"
    return df


class ActionPlanner:
    """First compression point: non-compressed intents -> primitive candidates.

    The planner is intentionally pseudo-reality-specific. It reads the current
    local system character from the affordance/v8 fields and chooses an
    actuation primitive. It is allowed to compress; earlier layers are not.
    """

    def primitive_library(self) -> pd.DataFrame:
        return _primitive_df()

    def _intent_vector_for_channel(self, intents: pd.DataFrame, channel: str) -> dict:
        rel_col = CHANNEL_TO_RELEVANCE_COL[channel]
        rel = intents[intents[rel_col].astype(bool)].copy() if rel_col in intents.columns else intents.iloc[0:0].copy()
        if rel.empty:
            return {
                "intent_total_signal": 0.0,
                "attempt_signal": 0.0,
                "adoption_relief_signal": 0.0,
                "sensitivity_opening_signal": 0.0,
                "cooldown_opening_signal": 0.0,
                "sandbox_probe_signal": 0.0,
                "diagnostic_signal": 0.0,
                "rollback_guard_signal": 0.0,
                "intensity_cap_brake_signal": 0.0,
                "commitment_relief_signal": 0.0,
                "dominant_semantic_effect": "none",
                "dominant_pressure_component": "none",
                "intent_component_count": 0,
            }
        rel["signal"] = rel["h11_received_abs_pressure"].astype(float) + 0.35 * rel["component_magnitude"].astype(float)
        effect_signal = rel.groupby("semantic_effect")["signal"].sum().to_dict()
        comp_signal = rel.groupby("pressure_component")["signal"].sum().to_dict()
        dominant_effect = max(effect_signal.items(), key=lambda kv: kv[1])[0] if effect_signal else "none"
        dominant_comp = max(comp_signal.items(), key=lambda kv: kv[1])[0] if comp_signal else "none"
        return {
            "intent_total_signal": float(rel["signal"].sum()),
            "attempt_signal": float(effect_signal.get("exploration_attempt_frequency_up", 0.0)),
            "adoption_relief_signal": float(effect_signal.get("adoption_barrier_relief", 0.0)),
            "sensitivity_opening_signal": float(effect_signal.get("sensitivity_opening", 0.0)),
            "cooldown_opening_signal": float(effect_signal.get("update_access_opening", 0.0)),
            "sandbox_probe_signal": float(effect_signal.get("sandbox_probe_entry_up", 0.0)),
            "diagnostic_signal": float(effect_signal.get("diagnostic_resolution_up", 0.0)),
            "rollback_guard_signal": float(effect_signal.get("rollback_guard_up", 0.0)),
            "intensity_cap_brake_signal": float(effect_signal.get("intensity_cap_brake", 0.0)),
            "commitment_relief_signal": float(effect_signal.get("commitment_strength_down", 0.0)),
            "dominant_semantic_effect": dominant_effect,
            "dominant_pressure_component": dominant_comp,
            "intent_component_count": int(rel[["pressure_component", "semantic_effect"]].drop_duplicates().shape[0]),
        }

    def _compose_primitive(self, aff: pd.Series, channel: str, vec: dict) -> dict:
        """Choose pseudo-reality-specific primitive and actual channel.

        This is the key RC1 change. For locked or shocked states, a route is not
        enacted directly; it is staged through buffer/coupling relief/damping or
        observation-only.
        """
        scenario = str(aff.get("scenario", "unknown"))
        v8_conflict = float(aff.get("v8_conflict", 0.0))
        v8_unresolved = float(aff.get("v8_unresolved", 0.0))
        cost = float(aff.get("estimated_action_cost", 0.0))
        target_need = float(aff.get("target_need", 0.0))
        # Local proxies available from affordance/v8 only. Direct GraphObject is not passed to upper.
        high_local_risk = (v8_conflict > 0.46) or (v8_unresolved > 0.54) or (cost > 0.58)
        locked_context = scenario == "relation_lock" or (channel in {"relation_unlock", "exploration_injection"} and v8_conflict > 0.42 and cost > 0.42)
        shock_context = scenario == "shock" or (channel in {"uncertainty_probe", "volatility_damping", "buffer_increase"} and v8_unresolved > 0.45)
        exploration_loss_context = scenario == "exploration_loss"

        primitive = "observe_only"
        planned_channel = "no_op"
        route = "observe_only"
        multiplier = 0.0
        sequence = "observe"
        stage = 0
        duration = 1
        rollback = "none"
        reason = "default_safe_observe"

        if locked_context:
            if channel == "exploration_injection":
                # Do not inject exploration directly into a locked/coupled field.
                if vec["sandbox_probe_signal"] + vec["diagnostic_signal"] > 0.0 and high_local_risk:
                    primitive = "observe_only"
                    planned_channel = "no_op"
                    route = "locked_observe_before_explore"
                    multiplier = 0.0
                    sequence = "observe -> peripheral_explore"
                    stage = 0
                    reason = "locked_context_and_high_v8_risk"
                else:
                    primitive = "peripheral_explore"
                    planned_channel = "exploration_injection"
                    route = "locked_peripheral_explore"
                    multiplier = 0.42
                    sequence = "buffer/watch -> peripheral_explore"
                    stage = 2
                    rollback = "revert_if_conflict_or_relation_lock_increases"
                    reason = "exploration_preserved_but_moved_to_periphery"
            elif channel == "relation_unlock":
                # Prefer buffer/coupling relief before direct unlock.
                if v8_conflict > 0.48 or cost > 0.52:
                    primitive = "buffer_first"
                    planned_channel = "buffer_increase"
                    route = "buffer_before_relation_unlock"
                    multiplier = 0.45
                    sequence = "buffer -> coupling_relief -> staged_unlock"
                    stage = 1
                    rollback = "revert_if_conflict_increases"
                    reason = "direct_unlock_too_disruptive_under_relation_lock"
                else:
                    primitive = "coupling_relief_first"
                    planned_channel = "coupling_relief"
                    route = "coupling_relief_before_unlock"
                    multiplier = 0.55
                    sequence = "coupling_relief -> staged_unlock"
                    stage = 1
                    rollback = "revert_if_conflict_increases"
                    reason = "relieve_coupling_before_unlock"
            elif channel == "coupling_relief":
                primitive = "coupling_relief_first"
                planned_channel = "coupling_relief"
                route = "coupling_relief_first"
                multiplier = 0.70
                sequence = "coupling_relief -> observe"
                stage = 1
                rollback = "revert_if_conflict_increases"
                reason = "relation_lock_primary_safe_relief"
            elif channel == "buffer_increase":
                primitive = "buffer_first"
                planned_channel = "buffer_increase"
                route = "relation_lock_buffer_first"
                multiplier = 0.75
                sequence = "buffer -> observe -> optional_unlock"
                stage = 1
                rollback = "none_or_revert_if_volatility_increases"
                reason = "increase_reversibility_before_touching_relation"
            else:
                primitive = "observe_only" if high_local_risk else "buffer_first"
                planned_channel = "no_op" if high_local_risk else "buffer_increase"
                route = "locked_context_safe_substitution"
                multiplier = 0.0 if high_local_risk else 0.38
                sequence = "observe/buffer -> replan"
                stage = 0 if high_local_risk else 1
                reason = "non_lock_action_substituted_under_locked_context"
        elif shock_context:
            if channel == "uncertainty_probe":
                if high_local_risk:
                    primitive = "volatility_damp_first"
                    planned_channel = "volatility_damping"
                    route = "shock_damp_before_probe"
                    multiplier = 0.50
                    sequence = "damp -> buffer -> delayed_probe"
                    stage = 1
                    rollback = "revert_if_volatility_or_conflict_increases"
                    reason = "probe_delayed_until_shock_calms"
                else:
                    primitive = "delayed_uncertainty_probe"
                    planned_channel = "uncertainty_probe"
                    route = "delayed_uncertainty_probe"
                    multiplier = 0.48
                    sequence = "buffer/watch -> local_probe"
                    stage = 2
                    rollback = "revert_if_conflict_increases"
                    reason = "probe_allowed_after_v8_risk_is_moderate"
            elif channel == "buffer_increase":
                primitive = "buffer_first"
                planned_channel = "buffer_increase"
                route = "shock_buffer_first"
                multiplier = 0.78
                sequence = "buffer -> observe"
                stage = 1
                rollback = "none"
                reason = "shock_requires_reversibility_first"
            elif channel == "volatility_damping":
                primitive = "volatility_damp_first"
                planned_channel = "volatility_damping"
                route = "shock_volatility_damp_first"
                multiplier = 0.72
                sequence = "damp -> observe"
                stage = 1
                rollback = "revert_if_reversibility_decreases"
                reason = "direct_volatility_damping_is_primary_shock_response"
            else:
                primitive = "buffer_first"
                planned_channel = "buffer_increase"
                route = "shock_safe_buffer_substitution"
                multiplier = 0.38
                sequence = "buffer -> replan"
                stage = 1
                rollback = "none"
                reason = "non_shock_route_substituted_to_buffer"
        elif exploration_loss_context and channel == "exploration_injection":
            # Preserve distinction: attempt/cooldown first, adoption relief only when risk is low.
            if vec["attempt_signal"] + vec["cooldown_opening_signal"] >= vec["adoption_relief_signal"] or v8_conflict >= 0.34:
                primitive = "exploration_cost_relief"
                planned_channel = "exploration_injection"
                route = "exploration_cost_relief_only"
                multiplier = 0.70
                sequence = "increase_attempts_and_reduce_cooldown -> observe"
                stage = 1
                rollback = "revert_if_uncertainty_or_conflict_increases"
                reason = "keep_adoption_conservative_while_restoring_attempts"
            else:
                primitive = "adoption_barrier_relief_guarded"
                planned_channel = "exploration_injection"
                route = "guarded_adoption_barrier_relief"
                multiplier = 0.55
                sequence = "guarded_adoption_relief -> observe"
                stage = 1
                rollback = "revert_if_conflict_increases"
                reason = "adoption_relief_allowed_only_under_low_conflict"
        else:
            # Normal/low-risk mappings.
            if channel == "exploration_injection":
                primitive = "exploration_cost_relief" if vec["attempt_signal"] + vec["cooldown_opening_signal"] >= vec["adoption_relief_signal"] else "adoption_barrier_relief_guarded"
                planned_channel = "exploration_injection"
                route = primitive
                multiplier = 0.78 if primitive == "exploration_cost_relief" else 0.62
                sequence = "explore -> observe"
                stage = 1
                rollback = "revert_if_conflict_increases"
                reason = "normal_exploration_route"
            elif channel == "relation_unlock":
                primitive = "staged_relation_unlock" if not high_local_risk else "coupling_relief_first"
                planned_channel = "relation_unlock" if primitive == "staged_relation_unlock" else "coupling_relief"
                route = primitive
                multiplier = 0.52 if primitive == "staged_relation_unlock" else 0.45
                sequence = "staged_unlock -> observe"
                stage = 2 if primitive == "staged_relation_unlock" else 1
                rollback = "revert_if_conflict_increases"
                reason = "normal_relation_unlock_route"
            elif channel == "volatility_damping":
                primitive = "volatility_damp_first"
                planned_channel = "volatility_damping"
                route = "volatility_damp_first"
                multiplier = 0.72
                sequence = "damp -> observe"
                stage = 1
                rollback = "revert_if_reversibility_decreases"
                reason = "normal_damping_route"
            elif channel == "uncertainty_probe":
                primitive = "delayed_uncertainty_probe" if high_local_risk else "delayed_uncertainty_probe"
                planned_channel = "uncertainty_probe"
                route = "delayed_uncertainty_probe"
                multiplier = 0.50 if high_local_risk else 0.64
                sequence = "observe/buffer -> probe"
                stage = 2 if high_local_risk else 1
                rollback = "revert_if_conflict_increases"
                reason = "probe_is_kept_local_and_reversible"
            elif channel == "coupling_relief":
                primitive = "coupling_relief_first"
                planned_channel = "coupling_relief"
                route = "coupling_relief_first"
                multiplier = 0.68
                sequence = "coupling_relief -> observe"
                stage = 1
                rollback = "revert_if_conflict_increases"
                reason = "normal_coupling_relief_route"
            elif channel == "buffer_increase":
                primitive = "buffer_first"
                planned_channel = "buffer_increase"
                route = "buffer_first"
                multiplier = 0.72
                sequence = "buffer -> observe"
                stage = 1
                rollback = "none"
                reason = "normal_buffer_route"

        # Longer duration is used only for gentle stabilizing primitives.
        if primitive in {"buffer_first", "volatility_damp_first", "coupling_relief_first"} and target_need > 0.75:
            duration = 2
        if primitive == "observe_only":
            duration = 1

        return {
            "planner_route": route,
            "action_primitive": primitive,
            "action_channel": planned_channel,
            "planner_route_multiplier": float(multiplier),
            "primitive_sequence": sequence,
            "primitive_stage": int(stage),
            "action_scope": next((p["scope"] for p in PRIMITIVE_LIBRARY if p["primitive_id"] == primitive), "unknown"),
            "duration_steps": int(duration),
            "rollback_condition": rollback,
            "primitive_reason": reason,
        }

    def plan(self, pressure_intents: pd.DataFrame, v8_affordance: pd.DataFrame, params: dict) -> pd.DataFrame:
        if v8_affordance.empty:
            return pd.DataFrame()
        cap = float(params.get("action_intensity_cap", 0.55))
        sparsity = float(params.get("planner_min_action_strength", 0.012))
        rows = []
        group_cols = [c for c in ["seed", "scenario", "t", "generator", "phase_bin"] if c in pressure_intents.columns]

        precomputed = {}
        if group_cols:
            groups = pressure_intents.groupby(group_cols, dropna=False)
            for key, sub in groups:
                key = key if isinstance(key, tuple) else (key,)
                for channel in CHANNEL_TO_RELEVANCE_COL:
                    precomputed[(key, channel)] = self._intent_vector_for_channel(sub, channel)
        else:
            for channel in CHANNEL_TO_RELEVANCE_COL:
                precomputed[(("__all__",), channel)] = self._intent_vector_for_channel(pressure_intents, channel)

        for _, aff in v8_affordance.iterrows():
            original_channel = str(aff.action_channel)
            if original_channel == "no_op" or original_channel not in CHANNEL_TO_RELEVANCE_COL:
                continue
            if group_cols:
                key = tuple(aff[c] for c in group_cols if c in aff.index)
                vec = precomputed.get((key, original_channel))
                if vec is None:
                    matching = pressure_intents
                    for c in ["seed", "scenario", "t"]:
                        if c in pressure_intents.columns and c in aff.index:
                            matching = matching[matching[c] == aff[c]]
                    vec = self._intent_vector_for_channel(matching, original_channel)
            else:
                vec = precomputed.get((("__all__",), original_channel), self._intent_vector_for_channel(pressure_intents, original_channel))
            signal = vec["intent_total_signal"]
            if signal <= 1e-12:
                continue
            primitive = self._compose_primitive(aff, original_channel, vec)
            if primitive["action_channel"] == "no_op" or primitive["planner_route_multiplier"] <= 0:
                # Keep observe-only in audit, but with zero strength; final gate will no-op if evaluated.
                pass
            target_need = float(aff.target_need)
            cost = float(aff.estimated_action_cost)
            v8_conf = float(aff.get("v8_confidence", 0.50))
            v8_conflict = float(aff.get("v8_conflict", 0.0))
            v8_unresolved = float(aff.get("v8_unresolved", 0.0))
            safety_discount = float(np.clip(1.0 - 0.45 * cost - 0.42 * v8_conflict - 0.30 * v8_unresolved, 0.08, 1.0))
            raw_strength = signal * target_need * primitive["planner_route_multiplier"] * safety_discount * 1.75
            strength = float(np.clip(raw_strength, 0.0, cap))
            if primitive["action_channel"] == "no_op":
                strength = 0.0
            if strength < sparsity and primitive["action_channel"] != "no_op":
                continue
            planner_confidence = float(np.clip(0.35 + 0.35 * v8_conf + 0.20 * min(signal * 8.0, 1.0) + 0.10 * (1 - cost), 0, 1))
            out = aff.to_dict()
            out.update(vec)
            out.update(primitive)
            out.update({
                "original_affordance_channel": original_channel,
                "planner_raw_strength": raw_strength,
                "action_strength": strength,
                "planner_confidence": planner_confidence,
                "first_compression_layer": "ActionPlanner",
                "action_planner_contract": "composes_environment_specific_actuation_primitives_from_noncompressed_intents__RC1",
                "truth_used_for_action_planner": False,
            })
            rows.append(out)
        return pd.DataFrame(rows)


class ActionModule:
    """Actuator: final gated primitive candidates -> pseudo-reality interventions."""

    def __init__(self, mode: str = "primitive_reversible"):
        self.mode = mode

    def _primitive_gain_adjustment(self, primitive: str) -> float:
        # Environment-specific adjustments for current pseudo reality.
        return {
            "buffer_first": 1.05,
            "coupling_relief_first": 0.85,
            "staged_relation_unlock": 0.55,
            "peripheral_explore": 0.65,
            "exploration_cost_relief": 0.78,
            "adoption_barrier_relief_guarded": 0.48,
            "volatility_damp_first": 0.95,
            "delayed_uncertainty_probe": 0.55,
            "observe_only": 0.0,
        }.get(primitive, 0.60)

    def build_action_frame(self, final_gate: pd.DataFrame, params: dict) -> pd.DataFrame:
        if final_gate.empty:
            return pd.DataFrame(columns=["entity_id", "action_channel", "action_strength", "direction", "source_gate_decision"])
        rows = []
        candidates = []
        for _, r in final_gate.iterrows():
            if r.final_gate_decision in ["hold_shadow", "gate_no_op"]:
                continue
            if str(r.get("action_primitive", "")) == "observe_only" or r.action_channel == "no_op":
                continue
            gain_name = GAIN_BY_CHANNEL.get(r.action_channel)
            gain = 0.0 if gain_name is None else float(params.get(gain_name, 0.30))
            primitive_adj = self._primitive_gain_adjustment(str(r.get("action_primitive", "general")))
            duration_adj = float(np.sqrt(max(1.0, float(r.get("duration_steps", 1)))))
            strength = float(np.clip(r.effective_action_strength * gain * primitive_adj * duration_adj, 0.0, 0.22))
            if strength <= 0:
                continue
            priority = strength * float(r.get("gate_score", 0.5)) * float(r.get("planner_confidence", 0.5))
            # Direct unlock/probe are intentionally lower priority than buffer/coupling/damp when same entity has options.
            primitive = str(r.get("action_primitive", "general"))
            if primitive in {"staged_relation_unlock", "delayed_uncertainty_probe", "adoption_barrier_relief_guarded"}:
                priority *= 0.78
            elif primitive in {"buffer_first", "volatility_damp_first", "coupling_relief_first"}:
                priority *= 1.08
            candidates.append((priority, r, strength))
        if not candidates:
            return pd.DataFrame(columns=["entity_id", "action_channel", "action_strength", "direction", "source_gate_decision"])
        by_entity = {}
        for priority, r, strength in candidates:
            eid = r.entity_id
            if eid not in by_entity or priority > by_entity[eid][0]:
                by_entity[eid] = (priority, r, strength)
        for priority, r, strength in by_entity.values():
            rows.append({
                "entity_id": r.entity_id,
                "action_channel": r.action_channel,
                "action_strength": strength,
                "direction": float(r.direction),
                "source_gate_decision": r.final_gate_decision,
                "planner_route": r.get("planner_route", "unknown"),
                "action_primitive": r.get("action_primitive", "unknown"),
                "primitive_sequence": r.get("primitive_sequence", "unknown"),
                "primitive_stage": int(r.get("primitive_stage", 0)),
                "action_scope": r.get("action_scope", "unknown"),
                "duration_steps": int(r.get("duration_steps", 1)),
                "rollback_condition": r.get("rollback_condition", "unknown"),
                "dominant_semantic_effect": r.get("dominant_semantic_effect", "unknown"),
                "dominant_pressure_component": r.get("dominant_pressure_component", "unknown"),
                "action_selection_priority": priority,
                "action_module_mode": self.mode,
                "action_module_contract": "actuator_applies_selected_primitive_commands_to_pseudo_reality_only__never_directly_mutates_G_or_K__RC1",
            })
        return pd.DataFrame(rows)
