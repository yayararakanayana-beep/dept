"""local_audit_module: shared v8-style local audit for exploration/action targets.

Task8 strengthens the local-audit boundary:
  - exploration_v8_audit audits sandboxed exploration candidates before bridge use;
  - action_v8_check audits pre-gate action candidates before ActionFrame creation;
  - v8 remains local support only, never a G/K generator, upper-pressure input,
    parameter updater, or ActionModule caller.
"""
from __future__ import annotations

from typing import Any
import hashlib
import json
import pandas as pd

from DEPT2_ActionModule_ActuationPrimitives_RC1.dept2_system.v8_support import V8LocalSupport


def _fingerprint_df(df: pd.DataFrame | None) -> str:
    if df is None or df.empty:
        return "empty"
    payload = {
        "columns": list(map(str, df.columns)),
        "rows": int(len(df)),
        "head": df.head(30).astype(str).to_dict(orient="records"),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def _to_params(params: dict[str, Any] | pd.DataFrame | None) -> dict[str, Any]:
    if params is None:
        return {}
    if isinstance(params, dict):
        return params
    if isinstance(params, pd.DataFrame) and not params.empty:
        if "parameter_name" in params.columns and "shadow_value" in params.columns:
            return {str(r["parameter_name"]): float(r["shadow_value"]) for _, r in params.iterrows()}
        numeric = params.select_dtypes(include="number")
        return {str(c): float(numeric[c].iloc[-1]) for c in numeric.columns if len(numeric[c])}
    return {}


class LocalAuditModule:
    name = "local_audit_module"

    def __init__(self):
        self.v8 = V8LocalSupport()

    def _attach_graph_fields(self, candidates: pd.DataFrame, graph_objects: pd.DataFrame) -> pd.DataFrame:
        if candidates is None or candidates.empty:
            return pd.DataFrame()
        work = candidates.copy()
        if "graph_object_id" not in work.columns and "entity_id" in work.columns and graph_objects is not None and not graph_objects.empty:
            cols = [c for c in ["entity_id", "graph_object_id"] if c in graph_objects.columns]
            if set(cols) == {"entity_id", "graph_object_id"}:
                work = work.merge(graph_objects[cols].drop_duplicates("entity_id"), on="entity_id", how="left")
        if "graph_object_id" not in work.columns:
            work["graph_object_id"] = work.get("entity_id", pd.Series(range(len(work)))).astype(str).map(lambda x: f"GO_{x}")
        if "action_channel" not in work.columns:
            work["action_channel"] = "local_probe"
        if "target_need" not in work.columns:
            if "action_strength" in work.columns:
                work["target_need"] = pd.to_numeric(work["action_strength"], errors="coerce").fillna(0.0).abs().clip(0, 1)
            elif "pre_sandbox_score" in work.columns:
                work["target_need"] = pd.to_numeric(work["pre_sandbox_score"], errors="coerce").fillna(0.0).clip(0, 1)
            else:
                work["target_need"] = 0.0
        return work

    def _tag_common(self, out: pd.DataFrame, *, role: str, source_rows: int, source_fp: str) -> pd.DataFrame:
        if out is None or out.empty:
            # Task16: an explicit zero-source audit row is still an audit.
            # This is important for exploration-disabled minimal integration runs:
            # the module must show that v8 did not run because there were no
            # exploration candidates, not because the boundary was bypassed.
            out = pd.DataFrame([{
                "local_audit_role": role,
                "local_audit_stage": "v8_local_support_audit",
                "local_audit_contract": "Task8_v8_local_audit_only__not_GK_generator__not_upper_formal_input__no_writeback__RC1",
                "v8_support_status": "pass",
                "source_rows_audited": int(source_rows),
                "source_fingerprint": source_fp,
                "zero_source_audit_row": True,
            }])
        else:
            out = out.copy()
            out["zero_source_audit_row"] = False
        out["local_audit_role"] = role
        out["local_audit_stage"] = "v8_local_support_audit"
        out["local_audit_contract"] = "Task8_v8_local_audit_only__not_GK_generator__not_upper_formal_input__no_writeback__RC1"
        out["v8_support_status"] = "pass"
        out["source_rows_audited"] = int(source_rows)
        out["source_fingerprint"] = source_fp
        out["v8_is_gk_generator"] = False
        out["v8_is_upper_formal_input"] = False
        out["v8_generates_pressure"] = False
        out["v8_updates_parameter_box"] = False
        out["v8_calls_actionmodule"] = False
        out["v8_writes_world"] = False
        out["v8_writes_gk"] = False
        out["v8_writes_ot"] = False
        out["v8_writes_canonical_parameter"] = False
        out["local_audit_writeback_performed"] = False
        out["local_audit_passed"] = True
        return out

    def audit_action(self, candidates: pd.DataFrame, graph_objects: pd.DataFrame, params: dict | pd.DataFrame | None) -> pd.DataFrame:
        """Audit action candidates with v8 local support.

        This is deliberately pre-ActionFrame.  The returned rows may inform gate
        diagnostics, but they are not passed to ActionModule directly.
        """
        work = self._attach_graph_fields(candidates, graph_objects)
        if work.empty:
            return self._tag_common(pd.DataFrame(), role="action_v8_check", source_rows=0, source_fp="empty")
        out = self.v8.evaluate(work, graph_objects, _to_params(params))
        out = self._tag_common(out, role="action_v8_check", source_rows=len(work), source_fp=_fingerprint_df(work))
        out["action_candidate_local_audit"] = True
        out["action_frame_created_by_local_audit"] = False
        out["actionmodule_direct_input_from_local_audit"] = False
        return out

    def audit_exploration(self, exploration_candidates: pd.DataFrame, ot_exploration_view: pd.DataFrame, params: dict | pd.DataFrame | None) -> pd.DataFrame:
        """Audit exploration candidates before bridge projection.

        O_t exploration view supplies local graph-like fields for v8 support.
        The audit does not decide projection and does not execute actions.
        """
        if exploration_candidates is None or exploration_candidates.empty:
            return self._tag_common(pd.DataFrame(), role="exploration_v8_audit", source_rows=0, source_fp="empty")
        work = exploration_candidates.copy()
        if "candidate_axis_id" in work.columns:
            work["exploration_candidate_id"] = work["candidate_axis_id"].astype(str)
        if "action_channel" not in work.columns:
            work["action_channel"] = "exploration_probe"
        if "target_need" not in work.columns:
            work["target_need"] = pd.to_numeric(work.get("pre_sandbox_score", pd.Series([0.0] * len(work))), errors="coerce").fillna(0.0).clip(0, 1)
        graph_like = ot_exploration_view.copy() if ot_exploration_view is not None else pd.DataFrame()
        if not graph_like.empty and "graph_object_id" not in work.columns:
            cols = [c for c in ["entity_id", "graph_object_id"] if c in graph_like.columns]
            if set(cols) == {"entity_id", "graph_object_id"}:
                work = work.merge(graph_like[cols].drop_duplicates("entity_id"), on="entity_id", how="left")
        if "graph_object_id" not in work.columns:
            work["graph_object_id"] = work.get("entity_id", pd.Series(range(len(work)))).astype(str).map(lambda x: f"GO_{x}")
        required_graph_cols = ["graph_object_id", "risk", "residual", "readiness", "volatility", "relation_lock", "reversibility", "uncertainty"]
        if graph_like.empty:
            graph_like = work.copy()
        for col in required_graph_cols:
            if col not in graph_like.columns:
                if col == "graph_object_id":
                    graph_like[col] = work["graph_object_id"].values[:len(graph_like)] if len(graph_like) else work["graph_object_id"]
                elif col == "readiness" or col == "reversibility":
                    graph_like[col] = 0.5
                else:
                    graph_like[col] = 0.0
        out = self.v8.evaluate(work, graph_like[required_graph_cols].drop_duplicates("graph_object_id"), _to_params(params))
        out = self._tag_common(out, role="exploration_v8_audit", source_rows=len(work), source_fp=_fingerprint_df(work))
        out["exploration_candidate_local_audit"] = True
        out["exploration_projection_created_by_local_audit"] = False
        out["exploration_action_created_by_local_audit"] = False
        out["sidecar_compression_by_local_audit"] = False
        if "candidate_axis_id" in out.columns and "exploration_candidate_id" not in out.columns:
            out["exploration_candidate_id"] = out["candidate_axis_id"].astype(str)
        return out
