import pandas as pd

from dept2_fullspec_runner_rc1.contracts import FullSpecRunnerConfig
from dept2_fullspec_runner_rc1.modules.dept_prediction_activation_module import (
    DEPTPredictionActivationModule,
    PredictionActivationConfig,
)
from dept2_fullspec_runner_rc1.modules.dept_prediction_module import (
    DEPTPredictionModule,
    output_contains_judgment_terms,
)
from dept2_fullspec_runner_rc1.runner.fullspec_integrated_closed_loop_runner import (
    FullSpecIntegratedClosedLoopRunner,
    run_fullspec_task16,
)

ALLOWED_DYNAMICS_DIRECTIONS = {"overconvergence", "fixation", "divergence", "neutral"}


def _trace(t: int, value_shift: float = 0.0):
    entity = pd.DataFrame([
        {
            "entity_id": "E1",
            "t": t,
            "scenario": "unit",
            "seed": 7,
            "activity": 0.40 + value_shift,
            "volatility": 0.20 + value_shift,
            "uncertainty": 0.30 + value_shift,
            "exploration": 0.50,
            "relation_lock": 0.35 + value_shift,
            "coupling": 0.25,
            "reversibility": 0.70 - value_shift,
            "entropy": 0.60,
            "readiness": 0.55,
        },
        {
            "entity_id": "E2",
            "t": t,
            "scenario": "unit",
            "seed": 7,
            "activity": 0.30 + value_shift,
            "volatility": 0.25 + value_shift,
            "uncertainty": 0.35 + value_shift,
            "exploration": 0.45,
            "relation_lock": 0.25 + value_shift,
            "coupling": 0.30,
            "reversibility": 0.65 - value_shift,
            "entropy": 0.58,
            "readiness": 0.52,
        },
    ])
    relation = pd.DataFrame([
        {
            "source": "E1",
            "target": "E2",
            "relation_strength": 0.55 + value_shift,
            "relation_rigidity": 0.30 + value_shift,
            "flow": 0.22 + value_shift,
            "t": t,
            "scenario": "unit",
            "seed": 7,
        }
    ])
    return {"entity_trace": entity, "relation_trace": relation}


def _direction_trace(t: int, drift: float = 0.0):
    trace = _trace(t, 0.0)
    e = trace["entity_trace"].copy()
    r = trace["relation_trace"].copy()
    e["exploration"] = e["exploration"] - drift
    e["entropy"] = e["entropy"] - drift
    e["reversibility"] = e["reversibility"] - drift
    e["relation_lock"] = e["relation_lock"] + drift
    r["relation_rigidity"] = r["relation_rigidity"] + drift
    r["flow"] = r["flow"] - drift
    trace["entity_trace"] = e
    trace["relation_trace"] = r
    return trace


def _ot_tables():
    ot_action_view = pd.DataFrame([
        {
            "entity_id": "E1",
            "ot_id": "OT_E1",
            "ot_identity_key": "E1",
            "t": 0,
            "activity": 0.4,
            "volatility": 0.2,
            "uncertainty": 0.3,
            "relation_lock": 0.35,
            "coupling": 0.25,
            "exploration": 0.5,
            "reversibility": 0.7,
            "entropy": 0.6,
            "relation_degree": 1.0,
            "ot_residual_score": 0.12,
            "ot_noise_score": 0.20,
            "ot_unresolved_score": 0.18,
            "ot_ambiguity_score": 0.16,
            "ot_macro_micro_mismatch_score": 0.10,
            "ot_boundary_instability_score": 0.22,
            "ot_local_observation_need_score": 0.18,
        },
        {
            "entity_id": "E2",
            "ot_id": "OT_E2",
            "ot_identity_key": "E2",
            "t": 0,
            "activity": 0.3,
            "volatility": 0.25,
            "uncertainty": 0.35,
            "relation_lock": 0.25,
            "coupling": 0.3,
            "exploration": 0.45,
            "reversibility": 0.65,
            "entropy": 0.58,
            "relation_degree": 1.0,
            "ot_residual_score": 0.15,
            "ot_noise_score": 0.25,
            "ot_unresolved_score": 0.20,
            "ot_ambiguity_score": 0.19,
            "ot_macro_micro_mismatch_score": 0.11,
            "ot_boundary_instability_score": 0.24,
            "ot_local_observation_need_score": 0.20,
        },
    ])
    residual = pd.DataFrame([
        {
            "entity_id": "E1",
            "ot_id": "OT_E1",
            "ot_identity_key": "E1",
            "last_seen_t": 0,
            "ot_residual_score": 0.12,
            "ot_noise_score": 0.20,
            "ot_unresolved_score": 0.18,
            "ot_ambiguity_score": 0.16,
            "ot_macro_micro_mismatch_score": 0.10,
            "ot_boundary_instability_score": 0.22,
            "observation_count": 1,
            "active_count": 0,
            "consecutive_active_count": 0,
            "max_noise_score_seen": 0.20,
            "noise_delta": 0.02,
            "residual_delta": 0.01,
        }
    ])
    return ot_action_view.copy(), ot_action_view, residual


def test_prediction_activation_short_spike_requests_projection():
    activation = DEPTPredictionActivationModule(
        PredictionActivationConfig(initial_reference_score=0.0, standard_threshold=0.05, deep_threshold=0.20)
    )
    ot_native, ot_action_view, residual = _ot_tables()
    first = activation.build(
        world_trace_before=_trace(0, 0.0),
        gt=pd.DataFrame(),
        kt=pd.DataFrame(),
        ot_native=ot_native,
        ot_action_view=ot_action_view,
        residual_noise_log=residual,
        loop_step=0,
        seed=7,
        scenario="unit",
    )
    assert bool(first["standard_projection_requested"].iloc[0]) is False
    second = activation.build(
        world_trace_before=_trace(1, 0.35),
        gt=pd.DataFrame(),
        kt=pd.DataFrame(),
        ot_native=ot_native,
        ot_action_view=ot_action_view,
        residual_noise_log=residual,
        loop_step=1,
        seed=7,
        scenario="unit",
    )
    assert float(second["short_intensity_change"].iloc[0]) > 0.05
    assert bool(second["standard_projection_requested"].iloc[0]) is True


def test_prediction_activation_integrates_directional_drift():
    activation = DEPTPredictionActivationModule(
        PredictionActivationConfig(initial_reference_score=0.0, standard_threshold=0.004, deep_threshold=0.99, short_window=3, mid_window=6)
    )
    ot_native, ot_action_view, residual = _ot_tables()
    last = pd.DataFrame()
    for step in range(7):
        last = activation.build(
            world_trace_before=_direction_trace(step, drift=0.015 * step),
            gt=pd.DataFrame(),
            kt=pd.DataFrame(),
            ot_native=ot_native,
            ot_action_view=ot_action_view,
            residual_noise_log=residual,
            loop_step=step,
            seed=7,
            scenario="unit",
        )
    assert float(last["overconvergence_integral_mid"].iloc[0]) >= 0.0
    assert float(last["fixation_integral_mid"].iloc[0]) >= 0.0
    assert bool(last["standard_projection_requested"].iloc[0]) is True


def test_prediction_module_emits_values_without_judgment_terms():
    module = DEPTPredictionModule()
    ot_native, ot_action_view, residual = _ot_tables()
    outputs = module.build(
        world_trace_before=_trace(0, 0.0),
        baseline_trace_after=_trace(1, 0.05),
        gt=pd.DataFrame([{"gt_uncertainty": 0.3, "gt_relation_lock": 0.4}]),
        kt=pd.DataFrame([{"kt_n_observations": 2, "kt_uncertainty_slope": 0.03}]),
        ot_native=ot_native,
        ot_action_view=ot_action_view,
        residual_noise_log=residual,
        loop_step=0,
        seed=7,
        scenario="unit",
    )
    assert set(outputs) == {
        "dept_prediction_entity_projection",
        "dept_prediction_relation_projection",
        "dept_prediction_ot_context",
        "dept_prediction_dynamics_projection",
        "dept_prediction_global_summary",
        "dept_prediction_output_packet",
    }
    for name, table in outputs.items():
        assert table is not None
        assert not table.empty, name
    assert output_contains_judgment_terms(outputs) is False


def test_prediction_module_uses_baseline_trace_as_no_action_projection():
    module = DEPTPredictionModule()
    _ot_native, ot_action_view, residual = _ot_tables()
    outputs = module.build(
        world_trace_before=_trace(0, 0.0),
        baseline_trace_after=_trace(1, 0.05),
        gt=pd.DataFrame(),
        kt=pd.DataFrame(),
        ot_native=ot_action_view,
        ot_action_view=ot_action_view,
        residual_noise_log=residual,
        loop_step=0,
        seed=7,
        scenario="unit",
    )
    entity_projection = outputs["dept_prediction_entity_projection"]
    row = entity_projection[
        (entity_projection["entity_id"] == "E1")
        & (entity_projection["metric_name"] == "activity")
    ].iloc[0]
    assert row["projection_source"] == "baseline_no_action_trace"
    assert int(row["projection_horizon_steps"]) == 1
    assert abs(float(row["projected_no_action_delta"]) - 0.05) < 1e-9
    assert abs(float(row["projected_no_action_delta_per_step"]) - 0.05) < 1e-9


def test_prediction_module_emits_dynamics_direction_and_strength_schema():
    module = DEPTPredictionModule()
    ot_native, ot_action_view, residual = _ot_tables()
    outputs = module.build(
        world_trace_before=_direction_trace(0, drift=0.0),
        baseline_trace_after=_direction_trace(3, drift=0.18),
        gt=pd.DataFrame(),
        kt=pd.DataFrame(),
        ot_native=ot_native,
        ot_action_view=ot_action_view,
        residual_noise_log=residual,
        loop_step=0,
        seed=7,
        scenario="unit",
    )
    dynamics = outputs["dept_prediction_dynamics_projection"].iloc[0]
    assert dynamics["predicted_dynamics_direction"] in ALLOWED_DYNAMICS_DIRECTIONS
    assert float(dynamics["predicted_dynamics_strength"]) >= 0.0
    assert float(dynamics["predicted_direction_margin"]) >= -1.0
    packet = outputs["dept_prediction_output_packet"].iloc[0]
    assert packet["predicted_dynamics_direction"] == dynamics["predicted_dynamics_direction"]
    assert float(packet["predicted_dynamics_strength"]) == float(dynamics["predicted_dynamics_strength"])


def test_prediction_module_runner_integration_outputs_prediction_tables():
    cfg = FullSpecRunnerConfig(steps=1, seed=11, n_entities=8, run_baseline_shadow=True)
    outputs = run_fullspec_task16(cfg)
    assert "dept_prediction_activation_state" in outputs
    assert not outputs["dept_prediction_activation_state"].empty
    assert bool(outputs["dept_prediction_activation_state"]["standard_projection_requested"].iloc[0]) is True
    for name in [
        "dept_prediction_entity_projection",
        "dept_prediction_relation_projection",
        "dept_prediction_ot_context",
        "dept_prediction_global_summary",
        "dept_prediction_output_packet",
    ]:
        assert name in outputs
        assert not outputs[name].empty
    prediction_only = {k: outputs[k] for k in outputs if k.startswith("dept_prediction_")}
    assert output_contains_judgment_terms(prediction_only) is False


def test_prediction_module_is_dept_side_not_actionmodule_pull():
    cfg = FullSpecRunnerConfig(steps=1, seed=12, n_entities=8, run_baseline_shadow=True)
    runner = FullSpecIntegratedClosedLoopRunner(cfg)
    trace = runner.world_adapter.snapshot()
    artifacts = runner.run_cycle(0, trace)
    assert artifacts.dept_prediction_activation_state is not None
    assert not artifacts.dept_prediction_activation_state.empty
    assert artifacts.dept_prediction_output_packet is not None
    assert not artifacts.dept_prediction_output_packet.empty
    assert artifacts.baseline_trace_after is not None
    assert "prediction_packet_id" in artifacts.dept_prediction_output_packet.columns
    assert not artifacts.dept_prediction_global_summary.empty
