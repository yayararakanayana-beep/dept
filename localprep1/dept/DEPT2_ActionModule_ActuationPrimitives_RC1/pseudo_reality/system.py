"""
PseudoReality system for DEPT2 closed-loop validation.

This module is intentionally independent from the DEPT2/H-DEPT system code.
The action module may modify this pseudo-world, but the upper layer must only
observe G_t / K_t_global reconstructed from emitted traces.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional
import numpy as np
import pandas as pd

STATE_FEATURES = [
    "activity",
    "volatility",
    "uncertainty",
    "relation_lock",
    "coupling",
    "exploration",
    "reversibility",
    "entropy",
]

ACTION_CHANNELS = [
    "exploration_injection",
    "coupling_relief",
    "volatility_damping",
    "uncertainty_probe",
    "relation_unlock",
    "buffer_increase",
    "no_op",
]


@dataclass(frozen=True)
class PseudoRealityConfig:
    n_entities: int = 18
    seed: int = 42
    scenario: str = "normal"
    noise_scale: float = 0.018
    drift_scale: float = 0.006
    action_coupling: float = 0.045
    relation_decay: float = 0.015
    shock_time: int = 18
    shock_strength: float = 0.18


class PseudoRealitySystem:
    """A small synthetic dynamic system with entity states and relation matrix."""

    def __init__(self, config: PseudoRealityConfig):
        self.config = config
        self.rng = np.random.default_rng(config.seed)
        self.t = 0
        self.entities = self._init_entities()
        self.relations = self._init_relations()

    def _init_entities(self) -> pd.DataFrame:
        n = self.config.n_entities
        base = pd.DataFrame({"entity_id": [f"E{i:03d}" for i in range(n)]})
        # Scenario-conditioned initial states.
        if self.config.scenario == "exploration_loss":
            means = dict(activity=0.55, volatility=0.22, uncertainty=0.45, relation_lock=0.70,
                         coupling=0.75, exploration=0.24, reversibility=0.38, entropy=0.42)
        elif self.config.scenario == "relation_lock":
            means = dict(activity=0.50, volatility=0.25, uncertainty=0.48, relation_lock=0.82,
                         coupling=0.80, exploration=0.34, reversibility=0.34, entropy=0.40)
        elif self.config.scenario == "shock":
            means = dict(activity=0.52, volatility=0.35, uncertainty=0.56, relation_lock=0.55,
                         coupling=0.62, exploration=0.42, reversibility=0.44, entropy=0.51)
        else:
            means = dict(activity=0.52, volatility=0.24, uncertainty=0.42, relation_lock=0.50,
                         coupling=0.58, exploration=0.46, reversibility=0.55, entropy=0.50)
        for k in STATE_FEATURES:
            base[k] = np.clip(self.rng.normal(means[k], 0.06, size=n), 0.02, 0.98)
        return base

    def _init_relations(self) -> pd.DataFrame:
        ids = self.entities.entity_id.tolist()
        rows = []
        for i, src in enumerate(ids):
            for j, dst in enumerate(ids):
                if i == j:
                    continue
                # Sparse-ish relation field, but never empty.
                if self.rng.random() < 0.22:
                    strength = np.clip(self.rng.normal(0.42, 0.16), 0.02, 0.95)
                    rigidity = np.clip(self.rng.normal(0.45, 0.16), 0.02, 0.95)
                    flow = np.clip(self.rng.normal(0.50, 0.18), 0.02, 0.95)
                    rows.append((src, dst, strength, rigidity, flow))
        if not rows:
            rows.append((ids[0], ids[1], 0.4, 0.4, 0.5))
        return pd.DataFrame(rows, columns=["source", "target", "relation_strength", "relation_rigidity", "flow"])

    def _scenario_drift(self) -> Dict[str, float]:
        s = self.config.scenario
        if s == "exploration_loss":
            return {"exploration": -0.012, "relation_lock": 0.010, "coupling": 0.006, "entropy": -0.005}
        if s == "relation_lock":
            return {"relation_lock": 0.014, "coupling": 0.008, "reversibility": -0.010, "exploration": -0.004}
        if s == "shock":
            return {"volatility": 0.004, "uncertainty": 0.003, "reversibility": -0.003}
        return {"entropy": 0.001, "exploration": 0.001}

    def emit_trace(self) -> Dict[str, pd.DataFrame]:
        e = self.entities.copy()
        e["t"] = self.t
        e["scenario"] = self.config.scenario
        e["seed"] = self.config.seed
        r = self.relations.copy()
        r["t"] = self.t
        r["scenario"] = self.config.scenario
        r["seed"] = self.config.seed
        return {"entity_trace": e, "relation_trace": r}

    def step(self, action_frame: Optional[pd.DataFrame] = None) -> Dict[str, pd.DataFrame]:
        """Advance the pseudo reality by one step.

        action_frame schema:
            entity_id, action_channel, action_strength, direction
        direction is +1 for increase / -1 for decrease when meaningful.
        """
        self.t += 1
        e = self.entities.copy()
        cfg = self.config

        # Natural drift and noise.
        drift = self._scenario_drift()
        for feat in STATE_FEATURES:
            natural = drift.get(feat, 0.0)
            e[feat] = e[feat] + natural + self.rng.normal(0, cfg.noise_scale, size=len(e))

        # Scenario shock.
        if cfg.scenario == "shock" and self.t == cfg.shock_time:
            e["volatility"] += cfg.shock_strength
            e["uncertainty"] += cfg.shock_strength * 0.75
            e["reversibility"] -= cfg.shock_strength * 0.45
            e["entropy"] += cfg.shock_strength * 0.30

        # Apply action module output to pseudo reality, not to G_t directly.
        if action_frame is not None and not action_frame.empty:
            af = action_frame.copy()
            af = af[af["action_channel"] != "no_op"]
            for _, row in af.iterrows():
                idx = e["entity_id"] == row["entity_id"]
                if not idx.any():
                    continue
                strength = float(np.clip(row.get("action_strength", 0.0), 0.0, 1.0)) * cfg.action_coupling
                ch = row["action_channel"]
                if ch == "exploration_injection":
                    e.loc[idx, "exploration"] += strength
                    e.loc[idx, "entropy"] += strength * 0.40
                    e.loc[idx, "uncertainty"] += strength * 0.15
                elif ch == "coupling_relief":
                    e.loc[idx, "coupling"] -= strength
                    e.loc[idx, "relation_lock"] -= strength * 0.45
                elif ch == "volatility_damping":
                    e.loc[idx, "volatility"] -= strength
                    e.loc[idx, "reversibility"] += strength * 0.35
                elif ch == "uncertainty_probe":
                    e.loc[idx, "uncertainty"] -= strength * 0.55
                    e.loc[idx, "exploration"] += strength * 0.20
                elif ch == "relation_unlock":
                    e.loc[idx, "relation_lock"] -= strength
                    e.loc[idx, "reversibility"] += strength * 0.30
                elif ch == "buffer_increase":
                    e.loc[idx, "reversibility"] += strength
                    e.loc[idx, "volatility"] -= strength * 0.25
                    e.loc[idx, "uncertainty"] -= strength * 0.15

        for feat in STATE_FEATURES:
            e[feat] = np.clip(e[feat], 0.02, 0.98)

        # Relation updates reflect entity coupling / lock / exploration.
        r = self.relations.copy()
        ent = e.set_index("entity_id")
        if not r.empty:
            src_lock = r["source"].map(ent["relation_lock"]).to_numpy()
            dst_lock = r["target"].map(ent["relation_lock"]).to_numpy()
            src_coupling = r["source"].map(ent["coupling"]).to_numpy()
            dst_explore = r["target"].map(ent["exploration"]).to_numpy()
            r["relation_rigidity"] = r["relation_rigidity"] + 0.020 * ((src_lock + dst_lock)/2 - 0.5) - cfg.relation_decay * (r["relation_rigidity"] - 0.45)
            r["relation_strength"] = r["relation_strength"] + 0.015 * ((src_coupling + r["relation_rigidity"])/2 - 0.5)
            r["flow"] = r["flow"] + 0.018 * (dst_explore - 0.45) + self.rng.normal(0, cfg.noise_scale, len(r))
            for c in ["relation_strength", "relation_rigidity", "flow"]:
                r[c] = np.clip(r[c], 0.02, 0.98)

        self.entities = e
        self.relations = r
        return self.emit_trace()
