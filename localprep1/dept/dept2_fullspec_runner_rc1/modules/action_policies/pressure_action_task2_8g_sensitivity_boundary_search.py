"""Task 2-8g: high-risk boundary / strength-duration / prediction-accuracy sensitivity search RC1.

Purpose:
    Explore the boundary conditions under which terrain reshaping becomes
    positive as tail-risk insurance:
      - initial risk level boundary
      - crash threshold boundary
      - strength and duration boundary
      - timing / lead-time boundary
      - cause-prediction accuracy boundary
      - side-effect scaling with strength and duration

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

from .pressure_action_task2_8f_high_risk_crash_cost_sandbox import (
    ACTION_JA,
    DYNAMICS_SPECS,
    HighRiskDynamicsSpec,
)

TASK2_8G_VERSION = "sensitivity_boundary_search_rc1"
TASK2_8G_CONTRACT = "Task2_8g_high_risk_boundary_strength_duration_prediction_accuracy_sensitivity__no_upper_pressure__no_exploration_escape"
HORIZON = 120
SEEDS = (11, 37)

INITIAL_RISK_LEVELS = (0.35, 0.45, 0.55, 0.65, 0.75, 0.85)
CRASH_THRESHOLDS = (0.70, 0.76, 0.82, 0.88)
PREDICTION_ACCURACIES = (1.00, 0.80, 0.60, 0.40)
STRENGTH_BANDS = {"low": 0.18, "mid": 0.30, "high": 0.42, "excessive": 0.64}
DURATION_BANDS = {"short": 14, "mid": 28, "long": 44}
TIMING_BANDS = {"early": 8, "on_time": 22, "late": 52}

POLICIES = (
    "no_op",
    "single_predicted",
    "pair_predicted",
    "all_cover",
)

REQUIRED_TASK2_8G_COLUMNS = [
    "task2_8g_version",
    "task2_8g_contract",
    "validation_only",
    "runtime_policy_input",
    "action_frame_created",
    "actionmodule_called",
    "world_runtime_called",
    "canonical_write_performed",
    "upper_pressure_connected",
    "exploration_escape_connected",
    "synthetic_dynamics_only",
    "sensitivity_search",
    "risk_dynamics_type",
    "risk_dynamics_ja",
    "seed",
    "horizon",
    "initial_risk_level",
    "crash_threshold",
    "policy",
    "prediction_required",
    "prediction_accuracy",
    "prediction_correct",
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
    "regime_class",
    "improvement_class",
]


@dataclass(frozen=True)
class SensitivityConfig:
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


def _action_names_ja(actions: tuple[str, ...]) -> str:
    return ";".join(ACTION_JA.get(a, a) for a in actions)


def _stable_score(*items: object) -> float:
    s = "|".join(str(x) for x in items)
    acc = 0
    for i, ch in enumerate(s):
        acc += (i + 1) * ord(ch)
    return (acc % 1000) / 1000.0


def _wrong_pair(spec: HighRiskDynamicsSpec) -> tuple[str, ...]:
    all_actions = ("input_sensitivity_reduction", "amplification_loop_damping", "recovery_basin_formation")
    wrong = list(spec.wrong_single)
    for action in all_actions:
        if action not in spec.recommended_pair and action not in wrong:
            wrong.append(action)
            break
    return tuple(wrong[:2])


def _policy_actions(spec: HighRiskDynamicsSpec, policy: str, prediction_correct: bool) -> tuple[str, ...]:
    if policy == "no_op":
        return ("none",)
    if policy == "all_cover":
        return ("input_sensitivity_reduction", "amplification_loop_damping", "recovery_basin_formation")
    if policy == "single_predicted":
        return spec.recommended_single if prediction_correct else spec.wrong_single
    if policy == "pair_predicted":
        return spec.recommended_pair if prediction_correct else _wrong_pair(spec)
    return ("none",)


def _policy_matches(spec: HighRiskDynamicsSpec, policy: str, actions: tuple[str, ...], prediction_correct: bool) -> bool:
    if policy == "no_op":
        return False
    if policy == "all_cover":
        return bool(set(actions) & set(spec.recommended_pair))
    return bool(prediction_correct and set(actions) & (set(spec.recommended_single) | set(spec.recommended_pair)))


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
    precision = 1.0 if matched else 0.34
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
    short_gain_loss = (0.004 + 0.010 * strength * strength) * (1.0 + 0.25 * ("amplification_loop_damping" in actions))
    liquidity_loss = (0.003 + 0.008 * strength) * (1.0 + 0.35 * ("input_sensitivity_reduction" in actions))
    overcooling_loss = max(0.0, total_change - 0.018) * (1.25 + 0.30 * n_actions)
    mismatch_cost = 0.0 if matched else 0.020 + 0.024 * strength
    complexity_cost = 0.004 * max(0, n_actions - 1) * strength
    if matched:
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
    initial_risk: float,
    crash_threshold: float,
    policy: str,
    actions: tuple[str, ...],
    matched: bool,
    strength: float,
    duration: int,
    start_step: int,
    seed: int,
    cfg: SensitivityConfig,
) -> dict:
    risk = _clip01(initial_risk)
    gain = spec.gain_base
    input_sensitivity = spec.input_sensitivity
    amplification = spec.amplification
    recovery_margin = spec.recovery_margin
    initial_coeffs = (input_sensitivity, amplification, recovery_margin)
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
        active = policy != "no_op" and start_step <= step < end_step
        side = {"short_gain_loss": 0.0, "liquidity_loss": 0.0, "overcooling_loss": 0.0, "mismatch_cost": 0.0, "complexity_cost": 0.0}
        if active:
            input_sensitivity, amplification, recovery_margin, side = _apply_actions(
                actions, strength, matched, input_sensitivity, amplification, recovery_margin
            )

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


def _classify(row: dict) -> str:
    if row["policy"] == "no_op":
        if row["crash_cost_auc"] <= 0.0:
            return "baseline_self_recoverable"
        return "baseline_tail_loss"
    if row["positive_tail_insurance_condition"]:
        if row["policy"] == "all_cover":
            return "positive_without_cause_precision_but_costly"
        return "positive_with_prediction"
    if row["initial_risk_level"] < 0.55 and row["long_term_net_benefit"] <= 0.0:
        return "self_recoverable_premium_loses"
    if row["prediction_required"] and not row["prediction_correct"] and row["long_term_net_benefit"] <= 0.0:
        return "prediction_miss_loses"
    if row["timing_band"] == "late" and row["long_term_net_benefit"] <= 0.0:
        return "late_action_loses"
    if row["side_effect_delta_vs_no_op"] > 0.18 and row["long_term_net_benefit"] <= 0.0:
        return "side_effect_loses"
    return "mixed_or_boundary"


def _regime_class(no_op_crash_cost: float, initial_risk: float, positive: bool) -> str:
    if no_op_crash_cost <= 0.0 and initial_risk <= 0.55:
        return "放置可能領域"
    if positive:
        return "保険有効領域"
    if initial_risk >= 0.80:
        return "介入困難領域"
    return "境界領域"


def build_sensitivity_boundary_search_table(cfg: SensitivityConfig = SensitivityConfig()) -> pd.DataFrame:
    rows = []
    for spec in DYNAMICS_SPECS:
        for initial_risk in INITIAL_RISK_LEVELS:
            for crash_threshold in CRASH_THRESHOLDS:
                for seed in SEEDS:
                    baseline_actions = ("none",)
                    baseline = _simulate(
                        spec, initial_risk, crash_threshold, "no_op", baseline_actions, False, 0.0, 0, 0, seed, cfg
                    )
                    base_row = {
                        "task2_8g_version": TASK2_8G_VERSION,
                        "task2_8g_contract": TASK2_8G_CONTRACT,
                        "validation_only": True,
                        "runtime_policy_input": False,
                        "action_frame_created": False,
                        "actionmodule_called": False,
                        "world_runtime_called": False,
                        "canonical_write_performed": False,
                        "upper_pressure_connected": False,
                        "exploration_escape_connected": False,
                        "synthetic_dynamics_only": True,
                        "sensitivity_search": True,
                        "risk_dynamics_type": spec.dynamics_type,
                        "risk_dynamics_ja": spec.dynamics_ja,
                        "seed": int(seed),
                        "horizon": int(cfg.horizon),
                        "initial_risk_level": float(initial_risk),
                        "crash_threshold": float(crash_threshold),
                        "policy": "no_op",
                        "prediction_required": False,
                        "prediction_accuracy": -1.0,
                        "prediction_correct": False,
                        "terrain_actions": "none",
                        "terrain_actions_ja": "なし",
                        "action_matches_dynamics": False,
                        "strength_band": "none",
                        "strength_value": 0.0,
                        "duration_band": "none",
                        "duration_steps": 0,
                        "timing_band": "none",
                        "start_step": 0,
                        **baseline,
                        "long_term_net_benefit": 0.0,
                        "risk_peak_delta_vs_no_op": 0.0,
                        "risk_auc_delta_vs_no_op": 0.0,
                        "post_action_auc_delta_vs_no_op": 0.0,
                        "gain_auc_delta_vs_no_op": 0.0,
                        "crash_cost_delta_vs_no_op": 0.0,
                        "irreversibility_delta_vs_no_op": 0.0,
                        "side_effect_delta_vs_no_op": 0.0,
                        "terrain_persistence_delta_vs_no_op": 0.0,
                        "positive_tail_insurance_condition": False,
                        "regime_class": _regime_class(baseline["crash_cost_auc"], initial_risk, False),
                    }
                    base_row["improvement_class"] = _classify(base_row)
                    rows.append(base_row)

                    for policy in ("single_predicted", "pair_predicted", "all_cover"):
                        prediction_required = policy in {"single_predicted", "pair_predicted"}
                        accuracy_values = PREDICTION_ACCURACIES if prediction_required else (1.0,)
                        for prediction_accuracy in accuracy_values:
                            for strength_band, strength_value in STRENGTH_BANDS.items():
                                for duration_band, duration_steps in DURATION_BANDS.items():
                                    for timing_band, start_step in TIMING_BANDS.items():
                                        score = _stable_score(spec.dynamics_type, initial_risk, crash_threshold, seed, policy, prediction_accuracy, strength_band, duration_band, timing_band)
                                        prediction_correct = bool((not prediction_required) or score < prediction_accuracy)
                                        actions = _policy_actions(spec, policy, prediction_correct)
                                        matched = _policy_matches(spec, policy, actions, prediction_correct)
                                        res = _simulate(
                                            spec, initial_risk, crash_threshold, policy, actions, matched,
                                            float(strength_value), int(duration_steps), int(start_step), seed, cfg
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
                                            net > 0.0
                                            and auc_delta > 0.0
                                            and crash_delta > 0.0
                                            and irreversible_delta >= 0.0
                                            and matched
                                        )
                                        row = {
                                            "task2_8g_version": TASK2_8G_VERSION,
                                            "task2_8g_contract": TASK2_8G_CONTRACT,
                                            "validation_only": True,
                                            "runtime_policy_input": False,
                                            "action_frame_created": False,
                                            "actionmodule_called": False,
                                            "world_runtime_called": False,
                                            "canonical_write_performed": False,
                                            "upper_pressure_connected": False,
                                            "exploration_escape_connected": False,
                                            "synthetic_dynamics_only": True,
                                            "sensitivity_search": True,
                                            "risk_dynamics_type": spec.dynamics_type,
                                            "risk_dynamics_ja": spec.dynamics_ja,
                                            "seed": int(seed),
                                            "horizon": int(cfg.horizon),
                                            "initial_risk_level": float(initial_risk),
                                            "crash_threshold": float(crash_threshold),
                                            "policy": policy,
                                            "prediction_required": bool(prediction_required),
                                            "prediction_accuracy": float(prediction_accuracy),
                                            "prediction_correct": bool(prediction_correct),
                                            "terrain_actions": ";".join(actions),
                                            "terrain_actions_ja": _action_names_ja(actions),
                                            "action_matches_dynamics": bool(matched),
                                            "strength_band": strength_band,
                                            "strength_value": float(strength_value),
                                            "duration_band": duration_band,
                                            "duration_steps": int(duration_steps),
                                            "timing_band": timing_band,
                                            "start_step": int(start_step),
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
                                            "regime_class": _regime_class(baseline["crash_cost_auc"], initial_risk, positive),
                                        }
                                        row["improvement_class"] = _classify(row)
                                        rows.append(row)
    out = pd.DataFrame(rows)
    return out[REQUIRED_TASK2_8G_COLUMNS]


def build_boundary_summary(table: pd.DataFrame) -> pd.DataFrame:
    if table is None or table.empty:
        return pd.DataFrame()
    positive = table[table["positive_tail_insurance_condition"].astype(bool)].copy()
    if positive.empty:
        return pd.DataFrame()
    grouped = positive.groupby(["risk_dynamics_type", "policy"]).agg(
        break_even_risk_level=("initial_risk_level", "min"),
        easiest_crash_threshold=("crash_threshold", "max"),
        min_prediction_accuracy=("prediction_accuracy", lambda s: float(pd.Series(s)[pd.Series(s) >= 0.0].min()) if bool((pd.Series(s) >= 0.0).any()) else -1.0),
        best_net=("long_term_net_benefit", "max"),
        positive_rows=("positive_tail_insurance_condition", "size"),
        mean_side_effect=("side_effect_delta_vs_no_op", "mean"),
        mean_crash_reduction=("crash_cost_delta_vs_no_op", "mean"),
    ).reset_index()
    return grouped


def summarize_sensitivity_boundary_search(table: pd.DataFrame) -> dict:
    if table is None or table.empty:
        return {"rows": 0}
    positive = table[table["positive_tail_insurance_condition"].astype(bool)].copy()
    boundary = build_boundary_summary(table)
    by_policy = table.groupby("policy").agg(
        rows=("policy", "size"),
        positive_rows=("positive_tail_insurance_condition", lambda s: int(pd.Series(s).astype(bool).sum())),
        mean_net=("long_term_net_benefit", "mean"),
        mean_side=("side_effect_delta_vs_no_op", "mean"),
        mean_crash_reduction=("crash_cost_delta_vs_no_op", "mean"),
    ).reset_index()
    best = positive.sort_values("long_term_net_benefit", ascending=False).head(1).iloc[0].to_dict() if not positive.empty else {}
    return {
        "rows": int(len(table)),
        "risk_dynamics_types": sorted(table["risk_dynamics_type"].astype(str).unique().tolist()),
        "initial_risk_levels": sorted(table["initial_risk_level"].astype(float).unique().tolist()),
        "crash_thresholds": sorted(table["crash_threshold"].astype(float).unique().tolist()),
        "policies": sorted(table["policy"].astype(str).unique().tolist()),
        "positive_tail_insurance_rows": int(len(positive)),
        "best_positive_dynamics": str(best.get("risk_dynamics_type", "none")),
        "best_positive_policy": str(best.get("policy", "none")),
        "best_positive_actions": str(best.get("terrain_actions", "none")),
        "best_positive_initial_risk": float(best.get("initial_risk_level", -1.0)) if best else -1.0,
        "best_positive_crash_threshold": float(best.get("crash_threshold", -1.0)) if best else -1.0,
        "best_positive_prediction_accuracy": float(best.get("prediction_accuracy", -1.0)) if best else -1.0,
        "best_positive_strength_band": str(best.get("strength_band", "none")),
        "best_positive_duration_band": str(best.get("duration_band", "none")),
        "best_positive_timing_band": str(best.get("timing_band", "none")),
        "best_positive_net": float(best.get("long_term_net_benefit", 0.0)) if best else 0.0,
        "boundary_summary": boundary.to_dict(orient="records"),
        "by_policy": by_policy.to_dict(orient="records"),
    }


def validate_sensitivity_boundary_search(table: pd.DataFrame) -> list[str]:
    errors = []
    if table is None or table.empty:
        return ["task2_8g_table_empty"]
    missing = sorted(set(REQUIRED_TASK2_8G_COLUMNS) - set(table.columns))
    if missing:
        return ["task2_8g_required_columns_missing:" + ",".join(missing)]
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
            errors.append(f"task2_8g_forbidden_true:{field}")
    for field in ["validation_only", "synthetic_dynamics_only", "sensitivity_search"]:
        if not bool(table[field].astype(bool).all()):
            errors.append(f"task2_8g_required_true_not_all:{field}")
    if int(table["risk_dynamics_type"].nunique()) < 4:
        errors.append("task2_8g_missing_risk_dynamics_types")
    if set(table["initial_risk_level"].astype(float).unique()) != set(INITIAL_RISK_LEVELS):
        errors.append("task2_8g_initial_risk_levels_missing")
    if set(table["crash_threshold"].astype(float).unique()) != set(CRASH_THRESHOLDS):
        errors.append("task2_8g_crash_thresholds_missing")
    if not bool((table["policy"].astype(str) == "no_op").any()):
        errors.append("task2_8g_no_no_op_rows")
    positive = table[table["positive_tail_insurance_condition"].astype(bool)]
    if positive.empty:
        errors.append("task2_8g_no_positive_tail_insurance_condition")
    if not positive.empty:
        if not bool(positive["action_matches_dynamics"].astype(bool).all()):
            errors.append("task2_8g_positive_contains_unmatched_action")
        if not bool((positive["crash_cost_delta_vs_no_op"] > 0.0).all()):
            errors.append("task2_8g_positive_without_crash_reduction")
    side_sum = (
        table["short_gain_loss_auc"]
        + table["liquidity_loss_auc"]
        + table["overcooling_loss_auc"]
        + table["mismatch_cost_auc"]
        + table["complexity_cost_auc"]
    )
    if bool((side_sum - table["side_effect_auc"]).abs().gt(1e-9).any()):
        errors.append("task2_8g_side_effect_decomposition_mismatch")
    for col in ["risk_peak", "risk_auc", "gain_auc", "side_effect_auc", "crash_cost_auc", "irreversibility_auc"]:
        vals = pd.to_numeric(table[col], errors="coerce")
        if bool(vals.isna().any() or (vals < 0.0).any()):
            errors.append(f"task2_8g_invalid_nonnegative:{col}")
    return errors


def build_and_validate_sensitivity_boundary_search_table() -> tuple[pd.DataFrame, list[str], dict]:
    table = build_sensitivity_boundary_search_table()
    errors = validate_sensitivity_boundary_search(table)
    summary = summarize_sensitivity_boundary_search(table)
    return table, errors, summary
