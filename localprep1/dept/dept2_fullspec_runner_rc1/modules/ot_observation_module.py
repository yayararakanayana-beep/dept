"""ot_observation_module: explicit lower local observation surface O_t.

Task4 strengthens O_t from a thin graph-object wrapper into a lower-local
observation surface with four explicit products:

  1. O_t_native: local observation units with source/provenance contracts.
  2. O_t_action_view: action-planning view; never an ActionModule input.
  3. O_t_exploration_view: exploration-facing view; no unverified action path.
  4. residual_noise_log: retained ledger of residual, ambiguity, unresolved,
     mismatch, and low-signal noise. Nothing is silently discarded.

O_t is not a G/K generator, not an upper formal input, and not a direct
ActionModule input.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict
import numpy as np
import pandas as pd

from DEPT2_ActionModule_ActuationPrimitives_RC1.pseudo_reality.observation import GraphObjectBuilder
from dept2_fullspec_runner_rc1.modules.world_adapter import trace_fingerprint


OT_CONTRACT = "O_t_lower_local_observation_surface__not_GK_generator__not_upper_formal_input__Task4_RC1"
NOISE_LEDGER_CONTRACT = "residual_unresolved_ambiguity_and_unclassified_noise_retained__Task4_RC1"


@dataclass
class _NoiseMemory:
    first_seen_t: int
    last_seen_t: int
    observation_count: int = 0
    active_count: int = 0
    consecutive_active_count: int = 0
    max_noise_score: float = 0.0
    previous_noise_score: float = 0.0
    previous_residual_score: float = 0.0
    previous_status: str = "new"


def _clip(value) -> pd.Series | float:
    return np.clip(value, 0.0, 1.0)


def _scalar(df: pd.DataFrame, col: str, default: float = 0.0) -> float:
    if df is None or df.empty or col not in df.columns:
        return float(default)
    return float(df[col].iloc[0])


class OtObservationModule:
    name = "ot_observation_module"

    def __init__(self):
        self.graph_builder = GraphObjectBuilder()
        self._noise_memory: dict[str, _NoiseMemory] = {}

    def build(self, trace: Dict[str, pd.DataFrame], gt: pd.DataFrame, kt: pd.DataFrame) -> dict[str, pd.DataFrame]:
        graph_objects = self.graph_builder.build(trace)
        if graph_objects.empty:
            empty_audit = self._empty_audit(trace, gt, kt)
            return {
                "graph_objects": pd.DataFrame(),
                "ot_native": pd.DataFrame(),
                "ot_action_view": pd.DataFrame(),
                "ot_exploration_view": pd.DataFrame(),
                "ot_observation_audit": empty_audit,
                "residual_noise_log": pd.DataFrame(),
                "residual_noise_ledger_audit": self._empty_noise_audit(trace),
            }

        trace_fp = trace_fingerprint(trace)
        world_t = int(trace["entity_trace"]["t"].iloc[0]) if "entity_trace" in trace and not trace["entity_trace"].empty else -1
        gt_fp = str(gt.get("gk_source_trace_fingerprint", pd.Series([trace_fp])).iloc[0]) if gt is not None and not gt.empty else trace_fp
        gt_uncertainty = _scalar(gt, "gt_uncertainty")
        gt_relation_lock = _scalar(gt, "gt_relation_lock")
        gt_exploration = _scalar(gt, "gt_exploration")
        kt_uncertainty_slope = _scalar(kt, "kt_uncertainty_slope")
        kt_exploration_slope = _scalar(kt, "kt_exploration_slope")

        ot_native = graph_objects.copy()
        ot_native["ot_id"] = ot_native["graph_object_id"].astype(str).map(lambda x: f"OT_{x}")
        ot_native["ot_identity_key"] = ot_native["entity_id"].astype(str)
        ot_native["ot_source_trace_fingerprint"] = trace_fp
        ot_native["ot_source_gk_trace_fingerprint"] = gt_fp
        ot_native["ot_source_world_t"] = world_t

        residual = ot_native["residual"].astype(float)
        uncertainty = ot_native["uncertainty"].astype(float)
        volatility = ot_native["volatility"].astype(float)
        readiness = ot_native["readiness"].astype(float)
        risk = ot_native["risk"].astype(float)
        relation_lock = ot_native["relation_lock"].astype(float)
        exploration = ot_native["exploration"].astype(float)
        coupling = ot_native["coupling"].astype(float)
        reversibility = ot_native["reversibility"].astype(float)

        ot_native["ot_residual_score"] = _clip(residual)
        ot_native["ot_noise_score"] = _clip((residual + uncertainty + volatility) / 3.0)
        ot_native["ot_unresolved_score"] = _clip((residual + (1.0 - readiness)) / 2.0)
        ot_native["ot_ambiguity_score"] = _clip((ot_native["ot_noise_score"] + ot_native["ot_unresolved_score"] + np.abs(exploration - 0.5)) / 3.0)
        ot_native["ot_boundary_instability_score"] = _clip((relation_lock + coupling + volatility) / 3.0)
        ot_native["ot_macro_micro_mismatch_score"] = _clip((np.abs(uncertainty - gt_uncertainty) + np.abs(relation_lock - gt_relation_lock) + np.abs(exploration - gt_exploration)) / 3.0)
        ot_native["ot_action_relevance_score"] = _clip((risk + ot_native["ot_unresolved_score"] + (1.0 - reversibility)) / 3.0)
        ot_native["ot_exploration_gap_score"] = _clip((ot_native["ot_residual_score"] + (1.0 - exploration) + ot_native["ot_ambiguity_score"] + ot_native["ot_macro_micro_mismatch_score"]) / 4.0)
        ot_native["ot_local_observation_need_score"] = _clip((ot_native["ot_unresolved_score"] + ot_native["ot_ambiguity_score"] + ot_native["ot_macro_micro_mismatch_score"]) / 3.0)
        ot_native["ot_temporal_uncertainty_pressure"] = _clip(abs(kt_uncertainty_slope) + ot_native["ot_noise_score"])
        ot_native["ot_temporal_exploration_pressure"] = _clip(abs(kt_exploration_slope) + ot_native["ot_exploration_gap_score"])

        ot_native["ot_explanation_status"] = np.select(
            [
                ot_native["ot_unresolved_score"] >= 0.55,
                ot_native["ot_ambiguity_score"] >= 0.45,
                ot_native["ot_residual_score"] >= 0.45,
                ot_native["ot_noise_score"] >= 0.35,
            ],
            ["unresolved", "ambiguous", "residual_high", "retained_noise"],
            default="explained_low_residual",
        )
        ot_native["ot_contract"] = OT_CONTRACT
        ot_native["truth_used_for_ot"] = False
        ot_native["ot_gk_generation_performed"] = False
        ot_native["ot_upper_formal_input_performed"] = False
        ot_native["ot_action_module_direct_input"] = False
        ot_native["ot_writeback_performed"] = False

        ot_action_view = self._build_action_view(ot_native)
        ot_exploration_view = self._build_exploration_view(ot_native)
        residual_noise_log = self._build_residual_noise_log(ot_native, world_t)
        ot_observation_audit = self._build_observation_audit(trace, gt, kt, ot_native, ot_action_view, ot_exploration_view, residual_noise_log)
        residual_noise_ledger_audit = self._build_noise_ledger_audit(trace, residual_noise_log)

        return {
            "graph_objects": graph_objects,
            "ot_native": ot_native,
            "ot_action_view": ot_action_view,
            "ot_exploration_view": ot_exploration_view,
            "ot_observation_audit": ot_observation_audit,
            "residual_noise_log": residual_noise_log,
            "residual_noise_ledger_audit": residual_noise_ledger_audit,
        }

    def _build_action_view(self, ot_native: pd.DataFrame) -> pd.DataFrame:
        action_cols = [
            "seed", "scenario", "t", "ot_id", "ot_identity_key", "graph_object_id", "entity_id",
            "readiness", "risk", "residual", "ot_residual_score", "ot_unresolved_score",
            "ot_ambiguity_score", "ot_macro_micro_mismatch_score", "ot_action_relevance_score",
            "ot_local_observation_need_score", "activity", "volatility", "uncertainty", "relation_lock",
            "coupling", "exploration", "reversibility", "entropy", "relation_degree",
        ]
        out = ot_native[[c for c in action_cols if c in ot_native.columns]].copy()
        out["ot_view_role"] = "action_view"
        out["requires_action_local_audit"] = out["ot_local_observation_need_score"].astype(float) >= 0.35
        out["suggested_action_attention"] = np.select(
            [out["ot_action_relevance_score"] >= 0.55, out["ot_local_observation_need_score"] >= 0.40],
            ["high_action_relevance", "local_audit_recommended"],
            default="normal_action_surface_context",
        )
        out["ot_action_view_contract"] = "O_t_action_view_for_action_surface_planning__not_ActionModule_input__Task4_RC1"
        return out

    def _build_exploration_view(self, ot_native: pd.DataFrame) -> pd.DataFrame:
        base = self._build_action_view(ot_native)
        out = base.copy()
        out["ot_view_role"] = "exploration_view"
        out["exploration_gap_proxy"] = ot_native["ot_exploration_gap_score"].to_numpy()
        out["residual_gap_score"] = ot_native["ot_residual_score"].to_numpy()
        out["novelty_pressure_proxy"] = _clip((ot_native["ot_exploration_gap_score"] + ot_native["ot_macro_micro_mismatch_score"] + (1.0 - ot_native["exploration"].astype(float))) / 3.0)
        out["unresolved_cluster_key"] = np.where(
            ot_native["ot_unresolved_score"].astype(float) >= 0.45,
            "cluster_unresolved_high",
            "cluster_unresolved_low",
        )
        out["exploration_attention"] = np.select(
            [out["novelty_pressure_proxy"] >= 0.55, out["exploration_gap_proxy"] >= 0.42],
            ["candidate_axis_seed", "monitor_for_axis_seed"],
            default="retain_context_only",
        )
        out["ot_exploration_view_contract"] = "O_t_exploration_view_for_candidate_generation__unverified_axes_do_not_pass__Task4_RC1"
        return out

    def _build_residual_noise_log(self, ot_native: pd.DataFrame, world_t: int) -> pd.DataFrame:
        rows = []
        for _, r in ot_native.iterrows():
            key = str(r["ot_identity_key"])
            noise_score = float(r["ot_noise_score"])
            residual_score = float(r["ot_residual_score"])
            unresolved_score = float(r["ot_unresolved_score"])
            ambiguity_score = float(r["ot_ambiguity_score"])
            mismatch_score = float(r["ot_macro_micro_mismatch_score"])
            boundary_score = float(r["ot_boundary_instability_score"])
            active = noise_score >= 0.45 or unresolved_score >= 0.45 or ambiguity_score >= 0.45 or mismatch_score >= 0.45
            memory = self._noise_memory.get(key)
            if memory is None:
                memory = _NoiseMemory(first_seen_t=world_t, last_seen_t=world_t)
            previous_noise = memory.previous_noise_score
            previous_residual = memory.previous_residual_score
            memory.observation_count += 1
            memory.last_seen_t = world_t
            memory.max_noise_score = max(memory.max_noise_score, noise_score)
            if active:
                memory.active_count += 1
                memory.consecutive_active_count += 1
            else:
                memory.consecutive_active_count = 0
            noise_delta = noise_score - previous_noise
            residual_delta = residual_score - previous_residual

            noise_kind = self._classify_noise_kind(residual_score, noise_score, unresolved_score, ambiguity_score, mismatch_score, boundary_score)
            noise_status = self._classify_noise_status(noise_score, unresolved_score, ambiguity_score, mismatch_score, memory.consecutive_active_count)
            memory.previous_noise_score = noise_score
            memory.previous_residual_score = residual_score
            memory.previous_status = noise_status
            self._noise_memory[key] = memory

            rows.append({
                "seed": r.get("seed"),
                "scenario": r.get("scenario"),
                "t": r.get("t"),
                "noise_event_id": f"NL_t{world_t}_{r['ot_id']}",
                "ot_id": r["ot_id"],
                "graph_object_id": r["graph_object_id"],
                "entity_id": r["entity_id"],
                "ot_identity_key": key,
                "ot_source_trace_fingerprint": r["ot_source_trace_fingerprint"],
                "ot_residual_score": residual_score,
                "ot_noise_score": noise_score,
                "ot_unresolved_score": unresolved_score,
                "ot_ambiguity_score": ambiguity_score,
                "ot_macro_micro_mismatch_score": mismatch_score,
                "ot_boundary_instability_score": boundary_score,
                "residual_noise_present": bool(residual_score >= 0.35),
                "uncertainty_noise_present": bool(float(r.get("uncertainty", 0.0)) >= 0.45),
                "ambiguity_noise_present": bool(ambiguity_score >= 0.35),
                "unresolved_noise_present": bool(unresolved_score >= 0.35),
                "boundary_instability_present": bool(boundary_score >= 0.45),
                "macro_micro_mismatch_present": bool(mismatch_score >= 0.35),
                "noise_kind": noise_kind,
                "noise_status": noise_status,
                "noise_retention_policy": "retain_all_even_low_or_unclassified",
                "noise_retained": True,
                "first_seen_t": int(memory.first_seen_t),
                "last_seen_t": int(memory.last_seen_t),
                "observation_count": int(memory.observation_count),
                "active_count": int(memory.active_count),
                "consecutive_active_count": int(memory.consecutive_active_count),
                "persistent_noise": bool(memory.consecutive_active_count >= 2),
                "max_noise_score_seen": float(memory.max_noise_score),
                "previous_noise_score": float(previous_noise),
                "noise_delta": float(noise_delta),
                "previous_residual_score": float(previous_residual),
                "residual_delta": float(residual_delta),
                "noise_retention_contract": NOISE_LEDGER_CONTRACT,
                "used_as_upper_formal_input": False,
                "written_back_to_gk": False,
                "written_back_to_world": False,
            })
        return pd.DataFrame(rows)

    @staticmethod
    def _classify_noise_kind(residual: float, noise: float, unresolved: float, ambiguity: float, mismatch: float, boundary: float) -> str:
        scored = {
            "unresolved_noise": unresolved,
            "ambiguity_noise": ambiguity,
            "macro_micro_mismatch": mismatch,
            "boundary_instability": boundary,
            "residual_noise": residual,
            "low_unclassified_noise": noise,
        }
        return max(scored, key=scored.get)

    @staticmethod
    def _classify_noise_status(noise: float, unresolved: float, ambiguity: float, mismatch: float, consecutive: int) -> str:
        if consecutive >= 2:
            return "persistent_unresolved_noise"
        if max(noise, unresolved, ambiguity, mismatch) >= 0.55:
            return "active_unresolved_noise"
        if max(noise, unresolved, ambiguity, mismatch) >= 0.35:
            return "retained_monitored_noise"
        return "retained_low_noise"

    def _build_observation_audit(
        self,
        trace: Dict[str, pd.DataFrame],
        gt: pd.DataFrame,
        kt: pd.DataFrame,
        ot_native: pd.DataFrame,
        ot_action_view: pd.DataFrame,
        ot_exploration_view: pd.DataFrame,
        residual_noise_log: pd.DataFrame,
    ) -> pd.DataFrame:
        row = {
            "ot_audit_contract": "O_t_observation_audit__lower_local_surface_only__Task4_RC1",
            "source_trace_fingerprint": trace_fingerprint(trace),
            "source_world_t": int(trace["entity_trace"]["t"].iloc[0]) if "entity_trace" in trace and not trace["entity_trace"].empty else -1,
            "source_gt_rows": int(len(gt)) if gt is not None else 0,
            "source_kt_rows": int(len(kt)) if kt is not None else 0,
            "ot_native_rows": int(len(ot_native)),
            "ot_action_view_rows": int(len(ot_action_view)),
            "ot_exploration_view_rows": int(len(ot_exploration_view)),
            "residual_noise_log_rows": int(len(residual_noise_log)),
            "all_noise_retained": bool(len(residual_noise_log) >= len(ot_native)),
            "ot_is_gk_generator": False,
            "ot_used_as_upper_formal_input": False,
            "ot_is_action_module_direct_input": False,
            "ot_writeback_performed": False,
            "native_contract_present": bool("ot_contract" in ot_native.columns and ot_native["ot_contract"].eq(OT_CONTRACT).all()),
            "action_view_contract_present": bool("ot_action_view_contract" in ot_action_view.columns),
            "exploration_view_contract_present": bool("ot_exploration_view_contract" in ot_exploration_view.columns),
            "active_noise_rows": int(residual_noise_log["noise_status"].isin(["active_unresolved_noise", "persistent_unresolved_noise"]).sum()) if not residual_noise_log.empty else 0,
            "retained_noise_rows": int(residual_noise_log["noise_retained"].astype(bool).sum()) if not residual_noise_log.empty and "noise_retained" in residual_noise_log.columns else 0,
            "max_observation_need": float(ot_native["ot_local_observation_need_score"].max()) if not ot_native.empty else 0.0,
            "max_exploration_gap": float(ot_native["ot_exploration_gap_score"].max()) if not ot_native.empty else 0.0,
        }
        return pd.DataFrame([row])

    def _build_noise_ledger_audit(self, trace: Dict[str, pd.DataFrame], residual_noise_log: pd.DataFrame) -> pd.DataFrame:
        if residual_noise_log is None or residual_noise_log.empty:
            return self._empty_noise_audit(trace)
        statuses = residual_noise_log["noise_status"].value_counts().to_dict()
        row = {
            "noise_ledger_audit_contract": "residual_noise_ledger_audit__retain_all_noise_rows__Task4_RC1",
            "source_trace_fingerprint": trace_fingerprint(trace),
            "source_world_t": int(trace["entity_trace"]["t"].iloc[0]) if "entity_trace" in trace and not trace["entity_trace"].empty else -1,
            "noise_log_rows": int(len(residual_noise_log)),
            "noise_retained_rows": int(residual_noise_log["noise_retained"].astype(bool).sum()),
            "all_noise_retained": bool(residual_noise_log["noise_retained"].astype(bool).all()),
            "active_unresolved_noise_rows": int(statuses.get("active_unresolved_noise", 0)),
            "persistent_unresolved_noise_rows": int(statuses.get("persistent_unresolved_noise", 0)),
            "retained_monitored_noise_rows": int(statuses.get("retained_monitored_noise", 0)),
            "retained_low_noise_rows": int(statuses.get("retained_low_noise", 0)),
            "persistent_noise_rows": int(residual_noise_log["persistent_noise"].astype(bool).sum()),
            "max_noise_score": float(residual_noise_log["ot_noise_score"].max()),
            "max_unresolved_score": float(residual_noise_log["ot_unresolved_score"].max()),
            "max_ambiguity_score": float(residual_noise_log["ot_ambiguity_score"].max()),
            "max_macro_micro_mismatch_score": float(residual_noise_log["ot_macro_micro_mismatch_score"].max()),
            "unclassified_noise_discarded": False,
            "ledger_available_for_exploration": True,
        }
        return pd.DataFrame([row])

    @staticmethod
    def _empty_audit(trace: Dict[str, pd.DataFrame], gt: pd.DataFrame, kt: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame([{
            "ot_audit_contract": "O_t_observation_audit__empty_source__Task4_RC1",
            "source_trace_fingerprint": trace_fingerprint(trace) if trace else "missing",
            "source_gt_rows": int(len(gt)) if gt is not None else 0,
            "source_kt_rows": int(len(kt)) if kt is not None else 0,
            "ot_native_rows": 0,
            "ot_action_view_rows": 0,
            "ot_exploration_view_rows": 0,
            "residual_noise_log_rows": 0,
            "all_noise_retained": True,
            "ot_is_gk_generator": False,
            "ot_used_as_upper_formal_input": False,
            "ot_is_action_module_direct_input": False,
            "ot_writeback_performed": False,
        }])

    @staticmethod
    def _empty_noise_audit(trace: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        return pd.DataFrame([{
            "noise_ledger_audit_contract": "residual_noise_ledger_audit__empty_source__Task4_RC1",
            "source_trace_fingerprint": trace_fingerprint(trace) if trace else "missing",
            "noise_log_rows": 0,
            "noise_retained_rows": 0,
            "all_noise_retained": True,
            "unclassified_noise_discarded": False,
            "ledger_available_for_exploration": True,
        }])
