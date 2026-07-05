"""Task 2-8d: targeted terrain reshaping validation RC1.

Purpose:
    Find whether intentionally narrowed terrain-reshaping conditions can turn
    long-term net benefit positive, even with side effects.

Boundary:
    - validation only
    - deliberately fixed / partly arbitrary targeting thresholds
    - no real H-DEPT upper pressure connection
    - no exploration-axis side-effect escape
    - no ActionFrame / ActionModule / world runtime / canonical write
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .pressure_action_task2_8b_terrain_reshaping_candidates import (
    TERRAIN_RESHAPING_ACTIONS,
    build_demo_lower_risk_information,
    build_demo_v8_local_evidence,
    build_terrain_reshaping_candidates,
)

TASK2_8D_VERSION = "terrain_reshaping_targeted_validation_rc1"
TASK2_8D_CONTRACT = "Task2_8d_targeted_strength_duration_validation__fixed_settings__no_upper_pressure__no_exploration_escape"
HORIZON = 72
SEEDS = (11, 23, 37)
STRENGTH_BANDS = {"low": 0.18, "mid": 0.30, "high": 0.42}
DURATION_BANDS = {"short": 12, "mid": 24, "long": 36}
MODES = (
    "no_op",
    "state_action_only",
    "terrain_untargeted",
    "terrain_targeted",
    "combined_targeted",
)

REQUIRED_TASK2_8D_COLUMNS = [
    "task2_8d_version",
    "task2_8d_contract",
    "validation_only",
    "runtime_policy_input",
    "action_frame_created",
    "actionmodule_called",
    "world_runtime_called",
    "canonical_write_performed",
    "upper_pressure_connected",
    "exploration_escape_connected",
    "fixed_validation_settings",
    "targeting_thresholds_arbitrary",
    "terrain_location_id",
    "seed",
    "horizon",
    "mode",
    "strength_band",
    "strength_value",
    "duration_band",
    "duration_steps",
    "targeting_passed",
    "targeted_actions",
    "matched_local_patterns",
    "start_risk",
    "risk_peak",
    "risk_end",
    "risk_auc",
    "risk_slope_tail",
    "risk_acceleration_mean",
    "gain_auc",
    "gain_end",
    "side_effect_auc",
    "recovery_time",
    "post_action_persistence",
    "long_term_net_benefit",
    "risk_peak_delta_vs_no_op",
    "risk_auc_delta_vs_no_op",
    "gain_auc_delta_vs_no_op",
    "side_effect_delta_vs_no_op",
    "positive_net_condition",
    "trend_improvement_class",
]


@dataclass(frozen=True)
class TargetedValidationConfig:
    horizon: int = HORIZON
    state_action_strength: float = 0.14
    side_effect_weight: float = 0.58
    high_risk_threshold: float = 0.65
    trend_threshold: float = 0.45
    peak_threshold: float = 0.70
    acceleration_exception_threshold: float = 0.60


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
    return ((((seed * 131 + step * 71) % 1000) / 1000.0) - 0.5) * 0.0013


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


def _v8_patterns_for_location(v8: pd.DataFrame, loc: str) -> set[str]:
    if v8 is None or v8.empty:
        return set()
    m = v8[v8["terrain_location_id"].astype(str) == loc]
    return set(m["local_pattern_type"].astype(str).tolist())


def _target_pass(row: pd.Series, patterns: set[str], cfg: TargetedValidationConfig) -> bool:
    base_hits = sum([
        _num(row, "risk_level") >= cfg.high_risk_threshold,
        _num(row, "risk_slope") >= cfg.trend_threshold,
        _num(row, "peak_risk_estimate") >= cfg.peak_threshold,
    ])
    exception_patterns = bool(patterns & {"recursive_amplification", "input_overreaction", "boundary_instability"})
    exception = _num(row, "risk_acceleration") >= cfg.acceleration_exception_threshold and exception_patterns
    return bool(base_hits >= 2 or exception)


def _action_matches_target(row: pd.Series, action: str, patterns: set[str]) -> bool:
    if action == "input_sensitivity_reduction":
        return (
            _num(row, "input_sensitivity_score") >= 0.58
            and _num(row, "risk_slope") >= 0.40
            and bool(patterns & {"input_overreaction", "boundary_instability"})
        )
    if action == "amplification_loop_damping":
        return (
            _num(row, "amplification_score") >= 0.58
            and _num(row, "risk_acceleration") >= 0.42
            and bool(patterns & {"recursive_amplification", "oscillation", "recurrence"})
        )
    if action == "recovery_basin_formation":
        return (
            _num(row, "recovery_margin") <= 0.42
            and _num(row, "irreversibility_risk") >= 0.52
            and bool(patterns & {"recovery_failure", "regime_switch", "split_merge_return_failure"})
        )
    return False


def _candidate_table_without_upper_pressure() -> pd.DataFrame:
    return build_terrain_reshaping_candidates(
        build_demo_lower_risk_information(),
        build_demo_v8_local_evidence(),
        upper_pressure_modulation=None,
        exploration_efficiency_hints=None,
    )


def build_targeted_candidate_table(cfg: TargetedValidationConfig = TargetedValidationConfig()) -> pd.DataFrame:
    lower = build_demo_lower_risk_information()
    v8 = build_demo_v8_local_evidence()
    candidates = _candidate_table_without_upper_pressure()
    rows = []
    for _, r in lower.iterrows():
        loc = str(r["terrain_location_id"])
        patterns = _v8_patterns_for_location(v8, loc)
        base_pass = _target_pass(r, patterns, cfg)
        cm = candidates[candidates["terrain_location_id"].astype(str) == loc]
        for _, c in cm.iterrows():
            action = str(c["terrain_reshaping_action"])
            match = _action_matches_target(r, action, patterns)
            row = dict(c)
            row.update({
                "targeting_passed": bool(base_pass and match),
                "matched_local_patterns": ";".join(sorted(patterns)) if patterns else "none",
                "targeting_basis": (
                    f"base_pass={base_pass}; match={match}; "
                    f"risk={_num(r, 'risk_level'):.3f}; slope={_num(r, 'risk_slope'):.3f}; "
                    f"peak={_num(r, 'peak_risk_estimate'):.3f}; accel={_num(r, 'risk_acceleration'):.3f}; "
                    f"patterns={';'.join(sorted(patterns)) if patterns else 'none'}"
                ),
            })
            rows.append(row)
    return pd.DataFrame(rows)


def _selected_actions(targeted_candidates: pd.DataFrame, loc: str, mode: str) -> pd.DataFrame:
    if mode in {"no_op", "state_action_only"}:
        return targeted_candidates.iloc[0:0].copy()
    c = targeted_candidates[targeted_candidates["terrain_location_id"].astype(str) == loc].copy()
    if mode in {"terrain_targeted", "combined_targeted"}:
        c = c[c["targeting_passed"].astype(bool)].copy()
    if mode == "terrain_untargeted":
        c = c.sort_values("candidate_score", ascending=False).head(3).copy()
    return c


def _terrain_effects(actions: pd.DataFrame, strength: float, targeted: bool) -> dict[str, float]:
    if actions is None or actions.empty:
        return {"sensitivity": 0.0, "amplification": 0.0, "recovery": 0.0, "persistence": 0.0, "side": 0.0}
    sens = amp = rec = pers = side = 0.0
    for _, row in actions.iterrows():
        score = _num(row, "candidate_score")
        # Targeted actions are assumed to hit the correct local force more cleanly.
        precision = 1.18 if targeted else 0.72
        side_multiplier = 0.62 if targeted else 1.15
        action = str(row["terrain_reshaping_action"])
        if action == "input_sensitivity_reduction":
            sens += 0.78 * score * strength * precision
        elif action == "amplification_loop_damping":
            amp += 0.82 * score * strength * precision
        elif action == "recovery_basin_formation":
            rec += 0.86 * score * strength * precision
        pers += (0.18 + 0.65 * score) * strength * (1.15 if targeted else 0.56)
        side += (0.030 + 0.070 * _num(row, "side_effect_estimate")) * strength * side_multiplier
    return {
        "sensitivity": _clip01(sens),
        "amplification": _clip01(amp),
        "recovery": _clip01(rec),
        "persistence": _clip01(pers),
        "side": _clip01(side),
    }


def _simulate(row: pd.Series, targeted_candidates: pd.DataFrame, mode: str, strength: float, duration: int, seed: int, cfg: TargetedValidationConfig) -> dict:
    loc = str(row["terrain_location_id"])
    selected = _selected_actions(targeted_candidates, loc, mode)
    targeted = mode in {"terrain_targeted", "combined_targeted"}
    te = _terrain_effects(selected, strength, targeted)

    risk = _clip01(_num(row, "risk_level"))
    gain = _clip01(0.50 + 0.18 * (1.0 - risk) + 0.10 * max(0.0, _num(row, "peak_risk_estimate") - risk))
    input_sens_base = _clip01(_num(row, "input_sensitivity_score"))
    amp_base = _clip01(_num(row, "amplification_score"))
    recovery_base = _clip01(_num(row, "recovery_margin"))
    peak_base = _clip01(_num(row, "peak_risk_estimate"))
    risks = [risk]
    gains = [gain]
    side_auc = 0.0
    active_actions = ";".join(selected["terrain_reshaping_action"].astype(str).unique().tolist()) if not selected.empty else "none"

    for t in range(1, cfg.horizon + 1):
        active = t <= duration
        post_decay = (0.30 + 0.70 * te["persistence"]) if not active else 1.0
        sens_eff = input_sens_base * (1.0 - te["sensitivity"] * post_decay)
        amp_eff = amp_base * (1.0 - te["amplification"] * post_decay)
        recovery_eff = recovery_base + te["recovery"] * post_decay
        peak_eff = peak_base * (1.0 - 0.35 * te["sensitivity"] * post_decay - 0.30 * te["amplification"] * post_decay)

        bubble_push = 0.005 + 0.010 * sens_eff + 0.014 * amp_eff + 0.007 * max(0.0, peak_eff - risk)
        self_push = 0.010 * amp_eff * max(0.0, risk - 0.52)
        recovery_pull = 0.014 * recovery_eff * max(0.0, risk - 0.24)
        state_relief = cfg.state_action_strength * 0.038 if active and mode in {"state_action_only", "combined_targeted"} else 0.0
        risk = _clip01(risk + bubble_push + self_push - recovery_pull - state_relief + _noise(seed, t))

        state_side = cfg.state_action_strength * 0.016 if active and mode in {"state_action_only", "combined_targeted"} else 0.0
        terrain_side = te["side"] if active and selected is not None and not selected.empty else te["side"] * 0.18 if selected is not None and not selected.empty else 0.0
        side_auc += state_side + terrain_side
        # If targeted terrain lowers risk dynamics, it preserves future gain, but direct intervention has a cost.
        gain = _clip01(gain + 0.015 * (1.0 - risk) - 0.005 * risk - 0.030 * (state_side + terrain_side))
        gains.append(gain)
        risks.append(risk)

    tail = risks[-12:]
    post = risks[duration:]
    early = risks[: duration + 1]
    persistence = max(0.0, sum(early) / len(early) - sum(post) / len(post)) if post else 0.0
    recovery_threshold = risks[0] * 0.88
    recovery_hits = [i for i, v in enumerate(risks) if i > duration and v <= recovery_threshold]
    return {
        "targeted_actions": active_actions,
        "start_risk": float(risks[0]),
        "risk_peak": float(max(risks)),
        "risk_end": float(risks[-1]),
        "risk_auc": float(sum(risks) / len(risks)),
        "risk_slope_tail": _lin_slope(tail),
        "risk_acceleration_mean": _mean_acceleration(risks),
        "gain_auc": float(sum(gains) / len(gains)),
        "gain_end": float(gains[-1]),
        "side_effect_auc": float(side_auc),
        "recovery_time": int(recovery_hits[0] - duration) if recovery_hits else -1,
        "post_action_persistence": float(persistence),
    }


def build_terrain_reshaping_targeted_validation_table(cfg: TargetedValidationConfig = TargetedValidationConfig()) -> pd.DataFrame:
    lower = build_demo_lower_risk_information()
    targeted_candidates = build_targeted_candidate_table(cfg)
    rows = []
    for _, state in lower.iterrows():
        loc = str(state["terrain_location_id"])
        loc_candidates = targeted_candidates[targeted_candidates["terrain_location_id"].astype(str) == loc]
        targeting_passed = bool(loc_candidates["targeting_passed"].astype(bool).any()) if not loc_candidates.empty else False
        matched_patterns = ";".join(sorted(set(loc_candidates["matched_local_patterns"].astype(str)))) if not loc_candidates.empty else "none"
        for seed in SEEDS:
            for strength_band, strength_value in STRENGTH_BANDS.items():
                for duration_band, duration_steps in DURATION_BANDS.items():
                    baseline = _simulate(state, targeted_candidates, "no_op", strength_value, duration_steps, seed, cfg)
                    for mode in MODES:
                        res = baseline if mode == "no_op" else _simulate(state, targeted_candidates, mode, strength_value, duration_steps, seed, cfg)
                        peak_delta = baseline["risk_peak"] - res["risk_peak"]
                        auc_delta = baseline["risk_auc"] - res["risk_auc"]
                        gain_delta = res["gain_auc"] - baseline["gain_auc"]
                        side_delta = res["side_effect_auc"] - baseline["side_effect_auc"]
                        net = auc_delta + gain_delta + 0.30 * peak_delta + 0.20 * res["post_action_persistence"] - cfg.side_effect_weight * side_delta
                        if res["risk_slope_tail"] < baseline["risk_slope_tail"] * 0.50:
                            cls = "trend_damping"
                        elif peak_delta > 0.02 and auc_delta > 0.015:
                            cls = "peak_and_auc_lowering"
                        elif net > 0.0 and auc_delta > 0.0:
                            cls = "positive_net_with_risk_relief"
                        elif side_delta > 0.0 and net < 0.0:
                            cls = "side_effect_dominant"
                        else:
                            cls = "no_effect"
                        rows.append({
                            "task2_8d_version": TASK2_8D_VERSION,
                            "task2_8d_contract": TASK2_8D_CONTRACT,
                            "validation_only": True,
                            "runtime_policy_input": False,
                            "action_frame_created": False,
                            "actionmodule_called": False,
                            "world_runtime_called": False,
                            "canonical_write_performed": False,
                            "upper_pressure_connected": False,
                            "exploration_escape_connected": False,
                            "fixed_validation_settings": True,
                            "targeting_thresholds_arbitrary": True,
                            "terrain_location_id": loc,
                            "seed": int(seed),
                            "horizon": int(cfg.horizon),
                            "mode": mode,
                            "strength_band": strength_band,
                            "strength_value": float(strength_value),
                            "duration_band": duration_band,
                            "duration_steps": int(duration_steps),
                            "targeting_passed": bool(targeting_passed),
                            "matched_local_patterns": matched_patterns,
                            **res,
                            "long_term_net_benefit": float(net),
                            "risk_peak_delta_vs_no_op": float(peak_delta),
                            "risk_auc_delta_vs_no_op": float(auc_delta),
                            "gain_auc_delta_vs_no_op": float(gain_delta),
                            "side_effect_delta_vs_no_op": float(side_delta),
                            "positive_net_condition": bool(net > 0.0 and auc_delta > 0.0 and peak_delta >= 0.0),
                            "trend_improvement_class": cls,
                        })
    out = pd.DataFrame(rows)
    return out[REQUIRED_TASK2_8D_COLUMNS]


def summarize_terrain_reshaping_targeted_validation(table: pd.DataFrame) -> dict:
    if table is None or table.empty:
        return {"rows": 0}
    by_mode = table.groupby("mode").agg(
        rows=("mode", "size"),
        mean_net=("long_term_net_benefit", "mean"),
        positive_rows=("positive_net_condition", lambda s: int(pd.Series(s).astype(bool).sum())),
        mean_peak_delta=("risk_peak_delta_vs_no_op", "mean"),
        mean_auc_delta=("risk_auc_delta_vs_no_op", "mean"),
        mean_gain_delta=("gain_auc_delta_vs_no_op", "mean"),
        mean_side_delta=("side_effect_delta_vs_no_op", "mean"),
        mean_persistence=("post_action_persistence", "mean"),
    ).reset_index()
    positive = table[table["positive_net_condition"].astype(bool)].copy()
    best = table.sort_values("long_term_net_benefit", ascending=False).head(1).iloc[0].to_dict()
    return {
        "rows": int(len(table)),
        "terrain_locations": int(table["terrain_location_id"].nunique()),
        "modes": sorted(table["mode"].astype(str).unique().tolist()),
        "horizon": int(table["horizon"].max()),
        "upper_pressure_connected": bool(table["upper_pressure_connected"].astype(bool).any()),
        "exploration_escape_connected": bool(table["exploration_escape_connected"].astype(bool).any()),
        "positive_net_rows": int(len(positive)),
        "best_mode": str(best["mode"]),
        "best_strength_band": str(best["strength_band"]),
        "best_duration_band": str(best["duration_band"]),
        "best_net": float(best["long_term_net_benefit"]),
        "by_mode": by_mode.to_dict(orient="records"),
    }


def validate_terrain_reshaping_targeted_validation(table: pd.DataFrame) -> list[str]:
    errors = []
    if table is None or table.empty:
        return ["task2_8d_table_empty"]
    missing = sorted(set(REQUIRED_TASK2_8D_COLUMNS) - set(table.columns))
    if missing:
        return ["task2_8d_required_columns_missing:" + ",".join(missing)]
    for field in [
        "runtime_policy_input",
        "action_frame_created",
        "actionmodule_called",
        "world_runtime_called",
        "canonical_write_performed",
        "upper_pressure_connected",
        "exploration_escape_connected",
    ]:
        if bool(table[field].astype(bool).any()):
            errors.append(f"task2_8d_forbidden_true:{field}")
    for field in ["validation_only", "fixed_validation_settings", "targeting_thresholds_arbitrary"]:
        if not bool(table[field].astype(bool).all()):
            errors.append(f"task2_8d_required_true_not_all:{field}")
    if set(table["mode"].astype(str)) != set(MODES):
        errors.append("task2_8d_modes_missing")
    if set(table["strength_band"].astype(str)) != set(STRENGTH_BANDS):
        errors.append("task2_8d_strength_bands_missing")
    if set(table["duration_band"].astype(str)) != set(DURATION_BANDS):
        errors.append("task2_8d_duration_bands_missing")
    if int(table["horizon"].max()) != HORIZON:
        errors.append("task2_8d_horizon_not_72")
    if not bool(table["targeting_passed"].astype(bool).any()):
        errors.append("task2_8d_no_targeting_passed")
    if not bool(table["positive_net_condition"].astype(bool).any()):
        errors.append("task2_8d_no_positive_net_condition_found")
    targeted_positive = table[(table["mode"].astype(str).isin(["terrain_targeted", "combined_targeted"])) & table["positive_net_condition"].astype(bool)]
    if targeted_positive.empty:
        errors.append("task2_8d_no_targeted_positive_net_condition")
    for col in ["risk_peak", "risk_auc", "gain_auc", "side_effect_auc"]:
        vals = pd.to_numeric(table[col], errors="coerce")
        if bool(vals.isna().any() or (vals < 0.0).any()):
            errors.append(f"task2_8d_invalid_nonnegative:{col}")
    return errors


def build_and_validate_terrain_reshaping_targeted_validation_table() -> tuple[pd.DataFrame, list[str], dict]:
    table = build_terrain_reshaping_targeted_validation_table()
    errors = validate_terrain_reshaping_targeted_validation(table)
    summary = summarize_terrain_reshaping_targeted_validation(table)
    return table, errors, summary
