"""Task 2-8j-6c: v2 structure-change / relation-field tracking validation RC1.

Purpose:
    Validate whether the fixed-7-axis G_t relation field can follow observable
    v2 game-structure changes across phase-shifted pseudo-reality settings.

Position:
    Task 2-8j-6 built a macro-game relation field from fixed static_pca_7 G_t.
    Task 2-8j-6b checked whether that field reproduces observable v2 states.
    This task checks whether the relation field changes when the v2 game
    structure changes, without mutating the G_t axes.

Boundary:
    - validation only
    - fixed static_pca_7 main map
    - relation field may be updated by window / phase
    - no effective-dimension re-fitting or axis mutation
    - no residual auxiliary injection into G_t main
    - no action conversion, upper-pressure connection, runtime call, or writeback
    - no hidden-truth / future-information input
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from math import sqrt

import numpy as np
import pandas as pd

from .pressure_action_task2_8j_1_candidate_feature_log import (
    CandidateFeatureLogConfig,
    DEFAULT_V2_WORLD_CONFIG,
)
from .pressure_action_task2_8j_6_macro_game_relation_field_validation import (
    MacroGameRelationFieldConfig,
    build_and_validate_macro_game_relation_field,
)
from .pressure_action_task2_8j_6b_v2_state_relation_field_reproduction import (
    V2StateRelationFieldReproductionConfig,
    _relation_reconstruct_state_timeline,
    build_state_reproduction_table,
)

TASK2_8J_6C_VERSION = "v2_structure_change_relation_field_tracking_rc1"
TASK2_8J_6C_CONTRACT = (
    "Task2_8j_6c_v2_structure_change_relation_field_tracking__"
    "fixed_static_pca_7__phase_relation_field_update_only__"
    "no_axis_mutation_no_hidden_truth_no_runtime_write"
)

BOUNDARY = {
    "task2_8j_6c_version": TASK2_8J_6C_VERSION,
    "task2_8j_6c_contract": TASK2_8J_6C_CONTRACT,
    "validation_only": True,
    "incomplete_observation_assumption": True,
    "gt_main_map_name": "static_pca_7",
    "gt_main_component_count": 7,
    "observable_v2_state_only": True,
    "relation_field_update_allowed": True,
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
    "action_weight_converted": False,
    "hidden_truth_input": False,
    "future_information_used": False,
}

FORBIDDEN_TRUE = [
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
    "action_weight_converted",
    "hidden_truth_input",
    "future_information_used",
]

REQUIRED_PHASE_COLUMNS = list(BOUNDARY) + [
    "phase_name",
    "phase_order",
    "scenario",
    "state_count",
    "reproduced_state_count",
    "mean_state_r2",
    "mean_state_correlation",
    "mean_state_event_accuracy",
    "weak_state_names",
]

REQUIRED_EDGE_COLUMNS = list(BOUNDARY) + [
    "source_phase",
    "target_phase",
    "source_macro_signal",
    "target_macro_signal",
    "source_relation_strength",
    "target_relation_strength",
    "relation_strength_delta",
    "source_same_time_correlation",
    "target_same_time_correlation",
    "same_time_sign_changed",
    "source_lagged_correlation",
    "target_lagged_correlation",
    "lagged_sign_changed",
    "structure_change_detected",
]

REQUIRED_STALE_COLUMNS = list(BOUNDARY) + [
    "source_relation_phase",
    "target_state_phase",
    "updated_relation_phase",
    "stale_mean_state_event_accuracy",
    "updated_mean_state_event_accuracy",
    "updated_minus_stale_event_accuracy",
    "stale_mean_state_correlation",
    "updated_mean_state_correlation",
    "updated_minus_stale_correlation",
    "tracking_recovery_status",
]

REQUIRED_SUMMARY_COLUMNS = list(BOUNDARY) + [
    "phase_count",
    "edge_comparison_count",
    "changed_edge_count",
    "sign_change_count",
    "stale_updated_comparison_count",
    "updated_recovery_count",
    "mean_phase_state_event_accuracy",
    "min_phase_state_event_accuracy",
    "v2_structure_tracking_decision",
    "next_task",
]


@dataclass(frozen=True)
class V2StructureChangeTrackingConfig:
    seeds: tuple[int, ...] = (501, 502, 503)
    steps: int = 24
    window_sizes: tuple[int, ...] = (1, 6, 12)
    relation_strength_delta_threshold: float = 0.08
    recovery_tolerance: float = -0.02
    min_phase_event_accuracy: float = 0.55


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return float(default)
    if not np.isfinite(out):
        return float(default)
    return float(out)


def _safe_mean(values, default: float = 0.0) -> float:
    arr = pd.to_numeric(pd.Series(values), errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if arr.empty:
        return float(default)
    return float(arr.mean())


def _sign(value: float, eps: float = 1e-9) -> int:
    if value > eps:
        return 1
    if value < -eps:
        return -1
    return 0


def _world_config_for_phase(phase_name: str) -> dict:
    cfg = deepcopy(DEFAULT_V2_WORLD_CONFIG)
    if phase_name == "baseline":
        return cfg
    if phase_name == "defensive_hoarding_shift":
        cfg["active_dynamics"]["defensive_hoarding"]["intensity"] = 0.11
        cfg["active_dynamics"]["trust_decay"]["intensity"] = 0.07
        cfg["resource_settings"]["resource_depletion_rate"] = 0.052
        cfg["side_effect_settings"]["exploration_exploitation_risk"] = 0.34
        return cfg
    if phase_name == "information_damage_shift":
        cfg["active_dynamics"]["hidden_damage_growth"]["intensity"] = 0.11
        cfg["information_settings"]["information_delay_steps"] = 4
        cfg["information_settings"]["information_distortion_scale"] = 0.12
        cfg["information_settings"]["misread_probability"] = 0.18
        cfg["information_settings"]["hidden_state_visibility"] = 0.14
        cfg["active_dynamics"]["no_op_decay"]["intensity"] = 0.06
        return cfg
    raise ValueError(f"unknown phase: {phase_name}")


def _phase_feature_cfg(phase_name: str, phase_order: int, cfg: V2StructureChangeTrackingConfig) -> CandidateFeatureLogConfig:
    return CandidateFeatureLogConfig(
        steps=cfg.steps,
        seeds=cfg.seeds,
        scenario=f"v2_structure_change_{phase_order}_{phase_name}",
        window_sizes=cfg.window_sizes,
        world_config=_world_config_for_phase(phase_name),
    )


def _phase_reproduction_from_task6_state(state_table: pd.DataFrame, relation_field: pd.DataFrame) -> pd.DataFrame:
    timeline = _relation_reconstruct_state_timeline(state_table, relation_field)
    return build_state_reproduction_table(timeline, relation_field, V2StateRelationFieldReproductionConfig())


def _phase_metrics(phase_name: str, phase_order: int, state_reproduction: pd.DataFrame) -> dict:
    statuses = state_reproduction["state_reproduction_status"].astype(str) if not state_reproduction.empty else pd.Series(dtype=str)
    reproduced = int(statuses.str.contains("reproduced|partial").sum()) if not statuses.empty else 0
    weak = sorted(state_reproduction.loc[statuses == "weak_v2_state_reproduction", "macro_signal"].astype(str).tolist()) if not state_reproduction.empty else []
    return {
        **BOUNDARY,
        "phase_name": phase_name,
        "phase_order": int(phase_order),
        "scenario": f"v2_structure_change_{phase_order}_{phase_name}",
        "state_count": int(len(state_reproduction)),
        "reproduced_state_count": reproduced,
        "mean_state_r2": _safe_mean(state_reproduction["r2_vs_mean_baseline"]) if not state_reproduction.empty else 0.0,
        "mean_state_correlation": _safe_mean(state_reproduction["correlation"]) if not state_reproduction.empty else 0.0,
        "mean_state_event_accuracy": _safe_mean(state_reproduction["state_event_accuracy"]) if not state_reproduction.empty else 0.0,
        "weak_state_names": ";".join(weak),
    }


def _edge_keyed(field: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "source_macro_signal",
        "target_macro_signal",
        "relation_strength",
        "same_time_correlation",
        "lagged_source_to_target_correlation",
    ]
    out = field[cols].copy()
    out["source_macro_signal"] = out["source_macro_signal"].astype(str)
    out["target_macro_signal"] = out["target_macro_signal"].astype(str)
    return out


def build_phase_edge_change_table(phase_outputs: dict[str, dict], cfg: V2StructureChangeTrackingConfig) -> pd.DataFrame:
    rows: list[dict] = []
    names = list(phase_outputs)
    for a, b in zip(names[:-1], names[1:]):
        left = _edge_keyed(phase_outputs[a]["relation_field"])
        right = _edge_keyed(phase_outputs[b]["relation_field"])
        merged = left.merge(right, on=["source_macro_signal", "target_macro_signal"], suffixes=("_source", "_target"))
        for row in merged.itertuples(index=False):
            source_strength = _safe_float(row.relation_strength_source)
            target_strength = _safe_float(row.relation_strength_target)
            same_source = _safe_float(row.same_time_correlation_source)
            same_target = _safe_float(row.same_time_correlation_target)
            lag_source = _safe_float(row.lagged_source_to_target_correlation_source)
            lag_target = _safe_float(row.lagged_source_to_target_correlation_target)
            delta = target_strength - source_strength
            same_changed = _sign(same_source) != _sign(same_target)
            lag_changed = _sign(lag_source) != _sign(lag_target)
            changed = abs(delta) >= cfg.relation_strength_delta_threshold or same_changed or lag_changed
            rows.append({
                **BOUNDARY,
                "source_phase": a,
                "target_phase": b,
                "source_macro_signal": str(row.source_macro_signal),
                "target_macro_signal": str(row.target_macro_signal),
                "source_relation_strength": source_strength,
                "target_relation_strength": target_strength,
                "relation_strength_delta": float(delta),
                "source_same_time_correlation": same_source,
                "target_same_time_correlation": same_target,
                "same_time_sign_changed": bool(same_changed),
                "source_lagged_correlation": lag_source,
                "target_lagged_correlation": lag_target,
                "lagged_sign_changed": bool(lag_changed),
                "structure_change_detected": bool(changed),
            })
    return pd.DataFrame(rows, columns=REQUIRED_EDGE_COLUMNS)


def _mean_reproduction_scores(state_reproduction: pd.DataFrame) -> tuple[float, float]:
    if state_reproduction is None or state_reproduction.empty:
        return 0.0, 0.0
    return _safe_mean(state_reproduction["state_event_accuracy"]), _safe_mean(state_reproduction["correlation"])


def build_stale_vs_updated_table(phase_outputs: dict[str, dict], cfg: V2StructureChangeTrackingConfig) -> pd.DataFrame:
    rows: list[dict] = []
    names = list(phase_outputs)
    baseline_relation = phase_outputs[names[0]]["relation_field"]
    for target_name in names[1:]:
        target_state = phase_outputs[target_name]["task6_state_table"]
        updated_relation = phase_outputs[target_name]["relation_field"]
        stale_timeline = _relation_reconstruct_state_timeline(target_state, baseline_relation)
        updated_timeline = _relation_reconstruct_state_timeline(target_state, updated_relation)
        stale_repro = build_state_reproduction_table(stale_timeline, baseline_relation, V2StateRelationFieldReproductionConfig())
        updated_repro = build_state_reproduction_table(updated_timeline, updated_relation, V2StateRelationFieldReproductionConfig())
        stale_acc, stale_corr = _mean_reproduction_scores(stale_repro)
        updated_acc, updated_corr = _mean_reproduction_scores(updated_repro)
        acc_delta = updated_acc - stale_acc
        corr_delta = updated_corr - stale_corr
        status = "updated_relation_field_recovers_or_preserves_reproduction" if acc_delta >= cfg.recovery_tolerance else "watch_updated_relation_field_not_yet_recovering"
        rows.append({
            **BOUNDARY,
            "source_relation_phase": names[0],
            "target_state_phase": target_name,
            "updated_relation_phase": target_name,
            "stale_mean_state_event_accuracy": stale_acc,
            "updated_mean_state_event_accuracy": updated_acc,
            "updated_minus_stale_event_accuracy": acc_delta,
            "stale_mean_state_correlation": stale_corr,
            "updated_mean_state_correlation": updated_corr,
            "updated_minus_stale_correlation": corr_delta,
            "tracking_recovery_status": status,
        })
    return pd.DataFrame(rows, columns=REQUIRED_STALE_COLUMNS)


def build_final_summary(phase_table: pd.DataFrame, edge_change: pd.DataFrame, stale_updated: pd.DataFrame, cfg: V2StructureChangeTrackingConfig) -> pd.DataFrame:
    phase_count = int(len(phase_table)) if phase_table is not None else 0
    edge_count = int(len(edge_change)) if edge_change is not None else 0
    changed_count = int(edge_change["structure_change_detected"].astype(bool).sum()) if edge_count else 0
    sign_count = 0
    if edge_count:
        sign_count = int((edge_change["same_time_sign_changed"].astype(bool) | edge_change["lagged_sign_changed"].astype(bool)).sum())
    stale_count = int(len(stale_updated)) if stale_updated is not None else 0
    recovery_count = int(stale_updated["tracking_recovery_status"].astype(str).str.contains("recovers|preserves").sum()) if stale_count else 0
    mean_acc = _safe_mean(phase_table["mean_state_event_accuracy"]) if phase_count else 0.0
    min_acc = float(pd.to_numeric(phase_table["mean_state_event_accuracy"], errors="coerce").min()) if phase_count else 0.0
    if phase_count >= 3 and changed_count > 0 and min_acc >= cfg.min_phase_event_accuracy and recovery_count >= max(1, stale_count):
        decision = "relation_field_tracks_v2_structure_change_within_fixed_7axis_gt"
    elif phase_count >= 3 and changed_count > 0:
        decision = "relation_field_detects_v2_structure_change_but_tracking_needs_watch"
    else:
        decision = "relation_field_tracking_not_confirmed_for_v2_structure_change"
    return pd.DataFrame([{
        **BOUNDARY,
        "phase_count": phase_count,
        "edge_comparison_count": edge_count,
        "changed_edge_count": changed_count,
        "sign_change_count": sign_count,
        "stale_updated_comparison_count": stale_count,
        "updated_recovery_count": recovery_count,
        "mean_phase_state_event_accuracy": mean_acc,
        "min_phase_state_event_accuracy": min_acc,
        "v2_structure_tracking_decision": decision,
        "next_task": "Task 2-8j-7: O_t observation map over tracked fixed-7-axis G_t relation field",
    }], columns=REQUIRED_SUMMARY_COLUMNS)


def validate_v2_structure_change_tracking_tables(phase_table: pd.DataFrame, edge_change: pd.DataFrame, stale_updated: pd.DataFrame, final_summary: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    required = {
        "phase_table": (phase_table, REQUIRED_PHASE_COLUMNS),
        "edge_change": (edge_change, REQUIRED_EDGE_COLUMNS),
        "stale_updated": (stale_updated, REQUIRED_STALE_COLUMNS),
        "final_summary": (final_summary, REQUIRED_SUMMARY_COLUMNS),
    }
    for name, (table, cols) in required.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_6c_empty_table:{name}")
            continue
        missing = [c for c in cols if c not in table.columns]
        if missing:
            errors.append(f"task2_8j_6c_missing_columns:{name}:" + ",".join(missing))
            continue
        for col in ["validation_only", "incomplete_observation_assumption", "observable_v2_state_only", "relation_field_update_allowed"]:
            if not bool(table[col].astype(bool).all()):
                errors.append(f"task2_8j_6c_required_true_not_all_true:{name}:{col}")
        if set(table["gt_main_map_name"].astype(str)) != {"static_pca_7"}:
            errors.append(f"task2_8j_6c_wrong_gt_main_map_name:{name}")
        if set(table["gt_main_component_count"].astype(int)) != {7}:
            errors.append(f"task2_8j_6c_wrong_component_count:{name}")
        for col in FORBIDDEN_TRUE:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_6c_forbidden_true:{name}:{col}")
    if final_summary is not None and not final_summary.empty:
        if int(final_summary["phase_count"].iloc[0]) < 3:
            errors.append("task2_8j_6c_phase_count_too_low")
        if int(final_summary["edge_comparison_count"].iloc[0]) <= 0:
            errors.append("task2_8j_6c_no_edge_comparisons")
    return errors


def build_and_validate_v2_structure_change_relation_field_tracking(
    cfg: V2StructureChangeTrackingConfig | None = None,
    task6_cfg: MacroGameRelationFieldConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    cfg = cfg or V2StructureChangeTrackingConfig()
    task6_cfg = task6_cfg or MacroGameRelationFieldConfig()
    phases = ["baseline", "defensive_hoarding_shift", "information_damage_shift"]
    phase_outputs: dict[str, dict] = {}
    phase_rows: list[dict] = []
    upstream_errors: list[str] = []
    for order, phase in enumerate(phases):
        feature_cfg = _phase_feature_cfg(phase, order, cfg)
        _signal_table, task6_state_table, relation_field, _summary, errors, _summary_json = build_and_validate_macro_game_relation_field(feature_cfg, task6_cfg)
        upstream_errors.extend([f"{phase}:{e}" for e in errors])
        state_reproduction = _phase_reproduction_from_task6_state(task6_state_table, relation_field)
        phase_outputs[phase] = {
            "task6_state_table": task6_state_table,
            "relation_field": relation_field,
            "state_reproduction": state_reproduction,
        }
        phase_rows.append(_phase_metrics(phase, order, state_reproduction))
    phase_table = pd.DataFrame(phase_rows, columns=REQUIRED_PHASE_COLUMNS)
    edge_change = build_phase_edge_change_table(phase_outputs, cfg)
    stale_updated = build_stale_vs_updated_table(phase_outputs, cfg)
    final_summary = build_final_summary(phase_table, edge_change, stale_updated, cfg)
    errors = [f"task2_8j_6c_upstream_task6_error:{e}" for e in upstream_errors]
    errors.extend(validate_v2_structure_change_tracking_tables(phase_table, edge_change, stale_updated, final_summary))
    summary = {
        "gt_main_map_name": "static_pca_7",
        "gt_main_component_count": 7,
        "phase_count": int(final_summary["phase_count"].iloc[0]),
        "edge_comparison_count": int(final_summary["edge_comparison_count"].iloc[0]),
        "changed_edge_count": int(final_summary["changed_edge_count"].iloc[0]),
        "sign_change_count": int(final_summary["sign_change_count"].iloc[0]),
        "stale_updated_comparison_count": int(final_summary["stale_updated_comparison_count"].iloc[0]),
        "updated_recovery_count": int(final_summary["updated_recovery_count"].iloc[0]),
        "mean_phase_state_event_accuracy": _safe_float(final_summary["mean_phase_state_event_accuracy"].iloc[0]),
        "min_phase_state_event_accuracy": _safe_float(final_summary["min_phase_state_event_accuracy"].iloc[0]),
        "v2_structure_tracking_decision": str(final_summary["v2_structure_tracking_decision"].iloc[0]),
        "validation_errors": errors,
    }
    return phase_table, edge_change, stale_updated, final_summary, errors, summary
