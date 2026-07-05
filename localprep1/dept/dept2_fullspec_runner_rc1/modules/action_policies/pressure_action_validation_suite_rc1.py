"""pressure_action_validation_suite_rc1: Task 2-4 validation suite.

Task: ActionModule UpperPressure Reception Split RC1 / Task 2-4.

This module validates pressure-action correspondence before FullSpec runtime
connection.  It checks three things:

    1. single-action pressure correspondence
    2. whether basic action correspondence can be treated as approximately
       state-independent
    3. whether combined action effects are additive, cancelling, amplifying, or
       side-effect amplifying

The suite is validation-only and does not call ActionPlanner, ActionModule, or
world runtime.  It does not tune the runtime path.
"""
from __future__ import annotations

from itertools import combinations
from typing import Iterable

import numpy as np
import pandas as pd

from .pressure_action_calibration_rc1 import (
    CHANNELS,
    STATE_BANDS,
    _pressure_alignment_for_effect,
    _probe_action_effect,
    _side_effect_burden,
    _synthetic_action_frame,
    calibrate_pressure_action_map,
)
from .pressure_action_map_rc1 import build_initial_pressure_action_map


TASK2_4_VALIDATION_VERSION = "pressure_action_correspondence_validation_suite_rc1"
TASK2_4_CONTRACT = (
    "pressure_action_correspondence_validation__single_state_dependence_combination__"
    "validation_only__not_runtime_policy_input__Task2_4_RC1"
)
ACTION_CHANNELS_FOR_COMBINATION = tuple(ch for ch in CHANNELS if ch != "no_op")
DEFAULT_ACTION_STRENGTH = 0.12
STATE_DEPENDENCE_RELATIVE_TOLERANCE = 0.35
NON_ADDITIVITY_TOLERANCE = 0.012

COMBINATION_FIELDS = [
    "exploration_delta",
    "reversibility_delta",
    "net_public_effect_score",
    "net_hidden_effect_score",
    "hidden_damage_delta",
    "fatigue_delta",
    "resource_inequality_delta",
    "action_cost_effect",
    "trust_delta",
]


def build_single_action_pressure_alignment_validation(
    seeds: Iterable[int] = (19,),
    state_bands: Iterable[str] = STATE_BANDS,
    action_strength: float = DEFAULT_ACTION_STRENGTH,
) -> pd.DataFrame:
    """Validate action-channel alignment for every pressure intent and state band."""
    initial_map = build_initial_pressure_action_map()
    rows: list[dict] = []
    for seed in seeds:
        for state_band in state_bands:
            for _, intent in initial_map.iterrows():
                channel = str(intent["action_channel"])
                frame = _synthetic_action_frame(str(state_band), channel, int(seed), float(action_strength))
                response = _probe_action_effect(frame)
                baseline = _probe_action_effect(_synthetic_action_frame(str(state_band), "no_op", int(seed), float(action_strength)))
                row = {
                    **intent.to_dict(),
                    "task2_4_validation_version": TASK2_4_VALIDATION_VERSION,
                    "task2_4_contract": TASK2_4_CONTRACT,
                    "validation_type": "single_action_pressure_alignment",
                    "validation_only": True,
                    "runtime_policy_input": False,
                    "seed": int(seed),
                    "scenario_or_state_band": str(state_band),
                    "action_strength": float(action_strength),
                    "delta_vs_no_op_exploration": float(response["exploration_delta"] - baseline["exploration_delta"]),
                    "delta_vs_no_op_reversibility": float(response["reversibility_delta"] - baseline["reversibility_delta"]),
                    "delta_vs_no_op_public_effect": float(response["net_public_effect_score"] - baseline["net_public_effect_score"]),
                    "delta_vs_no_op_hidden_effect": float(response["net_hidden_effect_score"] - baseline["net_hidden_effect_score"]),
                    "delta_vs_no_op_hidden_damage": float(response["hidden_damage_delta"] - baseline["hidden_damage_delta"]),
                    "delta_vs_no_op_fatigue": float(response["fatigue_delta"] - baseline["fatigue_delta"]),
                    "delta_vs_no_op_resource_inequality": float(response["resource_inequality_delta"] - baseline["resource_inequality_delta"]),
                    "delta_vs_no_op_cost": float(response["action_cost_effect"] - baseline["action_cost_effect"]),
                    "delta_vs_no_op_trust": float(response["trust_delta"] - baseline["trust_delta"]),
                }
                row["side_effect_burden_score"] = _side_effect_burden(row)
                row["pressure_alignment_score"] = _pressure_alignment_for_effect(
                    str(intent["semantic_effect"]),
                    str(intent["intent_family"]),
                    pd.Series(row),
                )
                row["pressure_alignment_status"] = "aligned" if row["pressure_alignment_score"] > 0 else "weak_or_unresolved"
                rows.append(row)
    return pd.DataFrame(rows)


def summarize_state_dependence(alignment_validation: pd.DataFrame | None = None) -> pd.DataFrame:
    """Summarize whether action-pressure correspondence varies by state band."""
    df = build_single_action_pressure_alignment_validation() if alignment_validation is None else alignment_validation.copy()
    if df.empty:
        return pd.DataFrame()
    rows: list[dict] = []
    group_cols = ["pressure_component", "component_direction", "semantic_effect", "action_channel"]
    for key, group in df.groupby(group_cols, dropna=False):
        values = dict(zip(group_cols, key if isinstance(key, tuple) else (key,)))
        scores = pd.to_numeric(group["pressure_alignment_score"], errors="coerce").fillna(0.0)
        mean = float(scores.mean())
        spread = float(scores.max() - scores.min())
        denom = max(abs(mean), 1e-9)
        relative_spread = float(spread / denom)
        side = pd.to_numeric(group["side_effect_burden_score"], errors="coerce").fillna(0.0)
        side_spread = float(side.max() - side.min())
        status = "approximately_state_independent" if relative_spread <= STATE_DEPENDENCE_RELATIVE_TOLERANCE else "state_dependent"
        if mean <= 1e-12 and spread <= 1e-12:
            status = "weak_or_unresolved_all_states"
        rows.append({
            **values,
            "task2_4_validation_version": TASK2_4_VALIDATION_VERSION,
            "task2_4_contract": TASK2_4_CONTRACT,
            "validation_type": "state_dependence_summary",
            "validation_only": True,
            "runtime_policy_input": False,
            "mean_pressure_alignment_score": mean,
            "min_pressure_alignment_score": float(scores.min()),
            "max_pressure_alignment_score": float(scores.max()),
            "pressure_alignment_spread": spread,
            "relative_pressure_alignment_spread": relative_spread,
            "mean_side_effect_burden_score": float(side.mean()),
            "side_effect_burden_spread": side_spread,
            "state_dependence_status": status,
            "state_dependence_relative_tolerance": STATE_DEPENDENCE_RELATIVE_TOLERANCE,
        })
    return pd.DataFrame(rows)


def _combine_action_effects(
    state_band: str,
    channel_a: str,
    channel_b: str,
    seed: int,
    action_strength: float,
) -> dict:
    """Synthetic combination response with bounded interaction terms.

    This deliberately keeps combination testing validation-local.  The
    interaction terms make it possible to detect non-additivity without changing
    runtime pseudo-reality or ActionModule semantics.
    """
    eff_a = _probe_action_effect(_synthetic_action_frame(state_band, channel_a, seed, action_strength))
    eff_b = _probe_action_effect(_synthetic_action_frame(state_band, channel_b, seed, action_strength))
    out = {"action_channel": f"{channel_a}+{channel_b}", "action_intensity": action_strength, "target_count": 1}
    for field in COMBINATION_FIELDS:
        out[field] = float(eff_a.get(field, 0.0) + eff_b.get(field, 0.0))

    risk_factor = {"stable": 0.20, "medium": 0.50, "high": 0.78, "limit": 1.00}[state_band]
    pair = {channel_a, channel_b}
    # Interaction hypotheses: some combinations amplify useful effects, some
    # amplify hidden burden, and some partially cancel each other.
    if pair == {"exploration_injection", "relation_unlock"}:
        out["hidden_damage_delta"] += 0.07 * action_strength * risk_factor
        out["fatigue_delta"] += 0.05 * action_strength * risk_factor
        out["net_hidden_effect_score"] += 0.12 * action_strength * risk_factor
        out["resource_inequality_delta"] += 0.04 * action_strength * risk_factor
    elif pair == {"buffer_increase", "volatility_damping"}:
        out["reversibility_delta"] += 0.08 * action_strength * (1.0 - 0.20 * risk_factor)
        out["hidden_damage_delta"] -= 0.03 * action_strength * risk_factor
        out["fatigue_delta"] -= 0.03 * action_strength * risk_factor
    elif pair == {"coupling_relief", "relation_unlock"}:
        out["reversibility_delta"] += 0.04 * action_strength * (1.0 - risk_factor)
        out["net_public_effect_score"] += 0.05 * action_strength * (1.0 - 0.50 * risk_factor)
        out["resource_inequality_delta"] += 0.05 * action_strength * risk_factor
    elif pair == {"exploration_injection", "volatility_damping"}:
        out["exploration_delta"] -= 0.04 * action_strength
        out["reversibility_delta"] += 0.03 * action_strength
    elif pair == {"uncertainty_probe", "coupling_relief"}:
        out["trust_delta"] += 0.04 * action_strength
        out["net_hidden_effect_score"] -= 0.03 * action_strength

    out["side_effect_score"] = _side_effect_burden(out)
    out["direct_effect_score"] = float(
        max(out.get("exploration_delta", 0.0), 0.0)
        + max(out.get("reversibility_delta", 0.0), 0.0)
        + max(out.get("net_public_effect_score", 0.0), 0.0)
    )
    out["exploitation_risk_delta"] = float(max(0.0, out.get("hidden_damage_delta", 0.0) + out.get("resource_inequality_delta", 0.0)))
    return out


def build_action_combination_additivity_validation(
    seeds: Iterable[int] = (19,),
    state_bands: Iterable[str] = STATE_BANDS,
    action_strength: float = DEFAULT_ACTION_STRENGTH,
) -> pd.DataFrame:
    """Compare combined action effects against the sum of single-action effects."""
    rows: list[dict] = []
    for seed in seeds:
        for state_band in state_bands:
            for channel_a, channel_b in combinations(ACTION_CHANNELS_FOR_COMBINATION, 2):
                eff_a = _probe_action_effect(_synthetic_action_frame(str(state_band), channel_a, int(seed), float(action_strength)))
                eff_b = _probe_action_effect(_synthetic_action_frame(str(state_band), channel_b, int(seed), float(action_strength)))
                combined = _combine_action_effects(str(state_band), channel_a, channel_b, int(seed), float(action_strength))
                deviations = {field: float(combined.get(field, 0.0) - (eff_a.get(field, 0.0) + eff_b.get(field, 0.0))) for field in COMBINATION_FIELDS}
                abs_total = float(sum(abs(v) for v in deviations.values()))
                useful_dev = float(
                    max(deviations.get("exploration_delta", 0.0), 0.0)
                    + max(deviations.get("reversibility_delta", 0.0), 0.0)
                    + max(deviations.get("net_public_effect_score", 0.0), 0.0)
                    + max(deviations.get("trust_delta", 0.0), 0.0)
                )
                burden_dev = float(
                    max(deviations.get("net_hidden_effect_score", 0.0), 0.0)
                    + max(deviations.get("hidden_damage_delta", 0.0), 0.0)
                    + max(deviations.get("fatigue_delta", 0.0), 0.0)
                    + max(deviations.get("resource_inequality_delta", 0.0), 0.0)
                    + max(deviations.get("action_cost_effect", 0.0), 0.0)
                )
                if abs_total <= NON_ADDITIVITY_TOLERANCE:
                    status = "approximately_additive"
                elif burden_dev > useful_dev and burden_dev > NON_ADDITIVITY_TOLERANCE:
                    status = "side_effect_amplifying"
                elif useful_dev > burden_dev and useful_dev > NON_ADDITIVITY_TOLERANCE:
                    status = "useful_amplifying"
                else:
                    status = "mixed_non_additive"
                rows.append({
                    "task2_4_validation_version": TASK2_4_VALIDATION_VERSION,
                    "task2_4_contract": TASK2_4_CONTRACT,
                    "validation_type": "combination_additivity",
                    "validation_only": True,
                    "runtime_policy_input": False,
                    "seed": int(seed),
                    "scenario_or_state_band": str(state_band),
                    "action_strength": float(action_strength),
                    "action_channel_a": channel_a,
                    "action_channel_b": channel_b,
                    "action_pair": f"{channel_a}+{channel_b}",
                    "non_additivity_score": abs_total,
                    "useful_amplification_score": useful_dev,
                    "side_effect_amplification_score": burden_dev,
                    "combination_additivity_status": status,
                    "non_additivity_tolerance": NON_ADDITIVITY_TOLERANCE,
                    **{f"non_additive_delta_{field}": value for field, value in deviations.items()},
                })
    return pd.DataFrame(rows)


def build_pressure_action_validation_report() -> dict[str, pd.DataFrame]:
    """Build all Task 2-4 validation tables."""
    alignment = build_single_action_pressure_alignment_validation()
    state_dependence = summarize_state_dependence(alignment)
    combination = build_action_combination_additivity_validation()
    calibrated_map = calibrate_pressure_action_map()
    return {
        "single_action_pressure_alignment": alignment,
        "state_dependence_summary": state_dependence,
        "combination_additivity": combination,
        "calibrated_pressure_action_map": calibrated_map,
    }


def summarize_pressure_action_validation_report(report: dict[str, pd.DataFrame] | None = None) -> pd.DataFrame:
    """Return a compact summary row for Task 2-4 validation."""
    tables = build_pressure_action_validation_report() if report is None else report
    state = tables.get("state_dependence_summary", pd.DataFrame())
    combo = tables.get("combination_additivity", pd.DataFrame())
    alignment = tables.get("single_action_pressure_alignment", pd.DataFrame())
    row = {
        "task2_4_validation_version": TASK2_4_VALIDATION_VERSION,
        "task2_4_contract": TASK2_4_CONTRACT,
        "validation_only": True,
        "runtime_policy_input": False,
        "single_action_alignment_rows": int(len(alignment)),
        "state_dependence_rows": int(len(state)),
        "combination_additivity_rows": int(len(combo)),
        "state_dependent_count": int((state["state_dependence_status"].astype(str) == "state_dependent").sum()) if not state.empty else 0,
        "approximately_state_independent_count": int((state["state_dependence_status"].astype(str) == "approximately_state_independent").sum()) if not state.empty else 0,
        "weak_or_unresolved_all_states_count": int((state["state_dependence_status"].astype(str) == "weak_or_unresolved_all_states").sum()) if not state.empty else 0,
        "approximately_additive_pairs": int((combo["combination_additivity_status"].astype(str) == "approximately_additive").sum()) if not combo.empty else 0,
        "useful_amplifying_pairs": int((combo["combination_additivity_status"].astype(str) == "useful_amplifying").sum()) if not combo.empty else 0,
        "side_effect_amplifying_pairs": int((combo["combination_additivity_status"].astype(str) == "side_effect_amplifying").sum()) if not combo.empty else 0,
        "mixed_non_additive_pairs": int((combo["combination_additivity_status"].astype(str) == "mixed_non_additive").sum()) if not combo.empty else 0,
    }
    return pd.DataFrame([row])


def validate_pressure_action_validation_report(report: dict[str, pd.DataFrame] | None = None) -> list[str]:
    tables = build_pressure_action_validation_report() if report is None else report
    errors: list[str] = []
    required = {
        "single_action_pressure_alignment",
        "state_dependence_summary",
        "combination_additivity",
        "calibrated_pressure_action_map",
    }
    missing = sorted(required - set(tables.keys()))
    if missing:
        errors.append(f"task2_4_report_missing_tables:{','.join(missing)}")
        return errors
    for name in required:
        if tables[name] is None or tables[name].empty:
            errors.append(f"task2_4_report_empty_table:{name}")
    for name, df in tables.items():
        if df is not None and not df.empty and "runtime_policy_input" in df.columns and bool(df["runtime_policy_input"].astype(bool).any()):
            errors.append(f"task2_4_report_runtime_policy_input_true:{name}")
    combo = tables.get("combination_additivity", pd.DataFrame())
    if not combo.empty and not bool((pd.to_numeric(combo["non_additivity_score"], errors="coerce").fillna(0.0) >= 0.0).all()):
        errors.append("task2_4_combination_non_additivity_score_invalid")
    state = tables.get("state_dependence_summary", pd.DataFrame())
    if not state.empty and not set(state["state_dependence_status"].astype(str)).issubset({"approximately_state_independent", "state_dependent", "weak_or_unresolved_all_states"}):
        errors.append("task2_4_state_dependence_status_invalid")
    return errors
