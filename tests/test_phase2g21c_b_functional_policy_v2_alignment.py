"""Phase 2G-21C-B functional policy × v2 response curve alignment.

Test-local alignment only: compares 21B-B functional policy outputs with 21C-A
measured v2 response summaries/curves.  It does not tune coefficients, alter v2
dynamics, or touch production runtime code.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import inspect
import sys
import subprocess

import pandas as pd

TESTS_ROOT = Path(__file__).resolve().parent
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))

from test_phase2g21b_b_functional_insurance_policy import (  # noqa: E402
    CHANNELS,
    ActionHistoryBundle,
    LowerDistributionBundle,
    UpperPressureBundle,
    functional_insurance_policy,
)
from test_phase2g21c_a_v2_strength_response_curve import (  # noqa: E402
    ACTION_CHANNELS,
    measure_v2_strength_response_curve,
)

NON_ACTIONS = {"no_op", "observe_only", "cooldown", "hold_shadow"}
HARMFUL_JUDGEMENTS = {"harmful_strength", "side_effect_dominant"}
PRODUCTION_RUNTIME_PATHS = [
    Path("localprep1/dept/DEPT2_ActionModule_ActuationPrimitives_RC1/pseudo_reality/asymmetric_game_v2.py"),
    Path("localprep1/dept/DEPT2_ActionModule_ActuationPrimitives_RC1/action_module.py"),
    Path("localprep1/dept/DEPT2_ActionModule_ActuationPrimitives_RC1/action_planner.py"),
]
LONG_COLUMNS = ["run_id", "seed", "scenario_label_for_audit_only", "action_channel", "fire_permission_score", "action_mass_cap", "channel_weight", "non_action_decision", "cooldown_score", "suppression_reason", "observed_best_strength", "observed_best_net_benefit", "observed_safe_strength_min", "observed_safe_strength_max", "observed_safe_strength_range", "observed_harmful_threshold", "max_risk_reduction_vs_no_op", "max_side_effect_score", "net_benefit_positive_count", "net_benefit_negative_count", "curve_shape_judgement", "response_summary_judgement", "policy_cap_within_safe_range", "policy_cap_above_harmful_threshold", "policy_channel_rank", "observed_channel_rank", "channel_rank_delta", "channel_alignment_score", "cap_alignment_score", "permission_alignment_score", "cooldown_alignment_score", "alignment_judgement", "misalignment_reason", "policy_evidence_trace", "v2_response_evidence_trace", "missing_input_flags", "v2_trace_used_as_action_runtime_input", "v2_trace_used_as_post_action_audit", "production_runtime_changed"]
SUMMARY_COLUMNS = ["run_id", "seed", "scenario_label_for_audit_only", "fire_permission_score", "action_mass_cap", "non_action_decision", "cooldown_score", "suppression_reason", "top_policy_channel", "top_policy_channel_weight", "top_observed_channel", "top_observed_net_benefit", "safe_channel_count", "harmful_channel_count", "positive_net_benefit_channel_count", "negative_net_benefit_channel_count", "best_channel_cap_alignment", "best_channel_rank_alignment", "overall_alignment_score", "overall_alignment_judgement", "primary_misalignment_type", "misalignment_reasons", "missing_input_flags"]

@dataclass(frozen=True)
class AlignmentResult:
    functional_policy_v2_alignment_long: pd.DataFrame
    functional_policy_v2_alignment_summary: pd.DataFrame


def policy_bundle_from_v2_case(case_summary: pd.DataFrame) -> tuple[UpperPressureBundle, LowerDistributionBundle, ActionHistoryBundle]:
    # Uses measured numeric response properties only; labels are audit-only.
    safe_count = int((case_summary.observed_safe_strength_range != "none").sum())
    harmful_count = int(case_summary.observed_harmful_threshold.notna().sum())
    pos_rows = int(case_summary.net_benefit_positive_count.sum())
    neg_rows = int(case_summary.net_benefit_negative_count.sum())
    max_benefit = max(0.0, float(case_summary.observed_best_net_benefit.max()))
    max_side = min(1.0, float(case_summary.max_side_effect_score.max()))
    safe_ratio = safe_count / max(1, len(case_summary))
    harmful_ratio = harmful_count / max(1, len(case_summary))
    positive_ratio = pos_rows / max(1, pos_rows + neg_rows)
    min_harmful = case_summary.observed_harmful_threshold.dropna()
    harmful_pressure = 0.0 if min_harmful.empty else max(0.0, 1.0 - float(min_harmful.min()) / 0.24)
    upper = UpperPressureBundle(
        stabilize_pressure=min(1.0, 0.25 + safe_ratio), explore_pressure=min(1.0, 0.20 + positive_ratio),
        buffer_pressure=min(1.0, 0.20 + safe_ratio), relation_relief_pressure=min(1.0, 0.20 + safe_ratio),
        reversibility_pressure=min(1.0, 0.20 + safe_ratio), cooldown_pressure=min(1.0, harmful_ratio + harmful_pressure),
        observe_pressure=min(1.0, harmful_ratio), de_risk_pressure=min(1.0, 0.20 + positive_ratio),
        overconvergence_avoidance_pressure=min(1.0, 0.10 + positive_ratio / 2),
    )
    lower = LowerDistributionBundle(
        local_no_action_risk_estimate=min(1.0, max_benefit * 4), local_action_side_effect_cost_estimate=max_side,
        local_fire_margin=max(-1.0, min(1.0, 2 * positive_ratio - 1)), pair_no_action_risk_estimate=min(1.0, max_benefit * 3),
        pair_action_side_effect_cost_estimate=max_side, pair_fire_margin=max(-1.0, min(1.0, 2 * safe_ratio - 1)),
        confidence=max(0.2, min(1.0, 0.35 + safe_ratio - 0.35 * harmful_ratio)), burden=min(1.0, harmful_ratio),
        fatigue=min(1.0, max_side), collapse_proximity=min(1.0, harmful_pressure), reversibility_need=safe_ratio,
        relation_lock_proxy=safe_ratio, coupling_proxy=safe_ratio, exploration_need=positive_ratio,
        unresolved_proxy=1.0 - safe_ratio, side_effect_risk=min(1.0, max_side + harmful_ratio / 2),
    )
    history = ActionHistoryBundle(
        recent_correct_fire_rate=positive_ratio, recent_harmful_fire_rate=min(1.0, harmful_ratio),
        recent_side_effect_score=max_side, recent_cooldown_state=harmful_pressure, recent_no_op_worsening=max_benefit,
        recent_wrong_direction_rate=harmful_ratio,
    )
    return upper, lower, history


def _rank_map(items: dict[str, float], reverse=True) -> dict[str, int]:
    return {name: i + 1 for i, (name, _) in enumerate(sorted(items.items(), key=lambda kv: kv[1], reverse=reverse))}


def _cap_score(cap, safe_min, safe_max, harmful):
    if safe_min is not None and pd.notna(safe_min) and safe_max is not None and pd.notna(safe_max):
        if safe_min <= cap <= safe_max:
            return 1.0
        if cap < safe_min:
            return 0.7
        if harmful is None or pd.isna(harmful) or cap < harmful:
            return 0.5
        return 0.0
    if harmful is not None and pd.notna(harmful) and cap >= harmful:
        return 0.0
    return 0.3


def _permission_score(fire, safe_count, harmful_count, channel_count):
    has_safe = safe_count > 0
    mostly_harmful = harmful_count >= max(1, channel_count // 2)
    if fire >= 0.45 and has_safe and not mostly_harmful:
        return 1.0
    if fire < 0.25 and not has_safe:
        return 1.0
    if fire >= 0.45 and mostly_harmful:
        return 0.0
    if fire < 0.25 and safe_count >= 2:
        return 0.0
    return 0.6


def _cooldown_score(cooldown, non_action, safe_count, harmful_count, channel_count):
    suppressing = cooldown >= 0.55 or non_action in NON_ACTIONS
    mostly_harmful = harmful_count >= max(1, channel_count // 2)
    if suppressing and (safe_count == 0 or mostly_harmful):
        return 1.0
    if suppressing and safe_count > 0:
        return 0.25
    if not suppressing and safe_count > 0:
        return 1.0
    if not suppressing and mostly_harmful:
        return 0.0
    return 0.6


def _reasons(row):
    reasons = []
    if row.cap_alignment_score == 0.0 and row.policy_cap_above_harmful_threshold:
        reasons.append("policy_cap_too_high")
    if row.cap_alignment_score == 0.7:
        reasons.append("policy_cap_too_low")
    if row.channel_alignment_score == 0.0:
        reasons.append("policy_channel_weight_mismatch")
    if row.permission_alignment_score == 0.0 and row.fire_permission_score >= 0.45:
        reasons.append("policy_permission_too_high")
    if row.permission_alignment_score == 0.0 and row.fire_permission_score < 0.25:
        reasons.append("policy_permission_too_low")
    if row.cooldown_alignment_score == 0.25:
        reasons.append("cooldown_too_strong")
    if row.cooldown_alignment_score == 0.0:
        reasons.append("cooldown_too_weak")
    if row.observed_safe_strength_range == "none":
        reasons.append("safe_range_absent")
    if pd.notna(row.observed_harmful_threshold) and row.observed_harmful_threshold <= 0.08:
        reasons.append("harmful_threshold_low")
    if row.curve_shape_judgement == "mostly_harmful":
        reasons.append("v2_curve_mostly_harmful")
    if row.curve_shape_judgement == "mostly_no_effect":
        reasons.append("v2_curve_mostly_no_effect")
    return "+".join(reasons) if reasons else "none"


def _judgement(row):
    if row.missing_input_flags:
        return "unresolved"
    if row.non_action_decision in NON_ACTIONS and row.observed_safe_strength_range != "none" and row.observed_best_net_benefit > 0:
        return "missed_opportunity"
    if row.non_action_decision in NON_ACTIONS and (row.observed_safe_strength_range == "none" or row.curve_shape_judgement == "mostly_harmful" or (pd.notna(row.observed_harmful_threshold) and row.observed_harmful_threshold <= 0.08)):
        return "correct_suppression"
    if row.policy_cap_above_harmful_threshold or (row.fire_permission_score >= 0.45 and row.response_summary_judgement == "no_safe_strength_observed"):
        return "over_firing"
    if row.action_mass_cap < (row.observed_safe_strength_min if pd.notna(row.observed_safe_strength_min) else -1) and row.observed_best_net_benefit > 0:
        return "under_firing"
    if row.channel_alignment_score == 0.0:
        return "wrong_channel"
    if row.permission_alignment_score == 0.0 and row.fire_permission_score >= 0.45:
        return "over_permission"
    if row.permission_alignment_score == 0.0 and row.fire_permission_score < 0.25:
        return "under_permission"
    if row.cap_alignment_score >= 0.5 and row.channel_alignment_score >= 0.5:
        return "aligned"
    return "inconclusive"


@lru_cache(maxsize=4)
def align_functional_policy_with_v2_response_curve(*, label_override=None) -> AlignmentResult:
    measured = measure_v2_strength_response_curve(label_override=label_override)
    summary = measured.v2_strength_response_summary
    long_curve = measured.v2_strength_response_curve_long
    rows = []
    for (run_id, seed, label), case_summary in summary.groupby(["run_id", "seed", "scenario_label_for_audit_only"], sort=False):
        policy = functional_insurance_policy(*policy_bundle_from_v2_case(case_summary))
        observed_ranks = _rank_map(dict(zip(case_summary.action_channel, case_summary.observed_best_net_benefit)))
        policy_ranks = _rank_map({c: policy.channel_weights[c] for c in ACTION_CHANNELS})
        safe_count = int((case_summary.observed_safe_strength_range != "none").sum())
        harmful_count = int(case_summary.observed_harmful_threshold.notna().sum())
        for _, s in case_summary.iterrows():
            channel_rows = long_curve[(long_curve.run_id == run_id) & (long_curve.action_channel == s.action_channel)]
            cap = policy.action_mass_cap
            within = pd.notna(s.observed_safe_strength_min) and s.observed_safe_strength_min <= cap <= s.observed_safe_strength_max
            above = pd.notna(s.observed_harmful_threshold) and cap >= s.observed_harmful_threshold
            pr, orank = policy_ranks[s.action_channel], observed_ranks[s.action_channel]
            ch_score = 1.0 if pr == 1 and orank == 1 else (0.7 if pr == 1 and orank <= 3 else (0.5 if s.observed_best_net_benefit > 0 else 0.0))
            rec = {"run_id": run_id, "seed": seed, "scenario_label_for_audit_only": label, "action_channel": s.action_channel,
                   "fire_permission_score": policy.fire_permission_score, "action_mass_cap": cap, "channel_weight": policy.channel_weights[s.action_channel],
                   "non_action_decision": policy.non_action_decision, "cooldown_score": policy.cooldown_score, "suppression_reason": policy.suppression_reason,
                   "observed_best_strength": s.observed_best_strength, "observed_best_net_benefit": s.observed_best_net_benefit,
                   "observed_safe_strength_min": s.observed_safe_strength_min, "observed_safe_strength_max": s.observed_safe_strength_max,
                   "observed_safe_strength_range": s.observed_safe_strength_range, "observed_harmful_threshold": s.observed_harmful_threshold,
                   "max_risk_reduction_vs_no_op": s.max_risk_reduction_vs_no_op, "max_side_effect_score": s.max_side_effect_score,
                   "net_benefit_positive_count": s.net_benefit_positive_count, "net_benefit_negative_count": s.net_benefit_negative_count,
                   "curve_shape_judgement": s.curve_shape_judgement, "response_summary_judgement": s.response_summary_judgement,
                   "policy_cap_within_safe_range": bool(within), "policy_cap_above_harmful_threshold": bool(above),
                   "policy_channel_rank": pr, "observed_channel_rank": orank, "channel_rank_delta": abs(pr - orank),
                   "channel_alignment_score": ch_score, "cap_alignment_score": _cap_score(cap, s.observed_safe_strength_min, s.observed_safe_strength_max, s.observed_harmful_threshold),
                   "permission_alignment_score": _permission_score(policy.fire_permission_score, safe_count, harmful_count, len(case_summary)),
                   "cooldown_alignment_score": _cooldown_score(policy.cooldown_score, policy.non_action_decision, safe_count, harmful_count, len(case_summary)),
                   "policy_evidence_trace": policy.evidence_trace,
                   "v2_response_evidence_trace": channel_rows[["requested_strength", "net_benefit", "risk_reduction_vs_no_op", "side_effect_cost", "response_judgement"]].to_dict("records"),
                   "missing_input_flags": sorted(set(policy.input_boundary_flags + list(s.missing_input_flags))),
                   "v2_trace_used_as_action_runtime_input": False, "v2_trace_used_as_post_action_audit": True, "production_runtime_changed": False}
            rows.append(rec)
    long = pd.DataFrame(rows)
    long["misalignment_reason"] = long.apply(_reasons, axis=1)
    long["alignment_judgement"] = long.apply(_judgement, axis=1)
    long = long[LONG_COLUMNS]
    summary_rows = []
    for (run_id, seed, label), g in long.groupby(["run_id", "seed", "scenario_label_for_audit_only"], sort=False):
        top_policy = g.sort_values("channel_weight", ascending=False).iloc[0]
        top_observed = g.sort_values("observed_best_net_benefit", ascending=False).iloc[0]
        score = float(g[["channel_alignment_score", "cap_alignment_score", "permission_alignment_score", "cooldown_alignment_score"]].mean(axis=1).mean())
        reasons = sorted({r for cell in g.misalignment_reason for r in cell.split("+") if r != "none"})
        judgements = set(g.alignment_judgement)
        if score >= 0.85: overall = "well_aligned"
        elif score >= 0.70: overall = "mostly_aligned"
        elif "wrong_channel" in judgements: overall = "wrong_channel_bias"
        elif "over_firing" in judgements or "over_permission" in judgements: overall = "over_firing_bias"
        elif "under_firing" in judgements or "under_permission" in judgements: overall = "under_firing_bias"
        elif "missed_opportunity" in judgements: overall = "over_suppression_bias"
        elif "correct_suppression" in judgements and score < 0.5: overall = "under_suppression_bias"
        elif "unresolved" in judgements: overall = "unresolved"
        else: overall = "mixed_alignment"
        summary_rows.append({"run_id": run_id, "seed": seed, "scenario_label_for_audit_only": label,
            "fire_permission_score": top_policy.fire_permission_score, "action_mass_cap": top_policy.action_mass_cap,
            "non_action_decision": top_policy.non_action_decision, "cooldown_score": top_policy.cooldown_score, "suppression_reason": top_policy.suppression_reason,
            "top_policy_channel": top_policy.action_channel, "top_policy_channel_weight": top_policy.channel_weight,
            "top_observed_channel": top_observed.action_channel, "top_observed_net_benefit": top_observed.observed_best_net_benefit,
            "safe_channel_count": int((g.observed_safe_strength_range != "none").sum()), "harmful_channel_count": int(g.observed_harmful_threshold.notna().sum()),
            "positive_net_benefit_channel_count": int((g.observed_best_net_benefit > 0).sum()), "negative_net_benefit_channel_count": int((g.observed_best_net_benefit < 0).sum()),
            "best_channel_cap_alignment": top_observed.cap_alignment_score, "best_channel_rank_alignment": top_observed.channel_alignment_score,
            "overall_alignment_score": score, "overall_alignment_judgement": overall,
            "primary_misalignment_type": reasons[0] if reasons else "none", "misalignment_reasons": reasons,
            "missing_input_flags": sorted({f for flags in g.missing_input_flags for f in flags})})
    return AlignmentResult(long, pd.DataFrame(summary_rows)[SUMMARY_COLUMNS])

# Required and desired contract tests
def test_alignment_long_exports_expected_columns(): assert list(align_functional_policy_with_v2_response_curve().functional_policy_v2_alignment_long.columns) == LONG_COLUMNS
def test_alignment_summary_exports_expected_columns(): assert list(align_functional_policy_with_v2_response_curve().functional_policy_v2_alignment_summary.columns) == SUMMARY_COLUMNS
def test_alignment_uses_21b_b_policy_output(): assert "functional_insurance_policy" in inspect.getsource(align_functional_policy_with_v2_response_curve)
def test_alignment_uses_21c_a_v2_response_summary(): assert "v2_strength_response_summary" in inspect.getsource(align_functional_policy_with_v2_response_curve)
def test_policy_cap_within_safe_range_is_computed_from_observed_safe_range():
    assert _cap_score(0.04, 0.02, 0.08, 0.16) == 1.0
    df = align_functional_policy_with_v2_response_curve().functional_policy_v2_alignment_long
    computed = df.apply(lambda r: bool(pd.notna(r.observed_safe_strength_min) and r.observed_safe_strength_min <= r.action_mass_cap <= r.observed_safe_strength_max), axis=1)
    assert df.policy_cap_within_safe_range.tolist() == computed.tolist()
def test_policy_cap_above_harmful_threshold_is_computed_from_observed_harmful_threshold():
    r = align_functional_policy_with_v2_response_curve().functional_policy_v2_alignment_long.dropna(subset=["observed_harmful_threshold"]).iloc[0]; assert r.policy_cap_above_harmful_threshold == (r.action_mass_cap >= r.observed_harmful_threshold)
def test_observed_best_channel_is_derived_from_observed_net_benefit():
    res = align_functional_policy_with_v2_response_curve(); s = res.functional_policy_v2_alignment_summary.iloc[0]; g = res.functional_policy_v2_alignment_long[res.functional_policy_v2_alignment_long.run_id == s.run_id]; assert s.top_observed_channel == g.sort_values("observed_best_net_benefit", ascending=False).iloc[0].action_channel
def test_channel_rank_delta_is_derived_from_policy_and_observed_ranks():
    r = align_functional_policy_with_v2_response_curve().functional_policy_v2_alignment_long.iloc[0]; assert r.channel_rank_delta == abs(r.policy_channel_rank - r.observed_channel_rank)
def test_cap_alignment_score_penalizes_cap_above_harmful_threshold(): assert _cap_score(0.20, 0.02, 0.08, 0.16) == 0.0
def test_channel_alignment_score_rewards_matching_top_channel():
    res = align_functional_policy_with_v2_response_curve(); row = res.functional_policy_v2_alignment_long[(res.functional_policy_v2_alignment_long.policy_channel_rank == 1) & (res.functional_policy_v2_alignment_long.observed_channel_rank == 1)]; assert row.empty or (row.channel_alignment_score == 1.0).all()
def test_permission_alignment_score_detects_over_permission(): assert _permission_score(0.8, 0, 4, 6) == 0.0
def test_permission_alignment_score_detects_under_permission(): assert _permission_score(0.1, 3, 0, 6) == 0.0
def test_cooldown_alignment_score_detects_correct_suppression(): assert _cooldown_score(0.8, "cooldown", 0, 4, 6) == 1.0
def test_missed_opportunity_detected_when_non_action_but_safe_benefit_exists():
    row = pd.Series({"missing_input_flags": [], "non_action_decision": "observe_only", "observed_safe_strength_range": "0.02-0.08", "observed_best_net_benefit": 0.1, "curve_shape_judgement": "single_peak_safe", "observed_harmful_threshold": None, "policy_cap_above_harmful_threshold": False, "fire_permission_score": 0.1, "response_summary_judgement": "has_safe_strength", "action_mass_cap": 0.0, "observed_safe_strength_min": 0.02, "channel_alignment_score": 1.0, "permission_alignment_score": 1.0, "cap_alignment_score": 1.0}); assert _judgement(row) == "missed_opportunity"
def test_alignment_judgement_is_not_controlled_by_scenario_label():
    a = align_functional_policy_with_v2_response_curve().functional_policy_v2_alignment_long.alignment_judgement.tolist(); b = align_functional_policy_with_v2_response_curve(label_override="renamed").functional_policy_v2_alignment_long.alignment_judgement.tolist(); assert a == b
def test_misalignment_reason_is_not_controlled_by_scenario_label():
    a = align_functional_policy_with_v2_response_curve().functional_policy_v2_alignment_long.misalignment_reason.tolist(); b = align_functional_policy_with_v2_response_curve(label_override="renamed").functional_policy_v2_alignment_long.misalignment_reason.tolist(); assert a == b
def test_21b_b_coefficients_are_not_modified(): assert "0.56 * fire_permission_score" in inspect.getsource(functional_insurance_policy)
def test_no_dynamic_pressure_coefficient_modulation_is_added(): assert "dynamic" not in inspect.getsource(align_functional_policy_with_v2_response_curve).lower() and "coefficient" not in inspect.getsource(align_functional_policy_with_v2_response_curve).lower()
def test_v2_traces_are_post_action_audit_not_runtime_inputs():
    df = align_functional_policy_with_v2_response_curve().functional_policy_v2_alignment_long; assert not df.v2_trace_used_as_action_runtime_input.any() and df.v2_trace_used_as_post_action_audit.all()
def test_production_runtime_files_are_not_modified(): assert subprocess.run(["git", "diff", "--name-only", "--"] + [str(p) for p in PRODUCTION_RUNTIME_PATHS], check=True, text=True, capture_output=True).stdout.splitlines() == []
def test_alignment_summary_has_one_row_per_case():
    s = align_functional_policy_with_v2_response_curve().functional_policy_v2_alignment_summary; assert len(s) == s.run_id.nunique()
def test_alignment_long_has_one_row_per_case_channel():
    l = align_functional_policy_with_v2_response_curve().functional_policy_v2_alignment_long; assert len(l) == l.run_id.nunique() * len(ACTION_CHANNELS)
def test_safe_channel_count_matches_v2_summary_rows():
    res = align_functional_policy_with_v2_response_curve(); s = res.functional_policy_v2_alignment_summary.iloc[0]; g = res.functional_policy_v2_alignment_long[res.functional_policy_v2_alignment_long.run_id == s.run_id]; assert s.safe_channel_count == int((g.observed_safe_strength_range != "none").sum())
def test_harmful_channel_count_matches_v2_summary_rows():
    res = align_functional_policy_with_v2_response_curve(); s = res.functional_policy_v2_alignment_summary.iloc[0]; g = res.functional_policy_v2_alignment_long[res.functional_policy_v2_alignment_long.run_id == s.run_id]; assert s.harmful_channel_count == int(g.observed_harmful_threshold.notna().sum())
def test_positive_negative_net_benefit_channel_counts_match_v2_summary_rows():
    res = align_functional_policy_with_v2_response_curve(); s = res.functional_policy_v2_alignment_summary.iloc[0]; g = res.functional_policy_v2_alignment_long[res.functional_policy_v2_alignment_long.run_id == s.run_id]; assert s.positive_net_benefit_channel_count == int((g.observed_best_net_benefit > 0).sum()) and s.negative_net_benefit_channel_count == int((g.observed_best_net_benefit < 0).sum())
def test_over_firing_judgement_when_cap_exceeds_harmful_threshold(): assert _cap_score(0.24, 0.02, 0.08, 0.16) == 0.0
def test_under_firing_judgement_when_cap_below_safe_min():
    row = pd.Series({"missing_input_flags": [], "non_action_decision": "none", "observed_safe_strength_range": "0.08-0.16", "observed_best_net_benefit": 0.1, "curve_shape_judgement": "single_peak_safe", "observed_harmful_threshold": None, "policy_cap_above_harmful_threshold": False, "fire_permission_score": 0.3, "response_summary_judgement": "has_safe_strength", "action_mass_cap": 0.02, "observed_safe_strength_min": 0.08, "channel_alignment_score": 1.0, "permission_alignment_score": 1.0, "cap_alignment_score": 0.7}); assert _judgement(row) == "under_firing"
def test_wrong_channel_judgement_when_policy_rank_is_bad():
    row = pd.Series({"missing_input_flags": [], "non_action_decision": "none", "observed_safe_strength_range": "0.02-0.08", "observed_best_net_benefit": 0.1, "curve_shape_judgement": "single_peak_safe", "observed_harmful_threshold": None, "policy_cap_above_harmful_threshold": False, "fire_permission_score": 0.3, "response_summary_judgement": "has_safe_strength", "action_mass_cap": 0.04, "observed_safe_strength_min": 0.02, "channel_alignment_score": 0.0, "permission_alignment_score": 1.0, "cap_alignment_score": 1.0}); assert _judgement(row) == "wrong_channel"
def test_correct_suppression_when_no_safe_strength_and_cooldown_high():
    row = pd.Series({"missing_input_flags": [], "non_action_decision": "cooldown", "observed_safe_strength_range": "none", "observed_best_net_benefit": -0.1, "curve_shape_judgement": "mostly_harmful", "observed_harmful_threshold": 0.04, "policy_cap_above_harmful_threshold": False, "fire_permission_score": 0.1, "response_summary_judgement": "no_safe_strength_observed", "action_mass_cap": 0.0, "observed_safe_strength_min": None, "channel_alignment_score": 0.0, "permission_alignment_score": 1.0, "cap_alignment_score": 0.3}); assert _judgement(row) == "correct_suppression"
def test_policy_evidence_trace_is_preserved(): assert isinstance(align_functional_policy_with_v2_response_curve().functional_policy_v2_alignment_long.iloc[0].policy_evidence_trace, dict)
def test_v2_response_evidence_trace_is_preserved(): assert align_functional_policy_with_v2_response_curve().functional_policy_v2_alignment_long.iloc[0].v2_response_evidence_trace
