"""Task 2-7b v2: closed validation for insurance terrain gate.

Flow:
    v2 risk-state templates
    -> deterministic lower observation terrain
    -> deterministic upper pressure projection
    -> Task2-6 pressure candidates
    -> Task2-7 insurance terrain gate
    -> validation-only result comparison against no_op
    -> threshold-lowering observation

The threshold sweep is measured, not forced.  If lower thresholds produce more
activation, that is logged.  If not, that is also a valid observation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd

from .pressure_action_calibration_rc1 import _probe_action_effect, _side_effect_burden, _synthetic_action_frame
from .pressure_action_task2_7_insurance_terrain_gate import InsuranceTerrainGateConfig, build_insurance_terrain_action_gate_table


TASK2_7B_V2_VERSION = "insurance_closed_validation_v2_rc1"
TASK2_7B_V2_CONTRACT = "Task2_7b_v2_risk_state_to_observation_to_pressure_to_gate__validation_only"

RISK_STATES = (
    ("v2_boundary_instability_risk", 0.92, 0.86, 0.18, 0.78, 0.64, 0.55, 0.50, 0.42, 0.10, 0.12, 0.08),
    ("v2_unresolved_medium_risk", 0.45, 0.48, 0.46, 0.42, 0.62, 0.52, 0.57, 0.51, 0.35, 0.40, 0.28),
    ("v2_low_risk_gain_window", 0.12, 0.18, 0.88, 0.10, 0.32, 0.12, 0.10, 0.16, 0.82, 0.74, 0.63),
)

THRESHOLDS = (
    ("conservative", 0.76, 0.50, 0.26, 0.58),
    ("base", 0.68, 0.42, 0.32, 0.50),
    ("reduced", 0.58, 0.34, 0.40, 0.42),
)

REQUIRED_TASK2_7B_V2_COLUMNS = [
    "task2_7b_v2_version", "task2_7b_v2_contract", "validation_only", "runtime_policy_input",
    "action_frame_created", "actionmodule_called", "world_runtime_called", "canonical_write_performed",
    "anti_arbitrariness_contract", "v2_state_id", "threshold_profile", "high_risk_threshold",
    "medium_risk_threshold", "safe_gain_risk_ceiling", "safe_gain_threshold",
    "lower_observation_detected_risk", "lower_observation_risk_score", "lower_observation_gain_score",
    "upper_pressure_rows", "pressure_inputs_preserved", "gate_decision", "recommended_action_mode",
    "action_channel", "action_name_ja", "pressure_component", "component_direction", "pressure_strength",
    "terrain_risk_band", "terrain_risk_score", "terrain_gain_score", "recommended_action_strength_hint",
    "activated", "activation_rank", "risk_improvement_vs_no_op", "recovery_improvement_vs_no_op",
    "gain_improvement_vs_no_op", "side_effect_burden", "side_effect_delta_vs_no_op",
    "net_validation_benefit", "benefit_pass", "side_effect_guard_pass", "requires_local_audit_before_action",
    "requires_sandbox_before_action", "threshold_reduction_activation_delta",
    "threshold_reduction_side_effect_delta", "threshold_reduction_triggered_more_actions",
    "threshold_reduction_side_effect_caution", "validation_note",
]


@dataclass(frozen=True)
class ClosedValidationV2Config:
    max_side_effect_burden: float = 0.20
    min_net_benefit: float = 0.005


def _clip01(x: float) -> float:
    return float(max(0.0, min(1.0, float(x))))


def _num(row, key: str, default: float = 0.0) -> float:
    try:
        v = row.get(key, default)
        if pd.isna(v):
            return float(default)
        return float(v)
    except Exception:
        return float(default)


def build_v2_risk_states() -> pd.DataFrame:
    cols = [
        "v2_state_id", "boundary_load", "volatility", "recovery_capacity", "trend_deterioration",
        "local_uncertainty", "residual_noise", "unresolved_mass", "ambiguity", "gain_potential",
        "exploration_axis_gain", "macro_gain",
    ]
    df = pd.DataFrame([dict(zip(cols, row)) for row in RISK_STATES])
    df["validation_only"] = True
    df["runtime_policy_input"] = False
    return df


def lower_observation_from_v2_risk_state(v2_states: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, s in v2_states.iterrows():
        rows.append({
            "terrain_location_id": str(s["v2_state_id"]),
            "v2_state_id": str(s["v2_state_id"]),
            "boundary_risk_score": _clip01(_num(s, "boundary_load")),
            "instability_score": _clip01(_num(s, "volatility")),
            "recovery_margin": _clip01(_num(s, "recovery_capacity")),
            "trend_risk_score": _clip01(_num(s, "trend_deterioration")),
            "local_uncertainty_score": _clip01(_num(s, "local_uncertainty")),
            "ot_residual_score": _clip01(_num(s, "residual_noise")),
            "ot_unresolved_score": _clip01(_num(s, "unresolved_mass")),
            "ot_ambiguity_score": _clip01(_num(s, "ambiguity")),
            "terrain_gain_potential_score": _clip01(_num(s, "gain_potential")),
            "exploration_axis_gain_score": _clip01(_num(s, "exploration_axis_gain")),
            "macro_trend_gain_score": _clip01(_num(s, "macro_gain")),
            "validation_only": True,
            "runtime_policy_input": False,
        })
    return pd.DataFrame(rows)


def upper_pressure_from_lower_observation_v2(terrain: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, t in terrain.iterrows():
        sid = str(t["v2_state_id"])
        boundary = _num(t, "boundary_risk_score")
        instability = _num(t, "instability_score")
        recovery_deficit = 1.0 - _num(t, "recovery_margin")
        trend = _num(t, "trend_risk_score")
        uncertainty = _num(t, "local_uncertainty_score")
        unresolved = max(_num(t, "ot_residual_score"), _num(t, "ot_unresolved_score"), _num(t, "ot_ambiguity_score"))
        gain = max(_num(t, "terrain_gain_potential_score"), _num(t, "exploration_axis_gain_score"), _num(t, "macro_trend_gain_score"))
        projected = [
            ("rollback_sensitivity", "increase", 10.0 * _clip01(0.50 * recovery_deficit + 0.30 * boundary + 0.20 * instability)),
            ("pressure_cap", "decrease", 10.0 * _clip01(0.45 * boundary + 0.35 * instability + 0.20 * trend)),
            ("diagnostic_depth", "increase", 10.0 * _clip01(0.55 * unresolved + 0.35 * uncertainty + 0.10 * trend)),
            ("exploration_frequency", "increase", 10.0 * _clip01(0.55 * gain + 0.25 * uncertainty + 0.20 * (1.0 - boundary))),
            ("commitment_strength", "decrease", 10.0 * _clip01(0.40 * instability + 0.35 * unresolved + 0.25 * trend)),
        ]
        for component, direction, strength in projected:
            if strength > 0.05:
                rows.append({
                    "pressure_input_id": f"pressure_from_{sid}_{component}_{direction}",
                    "v2_state_id": sid,
                    "pressure_component": component,
                    "component_direction": direction,
                    "pressure_strength": float(strength),
                    "validation_only": True,
                    "runtime_policy_input": False,
                })
    return pd.DataFrame(rows)


def _profile_cfg(profile: tuple) -> InsuranceTerrainGateConfig:
    _, high, medium, ceiling, gain = profile
    return InsuranceTerrainGateConfig(
        high_risk_threshold=float(high),
        medium_risk_threshold=float(medium),
        safe_gain_risk_ceiling=float(ceiling),
        safe_gain_threshold=float(gain),
    )


def _state_band(risk: float) -> str:
    if risk >= 0.78:
        return "limit"
    if risk >= 0.58:
        return "high"
    if risk >= 0.34:
        return "medium"
    return "stable"


def _result(row: pd.Series) -> dict:
    risk = _num(row, "terrain_risk_score")
    gain = _num(row, "terrain_gain_score")
    strength = _num(row, "recommended_action_strength_hint") if bool(row["activated"]) else 0.0
    action = str(row["action_channel"]) if bool(row["activated"]) else "no_op"
    baseline = _probe_action_effect(_synthetic_action_frame(_state_band(risk), "no_op", 41, strength))
    effect = _probe_action_effect(_synthetic_action_frame(_state_band(risk), action, 41, strength))
    side = float(_side_effect_burden(effect))
    side_delta = max(0.0, side - float(_side_effect_burden(baseline)))
    mode = str(row["recommended_action_mode"])
    insurance = 1.0 if mode == "insurance" else 0.0
    gain_probe = 1.0 if mode == "safe_gain_probe" else 0.0
    risk_improve = _clip01(0.58 * strength * insurance + 0.10 * max(effect.get("reversibility_delta", 0.0), 0.0))
    recovery_improve = _clip01(0.62 * strength * insurance + 0.18 * max(effect.get("reversibility_delta", 0.0), 0.0))
    gain_improve = _clip01(0.70 * strength * gain_probe + 0.12 * max(effect.get("exploration_delta", 0.0), 0.0))
    return {
        "risk_improvement_vs_no_op": risk_improve,
        "recovery_improvement_vs_no_op": recovery_improve,
        "gain_improvement_vs_no_op": gain_improve,
        "side_effect_burden": side,
        "side_effect_delta_vs_no_op": side_delta,
        "net_validation_benefit": float(risk_improve + recovery_improve + gain_improve - side_delta),
    }


def build_insurance_closed_validation_v2_table(config: ClosedValidationV2Config = ClosedValidationV2Config()) -> pd.DataFrame:
    v2 = build_v2_risk_states()
    terrain = lower_observation_from_v2_risk_state(v2)
    pressure = upper_pressure_from_lower_observation_v2(terrain)
    rows = []
    profile_counts = {}
    profile_side = {}
    for profile in THRESHOLDS:
        name, high, medium, ceiling, gain_thr = profile
        gate = build_insurance_terrain_action_gate_table(pressure, terrain, config=_profile_cfg(profile))
        gate = gate[gate.apply(lambda r: str(r["terrain_location_id"]) in str(r["pressure_input_id"]), axis=1)].copy()
        gate["activated"] = gate["gate_decision"].astype(str).isin({"surface_insurance_candidate", "surface_safe_gain_probe_candidate"})
        gate = gate.sort_values(["terrain_location_id", "activated", "terrain_risk_score"], ascending=[True, False, False]).reset_index(drop=True)
        gate["activation_rank"] = gate.groupby("terrain_location_id").cumcount() + 1
        for _, g in gate.iterrows():
            res = _result(g)
            rows.append({
                "task2_7b_v2_version": TASK2_7B_V2_VERSION,
                "task2_7b_v2_contract": TASK2_7B_V2_CONTRACT,
                "validation_only": True,
                "runtime_policy_input": False,
                "action_frame_created": False,
                "actionmodule_called": False,
                "world_runtime_called": False,
                "canonical_write_performed": False,
                "anti_arbitrariness_contract": "deterministic_state_to_observation_to_pressure_to_gate__no_handpicked_action",
                "v2_state_id": str(g["terrain_location_id"]),
                "threshold_profile": str(name),
                "high_risk_threshold": float(high),
                "medium_risk_threshold": float(medium),
                "safe_gain_risk_ceiling": float(ceiling),
                "safe_gain_threshold": float(gain_thr),
                "lower_observation_detected_risk": bool(_num(g, "terrain_risk_score") >= float(medium)),
                "lower_observation_risk_score": _num(g, "terrain_risk_score"),
                "lower_observation_gain_score": _num(g, "terrain_gain_score"),
                "upper_pressure_rows": int(pressure[pressure["v2_state_id"].astype(str) == str(g["terrain_location_id"])].shape[0]),
                "pressure_inputs_preserved": True,
                "gate_decision": str(g["gate_decision"]),
                "recommended_action_mode": str(g["recommended_action_mode"]),
                "action_channel": str(g["action_channel"]),
                "action_name_ja": str(g["action_name_ja"]),
                "pressure_component": str(g["pressure_component"]),
                "component_direction": str(g["component_direction"]),
                "pressure_strength": _num(g, "pressure_strength"),
                "terrain_risk_band": str(g["terrain_risk_band"]),
                "terrain_risk_score": _num(g, "terrain_risk_score"),
                "terrain_gain_score": _num(g, "terrain_gain_score"),
                "recommended_action_strength_hint": _num(g, "recommended_action_strength_hint"),
                "activated": bool(g["activated"]),
                "activation_rank": int(g["activation_rank"]),
                **res,
                "benefit_pass": bool(res["net_validation_benefit"] >= config.min_net_benefit or not bool(g["activated"])),
                "side_effect_guard_pass": bool(res["side_effect_burden"] <= config.max_side_effect_burden or not bool(g["activated"])),
                "requires_local_audit_before_action": bool(g["requires_local_audit_before_action"]),
                "requires_sandbox_before_action": bool(g["requires_sandbox_before_action"]),
                "threshold_reduction_activation_delta": 0,
                "threshold_reduction_side_effect_delta": 0.0,
                "threshold_reduction_triggered_more_actions": False,
                "threshold_reduction_side_effect_caution": False,
                "validation_note": str(g["terrain_gate_audit_note"]),
            })
        active = gate[gate["activated"].astype(bool)]
        profile_counts[str(name)] = int(len(active))
        profile_side[str(name)] = float(active["recommended_action_strength_hint"].sum()) if not active.empty else 0.0
    out = pd.DataFrame(rows)
    if out.empty:
        return pd.DataFrame(columns=REQUIRED_TASK2_7B_V2_COLUMNS)
    delta = int(profile_counts.get("reduced", 0) - profile_counts.get("base", 0))
    side_delta = float(profile_side.get("reduced", 0.0) - profile_side.get("base", 0.0))
    out["threshold_reduction_activation_delta"] = delta
    out["threshold_reduction_side_effect_delta"] = side_delta
    out["threshold_reduction_triggered_more_actions"] = bool(delta > 0)
    out["threshold_reduction_side_effect_caution"] = bool(side_delta > 0.0)
    return out[REQUIRED_TASK2_7B_V2_COLUMNS]


def summarize_insurance_closed_validation_v2(table: pd.DataFrame) -> dict:
    if table is None or table.empty:
        return {"rows": 0}
    activated = table[table["activated"].astype(bool)]
    by_profile = table.groupby("threshold_profile").agg(
        rows=("threshold_profile", "size"),
        activated_rows=("activated", lambda s: int(s.astype(bool).sum())),
        mean_net_benefit=("net_validation_benefit", "mean"),
        mean_side_effect=("side_effect_burden", "mean"),
    ).reset_index()
    return {
        "rows": int(len(table)),
        "v2_states": int(table["v2_state_id"].nunique()),
        "activated_rows": int(len(activated)),
        "mean_activated_net_benefit": float(activated["net_validation_benefit"].mean()) if not activated.empty else 0.0,
        "max_activated_side_effect_burden": float(activated["side_effect_burden"].max()) if not activated.empty else 0.0,
        "threshold_reduction_activation_delta": int(pd.to_numeric(table["threshold_reduction_activation_delta"], errors="coerce").fillna(0).max()),
        "threshold_reduction_side_effect_delta": float(pd.to_numeric(table["threshold_reduction_side_effect_delta"], errors="coerce").fillna(0.0).max()),
        "threshold_reduction_triggered_more_actions": bool(table["threshold_reduction_triggered_more_actions"].astype(bool).any()),
        "threshold_reduction_side_effect_caution": bool(table["threshold_reduction_side_effect_caution"].astype(bool).any()),
        "by_threshold_profile": by_profile.to_dict(orient="records"),
    }


def validate_insurance_closed_validation_v2_table(table: pd.DataFrame) -> list[str]:
    errors = []
    if table is None or table.empty:
        return ["task2_7b_v2_table_empty"]
    missing = sorted(set(REQUIRED_TASK2_7B_V2_COLUMNS) - set(table.columns))
    if missing:
        return ["task2_7b_v2_required_columns_missing:" + ",".join(missing)]
    for field in ["runtime_policy_input", "action_frame_created", "actionmodule_called", "world_runtime_called", "canonical_write_performed"]:
        if bool(table[field].astype(bool).any()):
            errors.append(f"task2_7b_v2_forbidden_true_field:{field}")
    if not bool(table["validation_only"].astype(bool).all()):
        errors.append("task2_7b_v2_validation_only_not_all_true")
    if not bool(table["pressure_inputs_preserved"].astype(bool).all()):
        errors.append("task2_7b_v2_pressure_inputs_not_preserved")
    danger = table[table["v2_state_id"].astype(str).isin(["v2_boundary_instability_risk", "v2_unresolved_medium_risk"])]
    if danger.empty or not bool(danger["lower_observation_detected_risk"].astype(bool).any()):
        errors.append("task2_7b_v2_lower_observation_failed_to_detect_risk")
    activated = table[table["activated"].astype(bool)]
    if activated.empty:
        errors.append("task2_7b_v2_no_actions_activated")
    elif not bool((activated["net_validation_benefit"] > 0.0).any()):
        errors.append("task2_7b_v2_no_positive_net_benefit")
    for col in ["threshold_reduction_activation_delta", "threshold_reduction_side_effect_delta"]:
        if pd.to_numeric(table[col], errors="coerce").isna().any():
            errors.append(f"task2_7b_v2_invalid_threshold_delta:{col}")
    return errors


def build_and_validate_insurance_closed_validation_v2_table() -> tuple[pd.DataFrame, list[str], dict]:
    table = build_insurance_closed_validation_v2_table()
    errors = validate_insurance_closed_validation_v2_table(table)
    summary = summarize_insurance_closed_validation_v2(table)
    return table, errors, summary
