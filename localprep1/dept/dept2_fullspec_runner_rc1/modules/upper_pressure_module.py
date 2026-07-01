"""upper_pressure_module: formal G/K -> M_t -> weak pressure, with Task5 audit.

Task5 strengthens the H-DEPT upper-pressure boundary:
  - The only formal input is the G/K formal packet.
  - O_t, v8, exploration, action-surface, gate, and ActionFrame data are rejected.
  - M_t is derived from G/K only.
  - weak pressure is derived from M_t only.
  - A per-cycle upper-pressure audit row records provenance, contracts, and leakage checks.
"""
from __future__ import annotations

import hashlib
import json
from typing import Iterable

import pandas as pd

from DEPT2_ActionModule_ActuationPrimitives_RC1.dept2_system.hdept_observer import HDEPTObserver

FORBIDDEN_UPPER_PREFIXES = (
    "ot_",
    "v8_",
    "exploration_",
    "graph_object",
    "action_surface",
    "action_",
    "final_gate",
    "coactivation_",
)
REQUIRED_FORMAL_COLUMNS = {
    "gt_activity",
    "gt_volatility",
    "gt_uncertainty",
    "gt_relation_lock",
    "gt_exploration",
    "gt_reversibility",
    "kt_n_observations",
}


def _stable_table_fingerprint(df: pd.DataFrame) -> str:
    """Return a stable lightweight fingerprint for audit/provenance."""
    if df is None:
        return "none"
    view = df.copy()
    # Sort columns only; preserve rows because time/order are meaningful.
    view = view.reindex(sorted(view.columns), axis=1)
    payload = view.to_json(orient="split", date_format="iso", double_precision=12)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def _prefix_leaks(columns: Iterable[str]) -> list[str]:
    return [c for c in columns if str(c).startswith(FORBIDDEN_UPPER_PREFIXES)]


class UpperPressureModule:
    name = "upper_pressure_module"

    def __init__(self):
        self.observer = HDEPTObserver()
        self.prev_pressure: pd.DataFrame | None = None
        self.contract = "upper_pressure_from_formal_GK_only__no_Ot_no_v8_no_exploration__Task5_RC1"

    def compute(self, formal_packet: pd.DataFrame, *, loop_step: int | None = None) -> dict[str, pd.DataFrame]:
        """Compute M_t and weak pressure from formal G/K only.

        The method intentionally accepts only the formal packet. Downstream local
        objects are not present in the signature, which makes accidental coupling
        harder and keeps the H-DEPT formal input clean.
        """
        self._validate_formal_only(formal_packet)
        fp_before = _stable_table_fingerprint(formal_packet)

        m_observation = self.observer.observe_m(formal_packet)
        m_observation = self._annotate_m(m_observation, fp_before)

        weak_pressure = self.observer.propose_pressure(m_observation, prev_pressure=self.prev_pressure)
        weak_pressure = self._annotate_pressure(weak_pressure, _stable_table_fingerprint(m_observation), fp_before)
        self.prev_pressure = weak_pressure.copy()

        audit = self.build_audit(formal_packet, m_observation, weak_pressure, fp_before, loop_step)
        return {"m_observation": m_observation, "weak_pressure": weak_pressure, "upper_pressure_audit": audit}

    def _annotate_m(self, m_observation: pd.DataFrame, formal_fp: str) -> pd.DataFrame:
        out = m_observation.copy()
        out["upper_pressure_module"] = self.name
        out["m_source_contract"] = "M_t_derived_from_formal_GK_only__Task5_RC1"
        out["formal_packet_fingerprint"] = formal_fp
        out["m_uses_ot"] = False
        out["m_uses_v8"] = False
        out["m_uses_exploration"] = False
        out["m_uses_action_surface"] = False
        out["m_uses_action_result"] = False
        out["m_writeback_performed"] = False
        return out

    def _annotate_pressure(self, weak_pressure: pd.DataFrame, m_fp: str, formal_fp: str) -> pd.DataFrame:
        out = weak_pressure.copy()
        out["upper_pressure_module"] = self.name
        out["weak_pressure_contract"] = "weak_pressure_derived_from_M_only__M_from_formal_GK_only__Task5_RC1"
        out["m_observation_fingerprint"] = m_fp
        out["formal_packet_fingerprint"] = formal_fp
        out["pressure_uses_ot"] = False
        out["pressure_uses_v8"] = False
        out["pressure_uses_exploration"] = False
        out["pressure_uses_action_surface"] = False
        out["pressure_uses_action_result"] = False
        out["pressure_writeback_performed"] = False
        return out

    def build_audit(
        self,
        formal_packet: pd.DataFrame,
        m_observation: pd.DataFrame,
        weak_pressure: pd.DataFrame,
        formal_fp: str,
        loop_step: int | None,
    ) -> pd.DataFrame:
        leaked = _prefix_leaks(formal_packet.columns if formal_packet is not None else [])
        missing = sorted(REQUIRED_FORMAL_COLUMNS - set(formal_packet.columns if formal_packet is not None else []))
        formal_contract = ""
        source_trace_fp = ""
        source_world_t = -1
        if formal_packet is not None and not formal_packet.empty:
            formal_contract = str(formal_packet.get("formal_input_source_contract", pd.Series([""])).iloc[0])
            source_trace_fp = str(formal_packet.get("gk_source_trace_fingerprint", pd.Series([""])).iloc[0])
            source_world_t = int(formal_packet.get("gk_source_world_t", pd.Series([-1])).iloc[0])
        m_leaks = _prefix_leaks(m_observation.columns if m_observation is not None else [])
        p_leaks = _prefix_leaks(weak_pressure.columns if weak_pressure is not None else [])
        pressure_l1 = 0.0
        pressure_cols = []
        if weak_pressure is not None and not weak_pressure.empty:
            pressure_cols = [c for c in weak_pressure.columns if c.startswith("approved_") and c != "approved_component_l1"]
            if "approved_component_l1" in weak_pressure.columns:
                pressure_l1 = float(weak_pressure["approved_component_l1"].sum())
            else:
                pressure_l1 = float(weak_pressure[pressure_cols].abs().sum(axis=1).sum()) if pressure_cols else 0.0
        row = {
            "loop_step": -1 if loop_step is None else int(loop_step),
            "upper_pressure_contract": self.contract,
            "formal_input_contract_seen": formal_contract,
            "formal_packet_fingerprint": formal_fp,
            "formal_source_trace_fingerprint": source_trace_fp,
            "formal_source_world_t": source_world_t,
            "formal_rows": int(len(formal_packet)) if formal_packet is not None else 0,
            "formal_columns_count": int(len(formal_packet.columns)) if formal_packet is not None else 0,
            "formal_required_columns_missing_count": int(len(missing)),
            "formal_required_columns_missing": "|".join(missing),
            "formal_lower_leak_count": int(len(leaked)),
            "formal_lower_leak_columns": "|".join(leaked),
            "formal_input_is_gk_only": bool(not leaked and not missing),
            "m_rows": int(len(m_observation)) if m_observation is not None else 0,
            "pressure_rows": int(len(weak_pressure)) if weak_pressure is not None else 0,
            "m_lower_leak_count": int(len(m_leaks)),
            "pressure_lower_leak_count": int(len(p_leaks)),
            "approved_pressure_component_count": int(len(pressure_cols)),
            "approved_pressure_l1_sum": pressure_l1,
            "upper_uses_ot": False,
            "upper_uses_v8": False,
            "upper_uses_exploration": False,
            "upper_uses_action_surface": False,
            "upper_uses_action_result": False,
            "truth_used_for_m_observation": bool(m_observation.get("truth_used_for_m_observation", pd.Series([False])).astype(bool).any()) if m_observation is not None and not m_observation.empty else False,
            "truth_used_for_pressure_candidate": bool(weak_pressure.get("truth_used_for_pressure_candidate", pd.Series([False])).astype(bool).any()) if weak_pressure is not None and not weak_pressure.empty else False,
            "upper_writeback_performed": False,
            "audit_status": "pass" if (not leaked and not missing and not m_leaks and not p_leaks) else "fail",
        }
        row["audit_payload_json"] = json.dumps(
            {
                "formal_missing": missing,
                "formal_lower_leaks": leaked,
                "m_lower_leaks": m_leaks,
                "pressure_lower_leaks": p_leaks,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return pd.DataFrame([row])

    @staticmethod
    def _validate_formal_only(formal_packet: pd.DataFrame) -> None:
        if formal_packet is None or formal_packet.empty:
            raise ValueError("upper_pressure_module requires non-empty formal G/K packet")
        leaked = _prefix_leaks(formal_packet.columns)
        if leaked:
            raise ValueError(f"upper_pressure_module formal input leaked non-G/K columns: {leaked}")
        missing = sorted(REQUIRED_FORMAL_COLUMNS - set(formal_packet.columns))
        if missing:
            raise ValueError(f"upper_pressure_module formal input missing required G/K columns: {missing}")
