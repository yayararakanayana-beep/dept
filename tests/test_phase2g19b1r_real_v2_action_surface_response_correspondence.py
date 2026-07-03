"""Phase 2G-19B-1R real-v2 action-surface response correspondence.

This validation intentionally uses the existing PseudoReality v2 asymmetric game
runner and its emitted ``v2_action_effect_trace``.  It is an external verifier:
it does not tune ActionModule/ActionPlanner behavior, primitive gains,
PseudoReality v2 dynamics, pressure translation, ParameterBox/ShadowBox, or any
canonical write path.
"""

from __future__ import annotations

import csv
import inspect
import subprocess
import sys
from io import StringIO
from pathlib import Path

import pandas as pd
import pytest

RC1_ROOT = Path("localprep1/dept/DEPT2_ActionModule_ActuationPrimitives_RC1")
if str(RC1_ROOT) not in sys.path:
    sys.path.insert(0, str(RC1_ROOT))

from pseudo_reality.asymmetric_game_v2 import AsymmetricGamePseudoRealitySystem  # noqa: E402


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
DELTA_FIELDS = (
    "delta_vs_no_op_exploration",
    "delta_vs_no_op_reversibility",
    "delta_vs_no_op_hidden_damage",
    "delta_vs_no_op_fatigue",
    "delta_vs_no_op_resource_inequality",
    "delta_vs_no_op_cost",
)
RESPONSE_STATUSES = {"aligned", "mixed", "side_effect_heavy", "weak_effect", "unresolved", "blocker"}
PRIMITIVES = {
    "no_op": "observe_only",
    "buffer_increase": "reversibility_buffer",
    "coupling_relief": "coupling_relief_unlock",
    "volatility_damping": "volatility_damping",
    "uncertainty_probe": "low_cost_uncertainty_probe",
    "exploration_injection": "exploration_injection",
    "relation_unlock": "relation_unlock",
}
STATE_INITIAL_CONDITIONS = {
    "stable": dict(fatigue=0.16, hidden_damage=0.08, latent_pressure=0.18, defensiveness=0.20, private_resource=0.76, exploration=0.48, reversibility=0.72, volatility=0.16, uncertainty=0.22, relation_lock=0.24, coupling=0.36, shared_resource=0.82, commons_health=0.84),
    "medium": dict(fatigue=0.34, hidden_damage=0.22, latent_pressure=0.42, defensiveness=0.42, private_resource=0.62, exploration=0.42, reversibility=0.58, volatility=0.30, uncertainty=0.42, relation_lock=0.50, coupling=0.56, shared_resource=0.68, commons_health=0.70),
    "high": dict(fatigue=0.62, hidden_damage=0.48, latent_pressure=0.70, defensiveness=0.68, private_resource=0.45, exploration=0.32, reversibility=0.38, volatility=0.58, uncertainty=0.64, relation_lock=0.72, coupling=0.74, shared_resource=0.44, commons_health=0.48),
    "limit": dict(fatigue=0.82, hidden_damage=0.72, latent_pressure=0.86, defensiveness=0.82, private_resource=0.30, exploration=0.22, reversibility=0.22, volatility=0.78, uncertainty=0.78, relation_lock=0.86, coupling=0.84, shared_resource=0.26, commons_health=0.30),
}


def _make_action_frame(state_band: str, channel: str, seed: int = 191, strength: float | None = None) -> dict:
    action_strength = 0.0 if channel == "no_op" else (0.12 if strength is None else strength)
    return {
        "entity_id": "E000",
        "state_band": state_band,
        "seed": seed,
        "action_channel": channel,
        "action_strength": action_strength,
        "direction": "external_real_v2_channel_probe",
        "source_gate_decision": "validation_probe_not_runtime_gate",
        "planner_route": "manual_validation_probe_not_runtime_policy",
        "action_primitive": PRIMITIVES[channel],
        "primitive_sequence": f"probe::{PRIMITIVES[channel]}",
        "primitive_stage": 1,
        "action_scope": "single_entity_real_v2_probe",
        "duration_steps": 1,
        "rollback_condition": "validation_only_no_runtime_write",
        "dominant_semantic_effect": channel,
        "dominant_pressure_component": "external_correspondence_validation",
        "action_module_contract": "not_runtime_actuator_input",
    }


def _make_world(state_band: str, seed: int) -> AsymmetricGamePseudoRealitySystem:
    cfg = {
        "active_dynamics": {
            "trust_decay": {"enabled": True, "intensity": 0.04},
            "defensive_hoarding": {"enabled": True, "intensity": 0.05},
            "hidden_damage_growth": {"enabled": True, "intensity": 0.04},
            "no_op_decay": {"enabled": True, "intensity": 0.03},
        },
        "implemented_axes": ["action_cost"],
        "cause_side_parameters": {"action_cost": 0.25},
    }
    world = AsymmetricGamePseudoRealitySystem(seed=seed, scenario=f"phase2g19b1r_{state_band}", profile_config=cfg)
    init = STATE_INITIAL_CONDITIONS[state_band]
    for col in ("fatigue", "hidden_damage", "latent_pressure", "defensiveness", "private_resource"):
        world.hidden[col] = init[col]
    for col in ("exploration", "reversibility", "volatility", "uncertainty", "relation_lock", "coupling"):
        world.entities[col] = init[col]
    # Small spread lets resource inequality deltas be observable without changing v2 dynamics.
    world.hidden["private_resource"] = (world.hidden["private_resource"] + pd.Series(range(len(world.hidden))) * 0.001).clip(0.0, 1.0)
    world.shared_resource = init["shared_resource"]
    world.commons_health = init["commons_health"]
    return world


def _real_v2_effect_for(frame: dict) -> tuple[dict, dict]:
    world = _make_world(frame["state_band"], frame["seed"])
    probe = pd.DataFrame([frame])
    trace = world.step(probe)
    effect = trace.get("v2_action_effect_trace", pd.DataFrame())
    meta = {
        "real_v2_runner_used": "pseudo_reality.asymmetric_game_v2.AsymmetricGamePseudoRealitySystem.step",
        "real_v2_trace_used": "v2_action_effect_trace",
        "real_v2_connection_status": "connected" if isinstance(effect, pd.DataFrame) and not effect.empty else "blocker",
        "state_band_mapping_note": "test helper maps state_band to initial conditions before existing v2 dynamics/action application",
    }
    if not isinstance(effect, pd.DataFrame) or effect.empty:
        return {"action_channel": frame["action_channel"]}, meta
    matched = effect[effect["action_channel"].astype(str) == frame["action_channel"]]
    if matched.empty and frame["action_channel"] == "no_op":
        matched = effect[effect["action_channel"].astype(str).isin(["no_action", "no_op"])]
    row = (matched.iloc[0] if not matched.empty else effect.iloc[0]).to_dict()
    if frame["action_channel"] == "no_op" and row.get("action_channel") == "no_action":
        row["action_channel"] = "no_op"
    return row, meta


def _score_row(row: dict) -> dict:
    missing = [field for field in CORE_FIELDS if field not in row or pd.isna(row[field])]
    if row.get("real_v2_connection_status") != "connected":
        return {"missing_response_fields": missing, "intended_effect_score": 0.0, "side_effect_burden_score": 0.0, "cost_burden_score": 0.0, "response_alignment_score": 0.0, "response_status": "blocker", "side_effect_flags": [], "unresolved_reason": "real_v2_action_effect_trace_unavailable"}
    if missing:
        return {"missing_response_fields": missing, "intended_effect_score": 0.0, "side_effect_burden_score": 0.0, "cost_burden_score": 0.0, "response_alignment_score": 0.0, "response_status": "unresolved", "side_effect_flags": ["missing_core_fields"], "unresolved_reason": "missing_core_v2_action_effect_fields"}
    burden = abs(float(row["net_hidden_effect_score"])) + max(float(row["hidden_damage_delta"]), 0.0) + max(float(row["fatigue_delta"]), 0.0) + max(float(row["resource_inequality_delta"]), 0.0)
    cost = abs(float(row["action_cost_effect"]))
    channel = row["action_channel"]
    intended = {
        "no_op": 1.0 - sum(abs(float(row[f])) for f in CORE_FIELDS),
        "buffer_increase": float(row["reversibility_delta"]),
        "coupling_relief": max(0.0, -float(row["resource_inequality_delta"])) + 0.5 * max(0.0, -float(row["net_hidden_effect_score"])),
        "volatility_damping": max(0.0, float(row["reversibility_delta"])) + max(0.0, -float(row["hidden_damage_delta"])) + max(0.0, -float(row["fatigue_delta"])),
        "uncertainty_probe": 0.05 - burden - cost,
        "exploration_injection": float(row["exploration_delta"]),
        "relation_unlock": float(row["reversibility_delta"]) + float(row["net_public_effect_score"]) - max(float(row["resource_inequality_delta"]), 0.0),
    }[channel]
    alignment = intended - burden - cost
    flags = []
    if burden > 0.020:
        flags.append("hidden_burden_elevated")
    if float(row["resource_inequality_delta"]) > 0.005:
        flags.append("resource_inequality_elevated")
    if cost > 0.003:
        flags.append("action_cost_elevated")
    status = "aligned" if alignment > 0.005 and not flags else "mixed"
    if burden > max(0.012, intended + cost):
        status = "side_effect_heavy"
    elif abs(intended) < 0.004 and not flags:
        status = "weak_effect"
    return {"missing_response_fields": missing, "intended_effect_score": intended, "side_effect_burden_score": burden, "cost_burden_score": cost, "response_alignment_score": alignment, "response_status": status, "side_effect_flags": flags, "unresolved_reason": ""}


def build_real_v2_response_map(seed: int = 191) -> pd.DataFrame:
    rows = []
    for state_band in STATE_BANDS:
        baseline_key = f"{state_band}:{seed}:no_op"
        baseline_frame = _make_action_frame(state_band, "no_op", seed)
        baseline_effect, _ = _real_v2_effect_for(baseline_frame)
        for channel in CHANNELS:
            frame = _make_action_frame(state_band, channel, seed)
            effect, meta = _real_v2_effect_for(frame)
            row = {**frame, **effect, **meta, "no_op_baseline_key": baseline_key}
            for src, dst in (("exploration_delta", "delta_vs_no_op_exploration"), ("reversibility_delta", "delta_vs_no_op_reversibility"), ("hidden_damage_delta", "delta_vs_no_op_hidden_damage"), ("fatigue_delta", "delta_vs_no_op_fatigue"), ("resource_inequality_delta", "delta_vs_no_op_resource_inequality"), ("action_cost_effect", "delta_vs_no_op_cost")):
                row[dst] = float(row[src]) - float(baseline_effect[src]) if src in row and src in baseline_effect else None
            row.update(_score_row(row))
            rows.append(row)
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def response_map() -> pd.DataFrame:
    return build_real_v2_response_map()


def test_real_v2_connection_is_attempted_and_recorded(response_map):
    assert {"real_v2_connection_status", "real_v2_runner_used", "real_v2_trace_used"}.issubset(response_map.columns)
    assert response_map["real_v2_runner_used"].str.contains("AsymmetricGamePseudoRealitySystem.step", regex=False).all()
    assert set(response_map["real_v2_connection_status"]).issubset({"connected", "blocker"})


def test_response_map_uses_real_v2_action_effect_trace_when_available(response_map):
    assert set(response_map["real_v2_trace_used"]) == {"v2_action_effect_trace"}
    assert response_map["real_v2_connection_status"].eq("connected").all()
    assert response_map[list(CORE_FIELDS)].notna().all().all()


def test_no_op_baseline_is_present(response_map):
    no_op = response_map[response_map["action_channel"] == "no_op"]
    assert len(no_op) == len(STATE_BANDS)
    assert (no_op["action_strength"] == 0.0).all()
    assert (no_op["action_cost_effect"].abs() <= 1e-12).all()
    assert no_op["no_op_baseline_key"].str.endswith(":no_op").all()


def test_required_channels_are_attempted(response_map):
    assert set(response_map["action_channel"]) == set(CHANNELS)


def test_required_state_bands_are_attempted(response_map):
    assert set(response_map["state_band"]) == set(STATE_BANDS)
    assert response_map["state_band_mapping_note"].notna().all()


def test_core_effect_fields_are_present_or_explicitly_unresolved(response_map):
    assert set(CORE_FIELDS).issubset(response_map.columns)
    assert response_map["missing_response_fields"].map(list).map(len).eq(0).all()


def test_delta_vs_no_op_is_computed(response_map):
    assert set(DELTA_FIELDS).issubset(response_map.columns)
    assert response_map[list(DELTA_FIELDS)].notna().all().all()


def test_at_least_some_non_no_op_response_differs_from_no_op_when_connected(response_map):
    connected = response_map[(response_map["real_v2_connection_status"] == "connected") & (response_map["action_channel"] != "no_op")]
    assert (connected[list(DELTA_FIELDS)].abs().sum(axis=1) > 0).any()


def test_response_scores_are_emitted(response_map):
    fields = {"intended_effect_score", "side_effect_burden_score", "cost_burden_score", "response_alignment_score", "response_status", "side_effect_flags"}
    assert fields.issubset(response_map.columns)
    assert set(response_map["response_status"]).issubset(RESPONSE_STATUSES)


def test_channel_specific_response_is_not_required_to_be_clean(response_map):
    assert set(response_map["response_status"]).issubset(RESPONSE_STATUSES)
    assert response_map["side_effect_flags"].map(lambda x: isinstance(x, list)).all()
    assert {"mixed", "side_effect_heavy", "weak_effect", "aligned"}.intersection(set(response_map["response_status"]))


def test_real_v2_response_map_can_be_exported(response_map):
    required = {"state_band", "seed", "action_channel", "action_strength", "action_primitive", "target_count", "real_v2_runner_used", "real_v2_trace_used", "real_v2_connection_status", *CORE_FIELDS, *DELTA_FIELDS, "intended_effect_score", "side_effect_burden_score", "cost_burden_score", "response_alignment_score", "response_status", "side_effect_flags", "missing_response_fields", "unresolved_reason"}
    assert required.issubset(response_map.columns)
    assert len(response_map) >= len(STATE_BANDS) * len(CHANNELS)
    csv_text = response_map.to_csv(index=False)
    parsed = list(csv.DictReader(StringIO(csv_text)))
    assert len(parsed) == len(response_map)
    assert required.issubset(parsed[0])


def test_validation_does_not_tune_action_module():
    changed = subprocess.run(["git", "diff", "--name-only", "HEAD"], check=True, text=True, capture_output=True).stdout.splitlines()
    forbidden_fragments = ("action_module/actions.py", "action_surface_planning_module.py", "action_execution_module.py", "pseudo_reality/asymmetric_game_v2.py", "pressure_translation_module.py", "parameter_box.py", "parameter_shadow_box.py", "primitive", "gain")
    assert not [path for path in changed if any(fragment in path for fragment in forbidden_fragments)]


def test_no_observation_window_output_is_used_as_action_runtime_input():
    source = inspect.getsource(_make_action_frame) + inspect.getsource(build_real_v2_response_map)
    forbidden = ["composite_balance_window", "v2_direct_benefit_window", "v2_direct_growth_window", "v2_direct_risk_band_window", "ActionPlanner", "ActionModule"]
    assert not [token for token in forbidden if token in source]


def test_no_v2_trace_is_passed_into_actionplanner_or_actionmodule():
    source = inspect.getsource(_make_action_frame) + inspect.getsource(_real_v2_effect_for) + inspect.getsource(build_real_v2_response_map)
    assert "ActionPlanner" not in source
    assert "ActionModule" not in source
    assert "step(probe)" in source
    assert source.find("step(probe)") < source.find("trace.get(\"v2_action_effect_trace\"")
