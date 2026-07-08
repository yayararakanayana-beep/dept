"""Terrain-operation effectiveness validation for PseudoReality v3.

This module is diagnostic-only. It applies explicit terrain operations to the
internal PseudoReality v3 terrain after a common shock setup and compares their
numeric effects. It does not add a predictor, game-structure extractor,
action-decision module, phenomenon flags, G_t/O_t/DEPT connections, public
observations, or individual player/entity models.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from pseudo_reality.distribution_terrain_v3 import DistributionTerrainV3Config, DistributionTerrainV3World


COMPOUND_SHOCK_FACTORS = {
    "external_resource_supply": -0.8,
    "external_demand": 0.8,
    "external_competition_pressure": 0.8,
    "external_information_noise": 0.8,
    "external_shock": 1.0,
    "external_constraint_pressure": 0.8,
}

POST_SHOCK_NEUTRAL_FACTORS = {
    "external_resource_supply": 0.0,
    "external_demand": 0.2,
    "external_competition_pressure": 0.2,
    "external_information_noise": 0.2,
    "external_shock": 0.0,
    "external_constraint_pressure": 0.2,
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

COMPACT_PRINT_COLUMNS = (
    "scenario",
    "operation_target",
    "operation_scope",
    "operation_start",
    "operation_duration",
    "operation_strength",
    "final_short_payoff_distribution_weighted_mean",
    "final_medium_payoff_distribution_weighted_mean",
    "final_total_gain_distribution_weighted_mean",
    "delta_total_gain_distribution_weighted_mean",
    "final_damage_distribution_weighted_mean",
    "final_rigidity_distribution_weighted_mean",
    "final_friction_distribution_weighted_mean",
    "final_recovery_speed_distribution_weighted_mean",
    "final_total_flow",
    "operation_effect_strength_sum",
)


@dataclass(frozen=True)
class TerrainOperationSpec:
    name: str
    target: str
    scope: str
    start: int
    duration: int
    strength: float


@dataclass(frozen=True)
class TerrainOperationResult:
    spec: TerrainOperationSpec
    summary: dict[str, float | int | str]
    traces: dict[str, pd.DataFrame]


def terrain_operation_specs(*, steps: int = 30) -> tuple[TerrainOperationSpec, ...]:
    """Return a lightweight terrain-operation candidate set."""

    shock_end = max(1, steps // 3)
    late_start = max(shock_end + 1, (steps * 2) // 3)
    short_duration = max(1, steps // 10)
    return (
        TerrainOperationSpec("terrain_op_no_operation", "none", "none", start=steps + 1, duration=0, strength=0.0),
        TerrainOperationSpec(
            "terrain_op_damage_reduction_early",
            "damage_reduction",
            "distribution_hotspot",
            start=shock_end,
            duration=short_duration,
            strength=0.18,
        ),
        TerrainOperationSpec(
            "terrain_op_rigidity_reduction_early",
            "rigidity_reduction",
            "high_rigidity",
            start=shock_end,
            duration=short_duration,
            strength=0.18,
        ),
        TerrainOperationSpec(
            "terrain_op_friction_reduction_early",
            "friction_reduction",
            "high_friction",
            start=shock_end,
            duration=short_duration,
            strength=0.16,
        ),
        TerrainOperationSpec(
            "terrain_op_recovery_speed_boost_early",
            "recovery_speed_boost",
            "distribution_hotspot",
            start=shock_end,
            duration=short_duration,
            strength=0.18,
        ),
        TerrainOperationSpec(
            "terrain_op_medium_path_boost_early",
            "medium_path_boost",
            "medium_escape_path",
            start=shock_end,
            duration=short_duration,
            strength=0.16,
        ),
        TerrainOperationSpec(
            "terrain_op_wrong_direction_early",
            "wrong_short_attractor_boost",
            "high_pressure_short_attractor",
            start=shock_end,
            duration=short_duration,
            strength=0.16,
        ),
        TerrainOperationSpec(
            "terrain_op_damage_reduction_late",
            "damage_reduction",
            "distribution_hotspot",
            start=late_start,
            duration=short_duration,
            strength=0.18,
        ),
        TerrainOperationSpec(
            "terrain_op_recovery_speed_boost_late",
            "recovery_speed_boost",
            "distribution_hotspot",
            start=late_start,
            duration=short_duration,
            strength=0.18,
        ),
    )


def _normalize_mask(mask: np.ndarray) -> np.ndarray:
    mask = np.nan_to_num(mask, nan=0.0, posinf=0.0, neginf=0.0)
    mask = np.maximum(mask, 0.0)
    max_value = float(mask.max())
    if max_value <= 1e-12:
        return np.ones_like(mask, dtype=float)
    return np.clip(mask / max_value, 0.0, 1.0)


def _operation_scope_mask(world: DistributionTerrainV3World, scope: str) -> np.ndarray:
    if scope == "none":
        return np.zeros(world.shape, dtype=float)
    if scope == "distribution_hotspot":
        return _normalize_mask(world.distribution)
    if scope == "high_rigidity":
        return _normalize_mask(world.rigidity)
    if scope == "high_friction":
        return _normalize_mask(world.friction)
    if scope == "medium_escape_path":
        _resource, info, pressure, exploration, reversibility = world._coordinate_grids()
        path_score = info * exploration * reversibility * (1.0 - np.abs(pressure - 0.45))
        return _normalize_mask(path_score)
    if scope == "high_pressure_short_attractor":
        _resource, _info, pressure, exploration, _reversibility = world._coordinate_grids()
        short_attractor = pressure * (1.0 - exploration) * (0.5 + 0.5 * _normalize_mask(world.distribution))
        return _normalize_mask(short_attractor)
    raise ValueError(f"Unknown terrain operation scope: {scope!r}")


def apply_terrain_operation(world: DistributionTerrainV3World, spec: TerrainOperationSpec) -> float:
    """Apply one diagnostic terrain operation and return its mean absolute effect."""

    if spec.target == "none" or spec.strength <= 0.0 or spec.duration <= 0:
        return 0.0

    mask = _operation_scope_mask(world, spec.scope)
    strength = float(spec.strength)
    before = _terrain_state_vector(world)

    if spec.target == "damage_reduction":
        world.damage = np.clip(world.damage - strength * mask, 0.0, 1.0)
    elif spec.target == "rigidity_reduction":
        world.rigidity = np.clip(world.rigidity - strength * mask, 0.0, 1.0)
    elif spec.target == "friction_reduction":
        world.friction = np.clip(world.friction - strength * mask, 0.0, 0.95)
    elif spec.target == "recovery_speed_boost":
        world.recovery_speed = np.clip(world.recovery_speed + strength * mask, 0.0, 1.0)
    elif spec.target == "medium_path_boost":
        world.medium_payoff = np.clip(world.medium_payoff + strength * mask, 0.0, 1.5)
        world.friction = np.clip(world.friction - 0.50 * strength * mask, 0.0, 0.95)
    elif spec.target == "wrong_short_attractor_boost":
        world.short_payoff = np.clip(world.short_payoff + strength * mask, 0.0, 1.5)
        world.medium_payoff = np.clip(world.medium_payoff - 0.50 * strength * mask, 0.0, 1.5)
        world.damage = np.clip(world.damage + 0.40 * strength * mask, 0.0, 1.0)
        world.friction = np.clip(world.friction + 0.30 * strength * mask, 0.0, 0.95)
    else:
        raise ValueError(f"Unknown terrain operation target: {spec.target!r}")

    after = _terrain_state_vector(world)
    return float(np.mean(np.abs(after - before)))


def _terrain_state_vector(world: DistributionTerrainV3World) -> np.ndarray:
    return np.stack(
        [
            world.short_payoff,
            world.medium_payoff,
            world.friction,
            world.viscosity,
            world.damage,
            world.rigidity,
            world.recovery_speed,
        ],
        axis=0,
    )


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


def _first_last_delta(summary: dict[str, float | int | str], prefix: str, frame: pd.DataFrame, column: str) -> None:
    initial = float(frame[column].iloc[0])
    final = float(frame[column].iloc[-1])
    summary[f"initial_{prefix}"] = initial
    summary[f"final_{prefix}"] = final
    summary[f"delta_{prefix}"] = final - initial


def _external_factors_for_step(t: int, shock_end: int) -> dict[str, float]:
    return COMPOUND_SHOCK_FACTORS if t < shock_end else POST_SHOCK_NEUTRAL_FACTORS


def _operation_is_active(spec: TerrainOperationSpec, t: int) -> bool:
    return spec.start <= t < spec.start + spec.duration


def run_terrain_operation_scenario(spec: TerrainOperationSpec, *, seed: int = 0, steps: int = 30) -> TerrainOperationResult:
    shock_end = max(1, steps // 3)
    world = DistributionTerrainV3World(DistributionTerrainV3Config(seed=seed, scenario=spec.name))
    weighted_rows = [_distribution_weighted_terrain_row(world)]
    operation_rows: list[dict[str, float | int | str]] = []

    for t in range(steps):
        world.set_external_factors(_external_factors_for_step(t, shock_end))
        operation_effect_strength = 0.0
        if _operation_is_active(spec, t):
            operation_effect_strength = apply_terrain_operation(world, spec)
        operation_rows.append(
            {
                "t": t,
                "scenario": spec.name,
                "operation_target": spec.target,
                "operation_scope": spec.scope,
                "operation_active": int(_operation_is_active(spec, t)),
                "operation_effect_strength": operation_effect_strength,
            }
        )
        world.step()
        weighted_rows.append(_distribution_weighted_terrain_row(world))

    traces = world.emit_trace()
    traces["v3_internal_distribution_weighted_terrain_trace"] = pd.DataFrame(weighted_rows)
    traces["v3_internal_terrain_operation_trace"] = pd.DataFrame(operation_rows)
    return TerrainOperationResult(spec=spec, summary=_build_summary(spec, steps, traces), traces=traces)


def _build_summary(
    spec: TerrainOperationSpec,
    steps: int,
    traces: dict[str, pd.DataFrame],
) -> dict[str, float | int | str]:
    distribution = traces["v3_internal_distribution_trace"]
    flow = traces["v3_internal_flow_trace"]
    weighted_terrain = traces["v3_internal_distribution_weighted_terrain_trace"]
    operation = traces["v3_internal_terrain_operation_trace"]
    summary: dict[str, float | int | str] = {
        "scenario": spec.name,
        "seed": int(distribution["seed"].iloc[-1]),
        "steps": steps,
        "operation_target": spec.target,
        "operation_scope": spec.scope,
        "operation_start": spec.start,
        "operation_duration": spec.duration,
        "operation_strength": spec.strength,
        "operation_effect_strength_sum": float(operation["operation_effect_strength"].sum()),
        "operation_active_steps": int(operation["operation_active"].sum()),
    }
    _first_last_delta(summary, "entropy", distribution, "entropy")
    _first_last_delta(summary, "max_mass", distribution, "max_mass")
    _first_last_delta(summary, "concentration", flow, "concentration")
    summary["total_moved_mass_sum"] = float(flow["moved_mass"].sum())
    summary["mean_total_flow"] = float(flow["total_flow"].mean())
    summary["final_total_flow"] = float(flow["total_flow"].iloc[-1])

    for column in DISTRIBUTION_WEIGHTED_TERRAIN_COLUMNS:
        _first_last_delta(summary, column, weighted_terrain, column)

    summary["initial_total_gain_distribution_weighted_mean"] = summary[
        "initial_composite_payoff_distribution_weighted_mean"
    ]
    summary["final_total_gain_distribution_weighted_mean"] = summary[
        "final_composite_payoff_distribution_weighted_mean"
    ]
    summary["delta_total_gain_distribution_weighted_mean"] = summary[
        "delta_composite_payoff_distribution_weighted_mean"
    ]
    summary["final_short_dominance_distribution_weighted_margin"] = (
        float(summary["final_short_payoff_distribution_weighted_mean"])
        - float(summary["final_medium_payoff_distribution_weighted_mean"])
    )
    summary["final_medium_dominance_distribution_weighted_margin"] = -float(
        summary["final_short_dominance_distribution_weighted_margin"]
    )
    summary["damage_residual_distribution_weighted_mean"] = summary["final_damage_distribution_weighted_mean"]
    summary["rigidity_residual_distribution_weighted_mean"] = summary["final_rigidity_distribution_weighted_mean"]
    return summary


def run_terrain_operation_effectiveness_suite(
    *,
    seed: int = 0,
    steps: int = 30,
) -> tuple[pd.DataFrame, dict[str, dict[str, pd.DataFrame]]]:
    results = [run_terrain_operation_scenario(spec, seed=seed, steps=steps) for spec in terrain_operation_specs(steps=steps)]
    summary = pd.DataFrame([result.summary for result in results])
    traces_by_scenario = {result.spec.name: result.traces for result in results}
    return summary, traces_by_scenario


def export_terrain_operation_effectiveness(output_dir: str | Path, *, seed: int = 0, steps: int = 30) -> pd.DataFrame:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    summary, _traces_by_scenario = run_terrain_operation_effectiveness_suite(seed=seed, steps=steps)
    summary.to_csv(root / "terrain_operation_effectiveness_summary.csv", index=False)
    summary.to_json(root / "terrain_operation_effectiveness_summary.json", orient="records", indent=2)
    return summary


def compact_readout(table: pd.DataFrame) -> pd.DataFrame:
    available = [column for column in COMPACT_PRINT_COLUMNS if column in table.columns]
    return table[available].copy()


if __name__ == "__main__":
    table = export_terrain_operation_effectiveness(
        "outputs/pseudoreality-v3-validation/terrain-operation-effectiveness",
        seed=0,
        steps=30,
    )
    print(compact_readout(table).to_string(index=False))
