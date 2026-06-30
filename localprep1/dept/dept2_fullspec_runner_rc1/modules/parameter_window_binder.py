"""parameter_window_binder: Task22C-Rev1-Q2-U minimal ParameterBox -> module window binding.

This module binds updated ParameterBox values to module-owned parameter windows.
It is not a new upper-pressure route.

Allowed inputs:
  - current_params from ParameterShadowBox.current_params()
  - shadow_parameter_state emitted by ParameterShadowBox

Forbidden:
  - upper pressure / H11 field / G/K / O_t / action candidates / world trace
  - ActionModule calls
  - world, G/K, O_t, canonical parameter, or ActionFrame writes
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, asdict
from typing import Any, Mapping

import pandas as pd


REGISTRY = {
    "action_intensity_cap": (0.55, 0.25, 0.85),
    "action_sparsity_threshold": (0.16, 0.06, 0.35),
    "v8_activation_threshold": (0.42, 0.20, 0.75),
    "conflict_penalty_weight": (0.60, 0.20, 1.00),
    "unresolved_penalty_weight": (0.50, 0.15, 0.95),
    "shadow_threshold": (0.48, 0.25, 0.80),
    "rollback_sensitivity": (0.55, 0.25, 0.95),
    "graph_update_rate": (0.18, 0.05, 0.40),
    "exploration_gain": (0.38, 0.05, 0.80),
    "damping_gain": (0.42, 0.08, 0.85),
    "unlock_gain": (0.36, 0.05, 0.80),
    "buffer_gain": (0.34, 0.05, 0.80),
}


def _clip(x: float, lo: float, hi: float) -> float:
    try:
        return max(lo, min(hi, float(x)))
    except Exception:
        return float(lo)


def _clip_int(x: float, lo: int, hi: int) -> int:
    return int(max(lo, min(hi, round(float(x)))))


def _fingerprint_mapping(values: Mapping[str, Any]) -> str:
    if not values:
        return "empty"
    payload = json.dumps(values, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _fingerprint_df(df: pd.DataFrame | None) -> str:
    if df is None or df.empty:
        return "empty"
    payload = pd.util.hash_pandas_object(df.sort_index(axis=1), index=True).values.tobytes()
    return hashlib.sha256(payload).hexdigest()[:16]


def theta(params: Mapping[str, float], name: str) -> float:
    theta0, lo, hi = REGISTRY[name]
    return _clip(float(params.get(name, theta0)), lo, hi)


def d(params: Mapping[str, float], name: str) -> float:
    theta0, lo, hi = REGISTRY[name]
    return _clip((theta(params, name) - theta0) / max(hi - lo, 1e-12), -1.0, 1.0)


@dataclass
class ExplorationWindowValues:
    candidate_budget: int
    sandbox_entry_threshold: float
    pass_threshold: float
    watch_threshold: float
    max_noise_risk: float
    max_topology_break_risk: float


@dataclass
class ActionWindowValues:
    action_affordance_floor: float
    candidate_sparsity_threshold: float
    max_action_strength: float
    strength_scale: float
    channel_gain_map: dict[str, float]


@dataclass
class GateWindowValues:
    gate_dampen_threshold: float
    gate_defer_threshold: float
    gate_block_threshold: float


class ParameterWindowBinder:
    name = "parameter_window_binder"

    def bind(
        self,
        current_params: Mapping[str, float],
        shadow_parameter_state: pd.DataFrame,
        *,
        loop_step: int | None = None,
    ) -> dict[str, Any]:
        """Return module window values and an audit row.

        This function only binds already-updated ParameterBox values to module-owned
        windows. It never reads upper pressure directly and never writes to canonical
        parameters, world, G/K, O_t, ActionFrame, or ActionModule.
        """
        params = {k: theta(current_params, k) for k in REGISTRY}
        shadow_state = self._normalize_shadow_state(shadow_parameter_state)
        module_window_values = {
            "exploration": asdict(self._exploration_windows(params)),
            "local_audit": self._local_audit_params(params),
            "action": asdict(self._action_windows(params)),
            "bridge": self._bridge_params(params),
            "gate": asdict(self._gate_windows(params)),
        }
        audit = self._audit(params, shadow_state, module_window_values, loop_step)
        return {
            "module_window_values": module_window_values,
            "shadow_parameter_state": shadow_state,
            "parameter_window_binding_audit": audit,
        }

    def _normalize_shadow_state(self, shadow_state: pd.DataFrame | None) -> pd.DataFrame:
        if shadow_state is None:
            shadow_state = pd.DataFrame()
        out = shadow_state.copy()
        if out.empty:
            return out
        if "shadow_theta_delta_from_previous" in out.columns:
            delta = pd.to_numeric(out["shadow_theta_delta_from_previous"], errors="coerce").fillna(0.0).abs()
            # Compatibility columns for coactivation gate.
            out["theta_delta_abs"] = delta
            out["bounded_delta_abs"] = delta
            out["abs_delta"] = delta
        elif "theta_delta" in out.columns:
            delta = pd.to_numeric(out["theta_delta"], errors="coerce").fillna(0.0).abs()
            out["theta_delta_abs"] = delta
            out["bounded_delta_abs"] = delta
            out["abs_delta"] = delta
        else:
            out["theta_delta_abs"] = 0.0
            out["bounded_delta_abs"] = 0.0
            out["abs_delta"] = 0.0
        out["parameter_window_binding_normalized"] = True
        return out

    def _exploration_windows(self, params: Mapping[str, float]) -> ExplorationWindowValues:
        return ExplorationWindowValues(
            candidate_budget=_clip_int(
                6 + 4*d(params, "exploration_gain") + 2*d(params, "graph_update_rate") - 2*d(params, "rollback_sensitivity"),
                3, 10,
            ),
            sandbox_entry_threshold=_clip(
                0.34 - 0.06*d(params, "exploration_gain") + 0.03*d(params, "action_sparsity_threshold") + 0.04*d(params, "rollback_sensitivity"),
                0.25, 0.46,
            ),
            pass_threshold=_clip(
                0.50 - 0.03*d(params, "exploration_gain") + 0.05*d(params, "rollback_sensitivity") + 0.03*d(params, "action_sparsity_threshold"),
                0.42, 0.62,
            ),
            watch_threshold=_clip(
                0.34 - 0.02*d(params, "exploration_gain") + 0.03*d(params, "rollback_sensitivity"),
                0.28, 0.42,
            ),
            max_noise_risk=_clip(
                0.72 - 0.08*d(params, "rollback_sensitivity") + 0.03*d(params, "buffer_gain") + 0.02*d(params, "exploration_gain"),
                0.55, 0.78,
            ),
            max_topology_break_risk=_clip(
                0.72 - 0.09*d(params, "rollback_sensitivity") + 0.04*d(params, "buffer_gain") - 0.02*d(params, "graph_update_rate"),
                0.55, 0.78,
            ),
        )

    def _local_audit_params(self, params: Mapping[str, float]) -> dict[str, float]:
        return {
            "v8_activation_threshold": theta(params, "v8_activation_threshold"),
            "conflict_weight": _clip(theta(params, "conflict_penalty_weight") / 0.60, 0.50, 1.60),
            "unresolved_weight": _clip(theta(params, "unresolved_penalty_weight") / 0.50, 0.50, 1.60),
        }

    def _action_windows(self, params: Mapping[str, float]) -> ActionWindowValues:
        channel_gain_map = {
            "exploration_injection": _clip(1 + 0.35*d(params, "exploration_gain"), 0.75, 1.30),
            "uncertainty_probe": _clip(1 + 0.20*d(params, "exploration_gain"), 0.80, 1.20),
            "volatility_damping": _clip(1 + 0.35*d(params, "damping_gain"), 0.75, 1.30),
            "relation_unlock": _clip(1 + 0.35*d(params, "unlock_gain"), 0.75, 1.30),
            "guarded_relation_unlock": _clip(1 + 0.35*d(params, "unlock_gain"), 0.75, 1.30),
            "coupling_relief": _clip(1 + 0.25*d(params, "unlock_gain"), 0.80, 1.25),
            "buffer_increase": _clip(1 + 0.35*d(params, "buffer_gain"), 0.75, 1.30),
            "diagnostic_exploration_restraint": _clip(1 + 0.35*d(params, "buffer_gain"), 0.75, 1.30),
            "diagnostic_update_restraint": _clip(1 + 0.35*d(params, "buffer_gain"), 0.75, 1.30),
            "diagnostic_probe_restraint_direct": _clip(1 + 0.35*d(params, "buffer_gain"), 0.75, 1.30),
        }
        return ActionWindowValues(
            action_affordance_floor=_clip(
                0.025 + 0.020*d(params, "action_sparsity_threshold") - 0.010*d(params, "exploration_gain"),
                0.010, 0.060,
            ),
            candidate_sparsity_threshold=theta(params, "action_sparsity_threshold"),
            max_action_strength=_clip(
                0.030 * _clip(theta(params, "action_intensity_cap") / 0.55, 0.60, 1.35) * _clip(1 - 0.20*d(params, "rollback_sensitivity"), 0.80, 1.10),
                0.015, 0.045,
            ),
            strength_scale=_clip(
                0.12 * _clip(theta(params, "action_intensity_cap") / 0.55, 0.75, 1.25) * _clip(1 + 0.10*d(params, "buffer_gain"), 0.90, 1.10),
                0.08, 0.16,
            ),
            channel_gain_map=channel_gain_map,
        )

    def _bridge_params(self, params: Mapping[str, float]) -> dict[str, float]:
        return {
            "projection_adoption_threshold": _clip(
                0.34 + 0.03*d(params, "action_sparsity_threshold") + 0.03*d(params, "rollback_sensitivity") - 0.06*d(params, "exploration_gain"),
                0.28, 0.45,
            )
        }

    def _gate_windows(self, params: Mapping[str, float]) -> GateWindowValues:
        dampen = _clip(
            0.36 - 0.04*d(params, "rollback_sensitivity") - 0.03*d(params, "conflict_penalty_weight") + 0.02*d(params, "shadow_threshold"),
            0.28, 0.46,
        )
        defer = _clip(
            0.64 - 0.06*d(params, "rollback_sensitivity") - 0.04*d(params, "conflict_penalty_weight") + 0.03*d(params, "shadow_threshold"),
            0.54, 0.74,
        )
        block = _clip(
            0.82 - 0.08*d(params, "rollback_sensitivity") - 0.05*d(params, "conflict_penalty_weight") + 0.04*d(params, "shadow_threshold"),
            0.72, 0.90,
        )
        defer = max(defer, dampen + 0.08)
        block = max(block, defer + 0.08)
        return GateWindowValues(dampen, defer, block)

    def _audit(
        self,
        params: Mapping[str, float],
        shadow_state: pd.DataFrame,
        windows: Mapping[str, Any],
        loop_step: int | None,
    ) -> pd.DataFrame:
        flat = {
            "exploration_candidate_budget": windows["exploration"]["candidate_budget"],
            "exploration_sandbox_entry_threshold": windows["exploration"]["sandbox_entry_threshold"],
            "exploration_pass_threshold": windows["exploration"]["pass_threshold"],
            "action_affordance_floor": windows["action"]["action_affordance_floor"],
            "candidate_sparsity_threshold": windows["action"]["candidate_sparsity_threshold"],
            "max_action_strength": windows["action"]["max_action_strength"],
            "strength_scale": windows["action"]["strength_scale"],
            "projection_adoption_threshold": windows["bridge"]["projection_adoption_threshold"],
            "gate_dampen_threshold": windows["gate"]["gate_dampen_threshold"],
            "gate_defer_threshold": windows["gate"]["gate_defer_threshold"],
            "gate_block_threshold": windows["gate"]["gate_block_threshold"],
            "v8_activation_threshold": windows["local_audit"]["v8_activation_threshold"],
            "conflict_weight": windows["local_audit"]["conflict_weight"],
            "unresolved_weight": windows["local_audit"]["unresolved_weight"],
        }
        return pd.DataFrame([{
            "parameter_window_binding_contract": "Task22C_Rev1_Q2U_bind_ParameterBox_values_to_module_owned_windows__no_upper_pressure_route__RC1",
            "loop_step": -1 if loop_step is None else int(loop_step),
            "binding_source": "ParameterShadowBox.current_params_and_shadow_parameter_state_only",
            "current_params_fingerprint": _fingerprint_mapping(params),
            "shadow_parameter_state_fingerprint": _fingerprint_df(shadow_state),
            "module_window_values_fingerprint": _fingerprint_mapping(windows),
            "parameter_windows_bound": True,
            "upper_pressure_read_by_binder": False,
            "h11_pressure_read_by_binder": False,
            "gk_read_by_binder": False,
            "ot_read_by_binder": False,
            "action_candidates_read_by_binder": False,
            "actionmodule_called_by_binder": False,
            "action_frame_created_by_binder": False,
            "canonical_parameter_write_performed": False,
            "world_write_performed": False,
            "gk_writeback_performed": False,
            "ot_writeback_performed": False,
            "audit_status": "pass",
            **flat,
        }])
