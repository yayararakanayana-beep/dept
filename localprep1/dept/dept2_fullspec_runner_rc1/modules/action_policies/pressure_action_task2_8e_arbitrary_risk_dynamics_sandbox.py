"""Task 2-8e: arbitrary risk dynamics sandbox RC1.

Purpose:
    Create explicit synthetic risk dynamics and test when terrain reshaping
    improves total benefit compared with no_op.

This intentionally uses artificial dynamics. The goal is not realism yet.
The goal is to isolate improvement conditions:
    - which terrain coefficient
    - which direction
    - which strength
    - which duration
    - which timing

Boundary:
    - validation only
    - no real H-DEPT upper pressure connection
    - no exploration-axis side-effect escape
    - no ActionFrame / ActionModule / world runtime / canonical write
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import pandas as pd

TASK2_8E_VERSION = "arbitrary_risk_dynamics_sandbox_rc1"
TASK2_8E_CONTRACT = "Task2_8e_arbitrary_risk_dynamics_sandbox__no_op_comparison__no_upper_pressure__no_exploration_escape"
HORIZON = 96
SEEDS = (11, 23, 37)

STRENGTH_BANDS = {"low": 0.18, "mid": 0.30, "high": 0.42, "excessive": 0.64}
DURATION_BANDS = {"short": 12, "mid": 24, "long": 36}
TIMING_BANDS = {"early": 6, "on_time": 18, "late": 42}

ACTIONS = {
    "input_sensitivity_reduction": "入力感度低下作用",
    "amplification_loop_damping": "自己増幅遮断作用",
    "recovery_basin_formation": "回復谷形成作用",
}

STRATEGIES = (
    "no_op",
    "matched_action",
    "mismatched_action",
    "excessive_overlong_matched",
    "late_matched_action",
)

REQUIRED_TASK2_8E_COLUMNS = [
    "task2_8e_version",
    "task2_8e_contract",
    "validation_only",
    "runtime_policy_input",
    "action_frame_created",
    "actionmodule_called",
    "world_runtime_called",
    "canonical_write_performed",
    "upper_pressure_connected",
    "exploration_escape_connected",
    "synthetic_dynamics_only",
    "terrain_coefficients_explicit",
    "risk_dynamics_type",
    "risk_dynamics_ja",
    "seed",
    "horizon",
    "strategy",
    "terrain_action",
    "terrain_action_ja",
    "action_matches_dynamics",
    "strength_band",
    "strength_value",
    "duration_band",
    "duration_steps",
    "timing_band",
    "start_step",
    "end_step",
    "risk_peak",
    "risk_end",
    "risk_auc",
    "risk_slope_after_action",
    "risk_acceleration_mean",
    "gain_auc",
    "gain_end",
    "side_effect_auc",
    "terrain_coeff_persistence",
    "post_action_risk_auc",
    "long_term_net_benefit",
    "risk_peak_delta_vs_no_op",
    "risk_auc_delta_vs_no_op",
    "post_action_auc_delta_vs_no_op",
    "gain_auc_delta_vs_no_op",
    "side_effect_delta_vs_no_op",
    "terrain_persistence_delta_vs_no_op",
    "positive_net_vs_no_op",
    "improvement_class",
]


@dataclass(frozen=True)
class RiskDynamicsSpec:
    dynamics_type: str
    dynamics_ja: str
    recommended_action: str
    wrong_action: str
    input_sensitivity: float
    amplification: float
    recovery_margin: float
    baseline_pressure: float
    shock_step: int
    shock_size: float
    gain_base: float


DYNAMICS_SPECS = (
    RiskDynamicsSpec(
        dynamics_type="input_sensitivity_bubble",
        dynamics_ja="入力感度過大型",
        recommended_action="input_sensitivity_reduction",
        wrong_action="recovery_basin_formation",
        input_sensitivity=0.86,
        amplification=0.36,
        recovery_margin=0.26,
        baseline_pressure=0.56,
        shock_step=26,
        shock_size=0.080,
        gain_base=0.58,
    ),
    RiskDynamicsSpec(
        dynamics_type="amplification_loop_bubble",
        dynamics_ja="自己増幅型",
        recommended_action="amplification_loop_damping",
        wrong_action="input_sensitivity_reduction",
        input_sensitivity=0.48,
        amplification=0.88,
        recovery_margin=0.24,
        baseline_pressure=0.46,
        shock_step=30,
        shock_size=0.060,
        gain_base=0.57,
    ),
    RiskDynamicsSpec(
        dynamics_type="recovery_failure_trap",
        dynamics_ja="回復不能型",
        recommended_action="recovery_basin_formation",
        wrong_action="amplification_loop_damping",
        input_sensitivity=0.46,
        amplification=0.48,
        recovery_margin=0.08,
        baseline_pressure=0.42,
        shock_step=24,
        shock_size=0.090,
        gain_base=0.56,
    ),
    RiskDynamicsSpec(
        dynamics_type="composite_bubble",
        dynamics_ja="複合バブル型",
        recommended_action="amplification_loop_damping",
        wrong_action="recovery_basin_formation",
        input_sensitivity=0.76,
        amplification=0.82,
        recovery_margin=0.14,
        baseline_pressure=0.52,
        shock_step=28,
        shock_size=0.085,
        gain_base=0.59,
    ),
)


@dataclass(frozen=True)
class SandboxConfig:
    horizon: int = HORIZON
    side_effect_weight: float = 0.62
    terrain_persistence_weight: float = 0.24
    peak_weight: float = 0.34
    post_action_weight: float = 0.35


def _clip01(x: float) -> float:
    return float(max(0.0, min(1.0, float(x))))


def _noise(seed: int, step: int) -> float:
    return ((((seed * 173 + step * 67) % 1000) / 1000.0) - 0.5) * 0.0014


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


def _apply_terrain_action(
    action: str,
    strength: float,
    action_matches: bool,
    input_sensitivity: float,
    amplification: float,
    recovery_margin: float,
) -> tuple[float, float, float, float]:
    """Return updated coefficients and step side effect.

    Matched actions are assumed to hit the correct dynamics with less waste.
    Mismatched actions still change a coefficient, but the changed coefficient is
    not the dominant failure mode, so total benefit should usually be weaker.
    """
    precision = 1.00 if action_matches else 0.38
    side_multiplier = 0.55 if action_matches else 1.30
    change = 0.018 * strength * precision
    if action == "input_sensitivity_reduction":
        input_sensitivity = max(0.05, input_sensitivity - change)
    elif action == "amplification_loop_damping":
        amplification = max(0.05, amplification - change)
    elif action == "recovery_basin_formation":
        recovery_margin = min(0.92, recovery_margin + change)
    else:
        side_multiplier = 0.0
    side = (0.006 + 0.018 * strength * strength) * side_multiplier
    return input_sensitivity, amplification, recovery_margin, side


def _simulate(
    spec: RiskDynamicsSpec,
    strategy: str,
    terrain_action: str,
    strength: float,
    duration: int,
    start_step: int,
    seed: int,
    cfg: SandboxConfig,
) -> dict:
    risk = 0.30
    gain = spec.gain_base
    input_sensitivity = spec.input_sensitivity
    amplification = spec.amplification
    recovery_margin = spec.recovery_margin
    initial_coeffs = (input_sensitivity, amplification, recovery_margin)
    action_matches = terrain_action == spec.recommended_action and strategy != "no_op"
    risks = [risk]
    gains = [gain]
    side_auc = 0.0
    end_step = start_step + duration

    for step in range(1, cfg.horizon + 1):
        active = strategy != "no_op" and start_step <= step < end_step
        if active:
            input_sensitivity, amplification, recovery_margin, side = _apply_terrain_action(
                terrain_action,
                strength,
                action_matches,
                input_sensitivity,
                amplification,
                recovery_margin,
            )
        else:
            side = 0.0

        external_pressure = spec.baseline_pressure + 0.12 * max(0.0, (step - 18) / cfg.horizon)
        shock = spec.shock_size if step == spec.shock_step else 0.0
        input_push = 0.016 * input_sensitivity * external_pressure
        loop_push = 0.018 * amplification * max(0.0, risk - 0.40) ** 1.15
        recovery_pull = 0.020 * recovery_margin * max(0.0, risk - 0.22)
        collapse_drag = 0.030 if risk > 0.88 else 0.0
        risk = _clip01(risk + input_push + loop_push + shock - recovery_pull + _noise(seed, step))

        gain_flow = 0.012 * (1.0 - risk) - 0.006 * risk - 0.018 * collapse_drag - 0.020 * side
        gain = _clip01(gain + gain_flow)
        side_auc += side
        risks.append(risk)
        gains.append(gain)

    post_start = min(max(end_step, 1), cfg.horizon - 1)
    post_values = risks[post_start:]
    coeff_persistence = (
        abs(initial_coeffs[0] - input_sensitivity)
        + abs(initial_coeffs[1] - amplification)
        + abs(recovery_margin - initial_coeffs[2])
    ) / 3.0
    return {
        "action_matches_dynamics": bool(action_matches),
        "end_step": int(end_step),
        "risk_peak": float(max(risks)),
        "risk_end": float(risks[-1]),
        "risk_auc": float(sum(risks) / len(risks)),
        "risk_slope_after_action": _lin_slope(post_values[-18:] if len(post_values) >= 18 else post_values),
        "risk_acceleration_mean": _mean_acceleration(risks),
        "gain_auc": float(sum(gains) / len(gains)),
        "gain_end": float(gains[-1]),
        "side_effect_auc": float(side_auc),
        "terrain_coeff_persistence": float(coeff_persistence),
        "post_action_risk_auc": float(sum(post_values) / len(post_values)) if post_values else float(risks[-1]),
    }


def _condition_grid() -> list[dict]:
    rows = []
    rows.append({
        "strategy": "no_op",
        "strength_band": "none",
        "strength_value": 0.0,
        "duration_band": "none",
        "duration_steps": 0,
        "timing_band": "none",
        "start_step": 0,
    })
    for strength_band, strength_value in STRENGTH_BANDS.items():
        for duration_band, duration_steps in DURATION_BANDS.items():
            for timing_band, start_step in TIMING_BANDS.items():
                rows.append({
                    "strategy": "matched_action",
                    "strength_band": strength_band,
                    "strength_value": strength_value,
                    "duration_band": duration_band,
                    "duration_steps": duration_steps,
                    "timing_band": timing_band,
                    "start_step": start_step,
                })
                rows.append({
                    "strategy": "mismatched_action",
                    "strength_band": strength_band,
                    "strength_value": strength_value,
                    "duration_band": duration_band,
                    "duration_steps": duration_steps,
                    "timing_band": timing_band,
                    "start_step": start_step,
                })
    for timing_band, start_step in {"early": 6, "on_time": 18}.items():
        rows.append({
            "strategy": "excessive_overlong_matched",
            "strength_band": "excessive",
            "strength_value": STRENGTH_BANDS["excessive"],
            "duration_band": "long",
            "duration_steps": DURATION_BANDS["long"],
            "timing_band": timing_band,
            "start_step": start_step,
        })
    for strength_band, strength_value in STRENGTH_BANDS.items():
        for duration_band, duration_steps in DURATION_BANDS.items():
            rows.append({
                "strategy": "late_matched_action",
                "strength_band": strength_band,
                "strength_value": strength_value,
                "duration_band": duration_band,
                "duration_steps": duration_steps,
                "timing_band": "late",
                "start_step": TIMING_BANDS["late"],
            })
    return rows


def _terrain_action_for_strategy(spec: RiskDynamicsSpec, strategy: str) -> str:
    if strategy == "no_op":
        return "none"
    if strategy == "mismatched_action":
        return spec.wrong_action
    return spec.recommended_action


def _classify(row: dict) -> str:
    if row["strategy"] == "no_op":
        return "baseline_no_op"
    if row["positive_net_vs_no_op"] and row["action_matches_dynamics"]:
        return "matched_positive_condition"
    if row["risk_auc_delta_vs_no_op"] > 0.03 and row["long_term_net_benefit"] <= 0.0:
        return "risk_improves_but_side_effect_loses"
    if not row["action_matches_dynamics"] and row["long_term_net_benefit"] <= 0.0:
        return "mismatch_or_waste_loses"
    if row["timing_band"] == "late" and row["long_term_net_benefit"] <= 0.0:
        return "late_action_loses"
    if row["side_effect_delta_vs_no_op"] > 0.10 and row["long_term_net_benefit"] <= 0.0:
        return "overuse_side_effect_loses"
    return "mixed_or_weak_effect"


def build_arbitrary_risk_dynamics_sandbox_table(cfg: SandboxConfig = SandboxConfig()) -> pd.DataFrame:
    rows = []
    grid = _condition_grid()
    for spec in DYNAMICS_SPECS:
        for seed in SEEDS:
            baseline = _simulate(spec, "no_op", "none", 0.0, 0, 0, seed, cfg)
            for cond in grid:
                strategy = str(cond["strategy"])
                terrain_action = _terrain_action_for_strategy(spec, strategy)
                res = baseline if strategy == "no_op" else _simulate(
                    spec,
                    strategy,
                    terrain_action,
                    float(cond["strength_value"]),
                    int(cond["duration_steps"]),
                    int(cond["start_step"]),
                    seed,
                    cfg,
                )
                peak_delta = baseline["risk_peak"] - res["risk_peak"]
                auc_delta = baseline["risk_auc"] - res["risk_auc"]
                post_delta = baseline["post_action_risk_auc"] - res["post_action_risk_auc"]
                gain_delta = res["gain_auc"] - baseline["gain_auc"]
                side_delta = res["side_effect_auc"] - baseline["side_effect_auc"]
                terrain_delta = res["terrain_coeff_persistence"] - baseline["terrain_coeff_persistence"]
                net = (
                    auc_delta
                    + cfg.post_action_weight * post_delta
                    + cfg.peak_weight * peak_delta
                    + gain_delta
                    + cfg.terrain_persistence_weight * terrain_delta
                    - cfg.side_effect_weight * side_delta
                )
                positive = bool(strategy != "no_op" and res["action_matches_dynamics"] and net > 0.0 and auc_delta > 0.0 and post_delta > 0.0)
                row = {
                    "task2_8e_version": TASK2_8E_VERSION,
                    "task2_8e_contract": TASK2_8E_CONTRACT,
                    "validation_only": True,
                    "runtime_policy_input": False,
                    "action_frame_created": False,
                    "actionmodule_called": False,
                    "world_runtime_called": False,
                    "canonical_write_performed": False,
                    "upper_pressure_connected": False,
                    "exploration_escape_connected": False,
                    "synthetic_dynamics_only": True,
                    "terrain_coefficients_explicit": True,
                    "risk_dynamics_type": spec.dynamics_type,
                    "risk_dynamics_ja": spec.dynamics_ja,
                    "seed": int(seed),
                    "horizon": int(cfg.horizon),
                    "strategy": strategy,
                    "terrain_action": terrain_action,
                    "terrain_action_ja": ACTIONS.get(terrain_action, "なし"),
                    "strength_band": str(cond["strength_band"]),
                    "strength_value": float(cond["strength_value"]),
                    "duration_band": str(cond["duration_band"]),
                    "duration_steps": int(cond["duration_steps"]),
                    "timing_band": str(cond["timing_band"]),
                    "start_step": int(cond["start_step"]),
                    **res,
                    "long_term_net_benefit": float(net),
                    "risk_peak_delta_vs_no_op": float(peak_delta),
                    "risk_auc_delta_vs_no_op": float(auc_delta),
                    "post_action_auc_delta_vs_no_op": float(post_delta),
                    "gain_auc_delta_vs_no_op": float(gain_delta),
                    "side_effect_delta_vs_no_op": float(side_delta),
                    "terrain_persistence_delta_vs_no_op": float(terrain_delta),
                    "positive_net_vs_no_op": positive,
                }
                row["improvement_class"] = _classify(row)
                rows.append(row)
    out = pd.DataFrame(rows)
    return out[REQUIRED_TASK2_8E_COLUMNS]


def summarize_arbitrary_risk_dynamics_sandbox(table: pd.DataFrame) -> dict:
    if table is None or table.empty:
        return {"rows": 0}
    positive = table[table["positive_net_vs_no_op"].astype(bool)].copy()
    by_strategy = table.groupby("strategy").agg(
        rows=("strategy", "size"),
        positive_rows=("positive_net_vs_no_op", lambda s: int(pd.Series(s).astype(bool).sum())),
        mean_net=("long_term_net_benefit", "mean"),
        mean_auc_delta=("risk_auc_delta_vs_no_op", "mean"),
        mean_post_delta=("post_action_auc_delta_vs_no_op", "mean"),
        mean_peak_delta=("risk_peak_delta_vs_no_op", "mean"),
        mean_side_delta=("side_effect_delta_vs_no_op", "mean"),
        mean_terrain_persistence=("terrain_persistence_delta_vs_no_op", "mean"),
    ).reset_index()
    best_positive = positive.sort_values("long_term_net_benefit", ascending=False).head(1).iloc[0].to_dict() if not positive.empty else {}
    return {
        "rows": int(len(table)),
        "risk_dynamics_types": sorted(table["risk_dynamics_type"].astype(str).unique().tolist()),
        "strategies": sorted(table["strategy"].astype(str).unique().tolist()),
        "horizon": int(table["horizon"].max()),
        "positive_net_rows": int(len(positive)),
        "best_positive_dynamics": str(best_positive.get("risk_dynamics_type", "none")),
        "best_positive_strategy": str(best_positive.get("strategy", "none")),
        "best_positive_action": str(best_positive.get("terrain_action", "none")),
        "best_positive_strength_band": str(best_positive.get("strength_band", "none")),
        "best_positive_duration_band": str(best_positive.get("duration_band", "none")),
        "best_positive_timing_band": str(best_positive.get("timing_band", "none")),
        "best_positive_net": float(best_positive.get("long_term_net_benefit", 0.0)) if best_positive else 0.0,
        "by_strategy": by_strategy.to_dict(orient="records"),
    }


def validate_arbitrary_risk_dynamics_sandbox(table: pd.DataFrame) -> list[str]:
    errors = []
    if table is None or table.empty:
        return ["task2_8e_table_empty"]
    missing = sorted(set(REQUIRED_TASK2_8E_COLUMNS) - set(table.columns))
    if missing:
        return ["task2_8e_required_columns_missing:" + ",".join(missing)]
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
            errors.append(f"task2_8e_forbidden_true:{field}")
    for field in ["validation_only", "synthetic_dynamics_only", "terrain_coefficients_explicit"]:
        if not bool(table[field].astype(bool).all()):
            errors.append(f"task2_8e_required_true_not_all:{field}")
    if not bool((table["strategy"].astype(str) == "no_op").any()):
        errors.append("task2_8e_no_no_op_rows")
    if int(table["risk_dynamics_type"].nunique()) < 4:
        errors.append("task2_8e_missing_risk_dynamics_types")
    positive = table[table["positive_net_vs_no_op"].astype(bool)]
    if positive.empty:
        errors.append("task2_8e_no_positive_net_vs_no_op")
    if not positive.empty and not bool(positive["action_matches_dynamics"].astype(bool).all()):
        errors.append("task2_8e_positive_condition_contains_mismatched_action")
    mismatch = table[table["strategy"].astype(str) == "mismatched_action"]
    if not mismatch.empty and bool((mismatch["positive_net_vs_no_op"].astype(bool)).any()):
        errors.append("task2_8e_mismatch_positive_unexpected")
    for col in ["risk_peak", "risk_auc", "gain_auc", "side_effect_auc"]:
        vals = pd.to_numeric(table[col], errors="coerce")
        if bool(vals.isna().any() or (vals < 0.0).any()):
            errors.append(f"task2_8e_invalid_nonnegative:{col}")
    return errors


def build_and_validate_arbitrary_risk_dynamics_sandbox_table() -> tuple[pd.DataFrame, list[str], dict]:
    table = build_arbitrary_risk_dynamics_sandbox_table()
    errors = validate_arbitrary_risk_dynamics_sandbox(table)
    summary = summarize_arbitrary_risk_dynamics_sandbox(table)
    return table, errors, summary
