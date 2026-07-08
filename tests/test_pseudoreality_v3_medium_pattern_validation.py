from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import pandas as pd
import pytest

import scripts.pseudoreality_v3_medium_pattern_validation as medium_validation


def test_add_dominance_columns_adds_short_and_medium_margins():
    frame = pd.DataFrame(
        [
            {
                "initial_short_payoff_distribution_weighted_mean": 0.6,
                "initial_medium_payoff_distribution_weighted_mean": 0.4,
                "final_short_payoff_distribution_weighted_mean": 0.7,
                "final_medium_payoff_distribution_weighted_mean": 0.3,
            },
            {
                "initial_short_payoff_distribution_weighted_mean": 0.3,
                "initial_medium_payoff_distribution_weighted_mean": 0.7,
                "final_short_payoff_distribution_weighted_mean": 0.2,
                "final_medium_payoff_distribution_weighted_mean": 0.8,
            },
        ]
    )

    enriched = medium_validation.add_dominance_columns(frame)

    assert enriched["final_short_dominance_distribution_weighted_margin"].iloc[0] == pytest.approx(0.4)
    assert enriched["final_medium_dominance_distribution_weighted_margin"].iloc[1] == pytest.approx(0.6)
    assert enriched["final_dominance_regime"].tolist() == ["short_dominant", "medium_dominant"]


def test_add_total_gain_columns_reads_short_dominant_total_decline_tension():
    frame = pd.DataFrame(
        [
            {
                "final_dominance_regime": "short_dominant",
                "final_short_dominance_distribution_weighted_margin": 0.5,
                "final_short_payoff_distribution_weighted_mean": 0.8,
                "initial_composite_payoff_distribution_weighted_mean": 0.6,
                "final_composite_payoff_distribution_weighted_mean": 0.3,
                "final_total_flow": 0.07,
                "final_damage_distribution_weighted_mean": 0.25,
            }
        ]
    )

    enriched = medium_validation.add_total_gain_columns(frame)

    assert enriched["initial_total_gain_distribution_weighted_mean"].iloc[0] == pytest.approx(0.6)
    assert enriched["final_total_gain_distribution_weighted_mean"].iloc[0] == pytest.approx(0.3)
    assert enriched["delta_total_gain_distribution_weighted_mean"].iloc[0] == pytest.approx(-0.3)
    assert enriched["short_dominant_total_gain_decline_tension"].iloc[0] == pytest.approx(0.15)
    assert enriched["final_total_gain_tension_readout"].iloc[0] == "short_dominant_total_decline_with_damage"


def test_run_medium_pattern_validation_exports_combined_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(medium_validation, "MEDIUM_PATTERN_STEPS", (2,))

    summary = medium_validation.run_medium_pattern_validation(tmp_path)

    assert set(summary["validation_steps"]) == {2}
    assert {"default", "stable"} <= set(summary["suite"])
    assert "final_short_dominance_distribution_weighted_margin" in summary.columns
    assert "final_medium_dominance_distribution_weighted_margin" in summary.columns
    assert "final_dominance_regime" in summary.columns
    assert "final_total_gain_distribution_weighted_mean" in summary.columns
    assert "delta_total_gain_distribution_weighted_mean" in summary.columns
    assert "short_dominant_total_gain_decline_tension" in summary.columns
    assert "final_total_gain_tension_readout" in summary.columns
    assert (tmp_path / "medium_pattern_summary.csv").exists()
    assert (tmp_path / "default_steps_2" / "scenario_summary.csv").exists()
    assert (tmp_path / "stable_steps_2" / "scenario_summary.csv").exists()
