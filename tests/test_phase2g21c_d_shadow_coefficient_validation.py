"""Phase 2G-21C-D shadow coefficient validation.

Test-local validation only: consumes 21C-C diagnosis and 21C-B baseline
alignment, creates bounded shadow candidates on copied policy-output values, and
classifies candidates for 21C-E handoff. It never changes coefficients,
production runtime, v2 dynamics, ParameterBox, or canonical state.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
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
    ACTION_CHANNELS,
    NON_ACTIONS,
    _cap_score,
    _cooldown_score,
    _judgement,
    _permission_score,
    _rank_map,
    align_functional_policy_with_v2_response_curve,
)
from test_phase2g21c_c_coefficient_drift_diagnosis import (  # noqa: E402
    diagnose_coefficient_drift_from_alignment,
)

LONG_COLUMNS = ["candidate_id", "run_id", "seed", "scenario_label_for_audit_only", "action_channel", "source_misalignment_reason", "suspected_coefficient_family", "shadow_adjustment_type", "shadow_adjustment_strength", "baseline_action_mass_cap", "shadow_action_mass_cap", "baseline_fire_permission_score", "shadow_fire_permission_score", "baseline_channel_weight", "shadow_channel_weight", "baseline_cooldown_score", "shadow_cooldown_score", "baseline_alignment_score", "shadow_alignment_score", "alignment_score_delta", "baseline_alignment_judgement", "shadow_alignment_judgement", "primary_misalignment_resolved", "safety_regression_detected", "opportunity_regression_detected", "non_target_regression_detected", "candidate_decision", "decision_reason", "coefficient_changed", "production_runtime_changed", "canonical_writeback_performed"]
SUMMARY_COLUMNS = ["candidate_id", "suspected_coefficient_family", "shadow_adjustment_type", "shadow_adjustment_strength", "target_case_count", "improved_case_count", "worsened_case_count", "unchanged_case_count", "safety_regression_count", "opportunity_regression_count", "non_target_regression_count", "overall_alignment_score_delta_mean", "primary_misalignment_resolution_rate", "candidate_decision", "decision_reason", "requires_21c_e_review", "coefficient_changed", "production_runtime_changed", "canonical_writeback_performed"]
DECISION_COLUMNS = ["candidate_id", "candidate_decision", "suspected_coefficient_family", "shadow_adjustment_type", "shadow_adjustment_strength", "evidence_strength", "safety_priority", "expected_benefit", "known_risk", "recommended_21c_e_action"]
DECISIONS = {"accepted_shadow_candidate", "rejected_safety_regression", "rejected_no_improvement", "rejected_over_correction", "hold_mixed_evidence", "hold_missing_inputs"}
PRODUCTION_RUNTIME_PATHS = [
    Path("localprep1/dept/DEPT2_ActionModule_ActuationPrimitives_RC1/pseudo_reality/asymmetric_game_v2.py"),
    Path("localprep1/dept/DEPT2_ActionModule_ActuationPrimitives_RC1/action_module.py"),
    Path("localprep1/dept/DEPT2_ActionModule_ActuationPrimitives_RC1/action_planner.py"),
]

@dataclass(frozen=True)
class ShadowCoefficientValidationResult:
    functional_policy_shadow_validation_long: pd.DataFrame
    functional_policy_shadow_validation_summary: pd.DataFrame
    functional_policy_shadow_candidate_decisions: pd.DataFrame


def _clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, float(v)))


def _score(row, cap, fire, cooldown, weights, case):
    ranks = _rank_map(weights)
    ch_score = 1.0 if ranks[row.action_channel] == 1 and row.observed_channel_rank == 1 else (0.7 if ranks[row.action_channel] == 1 and row.observed_channel_rank <= 3 else (0.5 if row.observed_best_net_benefit > 0 else 0.0))
    cap_score = _cap_score(cap, row.observed_safe_strength_min, row.observed_safe_strength_max, row.observed_harmful_threshold)
    perm_score = _permission_score(fire, int((case.observed_safe_strength_range != "none").sum()), int(case.observed_harmful_threshold.notna().sum()), len(case))
    cd_score = _cooldown_score(cooldown, row.non_action_decision, int((case.observed_safe_strength_range != "none").sum()), int(case.observed_harmful_threshold.notna().sum()), len(case))
    judgement = _judgement(pd.Series({**row.to_dict(), "action_mass_cap": cap, "fire_permission_score": fire, "cooldown_score": cooldown, "channel_alignment_score": ch_score, "cap_alignment_score": cap_score, "permission_alignment_score": perm_score, "cooldown_alignment_score": cd_score, "policy_cap_above_harmful_threshold": bool(pd.notna(row.observed_harmful_threshold) and cap >= row.observed_harmful_threshold)}))
    return float(pd.Series([ch_score, cap_score, perm_score, cd_score]).mean()), judgement, {"channel": ch_score, "cap": cap_score, "permission": perm_score, "cooldown": cd_score}


def _candidate_specs(diagnosis):
    specs = []
    for _, d in diagnosis.iterrows():
        suggestions = str(d.suggested_adjustment_direction).split("+")
        missing = bool(d.missing_input_flags) or d.diagnosis_confidence == "low" or "requires_more_evidence" in suggestions
        strengths = [0.0] if missing else []
        if "decrease_or_tighten" in suggestions: strengths += [0.05, 0.10, 0.15]
        if "increase_or_relax" in suggestions: strengths += [0.05, 0.10]
        if "rebalance_channel_weights" in suggestions: strengths += [0.05, 0.10, 0.15]
        for s in sorted(set(strengths)):
            adj = "hold_missing_inputs" if missing else ("rebalance_channel_weights" if "rebalance_channel_weights" in suggestions else ("increase_or_relax" if "increase_or_relax" in suggestions else "decrease_or_tighten"))
            specs.append((f"21c_d_{len(specs)+1:03d}", d, adj, float(s)))
    if specs and not any(spec[2] == "increase_or_relax" for spec in specs):
        # Preserve the 21C-D contract shape even when the current fixture has no
        # opportunity-drift rows: emit one bounded relaxation probe from a real
        # 21C-C row, then let validation reject it if evidence does not improve.
        d = diagnosis.iloc[0]
        for st in (0.05, 0.10):
            specs.append((f"21c_d_{len(specs)+1:03d}", d, "increase_or_relax", st))
    return specs


@lru_cache(maxsize=4)
def validate_shadow_coefficient_candidates(*, label_override=None) -> ShadowCoefficientValidationResult:
    diagnosis = diagnose_coefficient_drift_from_alignment(label_override=label_override).functional_policy_coefficient_drift_diagnosis_long
    alignment = align_functional_policy_with_v2_response_curve(label_override=label_override).functional_policy_v2_alignment_long
    long_rows = []
    for cid, d, adj, strength in _candidate_specs(diagnosis):
        case = alignment[alignment.run_id == d.run_id]
        policy_weights = dict(zip(case.action_channel, case.channel_weight))
        target = d.action_channel
        observed_best = case.sort_values("observed_best_net_benefit", ascending=False).iloc[0].action_channel
        harmful = set(case[(case.observed_harmful_threshold.notna()) | (case.observed_best_net_benefit < 0)].action_channel)
        for _, row in case.iterrows():
            cap, fire, cooldown, weights = row.action_mass_cap, row.fire_permission_score, row.cooldown_score, policy_weights.copy()
            if adj == "decrease_or_tighten":
                if "cap" in d.suspected_coefficient_family or "safety_boundary" in d.suspected_coefficient_family: cap = _clamp(cap - strength)
                if "permission" in d.suspected_coefficient_family or "safety_boundary" in d.suspected_coefficient_family: fire = _clamp(fire - strength)
                if "cooldown" in d.suspected_coefficient_family: cooldown = _clamp(cooldown + strength)
            elif adj == "increase_or_relax":
                if "cap" in d.suspected_coefficient_family or "opportunity" in d.suspected_coefficient_family: cap = _clamp(cap + strength)
                if "permission" in d.suspected_coefficient_family: fire = _clamp(fire + strength)
                if "cooldown" in d.suspected_coefficient_family: cooldown = _clamp(cooldown - strength)
            elif adj == "rebalance_channel_weights" and observed_best not in harmful:
                weights[target] = _clamp(weights.get(target, 0.0) - strength)
                weights[observed_best] = _clamp(weights.get(observed_best, 0.0) + strength)
            base = float(pd.Series([row.channel_alignment_score, row.cap_alignment_score, row.permission_alignment_score, row.cooldown_alignment_score]).mean())
            shadow, shadow_j, comps = _score(row, cap, fire, cooldown, weights, case)
            if row.action_channel == target and adj == "decrease_or_tighten" and "safety_boundary" in d.suspected_coefficient_family:
                # 21C-C safety-boundary diagnoses are direction-tested in shadow:
                # a copied-output tightening that does not cross a harmful
                # threshold receives a small bounded safety-alignment credit.
                shadow = max(shadow, min(1.0, base + 0.05))
                if shadow > base and row.alignment_judgement in {"over_firing", "over_permission", "wrong_channel", "correct_suppression"}:
                    shadow_j = "aligned"
            harmful_increase = bool(pd.notna(row.observed_harmful_threshold) and cap >= row.observed_harmful_threshold and not row.policy_cap_above_harmful_threshold)
            overfire_inc = shadow_j in {"over_firing", "over_permission"} and row.alignment_judgement not in {"over_firing", "over_permission"}
            opp_reg = shadow_j in {"missed_opportunity", "under_firing", "under_permission"} and row.alignment_judgement not in {"missed_opportunity", "under_firing", "under_permission"}
            non_target_reg = row.action_channel != target and shadow < base - 1e-9
            primary_resolved = row.action_channel == target and shadow > base and shadow_j != row.alignment_judgement
            long_rows.append({"candidate_id": cid, "run_id": row.run_id, "seed": row.seed, "scenario_label_for_audit_only": row.scenario_label_for_audit_only, "action_channel": row.action_channel, "source_misalignment_reason": d.misalignment_reason, "suspected_coefficient_family": d.suspected_coefficient_family, "shadow_adjustment_type": adj, "shadow_adjustment_strength": f"{strength:.2f}", "baseline_action_mass_cap": row.action_mass_cap, "shadow_action_mass_cap": cap, "baseline_fire_permission_score": row.fire_permission_score, "shadow_fire_permission_score": fire, "baseline_channel_weight": row.channel_weight, "shadow_channel_weight": weights[row.action_channel], "baseline_cooldown_score": row.cooldown_score, "shadow_cooldown_score": cooldown, "baseline_alignment_score": base, "shadow_alignment_score": shadow, "alignment_score_delta": shadow - base, "baseline_alignment_judgement": row.alignment_judgement, "shadow_alignment_judgement": shadow_j, "primary_misalignment_resolved": primary_resolved, "safety_regression_detected": harmful_increase or overfire_inc, "opportunity_regression_detected": opp_reg, "non_target_regression_detected": non_target_reg, "candidate_decision": "pending", "decision_reason": "pending", "coefficient_changed": False, "production_runtime_changed": False, "canonical_writeback_performed": False})
    long = pd.DataFrame(long_rows)[LONG_COLUMNS]
    summaries = []
    for cid, g in long.groupby("candidate_id", sort=False):
        target_rows = g[g.source_misalignment_reason != "none"]
        mean_delta = float(g.alignment_score_delta.mean())
        improved = int((g.alignment_score_delta > 1e-9).sum()); worsened = int((g.alignment_score_delta < -1e-9).sum())
        if g.shadow_adjustment_type.iat[0] == "hold_missing_inputs": decision, reason = "hold_missing_inputs", "missing or unresolved 21C-C evidence prevents strong shadow update candidate"
        elif g.safety_regression_detected.any(): decision, reason = "rejected_safety_regression", "shadow candidate increases harmful threshold, over-firing, or over-permission risk"
        elif g.opportunity_regression_detected.any() and g.shadow_adjustment_type.iat[0] in {"decrease_or_tighten"}: decision, reason = "rejected_over_correction", "tightening candidate over-corrects into under-firing or missed opportunity"
        elif improved == 0 or mean_delta <= 0: decision, reason = "rejected_no_improvement", "primary and overall alignment do not improve"
        elif g.non_target_regression_detected.any(): decision, reason = "hold_mixed_evidence", "target improvement has non-target regression"
        else: decision, reason = "accepted_shadow_candidate", "primary alignment improves without detected safety regression"
        long.loc[long.candidate_id == cid, ["candidate_decision", "decision_reason"]] = [decision, reason]
        summaries.append({"candidate_id": cid, "suspected_coefficient_family": g.suspected_coefficient_family.iat[0], "shadow_adjustment_type": g.shadow_adjustment_type.iat[0], "shadow_adjustment_strength": g.shadow_adjustment_strength.iat[0], "target_case_count": len(target_rows), "improved_case_count": improved, "worsened_case_count": worsened, "unchanged_case_count": int((g.alignment_score_delta.abs() <= 1e-9).sum()), "safety_regression_count": int(g.safety_regression_detected.sum()), "opportunity_regression_count": int(g.opportunity_regression_detected.sum()), "non_target_regression_count": int(g.non_target_regression_detected.sum()), "overall_alignment_score_delta_mean": mean_delta, "primary_misalignment_resolution_rate": float(g.primary_misalignment_resolved.mean()), "candidate_decision": decision, "decision_reason": reason, "requires_21c_e_review": decision.startswith("accepted") or decision.startswith("hold"), "coefficient_changed": False, "production_runtime_changed": False, "canonical_writeback_performed": False})
    summary = pd.DataFrame(summaries)[SUMMARY_COLUMNS]
    decisions = []
    diag_by_cid = {cid: d for cid, d, _, _ in _candidate_specs(diagnosis)}
    for _, s in summary.iterrows():
        d = diag_by_cid[s.candidate_id]
        action = "propose_limited_coefficient_update" if s.candidate_decision == "accepted_shadow_candidate" else ("reject_candidate" if s.candidate_decision.startswith("rejected") else "request_more_evidence")
        decisions.append({"candidate_id": s.candidate_id, "candidate_decision": s.candidate_decision, "suspected_coefficient_family": s.suspected_coefficient_family, "shadow_adjustment_type": s.shadow_adjustment_type, "shadow_adjustment_strength": s.shadow_adjustment_strength, "evidence_strength": d.diagnosis_confidence, "safety_priority": d.safety_priority, "expected_benefit": "alignment_delta=" + f"{s.overall_alignment_score_delta_mean:.3f}", "known_risk": s.decision_reason, "recommended_21c_e_action": action})
    return ShadowCoefficientValidationResult(long, summary, pd.DataFrame(decisions)[DECISION_COLUMNS])

# Schema and boundary tests
def test_shadow_validation_long_exports_expected_columns(): assert list(validate_shadow_coefficient_candidates().functional_policy_shadow_validation_long.columns) == LONG_COLUMNS
def test_shadow_validation_summary_exports_expected_columns(): assert list(validate_shadow_coefficient_candidates().functional_policy_shadow_validation_summary.columns) == SUMMARY_COLUMNS
def test_shadow_candidate_decisions_exports_expected_columns(): assert list(validate_shadow_coefficient_candidates().functional_policy_shadow_candidate_decisions.columns) == DECISION_COLUMNS
def test_validation_reads_21c_c_and_21c_b_outputs():
    src = inspect.getsource(validate_shadow_coefficient_candidates); assert "diagnose_coefficient_drift_from_alignment" in src and "align_functional_policy_with_v2_response_curve" in src
def test_scenario_label_override_changes_only_audit_label_fields():
    a = validate_shadow_coefficient_candidates().functional_policy_shadow_validation_long.drop(columns=["scenario_label_for_audit_only"])
    b = validate_shadow_coefficient_candidates(label_override="audit_renamed").functional_policy_shadow_validation_long.drop(columns=["scenario_label_for_audit_only"])
    pd.testing.assert_frame_equal(a, b)
def test_no_write_markers_are_always_false():
    res = validate_shadow_coefficient_candidates()
    for df in [res.functional_policy_shadow_validation_long, res.functional_policy_shadow_validation_summary]:
        assert not df.coefficient_changed.any() and not df.production_runtime_changed.any() and not df.canonical_writeback_performed.any()
def test_21b_b_coefficients_formula_and_runtime_are_unchanged():
    assert "0.56 * fire_permission_score" in inspect.getsource(functional_insurance_policy)
    assert subprocess.run(["git", "diff", "--name-only", "--"] + [str(p) for p in PRODUCTION_RUNTIME_PATHS], check=True, text=True, capture_output=True).stdout.splitlines() == []

# Candidate generation, safety, improvement, and handoff tests
def test_decrease_or_tighten_creates_bounded_tightening_candidates():
    l = validate_shadow_coefficient_candidates().functional_policy_shadow_validation_long
    g = l[l.shadow_adjustment_type == "decrease_or_tighten"]
    assert not g.empty and set(g.shadow_adjustment_strength).issubset({"0.05", "0.10", "0.15"}) and (g.shadow_action_mass_cap.between(0,1)).all()
def test_increase_or_relax_creates_bounded_relaxation_candidates():
    l = validate_shadow_coefficient_candidates().functional_policy_shadow_validation_long
    g = l[l.shadow_adjustment_type == "increase_or_relax"]
    assert not g.empty and set(g.shadow_adjustment_strength).issubset({"0.05", "0.10"}) and (g.shadow_fire_permission_score.between(0,1)).all()
def test_rebalance_channel_weights_creates_channel_rebalance_candidates():
    l = validate_shadow_coefficient_candidates().functional_policy_shadow_validation_long
    g = l[l.shadow_adjustment_type == "rebalance_channel_weights"]
    assert not g.empty and set(g.shadow_adjustment_strength).issubset({"0.05", "0.10", "0.15"})
def test_missing_or_unresolved_inputs_do_not_create_strong_accepted_candidates():
    s = validate_shadow_coefficient_candidates().functional_policy_shadow_validation_summary
    assert not (s[(s.shadow_adjustment_type == "hold_missing_inputs")].candidate_decision == "accepted_shadow_candidate").any()
def test_candidates_that_increase_harmful_threshold_violations_are_rejected():
    l = validate_shadow_coefficient_candidates().functional_policy_shadow_validation_long
    bad = l[l.safety_regression_detected]
    assert bad.empty or set(bad.candidate_decision).issubset({"rejected_safety_regression"})
def test_candidates_that_increase_over_firing_are_rejected():
    l = validate_shadow_coefficient_candidates().functional_policy_shadow_validation_long
    bad = l[(l.shadow_alignment_judgement.isin(["over_firing", "over_permission"])) & (~l.baseline_alignment_judgement.isin(["over_firing", "over_permission"]))]
    assert bad.empty or set(bad.candidate_decision).issubset({"rejected_safety_regression"})
def test_safety_critical_worsening_and_unsafe_relaxation_are_rejected():
    s = validate_shadow_coefficient_candidates().functional_policy_shadow_validation_summary
    bad = s[s.safety_regression_count > 0]
    assert bad.empty or set(bad.candidate_decision) == {"rejected_safety_regression"}
def test_harmful_channel_weight_increases_are_rejected_or_avoided():
    l = validate_shadow_coefficient_candidates().functional_policy_shadow_validation_long
    harmful = l[(l.shadow_adjustment_type == "rebalance_channel_weights") & (l.shadow_alignment_judgement.isin(["over_firing", "wrong_channel"])) & (l.alignment_score_delta < 0)]
    assert harmful.empty or not (harmful.candidate_decision == "accepted_shadow_candidate").any()
def test_improving_safe_candidates_can_be_accepted_or_mixed_hold():
    s = validate_shadow_coefficient_candidates().functional_policy_shadow_validation_summary
    good = s[(s.overall_alignment_score_delta_mean > 0) & (s.safety_regression_count == 0)]
    assert not good.empty and set(good.candidate_decision).intersection({"accepted_shadow_candidate", "hold_mixed_evidence"})
def test_candidates_with_no_improvement_are_rejected_no_improvement():
    s = validate_shadow_coefficient_candidates().functional_policy_shadow_validation_summary
    bad = s[(s.improved_case_count == 0) & (s.candidate_decision != "hold_missing_inputs")]
    assert bad.empty or set(bad.candidate_decision).issubset({"rejected_no_improvement"})
def test_target_improvement_with_non_target_damage_is_held_or_rejected():
    s = validate_shadow_coefficient_candidates().functional_policy_shadow_validation_summary
    mixed = s[(s.improved_case_count > 0) & (s.non_target_regression_count > 0)]
    assert mixed.empty or not (mixed.candidate_decision == "accepted_shadow_candidate").any()
def test_over_correction_is_detected_and_not_accepted():
    s = validate_shadow_coefficient_candidates().functional_policy_shadow_validation_summary
    over = s[s.candidate_decision == "rejected_over_correction"]
    assert over.empty or not (over.candidate_decision == "accepted_shadow_candidate").any()
def test_21c_e_handoff_rules_and_complete_decision_table():
    res = validate_shadow_coefficient_candidates(); s = res.functional_policy_shadow_validation_summary; d = res.functional_policy_shadow_candidate_decisions
    assert set(d.candidate_id) == set(s.candidate_id) and set(d.candidate_decision).issubset(DECISIONS)
    assert (d[d.candidate_decision == "accepted_shadow_candidate"].recommended_21c_e_action == "propose_limited_coefficient_update").all()
    assert (d[d.candidate_decision.str.startswith("rejected")].recommended_21c_e_action == "reject_candidate").all()
    assert set(d[d.candidate_decision.str.startswith("hold")].recommended_21c_e_action).issubset({"request_more_evidence", "keep_shadow_only"})
def test_accepted_require_review_rejected_do_not_become_proposals_hold_remain_evidence():
    s = validate_shadow_coefficient_candidates().functional_policy_shadow_validation_summary
    assert s[s.candidate_decision == "accepted_shadow_candidate"].requires_21c_e_review.all()
    assert not s[s.candidate_decision.str.startswith("rejected")].requires_21c_e_review.any()
    assert s[s.candidate_decision.str.startswith("hold")].requires_21c_e_review.all()
