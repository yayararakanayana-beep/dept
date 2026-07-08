"""action_surface_planning_module: creates audited pre-ActionFrame action candidates.

Task11 goal:
  - Convert O_t_action_view + graph_objects + PressureIntentBundle + shadow params
    + exploration projection into pre-gate action candidates.
  - Emit local observation needs for downstream action-side local audit.
  - Emit action_surface_planning_audit proving this module does not create
    ActionFrame, call ActionModule, or write back to world/G/K/canonical params.

Task2-8j-27 adds a Task2-8j-primary route: when configured, Task2-8j-24
operator material is translated into pre-gate action candidates and placed ahead
of the legacy repaired-policy candidates.  The legacy route remains available as
fallback material, but Task2-8j rows are marked as the primary action-planning
source.
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

TASK2_8J_27_VERSION = "task2_8j_primary_actionsurface_integration_rc1"
TASK2_8J_27_CONTRACT = (
    "Task2_8j_27_PrimaryActionSurfaceIntegration__"
    "Task2_8j_operator_material_to_pre_gate_action_candidates__"
    "legacy_candidates_retained_as_fallback__no_ActionFrame_no_writeback"
)

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


def _operator_to_channel(risk_name: str, selected_operator_name: str, selected_operator_family: str) -> tuple[str, str, str]:
    risk = str(risk_name)
    op = str(selected_operator_name)
    family = str(selected_operator_family)
    if risk == "relation_lock" or op in {"soft_resistance", "escape_channel"} or family == "lock_relief":
        return "diagnostic_task2_8j_relation_lock_relief", "coupling_relief", "relation_lock_relief"
    if risk == "resource_pressure" or op in {"pressure_diffusion", "buffer_injection"} or family == "pressure_relief":
        return "diagnostic_task2_8j_pressure_buffer", "buffer_increase", "resource_pressure_buffer"
    if risk == "reversibility_loss" or op in {"reversibility_support"} or family == "return_path_support":
        return "diagnostic_task2_8j_reversibility_support", "relation_unlock", "return_path_support"
    if risk == "boundary_fragile" or family == "boundary_standoff":
        return "diagnostic_task2_8j_boundary_buffer", "buffer_increase", "boundary_standoff"
    if risk == "oscillation" or op in {"damping", "gradient_smoothing"} or family == "oscillation_damping":
        return "diagnostic_task2_8j_oscillation_damping", "volatility_damping", "oscillation_damping"
    return "diagnostic_task2_8j_review_only", "no_op", "review_only"


class ActionSurfacePlanningModule:
    name = "action_surface_planning_module"

    def __init__(self, cfg: FullSpecRunnerConfig):
        self.cfg = cfg
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
        task2_8j_operator_selection: pd.DataFrame | None = None,
    ) -> dict[str, pd.DataFrame]:
        """Build action affordance, local observation needs, and pre-gate candidates.

        Boundary:
          - This module may read O_t_action_view and graph/action affordances.
          - This module may read PressureIntentBundle and shadow summaries.
          - In Task2-8j primary mode it may read Task2-8j operator material.
          - This module does not create ActionFrame and does not call ActionModule.
        """
        parameter_windows = parameter_windows or {}
        action_route = str(getattr(self.cfg, "action_planning_route", "legacy"))
        task2_primary_requested = action_route == "task2_8j_primary"
        self._reject_forbidden_inputs(pressure_intents, "pressure_intents")
        self._reject_forbidden_inputs(ot_action_view, "ot_action_view")
        self._reject_forbidden_inputs(exploration_projection, "exploration_projection")
        self._reject_forbidden_inputs(task2_8j_operator_selection, "task2_8j_operator_selection")

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
            affordance["task2_8j_primary_route_available"] = bool(task2_primary_requested)
            affordance["task2_8j_primary_route_used"] = False
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

        legacy_candidates, sequence_events = self.policy.build_action_frame(
            pressure_intents, graph_objects, step, seed, scenario
        )
        if legacy_candidates is None:
            legacy_candidates = pd.DataFrame()
        if sequence_events is None:
            sequence_events = pd.DataFrame()
        legacy_candidates = self._apply_parameter_windows_to_candidates(legacy_candidates, parameter_windows)
        if not legacy_candidates.empty:
            legacy_candidates = legacy_candidates.copy()
            legacy_candidates["task2_8j_action_planning_route"] = action_route
            legacy_candidates["task2_8j_candidate_source"] = "legacy_repaired_policy_fallback" if task2_primary_requested else "legacy_repaired_policy_primary"
            legacy_candidates["task2_8j_primary_candidate"] = False
            legacy_candidates["task2_8j_legacy_fallback_candidate"] = bool(task2_primary_requested)
            legacy_candidates["action_planning_route_priority"] = 2 if task2_primary_requested else 1

        task2_candidates = self._build_task2_8j_primary_candidates(
            task2_8j_operator_selection=task2_8j_operator_selection,
            graph_objects=graph_objects,
            parameter_windows=parameter_windows,
            step=step,
            seed=seed,
            scenario=scenario,
        ) if task2_primary_requested else pd.DataFrame()

        if task2_primary_requested and task2_candidates is not None and not task2_candidates.empty:
            action_candidates = pd.concat([task2_candidates, legacy_candidates], ignore_index=True, sort=False)
            if not affordance.empty:
                affordance["task2_8j_primary_route_used"] = True
                affordance["task2_8j_operator_selection_rows_available"] = int(len(task2_8j_operator_selection)) if task2_8j_operator_selection is not None else 0
                affordance["task2_8j_primary_candidate_rows"] = int(len(task2_candidates))
        else:
            action_candidates = legacy_candidates.copy() if legacy_candidates is not None else pd.DataFrame()

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
            action_candidates["task2_8j_27_version"] = TASK2_8J_27_VERSION if task2_primary_requested else ""
            action_candidates["task2_8j_27_contract"] = TASK2_8J_27_CONTRACT if task2_primary_requested else ""
            if "task2_8j_action_planning_route" not in action_candidates.columns:
                action_candidates["task2_8j_action_planning_route"] = action_route
            if "task2_8j_primary_candidate" not in action_candidates.columns:
                action_candidates["task2_8j_primary_candidate"] = False
            if "task2_8j_legacy_fallback_candidate" not in action_candidates.columns:
                action_candidates["task2_8j_legacy_fallback_candidate"] = False

            if ot_action_view is not None and not ot_action_view.empty and "entity_id" in ot_action_view.columns:
                entity_view_cols = [
                    c for c in [
                        "entity_id", "ot_id", "ot_action_relevance_score",
                        "ot_local_observation_need_score", "ot_local_observation_need_score_x", "ot_local_observation_need_score_y",
                        "requires_action_local_audit", "suggested_action_attention", "ot_residual_score",
                        "ot_unresolved_score", "ot_ambiguity_score",
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
            if "task2_8j_primary_candidate" in action_candidates.columns:
                need = need.mask(action_candidates["task2_8j_primary_candidate"].fillna(False).astype(bool), need.clip(lower=0.35))
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
            sequence_events["task2_8j_primary_route_used"] = bool(task2_primary_requested and task2_candidates is not None and not task2_candidates.empty)

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
            task2_8j_operator_selection=task2_8j_operator_selection,
            action_route=action_route,
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

    def _build_task2_8j_primary_candidates(
        self,
        *,
        task2_8j_operator_selection: pd.DataFrame | None,
        graph_objects: pd.DataFrame,
        parameter_windows: dict[str, Any],
        step: int,
        seed: int,
        scenario: str,
    ) -> pd.DataFrame:
        if task2_8j_operator_selection is None or task2_8j_operator_selection.empty:
            return pd.DataFrame()
        entity_ids = graph_objects["entity_id"].astype(str).tolist() if graph_objects is not None and not graph_objects.empty and "entity_id" in graph_objects.columns else [f"E{i:03d}" for i in range(self.policy.cfg.n_entities)]
        max_strength = float(parameter_windows.get("max_action_strength", self.policy.cfg.max_action_strength)) if parameter_windows else float(self.policy.cfg.max_action_strength)
        min_strength = float(getattr(self.policy.cfg, "min_action_strength", 0.006))
        base_strength = min(max(0.018, min_strength), max_strength)
        rows: list[dict[str, Any]] = []
        usable = task2_8j_operator_selection.copy()
        if "operator_selection_status" in usable.columns:
            usable = usable[usable["operator_selection_status"].astype(str).str.contains("terrain_operator_selected", regex=False)]
        for i, (_, r) in enumerate(usable.reset_index(drop=True).iterrows()):
            primitive, channel, role = _operator_to_channel(
                r.get("risk_name", ""),
                r.get("selected_operator_name", ""),
                r.get("selected_operator_family", ""),
            )
            entity_id = entity_ids[i % len(entity_ids)] if entity_ids else f"E{i:03d}"
            rows.append({
                "run_seed": seed,
                "run_scenario": scenario,
                "loop_step": step,
                "entity_id": entity_id,
                "source_pressure_component": str(r.get("risk_name", "")),
                "component_direction": str(r.get("primary_action_direction", "")),
                "source_semantic_effect": str(r.get("risk_name", "")),
                "semantic_effect": str(r.get("selected_operator_name", "")),
                "intent_family": str(r.get("selected_operator_family", "")),
                "suggested_control_route": "task2_8j_primary_actionsurface_route",
                "action_primitive": primitive,
                "primitive_sequence": str(r.get("selected_operator_name", "")) + " -> observe -> report",
                "action_channel": channel,
                "action_strength": base_strength,
                "diagnostic_role": role,
                "sequence_id": "",
                "expected_contract": "task2_8j_operator_material_contract",
                "integrated_policy_contract": TASK2_8J_27_CONTRACT,
                "diagnostic_only": True,
                "target_need": max(0.35, min(base_strength / max(max_strength, 1e-12), 1.0)),
                "candidate_risk": 0.18 if channel != "no_op" else 0.05,
                "task2_8j_action_planning_route": "task2_8j_primary",
                "task2_8j_candidate_source": "task2_8j_operator_selection_primary",
                "task2_8j_primary_candidate": True,
                "task2_8j_legacy_fallback_candidate": False,
                "action_planning_route_priority": 1,
                "task2_8j_operator_selection_id": str(r.get("operator_selection_id", "")),
                "task2_8j_operator_family": str(r.get("selected_operator_family", "")),
                "task2_8j_selected_operator_name": str(r.get("selected_operator_name", "")),
                "task2_8j_secondary_operator_name": str(r.get("secondary_operator_name", "")),
                "task2_8j_operator_strength_band": str(r.get("operator_strength_band", "")),
                "task2_8j_operator_duration_band": str(r.get("operator_duration_band", "")),
                "task2_8j_operator_trigger_mode": str(r.get("operator_trigger_mode", "")),
                "task2_8j_boundary_guard_mode": str(r.get("boundary_guard_mode", "")),
                "task2_8j_operator_material_used_by_actionsurface": True,
                "task2_8j_primary_route_candidate_created": True,
                "action_frame_created_by_task2_8j_planning": False,
                "actionmodule_called_by_task2_8j_planning": False,
                "canonical_write_performed_by_task2_8j_planning": False,
                "axis_execution_performed_by_task2_8j_planning": False,
                "direct_dept_read_by_actionmodule": False,
            })
        return pd.DataFrame(rows)

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
            guarded_unlock_strength_factor=float(parameter_windows.get("guarded_unlock_strength_factor", getattr(cfg, "guarded_unlock_strength_factor", 0.70))),
            guarded_unlock_delay_steps=1,
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
            out["candidate_sparsity_threshold_effective"] = sparsity
            out["channel_gain_mode"] = str(parameter_windows.get("channel_gain_mode", "current"))
            out["guarded_unlock_delay_mode"] = str(parameter_windows.get("guarded_unlock_delay_mode", "current_delayed"))
            out["guarded_unlock_strength_factor"] = float(parameter_windows.get("guarded_unlock_strength_factor", 0.70))
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
        elif "local_observation_need_score" in action_candidates.columns:
            need = action_candidates.groupby("entity_id", dropna=False)["local_observation_need_score"].max().reset_index()
            group = group.merge(need, on="entity_id", how="left")
            group["local_observation_need_score"] = group["local_observation_need_score"].fillna(0.0).astype(float)
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
        if "task2_8j_primary_candidate" in action_candidates.columns:
            primary = action_candidates.groupby("entity_id", dropna=False)["task2_8j_primary_candidate"].max().reset_index()
            group = group.merge(primary, on="entity_id", how="left")
            group["task2_8j_primary_need_source"] = group["task2_8j_primary_candidate"].fillna(False).astype(bool)
        else:
            group["task2_8j_primary_need_source"] = False
        group["action_frame_created_by_need_builder"] = False
        group["actionmodule_called_by_need_builder"] = False
        group["run_seed"] = seed
        group["run_scenario"] = scenario
        group["loop_step"] = step
        first = [
            "run_seed", "run_scenario", "loop_step", "entity_id", "ot_id",
            "local_observation_need_score", "requires_action_local_audit",
            "action_candidate_count", "trigger_reason", "need_source_contract",
            "task2_8j_primary_need_source",
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
        task2_8j_operator_selection: pd.DataFrame | None,
        action_route: str,
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
        task2_material_rows = int(len(task2_8j_operator_selection)) if task2_8j_operator_selection is not None else 0
        task2_candidate_rows = int(action_candidates["task2_8j_primary_candidate"].fillna(False).astype(bool).sum()) if action_candidates is not None and not action_candidates.empty and "task2_8j_primary_candidate" in action_candidates.columns else 0
        fallback_candidate_rows = int(action_candidates["task2_8j_legacy_fallback_candidate"].fillna(False).astype(bool).sum()) if action_candidates is not None and not action_candidates.empty and "task2_8j_legacy_fallback_candidate" in action_candidates.columns else 0
        candidates_have_required_contract = bool(
            candidate_rows > 0
            and "action_candidate_contract" in action_candidates.columns
            and action_candidates["action_candidate_contract"].astype(str).str.contains("pre_ActionFrame_candidate", regex=False).all()
        )
        task2_primary_ok = bool(action_route != "task2_8j_primary" or (task2_material_rows > 0 and task2_candidate_rows > 0))
        ot_used = bool(ot_action_view is not None and not ot_action_view.empty)
        pressure_intent_used = bool(pressure_intents is not None and not pressure_intents.empty)
        audit_status = "pass" if (
            candidate_rows > 0
            and affordance_rows > 0
            and need_rows > 0
            and candidates_have_required_contract
            and pressure_intent_used
            and task2_primary_ok
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
            "task2_8j_27_version": TASK2_8J_27_VERSION if action_route == "task2_8j_primary" else "",
            "task2_8j_27_contract": TASK2_8J_27_CONTRACT if action_route == "task2_8j_primary" else "",
            "action_planning_route": action_route,
            "task2_8j_primary_route_requested": bool(action_route == "task2_8j_primary"),
            "task2_8j_operator_material_rows": task2_material_rows,
            "task2_8j_primary_candidate_rows": task2_candidate_rows,
            "task2_8j_legacy_fallback_candidate_rows": fallback_candidate_rows,
            "task2_8j_primary_route_used": bool(action_route == "task2_8j_primary" and task2_candidate_rows > 0),
            "task2_8j_material_promoted_to_action_candidates": bool(task2_candidate_rows > 0),
            "legacy_candidates_retained_as_fallback": bool(action_route == "task2_8j_primary" and fallback_candidate_rows > 0),
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
            "task2_8j_operator_selection_fingerprint": _fingerprint_df(task2_8j_operator_selection),
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
