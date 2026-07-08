"""Minimal PseudoReality v3 distribution-terrain world.

This module intentionally implements only the v3-1 internal world skeleton:
a normalized state distribution moves on a five-axis payoff terrain, and the
resulting flow/concentration lightly deforms auxiliary terrain attributes.
It does not connect to G_t, O_t, DEPT internals, public observations, or
individual player/entity models.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


_AXIS_NAMES = (
    "resource_slack",
    "information_quality",
    "pressure",
    "exploration_room",
    "reversibility",
)

_EXTERNAL_FACTOR_DEFAULTS = {
    "external_resource_supply": 0.0,
    "external_demand": 0.0,
    "external_competition_pressure": 0.0,
    "external_information_noise": 0.0,
    "external_shock": 0.0,
    "external_constraint_pressure": 0.0,
}

_THRESHOLD_DEFAULTS = {
    "resource_slack_low": 0.2,
    "information_quality_low": 0.2,
    "pressure_high": 0.8,
    "exploration_room_low": 0.2,
    "damage_high": 0.7,
    "rigidity_high": 0.7,
}


@dataclass(frozen=True)
class DistributionTerrainV3Config:
    """Configuration for the minimal PseudoReality v3 terrain world."""

    scenario: str = "distribution_terrain_v3_minimal"
    seed: int = 0
    n_bins: int = 5
    axes: tuple[str, ...] = _AXIS_NAMES

    short_term_weight: float = 0.6
    medium_term_weight: float = 0.4

    base_move_fraction: float = 0.2
    diffusion_rate: float = 0.01

    path_reinforcement_rate: float = 0.02
    overconcentration_damage_rate: float = 0.03
    natural_recovery_rate: float = 0.01

    base_friction: float = 0.10
    base_viscosity: float = 0.30
    base_recovery_speed: float = 0.05

    concentration_damage_threshold: float = 0.002

    external_factors: dict[str, float] | None = None
    thresholds: dict[str, float] | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DistributionTerrainV3Config":
        """Build a config from the JSON profile shape used by this task."""

        flattened: dict[str, Any] = {}
        direct_fields = {field.name for field in fields(cls)}
        for key, value in data.items():
            if key in direct_fields:
                flattened[key] = tuple(value) if key == "axes" else value

        payoff_weights = data.get("payoff_weights", {})
        flattened.setdefault("short_term_weight", payoff_weights.get("short_term", cls.short_term_weight))
        flattened.setdefault("medium_term_weight", payoff_weights.get("medium_term", cls.medium_term_weight))

        mobility = data.get("mobility", {})
        flattened.setdefault("base_move_fraction", mobility.get("base_move_fraction", cls.base_move_fraction))
        flattened.setdefault("diffusion_rate", mobility.get("diffusion_rate", cls.diffusion_rate))

        rates = data.get("terrain_deformation_rates", {})
        flattened.setdefault("path_reinforcement_rate", rates.get("path_reinforcement", cls.path_reinforcement_rate))
        flattened.setdefault(
            "overconcentration_damage_rate",
            rates.get("overconcentration_damage", cls.overconcentration_damage_rate),
        )
        flattened.setdefault("natural_recovery_rate", rates.get("natural_recovery", cls.natural_recovery_rate))

        defaults = data.get("auxiliary_defaults", {})
        flattened.setdefault("base_friction", defaults.get("base_friction", cls.base_friction))
        flattened.setdefault("base_viscosity", defaults.get("base_viscosity", cls.base_viscosity))
        flattened.setdefault("base_recovery_speed", defaults.get("base_recovery_speed", cls.base_recovery_speed))

        flattened.setdefault("external_factors", data.get("external_factors"))
        flattened.setdefault("thresholds", data.get("thresholds"))
        return cls(**flattened)

    @classmethod
    def from_json(cls, path: str | Path) -> "DistributionTerrainV3Config":
        with Path(path).open("r", encoding="utf-8") as fh:
            return cls.from_dict(json.load(fh))


class DistributionTerrainV3World:
    """Minimal executable distribution-terrain world for PseudoReality v3."""

    def __init__(self, config: DistributionTerrainV3Config | None = None) -> None:
        self.config = config or DistributionTerrainV3Config()
        if len(self.config.axes) != 5:
            raise ValueError("DistributionTerrainV3World expects exactly five axes")
        if self.config.n_bins < 2:
            raise ValueError("n_bins must be at least 2")
        self.shape = (self.config.n_bins,) * len(self.config.axes)
        self.rng = np.random.default_rng(self.config.seed)
        self.external_factors = dict(_EXTERNAL_FACTOR_DEFAULTS)
        self.external_factors.update(self.config.external_factors or {})
        self.thresholds = dict(_THRESHOLD_DEFAULTS)
        self.thresholds.update(self.config.thresholds or {})
        self.reset()

    def reset(self) -> None:
        self.t = 0
        coords = self._coordinate_grids()
        center = 0.5
        squared_radius = sum((coord - center) ** 2 for coord in coords)
        self.distribution = np.exp(-squared_radius / 0.08)
        self.distribution += self.rng.random(self.shape) * 0.001
        self._normalize_distribution()

        resource, info, pressure, exploration, reversibility = coords
        self.short_payoff = 0.45 * pressure + 0.25 * (1.0 - resource) + 0.20 * (1.0 - exploration) + 0.10 * (1.0 - info)
        self.medium_payoff = 0.35 * info + 0.25 * exploration + 0.25 * reversibility + 0.15 * (1.0 - np.abs(pressure - 0.45))

        self.friction = np.full(self.shape, self.config.base_friction, dtype=float)
        self.viscosity = np.full(self.shape, self.config.base_viscosity, dtype=float)
        self.damage = np.zeros(self.shape, dtype=float)
        self.rigidity = np.full(self.shape, 0.05, dtype=float)
        self.recovery_speed = np.full(self.shape, self.config.base_recovery_speed, dtype=float)
        self.last_flow = np.zeros(self.shape, dtype=float)

        self._distribution_trace: list[dict[str, Any]] = []
        self._terrain_trace: list[dict[str, Any]] = []
        self._flow_trace: list[dict[str, Any]] = []
        self._external_trace: list[dict[str, Any]] = []
        self._auxiliary_trace: list[dict[str, Any]] = []
        self._record_trace(total_flow=0.0, stay_mass=float(self.distribution.sum()))

    def step(self) -> None:
        composite = self._composite_payoff()
        new_distribution, inbound_flow, total_flow, stay_mass = self._flow_distribution(composite)
        self.distribution = np.maximum(new_distribution, 0.0)
        self._normalize_distribution()
        self.last_flow = inbound_flow
        self._deform_terrain(inbound_flow)
        self.t += 1
        self._record_trace(total_flow=total_flow, stay_mass=stay_mass)

    def emit_trace(self) -> dict[str, Any]:
        return {
            "v3_internal_distribution_trace": pd.DataFrame(self._distribution_trace),
            "v3_internal_terrain_trace": pd.DataFrame(self._terrain_trace),
            "v3_internal_flow_trace": pd.DataFrame(self._flow_trace),
            "v3_internal_external_trace": pd.DataFrame(self._external_trace),
            "v3_internal_auxiliary_trace": pd.DataFrame(self._auxiliary_trace),
        }

    def _coordinate_grids(self) -> tuple[np.ndarray, ...]:
        axis = np.linspace(0.0, 1.0, self.config.n_bins)
        return tuple(np.meshgrid(*([axis] * len(self.config.axes)), indexing="ij"))

    def _normalize_distribution(self) -> None:
        self.distribution = np.nan_to_num(self.distribution, nan=0.0, posinf=0.0, neginf=0.0)
        self.distribution = np.maximum(self.distribution, 0.0)
        total = float(self.distribution.sum())
        if total <= 0.0:
            self.distribution = np.full(self.shape, 1.0 / np.prod(self.shape), dtype=float)
        else:
            self.distribution /= total

    def _composite_payoff(self) -> np.ndarray:
        return (
            self.config.short_term_weight * self.short_payoff
            + self.config.medium_term_weight * self.medium_payoff
            - self.friction
        )

    def _neighbors(self, index: tuple[int, ...]) -> list[tuple[int, ...]]:
        neighbors = [index]
        for axis in range(len(index)):
            for delta in (-1, 1):
                candidate = list(index)
                candidate[axis] += delta
                if 0 <= candidate[axis] < self.config.n_bins:
                    neighbors.append(tuple(candidate))
        return neighbors

    def _flow_distribution(self, composite: np.ndarray) -> tuple[np.ndarray, np.ndarray, float, float]:
        new_distribution = np.zeros_like(self.distribution)
        inbound_flow = np.zeros_like(self.distribution)
        total_flow = 0.0
        stay_mass = 0.0
        for index in np.ndindex(self.shape):
            mass = float(self.distribution[index])
            if mass <= 0.0:
                continue
            candidates = self._neighbors(index)
            payoffs = np.array([composite[candidate] for candidate in candidates], dtype=float)
            payoff_gain = np.maximum(payoffs - composite[index], 0.0)
            payoff_gain[0] = 0.0
            diffusion = np.full(len(candidates), self.config.diffusion_rate, dtype=float)
            diffusion[0] = 0.0
            raw_weights = payoff_gain + diffusion
            raw_weights[0] = 0.0
            raw_sum = float(raw_weights.sum())
            local_drag = (1.0 - float(np.clip(self.viscosity[index], 0.0, 0.95))) * (1.0 - float(np.clip(self.friction[index], 0.0, 0.95)))
            move_fraction = float(np.clip(self.config.base_move_fraction * local_drag, 0.0, 0.95))
            movable_mass = mass * move_fraction if raw_sum > 0.0 else 0.0
            stay = mass - movable_mass
            new_distribution[index] += stay
            stay_mass += stay
            if movable_mass <= 0.0:
                continue
            for candidate, weight in zip(candidates, raw_weights, strict=True):
                moved = movable_mass * float(weight / raw_sum)
                new_distribution[candidate] += moved
                if candidate != index:
                    inbound_flow[candidate] += moved
                    total_flow += moved
        return new_distribution, inbound_flow, total_flow, stay_mass

    def _deform_terrain(self, inbound_flow: np.ndarray) -> None:
        concentration_excess = np.maximum(self.distribution - self.config.concentration_damage_threshold, 0.0)
        damage_delta = self.config.overconcentration_damage_rate * concentration_excess
        recovery = self.config.natural_recovery_rate * self.recovery_speed
        self.damage = np.clip(self.damage + damage_delta - recovery, 0.0, 1.0)
        self.rigidity = np.clip(self.rigidity + 0.5 * damage_delta - recovery, 0.0, 1.0)
        reinforcement = self.config.path_reinforcement_rate * inbound_flow
        self.short_payoff = np.clip(self.short_payoff + reinforcement - 0.01 * self.damage, 0.0, 1.5)
        self.medium_payoff = np.clip(self.medium_payoff - 0.02 * self.damage + 0.25 * recovery, 0.0, 1.5)
        self.friction = np.clip(self.config.base_friction + 0.40 * self.damage + 0.10 * self.rigidity - reinforcement, 0.0, 0.95)
        self.viscosity = np.clip(self.config.base_viscosity + 0.30 * self.rigidity + 0.20 * self.damage, 0.0, 0.95)
        self.recovery_speed = np.clip(self.config.base_recovery_speed * (1.0 - 0.60 * self.damage - 0.30 * self.rigidity), 0.0, 1.0)

    def _record_trace(self, total_flow: float, stay_mass: float) -> None:
        coords = self._coordinate_grids()
        entropy = -float(np.sum(self.distribution * np.log(np.maximum(self.distribution, 1e-12))))
        base = {"t": self.t, "scenario": self.config.scenario, "seed": self.config.seed}
        distribution_row = {
            **base,
            "mass_sum": float(self.distribution.sum()),
            "entropy": entropy,
            "max_mass": float(self.distribution.max()),
        }
        for axis_name, coord in zip(self.config.axes, coords, strict=True):
            center = float(np.sum(self.distribution * coord))
            distribution_row[f"center_{axis_name}"] = center
            distribution_row[f"spread_{axis_name}"] = float(np.sqrt(np.sum(self.distribution * (coord - center) ** 2)))
        self._distribution_trace.append(distribution_row)

        gap = np.abs(self.short_payoff - self.medium_payoff)
        terrain_row = {
            **base,
            "short_payoff_mean": float(self.short_payoff.mean()),
            "medium_payoff_mean": float(self.medium_payoff.mean()),
            "short_medium_gap_mean": float(gap.mean()),
            "friction_mean": float(self.friction.mean()),
            "viscosity_mean": float(self.viscosity.mean()),
            "damage_mean": float(self.damage.mean()),
            "rigidity_mean": float(self.rigidity.mean()),
            "recovery_speed_mean": float(self.recovery_speed.mean()),
        }
        self._terrain_trace.append(terrain_row)
        self._flow_trace.append({
            **base,
            "total_flow": float(total_flow),
            "mean_flow": float(self.last_flow.mean()),
            "max_flow": float(self.last_flow.max()),
            "stay_mass": float(stay_mass),
            "moved_mass": float(total_flow),
            "concentration": float(np.sum(self.distribution ** 2)),
        })
        self._external_trace.append({**base, **self.external_factors})
        self._auxiliary_trace.append({
            **base,
            "damage_mean": terrain_row["damage_mean"],
            "rigidity_mean": terrain_row["rigidity_mean"],
            "friction_mean": terrain_row["friction_mean"],
            "viscosity_mean": terrain_row["viscosity_mean"],
            "recovery_speed_mean": terrain_row["recovery_speed_mean"],
        })
