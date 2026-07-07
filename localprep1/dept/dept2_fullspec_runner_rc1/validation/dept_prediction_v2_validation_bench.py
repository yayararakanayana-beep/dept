"""v2 heldout validation bench for DEPT prediction dynamics.

Boundary rule:
  - The prediction module never reads v2 hidden/game/resource/information traces.
  - The prediction module receives only current public trace plus a DEPT-side
    projected public trace built from past public traces.
  - v2 future traces are held out and used only by this validation bench as
    answer keys for direction/strength scoring.

This bench therefore tests whether input-only public-history extrapolation plus
DEPT dynamics projection can approximate the held-out v2 no-action dynamics.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict
import copy

import pandas as pd

from DEPT2_ActionModule_ActuationPrimitives_RC1.pseudo_reality.asymmetric_game_v2 import (
    AsymmetricGamePseudoRealitySystem,
)
from dept2_fullspec_runner_rc1.modules.dept_prediction_module import DEPTPredictionModule


V2_PROFILES = [
    "pseudo_reality_v2_shrinking_equilibrium",
    "pseudo_reality_v2_trust_collapse",
    "pseudo_reality_v2_public_stability_hidden_decay",
]
HORIZONS = [1, 2, 3, 5]
PUBLIC_TRACE_KEYS = ["entity_trace", "relation_trace"]
FORBIDDEN_PREDICTION_INPUT_KEYS = {
    "v2_hidden_trace",
    "v2_game_trace",
    "v2_resource_trace",
    "v2_information_trace",
    "v2_action_effect_trace",
}


@dataclass(frozen=True)
class V2PredictionBenchConfig:
    seed: int = 202
    n_entities: int = 18
    warmup_steps: int = 3
    source_steps: int = 6
    max_horizon: int = 5
    direction_match_floor: float = 0.25
    strength_abs_error_ceiling: float = 0.25


def _copy_public_trace(trace: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    return {k: trace[k].copy(deep=True) for k in PUBLIC_TRACE_KEYS if k in trace}


def _numeric_cols(df: pd.DataFrame, exclude: set[str]) -> list[str]:
    if df is None or df.empty:
        return []
    out = []
    for col in df.columns:
        if col in exclude:
            continue
        series = pd.to_numeric(df[col], errors="coerce")
        if series.notna().any():
            out.append(str(col))
    return out


def _clip_public_trace(trace: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    out = _copy_public_trace(trace)
    entity_exclude = {"entity_id", "t", "scenario", "seed", "primary_type"}
    relation_exclude = {"source", "target", "t", "scenario", "seed"}
    for col in _numeric_cols(out.get("entity_trace", pd.DataFrame()), entity_exclude):
        out["entity_trace"][col] = pd.to_numeric(out["entity_trace"][col], errors="coerce").fillna(0.0).clip(0.0, 1.0)
    for col in _numeric_cols(out.get("relation_trace", pd.DataFrame()), relation_exclude):
        out["relation_trace"][col] = pd.to_numeric(out["relation_trace"][col], errors="coerce").fillna(0.0).clip(0.0, 1.0)
    return out


def project_public_trace_from_history(history: list[Dict[str, pd.DataFrame]], horizon: int) -> Dict[str, pd.DataFrame]:
    """Build a DEPT-side projected public trace from prior public traces only."""
    if not history:
        raise ValueError("history must not be empty")
    current = _copy_public_trace(history[-1])
    if len(history) < 2:
        projected = _copy_public_trace(current)
    else:
        previous = history[-2]
        projected = _copy_public_trace(current)
        cur_e = current["entity_trace"].set_index("entity_id")
        prev_e = previous["entity_trace"].set_index("entity_id")
        common_e = cur_e.index.intersection(prev_e.index)
        entity_numeric = _numeric_cols(current["entity_trace"], {"entity_id", "t", "scenario", "seed", "primary_type"})
        proj_e = projected["entity_trace"].set_index("entity_id")
        for col in entity_numeric:
            if col in prev_e.columns:
                delta = pd.to_numeric(cur_e.loc[common_e, col], errors="coerce") - pd.to_numeric(prev_e.loc[common_e, col], errors="coerce")
                proj_e.loc[common_e, col] = pd.to_numeric(cur_e.loc[common_e, col], errors="coerce") + delta * float(horizon)
        projected["entity_trace"] = proj_e.reset_index()

        cur_r = current["relation_trace"].set_index(["source", "target"])
        prev_r = previous["relation_trace"].set_index(["source", "target"])
        common_r = cur_r.index.intersection(prev_r.index)
        relation_numeric = _numeric_cols(current["relation_trace"], {"source", "target", "t", "scenario", "seed"})
        proj_r = projected["relation_trace"].set_index(["source", "target"])
        for col in relation_numeric:
            if col in prev_r.columns and len(common_r) > 0:
                delta = pd.to_numeric(cur_r.loc[common_r, col], errors="coerce") - pd.to_numeric(prev_r.loc[common_r, col], errors="coerce")
                proj_r.loc[common_r, col] = pd.to_numeric(cur_r.loc[common_r, col], errors="coerce") + delta * float(horizon)
        projected["relation_trace"] = proj_r.reset_index()

    current_t = int(current["entity_trace"]["t"].iloc[0]) if not current["entity_trace"].empty else 0
    for key in PUBLIC_TRACE_KEYS:
        if key in projected and "t" in projected[key].columns:
            projected[key]["t"] = current_t + int(horizon)
    return _clip_public_trace(projected)


def build_public_ot_tables(public_trace: Dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Create public-input O-like context from public trace only, not from v2 hidden traces."""
    e = public_trace["entity_trace"].copy()
    rows = []
    residual_rows = []
    relation_degree = public_trace["relation_trace"].groupby("source").size().to_dict() if not public_trace["relation_trace"].empty else {}
    for _, ent in e.iterrows():
        entity_id = str(ent["entity_id"])
        uncertainty = float(ent.get("uncertainty", 0.0))
        volatility = float(ent.get("volatility", 0.0))
        relation_lock = float(ent.get("relation_lock", 0.0))
        reversibility = float(ent.get("reversibility", 0.0))
        exploration = float(ent.get("exploration", 0.0))
        residual = max(0.0, volatility * 0.35 + uncertainty * 0.25 + max(0.0, relation_lock - reversibility) * 0.25)
        unresolved = max(0.0, uncertainty * 0.30 + max(0.0, 0.45 - exploration) * 0.20)
        ambiguity = max(0.0, uncertainty * 0.25 + volatility * 0.20)
        mismatch = max(0.0, abs(relation_lock - exploration) * 0.25)
        boundary = max(0.0, relation_lock * 0.20 + volatility * 0.30)
        row = {
            "entity_id": entity_id,
            "ot_id": f"public_OT_{entity_id}",
            "ot_identity_key": entity_id,
            "t": int(ent.get("t", 0)),
            "activity": float(ent.get("activity", 0.0)),
            "volatility": volatility,
            "uncertainty": uncertainty,
            "relation_lock": relation_lock,
            "coupling": float(ent.get("coupling", 0.0)),
            "exploration": exploration,
            "reversibility": reversibility,
            "entropy": float(ent.get("entropy", 0.0)),
            "relation_degree": float(relation_degree.get(entity_id, 0)),
            "ot_residual_score": min(1.0, residual),
            "ot_noise_score": min(1.0, residual * 0.65),
            "ot_unresolved_score": min(1.0, unresolved),
            "ot_ambiguity_score": min(1.0, ambiguity),
            "ot_macro_micro_mismatch_score": min(1.0, mismatch),
            "ot_boundary_instability_score": min(1.0, boundary),
            "ot_local_observation_need_score": min(1.0, max(residual, unresolved, ambiguity, mismatch, boundary)),
        }
        rows.append(row)
        residual_rows.append({
            "entity_id": entity_id,
            "ot_id": row["ot_id"],
            "ot_identity_key": entity_id,
            "last_seen_t": row["t"],
            "ot_residual_score": row["ot_residual_score"],
            "ot_noise_score": row["ot_noise_score"],
            "ot_unresolved_score": row["ot_unresolved_score"],
            "ot_ambiguity_score": row["ot_ambiguity_score"],
            "ot_macro_micro_mismatch_score": row["ot_macro_micro_mismatch_score"],
            "ot_boundary_instability_score": row["ot_boundary_instability_score"],
            "observation_count": 1,
            "active_count": int(row["ot_local_observation_need_score"] > 0.20),
            "consecutive_active_count": 0,
            "max_noise_score_seen": row["ot_noise_score"],
            "noise_delta": 0.0,
            "residual_delta": 0.0,
        })
    ot = pd.DataFrame(rows)
    residual = pd.DataFrame(residual_rows)
    return ot.copy(), ot, residual


def build_placeholder_gk(public_trace: Dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    e = public_trace["entity_trace"]
    t = int(e["t"].iloc[0]) if not e.empty and "t" in e.columns else 0
    gt = pd.DataFrame([{
        "gt_uncertainty": float(pd.to_numeric(e.get("uncertainty", pd.Series([0.0])), errors="coerce").fillna(0.0).mean()),
        "gt_relation_lock": float(pd.to_numeric(e.get("relation_lock", pd.Series([0.0])), errors="coerce").fillna(0.0).mean()),
    }])
    kt = pd.DataFrame([{"kt_n_observations": t + 1, "kt_uncertainty_slope": 0.0, "kt_exploration_slope": 0.0}])
    return gt, kt


def _score_direction_strength(current: Dict[str, pd.DataFrame], future: Dict[str, pd.DataFrame], horizon: int) -> tuple[str, float]:
    module = DEPTPredictionModule()
    ot_native, ot_action_view, residual = build_public_ot_tables(current)
    gt, kt = build_placeholder_gk(current)
    out = module.build(
        world_trace_before=current,
        baseline_trace_after=future,
        gt=gt,
        kt=kt,
        ot_native=ot_native,
        ot_action_view=ot_action_view,
        residual_noise_log=residual,
        loop_step=int(current["entity_trace"]["t"].iloc[0]),
        seed=int(current["entity_trace"]["seed"].iloc[0]),
        scenario=str(current["entity_trace"]["scenario"].iloc[0]),
    )
    dyn = out["dept_prediction_dynamics_projection"].iloc[0]
    return str(dyn["predicted_dynamics_direction"]), float(dyn["predicted_dynamics_strength"])


def _run_v2_world(profile: str, cfg: V2PredictionBenchConfig) -> list[Dict[str, pd.DataFrame]]:
    world = AsymmetricGamePseudoRealitySystem(
        seed=cfg.seed,
        scenario=profile,
        n_entities=cfg.n_entities,
        profile_name=profile,
    )
    traces = [_copy_public_trace(world.emit_trace())]
    total_steps = cfg.warmup_steps + cfg.source_steps + cfg.max_horizon + 1
    for _ in range(total_steps):
        traces.append(_copy_public_trace(world.step(None)))
    return traces


def validate_v2_profile(profile: str, cfg: V2PredictionBenchConfig | None = None) -> pd.DataFrame:
    cfg = cfg or V2PredictionBenchConfig()
    traces = _run_v2_world(profile, cfg)
    module = DEPTPredictionModule()
    rows = []
    for source_index in range(cfg.warmup_steps, cfg.warmup_steps + cfg.source_steps):
        history = traces[: source_index + 1]
        current = history[-1]
        ot_native, ot_action_view, residual = build_public_ot_tables(current)
        gt, kt = build_placeholder_gk(current)
        for horizon in HORIZONS:
            if horizon > cfg.max_horizon:
                continue
            projected = project_public_trace_from_history(history, horizon)
            predicted = module.build(
                world_trace_before=current,
                baseline_trace_after=projected,
                gt=gt,
                kt=kt,
                ot_native=ot_native,
                ot_action_view=ot_action_view,
                residual_noise_log=residual,
                loop_step=int(current["entity_trace"]["t"].iloc[0]),
                seed=cfg.seed,
                scenario=profile,
            )["dept_prediction_dynamics_projection"].iloc[0]
            future = traces[source_index + horizon]
            actual_direction, actual_strength = _score_direction_strength(current, future, horizon)
            rows.append({
                "profile": profile,
                "source_world_t": int(current["entity_trace"]["t"].iloc[0]),
                "horizon": int(horizon),
                "predicted_dynamics_direction": str(predicted["predicted_dynamics_direction"]),
                "predicted_dynamics_strength": float(predicted["predicted_dynamics_strength"]),
                "actual_dynamics_direction": actual_direction,
                "actual_dynamics_strength": actual_strength,
                "direction_match": str(predicted["predicted_dynamics_direction"]) == actual_direction,
                "strength_abs_error": abs(float(predicted["predicted_dynamics_strength"]) - actual_strength),
                "input_boundary_status": "public_trace_only",
                "forbidden_v2_trace_keys_passed_to_prediction": False,
            })
    return pd.DataFrame(rows)


def run_v2_prediction_validation_bench(cfg: V2PredictionBenchConfig | None = None) -> dict[str, pd.DataFrame]:
    cfg = cfg or V2PredictionBenchConfig()
    rows = [validate_v2_profile(profile, cfg) for profile in V2_PROFILES]
    result = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    summary = pd.DataFrame()
    if not result.empty:
        summary = result.groupby(["profile", "horizon"], as_index=False).agg(
            direction_match_rate=("direction_match", "mean"),
            mean_strength_abs_error=("strength_abs_error", "mean"),
            max_strength_abs_error=("strength_abs_error", "max"),
            mean_predicted_dynamics_strength=("predicted_dynamics_strength", "mean"),
            mean_actual_dynamics_strength=("actual_dynamics_strength", "mean"),
            rows=("direction_match", "size"),
        )
        summary["usable_direction_match_floor"] = float(cfg.direction_match_floor)
        summary["usable_strength_error_ceiling"] = float(cfg.strength_abs_error_ceiling)
        summary["direction_floor_pass"] = summary["direction_match_rate"] >= cfg.direction_match_floor
        summary["strength_error_pass"] = summary["mean_strength_abs_error"] <= cfg.strength_abs_error_ceiling
    boundary = pd.DataFrame([{
        "bench_name": "v2_prediction_validation_bench",
        "prediction_input_contract": "public_trace_history_only",
        "v2_future_usage": "heldout_answer_key_only",
        "forbidden_prediction_input_keys": ",".join(sorted(FORBIDDEN_PREDICTION_INPUT_KEYS)),
        "forbidden_v2_trace_keys_passed_to_prediction": bool(result["forbidden_v2_trace_keys_passed_to_prediction"].any()) if not result.empty else False,
        "boundary_pass": False if result.empty else not bool(result["forbidden_v2_trace_keys_passed_to_prediction"].any()),
    }])
    return {
        "v2_prediction_validation_rows": result,
        "v2_prediction_validation_summary": summary,
        "v2_prediction_validation_boundary": boundary,
    }
