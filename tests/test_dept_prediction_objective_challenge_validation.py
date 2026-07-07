from dept2_fullspec_runner_rc1.validation.dept_prediction_objective_challenge_validation import (
    NEUTRAL_BASELINE_METHOD,
    OBJECTIVE_PATTERNS,
    PREDICTION_METHOD,
    PREVIOUS_STEP_BASELINE_METHOD,
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
        direction_match_floor=0.0,
        balanced_direction_floor=0.0,
        strength_abs_error_ceiling=1.0,
    )


def test_objective_challenge_outputs_all_core_tables():
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
    for name, table in outputs.items():
        assert table is not None, name
        assert not table.empty, name


def test_objective_challenge_is_direction_balanced_and_covers_methods():
    cfg = _small_cfg()
    rows = run_prediction_objective_challenge_validation(cfg)["prediction_objective_challenge_rows"]
    assert set(rows["method"]) == {
        PREDICTION_METHOD,
        NEUTRAL_BASELINE_METHOD,
        PREVIOUS_STEP_BASELINE_METHOD,
    }
    assert set(rows["pattern"]) == set(cfg.patterns)
    assert set(rows["seed"]) == set(cfg.seeds)
    assert set(rows["noise_level"]) == set(cfg.noise_levels)
    assert set(rows["horizon"]) == set(cfg.horizons)
    assert set(rows["actual_direction"]) == {"neutral", "overconvergence", "fixation", "divergence"}


def test_objective_challenge_boundary_and_future_usage_contract():
    outputs = run_prediction_objective_challenge_validation(_small_cfg())
    rows = outputs["prediction_objective_challenge_rows"]
    boundary = outputs["prediction_objective_challenge_boundary"].iloc[0]
    assert bool(rows["forbidden_v2_trace_keys_passed_to_prediction"].any()) is False
    assert bool(boundary["forbidden_v2_trace_keys_passed_to_prediction"]) is False
    assert bool(boundary["boundary_pass"]) is True
    assert bool(boundary["direction_diversity_pass"]) is True
    assert boundary["prediction_input_contract"] == "public_trace_history_projection_only"
    assert boundary["future_usage"] == "heldout_answer_key_only"


def test_objective_challenge_reports_metrics_without_hiding_failures():
    outputs = run_prediction_objective_challenge_validation(_small_cfg())
    method_summary = outputs["prediction_objective_challenge_method_summary"]
    balanced = outputs["prediction_objective_challenge_balanced_accuracy"]
    comparison = outputs["prediction_objective_challenge_baseline_comparison"]
    worst = outputs["prediction_objective_challenge_worst_cases"]
    assert method_summary["direction_match_rate"].between(0.0, 1.0).all()
    assert method_summary["mean_strength_abs_error"].ge(0.0).all()
    assert balanced["balanced_direction_match_rate"].between(0.0, 1.0).all()
    assert "direction_match_lift" in comparison.columns
    assert "strength_error_reduction" in comparison.columns
    assert len(worst) > 0
