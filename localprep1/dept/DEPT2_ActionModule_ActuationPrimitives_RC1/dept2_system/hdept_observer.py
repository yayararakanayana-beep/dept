"""H-DEPT-compatible observer and pressure proposal from formal G/K only."""
from __future__ import annotations

import numpy as np
import pandas as pd

H11_DIMS = [
    "Stability", "Adaptability", "Exploration", "Efficiency", "Robustness",
    "StructuralDiversity", "TrajectoryDynamics", "Predictability",
    "Coherence", "Recoverability", "NoveltyQuality",
]
PRESSURE_COMPONENTS = [
    "diagnostic_depth", "exploration_frequency", "sandbox_entry_rate",
    "adoption_threshold", "rollback_sensitivity", "deadzone_width",
    "cooldown_length", "hysteresis_strength", "update_frequency",
    "pressure_cap", "commitment_strength",
]


def clip01(x):
    return float(np.clip(x, 0.0, 1.0))


class HDEPTObserver:
    """Map formal G/K packet to H11 observation and upper pressure candidate.

    Contract: input must be G_t/K_t_global only. Any GraphObject/v8/final_gate
    leakage is rejected.
    """

    def validate_formal_input(self, packet: pd.DataFrame) -> None:
        forbidden = [c for c in packet.columns if c.startswith(("graph_object", "v8_", "final_gate", "action_surface"))]
        if forbidden:
            raise ValueError(f"H-DEPT formal input leaked lower internals: {forbidden}")
        required = ["gt_activity", "gt_volatility", "gt_uncertainty", "gt_relation_lock", "gt_exploration", "gt_reversibility", "kt_n_observations"]
        missing = [c for c in required if c not in packet.columns]
        if missing:
            raise ValueError(f"H-DEPT formal input missing required columns: {missing}")

    def observe_m(self, packet: pd.DataFrame) -> pd.DataFrame:
        self.validate_formal_input(packet)
        rows = []
        for _, r in packet.iterrows():
            g = r.to_dict()
            # Simple but explicit H11 projection from G/K.
            vals = {
                "Stability": clip01(1 - 0.58*g["gt_volatility"] - 0.35*g["gt_conflict"] + 0.18*g["gt_reversibility"]),
                "Adaptability": clip01(0.45*g["gt_exploration"] + 0.32*g["gt_reversibility"] + 0.23*(1-g["gt_relation_lock"])),
                "Exploration": clip01(0.78*g["gt_exploration"] + 0.22*g["gt_entropy"]),
                "Efficiency": clip01(1 - 0.42*g["gt_uncertainty"] - 0.30*g["gt_entropy"] + 0.18*g["gt_activity"]),
                "Robustness": clip01(1 - 0.46*g["gt_volatility"] - 0.34*g["gt_uncertainty"] + 0.26*g["gt_reversibility"]),
                "StructuralDiversity": clip01(0.52*g["gt_entropy"] + 0.25*g["gt_relation_curl"] + 0.23*(1-g["gt_coupling"])),
                "TrajectoryDynamics": clip01(0.50 + 2.4*abs(g.get("kt_activity_slope", 0.0)) + 1.8*abs(g.get("kt_relation_lock_slope", 0.0)) + 0.6*g["gt_flow_curl"]),
                "Predictability": clip01(1 - 0.45*g["gt_volatility"] - 0.36*g["gt_flow_curl"] - 0.20*g["gt_uncertainty"]),
                "Coherence": clip01(1 - 0.46*g["gt_relation_lock"] - 0.25*g["gt_conflict"] + 0.20*g["gt_coupling"]),
                "Recoverability": clip01(0.70*g["gt_reversibility"] + 0.30*(1-g["gt_conflict"])),
                "NoveltyQuality": clip01(0.55*g["gt_exploration"] + 0.25*g["gt_entropy"] + 0.20*(1-g["gt_uncertainty"])),
            }
            base = {k: r[k] for k in ["seed", "scenario", "t", "generator", "phase_bin"] if k in r.index}
            base["m_mean_overall"] = float(np.mean(list(vals.values())))
            base["m_min_overall"] = float(np.min(list(vals.values())))
            base["m_dispersion"] = float(np.std(list(vals.values())))
            base["m_observation_contract"] = "M_t_derived_from_G_t_K_t_global_only__codebase_RC1"
            base["truth_used_for_m_observation"] = False
            rows.append({**base, **vals})
        return pd.DataFrame(rows)

    def propose_pressure(self, m: pd.DataFrame, prev_pressure: pd.DataFrame | None = None) -> pd.DataFrame:
        rows = []
        prev_map = {}
        if prev_pressure is not None and not prev_pressure.empty:
            last = prev_pressure.sort_values("t").iloc[-1]
            prev_map = {c.replace("approved_", ""): float(last[c]) for c in prev_pressure.columns if c.startswith("approved_")}
        for _, r in m.iterrows():
            deficits = {d: 1.0 - float(r[d]) for d in H11_DIMS}
            needs = {
                "diagnostic_depth": 0.35*deficits["Predictability"] + 0.35*deficits["Coherence"] + 0.30*deficits["TrajectoryDynamics"],
                "exploration_frequency": 0.65*deficits["Exploration"] + 0.35*deficits["NoveltyQuality"],
                "sandbox_entry_rate": 0.45*deficits["Exploration"] + 0.35*deficits["StructuralDiversity"] + 0.20*deficits["Coherence"],
                "adoption_threshold": 0.52*deficits["Robustness"] + 0.30*deficits["Predictability"] - 0.18*deficits["Exploration"],
                "rollback_sensitivity": 0.55*deficits["Robustness"] + 0.30*deficits["Recoverability"] + 0.15*deficits["Stability"],
                "deadzone_width": 0.50*deficits["Efficiency"] + 0.30*deficits["Stability"] + 0.20*deficits["Coherence"],
                "cooldown_length": 0.60*deficits["Stability"] + 0.40*deficits["Robustness"],
                "hysteresis_strength": 0.55*deficits["Coherence"] + 0.45*deficits["Predictability"],
                "update_frequency": 0.55*deficits["Adaptability"] + 0.30*deficits["TrajectoryDynamics"] + 0.15*deficits["Exploration"],
                "pressure_cap": 0.52*deficits["Robustness"] + 0.28*deficits["Stability"] + 0.20*deficits["Coherence"],
                "commitment_strength": 0.45*deficits["Coherence"] + 0.35*deficits["Predictability"] + 0.20*deficits["Efficiency"],
            }
            out = {k: r[k] for k in ["seed", "scenario", "t", "generator", "phase_bin"] if k in r.index}
            for c in PRESSURE_COMPONENTS:
                raw = float(np.clip(needs[c] - 0.55, -0.30, 0.30))
                # Weak, slow update around previous pressure.
                prev = prev_map.get(c, 0.0)
                approved = float(np.clip(0.75*prev + 0.25*raw, -0.08, 0.08))
                out[f"need_{c}"] = float(needs[c])
                out[f"approved_{c}"] = approved
            out["approved_component_l1"] = float(sum(abs(out[f"approved_{c}"]) for c in PRESSURE_COMPONENTS))
            out["pressure_candidate_contract"] = "derived_from_M_only__M_derived_from_GK_only__codebase_RC1"
            out["truth_used_for_pressure_candidate"] = False
            rows.append(out)
        return pd.DataFrame(rows)
