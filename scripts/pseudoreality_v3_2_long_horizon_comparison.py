"""Long-horizon comparison between PseudoReality v3 and v3.2.

v3.2 is the gain-optimization branch: it does not inherit from the v3.1 stress
lineage. This comparison checks whether expected-value comparison, exploration
cost, and information retention create a short-to-medium route without directly
forcing medium dominance.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pandas as pd

from pseudo_reality.distribution_terrain_v3_scenarios import (
    run_default_scenario_suite as run_v3_default_scenario_suite,
    run_stable_scenario_suite as run_v3_stable_scenario_suite,
)
from pseudo_reality.distribution_terrain_v3_2_scenarios import (
    run_default_scenario_suite as run_v32_default_scenario_suite,
    run_scenario_suite as run_v32_scenario_suite,
    run_stable_scenario_suite as run_v32_stable_scenario_suite,
)
from scripts.pseudoreality_v3_medium_pattern_validation import (
    add_dominance_columns,
    add_total_gain_columns,
)
from scripts.pseudoreality_v3_typical_pattern_suite import typical_pattern_scenario_specs
from scripts.pseudoreality_v3_typical_pattern_suite import (
    run_typical_pattern_scenario_suite as run_v3_typical_pattern_scenario_suite,
)


LONG_HORIZON_COMPARISON_STEPS = (50, 100, 200)
LONG_HORIZON_COMPARISON_SEED = 0
COMPARISON_METRICS = (
    "final_total_gain_distribution_weighted_mean",
    "delta_total_gain_distribution_weighted_mean",
    "final_short_dominance_distribution_weighted_margin",
    "final_medium_dominance_distribution_weighted_margin",
    "final_damage_distribution_weighted_mean",
    "final_rigidity_distribution_weighted_mean",
    "final_friction_distribution_weighted_mean",
    "final_total_flow",
)
V32_EXTRA_METRICS = (
    "final_existing_path_expected_value_distribution_weighted_mean",
    "final_exploration_cost_distribution_weighted_mean",
    "final_exploration_option_value_distribution_weighted_mean",
    "final_exploration_net_expected_value_distribution_weighted_mean",
    "final_expected_value_advantage_distribution_weighted_mean",
    "final_information_memory_distribution_weighted_mean",
    "final_short_gain_information_conversion_distribution_weighted_mean",
)
COMPACT_MODEL_COLUMNS = (
    "model",
    "suite",
    "validation_steps",
    "scenario",
    "final_dominance_regime",
    "final_total_gain_distribution_weighted_mean",
    "delta_total_gain_distribution_weighted_mean",
    "final_damage_distribution_weighted_mean",
    "final_friction_distribution_weighted_mean",
    "final_total_flow",
    "final_expected_value_advantage_distribution_weighted_mean",
    "final_information_memory_distribution_weighted_mean",
    "v3_2_long_horizon_readout",
)
COMPACT_DELTA_COLUMNS = (
    "suite",
    "scenario",
    "validation_steps",
    "v3_final_dominance_regime",
    "v32_final_dominance_regime",
    "total_gain_delta_v32_minus_v3",
    "damage_delta_v32_minus_v3",
    "friction_delta_v32_minus_v3",
    "flow_delta_v32_minus_v3",
    "v32_final_expected_value_advantage_distribution_weighted_mean",
    "v32_final_information_memory_distribution_weighted_mean",
    "v3_2_comparison_readout",
)


def _v32_typical_pattern_scenario_suite(*, seed: int = 0, steps: int = 30) -> tuple[pd.DataFrame, dict[str, dict[str, pd.DataFrame]]]:
    return run_v32_scenario_suite(typical_pattern_scenario_specs(seed=seed, steps=steps))


def _suite_runners() -> tuple[
    tuple[
        str,
        Callable[..., tuple[pd.DataFrame, dict[str, dict[str, pd.DataFrame]]]],
        Callable[..., tuple[pd.DataFrame, dict[str, dict[str, pd.DataFrame]]]],
    ],
    ...,
]:
    return (
        ("default", run_v3_default_scenario_suite, run_v32_default_scenario_suite),
        ("stable", run_v3_stable_scenario_suite, run_v32_stable_scenario_suite),
        ("typical", run_v3_typical_pattern_scenario_suite, _v32_typical_pattern_scenario_suite),
    )


def _prepare_summary(summary: pd.DataFrame, *, model: str, suite: str, steps: int) -> pd.DataFrame:
    table = add_total_gain_columns(add_dominance_columns(summary.copy()))
    table["model"] = model
    table["suite"] = suite
    table["validation_steps"] = int(steps)
    table["v3_2_long_horizon_readout"] = table.apply(_model_readout, axis=1)
    leading = ["model", "suite", "validation_steps"]
    ordered = leading + [column for column in table.columns if column not in leading]
    return table[ordered]


def _model_readout(row: pd.Series) -> str:
    regime = str(row["final_dominance_regime"])
    total_delta = float(row["delta_total_gain_distribution_weighted_mean"])
    damage = float(row["final_damage_distribution_weighted_mean"])
    flow = float(row["final_total_flow"])
    advantage = float(row.get("final_expected_value_advantage_distribution_weighted_mean", 0.0))
    memory = float(row.get("final_information_memory_distribution_weighted_mean", 0.0))

    if regime == "medium_dominant" and damage < 0.45 and flow > 0.04:
        return "medium_path_persistent"
    if memory > 0.02 and advantage > 0.01 and total_delta > -0.02:
        return "expected_value_route_active"
    if memory > 0.02 and damage < 0.55:
        return "information_memory_present"
    if damage >= 0.90 and flow <= 0.03:
        return "high_damage_low_flow"
    if total_delta >= 0.05 and damage < 0.50:
        return f"{regime}_gain_positive"
    if total_delta <= -0.10:
        return f"{regime}_gain_declining"
    return f"{regime}_mixed"


def run_v3_2_long_horizon_comparison(
    *,
    seed: int = LONG_HORIZON_COMPARISON_SEED,
    steps_set: tuple[int, ...] = LONG_HORIZON_COMPARISON_STEPS,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run v3/v3.2 long-horizon comparison tables."""

    model_tables: list[pd.DataFrame] = []
    for steps in steps_set:
        for suite_name, v3_runner, v32_runner in _suite_runners():
            v3_summary, _v3_traces = v3_runner(seed=seed, steps=steps)
            v32_summary, _v32_traces = v32_runner(seed=seed, steps=steps)
            model_tables.append(_prepare_summary(v3_summary, model="v3", suite=suite_name, steps=steps))
            model_tables.append(_prepare_summary(v32_summary, model="v3.2", suite=suite_name, steps=steps))
    by_model = pd.concat(model_tables, ignore_index=True)
    delta = build_v3_2_delta_summary(by_model)
    return by_model, delta


def build_v3_2_delta_summary(by_model: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    group_keys = ["suite", "scenario", "validation_steps"]
    for keys, group in by_model.groupby(group_keys, sort=True):
        suite, scenario, validation_steps = keys
        if set(group["model"]) != {"v3", "v3.2"}:
            continue
        v3_row = group[group["model"] == "v3"].iloc[0]
        v32_row = group[group["model"] == "v3.2"].iloc[0]
        row: dict[str, object] = {
            "suite": suite,
            "scenario": scenario,
            "validation_steps": int(validation_steps),
            "v3_final_dominance_regime": str(v3_row["final_dominance_regime"]),
            "v32_final_dominance_regime": str(v32_row["final_dominance_regime"]),
        }
        for metric in COMPARISON_METRICS:
            row[f"v3_{metric}"] = float(v3_row[metric])
            row[f"v32_{metric}"] = float(v32_row[metric])
            row[f"{metric}_v32_minus_v3"] = float(v32_row[metric] - v3_row[metric])
        for metric in V32_EXTRA_METRICS:
            if metric in v32_row.index:
                row[f"v32_{metric}"] = float(v32_row[metric])
        row["total_gain_delta_v32_minus_v3"] = row[
            "final_total_gain_distribution_weighted_mean_v32_minus_v3"
        ]
        row["damage_delta_v32_minus_v3"] = row["final_damage_distribution_weighted_mean_v32_minus_v3"]
        row["friction_delta_v32_minus_v3"] = row["final_friction_distribution_weighted_mean_v32_minus_v3"]
        row["flow_delta_v32_minus_v3"] = row["final_total_flow_v32_minus_v3"]
        row["v3_2_comparison_readout"] = _comparison_readout(row)
        rows.append(row)
    return pd.DataFrame(rows)


def _numeric_row_value(row: dict[str, object], key: str, default: float = 0.0) -> float:
    value = row.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _comparison_readout(row: dict[str, object]) -> str:
    v3_regime = str(row["v3_final_dominance_regime"])
    v32_regime = str(row["v32_final_dominance_regime"])
    total_gain_delta = _numeric_row_value(row, "total_gain_delta_v32_minus_v3")
    damage_delta = _numeric_row_value(row, "damage_delta_v32_minus_v3")
    friction_delta = _numeric_row_value(row, "friction_delta_v32_minus_v3")
    flow_delta = _numeric_row_value(row, "flow_delta_v32_minus_v3")
    advantage = _numeric_row_value(row, "v32_final_expected_value_advantage_distribution_weighted_mean")
    memory = _numeric_row_value(row, "v32_final_information_memory_distribution_weighted_mean")

    if v3_regime == "short_dominant" and v32_regime == "medium_dominant":
        return "v32_creates_medium_route"
    if total_gain_delta >= 0.03 and damage_delta <= -0.05 and friction_delta <= -0.01:
        return "v32_improves_gain_damage_and_cost"
    if memory > 0.02 and advantage > 0.01 and total_gain_delta >= 0.0:
        return "v32_expected_value_route_active"
    if memory > 0.02 and total_gain_delta >= 0.0:
        return "v32_information_memory_active"
    if total_gain_delta < -0.05 and damage_delta > 0.05:
        return "v32_worse_on_gain_and_damage"
    if flow_delta > 0.02:
        return "v32_flow_higher"
    return "v32_mixed_comparison"


def export_v3_2_long_horizon_comparison(
    output_dir: str | Path,
    *,
    seed: int = LONG_HORIZON_COMPARISON_SEED,
    steps_set: tuple[int, ...] = LONG_HORIZON_COMPARISON_STEPS,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    by_model, delta = run_v3_2_long_horizon_comparison(seed=seed, steps_set=steps_set)
    by_model.to_csv(root / "v3_2_long_horizon_by_model_summary.csv", index=False)
    by_model.to_json(root / "v3_2_long_horizon_by_model_summary.json", orient="records", indent=2)
    delta.to_csv(root / "v3_2_long_horizon_delta_summary.csv", index=False)
    delta.to_json(root / "v3_2_long_horizon_delta_summary.json", orient="records", indent=2)
    return by_model, delta


def compact_model_readout(table: pd.DataFrame) -> pd.DataFrame:
    available = [column for column in COMPACT_MODEL_COLUMNS if column in table.columns]
    return table[available].copy()


def compact_delta_readout(table: pd.DataFrame) -> pd.DataFrame:
    available = [column for column in COMPACT_DELTA_COLUMNS if column in table.columns]
    return table[available].copy()


if __name__ == "__main__":
    by_model_table, delta_table = export_v3_2_long_horizon_comparison(
        "outputs/pseudoreality-v3-validation/v3-2-long-horizon-comparison",
        seed=LONG_HORIZON_COMPARISON_SEED,
        steps_set=LONG_HORIZON_COMPARISON_STEPS,
    )
    print("\n=== v3/v3.2 by-model readout ===")
    print(compact_model_readout(by_model_table).to_string(index=False))
    print("\n=== v3.2 delta readout ===")
    print(compact_delta_readout(delta_table).to_string(index=False))
