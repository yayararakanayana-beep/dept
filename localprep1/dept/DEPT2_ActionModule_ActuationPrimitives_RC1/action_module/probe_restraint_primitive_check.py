"""ProbeRestraintPrimitiveCheck RC1.

Checks the remaining ambiguity around sandbox_probe_entry_down.

Question:
    Is the current buffer-style probe restraint good enough because it produces
    stabilizing movement, or do we need a direct probe-restraint primitive that
    actually expresses old sandbox/probe restraint semantics?

Scope:
    - sandbox_probe_entry_down only
    - diagnostic validation only

Boundary:
    - no H-DEPT pressure tuning
    - no coupling_relief -> staged_unlock repair
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple
import json
import re
import numpy as np
import pandas as pd

from DEPT2_ActionModule_ActuationPrimitives_RC1.pseudo_reality.system import (
    PseudoRealityConfig,
    PseudoRealitySystem,
    STATE_FEATURES,
)
from DEPT2_ActionModule_ActuationPrimitives_RC1.action_module.diagnostic_closed_loop_rerun import (
    summarize_trace,
    delta_summary,
)


CHECK_VERSION = "ProbeRestraintPrimitiveCheck_RC1"
TARGET_SEMANTIC = "sandbox_probe_entry_down"
DETAIL_RE = re.compile(r"([A-Za-z_]+):expected=([-0-9.]+)")


@dataclass(frozen=True)
class ProbeCheckConfig:
    n_entities: int = 18
    action_coupling: float = 0.045
    noise_scale: float = 0.018
    drift_scale: float = 0.006
    alignment_threshold: float = 0.50
    min_observed_abs: float = 1e-12


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
        try:
            out[k.strip()] = int(v.strip())
        except ValueError:
            try:
                out[k.strip()] = int(float(v.strip()))
            except ValueError:
                pass
    return out


def _contract_to_string(contract: Dict[str, int]) -> str:
    return ";".join(f"{k}:{v:+d}" for k, v in sorted(contract.items()))


def _old_contract_from_semantic_outcome(semantic_outcome: pd.DataFrame, effect: str = TARGET_SEMANTIC) -> Dict[str, int]:
    sub = semantic_outcome[semantic_outcome["semantic_effect"].astype(str) == effect].copy() if semantic_outcome is not None and not semantic_outcome.empty else pd.DataFrame()
    votes: Dict[str, list[int]] = {}
    if sub.empty:
        return {}
    for details in sub.get("semantic_outcome_details", pd.Series(dtype=str)).dropna().astype(str):
        for feat, sign_s in DETAIL_RE.findall(details):
            try:
                sign = int(float(sign_s))
            except ValueError:
                continue
            votes.setdefault(feat, []).append(sign)
    return {feat: (1 if float(np.mean(vals)) >= 0 else -1) for feat, vals in votes.items() if vals}


def _patched_contract_from_table(patch_table: pd.DataFrame, effect: str = TARGET_SEMANTIC) -> Dict[str, int]:
    if patch_table is None or patch_table.empty:
        return {}
    sub = patch_table[patch_table["semantic_effect"].astype(str) == effect]
    if sub.empty:
        return {}
    return _parse_contract_string(str(sub.iloc[0].get("patched_contract", "")))


def _match_contract(contract: Dict[str, int], observed: Dict[str, float], threshold: float, min_abs: float) -> Tuple[float, bool, str, int]:
    if not contract:
        return 0.0, False, "empty_contract", 0
    hits = 0
    details = []
    for feat, sign in contract.items():
        val = float(observed.get(f"observed_delta_{feat}", 0.0))
        match = abs(val) > min_abs and np.sign(val) == np.sign(sign)
        hits += int(match)
        details.append(f"{feat}:expected={sign},observed={val:.6f},match={bool(match)}")
    score = float(hits / max(len(contract), 1))
    return score, bool(score >= threshold), "; ".join(details), len(contract)


def _make_world(seed: int, scenario: str, cfg: ProbeCheckConfig) -> PseudoRealitySystem:
    return PseudoRealitySystem(PseudoRealityConfig(
        n_entities=cfg.n_entities,
        seed=int(seed),
        scenario=str(scenario),
        noise_scale=cfg.noise_scale,
        drift_scale=cfg.drift_scale,
        action_coupling=cfg.action_coupling,
    ))


def _advance_to_step(world: PseudoRealitySystem, step: int) -> None:
    for _ in range(int(step)):
        world.step(None)


def _prepare_actions(action_rows: pd.DataFrame, world: PseudoRealitySystem) -> pd.DataFrame:
    if action_rows is None or action_rows.empty:
        return pd.DataFrame(columns=["entity_id", "action_channel", "action_strength"])
    entities = world.entities["entity_id"].tolist()
    rows = []
    for i, (_, row) in enumerate(action_rows.reset_index(drop=True).iterrows()):
        rows.append({
            **row.to_dict(),
            "entity_id": entities[i % len(entities)],
            "action_channel": row.get("action_channel", "no_op"),
            "action_strength": float(row.get("action_strength", 0.0)),
            "direction": 1,
        })
    return pd.DataFrame(rows)


def _apply_probe_direct(world: PseudoRealitySystem, action_frame: pd.DataFrame, mode: str) -> None:
    if action_frame is None or action_frame.empty:
        return
    e = world.entities.copy()
    cfg = world.config
    for _, row in action_frame.iterrows():
        ch = str(row.get("action_channel", ""))
        if ch not in {"diagnostic_probe_restraint_direct", "diagnostic_probe_restraint_hybrid"}:
            continue
        idx = e["entity_id"] == row["entity_id"]
        if not idx.any():
            continue
        strength = float(np.clip(row.get("action_strength", 0.0), 0.0, 1.0)) * cfg.action_coupling
        if ch == "diagnostic_probe_restraint_direct":
            # Express old probe-restraint semantics directly:
            # exploration down, overconvergence / relation_lock up.
            e.loc[idx, "exploration"] -= strength
            e.loc[idx, "entropy"] -= strength * 0.35
            e.loc[idx, "relation_lock"] += strength * 0.45
            e.loc[idx, "uncertainty"] += strength * 0.10
        elif ch == "diagnostic_probe_restraint_hybrid":
            # Hybrid: some direct probe restraint but keep stabilizing behavior.
            e.loc[idx, "exploration"] -= strength * 0.75
            e.loc[idx, "entropy"] -= strength * 0.25
            e.loc[idx, "relation_lock"] += strength * 0.25
            e.loc[idx, "uncertainty"] -= strength * 0.25
            e.loc[idx, "reversibility"] += strength * 0.20
    for feat in STATE_FEATURES:
        e[feat] = np.clip(e[feat], 0.02, 0.98)
    world.entities = e


def _step_variant(world: PseudoRealitySystem, af: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    if af is None or af.empty:
        return world.step(None)
    direct_channels = {"diagnostic_probe_restraint_direct", "diagnostic_probe_restraint_hybrid"}
    base_af = af[~af["action_channel"].isin(direct_channels)].copy()
    direct_af = af[af["action_channel"].isin(direct_channels)].copy()
    trace = world.step(base_af if not base_af.empty else None)
    if not direct_af.empty:
        _apply_probe_direct(world, direct_af, "direct")
        trace = world.emit_trace()
    return trace


def make_probe_variants(action_frame: pd.DataFrame) -> pd.DataFrame:
    target = action_frame[action_frame["semantic_effect"].astype(str) == TARGET_SEMANTIC].copy() if action_frame is not None and not action_frame.empty else pd.DataFrame()
    if target.empty:
        return pd.DataFrame()

    variants = []

    current = target.copy()
    current["probe_variant"] = "current_buffer_style"
    current["variant_reason"] = "current patched behavior; stabilizing buffer-style probe restraint"
    variants.append(current)

    direct = target.copy()
    direct["probe_variant"] = "direct_probe_restraint"
    direct["action_primitive"] = "diagnostic_probe_restraint_direct_v1"
    direct["primitive_sequence"] = "probe_restraint_direct -> reduce_probe_entry -> observe -> report"
    direct["action_channel"] = "diagnostic_probe_restraint_direct"
    direct["diagnostic_action_primitive"] = "diagnostic_probe_restraint_direct_v1"
    direct["diagnostic_primitive_sequence"] = "probe_restraint_direct -> reduce_probe_entry -> observe -> report"
    direct["diagnostic_action_channel"] = "diagnostic_probe_restraint_direct"
    direct["variant_reason"] = "directly tests old sandbox/probe restraint semantics"
    variants.append(direct)

    hybrid = target.copy()
    hybrid["probe_variant"] = "hybrid_probe_restraint"
    hybrid["action_primitive"] = "diagnostic_probe_restraint_hybrid_v1"
    hybrid["primitive_sequence"] = "probe_restraint_hybrid -> stabilize_and_reduce_probe -> observe -> report"
    hybrid["action_channel"] = "diagnostic_probe_restraint_hybrid"
    hybrid["diagnostic_action_primitive"] = "diagnostic_probe_restraint_hybrid_v1"
    hybrid["diagnostic_primitive_sequence"] = "probe_restraint_hybrid -> stabilize_and_reduce_probe -> observe -> report"
    hybrid["diagnostic_action_channel"] = "diagnostic_probe_restraint_hybrid"
    hybrid["variant_reason"] = "tests compromise between direct probe restraint and stabilizing patched behavior"
    variants.append(hybrid)

    out = pd.concat(variants, ignore_index=True)
    out["probe_check_contract"] = CHECK_VERSION + "__variant_action_frame"
    return out


def run_probe_variant_replay(
    variants: pd.DataFrame,
    old_contract: Dict[str, int],
    patched_contract: Dict[str, int],
    cfg: ProbeCheckConfig | None = None,
) -> pd.DataFrame:
    cfg = cfg or ProbeCheckConfig()
    rows = []
    if variants is None or variants.empty:
        return pd.DataFrame()

    group_cols = ["probe_variant", "run_seed", "run_scenario", "loop_step", "semantic_effect"]
    for (variant, seed, scenario, step, effect), group in variants.groupby(group_cols, dropna=False):
        active = _make_world(int(seed), str(scenario), cfg)
        baseline = _make_world(int(seed), str(scenario), cfg)
        _advance_to_step(active, int(step))
        _advance_to_step(baseline, int(step))

        af = _prepare_actions(group.copy(), active)
        active_trace = _step_variant(active, af)
        baseline_trace = baseline.step(None)
        d = delta_summary(summarize_trace(active_trace), summarize_trace(baseline_trace))

        old_score, old_pass, old_details, old_n = _match_contract(old_contract, d, cfg.alignment_threshold, cfg.min_observed_abs)
        patched_score, patched_pass, patched_details, patched_n = _match_contract(patched_contract, d, cfg.alignment_threshold, cfg.min_observed_abs)

        row = {
            "probe_variant": str(variant),
            "run_seed": int(seed),
            "run_scenario": str(scenario),
            "loop_step": int(step),
            "semantic_effect": str(effect),
            "intent_family": str(group["intent_family"].dropna().iloc[0]) if "intent_family" in group.columns and group["intent_family"].notna().any() else "",
            "action_primitive": "|".join(sorted(set(group["action_primitive"].dropna().astype(str)))) if "action_primitive" in group.columns else "",
            "primitive_sequence": "|".join(sorted(set(group["primitive_sequence"].dropna().astype(str)))) if "primitive_sequence" in group.columns else "",
            "action_channel": "|".join(sorted(set(group["action_channel"].dropna().astype(str)))) if "action_channel" in group.columns else "",
            "action_rows": int(len(af)),
            "action_mass": float(af["action_strength"].sum()) if not af.empty else 0.0,
            "old_contract": _contract_to_string(old_contract),
            "patched_contract": _contract_to_string(patched_contract),
            "old_contract_feature_count": int(old_n),
            "patched_contract_feature_count": int(patched_n),
            "old_contract_alignment_score": float(old_score),
            "old_contract_alignment_pass": bool(old_pass),
            "old_contract_details": old_details,
            "patched_contract_alignment_score": float(patched_score),
            "patched_contract_alignment_pass": bool(patched_pass),
            "patched_contract_details": patched_details,
            "probe_check_contract": CHECK_VERSION + "__probe_variant_vs_old_and_patched_contracts",
        }
        row.update(d)
        rows.append(row)
    return pd.DataFrame(rows)


def summarize_probe_variants(alignment: pd.DataFrame) -> pd.DataFrame:
    if alignment is None or alignment.empty:
        return pd.DataFrame()
    return alignment.groupby(["probe_variant"], as_index=False).agg(
        rows=("probe_variant", "size"),
        action_primitive=("action_primitive", lambda s: "|".join(sorted(set(s.dropna().astype(str))))),
        action_channel=("action_channel", lambda s: "|".join(sorted(set(s.dropna().astype(str))))),
        mean_action_mass=("action_mass", "mean"),
        old_contract_pass_rate=("old_contract_alignment_pass", "mean"),
        old_contract_mean_score=("old_contract_alignment_score", "mean"),
        patched_contract_pass_rate=("patched_contract_alignment_pass", "mean"),
        patched_contract_mean_score=("patched_contract_alignment_score", "mean"),
        mean_delta_conflict=("observed_delta_conflict", "mean"),
        mean_delta_uncertainty=("observed_delta_uncertainty", "mean"),
        mean_delta_exploration=("observed_delta_exploration", "mean"),
        mean_delta_overconvergence=("observed_delta_overconvergence", "mean"),
        mean_delta_m_overall=("observed_delta_m_overall", "mean"),
    ).sort_values(["old_contract_pass_rate", "patched_contract_pass_rate", "patched_contract_mean_score"], ascending=[False, False, False])


def decide_probe_policy(summary: pd.DataFrame) -> pd.DataFrame:
    if summary is None or summary.empty:
        return pd.DataFrame()

    rows = []
    # Prefer direct if old semantics matter and it performs better there.
    direct = summary[summary["probe_variant"] == "direct_probe_restraint"]
    current = summary[summary["probe_variant"] == "current_buffer_style"]
    hybrid = summary[summary["probe_variant"] == "hybrid_probe_restraint"]

    direct_old = float(direct["old_contract_mean_score"].iloc[0]) if not direct.empty else 0.0
    current_old = float(current["old_contract_mean_score"].iloc[0]) if not current.empty else 0.0
    hybrid_old = float(hybrid["old_contract_mean_score"].iloc[0]) if not hybrid.empty else 0.0

    direct_patch = float(direct["patched_contract_mean_score"].iloc[0]) if not direct.empty else 0.0
    current_patch = float(current["patched_contract_mean_score"].iloc[0]) if not current.empty else 0.0
    hybrid_patch = float(hybrid["patched_contract_mean_score"].iloc[0]) if not hybrid.empty else 0.0

    if direct_old > current_old and direct_old >= 0.5:
        recommendation = "add_direct_probe_restraint_primitive"
        reason = "direct variant expresses old sandbox/probe restraint semantics better than current buffer-style mapping"
        priority = 1
    elif hybrid_old > current_old and hybrid_patch >= current_patch:
        recommendation = "add_hybrid_probe_restraint_primitive"
        reason = "hybrid variant improves old semantic expression while preserving patched stabilization behavior"
        priority = 1
    else:
        recommendation = "retain_buffer_style_as_stabilization_contract"
        reason = "direct/hybrid variants do not outperform current behavior enough; treat sandbox_probe_entry_down as stabilization contract"
        priority = 2

    rows.append({
        "recommendation": recommendation,
        "reason": reason,
        "priority": priority,
        "current_old_contract_score": current_old,
        "direct_old_contract_score": direct_old,
        "hybrid_old_contract_score": hybrid_old,
        "current_patched_contract_score": current_patch,
        "direct_patched_contract_score": direct_patch,
        "hybrid_patched_contract_score": hybrid_patch,
        "next_task_if_adopted": "ProbeRestraintPrimitivePatch_RC1" if "primitive" in recommendation else "Continue_to_CouplingReliefStagedUnlockRepair_RC1",
    })
    return pd.DataFrame(rows)


def build_outputs_from_results_dir(results_dir: str | Path) -> Dict[str, pd.DataFrame]:
    results = Path(results_dir)
    action_frame = _safe_read_csv(results / "diagnostic_primitive_mapping_repaired_action_frame_RC1.csv")
    semantic_outcome = _safe_read_csv(results / "pressure_semantic_outcome_alignment_RC1.csv")
    patch_table = _safe_read_csv(results / "expected_effect_contract_patch_table_RC1.csv")

    old_contract = _old_contract_from_semantic_outcome(semantic_outcome, TARGET_SEMANTIC)
    patched_contract = _patched_contract_from_table(patch_table, TARGET_SEMANTIC)

    variants = make_probe_variants(action_frame)
    alignment = run_probe_variant_replay(variants, old_contract, patched_contract, ProbeCheckConfig())
    summary = summarize_probe_variants(alignment)
    decision = decide_probe_policy(summary)

    contract_table = pd.DataFrame([
        {
            "semantic_effect": TARGET_SEMANTIC,
            "old_contract": _contract_to_string(old_contract),
            "patched_contract": _contract_to_string(patched_contract),
            "contract_issue": "patched stabilization contract aligns, but direct probe-restraint expression was ambiguous",
            "probe_check_contract": CHECK_VERSION + "__old_vs_patched_contract_basis",
        }
    ])

    return {
        "probe_restraint_variant_action_frame": variants,
        "probe_restraint_variant_alignment": alignment,
        "probe_restraint_variant_summary": summary,
        "probe_restraint_contract_basis": contract_table,
        "probe_restraint_policy_decision": decision,
    }


def probe_check_summary_json(outputs: Dict[str, pd.DataFrame]) -> dict:
    variants = outputs.get("probe_restraint_variant_action_frame", pd.DataFrame())
    alignment = outputs.get("probe_restraint_variant_alignment", pd.DataFrame())
    summary = outputs.get("probe_restraint_variant_summary", pd.DataFrame())
    decision = outputs.get("probe_restraint_policy_decision", pd.DataFrame())

    if alignment.empty or summary.empty:
        return {"task": CHECK_VERSION, "status": "empty", "all_sanity_checks_passed": False}

    best_old = summary.sort_values(["old_contract_mean_score", "patched_contract_mean_score"], ascending=[False, False]).iloc[0].to_dict()
    best_patch = summary.sort_values(["patched_contract_mean_score", "old_contract_mean_score"], ascending=[False, False]).iloc[0].to_dict()
    rec = decision.iloc[0].to_dict() if not decision.empty else {}

    return {
        "task": CHECK_VERSION,
        "status": "completed",
        "semantic_effect": TARGET_SEMANTIC,
        "variant_count": int(summary["probe_variant"].nunique()),
        "variant_action_rows": int(len(variants)),
        "alignment_rows": int(len(alignment)),
        "best_old_contract_variant": str(best_old.get("probe_variant")),
        "best_old_contract_score": float(best_old.get("old_contract_mean_score", 0.0)),
        "best_patched_contract_variant": str(best_patch.get("probe_variant")),
        "best_patched_contract_score": float(best_patch.get("patched_contract_mean_score", 0.0)),
        "policy_recommendation": rec.get("recommendation"),
        "policy_reason": rec.get("reason"),
        "decision": rec,
        "variant_summary": summary.to_dict(orient="records"),
        "primary_conclusion": "Probe-restraint ambiguity is resolved by comparing buffer-style, direct, and hybrid variants against old and patched contracts.",
        "dept_pressure_tuning_readiness": "not_ready_sequence_repair_still_required",
        "next_recommended_task": rec.get("next_task_if_adopted", "CouplingReliefStagedUnlockRepair_RC1"),
        "all_sanity_checks_passed": bool(
            int(summary["probe_variant"].nunique()) == 3
            and len(alignment) > 0
            and bool(rec)
        ),
    }
