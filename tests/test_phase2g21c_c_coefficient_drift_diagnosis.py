"""Phase 2G-21C-C functional policy coefficient drift diagnosis.

Test-local diagnosis only: consumes 21C-B functional-policy × v2 response
alignment outputs and proposes coefficient-family drift hypotheses for 21C-D
validation. It does not alter coefficients, v2 dynamics, production runtime, or
canonical parameters.
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
    align_functional_policy_with_v2_response_curve,
)

PRODUCTION_RUNTIME_PATHS = [
    Path("localprep1/dept/DEPT2_ActionModule_ActuationPrimitives_RC1/pseudo_reality/asymmetric_game_v2.py"),
    Path("localprep1/dept/DEPT2_ActionModule_ActuationPrimitives_RC1/action_module.py"),
    Path("localprep1/dept/DEPT2_ActionModule_ActuationPrimitives_RC1/action_planner.py"),
]

MISALIGNMENT_REASON_TO_FAMILY = {
    "policy_cap_too_high": "action_mass_cap_family",
    "policy_cap_too_low": "action_mass_cap_family",
    "policy_channel_weight_mismatch": "channel_weight_family",
    "policy_permission_too_high": "fire_permission_family",
    "policy_permission_too_low": "fire_permission_family",
    "cooldown_too_strong": "cooldown_suppression_family",
    "cooldown_too_weak": "cooldown_suppression_family",
    "safe_range_absent": "safety_boundary_family",
    "harmful_threshold_low": "safety_boundary_family",
    "v2_curve_mostly_harmful": "safety_boundary_family",
    "v2_curve_mostly_no_effect": "opportunity_detection_family",
}

LONG_COLUMNS = [
    "run_id", "seed", "scenario_label_for_audit_only", "action_channel", "alignment_judgement", "misalignment_reason",
    "suspected_coefficient_family", "drift_direction", "suggested_adjustment_direction", "diagnosis_confidence", "safety_priority",
    "evidence_summary", "counter_evidence_summary", "policy_evidence_trace", "v2_response_evidence_trace", "missing_input_flags",
    "coefficient_changed", "production_runtime_changed", "canonical_writeback_performed", "requires_21c_d_validation",
]
SUMMARY_COLUMNS = [
    "run_id", "seed", "scenario_label_for_audit_only", "overall_alignment_judgement", "primary_misalignment_type", "suspected_coefficient_families",
    "dominant_drift_direction", "dominant_suggested_adjustment_direction", "diagnosis_confidence", "safety_priority",
    "evidence_summary", "counter_evidence_summary", "missing_input_flags", "coefficient_changed", "production_runtime_changed",
    "canonical_writeback_performed", "requires_21c_d_validation",
]
FAMILY_COLUMNS = [
    "suspected_coefficient_family", "row_count", "drift_directions", "suggested_adjustment_directions", "diagnosis_confidence",
    "safety_priority", "misalignment_reasons", "evidence_summary", "counter_evidence_summary", "coefficient_changed",
    "production_runtime_changed", "canonical_writeback_performed", "requires_21c_d_validation",
]

@dataclass(frozen=True)
class CoefficientDriftDiagnosisResult:
    functional_policy_coefficient_drift_diagnosis_long: pd.DataFrame
    functional_policy_coefficient_drift_diagnosis_summary: pd.DataFrame
    functional_policy_coefficient_family_summary: pd.DataFrame


def _split_reasons(cell: str) -> list[str]:
    return [r for r in str(cell).split("+") if r and r != "none"]


def _family_for_reason(reason: str) -> str:
    return MISALIGNMENT_REASON_TO_FAMILY.get(reason, "unresolved_family")


def _diagnose_reason(reason: str) -> tuple[str, str]:
    if reason in {"policy_cap_too_high", "policy_permission_too_high", "cooldown_too_weak", "harmful_threshold_low", "v2_curve_mostly_harmful", "safe_range_absent"}:
        return "too_aggressive", "decrease_or_tighten"
    if reason in {"policy_cap_too_low", "policy_permission_too_low", "cooldown_too_strong", "v2_curve_mostly_no_effect"}:
        return "too_conservative", "increase_or_relax"
    if reason == "policy_channel_weight_mismatch":
        return "misrouted", "rebalance_channel_weights"
    return "unresolved", "requires_more_evidence"


def _confidence(row: pd.Series, reasons: list[str]) -> str:
    if row.missing_input_flags or not reasons:
        return "low"
    strong = row.alignment_judgement in {"over_firing", "wrong_channel", "missed_opportunity", "over_permission", "under_permission", "under_firing"}
    return "high" if strong and len(reasons) >= 2 else "medium"


def _priority(row: pd.Series, reasons: list[str]) -> str:
    safety_reasons = {"policy_cap_too_high", "policy_permission_too_high", "cooldown_too_weak", "harmful_threshold_low", "v2_curve_mostly_harmful", "safe_range_absent"}
    opportunity_reasons = {"policy_cap_too_low", "policy_permission_too_low", "cooldown_too_strong", "v2_curve_mostly_no_effect"}
    has_safety = bool(safety_reasons.intersection(reasons)) or row.alignment_judgement in {"over_firing", "over_permission"}
    has_opportunity = bool(opportunity_reasons.intersection(reasons)) or row.alignment_judgement in {"missed_opportunity", "under_firing", "under_permission"}
    if has_safety and has_opportunity:
        return "mixed"
    if has_safety:
        return "safety_critical"
    if "policy_channel_weight_mismatch" in reasons or row.alignment_judgement == "wrong_channel":
        return "routing_accuracy"
    if has_opportunity:
        return "opportunity_recovery"
    return "unresolved"


def _evidence(row: pd.Series, reasons: list[str]) -> str:
    return (
        f"21C-B judgement={row.alignment_judgement}; reasons={reasons or ['none']}; "
        f"channel={row.action_channel}; cap_alignment={row.cap_alignment_score}; "
        f"channel_alignment={row.channel_alignment_score}; permission_alignment={row.permission_alignment_score}; "
        f"cooldown_alignment={row.cooldown_alignment_score}"
    )


def _counter_evidence(row: pd.Series, reasons: list[str]) -> str:
    counters = []
    if row.cap_alignment_score >= 0.5:
        counters.append("cap_not_fully_disconfirmed")
    if row.channel_alignment_score >= 0.5:
        counters.append("channel_not_fully_disconfirmed")
    if row.permission_alignment_score >= 0.5:
        counters.append("permission_not_fully_disconfirmed")
    if row.cooldown_alignment_score >= 0.5:
        counters.append("cooldown_not_fully_disconfirmed")
    if not reasons:
        counters.append("no_explicit_21c_b_misalignment_reason")
    return "; ".join(counters) if counters else "no_counter_evidence_in_alignment_row"


@lru_cache(maxsize=4)
def diagnose_coefficient_drift_from_alignment(*, label_override=None) -> CoefficientDriftDiagnosisResult:
    alignment = align_functional_policy_with_v2_response_curve(label_override=label_override)
    long_rows = []
    for _, row in alignment.functional_policy_v2_alignment_long.iterrows():
        reasons = _split_reasons(row.misalignment_reason)
        families = sorted({_family_for_reason(r) for r in reasons}) or ["no_drift_detected"]
        directions = sorted({_diagnose_reason(r)[0] for r in reasons}) or ["none"]
        suggestions = sorted({_diagnose_reason(r)[1] for r in reasons}) or ["no_adjustment_suggested"]
        long_rows.append({
            "run_id": row.run_id, "seed": row.seed, "scenario_label_for_audit_only": row.scenario_label_for_audit_only,
            "action_channel": row.action_channel, "alignment_judgement": row.alignment_judgement, "misalignment_reason": row.misalignment_reason,
            "suspected_coefficient_family": "+".join(families), "drift_direction": "+".join(directions),
            "suggested_adjustment_direction": "+".join(suggestions), "diagnosis_confidence": _confidence(row, reasons),
            "safety_priority": _priority(row, reasons), "evidence_summary": _evidence(row, reasons),
            "counter_evidence_summary": _counter_evidence(row, reasons), "policy_evidence_trace": row.policy_evidence_trace,
            "v2_response_evidence_trace": row.v2_response_evidence_trace, "missing_input_flags": row.missing_input_flags,
            "coefficient_changed": False, "production_runtime_changed": False, "canonical_writeback_performed": False,
            "requires_21c_d_validation": True,
        })
    long = pd.DataFrame(long_rows)[LONG_COLUMNS]

    summary_rows = []
    for _, srow in alignment.functional_policy_v2_alignment_summary.iterrows():
        g = long[long.run_id == srow.run_id]
        priorities = set(g.safety_priority)
        priority = "safety_critical" if "safety_critical" in priorities else ("routing_accuracy" if "routing_accuracy" in priorities else ("opportunity_recovery" if "opportunity_recovery" in priorities else "unresolved"))
        conf = "low" if (g.diagnosis_confidence == "low").any() else ("high" if (g.diagnosis_confidence == "high").any() else "medium")
        summary_rows.append({
            "run_id": srow.run_id, "seed": srow.seed, "scenario_label_for_audit_only": srow.scenario_label_for_audit_only,
            "overall_alignment_judgement": srow.overall_alignment_judgement, "primary_misalignment_type": srow.primary_misalignment_type,
            "suspected_coefficient_families": sorted({f for cell in g.suspected_coefficient_family for f in cell.split("+")}),
            "dominant_drift_direction": g.drift_direction.mode().iat[0], "dominant_suggested_adjustment_direction": g.suggested_adjustment_direction.mode().iat[0],
            "diagnosis_confidence": conf, "safety_priority": priority,
            "evidence_summary": " | ".join(g.evidence_summary.head(3)), "counter_evidence_summary": " | ".join(g.counter_evidence_summary.head(3)),
            "missing_input_flags": sorted({f for flags in g.missing_input_flags for f in flags}),
            "coefficient_changed": False, "production_runtime_changed": False, "canonical_writeback_performed": False, "requires_21c_d_validation": True,
        })
    summary = pd.DataFrame(summary_rows)[SUMMARY_COLUMNS]

    fam_rows = []
    exploded = long.assign(suspected_coefficient_family=long.suspected_coefficient_family.str.split("+")).explode("suspected_coefficient_family")
    for family, g in exploded.groupby("suspected_coefficient_family", sort=True):
        fam_rows.append({
            "suspected_coefficient_family": family, "row_count": len(g), "drift_directions": sorted(set(g.drift_direction)),
            "suggested_adjustment_directions": sorted(set(g.suggested_adjustment_direction)),
            "diagnosis_confidence": "low" if (g.diagnosis_confidence == "low").any() else ("high" if (g.diagnosis_confidence == "high").any() else "medium"),
            "safety_priority": "safety_critical" if (g.safety_priority == "safety_critical").any() else g.safety_priority.mode().iat[0],
            "misalignment_reasons": sorted({r for cell in g.misalignment_reason for r in _split_reasons(cell)}),
            "evidence_summary": " | ".join(g.evidence_summary.head(3)), "counter_evidence_summary": " | ".join(g.counter_evidence_summary.head(3)),
            "coefficient_changed": False, "production_runtime_changed": False, "canonical_writeback_performed": False, "requires_21c_d_validation": True,
        })
    family = pd.DataFrame(fam_rows)[FAMILY_COLUMNS]
    return CoefficientDriftDiagnosisResult(long, summary, family)


def test_diagnosis_long_exports_expected_columns(): assert list(diagnose_coefficient_drift_from_alignment().functional_policy_coefficient_drift_diagnosis_long.columns) == LONG_COLUMNS
def test_diagnosis_summary_exports_expected_columns(): assert list(diagnose_coefficient_drift_from_alignment().functional_policy_coefficient_drift_diagnosis_summary.columns) == SUMMARY_COLUMNS
def test_family_summary_exports_expected_columns(): assert list(diagnose_coefficient_drift_from_alignment().functional_policy_coefficient_family_summary.columns) == FAMILY_COLUMNS
def test_diagnosis_reads_21c_b_alignment_outputs(): assert "align_functional_policy_with_v2_response_curve" in inspect.getsource(diagnose_coefficient_drift_from_alignment)
def test_diagnosis_is_not_controlled_by_scenario_labels():
    a = diagnose_coefficient_drift_from_alignment().functional_policy_coefficient_drift_diagnosis_long.drop(columns=["scenario_label_for_audit_only"])
    b = diagnose_coefficient_drift_from_alignment(label_override="renamed").functional_policy_coefficient_drift_diagnosis_long.drop(columns=["scenario_label_for_audit_only"])
    pd.testing.assert_frame_equal(a, b)
def test_coefficients_and_production_runtime_are_not_modified():
    assert "0.56 * fire_permission_score" in inspect.getsource(functional_insurance_policy)
    assert subprocess.run(["git", "diff", "--name-only", "--"] + [str(p) for p in PRODUCTION_RUNTIME_PATHS], check=True, text=True, capture_output=True).stdout.splitlines() == []
def test_each_misalignment_reason_maps_to_expected_coefficient_family():
    for reason, family in MISALIGNMENT_REASON_TO_FAMILY.items(): assert _family_for_reason(reason) == family
def test_missing_inputs_reduce_confidence():
    row = pd.Series({"missing_input_flags": ["missing"], "alignment_judgement": "over_firing"})
    assert _confidence(row, ["policy_cap_too_high"]) == "low"
def test_harmful_threshold_and_over_firing_cases_receive_safety_critical_priority():
    row = pd.Series({"alignment_judgement": "over_firing"})
    assert _priority(row, ["harmful_threshold_low"]) == "safety_critical"
def test_opportunity_loss_cases_receive_opportunity_recovery_priority():
    row = pd.Series({"alignment_judgement": "missed_opportunity"})
    assert _priority(row, ["cooldown_too_strong"]) == "opportunity_recovery"
def test_channel_mismatch_receives_routing_accuracy_priority():
    row = pd.Series({"alignment_judgement": "wrong_channel"})
    assert _priority(row, ["policy_channel_weight_mismatch"]) == "routing_accuracy"
def test_all_rows_require_21c_d_validation():
    res = diagnose_coefficient_drift_from_alignment()
    assert res.functional_policy_coefficient_drift_diagnosis_long.requires_21c_d_validation.all()
    assert res.functional_policy_coefficient_drift_diagnosis_summary.requires_21c_d_validation.all()
    assert res.functional_policy_coefficient_family_summary.requires_21c_d_validation.all()
def test_no_coefficient_change_runtime_change_or_canonical_writeback_occurs():
    for df in [
        diagnose_coefficient_drift_from_alignment().functional_policy_coefficient_drift_diagnosis_long,
        diagnose_coefficient_drift_from_alignment().functional_policy_coefficient_drift_diagnosis_summary,
        diagnose_coefficient_drift_from_alignment().functional_policy_coefficient_family_summary,
    ]:
        assert not df.coefficient_changed.any()
        assert not df.production_runtime_changed.any()
        assert not df.canonical_writeback_performed.any()
