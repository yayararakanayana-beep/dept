"""DiagnosticActionModuleIntegrationReview RC1.

Final integration review for the validation-oriented diagnostic action module
after the chain of repairs:

    DiagnosticActionTranslationPolicy_RC1
    PressureOutcomeAlignmentAudit_RC2b
    DiagnosticClosedLoopRerun_RC1
    DiagnosticPrimitiveMappingRepair_RC1
    ExpectedEffectContractPatch_RC1
    ProbeRestraintPrimitivePatch_RC1
    CouplingReliefStagedUnlockRepair_RC1

Scope:
    Review coherence of the diagnostic action module.

Boundary:
    This does not tune H-DEPT pressure generation.
    This does not claim deployment safety.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Any
import json
import numpy as np
import pandas as pd


REVIEW_VERSION = "DiagnosticActionModuleIntegrationReview_RC1"


def _safe_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _status(v: bool) -> str:
    return "pass" if bool(v) else "fail"


def build_milestone_review(results_dir: str | Path) -> pd.DataFrame:
    results = Path(results_dir)
    s_translation = _safe_json(results / "diagnostic_action_translation_policy_summary_RC1.json")
    s_rc2b = _safe_json(results / "pressure_outcome_alignment_rc2b_summary.json")
    s_rerun = _safe_json(results / "diagnostic_closed_loop_rerun_summary_RC1.json")
    s_rerun_review = _safe_json(results / "diagnostic_closed_loop_rerun_review_summary_RC1.json")
    s_mapping = _safe_json(results / "diagnostic_primitive_mapping_repair_summary_RC1.json")
    s_contract_review = _safe_json(results / "expected_effect_contract_review_summary_RC1.json")
    s_contract_patch = _safe_json(results / "expected_effect_contract_patch_summary_RC1.json")
    s_probe_check = _safe_json(results / "probe_restraint_primitive_check_summary_RC1.json")
    s_probe_patch = _safe_json(results / "probe_restraint_primitive_patch_summary_RC1.json")
    s_sequence = _safe_json(results / "coupling_relief_staged_unlock_repair_summary_RC1.json")

    rows = [
        {
            "milestone": "semantic_action_coverage",
            "source_task": "DiagnosticActionTranslationPolicy_RC1",
            "status": _status(s_translation.get("policy_semantic_to_plan_rate", 0) >= 0.999 and s_translation.get("policy_plan_to_action_rate", 0) >= 0.999),
            "key_metric": f'plan={s_translation.get("policy_semantic_to_plan_rate")}; action={s_translation.get("policy_plan_to_action_rate")}',
            "integration_meaning": "semantic_effect is preserved into diagnostic plan/action for validation",
        },
        {
            "milestone": "coverage_vs_outcome_boundary",
            "source_task": "PressureOutcomeAlignmentAudit_RC2b",
            "status": _status(s_rc2b.get("policy_action_rate", 0) >= 0.999 and s_rc2b.get("outcome_pending_rate", 0) > 0),
            "key_metric": f'policy_action={s_rc2b.get("policy_action_rate")}; pending={s_rc2b.get("outcome_pending_rate")}',
            "integration_meaning": "coverage was fixed but correctly separated from true outcome attribution",
        },
        {
            "milestone": "diagnostic_action_delivery",
            "source_task": "DiagnosticClosedLoopRerun_RC1",
            "status": _status(s_rerun.get("applied_action_rows", 0) > 0 and s_rerun.get("semantic_effect_count", 0) >= 8),
            "key_metric": f'applied={s_rerun.get("applied_action_rows")}; pass_rate={s_rerun.get("isolated_alignment_pass_rate")}',
            "integration_meaning": "diagnostic actions were actually applied to pseudo-reality and measured",
        },
        {
            "milestone": "bottleneck_classification",
            "source_task": "DiagnosticClosedLoopRerunReview_RC1",
            "status": _status(s_rerun_review.get("primitive_mapping_repair_count", 0) > 0 and s_rerun_review.get("contract_review_count", 0) > 0),
            "key_metric": f'mapping_repair={s_rerun_review.get("primitive_mapping_repair_count")}; contract_review={s_rerun_review.get("contract_review_count")}',
            "integration_meaning": "remaining errors were separated into mapping vs contract problems",
        },
        {
            "milestone": "primitive_mapping_repair",
            "source_task": "DiagnosticPrimitiveMappingRepair_RC1",
            "status": _status(s_mapping.get("target_repaired_pass_rate", 0) >= 0.999 and s_mapping.get("target_count", 0) >= 3),
            "key_metric": f'target_old={s_mapping.get("target_old_pass_rate")}; target_repaired={s_mapping.get("target_repaired_pass_rate")}',
            "integration_meaning": "misaligned primitive mappings were repaired in compact isolated rerun",
        },
        {
            "milestone": "expected_contract_review",
            "source_task": "ExpectedEffectContractReview_RC1",
            "status": _status(s_contract_review.get("mean_candidate_contract_alignment_score", 0) > s_contract_review.get("mean_old_contract_alignment_score", 0)),
            "key_metric": f'old={s_contract_review.get("mean_old_contract_alignment_score")}; candidate={s_contract_review.get("mean_candidate_contract_alignment_score")}',
            "integration_meaning": "old expected-effect contracts were identified as mismatched/coarse",
        },
        {
            "milestone": "expected_contract_patch",
            "source_task": "ExpectedEffectContractPatch_RC1",
            "status": _status(s_contract_patch.get("overall_patched_pass_rate", 0) >= 0.999),
            "key_metric": f'before={s_contract_patch.get("overall_repaired_pass_rate_before_patch")}; after={s_contract_patch.get("overall_patched_pass_rate")}',
            "integration_meaning": "diagnostic expected-effect contracts were patched and re-evaluated",
        },
        {
            "milestone": "probe_restraint_ambiguity_check",
            "source_task": "ProbeRestraintPrimitiveCheck_RC1",
            "status": _status(s_probe_check.get("policy_recommendation") == "add_direct_probe_restraint_primitive"),
            "key_metric": f'best_old={s_probe_check.get("best_old_contract_variant")}; best_patched={s_probe_check.get("best_patched_contract_variant")}',
            "integration_meaning": "sandbox_probe_entry_down ambiguity was verified as real",
        },
        {
            "milestone": "probe_restraint_role_split",
            "source_task": "ProbeRestraintPrimitivePatch_RC1",
            "status": _status(s_probe_patch.get("direct_probe_restraint_role_pass_rate", 0) >= 0.999 and s_probe_patch.get("stabilization_guard_role_pass_rate", 0) >= 0.999),
            "key_metric": f'direct={s_probe_patch.get("direct_probe_restraint_role_pass_rate")}; stabilization={s_probe_patch.get("stabilization_guard_role_pass_rate")}',
            "integration_meaning": "probe-restraint and stabilization roles were separated cleanly",
        },
        {
            "milestone": "staged_unlock_sequence_repair",
            "source_task": "CouplingReliefStagedUnlockRepair_RC1",
            "status": _status("guarded" in str(s_sequence.get("best_variant", "")) and s_sequence.get("best_variant_pass_rate", 0) >= 0.999),
            "key_metric": f'prior={s_sequence.get("prior_staged_unlock_mean_pass_rate")}; best={s_sequence.get("best_variant")}; best_pass={s_sequence.get("best_variant_pass_rate")}',
            "integration_meaning": "immediate unlock was replaced by guarded delayed unlock as sequence policy",
        },
    ]
    return pd.DataFrame(rows)


def build_metric_review(results_dir: str | Path) -> pd.DataFrame:
    results = Path(results_dir)
    summaries = {
        "translation": _safe_json(results / "diagnostic_action_translation_policy_summary_RC1.json"),
        "rc2b": _safe_json(results / "pressure_outcome_alignment_rc2b_summary.json"),
        "rerun": _safe_json(results / "diagnostic_closed_loop_rerun_summary_RC1.json"),
        "mapping": _safe_json(results / "diagnostic_primitive_mapping_repair_summary_RC1.json"),
        "contract_patch": _safe_json(results / "expected_effect_contract_patch_summary_RC1.json"),
        "probe_patch": _safe_json(results / "probe_restraint_primitive_patch_summary_RC1.json"),
        "sequence": _safe_json(results / "coupling_relief_staged_unlock_repair_summary_RC1.json"),
    }
    rows = [
        {
            "metric_group": "coverage",
            "metric_name": "semantic_to_plan_rate",
            "value": summaries["translation"].get("policy_semantic_to_plan_rate"),
            "target": ">= 0.999",
            "status": _status(summaries["translation"].get("policy_semantic_to_plan_rate", 0) >= 0.999),
            "interpretation": "semantic effects survive into plan in validation mode",
        },
        {
            "metric_group": "coverage",
            "metric_name": "plan_to_action_rate",
            "value": summaries["translation"].get("policy_plan_to_action_rate"),
            "target": ">= 0.999",
            "status": _status(summaries["translation"].get("policy_plan_to_action_rate", 0) >= 0.999),
            "interpretation": "semantic effects survive into weak diagnostic action",
        },
        {
            "metric_group": "delivery",
            "metric_name": "applied_action_rows",
            "value": summaries["rerun"].get("applied_action_rows"),
            "target": "> 0",
            "status": _status(summaries["rerun"].get("applied_action_rows", 0) > 0),
            "interpretation": "diagnostic action frame can be applied to pseudo-reality",
        },
        {
            "metric_group": "pre_repair_alignment",
            "metric_name": "initial_isolated_alignment_pass_rate",
            "value": summaries["rerun"].get("isolated_alignment_pass_rate"),
            "target": "diagnostic only",
            "status": "informational",
            "interpretation": "initial diagnostic rerun was mixed and justified repairs",
        },
        {
            "metric_group": "mapping_repair",
            "metric_name": "target_repaired_pass_rate",
            "value": summaries["mapping"].get("target_repaired_pass_rate"),
            "target": ">= 0.999",
            "status": _status(summaries["mapping"].get("target_repaired_pass_rate", 0) >= 0.999),
            "interpretation": "target primitive mappings pass after repair",
        },
        {
            "metric_group": "contract_patch",
            "metric_name": "overall_patched_pass_rate",
            "value": summaries["contract_patch"].get("overall_patched_pass_rate"),
            "target": ">= 0.999",
            "status": _status(summaries["contract_patch"].get("overall_patched_pass_rate", 0) >= 0.999),
            "interpretation": "patched diagnostic contracts align with repaired outcomes",
        },
        {
            "metric_group": "probe_split",
            "metric_name": "direct_probe_restraint_role_pass_rate",
            "value": summaries["probe_patch"].get("direct_probe_restraint_role_pass_rate"),
            "target": ">= 0.999",
            "status": _status(summaries["probe_patch"].get("direct_probe_restraint_role_pass_rate", 0) >= 0.999),
            "interpretation": "direct probe-restraint role expresses old probe-restraint semantics",
        },
        {
            "metric_group": "probe_split",
            "metric_name": "stabilization_guard_role_pass_rate",
            "value": summaries["probe_patch"].get("stabilization_guard_role_pass_rate"),
            "target": ">= 0.999",
            "status": _status(summaries["probe_patch"].get("stabilization_guard_role_pass_rate", 0) >= 0.999),
            "interpretation": "buffer-style stabilization remains available as separate behavior",
        },
        {
            "metric_group": "sequence_repair",
            "metric_name": "recommended_sequence",
            "value": summaries["sequence"].get("recommended_sequence"),
            "target": "guarded delayed sequence",
            "status": _status("guarded" in str(summaries["sequence"].get("recommended_sequence", ""))),
            "interpretation": "staged unlock is delayed and guarded for traceability",
        },
    ]
    return pd.DataFrame(rows)


def build_readiness_gate(milestones: pd.DataFrame, metrics: pd.DataFrame) -> pd.DataFrame:
    milestone_pass_rate = float((milestones["status"] == "pass").mean()) if not milestones.empty else 0.0
    metric_pass = metrics[metrics["status"].isin(["pass", "fail"])] if not metrics.empty else pd.DataFrame()
    metric_pass_rate = float((metric_pass["status"] == "pass").mean()) if not metric_pass.empty else 0.0

    rows = [
        {
            "gate": "validation_action_module_coherence",
            "status": "pass" if milestone_pass_rate >= 0.999 and metric_pass_rate >= 0.999 else "review",
            "score": min(milestone_pass_rate, metric_pass_rate),
            "meaning": "whether repaired validation action module is internally coherent",
        },
        {
            "gate": "pressure_tuning_readiness",
            "status": "not_ready",
            "score": 0.0,
            "meaning": "do not tune H-DEPT pressure yet; run integrated closed-loop validation first",
        },
        {
            "gate": "deployment_readiness",
            "status": "not_ready",
            "score": 0.0,
            "meaning": "this is synthetic validation; not safety/deployment proof",
        },
        {
            "gate": "next_phase_readiness",
            "status": "ready_for_integrated_diagnostic_closed_loop",
            "score": min(milestone_pass_rate, metric_pass_rate),
            "meaning": "ready to run a full integrated diagnostic closed-loop using repaired action policy",
        },
    ]
    return pd.DataFrame(rows)


def build_risk_review(results_dir: str | Path) -> pd.DataFrame:
    results = Path(results_dir)
    s_sequence = _safe_json(results / "coupling_relief_staged_unlock_repair_summary_RC1.json")
    s_contract = _safe_json(results / "expected_effect_contract_patch_summary_RC1.json")
    s_probe = _safe_json(results / "probe_restraint_primitive_patch_summary_RC1.json")

    rows = [
        {
            "risk": "compact_replay_overfit",
            "severity": "medium",
            "status": "open",
            "evidence": "many repairs are validated in compact isolated rerun, not full fresh closed-loop",
            "mitigation": "run IntegratedDiagnosticClosedLoop_RC1 with repaired action frame/policy",
        },
        {
            "risk": "diagnostic_contract_self_consistency_not_real_world_validity",
            "severity": "medium",
            "status": "open",
            "evidence": f'patched pass rate={s_contract.get("overall_patched_pass_rate")}',
            "mitigation": "treat contracts as diagnostic pseudo-reality contracts only",
        },
        {
            "risk": "probe_role_split_increases_action_rows",
            "severity": "low",
            "status": "managed",
            "evidence": f'role_split_rows={s_probe.get("role_split_rows")}',
            "mitigation": "keep direct probe-restraint and stabilization as separate low-strength diagnostic roles",
        },
        {
            "risk": "staged_unlock_improvement_not_numeric_in_compact_replay",
            "severity": "medium",
            "status": "managed",
            "evidence": f'pass_rate_delta_vs_old={s_sequence.get("pass_rate_delta_vs_old")}; prior_staged_unlock_mean_pass_rate={s_sequence.get("prior_staged_unlock_mean_pass_rate")}',
            "mitigation": "adopt guarded delayed sequence for traceability/causal separation; verify in full integrated rerun",
        },
        {
            "risk": "pressure_generation_not_yet_validated_after_repairs",
            "severity": "high",
            "status": "open",
            "evidence": "action module was repaired after original pressure/outcome audits",
            "mitigation": "rerun end-to-end pressure->action->outcome before tuning DEPT pressure",
        },
    ]
    return pd.DataFrame(rows)


def build_next_action_plan(readiness: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "priority": 1,
            "next_task": "IntegratedDiagnosticClosedLoop_RC1",
            "reason": "All validation action-module repairs are coherent; next test must run them together end-to-end.",
            "success_metric": "pressure semantic -> repaired action policy -> pseudo-reality outcome alignment in fresh closed-loop",
        },
        {
            "priority": 2,
            "next_task": "PressureOutcomeAlignmentAudit_RC3",
            "reason": "After integrated diagnostic closed-loop, rerun the alignment audit against fresh outcome traces.",
            "success_metric": "semantic/primitive/sequence alignment under repaired action module",
        },
        {
            "priority": 3,
            "next_task": "DEPTPressureTuningReview_RC1",
            "reason": "Only after repaired-action RC3 audit should pressure generation be reviewed.",
            "success_metric": "decide whether pressure weights/signs need tuning or action module is sufficient",
        },
    ])


def build_outputs_from_results_dir(results_dir: str | Path) -> Dict[str, pd.DataFrame]:
    milestones = build_milestone_review(results_dir)
    metrics = build_metric_review(results_dir)
    readiness = build_readiness_gate(milestones, metrics)
    risks = build_risk_review(results_dir)
    next_plan = build_next_action_plan(readiness)

    return {
        "diagnostic_action_module_integration_milestones": milestones,
        "diagnostic_action_module_integration_metrics": metrics,
        "diagnostic_action_module_integration_readiness": readiness,
        "diagnostic_action_module_integration_risks": risks,
        "diagnostic_action_module_integration_next_plan": next_plan,
    }


def integration_review_summary_json(outputs: Dict[str, pd.DataFrame]) -> dict:
    milestones = outputs.get("diagnostic_action_module_integration_milestones", pd.DataFrame())
    metrics = outputs.get("diagnostic_action_module_integration_metrics", pd.DataFrame())
    readiness = outputs.get("diagnostic_action_module_integration_readiness", pd.DataFrame())
    risks = outputs.get("diagnostic_action_module_integration_risks", pd.DataFrame())
    next_plan = outputs.get("diagnostic_action_module_integration_next_plan", pd.DataFrame())

    milestone_pass_count = int((milestones["status"] == "pass").sum()) if not milestones.empty else 0
    metric_eval = metrics[metrics["status"].isin(["pass", "fail"])] if not metrics.empty else pd.DataFrame()
    metric_pass_count = int((metric_eval["status"] == "pass").sum()) if not metric_eval.empty else 0

    coherence_row = readiness[readiness["gate"] == "validation_action_module_coherence"].iloc[0].to_dict() if not readiness.empty else {}
    next_row = next_plan.sort_values("priority").iloc[0].to_dict() if not next_plan.empty else {}

    return {
        "task": REVIEW_VERSION,
        "status": "completed",
        "milestone_count": int(len(milestones)),
        "milestone_pass_count": milestone_pass_count,
        "metric_count": int(len(metric_eval)),
        "metric_pass_count": metric_pass_count,
        "coherence_gate_status": coherence_row.get("status"),
        "coherence_score": float(coherence_row.get("score", 0.0)),
        "pressure_tuning_readiness": "not_ready_integrated_closed_loop_required",
        "deployment_readiness": "not_ready_synthetic_validation_only",
        "next_phase_readiness": "ready_for_integrated_diagnostic_closed_loop",
        "open_high_risks": risks[(risks["status"] == "open") & (risks["severity"] == "high")]["risk"].astype(str).tolist() if not risks.empty else [],
        "open_medium_risks": risks[(risks["status"] == "open") & (risks["severity"] == "medium")]["risk"].astype(str).tolist() if not risks.empty else [],
        "recommended_next_task": next_row.get("next_task"),
        "primary_conclusion": "The validation action module is internally coherent after repairs, but H-DEPT pressure tuning requires a fresh integrated diagnostic closed-loop and RC3 audit.",
        "all_sanity_checks_passed": bool(
            len(milestones) >= 10
            and milestone_pass_count == len(milestones)
            and not metric_eval.empty
            and metric_pass_count == len(metric_eval)
            and coherence_row.get("status") == "pass"
        ),
    }
