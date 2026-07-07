"""DEPT prediction validation suite.

This validation is action-free.  It checks two things separately:

1. Activation response accuracy:
   whether the low-cost activation controller responds to target dynamics
   patterns such as overconvergence, fixation, divergence, sudden angle change,
   and sudden intensity change.

2. Projection packaging accuracy:
   whether the prediction module correctly preserves supplied no-action future
   values and deltas over multiple horizons.  This is not yet a full self-
   generated multi-step forecaster; it validates the projection packet layer
   given synthetic no-action future traces.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable

import pandas as pd

from dept2_fullspec_runner_rc1.modules.dept_prediction_activation_module import (
    DEPTPredictionActivationModule,
    PredictionActivationConfig,
)
from dept2_fullspec_runner_rc1.modules.dept_prediction_module import DEPTPredictionModule


PATTERNS = [
    "stable",
    "overconvergence",
    "fixation",
    "divergence",
    "sudden_angle",
    "sudden_intensity",
]
HORIZONS = [1, 2, 3, 5]
ENTITY_IDS = ["E1", "E2", "E3"]


@dataclass(frozen=True)
class PredictionValidationConfig:
    steps: int = 10
    activation_threshold: float = 0.045
    deep_threshold: float = 0.25
    projection_error_tolerance: float = 1e-9


def _base_entity(entity_id: str, t: int) -> dict:
    index = ENTITY_IDS.index(entity_id)
    return {
        "entity_id": entity_id,
        "t": int(t),
        "scenario": "prediction_validation",
        "seed": 101,
        "activity": 0.42 + index * 0.03,
        "volatility": 0.18 + index * 0.02,
        "uncertainty": 0.28 + index * 0.01,
        "exploration": 0.54 - index * 0.02,
        "relation_lock": 0.30 + index * 0.02,
        "coupling": 0.22 + index * 0.03,
        "reversibility": 0.70 - index * 0.03,
        "entropy": 0.62 - index * 0.02,
        "readiness": 0.58,
    }


def _apply_pattern(row: dict, pattern: str, t: int) -> dict:
    out = dict(row)
    slow = 0.018 * t
    fast = 0.22 if t >= 5 else 0.0
    if pattern == "stable":
        return out
    if pattern == "overconvergence":
        out["exploration"] -= slow
        out["entropy"] -= slow
        out["reversibility"] -= slow * 0.8
        out["relation_lock"] += slow
    elif pattern == "fixation":
        out["relation_lock"] += slow
        out["reversibility"] -= slow * 0.7
        out["volatility"] *= 0.9
        out["activity"] -= slow * 0.2
    elif pattern == "divergence":
        out["volatility"] += slow * 1.5
        out["uncertainty"] += slow
        out["activity"] += slow * 0.8
        out["entropy"] += slow * 0.7
    elif pattern == "sudden_angle":
        if t < 5:
            out["exploration"] += 0.012 * t
            out["entropy"] += 0.010 * t
            out["relation_lock"] -= 0.008 * t
        else:
            turn = 0.08 * (t - 4)
            out["exploration"] -= turn
            out["entropy"] -= turn
            out["relation_lock"] += turn
            out["reversibility"] -= turn * 0.5
    elif pattern == "sudden_intensity":
        out["volatility"] += fast
        out["uncertainty"] += fast * 0.7
        out["relation_lock"] += fast * 0.6
        out["reversibility"] -= fast * 0.5
    return {k: (max(0.0, min(1.0, v)) if isinstance(v, float) else v) for k, v in out.items()}


def build_v2_pattern_trace(pattern: str, t: int) -> Dict[str, pd.DataFrame]:
    entity_rows = [_apply_pattern(_base_entity(eid, t), pattern, t) for eid in ENTITY_IDS]
    relation_rows = []
    pairs = [("E1", "E2"), ("E2", "E3"), ("E1", "E3")]
    for i, (source, target) in enumerate(pairs):
        slow = 0.015 * t
        fast = 0.18 if pattern == "sudden_intensity" and t >= 5 else 0.0
        relation_strength = 0.48 + i * 0.04
        relation_rigidity = 0.26 + i * 0.03
        flow = 0.25 + i * 0.02
        if pattern == "overconvergence":
            relation_rigidity += slow
            flow -= slow
        elif pattern == "fixation":
            relation_rigidity += slow * 1.4
            flow -= slow * 1.2
        elif pattern == "divergence":
            flow += slow * 1.8
            relation_strength -= slow * 0.4
        elif pattern == "sudden_angle" and t >= 5:
            relation_rigidity += 0.05 * (t - 4)
            flow -= 0.04 * (t - 4)
        elif pattern == "sudden_intensity":
            relation_rigidity += fast
            flow += fast
        relation_rows.append({
            "source": source,
            "target": target,
            "relation_strength": max(0.0, min(1.0, relation_strength)),
            "relation_rigidity": max(0.0, min(1.0, relation_rigidity)),
            "flow": max(0.0, min(1.0, flow)),
            "t": int(t),
            "scenario": "prediction_validation",
            "seed": 101,
        })
    return {
        "entity_trace": pd.DataFrame(entity_rows),
        "relation_trace": pd.DataFrame(relation_rows),
    }


def build_ot_tables(trace: Dict[str, pd.DataFrame], pattern: str, t: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    entity = trace["entity_trace"]
    rows = []
    residual_rows = []
    for _, ent in entity.iterrows():
        residual = 0.08
        unresolved = 0.07
        ambiguity = 0.06
        mismatch = 0.05
        boundary = 0.06
        if pattern == "divergence":
            residual += 0.018 * t
            unresolved += 0.014 * t
            mismatch += 0.018 * t
            boundary += 0.014 * t
        elif pattern == "fixation":
            residual += 0.012 * t
            unresolved += 0.012 * t
            ambiguity += 0.008 * t
        elif pattern == "sudden_intensity" and t >= 5:
            residual += 0.20
            boundary += 0.18
        elif pattern == "sudden_angle" and t >= 5:
            ambiguity += 0.12
            mismatch += 0.12
        row = {
            "entity_id": ent["entity_id"],
            "ot_id": f"OT_{ent['entity_id']}",
            "ot_identity_key": ent["entity_id"],
            "t": int(t),
            "activity": float(ent["activity"]),
            "volatility": float(ent["volatility"]),
            "uncertainty": float(ent["uncertainty"]),
            "relation_lock": float(ent["relation_lock"]),
            "coupling": float(ent["coupling"]),
            "exploration": float(ent["exploration"]),
            "reversibility": float(ent["reversibility"]),
            "entropy": float(ent["entropy"]),
            "relation_degree": 2.0,
            "ot_residual_score": min(1.0, residual),
            "ot_noise_score": min(1.0, residual * 0.8),
            "ot_unresolved_score": min(1.0, unresolved),
            "ot_ambiguity_score": min(1.0, ambiguity),
            "ot_macro_micro_mismatch_score": min(1.0, mismatch),
            "ot_boundary_instability_score": min(1.0, boundary),
            "ot_local_observation_need_score": min(1.0, max(residual, unresolved, ambiguity, mismatch, boundary)),
        }
        rows.append(row)
        residual_rows.append({
            "entity_id": ent["entity_id"],
            "ot_id": f"OT_{ent['entity_id']}",
            "ot_identity_key": ent["entity_id"],
            "last_seen_t": int(t),
            "ot_residual_score": row["ot_residual_score"],
            "ot_noise_score": row["ot_noise_score"],
            "ot_unresolved_score": row["ot_unresolved_score"],
            "ot_ambiguity_score": row["ot_ambiguity_score"],
            "ot_macro_micro_mismatch_score": row["ot_macro_micro_mismatch_score"],
            "ot_boundary_instability_score": row["ot_boundary_instability_score"],
            "observation_count": t + 1,
            "active_count": int(row["ot_local_observation_need_score"] > 0.20),
            "consecutive_active_count": int(row["ot_local_observation_need_score"] > 0.20) * max(1, t - 4),
            "max_noise_score_seen": row["ot_noise_score"],
            "noise_delta": 0.01 * t,
            "residual_delta": 0.01 * t,
        })
    ot = pd.DataFrame(rows)
    residual = pd.DataFrame(residual_rows)
    return ot.copy(), ot, residual


def _empty_gk(t: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    gt = pd.DataFrame([{"gt_uncertainty": 0.1 + 0.01 * t, "gt_relation_lock": 0.2 + 0.005 * t}])
    kt = pd.DataFrame([{"kt_uncertainty_slope": 0.01, "kt_exploration_slope": 0.01, "kt_n_observations": t + 1}])
    return gt, kt


def expected_pattern_response(pattern: str) -> dict[str, str | bool]:
    mapping = {
        "stable": {"primary_channel": "none", "should_request_projection": False},
        "overconvergence": {"primary_channel": "overconvergence", "should_request_projection": True},
        "fixation": {"primary_channel": "fixation", "should_request_projection": True},
        "divergence": {"primary_channel": "divergence", "should_request_projection": True},
        "sudden_angle": {"primary_channel": "short_angle", "should_request_projection": True},
        "sudden_intensity": {"primary_channel": "short_intensity", "should_request_projection": True},
    }
    return mapping[pattern]


def dominant_activation_channel(row: pd.Series) -> str:
    candidates = {
        "short_intensity": float(row.get("short_intensity_change", 0.0)),
        "short_angle": float(row.get("short_angle_change", 0.0)),
        "overconvergence": max(float(row.get("overconvergence_integral_mid", 0.0)), float(row.get("overconvergence_integral_short", 0.0))),
        "fixation": max(float(row.get("fixation_integral_mid", 0.0)), float(row.get("fixation_integral_short", 0.0))),
        "divergence": max(float(row.get("divergence_integral_mid", 0.0)), float(row.get("divergence_integral_short", 0.0))),
    }
    name, value = max(candidates.items(), key=lambda kv: kv[1])
    return name if value > 0.0 else "none"


def _future_trace_error(predicted: pd.DataFrame, future_trace: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    entity_future = future_trace["entity_trace"].set_index("entity_id")
    rows = []
    for _, pred in predicted.iterrows():
        entity_id = pred["entity_id"]
        metric = pred["metric_name"]
        if entity_id not in entity_future.index or metric not in entity_future.columns:
            continue
        expected_value = float(entity_future.loc[entity_id, metric])
        predicted_value = float(pred["projected_no_action_value"])
        rows.append({
            "entity_id": entity_id,
            "metric_name": metric,
            "predicted_value": predicted_value,
            "expected_value": expected_value,
            "abs_error": abs(predicted_value - expected_value),
        })
    return pd.DataFrame(rows)


def validate_pattern(pattern: str, cfg: PredictionValidationConfig | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    cfg = cfg or PredictionValidationConfig()
    activation = DEPTPredictionActivationModule(PredictionActivationConfig(
        initial_reference_score=0.0,
        standard_threshold=cfg.activation_threshold,
        deep_threshold=cfg.deep_threshold,
        short_window=3,
        mid_window=8,
    ))
    activation_rows = []
    projection_rows = []
    projection_error_rows = []
    module = DEPTPredictionModule()
    for t in range(cfg.steps):
        trace = build_v2_pattern_trace(pattern, t)
        ot_native, ot_action_view, residual = build_ot_tables(trace, pattern, t)
        gt, kt = _empty_gk(t)
        activation_state = activation.build(
            world_trace_before=trace,
            gt=gt,
            kt=kt,
            ot_native=ot_native,
            ot_action_view=ot_action_view,
            residual_noise_log=residual,
            loop_step=t,
            seed=101,
            scenario=pattern,
        )
        row = activation_state.iloc[0].to_dict()
        row["pattern"] = pattern
        row["dominant_activation_channel"] = dominant_activation_channel(activation_state.iloc[0])
        expected = expected_pattern_response(pattern)
        row["expected_primary_channel"] = expected["primary_channel"]
        row["expected_projection_requested"] = bool(expected["should_request_projection"])
        row["projection_response_match"] = bool(row["standard_projection_requested"]) == bool(expected["should_request_projection"])
        row["primary_channel_match"] = row["dominant_activation_channel"] == row["expected_primary_channel"] or pattern == "stable"
        activation_rows.append(row)
        if bool(row["standard_projection_requested"]):
            for horizon in HORIZONS:
                future = build_v2_pattern_trace(pattern, t + horizon)
                pred = module.build(
                    world_trace_before=trace,
                    baseline_trace_after=future,
                    gt=gt,
                    kt=kt,
                    ot_native=ot_native,
                    ot_action_view=ot_action_view,
                    residual_noise_log=residual,
                    loop_step=t,
                    seed=101,
                    scenario=pattern,
                )
                entity_projection = pred["dept_prediction_entity_projection"].copy()
                entity_projection["pattern"] = pattern
                entity_projection["source_step"] = t
                entity_projection["horizon"] = horizon
                projection_rows.append(entity_projection)
                errors = _future_trace_error(entity_projection, future)
                if not errors.empty:
                    errors["pattern"] = pattern
                    errors["source_step"] = t
                    errors["horizon"] = horizon
                    projection_error_rows.append(errors)
    return (
        pd.DataFrame(activation_rows),
        pd.concat(projection_rows, ignore_index=True) if projection_rows else pd.DataFrame(),
        pd.concat(projection_error_rows, ignore_index=True) if projection_error_rows else pd.DataFrame(),
    )


def run_dept_prediction_validation(cfg: PredictionValidationConfig | None = None) -> dict[str, pd.DataFrame]:
    cfg = cfg or PredictionValidationConfig()
    activation_tables = []
    projection_tables = []
    error_tables = []
    for pattern in PATTERNS:
        activation, projection, errors = validate_pattern(pattern, cfg)
        activation_tables.append(activation)
        if not projection.empty:
            projection_tables.append(projection)
        if not errors.empty:
            error_tables.append(errors)
    activation_all = pd.concat(activation_tables, ignore_index=True)
    projection_all = pd.concat(projection_tables, ignore_index=True) if projection_tables else pd.DataFrame()
    error_all = pd.concat(error_tables, ignore_index=True) if error_tables else pd.DataFrame()
    summary_rows = []
    for pattern, group in activation_all.groupby("pattern"):
        expected = expected_pattern_response(pattern)
        after_warmup = group[group["loop_step"] >= 2]
        response_rate = float(after_warmup["projection_response_match"].mean()) if not after_warmup.empty else 0.0
        channel_rate = float(after_warmup["primary_channel_match"].mean()) if not after_warmup.empty else 0.0
        summary_rows.append({
            "pattern": pattern,
            "expected_primary_channel": expected["primary_channel"],
            "expected_projection_requested": expected["should_request_projection"],
            "activation_response_match_rate_after_warmup": response_rate,
            "primary_channel_match_rate_after_warmup": channel_rate,
            "max_prediction_need_score": float(group["prediction_need_score"].max()),
            "max_short_intensity_change": float(group["short_intensity_change"].max()),
            "max_short_angle_change": float(group["short_angle_change"].max()),
            "max_overconvergence_integral_mid": float(group["overconvergence_integral_mid"].max()),
            "max_fixation_integral_mid": float(group["fixation_integral_mid"].max()),
            "max_divergence_integral_mid": float(group["divergence_integral_mid"].max()),
        })
    activation_summary = pd.DataFrame(summary_rows)
    horizon_summary = pd.DataFrame()
    if not error_all.empty:
        horizon_summary = error_all.groupby(["pattern", "horizon"], as_index=False).agg(
            mean_abs_error=("abs_error", "mean"),
            max_abs_error=("abs_error", "max"),
            rows=("abs_error", "size"),
        )
        horizon_summary["projection_packaging_within_tolerance"] = horizon_summary["max_abs_error"] <= cfg.projection_error_tolerance
    return {
        "prediction_activation_validation": activation_all,
        "prediction_activation_summary": activation_summary,
        "prediction_projection_rows": projection_all,
        "prediction_projection_error_rows": error_all,
        "prediction_horizon_summary": horizon_summary,
    }
