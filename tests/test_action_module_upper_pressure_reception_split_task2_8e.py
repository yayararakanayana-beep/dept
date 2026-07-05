from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8e_arbitrary_risk_dynamics_sandbox import (
    HORIZON,
    build_and_validate_arbitrary_risk_dynamics_sandbox_table,
    build_arbitrary_risk_dynamics_sandbox_table,
    summarize_arbitrary_risk_dynamics_sandbox,
    validate_arbitrary_risk_dynamics_sandbox,
)


def test_task2_8e_contract_and_boundaries():
    table, errors, summary = build_and_validate_arbitrary_risk_dynamics_sandbox_table()

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
    assert set(table["terrain_coefficients_explicit"]) == {True}
    assert summary["rows"] == len(table)


def test_task2_8e_contains_no_op_comparison_and_four_dynamics():
    table = build_arbitrary_risk_dynamics_sandbox_table()

    assert (table["strategy"].astype(str) == "no_op").any()
    assert table["risk_dynamics_type"].nunique() >= 4
    assert set(table["horizon"].astype(int)) == {HORIZON}
    assert table["risk_peak_delta_vs_no_op"].notna().all()
    assert table["risk_auc_delta_vs_no_op"].notna().all()


def test_task2_8e_finds_positive_matched_conditions_vs_no_op():
    table, errors, summary = build_and_validate_arbitrary_risk_dynamics_sandbox_table()
    positive = table[table["positive_net_vs_no_op"].astype(bool)]

    assert errors == []
    assert not positive.empty
    assert positive["action_matches_dynamics"].astype(bool).all()
    assert positive["risk_auc_delta_vs_no_op"].gt(0.0).all()
    assert positive["post_action_auc_delta_vs_no_op"].gt(0.0).all()
    assert summary["positive_net_rows"] == len(positive)


def test_task2_8e_mismatched_actions_do_not_count_as_positive():
    table = build_arbitrary_risk_dynamics_sandbox_table()
    mismatch = table[table["strategy"].astype(str) == "mismatched_action"]

    assert not mismatch.empty
    assert not mismatch["positive_net_vs_no_op"].astype(bool).any()


def test_task2_8e_summary_exposes_best_positive_condition():
    table = build_arbitrary_risk_dynamics_sandbox_table()
    summary = summarize_arbitrary_risk_dynamics_sandbox(table)

    assert summary["horizon"] == HORIZON
    assert summary["positive_net_rows"] > 0
    assert summary["best_positive_dynamics"] != "none"
    assert summary["best_positive_strategy"] in {"matched_action", "late_matched_action", "excessive_overlong_matched"}
    assert summary["best_positive_action"] != "none"


def test_task2_8e_validator_detects_upper_pressure_mislabel():
    table = build_arbitrary_risk_dynamics_sandbox_table()
    table.loc[table.index[0], "upper_pressure_connected"] = True

    errors = validate_arbitrary_risk_dynamics_sandbox(table)
    assert "task2_8e_forbidden_true:upper_pressure_connected" in errors
