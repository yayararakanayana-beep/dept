from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from scripts.pseudoreality_v3_seed_variation_validation import (
    aggregate_seed_variation,
    compact_aggregate_readout,
    export_seed_variation_validation,
)


def _synthetic_per_seed_table() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "suite": "synthetic",
                "scenario": "stable_case",
                "validation_steps": 4,
                "seed": 0,
                "final_dominance_regime": "medium_dominant",
                "final_total_gain_distribution_weighted_mean": 0.50,
                "delta_total_gain_distribution_weighted_mean": 0.10,
            },
            {
                "suite": "synthetic",
                "scenario": "stable_case",
                "validation_steps": 4,
                "seed": 1,
                "final_dominance_regime": "medium_dominant",
                "final_total_gain_distribution_weighted_mean": 0.52,
                "delta_total_gain_distribution_weighted_mean": 0.12,
            },
        ]
    )


def test_aggregate_seed_variation_summarizes_synthetic_seed_table():
    aggregate = aggregate_seed_variation(_synthetic_per_seed_table())

    assert len(aggregate) == 1
    assert aggregate["seed_count"].iloc[0] == 2
    assert aggregate["dominant_regime_mode"].iloc[0] == "medium_dominant"
    assert "final_total_gain_distribution_weighted_mean_mean" in aggregate.columns
    assert "final_total_gain_distribution_weighted_mean_range" in aggregate.columns
    assert "seed_stability_note" in aggregate.columns


def test_compact_aggregate_readout_keeps_log_safe_columns():
    aggregate = aggregate_seed_variation(_synthetic_per_seed_table())
    compact = compact_aggregate_readout(aggregate)

    assert "suite" in compact.columns
    assert "scenario" in compact.columns
    assert "seed_stability_note" in compact.columns
    assert len(compact.columns) <= len(aggregate.columns)


def test_export_seed_variation_validation_writes_outputs_smoke(tmp_path):
    per_seed, aggregate = export_seed_variation_validation(tmp_path, seeds=(0,), steps=2)

    assert not per_seed.empty
    assert not aggregate.empty
    assert (tmp_path / "seed_variation_per_seed_summary.csv").exists()
    assert (tmp_path / "seed_variation_per_seed_summary.json").exists()
    assert (tmp_path / "seed_variation_aggregate_summary.csv").exists()
    assert (tmp_path / "seed_variation_aggregate_summary.json").exists()
