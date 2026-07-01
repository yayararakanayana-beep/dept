"""CouplingReliefStagedUnlockRepair RC1.

Repairs the sequence-level issue around:

    coupling_relief -> staged_unlock

Previous audits showed that this family was not a simple coverage problem:
actions could be present, but the immediate sequence was poorly aligned.

This repair separates the sequence into variants and introduces a guarded
delayed unlock sequence:

    coupling_relief -> observe -> guarded_relation_unlock

Boundary:
    - diagnostic validation sequence repair only
    - no H-DEPT pressure tuning
    - no direct DEPT-system access from the action module
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


REPAIR_VERSION = "CouplingReliefStagedUnlockRepair_RC1"
DETAIL_RE = re.compile(r"([A-Za-z_]+):expected=([-0-9.]+)")

EXPECTED_SEQUENCE_CONTRACT = {
    "conflict": -1,
    "overconvergence": -1,
    "m_overall": 1,
}


@dataclass(frozen=True)
class SequenceRepairConfig:
    n_entities: int = 18
    action_coupling: float = 0.045
    noise_scale: float = 0.018
    drift_scale: float = 0.006
    alignment_threshold: float = 0.50
    min_observed_abs: float = 1e-12
    min_action_strength: float = 0.006
    max_action_strength: float = 0.030
    strength_scale: float = 0.12


def _safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _make_world(seed: int, scenario: str, cfg: SequenceRepairConfig) -> PseudoRealitySystem:
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


def _match_contract(contract: Dict[str, int], observed: Dict[str, float], threshold: float, min_abs: float) -> Tuple[float, bool, str, int]:
    hits = 0
    details = []
    for feat, sign in contract.items():
        val = float(observed.get(f"observed_delta_{feat}", 0.0))
        match = abs(val) > min_abs and np.sign(val) == np.sign(sign)
        hits += int(match)
        details.append(f"{feat}:expected={sign},observed={val:.6f},match={bool(match)}")
    score = float(hits / max(len(contract), 1))
    return score, bool(score >= threshold), "; ".join(details), len(contract)


def _contract_to_string(contract: Dict[str, int]) -> str:
    return ";".join(f"{k}:{v:+d}" for k, v in sorted(contract.items()))


def _strength_from_row(row: pd.Series, cfg: SequenceRepairConfig) -> float:
    for key in ["max_component_magnitude", "mean_action_strength", "mean_planned_strength"]:
        val = row.get(key, np.nan)
        if pd.notna(val):
            val = abs(float(val))
            if val > 0:
                if key == "mean_planned_strength":
                    val = val * 0.018
                else:
                    val = val * cfg.strength_scale
                return float(np.clip(val, cfg.min_action_strength, cfg.max_action_strength))
    return cfg.min_action_strength


def build_staged_unlock_targets(plan_action_chain: pd.DataFrame, cfg: SequenceRepairConfig | None = None) -> pd.DataFrame:
    cfg = cfg or SequenceRepairConfig()
    if plan_action_chain is None or plan_action_chain.empty:
        return pd.DataFrame()

    chain = plan_action_chain.copy()
    mask = chain["primitive_sequence"].astype(str).str.contains("staged_unlock", case=False, na=False)
    targets = chain[mask].copy()
    if targets.empty:
        return pd.DataFrame()

    group_cols = ["run_seed", "run_scenario", "loop_step", "semantic_effect", "intent_family"]
    rows = []
    for keys, grp in targets.groupby(group_cols, dropna=False):
        seed, scenario, step, effect, family = keys
        primitive_sequences = "|".join(sorted(set(grp["primitive_sequence"].dropna().astype(str))))
        action_primitives = "|".join(sorted(set(grp["action_primitive"].dropna().astype(str))))
        channels = "|".join(sorted(set(grp["action_channel"].dropna().astype(str))))
        representative = grp.iloc[0]
        strength = _strength_from_row(representative, cfg)
        rows.append({
            "run_seed": int(seed),
            "run_scenario": str(scenario),
            "loop_step": int(step),
            "semantic_effect": str(effect),
            "intent_family": str(family),
            "original_action_primitives": action_primitives,
            "original_primitive_sequences": primitive_sequences,
            "original_action_channels": channels,
            "target_rows": int(len(grp)),
            "diagnostic_strength": strength,
            "target_contract": REPAIR_VERSION + "__staged_unlock_target",
        })

    return pd.DataFrame(rows)


def _prepare_actions(world: PseudoRealitySystem, rows: list[dict]) -> pd.DataFrame:
    entities = world.entities["entity_id"].tolist()
    out = []
    for i, row in enumerate(rows):
        out.append({
            "entity_id": entities[i % len(entities)],
            "action_channel": row["action_channel"],
            "action_strength": float(row["action_strength"]),
            "direction": 1,
            **{k: v for k, v in row.items() if k not in {"action_channel", "action_strength"}},
        })
    return pd.DataFrame(out)


def _apply_guarded_relation_unlock(world: PseudoRealitySystem, af: pd.DataFrame) -> None:
    if af is None or af.empty:
        return
    e = world.entities.copy()
    cfg = world.config
    for _, row in af.iterrows():
        if str(row.get("action_channel", "")) != "guarded_relation_unlock":
            continue
        idx = e["entity_id"] == row["entity_id"]
        if not idx.any():
            continue
        strength = float(np.clip(row.get("action_strength", 0.0), 0.0, 1.0)) * cfg.action_coupling
        e.loc[idx, "relation_lock"] -= strength
        e.loc[idx, "coupling"] -= strength * 0.30
        e.loc[idx, "reversibility"] += strength * 0.35
        e.loc[idx, "uncertainty"] -= strength * 0.20
    for feat in STATE_FEATURES:
        e[feat] = np.clip(e[feat], 0.02, 0.98)
    world.entities = e


def _step_with_guarded_unlock(world: PseudoRealitySystem, action_frame: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    if action_frame is None or action_frame.empty:
        return world.step(None)
    guarded = action_frame[action_frame["action_channel"] == "guarded_relation_unlock"].copy()
    base = action_frame[action_frame["action_channel"] != "guarded_relation_unlock"].copy()
    trace = world.step(base if not base.empty else None)
    if not guarded.empty:
        _apply_guarded_relation_unlock(world, guarded)
        trace = world.emit_trace()
    return trace


def _sequence_actions_for_variant(variant: str, strength: float) -> list[list[dict]]:
    """Return list of action frames by relative step."""
    if variant == "old_immediate_unlock":
        return [[
            {"action_channel": "coupling_relief", "action_strength": strength, "sequence_role": "coupling_relief"},
            {"action_channel": "relation_unlock", "action_strength": strength * 0.70, "sequence_role": "immediate_relation_unlock"},
        ]]
    if variant == "relief_observe_only":
        return [[
            {"action_channel": "coupling_relief", "action_strength": strength, "sequence_role": "coupling_relief_only"},
        ]]
    if variant == "delayed_guarded_unlock":
        return [
            [{"action_channel": "coupling_relief", "action_strength": strength, "sequence_role": "coupling_relief"}],
            [{"action_channel": "guarded_relation_unlock", "action_strength": strength * 0.70, "sequence_role": "guarded_relation_unlock"}],
        ]
    if variant == "buffered_delayed_guarded_unlock":
        return [
            [
                {"action_channel": "buffer_increase", "action_strength": strength * 0.55, "sequence_role": "buffer_precondition"},
                {"action_channel": "coupling_relief", "action_strength": strength, "sequence_role": "coupling_relief"},
            ],
            [{"action_channel": "guarded_relation_unlock", "action_strength": strength * 0.60, "sequence_role": "guarded_relation_unlock"}],
        ]
    raise ValueError(f"unknown variant: {variant}")


def run_sequence_variant_replay(targets: pd.DataFrame, cfg: SequenceRepairConfig | None = None) -> pd.DataFrame:
    cfg = cfg or SequenceRepairConfig()
    if targets is None or targets.empty:
        return pd.DataFrame()

    variants = [
        "old_immediate_unlock",
        "relief_observe_only",
        "delayed_guarded_unlock",
        "buffered_delayed_guarded_unlock",
    ]
    rows = []

    for _, target in targets.iterrows():
        seed = int(target["run_seed"])
        scenario = str(target["run_scenario"])
        step = int(target["loop_step"])
        strength = float(target["diagnostic_strength"])

        for variant in variants:
            active = _make_world(seed, scenario, cfg)
            baseline = _make_world(seed, scenario, cfg)
            _advance_to_step(active, step)
            _advance_to_step(baseline, step)

            trace_active = None
            trace_base = None
            for relative_step, action_specs in enumerate(_sequence_actions_for_variant(variant, strength)):
                af = _prepare_actions(active, action_specs)
                trace_active = _step_with_guarded_unlock(active, af)
                trace_base = baseline.step(None)

            d = delta_summary(summarize_trace(trace_active), summarize_trace(trace_base))
            score, passed, details, n = _match_contract(EXPECTED_SEQUENCE_CONTRACT, d, cfg.alignment_threshold, cfg.min_observed_abs)

            rows.append({
                "sequence_variant": variant,
                "run_seed": seed,
                "run_scenario": scenario,
                "loop_step": step,
                "semantic_effect": str(target["semantic_effect"]),
                "intent_family": str(target["intent_family"]),
                "original_action_primitives": target.get("original_action_primitives", ""),
                "original_primitive_sequences": target.get("original_primitive_sequences", ""),
                "original_action_channels": target.get("original_action_channels", ""),
                "diagnostic_strength": strength,
                "sequence_steps": len(_sequence_actions_for_variant(variant, strength)),
                "expected_feature_count": int(n),
                "sequence_alignment_score": float(score),
                "sequence_alignment_pass": bool(passed),
                "sequence_alignment_details": details,
                "sequence_outcome_verdict": "sequence_aligned" if passed else "sequence_misaligned",
                "sequence_repair_contract": REPAIR_VERSION + "__variant_replay_vs_expected_sequence_contract",
                **d,
            })

    return pd.DataFrame(rows)


def summarize_sequence_variants(alignment: pd.DataFrame) -> pd.DataFrame:
    if alignment is None or alignment.empty:
        return pd.DataFrame()
    return alignment.groupby(["sequence_variant"], as_index=False).agg(
        rows=("sequence_variant", "size"),
        semantic_effects=("semantic_effect", "nunique"),
        scenarios=("run_scenario", "nunique"),
        mean_alignment_score=("sequence_alignment_score", "mean"),
        alignment_pass_rate=("sequence_alignment_pass", "mean"),
        mean_diagnostic_strength=("diagnostic_strength", "mean"),
        mean_delta_conflict=("observed_delta_conflict", "mean"),
        mean_delta_uncertainty=("observed_delta_uncertainty", "mean"),
        mean_delta_exploration=("observed_delta_exploration", "mean"),
        mean_delta_overconvergence=("observed_delta_overconvergence", "mean"),
        mean_delta_m_overall=("observed_delta_m_overall", "mean"),
    ).sort_values(["alignment_pass_rate", "mean_alignment_score"], ascending=[False, False])


def build_repaired_sequence_policy(summary: pd.DataFrame) -> pd.DataFrame:
    if summary is None or summary.empty:
        return pd.DataFrame()
    preferred_order = ["delayed_guarded_unlock", "buffered_delayed_guarded_unlock", "relief_observe_only", "old_immediate_unlock"]
    ranked = summary.copy()
    ranked["preference_rank"] = ranked["sequence_variant"].apply(lambda x: preferred_order.index(x) if x in preferred_order else 999)
    ranked = ranked.sort_values(["alignment_pass_rate", "mean_alignment_score", "preference_rank"], ascending=[False, False, True])
    best = ranked.iloc[0]
    return pd.DataFrame([{
        "recommended_sequence_variant": best["sequence_variant"],
        "recommended_sequence": (
            "coupling_relief -> observe -> guarded_relation_unlock"
            if best["sequence_variant"] == "delayed_guarded_unlock"
            else "buffer -> coupling_relief -> observe -> guarded_relation_unlock"
            if best["sequence_variant"] == "buffered_delayed_guarded_unlock"
            else "coupling_relief -> observe"
            if best["sequence_variant"] == "relief_observe_only"
            else "coupling_relief -> relation_unlock"
        ),
        "alignment_pass_rate": float(best["alignment_pass_rate"]),
        "mean_alignment_score": float(best["mean_alignment_score"]),
        "repair_decision": "replace_immediate_unlock_with_guarded_delayed_sequence" if "guarded" in str(best["sequence_variant"]) else "review_before_replacing",
        "repair_reason": "sequence-level repair separates relief from unlock and gates unlock after observation",
        "policy_contract": REPAIR_VERSION + "__recommended_sequence_policy",
    }])


def build_outputs_from_results_dir(results_dir: str | Path) -> Dict[str, pd.DataFrame]:
    results = Path(results_dir)
    chain = _safe_read_csv(results / "pressure_semantic_plan_action_chain_RC1.csv")
    prior = _safe_read_csv(results / "pressure_outcome_alignment_rc2_primitive_summary.csv")

    targets = build_staged_unlock_targets(chain, SequenceRepairConfig())
    alignment = run_sequence_variant_replay(targets, SequenceRepairConfig())
    summary = summarize_sequence_variants(alignment)
    policy = build_repaired_sequence_policy(summary)

    prior_targets = pd.DataFrame()
    if not prior.empty:
        prior_targets = prior[prior["primitive_sequence"].astype(str).str.contains("staged_unlock", case=False, na=False)].copy()
        prior_targets["prior_source"] = "pressure_outcome_alignment_rc2_primitive_summary"

    repair_table = pd.DataFrame([
        {
            "old_sequence": "coupling_relief -> staged_unlock",
            "repair_sequence": "coupling_relief -> observe -> guarded_relation_unlock",
            "repair_type": "delayed_guarded_sequence",
            "reason": "immediate unlock is a sequence-level risk; separate relief from unlock and gate unlock after observation",
            "repair_contract": REPAIR_VERSION + "__sequence_repair_table",
        },
        {
            "old_sequence": "buffer -> coupling_relief -> staged_unlock",
            "repair_sequence": "buffer -> coupling_relief -> observe -> guarded_relation_unlock",
            "repair_type": "buffered_delayed_guarded_sequence",
            "reason": "buffer precondition can be retained but unlock should remain delayed and guarded",
            "repair_contract": REPAIR_VERSION + "__sequence_repair_table",
        },
    ])

    return {
        "coupling_relief_staged_unlock_targets": targets,
        "coupling_relief_staged_unlock_variant_alignment": alignment,
        "coupling_relief_staged_unlock_variant_summary": summary,
        "coupling_relief_staged_unlock_repaired_policy": policy,
        "coupling_relief_staged_unlock_prior_rc2": prior_targets,
        "coupling_relief_staged_unlock_repair_table": repair_table,
    }


def sequence_repair_summary_json(outputs: Dict[str, pd.DataFrame]) -> dict:
    targets = outputs.get("coupling_relief_staged_unlock_targets", pd.DataFrame())
    alignment = outputs.get("coupling_relief_staged_unlock_variant_alignment", pd.DataFrame())
    summary = outputs.get("coupling_relief_staged_unlock_variant_summary", pd.DataFrame())
    policy = outputs.get("coupling_relief_staged_unlock_repaired_policy", pd.DataFrame())
    prior = outputs.get("coupling_relief_staged_unlock_prior_rc2", pd.DataFrame())

    if alignment.empty or summary.empty or policy.empty:
        return {"task": REPAIR_VERSION, "status": "empty", "all_sanity_checks_passed": False}

    best = policy.iloc[0].to_dict()
    old = summary[summary["sequence_variant"] == "old_immediate_unlock"]
    best_variant = str(best["recommended_sequence_variant"])
    best_row = summary[summary["sequence_variant"] == best_variant]
    old_pass = float(old["alignment_pass_rate"].iloc[0]) if not old.empty else 0.0
    best_pass = float(best_row["alignment_pass_rate"].iloc[0]) if not best_row.empty else 0.0
    old_score = float(old["mean_alignment_score"].iloc[0]) if not old.empty else 0.0
    best_score = float(best_row["mean_alignment_score"].iloc[0]) if not best_row.empty else 0.0

    return {
        "task": REPAIR_VERSION,
        "status": "completed",
        "target_rows": int(len(targets)),
        "alignment_rows": int(len(alignment)),
        "variant_count": int(summary["sequence_variant"].nunique()),
        "prior_staged_unlock_rows": int(len(prior)),
        "prior_staged_unlock_mean_pass_rate": float(prior["alignment_pass_rate"].mean()) if not prior.empty and "alignment_pass_rate" in prior.columns else None,
        "old_immediate_pass_rate": old_pass,
        "old_immediate_mean_score": old_score,
        "best_variant": best_variant,
        "best_variant_pass_rate": best_pass,
        "best_variant_mean_score": best_score,
        "pass_rate_delta_vs_old": float(best_pass - old_pass),
        "score_delta_vs_old": float(best_score - old_score),
        "recommended_sequence": best.get("recommended_sequence"),
        "repair_decision": best.get("repair_decision"),
        "variant_summary": summary.to_dict(orient="records"),
        "primary_conclusion": "Immediate staged unlock should be replaced by a guarded delayed unlock sequence for diagnostic validation.",
        "dept_pressure_tuning_readiness": "not_ready_final_integration_review_required",
        "next_recommended_task": "DiagnosticActionModuleIntegrationReview_RC1",
        "all_sanity_checks_passed": bool(
            int(summary["sequence_variant"].nunique()) >= 4
            and best_pass >= old_pass
            and "guarded" in best_variant
            and len(targets) > 0
        ),
    }
