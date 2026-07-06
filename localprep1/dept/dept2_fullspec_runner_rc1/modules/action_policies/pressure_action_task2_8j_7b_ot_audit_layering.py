"""Task 2-8j-7b: O_t audit-target reason / strength layering RC1.

Purpose:
    Split O_t audit targets into reason and strength layers so that risk,
    confidence, change magnitude, centrality, and residual / weak-state concerns
    are not collapsed into a single boolean flag.

Position:
    Task 2-8j-7 creates O_t observation-map units from the verified relation
    field while keeping the upper-pressure route separate.  This task refines
    the O_t audit route only: it does not create upper pressure, action-module
    inputs, or concrete actions.

Boundary:
    - O_t audit-layer validation only
    - fixed static_pca_7 main map
    - upper-pressure route remains separate and unconnected
    - no action conversion, ActionFrame creation, ActionModule call, runtime call, or writeback
    - no hidden-truth / future-information input
    - no effective-dimension re-fitting or axis mutation
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .pressure_action_task2_8j_6c_v2_structure_change_relation_field_tracking import V2StructureChangeTrackingConfig
from .pressure_action_task2_8j_7_ot_observation_map_from_relation_field import (
    OtObservationMapConfig,
    build_and_validate_ot_observation_map_from_relation_field,
)

TASK2_8J_7B_VERSION = "ot_audit_target_reason_strength_layering_rc1"
TASK2_8J_7B_CONTRACT = (
    "Task2_8j_7b_Ot_audit_target_reason_strength_layering__"
    "risk_confidence_change_centrality_residual_split__"
    "upper_pressure_route_separate__no_actionmodule_no_writeback"
)

BOUNDARY = {
    "task2_8j_7b_version": TASK2_8J_7B_VERSION,
    "task2_8j_7b_contract": TASK2_8J_7B_CONTRACT,
    "validation_only": True,
    "audit_layering_only": True,
    "observation_map_source": "Task2_8j_7_ot_observation_map",
    "gt_main_map_name": "static_pca_7",
    "gt_main_component_count": 7,
    "upper_pressure_route_connected": False,
    "hdept_pressure_generated": False,
    "action_input_converted": False,
    "action_frame_created": False,
    "actionmodule_called": False,
    "runtime_policy_input": False,
    "fullspec_runtime_connected": False,
    "canonical_write_performed": False,
    "gk_writeback_performed": False,
    "ot_writeback_performed": False,
    "effective_dimension_refit_performed": False,
    "axis_mutation_performed": False,
    "residual_auxiliary_injected_into_gt_main": False,
    "hidden_truth_input": False,
    "future_information_used": False,
}

FORBIDDEN_TRUE = [
    "upper_pressure_route_connected",
    "hdept_pressure_generated",
    "action_input_converted",
    "action_frame_created",
    "actionmodule_called",
    "runtime_policy_input",
    "fullspec_runtime_connected",
    "canonical_write_performed",
    "gk_writeback_performed",
    "ot_writeback_performed",
    "effective_dimension_refit_performed",
    "axis_mutation_performed",
    "residual_auxiliary_injected_into_gt_main",
    "hidden_truth_input",
    "future_information_used",
]

REQUIRED_LAYER_COLUMNS = list(BOUNDARY) + [
    "observation_id",
    "observation_kind",
    "where_signal",
    "audit_candidate",
    "audit_reason_count",
    "audit_reasons",
    "risk_reason_count",
    "confidence_reason_count",
    "change_reason_count",
    "centrality_reason_count",
    "residual_reason_count",
    "risk_score",
    "confidence_score",
    "change_score",
    "centrality_score",
    "residual_score",
    "audit_strength_score",
    "audit_level",
    "direct_action_allowed_without_review",
    "audit_layer_status",
]

REQUIRED_REASON_COLUMNS = list(BOUNDARY) + [
    "audit_reason",
    "reason_category",
    "observation_count",
    "mean_audit_strength_score",
    "max_audit_strength_score",
    "dominant_audit_level",
]

REQUIRED_SUMMARY_COLUMNS = list(BOUNDARY) + [
    "observation_unit_count",
    "audit_candidate_count",
    "monitor_count",
    "review_before_action_count",
    "block_direct_action_count",
    "risk_reason_total",
    "confidence_reason_total",
    "change_reason_total",
    "centrality_reason_total",
    "residual_reason_total",
    "reason_summary_count",
    "audit_layering_decision",
    "next_task",
]


@dataclass(frozen=True)
class OtAuditLayeringConfig:
    low_confidence_threshold: float = 0.55
    medium_confidence_threshold: float = 0.75
    high_change_threshold: float = 0.70
    medium_change_threshold: float = 0.35
    high_centrality_threshold: int = 8
    medium_centrality_threshold: int = 4
    review_threshold: float = 0.38
    block_threshold: float = 0.62


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return float(default)
    if not np.isfinite(out):
        return float(default)
    return float(out)


def _clip01(value: float) -> float:
    return float(min(1.0, max(0.0, value)))


def _split_nodes(row) -> list[str]:
    nodes = [str(row.direction_from), str(row.direction_to)]
    where = str(row.where_signal)
    if "->" in where:
        nodes.extend([p.strip() for p in where.split("->") if p.strip()])
    else:
        nodes.append(where)
    return [n for n in nodes if n and n.lower() != "nan"]


def _node_centrality(observation_units: pd.DataFrame) -> Counter:
    counter: Counter = Counter()
    for row in observation_units.itertuples(index=False):
        for node in set(_split_nodes(row)):
            counter[node] += 1
    return counter


def _reason_category(reason: str) -> str:
    if reason in {"resource_pressure_involved", "action_side_effect_sensitive"}:
        return "risk"
    if reason in {"low_confidence", "medium_confidence"}:
        return "confidence"
    if reason in {"high_change_intensity", "medium_change_intensity", "phase_sensitive_relation"}:
        return "change"
    if reason in {"high_centrality", "medium_centrality"}:
        return "centrality"
    if reason in {"residual_flag", "weak_state_reproduction"}:
        return "residual"
    return "other"


def _dominant_level(levels: pd.Series) -> str:
    order = {"block_direct_action": 3, "review_before_action": 2, "monitor": 1}
    if levels.empty:
        return "monitor"
    return max(levels.astype(str), key=lambda v: order.get(v, 0))


def _reasons_for_observation(row, centrality: Counter, cfg: OtAuditLayeringConfig) -> tuple[list[str], dict[str, float]]:
    reasons: list[str] = []
    nodes = set(_split_nodes(row))
    confidence = _safe_float(row.confidence)
    intensity = _safe_float(row.intensity)
    residual = bool(row.residual_flag)
    original_audit = bool(row.audit_target)
    kind = str(row.observation_kind)
    polarity = str(row.direction_polarity)
    if original_audit:
        reasons.append("original_task2_8j_7_audit_target")
    if "resource_pressure" in nodes:
        reasons.append("resource_pressure_involved")
    if {"information_degradation", "resource_pressure"} & nodes:
        reasons.append("action_side_effect_sensitive")
    if confidence < cfg.low_confidence_threshold:
        reasons.append("low_confidence")
    elif confidence < cfg.medium_confidence_threshold:
        reasons.append("medium_confidence")
    if intensity >= cfg.high_change_threshold:
        reasons.append("high_change_intensity")
    elif intensity >= cfg.medium_change_threshold:
        reasons.append("medium_change_intensity")
    if kind == "relation_change":
        reasons.append("phase_sensitive_relation")
    max_cent = max([centrality.get(n, 0) for n in nodes] or [0])
    if max_cent >= cfg.high_centrality_threshold:
        reasons.append("high_centrality")
    elif max_cent >= cfg.medium_centrality_threshold:
        reasons.append("medium_centrality")
    if residual:
        reasons.append("residual_flag")
    if polarity == "watch_weak_state":
        reasons.append("weak_state_reproduction")
    # Stable order, no duplicates.
    reasons = list(dict.fromkeys(reasons))
    scores = {
        "risk_score": 0.0,
        "confidence_score": 0.0,
        "change_score": 0.0,
        "centrality_score": 0.0,
        "residual_score": 0.0,
    }
    if "resource_pressure_involved" in reasons:
        scores["risk_score"] += 0.35
    if "action_side_effect_sensitive" in reasons:
        scores["risk_score"] += 0.20
    if "low_confidence" in reasons:
        scores["confidence_score"] += 0.45
    if "medium_confidence" in reasons:
        scores["confidence_score"] += 0.20
    if "high_change_intensity" in reasons:
        scores["change_score"] += 0.35
    if "medium_change_intensity" in reasons:
        scores["change_score"] += 0.20
    if "phase_sensitive_relation" in reasons:
        scores["change_score"] += 0.12
    if "high_centrality" in reasons:
        scores["centrality_score"] += 0.35
    if "medium_centrality" in reasons:
        scores["centrality_score"] += 0.18
    if "residual_flag" in reasons:
        scores["residual_score"] += 0.35
    if "weak_state_reproduction" in reasons:
        scores["residual_score"] += 0.25
    for key in list(scores):
        scores[key] = _clip01(scores[key])
    return reasons, scores


def _audit_level(score: float, reasons: list[str], cfg: OtAuditLayeringConfig) -> str:
    if score >= cfg.block_threshold or {"residual_flag", "low_confidence"}.issubset(set(reasons)):
        return "block_direct_action"
    if score >= cfg.review_threshold or "resource_pressure_involved" in reasons:
        return "review_before_action"
    return "monitor"


def build_audit_layer_table(observation_units: pd.DataFrame, cfg: OtAuditLayeringConfig | None = None) -> pd.DataFrame:
    cfg = cfg or OtAuditLayeringConfig()
    if observation_units is None or observation_units.empty:
        return pd.DataFrame(columns=REQUIRED_LAYER_COLUMNS)
    centrality = _node_centrality(observation_units)
    rows: list[dict] = []
    for row in observation_units.itertuples(index=False):
        reasons, scores = _reasons_for_observation(row, centrality, cfg)
        risk_count = sum(1 for r in reasons if _reason_category(r) == "risk")
        conf_count = sum(1 for r in reasons if _reason_category(r) == "confidence")
        change_count = sum(1 for r in reasons if _reason_category(r) == "change")
        cent_count = sum(1 for r in reasons if _reason_category(r) == "centrality")
        residual_count = sum(1 for r in reasons if _reason_category(r) == "residual")
        strength = _clip01(
            0.32 * scores["risk_score"]
            + 0.22 * scores["confidence_score"]
            + 0.18 * scores["change_score"]
            + 0.18 * scores["centrality_score"]
            + 0.10 * scores["residual_score"]
        )
        level = _audit_level(strength, reasons, cfg)
        rows.append({
            **BOUNDARY,
            "observation_id": str(row.observation_id),
            "observation_kind": str(row.observation_kind),
            "where_signal": str(row.where_signal),
            "audit_candidate": bool(reasons),
            "audit_reason_count": int(len(reasons)),
            "audit_reasons": ";".join(reasons),
            "risk_reason_count": int(risk_count),
            "confidence_reason_count": int(conf_count),
            "change_reason_count": int(change_count),
            "centrality_reason_count": int(cent_count),
            "residual_reason_count": int(residual_count),
            "risk_score": scores["risk_score"],
            "confidence_score": scores["confidence_score"],
            "change_score": scores["change_score"],
            "centrality_score": scores["centrality_score"],
            "residual_score": scores["residual_score"],
            "audit_strength_score": strength,
            "audit_level": level,
            "direct_action_allowed_without_review": bool(level == "monitor"),
            "audit_layer_status": "layered_audit_target" if reasons else "no_audit_reason_detected",
        })
    return pd.DataFrame(rows, columns=REQUIRED_LAYER_COLUMNS)


def build_reason_summary(audit_layers: pd.DataFrame) -> pd.DataFrame:
    if audit_layers is None or audit_layers.empty:
        return pd.DataFrame(columns=REQUIRED_REASON_COLUMNS)
    expanded: list[dict] = []
    for row in audit_layers.itertuples(index=False):
        reasons = [r for r in str(row.audit_reasons).split(";") if r]
        for reason in reasons:
            expanded.append({
                "audit_reason": reason,
                "reason_category": _reason_category(reason),
                "audit_strength_score": _safe_float(row.audit_strength_score),
                "audit_level": str(row.audit_level),
            })
    if not expanded:
        return pd.DataFrame(columns=REQUIRED_REASON_COLUMNS)
    df = pd.DataFrame(expanded)
    rows: list[dict] = []
    for (reason, category), sub in df.groupby(["audit_reason", "reason_category"], sort=True):
        rows.append({
            **BOUNDARY,
            "audit_reason": str(reason),
            "reason_category": str(category),
            "observation_count": int(len(sub)),
            "mean_audit_strength_score": float(sub["audit_strength_score"].mean()),
            "max_audit_strength_score": float(sub["audit_strength_score"].max()),
            "dominant_audit_level": _dominant_level(sub["audit_level"]),
        })
    return pd.DataFrame(rows, columns=REQUIRED_REASON_COLUMNS)


def build_final_summary(audit_layers: pd.DataFrame, reason_summary: pd.DataFrame) -> pd.DataFrame:
    count = int(len(audit_layers)) if audit_layers is not None else 0
    audit_count = int(audit_layers["audit_candidate"].astype(bool).sum()) if count else 0
    monitor = int((audit_layers["audit_level"].astype(str) == "monitor").sum()) if count else 0
    review = int((audit_layers["audit_level"].astype(str) == "review_before_action").sum()) if count else 0
    block = int((audit_layers["audit_level"].astype(str) == "block_direct_action").sum()) if count else 0
    risk_total = int(audit_layers["risk_reason_count"].astype(int).sum()) if count else 0
    conf_total = int(audit_layers["confidence_reason_count"].astype(int).sum()) if count else 0
    change_total = int(audit_layers["change_reason_count"].astype(int).sum()) if count else 0
    cent_total = int(audit_layers["centrality_reason_count"].astype(int).sum()) if count else 0
    residual_total = int(audit_layers["residual_reason_count"].astype(int).sum()) if count else 0
    reason_count = int(len(reason_summary)) if reason_summary is not None else 0
    if count > 0 and audit_count > 0 and reason_count >= 5 and (review + block) > 0:
        decision = "ot_audit_targets_layered_by_reason_and_strength"
    else:
        decision = "ot_audit_layering_not_confirmed"
    return pd.DataFrame([{
        **BOUNDARY,
        "observation_unit_count": count,
        "audit_candidate_count": audit_count,
        "monitor_count": monitor,
        "review_before_action_count": review,
        "block_direct_action_count": block,
        "risk_reason_total": risk_total,
        "confidence_reason_total": conf_total,
        "change_reason_total": change_total,
        "centrality_reason_total": cent_total,
        "residual_reason_total": residual_total,
        "reason_summary_count": reason_count,
        "audit_layering_decision": decision,
        "next_task": "Task 2-8j-8: action-module input split contract for upper-pressure route and O_t observation-map route",
    }], columns=REQUIRED_SUMMARY_COLUMNS)


def validate_ot_audit_layering_tables(audit_layers: pd.DataFrame, reason_summary: pd.DataFrame, final_summary: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    tables = {
        "audit_layers": (audit_layers, REQUIRED_LAYER_COLUMNS),
        "reason_summary": (reason_summary, REQUIRED_REASON_COLUMNS),
        "final_summary": (final_summary, REQUIRED_SUMMARY_COLUMNS),
    }
    for name, (table, required) in tables.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_7b_empty_table:{name}")
            continue
        missing = [c for c in required if c not in table.columns]
        if missing:
            errors.append(f"task2_8j_7b_missing_columns:{name}:" + ",".join(missing))
            continue
        for col in ["validation_only", "audit_layering_only"]:
            if not bool(table[col].astype(bool).all()):
                errors.append(f"task2_8j_7b_required_true_not_all_true:{name}:{col}")
        if set(table["gt_main_map_name"].astype(str)) != {"static_pca_7"}:
            errors.append(f"task2_8j_7b_wrong_gt_main_map_name:{name}")
        if set(table["gt_main_component_count"].astype(int)) != {7}:
            errors.append(f"task2_8j_7b_wrong_component_count:{name}")
        for col in FORBIDDEN_TRUE:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_7b_forbidden_true:{name}:{col}")
    if audit_layers is not None and not audit_layers.empty:
        for col in ["risk_score", "confidence_score", "change_score", "centrality_score", "residual_score", "audit_strength_score"]:
            if not bool(audit_layers[col].astype(float).between(0.0, 1.0).all()):
                errors.append(f"task2_8j_7b_score_out_of_range:{col}")
        allowed = {"monitor", "review_before_action", "block_direct_action"}
        if not set(audit_layers["audit_level"].astype(str)).issubset(allowed):
            errors.append("task2_8j_7b_unknown_audit_level")
    return errors


def build_and_validate_ot_audit_layering(
    tracking_cfg: V2StructureChangeTrackingConfig | None = None,
    ot_cfg: OtObservationMapConfig | None = None,
    cfg: OtAuditLayeringConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    observation_units, _route_table, _ot_summary, ot_errors, _ot_json = build_and_validate_ot_observation_map_from_relation_field(
        tracking_cfg or V2StructureChangeTrackingConfig(),
        ot_cfg or OtObservationMapConfig(),
    )
    audit_layers = build_audit_layer_table(observation_units, cfg or OtAuditLayeringConfig())
    reason_summary = build_reason_summary(audit_layers)
    final_summary = build_final_summary(audit_layers, reason_summary)
    errors = [f"task2_8j_7b_upstream_7_error:{e}" for e in ot_errors]
    errors.extend(validate_ot_audit_layering_tables(audit_layers, reason_summary, final_summary))
    summary = {
        "gt_main_map_name": "static_pca_7",
        "gt_main_component_count": 7,
        "observation_unit_count": int(final_summary["observation_unit_count"].iloc[0]) if not final_summary.empty else 0,
        "audit_candidate_count": int(final_summary["audit_candidate_count"].iloc[0]) if not final_summary.empty else 0,
        "monitor_count": int(final_summary["monitor_count"].iloc[0]) if not final_summary.empty else 0,
        "review_before_action_count": int(final_summary["review_before_action_count"].iloc[0]) if not final_summary.empty else 0,
        "block_direct_action_count": int(final_summary["block_direct_action_count"].iloc[0]) if not final_summary.empty else 0,
        "risk_reason_total": int(final_summary["risk_reason_total"].iloc[0]) if not final_summary.empty else 0,
        "confidence_reason_total": int(final_summary["confidence_reason_total"].iloc[0]) if not final_summary.empty else 0,
        "change_reason_total": int(final_summary["change_reason_total"].iloc[0]) if not final_summary.empty else 0,
        "centrality_reason_total": int(final_summary["centrality_reason_total"].iloc[0]) if not final_summary.empty else 0,
        "residual_reason_total": int(final_summary["residual_reason_total"].iloc[0]) if not final_summary.empty else 0,
        "reason_summary_count": int(final_summary["reason_summary_count"].iloc[0]) if not final_summary.empty else 0,
        "audit_layering_decision": str(final_summary["audit_layering_decision"].iloc[0]) if not final_summary.empty else "empty",
        "upper_pressure_route_connected": False,
        "actionmodule_called": False,
        "validation_errors": errors,
    }
    return audit_layers, reason_summary, final_summary, errors, summary
