from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8f_high_risk_crash_cost_sandbox import (
    HORIZON,
    build_and_validate_high_risk_crash_cost_sandbox_table,
    build_high_risk_crash_cost_sandbox_table,
    summarize_high_risk_crash_cost_sandbox,
    validate_high_risk_crash_cost_sandbox,
)


def test_task2_8f_contract_and_boundaries():
    table, errors, summary = build_and_validate_high_risk_crash_cost_sandbox_table()

    assert errors == []
    assert not table.empty
    assert set(table["validation_only"]) == {True}
    assert set(table["runtime_policy_input"]) == {False}
    assert set(table["action_frame_created"]) == {False}
    assert set(table["actionmodule_called"]) == {False}
    assert set(table["world_runtime_called"]) == {False}
    assert set(table["canonical_write_performed"]) == {False}
    assert set(table["upper_pressure_connected"]) == {False}
    assert set(table["exploration_escape_connected"]) == {False}
    assert set(table["synthetic_dynamics_only"]) == {True}
    assert set(table["high_risk_tail_loss_enabled"]) == {True}
    assert set(table["side_effect_decomposed"]) == {True}
    assert summary["rows"] == len(table)


def test_task2_8f_has_no_op_crash_cost_and_four_dynamics():
    table = build_high_risk_crash_cost_sandbox_table()
    no_op = table[table["strategy"].astype(str) == "no_op"]

    assert set(table["horizon"].astype(int)) == {HORIZON}
    assert table["risk_dynamics_type"].nunique() >= 4
    assert not no_op.empty
    assert no_op["crash_cost_auc"].gt(0.0).any()
    assert no_op["irreversibility_auc"].gt(0.0).any()


def test_task2_8f_finds_positive_tail_insurance_condition():
    table, errors, summary = build_and_validate_high_risk_crash_cost_sandbox_table()
    positive = table[table["positive_tail_insurance_condition"].astype(bool)]

    assert errors == []
    assert not positive.empty
    assert positive["action_matches_dynamics"].astype(bool).all()
    assert positive["crash_cost_delta_vs_no_op"].gt(0.0).all()
    assert positive["risk_auc_delta_vs_no_op"].gt(0.0).all()
    assert summary["positive_tail_insurance_rows"] == len(positive)


def test_task2_8f_side_effects_are_decomposed():
    table = build_high_risk_crash_cost_sandbox_table()
    side_sum = (
        table["short_gain_loss_auc"]
        + table["liquidity_loss_auc"]
        + table["overcooling_loss_auc"]
        + table["mismatch_cost_auc"]
        + table["complexity_cost_auc"]
    )

    assert (side_sum - table["side_effect_auc"]).abs().le(1e-9).all()
    assert table["short_gain_loss_auc"].ge(0.0).all()
    assert table["liquidity_loss_auc"].ge(0.0).all()
    assert table["overcooling_loss_auc"].ge(0.0).all()
    assert table["mismatch_cost_auc"].ge(0.0).all()
    assert table["complexity_cost_auc"].ge(0.0).all()


def test_task2_8f_mismatch_does_not_count_as_positive():
    table = build_high_risk_crash_cost_sandbox_table()
    mismatch = table[table["strategy"].astype(str) == "mismatched_single"]

    assert not mismatch.empty
    assert not mismatch["positive_tail_insurance_condition"].astype(bool).any()


def test_task2_8f_summary_exposes_best_positive_condition():
    table = build_high_risk_crash_cost_sandbox_table()
    summary = summarize_high_risk_crash_cost_sandbox(table)

    assert summary["horizon"] == HORIZON
    assert summary["positive_tail_insurance_rows"] > 0
    assert summary["best_positive_dynamics"] != "none"
    assert summary["best_positive_strategy"] in {
        "matched_single",
        "matched_composite_pair",
        "matched_composite_all",
        "excessive_overlong_matched",
        "late_composite",
    }
    assert summary["best_positive_actions"] != "none"


def test_task2_8f_validator_detects_exploration_escape_mislabel():
    table = build_high_risk_crash_cost_sandbox_table()
    table.loc[table.index[0], "exploration_escape_connected"] = True

    errors = validate_high_risk_crash_cost_sandbox(table)
    assert "task2_8f_forbidden_true:exploration_escape_connected" in errors
