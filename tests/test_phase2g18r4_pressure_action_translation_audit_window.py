from pathlib import Path
from types import SimpleNamespace
import sys

import pandas as pd
import pytest

LOCALPREP_ROOT = Path(__file__).resolve().parents[1] / "localprep1" / "dept"
if str(LOCALPREP_ROOT) not in sys.path:
    sys.path.insert(0, str(LOCALPREP_ROOT))

from scripts.observation_window_summary import build_observation_window_summary


def _cfg():
    return SimpleNamespace(validation_profile_name="smoke", world_profile_name="pseudo", action_profile_name="action")


def _out(pressure=None, gate=None, translation=None, action=None, **extra):
    out = {
        "pressure_trace": pd.DataFrame([pressure if pressure is not None else {"t": 4, "seed": 7, "scenario": "s", "pressure_frame_id": "p4", "pressure_norm": 0.24, "dominant_pressure_axis": "Exploration"}]),
        "gate_trace": pd.DataFrame([gate if gate is not None else {"t": 4, "seed": 7, "scenario": "s", "gate_passed": True, "gate_blocked": False, "safety_projection_applied": False}]),
        "translation_trace": pd.DataFrame([translation if translation is not None else {"t": 4, "seed": 7, "scenario": "s", "translation_frame_id": "tr4", "selected_action_channels": "exploration_injection", "translation_unresolved_flags": ""}]),
        "action_frame": pd.DataFrame(action if action is not None else [{"t": 4, "seed": 7, "scenario": "s", "action_frame_id": "a4", "action_channel": "exploration_injection", "action_strength": 0.08, "target_count": 1}]),
        "v2_resource_trace": pd.DataFrame([{"t": 0, "shared_resource": 0.8, "commons_health": 0.8, "private_resource_mean": 0.8}, {"t": 4, "shared_resource": 0.8, "commons_health": 0.8, "private_resource_mean": 0.8}]),
        "v2_game_trace": pd.DataFrame([{"t": 0, "local_payoff": 0.8, "short_term_payoff": 0.8}, {"t": 4, "local_payoff": 0.8, "short_term_payoff": 0.8}]),
        "v2_action_effect_trace": pd.DataFrame([{"t": 4, "net_public_effect_score": 0.1, "net_hidden_effect_score": 0.0, "exploration_delta": 0.1, "reversibility_delta": 0.1, "hidden_damage_delta": 0.0, "fatigue_delta": 0.0, "resource_inequality_delta": 0.0, "action_cost_effect": 0.0}]),
    }
    out.update(extra)
    return out


def _window(out):
    summary = build_observation_window_summary("unit", _cfg(), out)
    return next(w for w in summary["windows"] if w["window_name"] == "pressure_action_translation_audit_window")


def _d(window, key):
    return window["derived_fields"][key]["value"]


def test_core_fields_present_is_not_unresolved_and_ratio():
    window = _window(_out())
    assert window["window_name"] == "pressure_action_translation_audit_window"
    assert window["status_label"] != "unresolved"
    assert not [f for f in window["unresolved_flags"] if f.startswith("unresolved_core_")]
    assert _d(window, "pressure_to_action_ratio") == pytest.approx(0.08 / 0.24)


def test_channel_alignment_high_and_low():
    high = _window(_out())
    low = _window(_out(action=[{"action_channel": "volatility_damping", "action_strength": 0.08, "target_count": 1}]))
    assert _d(high, "channel_alignment_proxy") == pytest.approx(1.0)
    assert _d(low, "channel_alignment_proxy") == pytest.approx(0.0)
    assert "channel_alignment_low" in low["warning_flags"]


def test_gate_passed_action_is_consistent_and_gate_blocked_action_is_critical():
    passed = _window(_out())
    assert _d(passed, "gate_action_consistency_proxy") == pytest.approx(1.0)
    assert "critical_gate_blocked_but_action_emitted" not in passed["warning_flags"]
    blocked = _window(_out(gate={"gate_passed": False, "gate_blocked": True}))
    assert blocked["status_label"] in {"warning", "critical"}
    assert "critical_gate_blocked_but_action_emitted" in blocked["warning_flags"]


def test_under_and_over_action_flags():
    under = _window(_out(action=[{"action_channel": "exploration_injection", "action_strength": 0.02, "target_count": 1}]))
    assert under["status_label"] == "warning"
    assert "under_action_for_pressure" in under["warning_flags"]
    over = _window(_out(pressure={"pressure_norm": 0.02, "dominant_pressure_axis": "Exploration"}, action=[{"action_channel": "exploration_injection", "action_strength": 0.06, "target_count": 1}]))
    assert {"over_action_for_pressure", "critical_action_without_pressure"} & set(over["warning_flags"])


def test_high_pressure_no_op_rate_high_warns():
    action = [
        {"action_channel": "no_op", "action_strength": 0.0, "target_count": 1},
        {"action_channel": "no_op", "action_strength": 0.0, "target_count": 1},
        {"action_channel": "no_op", "action_strength": 0.0, "target_count": 1},
        {"action_channel": "exploration_injection", "action_strength": 0.02, "target_count": 1},
    ]
    window = _window(_out(action=action))
    assert "gate_passed_but_no_action_high" in window["warning_flags"]
    assert window["status_label"] == "warning"


def test_v2_result_fields_do_not_drive_status():
    window = _window(_out(v2_action_effect_trace=pd.DataFrame([{"t": 4, "net_public_effect_score": -9, "net_hidden_effect_score": 9, "exploration_delta": -9, "reversibility_delta": -9, "hidden_damage_delta": 9, "fatigue_delta": 9, "resource_inequality_delta": 9, "action_cost_effect": 9}]), v2_resource_trace=pd.DataFrame([{"t": 0, "shared_resource": 1, "commons_health": 1, "private_resource_mean": 1}, {"t": 4, "shared_resource": 0, "commons_health": 0, "private_resource_mean": 0}]), v2_game_trace=pd.DataFrame([{"t": 0, "local_payoff": 1, "short_term_payoff": 1}, {"t": 4, "local_payoff": 0, "short_term_payoff": 0}])))
    assert window["status_label"] == "healthy"


def test_pressure_core_and_action_frame_missing_are_unresolved():
    assert _window(_out(pressure={}))["status_label"] == "unresolved"
    missing_action = _out()
    missing_action["action_frame"] = pd.DataFrame()
    window = _window(missing_action)
    assert window["status_label"] == "unresolved"
    assert "unresolved_core_action_frame" in window["unresolved_flags"]


def test_pairing_keys_and_weak_pairing_context():
    window = _window(_out())
    assert window["context_fields"]["pairing_keys"]["action_frame_id"] == "a4"
    weak = _window(_out(pressure={"pressure_norm": 0.24, "dominant_pressure_axis": "Exploration"}, gate={"gate_passed": True, "gate_blocked": False}, translation={"selected_action_channels": "exploration_injection", "translation_unresolved_flags": ""}, action=[{"action_channel": "exploration_injection", "action_strength": 0.08, "target_count": 1}]))
    assert "weak_pairing_context" in weak["context_fields"]["flags"]


def test_safety_projection_context_not_critical_by_itself():
    window = _window(_out(gate={"gate_passed": True, "gate_blocked": False, "safety_projection_applied": True}))
    assert "safety_projection_applied_context" in window["context_fields"]["flags"]
    assert window["status_label"] != "critical"


def test_translation_missing_but_action_emitted_not_healthy():
    out = _out()
    out["translation_trace"] = pd.DataFrame()
    out["action_frame"] = pd.DataFrame([{"action_channel": "exploration_injection", "action_strength": 0.25, "target_count": 1}])
    window = _window(out)
    assert {"unresolved_core_translation_log", "critical_translation_missing_but_action_emitted"} & (set(window["unresolved_flags"]) | set(window["warning_flags"]))
    assert window["status_label"] in {"unresolved", "warning", "critical"}
