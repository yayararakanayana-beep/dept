#!/usr/bin/env python3
"""DEPT2 closed-loop codebase RC1 runner.

Purpose:
    Establish a clean baseline execution codebase split into:
      - pseudo_reality system
      - DEPT2/H-DEPT integrated system
      - action module
      - lower parameter governance box

This runner is a smoke/baseline validation, not performance proof.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import json
import sys
from typing import Dict, List

import numpy as np
import pandas as pd

# Allow running from package root or directly.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pseudo_reality.system import PseudoRealityConfig, PseudoRealitySystem
from pseudo_reality.observation import GtKtBuilder, GraphObjectBuilder
from dept2_system.hdept_observer import HDEPTObserver
from dept2_system.h11_local import H11LocalPressureReceiver
from dept2_system.parameter_box import LowerParameterGovernanceBox
from dept2_system.action_surface import ActionSurface
from dept2_system.v8_support import V8LocalSupport
from dept2_system.final_gate import FinalGate
from action_module.actions import ActionModule


def run_one(seed: int, scenario: str, steps: int, out_dir: Path) -> Dict[str, pd.DataFrame]:
    world = PseudoRealitySystem(PseudoRealityConfig(seed=seed, scenario=scenario))
    gk_builder = GtKtBuilder(kt_window=6)
    go_builder = GraphObjectBuilder()
    hdept = HDEPTObserver()
    h11 = H11LocalPressureReceiver()
    param_box = LowerParameterGovernanceBox()
    surface = ActionSurface()
    v8 = V8LocalSupport()
    gate = FinalGate()
    actions = ActionModule()

    all_gt, all_kt, all_formal, all_m, all_pressure, all_h11 = [], [], [], [], [], []
    all_params, all_reg, all_graph, all_surface, all_v8, all_gate, all_action, all_metrics = [], [], [], [], [], [], [], []
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
        reg, param_updates = param_box.update(formal, h11_field)
        params = param_box.current_params()
        graph_objects = go_builder.build(trace)
        candidates = surface.compress(graph_objects, h11_field, params)
        v8_eval = v8.evaluate(candidates, graph_objects, params)
        final = gate.decide(v8_eval, params)
        action_frame = actions.build_action_frame(final, params)

        # Add loop metadata.
        for df in [gt, kt, formal, m, pressure, h11_field, param_updates, graph_objects, candidates, v8_eval, final, action_frame]:
            if df is not None and not df.empty:
                df["loop_step"] = step
                df["run_seed"] = seed
                df["run_scenario"] = scenario

        all_gt.append(gt); all_kt.append(kt); all_formal.append(formal); all_m.append(m); all_pressure.append(pressure); all_h11.append(h11_field)
        all_reg.append(reg); all_params.append(param_updates); all_graph.append(graph_objects); all_surface.append(candidates); all_v8.append(v8_eval); all_gate.append(final); all_action.append(action_frame)

        mean_risk = float(gt["gt_conflict"].mean())
        mean_uncertainty = float(gt["gt_uncertainty"].mean())
        mean_overconv = float(gt["gt_overconvergence"].mean())
        allow_rate = float((final.final_gate_decision == "allow").mean()) if not final.empty else 0.0
        weaken_rate = float((final.final_gate_decision == "weaken").mean()) if not final.empty else 0.0
        shadow_rate = float((final.final_gate_decision == "hold_shadow").mean()) if not final.empty else 0.0
        action_mass = float(action_frame["action_strength"].sum()) if not action_frame.empty else 0.0
        all_metrics.append(pd.DataFrame([{
            "run_seed": seed,
            "run_scenario": scenario,
            "loop_step": step,
            "gt_conflict_mean": mean_risk,
            "gt_uncertainty_mean": mean_uncertainty,
            "gt_overconvergence_mean": mean_overconv,
            "m_mean_overall": float(m["m_mean_overall"].mean()),
            "approved_pressure_l1": float(pressure["approved_component_l1"].mean()),
            "allow_rate": allow_rate,
            "weaken_rate": weaken_rate,
            "shadow_rate": shadow_rate,
            "action_mass": action_mass,
            "formal_input_contract": formal["formal_hdept_input_contract"].iloc[0],
        }]))

    return {
        "gt_global": pd.concat(all_gt, ignore_index=True),
        "kt_global": pd.concat(all_kt, ignore_index=True),
        "formal_gtkt_packets": pd.concat(all_formal, ignore_index=True),
        "m_observation": pd.concat(all_m, ignore_index=True),
        "pressure_candidates": pd.concat(all_pressure, ignore_index=True),
        "h11_local_pressure_field": pd.concat(all_h11, ignore_index=True),
        "parameter_registry": all_reg[-1],
        "parameter_updates": pd.concat(all_params, ignore_index=True),
        "graph_objects_audit": pd.concat(all_graph, ignore_index=True),
        "action_surface_candidates": pd.concat(all_surface, ignore_index=True),
        "v8_support_audit": pd.concat(all_v8, ignore_index=True),
        "final_gate_audit": pd.concat(all_gate, ignore_index=True),
        "action_module_frames": pd.concat(all_action, ignore_index=True) if all_action else pd.DataFrame(),
        "closed_loop_metrics": pd.concat(all_metrics, ignore_index=True),
    }


def validate_outputs(outputs: Dict[str, pd.DataFrame]) -> Dict[str, object]:
    formal = outputs["formal_gtkt_packets"]
    forbidden = [c for c in formal.columns if c.startswith(("graph_object", "v8_", "final_gate", "action_surface"))]
    metrics = outputs["closed_loop_metrics"]
    start = metrics.groupby(["run_seed", "run_scenario"]).first()["gt_conflict_mean"]
    end = metrics.groupby(["run_seed", "run_scenario"]).last()["gt_conflict_mean"]
    delta = (end - start)
    registry = outputs["parameter_registry"]
    param_updates = outputs["parameter_updates"]
    summary = {
        "validation_scope": "codebase_structure_and_smoke_closed_loop_not_performance_proof",
        "formal_input_no_lower_leakage": len(forbidden) == 0,
        "formal_input_forbidden_columns": forbidden,
        "pseudo_reality_rows": int(outputs["gt_global"].shape[0]),
        "formal_packet_rows": int(formal.shape[0]),
        "h11_pressure_field_rows": int(outputs["h11_local_pressure_field"].shape[0]),
        "action_surface_rows": int(outputs["action_surface_candidates"].shape[0]),
        "final_gate_rows": int(outputs["final_gate_audit"].shape[0]),
        "action_module_rows": int(outputs["action_module_frames"].shape[0]),
        "parameter_registry_rows": int(registry.shape[0]),
        "parameter_update_rows": int(param_updates.shape[0]),
        "mean_start_conflict": float(start.mean()),
        "mean_end_conflict": float(end.mean()),
        "mean_conflict_delta": float(delta.mean()),
        "max_abs_theta_delta": float(param_updates["theta_delta"].abs().max()) if not param_updates.empty else 0.0,
        "max_abs_theta_delta_within_registry": bool((param_updates.merge(registry[["parameter_name", "max_step_delta"]], on="parameter_name")["theta_delta"].abs() <= param_updates.merge(registry[["parameter_name", "max_step_delta"]], on="parameter_name")["max_step_delta"] + 1e-12).all()),
        "all_sanity_checks_passed": False,
    }
    summary["all_sanity_checks_passed"] = bool(
        summary["formal_input_no_lower_leakage"]
        and summary["formal_packet_rows"] > 0
        and summary["h11_pressure_field_rows"] > 0
        and summary["final_gate_rows"] > 0
        and summary["parameter_registry_rows"] >= 8
        and summary["max_abs_theta_delta_within_registry"]
    )
    return summary


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
            outputs = run_one(seed=seed, scenario=scenario, steps=args.steps, out_dir=out_dir)
            for k, df in outputs.items():
                collected.setdefault(k, []).append(df)

    merged = {k: pd.concat(v, ignore_index=True) for k, v in collected.items() if v}
    # registry duplicates across runs; keep unique.
    if "parameter_registry" in merged:
        merged["parameter_registry"] = merged["parameter_registry"].drop_duplicates("parameter_name").reset_index(drop=True)

    for name, df in merged.items():
        df.to_csv(out_dir / f"{name}_RC1.csv", index=False)

    summary = validate_outputs(merged)
    with open(out_dir / "validation_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
