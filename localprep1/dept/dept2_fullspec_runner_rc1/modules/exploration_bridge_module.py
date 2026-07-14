"""exploration_bridge_module: verified exploration bridge for Task10/Phase 2G-20AB.

Task10 created a verified bridge from Task7/Task8 exploration into action-side
planning.  Phase 2G-20AB keeps the safety boundary but relaxes the old all-or-
nothing projection rule:
  - sandbox_pass candidates may become strong action-readable candidates;
  - sandbox/watch candidates may still reach the action side as probe-only or
    weak candidates;
  - blocked, unsafe, audit-failed, v8-failed, or unverified-danger candidates do
    not become action-readable projections;
  - the bridge classifies and budgets candidates but does not decide execution;
  - final execution remains owned by the action module.

The full exploration context remains in the non-compressed sidecar.  The thin
projection is a candidate handoff, not an ActionFrame and not a direct
ActionModule command.
"""
from __future__ import annotations

from hashlib import sha256
import json
import pandas as pd


def _rows(df: pd.DataFrame | None) -> int:
    return int(len(df)) if df is not None else 0


def _fingerprint_df(df: pd.DataFrame | None) -> str:
    if df is None or df.empty:
        return "empty"
    payload = {
        "columns": list(map(str, df.columns)),
        "rows": int(len(df)),
        "head": df.head(50).astype(str).to_dict(orient="records"),
    }
    return sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def _ensure(df: pd.DataFrame | None) -> pd.DataFrame:
    return pd.DataFrame() if df is None else df.copy()


def _num(df: pd.DataFrame, col: str, default: float = 0.0) -> pd.Series:
    if col in df.columns:
        return pd.to_numeric(df[col], errors="coerce").fillna(default)
    return pd.Series([default] * len(df), index=df.index, dtype="float64")


def _bool(df: pd.DataFrame, col: str, default: bool = False) -> pd.Series:
    if col in df.columns:
        return df[col].fillna(default).astype(bool)
    return pd.Series([default] * len(df), index=df.index, dtype="bool")


def _str(df: pd.DataFrame, col: str, default: str = "") -> pd.Series:
    if col in df.columns:
        return df[col].fillna(default).astype(str)
    return pd.Series([default] * len(df), index=df.index, dtype="object")


class ExplorationBridgeModule:
    name = "exploration_bridge_module"

    def project(
        self,
        exploration_decision: pd.DataFrame,
        exploration_sandbox: pd.DataFrame,
        exploration_local_audit: pd.DataFrame,
        parameter_windows: dict | None = None,
    ) -> dict[str, pd.DataFrame]:
        decision = _ensure(exploration_decision)
        sandbox = _ensure(exploration_sandbox)
        local_audit = _ensure(exploration_local_audit)
        parameter_windows = parameter_windows or {}

        if decision.empty:
            sidecar = pd.DataFrame([{
                "sidecar_id": "exploration_sidecar_empty",
                "full_context_present": True,
                "sidecar_is_noncompressed": True,
                "sidecar_contains_decision": False,
                "sidecar_contains_sandbox": False,
                "sidecar_contains_local_audit": False,
                "sidecar_direct_actionmodule_input": False,
                "parameter_window_binding_used": bool(parameter_windows),
                "projection_adoption_threshold": float(parameter_windows.get("projection_adoption_threshold", 0.50)),
                "watch_projection_threshold": float(parameter_windows.get("watch_projection_threshold", 0.30)),
                "execution_decision_owner": "action_module",
                "bridge_status": "empty_no_exploration_decision",
                "sidecar_contract": "Task10_full_exploration_context_sidecar_reserved__no_compression__RC1",
            }])
            projection = self._empty_projection()
            return {"exploration_projection": projection, "exploration_sidecar": sidecar}

        sidecar = self._build_sidecar(decision, sandbox, local_audit, parameter_windows)
        projection = self._build_projection(sidecar)
        return {"exploration_projection": projection, "exploration_sidecar": sidecar}

    def _build_sidecar(
        self,
        decision: pd.DataFrame,
        sandbox: pd.DataFrame,
        local_audit: pd.DataFrame,
        parameter_windows: dict | None = None,
    ) -> pd.DataFrame:
        parameter_windows = parameter_windows or {}
        projection_adoption_threshold = float(parameter_windows.get("projection_adoption_threshold", 0.50))
        watch_projection_threshold = float(
            parameter_windows.get("watch_projection_threshold", min(0.49, max(0.20, projection_adoption_threshold * 0.60)))
        )
        merged = decision.copy()
        if "candidate_axis_id" in merged.columns:
            if not sandbox.empty and "candidate_axis_id" in sandbox.columns:
                sandbox_cols = [
                    c for c in [
                        "candidate_axis_id", "sandbox_verified", "sandbox_status",
                        "dispersion_gain", "residual_reduction", "information_gain",
                        "stability_cost", "noise_risk", "adoption_risk",
                        "residual_delta", "ambiguity_delta_sandbox",
                        "unresolved_delta_sandbox", "topology_preservation_score",
                        "topology_break_risk", "sandbox_projection_contract",
                        "world_writeback_performed", "gk_writeback_performed",
                        "ot_writeback_performed", "parameter_update_performed",
                        "action_performed",
                    ]
                    if c in sandbox.columns
                ]
                merged = merged.merge(
                    sandbox[sandbox_cols].drop_duplicates("candidate_axis_id"),
                    on="candidate_axis_id",
                    how="left",
                    suffixes=("", "_sandbox"),
                )
            if not local_audit.empty and "candidate_axis_id" in local_audit.columns:
                audit_cols = [
                    c for c in [
                        "candidate_axis_id", "entity_id", "graph_object_id", "ot_id",
                        "axis_type", "action_channel", "target_need", "v8_requested",
                        "v8_confidence", "v8_conflict", "v8_unresolved",
                        "local_audit_passed", "local_audit_role",
                        "v8_support_status", "local_audit_contract",
                        "v8_is_gk_generator", "v8_is_upper_formal_input",
                        "v8_generates_pressure", "v8_updates_parameter_box",
                        "v8_calls_actionmodule", "v8_writes_world", "v8_writes_gk",
                        "v8_writes_ot", "v8_writes_canonical_parameter",
                        "local_audit_writeback_performed",
                        "exploration_projection_created_by_local_audit",
                        "exploration_action_created_by_local_audit",
                        "sidecar_compression_by_local_audit",
                    ]
                    if c in local_audit.columns
                ]
                merged = merged.merge(
                    local_audit[audit_cols].drop_duplicates("candidate_axis_id"),
                    on="candidate_axis_id",
                    how="left",
                    suffixes=("", "_v8"),
                )

        # Stable sidecar id must be per candidate, not just per cycle.
        merged["sidecar_id"] = merged.apply(
            lambda r: f"exploration_sidecar_{int(r.get('seed', r.get('run_seed', -1)))}_"
            f"{r.get('scenario', r.get('run_scenario', 'unknown'))}_"
            f"t{int(r.get('t', r.get('loop_step', -1)))}_{r.get('candidate_axis_id', 'none')}",
            axis=1,
        )
        merged["full_context_present"] = True
        merged["sidecar_is_noncompressed"] = True
        merged["sidecar_contains_decision"] = True
        merged["sidecar_contains_sandbox"] = "sandbox_status" in merged.columns
        merged["sidecar_contains_local_audit"] = "v8_support_status" in merged.columns
        merged["sidecar_decision_rows_source"] = _rows(decision)
        merged["sidecar_sandbox_rows_source"] = _rows(sandbox)
        merged["sidecar_local_audit_rows_source"] = _rows(local_audit)
        merged["sidecar_decision_fingerprint"] = _fingerprint_df(decision)
        merged["sidecar_sandbox_fingerprint"] = _fingerprint_df(sandbox)
        merged["sidecar_local_audit_fingerprint"] = _fingerprint_df(local_audit)
        merged["sidecar_direct_actionmodule_input"] = False
        merged["projection_payload_thin"] = True
        merged["bridge_writes_world"] = False
        merged["bridge_writes_gk"] = False
        merged["bridge_writes_ot"] = False
        merged["bridge_updates_parameter_box"] = False
        merged["bridge_calls_actionmodule"] = False
        merged["bridge_creates_actionframe"] = False
        merged["parameter_window_binding_used"] = bool(parameter_windows)
        merged["projection_adoption_threshold"] = projection_adoption_threshold
        merged["watch_projection_threshold"] = watch_projection_threshold
        merged["execution_decision_owner"] = "action_module"
        merged["bridge_contract"] = (
            "Phase2G20AB_exploration_bridge__tiered_candidate_projection__"
            "action_module_final_execution_decision__RC1"
        )
        merged["sidecar_contract"] = (
            "Task10_full_exploration_context_preserved__decision_sandbox_local_audit_retained__no_context_compression__RC1"
        )

        decision_score = _num(merged, "decision_score", 0.0)
        decision_status = _str(merged, "decision_status", "monitor_only")
        sandbox_status = _str(merged, "sandbox_status", "not_run")
        verified = _bool(merged, "sandbox_verified", False)
        audit_pass = _bool(merged, "local_audit_passed", False)
        status_pass = _str(merged, "v8_support_status", "fail").eq("pass")
        unverified_pass = _bool(merged, "unverified_candidate_can_pass", False)
        topology_break = _num(merged, "topology_break_risk", _num(merged, "topology_break_risk_prior", 0.0).mean() if len(merged) else 0.0)
        noise_risk = _num(merged, "noise_risk", 0.0)

        merged["passes_projection_adoption_threshold"] = decision_score >= projection_adoption_threshold
        merged["passes_watch_projection_threshold"] = decision_score >= watch_projection_threshold

        hard_block = (
            decision_status.eq("block")
            | sandbox_status.eq("block")
            | ~audit_pass
            | ~status_pass
            | unverified_pass
        )
        verified_pass = decision_status.eq("sandbox_pass") & verified & ~hard_block
        verified_watch = decision_status.eq("watch") & verified & ~hard_block
        below_pass_but_candidate = verified_pass & ~merged["passes_projection_adoption_threshold"] & merged["passes_watch_projection_threshold"]
        strong = verified_pass & merged["passes_projection_adoption_threshold"]
        weak = below_pass_but_candidate
        probe = verified_watch & merged["passes_watch_projection_threshold"]

        merged["projection_tier"] = "monitor_only"
        merged.loc[hard_block, "projection_tier"] = "blocked"
        merged.loc[probe, "projection_tier"] = "probe_only"
        merged.loc[weak, "projection_tier"] = "weak_candidate"
        merged.loc[strong, "projection_tier"] = "strong_candidate"

        merged["candidate_use_permission"] = "monitor_only"
        merged.loc[hard_block, "candidate_use_permission"] = "blocked"
        merged.loc[probe | weak, "candidate_use_permission"] = "probe_only"
        merged.loc[strong, "candidate_use_permission"] = "action_allowed"

        frontier = (
            0.30 * decision_score
            + 0.25 * _num(merged, "information_gain", 0.0).clip(lower=0.0)
            + 0.25 * _num(merged, "residual_reduction", 0.0).clip(lower=0.0)
            + 0.20 * _num(merged, "dispersion_gain", 0.0).clip(lower=0.0)
        ).clip(0.0, 1.0)
        side_effect_budget = (
            0.020
            + 0.050 * frontier
            - 0.020 * noise_risk
            - 0.020 * topology_break
            - 0.010 * _num(merged, "stability_cost", 0.0)
        ).clip(lower=0.005, upper=0.080)

        merged["frontier_expectation_score"] = frontier.round(6)
        merged["side_effect_budget"] = side_effect_budget.round(6)
        merged["max_start_strength"] = 0.0
        merged.loc[probe, "max_start_strength"] = 0.025
        merged.loc[weak, "max_start_strength"] = 0.040
        merged.loc[strong, "max_start_strength"] = (0.040 + 0.060 * frontier[strong]).clip(upper=0.100).round(6)
        merged["max_escalated_strength"] = 0.0
        merged.loc[probe, "max_escalated_strength"] = 0.040
        merged.loc[weak, "max_escalated_strength"] = 0.070
        merged.loc[strong, "max_escalated_strength"] = (0.070 + 0.080 * frontier[strong]).clip(upper=0.150).round(6)
        merged["cooldown_steps"] = 3
        merged.loc[probe, "cooldown_steps"] = 4
        merged.loc[strong, "cooldown_steps"] = 2
        merged.loc[hard_block, "cooldown_steps"] = 999
        merged["action_module_final_decision_required"] = merged["projection_tier"].isin(["strong_candidate", "weak_candidate", "probe_only"])

        eligible = merged["projection_tier"].isin(["strong_candidate", "weak_candidate", "probe_only"])
        merged["eligible_for_action_projection"] = eligible
        merged["all_projected_candidates_verified"] = bool(verified[eligible].all()) if bool(eligible.any()) else True
        merged["unverified_candidate_projected"] = bool((~verified & eligible).any())
        merged["bridge_status"] = "tiered_candidate_projection"
        return merged

    def _build_projection(self, sidecar: pd.DataFrame) -> pd.DataFrame:
        if sidecar is None or sidecar.empty:
            return self._empty_projection()
        eligible = sidecar[sidecar.get("eligible_for_action_projection", pd.Series(False, index=sidecar.index)).astype(bool)].copy()
        if eligible.empty:
            return self._empty_projection()

        # Thin projection: only action-readable hints and references.  The full
        # context remains in sidecar and can be recovered through sidecar_id.
        confidence = _num(eligible, "v8_confidence", 0.50)
        decision_score = _num(eligible, "decision_score", 0.0)
        residual_reduction = _num(eligible, "residual_reduction", 0.0).clip(lower=0.0)
        topology = _num(eligible, "topology_preservation_score", 0.50)
        conflict_penalty = _num(eligible, "v8_conflict", 0.0) * 0.20
        unresolved_penalty = _num(eligible, "v8_unresolved", 0.0) * 0.10
        projection_strength = (
            0.35 * decision_score
            + 0.25 * confidence
            + 0.25 * residual_reduction
            + 0.15 * topology
            - conflict_penalty
            - unresolved_penalty
        ).clip(lower=0.05, upper=1.0)
        projection_strength = projection_strength.clip(upper=_num(eligible, "max_escalated_strength", 0.05).clip(lower=0.05))

        projection = pd.DataFrame({
            "projection_id": [f"EXP_PROJ_{i:05d}" for i in range(len(eligible))],
            "sidecar_id": eligible["sidecar_id"].astype(str).values,
            "candidate_axis_id": eligible.get("candidate_axis_id", pd.Series([""] * len(eligible))).astype(str).values,
            "entity_id": eligible.get("entity_id", pd.Series([""] * len(eligible))).astype(str).values,
            "graph_object_id": eligible.get("graph_object_id", pd.Series([""] * len(eligible))).astype(str).values,
            "ot_id": eligible.get("ot_id", pd.Series([""] * len(eligible))).astype(str).values,
            "exploration_axis_hint": eligible.get("axis_type", pd.Series(["exploration_axis"] * len(eligible))).astype(str).values,
            "action_channel_hint": eligible.get("action_channel", pd.Series(["exploration_injection"] * len(eligible))).astype(str).values,
            "target_need_hint": eligible.get("target_need", pd.Series(["residual_gap"] * len(eligible))).astype(str).values,
            "projection_strength": projection_strength.round(6).values,
            "projection_tier": eligible.get("projection_tier", pd.Series(["strong_candidate"] * len(eligible))).astype(str).values,
            "candidate_use_permission": eligible.get("candidate_use_permission", pd.Series(["action_allowed"] * len(eligible))).astype(str).values,
            "frontier_expectation_score": _num(eligible, "frontier_expectation_score", 0.0).round(6).values,
            "side_effect_budget": _num(eligible, "side_effect_budget", 0.0).round(6).values,
            "max_start_strength": _num(eligible, "max_start_strength", 0.0).round(6).values,
            "max_escalated_strength": _num(eligible, "max_escalated_strength", 0.0).round(6).values,
            "cooldown_steps": _num(eligible, "cooldown_steps", 0).astype(int).values,
            "execution_decision_owner": eligible.get("execution_decision_owner", pd.Series(["action_module"] * len(eligible))).astype(str).values,
            "action_module_final_decision_required": eligible.get("action_module_final_decision_required", pd.Series([True] * len(eligible))).fillna(True).astype(bool).values,
            "projection_decision": eligible.get("decision_status", pd.Series(["sandbox_pass"] * len(eligible))).astype(str).values,
            "sandbox_status": eligible.get("sandbox_status", pd.Series(["pass"] * len(eligible))).astype(str).values,
            "projection_source_verified": eligible.get("sandbox_verified", pd.Series([True] * len(eligible))).fillna(False).astype(bool).values,
            "projection_source_local_audit_passed": eligible.get("local_audit_passed", pd.Series([True] * len(eligible))).fillna(False).astype(bool).values,
            "projection_source_v8_status": eligible.get("v8_support_status", pd.Series(["pass"] * len(eligible))).astype(str).values,
            "projection_is_thin": True,
            "projection_contains_full_sidecar_payload": False,
            "sidecar_direct_actionmodule_input": False,
            "projection_writes_world": False,
            "projection_writes_gk": False,
            "projection_writes_ot": False,
            "projection_updates_parameter_box": False,
            "projection_calls_actionmodule": False,
            "projection_creates_actionframe": False,
            "projection_contract": (
                "Phase2G20AB_action_readable_tiered_exploration_projection__"
                "thin_projection_only__thin_candidate_handoff_only__action_module_final_execution_decision__RC1"
            ),
        })
        return projection

    def _empty_projection(self) -> pd.DataFrame:
        return pd.DataFrame(columns=[
            "projection_id", "sidecar_id", "candidate_axis_id", "entity_id",
            "graph_object_id", "ot_id", "exploration_axis_hint",
            "action_channel_hint", "target_need_hint", "projection_strength",
            "projection_tier", "candidate_use_permission",
            "frontier_expectation_score", "side_effect_budget",
            "max_start_strength", "max_escalated_strength", "cooldown_steps",
            "execution_decision_owner", "action_module_final_decision_required",
            "projection_decision", "sandbox_status", "projection_source_verified",
            "projection_source_local_audit_passed", "projection_source_v8_status",
            "projection_is_thin", "projection_contains_full_sidecar_payload",
            "sidecar_direct_actionmodule_input", "projection_writes_world",
            "projection_writes_gk", "projection_writes_ot",
            "projection_updates_parameter_box", "projection_calls_actionmodule",
            "projection_creates_actionframe", "projection_contract",
        ])
