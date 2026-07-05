"""Task 2-8j-1: candidate feature-log generation for effective-dimension validation RC1.

Purpose:
    Generate a validation-only candidate feature log for the next effective-
    dimension tests.  This task does not extract effective dimensions yet; it
    only prepares coarse-grained observed features that can later be fed into
    temporal PCA / Sparse PCA validation.

Boundary:
    - validation only
    - synthetic v2 trace source only
    - no effective-dimension extraction yet
    - no dynamics-axis extraction yet
    - no upper-pressure connection
    - no ActionFrame / ActionModule / FullSpec runtime / canonical write
    - no v2_hidden_trace as a G_t input feature
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import numpy as np
import pandas as pd

from DEPT2_ActionModule_ActuationPrimitives_RC1.pseudo_reality.asymmetric_game_v2 import (
    AsymmetricGamePseudoRealitySystem,
)
from DEPT2_ActionModule_ActuationPrimitives_RC1.pseudo_reality.system import STATE_FEATURES


TASK2_8J_1_VERSION = "effective_dimension_candidate_feature_log_rc1"
TASK2_8J_1_CONTRACT = (
    "Task2_8j_1_candidate_feature_log__Gt_effective_dimension_validation_only__"
    "no_hidden_trace_input__no_actionframe_no_runtime_write"
)

FORBIDDEN_INPUT_TRACES = {"v2_hidden_trace"}
ALLOWED_INPUT_TRACES = {
    "entity_trace",
    "relation_trace",
    "v2_game_trace",
    "v2_resource_trace",
    "v2_information_trace",
    "v2_action_effect_trace",
}

GAME_TENDENCY_COLUMNS = (
    "cooperate_tendency",
    "defend_tendency",
    "explore_tendency",
    "extract_tendency",
    "connect_tendency",
    "amplify_tendency",
    "hoard_tendency",
    "share_tendency",
    "local_payoff",
    "short_term_payoff",
    "long_term_health_proxy",
)

RESOURCE_COLUMNS = (
    "shared_resource",
    "commons_health",
    "resource_pressure",
    "resource_inequality",
    "private_resource_mean",
    "private_resource_std",
    "private_resource_min",
    "private_resource_max",
)

INFORMATION_COLUMNS = (
    "information_delay_mean",
    "information_distortion_mean",
    "hidden_state_visibility",
    "private_information_rate",
    "misread_probability_mean",
    "information_quality_mean",
    "information_flow_mean",
    "coordination_lag_mean",
    "cause_side_information_asymmetry",
    "cause_side_action_cost",
    "observed_vs_hidden_gap_proxy",
)

ACTION_EFFECT_COLUMNS = (
    "action_intensity",
    "target_count",
    "direct_effect_score",
    "side_effect_score",
    "net_public_effect_score",
    "net_hidden_effect_score",
    "exploitation_risk_delta",
    "trust_delta",
    "fatigue_delta",
    "hidden_damage_delta",
    "resource_inequality_delta",
    "reversibility_delta",
    "exploration_delta",
    "action_cost_effect",
)

REQUIRED_TASK2_8J_1_COLUMNS = [
    "task2_8j_1_version",
    "task2_8j_1_contract",
    "validation_only",
    "runtime_policy_input",
    "fullspec_runtime_connected",
    "upper_pressure_connected",
    "action_frame_created",
    "actionmodule_called",
    "canonical_write_performed",
    "gk_writeback_performed",
    "ot_writeback_performed",
    "effective_dimension_extracted",
    "dynamics_axis_extracted",
    "candidate_feature_log",
    "synthetic_v2_trace_source",
    "seed",
    "scenario",
    "t",
    "window_id",
    "window_size",
    "scope",
    "entity_id",
    "source_trace",
    "feature_group",
    "feature_name",
    "stat_name",
    "feature_value",
    "feature_value_valid",
    "temporal_feature",
    "input_role",
    "observability_class",
    "allowed_for_gt",
    "hidden_truth_input",
    "raw_trace_passthrough",
    "future_information_used",
    "source_contract",
]


DEFAULT_V2_WORLD_CONFIG = {
    "entity_mix": {
        "stabilizer": 0.30,
        "explorer": 0.20,
        "extractor": 0.20,
        "connector": 0.20,
        "amplifier": 0.10,
    },
    "resource_settings": {
        "initial_shared_resource": 0.72,
        "resource_recovery_rate": 0.018,
        "resource_depletion_rate": 0.035,
    },
    "information_settings": {
        "information_delay_steps": 2,
        "information_distortion_scale": 0.06,
        "hidden_state_visibility": 0.22,
        "private_information_rate": 0.30,
        "misread_probability": 0.10,
    },
    "side_effect_settings": {
        "exploration_exploitation_risk": 0.24,
        "stabilization_lockin_side_effect": 0.22,
    },
    "active_dynamics": {
        "trust_decay": {"enabled": True, "intensity": 0.04},
        "defensive_hoarding": {"enabled": True, "intensity": 0.05},
        "hidden_damage_growth": {"enabled": True, "intensity": 0.04},
        "no_op_decay": {"enabled": True, "intensity": 0.03},
    },
}


@dataclass(frozen=True)
class CandidateFeatureLogConfig:
    steps: int = 18
    seeds: tuple[int, ...] = (501, 502)
    scenario: str = "v2_shrinking_equilibrium"
    n_entities: int = 24
    action_coupling: float = 0.045
    noise_scale: float = 0.018
    drift_scale: float = 0.006
    world_profile: str = "pseudo_reality_v2_shrinking_equilibrium"
    world_config: dict = field(default_factory=lambda: dict(DEFAULT_V2_WORLD_CONFIG))
    window_sizes: tuple[int, ...] = (1, 6, 12)


@dataclass(frozen=True)
class CandidateFeatureSchemaRow:
    column: str
    role: str
    required: bool = True


def _finite_float(value: object, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return float(default)
    if not np.isfinite(out):
        return float(default)
    return float(out)


def _series(df: pd.DataFrame, column: str) -> pd.Series:
    if df is None or df.empty or column not in df.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(df[column], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna().astype(float)


def _gini(values: Iterable[float]) -> float:
    arr = np.asarray(list(values), dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) == 0:
        return 0.0
    arr = np.clip(arr, 0.0, None)
    if float(arr.sum()) <= 1e-12:
        return 0.0
    arr = np.sort(arr)
    n = len(arr)
    index = np.arange(1, n + 1, dtype=float)
    return float((np.sum((2.0 * index - n - 1.0) * arr)) / (n * np.sum(arr)))


def _distribution_stats(values: pd.Series) -> dict[str, float]:
    s = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna().astype(float)
    if s.empty:
        return {}
    return {
        "count": float(len(s)),
        "mean": float(s.mean()),
        "std": float(s.std(ddof=0)),
        "q10": float(s.quantile(0.10)),
        "q50": float(s.quantile(0.50)),
        "q90": float(s.quantile(0.90)),
        "min": float(s.min()),
        "max": float(s.max()),
        "range": float(s.max() - s.min()),
        "tail_high_075": float((s >= 0.75).mean()),
        "tail_low_025": float((s <= 0.25).mean()),
        "gini": _gini(s.to_numpy(dtype=float)),
    }


def _base_row(
    *,
    seed: int,
    scenario: str,
    t: int,
    source_trace: str,
    feature_group: str,
    feature_name: str,
    stat_name: str,
    feature_value: float,
    window_id: str = "current",
    window_size: int = 1,
    scope: str = "global",
    entity_id: str = "__global__",
    temporal_feature: bool = False,
    input_role: str = "candidate_feature",
    observability_class: str = "observed_or_derived",
) -> dict:
    value = _finite_float(feature_value, default=0.0)
    return {
        "task2_8j_1_version": TASK2_8J_1_VERSION,
        "task2_8j_1_contract": TASK2_8J_1_CONTRACT,
        "validation_only": True,
        "runtime_policy_input": False,
        "fullspec_runtime_connected": False,
        "upper_pressure_connected": False,
        "action_frame_created": False,
        "actionmodule_called": False,
        "canonical_write_performed": False,
        "gk_writeback_performed": False,
        "ot_writeback_performed": False,
        "effective_dimension_extracted": False,
        "dynamics_axis_extracted": False,
        "candidate_feature_log": True,
        "synthetic_v2_trace_source": True,
        "seed": int(seed),
        "scenario": str(scenario),
        "t": int(t),
        "window_id": str(window_id),
        "window_size": int(window_size),
        "scope": str(scope),
        "entity_id": str(entity_id),
        "source_trace": str(source_trace),
        "feature_group": str(feature_group),
        "feature_name": str(feature_name),
        "stat_name": str(stat_name),
        "feature_value": value,
        "feature_value_valid": bool(np.isfinite(value)),
        "temporal_feature": bool(temporal_feature),
        "input_role": str(input_role),
        "observability_class": str(observability_class),
        "allowed_for_gt": str(source_trace) in ALLOWED_INPUT_TRACES,
        "hidden_truth_input": str(source_trace) in FORBIDDEN_INPUT_TRACES,
        "raw_trace_passthrough": False,
        "future_information_used": False,
        "source_contract": "coarse_candidate_feature_from_allowed_observed_trace__not_raw_trace_passthrough",
    }


def _append_stat_rows(
    rows: list[dict],
    *,
    seed: int,
    scenario: str,
    t: int,
    source_trace: str,
    feature_group: str,
    feature_name: str,
    values: pd.Series,
    observability_class: str = "observed_or_derived",
) -> None:
    for stat_name, value in _distribution_stats(values).items():
        rows.append(
            _base_row(
                seed=seed,
                scenario=scenario,
                t=t,
                source_trace=source_trace,
                feature_group=feature_group,
                feature_name=feature_name,
                stat_name=stat_name,
                feature_value=value,
                observability_class=observability_class,
            )
        )


def _trace_time(trace: dict[str, pd.DataFrame]) -> tuple[int, int, str]:
    e = trace["entity_trace"]
    return int(e["seed"].iloc[0]), int(e["t"].iloc[0]), str(e["scenario"].iloc[0])


def build_v2_trace_history(cfg: CandidateFeatureLogConfig | None = None) -> list[dict[str, pd.DataFrame]]:
    """Build validation-only v2 trace history without ActionFrame input."""
    cfg = cfg or CandidateFeatureLogConfig()
    traces: list[dict[str, pd.DataFrame]] = []
    for seed in cfg.seeds:
        world = AsymmetricGamePseudoRealitySystem(
            seed=int(seed),
            scenario=cfg.scenario,
            n_entities=cfg.n_entities,
            action_coupling=cfg.action_coupling,
            noise_scale=cfg.noise_scale,
            drift_scale=cfg.drift_scale,
            profile_name=cfg.world_profile,
            profile_config=cfg.world_config,
        )
        traces.append(world.emit_trace())
        for _ in range(cfg.steps):
            traces.append(world.step(pd.DataFrame()))
    return traces


def _entity_feature_rows(trace: dict[str, pd.DataFrame], rows: list[dict]) -> None:
    e = trace["entity_trace"]
    seed, t, scenario = _trace_time(trace)
    for col in STATE_FEATURES:
        _append_stat_rows(
            rows,
            seed=seed,
            scenario=scenario,
            t=t,
            source_trace="entity_trace",
            feature_group="public_state",
            feature_name=str(col),
            values=_series(e, str(col)),
            observability_class="public_observed",
        )


def _relation_feature_rows(trace: dict[str, pd.DataFrame], rows: list[dict]) -> None:
    e = trace["entity_trace"]
    r = trace["relation_trace"]
    seed, t, scenario = _trace_time(trace)
    for col in ("relation_strength", "relation_rigidity", "flow"):
        _append_stat_rows(
            rows,
            seed=seed,
            scenario=scenario,
            t=t,
            source_trace="relation_trace",
            feature_group="relation_structure",
            feature_name=str(col),
            values=_series(r, str(col)),
            observability_class="public_relation_observed",
        )

    n_entities = max(1, int(e["entity_id"].nunique()))
    max_edges = max(1, n_entities * (n_entities - 1))
    edge_count = int(len(r)) if r is not None else 0
    scalar_features = {
        "relation_edge_count": float(edge_count),
        "relation_density": float(edge_count / max_edges),
    }
    if r is not None and not r.empty:
        out_degree = r["source"].value_counts().reindex(e["entity_id"]).fillna(0.0).astype(float)
        in_degree = r["target"].value_counts().reindex(e["entity_id"]).fillna(0.0).astype(float)
        total_degree = out_degree + in_degree
        _append_stat_rows(
            rows,
            seed=seed,
            scenario=scenario,
            t=t,
            source_trace="relation_trace",
            feature_group="relation_structure",
            feature_name="out_degree",
            values=out_degree,
            observability_class="public_relation_derived",
        )
        _append_stat_rows(
            rows,
            seed=seed,
            scenario=scenario,
            t=t,
            source_trace="relation_trace",
            feature_group="relation_structure",
            feature_name="in_degree",
            values=in_degree,
            observability_class="public_relation_derived",
        )
        _append_stat_rows(
            rows,
            seed=seed,
            scenario=scenario,
            t=t,
            source_trace="relation_trace",
            feature_group="relation_structure",
            feature_name="total_degree",
            values=total_degree,
            observability_class="public_relation_derived",
        )
        scalar_features["bridge_node_ratio"] = float(((out_degree > 0) & (in_degree > 0)).mean())
        scalar_features["degree_gini"] = _gini(total_degree.to_numpy(dtype=float))
    else:
        scalar_features["bridge_node_ratio"] = 0.0
        scalar_features["degree_gini"] = 0.0

    for feature_name, value in scalar_features.items():
        rows.append(
            _base_row(
                seed=seed,
                scenario=scenario,
                t=t,
                source_trace="relation_trace",
                feature_group="relation_structure",
                feature_name=feature_name,
                stat_name="value",
                feature_value=value,
                observability_class="public_relation_derived",
            )
        )


def _game_feature_rows(trace: dict[str, pd.DataFrame], rows: list[dict]) -> None:
    if "v2_game_trace" not in trace or trace["v2_game_trace"].empty:
        return
    g = trace["v2_game_trace"]
    seed, t, scenario = _trace_time(trace)
    for col in GAME_TENDENCY_COLUMNS:
        _append_stat_rows(
            rows,
            seed=seed,
            scenario=scenario,
            t=t,
            source_trace="v2_game_trace",
            feature_group="role_payoff_tendency",
            feature_name=str(col),
            values=_series(g, str(col)),
            observability_class="v2_observation_summary",
        )
    if "short_term_payoff" in g.columns and "long_term_health_proxy" in g.columns:
        gap = _series(g, "short_term_payoff") - _series(g, "long_term_health_proxy")
        _append_stat_rows(
            rows,
            seed=seed,
            scenario=scenario,
            t=t,
            source_trace="v2_game_trace",
            feature_group="role_payoff_tendency",
            feature_name="short_long_payoff_gap",
            values=gap,
            observability_class="v2_observation_summary",
        )
    if "primary_type" in g.columns:
        shares = g["primary_type"].astype(str).value_counts(normalize=True).sort_index()
        for primary_type, share in shares.items():
            rows.append(
                _base_row(
                    seed=seed,
                    scenario=scenario,
                    t=t,
                    source_trace="v2_game_trace",
                    feature_group="role_payoff_tendency",
                    feature_name=f"primary_type_share_{primary_type}",
                    stat_name="share",
                    feature_value=float(share),
                    observability_class="v2_observation_summary",
                )
            )


def _single_row_numeric_features(
    trace: dict[str, pd.DataFrame],
    rows: list[dict],
    *,
    source_trace: str,
    feature_group: str,
    columns: tuple[str, ...],
    observability_class: str,
) -> None:
    if source_trace not in trace or trace[source_trace].empty:
        return
    df = trace[source_trace]
    seed, t, scenario = _trace_time(trace)
    for col in columns:
        if col not in df.columns:
            continue
        values = _series(df, col)
        if values.empty:
            continue
        # Most v2 resource/information/action-effect traces are global one-row
        # summaries.  Use value for one row, and distribution stats if later
        # revisions emit multiple rows.
        if len(values) == 1:
            rows.append(
                _base_row(
                    seed=seed,
                    scenario=scenario,
                    t=t,
                    source_trace=source_trace,
                    feature_group=feature_group,
                    feature_name=str(col),
                    stat_name="value",
                    feature_value=float(values.iloc[0]),
                    observability_class=observability_class,
                )
            )
        else:
            _append_stat_rows(
                rows,
                seed=seed,
                scenario=scenario,
                t=t,
                source_trace=source_trace,
                feature_group=feature_group,
                feature_name=str(col),
                values=values,
                observability_class=observability_class,
            )


def build_current_candidate_feature_rows(traces: list[dict[str, pd.DataFrame]]) -> pd.DataFrame:
    rows: list[dict] = []
    for trace in traces:
        _entity_feature_rows(trace, rows)
        _relation_feature_rows(trace, rows)
        _game_feature_rows(trace, rows)
        _single_row_numeric_features(
            trace,
            rows,
            source_trace="v2_resource_trace",
            feature_group="resource_structure",
            columns=RESOURCE_COLUMNS,
            observability_class="v2_observation_summary",
        )
        _single_row_numeric_features(
            trace,
            rows,
            source_trace="v2_information_trace",
            feature_group="information_structure",
            columns=INFORMATION_COLUMNS,
            observability_class="v2_observation_summary",
        )
        _single_row_numeric_features(
            trace,
            rows,
            source_trace="v2_action_effect_trace",
            feature_group="action_effect_audit",
            columns=ACTION_EFFECT_COLUMNS,
            observability_class="v2_action_effect_audit",
        )
    return pd.DataFrame(rows, columns=REQUIRED_TASK2_8J_1_COLUMNS)


def build_temporal_candidate_feature_rows(
    current_log: pd.DataFrame,
    window_sizes: tuple[int, ...] = (1, 6, 12),
) -> pd.DataFrame:
    if current_log.empty:
        return current_log.copy()
    temporal_rows: list[dict] = []
    windows = tuple(int(w) for w in window_sizes if int(w) > 1)
    if not windows:
        return pd.DataFrame(columns=REQUIRED_TASK2_8J_1_COLUMNS)

    group_cols = [
        "seed",
        "scenario",
        "scope",
        "entity_id",
        "source_trace",
        "feature_group",
        "feature_name",
        "stat_name",
        "observability_class",
    ]
    base = current_log[current_log["window_size"].astype(int) == 1].copy()
    base = base.sort_values(["seed", "scenario", "t", "source_trace", "feature_group", "feature_name", "stat_name"])
    for keys, group in base.groupby(group_cols, dropna=False):
        key_map = dict(zip(group_cols, keys))
        group = group.sort_values("t")
        values = pd.to_numeric(group["feature_value"], errors="coerce").to_numpy(dtype=float)
        times = group["t"].astype(int).to_numpy()
        for pos, t in enumerate(times):
            for window in windows:
                start = max(0, pos - window + 1)
                vals = values[start : pos + 1]
                vals = vals[np.isfinite(vals)]
                if len(vals) < 2:
                    continue
                slope = float((vals[-1] - vals[0]) / max(len(vals) - 1, 1))
                temporal_stats = {
                    "window_mean": float(vals.mean()),
                    "window_std": float(vals.std(ddof=0)),
                    "window_slope": slope,
                    "window_delta": float(vals[-1] - vals[0]),
                    "window_min": float(vals.min()),
                    "window_max": float(vals.max()),
                    "window_persistence_up": float(np.mean(np.diff(vals) > 0.0)) if len(vals) >= 3 else float(vals[-1] > vals[0]),
                    "window_persistence_down": float(np.mean(np.diff(vals) < 0.0)) if len(vals) >= 3 else float(vals[-1] < vals[0]),
                }
                for temporal_stat, value in temporal_stats.items():
                    temporal_rows.append(
                        _base_row(
                            seed=int(key_map["seed"]),
                            scenario=str(key_map["scenario"]),
                            t=int(t),
                            source_trace=str(key_map["source_trace"]),
                            feature_group=str(key_map["feature_group"]),
                            feature_name=str(key_map["feature_name"]),
                            stat_name=f"{key_map['stat_name']}__{temporal_stat}",
                            feature_value=value,
                            window_id=f"w{window}",
                            window_size=int(window),
                            scope=str(key_map["scope"]),
                            entity_id=str(key_map["entity_id"]),
                            temporal_feature=True,
                            input_role="temporal_candidate_feature",
                            observability_class=str(key_map["observability_class"]),
                        )
                    )
    return pd.DataFrame(temporal_rows, columns=REQUIRED_TASK2_8J_1_COLUMNS)


def build_candidate_feature_log(cfg: CandidateFeatureLogConfig | None = None) -> pd.DataFrame:
    cfg = cfg or CandidateFeatureLogConfig()
    traces = build_v2_trace_history(cfg)
    current = build_current_candidate_feature_rows(traces)
    temporal = build_temporal_candidate_feature_rows(current, cfg.window_sizes)
    out = pd.concat([current, temporal], ignore_index=True)
    if not out.empty:
        out = out.sort_values(
            ["seed", "scenario", "t", "window_size", "source_trace", "feature_group", "feature_name", "stat_name"],
            ignore_index=True,
        )
    return out


def build_candidate_feature_schema() -> pd.DataFrame:
    rows = [CandidateFeatureSchemaRow(column=c, role="required_output_column") for c in REQUIRED_TASK2_8J_1_COLUMNS]
    return pd.DataFrame([r.__dict__ for r in rows])


def build_feature_input_audit(feature_log: pd.DataFrame) -> pd.DataFrame:
    if feature_log is None or feature_log.empty:
        return pd.DataFrame(
            [
                {
                    "source_trace": "__overall__",
                    "rows": 0,
                    "unique_features": 0,
                    "hidden_truth_input_rows": 0,
                    "raw_trace_passthrough_rows": 0,
                    "allowed_for_gt_all": False,
                    "feature_value_valid_all": False,
                    "audit_status": "fail_empty",
                }
            ]
        )
    rows = []
    for source, group in feature_log.groupby("source_trace"):
        rows.append(
            {
                "source_trace": str(source),
                "rows": int(len(group)),
                "unique_features": int(group[["feature_group", "feature_name", "stat_name"]].drop_duplicates().shape[0]),
                "hidden_truth_input_rows": int(group["hidden_truth_input"].astype(bool).sum()),
                "raw_trace_passthrough_rows": int(group["raw_trace_passthrough"].astype(bool).sum()),
                "allowed_for_gt_all": bool(group["allowed_for_gt"].astype(bool).all()),
                "feature_value_valid_all": bool(group["feature_value_valid"].astype(bool).all()),
                "audit_status": "pass" if bool(group["allowed_for_gt"].astype(bool).all()) and not bool(group["hidden_truth_input"].astype(bool).any()) else "fail",
            }
        )
    rows.append(
        {
            "source_trace": "__overall__",
            "rows": int(len(feature_log)),
            "unique_features": int(feature_log[["feature_group", "feature_name", "stat_name"]].drop_duplicates().shape[0]),
            "hidden_truth_input_rows": int(feature_log["hidden_truth_input"].astype(bool).sum()),
            "raw_trace_passthrough_rows": int(feature_log["raw_trace_passthrough"].astype(bool).sum()),
            "allowed_for_gt_all": bool(feature_log["allowed_for_gt"].astype(bool).all()),
            "feature_value_valid_all": bool(feature_log["feature_value_valid"].astype(bool).all()),
            "audit_status": "pass"
            if bool(feature_log["allowed_for_gt"].astype(bool).all())
            and not bool(feature_log["hidden_truth_input"].astype(bool).any())
            and not bool(feature_log["raw_trace_passthrough"].astype(bool).any())
            else "fail",
        }
    )
    return pd.DataFrame(rows)


def validate_candidate_feature_log(feature_log: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    if feature_log is None or feature_log.empty:
        return ["task2_8j_1_empty_feature_log"]
    missing = [c for c in REQUIRED_TASK2_8J_1_COLUMNS if c not in feature_log.columns]
    if missing:
        errors.append("task2_8j_1_missing_columns:" + ",".join(missing))
        return errors

    forbidden_true = [
        "runtime_policy_input",
        "fullspec_runtime_connected",
        "upper_pressure_connected",
        "action_frame_created",
        "actionmodule_called",
        "canonical_write_performed",
        "gk_writeback_performed",
        "ot_writeback_performed",
        "effective_dimension_extracted",
        "dynamics_axis_extracted",
        "raw_trace_passthrough",
        "future_information_used",
    ]
    for col in forbidden_true:
        if bool(feature_log[col].astype(bool).any()):
            errors.append(f"task2_8j_1_forbidden_true:{col}")

    if not bool(feature_log["validation_only"].astype(bool).all()):
        errors.append("task2_8j_1_validation_only_not_all_true")
    if not bool(feature_log["candidate_feature_log"].astype(bool).all()):
        errors.append("task2_8j_1_candidate_feature_log_not_all_true")
    if not bool(feature_log["feature_value_valid"].astype(bool).all()):
        errors.append("task2_8j_1_invalid_feature_value")
    if bool(feature_log["hidden_truth_input"].astype(bool).any()):
        errors.append("task2_8j_1_hidden_truth_input_true")
    if bool(feature_log["source_trace"].astype(str).isin(FORBIDDEN_INPUT_TRACES).any()):
        errors.append("task2_8j_1_hidden_trace_used_as_input")
    unknown_sources = sorted(set(feature_log["source_trace"].astype(str)) - ALLOWED_INPUT_TRACES)
    if unknown_sources:
        errors.append("task2_8j_1_unknown_source_trace:" + ",".join(unknown_sources))
    if not bool(feature_log["allowed_for_gt"].astype(bool).all()):
        errors.append("task2_8j_1_allowed_for_gt_not_all_true")
    if not bool((feature_log["window_size"].astype(int) > 1).any()):
        errors.append("task2_8j_1_missing_temporal_window_features")
    if not bool(feature_log["temporal_feature"].astype(bool).any()):
        errors.append("task2_8j_1_missing_temporal_feature_rows")

    required_sources = {"entity_trace", "relation_trace", "v2_game_trace", "v2_resource_trace", "v2_information_trace"}
    missing_sources = sorted(required_sources - set(feature_log["source_trace"].astype(str).unique()))
    if missing_sources:
        errors.append("task2_8j_1_missing_required_sources:" + ",".join(missing_sources))
    return errors


def summarize_candidate_feature_log(feature_log: pd.DataFrame) -> dict:
    if feature_log is None or feature_log.empty:
        return {"rows": 0, "status": "empty"}
    temporal = feature_log[feature_log["temporal_feature"].astype(bool)]
    current = feature_log[~feature_log["temporal_feature"].astype(bool)]
    return {
        "rows": int(len(feature_log)),
        "current_rows": int(len(current)),
        "temporal_rows": int(len(temporal)),
        "unique_features": int(feature_log[["feature_group", "feature_name", "stat_name"]].drop_duplicates().shape[0]),
        "feature_groups": sorted(feature_log["feature_group"].astype(str).unique().tolist()),
        "source_traces": sorted(feature_log["source_trace"].astype(str).unique().tolist()),
        "window_sizes": sorted(int(x) for x in feature_log["window_size"].astype(int).unique().tolist()),
        "seeds": sorted(int(x) for x in feature_log["seed"].astype(int).unique().tolist()),
        "t_min": int(feature_log["t"].astype(int).min()),
        "t_max": int(feature_log["t"].astype(int).max()),
        "hidden_truth_input_rows": int(feature_log["hidden_truth_input"].astype(bool).sum()),
        "raw_trace_passthrough_rows": int(feature_log["raw_trace_passthrough"].astype(bool).sum()),
        "effective_dimension_extracted": bool(feature_log["effective_dimension_extracted"].astype(bool).any()),
        "dynamics_axis_extracted": bool(feature_log["dynamics_axis_extracted"].astype(bool).any()),
    }


def build_and_validate_candidate_feature_log(
    cfg: CandidateFeatureLogConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, list[str], dict]:
    feature_log = build_candidate_feature_log(cfg)
    input_audit = build_feature_input_audit(feature_log)
    errors = validate_candidate_feature_log(feature_log)
    summary = summarize_candidate_feature_log(feature_log)
    summary["validation_errors"] = errors
    summary["input_audit_status"] = "pass" if not input_audit.empty and set(input_audit["audit_status"].astype(str)) == {"pass"} else "fail"
    return feature_log, input_audit, errors, summary
