"""Configuration and vector generation for Task 3.1e."""
from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from itertools import combinations, product
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
from scipy.stats import qmc

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pseudo_reality.distribution_terrain_v3_2_2 import (
    DistributionTerrainV322Config,
    DistributionTerrainV322World,
)

EXTERNAL_COLUMNS = [
    "external_resource_supply",
    "external_demand",
    "external_competition_pressure",
    "external_information_noise",
    "external_shock",
    "external_constraint_pressure",
]
RANGES = {
    "external_resource_supply": (-1.0, 1.0),
    "external_demand": (-1.0, 1.0),
    "external_competition_pressure": (0.0, 1.0),
    "external_information_noise": (0.0, 1.0),
    "external_shock": (0.0, 1.0),
    "external_constraint_pressure": (0.0, 1.0),
}
TERRAIN_FIELDS = [
    "short_payoff", "medium_payoff", "effective_medium_payoff", "friction",
    "viscosity", "damage", "rigidity", "recovery_speed",
    "existing_path_expected_value", "exploration_cost", "exploration_option_value",
    "exploration_net_expected_value", "expected_value_advantage", "information_memory",
    "viability_reserve", "route_support", "maintenance_cost", "net_viability_value",
    "negative_viability_pressure", "operating_cost", "cost_reduction_gain",
    "cost_reduction_preference",
]
EXCLUDED_TRANSITION_FIELDS = [
    "last_flow", "short_gain_information_conversion", "short_path_decline_information",
    "exploration_experience_information", "support_erosion", "released_mass",
    "release_reallocation_flow", "total_gain_delta_signal",
    "last_external_deformation_strength", "last_threshold_activation_strength",
    "last_distribution_weighted_threshold_activation_strength",
]
OUT_SUBDIR = "pseudoreality_v3_3_task3_1e_static_full_distribution"
DEFAULT_CONFIG = ROOT / "configs" / "task3_1e_static_full_distribution_testbed.json"
MASS_TOLERANCE = 1e-8
NEGATIVE_TOLERANCE = 1e-12
JS_EPSILON = 1e-12


@dataclass(frozen=True)
class ExternalVector:
    external_vector_id: str
    dataset_split: str
    vector_origin: str
    mask_bits: str
    active_factor_count: int
    is_base_vector: bool
    sobol_scramble_seed: int | None
    sobol_index: int | None
    values: tuple[float, ...]
    candidate_pool_id: str | None = None
    adaptive_selection_rank: int | None = None


@dataclass(frozen=True)
class AdaptiveCandidate:
    candidate_pool_id: str
    mask_bits: str
    active_factor_count: int
    sobol_scramble_seed: int
    sobol_index: int
    values: tuple[float, ...]


@dataclass(frozen=True)
class SelectedCandidate:
    candidate: AdaptiveCandidate
    selection_rank: int
    minimum_js_distance_at_selection: float


def _require_mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def load_config(path: str | Path, profile: str) -> tuple[dict[str, Any], dict[str, Any]]:
    config_path = Path(path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if profile not in config.get("profiles", {}):
        raise ValueError(f"unknown profile: {profile}")
    if config.get("axis_count") != 5 or config.get("n_bins") != 5 or config.get("cell_count") != 3125:
        raise ValueError("Task 3.1e requires five axes, five bins, and 3125 cells")
    if config.get("external_columns") != EXTERNAL_COLUMNS:
        raise ValueError("external_columns does not match the six-factor contract")
    profile_config = _require_mapping(config["profiles"][profile], f"profiles.{profile}")
    for section in ("capture_steps", "world_seeds", "sobol_seeds", "fit_allocation", "validation_allocation"):
        _require_mapping(profile_config.get(section), f"profiles.{profile}.{section}")
    for split in ("fit", "validation", "holdout"):
        seeds = profile_config["world_seeds"].get(split)
        if not isinstance(seeds, list) or not seeds or any(not isinstance(seed, int) for seed in seeds):
            raise ValueError(f"world_seeds.{split} must be a non-empty integer list")
    for name in ("external", "base"):
        steps = profile_config["capture_steps"].get(name)
        if not isinstance(steps, list) or not steps or any(not isinstance(step, int) or step < 0 for step in steps):
            raise ValueError(f"capture_steps.{name} must be a non-empty non-negative integer list")
        if steps != sorted(set(steps)):
            raise ValueError(f"capture_steps.{name} must be strictly increasing and unique")
    if any(step == 0 for step in profile_config["capture_steps"]["external"]):
        raise ValueError("external capture steps must not include step 0")
    for allocation_name in ("fit_allocation", "validation_allocation"):
        allocation = profile_config[allocation_name]
        if set(allocation) != {str(k) for k in range(1, 7)}:
            raise ValueError(f"{allocation_name} must define active-factor counts 1..6")
        if any(not isinstance(value, int) or value < 0 for value in allocation.values()):
            raise ValueError(f"{allocation_name} values must be non-negative integers")
    holdout = _require_mapping(profile_config.get("holdout"), f"profiles.{profile}.holdout")
    if not 0 <= int(holdout.get("boundary_count", -1)) <= 64:
        raise ValueError("holdout.boundary_count must be between 0 and 64")
    if int(holdout.get("full6_count", -1)) < 0:
        raise ValueError("holdout.full6_count must be non-negative")
    pool = profile_config.get("adaptive_pool")
    if not isinstance(pool, list) or not pool:
        raise ValueError("adaptive_pool must be a non-empty list")
    for item in pool:
        _require_mapping(item, "adaptive_pool item")
        k = int(item.get("active_factor_count", 0))
        n = int(item.get("points_per_mask", -1))
        if k < 1 or k > 6 or n < 0:
            raise ValueError("adaptive_pool entries require active_factor_count 1..6 and non-negative points_per_mask")
    if int(profile_config.get("adaptive_selected_count", -1)) <= 0:
        raise ValueError("adaptive_selected_count must be positive")
    if int(profile_config.get("adaptive_reference_seed", -1)) < 0:
        raise ValueError("adaptive_reference_seed must be non-negative")
    if int(profile_config.get("adaptive_reference_step", -1)) <= 0:
        raise ValueError("adaptive_reference_step must be positive")
    return config, profile_config


def validate_external_values(values: Sequence[float]) -> tuple[float, ...]:
    if len(values) != len(EXTERNAL_COLUMNS):
        raise ValueError("exactly six external factors are required")
    validated: list[float] = []
    for column, raw in zip(EXTERNAL_COLUMNS, values):
        value = float(raw)
        low, high = RANGES[column]
        if not np.isfinite(value) or value < low or value > high:
            raise ValueError(f"{column}={value} outside [{low}, {high}]")
        validated.append(value)
    return tuple(validated)


def all_external_update(values: Sequence[float]) -> dict[str, float]:
    return dict(zip(EXTERNAL_COLUMNS, validate_external_values(values)))


def rounded_key(values: Sequence[float]) -> tuple[float, ...]:
    return tuple(round(float(value), 12) for value in values)


def mask_bits_for(active: Iterable[int]) -> str:
    active_set = set(active)
    return "".join("1" if index in active_set else "0" for index in range(6))


def masks_by_count(count: int) -> list[tuple[int, ...]]:
    if count == 6:
        return [tuple(range(6))]
    return list(combinations(range(6), count))


def real_from_unit(dimension: int, unit_value: float) -> float:
    return 2.0 * float(unit_value) - 1.0 if dimension in (0, 1) else float(unit_value)


def sobol_points(dimension: int, count: int, seed: int) -> np.ndarray:
    if count == 0:
        return np.empty((0, dimension), dtype=np.float64)
    exponent = 0 if count == 1 else math.ceil(math.log2(count))
    points = qmc.Sobol(d=dimension, scramble=True, seed=seed).random_base2(exponent)
    return np.asarray(points[:count], dtype=np.float64)


def vector_from_active(active: Sequence[int], unit_row: Sequence[float]) -> tuple[float, ...]:
    values = [0.0] * 6
    for local_index, dimension in enumerate(active):
        values[dimension] = real_from_unit(dimension, float(unit_row[local_index]))
    return validate_external_values(values)


def _base_vector(split: str, index: int) -> ExternalVector:
    return ExternalVector(f"vec_{split}_{index:06d}", split, "base", "000000", 0, True, None, None, (0.0,) * 6)


def _stratified_vectors(split: str, seed: int, allocation: dict[str, int], start_index: int = 1) -> tuple[list[ExternalVector], int]:
    vectors: list[ExternalVector] = []
    next_index = start_index
    for active_count in range(1, 7):
        points_per_mask = int(allocation[str(active_count)])
        for active in masks_by_count(active_count):
            for sobol_index, row in enumerate(sobol_points(active_count, points_per_mask, seed)):
                vectors.append(ExternalVector(
                    f"vec_{split}_{next_index:06d}", split, "sobol_stratified",
                    mask_bits_for(active), active_count, False, seed, sobol_index,
                    vector_from_active(active, row),
                ))
                next_index += 1
    return vectors, next_index


def _boundary_vectors(split: str, count: int, start_index: int = 1) -> tuple[list[ExternalVector], int]:
    corners = product((-1.0, 1.0), (-1.0, 1.0), (0.0, 1.0), (0.0, 1.0), (0.0, 1.0), (0.0, 1.0))
    vectors: list[ExternalVector] = []
    next_index = start_index
    for raw_values in list(corners)[:count]:
        values = validate_external_values(raw_values)
        active = tuple(index for index, value in enumerate(values) if value != 0.0)
        vectors.append(ExternalVector(
            f"vec_{split}_{next_index:06d}", split, "boundary_corner",
            mask_bits_for(active), len(active), False, None, None, values,
        ))
        next_index += 1
    return vectors, next_index


def build_initial_vectors(profile_config: dict[str, Any]) -> dict[str, list[ExternalVector]]:
    seeds = profile_config["sobol_seeds"]
    fit, fit_next = _stratified_vectors("fit", int(seeds["fit"]), profile_config["fit_allocation"])
    fit.append(_base_vector("fit", fit_next))
    validation, validation_next = _stratified_vectors("validation", int(seeds["validation"]), profile_config["validation_allocation"])
    validation.append(_base_vector("validation", validation_next))
    holdout_config = profile_config["holdout"]
    holdout, holdout_next = _boundary_vectors("holdout", int(holdout_config["boundary_count"]))
    full6_count = int(holdout_config["full6_count"])
    full6_seed = int(seeds["holdout_full6"])
    for sobol_index, row in enumerate(sobol_points(6, full6_count, full6_seed)):
        holdout.append(ExternalVector(
            f"vec_holdout_{holdout_next:06d}", "holdout", "holdout_full6_sobol",
            "111111", 6, False, full6_seed, sobol_index,
            vector_from_active(tuple(range(6)), row),
        ))
        holdout_next += 1
    holdout.append(_base_vector("holdout", holdout_next))
    return {"fit": fit, "validation": validation, "holdout": holdout}


def build_adaptive_pool(initial_vectors: dict[str, list[ExternalVector]], profile_config: dict[str, Any]) -> list[AdaptiveCandidate]:
    existing = {rounded_key(vector.values) for vectors in initial_vectors.values() for vector in vectors}
    pool_seen: set[tuple[float, ...]] = set()
    candidates: list[AdaptiveCandidate] = []
    candidate_number = 1
    seed = int(profile_config["sobol_seeds"]["adaptive_pool"])
    for pool_spec in profile_config["adaptive_pool"]:
        active_count = int(pool_spec["active_factor_count"])
        points_per_mask = int(pool_spec["points_per_mask"])
        for active in masks_by_count(active_count):
            for sobol_index, row in enumerate(sobol_points(active_count, points_per_mask, seed)):
                values = vector_from_active(active, row)
                key = rounded_key(values)
                if key in existing or key in pool_seen:
                    continue
                pool_seen.add(key)
                candidates.append(AdaptiveCandidate(
                    f"cand_{candidate_number:06d}", mask_bits_for(active), active_count,
                    seed, sobol_index, values,
                ))
                candidate_number += 1
    return candidates
