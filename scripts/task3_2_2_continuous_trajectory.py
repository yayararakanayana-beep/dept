"""Task 3.2-2: generate small continuous PseudoReality v3.3 trajectories.

The generator records raw full-state snapshots and observed logs for later
macro-dynamics exploration. It does not fit a predictor, select a dynamics
model, construct formal G_t/K_t, or treat scenario names as outcome truth.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from pseudo_reality.distribution_terrain_v3_2_2 import (  # noqa: E402
    DistributionTerrainV322Config,
    DistributionTerrainV322World,
)
from task3_2_1_macro_dynamics_contract import (  # noqa: E402
    ContractError,
    load_contract,
    validate_bundle,
    validate_split_assignments,
)

DEFAULT_CONFIG = ROOT / "configs" / "task3_2_2_continuous_trajectory.json"
EXTERNAL_FIELDS = (
    "external_resource_supply",
    "external_demand",
    "external_competition_pressure",
    "external_information_noise",
    "external_shock",
    "external_constraint_pressure",
)
OPTIONAL_TRANSITION_ARRAYS = (
    "last_flow",
    "short_gain_information_conversion",
    "short_path_decline_information",
    "exploration_experience_information",
    "support_erosion",
    "released_mass",
    "release_reallocation_flow",
)
OPTIONAL_TRANSITION_SCALARS = (
    "total_gain_delta_signal",
    "last_external_deformation_strength",
    "last_threshold_activation_strength",
    "last_distribution_weighted_threshold_activation_strength",
)


class TrajectoryError(ValueError):
    """Raised when Task 3.2-2 generation or validation fails."""


def _json_dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _json_load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise TrajectoryError(f"{path}:{line_number} must contain a JSON object")
            rows.append(value)
    return rows


def _finite_number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TrajectoryError(f"{name} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise TrajectoryError(f"{name} must be finite")
    return number


def load_generation_config(path: str | Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = _json_load(Path(path))
    validate_generation_config(config)
    return config


def validate_generation_config(config: Mapping[str, Any]) -> None:
    for key in ("profiles", "scenario_order", "scenarios", "provisional_outcome_rules", "numeric"):
        if key not in config:
            raise TrajectoryError(f"generation config missing {key}")
    profiles = config["profiles"]
    if not isinstance(profiles, Mapping) or not profiles:
        raise TrajectoryError("profiles must be a non-empty object")
    for name, profile in profiles.items():
        if not isinstance(profile, Mapping):
            raise TrajectoryError(f"profile {name} must be an object")
        transitions = profile.get("transitions")
        if isinstance(transitions, bool) or not isinstance(transitions, int) or transitions < 2:
            raise TrajectoryError(f"profile {name}.transitions must be an integer >= 2")
        seeds = profile.get("seeds")
        if not isinstance(seeds, list) or not seeds or any(
            isinstance(seed, bool) or not isinstance(seed, int) or seed < 0 for seed in seeds
        ):
            raise TrajectoryError(f"profile {name}.seeds must be non-negative integers")
        if len(seeds) != len(set(seeds)):
            raise TrajectoryError(f"profile {name}.seeds must be unique")
        if "split_by_seed" in profile:
            split_map = profile["split_by_seed"]
            if set(split_map) != {str(seed) for seed in seeds}:
                raise TrajectoryError(f"profile {name}.split_by_seed must cover every seed")
        elif profile.get("dataset_split") not in {"fit", "validation", "holdout", "exploratory"}:
            raise TrajectoryError(f"profile {name}.dataset_split is invalid")

    scenario_order = config["scenario_order"]
    scenarios = config["scenarios"]
    if not isinstance(scenario_order, list) or set(scenario_order) != set(scenarios):
        raise TrajectoryError("scenario_order must list each scenario exactly once")
    if len(scenario_order) != len(set(scenario_order)):
        raise TrajectoryError("scenario_order contains duplicates")
    for scenario_id in scenario_order:
        scenario = scenarios[scenario_id]
        segments = scenario.get("segments") if isinstance(scenario, Mapping) else None
        if not isinstance(segments, list) or not segments:
            raise TrajectoryError(f"scenario {scenario_id} requires segments")
        expected_start = 0
        for index, segment in enumerate(segments):
            if not isinstance(segment, Mapping):
                raise TrajectoryError(f"scenario {scenario_id} segment {index} must be an object")
            start = segment.get("start")
            end = segment.get("end")
            if start != expected_start:
                raise TrajectoryError(f"scenario {scenario_id} segments must be contiguous from step 0")
            if end is None:
                if index != len(segments) - 1:
                    raise TrajectoryError(f"scenario {scenario_id} open-ended segment must be last")
            elif isinstance(end, bool) or not isinstance(end, int) or end <= start:
                raise TrajectoryError(f"scenario {scenario_id} segment end must exceed start")
            for field in EXTERNAL_FIELDS:
                if field not in segment:
                    raise TrajectoryError(f"scenario {scenario_id} segment missing {field}")
                value = _finite_number(segment[field], f"{scenario_id}.{field}")
                low, high = (-1.0, 1.0) if field in EXTERNAL_FIELDS[:2] else (0.0, 1.0)
                if value < low or value > high:
                    raise TrajectoryError(f"{scenario_id}.{field} outside [{low}, {high}]")
            expected_start = end


def _profile_split(profile: Mapping[str, Any], seed: int) -> str:
    if "split_by_seed" in profile:
        return str(profile["split_by_seed"][str(seed)])
    return str(profile["dataset_split"])


def _segment_at(scenario: Mapping[str, Any], step: int) -> tuple[dict[str, float], list[str]]:
    for segment in scenario["segments"]:
        start = int(segment["start"])
        end = segment["end"]
        if step >= start and (end is None or step < int(end)):
            external = {field: float(segment[field]) for field in EXTERNAL_FIELDS}
            event = str(segment.get("event", "unspecified_segment"))
            events = [f"regime:{event}"]
            if step == start:
                events.append(f"started:{event}")
            return external, events
    raise TrajectoryError(f"no scenario segment covers step {step}")


def _trajectory_id(profile_name: str, scenario_id: str, seed: int) -> str:
    return f"traj_{profile_name}_{scenario_id}_seed{seed:03d}"


def _array_digest_update(digest: hashlib._Hash, name: str, value: np.ndarray) -> None:
    array = np.ascontiguousarray(value)
    digest.update(name.encode("utf-8"))
    digest.update(str(array.shape).encode("ascii"))
    digest.update(str(array.dtype).encode("ascii"))
    digest.update(array.tobytes(order="C"))


def _snapshot_world(
    world: DistributionTerrainV322World,
    path: Path,
    required_arrays: Sequence[str],
    dtype: str,
    trajectory_digest: hashlib._Hash,
) -> list[str]:
    payload: dict[str, np.ndarray] = {}
    expected_shape = tuple(world.shape)
    for name in required_arrays:
        if not hasattr(world, name):
            raise TrajectoryError(f"world is missing required state array {name}")
        array = np.asarray(getattr(world, name), dtype=dtype).copy()
        if array.shape != expected_shape:
            raise TrajectoryError(f"{name} shape {array.shape} != {expected_shape}")
        if not np.all(np.isfinite(array)):
            raise TrajectoryError(f"{name} contains non-finite values")
        payload[name] = array
        _array_digest_update(trajectory_digest, name, array)

    for name in OPTIONAL_TRANSITION_ARRAYS:
        if hasattr(world, name):
            array = np.asarray(getattr(world, name), dtype=dtype).copy()
            if array.shape != expected_shape:
                raise TrajectoryError(f"{name} shape {array.shape} != {expected_shape}")
            if not np.all(np.isfinite(array)):
                raise TrajectoryError(f"{name} contains non-finite values")
            payload[name] = array
            _array_digest_update(trajectory_digest, name, array)

    for name in OPTIONAL_TRANSITION_SCALARS:
        if hasattr(world, name):
            value = np.asarray(float(getattr(world, name)), dtype=np.float64)
            if not np.all(np.isfinite(value)):
                raise TrajectoryError(f"{name} is non-finite")
            payload[name] = value
            _array_digest_update(trajectory_digest, name, value)

    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **payload)
    return list(required_arrays)


def _weighted_mean(distribution: np.ndarray, value: np.ndarray) -> float:
    return float(np.sum(distribution * value))


def _state_metrics(world: DistributionTerrainV322World, external: Mapping[str, float]) -> dict[str, float]:
    distribution = np.asarray(world.distribution, dtype=np.float64)
    entropy = -float(np.sum(distribution * np.log(np.maximum(distribution, 1e-12))))
    weighted = {
        "damage": _weighted_mean(distribution, world.damage),
        "rigidity": _weighted_mean(distribution, world.rigidity),
        "friction": _weighted_mean(distribution, world.friction),
        "viscosity": _weighted_mean(distribution, world.viscosity),
        "recovery_speed": _weighted_mean(distribution, world.recovery_speed),
        "route_support": _weighted_mean(distribution, world.route_support),
        "viability_reserve": _weighted_mean(distribution, world.viability_reserve),
        "negative_viability_pressure": _weighted_mean(distribution, world.negative_viability_pressure),
    }
    risk_score = (
        0.20 * weighted["damage"]
        + 0.15 * weighted["rigidity"]
        + 0.15 * weighted["friction"]
        + 0.10 * weighted["viscosity"]
        + 0.15 * (1.0 - weighted["recovery_speed"])
        + 0.10 * (1.0 - weighted["route_support"])
        + 0.05 * (1.0 - weighted["viability_reserve"])
        + 0.10 * weighted["negative_viability_pressure"]
    )
    metrics: dict[str, float] = {
        "mass_sum": float(distribution.sum()),
        "entropy": entropy,
        "concentration": float(np.sum(distribution**2)),
        "max_mass": float(distribution.max()),
        "moved_mass": float(np.sum(np.asarray(world.last_flow, dtype=np.float64))),
        "risk_score": float(risk_score),
        **{f"weighted_{name}": float(value) for name, value in weighted.items()},
    }
    axis = np.linspace(0.0, 1.0, world.config.n_bins)
    coordinates = np.meshgrid(*([axis] * len(world.config.axes)), indexing="ij")
    for axis_name, coordinate in zip(world.config.axes, coordinates, strict=True):
        center = float(np.sum(distribution * coordinate))
        metrics[f"center_{axis_name}"] = center
        metrics[f"spread_{axis_name}"] = float(
            np.sqrt(np.sum(distribution * (coordinate - center) ** 2))
        )
    for name, value in external.items():
        metrics[name] = float(value)
    return metrics


def _first_sustained(values: Sequence[float], threshold: float, length: int) -> int | None:
    if length <= 0:
        return None
    run = 0
    for index, value in enumerate(values):
        run = run + 1 if value >= threshold else 0
        if run >= length:
            return index - length + 1
    return None


def _analyse_outcome(metrics: Sequence[Mapping[str, float]], rules: Mapping[str, Any]) -> dict[str, Any]:
    risk = np.asarray([row["risk_score"] for row in metrics], dtype=np.float64)
    concentration = np.asarray([row["concentration"] for row in metrics], dtype=np.float64)
    mobility = np.asarray([row["moved_mass"] for row in metrics], dtype=np.float64)
    rigidity = np.asarray([row["weighted_rigidity"] for row in metrics], dtype=np.float64)
    baseline_count = min(int(rules["baseline_steps"]), len(metrics))
    tail_count = min(int(rules["tail_steps"]), len(metrics))
    baseline = float(np.mean(risk[:baseline_count]))
    tail = float(np.mean(risk[-tail_count:]))
    peak_step = int(np.argmax(risk))
    peak = float(risk[peak_step])
    peak_elevation = peak - baseline
    tail_delta = tail - baseline
    elevated_delta = float(rules["elevated_risk_delta"])
    onset = _first_sustained(risk.tolist(), baseline + elevated_delta, int(rules["sustained_steps"]))

    recovery_step: int | None = None
    for step in range(peak_step, len(risk)):
        if risk[step] <= baseline + float(rules["full_recovery_tolerance"]):
            recovery_step = step
            break
    if peak_elevation > 1e-12:
        recovered_fraction = float(np.clip((peak - tail) / peak_elevation, -1.0, 1.0))
    else:
        recovered_fraction = 0.0

    base_concentration = max(float(np.mean(concentration[:baseline_count])), 1e-12)
    concentration_ratio = float(np.mean(concentration[-tail_count:]) / base_concentration)
    mobility_base_slice = mobility[1 : max(2, baseline_count)]
    base_mobility = max(float(np.mean(mobility_base_slice)), 1e-12)
    mobility_ratio = float(np.mean(mobility[-tail_count:]) / base_mobility)
    rigidity_delta = float(np.mean(rigidity[-tail_count:]) - np.mean(rigidity[:baseline_count]))

    collapse = (
        tail >= float(rules["collapse_risk_score"])
        and tail_delta >= float(rules["collapse_risk_delta"])
    )
    fixation = (
        concentration_ratio >= float(rules["fixation_concentration_ratio"])
        and mobility_ratio <= float(rules["fixation_mobility_ratio"])
        and rigidity_delta >= float(rules["fixation_rigidity_delta"])
    )
    minimum_peak = float(rules["minimum_peak_elevation"])
    recovery_fraction_gate = float(rules["recovery_fraction"])

    if collapse:
        event = "collapse"
        coarse = "collapse_or_divergence_candidate"
        recovery_outcome = "no_natural_recovery"
    elif fixation:
        event = "fixation"
        coarse = "fixation_candidate"
        recovery_outcome = "no_natural_recovery"
    elif tail_delta >= elevated_delta and recovered_fraction < recovery_fraction_gate:
        event = "persistent_deterioration"
        coarse = "persistent_deterioration"
        recovery_outcome = "no_natural_recovery"
    elif peak_elevation >= minimum_peak and recovery_step is not None:
        event = "none"
        coarse = "natural_recovery"
        recovery_outcome = "natural_recovery"
    elif peak_elevation >= minimum_peak and recovered_fraction >= recovery_fraction_gate:
        event = "delayed_recovery"
        coarse = "delayed_recovery"
        recovery_outcome = "delayed_natural_recovery"
    elif tail_delta >= elevated_delta:
        event = "persistent_deterioration"
        coarse = "persistent_deterioration"
        recovery_outcome = "no_natural_recovery"
    else:
        event = "none"
        coarse = "stable"
        recovery_outcome = "not_evaluated"

    elevated = risk >= baseline + elevated_delta
    risk_depth = {
        "return_time_steps": recovery_step,
        "minimum_effective_action_strength": None,
        "recovery_probability": None,
        "hazard_persistence_steps": int(np.sum(elevated)),
        "deterioration_rate": float(np.max(np.diff(risk))) if len(risk) > 1 else 0.0,
        "distance_from_safe_reference": float(max(0.0, tail_delta)),
        "available_recovery_route_count": None,
        "relapse_probability": None,
    }
    return {
        "coarse_outcome": coarse,
        "future_risk_event": event,
        "risk_onset_step": onset,
        "recovery_outcome": recovery_outcome,
        "recovery_time_steps": recovery_step,
        "irreversibility_level": 0 if recovery_outcome == "natural_recovery" else None,
        "boundary_crossing_step": None,
        "risk_depth": risk_depth,
        "baseline_risk_score": baseline,
        "tail_risk_score": tail,
        "peak_risk_score": peak,
        "peak_risk_step": peak_step,
        "peak_elevation": peak_elevation,
        "recovered_fraction": recovered_fraction,
        "concentration_ratio": concentration_ratio,
        "mobility_ratio": mobility_ratio,
        "rigidity_delta": rigidity_delta,
        "label_is_provisional": True,
        "label_source": "measured_trajectory_not_scenario_id",
    }


def _truth_rows(
    trajectory_id: str,
    transitions: int,
    outcome: Mapping[str, Any],
) -> list[dict[str, Any]]:
    onset = outcome["risk_onset_step"]
    event = str(outcome["future_risk_event"])
    rows: list[dict[str, Any]] = []
    for step in range(transitions):
        if event == "none" or onset is None:
            horizon = None
        else:
            horizon = max(0, int(onset) - step)
        rows.append(
            {
                "trajectory_id": trajectory_id,
                "prediction_step": step,
                "target_step": step + 1,
                "next_state_ref": f"states/step_{step + 1:06d}.npz",
                "future_risk_event": event,
                "future_risk_horizon_steps": horizon,
                "recovery_outcome": outcome["recovery_outcome"],
                "recovery_time_steps": outcome["recovery_time_steps"],
                "irreversibility_level": outcome["irreversibility_level"],
                "risk_depth": dict(outcome["risk_depth"]),
                "boundary_crossing_step": outcome["boundary_crossing_step"],
                "truth_source": "observed_trajectory",
            }
        )
    return rows


def _observed_response(step: int, metrics: Mapping[str, float]) -> dict[str, float] | None:
    if step == 0:
        return None
    return {
        "previous_transition_moved_mass": float(metrics["moved_mass"]),
        "current_risk_score": float(metrics["risk_score"]),
        "current_entropy": float(metrics["entropy"]),
        "current_concentration": float(metrics["concentration"]),
    }


def _escape_xml(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _polyline_points(values: Sequence[float], x: float, y: float, width: float, height: float) -> str:
    if not values:
        return ""
    low = min(values)
    high = max(values)
    span = high - low
    points: list[str] = []
    denominator = max(len(values) - 1, 1)
    for index, value in enumerate(values):
        px = x + width * index / denominator
        py = y + height / 2.0 if span <= 1e-15 else y + height * (high - value) / span
        points.append(f"{px:.2f},{py:.2f}")
    return " ".join(points)


def _write_trajectory_svg(path: Path, title: str, metrics: Sequence[Mapping[str, float]]) -> None:
    series = [
        ("risk_score", "Risk score"),
        ("entropy", "Entropy"),
        ("concentration", "Concentration"),
        ("moved_mass", "Moved mass"),
        ("external_shock", "External shock"),
        ("external_constraint_pressure", "Constraint pressure"),
    ]
    width = 960
    panel_height = 105
    margin_left = 150
    margin_right = 30
    margin_top = 55
    height = margin_top + panel_height * len(series) + 30
    fragments = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="20" y="30" font-family="sans-serif" font-size="18">{_escape_xml(title)}</text>',
    ]
    plot_width = width - margin_left - margin_right
    for panel, (key, label) in enumerate(series):
        y = margin_top + panel * panel_height
        values = [float(row[key]) for row in metrics]
        fragments.extend(
            [
                f'<text x="10" y="{y + 50}" font-family="sans-serif" font-size="13">{_escape_xml(label)}</text>',
                f'<rect x="{margin_left}" y="{y}" width="{plot_width}" height="80" fill="none" stroke="#999"/>',
                f'<polyline points="{_polyline_points(values, margin_left, y, plot_width, 80)}" fill="none" stroke="#222" stroke-width="2"/>',
                f'<text x="{margin_left}" y="{y + 98}" font-family="monospace" font-size="11">min={min(values):.6g} max={max(values):.6g}</text>',
            ]
        )
    fragments.append("</svg>\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(fragments), encoding="utf-8")


def _write_overview_svg(path: Path, summaries: Sequence[Mapping[str, Any]]) -> None:
    width = 1100
    row_height = 28
    height = 70 + row_height * len(summaries)
    risk_values = [float(summary["outcome"]["tail_risk_score"]) for summary in summaries]
    max_risk = max(risk_values + [1e-12])
    fragments = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="20" y="30" font-family="sans-serif" font-size="18">Task 3.2-2 trajectory overview</text>',
    ]
    for index, summary in enumerate(summaries):
        y = 55 + index * row_height
        label = f"{summary['scenario_id']} / seed {summary['seed']} / {summary['outcome']['coarse_outcome']}"
        bar_width = 420 * float(summary["outcome"]["tail_risk_score"]) / max_risk
        fragments.extend(
            [
                f'<text x="20" y="{y + 15}" font-family="sans-serif" font-size="12">{_escape_xml(label)}</text>',
                f'<rect x="570" y="{y}" width="{bar_width:.2f}" height="18" fill="#777"/>',
                f'<text x="1000" y="{y + 15}" font-family="monospace" font-size="12">{float(summary["outcome"]["tail_risk_score"]):.5f}</text>',
            ]
        )
    fragments.append("</svg>\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(fragments), encoding="utf-8")


def generate_trajectory(
    output_dir: Path,
    profile_name: str,
    scenario_id: str,
    scenario: Mapping[str, Any],
    seed: int,
    transitions: int,
    dataset_split: str,
    generation_config: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    trajectory_id = _trajectory_id(profile_name, scenario_id, seed)
    trajectory_dir = output_dir / "trajectories" / trajectory_id
    if trajectory_dir.exists():
        shutil.rmtree(trajectory_dir)
    (trajectory_dir / "states").mkdir(parents=True, exist_ok=True)

    world = DistributionTerrainV322World(DistributionTerrainV322Config(seed=seed))
    required_arrays = list(contract["step_record"]["required_state_arrays"])
    dtype = str(generation_config["numeric"]["state_dtype"])
    metadata = {
        "trajectory_id": trajectory_id,
        "scenario_id": scenario_id,
        "seed": seed,
        "initial_state_id": "distribution_terrain_v3_2_2_default_reset",
        "world_module": generation_config["world"]["module"],
        "world_class": generation_config["world"]["class"],
        "world_version": generation_config["world"]["working_version"],
        "config_version": generation_config["world"]["config_version"],
        "total_steps": transitions,
        "dataset_split": dataset_split,
    }
    trajectory_digest = hashlib.sha256()
    step_rows: list[dict[str, Any]] = []
    metric_rows: list[dict[str, float]] = []

    for step in range(transitions + 1):
        external, events = _segment_at(scenario, step)
        world.set_external_factors(external)
        state_ref = f"states/step_{step:06d}.npz"
        available = _snapshot_world(
            world,
            trajectory_dir / state_ref,
            required_arrays,
            dtype,
            trajectory_digest,
        )
        metrics = _state_metrics(world, external)
        metrics["step"] = float(step)
        metric_rows.append(metrics)
        response = _observed_response(step, metrics)
        model_input = {
            "state_ref": state_ref,
            "history_available_through_step": None if step == 0 else step - 1,
            "observed_external_input": external,
            "observed_events": events,
            "observed_action": None,
            "observed_response": response,
        }
        step_rows.append(
            {
                "trajectory_id": trajectory_id,
                "step": step,
                "phase": "pre_transition",
                "state_ref": state_ref,
                "history_available_through_step": None if step == 0 else step - 1,
                "observed_external_input": external,
                "observed_events": events,
                "observed_action": None,
                "observed_response": response,
                "state_arrays_available": available,
                "model_input": model_input,
            }
        )
        if step < transitions:
            world.step()

    outcome = _analyse_outcome(metric_rows, generation_config["provisional_outcome_rules"])
    truth_rows = _truth_rows(trajectory_id, transitions, outcome)
    summary = {
        "trajectory_id": trajectory_id,
        "profile": profile_name,
        "scenario_id": scenario_id,
        "scenario_description": scenario.get("description", ""),
        "seed": seed,
        "dataset_split": dataset_split,
        "transitions": transitions,
        "trajectory_fingerprint": trajectory_digest.hexdigest(),
        "outcome": outcome,
        "initial_metrics": metric_rows[0],
        "final_metrics": metric_rows[-1],
    }

    _json_dump(trajectory_dir / "metadata.json", metadata)
    _write_jsonl(trajectory_dir / "steps.jsonl", step_rows)
    _write_jsonl(trajectory_dir / "truth.jsonl", truth_rows)
    _write_jsonl(trajectory_dir / "metrics.jsonl", metric_rows)
    _json_dump(trajectory_dir / "summary.json", summary)
    _write_trajectory_svg(
        trajectory_dir / "trajectory.svg",
        f"{trajectory_id}: {outcome['coarse_outcome']}",
        metric_rows,
    )
    validation = validate_trajectory_directory(trajectory_dir, contract, generation_config)
    _json_dump(trajectory_dir / "validation.json", validation)
    return summary


def validate_trajectory_directory(
    trajectory_dir: str | Path,
    contract: Mapping[str, Any],
    generation_config: Mapping[str, Any],
) -> dict[str, Any]:
    directory = Path(trajectory_dir)
    metadata = _json_load(directory / "metadata.json")
    steps = _read_jsonl(directory / "steps.jsonl")
    truth = _read_jsonl(directory / "truth.jsonl")
    contract_result = validate_bundle(metadata, steps, truth, contract)
    required = set(contract["step_record"]["required_state_arrays"])
    expected_shape = (5, 5, 5, 5, 5)
    mass_tolerance = float(generation_config["numeric"]["mass_tolerance"])
    negative_tolerance = float(generation_config["numeric"]["negative_tolerance"])
    checked_arrays = 0
    for record in steps:
        state_ref = Path(record["state_ref"])
        if state_ref.is_absolute() or ".." in state_ref.parts:
            raise TrajectoryError("state_ref must remain inside the trajectory directory")
        state_path = directory / state_ref
        if not state_path.is_file():
            raise TrajectoryError(f"missing state file {state_ref}")
        with np.load(state_path, allow_pickle=False) as bundle:
            missing = sorted(required - set(bundle.files))
            if missing:
                raise TrajectoryError(f"{state_ref} missing arrays {missing}")
            for name in bundle.files:
                array = np.asarray(bundle[name])
                if not np.all(np.isfinite(array)):
                    raise TrajectoryError(f"{state_ref}:{name} contains non-finite values")
                if name in required and array.shape != expected_shape:
                    raise TrajectoryError(f"{state_ref}:{name} shape {array.shape} != {expected_shape}")
                checked_arrays += 1
            distribution = np.asarray(bundle["distribution"], dtype=np.float64)
            if float(distribution.min()) < -negative_tolerance:
                raise TrajectoryError(f"{state_ref}:distribution contains negative mass")
            if abs(float(distribution.sum()) - 1.0) > mass_tolerance:
                raise TrajectoryError(f"{state_ref}:distribution mass does not sum to one")
    return {
        **contract_result,
        "state_file_count": len(steps),
        "checked_array_count": checked_arrays,
        "shape_check": "passed",
        "finite_value_check": "passed",
        "mass_check": "passed",
        "status": "valid",
    }


def _write_comparison_csv(path: Path, summaries: Sequence[Mapping[str, Any]]) -> None:
    columns = [
        "trajectory_id",
        "scenario_id",
        "seed",
        "dataset_split",
        "coarse_outcome",
        "future_risk_event",
        "baseline_risk_score",
        "tail_risk_score",
        "peak_risk_score",
        "risk_onset_step",
        "recovery_time_steps",
        "concentration_ratio",
        "mobility_ratio",
        "rigidity_delta",
        "trajectory_fingerprint",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for summary in summaries:
            outcome = summary["outcome"]
            writer.writerow(
                {
                    "trajectory_id": summary["trajectory_id"],
                    "scenario_id": summary["scenario_id"],
                    "seed": summary["seed"],
                    "dataset_split": summary["dataset_split"],
                    "coarse_outcome": outcome["coarse_outcome"],
                    "future_risk_event": outcome["future_risk_event"],
                    "baseline_risk_score": outcome["baseline_risk_score"],
                    "tail_risk_score": outcome["tail_risk_score"],
                    "peak_risk_score": outcome["peak_risk_score"],
                    "risk_onset_step": outcome["risk_onset_step"],
                    "recovery_time_steps": outcome["recovery_time_steps"],
                    "concentration_ratio": outcome["concentration_ratio"],
                    "mobility_ratio": outcome["mobility_ratio"],
                    "rigidity_delta": outcome["rigidity_delta"],
                    "trajectory_fingerprint": summary["trajectory_fingerprint"],
                }
            )


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_manifest(output_dir: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for path in sorted(output_dir.rglob("*")):
        if not path.is_file() or path.name == "manifest.json":
            continue
        files.append(
            {
                "path": path.relative_to(output_dir).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": _file_sha256(path),
            }
        )
    manifest = {
        "file_count": len(files),
        "total_size_bytes": sum(item["size_bytes"] for item in files),
        "files": files,
    }
    _json_dump(output_dir / "manifest.json", manifest)
    return manifest


def validate_corpus(
    output_dir: str | Path,
    contract: Mapping[str, Any],
    generation_config: Mapping[str, Any],
) -> dict[str, Any]:
    root = Path(output_dir)
    trajectory_dirs = sorted((root / "trajectories").glob("traj_*"))
    if not trajectory_dirs:
        raise TrajectoryError("corpus contains no trajectories")
    metadata_rows: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for directory in trajectory_dirs:
        validate_trajectory_directory(directory, contract, generation_config)
        metadata_rows.append(_json_load(directory / "metadata.json"))
        summaries.append(_json_load(directory / "summary.json"))
    validate_split_assignments(metadata_rows, contract)

    by_scenario: dict[str, set[str]] = {}
    by_seed: dict[int, set[str]] = {}
    for summary in summaries:
        fingerprint = str(summary["trajectory_fingerprint"])
        by_scenario.setdefault(str(summary["scenario_id"]), set()).add(fingerprint)
        by_seed.setdefault(int(summary["seed"]), set()).add(fingerprint)
    multi_seed_scenarios = [
        scenario for scenario in by_scenario if sum(s["scenario_id"] == scenario for s in summaries) > 1
    ]
    if any(len(by_scenario[scenario]) < 2 for scenario in multi_seed_scenarios):
        raise TrajectoryError("different seeds produced identical full trajectories for a scenario")
    scenario_count = len({summary["scenario_id"] for summary in summaries})
    if scenario_count > 1 and any(len(fingerprints) < scenario_count for fingerprints in by_seed.values()):
        raise TrajectoryError("different scenarios produced identical full trajectories for a seed")

    return {
        "trajectory_count": len(trajectory_dirs),
        "scenario_count": scenario_count,
        "seed_count": len({summary["seed"] for summary in summaries}),
        "trajectory_split_check": "passed",
        "seed_difference_check": "passed",
        "scenario_difference_check": "passed",
        "status": "valid",
    }


def generate_corpus(
    output_dir: str | Path,
    profile_name: str,
    config_path: str | Path = DEFAULT_CONFIG,
    scenarios: Sequence[str] | None = None,
    seeds: Sequence[int] | None = None,
    transitions_override: int | None = None,
    reproducibility_check: bool | None = None,
) -> dict[str, Any]:
    config = load_generation_config(config_path)
    if profile_name not in config["profiles"]:
        raise TrajectoryError(f"unknown profile {profile_name}")
    contract = load_contract(ROOT / config["contract_path"])
    profile = config["profiles"][profile_name]
    selected_scenarios = list(scenarios) if scenarios is not None else list(config["scenario_order"])
    unknown = set(selected_scenarios) - set(config["scenarios"])
    if unknown:
        raise TrajectoryError(f"unknown scenarios: {sorted(unknown)}")
    selected_seeds = list(seeds) if seeds is not None else list(profile["seeds"])
    if not selected_seeds or any(seed not in profile["seeds"] for seed in selected_seeds):
        raise TrajectoryError("selected seeds must be present in the profile")
    transitions = int(transitions_override) if transitions_override is not None else int(profile["transitions"])
    if transitions < 2:
        raise TrajectoryError("transitions must be >= 2")

    root = Path(output_dir)
    if root.exists():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)
    summaries: list[dict[str, Any]] = []
    for scenario_id in selected_scenarios:
        scenario = config["scenarios"][scenario_id]
        for seed in selected_seeds:
            summaries.append(
                generate_trajectory(
                    root,
                    profile_name,
                    scenario_id,
                    scenario,
                    seed,
                    transitions,
                    _profile_split(profile, seed),
                    config,
                    contract,
                )
            )

    _write_comparison_csv(root / "scenario_comparison.csv", summaries)
    _write_overview_svg(root / "trajectory_overview.svg", summaries)
    corpus_summary = {
        "task_id": config["task_id"],
        "profile": profile_name,
        "transitions_per_trajectory": transitions,
        "trajectory_count": len(summaries),
        "scenarios": selected_scenarios,
        "seeds": selected_seeds,
        "outcome_counts": {},
        "summaries": summaries,
    }
    for summary in summaries:
        label = summary["outcome"]["coarse_outcome"]
        corpus_summary["outcome_counts"][label] = corpus_summary["outcome_counts"].get(label, 0) + 1
    _json_dump(root / "corpus_summary.json", corpus_summary)
    validation = validate_corpus(root, contract, config)

    do_repro = bool(profile.get("reproducibility_check", False)) if reproducibility_check is None else reproducibility_check
    if do_repro:
        first = summaries[0]
        with tempfile.TemporaryDirectory(prefix="task3_2_2_repro_") as temporary:
            replay = generate_trajectory(
                Path(temporary),
                profile_name,
                str(first["scenario_id"]),
                config["scenarios"][str(first["scenario_id"])],
                int(first["seed"]),
                transitions,
                str(first["dataset_split"]),
                config,
                contract,
            )
        if replay["trajectory_fingerprint"] != first["trajectory_fingerprint"]:
            raise TrajectoryError("same scenario and seed failed deterministic replay")
        validation["reproducibility_check"] = "passed"
    else:
        validation["reproducibility_check"] = "not_run"

    _json_dump(root / "validation.json", validation)
    manifest = _write_manifest(root)
    return {
        "output_dir": str(root),
        "trajectory_count": len(summaries),
        "validation": validation,
        "manifest": manifest,
        "outcome_counts": corpus_summary["outcome_counts"],
    }


def _parse_csv_strings(value: str | None) -> list[str] | None:
    return None if value is None else [item.strip() for item in value.split(",") if item.strip()]


def _parse_csv_ints(value: str | None) -> list[int] | None:
    return None if value is None else [int(item.strip()) for item in value.split(",") if item.strip()]


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate = subparsers.add_parser("generate", help="generate and validate a trajectory corpus")
    generate.add_argument("--output", required=True)
    generate.add_argument("--profile", default="smoke")
    generate.add_argument("--config", default=str(DEFAULT_CONFIG))
    generate.add_argument("--scenarios", help="comma-separated scenario ids")
    generate.add_argument("--seeds", help="comma-separated seeds")
    generate.add_argument("--transitions", type=int)
    generate.add_argument("--skip-reproducibility-check", action="store_true")
    validate = subparsers.add_parser("validate", help="validate an existing corpus")
    validate.add_argument("--input", required=True)
    validate.add_argument("--config", default=str(DEFAULT_CONFIG))

    args = parser.parse_args(argv)
    if args.command == "generate":
        result = generate_corpus(
            args.output,
            args.profile,
            args.config,
            _parse_csv_strings(args.scenarios),
            _parse_csv_ints(args.seeds),
            args.transitions,
            False if args.skip_reproducibility_check else None,
        )
    else:
        config = load_generation_config(args.config)
        contract = load_contract(ROOT / config["contract_path"])
        result = validate_corpus(args.input, contract, config)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DEFAULT_CONFIG",
    "TrajectoryError",
    "generate_corpus",
    "generate_trajectory",
    "load_generation_config",
    "validate_corpus",
    "validate_generation_config",
    "validate_trajectory_directory",
]
