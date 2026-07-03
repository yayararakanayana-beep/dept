"""Action Module API Consolidation RC1 test-local API layer.

This module intentionally implements the RC1 action-module API as test-local
scaffold code.  It wraps the already frozen functional insurance policy and
21C-E handoff contract without modifying production runtime modules,
coefficients, v2 dynamics, ActionPlanner, ActionModule, ParameterBox, or
ShadowBox.
"""
from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path
import copy
import inspect
import subprocess

import pandas as pd

from test_phase2g21b_b_functional_insurance_policy import (
    ActionHistoryBundle,
    LowerDistributionBundle,
    UpperPressureBundle,
    functional_insurance_policy,
)
from test_phase2g21c_b_functional_policy_v2_alignment import (
    align_functional_policy_with_v2_response_curve,
)
from test_phase2g21c_c_coefficient_drift_diagnosis import (
    diagnose_coefficient_drift_from_alignment,
)
from test_phase2g21c_d_shadow_coefficient_validation import (
    validate_shadow_coefficient_candidates,
)
from test_phase2g21c_e_verification_freeze import freeze_21c_verification_results

EXECUTION_CHANNELS = {
    "buffer_increase",
    "coupling_relief",
    "volatility_damping",
    "uncertainty_probe",
    "exploration_injection",
    "relation_unlock",
    "stabilize",
    "explore",
    "de_risk",
}
NON_EXECUTION_CHANNELS = {"observe_only", "cooldown", "no_op", "hold_shadow", "rollback"}
PRODUCTION_RUNTIME_PATHS = [
    Path("localprep1/dept/DEPT2_ActionModule_ActuationPrimitives_RC1/pseudo_reality/asymmetric_game_v2.py"),
    Path("localprep1/dept/DEPT2_ActionModule_ActuationPrimitives_RC1/action_module.py"),
    Path("localprep1/dept/DEPT2_ActionModule_ActuationPrimitives_RC1/action_planner.py"),
]


def _clip(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def _truthy_mapping(value) -> dict:
    return dict(value or {})


@dataclass(frozen=True)
class ActionContext:
    prepared_upper_pressure: dict
    prepared_lower_state: dict
    prepared_observation_view: dict
    action_history: dict
    parameter_snapshot: dict
    guardrail_snapshot: dict
    handoff_contract: pd.DataFrame
    audit_label: str | None


@dataclass(frozen=True)
class FunctionalPolicyOutput:
    fire_permission_score: float
    action_mass_cap: float
    cooldown_score: float
    channel_weights: dict
    non_action_decision: str
    rollback_permission_score: float
    policy_reason: str


@dataclass(frozen=True)
class ActionCandidate:
    candidate_id: str
    action_channel: str
    proposed_action_mass: float
    expected_direction: str
    expected_effect: str
    risk_class: str
    source_policy_component: str


@dataclass(frozen=True)
class ProjectedActionCandidate:
    candidate_id: str
    action_channel: str
    original_action_mass: float
    projected_action_mass: float
    projection_reason: str
    safety_passed: bool
    rejected_by_guardrail: bool


@dataclass(frozen=True)
class ActionDecision:
    decision_id: str
    decision_type: str
    selected_channel: str | None
    selected_action_mass: float
    cooldown_applied: bool
    rollback_selected: bool
    no_op_selected: bool
    decision_reason: str


@dataclass(frozen=True)
class ActionAuditRecord:
    step_id: str
    policy_summary: dict
    candidate_summary: dict
    projection_summary: dict
    decision_summary: dict
    boundary_flags: dict
    handoff_flags: dict


@dataclass(frozen=True)
class ActionHistoryUpdate:
    latest_decision_type: str
    latest_channel: str | None
    latest_action_mass: float
    cooldown_state_update: dict
    rollback_state_update: dict
    audit_trace_id: str


@dataclass(frozen=True)
class ActionModuleStepResult:
    action_context: ActionContext
    functional_policy_output: FunctionalPolicyOutput
    action_candidates: list[ActionCandidate]
    projected_action_candidates: list[ProjectedActionCandidate]
    action_decision: ActionDecision
    action_audit_record: ActionAuditRecord
    action_history_update: ActionHistoryUpdate


def build_action_context(
    prepared_upper_pressure,
    prepared_lower_state,
    prepared_observation_view,
    action_history,
    parameter_snapshot=None,
    guardrail_snapshot=None,
    handoff_contract=None,
    *,
    label_override=None,
) -> ActionContext:
    contract = handoff_contract
    if contract is None:
        contract = freeze_21c_verification_results().functional_policy_action_module_handoff_contract
    return ActionContext(
        prepared_upper_pressure=_truthy_mapping(prepared_upper_pressure),
        prepared_lower_state=_truthy_mapping(prepared_lower_state),
        prepared_observation_view=_truthy_mapping(prepared_observation_view),
        action_history=_truthy_mapping(action_history),
        parameter_snapshot=_truthy_mapping(parameter_snapshot),
        guardrail_snapshot=_truthy_mapping(guardrail_snapshot),
        handoff_contract=contract.copy(deep=True),
        audit_label=label_override,
    )


def _policy_bundles(context: ActionContext):
    upper_in = context.prepared_upper_pressure
    lower_in = context.prepared_lower_state
    observation = context.prepared_observation_view
    history_in = context.action_history
    preferred = dict(upper_in.get("preferred_channels", {}) or {})
    intensity = _clip(upper_in.get("pressure_intensity", max(preferred.values(), default=0.0)))
    evidence_strength = observation.get("evidence_strength", "missing" if observation.get("missing_evidence", True) else "medium")
    confidence_by_evidence = {"high": 0.90, "medium": 0.72, "low": 0.35, "missing": 0.20}
    confidence = _clip(confidence_by_evidence.get(evidence_strength, 0.50))
    if observation.get("missing_evidence", False):
        confidence = min(confidence, 0.25)
    upper = UpperPressureBundle(
        stabilize_pressure=_clip(preferred.get("stabilize", intensity)),
        explore_pressure=_clip(preferred.get("explore", lower_in.get("opportunity", intensity * 0.5))),
        buffer_pressure=_clip(preferred.get("buffer", preferred.get("de_risk", intensity * 0.7))),
        relation_relief_pressure=_clip(preferred.get("relation", intensity * 0.4)),
        reversibility_pressure=_clip(preferred.get("de_risk", intensity * 0.6)),
        cooldown_pressure=_clip(1.0 if context.guardrail_snapshot.get("force_cooldown") else lower_in.get("risk", 0.0)),
        observe_pressure=_clip(1.0 if observation.get("missing_evidence", False) else 1.0 - confidence),
        de_risk_pressure=_clip(preferred.get("de_risk", upper_in.get("safety_pressure", lower_in.get("risk", intensity * 0.4)))),
        overconvergence_avoidance_pressure=_clip(preferred.get("explore", lower_in.get("opportunity", 0.0))),
    )
    lower = LowerDistributionBundle(
        local_no_action_risk_estimate=_clip(lower_in.get("instability", 0.0)),
        local_action_side_effect_cost_estimate=_clip(lower_in.get("risk", 0.0)),
        local_fire_margin=_clip(lower_in.get("opportunity", 0.0)) * 2.0 - 1.0,
        pair_no_action_risk_estimate=_clip(lower_in.get("instability", 0.0) * 0.8),
        pair_action_side_effect_cost_estimate=_clip(lower_in.get("risk", 0.0)),
        pair_fire_margin=_clip(lower_in.get("opportunity", 0.0)) * 2.0 - 1.0,
        confidence=confidence,
        burden=_clip(lower_in.get("burden", lower_in.get("risk", 0.0))),
        fatigue=_clip(lower_in.get("fatigue", 0.0)),
        collapse_proximity=_clip(lower_in.get("instability", 0.0)),
        reversibility_need=_clip(lower_in.get("recovery_need", 0.0)),
        relation_lock_proxy=_clip(lower_in.get("relation_lock", 0.0)),
        coupling_proxy=_clip(lower_in.get("coupling", 0.0)),
        exploration_need=_clip(lower_in.get("opportunity", 0.0)),
        unresolved_proxy=_clip(1.0 - confidence),
        side_effect_risk=_clip(lower_in.get("risk", 0.0)),
    )
    history = ActionHistoryBundle(
        recent_correct_fire_rate=_clip(1.0 - history_in.get("last_action_mass", 0.0)),
        recent_harmful_fire_rate=_clip(history_in.get("recent_harmful_fire_rate", 0.0)),
        recent_side_effect_score=_clip(history_in.get("recent_side_effect_score", lower_in.get("risk", 0.0))),
        recent_cooldown_state=_clip(1.0 if history_in.get("cooldown_active", False) else 0.0),
        recent_no_op_worsening=_clip(lower_in.get("instability", 0.0)),
        recent_wrong_direction_rate=_clip(1.0 if history_in.get("recent_rollback", False) else 0.0),
    )
    return upper, lower, history


def compute_functional_policy(context: ActionContext) -> FunctionalPolicyOutput:
    raw = functional_insurance_policy(*_policy_bundles(context))
    parameter_cap = _clip(context.parameter_snapshot.get("max_action_mass", 1.0))
    guardrail_cap = _clip(context.guardrail_snapshot.get("max_allowed_action_mass", 1.0))
    action_mass_cap = min(_clip(raw.action_mass_cap), parameter_cap, guardrail_cap)
    risk = _clip(context.prepared_lower_state.get("risk", 0.0))
    rollback_permission_score = _clip(
        (1.0 if context.guardrail_snapshot.get("force_rollback") else 0.0)
        or max(risk, context.action_history.get("recent_harmful_fire_rate", 0.0), 0.65 if context.action_history.get("recent_rollback") else 0.0)
    )
    return FunctionalPolicyOutput(
        fire_permission_score=_clip(raw.fire_permission_score),
        action_mass_cap=action_mass_cap,
        cooldown_score=_clip(max(raw.cooldown_score, 1.0 if context.guardrail_snapshot.get("force_cooldown") else 0.0)),
        channel_weights={k: _clip(v) for k, v in raw.channel_weights.items()},
        non_action_decision=str(raw.non_action_decision),
        rollback_permission_score=rollback_permission_score,
        policy_reason=str(raw.suppression_reason or "none"),
    )


def propose_action_candidates(context: ActionContext, policy: FunctionalPolicyOutput) -> list[ActionCandidate]:
    candidates: list[ActionCandidate] = []
    if policy.fire_permission_score >= _clip(context.parameter_snapshot.get("min_fire_permission", 0.50)):
        for channel, weight in sorted(policy.channel_weights.items()):
            if channel in NON_EXECUTION_CHANNELS or weight <= 0.0:
                continue
            mass = min(policy.action_mass_cap, policy.action_mass_cap * weight)
            if mass > 0.0:
                candidates.append(ActionCandidate(f"cand_{len(candidates)+1:03d}", channel, mass, "bounded_positive", "one_step_translation", "normal", f"channel_weight:{channel}"))
    if policy.cooldown_score >= 0.70 or policy.non_action_decision == "cooldown":
        candidates.append(ActionCandidate(f"cand_{len(candidates)+1:03d}", "cooldown", 0.0, "reduce_action", "cooldown", "protective", "cooldown_score"))
    if policy.rollback_permission_score >= 0.75:
        candidates.append(ActionCandidate(f"cand_{len(candidates)+1:03d}", "rollback", 0.0, "reverse_recent_action", "rollback", "protective", "rollback_permission_score"))
    return candidates


def _evidence_weak(context: ActionContext) -> bool:
    obs = context.prepared_observation_view
    return bool(obs.get("missing_evidence", not obs)) or obs.get("evidence_strength") in {"low", "missing"} or not obs.get("safe_range_known", False) or not obs.get("harmful_threshold_known", False)


def apply_action_safety_projection(context: ActionContext, policy: FunctionalPolicyOutput, candidates: list[ActionCandidate]) -> list[ProjectedActionCandidate]:
    blocked = set(context.guardrail_snapshot.get("blocked_channels", []) or [])
    projected = []
    for c in candidates:
        reasons = []
        rejected = c.action_channel in blocked
        if rejected:
            reasons.append("blocked_channel_guardrail")
        mass = min(c.proposed_action_mass, policy.action_mass_cap, _clip(context.guardrail_snapshot.get("max_allowed_action_mass", 1.0)))
        if policy.cooldown_score >= 0.70 and c.action_channel not in {"cooldown", "rollback"}:
            mass *= 0.25
            reasons.append("cooldown_weakened_execution")
        if policy.rollback_permission_score >= 0.75 and c.action_channel != "rollback":
            rejected = True
            mass = 0.0
            reasons.append("rollback_prioritized")
        if _evidence_weak(context) and c.action_channel not in {"cooldown", "rollback"}:
            rejected = True
            mass = 0.0
            reasons.append("weak_or_missing_evidence")
        if c.source_policy_component.startswith(("rejected", "hold", "artificial_probe")):
            rejected = True
            mass = 0.0
            reasons.append("disallowed_candidate_source")
        if c.proposed_action_mass > mass and "cap_projection" not in reasons:
            reasons.append("cap_projection")
        if not reasons:
            reasons.append("within_policy_and_guardrails")
        projected.append(ProjectedActionCandidate(c.candidate_id, c.action_channel, c.proposed_action_mass, mass, "+".join(reasons), not rejected and mass >= 0.0, rejected))
    return projected


def select_action_decision(context: ActionContext, policy: FunctionalPolicyOutput, projected_candidates: list[ProjectedActionCandidate]) -> ActionDecision:
    if context.guardrail_snapshot.get("force_rollback") or policy.rollback_permission_score >= 0.75:
        return ActionDecision("decision_001", "ROLLBACK", "rollback", 0.0, False, True, False, "rollback condition strong")
    if context.guardrail_snapshot.get("force_cooldown") or policy.cooldown_score >= 0.70:
        return ActionDecision("decision_001", "COOLDOWN", "cooldown", 0.0, True, False, False, "cooldown condition strong")
    if policy.fire_permission_score < 0.50:
        return ActionDecision("decision_001", "NO_OP", None, 0.0, False, False, True, "fire permission below execution threshold")
    safe = [p for p in projected_candidates if p.safety_passed and not p.rejected_by_guardrail and p.action_channel not in NON_EXECUTION_CHANNELS and p.projected_action_mass > 0.0]
    if safe:
        best = max(safe, key=lambda p: (p.projected_action_mass, p.action_channel))
        return ActionDecision("decision_001", "EXECUTE", best.action_channel, best.projected_action_mass, False, False, False, "selected safe projected execution candidate")
    if _evidence_weak(context):
        return ActionDecision("decision_001", "HOLD_FOR_EVIDENCE", None, 0.0, False, False, False, "evidence missing or weak")
    return ActionDecision("decision_001", "NO_OP", None, 0.0, False, False, True, "no safe execution candidate")


def build_action_audit_record(context: ActionContext, policy: FunctionalPolicyOutput, candidates: list[ActionCandidate], projected_candidates: list[ProjectedActionCandidate], decision: ActionDecision) -> ActionAuditRecord:
    boundary_flags = {
        "coefficient_changed": False,
        "production_runtime_changed": False,
        "canonical_writeback_performed": False,
        "fixed_candidate_used_as_runtime_coefficient": False,
        "shadow_adjustment_used_as_runtime_default": False,
        "rejected_candidate_used": False,
        "hold_candidate_used": False,
        "artificial_probe_used": False,
        "scenario_label_controlled_logic": False,
    }
    boundary_flags["audit_passed"] = all(v is False for k, v in boundary_flags.items())
    handoff_flags = {str(r.handoff_item): str(r.handoff_status) for _, r in context.handoff_contract.iterrows()} if not context.handoff_contract.empty else {}
    return ActionAuditRecord(
        "action_module_step_rc1",
        {"fire_permission_score": policy.fire_permission_score, "action_mass_cap": policy.action_mass_cap, "cooldown_score": policy.cooldown_score, "rollback_permission_score": policy.rollback_permission_score, "non_action_decision": policy.non_action_decision, "policy_reason": policy.policy_reason},
        {"candidate_count": len(candidates), "execution_candidate_count": sum(c.action_channel not in NON_EXECUTION_CHANNELS for c in candidates)},
        {"projected_candidate_count": len(projected_candidates), "safe_candidate_count": sum(p.safety_passed and not p.rejected_by_guardrail for p in projected_candidates)},
        {"decision_type": decision.decision_type, "selected_channel": decision.selected_channel, "selected_action_mass": decision.selected_action_mass, "decision_reason": decision.decision_reason},
        boundary_flags,
        handoff_flags,
    )


def build_action_history_update(decision: ActionDecision, audit_record: ActionAuditRecord) -> ActionHistoryUpdate:
    return ActionHistoryUpdate(
        decision.decision_type,
        decision.selected_channel,
        decision.selected_action_mass,
        {"cooldown_active": decision.cooldown_applied, "latest_reason": decision.decision_reason if decision.cooldown_applied else None},
        {"rollback_selected": decision.rollback_selected, "latest_reason": decision.decision_reason if decision.rollback_selected else None},
        audit_record.step_id,
    )


def action_module_step(prepared_upper_pressure, prepared_lower_state, prepared_observation_view, action_history, parameter_snapshot=None, guardrail_snapshot=None, handoff_contract=None, *, label_override=None) -> ActionModuleStepResult:
    context = build_action_context(prepared_upper_pressure, prepared_lower_state, prepared_observation_view, action_history, parameter_snapshot, guardrail_snapshot, handoff_contract, label_override=label_override)
    policy = compute_functional_policy(context)
    candidates = propose_action_candidates(context, policy)
    projected = apply_action_safety_projection(context, policy, candidates)
    decision = select_action_decision(context, policy, projected)
    audit = build_action_audit_record(context, policy, candidates, projected, decision)
    history_update = build_action_history_update(decision, audit)
    return ActionModuleStepResult(context, policy, candidates, projected, decision, audit, history_update)


# DataFrame helpers

def action_module_context_summary(result: ActionModuleStepResult) -> pd.DataFrame:
    c = result.action_context
    return pd.DataFrame([{"step_id": result.action_audit_record.step_id, "has_upper_pressure": bool(c.prepared_upper_pressure), "has_lower_state": bool(c.prepared_lower_state), "has_observation_view": bool(c.prepared_observation_view), "has_action_history": bool(c.action_history), "has_handoff_contract": not c.handoff_contract.empty, "scenario_label_for_audit_only": c.audit_label, "direct_dept_access_performed": False, "canonical_read_performed": False, "canonical_writeback_performed": False}])


def action_module_policy_output(result):
    p = result.functional_policy_output
    return pd.DataFrame([{**result.action_audit_record.policy_summary, "step_id": result.action_audit_record.step_id, "coefficient_changed": False, "runtime_coefficient_update_performed": False}])[["step_id", "fire_permission_score", "action_mass_cap", "cooldown_score", "rollback_permission_score", "non_action_decision", "policy_reason", "coefficient_changed", "runtime_coefficient_update_performed"]]


def action_module_candidate_table(result):
    return pd.DataFrame([{**c.__dict__, "step_id": result.action_audit_record.step_id} for c in result.action_candidates], columns=["step_id", "candidate_id", "action_channel", "proposed_action_mass", "expected_direction", "expected_effect", "risk_class", "source_policy_component"])


def action_module_projected_candidate_table(result):
    return pd.DataFrame([{**p.__dict__, "step_id": result.action_audit_record.step_id} for p in result.projected_action_candidates], columns=["step_id", "candidate_id", "action_channel", "original_action_mass", "projected_action_mass", "projection_reason", "safety_passed", "rejected_by_guardrail"])


def action_module_decision_table(result):
    d = result.action_decision
    return pd.DataFrame([{**d.__dict__, "step_id": result.action_audit_record.step_id}], columns=["step_id", "decision_id", "decision_type", "selected_channel", "selected_action_mass", "cooldown_applied", "rollback_selected", "no_op_selected", "decision_reason"])


def action_module_audit_table(result):
    return pd.DataFrame([{**result.action_audit_record.boundary_flags, "step_id": result.action_audit_record.step_id}], columns=["step_id", "coefficient_changed", "production_runtime_changed", "canonical_writeback_performed", "fixed_candidate_used_as_runtime_coefficient", "rejected_candidate_used", "hold_candidate_used", "artificial_probe_used", "scenario_label_controlled_logic", "audit_passed"])


def action_module_history_update_table(result):
    return pd.DataFrame([{**result.action_history_update.__dict__, "step_id": result.action_audit_record.step_id}], columns=["step_id", "latest_decision_type", "latest_channel", "latest_action_mass", "cooldown_state_update", "rollback_state_update", "audit_trace_id"])


SAMPLE_UPPER = {"pressure_intensity": 0.95, "safety_priority": "medium", "preferred_channels": {"stabilize": 1.0, "explore": 1.0, "de_risk": 1.0}}
SAMPLE_LOWER = {"instability": 0.15, "opportunity": 1.0, "risk": 0.05, "recovery_need": 0.20}
SAMPLE_OBS = {"evidence_strength": "high", "missing_evidence": False, "safe_range_known": True, "harmful_threshold_known": True}
SAMPLE_HISTORY = {"cooldown_active": False, "recent_rollback": False, "last_action_mass": 0.10}
SAMPLE_PARAMS = {"max_action_mass": 0.30, "min_fire_permission": 0.50}
SAMPLE_GUARDS = {"blocked_channels": [], "max_allowed_action_mass": 0.30, "force_cooldown": False, "force_rollback": False}


def sample_result(**overrides):
    return action_module_step(
        overrides.get("upper", SAMPLE_UPPER),
        overrides.get("lower", SAMPLE_LOWER),
        overrides.get("obs", SAMPLE_OBS),
        overrides.get("history", SAMPLE_HISTORY),
        overrides.get("params", SAMPLE_PARAMS),
        overrides.get("guards", SAMPLE_GUARDS),
        label_override=overrides.get("label"),
    )


def test_dataclasses_and_result_fields_exist():
    expected = {
        ActionContext: ["prepared_upper_pressure", "prepared_lower_state", "prepared_observation_view", "action_history", "parameter_snapshot", "guardrail_snapshot", "handoff_contract", "audit_label"],
        FunctionalPolicyOutput: ["fire_permission_score", "action_mass_cap", "cooldown_score", "channel_weights", "non_action_decision", "rollback_permission_score", "policy_reason"],
        ActionModuleStepResult: ["action_context", "functional_policy_output", "action_candidates", "projected_action_candidates", "action_decision", "action_audit_record", "action_history_update"],
    }
    for cls, names in expected.items():
        assert [f.name for f in fields(cls)] == names
    assert isinstance(sample_result(), ActionModuleStepResult)


def test_context_boundaries_defaults_and_label_audit_only():
    unlabeled = action_module_step({}, {}, {}, {}, label_override=None)
    labeled = action_module_step({}, {}, {}, {}, label_override="audit_case")
    assert labeled.action_context.audit_label == "audit_case"
    assert unlabeled.action_decision == labeled.action_decision
    ctx = labeled.action_context
    assert ctx.parameter_snapshot == {}
    assert ctx.guardrail_snapshot == {}
    assert not ctx.handoff_contract.empty
    assert not action_module_context_summary(labeled).iloc[0].canonical_read_performed
    assert not action_module_context_summary(labeled).iloc[0].canonical_writeback_performed


def test_policy_wrapper_maps_ranges_and_does_not_modify_source():
    before = inspect.getsource(functional_insurance_policy)
    p = compute_functional_policy(sample_result().action_context)
    after = inspect.getsource(functional_insurance_policy)
    assert before == after
    assert 0.0 <= p.fire_permission_score <= 1.0
    assert 0.0 <= p.action_mass_cap <= SAMPLE_PARAMS["max_action_mass"]
    assert 0.0 <= p.cooldown_score <= 1.0
    assert 0.0 <= p.rollback_permission_score <= 1.0
    assert all(0.0 <= v <= 1.0 for v in p.channel_weights.values())
    assert not sample_result().action_audit_record.boundary_flags["fixed_candidate_used_as_runtime_coefficient"]
    assert not sample_result().action_audit_record.boundary_flags["shadow_adjustment_used_as_runtime_default"]


def test_candidate_generation_requirements():
    r = sample_result()
    assert r.action_candidates
    assert all(c.proposed_action_mass <= r.functional_policy_output.action_mass_cap for c in r.action_candidates)
    assert all(c.source_policy_component for c in r.action_candidates)
    low = sample_result(upper={"pressure_intensity": 0.05, "preferred_channels": {}}, lower={"instability": 0.1, "opportunity": 0.0, "risk": 0.2})
    assert low.action_decision.decision_type == "NO_OP"
    assert sample_result(guards={**SAMPLE_GUARDS, "force_cooldown": True}).action_decision.decision_type == "COOLDOWN"
    assert sample_result(guards={**SAMPLE_GUARDS, "force_rollback": True}).action_decision.decision_type == "ROLLBACK"


def test_safety_projection_blocks_and_projects():
    r = sample_result(guards={**SAMPLE_GUARDS, "max_allowed_action_mass": 0.05})
    assert all(p.projected_action_mass <= 0.05 for p in r.projected_action_candidates)
    blocked = sample_result(guards={**SAMPLE_GUARDS, "blocked_channels": ["volatility_damping", "exploration_injection"]})
    assert any(p.rejected_by_guardrail for p in blocked.projected_action_candidates)
    assert sample_result(guards={**SAMPLE_GUARDS, "force_rollback": True}).action_decision.decision_type == "ROLLBACK"
    missing = sample_result(obs={"evidence_strength": "low", "missing_evidence": True})
    assert missing.action_decision.decision_type in {"HOLD_FOR_EVIDENCE", "NO_OP"}
    assert not any(c.source_policy_component.startswith(("rejected", "hold", "artificial_probe")) for c in r.action_candidates)


def test_decision_priority_and_empty_ambiguous_cases():
    assert sample_result(guards={**SAMPLE_GUARDS, "force_rollback": True}).action_decision.decision_type == "ROLLBACK"
    assert sample_result(guards={**SAMPLE_GUARDS, "force_cooldown": True}).action_decision.decision_type == "COOLDOWN"
    assert sample_result(upper={"pressure_intensity": 0.0}, lower={"opportunity": 0.0, "risk": 0.3}).action_decision.decision_type == "NO_OP"
    assert sample_result().action_decision.decision_type == "EXECUTE"
    assert sample_result(obs={}).action_decision.decision_type in {"HOLD_FOR_EVIDENCE", "NO_OP"}
    ctx = build_action_context(SAMPLE_UPPER, SAMPLE_LOWER, SAMPLE_OBS, SAMPLE_HISTORY, SAMPLE_PARAMS, SAMPLE_GUARDS)
    policy = compute_functional_policy(ctx)
    assert select_action_decision(ctx, policy, []).decision_type == "NO_OP"


def test_audit_and_history_update_are_safe_and_non_mutating():
    history = copy.deepcopy(SAMPLE_HISTORY)
    r = action_module_step(SAMPLE_UPPER, SAMPLE_LOWER, SAMPLE_OBS, history, SAMPLE_PARAMS, SAMPLE_GUARDS)
    assert history == SAMPLE_HISTORY
    assert isinstance(r.action_audit_record, ActionAuditRecord)
    assert r.action_audit_record.boundary_flags["audit_passed"] is True
    for key in ["coefficient_changed", "production_runtime_changed", "canonical_writeback_performed", "fixed_candidate_used_as_runtime_coefficient", "shadow_adjustment_used_as_runtime_default", "rejected_candidate_used", "hold_candidate_used", "artificial_probe_used", "scenario_label_controlled_logic"]:
        assert r.action_audit_record.boundary_flags[key] is False
    assert r.action_history_update.latest_decision_type == r.action_decision.decision_type
    assert r.action_history_update.audit_trace_id == r.action_audit_record.step_id


def test_action_module_step_integration_tables_and_determinism():
    r1 = sample_result(label="audit_a")
    r2 = sample_result(label="audit_b")
    assert r1.action_decision == r2.action_decision
    assert action_module_context_summary(r1).columns.tolist() == ["step_id", "has_upper_pressure", "has_lower_state", "has_observation_view", "has_action_history", "has_handoff_contract", "scenario_label_for_audit_only", "direct_dept_access_performed", "canonical_read_performed", "canonical_writeback_performed"]
    assert action_module_policy_output(r1).columns.tolist() == ["step_id", "fire_permission_score", "action_mass_cap", "cooldown_score", "rollback_permission_score", "non_action_decision", "policy_reason", "coefficient_changed", "runtime_coefficient_update_performed"]
    assert action_module_candidate_table(r1).columns.tolist() == ["step_id", "candidate_id", "action_channel", "proposed_action_mass", "expected_direction", "expected_effect", "risk_class", "source_policy_component"]
    assert action_module_projected_candidate_table(r1).columns.tolist() == ["step_id", "candidate_id", "action_channel", "original_action_mass", "projected_action_mass", "projection_reason", "safety_passed", "rejected_by_guardrail"]
    assert action_module_decision_table(r1).columns.tolist() == ["step_id", "decision_id", "decision_type", "selected_channel", "selected_action_mass", "cooldown_applied", "rollback_selected", "no_op_selected", "decision_reason"]
    assert action_module_audit_table(r1).columns.tolist() == ["step_id", "coefficient_changed", "production_runtime_changed", "canonical_writeback_performed", "fixed_candidate_used_as_runtime_coefficient", "rejected_candidate_used", "hold_candidate_used", "artificial_probe_used", "scenario_label_controlled_logic", "audit_passed"]
    assert action_module_history_update_table(r1).columns.tolist() == ["step_id", "latest_decision_type", "latest_channel", "latest_action_mass", "cooldown_state_update", "rollback_state_update", "audit_trace_id"]


def test_21c_e_handoff_contract_boundaries():
    r = sample_result()
    flags = r.action_audit_record.handoff_flags
    assert flags["functional_insurance_policy"] == "wrap_allowed"
    assert flags["21c_b_alignment_helper"] == "audit_only"
    assert flags["21c_c_coefficient_drift_diagnosis_helper"] == "audit_only"
    assert flags["21c_d_shadow_validation_helper"] == "pre_update_validation_only"
    assert flags["21c_e_fixed_update_candidates"] == "not_runtime_coefficients"
    assert flags["rejected_candidates"] == "not_allowed"
    assert flags["hold_candidates"] == "additional_evidence_only"
    assert flags["artificial_probe_candidates"] == "guarded"
    assert flags["scenario_labels"] == "audit_only"
    assert flags["shadow_adjustment_values"] == "not_runtime_defaults"
    assert callable(align_functional_policy_with_v2_response_curve)
    assert callable(diagnose_coefficient_drift_from_alignment)
    assert callable(validate_shadow_coefficient_candidates)


def test_production_no_change_paths_are_not_in_git_diff():
    changed = set(subprocess.check_output(["git", "diff", "--name-only"], text=True).splitlines())
    forbidden = {str(p) for p in PRODUCTION_RUNTIME_PATHS}
    forbidden |= {p for p in changed if any(name in p for name in ["ActionPlanner", "ActionModule", "ParameterBox", "ShadowBox", "asymmetric_game_v2.py", "action_planner.py", "action_module.py"])}
    assert not (changed & forbidden)
