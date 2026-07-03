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


def _base(**overrides):
    hidden = {"t": 1, "hidden_damage": 0.1, "fatigue": 0.1, "latent_pressure": 0.1, "defensiveness": 0.1, "opportunism": 0.1, "cooperation_intent": 0.9, "private_resource": 0.9}
    resource = {"t": 1, "resource_pressure": 0.1, "resource_inequality": 0.1, "private_resource_min": 0.9, "private_resource_std": 0.1, "shared_resource": 0.9, "commons_health": 0.9, "private_resource_mean": 0.9}
    info = {"t": 1, "observed_vs_hidden_gap_proxy": 0.1, "information_distortion_mean": 0.1, "information_quality_mean": 0.9, "information_flow_mean": 0.9}
    hidden.update(overrides.pop("hidden", {})); resource.update(overrides.pop("resource", {})); info.update(overrides.pop("info", {}))
    out = {
        "v2_hidden_trace": pd.DataFrame([hidden]),
        "v2_resource_trace": pd.DataFrame([resource]),
        "v2_information_trace": pd.DataFrame([info]),
        "v2_game_trace": pd.DataFrame([{"t": 0, "local_payoff": 0.8, "short_term_payoff": 0.8}, {"t": 1, "local_payoff": 0.8, "short_term_payoff": 0.8}]),
        "v2_action_effect_trace": pd.DataFrame([{"t": 1, "net_public_effect_score": 0.0, "net_hidden_effect_score": 0.0, "exploration_delta": 0.0, "reversibility_delta": 0.0, "hidden_damage_delta": 0.0, "fatigue_delta": 0.0, "resource_inequality_delta": 0.0, "action_cost_effect": 0.0}]),
        "pressure_trace": pd.DataFrame([{"t": 1, "pressure_norm": 0.1, "dominant_pressure_axis": "Exploration"}]),
        "gate_trace": pd.DataFrame([{"t": 1, "gate_passed": True, "gate_blocked": False}]),
        "translation_trace": pd.DataFrame([{"t": 1, "selected_action_channels": "exploration_injection"}]),
        "action_frame": pd.DataFrame([{"t": 1, "action_channel": "exploration_injection", "action_strength": 0.05, "target_count": 1}]),
    }
    out.update(overrides)
    return out


def _window(out):
    return next(w for w in build_observation_window_summary("unit", _cfg(), out)["windows"] if w["window_name"] == "v2_direct_risk_band_window")


def _d(w, key): return w["derived_fields"][key]["value"]


def test_core_fields_present_and_main_derived_scores():
    w = _window(_base(hidden={"hidden_damage": .3, "fatigue": .4, "latent_pressure": .5, "defensiveness": .2, "opportunism": .4, "cooperation_intent": .7}, resource={"resource_pressure": .2, "resource_inequality": .3, "private_resource_min": .6, "private_resource_std": .2}, info={"observed_vs_hidden_gap_proxy": .2, "information_distortion_mean": .4, "information_quality_mean": .8, "information_flow_mean": .7}))
    assert w["status_label"] != "unresolved"
    assert not [f for f in w["unresolved_flags"] if f.startswith("unresolved_core_")]
    assert _d(w, "internal_damage_risk") == pytest.approx((.3+.4+.5)/3)
    assert _d(w, "closure_defense_risk") == pytest.approx((.2+.4+.3)/3)
    assert _d(w, "resource_stress_risk") == pytest.approx((.2+.3+.4+.2)/4)
    assert _d(w, "information_blindness_risk") == pytest.approx((.2+.4+.2+.3)/4)
    assert _d(w, "direct_risk_band_score") == pytest.approx(max(_d(w, "internal_damage_risk"), _d(w, "closure_defense_risk"), _d(w, "resource_stress_risk"), _d(w, "information_blindness_risk")))
    assert _d(w, "systemic_risk_pressure") == pytest.approx(sum(_d(w, k) for k in ["internal_damage_risk", "closure_defense_risk", "resource_stress_risk", "information_blindness_risk"])/4)


@pytest.mark.parametrize("updates,flag", [
    ({"hidden": {"hidden_damage": .7}, "info": {"observed_vs_hidden_gap_proxy": .65}}, "hidden_damage_blindness_risk"),
    ({"hidden": {"fatigue": .7, "latent_pressure": .65}}, "fatigue_pressure_accumulation_risk"),
    ({"resource": {"resource_pressure": .7, "resource_inequality": .65}}, "resource_squeeze_inequality_risk"),
    ({"hidden": {"defensiveness": .7, "cooperation_intent": .35}}, "defensive_noncooperation_risk"),
    ({"info": {"information_distortion_mean": .7, "information_quality_mean": .35}}, "information_corruption_risk"),
    ({"info": {"information_flow_mean": .35, "observed_vs_hidden_gap_proxy": .7}}, "information_blockage_risk"),
    ({"resource": {"private_resource_min": .35, "private_resource_std": .7}}, "local_depletion_inequality_risk"),
    ({"hidden": {"opportunism": .7}, "resource": {"resource_pressure": .65}}, "opportunistic_extraction_risk"),
])
def test_combination_risk_flags(updates, flag):
    w = _window(_base(**updates))
    assert _d(w, flag) >= .60
    assert flag in w["warning_flags"]
    assert w["status_label"] in {"warning", "critical"}


def test_healthy_core_missing_auxiliary_missing_and_fallback():
    assert _window(_base())["status_label"] == "healthy"
    out = _base(); out["v2_hidden_trace"] = out["v2_hidden_trace"].drop(columns=["hidden_damage"])
    w = _window(out)
    assert w["status_label"] == "unresolved" and "unresolved_core_hidden_damage" in w["unresolved_flags"]
    out = _base(); out["v2_hidden_trace"] = out["v2_hidden_trace"].drop(columns=["opportunism", "cooperation_intent"])
    w = _window(out)
    assert w["status_label"] != "unresolved"
    assert "missing_auxiliary_opportunism" in w["context_fields"]["flags"]
    out = _base(); out["v2_resource_trace"] = out["v2_resource_trace"].drop(columns=["private_resource_min", "private_resource_std"])
    w = _window(out)
    assert {"private_resource_min_fallback_from_hidden", "private_resource_std_fallback_from_hidden"} <= set(w["context_fields"]["flags"])


def test_external_benefit_growth_h11_translation_and_dept_fields_ignored():
    w = _window(_base(resource={"visible_benefit_proxy": 99}, info={"direct_growth_delta": 99, "h11_action_effect_proxy": 99}, world_transition_audit=pd.DataFrame([{"H11": 99, "G": 99, "K": 99, "O_t": 99, "dept_risk": 99, "world_transition_audit": 99}]), action_frame=pd.DataFrame([{"t": 1, "action_strength": 99, "pressure_to_action_ratio": 99, "net_hidden_effect_score": 99}])) )
    assert w["status_label"] not in {"warning", "critical"}


def test_time_axis_latest_and_missing_time_mean_context():
    out = _base()
    out["v2_hidden_trace"] = pd.DataFrame([{**out["v2_hidden_trace"].iloc[0].to_dict(), "t": 0, "hidden_damage": .9}, {**out["v2_hidden_trace"].iloc[0].to_dict(), "t": 2, "hidden_damage": .2}])
    assert next(e for e in _window(out)["evidence_fields"] if e["field"] == "hidden_damage")["value"] == pytest.approx(.2)
    out = _base()
    for key in ["v2_hidden_trace", "v2_resource_trace", "v2_information_trace"]:
        out[key] = out[key].drop(columns=["t"])
    w = _window(out)
    assert next(e for e in w["evidence_fields"] if e["field"] == "hidden_damage")["method"] == "all_row_mean_no_time_axis"
    assert "time_axis_missing_context" in w["context_fields"]["flags"]
