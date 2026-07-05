"""Task 2-8f: high-risk crash-cost risk dynamics sandbox RC1.

Purpose:
    Strengthen high-risk dynamics compared with Task 2-8e by adding:
      - no_op crash cost when risk crosses a threshold
      - high-risk recovery degradation
      - amplification phase transition
      - composite terrain actions
      - decomposed side-effect costs

This remains an artificial validation sandbox. The goal is to test whether
terrain reshaping behaves like insurance against tail-loss conditions.

Boundary:
    - validation only
    - synthetic dynamics only
    - no real H-DEPT upper pressure connection
    - no exploration-axis side-effect escape
    - no ActionFrame / ActionModule / world runtime / canonical write
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

TASK2_8F_VERSION = "high_risk_crash_cost_sandbox_rc1"
TASK2_8F_CONTRACT = "Task2_8f_high_risk_crash_cost_sandbox__no_op_tail_loss__composite_actions__no_upper_pressure__no_exploration_escape"
HORIZON = 120
SEEDS = (11, 23, 37)

STRENGTH_BANDS = {"low": 0.18, "mid": 0.30, "high": 0.42, "excessive": 0.64}
DURATION_BANDS = {"short": 14, "mid": 28, "long": 44}
TIMING_BANDS = {"early": 8, "on_time": 22, "late": 52}

ACTION_JA = {
    "none": "なし",
    "input_sensitivity_reduction": "入力感度低下作用",
    "amplification_loop_damping": "自己増幅遮断作用",
    "recovery_basin_formation": "回復谷形成作用",
}

STRATEGIES = (
    "no_op",
    "matched_single",
    "matched_composite_pair",
    "matched_composite_all",
    "mismatched_single",
    "excessive_overlong_matched",
    "late_composite",
)

REQUIRED_TASK2_8F_COLUMNS = [
    "task2_8f_version",
    "task2_8f_contract",
    "validation_only",
    "runtime_policy_input",
    "action_frame_created",
    "actionmodule_called",
    "world_runtime_called",
    "canonical_write_performed",
    "upper_pressure_connected",
    "exploration_escape_connected",
    "synthetic_dynamics_only",
    "high_risk_tail_loss_enabled",
    "side_effect_decomposed",
    "risk_dynamics_type",
    "risk_dynamics_ja",
    "seed",
    "horizon",
    "strategy",
    "terrain_actions",
    "terrain_actions_ja",
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
    "post_action_risk_auc",
    "risk_slope_after_action",
    "gain_auc",
    "gain_end",
    "gain_min",
    "crash_cost_auc",
    "crash_steps",
    "irreversibility_auc",
    "recovery_margin_end",
    "amplification_end",
    "input_sensitivity_end",
    "terrain_coeff_persistence",
    "short_gain_loss_auc",
    "liquidity_loss_auc",
    "overcooling_loss_auc",
    "mismatch_cost_auc",
    "complexity_cost_auc",
    "side_effect_auc",
    "long_term_net_benefit",
    "risk_peak_delta_vs_no_op",
    "risk_auc_delta_vs_no_op",
    "post_action_auc_delta_vs_no_op",
    "gain_auc_delta_vs_no_op",
    "crash_cost_delta_vs_no_op",
    "irreversibility_delta_vs_no_op",
    "side_effect_delta_vs_no_op",
    "terrain_persistence_delta_vs_no_op",
    "positive_tail_insurance_condition",
    "improvement_class",
]


@dataclass(frozen=True)
class HighRiskDynamicsSpec:
    dynamics_type: str
    dynamics_ja: str
    recommended_single: tuple[str, ...]
    recommended_pair: tuple[str, ...]
    wrong_single: tuple[str, ...]
    input_sensitivity: float
    amplification: float
    recovery_margin: float
    external_pressure: float
    shock_step: int
    shock_size: float
    transition_threshold: float
    crash_threshold: float
    transition_gain: float
    recovery_degradation: float
    crash_gain_loss: float
    gain_base: float


DYNAMICS_SPECS = (
    HighRiskDynamicsSpec(
        dynamics_type="input_sensitivity_tail_bubble",
        dynamics_ja="入力感度尾部バブル型",
        recommended_single=("input_sensitivity_reduction",),
        recommended_pair=("input_sensitivity_reduction", "amplification_loop_damping"),
        wrong_single=("recovery_basin_formation",),
        input_sensitivity=0.92,
        amplification=0.48,
        recovery_margin=0.20,
        external_pressure=0.62,
        shock_step=30,
        shock_size=0.090,
        transition_threshold=0.66,
        crash_threshold=0.82,
        transition_gain=0.012,
        recovery_degradation=0.010,
        crash_gain_loss=0.085,
        gain_base=0.60,
    ),
    HighRiskDynamicsSpec(
        dynamics_type="amplification_phase_transition",
        dynamics_ja="自己増幅相転移型",
        recommended_single=("amplification_loop_damping",),
        recommended_pair=("input_sensitivity_reduction", "amplification_loop_damping"),
        wrong_single=("recovery_basin_formation",),
        input_sensitivity=0.58,
        amplification=0.96,
        recovery_margin=0.18,
        external_pressure=0.55,
        shock_step=34,
        shock_size=0.075,
        transition_threshold=0.58,
        crash_threshold=0.80,
        transition_gain=0.020,
        recovery_degradation=0.012,
        crash_gain_loss=0.090,
        gain_base=0.59,
    ),
    HighRiskDynamicsSpec(
        dynamics_type="recovery_irreversibility_trap",
        dynamics_ja="回復不能化罠型",
        recommended_single=("recovery_basin_formation",),
        recommended_pair=("amplification_loop_damping", "recovery_basin_formation"),
        wrong_single=("input_sensitivity_reduction",),
        input_sensitivity=0.56,
        amplification=0.62,
        recovery_margin=0.08,
        external_pressure=0.50,
        shock_step=28,
        shock_size=0.110,
        transition_threshold=0.62,
        crash_threshold=0.78,
        transition_gain=0.012,
        recovery_degradation=0.020,
        crash_gain_loss=0.095,
        gain_base=0.58,
    ),
    HighRiskDynamicsSpec(
        dynamics_type="composite_tail_bubble",
        dynamics_ja="複合尾部バブル型",
        recommended_single=("amplification_loop_damping",),
        recommended_pair=("input_sensitivity_reduction", "amplification_loop_damping"),
        wrong_single=("recovery_basin_formation",),
        input_sensitivity=0.82,
        amplification=0.92,
        recovery_margin=0.10,
        external_pressure=0.60,
        shock_step=32,
        shock_size=0.095,
        transition_threshold=0.56,
        crash_threshold=0.76,
        transition_gain=0.022,
        recovery_degradation=0.018,
        crash_gain_loss=0.105,
        gain_base=0.61,
    ),
)


@dataclass(frozen=True)
class HighRiskSandboxConfig:
    horizon: int = HORIZON
    side_effect_weight: float = 0.52
    peak_weight: float = 0.34
    post_action_weight: float = 0.38
    crash_cost_weight: float = 0.90
    irreversibility_weight: float = 0.50
    terrain_persistence_weight: float = 0.18


def _clip01(x: float) -> float:
    return float(max(0.0, min(1.0, float(x))))


def _noise(seed: int, step: int) -> float:
    return ((((seed * 181 + step * 79) % 1000) / 1000.0) - 0.5) * 0.0011


def _lin_slope(values: list[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    xm = (n - 1) / 2.0
    ym = sum(values) / n
    denom = sum((i - xm) ** 2 for i in range(n)) or 1.0
    return float(sum((i - xm) * (v - ym) for i, v in enumerate(values)) / denom)


def _terrain_actions_for_strategy(spec: HighRiskDynamicsSpec, strategy: str) -> tuple[str, ...]:
    if strategy == "no_op":
        return ("none",)
    if strategy == "mismatched_single":
        return spec.wrong_single
    if strategy in {"matched_composite_pair", "late_composite"}:
        return spec.recommended_pair
    if strategy == "matched_composite_all":
        return ("input_sensitivity_reduction", "amplification_loop_damping", "recovery_basin_formation")
    return spec.recommended_single


def _strategy_is_matched(spec: HighRiskDynamicsSpec, strategy: str, actions: tuple[str, ...]) -> bool:
    if strategy == "no_op":
        return False
    if strategy == "mismatched_single":
        return False
    return bool(set(actions) & (set(spec.recommended_single) | set(spec.recommended_pair)))


def _apply_actions(
    actions: tuple[str, ...],
    strength: float,
    matched: bool,
    input_sensitivity: float,
    amplification: float,
    recovery_margin: float,
) -> tuple[float, float, float, dict[str, float]]:
    n_actions = len([a for a in actions if a != "none"])
    if n_actions <= 0:
        return input_sensitivity, amplification, recovery_margin, {
            "short_gain_loss": 0.0,
            "liquidity_loss": 0.0,
            "overcooling_loss": 0.0,
            "mismatch_cost": 0.0,
            "complexity_cost": 0.0,
        }
    precision = 1.00 if matched else 0.34
    before = (input_sensitivity, amplification, recovery_margin)
    step_change = 0.020 * strength * precision / max(1.0, n_actions ** 0.35)
    for action in actions:
        if action == "input_sensitivity_reduction":
            input_sensitivity = max(0.06, input_sensitivity - step_change)
        elif action == "amplification_loop_damping":
            amplification = max(0.06, amplification - step_change)
        elif action == "recovery_basin_formation":
            recovery_margin = min(0.95, recovery_margin + step_change)
    total_change = abs(before[0] - input_sensitivity) + abs(before[1] - amplification) + abs(recovery_margin - before[2])
    # Decomposed side effects. They are deliberately not all equal: suppressing
    # input sensitivity costs liquidity, damping amplification costs short gain,
    # excessive multi-action use can overcool the terrain.
    short_gain_loss = (0.004 + 0.010 * strength * strength) * (1.0 + 0.25 * ("amplification_loop_damping" in actions))
    liquidity_loss = (0.003 + 0.008 * strength) * (1.0 + 0.35 * ("input_sensitivity_reduction" in actions))
    overcooling_loss = max(0.0, total_change - 0.018) * (1.25 + 0.30 * n_actions)
    mismatch_cost = 0.0 if matched else 0.020 + 0.024 * strength
    complexity_cost = 0.004 * max(0, n_actions - 1) * strength
    if matched:
        mismatch_cost = 0.0
        liquidity_loss *= 0.70
        short_gain_loss *= 0.75
    return input_sensitivity, amplification, recovery_margin, {
        "short_gain_loss": float(short_gain_loss),
        "liquidity_loss": float(liquidity_loss),
        "overcooling_loss": float(overcooling_loss),
        "mismatch_cost": float(mismatch_cost),
        "complexity_cost": float(complexity_cost),
    }


def _simulate(
    spec: HighRiskDynamicsSpec,
    strategy: str,
    actions: tuple[str, ...],
    strength: float,
    duration: int,
    start_step: int,
    seed: int,
    cfg: HighRiskSandboxConfig,
) -> dict:
    risk = 0.32
    gain = spec.gain_base
    input_sensitivity = spec.input_sensitivity
    amplification = spec.amplification
    recovery_margin = spec.recovery_margin
    initial_coeffs = (input_sensitivity, amplification, recovery_margin)
    matched = _strategy_is_matched(spec, strategy, actions)
    end_step = start_step + duration
    risks = [risk]
    gains = [gain]
    short_gain_loss_auc = 0.0
    liquidity_loss_auc = 0.0
    overcooling_loss_auc = 0.0
    mismatch_cost_auc = 0.0
    complexity_cost_auc = 0.0
    crash_cost_auc = 0.0
    irreversibility_auc = 0.0
    crash_steps = 0

    for step in range(1, cfg.horizon + 1):
        active = strategy != "no_op" and start_step <= step < end_step
        side = {
            "short_gain_loss": 0.0,
            "liquidity_loss": 0.0,
            "overcooling_loss": 0.0,
            "mismatch_cost": 0.0,
            "complexity_cost": 0.0,
        }
        if active:
            input_sensitivity, amplification, recovery_margin, side = _apply_actions(
                actions,
                strength,
                matched,
                input_sensitivity,
                amplification,
                recovery_margin,
            )

        # High-risk nonlinearity: when risk crosses the transition zone,
        # amplification rises and recovery margin degrades. This makes no_op
        # tail-loss materially worse than in Task 2-8e.
        high_excess = max(0.0, risk - spec.transition_threshold)
        if high_excess > 0.0:
            amplification = min(1.55, amplification + spec.transition_gain * high_excess)
            recovery_margin = max(0.01, recovery_margin - spec.recovery_degradation * high_excess)
            irreversibility_auc += high_excess

        external_pressure = spec.external_pressure + 0.16 * max(0.0, (step - 20) / cfg.horizon)
        shock = spec.shock_size if step == spec.shock_step else 0.0
        input_push = 0.019 * input_sensitivity * external_pressure
        loop_push = 0.026 * amplification * max(0.0, risk - 0.38) ** 1.18
        recovery_pull = 0.017 * recovery_margin * max(0.0, risk - 0.22)
        risk = _clip01(risk + input_push + loop_push + shock - recovery_pull + _noise(seed, step))

        crash_excess = max(0.0, risk - spec.crash_threshold)
        crash_cost = spec.crash_gain_loss * crash_excess * (1.0 + 1.8 * crash_excess)
        if crash_excess > 0.0:
            crash_steps += 1
        side_total = sum(side.values())
        gain_flow = 0.010 * (1.0 - risk) - 0.004 * risk - crash_cost - 0.030 * side_total
        gain = _clip01(gain + gain_flow)

        short_gain_loss_auc += side["short_gain_loss"]
        liquidity_loss_auc += side["liquidity_loss"]
        overcooling_loss_auc += side["overcooling_loss"]
        mismatch_cost_auc += side["mismatch_cost"]
        complexity_cost_auc += side["complexity_cost"]
        crash_cost_auc += crash_cost
        risks.append(risk)
        gains.append(gain)

    post_start = min(max(end_step, 1), cfg.horizon - 1)
    post_values = risks[post_start:]
    coeff_persistence = (
        abs(initial_coeffs[0] - input_sensitivity)
        + abs(initial_coeffs[1] - amplification)
        + abs(recovery_margin - initial_coeffs[2])
    ) / 3.0
    side_effect_auc = short_gain_loss_auc + liquidity_loss_auc + overcooling_loss_auc + mismatch_cost_auc + complexity_cost_auc
    return {
        "action_matches_dynamics": bool(matched),
        "end_step": int(end_step),
        "risk_peak": float(max(risks)),
        "risk_end": float(risks[-1]),
        "risk_auc": float(sum(risks) / len(risks)),
        "post_action_risk_auc": float(sum(post_values) / len(post_values)) if post_values else float(risks[-1]),
        "risk_slope_after_action": _lin_slope(post_values[-24:] if len(post_values) >= 24 else post_values),
        "gain_auc": float(sum(gains) / len(gains)),
        "gain_end": float(gains[-1]),
        "gain_min": float(min(gains)),
        "crash_cost_auc": float(crash_cost_auc),
        "crash_steps": int(crash_steps),
        "irreversibility_auc": float(irreversibility_auc),
        "recovery_margin_end": float(recovery_margin),
        "amplification_end": float(amplification),
        "input_sensitivity_end": float(input_sensitivity),
        "terrain_coeff_persistence": float(coeff_persistence),
        "short_gain_loss_auc": float(short_gain_loss_auc),
        "liquidity_loss_auc": float(liquidity_loss_auc),
        "overcooling_loss_auc": float(overcooling_loss_auc),
        "mismatch_cost_auc": float(mismatch_cost_auc),
        "complexity_cost_auc": float(complexity_cost_auc),
        "side_effect_auc": float(side_effect_auc),
    }


def _condition_grid() -> list[dict]:
    rows = [{
        "strategy": "no_op",
        "strength_band": "none",
        "strength_value": 0.0,
        "duration_band": "none",
        "duration_steps": 0,
        "timing_band": "none",
        "start_step": 0,
    }]
    for strength_band, strength_value in STRENGTH_BANDS.items():
        for duration_band, duration_steps in DURATION_BANDS.items():
            for timing_band, start_step in TIMING_BANDS.items():
                for strategy in ("matched_single", "matched_composite_pair", "matched_composite_all", "mismatched_single"):
                    rows.append({
                        "strategy": strategy,
                        "strength_band": strength_band,
                        "strength_value": strength_value,
                        "duration_band": duration_band,
                        "duration_steps": duration_steps,
                        "timing_band": timing_band,
                        "start_step": start_step,
                    })
    for timing_band, start_step in {"early": 8, "on_time": 22}.items():
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
                "strategy": "late_composite",
                "strength_band": strength_band,
                "strength_value": strength_value,
                "duration_band": duration_band,
                "duration_steps": duration_steps,
                "timing_band": "late",
                "start_step": TIMING_BANDS["late"],
            })
    return rows


def _action_names_ja(actions: tuple[str, ...]) -> str:
    return ";".join(ACTION_JA.get(a, a) for a in actions)


def _classify(row: dict) -> str:
    if row["strategy"] == "no_op":
        return "baseline_no_op_tail_loss"
    if row["positive_tail_insurance_condition"] and row["strategy"] in {"matched_composite_pair", "matched_composite_all"}:
        return "composite_tail_insurance_positive"
    if row["positive_tail_insurance_condition"]:
        return "single_tail_insurance_positive"
    if row["crash_cost_delta_vs_no_op"] > 0.02 and row["long_term_net_benefit"] <= 0.0:
        return "crash_reduced_but_side_effect_loses"
    if not row["action_matches_dynamics"] and row["long_term_net_benefit"] <= 0.0:
        return "mismatch_or_waste_loses"
    if row["timing_band"] == "late" and row["long_term_net_benefit"] <= 0.0:
        return "late_action_loses"
    if row["side_effect_delta_vs_no_op"] > 0.18 and row["long_term_net_benefit"] <= 0.0:
        return "overuse_side_effect_loses"
    return "mixed_or_weak_effect"


def build_high_risk_crash_cost_sandbox_table(cfg: HighRiskSandboxConfig = HighRiskSandboxConfig()) -> pd.DataFrame:
    rows = []
    grid = _condition_grid()
    for spec in DYNAMICS_SPECS:
        for seed in SEEDS:
            baseline = _simulate(spec, "no_op", ("none",), 0.0, 0, 0, seed, cfg)
            for cond in grid:
                strategy = str(cond["strategy"])
                actions = _terrain_actions_for_strategy(spec, strategy)
                res = baseline if strategy == "no_op" else _simulate(
                    spec,
                    strategy,
                    actions,
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
                crash_delta = baseline["crash_cost_auc"] - res["crash_cost_auc"]
                irreversible_delta = baseline["irreversibility_auc"] - res["irreversibility_auc"]
                side_delta = res["side_effect_auc"] - baseline["side_effect_auc"]
                terrain_delta = res["terrain_coeff_persistence"] - baseline["terrain_coeff_persistence"]
                net = (
                    auc_delta
                    + cfg.post_action_weight * post_delta
                    + cfg.peak_weight * peak_delta
                    + gain_delta
                    + cfg.crash_cost_weight * crash_delta
                    + cfg.irreversibility_weight * irreversible_delta
                    + cfg.terrain_persistence_weight * terrain_delta
                    - cfg.side_effect_weight * side_delta
                )
                positive = bool(
                    strategy != "no_op"
                    and res["action_matches_dynamics"]
                    and net > 0.0
                    and crash_delta > 0.0
                    and irreversible_delta >= 0.0
                    and auc_delta > 0.0
                )
                row = {
                    "task2_8f_version": TASK2_8F_VERSION,
                    "task2_8f_contract": TASK2_8F_CONTRACT,
                    "validation_only": True,
                    "runtime_policy_input": False,
                    "action_frame_created": False,
                    "actionmodule_called": False,
                    "world_runtime_called": False,
                    "canonical_write_performed": False,
                    "upper_pressure_connected": False,
                    "exploration_escape_connected": False,
                    "synthetic_dynamics_only": True,
                    "high_risk_tail_loss_enabled": True,
                    "side_effect_decomposed": True,
                    "risk_dynamics_type": spec.dynamics_type,
                    "risk_dynamics_ja": spec.dynamics_ja,
                    "seed": int(seed),
                    "horizon": int(cfg.horizon),
                    "strategy": strategy,
                    "terrain_actions": ";".join(actions),
                    "terrain_actions_ja": _action_names_ja(actions),
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
                    "crash_cost_delta_vs_no_op": float(crash_delta),
                    "irreversibility_delta_vs_no_op": float(irreversible_delta),
                    "side_effect_delta_vs_no_op": float(side_delta),
                    "terrain_persistence_delta_vs_no_op": float(terrain_delta),
                    "positive_tail_insurance_condition": positive,
                }
                row["improvement_class"] = _classify(row)
                rows.append(row)
    out = pd.DataFrame(rows)
    return out[REQUIRED_TASK2_8F_COLUMNS]


def summarize_high_risk_crash_cost_sandbox(table: pd.DataFrame) -> dict:
    if table is None or table.empty:
        return {"rows": 0}
    positive = table[table["positive_tail_insurance_condition"].astype(bool)].copy()
    by_strategy = table.groupby("strategy").agg(
        rows=("strategy", "size"),
        positive_rows=("positive_tail_insurance_condition", lambda s: int(pd.Series(s).astype(bool).sum())),
        mean_net=("long_term_net_benefit", "mean"),
        mean_crash_delta=("crash_cost_delta_vs_no_op", "mean"),
        mean_irreversibility_delta=("irreversibility_delta_vs_no_op", "mean"),
        mean_auc_delta=("risk_auc_delta_vs_no_op", "mean"),
        mean_gain_delta=("gain_auc_delta_vs_no_op", "mean"),
        mean_side_delta=("side_effect_delta_vs_no_op", "mean"),
    ).reset_index()
    side_by_strategy = table.groupby("strategy").agg(
        short_gain_loss_mean=("short_gain_loss_auc", "mean"),
        liquidity_loss_mean=("liquidity_loss_auc", "mean"),
        overcooling_loss_mean=("overcooling_loss_auc", "mean"),
        mismatch_cost_mean=("mismatch_cost_auc", "mean"),
        complexity_cost_mean=("complexity_cost_auc", "mean"),
    ).reset_index()
    best_positive = positive.sort_values("long_term_net_benefit", ascending=False).head(1).iloc[0].to_dict() if not positive.empty else {}
    return {
        "rows": int(len(table)),
        "risk_dynamics_types": sorted(table["risk_dynamics_type"].astype(str).unique().tolist()),
        "strategies": sorted(table["strategy"].astype(str).unique().tolist()),
        "horizon": int(table["horizon"].max()),
        "positive_tail_insurance_rows": int(len(positive)),
        "best_positive_dynamics": str(best_positive.get("risk_dynamics_type", "none")),
        "best_positive_strategy": str(best_positive.get("strategy", "none")),
        "best_positive_actions": str(best_positive.get("terrain_actions", "none")),
        "best_positive_strength_band": str(best_positive.get("strength_band", "none")),
        "best_positive_duration_band": str(best_positive.get("duration_band", "none")),
        "best_positive_timing_band": str(best_positive.get("timing_band", "none")),
        "best_positive_net": float(best_positive.get("long_term_net_benefit", 0.0)) if best_positive else 0.0,
        "by_strategy": by_strategy.to_dict(orient="records"),
        "side_effect_by_strategy": side_by_strategy.to_dict(orient="records"),
    }


def validate_high_risk_crash_cost_sandbox(table: pd.DataFrame) -> list[str]:
    errors = []
    if table is None or table.empty:
        return ["task2_8f_table_empty"]
    missing = sorted(set(REQUIRED_TASK2_8F_COLUMNS) - set(table.columns))
    if missing:
        return ["task2_8f_required_columns_missing:" + ",".join(missing)]
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
            errors.append(f"task2_8f_forbidden_true:{field}")
    for field in ["validation_only", "synthetic_dynamics_only", "high_risk_tail_loss_enabled", "side_effect_decomposed"]:
        if not bool(table[field].astype(bool).all()):
            errors.append(f"task2_8f_required_true_not_all:{field}")
    if not bool((table["strategy"].astype(str) == "no_op").any()):
        errors.append("task2_8f_no_no_op_rows")
    if int(table["risk_dynamics_type"].nunique()) < 4:
        errors.append("task2_8f_missing_risk_dynamics_types")
    no_op = table[table["strategy"].astype(str) == "no_op"]
    if no_op.empty or not bool((no_op["crash_cost_auc"] > 0.0).any()):
        errors.append("task2_8f_no_op_has_no_crash_cost")
    positive = table[table["positive_tail_insurance_condition"].astype(bool)]
    if positive.empty:
        errors.append("task2_8f_no_positive_tail_insurance_condition")
    if not positive.empty:
        if not bool(positive["action_matches_dynamics"].astype(bool).all()):
            errors.append("task2_8f_positive_contains_mismatched_action")
        if not bool((positive["crash_cost_delta_vs_no_op"] > 0.0).all()):
            errors.append("task2_8f_positive_without_crash_cost_reduction")
    mismatch = table[table["strategy"].astype(str) == "mismatched_single"]
    if not mismatch.empty and bool(mismatch["positive_tail_insurance_condition"].astype(bool).any()):
        errors.append("task2_8f_mismatch_positive_unexpected")
    side_sum = (
        table["short_gain_loss_auc"]
        + table["liquidity_loss_auc"]
        + table["overcooling_loss_auc"]
        + table["mismatch_cost_auc"]
        + table["complexity_cost_auc"]
    )
    if bool((side_sum - table["side_effect_auc"]).abs().gt(1e-9).any()):
        errors.append("task2_8f_side_effect_decomposition_mismatch")
    for col in ["risk_peak", "risk_auc", "gain_auc", "side_effect_auc", "crash_cost_auc", "irreversibility_auc"]:
        vals = pd.to_numeric(table[col], errors="coerce")
        if bool(vals.isna().any() or (vals < 0.0).any()):
            errors.append(f"task2_8f_invalid_nonnegative:{col}")
    return errors


def build_and_validate_high_risk_crash_cost_sandbox_table() -> tuple[pd.DataFrame, list[str], dict]:
    table = build_high_risk_crash_cost_sandbox_table()
    errors = validate_high_risk_crash_cost_sandbox(table)
    summary = summarize_high_risk_crash_cost_sandbox(table)
    return table, errors, summary
