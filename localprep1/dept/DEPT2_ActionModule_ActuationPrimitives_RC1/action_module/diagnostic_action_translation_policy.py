"""DiagnosticActionTranslationPolicy RC1.

Validation-only policy for preserving pressure semantic effects into weak,
traceable diagnostic actions.

This task is intentionally not a safety/governance policy. Its purpose is to
make pressure intent observable:

    approved pressure sign
    -> semantic_effect
    -> diagnostic plan
    -> weak diagnostic action
    -> later outcome alignment audit

It addresses the RC2 finding:

    semantic_to_plan_present_rate was low
    plan_to_action_present_rate was very low

The policy therefore guarantees minimum semantic-family survival into plan and
weak action for validation. It records exactly what was rescued and why.

It does not repair the coupling_relief -> staged_unlock sequence; that is a
separate task.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import json
import numpy as np
import pandas as pd


POLICY_VERSION = "DiagnosticActionTranslationPolicy_RC1"


@dataclass(frozen=True)
class DiagnosticPolicyConfig:
    mode: str = "alignment_probe"
    min_diagnostic_strength: float = 0.006
    max_diagnostic_strength: float = 0.030
    strength_scale: float = 0.12
    preserve_existing_actions: bool = True
    guarantee_min_family_survival: bool = True


SEMANTIC_DIAGNOSTIC_ROUTES: Dict[str, Dict[str, str]] = {
    "sandbox_probe_entry_up": {
        "intent_family": "exploration_observation",
        "action_primitive": "diagnostic_sandbox_probe",
        "primitive_sequence": "sandbox_probe -> observe -> report",
        "action_channel": "exploration_injection",
        "diagnostic_role": "weak sandbox/probe entry to test exploratory affordance",
    },
    "sandbox_probe_entry_down": {
        "intent_family": "probe_restraint",
        "action_primitive": "diagnostic_probe_restraint",
        "primitive_sequence": "probe_restraint -> observe",
        "action_channel": "buffer_increase",
        "diagnostic_role": "weak probe restraint to test restraint semantics",
    },
    "update_frequency_up": {
        "intent_family": "update_opening",
        "action_primitive": "diagnostic_update_opening",
        "primitive_sequence": "update_opening -> observe -> report",
        "action_channel": "uncertainty_probe",
        "diagnostic_role": "weak update access probe",
    },
    "update_frequency_down": {
        "intent_family": "update_restraint",
        "action_primitive": "diagnostic_update_restraint",
        "primitive_sequence": "update_restraint -> observe",
        "action_channel": "buffer_increase",
        "diagnostic_role": "weak update restraint probe",
    },
    "update_access_opening": {
        "intent_family": "temporal_opening",
        "action_primitive": "diagnostic_update_access_probe",
        "primitive_sequence": "update_access_probe -> observe -> report",
        "action_channel": "uncertainty_probe",
        "diagnostic_role": "weak temporal/update opening probe",
    },
    "exploration_attempt_frequency_up": {
        "intent_family": "exploration_attempt",
        "action_primitive": "diagnostic_exploration_attempt",
        "primitive_sequence": "exploration_attempt -> observe -> report",
        "action_channel": "exploration_injection",
        "diagnostic_role": "weak exploration attempt",
    },
    "exploration_attempt_frequency_down": {
        "intent_family": "exploration_restraint",
        "action_primitive": "diagnostic_exploration_restraint",
        "primitive_sequence": "exploration_restraint -> observe",
        "action_channel": "buffer_increase",
        "diagnostic_role": "weak exploration restraint",
    },
    "adoption_barrier_relief": {
        "intent_family": "adoption_opening",
        "action_primitive": "diagnostic_adoption_opening_probe",
        "primitive_sequence": "adoption_opening_probe -> buffer_observe -> report",
        "action_channel": "exploration_injection",
        "diagnostic_role": "weak adoption opening with buffer observation",
    },
    "sensitivity_opening": {
        "intent_family": "response_opening",
        "action_primitive": "diagnostic_sensitivity_opening",
        "primitive_sequence": "sensitivity_opening -> observe -> report",
        "action_channel": "coupling_relief",
        "diagnostic_role": "weak sensitivity/opening probe",
    },
    "hysteresis_guard_down": {
        "intent_family": "switching_flexibility",
        "action_primitive": "diagnostic_switching_flexibility",
        "primitive_sequence": "switching_flexibility -> observe",
        "action_channel": "coupling_relief",
        "diagnostic_role": "weak flexibility/coupling relief probe",
    },
    "diagnostic_resolution_down": {
        "intent_family": "observation_cost_saving",
        "action_primitive": "diagnostic_observation_saving_probe",
        "primitive_sequence": "lighter_observation -> report",
        "action_channel": "uncertainty_probe",
        "diagnostic_role": "weak observation-cost semantics probe",
    },
    "rollback_guard_down": {
        "intent_family": "safety_relaxation",
        "action_primitive": "diagnostic_rollback_relaxation_probe",
        "primitive_sequence": "rollback_relaxation -> observe",
        "action_channel": "buffer_increase",
        "diagnostic_role": "weak rollback relaxation probe",
    },
    "commitment_strength_down": {
        "intent_family": "commitment_relief",
        "action_primitive": "diagnostic_commitment_relief_probe",
        "primitive_sequence": "commitment_relief -> peripheral_observe",
        "action_channel": "exploration_injection",
        "diagnostic_role": "weak commitment relief probe",
    },
    "intensity_cap_brake": {
        "intent_family": "safety_cap",
        "action_primitive": "buffer_first",
        "primitive_sequence": "buffer -> replan",
        "action_channel": "buffer_increase",
        "diagnostic_role": "positive control: buffer->replan retained",
    },
}


def _safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _semantic_key_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in ["run_seed", "run_scenario", "loop_step", "semantic_effect"] if c in df.columns]


def _ensure_columns(df: pd.DataFrame, defaults: dict) -> pd.DataFrame:
    out = df.copy()
    for c, v in defaults.items():
        if c not in out.columns:
            out[c] = v
    return out


def _diagnostic_strength(row: pd.Series, cfg: DiagnosticPolicyConfig) -> float:
    base = float(row.get("max_component_magnitude", 0.0))
    if not np.isfinite(base) or base <= 0:
        base = abs(float(row.get("mean_component_signed_value", 0.0)))
    if not np.isfinite(base) or base <= 0:
        base = float(row.get("total_received_abs_pressure", 0.0)) / max(float(row.get("intent_rows", 1.0)), 1.0)
    strength = base * cfg.strength_scale
    return float(np.clip(strength, cfg.min_diagnostic_strength, cfg.max_diagnostic_strength))


def _coverage_lookup(plan_action_chain: pd.DataFrame) -> pd.DataFrame:
    if plan_action_chain is None or plan_action_chain.empty:
        return pd.DataFrame()

    chain = _ensure_columns(plan_action_chain, {
        "semantic_to_plan_present": False,
        "plan_to_action_present": False,
        "planned_rows": 0.0,
        "action_rows": 0.0,
        "action_mass": 0.0,
        "action_primitive": "",
        "primitive_sequence": "",
        "action_channel": "",
    })

    keys = _semantic_key_cols(chain)
    if not keys:
        return pd.DataFrame()

    agg = chain.groupby(keys, as_index=False).agg(
        original_semantic_to_plan_present=("semantic_to_plan_present", "max"),
        original_plan_to_action_present=("plan_to_action_present", "max"),
        original_planned_rows=("planned_rows", "sum"),
        original_action_rows=("action_rows", "sum"),
        original_action_mass=("action_mass", "sum"),
        original_action_primitive=("action_primitive", lambda s: "|".join(sorted(set(s.dropna().astype(str))))),
        original_primitive_sequence=("primitive_sequence", lambda s: "|".join(sorted(set(s.dropna().astype(str))))),
        original_action_channel=("action_channel", lambda s: "|".join(sorted(set(s.dropna().astype(str))))),
    )
    return agg


def build_diagnostic_translation_policy(
    semantic_chain: pd.DataFrame,
    plan_action_chain: pd.DataFrame | None = None,
    cfg: DiagnosticPolicyConfig | None = None,
) -> Dict[str, pd.DataFrame]:
    cfg = cfg or DiagnosticPolicyConfig()
    if semantic_chain is None or semantic_chain.empty:
        empty = pd.DataFrame()
        return {
            "diagnostic_policy_plan": empty,
            "diagnostic_policy_action_frame": empty,
            "diagnostic_policy_drop_reason": empty,
            "diagnostic_policy_semantic_coverage": empty,
            "diagnostic_policy_primitive_route_summary": empty,
            "diagnostic_policy_family_summary": empty,
        }

    sem = semantic_chain.copy()
    cov = _coverage_lookup(plan_action_chain if plan_action_chain is not None else pd.DataFrame())
    keys = _semantic_key_cols(sem)
    if not cov.empty and keys:
        sem = sem.merge(cov, on=keys, how="left")
    else:
        for c in [
            "original_semantic_to_plan_present", "original_plan_to_action_present",
            "original_planned_rows", "original_action_rows", "original_action_mass",
            "original_action_primitive", "original_primitive_sequence", "original_action_channel",
        ]:
            if "present" in c:
                sem[c] = False
            elif c in ["original_action_primitive", "original_primitive_sequence", "original_action_channel"]:
                sem[c] = ""
            else:
                sem[c] = 0.0

    for c in ["original_semantic_to_plan_present", "original_plan_to_action_present"]:
        sem[c] = sem[c].fillna(False).astype(bool)
    for c in ["original_planned_rows", "original_action_rows", "original_action_mass"]:
        sem[c] = sem[c].fillna(0.0)

    plan_rows = []
    action_rows = []
    drop_rows = []

    for _, row in sem.iterrows():
        effect = str(row.get("semantic_effect", "none"))
        route = SEMANTIC_DIAGNOSTIC_ROUTES.get(effect)
        had_plan = bool(row.get("original_semantic_to_plan_present", False))
        had_action = bool(row.get("original_plan_to_action_present", False))

        if route is None:
            route = {
                "intent_family": str(row.get("intent_family", "unknown")),
                "action_primitive": "diagnostic_generic_semantic_probe",
                "primitive_sequence": "generic_semantic_probe -> observe -> report",
                "action_channel": "uncertainty_probe",
                "diagnostic_role": "generic weak semantic probe; mapping missing in RC1",
            }
            route_status = "fallback_generic_route"
        else:
            route_status = "explicit_route"

        strength = _diagnostic_strength(row, cfg)
        source = "existing_action_retained" if had_action and cfg.preserve_existing_actions else (
            "existing_plan_rescued_to_action" if had_plan else "missing_plan_rescued_to_plan_and_action"
        )

        if had_action:
            original_state = "already_actuated"
            drop_reason = "none_retained_existing_action"
            dropped_at = "none"
        elif had_plan:
            original_state = "planned_but_not_actuated"
            drop_reason = "original_execution_policy_or_gate_dropped"
            dropped_at = "execution_policy_or_final_gate"
        else:
            original_state = "not_planned"
            drop_reason = "original_planner_missing_or_no_route"
            dropped_at = "planner_or_missing_route"

        base = {
            "policy_mode": cfg.mode,
            "run_seed": row.get("run_seed"),
            "run_scenario": row.get("run_scenario"),
            "loop_step": row.get("loop_step"),
            "pressure_component": row.get("pressure_component"),
            "component_direction": row.get("component_direction"),
            "semantic_effect": effect,
            "intent_family": route.get("intent_family", row.get("intent_family")),
            "suggested_control_route": row.get("suggested_control_route"),
            "diagnostic_route_status": route_status,
            "original_semantic_to_plan_present": had_plan,
            "original_plan_to_action_present": had_action,
            "original_state": original_state,
            "policy_action_source": source,
            "diagnostic_action_primitive": route["action_primitive"],
            "diagnostic_primitive_sequence": route["primitive_sequence"],
            "diagnostic_action_channel": route["action_channel"],
            "diagnostic_action_strength": strength,
            "diagnostic_role": route["diagnostic_role"],
            "max_component_magnitude": float(row.get("max_component_magnitude", 0.0)),
            "total_received_abs_pressure": float(row.get("total_received_abs_pressure", 0.0)),
            "intent_rows": int(row.get("intent_rows", 0)) if pd.notna(row.get("intent_rows", 0)) else 0,
            "semantic_retained_to_plan_by_policy": True,
            "semantic_retained_to_action_by_policy": True,
            "positive_control_flag": bool(route["action_primitive"] == "buffer_first" and route["primitive_sequence"] == "buffer -> replan"),
            "policy_contract": POLICY_VERSION + "__validation_semantic_minimum_survival",
        }
        plan_rows.append({
            **base,
            "planned_rows_after_policy": max(float(row.get("original_planned_rows", 0.0)), 1.0),
            "planned_strength_after_policy": strength,
            "plan_preservation_reason": "minimum_semantic_family_plan_guarantee" if not had_plan else "original_plan_preserved",
        })
        action_rows.append({
            **base,
            "action_rows_after_policy": max(float(row.get("original_action_rows", 0.0)), 1.0),
            "action_mass_after_policy": max(float(row.get("original_action_mass", 0.0)), strength),
            "action_preservation_reason": "weak_diagnostic_action_pass_through" if not had_action else "original_action_preserved",
            "action_primitive": route["action_primitive"],
            "primitive_sequence": route["primitive_sequence"],
            "action_channel": route["action_channel"],
            "action_strength": strength,
            "estimated_pseudo_input_strength": strength,
            "diagnostic_only": True,
        })
        drop_rows.append({
            **base,
            "drop_reason_original": drop_reason,
            "dropped_at_original": dropped_at,
            "policy_resolution": "retained" if had_action else "rescued_by_validation_policy",
            "drop_reason_after_policy": "none_validation_pass_through",
        })

    plan_df = pd.DataFrame(plan_rows)
    action_df = pd.DataFrame(action_rows)
    drop_df = pd.DataFrame(drop_rows)

    semantic_cov = plan_df.groupby("semantic_effect", as_index=False).agg(
        intent_family=("intent_family", "first"),
        rows=("semantic_effect", "size"),
        original_plan_rate=("original_semantic_to_plan_present", "mean"),
        original_action_rate=("original_plan_to_action_present", "mean"),
        policy_plan_rate=("semantic_retained_to_plan_by_policy", "mean"),
        policy_action_rate=("semantic_retained_to_action_by_policy", "mean"),
        diagnostic_action_mass=("diagnostic_action_strength", "sum"),
        explicit_route_rate=("diagnostic_route_status", lambda s: float((s == "explicit_route").mean())),
        positive_control_rows=("positive_control_flag", "sum"),
    )

    primitive_summary = action_df.groupby(
        ["diagnostic_action_primitive", "diagnostic_primitive_sequence", "diagnostic_action_channel"],
        as_index=False,
    ).agg(
        semantic_effects=("semantic_effect", "nunique"),
        rows=("semantic_effect", "size"),
        total_action_mass_after_policy=("action_mass_after_policy", "sum"),
        mean_diagnostic_strength=("diagnostic_action_strength", "mean"),
        originally_actuated_rate=("original_plan_to_action_present", "mean"),
        positive_control_rows=("positive_control_flag", "sum"),
    )

    family_summary = action_df.groupby("intent_family", as_index=False).agg(
        semantic_effects=("semantic_effect", "nunique"),
        rows=("semantic_effect", "size"),
        original_plan_rate=("original_semantic_to_plan_present", "mean"),
        original_action_rate=("original_plan_to_action_present", "mean"),
        policy_plan_rate=("semantic_retained_to_plan_by_policy", "mean"),
        policy_action_rate=("semantic_retained_to_action_by_policy", "mean"),
        diagnostic_action_mass=("diagnostic_action_strength", "sum"),
    )

    return {
        "diagnostic_policy_plan": plan_df,
        "diagnostic_policy_action_frame": action_df,
        "diagnostic_policy_drop_reason": drop_df,
        "diagnostic_policy_semantic_coverage": semantic_cov,
        "diagnostic_policy_primitive_route_summary": primitive_summary,
        "diagnostic_policy_family_summary": family_summary,
    }


def build_outputs_from_results_dir(results_dir: str | Path, cfg: DiagnosticPolicyConfig | None = None) -> Dict[str, pd.DataFrame]:
    results = Path(results_dir)
    semantic_chain = _safe_read_csv(results / "pressure_sign_semantic_chain_RC1.csv")
    plan_action_chain = _safe_read_csv(results / "pressure_semantic_plan_action_chain_RC1.csv")
    return build_diagnostic_translation_policy(semantic_chain, plan_action_chain, cfg=cfg)


def diagnostic_policy_summary_json(outputs: Dict[str, pd.DataFrame]) -> dict:
    plan = outputs.get("diagnostic_policy_plan", pd.DataFrame())
    action = outputs.get("diagnostic_policy_action_frame", pd.DataFrame())
    drop = outputs.get("diagnostic_policy_drop_reason", pd.DataFrame())
    semantic = outputs.get("diagnostic_policy_semantic_coverage", pd.DataFrame())
    primitive = outputs.get("diagnostic_policy_primitive_route_summary", pd.DataFrame())
    family = outputs.get("diagnostic_policy_family_summary", pd.DataFrame())

    if plan.empty or action.empty:
        return {
            "task": POLICY_VERSION,
            "status": "empty",
            "all_sanity_checks_passed": False,
        }

    return {
        "task": POLICY_VERSION,
        "status": "completed",
        "policy_mode": str(plan["policy_mode"].iloc[0]),
        "semantic_rows": int(len(plan)),
        "semantic_effect_count": int(plan["semantic_effect"].nunique()),
        "intent_family_count": int(plan["intent_family"].nunique()),
        "diagnostic_action_rows": int(len(action)),
        "diagnostic_primitive_count": int(action["diagnostic_action_primitive"].nunique()),
        "original_semantic_to_plan_rate": float(plan["original_semantic_to_plan_present"].mean()),
        "original_plan_to_action_rate": float(plan["original_plan_to_action_present"].mean()),
        "policy_semantic_to_plan_rate": float(plan["semantic_retained_to_plan_by_policy"].mean()),
        "policy_plan_to_action_rate": float(action["semantic_retained_to_action_by_policy"].mean()),
        "rescued_from_no_plan_rows": int((drop["dropped_at_original"] == "planner_or_missing_route").sum()),
        "rescued_from_no_action_rows": int((drop["dropped_at_original"] == "execution_policy_or_final_gate").sum()),
        "retained_existing_action_rows": int((drop["dropped_at_original"] == "none").sum()),
        "positive_control_rows": int(action["positive_control_flag"].sum()),
        "total_diagnostic_action_mass": float(action["action_mass_after_policy"].sum()),
        "explicit_route_rate": float((action["diagnostic_route_status"] == "explicit_route").mean()),
        "semantic_coverage": semantic.to_dict(orient="records") if not semantic.empty else [],
        "primitive_route_summary": primitive.to_dict(orient="records") if not primitive.empty else [],
        "family_summary": family.to_dict(orient="records") if not family.empty else [],
        "all_sanity_checks_passed": bool(
            len(action) > 0
            and float(plan["semantic_retained_to_plan_by_policy"].mean()) >= 0.999
            and float(action["semantic_retained_to_action_by_policy"].mean()) >= 0.999
            and int(action["semantic_effect"].nunique()) >= 8
            and int(action["positive_control_flag"].sum()) > 0
        ),
    }
