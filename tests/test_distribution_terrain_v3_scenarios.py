from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from pseudo_reality.distribution_terrain_v3_scenarios import (
    default_scenario_specs,
    make_static_scenario,
    run_default_scenario_suite,
    run_scenario,
)


FORBIDDEN_PHENOMENON_FLAGS = (
    "shrinking_equilibrium_flag",
    "exploration_decline_flag",
    "goodhart_flag",
    "collapse_flag",
    "information_degradation_flag",
    "collapse_detected",
    "goodhart_detected",
    "shrinking_equilibrium_detected",
    "exploration_decline_detected",
    "information_degradation_detected",
)


REQUIRED_SUMMARY_COLUMNS = {
    "scenario",
    "seed",
    "steps",
    "initial_entropy",
    "final_entropy",
    "delta_entropy",
    "initial_max_mass",
    "final_max_mass",
    "delta_max_mass",
    "initial_concentration",
    "final_concentration",
    "delta_concentration",
    "total_moved_mass_sum",
    "mean_total_flow",
    "final_total_flow",
    "initial_short_payoff_mean",
    "final_short_payoff_mean",
    "delta_short_payoff_mean",
    "initial_medium_payoff_mean",
    "final_medium_payoff_mean",
    "delta_medium_payoff_mean",
    "initial_friction_mean",
    "final_friction_mean",
    "delta_friction_mean",
    "initial_viscosity_mean",
    "final_viscosity_mean",
    "delta_viscosity_mean",
    "initial_damage_mean",
    "final_damage_mean",
    "delta_damage_mean",
    "initial_rigidity_mean",
    "final_rigidity_mean",
    "delta_rigidity_mean",
    "initial_recovery_speed_mean",
    "final_recovery_speed_mean",
    "delta_recovery_speed_mean",
    "max_threshold_activation_strength",
    "final_threshold_activation_strength",
    "max_distribution_weighted_threshold_activation_strength",
    "final_distribution_weighted_threshold_activation_strength",
    "max_external_deformation_strength",
    "final_external_deformation_strength",
}


def test_distribution_terrain_v3_default_scenario_specs_include_required_scenarios():
    names = {spec.name for spec in default_scenario_specs(seed=0, steps=5)}
    assert {
        "baseline",
        "resource_scarcity",
        "high_pressure_competition",
        "information_noise_constraint",
        "compound_shock",
    } <= names


def test_distribution_terrain_v3_run_scenario_returns_summary_and_traces():
    spec = make_static_scenario(
        "test_resource_scarcity",
        {
            "external_resource_supply": -1.0,
            "external_demand": 0.4,
            "external_competition_pressure": 0.3,
            "external_information_noise": 0.1,
            "external_shock": 0.0,
            "external_constraint_pressure": 0.2,
        },
        seed=0,
        steps=5,
    )

    result = run_scenario(spec)

    assert result.summary["scenario"] == "test_resource_scarcity"
    assert result.summary["steps"] == 5
    assert set(result.traces) == {
        "v3_internal_distribution_trace",
        "v3_internal_terrain_trace",
        "v3_internal_flow_trace",
        "v3_internal_external_trace",
        "v3_internal_auxiliary_trace",
    }
    for frame in result.traces.values():
        assert isinstance(frame, pd.DataFrame)
        assert not frame.empty


def test_distribution_terrain_v3_run_default_scenario_suite_returns_summary():
    summary, traces_by_scenario = run_default_scenario_suite(seed=0, steps=5)

    assert isinstance(summary, pd.DataFrame)
    assert not summary.empty
    assert {"baseline", "compound_shock"} <= set(summary["scenario"])
    assert {"baseline", "compound_shock"} <= set(traces_by_scenario)


def test_distribution_terrain_v3_scenario_summary_has_required_columns():
    summary, _ = run_default_scenario_suite(seed=0, steps=5)

    missing = REQUIRED_SUMMARY_COLUMNS - set(summary.columns)
    assert not missing, f"Missing columns: {sorted(missing)}"


def test_distribution_terrain_v3_scenario_module_has_no_phenomenon_flag_strings():
    module_text = Path("pseudo_reality/distribution_terrain_v3_scenarios.py").read_text(encoding="utf-8")

    for forbidden in FORBIDDEN_PHENOMENON_FLAGS:
        assert forbidden not in module_text
