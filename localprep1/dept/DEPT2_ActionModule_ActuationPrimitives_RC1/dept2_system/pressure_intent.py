"""Non-compressive H-DEPT pressure intent annotator.

This module translates approved H-DEPT parameter-pressure components into
semantic intent rows without collapsing them into one coarse action label.

Contract:
    - preserve component identity
    - preserve signed parameter direction
    - annotate semantic effect of the direction
    - do not aggregate/average into exploration_drive / brake / action channel
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .hdept_observer import PRESSURE_COMPONENTS

# Directional semantics. The sign is about parameter movement, not support/opposition.
COMPONENT_INTENT_SPEC = {
    "diagnostic_depth": {
        "control_domain": "observation_resolution",
        "increase": ("diagnostic_resolution_up", "observation_detail", "v8_detail_or_audit"),
        "decrease": ("diagnostic_resolution_down", "observation_cost_saving", "lighter_observation"),
    },
    "exploration_frequency": {
        "control_domain": "exploration_scheduler",
        "increase": ("exploration_attempt_frequency_up", "exploration_attempt", "increase_trials"),
        "decrease": ("exploration_attempt_frequency_down", "exploration_restraint", "reduce_trials"),
    },
    "sandbox_entry_rate": {
        "control_domain": "sandbox_and_probe",
        "increase": ("sandbox_probe_entry_up", "exploration_observation", "increase_sandbox_probe"),
        "decrease": ("sandbox_probe_entry_down", "probe_restraint", "reduce_sandbox_probe"),
    },
    "adoption_threshold": {
        "control_domain": "candidate_adoption_gate",
        "increase": ("adoption_barrier_raise", "adoption_guard", "keep_adoption_strict"),
        "decrease": ("adoption_barrier_relief", "adoption_opening", "lower_candidate_barrier"),
    },
    "rollback_sensitivity": {
        "control_domain": "rollback_guard",
        "increase": ("rollback_guard_up", "safety_guard", "prepare_reversal"),
        "decrease": ("rollback_guard_down", "safety_relaxation", "reduce_reversal_bias"),
    },
    "deadzone_width": {
        "control_domain": "response_deadzone",
        "increase": ("sensitivity_deadzone_widen", "response_restraint", "ignore_minor_variation"),
        "decrease": ("sensitivity_opening", "response_opening", "respond_to_smaller_signal"),
    },
    "cooldown_length": {
        "control_domain": "update_cooldown",
        "increase": ("update_waiting_longer", "temporal_brake", "lengthen_wait"),
        "decrease": ("update_access_opening", "temporal_opening", "shorten_wait"),
    },
    "hysteresis_strength": {
        "control_domain": "persistence_guard",
        "increase": ("hysteresis_guard_up", "persistence_guard", "resist_fast_switching"),
        "decrease": ("hysteresis_guard_down", "switching_flexibility", "allow_axis_turnover"),
    },
    "update_frequency": {
        "control_domain": "update_scheduler",
        "increase": ("update_frequency_up", "update_opening", "increase_update_access"),
        "decrease": ("update_frequency_down", "update_restraint", "reduce_update_access"),
    },
    "pressure_cap": {
        "control_domain": "intensity_cap",
        "increase": ("intensity_cap_relief", "capacity_opening", "allow_larger_action_cap"),
        "decrease": ("intensity_cap_brake", "safety_cap", "lower_action_cap"),
    },
    "commitment_strength": {
        "control_domain": "commitment_and_persistence",
        "increase": ("commitment_strength_up", "commitment_guard", "stabilize_selected_path"),
        "decrease": ("commitment_strength_down", "commitment_relief", "keep_path_reversible"),
    },
}

# Which fine-grained intents are potentially useful for each action branch.
# This is relevance annotation, not compression. Multiple routes can stay alive.
ACTION_RELEVANCE = {
    "exploration_injection": {
        "exploration_attempt_frequency_up", "sandbox_probe_entry_up", "adoption_barrier_relief",
        "sensitivity_opening", "update_access_opening", "update_frequency_up", "hysteresis_guard_down",
        "commitment_strength_down",
    },
    "relation_unlock": {
        "adoption_barrier_relief", "sensitivity_opening", "update_access_opening",
        "hysteresis_guard_down", "commitment_strength_down", "rollback_guard_up",
    },
    "volatility_damping": {
        "rollback_guard_up", "intensity_cap_brake", "hysteresis_guard_up", "update_waiting_longer",
        "commitment_strength_up", "diagnostic_resolution_up",
    },
    "uncertainty_probe": {
        "diagnostic_resolution_up", "sandbox_probe_entry_up", "sensitivity_opening",
        "rollback_guard_up", "update_frequency_up",
    },
    "coupling_relief": {
        "sensitivity_opening", "adoption_barrier_relief", "hysteresis_guard_down",
        "commitment_strength_down", "intensity_cap_brake",
    },
    "buffer_increase": {
        "rollback_guard_up", "update_waiting_longer", "commitment_strength_up",
        "diagnostic_resolution_up", "intensity_cap_brake",
    },
}


def _direction(value: float) -> str:
    if value > 1e-12:
        return "increase"
    if value < -1e-12:
        return "decrease"
    return "neutral"


class HDEPTPressureIntentAnnotator:
    """Annotate pressure components without action compression."""

    def annotate(self, h11_field: pd.DataFrame) -> pd.DataFrame:
        if h11_field.empty:
            return pd.DataFrame()
        rows = []
        for _, r in h11_field.iterrows():
            comp = str(r.pressure_component)
            val = float(r.hdept_approved_component_value)
            direction = _direction(val)
            if direction == "neutral":
                effect, family, route = "neutral_component", "neutral", "no_route"
                domain = COMPONENT_INTENT_SPEC.get(comp, {}).get("control_domain", "unknown")
            else:
                spec = COMPONENT_INTENT_SPEC[comp]
                domain = spec["control_domain"]
                effect, family, route = spec[direction]
            magnitude = abs(val)
            received_abs = abs(float(r.h11_local_received_pressure))
            # Relevance flags are separate columns; they do not collapse the intent.
            relevance = {f"relevant_to_{ch}": effect in effects for ch, effects in ACTION_RELEVANCE.items()}
            out = {
                **{k: r[k] for k in ["seed", "scenario", "t", "generator", "phase_bin"] if k in r.index},
                "h11_dimension": r.h11_dimension,
                "pressure_component": comp,
                "component_direction": direction,
                "component_signed_value": val,
                "component_magnitude": magnitude,
                "h11_received_signed_pressure": float(r.h11_local_received_pressure),
                "h11_received_abs_pressure": received_abs,
                "control_domain": domain,
                "semantic_effect": effect,
                "intent_family": family,
                "suggested_control_route": route,
                "compression_allowed_before_action_planner": False,
                "intent_annotation_contract": "non_compressive_annotation__preserve_component_direction_and_identity__RC1",
                "truth_used_for_intent_annotation": False,
            }
            out.update(relevance)
            rows.append(out)
        return pd.DataFrame(rows)
