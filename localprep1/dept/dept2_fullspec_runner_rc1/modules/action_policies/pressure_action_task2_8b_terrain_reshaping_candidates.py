"""Task 2-8b: minimal terrain reshaping candidate builder RC1.

This module creates terrain-reshaping candidates from prepared lower-risk
information, prepared v8-local evidence, upper-pressure modulation, and optional
exploration efficiency hints.

Boundary:
    - candidate generation only
    - no long-run validation
    - no ActionFrame creation
    - no ActionModule call
    - no world runtime
    - no canonical write
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd

from .pressure_action_task2_7b_insurance_closed_validation_v2 import (
    build_v2_risk_states,
    lower_observation_from_v2_risk_state,
    upper_pressure_from_lower_observation_v2,
)

TASK2_8B_VERSION = "terrain_reshaping_candidate_builder_rc1"
TASK2_8B_CONTRACT = (
    "Task2_8b_terrain_reshaping_candidates__candidate_only__lower_risk_plus_v8_local__"
    "upper_pressure_modulates_thresholds_not_direct_selection__no_ActionFrame"
)

TERRAIN_RESHAPING_ACTIONS = {
    "input_sensitivity_reduction": "入力感度低下作用",
    "amplification_loop_damping": "自己増幅遮断作用",
    "recovery_basin_formation": "回復谷形成作用",
}

REQUIRED_LOWER_RISK_COLUMNS = [
    "terrain_location_id",
    "risk_level",
    "risk_slope",
    "risk_acceleration",
    "input_sensitivity_score",
    "amplification_score",
    "peak_risk_estimate",
    "recovery_margin",
    "irreversibility_risk",
    "local_uncertainty",
]

REQUIRED_V8_COLUMNS = [
    "terrain_location_id",
    "local_pattern_type",
    "local_confidence",
    "local_uncertainty",
    "local_counter_evidence",
    "recommended_terrain_target",
    "requires_micro_audit",
]

REQUIRED_TASK2_8B_COLUMNS = [
    "task2_8b_version",
    "task2_8b_contract",
    "candidate_only",
    "validation_only",
    "runtime_policy_input",
    "action_frame_created",
    "actionmodule_called",
    "world_runtime_called",
    "canonical_write_performed",
    "terrain_location_id",
    "terrain_reshaping_action",
    "terrain_reshaping_action_ja",
    "terrain_target",
    "candidate_score",
    "activation_threshold_after_pressure",
    "candidate_status",
    "expected_slope_effect",
    "expected_peak_effect",
    "expected_recovery_effect",
    "expected_persistence_effect",
    "side_effect_estimate",
    "sandbox_required",
    "micro_audit_required",
    "lower_risk_basis",
    "v8_local_evidence_basis",
    "upper_pressure_modulation_basis",
    "exploration_efficiency_basis",
    "pressure_directly_selected_action",
    "raw_v8_access_performed",
]


@dataclass(frozen=True)
class TerrainReshapingCandidateConfig:
    base_activation_threshold: float = 0.58
    min_candidate_score: float = 0.30
    max_side_effect_estimate: float = 0.45


def _clip01(x: float) -> float:
    return float(max(0.0, min(1.0, float(x))))


def _num(row, key: str, default: float = 0.0) -> float:
    try:
        v = row.get(key, default)
        if pd.isna(v):
            return float(default)
        return float(v)
    except Exception:
        return float(default)


def _require_columns(df: pd.DataFrame, required: Iterable[str], name: str) -> None:
    missing = sorted(set(required) - set(df.columns))
    if missing:
        raise ValueError(f"{name}_required_columns_missing:" + ",".join(missing))


def build_demo_lower_risk_information() -> pd.DataFrame:
    terrain = lower_observation_from_v2_risk_state(build_v2_risk_states())
    rows = []
    for _, t in terrain.iterrows():
        risk_level = _clip01(0.22 * _num(t, "boundary_risk_score") + 0.22 * _num(t, "instability_score") + 0.20 * (1.0 - _num(t, "recovery_margin")) + 0.16 * _num(t, "trend_risk_score") + 0.12 * _num(t, "local_uncertainty_score") + 0.08 * max(_num(t, "ot_residual_score"), _num(t, "ot_unresolved_score"), _num(t, "ot_ambiguity_score")))
        risk_slope = _clip01(0.65 * _num(t, "trend_risk_score") + 0.35 * _num(t, "instability_score"))
        risk_acceleration = _clip01(0.55 * _num(t, "instability_score") + 0.45 * _num(t, "ot_unresolved_score"))
        input_sensitivity = _clip01(0.55 * _num(t, "boundary_risk_score") + 0.30 * _num(t, "local_uncertainty_score") + 0.15 * _num(t, "trend_risk_score"))
        amplification = _clip01(0.45 * risk_acceleration + 0.35 * _num(t, "trend_risk_score") + 0.20 * _num(t, "ot_residual_score"))
        peak = _clip01(0.50 * risk_level + 0.30 * risk_slope + 0.20 * amplification)
        recovery = _clip01(_num(t, "recovery_margin"))
        irreversibility = _clip01(0.60 * (1.0 - recovery) + 0.25 * peak + 0.15 * _num(t, "ot_unresolved_score"))
        rows.append({
            "terrain_location_id": str(t["terrain_location_id"]),
            "risk_level": risk_level,
            "risk_slope": risk_slope,
            "risk_acceleration": risk_acceleration,
            "input_sensitivity_score": input_sensitivity,
            "amplification_score": amplification,
            "peak_risk_estimate": peak,
            "recovery_margin": recovery,
            "irreversibility_risk": irreversibility,
            "local_uncertainty": _clip01(_num(t, "local_uncertainty_score")),
        })
    return pd.DataFrame(rows)


def build_demo_v8_local_evidence() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "terrain_location_id": "v2_boundary_instability_risk",
            "local_pattern_type": "boundary_instability",
            "local_confidence": 0.86,
            "local_uncertainty": 0.34,
            "local_counter_evidence": 0.12,
            "recommended_terrain_target": "sensitivity",
            "requires_micro_audit": True,
        },
        {
            "terrain_location_id": "v2_boundary_instability_risk",
            "local_pattern_type": "recursive_amplification",
            "local_confidence": 0.78,
            "local_uncertainty": 0.38,
            "local_counter_evidence": 0.18,
            "recommended_terrain_target": "amplification",
            "requires_micro_audit": True,
        },
        {
            "terrain_location_id": "v2_unresolved_medium_risk",
            "local_pattern_type": "unresolved_noise_cluster",
            "local_confidence": 0.62,
            "local_uncertainty": 0.58,
            "local_counter_evidence": 0.32,
            "recommended_terrain_target": "audit_first",
            "requires_micro_audit": True,
        },
        {
            "terrain_location_id": "v2_low_risk_gain_window",
            "local_pattern_type": "input_overreaction",
            "local_confidence": 0.64,
            "local_uncertainty": 0.24,
            "local_counter_evidence": 0.20,
            "recommended_terrain_target": "sensitivity",
            "requires_micro_audit": False,
        },
    ])


def build_demo_upper_pressure_modulation() -> pd.DataFrame:
    pressure = upper_pressure_from_lower_observation_v2(lower_observation_from_v2_risk_state(build_v2_risk_states()))
    rows = []
    for state_id, group in pressure.groupby("v2_state_id"):
        def strength(component: str, direction: str) -> float:
            m = group[(group["pressure_component"] == component) & (group["component_direction"] == direction)]
            return float(m["pressure_strength"].max()) / 10.0 if not m.empty else 0.0

        rollback_up = strength("rollback_sensitivity", "increase")
        cap_down = strength("pressure_cap", "decrease")
        diag_up = strength("diagnostic_depth", "increase")
        explore_up = strength("exploration_frequency", "increase")
        commit_down = strength("commitment_strength", "decrease")
        rows.append({
            "terrain_location_id": str(state_id),
            "activation_threshold_delta": -0.10 * rollback_up - 0.06 * commit_down,
            "strength_cap_delta": -0.12 * cap_down,
            "audit_requirement_delta": 0.12 * diag_up,
            "sandbox_rate_delta": 0.10 * explore_up,
            "adoption_hardening_delta": 0.04 * cap_down + 0.04 * diag_up,
            "pressure_summary": f"rollback_up={rollback_up:.3f}; cap_down={cap_down:.3f}; diagnostic_up={diag_up:.3f}; exploration_up={explore_up:.3f}; commitment_down={commit_down:.3f}",
        })
    return pd.DataFrame(rows)


def build_demo_exploration_efficiency_hints() -> pd.DataFrame:
    return pd.DataFrame([
        {"terrain_location_id": "v2_boundary_instability_risk", "terrain_target": "sensitivity", "efficiency_hint": 0.62, "side_effect_relief_hint": 0.42},
        {"terrain_location_id": "v2_boundary_instability_risk", "terrain_target": "amplification", "efficiency_hint": 0.70, "side_effect_relief_hint": 0.36},
        {"terrain_location_id": "v2_unresolved_medium_risk", "terrain_target": "recovery", "efficiency_hint": 0.44, "side_effect_relief_hint": 0.48},
        {"terrain_location_id": "v2_low_risk_gain_window", "terrain_target": "sensitivity", "efficiency_hint": 0.38, "side_effect_relief_hint": 0.55},
    ])


def _evidence_score(v8_rows: pd.DataFrame, patterns: set[str], targets: set[str]) -> tuple[float, str, bool]:
    if v8_rows.empty:
        return 0.0, "no_v8_local_evidence", True
    best = 0.0
    parts = []
    micro = False
    for _, e in v8_rows.iterrows():
        pattern_hit = 1.0 if str(e["local_pattern_type"]) in patterns else 0.0
        target_hit = 1.0 if str(e["recommended_terrain_target"]) in targets else 0.0
        raw = (0.55 * pattern_hit + 0.25 * target_hit + 0.20) * _num(e, "local_confidence") * (1.0 - 0.55 * _num(e, "local_counter_evidence"))
        raw = _clip01(raw)
        if raw > best:
            best = raw
        parts.append(f"{e['local_pattern_type']}:{raw:.3f}")
        micro = micro or bool(e.get("requires_micro_audit", False)) or _num(e, "local_uncertainty") > 0.50
    return best, "; ".join(parts), micro


def _efficiency_hint(eff: pd.DataFrame, terrain_location_id: str, target: str) -> tuple[float, str]:
    if eff is None or eff.empty:
        return 0.0, "no_exploration_efficiency_hint"
    m = eff[(eff["terrain_location_id"].astype(str) == terrain_location_id) & (eff["terrain_target"].astype(str) == target)]
    if m.empty:
        return 0.0, "no_matching_exploration_efficiency_hint"
    row = m.iloc[0]
    return _clip01(0.70 * _num(row, "efficiency_hint") + 0.30 * _num(row, "side_effect_relief_hint")), f"eff={_num(row, 'efficiency_hint'):.3f}; side_relief={_num(row, 'side_effect_relief_hint'):.3f}"


def _candidate_specs() -> list[dict]:
    return [
        {
            "action": "input_sensitivity_reduction",
            "target": "sensitivity",
            "patterns": {"input_overreaction", "boundary_instability"},
            "targets": {"sensitivity"},
            "risk_score": lambda r: _clip01(0.45 * _num(r, "input_sensitivity_score") + 0.25 * _num(r, "risk_slope") + 0.20 * _num(r, "peak_risk_estimate") + 0.10 * _num(r, "risk_level")),
            "effects": (0.30, 0.28, 0.10, 0.20, 0.18),
        },
        {
            "action": "amplification_loop_damping",
            "target": "amplification",
            "patterns": {"recursive_amplification", "oscillation", "recurrence"},
            "targets": {"amplification"},
            "risk_score": lambda r: _clip01(0.40 * _num(r, "amplification_score") + 0.30 * _num(r, "risk_acceleration") + 0.20 * _num(r, "peak_risk_estimate") + 0.10 * _num(r, "risk_slope")),
            "effects": (0.24, 0.34, 0.12, 0.24, 0.22),
        },
        {
            "action": "recovery_basin_formation",
            "target": "recovery",
            "patterns": {"recovery_failure", "regime_switch", "split_merge_return_failure"},
            "targets": {"recovery"},
            "risk_score": lambda r: _clip01(0.38 * (1.0 - _num(r, "recovery_margin")) + 0.32 * _num(r, "irreversibility_risk") + 0.20 * _num(r, "risk_level") + 0.10 * _num(r, "local_uncertainty")),
            "effects": (0.16, 0.18, 0.38, 0.32, 0.20),
        },
    ]


def build_terrain_reshaping_candidates(
    lower_risk_information: pd.DataFrame,
    v8_local_evidence: pd.DataFrame,
    upper_pressure_modulation: pd.DataFrame | None = None,
    exploration_efficiency_hints: pd.DataFrame | None = None,
    config: TerrainReshapingCandidateConfig = TerrainReshapingCandidateConfig(),
) -> pd.DataFrame:
    _require_columns(lower_risk_information, REQUIRED_LOWER_RISK_COLUMNS, "lower_risk_information")
    _require_columns(v8_local_evidence, REQUIRED_V8_COLUMNS, "v8_local_evidence")
    pressure = upper_pressure_modulation if upper_pressure_modulation is not None else pd.DataFrame()
    eff = exploration_efficiency_hints if exploration_efficiency_hints is not None else pd.DataFrame()
    rows = []
    for _, r in lower_risk_information.iterrows():
        loc = str(r["terrain_location_id"])
        v8_rows = v8_local_evidence[v8_local_evidence["terrain_location_id"].astype(str) == loc]
        p = pressure[pressure["terrain_location_id"].astype(str) == loc].iloc[0] if not pressure.empty and not pressure[pressure["terrain_location_id"].astype(str) == loc].empty else None
        threshold_delta = _num(p, "activation_threshold_delta") if p is not None else 0.0
        strength_cap_delta = _num(p, "strength_cap_delta") if p is not None else 0.0
        audit_delta = _num(p, "audit_requirement_delta") if p is not None else 0.0
        sandbox_delta = _num(p, "sandbox_rate_delta") if p is not None else 0.0
        adoption_delta = _num(p, "adoption_hardening_delta") if p is not None else 0.0
        pressure_basis = str(p.get("pressure_summary", "no_upper_pressure_modulation")) if p is not None else "no_upper_pressure_modulation"
        threshold = _clip01(config.base_activation_threshold + threshold_delta + adoption_delta)
        for spec in _candidate_specs():
            risk_basis = float(spec["risk_score"](r))
            evidence_score, evidence_basis, micro = _evidence_score(v8_rows, spec["patterns"], spec["targets"])
            efficiency, efficiency_basis = _efficiency_hint(eff, loc, spec["target"])
            score = _clip01(0.48 * risk_basis + 0.34 * evidence_score + 0.18 * efficiency)
            slope_eff, peak_eff, recovery_eff, persistence_eff, side_base = spec["effects"]
            side_est = _clip01(side_base * (1.0 - 0.35 * efficiency) + 0.08 * _num(r, "local_uncertainty") + 0.05 * abs(strength_cap_delta))
            status = "candidate_ready_for_sandbox" if score >= threshold and side_est <= config.max_side_effect_estimate else "candidate_shadow_or_hold"
            rows.append({
                "task2_8b_version": TASK2_8B_VERSION,
                "task2_8b_contract": TASK2_8B_CONTRACT,
                "candidate_only": True,
                "validation_only": True,
                "runtime_policy_input": False,
                "action_frame_created": False,
                "actionmodule_called": False,
                "world_runtime_called": False,
                "canonical_write_performed": False,
                "terrain_location_id": loc,
                "terrain_reshaping_action": spec["action"],
                "terrain_reshaping_action_ja": TERRAIN_RESHAPING_ACTIONS[spec["action"]],
                "terrain_target": spec["target"],
                "candidate_score": score,
                "activation_threshold_after_pressure": threshold,
                "candidate_status": status,
                "expected_slope_effect": _clip01(slope_eff * score),
                "expected_peak_effect": _clip01(peak_eff * score),
                "expected_recovery_effect": _clip01(recovery_eff * score),
                "expected_persistence_effect": _clip01(persistence_eff * score),
                "side_effect_estimate": side_est,
                "sandbox_required": True,
                "micro_audit_required": bool(micro or audit_delta > 0.05 or score < threshold),
                "lower_risk_basis": f"risk_basis={risk_basis:.3f}; risk_level={_num(r, 'risk_level'):.3f}; slope={_num(r, 'risk_slope'):.3f}; accel={_num(r, 'risk_acceleration'):.3f}; recovery={_num(r, 'recovery_margin'):.3f}",
                "v8_local_evidence_basis": evidence_basis,
                "upper_pressure_modulation_basis": pressure_basis,
                "exploration_efficiency_basis": efficiency_basis,
                "pressure_directly_selected_action": False,
                "raw_v8_access_performed": False,
            })
    out = pd.DataFrame(rows)
    if out.empty:
        return pd.DataFrame(columns=REQUIRED_TASK2_8B_COLUMNS)
    out = out.sort_values(["candidate_score", "expected_persistence_effect"], ascending=[False, False]).reset_index(drop=True)
    return out[REQUIRED_TASK2_8B_COLUMNS]


def build_and_validate_demo_terrain_reshaping_candidates() -> tuple[pd.DataFrame, list[str], dict]:
    table = build_terrain_reshaping_candidates(
        build_demo_lower_risk_information(),
        build_demo_v8_local_evidence(),
        build_demo_upper_pressure_modulation(),
        build_demo_exploration_efficiency_hints(),
    )
    errors = validate_terrain_reshaping_candidates(table)
    summary = summarize_terrain_reshaping_candidates(table)
    return table, errors, summary


def summarize_terrain_reshaping_candidates(table: pd.DataFrame) -> dict:
    if table is None or table.empty:
        return {"rows": 0}
    ready = table[table["candidate_status"] == "candidate_ready_for_sandbox"]
    return {
        "rows": int(len(table)),
        "terrain_locations": int(table["terrain_location_id"].nunique()),
        "candidate_actions": sorted(table["terrain_reshaping_action"].astype(str).unique().tolist()),
        "ready_for_sandbox_rows": int(len(ready)),
        "max_candidate_score": float(table["candidate_score"].max()),
        "mean_side_effect_estimate": float(table["side_effect_estimate"].mean()),
        "raw_v8_access_performed": bool(table["raw_v8_access_performed"].astype(bool).any()),
        "pressure_directly_selected_action": bool(table["pressure_directly_selected_action"].astype(bool).any()),
    }


def validate_terrain_reshaping_candidates(table: pd.DataFrame) -> list[str]:
    errors = []
    if table is None or table.empty:
        return ["task2_8b_candidate_table_empty"]
    missing = sorted(set(REQUIRED_TASK2_8B_COLUMNS) - set(table.columns))
    if missing:
        return ["task2_8b_required_columns_missing:" + ",".join(missing)]
    for field in ["runtime_policy_input", "action_frame_created", "actionmodule_called", "world_runtime_called", "canonical_write_performed", "pressure_directly_selected_action", "raw_v8_access_performed"]:
        if bool(table[field].astype(bool).any()):
            errors.append(f"task2_8b_forbidden_true:{field}")
    for field in ["candidate_only", "validation_only", "sandbox_required"]:
        if not bool(table[field].astype(bool).all()):
            errors.append(f"task2_8b_required_true_not_all:{field}")
    if set(table["terrain_reshaping_action"].astype(str)) != set(TERRAIN_RESHAPING_ACTIONS):
        errors.append("task2_8b_missing_minimal_three_actions")
    for col in ["candidate_score", "activation_threshold_after_pressure", "expected_slope_effect", "expected_peak_effect", "expected_recovery_effect", "expected_persistence_effect", "side_effect_estimate"]:
        vals = pd.to_numeric(table[col], errors="coerce")
        if bool(vals.isna().any() or (vals < 0.0).any() or (vals > 1.0).any()):
            errors.append(f"task2_8b_invalid_unit_score:{col}")
    if not bool((table["candidate_status"] == "candidate_ready_for_sandbox").any()):
        errors.append("task2_8b_no_candidate_ready_for_sandbox")
    if not bool(table["v8_local_evidence_basis"].astype(str).str.len().gt(0).all()):
        errors.append("task2_8b_missing_v8_evidence_basis")
    return errors
