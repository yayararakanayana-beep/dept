from dept2_fullspec_runner_rc1.validation.dept_prediction_validation_suite import (
    PredictionValidationConfig,
    PATTERNS,
    CORE_DIRECTION_PATTERNS,
    run_dept_prediction_validation,
)


def test_prediction_validation_suite_outputs_core_tables():
    outputs = run_dept_prediction_validation(PredictionValidationConfig(steps=8, activation_threshold=0.004, deep_threshold=0.99))
    assert set(outputs) == {
        "prediction_activation_validation",
        "prediction_activation_summary",
        "prediction_projection_rows",
        "prediction_projection_error_rows",
        "prediction_horizon_summary",
        "prediction_dynamics_rows",
        "prediction_dynamics_summary",
    }
    assert not outputs["prediction_activation_validation"].empty
    assert not outputs["prediction_activation_summary"].empty
    assert not outputs["prediction_dynamics_rows"].empty
    assert not outputs["prediction_dynamics_summary"].empty
    assert set(outputs["prediction_activation_summary"]["pattern"]) == set(PATTERNS)


def test_prediction_activation_responds_to_target_patterns_after_warmup():
    outputs = run_dept_prediction_validation(PredictionValidationConfig(steps=8, activation_threshold=0.004, deep_threshold=0.99))
    summary = outputs["prediction_activation_summary"].set_index("pattern")
    for pattern in ["overconvergence", "fixation", "divergence", "sudden_angle", "sudden_intensity"]:
        assert summary.loc[pattern, "activation_response_match_rate_after_warmup"] >= 0.80
        assert summary.loc[pattern, "max_prediction_need_score"] > 0.0
    assert summary.loc["stable", "activation_response_match_rate_after_warmup"] >= 0.80


def test_prediction_activation_channels_are_visible_for_core_patterns():
    outputs = run_dept_prediction_validation(PredictionValidationConfig(steps=8, activation_threshold=0.004, deep_threshold=0.99))
    summary = outputs["prediction_activation_summary"].set_index("pattern")
    assert summary.loc["overconvergence", "max_overconvergence_integral_mid"] > 0.0
    assert summary.loc["fixation", "max_fixation_integral_mid"] > 0.0
    assert summary.loc["divergence", "max_divergence_integral_mid"] > 0.0
    assert summary.loc["sudden_intensity", "max_short_intensity_change"] > 0.0
    assert summary.loc["sudden_angle", "max_short_angle_change"] > 0.0


def test_dynamics_direction_accuracy_for_core_patterns():
    outputs = run_dept_prediction_validation(PredictionValidationConfig(steps=8, activation_threshold=0.004, deep_threshold=0.99))
    dynamics = outputs["prediction_dynamics_summary"]
    assert not dynamics.empty
    core = dynamics[dynamics["pattern"].isin(CORE_DIRECTION_PATTERNS)]
    assert not core.empty
    assert float(core["dynamics_direction_match_rate"].min()) >= 0.80
    assert float(core["mean_predicted_dynamics_strength"].min()) > 0.0


def test_projection_packaging_accuracy_by_horizon_when_future_trace_supplied():
    outputs = run_dept_prediction_validation(PredictionValidationConfig(steps=6, activation_threshold=0.004, deep_threshold=0.99))
    horizon = outputs["prediction_horizon_summary"]
    assert not horizon.empty
    assert set(horizon["horizon"]) == {1, 2, 3, 5}
    assert bool(horizon["projection_packaging_within_tolerance"].all()) is True
    assert float(horizon["max_abs_error"].max()) <= 1e-9
