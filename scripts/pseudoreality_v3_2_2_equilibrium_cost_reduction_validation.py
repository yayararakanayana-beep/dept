"""Pinpoint validation for PseudoReality v3.2.2 equilibrium cost reduction.

This validation is intentionally not a long-horizon superiority test. It checks
whether a weak cost-reduction subgain changes behavior around three mild
equilibrium-like settings:

- gentle growth equilibrium;
- stable equilibrium;
- shrinking equilibrium.

The expected diagnostic target is modest: when ordinary payoff differences are
small, v3.2.2 should make cost reduction visible as an effective medium route
without turning cost reduction into the primary payoff route.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from pseudo_reality.distribution_terrain_v3_2 import DistributionTerrainV32Config, DistributionTerrainV32World
from pseudo_reality.distribution_terrain_v3_2_2 import DistributionTerrainV322Config, DistributionTerrainV322World
from pseudo_reality.distribution_terrain_v3_scenarios import BASELINE_EXTERNAL_FACTORS, ScenarioPhase, ScenarioSpec


SUMMARY_METRICS = (
    "composite_payoff",
    "short_payoff",
    "medium_payoff",
    "effective_medium_payoff",
    "short_medium_gap",
    "friction",
    "viscosity",
    "damage",
    "rigidity",
    "maintenance_cost",
    "operating_cost",
    "cost_reduction_gain",
    "cost_reduction_preference",
    "information_memory",
    "route_support",
    "negative_viability_pressure",
    "expected_value_advantage",
    "total_flow",
)


def equilibrium_pinpoint_specs(*, seed: int = 0, steps: int = 60) -> tuple[ScenarioSpec, ...]:
    """Return mild equilibrium-like scenarios for v3.2.2 pinpoint testing."""

    gentle_growth = {
        "external_resource_supply": 0.25,
        "external_demand": 0.12,
        "external_competition_pressure": 0.02,
        "external_information_noise": 0.00,
        "external_shock": 0.00,
        "external_constraint_pressure": 0.02,
    }
    stable = dict(BASELINE_EXTERNAL_FACTORS)
    shrinking = {
        "external_resource_supply": -0.22,
        "external_demand": -0.06,
        "external_competition_pressure": 0.03,
        "external_information_noise": 0.04,
        "external_shock": 0.00,
        "external_constraint_pressure": 0.04,
    }
    return (
        ScenarioSpec(
            name="gentle_growth_equilibrium",
            seed=seed,
            steps=steps,
            phases=(ScenarioPhase(start=0, end=steps, external_factors=gentle_growth),),
            initial_center=(0.55, 0.65, 0.40, 0.55, 0.65),
            initial_width=0.07,
        ),
        ScenarioSpec(
            name="stable_equilibrium",
            seed=seed,
            steps=steps,
            phases=(ScenarioPhase(start=0, end=steps, external_factors=stable),),
            initial_center=(0.55, 0.65, 0.45, 0.50, 0.65),
            initial_width=0.07,
        ),
        ScenarioSpec(
            name="shrinking_equilibrium",
            seed=seed,
            steps=steps,
            phases=(ScenarioPhase(start=0, end=steps, external_factors=shrinking),),
            initial_center=(0.45, 0.58, 0.42, 0.45, 0.58),
            initial_width=0.07,
        ),
    )


def _external_factors_for_step(spec: ScenarioSpec, t: int) -> dict[str, float]:
    for phase in spec.phases:
        if phase.start <= t < phase.end:
            return phase.external_factors
    return BASELINE_EXTERNAL_FACTORS


def _replace_initial_distribution(world: Any, spec: ScenarioSpec) -> None:
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
    if hasattr(world, "previous_total_gain"):
        world.previous_total_gain = float((world.distribution * world._base_composite_payoff()).sum())
    if hasattr(world, "_update_cost_reduction_fields"):
        world._update_cost_reduction_fields(world._learning_quality())
    world._record_trace(total_flow=0.0, stay_mass=float(world.distribution.sum()))


def _weighted_mean(world: Any, value: np.ndarray) -> float:
    return float(np.sum(world.distribution * value))


def _snapshot(world: Any, *, model: str, spec: ScenarioSpec, phase: str, total_flow_mean: float) -> dict[str, float | int | str]:
    short_medium_gap = np.abs(world.short_payoff - world.medium_payoff)
    medium = getattr(world, "effective_medium_payoff", world.medium_payoff)
    operating_cost = getattr(world, "operating_cost", world.friction + 0.35 * world.viscosity)
    return {
        "model": model,
        "scenario": spec.name,
        "seed": spec.seed,
        "steps": spec.steps,
        "phase": phase,
        "composite_payoff": _weighted_mean(world, world._base_composite_payoff()),
        "short_payoff": _weighted_mean(world, world.short_payoff),
        "medium_payoff": _weighted_mean(world, world.medium_payoff),
        "effective_medium_payoff": _weighted_mean(world, medium),
        "short_medium_gap": _weighted_mean(world, short_medium_gap),
        "friction": _weighted_mean(world, world.friction),
        "viscosity": _weighted_mean(world, world.viscosity),
        "damage": _weighted_mean(world, world.damage),
        "rigidity": _weighted_mean(world, world.rigidity),
        "maintenance_cost": _weighted_mean(world, getattr(world, "maintenance_cost", np.zeros(world.shape))),
        "operating_cost": _weighted_mean(world, operating_cost),
        "cost_reduction_gain": _weighted_mean(world, getattr(world, "cost_reduction_gain", np.zeros(world.shape))),
        "cost_reduction_preference": _weighted_mean(world, getattr(world, "cost_reduction_preference", np.zeros(world.shape))),
        "information_memory": _weighted_mean(world, getattr(world, "information_memory", np.zeros(world.shape))),
        "route_support": _weighted_mean(world, getattr(world, "route_support", np.zeros(world.shape))),
        "negative_viability_pressure": _weighted_mean(
            world,
            getattr(world, "negative_viability_pressure", np.zeros(world.shape)),
        ),
        "expected_value_advantage": _weighted_mean(world, getattr(world, "expected_value_advantage", np.zeros(world.shape))),
        "total_flow": total_flow_mean,
    }


def _run_world(model: str, world: Any, spec: ScenarioSpec) -> dict[str, float | int | str]:
    _replace_initial_distribution(world, spec)
    initial = _snapshot(world, model=model, spec=spec, phase="initial", total_flow_mean=0.0)
    flow_values: list[float] = []
    for t in range(spec.steps):
        world.set_external_factors(_external_factors_for_step(spec, t))
        world.step()
        flow_values.append(float(world.last_flow.sum()))
    final = _snapshot(
        world,
        model=model,
        spec=spec,
        phase="final",
        total_flow_mean=float(np.mean(flow_values)) if flow_values else 0.0,
    )
    row: dict[str, float | int | str] = {"model": model, "scenario": spec.name, "seed": spec.seed, "steps": spec.steps}
    for metric in SUMMARY_METRICS:
        row[f"initial_{metric}"] = initial[metric]
        row[f"final_{metric}"] = final[metric]
        row[f"delta_{metric}"] = float(final[metric]) - float(initial[metric])
    return row


def run_equilibrium_cost_reduction_validation(
    *,
    seeds: tuple[int, ...] | list[int] = (0, 1, 2),
    steps: int = 60,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, float | int | str]] = []
    for seed in seeds:
        for spec in equilibrium_pinpoint_specs(seed=seed, steps=steps):
            rows.append(_run_world("v3.2", DistributionTerrainV32World(DistributionTerrainV32Config(seed=seed)), spec))
            rows.append(_run_world("v3.2.2", DistributionTerrainV322World(DistributionTerrainV322Config(seed=seed)), spec))

    by_model = pd.DataFrame(rows)
    comparison_rows: list[dict[str, float | int | str]] = []
    for (scenario, seed), group in by_model.groupby(["scenario", "seed"], sort=False):
        base = group[group["model"] == "v3.2"].iloc[0]
        candidate = group[group["model"] == "v3.2.2"].iloc[0]
        row: dict[str, float | int | str] = {"scenario": scenario, "seed": int(seed), "steps": int(candidate["steps"])}
        for metric in SUMMARY_METRICS:
            row[f"v32_final_{metric}"] = float(base[f"final_{metric}"])
            row[f"v322_final_{metric}"] = float(candidate[f"final_{metric}"])
            row[f"delta_final_{metric}"] = float(candidate[f"final_{metric}"]) - float(base[f"final_{metric}"])
            row[f"delta_change_{metric}"] = float(candidate[f"delta_{metric}"]) - float(base[f"delta_{metric}"])
        row["cost_reduction_route_visible"] = bool(
            row["v322_final_cost_reduction_gain"] > 0.0
            and row["delta_final_operating_cost"] <= 0.0
            and row["delta_final_effective_medium_payoff"] >= 0.0
        )
        row["ordinary_payoff_not_overridden"] = bool(row["delta_final_composite_payoff"] > -0.02)
        comparison_rows.append(row)

    comparison = pd.DataFrame(comparison_rows)
    numeric_columns = comparison.select_dtypes(include=["number", "bool"]).columns.tolist()
    aggregate = comparison.groupby("scenario", as_index=False)[numeric_columns].mean()
    return by_model, comparison, aggregate


def export_equilibrium_cost_reduction_validation(
    output_root: str | Path,
    *,
    seeds: tuple[int, ...] | list[int] = (0, 1, 2),
    steps: int = 60,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    by_model, comparison, aggregate = run_equilibrium_cost_reduction_validation(seeds=seeds, steps=steps)
    by_model.to_csv(root / "v3_2_2_equilibrium_cost_reduction_by_model.csv", index=False)
    comparison.to_csv(root / "v3_2_2_equilibrium_cost_reduction_comparison.csv", index=False)
    aggregate.to_csv(root / "v3_2_2_equilibrium_cost_reduction_aggregate.csv", index=False)
    return by_model, comparison, aggregate


def compact_readout(aggregate: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "scenario",
        "delta_final_composite_payoff",
        "delta_final_operating_cost",
        "delta_final_friction",
        "delta_final_viscosity",
        "delta_final_effective_medium_payoff",
        "v322_final_cost_reduction_gain",
        "v322_final_cost_reduction_preference",
        "cost_reduction_route_visible",
        "ordinary_payoff_not_overridden",
    ]
    return aggregate[columns]


if __name__ == "__main__":
    _by_model, _comparison, _aggregate = export_equilibrium_cost_reduction_validation(
        "outputs/pseudoreality-v3-validation/v3-2-2-equilibrium-cost-reduction",
        seeds=(0, 1, 2),
        steps=60,
    )
    print(compact_readout(_aggregate).to_string(index=False))
