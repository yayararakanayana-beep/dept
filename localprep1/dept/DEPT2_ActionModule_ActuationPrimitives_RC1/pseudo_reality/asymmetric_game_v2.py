"""PseudoReality v2 asymmetric shrinking-equilibrium smoke world.

This module is intentionally world-local. It accepts only ActionFrame-like
input and emits trace tables for downstream read-only derivation.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple
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
        cause = self.profile_config.get("cause_side_parameters", {})
        self.cause_side_parameters = cause if isinstance(cause, dict) else {}
        implemented = self.profile_config.get("implemented_axes", [])
        self.implemented_axes = set(implemented if isinstance(implemented, list) else [])
        self.rng = np.random.default_rng(self.seed)
        self.shared_resource = float(self._cfg("resource_settings", "initial_shared_resource", 0.72))
        self.commons_health = float(self._cfg("resource_settings", "initial_commons_health", 0.70))
        self._last_action_effect = pd.DataFrame()
        self.t = 0
        self.entities = self._init_entities()
        self.hidden = self._init_hidden()
        self.relations = self._init_relations()

    def _clip(self, values):
        return np.clip(values, 0.0, 1.0)

    def _cfg(self, section: str, key: str, default: Any) -> Any:
        section_cfg = self.profile_config.get(section, {})
        if not isinstance(section_cfg, dict):
            return default
        return section_cfg.get(key, default)

    def _dynamic_enabled(self, name: str, default: bool = True) -> bool:
        dynamics = self.profile_config.get("active_dynamics", {})
        item = dynamics.get(name, {}) if isinstance(dynamics, dict) else {}
        if not isinstance(item, dict):
            return default
        return bool(item.get("enabled", default))

    def _dynamic_intensity(self, name: str, default: float) -> float:
        if not self._dynamic_enabled(name, True):
            return 0.0
        dynamics = self.profile_config.get("active_dynamics", {})
        item = dynamics.get(name, {}) if isinstance(dynamics, dict) else {}
        if not isinstance(item, dict):
            return float(default)
        return float(item.get("intensity", default))

    def _cause_axis(self, name: str, default: float = 0.0) -> float:
        if name not in self.implemented_axes:
            return float(default)
        try:
            return float(np.clip(self.cause_side_parameters.get(name, default), 0.0, 1.0))
        except (TypeError, ValueError):
            return float(default)

    def _init_entities(self) -> pd.DataFrame:
        n = self.n_entities
        e = pd.DataFrame({"entity_id": [f"E{i:03d}" for i in range(n)]})
        mix = self._cfg("entity_mix", "weights", None) or self.profile_config.get("entity_mix", {})
        types = ["stabilizer", "explorer", "extractor", "connector", "amplifier"]
        probs = np.array([float(mix.get(t, 1.0 / len(types))) for t in types]) if isinstance(mix, dict) else np.ones(len(types)) / len(types)
        probs = probs / probs.sum() if probs.sum() > 0 else np.ones(len(types)) / len(types)
        e["primary_type"] = self.rng.choice(types, size=n, p=probs)
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
        return {
            "entity_trace": e,
            "relation_trace": r,
            "v2_hidden_trace": h,
            "v2_game_trace": self._build_game_trace(e, h),
            "v2_resource_trace": self._build_resource_trace(h),
            "v2_information_trace": self._build_information_trace(h, r),
            "v2_action_effect_trace": self._build_action_effect_trace(),
        }


    def _base_row(self) -> Dict[str, Any]:
        return {"t": self.t, "scenario": self.scenario, "seed": self.seed}

    def _build_game_trace(self, e: pd.DataFrame, h: pd.DataFrame) -> pd.DataFrame:
        g = pd.DataFrame({"entity_id": e["entity_id"], "primary_type": e.get("primary_type", "unknown")})
        g["t"] = self.t
        g["scenario"] = self.scenario
        g["seed"] = self.seed
        g["cooperate_tendency"] = self._clip(0.55 * h["cooperation_intent"] + 0.25 * e["coupling"] + 0.20 * (1.0 - h["defensiveness"]))
        g["defend_tendency"] = self._clip(0.60 * h["defensiveness"] + 0.25 * e["relation_lock"] + 0.15 * h["latent_pressure"])
        g["explore_tendency"] = self._clip(0.70 * e["exploration"] + 0.30 * (1.0 - h["fatigue"]))
        g["extract_tendency"] = self._clip(0.55 * h["opportunism"] + 0.45 * (1.0 - h["private_resource"]))
        g["connect_tendency"] = self._clip(0.50 * e["coupling"] + 0.30 * h["cooperation_intent"] + 0.20 * (1.0 - e["relation_lock"]))
        g["amplify_tendency"] = self._clip(0.45 * e["volatility"] + 0.35 * (1.0 - h["information_quality"]) + 0.20 * h["latent_pressure"])
        g["hoard_tendency"] = self._clip(0.55 * h["defensiveness"] + 0.30 * h["private_resource"] + 0.15 * h["opportunism"])
        g["share_tendency"] = self._clip(0.60 * h["cooperation_intent"] + 0.25 * self.commons_health + 0.15 * (1.0 - h["opportunism"]))
        g["short_term_payoff"] = self._clip(0.45 * g["extract_tendency"] + 0.30 * g["defend_tendency"] + 0.25 * h["private_resource"])
        g["long_term_health_proxy"] = self._clip(0.35 * g["cooperate_tendency"] + 0.25 * g["explore_tendency"] + 0.25 * e["reversibility"] + 0.15 * (1.0 - h["hidden_damage"]))
        g["local_payoff"] = self._clip(0.55 * g["short_term_payoff"] + 0.45 * g["long_term_health_proxy"])
        cols = ["entity_id", "t", "scenario", "seed", "primary_type", "cooperate_tendency", "defend_tendency", "explore_tendency", "extract_tendency", "connect_tendency", "amplify_tendency", "hoard_tendency", "share_tendency", "local_payoff", "short_term_payoff", "long_term_health_proxy"]
        return g[cols]

    def _build_resource_trace(self, h: pd.DataFrame) -> pd.DataFrame:
        private = pd.to_numeric(h["private_resource"], errors="coerce").fillna(0.0)
        return pd.DataFrame([{**self._base_row(), "shared_resource": self.shared_resource, "commons_health": self.commons_health, "resource_pressure": float(self._clip(1.0 - self.shared_resource)), "resource_inequality": float(max(0.0, private.max() - private.min())), "private_resource_mean": float(private.mean()), "private_resource_std": float(max(0.0, private.std(ddof=0))), "private_resource_min": float(private.min()), "private_resource_max": float(private.max())}])

    def _build_information_trace(self, h: pd.DataFrame, r: pd.DataFrame) -> pd.DataFrame:
        quality = pd.to_numeric(h["information_quality"], errors="coerce").fillna(0.0)
        flow = float(r["flow"].mean()) if r is not None and not r.empty and "flow" in r.columns else 0.0
        information_asymmetry = self._cause_axis("information_asymmetry", 0.0)
        action_cost = self._cause_axis("action_cost", 0.0)
        distortion = float(self._cfg("information_settings", "information_distortion_scale", 0.06)) + float((1.0 - quality.mean()) * 0.35)
        delay = float(self._cfg("information_settings", "information_delay_steps", 2)) / 10.0 + float(h["latent_pressure"].mean() * 0.15)
        return pd.DataFrame([{**self._base_row(), "information_delay_mean": float(self._clip(delay)), "information_distortion_mean": float(self._clip(distortion)), "hidden_state_visibility": float(self._clip(self._cfg("information_settings", "hidden_state_visibility", 0.22))), "private_information_rate": float(self._clip(self._cfg("information_settings", "private_information_rate", 0.30))), "misread_probability_mean": float(self._clip(self._cfg("information_settings", "misread_probability", 0.10) + distortion * 0.5)), "information_quality_mean": float(self._clip(quality.mean())), "information_flow_mean": float(self._clip(flow * quality.mean())), "coordination_lag_mean": float(self._clip(delay + distortion * 0.3)), "cause_side_information_asymmetry": information_asymmetry, "cause_side_action_cost": action_cost, "observed_vs_hidden_gap_proxy": float(self._clip(information_asymmetry * (1.0 - quality.mean()) + h["hidden_damage"].mean() * 0.25))}])

    def _build_action_effect_trace(self) -> pd.DataFrame:
        if self._last_action_effect is None or self._last_action_effect.empty:
            row = {**self._base_row(), "action_channel": "no_action", "action_intensity": 0.0, "target_count": 0, "direct_effect_score": 0.0, "side_effect_score": 0.0, "net_public_effect_score": 0.0, "net_hidden_effect_score": 0.0, "exploitation_risk_delta": 0.0, "trust_delta": 0.0, "fatigue_delta": 0.0, "hidden_damage_delta": 0.0, "resource_inequality_delta": 0.0, "reversibility_delta": 0.0, "exploration_delta": 0.0, "action_cost_effect": 0.0}
            return pd.DataFrame([row])
        out = self._last_action_effect.copy()
        out["t"] = self.t
        out["scenario"] = self.scenario
        out["seed"] = self.seed
        cols = ["t", "scenario", "seed", "action_channel", "action_intensity", "target_count", "direct_effect_score", "side_effect_score", "net_public_effect_score", "net_hidden_effect_score", "exploitation_risk_delta", "trust_delta", "fatigue_delta", "hidden_damage_delta", "resource_inequality_delta", "reversibility_delta", "exploration_delta", "action_cost_effect"]
        return out[cols]

    def step(self, action_frame: Optional[pd.DataFrame] = None) -> Dict[str, pd.DataFrame]:
        self.t += 1
        e = self.entities.copy()
        h = self.hidden.copy()
        n = len(e)

        trust_decay = self._dynamic_intensity("trust_decay", 0.04)
        hoarding = self._dynamic_intensity("defensive_hoarding", 0.05)
        hidden_growth = self._dynamic_intensity("hidden_damage_growth", 0.04)
        info_distortion = float(self._cfg("information_settings", "information_distortion_scale", 0.06))
        resource_depletion = float(self._cfg("resource_settings", "resource_depletion_rate", 0.035))
        no_op_decay = self._dynamic_intensity("no_op_decay", 0.03)
        information_asymmetry = self._cause_axis("information_asymmetry", 0.0)
        action_cost = self._cause_axis("action_cost", 0.0)

        h["latent_pressure"] += 0.010 + 0.50 * hoarding * h["defensiveness"] + self.rng.normal(0, self.noise_scale, n)
        h["fatigue"] += 0.010 + 0.35 * no_op_decay + 0.018 * h["latent_pressure"] + self.rng.normal(0, self.noise_scale, n)
        h["hidden_damage"] += 0.006 + 0.40 * hidden_growth + 0.020 * h["fatigue"] + 0.012 * (1.0 - h["information_quality"]) + 0.006 * information_asymmetry
        h["private_resource"] += -0.004 - resource_depletion * h["opportunism"] + self.rng.normal(0, self.noise_scale * 0.5, n)
        h["defensiveness"] += 0.006 + 0.35 * hoarding + 0.018 * h["latent_pressure"] + 0.005 * information_asymmetry
        h["cooperation_intent"] += -0.004 - 0.25 * trust_decay - 0.020 * h["defensiveness"] - 0.004 * information_asymmetry
        h["information_quality"] += -0.004 - info_distortion - 0.012 * h["opportunism"] - 0.010 * information_asymmetry
        h["opportunism"] += 0.004 + 0.010 * (1.0 - h["private_resource"])
        self.shared_resource = float(self._clip(self.shared_resource + float(self._cfg("resource_settings", "resource_recovery_rate", 0.018)) * self.commons_health - resource_depletion * float(h["opportunism"].mean())))
        self.commons_health = float(self._clip(self.commons_health - 0.25 * hidden_growth * float(h["hidden_damage"].mean()) - 0.10 * resource_depletion))

        before_e = e.copy()
        before_h = h.copy()
        effect_rows = []
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
                if action_cost:
                    h.loc[idx, "fatigue"] += strength * action_cost
                    h.loc[idx, "defensiveness"] += strength * action_cost * 0.50
                    h.loc[idx, "latent_pressure"] += strength * action_cost * 0.50
                side = float(self._cfg("side_effect_settings", "exploration_exploitation_risk", 0.24)) if ch == "exploration_injection" else float(self._cfg("side_effect_settings", "stabilization_lockin_side_effect", 0.22))
                effect_rows.append({"action_channel": ch, "action_intensity": float(strength / max(self.action_coupling, 1e-9)), "target_count": int(idx.sum()), "direct_effect_score": float(self._clip(strength * 8.0)), "side_effect_score": float(self._clip(side * strength * 8.0)), "exploitation_risk_delta": float(self._clip(side * strength)), "trust_delta": float(self._clip(strength * (1.0 if ch in {"uncertainty_probe", "coupling_relief"} else 0.0))), "fatigue_delta": float(self._clip(abs(h.loc[idx, "fatigue"].mean() - before_h.loc[idx, "fatigue"].mean()))), "hidden_damage_delta": 0.0, "resource_inequality_delta": 0.0, "reversibility_delta": float(self._clip(abs(e.loc[idx, "reversibility"].mean() - before_e.loc[idx, "reversibility"].mean()))), "exploration_delta": float(self._clip(abs(e.loc[idx, "exploration"].mean() - before_e.loc[idx, "exploration"].mean()))), "action_cost_effect": float(self._clip(strength * action_cost))})

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

        if effect_rows:
            cur_ineq = float(h["private_resource"].max() - h["private_resource"].min())
            prev_ineq = float(before_h["private_resource"].max() - before_h["private_resource"].min())
            for row in effect_rows:
                row["net_public_effect_score"] = float(self._clip(abs(row["reversibility_delta"]) + abs(row["exploration_delta"])))
                row["net_hidden_effect_score"] = float(self._clip(abs(row["fatigue_delta"]) + abs(row["exploitation_risk_delta"])))
                row["hidden_damage_delta"] = float(self._clip(abs(h["hidden_damage"].mean() - before_h["hidden_damage"].mean())))
                row["resource_inequality_delta"] = float(self._clip(abs(cur_ineq - prev_ineq)))
            self._last_action_effect = pd.DataFrame(effect_rows)
        else:
            self._last_action_effect = pd.DataFrame()

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
