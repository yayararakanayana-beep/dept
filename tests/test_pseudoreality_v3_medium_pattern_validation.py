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


def test_run_medium_pattern_validation_exports_combined_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(medium_validation, "MEDIUM_PATTERN_STEPS", (1,))

    summary = medium_validation.run_medium_pattern_validation(tmp_path)

    assert set(summary["validation_steps"]) == {1}
    assert {"default", "stable"} <= set(summary["suite"])
    assert "final_short_dominance_distribution_weighted_margin" in summary.columns
    assert "final_medium_dominance_distribution_weighted_margin" in summary.columns
    assert "final_dominance_regime" in summary.columns
    assert (tmp_path / "medium_pattern_summary.csv").exists()
    assert (tmp_path / "default_steps_1" / "scenario_summary.csv").exists()
    assert (tmp_path / "stable_steps_1" / "scenario_summary.csv").exists()
