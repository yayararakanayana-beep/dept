from dept2_fullspec_runner_rc1.validation.dept_prediction_full_validation_phase1 import (
    NEUTRAL_BASELINE_METHOD,
    PREDICTION_METHOD,
    PREVIOUS_STEP_BASELINE_METHOD,
    PredictionFullValidationPhase1Config,
    run_prediction_full_validation_phase1,
)


def _small_cfg():
    return PredictionFullValidationPhase1Config(
        seeds=(111, 222),
        profiles=("pseudo_reality_v2_shrinking_equilibrium", "pseudo_reality_v2_trust_collapse"),
        n_entities=8,
        warmup_steps=3,
        source_steps=3,
        max_horizon=3,
    )


def test_full_validation_phase1_outputs_measurement_tables():
    outputs = run_prediction_full_validation_phase1(_small_cfg())
    assert set(outputs) == {
        "prediction_full_validation_phase1_rows",
        "prediction_full_validation_phase1_method_summary",
        "prediction_full_validation_phase1_seed_stability",
        "prediction_full_validation_phase1_baseline_comparison",
        "prediction_full_validation_phase1_horizon_measurement",
        "prediction_full_validation_phase1_boundary",
    }
    for name, table in outputs.items():
        assert table is not None, name
        assert not table.empty, name


def test_full_validation_phase1_covers_methods_profiles_seeds_and_horizons():
    cfg = _small_cfg()
    rows = run_prediction_full_validation_phase1(cfg)["prediction_full_validation_phase1_rows"]
    assert set(rows["method"]) == {
        PREDICTION_METHOD,
        NEUTRAL_BASELINE_METHOD,
        PREVIOUS_STEP_BASELINE_METHOD,
    }
    assert set(rows["seed"]) == set(cfg.seeds)
    assert set(rows["profile"]) == set(cfg.profiles)
    assert set(rows["horizon"]) == {1, 2, 3}
    assert rows["direction_match"].isin([True, False]).all()
    assert rows["strength_abs_error"].ge(0.0).all()


def test_full_validation_phase1_boundary_contract_has_no_v2_leakage():
    outputs = run_prediction_full_validation_phase1(_small_cfg())
    rows = outputs["prediction_full_validation_phase1_rows"]
    boundary = outputs["prediction_full_validation_phase1_boundary"].iloc[0]
    assert bool(rows["forbidden_v2_trace_keys_passed_to_prediction"].any()) is False
    assert bool(boundary["forbidden_v2_trace_keys_passed_to_prediction"]) is False
    assert bool(boundary["boundary_violation_detected"]) is False
    assert boundary["prediction_input_contract"] == "public_trace_history_only"
    assert boundary["v2_future_usage"] == "heldout_answer_key_only"


def test_full_validation_phase1_reports_measurements_not_pass_fail_gates():
    outputs = run_prediction_full_validation_phase1(_small_cfg())
    method_summary = outputs["prediction_full_validation_phase1_method_summary"]
    comparison = outputs["prediction_full_validation_phase1_baseline_comparison"]
    horizon = outputs["prediction_full_validation_phase1_horizon_measurement"]
    assert method_summary["direction_match_rate"].between(0.0, 1.0).all()
    assert method_summary["mean_strength_abs_error"].ge(0.0).all()
    assert method_summary["max_strength_abs_error"].ge(0.0).all()
    assert method_summary["p95_strength_abs_error"].ge(0.0).all()
    assert "direction_match_lift" in comparison.columns
    assert "mean_strength_error_delta_vs_baseline" in comparison.columns
    assert "max_strength_error_delta_vs_baseline" in comparison.columns
    assert "p95_strength_error_delta_vs_baseline" in comparison.columns
    assert "max_strength_abs_error_across_horizons" in horizon.columns
    forbidden_terms = {"pass", "floor", "ceiling", "usable"}
    for table in [method_summary, comparison, horizon]:
        for col in table.columns:
            assert not any(term in col for term in forbidden_terms), col
