from __future__ import annotations

import task3_2_4_result_runner as runner


def _metrics(**overrides):
    values = {
        "event_recall": 1.0,
        "median_lead_time_steps": 4.0,
        "false_alarm_rate": 0.02,
        "false_alarm_trajectory_count": 0,
        "near_state_pair_accuracy": 0.45,
        "depth_mae": 0.004,
        "brier_score": 0.03,
    }
    values.update(overrides)
    return values


def test_earlier_warning_with_safe_false_alarm_and_depth_loss_is_partial() -> None:
    config = runner.load_config()
    result = runner._judgement(
        _metrics(
            median_lead_time_steps=7.0,
            false_alarm_trajectory_count=1,
            near_state_pair_accuracy=0.375,
            depth_mae=0.027,
            brier_score=0.062,
        ),
        _metrics(),
        config,
    )
    assert result["grade"] == "B_macro_dynamics_partially_promising"
    assert result["core_improvements"]["lead_time"] is True
    assert result["core_degraded"] is True
    assert result["degradation_reasons"]["safe_trajectory_false_alarm"] is True
    assert result["degradation_reasons"]["depth_mae"] is True


def test_clean_lead_time_gain_can_be_A() -> None:
    config = runner.load_config()
    result = runner._judgement(
        _metrics(median_lead_time_steps=7.0, false_alarm_rate=0.01, depth_mae=0.0038),
        _metrics(),
        config,
    )
    assert result["grade"] == "A_macro_dynamics_promising"
    assert result["core_degraded"] is False


def test_no_gain_and_no_secondary_improvement_is_C() -> None:
    config = runner.load_config()
    result = runner._judgement(
        _metrics(false_alarm_rate=0.04, depth_mae=0.006, brier_score=0.05),
        _metrics(),
        config,
    )
    assert result["grade"] == "C_macro_dynamics_not_promising_at_current_resolution"
