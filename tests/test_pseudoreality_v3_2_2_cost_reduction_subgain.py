from __future__ import annotations

from pathlib import Path

import numpy as np

from pseudo_reality.distribution_terrain_v3_2_2 import DistributionTerrainV322Config, DistributionTerrainV322World
from scripts.pseudoreality_v3_2_2_equilibrium_cost_reduction_validation import (
    compact_readout,
    export_equilibrium_cost_reduction_validation,
)


def test_v3_2_2_declares_weak_cost_reduction_subgain() -> None:
    config = DistributionTerrainV322Config(seed=0)
    assert config.cost_reduction_gain_weight == 0.10

    world = DistributionTerrainV322World(config)
    for _ in range(4):
        world.step()

    assert hasattr(world, "cost_reduction_gain")
    assert hasattr(world, "cost_reduction_preference")
    assert hasattr(world, "effective_medium_payoff")
    assert float(world.cost_reduction_gain.min()) >= 0.0
    assert float(world.cost_reduction_preference.max()) <= 0.10 + 1e-12
    assert np.all(world.effective_medium_payoff >= world.medium_payoff)

    terrain = world.emit_trace()["v3_2_2_internal_terrain_trace"]
    for column in (
        "operating_cost_distribution_weighted_mean",
        "cost_reduction_gain_distribution_weighted_mean",
        "cost_reduction_preference_distribution_weighted_mean",
        "effective_medium_payoff_distribution_weighted_mean",
    ):
        assert column in terrain.columns


def test_v3_2_2_equilibrium_pinpoint_validation_exports_expected_readouts(tmp_path: Path) -> None:
    by_model, comparison, aggregate = export_equilibrium_cost_reduction_validation(
        tmp_path,
        seeds=(0,),
        steps=10,
    )

    assert set(by_model["model"]) == {"v3.2", "v3.2.2"}
    assert set(comparison["scenario"]) == {
        "gentle_growth_equilibrium",
        "stable_equilibrium",
        "shrinking_equilibrium",
    }
    assert "delta_final_operating_cost" in comparison.columns
    assert "v322_final_cost_reduction_gain" in comparison.columns
    assert "delta_final_effective_medium_payoff" in comparison.columns
    assert float(comparison["v322_final_cost_reduction_gain"].min()) >= 0.0
    assert not aggregate.empty
    assert not compact_readout(aggregate).empty

    assert (tmp_path / "v3_2_2_equilibrium_cost_reduction_by_model.csv").exists()
    assert (tmp_path / "v3_2_2_equilibrium_cost_reduction_comparison.csv").exists()
    assert (tmp_path / "v3_2_2_equilibrium_cost_reduction_aggregate.csv").exists()
