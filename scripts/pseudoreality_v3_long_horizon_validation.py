"""Long-horizon validation for PseudoReality v3.

This module is diagnostic-only. It runs existing PseudoReality v3 scenario suites
at longer horizons and summarizes whether short/medium dominance, total gain,
damage, rigidity, friction, and flow remain stable or drift over time. It does
not change v3 dynamics, add phenomenon flags, connect to G_t/O_t/DEPT, or add an
action module.
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


LONG_HORIZON_STEPS = (50, 100, 200)
LONG_HORIZON_SEED = 0
LONG_HORIZON_METRIC_COLUMNS = (
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
COMPACT_HORIZON_COLUMNS = (
    "suite",
    "validation_steps",
    "scenario",
    "final_dominance_regime",
    "final_total_gain_distribution_weighted_mean",
    "delta_total_gain_distribution_weighted_mean",
    "final_damage_distribution_weighted_mean",
    "final_rigidity_distribution_weighted_mean",
    "final_friction_distribution_weighted_mean",
    "final_total_flow",
    "long_horizon_point_readout",
)
COMPACT_TREND_COLUMNS = (
    "suite",
    "scenario",
    "min_validation_steps",
    "max_validation_steps",
    "dominance_regime_unique_count",
    "first_dominance_regime",
    "last_dominance_regime",
    "total_gain_change_from_min_to_max",
    "damage_change_from_min_to_max",
    "flow_change_from_min_to_max",
    "long_horizon_trend_readout",
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


def _run_suite_for_horizon(
    *,
    suite_name: str,
    runner: Callable[..., tuple[pd.DataFrame, dict[str, dict[str, pd.DataFrame]]]],
    seed: int,
    steps: int,
) -> pd.DataFrame:
    summary, _traces_by_scenario = runner(seed=seed, steps=steps)
    summary = add_dominance_columns(summary)
    summary = add_total_gain_columns(summary)
    summary = _with_front_columns(summary, suite_name=suite_name, seed=seed, steps=steps)
    summary["long_horizon_point_readout"] = summary.apply(_point_readout, axis=1)
    return summary


def _point_readout(row: pd.Series) -> str:
    total_delta = float(row["delta_total_gain_distribution_weighted_mean"])
    damage = float(row.get("final_damage_distribution_weighted_mean", 0.0))
    flow = float(row.get("final_total_flow", 0.0))
    regime = str(row["final_dominance_regime"])

    if damage >= 0.90 and flow <= 0.03:
        return "high_damage_low_flow"
    if damage >= 0.70:
        return "high_damage_persistent"
    if total_delta >= 0.10 and damage < 0.40:
        return f"{regime}_gain_rising"
    if total_delta <= -0.10:
        return f"{regime}_gain_declining"
    if abs(total_delta) < 0.05 and damage < 0.20:
        return f"{regime}_near_stable"
    return f"{regime}_mixed_long_horizon"


def run_long_horizon_validation(
    *,
    seed: int = LONG_HORIZON_SEED,
    steps_set: tuple[int, ...] = LONG_HORIZON_STEPS,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run long-horizon validation and return per-horizon and trend tables."""

    per_horizon_tables: list[pd.DataFrame] = []
    for steps in steps_set:
        for suite_name, runner in _scenario_suites():
            per_horizon_tables.append(
                _run_suite_for_horizon(suite_name=suite_name, runner=runner, seed=seed, steps=int(steps))
            )
    per_horizon = pd.concat(per_horizon_tables, ignore_index=True)
    trend = aggregate_long_horizon_trends(per_horizon)
    return per_horizon, trend


def aggregate_long_horizon_trends(per_horizon: pd.DataFrame) -> pd.DataFrame:
    """Aggregate long-horizon drift by suite/scenario."""

    rows: list[dict[str, object]] = []
    group_keys = ["suite", "scenario"]
    available_metric_columns = [column for column in LONG_HORIZON_METRIC_COLUMNS if column in per_horizon.columns]
    for keys, group in per_horizon.groupby(group_keys, sort=True):
        suite, scenario = keys
        ordered = group.sort_values("validation_steps")
        first = ordered.iloc[0]
        last = ordered.iloc[-1]
        regime_counts = ordered["final_dominance_regime"].value_counts()
        row: dict[str, object] = {
            "suite": suite,
            "scenario": scenario,
            "seed": int(last["seed"]),
            "min_validation_steps": int(first["validation_steps"]),
            "max_validation_steps": int(last["validation_steps"]),
            "horizon_count": int(ordered["validation_steps"].nunique()),
            "first_dominance_regime": str(first["final_dominance_regime"]),
            "last_dominance_regime": str(last["final_dominance_regime"]),
            "dominance_regime_unique_count": int(regime_counts.shape[0]),
        }
        for regime, count in regime_counts.items():
            row[f"dominance_regime_count_{regime}"] = int(count)

        for column in available_metric_columns:
            row[f"{column}_at_min_horizon"] = float(first[column])
            row[f"{column}_at_max_horizon"] = float(last[column])
            row[f"{column}_change_from_min_to_max"] = float(last[column] - first[column])
            row[f"{column}_range_across_horizons"] = float(ordered[column].max() - ordered[column].min())

        row["total_gain_change_from_min_to_max"] = row.get(
            "final_total_gain_distribution_weighted_mean_change_from_min_to_max",
            0.0,
        )
        row["damage_change_from_min_to_max"] = row.get(
            "final_damage_distribution_weighted_mean_change_from_min_to_max",
            0.0,
        )
        row["flow_change_from_min_to_max"] = row.get("final_total_flow_change_from_min_to_max", 0.0)
        row["long_horizon_trend_readout"] = _trend_readout(row)
        rows.append(row)
    return pd.DataFrame(rows)


def _numeric_row_value(row: dict[str, object], key: str, default: float = 0.0) -> float:
    value = row.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _trend_readout(row: dict[str, object]) -> str:
    regime_unique = int(row.get("dominance_regime_unique_count", 0))
    total_gain_change = _numeric_row_value(row, "total_gain_change_from_min_to_max")
    damage_change = _numeric_row_value(row, "damage_change_from_min_to_max")
    flow_change = _numeric_row_value(row, "flow_change_from_min_to_max")
    final_damage = _numeric_row_value(row, "final_damage_distribution_weighted_mean_at_max_horizon")
    final_flow = _numeric_row_value(row, "final_total_flow_at_max_horizon")

    if regime_unique > 1 and total_gain_change < -0.05:
        return "regime_shift_with_gain_decline"
    if final_damage >= 0.90 and final_flow <= 0.03:
        return "high_damage_low_flow_at_long_horizon"
    if total_gain_change >= 0.05 and damage_change <= 0.10:
        return "gain_improves_without_large_damage_accumulation"
    if abs(total_gain_change) < 0.03 and abs(damage_change) < 0.05 and abs(flow_change) < 0.03:
        return "near_stable_across_horizons"
    if damage_change >= 0.15:
        return "damage_accumulation_across_horizons"
    if total_gain_change <= -0.05:
        return "gain_declines_across_horizons"
    return "mixed_long_horizon_drift"


def export_long_horizon_validation(
    output_dir: str | Path,
    *,
    seed: int = LONG_HORIZON_SEED,
    steps_set: tuple[int, ...] = LONG_HORIZON_STEPS,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Export per-horizon and trend tables for long-horizon validation."""

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    per_horizon, trend = run_long_horizon_validation(seed=seed, steps_set=steps_set)
    per_horizon.to_csv(root / "long_horizon_per_horizon_summary.csv", index=False)
    per_horizon.to_json(root / "long_horizon_per_horizon_summary.json", orient="records", indent=2)
    trend.to_csv(root / "long_horizon_trend_summary.csv", index=False)
    trend.to_json(root / "long_horizon_trend_summary.json", orient="records", indent=2)
    return per_horizon, trend


def compact_horizon_readout(table: pd.DataFrame) -> pd.DataFrame:
    available = [column for column in COMPACT_HORIZON_COLUMNS if column in table.columns]
    return table[available].copy()


def compact_trend_readout(table: pd.DataFrame) -> pd.DataFrame:
    available = [column for column in COMPACT_TREND_COLUMNS if column in table.columns]
    return table[available].copy()


if __name__ == "__main__":
    per_horizon_table, trend_table = export_long_horizon_validation(
        "outputs/pseudoreality-v3-validation/long-horizon",
        seed=LONG_HORIZON_SEED,
        steps_set=LONG_HORIZON_STEPS,
    )
    print("\n=== long horizon per-horizon readout ===")
    print(compact_horizon_readout(per_horizon_table).to_string(index=False))
    print("\n=== long horizon trend readout ===")
    print(compact_trend_readout(trend_table).to_string(index=False))
