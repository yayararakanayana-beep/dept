from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_5b_gt_information_ingestion_contract import (
    GTInformationIngestionContractConfig,
    build_and_validate_gt_information_ingestion_contract,
    validate_gt_information_ingestion_contract_tables,
)


def test_task2_8j_5b_contract_boundaries_and_incomplete_observation():
    allowed, forbidden, granularity, residual, final_summary, errors, summary = build_and_validate_gt_information_ingestion_contract()

    assert errors == []
    assert not allowed.empty
    assert not forbidden.empty
    assert not granularity.empty
    assert not residual.empty
    assert not final_summary.empty
    assert summary["gt_main_map_name"] == "static_pca_7"
    assert summary["gt_main_component_count"] == 7
    assert summary["incomplete_observation_assumption"] is True
    assert summary["ai_translation_implemented"] is False
    assert summary["raw_data_ingestion_implemented"] is False
    assert summary["axis_mutation_performed"] is False

    for table in [allowed, forbidden, granularity, residual, final_summary]:
        assert set(table["contract_created"].astype(bool)) == {True}
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
            "ai_translation_implemented",
            "raw_data_ingestion_implemented",
            "axis_refit_performed",
            "axis_mutation_performed",
            "residual_auxiliary_injected_into_gt_main",
            "action_weight_converted",
        ]:
            assert set(table[col].astype(bool)) == {False}


def test_task2_8j_5b_allowed_groups_match_game_structure_granularity():
    allowed, forbidden, granularity, residual, final_summary, _errors, _summary = build_and_validate_gt_information_ingestion_contract()

    assert set(allowed["information_group"].astype(str)) == {
        "relation_structure",
        "coordination_behavior",
        "resource_pressure",
        "information_quality",
        "action_tendency",
        "effect_and_side_effect_proxy",
        "history_change",
    }
    assert allowed["required_for_game_structure_extraction"].astype(bool).all()
    assert "hidden_truth" in set(forbidden["forbidden_input_type"].astype(str))
    assert "future_information" in set(forbidden["forbidden_input_type"].astype(str))
    assert "full_raw_logs" in set(forbidden["forbidden_input_type"].astype(str))
    assert "unbounded_ai_interpretation" in set(forbidden["forbidden_input_type"].astype(str))
    assert len(granularity) == 9
    assert set(granularity["time_scale"].astype(str)) == {"short", "mid", "long"}
    assert set(granularity["scope"].astype(str)) == {"local", "relation", "global"}
    assert "O_t_residual" in ";".join(residual["v3_status"].astype(str))
    assert str(final_summary["ingestion_decision"].iloc[0]) == "use_observable_coarse_grained_game_structure_information_for_static_pca_7_gt"


def test_task2_8j_5b_validator_detects_axis_mutation():
    allowed, forbidden, granularity, residual, final_summary, _errors, _summary = build_and_validate_gt_information_ingestion_contract()
    bad = allowed.copy()
    bad.loc[bad.index[0], "axis_mutation_performed"] = True

    errors = validate_gt_information_ingestion_contract_tables(
        bad,
        forbidden,
        granularity,
        residual,
        final_summary,
        GTInformationIngestionContractConfig(),
    )
    assert "task2_8j_5b_forbidden_true:allowed:axis_mutation_performed" in errors
