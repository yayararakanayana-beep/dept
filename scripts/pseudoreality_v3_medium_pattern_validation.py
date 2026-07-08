"""Medium-pattern validation exports for PseudoReality v3.

This script is diagnostic-only. It post-processes PseudoReality v3 scenario
summaries to add short/medium dominance readouts and exports 30/50/100-step
validation summary tables for default and stable scenario suites.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pandas as pd

from pseudo_reality.distribution_terrain_v3_scenarios import (
    run_default_scenario_suite,
    run_stable_scenario_suite,
)


MEDIUM_PATTERN_STEPS = (30, 50, 100)
SHORT_WEIGHTED_COLUMN = "final_short_payoff_distribution_weighted_mean"
MEDIUM_WEIGHTED_COLUMN = "final_medium_payoff_distribution_weighted_mean"
INITIAL_SHORT_WEIGHTED_COLUMN = "initial_short_payoff_distribution_weighted_mean"
INITIAL_MEDIUM_WEIGHTED_COLUMN = "initial_medium_payoff_distribution_weighted_mean"
COMPACT_PRINT_COLUMNS = (
    "suite",
    "validation_steps",
    "scenario",
    SHORT_WEIGHTED_COLUMN,
    MEDIUM_WEIGHTED_COLUMN,
    "final_short_dominance_distribution_weighted_margin",
    "final_medium_dominance_distribution_weighted_margin",
    "final_dominance_regime",
    "final_composite_payoff_distribution_weighted_mean",
    "final_damage_distribution_weighted_mean",
    "final_total_flow",
)


def add_dominance_columns(summary: pd.DataFrame) -> pd.DataFrame:
    """Add short/medium dominance margins to a scenario summary table."""

    enriched = summary.copy()
    enriched["initial_short_dominance_distribution_weighted_margin"] = (
        enriched[INITIAL_SHORT_WEIGHTED_COLUMN] - enriched[INITIAL_MEDIUM_WEIGHTED_COLUMN]
    )
    enriched["initial_medium_dominance_distribution_weighted_margin"] = (
        enriched[INITIAL_MEDIUM_WEIGHTED_COLUMN] - enriched[INITIAL_SHORT_WEIGHTED_COLUMN]
    )
    enriched["final_short_dominance_distribution_weighted_margin"] = (
        enriched[SHORT_WEIGHTED_COLUMN] - enriched[MEDIUM_WEIGHTED_COLUMN]
    )
    enriched["final_medium_dominance_distribution_weighted_margin"] = (
        enriched[MEDIUM_WEIGHTED_COLUMN] - enriched[SHORT_WEIGHTED_COLUMN]
    )
    enriched["delta_short_dominance_distribution_weighted_margin"] = (
        enriched["final_short_dominance_distribution_weighted_margin"]
        - enriched["initial_short_dominance_distribution_weighted_margin"]
    )
    enriched["delta_medium_dominance_distribution_weighted_margin"] = (
        enriched["final_medium_dominance_distribution_weighted_margin"]
        - enriched["initial_medium_dominance_distribution_weighted_margin"]
    )
    enriched["final_dominance_regime"] = enriched.apply(_dominance_regime, axis=1)
    return enriched


def _dominance_regime(row: pd.Series) -> str:
    margin = float(row["final_medium_dominance_distribution_weighted_margin"])
    if margin > 0.05:
        return "medium_dominant"
    if margin < -0.05:
        return "short_dominant"
    return "mixed_or_near_balanced"


def _export_suite(
    *,
    root: Path,
    suite_name: str,
    steps: int,
    runner: Callable[..., tuple[pd.DataFrame, dict[str, dict[str, pd.DataFrame]]]],
) -> pd.DataFrame:
    output_dir = root / f"{suite_name}_steps_{steps}"
    output_dir.mkdir(parents=True, exist_ok=True)
    summary, _traces_by_scenario = runner(seed=0, steps=steps)
    summary = add_dominance_columns(summary)
    summary.insert(0, "suite", suite_name)
    summary.insert(1, "validation_steps", steps)
    summary.to_csv(output_dir / "scenario_summary.csv", index=False)
    summary.to_json(output_dir / "scenario_summary.json", orient="records", indent=2)
    return summary


def run_medium_pattern_validation(output_dir: str | Path) -> pd.DataFrame:
    """Run default/stable scenario suites for 30/50/100 steps and export summaries."""

    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    summaries: list[pd.DataFrame] = []
    suites = (
        ("default", run_default_scenario_suite),
        ("stable", run_stable_scenario_suite),
    )
    for steps in MEDIUM_PATTERN_STEPS:
        for suite_name, runner in suites:
            summaries.append(_export_suite(root=root, suite_name=suite_name, steps=steps, runner=runner))

    combined = pd.concat(summaries, ignore_index=True)
    combined.to_csv(root / "medium_pattern_summary.csv", index=False)
    combined.to_json(root / "medium_pattern_summary.json", orient="records", indent=2)
    return combined


def compact_readout(table: pd.DataFrame) -> pd.DataFrame:
    """Return a compact, log-safe readout for GitHub Actions output."""

    available = [column for column in COMPACT_PRINT_COLUMNS if column in table.columns]
    return table[available].copy()


if __name__ == "__main__":
    table = run_medium_pattern_validation("outputs/pseudoreality-v3-validation/medium-pattern")
    print(compact_readout(table).to_string(index=False))
