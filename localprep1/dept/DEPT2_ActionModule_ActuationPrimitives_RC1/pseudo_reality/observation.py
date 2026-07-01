"""Observation builders: pseudo trace -> G_t / K_t_global.

Upper H-DEPT-compatible code consumes only these G/K tables.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List
import numpy as np
import pandas as pd

GT_FEATURES = [
    "gt_activity", "gt_volatility", "gt_uncertainty", "gt_relation_lock",
    "gt_coupling", "gt_exploration", "gt_reversibility", "gt_entropy",
    "gt_overconvergence", "gt_conflict", "gt_relation_curl", "gt_flow_curl",
]

BASE_FEATURES = [
    "activity", "volatility", "uncertainty", "relation_lock",
    "coupling", "exploration", "reversibility", "entropy",
]


class GtKtBuilder:
    """Build global G_t and K_t from emitted pseudo-reality traces."""

    def __init__(self, kt_window: int = 6):
        self.kt_window = kt_window
        self.history: List[pd.DataFrame] = []

    def build_gt(self, trace: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        e = trace["entity_trace"].copy()
        r = trace["relation_trace"].copy()
        seed = int(e["seed"].iloc[0])
        scenario = str(e["scenario"].iloc[0])
        t = int(e["t"].iloc[0])
        # Global distribution features from pseudo reality traces.
        gt = {
            "seed": seed,
            "scenario": scenario,
            "t": t,
            "generator": f"pseudo_{scenario}",
            "phase_bin": "runtime",
            "gt_activity": e["activity"].mean(),
            "gt_volatility": e["volatility"].mean(),
            "gt_uncertainty": e["uncertainty"].mean(),
            "gt_relation_lock": e["relation_lock"].mean(),
            "gt_coupling": e["coupling"].mean(),
            "gt_exploration": e["exploration"].mean(),
            "gt_reversibility": e["reversibility"].mean(),
            "gt_entropy": e["entropy"].mean(),
        }
        gt["gt_overconvergence"] = float(np.clip((gt["gt_relation_lock"] + gt["gt_coupling"] + (1 - gt["gt_exploration"])) / 3.0, 0, 1))
        gt["gt_conflict"] = float(np.clip((gt["gt_uncertainty"] + gt["gt_volatility"] + gt["gt_relation_lock"] - gt["gt_reversibility"]) / 3.0, 0, 1))
        if not r.empty:
            gt["gt_relation_curl"] = float(np.clip((r["relation_rigidity"].std(ddof=0) + r["relation_strength"].std(ddof=0)) / 2.0, 0, 1))
            gt["gt_flow_curl"] = float(np.clip(r["flow"].std(ddof=0), 0, 1))
        else:
            gt["gt_relation_curl"] = 0.0
            gt["gt_flow_curl"] = 0.0
        out = pd.DataFrame([gt])
        self.history.append(out)
        return out

    def build_kt_global(self) -> pd.DataFrame:
        if not self.history:
            raise RuntimeError("No G_t history available")
        hist = pd.concat(self.history, ignore_index=True)
        tail = hist.tail(self.kt_window)
        last = tail.iloc[-1]
        kt = {
            "seed": int(last["seed"]),
            "scenario": str(last["scenario"]),
            "t": int(last["t"]),
            "kt_n_observations": int(len(tail)),
        }
        for col in GT_FEATURES:
            values = tail[col].to_numpy(dtype=float)
            if len(values) >= 2:
                kt[col.replace("gt_", "kt_") + "_slope"] = float(values[-1] - values[0]) / max(len(values) - 1, 1)
            else:
                kt[col.replace("gt_", "kt_") + "_slope"] = 0.0
        return pd.DataFrame([kt])

    def build_formal_packet(self, gt: pd.DataFrame, kt: pd.DataFrame) -> pd.DataFrame:
        pkt = gt.merge(kt, on=["seed", "scenario", "t"], how="left")
        pkt["formal_hdept_input_contract"] = "G_t_and_K_t_global_only__codebase_RC1"
        pkt["truth_used_for_formal_hdept_input"] = False
        forbidden_prefixes = ("graph_object", "v8_", "final_gate", "action_surface")
        bad = [c for c in pkt.columns if c.startswith(forbidden_prefixes)]
        if bad:
            raise ValueError(f"Formal packet leaked lower internals: {bad}")
        return pkt


class GraphObjectBuilder:
    """Build lower-side graph objects from traces for targeting only.

    These outputs are lower-side artifacts. They must never be fed directly
    into H-DEPT formal observation.
    """

    def build(self, trace: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        e = trace["entity_trace"].copy()
        r = trace["relation_trace"].copy()
        rows = []
        for _, row in e.iterrows():
            risk = np.clip((row.uncertainty + row.volatility + row.relation_lock - row.reversibility) / 3.0, 0, 1)
            readiness = np.clip((row.reversibility + row.exploration + (1-row.volatility)) / 3.0, 0, 1)
            residual = np.clip((row.uncertainty + abs(row.exploration - 0.5) + row.relation_lock) / 3.0, 0, 1)
            rows.append({
                "graph_object_id": f"GO_{row.entity_id}",
                "entity_id": row.entity_id,
                "object_type": "entity_proxy",
                "t": int(row.t),
                "scenario": row.scenario,
                "seed": int(row.seed),
                "readiness": readiness,
                "risk": risk,
                "residual": residual,
                "activity": row.activity,
                "volatility": row.volatility,
                "uncertainty": row.uncertainty,
                "relation_lock": row.relation_lock,
                "coupling": row.coupling,
                "exploration": row.exploration,
                "reversibility": row.reversibility,
                "entropy": row.entropy,
                "contract_status": "active" if readiness > 0.42 else "provisional",
            })
        out = pd.DataFrame(rows)
        if not r.empty:
            deg = pd.concat([r["source"], r["target"]]).value_counts().rename("relation_degree")
            out["relation_degree"] = out["entity_id"].map(deg).fillna(0).astype(float)
        else:
            out["relation_degree"] = 0.0
        out["lower_artifact_contract"] = "graph_objects_are_lower_side_only__not_HDEPT_formal_input"
        return out
