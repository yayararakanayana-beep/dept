"""Task 3.2-4.1 structural risk, shrinking equilibrium, and escape feasibility.

This task creates counterfactual branches from persisted PseudoReality v3.3
snapshots.  It measures whether a state can still reach a fit-calibrated safe
region under a bounded probe set.  The measured structural truths remain
future-side labels and never enter predictor features.

The task does not prove universal irreversibility, identify real players, write
back to the source trajectory, update the Parameter Box, or connect the Action
Module.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import average_precision_score, brier_score_loss, recall_score
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from pseudo_reality.distribution_terrain_v3_2_2 import (  # noqa: E402
    DistributionTerrainV322Config,
    DistributionTerrainV322World,
)
import task3_2_2_continuous_trajectory as t2  # noqa: E402
import task3_2_3_simple_early_warning as t3_public  # noqa: F401,E402
import _task3_2_3_core as t3  # noqa: E402
import task3_2_4_macro_dynamics as t4  # noqa: E402

DEFAULT_CONFIG = ROOT / "configs" / "task3_2_4_1_structural_risk.json"
EXTERNAL_FIELDS = tuple(t2.EXTERNAL_FIELDS)


class StructuralRiskError(ValueError):
    """Raised when Task 4.1 boundaries or artifacts are invalid."""


def _json_load(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _json_dump(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise StructuralRiskError(f"{path}:{line_number} must contain an object")
            rows.append(value)
    return rows


def _write_csv(path: str | Path, rows: Sequence[Mapping[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        target.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(str(key))
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_config(path: str | Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = _json_load(path)
    required = {
        "challenge",
        "representation_candidates",
        "fixed_macro_candidate",
        "snapshot_selection",
        "safe_region",
        "branch_probe",
        "structural_truth",
        "prediction",
        "split_contract",
        "forbidden_feature_tokens",
        "outputs",
    }
    missing = sorted(required - set(config))
    if missing:
        raise StructuralRiskError(f"Task 4.1 config missing {missing}")
    challenge = config["challenge"]
    seeds = challenge["fit_seeds"] + challenge["validation_seeds"] + challenge["holdout_seeds"]
    if len(seeds) != len(set(seeds)):
        raise StructuralRiskError("Task 4.1 seeds must be unique across splits")
    if "stable_continuation" not in challenge["condition_groups"]:
        raise StructuralRiskError("stable_continuation is required")
    branch = config["branch_probe"]
    if int(branch["replicate_count"]) < 1:
        raise StructuralRiskError("replicate_count must be positive")
    if set(branch["probe_families"]) != set(branch["action_axes"]):
        raise StructuralRiskError("every probe family requires an action-axis definition")
    if config["split_contract"].get("holdout_requires_validated_selection_lock") is not True:
        raise StructuralRiskError("holdout selection-lock gate must remain enabled")
    return config


@dataclass(frozen=True)
class Entry:
    trajectory_id: str
    scenario_id: str
    seed: int
    split: str
    path: Path
    total_steps: int


class CorpusIndex:
    """Metadata-only corpus index with a Task 4.1 holdout state-read gate."""

    def __init__(self, root: str | Path, config: Mapping[str, Any]):
        self.root = Path(root)
        self.config = config
        entries: list[Entry] = []
        for directory in sorted((self.root / "trajectories").glob("traj_*")):
            metadata = _json_load(directory / "metadata.json")
            entries.append(
                Entry(
                    trajectory_id=str(metadata["trajectory_id"]),
                    scenario_id=str(metadata["scenario_id"]),
                    seed=int(metadata["seed"]),
                    split=str(metadata["dataset_split"]),
                    path=directory,
                    total_steps=int(metadata["total_steps"]),
                )
            )
        if not entries:
            raise StructuralRiskError("Task 4.1 corpus contains no trajectories")
        self.entries = entries
        self._validate()

    def _validate(self) -> None:
        challenge = self.config["challenge"]
        expected = {
            "fit": set(int(value) for value in challenge["fit_seeds"]),
            "validation": set(int(value) for value in challenge["validation_seeds"]),
            "holdout": set(int(value) for value in challenge["holdout_seeds"]),
        }
        actual = {
            split: {entry.seed for entry in self.entries if entry.split == split}
            for split in expected
        }
        if actual != expected:
            raise StructuralRiskError(f"split mismatch: {actual} != {expected}")
        seed_splits: dict[int, set[str]] = {}
        for entry in self.entries:
            seed_splits.setdefault(entry.seed, set()).add(entry.split)
        if any(len(value) != 1 for value in seed_splits.values()):
            raise StructuralRiskError("one seed appears in multiple splits")
        required_scenarios = set(challenge["condition_groups"])
        for seed in sorted(seed_splits):
            observed = {entry.scenario_id for entry in self.entries if entry.seed == seed}
            if observed != required_scenarios:
                raise StructuralRiskError(f"seed {seed} does not cover every Task 4.1 condition")

    def entries_for(
        self,
        split: str,
        *,
        lock_path: str | Path | None = None,
        validation_path: str | Path | None = None,
    ) -> list[Entry]:
        if split == "holdout":
            if lock_path is None or validation_path is None:
                raise StructuralRiskError("Task 4.1 holdout state read blocked before lock validation")
            validate_selection_lock(lock_path, validation_path)
        return [entry for entry in self.entries if entry.split == split]

    def split_manifest(self) -> dict[str, Any]:
        return {
            "trajectory_count": len(self.entries),
            "splits": {
                split: {
                    "seeds": sorted({entry.seed for entry in self.entries if entry.split == split}),
                    "trajectory_ids": sorted(
                        entry.trajectory_id for entry in self.entries if entry.split == split
                    ),
                }
                for split in ("fit", "validation", "holdout")
            },
            "branch_inherits_source_split": True,
            "random_branch_split": False,
        }


def _to_t4_entry(entry: Entry) -> t4.Entry:
    return t4.Entry(
        trajectory_id=entry.trajectory_id,
        scenario_id=entry.scenario_id,
        seed=entry.seed,
        split=entry.split,
        path=entry.path,
        total_steps=entry.total_steps,
    )


def _to_t3_entry(entry: Entry) -> t3.CorpusEntry:
    return t3.CorpusEntry(
        trajectory_id=entry.trajectory_id,
        scenario_id=entry.scenario_id,
        seed=entry.seed,
        split=entry.split,
        path=entry.path,
        total_steps=entry.total_steps,
    )


def _weighted(distribution: np.ndarray, value: np.ndarray) -> float:
    return float(np.sum(distribution * value))


def _metrics_from_arrays(bundle: Mapping[str, Any]) -> dict[str, float]:
    distribution = np.asarray(bundle["distribution"], dtype=np.float64)
    entropy = -float(np.sum(distribution * np.log(np.maximum(distribution, 1e-12))))
    names = (
        "damage",
        "rigidity",
        "friction",
        "viscosity",
        "recovery_speed",
        "route_support",
        "viability_reserve",
        "negative_viability_pressure",
        "maintenance_cost",
        "operating_cost",
        "exploration_cost",
        "expected_value_advantage",
        "net_viability_value",
        "effective_medium_payoff",
    )
    weighted = {
        name: _weighted(distribution, np.asarray(bundle[name], dtype=np.float64))
        for name in names
    }
    risk = (
        0.20 * weighted["damage"]
        + 0.15 * weighted["rigidity"]
        + 0.15 * weighted["friction"]
        + 0.10 * weighted["viscosity"]
        + 0.15 * (1.0 - weighted["recovery_speed"])
        + 0.10 * (1.0 - weighted["route_support"])
        + 0.05 * (1.0 - weighted["viability_reserve"])
        + 0.10 * weighted["negative_viability_pressure"]
    )
    current_value = (
        0.30 * weighted["net_viability_value"]
        + 0.18 * weighted["route_support"]
        + 0.14 * weighted["viability_reserve"]
        + 0.12 * weighted["expected_value_advantage"]
        + 0.12 * weighted["effective_medium_payoff"]
        + 0.06 * weighted["recovery_speed"]
        - 0.12 * weighted["maintenance_cost"]
        - 0.10 * weighted["operating_cost"]
        - 0.08 * weighted["exploration_cost"]
        - 0.18 * weighted["negative_viability_pressure"]
    )
    return {
        "risk_score": float(risk),
        "current_value": float(current_value),
        "entropy": entropy,
        "concentration": float(np.sum(distribution**2)),
        "weighted_damage": weighted["damage"],
        "weighted_rigidity": weighted["rigidity"],
        "weighted_friction": weighted["friction"],
        "weighted_viscosity": weighted["viscosity"],
        "weighted_recovery_speed": weighted["recovery_speed"],
        "weighted_route_support": weighted["route_support"],
        "weighted_viability_reserve": weighted["viability_reserve"],
        "weighted_negative_viability_pressure": weighted["negative_viability_pressure"],
        "weighted_maintenance_cost": weighted["maintenance_cost"],
        "weighted_operating_cost": weighted["operating_cost"],
        "weighted_exploration_cost": weighted["exploration_cost"],
    }


def _metrics_from_world(world: DistributionTerrainV322World) -> dict[str, float]:
    names = [
        "distribution",
        "damage",
        "rigidity",
        "friction",
        "viscosity",
        "recovery_speed",
        "route_support",
        "viability_reserve",
        "negative_viability_pressure",
        "maintenance_cost",
        "operating_cost",
        "exploration_cost",
        "expected_value_advantage",
        "net_viability_value",
        "effective_medium_payoff",
    ]
    return _metrics_from_arrays({name: getattr(world, name) for name in names})


def calibrate_safe_region(entries: Sequence[Entry], config: Mapping[str, Any]) -> dict[str, Any]:
    reference = str(config["safe_region"]["reference_scenario"])
    rows: list[dict[str, float]] = []
    for entry in entries:
        if entry.scenario_id != reference:
            continue
        steps = _read_jsonl(entry.path / "steps.jsonl")
        for record in steps:
            with np.load(entry.path / str(record["state_ref"]), allow_pickle=False) as bundle:
                rows.append(_metrics_from_arrays(bundle))
    if not rows:
        raise StructuralRiskError("safe-region calibration has no fit stable-reference rows")
    frame = pd.DataFrame(rows)
    settings = config["safe_region"]
    lower_q = float(settings["lower_quantile"])
    upper_q = float(settings["upper_quantile"])
    risk_q = float(settings["risk_quantile"])
    margin = float(settings["numeric_margin"])
    return {
        "source": "fit stable_continuation only",
        "row_count": len(frame),
        "risk_max": float(frame["risk_score"].quantile(risk_q) + margin),
        "current_value_min": float(frame["current_value"].quantile(lower_q) - margin),
        "damage_max": float(frame["weighted_damage"].quantile(upper_q) + margin),
        "negative_pressure_max": float(
            frame["weighted_negative_viability_pressure"].quantile(upper_q) + margin
        ),
        "route_support_min": float(frame["weighted_route_support"].quantile(lower_q) - margin),
        "recovery_speed_min": float(frame["weighted_recovery_speed"].quantile(lower_q) - margin),
        "viability_reserve_min": float(frame["weighted_viability_reserve"].quantile(lower_q) - margin),
        "sustained_steps": int(settings["sustained_steps"]),
        "post_action_followup_steps": int(settings["post_action_followup_steps"]),
        "fit_only": True,
    }


def safe_state(metrics: Mapping[str, float], safe: Mapping[str, Any]) -> bool:
    mandatory = (
        float(metrics["risk_score"]) <= float(safe["risk_max"])
        and float(metrics["current_value"]) >= float(safe["current_value_min"])
    )
    supporting = [
        float(metrics["weighted_damage"]) <= float(safe["damage_max"]),
        float(metrics["weighted_negative_viability_pressure"])
        <= float(safe["negative_pressure_max"]),
        float(metrics["weighted_route_support"]) >= float(safe["route_support_min"]),
        float(metrics["weighted_recovery_speed"]) >= float(safe["recovery_speed_min"]),
        float(metrics["weighted_viability_reserve"]) >= float(safe["viability_reserve_min"]),
    ]
    return bool(mandatory and sum(bool(value) for value in supporting) >= 4)


def _restore_world(
    entry: Entry,
    step_record: Mapping[str, Any],
    replicate: int,
    config: Mapping[str, Any],
) -> DistributionTerrainV322World:
    branch_seed = int(entry.seed * 100_003 + int(step_record["step"]) * 101 + replicate)
    world = DistributionTerrainV322World(DistributionTerrainV322Config(seed=branch_seed))
    state_path = entry.path / str(step_record["state_ref"])
    with np.load(state_path, allow_pickle=False) as bundle:
        for name in bundle.files:
            value = np.asarray(bundle[name])
            if value.shape == world.shape:
                setattr(world, name, np.asarray(value, dtype=np.float64).copy())
            elif value.ndim == 0:
                setattr(world, name, float(value))
    noise_scale = float(config["branch_probe"]["replicate_distribution_noise"])
    if noise_scale > 0.0:
        rng = np.random.default_rng(branch_seed)
        world.distribution = np.maximum(
            world.distribution + rng.normal(0.0, noise_scale, world.shape),
            0.0,
        )
        world._normalize_distribution()
    world.t = int(step_record["step"])
    world.previous_total_gain = world._distribution_weighted_base_composite()
    world._distribution_trace = []
    world._terrain_trace = []
    world._flow_trace = []
    world._external_trace = []
    world._auxiliary_trace = []
    return world


def _neutral_input() -> dict[str, float]:
    return {name: 0.0 for name in EXTERNAL_FIELDS}


def action_input(
    current: Mapping[str, float], family: str, strength: float
) -> dict[str, float]:
    values = {name: float(current.get(name, 0.0)) for name in EXTERNAL_FIELDS}
    strength = float(np.clip(strength, 0.0, 1.0))
    if family == "no_action":
        return values
    if family in {"resource_relief", "combined_relief"}:
        values["external_resource_supply"] = float(
            np.clip(values["external_resource_supply"] + strength * (1.0 - values["external_resource_supply"]), -1.0, 1.0)
        )
        values["external_demand"] = float(
            np.clip(values["external_demand"] - strength * (values["external_demand"] + 1.0), -1.0, 1.0)
        )
    if family in {"constraint_relief", "combined_relief"}:
        values["external_competition_pressure"] *= 1.0 - strength
        values["external_constraint_pressure"] *= 1.0 - strength
    if family in {"information_relief", "combined_relief"}:
        values["external_information_noise"] *= 1.0 - strength
        values["external_shock"] *= 1.0 - strength
    if family not in {
        "resource_relief",
        "constraint_relief",
        "information_relief",
        "combined_relief",
    }:
        raise StructuralRiskError(f"unknown probe family {family}")
    return {name: float(np.clip(value, -1.0 if name in EXTERNAL_FIELDS[:2] else 0.0, 1.0)) for name, value in values.items()}


def _first_sustained_safe(flags: Sequence[bool], length: int) -> int | None:
    run = 0
    for index, flag in enumerate(flags):
        run = run + 1 if flag else 0
        if run >= length:
            return index - length + 1
    return None


def run_branch(
    entry: Entry,
    step_record: Mapping[str, Any],
    safe: Mapping[str, Any],
    family: str,
    strength: float,
    delay: int,
    replicate: int,
    config: Mapping[str, Any],
) -> dict[str, Any]:
    world = _restore_world(entry, step_record, replicate, config)
    current_input = {
        name: float(step_record["observed_external_input"][name]) for name in EXTERNAL_FIELDS
    }
    branch_settings = config["branch_probe"]
    duration = int(branch_settings["action_duration_steps"])
    followup = int(safe["post_action_followup_steps"])
    timeline: list[dict[str, float]] = [_metrics_from_world(world)]
    phase_rows: list[str] = ["snapshot"]

    for _ in range(int(delay)):
        world.set_external_factors(current_input)
        world.step()
        timeline.append(_metrics_from_world(world))
        phase_rows.append("delay")

    applied = current_input if family == "no_action" else action_input(current_input, family, strength)
    for _ in range(duration):
        world.set_external_factors(applied)
        world.step()
        timeline.append(_metrics_from_world(world))
        phase_rows.append("action" if family != "no_action" else "no_action")

    neutral = _neutral_input()
    for _ in range(followup):
        world.set_external_factors(neutral)
        world.step()
        timeline.append(_metrics_from_world(world))
        phase_rows.append("followup")

    safe_flags = [safe_state(row, safe) for row in timeline]
    first_safe = _first_sustained_safe(safe_flags, int(safe["sustained_steps"]))
    final_safe = bool(all(safe_flags[-int(safe["sustained_steps"]):]))
    ever_safe = first_safe is not None
    refixation = bool(ever_safe and not final_safe)
    axes = len(config["branch_probe"]["action_axes"][family])
    weights = config["branch_probe"]["cost_weights"]
    active_strength = 0.0 if family == "no_action" else float(strength)
    action_cost = (
        active_strength
        * axes
        * duration
        * float(weights["intensity_axis_step"])
    )
    recovery_time = len(timeline) if first_safe is None else int(first_safe)
    peak_risk = max(float(row["risk_score"]) for row in timeline)
    total_cost = (
        action_cost
        + recovery_time * float(weights["time_to_recovery"])
        + peak_risk * float(weights["peak_risk"])
        + int(refixation) * float(weights["refixation"])
    )
    final = timeline[-1]
    branch_id = (
        f"{entry.trajectory_id}__s{int(step_record['step']):03d}__{family}"
        f"__q{strength:.2f}__d{int(delay):02d}__r{replicate:02d}"
    )
    return {
        "branch_id": branch_id,
        "trajectory_id": entry.trajectory_id,
        "scenario_id": entry.scenario_id,
        "source_seed": entry.seed,
        "source_split": entry.split,
        "snapshot_step": int(step_record["step"]),
        "probe_family": family,
        "strength": float(strength),
        "delay_steps": int(delay),
        "replicate": int(replicate),
        "simultaneous_action_scale": axes,
        "recovered": int(final_safe),
        "ever_safe": int(ever_safe),
        "refixation": int(refixation),
        "recovery_time_steps": recovery_time,
        "action_cost": float(action_cost),
        "total_escape_cost": float(total_cost),
        "peak_risk": peak_risk,
        "initial_risk": float(timeline[0]["risk_score"]),
        "initial_current_value": float(timeline[0]["current_value"]),
        "final_risk": float(final["risk_score"]),
        "final_current_value": float(final["current_value"]),
        "final_route_support": float(final["weighted_route_support"]),
        "final_recovery_speed": float(final["weighted_recovery_speed"]),
        "final_concentration": float(final["concentration"]),
        "state_writeback": 0,
        "parameter_write": 0,
        "action_module_connection": 0,
    }


def snapshot_records(entry: Entry, config: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = _read_jsonl(entry.path / "steps.jsonl")
    wanted = set(int(value) for value in config["snapshot_selection"]["steps"])
    selected = [row for row in rows if int(row["step"]) in wanted]
    maximum = int(config["snapshot_selection"]["maximum_snapshots_per_trajectory"])
    return selected[:maximum]


def generate_branch_rows(
    entries: Sequence[Entry], safe: Mapping[str, Any], config: Mapping[str, Any]
) -> list[dict[str, Any]]:
    settings = config["branch_probe"]
    rows: list[dict[str, Any]] = []
    for entry in entries:
        for step_record in snapshot_records(entry, config):
            for replicate in range(int(settings["replicate_count"])):
                rows.append(
                    run_branch(entry, step_record, safe, "no_action", 0.0, 0, replicate, config)
                )
                for family in settings["probe_families"]:
                    if family == "no_action":
                        continue
                    for strength in settings["strengths"]:
                        for delay in settings["delays"]:
                            rows.append(
                                run_branch(
                                    entry,
                                    step_record,
                                    safe,
                                    str(family),
                                    float(strength),
                                    int(delay),
                                    replicate,
                                    config,
                                )
                            )
    return rows


def _group_frontier(branch_rows: Sequence[Mapping[str, Any]], config: Mapping[str, Any]) -> pd.DataFrame:
    frame = pd.DataFrame(branch_rows)
    keys = [
        "trajectory_id",
        "scenario_id",
        "source_seed",
        "source_split",
        "snapshot_step",
        "probe_family",
        "strength",
        "delay_steps",
        "simultaneous_action_scale",
    ]
    grouped = frame.groupby(keys, sort=False, dropna=False)
    rows: list[dict[str, Any]] = []
    for key, group in grouped:
        row = dict(zip(keys, key, strict=True))
        row.update(
            {
                "replicate_count": len(group),
                "recovery_probability": float(group["recovered"].mean()),
                "ever_safe_probability": float(group["ever_safe"].mean()),
                "refixation_probability": float(group["refixation"].mean()),
                "mean_escape_cost": float(group["total_escape_cost"].mean()),
                "mean_recovery_time": float(group["recovery_time_steps"].mean()),
                "mean_final_risk": float(group["final_risk"].mean()),
                "mean_final_current_value": float(group["final_current_value"].mean()),
                "mean_final_route_support": float(group["final_route_support"].mean()),
                "mean_final_recovery_speed": float(group["final_recovery_speed"].mean()),
                "mean_final_concentration": float(group["final_concentration"].mean()),
                "initial_risk": float(group["initial_risk"].mean()),
                "initial_current_value": float(group["initial_current_value"].mean()),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def _reachable_range(group: pd.DataFrame) -> float:
    columns = [
        "mean_final_risk",
        "mean_final_current_value",
        "mean_final_route_support",
        "mean_final_recovery_speed",
        "mean_final_concentration",
    ]
    matrix = group[columns].to_numpy(dtype=np.float64)
    if len(matrix) < 2:
        return 0.0
    scale = np.asarray([0.2, 0.2, 0.2, 0.1, 0.01], dtype=np.float64)
    normalized = matrix / np.maximum(scale, 1e-12)
    distances: list[float] = []
    for left in range(len(normalized)):
        for right in range(left + 1, len(normalized)):
            distances.append(float(np.linalg.norm(normalized[left] - normalized[right])))
    diversity = group.loc[group["recovery_probability"] > 0.0, "probe_family"].nunique() / 4.0
    return float((np.mean(distances) if distances else 0.0) + diversity)


def structural_truth_from_frontier(
    frontier: pd.DataFrame, config: Mapping[str, Any]
) -> pd.DataFrame:
    threshold = float(config["structural_truth"]["recovery_probability_threshold"])
    rows: list[dict[str, Any]] = []
    group_keys = [
        "trajectory_id",
        "scenario_id",
        "source_seed",
        "source_split",
        "snapshot_step",
    ]
    for key, group in frontier.groupby(group_keys, sort=False):
        successful = group[group["recovery_probability"] >= threshold].copy()
        failure_cost = float(group["mean_escape_cost"].max() + 1.0)
        if successful.empty:
            minimum_cost = failure_cost
            best_row = None
            last_window = -1
            minimum_scale = 7
            refixation = 1.0
            level = 4
        else:
            successful = successful.sort_values(
                ["mean_escape_cost", "strength", "simultaneous_action_scale", "delay_steps"]
            )
            best_row = successful.iloc[0]
            minimum_cost = float(best_row["mean_escape_cost"])
            last_window = int(successful["delay_steps"].max())
            minimum_scale = int(successful["simultaneous_action_scale"].min())
            refixation = float(best_row["refixation_probability"])
            no_action = successful[successful["probe_family"] == "no_action"]
            if not no_action.empty:
                level = 0
            elif float(best_row["strength"]) <= 0.35 and minimum_scale <= 2:
                level = 1
            elif float(best_row["strength"]) <= 0.70:
                level = 2
            else:
                level = 3
        no_action_rows = group[group["probe_family"] == "no_action"]
        no_action_value = float(no_action_rows["mean_final_current_value"].mean())
        initial_value = float(group["initial_current_value"].iloc[0])
        current_maintenance = max(0.0, initial_value - no_action_value)
        current_maintenance += 0.5 * float(no_action_rows["mean_final_risk"].mean())
        rows.append(
            {
                "trajectory_id": key[0],
                "scenario_id": key[1],
                "seed": int(key[2]),
                "split": key[3],
                "snapshot_step": int(key[4]),
                "current_value": initial_value,
                "current_risk": float(group["initial_risk"].iloc[0]),
                "maintenance_cost": float(current_maintenance),
                "minimum_escape_cost": minimum_cost,
                "escape_not_observed": int(successful.empty),
                "best_recovery_probability": float(group["recovery_probability"].max()),
                "reachable_value": float(group["mean_final_current_value"].max()),
                "reachable_range": _reachable_range(group),
                "last_action_window": last_window,
                "refixation_probability": refixation,
                "minimum_simultaneous_action_scale": minimum_scale,
                "provisional_irreversibility_level": level,
                "best_probe_family": None if best_row is None else str(best_row["probe_family"]),
                "best_probe_strength": None if best_row is None else float(best_row["strength"]),
                "best_probe_delay": None if best_row is None else int(best_row["delay_steps"]),
            }
        )
    result = pd.DataFrame(rows)
    result = label_shrinking_equilibrium(result, config)
    return result


def label_shrinking_equilibrium(frame: pd.DataFrame, config: Mapping[str, Any]) -> pd.DataFrame:
    settings = config["structural_truth"]
    output_rows: list[dict[str, Any]] = []
    for _, group in frame.groupby("trajectory_id", sort=False):
        group = group.sort_values("snapshot_step")
        previous: Mapping[str, Any] | None = None
        for row in group.to_dict(orient="records"):
            row = dict(row)
            if previous is None:
                row.update(
                    {
                        "current_value_slope": 0.0,
                        "escape_cost_delta": 0.0,
                        "reachable_value_delta": 0.0,
                        "reachable_range_delta": 0.0,
                        "last_action_window_delta": 0.0,
                        "shrinking_evidence_count": 0,
                        "shrinking_equilibrium_candidate": 0,
                    }
                )
            else:
                step_delta = max(int(row["snapshot_step"]) - int(previous["snapshot_step"]), 1)
                current_slope = (float(row["current_value"]) - float(previous["current_value"])) / step_delta
                escape_delta = float(row["minimum_escape_cost"]) - float(previous["minimum_escape_cost"])
                reachable_value_delta = float(row["reachable_value"]) - float(previous["reachable_value"])
                range_delta = float(row["reachable_range"]) - float(previous["reachable_range"])
                window_delta = float(row["last_action_window"]) - float(previous["last_action_window"])
                evidence = [
                    escape_delta >= float(settings["shrinking_escape_cost_increase"]),
                    reachable_value_delta <= -float(settings["shrinking_reachable_value_decline"]),
                    range_delta <= -float(settings["shrinking_reachable_range_decline"]),
                    window_delta <= -float(settings["shrinking_last_window_decline_steps"]),
                    float(row["maintenance_cost"]) > float(previous["maintenance_cost"]) + 0.01,
                ]
                stable = abs(current_slope) <= float(
                    settings["shrinking_current_value_slope_tolerance"]
                )
                evidence_count = sum(bool(value) for value in evidence)
                row.update(
                    {
                        "current_value_slope": current_slope,
                        "escape_cost_delta": escape_delta,
                        "reachable_value_delta": reachable_value_delta,
                        "reachable_range_delta": range_delta,
                        "last_action_window_delta": window_delta,
                        "shrinking_evidence_count": evidence_count,
                        "shrinking_equilibrium_candidate": int(
                            stable and evidence_count >= int(settings["minimum_evidence_count"])
                        ),
                    }
                )
            output_rows.append(row)
            previous = row
    return pd.DataFrame(output_rows)


def _load_series(
    entries: Sequence[Entry], task3_config: Mapping[str, Any], calibration: Mapping[str, Any]
) -> list[t3.TrajectorySeries]:
    series = [t3.load_trajectory_series(_to_t3_entry(entry), task3_config) for entry in entries]
    t3.attach_future_truth(series, task3_config, calibration)
    return series


def feature_frame(
    fit_entries: Sequence[Entry],
    target_entries: Sequence[Entry],
    truth: pd.DataFrame,
    config: Mapping[str, Any],
    task3_config: Mapping[str, Any],
    calibration: Mapping[str, Any],
    required_arrays: Sequence[str],
    *,
    preprocessor: t4.MacroPreprocessor | None = None,
    dynamics: t4.DynamicsModel | None = None,
    fit_series: Sequence[t3.TrajectorySeries] | None = None,
) -> tuple[pd.DataFrame, t4.MacroPreprocessor, t4.DynamicsModel, list[str], list[str]]:
    macro_settings = config["fixed_macro_candidate"]
    if fit_series is None:
        fit_series = _load_series(fit_entries, task3_config, calibration)
    target_series = _load_series(target_entries, task3_config, calibration)
    fit_by_id = {item.entry.trajectory_id: item for item in fit_series}
    target_by_id = {item.entry.trajectory_id: item for item in target_series}
    fit_t4_entries = [_to_t4_entry(entry) for entry in fit_entries]
    target_t4_entries = [_to_t4_entry(entry) for entry in target_entries]
    if preprocessor is None:
        preprocessor = t4.MacroPreprocessor(
            str(macro_settings["input_scope"]), config, required_arrays
        ).fit(fit_t4_entries)
    latent_fit = preprocessor.transform(fit_t4_entries)
    latent_target = preprocessor.transform(target_t4_entries)
    if dynamics is None:
        dynamics = t4.DynamicsModel(
            str(macro_settings["dynamics_family"]),
            int(macro_settings["latent_dimension"]),
            config,
        ).fit(latent_fit, fit_by_id)
    macro, _ = t4.macro_feature_frame(
        target_t4_entries,
        target_by_id,
        latent_target,
        dynamics,
        int(macro_settings["latent_dimension"]),
        int(macro_settings["prediction_horizon"]),
    )
    macro_names = sorted(name for name in macro.columns if name.startswith("macro_"))
    history_width = int(macro_settings["history_width"])
    task3_rows: list[dict[str, Any]] = []
    task3_names: list[str] | None = None
    for item in target_series:
        steps = set(
            int(value)
            for value in truth.loc[
                truth["trajectory_id"] == item.entry.trajectory_id, "snapshot_step"
            ].tolist()
        )
        for step in sorted(steps):
            values = t3.feature_vector_at(item, step, history_width, task3_config)
            if task3_names is None:
                task3_names = sorted(values)
            elif sorted(values) != task3_names:
                raise StructuralRiskError("Task 3 feature schema changed")
            task3_rows.append({"trajectory_id": item.entry.trajectory_id, "snapshot_step": step, **values})
    if task3_names is None:
        raise StructuralRiskError("no Task 3 features were built")
    task3_frame = pd.DataFrame(task3_rows)
    macro = macro.rename(columns={"step": "snapshot_step"})
    merged = truth.merge(task3_frame, on=["trajectory_id", "snapshot_step"], validate="one_to_one")
    merged = merged.merge(
        macro[["trajectory_id", "snapshot_step", *macro_names]],
        on=["trajectory_id", "snapshot_step"],
        validate="one_to_one",
    )
    audit_feature_names(task3_names + macro_names, config)
    return merged, preprocessor, dynamics, task3_names, macro_names


def audit_feature_names(names: Iterable[str], config: Mapping[str, Any]) -> None:
    forbidden = [str(token).lower() for token in config["forbidden_feature_tokens"]]
    leaked = sorted(
        str(name) for name in names if any(token in str(name).lower() for token in forbidden)
    )
    if leaked:
        raise StructuralRiskError(f"future/metadata tokens leaked into features: {leaked}")


def _feature_names(
    family: str, task3_names: Sequence[str], macro_names: Sequence[str]
) -> list[str]:
    if family == "current_risk":
        return ["current__risk_score"]
    if family == "task3":
        return list(task3_names)
    if family == "task4":
        return list(macro_names)
    if family == "task3_plus_task4":
        return list(task3_names) + list(macro_names)
    raise StructuralRiskError(f"unknown predictor family {family}")


def _fit_continuous(X: np.ndarray, y: np.ndarray, config: Mapping[str, Any]) -> Any:
    if np.allclose(y, y[0]):
        return {"kind": "constant", "value": float(y[0])}
    return Ridge(alpha=float(config["prediction"]["ridge_alpha"])).fit(X, y)


def _predict_continuous(model: Any, X: np.ndarray) -> np.ndarray:
    if isinstance(model, dict):
        return np.full(len(X), float(model["value"]), dtype=np.float64)
    return np.asarray(model.predict(X), dtype=np.float64)


def fit_predictor(
    frame: pd.DataFrame, features: Sequence[str], config: Mapping[str, Any]
) -> dict[str, Any]:
    X = frame[list(features)].to_numpy(dtype=np.float64)
    scaler = StandardScaler().fit(X)
    transformed = scaler.transform(X)
    targets = list(config["prediction"]["targets"])
    models: dict[str, Any] = {}
    for target in targets:
        y = frame[target].to_numpy(dtype=np.float64)
        if target == "shrinking_equilibrium_candidate":
            classes = np.unique(y.astype(int))
            if len(classes) < 2:
                models[target] = {"kind": "constant_probability", "value": float(np.mean(y))}
            else:
                models[target] = LogisticRegression(
                    C=float(config["prediction"]["logistic_C"]),
                    max_iter=3000,
                    class_weight="balanced",
                    random_state=int(config["prediction"]["random_state"]),
                ).fit(transformed, y.astype(int))
        else:
            models[target] = _fit_continuous(transformed, y, config)
    return {"features": list(features), "scaler": scaler, "models": models}


def predict(model: Mapping[str, Any], frame: pd.DataFrame, config: Mapping[str, Any]) -> pd.DataFrame:
    X = frame[list(model["features"])].to_numpy(dtype=np.float64)
    transformed = model["scaler"].transform(X)
    output = frame[["trajectory_id", "scenario_id", "seed", "split", "snapshot_step"]].copy()
    max_delay = max(int(value) for value in config["branch_probe"]["delays"])
    for target, fitted in model["models"].items():
        if target == "shrinking_equilibrium_candidate":
            if isinstance(fitted, dict):
                values = np.full(len(frame), float(fitted["value"]), dtype=np.float64)
            else:
                values = fitted.predict_proba(transformed)[:, 1]
        else:
            values = _predict_continuous(fitted, transformed)
            if target in {
                "minimum_escape_cost",
                "best_recovery_probability",
                "reachable_range",
                "refixation_probability",
                "minimum_simultaneous_action_scale",
            }:
                values = np.maximum(values, 0.0)
            if target in {"best_recovery_probability", "refixation_probability"}:
                values = np.clip(values, 0.0, 1.0)
            if target == "last_action_window":
                values = np.clip(values, -1.0, float(max_delay))
            if target == "minimum_simultaneous_action_scale":
                values = np.clip(values, 0.0, 7.0)
            if target == "provisional_irreversibility_level":
                values = np.clip(values, 0.0, 4.0)
        output[f"predicted__{target}"] = values
        output[f"actual__{target}"] = frame[target].to_numpy(dtype=np.float64)
    return output


def _safe_spearman(actual: Sequence[float], predicted: Sequence[float]) -> float:
    a = np.asarray(actual, dtype=np.float64)
    p = np.asarray(predicted, dtype=np.float64)
    if len(a) < 2 or np.allclose(a, a[0]) or np.allclose(p, p[0]):
        return 0.0
    value = spearmanr(a, p).statistic
    return 0.0 if value is None or not math.isfinite(float(value)) else float(value)


def evaluate_predictions(predictions: pd.DataFrame) -> dict[str, Any]:
    actual_shrink = predictions["actual__shrinking_equilibrium_candidate"].to_numpy(dtype=int)
    shrink_probability = predictions["predicted__shrinking_equilibrium_candidate"].to_numpy(dtype=float)
    if int(actual_shrink.sum()) == 0:
        ap = 0.0
        recall = 0.0
    elif int(actual_shrink.sum()) == len(actual_shrink):
        ap = 1.0
        recall = float(np.mean(shrink_probability >= 0.5))
    else:
        ap = float(average_precision_score(actual_shrink, shrink_probability))
        recall = float(recall_score(actual_shrink, shrink_probability >= 0.5, zero_division=0))
    false_alarm = float(
        np.mean((shrink_probability >= 0.5)[actual_shrink == 0])
        if np.any(actual_shrink == 0)
        else 0.0
    )
    actual_escape = predictions["actual__minimum_escape_cost"].to_numpy(dtype=float)
    predicted_escape = predictions["predicted__minimum_escape_cost"].to_numpy(dtype=float)
    actual_window = predictions["actual__last_action_window"].to_numpy(dtype=float)
    predicted_window = predictions["predicted__last_action_window"].to_numpy(dtype=float)
    actual_level = predictions["actual__provisional_irreversibility_level"].to_numpy(dtype=float)
    predicted_level = np.rint(
        predictions["predicted__provisional_irreversibility_level"].to_numpy(dtype=float)
    )
    return {
        "row_count": len(predictions),
        "shrinking_positive_count": int(actual_shrink.sum()),
        "shrinking_average_precision": ap,
        "shrinking_recall": recall,
        "shrinking_false_alarm_rate": false_alarm,
        "shrinking_brier_score": float(brier_score_loss(actual_shrink, shrink_probability)),
        "escape_cost_mae": float(np.mean(np.abs(predicted_escape - actual_escape))),
        "escape_cost_rank_correlation": _safe_spearman(actual_escape, predicted_escape),
        "recovery_probability_mae": float(
            np.mean(
                np.abs(
                    predictions["predicted__best_recovery_probability"]
                    - predictions["actual__best_recovery_probability"]
                )
            )
        ),
        "reachable_value_mae": float(
            np.mean(
                np.abs(
                    predictions["predicted__reachable_value"]
                    - predictions["actual__reachable_value"]
                )
            )
        ),
        "reachable_range_mae": float(
            np.mean(
                np.abs(
                    predictions["predicted__reachable_range"]
                    - predictions["actual__reachable_range"]
                )
            )
        ),
        "last_action_window_mae": float(np.mean(np.abs(predicted_window - actual_window))),
        "refixation_probability_mae": float(
            np.mean(
                np.abs(
                    predictions["predicted__refixation_probability"]
                    - predictions["actual__refixation_probability"]
                )
            )
        ),
        "simultaneous_action_scale_mae": float(
            np.mean(
                np.abs(
                    predictions["predicted__minimum_simultaneous_action_scale"]
                    - predictions["actual__minimum_simultaneous_action_scale"]
                )
            )
        ),
        "irreversibility_exact_accuracy": float(np.mean(predicted_level == actual_level)),
        "irreversibility_adjacent_accuracy": float(np.mean(np.abs(predicted_level - actual_level) <= 1.0)),
    }


def _selection_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        float(row["shrinking_average_precision"]),
        float(row["shrinking_recall"]),
        float(row["escape_cost_rank_correlation"]),
        -float(row["last_action_window_mae"]),
        float(row["irreversibility_adjacent_accuracy"]),
        -int(row["feature_count"]),
    )


def _create_lock(
    path: Path,
    selected: Mapping[str, Any],
    safe: Mapping[str, Any],
    config: Mapping[str, Any],
    structural_truth_hash: str,
) -> dict[str, Any]:
    payload = {
        "task_id": config["task_id"],
        "status": "locked_before_holdout_state_read",
        "selected_candidate": dict(selected),
        "safe_region_hash": _canonical_hash(safe),
        "fit_validation_structural_truth_hash": structural_truth_hash,
        "config_hash": _canonical_hash(config),
        "predictor_refit_on_fit_plus_validation": True,
        "macro_preprocessor_remains_fit_only": True,
        "post_holdout_reselection_forbidden": True,
    }
    payload["lock_hash"] = _canonical_hash(payload)
    _json_dump(path, payload)
    return payload


def _write_lock_validation(path: Path, lock: Mapping[str, Any]) -> dict[str, Any]:
    body = dict(lock)
    claimed = body.pop("lock_hash")
    actual = _canonical_hash(body)
    validation = {
        "valid": claimed == actual,
        "claimed_lock_hash": claimed,
        "lock_hash": actual,
        "holdout_state_not_read_before_validation": True,
    }
    _json_dump(path, validation)
    if not validation["valid"]:
        raise StructuralRiskError("Task 4.1 lock validation failed")
    return validation


def validate_selection_lock(lock_path: str | Path, validation_path: str | Path) -> dict[str, Any]:
    lock = _json_load(lock_path)
    validation = _json_load(validation_path)
    body = dict(lock)
    claimed = body.pop("lock_hash", None)
    actual = _canonical_hash(body)
    if claimed != actual:
        raise StructuralRiskError("Task 4.1 selection lock hash mismatch")
    if validation.get("valid") is not True or validation.get("lock_hash") != actual:
        raise StructuralRiskError("Task 4.1 selection lock is not independently valid")
    return lock


def _bar_svg(path: Path, title: str, labels: Sequence[str], values: Sequence[float]) -> None:
    width = 1000
    height = 80 + 32 * len(labels)
    maximum = max([abs(float(value)) for value in values] + [1e-12])
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="20" y="30" font-family="sans-serif" font-size="18">{title}</text>',
    ]
    for index, (label, value) in enumerate(zip(labels, values, strict=True)):
        y = 55 + index * 32
        bar = 500.0 * max(0.0, float(value)) / maximum
        lines.append(f'<text x="20" y="{y+17}" font-family="sans-serif" font-size="12">{label}</text>')
        lines.append(f'<rect x="400" y="{y}" width="{bar:.2f}" height="20" fill="#777"/>')
        lines.append(f'<text x="920" y="{y+17}" font-family="monospace" font-size="12">{float(value):.6g}</text>')
    lines.append("</svg>\n")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_manifest(root: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "manifest.json":
            continue
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": _file_sha256(path),
            }
        )
    value = {
        "file_count": len(files),
        "total_size_bytes": sum(int(item["size_bytes"]) for item in files),
        "files": files,
    }
    _json_dump(root / "manifest.json", value)
    return value


def _ledgers(truth: pd.DataFrame) -> dict[str, list[dict[str, Any]]]:
    base = ["trajectory_id", "scenario_id", "seed", "split", "snapshot_step"]
    return {
        "escape": truth[base + ["minimum_escape_cost", "escape_not_observed", "best_probe_family", "best_probe_strength", "best_probe_delay"]].to_dict(orient="records"),
        "value": truth[base + ["current_value", "reachable_value", "reachable_value_delta"]].to_dict(orient="records"),
        "range": truth[base + ["reachable_range", "reachable_range_delta"]].to_dict(orient="records"),
        "window": truth[base + ["last_action_window", "last_action_window_delta"]].to_dict(orient="records"),
        "refix": truth[base + ["refixation_probability"]].to_dict(orient="records"),
        "maintenance": truth[base + ["maintenance_cost", "current_value_slope"]].to_dict(orient="records"),
    }


def _judgement(
    truth_all: pd.DataFrame,
    selected_holdout: Mapping[str, Any],
    baseline_holdout: Mapping[str, Any],
) -> dict[str, Any]:
    shrinking_count = int(truth_all["shrinking_equilibrium_candidate"].sum())
    level_variation = int(truth_all["provisional_irreversibility_level"].nunique())
    structural_variation = (
        float(truth_all["minimum_escape_cost"].std()) > 1e-6
        and float(truth_all["reachable_value"].std()) > 1e-6
    )
    prediction_gain = (
        float(selected_holdout["escape_cost_rank_correlation"])
        > float(baseline_holdout["escape_cost_rank_correlation"]) + 0.05
        or float(selected_holdout["shrinking_average_precision"])
        > float(baseline_holdout["shrinking_average_precision"]) + 0.05
        or float(selected_holdout["irreversibility_adjacent_accuracy"])
        > float(baseline_holdout["irreversibility_adjacent_accuracy"]) + 0.05
    )
    if shrinking_count > 0 and level_variation >= 3 and structural_variation and prediction_gain:
        grade = "A_structural_risk_promising"
    elif structural_variation and level_variation >= 2:
        grade = "B_structural_risk_partially_promising"
    else:
        grade = "C_world_model_or_probe_set_insufficient"
    return {
        "grade": grade,
        "shrinking_equilibrium_count": shrinking_count,
        "irreversibility_level_count": level_variation,
        "structural_truth_has_variation": structural_variation,
        "selected_predictor_improves_over_current_risk": prediction_gain,
        "universal_irreversibility_claim": False,
    }


def run(
    corpus_dir: str | Path,
    output_dir: str | Path,
    config_path: str | Path = DEFAULT_CONFIG,
) -> dict[str, Any]:
    config = load_config(config_path)
    output = Path(output_dir)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    task3_config = _json_load(ROOT / config["task3_config_path"])
    calibration = _json_load(ROOT / config["calibration_config_path"])
    contract = _json_load(ROOT / config["task1_contract_path"])
    required_arrays = list(contract["step_record"]["required_state_arrays"])
    index = CorpusIndex(corpus_dir, config)
    _json_dump(output / config["outputs"]["split_manifest"], index.split_manifest())

    fit_entries = index.entries_for("fit")
    validation_entries = index.entries_for("validation")
    safe = calibrate_safe_region(fit_entries, config)
    _json_dump(output / config["outputs"]["safe_region_schema"], safe)
    _json_dump(
        output / config["outputs"]["branch_simulation_contract"],
        {
            "source_snapshot_is_immutable": True,
            "branch_world_is_new_instance": True,
            "current_input_persists_during_delay": True,
            "neutral_input_after_action": True,
            "parameter_box_write": False,
            "action_module_connection": False,
            "universal_irreversibility_claim": False,
            "truth_source": "counterfactual_replicates",
        },
    )
    _json_dump(
        output / config["outputs"]["action_probe_schema"],
        config["branch_probe"],
    )
    _json_dump(
        output / config["outputs"]["structural_truth_schema"],
        {
            "targets": config["prediction"]["targets"],
            "irreversibility_levels": {
                "0": "no-action recovery observed",
                "1": "weak low-scale action recovery observed",
                "2": "medium action recovery observed",
                "3": "strong or broad action recovery observed",
                "4": "no recovery in tested probe set",
            },
            "conditional_on_probe_set": True,
            "future_side_only": True,
        },
    )

    fit_branches = generate_branch_rows(fit_entries, safe, config)
    validation_branches = generate_branch_rows(validation_entries, safe, config)
    fit_frontier = _group_frontier(fit_branches, config)
    validation_frontier = _group_frontier(validation_branches, config)
    fit_truth = structural_truth_from_frontier(fit_frontier, config)
    validation_truth = structural_truth_from_frontier(validation_frontier, config)

    fit_series = _load_series(fit_entries, task3_config, calibration)
    fit_features, preprocessor, dynamics, task3_names, macro_names = feature_frame(
        fit_entries,
        fit_entries,
        fit_truth,
        config,
        task3_config,
        calibration,
        required_arrays,
        fit_series=fit_series,
    )
    validation_features, _, _, _, _ = feature_frame(
        fit_entries,
        validation_entries,
        validation_truth,
        config,
        task3_config,
        calibration,
        required_arrays,
        preprocessor=preprocessor,
        dynamics=dynamics,
        fit_series=fit_series,
    )

    candidate_rows: list[dict[str, Any]] = []
    validation_predictions: dict[str, pd.DataFrame] = {}
    models: dict[str, Any] = {}
    for family in config["prediction"]["candidate_families"]:
        features = _feature_names(str(family), task3_names, macro_names)
        model = fit_predictor(fit_features, features, config)
        predictions = predict(model, validation_features, config)
        metrics = evaluate_predictions(predictions)
        row = {"candidate_family": family, "feature_count": len(features), **metrics}
        candidate_rows.append(row)
        validation_predictions[str(family)] = predictions
        models[str(family)] = model
    candidate_rows.sort(key=_selection_key, reverse=True)
    selected = candidate_rows[0]
    selected_family = str(selected["candidate_family"])
    structural_hash = _canonical_hash(
        pd.concat([fit_truth, validation_truth], ignore_index=True).to_dict(orient="records")
    )
    lock_path = output / config["outputs"]["selection_lock"]
    validation_path = output / config["outputs"]["selection_lock_validation"]
    lock = _create_lock(lock_path, selected, safe, config, structural_hash)
    _write_lock_validation(validation_path, lock)

    holdout_entries = index.entries_for(
        "holdout", lock_path=lock_path, validation_path=validation_path
    )
    holdout_branches = generate_branch_rows(holdout_entries, safe, config)
    holdout_frontier = _group_frontier(holdout_branches, config)
    holdout_truth = structural_truth_from_frontier(holdout_frontier, config)
    holdout_features, _, _, _, _ = feature_frame(
        fit_entries,
        holdout_entries,
        holdout_truth,
        config,
        task3_config,
        calibration,
        required_arrays,
        preprocessor=preprocessor,
        dynamics=dynamics,
        fit_series=fit_series,
    )

    train_features = pd.concat([fit_features, validation_features], ignore_index=True)
    selected_features = _feature_names(selected_family, task3_names, macro_names)
    selected_model = fit_predictor(train_features, selected_features, config)
    selected_predictions = predict(selected_model, holdout_features, config)
    selected_metrics = evaluate_predictions(selected_predictions)
    baseline_features = _feature_names("current_risk", task3_names, macro_names)
    baseline_model = fit_predictor(train_features, baseline_features, config)
    baseline_predictions = predict(baseline_model, holdout_features, config)
    baseline_metrics = evaluate_predictions(baseline_predictions)

    all_branches = fit_branches + validation_branches + holdout_branches
    all_frontier = pd.concat([fit_frontier, validation_frontier, holdout_frontier], ignore_index=True)
    all_truth = pd.concat([fit_truth, validation_truth, holdout_truth], ignore_index=True)
    _write_csv(output / config["outputs"]["branch_manifest"], [
        {
            "branch_id": row["branch_id"],
            "trajectory_id": row["trajectory_id"],
            "snapshot_step": row["snapshot_step"],
            "probe_family": row["probe_family"],
            "strength": row["strength"],
            "delay_steps": row["delay_steps"],
            "replicate": row["replicate"],
            "source_split": row["source_split"],
        }
        for row in all_branches
    ])
    _write_csv(output / config["outputs"]["branch_results"], all_branches)
    _write_csv(output / config["outputs"]["recovery_frontier"], all_frontier.to_dict(orient="records"))
    ledgers = _ledgers(all_truth)
    _write_csv(output / config["outputs"]["escape_cost_ledger"], ledgers["escape"])
    _write_csv(output / config["outputs"]["reachable_value_ledger"], ledgers["value"])
    _write_csv(output / config["outputs"]["reachable_range_ledger"], ledgers["range"])
    _write_csv(output / config["outputs"]["last_action_window"], ledgers["window"])
    _write_csv(output / config["outputs"]["refixation_ledger"], ledgers["refix"])
    _write_csv(output / config["outputs"]["maintenance_cost_ledger"], ledgers["maintenance"])
    _write_csv(
        output / config["outputs"]["shrinking_equilibrium_candidates"],
        all_truth.to_dict(orient="records"),
    )
    transient = all_truth[
        all_truth["scenario_id"].isin(["temporary_disturbance", "stable_continuation"])
        | (all_truth["shrinking_equilibrium_candidate"] == 1)
    ]
    _write_csv(
        output / config["outputs"]["transient_vs_shrinking"],
        transient.to_dict(orient="records"),
    )
    _write_csv(output / config["outputs"]["candidate_comparison"], candidate_rows)
    _json_dump(
        output / config["outputs"]["validation_metrics"],
        {
            "selected_candidate": selected,
            "all_candidates": candidate_rows,
            "shrinking_positive_count": int(validation_truth["shrinking_equilibrium_candidate"].sum()),
        },
    )
    _json_dump(
        output / config["outputs"]["feature_schema"],
        {
            "task3_feature_names": task3_names,
            "task4_feature_names": macro_names,
            "selected_feature_names": selected_features,
            "future_information_audit": "passed",
            "metadata_feature_audit": "passed",
        },
    )
    _json_dump(
        output / config["outputs"]["holdout_metrics"],
        {
            "selected_candidate": selected_metrics,
            "current_risk_baseline": baseline_metrics,
        },
    )
    selected_output = selected_predictions.copy()
    selected_output.insert(0, "candidate_family", selected_family)
    baseline_output = baseline_predictions.copy()
    baseline_output.insert(0, "candidate_family", "current_risk")
    _write_csv(
        output / config["outputs"]["holdout_predictions"],
        pd.concat([selected_output, baseline_output], ignore_index=True).to_dict(orient="records"),
    )

    judgement = _judgement(all_truth, selected_metrics, baseline_metrics)
    _bar_svg(
        output / "escape_cost_over_time.svg",
        "Mean minimum escape cost by snapshot",
        [str(value) for value in sorted(all_truth["snapshot_step"].unique())],
        [
            float(all_truth.loc[all_truth["snapshot_step"] == value, "minimum_escape_cost"].mean())
            for value in sorted(all_truth["snapshot_step"].unique())
        ],
    )
    _bar_svg(
        output / "reachable_value_over_time.svg",
        "Mean reachable value by snapshot",
        [str(value) for value in sorted(all_truth["snapshot_step"].unique())],
        [
            float(all_truth.loc[all_truth["snapshot_step"] == value, "reachable_value"].mean())
            for value in sorted(all_truth["snapshot_step"].unique())
        ],
    )
    _bar_svg(
        output / "irreversibility_level_distribution.svg",
        "Provisional irreversibility level counts",
        [str(level) for level in range(5)],
        [float((all_truth["provisional_irreversibility_level"] == level).sum()) for level in range(5)],
    )
    _bar_svg(
        output / "predictor_comparison.svg",
        "Holdout escape-cost rank correlation",
        [selected_family, "current_risk"],
        [
            selected_metrics["escape_cost_rank_correlation"],
            baseline_metrics["escape_cost_rank_correlation"],
        ],
    )

    results = f"""# Task 3.2-4.1 実行結果

## 構造正解

- 分岐数: {len(all_branches)}
- 判定時点数: {len(all_truth)}
- 縮小均衡候補数: {int(all_truth['shrinking_equilibrium_candidate'].sum())}
- 暫定不可逆性段階の種類数: {int(all_truth['provisional_irreversibility_level'].nunique())}

## 選択予測器

`{selected_family}`

## Holdout

| 指標 | 選択予測器 | 現在リスクのみ |
|---|---:|---:|
| 縮小均衡AP | {selected_metrics['shrinking_average_precision']:.6f} | {baseline_metrics['shrinking_average_precision']:.6f} |
| 脱出費用順位相関 | {selected_metrics['escape_cost_rank_correlation']:.6f} | {baseline_metrics['escape_cost_rank_correlation']:.6f} |
| 最終作用可能時間MAE | {selected_metrics['last_action_window_mae']:.6f} | {baseline_metrics['last_action_window_mae']:.6f} |
| 不可逆性隣接段階一致 | {selected_metrics['irreversibility_adjacent_accuracy']:.6f} | {baseline_metrics['irreversibility_adjacent_accuracy']:.6f} |

## 判定

`{judgement['grade']}`

## 境界

不可逆性は、今回試した作用集合・費用・時間幅に対する暫定評価である。絶対的不可逆性、正式な協調人数、実世界のゲーム構造を示すものではない。
"""
    (output / config["outputs"]["results_markdown"]).write_text(results, encoding="utf-8")
    completion = f"""# Task 3.2-4.1 完了記録

- 状態分岐複製: 完了
- 元軌道書戻し禁止: 検査済み
- 作用強度・開始遅延・作用解除後追跡: 実施
- 最小脱出費用: 算出
- 回復成功率: 算出
- 到達可能価値・範囲: 算出
- 最終作用可能時間: 算出
- 再固定化率: 算出
- 縮小均衡監査: 実施
- 軽量予測器比較: 実施
- selection lock後holdout: 実施
- 選択予測器: `{selected_family}`
- 判定: `{judgement['grade']}`
"""
    (output / config["outputs"]["completion_markdown"]).write_text(completion, encoding="utf-8")
    handoff = f"""# Task 3.2-4.1 → Task 3.2-5 引き渡し

Task 5へ、方向リスクとは分離した構造リスク値を渡す。

- 最小脱出費用
- 回復成功率
- 到達可能価値
- 到達可能範囲
- 最終作用可能時間
- 再固定化率
- 必要同時作用規模の代理
- 縮小均衡候補
- 暫定不可逆性段階

selection lock: `{lock['lock_hash']}`

判定: `{judgement['grade']}`
"""
    (output / config["outputs"]["handoff_markdown"]).write_text(handoff, encoding="utf-8")

    summary = {
        "task_id": config["task_id"],
        "status": "complete",
        "branch_count": len(all_branches),
        "snapshot_truth_count": len(all_truth),
        "selected_candidate": selected,
        "holdout": {
            "selected_candidate": selected_metrics,
            "current_risk_baseline": baseline_metrics,
        },
        "judgement": judgement,
        "selection_lock_hash": lock["lock_hash"],
        "holdout_state_read_gate": "passed",
        "source_trajectory_writeback": False,
        "parameter_box_write": False,
        "action_module_connection": False,
    }
    _json_dump(output / "summary.json", summary)
    manifest = _write_manifest(output)
    return {**summary, "manifest_file_count": manifest["file_count"]}


def validate_output(
    input_dir: str | Path, config_path: str | Path = DEFAULT_CONFIG
) -> dict[str, Any]:
    config = load_config(config_path)
    root = Path(input_dir)
    required = set(config["outputs"].values()) | {
        "summary.json",
        "escape_cost_over_time.svg",
        "reachable_value_over_time.svg",
        "irreversibility_level_distribution.svg",
        "predictor_comparison.svg",
    }
    missing = sorted(name for name in required if not (root / name).is_file())
    if missing:
        raise StructuralRiskError(f"Task 4.1 output missing {missing}")
    lock = validate_selection_lock(
        root / config["outputs"]["selection_lock"],
        root / config["outputs"]["selection_lock_validation"],
    )
    summary = _json_load(root / "summary.json")
    if summary.get("status") != "complete":
        raise StructuralRiskError("Task 4.1 summary is not complete")
    if summary.get("selection_lock_hash") != lock["lock_hash"]:
        raise StructuralRiskError("Task 4.1 summary/selection-lock mismatch")
    if summary.get("source_trajectory_writeback") is not False:
        raise StructuralRiskError("Task 4.1 source trajectory writeback boundary failed")
    if summary.get("parameter_box_write") is not False:
        raise StructuralRiskError("Task 4.1 Parameter Box boundary failed")
    return {
        "status": "valid",
        "selected_candidate": summary["selected_candidate"]["candidate_family"],
        "selection_lock_hash": lock["lock_hash"],
        "branch_count": summary["branch_count"],
        "holdout_state_read_gate": "passed",
        "source_writeback_boundary": "passed",
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    execute = sub.add_parser("run")
    execute.add_argument("--corpus", required=True)
    execute.add_argument("--output", required=True)
    execute.add_argument("--config", default=str(DEFAULT_CONFIG))
    check = sub.add_parser("validate")
    check.add_argument("--input", required=True)
    check.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args(argv)
    result = (
        run(args.corpus, args.output, args.config)
        if args.command == "run"
        else validate_output(args.input, args.config)
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CorpusIndex",
    "Entry",
    "StructuralRiskError",
    "action_input",
    "calibrate_safe_region",
    "evaluate_predictions",
    "generate_branch_rows",
    "label_shrinking_equilibrium",
    "load_config",
    "run",
    "run_branch",
    "safe_state",
    "structural_truth_from_frontier",
    "validate_output",
    "validate_selection_lock",
]
