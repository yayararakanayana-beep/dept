"""PseudoReality v3.2 expected-value exploration-cost terrain world.

v3.2 deliberately branches from the frozen v3 world, not from the v3.1 stress
lineage. It adds a gain-optimization route:

- existing-path expected value falls when short dominance coincides with total
  gain decline;
- exploration is not directly commanded as a pressure. It becomes attractive
  when exploration-cost-adjusted expected value exceeds the existing path;
- successful short gains and exploratory flow are retained as information;
- retained information lowers exploration/friction cost and gives a natural
  route toward medium-term payoff.

The module does not add residual stress, stress tolerance, credit cost,
phenomenon flags, action modules, G_t/O_t/DEPT connections, or individual agents.
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
class DistributionTerrainV32Config(DistributionTerrainV3Config):
    """Configuration for the v3.2 gain-optimization route."""

    scenario: str = "distribution_terrain_v3_2_expected_value_exploration_cost"

    expected_value_decline_rate: float = 0.35
    exploration_option_bonus_rate: float = 0.20
    base_exploration_cost: float = 0.24
    information_memory_retention_rate: float = 0.045
    information_memory_decay_rate: float = 0.010
    information_memory_cost_reduction_rate: float = 0.30
    information_to_medium_rate: float = 0.055
    information_friction_reduction_rate: float = 0.040
    information_viscosity_reduction_rate: float = 0.020
    exploration_advantage_short_penalty_rate: float = 0.018


class DistributionTerrainV32World(DistributionTerrainV3World):
    """v3.2 terrain world with expected-value comparison and exploration cost."""

    config: DistributionTerrainV32Config

    def __init__(self, config: DistributionTerrainV32Config | None = None) -> None:
        super().__init__(config or DistributionTerrainV32Config())

    def reset(self) -> None:
        self.existing_path_expected_value = np.zeros(self.shape, dtype=float)
        self.exploration_cost = np.zeros(self.shape, dtype=float)
        self.exploration_option_value = np.zeros(self.shape, dtype=float)
        self.exploration_net_expected_value = np.zeros(self.shape, dtype=float)
        self.expected_value_advantage = np.zeros(self.shape, dtype=float)
        self.information_memory = np.zeros(self.shape, dtype=float)
        self.short_gain_information_conversion = np.zeros(self.shape, dtype=float)
        self.total_gain_delta_signal = 0.0
        self.previous_total_gain = 0.0
        super().reset()
        self.previous_total_gain = self._distribution_weighted_base_composite()

    def emit_trace(self) -> dict[str, Any]:
        return {
            "v3_2_internal_distribution_trace": pd.DataFrame(self._distribution_trace),
            "v3_2_internal_terrain_trace": pd.DataFrame(self._terrain_trace),
            "v3_2_internal_flow_trace": pd.DataFrame(self._flow_trace),
            "v3_2_internal_external_trace": pd.DataFrame(self._external_trace),
            "v3_2_internal_auxiliary_trace": pd.DataFrame(self._auxiliary_trace),
        }

    def _base_composite_payoff(self) -> np.ndarray:
        return (
            self.config.short_term_weight * self.short_payoff
            + self.config.medium_term_weight * self.medium_payoff
            - self.friction
        )

    def _distribution_weighted_base_composite(self) -> float:
        return float(np.sum(self.distribution * self._base_composite_payoff()))

    def _composite_payoff(self) -> np.ndarray:
        # Exploration attractiveness is an expected-value difference, not a direct
        # phenomenon flag or externally commanded exploration pressure.
        return np.clip(
            self._base_composite_payoff()
            + self.config.exploration_option_bonus_rate * self.expected_value_advantage,
            -1.0,
            1.5,
        )

    def _learning_quality(self) -> np.ndarray:
        resource, info, pressure, exploration, reversibility = self._coordinate_grids()
        pressure_balance = 1.0 - np.clip((pressure - 0.45) / 0.55, 0.0, 1.0)
        return np.clip(
            0.16 * resource
            + 0.28 * info
            + 0.22 * exploration
            + 0.20 * reversibility
            + 0.06 * pressure_balance
            + 0.04 * (1.0 - self.damage)
            + 0.04 * (1.0 - self.friction),
            0.0,
            1.0,
        )

    def _update_expected_value_fields(self) -> tuple[np.ndarray, float, float]:
        resource, info, pressure, exploration, reversibility = self._coordinate_grids()
        del resource, pressure
        base_composite = self._base_composite_payoff()
        current_total_gain = float(np.sum(self.distribution * base_composite))
        total_gain_delta = current_total_gain - self.previous_total_gain
        decline_signal = float(np.clip(-total_gain_delta / 0.05, 0.0, 1.0))
        self.total_gain_delta_signal = total_gain_delta

        short_dominance = np.clip((self.short_payoff - self.medium_payoff) / 0.50, 0.0, 1.0)
        normalized_existing = np.clip(base_composite / 1.5, -1.0, 1.0)
        self.existing_path_expected_value = np.clip(
            normalized_existing - self.config.expected_value_decline_rate * decline_signal * short_dominance,
            -1.0,
            1.0,
        )

        distribution_load = self.distribution / max(float(self.distribution.max()), 1e-12)
        unused_route_room = 1.0 - np.clip(distribution_load, 0.0, 1.0)
        learning_quality = self._learning_quality()
        self.exploration_cost = np.clip(
            self.config.base_exploration_cost
            * (1.0 - 0.28 * info - 0.24 * exploration - 0.20 * reversibility)
            + 0.16 * self.damage
            + 0.08 * self.friction
            - self.config.information_memory_cost_reduction_rate * self.information_memory,
            0.0,
            1.0,
        )
        self.exploration_option_value = np.clip(
            0.30 * exploration
            + 0.28 * info
            + 0.18 * reversibility
            + 0.14 * unused_route_room
            + 0.10 * self.information_memory,
            0.0,
            1.0,
        )
        self.exploration_net_expected_value = np.clip(
            self.exploration_option_value - self.exploration_cost,
            -1.0,
            1.0,
        )
        relative_advantage = np.maximum(self.exploration_net_expected_value - self.existing_path_expected_value, 0.0)
        self.expected_value_advantage = np.clip(
            relative_advantage * short_dominance * (0.30 + 0.70 * decline_signal) * learning_quality,
            0.0,
            1.0,
        )
        return learning_quality, total_gain_delta, decline_signal

    def _deform_terrain(self, inbound_flow: np.ndarray) -> None:
        learning_quality, total_gain_delta, _decline_signal = self._update_expected_value_fields()
        success_signal = float(np.clip(total_gain_delta / 0.05, 0.0, 1.0))
        short_dominance = np.clip((self.short_payoff - self.medium_payoff) / 0.50, 0.0, 1.0)

        concentration_excess = np.maximum(self.distribution - self.config.concentration_damage_threshold, 0.0)
        damage_delta = self.config.overconcentration_damage_rate * concentration_excess
        recovery = self.config.natural_recovery_rate * self.recovery_speed
        self.damage = np.clip(self.damage + damage_delta - recovery, 0.0, 1.0)
        self.rigidity = np.clip(self.rigidity + 0.5 * damage_delta - recovery, 0.0, 1.0)

        self.short_gain_information_conversion = np.clip(
            inbound_flow * short_dominance * learning_quality * success_signal,
            0.0,
            1.0,
        )
        exploratory_information = inbound_flow * self.expected_value_advantage * learning_quality
        information_delta = self.config.information_memory_retention_rate * (
            self.short_gain_information_conversion + exploratory_information
        )
        memory_decay = self.config.information_memory_decay_rate * (1.0 - 0.35 * learning_quality)
        self.information_memory = np.clip((1.0 - memory_decay) * self.information_memory + information_delta, 0.0, 1.0)

        reinforcement = self.config.path_reinforcement_rate * inbound_flow
        short_reinforcement = reinforcement * (1.0 - 0.35 * self.expected_value_advantage)
        medium_information_gain = self.config.information_to_medium_rate * self.information_memory * learning_quality
        short_advantage_penalty = self.config.exploration_advantage_short_penalty_rate * self.expected_value_advantage

        self.short_payoff = np.clip(
            self.short_payoff + short_reinforcement - 0.01 * self.damage - short_advantage_penalty,
            0.0,
            1.5,
        )
        self.medium_payoff = np.clip(
            self.medium_payoff - 0.02 * self.damage + 0.25 * recovery + medium_information_gain,
            0.0,
            1.5,
        )
        self.friction = np.clip(
            self.config.base_friction
            + 0.40 * self.damage
            + 0.10 * self.rigidity
            - reinforcement
            - self.config.information_friction_reduction_rate * self.information_memory,
            0.0,
            0.95,
        )
        self.viscosity = np.clip(
            self.config.base_viscosity
            + 0.30 * self.rigidity
            + 0.20 * self.damage
            - self.config.information_viscosity_reduction_rate * self.information_memory,
            0.0,
            0.95,
        )
        self.recovery_speed = np.clip(
            self.config.base_recovery_speed * (1.0 - 0.60 * self.damage - 0.30 * self.rigidity)
            + 0.04 * self.information_memory,
            0.0,
            1.0,
        )
        self.previous_total_gain = self._distribution_weighted_base_composite()

    def _record_trace(self, total_flow: float, stay_mass: float) -> None:
        super()._record_trace(total_flow=total_flow, stay_mass=stay_mass)
        distribution = self.distribution

        def weighted_mean(value: np.ndarray) -> float:
            return float(np.sum(distribution * value))

        optimization_row = {
            "existing_path_expected_value_mean": float(self.existing_path_expected_value.mean()),
            "exploration_cost_mean": float(self.exploration_cost.mean()),
            "exploration_option_value_mean": float(self.exploration_option_value.mean()),
            "exploration_net_expected_value_mean": float(self.exploration_net_expected_value.mean()),
            "expected_value_advantage_mean": float(self.expected_value_advantage.mean()),
            "information_memory_mean": float(self.information_memory.mean()),
            "short_gain_information_conversion_mean": float(self.short_gain_information_conversion.mean()),
            "total_gain_delta_signal": float(self.total_gain_delta_signal),
            "existing_path_expected_value_distribution_weighted_mean": weighted_mean(self.existing_path_expected_value),
            "exploration_cost_distribution_weighted_mean": weighted_mean(self.exploration_cost),
            "exploration_option_value_distribution_weighted_mean": weighted_mean(self.exploration_option_value),
            "exploration_net_expected_value_distribution_weighted_mean": weighted_mean(self.exploration_net_expected_value),
            "expected_value_advantage_distribution_weighted_mean": weighted_mean(self.expected_value_advantage),
            "information_memory_distribution_weighted_mean": weighted_mean(self.information_memory),
            "short_gain_information_conversion_distribution_weighted_mean": weighted_mean(
                self.short_gain_information_conversion
            ),
        }
        self._terrain_trace[-1].update(optimization_row)
        self._auxiliary_trace[-1].update(optimization_row)
