"""Task 2-8j-24b3: multi-scenario stateful rollout validation RC1.

Runs a stricter robustness check before any adoption-hurdle freeze.
This task compares Task24 terrain-operator material against:

- observed v2 NO_OP future trajectories,
- relation-field counterfactual rollouts with the selected operator,
- reversed-operator controls inherited from Task24b2, and
- randomized-operator baselines.

The validation is repeated across multiple synthetic v2 scenario profiles, seeds,
start states, and wait steps.  Results are used only to audit robustness of
future adoption-hurdle candidates; no threshold is updated, no formal action
candidate is created, and the v2 window is not a runtime oracle.
"""
from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
from typing import Any

import numpy as np
import pandas as pd

from .pressure_action_task2_8j_1_candidate_feature_log import CandidateFeatureLogConfig, DEFAULT_V2_WORLD_CONFIG
from .pressure_action_task2_8j_6_macro_game_relation_field_validation import MacroGameRelationFieldConfig, build_and_validate_macro_game_relation_field
from .pressure_action_task2_8j_6b_v2_state_relation_field_reproduction import (
    V2StateRelationFieldReproductionConfig,
    _relation_reconstruct_state_timeline,
    build_state_reproduction_table,
    build_transition_reproduction_table,
    build_relation_consistency_table,
    build_v2_state_relation_field_reproduction_summary,
    validate_v2_state_relation_field_reproduction_tables,
)
from .pressure_action_task2_8j_24_terrain_operator_selection_dry_run import (
    TerrainOperatorSelectionDryRunConfig,
    build_and_validate_terrain_operator_selection_dry_run,
)
from .pressure_action_task2_8j_24b2_v2_stateful_rollout_action_material_validation import (
    build_v2_rollout_start_points,
    build_stateful_rollout_validation,
    build_step_summary as build_b2_step_summary,
    V2StatefulRolloutActionMaterialValidationConfig,
)

TASK2_8J_24B3_VERSION = "multi_scenario_stateful_rollout_validation_rc1"
TASK24_ACCEPTED_DECISION = "terrain_operator_selection_dry_run_ready"

BOUNDARY: dict[str, Any] = {
    "task2_8j_24b3_version": TASK2_8J_24B3_VERSION,
    "validation_only": True,
    "multi_scenario_stateful_rollout_validation": True,
    "observable_v2_no_op_future_used_for_scoring": True,
    "relation_field_counterfactual_rollout_used": True,
    "reversed_operator_control_used": True,
    "randomized_operator_baseline_used": True,
    "v2_window_used_as_validation_surface": True,
    "v2_window_not_runtime_oracle": True,
    "NO_OP_comparison_required": True,
    "multi_seed_multi_start_required": True,
    "multi_scenario_required": True,
    "step_count_sensitivity": True,
    "per_risk_robustness_audit": True,
    "adoption_threshold_tradeoff_audit": True,
    "source_task24_required": True,
    "gt_main_map_name": "static_pca_7",
    "gt_main_component_count": 7,
    "terrain_operator_material_input_used": True,
    "threshold_values_are_provisional": True,
    "threshold_revision_requires_validation": True,
    "no_threshold_update_performed": True,
    "overfit_to_v2_forbidden": True,
    "release_rollback_audit_shaped": False,
    "action_candidate_generated": False,
    "concrete_action_generated": False,
    "action_effect_prediction_generated": False,
    "effect_prediction_model_executed": False,
    "expected_value_final_judgment_performed": False,
    "real_actionmodule_called": False,
    "axis_executed": False,
    "upper_pressure_coupled_now": False,
    "hidden_truth_input": False,
    "future_information_used_as_runtime_input": False,
    "canonical_write_performed": False,
}

REQUIRED_TRUE = [
    "validation_only", "multi_scenario_stateful_rollout_validation", "observable_v2_no_op_future_used_for_scoring",
    "relation_field_counterfactual_rollout_used", "reversed_operator_control_used", "randomized_operator_baseline_used",
    "v2_window_used_as_validation_surface", "v2_window_not_runtime_oracle", "NO_OP_comparison_required",
    "multi_seed_multi_start_required", "multi_scenario_required", "step_count_sensitivity", "per_risk_robustness_audit",
    "adoption_threshold_tradeoff_audit", "source_task24_required", "terrain_operator_material_input_used",
    "threshold_values_are_provisional", "threshold_revision_requires_validation", "no_threshold_update_performed",
    "overfit_to_v2_forbidden",
]
FORBIDDEN_TRUE = [
    "release_rollback_audit_shaped", "action_candidate_generated", "concrete_action_generated",
    "action_effect_prediction_generated", "effect_prediction_model_executed", "expected_value_final_judgment_performed",
    "real_actionmodule_called", "axis_executed", "upper_pressure_coupled_now", "hidden_truth_input",
    "future_information_used_as_runtime_input", "canonical_write_performed",
]

SCENARIO_COLUMNS = list(BOUNDARY) + [
    "scenario_profile", "scenario_role", "seed_count", "start_count", "state_count", "reproduced_state_count",
    "mean_state_event_accuracy", "mean_direction_match_rate", "relation_consistency_pass_count",
    "v2_reproduction_decision", "scenario_status",
]
ROLLOUT_COLUMNS = list(BOUNDARY) + [
    "scenario_profile", "rollout_kind", "rollout_id", "operator_selection_id", "start_id", "seed", "scenario", "t0",
    "risk_name", "selected_operator_name", "action_wait_step", "horizon", "no_op_final_risk", "action_final_risk",
    "negative_control_final_risk", "no_op_peak_risk", "action_peak_risk", "risk_reduction_final", "risk_reduction_peak",
    "negative_control_gap", "side_effect_delta", "rollback_margin", "boundary_margin", "relative_ev_rollout",
    "action_beats_no_op", "action_beats_negative_control", "timing_class", "rollout_status",
]
BASELINE_COLUMNS = list(BOUNDARY) + [
    "baseline_id", "scenario_profile", "risk_name", "action_wait_step", "policy_rollout_count", "random_rollout_count",
    "policy_mean_ev", "random_mean_ev", "policy_minus_random_ev", "policy_beat_no_op_rate", "random_beat_no_op_rate",
    "policy_minus_random_beat_rate", "baseline_status",
]
RISK_COLUMNS = list(BOUNDARY) + [
    "risk_robustness_id", "risk_name", "scenario_count", "policy_rollout_count", "mean_policy_ev", "min_scenario_policy_ev",
    "policy_beat_no_op_rate", "policy_beats_random_scenario_rate", "negative_control_pass_rate", "best_wait_step_mode",
    "risk_adoption_class", "risk_review_reason", "risk_status",
]
STEP_COLUMNS = list(BOUNDARY) + [
    "step_summary_id", "action_wait_step", "scenario_count", "row_count", "policy_mean_ev", "policy_median_ev",
    "policy_beat_no_op_rate", "policy_beats_random_rate", "mean_rollback_margin", "mean_boundary_margin", "step_status",
]
THRESHOLD_COLUMNS = list(BOUNDARY) + [
    "threshold_audit_id", "max_allowed_wait_step", "minimum_relative_ev_candidate", "minimum_rollback_margin_candidate",
    "minimum_policy_minus_random_ev", "accepted_policy_count", "accepted_scenario_count", "accepted_risk_count",
    "accepted_random_failure_count", "accepted_late_count", "threshold_candidate_class", "may_update_threshold_now",
    "requires_validation_before_update", "threshold_status",
]
CHECK_COLUMNS = list(BOUNDARY) + ["check_id", "check_scope", "check_description", "expected_value", "observed_value", "check_status"]
SUMMARY_COLUMNS = list(BOUNDARY) + [
    "scenario_count", "operator_selection_count", "total_start_count", "policy_rollout_row_count", "random_rollout_row_count",
    "baseline_comparison_count", "risk_robustness_count", "threshold_audit_count", "unique_seed_count",
    "policy_action_beats_no_op_rate", "policy_beats_random_rate", "negative_control_pass_rate", "positive_policy_ev_rate",
    "robust_adoptable_risk_count", "review_risk_count", "best_wait_step", "best_step_policy_ev",
    "threshold_candidate_viable_count", "validation_check_count", "validation_check_pass_count", "task24_ready",
    "multi_scenario_stateful_rollout_validation_decision", "next_task",
]


@dataclass(frozen=True)
class MultiScenarioStatefulRolloutValidationConfig:
    require_task24_ready: bool = True
    feature_steps: int = 42
    seeds: tuple[int, ...] = (501, 502, 503, 504, 505)
    horizon: int = 6
    max_wait_step: int = 5
    start_stride: int = 4
    max_starts_per_scenario: int = 45
    min_scenarios: int = 4
    min_total_rollouts: int = 1200


def _with_boundary(row: dict[str, Any]) -> dict[str, Any]:
    return {**BOUNDARY, **row}


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return float(default)
    return float(out) if np.isfinite(out) else float(default)


def _scenario_configs() -> list[tuple[str, str, dict[str, Any], float, float, float]]:
    base = deepcopy(DEFAULT_V2_WORLD_CONFIG)
    def make(label: str, role: str, changes: dict[str, dict[str, Any]], noise: float, drift: float, coupling: float):
        cfg = deepcopy(base)
        for section, vals in changes.items():
            cfg.setdefault(section, {}).update(vals)
        return label, role, cfg, noise, drift, coupling
    return [
        make("shrinking_equilibrium", "baseline_shrinking_equilibrium", {}, 0.018, 0.006, 0.045),
        make("resource_depletion_stress", "resource_pressure_high", {"resource_settings": {"initial_shared_resource": 0.58, "resource_recovery_rate": 0.010, "resource_depletion_rate": 0.052}}, 0.022, 0.008, 0.050),
        make("information_delay_stress", "information_quality_low", {"information_settings": {"information_delay_steps": 4, "information_distortion_scale": 0.105, "misread_probability": 0.18, "hidden_state_visibility": 0.15}}, 0.025, 0.007, 0.044),
        make("lock_in_side_effect_stress", "relation_lock_high", {"side_effect_settings": {"stabilization_lockin_side_effect": 0.36, "exploration_exploitation_risk": 0.28}, "active_dynamics": {"trust_decay": {"enabled": True, "intensity": 0.065}, "defensive_hoarding": {"enabled": True, "intensity": 0.060}, "hidden_damage_growth": {"enabled": True, "intensity": 0.052}, "no_op_decay": {"enabled": True, "intensity": 0.038}}}, 0.020, 0.009, 0.043),
        make("noisy_recovery_stress", "high_noise_recovery_mixed", {"resource_settings": {"resource_recovery_rate": 0.026, "resource_depletion_rate": 0.033}, "information_settings": {"information_distortion_scale": 0.090, "misread_probability": 0.16}}, 0.040, 0.013, 0.041),
    ]


def _compute_scenario_state(label: str, role: str, world_config: dict[str, Any], noise: float, drift: float, coupling: float, cfg: MultiScenarioStatefulRolloutValidationConfig):
    feature_cfg = CandidateFeatureLogConfig(
        steps=cfg.feature_steps,
        seeds=cfg.seeds,
        scenario=f"v2_{label}",
        action_coupling=coupling,
        noise_scale=noise,
        drift_scale=drift,
        world_profile=f"pseudo_reality_v2_{label}",
        world_config=world_config,
        window_sizes=(1, 6, 12),
    )
    signal_table, task6_state_table, relation_field, _summary6, task6_errors, _json6 = build_and_validate_macro_game_relation_field(feature_cfg, MacroGameRelationFieldConfig())
    state_timeline = _relation_reconstruct_state_timeline(task6_state_table, relation_field)
    state_reproduction = build_state_reproduction_table(state_timeline, relation_field, V2StateRelationFieldReproductionConfig())
    transition = build_transition_reproduction_table(state_timeline, V2StateRelationFieldReproductionConfig())
    consistency = build_relation_consistency_table(state_timeline, relation_field, V2StateRelationFieldReproductionConfig())
    final6b = build_v2_state_relation_field_reproduction_summary(state_reproduction, transition, consistency)
    errors = [f"task6:{e}" for e in task6_errors]
    errors.extend(validate_v2_state_relation_field_reproduction_tables(state_reproduction, state_timeline, transition, consistency, final6b))
    return signal_table, state_timeline, relation_field, final6b, errors


def build_scenario_summary_rows(scenario_payloads: list[dict[str, Any]]) -> pd.DataFrame:
    rows = []
    for p in scenario_payloads:
        final6b = p["final6b"]
        starts = p["starts"]
        errors = p["errors"]
        rows.append(_with_boundary({
            "scenario_profile": p["label"],
            "scenario_role": p["role"],
            "seed_count": int(starts["seed"].nunique()) if not starts.empty else 0,
            "start_count": int(len(starts)),
            "state_count": _safe_int(final6b["state_count"].iloc[0]) if not final6b.empty else 0,
            "reproduced_state_count": _safe_int(final6b["reproduced_state_count"].iloc[0]) if not final6b.empty else 0,
            "mean_state_event_accuracy": _safe_float(final6b["mean_state_event_accuracy"].iloc[0]) if not final6b.empty else 0.0,
            "mean_direction_match_rate": _safe_float(final6b["mean_direction_match_rate"].iloc[0]) if not final6b.empty else 0.0,
            "relation_consistency_pass_count": _safe_int(final6b["relation_consistency_pass_count"].iloc[0]) if not final6b.empty else 0,
            "v2_reproduction_decision": str(final6b["v2_state_reproduction_decision"].iloc[0]) if not final6b.empty else "empty",
            "scenario_status": "scenario_ready" if not errors else "scenario_generated_with_reproduction_warnings",
        }))
    return pd.DataFrame(rows, columns=SCENARIO_COLUMNS)


def _randomized_selection(selection: pd.DataFrame, scenario_label: str) -> pd.DataFrame:
    out = selection.copy()
    names = sorted(selection["selected_operator_name"].astype(str).unique().tolist())
    if len(names) <= 1:
        return out
    shift = (sum(ord(c) for c in scenario_label) % (len(names) - 1)) + 1
    mapping = {name: names[(i + shift) % len(names)] for i, name in enumerate(names)}
    out["selected_operator_name"] = out["selected_operator_name"].astype(str).map(mapping).fillna(out["selected_operator_name"].astype(str))
    out["operator_selection_id"] = out["operator_selection_id"].astype(str) + "_randomized_" + scenario_label
    return out


def build_multi_scenario_rollouts(selection: pd.DataFrame, scenario_payloads: list[dict[str, Any]], cfg: MultiScenarioStatefulRolloutValidationConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_policy = []
    all_random = []
    b2cfg = V2StatefulRolloutActionMaterialValidationConfig(
        require_task24_ready=False,
        require_task6b_ready=False,
        feature_steps=cfg.feature_steps,
        seeds=cfg.seeds,
        horizon=cfg.horizon,
        max_wait_step=cfg.max_wait_step,
        start_stride=cfg.start_stride,
        max_starts=cfg.max_starts_per_scenario,
    )
    for p in scenario_payloads:
        label = p["label"]
        starts = p["starts"]
        state_timeline = p["state_timeline"]
        relation_field = p["relation_field"]
        policy = build_stateful_rollout_validation(selection, state_timeline, relation_field, starts, b2cfg)
        random_sel = _randomized_selection(selection, label)
        random_rollout = build_stateful_rollout_validation(random_sel, state_timeline, relation_field, starts, b2cfg)
        if not policy.empty:
            policy = policy.copy()
            policy.insert(0, "scenario_profile", label)
            policy.insert(1, "rollout_kind", "policy_operator")
            all_policy.append(policy)
        if not random_rollout.empty:
            random_rollout = random_rollout.copy()
            random_rollout.insert(0, "scenario_profile", label)
            random_rollout.insert(1, "rollout_kind", "randomized_operator_baseline")
            all_random.append(random_rollout)
    policy_df = pd.concat(all_policy, ignore_index=True) if all_policy else pd.DataFrame()
    random_df = pd.concat(all_random, ignore_index=True) if all_random else pd.DataFrame()
    # Convert Task24b2 boundary columns into Task24b3 boundary columns by rewrapping rows.
    def rewrap(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame(columns=ROLLOUT_COLUMNS)
        rows = []
        keep = [c for c in ROLLOUT_COLUMNS if c not in BOUNDARY]
        for _, r in df.iterrows():
            rows.append(_with_boundary({c: r[c] for c in keep}))
        return pd.DataFrame(rows, columns=ROLLOUT_COLUMNS)
    return rewrap(policy_df), rewrap(random_df)


def build_randomized_operator_baseline(policy: pd.DataFrame, random_rollout: pd.DataFrame) -> pd.DataFrame:
    rows = []
    if policy.empty or random_rollout.empty:
        return pd.DataFrame(columns=BASELINE_COLUMNS)
    for (scenario, risk, step), pg in policy.groupby(["scenario_profile", "risk_name", "action_wait_step"], sort=True):
        rg = random_rollout[(random_rollout["scenario_profile"].astype(str) == str(scenario)) & (random_rollout["risk_name"].astype(str) == str(risk)) & (random_rollout["action_wait_step"].astype(int) == int(step))]
        if rg.empty:
            continue
        pe = float(pg["relative_ev_rollout"].astype(float).mean())
        re = float(rg["relative_ev_rollout"].astype(float).mean())
        pbeat = float(pg["action_beats_no_op"].astype(bool).mean())
        rbeat = float(rg["action_beats_no_op"].astype(bool).mean())
        status = "policy_operator_beats_randomized_baseline" if pe > re and pbeat >= rbeat else "policy_operator_not_clearly_above_randomized_baseline"
        rows.append(_with_boundary({
            "baseline_id": f"baseline_{scenario}_{risk}_wait_{int(step)}",
            "scenario_profile": str(scenario),
            "risk_name": str(risk),
            "action_wait_step": int(step),
            "policy_rollout_count": int(len(pg)),
            "random_rollout_count": int(len(rg)),
            "policy_mean_ev": round(pe, 6),
            "random_mean_ev": round(re, 6),
            "policy_minus_random_ev": round(pe - re, 6),
            "policy_beat_no_op_rate": round(pbeat, 6),
            "random_beat_no_op_rate": round(rbeat, 6),
            "policy_minus_random_beat_rate": round(pbeat - rbeat, 6),
            "baseline_status": status,
        }))
    return pd.DataFrame(rows, columns=BASELINE_COLUMNS)


def build_per_risk_robustness(policy: pd.DataFrame, baseline: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for risk, g in policy.groupby("risk_name", sort=True):
        scen_ev = g.groupby("scenario_profile")["relative_ev_rollout"].mean()
        scen_beats_random = []
        for scenario in sorted(g["scenario_profile"].astype(str).unique().tolist()):
            bg = baseline[(baseline["scenario_profile"].astype(str) == scenario) & (baseline["risk_name"].astype(str) == str(risk))]
            scen_beats_random.append(bool(not bg.empty and float(bg["policy_minus_random_ev"].mean()) > 0.0))
        best_by_step = g.groupby("action_wait_step")["relative_ev_rollout"].mean().sort_values(ascending=False)
        best_wait = int(best_by_step.index[0]) if not best_by_step.empty else -1
        mean_ev = float(g["relative_ev_rollout"].astype(float).mean())
        min_scen = float(scen_ev.min()) if not scen_ev.empty else 0.0
        beat_rate = float(g["action_beats_no_op"].astype(bool).mean())
        neg_rate = float(g["action_beats_negative_control"].astype(bool).mean())
        scen_random_rate = float(np.mean(scen_beats_random)) if scen_beats_random else 0.0
        if mean_ev >= 0.10 and min_scen >= 0.00 and beat_rate >= 0.55 and scen_random_rate >= 0.60 and neg_rate >= 0.90:
            cls = "robust_adoptable_candidate"
            reason = "positive_across_scenarios_and_above_randomized_baseline"
        elif mean_ev >= 0.04 and beat_rate >= 0.45:
            cls = "review_candidate"
            reason = "some_positive_signal_but_not_robust_enough_for_hurdle_freeze"
        else:
            cls = "do_not_adopt_now"
            reason = "weak_or_nonrobust_against_NO_OP_or_randomized_baseline"
        rows.append(_with_boundary({
            "risk_robustness_id": f"risk_robustness_{risk}",
            "risk_name": str(risk),
            "scenario_count": int(g["scenario_profile"].nunique()),
            "policy_rollout_count": int(len(g)),
            "mean_policy_ev": round(mean_ev, 6),
            "min_scenario_policy_ev": round(min_scen, 6),
            "policy_beat_no_op_rate": round(beat_rate, 6),
            "policy_beats_random_scenario_rate": round(scen_random_rate, 6),
            "negative_control_pass_rate": round(neg_rate, 6),
            "best_wait_step_mode": best_wait,
            "risk_adoption_class": cls,
            "risk_review_reason": reason,
            "risk_status": "per_risk_robustness_audited",
        }))
    return pd.DataFrame(rows, columns=RISK_COLUMNS)


def build_multi_scenario_step_summary(policy: pd.DataFrame, baseline: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for step, g in policy.groupby("action_wait_step", sort=True):
        bg = baseline[baseline["action_wait_step"].astype(int) == int(step)]
        beats_random = float((bg["policy_minus_random_ev"].astype(float) > 0).mean()) if not bg.empty else 0.0
        rows.append(_with_boundary({
            "step_summary_id": f"multi_scenario_step_{int(step)}",
            "action_wait_step": int(step),
            "scenario_count": int(g["scenario_profile"].nunique()),
            "row_count": int(len(g)),
            "policy_mean_ev": round(float(g["relative_ev_rollout"].astype(float).mean()), 6),
            "policy_median_ev": round(float(g["relative_ev_rollout"].astype(float).median()), 6),
            "policy_beat_no_op_rate": round(float(g["action_beats_no_op"].astype(bool).mean()), 6),
            "policy_beats_random_rate": round(beats_random, 6),
            "mean_rollback_margin": round(float(g["rollback_margin"].astype(float).mean()), 6),
            "mean_boundary_margin": round(float(g["boundary_margin"].astype(float).mean()), 6),
            "step_status": "multi_scenario_step_summary_ready",
        }))
    return pd.DataFrame(rows, columns=STEP_COLUMNS)


def build_threshold_audit(policy: pd.DataFrame, baseline: pd.DataFrame) -> pd.DataFrame:
    merged = policy.merge(
        baseline[["scenario_profile", "risk_name", "action_wait_step", "policy_minus_random_ev"]],
        on=["scenario_profile", "risk_name", "action_wait_step"],
        how="left",
    )
    merged["policy_minus_random_ev"] = pd.to_numeric(merged["policy_minus_random_ev"], errors="coerce").fillna(0.0)
    rows = []
    idx = 1
    for max_wait in [0, 1, 2, 3, 4, 5]:
        for min_ev in [0.00, 0.05, 0.10, 0.15]:
            for min_rb in [0.35, 0.50, 0.65]:
                for min_adv in [0.00, 0.04, 0.08]:
                    e = merged[
                        (merged["action_wait_step"].astype(int) <= max_wait)
                        & (merged["relative_ev_rollout"].astype(float) >= min_ev)
                        & (merged["rollback_margin"].astype(float) >= min_rb)
                        & (merged["policy_minus_random_ev"].astype(float) >= min_adv)
                    ]
                    count = int(len(e))
                    scen = int(e["scenario_profile"].nunique()) if count else 0
                    risk = int(e["risk_name"].nunique()) if count else 0
                    random_fail = int((e["policy_minus_random_ev"].astype(float) <= 0.0).sum()) if count else 0
                    late = int((e["action_wait_step"].astype(int) >= 3).sum()) if count else 0
                    if count == 0:
                        cls = "too_strict_or_no_robust_window"
                    elif scen < 3:
                        cls = "insufficient_scenario_coverage"
                    elif random_fail > 0:
                        cls = "admits_random_baseline_failures_reject"
                    elif late > 0:
                        cls = "admits_late_cases_review_timing_loss"
                    else:
                        cls = "candidate_for_later_provisional_policy"
                    rows.append(_with_boundary({
                        "threshold_audit_id": f"threshold_{idx:04d}",
                        "max_allowed_wait_step": int(max_wait),
                        "minimum_relative_ev_candidate": float(min_ev),
                        "minimum_rollback_margin_candidate": float(min_rb),
                        "minimum_policy_minus_random_ev": float(min_adv),
                        "accepted_policy_count": count,
                        "accepted_scenario_count": scen,
                        "accepted_risk_count": risk,
                        "accepted_random_failure_count": random_fail,
                        "accepted_late_count": late,
                        "threshold_candidate_class": cls,
                        "may_update_threshold_now": False,
                        "requires_validation_before_update": True,
                        "threshold_status": "multi_scenario_threshold_audited_no_update",
                    }))
                    idx += 1
    return pd.DataFrame(rows, columns=THRESHOLD_COLUMNS)


def build_checks(scenarios: pd.DataFrame, policy: pd.DataFrame, random_rollout: pd.DataFrame, baseline: pd.DataFrame, risk: pd.DataFrame, step: pd.DataFrame, threshold: pd.DataFrame, task24_ready: bool, cfg: MultiScenarioStatefulRolloutValidationConfig) -> pd.DataFrame:
    checks = [
        ("check_task24_ready", "upstream", "Task24 terrain operator material is ready.", True, task24_ready),
        ("check_scenario_count", "coverage", "At least the configured number of scenario profiles is evaluated.", True, len(scenarios) >= cfg.min_scenarios),
        ("check_seed_coverage", "coverage", "At least three seeds are represented.", True, int(policy["seed"].nunique()) >= 3 if not policy.empty else False),
        ("check_rollout_volume", "coverage", "Rollout volume is materially larger than previous small proxy sweeps.", True, len(policy) >= cfg.min_total_rollouts),
        ("check_random_baseline", "control", "Randomized operator baseline rollout exists.", True, len(random_rollout) > 0 and len(baseline) > 0),
        ("check_negative_control", "control", "Reversed-operator control result is present in policy rows.", True, bool(policy["action_beats_negative_control"].astype(bool).any()) if not policy.empty else False),
        ("check_per_risk", "risk", "Per-risk robustness audit exists.", True, len(risk) > 0),
        ("check_step_coverage", "step", "All wait steps 0..5 are represented.", True, set(policy["action_wait_step"].astype(int)) == set(range(6)) if not policy.empty else False),
        ("check_threshold_audit", "threshold", "Threshold audit exists and does not update thresholds.", True, len(threshold) > 0 and not bool(threshold["may_update_threshold_now"].astype(bool).any())),
        ("check_no_action_candidate", "boundary", "No formal action candidate is generated.", False, bool(policy["action_candidate_generated"].astype(bool).any()) if not policy.empty else True),
        ("check_no_real_execution", "boundary", "No real ActionModule call or axis execution occurs.", False, bool(policy["real_actionmodule_called"].astype(bool).any() or policy["axis_executed"].astype(bool).any()) if not policy.empty else True),
        ("check_no_runtime_future", "boundary", "Future v2 states are not used as runtime input.", False, bool(policy["future_information_used_as_runtime_input"].astype(bool).any()) if not policy.empty else True),
    ]
    return pd.DataFrame([_with_boundary({"check_id": c[0], "check_scope": c[1], "check_description": c[2], "expected_value": bool(c[3]), "observed_value": bool(c[4]), "check_status": "pass" if bool(c[3]) == bool(c[4]) else "fail"}) for c in checks], columns=CHECK_COLUMNS)


def build_final_summary(scenarios: pd.DataFrame, selection: pd.DataFrame, policy: pd.DataFrame, random_rollout: pd.DataFrame, baseline: pd.DataFrame, risk: pd.DataFrame, step: pd.DataFrame, threshold: pd.DataFrame, checks: pd.DataFrame, task24_ready: bool) -> pd.DataFrame:
    pass_count = int((checks["check_status"].astype(str) == "pass").sum()) if not checks.empty else 0
    step_sorted = step.sort_values("policy_mean_ev", ascending=False) if not step.empty else pd.DataFrame()
    best_step = int(step_sorted["action_wait_step"].iloc[0]) if not step_sorted.empty else -1
    best_ev = float(step_sorted["policy_mean_ev"].iloc[0]) if not step_sorted.empty else 0.0
    robust = int((risk["risk_adoption_class"].astype(str) == "robust_adoptable_candidate").sum()) if not risk.empty else 0
    review = int((risk["risk_adoption_class"].astype(str) != "robust_adoptable_candidate").sum()) if not risk.empty else 0
    viable = int((threshold["threshold_candidate_class"].astype(str) == "candidate_for_later_provisional_policy").sum()) if not threshold.empty else 0
    pbr = float((baseline["policy_minus_random_ev"].astype(float) > 0.0).mean()) if not baseline.empty else 0.0
    decision = "multi_scenario_stateful_rollout_validation_ready" if task24_ready and len(checks) == pass_count else "multi_scenario_stateful_rollout_validation_needs_review"
    return pd.DataFrame([_with_boundary({
        "scenario_count": len(scenarios),
        "operator_selection_count": len(selection),
        "total_start_count": int(scenarios["start_count"].astype(int).sum()) if not scenarios.empty else 0,
        "policy_rollout_row_count": len(policy),
        "random_rollout_row_count": len(random_rollout),
        "baseline_comparison_count": len(baseline),
        "risk_robustness_count": len(risk),
        "threshold_audit_count": len(threshold),
        "unique_seed_count": int(policy["seed"].nunique()) if not policy.empty else 0,
        "policy_action_beats_no_op_rate": round(float(policy["action_beats_no_op"].astype(bool).mean()), 6) if not policy.empty else 0.0,
        "policy_beats_random_rate": round(pbr, 6),
        "negative_control_pass_rate": round(float(policy["action_beats_negative_control"].astype(bool).mean()), 6) if not policy.empty else 0.0,
        "positive_policy_ev_rate": round(float((policy["relative_ev_rollout"].astype(float) > 0.0).mean()), 6) if not policy.empty else 0.0,
        "robust_adoptable_risk_count": robust,
        "review_risk_count": review,
        "best_wait_step": best_step,
        "best_step_policy_ev": round(best_ev, 6),
        "threshold_candidate_viable_count": viable,
        "validation_check_count": len(checks),
        "validation_check_pass_count": pass_count,
        "task24_ready": bool(task24_ready),
        "multi_scenario_stateful_rollout_validation_decision": decision,
        "next_task": "Task 2-8j-24c only after review of robust risk classes; otherwise add targeted stress validation",
    })], columns=SUMMARY_COLUMNS)


def validate_tables(scenarios: pd.DataFrame, policy: pd.DataFrame, random_rollout: pd.DataFrame, baseline: pd.DataFrame, risk: pd.DataFrame, step: pd.DataFrame, threshold: pd.DataFrame, checks: pd.DataFrame, final_summary: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    tables = {"scenarios": (scenarios, SCENARIO_COLUMNS), "policy": (policy, ROLLOUT_COLUMNS), "random_rollout": (random_rollout, ROLLOUT_COLUMNS), "baseline": (baseline, BASELINE_COLUMNS), "risk": (risk, RISK_COLUMNS), "step": (step, STEP_COLUMNS), "threshold": (threshold, THRESHOLD_COLUMNS), "checks": (checks, CHECK_COLUMNS), "final_summary": (final_summary, SUMMARY_COLUMNS)}
    for name, (table, cols) in tables.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_24b3_empty_table:{name}"); continue
        missing = [c for c in cols if c not in table.columns]
        if missing:
            errors.append(f"task2_8j_24b3_missing_columns:{name}:" + ",".join(missing)); continue
        for col in REQUIRED_TRUE:
            if not bool(table[col].astype(bool).all()):
                errors.append(f"task2_8j_24b3_required_true_not_all_true:{name}:{col}")
        for col in FORBIDDEN_TRUE:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_24b3_forbidden_true:{name}:{col}")
    if checks is not None and not checks.empty and not bool((checks["check_status"].astype(str) == "pass").all()):
        errors.append("task2_8j_24b3_check_failed")
    if threshold is not None and not threshold.empty:
        if bool(threshold["may_update_threshold_now"].astype(bool).any()):
            errors.append("task2_8j_24b3_threshold_update_attempted")
        if not bool(threshold["requires_validation_before_update"].astype(bool).all()):
            errors.append("task2_8j_24b3_threshold_candidate_without_validation_requirement")
    return errors


def build_and_validate_multi_scenario_stateful_rollout_validation(cfg: MultiScenarioStatefulRolloutValidationConfig | None = None, **_unused: object) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    cfg = cfg or MultiScenarioStatefulRolloutValidationConfig()
    selection, _review24, _checks24, _final24, task24_errors, task24_summary = build_and_validate_terrain_operator_selection_dry_run(cfg=TerrainOperatorSelectionDryRunConfig())
    task24_ready = len(task24_errors) == 0 and str(task24_summary.get("terrain_operator_selection_dry_run_decision", "")).startswith(TASK24_ACCEPTED_DECISION)
    if not cfg.require_task24_ready:
        task24_ready = True
    scenario_payloads = []
    scenario_errors: list[str] = []
    b2cfg = V2StatefulRolloutActionMaterialValidationConfig(require_task24_ready=False, require_task6b_ready=False, feature_steps=cfg.feature_steps, seeds=cfg.seeds, horizon=cfg.horizon, max_wait_step=cfg.max_wait_step, start_stride=cfg.start_stride, max_starts=cfg.max_starts_per_scenario)
    for label, role, world_config, noise, drift, coupling in _scenario_configs():
        _signal, state_timeline, relation_field, final6b, errs = _compute_scenario_state(label, role, world_config, noise, drift, coupling, cfg)
        starts = build_v2_rollout_start_points(state_timeline, b2cfg)
        scenario_payloads.append({"label": label, "role": role, "state_timeline": state_timeline, "relation_field": relation_field, "final6b": final6b, "starts": starts, "errors": errs})
        scenario_errors.extend([f"scenario_{label}:{e}" for e in errs])
    scenarios = build_scenario_summary_rows(scenario_payloads)
    policy, random_rollout = build_multi_scenario_rollouts(selection, scenario_payloads, cfg)
    baseline = build_randomized_operator_baseline(policy, random_rollout)
    risk = build_per_risk_robustness(policy, baseline)
    step = build_multi_scenario_step_summary(policy, baseline)
    threshold = build_threshold_audit(policy, baseline)
    checks = build_checks(scenarios, policy, random_rollout, baseline, risk, step, threshold, task24_ready, cfg)
    final_summary = build_final_summary(scenarios, selection, policy, random_rollout, baseline, risk, step, threshold, checks, task24_ready)
    errors: list[str] = []
    if cfg.require_task24_ready:
        errors += [f"task2_8j_24b3_upstream_24_error:{e}" for e in task24_errors]
    # Scenario reproduction warnings are reported in scenario_status, but not converted to fatal errors unless tables/checks fail.
    errors += validate_tables(scenarios, policy, random_rollout, baseline, risk, step, threshold, checks, final_summary)
    summary = {
        "gt_main_map_name": "static_pca_7",
        "gt_main_component_count": 7,
        "task24_decision": task24_summary.get("terrain_operator_selection_dry_run_decision", ""),
        "scenario_count": _safe_int(final_summary["scenario_count"].iloc[0]),
        "operator_selection_count": _safe_int(final_summary["operator_selection_count"].iloc[0]),
        "total_start_count": _safe_int(final_summary["total_start_count"].iloc[0]),
        "policy_rollout_row_count": _safe_int(final_summary["policy_rollout_row_count"].iloc[0]),
        "random_rollout_row_count": _safe_int(final_summary["random_rollout_row_count"].iloc[0]),
        "baseline_comparison_count": _safe_int(final_summary["baseline_comparison_count"].iloc[0]),
        "risk_robustness_count": _safe_int(final_summary["risk_robustness_count"].iloc[0]),
        "threshold_audit_count": _safe_int(final_summary["threshold_audit_count"].iloc[0]),
        "unique_seed_count": _safe_int(final_summary["unique_seed_count"].iloc[0]),
        "policy_action_beats_no_op_rate": float(final_summary["policy_action_beats_no_op_rate"].iloc[0]),
        "policy_beats_random_rate": float(final_summary["policy_beats_random_rate"].iloc[0]),
        "negative_control_pass_rate": float(final_summary["negative_control_pass_rate"].iloc[0]),
        "positive_policy_ev_rate": float(final_summary["positive_policy_ev_rate"].iloc[0]),
        "robust_adoptable_risk_count": _safe_int(final_summary["robust_adoptable_risk_count"].iloc[0]),
        "review_risk_count": _safe_int(final_summary["review_risk_count"].iloc[0]),
        "best_wait_step": _safe_int(final_summary["best_wait_step"].iloc[0]),
        "best_step_policy_ev": float(final_summary["best_step_policy_ev"].iloc[0]),
        "threshold_candidate_viable_count": _safe_int(final_summary["threshold_candidate_viable_count"].iloc[0]),
        "validation_check_count": _safe_int(final_summary["validation_check_count"].iloc[0]),
        "validation_check_pass_count": _safe_int(final_summary["validation_check_pass_count"].iloc[0]),
        "task24_ready": bool(task24_ready),
        "scenario_reproduction_warning_count": len(scenario_errors),
        "multi_scenario_stateful_rollout_validation_decision": str(final_summary["multi_scenario_stateful_rollout_validation_decision"].iloc[0]),
        "randomized_operator_baseline_used": True,
        "per_risk_robustness_audit": True,
        "no_threshold_update_performed": True,
        "action_candidate_generated": False,
        "real_actionmodule_called": False,
        "axis_executed": False,
        "validation_errors": errors,
    }
    return scenarios, policy, random_rollout, baseline, risk, step, threshold, checks, final_summary, errors, summary
