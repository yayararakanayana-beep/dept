"""Task 2-6 confirmation: validity validation for the pressure-action converter.

This module validates structural and semantic-result behavior of
``convert_pressure_inputs_to_action_candidates`` before the converter is wired
into a downstream path.

Validation focus:
    - all 11 x 2 pressure intents are handled when evidence exists
    - direction semantics are preserved
    - pressure signal is monotonic with pressure strength
    - expected result is never boosted above pressure signal
    - pressure/result gap is preserved
    - unresolved pressure intent audit columns are present and active
    - pressure intent and validation-local action result point in the same direction
    - candidate rows remain candidates, not final actions
"""
from __future__ import annotations

import json

import pandas as pd

from .pressure_action_calibration_rc1 import (
    _pressure_alignment_for_effect,
    _probe_action_effect,
    _side_effect_burden,
    _synthetic_action_frame,
)
from .pressure_action_task2_5a_single_action_correspondence import build_single_action_to_pressure_correspondence_table
from .pressure_action_task2_6_converter_rc1 import convert_pressure_inputs_to_action_candidates


TASK2_6_VALIDITY_VERSION = "pressure_action_converter_validity_validation_rc1"
TASK2_6_VALIDITY_CONTRACT = (
    "Task2_6_validity_validation__converter_structure_and_result_consistency__"
    "no_strength_boost__no_actionframe__no_actionmodule_call"
)

VALIDATION_STRENGTHS = (1.0, 5.0, 10.0)
VALIDATION_STATE_CASES = (
    {
        "state_case_id": "stable_no_state_supplied",
        "state_axes": (),
        "state_level": "low",
        "state_band": "stable",
    },
    {
        "state_case_id": "high_opening_risk_state",
        "state_axes": ("exploration_deficit", "fixation_strength", "oscillation_strength", "buffer_scarcity"),
        "state_level": "high",
        "state_band": "high",
    },
)

REQUIRED_TASK2_6_VALIDITY_COLUMNS = [
    "task2_6_validity_version",
    "task2_6_validity_contract",
    "validation_type",
    "validation_only",
    "runtime_policy_input",
    "pressure_to_action_converter_created",
    "action_strength_correction_applied",
    "pressure_matching_boost_applied",
    "final_action_decision",
    "action_frame_created",
    "actionmodule_called",
    "world_runtime_called",
    "pressure_component",
    "component_direction",
    "semantic_effect",
    "intent_family",
    "suggested_control_route",
    "state_case_id",
    "strengths_tested_json",
    "candidate_rows_total",
    "candidate_actions_json",
    "candidate_actions_ja_json",
    "all_strengths_produced_candidates",
    "no_strength_boost_invariant_pass",
    "gap_preserved_invariant_pass",
    "monotonic_pressure_signal_pass",
    "direction_semantics_preserved",
    "unresolved_intent_audit_columns_present",
    "unresolved_intent_audit_active",
    "pressure_action_result_consistency_pass",
    "mean_result_alignment_score",
    "min_result_alignment_score",
    "max_result_alignment_score",
    "mean_result_side_effect_burden",
    "worst_result_consistency_note",
    "downstream_gate_review_rows",
    "blocked_or_deferred_rows",
    "min_pressure_intent_coverage_score",
    "min_action_vocabulary_fit_score",
    "max_pressure_result_gap",
    "validity_status",
    "validity_notes",
]


def _json_list(values: list[str]) -> str:
    return json.dumps(values, ensure_ascii=False)


def _clip_strength_for_validation(expected_result_signal: float) -> float:
    """Map converter signal to the small synthetic action-strength range.

    This is only for validation-local result probing.  It does not feed back into
    the converter and must not be interpreted as strength correction.
    """
    signal = max(float(expected_result_signal), 0.0)
    return float(max(0.015, min(0.24, 0.015 + 0.03 * signal)))


def _response_for_candidate(row: pd.Series, state_band: str) -> dict:
    strength = _clip_strength_for_validation(float(row.get("expected_result_signal", 0.0)))
    action = str(row["action_channel"])
    baseline = _probe_action_effect(_synthetic_action_frame(str(state_band), "no_op", 37, strength))
    effect = _probe_action_effect(_synthetic_action_frame(str(state_band), action, 37, strength))
    return {
        **effect,
        "delta_vs_no_op_exploration": float(effect["exploration_delta"] - baseline["exploration_delta"]),
        "delta_vs_no_op_reversibility": float(effect["reversibility_delta"] - baseline["reversibility_delta"]),
        "delta_vs_no_op_public_effect": float(effect["net_public_effect_score"] - baseline["net_public_effect_score"]),
        "delta_vs_no_op_hidden_effect": float(effect["net_hidden_effect_score"] - baseline["net_hidden_effect_score"]),
        "delta_vs_no_op_hidden_damage": float(effect["hidden_damage_delta"] - baseline["hidden_damage_delta"]),
        "delta_vs_no_op_fatigue": float(effect["fatigue_delta"] - baseline["fatigue_delta"]),
        "delta_vs_no_op_resource_inequality": float(effect["resource_inequality_delta"] - baseline["resource_inequality_delta"]),
        "delta_vs_no_op_reversibility_effect": float(effect["reversibility_delta"] - baseline["reversibility_delta"]),
        "delta_vs_no_op_cost": float(effect["action_cost_effect"] - baseline["action_cost_effect"]),
        "delta_vs_no_op_trust": float(effect["trust_delta"] - baseline["trust_delta"]),
    }


def _result_alignment_audit(out: pd.DataFrame, state_band: str) -> dict:
    alignments: list[float] = []
    burdens: list[float] = []
    notes: list[str] = []
    for _, row in out.iterrows():
        response = _response_for_candidate(row, state_band)
        alignment = float(_pressure_alignment_for_effect(str(row["semantic_effect"]), str(row["intent_family"]), pd.Series(response)))
        burden = float(_side_effect_burden(response))
        alignments.append(alignment)
        burdens.append(burden)
        if alignment <= 0.0:
            notes.append(
                f"{row['semantic_effect']} -> {row['action_name_ja']} は検証用結果で圧意図への正方向寄与が見えない"
            )
    if not alignments:
        return {
            "pressure_action_result_consistency_pass": False,
            "mean_result_alignment_score": 0.0,
            "min_result_alignment_score": 0.0,
            "max_result_alignment_score": 0.0,
            "mean_result_side_effect_burden": 0.0,
            "worst_result_consistency_note": "no candidate result alignment rows",
        }
    mean_alignment = float(sum(alignments) / len(alignments))
    min_alignment = float(min(alignments))
    max_alignment = float(max(alignments))
    mean_burden = float(sum(burdens) / len(burdens)) if burdens else 0.0
    # A candidate set is acceptable when at least one candidate clearly points in
    # the pressure-intended direction and the average is not completely zero.
    # This does not require the result magnitude to match the pressure magnitude.
    consistency_pass = bool(max_alignment > 0.0 and mean_alignment > 0.0)
    note = notes[0] if notes else "validation-local action result has nonzero alignment with pressure intent"
    return {
        "pressure_action_result_consistency_pass": consistency_pass,
        "mean_result_alignment_score": mean_alignment,
        "min_result_alignment_score": min_alignment,
        "max_result_alignment_score": max_alignment,
        "mean_result_side_effect_burden": mean_burden,
        "worst_result_consistency_note": note,
    }


def _pressure_pairs(correspondence: pd.DataFrame) -> pd.DataFrame:
    positive = correspondence[pd.to_numeric(correspondence["basic_alignment_score"], errors="coerce").fillna(0.0) > 0.0].copy()
    cols = ["pressure_component", "component_direction", "semantic_effect", "intent_family", "suggested_control_route"]
    return positive[cols].drop_duplicates().sort_values(["pressure_component", "component_direction"]).reset_index(drop=True)


def _inputs_for_pair(component: str, direction: str) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "pressure_input_id": f"validity_{component}_{direction}_{str(strength).replace('.', '_')}",
            "pressure_component": component,
            "component_direction": direction,
            "pressure_strength": float(strength),
        }
        for strength in VALIDATION_STRENGTHS
    ])


def _validate_pair_case(pair: pd.Series, state_case: dict, correspondence: pd.DataFrame) -> dict:
    component = str(pair["pressure_component"])
    direction = str(pair["component_direction"])
    out = convert_pressure_inputs_to_action_candidates(
        _inputs_for_pair(component, direction),
        state_axes=state_case["state_axes"],
        state_level=str(state_case["state_level"]),
        state_band=str(state_case["state_band"]),
        correspondence=correspondence,
    )

    if out.empty:
        return {
            "candidate_rows_total": 0,
            "candidate_actions_json": "[]",
            "candidate_actions_ja_json": "[]",
            "all_strengths_produced_candidates": False,
            "no_strength_boost_invariant_pass": False,
            "gap_preserved_invariant_pass": False,
            "monotonic_pressure_signal_pass": False,
            "direction_semantics_preserved": False,
            "unresolved_intent_audit_columns_present": False,
            "unresolved_intent_audit_active": False,
            "pressure_action_result_consistency_pass": False,
            "mean_result_alignment_score": 0.0,
            "min_result_alignment_score": 0.0,
            "max_result_alignment_score": 0.0,
            "mean_result_side_effect_burden": 0.0,
            "worst_result_consistency_note": "converter returned no candidates for this pressure pair/state case",
            "downstream_gate_review_rows": 0,
            "blocked_or_deferred_rows": 0,
            "min_pressure_intent_coverage_score": 0.0,
            "min_action_vocabulary_fit_score": 0.0,
            "max_pressure_result_gap": 0.0,
            "validity_status": "fail",
            "validity_notes": "converter returned no candidates for this pressure pair/state case",
        }

    produced_strengths = set(pd.to_numeric(out["pressure_strength"], errors="coerce").dropna().astype(float))
    all_strengths = set(float(s) for s in VALIDATION_STRENGTHS).issubset(produced_strengths)
    no_boost = bool(
        (out["action_strength_correction_applied"].astype(bool).sum() == 0)
        and (out["pressure_matching_boost_applied"].astype(bool).sum() == 0)
        and (out["strength_curve_applied"].astype(bool).sum() == 0)
        and (pd.to_numeric(out["expected_result_signal"], errors="coerce") <= pd.to_numeric(out["pressure_signal"], errors="coerce") + 1e-12).all()
    )
    gap = bool((pd.to_numeric(out["pressure_result_gap"], errors="coerce") > 0.0).any())

    monotonic_pass = True
    for action, group in out.groupby("action_channel"):
        means = group.groupby("pressure_strength")["pressure_signal"].max().sort_index()
        if not means.is_monotonic_increasing:
            monotonic_pass = False
            break

    direction_semantics = bool(
        out["component_direction"].astype(str).eq(direction).all()
        and out["semantic_effect"].astype(str).eq(str(pair["semantic_effect"])).all()
        and out["intent_family"].astype(str).eq(str(pair["intent_family"])).all()
    )
    audit_cols = [
        "pressure_intent_coverage_score",
        "action_vocabulary_fit_score",
        "action_granularity_insufficient_flag",
        "new_action_channel_candidate_flag",
        "unresolved_pressure_intent",
        "safety_fallback_used",
    ]
    audit_present = all(col in out.columns for col in audit_cols)
    audit_active = bool(
        audit_present
        and (
            out["action_granularity_insufficient_flag"].astype(bool).any()
            or out["new_action_channel_candidate_flag"].astype(bool).any()
            or out["safety_fallback_used"].astype(bool).any()
            or out["unresolved_pressure_intent"].astype(str).str.len().gt(0).any()
        )
    )
    result_audit = _result_alignment_audit(out, str(state_case["state_band"]))
    blocked_deferred = int(out["candidate_status"].astype(str).str.contains("blocked|deferred", regex=True).sum())
    gate_review = int(out["requires_downstream_gate_review"].astype(bool).sum())
    status = "pass" if all([
        all_strengths,
        no_boost,
        gap,
        monotonic_pass,
        direction_semantics,
        audit_present,
        bool(result_audit["pressure_action_result_consistency_pass"]),
    ]) else "fail"
    notes = []
    if not audit_active:
        notes.append("unresolved audit columns exist but no unresolved row surfaced in this pair/state case")
    if gate_review > 0:
        notes.append("downstream gate review required for some candidates")
    if blocked_deferred > 0:
        notes.append("blocked/deferred candidates surfaced as candidates only")
    if not bool(result_audit["pressure_action_result_consistency_pass"]):
        notes.append(str(result_audit["worst_result_consistency_note"])
        )
    if not notes:
        notes.append("converter invariants and result-consistency checks passed")

    return {
        "candidate_rows_total": int(len(out)),
        "candidate_actions_json": _json_list(sorted(out["action_channel"].astype(str).unique().tolist())),
        "candidate_actions_ja_json": _json_list(sorted(out["action_name_ja"].astype(str).unique().tolist())),
        "all_strengths_produced_candidates": bool(all_strengths),
        "no_strength_boost_invariant_pass": bool(no_boost),
        "gap_preserved_invariant_pass": bool(gap),
        "monotonic_pressure_signal_pass": bool(monotonic_pass),
        "direction_semantics_preserved": bool(direction_semantics),
        "unresolved_intent_audit_columns_present": bool(audit_present),
        "unresolved_intent_audit_active": bool(audit_active),
        **result_audit,
        "downstream_gate_review_rows": gate_review,
        "blocked_or_deferred_rows": blocked_deferred,
        "min_pressure_intent_coverage_score": float(pd.to_numeric(out["pressure_intent_coverage_score"], errors="coerce").min()) if audit_present else 0.0,
        "min_action_vocabulary_fit_score": float(pd.to_numeric(out["action_vocabulary_fit_score"], errors="coerce").min()) if audit_present else 0.0,
        "max_pressure_result_gap": float(pd.to_numeric(out["pressure_result_gap"], errors="coerce").max()),
        "validity_status": status,
        "validity_notes": " / ".join(notes),
    }


def build_pressure_action_converter_validity_validation_table(
    correspondence: pd.DataFrame | None = None,
) -> pd.DataFrame:
    corr = build_single_action_to_pressure_correspondence_table() if correspondence is None else correspondence.copy()
    if corr.empty:
        return pd.DataFrame(columns=REQUIRED_TASK2_6_VALIDITY_COLUMNS)
    pairs = _pressure_pairs(corr)
    rows: list[dict] = []
    for _, pair in pairs.iterrows():
        for state_case in VALIDATION_STATE_CASES:
            result = _validate_pair_case(pair, state_case, corr)
            rows.append({
                "task2_6_validity_version": TASK2_6_VALIDITY_VERSION,
                "task2_6_validity_contract": TASK2_6_VALIDITY_CONTRACT,
                "validation_type": "pressure_action_converter_validity_validation",
                "validation_only": True,
                "runtime_policy_input": False,
                "pressure_to_action_converter_created": True,
                "action_strength_correction_applied": False,
                "pressure_matching_boost_applied": False,
                "final_action_decision": False,
                "action_frame_created": False,
                "actionmodule_called": False,
                "world_runtime_called": False,
                "pressure_component": str(pair["pressure_component"]),
                "component_direction": str(pair["component_direction"]),
                "semantic_effect": str(pair["semantic_effect"]),
                "intent_family": str(pair["intent_family"]),
                "suggested_control_route": str(pair["suggested_control_route"]),
                "state_case_id": str(state_case["state_case_id"]),
                "strengths_tested_json": json.dumps(list(VALIDATION_STRENGTHS), ensure_ascii=False),
                **result,
            })
    out = pd.DataFrame(rows)
    return out[REQUIRED_TASK2_6_VALIDITY_COLUMNS]


def validate_pressure_action_converter_validity_validation_table(df: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    if df is None or df.empty:
        return ["task2_6_validity_table_empty"]
    missing = sorted(set(REQUIRED_TASK2_6_VALIDITY_COLUMNS) - set(df.columns))
    if missing:
        errors.append("task2_6_validity_required_columns_missing:" + ",".join(missing))
        return errors

    false_fields = [
        "runtime_policy_input",
        "action_strength_correction_applied",
        "pressure_matching_boost_applied",
        "final_action_decision",
        "action_frame_created",
        "actionmodule_called",
        "world_runtime_called",
    ]
    for field in false_fields:
        if bool(df[field].astype(bool).any()):
            errors.append(f"task2_6_validity_forbidden_true_field:{field}")

    required_true = [
        "validation_only",
        "pressure_to_action_converter_created",
        "all_strengths_produced_candidates",
        "no_strength_boost_invariant_pass",
        "gap_preserved_invariant_pass",
        "monotonic_pressure_signal_pass",
        "direction_semantics_preserved",
        "unresolved_intent_audit_columns_present",
        "pressure_action_result_consistency_pass",
    ]
    for field in required_true:
        if not bool(df[field].astype(bool).all()):
            errors.append(f"task2_6_validity_required_true_field_not_all_true:{field}")

    if bool((df["validity_status"].astype(str) != "pass").any()):
        errors.append("task2_6_validity_status_contains_fail")

    pair_count = df[["pressure_component", "component_direction"]].drop_duplicates().shape[0]
    if pair_count < 22:
        errors.append(f"task2_6_validity_pressure_pair_count_too_low:{pair_count}")

    for col in [
        "min_pressure_intent_coverage_score",
        "min_action_vocabulary_fit_score",
        "mean_result_alignment_score",
        "min_result_alignment_score",
        "max_result_alignment_score",
    ]:
        vals = pd.to_numeric(df[col], errors="coerce")
        if bool(vals.isna().any() or (vals < 0.0).any()):
            errors.append(f"task2_6_validity_invalid_nonnegative_score:{col}")
        if col in {"min_pressure_intent_coverage_score", "min_action_vocabulary_fit_score"} and bool((vals > 1.0).any()):
            errors.append(f"task2_6_validity_invalid_unit_score:{col}")

    if not bool(df["unresolved_intent_audit_active"].astype(bool).any()):
        errors.append("task2_6_validity_no_unresolved_intent_audit_active_rows")
    if not bool(pd.to_numeric(df["downstream_gate_review_rows"], errors="coerce").fillna(0).gt(0).any()):
        errors.append("task2_6_validity_no_downstream_gate_review_rows")
    if not bool(pd.to_numeric(df["mean_result_alignment_score"], errors="coerce").fillna(0).gt(0).all()):
        errors.append("task2_6_validity_result_alignment_not_positive_for_all_rows")

    return errors


def build_and_validate_pressure_action_converter_validity_validation_table() -> tuple[pd.DataFrame, list[str]]:
    df = build_pressure_action_converter_validity_validation_table()
    return df, validate_pressure_action_converter_validity_validation_table(df)
