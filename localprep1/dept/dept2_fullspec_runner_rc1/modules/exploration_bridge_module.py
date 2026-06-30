"""exploration_bridge_module: verified exploration bridge for Task10 RC1.

Task10 strengthens the bridge from Task7/Task8 exploration into action-side
planning:
  - only sandbox_pass + sandbox_verified + local_audit_passed candidates may
    produce an action-readable projection;
  - full exploration context is retained in a non-compressed sidecar;
  - the projection is intentionally thin and safe for action-side planning;
  - the full sidecar is audit-only and is never passed directly to ActionModule.
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
        decision_score = pd.to_numeric(merged.get("decision_score", pd.Series([0.0] * len(merged), index=merged.index)), errors="coerce").fillna(0.0)
        merged["passes_projection_adoption_threshold"] = decision_score >= projection_adoption_threshold
        merged["bridge_contract"] = (
            "Task10_exploration_bridge__full_sidecar_noncompressed__thin_action_readable_projection__RC1"
        )
        merged["sidecar_contract"] = (
            "Task10_full_exploration_context_preserved__decision_sandbox_local_audit_retained__no_context_compression__RC1"
        )

        decision_pass = merged["decision_status"].astype(str).eq("sandbox_pass") if "decision_status" in merged.columns else False
        verified = merged["sandbox_verified"].fillna(False).astype(bool) if "sandbox_verified" in merged.columns else False
        audit_pass = merged["local_audit_passed"].fillna(False).astype(bool) if "local_audit_passed" in merged.columns else False
        status_pass = merged["v8_support_status"].astype(str).eq("pass") if "v8_support_status" in merged.columns else False
        unverified_pass = merged["unverified_candidate_can_pass"].fillna(False).astype(bool) if "unverified_candidate_can_pass" in merged.columns else False
        adoption_pass = merged["passes_projection_adoption_threshold"].fillna(False).astype(bool) if "passes_projection_adoption_threshold" in merged.columns else True
        eligible = decision_pass & verified & audit_pass & status_pass & adoption_pass & ~unverified_pass
        merged["eligible_for_action_projection"] = eligible
        merged["all_projected_candidates_verified"] = True
        merged["unverified_candidate_projected"] = False
        merged["bridge_status"] = "pass"
        return merged

    def _build_projection(self, sidecar: pd.DataFrame) -> pd.DataFrame:
        if sidecar is None or sidecar.empty:
            return self._empty_projection()
        eligible = sidecar[sidecar.get("eligible_for_action_projection", pd.Series(False, index=sidecar.index)).astype(bool)].copy()
        if eligible.empty:
            return self._empty_projection()

        # Thin projection: only action-readable hints and references.  The full
        # context remains in sidecar and can be recovered through sidecar_id.
        def _num(col: str, default: float = 0.0) -> pd.Series:
            if col in eligible.columns:
                return pd.to_numeric(eligible[col], errors="coerce").fillna(default)
            return pd.Series([default] * len(eligible), index=eligible.index)

        confidence = _num("v8_confidence", 0.50)
        decision_score = _num("decision_score", 0.0)
        residual_reduction = _num("residual_reduction", 0.0).clip(lower=0.0)
        topology = _num("topology_preservation_score", 0.50)
        conflict_penalty = _num("v8_conflict", 0.0) * 0.20
        unresolved_penalty = _num("v8_unresolved", 0.0) * 0.10
        projection_strength = (0.35 * decision_score + 0.25 * confidence + 0.25 * residual_reduction + 0.15 * topology - conflict_penalty - unresolved_penalty).clip(lower=0.05, upper=1.0)

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
                "Task10_action_readable_projection_from_verified_sandbox_and_local_audit__"
                "thin_projection_only__full_context_in_sidecar__no_ActionModule_direct_sidecar_input__RC1"
            ),
        })
        return projection

    def _empty_projection(self) -> pd.DataFrame:
        return pd.DataFrame(columns=[
            "projection_id", "sidecar_id", "candidate_axis_id", "entity_id",
            "graph_object_id", "ot_id", "exploration_axis_hint",
            "action_channel_hint", "target_need_hint", "projection_strength",
            "projection_decision", "sandbox_status", "projection_source_verified",
            "projection_source_local_audit_passed", "projection_source_v8_status",
            "projection_is_thin", "projection_contains_full_sidecar_payload",
            "sidecar_direct_actionmodule_input", "projection_writes_world",
            "projection_writes_gk", "projection_writes_ot",
            "projection_updates_parameter_box", "projection_calls_actionmodule",
            "projection_creates_actionframe", "projection_contract",
        ])
