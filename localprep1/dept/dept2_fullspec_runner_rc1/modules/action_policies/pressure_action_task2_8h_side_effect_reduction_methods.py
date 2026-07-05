"""Task 2-8h: action-method side-effect reduction sandbox RC1.

Purpose:
    Compare action *methods*, not exploration axes, to see whether more precise
    terrain-resistance adjustment can reduce side effects while preserving
    tail-risk insurance benefit.

Compared methods:
    - no_op
    - wall_global: broad coefficient intervention, close to the previous wall-like action
    - direction_selective: resist only dangerous transition components
    - state_dependent: resist only when risk / slope / acceleration gates are active
    - thin_film_release: short-lived intervention that releases after improvement
    - selective_state_thin: direction-selective + state-dependent + early release

Boundary:
    - validation only
    - synthetic dynamics only
    - no exploration-axis incentive
    - no real H-DEPT upper pressure connection
    - no ActionFrame / ActionModule / world runtime / canonical write
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .pressure_action_task2_8f_high_risk_crash_cost_sandbox import (
    ACTION_JA,
    DYNAMICS_SPECS,
    HighRiskDynamicsSpec,
)

TASK2_8H_VERSION = "side_effect_reduction_methods_rc1"
TASK2_8H_CONTRACT = "Task2_8h_action_method_side_effect_reduction__no_exploration_axis__no_upper_pressure"
HORIZON = 120
SEEDS = (11, 37)
INITIAL_RISK_LEVELS = (0.35, 0.45, 0.55, 0.65)
CRASH_THRESHOLDS = (0.76, 0.82)
STRENGTH_BANDS = {"low": 0.18, "mid": 0.30, "high": 0.42}
DURATION_BANDS = {"short": 14, "mid": 28, "long": 44}
TIMING_BANDS = {"early": 8, "on_time": 22}

METHODS = (
    "no_op",
    "wall_global",
    "direction_selective",
    "state_dependent",
    "thin_film_release",
    "selective_state_thin",
)

METHOD_JA = {
    "no_op": "何もしない",
    "wall_global": "壁型作用",
    "direction_selective": "方向選択型抵抗",
    "state_dependent": "状態依存型抵抗",
    "thin_film_release": "薄膜・即時解除型作用",
    "selective_state_thin": "方向選択+状態依存+即時解除",
}

REQUIRED_TASK2_8H_COLUMNS = [
    "task2_8h_version",
    "task2_8h_contract",
    "validation_only",
    "runtime_policy_input",
    "action_frame_created",
    "actionmodule_called",
    "world_runtime_called",
    "canonical_write_performed",
    "upper_pressure_connected",
    "exploration_axis_connected",
    "synthetic_dynamics_only",
    "action_method_comparison",
    "risk_dynamics_type",
    "risk_dynamics_ja",
    "seed",
    "horizon",
    "initial_risk_level",
    "crash_threshold",
    "method",
    "method_ja",
    "terrain_actions",
    "terrain_actions_ja",
    "strength_band",
    "strength_value",
    "duration_band",
    "duration_steps",
    "timing_band",
    "start_step",
    "actual_active_steps",
    "release_triggered",
    "risk_peak",
    "risk_end",
    "risk_auc",
    "post_action_risk_auc",
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
    "risk_auc_delta_vs_no_op",
    "crash_cost_delta_vs_no_op",
    "irreversibility_delta_vs_no_op",
    "gain_auc_delta_vs_no_op",
    "side_effect_delta_vs_no_op",
    "side_effect_per_crash_reduction",
    "net_per_side_effect",
    "positive_side_effect_reduced_condition",
    "improvement_class",
]


@dataclass(frozen=True)
class MethodSandboxConfig:
    horizon: int = HORIZON
    side_effect_weight: float = 0.52
    crash_cost_weight: float = 0.90
    irreversibility_weight: float = 0.50
    post_action_weight: float = 0.36
    terrain_persistence_weight: float = 0.12


def _clip01(x: float) -> float:
    return float(max(0.0, min(1.0, float(x))))


def _noise(seed: int, step: int) -> float:
    return ((((seed * 181 + step * 79) % 1000) / 1000.0) - 0.5) * 0.0011


def _actions_for_spec(spec: HighRiskDynamicsSpec) -> tuple[str, ...]:
    # Use the recommended pair as the fixed target, so the experiment isolates
    # action method, not prediction/exploration quality.
    return spec.recommended_pair


def _action_names_ja(actions: tuple[str, ...]) -> str:
    return ";".join(ACTION_JA.get(a, a) for a in actions)


def _side_effects(
    method: str,
    actions: tuple[str, ...],
    strength: float,
    method_factor: float,
    total_coeff_change: float,
) -> dict[str, float]:
    n_actions = len([a for a in actions if a != "none"])
    if method == "no_op" or n_actions <= 0 or method_factor <= 0.0:
        return {
            "short_gain_loss": 0.0,
            "liquidity_loss": 0.0,
            "overcooling_loss": 0.0,
            "mismatch_cost": 0.0,
            "complexity_cost": 0.0,
        }
    # Wall-like action has broad cost. Selective/state/thin methods pay less
    # because they touch only dangerous transition components or release early.
    method_side_scale = {
        "wall_global": 1.00,
        "direction_selective": 0.46,
        "state_dependent": 0.54,
        "thin_film_release": 0.58,
        "selective_state_thin": 0.32,
    }.get(method, 1.0)
    short_gain_loss = (0.004 + 0.010 * strength * strength) * method_side_scale * method_factor
    liquidity_loss = (0.003 + 0.008 * strength) * method_side_scale * method_factor
    overcooling_loss = max(0.0, total_coeff_change - 0.018) * (1.10 + 0.22 * n_actions) * method_side_scale
    mismatch_cost = 0.0
    complexity_cost = 0.0035 * max(0, n_actions - 1) * strength * method_side_scale * method_factor
    return {
        "short_gain_loss": float(short_gain_loss),
        "liquidity_loss": float(liquidity_loss),
        "overcooling_loss": float(overcooling_loss),
        "mismatch_cost": float(mismatch_cost),
        "complexity_cost": float(complexity_cost),
    }


def _method_gate(method: str, risk: float, previous_risk: float, spec: HighRiskDynamicsSpec, start_step: int, step: int) -> float:
    slope = risk - previous_risk
    risk_excess = max(0.0, risk - spec.transition_threshold)
    accel_like = max(0.0, slope)
    if method == "wall_global":
        return 1.0
    if method == "direction_selective":
        return 1.0 if (slope > 0.001 or risk > spec.transition_threshold) else 0.20
    if method == "state_dependent":
        return _clip01(0.20 + 3.0 * risk_excess + 55.0 * accel_like)
    if method == "thin_film_release":
        # Front-loaded thin action: strongest early, then fades.
        age = max(0, step - start_step)
        return max(0.12, 1.0 - 0.055 * age)
    if method == "selective_state_thin":
        age = max(0, step - start_step)
        thin = max(0.10, 1.0 - 0.065 * age)
        state = _clip01(0.10 + 3.2 * risk_excess + 60.0 * accel_like)
        directional = 1.0 if (slope > 0.001 or risk > spec.transition_threshold) else 0.10
        return max(0.0, min(thin, state) * directional)
    return 0.0


def _apply_wall_coeffs(
    actions: tuple[str, ...],
    strength: float,
    input_sensitivity: float,
    amplification: float,
    recovery_margin: float,
) -> tuple[float, float, float, float]:
    before = (input_sensitivity, amplification, recovery_margin)
    step_change = 0.018 * strength / max(1.0, len(actions) ** 0.35)
    for action in actions:
        if action == "input_sensitivity_reduction":
            input_sensitivity = max(0.06, input_sensitivity - step_change)
        elif action == "amplification_loop_damping":
            amplification = max(0.06, amplification - step_change)
        elif action == "recovery_basin_formation":
            recovery_margin = min(0.95, recovery_margin + step_change)
    total_change = abs(before[0] - input_sensitivity) + abs(before[1] - amplification) + abs(recovery_margin - before[2])
    return input_sensitivity, amplification, recovery_margin, float(total_change)


def _simulate(
    spec: HighRiskDynamicsSpec,
    initial_risk: float,
    crash_threshold: float,
    method: str,
    actions: tuple[str, ...],
    strength: float,
    duration: int,
    start_step: int,
    seed: int,
    cfg: MethodSandboxConfig,
) -> dict:
    risk = _clip01(initial_risk)
    previous_risk = risk
    gain = spec.gain_base
    input_sensitivity = spec.input_sensitivity
    amplification = spec.amplification
    recovery_margin = spec.recovery_margin
    initial_coeffs = (input_sensitivity, amplification, recovery_margin)
    end_step = start_step + duration
    released = False
    release_counter = 0
    actual_active_steps = 0
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
        scheduled_active = method != "no_op" and start_step <= step < end_step
        if method in {"thin_film_release", "selective_state_thin"} and scheduled_active:
            if len(risks) >= 4 and risks[-1] < risks[-2] < risks[-3]:
                release_counter += 1
            else:
                release_counter = 0
            if release_counter >= 2:
                released = True
        active = scheduled_active and not released
        gate = _method_gate(method, risk, previous_risk, spec, start_step, step) if active else 0.0
        total_change = 0.0
        if active and gate > 0.0:
            actual_active_steps += 1
            if method == "wall_global":
                input_sensitivity, amplification, recovery_margin, total_change = _apply_wall_coeffs(
                    actions, strength * gate, input_sensitivity, amplification, recovery_margin
                )
        side = _side_effects(method, actions, strength, gate, total_change)

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

        if active and gate > 0.0 and method != "wall_global":
            # Instead of broadly changing terrain coefficients, precise methods
            # resist only dangerous transition components in the current step.
            effect = strength * gate
            if "input_sensitivity_reduction" in actions:
                input_push *= max(0.30, 1.0 - 0.65 * effect)
            if "amplification_loop_damping" in actions:
                loop_push *= max(0.25, 1.0 - 0.72 * effect)
            if "recovery_basin_formation" in actions:
                recovery_pull *= 1.0 + 0.55 * effect
            total_change = 0.010 * effect * len([a for a in actions if a != "none"])

        previous_risk = risk
        risk = _clip01(risk + input_push + loop_push + shock - recovery_pull + _noise(seed, step))

        crash_excess = max(0.0, risk - crash_threshold)
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
        "actual_active_steps": int(actual_active_steps),
        "release_triggered": bool(released),
        "risk_peak": float(max(risks)),
        "risk_end": float(risks[-1]),
        "risk_auc": float(sum(risks) / len(risks)),
        "post_action_risk_auc": float(sum(post_values) / len(post_values)) if post_values else float(risks[-1]),
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


def _classify(row: dict) -> str:
    if row["method"] == "no_op":
        return "baseline_no_op"
    if row["positive_side_effect_reduced_condition"] and row["side_effect_per_crash_reduction"] < 0.80:
        return "efficient_side_effect_reduced_insurance"
    if row["positive_side_effect_reduced_condition"]:
        return "positive_but_costly_insurance"
    if row["crash_cost_delta_vs_no_op"] > 0.0 and row["long_term_net_benefit"] <= 0.0:
        return "crash_reduced_but_side_effect_loses"
    if row["side_effect_delta_vs_no_op"] > 0.5 and row["long_term_net_benefit"] <= 0.0:
        return "wall_like_side_effect_loses"
    return "mixed_or_weak_effect"


def build_side_effect_reduction_methods_table(cfg: MethodSandboxConfig = MethodSandboxConfig()) -> pd.DataFrame:
    rows = []
    for spec in DYNAMICS_SPECS:
        actions = _actions_for_spec(spec)
        for initial_risk in INITIAL_RISK_LEVELS:
            for crash_threshold in CRASH_THRESHOLDS:
                for seed in SEEDS:
                    baseline = _simulate(spec, initial_risk, crash_threshold, "no_op", ("none",), 0.0, 0, 0, seed, cfg)
                    for method in METHODS:
                        if method == "no_op":
                            conds = [("none", 0.0, "none", 0, "none", 0)]
                        else:
                            conds = [
                                (strength_band, strength_value, duration_band, duration_steps, timing_band, start_step)
                                for strength_band, strength_value in STRENGTH_BANDS.items()
                                for duration_band, duration_steps in DURATION_BANDS.items()
                                for timing_band, start_step in TIMING_BANDS.items()
                            ]
                        for strength_band, strength_value, duration_band, duration_steps, timing_band, start_step in conds:
                            res = baseline if method == "no_op" else _simulate(
                                spec,
                                initial_risk,
                                crash_threshold,
                                method,
                                actions,
                                float(strength_value),
                                int(duration_steps),
                                int(start_step),
                                seed,
                                cfg,
                            )
                            auc_delta = baseline["risk_auc"] - res["risk_auc"]
                            crash_delta = baseline["crash_cost_auc"] - res["crash_cost_auc"]
                            irreversible_delta = baseline["irreversibility_auc"] - res["irreversibility_auc"]
                            gain_delta = res["gain_auc"] - baseline["gain_auc"]
                            side_delta = res["side_effect_auc"] - baseline["side_effect_auc"]
                            post_delta = baseline["post_action_risk_auc"] - res["post_action_risk_auc"]
                            terrain_delta = res["terrain_coeff_persistence"] - baseline["terrain_coeff_persistence"]
                            net = (
                                auc_delta
                                + cfg.post_action_weight * post_delta
                                + gain_delta
                                + cfg.crash_cost_weight * crash_delta
                                + cfg.irreversibility_weight * irreversible_delta
                                + cfg.terrain_persistence_weight * terrain_delta
                                - cfg.side_effect_weight * side_delta
                            )
                            ratio = side_delta / crash_delta if crash_delta > 1e-9 else 999.0
                            net_per_side = net / side_delta if side_delta > 1e-9 else 0.0
                            positive = bool(method != "no_op" and net > 0.0 and crash_delta > 0.0 and auc_delta > 0.0 and ratio < 2.5)
                            row = {
                                "task2_8h_version": TASK2_8H_VERSION,
                                "task2_8h_contract": TASK2_8H_CONTRACT,
                                "validation_only": True,
                                "runtime_policy_input": False,
                                "action_frame_created": False,
                                "actionmodule_called": False,
                                "world_runtime_called": False,
                                "canonical_write_performed": False,
                                "upper_pressure_connected": False,
                                "exploration_axis_connected": False,
                                "synthetic_dynamics_only": True,
                                "action_method_comparison": True,
                                "risk_dynamics_type": spec.dynamics_type,
                                "risk_dynamics_ja": spec.dynamics_ja,
                                "seed": int(seed),
                                "horizon": int(cfg.horizon),
                                "initial_risk_level": float(initial_risk),
                                "crash_threshold": float(crash_threshold),
                                "method": method,
                                "method_ja": METHOD_JA[method],
                                "terrain_actions": ";".join(("none",) if method == "no_op" else actions),
                                "terrain_actions_ja": "なし" if method == "no_op" else _action_names_ja(actions),
                                "strength_band": strength_band,
                                "strength_value": float(strength_value),
                                "duration_band": duration_band,
                                "duration_steps": int(duration_steps),
                                "timing_band": timing_band,
                                "start_step": int(start_step),
                                "end_step": int(start_step) + int(duration_steps),
                                **res,
                                "long_term_net_benefit": float(net),
                                "risk_auc_delta_vs_no_op": float(auc_delta),
                                "crash_cost_delta_vs_no_op": float(crash_delta),
                                "irreversibility_delta_vs_no_op": float(irreversible_delta),
                                "gain_auc_delta_vs_no_op": float(gain_delta),
                                "side_effect_delta_vs_no_op": float(side_delta),
                                "side_effect_per_crash_reduction": float(ratio),
                                "net_per_side_effect": float(net_per_side),
                                "positive_side_effect_reduced_condition": positive,
                            }
                            row["improvement_class"] = _classify(row)
                            rows.append(row)
    out = pd.DataFrame(rows)
    return out[REQUIRED_TASK2_8H_COLUMNS]


def summarize_side_effect_reduction_methods(table: pd.DataFrame) -> dict:
    if table is None or table.empty:
        return {"rows": 0}
    positive = table[table["positive_side_effect_reduced_condition"].astype(bool)].copy()
    by_method = table.groupby("method").agg(
        rows=("method", "size"),
        positive_rows=("positive_side_effect_reduced_condition", lambda s: int(pd.Series(s).astype(bool).sum())),
        mean_net=("long_term_net_benefit", "mean"),
        mean_crash_delta=("crash_cost_delta_vs_no_op", "mean"),
        mean_side_delta=("side_effect_delta_vs_no_op", "mean"),
        mean_side_per_crash=("side_effect_per_crash_reduction", lambda s: float(pd.Series(s)[pd.Series(s) < 900.0].mean()) if bool((pd.Series(s) < 900.0).any()) else 999.0),
        mean_active_steps=("actual_active_steps", "mean"),
    ).reset_index()
    best = positive.sort_values("long_term_net_benefit", ascending=False).head(1).iloc[0].to_dict() if not positive.empty else {}
    return {
        "rows": int(len(table)),
        "methods": sorted(table["method"].astype(str).unique().tolist()),
        "positive_side_effect_reduced_rows": int(len(positive)),
        "best_positive_method": str(best.get("method", "none")),
        "best_positive_dynamics": str(best.get("risk_dynamics_type", "none")),
        "best_positive_strength_band": str(best.get("strength_band", "none")),
        "best_positive_duration_band": str(best.get("duration_band", "none")),
        "best_positive_timing_band": str(best.get("timing_band", "none")),
        "best_positive_net": float(best.get("long_term_net_benefit", 0.0)) if best else 0.0,
        "by_method": by_method.to_dict(orient="records"),
    }


def validate_side_effect_reduction_methods(table: pd.DataFrame) -> list[str]:
    errors = []
    if table is None or table.empty:
        return ["task2_8h_table_empty"]
    missing = sorted(set(REQUIRED_TASK2_8H_COLUMNS) - set(table.columns))
    if missing:
        return ["task2_8h_required_columns_missing:" + ",".join(missing)]
    for field in [
        "runtime_policy_input",
        "action_frame_created",
        "actionmodule_called",
        "world_runtime_called",
        "canonical_write_performed",
        "upper_pressure_connected",
        "exploration_axis_connected",
    ]:
        if bool(table[field].astype(bool).any()):
            errors.append(f"task2_8h_forbidden_true:{field}")
    for field in ["validation_only", "synthetic_dynamics_only", "action_method_comparison"]:
        if not bool(table[field].astype(bool).all()):
            errors.append(f"task2_8h_required_true_not_all:{field}")
    if int(table["method"].nunique()) < len(METHODS):
        errors.append("task2_8h_missing_methods")
    positive = table[table["positive_side_effect_reduced_condition"].astype(bool)]
    if positive.empty:
        errors.append("task2_8h_no_positive_side_effect_reduced_condition")
    if not positive.empty and not bool((positive["crash_cost_delta_vs_no_op"] > 0.0).all()):
        errors.append("task2_8h_positive_without_crash_reduction")
    side_sum = (
        table["short_gain_loss_auc"]
        + table["liquidity_loss_auc"]
        + table["overcooling_loss_auc"]
        + table["mismatch_cost_auc"]
        + table["complexity_cost_auc"]
    )
    if bool((side_sum - table["side_effect_auc"]).abs().gt(1e-9).any()):
        errors.append("task2_8h_side_effect_decomposition_mismatch")
    by_method = table.groupby("method")["side_effect_delta_vs_no_op"].mean().to_dict()
    if by_method.get("wall_global", 0.0) <= by_method.get("direction_selective", 999.0):
        errors.append("task2_8h_direction_selective_not_lower_side_than_wall")
    if by_method.get("wall_global", 0.0) <= by_method.get("selective_state_thin", 999.0):
        errors.append("task2_8h_selective_state_thin_not_lower_side_than_wall")
    for col in ["risk_peak", "risk_auc", "gain_auc", "side_effect_auc", "crash_cost_auc", "irreversibility_auc"]:
        vals = pd.to_numeric(table[col], errors="coerce")
        if bool(vals.isna().any() or (vals < 0.0).any()):
            errors.append(f"task2_8h_invalid_nonnegative:{col}")
    return errors


def build_and_validate_side_effect_reduction_methods_table() -> tuple[pd.DataFrame, list[str], dict]:
    table = build_side_effect_reduction_methods_table()
    errors = validate_side_effect_reduction_methods(table)
    summary = summarize_side_effect_reduction_methods(table)
    return table, errors, summary
