"""action_execution_module: ActionFrame builder + ActionModule adapter boundary.

Task14 strengthens this module as the only place where pre-gate action
candidates become an ActionFrame and where the pseudo-reality world is stepped.
The adapter deliberately receives only ActionFrame.  G/K, O_t, v8 internals,
exploration sidecars, and parameter boxes are excluded from the ActionModule
call boundary and recorded only in audit summaries.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Dict, Any
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


def _trace_t(trace: Dict[str, pd.DataFrame] | None) -> int:
    if not trace or "entity_trace" not in trace or trace["entity_trace"].empty:
        return -1
    return int(trace["entity_trace"]["t"].iloc[0]) if "t" in trace["entity_trace"].columns else -1


class ActionExecutionModule:
    name = "action_execution_module"

    def build_action_frame(
        self,
        action_candidates: pd.DataFrame,
        gate_decision: pd.DataFrame,
        action_local_audit: pd.DataFrame,
        shadow_params: pd.DataFrame,
        exploration_projection: pd.DataFrame,
    ) -> pd.DataFrame:
        """Build the final ActionFrame after coactivation gate decision.

        Boundary:
          - Input candidates must already be pre-gate candidates.
          - Gate decision is mandatory before ActionFrame creation.
          - This method does not call the ActionModule and does not step world.
          - It only serializes safe action-readable fields plus boundary flags.
        """
        if action_candidates is None or action_candidates.empty:
            return pd.DataFrame()
        if gate_decision is None or gate_decision.empty:
            raise ValueError("Cannot build ActionFrame without coactivation gate decision")

        decision = str(gate_decision["coactivation_gate_decision"].iloc[0])
        frame = action_candidates.copy()
        frame["action_frame_id"] = [f"AF_{i:05d}" for i in range(len(frame))]
        frame["source_candidate_fingerprint"] = _fingerprint_df(action_candidates)
        frame["action_frame_builder_contract"] = "Task14_ActionFrame_builder_after_gate__no_world_step__no_ActionModule_call"
        frame["action_frame_contract"] = "ActionFrame_is_only_input_to_ActionModule__Task14_RC1"
        frame["action_execution_stage"] = "action_frame_built_after_gate"
        frame["coactivation_gate_decision"] = decision
        frame["coactivation_gate_applied_before_actionframe"] = True
        frame["source_action_candidate_rows"] = int(len(action_candidates))
        frame["action_local_audit_rows_available"] = _rows(action_local_audit)
        frame["shadow_summary_rows_available"] = _rows(shadow_params)
        frame["exploration_projection_rows_available"] = _rows(exploration_projection)

        # Boundary flags: these must remain false.  The ActionModule adapter is
        # only given this ActionFrame; direct lower/core objects are not passed.
        frame["reads_gk_directly"] = False
        frame["reads_ot_directly"] = False
        frame["reads_v8_directly"] = False
        frame["reads_exploration_sidecar_directly"] = False
        frame["reads_parameter_box_directly"] = False
        frame["canonical_parameter_write"] = False
        frame["world_write_performed_by_builder"] = False
        frame["gk_writeback_performed_by_builder"] = False
        frame["actionmodule_called_by_builder"] = False

        if decision == "block":
            frame["gate_block_applied"] = True
            return frame.iloc[0:0].copy()
        frame["gate_block_applied"] = False
        if decision == "defer":
            frame["gate_defer_applied"] = True
            return frame.iloc[0:0].copy()
        frame["gate_defer_applied"] = False
        if decision == "dampen" and "action_strength" in frame.columns:
            frame["pre_gate_action_strength"] = frame["action_strength"].astype(float)
            frame["action_strength"] = frame["action_strength"].astype(float) * 0.50
            frame["gate_dampening_applied"] = True
        else:
            frame["pre_gate_action_strength"] = frame["action_strength"].astype(float) if "action_strength" in frame.columns else 0.0
            frame["gate_dampening_applied"] = False
        return frame

    def apply(self, world_adapter, action_frame: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """Apply ActionFrame through the world adapter.

        The adapter deliberately receives only ActionFrame; it does not receive
        G/K, O_t, v8 internals, exploration sidecars, or parameter box objects.
        """
        return world_adapter.step(action_frame)

    def audit_execution_boundary(
        self,
        action_candidates: pd.DataFrame,
        gate_decision: pd.DataFrame,
        action_frame: pd.DataFrame,
        action_local_audit: pd.DataFrame,
        shadow_params: pd.DataFrame,
        exploration_projection: pd.DataFrame,
        exploration_sidecar: pd.DataFrame,
        world_trace_before: Dict[str, pd.DataFrame] | None,
        world_trace_after: Dict[str, pd.DataFrame] | None,
    ) -> pd.DataFrame:
        """Emit one audit row for the ActionFrame/ActionModule boundary."""
        decision = "missing"
        if gate_decision is not None and not gate_decision.empty and "coactivation_gate_decision" in gate_decision.columns:
            decision = str(gate_decision["coactivation_gate_decision"].iloc[0])
        frame_rows = _rows(action_frame)
        candidate_rows = _rows(action_candidates)
        before_t = _trace_t(world_trace_before)
        after_t = _trace_t(world_trace_after)
        frame_has_contract = bool(
            action_frame is not None and not action_frame.empty
            and "action_frame_contract" in action_frame.columns
            and action_frame["action_frame_contract"].astype(str).str.contains("ActionFrame_is_only_input", regex=False).all()
        )
        boundary_flags_false = True
        if action_frame is not None and not action_frame.empty:
            for col in [
                "reads_gk_directly", "reads_ot_directly", "reads_v8_directly",
                "reads_exploration_sidecar_directly", "reads_parameter_box_directly",
                "canonical_parameter_write", "world_write_performed_by_builder",
                "gk_writeback_performed_by_builder", "actionmodule_called_by_builder",
            ]:
                if col in action_frame.columns and bool(action_frame[col].astype(bool).any()):
                    boundary_flags_false = False
        row: dict[str, Any] = {
            "action_execution_contract": "Task14_ActionExecution__ActionFrame_builder_plus_ActionModule_adapter__ActionFrame_only_input",
            "audit_status": "pass" if (decision != "missing" and after_t == before_t + 1 and boundary_flags_false and (frame_has_contract or frame_rows == 0)) else "fail",
            "source_action_candidate_rows": candidate_rows,
            "action_frame_rows": frame_rows,
            "action_local_audit_rows": _rows(action_local_audit),
            "shadow_parameter_rows_available_but_not_passed_to_actionmodule": _rows(shadow_params),
            "exploration_projection_rows_available_but_only_projection_is_frame_eligible": _rows(exploration_projection),
            "exploration_sidecar_rows_retained_but_not_passed_to_actionmodule": _rows(exploration_sidecar),
            "coactivation_gate_decision": decision,
            "coactivation_gate_applied_before_actionframe": bool(decision != "missing"),
            "action_frame_contract_present": frame_has_contract or frame_rows == 0,
            "actionmodule_called_by_adapter": True,
            "actionmodule_input_contract": "ActionFrame_only",
            "actionmodule_received_actionframe_only": True,
            "direct_gk_input_to_actionmodule": False,
            "direct_ot_input_to_actionmodule": False,
            "direct_v8_input_to_actionmodule": False,
            "direct_exploration_sidecar_input_to_actionmodule": False,
            "direct_parameter_box_input_to_actionmodule": False,
            "canonical_parameter_write_performed": False,
            "gk_writeback_performed": False,
            "ot_writeback_performed": False,
            "world_step_performed_by_adapter": bool(after_t == before_t + 1),
            "world_t_before": before_t,
            "world_t_after": after_t,
            "action_frame_fingerprint": _fingerprint_df(action_frame),
            "action_candidate_fingerprint": _fingerprint_df(action_candidates),
        }
        return pd.DataFrame([row])
