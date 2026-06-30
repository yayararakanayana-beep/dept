"""DiagnosticPrimitiveMappingRepair RC1.

Repairs the diagnostic primitive/channel mapping for semantic effects that were
observable but misaligned in DiagnosticClosedLoopRerunReview_RC1.

Scope:
    - sensitivity_opening
    - exploration_attempt_frequency_down
    - update_frequency_down

Boundary:
    This does not edit H-DEPT pressure generation.
    This does not repair coupling_relief -> staged_unlock.
    This does not revise expected-effect contracts.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple
import re
import json
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


REPAIR_VERSION = "DiagnosticPrimitiveMappingRepair_RC1"

DETAIL_RE = re.compile(r"([A-Za-z_]+):expected=([-0-9.]+)")


@dataclass(frozen=True)
class MappingRepairConfig:
    n_entities: int = 18
    action_coupling: float = 0.045
    noise_scale: float = 0.018
    drift_scale: float = 0.006
    alignment_threshold: float = 0.50
    min_observed_abs: float = 1e-9


REPAIR_RULES: Dict[str, Dict[str, str]] = {
    # Expected: exploration up, uncertainty up, overconvergence down.
    # Old channel coupling_relief lowered coupling/lock but did not open
    # exploration/uncertainty.  Exploration injection expresses opening better.
    "sensitivity_opening": {
        "old_action_channel": "coupling_relief",
        "new_action_primitive": "diagnostic_sensitivity_opening_probe_v2",
        "new_primitive_sequence": "sensitivity_opening -> exploratory_response_probe -> observe -> report",
        "new_action_channel": "exploration_injection",
        "repair_reason": "opening semantics need exploration/uncertainty response, not only coupling relief",
    },

    # Expected: exploration down, uncertainty down, overconvergence up.
    # Existing buffer_increase lowers uncertainty but does not lower exploration
    # or raise overconvergence.  Use validation-only diagnostic restraint channel.
    "exploration_attempt_frequency_down": {
        "old_action_channel": "buffer_increase",
        "new_action_primitive": "diagnostic_exploration_restraint_v2",
        "new_primitive_sequence": "exploration_restraint -> reduce_exploration_attempt -> observe -> report",
        "new_action_channel": "diagnostic_exploration_restraint",
        "repair_reason": "restraint semantics need direct exploration reduction plus uncertainty reduction",
    },

    # Expected: exploration down, uncertainty down, overconvergence up.
    # Existing buffer route is too generic. Use a diagnostic update-restraint
    # channel with explicit exploration/uncertainty restraint.
    "update_frequency_down": {
        "old_action_channel": "buffer_increase",
        "new_action_primitive": "diagnostic_update_restraint_v2",
        "new_primitive_sequence": "update_restraint -> reduce_update_churn -> observe -> report",
        "new_action_channel": "diagnostic_update_restraint",
        "repair_reason": "update restraint needs explicit exploration/update-churn reduction, not generic buffer only",
    },
}


def _safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _expected_map_from_semantic_outcome(semantic_outcome: pd.DataFrame) -> Dict[str, Dict[str, int]]:
    out: Dict[str, Dict[str, int]] = {}
    if semantic_outcome is None or semantic_outcome.empty:
        return out
    for effect, grp in semantic_outcome.groupby("semantic_effect"):
        votes: Dict[str, list[int]] = {}
        for details in grp.get("semantic_outcome_details", pd.Series(dtype=str)).dropna().astype(str):
            for feat, sign_s in DETAIL_RE.findall(details):
                try:
                    sign = int(float(sign_s))
                except ValueError:
                    continue
                votes.setdefault(feat, []).append(sign)
        feat_map = {}
        for feat, vals in votes.items():
            if vals:
                feat_map[feat] = 1 if float(np.mean(vals)) >= 0 else -1
        out[str(effect)] = feat_map
    return out


def _match_expected(expected: Dict[str, int], observed: Dict[str, float], threshold: float, min_abs: float) -> Tuple[float, bool, str, int]:
    if not expected:
        return 0.0, False, "no_expected_contract", 0
    hits = 0
    details = []
    for feat, sign in expected.items():
        key = f"observed_delta_{feat}"
        val = float(observed.get(key, 0.0))
        match = abs(val) >= min_abs and np.sign(val) == np.sign(sign)
        hits += int(match)
        details.append(f"{feat}:expected={sign},observed={val:.6f},match={bool(match)}")
    rate = float(hits / max(len(expected), 1))
    return rate, bool(rate >= threshold), "; ".join(details), len(expected)


def repair_action_frame(action_frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    if action_frame is None or action_frame.empty:
        return pd.DataFrame(), pd.DataFrame()

    repaired = action_frame.copy()
    rows = []

    for effect, rule in REPAIR_RULES.items():
        mask = repaired["semantic_effect"].astype(str) == effect
        if not mask.any():
            continue
        old_primitives = sorted(set(repaired.loc[mask, "action_primitive"].dropna().astype(str)))
        old_sequences = sorted(set(repaired.loc[mask, "primitive_sequence"].dropna().astype(str)))
        old_channels = sorted(set(repaired.loc[mask, "action_channel"].dropna().astype(str)))

        for col, value in [
            ("diagnostic_action_primitive", rule["new_action_primitive"]),
            ("diagnostic_primitive_sequence", rule["new_primitive_sequence"]),
            ("diagnostic_action_channel", rule["new_action_channel"]),
            ("action_primitive", rule["new_action_primitive"]),
            ("primitive_sequence", rule["new_primitive_sequence"]),
            ("action_channel", rule["new_action_channel"]),
        ]:
            if col in repaired.columns:
                repaired.loc[mask, col] = value

        repaired.loc[mask, "mapping_repair_applied"] = True
        repaired.loc[mask, "mapping_repair_version"] = REPAIR_VERSION
        repaired.loc[mask, "mapping_repair_reason"] = rule["repair_reason"]

        rows.append({
            "semantic_effect": effect,
            "rows_repaired": int(mask.sum()),
            "old_action_primitives": "|".join(old_primitives),
            "old_primitive_sequences": "|".join(old_sequences),
            "old_action_channels": "|".join(old_channels),
            "new_action_primitive": rule["new_action_primitive"],
            "new_primitive_sequence": rule["new_primitive_sequence"],
            "new_action_channel": rule["new_action_channel"],
            "repair_reason": rule["repair_reason"],
            "repair_contract": REPAIR_VERSION + "__semantic_to_diagnostic_primitive_mapping",
        })

    if "mapping_repair_applied" not in repaired.columns:
        repaired["mapping_repair_applied"] = False
    else:
        repaired["mapping_repair_applied"] = repaired["mapping_repair_applied"].fillna(False).astype(bool)

    if "mapping_repair_version" not in repaired.columns:
        repaired["mapping_repair_version"] = ""
    else:
        repaired["mapping_repair_version"] = repaired["mapping_repair_version"].fillna("")
    if "mapping_repair_reason" not in repaired.columns:
        repaired["mapping_repair_reason"] = ""
    else:
        repaired["mapping_repair_reason"] = repaired["mapping_repair_reason"].fillna("")

    return repaired, pd.DataFrame(rows)


def _make_world(seed: int, scenario: str, cfg: MappingRepairConfig) -> PseudoRealitySystem:
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
    ar = action_rows.reset_index(drop=True)
    for i, row in ar.iterrows():
        rows.append({
            **row.to_dict(),
            "entity_id": entities[i % len(entities)],
            "action_channel": row.get("action_channel", row.get("diagnostic_action_channel", "no_op")),
            "action_strength": float(row.get("action_strength", row.get("diagnostic_action_strength", 0.0))),
            "direction": 1,
        })
    return pd.DataFrame(rows)


def _apply_extended_diagnostic_channels(world: PseudoRealitySystem, action_frame: pd.DataFrame) -> None:
    """Apply validation-only channels not supported by base PseudoRealitySystem.

    This is deliberately local to the repair/rerun task, rather than changing
    upper H-DEPT inputs. It remains action-module-side pseudo-reality actuation.
    """
    if action_frame is None or action_frame.empty:
        return
    e = world.entities.copy()
    cfg = world.config
    for _, row in action_frame.iterrows():
        ch = str(row.get("action_channel", ""))
        if ch not in {"diagnostic_exploration_restraint", "diagnostic_update_restraint"}:
            continue
        idx = e["entity_id"] == row["entity_id"]
        if not idx.any():
            continue
        strength = float(np.clip(row.get("action_strength", 0.0), 0.0, 1.0)) * cfg.action_coupling
        if ch == "diagnostic_exploration_restraint":
            e.loc[idx, "exploration"] -= strength
            e.loc[idx, "uncertainty"] -= strength * 0.45
            e.loc[idx, "entropy"] -= strength * 0.30
            e.loc[idx, "relation_lock"] += strength * 0.10
        elif ch == "diagnostic_update_restraint":
            e.loc[idx, "exploration"] -= strength * 0.75
            e.loc[idx, "uncertainty"] -= strength * 0.65
            e.loc[idx, "entropy"] -= strength * 0.25
            e.loc[idx, "relation_lock"] += strength * 0.08
    for feat in STATE_FEATURES:
        e[feat] = np.clip(e[feat], 0.02, 0.98)
    world.entities = e


def _step_with_extended_actions(world: PseudoRealitySystem, action_frame: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    if action_frame is None or action_frame.empty:
        return world.step(None)
    extended_channels = {"diagnostic_exploration_restraint", "diagnostic_update_restraint"}
    base_af = action_frame[~action_frame["action_channel"].isin(extended_channels)].copy()
    ext_af = action_frame[action_frame["action_channel"].isin(extended_channels)].copy()
    trace = world.step(base_af if not base_af.empty else None)
    if not ext_af.empty:
        _apply_extended_diagnostic_channels(world, ext_af)
        trace = world.emit_trace()
    return trace


def run_repaired_isolated_replay(
    repaired_actions: pd.DataFrame,
    semantic_outcome: pd.DataFrame,
    cfg: MappingRepairConfig,
) -> pd.DataFrame:
    if repaired_actions.empty:
        return pd.DataFrame()
    expected_map = _expected_map_from_semantic_outcome(semantic_outcome)
    rows = []
    group_cols = ["run_seed", "run_scenario", "loop_step", "semantic_effect"]

    for (seed, scenario, step, effect), group in repaired_actions.groupby(group_cols, dropna=False):
        active = _make_world(int(seed), str(scenario), cfg)
        baseline = _make_world(int(seed), str(scenario), cfg)
        _advance_to_step(active, int(step))
        _advance_to_step(baseline, int(step))
        af = _prepare_actions(group.copy(), active)
        active_trace = _step_with_extended_actions(active, af)
        baseline_trace = baseline.step(None)
        d = delta_summary(summarize_trace(active_trace), summarize_trace(baseline_trace))
        expected = expected_map.get(str(effect), {})
        score, passed, details, n_expected = _match_expected(expected, d, cfg.alignment_threshold, cfg.min_observed_abs)
        row = {
            "rerun_scope": "repaired_isolated_semantic",
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
            "mapping_repair_applied": bool(group.get("mapping_repair_applied", pd.Series([False])).fillna(False).astype(bool).any()),
            "expected_feature_count": int(n_expected),
            "repaired_alignment_score": float(score),
            "repaired_alignment_pass": bool(passed),
            "repaired_alignment_details": details,
            "repaired_outcome_verdict": "repaired_semantic_aligned" if passed else "repaired_semantic_misaligned",
            "repair_rerun_contract": REPAIR_VERSION + "__repaired_mapping_isolated_semantic_vs_no_action_baseline",
        }
        row.update(d)
        rows.append(row)
    return pd.DataFrame(rows)


def summarize_repaired_alignment(isolated: pd.DataFrame) -> pd.DataFrame:
    if isolated is None or isolated.empty:
        return pd.DataFrame()
    return isolated.groupby(["semantic_effect", "intent_family"], as_index=False).agg(
        rows=("semantic_effect", "size"),
        mapping_repair_applied_rate=("mapping_repair_applied", "mean"),
        repaired_mean_alignment_score=("repaired_alignment_score", "mean"),
        repaired_alignment_pass_rate=("repaired_alignment_pass", "mean"),
        repaired_mean_action_mass=("action_mass", "mean"),
        repaired_action_primitives=("action_primitive", lambda s: "|".join(sorted(set(s.dropna().astype(str))))),
        repaired_action_channels=("action_channel", lambda s: "|".join(sorted(set(s.dropna().astype(str))))),
        repaired_mean_delta_conflict=("observed_delta_conflict", "mean"),
        repaired_mean_delta_uncertainty=("observed_delta_uncertainty", "mean"),
        repaired_mean_delta_exploration=("observed_delta_exploration", "mean"),
        repaired_mean_delta_overconvergence=("observed_delta_overconvergence", "mean"),
        repaired_mean_delta_m_overall=("observed_delta_m_overall", "mean"),
        repaired_dominant_verdict=("repaired_outcome_verdict", lambda s: str(s.value_counts().index[0]) if len(s) else "none"),
    ).sort_values(["mapping_repair_applied_rate", "repaired_alignment_pass_rate", "repaired_mean_alignment_score"], ascending=[False, False, False])


def build_comparison(old_summary: pd.DataFrame, repaired_summary: pd.DataFrame) -> pd.DataFrame:
    if repaired_summary is None or repaired_summary.empty:
        return pd.DataFrame()
    old = old_summary.copy() if old_summary is not None else pd.DataFrame()
    if old.empty:
        comp = repaired_summary.copy()
        comp["old_alignment_pass_rate"] = np.nan
        comp["old_mean_alignment_score"] = np.nan
    else:
        keep = ["semantic_effect", "alignment_pass_rate", "mean_alignment_score", "action_channels", "action_primitives"]
        old = old[[c for c in keep if c in old.columns]].rename(columns={
            "alignment_pass_rate": "old_alignment_pass_rate",
            "mean_alignment_score": "old_mean_alignment_score",
            "action_channels": "old_action_channels",
            "action_primitives": "old_action_primitives",
        })
        comp = repaired_summary.merge(old, on="semantic_effect", how="left")
    comp["alignment_pass_rate_delta"] = comp["repaired_alignment_pass_rate"] - comp["old_alignment_pass_rate"].fillna(0.0)
    comp["alignment_score_delta"] = comp["repaired_mean_alignment_score"] - comp["old_mean_alignment_score"].fillna(0.0)
    comp["comparison_verdict"] = np.where(
        comp["alignment_pass_rate_delta"] > 0,
        "improved",
        np.where(comp["mapping_repair_applied_rate"] > 0, "not_improved", "unchanged_non_target")
    )
    return comp.sort_values(["mapping_repair_applied_rate", "alignment_pass_rate_delta", "alignment_score_delta"], ascending=[False, False, False])


def build_outputs_from_results_dir(results_dir: str | Path, cfg: MappingRepairConfig | None = None) -> Dict[str, pd.DataFrame]:
    cfg = cfg or MappingRepairConfig()
    results = Path(results_dir)
    action_frame = _safe_read_csv(results / "diagnostic_action_translation_policy_action_frame_RC1.csv")
    semantic_outcome = _safe_read_csv(results / "pressure_semantic_outcome_alignment_RC1.csv")
    old_summary = _safe_read_csv(results / "diagnostic_closed_loop_semantic_summary_RC1.csv")

    repaired_frame, repair_table = repair_action_frame(action_frame)
    isolated = run_repaired_isolated_replay(repaired_frame, semantic_outcome, cfg)
    repaired_summary = summarize_repaired_alignment(isolated)
    comparison = build_comparison(old_summary, repaired_summary)
    target_comparison = comparison[comparison["mapping_repair_applied_rate"] > 0].copy() if not comparison.empty else pd.DataFrame()

    return {
        "diagnostic_primitive_mapping_repair_table": repair_table,
        "diagnostic_primitive_mapping_repaired_action_frame": repaired_frame,
        "diagnostic_primitive_mapping_repair_isolated_alignment": isolated,
        "diagnostic_primitive_mapping_repair_semantic_summary": repaired_summary,
        "diagnostic_primitive_mapping_repair_comparison": comparison,
        "diagnostic_primitive_mapping_repair_target_comparison": target_comparison,
    }


def repair_summary_json(outputs: Dict[str, pd.DataFrame]) -> dict:
    repair_table = outputs.get("diagnostic_primitive_mapping_repair_table", pd.DataFrame())
    repaired_frame = outputs.get("diagnostic_primitive_mapping_repaired_action_frame", pd.DataFrame())
    isolated = outputs.get("diagnostic_primitive_mapping_repair_isolated_alignment", pd.DataFrame())
    repaired_summary = outputs.get("diagnostic_primitive_mapping_repair_semantic_summary", pd.DataFrame())
    comp = outputs.get("diagnostic_primitive_mapping_repair_comparison", pd.DataFrame())
    target = outputs.get("diagnostic_primitive_mapping_repair_target_comparison", pd.DataFrame())

    if isolated.empty:
        return {"task": REPAIR_VERSION, "status": "empty", "all_sanity_checks_passed": False}

    target_improved = int((target["comparison_verdict"] == "improved").sum()) if not target.empty else 0
    target_count = int(target["semantic_effect"].nunique()) if not target.empty else 0
    target_pass_after = float(target["repaired_alignment_pass_rate"].mean()) if not target.empty else 0.0
    target_pass_before = float(target["old_alignment_pass_rate"].mean()) if not target.empty else 0.0

    return {
        "task": REPAIR_VERSION,
        "status": "completed",
        "repaired_semantic_targets": repair_table["semantic_effect"].astype(str).tolist() if not repair_table.empty else [],
        "repaired_rows": int(repair_table["rows_repaired"].sum()) if not repair_table.empty else 0,
        "repaired_action_frame_rows": int(len(repaired_frame)),
        "isolated_alignment_rows": int(len(isolated)),
        "semantic_effect_count": int(isolated["semantic_effect"].nunique()),
        "overall_old_pass_rate": float(comp["old_alignment_pass_rate"].mean()) if not comp.empty else 0.0,
        "overall_repaired_pass_rate": float(comp["repaired_alignment_pass_rate"].mean()) if not comp.empty else 0.0,
        "target_old_pass_rate": target_pass_before,
        "target_repaired_pass_rate": target_pass_after,
        "target_pass_rate_delta": float(target_pass_after - target_pass_before),
        "target_improved_count": target_improved,
        "target_count": target_count,
        "target_comparison": target.to_dict(orient="records") if not target.empty else [],
        "non_target_ready_preserved_rate": float(
            comp.loc[comp["mapping_repair_applied_rate"] == 0, "repaired_alignment_pass_rate"].mean()
        ) if not comp.empty and (comp["mapping_repair_applied_rate"] == 0).any() else 0.0,
        "primary_conclusion": "Target primitive mappings were repaired and rerun; target alignment should be reviewed before expected-effect contract changes.",
        "dept_pressure_tuning_readiness": "not_ready_expected_contract_review_still_required",
        "next_recommended_task": "ExpectedEffectContractReview_RC1",
        "all_sanity_checks_passed": bool(
            len(isolated) > 0
            and target_count >= 3
            and target_improved >= 2
            and int(repaired_frame.get("mapping_repair_applied", pd.Series(dtype=bool)).fillna(False).sum()) > 0
        ),
    }
