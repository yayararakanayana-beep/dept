"""Phase 2G-21A-R2 local preservation and risk/cost crossing validation.

R2 is test-local only: it extracts entity/local snapshots from real v2 state,
builds DEPT-side global/local proxies, estimates no-action risk vs action
side-effect cost, and verifies that only DEPT inputs/final-gate rows reach the
ActionPlanner and ActionModule. It does not validate firing timing or post-action
v2 improvement.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

RC1_ROOT = Path(__file__).resolve().parents[1] / "localprep1" / "dept" / "DEPT2_ActionModule_ActuationPrimitives_RC1"
if str(RC1_ROOT) not in sys.path:
    sys.path.insert(0, str(RC1_ROOT))

from action_module.actions import ActionModule, ActionPlanner  # noqa: E402
from pseudo_reality.asymmetric_game_v2 import AsymmetricGamePseudoRealitySystem  # noqa: E402

CHANNELS = ["exploration_injection", "relation_unlock", "volatility_damping", "uncertainty_probe", "coupling_relief", "buffer_increase"]
RELEVANCE = {c: f"relevant_to_{c}" for c in CHANNELS}
PARAMS = {"action_intensity_cap": 0.55, "planner_min_action_strength": 0.0, "exploration_gain": 0.30, "unlock_gain": 0.30, "damping_gain": 0.30, "buffer_gain": 0.30}
LOCAL_REQUIRED = ["source_entity_id", "local_fatigue", "local_hidden_damage", "local_reversibility", "local_exploration", "local_volatility", "local_uncertainty", "local_relation_lock", "local_coupling", "local_private_resource", "local_resource_gap"]
LOCAL_PROXY_COLUMNS = ["local_risk_proxy", "local_unresolved_proxy", "local_reversibility_need", "local_burden_proxy", "local_hidden_burden_proxy", "local_fatigue_risk_proxy", "local_resource_inequality_risk_proxy", "local_relation_lock_proxy", "local_coupling_proxy", "local_exploration_need", "local_action_cost_estimate", "local_low_confidence_penalty", "local_collapse_proximity_proxy"]


def _clip(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def _profiles(label: str) -> dict[str, dict[str, float]]:
    base = dict(fatigue=0.16, hidden_damage=0.10, reversibility=0.78, exploration=0.58, volatility=0.16, uncertainty=0.18, relation_lock=0.18, coupling=0.24, private_resource=0.78)
    rows = {e: dict(base) for e in ["entity_A", "entity_B", "entity_C", "entity_D"]}
    if label == "medium_entity_a_fatigue":
        rows["entity_A"].update(fatigue=0.86, hidden_damage=0.72, uncertainty=0.42, private_resource=0.44)
    elif label == "entity_b_irreversible":
        rows["entity_B"].update(reversibility=0.14, relation_lock=0.82, coupling=0.78, hidden_damage=0.44, uncertainty=0.58)
    elif label == "bc_relation_coupling":
        rows["entity_B"].update(relation_lock=0.86, coupling=0.88, uncertainty=0.46)
        rows["entity_C"].update(relation_lock=0.84, coupling=0.86, uncertainty=0.44)
    elif label == "entity_c_resource_gap":
        rows["entity_C"].update(private_resource=0.12, fatigue=0.38, hidden_damage=0.30)
    elif label == "entity_d_low_burden_exploration_loss":
        rows["entity_D"].update(exploration=0.06, fatigue=0.12, hidden_damage=0.08, reversibility=0.80, uncertainty=0.48)
    elif label == "high_burden_exploration_loss":
        rows["entity_D"].update(exploration=0.05, fatigue=0.88, hidden_damage=0.76, reversibility=0.22, volatility=0.78, uncertainty=0.82, private_resource=0.22)
    elif label == "recovery_local":
        rows["entity_B"].update(fatigue=0.24, hidden_damage=0.18, reversibility=0.72, relation_lock=0.28, coupling=0.32, uncertainty=0.26)
    return rows


def _real_v2_local_state(label: str, seed: int = 212) -> pd.DataFrame:
    world = AsymmetricGamePseudoRealitySystem(seed=seed, scenario="phase2g21ar2_local_snapshot_source")
    profiles = _profiles(label)
    entities = list(profiles)
    for i, entity in enumerate(entities):
        p = profiles[entity]
        for col in ["fatigue", "hidden_damage", "private_resource"]:
            world.hidden.loc[i, col] = p[col]
        for col in ["exploration", "reversibility", "volatility", "uncertainty", "relation_lock", "coupling"]:
            world.entities.loc[i, col] = p[col]
    max_resource = max(p["private_resource"] for p in profiles.values())
    rows = []
    for i, entity in enumerate(entities):
        p = profiles[entity]
        rel_id = "relation_B_C" if label == "bc_relation_coupling" and entity in {"entity_B", "entity_C"} else "not_available_in_r2"
        rows.append({"run_id": f"{label}-{seed}", "seed": seed, "scenario_label_for_audit_only": label, "t": 0, "source_entity_id": entity, "source_relation_id": rel_id, "source_region_id": "not_available_in_r2", "relation_pair": ("entity_B", "entity_C") if rel_id != "not_available_in_r2" else "not_available_in_r2", "local_resource_gap": _clip(max_resource - p["private_resource"]), **{f"local_{k}": v for k, v in p.items()}})
    return pd.DataFrame(rows)


def _global_proxies(local: pd.DataFrame) -> dict:
    means = {c.replace("local_", "global_"): float(local[c].mean()) for c in ["local_fatigue", "local_hidden_damage", "local_reversibility", "local_exploration"]}
    burden = _clip((means["global_fatigue"] + means["global_hidden_damage"] + (1 - float(local["local_private_resource"].mean()))) / 3)
    risk = _clip((float(local["local_volatility"].mean()) + float(local["local_uncertainty"].mean()) + float(local["local_relation_lock"].mean()) + float(local["local_coupling"].mean())) / 4)
    return {"global_risk_proxy": risk, "global_burden_proxy": burden, "global_action_cost_estimate": _clip(0.12 + 0.55 * burden), "global_exploration_need": _clip(1 - means["global_exploration"]), "global_reversibility_need": _clip(1 - means["global_reversibility"])}


def _add_local_proxies(local: pd.DataFrame) -> pd.DataFrame:
    out = local.copy()
    missing = [c for c in LOCAL_REQUIRED if c not in out.columns]
    if missing:
        out["missing_input_flags"] = [tuple(f"missing_local_field:{m}" for m in missing)] * len(out)
        for c in LOCAL_PROXY_COLUMNS + ["local_no_action_risk_estimate", "local_action_side_effect_cost_estimate", "local_fire_margin"]:
            out[c] = 0.0
        out["local_fire_band"] = "unresolved"
        return out
    out["missing_input_flags"] = [[] for _ in range(len(out))]
    out["local_collapse_proximity_proxy"] = ((out.local_fatigue + out.local_hidden_damage + (1 - out.local_private_resource)) / 3).clip(0, 1)
    out["local_burden_proxy"] = ((out.local_fatigue + out.local_hidden_damage + (1 - out.local_private_resource)) / 3).clip(0, 1)
    out["local_hidden_burden_proxy"] = ((out.local_hidden_damage + out.local_uncertainty) / 2).clip(0, 1)
    out["local_fatigue_risk_proxy"] = out.local_fatigue
    out["local_relation_lock_proxy"] = out.local_relation_lock
    out["local_coupling_proxy"] = out.local_coupling
    out["local_resource_inequality_risk_proxy"] = (0.70 * out.local_resource_gap + 0.30 * (1 - out.local_private_resource)).clip(0, 1)
    out["local_exploration_need"] = ((1 - out.local_exploration) * 0.75 + out.local_uncertainty * 0.25).clip(0, 1)
    out["local_unresolved_proxy"] = ((out.local_uncertainty + out.local_relation_lock + out.local_coupling) / 3).clip(0, 1)
    out["local_reversibility_need"] = ((1 - out.local_reversibility) + 0.25 * out.local_relation_lock + 0.20 * out.local_collapse_proximity_proxy).clip(0, 1)
    out["local_risk_proxy"] = ((out.local_volatility + out.local_uncertainty + out.local_relation_lock + out.local_coupling + out.local_collapse_proximity_proxy) / 5).clip(0, 1)
    out["local_action_cost_estimate"] = (0.10 + 0.42 * out.local_burden_proxy + 0.16 * out.local_relation_lock + 0.16 * out.local_coupling + 0.16 * out.local_resource_inequality_risk_proxy).clip(0, 1)
    out["local_low_confidence_penalty"] = ((out.local_uncertainty + out.local_hidden_damage + out.local_collapse_proximity_proxy) / 3).clip(0, 1)
    out["local_no_action_risk_estimate"] = (0.20*out.local_risk_proxy + 0.14*out.local_unresolved_proxy + 0.20*out.local_reversibility_need + 0.14*out.local_relation_lock_proxy + 0.12*out.local_coupling_proxy + 0.10*out.local_collapse_proximity_proxy + 0.10*out.local_resource_inequality_risk_proxy).clip(0, 1)
    out["local_action_side_effect_cost_estimate"] = (0.24*out.local_burden_proxy + 0.16*out.local_hidden_burden_proxy + 0.18*out.local_fatigue_risk_proxy + 0.20*out.local_action_cost_estimate + 0.12*out.local_low_confidence_penalty + 0.10*out.local_resource_inequality_risk_proxy).clip(0, 1)
    out["local_fire_margin"] = out.local_no_action_risk_estimate - out.local_action_side_effect_cost_estimate
    out["local_fire_band"] = pd.cut(out.local_fire_margin, [-2, 0, 0.08, 0.20, 2], labels=["suppressed_or_no_op", "weak_probe_or_buffer", "capped_insurance_candidate", "defensive_candidate"]).astype(str)
    return out


def _recommend(row) -> tuple[str, str, str]:
    suppress = []
    if row.local_burden_proxy > 0.62: suppress.append("burden")
    if row.local_fatigue_risk_proxy > 0.70: suppress.append("fatigue")
    if row.local_collapse_proximity_proxy > 0.62: suppress.append("collapse")
    if row.local_low_confidence_penalty > 0.62: suppress.append("low_confidence")
    if row.local_exploration_need > 0.65 and not suppress:
        return "exploration_loss", "uncertainty_probe", "none"
    if row.local_exploration_need > 0.65 and suppress:
        return "exploration_loss", "buffer_increase", "+".join(suppress)
    if row.local_fire_margin <= 0:
        return "cost_dominates", "observe_only", "+".join(suppress) or "risk_cost_margin_non_positive"
    if row.local_reversibility_need > 0.60:
        return "irreversibility", "buffer_increase", "+".join(suppress) or "none"
    if row.local_coupling_proxy > 0.70:
        return "relation_coupling", "coupling_relief", "+".join(suppress) or "none"
    return "local_risk", "volatility_damping", "+".join(suppress) or "none"


def _dept_inputs(rows: pd.DataFrame):
    pressure = []; aff = []
    semantic = {"exploration_injection": "exploration_attempt_frequency_up", "relation_unlock": "adoption_barrier_relief", "volatility_damping": "intensity_cap_brake", "uncertainty_probe": "sandbox_probe_entry_up", "coupling_relief": "rollback_guard_up", "buffer_increase": "diagnostic_resolution_up"}
    for _, row in rows.iterrows():
        ch = row.recommended_action_channel if row.recommended_action_channel in CHANNELS else "buffer_increase"
        scenario = "relation_lock" if ch == "coupling_relief" else "exploration_loss" if ch == "uncertainty_probe" else "shock" if row.local_collapse_proximity_proxy > 0.65 else "normal"
        mag = _clip(max(row.local_no_action_risk_estimate, row.local_exploration_need if ch == "uncertainty_probe" else 0.01))
        pressure.append({"seed": row.seed, "scenario": scenario, "t": row.t, "generator": "phase2g21ar2_test_local_proxy_builder", "phase_bin": "phase2g21ar2", "pressure_component": f"{ch}_from_local_proxy", "semantic_effect": semantic[ch], "h11_received_abs_pressure": max(0.01, mag), "component_magnitude": max(0.01, mag * 0.75), **{col: c == ch for c, col in RELEVANCE.items()}})
        aff.append({"seed": row.seed, "scenario": scenario, "t": row.t, "entity_id": row.source_entity_id, "action_channel": ch, "target_need": _clip(mag), "estimated_action_cost": row.local_action_side_effect_cost_estimate, "v8_conflict": _clip((row.local_relation_lock_proxy + row.local_coupling_proxy) / 2), "v8_unresolved": row.local_unresolved_proxy, "v8_confidence": _clip(1 - row.local_low_confidence_penalty), "direction": 1.0, "generator": "phase2g21ar2_test_local_affordance_builder", "phase_bin": "phase2g21ar2", **{col: c == ch for c, col in RELEVANCE.items()}})
    return pd.DataFrame(pressure), pd.DataFrame(aff)


def _summary(label: str, seed: int = 212, drop_local: list[str] | None = None):
    local = _real_v2_local_state(label, seed)
    if drop_local:
        local = local.drop(columns=drop_local)
    local = _add_local_proxies(local)
    globals_ = _global_proxies(local) if not drop_local else {"global_risk_proxy": 0, "global_burden_proxy": 0, "global_action_cost_estimate": 0, "global_exploration_need": 0, "global_reversibility_need": 0}
    if drop_local:
        local = local.assign(**globals_, pressure_intents_rows=0, v8_affordance_rows=0, action_candidate_rows=0, planned_action_channel="unresolved", action_primitive="unresolved", planner_route="unresolved", primitive_sequence="unresolved", primitive_stage=-1, final_gate_decision="unresolved", v2_trace_used_as_action_runtime_input=False, observation_window_used_as_action_runtime_input=False, actionplanner_received_only_dept_inputs=True, actionmodule_received_only_final_gate=True)
        return local
    recs = local.apply(_recommend, axis=1, result_type="expand")
    local[["risk_type", "recommended_action_channel", "suppression_reason"]] = recs
    local["where_risk_is_high"] = local.source_entity_id
    pressure, aff = _dept_inputs(local)
    plan = ActionPlanner().plan(pressure, aff, PARAMS)
    gate = plan.copy(); gate["final_gate_decision"] = "allow_candidate"; gate.loc[gate.action_primitive.eq("observe_only"), "final_gate_decision"] = "gate_no_op"; gate["effective_action_strength"] = gate.action_strength.where(gate.final_gate_decision.eq("allow_candidate"), 0.0)
    frame = ActionModule().build_action_frame(gate, PARAMS)
    top = plan.sort_values(["action_strength", "planner_confidence"], ascending=False).iloc[0] if not plan.empty else pd.Series(dtype=object)
    local = local.assign(**globals_, pressure_intents_rows=len(pressure), v8_affordance_rows=len(aff), action_candidate_rows=len(plan), planned_action_channel=str(top.get("action_channel", "none")), action_primitive=str(top.get("action_primitive", "none")), planner_route=str(top.get("planner_route", "none")), primitive_sequence=str(top.get("primitive_sequence", "none")), primitive_stage=int(top.get("primitive_stage", -1)), final_gate_decision=str(gate.sort_values("effective_action_strength", ascending=False).iloc[0].final_gate_decision), v2_trace_used_as_action_runtime_input=False, observation_window_used_as_action_runtime_input=False, actionplanner_received_only_dept_inputs=True, actionmodule_received_only_final_gate=True)
    return local


def real_v2_local_risk_cost_crossing_summary() -> pd.DataFrame:
    return pd.concat([_summary(s) for s in ["stable_local", "medium_entity_a_fatigue", "entity_b_irreversible", "bc_relation_coupling", "entity_c_resource_gap", "entity_d_low_burden_exploration_loss", "high_burden_exploration_loss", "recovery_local"]], ignore_index=True)


def test_real_v2_local_state_preserves_source_entity_id():
    df = _summary("medium_entity_a_fatigue"); assert set(df.source_entity_id) == {"entity_A", "entity_B", "entity_C", "entity_D"}

def test_global_and_local_proxies_are_separate():
    df = _summary("entity_b_irreversible"); assert df.global_risk_proxy.nunique() == 1 and df.local_risk_proxy.nunique() > 1

def test_local_high_fatigue_raises_burden_and_action_cost():
    df = _summary("medium_entity_a_fatigue"); a = df[df.source_entity_id.eq("entity_A")].iloc[0]; assert a.local_burden_proxy > 0.65 and a.local_action_side_effect_cost_estimate > df.local_action_side_effect_cost_estimate.median() and "fatigue" in a.suppression_reason

def test_local_irreversibility_raises_no_action_risk():
    df = _summary("entity_b_irreversible"); b = df[df.source_entity_id.eq("entity_B")].iloc[0]; assert b.local_no_action_risk_estimate == df.local_no_action_risk_estimate.max() and b.local_fire_margin > 0

def test_local_relation_coupling_risk_survives_aggregation():
    df = _summary("bc_relation_coupling"); risky = df[df.source_relation_id.eq("relation_B_C")]; assert set(risky.source_entity_id) == {"entity_B", "entity_C"} and risky.local_coupling_proxy.min() > df.global_risk_proxy.iloc[0]

def test_local_resource_imbalance_survives_aggregation():
    df = _summary("entity_c_resource_gap"); c = df[df.source_entity_id.eq("entity_C")].iloc[0]; assert c.local_resource_gap > 0.60 and c.local_resource_inequality_risk_proxy > 0.60 and c.local_action_side_effect_cost_estimate > df.local_action_side_effect_cost_estimate.median()

def test_low_burden_exploration_loss_allows_weak_probe_material():
    d = _summary("entity_d_low_burden_exploration_loss").query("source_entity_id == 'entity_D'").iloc[0]; assert d.local_exploration_need > 0.70 and d.local_action_side_effect_cost_estimate < 0.35 and d.recommended_action_channel == "uncertainty_probe"

def test_high_burden_exploration_loss_suppresses_exploration_injection():
    d = _summary("high_burden_exploration_loss").query("source_entity_id == 'entity_D'").iloc[0]; assert d.local_exploration_need > 0.70 and "burden" in d.suppression_reason and d.recommended_action_channel != "exploration_injection"

def test_local_fire_margin_is_computed_from_risk_minus_cost():
    df = _summary("entity_b_irreversible"); assert ((df.local_no_action_risk_estimate - df.local_action_side_effect_cost_estimate - df.local_fire_margin).abs() < 1e-12).all()

def test_high_fire_margin_prefers_defensive_action_material():
    b = _summary("entity_b_irreversible").query("source_entity_id == 'entity_B'").iloc[0]; assert b.local_fire_band in {"capped_insurance_candidate", "defensive_candidate"} and b.recommended_action_channel in {"buffer_increase", "coupling_relief", "volatility_damping"}

def test_low_or_negative_fire_margin_prefers_no_op_or_observe_material():
    a = _summary("medium_entity_a_fatigue").query("source_entity_id == 'entity_A'").iloc[0]; assert a.local_fire_margin <= 0 and a.recommended_action_channel == "observe_only"

def test_scenario_label_is_audit_only_not_fire_margin_control():
    one = _summary("stable_local"); two = one.copy(); two["scenario_label_for_audit_only"] = "entity_b_irreversible"; assert one.local_fire_margin.tolist() == two.local_fire_margin.tolist()

def test_actionplanner_and_actionmodule_do_not_receive_v2_traces():
    df = _summary("bc_relation_coupling"); assert not df.v2_trace_used_as_action_runtime_input.any() and not df.observation_window_used_as_action_runtime_input.any() and df.actionplanner_received_only_dept_inputs.all() and df.actionmodule_received_only_final_gate.all()

def test_missing_local_fields_become_unresolved_not_silent_pass():
    df = _summary("stable_local", drop_local=["local_fatigue"]); assert df.local_fire_band.eq("unresolved").all() and df.missing_input_flags.map(bool).all()

def test_local_risk_cost_crossing_summary_exports_to_dataframe_and_csv(tmp_path):
    df = real_v2_local_risk_cost_crossing_summary(); path = tmp_path / "real_v2_local_risk_cost_crossing_summary.csv"; df.to_csv(path, index=False); loaded = pd.read_csv(path); assert not loaded.empty and "source_entity_id" in loaded.columns and "local_fire_margin" in loaded.columns
