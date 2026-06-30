"""DiagnosticClosedLoopRerun RC1.

Actually reruns pseudo-reality using DiagnosticActionTranslationPolicy_RC1 weak
diagnostic actions.

RC2b confirmed diagnostic action coverage but outcome attribution was pending.
This module performs the missing pseudo-reality replay.

It provides:
    - combined diagnostic rerun: all diagnostic actions per scenario/step
    - isolated semantic rerun: one semantic_effect group at a time
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


RERUN_VERSION = "DiagnosticClosedLoopRerun_RC1"

DETAIL_RE = re.compile(r"([A-Za-z_]+):expected=([-0-9.]+)")


@dataclass(frozen=True)
class DiagnosticRerunConfig:
    n_entities: int = 18
    action_coupling: float = 0.045
    noise_scale: float = 0.018
    drift_scale: float = 0.006
    alignment_threshold: float = 0.50
    min_observed_abs: float = 1e-9
    max_steps: int | None = None


def _safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def summarize_trace(trace: Dict[str, pd.DataFrame]) -> Dict[str, float]:
    e = trace["entity_trace"]
    summary = {feat: float(e[feat].mean()) for feat in STATE_FEATURES if feat in e.columns}
    conflict = float((e["volatility"] + e["uncertainty"] + e["relation_lock"] + e["coupling"]).mean() / 4.0)
    overconvergence = float((e["relation_lock"] + e["coupling"] - e["exploration"] - e["entropy"]).mean() / 2.0)
    m_overall = float(
        (e["exploration"] + e["reversibility"] + e["entropy"]).mean()
        - (e["volatility"] + e["uncertainty"] + e["relation_lock"] + e["coupling"]).mean() / 4.0
    )
    summary.update({
        "conflict": conflict,
        "overconvergence": overconvergence,
        "m_overall": m_overall,
    })
    return summary


def delta_summary(active: Dict[str, float], baseline: Dict[str, float]) -> Dict[str, float]:
    keys = sorted(set(active) | set(baseline))
    return {f"observed_delta_{k}": float(active.get(k, 0.0) - baseline.get(k, 0.0)) for k in keys}


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
                mean = float(np.mean(vals))
                feat_map[feat] = 1 if mean >= 0 else -1
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


def _make_world(seed: int, scenario: str, cfg: DiagnosticRerunConfig) -> PseudoRealitySystem:
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


def run_combined_diagnostic_loop(actions: pd.DataFrame, cfg: DiagnosticRerunConfig) -> Tuple[pd.DataFrame, pd.DataFrame]:
    trace_rows = []
    applied_rows = []
    if actions.empty:
        return pd.DataFrame(), pd.DataFrame()

    for _, pair in actions[["run_seed", "run_scenario"]].drop_duplicates().iterrows():
        seed = int(pair["run_seed"])
        scenario = str(pair["run_scenario"])
        active = _make_world(seed, scenario, cfg)
        baseline = _make_world(seed, scenario, cfg)
        steps = sorted(actions[(actions["run_seed"] == seed) & (actions["run_scenario"] == scenario)]["loop_step"].unique())
        if cfg.max_steps is not None:
            steps = [s for s in steps if int(s) < cfg.max_steps]
        prev = -1
        for step in steps:
            while prev + 1 < int(step):
                active.step(None)
                baseline.step(None)
                prev += 1
            group = actions[(actions["run_seed"] == seed) & (actions["run_scenario"] == scenario) & (actions["loop_step"] == step)].copy()
            af = _prepare_actions(group, active)
            active_trace = active.step(af)
            baseline_trace = baseline.step(None)
            prev = int(step)

            active_summary = summarize_trace(active_trace)
            baseline_summary = summarize_trace(baseline_trace)
            d = delta_summary(active_summary, baseline_summary)
            trace_row = {
                "rerun_scope": "combined_diagnostic",
                "run_seed": seed,
                "run_scenario": scenario,
                "loop_step": int(step),
                "action_rows": int(len(af)),
                "semantic_effects": int(group["semantic_effect"].nunique()),
                "diagnostic_primitives": int(group["action_primitive"].nunique()),
                "action_mass": float(af["action_strength"].sum()) if not af.empty else 0.0,
                "rerun_contract": RERUN_VERSION + "__combined_policy_actions_vs_no_action_baseline",
            }
            trace_row.update(d)
            trace_rows.append(trace_row)

            if not af.empty:
                applied = af.copy()
                applied["rerun_scope"] = "combined_diagnostic"
                applied["applied_loop_step"] = int(step)
                applied_rows.append(applied)

    return (
        pd.DataFrame(trace_rows),
        pd.concat(applied_rows, ignore_index=True) if applied_rows else pd.DataFrame(),
    )


def run_isolated_semantic_replay(
    actions: pd.DataFrame,
    semantic_outcome: pd.DataFrame,
    cfg: DiagnosticRerunConfig,
) -> pd.DataFrame:
    if actions.empty:
        return pd.DataFrame()

    expected_map = _expected_map_from_semantic_outcome(semantic_outcome)
    rows = []
    group_cols = ["run_seed", "run_scenario", "loop_step", "semantic_effect"]

    for (seed, scenario, step, effect), group in actions.groupby(group_cols, dropna=False):
        if cfg.max_steps is not None and int(step) >= cfg.max_steps:
            continue
        active = _make_world(int(seed), str(scenario), cfg)
        baseline = _make_world(int(seed), str(scenario), cfg)
        _advance_to_step(active, int(step))
        _advance_to_step(baseline, int(step))

        af = _prepare_actions(group.copy(), active)
        active_trace = active.step(af)
        baseline_trace = baseline.step(None)
        d = delta_summary(summarize_trace(active_trace), summarize_trace(baseline_trace))

        expected = expected_map.get(str(effect), {})
        match_rate, match_pass, details, n_expected = _match_expected(expected, d, cfg.alignment_threshold, cfg.min_observed_abs)

        row = {
            "rerun_scope": "isolated_semantic",
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
            "expected_feature_count": int(n_expected),
            "diagnostic_alignment_score": float(match_rate),
            "diagnostic_alignment_pass": bool(match_pass),
            "diagnostic_alignment_details": details,
            "diagnostic_outcome_verdict": "diagnostic_semantic_aligned" if match_pass else "diagnostic_semantic_misaligned",
            "rerun_contract": RERUN_VERSION + "__isolated_semantic_action_vs_no_action_baseline",
        }
        row.update(d)
        rows.append(row)

    return pd.DataFrame(rows)


def summarize_isolated_alignment(isolated: pd.DataFrame) -> pd.DataFrame:
    if isolated is None or isolated.empty:
        return pd.DataFrame()
    return isolated.groupby(["semantic_effect", "intent_family"], as_index=False).agg(
        rows=("semantic_effect", "size"),
        mean_alignment_score=("diagnostic_alignment_score", "mean"),
        alignment_pass_rate=("diagnostic_alignment_pass", "mean"),
        mean_action_mass=("action_mass", "mean"),
        action_primitives=("action_primitive", lambda s: "|".join(sorted(set(s.dropna().astype(str))))),
        action_channels=("action_channel", lambda s: "|".join(sorted(set(s.dropna().astype(str))))),
        mean_delta_conflict=("observed_delta_conflict", "mean"),
        mean_delta_uncertainty=("observed_delta_uncertainty", "mean"),
        mean_delta_exploration=("observed_delta_exploration", "mean"),
        mean_delta_overconvergence=("observed_delta_overconvergence", "mean"),
        mean_delta_m_overall=("observed_delta_m_overall", "mean"),
        dominant_verdict=("diagnostic_outcome_verdict", lambda s: str(s.value_counts().index[0]) if len(s) else "none"),
    ).sort_values(["alignment_pass_rate", "mean_alignment_score"], ascending=[True, True])


def summarize_scenario(combined: pd.DataFrame, isolated: pd.DataFrame) -> pd.DataFrame:
    csum = pd.DataFrame()
    isum = pd.DataFrame()
    if combined is not None and not combined.empty:
        csum = combined.groupby("run_scenario", as_index=False).agg(
            combined_steps=("loop_step", "size"),
            combined_mean_action_mass=("action_mass", "mean"),
            combined_mean_delta_conflict=("observed_delta_conflict", "mean"),
            combined_mean_delta_uncertainty=("observed_delta_uncertainty", "mean"),
            combined_mean_delta_exploration=("observed_delta_exploration", "mean"),
            combined_mean_delta_m_overall=("observed_delta_m_overall", "mean"),
        )
    if isolated is not None and not isolated.empty:
        isum = isolated.groupby("run_scenario", as_index=False).agg(
            isolated_rows=("semantic_effect", "size"),
            isolated_alignment_pass_rate=("diagnostic_alignment_pass", "mean"),
            isolated_mean_alignment_score=("diagnostic_alignment_score", "mean"),
            isolated_mean_action_mass=("action_mass", "mean"),
        )
    if not csum.empty and not isum.empty:
        return csum.merge(isum, on="run_scenario", how="outer")
    return csum if not csum.empty else isum


def build_outputs_from_results_dir(results_dir: str | Path, cfg: DiagnosticRerunConfig | None = None) -> Dict[str, pd.DataFrame]:
    cfg = cfg or DiagnosticRerunConfig()
    results = Path(results_dir)
    actions = _safe_read_csv(results / "diagnostic_action_translation_policy_action_frame_RC1.csv")
    semantic_outcome = _safe_read_csv(results / "pressure_semantic_outcome_alignment_RC1.csv")

    combined, applied = run_combined_diagnostic_loop(actions, cfg)
    isolated = run_isolated_semantic_replay(actions, semantic_outcome, cfg)
    return {
        "diagnostic_closed_loop_combined_trace": combined,
        "diagnostic_closed_loop_action_application": applied,
        "diagnostic_closed_loop_semantic_isolated_alignment": isolated,
        "diagnostic_closed_loop_semantic_summary": summarize_isolated_alignment(isolated),
        "diagnostic_closed_loop_scenario_summary": summarize_scenario(combined, isolated),
    }


def diagnostic_rerun_summary_json(outputs: Dict[str, pd.DataFrame]) -> dict:
    combined = outputs.get("diagnostic_closed_loop_combined_trace", pd.DataFrame())
    applied = outputs.get("diagnostic_closed_loop_action_application", pd.DataFrame())
    isolated = outputs.get("diagnostic_closed_loop_semantic_isolated_alignment", pd.DataFrame())
    semantic = outputs.get("diagnostic_closed_loop_semantic_summary", pd.DataFrame())
    scenario = outputs.get("diagnostic_closed_loop_scenario_summary", pd.DataFrame())

    if isolated.empty:
        return {"task": RERUN_VERSION, "status": "empty", "all_sanity_checks_passed": False}

    return {
        "task": RERUN_VERSION,
        "status": "completed",
        "combined_trace_rows": int(len(combined)),
        "applied_action_rows": int(len(applied)),
        "isolated_alignment_rows": int(len(isolated)),
        "semantic_effect_count": int(isolated["semantic_effect"].nunique()),
        "scenario_count": int(isolated["run_scenario"].nunique()),
        "mean_isolated_alignment_score": float(isolated["diagnostic_alignment_score"].mean()),
        "isolated_alignment_pass_rate": float(isolated["diagnostic_alignment_pass"].mean()),
        "mean_isolated_action_mass": float(isolated["action_mass"].mean()),
        "combined_mean_delta_conflict": float(combined["observed_delta_conflict"].mean()) if not combined.empty else 0.0,
        "combined_mean_delta_uncertainty": float(combined["observed_delta_uncertainty"].mean()) if not combined.empty else 0.0,
        "combined_mean_delta_exploration": float(combined["observed_delta_exploration"].mean()) if not combined.empty else 0.0,
        "combined_mean_delta_m_overall": float(combined["observed_delta_m_overall"].mean()) if not combined.empty else 0.0,
        "semantic_summary": semantic.to_dict(orient="records") if not semantic.empty else [],
        "scenario_summary": scenario.to_dict(orient="records") if not scenario.empty else [],
        "weakest_semantic_effects": semantic.head(6).to_dict(orient="records") if not semantic.empty else [],
        "strongest_semantic_effects": semantic.sort_values(["alignment_pass_rate", "mean_alignment_score"], ascending=[False, False]).head(6).to_dict(orient="records") if not semantic.empty else [],
        "dept_pressure_tuning_readiness": "not_ready_review_diagnostic_outcome_alignment_first",
        "next_recommended_task": "DiagnosticClosedLoopRerunReview_RC1",
        "all_sanity_checks_passed": bool(
            len(isolated) > 0 and int(isolated["semantic_effect"].nunique()) >= 8 and len(combined) > 0 and len(applied) > 0
        ),
    }
