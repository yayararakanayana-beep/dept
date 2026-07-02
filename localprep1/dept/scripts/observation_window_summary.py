#!/usr/bin/env python3
"""Phase 2G-17 external observation-window summary helpers.

These helpers derive validation-only observation windows from existing runner
outputs.  They intentionally do not import or call ActionModule code, do not
write world/canonical state, and do not feed window outputs back into runtime
inputs.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping

import pandas as pd

Window = Dict[str, Any]

STATUS_LABELS = {"healthy", "watch", "warning", "critical", "unresolved"}


def _df(out: Mapping[str, Any], name: str) -> pd.DataFrame:
    value = out.get(name)
    return value if isinstance(value, pd.DataFrame) else pd.DataFrame()


def _mean(frame: pd.DataFrame, column: str) -> float | None:
    if frame.empty or column not in frame.columns:
        return None
    series = pd.to_numeric(frame[column], errors="coerce").dropna()
    if series.empty:
        return None
    return float(series.mean())



def _latest_t(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or "t" not in frame.columns:
        return frame
    t = pd.to_numeric(frame["t"], errors="coerce")
    if t.dropna().empty:
        return frame
    return frame.loc[t == t.max()]


def _latest_mean(frame: pd.DataFrame, column: str) -> float | None:
    return _mean(_latest_t(frame), column)


def _latest_value(frame: pd.DataFrame, column: str) -> float | None:
    latest = _latest_t(frame)
    if latest.empty or column not in latest.columns:
        return None
    series = pd.to_numeric(latest[column], errors="coerce").dropna()
    if series.empty:
        return None
    return float(series.iloc[-1])


def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _equal_mean(*values: float) -> float:
    return _clip01(sum(values) / len(values))

def _sum(frame: pd.DataFrame, column: str) -> float | None:
    if frame.empty or column not in frame.columns:
        return None
    series = pd.to_numeric(frame[column], errors="coerce").dropna()
    if series.empty:
        return None
    return float(series.sum())


def _evidence(name: str, source: str, value: Any, method: str = "existing_trace_mean") -> Dict[str, Any]:
    return {"field": name, "source": source, "value": value, "method": method}


def _status(warnings: List[str], unresolved: List[str], evidence: List[Dict[str, Any]]) -> str:
    if not evidence:
        return "unresolved"
    if any(flag.startswith("critical_") or flag.endswith("_extreme") for flag in warnings):
        return "critical"
    if len(warnings) >= 3:
        return "warning"
    if warnings:
        return "watch"
    return "healthy" if not unresolved else "watch"


def _missing(unresolved: List[str], name: str) -> None:
    unresolved.append(f"missing_{name}")


def _add_mean(evidence: List[Dict[str, Any]], unresolved: List[str], frame: pd.DataFrame, source: str, column: str, alias: str | None = None, *, mark_missing: bool = True) -> float | None:
    value = _mean(frame, column)
    key = alias or column
    if value is None:
        if mark_missing:
            _missing(unresolved, key)
    else:
        evidence.append(_evidence(key, source, value))
    return value


def _reason(status: str, warnings: List[str], unresolved: List[str]) -> str:
    if status == "unresolved":
        return "Required fields are not available in the current trace."
    if warnings:
        return "Existing trace fields raised validation-only warning flags: " + ", ".join(warnings[:4]) + "."
    if unresolved:
        return "Available fields did not raise warnings; missing fields remain unresolved for later trace repair."
    return "Available fields did not raise validation-only warning flags."


def _window(name: str, evidence: List[Dict[str, Any]], warnings: List[str], unresolved: List[str]) -> Window:
    status = _status(warnings, unresolved, evidence)
    return {
        "window_name": name,
        "status_label": status,
        "evidence_fields": evidence,
        "warning_flags": warnings,
        "unresolved_flags": unresolved,
        "short_reason": _reason(status, warnings, unresolved),
    }


def build_observation_window_summary(label: str, cfg: Any, out: Mapping[str, Any], metrics: Mapping[str, Any] | None = None) -> Dict[str, Any]:
    """Build six Phase 2G-17 observation windows from existing validation output."""
    hidden = _df(out, "v2_hidden_trace")
    if hidden.empty and metrics:
        metric_hidden = {
            key.removesuffix("_mean"): value
            for key, value in metrics.items()
            if key in {
                "hidden_damage_mean",
                "fatigue_mean",
                "information_quality_mean",
                "cooperation_intent_mean",
                "defensiveness_mean",
                "latent_pressure_mean",
                "private_resource_mean",
            }
        }
        if metric_hidden:
            hidden = pd.DataFrame([metric_hidden])
    resource = _df(out, "v2_resource_trace")
    info = _df(out, "v2_information_trace")
    world = _df(out, "world_transition_audit")
    action = _df(out, "action_frame")
    shadow = _df(out, "parameter_shadow_audit")

    windows: List[Window] = []

    # 1. v2 Direct Benefit Window
    ev: List[Dict[str, Any]] = []
    warn: List[str] = []
    unr: List[str] = []
    context_fields: Dict[str, Any] = {}
    context_flags: List[str] = []

    def add_core(field: str, source: str, value: float | None, method: str) -> float | None:
        if value is None:
            unr.append(f"unresolved_core_{field}")
            return None
        ev.append(_evidence(field, source, value, method))
        return value

    def add_context(field: str, source: str, value: float | None, method: str, status_effect: str = "context_only") -> float | None:
        if value is not None:
            context_fields[field] = {"value": value, "source": source, "method": method, "status_effect": status_effect}
        return value

    shared_resource = add_core("shared_resource", "v2_resource_trace", _latest_value(resource, "shared_resource"), "latest_t_value")
    commons_health = add_core("commons_health", "v2_resource_trace", _latest_value(resource, "commons_health"), "latest_t_value")
    private_resource_mean_value = _latest_value(resource, "private_resource_mean")
    private_resource_source = "v2_resource_trace"
    private_resource_method = "latest_t_value"
    if private_resource_mean_value is None:
        private_resource_mean_value = _latest_mean(hidden, "private_resource")
        private_resource_source = "v2_hidden_trace.private_resource"
        private_resource_method = "latest_t_mean_fallback"
    private_resource_mean = add_core("private_resource_mean", private_resource_source, private_resource_mean_value, private_resource_method)
    game = _df(out, "v2_game_trace")
    local_payoff_mean = add_core("local_payoff_mean", "v2_game_trace.local_payoff", _latest_mean(game, "local_payoff"), "latest_t_mean")
    short_term_payoff_mean = add_core("short_term_payoff_mean", "v2_game_trace.short_term_payoff", _latest_mean(game, "short_term_payoff"), "latest_t_mean")

    resource_pressure = add_context("resource_pressure", "v2_resource_trace", _latest_value(resource, "resource_pressure"), "latest_t_value", "used_for_status")
    resource_inequality = add_context("resource_inequality", "v2_resource_trace", _latest_value(resource, "resource_inequality"), "latest_t_value")
    cooperation_intent_mean = add_context("cooperation_intent_mean", "v2_hidden_trace.cooperation_intent", _latest_mean(hidden, "cooperation_intent"), "latest_t_mean")
    add_context("cooperate_tendency_mean", "v2_game_trace.cooperate_tendency", _latest_mean(game, "cooperate_tendency"), "latest_t_mean")
    add_context("share_tendency_mean", "v2_game_trace.share_tendency", _latest_mean(game, "share_tendency"), "latest_t_mean")
    information_quality_mean = _latest_mean(info, "information_quality_mean")
    information_quality_source = "v2_information_trace.information_quality_mean"
    if information_quality_mean is None:
        information_quality_mean = _latest_mean(hidden, "information_quality")
        information_quality_source = "v2_hidden_trace.information_quality"
    add_context("information_quality_mean", information_quality_source, information_quality_mean, "latest_t_mean")
    add_context("information_flow_mean", "v2_information_trace.information_flow_mean", _latest_mean(info, "information_flow_mean"), "latest_t_mean")

    derived_fields: Dict[str, Any] = {}
    if unr:
        status = "unresolved"
        short_reason = "core field missing: " + ", ".join(flag.removeprefix("unresolved_core_") for flag in unr)
    else:
        total_resource_proxy = _equal_mean(shared_resource, commons_health, private_resource_mean)  # type: ignore[arg-type]
        visible_benefit_proxy = _equal_mean(shared_resource, commons_health, private_resource_mean, local_payoff_mean)  # type: ignore[arg-type]
        short_term_benefit_proxy = _equal_mean(short_term_payoff_mean, local_payoff_mean)  # type: ignore[arg-type]
        derived_fields = {
            "total_resource_proxy": {"value": total_resource_proxy, "method": "equal_mean(shared_resource, commons_health, private_resource_mean)"},
            "visible_benefit_proxy": {"value": visible_benefit_proxy, "method": "equal_mean(shared_resource, commons_health, private_resource_mean, local_payoff_mean)"},
            "short_term_benefit_proxy": {"value": short_term_benefit_proxy, "method": "equal_mean(short_term_payoff_mean, local_payoff_mean)"},
        }
        critical = []
        if visible_benefit_proxy < 0.20: critical.append("critical_visible_benefit_collapse")
        if total_resource_proxy < 0.20: critical.append("critical_total_resource_proxy_collapse")
        if shared_resource < 0.20 and commons_health < 0.20: critical.append("critical_shared_base_collapse")  # type: ignore[operator]
        if private_resource_mean < 0.20: critical.append("critical_private_resource_depletion")  # type: ignore[operator]
        if resource_pressure is not None and resource_pressure > 0.90: critical.append("critical_resource_pressure_extreme")
        if visible_benefit_proxy < 0.35: warn.append("visible_benefit_low")
        if total_resource_proxy < 0.35: warn.append("total_resource_proxy_low")
        if short_term_benefit_proxy < 0.35: warn.append("short_term_benefit_low")
        if shared_resource < 0.35: warn.append("shared_resource_low")  # type: ignore[operator]
        if commons_health < 0.35: warn.append("commons_health_low")  # type: ignore[operator]
        if private_resource_mean < 0.35: warn.append("private_resource_mean_low")  # type: ignore[operator]
        if resource_pressure is not None and resource_pressure > 0.80: warn.append("resource_pressure_high")
        warn = critical + warn
        if resource_inequality is not None and resource_inequality > 0.75: context_flags.append("resource_inequality_high_context")
        if cooperation_intent_mean is not None and cooperation_intent_mean < 0.35: context_flags.append("cooperation_context_low")
        if information_quality_mean is not None and information_quality_mean < 0.35: context_flags.append("information_quality_context_low")
        if context_flags:
            context_fields["flags"] = context_flags
        watch_condition = (
            0.35 <= visible_benefit_proxy < 0.55 or 0.35 <= total_resource_proxy < 0.55 or
            0.35 <= short_term_benefit_proxy < 0.45 or (resource_pressure is not None and 0.65 < resource_pressure <= 0.80)
        )
        healthy_condition = visible_benefit_proxy >= 0.55 and total_resource_proxy >= 0.55 and short_term_benefit_proxy >= 0.45 and (resource_pressure is None or resource_pressure <= 0.65)
        if critical:
            status = "critical"
        elif warn:
            status = "warning"
        elif healthy_condition:
            status = "healthy"
        elif watch_condition:
            status = "watch"
        else:
            status = "watch"
        short_reason = _reason(status, warn, [])
    windows.append({
        "window_name": "v2_direct_benefit_window",
        "status_label": status,
        "evidence_fields": ev,
        "derived_fields": derived_fields,
        "context_fields": context_fields,
        "warning_flags": warn,
        "unresolved_flags": unr,
        "short_reason": short_reason,
    })

    # 2. H11 Possibility-Distribution Window
    ev, warn, unr = [], [], []
    h11_map = {
        "stability": "mean_delta_volatility",
        "adaptability": "mean_delta_reversibility",
        "exploration": "mean_delta_exploration",
        "efficiency": "mean_delta_uncertainty",
        "robustness": "mean_delta_relation_lock",
        "structural_diversity": "mean_delta_entropy",
        "trajectory_dynamics": "mean_delta_coupling",
        "predictability": "mean_delta_uncertainty",
        "coherence": "mean_delta_relation_lock",
        "recoverability": "mean_delta_reversibility",
    }
    vals = {k: _add_mean(ev, unr, world, "world_transition_audit", v, k) for k, v in h11_map.items()}
    _missing(unr, "novelty_quality")
    if vals.get("exploration") is not None and vals["exploration"] < -0.01:
        warn.append("exploration_route_contracting")
    if vals.get("structural_diversity") is not None and vals["structural_diversity"] < -0.01:
        warn.append("structural_diversity_contracting")
    if vals.get("recoverability") is not None and vals["recoverability"] < -0.01:
        warn.append("recoverability_contracting")
    if vals.get("coherence") is not None and vals["coherence"] > 0.01:
        warn.append("coherence_relation_lock_risk")
    windows.append(_window("h11_possibility_distribution_window", ev, warn, unr))

    # 3. Pressure-Action Alignment Window
    ev, warn, unr = [], [], []
    pressure_norm = _add_mean(ev, unr, shadow, "parameter_shadow_audit", "gate_pressure_norm", "upper_pressure_intensity_proxy")
    _add_mean(ev, unr, shadow, "parameter_shadow_audit", "gate_integral_norm", "h11_pressure_intensity_proxy")
    action_mass = _sum(action, "action_strength")
    if action_mass is None:
        _missing(unr, "action_mass")
    else:
        ev.append(_evidence("action_mass", "action_frame", action_mass, "existing_trace_sum"))
    for col in ["action_strength", "action_cost"]:
        _add_mean(ev, unr, action, "action_frame", col)
    if "action_channel" in action.columns:
        ev.append(_evidence("selected_action_channel", "action_frame", sorted(action["action_channel"].astype(str).unique().tolist()), "existing_trace_unique_values"))
    else:
        _missing(unr, "selected_action_channel")
    if pressure_norm is not None and action_mass is not None and pressure_norm < 0.01 and action_mass > 0.1:
        warn.append("pressure_absent_but_action_present")
    if pressure_norm is not None and action_mass is not None and action_mass > max(pressure_norm * 100.0, 10.0):
        warn.append("action_mass_high_relative_to_pressure_proxy")
    for miss in ["upper_pressure_direction", "h11_pressure_direction", "action_mass_by_channel", "over_action_risk", "under_action_risk"]:
        _missing(unr, miss)
    windows.append(_window("pressure_action_alignment_window", ev, warn, unr))

    # 4. Risk-Band Window
    ev, warn, unr = [], [], []
    risk_vals = {}
    for col in ["hidden_damage", "fatigue", "defensiveness", "latent_pressure", "cooperation_intent", "information_quality"]:
        risk_vals[col] = _add_mean(ev, unr, hidden, "v2_hidden_trace", col)
    risk_vals["information_asymmetry"] = _add_mean(ev, unr, info, "v2_information_trace", "information_asymmetry")
    risk_vals["action_cost"] = _add_mean(ev, unr, action, "action_frame", "action_cost")
    risk_vals["relation_lock"] = _add_mean(ev, unr, world, "world_transition_audit", "mean_delta_relation_lock", "relation_lock_proxy")
    for col in ["recovery_capacity", "possibility_distribution_narrowing", "shrinking_equilibrium_risk", "relation_rigidity"]:
        _missing(unr, col)
    if any((risk_vals.get(c) or 0.0) >= 0.75 for c in ["hidden_damage", "fatigue", "defensiveness", "latent_pressure"]):
        warn.append("critical_hidden_or_pressure_burden_extreme")
    elif any((risk_vals.get(c) or 0.0) >= 0.55 for c in ["hidden_damage", "fatigue", "defensiveness", "latent_pressure"]):
        warn.append("hidden_or_pressure_burden_elevated")
    if risk_vals.get("cooperation_intent") is not None and risk_vals["cooperation_intent"] <= 0.35:
        warn.append("cooperation_intent_low")
    windows.append(_window("risk_band_window", ev, warn, unr))

    # 5. Growth Window
    ev, warn, unr = [], [], []
    for col in ["realized_growth_proxy", "sustainable_growth_proxy", "growth_capacity_proxy"]:
        _missing(unr, col)
    growth_proxy = _add_mean(ev, unr, world, "world_transition_audit", "mean_delta_reversibility", "growth_capacity_proxy_from_reversibility_delta")
    hidden_damage = _add_mean(ev, unr, hidden, "v2_hidden_trace", "hidden_damage", "hidden_damage_trend_proxy")
    fatigue = _add_mean(ev, unr, hidden, "v2_hidden_trace", "fatigue", "fatigue_trend_proxy")
    latent = _add_mean(ev, unr, hidden, "v2_hidden_trace", "latent_pressure", "latent_pressure_trend_proxy")
    _missing(unr, "h11_possibility_route_preservation")
    if growth_proxy is not None and growth_proxy < -0.01:
        warn.append("growth_capacity_proxy_contracting")
    if any(v is not None and v >= 0.55 for v in [hidden_damage, fatigue, latent]):
        warn.append("growth_hidden_cost_elevated")
    windows.append(_window("growth_window", ev, warn, unr))

    # 6. Composite Balance Window
    ev, warn, unr = [], [], []
    status_by_name = {w["window_name"]: w["status_label"] for w in windows}
    warning_by_name = {w["window_name"]: len(w["warning_flags"]) for w in windows}
    ev.append(_evidence("window_statuses", "observation_window_summary", status_by_name, "derived_from_window_status_labels"))
    ev.append(_evidence("window_warning_counts", "observation_window_summary", warning_by_name, "derived_from_window_warning_flags"))
    if status_by_name.get("v2_direct_benefit_window") in {"healthy", "watch"} and status_by_name.get("h11_possibility_distribution_window") in {"warning", "critical"}:
        warn.append("benefit_vs_possibility_tension")
    if status_by_name.get("growth_window") in {"healthy", "watch"} and "fatigue_elevated" in windows[0]["warning_flags"]:
        warn.append("growth_vs_fatigue_tension")
    if action_mass is not None and action_mass > 0 and status_by_name.get("pressure_action_alignment_window") in {"warning", "critical"}:
        warn.append("action_mass_vs_action_usefulness_tension")
    for col in ["benefit_vs_possibility", "visible_benefit_vs_hidden_damage", "growth_vs_fatigue", "stability_vs_shrinking_equilibrium", "predictability_vs_predictable_collapse", "pressure_alignment_vs_metric_optimization", "short_term_benefit_vs_long_term_route_preservation"]:
        _missing(unr, col)
    windows.append(_window("composite_balance_window", ev, warn, unr))

    return {
        "phase": "Phase 2G-18R-1",
        "label": label,
        "validation_profile": getattr(cfg, "validation_profile_name", ""),
        "world_profile": getattr(cfg, "world_profile_name", ""),
        "action_profile": getattr(cfg, "action_profile_name", ""),
        "boundary_note": "Observation-window outputs are external validation/design-adjustment artifacts and are not runtime ActionModule inputs.",
        "windows": windows,
        "available_field_count": sum(len(w["evidence_fields"]) for w in windows),
        "unresolved_field_count": sum(len(w["unresolved_flags"]) for w in windows),
    }


def flatten_observation_windows(summary: Mapping[str, Any]) -> pd.DataFrame:
    rows = []
    for window in summary.get("windows", []):
        rows.append({
            "label": summary.get("label", ""),
            "window_name": window["window_name"],
            "status_label": window["status_label"],
            "evidence_field_count": len(window["evidence_fields"]),
            "warning_flags": ";".join(window["warning_flags"]),
            "unresolved_flags": ";".join(window["unresolved_flags"]),
            "short_reason": window["short_reason"],
            "boundary_note": summary.get("boundary_note", ""),
            "derived_fields_json": json.dumps(window.get("derived_fields", {}), ensure_ascii=False, sort_keys=True),
            "context_fields_json": json.dumps(window.get("context_fields", {}), ensure_ascii=False, sort_keys=True),
        })
    return pd.DataFrame(rows)
