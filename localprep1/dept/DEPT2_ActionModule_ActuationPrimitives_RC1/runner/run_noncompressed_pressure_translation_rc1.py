#!/usr/bin/env python3
"""DEPT2 non-compressed pressure translation RC1 runner.

Purpose:
    Validate the revised contract:
      - lower layer receives upper pressure without compressing it
      - H-DEPT approved components are annotated, not collapsed
      - ActionSurface emits affordances, not pressure-compressed commands
      - ActionPlanner is the first compression/decision point
      - Actuator applies only final gated ActionCommands to pseudo reality
      - H-DEPT formal input remains G_t/K_t global only
"""
from __future__ import annotations

import argparse
from pathlib import Path
import json
import sys
from typing import Dict, List

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pseudo_reality.system import PseudoRealityConfig, PseudoRealitySystem
from pseudo_reality.observation import GtKtBuilder, GraphObjectBuilder
from dept2_system.hdept_observer import HDEPTObserver
from dept2_system.h11_local import H11LocalPressureReceiver
from dept2_system.pressure_intent import HDEPTPressureIntentAnnotator
from dept2_system.parameter_box import LowerParameterGovernanceBox
from dept2_system.action_surface import ActionSurface
from dept2_system.v8_support import V8LocalSupport
from dept2_system.final_gate import FinalGate
from action_module.actions import ActionPlanner, ActionModule


def run_one(seed: int, scenario: str, steps: int) -> Dict[str, pd.DataFrame]:
    world = PseudoRealitySystem(PseudoRealityConfig(seed=seed, scenario=scenario))
    gk_builder = GtKtBuilder(kt_window=6)
    go_builder = GraphObjectBuilder()
    hdept = HDEPTObserver()
    h11 = H11LocalPressureReceiver()
    annotator = HDEPTPressureIntentAnnotator()
    param_box = LowerParameterGovernanceBox()
    surface = ActionSurface()
    v8 = V8LocalSupport()
    planner = ActionPlanner()
    gate = FinalGate()
    actuator = ActionModule()

    collected: Dict[str, List[pd.DataFrame]] = {k: [] for k in [
        "gt_global", "kt_global", "formal_gtkt_packets", "m_observation", "pressure_candidates",
        "h11_local_pressure_field", "pressure_intent_bundle", "parameter_registry", "parameter_updates",
        "graph_objects_audit", "action_surface_affordance", "v8_affordance_support",
        "planned_action_candidates", "final_gate_audit", "action_module_frames", "closed_loop_metrics",
    ]}
    action_frame = pd.DataFrame()
    prev_pressure = None

    for step in range(steps):
        trace = world.emit_trace() if step == 0 else world.step(action_frame)
        gt = gk_builder.build_gt(trace)
        kt = gk_builder.build_kt_global()
        formal = gk_builder.build_formal_packet(gt, kt)
        m = hdept.observe_m(formal)
        pressure = hdept.propose_pressure(m, prev_pressure=prev_pressure)
        prev_pressure = pressure.copy()
        h11_field = h11.receive(m, pressure)
        intents = annotator.annotate(h11_field)
        registry, param_updates = param_box.update(formal, h11_field)
        params = param_box.current_params()
        graph_objects = go_builder.build(trace)
        affordance = surface.build_affordance(graph_objects, params)
        v8_affordance = v8.evaluate(affordance, graph_objects, params)
        planned = planner.plan(intents, v8_affordance, params)
        v8_planned = v8.evaluate(planned, graph_objects, params) if not planned.empty else pd.DataFrame()
        final = gate.decide(v8_planned, params)
        action_frame = actuator.build_action_frame(final, params)

        for df in [gt, kt, formal, m, pressure, h11_field, intents, param_updates, graph_objects, affordance, v8_affordance, planned, final, action_frame]:
            if df is not None and not df.empty:
                df["loop_step"] = step
                df["run_seed"] = seed
                df["run_scenario"] = scenario

        # Metrics
        metrics = pd.DataFrame([{
            "run_seed": seed,
            "run_scenario": scenario,
            "loop_step": step,
            "gt_conflict_mean": float(gt["gt_conflict"].mean()),
            "gt_uncertainty_mean": float(gt["gt_uncertainty"].mean()),
            "gt_exploration_mean": float(gt["gt_exploration"].mean()),
            "gt_overconvergence_mean": float(gt["gt_overconvergence"].mean()),
            "m_mean_overall": float(m["m_mean_overall"].mean()),
            "approved_pressure_l1": float(pressure["approved_component_l1"].mean()),
            "intent_rows": int(intents.shape[0]),
            "unique_intent_effects": int(intents["semantic_effect"].nunique()) if not intents.empty else 0,
            "affordance_rows": int(affordance.shape[0]),
            "planned_rows": int(planned.shape[0]),
            "final_rows": int(final.shape[0]),
            "action_rows": int(action_frame.shape[0]),
            "allow_rate": float((final.final_gate_decision == "allow").mean()) if not final.empty else 0.0,
            "weaken_rate": float((final.final_gate_decision == "weaken").mean()) if not final.empty else 0.0,
            "shadow_rate": float((final.final_gate_decision == "hold_shadow").mean()) if not final.empty else 0.0,
            "action_mass": float(action_frame["action_strength"].sum()) if not action_frame.empty else 0.0,
            "exploration_action_mass": float(action_frame.loc[action_frame["action_channel"] == "exploration_injection", "action_strength"].sum()) if not action_frame.empty else 0.0,
            "formal_input_contract": formal["formal_hdept_input_contract"].iloc[0],
        }])

        frames = {
            "gt_global": gt, "kt_global": kt, "formal_gtkt_packets": formal, "m_observation": m,
            "pressure_candidates": pressure, "h11_local_pressure_field": h11_field,
            "pressure_intent_bundle": intents, "parameter_registry": registry,
            "parameter_updates": param_updates, "graph_objects_audit": graph_objects,
            "action_surface_affordance": affordance, "v8_affordance_support": v8_affordance,
            "planned_action_candidates": planned, "final_gate_audit": final,
            "action_module_frames": action_frame, "closed_loop_metrics": metrics,
        }
        for k, df in frames.items():
            if df is not None and not df.empty:
                collected[k].append(df)

    return {k: pd.concat(v, ignore_index=True) if v else pd.DataFrame() for k, v in collected.items()}


def validate_outputs(outputs: Dict[str, pd.DataFrame]) -> dict:
    formal = outputs["formal_gtkt_packets"]
    forbidden = [c for c in formal.columns if c.startswith(("graph_object", "v8_", "final_gate", "action_surface", "pressure_intent", "planner"))]
    intents = outputs["pressure_intent_bundle"]
    planned = outputs["planned_action_candidates"]
    affordance = outputs["action_surface_affordance"]
    metrics = outputs["closed_loop_metrics"]
    registry = outputs["parameter_registry"]
    p_updates = outputs["parameter_updates"]

    # No old signed-mean compression should appear in affordance or intent layer.
    forbidden_compression_cols = [c for c in affordance.columns if c in ["h11_dimension", "h11_local_received_pressure", "dim_pressure"]]
    first_compression_ok = (not planned.empty) and planned.get("first_compression_layer", pd.Series(dtype=str)).eq("ActionPlanner").all()
    intent_noncompress_ok = (not intents.empty) and intents.get("compression_allowed_before_action_planner", pd.Series(dtype=bool)).eq(False).all()

    start = metrics.groupby(["run_seed", "run_scenario"]).first()
    end = metrics.groupby(["run_seed", "run_scenario"]).last()
    delta = end["gt_conflict_mean"] - start["gt_conflict_mean"]
    scenario_summary = metrics.groupby("run_scenario").agg(
        mean_action_mass=("action_mass", "mean"),
        mean_exploration_action_mass=("exploration_action_mass", "mean"),
        mean_planned_rows=("planned_rows", "mean"),
        start_conflict=("gt_conflict_mean", "first"),
        end_conflict=("gt_conflict_mean", "last"),
    ).reset_index()

    # exploration_loss should no longer be zero-action purely because of premature signed compression.
    exp_rows = metrics[metrics["run_scenario"] == "exploration_loss"]
    exploration_loss_has_plans = bool((exp_rows["planned_rows"] > 0).any()) if not exp_rows.empty else False
    exploration_loss_has_actions = bool((exp_rows["action_rows"] > 0).any()) if not exp_rows.empty else False

    merged = p_updates.merge(registry[["parameter_name", "max_step_delta"]], on="parameter_name", how="left") if not p_updates.empty and not registry.empty else pd.DataFrame()
    theta_ok = bool((merged["theta_delta"].abs() <= merged["max_step_delta"] + 1e-12).all()) if not merged.empty else True

    summary = {
        "validation_scope": "noncompressed_pressure_translation_to_action_planner__not_performance_proof",
        "formal_input_no_lower_leakage": len(forbidden) == 0,
        "formal_input_forbidden_columns": forbidden,
        "intent_rows": int(intents.shape[0]),
        "unique_semantic_effects": int(intents["semantic_effect"].nunique()) if not intents.empty else 0,
        "affordance_rows": int(affordance.shape[0]),
        "planned_action_rows": int(planned.shape[0]),
        "final_gate_rows": int(outputs["final_gate_audit"].shape[0]),
        "action_module_rows": int(outputs["action_module_frames"].shape[0]),
        "first_compression_layer_is_action_planner": bool(first_compression_ok),
        "intent_annotation_is_noncompressive": bool(intent_noncompress_ok),
        "action_surface_has_no_pressure_compression_columns": len(forbidden_compression_cols) == 0,
        "forbidden_action_surface_compression_columns": forbidden_compression_cols,
        "exploration_loss_has_planned_actions": exploration_loss_has_plans,
        "exploration_loss_has_actuated_actions": exploration_loss_has_actions,
        "mean_start_conflict": float(start["gt_conflict_mean"].mean()),
        "mean_end_conflict": float(end["gt_conflict_mean"].mean()),
        "mean_conflict_delta": float(delta.mean()),
        "max_abs_theta_delta_within_registry": theta_ok,
        "scenario_summary_records": scenario_summary.to_dict(orient="records"),
        "all_sanity_checks_passed": False,
    }
    summary["all_sanity_checks_passed"] = bool(
        summary["formal_input_no_lower_leakage"]
        and summary["intent_rows"] > 0
        and summary["unique_semantic_effects"] >= 6
        and summary["affordance_rows"] > 0
        and summary["planned_action_rows"] > 0
        and summary["first_compression_layer_is_action_planner"]
        and summary["intent_annotation_is_noncompressive"]
        and summary["action_surface_has_no_pressure_compression_columns"]
        and summary["max_abs_theta_delta_within_registry"]
        and summary["exploration_loss_has_planned_actions"]
    )
    return summary, scenario_summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument("--seeds", type=str, default="42,43")
    parser.add_argument("--scenarios", type=str, default="normal,exploration_loss,relation_lock,shock")
    parser.add_argument("--out", type=str, default=str(ROOT / "results"))
    args = parser.parse_args()
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    seeds = [int(x) for x in args.seeds.split(",") if x]
    scenarios = [x for x in args.scenarios.split(",") if x]

    collected: Dict[str, List[pd.DataFrame]] = {}
    for seed in seeds:
        for scenario in scenarios:
            outputs = run_one(seed, scenario, args.steps)
            for k, df in outputs.items():
                if not df.empty:
                    collected.setdefault(k, []).append(df)
    merged = {k: pd.concat(v, ignore_index=True) for k, v in collected.items()}
    if "parameter_registry" in merged:
        merged["parameter_registry"] = merged["parameter_registry"].drop_duplicates("parameter_name").reset_index(drop=True)
    for name, df in merged.items():
        df.to_csv(out_dir / f"{name}_RC1.csv", index=False)
    summary, scenario_summary = validate_outputs(merged)
    scenario_summary.to_csv(out_dir / "scenario_summary_RC1.csv", index=False)
    with open(out_dir / "validation_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
