"""Scenario runner for PseudoReality v3.2.

This runner reuses the frozen v3 scenario specifications but runs them through
the separate v3.2 expected-value exploration-cost world. It is diagnostic-only
and does not connect to G_t/O_t/DEPT, action modules, or individual agents.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from pseudo_reality.distribution_terrain_v3_2 import DistributionTerrainV32Config, DistributionTerrainV32World
from pseudo_reality.distribution_terrain_v3_scenarios import (
    BASELINE_EXTERNAL_FACTORS,
    DISTRIBUTION_WEIGHTED_TERRAIN_COLUMNS,
    ScenarioPhase,
    ScenarioResult,
    ScenarioSpec,
    default_scenario_specs,
    make_static_scenario,
    stable_scenario_specs,
)


V32_DISTRIBUTION_WEIGHTED_TERRAIN_COLUMNS = DISTRIBUTION_WEIGHTED_TERRAIN_COLUMNS + (
    "existing_path_expected_value_distribution_weighted_mean",
    "exploration_cost_distribution_weighted_mean",
    "exploration_option_value_distribution_weighted_mean",
    "exploration_net_expected_value_distribution_weighted_mean",
    "expected_value_advantage_distribution_weighted_mean",
    "information_memory_distribution_weighted_mean",
    "short_gain_information_conversion_distribution_weighted_mean",
)


def _effective_phases(spec: ScenarioSpec) -> tuple[ScenarioPhase, ...]:
    if not spec.phases:
        return (ScenarioPhase(start=0, end=spec.steps, external_factors=BASELINE_EXTERNAL_FACTORS),)
    return spec.phases


def _validate_phases(spec: ScenarioSpec) -> tuple[ScenarioPhase, ...]:
    if spec.steps < 0:
        raise ValueError("steps must be non-negative")
    if spec.initial_center is not None and len(spec.initial_center) != len(DistributionTerrainV32Config().axes):
        raise ValueError("initial_center must match the five PseudoReality v3.2 axes")
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


def _replace_initial_distribution(world: DistributionTerrainV32World, spec: ScenarioSpec) -> None:
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
    world.previous_total_gain = float((world.distribution * world._base_composite_payoff()).sum())
    world._record_trace(total_flow=0.0, stay_mass=float(world.distribution.sum()))


def _distribution_weighted_terrain_row(world: DistributionTerrainV32World) -> dict[str, float | int | str]:
    distribution = world.distribution

    def weighted_mean(value: Any) -> float:
        return float((distribution * value).sum())

    short_medium_gap = abs(world.short_payoff - world.medium_payoff)
    composite_payoff = world._base_composite_payoff()
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
        "existing_path_expected_value_distribution_weighted_mean": weighted_mean(world.existing_path_expected_value),
        "exploration_cost_distribution_weighted_mean": weighted_mean(world.exploration_cost),
        "exploration_option_value_distribution_weighted_mean": weighted_mean(world.exploration_option_value),
        "exploration_net_expected_value_distribution_weighted_mean": weighted_mean(world.exploration_net_expected_value),
        "expected_value_advantage_distribution_weighted_mean": weighted_mean(world.expected_value_advantage),
        "information_memory_distribution_weighted_mean": weighted_mean(world.information_memory),
        "short_gain_information_conversion_distribution_weighted_mean": weighted_mean(
            world.short_gain_information_conversion
        ),
    }


def _first_last_delta(summary: dict[str, Any], prefix: str, frame: pd.DataFrame, column: str) -> None:
    initial = float(frame[column].iloc[0])
    final = float(frame[column].iloc[-1])
    summary[f"initial_{prefix}"] = initial
    summary[f"final_{prefix}"] = final
    summary[f"delta_{prefix}"] = final - initial


def _build_summary(spec: ScenarioSpec, traces: dict[str, pd.DataFrame]) -> dict[str, float | int | str]:
    distribution = traces["v3_2_internal_distribution_trace"]
    flow = traces["v3_2_internal_flow_trace"]
    terrain = traces["v3_2_internal_terrain_trace"]
    weighted_terrain = traces["v3_2_internal_distribution_weighted_terrain_trace"]
    external = traces["v3_2_internal_external_trace"]
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
        "existing_path_expected_value_mean",
        "exploration_cost_mean",
        "exploration_option_value_mean",
        "exploration_net_expected_value_mean",
        "expected_value_advantage_mean",
        "information_memory_mean",
        "short_gain_information_conversion_mean",
    ):
        _first_last_delta(summary, column, terrain, column)

    for column in V32_DISTRIBUTION_WEIGHTED_TERRAIN_COLUMNS:
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
    world = DistributionTerrainV32World(DistributionTerrainV32Config(seed=spec.seed, scenario=spec.name))
    _replace_initial_distribution(world, spec)
    weighted_terrain_rows = [_distribution_weighted_terrain_row(world)]
    for t in range(spec.steps):
        world.set_external_factors(_external_factors_for_step(phases, t))
        world.step()
        weighted_terrain_rows.append(_distribution_weighted_terrain_row(world))
    traces = world.emit_trace()
    traces["v3_2_internal_distribution_weighted_terrain_trace"] = pd.DataFrame(weighted_terrain_rows)
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


__all__ = [
    "BASELINE_EXTERNAL_FACTORS",
    "ScenarioPhase",
    "ScenarioResult",
    "ScenarioSpec",
    "V32_DISTRIBUTION_WEIGHTED_TERRAIN_COLUMNS",
    "default_scenario_specs",
    "make_static_scenario",
    "run_default_scenario_suite",
    "run_scenario",
    "run_scenario_suite",
    "run_stable_scenario_suite",
    "stable_scenario_specs",
]
