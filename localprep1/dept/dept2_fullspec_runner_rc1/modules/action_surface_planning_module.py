"""action_surface_planning_module: creates audited pre-ActionFrame action candidates.

Task11 goal:
  - Convert O_t_action_view + graph_objects + PressureIntentBundle + shadow params
    + exploration projection into pre-gate action candidates.
  - Emit local observation needs for downstream action-side local audit.
  - Emit action_surface_planning_audit proving this module does not create
    ActionFrame, call ActionModule, or write back to world/G/K/canonical params.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

import pandas as pd

from DEPT2_ActionModule_ActuationPrimitives_RC1.dept2_system.action_surface import ActionSurface
from DEPT2_ActionModule_ActuationPrimitives_RC1.action_module.integrated_diagnostic_closed_loop import (
    IntegratedDiagnosticConfig,
    RepairedDiagnosticActionPolicy,
)
from dept2_fullspec_runner_rc1.contracts import FullSpecRunnerConfig


_FORBIDDEN_LOWER_DIRECT_COL_PREFIXES = (
    "action_frame", "actionmodule", "world_write", "gk_writeback", "canonical_write",
)


def _fingerprint_df(df: pd.DataFrame | None) -> str:
    if df is None or df.empty:
        return "empty"
    payload = {
        "columns": list(map(str, df.columns)),
        "rows": int(len(df)),
        "head": df.head(20).astype(str).to_dict(orient="records"),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]


def _safe_bool_series(df: pd.DataFrame, col: str, default: bool = False) -> pd.Series:
    if col in df.columns:
        return df[col].fillna(default).astype(bool)
    return pd.Series([default] * len(df), index=df.index)


class ActionSurfacePlanningModule:
    name = "action_surface_planning_module"

    def __init__(self, cfg: FullSpecRunnerConfig):
        self.surface = ActionSurface()
        # The existing repaired policy expects the old diagnostic config.
        self.policy = RepairedDiagnosticActionPolicy(IntegratedDiagnosticConfig(
            steps=cfg.steps,
            n_entities=cfg.n_entities,
            action_coupling=cfg.action_coupling,
            noise_scale=cfg.noise_scale,
            drift_scale=cfg.drift_scale,
            min_action_strength=cfg.min_action_strength,
            max_action_strength=cfg.max_action_strength,
            strength_scale=cfg.strength_scale,
            alignment_threshold=cfg.alignment_threshold,
        ))

    def plan(
        self,
        graph_objects: pd.DataFrame,
        pressure_intents: pd.DataFrame,
        shadow_params: dict[str, Any],
        parameter_windows: dict[str, Any] | None,
        exploration_projection: pd.DataFrame,
        step: int,
        seed: int,
        scenario: str,
        ot_action_view: pd.DataFrame | None = None,
    ) -> dict[str, pd.DataFrame]:
        """Build action affordance, local observation needs, and pre-gate candidates.

        Boundary:
          - This module may read O_t_action_view and graph/action affordances.
          - This module may read PressureIntentBundle and shadow summaries.
          - This module does not create ActionFrame and does not call ActionModule.
        """
        parameter_windows = parameter_windows or {}
        self._reject_forbidden_inputs(pressure_intents, "pressure_intents")
        self._reject_forbidden_inputs(ot_action_view, "ot_action_view")
        self._reject_forbidden_inputs(exploration_projection, "exploration_projection")

        surface_params = dict(shadow_params or {})
        surface_params.update({k: v for k, v in parameter_windows.items() if k != "channel_gain_map"})
        self._configure_policy_from_windows(parameter_windows)

        affordance = self.surface.build_affordance(graph_objects, surface_params)
        if affordance is None:
            affordance = pd.DataFrame()
        if not affordance.empty:
            affordance = affordance.copy()
            affordance["action_surface_planning_stage"] = "affordance_mapping"
            affordance["action_surface_planning_contract"] = (
                "action_surface_planning_uses_Ot_action_view_and_pressure_intents__"
                "pre_ActionFrame_only__Task11_RC1"
            )
            affordance["action_frame_created_by_planning"] = False
            affordance["actionmodule_called_by_planning"] = False
            affordance["planning_writeback_performed"] = False

        if ot_action_view is not None and not ot_action_view.empty and not affordance.empty:
            view_cols = [
                c for c in [
                    "graph_object_id", "ot_id", "ot_action_relevance_score",
                    "ot_local_observation_need_score", "requires_action_local_audit",
                    "suggested_action_attention", "ot_residual_score", "ot_unresolved_score",
                    "ot_ambiguity_score",
                ]
                if c in ot_action_view.columns
            ]
            if "graph_object_id" in view_cols:
                affordance = affordance.merge(
                    ot_action_view[view_cols].drop_duplicates("graph_object_id"),
                    on="graph_object_id",
                    how="left",
                )
                affordance["ot_action_view_used"] = True
                affordance["ot_action_view_contract"] = (
                    "O_t_action_view_merged_into_action_surface_planning__"
                    "not_ActionModule_direct_input__Task11_RC1"
                )
        elif not affordance.empty:
            affordance["ot_action_view_used"] = False

        # Existing repaired policy produces pre-ActionFrame candidates; Task11 audits
        # that these remain candidates only until coactivation gate and action execution.
        action_candidates, sequence_events = self.policy.build_action_frame(
            pressure_intents, graph_objects, step, seed, scenario
        )
        if action_candidates is None:
            action_candidates = pd.DataFrame()
        if sequence_events is None:
            sequence_events = pd.DataFrame()
        action_candidates = self._apply_parameter_windows_to_candidates(action_candidates, parameter_windows)

        if not action_candidates.empty:
            action_candidates = action_candidates.copy()
            action_candidates["candidate_status"] = "pre_gate_candidate"
            action_candidates["action_candidate_contract"] = (
                "ActionSurfacePlanning_pre_ActionFrame_candidate__must_pass_local_audit_and_coactivation_gate__Task11_RC1"
            )
            action_candidates["planning_stage"] = "pre_actionframe_candidate_planning"
            action_candidates["pressure_intent_used"] = True
            action_candidates["shadow_parameter_summary_used"] = bool(shadow_params)
            action_candidates["parameter_window_binding_used"] = bool(parameter_windows)
            action_candidates["exploration_projection_used"] = False if exploration_projection is None or exploration_projection.empty else True
            action_candidates["action_frame_created_by_planning"] = False
            action_candidates["actionmodule_called_by_planning"] = False
            action_candidates["reads_gk_directly"] = False
            action_candidates["reads_ot_directly"] = False
            action_candidates["ot_direct_actionmodule_input"] = False
            action_candidates["canonical_parameter_write"] = False
            action_candidates["world_write_performed"] = False
            action_candidates["gk_writeback_performed"] = False
            if ot_action_view is not None and not ot_action_view.empty and "entity_id" in ot_action_view.columns:
                entity_view_cols = [
                    c for c in [
                        "entity_id", "ot_id", "ot_action_relevance_score",
                        "ot_local_observation_need_score", "requires_action_local_audit",
                        "suggested_action_attention", "ot_residual_score", "ot_unresolved_score",
                        "ot_ambiguity_score",
                    ]
                    if c in ot_action_view.columns
                ]
                action_candidates = action_candidates.merge(
                    ot_action_view[entity_view_cols].drop_duplicates("entity_id"),
                    on="entity_id",
                    how="left",
                )
                action_candidates["ot_action_view_used"] = True
                action_candidates["ot_action_view_contract"] = (
                    "O_t_action_view_used_by_action_surface_planning__not_ActionModule_direct_input__Task11_RC1"
                )
            else:
                action_candidates["ot_action_view_used"] = False

            if "ot_local_observation_need_score" in action_candidates.columns:
                need = action_candidates["ot_local_observation_need_score"].fillna(0.0).astype(float)
            else:
                need = pd.Series([0.0] * len(action_candidates), index=action_candidates.index)
            if "requires_action_local_audit" in action_candidates.columns:
                requires = action_candidates["requires_action_local_audit"].fillna(False).astype(bool)
            else:
                requires = need >= 0.30
            action_candidates["local_observation_need_score"] = need
            action_candidates["requires_action_local_audit"] = requires | (need >= 0.30)

        if not sequence_events.empty:
            sequence_events = sequence_events.copy()
            sequence_events["action_surface_planning_contract"] = (
                "sequence_events_from_repaired_policy__side_channel_only__not_ActionModule_direct_input__Task11_RC1"
            )

        local_observation_needs = self._build_local_observation_needs(
            action_candidates=action_candidates,
            ot_action_view=ot_action_view,
            affordance=affordance,
            step=step,
            seed=seed,
            scenario=scenario,
        )
        planning_audit = self._build_planning_audit(
            graph_objects=graph_objects,
            pressure_intents=pressure_intents,
            shadow_params=shadow_params,
            parameter_windows=parameter_windows,
            exploration_projection=exploration_projection,
            ot_action_view=ot_action_view,
            affordance=affordance,
            action_candidates=action_candidates,
            local_observation_needs=local_observation_needs,
            sequence_events=sequence_events,
            step=step,
            seed=seed,
            scenario=scenario,
        )
        return {
            "action_affordance": affordance,
            "action_candidates": action_candidates,
            "local_observation_needs": local_observation_needs,
            "action_surface_planning_audit": planning_audit,
            "sequence_events": sequence_events,
        }

    def _configure_policy_from_windows(self, parameter_windows: dict[str, Any]) -> None:
        """Bind ParameterBox-derived action windows to the internal policy config."""
        if not parameter_windows:
            return
        cfg = self.policy.cfg
        self.policy.cfg = IntegratedDiagnosticConfig(
            steps=cfg.steps,
            n_entities=cfg.n_entities,
            action_coupling=cfg.action_coupling,
            noise_scale=cfg.noise_scale,
            drift_scale=cfg.drift_scale,
            min_action_strength=cfg.min_action_strength,
            max_action_strength=float(parameter_windows.get("max_action_strength", cfg.max_action_strength)),
            strength_scale=float(parameter_windows.get("strength_scale", cfg.strength_scale)),
            alignment_threshold=cfg.alignment_threshold,
            min_observed_abs=cfg.min_observed_abs,
            run_isolated_semantic_shadow=cfg.run_isolated_semantic_shadow,
        )

    def _apply_parameter_windows_to_candidates(self, action_candidates: pd.DataFrame, parameter_windows: dict[str, Any]) -> pd.DataFrame:
        if action_candidates is None or action_candidates.empty or not parameter_windows:
            return action_candidates if action_candidates is not None else pd.DataFrame()
        out = action_candidates.copy()
        gain_map = parameter_windows.get("channel_gain_map", {}) or {}
        max_strength = float(parameter_windows.get("max_action_strength", 0.030))
        sparsity = float(parameter_windows.get("candidate_sparsity_threshold", 0.0))
        if "action_strength" in out.columns:
            base_strength = pd.to_numeric(out["action_strength"], errors="coerce").fillna(0.0)
            out["action_strength_before_parameter_window"] = base_strength
            gains = out.get("action_channel", pd.Series([""] * len(out), index=out.index)).astype(str).map(lambda c: float(gain_map.get(c, 1.0)))
            out["parameter_window_gain"] = gains
            out["action_strength"] = (base_strength * gains).clip(lower=0.0, upper=max_strength)
            denom = max(max_strength, 1e-12)
            out["candidate_relative_strength_after_window"] = (out["action_strength"] / denom).clip(lower=0.0, upper=1.0)
            out["candidate_sparsity_threshold"] = sparsity
            out["candidate_passes_parameter_window"] = out["candidate_relative_strength_after_window"] >= sparsity
            if not bool(out["candidate_passes_parameter_window"].any()) and len(out):
                keep_idx = out["candidate_relative_strength_after_window"].idxmax()
                out.loc[keep_idx, "candidate_passes_parameter_window"] = True
                out["candidate_window_rescue_keep_top"] = out.index == keep_idx
            else:
                out["candidate_window_rescue_keep_top"] = False
            out = out[out["candidate_passes_parameter_window"].astype(bool)].copy()
        else:
            out["parameter_window_gain"] = 1.0
            out["candidate_sparsity_threshold"] = sparsity
            out["candidate_passes_parameter_window"] = True
            out["candidate_window_rescue_keep_top"] = False
        out["parameter_window_binding_used"] = True
        return out

    def _build_local_observation_needs(
        self,
        action_candidates: pd.DataFrame,
        ot_action_view: pd.DataFrame | None,
        affordance: pd.DataFrame,
        step: int,
        seed: int,
        scenario: str,
    ) -> pd.DataFrame:
        if action_candidates is None or action_candidates.empty:
            return pd.DataFrame(columns=[
                "run_seed", "run_scenario", "loop_step", "entity_id", "ot_id",
                "local_observation_need_score", "requires_action_local_audit",
                "action_candidate_count", "trigger_reason", "need_source_contract",
            ])
        group = action_candidates.groupby("entity_id", dropna=False).agg(
            action_candidate_count=("entity_id", "size"),
            max_action_strength=("action_strength", "max") if "action_strength" in action_candidates.columns else ("entity_id", "size"),
        ).reset_index()
        if "ot_local_observation_need_score" in action_candidates.columns:
            need = action_candidates.groupby("entity_id", dropna=False)["ot_local_observation_need_score"].max().reset_index()
            group = group.merge(need, on="entity_id", how="left")
            group["local_observation_need_score"] = group["ot_local_observation_need_score"].fillna(0.0).astype(float)
            group = group.drop(columns=["ot_local_observation_need_score"])
        else:
            group["local_observation_need_score"] = 0.0
        if "requires_action_local_audit" in action_candidates.columns:
            req = action_candidates.groupby("entity_id", dropna=False)["requires_action_local_audit"].max().reset_index()
            group = group.merge(req, on="entity_id", how="left")
        else:
            group["requires_action_local_audit"] = False
        if "ot_id" in action_candidates.columns:
            oid = action_candidates.groupby("entity_id", dropna=False)["ot_id"].first().reset_index()
            group = group.merge(oid, on="entity_id", how="left")
        else:
            group["ot_id"] = ""
        group["requires_action_local_audit"] = group["requires_action_local_audit"].fillna(False).astype(bool) | (group["local_observation_need_score"] >= 0.30)
        group["trigger_reason"] = group.apply(
            lambda r: "ot_need_or_candidate_density" if bool(r["requires_action_local_audit"]) else "routine_action_surface_context",
            axis=1,
        )
        group["need_source_contract"] = (
            "local_observation_needs_from_O_t_action_view_and_pre_gate_action_candidates__Task11_RC1"
        )
        group["action_frame_created_by_need_builder"] = False
        group["actionmodule_called_by_need_builder"] = False
        group["run_seed"] = seed
        group["run_scenario"] = scenario
        group["loop_step"] = step
        # Put stable columns first.
        first = [
            "run_seed", "run_scenario", "loop_step", "entity_id", "ot_id",
            "local_observation_need_score", "requires_action_local_audit",
            "action_candidate_count", "trigger_reason", "need_source_contract",
            "action_frame_created_by_need_builder", "actionmodule_called_by_need_builder",
        ]
        rest = [c for c in group.columns if c not in first]
        return group[first + rest]

    def _build_planning_audit(
        self,
        graph_objects: pd.DataFrame,
        pressure_intents: pd.DataFrame,
        shadow_params: dict[str, Any],
        parameter_windows: dict[str, Any] | None,
        exploration_projection: pd.DataFrame,
        ot_action_view: pd.DataFrame | None,
        affordance: pd.DataFrame,
        action_candidates: pd.DataFrame,
        local_observation_needs: pd.DataFrame,
        sequence_events: pd.DataFrame,
        step: int,
        seed: int,
        scenario: str,
    ) -> pd.DataFrame:
        action_frame_created = False
        actionmodule_called = False
        writeback_performed = False
        lower_direct_to_actionmodule = False
        candidate_rows = int(len(action_candidates)) if action_candidates is not None else 0
        affordance_rows = int(len(affordance)) if affordance is not None else 0
        need_rows = int(len(local_observation_needs)) if local_observation_needs is not None else 0
        candidates_have_required_contract = bool(
            candidate_rows > 0
            and "action_candidate_contract" in action_candidates.columns
            and action_candidates["action_candidate_contract"].astype(str).str.contains("pre_ActionFrame_candidate", regex=False).all()
        )
        ot_used = bool(ot_action_view is not None and not ot_action_view.empty)
        pressure_intent_used = bool(pressure_intents is not None and not pressure_intents.empty)
        audit_status = "pass" if (
            candidate_rows > 0
            and affordance_rows > 0
            and need_rows > 0
            and candidates_have_required_contract
            and pressure_intent_used
            and not action_frame_created
            and not actionmodule_called
            and not writeback_performed
            and not lower_direct_to_actionmodule
        ) else "watch"
        row = {
            "run_seed": seed,
            "run_scenario": scenario,
            "loop_step": step,
            "planning_contract": (
                "action_surface_planning_pre_ActionFrame_only__uses_Ot_action_view_pressure_intents_shadow_and_exploration_projection__Task11_RC1"
            ),
            "audit_status": audit_status,
            "graph_object_rows": int(len(graph_objects)) if graph_objects is not None else 0,
            "pressure_intent_rows": int(len(pressure_intents)) if pressure_intents is not None else 0,
            "ot_action_view_rows": int(len(ot_action_view)) if ot_action_view is not None else 0,
            "affordance_rows": affordance_rows,
            "action_candidate_rows": candidate_rows,
            "local_observation_need_rows": need_rows,
            "sequence_event_rows": int(len(sequence_events)) if sequence_events is not None else 0,
            "pressure_intent_used": pressure_intent_used,
            "ot_action_view_used": ot_used,
            "shadow_parameter_summary_used": bool(shadow_params),
            "parameter_window_binding_used": bool(parameter_windows),
            "action_affordance_floor_bound": float((parameter_windows or {}).get("action_affordance_floor", 0.025)),
            "candidate_sparsity_threshold_bound": float((parameter_windows or {}).get("candidate_sparsity_threshold", 0.0)),
            "max_action_strength_bound": float((parameter_windows or {}).get("max_action_strength", 0.030)),
            "strength_scale_bound": float((parameter_windows or {}).get("strength_scale", 0.12)),
            "exploration_projection_used": bool(exploration_projection is not None and not exploration_projection.empty),
            "candidates_have_required_contract": candidates_have_required_contract,
            "action_frame_created_by_planning": action_frame_created,
            "actionmodule_called_by_planning": actionmodule_called,
            "planning_writeback_performed": writeback_performed,
            "canonical_write_performed": False,
            "world_write_performed": False,
            "gk_writeback_performed": False,
            "ot_direct_actionmodule_input": lower_direct_to_actionmodule,
            "v8_direct_actionmodule_input": False,
            "exploration_sidecar_direct_actionmodule_input": False,
            "graph_objects_fingerprint": _fingerprint_df(graph_objects),
            "pressure_intents_fingerprint": _fingerprint_df(pressure_intents),
            "ot_action_view_fingerprint": _fingerprint_df(ot_action_view),
            "affordance_fingerprint": _fingerprint_df(affordance),
            "action_candidates_fingerprint": _fingerprint_df(action_candidates),
            "local_observation_needs_fingerprint": _fingerprint_df(local_observation_needs),
        }
        return pd.DataFrame([row])

    def _reject_forbidden_inputs(self, df: pd.DataFrame | None, name: str) -> None:
        if df is None or df.empty:
            return
        forbidden = [c for c in df.columns if str(c).startswith(_FORBIDDEN_LOWER_DIRECT_COL_PREFIXES)]
        if forbidden:
            raise ValueError(f"{self.name} received forbidden direct-action/writeback columns in {name}: {forbidden}")
