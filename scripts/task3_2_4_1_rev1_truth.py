"""Structural truth construction for Task 3.2-4.1 Rev1."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from task3_2_4_1_rev1_boundaries import aggregate_branches


def geometric_spread(group: pd.DataFrame) -> float:
    columns = [
        "mean_final_risk", "mean_final_current_value", "mean_final_route_support",
        "mean_final_recovery_speed", "mean_final_concentration",
    ]
    matrix = group[columns].to_numpy(dtype=np.float64)
    if len(matrix) < 2:
        return 0.0
    scale = np.asarray([0.2, 0.2, 0.2, 0.1, 0.01], dtype=np.float64)
    normalized = matrix / np.maximum(scale, 1e-12)
    distances = [
        float(np.linalg.norm(normalized[left] - normalized[right]))
        for left in range(len(normalized))
        for right in range(left + 1, len(normalized))
    ]
    return float(np.mean(distances) if distances else 0.0)


def condition_truth(group: pd.DataFrame, config: Mapping[str, Any]) -> dict[str, Any]:
    threshold = float(config["structural_truth"]["recovery_probability_threshold"])
    successful = group[group["recovery_probability"] >= threshold].copy()
    escape_observed = int(not successful.empty)
    if successful.empty:
        cost = float("nan")
        last_window = -1
        minimum_scale = float("nan")
        best_family = ""
        best_strength = float("nan")
        best_delay = -1
        stage = 4
        safe_range = 0.0
    else:
        successful = successful.sort_values(
            ["mean_escape_cost", "strength", "simultaneous_action_scale", "delay_steps", "probe_family"]
        )
        best = successful.iloc[0]
        cost = float(best["mean_escape_cost"])
        last_window = int(successful["delay_steps"].max())
        minimum_scale = float(successful["simultaneous_action_scale"].min())
        best_family = str(best["probe_family"])
        best_strength = float(best["strength"])
        best_delay = int(best["delay_steps"])
        no_action = successful[successful["probe_family"] == "no_action"]
        if not no_action.empty:
            stage = 0
        elif best_strength <= 0.35 and minimum_scale <= 2:
            stage = 1
        elif best_strength <= 0.70:
            stage = 2
        else:
            stage = 3
        safe_range = geometric_spread(successful)
    no_action = group[group["probe_family"] == "no_action"]
    initial_value = float(group["initial_current_value"].iloc[0])
    no_action_value = float(no_action["mean_final_current_value"].mean()) if not no_action.empty else initial_value
    maintenance = max(0.0, initial_value - no_action_value)
    if not no_action.empty:
        maintenance += 0.5 * float(no_action["mean_final_risk"].mean())
    return {
        "escape_observed": escape_observed,
        "conditional_escape_cost": cost,
        "best_recovery_probability": float(group["recovery_probability"].max()),
        "reachable_value": float(group["mean_final_current_value"].max()),
        "geometric_outcome_spread": geometric_spread(group),
        "successful_family_diversity": float(successful["probe_family"].nunique() / 4.0) if escape_observed else 0.0,
        "safe_reachable_range": safe_range,
        "last_action_window": last_window,
        "minimum_simultaneous_action_scale": minimum_scale,
        "relapse_after_recovery_rate": float(group["relapse_after_recovery_rate"].max()),
        "irreversibility_stage": stage,
        "best_probe_family": best_family,
        "best_probe_strength": best_strength,
        "best_probe_delay": best_delay,
        "maintenance_cost": float(maintenance),
    }


def structural_truth_from_branches(
    rows: Sequence[Mapping[str, Any]], nonmonotonic: Sequence[Mapping[str, Any]], config: Mapping[str, Any]
) -> pd.DataFrame:
    aggregate = aggregate_branches(rows)
    state_keys = ["trajectory_id", "scenario_id", "source_seed", "source_split", "snapshot_step"]
    boundary_states = {
        (str(row["trajectory_id"]), int(row["snapshot_step"])) for row in rows if row.get("boundary_id")
    }
    nonmono_states = {
        (str(row["trajectory_id"]), int(row["snapshot_step"])) for row in nonmonotonic
    }
    output: list[dict[str, Any]] = []
    for key, group in aggregate.groupby(state_keys, sort=False):
        row = {
            "trajectory_id": key[0], "scenario_id": key[1], "seed": int(key[2]),
            "split": key[3], "snapshot_step": int(key[4]),
            "current_risk": float(group["initial_risk"].iloc[0]),
            "current_value": float(group["initial_current_value"].iloc[0]),
        }
        no_action_classes: list[int] = []
        for condition in config["branch_probe"]["continuation_conditions"]:
            condition_group = group[group["continuation_condition"] == condition]
            no_action = condition_group[condition_group["probe_family"] == "no_action"]
            no_action_classes.append(int(float(no_action["recovery_probability"].max()) >= 0.5))
        row["continuation_sensitive"] = int(len(set(no_action_classes)) > 1)
        for prefix, condition in (
            ("c2", "C2_original_future_replay"),
            ("c3", "C3_same_seed_stable_future_replay"),
        ):
            values = condition_truth(group[group["continuation_condition"] == condition], config)
            row.update({f"{prefix}_{name}": value for name, value in values.items()})
        row["environment_dependent_deterioration"] = int(
            row["c2_escape_observed"] == 0 and row["c3_escape_observed"] == 1
        )
        row["intrinsic_recovery_loss"] = int(row["c3_escape_observed"] == 0)
        state_id = (str(row["trajectory_id"]), int(row["snapshot_step"]))
        row["action_boundary_exists"] = int(state_id in boundary_states)
        row["nonmonotonic_action_response"] = int(state_id in nonmono_states)
        output.append(row)
    frame = pd.DataFrame(output)
    settings = config["structural_truth"]
    labelled: list[dict[str, Any]] = []
    for _, group in frame.groupby("trajectory_id", sort=False):
        previous: Mapping[str, Any] | None = None
        for source in group.sort_values("snapshot_step").to_dict(orient="records"):
            row = dict(source)
            if previous is None:
                row.update({
                    "structural_contraction_evidence_count": 0,
                    "structural_contraction": 0,
                    "dangerous_shrinking": 0,
                    "irreversibility_progression": 0,
                })
            else:
                cost_increase = (
                    row["c3_escape_observed"] == 1
                    and previous["c3_escape_observed"] == 1
                    and float(row["c3_conditional_escape_cost"]) - float(previous["c3_conditional_escape_cost"])
                    >= float(settings["conditional_escape_cost_increase"])
                )
                escape_transition = previous["c3_escape_observed"] == 1 and row["c3_escape_observed"] == 0
                safe_range_decline = (
                    float(row["c3_safe_reachable_range"]) - float(previous["c3_safe_reachable_range"])
                    <= -float(settings["safe_range_decline"])
                )
                spread_decline = (
                    float(row["c3_geometric_outcome_spread"]) - float(previous["c3_geometric_outcome_spread"])
                    <= -float(settings["geometric_spread_decline"])
                )
                diversity_decline = (
                    float(row["c3_successful_family_diversity"]) - float(previous["c3_successful_family_diversity"])
                    <= -float(settings["successful_family_diversity_decline"])
                )
                window_decline = (
                    float(row["c3_last_action_window"]) - float(previous["c3_last_action_window"])
                    <= -float(settings["last_action_window_decline"])
                )
                maintenance_increase = (
                    float(row["c3_maintenance_cost"]) - float(previous["c3_maintenance_cost"])
                    >= float(settings["maintenance_cost_increase"])
                )
                evidence = [
                    cost_increase, escape_transition, safe_range_decline, spread_decline,
                    diversity_decline, window_decline, maintenance_increase,
                ]
                count = sum(bool(value) for value in evidence)
                contraction = int(count >= int(settings["structural_contraction_minimum_evidence"]))
                recovery_decline = (
                    float(row["c3_best_recovery_probability"]) - float(previous["c3_best_recovery_probability"])
                    <= -float(settings["recovery_probability_decline"])
                )
                relapse_increase = (
                    float(row["c3_relapse_after_recovery_rate"]) - float(previous["c3_relapse_after_recovery_rate"])
                    >= float(settings["relapse_rate_increase"])
                )
                stage_increase = int(row["c3_irreversibility_stage"]) > int(previous["c3_irreversibility_stage"])
                dangerous = int(
                    contraction
                    and (escape_transition or window_decline or recovery_decline or relapse_increase or stage_increase)
                )
                progression = int(
                    escape_transition
                    or stage_increase
                    or (int(previous["c3_last_action_window"]) >= 0 and int(row["c3_last_action_window"]) < 0)
                )
                row.update({
                    "structural_contraction_evidence_count": count,
                    "structural_contraction": contraction,
                    "dangerous_shrinking": dangerous,
                    "irreversibility_progression": progression,
                })
            labelled.append(row)
            previous = row
    return pd.DataFrame(labelled)
