from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pseudo_reality.distribution_terrain_v3 import DistributionTerrainV3World
from pseudo_reality.distribution_terrain_v3_1 import DistributionTerrainV31Config, DistributionTerrainV31World
from pseudo_reality.distribution_terrain_v3_1_scenarios import run_default_scenario_suite, run_stable_scenario_suite
from scripts.pseudoreality_v3_1_long_horizon_comparison import V31_EXTRA_METRICS


def test_v3_1_world_keeps_v3_world_separate():
    v3_world = DistributionTerrainV3World()
    v31_world = DistributionTerrainV31World()

    assert not hasattr(v3_world, "residual_stress")
    assert not hasattr(v3_world, "stress_tolerance")
    assert hasattr(v31_world, "residual_stress")
    assert hasattr(v31_world, "stress_tolerance")
    assert isinstance(v31_world.config, DistributionTerrainV31Config)


def test_v3_1_world_records_circulation_metrics_after_step():
    world = DistributionTerrainV31World()
    world.set_external_factors(
        {
            "external_resource_supply": -0.8,
            "external_demand": 0.8,
            "external_competition_pressure": 0.8,
            "external_information_noise": 0.8,
            "external_shock": 1.0,
            "external_constraint_pressure": 0.8,
        }
    )
    world.step()
    traces = world.emit_trace()
    terrain = traces["v3_1_internal_terrain_trace"]

    assert "residual_stress_distribution_weighted_mean" in terrain.columns
    assert "nonproductive_stress_distribution_weighted_mean" in terrain.columns
    assert "stress_tolerance_distribution_weighted_mean" in terrain.columns
    assert "medium_path_memory_distribution_weighted_mean" in terrain.columns
    assert terrain["stress_load_distribution_weighted_mean"].iloc[-1] >= 0.0
    assert terrain["residual_stress_distribution_weighted_mean"].iloc[-1] >= 0.0
    assert 0.0 <= terrain["stress_tolerance_distribution_weighted_mean"].iloc[-1] <= 1.0


def test_v3_1_scenario_suites_return_expected_columns():
    default_summary, _default_traces = run_default_scenario_suite(seed=0, steps=2)
    stable_summary, _stable_traces = run_stable_scenario_suite(seed=0, steps=2)

    assert not default_summary.empty
    assert not stable_summary.empty
    for table in (default_summary, stable_summary):
        assert "final_residual_stress_distribution_weighted_mean" in table.columns
        assert "final_nonproductive_stress_distribution_weighted_mean" in table.columns
        assert "final_stress_tolerance_distribution_weighted_mean" in table.columns
        assert "final_medium_path_memory_distribution_weighted_mean" in table.columns
        assert "final_total_flow" in table.columns


def test_v3_1_comparison_declares_stress_tolerance_extra_metric():
    assert "final_stress_tolerance_distribution_weighted_mean" in V31_EXTRA_METRICS
