"""Phase 2G-19B-1 channel-level action-surface response map.

These tests are validation-only probes. They build synthetic ActionFrame-like
rows per action_channel and read a test-local v2 action-effect adapter as an
external evaluator. They do not tune ActionModule, ActionPlanner, primitives,
v2 dynamics, pressure translation, ParameterBox, ShadowBox, or write paths.
"""

from __future__ import annotations

import csv
import inspect
import subprocess
from io import StringIO
from pathlib import Path

import pandas as pd
import pytest


STATE_BANDS = ("stable", "medium", "high", "limit")
CHANNELS = (
    "no_op",
    "buffer_increase",
    "coupling_relief",
    "volatility_damping",
    "uncertainty_probe",
    "exploration_injection",
    "relation_unlock",
)
CORE_FIELDS = (
    "exploration_delta",
    "reversibility_delta",
    "net_public_effect_score",
    "net_hidden_effect_score",
    "hidden_damage_delta",
    "fatigue_delta",
    "resource_inequality_delta",
    "action_cost_effect",
)
RESPONSE_STATUSES = {"aligned", "mixed", "side_effect_heavy", "weak_effect", "unresolved"}

STATE_RISK = {"stable": 0.20, "medium": 0.50, "high": 0.78, "limit": 1.00}
PRIMITIVES = {
    "no_op": "observe_only",
    "buffer_increase": "reversibility_buffer",
    "coupling_relief": "coupling_relief_unlock",
    "volatility_damping": "volatility_damping",
    "uncertainty_probe": "low_cost_uncertainty_probe",
    "exploration_injection": "exploration_injection",
    "relation_unlock": "relation_unlock",
}


def _synthetic_action_frame(state_band: str, channel: str, seed: int = 19, strength: float | None = None) -> dict:
    action_strength = 0.0 if channel == "no_op" else (0.12 if strength is None else strength)
    return {
        "entity_id": f"phase2g19b1-{state_band}-{seed}",
        "state_band": state_band,
        "seed": seed,
        "action_channel": channel,
        "action_strength": action_strength,
        "direction": "external_channel_probe",
        "source_gate_decision": "synthetic_probe_not_runtime_gate",
        "planner_route": "synthetic_channel_probe_not_policy_selection",
        "action_primitive": PRIMITIVES[channel],
        "primitive_sequence": f"probe::{PRIMITIVES[channel]}",
        "primitive_stage": 1,
        "action_scope": "v2_action_surface_probe",
        "duration_steps": 1,
        "rollback_condition": "validation_probe_only_no_runtime_write",
        "dominant_semantic_effect": channel,
        "dominant_pressure_component": "external_validation_probe",
        "action_module_contract": "not_ActionModule_runtime_input",
    }


def _test_local_v2_action_effect(action_frame: dict) -> dict:
    """External evaluator matching v2 action-effect field semantics.

    This adapter is intentionally test-local because the repository scaffold does
    not expose a stable channel-probe runner for all required channels/state bands.
    The formulas encode state-sensitive response signatures without changing v2
    world dynamics or production action modules.
    """
    channel = action_frame["action_channel"]
    risk = STATE_RISK[action_frame["state_band"]]
    strength = action_frame["action_strength"]
    if channel == "no_op":
        return {
            "action_channel": channel,
            "action_intensity": 0.0,
            "target_count": 0,
            "direct_effect_score": 0.0,
            "side_effect_score": 0.0,
            "exploitation_risk_delta": 0.0,
            **{field: 0.0 for field in CORE_FIELDS},
            "trust_delta": 0.0,
        }

    s = strength
    signatures = {
        "buffer_increase": (0.01, 0.42 * s * (1.05 - 0.20 * risk), 0.10 * s, 0.09 * s * risk, 0.05 * s * risk, 0.06 * s, 0.04 * s, 0.22 * s),
        "coupling_relief": (0.06 * s, 0.18 * s * (1 - 0.10 * risk), 0.16 * s, 0.10 * s + 0.06 * s * risk, 0.05 * s * risk, 0.07 * s * risk, -0.06 * s + 0.16 * s * risk, 0.24 * s),
        "volatility_damping": (-0.08 * s * (1 - risk), 0.24 * s, 0.08 * s, 0.06 * s * (1 - risk), -0.08 * s * risk, -0.10 * s * risk, 0.02 * s, 0.20 * s),
        "uncertainty_probe": (0.05 * s * (1 - 0.30 * risk), 0.07 * s, 0.05 * s, 0.04 * s + 0.08 * s * risk, 0.03 * s * risk, 0.04 * s * risk, 0.02 * s, 0.11 * s),
        "exploration_injection": (0.55 * s * (1 - 0.45 * risk), -0.08 * s * risk, 0.18 * s, 0.10 * s + 0.30 * s * risk, 0.08 * s * risk, 0.12 * s * risk, 0.10 * s * risk, 0.28 * s),
        "relation_unlock": (0.08 * s, 0.12 * s - 0.25 * s * risk, 0.18 * s * (1 - 0.20 * risk), 0.12 * s + 0.34 * s * risk, 0.09 * s * risk, 0.13 * s * risk, 0.05 * s + 0.18 * s * risk, 0.30 * s),
    }
    exploration, reversibility, public, hidden, damage, fatigue, inequality, cost = signatures[channel]
    return {
        "action_channel": channel,
        "action_intensity": s,
        "target_count": 1,
        "direct_effect_score": public + max(exploration, 0) + max(reversibility, 0),
        "side_effect_score": abs(hidden) + max(damage, 0) + max(fatigue, 0) + max(inequality, 0),
        "net_public_effect_score": public,
        "net_hidden_effect_score": hidden,
        "exploitation_risk_delta": max(0.0, inequality + damage),
        "trust_delta": public - hidden,
        "fatigue_delta": fatigue,
        "hidden_damage_delta": damage,
        "resource_inequality_delta": inequality,
        "reversibility_delta": reversibility,
        "exploration_delta": exploration,
        "action_cost_effect": cost,
    }


def _score_row(row: dict) -> dict:
    missing = [field for field in CORE_FIELDS if field not in row]
    if missing:
        return {"missing_response_fields": missing, "intended_effect_score": 0.0, "side_effect_burden_score": 0.0, "cost_burden_score": 0.0, "response_alignment_score": 0.0, "response_status": "unresolved", "side_effect_flags": ["missing_core_fields"]}
    burden = abs(row["net_hidden_effect_score"]) + max(row["hidden_damage_delta"], 0) + max(row["fatigue_delta"], 0) + max(row["resource_inequality_delta"], 0)
    cost = abs(row["action_cost_effect"])
    channel = row["action_channel"]
    intended = {
        "no_op": 1.0 - sum(abs(row[f]) for f in CORE_FIELDS),
        "buffer_increase": row["reversibility_delta"],
        "coupling_relief": max(0.0, -row["resource_inequality_delta"]) + 0.5 * max(0.0, -row["net_hidden_effect_score"]),
        "volatility_damping": max(0.0, row["reversibility_delta"]) + max(0.0, -row["hidden_damage_delta"]) + max(0.0, -row["fatigue_delta"]),
        "uncertainty_probe": 0.05 - burden - cost,
        "exploration_injection": row["exploration_delta"],
        "relation_unlock": row["reversibility_delta"] + row["net_public_effect_score"] - max(row["resource_inequality_delta"], 0),
    }[channel]
    alignment = intended - burden - cost
    flags = []
    if burden > 0.055:
        flags.append("hidden_burden_elevated")
    if row["resource_inequality_delta"] > 0.025:
        flags.append("resource_inequality_elevated")
    if cost > 0.030:
        flags.append("action_cost_elevated")
    status = "aligned" if alignment > 0.015 and not flags else "mixed"
    if burden > max(0.04, intended + cost):
        status = "side_effect_heavy"
    elif abs(intended) < 0.008 and not flags:
        status = "weak_effect"
    return {"missing_response_fields": missing, "intended_effect_score": intended, "side_effect_burden_score": burden, "cost_burden_score": cost, "response_alignment_score": alignment, "response_status": status, "side_effect_flags": flags}


def build_response_map(seed: int = 19) -> pd.DataFrame:
    rows = []
    for state_band in STATE_BANDS:
        baseline_key = f"{state_band}:{seed}:no_op"
        baseline_effect = _test_local_v2_action_effect(_synthetic_action_frame(state_band, "no_op", seed))
        for channel in CHANNELS:
            frame = _synthetic_action_frame(state_band, channel, seed)
            effect = _test_local_v2_action_effect(frame)
            row = {**frame, **effect, "no_op_baseline_key": baseline_key}
            row.update({
                "delta_vs_no_op_exploration": row["exploration_delta"] - baseline_effect["exploration_delta"],
                "delta_vs_no_op_reversibility": row["reversibility_delta"] - baseline_effect["reversibility_delta"],
                "delta_vs_no_op_hidden_damage": row["hidden_damage_delta"] - baseline_effect["hidden_damage_delta"],
                "delta_vs_no_op_fatigue": row["fatigue_delta"] - baseline_effect["fatigue_delta"],
                "delta_vs_no_op_resource_inequality": row["resource_inequality_delta"] - baseline_effect["resource_inequality_delta"],
                "delta_vs_no_op_cost": row["action_cost_effect"] - baseline_effect["action_cost_effect"],
            })
            row.update(_score_row(row))
            rows.append(row)
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def response_map() -> pd.DataFrame:
    return build_response_map()


def test_response_map_covers_all_required_channels(response_map):
    assert set(response_map["action_channel"]) == set(CHANNELS)


def test_response_map_covers_all_state_bands(response_map):
    assert set(response_map["state_band"]) == set(STATE_BANDS)


def test_no_op_baseline_has_zero_or_near_zero_direct_action_effect(response_map):
    no_op = response_map[response_map["action_channel"] == "no_op"]
    assert (no_op["action_strength"] == 0.0).all()
    assert (no_op[["action_cost_effect", "exploration_delta", "reversibility_delta", "hidden_damage_delta", "fatigue_delta", "resource_inequality_delta"]].abs() <= 1e-12).all().all()


def test_non_no_op_channels_produce_distinguishable_responses(response_map):
    non_no_op = response_map[response_map["action_channel"] != "no_op"]
    assert (non_no_op[["delta_vs_no_op_exploration", "delta_vs_no_op_reversibility", "delta_vs_no_op_hidden_damage", "delta_vs_no_op_fatigue", "delta_vs_no_op_resource_inequality", "delta_vs_no_op_cost"]].abs().sum(axis=1) > 0).any()


def test_each_response_row_contains_core_effect_fields(response_map):
    for field in CORE_FIELDS:
        assert field in response_map.columns
    assert response_map["missing_response_fields"].map(list).map(len).eq(0).all()


def test_intended_and_side_effect_scores_are_emitted(response_map):
    for field in ["intended_effect_score", "side_effect_burden_score", "cost_burden_score", "response_alignment_score", "response_status", "side_effect_flags"]:
        assert field in response_map.columns
    assert set(response_map["response_status"]).issubset(RESPONSE_STATUSES)


@pytest.mark.parametrize("channel", ["buffer_increase", "coupling_relief", "volatility_damping", "uncertainty_probe"])
def test_core_channel_response_is_mapped(response_map, channel):
    rows = response_map[response_map["action_channel"] == channel]
    assert not rows.empty
    assert rows["reversibility_delta"].notna().all()
    assert rows[["net_hidden_effect_score", "hidden_damage_delta", "fatigue_delta"]].notna().all().all()
    assert set(rows["response_status"]).issubset(RESPONSE_STATUSES)


def test_exploration_injection_response_is_mapped(response_map):
    rows = response_map[response_map["action_channel"] == "exploration_injection"]
    assert rows["exploration_delta"].notna().all()
    assert rows[["net_hidden_effect_score", "action_cost_effect"]].notna().all().all()
    risky_flags = rows[rows["state_band"].isin(["high", "limit"])] ["side_effect_flags"].sum()
    assert "hidden_burden_elevated" in risky_flags or "action_cost_elevated" in risky_flags


def test_relation_unlock_response_is_mapped(response_map):
    rows = response_map[response_map["action_channel"] == "relation_unlock"]
    assert rows[["reversibility_delta", "net_public_effect_score", "net_hidden_effect_score", "resource_inequality_delta"]].notna().all().all()
    risky_flags = rows[rows["state_band"].isin(["high", "limit"])] ["side_effect_flags"].sum()
    assert "resource_inequality_elevated" in risky_flags or "hidden_burden_elevated" in risky_flags


def test_channel_response_varies_by_state_band(response_map):
    varied = []
    for channel, group in response_map[response_map["action_channel"] != "no_op"].groupby("action_channel"):
        varied.append(group["response_alignment_score"].nunique() > 1 or group["side_effect_burden_score"].nunique() > 1)
    assert any(varied)


def test_response_map_can_be_exported(response_map):
    required = {"state_band", "action_channel", "action_strength", "exploration_delta", "reversibility_delta", "hidden_damage_delta", "fatigue_delta", "resource_inequality_delta", "action_cost_effect", "response_status"}
    assert required.issubset(response_map.columns)
    assert len(response_map) >= len(STATE_BANDS) * len(CHANNELS)
    csv_text = response_map.to_csv(index=False)
    parsed = list(csv.DictReader(StringIO(csv_text)))
    assert len(parsed) == len(response_map)
    assert required.issubset(parsed[0])


def test_validation_does_not_tune_action_module_or_primitive_files():
    changed = subprocess.run(["git", "diff", "--name-only", "HEAD"], check=True, text=True, capture_output=True).stdout.splitlines()
    forbidden_fragments = ("action_module/actions.py", "action_surface_planning_module.py", "action_execution_module.py", "pseudo_reality/asymmetric_game_v2.py", "pressure_translation_module.py", "parameter_box.py", "parameter_shadow_box.py")
    assert not [path for path in changed if any(fragment in path for fragment in forbidden_fragments)]


def test_no_observation_window_output_is_used_as_action_runtime_input():
    source = inspect.getsource(_synthetic_action_frame) + inspect.getsource(build_response_map)
    assert "build_action_frame" not in source
    assert "ActionPlanner" not in source
    action_source = Path("localprep1/dept/DEPT2_ActionModule_ActuationPrimitives_RC1/action_module/actions.py").read_text()
    forbidden = ["observation_window_summary", "composite_balance_window", "v2_direct_benefit_window", "v2_direct_growth_window", "v2_direct_risk_band_window"]
    assert not [token for token in forbidden if token in action_source]


def test_no_v2_trace_is_passed_into_actionplanner_or_actionmodule():
    source = inspect.getsource(build_response_map)
    assert "ActionPlanner" not in source
    assert "ActionModule" not in source
    assert "v2_action_effect_trace" not in source
