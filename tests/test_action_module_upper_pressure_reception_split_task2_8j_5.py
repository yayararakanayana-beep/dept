from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_5_fixed_map_contract import (
    FixedMapContractConfig,
    build_and_validate_fixed_map_contract,
    validate_fixed_map_contract_tables,
)


def test_task2_8j_5_fixed_map_contract_boundaries():
    fixed_map, evidence, final_summary, errors, summary = build_and_validate_fixed_map_contract()

    assert errors == []
    assert not fixed_map.empty
    assert not evidence.empty
    assert not final_summary.empty
    assert summary["gt_main_component_count"] == 7
    assert summary["gt_main_map_name"] == "static_pca_7"
    assert summary["production_freeze_performed"] is False
    assert summary["canonical_write_performed"] is False

    for table in [fixed_map, evidence, final_summary]:
        assert set(table["contract_created"].astype(bool)) == {True}
        assert set(table["validation_fixed_map_contract"].astype(bool)) == {True}
        for col in [
            "runtime_policy_input",
            "fullspec_runtime_connected",
            "upper_pressure_connected",
            "action_frame_created",
            "actionmodule_called",
            "canonical_write_performed",
            "gk_writeback_performed",
            "ot_writeback_performed",
            "action_weight_converted",
            "production_adoption_performed",
        ]:
            assert set(table[col].astype(bool)) == {False}


def test_task2_8j_5_fixed_map_roles_and_residual_policy():
    fixed_map, evidence, final_summary, _errors, _summary = build_and_validate_fixed_map_contract()

    row = fixed_map.iloc[0]
    assert int(row["gt_main_component_count"]) == 7
    assert str(row["gt_main_map_name"]) == "static_pca_7"
    assert int(row["standard_baseline_component_count"]) == 6
    assert int(row["lightweight_reference_component_count"]) == 3
    assert int(row["extra_reference_component_count"]) == 8
    assert "residual" in str(row["residual_auxiliary_dimension_policy"])
    assert str(row["v2_residual_auxiliary_status"]) == "not_required_for_main_validation"
    assert str(row["v3_residual_auxiliary_status"]) == "recommended_for_pseudo_open_system_residual_audit"

    assert set(evidence["supports_7_axis_fixed_map"].astype(bool)) == {True}
    assert str(final_summary["fixed_map_decision"].iloc[0]).startswith("use_static_pca_7")
    assert bool(final_summary["production_freeze_performed"].iloc[0]) is False


def test_task2_8j_5_validator_detects_wrong_axis_count():
    fixed_map, evidence, final_summary, _errors, _summary = build_and_validate_fixed_map_contract()
    bad = fixed_map.copy()
    bad.loc[bad.index[0], "gt_main_component_count"] = 6

    errors = validate_fixed_map_contract_tables(
        bad,
        evidence,
        final_summary,
        FixedMapContractConfig(gt_main_component_count=7),
    )
    assert "task2_8j_5_wrong_gt_main_component_count" in errors
