"""PseudoReality v3.2.2 cost-reduction subgain terrain world.

v3.2.2 keeps v3.2's expected-value exploration and release dynamics, then
adds one deliberately small preference: when ordinary payoff differences are
small, lower operating cost can become attractive. Cost reduction is not the
main payoff route. It is treated as a weak subgain with weight 0.10, so strong
ordinary payoff growth should still dominate.

The module does not add phenomenon flags, action modules, G_t/O_t/DEPT
connections, public observations, or individual players.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from pseudo_reality.distribution_terrain_v3_2 import DistributionTerrainV32Config, DistributionTerrainV32World


@dataclass(frozen=True)
class DistributionTerrainV322Config(DistributionTerrainV32Config):
    """Configuration for the v3.2.2 weak cost-reduction subgain route."""

    scenario: str = "distribution_terrain_v3_2_2_cost_reduction_subgain"

    cost_reduction_gain_weight: float = 0.10
    viscosity_cost_weight: float = 0.35
    maintenance_cost_weight: float = 0.25
    cost_reduction_friction_rate: float = 0.025
    cost_reduction_viscosity_rate: float = 0.015
    cost_reduction_medium_rate: float = 0.020


class DistributionTerrainV322World(DistributionTerrainV32World):
    """v3.2.2 terrain world with weak cost-reduction-as-subgain behavior."""

    config: DistributionTerrainV322Config

    def __init__(self, config: DistributionTerrainV322Config | None = None) -> None:
        super().__init__(config or DistributionTerrainV322Config())

    def reset(self) -> None:
        self.operating_cost = np.zeros(self.shape, dtype=float)
        self.cost_reduction_gain = np.zeros(self.shape, dtype=float)
        self.cost_reduction_preference = np.zeros(self.shape, dtype=float)
        self.effective_medium_payoff = np.zeros(self.shape, dtype=float)
        super().reset()
        self._update_cost_reduction_fields(self._learning_quality())
        if self._terrain_trace:
            cost_row = self._cost_reduction_trace_row()
            self._terrain_trace[-1].update(cost_row)
            self._auxiliary_trace[-1].update(cost_row)

    def emit_trace(self) -> dict[str, Any]:
        return {
            "v3_2_2_internal_distribution_trace": pd.DataFrame(self._distribution_trace),
            "v3_2_2_internal_terrain_trace": pd.DataFrame(self._terrain_trace),
            "v3_2_2_internal_flow_trace": pd.DataFrame(self._flow_trace),
            "v3_2_2_internal_external_trace": pd.DataFrame(self._external_trace),
            "v3_2_2_internal_auxiliary_trace": pd.DataFrame(self._auxiliary_trace),
        }

    def _raw_operating_cost(self) -> np.ndarray:
        return np.clip(
            self.friction
            + self.config.viscosity_cost_weight * self.viscosity
            + self.config.maintenance_cost_weight * self.maintenance_cost,
            0.0,
            2.0,
        )

    def _update_cost_reduction_fields(self, learning_quality: np.ndarray) -> None:
        self.operating_cost = self._raw_operating_cost()
        current_route_cost = float(np.sum(self.distribution * self.operating_cost))
        cost_reduction_room = np.maximum(current_route_cost - self.operating_cost, 0.0)
        support_gate = 0.30 + 0.70 * self.route_support
        learning_gate = 0.40 + 0.60 * learning_quality
        self.cost_reduction_gain = np.clip(cost_reduction_room * support_gate * learning_gate, 0.0, 1.0)
        self.cost_reduction_preference = np.clip(
            self.config.cost_reduction_gain_weight * self.cost_reduction_gain,
            0.0,
            1.0,
        )
        self.effective_medium_payoff = np.clip(self.medium_payoff + self.cost_reduction_preference, 0.0, 1.5)

    def _composite_payoff(self) -> np.ndarray:
        # Cost reduction is a weak subgain. Strong ordinary payoff differences and
        # the existing exploration expected-value term remain dominant.
        return np.clip(
            self._base_composite_payoff()
            + self.config.exploration_option_bonus_rate * self.expected_value_advantage
            + self.cost_reduction_preference,
            -1.0,
            1.5,
        )

    def _deform_terrain(self, inbound_flow: np.ndarray) -> None:
        super()._deform_terrain(inbound_flow)
        learning_quality = self._learning_quality()
        self._update_cost_reduction_fields(learning_quality)

        # The subgain can slowly reduce actual operating costs, but the rate is
        # deliberately small. If ordinary payoff is falling sharply, this weak
        # term should not be enough to rescue the route by itself.
        self.friction = np.clip(
            self.friction - self.config.cost_reduction_friction_rate * self.cost_reduction_gain,
            0.0,
            0.95,
        )
        self.viscosity = np.clip(
            self.viscosity - self.config.cost_reduction_viscosity_rate * self.cost_reduction_gain,
            0.0,
            0.95,
        )
        self.medium_payoff = np.clip(
            self.medium_payoff
            + self.config.cost_reduction_medium_rate * self.cost_reduction_gain * learning_quality,
            0.0,
            1.5,
        )
        self._update_cost_reduction_fields(learning_quality)
        self.previous_total_gain = self._distribution_weighted_base_composite()

    def _cost_reduction_trace_row(self) -> dict[str, float]:
        distribution = self.distribution

        def weighted_mean(value: np.ndarray) -> float:
            return float(np.sum(distribution * value))

        return {
            "operating_cost_mean": float(self.operating_cost.mean()),
            "cost_reduction_gain_mean": float(self.cost_reduction_gain.mean()),
            "cost_reduction_preference_mean": float(self.cost_reduction_preference.mean()),
            "effective_medium_payoff_mean": float(self.effective_medium_payoff.mean()),
            "operating_cost_distribution_weighted_mean": weighted_mean(self.operating_cost),
            "cost_reduction_gain_distribution_weighted_mean": weighted_mean(self.cost_reduction_gain),
            "cost_reduction_preference_distribution_weighted_mean": weighted_mean(
                self.cost_reduction_preference
            ),
            "effective_medium_payoff_distribution_weighted_mean": weighted_mean(self.effective_medium_payoff),
        }

    def _record_trace(self, total_flow: float, stay_mass: float) -> None:
        super()._record_trace(total_flow=total_flow, stay_mass=stay_mass)
        cost_row = self._cost_reduction_trace_row()
        self._terrain_trace[-1].update(cost_row)
        self._auxiliary_trace[-1].update(cost_row)


__all__ = ["DistributionTerrainV322Config", "DistributionTerrainV322World"]
