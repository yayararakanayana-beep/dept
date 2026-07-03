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



def _latest_string(frame: pd.DataFrame, column: str) -> str | None:
    latest = _latest_t(frame)
    if latest.empty or column not in latest.columns:
        return None
    series = latest[column].dropna()
    if series.empty:
        return None
    return str(series.iloc[-1])


def _latest_bool(frame: pd.DataFrame, column: str) -> bool | None:
    latest = _latest_t(frame)
    if latest.empty or column not in latest.columns:
        return None
    series = latest[column].dropna()
    if series.empty:
        return None
    value = series.iloc[-1]
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").dropna()
    if numeric.empty:
        return None
    return bool(numeric.iloc[-1])


def _unique_strings(frame: pd.DataFrame, column: str) -> list[str] | None:
    if frame.empty or column not in frame.columns:
        return None
    values = sorted(str(value) for value in frame[column].dropna().unique().tolist() if str(value) != "")
    return values

def _clip01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _equal_mean(*values: float) -> float:
    return _clip01(sum(values) / len(values))


def _signed_equal_mean(*values: float) -> float:
    return max(-1.0, min(1.0, float(sum(values) / len(values))))

def _sum(frame: pd.DataFrame, column: str) -> float | None:
    if frame.empty or column not in frame.columns:
        return None
    series = pd.to_numeric(frame[column], errors="coerce").dropna()
    if series.empty:
        return None
    return float(series.sum())


def _evidence(name: str, source: str, value: Any, method: str = "existing_trace_mean") -> Dict[str, Any]:
    return {"field": name, "source": source, "value": value, "method": method}


def _interpreted_evidence(name: str, source: str, value: Any, method: str, interpretation: str, higher_is: str) -> Dict[str, Any]:
    item = _evidence(name, source, value, method)
    item.update({"interpretation": interpretation, "higher_is": higher_is})
    return item


def _field_entry(value: float, method: str, interpretation: str, higher_is: str = "worse") -> Dict[str, Any]:
    return {"value": _clip01(value), "method": method, "interpretation": interpretation, "higher_is": higher_is}


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



def _entry_value(entry: Any) -> float | None:
    if isinstance(entry, Mapping):
        entry = entry.get("value")
    try:
        value = float(entry)
    except (TypeError, ValueError):
        return None
    return value


def _build_composite_balance_window(windows: List[Window]) -> Window:
    """Build the auxiliary composite balance window from existing windows only."""
    by_name = {w.get("window_name"): w for w in windows}
    main_sources = {
        "v2_h11_action_effect_window": ("governance_health_reference", "h11_action_effect_proxy"),
        "v2_direct_benefit_window": ("benefit_preservation_reference", "visible_benefit_proxy"),
        "v2_direct_growth_window": ("growth_preservation_reference", "direct_growth_delta"),
    }
    auxiliary_sources = {
        "v2_direct_risk_band_window": ["direct_risk_band_score", "systemic_risk_pressure"],
        "pressure_action_translation_audit_window": ["translation_observability_proxy", "gate_action_consistency_proxy", "channel_alignment_proxy"],
    }
    evidence: List[Dict[str, Any]] = []
    warning_flags: List[str] = []
    unresolved_flags: List[str] = []
    missing_reference_fields: List[str] = []
    used_reference_fields: Dict[str, str] = {}
    values: Dict[str, float] = {}

    status_by_name = {str(w.get("window_name")): w.get("status_label") for w in windows}
    warning_by_name = {str(w.get("window_name")): len(w.get("warning_flags", [])) for w in windows}
    unresolved_by_name = {str(w.get("window_name")): len(w.get("unresolved_flags", [])) for w in windows}

    for window_name, (reference_name, field_name) in main_sources.items():
        window = by_name.get(window_name)
        if not window:
            unresolved_flags.append(f"unresolved_missing_{window_name}")
            unresolved_flags.append(f"unresolved_missing_{reference_name}")
            missing_reference_fields.append(f"{window_name}.derived_fields.{field_name}")
            continue
        value = _entry_value(window.get("derived_fields", {}).get(field_name))
        if value is None:
            unresolved_flags.append(f"unresolved_missing_{reference_name}")
            missing_reference_fields.append(f"{window_name}.derived_fields.{field_name}")
            continue
        values[reference_name] = value
        source = f"{window_name}.derived_fields.{field_name}"
        used_reference_fields[reference_name] = source
        evidence.append(_interpreted_evidence(reference_name, source, value, "existing_window_derived_field", {
            "governance_health_reference": "H11-like action effect reference for governance health",
            "benefit_preservation_reference": "direct v2 benefit preservation reference",
            "growth_preservation_reference": "signed direct v2 growth reference",
        }[reference_name], "better"))

    risk_window = by_name.get("v2_direct_risk_band_window")
    if not risk_window:
        warning_flags.append("missing_auxiliary_risk_window")
        missing_reference_fields.append("v2_direct_risk_band_window")
    else:
        for field_name in auxiliary_sources["v2_direct_risk_band_window"]:
            value = _entry_value(risk_window.get("derived_fields", {}).get(field_name))
            if value is not None:
                values["direct_risk_reference"] = value
                source = f"v2_direct_risk_band_window.derived_fields.{field_name}"
                used_reference_fields["direct_risk_reference"] = source
                evidence.append(_interpreted_evidence("direct_risk_reference", source, value, "existing_window_derived_field", "auxiliary direct v2 risk reference", "worse"))
                break
        if "direct_risk_reference" not in values:
            warning_flags.append("missing_auxiliary_direct_risk_reference")
            missing_reference_fields.append("v2_direct_risk_band_window.derived_fields.direct_risk_band_score|systemic_risk_pressure")

    translation_window = by_name.get("pressure_action_translation_audit_window")
    translation_values: List[float] = []
    if not translation_window:
        warning_flags.append("missing_auxiliary_translation_window")
        missing_reference_fields.append("pressure_action_translation_audit_window")
    else:
        for field_name in auxiliary_sources["pressure_action_translation_audit_window"]:
            value = _entry_value(translation_window.get("derived_fields", {}).get(field_name))
            if value is not None:
                translation_values.append(_clip01(value))
                used_reference_fields[f"translation_audit_reference.{field_name}"] = f"pressure_action_translation_audit_window.derived_fields.{field_name}"
        if translation_values:
            values["translation_audit_reference"] = _equal_mean(*translation_values)
            evidence.append(_interpreted_evidence("translation_audit_reference", "pressure_action_translation_audit_window.derived_fields.translation_observability_proxy|gate_action_consistency_proxy|channel_alignment_proxy", values["translation_audit_reference"], "equal_mean(existing_translation_audit_fields_present)", "auxiliary pressure-to-action readability reference", "better"))
        else:
            warning_flags.append("missing_auxiliary_translation_audit_reference")
            missing_reference_fields.append("pressure_action_translation_audit_window.derived_fields.translation_observability_proxy|gate_action_consistency_proxy|channel_alignment_proxy")

    context_fields: Dict[str, Any] = {
        "source_window_statuses": status_by_name,
        "source_window_warning_counts": warning_by_name,
        "source_window_unresolved_counts": unresolved_by_name,
        "used_reference_fields": used_reference_fields,
        "missing_reference_fields": missing_reference_fields,
        "auxiliary_context": {
            "direct_risk_status": status_by_name.get("v2_direct_risk_band_window"),
            "translation_audit_status": status_by_name.get("pressure_action_translation_audit_window"),
        },
        "extension_notes": [
            "governance_risk_tension can be added later if direct risk becomes central",
            "translation_benefit_tension can be added later if translation/benefit mismatch becomes important",
            "benefit_growth_split_tension can be added later if benefit and growth diverge repeatedly",
            "long_term_health_tension can be added when long-term health proxy becomes stable",
        ],
    }
    derived_fields: Dict[str, Any] = {}
    if unresolved_flags:
        return {"window_name": "composite_balance_window", "status_label": "unresolved", "evidence_fields": evidence, "derived_fields": derived_fields, "context_fields": context_fields, "warning_flags": sorted(set(warning_flags)), "unresolved_flags": sorted(set(unresolved_flags)), "short_reason": "Composite balance window cannot read all main references."}

    gh = values["governance_health_reference"]; benefit = values["benefit_preservation_reference"]; growth = values["growth_preservation_reference"]
    risk = values.get("direct_risk_reference", 0.0); translation_ref = values.get("translation_audit_reference", 0.0)
    ngh = _clip01(0.5 + gh); clipped_growth = _clip01(0.5 + growth)
    primary = _equal_mean(ngh, benefit, clipped_growth)
    tensions = {
        "governance_benefit_tension": max(0.0, ngh - benefit),
        "governance_growth_tension": max(0.0, gh - growth),
        "benefit_risk_tension": min(benefit, risk),
        "growth_risk_tension": risk if growth >= 0.03 else 0.0,
        "translation_effect_tension": max(0.0, translation_ref - ngh),
    }
    for name, value, method, interp, higher in [
        ("governance_health_reference", gh, "v2_h11_action_effect_window.derived_fields.h11_action_effect_proxy", "H11-like action effect reference for governance health", "better"),
        ("benefit_preservation_reference", benefit, "v2_direct_benefit_window.derived_fields.visible_benefit_proxy", "direct v2 benefit preservation reference", "better"),
        ("growth_preservation_reference", growth, "v2_direct_growth_window.derived_fields.direct_growth_delta", "signed direct v2 growth reference", "better"),
        ("direct_risk_reference", risk, used_reference_fields.get("direct_risk_reference", "missing_auxiliary_default_0"), "auxiliary direct v2 risk reference", "worse"),
        ("translation_audit_reference", translation_ref, "equal_mean(translation_observability_proxy, gate_action_consistency_proxy, channel_alignment_proxy)", "auxiliary pressure-to-action readability reference", "better"),
        ("primary_balance_reference", primary, "equal_mean(normalized_governance_health, benefit_preservation_reference, clipped_growth_reference)", "display-only primary balance reference; not a success/failure judgment", "better"),
    ]:
        derived_fields[name] = {"value": value, "method": method, "interpretation": interp, "higher_is": higher}
    for name, value in tensions.items():
        derived_fields[name] = {"value": value, "method": name, "interpretation": name.replace("_", " "), "higher_is": "worse"}

    critical_primary = any(status_by_name.get(n) == "critical" for n in main_sources)
    warning_primary = any(status_by_name.get(n) == "warning" for n in main_sources)
    eps = 1e-12
    if gh + eps >= 0.05 and benefit < 0.20: warning_flags.append("critical_governance_benefit_tension")
    elif gh + eps >= 0.03 and benefit < 0.35: warning_flags.append("governance_benefit_tension")
    if gh + eps >= 0.05 and growth <= -0.10 + eps: warning_flags.append("critical_governance_growth_tension")
    elif gh + eps >= 0.03 and growth <= -0.03 + eps: warning_flags.append("governance_growth_tension")
    if benefit + eps >= 0.55 and risk + eps >= 0.80: warning_flags.append("benefit_risk_tension")
    elif benefit + eps >= 0.55 and risk + eps >= 0.60: warning_flags.append("benefit_risk_tension")
    if growth + eps >= 0.03 and risk + eps >= 0.80: warning_flags.append("growth_risk_tension")
    elif growth + eps >= 0.03 and risk + eps >= 0.60: warning_flags.append("growth_risk_tension")
    if translation_ref + eps >= 0.80 and gh <= -0.10 + eps: warning_flags.append("critical_translation_effect_tension")
    elif translation_ref + eps >= 0.70 and gh <= -0.03 + eps: warning_flags.append("translation_effect_tension")
    if critical_primary: warning_flags.append("critical_primary_window_status")
    if risk_window and risk_window.get("status_label") == "critical": warning_flags.append("direct_risk_critical_context")
    elif risk >= 0.60: warning_flags.append("direct_risk_high_context")
    if translation_window and translation_window.get("status_label") in {"warning", "critical"}: warning_flags.append("translation_audit_low_context")

    critical_flags = {"critical_governance_benefit_tension", "critical_governance_growth_tension", "critical_translation_effect_tension", "critical_primary_window_status"}
    primary_warning_flags = {"governance_benefit_tension", "governance_growth_tension", "translation_effect_tension"}
    if critical_flags & set(warning_flags): status = "critical"
    elif warning_primary or primary_warning_flags & set(warning_flags) or {"benefit_risk_tension", "growth_risk_tension"} & set(warning_flags): status = "warning"
    elif warning_flags or any(status_by_name.get(n) in {"watch"} for n in list(main_sources) + list(auxiliary_sources)): status = "watch"
    else: status = "healthy"
    if "direct_risk_critical_context" in warning_flags and not critical_flags & set(warning_flags): status = "warning"
    return {"window_name": "composite_balance_window", "status_label": status, "evidence_fields": evidence, "derived_fields": derived_fields, "context_fields": context_fields, "warning_flags": sorted(set(warning_flags)), "unresolved_flags": [], "short_reason": "Composite balance window reads existing window references as auxiliary integration; it does not replace primary judgments."}


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

    # 2. v2-H11 Action Effect Window
    ev, warn, unr = [], [], []
    h11_context_fields: Dict[str, Any] = {}
    h11_context_flags: List[str] = []
    action_effect = _df(out, "v2_action_effect_trace")
    core_effect_fields = [
        "net_public_effect_score",
        "net_hidden_effect_score",
        "exploration_delta",
        "reversibility_delta",
        "hidden_damage_delta",
        "fatigue_delta",
        "resource_inequality_delta",
        "action_cost_effect",
    ]

    if action_effect.empty:
        unr.append("unresolved_core_v2_action_effect_trace")
        h11_method = "latest_t_mean"
        core_values: Dict[str, float] = {}
    else:
        has_time_axis = "t" in action_effect.columns and not pd.to_numeric(action_effect["t"], errors="coerce").dropna().empty
        h11_method = "latest_t_mean" if has_time_axis else "all_row_mean_no_time_axis"
        if not has_time_axis:
            h11_context_flags.append("time_axis_missing_context")
        h11_frame = _latest_t(action_effect) if has_time_axis else action_effect
        core_values = {}
        for field in core_effect_fields:
            value = _mean(h11_frame, field)
            if value is None:
                unr.append(f"unresolved_core_{field}")
            else:
                item = _evidence(field, f"v2_action_effect_trace.{field}", value, h11_method)
                if field == "net_hidden_effect_score":
                    item.update({"interpretation": "hidden_burden_magnitude", "higher_is": "worse"})
                elif field in {"exploration_delta", "reversibility_delta"}:
                    item.update({"interpretation": "surface_opening_effect_magnitude", "higher_is": "better_or_effective_when_hidden_burden_is_low"})
                core_values[field] = value
                ev.append(item)

    def add_h11_context(frame: pd.DataFrame, trace: str, field: str, method: str = "latest_t_mean") -> float | None:
        value = _latest_value(frame, field) if method == "latest_t_value" else _latest_mean(frame, field)
        if value is not None:
            h11_context_fields[field] = {"value": value, "source": f"{trace}.{field}", "method": method, "status_effect": "context_only"}
        return value

    rp = add_h11_context(resource, "v2_resource_trace", "resource_pressure", "latest_t_value")
    ri = add_h11_context(resource, "v2_resource_trace", "resource_inequality", "latest_t_value")
    add_h11_context(resource, "v2_resource_trace", "shared_resource", "latest_t_value")
    add_h11_context(resource, "v2_resource_trace", "commons_health", "latest_t_value")
    lth = add_h11_context(game, "v2_game_trace", "long_term_health_proxy")
    for field in ["cooperate_tendency", "defend_tendency", "explore_tendency", "extract_tendency", "connect_tendency", "amplify_tendency"]:
        add_h11_context(game, "v2_game_trace", field)
    gap = add_h11_context(info, "v2_information_trace", "observed_vs_hidden_gap_proxy")
    iq = add_h11_context(info, "v2_information_trace", "information_quality_mean")
    add_h11_context(info, "v2_information_trace", "information_flow_mean")
    distort = add_h11_context(info, "v2_information_trace", "information_distortion_mean")
    if rp is not None and rp >= 0.80: h11_context_flags.append("resource_pressure_high_context")
    if ri is not None and ri >= 0.75: h11_context_flags.append("resource_inequality_high_context")
    if lth is not None and lth <= 0.35: h11_context_flags.append("long_term_health_proxy_low_context")
    if gap is not None and gap >= 0.30: h11_context_flags.append("observed_hidden_gap_high_context")
    if iq is not None and iq <= 0.35: h11_context_flags.append("information_quality_low_context")
    if distort is not None and distort >= 0.30: h11_context_flags.append("information_distortion_high_context")
    for field, flag in [("defend_tendency", "defend_tendency_high_context"), ("extract_tendency", "extract_tendency_high_context")]:
        value = h11_context_fields.get(field, {}).get("value")
        if value is not None and value >= 0.70:
            h11_context_flags.append(flag)
    if h11_context_flags:
        h11_context_fields["flags"] = h11_context_flags

    h11_derived_fields: Dict[str, Any] = {}
    if unr:
        h11_status = "unresolved"
        h11_short_reason = "v2 H11 action effect requires v2_action_effect_trace and all core effect fields."
    else:
        surface_opening = (core_values["exploration_delta"] + core_values["reversibility_delta"]) / 2.0
        hidden_effect_burden = core_values["net_hidden_effect_score"]
        hidden_state_burden = (core_values["hidden_damage_delta"] + core_values["fatigue_delta"]) / 2.0
        distribution_burden = core_values["resource_inequality_delta"]
        cost_burden = core_values["action_cost_effect"]
        public_hidden_tension = core_values["net_public_effect_score"] - hidden_effect_burden
        h11_proxy = (core_values["net_public_effect_score"] + surface_opening - hidden_effect_burden - hidden_state_burden - distribution_burden - cost_burden) / 6.0
        h11_derived_fields = {
            "surface_opening_effect_proxy": {"value": surface_opening, "method": "equal_mean(exploration_delta, reversibility_delta)", "interpretation": "opening effect magnitude on v2 surface", "higher_is": "better_or_effective_when_hidden_burden_is_low"},
            "hidden_effect_burden_proxy": {"value": hidden_effect_burden, "method": "net_hidden_effect_score", "interpretation": "hidden side-effect burden magnitude", "higher_is": "worse"},
            "hidden_state_burden_proxy": {"value": hidden_state_burden, "method": "equal_mean(hidden_damage_delta, fatigue_delta)", "interpretation": "hidden damage and fatigue burden", "higher_is": "worse"},
            "distribution_burden_proxy": {"value": distribution_burden, "method": "resource_inequality_delta", "interpretation": "resource inequality burden", "higher_is": "worse"},
            "cost_burden_proxy": {"value": cost_burden, "method": "action_cost_effect", "interpretation": "action cost burden", "higher_is": "worse"},
            "public_hidden_tension_proxy": {"value": public_hidden_tension, "method": "net_public_effect_score - hidden_effect_burden_proxy", "interpretation": "visible effect minus hidden burden", "higher_is": "better"},
            "h11_action_effect_proxy": {"value": h11_proxy, "method": "equal_mean(net_public_effect_score, surface_opening_effect_proxy, -hidden_effect_burden_proxy, -hidden_state_burden_proxy, -distribution_burden_proxy, -cost_burden_proxy)", "interpretation": "v2-side H11 action effect proxy", "higher_is": "better"},
        }
        critical_flags = []
        if h11_proxy <= -0.10: critical_flags.append("critical_h11_action_effect_collapse")
        if hidden_effect_burden >= 0.12: critical_flags.append("critical_hidden_effect_burden_spike")
        if core_values["hidden_damage_delta"] >= 0.12: critical_flags.append("critical_hidden_damage_spike")
        if core_values["fatigue_delta"] >= 0.12: critical_flags.append("critical_fatigue_spike")
        if core_values["hidden_damage_delta"] >= 0.08 and core_values["fatigue_delta"] >= 0.08: critical_flags.append("critical_hidden_damage_and_fatigue_spike")
        burden_count = sum([hidden_effect_burden >= 0.06, core_values["hidden_damage_delta"] >= 0.05, core_values["fatigue_delta"] >= 0.05, distribution_burden >= 0.05, cost_burden >= 0.08])
        if burden_count >= 3: critical_flags.append("critical_multi_field_h11_burden")
        warning_flags = []
        if h11_proxy <= -0.03: warning_flags.append("h11_action_effect_negative")
        if hidden_effect_burden >= 0.06: warning_flags.append("hidden_effect_burden_high")
        if hidden_state_burden >= 0.05: warning_flags.append("hidden_state_burden_high")
        if core_values["hidden_damage_delta"] >= 0.05: warning_flags.append("hidden_damage_increasing")
        if core_values["fatigue_delta"] >= 0.05: warning_flags.append("fatigue_increasing")
        if distribution_burden >= 0.05: warning_flags.append("resource_inequality_increasing")
        if cost_burden >= 0.08: warning_flags.append("action_cost_high")
        if public_hidden_tension <= -0.03: warning_flags.append("public_hidden_tension_negative")
        if core_values["net_public_effect_score"] >= 0.03 and hidden_effect_burden >= 0.06: warning_flags.append("visible_effect_with_hidden_burden")
        if h11_proxy >= 0.03 and any(v > 0.03 for v in [hidden_effect_burden, hidden_state_burden, distribution_burden, cost_burden]): warning_flags.append("mixed_h11_action_effect_direction")
        warn = critical_flags + warning_flags
        if critical_flags:
            h11_status = "critical"
        elif warning_flags:
            h11_status = "warning"
        elif h11_proxy >= 0.03 and core_values["net_public_effect_score"] >= 0.03 and surface_opening >= 0.01 and hidden_effect_burden <= 0.03 and hidden_state_burden <= 0.03 and distribution_burden <= 0.03 and cost_burden <= 0.05:
            h11_status = "healthy"
        else:
            h11_status = "watch"
        h11_short_reason = "v2 H11 action effect status uses v2_action_effect_trace core effect fields only; auxiliary traces are context-only."
    windows.append({
        "window_name": "v2_h11_action_effect_window",
        "status_label": h11_status,
        "evidence_fields": ev,
        "derived_fields": h11_derived_fields,
        "context_fields": h11_context_fields,
        "warning_flags": warn,
        "unresolved_flags": unr,
        "short_reason": h11_short_reason,
    })

    # 3. Pressure-Action Translation Audit Window
    ev, warn, unr = [], [], []
    context_fields: Dict[str, Any] = {}
    context_flags: List[str] = []
    critical_flags: List[str] = []
    derived_fields: Dict[str, Any] = {}

    pressure = _df(out, "pressure_trace")
    gate = _df(out, "gate_trace")
    translation = _df(out, "translation_trace")
    if pressure.empty and not shadow.empty:
        pressure = shadow
    if gate.empty and not shadow.empty:
        gate = shadow

    def audit_evidence(field: str, source: str, value: Any, method: str, **extra: Any) -> None:
        item = _evidence(field, source, value, method)
        item.update(extra)
        ev.append(item)

    pressure_norm = _latest_value(pressure, "pressure_norm")
    pressure_norm_source = "pressure_trace.pressure_norm"
    if pressure_norm is None:
        pressure_norm = _latest_value(pressure, "gate_pressure_norm")
        pressure_norm_source = "parameter_shadow_audit.gate_pressure_norm"
    dominant_axis = _latest_string(pressure, "dominant_pressure_axis")
    if dominant_axis is None:
        dominant_axis = _latest_string(pressure, "pressure_axis")
    if pressure.empty:
        unr.append("unresolved_core_pressure_log")
    if pressure_norm is None:
        unr.append("unresolved_core_pressure_norm")
    else:
        audit_evidence("pressure_norm", pressure_norm_source, pressure_norm, "latest_t_value", interpretation="pressure magnitude before action translation", higher_is="stronger_pressure")
    if dominant_axis is None:
        unr.append("unresolved_core_dominant_pressure_axis")
    else:
        audit_evidence("dominant_pressure_axis", "pressure_trace.dominant_pressure_axis", dominant_axis, "latest_t_value", interpretation="dominant pressure direction")
    if _latest_string(pressure, "pressure_component_distribution") is None:
        context_flags.append("pressure_component_distribution_missing_context")

    gate_passed = _latest_bool(gate, "gate_passed")
    gate_blocked = _latest_bool(gate, "gate_blocked")
    safety_projection = _latest_bool(gate, "safety_projection_applied") or False
    rollback_guard = _latest_bool(gate, "rollback_guard_active") or False
    no_op_guard = _latest_bool(gate, "no_op_guard_active") or False
    if gate.empty:
        unr.append("unresolved_core_gate_log")
    if gate_passed is None and gate_blocked is None:
        unr.append("unresolved_core_gate_log")
    for field, value in [("gate_passed", gate_passed), ("gate_blocked", gate_blocked), ("safety_projection_applied", safety_projection), ("rollback_guard_active", rollback_guard), ("no_op_guard_active", no_op_guard)]:
        if value is not None:
            audit_evidence(field, f"gate_trace.{field}", value, "latest_t_value")
    for field in ["gate_pressure_norm", "gate_integral_norm"]:
        value = _latest_value(gate, field)
        if value is not None:
            audit_evidence(field, f"gate_trace.{field}", value, "latest_t_value")
            if field == "gate_integral_norm" and value >= 0.7:
                context_flags.append("gate_integral_high_context")
    if safety_projection:
        context_flags.append("safety_projection_applied_context")

    selected_channels = _unique_strings(translation, "selected_action_channels")
    if selected_channels is None:
        selected_channels = _unique_strings(translation, "action_channel")
    translation_flags = _unique_strings(translation, "translation_unresolved_flags") or []
    if translation.empty:
        unr.append("unresolved_core_translation_log")
        translation_flags = sorted(set(translation_flags + ["unresolved_core_translation_log"]))
    if selected_channels is None:
        unr.append("unresolved_core_selected_action_channels")
    else:
        audit_evidence("selected_action_channels", "translation_trace.selected_action_channels", selected_channels, "unique_values")
    audit_evidence("translation_unresolved_flags", "translation_trace.translation_unresolved_flags", translation_flags, "unique_values")
    translated_intent = _latest_string(translation, "translated_action_intent")
    if translated_intent is not None:
        audit_evidence("translated_action_intent", "translation_trace.translated_action_intent", translated_intent, "latest_t_value")
    if _latest_value(translation, "translation_confidence") is None:
        context_flags.append("translation_confidence_missing_context")

    if action.empty:
        unr.append("unresolved_core_action_frame")
    action_channels = _unique_strings(action, "action_channel")
    if action_channels is None:
        unr.append("unresolved_core_action_channel")
    else:
        audit_evidence("action_channel", "action_frame.action_channel", action_channels, "unique_values")
    strengths = pd.to_numeric(action["action_strength"], errors="coerce") if not action.empty and "action_strength" in action.columns else pd.Series(dtype=float)
    if strengths.dropna().empty:
        unr.append("unresolved_core_action_strength")
        action_mass = None
    else:
        target = pd.to_numeric(action["target_count"], errors="coerce") if "target_count" in action.columns else None
        if target is not None and not target.dropna().empty:
            action_mass = float((strengths.fillna(0.0) * target.fillna(1.0)).sum())
            mass_method = "sum_action_strength_times_target_count"
        else:
            action_mass = float(strengths.dropna().sum())
            mass_method = "sum_action_strength"
            if "target_count" not in action.columns:
                context_flags.append("target_count_missing_context")
        audit_evidence("action_strength", "action_frame.action_strength", float(strengths.dropna().mean()), "mean")
        audit_evidence("action_mass", "action_frame.action_strength", action_mass, mass_method, interpretation="total emitted action mass", higher_is="more_action")
    no_op_count = int(action["action_channel"].astype(str).isin({"no_op", "no_action"}).sum()) if action_channels is not None else 0
    no_op_rate = (no_op_count / len(action)) if len(action) else None
    if no_op_rate is None:
        context_flags.append("no_op_rate_missing_context")

    expected = {
        "Exploration": {"exploration_injection", "uncertainty_probe"},
        "Recoverability": {"buffer_increase", "relation_unlock", "coupling_relief"},
        "Reversibility": {"buffer_increase", "relation_unlock", "coupling_relief"},
        "Stability": {"volatility_damping", "coupling_relief", "buffer_increase"},
        "Robustness": {"volatility_damping", "buffer_increase", "coupling_relief"},
        "Coherence": {"coupling_relief", "uncertainty_probe"},
    }
    alignment = None
    if action_mass is not None and action_mass > 0 and action_channels is not None:
        expected_channels = expected.get(str(dominant_axis), set())
        if not expected_channels and dominant_axis != "Efficiency":
            context_flags.append("translation_route_unknown_context")
        matched = 0.0
        for _, row in action.iterrows():
            strength = pd.to_numeric(pd.Series([row.get("action_strength")]), errors="coerce").fillna(0.0).iloc[0]
            count = pd.to_numeric(pd.Series([row.get("target_count", 1.0)]), errors="coerce").fillna(1.0).iloc[0]
            mass = float(strength * count) if "target_count" in action.columns else float(strength)
            if str(row.get("action_channel")) in expected_channels:
                matched += mass
        alignment = matched / action_mass if action_mass else None

    pressure_present = pressure_norm is not None and pressure_norm >= 0.03
    action_present = action_mass is not None and action_mass >= 0.01
    gate_consistency = None
    if gate_passed is True and action_present:
        gate_consistency = 1.0
    elif gate_blocked is True and not action_present:
        gate_consistency = 1.0
    elif gate_blocked is True and action_present:
        gate_consistency = 0.0
    elif gate_passed is True and pressure_present and no_op_rate is not None and no_op_rate >= 0.70:
        gate_consistency = 0.5

    pairing = {k: None for k in ["run_id", "scenario", "seed", "t", "pressure_frame_id", "translation_frame_id", "action_frame_id"]}
    for key in pairing:
        for frame in [action, pressure, translation, gate]:
            if not frame.empty and key in frame.columns:
                pairing[key] = frame[key].dropna().iloc[-1] if not frame[key].dropna().empty else None
                break
    context_fields["pairing_keys"] = {k: v for k, v in pairing.items() if v is not None}
    if not any(pairing.get(k) is not None for k in ["action_frame_id", "pressure_frame_id", "translation_frame_id"]) and not all(pairing.get(k) is not None for k in ["t", "seed", "scenario"]):
        context_flags.append("weak_pairing_context")

    groups_present = sum([pressure_norm is not None and dominant_axis is not None, gate_passed is not None or gate_blocked is not None, bool(selected_channels is not None and not translation.empty), action_mass is not None and action_channels is not None, "weak_pairing_context" not in context_flags])
    observability = groups_present / 5.0
    if pressure_norm is not None and action_mass is not None:
        derived_fields["pressure_presence_proxy"] = {"value": pressure_norm, "method": "pressure_norm"}
        derived_fields["action_mass_proxy"] = {"value": action_mass, "method": mass_method}
        derived_fields["pressure_to_action_ratio"] = {"value": action_mass / max(pressure_norm, 1e-9), "method": "action_mass_proxy / max(pressure_norm, epsilon)", "interpretation": "translation intensity relative to pressure", "higher_is": "more_action_per_pressure"}
    derived_fields["no_op_rate_proxy"] = {"value": no_op_rate, "method": "no_op_count / len(action_frame)"}
    derived_fields["channel_alignment_proxy"] = {"value": alignment, "method": "matched_action_mass / total_action_mass", "interpretation": "share of action mass emitted through expected channels for dominant pressure axis", "higher_is": "better"}
    derived_fields["gate_action_consistency_proxy"] = {"value": gate_consistency, "method": "gate decision and action presence consistency", "interpretation": "whether gate outcome and emitted action agree", "higher_is": "better"}
    derived_fields["translation_observability_proxy"] = {"value": observability, "method": "required audit field completeness", "interpretation": "how well the pressure-to-action path can be reconstructed", "higher_is": "better"}

    if pressure_norm is not None and action_mass is not None:
        if pressure_norm >= 0.30 and action_mass == 0: critical_flags.append("critical_pressure_without_action")
        elif pressure_norm >= 0.20 and action_mass < 0.03: warn.append("under_action_for_pressure")
        if pressure_norm < 0.01 and action_mass >= 0.10: critical_flags.append("critical_action_without_pressure")
        elif pressure_norm < 0.03 and action_mass >= 0.05: warn.append("over_action_for_pressure")
    if gate_blocked is True and action_present: critical_flags.append("critical_gate_blocked_but_action_emitted")
    if rollback_guard and action_present: critical_flags.append("critical_rollback_guard_ignored")
    if no_op_guard and action_present: critical_flags.append("critical_no_op_guard_ignored")
    if not translation.empty and selected_channels == [] and action_present: warn.append("translation_unresolved")
    if translation.empty and action_mass is not None and action_mass >= 0.20: critical_flags.append("critical_translation_missing_but_action_emitted")
    if alignment is not None and alignment < 0.40: warn.append("channel_alignment_low")
    if gate_passed is True and pressure_norm is not None and pressure_norm >= 0.20 and no_op_rate is not None and no_op_rate >= 0.70: warn.append("gate_passed_but_no_action_high")
    if translation_flags: warn.append("translation_unresolved")
    if observability < 0.70: warn.append("translation_observability_low")
    if strengths is not None and not strengths.dropna().empty and (strengths.dropna() >= 0.95).mean() >= 0.8: critical_flags.append("critical_action_strength_saturation")
    if "weak_pairing_context" in context_flags and action_mass is not None and action_mass >= 0.20: critical_flags.append("critical_unpaired_action_frame")
    if "translation_route_unknown_context" in context_flags: warn.append("translation_route_unknown")
    if "weak_pairing_context" in context_flags: warn.append("weak_pairing_context")

    if context_flags:
        context_fields["flags"] = sorted(set(context_flags))
    warn = sorted(set(critical_flags + warn))
    if unr:
        status = "unresolved"
        short_reason = "pressure-action translation audit core log missing: " + ", ".join(sorted(set(unr))[:5])
    elif critical_flags:
        status = "critical"
        short_reason = "pressure-action translation audit found critical pressure/gate/action inconsistency."
    elif any(flag in warn for flag in ["under_action_for_pressure", "over_action_for_pressure", "channel_alignment_low", "gate_passed_but_no_action_high", "translation_unresolved", "translation_observability_low"]):
        status = "warning"
        short_reason = "pressure-action translation audit found warning-level mismatch or observability gap."
    elif warn or safety_projection:
        status = "watch"
        short_reason = "pressure-action translation audit is readable with context/watch flags."
    else:
        status = "healthy"
        short_reason = "pressure, gate, translation, and ActionFrame logs are readable without mismatch flags."
    windows.append({
        "window_name": "pressure_action_translation_audit_window",
        "status_label": status,
        "evidence_fields": ev,
        "derived_fields": derived_fields,
        "context_fields": context_fields,
        "warning_flags": warn,
        "unresolved_flags": sorted(set(unr)),
        "short_reason": short_reason,
    })

    # 4. v2 Direct Risk-Band Window
    ev, warn, unr = [], [], []
    risk_context_fields: Dict[str, Any] = {"used_core_fields": [], "used_auxiliary_fields": [], "missing_auxiliary_fields": [], "flags": []}
    risk_derived_fields: Dict[str, Any] = {}
    risk_values: Dict[str, float] = {}

    risk_interpretations = {
        "hidden_damage": "hidden internal damage on v2 side",
        "fatigue": "fatigue and exhaustion on v2 side",
        "latent_pressure": "latent pressure accumulated on v2 side",
        "defensiveness": "defensive closure tendency on v2 side",
        "resource_pressure": "direct resource stress on v2 side",
        "resource_inequality": "direct resource inequality on v2 side",
        "observed_vs_hidden_gap_proxy": "observed-hidden state gap on v2 side",
        "information_distortion_mean": "direct information distortion on v2 side",
        "opportunism": "opportunistic behavior tendency on v2 side",
        "cooperation_intent": "cooperation intent; low value increases closure/defense risk",
        "information_quality_mean": "information quality; low value increases information risk",
        "information_flow_mean": "information flow; low value increases blockage risk",
        "private_resource_min": "minimum private resource; low value increases local depletion risk",
        "private_resource_std": "private resource spread on v2 side",
    }

    def risk_read(frame: pd.DataFrame, trace: str, field: str, method_kind: str) -> tuple[float | None, str]:
        if frame.empty or field not in frame.columns:
            return None, "missing"
        if "t" in frame.columns:
            method = "latest_t_value" if method_kind == "value" else "latest_t_mean"
            value = _latest_value(frame, field) if method_kind == "value" else _latest_mean(frame, field)
        else:
            method = "all_row_mean_no_time_axis"
            value = _mean(frame, field)
            if "time_axis_missing_context" not in risk_context_fields["flags"]:
                risk_context_fields["flags"].append("time_axis_missing_context")
        return (None if value is None else _clip01(value)), method

    core_specs = {
        "hidden_damage": (hidden, "v2_hidden_trace", "hidden_damage", "mean"),
        "fatigue": (hidden, "v2_hidden_trace", "fatigue", "mean"),
        "latent_pressure": (hidden, "v2_hidden_trace", "latent_pressure", "mean"),
        "defensiveness": (hidden, "v2_hidden_trace", "defensiveness", "mean"),
        "resource_pressure": (resource, "v2_resource_trace", "resource_pressure", "value"),
        "resource_inequality": (resource, "v2_resource_trace", "resource_inequality", "value"),
        "observed_vs_hidden_gap_proxy": (info, "v2_information_trace", "observed_vs_hidden_gap_proxy", "mean"),
        "information_distortion_mean": (info, "v2_information_trace", "information_distortion_mean", "mean"),
    }
    aux_specs = {
        "opportunism": (hidden, "v2_hidden_trace", "opportunism", "mean"),
        "cooperation_intent": (hidden, "v2_hidden_trace", "cooperation_intent", "mean"),
        "information_quality_mean": (info, "v2_information_trace", "information_quality_mean", "mean"),
        "information_flow_mean": (info, "v2_information_trace", "information_flow_mean", "mean"),
        "private_resource_min": (resource, "v2_resource_trace", "private_resource_min", "value"),
        "private_resource_std": (resource, "v2_resource_trace", "private_resource_std", "value"),
    }

    for field, (frame, trace, col, kind) in core_specs.items():
        value, method = risk_read(frame, trace, col, kind)
        if value is None:
            unr.append(f"unresolved_core_{field}")
        else:
            risk_values[field] = value
            risk_context_fields["used_core_fields"].append(field)
            ev.append(_interpreted_evidence(field, f"{trace}.{col}", value, method, risk_interpretations[field], "worse"))

    for field, (frame, trace, col, kind) in aux_specs.items():
        value, method = risk_read(frame, trace, col, kind)
        if value is None and field in {"private_resource_min", "private_resource_std"} and not hidden.empty and "private_resource" in hidden.columns:
            latest_hidden = _latest_t(hidden) if "t" in hidden.columns else hidden
            series = pd.to_numeric(latest_hidden["private_resource"], errors="coerce").dropna()
            if not series.empty:
                value = _clip01(float(series.min() if field == "private_resource_min" else series.std(ddof=0)))
                method = "latest_t_min_fallback" if field == "private_resource_min" else "latest_t_std_fallback"
                risk_context_fields["flags"].append(f"{field}_fallback_from_hidden")
                trace = "v2_hidden_trace"
                col = "private_resource"
        if value is None:
            risk_context_fields["missing_auxiliary_fields"].append(field)
            risk_context_fields["flags"].append(f"missing_auxiliary_{field}")
        else:
            risk_values[field] = value
            risk_context_fields["used_auxiliary_fields"].append(field)
            higher = "better" if field in {"cooperation_intent", "information_quality_mean", "information_flow_mean", "private_resource_min"} else "worse"
            ev.append(_interpreted_evidence(field, f"{trace}.{col}", value, method, risk_interpretations[field], higher))

    if unr:
        windows.append({
            "window_name": "v2_direct_risk_band_window",
            "status_label": "unresolved",
            "evidence_fields": ev,
            "derived_fields": {},
            "context_fields": risk_context_fields,
            "warning_flags": [],
            "unresolved_flags": sorted(set(unr)),
            "short_reason": "Required v2 direct risk core fields are not readable: " + ", ".join(sorted(set(unr))[:4]) + ".",
        })
    else:
        def vals(*names: str) -> list[float]:
            return [risk_values[n] for n in names if n in risk_values]
        derived_raw = {
            "internal_damage_risk": (_equal_mean(*vals("hidden_damage", "fatigue", "latent_pressure")), "equal_mean(hidden_damage, fatigue, latent_pressure)", "hidden damage, fatigue, and latent pressure risk"),
            "closure_defense_risk": (_equal_mean(*vals("defensiveness", "opportunism") + ([1 - risk_values["cooperation_intent"]] if "cooperation_intent" in risk_values else [])), "equal_mean(defensiveness, opportunism, 1 - cooperation_intent)", "defensive closure, opportunism, and non-cooperation risk"),
            "resource_stress_risk": (_equal_mean(*vals("resource_pressure", "resource_inequality") + ([1 - risk_values["private_resource_min"]] if "private_resource_min" in risk_values else []) + ([risk_values["private_resource_std"]] if "private_resource_std" in risk_values else [])), "equal_mean(resource_pressure, resource_inequality, 1 - private_resource_min, private_resource_std)", "resource pressure, inequality, local depletion, and resource spread risk"),
            "information_blindness_risk": (_equal_mean(*vals("observed_vs_hidden_gap_proxy", "information_distortion_mean") + ([1 - risk_values["information_quality_mean"]] if "information_quality_mean" in risk_values else []) + ([1 - risk_values["information_flow_mean"]] if "information_flow_mean" in risk_values else [])), "equal_mean(observed_vs_hidden_gap_proxy, information_distortion_mean, 1 - information_quality_mean, 1 - information_flow_mean)", "observed-hidden gap, distortion, low quality, and low flow information risk"),
        }
        band = max(v[0] for v in derived_raw.values())
        systemic = _equal_mean(*(v[0] for v in derived_raw.values()))
        derived_raw["direct_risk_band_score"] = (band, "max(internal_damage_risk, closure_defense_risk, resource_stress_risk, information_blindness_risk)", "highest direct v2 risk band")
        derived_raw["systemic_risk_pressure"] = (systemic, "equal_mean(internal_damage_risk, closure_defense_risk, resource_stress_risk, information_blindness_risk)", "spread of direct v2 risk across semantic risk families")
        combos = {
            "hidden_damage_blindness_risk": (min(risk_values["hidden_damage"], risk_values["observed_vs_hidden_gap_proxy"]), "min(hidden_damage, observed_vs_hidden_gap_proxy)", "hidden damage with observed-hidden gap"),
            "fatigue_pressure_accumulation_risk": (min(risk_values["fatigue"], risk_values["latent_pressure"]), "min(fatigue, latent_pressure)", "fatigue with latent pressure accumulation"),
            "resource_squeeze_inequality_risk": (min(risk_values["resource_pressure"], risk_values["resource_inequality"]), "min(resource_pressure, resource_inequality)", "resource pressure with inequality"),
        }
        if "cooperation_intent" in risk_values: combos["defensive_noncooperation_risk"] = (min(risk_values["defensiveness"], 1 - risk_values["cooperation_intent"]), "min(defensiveness, 1 - cooperation_intent)", "defensiveness with low cooperation intent")
        if "information_quality_mean" in risk_values: combos["information_corruption_risk"] = (min(risk_values["information_distortion_mean"], 1 - risk_values["information_quality_mean"]), "min(information_distortion_mean, 1 - information_quality_mean)", "information distortion with low quality")
        if "information_flow_mean" in risk_values: combos["information_blockage_risk"] = (min(1 - risk_values["information_flow_mean"], risk_values["observed_vs_hidden_gap_proxy"]), "min(1 - information_flow_mean, observed_vs_hidden_gap_proxy)", "low information flow with observed-hidden gap")
        if "private_resource_min" in risk_values and "private_resource_std" in risk_values: combos["local_depletion_inequality_risk"] = (min(1 - risk_values["private_resource_min"], risk_values["private_resource_std"]), "min(1 - private_resource_min, private_resource_std)", "local depletion with resource inequality")
        if "opportunism" in risk_values: combos["opportunistic_extraction_risk"] = (max(min(risk_values["opportunism"], risk_values["resource_pressure"]), min(risk_values["opportunism"], risk_values["resource_inequality"])), "max(min(opportunism, resource_pressure), min(opportunism, resource_inequality))", "opportunism under resource pressure or inequality")
        derived_raw.update(combos)
        risk_derived_fields = {k: _field_entry(v, m, i) for k, (v, m, i) in derived_raw.items()}

        individual_warn = {"hidden_damage": "hidden_damage_high", "fatigue": "fatigue_high", "latent_pressure": "latent_pressure_high", "defensiveness": "defensiveness_high", "resource_pressure": "resource_pressure_high", "resource_inequality": "resource_inequality_high", "observed_vs_hidden_gap_proxy": "observed_hidden_gap_high", "information_distortion_mean": "information_distortion_high"}
        individual_crit = {"hidden_damage": "critical_hidden_damage", "fatigue": "critical_fatigue", "latent_pressure": "critical_latent_pressure", "resource_pressure": "critical_resource_pressure", "observed_vs_hidden_gap_proxy": "critical_observed_hidden_gap", "information_distortion_mean": "critical_information_distortion"}
        for field, flag in individual_warn.items():
            if risk_values[field] >= 0.60: warn.append(flag)
        for field, flag in individual_crit.items():
            if risk_values[field] >= (0.90 if field == "resource_pressure" else 0.85): warn.append(flag)
        combo_warning_count = 0
        for name, (value, _method, _interp) in combos.items():
            if value >= 0.60:
                warn.append(name); combo_warning_count += 1
            if value >= 0.80:
                warn.append(f"critical_{name}")
        core_ge_60 = sum(1 for f in core_specs if risk_values[f] >= 0.60)
        light_combo = any(0.35 <= value < 0.60 for value, _m, _i in combos.values())
        if any(flag.startswith("critical_") for flag in warn) or band >= 0.80 or risk_values["hidden_damage"] >= 0.85 or risk_values["fatigue"] >= 0.85 or risk_values["latent_pressure"] >= 0.85 or risk_values["resource_pressure"] >= 0.90 or combo_warning_count >= 3:
            status = "critical"
            reason = "v2 direct risk fields show critical direct or combined risk."
        elif band >= 0.60 or systemic >= 0.50 or core_ge_60 >= 2 or combo_warning_count >= 1 or sum(1 for flag in warn if not flag.startswith("critical_")) >= 2:
            status = "warning"
            reason = "v2 direct risk fields show warning-level direct or combined risk."
        elif band >= 0.35 or systemic >= 0.30 or any(risk_values[f] >= 0.45 for f in core_specs) or light_combo:
            status = "watch"
            reason = "v2 direct risk fields are approaching a risk band."
        else:
            status = "healthy"
            reason = "v2 direct risk fields do not show a direct risk band."
        windows.append({"window_name": "v2_direct_risk_band_window", "status_label": status, "evidence_fields": ev, "derived_fields": risk_derived_fields, "context_fields": risk_context_fields, "warning_flags": sorted(set(warn)), "unresolved_flags": [], "short_reason": reason})

    # 5. v2 Direct Growth Window
    ev, warn, unr = [], [], []
    growth_derived_fields: Dict[str, Any] = {}
    growth_context_fields: Dict[str, Any] = {}
    growth_context_flags: List[str] = []

    def numeric_times(frame: pd.DataFrame, source_name: str) -> set[float] | None:
        if frame.empty or "t" not in frame.columns:
            unr.append(f"unresolved_core_time_axis_{source_name}")
            return None
        values = pd.to_numeric(frame["t"], errors="coerce").dropna()
        if values.empty:
            unr.append(f"unresolved_core_time_axis_{source_name}")
            return None
        return set(float(value) for value in values)

    resource_times = numeric_times(resource, "v2_resource_trace")
    game_times = numeric_times(game, "v2_game_trace")
    initial_t = latest_t = previous_t = None
    if resource_times is not None and game_times is not None:
        common_t_values = sorted(resource_times & game_times)
        if len(common_t_values) < 2:
            unr.append("unresolved_core_insufficient_common_time_history")
        else:
            initial_t = common_t_values[0]
            latest_t = common_t_values[-1]
            previous_t = common_t_values[-2]

    def at_t(frame: pd.DataFrame, t_value: float | None) -> pd.DataFrame:
        if frame.empty or t_value is None or "t" not in frame.columns:
            return pd.DataFrame()
        numeric_t = pd.to_numeric(frame["t"], errors="coerce")
        return frame.loc[numeric_t == t_value]

    def value_at_t(frame: pd.DataFrame, column: str, t_value: float | None) -> float | None:
        point = at_t(frame, t_value)
        if point.empty or column not in point.columns:
            return None
        series = pd.to_numeric(point[column], errors="coerce").dropna()
        if series.empty:
            return None
        return float(series.iloc[-1])

    def mean_at_t(frame: pd.DataFrame, column: str, t_value: float | None) -> float | None:
        return _mean(at_t(frame, t_value), column)

    def evidence_pair(field: str, source: str, initial: float, latest: float, method: str) -> None:
        ev.append(_evidence(f"{field}_initial", source, initial, f"initial_t_{method}"))
        ev.append(_evidence(f"{field}_latest", source, latest, f"latest_t_{method}"))

    def add_delta(field: str, source: str, initial: float | None, latest: float | None, method: str) -> float | None:
        if initial is None or latest is None:
            unr.append(f"unresolved_core_{field}")
            return None
        evidence_pair(field, source, initial, latest, method)
        delta = latest - initial
        growth_derived_fields[f"{field}_delta"] = {"value": delta, "source": source, "method": "latest_t_minus_initial_t"}
        return delta

    def add_context_delta(field: str, source: str, initial: float | None, latest: float | None, flag: str, worsening: str) -> None:
        if initial is None or latest is None:
            return
        delta = latest - initial
        growth_context_fields[f"{field}_delta"] = {"value": delta, "source": source, "method": "latest_t_minus_initial_t", "status_effect": "context_only"}
        if (worsening == "positive" and delta > 0) or (worsening == "negative" and delta < 0):
            growth_context_flags.append(flag)

    core_deltas: Dict[str, float] = {}
    if not unr:
        shared_resource_delta = add_delta("shared_resource", "v2_resource_trace.shared_resource", value_at_t(resource, "shared_resource", initial_t), value_at_t(resource, "shared_resource", latest_t), "value")
        commons_health_delta = add_delta("commons_health", "v2_resource_trace.commons_health", value_at_t(resource, "commons_health", initial_t), value_at_t(resource, "commons_health", latest_t), "value")
        private_initial = value_at_t(resource, "private_resource_mean", initial_t)
        private_latest = value_at_t(resource, "private_resource_mean", latest_t)
        private_source = "v2_resource_trace.private_resource_mean"
        private_method = "value"
        if private_initial is None or private_latest is None:
            private_initial = mean_at_t(hidden, "private_resource", initial_t)
            private_latest = mean_at_t(hidden, "private_resource", latest_t)
            private_source = "v2_hidden_trace.private_resource"
            private_method = "mean_fallback"
        private_resource_mean_delta = add_delta("private_resource_mean", private_source, private_initial, private_latest, private_method)
        local_payoff_mean_delta = add_delta("local_payoff_mean", "v2_game_trace.local_payoff", mean_at_t(game, "local_payoff", initial_t), mean_at_t(game, "local_payoff", latest_t), "mean")
        short_term_payoff_mean_delta = add_delta("short_term_payoff_mean", "v2_game_trace.short_term_payoff", mean_at_t(game, "short_term_payoff", initial_t), mean_at_t(game, "short_term_payoff", latest_t), "mean")
        for key, value in {
            "shared_resource": shared_resource_delta,
            "commons_health": commons_health_delta,
            "private_resource_mean": private_resource_mean_delta,
            "local_payoff_mean": local_payoff_mean_delta,
            "short_term_payoff_mean": short_term_payoff_mean_delta,
        }.items():
            if value is not None:
                core_deltas[key] = value

    if unr:
        growth_status = "unresolved"
        growth_short_reason = "v2 direct growth requires t-aligned resource/game traces and all core growth fields."
    else:
        resource_growth_delta = _signed_equal_mean(core_deltas["shared_resource"], core_deltas["commons_health"], core_deltas["private_resource_mean"])
        payoff_growth_delta = _signed_equal_mean(core_deltas["local_payoff_mean"], core_deltas["short_term_payoff_mean"])
        direct_growth_delta = _signed_equal_mean(resource_growth_delta, payoff_growth_delta)
        growth_derived_fields.update({
            "resource_growth_delta": {"value": resource_growth_delta, "method": "equal_mean(shared_resource_delta, commons_health_delta, private_resource_mean_delta)"},
            "payoff_growth_delta": {"value": payoff_growth_delta, "method": "equal_mean(local_payoff_mean_delta, short_term_payoff_mean_delta)"},
            "direct_growth_delta": {"value": direct_growth_delta, "method": "equal_mean(resource_growth_delta, payoff_growth_delta)"},
        })
        if previous_t is not None:
            previous_private = value_at_t(resource, "private_resource_mean", previous_t)
            if previous_private is None:
                previous_private = mean_at_t(hidden, "private_resource", previous_t)
            latest_step_inputs = {
                "latest_step_shared_resource_delta": (value_at_t(resource, "shared_resource", previous_t), value_at_t(resource, "shared_resource", latest_t)),
                "latest_step_commons_health_delta": (value_at_t(resource, "commons_health", previous_t), value_at_t(resource, "commons_health", latest_t)),
                "latest_step_private_resource_mean_delta": (previous_private, private_latest),
                "latest_step_local_payoff_mean_delta": (mean_at_t(game, "local_payoff", previous_t), mean_at_t(game, "local_payoff", latest_t)),
                "latest_step_short_term_payoff_mean_delta": (mean_at_t(game, "short_term_payoff", previous_t), mean_at_t(game, "short_term_payoff", latest_t)),
            }
            latest_step_values = {key: latest - previous for key, (previous, latest) in latest_step_inputs.items() if previous is not None and latest is not None}
            required_latest_step = {
                "latest_step_shared_resource_delta",
                "latest_step_commons_health_delta",
                "latest_step_private_resource_mean_delta",
                "latest_step_local_payoff_mean_delta",
                "latest_step_short_term_payoff_mean_delta",
            }
            if required_latest_step <= set(latest_step_values):
                latest_step_resource_growth_delta = _signed_equal_mean(latest_step_values["latest_step_shared_resource_delta"], latest_step_values["latest_step_commons_health_delta"], latest_step_values["latest_step_private_resource_mean_delta"])
                latest_step_payoff_growth_delta = _signed_equal_mean(latest_step_values["latest_step_local_payoff_mean_delta"], latest_step_values["latest_step_short_term_payoff_mean_delta"])
                latest_step_values.update({
                    "latest_step_resource_growth_delta": latest_step_resource_growth_delta,
                    "latest_step_payoff_growth_delta": latest_step_payoff_growth_delta,
                    "latest_step_growth_delta": _signed_equal_mean(latest_step_resource_growth_delta, latest_step_payoff_growth_delta),
                })
                for key, value in latest_step_values.items():
                    growth_derived_fields[key] = {"value": value, "method": "latest_t_minus_previous_t", "status_effect": "auxiliary_only"}
        add_context_delta("resource_pressure", "v2_resource_trace.resource_pressure", value_at_t(resource, "resource_pressure", initial_t), value_at_t(resource, "resource_pressure", latest_t), "resource_pressure_increasing_context", "positive")
        add_context_delta("resource_inequality", "v2_resource_trace.resource_inequality", value_at_t(resource, "resource_inequality", initial_t), value_at_t(resource, "resource_inequality", latest_t), "resource_inequality_increasing_context", "positive")
        add_context_delta("long_term_health_proxy", "v2_game_trace.long_term_health_proxy", mean_at_t(game, "long_term_health_proxy", initial_t), mean_at_t(game, "long_term_health_proxy", latest_t), "long_term_health_proxy_declining_context", "negative")
        critical_flags = []
        if direct_growth_delta <= -0.10: critical_flags.append("critical_direct_growth_collapse")
        if resource_growth_delta <= -0.10: critical_flags.append("critical_resource_growth_collapse")
        if sum(value <= -0.08 for value in core_deltas.values()) >= 3: critical_flags.append("critical_multi_field_growth_collapse")
        warning_flags = []
        if direct_growth_delta <= -0.03: warning_flags.append("direct_growth_contracting")
        if resource_growth_delta <= -0.03: warning_flags.append("resource_growth_contracting")
        if payoff_growth_delta <= -0.03: warning_flags.append("payoff_growth_contracting")
        for key, flag in [("shared_resource", "shared_resource_contracting"), ("commons_health", "commons_health_contracting"), ("private_resource_mean", "private_resource_mean_contracting"), ("local_payoff_mean", "local_payoff_contracting"), ("short_term_payoff_mean", "short_term_payoff_contracting")]:
            if core_deltas[key] <= -0.08:
                warning_flags.append(flag)
        if direct_growth_delta >= 0.03 and (resource_growth_delta < 0 or payoff_growth_delta < 0):
            warning_flags.append("mixed_growth_direction")
        warn = critical_flags + warning_flags
        if growth_context_flags:
            growth_context_fields["flags"] = growth_context_flags
        if critical_flags:
            growth_status = "critical"
        elif warning_flags:
            growth_status = "warning"
        elif direct_growth_delta >= 0.03 and resource_growth_delta >= 0 and payoff_growth_delta >= 0:
            growth_status = "healthy"
        elif -0.03 < direct_growth_delta < 0.03 or (direct_growth_delta >= 0.03 and (resource_growth_delta < 0 or payoff_growth_delta < 0)):
            growth_status = "watch"
        else:
            growth_status = "watch"
        growth_short_reason = "v2 direct growth status is based on initial_t to latest_t direct benefit field deltas only."
    windows.append({
        "window_name": "v2_direct_growth_window",
        "status_label": growth_status,
        "evidence_fields": ev,
        "derived_fields": growth_derived_fields,
        "context_fields": growth_context_fields,
        "warning_flags": warn,
        "unresolved_flags": unr,
        "short_reason": growth_short_reason,
    })

    # 6. Composite Balance Window
    windows.append(_build_composite_balance_window(windows))

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
            "derived_fields_json": json.dumps(window.get("derived_fields", {}), ensure_ascii=False, sort_keys=True, default=str),
            "context_fields_json": json.dumps(window.get("context_fields", {}), ensure_ascii=False, sort_keys=True, default=str),
        })
    return pd.DataFrame(rows)
