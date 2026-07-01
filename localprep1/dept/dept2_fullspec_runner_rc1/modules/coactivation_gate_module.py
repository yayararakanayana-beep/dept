"""coactivation_gate_module: full same-step coactivation gate integration.

Task12 strengthens the previous narrow gate into an auditable same-step
coactivation gate.  The gate still does not solve all combined-interference
problems; it is a bounded pre-ActionFrame safety valve that classifies the
current cycle into allow / dampen / defer / block / monitor_only.

Inputs are deliberately restricted to summaries that are already safe to read:
weak pressure, thin exploration projection, pre-gate action candidates,
action-side local audit, shadow parameter state, and retained residual/noise
log.  The gate does not call ActionModule, does not build ActionFrame, and does
not write to world/G/K/O_t/canonical parameters.
"""
from __future__ import annotations

import json
from hashlib import sha256
import numpy as np
import pandas as pd


def _rows(df: pd.DataFrame | None) -> int:
    return int(len(df)) if df is not None else 0


def _safe_float_series(df: pd.DataFrame | None, col: str) -> pd.Series:
    if df is None or df.empty or col not in df.columns:
        return pd.Series([], dtype=float)
    return pd.to_numeric(df[col], errors="coerce").fillna(0.0).astype(float)


def _max(df: pd.DataFrame | None, col: str) -> float:
    s = _safe_float_series(df, col)
    return float(s.max()) if len(s) else 0.0


def _mean(df: pd.DataFrame | None, col: str) -> float:
    s = _safe_float_series(df, col)
    return float(s.mean()) if len(s) else 0.0


def _sum(df: pd.DataFrame | None, col: str) -> float:
    s = _safe_float_series(df, col)
    return float(s.sum()) if len(s) else 0.0


def _fingerprint_df(df: pd.DataFrame | None) -> str:
    if df is None or df.empty:
        return "empty"
    payload = {
        "rows": int(len(df)),
        "columns": list(map(str, df.columns)),
        "head": df.head(40).astype(str).to_dict(orient="records"),
    }
    return sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


class CoactivationGateModule:
    name = "coactivation_gate_module"

    def evaluate(
        self,
        weak_pressure: pd.DataFrame,
        exploration_projection: pd.DataFrame,
        action_candidates: pd.DataFrame,
        action_local_audit: pd.DataFrame,
        shadow_params: pd.DataFrame,
        residual_noise_log: pd.DataFrame,
        parameter_windows: dict | None = None,
    ) -> pd.DataFrame:
        """Classify same-step coactivation before ActionFrame construction.

        Decision logic is intentionally transparent and audit-first:
        - monitor_only when no action candidates exist.
        - block for very high coactivation risk or explicit hard danger.
        - defer for high risk that should not be acted on this step.
        - dampen for moderate pressure/exploration/action/noise coactivation.
        - allow for low coactivation risk.
        """
        action_rows = _rows(action_candidates)
        parameter_windows = parameter_windows or {}
        gate_dampen_threshold = float(parameter_windows.get("gate_dampen_threshold", 0.36))
        gate_defer_threshold = float(parameter_windows.get("gate_defer_threshold", 0.64))
        gate_block_threshold = float(parameter_windows.get("gate_block_threshold", 0.82))
        gate_dampening_factor_effective = float(parameter_windows.get("gate_dampening_factor_effective", 0.50))
        gate_threshold_mode = str(parameter_windows.get("gate_threshold_mode", "current"))

        pressure_rows = _rows(weak_pressure)
        projection_rows = _rows(exploration_projection)
        local_audit_rows = _rows(action_local_audit)
        shadow_rows = _rows(shadow_params)
        noise_rows = _rows(residual_noise_log)

        pressure_l1 = _mean(weak_pressure, "approved_component_l1")
        pressure_peak = _max(weak_pressure, "approved_component_l1")
        exploration_active = bool(projection_rows > 0)
        exploration_intensity = max(
            _max(exploration_projection, "projection_intensity"),
            _max(exploration_projection, "action_projection_strength"),
            _mean(exploration_projection, "projection_strength"),
            0.20 if exploration_active else 0.0,
        )
        action_strength_max = _max(action_candidates, "action_strength")
        action_strength_mean = _mean(action_candidates, "action_strength")
        candidate_risk_max = max(
            _max(action_candidates, "candidate_risk"),
            _max(action_candidates, "risk_score"),
            _max(action_candidates, "route_risk"),
        )
        max_conflict = _max(action_local_audit, "v8_conflict")
        max_unresolved = _max(action_local_audit, "v8_unresolved")
        max_noise = _max(residual_noise_log, "ot_noise_score")
        unresolved_noise_rows = int(residual_noise_log[residual_noise_log.get("noise_status", pd.Series([], dtype=str)).astype(str).str.contains("unresolved|active", case=False, regex=True)].shape[0]) if residual_noise_log is not None and not residual_noise_log.empty and "noise_status" in residual_noise_log.columns else 0
        shadow_delta = max(_max(shadow_params, "abs_delta"), _max(shadow_params, "theta_delta_abs"), _max(shadow_params, "bounded_delta_abs"))
        shadow_total_abs_delta = max(_sum(shadow_params, "abs_delta"), _sum(shadow_params, "theta_delta_abs"), _sum(shadow_params, "bounded_delta_abs"))
        shadow_active = bool(shadow_rows > 0 and (shadow_delta > 0 or shadow_total_abs_delta > 0))

        # Component scores are clipped separately so the audit can reveal which
        # coactivation source dominated the final decision.
        pressure_component = float(np.clip(0.55 * pressure_l1 + 0.45 * pressure_peak, 0.0, 1.0))
        exploration_component = float(np.clip(exploration_intensity + (0.08 if exploration_active else 0.0), 0.0, 1.0))
        action_component = float(np.clip(0.55 * action_strength_max + 0.25 * action_strength_mean + 0.20 * candidate_risk_max, 0.0, 1.0))
        local_risk_component = float(np.clip(0.55 * max_conflict + 0.45 * max_unresolved, 0.0, 1.0))
        noise_component = float(np.clip(max_noise + min(unresolved_noise_rows, 12) * 0.015, 0.0, 1.0))
        shadow_component = float(np.clip(shadow_delta + min(shadow_total_abs_delta, 1.0) * 0.08 + (0.04 if shadow_active else 0.0), 0.0, 1.0))

        coactivation_pair_bonus = 0.0
        active_components = [
            pressure_component > 0.20,
            exploration_component > 0.20,
            action_component > 0.20,
            local_risk_component > 0.20,
            noise_component > 0.20,
            shadow_component > 0.20,
        ]
        coactivation_pair_bonus = min(0.18, max(0, sum(active_components) - 2) * 0.045)

        coactivation_risk_score = float(np.clip(
            0.22 * pressure_component
            + 0.16 * exploration_component
            + 0.20 * action_component
            + 0.20 * local_risk_component
            + 0.14 * noise_component
            + 0.08 * shadow_component
            + coactivation_pair_bonus,
            0.0,
            1.0,
        ))

        hard_block_signal = bool(max_conflict >= 0.92 or max_unresolved >= 0.95 or candidate_risk_max >= 0.95)
        if action_rows == 0:
            decision = "monitor_only"
            dampening_factor = 0.0
            gate_reason = "no_action_candidates__monitor_only"
        elif hard_block_signal or coactivation_risk_score >= gate_block_threshold:
            decision = "block"
            dampening_factor = 0.0
            gate_reason = "high_same_step_coactivation_or_hard_block_signal"
        elif coactivation_risk_score >= gate_defer_threshold:
            decision = "defer"
            dampening_factor = 0.0
            gate_reason = "high_same_step_coactivation__defer_to_next_cycle"
        elif coactivation_risk_score >= gate_dampen_threshold:
            decision = "dampen"
            dampening_factor = gate_dampening_factor_effective
            gate_reason = "moderate_same_step_coactivation__dampen_action_frame_strength"
        else:
            decision = "allow"
            dampening_factor = 1.0
            gate_reason = "low_same_step_coactivation__allow"

        row = {
            "coactivation_gate_decision": decision,
            "gate_reason": gate_reason,
            "coactivation_risk_score": coactivation_risk_score,
            "parameter_window_binding_used": bool(parameter_windows),
            "gate_dampen_threshold": gate_dampen_threshold,
            "gate_defer_threshold": gate_defer_threshold,
            "gate_block_threshold": gate_block_threshold,
            # compatibility with earlier tasks/tests
            "risk_score": coactivation_risk_score,
            "approved_pressure_l1": pressure_l1,
            "pressure_component_score": pressure_component,
            "exploration_component_score": exploration_component,
            "action_component_score": action_component,
            "local_risk_component_score": local_risk_component,
            "noise_component_score": noise_component,
            "shadow_component_score": shadow_component,
            "coactivation_pair_bonus": coactivation_pair_bonus,
            "max_v8_conflict": max_conflict,
            "max_v8_unresolved": max_unresolved,
            "max_ot_noise_score": max_noise,
            "candidate_risk_max": candidate_risk_max,
            "action_strength_max": action_strength_max,
            "action_strength_mean": action_strength_mean,
            "shadow_delta_max": shadow_delta,
            "shadow_total_abs_delta": shadow_total_abs_delta,
            "unresolved_noise_rows": unresolved_noise_rows,
            "weak_pressure_rows": pressure_rows,
            "exploration_projection_rows": projection_rows,
            "action_candidate_rows": action_rows,
            "action_local_audit_rows": local_audit_rows,
            "shadow_parameter_rows": shadow_rows,
            "residual_noise_rows": noise_rows,
            "exploration_projection_active": exploration_active,
            "shadow_active": shadow_active,
            "hard_block_signal": hard_block_signal,
            "gate_required_before_actionframe": True,
            "gate_applies_to_action_frame": True,
            "gate_dampening_factor": dampening_factor,
            "gate_dampening_factor_effective": gate_dampening_factor_effective,
            "gate_threshold_mode": gate_threshold_mode,
            "gate_prevents_actionframe_when_block_or_defer": bool(decision in {"block", "defer", "monitor_only"}),
            "allow_like_decision": bool(decision == "allow"),
            "dampen_like_decision": bool(decision == "dampen"),
            "defer_like_decision": bool(decision == "defer"),
            "block_like_decision": bool(decision == "block"),
            "monitor_only_decision": bool(decision == "monitor_only"),
            "action_frame_created_by_gate": False,
            "actionmodule_called_by_gate": False,
            "parameter_box_updated_by_gate": False,
            "world_write_performed_by_gate": False,
            "gk_writeback_performed_by_gate": False,
            "ot_writeback_performed_by_gate": False,
            "canonical_parameter_write_by_gate": False,
            "sidecar_direct_actionmodule_input_by_gate": False,
            "gate_inputs_fingerprint": sha256(json.dumps({
                "weak_pressure": _fingerprint_df(weak_pressure),
                "exploration_projection": _fingerprint_df(exploration_projection),
                "action_candidates": _fingerprint_df(action_candidates),
                "action_local_audit": _fingerprint_df(action_local_audit),
                "shadow_params": _fingerprint_df(shadow_params),
                "residual_noise_log": _fingerprint_df(residual_noise_log),
            }, sort_keys=True).encode("utf-8")).hexdigest()[:16],
            "coactivation_gate_audit_status": "pass",
            "coactivation_gate_contract": "Task12_same_step_coactivation_gate__pre_ActionFrame__allow_dampen_defer_block_monitor_only__no_writeback__RC1",
        }
        return pd.DataFrame([row])
