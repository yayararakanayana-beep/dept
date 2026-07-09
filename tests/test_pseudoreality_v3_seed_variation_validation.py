from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.pseudoreality_v3_seed_variation_validation import (
    aggregate_seed_variation,
    compact_aggregate_readout,
    export_seed_variation_validation,
    run_seed_variation_validation,
)


def test_run_seed_variation_validation_returns_per_seed_and_aggregate_tables():
    per_seed, aggregate = run_seed_variation_validation(seeds=(0, 1), steps=4)

    assert not per_seed.empty
    assert not aggregate.empty
    assert {"default", "stable", "typical"} <= set(per_seed["suite"])
    assert set(per_seed["seed"]) == {0, 1}
    assert "final_dominance_regime" in per_seed.columns
    assert "seed_count" in aggregate.columns
    assert "dominant_regime_mode" in aggregate.columns
    assert "seed_stability_note" in aggregate.columns


def test_aggregate_seed_variation_summarizes_expected_columns():
    per_seed, _aggregate = run_seed_variation_validation(seeds=(0, 1), steps=4)
    aggregate = aggregate_seed_variation(per_seed)

    assert "final_total_gain_distribution_weighted_mean_mean" in aggregate.columns
    assert "final_total_gain_distribution_weighted_mean_std" in aggregate.columns
    assert "final_damage_distribution_weighted_mean_range" in aggregate.columns
    assert aggregate["seed_count"].min() == 2


def test_export_seed_variation_validation_writes_outputs(tmp_path):
    per_seed, aggregate = export_seed_variation_validation(tmp_path, seeds=(0, 1), steps=4)

    assert not per_seed.empty
    assert not aggregate.empty
    assert (tmp_path / "seed_variation_per_seed_summary.csv").exists()
    assert (tmp_path / "seed_variation_per_seed_summary.json").exists()
    assert (tmp_path / "seed_variation_aggregate_summary.csv").exists()
    assert (tmp_path / "seed_variation_aggregate_summary.json").exists()


def test_compact_aggregate_readout_keeps_log_safe_columns():
    _per_seed, aggregate = run_seed_variation_validation(seeds=(0, 1), steps=4)
    compact = compact_aggregate_readout(aggregate)

    assert "suite" in compact.columns
    assert "scenario" in compact.columns
    assert "seed_stability_note" in compact.columns
    assert len(compact.columns) < len(aggregate.columns)
