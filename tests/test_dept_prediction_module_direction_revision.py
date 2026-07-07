import pandas as pd

from dept2_fullspec_runner_rc1.modules.dept_prediction_module import DEPTPredictionModule


def _base_trace(t: int):
    entity = pd.DataFrame([
        {"entity_id": "E1", "t": t, "scenario": "revision", "seed": 1, "activity": 0.50, "volatility": 0.20, "uncertainty": 0.25, "exploration": 0.55, "relation_lock": 0.30, "coupling": 0.25, "reversibility": 0.70, "entropy": 0.60, "readiness": 0.55},
        {"entity_id": "E2", "t": t, "scenario": "revision", "seed": 1, "activity": 0.48, "volatility": 0.22, "uncertainty": 0.27, "exploration": 0.53, "relation_lock": 0.32, "coupling": 0.27, "reversibility": 0.68, "entropy": 0.58, "readiness": 0.54},
        {"entity_id": "E3", "t": t, "scenario": "revision", "seed": 1, "activity": 0.46, "volatility": 0.24, "uncertainty": 0.29, "exploration": 0.51, "relation_lock": 0.34, "coupling": 0.29, "reversibility": 0.66, "entropy": 0.56, "readiness": 0.53},
    ])
    relation = pd.DataFrame([
        {"source": "E1", "target": "E2", "relation_strength": 0.55, "relation_rigidity": 0.30, "flow": 0.24, "t": t, "scenario": "revision", "seed": 1},
        {"source": "E2", "target": "E3", "relation_strength": 0.53, "relation_rigidity": 0.32, "flow": 0.26, "t": t, "scenario": "revision", "seed": 1},
    ])
    return {"entity_trace": entity, "relation_trace": relation}


def _ot(trace):
    entity = trace["entity_trace"].copy()
    rows = []
    residual = []
    for _, ent in entity.iterrows():
        rows.append({
            "entity_id": ent["entity_id"],
            "ot_id": f"OT_{ent['entity_id']}",
            "ot_identity_key": ent["entity_id"],
            "t": int(ent["t"]),
            "activity": float(ent["activity"]),
            "volatility": float(ent["volatility"]),
            "uncertainty": float(ent["uncertainty"]),
            "relation_lock": float(ent["relation_lock"]),
            "coupling": float(ent["coupling"]),
            "exploration": float(ent["exploration"]),
            "reversibility": float(ent["reversibility"]),
            "entropy": float(ent["entropy"]),
            "relation_degree": 1.0,
            "ot_residual_score": 0.08,
            "ot_noise_score": 0.06,
            "ot_unresolved_score": 0.07,
            "ot_ambiguity_score": 0.06,
            "ot_macro_micro_mismatch_score": 0.05,
            "ot_boundary_instability_score": 0.05,
            "ot_local_observation_need_score": 0.08,
        })
        residual.append({
            "entity_id": ent["entity_id"],
            "ot_id": f"OT_{ent['entity_id']}",
            "ot_identity_key": ent["entity_id"],
            "last_seen_t": int(ent["t"]),
            "ot_residual_score": 0.08,
            "ot_noise_score": 0.06,
            "ot_unresolved_score": 0.07,
            "ot_ambiguity_score": 0.06,
            "ot_macro_micro_mismatch_score": 0.05,
            "ot_boundary_instability_score": 0.05,
            "observation_count": 1,
            "active_count": 0,
            "consecutive_active_count": 0,
            "max_noise_score_seen": 0.06,
            "noise_delta": 0.0,
            "residual_delta": 0.0,
        })
    ot = pd.DataFrame(rows)
    return ot.copy(), ot, pd.DataFrame(residual)


def _predict(current, projected):
    ot_native, ot_action_view, residual = _ot(current)
    outputs = DEPTPredictionModule().build(
        world_trace_before=current,
        baseline_trace_after=projected,
        gt=pd.DataFrame(),
        kt=pd.DataFrame(),
        ot_native=ot_native,
        ot_action_view=ot_action_view,
        residual_noise_log=residual,
        loop_step=int(current["entity_trace"]["t"].iloc[0]),
        seed=1,
        scenario="revision",
    )
    return outputs["dept_prediction_dynamics_projection"].iloc[0]


def _tiny_shift(trace):
    out = {"entity_trace": trace["entity_trace"].copy(), "relation_trace": trace["relation_trace"].copy()}
    for col in ["activity", "volatility", "uncertainty", "exploration", "relation_lock", "reversibility", "entropy"]:
        out["entity_trace"][col] = out["entity_trace"][col] + 0.0004
    for col in ["relation_strength", "relation_rigidity", "flow"]:
        out["relation_trace"][col] = out["relation_trace"][col] + 0.0004
    out["entity_trace"]["t"] = 1
    out["relation_trace"]["t"] = 1
    return out


def test_tiny_shift_stays_neutral_with_buffer():
    dyn = _predict(_base_trace(0), _tiny_shift(_base_trace(0)))
    assert dyn["predicted_dynamics_direction"] == "neutral"
    assert bool(dyn["neutral_buffer_applied"]) is True


def test_relation_release_pattern_predicts_divergence():
    current = _base_trace(0)
    projected = _base_trace(1)
    projected["entity_trace"]["volatility"] += 0.08
    projected["entity_trace"]["uncertainty"] += 0.08
    projected["entity_trace"]["activity"] += 0.04
    projected["entity_trace"]["entropy"] += 0.04
    projected["entity_trace"]["exploration"] += 0.04
    projected["entity_trace"]["relation_lock"] -= 0.05
    projected["relation_trace"]["relation_strength"] -= 0.03
    projected["relation_trace"]["relation_rigidity"] -= 0.05
    projected["relation_trace"]["flow"] += 0.07
    dyn = _predict(current, projected)
    assert dyn["predicted_dynamics_direction"] == "divergence"
    assert float(dyn["divergence_direction_strength"]) >= float(dyn["fixation_direction_strength"])


def test_shrinking_equilibrium_pattern_predicts_fixation():
    current = _base_trace(0)
    projected = _base_trace(1)
    projected["entity_trace"]["activity"] -= 0.08
    projected["entity_trace"]["volatility"] -= 0.03
    projected["entity_trace"]["exploration"] -= 0.05
    projected["entity_trace"]["reversibility"] -= 0.05
    projected["entity_trace"]["entropy"] -= 0.04
    projected["entity_trace"]["relation_lock"] += 0.07
    projected["relation_trace"]["relation_rigidity"] += 0.07
    projected["relation_trace"]["flow"] -= 0.06
    dyn = _predict(current, projected)
    assert dyn["predicted_dynamics_direction"] == "fixation"
    assert float(dyn["fixation_direction_strength"]) >= float(dyn["overconvergence_direction_strength"])


def test_concentration_pattern_predicts_overconvergence():
    current = _base_trace(0)
    projected = _base_trace(1)
    projected["entity_trace"].loc[0, "exploration"] -= 0.08
    projected["entity_trace"].loc[0, "entropy"] -= 0.08
    projected["entity_trace"].loc[0, "relation_lock"] += 0.08
    projected["entity_trace"].loc[1, "exploration"] -= 0.03
    projected["entity_trace"].loc[1, "entropy"] -= 0.03
    projected["entity_trace"].loc[1, "relation_lock"] += 0.03
    projected["relation_trace"].loc[0, "relation_rigidity"] += 0.05
    projected["relation_trace"].loc[0, "flow"] -= 0.04
    dyn = _predict(current, projected)
    assert dyn["predicted_dynamics_direction"] == "overconvergence"
    assert float(dyn["bias_concentration_measure"]) > 0.0
