from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

LOCALPREP_ROOT = Path(__file__).resolve().parents[1] / "localprep1" / "dept"
if str(LOCALPREP_ROOT) not in sys.path:
    sys.path.insert(0, str(LOCALPREP_ROOT))

from scripts.observation_window_summary import _build_composite_balance_window, build_observation_window_summary
from test_phase2g18r5_v2_direct_risk_band_window import _base

ALLOWED = {"healthy", "watch", "warning", "critical", "unresolved"}


def _cfg():
    return SimpleNamespace(validation_profile_name="smoke", world_profile_name="pseudo", action_profile_name="action")


def _field(value):
    return {"value": value, "method": "test"}


def _source(gh=0.04, benefit=0.62, growth=0.04, risk=0.2, translation=0.8, h11_status="healthy", benefit_status="healthy", growth_status="healthy", risk_status="healthy", translation_status="healthy", omit=()):
    windows = [
        {"window_name": "v2_direct_benefit_window", "status_label": benefit_status, "warning_flags": [], "unresolved_flags": [], "derived_fields": {"visible_benefit_proxy": _field(benefit), "total_resource_proxy": _field(.7), "short_term_benefit_proxy": _field(.7)}},
        {"window_name": "v2_h11_action_effect_window", "status_label": h11_status, "warning_flags": [], "unresolved_flags": [], "derived_fields": {"h11_action_effect_proxy": _field(gh)}},
        {"window_name": "pressure_action_translation_audit_window", "status_label": translation_status, "warning_flags": [], "unresolved_flags": [], "derived_fields": {"translation_observability_proxy": _field(translation), "gate_action_consistency_proxy": _field(translation), "channel_alignment_proxy": _field(translation), "pressure_to_action_ratio": _field(99)}},
        {"window_name": "v2_direct_risk_band_window", "status_label": risk_status, "warning_flags": [], "unresolved_flags": [], "derived_fields": {"direct_risk_band_score": _field(risk)}},
        {"window_name": "v2_direct_growth_window", "status_label": growth_status, "warning_flags": [], "unresolved_flags": [], "derived_fields": {"direct_growth_delta": _field(growth), "resource_growth_delta": _field(growth), "payoff_growth_delta": _field(growth)}},
    ]
    return [w for w in windows if w["window_name"] not in set(omit)]


def _w(**kwargs):
    return _build_composite_balance_window(_source(**kwargs))


def _v(window, field):
    return window["derived_fields"][field]["value"]


def test_composite_window_emits_required_shape():
    w = _w()
    assert w["window_name"] == "composite_balance_window"
    assert w["status_label"] in ALLOWED
    assert isinstance(w["evidence_fields"], list)
    assert isinstance(w["derived_fields"], dict)
    assert isinstance(w["context_fields"], dict)
    assert isinstance(w["warning_flags"], list)
    assert isinstance(w["unresolved_flags"], list)
    assert isinstance(w["short_reason"], str) and w["short_reason"]


def test_main_references_are_extracted_from_existing_windows():
    w = _w(gh=.05, benefit=.61, growth=.02)
    used = w["context_fields"]["used_reference_fields"]
    assert used["governance_health_reference"] == "v2_h11_action_effect_window.derived_fields.h11_action_effect_proxy"
    assert used["benefit_preservation_reference"] == "v2_direct_benefit_window.derived_fields.visible_benefit_proxy"
    assert used["growth_preservation_reference"] == "v2_direct_growth_window.derived_fields.direct_growth_delta"
    assert _v(w, "governance_health_reference") == pytest.approx(.05)
    assert _v(w, "benefit_preservation_reference") == pytest.approx(.61)
    assert _v(w, "growth_preservation_reference") == pytest.approx(.02)


def test_no_raw_trace_direct_dependency():
    out = _base()
    raw_normal = next(x for x in build_observation_window_summary("a", _cfg(), out)["windows"] if x["window_name"] == "composite_balance_window")
    out_extreme = dict(out)
    out_extreme["v2_hidden_trace"] = out_extreme["v2_hidden_trace"].assign(unused_extreme_raw_trace=999)
    raw_extreme = next(x for x in build_observation_window_summary("b", _cfg(), out_extreme)["windows"] if x["window_name"] == "composite_balance_window")
    assert raw_extreme["status_label"] == raw_normal["status_label"]
    assert all("derived_fields" in source for source in raw_extreme["context_fields"]["used_reference_fields"].values())


def test_main_reference_missing_is_unresolved():
    w = _build_composite_balance_window(_source(omit={"v2_h11_action_effect_window"}))
    assert w["status_label"] == "unresolved"
    assert "unresolved_missing_v2_h11_action_effect_window" in w["unresolved_flags"]
    assert "unresolved_missing_governance_health_reference" in w["unresolved_flags"]


def test_auxiliary_missing_is_not_unresolved():
    w = _build_composite_balance_window(_source(omit={"v2_direct_risk_band_window", "pressure_action_translation_audit_window"}))
    assert w["status_label"] != "unresolved"
    assert "missing_auxiliary_risk_window" in w["warning_flags"]
    assert "missing_auxiliary_translation_window" in w["warning_flags"]
    assert w["context_fields"]["missing_reference_fields"]


@pytest.mark.parametrize("kwargs,flag,status", [
    ({"gh": .03, "benefit": .34}, "governance_benefit_tension", {"warning", "critical"}),
    ({"gh": .05, "benefit": .19}, "critical_governance_benefit_tension", {"critical"}),
    ({"gh": .03, "growth": -.03}, "governance_growth_tension", {"warning", "critical"}),
    ({"gh": .05, "growth": -.10}, "critical_governance_growth_tension", {"critical"}),
    ({"benefit": .55, "risk": .60}, "benefit_risk_tension", {"watch", "warning"}),
    ({"growth": .03, "risk": .60}, "growth_risk_tension", {"watch", "warning"}),
    ({"gh": -.03, "translation": .70}, "translation_effect_tension", {"warning", "critical"}),
    ({"gh": -.10, "translation": .80}, "critical_translation_effect_tension", {"critical"}),
])
def test_tension_statuses(kwargs, flag, status):
    w = _w(**kwargs)
    assert flag in w["warning_flags"]
    assert w["status_label"] in status


def test_primary_window_critical_escalates_composite_critical():
    w = _w(h11_status="critical")
    assert "critical_primary_window_status" in w["warning_flags"]
    assert w["status_label"] == "critical"


def test_auxiliary_risk_critical_does_not_automatically_become_critical():
    w = _w(risk=.85, risk_status="critical", benefit=.4, growth=0.0)
    assert "direct_risk_critical_context" in w["warning_flags"]
    assert w["status_label"] in {"watch", "warning"}


def test_primary_balance_reference_does_not_mask_tension():
    w = _w(gh=.08, benefit=.19, growth=.30)
    assert _v(w, "primary_balance_reference") > .3
    assert "critical_governance_benefit_tension" in w["warning_flags"]
    assert w["status_label"] == "critical"


def test_window_order_updated():
    names = [w["window_name"] for w in build_observation_window_summary("unit", _cfg(), _base())["windows"]]
    assert names == ["v2_direct_benefit_window", "v2_h11_action_effect_window", "pressure_action_translation_audit_window", "v2_direct_risk_band_window", "v2_direct_growth_window", "composite_balance_window"]


def test_export_probe_accepts_derived_context_fields_for_composite():
    from scripts.probe_observation_window_exports import DERIVED_CONTEXT_WINDOW_KEYS
    w = _w()
    assert {"derived_fields", "context_fields"} <= set(w)
    assert {"derived_fields", "context_fields"} <= DERIVED_CONTEXT_WINDOW_KEYS
