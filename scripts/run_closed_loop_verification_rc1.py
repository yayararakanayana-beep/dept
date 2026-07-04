#!/usr/bin/env python3
"""Generate the Closed Loop Verification Package RC1 reports.

This script executes the already-merged test-local closed-loop runner with the
RC1 seed set and writes comparative result tables plus a human-readable report.
It does not mutate production runtime files, coefficients, canonical state,
ParameterBox, ShadowBox, ActionPlanner, or ActionModule defaults.
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

from tests.test_closed_loop_runner_integration_rc1 import (  # noqa: E402
    BASELINES,
    SCENARIOS,
    run_closed_loop_runner_integration_rc1,
)

OUTPUT_DIR = REPO_ROOT / "reports" / "closed_loop_verification_rc1"
SEEDS = (0, 1, 2, 3, 4)
LOW_RECOVERY_THRESHOLD = 0.35


def _round_df(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    float_cols = out.select_dtypes(include=["float"]).columns
    out[float_cols] = out[float_cols].round(6)
    return out


def _write_csv(df: pd.DataFrame, name: str) -> pd.DataFrame:
    out = _round_df(df)
    out.to_csv(OUTPUT_DIR / name, index=False)
    return out


def _severity(diff: float, *, time_metric: bool = False) -> str | None:
    diff = abs(float(diff))
    if time_metric:
        if diff >= 5:
            return "high"
        if diff >= 2:
            return "medium"
        if diff >= 1:
            return "low"
        return None
    if diff >= 0.25:
        return "high"
    if diff >= 0.10:
        return "medium"
    if diff > 0.03:
        return "low"
    return None


def _add_drift(rows: list[dict], scenario: str, baseline: str, drift_type: str, severity: str | None,
               metric: str, value: float, ref_baseline: str, ref_value: float, direction: str, diagnosis: str) -> None:
    if severity:
        rows.append({
            "scenario_type": scenario,
            "baseline_name": baseline,
            "drift_type": drift_type,
            "severity": severity,
            "evidence_metric": metric,
            "baseline_value": round(float(value), 6),
            "reference_baseline": ref_baseline,
            "reference_value": round(float(ref_value), 6),
            "direction": direction,
            "diagnosis": diagnosis,
        })


def build_drift_diagnosis(baseline_summary: pd.DataFrame, scenario_breakdown: pd.DataFrame,
                          episode_summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    ep_scenario = episode_summary.groupby(["scenario_type", "baseline_name"], as_index=False).agg(
        mean_final_risk=("final_risk", "mean"),
        mean_final_stability=("final_stability", "mean"),
        mean_missed_opportunity_rate=("missed_opportunity_rate", "mean"),
        mean_audit_pass_rate=("audit_pass_rate", "mean"),
    )
    merged = scenario_breakdown.merge(ep_scenario, on=["scenario_type", "baseline_name"], how="left")

    for scenario, group in merged.groupby("scenario_type", sort=False):
        best_gain = group.loc[group.mean_cumulative_gain.idxmax()]
        safest = group.loc[group.mean_safety_violation_rate.idxmin()]
        best_recovery = group.loc[group.mean_recovery_score.idxmax()]
        fastest = group.loc[group.mean_time_to_recover.idxmin()]
        lowest_lock = group.loc[group.mean_final_relation_lock.idxmin()]
        best_explore = group.loc[group.mean_exploration_capacity_retention.idxmax()]
        lowest_missed = group.loc[group.mean_missed_opportunity_rate.idxmin()]
        best_audit = group.loc[group.mean_audit_pass_rate.idxmax()]
        conservative_pool = group[group.baseline_name.isin(["ACTION_MODULE_RC1", "NO_ACTION"])]
        over_ref = conservative_pool.loc[conservative_pool.mean_over_action_rate.idxmin()]

        for _, row in group.iterrows():
            b = row.baseline_name
            _add_drift(rows, scenario, b, "short_term_gain_drift",
                       _severity(best_gain.mean_cumulative_gain - row.mean_cumulative_gain),
                       "mean_cumulative_gain", row.mean_cumulative_gain, best_gain.baseline_name,
                       best_gain.mean_cumulative_gain, "lower_is_worse",
                       f"{b} trails {best_gain.baseline_name} on cumulative gain in {scenario}.")
            _add_drift(rows, scenario, b, "safety_boundary_drift",
                       _severity(row.mean_safety_violation_rate - safest.mean_safety_violation_rate),
                       "mean_safety_violation_rate", row.mean_safety_violation_rate, safest.baseline_name,
                       safest.mean_safety_violation_rate, "higher_is_worse",
                       f"{b} has more safety-boundary violations than {safest.baseline_name} in {scenario}.")
            _add_drift(rows, scenario, b, "over_action_drift",
                       _severity(row.mean_over_action_rate - over_ref.mean_over_action_rate),
                       "mean_over_action_rate", row.mean_over_action_rate, over_ref.baseline_name,
                       over_ref.mean_over_action_rate, "higher_is_worse",
                       f"{b} over-acts more than the conservative reference {over_ref.baseline_name} in {scenario}.")
            rec_sev = _severity(best_recovery.mean_recovery_score - row.mean_recovery_score)
            ttr_sev = _severity(row.mean_time_to_recover - fastest.mean_time_to_recover, time_metric=True)
            rec_final = ttr_sev if ttr_sev == "high" or (ttr_sev == "medium" and rec_sev != "high") else rec_sev
            _add_drift(rows, scenario, b, "recovery_drift", rec_final,
                       "mean_recovery_score / mean_time_to_recover", row.mean_recovery_score,
                       best_recovery.baseline_name, best_recovery.mean_recovery_score, "lower_recovery_or_slower_recovery_is_worse",
                       f"{b} recovers less effectively than {best_recovery.baseline_name} or slower than {fastest.baseline_name} in {scenario}.")
            _add_drift(rows, scenario, b, "relation_lock_drift",
                       _severity(row.mean_final_relation_lock - lowest_lock.mean_final_relation_lock),
                       "mean_final_relation_lock", row.mean_final_relation_lock, lowest_lock.baseline_name,
                       lowest_lock.mean_final_relation_lock, "higher_is_worse",
                       f"{b} ends with higher relation lock than {lowest_lock.baseline_name} in {scenario}.")
            _add_drift(rows, scenario, b, "exploration_loss_drift",
                       _severity(best_explore.mean_exploration_capacity_retention - row.mean_exploration_capacity_retention),
                       "mean_exploration_capacity_retention", row.mean_exploration_capacity_retention,
                       best_explore.baseline_name, best_explore.mean_exploration_capacity_retention,
                       "lower_is_worse", f"{b} preserves less exploration capacity than {best_explore.baseline_name} in {scenario}.")
            _add_drift(rows, scenario, b, "missed_opportunity_drift",
                       _severity(row.mean_missed_opportunity_rate - lowest_missed.mean_missed_opportunity_rate),
                       "mean_missed_opportunity_rate", row.mean_missed_opportunity_rate, lowest_missed.baseline_name,
                       lowest_missed.mean_missed_opportunity_rate, "higher_is_worse",
                       f"{b} misses more opportunities than {lowest_missed.baseline_name} in {scenario}.")
            _add_drift(rows, scenario, b, "audit_boundary_drift",
                       _severity(best_audit.mean_audit_pass_rate - row.mean_audit_pass_rate),
                       "mean_audit_pass_rate", row.mean_audit_pass_rate, best_audit.baseline_name,
                       best_audit.mean_audit_pass_rate, "lower_is_worse",
                       f"{b} has a lower audit pass rate than {best_audit.baseline_name} in {scenario}.")

    cols = ["scenario_type", "baseline_name", "drift_type", "severity", "evidence_metric", "baseline_value",
            "reference_baseline", "reference_value", "direction", "diagnosis"]
    return pd.DataFrame(rows, columns=cols).sort_values(["severity", "scenario_type", "baseline_name", "drift_type"], ascending=[True, True, True, True])


def build_adjustment_candidates(drift: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict] = []
    high_or_medium = drift[(drift.baseline_name == "ACTION_MODULE_RC1") & (drift.severity.isin(["high", "medium"]))]
    mapping = {
        "missed_opportunity_drift": ("fire_permission_threshold", "review whether safe opportunities are being filtered too aggressively", "reduce missed safe opportunities", "may increase over-action or safety exposure"),
        "over_action_drift": ("max_action_mass_cap", "review action mass cap when conservative baseline still over-acts", "lower over-action frequency", "may reduce cumulative gain"),
        "recovery_drift": ("recovery_priority_weight", "review recovery weighting, cooldown trigger, or rollback trigger under stress", "improve post-shock recovery", "may make the module too conservative"),
        "relation_lock_drift": ("relation_lock_penalty", "review relation-lock penalty when actions accumulate lock", "reduce lock accumulation", "may suppress useful stabilize actions"),
        "exploration_loss_drift": ("exploration_retention_weight", "review exploration retention weighting", "preserve exploration capacity", "may reduce immediate stabilization"),
    }
    cid = 1
    for drift_type, (component, suggestion, effect, risk) in mapping.items():
        subset = high_or_medium[high_or_medium.drift_type == drift_type]
        if subset.empty:
            continue
        sev = "high" if (subset.severity == "high").any() else "medium"
        scenarios = ", ".join(sorted(subset.scenario_type.unique()))
        rows.append({
            "candidate_id": f"ACR-RC1-{cid:03d}",
            "target_component": component,
            "trigger_condition": f"ACTION_MODULE_RC1 {drift_type} severity {sev} in {scenarios}",
            "observed_issue": f"{drift_type} observed for ACTION_MODULE_RC1 in {len(subset)} scenario row(s).",
            "suggested_adjustment": suggestion,
            "expected_effect": effect,
            "risk_of_adjustment": risk,
            "priority": sev,
            "status": "candidate_only",
        })
        cid += 1

    greedy_brittle = drift[(drift.baseline_name == "V2_GREEDY_OPTIMIZER") & (drift.severity.isin(["high", "medium"])) &
                           (drift.scenario_type.isin(["safety_boundary_shift", "delayed_side_effect", "reaction_surface_drift", "hidden_fragility", "high_opportunity_high_risk"]))]
    if not greedy_brittle.empty:
        scenarios = ", ".join(sorted(greedy_brittle.scenario_type.unique()))
        rows.append({
            "candidate_id": f"ACR-RC1-{cid:03d}",
            "target_component": "over_action_penalty",
            "trigger_condition": f"GREEDY brittleness evidence in {scenarios}",
            "observed_issue": "Pure visible-surface optimization shows stress drift; this is evidence only, not a request to change GREEDY.",
            "suggested_adjustment": "retain as comparative evidence for why ACTION_MODULE_RC1 needs audit-aware constraints",
            "expected_effect": "keeps GREEDY as a brittle-reference baseline",
            "risk_of_adjustment": "none because no runtime adjustment is applied",
            "priority": "low",
            "status": "candidate_only",
        })

    if not rows:
        rows.append({
            "candidate_id": "ACR-RC1-000",
            "target_component": "missed_opportunity_guard",
            "trigger_condition": "No medium/high ACTION_MODULE_RC1 drift detected",
            "observed_issue": "No serious ACTION_MODULE_RC1 adjustment issue appeared in RC1 results.",
            "suggested_adjustment": "no high-priority adjustment candidate required",
            "expected_effect": "preserve current RC1 behavior pending broader validation",
            "risk_of_adjustment": "unnecessary tuning could overfit RC1 scenarios",
            "priority": "low",
            "status": "candidate_only",
        })
    return pd.DataFrame(rows)



def _to_markdown(df: pd.DataFrame) -> str:
    if df.empty:
        return "(no rows)"
    cols = list(df.columns)
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join(["---"] * len(cols)) + " |"]
    for _, row in df.iterrows():
        vals = [str(row[c]).replace("|", "\\|") for c in cols]
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)

def _winner(df: pd.DataFrame, metric: str, higher: bool = True) -> str:
    idx = df[metric].idxmax() if higher else df[metric].idxmin()
    return str(df.loc[idx, "baseline_name"])


def write_report(baseline: pd.DataFrame, scenario: pd.DataFrame, episode: pd.DataFrame, drift: pd.DataFrame,
                 candidates: pd.DataFrame, step_sample: pd.DataFrame) -> None:
    winners = {
        "short_term_gain_winner": _winner(baseline, "mean_cumulative_gain", True),
        "safety_winner": _winner(baseline, "mean_safety_violation_rate", False),
        "over_action_winner": _winner(baseline, "mean_over_action_rate", False),
        "recovery_winner": _winner(baseline, "mean_recovery_score", True),
        "relation_lock_winner": _winner(baseline, "mean_final_relation_lock", False),
        "exploration_retention_winner": _winner(baseline, "mean_exploration_capacity_retention", True),
        "robustness_winner": _winner(baseline, "closed_loop_robustness_score", True),
    }
    scenario_lines = []
    for scen, group in scenario.groupby("scenario_type", sort=False):
        epg = episode[episode.scenario_type == scen].groupby("baseline_name", as_index=False).agg(
            mean_final_risk=("final_risk", "mean"), mean_missed_opportunity_rate=("missed_opportunity_rate", "mean")
        )
        g = group.merge(epg, on="baseline_name", how="left")
        gain = _winner(g, "mean_cumulative_gain", True)
        safe = _winner(g, "mean_safety_violation_rate", False)
        am = g[g.baseline_name == "ACTION_MODULE_RC1"].iloc[0]
        greedy = g[g.baseline_name == "V2_GREEDY_OPTIMIZER"].iloc[0]
        no = g[g.baseline_name == "NO_ACTION"].iloc[0]
        scenario_lines.append(
            f"- **{scen}**: highest cumulative gain = {gain}; safest = {safe}. "
            f"ACTION_MODULE_RC1 recovery={am.mean_recovery_score:.3f}, risk={am.mean_final_risk:.3f}, over-action={am.mean_over_action_rate:.3f}. "
            f"GREEDY gain={greedy.mean_cumulative_gain:.3f}, risk={greedy.mean_final_risk:.3f}, over-action={greedy.mean_over_action_rate:.3f}. "
            f"NO_ACTION missed-opportunity={no.mean_missed_opportunity_rate:.3f}, recovery={no.mean_recovery_score:.3f}."
        )
    drift_summary = drift.groupby(["drift_type", "severity"]).size().reset_index(name="count") if not drift.empty else pd.DataFrame(columns=["drift_type", "severity", "count"])
    priority_summary = candidates.groupby(["priority"]).size().reset_index(name="count")
    next_step = "targeted adjustment proposal" if (candidates.priority.isin(["high", "medium"])).any() else "closed loop verification rerun after candidate adjustment"
    text = f"""# Closed Loop Verification Package RC1

## 1. Execution Conditions

- Runner function used: `run_closed_loop_runner_integration_rc1(...)` imported from `tests.test_closed_loop_runner_integration_rc1`.
- Seeds used: `{SEEDS}`.
- Baselines: `{', '.join(BASELINES)}`.
- Scenario count: `{len(SCENARIOS)}`.
- Step count per scenario: `12`.
- No production mutation was performed by this reporting script.
- No coefficient update was performed.
- No canonical writeback was performed.

## 2. Baselines

- **NO_ACTION**: no intervention baseline.
- **V2_GREEDY_OPTIMIZER**: visible-surface short-term optimizer.
- **ACTION_MODULE_RC1**: `action_module_step`-based conservative/action-audit baseline.

## 3. Scenarios

- **stable_closed_v2**: tests steady closed-loop opportunity where visible greedy gain should be strong.
- **shock_recovery**: tests post-shock recovery and risk control.
- **delayed_side_effect**: tests fatigue and relation-lock buildup after repeated action.
- **safety_boundary_shift**: tests behavior when safe action mass contracts.
- **reaction_surface_drift**: tests brittleness when the visible response surface shifts.
- **hidden_fragility**: tests conservative behavior under incomplete fragility exposure.
- **high_opportunity_high_risk**: tests balancing large opportunity against elevated risk.

## 4. Top-Level Comparison

| Winner category | Baseline |
| --- | --- |
"""
    for k, v in winners.items():
        text += f"| {k} | {v} |\n"
    text += "\nBaseline comparison table:\n\n" + _to_markdown(baseline) + "\n\n## 5. Scenario Breakdown\n\n" + "\n".join(scenario_lines)
    text += "\n\nScenario breakdown table:\n\n" + _to_markdown(scenario)
    text += "\n\n## 6. Drift Diagnosis\n\nMajor drift counts:\n\n" + _to_markdown(drift_summary)
    text += "\n\nImportant diagnosis rows are recorded in `drift_diagnosis.csv`; high and medium rows identify the main mismatch patterns by scenario, baseline, reference baseline, and metric."
    text += "\n\n## 7. Adjustment Candidates\n\nCandidate priority counts:\n\n" + _to_markdown(priority_summary) + "\n\n" + _to_markdown(candidates)
    text += "\n\nNo adjustments are applied by this package; every row remains `candidate_only`."
    text += "\n\n## 8. What We Learned\n\n"
    text += f"- {winners['short_term_gain_winner']} wins aggregate short-term/cumulative gain.\n"
    text += f"- {winners['robustness_winner']} wins aggregate closed-loop robustness.\n"
    text += f"- ACTION_MODULE_RC1 shows gain={baseline.set_index('baseline_name').loc['ACTION_MODULE_RC1','mean_cumulative_gain']:.3f}, risk={baseline.set_index('baseline_name').loc['ACTION_MODULE_RC1','mean_final_risk']:.3f}, over-action={baseline.set_index('baseline_name').loc['ACTION_MODULE_RC1','mean_over_action_rate']:.3f}, recovery={baseline.set_index('baseline_name').loc['ACTION_MODULE_RC1','mean_recovery_score']:.3f}.\n"
    text += f"- V2_GREEDY_OPTIMIZER shows gain={baseline.set_index('baseline_name').loc['V2_GREEDY_OPTIMIZER','mean_cumulative_gain']:.3f}, risk={baseline.set_index('baseline_name').loc['V2_GREEDY_OPTIMIZER','mean_final_risk']:.3f}, over-action={baseline.set_index('baseline_name').loc['V2_GREEDY_OPTIMIZER','mean_over_action_rate']:.3f}, recovery={baseline.set_index('baseline_name').loc['V2_GREEDY_OPTIMIZER','mean_recovery_score']:.3f}.\n"
    text += f"- NO_ACTION shows gain={baseline.set_index('baseline_name').loc['NO_ACTION','mean_cumulative_gain']:.3f} and missed-opportunity={baseline.set_index('baseline_name').loc['NO_ACTION','mean_missed_opportunity_rate']:.3f}.\n"
    text += "\n## 9. What We Cannot Claim Yet\n\n- This is not full v3 validation.\n- This is not real-world validation.\n- This does not prove universal superiority.\n- This does not justify runtime coefficient updates yet.\n- This does not update ParameterBox or ShadowBox.\n"
    text += f"\n## 10. Next Recommended Step\n\n{next_step}\n"
    (OUTPUT_DIR / "closed_loop_verification_report.md").write_text(text)


def build_step_sample(step_long: pd.DataFrame) -> pd.DataFrame:
    grouped = step_long.groupby(["scenario_type", "baseline_name", "seed"], group_keys=False)
    edge = grouped.apply(lambda g: pd.concat([g.nsmallest(3, "step"), g.nlargest(3, "step")]), include_groups=False).reset_index()
    flags = step_long[(step_long.safety_violation) | (step_long.over_action) | (step_long.missed_opportunity) | (step_long.recovery_score < LOW_RECOVERY_THRESHOLD)]
    return pd.concat([edge, flags], ignore_index=True).drop_duplicates(["scenario_type", "baseline_name", "seed", "step"]).sort_values(["scenario_type", "baseline_name", "seed", "step"])


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result = run_closed_loop_runner_integration_rc1(seeds=SEEDS)
    baseline = _write_csv(result.closed_loop_baseline_comparison_summary, "baseline_comparison_summary.csv")
    scenario = _write_csv(result.closed_loop_scenario_breakdown, "scenario_breakdown.csv")
    episode = _write_csv(result.closed_loop_episode_summary, "episode_summary.csv")
    step_sample = _write_csv(build_step_sample(result.closed_loop_step_long), "step_long_sample.csv")
    _write_csv(result.closed_loop_preflight_summary, "preflight_summary.csv")
    _write_csv(result.closed_loop_audit_boundary_summary, "audit_boundary_summary.csv")
    drift = _write_csv(build_drift_diagnosis(baseline, scenario, episode), "drift_diagnosis.csv")
    candidates = _write_csv(build_adjustment_candidates(drift), "adjustment_candidate_register.csv")
    write_report(baseline, scenario, episode, drift, candidates, step_sample)

    print("=== Closed Loop Verification RC1 ===")
    print("Output directory: reports/closed_loop_verification_rc1")
    print("\n=== Baseline Comparison Summary ===")
    print(baseline.to_string(index=False))
    print("\n=== Scenario Breakdown ===")
    print(scenario.to_string(index=False))
    print("\n=== Drift Diagnosis Summary ===")
    if drift.empty:
        print("No drift rows generated.")
    else:
        print(drift.groupby(["drift_type", "severity"]).size().reset_index(name="count").to_string(index=False))
    print("\n=== Adjustment Candidates ===")
    print(candidates.to_string(index=False))
    print("\nDone.")


if __name__ == "__main__":
    main()
