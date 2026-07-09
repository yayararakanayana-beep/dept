from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pseudo_reality.distribution_terrain_v3 import DistributionTerrainV3World
from pseudo_reality.distribution_terrain_v3_2 import DistributionTerrainV32Config, DistributionTerrainV32World
from pseudo_reality.distribution_terrain_v3_2_scenarios import run_default_scenario_suite, run_stable_scenario_suite
from scripts.pseudoreality_v3_2_long_horizon_comparison import V32_EXTRA_METRICS


def test_v3_2_world_keeps_v3_world_separate():
    v3_world = DistributionTerrainV3World()
    v32_world = DistributionTerrainV32World()

    assert not hasattr(v3_world, "information_memory")
    assert not hasattr(v3_world, "expected_value_advantage")
    assert not hasattr(v3_world, "exploration_cost")
    assert not hasattr(v3_world, "route_support")
    assert hasattr(v32_world, "information_memory")
    assert hasattr(v32_world, "expected_value_advantage")
    assert hasattr(v32_world, "exploration_cost")
    assert hasattr(v32_world, "route_support")
    assert hasattr(v32_world, "released_mass")
    assert isinstance(v32_world.config, DistributionTerrainV32Config)


def test_v3_2_world_records_expected_value_and_release_metrics_after_step():
    world = DistributionTerrainV32World()
    world.set_external_factors(
        {
            "external_resource_supply": -0.6,
            "external_demand": 0.8,
            "external_competition_pressure": 0.8,
            "external_information_noise": 0.4,
            "external_shock": 0.0,
            "external_constraint_pressure": 0.4,
        }
    )
    world.step()
    traces = world.emit_trace()
    terrain = traces["v3_2_internal_terrain_trace"]

    assert "existing_path_expected_value_distribution_weighted_mean" in terrain.columns
    assert "exploration_cost_distribution_weighted_mean" in terrain.columns
    assert "exploration_net_expected_value_distribution_weighted_mean" in terrain.columns
    assert "expected_value_advantage_distribution_weighted_mean" in terrain.columns
    assert "information_memory_distribution_weighted_mean" in terrain.columns
    assert "short_path_decline_information_distribution_weighted_mean" in terrain.columns
    assert "exploration_experience_information_distribution_weighted_mean" in terrain.columns
    assert "viability_reserve_distribution_weighted_mean" in terrain.columns
    assert "route_support_distribution_weighted_mean" in terrain.columns
    assert "negative_viability_pressure_distribution_weighted_mean" in terrain.columns
    assert "released_mass_sum" in terrain.columns
    assert terrain["exploration_cost_distribution_weighted_mean"].iloc[-1] >= 0.0
    assert terrain["expected_value_advantage_distribution_weighted_mean"].iloc[-1] >= 0.0
    assert terrain["information_memory_distribution_weighted_mean"].iloc[-1] >= 0.0
    assert terrain["route_support_distribution_weighted_mean"].iloc[-1] >= 0.0
    assert terrain["released_mass_sum"].iloc[-1] >= 0.0


def test_v3_2_scenario_suites_return_expected_columns():
    default_summary, _default_traces = run_default_scenario_suite(seed=0, steps=2)
    stable_summary, _stable_traces = run_stable_scenario_suite(seed=0, steps=2)

    assert not default_summary.empty
    assert not stable_summary.empty
    for table in (default_summary, stable_summary):
        assert "final_existing_path_expected_value_distribution_weighted_mean" in table.columns
        assert "final_exploration_cost_distribution_weighted_mean" in table.columns
        assert "final_expected_value_advantage_distribution_weighted_mean" in table.columns
        assert "final_information_memory_distribution_weighted_mean" in table.columns
        assert "final_route_support_distribution_weighted_mean" in table.columns
        assert "final_released_mass_sum" in table.columns
        assert "final_total_flow" in table.columns


def test_v3_2_comparison_declares_expected_value_and_release_extra_metrics():
    assert "final_existing_path_expected_value_distribution_weighted_mean" in V32_EXTRA_METRICS
    assert "final_exploration_cost_distribution_weighted_mean" in V32_EXTRA_METRICS
    assert "final_expected_value_advantage_distribution_weighted_mean" in V32_EXTRA_METRICS
    assert "final_information_memory_distribution_weighted_mean" in V32_EXTRA_METRICS
    assert "final_route_support_distribution_weighted_mean" in V32_EXTRA_METRICS
    assert "final_released_mass_sum" in V32_EXTRA_METRICS
