"""ParameterShadowBox controlled upper-pressure-only variant for Task22C-Rev1-Q4.

This variant is intentionally shadow-only in the FullSpec runner. It implements
Task22C controlled update behavior as the formal shadow-update candidate:
  - update decision uses H11-local pressure field only;
  - formal_packet is accepted for compatibility/fingerprint but not used for update;
  - persistence and integral gates suppress transient pressure;
  - no canonical/world/GK/O_t writeback is performed.
"""
from __future__ import annotations

import hashlib
import math
from typing import Dict
import numpy as np
import pandas as pd

from DEPT2_ActionModule_ActuationPrimitives_RC1.dept2_system.parameter_box import LowerParameterGovernanceBox

FORBIDDEN_INPUT_PREFIXES = (
    "ot_", "v8_", "exploration_", "graph_object", "action_surface",
    "action_", "final_gate", "coactivation_", "sidecar", "world_truth",
)

def _fingerprint_mapping(values: Dict[str, float]) -> str:
    if not values:
        return "empty"
    payload = "|".join(f"{k}:{float(values[k]):.12f}" for k in sorted(values))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

def _fingerprint_df(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "empty"
    payload = pd.util.hash_pandas_object(df.sort_index(axis=1), index=True).values.tobytes()
    return hashlib.sha256(payload).hexdigest()[:16]

def _clip(v: float, lo: float, hi: float) -> float:
    return float(max(lo, min(hi, float(v))))

class ParameterShadowBox:
    name = "parameter_shadow_box"

    def __init__(self):
        self.box = LowerParameterGovernanceBox()
        self._cycle_index = 0
        self._last_shadow_fingerprint = _fingerprint_mapping(self.box.current_params())
        self._integral: dict[str, float] = {}
        self._persistence: dict[str, int] = {}
        self._prev_signal: dict[str, float] = {}

    def update_shadow(self, formal_packet: pd.DataFrame, h11_local_pressure_field: pd.DataFrame, *, loop_step: int | None = None) -> dict[str, pd.DataFrame]:
        self._validate_inputs(formal_packet, h11_local_pressure_field)
        before_params = self.box.current_params()
        before_fp = _fingerprint_mapping(before_params)
        formal_fp = _fingerprint_df(formal_packet)
        h11_fp = _fingerprint_df(h11_local_pressure_field)
        effective_step = self._cycle_index if loop_step is None else int(loop_step)
        self._cycle_index = max(self._cycle_index + 1, effective_step + 1)

        signals = self._summarize_pressure(h11_local_pressure_field)
        gate = self._update_gate(signals)
        after_params = dict(before_params)

        registry = self.box.registry.copy()
        rows = []
        for _, reg in registry.iterrows():
            pname = str(reg.parameter_name)
            theta_cur = float(before_params[pname])
            score = self._parameter_score(pname, signals)
            integral_score = self._parameter_score(pname, self._integral)
            raw_delta = 0.35 * integral_score + 0.15 * score
            raw_delta *= gate["shift_response_gain"]
            raw_delta *= gate["boundary_damping"]
            if not gate["commit_gate_passed"]:
                raw_delta = 0.0
            # Resistance to theta0 remains upper-only because theta0 is registry prior.
            raw_delta -= float(reg.resistance_to_theta0) * (theta_cur - float(reg.theta0))
            if not gate["commit_gate_passed"]:
                # Do not let resistance create updates while gate is closed.
                raw_delta = 0.0
            bounded_delta = _clip(raw_delta, -float(reg.max_step_delta), float(reg.max_step_delta))
            theta_next = _clip(theta_cur + bounded_delta, float(reg.theta_min), float(reg.theta_max))
            after_params[pname] = theta_next
            rows.append({
                "parameter_name": pname,
                "theta_before": theta_cur,
                "theta_after": theta_next,
                "theta_delta": theta_next - theta_cur,
                "system_caution": 0.0,
                "exploration_need": 0.0,
                "relation_lock_need": 0.0,
                "pressure_signal": abs(score),
                "h11_signal": abs(integral_score),
                "controlled_pressure_score": score,
                "controlled_integral_score": integral_score,
                "update_contract": "Q4_task22c_controlled_shadow_update__H11_pressure_only__persistence_gated__no_formal_packet_update_signal",
                "truth_used_for_parameter_update": False,
                "parameter_update_mode": "shadow_only",
                "q4_shadow_update_candidate_id": "task22c_controlled_shadow_update",
                "shadow_carryover_enabled": True,
                "shadow_cycle_index": effective_step,
                "shadow_source": "runner_owned_parameter_shadow_state_controlled",
                "commit_status": "not_committed",
                "commit_gate_passed": False,
                "controlled_update_gate_passed": bool(gate["commit_gate_passed"]),
                "lower_parameter_update_committed": False,
                "canonical_write_performed": False,
                "canonical_theta_written": False,
                "world_write_performed": False,
                "world_state_written": False,
                "gk_writeback_performed": False,
                "canonical_gk_written": False,
                "rollback_ready": True,
                "parameter_shadow_contract": "Q4_task22c_controlled_shadow_update__shadow_only__no_commit__no_writeback__RC1",
                "shadow_previous_fingerprint": before_fp,
                "formal_packet_fingerprint": formal_fp,
                "h11_pressure_fingerprint": h11_fp,
                **{f"gate_{k}": v for k, v in gate.items() if isinstance(v, (int, float, bool, str))},
            })

        self.box.state = pd.DataFrame([{"parameter_name": k, "theta": v} for k, v in after_params.items()])
        after_fp = _fingerprint_mapping(after_params)
        updates = pd.DataFrame(rows)
        registry["parameter_registry_contract"] = "q4_task22c_controlled_shadow_update_registry_reference_only__not_canonical_theta_store__RC1"
        registry["canonical_theta_source"] = "none__shadow_only_runner_state"
        registry["canonical_write_allowed"] = False
        updates["shadow_next_fingerprint"] = after_fp

        max_abs_delta = float(updates["theta_delta"].abs().max()) if not updates.empty else 0.0
        total_abs_delta = float(updates["theta_delta"].abs().sum()) if not updates.empty else 0.0
        updated_rows = int((updates["theta_delta"].abs() > 1e-12).sum()) if not updates.empty else 0
        max_allowed_delta = float(registry["max_step_delta"].max()) if "max_step_delta" in registry.columns else 0.0
        bounded_delta_pass = bool(max_abs_delta <= max_allowed_delta + 1e-12)

        current_rows = []
        for k, v in after_params.items():
            before_v = float(before_params.get(k, v))
            current_rows.append({
                "parameter_name": k,
                "shadow_theta": float(v),
                "shadow_theta_previous": before_v,
                "shadow_theta_delta_from_previous": float(v) - before_v,
                "shadow_cycle_index": effective_step,
                "shadow_fingerprint": after_fp,
                "previous_shadow_fingerprint": before_fp,
                "shadow_contract": "Q3_task22c_controlled_shadow_only__no_canonical_write__RC1",
                "shadow_state_owner": "parameter_shadow_box",
                "canonical_theta_written": False,
                "world_state_written": False,
                "canonical_gk_written": False,
                "rollback_ready": True,
            })
        current = pd.DataFrame(current_rows)
        audit = pd.DataFrame([{
            "parameter_shadow_contract": "Q4_task22c_controlled_shadow_update__bounded_shadow_carryover_H11_pressure_only_persistence_gated__RC1",
            "shadow_cycle_index": effective_step,
            "formal_packet_fingerprint": formal_fp,
            "h11_pressure_fingerprint": h11_fp,
            "previous_shadow_fingerprint": before_fp,
            "new_shadow_fingerprint": after_fp,
            "previous_shadow_fingerprint_matches_last_cycle": bool(before_fp == self._last_shadow_fingerprint),
            "shadow_carryover_enabled": True,
            "shadow_state_rows": int(len(current)),
            "parameter_registry_rows": int(len(registry)),
            "parameter_update_rows": int(len(updates)),
            "updated_parameter_rows": updated_rows,
            "max_abs_theta_delta": max_abs_delta,
            "total_abs_theta_delta": total_abs_delta,
            "max_allowed_step_delta": max_allowed_delta,
            "bounded_delta_pass": bounded_delta_pass,
            "rollback_ready": True,
            "commit_status": "not_committed",
            "commit_gate_passed": False,
                "controlled_update_gate_passed": bool(gate["commit_gate_passed"]),
            "lower_parameter_update_committed": False,
            "canonical_write_performed": False,
            "canonical_theta_written": False,
            "world_write_performed": False,
            "world_state_written": False,
            "gk_writeback_performed": False,
            "canonical_gk_written": False,
            "formal_lower_leak_count": 0,
            "h11_lower_leak_count": 0,
            "truth_used_for_parameter_update": False,
            "q4_shadow_update_candidate_id": "task22c_controlled_shadow_update",
            **{f"gate_{k}": v for k, v in gate.items() if isinstance(v, (int, float, bool, str))},
            "audit_status": "pass" if bounded_delta_pass else "fail",
        }])
        self._last_shadow_fingerprint = after_fp
        return {
            "parameter_registry": registry,
            "parameter_updates": updates,
            "shadow_parameter_state": current,
            "parameter_shadow_audit": audit,
        }

    def current_params(self) -> dict:
        return self.box.current_params()

    def _summarize_pressure(self, h11: pd.DataFrame) -> dict[str, float]:
        if h11 is None or h11.empty:
            return {}
        col = "h11_local_received_pressure" if "h11_local_received_pressure" in h11.columns else "component_signed_value"
        s = h11.groupby("pressure_component")[col].mean()
        return {str(k): float(v) for k, v in s.to_dict().items()}

    def _update_gate(self, signals: dict[str, float]) -> dict[str, float | bool | str]:
        pnorm = math.sqrt(sum(float(v) ** 2 for v in signals.values()))
        sign_consistent = 0
        active = 0
        for k, v in signals.items():
            v = float(v)
            prev = float(self._prev_signal.get(k, 0.0))
            self._integral[k] = _clip(0.90 * float(self._integral.get(k, 0.0)) + 0.10 * v, -1.0, 1.0)
            same = (abs(v) > 0.001 and (prev == 0.0 or v * prev >= 0.0))
            if same:
                self._persistence[k] = int(self._persistence.get(k, 0)) + 1
                sign_consistent += 1
            else:
                self._persistence[k] = max(0, int(self._persistence.get(k, 0)) - 1)
            if abs(v) > 0.001:
                active += 1
            self._prev_signal[k] = v
        integral_norm = math.sqrt(sum(float(v) ** 2 for v in self._integral.values()))
        max_persistence = max(self._persistence.values()) if self._persistence else 0
        consistency = float(sign_consistent / max(1, active))
        shock_like = bool(pnorm > 0.18 and max_persistence < 2)
        persistent = bool(max_persistence >= 2 and integral_norm > 0.004 and consistency >= 0.55)
        commit = bool(persistent and not shock_like)
        gain = 1.0 if commit else 0.0
        if max_persistence >= 5:
            gain = 1.20
        return {
            "pressure_norm": pnorm,
            "integral_norm": integral_norm,
            "max_persistence": int(max_persistence),
            "sign_consistency": consistency,
            "shock_like_pressure_flag": shock_like,
            "persistent_shift_flag": persistent,
            "commit_gate_passed": commit,
            "shift_response_gain": gain,
            "boundary_damping": 1.0,
            "watch_only_reason": "" if commit else ("shock_like_or_not_persistent" if shock_like else "not_persistent_enough"),
        }

    def _parameter_score(self, pname: str, v: dict[str, float]) -> float:
        g = lambda k: float(v.get(k, 0.0))
        if pname == "action_intensity_cap":
            return g("pressure_cap") + 0.4*g("exploration_frequency") - 0.4*g("rollback_sensitivity")
        if pname == "action_sparsity_threshold":
            return g("deadzone_width") + 0.6*g("pressure_cap") + 0.3*g("update_frequency") - 0.2*g("exploration_frequency")
        if pname == "v8_activation_threshold":
            return -0.7*g("diagnostic_depth") + 0.3*g("rollback_sensitivity")
        if pname == "conflict_penalty_weight":
            return g("rollback_sensitivity") + 0.5*g("diagnostic_depth")
        if pname == "unresolved_penalty_weight":
            return g("diagnostic_depth") + 0.7*g("sandbox_entry_rate")
        if pname == "shadow_threshold":
            return g("rollback_sensitivity") + 0.6*g("pressure_cap") + 0.4*g("deadzone_width")
        if pname == "rollback_sensitivity":
            return g("rollback_sensitivity") + 0.7*g("cooldown_length")
        if pname == "graph_update_rate":
            return g("update_frequency") - 0.2*g("commitment_strength")
        if pname == "exploration_gain":
            return g("exploration_frequency") + g("sandbox_entry_rate") - 0.3*g("pressure_cap")
        if pname == "damping_gain":
            return g("pressure_cap") + 0.8*g("rollback_sensitivity")
        if pname == "unlock_gain":
            return -0.7*g("hysteresis_strength") + 0.6*g("update_frequency")
        if pname == "buffer_gain":
            return g("cooldown_length") + 0.8*g("rollback_sensitivity")
        return 0.0

    def _validate_inputs(self, formal_packet: pd.DataFrame, h11_local_pressure_field: pd.DataFrame) -> None:
        for label, df in [("formal_packet", formal_packet), ("h11_local_pressure_field", h11_local_pressure_field)]:
            if df is None or df.empty:
                raise ValueError(f"parameter_shadow_box requires non-empty {label}")
            leaked = [c for c in df.columns if str(c).startswith(FORBIDDEN_INPUT_PREFIXES)]
            if leaked:
                raise ValueError(f"parameter_shadow_box lower artifact leakage in {label}: {leaked}")
