"""PseudoReality v3.2 expected-value exploration-cost terrain world.

v3.2 deliberately branches from the frozen v3 world, not from the v3.1 stress
lineage. It adds a gain-optimization route:

- existing-path expected value falls when short dominance coincides with total
  gain decline;
- exploration is not directly commanded as a pressure. It becomes attractive
  when exploration-cost-adjusted expected value exceeds the existing path;
- short gains, short-path disappointment, exploratory flow, and released flow
  are retained as information;
- retained information lowers exploration/friction cost and gives a natural
  route toward medium-term payoff;
- sustained negative net viability erodes route support and releases mass from
  the old route into exploration-weighted reallocation.

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
    information_memory_retention_rate: float = 0.075
    information_decline_retention_rate: float = 0.022
    exploration_experience_retention_rate: float = 0.030
    information_memory_decay_rate: float = 0.008
    information_memory_cost_reduction_rate: float = 0.45
    information_to_medium_rate: float = 0.095
    information_friction_reduction_rate: float = 0.060
    information_viscosity_reduction_rate: float = 0.030
    exploration_advantage_short_penalty_rate: float = 0.018

    viability_reserve_initial: float = 0.65
    viability_reserve_gain_rate: float = 0.025
    viability_reserve_loss_rate: float = 0.080
    maintenance_cost_floor: float = 0.030
    route_support_initial: float = 0.70
    route_support_gain_rate: float = 0.020
    route_support_loss_rate: float = 0.075
    release_rate: float = 0.18


class DistributionTerrainV32World(DistributionTerrainV3World):
    """v3.2 terrain world with expected-value comparison and release dynamics."""

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
        self.short_path_decline_information = np.zeros(self.shape, dtype=float)
        self.exploration_experience_information = np.zeros(self.shape, dtype=float)
        self.viability_reserve = np.full(
            self.shape,
            float(np.clip(self.config.viability_reserve_initial, 0.0, 1.0)),
            dtype=float,
        )
        self.route_support = np.full(
            self.shape,
            float(np.clip(self.config.route_support_initial, 0.0, 1.0)),
            dtype=float,
        )
        self.maintenance_cost = np.zeros(self.shape, dtype=float)
        self.net_viability_value = np.zeros(self.shape, dtype=float)
        self.negative_viability_pressure = np.zeros(self.shape, dtype=float)
        self.support_erosion = np.zeros(self.shape, dtype=float)
        self.released_mass = np.zeros(self.shape, dtype=float)
        self.release_reallocation_flow = np.zeros(self.shape, dtype=float)
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
            + 0.08 * (1.0 - self.route_support)
            - self.config.information_memory_cost_reduction_rate * self.information_memory,
            0.0,
            1.0,
        )
        self.exploration_option_value = np.clip(
            0.30 * exploration
            + 0.28 * info
            + 0.18 * reversibility
            + 0.14 * unused_route_room
            + 0.10 * self.information_memory
            + 0.08 * (1.0 - self.route_support),
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

    def _update_support_and_release(self, learning_quality: np.ndarray) -> None:
        base_composite = self._base_composite_payoff()
        short_dominance = np.clip((self.short_payoff - self.medium_payoff) / 0.50, 0.0, 1.0)
        distribution_load = self.distribution / max(float(self.distribution.max()), 1e-12)
        self.maintenance_cost = np.clip(
            self.config.maintenance_cost_floor
            + 0.12 * self.friction
            + 0.10 * self.damage
            + 0.05 * self.rigidity
            + 0.04 * short_dominance,
            0.0,
            1.0,
        )
        self.net_viability_value = np.clip(base_composite - self.maintenance_cost, -1.0, 1.5)
        positive_viability = np.clip(self.net_viability_value / 0.25, 0.0, 1.0)
        self.negative_viability_pressure = np.clip(-self.net_viability_value / 0.25, 0.0, 1.0)

        reserve_gain = self.config.viability_reserve_gain_rate * positive_viability * learning_quality
        reserve_loss = (
            self.config.viability_reserve_loss_rate
            * self.negative_viability_pressure
            * (0.50 + 0.50 * distribution_load)
        )
        self.viability_reserve = np.clip(self.viability_reserve + reserve_gain - reserve_loss, 0.0, 1.0)

        old_support = self.route_support.copy()
        support_gain = (
            self.config.route_support_gain_rate
            * (positive_viability + 0.25 * self.information_memory)
            * learning_quality
        )
        support_loss = (
            self.config.route_support_loss_rate
            * self.negative_viability_pressure
            * (0.35 + 0.65 * (1.0 - self.viability_reserve))
            * (0.50 + 0.50 * distribution_load)
        )
        self.route_support = np.clip(self.route_support + support_gain - support_loss, 0.0, 1.0)
        self.support_erosion = np.maximum(old_support - self.route_support, 0.0)

        release_pressure = np.clip(
            self.config.release_rate
            * self.negative_viability_pressure
            * (1.0 - self.route_support)
            * (0.30 + 0.70 * distribution_load),
            0.0,
            0.45,
        )
        self.released_mass = self.distribution * release_pressure
        released_total = float(self.released_mass.sum())
        self.release_reallocation_flow = np.zeros_like(self.distribution)
        if released_total <= 0.0:
            return

        resource, info, pressure, exploration, reversibility = self._coordinate_grids()
        del resource, pressure
        target_weight = np.clip(
            np.maximum(self.exploration_net_expected_value, 0.0)
            + 0.50 * self.expected_value_advantage
            + 0.25 * learning_quality
            + 0.20 * exploration
            + 0.15 * reversibility
            + 0.10 * (1.0 - distribution_load)
            - 0.15 * self.damage
            - 0.05 * self.friction,
            0.0,
            None,
        )
        target_sum = float(target_weight.sum())
        if target_sum <= 0.0:
            target_weight = learning_quality + 1e-9
            target_sum = float(target_weight.sum())
        self.release_reallocation_flow = released_total * target_weight / target_sum
        self.distribution = np.maximum(self.distribution - self.released_mass + self.release_reallocation_flow, 0.0)
        self._normalize_distribution()
        self.last_flow = np.maximum(self.last_flow + self.release_reallocation_flow, 0.0)

    def _deform_terrain(self, inbound_flow: np.ndarray) -> None:
        learning_quality, total_gain_delta, decline_signal = self._update_expected_value_fields()
        success_signal = float(np.clip(total_gain_delta / 0.05, 0.0, 1.0))
        short_dominance = np.clip((self.short_payoff - self.medium_payoff) / 0.50, 0.0, 1.0)

        concentration_excess = np.maximum(self.distribution - self.config.concentration_damage_threshold, 0.0)
        damage_delta = self.config.overconcentration_damage_rate * concentration_excess
        recovery = self.config.natural_recovery_rate * self.recovery_speed
        self.damage = np.clip(self.damage + damage_delta - recovery, 0.0, 1.0)
        self.rigidity = np.clip(self.rigidity + 0.5 * damage_delta - recovery, 0.0, 1.0)

        self._update_support_and_release(learning_quality)

        self.short_gain_information_conversion = np.clip(
            inbound_flow * short_dominance * learning_quality * success_signal,
            0.0,
            1.0,
        )
        self.short_path_decline_information = np.clip(
            self.distribution
            * short_dominance
            * learning_quality
            * decline_signal
            * (0.20 + 0.80 * self.expected_value_advantage),
            0.0,
            1.0,
        )
        self.exploration_experience_information = np.clip(
            inbound_flow * learning_quality * (0.50 * self.expected_value_advantage + 0.25 * decline_signal)
            + self.release_reallocation_flow * learning_quality * (0.35 + 0.65 * self.expected_value_advantage),
            0.0,
            1.0,
        )
        information_delta = (
            self.config.information_memory_retention_rate
            * (self.short_gain_information_conversion + self.exploration_experience_information)
            + self.config.information_decline_retention_rate * self.short_path_decline_information
            + self.config.exploration_experience_retention_rate
            * self.distribution
            * learning_quality
            * self.expected_value_advantage
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
            + 0.04 * self.information_memory
            + 0.02 * self.viability_reserve,
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
            "short_path_decline_information_mean": float(self.short_path_decline_information.mean()),
            "exploration_experience_information_mean": float(self.exploration_experience_information.mean()),
            "viability_reserve_mean": float(self.viability_reserve.mean()),
            "route_support_mean": float(self.route_support.mean()),
            "maintenance_cost_mean": float(self.maintenance_cost.mean()),
            "net_viability_value_mean": float(self.net_viability_value.mean()),
            "negative_viability_pressure_mean": float(self.negative_viability_pressure.mean()),
            "support_erosion_mean": float(self.support_erosion.mean()),
            "released_mass_mean": float(self.released_mass.mean()),
            "release_reallocation_flow_mean": float(self.release_reallocation_flow.mean()),
            "released_mass_sum": float(self.released_mass.sum()),
            "release_reallocation_flow_sum": float(self.release_reallocation_flow.sum()),
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
            "short_path_decline_information_distribution_weighted_mean": weighted_mean(
                self.short_path_decline_information
            ),
            "exploration_experience_information_distribution_weighted_mean": weighted_mean(
                self.exploration_experience_information
            ),
            "viability_reserve_distribution_weighted_mean": weighted_mean(self.viability_reserve),
            "route_support_distribution_weighted_mean": weighted_mean(self.route_support),
            "maintenance_cost_distribution_weighted_mean": weighted_mean(self.maintenance_cost),
            "net_viability_value_distribution_weighted_mean": weighted_mean(self.net_viability_value),
            "negative_viability_pressure_distribution_weighted_mean": weighted_mean(self.negative_viability_pressure),
            "support_erosion_distribution_weighted_mean": weighted_mean(self.support_erosion),
            "released_mass_distribution_weighted_mean": weighted_mean(self.released_mass),
            "release_reallocation_flow_distribution_weighted_mean": weighted_mean(self.release_reallocation_flow),
        }
        self._terrain_trace[-1].update(optimization_row)
        self._auxiliary_trace[-1].update(optimization_row)
