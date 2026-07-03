from pathlib import Path
from types import SimpleNamespace
import json
import sys

import pandas as pd
import pytest

LOCALPREP_ROOT = Path(__file__).resolve().parents[1] / "localprep1" / "dept"
if str(LOCALPREP_ROOT) not in sys.path:
    sys.path.insert(0, str(LOCALPREP_ROOT))

from scripts.observation_window_summary import build_observation_window_summary, flatten_observation_windows
from scripts.probe_observation_window_exports import validate_output_dir

EXPECTED_WINDOWS = [
    "v2_direct_benefit_window",
    "v2_h11_action_effect_window",
    "pressure_action_translation_audit_window",
    "v2_direct_risk_band_window",
    "v2_direct_growth_window",
    "composite_balance_window",
]
LEGACY_WINDOWS = {"pressure_action_alignment_window", "risk_band_window", "h11_possibility_distribution_window", "direct_benefit_window", "direct_growth_window"}
ALLOWED_STATUS = {"healthy", "watch", "warning", "critical", "unresolved"}


def _cfg():
    return SimpleNamespace(validation_profile_name="smoke", world_profile_name="v2", action_profile_name="action_default")


def _base_out(**overrides):
    out = {
        "v2_hidden_trace": pd.DataFrame([
            {"t": 0, "hidden_damage": .08, "fatigue": .08, "latent_pressure": .08, "defensiveness": .08, "opportunism": .08, "cooperation_intent": .92, "private_resource": .72},
            {"t": 1, "hidden_damage": .10, "fatigue": .10, "latent_pressure": .10, "defensiveness": .10, "opportunism": .10, "cooperation_intent": .90, "private_resource": .82},
        ]),
        "v2_resource_trace": pd.DataFrame([
            {"t": 0, "shared_resource": .70, "commons_health": .72, "private_resource_mean": .74, "resource_pressure": .12, "resource_inequality": .10, "private_resource_min": .65, "private_resource_std": .08},
            {"t": 1, "shared_resource": .82, "commons_health": .84, "private_resource_mean": .86, "resource_pressure": .14, "resource_inequality": .12, "private_resource_min": .76, "private_resource_std": .09},
        ]),
        "v2_information_trace": pd.DataFrame([
            {"t": 0, "observed_vs_hidden_gap_proxy": .10, "information_distortion_mean": .10, "information_quality_mean": .90, "information_flow_mean": .90},
            {"t": 1, "observed_vs_hidden_gap_proxy": .10, "information_distortion_mean": .10, "information_quality_mean": .90, "information_flow_mean": .90},
        ]),
        "v2_game_trace": pd.DataFrame([
            {"t": 0, "agent": "a", "local_payoff": .64, "short_term_payoff": .62},
            {"t": 0, "agent": "b", "local_payoff": .66, "short_term_payoff": .64},
            {"t": 1, "agent": "a", "local_payoff": .78, "short_term_payoff": .76},
            {"t": 1, "agent": "b", "local_payoff": .80, "short_term_payoff": .78},
        ]),
        "v2_action_effect_trace": pd.DataFrame([{"t": 1, "net_public_effect_score": .20, "net_hidden_effect_score": -.01, "exploration_delta": .10, "reversibility_delta": .10, "hidden_damage_delta": .0, "fatigue_delta": .0, "resource_inequality_delta": .0, "action_cost_effect": .01}]),
        "pressure_trace": pd.DataFrame([{"t": 1, "run_id": "r", "scenario": "s", "seed": 1, "pressure_norm": .50, "dominant_pressure_axis": "Exploration", "pressure_component_distribution": "Exploration:1.0"}]),
        "gate_trace": pd.DataFrame([{"t": 1, "run_id": "r", "scenario": "s", "seed": 1, "gate_passed": True, "gate_blocked": False}]),
        "translation_trace": pd.DataFrame([{"t": 1, "run_id": "r", "scenario": "s", "seed": 1, "selected_action_channels": "exploration_injection", "translation_confidence": .9}]),
        "action_frame": pd.DataFrame([{"t": 1, "run_id": "r", "scenario": "s", "seed": 1, "action_channel": "exploration_injection", "action_strength": .45, "target_count": 1}]),
    }
    out.update(overrides)
    return out


def _summary(out):
    return build_observation_window_summary("phase2g18r7", _cfg(), out)


def _window(summary, name):
    return next(w for w in summary["windows"] if w["window_name"] == name)


def _derived(window, key):
    return window["derived_fields"][key]["value"]


def _statuses(summary):
    return {w["window_name"]: w["status_label"] for w in summary["windows"]}


def _flags(window):
    return set(window["warning_flags"]) | set(window["unresolved_flags"])


def test_six_windows_emit_expected_order_and_schema():
    summary = _summary(_base_out())
    assert [w["window_name"] for w in summary["windows"]] == EXPECTED_WINDOWS
    for window in summary["windows"]:
        assert set(window) == {"window_name", "status_label", "evidence_fields", "derived_fields", "context_fields", "warning_flags", "unresolved_flags", "short_reason"}
        assert window["status_label"] in ALLOWED_STATUS
        assert isinstance(window["evidence_fields"], list)
        assert isinstance(window["derived_fields"], dict)
        assert isinstance(window["context_fields"], dict)
        assert isinstance(window["warning_flags"], list)
        assert isinstance(window["unresolved_flags"], list)
        assert isinstance(window["short_reason"], str) and window["short_reason"]


def test_no_legacy_window_names_remain_in_emitted_windows():
    assert not (set(w["window_name"] for w in _summary(_base_out())["windows"]) & LEGACY_WINDOWS)


def test_all_healthy_scenario():
    statuses = _statuses(_summary(_base_out()))
    assert "critical" not in statuses.values()
    assert all(statuses[name] != "unresolved" for name in EXPECTED_WINDOWS)
    assert statuses["v2_direct_risk_band_window"] == "healthy"
    assert statuses["pressure_action_translation_audit_window"] in {"healthy", "watch"}
    assert statuses["composite_balance_window"] in {"healthy", "watch"}


def test_benefit_down_only_is_localized():
    out = _base_out(v2_resource_trace=pd.DataFrame([{ "t": 0, "shared_resource": .70, "commons_health": .72, "private_resource_mean": .74, "resource_pressure": .12, "resource_inequality": .10, "private_resource_min": .65, "private_resource_std": .08}, {"t": 1, "shared_resource": .20, "commons_health": .20, "private_resource_mean": .20, "resource_pressure": .14, "resource_inequality": .12, "private_resource_min": .76, "private_resource_std": .09}]), v2_game_trace=pd.DataFrame([{"t":0,"local_payoff":.20,"short_term_payoff":.20},{"t":1,"local_payoff":.20,"short_term_payoff":.20}]))
    s = _summary(out); statuses = _statuses(s)
    assert statuses["v2_direct_benefit_window"] in {"warning", "critical"}
    assert statuses["v2_direct_risk_band_window"] == "healthy"
    assert statuses["pressure_action_translation_audit_window"] in {"healthy", "watch"}
    assert statuses["v2_h11_action_effect_window"] in {"healthy", "watch"}
    assert statuses["composite_balance_window"] in {"warning", "critical"}
    assert _window(s, "v2_direct_benefit_window")["status_label"] in {"warning", "critical"}


def test_growth_down_only_is_localized():
    out = _base_out(v2_resource_trace=pd.DataFrame([{ "t":0,"shared_resource":.90,"commons_health":.90,"private_resource_mean":.90,"resource_pressure":.10,"resource_inequality":.10,"private_resource_min":.80,"private_resource_std":.08},{"t":1,"shared_resource":.62,"commons_health":.62,"private_resource_mean":.62,"resource_pressure":.10,"resource_inequality":.10,"private_resource_min":.80,"private_resource_std":.08}]), v2_game_trace=pd.DataFrame([{"t":0,"local_payoff":.90,"short_term_payoff":.90},{"t":1,"local_payoff":.62,"short_term_payoff":.62}]))
    s = _summary(out); statuses = _statuses(s)
    assert statuses["v2_direct_growth_window"] in {"warning", "critical"}
    assert statuses["v2_direct_benefit_window"] in {"watch", "healthy"}
    assert statuses["v2_direct_risk_band_window"] == "healthy"
    assert statuses["pressure_action_translation_audit_window"] in {"healthy", "watch"}
    assert "growth_preservation_reference" in _window(s, "composite_balance_window")["derived_fields"]
    assert _derived(_window(s, "composite_balance_window"), "growth_preservation_reference") < 0


def test_h11_effect_bad_only_is_localized():
    out = _base_out(v2_action_effect_trace=pd.DataFrame([{"t":1,"net_public_effect_score":-.2,"net_hidden_effect_score":-.4,"exploration_delta":-.2,"reversibility_delta":-.2,"hidden_damage_delta":.4,"fatigue_delta":.4,"resource_inequality_delta":.2,"action_cost_effect":.3}]))
    s = _summary(out); statuses = _statuses(s)
    assert statuses["v2_h11_action_effect_window"] in {"warning", "critical"}
    assert statuses["pressure_action_translation_audit_window"] in {"healthy", "watch"}
    assert statuses["v2_direct_risk_band_window"] == "healthy"
    assert statuses["v2_direct_benefit_window"] in {"healthy", "watch"}
    assert statuses["v2_direct_growth_window"] in {"healthy", "watch"}
    assert any("translation_effect" in f or "governance" in f for f in _flags(_window(s, "composite_balance_window")))


def test_translation_bad_only_is_localized():
    out = _base_out(pressure_trace=pd.DataFrame([{"t":1,"run_id":"r","scenario":"s","seed":1,"pressure_norm":.95,"dominant_pressure_axis":"Exploration"}]), gate_trace=pd.DataFrame([{"t":1,"run_id":"r","scenario":"s","seed":1,"gate_passed":True,"gate_blocked":False}]), action_frame=pd.DataFrame([{"t":1,"run_id":"r","scenario":"s","seed":1,"action_channel":"exploration_injection","action_strength":.02,"target_count":1}]))
    s = _summary(out); statuses = _statuses(s)
    assert statuses["pressure_action_translation_audit_window"] in {"warning", "critical"}
    assert statuses["v2_h11_action_effect_window"] in {"healthy", "watch"}
    assert statuses["v2_direct_risk_band_window"] == "healthy"
    assert statuses["v2_direct_benefit_window"] in {"healthy", "watch"}
    assert statuses["v2_direct_growth_window"] in {"healthy", "watch"}
    assert "translation_audit_reference" in _window(s, "composite_balance_window")["derived_fields"]


def test_risk_high_only_is_localized():
    out = _base_out(v2_hidden_trace=pd.DataFrame([{"t":0,"hidden_damage":.08,"fatigue":.08,"latent_pressure":.08,"defensiveness":.08,"opportunism":.08,"cooperation_intent":.90,"private_resource":.8},{"t":1,"hidden_damage":.85,"fatigue":.80,"latent_pressure":.82,"defensiveness":.75,"opportunism":.75,"cooperation_intent":.20,"private_resource":.8}]), v2_resource_trace=pd.DataFrame([{ "t":0,"shared_resource":.70,"commons_health":.72,"private_resource_mean":.74,"resource_pressure":.12,"resource_inequality":.10,"private_resource_min":.65,"private_resource_std":.08},{"t":1,"shared_resource":.82,"commons_health":.84,"private_resource_mean":.86,"resource_pressure":.14,"resource_inequality":.82,"private_resource_min":.20,"private_resource_std":.70}]), v2_information_trace=pd.DataFrame([{"t":0,"observed_vs_hidden_gap_proxy":.10,"information_distortion_mean":.10,"information_quality_mean":.90,"information_flow_mean":.90},{"t":1,"observed_vs_hidden_gap_proxy":.85,"information_distortion_mean":.80,"information_quality_mean":.20,"information_flow_mean":.20}]))
    s = _summary(out); statuses = _statuses(s)
    assert statuses["v2_direct_risk_band_window"] in {"warning", "critical"}
    assert statuses["v2_direct_benefit_window"] in {"healthy", "watch"}
    assert statuses["v2_direct_growth_window"] in {"healthy", "watch"}
    assert statuses["pressure_action_translation_audit_window"] in {"healthy", "watch"}
    assert "direct_risk_reference" in _window(s, "composite_balance_window")["derived_fields"]
    assert statuses["composite_balance_window"] in {"watch", "warning"}


def test_composite_tension_scenarios_are_not_masked():
    risk_high = _summary(_base_out(v2_hidden_trace=pd.DataFrame([{"t":1,"hidden_damage":.8,"fatigue":.8,"latent_pressure":.8,"defensiveness":.8,"opportunism":.8,"cooperation_intent":.2,"private_resource":.8}]), v2_information_trace=pd.DataFrame([{"t":1,"observed_vs_hidden_gap_proxy":.8,"information_distortion_mean":.8,"information_quality_mean":.2,"information_flow_mean":.2}])))
    assert _statuses(risk_high)["v2_direct_benefit_window"] in {"healthy", "watch"}
    assert _statuses(risk_high)["v2_direct_risk_band_window"] in {"warning", "critical"}
    assert {"benefit_risk_tension", "direct_risk_high_context"} & _flags(_window(risk_high, "composite_balance_window"))

    benefit_bad = _summary(_base_out(v2_resource_trace=pd.DataFrame([{"t":0,"shared_resource":.7,"commons_health":.7,"private_resource_mean":.7,"resource_pressure":.1,"resource_inequality":.1,"private_resource_min":.7,"private_resource_std":.1},{"t":1,"shared_resource":.18,"commons_health":.18,"private_resource_mean":.18,"resource_pressure":.1,"resource_inequality":.1,"private_resource_min":.7,"private_resource_std":.1}]), v2_game_trace=pd.DataFrame([{"t":0,"local_payoff":.7,"short_term_payoff":.7},{"t":1,"local_payoff":.18,"short_term_payoff":.18}])))
    assert {"governance_benefit_tension", "critical_governance_benefit_tension"} & _flags(_window(benefit_bad, "composite_balance_window"))

    growth_bad = _summary(_base_out(v2_resource_trace=pd.DataFrame([{"t":0,"shared_resource":.9,"commons_health":.9,"private_resource_mean":.9},{"t":1,"shared_resource":.55,"commons_health":.55,"private_resource_mean":.55}]), v2_game_trace=pd.DataFrame([{"t":0,"local_payoff":.9,"short_term_payoff":.9},{"t":1,"local_payoff":.55,"short_term_payoff":.55}])))
    assert {"governance_growth_tension", "critical_governance_growth_tension"} & _flags(_window(growth_bad, "composite_balance_window"))

    h11_bad = _summary(_base_out(v2_action_effect_trace=pd.DataFrame([{"t":1,"net_public_effect_score":-.2,"net_hidden_effect_score":-.4,"exploration_delta":-.2,"reversibility_delta":-.2,"hidden_damage_delta":.4,"fatigue_delta":.4,"resource_inequality_delta":.2,"action_cost_effect":.3}])))
    assert {"translation_effect_tension", "critical_translation_effect_tension"} & _flags(_window(h11_bad, "composite_balance_window"))


def test_core_missing_matrix():
    cases = [
        ("v2_direct_benefit_window", {"v2_resource_trace": _base_out()["v2_resource_trace"].drop(columns=["shared_resource"])}),
        ("v2_direct_growth_window", {"v2_resource_trace": _base_out()["v2_resource_trace"].drop(columns=["t"])}),
        ("v2_h11_action_effect_window", {"v2_action_effect_trace": pd.DataFrame([{"t":1}])}),
        ("pressure_action_translation_audit_window", {"pressure_trace": pd.DataFrame([{"t":1}])}),
        ("v2_direct_risk_band_window", {"v2_hidden_trace": _base_out()["v2_hidden_trace"].drop(columns=["hidden_damage"])}),
    ]
    for name, override in cases:
        w = _window(_summary(_base_out(**override)), name)
        assert w["status_label"] == "unresolved"
        assert w["unresolved_flags"]
    composite = _window(_summary(_base_out(v2_action_effect_trace=pd.DataFrame([{"t":1}]))), "composite_balance_window")
    assert composite["status_label"] == "unresolved"
    assert any("missing" in f for f in composite["unresolved_flags"])


def test_auxiliary_missing_matrix():
    risk = _window(_summary(_base_out(v2_hidden_trace=_base_out()["v2_hidden_trace"].drop(columns=["opportunism", "cooperation_intent"]), v2_resource_trace=_base_out()["v2_resource_trace"].drop(columns=["private_resource_min", "private_resource_std"]), v2_information_trace=_base_out()["v2_information_trace"].drop(columns=["information_quality_mean", "information_flow_mean"]))), "v2_direct_risk_band_window")
    assert risk["status_label"] != "unresolved"
    assert any("missing_auxiliary" in f for f in risk["context_fields"].get("flags", []))
    translation = _window(_summary(_base_out(translation_trace=pd.DataFrame([{"t":1,"run_id":"r","scenario":"s","seed":1,"selected_action_channels":"exploration_injection"}]))), "pressure_action_translation_audit_window")
    assert translation["status_label"] != "unresolved"
    composite = _window(_summary({k:v for k,v in _base_out().items() if k not in {"pressure_trace", "gate_trace", "translation_trace", "action_frame"}}), "composite_balance_window")
    assert composite["status_label"] != "unresolved"
    assert "translation_audit_status" in composite["context_fields"].get("auxiliary_context", {})


def test_export_json_csv_integrated_probe(tmp_path):
    summary = _summary(_base_out())
    flat = flatten_observation_windows(summary)
    outdir = tmp_path / "export"
    outdir.mkdir()
    (outdir / "observation_window_summary.json").write_text(json.dumps(summary, ensure_ascii=False, default=str), encoding="utf-8")
    flat.to_csv(outdir / "observation_window_summary.csv", index=False)
    result = validate_output_dir(outdir)
    assert result["csv_rows"] == 6
    assert list(flat["window_name"]) == EXPECTED_WINDOWS
    assert {"derived_fields_json", "context_fields_json"} <= set(flat.columns)
    assert "not runtime ActionModule inputs" in summary["boundary_note"]


def test_observation_windows_do_not_feed_runtime():
    source = (LOCALPREP_ROOT / "scripts" / "observation_window_summary.py").read_text(encoding="utf-8")
    probe = (LOCALPREP_ROOT / "scripts" / "probe_observation_window_exports.py").read_text(encoding="utf-8")
    assert "import ActionModule" not in source
    assert "from ActionModule" not in source
    assert "not runtime ActionModule inputs" in _summary(_base_out())["boundary_note"]
    assert "never feeds observation-window output back" in probe
    for forbidden in ["writeback =", "canonical_state", "world_state =", "ActionFrame direct generation"]:
        assert forbidden not in source


def test_evidence_sources_match_window_roles():
    summary = _summary(_base_out())
    pressure_sources = {e.get("source") for e in _window(summary, "pressure_action_translation_audit_window")["evidence_fields"]}
    risk_sources = {e.get("source") for e in _window(summary, "v2_direct_risk_band_window")["evidence_fields"]}
    composite_sources = {e.get("source") for e in _window(summary, "composite_balance_window")["evidence_fields"]}
    assert not any(str(s).startswith("v2_action_effect_trace") for s in pressure_sources)
    assert not ({"pressure_trace", "gate_trace", "translation_trace", "action_frame"} & risk_sources)
    assert all("derived_fields" in str(s) for s in composite_sources)
    assert not any(flag in LEGACY_WINDOWS for w in summary["windows"] for flag in w["warning_flags"])
