"""Prediction Module Full Validation Phase 1.

Purpose:
  Measure whether the prediction module can estimate future dynamics direction
  and strength from allowed public-history inputs only.

Boundary:
  - v2 is used only as a heldout answer generator by the validation layer.
  - The prediction module receives public current trace and public-history-based
    projected trace only.
  - v2 hidden/game/resource/information/action-effect traces are not passed to
    the prediction module.

Phase 1 adds:
  - multi-seed validation,
  - profile/horizon summaries,
  - neutral and previous-step baseline comparison,
  - seed-stability summary,
  - usable horizon estimates by profile and method.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd

from dept2_fullspec_runner_rc1.validation.dept_prediction_v2_validation_bench import (
    FORBIDDEN_PREDICTION_INPUT_KEYS,
    HORIZONS,
    V2_PROFILES,
    V2PredictionBenchConfig,
    _run_v2_world,
    _score_direction_strength,
    validate_v2_profile,
)

PREDICTION_METHOD = "prediction_module"
NEUTRAL_BASELINE_METHOD = "neutral_zero_baseline"
PREVIOUS_STEP_BASELINE_METHOD = "previous_step_baseline"
VALIDATION_METHODS = [
    PREDICTION_METHOD,
    NEUTRAL_BASELINE_METHOD,
    PREVIOUS_STEP_BASELINE_METHOD,
]


@dataclass(frozen=True)
class PredictionFullValidationPhase1Config:
    seeds: tuple[int, ...] = (101, 202, 303, 404, 505)
    profiles: tuple[str, ...] = tuple(V2_PROFILES)
    n_entities: int = 18
    warmup_steps: int = 3
    source_steps: int = 8
    max_horizon: int = 5
    direction_match_floor: float = 0.25
    strength_abs_error_ceiling: float = 0.25


def _bench_cfg(seed: int, cfg: PredictionFullValidationPhase1Config) -> V2PredictionBenchConfig:
    return V2PredictionBenchConfig(
        seed=seed,
        n_entities=cfg.n_entities,
        warmup_steps=cfg.warmup_steps,
        source_steps=cfg.source_steps,
        max_horizon=cfg.max_horizon,
        direction_match_floor=cfg.direction_match_floor,
        strength_abs_error_ceiling=cfg.strength_abs_error_ceiling,
    )


def _prediction_rows(profile: str, seed: int, cfg: PredictionFullValidationPhase1Config) -> pd.DataFrame:
    rows = validate_v2_profile(profile, _bench_cfg(seed, cfg)).copy()
    if rows.empty:
        return rows
    rows["seed"] = int(seed)
    rows["method"] = PREDICTION_METHOD
    rows["predicted_direction"] = rows["predicted_dynamics_direction"]
    rows["predicted_strength"] = rows["predicted_dynamics_strength"]
    rows["actual_direction"] = rows["actual_dynamics_direction"]
    rows["actual_strength"] = rows["actual_dynamics_strength"]
    rows["prediction_input_contract"] = "public_trace_history_projection_only"
    rows["baseline_family"] = "none"
    return rows[
        [
            "seed",
            "profile",
            "source_world_t",
            "horizon",
            "method",
            "baseline_family",
            "predicted_direction",
            "predicted_strength",
            "actual_direction",
            "actual_strength",
            "direction_match",
            "strength_abs_error",
            "input_boundary_status",
            "prediction_input_contract",
            "forbidden_v2_trace_keys_passed_to_prediction",
        ]
    ]


def _baseline_rows(profile: str, seed: int, cfg: PredictionFullValidationPhase1Config) -> pd.DataFrame:
    bench_cfg = _bench_cfg(seed, cfg)
    traces = _run_v2_world(profile, bench_cfg)
    rows: list[dict[str, object]] = []
    for source_index in range(cfg.warmup_steps, cfg.warmup_steps + cfg.source_steps):
        current = traces[source_index]
        previous = traces[source_index - 1] if source_index > 0 else current
        source_t = int(current["entity_trace"]["t"].iloc[0])
        previous_direction, previous_strength = _score_direction_strength(previous, current, 1)
        for horizon in HORIZONS:
            if horizon > cfg.max_horizon:
                continue
            future = traces[source_index + horizon]
            actual_direction, actual_strength = _score_direction_strength(current, future, horizon)
            for method, predicted_direction, predicted_strength, family in [
                (NEUTRAL_BASELINE_METHOD, "neutral", 0.0, "neutral"),
                (PREVIOUS_STEP_BASELINE_METHOD, previous_direction, previous_strength, "persistence"),
            ]:
                predicted_strength_f = float(predicted_strength)
                rows.append(
                    {
                        "seed": int(seed),
                        "profile": profile,
                        "source_world_t": source_t,
                        "horizon": int(horizon),
                        "method": method,
                        "baseline_family": family,
                        "predicted_direction": str(predicted_direction),
                        "predicted_strength": predicted_strength_f,
                        "actual_direction": actual_direction,
                        "actual_strength": actual_strength,
                        "direction_match": str(predicted_direction) == actual_direction,
                        "strength_abs_error": abs(predicted_strength_f - float(actual_strength)),
                        "input_boundary_status": "public_trace_only",
                        "prediction_input_contract": "public_trace_history_only",
                        "forbidden_v2_trace_keys_passed_to_prediction": False,
                    }
                )
    return pd.DataFrame(rows)


def run_profile_seed_phase1(
    profile: str,
    seed: int,
    cfg: PredictionFullValidationPhase1Config | None = None,
) -> pd.DataFrame:
    cfg = cfg or PredictionFullValidationPhase1Config()
    parts = [_prediction_rows(profile, seed, cfg), _baseline_rows(profile, seed, cfg)]
    parts = [p for p in parts if p is not None and not p.empty]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def _method_summary(rows: pd.DataFrame, cfg: PredictionFullValidationPhase1Config) -> pd.DataFrame:
    if rows.empty:
        return pd.DataFrame()
    summary = rows.groupby(["method", "profile", "horizon"], as_index=False).agg(
        direction_match_rate=("direction_match", "mean"),
        mean_strength_abs_error=("strength_abs_error", "mean"),
        max_strength_abs_error=("strength_abs_error", "max"),
        mean_predicted_strength=("predicted_strength", "mean"),
        mean_actual_strength=("actual_strength", "mean"),
        rows=("direction_match", "size"),
        seeds=("seed", "nunique"),
    )
    summary["usable_direction_match_floor"] = float(cfg.direction_match_floor)
    summary["usable_strength_error_ceiling"] = float(cfg.strength_abs_error_ceiling)
    summary["direction_floor_pass"] = summary["direction_match_rate"] >= cfg.direction_match_floor
    summary["strength_error_pass"] = summary["mean_strength_abs_error"] <= cfg.strength_abs_error_ceiling
    summary["usable_horizon_pass"] = summary["direction_floor_pass"] & summary["strength_error_pass"]
    return summary


def _seed_stability_summary(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return pd.DataFrame()
    per_seed = rows.groupby(["method", "profile", "horizon", "seed"], as_index=False).agg(
        seed_direction_match_rate=("direction_match", "mean"),
        seed_mean_strength_abs_error=("strength_abs_error", "mean"),
        rows=("direction_match", "size"),
    )
    return per_seed.groupby(["method", "profile", "horizon"], as_index=False).agg(
        mean_seed_direction_match_rate=("seed_direction_match_rate", "mean"),
        min_seed_direction_match_rate=("seed_direction_match_rate", "min"),
        max_seed_direction_match_rate=("seed_direction_match_rate", "max"),
        std_seed_direction_match_rate=("seed_direction_match_rate", "std"),
        mean_seed_strength_abs_error=("seed_mean_strength_abs_error", "mean"),
        max_seed_strength_abs_error=("seed_mean_strength_abs_error", "max"),
        seeds=("seed_direction_match_rate", "size"),
    ).fillna(0.0)


def _comparison_summary(method_summary: pd.DataFrame) -> pd.DataFrame:
    if method_summary.empty:
        return pd.DataFrame()
    prediction = method_summary[method_summary["method"] == PREDICTION_METHOD]
    baselines = method_summary[method_summary["method"].isin([NEUTRAL_BASELINE_METHOD, PREVIOUS_STEP_BASELINE_METHOD])]
    if prediction.empty or baselines.empty:
        return pd.DataFrame()
    pred_cols = prediction[
        [
            "profile",
            "horizon",
            "direction_match_rate",
            "mean_strength_abs_error",
            "rows",
            "seeds",
        ]
    ].rename(
        columns={
            "direction_match_rate": "prediction_direction_match_rate",
            "mean_strength_abs_error": "prediction_mean_strength_abs_error",
            "rows": "prediction_rows",
            "seeds": "prediction_seeds",
        }
    )
    base_cols = baselines[
        [
            "method",
            "profile",
            "horizon",
            "direction_match_rate",
            "mean_strength_abs_error",
            "rows",
            "seeds",
        ]
    ].rename(
        columns={
            "method": "baseline_method",
            "direction_match_rate": "baseline_direction_match_rate",
            "mean_strength_abs_error": "baseline_mean_strength_abs_error",
            "rows": "baseline_rows",
            "seeds": "baseline_seeds",
        }
    )
    merged = base_cols.merge(pred_cols, on=["profile", "horizon"], how="left")
    merged["direction_match_lift"] = merged["prediction_direction_match_rate"] - merged["baseline_direction_match_rate"]
    merged["strength_error_reduction"] = merged["baseline_mean_strength_abs_error"] - merged["prediction_mean_strength_abs_error"]
    merged["prediction_beats_baseline_direction"] = merged["direction_match_lift"] > 0.0
    merged["prediction_beats_baseline_strength"] = merged["strength_error_reduction"] > 0.0
    return merged


def _usable_horizon_summary(method_summary: pd.DataFrame) -> pd.DataFrame:
    if method_summary.empty:
        return pd.DataFrame()
    out = []
    for (method, profile), group in method_summary.groupby(["method", "profile"]):
        usable = group[group["usable_horizon_pass"]]
        out.append(
            {
                "method": method,
                "profile": profile,
                "usable_horizon": int(usable["horizon"].max()) if not usable.empty else 0,
                "tested_horizons": ",".join(str(int(h)) for h in sorted(group["horizon"].unique())),
                "rows": int(group["rows"].sum()),
                "seeds": int(group["seeds"].max()) if not group.empty else 0,
            }
        )
    return pd.DataFrame(out)


def _boundary_summary(rows: pd.DataFrame, cfg: PredictionFullValidationPhase1Config) -> pd.DataFrame:
    forbidden_passed = bool(rows["forbidden_v2_trace_keys_passed_to_prediction"].any()) if not rows.empty else True
    return pd.DataFrame(
        [
            {
                "validation_name": "Task2-8j-24d Prediction Module Full Validation Phase 1",
                "prediction_input_contract": "public_trace_history_only",
                "v2_future_usage": "heldout_answer_key_only",
                "forbidden_prediction_input_keys": ",".join(sorted(FORBIDDEN_PREDICTION_INPUT_KEYS)),
                "forbidden_v2_trace_keys_passed_to_prediction": forbidden_passed,
                "boundary_pass": (not forbidden_passed) and (not rows.empty),
                "n_seeds": len(cfg.seeds),
                "n_profiles": len(cfg.profiles),
                "n_methods": len(VALIDATION_METHODS),
                "max_horizon": int(cfg.max_horizon),
            }
        ]
    )


def run_prediction_full_validation_phase1(
    cfg: PredictionFullValidationPhase1Config | None = None,
) -> dict[str, pd.DataFrame]:
    cfg = cfg or PredictionFullValidationPhase1Config()
    parts: list[pd.DataFrame] = []
    for seed in cfg.seeds:
        for profile in cfg.profiles:
            parts.append(run_profile_seed_phase1(profile, int(seed), cfg))
    rows = pd.concat([p for p in parts if p is not None and not p.empty], ignore_index=True) if parts else pd.DataFrame()
    method_summary = _method_summary(rows, cfg)
    seed_stability = _seed_stability_summary(rows)
    comparison = _comparison_summary(method_summary)
    usable_horizon = _usable_horizon_summary(method_summary)
    boundary = _boundary_summary(rows, cfg)
    return {
        "prediction_full_validation_phase1_rows": rows,
        "prediction_full_validation_phase1_method_summary": method_summary,
        "prediction_full_validation_phase1_seed_stability": seed_stability,
        "prediction_full_validation_phase1_baseline_comparison": comparison,
        "prediction_full_validation_phase1_usable_horizon": usable_horizon,
        "prediction_full_validation_phase1_boundary": boundary,
    }
