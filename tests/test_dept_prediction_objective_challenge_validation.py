from dept2_fullspec_runner_rc1.validation.dept_prediction_objective_challenge_validation import (
    OBJECTIVE_PATTERNS,
    PredictionObjectiveChallengeConfig,
    run_prediction_objective_challenge_validation,
)


def _small_cfg():
    return PredictionObjectiveChallengeConfig(
        seeds=(11, 22),
        patterns=tuple(OBJECTIVE_PATTERNS),
        noise_levels=(0.0, 0.04),
        horizons=(1, 2, 3),
        history_steps=5,
        source_steps=3,
    )


def test_objective_challenge_outputs_tables():
    outputs = run_prediction_objective_challenge_validation(_small_cfg())
    assert set(outputs) == {
        "prediction_objective_challenge_rows",
        "prediction_objective_challenge_method_summary",
        "prediction_objective_challenge_balanced_accuracy",
        "prediction_objective_challenge_baseline_comparison",
        "prediction_objective_challenge_seed_stability",
        "prediction_objective_challenge_direction_distribution",
        "prediction_objective_challenge_worst_cases",
        "prediction_objective_challenge_boundary",
    }
    assert all(table is not None and not table.empty for table in outputs.values())


def test_objective_challenge_covers_balanced_directions():
    rows = run_prediction_objective_challenge_validation(_small_cfg())["prediction_objective_challenge_rows"]
    assert set(rows["actual_direction"]) == {"neutral", "overconvergence", "fixation", "divergence"}
    assert set(rows["horizon"]) == {1, 2, 3}
    assert set(rows["noise_level"]) == {0.0, 0.04}


def test_objective_challenge_reports_measurements_only():
    outputs = run_prediction_objective_challenge_validation(_small_cfg())
    method_summary = outputs["prediction_objective_challenge_method_summary"]
    balanced = outputs["prediction_objective_challenge_balanced_accuracy"]
    comparison = outputs["prediction_objective_challenge_baseline_comparison"]
    assert method_summary["direction_match_rate"].between(0.0, 1.0).all()
    assert method_summary["mean_strength_abs_error"].ge(0.0).all()
    assert method_summary["max_strength_abs_error"].ge(0.0).all()
    assert method_summary["p95_strength_abs_error"].ge(0.0).all()
    assert balanced["balanced_direction_match_rate"].between(0.0, 1.0).all()
    assert "direction_match_lift" in comparison.columns
    assert "mean_strength_error_delta_vs_baseline" in comparison.columns
    assert "max_strength_error_delta_vs_baseline" in comparison.columns
    assert "p95_strength_error_delta_vs_baseline" in comparison.columns
    blocked_terms = ("pass", "floor", "ceiling")
    for table in (method_summary, balanced, comparison):
        for col in table.columns:
            assert not any(term in col for term in blocked_terms), col
