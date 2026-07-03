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


def _core(**overrides):
    row = {
        "t": 1,
        "net_public_effect_score": 0.20,
        "net_hidden_effect_score": 0.01,
        "exploration_delta": 0.10,
        "reversibility_delta": 0.10,
        "hidden_damage_delta": 0.01,
        "fatigue_delta": 0.01,
        "resource_inequality_delta": 0.01,
        "action_cost_effect": 0.01,
    }
    row.update(overrides)
    return row


def _out(action_rows=None, **extra):
    out = {
        "v2_action_effect_trace": pd.DataFrame(action_rows if action_rows is not None else [_core()]),
        "v2_resource_trace": pd.DataFrame([{"t": 1, "shared_resource": 0.8, "commons_health": 0.8, "resource_pressure": 0.2, "resource_inequality": 0.2}]),
        "v2_game_trace": pd.DataFrame([{"t": 1, "long_term_health_proxy": 0.8, "cooperate_tendency": 0.5, "defend_tendency": 0.2, "explore_tendency": 0.5, "extract_tendency": 0.2, "connect_tendency": 0.5, "amplify_tendency": 0.5}]),
        "v2_information_trace": pd.DataFrame([{"t": 1, "observed_vs_hidden_gap_proxy": 0.1, "information_quality_mean": 0.8, "information_flow_mean": 0.8, "information_distortion_mean": 0.1}]),
    }
    out.update(extra)
    return out


def _window(out):
    summary = build_observation_window_summary("unit", _cfg(), out)
    return next(w for w in summary["windows"] if w["window_name"] == "v2_h11_action_effect_window")


def _d(window, field):
    return window["derived_fields"][field]["value"]


def test_core_fields_present_is_not_unresolved_and_hidden_burden_interpreted():
    window = _window(_out())
    assert window["window_name"] == "v2_h11_action_effect_window"
    assert window["status_label"] != "unresolved"
    assert not [f for f in window["unresolved_flags"] if f.startswith("unresolved_core_")]
    assert _d(window, "hidden_effect_burden_proxy") == pytest.approx(0.01)
    assert window["derived_fields"]["hidden_effect_burden_proxy"]["higher_is"] == "worse"
    hidden_evidence = next(e for e in window["evidence_fields"] if e["field"] == "net_hidden_effect_score")
    assert hidden_evidence["interpretation"] == "hidden_burden_magnitude"
    assert hidden_evidence["higher_is"] == "worse"


def test_surface_and_hidden_state_and_h11_proxy_subtract_burdens():
    window = _window(_out([_core(net_public_effect_score=0.06, net_hidden_effect_score=0.12, exploration_delta=0.02, reversibility_delta=0.04, hidden_damage_delta=0.06, fatigue_delta=0.02, resource_inequality_delta=0.03, action_cost_effect=0.06)]))
    assert _d(window, "surface_opening_effect_proxy") == pytest.approx(0.03)
    assert _d(window, "hidden_state_burden_proxy") == pytest.approx(0.04)
    expected = (0.06 + 0.03 - 0.12 - 0.04 - 0.03 - 0.06) / 6
    assert _d(window, "h11_action_effect_proxy") == pytest.approx(expected)
    assert expected < 0


def test_high_hidden_burden_warns_or_critical_and_not_healthy():
    window = _window(_out([_core(net_public_effect_score=0.20, net_hidden_effect_score=0.13)]))
    assert window["status_label"] in {"warning", "critical"}
    assert {"hidden_effect_burden_high", "critical_hidden_effect_burden_spike"} & set(window["warning_flags"])


def test_good_public_effect_low_burden_is_healthy_and_zero_effect_is_watch():
    assert _window(_out())["status_label"] == "healthy"
    zero = {k: 0.0 for k in _core() if k != "t"}
    window = _window(_out([{"t": 1, **zero}]))
    assert window["status_label"] == "watch"


def test_pressure_action_translation_fields_are_ignored():
    row = _core(pressure_norm=999, gate_pressure_norm=999, gate_integral_norm=999, action_channel="x", action_strength=999, action_mass_by_channel={"x": 999})
    window = _window(_out([row]))
    assert window["status_label"] == "healthy"


def test_context_fields_do_not_drive_status():
    window = _window(_out(
        v2_resource_trace=pd.DataFrame([{"t": 1, "resource_pressure": 1.0, "resource_inequality": 1.0}]),
        v2_game_trace=pd.DataFrame([{"t": 1, "long_term_health_proxy": 0.0, "defend_tendency": 1.0, "extract_tendency": 1.0}]),
        v2_information_trace=pd.DataFrame([{"t": 1, "observed_vs_hidden_gap_proxy": 1.0, "information_quality_mean": 0.0, "information_distortion_mean": 1.0}]),
    ))
    assert window["status_label"] == "healthy"
    assert "flags" in window["context_fields"]
    assert "resource_pressure_high_context" in window["context_fields"]["flags"]


def test_core_missing_is_unresolved_not_watch():
    row = _core()
    row.pop("action_cost_effect")
    window = _window(_out([row]))
    assert window["status_label"] == "unresolved"
    assert "unresolved_core_action_cost_effect" in window["unresolved_flags"]


def test_time_axis_latest_mean_and_no_time_axis_all_row_mean():
    window = _window(_out([_core(t=0, net_public_effect_score=-1.0), _core(t=1, net_public_effect_score=0.08)]))
    evidence = next(e for e in window["evidence_fields"] if e["field"] == "net_public_effect_score")
    assert evidence["value"] == pytest.approx(0.08)
    assert evidence["method"] == "latest_t_mean"

    rows = [_core(net_public_effect_score=0.02), _core(net_public_effect_score=0.04)]
    for row in rows:
        row.pop("t")
    window = _window(_out(rows))
    evidence = next(e for e in window["evidence_fields"] if e["field"] == "net_public_effect_score")
    assert evidence["value"] == pytest.approx(0.03)
    assert evidence["method"] == "all_row_mean_no_time_axis"
    assert "time_axis_missing_context" in window["context_fields"]["flags"]
    assert window["status_label"] != "unresolved"


def test_negative_h11_action_effect_proxy_is_not_clipped():
    window = _window(_out([_core(net_public_effect_score=0.0, net_hidden_effect_score=0.12, hidden_damage_delta=0.12, fatigue_delta=0.12, action_cost_effect=0.12)]))
    assert _d(window, "h11_action_effect_proxy") < 0
