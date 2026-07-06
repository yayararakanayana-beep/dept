from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_6c_v2_structure_change_relation_field_tracking import (
    V2StructureChangeTrackingConfig,
)
from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_11_game_structure_prediction_envelope_dry_run import (
    GameStructurePredictionEnvelopeDryRunConfig,
    build_and_validate_game_structure_prediction_envelope_dry_run,
    validate_game_structure_prediction_envelope_dry_run_tables,
)


def _small_tracking_cfg():
    return V2StructureChangeTrackingConfig(steps=18, seeds=(501, 502), window_sizes=(1, 6, 12))


def _small_prediction_cfg():
    return GameStructurePredictionEnvelopeDryRunConfig(max_relation_envelopes=4)


def test_task2_8j_11_prediction_envelope_boundaries():
    envelopes, source_trace, checks, final_summary, errors, summary = (
        build_and_validate_game_structure_prediction_envelope_dry_run(_small_tracking_cfg(), cfg=_small_prediction_cfg())
    )

    assert errors == []
    assert not envelopes.empty
    assert not source_trace.empty
    assert not checks.empty
    assert not final_summary.empty
    assert summary["gt_main_map_name"] == "static_pca_7"
    assert summary["gt_main_component_count"] == 7
    assert summary["real_prediction_model_executed"] is False
    assert summary["action_effect_prediction_generated"] is False
    assert summary["action_axis_generated"] is False
    assert summary["upper_pressure_generated_here"] is False
    assert summary["real_actionmodule_called"] is False

    for table in [envelopes, source_trace, checks, final_summary]:
        assert set(table["validation_only"].astype(bool)) == {True}
        assert set(table["dry_run_only"].astype(bool)) == {True}
        assert set(table["prediction_envelope_dry_run_only"].astype(bool)) == {True}
        assert set(table["prediction_envelope_created"].astype(bool)) == {True}
        assert set(table["source_trace_preserved"].astype(bool)) == {True}
        assert set(table["game_structure_prediction_route_separate"].astype(bool)) == {True}
        assert set(table["observation_forecast_allowed"].astype(bool)) == {True}
        assert set(table["real_prediction_model_executed"].astype(bool)) == {False}
        assert set(table["action_effect_prediction_generated"].astype(bool)) == {False}
        assert set(table["action_axis_generated"].astype(bool)) == {False}
        assert set(table["action_candidate_generated"].astype(bool)) == {False}
        assert set(table["upper_pressure_generated_here"].astype(bool)) == {False}
        assert set(table["real_actionmodule_called"].astype(bool)) == {False}
        assert set(table["gt_main_map_name"].astype(str)) == {"static_pca_7"}
        assert set(table["gt_main_component_count"].astype(int)) == {7}


def test_task2_8j_11_envelopes_have_required_payload_and_traces():
    envelopes, source_trace, checks, final_summary, _errors, summary = (
        build_and_validate_game_structure_prediction_envelope_dry_run(_small_tracking_cfg(), cfg=_small_prediction_cfg())
    )

    required_columns = {
        "prediction_bundle_id",
        "source_observation_ids",
        "source_relation_trace_ids",
        "prediction_horizon",
        "predicted_state_tendency",
        "predicted_relation_tendency",
        "confidence",
        "uncertainty",
        "validity_scope",
        "assumption_current_structure_continues",
        "provenance",
        "audit_level",
        "audit_reasons",
    }
    assert required_columns.issubset(set(envelopes.columns))
    assert set(envelopes["required_payload_fields_present"].astype(bool)) == {True}
    assert set(envelopes["forbidden_payload_fields_absent"].astype(bool)) == {True}
    assert set(envelopes["is_contract_stub"].astype(bool)) == {True}
    assert set(source_trace["trace_status"].astype(str)) == {"source_traces_preserved"}
    assert set(checks["check_status"].astype(str)) == {"pass"}
    assert int(final_summary["prediction_envelope_count"].iloc[0]) == len(envelopes)
    assert int(final_summary["prediction_trace_count"].iloc[0]) == len(source_trace)
    assert int(final_summary["source_trace_preserved_count"].iloc[0]) == len(source_trace)
    assert "traceable_observation_side_forecast_packaging" in summary["game_structure_prediction_envelope_dry_run_decision"]


def test_task2_8j_11_validator_detects_action_effect_prediction():
    envelopes, source_trace, checks, final_summary, _errors, _summary = (
        build_and_validate_game_structure_prediction_envelope_dry_run(_small_tracking_cfg(), cfg=_small_prediction_cfg())
    )
    bad = envelopes.copy()
    bad.loc[bad.index[0], "action_effect_prediction_generated"] = True
    errors = validate_game_structure_prediction_envelope_dry_run_tables(bad, source_trace, checks, final_summary)
    assert "task2_8j_11_forbidden_true:envelopes:action_effect_prediction_generated" in errors
