"""Task 2-7: insurance-style terrain action gate RC1.

This module is deliberately not a pressure route splitter.  It keeps the upper
pressure information and uses terrain risk to decide whether a six-action
candidate should be surfaced as:

- insurance-triggered candidate in dangerous terrain,
- safe-gain probe in low-risk terrain, or
- hold/sandbox/local-audit candidate when risk is unclear.

Boundary:
    - reads pressure-derived six-action candidates and terrain/local observation
      features
    - preserves pressure information instead of selecting pressure components to
      discard
    - uses terrain risk as a timing/location gate
    - emits pre-ActionFrame proposals only
    - does not create ActionFrame
    - does not call ActionModule or world runtime
    - does not write back to G/K/O_t/canonical parameters
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Iterable

import pandas as pd

from .pressure_action_task2_6_converter_rc1 import (
    NO_ACTION_CANDIDATE,
    convert_pressure_inputs_to_action_candidates,
)


TASK2_7_INSURANCE_GATE_VERSION = "insurance_terrain_action_gate_rc1"
TASK2_7_INSURANCE_GATE_CONTRACT = (
    "Task2_7_insurance_terrain_gate__terrain_timing_location_gate__"
    "keeps_pressure_information__six_action_vocabulary_only__pre_ActionFrame_only"
)

SIX_ACTIONS = {
    "exploration_injection",
    "relation_unlock",
    "volatility_damping",
    "uncertainty_probe",
    "coupling_relief",
    "buffer_increase",
}
INSURANCE_ACTIONS = {"buffer_increase", "volatility_damping", "uncertainty_probe"}
OPENING_ACTIONS = {"exploration_injection", "relation_unlock", "coupling_relief"}
SAFE_GAIN_ACTIONS = {"exploration_injection", "uncertainty_probe", "buffer_increase"}

REQUIRED_TERRAIN_COLUMNS = [
    "terrain_location_id",
    "boundary_risk_score",
    "instability_score",
    "recovery_margin",
    "trend_risk_score",
    "local_uncertainty_score",
]

OPTIONAL_TERRAIN_COLUMNS = [
    "terrain_gain_potential_score",
    "ot_residual_score",
    "ot_unresolved_score",
    "ot_ambiguity_score",
    "exploration_axis_gain_score",
    "macro_trend_gain_score",
]

REQUIRED_TASK2_7_COLUMNS = [
    "task2_7_gate_version",
    "task2_7_gate_contract",
    "gate_type",
    "pre_actionframe_only",
    "candidate_only",
    "runtime_policy_input",
    "final_action_decision",
    "action_frame_created",
    "actionmodule_called",
    "world_runtime_called",
    "canonical_write_performed",
    "pressure_information_preserved",
    "pressure_route_split_performed",
    "uses_six_action_vocabulary_only",
    "pressure_input_id",
    "pressure_component",
    "component_direction",
    "pressure_strength",
    "semantic_effect",
    "intent_family",
    "suggested_control_route",
    "action_channel",
    "action_name_ja",
    "candidate_status_from_converter",
    "terrain_location_id",
    "terrain_risk_score",
    "terrain_risk_band",
    "terrain_gain_score",
    "insurance_need_score",
    "safe_gain_opportunity_score",
    "terrain_trigger_reason",
    "gate_decision",
    "recommended_action_mode",
    "recommended_action_strength_hint",
    "requires_local_audit_before_action",
    "requires_sandbox_before_action",
    "insurance_fallback_used",
    "safe_gain_probe_used",
    "pressure_signal",
    "expected_result_signal",
    "pressure_result_gap",
    "unresolved_pressure_intent",
    "action_vocabulary_fit_score",
    "new_action_channel_candidate_flag",
    "terrain_gate_audit_note",
]


@dataclass(frozen=True)
class InsuranceTerrainGateConfig:
    """Thresholds for insurance-style terrain gating.

    These thresholds are intentionally transparent and bounded.  They do not
    learn a fixed side-effect model from terrain; they only decide whether risk
    is high enough to surface a conservative candidate.
    """

    high_risk_threshold: float = 0.68
    medium_risk_threshold: float = 0.42
    safe_gain_risk_ceiling: float = 0.32
    safe_gain_threshold: float = 0.50
    local_audit_threshold: float = 0.45
    sandbox_threshold: float = 0.52
    max_strength_hint: float = 0.18
    low_strength_hint: float = 0.04


def _clip01(value: float) -> float:
    return float(max(0.0, min(1.0, float(value))))


def _require_columns(df: pd.DataFrame, required: Iterable[str], name: str) -> None:
    missing = sorted(set(required) - set(df.columns))
    if missing:
        raise ValueError(f"{name}_required_columns_missing:" + ",".join(missing))


def _num(row: pd.Series, key: str, default: float = 0.0) -> float:
    try:
        value = row.get(key, default)
        if pd.isna(value):
            return float(default)
        return float(value)
    except Exception:
        return float(default)


def compute_terrain_risk(row: pd.Series) -> float:
    """Compute macro terrain risk without using a fixed side-effect lookup.

    The score combines boundary pressure, instability, poor recovery margin,
    macro trend risk, local uncertainty, and unresolved local observation.
    """
    boundary = _num(row, "boundary_risk_score")
    instability = _num(row, "instability_score")
    recovery_deficit = 1.0 - _num(row, "recovery_margin")
    trend = _num(row, "trend_risk_score")
    uncertainty = _num(row, "local_uncertainty_score")
    residual = max(_num(row, "ot_residual_score"), _num(row, "ot_unresolved_score"), _num(row, "ot_ambiguity_score"))
    risk = (
        0.22 * boundary
        + 0.22 * instability
        + 0.20 * recovery_deficit
        + 0.16 * trend
        + 0.12 * uncertainty
        + 0.08 * residual
    )
    return _clip01(risk)


def compute_terrain_gain(row: pd.Series) -> float:
    """Compute low-risk gain opportunity from terrain/exploration hints."""
    explicit_gain = _num(row, "terrain_gain_potential_score")
    axis_gain = _num(row, "exploration_axis_gain_score")
    macro_gain = _num(row, "macro_trend_gain_score")
    uncertainty = _num(row, "local_uncertainty_score")
    # Some uncertainty is useful for probing, but very high uncertainty is handled
    # by the risk gate and local-audit/sandbox flags.
    probeable_uncertainty = max(0.0, 1.0 - abs(uncertainty - 0.35) / 0.35) if uncertainty <= 0.70 else 0.0
    return _clip01(0.42 * explicit_gain + 0.30 * axis_gain + 0.18 * macro_gain + 0.10 * probeable_uncertainty)


def _risk_band(score: float, cfg: InsuranceTerrainGateConfig) -> str:
    if score >= cfg.high_risk_threshold:
        return "high"
    if score >= cfg.medium_risk_threshold:
        return "medium"
    return "low"


def _terrain_reason(row: pd.Series, risk: float, gain: float, band: str) -> str:
    drivers = {
        "境界接近": _num(row, "boundary_risk_score"),
        "不安定": _num(row, "instability_score"),
        "回復余地不足": 1.0 - _num(row, "recovery_margin"),
        "悪化傾向": _num(row, "trend_risk_score"),
        "局所不確実性": _num(row, "local_uncertainty_score"),
        "未解決観測": max(_num(row, "ot_residual_score"), _num(row, "ot_unresolved_score"), _num(row, "ot_ambiguity_score")),
        "利得余地": gain,
    }
    top = sorted(drivers.items(), key=lambda item: item[1], reverse=True)[:3]
    return f"risk_band={band}; risk={risk:.3f}; gain={gain:.3f}; drivers=" + ", ".join(f"{k}:{v:.2f}" for k, v in top)


def _decision_for_candidate(
    candidate: pd.Series,
    terrain: pd.Series,
    cfg: InsuranceTerrainGateConfig,
) -> dict[str, object]:
    action = str(candidate["action_channel"])
    risk = compute_terrain_risk(terrain)
    gain = compute_terrain_gain(terrain)
    band = _risk_band(risk, cfg)
    pressure_signal = _num(candidate, "pressure_signal")
    unresolved = bool(str(candidate.get("candidate_status", "")).startswith("unresolved") or action == NO_ACTION_CANDIDATE)
    fit = _num(candidate, "action_vocabulary_fit_score")

    insurance_need = _clip01(0.72 * risk + 0.18 * pressure_signal + 0.10 * (1.0 - fit))
    safe_gain = _clip01(0.62 * gain + 0.23 * pressure_signal + 0.15 * fit)

    requires_local_audit = bool(
        risk >= cfg.local_audit_threshold
        or _num(terrain, "local_uncertainty_score") >= cfg.local_audit_threshold
        or _num(terrain, "ot_unresolved_score") >= cfg.local_audit_threshold
        or unresolved
    )
    requires_sandbox = bool(
        risk >= cfg.sandbox_threshold
        or (action in OPENING_ACTIONS and band != "low")
        or unresolved
    )

    if unresolved:
        gate_decision = "hold_unresolved_pressure_intent"
        mode = "hold_for_new_action_or_sandbox"
        strength = 0.0
        insurance_fallback = False
        safe_gain_probe = False
        note = "圧は保持するが、6作用語彙に対応候補がないため実作用候補にはしない。"
    elif band == "high" and action in INSURANCE_ACTIONS:
        gate_decision = "surface_insurance_candidate"
        mode = "insurance"
        strength = min(cfg.max_strength_hint, max(cfg.low_strength_hint, 0.05 + 0.13 * insurance_need))
        insurance_fallback = True
        safe_gain_probe = False
        note = "高リスク地形のため、保険型作用候補として弱く表面化。"
    elif band == "high" and action in OPENING_ACTIONS:
        gate_decision = "hold_opening_action_high_risk"
        mode = "hold_or_sandbox"
        strength = 0.0
        insurance_fallback = True
        safe_gain_probe = False
        note = "高リスク地形で開口系作用は危険なため、実作用化せず保険側へ倒す。"
    elif band == "medium":
        gate_decision = "require_local_audit_or_sandbox"
        mode = "audit_before_action"
        strength = min(cfg.max_strength_hint * 0.55, max(0.0, 0.03 + 0.06 * insurance_need)) if action in INSURANCE_ACTIONS else 0.0
        insurance_fallback = action in INSURANCE_ACTIONS
        safe_gain_probe = False
        note = "中リスク地形のため、局所監査またはサンドボックスを要求。"
    elif risk <= cfg.safe_gain_risk_ceiling and gain >= cfg.safe_gain_threshold and action in SAFE_GAIN_ACTIONS:
        gate_decision = "surface_safe_gain_probe_candidate"
        mode = "safe_gain_probe"
        strength = min(cfg.max_strength_hint * 0.45, max(cfg.low_strength_hint, 0.03 + 0.07 * safe_gain))
        insurance_fallback = False
        safe_gain_probe = True
        note = "低リスクかつ利得余地ありのため、小さな利得探索候補として表面化。"
    else:
        gate_decision = "hold_no_terrain_trigger"
        mode = "hold"
        strength = 0.0
        insurance_fallback = False
        safe_gain_probe = False
        note = "地形上の危険発動条件または安全利得条件を満たさないため保留。"

    return {
        "terrain_risk_score": risk,
        "terrain_risk_band": band,
        "terrain_gain_score": gain,
        "insurance_need_score": insurance_need,
        "safe_gain_opportunity_score": safe_gain,
        "terrain_trigger_reason": _terrain_reason(terrain, risk, gain, band),
        "gate_decision": gate_decision,
        "recommended_action_mode": mode,
        "recommended_action_strength_hint": float(strength),
        "requires_local_audit_before_action": requires_local_audit,
        "requires_sandbox_before_action": requires_sandbox,
        "insurance_fallback_used": insurance_fallback,
        "safe_gain_probe_used": safe_gain_probe,
        "terrain_gate_audit_note": note,
    }


def build_insurance_terrain_action_gate_table(
    pressure_inputs: pd.DataFrame,
    terrain_map: pd.DataFrame,
    pressure_candidates: pd.DataFrame | None = None,
    config: InsuranceTerrainGateConfig = InsuranceTerrainGateConfig(),
) -> pd.DataFrame:
    """Build terrain-gated pre-ActionFrame action proposals.

    ``pressure_inputs`` are not route-split or discarded.  If precomputed
    ``pressure_candidates`` are not supplied, Task 2-6 conversion is used to
    create candidate rows first.  The terrain gate then cross-checks each
    candidate against terrain locations.
    """
    _require_columns(terrain_map, REQUIRED_TERRAIN_COLUMNS, "terrain_map")
    if pressure_candidates is None:
        candidates = convert_pressure_inputs_to_action_candidates(pressure_inputs)
    else:
        candidates = pressure_candidates.copy()
    if candidates.empty:
        return pd.DataFrame(columns=REQUIRED_TASK2_7_COLUMNS)

    rows: list[dict] = []
    for _, cand in candidates.reset_index(drop=True).iterrows():
        for _, terrain in terrain_map.reset_index(drop=True).iterrows():
            decision = _decision_for_candidate(cand, terrain, config)
            rows.append({
                "task2_7_gate_version": TASK2_7_INSURANCE_GATE_VERSION,
                "task2_7_gate_contract": TASK2_7_INSURANCE_GATE_CONTRACT,
                "gate_type": "insurance_terrain_timing_location_gate",
                "pre_actionframe_only": True,
                "candidate_only": True,
                "runtime_policy_input": False,
                "final_action_decision": False,
                "action_frame_created": False,
                "actionmodule_called": False,
                "world_runtime_called": False,
                "canonical_write_performed": False,
                "pressure_information_preserved": True,
                "pressure_route_split_performed": False,
                "uses_six_action_vocabulary_only": bool(str(cand["action_channel"]) in SIX_ACTIONS or str(cand["action_channel"]) == NO_ACTION_CANDIDATE),
                "pressure_input_id": str(cand.get("pressure_input_id", "")),
                "pressure_component": str(cand.get("pressure_component", "")),
                "component_direction": str(cand.get("component_direction", "")),
                "pressure_strength": _num(cand, "pressure_strength"),
                "semantic_effect": str(cand.get("semantic_effect", "")),
                "intent_family": str(cand.get("intent_family", "")),
                "suggested_control_route": str(cand.get("suggested_control_route", "")),
                "action_channel": str(cand.get("action_channel", "")),
                "action_name_ja": str(cand.get("action_name_ja", "")),
                "candidate_status_from_converter": str(cand.get("candidate_status", "")),
                "terrain_location_id": str(terrain["terrain_location_id"]),
                **decision,
                "pressure_signal": _num(cand, "pressure_signal"),
                "expected_result_signal": _num(cand, "expected_result_signal"),
                "pressure_result_gap": _num(cand, "pressure_result_gap"),
                "unresolved_pressure_intent": str(cand.get("unresolved_pressure_intent", "")),
                "action_vocabulary_fit_score": _num(cand, "action_vocabulary_fit_score"),
                "new_action_channel_candidate_flag": bool(cand.get("new_action_channel_candidate_flag", False)),
            })
    out = pd.DataFrame(rows)
    if out.empty:
        return pd.DataFrame(columns=REQUIRED_TASK2_7_COLUMNS)
    out = out.sort_values(
        ["terrain_risk_score", "safe_gain_opportunity_score", "insurance_need_score"],
        ascending=[False, False, False],
    ).reset_index(drop=True)
    return out[REQUIRED_TASK2_7_COLUMNS]


def validate_insurance_terrain_action_gate_table(df: pd.DataFrame, pressure_inputs: pd.DataFrame | None = None) -> list[str]:
    errors: list[str] = []
    if df is None or df.empty:
        return ["task2_7_insurance_gate_table_empty"]
    missing = sorted(set(REQUIRED_TASK2_7_COLUMNS) - set(df.columns))
    if missing:
        errors.append("task2_7_required_columns_missing:" + ",".join(missing))
        return errors

    false_fields = [
        "runtime_policy_input", "final_action_decision", "action_frame_created",
        "actionmodule_called", "world_runtime_called", "canonical_write_performed",
        "pressure_route_split_performed",
    ]
    for field in false_fields:
        if bool(df[field].astype(bool).any()):
            errors.append(f"task2_7_forbidden_true_field:{field}")

    true_fields = [
        "pre_actionframe_only", "candidate_only", "pressure_information_preserved",
        "uses_six_action_vocabulary_only",
    ]
    for field in true_fields:
        if not bool(df[field].astype(bool).all()):
            errors.append(f"task2_7_required_true_field_not_all_true:{field}")

    for col in [
        "terrain_risk_score", "terrain_gain_score", "insurance_need_score",
        "safe_gain_opportunity_score", "action_vocabulary_fit_score",
    ]:
        values = pd.to_numeric(df[col], errors="coerce")
        if bool(values.isna().any() or (values < 0.0).any() or (values > 1.0).any()):
            errors.append(f"task2_7_invalid_unit_score:{col}")

    if not bool(df["gate_decision"].astype(str).isin(["surface_insurance_candidate"]).any()):
        errors.append("task2_7_no_insurance_candidate_surfaced")
    if not bool(df["gate_decision"].astype(str).isin(["surface_safe_gain_probe_candidate"]).any()):
        errors.append("task2_7_no_safe_gain_probe_surfaced")
    if not bool(df["requires_local_audit_before_action"].astype(bool).any()):
        errors.append("task2_7_no_local_audit_required_rows")
    if not bool(df["requires_sandbox_before_action"].astype(bool).any()):
        errors.append("task2_7_no_sandbox_required_rows")

    if pressure_inputs is not None and not pressure_inputs.empty and "pressure_input_id" in pressure_inputs.columns:
        expected = set(pressure_inputs["pressure_input_id"].astype(str))
        observed = set(df["pressure_input_id"].astype(str))
        missing_inputs = sorted(expected - observed)
        if missing_inputs:
            errors.append("task2_7_pressure_inputs_not_preserved:" + ",".join(missing_inputs))

    return errors


def build_demo_terrain_map() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "terrain_location_id": "terrain_high_boundary_instability",
            "boundary_risk_score": 0.92,
            "instability_score": 0.86,
            "recovery_margin": 0.18,
            "trend_risk_score": 0.78,
            "local_uncertainty_score": 0.64,
            "ot_residual_score": 0.55,
            "ot_unresolved_score": 0.50,
            "ot_ambiguity_score": 0.42,
            "terrain_gain_potential_score": 0.10,
            "exploration_axis_gain_score": 0.12,
            "macro_trend_gain_score": 0.08,
        },
        {
            "terrain_location_id": "terrain_medium_uncertain",
            "boundary_risk_score": 0.45,
            "instability_score": 0.48,
            "recovery_margin": 0.46,
            "trend_risk_score": 0.42,
            "local_uncertainty_score": 0.62,
            "ot_residual_score": 0.52,
            "ot_unresolved_score": 0.57,
            "ot_ambiguity_score": 0.51,
            "terrain_gain_potential_score": 0.35,
            "exploration_axis_gain_score": 0.40,
            "macro_trend_gain_score": 0.28,
        },
        {
            "terrain_location_id": "terrain_low_risk_high_gain",
            "boundary_risk_score": 0.12,
            "instability_score": 0.18,
            "recovery_margin": 0.88,
            "trend_risk_score": 0.10,
            "local_uncertainty_score": 0.32,
            "ot_residual_score": 0.12,
            "ot_unresolved_score": 0.10,
            "ot_ambiguity_score": 0.16,
            "terrain_gain_potential_score": 0.82,
            "exploration_axis_gain_score": 0.74,
            "macro_trend_gain_score": 0.63,
        },
    ])


def build_demo_pressure_inputs_for_insurance_gate() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "pressure_input_id": "demo_pressure_exploration_up",
            "pressure_component": "exploration_frequency",
            "component_direction": "increase",
            "pressure_strength": 6.0,
        },
        {
            "pressure_input_id": "demo_pressure_rollback_up",
            "pressure_component": "rollback_sensitivity",
            "component_direction": "increase",
            "pressure_strength": 7.0,
        },
        {
            "pressure_input_id": "demo_pressure_commitment_down",
            "pressure_component": "commitment_strength",
            "component_direction": "decrease",
            "pressure_strength": 8.0,
        },
    ])


def build_and_validate_demo_insurance_terrain_action_gate_table() -> tuple[pd.DataFrame, list[str]]:
    pressure = build_demo_pressure_inputs_for_insurance_gate()
    table = build_insurance_terrain_action_gate_table(pressure, build_demo_terrain_map())
    return table, validate_insurance_terrain_action_gate_table(table, pressure)
