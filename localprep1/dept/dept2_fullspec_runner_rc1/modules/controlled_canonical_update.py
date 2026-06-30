"""controlled_canonical_update: Task22C-Rev1-Q8 controlled canonical update.

This module implements the canonical-update boundary defined in Q7.

Important:
- It may write only the in-memory canonical_parameter_state.
- It never writes world, G/K, O_t, ActionFrame, ActionModule, upper pressure, or H11 field.
- It does not read lower action/world success outputs for update decision.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping

import pandas as pd


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(x)))


def _fingerprint_mapping(values: Mapping[str, float]) -> str:
    if not values:
        return "empty"
    payload = "|".join(f"{k}:{float(values[k]):.12f}" for k in sorted(values))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _json_map(values: Mapping[str, float]) -> str:
    return json.dumps({str(k): float(v) for k, v in sorted(values.items())}, sort_keys=True, ensure_ascii=False)


@dataclass
class Q8CanonicalConfig:
    enabled: bool = False
    dry_run: bool = True
    binding_source: str = "shadow"  # shadow | canonical
    minimum_persistence_steps: int = 3
    minimum_observation_window: int = 6
    candidate_stability_steps: int = 1
    commit_cooldown_steps: int = 3
    max_total_abs_theta_delta_per_commit: float = 0.12
    max_parameters_changed_per_commit: int = 6
    max_canonical_commits_per_10_steps: int = 2


class ControlledCanonicalUpdateModule:
    name = "controlled_canonical_update"

    def __init__(self, initial_params: Mapping[str, float]):
        self.canonical_params = {str(k): float(v) for k, v in initial_params.items()}
        self.commit_history: list[dict[str, Any]] = []
        self.rollback_snapshots: dict[str, dict[str, float]] = {}
        self._last_candidate_fingerprint = "empty"
        self._candidate_stability_count = 0
        self._cooldown_until_step = -1
        self._prev_pressure_norm: float | None = None
        self._shock_block_until_step = -1

    def evaluate(
        self,
        *,
        shadow_parameter_state: pd.DataFrame,
        parameter_shadow_audit: pd.DataFrame,
        shadow_current_params: Mapping[str, float],
        loop_step: int,
        config: Q8CanonicalConfig,
    ) -> dict[str, Any]:
        candidate_params = self._candidate_params(shadow_parameter_state, shadow_current_params)
        candidate_fp = _fingerprint_mapping(candidate_params)
        canonical_before = dict(self.canonical_params)
        canonical_before_fp = _fingerprint_mapping(canonical_before)

        if candidate_fp == self._last_candidate_fingerprint:
            self._candidate_stability_count += 1
        else:
            self._candidate_stability_count = 1
        self._last_candidate_fingerprint = candidate_fp

        gate = self._commit_gate(
            candidate_params=candidate_params,
            canonical_before=canonical_before,
            parameter_shadow_audit=parameter_shadow_audit,
            loop_step=loop_step,
            config=config,
        )

        snapshot = self._make_snapshot(loop_step=loop_step, commit_candidate_id=gate["commit_candidate_id"], canonical_before=canonical_before)

        canonical_write_performed = False
        committed_delta = {}
        candidate_limited = dict(canonical_before)
        if gate["commit_gate_passed"]:
            candidate_limited, committed_delta = self._limited_candidate(canonical_before, candidate_params, config)
            # Re-check budget after sparse limiting.
            if sum(abs(v) for v in committed_delta.values()) > config.max_total_abs_theta_delta_per_commit + 1e-12:
                gate["commit_gate_passed"] = False
                gate["commit_gate_reason"] = "blocked_by_postlimit_budget"
        if config.enabled and (not config.dry_run) and gate["commit_gate_passed"]:
            self.canonical_params = dict(candidate_limited)
            canonical_write_performed = True
            self.commit_history.append({
                "loop_step": loop_step,
                "canonical_before_fingerprint": canonical_before_fp,
                "canonical_after_fingerprint": _fingerprint_mapping(self.canonical_params),
                "changed_parameter_count": len(committed_delta),
                "total_abs_theta_delta": sum(abs(v) for v in committed_delta.values()),
            })
            self._cooldown_until_step = loop_step + config.commit_cooldown_steps

        canonical_after_fp = _fingerprint_mapping(self.canonical_params)
        changed_parameter_count = int(len(committed_delta)) if gate["commit_gate_passed"] else 0
        total_abs_delta = float(sum(abs(v) for v in committed_delta.values())) if gate["commit_gate_passed"] else 0.0
        max_abs_delta = float(max([abs(v) for v in committed_delta.values()] or [0.0]))

        commit_gate_audit = pd.DataFrame([{
            "q8_commit_gate_contract": "Task22C_Q8_controlled_canonical_commit_gate_RC1",
            "loop_step": int(loop_step),
            "canonical_commit_enabled": bool(config.enabled),
            "canonical_commit_dry_run": bool(config.dry_run),
            "canonical_binding_source": str(config.binding_source),
            **gate,
            "candidate_stability_count": int(self._candidate_stability_count),
            "cooldown_until_step": int(self._cooldown_until_step),
            "rate_limit_recent_commit_count": int(self._recent_commit_count(loop_step)),
            "rollback_snapshot_ready": bool(snapshot["rollback_ready"]),
            "audit_status": "pass",
        }])

        canonical_write_audit = pd.DataFrame([{
            "canonical_commit_id": gate["commit_candidate_id"],
            "loop_step": int(loop_step),
            "commit_gate_passed": bool(gate["commit_gate_passed"]),
            "commit_gate_reason": str(gate["commit_gate_reason"]),
            "canonical_commit_enabled": bool(config.enabled),
            "canonical_commit_dry_run": bool(config.dry_run),
            "shadow_candidate_fingerprint": candidate_fp,
            "canonical_before_fingerprint": canonical_before_fp,
            "canonical_after_fingerprint": canonical_after_fp,
            "rollback_snapshot_id": snapshot["rollback_snapshot_id"],
            "changed_parameter_count": changed_parameter_count,
            "max_abs_theta_delta": max_abs_delta,
            "total_abs_theta_delta": total_abs_delta,
            "bounded_delta_pass": bool(gate["bounded_delta_pass"]),
            "shock_like_pressure_flag": bool(gate["shock_like_pressure_flag"]),
            "persistent_shift_flag": bool(gate["persistent_shift_flag"]),
            "canonical_write_performed": bool(canonical_write_performed),
            "world_write_performed": False,
            "gk_writeback_performed": False,
            "ot_writeback_performed": False,
            "actionmodule_direct_input": False,
            "audit_status": "pass" if (not canonical_write_performed or gate["commit_gate_passed"]) else "fail",
        }])

        canonical_state = self._canonical_state_df(loop_step)
        rollback_snapshot = pd.DataFrame([snapshot])

        return {
            "commit_gate_audit": commit_gate_audit,
            "rollback_snapshot": rollback_snapshot,
            "canonical_parameter_state": canonical_state,
            "canonical_write_audit": canonical_write_audit,
            "canonical_current_params": dict(self.canonical_params),
            "shadow_current_params": dict(shadow_current_params),
        }

    def _candidate_params(self, shadow_state: pd.DataFrame, fallback: Mapping[str, float]) -> dict[str, float]:
        if shadow_state is not None and not shadow_state.empty and {"parameter_name", "shadow_theta"}.issubset(shadow_state.columns):
            return {str(r.parameter_name): float(r.shadow_theta) for _, r in shadow_state.iterrows()}
        return {str(k): float(v) for k, v in fallback.items()}

    def _commit_gate(
        self,
        *,
        candidate_params: Mapping[str, float],
        canonical_before: Mapping[str, float],
        parameter_shadow_audit: pd.DataFrame,
        loop_step: int,
        config: Q8CanonicalConfig,
    ) -> dict[str, Any]:
        row = parameter_shadow_audit.iloc[-1] if parameter_shadow_audit is not None and not parameter_shadow_audit.empty else {}
        def b(col: str, default: bool = False) -> bool:
            try:
                return bool(row.get(col, default))
            except Exception:
                return default
        def f(col: str, default: float = 0.0) -> float:
            try:
                return float(row.get(col, default))
            except Exception:
                return default

        base_shock = b("gate_shock_like_pressure_flag", False)
        pressure_norm = f("gate_pressure_norm", 0.0)
        pressure_norm_jump = 0.0 if self._prev_pressure_norm is None else abs(pressure_norm - float(self._prev_pressure_norm))
        impulsive_pressure_shift = bool((loop_step + 1) >= config.minimum_observation_window and pressure_norm_jump > 0.004)
        if impulsive_pressure_shift:
            self._shock_block_until_step = max(self._shock_block_until_step, loop_step + 2)
        shock_cooldown_active = bool(loop_step <= self._shock_block_until_step)
        shock = bool(base_shock or impulsive_pressure_shift or shock_cooldown_active)
        self._prev_pressure_norm = pressure_norm

        persistent = b("gate_persistent_shift_flag", b("controlled_update_gate_passed", False))
        bounded = b("bounded_delta_pass", True)
        max_persistence = int(f("gate_max_persistence", 0))
        observation_ok = loop_step + 1 >= config.minimum_observation_window
        stability_ok = self._candidate_stability_count >= config.candidate_stability_steps
        cooldown_ok = loop_step >= self._cooldown_until_step
        rate_limit_ok = self._recent_commit_count(loop_step) < config.max_canonical_commits_per_10_steps

        deltas = {k: float(candidate_params.get(k, canonical_before.get(k, 0.0))) - float(canonical_before.get(k, 0.0)) for k in candidate_params}
        active = {k: v for k, v in deltas.items() if abs(v) > 1e-9}
        limited_active = self._select_limited_deltas(active, config)
        total_abs = float(sum(abs(v) for v in limited_active.values()))
        budget_ok = total_abs <= config.max_total_abs_theta_delta_per_commit + 1e-12
        changed_count_ok = len(limited_active) <= config.max_parameters_changed_per_commit

        reason = "commit_gate_passed"
        if not candidate_params:
            reason = "blocked_by_no_shadow_candidate"
        elif shock:
            reason = "blocked_by_shock_like_pressure"
        elif not persistent or max_persistence < config.minimum_persistence_steps:
            reason = "blocked_by_non_persistent_shift"
        elif not bounded:
            reason = "blocked_by_unbounded_delta"
        elif not observation_ok:
            reason = "blocked_by_minimum_observation_window"
        elif not stability_ok:
            reason = "blocked_by_candidate_instability"
        elif not cooldown_ok:
            reason = "blocked_by_cooldown"
        elif not rate_limit_ok:
            reason = "blocked_by_rate_limit"
        elif not budget_ok:
            reason = "blocked_by_total_delta_budget"
        elif not changed_count_ok:
            reason = "blocked_by_changed_parameter_count"

        candidate_id = f"q8_candidate_{loop_step}_{_fingerprint_mapping(candidate_params)}"
        return {
            "commit_candidate_id": candidate_id,
            "commit_gate_passed": reason == "commit_gate_passed",
            "commit_gate_reason": reason,
            "shadow_candidate_exists": bool(candidate_params),
            "persistent_shift_confirmed": bool(persistent),
            "shock_like_pressure_flag": bool(shock),
            "persistent_shift_flag": bool(persistent),
            "base_shock_like_pressure_flag": bool(base_shock),
            "pressure_norm": float(pressure_norm),
            "pressure_norm_jump": float(pressure_norm_jump),
            "impulsive_pressure_shift": bool(impulsive_pressure_shift),
            "shock_cooldown_active": bool(shock_cooldown_active),
            "shock_block_until_step": int(self._shock_block_until_step),
            "bounded_delta_pass": bool(bounded),
            "minimum_observation_window_satisfied": bool(observation_ok),
            "candidate_stable_across_k_steps": bool(stability_ok),
            "cooldown_passed": bool(cooldown_ok),
            "rate_limit_passed": bool(rate_limit_ok),
            "expected_update_is_weak_slow_reversible": bool(budget_ok and changed_count_ok),
            "max_persistence": int(max_persistence),
            "candidate_active_parameter_count": int(len(active)),
            "candidate_limited_parameter_count": int(len(limited_active)),
            "candidate_total_abs_delta_after_limit": total_abs,
        }

    def _select_limited_deltas(self, deltas: Mapping[str, float], config: Q8CanonicalConfig) -> dict[str, float]:
        ordered = sorted(deltas.items(), key=lambda kv: abs(kv[1]), reverse=True)
        selected: dict[str, float] = {}
        budget = float(config.max_total_abs_theta_delta_per_commit)
        for k, v in ordered:
            if abs(v) <= 1e-9 or len(selected) >= config.max_parameters_changed_per_commit:
                continue
            remaining = budget - sum(abs(x) for x in selected.values())
            if remaining <= 1e-12:
                break
            selected[k] = _clip(v, -remaining, remaining)
        return selected

    def _limited_candidate(self, before: Mapping[str, float], candidate: Mapping[str, float], config: Q8CanonicalConfig) -> tuple[dict[str, float], dict[str, float]]:
        deltas = {k: float(candidate.get(k, before.get(k, 0.0))) - float(before.get(k, 0.0)) for k in candidate}
        selected = self._select_limited_deltas(deltas, config)
        out = dict(before)
        for k, delta in selected.items():
            out[k] = float(before.get(k, 0.0)) + float(delta)
        return out, selected

    def _make_snapshot(self, *, loop_step: int, commit_candidate_id: str, canonical_before: Mapping[str, float]) -> dict[str, Any]:
        fp = _fingerprint_mapping(canonical_before)
        snapshot_id = f"rollback_{loop_step}_{fp}"
        self.rollback_snapshots[snapshot_id] = dict(canonical_before)
        return {
            "rollback_snapshot_id": snapshot_id,
            "commit_candidate_id": commit_candidate_id,
            "created_loop_step": int(loop_step),
            "canonical_state_fingerprint_before": fp,
            "canonical_parameter_rows": int(len(canonical_before)),
            "theta_before_map_json": _json_map(canonical_before),
            "rollback_ready": True,
            "rollback_expiry_step": int(loop_step + 20),
            "snapshot_contract": "Task22C_Q8_rollback_snapshot_schema_RC1",
        }

    def _canonical_state_df(self, loop_step: int) -> pd.DataFrame:
        fp = _fingerprint_mapping(self.canonical_params)
        rows = []
        for k, v in sorted(self.canonical_params.items()):
            rows.append({
                "parameter_name": k,
                "canonical_theta": float(v),
                "canonical_cycle_index": int(loop_step),
                "canonical_state_fingerprint": fp,
                "canonical_state_contract": "Task22C_Q8_controlled_canonical_parameter_state_RC1",
                "world_write_performed": False,
                "gk_writeback_performed": False,
                "ot_writeback_performed": False,
                "actionmodule_direct_input": False,
            })
        return pd.DataFrame(rows)

    def _recent_commit_count(self, loop_step: int) -> int:
        return int(sum(1 for h in self.commit_history if int(h.get("loop_step", -999)) >= loop_step - 9))

    def current_params(self) -> dict[str, float]:
        return dict(self.canonical_params)
