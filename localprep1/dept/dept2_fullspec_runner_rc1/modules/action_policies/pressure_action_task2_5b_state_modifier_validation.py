"""Task 2-5b: state modifier validation for pressure-action conversion.

Task: ActionModule UpperPressure Reception Split RC1 / Task 2-5b.

This module does not detect state from the lower layer and does not build the
pressure-to-action conversion function.  It creates a validation table that says
which lower-layer state axes should modify which action candidates once those
state signals are connected later.

Boundary:
    - builds a state-label input window for later lower-layer connection
    - summarizes which state axes boost/dampen/defer/block each action channel
    - uses Task 2-4/2-5a validation evidence only as review evidence
    - does not create final actions
    - does not create ActionFrame
    - does not call ActionPlanner, ActionModule, or world runtime
    - does not infer live lower-layer state
    - marks output as validation evidence, not runtime policy input
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd

from .pressure_action_task2_5a_single_action_correspondence import ACTION_CHANNEL_JA
from .pressure_action_validation_suite_rc1 import (
    build_single_action_pressure_alignment_validation,
    summarize_state_dependence,
)


TASK2_5B_VERSION = "state_modifier_validation_for_pressure_action_conversion_rc1"
TASK2_5B_MAPPING_SOURCE = "task2_4_state_band_evidence_plus_task2_5b_state_axis_contract"
TASK2_5B_CALIBRATION_STATUS = "task2_5b_state_modifier_validation_evidence"
TASK2_5B_CONTRACT = (
    "state_modifier_validation__lower_layer_connection_window_only__"
    "no_state_detector__not_pressure_to_action_converter__not_runtime_policy_input__Task2_5b_RC1"
)

STATE_LEVELS = ("low", "medium", "high", "limit")
STATE_LEVEL_JA = {
    "low": "低い",
    "medium": "中くらい",
    "high": "高い",
    "limit": "限界",
}

OPENING_ACTIONS = {"exploration_injection", "relation_unlock", "coupling_relief"}
SAFETY_ACTIONS = {"buffer_increase", "volatility_damping"}
PROBE_ACTIONS = {"uncertainty_probe"}


@dataclass(frozen=True)
class StateAxisSpec:
    state_axis: str
    state_axis_ja: str
    required_lower_layer_signal: str
    expected_source_layer: str
    expected_source_artifact: str
    missing_signal_behavior: str


STATE_AXIS_SPECS: tuple[StateAxisSpec, ...] = (
    StateAxisSpec(
        "oscillation_strength",
        "揺れの強さ",
        "oscillation_score / volatility_score / trajectory_curvature",
        "O_t / local audit / trajectory diagnostics",
        "O_t action view, local audit row, trajectory summary",
        "conservative_default__dampen_opening_actions_keep_safety_actions",
    ),
    StateAxisSpec(
        "buffer_scarcity",
        "余裕の少なさ",
        "buffer_margin / rollback_capacity / action_budget_margin",
        "shadow parameter box / buffer audit / action local audit",
        "shadow parameter state, local audit, residual/noise log",
        "conservative_default__boost_buffer_and_damping_dampen_unlocking",
    ),
    StateAxisSpec(
        "fixation_strength",
        "固定の強さ",
        "relation_lock_score / hysteresis_score / commitment_score",
        "O_t lineage graph / parameter box / local audit",
        "lineage graph, parameter shadow box, action local audit",
        "conservative_default__allow_mild_relief_but_require_buffer_check",
    ),
    StateAxisSpec(
        "exploration_excess",
        "探索過多",
        "exploration_rate / candidate_count / sandbox_load",
        "exploration module / sandbox audit / candidate registry",
        "exploration sidecar, sandbox report, candidate table",
        "conservative_default__dampen_exploration_and_probe",
    ),
    StateAxisSpec(
        "exploration_deficit",
        "探索不足",
        "coverage_gap / novelty_deficit / unresolved_gap",
        "O_t residual view / exploration module / coverage audit",
        "coverage audit, unresolved register, exploration sidecar",
        "conservative_default__mildly_allow_exploration_keep_safety_gate",
    ),
    StateAxisSpec(
        "uncertainty_level",
        "不確実性の高さ",
        "ambiguity_score / confidence_gap / identity_unresolved_rate",
        "O_t posterior / calibration layer / local audit",
        "calibrated posterior table, local audit, unresolved flags",
        "conservative_default__boost_probe_buffer_damping",
    ),
    StateAxisSpec(
        "residual_level",
        "残差の大きさ",
        "residual_score / unexplained_error / noise_residual_mass",
        "O_t residual log / noise log / local audit",
        "residual log, noise register, local audit row",
        "conservative_default__probe_before_strong_action",
    ),
    StateAxisSpec(
        "relation_congestion",
        "関係の詰まり",
        "relation_bottleneck_score / graph_congestion / route_lock_score",
        "O_t graph view / lineage graph / action surface audit",
        "lineage graph, relation audit, action surface planning audit",
        "conservative_default__allow_relief_but_dampen_unlock_without_buffer",
    ),
    StateAxisSpec(
        "hidden_damage_suspicion",
        "隠れ損傷の疑い",
        "hidden_damage_score / fatigue_score / resource_inequality_delta",
        "v2 action-effect trace / local audit / residual log",
        "v2_action_effect_trace, local audit, residual/noise log",
        "conservative_default__dampen_opening_actions_boost_safety_actions",
    ),
    StateAxisSpec(
        "recoverability_level",
        "巻き戻し可能性",
        "rollback_margin / reversibility_score / recovery_capacity",
        "rollback guard / buffer audit / local audit",
        "rollback guard audit, buffer state, action local audit",
        "conservative_default__if_unknown_treat_as_low_recoverability",
    ),
)

REQUIRED_TASK2_5B_COLUMNS = [
    "task2_5b_version",
    "task2_5b_contract",
    "validation_type",
    "validation_only",
    "runtime_policy_input",
    "state_detector_created",
    "lower_layer_state_connected",
    "pressure_to_action_converter_created",
    "final_action_decision",
    "action_frame_created",
    "actionmodule_called",
    "mapping_source",
    "calibration_status",
    "state_axis",
    "state_axis_ja",
    "state_level",
    "state_level_ja",
    "action_channel",
    "action_name_ja",
    "state_modifier",
    "modifier_class",
    "boost_flag",
    "dampen_flag",
    "defer_flag",
    "block_flag",
    "modifier_reason",
    "empirical_state_dependence_status",
    "empirical_relative_alignment_spread",
    "empirical_high_limit_alignment_ratio",
    "empirical_high_limit_side_effect_burden",
    "required_lower_layer_signal",
    "expected_source_layer",
    "expected_source_artifact",
    "lower_layer_connection_status",
    "missing_signal_behavior",
    "conservative_default_used_when_missing",
    "requires_task2_5c_interaction_review",
    "uses_existing_pressure_intent_semantics",
    "new_semantic_translation_layer_added",
    "diagnostic_compat_policy_used",
    "repaired_diagnostic_policy_used",
]


def _empirical_action_evidence(alignment_validation: pd.DataFrame | None = None) -> pd.DataFrame:
    alignment = (
        build_single_action_pressure_alignment_validation()
        if alignment_validation is None
        else alignment_validation.copy()
    )
    if alignment.empty:
        return pd.DataFrame()

    work = alignment.copy()
    work["_score"] = pd.to_numeric(work["pressure_alignment_score"], errors="coerce").fillna(0.0)
    work["_side"] = pd.to_numeric(work["side_effect_burden_score"], errors="coerce").fillna(0.0)

    by_band = (
        work.groupby(["action_channel", "scenario_or_state_band"], dropna=False)
        .agg(
            mean_alignment=("_score", "mean"),
            mean_side_effect=("_side", "mean"),
            sample_count=("_score", "count"),
        )
        .reset_index()
    )

    dep = summarize_state_dependence(alignment)
    if dep.empty:
        dep_summary = pd.DataFrame(columns=["action_channel", "state_dependence_status", "relative_pressure_alignment_spread"])
    else:
        dep_summary = (
            dep.groupby("action_channel", dropna=False)
            .agg(
                state_dependent_rows=("state_dependence_status", lambda s: int((s.astype(str) == "state_dependent").sum())),
                total_rows=("state_dependence_status", "count"),
                max_relative_spread=("relative_pressure_alignment_spread", "max"),
            )
            .reset_index()
        )
        dep_summary["state_dependence_status"] = dep_summary.apply(
            lambda r: "state_dependent" if int(r["state_dependent_rows"]) > 0 else "approximately_state_independent",
            axis=1,
        )
        dep_summary["relative_pressure_alignment_spread"] = pd.to_numeric(
            dep_summary["max_relative_spread"], errors="coerce"
        ).fillna(0.0)

    rows: list[dict] = []
    for action, group in by_band.groupby("action_channel", dropna=False):
        action = str(action)
        stable = group[group["scenario_or_state_band"].astype(str) == "stable"]
        high_limit = group[group["scenario_or_state_band"].astype(str).isin(["high", "limit"])]
        stable_score = float(stable["mean_alignment"].mean()) if not stable.empty else 0.0
        high_limit_score = float(high_limit["mean_alignment"].mean()) if not high_limit.empty else 0.0
        high_limit_side = float(high_limit["mean_side_effect"].mean()) if not high_limit.empty else 0.0
        ratio = high_limit_score / max(stable_score, 1e-9)
        dep_row = dep_summary[dep_summary["action_channel"].astype(str) == action]
        rows.append({
            "action_channel": action,
            "empirical_state_dependence_status": (
                str(dep_row["state_dependence_status"].iloc[0]) if not dep_row.empty else "not_evaluated"
            ),
            "empirical_relative_alignment_spread": (
                float(dep_row["relative_pressure_alignment_spread"].iloc[0]) if not dep_row.empty else 0.0
            ),
            "empirical_high_limit_alignment_ratio": float(ratio),
            "empirical_high_limit_side_effect_burden": float(high_limit_side),
        })
    return pd.DataFrame(rows)


def _class_from_modifier(modifier: float) -> str:
    if modifier <= 0.0:
        return "block"
    if modifier <= 0.35:
        return "defer"
    if modifier < 0.90:
        return "dampen"
    if modifier > 1.10:
        return "boost"
    return "keep"


def _modifier(axis: str, level: str, action: str) -> tuple[float, str]:
    if level == "low":
        if axis == "recoverability_level" and action in OPENING_ACTIONS:
            return 0.35, "巻き戻し可能性が低い場合、解除・探索・緩和系は延期寄りにする。"
        return 1.00, "状態影響が低いため、基本対応を維持する。"

    severity = {"medium": 0.5, "high": 0.8, "limit": 1.0}[level]

    if axis == "oscillation_strength":
        if action in OPENING_ACTIONS:
            return max(0.0, 1.0 - 0.75 * severity), "揺れが強いほど、探索・解除・緩和系は発散リスクを避けるため弱める。"
        if action in SAFETY_ACTIONS:
            return 1.0 + 0.35 * severity, "揺れが強いほど、余裕確保・揺れ抑制を安全側候補として強める。"
        return 1.0 + 0.15 * severity, "揺れが強い場合は、まず不確実性を探る方向を少し強める。"

    if axis == "buffer_scarcity":
        if action in OPENING_ACTIONS:
            return max(0.0, 1.0 - 0.85 * severity), "余裕が少ないほど、失敗時に戻しにくい解除・探索・緩和系を弱める。"
        if action in SAFETY_ACTIONS:
            return 1.0 + 0.40 * severity, "余裕が少ないほど、余裕枠増加・揺れ抑制を強める。"
        return 1.0 + 0.10 * severity, "余裕が少ない場合は、大きく動かず確認する作用を少し強める。"

    if axis == "fixation_strength":
        if action in {"coupling_relief", "relation_unlock"}:
            return 1.0 + 0.35 * severity, "固定が強いほど、結合緩和・関係固定解除の候補価値は上がる。"
        if action == "exploration_injection":
            return 1.0 + 0.20 * severity, "固定が強い場合、探索を増やす作用も停滞崩しとして少し強める。"
        if action in SAFETY_ACTIONS:
            return 0.95, "固定が強いだけなら安全側作用は維持するが、解除候補より優先しすぎない。"
        return 1.0, "固定が強い場合、不確実性確認は維持する。"

    if axis == "exploration_excess":
        if action == "exploration_injection":
            return max(0.0, 1.0 - 0.90 * severity), "探索過多では探索を増やす作用を強く弱める。"
        if action == "uncertainty_probe":
            return max(0.25, 1.0 - 0.45 * severity), "探索過多では探査も増やしすぎないよう弱める。"
        if action in SAFETY_ACTIONS:
            return 1.0 + 0.25 * severity, "探索過多では余裕確保・揺れ抑制を強める。"
        return max(0.60, 1.0 - 0.25 * severity), "探索過多では開口系もやや弱める。"

    if axis == "exploration_deficit":
        if action == "exploration_injection":
            return 1.0 + 0.45 * severity, "探索不足では探索を増やす作用を強める。"
        if action == "uncertainty_probe":
            return 1.0 + 0.25 * severity, "探索不足では不確実性を探る作用も補助的に強める。"
        if action == "coupling_relief":
            return 1.0 + 0.18 * severity, "探索不足が固定由来なら結合緩和を少し強める。"
        if action in SAFETY_ACTIONS:
            return 0.95, "探索不足だけなら安全側作用を過剰優先しない。"
        return 1.0, "探索不足ではこの作用は基本維持する。"

    if axis == "uncertainty_level":
        if action == "uncertainty_probe":
            return 1.0 + 0.45 * severity, "不確実性が高いほど、まず不確実性を探る作用を強める。"
        if action in SAFETY_ACTIONS:
            return 1.0 + 0.25 * severity, "不確実性が高いほど、余裕確保・揺れ抑制も強める。"
        if action in OPENING_ACTIONS:
            return max(0.20, 1.0 - 0.60 * severity), "不確実性が高い場合、大きく開く作用は弱める。"
        return 1.0, "不確実性が高い場合でもこの作用は維持する。"

    if axis == "residual_level":
        if action == "uncertainty_probe":
            return 1.0 + 0.40 * severity, "残差が大きいほど、まず不確実性を探る作用を強める。"
        if action == "buffer_increase":
            return 1.0 + 0.30 * severity, "残差が大きい場合、余裕を確保してから作用する。"
        if action == "exploration_injection":
            return 1.0 + 0.10 * severity, "残差が探索不足由来なら探索も少し残す。"
        if action == "relation_unlock":
            return max(0.25, 1.0 - 0.55 * severity), "残差が大きいだけでは関係固定解除を強く打たない。"
        return 1.0, "残差が大きい場合でもこの作用は基本維持する。"

    if axis == "relation_congestion":
        if action == "coupling_relief":
            return 1.0 + 0.40 * severity, "関係の詰まりが強いほど、結合を緩める作用を強める。"
        if action == "relation_unlock":
            return 1.0 + 0.22 * severity, "関係の詰まりが強い場合、関係固定解除も候補に残すが補正確認を要する。"
        if action == "uncertainty_probe":
            return 1.0 + 0.15 * severity, "関係詰まりの原因確認として不確実性探査を少し強める。"
        if action == "exploration_injection":
            return 0.90, "関係詰まりでは探索注入だけで解かず、緩和・確認を優先する。"
        return 1.0, "関係詰まりではこの作用は維持する。"

    if axis == "hidden_damage_suspicion":
        if action in OPENING_ACTIONS:
            return max(0.0, 1.0 - 0.80 * severity), "隠れ損傷の疑いが強いほど、探索・解除・緩和系を弱める。"
        if action in SAFETY_ACTIONS:
            return 1.0 + 0.40 * severity, "隠れ損傷の疑いが強いほど、余裕確保・揺れ抑制を強める。"
        return 1.0 + 0.20 * severity, "隠れ損傷が疑われる場合、確認作用を強める。"

    if axis == "recoverability_level":
        if level in {"medium", "high", "limit"}:
            # Here higher level means more recoverability, not more risk.
            recovery_boost = {"medium": 0.0, "high": 0.12, "limit": 0.20}[level]
            if action in OPENING_ACTIONS:
                return 1.0 + recovery_boost, "巻き戻し可能性が高いほど、解除・探索・緩和系を候補に残しやすい。"
            if action in SAFETY_ACTIONS:
                return 1.0, "巻き戻し可能性が高い場合でも安全側作用は維持する。"
            return 1.0, "巻き戻し可能性が高い場合でも確認作用は維持する。"

    return 1.0, "未分類の状態影響のため、基本対応を維持する。"


def build_state_modifier_validation_table(
    alignment_validation: pd.DataFrame | None = None,
    state_axes: Iterable[StateAxisSpec] = STATE_AXIS_SPECS,
    state_levels: Iterable[str] = STATE_LEVELS,
) -> pd.DataFrame:
    """Build the Task 2-5b state modifier validation table.

    The result is a validation contract, not a live state detector.  It defines
    how future lower-layer state labels should modify candidate actions.
    """
    evidence = _empirical_action_evidence(alignment_validation)
    if evidence.empty:
        actions = sorted(ACTION_CHANNEL_JA)
    else:
        actions = sorted(evidence["action_channel"].astype(str).unique())

    rows: list[dict] = []
    for spec in state_axes:
        for level in state_levels:
            level = str(level)
            if level not in STATE_LEVELS:
                continue
            for action in actions:
                modifier, reason = _modifier(spec.state_axis, level, action)
                modifier_class = _class_from_modifier(float(modifier))
                ev = evidence[evidence["action_channel"].astype(str) == action]
                rows.append({
                    "task2_5b_version": TASK2_5B_VERSION,
                    "task2_5b_contract": TASK2_5B_CONTRACT,
                    "validation_type": "state_modifier_validation",
                    "validation_only": True,
                    "runtime_policy_input": False,
                    "state_detector_created": False,
                    "lower_layer_state_connected": False,
                    "pressure_to_action_converter_created": False,
                    "final_action_decision": False,
                    "action_frame_created": False,
                    "actionmodule_called": False,
                    "mapping_source": TASK2_5B_MAPPING_SOURCE,
                    "calibration_status": TASK2_5B_CALIBRATION_STATUS,
                    "state_axis": spec.state_axis,
                    "state_axis_ja": spec.state_axis_ja,
                    "state_level": level,
                    "state_level_ja": STATE_LEVEL_JA[level],
                    "action_channel": action,
                    "action_name_ja": ACTION_CHANNEL_JA.get(action, action),
                    "state_modifier": float(modifier),
                    "modifier_class": modifier_class,
                    "boost_flag": modifier_class == "boost",
                    "dampen_flag": modifier_class == "dampen",
                    "defer_flag": modifier_class == "defer",
                    "block_flag": modifier_class == "block",
                    "modifier_reason": reason,
                    "empirical_state_dependence_status": (
                        str(ev["empirical_state_dependence_status"].iloc[0]) if not ev.empty else "not_evaluated"
                    ),
                    "empirical_relative_alignment_spread": (
                        float(ev["empirical_relative_alignment_spread"].iloc[0]) if not ev.empty else 0.0
                    ),
                    "empirical_high_limit_alignment_ratio": (
                        float(ev["empirical_high_limit_alignment_ratio"].iloc[0]) if not ev.empty else 0.0
                    ),
                    "empirical_high_limit_side_effect_burden": (
                        float(ev["empirical_high_limit_side_effect_burden"].iloc[0]) if not ev.empty else 0.0
                    ),
                    "required_lower_layer_signal": spec.required_lower_layer_signal,
                    "expected_source_layer": spec.expected_source_layer,
                    "expected_source_artifact": spec.expected_source_artifact,
                    "lower_layer_connection_status": "placeholder_until_lower_layer_connection",
                    "missing_signal_behavior": spec.missing_signal_behavior,
                    "conservative_default_used_when_missing": True,
                    "requires_task2_5c_interaction_review": action in OPENING_ACTIONS or action in SAFETY_ACTIONS or action in PROBE_ACTIONS,
                    "uses_existing_pressure_intent_semantics": True,
                    "new_semantic_translation_layer_added": False,
                    "diagnostic_compat_policy_used": False,
                    "repaired_diagnostic_policy_used": False,
                })
    out = pd.DataFrame(rows)
    return out[REQUIRED_TASK2_5B_COLUMNS]


def validate_state_modifier_validation_table(df: pd.DataFrame) -> list[str]:
    """Return validation errors for the Task 2-5b table."""
    errors: list[str] = []
    if df is None or df.empty:
        return ["task2_5b_state_modifier_table_empty"]
    missing = sorted(set(REQUIRED_TASK2_5B_COLUMNS) - set(df.columns))
    if missing:
        errors.append(f"task2_5b_required_columns_missing:{','.join(missing)}")
        return errors

    false_fields = [
        "runtime_policy_input",
        "state_detector_created",
        "lower_layer_state_connected",
        "pressure_to_action_converter_created",
        "final_action_decision",
        "action_frame_created",
        "actionmodule_called",
        "new_semantic_translation_layer_added",
        "diagnostic_compat_policy_used",
        "repaired_diagnostic_policy_used",
    ]
    for field in false_fields:
        if bool(df[field].astype(bool).any()):
            errors.append(f"task2_5b_forbidden_true_field:{field}")

    if not bool(df["validation_only"].astype(bool).all()):
        errors.append("task2_5b_not_all_validation_only")
    if not bool(df["uses_existing_pressure_intent_semantics"].astype(bool).all()):
        errors.append("task2_5b_pressure_intent_semantics_not_preserved")

    modifiers = pd.to_numeric(df["state_modifier"], errors="coerce")
    if bool(modifiers.isna().any() or (modifiers < 0.0).any() or (modifiers > 1.5).any()):
        errors.append("task2_5b_state_modifier_out_of_bounds")

    allowed_classes = {"boost", "keep", "dampen", "defer", "block"}
    if not set(df["modifier_class"].astype(str)).issubset(allowed_classes):
        errors.append("task2_5b_unknown_modifier_class")

    expected_axes = {spec.state_axis for spec in STATE_AXIS_SPECS}
    observed_axes = set(df["state_axis"].astype(str))
    if expected_axes - observed_axes:
        errors.append("task2_5b_state_axes_missing:" + ",".join(sorted(expected_axes - observed_axes)))

    if bool(df["required_lower_layer_signal"].astype(str).str.len().eq(0).any()):
        errors.append("task2_5b_missing_required_lower_layer_signal")
    if bool(df["expected_source_layer"].astype(str).str.len().eq(0).any()):
        errors.append("task2_5b_missing_expected_source_layer")
    if bool(df["missing_signal_behavior"].astype(str).str.len().eq(0).any()):
        errors.append("task2_5b_missing_signal_behavior_empty")

    # There must be at least one real boost, dampen, and defer/block rule, or the
    # table is not informative enough for later conversion design.
    classes = set(df["modifier_class"].astype(str))
    if "boost" not in classes:
        errors.append("task2_5b_no_boost_rules")
    if "dampen" not in classes:
        errors.append("task2_5b_no_dampen_rules")
    if not ({"defer", "block"} & classes):
        errors.append("task2_5b_no_defer_or_block_rules")

    return errors


def build_and_validate_state_modifier_validation_table() -> tuple[pd.DataFrame, list[str]]:
    df = build_state_modifier_validation_table()
    return df, validate_state_modifier_validation_table(df)
