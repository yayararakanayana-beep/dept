#!/usr/bin/env python3
"""Generate Action Pressure Reception Trace RC1 reports.

This is a trace-only/no-write diagnostic. It observes what prepared pressure
bundle reaches the action-module entry point during the existing closed-loop
scenarios. It does not change the action decision path, coefficients,
ParameterBox, ShadowBox, canonical state, production runtime, or the existing
closed-loop runner behavior.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = REPO_ROOT / "tests"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))
if "tests" not in sys.modules:
    tests_pkg = types.ModuleType("tests")
    tests_pkg.__path__ = [str(TESTS_DIR)]
    sys.modules["tests"] = tests_pkg

from tests.test_action_module_api_consolidation_rc1 import (  # noqa: E402
    NON_EXECUTION_CHANNELS,
    action_module_step,
)
from tests.test_closed_loop_runner_integration_rc1 import (  # noqa: E402
    ClosedLoopActionDecision,
    ClosedLoopHistory,
    apply_action_decision_to_pseudo_reality,
    build_closed_loop_scenarios,
    build_prepared_inputs_from_state,
    compute_closed_loop_recovery_score,
    compute_closed_loop_short_term_gain,
    compute_delayed_side_effect_cost,
    compute_missed_opportunity,
    compute_over_action,
    compute_safety_violation,
    initial_closed_loop_history,
    initial_state_for_scenario,
)

OUTPUT_DIR = REPO_ROOT / "reports" / "action_pressure_reception_trace_rc1"
SEEDS = (0, 1, 2, 3, 4)
BASELINE_NAME = "ACTION_MODULE_RC1"
TRACE_LABEL = "action_pressure_reception_trace_rc1"
EXPECTED_BUNDLE_KEYS = ("pressure_intensity", "preferred_channels", "safety_pressure")
EXPLICIT_MIXED_PRESSURE_KEYS = {
    "permission": ("permission_pressure", "safe_permission_pressure", "small_permission_pressure"),
    "exploration": ("exploration_pressure", "exploration_small_pressure", "small_exploration_pressure"),
    "recovery": ("recovery_pressure", "post_shock_recovery_pressure", "small_recovery_pressure"),
    "unlock": ("unlock_pressure", "relation_unlock_pressure", "de_fixation_pressure"),
}
PREFERRED_CHANNEL_KEYS = ("stabilize", "explore", "de_risk", "relation")


def _clip(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(value)))


def _round_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    float_cols = out.select_dtypes(include=["float"]).columns
    out[float_cols] = out[float_cols].round(6)
    return out


def _write_csv(df: pd.DataFrame, name: str) -> pd.DataFrame:
    out = _round_df(df)
    out.to_csv(OUTPUT_DIR / name, index=False)
    return out


def _join(values) -> str:
    vals = [str(v) for v in values if v is not None and str(v) != ""]
    return ",".join(vals)


def _first_present(mapping: dict, keys: tuple[str, ...]):
    for key in keys:
        if key in mapping:
            return key, mapping.get(key)
    return None, None


def _bool_present(mapping: dict, keys: tuple[str, ...]) -> bool:
    key, _ = _first_present(mapping, keys)
    return key is not None


def _float_or_zero(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _as_closed_loop_decision(result) -> ClosedLoopActionDecision:
    decision = result.action_decision
    audit_passed = bool(result.action_audit_record.boundary_flags.get("audit_passed", False))
    return ClosedLoopActionDecision(
        decision.decision_type,
        decision.selected_channel,
        float(decision.selected_action_mass),
        decision.decision_reason,
        audit_passed,
    )


def _update_history(history: ClosedLoopHistory, after_state, decision: ClosedLoopActionDecision, safety_violation: bool) -> ClosedLoopHistory:
    action_row = {
        "decision_type": decision.decision_type,
        "selected_channel": decision.selected_channel,
        "selected_action_mass": decision.selected_action_mass,
    }
    return ClosedLoopHistory(
        (history.recent_actions + (action_row,))[-5:],
        (history.recent_states + (after_state,))[-5:],
        max(0, history.cooldown_counter - 1) + (1 if decision.decision_type == "COOLDOWN" else 0),
        max(0, history.rollback_counter - 1) + (1 if decision.decision_type == "ROLLBACK" else 0),
        history.cumulative_action_mass + decision.selected_action_mass,
        history.cumulative_harmful_events + int(safety_violation),
    )


def _no_op_trace_class(bundle: dict, result, safe_projected_count: int) -> str:
    decision = result.action_decision
    policy = result.functional_policy_output
    if not bundle:
        return "NO_PRESSURE_BUNDLE"
    if decision.decision_type == "EXECUTE":
        return "EXECUTED"
    if decision.decision_type == "ROLLBACK":
        return "ROLLBACK_PRIORITY"
    if decision.decision_type == "COOLDOWN":
        return "COOLDOWN_PRIORITY"
    if decision.decision_type == "HOLD_FOR_EVIDENCE":
        return "EVIDENCE_HOLD"
    if decision.decision_type == "NO_OP" and policy.fire_permission_score < 0.50:
        return "BELOW_FIRE_THRESHOLD"
    if decision.decision_type == "NO_OP" and safe_projected_count == 0:
        return "NO_SAFE_EXECUTION_CANDIDATE"
    if decision.decision_type == "NO_OP":
        return "NO_OP_OTHER"
    return "NON_EXECUTION_OTHER"


def _trace_one_step(scenario, seed: int, state, history):
    prepared_inputs = build_prepared_inputs_from_state(state, history, scenario)
    result = action_module_step(**prepared_inputs, label_override=TRACE_LABEL)
    decision = _as_closed_loop_decision(result)

    gain = compute_closed_loop_short_term_gain(state, decision, scenario)
    safety_violation = compute_safety_violation(state, decision)
    over_action = compute_over_action(state, decision)
    after = apply_action_decision_to_pseudo_reality(state, decision, scenario)
    recovery_score = compute_closed_loop_recovery_score(state, after, decision, scenario)
    missed_opportunity = compute_missed_opportunity(state, decision)
    delayed_side_effect_cost = compute_delayed_side_effect_cost(state, decision, scenario)

    context = result.action_context
    bundle = dict(context.prepared_upper_pressure or {})
    preferred = dict(bundle.get("preferred_channels", {}) or {})
    missing_expected = [key for key in EXPECTED_BUNDLE_KEYS if key not in bundle]
    raw_keys = sorted(bundle.keys())

    explicit = {}
    for pressure_name, keys in EXPLICIT_MIXED_PRESSURE_KEYS.items():
        key, value = _first_present(bundle, keys)
        explicit[f"explicit_{pressure_name}_pressure_received"] = key is not None
        explicit[f"explicit_{pressure_name}_pressure_key"] = key or ""
        explicit[f"explicit_{pressure_name}_pressure_value"] = _float_or_zero(value) if key is not None else 0.0

    policy = result.functional_policy_output
    projected = result.projected_action_candidates
    safe_projected = [
        p for p in projected
        if p.safety_passed
        and not p.rejected_by_guardrail
        and p.action_channel not in NON_EXECUTION_CHANNELS
        and p.projected_action_mass > 0.0
    ]
    rejected_projection_reasons = _join(
        sorted({p.projection_reason for p in projected if p.rejected_by_guardrail or p.projected_action_mass <= 0.0})
    )

    row = {
        "scenario_id": scenario.scenario_id,
        "scenario_type": scenario.scenario_type,
        "baseline_name": BASELINE_NAME,
        "seed": seed,
        "step": state.step,
        "trace_only": True,
        "no_write_confirmed": True,
        "runtime_behavior_changed": False,
        "coefficient_changed": False,
        "parameterbox_updated": False,
        "shadowbox_updated": False,
        "canonical_writeback_performed": False,
        "pressure_bundle_received": bool(bundle),
        "pressure_bundle_schema_valid": bool(bundle) and not missing_expected and isinstance(bundle.get("preferred_channels"), dict),
        "pressure_bundle_raw_keys": _join(raw_keys),
        "pressure_bundle_missing_expected_keys": _join(missing_expected),
        "pressure_intensity": _float_or_zero(bundle.get("pressure_intensity")),
        "safety_pressure": _float_or_zero(bundle.get("safety_pressure")),
        "preferred_stabilize_pressure_received": "stabilize" in preferred,
        "preferred_stabilize_pressure_value": _float_or_zero(preferred.get("stabilize")),
        "preferred_explore_pressure_received": "explore" in preferred,
        "preferred_explore_pressure_value": _float_or_zero(preferred.get("explore")),
        "preferred_de_risk_pressure_received": "de_risk" in preferred,
        "preferred_de_risk_pressure_value": _float_or_zero(preferred.get("de_risk")),
        "preferred_relation_pressure_received": "relation" in preferred,
        "preferred_relation_pressure_value": _float_or_zero(preferred.get("relation")),
        **explicit,
        "explicit_mixed_pressure_any_received": any(_bool_present(bundle, keys) for keys in EXPLICIT_MIXED_PRESSURE_KEYS.values()),
        "functional_fire_permission_score": policy.fire_permission_score,
        "functional_action_mass_cap": policy.action_mass_cap,
        "functional_cooldown_score": policy.cooldown_score,
        "functional_rollback_permission_score": policy.rollback_permission_score,
        "functional_non_action_decision": policy.non_action_decision,
        "functional_policy_reason": policy.policy_reason,
        "candidate_count": len(result.action_candidates),
        "execution_candidate_count": sum(c.action_channel not in NON_EXECUTION_CHANNELS for c in result.action_candidates),
        "projected_candidate_count": len(projected),
        "safe_projected_execution_candidate_count": len(safe_projected),
        "rejected_projection_reasons": rejected_projection_reasons,
        "decision_type": decision.decision_type,
        "selected_channel": decision.selected_channel,
        "selected_action_mass": decision.selected_action_mass,
        "decision_reason": decision.decision_reason,
        "trace_class": _no_op_trace_class(bundle, result, len(safe_projected)),
        "opportunity_before": state.opportunity,
        "risk_before": state.risk,
        "stability_before": state.stability,
        "exploration_capacity_before": state.exploration_capacity,
        "recovery_capacity_before": state.recovery_capacity,
        "relation_lock_before": state.relation_lock,
        "hidden_fragility_before": state.hidden_fragility,
        "external_pressure_before": state.external_pressure,
        "safe_mass_upper_before": state.safe_mass_upper,
        "harmful_threshold_before": state.harmful_threshold,
        "safe_opportunity_detected": state.opportunity > 0.70 and state.risk < 0.55 and state.safe_mass_upper > 0.05,
        "recovery_need_detected": max(state.risk, 1.0 - state.stability) > 0.45,
        "exploration_need_detected": state.exploration_capacity < 0.75 or state.opportunity > 0.70,
        "relation_unlock_need_detected": state.relation_lock > 0.20,
        "short_term_gain": gain,
        "safety_violation": safety_violation,
        "over_action": over_action,
        "missed_opportunity": missed_opportunity,
        "delayed_side_effect_cost": delayed_side_effect_cost,
        "recovery_score": recovery_score,
        "stability_after": after.stability,
        "risk_after": after.risk,
        "exploration_capacity_after": after.exploration_capacity,
        "relation_lock_after": after.relation_lock,
    }
    return row, after, _update_history(history, after, decision, safety_violation)


def build_reception_trace_step(seeds=SEEDS) -> pd.DataFrame:
    rows = []
    for scenario in build_closed_loop_scenarios():
        for seed in seeds:
            state = initial_state_for_scenario(scenario, seed=seed)
            history = initial_closed_loop_history()
            for _ in range(scenario.n_steps):
                row, state, history = _trace_one_step(scenario, seed, state, history)
                rows.append(row)
    return pd.DataFrame(rows)


def build_reception_trace_summary(step: pd.DataFrame) -> pd.DataFrame:
    def summarize(g: pd.DataFrame) -> pd.Series:
        pressure_rows = g[g.pressure_bundle_received]
        return pd.Series({
            "n_steps": len(g),
            "pressure_bundle_received_rate": g.pressure_bundle_received.mean(),
            "pressure_bundle_schema_valid_rate": g.pressure_bundle_schema_valid.mean(),
            "explicit_mixed_pressure_any_received_rate": g.explicit_mixed_pressure_any_received.mean(),
            "preferred_explore_received_rate": g.preferred_explore_pressure_received.mean(),
            "preferred_de_risk_received_rate": g.preferred_de_risk_pressure_received.mean(),
            "preferred_relation_received_rate": g.preferred_relation_pressure_received.mean(),
            "mean_fire_permission_score": g.functional_fire_permission_score.mean(),
            "mean_action_mass_cap": g.functional_action_mass_cap.mean(),
            "mean_safe_projected_execution_candidate_count": g.safe_projected_execution_candidate_count.mean(),
            "execute_rate": (g.decision_type == "EXECUTE").mean(),
            "no_op_rate": (g.decision_type == "NO_OP").mean(),
            "hold_for_evidence_rate": (g.decision_type == "HOLD_FOR_EVIDENCE").mean(),
            "missed_opportunity_rate": g.missed_opportunity.mean(),
            "safe_opportunity_count": int(g.safe_opportunity_detected.sum()),
            "safe_opportunity_no_op_count": int(((g.safe_opportunity_detected) & (g.decision_type == "NO_OP")).sum()),
            "most_common_trace_class": g.trace_class.mode().iloc[0] if not g.trace_class.mode().empty else "",
            "received_raw_keys_sample": pressure_rows.pressure_bundle_raw_keys.iloc[0] if not pressure_rows.empty else "",
        })

    return step.groupby("scenario_type", as_index=False).apply(summarize, include_groups=False).reset_index(drop=True)


def build_trace_class_summary(step: pd.DataFrame) -> pd.DataFrame:
    return step.groupby(["scenario_type", "trace_class"], as_index=False).size().rename(columns={"size": "count"})


def _markdown_table(df: pd.DataFrame, max_rows: int = 20) -> str:
    if df.empty:
        return "(no rows)"
    use = _round_df(df.head(max_rows))
    cols = list(use.columns)
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in use.iterrows():
        vals = [str(row[c]).replace("|", "\\|") for c in cols]
        lines.append("| " + " | ".join(vals) + " |")
    if len(df) > max_rows:
        lines.append(f"\nShowing first {max_rows} of {len(df)} rows.")
    return "\n".join(lines)


def write_report(step: pd.DataFrame, summary: pd.DataFrame, cls: pd.DataFrame) -> None:
    total = len(step)
    pressure_rate = step.pressure_bundle_received.mean() if total else 0.0
    schema_rate = step.pressure_bundle_schema_valid.mean() if total else 0.0
    explicit_rate = step.explicit_mixed_pressure_any_received.mean() if total else 0.0
    execute_rate = (step.decision_type == "EXECUTE").mean() if total else 0.0
    no_op_rate = (step.decision_type == "NO_OP").mean() if total else 0.0
    missed_rate = step.missed_opportunity.mean() if total else 0.0
    safe_no_op = int(((step.safe_opportunity_detected) & (step.decision_type == "NO_OP")).sum()) if total else 0
    raw_keys = sorted(set(k for value in step.pressure_bundle_raw_keys.dropna().unique() for k in str(value).split(",") if k))

    text = f"""# Action Pressure Reception Trace RC1

## 1. Purpose

This report records what prepared pressure bundle reaches the action-module entry point during the existing closed-loop RC1 scenarios.

It is trace-only and no-write. It does not change action decisions, coefficients, ParameterBox, ShadowBox, canonical state, production runtime, or the existing closed-loop runner behavior.

## 2. Safety confirmation

- trace_only: true
- no_write_confirmed: true
- runtime_behavior_changed: false
- coefficient_changed: false
- parameterbox_updated: false
- shadowbox_updated: false
- canonical_writeback_performed: false
- baseline traced: `{BASELINE_NAME}`
- seeds: `{SEEDS}`

## 3. Top-level reception summary

- rows: `{total}`
- pressure bundle received rate: `{pressure_rate:.3f}`
- pressure bundle schema valid rate: `{schema_rate:.3f}`
- explicit mixed pressure received rate: `{explicit_rate:.3f}`
- execute rate: `{execute_rate:.3f}`
- NO_OP rate: `{no_op_rate:.3f}`
- missed opportunity rate: `{missed_rate:.3f}`
- safe opportunity + NO_OP count: `{safe_no_op}`
- received raw pressure keys: `{', '.join(raw_keys)}`

## 4. Important interpretation

The current action-module entry point does receive a prepared upper pressure bundle when ACTION_MODULE_RC1 is evaluated. The bundle is the existing RC1 schema, mainly `pressure_intensity`, `preferred_channels`, and `safety_pressure`.

This trace separately checks explicit mixed-pressure keys such as permission, exploration-small, recovery, and unlock pressure. If their received rate is zero, that means the current runner is not yet passing those explicit mixed-pressure fields into the action-module entry point. That does not prove the upper layer cannot generate them; it only means they are not visible at this entry point in this RC1 runner path.

## 5. Scenario summary

{_markdown_table(summary)}

## 6. Trace class summary

{_markdown_table(cls)}

## 7. Next diagnostic use

Use this output to decide whether the next fix belongs to:

1. upper-pressure generation, if explicit mixed pressure is absent;
2. pressure handoff schema, if upper pressure exists elsewhere but is not received here;
3. action-module fire / NO_OP conditions, if pressure is received but safe execution candidates are not selected;
4. pseudo-reality effect model, if action executes but has no useful effect.

## 8. What this report must not be used to claim

- It does not update runtime behavior.
- It does not prove that explicit mixed pressure was never generated upstream.
- It does not justify coefficient changes.
- It does not justify canonical writeback.
- It does not merge mixed pressure into actual action yet.
"""
    (OUTPUT_DIR / "action_pressure_reception_trace_report.md").write_text(text)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    step = _write_csv(build_reception_trace_step(), "action_pressure_reception_trace_step.csv")
    summary = _write_csv(build_reception_trace_summary(step), "action_pressure_reception_trace_summary.csv")
    cls = _write_csv(build_trace_class_summary(step), "action_pressure_reception_trace_class_summary.csv")
    write_report(step, summary, cls)

    print("=== Action Pressure Reception Trace RC1 ===")
    print("Output directory: reports/action_pressure_reception_trace_rc1")
    print("\n=== Scenario Summary ===")
    print(summary.to_string(index=False))
    print("\n=== Trace Class Summary ===")
    print(cls.to_string(index=False))
    print("\nDone.")


if __name__ == "__main__":
    main()
