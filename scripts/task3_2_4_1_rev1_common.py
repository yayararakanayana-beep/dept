"""Common contracts and branch execution for Task 3.2-4.1 Rev1."""
from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for candidate in (ROOT, ROOT / "scripts"):
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

import task3_2_4_1_structural_risk as t41  # noqa: E402

DEFAULT_CONFIG = ROOT / "configs" / "task3_2_4_1_rev1.json"


class Rev1Error(ValueError):
    """Raised when a Rev1 contract or artifact is invalid."""


def json_load(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def native(value: Any) -> Any:
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return None if not math.isfinite(float(value)) else float(value)
    if isinstance(value, dict):
        return {str(key): native(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [native(item) for item in value]
    return value


def json_dump(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(native(value), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_csv(path: str | Path, rows: Sequence[Mapping[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        target.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if str(key) not in fields:
                fields.append(str(key))
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: native(value) for key, value in dict(row).items()})


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(native(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_config(path: str | Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = json_load(path)
    required = {
        "task_id", "challenge", "fixed_macro_candidate", "snapshot_selection",
        "safe_region", "branch_probe", "adaptive_boundary", "structural_truth",
        "prediction", "split_contract", "budget", "forbidden_feature_tokens", "outputs",
    }
    missing = sorted(required - set(config))
    if missing:
        raise Rev1Error(f"Rev1 config missing {missing}")
    challenge = config["challenge"]
    seeds = challenge["fit_seeds"] + challenge["validation_seeds"] + challenge["holdout_seeds"]
    if seeds != [30, 31, 32, 33, 34] or len(set(seeds)) != 5:
        raise Rev1Error("Rev1 formal seeds must be exactly 30-34 with disjoint splits")
    branch = config["branch_probe"]
    expected_conditions = [
        "C0_current_input_fixed_then_neutral",
        "C1_immediate_neutral",
        "C2_original_future_replay",
        "C3_same_seed_stable_future_replay",
    ]
    if branch["continuation_conditions"] != expected_conditions:
        raise Rev1Error("Rev1 continuation contract changed")
    if set(branch["probe_families"]) != set(branch["action_axes"]):
        raise Rev1Error("every Rev1 probe family requires action axes")
    budget = config["budget"]
    planned = (
        int(budget["expected_coarse_branches"])
        + int(budget["maximum_boundary_branches"])
        + int(budget["maximum_probability_branches"])
    )
    if planned > int(budget["absolute_maximum_branches"]):
        raise Rev1Error("Rev1 configured branch budget exceeds absolute maximum")
    if config["split_contract"].get("holdout_requires_validated_selection_lock") is not True:
        raise Rev1Error("Rev1 holdout gate must remain enabled")
    return config


@dataclass
class BranchBudget:
    maximum: int
    used: int = 0
    coarse: int = 0
    boundary: int = 0
    probability: int = 0

    def reserve(self, phase: str, count: int = 1) -> None:
        if count < 0 or self.used + count > self.maximum:
            raise Rev1Error(f"Rev1 branch budget exceeded: {self.used + count} > {self.maximum}")
        self.used += count
        if phase == "coarse":
            self.coarse += count
        elif phase == "boundary":
            self.boundary += count
        elif phase == "probability":
            self.probability += count
        else:
            raise Rev1Error(f"unknown budget phase {phase}")


Entry = t41.Entry
CorpusIndex = t41.CorpusIndex


def steps(entry: Entry) -> dict[int, dict[str, Any]]:
    return {int(row["step"]): row for row in t41._read_jsonl(entry.path / "steps.jsonl")}


def neutral_input() -> dict[str, float]:
    return {name: 0.0 for name in t41.EXTERNAL_FIELDS}


def input_at(rows: Mapping[int, Mapping[str, Any]], step: int) -> dict[str, float]:
    record = rows.get(int(step))
    if record is None:
        return neutral_input()
    observed = record.get("observed_external_input", {})
    return {name: float(observed.get(name, 0.0)) for name in t41.EXTERNAL_FIELDS}


def continuation_schedule(
    condition: str,
    entry: Entry,
    stable_entry: Entry,
    step_record: Mapping[str, Any],
    horizon: int,
    config: Mapping[str, Any],
) -> list[dict[str, float]]:
    current = {
        name: float(step_record["observed_external_input"].get(name, 0.0))
        for name in t41.EXTERNAL_FIELDS
    }
    neutral = neutral_input()
    if condition == "C0_current_input_fixed_then_neutral":
        duration = int(config["branch_probe"]["action_duration_steps"])
        return [dict(current) for _ in range(min(duration, horizon))] + [
            dict(neutral) for _ in range(max(0, horizon - duration))
        ]
    if condition == "C1_immediate_neutral":
        return [dict(neutral) for _ in range(horizon)]
    start = int(step_record["step"])
    source_rows = steps(entry)
    stable_rows = steps(stable_entry)
    if condition == "C2_original_future_replay":
        return [input_at(source_rows, start + offset) for offset in range(horizon)]
    if condition == "C3_same_seed_stable_future_replay":
        return [input_at(stable_rows, start + offset) for offset in range(horizon)]
    raise Rev1Error(f"unknown continuation condition {condition}")


def simulate(
    entry: Entry,
    stable_entry: Entry,
    step_record: Mapping[str, Any],
    safe: Mapping[str, Any],
    condition: str,
    family: str,
    strength: float,
    delay: int,
    replicate: int,
    phase: str,
    config: Mapping[str, Any],
    *,
    boundary_id: str = "",
) -> dict[str, Any]:
    world = t41._restore_world(entry, step_record, replicate, config)
    branch = config["branch_probe"]
    duration = int(branch["action_duration_steps"])
    followup = int(safe["post_action_followup_steps"])
    base_horizon = int(branch["continuation_horizon_steps"])
    total_steps = base_horizon if family == "no_action" else max(base_horizon, int(delay) + duration + followup)
    baseline = continuation_schedule(condition, entry, stable_entry, step_record, total_steps, config)
    timeline: list[dict[str, float]] = [t41._metrics_from_world(world)]
    for offset, external in enumerate(baseline):
        applied = dict(external)
        if family != "no_action" and int(delay) <= offset < int(delay) + duration:
            applied = t41.action_input(applied, family, strength)
        world.set_external_factors(applied)
        world.step()
        timeline.append(t41._metrics_from_world(world))
    flags = [t41.safe_state(row, safe) for row in timeline]
    first_safe = t41._first_sustained_safe(flags, int(safe["sustained_steps"]))
    final_safe = bool(all(flags[-int(safe["sustained_steps"]):]))
    ever_safe = first_safe is not None
    relapse = bool(ever_safe and not final_safe)
    axes = len(branch["action_axes"][family])
    active_strength = 0.0 if family == "no_action" else float(strength)
    weights = branch["cost_weights"]
    action_cost = active_strength * axes * duration * float(weights["intensity_axis_step"])
    recovery_time = len(timeline) if first_safe is None else int(first_safe)
    peak_risk = max(float(row["risk_score"]) for row in timeline)
    total_cost = (
        action_cost
        + recovery_time * float(weights["time_to_recovery"])
        + peak_risk * float(weights["peak_risk"])
        + int(relapse) * float(weights["relapse_after_recovery"])
    )
    final = timeline[-1]
    return {
        "branch_id": (
            f"{entry.trajectory_id}__s{int(step_record['step']):03d}__{condition[:2]}"
            f"__{family}__q{float(strength):.4f}__d{int(delay):02d}__r{int(replicate):02d}"
        ),
        "trajectory_id": entry.trajectory_id,
        "scenario_id": entry.scenario_id,
        "source_seed": entry.seed,
        "source_split": entry.split,
        "snapshot_step": int(step_record["step"]),
        "continuation_condition": condition,
        "probe_family": family,
        "strength": float(strength),
        "delay_steps": int(delay),
        "replicate": int(replicate),
        "phase": phase,
        "boundary_id": boundary_id,
        "simultaneous_action_scale": axes,
        "recovered": int(final_safe),
        "ever_safe": int(ever_safe),
        "relapse_after_recovery": int(relapse),
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


def entry_maps(entries: Sequence[Entry]) -> tuple[dict[str, Entry], dict[int, Entry]]:
    by_id = {entry.trajectory_id: entry for entry in entries}
    stable = {entry.seed: entry for entry in entries if entry.scenario_id == "stable_continuation"}
    if set(stable) != {entry.seed for entry in entries}:
        raise Rev1Error("same-seed stable continuation entry is missing")
    return by_id, stable


def generate_coarse_branches(
    entries: Sequence[Entry], safe: Mapping[str, Any], config: Mapping[str, Any], budget: BranchBudget
) -> list[dict[str, Any]]:
    _, stable_by_seed = entry_maps(entries)
    branch = config["branch_probe"]
    rows: list[dict[str, Any]] = []
    conditions = list(branch["continuation_conditions"])
    primary = list(branch["primary_conditions"])
    families = [name for name in branch["probe_families"] if name != "no_action"]
    for entry in entries:
        stable_entry = stable_by_seed[entry.seed]
        for record in t41.snapshot_records(entry, config):
            for condition in conditions:
                budget.reserve("coarse")
                rows.append(simulate(entry, stable_entry, record, safe, condition, "no_action", 0.0, 0, 0, "coarse", config))
            for condition in primary:
                for family in families:
                    for strength in branch["coarse_strengths"]:
                        for delay in branch["coarse_delays"]:
                            budget.reserve("coarse")
                            rows.append(simulate(
                                entry, stable_entry, record, safe, condition, family,
                                float(strength), int(delay), 0, "coarse", config,
                            ))
                for delay in branch["coarse_delays"]:
                    budget.reserve("coarse")
                    rows.append(simulate(
                        entry, stable_entry, record, safe, condition, "combined_relief",
                        float(branch["combined_strong_strength"]), int(delay), 0, "coarse", config,
                    ))
    expected = len(entries) * len(config["snapshot_selection"]["steps"]) * 40
    if len(rows) != expected:
        raise Rev1Error(f"coarse branch count mismatch: {len(rows)} != {expected}")
    return rows
