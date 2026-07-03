"""Phase 2G-20C capped insurance-hybrid action policy contract tests.

Specification-only: this test file freezes the policy contract for the later
Phase 2G-20D real-v2 comparison.  It intentionally does not import or modify
production ActionModule, ActionPlanner, pseudo-reality v2, DEPT G/K/O_t,
ParameterBox, ShadowBox, or observation-window runtime code.
"""
from __future__ import annotations

STATE_BANDS = ("stable", "medium", "high", "limit")
CHANNELS = {
    "no_op",
    "uncertainty_probe",
    "buffer_increase",
    "volatility_damping",
    "coupling_relief",
    "exploration_injection",
    "relation_unlock",
}

ACTION_MASS_CAP = {
    "stable": 0.03,
    "medium": 0.08,
    "high": 0.14,
    "limit": 0.16,
}

POLICY = {
    "stable": {
        "default_action": "no_op",
        "primary_allowed": {"no_op"},
        "secondary_allowed": {"uncertainty_probe"},
        "insurance_allowed": set(),
        "exploration_allowed_by_default": False,
        "relation_unlock_allowed_by_default": False,
        "max_primary_actions": 1,
        "max_secondary_actions": 1,
        "max_probe_strength": 0.025,
    },
    "medium": {
        "default_action": "weak_support_when_risk_exceeds_cost",
        "primary_allowed": {"no_op", "buffer_increase", "uncertainty_probe", "coupling_relief"},
        "secondary_allowed": {"uncertainty_probe", "exploration_injection"},
        "insurance_allowed": {"buffer_increase", "coupling_relief"},
        "exploration_allowed_by_default": False,
        "exploration_allowed_from_projection": True,
        "relation_unlock_allowed_by_default": False,
        "max_primary_actions": 1,
        "max_secondary_actions": 1,
        "max_probe_strength": 0.04,
    },
    "high": {
        "default_action": "defensive_insurance",
        "primary_allowed": {"no_op", "buffer_increase", "volatility_damping", "coupling_relief"},
        "secondary_allowed": set(),
        "insurance_allowed": {"buffer_increase", "volatility_damping", "coupling_relief"},
        "exploration_allowed_by_default": False,
        "exploration_allowed_from_projection": False,
        "relation_unlock_allowed_by_default": False,
        "max_primary_actions": 1,
        "max_secondary_actions": 0,
    },
    "limit": {
        "default_action": "collapse_prevention_only",
        "primary_allowed": {"no_op", "buffer_increase", "volatility_damping"},
        "secondary_allowed": set(),
        "insurance_allowed": {"buffer_increase", "volatility_damping"},
        "exploration_allowed_by_default": False,
        "exploration_allowed_from_projection": False,
        "relation_unlock_allowed_by_default": False,
        "max_primary_actions": 1,
        "max_secondary_actions": 0,
    },
}

EXPLORATION_REQUIREMENTS = {
    "allowed_state_bands": {"stable", "medium"},
    "allowed_projection_tiers": {"strong_candidate", "weak_candidate", "probe_only"},
    "allowed_permissions": {"action_allowed", "probe_only"},
    "execution_decision_owner": "action_module",
    "requires_verified_source": True,
    "requires_local_audit_passed": True,
    "requires_v8_pass": True,
    "requires_max_start_strength_cap": True,
    "requires_side_effect_budget": True,
    "requires_cooldown_clear": True,
}

SIDE_EFFECT_STOP_CONDITIONS = {
    "fatigue_delta_increase",
    "hidden_burden_increase",
    "hidden_damage_delta_increase",
    "resource_inequality_delta_worsens",
    "reversibility_delta_fails_to_improve_when_targeted",
    "exploration_delta_below_expectation_when_targeted",
    "action_cost_effect_exceeds_budget",
    "risk_band_worsens_to_high_or_limit_after_exploration",
    "cooldown_violation",
    "missing_projection_verification",
    "missing_v8_or_local_audit_support",
    "benefit_or_growth_hides_hidden_burden",
}

RUNTIME_BOUNDARY = {
    "production_actionmodule_modified_in_20c": False,
    "production_actionplanner_modified_in_20c": False,
    "v2_dynamics_modified_in_20c": False,
    "actionmodule_reads_gk_ot_directly": False,
    "actionmodule_reads_parameter_box_directly": False,
    "actionmodule_writes_parameter_box": False,
    "actionmodule_writes_world_gk_ot": False,
    "v2_trace_used_as_runtime_input": False,
    "observation_windows_used_as_actionmodule_runtime_input": False,
    "bridge_creates_actionframe": False,
    "bridge_calls_actionmodule": False,
    "full_sidecar_direct_actionmodule_input": False,
}

COMPOSITE_RULE = {
    "benefit_offsets_hidden_burden_automatically": False,
    "growth_offsets_hidden_burden_automatically": False,
    "keep_benefit_growth_risk_burden_cost_separate": True,
}


def _exploration_candidate_eligible(candidate: dict, state_band: str) -> bool:
    """Contract helper for the future 20D policy implementation.

    This helper is deliberately test-local.  It does not claim that production
    ActionModule currently implements the policy.
    """
    if state_band not in EXPLORATION_REQUIREMENTS["allowed_state_bands"]:
        return False
    if candidate.get("projection_tier") not in EXPLORATION_REQUIREMENTS["allowed_projection_tiers"]:
        return False
    if candidate.get("candidate_use_permission") not in EXPLORATION_REQUIREMENTS["allowed_permissions"]:
        return False
    if candidate.get("execution_decision_owner") != EXPLORATION_REQUIREMENTS["execution_decision_owner"]:
        return False
    if not bool(candidate.get("projection_source_verified", False)):
        return False
    if not bool(candidate.get("projection_source_local_audit_passed", False)):
        return False
    if candidate.get("projection_source_v8_status") != "pass":
        return False
    if bool(candidate.get("cooldown_active", False)):
        return False
    if float(candidate.get("requested_strength", 0.0)) > float(candidate.get("max_start_strength", 0.0)):
        return False
    if float(candidate.get("projected_side_effect", 0.0)) > float(candidate.get("side_effect_budget", 0.0)):
        return False
    return True


def test_state_band_action_mass_caps_are_explicit_and_ordered():
    assert set(ACTION_MASS_CAP) == set(STATE_BANDS)
    assert ACTION_MASS_CAP["stable"] == 0.03
    assert ACTION_MASS_CAP["medium"] == 0.08
    assert ACTION_MASS_CAP["high"] == 0.14
    assert ACTION_MASS_CAP["limit"] == 0.16
    assert ACTION_MASS_CAP["stable"] < ACTION_MASS_CAP["medium"] < ACTION_MASS_CAP["limit"]


def test_stable_defaults_to_no_op_and_blocks_routine_action():
    stable = POLICY["stable"]
    assert stable["default_action"] == "no_op"
    assert stable["primary_allowed"] == {"no_op"}
    assert stable["secondary_allowed"] == {"uncertainty_probe"}
    assert not stable["exploration_allowed_by_default"]
    assert "exploration_injection" not in stable["primary_allowed"]
    assert "relation_unlock" not in stable["primary_allowed"]
    assert "buffer_increase" not in stable["primary_allowed"]
    assert "volatility_damping" not in stable["primary_allowed"]


def test_medium_allows_weak_support_but_not_default_exploration():
    medium = POLICY["medium"]
    assert {"buffer_increase", "uncertainty_probe", "coupling_relief"}.issubset(medium["primary_allowed"])
    assert medium["exploration_allowed_from_projection"] is True
    assert medium["exploration_allowed_by_default"] is False
    assert "exploration_injection" in medium["secondary_allowed"]
    assert "relation_unlock" not in medium["primary_allowed"]
    assert medium["max_probe_strength"] <= 0.04


def test_high_prioritizes_insurance_and_blocks_exploration():
    high = POLICY["high"]
    assert high["default_action"] == "defensive_insurance"
    assert {"buffer_increase", "volatility_damping", "coupling_relief"}.issubset(high["insurance_allowed"])
    assert high["exploration_allowed_from_projection"] is False
    assert "exploration_injection" not in high["primary_allowed"]
    assert "relation_unlock" not in high["primary_allowed"]
    assert high["max_secondary_actions"] == 0


def test_limit_is_collapse_prevention_only():
    limit = POLICY["limit"]
    assert limit["default_action"] == "collapse_prevention_only"
    assert limit["primary_allowed"] == {"no_op", "buffer_increase", "volatility_damping"}
    assert "exploration_injection" not in limit["primary_allowed"]
    assert "relation_unlock" not in limit["primary_allowed"]
    assert "coupling_relief" not in limit["primary_allowed"]
    assert "uncertainty_probe" not in limit["primary_allowed"]


def test_one_step_shape_is_one_primary_plus_optional_very_weak_probe():
    for band, policy in POLICY.items():
        assert policy["max_primary_actions"] == 1
        assert policy["max_secondary_actions"] in {0, 1}
        if band in {"high", "limit"}:
            assert policy["max_secondary_actions"] == 0


def test_exploration_requires_20ab_projection_contract_and_small_start():
    candidate = {
        "projection_tier": "weak_candidate",
        "candidate_use_permission": "probe_only",
        "execution_decision_owner": "action_module",
        "projection_source_verified": True,
        "projection_source_local_audit_passed": True,
        "projection_source_v8_status": "pass",
        "cooldown_active": False,
        "requested_strength": 0.025,
        "max_start_strength": 0.04,
        "projected_side_effect": 0.012,
        "side_effect_budget": 0.02,
    }
    assert _exploration_candidate_eligible(candidate, "medium")
    assert _exploration_candidate_eligible(candidate, "stable")
    assert not _exploration_candidate_eligible(candidate, "high")
    assert not _exploration_candidate_eligible(candidate, "limit")

    too_strong = dict(candidate, requested_strength=0.08)
    assert not _exploration_candidate_eligible(too_strong, "medium")

    wrong_owner = dict(candidate, execution_decision_owner="exploration_bridge")
    assert not _exploration_candidate_eligible(wrong_owner, "medium")

    cooldown = dict(candidate, cooldown_active=True)
    assert not _exploration_candidate_eligible(cooldown, "medium")

    over_budget = dict(candidate, projected_side_effect=0.05)
    assert not _exploration_candidate_eligible(over_budget, "medium")


def test_exploration_does_not_allow_unverified_or_blocked_projection():
    base = {
        "projection_tier": "strong_candidate",
        "candidate_use_permission": "action_allowed",
        "execution_decision_owner": "action_module",
        "projection_source_verified": True,
        "projection_source_local_audit_passed": True,
        "projection_source_v8_status": "pass",
        "cooldown_active": False,
        "requested_strength": 0.03,
        "max_start_strength": 0.04,
        "projected_side_effect": 0.01,
        "side_effect_budget": 0.02,
    }
    assert _exploration_candidate_eligible(base, "medium")
    assert not _exploration_candidate_eligible(dict(base, projection_tier="blocked"), "medium")
    assert not _exploration_candidate_eligible(dict(base, candidate_use_permission="blocked"), "medium")
    assert not _exploration_candidate_eligible(dict(base, projection_source_verified=False), "medium")
    assert not _exploration_candidate_eligible(dict(base, projection_source_local_audit_passed=False), "medium")
    assert not _exploration_candidate_eligible(dict(base, projection_source_v8_status="fail"), "medium")


def test_side_effect_stop_conditions_are_explicit_and_strict_for_exploration():
    expected = {
        "fatigue_delta_increase",
        "hidden_burden_increase",
        "hidden_damage_delta_increase",
        "resource_inequality_delta_worsens",
        "reversibility_delta_fails_to_improve_when_targeted",
        "exploration_delta_below_expectation_when_targeted",
        "action_cost_effect_exceeds_budget",
        "risk_band_worsens_to_high_or_limit_after_exploration",
        "cooldown_violation",
        "benefit_or_growth_hides_hidden_burden",
    }
    assert expected.issubset(SIDE_EFFECT_STOP_CONDITIONS)


def test_benefit_and_growth_do_not_hide_hidden_burden_or_cost():
    assert COMPOSITE_RULE["benefit_offsets_hidden_burden_automatically"] is False
    assert COMPOSITE_RULE["growth_offsets_hidden_burden_automatically"] is False
    assert COMPOSITE_RULE["keep_benefit_growth_risk_burden_cost_separate"] is True


def test_runtime_boundary_for_20c_spec_is_no_production_rewire():
    assert RUNTIME_BOUNDARY["production_actionmodule_modified_in_20c"] is False
    assert RUNTIME_BOUNDARY["production_actionplanner_modified_in_20c"] is False
    assert RUNTIME_BOUNDARY["v2_dynamics_modified_in_20c"] is False
    assert RUNTIME_BOUNDARY["actionmodule_reads_gk_ot_directly"] is False
    assert RUNTIME_BOUNDARY["actionmodule_reads_parameter_box_directly"] is False
    assert RUNTIME_BOUNDARY["actionmodule_writes_parameter_box"] is False
    assert RUNTIME_BOUNDARY["actionmodule_writes_world_gk_ot"] is False
    assert RUNTIME_BOUNDARY["v2_trace_used_as_runtime_input"] is False
    assert RUNTIME_BOUNDARY["observation_windows_used_as_actionmodule_runtime_input"] is False
    assert RUNTIME_BOUNDARY["bridge_creates_actionframe"] is False
    assert RUNTIME_BOUNDARY["bridge_calls_actionmodule"] is False
    assert RUNTIME_BOUNDARY["full_sidecar_direct_actionmodule_input"] is False


def test_policy_covers_every_known_channel_without_silent_default_control():
    covered = set()
    for policy in POLICY.values():
        covered |= policy["primary_allowed"]
        covered |= policy["secondary_allowed"]
        covered |= policy["insurance_allowed"]
    assert covered.issubset(CHANNELS)
    assert "relation_unlock" not in covered
    assert "exploration_injection" in covered  # only as medium secondary via approved projection.
    assert "no_op" in covered
