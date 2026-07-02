from pathlib import Path
from types import SimpleNamespace
import sys

import pandas as pd

LOCALPREP_ROOT = Path(__file__).resolve().parents[1] / "localprep1" / "dept"
if str(LOCALPREP_ROOT) not in sys.path:
    sys.path.insert(0, str(LOCALPREP_ROOT))

from scripts.observation_window_summary import build_observation_window_summary, flatten_observation_windows


def test_phase2g17_observation_windows_emit_required_shape_and_unresolved_fields():
    out = {
        "v2_hidden_trace": pd.DataFrame([
            {
                "private_resource": 0.8,
                "cooperation_intent": 0.7,
                "information_quality": 0.75,
                "hidden_damage": 0.1,
                "fatigue": 0.2,
                "defensiveness": 0.15,
                "latent_pressure": 0.1,
            }
        ]),
        "world_transition_audit": pd.DataFrame([
            {
                "mean_delta_reversibility": 0.001,
                "mean_delta_volatility": 0.0,
                "mean_delta_exploration": 0.002,
                "mean_delta_uncertainty": -0.001,
                "mean_delta_relation_lock": -0.001,
                "mean_delta_entropy": 0.002,
                "mean_delta_coupling": 0.0,
            }
        ]),
        "parameter_shadow_audit": pd.DataFrame([{"gate_pressure_norm": 0.05, "gate_integral_norm": 0.01}]),
        "action_frame": pd.DataFrame([{"action_strength": 0.02, "action_channel": "uncertainty_probe"}]),
        "v2_information_trace": pd.DataFrame([{"information_asymmetry": 0.2}]),
    }
    cfg = SimpleNamespace(validation_profile_name="smoke", world_profile_name="pseudo_reality_default", action_profile_name="action_default")

    summary = build_observation_window_summary("unit", cfg, out)

    assert [w["window_name"] for w in summary["windows"]] == [
        "system_benefit_window",
        "h11_possibility_distribution_window",
        "pressure_action_alignment_window",
        "risk_band_window",
        "growth_window",
        "composite_balance_window",
    ]
    for window in summary["windows"]:
        assert set(window) == {"window_name", "status_label", "evidence_fields", "warning_flags", "unresolved_flags", "short_reason"}
        assert window["status_label"] in {"healthy", "watch", "warning", "critical", "unresolved"}
    assert "missing_growth_capacity_proxy" in next(w for w in summary["windows"] if w["window_name"] == "growth_window")["unresolved_flags"]

    flat = flatten_observation_windows(summary)
    assert len(flat) == 6
    assert set(flat["window_name"]) == {w["window_name"] for w in summary["windows"]}


def test_phase2g17_missing_trace_does_not_infer_fields():
    cfg = SimpleNamespace(validation_profile_name="smoke", world_profile_name="missing", action_profile_name="action_default")

    summary = build_observation_window_summary("missing", cfg, {})

    assert all(window["status_label"] == "unresolved" for window in summary["windows"][:5])
    assert summary["unresolved_field_count"] > 0
