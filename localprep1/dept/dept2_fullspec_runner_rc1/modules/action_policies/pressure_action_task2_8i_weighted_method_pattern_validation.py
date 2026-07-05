"""Task 2-8i: prediction-accuracy / risk-state weighted action-method pattern validation RC1.

Purpose:
    Validate how to weight the three promising method components discovered in
    Task 2-8h:
      - direction selection weight
      - state-dependence weight
      - immediate-release weight

    The experiment asks which weighting pattern is preferable under different
    combinations of prediction accuracy, initial risk level, crash threshold, and
    risk-dynamics type.

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

TASK2_8I_VERSION = "weighted_method_pattern_validation_rc1"
TASK2_8I_CONTRACT = "Task2_8i_prediction_accuracy_risk_state_weighted_method_patterns__no_exploration_axis__no_upper_pressure"
HORIZON = 120
SEEDS = (11, 37)
INITIAL_RISK_LEVELS = (0.35, 0.45, 0.55, 0.65, 0.75)
CRASH_THRESHOLDS = (0.76, 0.82)
PREDICTION_ACCURACIES = (0.40, 0.60, 0.80, 1.00)

REQUIRED_TASK2_8I_COLUMNS = [
    "task2_8i_version",
    "task2_8i_contract",
    "validation_only",
    "runtime_policy_input",
    "action_frame_created",
    "actionmodule_called",
    "world_runtime_called",
    "canonical_write_performed",
    "upper_pressure_connected",
    "exploration_axis_connected",
    "synthetic_dynamics_only",
    "weight_pattern_validation",
    "risk_dynamics_type",
    "risk_dynamics_ja",
    "seed",
    "horizon",
    "initial_risk_level",
    "crash_threshold",
    "prediction_accuracy",
    "prediction_correct",
    "pattern",
    "pattern_ja",
    "direction_weight",
    "state_dependence_weight",
    "release_weight",
    "base_strength",
    "base_duration",
    "terrain_actions",
    "terrain_actions_ja",
    "action_matches_dynamics",
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
    "short_gain_loss_auc",
    "liquidity_loss_auc",
    "overcooling_loss_auc",
    "mismatch_cost_auc",
    "complexity_cost_auc",
    "side_effect_auc",
    "long_term_net_benefit",
    "risk_auc_delta_vs_no_op",
    "post_action_auc_delta_vs_no_op",
    "gain_auc_delta_vs_no_op",
    "crash_cost_delta_vs_no_op",
    "irreversibility_delta_vs_no_op",
    "side_effect_delta_vs_no_op",
    "side_effect_per_crash_reduction",
    "positive_weight_pattern_condition",
    "region_class",
]


@dataclass(frozen=True)
class WeightPatternSpec:
    pattern: str
    pattern_ja: str
    direction_weight: float
    state_dependence_weight: float
    release_weight: float
    base_strength: float
    base_duration: int


WEIGHT_PATTERNS = (
    WeightPatternSpec("safe_thin", "安全薄膜型", 0.25, 0.75, 1.00, 0.28, 20),
    WeightPatternSpec("standard_insurance", "標準保険型", 0.50, 0.75, 0.75, 0.32, 28),
    WeightPatternSpec("direction_heavy", "方向選択重視型", 1.00, 0.50, 0.50, 0.38, 28),
    WeightPatternSpec("state_gate", "状態門番型", 0.50, 1.00, 0.75, 0.32, 28),
    WeightPatternSpec("release_heavy", "即時解除重視型", 0.50, 0.50, 1.00, 0.30, 20),
    WeightPatternSpec("crash_avoidance", "破綻回避型", 1.00, 1.00, 0.25, 0.42, 44),
    WeightPatternSpec("balanced", "均衡型", 0.75, 0.75, 0.75, 0.35, 28),
    WeightPatternSpec("aggressive", "攻め型", 1.00, 0.75, 0.50, 0.42, 36),
)


@dataclass(frozen=True)
class WeightedPatternConfig:
    horizon: int = HORIZON
    side_effect_weight: float = 0.52
    crash_cost_weight: float = 0.90
    irreversibility_weight: float = 0.50
    post_action_weight: float = 0.36
    risk_peak_weight: float = 0.18


def _clip01(x: float) -> float:
    return float(max(0.0, min(1.0, float(x))))


def _noise(seed: int, step: int) -> float:
    return ((((seed * 181 + step * 79) % 1000) / 1000.0) - 0.5) * 0.0011


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


def _actions_for_prediction(spec: HighRiskDynamicsSpec, prediction_correct: bool) -> tuple[str, ...]:
    return spec.recommended_pair if prediction_correct else _wrong_pair(spec)


def _action_matches(spec: HighRiskDynamicsSpec, actions: tuple[str, ...], prediction_correct: bool) -> bool:
    return bool(prediction_correct and set(actions) & set(spec.recommended_pair))


def _action_names_ja(actions: tuple[str, ...]) -> str:
    return ";".join(ACTION_JA.get(a, a) for a in actions)


def _state_gate(spec: HighRiskDynamicsSpec, risk: float, previous_risk: float, pattern: WeightPatternSpec) -> float:
    slope = risk - previous_risk
    risk_excess = max(0.0, risk - spec.transition_threshold)
    slope_signal = max(0.0, slope)
    raw_state = _clip01(0.18 + 3.2 * risk_excess + 58.0 * slope_signal)
    # State-dependence weight mixes always-on baseline with state-triggered gate.
    return (1.0 - pattern.state_dependence_weight) + pattern.state_dependence_weight * raw_state


def _side_effects(
    pattern: WeightPatternSpec,
    actions: tuple[str, ...],
    active_gate: float,
    prediction_correct: bool,
    actual_effect: float,
) -> dict[str, float]:
    if active_gate <= 0.0:
        return {
            "short_gain_loss": 0.0,
            "liquidity_loss": 0.0,
            "overcooling_loss": 0.0,
            "mismatch_cost": 0.0,
            "complexity_cost": 0.0,
        }
    n_actions = len(actions)
    # Direction weight buys risk reduction but also carries side-effect exposure.
    # State-dependence and release reduce exposure mostly through active_gate and
    # active duration, not by erasing the per-step cost entirely.
    precision_scale = 1.0 if prediction_correct else 1.32
    short_gain_loss = (0.0025 + 0.0075 * pattern.base_strength**2) * (0.45 + 0.80 * pattern.direction_weight) * active_gate * precision_scale
    liquidity_loss = (0.0022 + 0.0065 * pattern.base_strength) * (0.40 + 0.75 * pattern.direction_weight) * active_gate * precision_scale
    overcooling_loss = max(0.0, actual_effect - 0.010) * (0.65 + 0.35 * n_actions)
    mismatch_cost = 0.0 if prediction_correct else 0.010 * pattern.direction_weight * active_gate + 0.006 * pattern.base_strength
    complexity_cost = 0.0025 * max(0, n_actions - 1) * pattern.base_strength * active_gate
    return {
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
    pattern: WeightPatternSpec | None,
    actions: tuple[str, ...],
    prediction_correct: bool,
    seed: int,
    cfg: WeightedPatternConfig,
) -> dict:
    risk = _clip01(initial_risk)
    previous_risk = risk
    gain = spec.gain_base
    input_sensitivity = spec.input_sensitivity
    amplification = spec.amplification
    recovery_margin = spec.recovery_margin
    start_step = 8
    duration = 0 if pattern is None else pattern.base_duration
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
        scheduled_active = pattern is not None and start_step <= step < end_step
        if scheduled_active and pattern is not None and pattern.release_weight > 0.0:
            if len(risks) >= 4 and risks[-1] < risks[-2] < risks[-3]:
                release_counter += 1
            else:
                release_counter = 0
            required_improvement_steps = max(1, int(round(4 - 2.5 * pattern.release_weight)))
            if release_counter >= required_improvement_steps:
                released = True
        active = scheduled_active and not released
        gate = _state_gate(spec, risk, previous_risk, pattern) if active and pattern is not None else 0.0
        age = max(0, step - start_step)
        if active and pattern is not None:
            thin_decay = max(0.12, 1.0 - 0.055 * pattern.release_weight * age)
            gate *= thin_decay
        actual_effect = 0.0

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

        if active and pattern is not None and gate > 0.0:
            actual_active_steps += 1
            direction_effect = pattern.base_strength * pattern.direction_weight * gate
            precision = 1.0 if prediction_correct else 0.20
            misfire = 0.0 if prediction_correct else 1.0
            if "input_sensitivity_reduction" in actions:
                input_push *= max(0.30, 1.0 - 0.66 * direction_effect * precision)
                if misfire:
                    recovery_pull *= max(0.82, 1.0 - 0.10 * direction_effect)
            if "amplification_loop_damping" in actions:
                loop_push *= max(0.25, 1.0 - 0.74 * direction_effect * precision)
                if misfire:
                    input_push *= max(0.88, 1.0 - 0.06 * direction_effect)
            if "recovery_basin_formation" in actions:
                recovery_pull *= 1.0 + 0.58 * direction_effect * precision
                if misfire:
                    loop_push *= 1.0 + 0.05 * direction_effect
            actual_effect = direction_effect * len(actions)

        side = _side_effects(pattern, actions, gate, prediction_correct, actual_effect) if pattern is not None else _side_effects(WeightPatternSpec("none", "none", 0, 0, 0, 0, 0), (), 0.0, True, 0.0)
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
        "short_gain_loss_auc": float(short_gain_loss_auc),
        "liquidity_loss_auc": float(liquidity_loss_auc),
        "overcooling_loss_auc": float(overcooling_loss_auc),
        "mismatch_cost_auc": float(mismatch_cost_auc),
        "complexity_cost_auc": float(complexity_cost_auc),
        "side_effect_auc": float(side_effect_auc),
    }


def _region_class(initial_risk: float, prediction_accuracy: float, positive: bool, net: float) -> str:
    if positive and initial_risk <= 0.45 and prediction_accuracy >= 0.80:
        return "early_high_accuracy_opportunity"
    if positive and prediction_accuracy < 0.80:
        return "low_accuracy_only_if_gated"
    if initial_risk >= 0.75 and net <= 0.0:
        return "likely_too_late_or_observe_only"
    if positive:
        return "usable_weight_region"
    return "fallback_or_no_action_region"


def build_weight_pattern_validation_table(cfg: WeightedPatternConfig = WeightedPatternConfig()) -> pd.DataFrame:
    rows = []
    for spec in DYNAMICS_SPECS:
        for initial_risk in INITIAL_RISK_LEVELS:
            for crash_threshold in CRASH_THRESHOLDS:
                for prediction_accuracy in PREDICTION_ACCURACIES:
                    for seed in SEEDS:
                        baseline = _simulate(spec, initial_risk, crash_threshold, None, ("none",), True, seed, cfg)
                        for pattern in WEIGHT_PATTERNS:
                            score = _stable_score(spec.dynamics_type, initial_risk, crash_threshold, prediction_accuracy, seed, pattern.pattern)
                            prediction_correct = bool(score < prediction_accuracy)
                            actions = _actions_for_prediction(spec, prediction_correct)
                            matched = _action_matches(spec, actions, prediction_correct)
                            res = _simulate(spec, initial_risk, crash_threshold, pattern, actions, prediction_correct, seed, cfg)
                            risk_delta = baseline["risk_auc"] - res["risk_auc"]
                            post_delta = baseline["post_action_risk_auc"] - res["post_action_risk_auc"]
                            gain_delta = res["gain_auc"] - baseline["gain_auc"]
                            crash_delta = baseline["crash_cost_auc"] - res["crash_cost_auc"]
                            irreversible_delta = baseline["irreversibility_auc"] - res["irreversibility_auc"]
                            side_delta = res["side_effect_auc"] - baseline["side_effect_auc"]
                            peak_delta = baseline["risk_peak"] - res["risk_peak"]
                            net = (
                                risk_delta
                                + cfg.post_action_weight * post_delta
                                + cfg.risk_peak_weight * peak_delta
                                + gain_delta
                                + cfg.crash_cost_weight * crash_delta
                                + cfg.irreversibility_weight * irreversible_delta
                                - cfg.side_effect_weight * side_delta
                            )
                            ratio = side_delta / crash_delta if crash_delta > 1e-9 else 999.0
                            positive = bool(net > 0.0 and risk_delta > 0.0 and crash_delta > 0.0 and ratio < 12.0)
                            row = {
                                "task2_8i_version": TASK2_8I_VERSION,
                                "task2_8i_contract": TASK2_8I_CONTRACT,
                                "validation_only": True,
                                "runtime_policy_input": False,
                                "action_frame_created": False,
                                "actionmodule_called": False,
                                "world_runtime_called": False,
                                "canonical_write_performed": False,
                                "upper_pressure_connected": False,
                                "exploration_axis_connected": False,
                                "synthetic_dynamics_only": True,
                                "weight_pattern_validation": True,
                                "risk_dynamics_type": spec.dynamics_type,
                                "risk_dynamics_ja": spec.dynamics_ja,
                                "seed": int(seed),
                                "horizon": int(cfg.horizon),
                                "initial_risk_level": float(initial_risk),
                                "crash_threshold": float(crash_threshold),
                                "prediction_accuracy": float(prediction_accuracy),
                                "prediction_correct": bool(prediction_correct),
                                "pattern": pattern.pattern,
                                "pattern_ja": pattern.pattern_ja,
                                "direction_weight": float(pattern.direction_weight),
                                "state_dependence_weight": float(pattern.state_dependence_weight),
                                "release_weight": float(pattern.release_weight),
                                "base_strength": float(pattern.base_strength),
                                "base_duration": int(pattern.base_duration),
                                "terrain_actions": ";".join(actions),
                                "terrain_actions_ja": _action_names_ja(actions),
                                "action_matches_dynamics": bool(matched),
                                **res,
                                "long_term_net_benefit": float(net),
                                "risk_auc_delta_vs_no_op": float(risk_delta),
                                "post_action_auc_delta_vs_no_op": float(post_delta),
                                "gain_auc_delta_vs_no_op": float(gain_delta),
                                "crash_cost_delta_vs_no_op": float(crash_delta),
                                "irreversibility_delta_vs_no_op": float(irreversible_delta),
                                "side_effect_delta_vs_no_op": float(side_delta),
                                "side_effect_per_crash_reduction": float(ratio),
                                "positive_weight_pattern_condition": positive,
                                "region_class": _region_class(initial_risk, prediction_accuracy, positive, net),
                            }
                            rows.append(row)
    out = pd.DataFrame(rows)
    return out[REQUIRED_TASK2_8I_COLUMNS]


def build_pattern_recommendation_table(table: pd.DataFrame) -> pd.DataFrame:
    if table is None or table.empty:
        return pd.DataFrame()
    grouped = table.groupby(["risk_dynamics_type", "initial_risk_level", "prediction_accuracy", "pattern"]).agg(
        mean_net=("long_term_net_benefit", "mean"),
        positive_rate=("positive_weight_pattern_condition", lambda s: float(pd.Series(s).astype(bool).mean())),
        mean_side=("side_effect_delta_vs_no_op", "mean"),
        mean_crash_reduction=("crash_cost_delta_vs_no_op", "mean"),
        mean_side_per_crash=("side_effect_per_crash_reduction", lambda s: float(pd.Series(s)[pd.Series(s) < 900.0].mean()) if bool((pd.Series(s) < 900.0).any()) else 999.0),
    ).reset_index()
    grouped["rank_key"] = grouped["mean_net"] + 0.25 * grouped["positive_rate"] - 0.04 * grouped["mean_side_per_crash"].clip(upper=20)
    best = grouped.sort_values(["risk_dynamics_type", "initial_risk_level", "prediction_accuracy", "rank_key"], ascending=[True, True, True, False])
    best = best.groupby(["risk_dynamics_type", "initial_risk_level", "prediction_accuracy"]).head(1).reset_index(drop=True)
    return best.drop(columns=["rank_key"])


def summarize_weight_pattern_validation(table: pd.DataFrame) -> dict:
    if table is None or table.empty:
        return {"rows": 0}
    positive = table[table["positive_weight_pattern_condition"].astype(bool)].copy()
    by_pattern = table.groupby("pattern").agg(
        rows=("pattern", "size"),
        positive_rows=("positive_weight_pattern_condition", lambda s: int(pd.Series(s).astype(bool).sum())),
        positive_rate=("positive_weight_pattern_condition", lambda s: float(pd.Series(s).astype(bool).mean())),
        mean_net=("long_term_net_benefit", "mean"),
        mean_side=("side_effect_delta_vs_no_op", "mean"),
        mean_crash_reduction=("crash_cost_delta_vs_no_op", "mean"),
        mean_side_per_crash=("side_effect_per_crash_reduction", lambda s: float(pd.Series(s)[pd.Series(s) < 900.0].mean()) if bool((pd.Series(s) < 900.0).any()) else 999.0),
    ).reset_index()
    by_accuracy = table.groupby(["prediction_accuracy", "pattern"]).agg(
        positive_rate=("positive_weight_pattern_condition", lambda s: float(pd.Series(s).astype(bool).mean())),
        mean_net=("long_term_net_benefit", "mean"),
        mean_side=("side_effect_delta_vs_no_op", "mean"),
    ).reset_index()
    best = positive.sort_values("long_term_net_benefit", ascending=False).head(1).iloc[0].to_dict() if not positive.empty else {}
    return {
        "rows": int(len(table)),
        "patterns": sorted(table["pattern"].astype(str).unique().tolist()),
        "prediction_accuracies": sorted(table["prediction_accuracy"].astype(float).unique().tolist()),
        "initial_risk_levels": sorted(table["initial_risk_level"].astype(float).unique().tolist()),
        "positive_weight_pattern_rows": int(len(positive)),
        "best_positive_pattern": str(best.get("pattern", "none")),
        "best_positive_dynamics": str(best.get("risk_dynamics_type", "none")),
        "best_positive_initial_risk": float(best.get("initial_risk_level", -1.0)) if best else -1.0,
        "best_positive_prediction_accuracy": float(best.get("prediction_accuracy", -1.0)) if best else -1.0,
        "best_positive_net": float(best.get("long_term_net_benefit", 0.0)) if best else 0.0,
        "by_pattern": by_pattern.to_dict(orient="records"),
        "by_accuracy": by_accuracy.to_dict(orient="records"),
    }


def validate_weight_pattern_validation(table: pd.DataFrame) -> list[str]:
    errors = []
    if table is None or table.empty:
        return ["task2_8i_table_empty"]
    missing = sorted(set(REQUIRED_TASK2_8I_COLUMNS) - set(table.columns))
    if missing:
        return ["task2_8i_required_columns_missing:" + ",".join(missing)]
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
            errors.append(f"task2_8i_forbidden_true:{field}")
    for field in ["validation_only", "synthetic_dynamics_only", "weight_pattern_validation"]:
        if not bool(table[field].astype(bool).all()):
            errors.append(f"task2_8i_required_true_not_all:{field}")
    if set(table["pattern"].astype(str).unique()) != {p.pattern for p in WEIGHT_PATTERNS}:
        errors.append("task2_8i_missing_weight_patterns")
    if set(table["prediction_accuracy"].astype(float).unique()) != set(PREDICTION_ACCURACIES):
        errors.append("task2_8i_missing_prediction_accuracy_levels")
    positive = table[table["positive_weight_pattern_condition"].astype(bool)]
    if positive.empty:
        errors.append("task2_8i_no_positive_weight_pattern_condition")
    if not positive.empty and not bool((positive["crash_cost_delta_vs_no_op"] > 0.0).all()):
        errors.append("task2_8i_positive_without_crash_reduction")
    side_sum = (
        table["short_gain_loss_auc"]
        + table["liquidity_loss_auc"]
        + table["overcooling_loss_auc"]
        + table["mismatch_cost_auc"]
        + table["complexity_cost_auc"]
    )
    if bool((side_sum - table["side_effect_auc"]).abs().gt(1e-9).any()):
        errors.append("task2_8i_side_effect_decomposition_mismatch")
    # A basic sanity check: direction-heavy should beat safety-thin at high accuracy
    # in average net, while safety/release-heavy should keep lower side effects.
    high_acc = table[table["prediction_accuracy"].astype(float) == 1.0]
    mean_net = high_acc.groupby("pattern")["long_term_net_benefit"].mean().to_dict()
    mean_side = table.groupby("pattern")["side_effect_delta_vs_no_op"].mean().to_dict()
    if mean_net.get("direction_heavy", -999.0) <= mean_net.get("safe_thin", 999.0):
        errors.append("task2_8i_direction_heavy_not_higher_net_than_safe_thin_at_high_accuracy")
    if mean_side.get("safe_thin", 999.0) >= mean_side.get("direction_heavy", -999.0):
        errors.append("task2_8i_safe_thin_not_lower_side_than_direction_heavy")
    for col in ["risk_peak", "risk_auc", "gain_auc", "side_effect_auc", "crash_cost_auc", "irreversibility_auc"]:
        vals = pd.to_numeric(table[col], errors="coerce")
        if bool(vals.isna().any() or (vals < 0.0).any()):
            errors.append(f"task2_8i_invalid_nonnegative:{col}")
    return errors


def build_and_validate_weight_pattern_validation_table() -> tuple[pd.DataFrame, list[str], dict]:
    table = build_weight_pattern_validation_table()
    errors = validate_weight_pattern_validation(table)
    summary = summarize_weight_pattern_validation(table)
    return table, errors, summary
