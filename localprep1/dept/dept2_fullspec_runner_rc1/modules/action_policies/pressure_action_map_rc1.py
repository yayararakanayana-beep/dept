"""pressure_action_map_rc1: initial pressure-action correspondence map.

Task: ActionModule UpperPressure Reception Split RC1 / Task 2-1.

This module creates the initial hypothesis version of the pressure-action map.
It does not calibrate the map and it does not connect the map to the FullSpec
runtime path.  Calibration is deferred to Task 2-2.

Boundary:
    - preserves existing PressureIntentBundle meanings
    - derives initial rows from existing ACTION_RELEVANCE flags
    - does not introduce a new semantic translation layer
    - does not call diagnostic compatibility policy
    - marks every row as uncalibrated initial hypothesis
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd

from DEPT2_ActionModule_ActuationPrimitives_RC1.dept2_system.pressure_intent import (
    ACTION_RELEVANCE,
    COMPONENT_INTENT_SPEC,
)


PRESSURE_ACTION_MAP_VERSION = "pressure_action_map_initial_hypothesis_rc1"
MAPPING_SOURCE = "initial_hypothesis_from_pressure_intent_relevance_flags"
CALIBRATION_STATUS = "uncalibrated"
CALIBRATION_METHOD = "not_yet_calibrated__requires_task2_2_single_action_validation"
SCENARIO_OR_STATE_BAND = "global_initial_hypothesis"
PRIMITIVE_SELECTION_STATUS = "deferred_until_action_surface_context"
ACTION_PRIMITIVE_PLACEHOLDER = "primitive_not_selected_at_pressure_action_map_level"

# Channel-level priors only.  These are not validation results.
# They are intentionally conservative placeholders until Task 2-2 estimates
# response signatures from Action -> result -> pressure-component alignment.
CHANNEL_SIDE_EFFECT_PRIOR = {
    "exploration_injection": 0.34,
    "relation_unlock": 0.42,
    "volatility_damping": 0.24,
    "uncertainty_probe": 0.22,
    "coupling_relief": 0.26,
    "buffer_increase": 0.18,
}

CHANNEL_REVERSIBILITY_PRIOR = {
    "exploration_injection": 0.42,
    "relation_unlock": 0.36,
    "volatility_damping": 0.64,
    "uncertainty_probe": 0.54,
    "coupling_relief": 0.62,
    "buffer_increase": 0.78,
}

CHANNEL_EXPLORATION_PRIOR = {
    "exploration_injection": 0.82,
    "relation_unlock": 0.38,
    "volatility_damping": 0.18,
    "uncertainty_probe": 0.46,
    "coupling_relief": 0.30,
    "buffer_increase": 0.20,
}


@dataclass(frozen=True)
class InitialPressureActionMapRow:
    pressure_component: str
    component_direction: str
    control_domain: str
    semantic_effect: str
    intent_family: str
    suggested_control_route: str
    action_channel: str
    initial_action_share: float
    relevant_channel_count: int

    def to_record(self) -> dict:
        return {
            "pressure_action_map_version": PRESSURE_ACTION_MAP_VERSION,
            "mapping_source": MAPPING_SOURCE,
            "calibration_status": CALIBRATION_STATUS,
            "calibration_method": CALIBRATION_METHOD,
            "sample_count": 0,
            "mapping_confidence": "low",
            "scenario_or_state_band": SCENARIO_OR_STATE_BAND,
            "pressure_component": self.pressure_component,
            "component_direction": self.component_direction,
            "control_domain": self.control_domain,
            "semantic_effect": self.semantic_effect,
            "intent_family": self.intent_family,
            "suggested_control_route": self.suggested_control_route,
            "action_channel": self.action_channel,
            "action_primitive": ACTION_PRIMITIVE_PLACEHOLDER,
            "primitive_selection_status": PRIMITIVE_SELECTION_STATUS,
            "initial_action_share": float(self.initial_action_share),
            "estimated_pressure_alignment": float(self.initial_action_share),
            "estimated_side_effect_burden": float(CHANNEL_SIDE_EFFECT_PRIOR.get(self.action_channel, 0.50)),
            "estimated_reversibility_effect": float(CHANNEL_REVERSIBILITY_PRIOR.get(self.action_channel, 0.50)),
            "estimated_exploration_effect": float(CHANNEL_EXPLORATION_PRIOR.get(self.action_channel, 0.50)),
            "estimated_public_effect": pd.NA,
            "estimated_hidden_effect": pd.NA,
            "relevant_channel_count": int(self.relevant_channel_count),
            "uses_existing_pressure_intent_semantics": True,
            "new_semantic_translation_layer_added": False,
            "diagnostic_compat_policy_used": False,
            "repaired_diagnostic_policy_used": False,
            "runtime_policy_input": False,
            "requires_task2_2_calibration": True,
            "task2_1_contract": (
                "initial_pressure_action_map_from_existing_relevance_flags__"
                "uncalibrated__not_runtime_policy_input__Task2_1_RC1"
            ),
        }


def _channels_for_effect(effect: str) -> list[str]:
    channels = [
        str(channel)
        for channel, effects in ACTION_RELEVANCE.items()
        if effect in effects
    ]
    return sorted(channels)


def _iter_non_neutral_component_rows() -> Iterable[InitialPressureActionMapRow]:
    for component, spec in COMPONENT_INTENT_SPEC.items():
        control_domain = str(spec["control_domain"])
        for direction in ("increase", "decrease"):
            semantic_effect, intent_family, suggested_route = spec[direction]
            channels = _channels_for_effect(str(semantic_effect))
            if not channels:
                continue
            share = 1.0 / float(len(channels))
            for channel in channels:
                yield InitialPressureActionMapRow(
                    pressure_component=str(component),
                    component_direction=direction,
                    control_domain=control_domain,
                    semantic_effect=str(semantic_effect),
                    intent_family=str(intent_family),
                    suggested_control_route=str(suggested_route),
                    action_channel=str(channel),
                    initial_action_share=share,
                    relevant_channel_count=len(channels),
                )


def build_initial_pressure_action_map() -> pd.DataFrame:
    """Return the Task 2-1 initial uncalibrated pressure-action map.

    The table is channel-level and hypothesis-only.  Primitive selection remains
    deferred because primitive choice depends on action-surface context and must
    not be pretended to be calibrated here.
    """
    rows = [row.to_record() for row in _iter_non_neutral_component_rows()]
    if not rows:
        return pd.DataFrame(columns=REQUIRED_PRESSURE_ACTION_MAP_COLUMNS)
    out = pd.DataFrame(rows)
    return out[REQUIRED_PRESSURE_ACTION_MAP_COLUMNS]


REQUIRED_PRESSURE_ACTION_MAP_COLUMNS = [
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
    "estimated_pressure_alignment",
    "estimated_side_effect_burden",
    "estimated_reversibility_effect",
    "estimated_exploration_effect",
    "estimated_public_effect",
    "estimated_hidden_effect",
    "relevant_channel_count",
    "uses_existing_pressure_intent_semantics",
    "new_semantic_translation_layer_added",
    "diagnostic_compat_policy_used",
    "repaired_diagnostic_policy_used",
    "runtime_policy_input",
    "requires_task2_2_calibration",
    "task2_1_contract",
]


def validate_initial_pressure_action_map(df: pd.DataFrame) -> list[str]:
    """Return validation errors for the Task 2-1 map contract."""
    errors: list[str] = []
    if df is None or df.empty:
        return ["pressure_action_map_empty"]
    missing = sorted(set(REQUIRED_PRESSURE_ACTION_MAP_COLUMNS) - set(df.columns))
    if missing:
        errors.append(f"pressure_action_map_required_columns_missing:{','.join(missing)}")
        return errors
    if not bool(df["calibration_status"].astype(str).eq(CALIBRATION_STATUS).all()):
        errors.append("pressure_action_map_not_all_uncalibrated")
    if not bool(df["mapping_source"].astype(str).eq(MAPPING_SOURCE).all()):
        errors.append("pressure_action_map_source_not_initial_hypothesis")
    if bool(df["new_semantic_translation_layer_added"].astype(bool).any()):
        errors.append("pressure_action_map_added_new_semantic_translation_layer")
    if bool(df["diagnostic_compat_policy_used"].astype(bool).any()):
        errors.append("pressure_action_map_used_diagnostic_compat_policy")
    if bool(df["repaired_diagnostic_policy_used"].astype(bool).any()):
        errors.append("pressure_action_map_used_repaired_diagnostic_policy")
    if bool(df["runtime_policy_input"].astype(bool).any()):
        errors.append("pressure_action_map_marked_as_runtime_policy_input_before_task2_3")
    if not bool(df["requires_task2_2_calibration"].astype(bool).all()):
        errors.append("pressure_action_map_missing_task2_2_calibration_requirement")
    shares = pd.to_numeric(df["initial_action_share"], errors="coerce")
    if bool(shares.isna().any() or (shares < 0).any() or (shares > 1).any()):
        errors.append("pressure_action_map_initial_share_out_of_bounds")
    grouped = df.groupby(["pressure_component", "component_direction", "semantic_effect"], dropna=False)["initial_action_share"].sum()
    if bool(((grouped - 1.0).abs() > 1e-9).any()):
        errors.append("pressure_action_map_initial_shares_not_normalized_by_intent")
    return errors


def build_and_validate_initial_pressure_action_map() -> tuple[pd.DataFrame, list[str]]:
    df = build_initial_pressure_action_map()
    return df, validate_initial_pressure_action_map(df)
