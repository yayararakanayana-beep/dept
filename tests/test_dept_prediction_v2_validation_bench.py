from dept2_fullspec_runner_rc1.validation.dept_prediction_v2_validation_bench import (
    HORIZONS,
    V2_PROFILES,
    V2PredictionBenchConfig,
    project_public_trace_from_history,
    run_v2_prediction_validation_bench,
    validate_v2_profile,
)


def test_v2_prediction_bench_outputs_core_tables_and_boundary_passes():
    outputs = run_v2_prediction_validation_bench(
        V2PredictionBenchConfig(seed=303, n_entities=8, warmup_steps=3, source_steps=3, max_horizon=5)
    )
    assert set(outputs) == {
        "v2_prediction_validation_rows",
        "v2_prediction_validation_summary",
        "v2_prediction_validation_boundary",
    }
    assert not outputs["v2_prediction_validation_rows"].empty
    assert not outputs["v2_prediction_validation_summary"].empty
    boundary = outputs["v2_prediction_validation_boundary"].iloc[0]
    assert boundary["prediction_input_contract"] == "public_trace_history_only"
    assert boundary["v2_future_usage"] == "heldout_answer_key_only"
    assert bool(boundary["forbidden_v2_trace_keys_passed_to_prediction"]) is False
    assert bool(boundary["boundary_pass"]) is True


def test_v2_prediction_bench_covers_profiles_and_horizons():
    outputs = run_v2_prediction_validation_bench(
        V2PredictionBenchConfig(seed=304, n_entities=8, warmup_steps=3, source_steps=3, max_horizon=5)
    )
    rows = outputs["v2_prediction_validation_rows"]
    assert set(rows["profile"]) == set(V2_PROFILES)
    assert set(rows["horizon"]) == set(HORIZONS)
    assert set(rows["input_boundary_status"]) == {"public_trace_only"}
    assert rows["predicted_dynamics_direction"].notna().all()
    assert rows["actual_dynamics_direction"].notna().all()
    assert rows["predicted_dynamics_strength"].ge(0.0).all()
    assert rows["actual_dynamics_strength"].ge(0.0).all()


def test_v2_prediction_summary_reports_usable_horizon_metrics():
    outputs = run_v2_prediction_validation_bench(
        V2PredictionBenchConfig(seed=305, n_entities=8, warmup_steps=3, source_steps=3, max_horizon=5)
    )
    summary = outputs["v2_prediction_validation_summary"]
    assert not summary.empty
    assert set(summary["horizon"]) == set(HORIZONS)
    assert summary["direction_match_rate"].between(0.0, 1.0).all()
    assert summary["mean_strength_abs_error"].ge(0.0).all()
    assert "direction_floor_pass" in summary.columns
    assert "strength_error_pass" in summary.columns


def test_v2_profile_validation_uses_heldout_future_not_prediction_input():
    rows = validate_v2_profile(
        "pseudo_reality_v2_shrinking_equilibrium",
        V2PredictionBenchConfig(seed=306, n_entities=8, warmup_steps=3, source_steps=2, max_horizon=3),
    )
    assert not rows.empty
    assert bool(rows["forbidden_v2_trace_keys_passed_to_prediction"].any()) is False
    assert set(rows["input_boundary_status"]) == {"public_trace_only"}


def test_public_projection_advances_time_without_v2_private_trace_inputs():
    rows = validate_v2_profile(
        "pseudo_reality_v2_trust_collapse",
        V2PredictionBenchConfig(seed=307, n_entities=8, warmup_steps=3, source_steps=1, max_horizon=1),
    )
    assert not rows.empty
    assert rows["horizon"].min() == 1
