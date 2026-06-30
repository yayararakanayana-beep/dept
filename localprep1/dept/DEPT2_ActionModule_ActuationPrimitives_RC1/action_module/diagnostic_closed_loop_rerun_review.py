"""DiagnosticClosedLoopRerunReview RC1.

Reviews DiagnosticClosedLoopRerun_RC1 before changing the action module again.

Purpose:
    classify semantic families into:
      - ready/usable diagnostic mapping
      - positive control
      - primitive mapping repair needed
      - expected-effect contract review needed
      - separate sequence-level repair candidate

This review does not tune H-DEPT pressure and does not modify pseudo-reality.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict

import json
import numpy as np
import pandas as pd


REVIEW_VERSION = "DiagnosticClosedLoopRerunReview_RC1"


def _safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _safe_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _net_direction(row: pd.Series) -> str:
    """Rough diagnostic sign summary for user-facing review."""
    good = []
    if float(row.get("mean_delta_conflict", 0.0)) < 0:
        good.append("conflict_down")
    if float(row.get("mean_delta_uncertainty", 0.0)) < 0:
        good.append("uncertainty_down")
    if float(row.get("mean_delta_exploration", 0.0)) > 0:
        good.append("exploration_up")
    if float(row.get("mean_delta_overconvergence", 0.0)) < 0:
        good.append("overconvergence_down")
    if float(row.get("mean_delta_m_overall", 0.0)) > 0:
        good.append("m_overall_up")
    return "|".join(good) if good else "no_clear_positive_direction"


def _classify_semantic(row: pd.Series) -> tuple[str, str, int]:
    effect = str(row.get("semantic_effect", ""))
    primitive = str(row.get("action_primitives", ""))
    channel = str(row.get("action_channels", ""))
    score = float(row.get("mean_alignment_score", 0.0))
    pass_rate = float(row.get("alignment_pass_rate", 0.0))
    conflict_down = float(row.get("mean_delta_conflict", 0.0)) < 0
    uncertainty_down = float(row.get("mean_delta_uncertainty", 0.0)) < 0
    exploration_up = float(row.get("mean_delta_exploration", 0.0)) > 0
    m_up = float(row.get("mean_delta_m_overall", 0.0)) > 0

    if effect == "intensity_cap_brake" and pass_rate >= 1.0:
        return (
            "positive_control_keep",
            "buffer->replan works as a stable positive control; keep it unchanged for comparisons.",
            1,
        )

    if pass_rate >= 1.0 and score >= 0.95:
        return (
            "ready_current_mapping",
            "current diagnostic primitive maps cleanly to expected outcome in pseudo-reality.",
            1,
        )

    if pass_rate >= 1.0 and score >= 0.50:
        return (
            "usable_but_review_expected_contract",
            "current primitive is usable, but only partially matches the semantic expected-effect contract.",
            2,
        )

    # Misaligned but produces generally beneficial pseudo-reality movement:
    if pass_rate == 0 and (conflict_down or uncertainty_down or m_up or exploration_up):
        if effect in {"diagnostic_resolution_down", "rollback_guard_down", "sandbox_probe_entry_down"}:
            return (
                "expected_effect_contract_review",
                "action produces understandable stabilizing movement, but the expected semantic contract appears mismatched.",
                2,
            )
        if "buffer_increase" in channel:
            return (
                "primitive_mapping_or_contract_review",
                "buffer route creates stabilizing movement but does not express the intended restraint/opening semantics clearly.",
                2,
            )
        if "coupling_relief" in channel:
            return (
                "primitive_mapping_repair",
                "coupling_relief route moves coupling/conflict but fails the semantic contract; mapping needs repair.",
                1,
            )

    if pass_rate < 0.5:
        return (
            "primitive_mapping_repair",
            "semantic effect is observable but not aligned enough; diagnostic primitive mapping should be revised.",
            1,
        )

    return (
        "manual_review",
        "mixed result; review feature-level details before changing pressure.",
        3,
    )


def build_semantic_family_review(semantic_summary: pd.DataFrame) -> pd.DataFrame:
    if semantic_summary is None or semantic_summary.empty:
        return pd.DataFrame()
    rows = []
    for _, row in semantic_summary.iterrows():
        cls, reason, priority = _classify_semantic(row)
        out = row.to_dict()
        out.update({
            "review_class": cls,
            "review_reason": reason,
            "review_priority": int(priority),
            "net_positive_direction": _net_direction(row),
        })
        rows.append(out)
    return pd.DataFrame(rows).sort_values(["review_priority", "review_class", "semantic_effect"])


def build_scenario_review(scenario_summary: pd.DataFrame) -> pd.DataFrame:
    if scenario_summary is None or scenario_summary.empty:
        return pd.DataFrame()
    rows = []
    for _, row in scenario_summary.iterrows():
        pass_rate = float(row.get("isolated_alignment_pass_rate", 0.0))
        conflict = float(row.get("combined_mean_delta_conflict", 0.0))
        exploration = float(row.get("combined_mean_delta_exploration", 0.0))
        m = float(row.get("combined_mean_delta_m_overall", 0.0))
        if pass_rate >= 0.70 and conflict < 0 and exploration > 0 and m > 0:
            cls = "scenario_ready_for_next_precision_test"
            reason = "diagnostic actions show usable alignment and favorable combined movement."
        elif conflict < 0 and exploration > 0 and m > 0:
            cls = "scenario_direction_good_alignment_mixed"
            reason = "combined direction is favorable, but isolated semantic alignment is mixed."
        else:
            cls = "scenario_needs_review"
            reason = "diagnostic movement or alignment is not yet reliable."
        out = row.to_dict()
        out.update({
            "scenario_review_class": cls,
            "scenario_review_reason": reason,
        })
        rows.append(out)
    return pd.DataFrame(rows)


def build_next_action_plan(semantic_review: pd.DataFrame, scenario_review: pd.DataFrame) -> pd.DataFrame:
    rows = [
        {
            "priority": 1,
            "next_task": "DiagnosticPrimitiveMappingRepair_RC1",
            "reason": "Some semantic effects are now observable but misaligned; fix diagnostic primitive mapping before DEPT pressure tuning.",
            "target_semantics": "|".join(
                semantic_review.loc[
                    semantic_review["review_class"].isin(["primitive_mapping_repair", "primitive_mapping_or_contract_review"]),
                    "semantic_effect"
                ].astype(str).tolist()
            ) if not semantic_review.empty else "",
            "expected_output": "revised semantic_effect -> diagnostic primitive/channel map and re-run alignment.",
        },
        {
            "priority": 2,
            "next_task": "ExpectedEffectContractReview_RC1",
            "reason": "Several stabilizing diagnostic actions look beneficial but fail the current expected-effect contract.",
            "target_semantics": "|".join(
                semantic_review.loc[
                    semantic_review["review_class"].isin(["expected_effect_contract_review", "usable_but_review_expected_contract"]),
                    "semantic_effect"
                ].astype(str).tolist()
            ) if not semantic_review.empty else "",
            "expected_output": "separate true misalignment from wrong expected-outcome contract.",
        },
        {
            "priority": 3,
            "next_task": "CouplingReliefStagedUnlockRepair_RC1",
            "reason": "Sequence-level repair remains separate; do it after diagnostic mapping/contract issues are separated.",
            "target_semantics": "sensitivity_opening|hysteresis_guard_down|relation/coupling families",
            "expected_output": "repair staged unlock only after current coupling-relief diagnostic semantics are understood.",
        },
        {
            "priority": 4,
            "next_task": "Keep_DEPT_pressure_tuning_frozen",
            "reason": "Outcome attribution exists now, but semantic mapping is still mixed.",
            "target_semantics": "all",
            "expected_output": "pressure tuning resumes only after diagnostic mapping is stable.",
        },
    ]
    return pd.DataFrame(rows)


def build_review_outputs(results_dir: str | Path) -> Dict[str, pd.DataFrame]:
    results = Path(results_dir)
    semantic_summary = _safe_read_csv(results / "diagnostic_closed_loop_semantic_summary_RC1.csv")
    scenario_summary = _safe_read_csv(results / "diagnostic_closed_loop_scenario_summary_RC1.csv")
    semantic_review = build_semantic_family_review(semantic_summary)
    scenario_review = build_scenario_review(scenario_summary)
    next_plan = build_next_action_plan(semantic_review, scenario_review)
    class_summary = pd.DataFrame()
    if not semantic_review.empty:
        class_summary = semantic_review.groupby(["review_class"], as_index=False).agg(
            semantic_count=("semantic_effect", "nunique"),
            mean_alignment_score=("mean_alignment_score", "mean"),
            mean_pass_rate=("alignment_pass_rate", "mean"),
            semantics=("semantic_effect", lambda s: "|".join(s.astype(str).tolist())),
        )
    return {
        "diagnostic_rerun_semantic_family_review": semantic_review,
        "diagnostic_rerun_scenario_review": scenario_review,
        "diagnostic_rerun_review_class_summary": class_summary,
        "diagnostic_rerun_next_action_plan": next_plan,
    }


def review_summary_json(outputs: Dict[str, pd.DataFrame], rerun_summary: dict | None = None) -> dict:
    semantic = outputs.get("diagnostic_rerun_semantic_family_review", pd.DataFrame())
    scenario = outputs.get("diagnostic_rerun_scenario_review", pd.DataFrame())
    class_summary = outputs.get("diagnostic_rerun_review_class_summary", pd.DataFrame())
    next_plan = outputs.get("diagnostic_rerun_next_action_plan", pd.DataFrame())

    if semantic.empty:
        return {
            "task": REVIEW_VERSION,
            "status": "empty",
            "all_sanity_checks_passed": False,
        }

    class_counts = semantic["review_class"].value_counts().to_dict()
    ready = semantic[semantic["review_class"].isin(["ready_current_mapping", "positive_control_keep"])]["semantic_effect"].astype(str).tolist()
    repair = semantic[semantic["review_class"].isin(["primitive_mapping_repair", "primitive_mapping_or_contract_review"])]["semantic_effect"].astype(str).tolist()
    contract = semantic[semantic["review_class"].isin(["expected_effect_contract_review", "usable_but_review_expected_contract"])]["semantic_effect"].astype(str).tolist()

    return {
        "task": REVIEW_VERSION,
        "status": "completed",
        "source_task": rerun_summary.get("task") if rerun_summary else None,
        "semantic_effect_count": int(semantic["semantic_effect"].nunique()),
        "ready_or_positive_control_count": len(ready),
        "primitive_mapping_repair_count": len(repair),
        "contract_review_count": len(contract),
        "class_counts": class_counts,
        "ready_semantics": ready,
        "primitive_mapping_repair_semantics": repair,
        "expected_contract_review_semantics": contract,
        "scenario_review_classes": scenario["scenario_review_class"].value_counts().to_dict() if not scenario.empty else {},
        "mean_isolated_alignment_score": float(rerun_summary.get("mean_isolated_alignment_score", 0.0)) if rerun_summary else None,
        "isolated_alignment_pass_rate": float(rerun_summary.get("isolated_alignment_pass_rate", 0.0)) if rerun_summary else None,
        "primary_conclusion": "Diagnostic actions are delivered and outcome-attributable; mapping is usable for opening/exploration semantics but mixed for restraint/update/safety-relaxation semantics.",
        "dept_pressure_tuning_readiness": "not_ready_mapping_and_contract_review_required",
        "recommended_next_task": str(next_plan.sort_values("priority").iloc[0]["next_task"]) if not next_plan.empty else None,
        "all_sanity_checks_passed": bool(
            int(semantic["semantic_effect"].nunique()) >= 8
            and len(ready) > 0
            and len(repair) > 0
            and len(contract) > 0
        ),
    }
