"""Seed-variation validation for PseudoReality v3.

This script is diagnostic-only. It runs existing default/stable/typical scenario
suites across multiple random seeds and summarizes whether the numeric readouts
remain stable. It does not change v3 dynamics, add phenomenon flags, connect to
G_t/O_t/DEPT, or introduce an action module.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pandas as pd

from pseudo_reality.distribution_terrain_v3_scenarios import (
    run_default_scenario_suite,
    run_stable_scenario_suite,
)
from scripts.pseudoreality_v3_medium_pattern_validation import (
    add_dominance_columns,
    add_total_gain_columns,
)
from scripts.pseudoreality_v3_typical_pattern_suite import run_typical_pattern_scenario_suite


SEED_VARIATION_SEEDS = (0, 1, 2, 3, 4)
SEED_VARIATION_STEPS = 30
VARIATION_METRIC_COLUMNS = (
    "final_short_payoff_distribution_weighted_mean",
    "final_medium_payoff_distribution_weighted_mean",
    "final_total_gain_distribution_weighted_mean",
    "delta_total_gain_distribution_weighted_mean",
    "final_short_dominance_distribution_weighted_margin",
    "final_medium_dominance_distribution_weighted_margin",
    "short_dominant_total_gain_decline_tension",
    "final_damage_distribution_weighted_mean",
    "final_rigidity_distribution_weighted_mean",
    "final_friction_distribution_weighted_mean",
    "final_total_flow",
)
COMPACT_AGGREGATE_COLUMNS = (
    "suite",
    "scenario",
    "validation_steps",
    "seed_count",
    "dominant_regime_mode",
    "dominant_regime_mode_count",
    "final_total_gain_distribution_weighted_mean_mean",
    "final_total_gain_distribution_weighted_mean_std",
    "delta_total_gain_distribution_weighted_mean_mean",
    "delta_total_gain_distribution_weighted_mean_std",
    "final_damage_distribution_weighted_mean_mean",
    "final_damage_distribution_weighted_mean_std",
    "final_total_flow_mean",
    "final_total_flow_std",
    "seed_stability_note",
)
LEADING_COLUMNS = ("suite", "validation_steps", "seed")


def _scenario_suites() -> tuple[
    tuple[str, Callable[..., tuple[pd.DataFrame, dict[str, dict[str, pd.DataFrame]]]]],
    ...,
]:
    return (
        ("default", run_default_scenario_suite),
        ("stable", run_stable_scenario_suite),
        ("typical", run_typical_pattern_scenario_suite),
    )


def _with_front_columns(summary: pd.DataFrame, *, suite_name: str, seed: int, steps: int) -> pd.DataFrame:
    enriched = summary.copy()
    enriched["suite"] = suite_name
    enriched["validation_steps"] = int(steps)
    enriched["seed"] = int(seed)
    ordered = [column for column in LEADING_COLUMNS if column in enriched.columns]
    ordered.extend(column for column in enriched.columns if column not in ordered)
    return enriched[ordered]


def _run_suite_for_seed(
    *,
    suite_name: str,
    runner: Callable[..., tuple[pd.DataFrame, dict[str, dict[str, pd.DataFrame]]]],
    seed: int,
    steps: int,
) -> pd.DataFrame:
    summary, _traces_by_scenario = runner(seed=seed, steps=steps)
    summary = add_dominance_columns(summary)
    summary = add_total_gain_columns(summary)
    return _with_front_columns(summary, suite_name=suite_name, seed=seed, steps=steps)


def run_seed_variation_validation(
    *,
    seeds: tuple[int, ...] = SEED_VARIATION_SEEDS,
    steps: int = SEED_VARIATION_STEPS,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run seed variation validation and return per-seed and aggregate tables."""

    per_seed_tables: list[pd.DataFrame] = []
    for suite_name, runner in _scenario_suites():
        for seed in seeds:
            per_seed_tables.append(_run_suite_for_seed(suite_name=suite_name, runner=runner, seed=seed, steps=steps))

    per_seed = pd.concat(per_seed_tables, ignore_index=True)
    aggregate = aggregate_seed_variation(per_seed)
    return per_seed, aggregate


def aggregate_seed_variation(per_seed: pd.DataFrame) -> pd.DataFrame:
    """Aggregate seed variation by suite/scenario/step."""

    group_keys = ["suite", "scenario", "validation_steps"]
    rows: list[dict[str, object]] = []
    available_metric_columns = [column for column in VARIATION_METRIC_COLUMNS if column in per_seed.columns]
    for keys, group in per_seed.groupby(group_keys, sort=True):
        suite, scenario, validation_steps = keys
        row: dict[str, object] = {
            "suite": suite,
            "scenario": scenario,
            "validation_steps": int(validation_steps),
            "seed_count": int(group["seed"].nunique()),
        }
        regime_counts = group["final_dominance_regime"].value_counts()
        row["dominant_regime_mode"] = str(regime_counts.index[0])
        row["dominant_regime_mode_count"] = int(regime_counts.iloc[0])
        row["dominant_regime_unique_count"] = int(regime_counts.shape[0])
        for regime, count in regime_counts.items():
            row[f"dominance_regime_count_{regime}"] = int(count)

        for column in available_metric_columns:
            row[f"{column}_mean"] = float(group[column].mean())
            row[f"{column}_std"] = float(group[column].std(ddof=0))
            row[f"{column}_min"] = float(group[column].min())
            row[f"{column}_max"] = float(group[column].max())
            row[f"{column}_range"] = float(group[column].max() - group[column].min())

        row["seed_stability_note"] = _seed_stability_note(row)
        rows.append(row)
    return pd.DataFrame(rows)


def _numeric_row_value(row: dict[str, object], key: str, default: float = 0.0) -> float:
    value = row.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _seed_stability_note(row: dict[str, object]) -> str:
    regime_unique = int(row.get("dominant_regime_unique_count", 0))
    total_gain_std = _numeric_row_value(row, "final_total_gain_distribution_weighted_mean_std")
    total_gain_range = _numeric_row_value(row, "final_total_gain_distribution_weighted_mean_range")
    damage_range = _numeric_row_value(row, "final_damage_distribution_weighted_mean_range")

    if regime_unique > 1 and total_gain_range > 0.05:
        return "regime_and_gain_seed_sensitive"
    if regime_unique > 1:
        return "regime_seed_sensitive"
    if total_gain_range > 0.05 or damage_range > 0.05:
        return "magnitude_seed_sensitive"
    if total_gain_std < 0.02:
        return "stable_across_tested_seeds"
    return "near_stable_across_tested_seeds"


def export_seed_variation_validation(
    output_dir: str | Path,
    *,
    seeds: tuple[int, ...] = SEED_VARIATION_SEEDS,
    steps: int = SEED_VARIATION_STEPS,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Export per-seed and aggregate seed-variation validation tables."""

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    per_seed, aggregate = run_seed_variation_validation(seeds=seeds, steps=steps)
    per_seed.to_csv(root / "seed_variation_per_seed_summary.csv", index=False)
    per_seed.to_json(root / "seed_variation_per_seed_summary.json", orient="records", indent=2)
    aggregate.to_csv(root / "seed_variation_aggregate_summary.csv", index=False)
    aggregate.to_json(root / "seed_variation_aggregate_summary.json", orient="records", indent=2)
    return per_seed, aggregate


def compact_aggregate_readout(table: pd.DataFrame) -> pd.DataFrame:
    available = [column for column in COMPACT_AGGREGATE_COLUMNS if column in table.columns]
    return table[available].copy()


if __name__ == "__main__":
    _per_seed, aggregate_table = export_seed_variation_validation(
        "outputs/pseudoreality-v3-validation/seed-variation",
        seeds=SEED_VARIATION_SEEDS,
        steps=SEED_VARIATION_STEPS,
    )
    print(compact_aggregate_readout(aggregate_table).to_string(index=False))
