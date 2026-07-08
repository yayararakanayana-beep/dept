"""Task 2-8j-6b: v2 state reproduction from the fixed-7-axis relation field RC1.

Purpose:
    Check whether the relation field built in Task 2-8j-6 reproduces observable
    v2-side states as game structure, rather than merely producing plausible
    macro-signal correlations.

Position:
    Task 2-8j-6 proved that a macro-game relation field can be extracted from
    fixed static_pca_7 G_t.  This 6b task asks the next question: when that
    relation field is used as a game-structure map, does it reproduce the
    observable v2 states, state transitions, and signal relations?

Boundary:
    - validation only
    - fixed static_pca_7 main map inherited from Task 2-8j-6
    - no effective-dimension re-fitting
    - no axis mutation
    - no residual auxiliary dimension injection into G_t main map
    - no action-weight conversion
    - no upper-pressure connection
    - no ActionFrame / ActionModule / FullSpec runtime / canonical write
    - no hidden-truth / future-information input
"""
from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

import numpy as np
import pandas as pd

from .pressure_action_task2_8j_1_candidate_feature_log import CandidateFeatureLogConfig
from .pressure_action_task2_8j_6_macro_game_relation_field_validation import (
    MacroGameRelationFieldConfig,
    build_and_validate_macro_game_relation_field,
)

TASK2_8J_6B_VERSION = "v2_state_relation_field_reproduction_rc1"
TASK2_8J_6B_CONTRACT = (
    "Task2_8j_6b_v2_state_relation_field_reproduction__"
    "fixed_static_pca_7_relation_field__observable_v2_state_only__"
    "no_hidden_truth_no_axis_mutation_no_runtime_write"
)

BOUNDARY_COLUMNS = [
    "task2_8j_6b_version",
    "task2_8j_6b_contract",
    "validation_only",
    "incomplete_observation_assumption",
    "gt_main_map_name",
    "gt_main_component_count",
    "relation_field_source",
    "observable_v2_state_only",
    "runtime_policy_input",
    "fullspec_runtime_connected",
    "upper_pressure_connected",
    "action_frame_created",
    "actionmodule_called",
    "canonical_write_performed",
    "gk_writeback_performed",
    "ot_writeback_performed",
    "effective_dimension_refit_performed",
    "axis_mutation_performed",
    "residual_auxiliary_injected_into_gt_main",
    "dynamics_axis_extracted_for_action",
    "action_weight_converted",
    "hidden_truth_input",
    "future_information_used",
]

REQUIRED_STATE_REPRODUCTION_COLUMNS = BOUNDARY_COLUMNS + [
    "macro_signal",
    "rows",
    "relation_source_count",
    "rmse",
    "baseline_rmse",
    "r2_vs_mean_baseline",
    "correlation",
    "state_event_accuracy",
    "state_event_f1",
    "state_reproduction_status",
]

REQUIRED_STATE_TIMELINE_COLUMNS = BOUNDARY_COLUMNS + [
    "seed",
    "scenario",
    "t",
    "macro_signal",
    "observable_v2_state_intensity",
    "gt_signal_intensity",
    "relation_field_reproduced_intensity",
    "reproduction_residual",
    "observable_state_event",
    "reproduced_state_event",
]

REQUIRED_TRANSITION_COLUMNS = BOUNDARY_COLUMNS + [
    "macro_signal",
    "transition_rows",
    "direction_match_rate",
    "rising_event_accuracy",
    "falling_event_accuracy",
    "transition_reproduction_status",
]

REQUIRED_RELATION_CONSISTENCY_COLUMNS = BOUNDARY_COLUMNS + [
    "source_macro_signal",
    "target_macro_signal",
    "observable_same_time_correlation",
    "observable_lagged_correlation",
    "relation_field_same_time_correlation",
    "relation_field_lagged_correlation",
    "same_time_sign_match",
    "lagged_sign_match",
    "relation_strength_gap",
    "relation_consistency_status",
]

REQUIRED_SUMMARY_COLUMNS = BOUNDARY_COLUMNS + [
    "state_count",
    "reproduced_state_count",
    "mean_state_r2",
    "mean_state_correlation",
    "mean_state_event_accuracy",
    "mean_direction_match_rate",
    "relation_consistency_count",
    "relation_consistency_pass_count",
    "weak_state_names",
    "v2_state_reproduction_decision",
    "next_task",
]


@dataclass(frozen=True)
class V2StateRelationFieldReproductionConfig:
    state_event_quantile: float = 0.67
    min_state_r2_for_pass: float = 0.0
    min_state_corr_for_pass: float = 0.35
    min_event_accuracy_for_pass: float = 0.55
    min_direction_match_for_pass: float = 0.55
    relation_consistency_gap_threshold: float = 0.45


def _boundary_payload() -> dict:
    return {
        "task2_8j_6b_version": TASK2_8J_6B_VERSION,
        "task2_8j_6b_contract": TASK2_8J_6B_CONTRACT,
        "validation_only": True,
        "incomplete_observation_assumption": True,
        "gt_main_map_name": "static_pca_7",
        "gt_main_component_count": 7,
        "relation_field_source": "Task2_8j_6_macro_game_relation_field",
        "observable_v2_state_only": True,
        "runtime_policy_input": False,
        "fullspec_runtime_connected": False,
        "upper_pressure_connected": False,
        "action_frame_created": False,
        "actionmodule_called": False,
        "canonical_write_performed": False,
        "gk_writeback_performed": False,
        "ot_writeback_performed": False,
        "effective_dimension_refit_performed": False,
        "axis_mutation_performed": False,
        "residual_auxiliary_injected_into_gt_main": False,
        "dynamics_axis_extracted_for_action": False,
        "action_weight_converted": False,
        "hidden_truth_input": False,
        "future_information_used": False,
    }


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return float(default)
    if not np.isfinite(out):
        return float(default)
    return float(out)


def _safe_mean(values: pd.Series | list[float] | np.ndarray, default: float = 0.0) -> float:
    arr = pd.to_numeric(pd.Series(values), errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if arr.empty:
        return float(default)
    return float(arr.mean())


def _safe_corr(a: np.ndarray, b: np.ndarray) -> float:
    x = np.asarray(a, dtype=float)
    y = np.asarray(b, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    x = x[mask]
    y = y[mask]
    if len(x) < 3 or float(np.std(x)) <= 1e-12 or float(np.std(y)) <= 1e-12:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])


def _sign_match(a: float, b: float, *, eps: float = 1e-9) -> bool:
    if abs(a) <= eps or abs(b) <= eps:
        return True
    return (a >= 0.0 and b >= 0.0) or (a < 0.0 and b < 0.0)


def _f1_score(true_event: np.ndarray, pred_event: np.ndarray) -> float:
    y = np.asarray(true_event, dtype=bool)
    p = np.asarray(pred_event, dtype=bool)
    tp = float(np.logical_and(y, p).sum())
    fp = float(np.logical_and(~y, p).sum())
    fn = float(np.logical_and(y, ~p).sum())
    denom = (2.0 * tp) + fp + fn
    if denom <= 1e-12:
        return 0.0
    return float((2.0 * tp) / denom)


def _state_status(r2: float, corr: float, acc: float, cfg: V2StateRelationFieldReproductionConfig) -> str:
    if r2 >= cfg.min_state_r2_for_pass and abs(corr) >= cfg.min_state_corr_for_pass and acc >= cfg.min_event_accuracy_for_pass:
        return "v2_state_reproduced_by_relation_field"
    if abs(corr) >= cfg.min_state_corr_for_pass or acc >= cfg.min_event_accuracy_for_pass:
        return "watch_partial_v2_state_reproduction"
    return "weak_v2_state_reproduction"


def _timeline_from_task6_state_table(state_table: pd.DataFrame) -> pd.DataFrame:
    if state_table is None or state_table.empty:
        return pd.DataFrame()
    cols = ["seed", "scenario", "t", "macro_signal", "observed_signal_intensity", "gt_predicted_signal_intensity"]
    out = state_table[cols].copy()
    out = out.rename(
        columns={
            "observed_signal_intensity": "observable_v2_state_intensity",
            "gt_predicted_signal_intensity": "gt_signal_intensity",
        }
    )
    out["seed"] = out["seed"].astype(int)
    out["t"] = out["t"].astype(int)
    out["macro_signal"] = out["macro_signal"].astype(str)
    return out.sort_values(["seed", "scenario", "macro_signal", "t"]).reset_index(drop=True)


def _relation_reconstruct_state_timeline(
    task6_state_table: pd.DataFrame,
    relation_field: pd.DataFrame,
) -> pd.DataFrame:
    base = _timeline_from_task6_state_table(task6_state_table)
    if base.empty or relation_field is None or relation_field.empty:
        return pd.DataFrame(columns=REQUIRED_STATE_TIMELINE_COLUMNS)
    records = []
    keys = ["seed", "scenario", "t"]
    pivot = base.pivot_table(index=keys, columns="macro_signal", values="gt_signal_intensity", aggfunc="mean").sort_index()
    observed = base.pivot_table(index=keys, columns="macro_signal", values="observable_v2_state_intensity", aggfunc="mean").sort_index()
    signal_names = sorted(set(base["macro_signal"].astype(str)))
    relation = relation_field.copy()
    relation["source_macro_signal"] = relation["source_macro_signal"].astype(str)
    relation["target_macro_signal"] = relation["target_macro_signal"].astype(str)
    thresholds = {
        c: float(observed[c].dropna().quantile(0.67)) if c in observed.columns and not observed[c].dropna().empty else 0.0
        for c in signal_names
    }
    for target in signal_names:
        incoming = relation[relation["target_macro_signal"] == target]
        for idx in pivot.index.tolist():
            seed, scenario, t = idx
            weighted: list[float] = []
            weights: list[float] = []
            for row in incoming.itertuples(index=False):
                source = str(row.source_macro_signal)
                if source not in pivot.columns:
                    continue
                same_coef = _safe_float(row.same_time_correlation)
                lag_coef = _safe_float(row.lagged_source_to_target_correlation)
                same_value = _safe_float(pivot.loc[idx, source])
                weighted.append(same_coef * same_value)
                weights.append(abs(same_coef))
                previous_key = (seed, scenario, int(t) - 1)
                if previous_key in pivot.index:
                    lag_value = _safe_float(pivot.loc[previous_key, source])
                    weighted.append(lag_coef * lag_value)
                    weights.append(abs(lag_coef))
            direct = _safe_float(pivot.loc[idx, target]) if target in pivot.columns else 0.0
            weighted.append(0.25 * direct)
            weights.append(0.25)
            denom = max(float(np.sum(weights)), 1e-12)
            reconstructed = float(np.sum(weighted) / denom)
            obs = _safe_float(observed.loc[idx, target]) if target in observed.columns else 0.0
            threshold = thresholds.get(target, 0.0)
            records.append(
                {
                    **_boundary_payload(),
                    "seed": int(seed),
                    "scenario": str(scenario),
                    "t": int(t),
                    "macro_signal": target,
                    "observable_v2_state_intensity": obs,
                    "gt_signal_intensity": direct,
                    "relation_field_reproduced_intensity": reconstructed,
                    "reproduction_residual": obs - reconstructed,
                    "observable_state_event": bool(obs >= threshold),
                    "reproduced_state_event": bool(reconstructed >= threshold),
                }
            )
    return pd.DataFrame(records, columns=REQUIRED_STATE_TIMELINE_COLUMNS)


def build_state_reproduction_table(
    state_timeline: pd.DataFrame,
    relation_field: pd.DataFrame,
    cfg: V2StateRelationFieldReproductionConfig | None = None,
) -> pd.DataFrame:
    cfg = cfg or V2StateRelationFieldReproductionConfig()
    if state_timeline is None or state_timeline.empty:
        return pd.DataFrame(columns=REQUIRED_STATE_REPRODUCTION_COLUMNS)
    rows = []
    for signal, sub in state_timeline.groupby("macro_signal", sort=True):
        y = sub["observable_v2_state_intensity"].to_numpy(dtype=float)
        pred = sub["relation_field_reproduced_intensity"].to_numpy(dtype=float)
        rmse = float(sqrt(float(np.mean((pred - y) ** 2)))) if len(y) else 0.0
        baseline = float(np.mean(y)) if len(y) else 0.0
        baseline_rmse = float(sqrt(float(np.mean((baseline - y) ** 2)))) if len(y) else 0.0
        r2 = float(1.0 - (rmse**2 / max(baseline_rmse**2, 1e-12)))
        corr = _safe_corr(y, pred)
        true_event = sub["observable_state_event"].astype(bool).to_numpy()
        pred_event = sub["reproduced_state_event"].astype(bool).to_numpy()
        acc = float((true_event == pred_event).mean()) if len(true_event) else 0.0
        f1 = _f1_score(true_event, pred_event)
        source_count = 0
        if relation_field is not None and not relation_field.empty:
            source_count = int((relation_field["target_macro_signal"].astype(str) == str(signal)).sum())
        rows.append(
            {
                **_boundary_payload(),
                "macro_signal": str(signal),
                "rows": int(len(sub)),
                "relation_source_count": source_count,
                "rmse": rmse,
                "baseline_rmse": baseline_rmse,
                "r2_vs_mean_baseline": r2,
                "correlation": corr,
                "state_event_accuracy": acc,
                "state_event_f1": f1,
                "state_reproduction_status": _state_status(r2, corr, acc, cfg),
            }
        )
    return pd.DataFrame(rows, columns=REQUIRED_STATE_REPRODUCTION_COLUMNS)


def build_transition_reproduction_table(
    state_timeline: pd.DataFrame,
    cfg: V2StateRelationFieldReproductionConfig | None = None,
) -> pd.DataFrame:
    cfg = cfg or V2StateRelationFieldReproductionConfig()
    if state_timeline is None or state_timeline.empty:
        return pd.DataFrame(columns=REQUIRED_TRANSITION_COLUMNS)
    rows = []
    for signal, sub in state_timeline.groupby("macro_signal", sort=True):
        matches: list[bool] = []
        rising_true: list[bool] = []
        rising_pred: list[bool] = []
        falling_true: list[bool] = []
        falling_pred: list[bool] = []
        for (_seed, _scenario), g in sub.groupby(["seed", "scenario"], sort=True):
            g = g.sort_values("t")
            obs = g["observable_v2_state_intensity"].to_numpy(dtype=float)
            pred = g["relation_field_reproduced_intensity"].to_numpy(dtype=float)
            if len(obs) < 2:
                continue
            d_obs = np.diff(obs)
            d_pred = np.diff(pred)
            matches.extend([_sign_match(a, b) for a, b in zip(d_obs, d_pred)])
            obs_std = float(np.std(d_obs)) or 1.0
            pred_std = float(np.std(d_pred)) or 1.0
            rising_true.extend(list(d_obs > (0.25 * obs_std)))
            rising_pred.extend(list(d_pred > (0.25 * pred_std)))
            falling_true.extend(list(d_obs < (-0.25 * obs_std)))
            falling_pred.extend(list(d_pred < (-0.25 * pred_std)))
        direction_rate = float(np.mean(matches)) if matches else 0.0
        rising_acc = float((np.asarray(rising_true, dtype=bool) == np.asarray(rising_pred, dtype=bool)).mean()) if rising_true else 0.0
        falling_acc = float((np.asarray(falling_true, dtype=bool) == np.asarray(falling_pred, dtype=bool)).mean()) if falling_true else 0.0
        status = "v2_state_transition_reproduced" if direction_rate >= cfg.min_direction_match_for_pass else "weak_v2_state_transition_reproduction"
        rows.append(
            {
                **_boundary_payload(),
                "macro_signal": str(signal),
                "transition_rows": int(len(matches)),
                "direction_match_rate": direction_rate,
                "rising_event_accuracy": rising_acc,
                "falling_event_accuracy": falling_acc,
                "transition_reproduction_status": status,
            }
        )
    return pd.DataFrame(rows, columns=REQUIRED_TRANSITION_COLUMNS)


def _observable_lagged_corr(state_timeline: pd.DataFrame, source: str, target: str) -> float:
    vals_source: list[float] = []
    vals_target: list[float] = []
    src = state_timeline[state_timeline["macro_signal"].astype(str) == str(source)]
    tgt = state_timeline[state_timeline["macro_signal"].astype(str) == str(target)]
    if src.empty or tgt.empty:
        return 0.0
    src_p = src.pivot_table(index=["seed", "scenario", "t"], values="observable_v2_state_intensity", aggfunc="mean").sort_index()
    tgt_p = tgt.pivot_table(index=["seed", "scenario", "t"], values="observable_v2_state_intensity", aggfunc="mean").sort_index()
    for idx in src_p.index.tolist():
        seed, scenario, t = idx
        next_idx = (seed, scenario, int(t) + 1)
        if next_idx in tgt_p.index:
            vals_source.append(_safe_float(src_p.loc[idx, "observable_v2_state_intensity"]))
            vals_target.append(_safe_float(tgt_p.loc[next_idx, "observable_v2_state_intensity"]))
    return _safe_corr(np.asarray(vals_source), np.asarray(vals_target))


def build_relation_consistency_table(
    state_timeline: pd.DataFrame,
    relation_field: pd.DataFrame,
    cfg: V2StateRelationFieldReproductionConfig | None = None,
) -> pd.DataFrame:
    cfg = cfg or V2StateRelationFieldReproductionConfig()
    if state_timeline is None or state_timeline.empty or relation_field is None or relation_field.empty:
        return pd.DataFrame(columns=REQUIRED_RELATION_CONSISTENCY_COLUMNS)
    rows = []
    for row in relation_field.itertuples(index=False):
        source = str(row.source_macro_signal)
        target = str(row.target_macro_signal)
        source_sub = state_timeline[state_timeline["macro_signal"].astype(str) == source]
        target_sub = state_timeline[state_timeline["macro_signal"].astype(str) == target]
        if source_sub.empty or target_sub.empty:
            continue
        merged = source_sub[["seed", "scenario", "t", "observable_v2_state_intensity"]].merge(
            target_sub[["seed", "scenario", "t", "observable_v2_state_intensity"]],
            on=["seed", "scenario", "t"],
            suffixes=("_source", "_target"),
        )
        obs_same = _safe_corr(
            merged["observable_v2_state_intensity_source"].to_numpy(dtype=float),
            merged["observable_v2_state_intensity_target"].to_numpy(dtype=float),
        )
        obs_lag = _observable_lagged_corr(state_timeline, source, target)
        field_same = _safe_float(row.same_time_correlation)
        field_lag = _safe_float(row.lagged_source_to_target_correlation)
        same_match = _sign_match(obs_same, field_same)
        lag_match = _sign_match(obs_lag, field_lag)
        strength_gap = abs(max(abs(obs_same), abs(obs_lag)) - max(abs(field_same), abs(field_lag)))
        if same_match and lag_match and strength_gap <= cfg.relation_consistency_gap_threshold:
            status = "relation_field_matches_observable_v2_relation"
        elif same_match or lag_match:
            status = "watch_partial_relation_consistency"
        else:
            status = "weak_relation_consistency"
        rows.append(
            {
                **_boundary_payload(),
                "source_macro_signal": source,
                "target_macro_signal": target,
                "observable_same_time_correlation": obs_same,
                "observable_lagged_correlation": obs_lag,
                "relation_field_same_time_correlation": field_same,
                "relation_field_lagged_correlation": field_lag,
                "same_time_sign_match": bool(same_match),
                "lagged_sign_match": bool(lag_match),
                "relation_strength_gap": float(strength_gap),
                "relation_consistency_status": status,
            }
        )
    return pd.DataFrame(rows, columns=REQUIRED_RELATION_CONSISTENCY_COLUMNS)


def build_v2_state_relation_field_reproduction_summary(
    state_reproduction: pd.DataFrame,
    transition_reproduction: pd.DataFrame,
    relation_consistency: pd.DataFrame,
) -> pd.DataFrame:
    state_count = int(len(state_reproduction)) if state_reproduction is not None else 0
    reproduced = 0
    if state_reproduction is not None and not state_reproduction.empty:
        reproduced = int(state_reproduction["state_reproduction_status"].astype(str).str.contains("reproduced|partial").sum())
    mean_r2 = _safe_mean(state_reproduction["r2_vs_mean_baseline"], default=0.0) if state_reproduction is not None and not state_reproduction.empty else 0.0
    mean_corr = _safe_mean(state_reproduction["correlation"], default=0.0) if state_reproduction is not None and not state_reproduction.empty else 0.0
    mean_acc = _safe_mean(state_reproduction["state_event_accuracy"], default=0.0) if state_reproduction is not None and not state_reproduction.empty else 0.0
    mean_dir = _safe_mean(transition_reproduction["direction_match_rate"], default=0.0) if transition_reproduction is not None and not transition_reproduction.empty else 0.0
    rel_count = int(len(relation_consistency)) if relation_consistency is not None else 0
    rel_pass = 0
    if relation_consistency is not None and not relation_consistency.empty:
        rel_pass = int(relation_consistency["relation_consistency_status"].astype(str).str.contains("matches|partial").sum())
    weak_names = []
    if state_reproduction is not None and not state_reproduction.empty:
        weak_names = sorted(state_reproduction.loc[
            state_reproduction["state_reproduction_status"].astype(str) == "weak_v2_state_reproduction",
            "macro_signal",
        ].astype(str).tolist())
    if state_count >= 4 and reproduced >= max(4, int(0.70 * state_count)) and mean_acc >= 0.55 and rel_pass >= max(1, int(0.50 * rel_count)):
        decision = "relation_field_reproduces_observable_v2_game_structure"
    elif reproduced >= max(3, int(0.50 * state_count)):
        decision = "relation_field_partially_reproduces_observable_v2_game_structure"
    else:
        decision = "relation_field_does_not_yet_reproduce_observable_v2_game_structure"
    row = {
        **_boundary_payload(),
        "state_count": state_count,
        "reproduced_state_count": reproduced,
        "mean_state_r2": mean_r2,
        "mean_state_correlation": mean_corr,
        "mean_state_event_accuracy": mean_acc,
        "mean_direction_match_rate": mean_dir,
        "relation_consistency_count": rel_count,
        "relation_consistency_pass_count": rel_pass,
        "weak_state_names": ";".join(weak_names),
        "v2_state_reproduction_decision": decision,
        "next_task": "Task 2-8j-7: O_t observation map over verified fixed-7-axis G_t relation field",
    }
    return pd.DataFrame([row], columns=REQUIRED_SUMMARY_COLUMNS)


def validate_v2_state_relation_field_reproduction_tables(
    state_reproduction: pd.DataFrame,
    state_timeline: pd.DataFrame,
    transition_reproduction: pd.DataFrame,
    relation_consistency: pd.DataFrame,
    final_summary: pd.DataFrame,
) -> list[str]:
    errors: list[str] = []
    tables = {
        "state_reproduction": (state_reproduction, REQUIRED_STATE_REPRODUCTION_COLUMNS),
        "state_timeline": (state_timeline, REQUIRED_STATE_TIMELINE_COLUMNS),
        "transition_reproduction": (transition_reproduction, REQUIRED_TRANSITION_COLUMNS),
        "relation_consistency": (relation_consistency, REQUIRED_RELATION_CONSISTENCY_COLUMNS),
        "final_summary": (final_summary, REQUIRED_SUMMARY_COLUMNS),
    }
    forbidden_true = [
        "runtime_policy_input",
        "fullspec_runtime_connected",
        "upper_pressure_connected",
        "action_frame_created",
        "actionmodule_called",
        "canonical_write_performed",
        "gk_writeback_performed",
        "ot_writeback_performed",
        "effective_dimension_refit_performed",
        "axis_mutation_performed",
        "residual_auxiliary_injected_into_gt_main",
        "dynamics_axis_extracted_for_action",
        "action_weight_converted",
        "hidden_truth_input",
        "future_information_used",
    ]
    for name, (table, required) in tables.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_6b_empty_table:{name}")
            continue
        missing = [c for c in required if c not in table.columns]
        if missing:
            errors.append(f"task2_8j_6b_missing_columns:{name}:" + ",".join(missing))
            continue
        for col in ["validation_only", "incomplete_observation_assumption", "observable_v2_state_only"]:
            if not bool(table[col].astype(bool).all()):
                errors.append(f"task2_8j_6b_required_true_not_all_true:{name}:{col}")
        if set(table["gt_main_map_name"].astype(str)) != {"static_pca_7"}:
            errors.append(f"task2_8j_6b_wrong_gt_main_map_name:{name}")
        if set(table["gt_main_component_count"].astype(int)) != {7}:
            errors.append(f"task2_8j_6b_wrong_gt_main_component_count:{name}")
        for col in forbidden_true:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_6b_forbidden_true:{name}:{col}")
    if state_reproduction is not None and not state_reproduction.empty:
        core = {"relation_lock", "coordination_lag", "information_degradation", "resource_pressure"}
        got = set(state_reproduction["macro_signal"].astype(str))
        missing_core = sorted(core - got)
        if missing_core:
            errors.append("task2_8j_6b_missing_core_v2_states:" + ",".join(missing_core))
        if not bool(state_reproduction["state_event_accuracy"].astype(float).between(0.0, 1.0).all()):
            errors.append("task2_8j_6b_state_event_accuracy_out_of_range")
    if transition_reproduction is not None and not transition_reproduction.empty:
        if not bool(transition_reproduction["direction_match_rate"].astype(float).between(0.0, 1.0).all()):
            errors.append("task2_8j_6b_direction_match_out_of_range")
    return errors


def build_and_validate_v2_state_relation_field_reproduction(
    feature_cfg: CandidateFeatureLogConfig | None = None,
    task6_cfg: MacroGameRelationFieldConfig | None = None,
    cfg: V2StateRelationFieldReproductionConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    cfg = cfg or V2StateRelationFieldReproductionConfig()
    feature_cfg = feature_cfg or CandidateFeatureLogConfig(steps=24, seeds=(501, 502, 503), window_sizes=(1, 6, 12))
    _signal_table, task6_state_table, relation_field, _task6_summary, task6_errors, _task6_json = build_and_validate_macro_game_relation_field(
        feature_cfg,
        task6_cfg or MacroGameRelationFieldConfig(),
    )
    state_timeline = _relation_reconstruct_state_timeline(task6_state_table, relation_field)
    state_reproduction = build_state_reproduction_table(state_timeline, relation_field, cfg)
    transition_reproduction = build_transition_reproduction_table(state_timeline, cfg)
    relation_consistency = build_relation_consistency_table(state_timeline, relation_field, cfg)
    final_summary = build_v2_state_relation_field_reproduction_summary(
        state_reproduction,
        transition_reproduction,
        relation_consistency,
    )
    errors = [f"task2_8j_6b_upstream_task6_error:{e}" for e in task6_errors]
    errors.extend(
        validate_v2_state_relation_field_reproduction_tables(
            state_reproduction,
            state_timeline,
            transition_reproduction,
            relation_consistency,
            final_summary,
        )
    )
    summary = {
        "gt_main_map_name": "static_pca_7",
        "gt_main_component_count": 7,
        "state_count": int(final_summary["state_count"].iloc[0]) if not final_summary.empty else 0,
        "reproduced_state_count": int(final_summary["reproduced_state_count"].iloc[0]) if not final_summary.empty else 0,
        "mean_state_r2": _safe_float(final_summary["mean_state_r2"].iloc[0]) if not final_summary.empty else 0.0,
        "mean_state_correlation": _safe_float(final_summary["mean_state_correlation"].iloc[0]) if not final_summary.empty else 0.0,
        "mean_state_event_accuracy": _safe_float(final_summary["mean_state_event_accuracy"].iloc[0]) if not final_summary.empty else 0.0,
        "mean_direction_match_rate": _safe_float(final_summary["mean_direction_match_rate"].iloc[0]) if not final_summary.empty else 0.0,
        "relation_consistency_count": int(final_summary["relation_consistency_count"].iloc[0]) if not final_summary.empty else 0,
        "relation_consistency_pass_count": int(final_summary["relation_consistency_pass_count"].iloc[0]) if not final_summary.empty else 0,
        "weak_state_names": str(final_summary["weak_state_names"].iloc[0]) if not final_summary.empty else "",
        "v2_state_reproduction_decision": str(final_summary["v2_state_reproduction_decision"].iloc[0]) if not final_summary.empty else "empty",
        "validation_errors": errors,
    }
    return state_reproduction, state_timeline, transition_reproduction, relation_consistency, final_summary, errors, summary
