"""PseudoReality v3.1 distribution-terrain world.

v3.1 keeps the frozen v3 implementation intact and adds a separate terrain world
with long-horizon circulation dynamics. The additions are deliberately local
terrain mechanics, not phenomenon flags and not an action module:

- medium-path self-reinforcement in high-quality terrain;
- conditional self-recovery when stress can be processed;
- residual/nonproductive stress when stress exceeds local drain capacity.

Collapse-like outcomes are not directly designed here. They may appear only as a
consequence of residual stress, damage, rigidity, friction, and low flow.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from pseudo_reality.distribution_terrain_v3 import (
    DistributionTerrainV3Config,
    DistributionTerrainV3World,
)


@dataclass(frozen=True)
class DistributionTerrainV31Config(DistributionTerrainV3Config):
    """Configuration for the v3.1 circulation-dynamics terrain world."""

    scenario: str = "distribution_terrain_v3_1_circulation"

    medium_path_reinforcement_rate: float = 0.035
    productive_stress_learning_rate: float = 0.015
    medium_path_memory_decay_rate: float = 0.015

    conditional_recovery_rate: float = 0.035
    residual_stress_accumulation_rate: float = 0.10
    residual_stress_release_rate: float = 0.035

    nonproductive_stress_damage_rate: float = 0.025
    nonproductive_stress_rigidity_rate: float = 0.020
    nonproductive_stress_friction_rate: float = 0.030
    nonproductive_stress_medium_penalty_rate: float = 0.035


class DistributionTerrainV31World(DistributionTerrainV3World):
    """v3.1 terrain world with local circulation and residual-stress mechanics."""

    config: DistributionTerrainV31Config

    def __init__(self, config: DistributionTerrainV31Config | None = None) -> None:
        super().__init__(config or DistributionTerrainV31Config())

    def reset(self) -> None:
        self.medium_path_memory = np.zeros(self.shape, dtype=float)
        self.stress_load = np.zeros(self.shape, dtype=float)
        self.stress_drain_capacity = np.zeros(self.shape, dtype=float)
        self.productive_stress = np.zeros(self.shape, dtype=float)
        self.residual_stress = np.zeros(self.shape, dtype=float)
        self.nonproductive_stress = np.zeros(self.shape, dtype=float)
        self.terrain_quality = np.zeros(self.shape, dtype=float)
        super().reset()

    def emit_trace(self) -> dict[str, Any]:
        return {
            "v3_1_internal_distribution_trace": pd.DataFrame(self._distribution_trace),
            "v3_1_internal_terrain_trace": pd.DataFrame(self._terrain_trace),
            "v3_1_internal_flow_trace": pd.DataFrame(self._flow_trace),
            "v3_1_internal_external_trace": pd.DataFrame(self._external_trace),
            "v3_1_internal_auxiliary_trace": pd.DataFrame(self._auxiliary_trace),
        }

    def _stress_balance(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        resource, info, pressure, exploration, reversibility = self._coordinate_grids()
        low_resource = 1.0 - resource
        low_info = 1.0 - info
        low_exploration = 1.0 - exploration
        low_reversibility = 1.0 - reversibility
        high_pressure = np.clip((pressure - 0.45) / 0.55, 0.0, 1.0)
        external_shock = max(0.0, float(self.external_factors.get("external_shock", 0.0)))
        external_constraint = max(0.0, float(self.external_factors.get("external_constraint_pressure", 0.0)))
        external_noise = max(0.0, float(self.external_factors.get("external_information_noise", 0.0)))

        stress_load = np.clip(
            0.18 * low_resource
            + 0.16 * low_info
            + 0.18 * high_pressure
            + 0.10 * low_exploration
            + 0.10 * low_reversibility
            + 0.13 * self.damage
            + 0.10 * self.rigidity
            + 0.08 * external_shock
            + 0.04 * external_constraint
            + 0.03 * external_noise,
            0.0,
            1.0,
        )

        raw_capacity = np.clip(
            0.22 * resource
            + 0.22 * info
            + 0.18 * reversibility
            + 0.12 * exploration
            + 0.12 * self.recovery_speed
            + 0.08 * (1.0 - self.friction)
            + 0.06 * (1.0 - self.viscosity),
            0.0,
            1.0,
        )
        damage_drag = np.clip((1.0 - 0.45 * self.damage) * (1.0 - 0.30 * self.rigidity), 0.0, 1.0)
        drain_capacity = np.clip(raw_capacity * damage_drag, 0.0, 1.0)
        productive_stress = np.minimum(stress_load, drain_capacity)
        residual_gap = np.maximum(stress_load - drain_capacity, 0.0)
        return stress_load, drain_capacity, productive_stress, residual_gap, high_pressure

    def _terrain_quality_score(self, high_pressure: np.ndarray) -> np.ndarray:
        resource, info, _pressure, exploration, reversibility = self._coordinate_grids()
        pressure_balance = 1.0 - high_pressure
        return np.clip(
            0.18 * resource
            + 0.24 * info
            + 0.18 * exploration
            + 0.20 * reversibility
            + 0.10 * pressure_balance
            + 0.05 * (1.0 - self.damage)
            + 0.05 * (1.0 - self.friction),
            0.0,
            1.0,
        )

    def _deform_terrain(self, inbound_flow: np.ndarray) -> None:
        stress_load, drain_capacity, productive_stress, residual_gap, high_pressure = self._stress_balance()
        terrain_quality = self._terrain_quality_score(high_pressure)

        released_stress = self.config.residual_stress_release_rate * drain_capacity * (1.0 - self.damage)
        self.residual_stress = np.clip(
            (1.0 - self.config.residual_stress_release_rate) * self.residual_stress
            + self.config.residual_stress_accumulation_rate * residual_gap
            - released_stress,
            0.0,
            1.0,
        )
        nonproductive_stress = np.clip(residual_gap + self.residual_stress, 0.0, 1.0)

        concentration_excess = np.maximum(self.distribution - self.config.concentration_damage_threshold, 0.0)
        concentration_damage = self.config.overconcentration_damage_rate * concentration_excess
        stress_damage = self.config.nonproductive_stress_damage_rate * nonproductive_stress
        damage_delta = concentration_damage + stress_damage

        base_recovery = self.config.natural_recovery_rate * self.recovery_speed
        recovery_gate = drain_capacity * terrain_quality * (1.0 - 0.50 * self.residual_stress)
        conditional_recovery = self.config.conditional_recovery_rate * np.clip(recovery_gate, 0.0, 1.0)
        recovery = np.clip(base_recovery + conditional_recovery, 0.0, 1.0)

        self.damage = np.clip(self.damage + damage_delta - recovery, 0.0, 1.0)
        self.rigidity = np.clip(
            self.rigidity
            + 0.5 * concentration_damage
            + self.config.nonproductive_stress_rigidity_rate * nonproductive_stress
            - 0.7 * recovery,
            0.0,
            1.0,
        )

        medium_memory_delta = (
            self.config.medium_path_reinforcement_rate * inbound_flow * terrain_quality
            + self.config.productive_stress_learning_rate * productive_stress * terrain_quality * self.distribution
        )
        self.medium_path_memory = np.clip(
            (1.0 - self.config.medium_path_memory_decay_rate) * self.medium_path_memory + medium_memory_delta,
            0.0,
            1.0,
        )

        short_bias = 1.0 - terrain_quality
        short_reinforcement = self.config.path_reinforcement_rate * inbound_flow * short_bias
        medium_reinforcement = self.medium_path_memory
        medium_penalty = self.config.nonproductive_stress_medium_penalty_rate * nonproductive_stress

        self.short_payoff = np.clip(
            self.short_payoff + short_reinforcement - 0.01 * self.damage,
            0.0,
            1.5,
        )
        self.medium_payoff = np.clip(
            self.medium_payoff
            + medium_reinforcement
            + 0.30 * recovery
            - 0.015 * self.damage
            - medium_penalty,
            0.0,
            1.5,
        )
        self.friction = np.clip(
            self.config.base_friction
            + 0.36 * self.damage
            + 0.10 * self.rigidity
            + self.config.nonproductive_stress_friction_rate * nonproductive_stress
            - 0.50 * self.medium_path_memory
            - short_reinforcement,
            0.0,
            0.95,
        )
        self.viscosity = np.clip(
            self.config.base_viscosity
            + 0.28 * self.rigidity
            + 0.16 * self.damage
            + 0.10 * nonproductive_stress
            - 0.15 * self.medium_path_memory,
            0.0,
            0.95,
        )
        self.recovery_speed = np.clip(
            self.config.base_recovery_speed * (1.0 - 0.55 * self.damage - 0.25 * self.rigidity)
            + 0.20 * drain_capacity
            + 0.10 * terrain_quality
            - 0.20 * self.residual_stress,
            0.0,
            1.0,
        )

        self.stress_load = stress_load
        self.stress_drain_capacity = drain_capacity
        self.productive_stress = productive_stress
        self.nonproductive_stress = nonproductive_stress
        self.terrain_quality = terrain_quality

    def _record_trace(self, total_flow: float, stay_mass: float) -> None:
        super()._record_trace(total_flow=total_flow, stay_mass=stay_mass)
        distribution = self.distribution

        def weighted_mean(value: np.ndarray) -> float:
            return float(np.sum(distribution * value))

        circulation_row = {
            "stress_load_mean": float(self.stress_load.mean()),
            "stress_drain_capacity_mean": float(self.stress_drain_capacity.mean()),
            "productive_stress_mean": float(self.productive_stress.mean()),
            "residual_stress_mean": float(self.residual_stress.mean()),
            "nonproductive_stress_mean": float(self.nonproductive_stress.mean()),
            "terrain_quality_mean": float(self.terrain_quality.mean()),
            "medium_path_memory_mean": float(self.medium_path_memory.mean()),
            "stress_load_distribution_weighted_mean": weighted_mean(self.stress_load),
            "stress_drain_capacity_distribution_weighted_mean": weighted_mean(self.stress_drain_capacity),
            "productive_stress_distribution_weighted_mean": weighted_mean(self.productive_stress),
            "residual_stress_distribution_weighted_mean": weighted_mean(self.residual_stress),
            "nonproductive_stress_distribution_weighted_mean": weighted_mean(self.nonproductive_stress),
            "terrain_quality_distribution_weighted_mean": weighted_mean(self.terrain_quality),
            "medium_path_memory_distribution_weighted_mean": weighted_mean(self.medium_path_memory),
        }
        self._terrain_trace[-1].update(circulation_row)
        self._auxiliary_trace[-1].update(circulation_row)
