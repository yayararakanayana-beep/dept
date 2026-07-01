"""ExpectedEffectContractPatch RC1.

Freezes candidate diagnostic expected-effect contracts proposed by
ExpectedEffectContractReview_RC1 and re-evaluates repaired diagnostic outcomes
against the patched contracts.

Boundary:
    - diagnostic contract patch only
    - no H-DEPT pressure tuning
    - no primitive mapping change
    - no coupling_relief -> staged_unlock repair
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple
import re
import json
import numpy as np
import pandas as pd


PATCH_VERSION = "ExpectedEffectContractPatch_RC1"
DETAIL_RE = re.compile(r"([A-Za-z_]+):expected=([-0-9.]+)")


def _safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _parse_contract_string(s: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    if s is None or str(s) == "nan" or not str(s).strip():
        return out
    for part in str(s).split(";"):
        if ":" not in part:
            continue
        k, v = part.split(":", 1)
        k = k.strip()
        v = v.strip()
        if not k:
            continue
        try:
            out[k] = int(v)
        except ValueError:
            try:
                out[k] = int(float(v))
            except ValueError:
                continue
    return out


def _contract_to_string(contract: Dict[str, int]) -> str:
    return ";".join(f"{k}:{v:+d}" for k, v in sorted(contract.items()))


def _old_contracts_from_semantic_outcome(semantic_outcome: pd.DataFrame) -> pd.DataFrame:
    rows = []
    if semantic_outcome is None or semantic_outcome.empty:
        return pd.DataFrame()
    for effect, grp in semantic_outcome.groupby("semantic_effect"):
        family = str(grp["intent_family"].dropna().iloc[0]) if "intent_family" in grp.columns and grp["intent_family"].notna().any() else ""
        votes: Dict[str, list[int]] = {}
        for details in grp.get("semantic_outcome_details", pd.Series(dtype=str)).dropna().astype(str):
            for feat, sign_s in DETAIL_RE.findall(details):
                try:
                    sign = int(float(sign_s))
                except ValueError:
                    continue
                votes.setdefault(feat, []).append(sign)
        contract = {}
        for feat, vals in votes.items():
            if vals:
                contract[feat] = 1 if float(np.mean(vals)) >= 0 else -1
        rows.append({
            "semantic_effect": str(effect),
            "intent_family": family,
            "old_contract": _contract_to_string(contract),
            "old_contract_source": "pressure_semantic_outcome_alignment_RC1",
        })
    return pd.DataFrame(rows)


def build_patched_contracts(semantic_outcome: pd.DataFrame, candidate_contracts: pd.DataFrame) -> pd.DataFrame:
    old = _old_contracts_from_semantic_outcome(semantic_outcome)
    if old.empty:
        return pd.DataFrame()

    cand = candidate_contracts.copy() if candidate_contracts is not None else pd.DataFrame()
    cand_map = {}
    reason_map = {}
    class_map = {}
    ambiguous = set()
    if not cand.empty:
        for _, r in cand.iterrows():
            effect = str(r.get("semantic_effect", ""))
            cand_map[effect] = str(r.get("candidate_contract", ""))
            reason_map[effect] = str(r.get("candidate_reason", ""))
            class_map[effect] = str(r.get("contract_review_class", ""))
            if str(r.get("contract_review_class", "")) == "contract_or_primitive_ambiguity":
                ambiguous.add(effect)

    rows = []
    for _, r in old.iterrows():
        effect = str(r["semantic_effect"])
        old_contract = str(r["old_contract"])
        patched = cand_map.get(effect, old_contract)
        source = "candidate_contract_frozen" if effect in cand_map else "old_contract_retained"
        rows.append({
            "semantic_effect": effect,
            "intent_family": r.get("intent_family", ""),
            "old_contract": old_contract,
            "patched_contract": patched,
            "patch_source": source,
            "contract_review_class": class_map.get(effect, "not_review_target"),
            "patch_reason": reason_map.get(effect, "retained old contract"),
            "ambiguity_flag": bool(effect in ambiguous),
            "patch_contract": PATCH_VERSION + "__diagnostic_expected_effect_contract",
        })
    return pd.DataFrame(rows)


def _score_contract(contract: Dict[str, int], row: pd.Series) -> Tuple[float, bool, str, int]:
    if not contract:
        return 0.0, False, "empty_contract", 0
    hits = 0
    details = []
    for feat, sign in contract.items():
        col = f"observed_delta_{feat}"
        val = float(row.get(col, 0.0))
        match = abs(val) > 1e-12 and np.sign(val) == np.sign(sign)
        hits += int(match)
        details.append(f"{feat}:expected={sign},observed={val:.6f},match={bool(match)}")
    score = float(hits / max(len(contract), 1))
    return score, bool(score >= 0.50), "; ".join(details), len(contract)


def evaluate_patched_alignment(repaired_alignment: pd.DataFrame, patched_contracts: pd.DataFrame) -> pd.DataFrame:
    if repaired_alignment is None or repaired_alignment.empty or patched_contracts is None or patched_contracts.empty:
        return pd.DataFrame()

    contract_map = {
        str(r.semantic_effect): _parse_contract_string(str(r.patched_contract))
        for _, r in patched_contracts.iterrows()
    }
    source_map = {str(r.semantic_effect): str(r.patch_source) for _, r in patched_contracts.iterrows()}
    ambiguity_map = {str(r.semantic_effect): bool(r.ambiguity_flag) for _, r in patched_contracts.iterrows()}
    class_map = {str(r.semantic_effect): str(r.contract_review_class) for _, r in patched_contracts.iterrows()}

    rows = []
    for _, row in repaired_alignment.iterrows():
        effect = str(row.get("semantic_effect", ""))
        contract = contract_map.get(effect, {})
        score, passed, details, n = _score_contract(contract, row)
        out = row.to_dict()
        out.update({
            "patched_expected_feature_count": int(n),
            "patched_alignment_score": float(score),
            "patched_alignment_pass": bool(passed),
            "patched_alignment_details": details,
            "patched_outcome_verdict": "patched_semantic_aligned" if passed else "patched_semantic_misaligned",
            "patch_source": source_map.get(effect, "missing_contract"),
            "contract_review_class": class_map.get(effect, "missing_contract"),
            "ambiguity_flag": ambiguity_map.get(effect, False),
            "patch_evaluation_contract": PATCH_VERSION + "__patched_contract_vs_repaired_outcome",
        })
        rows.append(out)
    return pd.DataFrame(rows)


def summarize_patched_alignment(patched_alignment: pd.DataFrame) -> pd.DataFrame:
    if patched_alignment is None or patched_alignment.empty:
        return pd.DataFrame()
    pa = patched_alignment.copy()
    for col in ["action_primitive", "action_channel", "action_mass", "repaired_alignment_score", "repaired_alignment_pass"]:
        if col not in pa.columns:
            if col in ["action_primitive", "action_channel"]:
                pa[col] = ""
            elif col == "repaired_alignment_pass":
                pa[col] = False
            else:
                pa[col] = 0.0
    return pa.groupby(["semantic_effect", "intent_family"], as_index=False).agg(
        rows=("semantic_effect", "size"),
        patch_source=("patch_source", lambda s: "|".join(sorted(set(s.dropna().astype(str))))),
        contract_review_class=("contract_review_class", lambda s: "|".join(sorted(set(s.dropna().astype(str))))),
        ambiguity_rate=("ambiguity_flag", "mean"),
        patched_mean_alignment_score=("patched_alignment_score", "mean"),
        patched_alignment_pass_rate=("patched_alignment_pass", "mean"),
        repaired_mean_alignment_score=("repaired_alignment_score", "mean"),
        repaired_alignment_pass_rate=("repaired_alignment_pass", "mean"),
        patched_mean_action_mass=("action_mass", "mean"),
        action_primitives=("action_primitive", lambda s: "|".join(sorted(set(s.dropna().astype(str))))),
        action_channels=("action_channel", lambda s: "|".join(sorted(set(s.dropna().astype(str))))),
        patched_dominant_verdict=("patched_outcome_verdict", lambda s: str(s.value_counts().index[0]) if len(s) else "none"),
    ).sort_values(["patched_alignment_pass_rate", "patched_mean_alignment_score"], ascending=[True, True])


def build_patch_comparison(semantic_summary: pd.DataFrame, patched_summary: pd.DataFrame) -> pd.DataFrame:
    if patched_summary is None or patched_summary.empty:
        return pd.DataFrame()
    patch = patched_summary.copy()
    patch["alignment_pass_rate_delta"] = patch["patched_alignment_pass_rate"] - patch["repaired_alignment_pass_rate"]
    patch["alignment_score_delta"] = patch["patched_mean_alignment_score"] - patch["repaired_mean_alignment_score"]
    patch["patch_verdict"] = np.where(
        patch["alignment_pass_rate_delta"] > 0,
        "improved_by_contract_patch",
        np.where(patch["patched_alignment_pass_rate"] >= 1.0, "already_or_now_aligned", "still_misaligned")
    )
    return patch


def build_outputs_from_results_dir(results_dir: str | Path) -> Dict[str, pd.DataFrame]:
    results = Path(results_dir)
    semantic_outcome = _safe_read_csv(results / "pressure_semantic_outcome_alignment_RC1.csv")
    candidates = _safe_read_csv(results / "expected_effect_contract_candidate_contracts_RC1.csv")
    repaired_alignment = _safe_read_csv(results / "diagnostic_primitive_mapping_repair_isolated_alignment_RC1.csv")
    repaired_summary = _safe_read_csv(results / "diagnostic_primitive_mapping_repair_semantic_summary_RC1.csv")

    patched_contracts = build_patched_contracts(semantic_outcome, candidates)
    patched_alignment = evaluate_patched_alignment(repaired_alignment, patched_contracts)
    patched_summary = summarize_patched_alignment(patched_alignment)
    comparison = build_patch_comparison(repaired_summary, patched_summary)

    patch_targets = patched_contracts[patched_contracts["patch_source"] == "candidate_contract_frozen"].copy() if not patched_contracts.empty else pd.DataFrame()
    target_comparison = comparison[comparison["patch_source"].astype(str).str.contains("candidate_contract_frozen", na=False)].copy() if not comparison.empty else pd.DataFrame()

    return {
        "expected_effect_contract_patch_table": patched_contracts,
        "expected_effect_contract_patch_alignment": patched_alignment,
        "expected_effect_contract_patch_semantic_summary": patched_summary,
        "expected_effect_contract_patch_comparison": comparison,
        "expected_effect_contract_patch_target_comparison": target_comparison,
        "expected_effect_contract_patch_targets": patch_targets,
    }


def patch_summary_json(outputs: Dict[str, pd.DataFrame]) -> dict:
    patch_table = outputs.get("expected_effect_contract_patch_table", pd.DataFrame())
    alignment = outputs.get("expected_effect_contract_patch_alignment", pd.DataFrame())
    summary = outputs.get("expected_effect_contract_patch_semantic_summary", pd.DataFrame())
    comp = outputs.get("expected_effect_contract_patch_comparison", pd.DataFrame())
    target = outputs.get("expected_effect_contract_patch_target_comparison", pd.DataFrame())

    if alignment.empty or summary.empty:
        return {"task": PATCH_VERSION, "status": "empty", "all_sanity_checks_passed": False}

    candidate_targets = patch_table[patch_table["patch_source"] == "candidate_contract_frozen"] if not patch_table.empty else pd.DataFrame()
    ambiguity = patch_table[patch_table["ambiguity_flag"] == True] if not patch_table.empty else pd.DataFrame()

    return {
        "task": PATCH_VERSION,
        "status": "completed",
        "patched_contract_count": int(len(candidate_targets)),
        "retained_contract_count": int((patch_table["patch_source"] == "old_contract_retained").sum()) if not patch_table.empty else 0,
        "ambiguous_patched_count": int(len(ambiguity)),
        "alignment_rows": int(len(alignment)),
        "semantic_effect_count": int(alignment["semantic_effect"].nunique()),
        "overall_repaired_pass_rate_before_patch": float(summary["repaired_alignment_pass_rate"].mean()),
        "overall_patched_pass_rate": float(summary["patched_alignment_pass_rate"].mean()),
        "overall_pass_rate_delta": float(summary["patched_alignment_pass_rate"].mean() - summary["repaired_alignment_pass_rate"].mean()),
        "overall_repaired_score_before_patch": float(summary["repaired_mean_alignment_score"].mean()),
        "overall_patched_score": float(summary["patched_mean_alignment_score"].mean()),
        "target_repaired_pass_rate_before_patch": float(target["repaired_alignment_pass_rate"].mean()) if not target.empty else 0.0,
        "target_patched_pass_rate": float(target["patched_alignment_pass_rate"].mean()) if not target.empty else 0.0,
        "target_pass_rate_delta": float((target["patched_alignment_pass_rate"] - target["repaired_alignment_pass_rate"]).mean()) if not target.empty else 0.0,
        "patched_targets": candidate_targets["semantic_effect"].astype(str).tolist() if not candidate_targets.empty else [],
        "ambiguous_targets": ambiguity["semantic_effect"].astype(str).tolist() if not ambiguity.empty else [],
        "target_comparison": target.to_dict(orient="records") if not target.empty else [],
        "primary_conclusion": "Candidate diagnostic expected-effect contracts were frozen and repaired outcomes were re-evaluated against the patch.",
        "dept_pressure_tuning_readiness": "not_ready_probe_restraint_and_sequence_repair_still_required",
        "next_recommended_task": "ProbeRestraintPrimitiveCheck_RC1_or_CouplingReliefStagedUnlockRepair_RC1",
        "all_sanity_checks_passed": bool(
            int(alignment["semantic_effect"].nunique()) >= 8
            and float(summary["patched_alignment_pass_rate"].mean()) >= float(summary["repaired_alignment_pass_rate"].mean())
            and int(len(candidate_targets)) >= 5
        ),
    }
