"""Aggregation and adaptive boundary search for Task 3.2-4.1 Rev1."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import pandas as pd

from task3_2_4_1_rev1_common import (
    BranchBudget, Entry, entry_maps, simulate, t41,
)


def aggregate_branches(rows: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    keys = [
        "trajectory_id", "scenario_id", "source_seed", "source_split", "snapshot_step",
        "continuation_condition", "probe_family", "strength", "delay_steps", "simultaneous_action_scale",
    ]
    output: list[dict[str, Any]] = []
    for key, group in frame.groupby(keys, sort=False, dropna=False):
        row = dict(zip(keys, key, strict=True))
        ever_count = int(group["ever_safe"].sum())
        row.update({
            "replicate_count": len(group),
            "recovery_probability": float(group["recovered"].mean()),
            "ever_safe_probability": float(group["ever_safe"].mean()),
            "relapse_after_recovery_rate": (
                float(group["relapse_after_recovery"].sum() / ever_count) if ever_count else 0.0
            ),
            "mean_escape_cost": float(group["total_escape_cost"].mean()),
            "mean_recovery_time": float(group["recovery_time_steps"].mean()),
            "mean_final_risk": float(group["final_risk"].mean()),
            "mean_final_current_value": float(group["final_current_value"].mean()),
            "mean_final_route_support": float(group["final_route_support"].mean()),
            "mean_final_recovery_speed": float(group["final_recovery_speed"].mean()),
            "mean_final_concentration": float(group["final_concentration"].mean()),
            "initial_risk": float(group["initial_risk"].mean()),
            "initial_current_value": float(group["initial_current_value"].mean()),
            "replicate_disagreement": int(group["recovered"].min() != group["recovered"].max()),
        })
        output.append(row)
    return pd.DataFrame(output)


def detect_boundaries(aggregate: pd.DataFrame) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates: list[dict[str, Any]] = []
    nonmonotonic: list[dict[str, Any]] = []
    action = aggregate[aggregate["probe_family"] != "no_action"].copy()
    state = ["trajectory_id", "scenario_id", "source_seed", "source_split", "snapshot_step", "continuation_condition"]
    for key, group in action.groupby(state + ["probe_family", "delay_steps"], sort=False):
        records = group.sort_values("strength").to_dict(orient="records")
        for left, right in zip(records, records[1:]):
            low_class = int(float(left["recovery_probability"]) >= 0.5)
            high_class = int(float(right["recovery_probability"]) >= 0.5)
            base = dict(zip(state + ["probe_family", "delay_steps"], key, strict=True))
            if low_class != high_class:
                candidates.append({
                    **base, "boundary_type": "strength", "low": float(left["strength"]),
                    "high": float(right["strength"]), "low_class": low_class, "high_class": high_class,
                })
            if high_class < low_class:
                nonmonotonic.append({
                    **base, "nonmonotonic_type": "stronger_action_worse",
                    "low": float(left["strength"]), "high": float(right["strength"]),
                })
    for key, group in action.groupby(state + ["probe_family", "strength"], sort=False):
        records = group.sort_values("delay_steps").to_dict(orient="records")
        for left, right in zip(records, records[1:]):
            low_class = int(float(left["recovery_probability"]) >= 0.5)
            high_class = int(float(right["recovery_probability"]) >= 0.5)
            base = dict(zip(state + ["probe_family", "strength"], key, strict=True))
            if low_class != high_class:
                candidates.append({
                    **base, "boundary_type": "delay", "low": float(left["delay_steps"]),
                    "high": float(right["delay_steps"]), "low_class": low_class, "high_class": high_class,
                })
            if high_class > low_class:
                nonmonotonic.append({
                    **base, "nonmonotonic_type": "later_action_better",
                    "low": float(left["delay_steps"]), "high": float(right["delay_steps"]),
                })
    candidates.sort(key=lambda row: (
        row["source_split"], row["trajectory_id"], int(row["snapshot_step"]),
        row["continuation_condition"], row["probe_family"], row["boundary_type"], float(row["low"]),
    ))
    for index, row in enumerate(candidates):
        row["boundary_id"] = f"{str(row['source_split'])[0].upper()}B{index:05d}"
    return candidates, nonmonotonic


def refine_boundaries(
    candidates: Sequence[Mapping[str, Any]], entries: Sequence[Entry], safe: Mapping[str, Any],
    config: Mapping[str, Any], budget: BranchBudget,
) -> list[dict[str, Any]]:
    by_id, stable_by_seed = entry_maps(entries)
    settings = config["adaptive_boundary"]
    maximum = int(settings["maximum_boundary_branches"])
    rows: list[dict[str, Any]] = []
    records_cache: dict[str, dict[int, dict[str, Any]]] = {}
    for source in candidates:
        if budget.boundary >= maximum:
            break
        spec = dict(source)
        entry = by_id[str(spec["trajectory_id"])]
        records_cache.setdefault(entry.trajectory_id, {
            int(record["step"]): record for record in t41.snapshot_records(entry, config)
        })
        record = records_cache[entry.trajectory_id][int(spec["snapshot_step"])]
        low, high = float(spec["low"]), float(spec["high"])
        low_class, high_class = int(spec["low_class"]), int(spec["high_class"])
        for refinement in range(int(settings["maximum_refinements_per_boundary"])):
            if budget.boundary >= maximum:
                break
            if spec["boundary_type"] == "delay":
                if high - low <= int(settings["delay_minimum_resolution"]):
                    break
                midpoint = float(int(round((low + high) / 2.0)))
                if midpoint <= low or midpoint >= high:
                    break
                family, strength, delay = str(spec["probe_family"]), float(spec["strength"]), int(midpoint)
            else:
                if high - low <= float(settings["strength_minimum_resolution"]):
                    break
                midpoint = round((low + high) / 2.0, 6)
                if midpoint <= low + 1e-12 or midpoint >= high - 1e-12:
                    break
                family, strength, delay = str(spec["probe_family"]), float(midpoint), int(spec["delay_steps"])
            budget.reserve("boundary")
            result = simulate(
                entry, stable_by_seed[entry.seed], record, safe,
                str(spec["continuation_condition"]), family, strength, delay, 0,
                "boundary", config, boundary_id=str(spec["boundary_id"]),
            )
            result.update({
                "boundary_type": spec["boundary_type"], "refinement": refinement + 1,
                "boundary_midpoint": midpoint,
            })
            rows.append(result)
            midpoint_class = int(result["recovered"])
            if midpoint_class == low_class:
                low, low_class = midpoint, midpoint_class
            elif midpoint_class == high_class:
                high, high_class = midpoint, midpoint_class
            else:
                break
    return rows


def probability_boundary_replicates(
    boundary_rows: Sequence[Mapping[str, Any]], entries: Sequence[Entry], safe: Mapping[str, Any],
    config: Mapping[str, Any], budget: BranchBudget,
) -> list[dict[str, Any]]:
    if not boundary_rows:
        return []
    by_id, stable_by_seed = entry_maps(entries)
    settings = config["adaptive_boundary"]
    max_cases = int(settings["maximum_probability_cases"])
    max_branches = int(settings["maximum_probability_branches"])
    max_extra = int(settings["additional_replicates_per_case"])
    unique: dict[tuple[Any, ...], Mapping[str, Any]] = {}
    for row in boundary_rows:
        key = (
            row["trajectory_id"], int(row["snapshot_step"]), row["continuation_condition"],
            row["probe_family"], float(row["strength"]), int(row["delay_steps"]), row["boundary_id"],
        )
        unique.setdefault(key, row)
    cases = [unique[key] for key in sorted(unique)[:max_cases]]
    records_cache: dict[str, dict[int, dict[str, Any]]] = {}
    output: list[dict[str, Any]] = []
    for case_index, source in enumerate(cases):
        if budget.probability >= max_branches:
            break
        entry = by_id[str(source["trajectory_id"])]
        records_cache.setdefault(entry.trajectory_id, {
            int(record["step"]): record for record in t41.snapshot_records(entry, config)
        })
        record = records_cache[entry.trajectory_id][int(source["snapshot_step"])]
        budget.reserve("probability")
        screen = simulate(
            entry, stable_by_seed[entry.seed], record, safe,
            str(source["continuation_condition"]), str(source["probe_family"]),
            float(source["strength"]), int(source["delay_steps"]), 1,
            "probability_screen", config, boundary_id=str(source["boundary_id"]),
        )
        screen["probability_case_id"] = f"P{case_index:03d}"
        output.append(screen)
        if int(screen["recovered"]) == int(source["recovered"]):
            continue
        for replicate in range(2, max_extra + 1):
            if budget.probability >= max_branches:
                break
            budget.reserve("probability")
            result = simulate(
                entry, stable_by_seed[entry.seed], record, safe,
                str(source["continuation_condition"]), str(source["probe_family"]),
                float(source["strength"]), int(source["delay_steps"]), replicate,
                "probability_expand", config, boundary_id=str(source["boundary_id"]),
            )
            result["probability_case_id"] = f"P{case_index:03d}"
            output.append(result)
    return output
