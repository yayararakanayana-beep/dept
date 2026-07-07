"""dept_prediction_module: DEPT-side prediction values.

This module reads DEPT-owned observation/log artifacts and emits prediction
values only: current values, projected no-action values, deltas, dynamics
direction/strength, uncertainty/context signals, and source lineage.

The central prediction product is not a full future-state oracle. It is the
projected dynamics direction and strength that downstream modules may use as
input material without the prediction module making an action decision.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable
import json
from math import sqrt

import pandas as pd

from dept2_fullspec_runner_rc1.modules.world_adapter import trace_fingerprint

IDENTITY_COLS = {"entity_id", "source", "target", "t", "scenario", "seed"}
ENTITY_EXCLUDE_PREFIXES = ("gt_", "kt_", "ot_", "v8_", "action_frame", "pressure_intent")
OT_NUMERIC_COLUMNS = ["activity", "volatility", "uncertainty", "relation_lock", "coupling", "exploration", "reversibility", "entropy", "relation_degree", "ot_residual_score", "ot_noise_score", "ot_unresolved_score", "ot_ambiguity_score", "ot_macro_micro_mismatch_score", "ot_boundary_instability_score", "ot_local_observation_need_score"]
RESIDUAL_CONTEXT_COLUMNS = ["ot_residual_score", "ot_noise_score", "ot_unresolved_score", "ot_ambiguity_score", "ot_macro_micro_mismatch_score", "ot_boundary_instability_score", "observation_count", "active_count", "consecutive_active_count", "max_noise_score_seen", "noise_delta", "residual_delta"]
DECISION_TERMS = ("risk", "safe", "admit", "reject")


@dataclass(frozen=True)
class PredictionModuleConfig:
    max_unmapped_columns_recorded: int = 64
    include_entity_metric_rows: bool = True
    include_relation_metric_rows: bool = True
    neutral_delta_buffer: float = 0.006
    neutral_strength_buffer: float = 0.004
    neutral_margin_buffer: float = 0.0015


def _empty(columns: Iterable[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=list(columns))


def _is_decision_name(name: object) -> bool:
    lower = str(name).lower()
    return any(term in lower for term in DECISION_TERMS)


def _numeric_columns(df: pd.DataFrame, exclude: set[str] | None = None) -> list[str]:
    if df is None or df.empty:
        return []
    exclude = exclude or set()
    cols: list[str] = []
    for col in df.columns:
        if col in exclude or _is_decision_name(col):
            continue
        if any(str(col).startswith(prefix) for prefix in ENTITY_EXCLUDE_PREFIXES):
            continue
        series = pd.to_numeric(df[col], errors="coerce")
        if series.notna().any():
            cols.append(str(col))
    return cols


def _first_world_t(trace: Dict[str, pd.DataFrame] | None) -> int:
    if not trace or "entity_trace" not in trace or trace["entity_trace"].empty or "t" not in trace["entity_trace"].columns:
        return -1
    return int(trace["entity_trace"]["t"].iloc[0])


def _safe_float(value, default: float = 0.0) -> float:
    try:
        out = float(value)
        if pd.isna(out):
            return float(default)
        return out
    except Exception:
        return float(default)


def _json_dict(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def _pos(value: float) -> float:
    return max(0.0, float(value))


def _mean(values: list[float]) -> float:
    return float(sum(values) / max(1, len(values)))


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


class DEPTPredictionModule:
    name = "dept_prediction_module"

    def __init__(self, cfg: PredictionModuleConfig | None = None):
        self.cfg = cfg or PredictionModuleConfig()

    def build(self, *, world_trace_before, baseline_trace_after, gt, kt, ot_native, ot_action_view, residual_noise_log, loop_step: int, seed: int, scenario: str) -> dict[str, pd.DataFrame]:
        entity_projection = self.build_entity_projection(world_trace_before=world_trace_before, baseline_trace_after=baseline_trace_after, ot_action_view=ot_action_view, residual_noise_log=residual_noise_log, loop_step=loop_step, seed=seed, scenario=scenario)
        relation_projection = self.build_relation_projection(world_trace_before=world_trace_before, baseline_trace_after=baseline_trace_after, loop_step=loop_step, seed=seed, scenario=scenario)
        ot_context = self.build_ot_prediction_context(ot_native=ot_native, ot_action_view=ot_action_view, residual_noise_log=residual_noise_log, loop_step=loop_step, seed=seed, scenario=scenario)
        dynamics_projection = self.build_dynamics_projection(entity_projection=entity_projection, relation_projection=relation_projection, ot_context=ot_context, loop_step=loop_step, seed=seed, scenario=scenario)
        global_summary = self.build_global_prediction_summary(world_trace_before=world_trace_before, baseline_trace_after=baseline_trace_after, gt=gt, kt=kt, ot_native=ot_native, ot_action_view=ot_action_view, residual_noise_log=residual_noise_log, entity_projection=entity_projection, relation_projection=relation_projection, ot_context=ot_context, dynamics_projection=dynamics_projection, loop_step=loop_step, seed=seed, scenario=scenario)
        output_packet = self.build_prediction_output_packet(global_summary, entity_projection, relation_projection, ot_context, dynamics_projection)
        return {"dept_prediction_entity_projection": entity_projection, "dept_prediction_relation_projection": relation_projection, "dept_prediction_ot_context": ot_context, "dept_prediction_dynamics_projection": dynamics_projection, "dept_prediction_global_summary": global_summary, "dept_prediction_output_packet": output_packet}

    def build_entity_projection(self, *, world_trace_before, baseline_trace_after, ot_action_view, residual_noise_log, loop_step: int, seed: int, scenario: str) -> pd.DataFrame:
        columns = ["loop_step", "run_seed", "run_scenario", "entity_id", "world_t_current", "world_t_projection", "metric_name", "current_value", "projected_no_action_value", "projected_no_action_delta", "projected_no_action_delta_per_step", "projection_source", "projection_horizon_steps", "ot_id", "ot_identity_key", "ot_residual_score", "ot_noise_score", "ot_unresolved_score", "ot_ambiguity_score", "ot_macro_micro_mismatch_score", "ot_boundary_instability_score", "noise_delta", "residual_delta", "source_trace_fingerprint_current", "source_trace_fingerprint_projection"]
        if not world_trace_before or "entity_trace" not in world_trace_before or world_trace_before["entity_trace"].empty:
            return _empty(columns)
        current = world_trace_before["entity_trace"].copy()
        baseline = baseline_trace_after.get("entity_trace", pd.DataFrame()).copy() if baseline_trace_after else pd.DataFrame()
        world_t_current = _first_world_t(world_trace_before)
        world_t_projection = _first_world_t(baseline_trace_after)
        current_fp = trace_fingerprint(world_trace_before)
        projection_fp = trace_fingerprint(baseline_trace_after) if baseline_trace_after else "missing"
        metric_cols = _numeric_columns(current, exclude=IDENTITY_COLS)
        baseline_lookup = baseline.set_index("entity_id") if not baseline.empty and "entity_id" in baseline.columns else pd.DataFrame()
        ot_lookup = self._latest_by_entity(ot_action_view)
        noise_lookup = self._latest_by_entity(residual_noise_log)
        rows: list[dict] = []
        for _, ent in current.iterrows():
            entity_id = str(ent["entity_id"])
            projected = baseline_lookup.loc[entity_id] if entity_id in baseline_lookup.index else None
            ot = ot_lookup.loc[entity_id] if entity_id in ot_lookup.index else None
            noise = noise_lookup.loc[entity_id] if entity_id in noise_lookup.index else None
            for metric in metric_cols:
                current_value = _safe_float(ent.get(metric))
                if projected is not None and metric in baseline_lookup.columns:
                    projected_value = _safe_float(projected.get(metric), current_value)
                    projection_source = "baseline_no_action_trace"
                    horizon = max(0, world_t_projection - world_t_current)
                else:
                    projected_value = current_value
                    projection_source = "current_value_carried_forward_no_projection_trace"
                    horizon = 0
                delta = projected_value - current_value
                per_step = delta / max(1, horizon)
                rows.append({"loop_step": int(loop_step), "run_seed": int(seed), "run_scenario": str(scenario), "entity_id": entity_id, "world_t_current": int(world_t_current), "world_t_projection": int(world_t_projection), "metric_name": str(metric), "current_value": float(current_value), "projected_no_action_value": float(projected_value), "projected_no_action_delta": float(delta), "projected_no_action_delta_per_step": float(per_step), "projection_source": projection_source, "projection_horizon_steps": int(horizon), "ot_id": "" if ot is None else str(ot.get("ot_id", "")), "ot_identity_key": "" if ot is None else str(ot.get("ot_identity_key", entity_id)), "ot_residual_score": _safe_float(None if ot is None else ot.get("ot_residual_score")), "ot_noise_score": _safe_float(None if noise is None else noise.get("ot_noise_score", None if ot is None else ot.get("ot_noise_score"))), "ot_unresolved_score": _safe_float(None if noise is None else noise.get("ot_unresolved_score", None if ot is None else ot.get("ot_unresolved_score"))), "ot_ambiguity_score": _safe_float(None if noise is None else noise.get("ot_ambiguity_score", None if ot is None else ot.get("ot_ambiguity_score"))), "ot_macro_micro_mismatch_score": _safe_float(None if noise is None else noise.get("ot_macro_micro_mismatch_score", None if ot is None else ot.get("ot_macro_micro_mismatch_score"))), "ot_boundary_instability_score": _safe_float(None if noise is None else noise.get("ot_boundary_instability_score", None if ot is None else ot.get("ot_boundary_instability_score"))), "noise_delta": _safe_float(None if noise is None else noise.get("noise_delta")), "residual_delta": _safe_float(None if noise is None else noise.get("residual_delta")), "source_trace_fingerprint_current": current_fp, "source_trace_fingerprint_projection": projection_fp})
        return pd.DataFrame(rows, columns=columns)

    def build_relation_projection(self, *, world_trace_before, baseline_trace_after, loop_step: int, seed: int, scenario: str) -> pd.DataFrame:
        columns = ["loop_step", "run_seed", "run_scenario", "source", "target", "world_t_current", "world_t_projection", "relation_metric_name", "current_value", "projected_no_action_value", "projected_no_action_delta", "projected_no_action_delta_per_step", "projection_source", "projection_horizon_steps", "source_trace_fingerprint_current", "source_trace_fingerprint_projection"]
        if not world_trace_before or "relation_trace" not in world_trace_before:
            return _empty(columns)
        current = world_trace_before.get("relation_trace", pd.DataFrame()).copy()
        if current.empty:
            return _empty(columns)
        baseline = baseline_trace_after.get("relation_trace", pd.DataFrame()).copy() if baseline_trace_after else pd.DataFrame()
        world_t_current = _first_world_t(world_trace_before)
        world_t_projection = _first_world_t(baseline_trace_after)
        current_fp = trace_fingerprint(world_trace_before)
        projection_fp = trace_fingerprint(baseline_trace_after) if baseline_trace_after else "missing"
        metric_cols = _numeric_columns(current, exclude=IDENTITY_COLS)
        key_cols = ["source", "target"]
        baseline_lookup = baseline.set_index(key_cols) if not baseline.empty and set(key_cols).issubset(baseline.columns) else pd.DataFrame()
        rows: list[dict] = []
        for _, rel in current.iterrows():
            key = (rel["source"], rel["target"])
            projected = baseline_lookup.loc[key] if key in baseline_lookup.index else None
            for metric in metric_cols:
                current_value = _safe_float(rel.get(metric))
                if projected is not None and metric in baseline_lookup.columns:
                    projected_value = _safe_float(projected.get(metric), current_value)
                    projection_source = "baseline_no_action_trace"
                    horizon = max(0, world_t_projection - world_t_current)
                else:
                    projected_value = current_value
                    projection_source = "current_value_carried_forward_no_projection_trace"
                    horizon = 0
                delta = projected_value - current_value
                per_step = delta / max(1, horizon)
                rows.append({"loop_step": int(loop_step), "run_seed": int(seed), "run_scenario": str(scenario), "source": str(rel["source"]), "target": str(rel["target"]), "world_t_current": int(world_t_current), "world_t_projection": int(world_t_projection), "relation_metric_name": str(metric), "current_value": float(current_value), "projected_no_action_value": float(projected_value), "projected_no_action_delta": float(delta), "projected_no_action_delta_per_step": float(per_step), "projection_source": projection_source, "projection_horizon_steps": int(horizon), "source_trace_fingerprint_current": current_fp, "source_trace_fingerprint_projection": projection_fp})
        return pd.DataFrame(rows, columns=columns)

    def build_ot_prediction_context(self, *, ot_native, ot_action_view, residual_noise_log, loop_step: int, seed: int, scenario: str) -> pd.DataFrame:
        columns = ["loop_step", "run_seed", "run_scenario", "entity_id", "ot_id", "ot_identity_key", "context_metric_name", "context_metric_value", "context_source_table", "source_world_t"]
        rows: list[dict] = []
        for source_name, df in [("ot_native", ot_native), ("ot_action_view", ot_action_view), ("residual_noise_log", residual_noise_log)]:
            if df is None or df.empty:
                continue
            entity_col = "entity_id" if "entity_id" in df.columns else None
            for _, r in df.iterrows():
                entity_id = str(r.get(entity_col, r.get("ot_identity_key", ""))) if entity_col else str(r.get("ot_identity_key", ""))
                ot_id = str(r.get("ot_id", ""))
                identity = str(r.get("ot_identity_key", entity_id))
                world_t = int(_safe_float(r.get("t", r.get("last_seen_t", -1)), -1))
                for metric in OT_NUMERIC_COLUMNS + RESIDUAL_CONTEXT_COLUMNS:
                    if metric not in df.columns or _is_decision_name(metric):
                        continue
                    rows.append({"loop_step": int(loop_step), "run_seed": int(seed), "run_scenario": str(scenario), "entity_id": entity_id, "ot_id": ot_id, "ot_identity_key": identity, "context_metric_name": str(metric), "context_metric_value": _safe_float(r.get(metric)), "context_source_table": source_name, "source_world_t": int(world_t)})
        return pd.DataFrame(rows, columns=columns)

    def build_dynamics_projection(self, *, entity_projection: pd.DataFrame, relation_projection: pd.DataFrame, ot_context: pd.DataFrame, loop_step: int, seed: int, scenario: str) -> pd.DataFrame:
        columns = ["loop_step", "run_seed", "run_scenario", "prediction_focus", "projection_horizon_steps", "predicted_dynamics_direction", "predicted_dynamics_strength", "predicted_direction_margin", "projected_delta_intensity", "overconvergence_direction_strength", "fixation_direction_strength", "divergence_direction_strength", "neutral_buffer_distance", "neutral_buffer_applied", "shrink_equilibrium_measure", "bias_concentration_measure", "divergence_release_measure", "direction_strength_json", "dynamics_projection_role"]
        if entity_projection is None or entity_projection.empty:
            return _empty(columns)
        horizon = int(entity_projection["projection_horizon_steps"].max()) if "projection_horizon_steps" in entity_projection.columns else 0

        def e(metric: str) -> float:
            return self._mean_entity_delta(entity_projection, metric)

        def r(metric: str) -> float:
            return self._mean_relation_delta(relation_projection, metric)

        def es(metric: str) -> float:
            return self._entity_spread_delta(entity_projection, metric)

        def rs(metric: str) -> float:
            return self._relation_spread_delta(relation_projection, metric)

        deltas = [float(v) for v in pd.to_numeric(entity_projection.get("projected_no_action_delta_per_step", pd.Series(dtype=float)), errors="coerce").fillna(0.0).to_list()]
        if relation_projection is not None and not relation_projection.empty:
            deltas += [float(v) for v in pd.to_numeric(relation_projection.get("projected_no_action_delta_per_step", pd.Series(dtype=float)), errors="coerce").fillna(0.0).to_list()]
        projected_delta_intensity = min(1.0, sqrt(sum(v * v for v in deltas)) / max(1.0, sqrt(len(deltas)))) if deltas else 0.0

        residual_context = self._mean_context(ot_context, "ot_residual_score")
        unresolved_context = self._mean_context(ot_context, "ot_unresolved_score")
        mismatch_context = self._mean_context(ot_context, "ot_macro_micro_mismatch_score")
        residual_excess = max(0.0, max(residual_context, unresolved_context, mismatch_context) - 0.12)

        activity = e("activity")
        volatility = e("volatility")
        uncertainty = e("uncertainty")
        exploration = e("exploration")
        lock = e("relation_lock")
        reversibility = e("reversibility")
        entropy = e("entropy")
        rigidity = r("relation_rigidity")
        relation_strength = r("relation_strength")
        flow = r("flow")

        shrink_equilibrium_measure = _mean([
            _pos(-activity),
            _pos(-exploration),
            _pos(-reversibility),
            _pos(-entropy),
            _pos(lock),
            _pos(rigidity),
            _pos(-flow),
            _pos(-volatility),
        ])
        bias_concentration_measure = _mean([
            _pos(es("exploration")),
            _pos(es("entropy")),
            _pos(es("relation_lock")),
            _pos(rs("relation_rigidity")),
            _pos(-rs("flow")),
            _pos(-exploration),
            _pos(-entropy),
            _pos(lock) * 0.5,
            _pos(rigidity) * 0.5,
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
            _pos(-relation_strength),
        ])

        residual_fixation_support = residual_excess * min(1.0, shrink_equilibrium_measure * 18.0)
        fixation = _mean([
            _pos(lock),
            _pos(rigidity),
            _pos(-flow),
            _pos(-reversibility),
            _pos(-activity) * 1.4,
            _pos(-volatility) * 0.8,
            residual_fixation_support,
        ])
        overconvergence = max(0.0, _mean([
            _pos(-exploration),
            _pos(-entropy),
            _pos(-reversibility) * 0.7,
            _pos(lock) * 0.55,
            _pos(rigidity) * 0.55,
            _pos(-flow) * 0.55,
            bias_concentration_measure * 1.6,
        ]) - _pos(-activity) * 0.35 - _pos(-volatility) * 0.15)
        divergence = _mean([
            _pos(volatility),
            _pos(uncertainty),
            _pos(activity),
            _pos(entropy),
            _pos(exploration),
            _pos(flow),
            _pos(-rigidity) * 1.2,
            _pos(-lock) * 1.2,
            _pos(-relation_strength) * 0.8,
            max(0.0, mismatch_context - residual_context * 0.25),
            divergence_release_measure,
        ])

        strengths = {
            "overconvergence": _clamp01(overconvergence),
            "fixation": _clamp01(fixation),
            "divergence": _clamp01(divergence),
        }
        ordered = sorted(strengths.items(), key=lambda kv: kv[1], reverse=True)
        top_strength = float(ordered[0][1]) if ordered else 0.0
        second_strength = float(ordered[1][1]) if len(ordered) > 1 else 0.0
        margin = top_strength - second_strength
        neutral_buffer_distance = projected_delta_intensity
        neutral_buffer_applied = (
            neutral_buffer_distance <= self.cfg.neutral_delta_buffer
            or top_strength <= self.cfg.neutral_strength_buffer
            or (margin <= self.cfg.neutral_margin_buffer and neutral_buffer_distance <= self.cfg.neutral_delta_buffer * 2.0)
        )
        if neutral_buffer_applied:
            direction = "neutral"
            strength = 0.0
            margin = 0.0
        else:
            direction = ordered[0][0] if ordered else "neutral"
            strength = top_strength
        row = {"loop_step": int(loop_step), "run_seed": int(seed), "run_scenario": str(scenario), "prediction_focus": "dynamics_direction_and_strength", "projection_horizon_steps": int(horizon), "predicted_dynamics_direction": direction, "predicted_dynamics_strength": float(strength), "predicted_direction_margin": float(margin), "projected_delta_intensity": float(projected_delta_intensity), "overconvergence_direction_strength": strengths["overconvergence"], "fixation_direction_strength": strengths["fixation"], "divergence_direction_strength": strengths["divergence"], "neutral_buffer_distance": float(neutral_buffer_distance), "neutral_buffer_applied": bool(neutral_buffer_applied), "shrink_equilibrium_measure": float(shrink_equilibrium_measure), "bias_concentration_measure": float(bias_concentration_measure), "divergence_release_measure": float(divergence_release_measure), "direction_strength_json": _json_dict(strengths), "dynamics_projection_role": "direction_strength_only"}
        return pd.DataFrame([row], columns=columns)

    def build_global_prediction_summary(self, *, world_trace_before, baseline_trace_after, gt, kt, ot_native, ot_action_view, residual_noise_log, entity_projection, relation_projection, ot_context, dynamics_projection, loop_step: int, seed: int, scenario: str) -> pd.DataFrame:
        entity = world_trace_before.get("entity_trace", pd.DataFrame()) if world_trace_before else pd.DataFrame()
        relation = world_trace_before.get("relation_trace", pd.DataFrame()) if world_trace_before else pd.DataFrame()
        baseline_entity = baseline_trace_after.get("entity_trace", pd.DataFrame()) if baseline_trace_after else pd.DataFrame()
        baseline_relation = baseline_trace_after.get("relation_trace", pd.DataFrame()) if baseline_trace_after else pd.DataFrame()
        numeric_entity_cols = _numeric_columns(entity, exclude=IDENTITY_COLS)
        numeric_relation_cols = _numeric_columns(relation, exclude=IDENTITY_COLS)
        gt_numeric_cols = _numeric_columns(gt if gt is not None else pd.DataFrame())
        kt_numeric_cols = _numeric_columns(kt if kt is not None else pd.DataFrame())

        def unmapped_cols(df, numeric_cols, extra_exclude=None):
            extra_exclude = extra_exclude or set()
            if df is None or df.empty:
                return []
            return [str(c) for c in df.columns if c not in extra_exclude and c not in numeric_cols and not _is_decision_name(c)][: self.cfg.max_unmapped_columns_recorded]

        dyn = dynamics_projection.iloc[0] if dynamics_projection is not None and not dynamics_projection.empty else {}
        unmapped = {"entity_columns": unmapped_cols(entity, numeric_entity_cols, IDENTITY_COLS), "relation_columns": unmapped_cols(relation, numeric_relation_cols, IDENTITY_COLS), "gt_columns": unmapped_cols(gt, gt_numeric_cols), "kt_columns": unmapped_cols(kt, kt_numeric_cols)}
        row = {"loop_step": int(loop_step), "run_seed": int(seed), "run_scenario": str(scenario), "prediction_module_name": self.name, "prediction_build_status": "pass", "source_trace_fingerprint_current": trace_fingerprint(world_trace_before) if world_trace_before else "missing", "source_trace_fingerprint_projection": trace_fingerprint(baseline_trace_after) if baseline_trace_after else "missing", "world_t_current": _first_world_t(world_trace_before), "world_t_projection": _first_world_t(baseline_trace_after), "entity_rows_current": int(len(entity)), "entity_rows_projection": int(len(baseline_entity)), "relation_rows_current": int(len(relation)), "relation_rows_projection": int(len(baseline_relation)), "gt_rows": int(len(gt)) if gt is not None else 0, "kt_rows": int(len(kt)) if kt is not None else 0, "ot_native_rows": int(len(ot_native)) if ot_native is not None else 0, "ot_action_view_rows": int(len(ot_action_view)) if ot_action_view is not None else 0, "residual_noise_log_rows": int(len(residual_noise_log)) if residual_noise_log is not None else 0, "entity_projection_rows": int(len(entity_projection)), "relation_projection_rows": int(len(relation_projection)), "ot_context_rows": int(len(ot_context)), "dynamics_projection_rows": int(len(dynamics_projection)) if dynamics_projection is not None else 0, "mean_entity_projected_abs_delta": float(entity_projection["projected_no_action_delta"].abs().mean()) if not entity_projection.empty else 0.0, "mean_relation_projected_abs_delta": float(relation_projection["projected_no_action_delta"].abs().mean()) if not relation_projection.empty else 0.0, "mean_observation_uncertainty": self._mean_ot_metric(ot_context, "uncertainty"), "mean_residual_score": self._mean_ot_metric(ot_context, "ot_residual_score"), "mean_unresolved_score": self._mean_ot_metric(ot_context, "ot_unresolved_score"), "mean_ambiguity_score": self._mean_ot_metric(ot_context, "ot_ambiguity_score"), "mean_macro_micro_mismatch_score": self._mean_ot_metric(ot_context, "ot_macro_micro_mismatch_score"), "predicted_dynamics_direction": str(dyn.get("predicted_dynamics_direction", "neutral")) if hasattr(dyn, "get") else "neutral", "predicted_dynamics_strength": float(dyn.get("predicted_dynamics_strength", 0.0)) if hasattr(dyn, "get") else 0.0, "predicted_direction_margin": float(dyn.get("predicted_direction_margin", 0.0)) if hasattr(dyn, "get") else 0.0, "unmapped_information_json": _json_dict(unmapped)}
        for col in numeric_entity_cols:
            row[f"current_mean_entity_{col}"] = float(pd.to_numeric(entity[col], errors="coerce").mean())
        for col in numeric_relation_cols:
            row[f"current_mean_relation_{col}"] = float(pd.to_numeric(relation[col], errors="coerce").mean())
        for col in gt_numeric_cols[:24]:
            row[f"source_gt_{col}"] = float(pd.to_numeric(gt[col], errors="coerce").mean()) if gt is not None and col in gt.columns else 0.0
        for col in kt_numeric_cols[:24]:
            row[f"source_kt_{col}"] = float(pd.to_numeric(kt[col], errors="coerce").mean()) if kt is not None and col in kt.columns else 0.0
        return pd.DataFrame([row])

    def build_prediction_output_packet(self, global_summary: pd.DataFrame, entity_projection: pd.DataFrame, relation_projection: pd.DataFrame, ot_context: pd.DataFrame, dynamics_projection: pd.DataFrame) -> pd.DataFrame:
        if global_summary is None or global_summary.empty:
            return pd.DataFrame()
        g = global_summary.iloc[0]
        d = dynamics_projection.iloc[0] if dynamics_projection is not None and not dynamics_projection.empty else {}
        row = {"loop_step": int(g.get("loop_step", -1)), "run_seed": int(g.get("run_seed", -1)), "run_scenario": str(g.get("run_scenario", "unknown")), "prediction_packet_id": f"dept_prediction_packet_s{int(g.get('run_seed', -1))}_t{int(g.get('loop_step', -1))}", "source_trace_fingerprint_current": str(g.get("source_trace_fingerprint_current", "missing")), "source_trace_fingerprint_projection": str(g.get("source_trace_fingerprint_projection", "missing")), "world_t_current": int(g.get("world_t_current", -1)), "world_t_projection": int(g.get("world_t_projection", -1)), "entity_projection_rows": int(len(entity_projection)), "relation_projection_rows": int(len(relation_projection)), "ot_context_rows": int(len(ot_context)), "dynamics_projection_rows": int(len(dynamics_projection)) if dynamics_projection is not None else 0, "mean_entity_projected_abs_delta": float(g.get("mean_entity_projected_abs_delta", 0.0)), "mean_relation_projected_abs_delta": float(g.get("mean_relation_projected_abs_delta", 0.0)), "mean_observation_uncertainty": float(g.get("mean_observation_uncertainty", 0.0)), "mean_residual_score": float(g.get("mean_residual_score", 0.0)), "mean_unresolved_score": float(g.get("mean_unresolved_score", 0.0)), "mean_ambiguity_score": float(g.get("mean_ambiguity_score", 0.0)), "mean_macro_micro_mismatch_score": float(g.get("mean_macro_micro_mismatch_score", 0.0)), "predicted_dynamics_direction": str(d.get("predicted_dynamics_direction", "neutral")) if hasattr(d, "get") else "neutral", "predicted_dynamics_strength": float(d.get("predicted_dynamics_strength", 0.0)) if hasattr(d, "get") else 0.0, "predicted_direction_margin": float(d.get("predicted_direction_margin", 0.0)) if hasattr(d, "get") else 0.0, "packet_content_type": "prediction_dynamics_direction_strength"}
        return pd.DataFrame([row])

    @staticmethod
    def _latest_by_entity(df: pd.DataFrame | None) -> pd.DataFrame:
        if df is None or df.empty or "entity_id" not in df.columns:
            return pd.DataFrame()
        sort_cols = [c for c in ["t", "last_seen_t", "loop_step"] if c in df.columns]
        out = df.copy()
        if sort_cols:
            out = out.sort_values(sort_cols)
        return out.drop_duplicates("entity_id", keep="last").set_index("entity_id")

    @staticmethod
    def _mean_ot_metric(ot_context: pd.DataFrame, metric_name: str) -> float:
        if ot_context is None or ot_context.empty:
            return 0.0
        rows = ot_context[ot_context["context_metric_name"].astype(str) == str(metric_name)]
        if rows.empty:
            return 0.0
        return float(pd.to_numeric(rows["context_metric_value"], errors="coerce").fillna(0.0).mean())

    @staticmethod
    def _mean_context(ot_context: pd.DataFrame, metric_name: str) -> float:
        return DEPTPredictionModule._mean_ot_metric(ot_context, metric_name)

    @staticmethod
    def _mean_entity_delta(entity_projection: pd.DataFrame, metric_name: str) -> float:
        if entity_projection is None or entity_projection.empty:
            return 0.0
        rows = entity_projection[entity_projection["metric_name"].astype(str) == str(metric_name)]
        if rows.empty:
            return 0.0
        return float(pd.to_numeric(rows["projected_no_action_delta_per_step"], errors="coerce").fillna(0.0).mean())

    @staticmethod
    def _mean_relation_delta(relation_projection: pd.DataFrame, metric_name: str) -> float:
        if relation_projection is None or relation_projection.empty:
            return 0.0
        rows = relation_projection[relation_projection["relation_metric_name"].astype(str) == str(metric_name)]
        if rows.empty:
            return 0.0
        return float(pd.to_numeric(rows["projected_no_action_delta_per_step"], errors="coerce").fillna(0.0).mean())

    @staticmethod
    def _entity_spread_delta(entity_projection: pd.DataFrame, metric_name: str) -> float:
        if entity_projection is None or entity_projection.empty:
            return 0.0
        rows = entity_projection[entity_projection["metric_name"].astype(str) == str(metric_name)]
        if rows.empty:
            return 0.0
        current = pd.to_numeric(rows["current_value"], errors="coerce").fillna(0.0)
        projected = pd.to_numeric(rows["projected_no_action_value"], errors="coerce").fillna(0.0)
        return float(projected.std(ddof=0) - current.std(ddof=0))

    @staticmethod
    def _relation_spread_delta(relation_projection: pd.DataFrame, metric_name: str) -> float:
        if relation_projection is None or relation_projection.empty:
            return 0.0
        rows = relation_projection[relation_projection["relation_metric_name"].astype(str) == str(metric_name)]
        if rows.empty:
            return 0.0
        current = pd.to_numeric(rows["current_value"], errors="coerce").fillna(0.0)
        projected = pd.to_numeric(rows["projected_no_action_value"], errors="coerce").fillna(0.0)
        return float(projected.std(ddof=0) - current.std(ddof=0))


def output_contains_judgment_terms(outputs: dict[str, pd.DataFrame]) -> bool:
    for table_name, df in outputs.items():
        if _is_decision_name(table_name):
            return True
        if df is None or df.empty:
            continue
        for col in df.columns:
            if _is_decision_name(col):
                return True
        text_values = df.select_dtypes(include=["object"]).astype(str)
        for value in text_values.to_numpy().flatten().tolist():
            if _is_decision_name(value):
                return True
    return False
