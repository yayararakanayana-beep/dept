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


def _base_out(resource=None, game=None, hidden=None):
    return {
        "v2_resource_trace": pd.DataFrame(resource if resource is not None else [
            {"t": 0, "shared_resource": 0.5, "commons_health": 0.6, "private_resource_mean": 0.7, "resource_pressure": 0.2, "resource_inequality": 0.2},
            {"t": 2, "shared_resource": 0.6, "commons_health": 0.7, "private_resource_mean": 0.8, "resource_pressure": 0.3, "resource_inequality": 0.25},
        ]),
        "v2_game_trace": pd.DataFrame(game if game is not None else [
            {"t": 0, "agent": "a", "local_payoff": 0.4, "short_term_payoff": 0.5, "long_term_health_proxy": 0.8},
            {"t": 0, "agent": "b", "local_payoff": 0.6, "short_term_payoff": 0.5, "long_term_health_proxy": 0.8},
            {"t": 2, "agent": "a", "local_payoff": 0.7, "short_term_payoff": 0.7, "long_term_health_proxy": 0.7},
            {"t": 2, "agent": "b", "local_payoff": 0.9, "short_term_payoff": 0.7, "long_term_health_proxy": 0.7},
        ]),
        "v2_hidden_trace": pd.DataFrame(hidden if hidden is not None else [
            {"t": 0, "private_resource": 0.7, "hidden_damage": 0.0, "fatigue": 0.0, "latent_pressure": 0.0, "defensiveness": 0.0},
            {"t": 2, "private_resource": 0.8, "hidden_damage": 0.0, "fatigue": 0.0, "latent_pressure": 0.0, "defensiveness": 0.0},
        ]),
    }


def _window(out):
    summary = build_observation_window_summary("unit", _cfg(), out)
    return next(w for w in summary["windows"] if w["window_name"] == "v2_direct_growth_window")


def _value(window, field, group="derived_fields"):
    return window[group][field]["value"]


def test_two_timepoints_do_not_unresolve_and_shared_resource_delta():
    window = _window(_base_out())
    assert window["window_name"] == "v2_direct_growth_window"
    assert window["status_label"] != "unresolved"
    assert not [flag for flag in window["unresolved_flags"] if flag.startswith("unresolved_core_")]
    assert _value(window, "shared_resource_delta") == pytest.approx(0.1)


def test_local_payoff_mean_delta_and_direct_growth_delta():
    window = _window(_base_out())
    assert _value(window, "local_payoff_mean_delta") == pytest.approx(0.3)
    assert round(_value(window, "resource_growth_delta"), 10) == round((0.1 + 0.1 + 0.1) / 3, 10)
    assert round(_value(window, "payoff_growth_delta"), 10) == round((0.3 + 0.2) / 2, 10)
    assert round(_value(window, "direct_growth_delta"), 10) == round((_value(window, "resource_growth_delta") + _value(window, "payoff_growth_delta")) / 2, 10)


def test_negative_delta_is_preserved_without_hidden_burden_status_effect():
    out = _base_out(
        resource=[
            {"t": 0, "shared_resource": 0.8, "commons_health": 0.8, "private_resource_mean": 0.8},
            {"t": 2, "shared_resource": 0.7, "commons_health": 0.7, "private_resource_mean": 0.7},
        ],
        game=[
            {"t": 0, "local_payoff": 0.8, "short_term_payoff": 0.8},
            {"t": 2, "local_payoff": 0.7, "short_term_payoff": 0.7},
        ],
        hidden=[{"t": 0, "hidden_damage": 1.0, "fatigue": 1.0, "latent_pressure": 1.0, "defensiveness": 1.0}, {"t": 2, "hidden_damage": 1.0, "fatigue": 1.0, "latent_pressure": 1.0, "defensiveness": 1.0}],
    )
    window = _window(out)
    assert _value(window, "shared_resource_delta") < 0
    assert _value(window, "direct_growth_delta") < 0


def test_excluded_hidden_burden_fields_do_not_drive_status():
    out = _base_out(hidden=[
        {"t": 0, "private_resource": 0.7, "hidden_damage": 1.0, "fatigue": 1.0, "latent_pressure": 1.0, "defensiveness": 1.0},
        {"t": 2, "private_resource": 0.8, "hidden_damage": 1.0, "fatigue": 1.0, "latent_pressure": 1.0, "defensiveness": 1.0},
    ])
    window = _window(out)
    assert window["status_label"] == "healthy"


def test_missing_t_or_one_common_timepoint_is_unresolved_not_watch():
    out = _base_out()
    out["v2_resource_trace"] = out["v2_resource_trace"].drop(columns=["t"])
    window = _window(out)
    assert window["status_label"] == "unresolved"
    assert "unresolved_core_time_axis_v2_resource_trace" in window["unresolved_flags"]

    window = _window(_base_out(resource=[{"t": 0, "shared_resource": 0.5, "commons_health": 0.5, "private_resource_mean": 0.5}], game=[{"t": 0, "local_payoff": 0.5, "short_term_payoff": 0.5}]))
    assert window["status_label"] == "unresolved"
    assert "unresolved_core_insufficient_common_time_history" in window["unresolved_flags"]


def test_private_resource_mean_fallback_from_hidden_trace():
    out = _base_out(resource=[
        {"t": 0, "shared_resource": 0.5, "commons_health": 0.6},
        {"t": 2, "shared_resource": 0.6, "commons_health": 0.7},
    ], hidden=[
        {"t": 0, "agent": "a", "private_resource": 0.4}, {"t": 0, "agent": "b", "private_resource": 0.6},
        {"t": 2, "agent": "a", "private_resource": 0.7}, {"t": 2, "agent": "b", "private_resource": 0.9},
    ])
    window = _window(out)
    assert window["status_label"] != "unresolved"
    assert _value(window, "private_resource_mean_delta") == pytest.approx(0.3)


def test_context_fields_do_not_drive_status():
    out = _base_out(resource=[
        {"t": 0, "shared_resource": 0.5, "commons_health": 0.6, "private_resource_mean": 0.7, "resource_pressure": 0.0, "resource_inequality": 0.0},
        {"t": 2, "shared_resource": 0.6, "commons_health": 0.7, "private_resource_mean": 0.8, "resource_pressure": 1.0, "resource_inequality": 1.0},
    ], game=[
        {"t": 0, "local_payoff": 0.5, "short_term_payoff": 0.5, "long_term_health_proxy": 1.0},
        {"t": 2, "local_payoff": 0.7, "short_term_payoff": 0.7, "long_term_health_proxy": 0.0},
    ])
    window = _window(out)
    assert window["status_label"] == "healthy"
    assert _value(window, "resource_pressure_delta", "context_fields") == 1.0
    assert _value(window, "resource_inequality_delta", "context_fields") == 1.0
    assert _value(window, "long_term_health_proxy_delta", "context_fields") == -1.0


def test_latest_step_growth_delta_is_auxiliary():
    out = _base_out(resource=[
        {"t": 0, "shared_resource": 0.5, "commons_health": 0.5, "private_resource_mean": 0.5},
        {"t": 1, "shared_resource": 0.9, "commons_health": 0.9, "private_resource_mean": 0.9},
        {"t": 2, "shared_resource": 0.7, "commons_health": 0.7, "private_resource_mean": 0.7},
    ], game=[
        {"t": 0, "local_payoff": 0.5, "short_term_payoff": 0.5},
        {"t": 1, "local_payoff": 0.9, "short_term_payoff": 0.9},
        {"t": 2, "local_payoff": 0.7, "short_term_payoff": 0.7},
    ])
    window = _window(out)
    assert round(_value(window, "direct_growth_delta"), 10) == 0.2
    assert round(_value(window, "latest_step_growth_delta"), 10) == -0.2
    assert window["status_label"] == "healthy"
