"""Shared contracts for the modular FullSpec runner RC1.

Task16 validates the coactivation gate after the exploration bridge.
It classifies same-step pressure / exploration / action / shadow / noise
coactivation into allow, dampen, defer, block, or monitor_only before
ActionFrame construction.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional
import pandas as pd


@dataclass(frozen=True)
class FullSpecRunnerConfig:
    """Runtime configuration for Task12 coactivation-gate integration."""

    steps: int = 2
    seed: int = 42
    scenario: str = "normal"
    n_entities: int = 18
    action_coupling: float = 0.045
    noise_scale: float = 0.018
    drift_scale: float = 0.006
    shock_time: int = 18
    shock_strength: float = 0.18
    min_action_strength: float = 0.006
    max_action_strength: float = 0.030
    strength_scale: float = 0.12
    alignment_threshold: float = 0.50
    kt_window: int = 6
    gt_route: str = "legacy"  # legacy | static_pca_7_smoke
    task2_8j_bridge_enabled: bool = False
    action_planning_route: str = "legacy"  # legacy | task2_8j_primary
    world_profile_name: str = "pseudo_reality_default"
    action_profile_name: str = "action_default"
    validation_profile_name: str = "smoke"
    exploration_enabled: bool = True
    run_baseline_shadow: bool = True
    output_prefix: str = "fullspec_task16"
    canonical_commit_enabled: bool = False
    canonical_commit_dry_run: bool = True
    canonical_binding_source: str = "shadow"  # shadow | canonical
    world_engine: str = "pseudo_reality_v1"
    v2_world_profile: str = ""
    v2_world_config: Dict[str, Any] = field(default_factory=dict)
    intermediate_conservatism_mode: str = "relaxed"


@dataclass
class ModuleOutput:
    """Generic module output with payload and audit metadata."""

    name: str
    payload: Dict[str, Any] = field(default_factory=dict)
    audit: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CycleArtifacts:
    """All major artifacts produced in one closed-loop cycle.

    Tables default to empty DataFrames to make audit serialization robust.
    """

    step: int
    seed: int
    scenario: str
    world_trace_before: Optional[Dict[str, pd.DataFrame]] = None
    world_trace_after: Optional[Dict[str, pd.DataFrame]] = None
    baseline_trace_after: Optional[Dict[str, pd.DataFrame]] = None
    entity_trace: pd.DataFrame = field(default_factory=pd.DataFrame)
    relation_trace: pd.DataFrame = field(default_factory=pd.DataFrame)
    v2_hidden_trace: pd.DataFrame = field(default_factory=pd.DataFrame)
    v2_game_trace: pd.DataFrame = field(default_factory=pd.DataFrame)
    v2_resource_trace: pd.DataFrame = field(default_factory=pd.DataFrame)
    v2_information_trace: pd.DataFrame = field(default_factory=pd.DataFrame)
    v2_action_effect_trace: pd.DataFrame = field(default_factory=pd.DataFrame)
    world_trace_audit: pd.DataFrame = field(default_factory=pd.DataFrame)
    world_transition_audit: pd.DataFrame = field(default_factory=pd.DataFrame)
    gt: pd.DataFrame = field(default_factory=pd.DataFrame)
    kt: pd.DataFrame = field(default_factory=pd.DataFrame)
    formal_packet: pd.DataFrame = field(default_factory=pd.DataFrame)
    gk_build_audit: pd.DataFrame = field(default_factory=pd.DataFrame)
    ot_native: pd.DataFrame = field(default_factory=pd.DataFrame)
    ot_action_view: pd.DataFrame = field(default_factory=pd.DataFrame)
    ot_exploration_view: pd.DataFrame = field(default_factory=pd.DataFrame)
    ot_observation_audit: pd.DataFrame = field(default_factory=pd.DataFrame)
    residual_noise_log: pd.DataFrame = field(default_factory=pd.DataFrame)
    residual_noise_ledger_audit: pd.DataFrame = field(default_factory=pd.DataFrame)
    m_observation: pd.DataFrame = field(default_factory=pd.DataFrame)
    weak_pressure: pd.DataFrame = field(default_factory=pd.DataFrame)
    upper_pressure_audit: pd.DataFrame = field(default_factory=pd.DataFrame)
    h11_local_pressure_field: pd.DataFrame = field(default_factory=pd.DataFrame)
    pressure_intent_bundle: pd.DataFrame = field(default_factory=pd.DataFrame)
    pressure_translation_audit: pd.DataFrame = field(default_factory=pd.DataFrame)
    task2_8j_bridge_audit: pd.DataFrame = field(default_factory=pd.DataFrame)
    task2_8j_operator_selection: pd.DataFrame = field(default_factory=pd.DataFrame)
    task2_8j_operator_review: pd.DataFrame = field(default_factory=pd.DataFrame)
    task2_8j_operator_checks: pd.DataFrame = field(default_factory=pd.DataFrame)
    task2_8j_operator_summary: pd.DataFrame = field(default_factory=pd.DataFrame)
    parameter_registry: pd.DataFrame = field(default_factory=pd.DataFrame)
    parameter_updates: pd.DataFrame = field(default_factory=pd.DataFrame)
    shadow_parameter_state: pd.DataFrame = field(default_factory=pd.DataFrame)
    parameter_shadow_audit: pd.DataFrame = field(default_factory=pd.DataFrame)
    parameter_window_binding_audit: pd.DataFrame = field(default_factory=pd.DataFrame)
    commit_gate_audit: pd.DataFrame = field(default_factory=pd.DataFrame)
    rollback_snapshot: pd.DataFrame = field(default_factory=pd.DataFrame)
    canonical_parameter_state: pd.DataFrame = field(default_factory=pd.DataFrame)
    canonical_write_audit: pd.DataFrame = field(default_factory=pd.DataFrame)
    exploration_candidates: pd.DataFrame = field(default_factory=pd.DataFrame)
    exploration_sandbox: pd.DataFrame = field(default_factory=pd.DataFrame)
    exploration_decision: pd.DataFrame = field(default_factory=pd.DataFrame)
    exploration_local_audit: pd.DataFrame = field(default_factory=pd.DataFrame)
    exploration_projection: pd.DataFrame = field(default_factory=pd.DataFrame)
    exploration_sidecar: pd.DataFrame = field(default_factory=pd.DataFrame)
    action_affordance: pd.DataFrame = field(default_factory=pd.DataFrame)
    action_local_audit: pd.DataFrame = field(default_factory=pd.DataFrame)
    action_candidates: pd.DataFrame = field(default_factory=pd.DataFrame)
    local_observation_needs: pd.DataFrame = field(default_factory=pd.DataFrame)
    action_surface_planning_audit: pd.DataFrame = field(default_factory=pd.DataFrame)
    coactivation_gate: pd.DataFrame = field(default_factory=pd.DataFrame)
    action_frame: pd.DataFrame = field(default_factory=pd.DataFrame)
    action_execution_audit: pd.DataFrame = field(default_factory=pd.DataFrame)
    action_result: pd.DataFrame = field(default_factory=pd.DataFrame)
    boundary_guard_audit: pd.DataFrame = field(default_factory=pd.DataFrame)
    boundary_violation_report: pd.DataFrame = field(default_factory=pd.DataFrame)
    cycle_audit_row: pd.DataFrame = field(default_factory=pd.DataFrame)
    boundary_violations: list[str] = field(default_factory=list)
