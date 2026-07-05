"""Task 2-5d: mixed-pressure input validation.

Task: ActionModule UpperPressure Reception Split RC1 / Task 2-5d.

This module validates what happens when multiple pressure intents are presented
together.  It uses validation-local projection to inspect candidate action sets,
conflicts, overcrowding, and unsafe interactions.  It does not create the final
pressure-to-action conversion function.

Boundary:
    - validates pressure-mix -> candidate-action-set behavior
    - uses Task 2-5a/2-5b/2-5c tables as validation evidence
    - does not build the runtime pressure-to-action converter
    - does not create final actions
    - does not create ActionFrame
    - does not call ActionPlanner, ActionModule, or world runtime
    - marks output as validation evidence, not runtime policy input
"""
from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
import json

import pandas as pd

from .pressure_action_task2_5a_single_action_correspondence import (
    ACTION_CHANNEL_JA,
    PRESSURE_COMPONENT_JA,
    build_single_action_to_pressure_correspondence_table,
)
from .pressure_action_task2_5b_state_modifier_validation import build_state_modifier_validation_table
from .pressure_action_task2_5c_interaction_modifier_validation import build_interaction_modifier_validation_table


TASK2_5D_VERSION = "mixed_pressure_input_validation_rc1"
TASK2_5D_MAPPING_SOURCE = "task2_5a_5b_5c_validation_projection_only"
TASK2_5D_CALIBRATION_STATUS = "task2_5d_mixed_pressure_validation_evidence"
TASK2_5D_CONTRACT = (
    "mixed_pressure_input_validation__candidate_set_audit_only__"
    "not_pressure_to_action_converter__not_runtime_policy_input__Task2_5d_RC1"
)

STATE_BANDS = ("stable", "medium", "high", "limit")
STATE_TO_LEVEL = {"stable": "low", "medium": "medium", "high": "high", "limit": "limit"}
STATE_BAND_JA = {"stable": "通常", "medium": "中負荷", "high": "高負荷", "limit": "限界"}

# This is deliberately an audit threshold, not a runtime adoption threshold.
# Task 2-5d must surface weak but dangerous candidates such as relation-unlock
# tails in mixed pressure inputs, because Task 2-5c interaction rules can make
# those tails important even when they are not the strongest candidate.
CANDIDATE_THRESHOLD = 0.018
TARGET_CANDIDATE_COUNT = 3

OPENING_ACTIONS = {"exploration_injection", "relation_unlock", "coupling_relief"}
SAFETY_ACTIONS = {"buffer_increase", "volatility_damping"}
PROBE_ACTIONS = {"uncertainty_probe"}

OPENING_FAMILIES = {
    "exploration_attempt",
    "exploration_observation",
    "adoption_opening",
    "response_opening",
    "temporal_opening",
    "update_opening",
    "switching_flexibility",
    "commitment_relief",
    "capacity_opening",
}
SAFETY_FAMILIES = {
    "safety_guard",
    "safety_cap",
    "persistence_guard",
    "commitment_guard",
    "temporal_brake",
    "adoption_guard",
    "response_restraint",
    "exploration_restraint",
    "probe_restraint",
    "observation_detail",
}


@dataclass(frozen=True)
class PressureInput:
    pressure_component: str
    component_direction: str
    pressure_strength: float


@dataclass(frozen=True)
class PressureMixSpec:
    pressure_mix_id: str
    pressure_mix_ja: str
    pressures: tuple[PressureInput, ...]
    state_axes: tuple[str, ...]
    mix_reason: str


PRESSURE_MIX_SPECS: tuple[PressureMixSpec, ...] = (
    PressureMixSpec(
        "exploration_up__rollback_guard_up",
        "探索頻度を上げたい圧 + 巻き戻し感度を上げたい圧",
        (
            PressureInput("exploration_frequency", "increase", 0.60),
            PressureInput("rollback_sensitivity", "increase", 0.55),
        ),
        ("exploration_deficit", "recoverability_level", "uncertainty_level"),
        "探索を開きたいが、同時に戻しやすさも確保したい混合。",
    ),
    PressureMixSpec(
        "exploration_up__commitment_down",
        "探索頻度を上げたい圧 + 固定強度を下げたい圧",
        (
            PressureInput("exploration_frequency", "increase", 0.65),
            PressureInput("commitment_strength", "decrease", 0.55),
        ),
        ("exploration_deficit", "fixation_strength", "oscillation_strength", "buffer_scarcity"),
        "探索開口と固定緩和が同時に来る危険寄りの混合。",
    ),
    PressureMixSpec(
        "commitment_up__pressure_cap_down",
        "固定強度を上げたい圧 + 圧上限を下げたい圧",
        (
            PressureInput("commitment_strength", "increase", 0.58),
            PressureInput("pressure_cap", "decrease", 0.58),
        ),
        ("oscillation_strength", "buffer_scarcity", "hidden_damage_suspicion"),
        "安定化と強度抑制が同時に来る安全側の混合。",
    ),
    PressureMixSpec(
        "commitment_down__adoption_threshold_down",
        "固定強度を下げたい圧 + 採用ハードルを下げたい圧",
        (
            PressureInput("commitment_strength", "decrease", 0.55),
            PressureInput("adoption_threshold", "decrease", 0.55),
        ),
        ("fixation_strength", "relation_congestion", "oscillation_strength", "recoverability_level"),
        "固定緩和と採用入口開放が重なるため、解除過多を監査する混合。",
    ),
    PressureMixSpec(
        "diagnostic_depth_up__deadzone_down",
        "診断深度を上げたい圧 + 不感帯幅を下げたい圧",
        (
            PressureInput("diagnostic_depth", "increase", 0.50),
            PressureInput("deadzone_width", "decrease", 0.50),
        ),
        ("uncertainty_level", "residual_level", "oscillation_strength"),
        "観測解像度を上げつつ、小さい信号にも反応したい混合。",
    ),
)

REQUIRED_TASK2_5D_COLUMNS = [
    "task2_5d_version",
    "task2_5d_contract",
    "validation_type",
    "validation_only",
    "runtime_policy_input",
    "validation_projection_only",
    "pressure_to_action_converter_created",
    "final_action_decision",
    "action_frame_created",
    "actionmodule_called",
    "mapping_source",
    "calibration_status",
    "pressure_mix_id",
    "pressure_mix_ja",
    "mix_reason",
    "scenario_or_state_band",
    "state_band_ja",
    "state_label_set",
    "state_label_set_ja",
    "pressure_components",
    "pressure_strength_vector",
    "candidate_action_set",
    "candidate_action_set_ja",
    "candidate_action_count",
    "candidate_score_json",
    "intended_pressure_coverage",
    "pressure_conflict_score",
    "action_overcrowding_score",
    "unsafe_combination_score",
    "side_effect_burden",
    "safe_action_mixing_required",
    "recommended_candidate_filtering",
    "unsafe_interaction_pairs",
    "requires_task2_5e_strength_review",
    "uses_existing_pressure_intent_semantics",
    "new_semantic_translation_layer_added",
    "diagnostic_compat_policy_used",
    "repaired_diagnostic_policy_used",
]


def _json_list(values: list[str]) -> str:
    return json.dumps(values, ensure_ascii=False)


def _pressure_label(pressure: PressureInput) -> str:
    comp = PRESSURE_COMPONENT_JA.get(pressure.pressure_component, pressure.pressure_component)
    direction = "上げる" if pressure.component_direction == "increase" else "下げる"
    return f"{comp}を{direction}圧"


def _pressure_mix_vectors(spec: PressureMixSpec) -> tuple[str, str]:
    components = [_pressure_label(p) for p in spec.pressures]
    strengths = {
        f"{p.pressure_component}:{p.component_direction}": float(p.pressure_strength)
        for p in spec.pressures
    }
    return _json_list(components), json.dumps(strengths, ensure_ascii=False, sort_keys=True)


def _state_modifier_for_action(state_modifiers: pd.DataFrame, action: str, state_axes: tuple[str, ...], state_band: str) -> float:
    level = STATE_TO_LEVEL[state_band]
    rows = state_modifiers[
        (state_modifiers["action_channel"].astype(str) == action)
        & (state_modifiers["state_axis"].astype(str).isin(state_axes))
        & (state_modifiers["state_level"].astype(str) == level)
    ]
    if rows.empty:
        return 1.0
    values = pd.to_numeric(rows["state_modifier"], errors="coerce").fillna(1.0)
    # Use the geometric mean so multiple mild modifiers compound without one
    # arbitrary axis dominating the whole validation projection.
    clipped = values.clip(lower=0.0, upper=1.5)
    if bool((clipped <= 0.0).any()):
        return 0.0
    product = 1.0
    for value in clipped:
        product *= float(value)
    return float(product ** (1.0 / len(clipped)))


def _projection_scores_for_mix(
    spec: PressureMixSpec,
    state_band: str,
    correspondence: pd.DataFrame,
    state_modifiers: pd.DataFrame,
) -> tuple[dict[str, float], dict[str, float]]:
    raw_scores: dict[str, float] = {}
    adjusted_scores: dict[str, float] = {}
    for pressure in spec.pressures:
        rows = correspondence[
            (correspondence["pressure_component"].astype(str) == pressure.pressure_component)
            & (correspondence["component_direction"].astype(str) == pressure.component_direction)
            & (pd.to_numeric(correspondence["basic_alignment_score"], errors="coerce").fillna(0.0) > 0.0)
        ]
        for _, row in rows.iterrows():
            action = str(row["action_channel"])
            share = float(row["action_to_pressure_share"])
            raw_scores[action] = raw_scores.get(action, 0.0) + float(pressure.pressure_strength) * share
    for action, raw in raw_scores.items():
        modifier = _state_modifier_for_action(state_modifiers, action, spec.state_axes, state_band)
        adjusted_scores[action] = float(raw * modifier)
    return raw_scores, adjusted_scores


def _pressure_coverage(spec: PressureMixSpec, correspondence: pd.DataFrame, candidate_actions: set[str]) -> float:
    if not spec.pressures:
        return 0.0
    covered = 0
    for pressure in spec.pressures:
        rows = correspondence[
            (correspondence["pressure_component"].astype(str) == pressure.pressure_component)
            & (correspondence["component_direction"].astype(str) == pressure.component_direction)
            & (correspondence["action_channel"].astype(str).isin(candidate_actions))
            & (pd.to_numeric(correspondence["basic_alignment_score"], errors="coerce").fillna(0.0) > 0.0)
        ]
        if not rows.empty:
            covered += 1
    return float(covered / len(spec.pressures))


def _pressure_conflict_score(spec: PressureMixSpec, correspondence: pd.DataFrame) -> float:
    families: set[str] = set()
    for pressure in spec.pressures:
        rows = correspondence[
            (correspondence["pressure_component"].astype(str) == pressure.pressure_component)
            & (correspondence["component_direction"].astype(str) == pressure.component_direction)
        ]
        families.update(rows["intent_family"].astype(str).tolist())
    has_opening = bool(families & OPENING_FAMILIES)
    has_safety = bool(families & SAFETY_FAMILIES)
    if has_opening and has_safety:
        return 0.70
    if len(families) >= 2:
        return 0.25
    return 0.0


def _interaction_lookup(interactions: pd.DataFrame, action_a: str, action_b: str, state_band: str) -> pd.DataFrame:
    pair1 = f"{action_a}+{action_b}"
    pair2 = f"{action_b}+{action_a}"
    return interactions[
        interactions["scenario_or_state_band"].astype(str).eq(state_band)
        & interactions["action_pair"].astype(str).isin([pair1, pair2])
    ]


def _unsafe_interactions(
    candidate_actions: list[str],
    state_band: str,
    interactions: pd.DataFrame,
) -> tuple[float, list[str], bool]:
    score = 0.0
    pairs: list[str] = []
    requires_strength = False
    for action_a, action_b in combinations(sorted(candidate_actions), 2):
        rows = _interaction_lookup(interactions, action_a, action_b, state_band)
        if rows.empty:
            continue
        row = rows.iloc[0]
        modifier = float(row["interaction_modifier"])
        modifier_class = str(row["modifier_class"])
        if bool(row.get("requires_task2_5e_strength_review", False)):
            requires_strength = True
        if modifier < 0.90 or modifier_class in {"dampen", "defer", "block"}:
            score += float(1.0 - modifier)
            pairs.append(str(row["action_pair_ja"] if "action_pair_ja" in rows.columns else f"{action_a}+{action_b}"))
    return float(score), pairs, requires_strength


def _side_effect_burden(candidate_actions: list[str], interactions: pd.DataFrame, state_band: str) -> float:
    rows = interactions[interactions["scenario_or_state_band"].astype(str).eq(state_band)]
    burdens = []
    for action_a, action_b in combinations(sorted(candidate_actions), 2):
        pair_rows = rows[rows["action_pair"].astype(str).isin([f"{action_a}+{action_b}", f"{action_b}+{action_a}"])]
        if not pair_rows.empty:
            burdens.append(float(pair_rows["side_effect_amplification_score"].iloc[0]))
    return float(sum(burdens))


def _recommended_filtering(
    candidate_count: int,
    pressure_conflict_score: float,
    unsafe_score: float,
    safe_action_mixing_required: bool,
) -> str:
    if unsafe_score >= 1.0:
        return "block_or_defer_unsafe_pair_then_recompute_candidates"
    if unsafe_score >= 0.45:
        return "dampen_or_defer_unsafe_pair"
    if candidate_count > TARGET_CANDIDATE_COUNT:
        return "prune_to_top_candidates_before_gate"
    if safe_action_mixing_required:
        return "add_or_preserve_safety_side_candidate"
    if pressure_conflict_score >= 0.60:
        return "keep_candidates_but_require_conflict_audit"
    return "keep_candidate_set"


def build_pressure_mix_validation_table(
    correspondence: pd.DataFrame | None = None,
    state_modifiers: pd.DataFrame | None = None,
    interactions: pd.DataFrame | None = None,
    mix_specs: tuple[PressureMixSpec, ...] = PRESSURE_MIX_SPECS,
) -> pd.DataFrame:
    """Build the Task 2-5d mixed-pressure validation table."""
    corr = build_single_action_to_pressure_correspondence_table() if correspondence is None else correspondence.copy()
    state = build_state_modifier_validation_table() if state_modifiers is None else state_modifiers.copy()
    inter = build_interaction_modifier_validation_table() if interactions is None else interactions.copy()
    if corr.empty or state.empty or inter.empty:
        return pd.DataFrame(columns=REQUIRED_TASK2_5D_COLUMNS)

    rows: list[dict] = []
    for spec in mix_specs:
        pressure_components, pressure_strength_vector = _pressure_mix_vectors(spec)
        for state_band in STATE_BANDS:
            raw_scores, adjusted_scores = _projection_scores_for_mix(spec, state_band, corr, state)
            sorted_actions = sorted(adjusted_scores, key=lambda action: adjusted_scores[action], reverse=True)
            candidate_actions = [action for action in sorted_actions if adjusted_scores[action] >= CANDIDATE_THRESHOLD]
            if not candidate_actions and sorted_actions:
                candidate_actions = sorted_actions[:1]
            candidate_set = set(candidate_actions)
            intended_coverage = _pressure_coverage(spec, corr, candidate_set)
            pressure_conflict = _pressure_conflict_score(spec, corr)
            unsafe_score, unsafe_pairs, requires_strength_review = _unsafe_interactions(candidate_actions, state_band, inter)
            overcrowding = max(0.0, float(len(candidate_actions) - TARGET_CANDIDATE_COUNT) / max(float(len(candidate_actions)), 1.0))
            side_burden = _side_effect_burden(candidate_actions, inter, state_band)
            has_safety = bool(candidate_set & SAFETY_ACTIONS)
            safe_required = bool((pressure_conflict >= 0.60 or unsafe_score > 0.0 or state_band in {"high", "limit"}) and not has_safety)
            rows.append({
                "task2_5d_version": TASK2_5D_VERSION,
                "task2_5d_contract": TASK2_5D_CONTRACT,
                "validation_type": "mixed_pressure_input_validation",
                "validation_only": True,
                "runtime_policy_input": False,
                "validation_projection_only": True,
                "pressure_to_action_converter_created": False,
                "final_action_decision": False,
                "action_frame_created": False,
                "actionmodule_called": False,
                "mapping_source": TASK2_5D_MAPPING_SOURCE,
                "calibration_status": TASK2_5D_CALIBRATION_STATUS,
                "pressure_mix_id": spec.pressure_mix_id,
                "pressure_mix_ja": spec.pressure_mix_ja,
                "mix_reason": spec.mix_reason,
                "scenario_or_state_band": state_band,
                "state_band_ja": STATE_BAND_JA[state_band],
                "state_label_set": _json_list(list(spec.state_axes)),
                "state_label_set_ja": _json_list([str(x) for x in spec.state_axes]),
                "pressure_components": pressure_components,
                "pressure_strength_vector": pressure_strength_vector,
                "candidate_action_set": _json_list(candidate_actions),
                "candidate_action_set_ja": _json_list([ACTION_CHANNEL_JA.get(action, action) for action in candidate_actions]),
                "candidate_action_count": int(len(candidate_actions)),
                "candidate_score_json": json.dumps(adjusted_scores, ensure_ascii=False, sort_keys=True),
                "intended_pressure_coverage": float(intended_coverage),
                "pressure_conflict_score": float(pressure_conflict),
                "action_overcrowding_score": float(overcrowding),
                "unsafe_combination_score": float(unsafe_score),
                "side_effect_burden": float(side_burden),
                "safe_action_mixing_required": bool(safe_required),
                "recommended_candidate_filtering": _recommended_filtering(
                    len(candidate_actions), pressure_conflict, unsafe_score, safe_required
                ),
                "unsafe_interaction_pairs": _json_list(unsafe_pairs),
                "requires_task2_5e_strength_review": bool(requires_strength_review or unsafe_score > 0.0 or overcrowding > 0.0),
                "uses_existing_pressure_intent_semantics": True,
                "new_semantic_translation_layer_added": False,
                "diagnostic_compat_policy_used": False,
                "repaired_diagnostic_policy_used": False,
            })
    out = pd.DataFrame(rows)
    return out[REQUIRED_TASK2_5D_COLUMNS]


def validate_pressure_mix_validation_table(df: pd.DataFrame) -> list[str]:
    """Return validation errors for the Task 2-5d table."""
    errors: list[str] = []
    if df is None or df.empty:
        return ["task2_5d_pressure_mix_table_empty"]
    missing = sorted(set(REQUIRED_TASK2_5D_COLUMNS) - set(df.columns))
    if missing:
        errors.append(f"task2_5d_required_columns_missing:{','.join(missing)}")
        return errors

    false_fields = [
        "runtime_policy_input",
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
            errors.append(f"task2_5d_forbidden_true_field:{field}")

    if not bool(df["validation_only"].astype(bool).all()):
        errors.append("task2_5d_not_all_validation_only")
    if not bool(df["validation_projection_only"].astype(bool).all()):
        errors.append("task2_5d_not_marked_validation_projection_only")
    if not bool(df["uses_existing_pressure_intent_semantics"].astype(bool).all()):
        errors.append("task2_5d_pressure_intent_semantics_not_preserved")

    for col in [
        "intended_pressure_coverage",
        "pressure_conflict_score",
        "action_overcrowding_score",
        "unsafe_combination_score",
        "side_effect_burden",
    ]:
        values = pd.to_numeric(df[col], errors="coerce")
        if bool(values.isna().any() or (values < 0.0).any()):
            errors.append(f"task2_5d_invalid_nonnegative_score:{col}")

    coverage = pd.to_numeric(df["intended_pressure_coverage"], errors="coerce")
    if bool((coverage > 1.0 + 1e-12).any()):
        errors.append("task2_5d_intended_pressure_coverage_above_one")
    if bool(pd.to_numeric(df["candidate_action_count"], errors="coerce").fillna(0).le(0).any()):
        errors.append("task2_5d_empty_candidate_action_set")

    observed_mix_ids = set(df["pressure_mix_id"].astype(str))
    expected_mix_ids = {spec.pressure_mix_id for spec in PRESSURE_MIX_SPECS}
    missing_mix_ids = expected_mix_ids - observed_mix_ids
    if missing_mix_ids:
        errors.append("task2_5d_missing_pressure_mix_ids:" + ",".join(sorted(missing_mix_ids)))

    risky_mix = df[df["pressure_mix_id"].astype(str).eq("exploration_up__commitment_down")]
    if risky_mix.empty:
        errors.append("task2_5d_missing_exploration_commitment_down_mix")
    else:
        high_risk = risky_mix[risky_mix["scenario_or_state_band"].astype(str).isin(["high", "limit"])]
        if high_risk.empty or not bool((pd.to_numeric(high_risk["unsafe_combination_score"], errors="coerce") > 0.0).any()):
            errors.append("task2_5d_risky_mix_did_not_surface_unsafe_combination")

    return errors


def build_and_validate_pressure_mix_validation_table() -> tuple[pd.DataFrame, list[str]]:
    df = build_pressure_mix_validation_table()
    return df, validate_pressure_mix_validation_table(df)
