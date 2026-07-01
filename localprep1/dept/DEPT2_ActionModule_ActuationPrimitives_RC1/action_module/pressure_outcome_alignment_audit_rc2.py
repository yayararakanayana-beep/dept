"""PressureOutcomeAlignmentAudit RC2.

RC2 corrects the central weakness of RC1:

    RC1 compared approved pressure component sign directly to observed outcome.

That was too coarse because approved_* signs are parameter-adjustment signs, not
necessarily direct outcome directions.

RC2 uses the chain made visible by PressureSignSemanticsAudit_RC1:

    approved pressure component + sign
    -> semantic_effect
    -> translated primitive / sequence
    -> actual action channel
    -> observed outcome

Primary alignment:
    semantic_effect / primitive_sequence vs observed outcome

Secondary / diagnostic alignment:
    pressure component sign coverage and semantic-to-action survival

This audit does not tune DEPT. It identifies whether pressure intent survives
into the action layer and whether the resulting semantic / primitive effect
matches observed outcome.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import json
import pandas as pd
import numpy as np


AUDIT_VERSION = "PressureOutcomeAlignmentAudit_RC2"


@dataclass(frozen=True)
class AlignmentRC2Config:
    match_rate_threshold: float = 0.50
    min_action_mass_for_attribution: float = 1e-8


def _safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _bool_any(s: pd.Series) -> bool:
    if s.empty:
        return False
    return bool(s.fillna(False).astype(bool).any())


def _sum_numeric(s: pd.Series) -> float:
    return float(pd.to_numeric(s, errors="coerce").fillna(0.0).sum())


def _unique_join(s: pd.Series) -> str:
    vals = sorted({str(x) for x in s.dropna().tolist() if str(x) != "nan"})
    return ";".join(vals)


def build_semantic_primary_alignment(
    semantic_outcome: pd.DataFrame,
    semantic_chain: pd.DataFrame,
    cfg: AlignmentRC2Config | None = None,
) -> pd.DataFrame:
    """Primary semantic-effect outcome alignment with plan/action attribution."""
    cfg = cfg or AlignmentRC2Config()
    if semantic_outcome is None or semantic_outcome.empty:
        return pd.DataFrame()

    sem = semantic_outcome.copy()
    chain = semantic_chain.copy() if semantic_chain is not None else pd.DataFrame()

    key = ["run_seed", "run_scenario", "loop_step", "pressure_component", "component_direction", "semantic_effect"]
    if not chain.empty:
        chain_cov = chain.groupby(key, dropna=False, as_index=False).agg(
            semantic_to_plan_present=("semantic_to_plan_present", _bool_any),
            plan_to_action_present=("plan_to_action_present", _bool_any),
            planned_rows=("planned_rows", _sum_numeric),
            action_rows=("action_rows", _sum_numeric),
            action_mass=("action_mass", _sum_numeric),
            action_primitive=("action_primitive", _unique_join),
            primitive_sequence=("primitive_sequence", _unique_join),
            action_channel=("action_channel", _unique_join),
            suggested_control_route=("suggested_control_route", _unique_join),
        )
        sem = sem.merge(chain_cov, on=key, how="left")
    else:
        for c in ["semantic_to_plan_present", "plan_to_action_present"]:
            sem[c] = False
        for c in ["planned_rows", "action_rows", "action_mass"]:
            sem[c] = 0.0
        for c in ["action_primitive", "primitive_sequence", "action_channel", "suggested_control_route"]:
            sem[c] = ""

    sem["semantic_to_plan_present"] = sem["semantic_to_plan_present"].fillna(False).astype(bool)
    sem["plan_to_action_present"] = sem["plan_to_action_present"].fillna(False).astype(bool)
    sem["planned_rows"] = pd.to_numeric(sem["planned_rows"], errors="coerce").fillna(0.0)
    sem["action_rows"] = pd.to_numeric(sem["action_rows"], errors="coerce").fillna(0.0)
    sem["action_mass"] = pd.to_numeric(sem["action_mass"], errors="coerce").fillna(0.0)
    sem["semantic_match_rate"] = pd.to_numeric(sem["semantic_outcome_match_rate"], errors="coerce").fillna(0.0)

    def verdict(row: pd.Series) -> str:
        aligned = row["semantic_match_rate"] >= cfg.match_rate_threshold
        acted = bool(row["plan_to_action_present"]) and float(row["action_mass"]) > cfg.min_action_mass_for_attribution
        planned = bool(row["semantic_to_plan_present"])
        if aligned and acted:
            return "semantic_aligned_and_actuated"
        if aligned and planned and not acted:
            return "semantic_aligned_planned_not_actuated"
        if aligned and not planned:
            return "semantic_aligned_but_unattributed"
        if (not aligned) and acted:
            return "semantic_misaligned_despite_action"
        if (not aligned) and planned:
            return "semantic_misaligned_planned_not_actuated"
        return "semantic_misaligned_not_planned"

    sem["alignment_basis"] = "semantic_effect"
    sem["rc2_alignment_verdict"] = sem.apply(verdict, axis=1)
    sem["alignment_attribution_status"] = np.where(
        sem["plan_to_action_present"], "actuated",
        np.where(sem["semantic_to_plan_present"], "planned_not_actuated", "not_planned")
    )
    sem["primary_alignment_score"] = sem["semantic_match_rate"]
    sem["primary_alignment_pass"] = sem["primary_alignment_score"] >= cfg.match_rate_threshold
    sem["rc2_contract"] = AUDIT_VERSION + "__semantic_effect_expected_outcome_primary"

    keep = [
        "alignment_basis", "run_seed", "run_scenario", "loop_step",
        "pressure_component", "component_direction", "semantic_effect", "intent_family",
        "suggested_control_route", "semantic_to_plan_present", "plan_to_action_present",
        "planned_rows", "action_rows", "action_mass", "action_primitive",
        "primitive_sequence", "action_channel",
        "expected_feature_count", "primary_alignment_score", "primary_alignment_pass",
        "semantic_outcome_details", "semantic_outcome_verdict", "rc2_alignment_verdict",
        "alignment_attribution_status",
        "observed_delta_conflict", "observed_delta_uncertainty",
        "observed_delta_exploration", "observed_delta_overconvergence",
        "observed_delta_m_overall", "rc2_contract",
    ]
    for c in keep:
        if c not in sem.columns:
            sem[c] = "" if c in {"action_primitive", "primitive_sequence", "action_channel", "suggested_control_route"} else 0
    return sem[keep].copy()


def build_primitive_primary_alignment(
    primitive_outcome: pd.DataFrame,
    cfg: AlignmentRC2Config | None = None,
) -> pd.DataFrame:
    """Primary primitive/sequence outcome alignment for actually actuated rows."""
    cfg = cfg or AlignmentRC2Config()
    if primitive_outcome is None or primitive_outcome.empty:
        return pd.DataFrame()
    prim = primitive_outcome.copy()
    prim["primitive_match_rate"] = pd.to_numeric(prim["primitive_outcome_match_rate"], errors="coerce").fillna(0.0)
    prim["action_mass"] = pd.to_numeric(prim["action_mass"], errors="coerce").fillna(0.0)
    prim["action_rows"] = pd.to_numeric(prim["action_rows"], errors="coerce").fillna(0.0)

    def verdict(row: pd.Series) -> str:
        aligned = row["primitive_match_rate"] >= cfg.match_rate_threshold
        if aligned and row["action_mass"] > cfg.min_action_mass_for_attribution:
            return "primitive_aligned_and_actuated"
        if aligned:
            return "primitive_aligned_weak_action"
        if row["action_mass"] > cfg.min_action_mass_for_attribution:
            return "primitive_misaligned_despite_action"
        return "primitive_misaligned_weak_action"

    prim["alignment_basis"] = "primitive_sequence"
    prim["rc2_alignment_verdict"] = prim.apply(verdict, axis=1)
    prim["primary_alignment_score"] = prim["primitive_match_rate"]
    prim["primary_alignment_pass"] = prim["primary_alignment_score"] >= cfg.match_rate_threshold
    prim["rc2_contract"] = AUDIT_VERSION + "__primitive_sequence_expected_outcome_primary"

    out = pd.DataFrame({
        "alignment_basis": prim["alignment_basis"],
        "run_seed": prim["run_seed"],
        "run_scenario": prim["run_scenario"],
        "loop_step": prim["loop_step"],
        "dominant_pressure_component": prim["dominant_pressure_component"],
        "dominant_semantic_effect": prim["dominant_semantic_effect"],
        "action_primitive": prim["action_primitive"],
        "primitive_sequence": prim["primitive_sequence"],
        "action_channel": prim["action_channel"],
        "action_rows": prim["action_rows"],
        "action_mass": prim["action_mass"],
        "expected_feature_count": prim["expected_feature_count"],
        "primary_alignment_score": prim["primary_alignment_score"],
        "primary_alignment_pass": prim["primary_alignment_pass"],
        "primitive_outcome_details": prim["primitive_outcome_details"],
        "primitive_outcome_verdict": prim["primitive_outcome_verdict"],
        "rc2_alignment_verdict": prim["rc2_alignment_verdict"],
        "observed_delta_conflict": prim["observed_delta_conflict"],
        "observed_delta_uncertainty": prim["observed_delta_uncertainty"],
        "observed_delta_exploration": prim["observed_delta_exploration"],
        "observed_delta_overconvergence": prim["observed_delta_overconvergence"],
        "observed_delta_m_overall": prim["observed_delta_m_overall"],
        "rc2_contract": prim["rc2_contract"],
    })
    return out


def build_chain_coverage_summary(chain: pd.DataFrame) -> pd.DataFrame:
    if chain is None or chain.empty:
        return pd.DataFrame()
    c = chain.copy()
    c["semantic_to_plan_present"] = c["semantic_to_plan_present"].fillna(False).astype(bool)
    c["plan_to_action_present"] = c["plan_to_action_present"].fillna(False).astype(bool)
    return c.groupby(["run_scenario"], as_index=False).agg(
        semantic_chain_rows=("semantic_effect", "size"),
        unique_semantic_effects=("semantic_effect", "nunique"),
        semantic_to_plan_present_rate=("semantic_to_plan_present", "mean"),
        plan_to_action_present_rate=("plan_to_action_present", "mean"),
        total_planned_rows=("planned_rows", _sum_numeric),
        total_action_rows=("action_rows", _sum_numeric),
        total_action_mass=("action_mass", _sum_numeric),
    )


def summarize_semantic(sem: pd.DataFrame) -> pd.DataFrame:
    if sem is None or sem.empty:
        return pd.DataFrame()
    return sem.groupby(["semantic_effect", "intent_family"], as_index=False).agg(
        rows=("semantic_effect", "size"),
        mean_alignment_score=("primary_alignment_score", "mean"),
        alignment_pass_rate=("primary_alignment_pass", "mean"),
        semantic_to_plan_present_rate=("semantic_to_plan_present", "mean"),
        plan_to_action_present_rate=("plan_to_action_present", "mean"),
        mean_action_mass=("action_mass", "mean"),
        dominant_verdict=("rc2_alignment_verdict", lambda s: str(s.value_counts().index[0]) if len(s) else "none"),
    ).sort_values(["alignment_pass_rate", "plan_to_action_present_rate", "mean_alignment_score"], ascending=[True, True, True])


def summarize_primitive(prim: pd.DataFrame) -> pd.DataFrame:
    if prim is None or prim.empty:
        return pd.DataFrame()
    return prim.groupby(["action_primitive", "primitive_sequence", "action_channel"], as_index=False).agg(
        rows=("action_primitive", "size"),
        mean_alignment_score=("primary_alignment_score", "mean"),
        alignment_pass_rate=("primary_alignment_pass", "mean"),
        total_action_rows=("action_rows", "sum"),
        total_action_mass=("action_mass", "sum"),
        dominant_verdict=("rc2_alignment_verdict", lambda s: str(s.value_counts().index[0]) if len(s) else "none"),
    ).sort_values(["alignment_pass_rate", "mean_alignment_score"], ascending=[True, True])


def build_rc2_outputs_from_results_dir(results_dir: str | Path) -> Dict[str, pd.DataFrame]:
    results = Path(results_dir)
    sem_out = _safe_read_csv(results / "pressure_semantic_outcome_alignment_RC1.csv")
    prim_out = _safe_read_csv(results / "pressure_primitive_outcome_alignment_RC1.csv")
    chain = _safe_read_csv(results / "pressure_semantic_plan_action_chain_RC1.csv")

    sem_primary = build_semantic_primary_alignment(sem_out, chain)
    prim_primary = build_primitive_primary_alignment(prim_out)
    coverage = build_chain_coverage_summary(chain)
    sem_summary = summarize_semantic(sem_primary)
    prim_summary = summarize_primitive(prim_primary)

    review_rows = []
    if not sem_primary.empty:
        review_rows.append({
            "review_item": "semantic_primary_alignment",
            "value": float(sem_primary["primary_alignment_pass"].mean()),
            "interpretation": "semantic effect vs outcome pass rate",
            "rc2_status": "mixed" if 0.25 <= float(sem_primary["primary_alignment_pass"].mean()) <= 0.75 else "strong_or_weak_extreme",
        })
        review_rows.append({
            "review_item": "semantic_to_plan_coverage",
            "value": float(sem_primary["semantic_to_plan_present"].mean()),
            "interpretation": "share of semantic effects that survive into planning",
            "rc2_status": "coverage_bottleneck" if float(sem_primary["semantic_to_plan_present"].mean()) < 0.65 else "acceptable",
        })
        review_rows.append({
            "review_item": "plan_to_action_coverage",
            "value": float(sem_primary["plan_to_action_present"].mean()),
            "interpretation": "share of semantic effects that survive to actual action",
            "rc2_status": "major_action_bottleneck" if float(sem_primary["plan_to_action_present"].mean()) < 0.25 else "acceptable",
        })
    if not prim_primary.empty:
        review_rows.append({
            "review_item": "primitive_primary_alignment",
            "value": float(prim_primary["primary_alignment_pass"].mean()),
            "interpretation": "actuated primitive/sequence vs outcome pass rate",
            "rc2_status": "mixed" if 0.25 <= float(prim_primary["primary_alignment_pass"].mean()) <= 0.75 else "strong_or_weak_extreme",
        })
    rc2_review = pd.DataFrame(review_rows)

    return {
        "pressure_outcome_alignment_rc2_semantic_primary": sem_primary,
        "pressure_outcome_alignment_rc2_primitive_primary": prim_primary,
        "pressure_outcome_alignment_rc2_chain_coverage": coverage,
        "pressure_outcome_alignment_rc2_semantic_summary": sem_summary,
        "pressure_outcome_alignment_rc2_primitive_summary": prim_summary,
        "pressure_outcome_alignment_rc2_review": rc2_review,
    }


def rc2_summary_json(outputs: Dict[str, pd.DataFrame]) -> dict:
    sem = outputs.get("pressure_outcome_alignment_rc2_semantic_primary", pd.DataFrame())
    prim = outputs.get("pressure_outcome_alignment_rc2_primitive_primary", pd.DataFrame())
    coverage = outputs.get("pressure_outcome_alignment_rc2_chain_coverage", pd.DataFrame())
    sem_summary = outputs.get("pressure_outcome_alignment_rc2_semantic_summary", pd.DataFrame())
    prim_summary = outputs.get("pressure_outcome_alignment_rc2_primitive_summary", pd.DataFrame())
    review = outputs.get("pressure_outcome_alignment_rc2_review", pd.DataFrame())

    if sem.empty and prim.empty:
        return {
            "task": AUDIT_VERSION,
            "status": "empty",
            "all_sanity_checks_passed": False,
        }

    semantic_alignment_rate = float(sem["primary_alignment_pass"].mean()) if not sem.empty else 0.0
    semantic_action_coverage = float(sem["plan_to_action_present"].mean()) if not sem.empty else 0.0
    semantic_plan_coverage = float(sem["semantic_to_plan_present"].mean()) if not sem.empty else 0.0
    primitive_alignment_rate = float(prim["primary_alignment_pass"].mean()) if not prim.empty else 0.0

    if semantic_action_coverage < 0.25:
        tuning_readiness = "not_ready_action_coverage_bottleneck"
    elif semantic_alignment_rate < 0.50 or primitive_alignment_rate < 0.50:
        tuning_readiness = "not_ready_alignment_mixed"
    else:
        tuning_readiness = "candidate_ready_for_limited_pressure_tuning"

    return {
        "task": AUDIT_VERSION,
        "status": "completed",
        "semantic_primary_rows": int(len(sem)),
        "primitive_primary_rows": int(len(prim)),
        "semantic_alignment_rate": semantic_alignment_rate,
        "semantic_mean_alignment_score": float(sem["primary_alignment_score"].mean()) if not sem.empty else 0.0,
        "semantic_to_plan_present_rate": semantic_plan_coverage,
        "plan_to_action_present_rate": semantic_action_coverage,
        "primitive_alignment_rate": primitive_alignment_rate,
        "primitive_mean_alignment_score": float(prim["primary_alignment_score"].mean()) if not prim.empty else 0.0,
        "chain_coverage_rows": int(len(coverage)),
        "weakest_semantic_effects": sem_summary.head(8).to_dict(orient="records") if not sem_summary.empty else [],
        "weakest_primitives": prim_summary.head(8).to_dict(orient="records") if not prim_summary.empty else [],
        "review_items": review.to_dict(orient="records") if not review.empty else [],
        "dept_pressure_tuning_readiness": tuning_readiness,
        "primary_alignment_basis": "semantic_effect_and_primitive_sequence",
        "secondary_diagnostic_basis": "approved_pressure_sign_only_for_sign_semantics_not_direct_outcome",
        "all_sanity_checks_passed": bool(len(sem) > 0 and len(review) > 0),
    }
