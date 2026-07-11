from __future__ import annotations

import _task3_2_3_core as core
import task3_2_3_simple_early_warning  # noqa: F401  # installs corrected judgement


def _metrics(**overrides):
    values = {
        "event_recall": 1.0,
        "median_lead_time_steps": 4.0,
        "average_precision": 0.99,
        "depth_rank_correlation": 1.0,
        "false_alarm_rate": 0.02,
        "depth_mae": 0.002,
    }
    values.update(overrides)
    return values


def test_equal_core_performance_with_only_secondary_gains_is_partial() -> None:
    config = core.load_config()
    result = core._research_judgement(
        _metrics(),
        _metrics(false_alarm_rate=0.0, depth_mae=0.0009),
        _metrics(),
        _metrics(false_alarm_rate=0.0, depth_mae=0.0008),
        config,
    )
    assert result["grade"] == "B_partially_promising"
    assert result["core_early_warning_improvement_count"] == 0
    assert result["improved_validation_dimension_count"] == 2


def test_core_gain_plus_secondary_gain_can_be_promising() -> None:
    config = core.load_config()
    result = core._research_judgement(
        _metrics(event_recall=0.7, median_lead_time_steps=2.0),
        _metrics(event_recall=1.0, median_lead_time_steps=4.0, false_alarm_rate=0.0),
        _metrics(event_recall=0.7, median_lead_time_steps=2.0),
        _metrics(event_recall=1.0, median_lead_time_steps=4.0, false_alarm_rate=0.0),
        config,
    )
    assert result["grade"] == "A_promising"
    assert result["core_early_warning_improvement_count"] >= 1
