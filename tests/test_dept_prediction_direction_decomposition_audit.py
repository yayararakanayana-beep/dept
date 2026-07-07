from dept2_fullspec_runner_rc1.validation.dept_prediction_direction_decomposition_audit import (
    PredictionDirectionDecompositionAuditConfig,
    run_prediction_direction_decomposition_audit,
)


def _small_cfg():
    return PredictionDirectionDecompositionAuditConfig(
        seeds=(11, 22),
        patterns=("neutral", "overconvergence", "fixation", "divergence"),
        noise_levels=(0.0, 0.04),
        horizons=(1, 2, 3),
        history_steps=5,
        source_steps=3,
    )


def test_direction_decomposition_outputs_tables():
    outputs = run_prediction_direction_decomposition_audit(_small_cfg())
    assert set(outputs) == {
        "prediction_direction_decomposition_rows",
        "prediction_direction_decomposition_group_summary",
        "prediction_direction_decomposition_confusion",
        "prediction_direction_decomposition_component_summary",
        "prediction_direction_decomposition_boundary",
    }
    assert all(table is not None and not table.empty for table in outputs.values())


def test_direction_decomposition_rows_include_core_measurements():
    rows = run_prediction_direction_decomposition_audit(_small_cfg())["prediction_direction_decomposition_rows"]
    assert set(rows["actual_direction"]) == {"neutral", "overconvergence", "fixation", "divergence"}
    for col in [
        "predicted_overconvergence_strength",
        "predicted_fixation_strength",
        "predicted_divergence_strength",
        "predicted_direction_margin",
        "neutral_buffer_distance_measure",
        "shrink_equilibrium_measure",
        "bias_concentration_measure",
        "divergence_release_measure",
        "entity_relation_lock_delta_per_step",
        "relation_relation_rigidity_delta_per_step",
        "relation_flow_delta_per_step",
        "entity_exploration_delta_per_step",
        "entity_uncertainty_delta_per_step",
        "entity_volatility_delta_per_step",
    ]:
        assert col in rows.columns, col
        assert rows[col].notna().all(), col


def test_direction_decomposition_reports_confusion_and_components():
    outputs = run_prediction_direction_decomposition_audit(_small_cfg())
    confusion = outputs["prediction_direction_decomposition_confusion"]
    component = outputs["prediction_direction_decomposition_component_summary"]
    boundary = outputs["prediction_direction_decomposition_boundary"].iloc[0]
    assert "actual_direction" in confusion.columns
    assert "predicted_direction" in confusion.columns
    assert "mean_divergence_release_measure" in component.columns
    assert "mean_shrink_equilibrium_measure" in component.columns
    assert bool(boundary["boundary_violation_detected"]) is False
