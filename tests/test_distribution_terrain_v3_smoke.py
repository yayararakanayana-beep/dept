from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd
import pytest

from pseudo_reality.distribution_terrain_v3 import (
    DistributionTerrainV3Config,
    DistributionTerrainV3World,
)


FORBIDDEN_PHENOMENON_FLAGS = (
    "shrinking_equilibrium_flag",
    "exploration_decline_flag",
    "goodhart_flag",
    "collapse_flag",
    "information_degradation_flag",
)


TERRAIN_ARRAY_NAMES = (
    "short_payoff",
    "medium_payoff",
    "friction",
    "viscosity",
    "damage",
    "rigidity",
    "recovery_speed",
)


STRONG_EXTERNAL_FACTORS = {
    "external_resource_supply": -0.8,
    "external_competition_pressure": 0.7,
    "external_information_noise": 0.6,
    "external_shock": 0.4,
    "external_constraint_pressure": 0.5,
}


def assert_distribution_valid(world: DistributionTerrainV3World) -> None:
    assert np.all(np.isfinite(world.distribution))
    assert np.all(world.distribution >= 0.0)
    assert abs(float(world.distribution.sum()) - 1.0) < 1e-9


def assert_columns(frame: pd.DataFrame, expected: set[str]) -> None:
    missing = expected - set(frame.columns)
    assert not missing, f"Missing columns: {sorted(missing)}"


def test_distribution_terrain_v3_initializes_normalized_world():
    world = DistributionTerrainV3World(DistributionTerrainV3Config(seed=0))

    assert world.distribution.shape == (5, 5, 5, 5, 5)
    assert_distribution_valid(world)
    for name in TERRAIN_ARRAY_NAMES:
        assert getattr(world, name).shape == world.distribution.shape


def test_distribution_terrain_v3_steps_without_mass_breakage():
    world = DistributionTerrainV3World(DistributionTerrainV3Config(seed=0))

    for _ in range(10):
        world.step()
        assert_distribution_valid(world)

    assert world.t == 10


def test_distribution_terrain_v3_emit_trace_contract():
    world = DistributionTerrainV3World(DistributionTerrainV3Config(seed=0))
    for _ in range(3):
        world.step()

    trace = world.emit_trace()
    expected_keys = {
        "v3_internal_distribution_trace",
        "v3_internal_terrain_trace",
        "v3_internal_flow_trace",
        "v3_internal_external_trace",
        "v3_internal_auxiliary_trace",
    }
    assert expected_keys <= set(trace)

    for frame in trace.values():
        assert isinstance(frame, pd.DataFrame)
        assert not frame.empty

    assert_columns(
        trace["v3_internal_distribution_trace"],
        {
            "t",
            "scenario",
            "seed",
            "mass_sum",
            "entropy",
            "max_mass",
            "center_resource_slack",
            "center_information_quality",
            "center_pressure",
            "center_exploration_room",
            "center_reversibility",
            "spread_resource_slack",
            "spread_information_quality",
            "spread_pressure",
            "spread_exploration_room",
            "spread_reversibility",
        },
    )
    assert_columns(
        trace["v3_internal_terrain_trace"],
        {
            "t",
            "scenario",
            "seed",
            "short_payoff_mean",
            "medium_payoff_mean",
            "short_medium_gap_mean",
            "friction_mean",
            "viscosity_mean",
            "damage_mean",
            "rigidity_mean",
            "recovery_speed_mean",
            "threshold_activation_strength",
        },
    )
    assert_columns(
        trace["v3_internal_flow_trace"],
        {
            "t",
            "scenario",
            "seed",
            "total_flow",
            "mean_flow",
            "max_flow",
            "stay_mass",
            "moved_mass",
            "concentration",
        },
    )
    assert_columns(
        trace["v3_internal_external_trace"],
        {
            "t",
            "scenario",
            "seed",
            "external_resource_supply",
            "external_demand",
            "external_competition_pressure",
            "external_information_noise",
            "external_shock",
            "external_constraint_pressure",
            "external_deformation_strength",
        },
    )
    assert_columns(
        trace["v3_internal_auxiliary_trace"],
        {
            "t",
            "scenario",
            "seed",
            "damage_mean",
            "rigidity_mean",
            "friction_mean",
            "viscosity_mean",
            "recovery_speed_mean",
            "resource_low_activation_mean",
            "information_low_activation_mean",
            "pressure_high_activation_mean",
            "exploration_low_activation_mean",
            "damage_high_activation_mean",
            "rigidity_high_activation_mean",
            "threshold_activation_strength",
        },
    )


def test_distribution_terrain_v3_threshold_dynamics_activate():
    world = DistributionTerrainV3World(DistributionTerrainV3Config(seed=0))
    world.set_external_factors(
        {
            "external_resource_supply": -1.0,
            "external_competition_pressure": 1.0,
            "external_information_noise": 1.0,
            "external_shock": 1.0,
            "external_constraint_pressure": 1.0,
        }
    )

    for _ in range(8):
        world.step()
        assert_distribution_valid(world)

    trace = world.emit_trace()
    terrain = trace["v3_internal_terrain_trace"]
    auxiliary = trace["v3_internal_auxiliary_trace"]

    assert terrain["threshold_activation_strength"].max() > 0.0
    activation_columns = {
        "resource_low_activation_mean",
        "information_low_activation_mean",
        "pressure_high_activation_mean",
        "exploration_low_activation_mean",
        "damage_high_activation_mean",
        "rigidity_high_activation_mean",
    }
    assert_columns(auxiliary, activation_columns | {"threshold_activation_strength"})
    assert any(auxiliary[column].max() > 0.0 for column in activation_columns)


def test_distribution_terrain_v3_rejects_reordered_axes():
    DistributionTerrainV3World(DistributionTerrainV3Config(seed=0))

    with pytest.raises(ValueError):
        DistributionTerrainV3World(
            DistributionTerrainV3Config(
                axes=(
                    "information_quality",
                    "resource_slack",
                    "pressure",
                    "exploration_room",
                    "reversibility",
                )
            )
        )

    with pytest.raises(ValueError):
        DistributionTerrainV3World(
            DistributionTerrainV3Config(
                axes=(
                    "resource_slack",
                    "information_quality",
                    "pressure",
                    "exploration_room",
                    "wrong_axis",
                )
            )
        )


def test_distribution_terrain_v3_external_factor_api_contract():
    world = DistributionTerrainV3World(DistributionTerrainV3Config(seed=0))

    world.set_external_factors(
        {
            "external_shock": 5.0,
            "external_resource_supply": -5.0,
        }
    )
    assert world.external_factors["external_shock"] == 1.0
    assert world.external_factors["external_resource_supply"] == -1.0

    with pytest.raises(ValueError):
        world.set_external_factors({"unknown_factor": 0.5})


def test_distribution_terrain_v3_external_factors_deform_terrain():
    world = DistributionTerrainV3World(DistributionTerrainV3Config(seed=0))
    before = {name: getattr(world, name).copy() for name in TERRAIN_ARRAY_NAMES}

    world.set_external_factors(STRONG_EXTERNAL_FACTORS)
    world.step()

    external_trace = world.emit_trace()["v3_internal_external_trace"]
    assert external_trace["external_deformation_strength"].iloc[-1] > 0.0
    changed = [not np.allclose(before[name], getattr(world, name)) for name in TERRAIN_ARRAY_NAMES]
    assert sum(changed) > 1
    assert_distribution_valid(world)


def test_distribution_terrain_v3_external_factors_change_flow():
    default = DistributionTerrainV3World(DistributionTerrainV3Config(seed=123))
    external = DistributionTerrainV3World(DistributionTerrainV3Config(seed=123))
    external.set_external_factors(
        {
            "external_resource_supply": -0.9,
            "external_competition_pressure": 0.8,
            "external_information_noise": 0.7,
            "external_shock": 0.5,
            "external_constraint_pressure": 0.7,
        }
    )

    for _ in range(8):
        default.step()
        external.step()

    assert_distribution_valid(default)
    assert_distribution_valid(external)
    assert external.emit_trace()["v3_internal_external_trace"]["external_deformation_strength"].iloc[-1] > 0.0

    default_flow = default.emit_trace()["v3_internal_flow_trace"]["total_flow"].to_numpy()
    external_flow = external.emit_trace()["v3_internal_flow_trace"]["total_flow"].to_numpy()
    assert not (
        np.allclose(default.distribution, external.distribution)
        and np.allclose(default_flow, external_flow)
    )


def test_distribution_terrain_v3_has_no_phenomenon_flag_strings():
    module_text = Path("pseudo_reality/distribution_terrain_v3.py").read_text(encoding="utf-8")

    for forbidden in FORBIDDEN_PHENOMENON_FLAGS:
        assert forbidden not in module_text


def test_distribution_terrain_v3_config_json_loads():
    cfg = DistributionTerrainV3Config.from_json(
        "configs/world_profiles/pseudo_reality_v3_distribution_terrain.json"
    )

    assert cfg.external_deformation_rates is not None
    world = DistributionTerrainV3World(cfg)
    assert_distribution_valid(world)
