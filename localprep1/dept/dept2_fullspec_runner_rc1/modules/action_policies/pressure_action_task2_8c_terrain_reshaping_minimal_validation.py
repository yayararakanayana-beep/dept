"""Task 2-8c: minimal validation of terrain reshaping direction.

Purpose:
    Test whether terrain reshaping changes long-term risk dynamics better than
    state actions alone, under fixed validation settings and without connecting
    real upper pressure.

Compared modes:
    - no_op
    - state_action_only
    - terrain_reshaping_only
    - combined_state_and_terrain

Boundary:
    - validation only
    - fixed validation parameters
    - no real H-DEPT pressure connection
    - no ActionFrame / ActionModule / world runtime / canonical write
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .pressure_action_task2_8b_terrain_reshaping_candidates import (
    build_demo_exploration_efficiency_hints,
    build_demo_lower_risk_information,
    build_demo_v8_local_evidence,
    build_terrain_reshaping_candidates,
)

TASK2_8C_VERSION = "terrain_reshaping_minimal_validation_rc1"
TASK2_8C_CONTRACT = "Task2_8c_fixed_settings_no_upper_pressure__terrain_reshaping_minimal_validation"
HORIZON = 60
SEEDS = (11, 23, 37)
MODES = ("no_op", "state_action_only", "terrain_reshaping_only", "combined_state_and_terrain")

REQUIRED_TASK2_8C_COLUMNS = [
    "task2_8c_version", "task2_8c_contract", "validation_only", "runtime_policy_input",
    "action_frame_created", "actionmodule_called", "world_runtime_called", "canonical_write_performed",
    "upper_pressure_connected", "fixed_validation_settings", "terrain_location_id", "seed", "horizon",
    "mode", "active_terrain_actions", "start_risk", "risk_peak", "risk_end", "risk_auc",
    "risk_slope_tail", "risk_acceleration_mean", "gain_auc", "gain_end", "side_effect_auc",
    "recovery_time", "post_action_persistence", "long_term_net_benefit",
    "risk_peak_delta_vs_no_op", "risk_auc_delta_vs_no_op", "gain_auc_delta_vs_no_op",
    "side_effect_delta_vs_no_op", "trend_improvement_class",
]


@dataclass(frozen=True)
class TerrainValidationConfig:
    horizon: int = HORIZON
    active_steps: int = 24
    state_action_strength: float = 0.16
    terrain_strength: float = 0.34
    side_effect_weight: float = 0.70


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
    return ((((seed * 53 + step * 97) % 1000) / 1000.0) - 0.5) * 0.0016


def _lin_slope(values: list[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    xm = (n - 1) / 2.0
    ym = sum(values) / n
    denom = sum((i - xm) ** 2 for i in range(n)) or 1.0
    return float(sum((i - xm) * (v - ym) for i, v in enumerate(values)) / denom)


def _mean_acceleration(values: list[float]) -> float:
    if len(values) < 3:
        return 0.0
    acc = [values[i] - 2.0 * values[i - 1] + values[i - 2] for i in range(2, len(values))]
    return float(sum(acc) / len(acc))


def _ready_candidates() -> pd.DataFrame:
    table = build_terrain_reshaping_candidates(
        build_demo_lower_risk_information(),
        build_demo_v8_local_evidence(),
        upper_pressure_modulation=None,
        exploration_efficiency_hints=build_demo_exploration_efficiency_hints(),
    )
    ready = table[table["candidate_status"].astype(str) == "candidate_ready_for_sandbox"].copy()
    if ready.empty:
        ready = table.sort_values("candidate_score", ascending=False).groupby("terrain_location_id").head(1).copy()
    return ready.reset_index(drop=True)


def _terrain_effects(candidates: pd.DataFrame, loc: str, strength: float) -> dict[str, float]:
    c = candidates[candidates["terrain_location_id"].astype(str) == loc]
    if c.empty:
        return {"sensitivity": 0.0, "amplification": 0.0, "recovery": 0.0, "persistence": 0.0, "side": 0.0}
    sens = amp = rec = pers = side = 0.0
    for _, row in c.iterrows():
        score = _num(row, "candidate_score")
        action = str(row["terrain_reshaping_action"])
        if action == "input_sensitivity_reduction":
            sens += 0.55 * score * strength
        elif action == "amplification_loop_damping":
            amp += 0.58 * score * strength
        elif action == "recovery_basin_formation":
            rec += 0.62 * score * strength
        pers += _num(row, "expected_persistence_effect") * strength
        side += _num(row, "side_effect_estimate") * strength * 0.08
    return {
        "sensitivity": _clip01(sens),
        "amplification": _clip01(amp),
        "recovery": _clip01(rec),
        "persistence": _clip01(pers),
        "side": _clip01(side),
    }


def _simulate_state(row: pd.Series, candidates: pd.DataFrame, mode: str, seed: int, cfg: TerrainValidationConfig) -> dict:
    loc = str(row["terrain_location_id"])
    start = _clip01(_num(row, "risk_level"))
    gain = _clip01(0.48 + 0.22 * (1.0 - start) + 0.16 * max(0.0, _num(row, "peak_risk_estimate") - start))
    risk = start
    input_sens = _clip01(_num(row, "input_sensitivity_score"))
    amp = _clip01(_num(row, "amplification_score"))
    recovery_margin = _clip01(_num(row, "recovery_margin"))
    peak = _clip01(_num(row, "peak_risk_estimate"))
    te = _terrain_effects(candidates, loc, cfg.terrain_strength) if "terrain" in mode else {"sensitivity": 0.0, "amplification": 0.0, "recovery": 0.0, "persistence": 0.0, "side": 0.0}
    risks = [risk]
    gains = [gain]
    side_auc = 0.0
    active_terrain = candidates[candidates["terrain_location_id"].astype(str) == loc]["terrain_reshaping_action"].astype(str).unique().tolist() if "terrain" in mode else []

    for t in range(1, cfg.horizon + 1):
        active = t <= cfg.active_steps
        terrain_decay = 1.0 if active else 0.40 + 0.60 * te["persistence"]
        sens_eff = input_sens * (1.0 - te["sensitivity"] * terrain_decay)
        amp_eff = amp * (1.0 - te["amplification"] * terrain_decay)
        recovery_eff = recovery_margin + te["recovery"] * terrain_decay
        natural = 0.006 + 0.012 * sens_eff + 0.014 * amp_eff + 0.006 * max(0.0, peak - risk)
        recovery_pull = 0.010 * recovery_eff * max(0.0, risk - 0.22)
        state_relief = cfg.state_action_strength * 0.035 if active and mode in {"state_action_only", "combined_state_and_terrain"} else 0.0
        state_side = cfg.state_action_strength * 0.018 if active and mode in {"state_action_only", "combined_state_and_terrain"} else 0.0
        terrain_side = te["side"] if active and "terrain" in mode else te["side"] * 0.22 if "terrain" in mode else 0.0
        risk = _clip01(risk + natural - recovery_pull - state_relief + _noise(seed, t))
        gain = _clip01(gain + 0.017 * (1.0 - risk) - 0.006 * risk - 0.08 * (state_side + terrain_side))
        side_auc += state_side + terrain_side
        risks.append(risk)
        gains.append(gain)

    tail = risks[-12:]
    post = risks[cfg.active_steps:]
    persistence = max(0.0, sum(risks[: cfg.active_steps + 1]) / (cfg.active_steps + 1) - sum(post) / len(post)) if post else 0.0
    recovery_threshold = start * 0.88
    recovery_hits = [i for i, v in enumerate(risks) if i > cfg.active_steps and v <= recovery_threshold]
    return {
        "active_terrain_actions": ";".join(active_terrain) if active_terrain else "none",
        "start_risk": start,
        "risk_peak": float(max(risks)),
        "risk_end": float(risks[-1]),
        "risk_auc": float(sum(risks) / len(risks)),
        "risk_slope_tail": _lin_slope(tail),
        "risk_acceleration_mean": _mean_acceleration(risks),
        "gain_auc": float(sum(gains) / len(gains)),
        "gain_end": float(gains[-1]),
        "side_effect_auc": float(side_auc),
        "recovery_time": int(recovery_hits[0] - cfg.active_steps) if recovery_hits else -1,
        "post_action_persistence": float(persistence),
    }


def build_terrain_reshaping_minimal_validation_table(cfg: TerrainValidationConfig = TerrainValidationConfig()) -> pd.DataFrame:
    lower = build_demo_lower_risk_information()
    candidates = _ready_candidates()
    rows = []
    for _, state in lower.iterrows():
        loc = str(state["terrain_location_id"])
        for seed in SEEDS:
            baseline = _simulate_state(state, candidates, "no_op", seed, cfg)
            for mode in MODES:
                res = baseline if mode == "no_op" else _simulate_state(state, candidates, mode, seed, cfg)
                peak_delta = baseline["risk_peak"] - res["risk_peak"]
                auc_delta = baseline["risk_auc"] - res["risk_auc"]
                gain_delta = res["gain_auc"] - baseline["gain_auc"]
                side_delta = res["side_effect_auc"] - baseline["side_effect_auc"]
                net = auc_delta + gain_delta + 0.25 * peak_delta - cfg.side_effect_weight * side_delta
                if res["risk_slope_tail"] < baseline["risk_slope_tail"] * 0.55:
                    cls = "trend_damping"
                elif peak_delta > 0.02 and auc_delta > 0.01:
                    cls = "peak_lowering"
                elif auc_delta > 0.005:
                    cls = "risk_auc_relief"
                elif net < 0.0:
                    cls = "side_effect_dominant"
                else:
                    cls = "no_effect"
                rows.append({
                    "task2_8c_version": TASK2_8C_VERSION,
                    "task2_8c_contract": TASK2_8C_CONTRACT,
                    "validation_only": True,
                    "runtime_policy_input": False,
                    "action_frame_created": False,
                    "actionmodule_called": False,
                    "world_runtime_called": False,
                    "canonical_write_performed": False,
                    "upper_pressure_connected": False,
                    "fixed_validation_settings": True,
                    "terrain_location_id": loc,
                    "seed": int(seed),
                    "horizon": int(cfg.horizon),
                    "mode": mode,
                    **res,
                    "long_term_net_benefit": float(net),
                    "risk_peak_delta_vs_no_op": float(peak_delta),
                    "risk_auc_delta_vs_no_op": float(auc_delta),
                    "gain_auc_delta_vs_no_op": float(gain_delta),
                    "side_effect_delta_vs_no_op": float(side_delta),
                    "trend_improvement_class": cls,
                })
    out = pd.DataFrame(rows)
    return out[REQUIRED_TASK2_8C_COLUMNS]


def summarize_terrain_reshaping_minimal_validation(table: pd.DataFrame) -> dict:
    if table is None or table.empty:
        return {"rows": 0}
    by_mode = table.groupby("mode").agg(
        rows=("mode", "size"),
        mean_net=("long_term_net_benefit", "mean"),
        mean_peak_delta=("risk_peak_delta_vs_no_op", "mean"),
        mean_auc_delta=("risk_auc_delta_vs_no_op", "mean"),
        mean_gain_delta=("gain_auc_delta_vs_no_op", "mean"),
        mean_side_delta=("side_effect_delta_vs_no_op", "mean"),
        mean_persistence=("post_action_persistence", "mean"),
        damping_rows=("trend_improvement_class", lambda s: int((s == "trend_damping").sum())),
        peak_lowering_rows=("trend_improvement_class", lambda s: int((s == "peak_lowering").sum())),
    ).reset_index()
    best = by_mode.sort_values("mean_net", ascending=False).head(1).to_dict(orient="records")[0]
    return {
        "rows": int(len(table)),
        "terrain_locations": int(table["terrain_location_id"].nunique()),
        "modes": sorted(table["mode"].astype(str).unique().tolist()),
        "horizon": int(table["horizon"].max()),
        "upper_pressure_connected": bool(table["upper_pressure_connected"].astype(bool).any()),
        "best_mode_by_mean_net": str(best["mode"]),
        "best_mean_net": float(best["mean_net"]),
        "by_mode": by_mode.to_dict(orient="records"),
    }


def validate_terrain_reshaping_minimal_validation(table: pd.DataFrame) -> list[str]:
    errors = []
    if table is None or table.empty:
        return ["task2_8c_table_empty"]
    missing = sorted(set(REQUIRED_TASK2_8C_COLUMNS) - set(table.columns))
    if missing:
        return ["task2_8c_required_columns_missing:" + ",".join(missing)]
    for field in ["runtime_policy_input", "action_frame_created", "actionmodule_called", "world_runtime_called", "canonical_write_performed", "upper_pressure_connected"]:
        if bool(table[field].astype(bool).any()):
            errors.append(f"task2_8c_forbidden_true:{field}")
    if not bool(table["validation_only"].astype(bool).all()):
        errors.append("task2_8c_validation_only_not_all_true")
    if not bool(table["fixed_validation_settings"].astype(bool).all()):
        errors.append("task2_8c_fixed_validation_settings_not_all_true")
    if set(table["mode"].astype(str)) != set(MODES):
        errors.append("task2_8c_modes_missing")
    if int(table["horizon"].max()) != HORIZON:
        errors.append("task2_8c_horizon_not_60")
    for col in ["risk_peak", "risk_auc", "gain_auc", "side_effect_auc"]:
        vals = pd.to_numeric(table[col], errors="coerce")
        if bool(vals.isna().any() or (vals < 0.0).any()):
            errors.append(f"task2_8c_invalid_nonnegative:{col}")
    if not bool((table["risk_peak_delta_vs_no_op"] > 0.0).any()):
        errors.append("task2_8c_no_peak_reduction")
    if not bool((table["risk_auc_delta_vs_no_op"] > 0.0).any()):
        errors.append("task2_8c_no_auc_reduction")
    return errors


def build_and_validate_terrain_reshaping_minimal_validation_table() -> tuple[pd.DataFrame, list[str], dict]:
    table = build_terrain_reshaping_minimal_validation_table()
    errors = validate_terrain_reshaping_minimal_validation(table)
    summary = summarize_terrain_reshaping_minimal_validation(table)
    return table, errors, summary
