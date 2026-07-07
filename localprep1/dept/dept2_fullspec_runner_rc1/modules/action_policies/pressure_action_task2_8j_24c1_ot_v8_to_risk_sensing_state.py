"""Task 2-8j-24c1: O_t / v8 -> risk-sensing simulation state RC1.

This is an implementation step, not a standalone contract step.

Purpose:
    Take already-shaped O_t terrain/game-structure information and v8 local
    observation summaries, preserve the source information, and convert them into
    numerical risk-sensing states that can be passed to the existing Task2-8j-22
    short-horizon NO_OP risk simulator.

Key rule:
    Do not cut away prediction-relevant information.  The output keeps source
    packet ids, terrain location, risk evidence status, terrain map summary,
    game-structure summary, and v8 local observation summary next to the numeric
    simulator features.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from .pressure_action_task2_8j_24c0_actionmodule_information_intake_bridge import (
    build_actionmodule_information_intake_packets,
)

TASK2_8J_24C1_VERSION = "ot_v8_to_risk_sensing_state_rc1"

SOURCE_INFORMATION_COLUMNS = [
    "intake_packet_id",
    "source_ot_packet_id",
    "source_v8_local_observation_id",
    "terrain_location_id",
    "risk_name",
    "risk_evidence_status",
    "risk_evidence_status_is_mutable",
    "terrain_map_summary",
    "game_structure_summary",
    "v8_local_observation_summary",
]

SIMULATOR_NUMERIC_COLUMNS = [
    "pressure_gradient",
    "relation_lock_signal",
    "reversibility",
    "boundary_distance",
    "escape_path_capacity",
    "neighbor_capacity",
    "flow_velocity",
    "curvature",
    "uncertainty",
    "NO_OP_baseline",
]

STATE_COLUMNS = [
    "task2_8j_24c1_version",
    "risk_sensing_state_id",
    "macro_state_id",
    "macro_state_name",
    "risk_label_for_evaluation_only",
    *SOURCE_INFORMATION_COLUMNS,
    *SIMULATOR_NUMERIC_COLUMNS,
    "dominant_numeric_feature",
    "source_information_preserved_count",
    "source_information_required_count",
    "source_information_preservation_status",
    "numeric_state_status",
]

QUALITY_COLUMNS = [
    "task2_8j_24c1_version",
    "risk_sensing_state_id",
    "risk_name",
    "terrain_location_id",
    "target_signal_name",
    "target_signal_value",
    "supporting_signal_summary",
    "risk_signal_alignment_score",
    "source_information_preservation_score",
    "simulator_numeric_completeness_score",
    "overall_state_quality_score",
    "simulator_ready",
    "quality_status",
]

SUMMARY_COLUMNS = [
    "task2_8j_24c1_version",
    "input_packet_count",
    "risk_sensing_state_count",
    "quality_row_count",
    "simulator_ready_state_count",
    "source_information_preserved_state_count",
    "numeric_complete_state_count",
    "risk_names_carried",
    "task2_8j_24c1_decision",
    "next_task",
]

# These are initial numerical encodings of the O_t/v8 risk evidence into the
# feature shape expected by the existing Task2-8j-22 coarse macro-game simulator.
# They are not final truths; they are state-construction priors to be tested by
# the downstream simulator.
RISK_NUMERIC_PROFILES: dict[str, dict[str, float | str]] = {
    "relation_lock": {
        "macro_state_id": "macro_lock_basin_from_ot_v8",
        "macro_state_name": "lock_basin_relation_cluster_from_ot_v8",
        "pressure_gradient": 0.78,
        "relation_lock_signal": 0.84,
        "reversibility": 0.38,
        "boundary_distance": 0.42,
        "escape_path_capacity": 0.31,
        "neighbor_capacity": 0.36,
        "flow_velocity": 0.41,
        "curvature": 0.28,
        "uncertainty": 0.34,
        "NO_OP_baseline": 0.55,
        "dominant_numeric_feature": "relation_lock_signal",
    },
    "resource_pressure": {
        "macro_state_id": "macro_resource_pressure_from_ot_v8",
        "macro_state_name": "resource_pressure_spike_from_ot_v8",
        "pressure_gradient": 0.86,
        "relation_lock_signal": 0.45,
        "reversibility": 0.52,
        "boundary_distance": 0.48,
        "escape_path_capacity": 0.44,
        "neighbor_capacity": 0.28,
        "flow_velocity": 0.58,
        "curvature": 0.36,
        "uncertainty": 0.31,
        "NO_OP_baseline": 0.61,
        "dominant_numeric_feature": "pressure_gradient",
    },
    "reversibility_loss": {
        "macro_state_id": "macro_reversibility_thin_from_ot_v8",
        "macro_state_name": "reversibility_thin_return_path_from_ot_v8",
        "pressure_gradient": 0.55,
        "relation_lock_signal": 0.48,
        "reversibility": 0.25,
        "boundary_distance": 0.36,
        "escape_path_capacity": 0.33,
        "neighbor_capacity": 0.47,
        "flow_velocity": 0.44,
        "curvature": 0.33,
        "uncertainty": 0.42,
        "NO_OP_baseline": 0.60,
        "dominant_numeric_feature": "reversibility_and_escape_path_capacity",
    },
    "boundary_fragile": {
        "macro_state_id": "macro_boundary_fragile_from_ot_v8",
        "macro_state_name": "shock_boundary_fragile_from_ot_v8",
        "pressure_gradient": 0.62,
        "relation_lock_signal": 0.40,
        "reversibility": 0.34,
        "boundary_distance": 0.24,
        "escape_path_capacity": 0.38,
        "neighbor_capacity": 0.42,
        "flow_velocity": 0.53,
        "curvature": 0.41,
        "uncertainty": 0.49,
        "NO_OP_baseline": 0.66,
        "dominant_numeric_feature": "boundary_distance",
    },
    "oscillation": {
        "macro_state_id": "macro_oscillation_from_ot_v8",
        "macro_state_name": "oscillatory_flow_instability_from_ot_v8",
        "pressure_gradient": 0.58,
        "relation_lock_signal": 0.39,
        "reversibility": 0.50,
        "boundary_distance": 0.58,
        "escape_path_capacity": 0.56,
        "neighbor_capacity": 0.50,
        "flow_velocity": 0.82,
        "curvature": 0.80,
        "uncertainty": 0.37,
        "NO_OP_baseline": 0.43,
        "dominant_numeric_feature": "flow_velocity_and_curvature",
    },
}


@dataclass(frozen=True)
class OtV8RiskSensingStateConfig:
    include_non_stable_risks: bool = True
    min_source_preservation_score: float = 1.0
    min_numeric_completeness_score: float = 1.0
    min_alignment_score: float = 0.55


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _is_present(value: object) -> bool:
    if value is None:
        return False
    text = str(value).strip()
    return bool(text) and text.lower() not in {"nan", "none", "null"}


def _source_preserved_count(row: pd.Series) -> int:
    return sum(1 for col in SOURCE_INFORMATION_COLUMNS if col in row and _is_present(row[col]))


def _numeric_complete_count(row: pd.Series) -> int:
    return sum(1 for col in SIMULATOR_NUMERIC_COLUMNS if col in row and pd.notna(row[col]))


def _target_signal(risk_name: str, row: pd.Series) -> tuple[str, float, str]:
    risk = str(risk_name)
    if risk == "relation_lock":
        return "relation_lock_signal", float(row["relation_lock_signal"]), (
            f"pressure={row['pressure_gradient']};escape={row['escape_path_capacity']};rev={row['reversibility']}"
        )
    if risk == "resource_pressure":
        return "pressure_gradient", float(row["pressure_gradient"]), (
            f"neighbor={row['neighbor_capacity']};escape={row['escape_path_capacity']};boundary={row['boundary_distance']}"
        )
    if risk == "reversibility_loss":
        value = _clip01(0.55 * (1.0 - float(row["reversibility"])) + 0.45 * (1.0 - float(row["escape_path_capacity"])))
        return "return_path_thinning", value, (
            f"reversibility={row['reversibility']};escape={row['escape_path_capacity']};boundary={row['boundary_distance']}"
        )
    if risk == "boundary_fragile":
        return "boundary_fragility", _clip01(1.0 - float(row["boundary_distance"])), (
            f"boundary={row['boundary_distance']};uncertainty={row['uncertainty']};rev={row['reversibility']}"
        )
    if risk == "oscillation":
        value = _clip01(0.52 * float(row["flow_velocity"]) + 0.48 * float(row["curvature"]))
        return "oscillation_energy", value, (
            f"flow={row['flow_velocity']};curvature={row['curvature']};uncertainty={row['uncertainty']}"
        )
    return "unknown", 0.0, "unknown_risk"


def build_ot_v8_risk_sensing_states(
    intake_packets: pd.DataFrame | None = None,
    config: OtV8RiskSensingStateConfig | None = None,
) -> pd.DataFrame:
    cfg = config or OtV8RiskSensingStateConfig()
    packets = intake_packets
    if packets is None:
        packets = build_actionmodule_information_intake_packets()
    if packets is None or packets.empty:
        return pd.DataFrame(columns=STATE_COLUMNS)

    rows: list[dict[str, Any]] = []
    for i, packet in packets.reset_index(drop=True).iterrows():
        risk_name = str(packet["risk_name"])
        if not cfg.include_non_stable_risks and risk_name in {"boundary_fragile", "resource_pressure"}:
            continue
        if risk_name not in RISK_NUMERIC_PROFILES:
            continue
        profile = RISK_NUMERIC_PROFILES[risk_name]
        row: dict[str, Any] = {
            "task2_8j_24c1_version": TASK2_8J_24C1_VERSION,
            "risk_sensing_state_id": f"risk_sensing_state_{i+1:04d}_{risk_name}",
            "macro_state_id": str(profile["macro_state_id"]),
            "macro_state_name": str(profile["macro_state_name"]),
            "risk_label_for_evaluation_only": risk_name,
        }
        for col in SOURCE_INFORMATION_COLUMNS:
            row[col] = packet[col] if col in packet else ""
        for col in SIMULATOR_NUMERIC_COLUMNS:
            row[col] = float(profile[col])
        row["dominant_numeric_feature"] = str(profile["dominant_numeric_feature"])
        preserved = sum(1 for col in SOURCE_INFORMATION_COLUMNS if _is_present(row.get(col)))
        row["source_information_preserved_count"] = preserved
        row["source_information_required_count"] = len(SOURCE_INFORMATION_COLUMNS)
        row["source_information_preservation_status"] = (
            "all_required_source_information_preserved" if preserved == len(SOURCE_INFORMATION_COLUMNS)
            else "source_information_missing_review_required"
        )
        numeric_complete = sum(1 for col in SIMULATOR_NUMERIC_COLUMNS if pd.notna(row.get(col)))
        row["numeric_state_status"] = (
            "task22_simulator_numeric_state_ready" if numeric_complete == len(SIMULATOR_NUMERIC_COLUMNS)
            else "numeric_state_incomplete_review_required"
        )
        rows.append(row)
    return pd.DataFrame(rows, columns=STATE_COLUMNS)


def build_risk_sensing_state_quality(states: pd.DataFrame, config: OtV8RiskSensingStateConfig | None = None) -> pd.DataFrame:
    cfg = config or OtV8RiskSensingStateConfig()
    if states is None or states.empty:
        return pd.DataFrame(columns=QUALITY_COLUMNS)
    rows: list[dict[str, Any]] = []
    for _, state in states.iterrows():
        risk_name = str(state["risk_name"])
        target_name, target_value, supporting = _target_signal(risk_name, state)
        source_score = _source_preserved_count(state) / len(SOURCE_INFORMATION_COLUMNS)
        numeric_score = _numeric_complete_count(state) / len(SIMULATOR_NUMERIC_COLUMNS)
        alignment = _clip01(target_value)
        overall = _clip01(0.44 * alignment + 0.30 * source_score + 0.26 * numeric_score)
        ready = (
            source_score >= cfg.min_source_preservation_score
            and numeric_score >= cfg.min_numeric_completeness_score
            and alignment >= cfg.min_alignment_score
        )
        if ready:
            status = "risk_sensing_state_ready_for_task22_noop_simulator"
        elif source_score < cfg.min_source_preservation_score:
            status = "source_information_loss_detected"
        elif numeric_score < cfg.min_numeric_completeness_score:
            status = "numeric_state_incomplete"
        else:
            status = "risk_signal_alignment_needs_review"
        rows.append({
            "task2_8j_24c1_version": TASK2_8J_24C1_VERSION,
            "risk_sensing_state_id": str(state["risk_sensing_state_id"]),
            "risk_name": risk_name,
            "terrain_location_id": str(state["terrain_location_id"]),
            "target_signal_name": target_name,
            "target_signal_value": round(float(target_value), 6),
            "supporting_signal_summary": supporting,
            "risk_signal_alignment_score": round(alignment, 6),
            "source_information_preservation_score": round(source_score, 6),
            "simulator_numeric_completeness_score": round(numeric_score, 6),
            "overall_state_quality_score": round(overall, 6),
            "simulator_ready": bool(ready),
            "quality_status": status,
        })
    return pd.DataFrame(rows, columns=QUALITY_COLUMNS)


def build_final_summary(states: pd.DataFrame, quality: pd.DataFrame, input_packet_count: int) -> pd.DataFrame:
    risk_names = sorted(states["risk_name"].astype(str).unique()) if states is not None and not states.empty else []
    ready_count = int(quality["simulator_ready"].astype(bool).sum()) if quality is not None and not quality.empty else 0
    preserved_count = int((states["source_information_preservation_status"].astype(str) == "all_required_source_information_preserved").sum()) if states is not None and not states.empty else 0
    numeric_count = int((states["numeric_state_status"].astype(str) == "task22_simulator_numeric_state_ready").sum()) if states is not None and not states.empty else 0
    decision = (
        "ot_v8_risk_sensing_states_ready_for_task22_noop_simulator"
        if len(states) > 0 and ready_count == len(states) and preserved_count == len(states) and numeric_count == len(states)
        else "ot_v8_risk_sensing_states_need_review"
    )
    return pd.DataFrame([{
        "task2_8j_24c1_version": TASK2_8J_24C1_VERSION,
        "input_packet_count": int(input_packet_count),
        "risk_sensing_state_count": int(len(states)),
        "quality_row_count": int(len(quality)),
        "simulator_ready_state_count": ready_count,
        "source_information_preserved_state_count": preserved_count,
        "numeric_complete_state_count": numeric_count,
        "risk_names_carried": ",".join(risk_names),
        "task2_8j_24c1_decision": decision,
        "next_task": "Task 2-8j-24c2: feed generated risk-sensing states into existing NO_OP risk simulator",
    }], columns=SUMMARY_COLUMNS)


def validate_tables(states: pd.DataFrame, quality: pd.DataFrame, final_summary: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    if states is None or states.empty:
        errors.append("task2_8j_24c1_empty_states")
        return errors
    missing_state_cols = [c for c in STATE_COLUMNS if c not in states.columns]
    if missing_state_cols:
        errors.append("task2_8j_24c1_missing_state_columns:" + ",".join(missing_state_cols))
    missing_quality_cols = [c for c in QUALITY_COLUMNS if c not in quality.columns] if quality is not None else QUALITY_COLUMNS
    if missing_quality_cols:
        errors.append("task2_8j_24c1_missing_quality_columns:" + ",".join(missing_quality_cols))
    missing_summary_cols = [c for c in SUMMARY_COLUMNS if c not in final_summary.columns] if final_summary is not None else SUMMARY_COLUMNS
    if missing_summary_cols:
        errors.append("task2_8j_24c1_missing_summary_columns:" + ",".join(missing_summary_cols))
    for col in SOURCE_INFORMATION_COLUMNS:
        if col in states.columns and states[col].astype(str).str.strip().eq("").any():
            errors.append(f"task2_8j_24c1_source_information_lost:{col}")
    for col in SIMULATOR_NUMERIC_COLUMNS:
        if col in states.columns:
            if states[col].isna().any():
                errors.append(f"task2_8j_24c1_numeric_nan:{col}")
            if not states[col].astype(float).between(0.0, 1.0).all():
                errors.append(f"task2_8j_24c1_numeric_out_of_range:{col}")
    if "risk_name" in states.columns:
        expected = {"relation_lock", "oscillation", "reversibility_loss", "boundary_fragile", "resource_pressure"}
        observed = set(states["risk_name"].astype(str))
        if not expected.issubset(observed):
            errors.append("task2_8j_24c1_not_all_risk_information_carried")
    if quality is not None and not quality.empty and not bool(quality["simulator_ready"].astype(bool).all()):
        errors.append("task2_8j_24c1_quality_not_all_simulator_ready")
    if final_summary is not None and not final_summary.empty:
        decision = str(final_summary["task2_8j_24c1_decision"].iloc[0])
        if decision != "ot_v8_risk_sensing_states_ready_for_task22_noop_simulator":
            errors.append("task2_8j_24c1_final_decision_not_ready")
    return errors


def build_and_validate_ot_v8_risk_sensing_state(
    intake_packets: pd.DataFrame | None = None,
    config: OtV8RiskSensingStateConfig | None = None,
):
    packets = intake_packets if intake_packets is not None else build_actionmodule_information_intake_packets()
    states = build_ot_v8_risk_sensing_states(packets, config)
    quality = build_risk_sensing_state_quality(states, config)
    final_summary = build_final_summary(states, quality, len(packets) if packets is not None else 0)
    errors = validate_tables(states, quality, final_summary)
    summary = final_summary.iloc[0].to_dict() if not final_summary.empty else {}
    summary["validation_errors"] = errors
    return states, quality, final_summary, errors, summary
