"""ProbeRestraintPrimitivePatch RC1.

Adds a direct probe-restraint primitive/channel for sandbox_probe_entry_down
while preserving the existing buffer-style stabilization behavior as a separate
contract/behavior.

This patch resolves the ambiguity found in ProbeRestraintPrimitiveCheck_RC1:
    - buffer style matches stabilization/patched contract
    - direct/hybrid variants express old probe-restraint semantics

Boundary:
    - diagnostic validation patch only
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


PATCH_VERSION = "ProbeRestraintPrimitivePatch_RC1"
TARGET_SEMANTIC = "sandbox_probe_entry_down"
DETAIL_RE = re.compile(r"([A-Za-z_]+):expected=([-0-9.]+)")


@dataclass(frozen=True)
class ProbePatchConfig:
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


def patch_probe_restraint_action_frame(action_frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if action_frame is None or action_frame.empty:
        return pd.DataFrame(), pd.DataFrame()

    base = action_frame.copy()
    target_mask = base["semantic_effect"].astype(str) == TARGET_SEMANTIC
    target = base[target_mask].copy()
    non_target = base[~target_mask].copy()

    if target.empty:
        return base, pd.DataFrame()

    # Existing buffer-style rows are preserved but relabeled as stabilization
    # guard. They remain available for the patched stabilization contract.
    stabilization = target.copy()
    stabilization["probe_role"] = "stabilization_guard"
    stabilization["semantic_effect"] = "sandbox_probe_entry_down_stabilization"
    stabilization["intent_family"] = "probe_restraint_stabilization"
    stabilization["action_primitive"] = "diagnostic_probe_restraint_stabilization_guard"
    stabilization["primitive_sequence"] = "probe_restraint_stabilization -> buffer_guard -> observe -> report"
    stabilization["action_channel"] = "buffer_increase"
    stabilization["diagnostic_action_primitive"] = "diagnostic_probe_restraint_stabilization_guard"
    stabilization["diagnostic_primitive_sequence"] = "probe_restraint_stabilization -> buffer_guard -> observe -> report"
    stabilization["diagnostic_action_channel"] = "buffer_increase"
    stabilization["probe_patch_note"] = "existing buffer-style behavior preserved as stabilization guard"

    # New direct rows represent the old probe-restraint semantics.
    direct = target.copy()
    direct["probe_role"] = "direct_probe_restraint"
    direct["action_primitive"] = "diagnostic_probe_restraint_direct_v1"
    direct["primitive_sequence"] = "probe_restraint_direct -> reduce_probe_entry -> observe -> report"
    direct["action_channel"] = "diagnostic_probe_restraint_direct"
    direct["diagnostic_action_primitive"] = "diagnostic_probe_restraint_direct_v1"
    direct["diagnostic_primitive_sequence"] = "probe_restraint_direct -> reduce_probe_entry -> observe -> report"
    direct["diagnostic_action_channel"] = "diagnostic_probe_restraint_direct"
    direct["probe_patch_note"] = "direct probe-restraint behavior added for old sandbox/probe restraint semantics"

    patched = pd.concat([non_target, stabilization, direct], ignore_index=True)
    patched["probe_restraint_patch_applied"] = patched.get("probe_role", pd.Series([""] * len(patched))).astype(str).isin(
        ["stabilization_guard", "direct_probe_restraint"]
    )
    patched["probe_restraint_patch_version"] = np.where(
        patched["probe_restraint_patch_applied"],
        PATCH_VERSION,
        "",
    )

    patch_table = pd.DataFrame([
        {
            "semantic_effect_original": TARGET_SEMANTIC,
            "patched_semantic_effect": "sandbox_probe_entry_down_stabilization",
            "probe_role": "stabilization_guard",
            "action_primitive": "diagnostic_probe_restraint_stabilization_guard",
            "action_channel": "buffer_increase",
            "contract_role": "patched_stabilization_contract",
            "rows": int(len(stabilization)),
            "reason": "preserve current buffer-style stabilization separately",
            "patch_contract": PATCH_VERSION + "__role_split",
        },
        {
            "semantic_effect_original": TARGET_SEMANTIC,
            "patched_semantic_effect": TARGET_SEMANTIC,
            "probe_role": "direct_probe_restraint",
            "action_primitive": "diagnostic_probe_restraint_direct_v1",
            "action_channel": "diagnostic_probe_restraint_direct",
            "contract_role": "old_probe_restraint_contract",
            "rows": int(len(direct)),
            "reason": "add direct primitive to express probe-entry-down semantics",
            "patch_contract": PATCH_VERSION + "__role_split",
        },
    ])
    return patched, patch_table


def _make_world(seed: int, scenario: str, cfg: ProbePatchConfig) -> PseudoRealitySystem:
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


def _apply_direct_probe_restraint(world: PseudoRealitySystem, action_frame: pd.DataFrame) -> None:
    if action_frame is None or action_frame.empty:
        return
    e = world.entities.copy()
    cfg = world.config
    for _, row in action_frame.iterrows():
        ch = str(row.get("action_channel", ""))
        if ch != "diagnostic_probe_restraint_direct":
            continue
        idx = e["entity_id"] == row["entity_id"]
        if not idx.any():
            continue
        strength = float(np.clip(row.get("action_strength", 0.0), 0.0, 1.0)) * cfg.action_coupling
        e.loc[idx, "exploration"] -= strength
        e.loc[idx, "entropy"] -= strength * 0.35
        e.loc[idx, "relation_lock"] += strength * 0.45
        e.loc[idx, "uncertainty"] += strength * 0.10
    for feat in STATE_FEATURES:
        e[feat] = np.clip(e[feat], 0.02, 0.98)
    world.entities = e


def _step_with_probe_patch(world: PseudoRealitySystem, af: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    if af is None or af.empty:
        return world.step(None)
    direct_af = af[af["action_channel"] == "diagnostic_probe_restraint_direct"].copy()
    base_af = af[af["action_channel"] != "diagnostic_probe_restraint_direct"].copy()
    trace = world.step(base_af if not base_af.empty else None)
    if not direct_af.empty:
        _apply_direct_probe_restraint(world, direct_af)
        trace = world.emit_trace()
    return trace


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


def run_role_split_replay(
    patched_frame: pd.DataFrame,
    old_contract: Dict[str, int],
    patched_contract: Dict[str, int],
    cfg: ProbePatchConfig | None = None,
) -> pd.DataFrame:
    cfg = cfg or ProbePatchConfig()
    target = patched_frame[
        patched_frame.get("probe_role", pd.Series([""] * len(patched_frame))).astype(str).isin(
            ["stabilization_guard", "direct_probe_restraint"]
        )
    ].copy()
    if target.empty:
        return pd.DataFrame()

    rows = []
    group_cols = ["probe_role", "run_seed", "run_scenario", "loop_step", "semantic_effect"]
    for (role, seed, scenario, step, effect), group in target.groupby(group_cols, dropna=False):
        active = _make_world(int(seed), str(scenario), cfg)
        baseline = _make_world(int(seed), str(scenario), cfg)
        _advance_to_step(active, int(step))
        _advance_to_step(baseline, int(step))
        af = _prepare_actions(group.copy(), active)
        active_trace = _step_with_probe_patch(active, af)
        baseline_trace = baseline.step(None)
        d = delta_summary(summarize_trace(active_trace), summarize_trace(baseline_trace))

        contract = old_contract if role == "direct_probe_restraint" else patched_contract
        old_score, old_pass, old_details, old_n = _match_contract(old_contract, d, cfg.alignment_threshold, cfg.min_observed_abs)
        patched_score, patched_pass, patched_details, patched_n = _match_contract(patched_contract, d, cfg.alignment_threshold, cfg.min_observed_abs)
        role_score, role_pass, role_details, role_n = _match_contract(contract, d, cfg.alignment_threshold, cfg.min_observed_abs)

        row = {
            "probe_role": str(role),
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
            "role_contract": "old_probe_restraint_contract" if role == "direct_probe_restraint" else "patched_stabilization_contract",
            "role_contract_alignment_score": float(role_score),
            "role_contract_alignment_pass": bool(role_pass),
            "role_contract_alignment_details": role_details,
            "old_contract_alignment_score": float(old_score),
            "old_contract_alignment_pass": bool(old_pass),
            "old_contract_details": old_details,
            "patched_contract_alignment_score": float(patched_score),
            "patched_contract_alignment_pass": bool(patched_pass),
            "patched_contract_details": patched_details,
            "probe_patch_replay_contract": PATCH_VERSION + "__role_split_replay",
        }
        row.update(d)
        rows.append(row)
    return pd.DataFrame(rows)


def summarize_role_split(alignment: pd.DataFrame) -> pd.DataFrame:
    if alignment is None or alignment.empty:
        return pd.DataFrame()
    return alignment.groupby(["probe_role", "semantic_effect"], as_index=False).agg(
        rows=("probe_role", "size"),
        action_primitive=("action_primitive", lambda s: "|".join(sorted(set(s.dropna().astype(str))))),
        action_channel=("action_channel", lambda s: "|".join(sorted(set(s.dropna().astype(str))))),
        mean_action_mass=("action_mass", "mean"),
        role_contract_pass_rate=("role_contract_alignment_pass", "mean"),
        role_contract_mean_score=("role_contract_alignment_score", "mean"),
        old_contract_pass_rate=("old_contract_alignment_pass", "mean"),
        old_contract_mean_score=("old_contract_alignment_score", "mean"),
        patched_contract_pass_rate=("patched_contract_alignment_pass", "mean"),
        patched_contract_mean_score=("patched_contract_alignment_score", "mean"),
        mean_delta_conflict=("observed_delta_conflict", "mean"),
        mean_delta_uncertainty=("observed_delta_uncertainty", "mean"),
        mean_delta_exploration=("observed_delta_exploration", "mean"),
        mean_delta_overconvergence=("observed_delta_overconvergence", "mean"),
        mean_delta_m_overall=("observed_delta_m_overall", "mean"),
    ).sort_values(["probe_role"])


def build_outputs_from_results_dir(results_dir: str | Path) -> Dict[str, pd.DataFrame]:
    results = Path(results_dir)
    action_frame = pd.read_csv(results / "diagnostic_primitive_mapping_repaired_action_frame_RC1.csv")
    semantic_outcome = pd.read_csv(results / "pressure_semantic_outcome_alignment_RC1.csv")
    patch_table_contracts = pd.read_csv(results / "expected_effect_contract_patch_table_RC1.csv")

    old_contract = _old_contract_from_semantic_outcome(semantic_outcome, TARGET_SEMANTIC)
    stabilization_contract = _patched_contract_from_table(patch_table_contracts, TARGET_SEMANTIC)

    patched_frame, patch_table = patch_probe_restraint_action_frame(action_frame)
    alignment = run_role_split_replay(patched_frame, old_contract, stabilization_contract, ProbePatchConfig())
    summary = summarize_role_split(alignment)

    contract_basis = pd.DataFrame([
        {
            "contract_role": "old_probe_restraint_contract",
            "semantic_effect": TARGET_SEMANTIC,
            "contract": _contract_to_string(old_contract),
            "assigned_probe_role": "direct_probe_restraint",
            "reason": "directly expresses sandbox/probe entry reduction",
        },
        {
            "contract_role": "patched_stabilization_contract",
            "semantic_effect": "sandbox_probe_entry_down_stabilization",
            "contract": _contract_to_string(stabilization_contract),
            "assigned_probe_role": "stabilization_guard",
            "reason": "preserves buffer-style stabilization as separate behavior",
        },
    ])

    return {
        "probe_restraint_primitive_patch_table": patch_table,
        "probe_restraint_primitive_patched_action_frame": patched_frame,
        "probe_restraint_primitive_patch_alignment": alignment,
        "probe_restraint_primitive_patch_summary": summary,
        "probe_restraint_primitive_patch_contract_basis": contract_basis,
    }


def patch_summary_json(outputs: Dict[str, pd.DataFrame]) -> dict:
    table = outputs.get("probe_restraint_primitive_patch_table", pd.DataFrame())
    frame = outputs.get("probe_restraint_primitive_patched_action_frame", pd.DataFrame())
    alignment = outputs.get("probe_restraint_primitive_patch_alignment", pd.DataFrame())
    summary = outputs.get("probe_restraint_primitive_patch_summary", pd.DataFrame())

    if alignment.empty or summary.empty:
        return {"task": PATCH_VERSION, "status": "empty", "all_sanity_checks_passed": False}

    direct = summary[summary["probe_role"] == "direct_probe_restraint"]
    stab = summary[summary["probe_role"] == "stabilization_guard"]
    direct_pass = float(direct["role_contract_pass_rate"].iloc[0]) if not direct.empty else 0.0
    stab_pass = float(stab["role_contract_pass_rate"].iloc[0]) if not stab.empty else 0.0

    return {
        "task": PATCH_VERSION,
        "status": "completed",
        "patched_action_frame_rows": int(len(frame)),
        "original_target_rows_split": int(table["rows"].sum() / 2) if not table.empty else 0,
        "role_split_rows": int(table["rows"].sum()) if not table.empty else 0,
        "alignment_rows": int(len(alignment)),
        "direct_probe_restraint_role_pass_rate": direct_pass,
        "stabilization_guard_role_pass_rate": stab_pass,
        "direct_probe_old_contract_score": float(direct["old_contract_mean_score"].iloc[0]) if not direct.empty else 0.0,
        "stabilization_patched_contract_score": float(stab["patched_contract_mean_score"].iloc[0]) if not stab.empty else 0.0,
        "role_summary": summary.to_dict(orient="records"),
        "primary_conclusion": "sandbox_probe_entry_down is now split into direct probe-restraint and stabilization guard roles.",
        "dept_pressure_tuning_readiness": "not_ready_coupling_sequence_repair_still_required",
        "next_recommended_task": "CouplingReliefStagedUnlockRepair_RC1",
        "all_sanity_checks_passed": bool(
            int(summary["probe_role"].nunique()) == 2
            and direct_pass >= 1.0
            and stab_pass >= 1.0
        ),
    }
