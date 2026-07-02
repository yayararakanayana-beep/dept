from pathlib import Path
from types import SimpleNamespace
import sys

import pandas as pd
import pytest

LOCALPREP_ROOT = Path(__file__).resolve().parents[1] / "localprep1" / "dept"
if str(LOCALPREP_ROOT) not in sys.path:
    sys.path.insert(0, str(LOCALPREP_ROOT))

from scripts.observation_window_summary import build_observation_window_summary, flatten_observation_windows


def _cfg():
    return SimpleNamespace(validation_profile_name="smoke", world_profile_name="v2", action_profile_name="action_default")


def _summary(out):
    return build_observation_window_summary("unit", _cfg(), out)


def _window(out):
    return next(w for w in _summary(out)["windows"] if w["window_name"] == "v2_direct_benefit_window")


def _base_out(**overrides):
    out = {
        "v2_resource_trace": pd.DataFrame([{"t": 1, "shared_resource": 0.70, "commons_health": 0.80, "private_resource_mean": 0.60, "resource_pressure": 0.40}]),
        "v2_game_trace": pd.DataFrame([
            {"t": 1, "entity": "a", "local_payoff": 0.50, "short_term_payoff": 0.40},
            {"t": 1, "entity": "b", "local_payoff": 0.70, "short_term_payoff": 0.60},
        ]),
    }
    out.update(overrides)
    return out


def _evidence_value(window, field):
    return next(item["value"] for item in window["evidence_fields"] if item["field"] == field)


def test_core_fields_present_is_not_unresolved():
    window = _window(_base_out())
    assert window["window_name"] == "v2_direct_benefit_window"
    assert window["status_label"] != "unresolved"
    assert not any(flag.startswith("unresolved_core_") for flag in window["unresolved_flags"])


def test_total_resource_proxy_uses_equal_mean_core_resource_fields():
    window = _window(_base_out())
    assert window["derived_fields"]["total_resource_proxy"]["value"] == (0.70 + 0.80 + 0.60) / 3


def test_visible_benefit_proxy_uses_equal_mean_with_local_payoff_mean():
    window = _window(_base_out())
    assert window["derived_fields"]["visible_benefit_proxy"]["value"] == (0.70 + 0.80 + 0.60 + 0.60) / 4


def test_short_term_benefit_proxy_uses_payoff_means():
    window = _window(_base_out())
    assert window["derived_fields"]["short_term_benefit_proxy"]["value"] == (0.50 + 0.60) / 2


def test_excluded_hidden_burden_fields_do_not_drive_status():
    hidden = pd.DataFrame([{"t": 1, "hidden_damage": 1.0, "fatigue": 1.0, "latent_pressure": 1.0, "defensiveness": 1.0}])
    window = _window(_base_out(v2_hidden_trace=hidden))
    assert window["status_label"] == "healthy"
    assert not any("hidden" in flag or "fatigue" in flag or "latent" in flag or "defensiveness" in flag for flag in window["warning_flags"])


def test_core_missing_is_unresolved_not_watch_and_has_no_derived_fields():
    resource = pd.DataFrame([{"t": 1, "commons_health": 0.80, "private_resource_mean": 0.60}])
    window = _window(_base_out(v2_resource_trace=resource))
    assert window["status_label"] == "unresolved"
    assert "unresolved_core_shared_resource" in window["unresolved_flags"]
    assert window["derived_fields"] == {}


def test_latest_t_only_drives_direct_benefit_proxies():
    resource = pd.DataFrame([
        {"t": 1, "shared_resource": 0.0, "commons_health": 0.0, "private_resource_mean": 0.0},
        {"t": 2, "shared_resource": 0.9, "commons_health": 0.8, "private_resource_mean": 0.7},
    ])
    game = pd.DataFrame([
        {"t": 1, "local_payoff": 0.0, "short_term_payoff": 0.0},
        {"t": 2, "local_payoff": 0.6, "short_term_payoff": 0.5},
        {"t": 2, "local_payoff": 0.8, "short_term_payoff": 0.7},
    ])
    window = _window(_base_out(v2_resource_trace=resource, v2_game_trace=game))
    assert window["derived_fields"]["total_resource_proxy"]["value"] == pytest.approx((0.9 + 0.8 + 0.7) / 3)
    assert window["derived_fields"]["short_term_benefit_proxy"]["value"] == pytest.approx((0.6 + 0.7) / 2)


def test_private_resource_mean_falls_back_to_hidden_private_resource_latest_mean():
    resource = pd.DataFrame([{"t": 1, "shared_resource": 0.70, "commons_health": 0.80}])
    hidden = pd.DataFrame([
        {"t": 1, "entity": "a", "private_resource": 0.40},
        {"t": 1, "entity": "b", "private_resource": 0.60},
    ])
    window = _window(_base_out(v2_resource_trace=resource, v2_hidden_trace=hidden))
    assert window["status_label"] != "unresolved"
    assert _evidence_value(window, "private_resource_mean") == 0.50


def test_csv_flatten_includes_derived_and_context_json_columns():
    flat = flatten_observation_windows(_summary(_base_out()))
    assert "derived_fields_json" in flat.columns
    assert "context_fields_json" in flat.columns
