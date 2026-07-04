from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_5d_pressure_mix_validation import (
    PRESSURE_MIX_SPECS,
    TASK2_5D_VERSION,
    build_and_validate_pressure_mix_validation_table,
    build_pressure_mix_validation_table,
    validate_pressure_mix_validation_table,
)


def test_task2_5d_pressure_mix_table_contract():
    table, errors = build_and_validate_pressure_mix_validation_table()

    assert errors == []
    assert not table.empty
    assert set(table["task2_5d_version"]) == {TASK2_5D_VERSION}
    assert set(table["validation_type"]) == {"mixed_pressure_input_validation"}
    assert set(table["validation_only"]) == {True}
    assert set(table["runtime_policy_input"]) == {False}
    assert set(table["validation_projection_only"]) == {True}
    assert set(table["pressure_to_action_converter_created"]) == {False}
    assert set(table["final_action_decision"]) == {False}
    assert set(table["action_frame_created"]) == {False}
    assert set(table["actionmodule_called"]) == {False}
    assert set(table["new_semantic_translation_layer_added"]) == {False}
    assert set(table["diagnostic_compat_policy_used"]) == {False}
    assert set(table["repaired_diagnostic_policy_used"]) == {False}


def test_task2_5d_contains_all_fixed_pressure_mixes_and_state_bands():
    table = build_pressure_mix_validation_table()

    expected_mix_ids = {spec.pressure_mix_id for spec in PRESSURE_MIX_SPECS}
    assert expected_mix_ids.issubset(set(table["pressure_mix_id"]))
    assert set(table["scenario_or_state_band"]) == {"stable", "medium", "high", "limit"}
    assert table["candidate_action_count"].gt(0).all()
    assert table["candidate_action_set_ja"].astype(str).str.contains("作用").any()


def test_task2_5d_risky_exploration_commitment_mix_surfaces_unsafe_interaction():
    table = build_pressure_mix_validation_table()
    risky = table[
        (table["pressure_mix_id"] == "exploration_up__commitment_down")
        & (table["scenario_or_state_band"].isin(["high", "limit"]))
    ]

    assert not risky.empty
    assert risky["unsafe_combination_score"].gt(0.0).any()
    assert risky["requires_task2_5e_strength_review"].any()
    assert risky["recommended_candidate_filtering"].astype(str).str.len().gt(0).all()


def test_task2_5d_safe_mix_preserves_coverage_and_safety_candidates():
    table = build_pressure_mix_validation_table()
    safe = table[table["pressure_mix_id"] == "commitment_up__pressure_cap_down"]

    assert not safe.empty
    assert safe["intended_pressure_coverage"].ge(0.5).all()
    assert safe["candidate_action_set"].astype(str).str.contains("buffer_increase|volatility_damping").any()


def test_task2_5d_validator_detects_runtime_input_mislabel():
    table = build_pressure_mix_validation_table()
    table.loc[table.index[0], "runtime_policy_input"] = True

    errors = validate_pressure_mix_validation_table(table)
    assert "task2_5d_forbidden_true_field:runtime_policy_input" in errors
