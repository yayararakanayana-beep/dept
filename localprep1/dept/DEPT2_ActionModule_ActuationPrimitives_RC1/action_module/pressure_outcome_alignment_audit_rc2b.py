"""PressureOutcomeAlignmentAudit RC2b.

RC2b re-reads outcome alignment after DiagnosticActionTranslationPolicy_RC1.

Important boundary:
    DiagnosticActionTranslationPolicy_RC1 creates weak diagnostic action frames
    from existing semantic chains. These rescued diagnostic actions have not yet
    been re-injected into the pseudo-reality loop.

Therefore RC2b separates:

    1. coverage/alignment-readiness after diagnostic policy
    2. observed outcome attribution from existing RC2 logs
    3. pending outcome attribution that requires a closed-loop rerun

RC2b must not overclaim outcome improvement from actions that were not actually
executed in pseudo-reality.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import json
import numpy as np
import pandas as pd


AUDIT_VERSION = "PressureOutcomeAlignmentAudit_RC2b"


@dataclass(frozen=True)
class RC2bConfig:
    alignment_threshold: float = 0.50


def _safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _safe_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _key_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in ["run_seed", "run_scenario", "loop_step", "semantic_effect"] if c in df.columns]


def _merge_policy_with_rc2_semantic(policy_action: pd.DataFrame, rc2_semantic: pd.DataFrame) -> pd.DataFrame:
    if policy_action.empty:
        return pd.DataFrame()

    p = policy_action.copy()
    keys = _key_cols(p)

    if rc2_semantic.empty or not keys:
        p["rc2_primary_alignment_score"] = np.nan
        p["rc2_primary_alignment_pass"] = False
        p["rc2_alignment_verdict"] = "no_prior_rc2_semantic_row"
        p["observed_outcome_source"] = "missing_prior_rc2"
        return p

    keep_cols = keys + [
        c for c in [
            "primary_alignment_score",
            "primary_alignment_pass",
            "semantic_outcome_verdict",
            "rc2_alignment_verdict",
            "alignment_attribution_status",
            "observed_delta_conflict",
            "observed_delta_uncertainty",
            "observed_delta_exploration",
            "observed_delta_overconvergence",
            "observed_delta_m_overall",
            "semantic_outcome_details",
        ]
        if c in rc2_semantic.columns
    ]
    rc = rc2_semantic[keep_cols].copy()
    rc = rc.rename(columns={
        "primary_alignment_score": "rc2_primary_alignment_score",
        "primary_alignment_pass": "rc2_primary_alignment_pass",
        "semantic_outcome_verdict": "rc2_semantic_outcome_verdict",
        "rc2_alignment_verdict": "rc2_prior_alignment_verdict",
        "alignment_attribution_status": "rc2_alignment_attribution_status",
    })
    merged = p.merge(rc, on=keys, how="left")
    merged["observed_outcome_source"] = np.where(
        merged["rc2_primary_alignment_score"].notna(),
        "existing_rc2_trace_not_reexecuted",
        "missing_prior_rc2",
    )
    return merged


def _classify_attribution(row: pd.Series) -> str:
    if bool(row.get("original_plan_to_action_present", False)):
        return "observed_existing_action_attribution"
    if bool(row.get("semantic_retained_to_action_by_policy", False)):
        return "diagnostic_action_created_outcome_pending"
    return "not_actionable"


def _classify_rc2b_verdict(row: pd.Series, threshold: float) -> str:
    if row.get("outcome_attribution_status") == "diagnostic_action_created_outcome_pending":
        # Existing outcome may be present, but it is not the result of the newly
        # rescued diagnostic action. It must not be used as proof.
        return "coverage_fixed_outcome_pending"
    score = row.get("rc2_primary_alignment_score")
    if pd.isna(score):
        return "coverage_fixed_no_prior_outcome_row"
    if float(score) >= threshold:
        return "existing_action_aligned"
    return "existing_action_misaligned"


def build_rc2b_audit(
    policy_action: pd.DataFrame,
    policy_plan: pd.DataFrame,
    drop_reason: pd.DataFrame,
    rc2_semantic: pd.DataFrame,
    rc2_primitive: pd.DataFrame | None = None,
    cfg: RC2bConfig | None = None,
) -> Dict[str, pd.DataFrame]:
    cfg = cfg or RC2bConfig()
    merged = _merge_policy_with_rc2_semantic(policy_action, rc2_semantic)
    if merged.empty:
        empty = pd.DataFrame()
        return {
            "rc2b_semantic_policy_alignment": empty,
            "rc2b_coverage_delta": empty,
            "rc2b_outcome_attribution_status": empty,
            "rc2b_diagnostic_action_readiness": empty,
            "rc2b_next_closed_loop_requirements": empty,
        }

    merged["outcome_attribution_status"] = merged.apply(_classify_attribution, axis=1)
    merged["rc2b_alignment_verdict"] = merged.apply(lambda r: _classify_rc2b_verdict(r, cfg.alignment_threshold), axis=1)
    merged["rc2b_contract"] = AUDIT_VERSION + "__coverage_fixed_outcome_attribution_separated"

    semantic_policy = merged.copy()

    coverage_delta = pd.DataFrame([{
        "metric": "semantic_to_plan_rate",
        "before_policy": float(merged["original_semantic_to_plan_present"].mean()),
        "after_policy": float(merged["semantic_retained_to_plan_by_policy"].mean()),
        "delta": float(merged["semantic_retained_to_plan_by_policy"].mean() - merged["original_semantic_to_plan_present"].mean()),
        "interpretation": "diagnostic policy fixes plan coverage for validation",
    }, {
        "metric": "plan_to_action_rate",
        "before_policy": float(merged["original_plan_to_action_present"].mean()),
        "after_policy": float(merged["semantic_retained_to_action_by_policy"].mean()),
        "delta": float(merged["semantic_retained_to_action_by_policy"].mean() - merged["original_plan_to_action_present"].mean()),
        "interpretation": "diagnostic policy fixes weak-action survival for validation",
    }, {
        "metric": "observed_existing_action_attribution_rate",
        "before_policy": float(merged["original_plan_to_action_present"].mean()),
        "after_policy": float((merged["outcome_attribution_status"] == "observed_existing_action_attribution").mean()),
        "delta": 0.0,
        "interpretation": "actual observed outcome attribution does not improve until closed-loop rerun",
    }, {
        "metric": "outcome_pending_rate",
        "before_policy": 0.0,
        "after_policy": float((merged["outcome_attribution_status"] == "diagnostic_action_created_outcome_pending").mean()),
        "delta": float((merged["outcome_attribution_status"] == "diagnostic_action_created_outcome_pending").mean()),
        "interpretation": "new diagnostic actions require pseudo-reality rerun for true outcome measurement",
    }])

    outcome_status = merged.groupby(["outcome_attribution_status", "rc2b_alignment_verdict"], as_index=False).agg(
        rows=("semantic_effect", "size"),
        semantic_effects=("semantic_effect", "nunique"),
        mean_prior_alignment_score=("rc2_primary_alignment_score", "mean"),
        total_diagnostic_action_mass=("action_mass_after_policy", "sum"),
    )

    readiness = merged.groupby(["semantic_effect", "intent_family"], as_index=False).agg(
        rows=("semantic_effect", "size"),
        original_plan_rate=("original_semantic_to_plan_present", "mean"),
        original_action_rate=("original_plan_to_action_present", "mean"),
        policy_plan_rate=("semantic_retained_to_plan_by_policy", "mean"),
        policy_action_rate=("semantic_retained_to_action_by_policy", "mean"),
        outcome_pending_rate=("outcome_attribution_status", lambda s: float((s == "diagnostic_action_created_outcome_pending").mean())),
        existing_observed_action_rate=("outcome_attribution_status", lambda s: float((s == "observed_existing_action_attribution").mean())),
        mean_prior_alignment_score=("rc2_primary_alignment_score", "mean"),
        diagnostic_action_primitive=("diagnostic_action_primitive", lambda s: "|".join(sorted(set(s.dropna().astype(str))))),
        diagnostic_primitive_sequence=("diagnostic_primitive_sequence", lambda s: "|".join(sorted(set(s.dropna().astype(str))))),
        diagnostic_action_channel=("diagnostic_action_channel", lambda s: "|".join(sorted(set(s.dropna().astype(str))))),
        diagnostic_action_mass=("action_mass_after_policy", "sum"),
    )
    readiness["readiness_verdict"] = np.where(
        readiness["policy_action_rate"] >= 0.999,
        "ready_for_closed_loop_rerun",
        "not_ready_policy_coverage_missing",
    )

    requirements = pd.DataFrame([
        {
            "requirement": "rerun_closed_loop_with_diagnostic_policy",
            "reason": "New weak diagnostic actions were created after the original pseudo-reality trace; their outcomes are not yet observed.",
            "success_metric": "outcome_pending_rate should become observed_existing_action_attribution_rate after rerun",
            "priority": 1,
        },
        {
            "requirement": "preserve semantic trace ids through pseudo-reality",
            "reason": "Outcome must be attributable to semantic_effect / diagnostic_action_primitive.",
            "success_metric": "each diagnostic action row carries semantic_effect, primitive, action_channel, and trace id",
            "priority": 1,
        },
        {
            "requirement": "compare RC2 vs RC2b after rerun",
            "reason": "Coverage is fixed now; alignment must be tested with actual new outcomes.",
            "success_metric": "semantic alignment pass rate under diagnostic rerun; not just coverage rate",
            "priority": 2,
        },
        {
            "requirement": "do not tune DEPT pressure yet",
            "reason": "Coverage is fixed syntactically, but outcome attribution is pending.",
            "success_metric": "DEPT tuning readiness remains false until diagnostic rerun confirms alignment",
            "priority": 2,
        },
    ])

    return {
        "rc2b_semantic_policy_alignment": semantic_policy,
        "rc2b_coverage_delta": coverage_delta,
        "rc2b_outcome_attribution_status": outcome_status,
        "rc2b_diagnostic_action_readiness": readiness,
        "rc2b_next_closed_loop_requirements": requirements,
    }


def build_outputs_from_results_dir(results_dir: str | Path, cfg: RC2bConfig | None = None) -> Dict[str, pd.DataFrame]:
    results = Path(results_dir)
    return build_rc2b_audit(
        policy_action=_safe_read_csv(results / "diagnostic_action_translation_policy_action_frame_RC1.csv"),
        policy_plan=_safe_read_csv(results / "diagnostic_action_translation_policy_plan_RC1.csv"),
        drop_reason=_safe_read_csv(results / "diagnostic_action_translation_policy_drop_reason_RC1.csv"),
        rc2_semantic=_safe_read_csv(results / "pressure_outcome_alignment_rc2_semantic_primary.csv"),
        rc2_primitive=_safe_read_csv(results / "pressure_outcome_alignment_rc2_primitive_primary.csv"),
        cfg=cfg,
    )


def rc2b_summary_json(outputs: Dict[str, pd.DataFrame], diagnostic_policy_summary: dict | None = None) -> dict:
    semantic = outputs.get("rc2b_semantic_policy_alignment", pd.DataFrame())
    coverage = outputs.get("rc2b_coverage_delta", pd.DataFrame())
    status = outputs.get("rc2b_outcome_attribution_status", pd.DataFrame())
    readiness = outputs.get("rc2b_diagnostic_action_readiness", pd.DataFrame())

    if semantic.empty:
        return {
            "task": AUDIT_VERSION,
            "status": "empty",
            "all_sanity_checks_passed": False,
        }

    metric_map = {r["metric"]: r for _, r in coverage.iterrows()} if not coverage.empty else {}

    def get_metric(metric: str, key: str, default: float = 0.0) -> float:
        if metric in metric_map:
            return float(metric_map[metric].get(key, default))
        return default

    return {
        "task": AUDIT_VERSION,
        "status": "completed",
        "semantic_rows": int(len(semantic)),
        "semantic_effect_count": int(semantic["semantic_effect"].nunique()),
        "policy_plan_rate": get_metric("semantic_to_plan_rate", "after_policy"),
        "policy_action_rate": get_metric("plan_to_action_rate", "after_policy"),
        "original_plan_rate": get_metric("semantic_to_plan_rate", "before_policy"),
        "original_action_rate": get_metric("plan_to_action_rate", "before_policy"),
        "coverage_delta_plan": get_metric("semantic_to_plan_rate", "delta"),
        "coverage_delta_action": get_metric("plan_to_action_rate", "delta"),
        "observed_existing_action_attribution_rate": float((semantic["outcome_attribution_status"] == "observed_existing_action_attribution").mean()),
        "outcome_pending_rate": float((semantic["outcome_attribution_status"] == "diagnostic_action_created_outcome_pending").mean()),
        "existing_action_alignment_rate": float((semantic["rc2b_alignment_verdict"] == "existing_action_aligned").mean()),
        "coverage_fixed_outcome_pending_rate": float((semantic["rc2b_alignment_verdict"] == "coverage_fixed_outcome_pending").mean()),
        "mean_prior_alignment_score": float(semantic["rc2_primary_alignment_score"].mean()) if "rc2_primary_alignment_score" in semantic.columns else 0.0,
        "outcome_attribution_status": status.to_dict(orient="records") if not status.empty else [],
        "readiness_summary": readiness.to_dict(orient="records") if not readiness.empty else [],
        "diagnostic_policy_summary_status": diagnostic_policy_summary.get("status") if diagnostic_policy_summary else None,
        "dept_pressure_tuning_readiness": "not_ready_outcome_pending_requires_diagnostic_closed_loop_rerun",
        "next_recommended_task": "DiagnosticClosedLoopRerun_RC1",
        "rc2b_interpretation": "Coverage is fixed by policy; true outcome alignment requires rerunning pseudo-reality with diagnostic actions.",
        "all_sanity_checks_passed": bool(
            len(semantic) > 0
            and get_metric("semantic_to_plan_rate", "after_policy") >= 0.999
            and get_metric("plan_to_action_rate", "after_policy") >= 0.999
            and float((semantic["outcome_attribution_status"] == "diagnostic_action_created_outcome_pending").mean()) > 0.0
        ),
    }
