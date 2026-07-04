import pandas as pd

from dept2_fullspec_runner_rc1.modules.action_policies.pressure_intent_to_action_candidate_adapter import (
    TASK2_3_ADAPTER_PROFILE,
    PressureIntentToActionCandidateAdapter,
    build_and_validate_pressure_intent_action_candidates,
    build_basic_action_correspondence_map,
    validate_pressure_intent_action_candidates,
)


def _sample_pressure_intents() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "seed": 7,
            "scenario": "normal",
            "t": 3,
            "generator": "task2_3_test",
            "phase_bin": "test",
            "h11_dimension": "Exploration",
            "pressure_component": "exploration_frequency",
            "component_direction": "increase",
            "component_signed_value": 0.42,
            "component_magnitude": 0.42,
            "h11_received_signed_pressure": 0.25,
            "h11_received_abs_pressure": 0.25,
            "control_domain": "exploration_scheduler",
            "semantic_effect": "exploration_attempt_frequency_up",
            "intent_family": "exploration_attempt",
            "suggested_control_route": "increase_trials",
            "compression_allowed_before_action_planner": False,
        },
        {
            "seed": 7,
            "scenario": "normal",
            "t": 3,
            "generator": "task2_3_test",
            "phase_bin": "test",
            "h11_dimension": "Safety",
            "pressure_component": "rollback_sensitivity",
            "component_direction": "increase",
            "component_signed_value": 0.36,
            "component_magnitude": 0.36,
            "h11_received_signed_pressure": 0.20,
            "h11_received_abs_pressure": 0.20,
            "control_domain": "rollback_guard",
            "semantic_effect": "rollback_guard_up",
            "intent_family": "safety_guard",
            "suggested_control_route": "prepare_reversal",
            "compression_allowed_before_action_planner": False,
        },
    ])


def test_task2_3_basic_action_correspondence_map_is_state_independent_candidate_input():
    basic_map = build_basic_action_correspondence_map()

    assert not basic_map.empty
    assert set(basic_map["runtime_policy_input"]) == {False}
    assert set(basic_map["basic_action_correspondence_only"]) == {True}
    assert "scenario_or_state_band" not in basic_map.columns
    grouped = basic_map.groupby(
        ["pressure_component", "component_direction", "semantic_effect"],
        dropna=False,
    )["action_correspondence_share"].sum()
    assert ((grouped - 1.0).abs() <= 1e-9).all()


def test_task2_3_adapter_builds_candidate_only_rows_from_pressure_intents():
    candidates, errors = build_and_validate_pressure_intent_action_candidates(_sample_pressure_intents())

    assert errors == []
    assert not candidates.empty
    assert set(candidates["action_policy_profile"]) == {TASK2_3_ADAPTER_PROFILE}
    assert set(candidates["candidate_only"]) == {True}
    assert set(candidates["final_action_decision"]) == {False}
    assert set(candidates["state_timing_evaluation_performed"]) == {False}
    assert set(candidates["state_dependent_effect_evaluation_performed"]) == {False}
    assert set(candidates["safety_decision_performed"]) == {False}
    assert set(candidates["actionmodule_called_by_adapter"]) == {False}
    assert set(candidates["pseudo_pressure_used"]) == {False}
    assert set(candidates["diagnostic_only"]) == {False}
    assert set(candidates["diagnostic_compat_policy_used"]) == {False}
    assert set(candidates["repaired_diagnostic_policy_used"]) == {False}
    assert set(candidates["upper_pressure_reception_policy_used"]) == {True}
    assert candidates["action_strength"].between(0.0, 0.030).all()


def test_task2_3_adapter_preserves_pressure_intent_meanings():
    pressure_intents = _sample_pressure_intents()
    candidates = PressureIntentToActionCandidateAdapter().build_action_candidates(pressure_intents)

    assert set(pressure_intents["pressure_component"]).issubset(set(candidates["pressure_component"]))
    assert set(pressure_intents["semantic_effect"]).issubset(set(candidates["semantic_effect"]))
    assert set(pressure_intents["intent_family"]).issubset(set(candidates["intent_family"]))
    assert set(pressure_intents["suggested_control_route"]).issubset(set(candidates["suggested_control_route"]))
    assert set(candidates["basic_action_correspondence_only"]) == {True}


def test_task2_3_validator_detects_final_action_mislabel():
    candidates = PressureIntentToActionCandidateAdapter().build_action_candidates(_sample_pressure_intents())
    broken = candidates.copy()
    broken.loc[broken.index[0], "final_action_decision"] = True

    errors = validate_pressure_intent_action_candidates(broken)

    assert "pressure_intent_action_candidates_claim_final_action_decision" in errors
