"""Modular FullSpec Integrated Closed Loop Runner - Task12 Coactivation Gate RC1.

Task12 goal:
  - Keep Task7 exploration, Task8 local audit, and Task10 exploration bridge.
  - Strengthen coactivation_gate_module so pressure / exploration / action / shadow / noise coactivation is classified before ActionFrame.
  - Preserve the gate as a bounded pre-ActionFrame safety valve, not a full combined-interference solution.

Task2-8j-26 adds an optional FullSpec integration bridge that loads the
Task2-8j material chain through Task2-8j-24 inside a FullSpec cycle.

Task2-8j-27 passes the Task2-8j operator material into ActionSurfacePlanning
when the task2_8j_primary action-planning route is selected.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd

from dept2_fullspec_runner_rc1.contracts import FullSpecRunnerConfig, CycleArtifacts
from dept2_fullspec_runner_rc1.modules.world_adapter import WorldAdapter
from dept2_fullspec_runner_rc1.modules.gk_builder import GKBuilderModule
from dept2_fullspec_runner_rc1.modules.ot_observation_module import OtObservationModule
from dept2_fullspec_runner_rc1.modules.upper_pressure_module import UpperPressureModule
from dept2_fullspec_runner_rc1.modules.pressure_translation_module import PressureTranslationModule
from dept2_fullspec_runner_rc1.modules.parameter_shadow_box import ParameterShadowBox
from dept2_fullspec_runner_rc1.modules.parameter_window_binder import ParameterWindowBinder
from dept2_fullspec_runner_rc1.modules.controlled_canonical_update import ControlledCanonicalUpdateModule, Q8CanonicalConfig
from dept2_fullspec_runner_rc1.modules.exploration_module import ExplorationModule
from dept2_fullspec_runner_rc1.modules.local_audit_module import LocalAuditModule
from dept2_fullspec_runner_rc1.modules.exploration_bridge_module import ExplorationBridgeModule
from dept2_fullspec_runner_rc1.modules.action_surface_planning_module import ActionSurfacePlanningModule
from dept2_fullspec_runner_rc1.modules.coactivation_gate_module import CoactivationGateModule
from dept2_fullspec_runner_rc1.modules.action_execution_module import ActionExecutionModule
from dept2_fullspec_runner_rc1.modules.audit_ledger_module import AuditLedgerModule
from dept2_fullspec_runner_rc1.modules.boundary_guard import BoundaryGuard
from dept2_fullspec_runner_rc1.modules.task2_8j_fullspec_integration_bridge import Task2_8jFullSpecIntegrationBridge

TASK2_8J_OPTIONAL_OUTPUT_TABLES = [
    "task2_8j_bridge_audit",
    "task2_8j_operator_selection",
    "task2_8j_operator_review",
    "task2_8j_operator_checks",
    "task2_8j_operator_summary",
]


class FullSpecIntegratedClosedLoopRunner:
    """13-module runner through Task12 coactivation-gate integration."""

    def __init__(self, cfg: FullSpecRunnerConfig):
        self.cfg = cfg
        self.world_adapter = WorldAdapter(cfg)
        self.gk_builder = GKBuilderModule(cfg)
        self.ot_observation_module = OtObservationModule()
        self.upper_pressure_module = UpperPressureModule()
        self.pressure_translation_module = PressureTranslationModule()
        self.parameter_shadow_box = ParameterShadowBox()
        self.canonical_update_module = ControlledCanonicalUpdateModule(self.parameter_shadow_box.current_params())
        self.parameter_window_binder = ParameterWindowBinder()
        self.exploration_module = ExplorationModule(enabled=cfg.exploration_enabled)
        self.local_audit_module = LocalAuditModule()
        self.exploration_bridge_module = ExplorationBridgeModule()
        self.action_surface_planning_module = ActionSurfacePlanningModule(cfg)
        self.coactivation_gate_module = CoactivationGateModule()
        self.action_execution_module = ActionExecutionModule()
        self.task2_8j_bridge = Task2_8jFullSpecIntegrationBridge()
        self.audit_ledger_module = AuditLedgerModule()
        self.boundary_guard = BoundaryGuard()

    def run(self) -> Dict[str, pd.DataFrame]:
        cycles: List[CycleArtifacts] = []
        trace = self.world_adapter.snapshot()

        for step in range(self.cfg.steps):
            artifacts = self.run_cycle(step=step, trace=trace)
            artifacts.cycle_audit_row = self.audit_ledger_module.build_cycle_row(artifacts)

            # Task15: first-class unified boundary guard after all per-module
            # audits exist.  The guard is diagnostic-only and emits its own
            # audit table plus an optional violation report.
            artifacts.boundary_guard_audit = self.boundary_guard.build_boundary_guard_audit(
                artifacts, artifacts.cycle_audit_row
            )
            artifacts.boundary_violations.extend(
                self.boundary_guard.validate_boundary_guard_audit(artifacts.boundary_guard_audit)
            )
            artifacts.boundary_violations.extend(self.boundary_guard.validate_audit_row(artifacts.cycle_audit_row))
            artifacts.boundary_violation_report = self.boundary_guard.build_boundary_violation_report(
                artifacts.boundary_guard_audit, artifacts.boundary_violations
            )

            # Rebuild row after guard validation so cycle-level violation counts
            # include Task15 guard findings.
            artifacts.cycle_audit_row = self.audit_ledger_module.build_cycle_row(artifacts)
            cycles.append(artifacts)
            trace = artifacts.world_trace_after

        outputs = self.audit_ledger_module.collect_outputs(cycles)
        outputs.update(self._collect_task2_8j_outputs(cycles))
        return outputs

    def run_cycle(self, step: int, trace) -> CycleArtifacts:
        artifacts = CycleArtifacts(step=step, seed=self.cfg.seed, scenario=self.cfg.scenario)
        artifacts.world_trace_before = trace

        # 1. World trace boundary audit before any DEPT-side derivation.
        artifacts.world_trace_audit = self._tag(self.world_adapter.audit_trace(trace, step, phase="before_gk_build"), step)
        artifacts.boundary_violations.extend(self.boundary_guard.validate_world_trace_audit(artifacts.world_trace_audit))

        # 2. World trace -> G/K with read-only fingerprint audit.
        gk_out = self.gk_builder.build(trace, loop_step=step)
        artifacts.gt = self._tag(gk_out["gt"], step)
        artifacts.kt = self._tag(gk_out["kt"], step)
        artifacts.formal_packet = self._tag(gk_out["formal_packet"], step)
        artifacts.gk_build_audit = self._tag(gk_out["gk_build_audit"], step)
        artifacts.boundary_violations.extend(self.boundary_guard.validate_formal_packet(artifacts.formal_packet))
        artifacts.boundary_violations.extend(self.boundary_guard.validate_gk_build_audit(artifacts.gk_build_audit))

        # 3. O_t lower local surface and residual/noise ledger.
        ot_out = self.ot_observation_module.build(trace, artifacts.gt, artifacts.kt)
        artifacts.ot_native = self._tag(ot_out["ot_native"], step)
        artifacts.ot_action_view = self._tag(ot_out["ot_action_view"], step)
        artifacts.ot_exploration_view = self._tag(ot_out["ot_exploration_view"], step)
        artifacts.ot_observation_audit = self._tag(ot_out["ot_observation_audit"], step)
        artifacts.residual_noise_log = self._tag(ot_out["residual_noise_log"], step)
        artifacts.residual_noise_ledger_audit = self._tag(ot_out["residual_noise_ledger_audit"], step)
        graph_objects = self._tag(ot_out["graph_objects"], step)
        artifacts.boundary_violations.extend(self.boundary_guard.validate_ot_outputs(
            artifacts.ot_native, artifacts.ot_action_view, artifacts.ot_exploration_view,
            artifacts.ot_observation_audit, artifacts.residual_noise_log, artifacts.residual_noise_ledger_audit,
        ))

        # 4. Upper pressure from formal G/K only.
        upper_out = self.upper_pressure_module.compute(artifacts.formal_packet, loop_step=step)
        artifacts.m_observation = self._tag(upper_out["m_observation"], step)
        artifacts.weak_pressure = self._tag(upper_out["weak_pressure"], step)
        artifacts.upper_pressure_audit = self._tag(upper_out["upper_pressure_audit"], step)
        artifacts.boundary_violations.extend(self.boundary_guard.validate_upper_pressure_audit(artifacts.upper_pressure_audit))

        # 8 then 5 in execution order: existing RC1 parameter box needs H11 field.
        # This preserves the user's conceptual boundary while binding to current code.
        trans_out = self.pressure_translation_module.translate(artifacts.m_observation, artifacts.weak_pressure, loop_step=step)
        artifacts.h11_local_pressure_field = self._tag(trans_out["h11_local_pressure_field"], step)
        artifacts.pressure_intent_bundle = self._tag(trans_out["pressure_intent_bundle"], step)
        artifacts.pressure_translation_audit = self._tag(trans_out["pressure_translation_audit"], step)
        artifacts.boundary_violations.extend(self.boundary_guard.validate_pressure_translation_audit(artifacts.pressure_translation_audit))

        if bool(getattr(self.cfg, "task2_8j_bridge_enabled", False)):
            task2_8j_out = self.task2_8j_bridge.build(
                gt=artifacts.gt,
                kt=artifacts.kt,
                formal_packet=artifacts.formal_packet,
                ot_action_view=artifacts.ot_action_view,
                pressure_intent_bundle=artifacts.pressure_intent_bundle,
                loop_step=step,
            )
            artifacts.task2_8j_bridge_audit = self._tag(task2_8j_out["task2_8j_bridge_audit"], step)
            artifacts.task2_8j_operator_selection = self._tag(task2_8j_out["task2_8j_operator_selection"], step)
            artifacts.task2_8j_operator_review = self._tag(task2_8j_out["task2_8j_operator_review"], step)
            artifacts.task2_8j_operator_checks = self._tag(task2_8j_out["task2_8j_operator_checks"], step)
            artifacts.task2_8j_operator_summary = self._tag(task2_8j_out["task2_8j_operator_summary"], step)
            if not artifacts.task2_8j_bridge_audit.empty and not bool((artifacts.task2_8j_bridge_audit["bridge_status"].astype(str) == "pass").all()):
                artifacts.boundary_violations.append("task2_8j_26_bridge_status_not_pass")

        shadow_out = self.parameter_shadow_box.update_shadow(artifacts.formal_packet, artifacts.h11_local_pressure_field, loop_step=step)
        artifacts.parameter_registry = self._tag(shadow_out["parameter_registry"], step)
        artifacts.parameter_updates = self._tag(shadow_out["parameter_updates"], step)
        artifacts.shadow_parameter_state = self._tag(shadow_out["shadow_parameter_state"], step)
        artifacts.parameter_shadow_audit = self._tag(shadow_out["parameter_shadow_audit"], step)
        artifacts.boundary_violations.extend(self.boundary_guard.validate_parameter_updates(artifacts.parameter_updates))
        artifacts.boundary_violations.extend(self.boundary_guard.validate_parameter_shadow_audit(artifacts.parameter_shadow_audit))
        shadow_params = self.parameter_shadow_box.current_params()

        # Task22C-Rev1-Q8: controlled canonical update boundary.
        canonical_out = self.canonical_update_module.evaluate(
            shadow_parameter_state=artifacts.shadow_parameter_state,
            parameter_shadow_audit=artifacts.parameter_shadow_audit,
            shadow_current_params=shadow_params,
            loop_step=step,
            config=Q8CanonicalConfig(
                enabled=bool(self.cfg.canonical_commit_enabled),
                dry_run=bool(self.cfg.canonical_commit_dry_run),
                binding_source=str(self.cfg.canonical_binding_source),
            ),
        )
        artifacts.commit_gate_audit = self._tag(canonical_out["commit_gate_audit"], step)
        artifacts.rollback_snapshot = self._tag(canonical_out["rollback_snapshot"], step)
        artifacts.canonical_parameter_state = self._tag(canonical_out["canonical_parameter_state"], step)
        artifacts.canonical_write_audit = self._tag(canonical_out["canonical_write_audit"], step)
        artifacts.boundary_violations.extend(self.boundary_guard.validate_canonical_update(
            artifacts.commit_gate_audit,
            artifacts.rollback_snapshot,
            artifacts.canonical_parameter_state,
            artifacts.canonical_write_audit,
        ))

        binding_params = shadow_params
        if str(self.cfg.canonical_binding_source) == "canonical":
            binding_params = canonical_out["canonical_current_params"]

        # Task22C-Rev1-Q2-U/Q8: bind ParameterBox values to module-owned parameter windows.
        binding_out = self.parameter_window_binder.bind(
            binding_params,
            artifacts.shadow_parameter_state,
            loop_step=step,
            intermediate_conservatism_mode=self.cfg.intermediate_conservatism_mode,
        )
        module_windows = binding_out["module_window_values"]
        artifacts.shadow_parameter_state = self._tag(binding_out["shadow_parameter_state"], step)
        artifacts.parameter_window_binding_audit = self._tag(binding_out["parameter_window_binding_audit"], step)

        # 6. Exploration candidate generation + sandbox + decision.
        exp_out = self.exploration_module.run(
            artifacts.gt,
            artifacts.kt,
            artifacts.ot_exploration_view,
            artifacts.residual_noise_log,
            artifacts.shadow_parameter_state,
            module_windows.get("exploration", {}),
        )
        artifacts.exploration_candidates = self._tag(exp_out["exploration_candidates"], step)
        artifacts.exploration_sandbox = self._tag(exp_out["exploration_sandbox"], step)
        artifacts.exploration_decision = self._tag(exp_out["exploration_decision"], step)

        # 7. Exploration local audit using v8-style support.
        # Task8 made this a first-class persisted artifact; Task10 uses it to validate projection eligibility.
        artifacts.exploration_local_audit = self._tag(
            self.local_audit_module.audit_exploration(artifacts.exploration_candidates, artifacts.ot_exploration_view, module_windows.get("local_audit", binding_params)),
            step,
        )
        artifacts.boundary_violations.extend(self.boundary_guard.validate_local_audit_outputs(artifacts.exploration_local_audit, role="exploration_v8_audit"))
        bridge_out = self.exploration_bridge_module.project(artifacts.exploration_decision, artifacts.exploration_sandbox, artifacts.exploration_local_audit, module_windows.get("bridge", {}))
        artifacts.exploration_projection = self._tag(bridge_out["exploration_projection"], step)
        artifacts.exploration_sidecar = self._tag(bridge_out["exploration_sidecar"], step)
        artifacts.boundary_violations.extend(self.boundary_guard.validate_exploration_bridge(artifacts.exploration_sidecar, artifacts.exploration_projection))

        # 9. Action surface planning: affordance + action candidates.
        action_out = self.action_surface_planning_module.plan(
            graph_objects=graph_objects,
            pressure_intents=artifacts.pressure_intent_bundle,
            shadow_params=binding_params,
            parameter_windows=module_windows.get("action", {}),
            exploration_projection=artifacts.exploration_projection,
            step=step,
            seed=self.cfg.seed,
            scenario=self.cfg.scenario,
            ot_action_view=artifacts.ot_action_view,
            task2_8j_operator_selection=artifacts.task2_8j_operator_selection,
        )
        artifacts.action_affordance = self._tag(action_out["action_affordance"], step)
        artifacts.action_candidates = self._tag(action_out["action_candidates"], step)
        artifacts.local_observation_needs = self._tag(action_out["local_observation_needs"], step)
        artifacts.action_surface_planning_audit = self._tag(action_out["action_surface_planning_audit"], step)
        artifacts.boundary_violations.extend(self.boundary_guard.validate_action_surface_planning_audit(artifacts.action_surface_planning_audit))
        artifacts.boundary_violations.extend(self.boundary_guard.validate_action_surface_outputs(
            artifacts.action_affordance, artifacts.action_candidates, artifacts.local_observation_needs
        ))
        # sequence_events are retained as action_result side-channel in Task11.
        artifacts.action_result = self._tag(action_out["sequence_events"], step)

        # 7. Action candidate local audit using v8 support.
        artifacts.action_local_audit = self._tag(
            self.local_audit_module.audit_action(artifacts.action_candidates, graph_objects, module_windows.get("local_audit", binding_params)),
            step,
        )
        artifacts.boundary_violations.extend(self.boundary_guard.validate_local_audit_outputs(artifacts.action_local_audit, role="action_v8_check"))

        # 11. Coactivation gate.
        artifacts.coactivation_gate = self._tag(
            self.coactivation_gate_module.evaluate(
                artifacts.weak_pressure,
                artifacts.exploration_projection,
                artifacts.action_candidates,
                artifacts.action_local_audit,
                artifacts.shadow_parameter_state,
                artifacts.residual_noise_log,
                module_windows.get("gate", {}),
            ),
            step,
        )
        artifacts.boundary_violations.extend(self.boundary_guard.validate_coactivation_gate(artifacts.coactivation_gate))

        # 12. Build ActionFrame only after gate, then apply through adapter.
        artifacts.action_frame = self._tag(
            self.action_execution_module.build_action_frame(
                artifacts.action_candidates,
                artifacts.coactivation_gate,
                artifacts.action_local_audit,
                artifacts.shadow_parameter_state,
                artifacts.exploration_projection,
            ),
            step,
        )
        artifacts.boundary_violations.extend(self.boundary_guard.validate_action_frame(artifacts.action_frame, artifacts.coactivation_gate))

        artifacts.world_trace_after = self.action_execution_module.apply(self.world_adapter, artifacts.action_frame)
        if isinstance(artifacts.world_trace_after, dict):
            artifacts.entity_trace = self._tag(artifacts.world_trace_after.get("entity_trace", pd.DataFrame()), step)
            artifacts.relation_trace = self._tag(artifacts.world_trace_after.get("relation_trace", pd.DataFrame()), step)
            artifacts.v2_hidden_trace = self._tag(artifacts.world_trace_after.get("v2_hidden_trace", pd.DataFrame()), step)
            artifacts.v2_game_trace = self._tag(artifacts.world_trace_after.get("v2_game_trace", pd.DataFrame()), step)
            artifacts.v2_resource_trace = self._tag(artifacts.world_trace_after.get("v2_resource_trace", pd.DataFrame()), step)
            artifacts.v2_information_trace = self._tag(artifacts.world_trace_after.get("v2_information_trace", pd.DataFrame()), step)
            artifacts.v2_action_effect_trace = self._tag(artifacts.world_trace_after.get("v2_action_effect_trace", pd.DataFrame()), step)
        artifacts.action_execution_audit = self._tag(
            self.action_execution_module.audit_execution_boundary(
                action_candidates=artifacts.action_candidates,
                gate_decision=artifacts.coactivation_gate,
                action_frame=artifacts.action_frame,
                action_local_audit=artifacts.action_local_audit,
                shadow_params=artifacts.shadow_parameter_state,
                exploration_projection=artifacts.exploration_projection,
                exploration_sidecar=artifacts.exploration_sidecar,
                world_trace_before=artifacts.world_trace_before,
                world_trace_after=artifacts.world_trace_after,
            ),
            step,
        )
        artifacts.boundary_violations.extend(self.boundary_guard.validate_action_execution_audit(artifacts.action_execution_audit))
        artifacts.world_transition_audit = self._tag(self.world_adapter.audit_transition(artifacts.world_trace_before, artifacts.world_trace_after, step), step)
        artifacts.boundary_violations.extend(self.boundary_guard.validate_world_transition_audit(artifacts.world_transition_audit))
        artifacts.baseline_trace_after = self.world_adapter.baseline_step() if self.cfg.run_baseline_shadow else None
        return artifacts

    def write_outputs(self, out_dir: Path) -> dict:
        outputs = self.run()
        return self.audit_ledger_module.write_outputs(outputs, out_dir, self.cfg)

    def _tag(self, df: pd.DataFrame, step: int) -> pd.DataFrame:
        if df is None or df.empty:
            return pd.DataFrame() if df is None else df
        out = df.copy()
        out["loop_step"] = step
        out["run_seed"] = self.cfg.seed
        out["run_scenario"] = self.cfg.scenario
        return out

    def _collect_task2_8j_outputs(self, cycles: List[CycleArtifacts]) -> Dict[str, pd.DataFrame]:
        outputs: Dict[str, pd.DataFrame] = {}
        for name in TASK2_8J_OPTIONAL_OUTPUT_TABLES:
            frames = []
            for cycle in cycles:
                df = getattr(cycle, name, pd.DataFrame())
                if df is not None and not df.empty:
                    frames.append(df.copy())
            outputs[name] = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        return outputs


def run_fullspec_task16(cfg: Optional[FullSpecRunnerConfig] = None) -> Dict[str, pd.DataFrame]:
    runner = FullSpecIntegratedClosedLoopRunner(cfg or FullSpecRunnerConfig())
    return runner.run()


def run_fullspec_task10(cfg: Optional[FullSpecRunnerConfig] = None) -> Dict[str, pd.DataFrame]:
    # Backward-compatible alias for Task10 scripts.
    return run_fullspec_task16(cfg)


def run_fullspec_task7(cfg: Optional[FullSpecRunnerConfig] = None) -> Dict[str, pd.DataFrame]:
    # Backward-compatible alias for Task7 scripts.
    return run_fullspec_task16(cfg)


def run_fullspec_task15(cfg: Optional[FullSpecRunnerConfig] = None) -> Dict[str, pd.DataFrame]:
    # Backward-compatible alias for Task7 scripts.
    return run_fullspec_task16(cfg)


def run_fullspec_task14(cfg: Optional[FullSpecRunnerConfig] = None) -> Dict[str, pd.DataFrame]:
    # Backward-compatible alias for Task7 scripts.
    return run_fullspec_task16(cfg)


def run_fullspec_task8(cfg: Optional[FullSpecRunnerConfig] = None) -> Dict[str, pd.DataFrame]:
    # Backward-compatible alias for Task8 scripts.
    return run_fullspec_task16(cfg)
