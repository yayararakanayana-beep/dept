from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd

from scripts.pseudoreality_v3_long_horizon_validation import (
    aggregate_long_horizon_trends,
    compact_horizon_readout,
    compact_trend_readout,
    export_long_horizon_validation,
    run_long_horizon_validation,
)


def _synthetic_per_horizon_table() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "suite": "synthetic",
                "scenario": "stable_case",
                "validation_steps": 50,
                "seed": 0,
                "final_dominance_regime": "medium_dominant",
                "final_total_gain_distribution_weighted_mean": 0.50,
                "delta_total_gain_distribution_weighted_mean": 0.10,
                "final_damage_distribution_weighted_mean": 0.10,
                "final_total_flow": 0.08,
            },
            {
                "suite": "synthetic",
                "scenario": "stable_case",
                "validation_steps": 100,
                "seed": 0,
                "final_dominance_regime": "medium_dominant",
                "final_total_gain_distribution_weighted_mean": 0.52,
                "delta_total_gain_distribution_weighted_mean": 0.12,
                "final_damage_distribution_weighted_mean": 0.11,
                "final_total_flow": 0.09,
            },
        ]
    )


def test_aggregate_long_horizon_trends_summarizes_synthetic_table():
    trend = aggregate_long_horizon_trends(_synthetic_per_horizon_table())

    assert len(trend) == 1
    assert trend["horizon_count"].iloc[0] == 2
    assert trend["first_dominance_regime"].iloc[0] == "medium_dominant"
    assert trend["last_dominance_regime"].iloc[0] == "medium_dominant"
    assert "total_gain_change_from_min_to_max" in trend.columns
    assert "long_horizon_trend_readout" in trend.columns


def test_run_long_horizon_validation_returns_tables_for_short_smoke():
    per_horizon, trend = run_long_horizon_validation(seed=0, steps_set=(5, 6))

    assert not per_horizon.empty
    assert not trend.empty
    assert {5, 6} == set(per_horizon["validation_steps"])
    assert {"default", "stable", "typical"} <= set(per_horizon["suite"])
    assert "long_horizon_point_readout" in per_horizon.columns
    assert "long_horizon_trend_readout" in trend.columns


def test_export_long_horizon_validation_writes_outputs(tmp_path):
    per_horizon, trend = export_long_horizon_validation(tmp_path, seed=0, steps_set=(5, 6))

    assert not per_horizon.empty
    assert not trend.empty
    assert (tmp_path / "long_horizon_per_horizon_summary.csv").exists()
    assert (tmp_path / "long_horizon_per_horizon_summary.json").exists()
    assert (tmp_path / "long_horizon_trend_summary.csv").exists()
    assert (tmp_path / "long_horizon_trend_summary.json").exists()


def test_compact_readouts_keep_log_safe_columns():
    per_horizon, trend = run_long_horizon_validation(seed=0, steps_set=(5, 6))
    horizon_compact = compact_horizon_readout(per_horizon)
    trend_compact = compact_trend_readout(trend)

    assert "suite" in horizon_compact.columns
    assert "scenario" in horizon_compact.columns
    assert "long_horizon_point_readout" in horizon_compact.columns
    assert "long_horizon_trend_readout" in trend_compact.columns
    assert len(horizon_compact.columns) <= len(per_horizon.columns)
    assert len(trend_compact.columns) <= len(trend.columns)
