"""PressureSignSemanticsAudit RC1.

Task A: split pressure sign, semantic effect, translated primitive/sequence,
actual action channel, and observed outcome.

This audit exists because PressureOutcomeAlignmentAudit_RC1 showed that reading
`approved_*` sign directly as an outcome direction is unsafe.

Core question:
    Where does the apparent pressure/outcome sign mismatch arise?

Audit chain:
    approved component + sign
    -> semantic_effect / intent_family / suggested route
    -> planned primitive / primitive sequence
    -> actuated primitive / action channel
    -> observed next-step outcome

This module does not tune DEPT.  It only makes the meaning chain visible.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence

import numpy as np
import pandas as pd


AUDIT_VERSION = "PressureSignSemanticsAudit_RC1"

OUTCOME_COLUMNS = {
    "conflict": "gt_conflict_mean",
    "uncertainty": "gt_uncertainty_mean",
    "exploration": "gt_exploration_mean",
    "overconvergence": "gt_overconvergence_mean",
    "m_overall": "m_mean_overall",
}

PRESSURE_COMPONENTS = [
    "diagnostic_depth",
    "exploration_frequency",
    "sandbox_entry_rate",
    "adoption_threshold",
    "rollback_sensitivity",
    "deadzone_width",
    "cooldown_length",
    "hysteresis_strength",
    "update_frequency",
    "pressure_cap",
    "commitment_strength",
]

# This mirrors dept2_system.pressure_intent.COMPONENT_INTENT_SPEC, but is kept
# here as an audit contract so that sign semantics are visible in outputs.
COMPONENT_SIGN_SEMANTICS = {
    "diagnostic_depth": {
        "increase": ("diagnostic_resolution_up", "observation_detail", "v8_detail_or_audit"),
        "decrease": ("diagnostic_resolution_down", "observation_cost_saving", "lighter_observation"),
    },
    "exploration_frequency": {
        "increase": ("exploration_attempt_frequency_up", "exploration_attempt", "increase_trials"),
        "decrease": ("exploration_attempt_frequency_down", "exploration_restraint", "reduce_trials"),
    },
    "sandbox_entry_rate": {
        "increase": ("sandbox_probe_entry_up", "exploration_observation", "increase_sandbox_probe"),
        "decrease": ("sandbox_probe_entry_down", "probe_restraint", "reduce_sandbox_probe"),
    },
    "adoption_threshold": {
        "increase": ("adoption_barrier_raise", "adoption_guard", "keep_adoption_strict"),
        "decrease": ("adoption_barrier_relief", "adoption_opening", "lower_candidate_barrier"),
    },
    "rollback_sensitivity": {
        "increase": ("rollback_guard_up", "safety_guard", "prepare_reversal"),
        "decrease": ("rollback_guard_down", "safety_relaxation", "reduce_reversal_bias"),
    },
    "deadzone_width": {
        "increase": ("sensitivity_deadzone_widen", "response_restraint", "ignore_minor_variation"),
        "decrease": ("sensitivity_opening", "response_opening", "respond_to_smaller_signal"),
    },
    "cooldown_length": {
        "increase": ("update_waiting_longer", "temporal_brake", "lengthen_wait"),
        "decrease": ("update_access_opening", "temporal_opening", "shorten_wait"),
    },
    "hysteresis_strength": {
        "increase": ("hysteresis_guard_up", "persistence_guard", "resist_fast_switching"),
        "decrease": ("hysteresis_guard_down", "switching_flexibility", "allow_axis_turnover"),
    },
    "update_frequency": {
        "increase": ("update_frequency_up", "update_opening", "increase_update_access"),
        "decrease": ("update_frequency_down", "update_restraint", "reduce_update_access"),
    },
    "pressure_cap": {
        "increase": ("intensity_cap_relief", "capacity_opening", "allow_larger_action_cap"),
        "decrease": ("intensity_cap_brake", "safety_cap", "lower_action_cap"),
    },
    "commitment_strength": {
        "increase": ("commitment_strength_up", "commitment_guard", "stabilize_selected_path"),
        "decrease": ("commitment_strength_down", "commitment_relief", "keep_path_reversible"),
    },
}

# Semantic effect expected outcome direction in the currently available
# pseudo-reality metrics. These are deliberately coarse and auditable.
SEMANTIC_EXPECTED_OUTCOME = {
    "diagnostic_resolution_up": {"uncertainty": -1, "conflict": -1, "m_overall": +1},
    "diagnostic_resolution_down": {"uncertainty": +1, "conflict": +1, "m_overall": -1},
    "exploration_attempt_frequency_up": {"exploration": +1, "overconvergence": -1, "uncertainty": +1},
    "exploration_attempt_frequency_down": {"exploration": -1, "overconvergence": +1, "uncertainty": -1},
    "sandbox_probe_entry_up": {"exploration": +1, "overconvergence": -1, "uncertainty": +1},
    "sandbox_probe_entry_down": {"exploration": -1, "overconvergence": +1},
    "adoption_barrier_raise": {"uncertainty": -1, "conflict": -1, "exploration": -1},
    "adoption_barrier_relief": {"exploration": +1, "overconvergence": -1, "uncertainty": +1},
    "rollback_guard_up": {"uncertainty": -1, "conflict": -1, "m_overall": +1},
    "rollback_guard_down": {"uncertainty": +1, "conflict": +1, "m_overall": -1},
    "sensitivity_deadzone_widen": {"uncertainty": -1, "conflict": -1, "exploration": -1},
    "sensitivity_opening": {"exploration": +1, "overconvergence": -1, "uncertainty": +1},
    "update_waiting_longer": {"uncertainty": -1, "conflict": -1, "exploration": -1},
    "update_access_opening": {"exploration": +1, "overconvergence": -1, "uncertainty": +1},
    "hysteresis_guard_up": {"uncertainty": -1, "conflict": -1, "overconvergence": +1},
    "hysteresis_guard_down": {"exploration": +1, "overconvergence": -1, "conflict": -1},
    "update_frequency_up": {"exploration": +1, "overconvergence": -1, "uncertainty": +1},
    "update_frequency_down": {"exploration": -1, "overconvergence": +1, "uncertainty": -1},
    "intensity_cap_relief": {"exploration": +1, "uncertainty": +1},
    "intensity_cap_brake": {"uncertainty": -1, "conflict": -1, "exploration": -1},
    "commitment_strength_up": {"uncertainty": -1, "overconvergence": +1, "m_overall": +1},
    "commitment_strength_down": {"exploration": +1, "overconvergence": -1, "m_overall": +1},
}

# Expected direct effect of primitive/channel on pseudo-reality metrics.
PRIMITIVE_EXPECTED_OUTCOME = {
    "observe_only": {},
    "buffer_first": {"uncertainty": -1, "conflict": -1, "m_overall": +1},
    "coupling_relief_first": {"conflict": -1, "overconvergence": -1, "m_overall": +1},
    "staged_relation_unlock": {"conflict": -1, "overconvergence": -1, "m_overall": +1},
    "peripheral_explore": {"exploration": +1, "overconvergence": -1, "uncertainty": +1},
    "exploration_cost_relief": {"exploration": +1, "overconvergence": -1, "uncertainty": +1},
    "adoption_barrier_relief_guarded": {"exploration": +1, "overconvergence": -1, "uncertainty": +1},
    "volatility_damp_first": {"uncertainty": -1, "conflict": -1, "m_overall": +1},
    "delayed_uncertainty_probe": {"uncertainty": -1, "exploration": +1, "m_overall": +1},
}


@dataclass(frozen=True)
class SignSemanticsAuditConfig:
    min_abs_pressure: float = 1e-8
    weak_effect_threshold: float = 1e-6
    match_rate_threshold: float = 0.50


def _safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def sign_label(v: float) -> str:
    if v > 1e-12:
        return "increase"
    if v < -1e-12:
        return "decrease"
    return "neutral"


def semantic_for(component: str, direction: str) -> tuple[str, str, str]:
    if direction == "neutral":
        return "neutral_component", "neutral", "no_route"
    return COMPONENT_SIGN_SEMANTICS.get(component, {}).get(direction, ("unknown_effect", "unknown_family", "unknown_route"))


def _feature_delta(current: pd.Series, nxt: pd.Series) -> dict:
    out = {}
    for feature, col in OUTCOME_COLUMNS.items():
        if col in current.index and col in nxt.index:
            out[feature] = float(nxt[col] - current[col])
        else:
            out[feature] = 0.0
    return out


def build_outcome_increment(metrics: pd.DataFrame) -> pd.DataFrame:
    if metrics is None or metrics.empty:
        return pd.DataFrame()
    rows = []
    key_cols = ["run_seed", "run_scenario"]
    for key, sub in metrics.sort_values("loop_step").groupby(key_cols, dropna=False):
        for i in range(len(sub) - 1):
            cur = sub.iloc[i]
            nxt = sub.iloc[i + 1]
            d = _feature_delta(cur, nxt)
            row = {
                "run_seed": cur["run_seed"],
                "run_scenario": cur["run_scenario"],
                "loop_step": int(cur["loop_step"]),
                "next_loop_step": int(nxt["loop_step"]),
            }
            for f, val in d.items():
                row[f"observed_delta_{f}"] = val
                row[f"observed_direction_{f}"] = sign_label(val)
            rows.append(row)
    return pd.DataFrame(rows)


def summarize_intents(intents: pd.DataFrame) -> pd.DataFrame:
    if intents is None or intents.empty:
        return pd.DataFrame()
    d = intents.copy()
    for c in ["run_seed", "run_scenario", "loop_step"]:
        if c not in d.columns:
            if c == "run_seed" and "seed" in d.columns: d[c] = d["seed"]
            if c == "run_scenario" and "scenario" in d.columns: d[c] = d["scenario"]
            if c == "loop_step" and "t" in d.columns: d[c] = d["t"]
    group_cols = [
        "run_seed", "run_scenario", "loop_step",
        "pressure_component", "component_direction", "semantic_effect",
        "intent_family", "suggested_control_route",
    ]
    existing = [c for c in group_cols if c in d.columns]
    out = d.groupby(existing, as_index=False).agg(
        intent_rows=("semantic_effect", "size"),
        mean_component_signed_value=("component_signed_value", "mean"),
        max_component_magnitude=("component_magnitude", "max"),
        total_received_abs_pressure=("h11_received_abs_pressure", "sum"),
        relevant_to_exploration=("relevant_to_exploration_injection", "max"),
        relevant_to_relation_unlock=("relevant_to_relation_unlock", "max"),
        relevant_to_volatility_damping=("relevant_to_volatility_damping", "max"),
        relevant_to_uncertainty_probe=("relevant_to_uncertainty_probe", "max"),
        relevant_to_coupling_relief=("relevant_to_coupling_relief", "max"),
        relevant_to_buffer_increase=("relevant_to_buffer_increase", "max"),
    )
    return out


def summarize_plans(plans: pd.DataFrame) -> pd.DataFrame:
    if plans is None or plans.empty:
        return pd.DataFrame()
    d = plans.copy()
    group_cols = ["run_seed", "run_scenario", "loop_step", "dominant_pressure_component", "dominant_semantic_effect", "action_primitive", "primitive_sequence", "action_channel"]
    out = d.groupby(group_cols, as_index=False).agg(
        planned_rows=("action_primitive", "size"),
        mean_planned_strength=("action_strength", "mean"),
        mean_planner_confidence=("planner_confidence", "mean"),
        unique_entities=("entity_id", "nunique"),
    )
    return out


def summarize_actions(actions: pd.DataFrame) -> pd.DataFrame:
    if actions is None or actions.empty:
        return pd.DataFrame()
    d = actions.copy()
    group_cols = ["run_seed", "run_scenario", "loop_step", "dominant_pressure_component", "dominant_semantic_effect", "action_primitive", "primitive_sequence", "action_channel"]
    out = d.groupby(group_cols, as_index=False).agg(
        action_rows=("action_primitive", "size"),
        mean_action_strength=("action_strength", "mean"),
        action_mass=("action_strength", "sum"),
        unique_entities=("entity_id", "nunique"),
    )
    return out


def _expected_match_rate(expected: dict, outcome_row: pd.Series) -> tuple[float, int, str]:
    hits = 0
    considered = 0
    details = []
    for feature, expected_sign in expected.items():
        col = f"observed_delta_{feature}"
        if col not in outcome_row.index:
            continue
        observed = float(outcome_row[col])
        if abs(observed) <= 1e-12:
            obs_sign = 0
        else:
            obs_sign = 1 if observed > 0 else -1
        considered += 1
        match = (obs_sign == int(expected_sign))
        hits += int(match)
        details.append(f"{feature}:expected={int(expected_sign)},observed={observed:.6f},match={match}")
    return (float(hits / considered) if considered else 0.0, considered, "; ".join(details))


def build_sign_semantics_audit(
    pressure: pd.DataFrame,
    intents: pd.DataFrame,
    plans: pd.DataFrame,
    actions: pd.DataFrame,
    metrics: pd.DataFrame,
    config: SignSemanticsAuditConfig | None = None,
) -> Dict[str, pd.DataFrame]:
    cfg = config or SignSemanticsAuditConfig()

    intent_summary = summarize_intents(intents)
    plan_summary = summarize_plans(plans)
    action_summary = summarize_actions(actions)
    outcome = build_outcome_increment(metrics)

    # Component sign table directly from pressure candidates.
    sign_rows = []
    if pressure is not None and not pressure.empty:
        p = pressure.copy()
        for c in ["run_seed", "run_scenario", "loop_step"]:
            if c not in p.columns:
                if c == "run_seed" and "seed" in p.columns: p[c] = p["seed"]
                if c == "run_scenario" and "scenario" in p.columns: p[c] = p["scenario"]
                if c == "loop_step" and "t" in p.columns: p[c] = p["t"]
        for _, r in p.iterrows():
            for comp in PRESSURE_COMPONENTS:
                col = f"approved_{comp}"
                if col not in r.index:
                    continue
                val = float(r[col])
                direction = sign_label(val)
                semantic, family, route = semantic_for(comp, direction)
                sign_rows.append({
                    "run_seed": r["run_seed"],
                    "run_scenario": r["run_scenario"],
                    "loop_step": int(r["loop_step"]),
                    "pressure_component": comp,
                    "approved_value": val,
                    "component_direction_from_sign": direction,
                    "semantic_effect_from_sign_contract": semantic,
                    "intent_family_from_sign_contract": family,
                    "suggested_route_from_sign_contract": route,
                    "pressure_sign_contract": AUDIT_VERSION + "__component_sign_to_semantic_effect",
                })
    component_sign_table = pd.DataFrame(sign_rows)

    # Join sign-contract and observed intent annotations to verify semantic chain.
    semantic_chain = pd.DataFrame()
    if not component_sign_table.empty and not intent_summary.empty:
        semantic_chain = component_sign_table.merge(
            intent_summary,
            left_on=["run_seed", "run_scenario", "loop_step", "pressure_component", "component_direction_from_sign", "semantic_effect_from_sign_contract"],
            right_on=["run_seed", "run_scenario", "loop_step", "pressure_component", "component_direction", "semantic_effect"],
            how="left",
            indicator="intent_match_indicator",
        )
        semantic_chain["sign_to_intent_semantics_match"] = semantic_chain["intent_match_indicator"].eq("both")
        semantic_chain["semantic_chain_contract"] = AUDIT_VERSION + "__pressure_sign_to_pressure_intent_bundle"

    # Join intent/plan/action.
    plan_action_chain = pd.DataFrame()
    if not intent_summary.empty:
        # Plan rows where the semantic effect becomes dominant semantic effect.
        plan_chain = intent_summary.merge(
            plan_summary,
            left_on=["run_seed", "run_scenario", "loop_step", "pressure_component", "semantic_effect"],
            right_on=["run_seed", "run_scenario", "loop_step", "dominant_pressure_component", "dominant_semantic_effect"],
            how="left",
        )
        plan_chain["semantic_to_plan_present"] = plan_chain["planned_rows"].fillna(0).gt(0)
        action_chain = plan_chain.merge(
            action_summary,
            on=["run_seed", "run_scenario", "loop_step", "dominant_pressure_component", "dominant_semantic_effect", "action_primitive", "primitive_sequence", "action_channel"],
            how="left",
        )
        action_chain["plan_to_action_present"] = action_chain["action_rows"].fillna(0).gt(0)
        action_chain["semantic_plan_action_contract"] = AUDIT_VERSION + "__semantic_effect_to_primitive_to_action"
        plan_action_chain = action_chain

    # Outcome alignment by semantic effect and by primitive.
    semantic_outcome_rows = []
    primitive_outcome_rows = []

    if not intent_summary.empty and not outcome.empty:
        sem = intent_summary.merge(outcome, on=["run_seed", "run_scenario", "loop_step"], how="inner")
        for _, r in sem.iterrows():
            effect = str(r["semantic_effect"])
            expected = SEMANTIC_EXPECTED_OUTCOME.get(effect, {})
            rate, n, details = _expected_match_rate(expected, r)
            semantic_outcome_rows.append({
                "run_seed": r["run_seed"],
                "run_scenario": r["run_scenario"],
                "loop_step": int(r["loop_step"]),
                "pressure_component": r["pressure_component"],
                "component_direction": r["component_direction"],
                "semantic_effect": effect,
                "intent_family": r["intent_family"],
                "expected_source": "semantic_effect",
                "expected_feature_count": n,
                "semantic_outcome_match_rate": rate,
                "semantic_outcome_details": details,
                "semantic_outcome_verdict": "semantic_aligned" if n and rate >= cfg.match_rate_threshold else ("semantic_unmapped" if not n else "semantic_misaligned"),
                **{c: r[c] for c in r.index if c.startswith("observed_delta_")},
                "semantic_outcome_contract": AUDIT_VERSION + "__semantic_effect_expected_outcome_vs_observed_increment",
            })
    semantic_outcome = pd.DataFrame(semantic_outcome_rows)

    if not action_summary.empty and not outcome.empty:
        prim = action_summary.merge(outcome, on=["run_seed", "run_scenario", "loop_step"], how="inner")
        for _, r in prim.iterrows():
            primitive = str(r["action_primitive"])
            expected = PRIMITIVE_EXPECTED_OUTCOME.get(primitive, {})
            rate, n, details = _expected_match_rate(expected, r)
            primitive_outcome_rows.append({
                "run_seed": r["run_seed"],
                "run_scenario": r["run_scenario"],
                "loop_step": int(r["loop_step"]),
                "dominant_pressure_component": r["dominant_pressure_component"],
                "dominant_semantic_effect": r["dominant_semantic_effect"],
                "action_primitive": primitive,
                "primitive_sequence": r["primitive_sequence"],
                "action_channel": r["action_channel"],
                "action_rows": int(r["action_rows"]),
                "action_mass": float(r["action_mass"]),
                "expected_source": "primitive",
                "expected_feature_count": n,
                "primitive_outcome_match_rate": rate,
                "primitive_outcome_details": details,
                "primitive_outcome_verdict": "primitive_aligned" if n and rate >= cfg.match_rate_threshold else ("primitive_unmapped" if not n else "primitive_misaligned"),
                **{c: r[c] for c in r.index if c.startswith("observed_delta_")},
                "primitive_outcome_contract": AUDIT_VERSION + "__primitive_expected_outcome_vs_observed_increment",
            })
    primitive_outcome = pd.DataFrame(primitive_outcome_rows)

    component_summary = pd.DataFrame()
    if not semantic_chain.empty:
        component_summary = semantic_chain.groupby(["pressure_component", "component_direction_from_sign", "semantic_effect_from_sign_contract"], as_index=False).agg(
            rows=("pressure_component", "size"),
            sign_to_intent_match_rate=("sign_to_intent_semantics_match", "mean"),
            mean_approved_value=("approved_value", "mean"),
            intent_rows=("intent_rows", "sum"),
        )

    semantic_summary = pd.DataFrame()
    if not semantic_outcome.empty:
        semantic_summary = semantic_outcome.groupby(["pressure_component", "component_direction", "semantic_effect"], as_index=False).agg(
            rows=("semantic_effect", "size"),
            mean_match_rate=("semantic_outcome_match_rate", "mean"),
            aligned_rows=("semantic_outcome_verdict", lambda s: int((s == "semantic_aligned").sum())),
            misaligned_rows=("semantic_outcome_verdict", lambda s: int((s == "semantic_misaligned").sum())),
            dominant_verdict=("semantic_outcome_verdict", lambda s: str(s.value_counts().index[0]) if len(s) else "none"),
        )

    primitive_summary = pd.DataFrame()
    if not primitive_outcome.empty:
        primitive_summary = primitive_outcome.groupby(["action_primitive", "action_channel"], as_index=False).agg(
            rows=("action_primitive", "size"),
            total_action_rows=("action_rows", "sum"),
            mean_action_mass=("action_mass", "mean"),
            mean_match_rate=("primitive_outcome_match_rate", "mean"),
            aligned_rows=("primitive_outcome_verdict", lambda s: int((s == "primitive_aligned").sum())),
            misaligned_rows=("primitive_outcome_verdict", lambda s: int((s == "primitive_misaligned").sum())),
            dominant_verdict=("primitive_outcome_verdict", lambda s: str(s.value_counts().index[0]) if len(s) else "none"),
        )

    return {
        "pressure_sign_component_table": component_sign_table,
        "pressure_sign_semantic_chain": semantic_chain,
        "pressure_semantic_plan_action_chain": plan_action_chain,
        "pressure_semantic_outcome_alignment": semantic_outcome,
        "pressure_primitive_outcome_alignment": primitive_outcome,
        "pressure_sign_component_summary": component_summary,
        "pressure_semantic_outcome_summary": semantic_summary,
        "pressure_primitive_outcome_summary": primitive_summary,
        "pressure_outcome_increment_table": outcome,
    }


def build_outputs_from_results_dir(results_dir: str | Path) -> Dict[str, pd.DataFrame]:
    results = Path(results_dir)
    return build_sign_semantics_audit(
        pressure=_safe_read_csv(results / "pressure_candidates_RC1.csv"),
        intents=_safe_read_csv(results / "pressure_intent_bundle_RC1.csv"),
        plans=_safe_read_csv(results / "planned_action_candidates_RC1.csv"),
        actions=_safe_read_csv(results / "action_module_frames_RC1.csv"),
        metrics=_safe_read_csv(results / "closed_loop_metrics_RC1.csv"),
    )


def audit_summary_json(outputs: Dict[str, pd.DataFrame]) -> dict:
    sign_chain = outputs.get("pressure_sign_semantic_chain", pd.DataFrame())
    action_chain = outputs.get("pressure_semantic_plan_action_chain", pd.DataFrame())
    sem_outcome = outputs.get("pressure_semantic_outcome_alignment", pd.DataFrame())
    prim_outcome = outputs.get("pressure_primitive_outcome_alignment", pd.DataFrame())
    comp_summary = outputs.get("pressure_sign_component_summary", pd.DataFrame())
    sem_summary = outputs.get("pressure_semantic_outcome_summary", pd.DataFrame())
    prim_summary = outputs.get("pressure_primitive_outcome_summary", pd.DataFrame())

    return {
        "task": AUDIT_VERSION,
        "status": "completed",
        "sign_semantic_chain_rows": int(len(sign_chain)),
        "semantic_plan_action_chain_rows": int(len(action_chain)),
        "semantic_outcome_rows": int(len(sem_outcome)),
        "primitive_outcome_rows": int(len(prim_outcome)),
        "sign_to_intent_match_rate": float(sign_chain["sign_to_intent_semantics_match"].mean()) if not sign_chain.empty and "sign_to_intent_semantics_match" in sign_chain else 0.0,
        "semantic_to_plan_present_rate": float(action_chain["semantic_to_plan_present"].mean()) if not action_chain.empty and "semantic_to_plan_present" in action_chain else 0.0,
        "plan_to_action_present_rate": float(action_chain["plan_to_action_present"].mean()) if not action_chain.empty and "plan_to_action_present" in action_chain else 0.0,
        "mean_semantic_outcome_match_rate": float(sem_outcome["semantic_outcome_match_rate"].mean()) if not sem_outcome.empty else 0.0,
        "semantic_aligned_rate": float((sem_outcome["semantic_outcome_verdict"] == "semantic_aligned").mean()) if not sem_outcome.empty else 0.0,
        "mean_primitive_outcome_match_rate": float(prim_outcome["primitive_outcome_match_rate"].mean()) if not prim_outcome.empty else 0.0,
        "primitive_aligned_rate": float((prim_outcome["primitive_outcome_verdict"] == "primitive_aligned").mean()) if not prim_outcome.empty else 0.0,
        "dominant_semantic_outcome_verdicts": sem_outcome["semantic_outcome_verdict"].value_counts().to_dict() if not sem_outcome.empty else {},
        "dominant_primitive_outcome_verdicts": prim_outcome["primitive_outcome_verdict"].value_counts().to_dict() if not prim_outcome.empty else {},
        "worst_semantic_effects": (
            sem_summary.sort_values(["mean_match_rate", "rows"], ascending=[True, False]).head(8).to_dict(orient="records")
            if not sem_summary.empty else []
        ),
        "worst_primitives": (
            prim_summary.sort_values(["mean_match_rate", "rows"], ascending=[True, False]).head(8).to_dict(orient="records")
            if not prim_summary.empty else []
        ),
        "all_sanity_checks_passed": bool(
            len(sign_chain) > 0 and len(action_chain) > 0 and len(sem_outcome) > 0 and len(prim_outcome) > 0
        ),
        "audit_interpretation": "primary purpose is chain visibility, not DEPT tuning",
    }
