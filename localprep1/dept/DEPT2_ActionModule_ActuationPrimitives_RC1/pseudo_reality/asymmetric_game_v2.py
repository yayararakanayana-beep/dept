"""PseudoReality v2 asymmetric shrinking-equilibrium smoke world.

This module is intentionally world-local. It accepts only ActionFrame-like
input and emits trace tables for downstream read-only derivation.
"""
from __future__ import annotations

from typing import Any, Dict, Optional
import numpy as np
import pandas as pd

from .system import STATE_FEATURES


V2_HIDDEN_FEATURES = [
    "latent_pressure",
    "fatigue",
    "private_resource",
    "defensiveness",
    "opportunism",
    "cooperation_intent",
    "information_quality",
    "hidden_damage",
]


class AsymmetricGamePseudoRealitySystem:
    """Minimal asymmetric game pseudo-world for v2 shrinking-equilibrium smoke."""

    def __init__(
        self,
        seed: int = 42,
        scenario: str = "v2_shrinking_equilibrium",
        n_entities: int = 24,
        action_coupling: float = 0.045,
        noise_scale: float = 0.018,
        drift_scale: float = 0.006,
        profile_name: str = "",
        profile_config: Optional[Dict[str, Any]] = None,
    ):
        self.seed = int(seed)
        self.scenario = str(scenario)
        self.n_entities = int(n_entities)
        self.action_coupling = float(action_coupling)
        self.noise_scale = float(noise_scale)
        self.drift_scale = float(drift_scale)
        self.profile_name = str(profile_name or "pseudo_reality_v2_shrinking_equilibrium")
        self.profile_config = dict(profile_config or {})
        self.rng = np.random.default_rng(self.seed)
        self.t = 0
        self.entities = self._init_entities()
        self.hidden = self._init_hidden()
        self.relations = self._init_relations()

    def _clip(self, values):
        return np.clip(values, 0.0, 1.0)

    def _init_entities(self) -> pd.DataFrame:
        n = self.n_entities
        e = pd.DataFrame({"entity_id": [f"E{i:03d}" for i in range(n)]})
        means = dict(activity=0.56, volatility=0.22, uncertainty=0.38, relation_lock=0.54,
                     coupling=0.60, exploration=0.42, reversibility=0.58, entropy=0.46)
        for feat in STATE_FEATURES:
            e[feat] = self._clip(self.rng.normal(means[feat], 0.055, size=n))
        return e

    def _init_hidden(self) -> pd.DataFrame:
        n = self.n_entities
        h = pd.DataFrame({"entity_id": [f"E{i:03d}" for i in range(n)]})
        means = dict(latent_pressure=0.42, fatigue=0.30, private_resource=0.62, defensiveness=0.46,
                     opportunism=0.36, cooperation_intent=0.52, information_quality=0.68, hidden_damage=0.22)
        for feat in V2_HIDDEN_FEATURES:
            h[feat] = self._clip(self.rng.normal(means[feat], 0.06, size=n))
        return h

    def _init_relations(self) -> pd.DataFrame:
        ids = self.entities["entity_id"].tolist()
        rows = []
        for i, src in enumerate(ids):
            for j, dst in enumerate(ids):
                if i == j:
                    continue
                if self.rng.random() < 0.18:
                    rows.append((
                        src,
                        dst,
                        float(self._clip(self.rng.normal(0.48, 0.13))),
                        float(self._clip(self.rng.normal(0.50, 0.14))),
                        float(self._clip(self.rng.normal(0.48, 0.14))),
                    ))
        if not rows and len(ids) >= 2:
            rows.append((ids[0], ids[1], 0.48, 0.50, 0.48))
        return pd.DataFrame(rows, columns=["source", "target", "relation_strength", "relation_rigidity", "flow"])

    def emit_trace(self) -> Dict[str, pd.DataFrame]:
        e = self.entities.copy()
        h = self.hidden.copy()
        r = self.relations.copy()
        for df in (e, h, r):
            df["t"] = self.t
            df["scenario"] = self.scenario
            df["seed"] = self.seed
        return {"entity_trace": e, "relation_trace": r, "v2_hidden_trace": h}

    def step(self, action_frame: Optional[pd.DataFrame] = None) -> Dict[str, pd.DataFrame]:
        self.t += 1
        e = self.entities.copy()
        h = self.hidden.copy()
        n = len(e)

        h["latent_pressure"] += 0.020 + 0.025 * h["defensiveness"] + self.rng.normal(0, self.noise_scale, n)
        h["fatigue"] += 0.018 + 0.018 * h["latent_pressure"] + self.rng.normal(0, self.noise_scale, n)
        h["hidden_damage"] += 0.014 + 0.020 * h["fatigue"] + 0.012 * (1.0 - h["information_quality"])
        h["private_resource"] += -0.010 - 0.018 * h["opportunism"] + self.rng.normal(0, self.noise_scale * 0.5, n)
        h["defensiveness"] += 0.014 + 0.018 * h["latent_pressure"]
        h["cooperation_intent"] += -0.014 - 0.020 * h["defensiveness"]
        h["information_quality"] += -0.010 - 0.012 * h["opportunism"]
        h["opportunism"] += 0.006 + 0.010 * (1.0 - h["private_resource"])

        if action_frame is not None and not action_frame.empty and "entity_id" in action_frame.columns:
            af = action_frame.copy()
            for _, row in af.iterrows():
                idx = e["entity_id"] == row.get("entity_id")
                if not idx.any():
                    continue
                strength = float(np.clip(row.get("action_strength", 0.0), 0.0, 1.0)) * self.action_coupling
                ch = str(row.get("action_channel", "no_op"))
                if ch == "exploration_injection":
                    e.loc[idx, "exploration"] += strength
                    h.loc[idx, "fatigue"] += strength * 0.30
                elif ch == "coupling_relief":
                    e.loc[idx, "coupling"] -= strength
                    e.loc[idx, "relation_lock"] -= strength * 0.40
                    h.loc[idx, "latent_pressure"] -= strength * 0.25
                elif ch == "volatility_damping":
                    e.loc[idx, "volatility"] -= strength
                    h.loc[idx, "fatigue"] -= strength * 0.15
                elif ch == "uncertainty_probe":
                    e.loc[idx, "uncertainty"] -= strength * 0.45
                    h.loc[idx, "information_quality"] += strength * 0.25
                elif ch == "relation_unlock":
                    e.loc[idx, "relation_lock"] -= strength
                    h.loc[idx, "defensiveness"] += strength * 0.20
                elif ch == "buffer_increase":
                    e.loc[idx, "reversibility"] += strength
                    h.loc[idx, "private_resource"] += strength * 0.20

        # Public stability mask: surface changes are bounded while hidden stress moves.
        e["activity"] += self.rng.normal(0, self.noise_scale, n)
        e["volatility"] += 0.010 * h["latent_pressure"] - 0.006 * h["cooperation_intent"]
        e["uncertainty"] += 0.010 * (1.0 - h["information_quality"])
        e["relation_lock"] += 0.012 * h["defensiveness"]
        e["coupling"] += 0.004 * h["defensiveness"]
        e["exploration"] += -0.014 * h["fatigue"] - 0.004
        e["reversibility"] += -0.012 * h["hidden_damage"]
        e["entropy"] += -0.006 * h["hidden_damage"] + self.rng.normal(0, self.noise_scale * 0.5, n)

        for feat in STATE_FEATURES:
            e[feat] = self._clip(e[feat])
        for feat in V2_HIDDEN_FEATURES:
            h[feat] = self._clip(h[feat])

        r = self.relations.copy()
        if not r.empty:
            ent = e.set_index("entity_id")
            src_lock = r["source"].map(ent["relation_lock"]).to_numpy()
            dst_explore = r["target"].map(ent["exploration"]).to_numpy()
            r["relation_rigidity"] = self._clip(r["relation_rigidity"] + 0.018 * (src_lock - 0.5))
            r["relation_strength"] = self._clip(r["relation_strength"] + 0.010 * (r["relation_rigidity"] - 0.5))
            r["flow"] = self._clip(r["flow"] + 0.014 * (dst_explore - 0.5) + self.rng.normal(0, self.noise_scale, len(r)))

        self.entities = e
        self.hidden = h
        self.relations = r
        return self.emit_trace()
