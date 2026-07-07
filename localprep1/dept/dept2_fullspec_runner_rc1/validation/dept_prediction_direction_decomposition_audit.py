"""Prediction Direction Decomposition Audit.

Measurement-only audit for Task2-8j-24e.

This audit does not change prediction behavior and does not define performance
pass/fail thresholds. It exposes the internal and observed components behind
prediction direction errors:

- neutral buffer distance: how small the observed movement is,
- shrink equilibrium measure: fixed/shrinking movement,
- bias concentration measure: uneven concentration / skew proxy,
- divergence release measure: loosening / expansion movement,
- predicted direction strengths and margin.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict
from math import sqrt

import pandas as pd

from dept2_fullspec_runner_rc1.modules.dept_prediction_module import DEPTPredictionModule
from dept2_fullspec_runner_rc1.validation.dept_prediction_objective_challenge_validation import (
    HORIZONS,
    NOISE_LEVELS,
    OBJECTIVE_PATTERNS,
    build_objective_trace_series,
    score_public_dynamics_independent,
)
from dept2_fullspec_runner_rc1.validation.dept_prediction_v2_validation_bench import (
    FORBIDDEN_PREDICTION_INPUT_KEYS,
    build_placeholder_gk,
    build_public_ot_tables,
    project_public_trace_from_history,
)


@dataclass(frozen=True)
class PredictionDirectionDecompositionAuditConfig:
    seeds: tuple[int, ...] = (101, 202, 303, 404, 505)
    patterns: tuple[str, ...] = tuple(OBJECTIVE_PATTERNS)
    noise_levels: tuple[float, ...] = tuple(NOISE_LEVELS)
    horizons: tuple[int, ...] = tuple(HORIZONS)
    history_steps: int = 6
    source_steps: int = 5


ENTITY_METRICS = [
    "activity",
    "volatility",
    "uncertainty",
    "exploration",
    "relation_lock",
    "reversibility",
    "entropy",
]
RELATION_METRICS = ["relation_strength", "relation_rigidity", "flow"]


def _num(df: pd.DataFrame, col: str) -> pd.Series:
    if df is None or df.empty or col not in df.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(df[col], errors="coerce").fillna(0.0)


def _mean_delta(current: pd.DataFrame, future: pd.DataFrame, key_cols: list[str], metric: str, horizon: int) -> float:
    if current.empty or future.empty or metric not in current.columns or metric not in future.columns:
        return 0.0
    cur = current.set_index(key_cols)
    fut = future.set_index(key_cols)
    common = cur.index.intersection(fut.index)
    if len(common) == 0:
        return 0.0
    delta = _num(fut.loc[common].reset_index(), metric) - _num(cur.loc[common].reset_index(), metric)
    return float(delta.mean() / max(1, int(horizon)))


def _std_delta(current: pd.DataFrame, future: pd.DataFrame, metric: str) -> float:
    if current.empty or future.empty or metric not in current.columns or metric not in future.columns:
        return 0.0
    return float(_num(future, metric).std(ddof=0) - _num(current, metric).std(ddof=0))


def _pos(value: float) -> float:
    return max(0.0, float(value))


def _mean(values: list[float]) -> float:
    return float(sum(values) / max(1, len(values)))


def _rms(values: list[float]) -> float:
    return float(sqrt(sum(float(v) * float(v) for v in values) / max(1, len(values))))


def _trace_measurements(current: Dict[str, pd.DataFrame], future: Dict[str, pd.DataFrame], horizon: int) -> dict[str, float]:
    e_df = current.get("entity_trace", pd.DataFrame())
    e_future = future.get("entity_trace", pd.DataFrame())
    r_df = current.get("relation_trace", pd.DataFrame())
    r_future = future.get("relation_trace", pd.DataFrame())

    e_delta = {f"entity_{m}_delta_per_step": _mean_delta(e_df, e_future, ["entity_id"], m, horizon) for m in ENTITY_METRICS}
    r_delta = {f"relation_{m}_delta_per_step": _mean_delta(r_df, r_future, ["source", "target"], m, horizon) for m in RELATION_METRICS}
    e_std = {f"entity_{m}_spread_delta": _std_delta(e_df, e_future, m) for m in ENTITY_METRICS}
    r_std = {f"relation_{m}_spread_delta": _std_delta(r_df, r_future, m) for m in RELATION_METRICS}

    activity = e_delta["entity_activity_delta_per_step"]
    volatility = e_delta["entity_volatility_delta_per_step"]
    uncertainty = e_delta["entity_uncertainty_delta_per_step"]
    exploration = e_delta["entity_exploration_delta_per_step"]
    lock = e_delta["entity_relation_lock_delta_per_step"]
    reversibility = e_delta["entity_reversibility_delta_per_step"]
    entropy = e_delta["entity_entropy_delta_per_step"]
    rigidity = r_delta["relation_relation_rigidity_delta_per_step"]
    flow = r_delta["relation_flow_delta_per_step"]

    neutral_buffer_distance_measure = _rms(list(e_delta.values()) + list(r_delta.values()))
    shrink_equilibrium_measure = _mean([
        _pos(-activity),
        _pos(-exploration),
        _pos(-reversibility),
        _pos(-entropy),
        _pos(lock),
        _pos(rigidity),
        _pos(-flow),
    ])
    bias_concentration_measure = _mean([
        _pos(e_std["entity_exploration_spread_delta"]),
        _pos(e_std["entity_entropy_spread_delta"]),
        _pos(e_std["entity_relation_lock_spread_delta"]),
        _pos(r_std["relation_relation_rigidity_spread_delta"]),
        _pos(-r_std["relation_flow_spread_delta"]),
    ])
    divergence_release_measure = _mean([
        _pos(volatility),
        _pos(uncertainty),
        _pos(activity),
        _pos(entropy),
        _pos(exploration),
        _pos(flow),
        _pos(-rigidity),
        _pos(-lock),
    ])
    overconvergence_fixation_overlap_measure = min(shrink_equilibrium_measure, bias_concentration_measure)

    out = {}
    out.update(e_delta)
    out.update(r_delta)
    out.update(e_std)
    out.update(r_std)
    out.update({
        "neutral_buffer_distance_measure": neutral_buffer_distance_measure,
        "shrink_equilibrium_measure": shrink_equilibrium_measure,
        "bias_concentration_measure": bias_concentration_measure,
        "divergence_release_measure": divergence_release_measure,
        "overconvergence_fixation_overlap_measure": overconvergence_fixation_overlap_measure,
    })
    return out


def _prediction_outputs(history: list[Dict[str, pd.DataFrame]], horizon: int, seed: int, pattern: str) -> dict[str, object]:
    current = history[-1]
    projected = project_public_trace_from_history(history, horizon)
    ot_native, ot_action_view, residual = build_public_ot_tables(current)
    gt, kt = build_placeholder_gk(current)
    outputs = DEPTPredictionModule().build(
        world_trace_before=current,
        baseline_trace_after=projected,
        gt=gt,
        kt=kt,
        ot_native=ot_native,
        ot_action_view=ot_action_view,
        residual_noise_log=residual,
        loop_step=int(current["entity_trace"]["t"].iloc[0]),
        seed=int(seed),
        scenario=f"direction_audit_{pattern}",
    )
    dyn = outputs["dept_prediction_dynamics_projection"].iloc[0]
    return {
        "predicted_direction": str(dyn["predicted_dynamics_direction"]),
        "predicted_strength": float(dyn["predicted_dynamics_strength"]),
        "predicted_direction_margin": float(dyn["predicted_direction_margin"]),
        "predicted_delta_intensity": float(dyn["projected_delta_intensity"]),
        "predicted_overconvergence_strength": float(dyn["overconvergence_direction_strength"]),
        "predicted_fixation_strength": float(dyn["fixation_direction_strength"]),
        "predicted_divergence_strength": float(dyn["divergence_direction_strength"]),
    }


def run_direction_decomposition_case(
    pattern: str,
    seed: int,
    noise_level: float,
    cfg: PredictionDirectionDecompositionAuditConfig,
) -> pd.DataFrame:
    total_steps = cfg.history_steps + cfg.source_steps + max(cfg.horizons) + 1
    traces = build_objective_trace_series(pattern, seed, noise_level, total_steps)
    rows: list[dict[str, object]] = []
    for source_index in range(cfg.history_steps, cfg.history_steps + cfg.source_steps):
        history = traces[: source_index + 1]
        current = history[-1]
        source_t = int(current["entity_trace"]["t"].iloc[0])
        for horizon in cfg.horizons:
            future = traces[source_index + int(horizon)]
            actual_direction, actual_strength, actual_scores = score_public_dynamics_independent(current, future, int(horizon))
            predicted = _prediction_outputs(history, int(horizon), seed, pattern)
            measurements = _trace_measurements(current, future, int(horizon))
            rows.append({
                "seed": int(seed),
                "pattern": str(pattern),
                "noise_level": float(noise_level),
                "source_world_t": source_t,
                "horizon": int(horizon),
                "actual_direction": str(actual_direction),
                "actual_strength": float(actual_strength),
                "actual_overconvergence_score": float(actual_scores.get("overconvergence", 0.0)),
                "actual_fixation_score": float(actual_scores.get("fixation", 0.0)),
                "actual_divergence_score": float(actual_scores.get("divergence", 0.0)),
                **predicted,
                "direction_match": str(predicted["predicted_direction"]) == str(actual_direction),
                "strength_abs_error": abs(float(predicted["predicted_strength"]) - float(actual_strength)),
                **measurements,
                "future_usage": "heldout_answer_key_only",
                "forbidden_v2_trace_keys_passed_to_prediction": False,
            })
    return pd.DataFrame(rows)


def _group_summary(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return pd.DataFrame()
    return rows.groupby(["actual_direction", "predicted_direction", "pattern", "noise_level", "horizon"], as_index=False).agg(
        rows=("direction_match", "size"),
        direction_match_rate=("direction_match", "mean"),
        mean_strength_abs_error=("strength_abs_error", "mean"),
        max_strength_abs_error=("strength_abs_error", "max"),
        mean_neutral_buffer_distance=("neutral_buffer_distance_measure", "mean"),
        mean_shrink_equilibrium_measure=("shrink_equilibrium_measure", "mean"),
        mean_bias_concentration_measure=("bias_concentration_measure", "mean"),
        mean_divergence_release_measure=("divergence_release_measure", "mean"),
        mean_predicted_overconvergence_strength=("predicted_overconvergence_strength", "mean"),
        mean_predicted_fixation_strength=("predicted_fixation_strength", "mean"),
        mean_predicted_divergence_strength=("predicted_divergence_strength", "mean"),
        mean_predicted_direction_margin=("predicted_direction_margin", "mean"),
    )


def _direction_confusion(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return pd.DataFrame()
    return rows.groupby(["actual_direction", "predicted_direction"], as_index=False).agg(
        rows=("direction_match", "size"),
        mean_strength_abs_error=("strength_abs_error", "mean"),
        max_strength_abs_error=("strength_abs_error", "max"),
        mean_neutral_buffer_distance=("neutral_buffer_distance_measure", "mean"),
        mean_shrink_equilibrium_measure=("shrink_equilibrium_measure", "mean"),
        mean_bias_concentration_measure=("bias_concentration_measure", "mean"),
        mean_divergence_release_measure=("divergence_release_measure", "mean"),
    )


def _component_summary(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return pd.DataFrame()
    return rows.groupby(["actual_direction", "pattern"], as_index=False).agg(
        rows=("direction_match", "size"),
        direction_match_rate=("direction_match", "mean"),
        mean_predicted_overconvergence_strength=("predicted_overconvergence_strength", "mean"),
        mean_predicted_fixation_strength=("predicted_fixation_strength", "mean"),
        mean_predicted_divergence_strength=("predicted_divergence_strength", "mean"),
        mean_neutral_buffer_distance=("neutral_buffer_distance_measure", "mean"),
        mean_shrink_equilibrium_measure=("shrink_equilibrium_measure", "mean"),
        mean_bias_concentration_measure=("bias_concentration_measure", "mean"),
        mean_divergence_release_measure=("divergence_release_measure", "mean"),
        mean_relation_lock_delta=("entity_relation_lock_delta_per_step", "mean"),
        mean_relation_rigidity_delta=("relation_relation_rigidity_delta_per_step", "mean"),
        mean_flow_delta=("relation_flow_delta_per_step", "mean"),
        mean_exploration_delta=("entity_exploration_delta_per_step", "mean"),
        mean_uncertainty_delta=("entity_uncertainty_delta_per_step", "mean"),
        mean_volatility_delta=("entity_volatility_delta_per_step", "mean"),
    )


def _boundary(rows: pd.DataFrame, cfg: PredictionDirectionDecompositionAuditConfig) -> pd.DataFrame:
    forbidden = bool(rows["forbidden_v2_trace_keys_passed_to_prediction"].any()) if not rows.empty else True
    return pd.DataFrame([{
        "validation_name": "Task2-8j-24e Prediction Direction Decomposition Audit",
        "future_usage": "heldout_answer_key_only",
        "forbidden_prediction_input_keys": ",".join(sorted(FORBIDDEN_PREDICTION_INPUT_KEYS)),
        "forbidden_v2_trace_keys_passed_to_prediction": forbidden,
        "boundary_violation_detected": forbidden or rows.empty,
        "rows_observed": int(len(rows)),
        "n_seeds": len(cfg.seeds),
        "n_patterns": len(cfg.patterns),
        "n_noise_levels": len(cfg.noise_levels),
        "n_horizons": len(cfg.horizons),
    }])


def run_prediction_direction_decomposition_audit(
    cfg: PredictionDirectionDecompositionAuditConfig | None = None,
) -> dict[str, pd.DataFrame]:
    cfg = cfg or PredictionDirectionDecompositionAuditConfig()
    parts: list[pd.DataFrame] = []
    for seed in cfg.seeds:
        for pattern in cfg.patterns:
            for noise_level in cfg.noise_levels:
                parts.append(run_direction_decomposition_case(pattern, int(seed), float(noise_level), cfg))
    rows = pd.concat([p for p in parts if p is not None and not p.empty], ignore_index=True) if parts else pd.DataFrame()
    return {
        "prediction_direction_decomposition_rows": rows,
        "prediction_direction_decomposition_group_summary": _group_summary(rows),
        "prediction_direction_decomposition_confusion": _direction_confusion(rows),
        "prediction_direction_decomposition_component_summary": _component_summary(rows),
        "prediction_direction_decomposition_boundary": _boundary(rows, cfg),
    }
