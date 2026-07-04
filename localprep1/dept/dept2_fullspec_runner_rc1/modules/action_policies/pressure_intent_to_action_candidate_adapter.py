"""pressure_intent_to_action_candidate_adapter: Task 2-3 candidate builder.

Task: ActionModule UpperPressure Reception Split RC1 / Task 2-3.

This module uses a calibrated or explicitly uncalibrated pressure-action map to
turn PressureIntentBundle rows into pre-gate action candidates.

Boundary:
    - preserves PressureIntentBundle meanings
    - uses the pressure-action map as correspondence evidence
    - builds candidates only, not final actions
    - does not evaluate state-dependent timing or state-dependent effect
    - does not perform safety/final adoption decisions
    - does not call diagnostic policy, ActionPlanner, ActionModule, or world
    - does not write world/G/K/O_t/canonical parameters
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from .pressure_action_calibration_rc1 import (
    TASK2_2_CALIBRATION_STATUS,
    TASK2_2_MAPPING_SOURCE,
    calibrate_pressure_action_map,
)
from .pressure_action_map_rc1 import build_initial_pressure_action_map


TASK2_3_ADAPTER_PROFILE = "pressure_intent_to_action_candidate_adapter_rc1"
TASK2_3_CONTRACT = (
    "pressure_intent_to_action_candidate_adapter__basic_action_correspondence_only__"
    "candidate_only__no_state_timing_or_final_decision__Task2_3_RC1"
)
BASIC_ACTION_MAP_VERSION = "pressure_action_basic_correspondence_map_rc1"
BASIC_ACTION_MAP_SOURCE = "state_band_aggregated_pressure_action_map"
BASIC_ACTION_MAP_STATUS = "basic_action_correspondence_from_available_map"

PRESSURE_INTENT_KEYS = [
    "pressure_component",
    "component_direction",
    "semantic_effect",
]

REQUIRED_ACTION_CANDIDATE_COLUMNS = [
    "entity_id",
    "action_channel",
    "action_strength",
    "direction",
    "candidate_status",
    "action_candidate_contract",
    "planning_stage",
    "pressure_intent_used",
    "candidate_only",
    "final_action_decision",
    "state_timing_evaluation_performed",
    "state_dependent_effect_evaluation_performed",
    "safety_decision_performed",
    "action_frame_created_by_adapter",
    "actionmodule_called_by_adapter",
    "world_write_performed",
    "gk_writeback_performed",
    "ot_writeback_performed",
    "canonical_parameter_write",
    "pseudo_pressure_used",
    "diagnostic_only",
    "diagnostic_compat_policy_used",
    "repaired_diagnostic_policy_used",
    "upper_pressure_reception_policy_used",
    "action_policy_profile",
    "pressure_intent_to_action_candidate_adapter_used",
    "pressure_intent_source",
    "pressure_component",
    "component_direction",
    "component_magnitude",
    "h11_received_abs_pressure",
    "semantic_effect",
    "intent_family",
    "suggested_control_route",
    "pressure_action_map_version",
    "mapping_source",
    "calibration_status",
    "mapping_confidence",
    "action_correspondence_share",
    "estimated_pressure_alignment",
    "estimated_side_effect_burden",
    "estimated_reversibility_effect",
    "estimated_exploration_effect",
    "state_band_aggregation_used",
    "state_band_aggregation_method",
    "basic_action_correspondence_only",
    "candidate_risk",
    "risk_score",
    "route_risk",
    "task2_3_contract",
]


@dataclass(frozen=True)
class CandidateStrengthConfig:
    """Weak candidate-strength bounds for candidate generation only."""

    max_candidate_strength: float = 0.030
    min_candidate_strength: float = 0.0
    h11_abs_weight: float = 1.0
    component_magnitude_weight: float = 0.35


def _direction_value(component_direction: Any) -> float:
    direction = str(component_direction)
    if direction == "increase":
        return 1.0
    if direction == "decrease":
        return -1.0
    return 0.0


def _safe_numeric(row: pd.Series, col: str, default: float = 0.0) -> float:
    try:
        value = row.get(col, default)
        if pd.isna(value):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _source_entity_id(row: pd.Series, idx: int) -> str:
    for col in ("entity_id", "target_entity_id", "graph_object_id"):
        value = row.get(col, None)
        if value is not None and not pd.isna(value) and str(value):
            return str(value)
    h11_dimension = str(row.get("h11_dimension", "global_pressure_intent"))
    return f"pressure_intent_candidate::{h11_dimension}::{idx:05d}"


def _choose_share_column(df: pd.DataFrame) -> str:
    if "calibrated_action_share" in df.columns:
        return "calibrated_action_share"
    if "initial_action_share" in df.columns:
        return "initial_action_share"
    raise ValueError("pressure-action map must contain calibrated_action_share or initial_action_share")


def build_basic_action_correspondence_map(pressure_action_map: pd.DataFrame | None = None) -> pd.DataFrame:
    """Build a state-independent basic pressure-action correspondence map.

    Task 2-3 intentionally does not decide timing or state-dependent suitability.
    If the supplied map contains state-band rows, this function averages them
    into a basic correspondence map and renormalizes shares by pressure intent.
    """
    if pressure_action_map is None:
        try:
            pressure_action_map = calibrate_pressure_action_map()
        except Exception:
            pressure_action_map = build_initial_pressure_action_map()
    if pressure_action_map is None or pressure_action_map.empty:
        return pd.DataFrame()

    src = pressure_action_map.copy()
    share_col = _choose_share_column(src)
    src["_map_share"] = pd.to_numeric(src[share_col], errors="coerce").fillna(0.0).clip(lower=0.0)
    for col in [
        "estimated_side_effect_burden",
        "measured_side_effect_burden",
        "estimated_reversibility_effect",
        "measured_reversibility_effect",
        "estimated_exploration_effect",
        "measured_exploration_effect",
        "estimated_pressure_alignment",
        "mapping_confidence",
        "sample_count",
        "mapping_source",
        "calibration_status",
        "pressure_action_map_version",
        "action_primitive",
        "primitive_selection_status",
    ]:
        if col not in src.columns:
            src[col] = pd.NA

    group_cols = [
        "pressure_component",
        "component_direction",
        "semantic_effect",
        "control_domain",
        "intent_family",
        "suggested_control_route",
        "action_channel",
    ]
    records: list[dict] = []
    for key, group in src.groupby(group_cols, dropna=False):
        values = dict(zip(group_cols, key if isinstance(key, tuple) else (key,)))
        share_mean = float(pd.to_numeric(group["_map_share"], errors="coerce").fillna(0.0).mean())
        side_col = "measured_side_effect_burden" if "measured_side_effect_burden" in group.columns else "estimated_side_effect_burden"
        rev_col = "measured_reversibility_effect" if "measured_reversibility_effect" in group.columns else "estimated_reversibility_effect"
        exp_col = "measured_exploration_effect" if "measured_exploration_effect" in group.columns else "estimated_exploration_effect"
        align_col = "measured_pressure_alignment_raw" if "measured_pressure_alignment_raw" in group.columns else "estimated_pressure_alignment"
        records.append({
            **values,
            "pressure_action_map_version": BASIC_ACTION_MAP_VERSION,
            "source_pressure_action_map_version_values": ",".join(sorted(group["pressure_action_map_version"].dropna().astype(str).unique())),
            "mapping_source": BASIC_ACTION_MAP_SOURCE,
            "source_mapping_values": ",".join(sorted(group["mapping_source"].dropna().astype(str).unique())),
            "calibration_status": BASIC_ACTION_MAP_STATUS,
            "source_calibration_status_values": ",".join(sorted(group["calibration_status"].dropna().astype(str).unique())),
            "mapping_confidence": "medium_low" if TASK2_2_CALIBRATION_STATUS in set(group["calibration_status"].astype(str)) else "low",
            "action_primitive": str(group["action_primitive"].dropna().astype(str).iloc[0]) if group["action_primitive"].dropna().shape[0] else "primitive_deferred_to_later_action_surface_context",
            "primitive_selection_status": str(group["primitive_selection_status"].dropna().astype(str).iloc[0]) if group["primitive_selection_status"].dropna().shape[0] else "deferred_until_later_action_surface_context",
            "action_correspondence_share_raw": share_mean,
            "estimated_pressure_alignment_raw": float(pd.to_numeric(group[align_col], errors="coerce").fillna(0.0).mean()),
            "estimated_side_effect_burden": float(pd.to_numeric(group[side_col], errors="coerce").fillna(0.0).mean()),
            "estimated_reversibility_effect": float(pd.to_numeric(group[rev_col], errors="coerce").fillna(0.0).mean()),
            "estimated_exploration_effect": float(pd.to_numeric(group[exp_col], errors="coerce").fillna(0.0).mean()),
            "sample_count": int(pd.to_numeric(group["sample_count"], errors="coerce").fillna(0).sum()),
            "state_band_aggregation_used": bool("scenario_or_state_band" in group.columns and group["scenario_or_state_band"].nunique(dropna=False) > 1),
            "state_band_aggregation_method": "mean_over_available_state_bands__timing_not_evaluated",
            "runtime_policy_input": False,
            "basic_action_correspondence_only": True,
        })
    out = pd.DataFrame(records)
    if out.empty:
        return out

    normalized: list[pd.DataFrame] = []
    for _, group in out.groupby(PRESSURE_INTENT_KEYS, dropna=False):
        g = group.copy()
        raw = pd.to_numeric(g["action_correspondence_share_raw"], errors="coerce").fillna(0.0)
        total = float(raw.sum())
        if total <= 1e-12:
            g["action_correspondence_share"] = 1.0 / max(len(g), 1)
        else:
            g["action_correspondence_share"] = raw / total
        g["estimated_pressure_alignment"] = g["action_correspondence_share"].astype(float)
        normalized.append(g)
    return pd.concat(normalized, ignore_index=True)


class PressureIntentToActionCandidateAdapter:
    """Build pre-gate action candidates from PressureIntentBundle rows."""

    profile = TASK2_3_ADAPTER_PROFILE
    contract = TASK2_3_CONTRACT

    def __init__(self, strength_config: CandidateStrengthConfig | None = None):
        self.strength_config = strength_config or CandidateStrengthConfig()

    def build_action_candidates(
        self,
        pressure_intents: pd.DataFrame,
        pressure_action_map: pd.DataFrame | None = None,
    ) -> pd.DataFrame:
        if pressure_intents is None or pressure_intents.empty:
            return pd.DataFrame(columns=REQUIRED_ACTION_CANDIDATE_COLUMNS)
        required = set(PRESSURE_INTENT_KEYS) | {"component_magnitude", "h11_received_abs_pressure"}
        missing = sorted(required - set(pressure_intents.columns))
        if missing:
            raise ValueError(f"PressureIntentBundle missing required columns for Task2-3 adapter: {missing}")

        basic_map = build_basic_action_correspondence_map(pressure_action_map)
        if basic_map is None or basic_map.empty:
            return pd.DataFrame(columns=REQUIRED_ACTION_CANDIDATE_COLUMNS)

        merged = pressure_intents.reset_index(drop=False).rename(columns={"index": "pressure_intent_row_id"}).merge(
            basic_map,
            on=PRESSURE_INTENT_KEYS,
            how="inner",
            suffixes=("", "_map"),
        )
        if merged.empty:
            return pd.DataFrame(columns=REQUIRED_ACTION_CANDIDATE_COLUMNS)

        rows: list[dict] = []
        cfg = self.strength_config
        for idx, row in merged.iterrows():
            component_magnitude = _safe_numeric(row, "component_magnitude", 0.0)
            h11_abs = _safe_numeric(row, "h11_received_abs_pressure", 0.0)
            share = _safe_numeric(row, "action_correspondence_share", 0.0)
            signal = max(0.0, cfg.h11_abs_weight * h11_abs + cfg.component_magnitude_weight * component_magnitude)
            strength = float(np.clip(signal * share * cfg.max_candidate_strength, cfg.min_candidate_strength, cfg.max_candidate_strength))
            side_effect = _safe_numeric(row, "estimated_side_effect_burden", 0.0)
            candidate_risk = float(np.clip(side_effect, 0.0, 1.0))
            record = {
                "entity_id": _source_entity_id(row, int(idx)),
                "action_channel": str(row.get("action_channel", "no_op")),
                "action_strength": strength,
                "direction": _direction_value(row.get("component_direction", "neutral")),
                "candidate_status": "pre_gate_candidate",
                "action_candidate_contract": TASK2_3_CONTRACT,
                "planning_stage": "pressure_intent_to_action_candidate_adaptation",
                "pressure_intent_used": True,
                "candidate_only": True,
                "final_action_decision": False,
                "state_timing_evaluation_performed": False,
                "state_dependent_effect_evaluation_performed": False,
                "safety_decision_performed": False,
                "action_frame_created_by_adapter": False,
                "actionmodule_called_by_adapter": False,
                "world_write_performed": False,
                "gk_writeback_performed": False,
                "ot_writeback_performed": False,
                "canonical_parameter_write": False,
                "pseudo_pressure_used": False,
                "diagnostic_only": False,
                "diagnostic_compat_policy_used": False,
                "repaired_diagnostic_policy_used": False,
                "upper_pressure_reception_policy_used": True,
                "action_policy_profile": TASK2_3_ADAPTER_PROFILE,
                "pressure_intent_to_action_candidate_adapter_used": True,
                "pressure_intent_source": str(row.get("pressure_intent_source", "formal_gk_upper_pressure__pressure_intent_bundle")),
                "pressure_component": str(row.get("pressure_component", "")),
                "component_direction": str(row.get("component_direction", "")),
                "component_magnitude": component_magnitude,
                "h11_received_abs_pressure": h11_abs,
                "semantic_effect": str(row.get("semantic_effect", "")),
                "intent_family": str(row.get("intent_family", row.get("intent_family_map", ""))),
                "suggested_control_route": str(row.get("suggested_control_route", row.get("suggested_control_route_map", ""))),
                "pressure_action_map_version": str(row.get("pressure_action_map_version", "")),
                "mapping_source": str(row.get("mapping_source", "")),
                "calibration_status": str(row.get("calibration_status", "")),
                "mapping_confidence": str(row.get("mapping_confidence", "")),
                "action_correspondence_share": share,
                "estimated_pressure_alignment": _safe_numeric(row, "estimated_pressure_alignment", share),
                "estimated_side_effect_burden": side_effect,
                "estimated_reversibility_effect": _safe_numeric(row, "estimated_reversibility_effect", 0.0),
                "estimated_exploration_effect": _safe_numeric(row, "estimated_exploration_effect", 0.0),
                "state_band_aggregation_used": bool(row.get("state_band_aggregation_used", False)),
                "state_band_aggregation_method": str(row.get("state_band_aggregation_method", "none")),
                "basic_action_correspondence_only": True,
                "candidate_risk": candidate_risk,
                "risk_score": candidate_risk,
                "route_risk": candidate_risk,
                "pressure_intent_row_id": int(row.get("pressure_intent_row_id", idx)),
                "task2_3_contract": TASK2_3_CONTRACT,
            }
            for optional in ["seed", "scenario", "t", "generator", "phase_bin", "h11_dimension"]:
                if optional in row.index:
                    record[optional] = row.get(optional)
            rows.append(record)

        out = pd.DataFrame(rows)
        first = [c for c in REQUIRED_ACTION_CANDIDATE_COLUMNS if c in out.columns]
        rest = [c for c in out.columns if c not in first]
        return out[first + rest]


def validate_pressure_intent_action_candidates(action_candidates: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    if action_candidates is None or action_candidates.empty:
        return ["pressure_intent_action_candidates_empty"]
    missing = sorted(set(REQUIRED_ACTION_CANDIDATE_COLUMNS) - set(action_candidates.columns))
    if missing:
        errors.append(f"pressure_intent_action_candidates_required_columns_missing:{','.join(missing)}")
        return errors
    if not bool(action_candidates["candidate_only"].astype(bool).all()):
        errors.append("pressure_intent_action_candidates_not_all_candidate_only")
    if bool(action_candidates["final_action_decision"].astype(bool).any()):
        errors.append("pressure_intent_action_candidates_claim_final_action_decision")
    for col in [
        "state_timing_evaluation_performed",
        "state_dependent_effect_evaluation_performed",
        "safety_decision_performed",
        "action_frame_created_by_adapter",
        "actionmodule_called_by_adapter",
        "world_write_performed",
        "gk_writeback_performed",
        "ot_writeback_performed",
        "canonical_parameter_write",
        "pseudo_pressure_used",
        "diagnostic_only",
        "diagnostic_compat_policy_used",
        "repaired_diagnostic_policy_used",
    ]:
        if bool(action_candidates[col].astype(bool).any()):
            errors.append(f"pressure_intent_action_candidates_forbidden_true_column:{col}")
    strengths = pd.to_numeric(action_candidates["action_strength"], errors="coerce")
    if bool(strengths.isna().any() or (strengths < -1e-12).any() or (strengths > 1.0 + 1e-12).any()):
        errors.append("pressure_intent_action_candidate_strength_out_of_bounds")
    shares = pd.to_numeric(action_candidates["action_correspondence_share"], errors="coerce")
    if bool(shares.isna().any() or (shares < -1e-12).any() or (shares > 1.0 + 1e-12).any()):
        errors.append("pressure_intent_action_candidate_share_out_of_bounds")
    if not bool(action_candidates["upper_pressure_reception_policy_used"].astype(bool).all()):
        errors.append("pressure_intent_action_candidates_missing_upper_pressure_reception_flag")
    if not bool(action_candidates["pressure_intent_to_action_candidate_adapter_used"].astype(bool).all()):
        errors.append("pressure_intent_action_candidates_missing_adapter_flag")
    return errors


def build_and_validate_pressure_intent_action_candidates(
    pressure_intents: pd.DataFrame,
    pressure_action_map: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    adapter = PressureIntentToActionCandidateAdapter()
    candidates = adapter.build_action_candidates(pressure_intents, pressure_action_map)
    return candidates, validate_pressure_intent_action_candidates(candidates)
