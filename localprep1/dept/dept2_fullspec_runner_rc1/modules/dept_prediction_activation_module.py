"""dept_prediction_activation_module: low-cost trigger control for DEPT prediction.

This module is DEPT-side and always cheap. It does not perform the projection
simulation itself. It reads current observation/log summaries, maintains a small
history, and decides only the computation tier for the prediction module.

Signals tracked here are dynamics quantities: short angle, short intensity,
acceleration, curvature, and short/mid direction integrals for overconvergence,
fixation, and divergence.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from math import sqrt
from typing import Dict

import pandas as pd

from dept2_fullspec_runner_rc1.modules.world_adapter import trace_fingerprint


@dataclass(frozen=True)
class PredictionActivationConfig:
    short_window: int = 3
    mid_window: int = 8
    initial_reference_score: float = 1.0
    standard_threshold: float = 0.22
    deep_threshold: float = 0.48
    stale_interval: int = 6
    eps: float = 1e-9


FEATURES = [
    "activity",
    "volatility",
    "uncertainty",
    "exploration",
    "relation_lock",
    "reversibility",
    "entropy",
    "readiness",
    "relation_strength",
    "relation_rigidity",
    "flow",
    "ot_residual_score",
    "ot_unresolved_score",
    "ot_ambiguity_score",
    "ot_macro_micro_mismatch_score",
    "ot_boundary_instability_score",
]


class DEPTPredictionActivationModule:
    name = "dept_prediction_activation_module"

    def __init__(self, cfg: PredictionActivationConfig | None = None):
        self.cfg = cfg or PredictionActivationConfig()
        self._aggregate_history: deque[dict[str, float]] = deque(maxlen=self.cfg.mid_window + 1)
        self._delta_history: deque[dict[str, float]] = deque(maxlen=self.cfg.mid_window)
        self._direction_history: deque[dict[str, float]] = deque(maxlen=self.cfg.mid_window)
        self._last_projection_loop_step: int | None = None

    def build(
        self,
        *,
        world_trace_before: Dict[str, pd.DataFrame] | None,
        gt: pd.DataFrame | None,
        kt: pd.DataFrame | None,
        ot_native: pd.DataFrame | None,
        ot_action_view: pd.DataFrame | None,
        residual_noise_log: pd.DataFrame | None,
        loop_step: int,
        seed: int,
        scenario: str,
    ) -> pd.DataFrame:
        current = self._build_current_aggregate(
            world_trace_before=world_trace_before,
            gt=gt,
            kt=kt,
            ot_native=ot_native,
            ot_action_view=ot_action_view,
            residual_noise_log=residual_noise_log,
        )
        previous = self._aggregate_history[-1] if self._aggregate_history else None
        previous_delta = self._delta_history[-1] if self._delta_history else None
        delta = self._delta(current, previous)
        short_intensity = self._norm(delta)
        short_angle = self._angle_change(delta, previous_delta)
        short_acceleration = self._norm(self._delta(delta, previous_delta))
        short_curvature = min(1.0, short_angle * (1.0 + short_intensity))
        direction_step = self._direction_step(current, delta, short_intensity)

        self._aggregate_history.append(current)
        self._delta_history.append(delta)
        self._direction_history.append(direction_step)

        direction_integrals = self._direction_integrals()
        direction_consistency = self._direction_consistency()
        first_reference_score = self.cfg.initial_reference_score if self._last_projection_loop_step is None else 0.0
        stale_score = 0.0
        if self._last_projection_loop_step is not None:
            stale_score = min(1.0, max(0, int(loop_step) - int(self._last_projection_loop_step)) / max(1, self.cfg.stale_interval))

        immediate_score = max(short_intensity, short_angle, short_acceleration, short_curvature)
        integral_score = max(
            direction_integrals["overconvergence_integral_mid"],
            direction_integrals["fixation_integral_mid"],
            direction_integrals["divergence_integral_mid"],
            direction_integrals["overconvergence_integral_short"],
            direction_integrals["fixation_integral_short"],
            direction_integrals["divergence_integral_short"],
        )
        prediction_need_score = max(immediate_score, integral_score, stale_score, first_reference_score)
        standard_projection_requested = bool(prediction_need_score >= self.cfg.standard_threshold)
        detailed_projection_requested = bool(
            prediction_need_score >= self.cfg.deep_threshold
            or (immediate_score >= self.cfg.standard_threshold and integral_score >= self.cfg.standard_threshold)
        )
        if detailed_projection_requested:
            computation_tier = "deep_projection"
        elif standard_projection_requested:
            computation_tier = "standard_projection"
        else:
            computation_tier = "cheap_monitor"
        if standard_projection_requested:
            self._last_projection_loop_step = int(loop_step)

        row = {
            "loop_step": int(loop_step),
            "run_seed": int(seed),
            "run_scenario": str(scenario),
            "activation_module_name": self.name,
            "source_trace_fingerprint_current": trace_fingerprint(world_trace_before) if world_trace_before else "missing",
            "history_observation_count": int(len(self._aggregate_history)),
            "short_window": int(self.cfg.short_window),
            "mid_window": int(self.cfg.mid_window),
            "short_intensity_change": float(short_intensity),
            "short_angle_change": float(short_angle),
            "short_acceleration": float(short_acceleration),
            "short_curvature": float(short_curvature),
            "immediate_trigger_score": float(immediate_score),
            **{k: float(v) for k, v in direction_step.items()},
            **{k: float(v) for k, v in direction_integrals.items()},
            **{k: float(v) for k, v in direction_consistency.items()},
            "integral_trigger_score": float(integral_score),
            "stale_projection_score": float(stale_score),
            "initial_reference_score": float(first_reference_score),
            "prediction_need_score": float(prediction_need_score),
            "standard_projection_requested": bool(standard_projection_requested),
            "detailed_projection_requested": bool(detailed_projection_requested),
            "prediction_computation_tier": computation_tier,
            "activation_output_role": "compute_tier_only",
        }
        return pd.DataFrame([row])

    def _build_current_aggregate(self, *, world_trace_before, gt, kt, ot_native, ot_action_view, residual_noise_log) -> dict[str, float]:
        entity = world_trace_before.get("entity_trace", pd.DataFrame()) if world_trace_before else pd.DataFrame()
        relation = world_trace_before.get("relation_trace", pd.DataFrame()) if world_trace_before else pd.DataFrame()
        aggregate = {f: 0.0 for f in FEATURES}
        for col in ["activity", "volatility", "uncertainty", "exploration", "relation_lock", "reversibility", "entropy", "readiness"]:
            aggregate[col] = self._mean(entity, col)
        for col in ["relation_strength", "relation_rigidity", "flow"]:
            aggregate[col] = self._mean(relation, col)
        source_ot = ot_action_view if ot_action_view is not None and not ot_action_view.empty else ot_native
        aggregate["ot_residual_score"] = self._mean(source_ot, "ot_residual_score")
        aggregate["ot_unresolved_score"] = self._mean(source_ot, "ot_unresolved_score")
        aggregate["ot_ambiguity_score"] = self._mean(source_ot, "ot_ambiguity_score")
        aggregate["ot_macro_micro_mismatch_score"] = self._mean(source_ot, "ot_macro_micro_mismatch_score")
        aggregate["ot_boundary_instability_score"] = self._mean(source_ot, "ot_boundary_instability_score")
        if residual_noise_log is not None and not residual_noise_log.empty:
            for col in ["ot_residual_score", "ot_unresolved_score", "ot_ambiguity_score", "ot_macro_micro_mismatch_score", "ot_boundary_instability_score"]:
                aggregate[col] = max(aggregate[col], self._mean(residual_noise_log, col))
        aggregate["gt_uncertainty"] = self._mean(gt, "gt_uncertainty")
        aggregate["kt_uncertainty_slope"] = abs(self._mean(kt, "kt_uncertainty_slope"))
        aggregate["kt_exploration_slope"] = abs(self._mean(kt, "kt_exploration_slope"))
        return aggregate

    def _direction_step(self, current: dict[str, float], delta: dict[str, float], short_intensity: float) -> dict[str, float]:
        residual_pressure = max(
            current.get("ot_residual_score", 0.0),
            current.get("ot_unresolved_score", 0.0),
            current.get("ot_macro_micro_mismatch_score", 0.0),
        )
        low_motion = max(0.0, 1.0 - min(1.0, short_intensity * 4.0))
        over = self._avg([
            self._pos(-delta.get("entropy", 0.0)),
            self._pos(-delta.get("exploration", 0.0)),
            self._pos(-delta.get("reversibility", 0.0)),
            self._pos(delta.get("relation_lock", 0.0)),
            self._pos(delta.get("relation_rigidity", 0.0)),
            self._pos(-delta.get("flow", 0.0)),
        ])
        fix = self._avg([
            self._pos(delta.get("relation_lock", 0.0)),
            self._pos(delta.get("relation_rigidity", 0.0)),
            self._pos(-delta.get("flow", 0.0)),
            self._pos(-delta.get("reversibility", 0.0)),
            residual_pressure * low_motion,
        ])
        div = self._avg([
            self._pos(delta.get("volatility", 0.0)),
            self._pos(delta.get("uncertainty", 0.0)),
            self._pos(delta.get("ot_residual_score", 0.0)),
            self._pos(delta.get("ot_macro_micro_mismatch_score", 0.0)),
            self._pos(delta.get("ot_boundary_instability_score", 0.0)),
            self._pos(delta.get("flow", 0.0)),
        ])
        return {
            "overconvergence_step": float(min(1.0, over)),
            "fixation_step": float(min(1.0, fix)),
            "divergence_step": float(min(1.0, div)),
        }

    def _direction_integrals(self) -> dict[str, float]:
        short_rows = list(self._direction_history)[-self.cfg.short_window :]
        mid_rows = list(self._direction_history)[-self.cfg.mid_window :]
        return {
            "overconvergence_integral_short": self._window_mean(short_rows, "overconvergence_step"),
            "fixation_integral_short": self._window_mean(short_rows, "fixation_step"),
            "divergence_integral_short": self._window_mean(short_rows, "divergence_step"),
            "overconvergence_integral_mid": self._window_mean(mid_rows, "overconvergence_step"),
            "fixation_integral_mid": self._window_mean(mid_rows, "fixation_step"),
            "divergence_integral_mid": self._window_mean(mid_rows, "divergence_step"),
        }

    def _direction_consistency(self) -> dict[str, float]:
        rows = list(self._direction_history)[-self.cfg.mid_window :]
        if not rows:
            return {"overconvergence_direction_consistency": 0.0, "fixation_direction_consistency": 0.0, "divergence_direction_consistency": 0.0}
        return {
            "overconvergence_direction_consistency": self._fraction_positive(rows, "overconvergence_step"),
            "fixation_direction_consistency": self._fraction_positive(rows, "fixation_step"),
            "divergence_direction_consistency": self._fraction_positive(rows, "divergence_step"),
        }

    def _delta(self, current: dict[str, float] | None, previous: dict[str, float] | None) -> dict[str, float]:
        keys = set((current or {}).keys()) | set((previous or {}).keys())
        return {k: float((current or {}).get(k, 0.0) - (previous or {}).get(k, 0.0)) for k in keys}

    def _norm(self, values: dict[str, float] | None) -> float:
        if not values:
            return 0.0
        return min(1.0, sqrt(sum(float(v) ** 2 for v in values.values())) / max(1.0, sqrt(len(values))))

    def _angle_change(self, current_delta: dict[str, float], previous_delta: dict[str, float] | None) -> float:
        if not previous_delta:
            return 0.0
        keys = set(current_delta.keys()) | set(previous_delta.keys())
        dot = sum(float(current_delta.get(k, 0.0)) * float(previous_delta.get(k, 0.0)) for k in keys)
        n1 = sqrt(sum(float(current_delta.get(k, 0.0)) ** 2 for k in keys))
        n2 = sqrt(sum(float(previous_delta.get(k, 0.0)) ** 2 for k in keys))
        if n1 <= self.cfg.eps or n2 <= self.cfg.eps:
            return 0.0
        cosine = max(-1.0, min(1.0, dot / (n1 * n2)))
        return float((1.0 - cosine) / 2.0)

    @staticmethod
    def _mean(df: pd.DataFrame | None, col: str) -> float:
        if df is None or df.empty or col not in df.columns:
            return 0.0
        return float(pd.to_numeric(df[col], errors="coerce").fillna(0.0).mean())

    @staticmethod
    def _pos(value: float) -> float:
        return max(0.0, float(value))

    @staticmethod
    def _avg(values: list[float]) -> float:
        return float(sum(values) / max(1, len(values)))

    @staticmethod
    def _window_mean(rows: list[dict[str, float]], key: str) -> float:
        if not rows:
            return 0.0
        return float(sum(float(r.get(key, 0.0)) for r in rows) / len(rows))

    @staticmethod
    def _fraction_positive(rows: list[dict[str, float]], key: str) -> float:
        if not rows:
            return 0.0
        return float(sum(1 for r in rows if float(r.get(key, 0.0)) > 0.0) / len(rows))
