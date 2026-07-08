"""Lightweight scenario validation runner for PseudoReality v3.

The runner is diagnostic-only: it applies external-factor schedules to the
internal distribution-terrain world and summarizes numeric traces. It does not
connect to G_t, O_t, DEPT internals, public observations, action modules, or
individual player/entity models.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from pseudo_reality.distribution_terrain_v3 import DistributionTerrainV3Config, DistributionTerrainV3World


BASELINE_EXTERNAL_FACTORS = {
    "external_resource_supply": 0.0,
    "external_demand": 0.0,
    "external_competition_pressure": 0.0,
    "external_information_noise": 0.0,
    "external_shock": 0.0,
    "external_constraint_pressure": 0.0,
}


DISTRIBUTION_WEIGHTED_TERRAIN_COLUMNS = (
    "short_payoff_distribution_weighted_mean",
    "medium_payoff_distribution_weighted_mean",
    "short_medium_gap_distribution_weighted_mean",
    "friction_distribution_weighted_mean",
    "viscosity_distribution_weighted_mean",
    "damage_distribution_weighted_mean",
    "rigidity_distribution_weighted_mean",
    "recovery_speed_distribution_weighted_mean",
    "composite_payoff_distribution_weighted_mean",
)


@dataclass(frozen=True)
class ScenarioPhase:
    start: int
    end: int
    external_factors: dict[str, float]


@dataclass(frozen=True)
class ScenarioSpec:
    name: str
    seed: int = 0
    steps: int = 30
    phases: tuple[ScenarioPhase, ...] = ()
    initial_center: tuple[float, ...] | None = None
    initial_width: float = 0.08


@dataclass(frozen=True)
class ScenarioResult:
    spec: ScenarioSpec
    summary: dict[str, float | int | str]
    traces: dict[str, pd.DataFrame]


def make_static_scenario(
    name: str,
    external_factors: dict[str, float],
    *,
    seed: int = 0,
    steps: int = 30,
    initial_center: tuple[float, ...] | None = None,
    initial_width: float = 0.08,
) -> ScenarioSpec:
    return ScenarioSpec(
        name=name,
        seed=seed,
        steps=steps,
        phases=(ScenarioPhase(start=0, end=steps, external_factors=dict(external_factors)),),
        initial_center=initial_center,
        initial_width=initial_width,
    )


def default_scenario_specs(*, seed: int = 0, steps: int = 30) -> tuple[ScenarioSpec, ...]:
    compound_shock = {
        "external_resource_supply": -0.8,
        "external_demand": 0.8,
        "external_competition_pressure": 0.8,
        "external_information_noise": 0.8,
        "external_shock": 1.0,
        "external_constraint_pressure": 0.8,
    }
    relief = {
        "external_resource_supply": 0.4,
        "external_demand": 0.2,
        "external_competition_pressure": 0.0,
        "external_information_noise": 0.1,
        "external_shock": 0.0,
        "external_constraint_pressure": 0.1,
    }
    midpoint = steps // 2
    return (
        make_static_scenario("baseline", BASELINE_EXTERNAL_FACTORS, seed=seed, steps=steps),
        make_static_scenario(
            "resource_scarcity",
            {
                "external_resource_supply": -1.0,
                "external_demand": 0.4,
                "external_competition_pressure": 0.3,
                "external_information_noise": 0.1,
                "external_shock": 0.0,
                "external_constraint_pressure": 0.2,
            },
            seed=seed,
            steps=steps,
        ),
        make_static_scenario(
            "high_pressure_competition",
            {
                "external_resource_supply": -0.3,
                "external_demand": 0.7,
                "external_competition_pressure": 1.0,
                "external_information_noise": 0.2,
                "external_shock": 0.0,
                "external_constraint_pressure": 0.2,
            },
            seed=seed,
            steps=steps,
        ),
        make_static_scenario(
            "information_noise_constraint",
            {
                "external_resource_supply": 0.0,
                "external_demand": 0.2,
                "external_competition_pressure": 0.3,
                "external_information_noise": 1.0,
                "external_shock": 0.0,
                "external_constraint_pressure": 0.8,
            },
            seed=seed,
            steps=steps,
        ),
        make_static_scenario("compound_shock", compound_shock, seed=seed, steps=steps),
        ScenarioSpec(
            name="shock_then_relief",
            seed=seed,
            steps=steps,
            phases=(
                ScenarioPhase(start=0, end=midpoint, external_factors=compound_shock),
                ScenarioPhase(start=midpoint, end=steps, external_factors=relief),
            ),
        ),
    )


def stable_scenario_specs(*, seed: int = 0, steps: int = 30) -> tuple[ScenarioSpec, ...]:
    stable_support = {
        "external_resource_supply": 0.7,
        "external_demand": 0.1,
        "external_competition_pressure": 0.0,
        "external_information_noise": 0.0,
        "external_shock": 0.0,
        "external_constraint_pressure": 0.0,
    }
    mild_stress = {
        "external_resource_supply": -0.2,
        "external_demand": 0.2,
        "external_competition_pressure": 0.2,
        "external_information_noise": 0.2,
        "external_shock": 0.0,
        "external_constraint_pressure": 0.1,
    }
    midpoint = steps // 2
    return (
        make_static_scenario(
            "stable_resource_support",
            stable_support,
            seed=seed,
            steps=steps,
        ),
        make_static_scenario(
            "stable_high_information",
            stable_support,
            seed=seed,
            steps=steps,
            initial_center=(0.65, 0.85, 0.35, 0.70, 0.80),
            initial_width=0.06,
        ),
        make_static_scenario(
            "stable_low_pressure_reversible",
            stable_support,
            seed=seed,
            steps=steps,
            initial_center=(0.60, 0.75, 0.25, 0.70, 0.90),
            initial_width=0.06,
        ),
        ScenarioSpec(
            name="mild_stress_then_stable_support",
            seed=seed,
            steps=steps,
            phases=(
                ScenarioPhase(start=0, end=midpoint, external_factors=mild_stress),
                ScenarioPhase(start=midpoint, end=steps, external_factors=stable_support),
            ),
            initial_center=(0.55, 0.65, 0.40, 0.60, 0.70),
            initial_width=0.07,
        ),
    )


def _effective_phases(spec: ScenarioSpec) -> tuple[ScenarioPhase, ...]:
    if not spec.phases:
        return (ScenarioPhase(start=0, end=spec.steps, external_factors=BASELINE_EXTERNAL_FACTORS),)
    return spec.phases


def _validate_phases(spec: ScenarioSpec) -> tuple[ScenarioPhase, ...]:
    if spec.steps < 0:
        raise ValueError("steps must be non-negative")
    if spec.initial_center is not None and len(spec.initial_center) != len(DistributionTerrainV3Config().axes):
        raise ValueError("initial_center must match the five PseudoReality v3 axes")
    if spec.initial_width <= 0.0:
        raise ValueError("initial_width must be positive")
    phases = _effective_phases(spec)
    previous_end = -1
    for phase in phases:
        if phase.start < 0:
            raise ValueError("scenario phase start must be >= 0")
        if phase.end <= phase.start:
            raise ValueError("scenario phase end must be greater than start")
        if phase.start < previous_end:
            raise ValueError("scenario phases must be sorted and non-overlapping")
        if phase.end > spec.steps:
            raise ValueError("scenario phases must fit within steps")
        previous_end = phase.end
    return phases


def _external_factors_for_step(phases: tuple[ScenarioPhase, ...], t: int) -> dict[str, float]:
    for phase in phases:
        if phase.start <= t < phase.end:
            return phase.external_factors
    return BASELINE_EXTERNAL_FACTORS


def _replace_initial_distribution(world: DistributionTerrainV3World, spec: ScenarioSpec) -> None:
    if spec.initial_center is None:
        return
    coords = world._coordinate_grids()
    center = tuple(float(np.clip(value, 0.0, 1.0)) for value in spec.initial_center)
    squared_radius = sum((coord - center_value) ** 2 for coord, center_value in zip(coords, center, strict=True))
    world.distribution = np.exp(-squared_radius / max(float(spec.initial_width), 1e-9))
    world._normalize_distribution()
    world._distribution_trace = []
    world._terrain_trace = []
    world._flow_trace = []
    world._external_trace = []
    world._auxiliary_trace = []
    world._record_trace(total_flow=0.0, stay_mass=float(world.distribution.sum()))


def _distribution_weighted_terrain_row(world: DistributionTerrainV3World) -> dict[str, float | int | str]:
    distribution = world.distribution

    def weighted_mean(value: Any) -> float:
        return float((distribution * value).sum())

    short_medium_gap = abs(world.short_payoff - world.medium_payoff)
    composite_payoff = (
        world.config.short_term_weight * world.short_payoff
        + world.config.medium_term_weight * world.medium_payoff
        - world.friction
    )
    return {
        "t": world.t,
        "scenario": world.config.scenario,
        "seed": world.config.seed,
        "short_payoff_distribution_weighted_mean": weighted_mean(world.short_payoff),
        "medium_payoff_distribution_weighted_mean": weighted_mean(world.medium_payoff),
        "short_medium_gap_distribution_weighted_mean": weighted_mean(short_medium_gap),
        "friction_distribution_weighted_mean": weighted_mean(world.friction),
        "viscosity_distribution_weighted_mean": weighted_mean(world.viscosity),
        "damage_distribution_weighted_mean": weighted_mean(world.damage),
        "rigidity_distribution_weighted_mean": weighted_mean(world.rigidity),
        "recovery_speed_distribution_weighted_mean": weighted_mean(world.recovery_speed),
        "composite_payoff_distribution_weighted_mean": weighted_mean(composite_payoff),
    }


def _first_last_delta(summary: dict[str, Any], prefix: str, frame: pd.DataFrame, column: str) -> None:
    initial = float(frame[column].iloc[0])
    final = float(frame[column].iloc[-1])
    summary[f"initial_{prefix}"] = initial
    summary[f"final_{prefix}"] = final
    summary[f"delta_{prefix}"] = final - initial


def _build_summary(spec: ScenarioSpec, traces: dict[str, pd.DataFrame]) -> dict[str, float | int | str]:
    distribution = traces["v3_internal_distribution_trace"]
    flow = traces["v3_internal_flow_trace"]
    terrain = traces["v3_internal_terrain_trace"]
    weighted_terrain = traces["v3_internal_distribution_weighted_terrain_trace"]
    external = traces["v3_internal_external_trace"]
    summary: dict[str, float | int | str] = {"scenario": spec.name, "seed": spec.seed, "steps": spec.steps}

    _first_last_delta(summary, "entropy", distribution, "entropy")
    _first_last_delta(summary, "max_mass", distribution, "max_mass")
    _first_last_delta(summary, "concentration", flow, "concentration")
    summary["total_moved_mass_sum"] = float(flow["moved_mass"].sum())
    summary["mean_total_flow"] = float(flow["total_flow"].mean())
    summary["final_total_flow"] = float(flow["total_flow"].iloc[-1])

    for column in (
        "short_payoff_mean",
        "medium_payoff_mean",
        "friction_mean",
        "viscosity_mean",
        "damage_mean",
        "rigidity_mean",
        "recovery_speed_mean",
    ):
        _first_last_delta(summary, column, terrain, column)

    for column in DISTRIBUTION_WEIGHTED_TERRAIN_COLUMNS:
        _first_last_delta(summary, column, weighted_terrain, column)

    summary["max_threshold_activation_strength"] = float(terrain["threshold_activation_strength"].max())
    summary["final_threshold_activation_strength"] = float(terrain["threshold_activation_strength"].iloc[-1])
    weighted_column = "distribution_weighted_threshold_activation_strength"
    summary[f"max_{weighted_column}"] = float(terrain[weighted_column].max())
    summary[f"final_{weighted_column}"] = float(terrain[weighted_column].iloc[-1])
    summary["max_external_deformation_strength"] = float(external["external_deformation_strength"].max())
    summary["final_external_deformation_strength"] = float(external["external_deformation_strength"].iloc[-1])
    return summary


def run_scenario(spec: ScenarioSpec) -> ScenarioResult:
    phases = _validate_phases(spec)
    world = DistributionTerrainV3World(DistributionTerrainV3Config(seed=spec.seed, scenario=spec.name))
    _replace_initial_distribution(world, spec)
    weighted_terrain_rows = [_distribution_weighted_terrain_row(world)]
    for t in range(spec.steps):
        world.set_external_factors(_external_factors_for_step(phases, t))
        world.step()
        weighted_terrain_rows.append(_distribution_weighted_terrain_row(world))
    traces = world.emit_trace()
    traces["v3_internal_distribution_weighted_terrain_trace"] = pd.DataFrame(weighted_terrain_rows)
    return ScenarioResult(spec=spec, summary=_build_summary(spec, traces), traces=traces)


def run_scenario_suite(specs: tuple[ScenarioSpec, ...] | list[ScenarioSpec]) -> tuple[pd.DataFrame, dict[str, dict[str, pd.DataFrame]]]:
    results = [run_scenario(spec) for spec in specs]
    summary = pd.DataFrame([result.summary for result in results])
    traces_by_scenario = {result.spec.name: result.traces for result in results}
    return summary, traces_by_scenario


def run_default_scenario_suite(*, seed: int = 0, steps: int = 30) -> tuple[pd.DataFrame, dict[str, dict[str, pd.DataFrame]]]:
    return run_scenario_suite(default_scenario_specs(seed=seed, steps=steps))


def run_stable_scenario_suite(*, seed: int = 0, steps: int = 30) -> tuple[pd.DataFrame, dict[str, dict[str, pd.DataFrame]]]:
    return run_scenario_suite(stable_scenario_specs(seed=seed, steps=steps))
