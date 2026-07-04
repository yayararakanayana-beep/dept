"""Task 2-7c-light: strength sensitivity and 40-step trend validation."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd

from .pressure_action_task2_7_insurance_terrain_gate import InsuranceTerrainGateConfig, build_insurance_terrain_action_gate_table
from .pressure_action_task2_7b_insurance_closed_validation_v2 import (
    build_v2_risk_states,
    lower_observation_from_v2_risk_state,
    upper_pressure_from_lower_observation_v2,
)

TASK2_7C_LIGHT_VERSION = "strength_trend_light_validation_rc1"
STRENGTH_MULTIPLIERS = (0.25, 0.50, 1.00, 1.50, 2.00)
SEEDS = (11, 23, 37)
HORIZON = 40

REQUIRED_TASK2_7C_COLUMNS = [
    "task2_7c_version", "validation_only", "runtime_policy_input", "action_frame_created",
    "actionmodule_called", "world_runtime_called", "canonical_write_performed", "pressure_source",
    "v2_state_id", "seed", "horizon", "strength_multiplier", "action_channel", "action_name_ja",
    "pressure_component", "component_direction", "base_strength_hint", "effective_strength",
    "start_risk", "start_gain", "baseline_risk_end", "action_risk_end", "risk_end_delta_vs_no_op",
    "baseline_risk_slope", "action_risk_slope", "risk_slope_delta_vs_no_op", "risk_trend_class",
    "baseline_risk_auc", "action_risk_auc", "risk_auc_reduction", "baseline_gain_auc", "action_gain_auc",
    "gain_auc_delta_vs_no_op", "side_effect_auc", "long_term_net_benefit", "benefit_per_side_effect",
]


@dataclass(frozen=True)
class StrengthTrendConfig:
    horizon: int = HORIZON
    side_effect_weight: float = 1.0


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


def _noise(seed: int, step: int) -> float:
    return ((((seed * 37 + step * 101) % 1000) / 1000.0) - 0.5) * 0.002


def _slope(risk: float, gain: float) -> float:
    if risk >= 0.70:
        return 0.012 + 0.010 * (risk - 0.70)
    if risk >= 0.34:
        return 0.005 + 0.006 * (risk - 0.34)
    return -0.003 * max(0.0, gain - 0.45)


def _params(action: str) -> tuple[float, float, float, float, float]:
    table = {
        "volatility_damping": (0.82, 0.042, 0.000, 0.004, 0.070),
        "buffer_increase": (0.58, 0.036, 0.002, 0.010, 0.105),
        "uncertainty_probe": (0.38, 0.018, 0.018, 0.002, 0.055),
        "exploration_injection": (0.05, 0.000, 0.032, 0.000, 0.075),
        "relation_unlock": (0.14, 0.006, 0.012, 0.006, 0.095),
        "coupling_relief": (0.20, 0.010, 0.010, 0.006, 0.090),
    }
    return table.get(action, (0.0, 0.0, 0.0, 0.0, 0.0))


def _lin_slope(values: list[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    xm = (n - 1) / 2.0
    ym = sum(values) / n
    denom = sum((i - xm) ** 2 for i in range(n)) or 1.0
    return float(sum((i - xm) * (v - ym) for i, v in enumerate(values)) / denom)


def _simulate(row: pd.Series, multiplier: float, seed: int, cfg: StrengthTrendConfig) -> dict:
    start_risk = _clip01(_num(row, "terrain_risk_score"))
    start_gain = _clip01(_num(row, "terrain_gain_score"))
    base_strength = _num(row, "recommended_action_strength_hint")
    strength = max(0.0, min(0.40, base_strength * float(multiplier)))
    action = str(row["action_channel"])
    damp, risk_pull, gain_boost, gain_drag, side_rate = _params(action)
    br = ar = start_risk
    bg = ag = start_gain
    brs = [br]
    ars = [ar]
    bgs = [bg]
    ags = [ag]
    side = 0.0
    for t in range(1, cfg.horizon + 1):
        br = _clip01(br + _slope(br, bg) + _noise(seed, t))
        bg = _clip01(bg + 0.018 * (1.0 - br) - 0.006 * br)
        nat = _slope(ar, ag)
        open_risk = 0.012 * strength if action == "exploration_injection" and ar > 0.45 else 0.0
        ar = _clip01(ar + nat * (1.0 - min(0.92, damp * strength)) - risk_pull * strength + open_risk + _noise(seed + 17, t))
        side_step = side_rate * (strength ** 1.15)
        ag = _clip01(ag + 0.018 * (1.0 - ar) - 0.006 * ar + gain_boost * strength - gain_drag * strength - 0.10 * side_step)
        side += side_step
        brs.append(br); ars.append(ar); bgs.append(bg); ags.append(ag)
    bs = _lin_slope(brs[-12:])
    acs = _lin_slope(ars[-12:])
    risk_b = sum(brs) / len(brs)
    risk_a = sum(ars) / len(ars)
    gain_b = sum(bgs) / len(bgs)
    gain_a = sum(ags) / len(ags)
    risk_red = risk_b - risk_a
    gain_delta = gain_a - gain_b
    net = risk_red + gain_delta - cfg.side_effect_weight * side
    if bs > 0.001 and acs < -0.001:
        cls = "trend_reversal"
    elif bs > 0.001 and acs < bs * 0.55:
        cls = "trend_damping"
    elif risk_red > 0.01:
        cls = "temporary_relief"
    elif net < 0.0:
        cls = "side_effect_dominant"
    else:
        cls = "no_effect"
    return {
        "start_risk": start_risk, "start_gain": start_gain,
        "baseline_risk_end": brs[-1], "action_risk_end": ars[-1], "risk_end_delta_vs_no_op": brs[-1] - ars[-1],
        "baseline_risk_slope": bs, "action_risk_slope": acs, "risk_slope_delta_vs_no_op": bs - acs,
        "risk_trend_class": cls,
        "baseline_risk_auc": risk_b, "action_risk_auc": risk_a, "risk_auc_reduction": risk_red,
        "baseline_gain_auc": gain_b, "action_gain_auc": gain_a, "gain_auc_delta_vs_no_op": gain_delta,
        "side_effect_auc": side, "long_term_net_benefit": net,
        "benefit_per_side_effect": (risk_red + gain_delta) / side if side > 1e-12 else 0.0,
    }


def _gate_candidates() -> pd.DataFrame:
    terrain = lower_observation_from_v2_risk_state(build_v2_risk_states())
    pressure = upper_pressure_from_lower_observation_v2(terrain)
    gate = build_insurance_terrain_action_gate_table(
        pressure,
        terrain,
        config=InsuranceTerrainGateConfig(high_risk_threshold=0.68, medium_risk_threshold=0.42, safe_gain_risk_ceiling=0.32, safe_gain_threshold=0.50),
    )
    gate = gate[gate.apply(lambda r: str(r["terrain_location_id"]) in str(r["pressure_input_id"]), axis=1)].copy()
    gate = gate[gate["gate_decision"].astype(str).isin({"surface_insurance_candidate", "surface_safe_gain_probe_candidate"})].copy()
    return gate.reset_index(drop=True)


def build_strength_trend_light_validation_table(
    multipliers: Iterable[float] = STRENGTH_MULTIPLIERS,
    seeds: Iterable[int] = SEEDS,
    cfg: StrengthTrendConfig = StrengthTrendConfig(),
) -> pd.DataFrame:
    rows = []
    for _, cand in _gate_candidates().iterrows():
        for m in multipliers:
            for seed in seeds:
                sim = _simulate(cand, float(m), int(seed), cfg)
                rows.append({
                    "task2_7c_version": TASK2_7C_LIGHT_VERSION,
                    "validation_only": True,
                    "runtime_policy_input": False,
                    "action_frame_created": False,
                    "actionmodule_called": False,
                    "world_runtime_called": False,
                    "canonical_write_performed": False,
                    "pressure_source": "Task2_7b_validation_pressure_not_real_HDEPT",
                    "v2_state_id": str(cand["terrain_location_id"]),
                    "seed": int(seed),
                    "horizon": int(cfg.horizon),
                    "strength_multiplier": float(m),
                    "action_channel": str(cand["action_channel"]),
                    "action_name_ja": str(cand["action_name_ja"]),
                    "pressure_component": str(cand["pressure_component"]),
                    "component_direction": str(cand["component_direction"]),
                    "base_strength_hint": _num(cand, "recommended_action_strength_hint"),
                    "effective_strength": max(0.0, min(0.40, _num(cand, "recommended_action_strength_hint") * float(m))),
                    **sim,
                })
    out = pd.DataFrame(rows)
    if out.empty:
        return pd.DataFrame(columns=REQUIRED_TASK2_7C_COLUMNS)
    return out[REQUIRED_TASK2_7C_COLUMNS]


def summarize_strength_trend_light_validation(table: pd.DataFrame) -> dict:
    if table is None or table.empty:
        return {"rows": 0}
    by_multiplier = table.groupby("strength_multiplier").agg(
        rows=("strength_multiplier", "size"),
        mean_net=("long_term_net_benefit", "mean"),
        mean_risk_auc_reduction=("risk_auc_reduction", "mean"),
        mean_gain_delta=("gain_auc_delta_vs_no_op", "mean"),
        mean_side_effect_auc=("side_effect_auc", "mean"),
        reversal_rows=("risk_trend_class", lambda s: int((s == "trend_reversal").sum())),
        damping_rows=("risk_trend_class", lambda s: int((s == "trend_damping").sum())),
    ).reset_index()
    best = by_multiplier.sort_values("mean_net", ascending=False).head(1).to_dict(orient="records")[0]
    return {
        "rows": int(len(table)),
        "v2_states": int(table["v2_state_id"].nunique()),
        "actions": sorted(table["action_channel"].astype(str).unique().tolist()),
        "horizon": int(table["horizon"].max()),
        "seeds": sorted(table["seed"].astype(int).unique().tolist()),
        "strength_multipliers": sorted(table["strength_multiplier"].astype(float).unique().tolist()),
        "best_multiplier_by_mean_net": float(best["strength_multiplier"]),
        "best_mean_net": float(best["mean_net"]),
        "trend_reversal_rows": int((table["risk_trend_class"] == "trend_reversal").sum()),
        "trend_damping_rows": int((table["risk_trend_class"] == "trend_damping").sum()),
        "side_effect_dominant_rows": int((table["risk_trend_class"] == "side_effect_dominant").sum()),
        "by_multiplier": by_multiplier.to_dict(orient="records"),
    }


def validate_strength_trend_light_validation_table(table: pd.DataFrame) -> list[str]:
    errors = []
    if table is None or table.empty:
        return ["task2_7c_light_table_empty"]
    missing = sorted(set(REQUIRED_TASK2_7C_COLUMNS) - set(table.columns))
    if missing:
        return ["task2_7c_missing:" + ",".join(missing)]
    for field in ["runtime_policy_input", "action_frame_created", "actionmodule_called", "world_runtime_called", "canonical_write_performed"]:
        if bool(table[field].astype(bool).any()):
            errors.append(f"task2_7c_forbidden_true:{field}")
    if set(table["strength_multiplier"].astype(float)) != set(float(x) for x in STRENGTH_MULTIPLIERS):
        errors.append("task2_7c_strength_multipliers_missing")
    if int(table["horizon"].max()) != HORIZON:
        errors.append("task2_7c_horizon_not_40")
    if not bool((table["risk_auc_reduction"] > 0.0).any()):
        errors.append("task2_7c_no_risk_auc_reduction")
    if not bool((table["long_term_net_benefit"] > 0.0).any()):
        errors.append("task2_7c_no_positive_net")
    if not bool(table["risk_trend_class"].isin(["trend_reversal", "trend_damping", "temporary_relief"]).any()):
        errors.append("task2_7c_no_trend_improvement")
    return errors


def build_and_validate_strength_trend_light_validation_table() -> tuple[pd.DataFrame, list[str], dict]:
    table = build_strength_trend_light_validation_table()
    errors = validate_strength_trend_light_validation_table(table)
    summary = summarize_strength_trend_light_validation(table)
    return table, errors, summary
