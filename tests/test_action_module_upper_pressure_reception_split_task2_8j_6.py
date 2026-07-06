from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_1_candidate_feature_log import (
    CandidateFeatureLogConfig,
)
from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_6_macro_game_relation_field_validation import (
    MacroGameRelationFieldConfig,
    build_and_validate_macro_game_relation_field,
    validate_macro_game_relation_field_tables,
)


def test_task2_8j_6_macro_game_relation_field_boundaries():
    feature_cfg = CandidateFeatureLogConfig(steps=18, seeds=(501, 502), window_sizes=(1, 6, 12))
    signal_table, state_table, relation_field, final_summary, errors, summary = build_and_validate_macro_game_relation_field(
        feature_cfg,
        MacroGameRelationFieldConfig(),
    )

    assert errors == []
    assert not signal_table.empty
    assert not state_table.empty
    assert not relation_field.empty
    assert not final_summary.empty
    assert summary["gt_main_map_name"] == "static_pca_7"
    assert summary["gt_main_component_count"] == 7

    for table in [signal_table, state_table, relation_field, final_summary]:
        assert set(table["validation_only"].astype(bool)) == {True}
        assert set(table["incomplete_observation_assumption"].astype(bool)) == {True}
        assert set(table["gt_main_map_name"].astype(str)) == {"static_pca_7"}
        assert set(table["gt_main_component_count"].astype(int)) == {7}
        for col in [
            "runtime_policy_input",
            "fullspec_runtime_connected",
            "upper_pressure_connected",
            "action_frame_created",
            "actionmodule_called",
            "canonical_write_performed",
            "gk_writeback_performed",
            "ot_writeback_performed",
            "effective_dimension_refit_performed",
            "axis_mutation_performed",
            "residual_auxiliary_injected_into_gt_main",
            "dynamics_axis_extracted_for_action",
            "action_weight_converted",
            "hidden_truth_input",
            "future_information_used",
        ]:
            assert set(table[col].astype(bool)) == {False}


def test_task2_8j_6_core_macro_signals_and_relation_field():
    feature_cfg = CandidateFeatureLogConfig(steps=18, seeds=(501, 502), window_sizes=(1, 6, 12))
    signal_table, state_table, relation_field, final_summary, _errors, summary = build_and_validate_macro_game_relation_field(
        feature_cfg,
        MacroGameRelationFieldConfig(),
    )

    signals = set(signal_table["macro_signal"].astype(str))
    assert {"relation_lock", "coordination_lag", "information_degradation", "resource_pressure"}.issubset(signals)
    assert signal_table["extraction_confidence"].astype(float).between(0.0, 1.0).all()
    assert relation_field["relation_strength"].astype(float).between(0.0, 1.0).all()
    assert "coordination_lag" in set(relation_field["source_macro_signal"].astype(str)) | set(relation_field["target_macro_signal"].astype(str))
    assert int(final_summary["macro_signal_count"].iloc[0]) >= 4
    assert int(final_summary["relation_edge_count"].iloc[0]) > 0
    assert "macro_game_relation_field" in str(final_summary["relation_field_decision"].iloc[0])
    assert "macro_game_relation_field" in summary["relation_field_decision"]


def test_task2_8j_6_validator_detects_axis_refit():
    feature_cfg = CandidateFeatureLogConfig(steps=18, seeds=(501, 502), window_sizes=(1, 6, 12))
    signal_table, state_table, relation_field, final_summary, _errors, _summary = build_and_validate_macro_game_relation_field(
        feature_cfg,
        MacroGameRelationFieldConfig(),
    )
    bad = signal_table.copy()
    bad.loc[bad.index[0], "effective_dimension_refit_performed"] = True

    errors = validate_macro_game_relation_field_tables(bad, state_table, relation_field, final_summary)
    assert "task2_8j_6_forbidden_true:signal_table:effective_dimension_refit_performed" in errors
