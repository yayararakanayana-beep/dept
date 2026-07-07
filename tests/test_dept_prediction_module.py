import pandas as pd

from dept2_fullspec_runner_rc1.contracts import FullSpecRunnerConfig
from dept2_fullspec_runner_rc1.modules.dept_prediction_module import (
    DEPTPredictionModule,
    output_contains_judgment_terms,
)
from dept2_fullspec_runner_rc1.runner.fullspec_integrated_closed_loop_runner import (
    FullSpecIntegratedClosedLoopRunner,
    run_fullspec_task16,
)


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
        "dept_prediction_global_summary",
        "dept_prediction_output_packet",
    }
    assert not outputs["dept_prediction_entity_projection"].empty
    assert not outputs["dept_prediction_relation_projection"].empty
    assert not outputs["dept_prediction_ot_context"].empty
    assert not outputs["dept_prediction_global_summary"].empty
    assert not outputs["dept_prediction_output_packet"].empty
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


def test_prediction_module_runner_integration_outputs_prediction_tables():
    cfg = FullSpecRunnerConfig(steps=1, seed=11, n_entities=8, run_baseline_shadow=True)
    outputs = run_fullspec_task16(cfg)
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
    assert artifacts.dept_prediction_output_packet is not None
    assert not artifacts.dept_prediction_output_packet.empty
    assert artifacts.baseline_trace_after is not None
    assert "prediction_packet_id" in artifacts.dept_prediction_output_packet.columns
    # The prediction packet exists before action execution audit is constructed.
    # It is built on the DEPT side from existing artifacts, not by the action module pulling internals.
    assert not artifacts.dept_prediction_global_summary.empty
