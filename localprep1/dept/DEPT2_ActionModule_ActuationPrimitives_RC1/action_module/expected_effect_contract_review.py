"""ExpectedEffectContractReview RC1.

Reviews whether some semantic-effect expected-outcome contracts are mismatched
with the observed diagnostic pseudo-reality effects.

Scope:
    contract review only.

It does not:
    - tune H-DEPT pressure
    - change diagnostic primitive mappings
    - repair coupling_relief -> staged_unlock
    - directly rewrite production contracts

The output is a candidate contract patch and review classification.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple
import json
import re
import numpy as np
import pandas as pd


REVIEW_VERSION = "ExpectedEffectContractReview_RC1"

DETAIL_RE = re.compile(r"([A-Za-z_]+):expected=([-0-9.]+)")

CONTRACT_REVIEW_TARGETS = [
    "diagnostic_resolution_down",
    "rollback_guard_down",
    "sandbox_probe_entry_down",
    "hysteresis_guard_down",
    "update_access_opening",
    "update_frequency_up",
]

FEATURES = ["conflict", "uncertainty", "exploration", "overconvergence", "m_overall"]

# Human-readable semantic intent hints.  These are not truth labels; they guide
# the review so candidate patches are not purely numeric echoing.
SEMANTIC_INTENT_HINTS: Dict[str, str] = {
    "diagnostic_resolution_down": "observation cost saving / lighter observation",
    "rollback_guard_down": "rollback/safety relaxation semantics; current action behaves like buffer stabilization",
    "sandbox_probe_entry_down": "probe/sandbox entry restraint; current action behaves like buffer stabilization",
    "hysteresis_guard_down": "switching flexibility / less hysteresis guard",
    "update_access_opening": "temporal/update access opening via uncertainty probe",
    "update_frequency_up": "update opening / more frequent diagnostic update via uncertainty probe",
}

# Candidate revisions are conservative and diagnostic-only.  They separate the
# observed pseudo-reality effect from the old semantic expectation.
CANDIDATE_CONTRACTS: Dict[str, Dict[str, int]] = {
    "diagnostic_resolution_down": {
        "conflict": -1,
        "uncertainty": -1,
        "m_overall": 1,
    },
    "rollback_guard_down": {
        "conflict": -1,
        "uncertainty": -1,
        "m_overall": 1,
    },
    "sandbox_probe_entry_down": {
        "conflict": -1,
        "uncertainty": -1,
        "m_overall": 1,
    },
    "hysteresis_guard_down": {
        "conflict": -1,
        "overconvergence": -1,
        "m_overall": 1,
    },
    "update_access_opening": {
        "exploration": 1,
        "overconvergence": -1,
        "uncertainty": -1,
        "m_overall": 1,
    },
    "update_frequency_up": {
        "exploration": 1,
        "overconvergence": -1,
        "uncertainty": -1,
        "m_overall": 1,
    },
}


def _safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _safe_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def parse_expected_contracts(semantic_outcome: pd.DataFrame) -> pd.DataFrame:
    rows = []
    if semantic_outcome is None or semantic_outcome.empty:
        return pd.DataFrame()

    for effect, grp in semantic_outcome.groupby("semantic_effect"):
        votes: Dict[str, list[int]] = {}
        family = str(grp["intent_family"].dropna().iloc[0]) if "intent_family" in grp.columns and grp["intent_family"].notna().any() else ""
        for details in grp.get("semantic_outcome_details", pd.Series(dtype=str)).dropna().astype(str):
            for feat, sign_s in DETAIL_RE.findall(details):
                try:
                    sign = int(float(sign_s))
                except ValueError:
                    continue
                votes.setdefault(feat, []).append(sign)

        for feat, vals in votes.items():
            if not vals:
                continue
            mean_vote = float(np.mean(vals))
            rows.append({
                "semantic_effect": str(effect),
                "intent_family": family,
                "feature": str(feat),
                "old_expected_sign": 1 if mean_vote >= 0 else -1,
                "old_expected_vote_mean": mean_vote,
                "old_expected_vote_count": int(len(vals)),
            })

    return pd.DataFrame(rows)


def _observed_feature_rows(repaired_summary: pd.DataFrame) -> pd.DataFrame:
    rows = []
    if repaired_summary is None or repaired_summary.empty:
        return pd.DataFrame()

    for _, row in repaired_summary.iterrows():
        effect = str(row.get("semantic_effect", ""))
        family = str(row.get("intent_family", ""))
        for feat in FEATURES:
            col = f"repaired_mean_delta_{feat}"
            if col not in row:
                continue
            val = float(row.get(col, 0.0))
            sign = 0
            if val > 0:
                sign = 1
            elif val < 0:
                sign = -1
            rows.append({
                "semantic_effect": effect,
                "intent_family": family,
                "feature": feat,
                "observed_delta": val,
                "observed_sign": sign,
                "observed_abs_delta": abs(val),
                "observed_nonzero": bool(sign != 0),
            })
    return pd.DataFrame(rows)


def _score_contract(contract: Dict[str, int], observed_map: Dict[str, int]) -> Tuple[float, str]:
    if not contract:
        return 0.0, "empty_contract"
    hits = 0
    details = []
    for feat, sign in contract.items():
        obs = int(observed_map.get(feat, 0))
        match = obs != 0 and np.sign(obs) == np.sign(sign)
        hits += int(match)
        details.append(f"{feat}:expected={sign},observed_sign={obs},match={bool(match)}")
    return float(hits / max(len(contract), 1)), "; ".join(details)


def _contract_to_string(contract: Dict[str, int]) -> str:
    return ";".join(f"{k}:{v:+d}" for k, v in sorted(contract.items()))


def _classify_contract(effect: str, old_score: float, candidate_score: float, observed_map: Dict[str, int], old_contract: Dict[str, int], candidate: Dict[str, int]) -> Tuple[str, str, int]:
    if effect == "sandbox_probe_entry_down":
        return (
            "contract_or_primitive_ambiguity",
            "Current buffer-style action does not express old probe-restraint expectations; candidate contract captures observed stabilization, but a future direct probe-restraint primitive may still be preferable.",
            1,
        )

    if old_score == 0 and candidate_score >= 0.75:
        return (
            "contract_inverted_or_wrong_direction",
            "Old contract expects the opposite direction from the observed diagnostic effect; candidate contract matches current pseudo-reality behavior.",
            1,
        )

    if old_score < 0.5 and candidate_score >= 0.75:
        return (
            "contract_mismatch_likely",
            "Current primitive is observable, but old expected-effect contract is mismatched or too coarse.",
            1,
        )

    if old_score >= 0.5 and candidate_score >= old_score:
        old_feats = set(old_contract.keys())
        cand_feats = set(candidate.keys())
        if old_feats != cand_feats:
            return (
                "contract_over_specified_or_missing_feature",
                "Old contract is partly valid but contains/omits features that do not match observed diagnostic effects.",
                2,
            )
        return (
            "contract_mostly_valid",
            "Old contract broadly matches observed effects; only minor review needed.",
            3,
        )

    return (
        "manual_review_required",
        "Observed diagnostic behavior does not clearly support either old or candidate contract.",
        2,
    )


def build_expected_effect_contract_review(
    semantic_outcome: pd.DataFrame,
    repaired_summary: pd.DataFrame,
    targets: list[str] | None = None,
) -> Dict[str, pd.DataFrame]:
    targets = targets or CONTRACT_REVIEW_TARGETS
    old_rows = parse_expected_contracts(semantic_outcome)
    obs_rows = _observed_feature_rows(repaired_summary)

    review_rows = []
    feature_rows = []
    candidate_rows = []

    for effect in targets:
        old_sub = old_rows[old_rows["semantic_effect"] == effect]
        obs_sub = obs_rows[obs_rows["semantic_effect"] == effect]
        if old_sub.empty and obs_sub.empty:
            continue

        family = ""
        if not obs_sub.empty:
            family = str(obs_sub["intent_family"].dropna().iloc[0])
        elif not old_sub.empty:
            family = str(old_sub["intent_family"].dropna().iloc[0])

        old_contract = {str(r.feature): int(r.old_expected_sign) for _, r in old_sub.iterrows()}
        observed_map = {str(r.feature): int(r.observed_sign) for _, r in obs_sub.iterrows()}
        observed_delta_map = {str(r.feature): float(r.observed_delta) for _, r in obs_sub.iterrows()}
        candidate = CANDIDATE_CONTRACTS.get(effect, {k: v for k, v in observed_map.items() if v != 0})

        old_score, old_details = _score_contract(old_contract, observed_map)
        candidate_score, candidate_details = _score_contract(candidate, observed_map)
        review_class, reason, priority = _classify_contract(effect, old_score, candidate_score, observed_map, old_contract, candidate)

        for feat in sorted(set(old_contract) | set(observed_map) | set(candidate)):
            old_sign = old_contract.get(feat, 0)
            obs_sign = observed_map.get(feat, 0)
            cand_sign = candidate.get(feat, 0)
            feature_rows.append({
                "semantic_effect": effect,
                "intent_family": family,
                "feature": feat,
                "old_expected_sign": old_sign,
                "observed_sign": obs_sign,
                "candidate_expected_sign": cand_sign,
                "observed_delta": observed_delta_map.get(feat, 0.0),
                "old_matches_observed": bool(old_sign != 0 and obs_sign != 0 and np.sign(old_sign) == np.sign(obs_sign)),
                "candidate_matches_observed": bool(cand_sign != 0 and obs_sign != 0 and np.sign(cand_sign) == np.sign(obs_sign)),
            })

        candidate_rows.append({
            "semantic_effect": effect,
            "intent_family": family,
            "old_contract": _contract_to_string(old_contract),
            "candidate_contract": _contract_to_string(candidate),
            "candidate_status": "candidate_only_not_yet_frozen",
            "candidate_reason": reason,
            "contract_review_class": review_class,
            "review_priority": priority,
            "contract_patch_contract": REVIEW_VERSION + "__candidate_expected_effect_contract",
        })

        review_rows.append({
            "semantic_effect": effect,
            "intent_family": family,
            "semantic_intent_hint": SEMANTIC_INTENT_HINTS.get(effect, ""),
            "old_contract": _contract_to_string(old_contract),
            "candidate_contract": _contract_to_string(candidate),
            "old_contract_alignment_score": old_score,
            "candidate_contract_alignment_score": candidate_score,
            "score_delta": candidate_score - old_score,
            "old_match_details": old_details,
            "candidate_match_details": candidate_details,
            "contract_review_class": review_class,
            "review_reason": reason,
            "review_priority": priority,
            "recommended_action": (
                "adopt_candidate_after_one_more_rerun"
                if review_class in {"contract_inverted_or_wrong_direction", "contract_mismatch_likely", "contract_over_specified_or_missing_feature"}
                else "manual_review_before_adoption"
            ),
        })

    review = pd.DataFrame(review_rows).sort_values(["review_priority", "semantic_effect"]) if review_rows else pd.DataFrame()
    features = pd.DataFrame(feature_rows)
    candidates = pd.DataFrame(candidate_rows).sort_values(["review_priority", "semantic_effect"]) if candidate_rows else pd.DataFrame()

    class_summary = pd.DataFrame()
    if not review.empty:
        class_summary = review.groupby("contract_review_class", as_index=False).agg(
            semantic_count=("semantic_effect", "nunique"),
            mean_old_score=("old_contract_alignment_score", "mean"),
            mean_candidate_score=("candidate_contract_alignment_score", "mean"),
            semantics=("semantic_effect", lambda s: "|".join(s.astype(str).tolist())),
        )

    next_plan = pd.DataFrame([
        {
            "priority": 1,
            "next_task": "ExpectedEffectContractPatch_RC1",
            "reason": "Review found candidate contracts that better match diagnostic pseudo-reality behavior.",
            "target_semantics": "|".join(candidates["semantic_effect"].astype(str).tolist()) if not candidates.empty else "",
            "expected_output": "freeze candidate contracts as diagnostic expected-effect contracts, then rerun alignment.",
        },
        {
            "priority": 2,
            "next_task": "ProbeRestraintPrimitiveCheck_RC1",
            "reason": "sandbox_probe_entry_down may be a contract/primitive ambiguity rather than a pure contract issue.",
            "target_semantics": "sandbox_probe_entry_down",
            "expected_output": "decide whether to keep buffer-style stabilization or add direct probe-restraint primitive.",
        },
        {
            "priority": 3,
            "next_task": "CouplingReliefStagedUnlockRepair_RC1",
            "reason": "Sequence-level repair remains separate after diagnostic mapping and contract review.",
            "target_semantics": "relation/coupling staged unlock families",
            "expected_output": "repair coupling_relief -> staged_unlock sequence.",
        },
    ])

    return {
        "expected_effect_contract_review_table": review,
        "expected_effect_contract_feature_evidence": features,
        "expected_effect_contract_candidate_contracts": candidates,
        "expected_effect_contract_class_summary": class_summary,
        "expected_effect_contract_next_action_plan": next_plan,
    }


def build_outputs_from_results_dir(results_dir: str | Path) -> Dict[str, pd.DataFrame]:
    results = Path(results_dir)
    semantic_outcome = _safe_read_csv(results / "pressure_semantic_outcome_alignment_RC1.csv")
    repaired_summary = _safe_read_csv(results / "diagnostic_primitive_mapping_repair_semantic_summary_RC1.csv")
    review_summary = _safe_json(results / "diagnostic_closed_loop_rerun_review_summary_RC1.json")
    targets = review_summary.get("expected_contract_review_semantics") or CONTRACT_REVIEW_TARGETS
    return build_expected_effect_contract_review(semantic_outcome, repaired_summary, targets=targets)


def expected_contract_review_summary_json(outputs: Dict[str, pd.DataFrame]) -> dict:
    review = outputs.get("expected_effect_contract_review_table", pd.DataFrame())
    features = outputs.get("expected_effect_contract_feature_evidence", pd.DataFrame())
    candidates = outputs.get("expected_effect_contract_candidate_contracts", pd.DataFrame())
    class_summary = outputs.get("expected_effect_contract_class_summary", pd.DataFrame())

    if review.empty:
        return {
            "task": REVIEW_VERSION,
            "status": "empty",
            "all_sanity_checks_passed": False,
        }

    adopted_like = review[review["recommended_action"] == "adopt_candidate_after_one_more_rerun"]
    ambiguous = review[review["contract_review_class"] == "contract_or_primitive_ambiguity"]

    return {
        "task": REVIEW_VERSION,
        "status": "completed",
        "reviewed_semantic_count": int(review["semantic_effect"].nunique()),
        "mean_old_contract_alignment_score": float(review["old_contract_alignment_score"].mean()),
        "mean_candidate_contract_alignment_score": float(review["candidate_contract_alignment_score"].mean()),
        "mean_score_delta": float(review["score_delta"].mean()),
        "candidate_adoption_after_rerun_count": int(len(adopted_like)),
        "ambiguity_count": int(len(ambiguous)),
        "class_counts": review["contract_review_class"].value_counts().to_dict(),
        "candidate_contract_semantics": candidates["semantic_effect"].astype(str).tolist() if not candidates.empty else [],
        "ambiguous_semantics": ambiguous["semantic_effect"].astype(str).tolist(),
        "class_summary": class_summary.to_dict(orient="records") if not class_summary.empty else [],
        "primary_conclusion": "Several old expected-effect contracts are mismatched with observed diagnostic pseudo-reality effects; candidate diagnostic contracts are proposed but not frozen.",
        "dept_pressure_tuning_readiness": "not_ready_contract_patch_and_rerun_required",
        "next_recommended_task": "ExpectedEffectContractPatch_RC1",
        "all_sanity_checks_passed": bool(
            int(review["semantic_effect"].nunique()) >= 5
            and float(review["candidate_contract_alignment_score"].mean()) > float(review["old_contract_alignment_score"].mean())
            and len(candidates) >= 5
        ),
    }
