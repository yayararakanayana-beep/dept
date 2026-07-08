"""Typical-pattern scenario suite for PseudoReality v3 validation.

This module defines diagnostic-only scenario schedules. It does not add
phenomenon flags, does not change PseudoReality v3 dynamics, and does not
connect to G_t, O_t, DEPT internals, public observations, action modules, or
individual player/entity models.
"""

from __future__ import annotations

import pandas as pd

from pseudo_reality.distribution_terrain_v3_scenarios import (
    ScenarioPhase,
    ScenarioSpec,
    make_static_scenario,
    run_scenario_suite,
)


COMPOUND_SHOCK_FACTORS = {
    "external_resource_supply": -0.8,
    "external_demand": 0.8,
    "external_competition_pressure": 0.8,
    "external_information_noise": 0.8,
    "external_shock": 1.0,
    "external_constraint_pressure": 0.8,
}

NO_SUPPORT_AFTER_SHOCK_FACTORS = {
    "external_resource_supply": 0.0,
    "external_demand": 0.3,
    "external_competition_pressure": 0.3,
    "external_information_noise": 0.3,
    "external_shock": 0.0,
    "external_constraint_pressure": 0.3,
}

WEAK_SUPPORT_AFTER_SHOCK_FACTORS = {
    "external_resource_supply": 0.3,
    "external_demand": 0.2,
    "external_competition_pressure": 0.1,
    "external_information_noise": 0.15,
    "external_shock": 0.0,
    "external_constraint_pressure": 0.15,
}

STRONG_SUPPORT_AFTER_SHOCK_FACTORS = {
    "external_resource_supply": 0.8,
    "external_demand": 0.1,
    "external_competition_pressure": 0.0,
    "external_information_noise": 0.0,
    "external_shock": 0.0,
    "external_constraint_pressure": 0.0,
}


def typical_pattern_scenario_specs(*, seed: int = 0, steps: int = 30) -> tuple[ScenarioSpec, ...]:
    """Return lightweight typical-pattern scenarios for 30-step validation."""

    shock_end = max(1, steps // 3)
    boom_end = max(1, (steps * 2) // 3)
    return (
        make_static_scenario(
            "constrained_low_reversibility_stability",
            {
                "external_resource_supply": 0.2,
                "external_demand": 0.1,
                "external_competition_pressure": 0.1,
                "external_information_noise": 0.0,
                "external_shock": 0.0,
                "external_constraint_pressure": 0.9,
            },
            seed=seed,
            steps=steps,
            initial_center=(0.55, 0.70, 0.30, 0.20, 0.20),
            initial_width=0.06,
        ),
        ScenarioSpec(
            name="frontier_boom_then_tightening",
            seed=seed,
            steps=steps,
            phases=(
                ScenarioPhase(
                    start=0,
                    end=boom_end,
                    external_factors={
                        "external_resource_supply": 0.8,
                        "external_demand": 1.0,
                        "external_competition_pressure": 0.7,
                        "external_information_noise": 0.2,
                        "external_shock": 0.0,
                        "external_constraint_pressure": 0.1,
                    },
                ),
                ScenarioPhase(
                    start=boom_end,
                    end=steps,
                    external_factors={
                        "external_resource_supply": -0.6,
                        "external_demand": 0.8,
                        "external_competition_pressure": 1.0,
                        "external_information_noise": 0.4,
                        "external_shock": 0.2,
                        "external_constraint_pressure": 0.3,
                    },
                ),
            ),
            initial_center=(0.75, 0.55, 0.65, 0.55, 0.45),
            initial_width=0.05,
        ),
        ScenarioSpec(
            name="shock_recovery_no_support",
            seed=seed,
            steps=steps,
            phases=(
                ScenarioPhase(start=0, end=shock_end, external_factors=COMPOUND_SHOCK_FACTORS),
                ScenarioPhase(start=shock_end, end=steps, external_factors=NO_SUPPORT_AFTER_SHOCK_FACTORS),
            ),
        ),
        ScenarioSpec(
            name="shock_recovery_weak_support",
            seed=seed,
            steps=steps,
            phases=(
                ScenarioPhase(start=0, end=shock_end, external_factors=COMPOUND_SHOCK_FACTORS),
                ScenarioPhase(start=shock_end, end=steps, external_factors=WEAK_SUPPORT_AFTER_SHOCK_FACTORS),
            ),
        ),
        ScenarioSpec(
            name="shock_recovery_strong_support",
            seed=seed,
            steps=steps,
            phases=(
                ScenarioPhase(start=0, end=shock_end, external_factors=COMPOUND_SHOCK_FACTORS),
                ScenarioPhase(start=shock_end, end=steps, external_factors=STRONG_SUPPORT_AFTER_SHOCK_FACTORS),
            ),
        ),
        make_static_scenario(
            "mild_stress_accumulation",
            {
                "external_resource_supply": -0.25,
                "external_demand": 0.3,
                "external_competition_pressure": 0.3,
                "external_information_noise": 0.2,
                "external_shock": 0.0,
                "external_constraint_pressure": 0.2,
            },
            seed=seed,
            steps=steps,
            initial_center=(0.55, 0.60, 0.40, 0.50, 0.60),
            initial_width=0.07,
        ),
    )


def run_typical_pattern_scenario_suite(*, seed: int = 0, steps: int = 30) -> tuple[pd.DataFrame, dict[str, dict[str, pd.DataFrame]]]:
    """Run the typical-pattern scenario suite."""

    return run_scenario_suite(typical_pattern_scenario_specs(seed=seed, steps=steps))
