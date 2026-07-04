from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_validation_suite_rc1 import (
    TASK2_4_VALIDATION_VERSION,
    build_action_combination_additivity_validation,
    build_pressure_action_validation_report,
    build_single_action_pressure_alignment_validation,
    summarize_pressure_action_validation_report,
    summarize_state_dependence,
    validate_pressure_action_validation_report,
)


def test_task2_4_single_action_pressure_alignment_validation_is_nonempty_and_validation_only():
    alignment = build_single_action_pressure_alignment_validation()

    assert not alignment.empty
    assert set(alignment["task2_4_validation_version"]) == {TASK2_4_VALIDATION_VERSION}
    assert set(alignment["validation_only"]) == {True}
    assert set(alignment["runtime_policy_input"]) == {False}
    assert "pressure_alignment_score" in alignment.columns
    assert alignment["pressure_alignment_score"].ge(0.0).all()


def test_task2_4_state_dependence_summary_classifies_correspondence_variation():
    alignment = build_single_action_pressure_alignment_validation()
    state_summary = summarize_state_dependence(alignment)

    assert not state_summary.empty
    assert set(state_summary["validation_type"]) == {"state_dependence_summary"}
    assert set(state_summary["runtime_policy_input"]) == {False}
    assert set(state_summary["state_dependence_status"]).issubset(
        {
            "approximately_state_independent",
            "state_dependent",
            "weak_or_unresolved_all_states",
        }
    )
    # We want this audit to be informative: at least one row must make a real
    # classification rather than all rows being unresolved.
    assert (
        state_summary["state_dependence_status"] != "weak_or_unresolved_all_states"
    ).any()


def test_task2_4_combination_additivity_detects_additive_or_non_additive_pairs():
    combination = build_action_combination_additivity_validation()

    assert not combination.empty
    assert set(combination["validation_type"]) == {"combination_additivity"}
    assert set(combination["runtime_policy_input"]) == {False}
    assert combination["non_additivity_score"].ge(0.0).all()
    assert set(combination["combination_additivity_status"]).issubset(
        {
            "approximately_additive",
            "side_effect_amplifying",
            "useful_amplifying",
            "mixed_non_additive",
        }
    )
    # At least one intentionally modeled pair should be non-additive so the
    # audit can detect that combination effects are not always simple sums.
    assert (
        combination["combination_additivity_status"] != "approximately_additive"
    ).any()


def test_task2_4_report_contains_all_validation_tables_and_summary():
    report = build_pressure_action_validation_report()
    errors = validate_pressure_action_validation_report(report)
    summary = summarize_pressure_action_validation_report(report)

    assert errors == []
    assert set(report) == {
        "single_action_pressure_alignment",
        "state_dependence_summary",
        "combination_additivity",
        "calibrated_pressure_action_map",
    }
    assert not summary.empty
    assert summary["single_action_alignment_rows"].iloc[0] > 0
    assert summary["state_dependence_rows"].iloc[0] > 0
    assert summary["combination_additivity_rows"].iloc[0] > 0
    assert summary["runtime_policy_input"].iloc[0] is False
