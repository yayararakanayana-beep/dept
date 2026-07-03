"""Phase 2G-21C-E verification freeze and fixed candidate revalidation.

Test-local freeze layer only: consumes 21C-D shadow validation outputs,
converts accepted shadow candidates into limited proposal candidates, revalidates
those proposals as fixed update candidates or blocked candidates, and emits the
handoff contract for Action Module API Consolidation. It never writes
coefficients, production runtime, v2 dynamics, ParameterBox, ShadowBox, or
canonical state.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import inspect
import subprocess
import sys

import pandas as pd

TESTS_ROOT = Path(__file__).resolve().parent
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))

from test_phase2g21b_b_functional_insurance_policy import functional_insurance_policy  # noqa: E402
from test_phase2g21c_b_functional_policy_v2_alignment import (  # noqa: E402
    align_functional_policy_with_v2_response_curve,
)
from test_phase2g21c_c_coefficient_drift_diagnosis import (  # noqa: E402
    diagnose_coefficient_drift_from_alignment,
)
from test_phase2g21c_d_shadow_coefficient_validation import (  # noqa: E402
    validate_shadow_coefficient_candidates,
)

FREEZE_SUMMARY_COLUMNS = ["phase_id", "source_phase_range", "baseline_alignment_case_count", "diagnosis_candidate_count", "shadow_candidate_count", "accepted_shadow_candidate_count", "rejected_candidate_count", "hold_candidate_count", "update_proposal_count", "fixed_update_candidate_count", "blocked_update_candidate_count", "safety_regression_rejected_count", "no_improvement_rejected_count", "over_correction_rejected_count", "mixed_evidence_hold_count", "missing_input_hold_count", "final_freeze_judgement", "coefficient_changed", "production_runtime_changed", "canonical_writeback_performed"]
PROPOSAL_COLUMNS = ["proposal_id", "source_candidate_id", "suspected_coefficient_family", "proposed_adjustment_direction", "proposed_adjustment_strength", "proposal_confidence", "safety_priority", "expected_benefit", "known_risk", "artificial_probe_flag", "requires_additional_validation", "coefficient_changed", "production_runtime_changed", "canonical_writeback_performed"]
FIXED_COLUMNS = ["fixed_candidate_id", "source_proposal_id", "source_candidate_id", "suspected_coefficient_family", "proposed_adjustment_direction", "proposed_adjustment_strength", "revalidation_passed", "safety_revalidation_passed", "opportunity_revalidation_passed", "non_target_regression_check_passed", "artificial_probe_guard_passed", "missing_evidence_guard_passed", "fixed_candidate_status", "coefficient_changed", "production_runtime_changed", "canonical_writeback_performed"]
REJECTED_COLUMNS = ["source_candidate_id", "candidate_decision", "suspected_coefficient_family", "shadow_adjustment_type", "shadow_adjustment_strength", "rejection_reason", "safety_regression_count", "opportunity_regression_count", "non_target_regression_count", "can_be_reconsidered_later", "required_condition_for_reconsideration"]
HOLD_COLUMNS = ["source_candidate_id", "candidate_decision", "suspected_coefficient_family", "shadow_adjustment_type", "shadow_adjustment_strength", "hold_reason", "missing_or_mixed_evidence_type", "required_additional_evidence", "recommended_next_action"]
HANDOFF_COLUMNS = ["handoff_item", "handoff_status", "source_phase", "description", "allowed_in_action_module_api", "requires_runtime_change", "requires_coefficient_change", "notes"]
PRODUCTION_RUNTIME_PATHS = [
    Path("localprep1/dept/DEPT2_ActionModule_ActuationPrimitives_RC1/pseudo_reality/asymmetric_game_v2.py"),
    Path("localprep1/dept/DEPT2_ActionModule_ActuationPrimitives_RC1/action_module.py"),
    Path("localprep1/dept/DEPT2_ActionModule_ActuationPrimitives_RC1/action_planner.py"),
]


@dataclass(frozen=True)
class VerificationFreezeResult:
    functional_policy_21c_freeze_summary: pd.DataFrame
    functional_policy_accepted_update_proposals: pd.DataFrame
    functional_policy_fixed_update_candidate_register: pd.DataFrame
    functional_policy_rejected_candidate_register: pd.DataFrame
    functional_policy_hold_candidate_register: pd.DataFrame
    functional_policy_action_module_handoff_contract: pd.DataFrame


def _empty(columns):
    return pd.DataFrame(columns=columns)


def _is_artificial_probe_like(row) -> bool:
    return str(row.shadow_adjustment_type) == "increase_or_relax" and str(getattr(row, "evidence_strength", "low")) != "high"


def _make_proposals(summary, decisions):
    merged = summary.merge(decisions, on=["candidate_id", "candidate_decision", "suspected_coefficient_family", "shadow_adjustment_type", "shadow_adjustment_strength"], how="left")
    rows = []
    for _, r in merged.iterrows():
        artificial = _is_artificial_probe_like(r)
        ok = (
            r.candidate_decision == "accepted_shadow_candidate"
            and r.recommended_21c_e_action == "propose_limited_coefficient_update"
            and int(r.safety_regression_count) == 0
            and float(r.overall_alignment_score_delta_mean) > 0
            and float(r.primary_misalignment_resolution_rate) > 0
            and not bool(r.coefficient_changed)
            and not bool(r.production_runtime_changed)
            and not bool(r.canonical_writeback_performed)
            and not artificial
            and str(r.evidence_strength) != "low"
        )
        if ok:
            rows.append({"proposal_id": f"21c_e_prop_{len(rows)+1:03d}", "source_candidate_id": r.candidate_id, "suspected_coefficient_family": r.suspected_coefficient_family, "proposed_adjustment_direction": r.shadow_adjustment_type, "proposed_adjustment_strength": r.shadow_adjustment_strength, "proposal_confidence": r.evidence_strength, "safety_priority": r.safety_priority, "expected_benefit": r.expected_benefit, "known_risk": r.known_risk, "artificial_probe_flag": False, "requires_additional_validation": True, "coefficient_changed": False, "production_runtime_changed": False, "canonical_writeback_performed": False})
    return pd.DataFrame(rows, columns=PROPOSAL_COLUMNS)


def _fixed_status(p, s):
    safety = int(s.safety_regression_count) == 0
    opp = int(s.opportunity_regression_count) == 0
    non_target = int(s.non_target_regression_count) == 0
    artificial_ok = not bool(p.artificial_probe_flag)
    missing_ok = p.proposal_confidence != "low"
    gain = float(s.overall_alignment_score_delta_mean) > 0 and float(s.primary_misalignment_resolution_rate) > 0 and int(s.improved_case_count) > 0
    if not safety: return "blocked_by_safety_revalidation", safety, opp, non_target, artificial_ok, missing_ok, False
    if not opp: return "blocked_by_opportunity_regression", safety, opp, non_target, artificial_ok, missing_ok, False
    if not non_target: return "blocked_by_non_target_regression", safety, opp, non_target, artificial_ok, missing_ok, False
    if not artificial_ok: return "blocked_by_artificial_probe_guard", safety, opp, non_target, artificial_ok, missing_ok, False
    if not missing_ok: return "blocked_by_missing_evidence", safety, opp, non_target, artificial_ok, missing_ok, False
    if not gain: return "blocked_by_no_revalidation_gain", safety, opp, non_target, artificial_ok, missing_ok, False
    return "fixed_update_candidate", safety, opp, non_target, artificial_ok, missing_ok, True


def _make_fixed(proposals, summary):
    rows = []
    by_candidate = summary.set_index("candidate_id")
    for _, p in proposals.iterrows():
        s = by_candidate.loc[p.source_candidate_id]
        status, safety, opp, non_target, artificial_ok, missing_ok, passed = _fixed_status(p, s)
        rows.append({"fixed_candidate_id": f"21c_e_fixed_{len(rows)+1:03d}", "source_proposal_id": p.proposal_id, "source_candidate_id": p.source_candidate_id, "suspected_coefficient_family": p.suspected_coefficient_family, "proposed_adjustment_direction": p.proposed_adjustment_direction, "proposed_adjustment_strength": p.proposed_adjustment_strength, "revalidation_passed": passed, "safety_revalidation_passed": safety, "opportunity_revalidation_passed": opp, "non_target_regression_check_passed": non_target, "artificial_probe_guard_passed": artificial_ok, "missing_evidence_guard_passed": missing_ok, "fixed_candidate_status": status, "coefficient_changed": False, "production_runtime_changed": False, "canonical_writeback_performed": False})
    return pd.DataFrame(rows, columns=FIXED_COLUMNS)


def _make_rejected(summary):
    rules = {
        "rejected_safety_regression": "new candidate removes harmful threshold, over-firing, or over-permission regression",
        "rejected_no_improvement": "stronger evidence or improved response data demonstrates measurable alignment gain",
        "rejected_over_correction": "smaller adjustment strength or combined family-level evidence avoids over-correction",
    }
    rows = []
    for _, r in summary[summary.candidate_decision.isin(rules)].iterrows():
        rows.append({"source_candidate_id": r.candidate_id, "candidate_decision": r.candidate_decision, "suspected_coefficient_family": r.suspected_coefficient_family, "shadow_adjustment_type": r.shadow_adjustment_type, "shadow_adjustment_strength": r.shadow_adjustment_strength, "rejection_reason": r.decision_reason, "safety_regression_count": r.safety_regression_count, "opportunity_regression_count": r.opportunity_regression_count, "non_target_regression_count": r.non_target_regression_count, "can_be_reconsidered_later": True, "required_condition_for_reconsideration": rules[r.candidate_decision]})
    return pd.DataFrame(rows, columns=REJECTED_COLUMNS)


def _make_hold(summary):
    rules = {
        "hold_mixed_evidence": ("mixed_target_and_non_target", "separate target improvement from non-target regression", "collect separated component evidence"),
        "hold_missing_inputs": ("missing_inputs", "resolve safe range, harmful threshold, v2 evidence, or missing inputs", "request more evidence"),
    }
    rows = []
    for _, r in summary[summary.candidate_decision.isin(rules)].iterrows():
        typ, evidence, action = rules[r.candidate_decision]
        rows.append({"source_candidate_id": r.candidate_id, "candidate_decision": r.candidate_decision, "suspected_coefficient_family": r.suspected_coefficient_family, "shadow_adjustment_type": r.shadow_adjustment_type, "shadow_adjustment_strength": r.shadow_adjustment_strength, "hold_reason": r.decision_reason, "missing_or_mixed_evidence_type": typ, "required_additional_evidence": evidence, "recommended_next_action": action})
    return pd.DataFrame(rows, columns=HOLD_COLUMNS)


def _handoff():
    specs = [
        ("functional_insurance_policy", "wrap_allowed", "21B-B", "May be wrapped as compute_functional_policy.", True, False, False, "wrapper only; no coefficient changes"),
        ("21c_b_alignment_helper", "audit_only", "21C-B", "Alignment helper remains evidence-only.", True, False, False, "not a controller"),
        ("21c_c_coefficient_drift_diagnosis_helper", "audit_only", "21C-C", "Coefficient drift diagnosis helper remains audit-only.", True, False, False, "no direct updates"),
        ("21c_d_shadow_validation_helper", "pre_update_validation_only", "21C-D", "Shadow validation helper may inform review.", True, False, False, "no runtime writes"),
        ("21c_e_fixed_update_candidates", "not_runtime_coefficients", "21C-E", "Fixed candidates are review artifacts only.", False, False, False, "must not become defaults"),
        ("rejected_candidates", "not_allowed", "21C-E", "Rejected candidates must not enter action module defaults.", False, False, False, "reconsider only with new evidence"),
        ("hold_candidates", "additional_evidence_only", "21C-E", "Hold candidates require additional evidence.", False, False, False, "not defaults"),
        ("artificial_probe_candidates", "guarded", "21C-D/21C-E", "Probe-like candidates require explicit guard and validation.", False, False, False, "cannot become fixed by themselves"),
        ("scenario_labels", "audit_only", "21C-A..E", "Scenario labels remain audit-only.", False, False, False, "must not control logic"),
        ("shadow_adjustment_values", "not_runtime_defaults", "21C-D/21C-E", "Shadow values are bounded review candidates.", False, False, False, "not runtime coefficients"),
    ]
    return pd.DataFrame([dict(zip(HANDOFF_COLUMNS, x)) for x in specs], columns=HANDOFF_COLUMNS)


def freeze_21c_verification_results(*, label_override=None) -> VerificationFreezeResult:
    shadow = validate_shadow_coefficient_candidates(label_override=label_override)
    long = shadow.functional_policy_shadow_validation_long
    summary = shadow.functional_policy_shadow_validation_summary
    decisions = shadow.functional_policy_shadow_candidate_decisions
    proposals = _make_proposals(summary, decisions)
    fixed = _make_fixed(proposals, summary)
    rejected = _make_rejected(summary)
    hold = _make_hold(summary)
    handoff = _handoff()
    fixed_count = int((fixed.fixed_candidate_status == "fixed_update_candidate").sum()) if not fixed.empty else 0
    blocked_count = len(fixed) - fixed_count
    if blocked_count and (fixed.fixed_candidate_status == "blocked_by_safety_revalidation").any(): judgement = "freeze_blocked_by_safety_revalidation"
    elif fixed_count: judgement = "freeze_ready_with_fixed_candidates"
    elif not hold.empty: judgement = "freeze_with_hold_items"
    else: judgement = "freeze_ready_for_action_module_api"
    freeze = pd.DataFrame([{"phase_id": "Phase 2G-21C-E", "source_phase_range": "21C-A..21C-E", "baseline_alignment_case_count": int(long[["run_id", "action_channel"]].drop_duplicates().shape[0]), "diagnosis_candidate_count": int(summary.suspected_coefficient_family.nunique()), "shadow_candidate_count": int(summary.candidate_id.nunique()), "accepted_shadow_candidate_count": int((summary.candidate_decision == "accepted_shadow_candidate").sum()), "rejected_candidate_count": len(rejected), "hold_candidate_count": len(hold), "update_proposal_count": len(proposals), "fixed_update_candidate_count": fixed_count, "blocked_update_candidate_count": blocked_count, "safety_regression_rejected_count": int((summary.candidate_decision == "rejected_safety_regression").sum()), "no_improvement_rejected_count": int((summary.candidate_decision == "rejected_no_improvement").sum()), "over_correction_rejected_count": int((summary.candidate_decision == "rejected_over_correction").sum()), "mixed_evidence_hold_count": int((summary.candidate_decision == "hold_mixed_evidence").sum()), "missing_input_hold_count": int((summary.candidate_decision == "hold_missing_inputs").sum()), "final_freeze_judgement": judgement, "coefficient_changed": False, "production_runtime_changed": False, "canonical_writeback_performed": False}], columns=FREEZE_SUMMARY_COLUMNS)
    return VerificationFreezeResult(freeze, proposals, fixed, rejected, hold, handoff)

# Tests

def test_freeze_exports_expected_schemas():
    r = freeze_21c_verification_results()
    assert list(r.functional_policy_21c_freeze_summary.columns) == FREEZE_SUMMARY_COLUMNS
    assert list(r.functional_policy_accepted_update_proposals.columns) == PROPOSAL_COLUMNS
    assert list(r.functional_policy_fixed_update_candidate_register.columns) == FIXED_COLUMNS
    assert list(r.functional_policy_rejected_candidate_register.columns) == REJECTED_COLUMNS
    assert list(r.functional_policy_hold_candidate_register.columns) == HOLD_COLUMNS
    assert list(r.functional_policy_action_module_handoff_contract.columns) == HANDOFF_COLUMNS


def test_freeze_reads_21c_d_and_references_21c_c_and_21c_b_helpers():
    src = inspect.getsource(freeze_21c_verification_results)
    assert "validate_shadow_coefficient_candidates" in src
    assert callable(diagnose_coefficient_drift_from_alignment) and callable(align_functional_policy_with_v2_response_curve)


def test_label_override_changes_only_audit_labels_not_freeze_decisions():
    a = freeze_21c_verification_results()
    b = freeze_21c_verification_results(label_override="renamed_audit_label")
    pd.testing.assert_frame_equal(a.functional_policy_21c_freeze_summary, b.functional_policy_21c_freeze_summary)
    pd.testing.assert_frame_equal(a.functional_policy_accepted_update_proposals, b.functional_policy_accepted_update_proposals)
    pd.testing.assert_frame_equal(a.functional_policy_fixed_update_candidate_register, b.functional_policy_fixed_update_candidate_register)


def test_no_write_markers_and_runtime_sources_are_unchanged():
    r = freeze_21c_verification_results()
    for df in [r.functional_policy_21c_freeze_summary, r.functional_policy_accepted_update_proposals, r.functional_policy_fixed_update_candidate_register]:
        if not df.empty:
            assert not df.coefficient_changed.any() and not df.production_runtime_changed.any() and not df.canonical_writeback_performed.any()
    assert "0.56 * fire_permission_score" in inspect.getsource(functional_insurance_policy)
    assert subprocess.run(["git", "diff", "--name-only", "--"] + [str(p) for p in PRODUCTION_RUNTIME_PATHS], check=True, text=True, capture_output=True).stdout.splitlines() == []


def test_only_accepted_candidates_become_proposals_and_require_validation():
    shadow = validate_shadow_coefficient_candidates()
    r = freeze_21c_verification_results()
    accepted = set(shadow.functional_policy_shadow_validation_summary.query("candidate_decision == 'accepted_shadow_candidate'").candidate_id)
    rejected_or_hold = set(shadow.functional_policy_shadow_validation_summary.query("candidate_decision != 'accepted_shadow_candidate'").candidate_id)
    assert set(r.functional_policy_accepted_update_proposals.source_candidate_id).issubset(accepted)
    assert set(r.functional_policy_accepted_update_proposals.source_candidate_id).isdisjoint(rejected_or_hold)
    if not r.functional_policy_accepted_update_proposals.empty:
        assert r.functional_policy_accepted_update_proposals.requires_additional_validation.all()
        assert not r.functional_policy_accepted_update_proposals.coefficient_changed.any()


def test_fixed_candidates_pass_all_revalidation_guards():
    fixed = freeze_21c_verification_results().functional_policy_fixed_update_candidate_register
    good = fixed[fixed.fixed_candidate_status == "fixed_update_candidate"]
    assert good.empty or (good.revalidation_passed & good.safety_revalidation_passed & good.opportunity_revalidation_passed & good.non_target_regression_check_passed & good.artificial_probe_guard_passed & good.missing_evidence_guard_passed).all()


def test_revalidation_blocking_statuses_are_reachable_with_synthetic_rows():
    p = pd.Series({"artificial_probe_flag": False, "proposal_confidence": "medium"})
    base = {"safety_regression_count": 0, "opportunity_regression_count": 0, "non_target_regression_count": 0, "overall_alignment_score_delta_mean": 0.1, "primary_misalignment_resolution_rate": 1.0, "improved_case_count": 1}
    cases = [({"safety_regression_count": 1}, "blocked_by_safety_revalidation"), ({"opportunity_regression_count": 1}, "blocked_by_opportunity_regression"), ({"non_target_regression_count": 1}, "blocked_by_non_target_regression"), ({"overall_alignment_score_delta_mean": 0.0}, "blocked_by_no_revalidation_gain")]
    for patch, status in cases:
        row = pd.Series({**base, **patch})
        assert _fixed_status(p, row)[0] == status
    assert _fixed_status(pd.Series({"artificial_probe_flag": True, "proposal_confidence": "medium"}), pd.Series(base))[0] == "blocked_by_artificial_probe_guard"
    assert _fixed_status(pd.Series({"artificial_probe_flag": False, "proposal_confidence": "low"}), pd.Series(base))[0] == "blocked_by_missing_evidence"


def test_artificial_probe_like_candidates_are_flagged_and_not_fixed():
    shadow = validate_shadow_coefficient_candidates()
    merged = shadow.functional_policy_shadow_validation_summary.merge(shadow.functional_policy_shadow_candidate_decisions, on=["candidate_id", "candidate_decision", "suspected_coefficient_family", "shadow_adjustment_type", "shadow_adjustment_strength"])
    probes = merged[merged.apply(_is_artificial_probe_like, axis=1)]
    assert not probes.empty
    r = freeze_21c_verification_results()
    assert set(probes.candidate_id).isdisjoint(set(r.functional_policy_accepted_update_proposals.source_candidate_id))
    assert set(probes.candidate_id).isdisjoint(set(r.functional_policy_fixed_update_candidate_register.source_candidate_id))


def test_rejected_register_contains_reconsideration_rules_and_never_enters_proposals():
    r = freeze_21c_verification_results()
    rej = r.functional_policy_rejected_candidate_register
    assert {"rejected_safety_regression", "rejected_no_improvement", "rejected_over_correction"}.intersection(set(rej.candidate_decision))
    assert rej.required_condition_for_reconsideration.astype(bool).all()
    assert set(rej.source_candidate_id).isdisjoint(set(r.functional_policy_accepted_update_proposals.source_candidate_id))


def test_hold_register_contains_evidence_requests_and_never_enters_proposals():
    r = freeze_21c_verification_results()
    hold = r.functional_policy_hold_candidate_register
    assert set(hold.candidate_decision).issubset({"hold_mixed_evidence", "hold_missing_inputs"})
    assert hold.required_additional_evidence.astype(bool).all()
    assert set(hold.source_candidate_id).isdisjoint(set(r.functional_policy_accepted_update_proposals.source_candidate_id))


def test_action_module_handoff_contract_marks_boundaries():
    h = freeze_21c_verification_results().functional_policy_action_module_handoff_contract.set_index("handoff_item")
    assert bool(h.loc["functional_insurance_policy", "allowed_in_action_module_api"])
    assert h.loc["21c_b_alignment_helper", "handoff_status"] == "audit_only"
    assert h.loc["21c_e_fixed_update_candidates", "handoff_status"] == "not_runtime_coefficients"
    assert not bool(h.loc["rejected_candidates", "allowed_in_action_module_api"])
    assert h.loc["hold_candidates", "handoff_status"] == "additional_evidence_only"
    assert h.loc["artificial_probe_candidates", "handoff_status"] == "guarded"
    assert h.loc["scenario_labels", "handoff_status"] == "audit_only"
    assert h.loc["shadow_adjustment_values", "handoff_status"] == "not_runtime_defaults"
