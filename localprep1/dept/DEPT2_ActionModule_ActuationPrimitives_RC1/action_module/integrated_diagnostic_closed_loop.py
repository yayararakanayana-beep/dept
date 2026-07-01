"""IntegratedDiagnosticClosedLoop RC1.

Runs a fresh end-to-end diagnostic closed loop using the repaired validation
action-module policy.

Execution chain:
    pseudo reality
    -> G_t / K_t_global
    -> formal H-DEPT input
    -> M_t
    -> approved pressure
    -> H11-local pressure reception
    -> PressureIntentBundle
    -> repaired diagnostic action policy
    -> pseudo reality
    -> fresh outcome trace

Boundary:
    - H-DEPT pressure generation is not tuned here.
    - This is diagnostic validation, not deployment safety.
    - Formal H-DEPT input remains G_t global + K_t global only.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple
import copy
import json
import numpy as np
import pandas as pd

from DEPT2_ActionModule_ActuationPrimitives_RC1.pseudo_reality.system import (
    PseudoRealityConfig,
    PseudoRealitySystem,
    STATE_FEATURES,
)
from DEPT2_ActionModule_ActuationPrimitives_RC1.pseudo_reality.observation import (
    GtKtBuilder,
    GraphObjectBuilder,
)
from DEPT2_ActionModule_ActuationPrimitives_RC1.dept2_system.hdept_observer import HDEPTObserver
from DEPT2_ActionModule_ActuationPrimitives_RC1.dept2_system.h11_local import H11LocalPressureReceiver
from DEPT2_ActionModule_ActuationPrimitives_RC1.dept2_system.pressure_intent import HDEPTPressureIntentAnnotator
from DEPT2_ActionModule_ActuationPrimitives_RC1.dept2_system.parameter_box import LowerParameterGovernanceBox
from DEPT2_ActionModule_ActuationPrimitives_RC1.dept2_system.action_surface import ActionSurface
from DEPT2_ActionModule_ActuationPrimitives_RC1.dept2_system.v8_support import V8LocalSupport
from DEPT2_ActionModule_ActuationPrimitives_RC1.dept2_system.final_gate import FinalGate


TASK = "IntegratedDiagnosticClosedLoop_RC1"


@dataclass(frozen=True)
class IntegratedDiagnosticConfig:
    steps: int = 8
    n_entities: int = 18
    action_coupling: float = 0.045
    noise_scale: float = 0.018
    drift_scale: float = 0.006
    min_action_strength: float = 0.006
    max_action_strength: float = 0.030
    strength_scale: float = 0.12
    alignment_threshold: float = 0.50
    min_observed_abs: float = 1e-12
    run_isolated_semantic_shadow: bool = True


EXPECTED_CONTRACTS: Dict[str, Dict[str, int]] = {
    "diagnostic_resolution_down": {"conflict": -1, "uncertainty": -1, "m_overall": 1},
    "diagnostic_resolution_up": {"exploration": 1, "uncertainty": 1},
    "exploration_attempt_frequency_up": {"exploration": 1, "uncertainty": 1, "overconvergence": -1},
    "exploration_attempt_frequency_down": {"exploration": -1, "uncertainty": -1, "overconvergence": 1},
    "sandbox_probe_entry_up": {"exploration": 1, "uncertainty": 1},
    "sandbox_probe_entry_down": {"exploration": -1, "overconvergence": 1},
    "sandbox_probe_entry_down_stabilization": {"conflict": -1, "uncertainty": -1, "m_overall": 1},
    "adoption_barrier_relief": {"exploration": 1, "overconvergence": -1, "m_overall": 1},
    "adoption_barrier_raise": {"exploration": -1, "overconvergence": 1},
    "rollback_guard_down": {"conflict": -1, "uncertainty": -1, "m_overall": 1},
    "rollback_guard_up": {"conflict": -1, "uncertainty": -1, "m_overall": 1},
    "sensitivity_opening": {"exploration": 1, "uncertainty": 1, "overconvergence": -1},
    "sensitivity_deadzone_widen": {"exploration": -1, "uncertainty": -1},
    "update_access_opening": {"exploration": 1, "overconvergence": -1, "uncertainty": -1, "m_overall": 1},
    "update_waiting_longer": {"exploration": -1, "uncertainty": -1},
    "hysteresis_guard_down": {"conflict": -1, "overconvergence": -1, "m_overall": 1},
    "hysteresis_guard_up": {"overconvergence": 1, "uncertainty": -1},
    "update_frequency_up": {"exploration": 1, "overconvergence": -1, "uncertainty": -1, "m_overall": 1},
    "update_frequency_down": {"exploration": -1, "uncertainty": -1, "overconvergence": 1},
    "intensity_cap_brake": {"conflict": -1, "uncertainty": -1, "m_overall": 1},
    "intensity_cap_relief": {"exploration": 1, "uncertainty": 1},
    "commitment_strength_down": {"conflict": -1, "overconvergence": -1, "m_overall": 1},
    "commitment_strength_up": {"overconvergence": 1, "uncertainty": -1},
}


def summarize_trace(trace: Dict[str, pd.DataFrame]) -> Dict[str, float]:
    e = trace["entity_trace"]
    summary = {feat: float(e[feat].mean()) for feat in STATE_FEATURES if feat in e.columns}
    conflict = float((e["volatility"] + e["uncertainty"] + e["relation_lock"] + e["coupling"]).mean() / 4.0)
    overconvergence = float((e["relation_lock"] + e["coupling"] - e["exploration"] - e["entropy"]).mean() / 2.0)
    m_overall = float(
        (e["exploration"] + e["reversibility"] + e["entropy"]).mean()
        - (e["volatility"] + e["uncertainty"] + e["relation_lock"] + e["coupling"]).mean() / 4.0
    )
    summary.update({
        "conflict": conflict,
        "overconvergence": overconvergence,
        "m_overall": m_overall,
    })
    return summary


def delta_summary(active: Dict[str, float], baseline: Dict[str, float]) -> Dict[str, float]:
    keys = sorted(set(active) | set(baseline))
    return {f"observed_delta_{k}": float(active.get(k, 0.0) - baseline.get(k, 0.0)) for k in keys}


def _match_contract(contract: Dict[str, int], observed: Dict[str, float], threshold: float, min_abs: float) -> Tuple[float, bool, str, int]:
    if not contract:
        return 0.0, False, "no_contract", 0
    hits = 0
    details = []
    for feat, sign in contract.items():
        val = float(observed.get(f"observed_delta_{feat}", 0.0))
        match = abs(val) > min_abs and np.sign(val) == np.sign(sign)
        hits += int(match)
        details.append(f"{feat}:expected={sign},observed={val:.6f},match={bool(match)}")
    score = float(hits / max(len(contract), 1))
    return score, bool(score >= threshold), "; ".join(details), len(contract)


def _contract_to_string(contract: Dict[str, int]) -> str:
    return ";".join(f"{k}:{v:+d}" for k, v in sorted(contract.items()))


class RepairedDiagnosticActionPolicy:
    """Validation-only repaired diagnostic action policy.

    The policy preserves semantic effects into weak diagnostic actions and
    incorporates the earlier repairs:
        - primitive mapping repair
        - expected-effect contract patch
        - probe-restraint role split
        - guarded delayed unlock sequence
    """

    SEQUENCE_SEMANTICS = {"hysteresis_guard_down", "commitment_strength_down"}

    BASE_MAP: Dict[str, Tuple[str, str, str, str]] = {
        "diagnostic_resolution_down": ("diagnostic_observation_saving_probe", "lighter_observation -> report", "uncertainty_probe", "observation_cost_saving"),
        "diagnostic_resolution_up": ("diagnostic_detail_probe", "detail_probe -> observe -> report", "uncertainty_probe", "observation_detail"),
        "exploration_attempt_frequency_up": ("diagnostic_exploration_attempt", "exploration_attempt -> observe -> report", "exploration_injection", "exploration_attempt"),
        "exploration_attempt_frequency_down": ("diagnostic_exploration_restraint_v2", "exploration_restraint -> reduce_exploration_attempt -> observe -> report", "diagnostic_exploration_restraint", "exploration_restraint"),
        "sandbox_probe_entry_up": ("diagnostic_sandbox_probe", "sandbox_probe -> observe -> report", "exploration_injection", "exploration_observation"),
        "sandbox_probe_entry_down": ("diagnostic_probe_restraint_direct_v1", "probe_restraint_direct -> reduce_probe_entry -> observe -> report", "diagnostic_probe_restraint_direct", "direct_probe_restraint"),
        "sandbox_probe_entry_down_stabilization": ("diagnostic_probe_restraint_stabilization_guard", "probe_restraint_stabilization -> buffer_guard -> observe -> report", "buffer_increase", "stabilization_guard"),
        "adoption_barrier_relief": ("diagnostic_adoption_opening_probe", "adoption_opening -> observe -> report", "exploration_injection", "adoption_opening"),
        "adoption_barrier_raise": ("diagnostic_adoption_guard", "adoption_guard -> observe -> report", "buffer_increase", "adoption_guard"),
        "rollback_guard_down": ("diagnostic_rollback_relaxation_probe", "rollback_relaxation -> observe -> report", "buffer_increase", "safety_relaxation"),
        "rollback_guard_up": ("diagnostic_rollback_guard_probe", "rollback_guard -> observe -> report", "buffer_increase", "safety_guard"),
        "sensitivity_opening": ("diagnostic_sensitivity_opening_probe_v2", "sensitivity_opening -> exploratory_response_probe -> observe -> report", "exploration_injection", "response_opening"),
        "sensitivity_deadzone_widen": ("diagnostic_response_restraint", "response_restraint -> observe -> report", "buffer_increase", "response_restraint"),
        "update_access_opening": ("diagnostic_update_access_probe", "update_access_probe -> observe -> report", "uncertainty_probe", "temporal_opening"),
        "update_waiting_longer": ("diagnostic_update_waiting_probe", "update_waiting -> observe -> report", "buffer_increase", "temporal_brake"),
        "hysteresis_guard_down": ("diagnostic_coupling_relief_then_guarded_unlock", "coupling_relief -> observe -> guarded_relation_unlock", "coupling_relief", "switching_flexibility"),
        "hysteresis_guard_up": ("diagnostic_hysteresis_guard", "hysteresis_guard -> observe -> report", "buffer_increase", "persistence_guard"),
        "update_frequency_up": ("diagnostic_update_frequency_probe", "update_frequency_probe -> observe -> report", "uncertainty_probe", "update_opening"),
        "update_frequency_down": ("diagnostic_update_restraint_v2", "update_restraint -> reduce_update_churn -> observe -> report", "diagnostic_update_restraint", "update_restraint"),
        "intensity_cap_brake": ("buffer_first", "buffer -> replan", "buffer_increase", "positive_control"),
        "intensity_cap_relief": ("diagnostic_intensity_relief_probe", "intensity_relief -> observe -> report", "exploration_injection", "capacity_opening"),
        "commitment_strength_down": ("diagnostic_coupling_relief_then_guarded_unlock", "coupling_relief -> observe -> guarded_relation_unlock", "coupling_relief", "commitment_relief"),
        "commitment_strength_up": ("diagnostic_commitment_guard", "commitment_guard -> observe -> report", "buffer_increase", "commitment_guard"),
    }

    def __init__(self, cfg: IntegratedDiagnosticConfig):
        self.cfg = cfg
        self.pending: List[dict] = []
        self._sequence_counter = 0

    def _strength(self, row: pd.Series) -> float:
        magnitude = abs(float(row.get("component_magnitude", row.get("h11_local_received_pressure", row.get("max_component_magnitude", 0.05)))))
        if magnitude <= 0:
            magnitude = 0.05
        return float(np.clip(magnitude * self.cfg.strength_scale, self.cfg.min_action_strength, self.cfg.max_action_strength))

    def _next_sequence_id(self, step: int, semantic: str) -> str:
        self._sequence_counter += 1
        return f"seq_{step:03d}_{semantic}_{self._sequence_counter:05d}"

    def build_action_frame(
        self,
        intents: pd.DataFrame,
        graph_objects: pd.DataFrame,
        step: int,
        seed: int,
        scenario: str,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        if intents is None or intents.empty:
            return pd.DataFrame(), pd.DataFrame()

        entity_ids = graph_objects["entity_id"].tolist() if graph_objects is not None and not graph_objects.empty and "entity_id" in graph_objects.columns else []
        if not entity_ids:
            entity_ids = [f"E{i:03d}" for i in range(self.cfg.n_entities)]

        action_rows: List[dict] = []
        event_rows: List[dict] = []

        # First, release pending guarded relation-unlock events scheduled in previous step.
        remaining_pending: List[dict] = []
        for pending in self.pending:
            if int(pending["execute_step"]) <= int(step):
                row = {
                    **pending,
                    "run_seed": seed,
                    "run_scenario": scenario,
                    "loop_step": step,
                    "entity_id": entity_ids[len(action_rows) % len(entity_ids)],
                    "action_primitive": "guarded_relation_unlock",
                    "primitive_sequence": "coupling_relief -> observe -> guarded_relation_unlock",
                    "action_channel": "guarded_relation_unlock",
                    "action_strength": pending["action_strength"],
                    "diagnostic_role": "guarded_delayed_unlock",
                    "source_semantic_effect": pending["source_semantic_effect"],
                    "semantic_effect": pending["source_semantic_effect"],
                    "intent_family": pending["intent_family"],
                    "expected_contract": _contract_to_string(EXPECTED_CONTRACTS.get(pending["source_semantic_effect"], EXPECTED_SEQUENCE_CONTRACT if 'EXPECTED_SEQUENCE_CONTRACT' in globals() else {})),
                    "integrated_policy_contract": TASK + "__pending_guarded_relation_unlock",
                    "diagnostic_only": True,
                }
                action_rows.append(row)
                event_rows.append({
                    "sequence_id": pending["sequence_id"],
                    "source_semantic_effect": pending["source_semantic_effect"],
                    "event_type": "execute_guarded_relation_unlock",
                    "scheduled_step": pending["scheduled_step"],
                    "execute_step": step,
                    "action_strength": pending["action_strength"],
                    "sequence_contract": TASK + "__guarded_delayed_unlock_event",
                })
            else:
                remaining_pending.append(pending)
        self.pending = remaining_pending

        for i, (_, intent) in enumerate(intents.reset_index(drop=True).iterrows()):
            semantic = str(intent.get("semantic_effect", ""))
            if semantic not in self.BASE_MAP:
                continue
            primitive, sequence, channel, role = self.BASE_MAP[semantic]
            strength = self._strength(intent)
            entity_id = entity_ids[(i + len(action_rows)) % len(entity_ids)]

            if semantic == "sandbox_probe_entry_down":
                # Role split: preserve direct probe-restraint and add stabilization guard as separate behavior.
                for split_semantic, split_primitive, split_sequence, split_channel, split_role in [
                    ("sandbox_probe_entry_down", "diagnostic_probe_restraint_direct_v1", "probe_restraint_direct -> reduce_probe_entry -> observe -> report", "diagnostic_probe_restraint_direct", "direct_probe_restraint"),
                    ("sandbox_probe_entry_down_stabilization", "diagnostic_probe_restraint_stabilization_guard", "probe_restraint_stabilization -> buffer_guard -> observe -> report", "buffer_increase", "stabilization_guard"),
                ]:
                    action_rows.append({
                        "run_seed": seed,
                        "run_scenario": scenario,
                        "loop_step": step,
                        "entity_id": entity_id,
                        "source_pressure_component": intent.get("pressure_component", ""),
                        "component_direction": intent.get("component_direction", ""),
                        "source_semantic_effect": semantic,
                        "semantic_effect": split_semantic,
                        "intent_family": split_role if split_semantic.endswith("_stabilization") else intent.get("intent_family", ""),
                        "suggested_control_route": intent.get("suggested_control_route", ""),
                        "action_primitive": split_primitive,
                        "primitive_sequence": split_sequence,
                        "action_channel": split_channel,
                        "action_strength": strength,
                        "diagnostic_role": split_role,
                        "sequence_id": "",
                        "expected_contract": _contract_to_string(EXPECTED_CONTRACTS.get(split_semantic, {})),
                        "integrated_policy_contract": TASK + "__probe_restraint_role_split",
                        "diagnostic_only": True,
                    })
                continue

            sequence_id = ""
            if semantic in self.SEQUENCE_SEMANTICS:
                sequence_id = self._next_sequence_id(step, semantic)
                # Current action is coupling relief. Guarded unlock occurs next step.
                self.pending.append({
                    "sequence_id": sequence_id,
                    "source_semantic_effect": semantic,
                    "intent_family": str(intent.get("intent_family", "")),
                    "scheduled_step": step,
                    "execute_step": step + 1,
                    "action_strength": strength * 0.70,
                })
                event_rows.append({
                    "sequence_id": sequence_id,
                    "source_semantic_effect": semantic,
                    "event_type": "schedule_guarded_relation_unlock",
                    "scheduled_step": step,
                    "execute_step": step + 1,
                    "action_strength": strength * 0.70,
                    "sequence_contract": TASK + "__guarded_delayed_unlock_event",
                })

            action_rows.append({
                "run_seed": seed,
                "run_scenario": scenario,
                "loop_step": step,
                "entity_id": entity_id,
                "source_pressure_component": intent.get("pressure_component", ""),
                "component_direction": intent.get("component_direction", ""),
                "source_semantic_effect": semantic,
                "semantic_effect": semantic,
                "intent_family": intent.get("intent_family", ""),
                "suggested_control_route": intent.get("suggested_control_route", ""),
                "action_primitive": primitive,
                "primitive_sequence": sequence,
                "action_channel": channel,
                "action_strength": strength,
                "diagnostic_role": role,
                "sequence_id": sequence_id,
                "expected_contract": _contract_to_string(EXPECTED_CONTRACTS.get(semantic, {})),
                "integrated_policy_contract": TASK + "__repaired_diagnostic_action_policy",
                "diagnostic_only": True,
            })

        return pd.DataFrame(action_rows), pd.DataFrame(event_rows)


def _apply_extended_channels(world: PseudoRealitySystem, action_frame: pd.DataFrame) -> None:
    if action_frame is None or action_frame.empty:
        return
    e = world.entities.copy()
    cfg = world.config
    for _, row in action_frame.iterrows():
        ch = str(row.get("action_channel", ""))
        if ch not in {
            "diagnostic_exploration_restraint",
            "diagnostic_update_restraint",
            "diagnostic_probe_restraint_direct",
            "guarded_relation_unlock",
        }:
            continue
        idx = e["entity_id"] == row["entity_id"]
        if not idx.any():
            continue
        strength = float(np.clip(row.get("action_strength", 0.0), 0.0, 1.0)) * cfg.action_coupling

        if ch == "diagnostic_exploration_restraint":
            e.loc[idx, "exploration"] -= strength
            e.loc[idx, "uncertainty"] -= strength * 0.45
            e.loc[idx, "entropy"] -= strength * 0.30
            e.loc[idx, "relation_lock"] += strength * 0.10
        elif ch == "diagnostic_update_restraint":
            e.loc[idx, "exploration"] -= strength * 0.75
            e.loc[idx, "uncertainty"] -= strength * 0.65
            e.loc[idx, "entropy"] -= strength * 0.25
            e.loc[idx, "relation_lock"] += strength * 0.08
        elif ch == "diagnostic_probe_restraint_direct":
            e.loc[idx, "exploration"] -= strength
            e.loc[idx, "entropy"] -= strength * 0.35
            e.loc[idx, "relation_lock"] += strength * 0.45
            e.loc[idx, "uncertainty"] += strength * 0.10
        elif ch == "guarded_relation_unlock":
            e.loc[idx, "relation_lock"] -= strength
            e.loc[idx, "coupling"] -= strength * 0.30
            e.loc[idx, "reversibility"] += strength * 0.35
            e.loc[idx, "uncertainty"] -= strength * 0.20

    for feat in STATE_FEATURES:
        e[feat] = np.clip(e[feat], 0.02, 0.98)
    world.entities = e


def step_with_repaired_actions(world: PseudoRealitySystem, action_frame: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    if action_frame is None or action_frame.empty:
        return world.step(None)
    extended_channels = {
        "diagnostic_exploration_restraint",
        "diagnostic_update_restraint",
        "diagnostic_probe_restraint_direct",
        "guarded_relation_unlock",
    }
    base = action_frame[~action_frame["action_channel"].isin(extended_channels)].copy()
    ext = action_frame[action_frame["action_channel"].isin(extended_channels)].copy()
    trace = world.step(base if not base.empty else None)
    if not ext.empty:
        _apply_extended_channels(world, ext)
        trace = world.emit_trace()
    return trace


def isolated_semantic_shadow_outcomes(
    world: PseudoRealitySystem,
    action_frame: pd.DataFrame,
    cfg: IntegratedDiagnosticConfig,
) -> pd.DataFrame:
    if action_frame is None or action_frame.empty:
        return pd.DataFrame()
    rows = []
    group_cols = ["run_seed", "run_scenario", "loop_step", "semantic_effect", "intent_family"]
    for (seed, scenario, step, semantic, family), group in action_frame.groupby(group_cols, dropna=False):
        active = copy.deepcopy(world)
        baseline = copy.deepcopy(world)
        active_trace = step_with_repaired_actions(active, group.copy())
        baseline_trace = baseline.step(None)
        d = delta_summary(summarize_trace(active_trace), summarize_trace(baseline_trace))
        contract = EXPECTED_CONTRACTS.get(str(semantic), {})
        score, passed, details, n = _match_contract(contract, d, cfg.alignment_threshold, cfg.min_observed_abs)
        rows.append({
            "run_seed": int(seed),
            "run_scenario": str(scenario),
            "loop_step": int(step),
            "semantic_effect": str(semantic),
            "intent_family": str(family),
            "action_rows": int(len(group)),
            "action_mass": float(group["action_strength"].sum()) if "action_strength" in group.columns else 0.0,
            "action_primitives": "|".join(sorted(set(group["action_primitive"].dropna().astype(str)))) if "action_primitive" in group.columns else "",
            "action_channels": "|".join(sorted(set(group["action_channel"].dropna().astype(str)))) if "action_channel" in group.columns else "",
            "expected_feature_count": int(n),
            "integrated_alignment_score": float(score),
            "integrated_alignment_pass": bool(passed),
            "integrated_alignment_details": details,
            "integrated_outcome_verdict": "integrated_semantic_aligned" if passed else "integrated_semantic_misaligned",
            "shadow_contract": TASK + "__fresh_isolated_semantic_shadow",
            **d,
        })
    return pd.DataFrame(rows)


def summarize_semantic_alignment(isolated: pd.DataFrame) -> pd.DataFrame:
    if isolated is None or isolated.empty:
        return pd.DataFrame()
    return isolated.groupby(["semantic_effect", "intent_family"], as_index=False).agg(
        rows=("semantic_effect", "size"),
        action_rows=("action_rows", "sum"),
        mean_action_mass=("action_mass", "mean"),
        action_primitives=("action_primitives", lambda s: "|".join(sorted(set(s.dropna().astype(str))))),
        action_channels=("action_channels", lambda s: "|".join(sorted(set(s.dropna().astype(str))))),
        mean_alignment_score=("integrated_alignment_score", "mean"),
        alignment_pass_rate=("integrated_alignment_pass", "mean"),
        mean_delta_conflict=("observed_delta_conflict", "mean"),
        mean_delta_uncertainty=("observed_delta_uncertainty", "mean"),
        mean_delta_exploration=("observed_delta_exploration", "mean"),
        mean_delta_overconvergence=("observed_delta_overconvergence", "mean"),
        mean_delta_m_overall=("observed_delta_m_overall", "mean"),
        dominant_verdict=("integrated_outcome_verdict", lambda s: str(s.value_counts().index[0]) if len(s) else "none"),
    ).sort_values(["alignment_pass_rate", "mean_alignment_score"], ascending=[True, True])


def run_one(seed: int, scenario: str, cfg: IntegratedDiagnosticConfig) -> Dict[str, pd.DataFrame]:
    world = PseudoRealitySystem(PseudoRealityConfig(
        seed=seed,
        scenario=scenario,
        n_entities=cfg.n_entities,
        action_coupling=cfg.action_coupling,
        noise_scale=cfg.noise_scale,
        drift_scale=cfg.drift_scale,
    ))
    baseline_world = PseudoRealitySystem(PseudoRealityConfig(
        seed=seed,
        scenario=scenario,
        n_entities=cfg.n_entities,
        action_coupling=cfg.action_coupling,
        noise_scale=cfg.noise_scale,
        drift_scale=cfg.drift_scale,
    ))

    gk = GtKtBuilder(kt_window=6)
    go_builder = GraphObjectBuilder()
    hdept = HDEPTObserver()
    h11 = H11LocalPressureReceiver()
    annotator = HDEPTPressureIntentAnnotator()
    params = LowerParameterGovernanceBox()
    surface = ActionSurface()
    v8 = V8LocalSupport()
    gate = FinalGate()
    policy = RepairedDiagnosticActionPolicy(cfg)

    collected: Dict[str, List[pd.DataFrame]] = {k: [] for k in [
        "gt_global",
        "kt_global",
        "formal_gtkt_packets",
        "m_observation",
        "pressure_candidates",
        "h11_local_pressure_field",
        "pressure_intent_bundle",
        "parameter_registry",
        "parameter_updates",
        "graph_objects_audit",
        "action_surface_affordance",
        "v8_affordance_support",
        "final_gate_audit",
        "integrated_action_frame",
        "integrated_sequence_events",
        "integrated_combined_outcomes",
        "integrated_isolated_semantic_outcomes",
        "integrated_loop_metrics",
    ]}

    trace = world.emit_trace()
    baseline_trace = baseline_world.emit_trace()
    prev_pressure = None

    for step in range(cfg.steps):
        # Observe current active state.
        gt = gk.build_gt(trace)
        kt = gk.build_kt_global()
        formal = gk.build_formal_packet(gt, kt)
        m = hdept.observe_m(formal)
        pressure = hdept.propose_pressure(m, prev_pressure=prev_pressure)
        prev_pressure = pressure.copy()
        h11_field = h11.receive(m, pressure)
        intents = annotator.annotate(h11_field)
        registry, param_updates = params.update(formal, h11_field)
        param_values = params.current_params()
        graph_objects = go_builder.build(trace)
        affordance = surface.build_affordance(graph_objects, param_values)
        v8_affordance = v8.evaluate(affordance, graph_objects, param_values) if not affordance.empty else pd.DataFrame()
        final_audit = gate.decide(v8_affordance, param_values) if not v8_affordance.empty else pd.DataFrame()

        action_frame, sequence_events = policy.build_action_frame(intents, graph_objects, step, seed, scenario)

        # Isolated shadow uses pre-action world state.
        isolated = isolated_semantic_shadow_outcomes(world, action_frame, cfg) if cfg.run_isolated_semantic_shadow else pd.DataFrame()

        # Apply combined repaired actions for actual closed-loop transition.
        active_after = step_with_repaired_actions(world, action_frame)
        baseline_after = baseline_world.step(None)
        combined_delta = delta_summary(summarize_trace(active_after), summarize_trace(baseline_after))
        combined_score_rows = []
        if not action_frame.empty:
            for semantic, grp in action_frame.groupby("semantic_effect", dropna=False):
                contract = EXPECTED_CONTRACTS.get(str(semantic), {})
                score, passed, details, n = _match_contract(contract, combined_delta, cfg.alignment_threshold, cfg.min_observed_abs)
                combined_score_rows.append({
                    "run_seed": seed,
                    "run_scenario": scenario,
                    "loop_step": step,
                    "semantic_effect": str(semantic),
                    "action_rows": int(len(grp)),
                    "action_mass": float(grp["action_strength"].sum()),
                    "combined_alignment_score": float(score),
                    "combined_alignment_pass": bool(passed),
                    "combined_alignment_details": details,
                    "combined_contract_feature_count": int(n),
                    "combined_outcome_contract": TASK + "__fresh_combined_step_outcome",
                    **combined_delta,
                })
        combined_outcomes = pd.DataFrame(combined_score_rows)

        # Tag metadata on core tables.
        for df in [gt, kt, formal, m, pressure, h11_field, intents, registry, param_updates, graph_objects, affordance, v8_affordance, final_audit, action_frame, sequence_events, isolated, combined_outcomes]:
            if df is not None and not df.empty:
                df["loop_step"] = step
                df["run_seed"] = seed
                df["run_scenario"] = scenario

        tables = {
            "gt_global": gt,
            "kt_global": kt,
            "formal_gtkt_packets": formal,
            "m_observation": m,
            "pressure_candidates": pressure,
            "h11_local_pressure_field": h11_field,
            "pressure_intent_bundle": intents,
            "parameter_registry": registry,
            "parameter_updates": param_updates,
            "graph_objects_audit": graph_objects,
            "action_surface_affordance": affordance,
            "v8_affordance_support": v8_affordance,
            "final_gate_audit": final_audit,
            "integrated_action_frame": action_frame,
            "integrated_sequence_events": sequence_events,
            "integrated_combined_outcomes": combined_outcomes,
            "integrated_isolated_semantic_outcomes": isolated,
        }
        for name, df in tables.items():
            if df is not None and not df.empty:
                collected[name].append(df.copy())

        metrics = pd.DataFrame([{
            "run_seed": seed,
            "run_scenario": scenario,
            "loop_step": step,
            "gt_conflict_mean": float(gt["gt_conflict"].mean()),
            "gt_uncertainty_mean": float(gt["gt_uncertainty"].mean()),
            "gt_exploration_mean": float(gt["gt_exploration"].mean()),
            "gt_overconvergence_mean": float(gt["gt_overconvergence"].mean()),
            "m_mean_overall": float(m["m_mean_overall"].mean()),
            "approved_pressure_l1": float(pressure["approved_component_l1"].mean()),
            "intent_rows": int(len(intents)),
            "action_rows": int(len(action_frame)),
            "action_mass": float(action_frame["action_strength"].sum()) if not action_frame.empty else 0.0,
            "unique_semantic_effects": int(action_frame["semantic_effect"].nunique()) if not action_frame.empty else 0,
            "sequence_event_rows": int(len(sequence_events)),
            "isolated_rows": int(len(isolated)),
            "isolated_pass_rate": float(isolated["integrated_alignment_pass"].mean()) if not isolated.empty else 0.0,
            "combined_rows": int(len(combined_outcomes)),
            "combined_pass_rate": float(combined_outcomes["combined_alignment_pass"].mean()) if not combined_outcomes.empty else 0.0,
            "observed_delta_conflict": float(combined_delta.get("observed_delta_conflict", 0.0)),
            "observed_delta_uncertainty": float(combined_delta.get("observed_delta_uncertainty", 0.0)),
            "observed_delta_exploration": float(combined_delta.get("observed_delta_exploration", 0.0)),
            "observed_delta_overconvergence": float(combined_delta.get("observed_delta_overconvergence", 0.0)),
            "observed_delta_m_overall": float(combined_delta.get("observed_delta_m_overall", 0.0)),
            "formal_input_contract": str(formal["formal_hdept_input_contract"].iloc[0]),
            "integrated_loop_contract": TASK + "__fresh_end_to_end_repaired_diagnostic_policy",
        }])
        collected["integrated_loop_metrics"].append(metrics)

        trace = active_after
        baseline_trace = baseline_after

    return {
        name: pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
        for name, frames in collected.items()
    }


def run_many(seeds: List[int], scenarios: List[str], cfg: IntegratedDiagnosticConfig) -> Dict[str, pd.DataFrame]:
    merged: Dict[str, List[pd.DataFrame]] = {}
    for seed in seeds:
        for scenario in scenarios:
            out = run_one(seed, scenario, cfg)
            for name, df in out.items():
                if name not in merged:
                    merged[name] = []
                if df is not None and not df.empty:
                    merged[name].append(df)
    return {name: pd.concat(frames, ignore_index=True) if frames else pd.DataFrame() for name, frames in merged.items()}


def build_summary(outputs: Dict[str, pd.DataFrame], cfg: IntegratedDiagnosticConfig) -> dict:
    metrics = outputs.get("integrated_loop_metrics", pd.DataFrame())
    actions = outputs.get("integrated_action_frame", pd.DataFrame())
    isolated = outputs.get("integrated_isolated_semantic_outcomes", pd.DataFrame())
    sequence = outputs.get("integrated_sequence_events", pd.DataFrame())
    semantic_summary = summarize_semantic_alignment(isolated)

    return {
        "task": TASK,
        "status": "completed" if not metrics.empty else "empty",
        "steps_per_run": int(cfg.steps),
        "run_count": int(metrics[["run_seed", "run_scenario"]].drop_duplicates().shape[0]) if not metrics.empty else 0,
        "metric_rows": int(len(metrics)),
        "action_rows": int(len(actions)),
        "unique_semantic_effects": int(actions["semantic_effect"].nunique()) if not actions.empty else 0,
        "sequence_event_rows": int(len(sequence)),
        "isolated_outcome_rows": int(len(isolated)),
        "isolated_alignment_pass_rate": float(isolated["integrated_alignment_pass"].mean()) if not isolated.empty else 0.0,
        "isolated_mean_alignment_score": float(isolated["integrated_alignment_score"].mean()) if not isolated.empty else 0.0,
        "combined_mean_pass_rate": float(metrics["combined_pass_rate"].mean()) if not metrics.empty else 0.0,
        "mean_action_rows_per_step": float(metrics["action_rows"].mean()) if not metrics.empty else 0.0,
        "mean_action_mass_per_step": float(metrics["action_mass"].mean()) if not metrics.empty else 0.0,
        "mean_delta_conflict": float(metrics["observed_delta_conflict"].mean()) if not metrics.empty else 0.0,
        "mean_delta_uncertainty": float(metrics["observed_delta_uncertainty"].mean()) if not metrics.empty else 0.0,
        "mean_delta_exploration": float(metrics["observed_delta_exploration"].mean()) if not metrics.empty else 0.0,
        "mean_delta_overconvergence": float(metrics["observed_delta_overconvergence"].mean()) if not metrics.empty else 0.0,
        "mean_delta_m_overall": float(metrics["observed_delta_m_overall"].mean()) if not metrics.empty else 0.0,
        "weakest_semantic_effects": semantic_summary.head(6).to_dict(orient="records") if not semantic_summary.empty else [],
        "strongest_semantic_effects": semantic_summary.sort_values(["alignment_pass_rate", "mean_alignment_score"], ascending=[False, False]).head(6).to_dict(orient="records") if not semantic_summary.empty else [],
        "pressure_tuning_readiness": "not_ready_rc3_audit_required",
        "next_recommended_task": "PressureOutcomeAlignmentAudit_RC3",
        "all_sanity_checks_passed": bool(
            not metrics.empty
            and not actions.empty
            and not isolated.empty
            and int(actions["semantic_effect"].nunique()) >= 10
            and len(sequence) > 0
            and metrics["formal_input_contract"].astype(str).str.contains("G_t").any()
        ),
    }


def write_outputs(outputs: Dict[str, pd.DataFrame], out_dir: Path, cfg: IntegratedDiagnosticConfig) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    name_map = {
        "gt_global": "integrated_diagnostic_gt_global_RC1.csv",
        "kt_global": "integrated_diagnostic_kt_global_RC1.csv",
        "formal_gtkt_packets": "integrated_diagnostic_formal_gtkt_packets_RC1.csv",
        "m_observation": "integrated_diagnostic_m_observation_RC1.csv",
        "pressure_candidates": "integrated_diagnostic_pressure_candidates_RC1.csv",
        "h11_local_pressure_field": "integrated_diagnostic_h11_local_pressure_field_RC1.csv",
        "pressure_intent_bundle": "integrated_diagnostic_pressure_intent_bundle_RC1.csv",
        "parameter_registry": "integrated_diagnostic_parameter_registry_RC1.csv",
        "parameter_updates": "integrated_diagnostic_parameter_updates_RC1.csv",
        "graph_objects_audit": "integrated_diagnostic_graph_objects_audit_RC1.csv",
        "action_surface_affordance": "integrated_diagnostic_action_surface_affordance_RC1.csv",
        "v8_affordance_support": "integrated_diagnostic_v8_affordance_support_RC1.csv",
        "final_gate_audit": "integrated_diagnostic_final_gate_audit_RC1.csv",
        "integrated_action_frame": "integrated_diagnostic_action_frame_RC1.csv",
        "integrated_sequence_events": "integrated_diagnostic_sequence_events_RC1.csv",
        "integrated_combined_outcomes": "integrated_diagnostic_combined_outcomes_RC1.csv",
        "integrated_isolated_semantic_outcomes": "integrated_diagnostic_isolated_semantic_outcomes_RC1.csv",
        "integrated_loop_metrics": "integrated_diagnostic_loop_metrics_RC1.csv",
    }
    for name, filename in name_map.items():
        outputs.get(name, pd.DataFrame()).to_csv(out_dir / filename, index=False)

    semantic_summary = summarize_semantic_alignment(outputs.get("integrated_isolated_semantic_outcomes", pd.DataFrame()))
    semantic_summary.to_csv(out_dir / "integrated_diagnostic_semantic_summary_RC1.csv", index=False)

    summary = build_summary(outputs, cfg)
    summary["outputs"] = {**name_map, "semantic_summary": "integrated_diagnostic_semantic_summary_RC1.csv"}
    (out_dir / "integrated_diagnostic_closed_loop_summary_RC1.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary
