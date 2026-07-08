"""Task2-8j-32: main-default FullSpec route smoke and multi-step validation.

This validation checks the post-Task2-8j-31 default FullSpec configuration.
It intentionally relies on FullSpecRunnerConfig defaults for route selection.

It does not change runtime behavior. It verifies that the main default route is:

- static_pca_7_smoke G_t
- Task2-8j bridge enabled
- Task2-8j-primary ActionSurfacePlanning

and that the route holds for smoke and short multi-step scenarios.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
import json

import pandas as pd

from dept2_fullspec_runner_rc1.contracts import FullSpecRunnerConfig
from dept2_fullspec_runner_rc1.runner.fullspec_integrated_closed_loop_runner import run_fullspec_task16

TASK2_8J_32_VERSION = "task2_8j_32_main_default_route_validation_rc1"
TASK2_8J_32_SMOKE_STEPS = 1
TASK2_8J_32_MULTI_STEPS = 4
TASK2_8J_32_SCENARIOS = ["normal", "relation_lock"]


def _first_text(df: pd.DataFrame, col: str, default: str = "") -> str:
    if df is None or df.empty or col not in df.columns:
        return default
    return str(df[col].iloc[0])


def _first_bool(df: pd.DataFrame, col: str, default: bool = False) -> bool:
    if df is None or df.empty or col not in df.columns:
        return bool(default)
    try:
        return bool(df[col].iloc[0])
    except Exception:
        return bool(default)


def _step_set(df: pd.DataFrame) -> set[int]:
    if df is None or df.empty or "loop_step" not in df.columns:
        return set()
    return set(df["loop_step"].astype(int).unique())


def _count_true(df: pd.DataFrame, col: str) -> int:
    if df is None or df.empty or col not in df.columns:
        return 0
    return int(df[col].fillna(False).astype(bool).sum())


def _run_default(*, steps: int, scenario: str) -> dict[str, pd.DataFrame]:
    cfg = FullSpecRunnerConfig(
        steps=steps,
        scenario=scenario,
        canonical_commit_enabled=False,
        canonical_commit_dry_run=True,
        run_baseline_shadow=False,
    )
    assert cfg.gt_route == "static_pca_7_smoke"
    assert cfg.task2_8j_bridge_enabled is True
    assert cfg.action_planning_route == "task2_8j_primary"
    return run_fullspec_task16(cfg)


def _summarize_run(*, label: str, scenario: str, steps: int, outputs: dict[str, pd.DataFrame]) -> dict[str, Any]:
    gt = outputs["gt"]
    bridge = outputs["task2_8j_bridge_audit"]
    planning = outputs["action_surface_planning_audit"]
    candidates = outputs["action_candidates"]
    needs = outputs["local_observation_needs"]
    gate = outputs["coactivation_gate"]
    execution = outputs["action_execution_audit"]
    transition = outputs["world_transition_audit"]
    expected_steps = set(range(steps))
    primary_candidate_rows = _count_true(candidates, "task2_8j_primary_candidate")
    primary_need_rows = _count_true(needs, "task2_8j_primary_need_source")
    transition_time_ok = bool(
        not transition.empty
        and "world_t_after" in transition.columns
        and "world_t_before" in transition.columns
        and (transition["world_t_after"].astype(int) == transition["world_t_before"].astype(int) + 1).all()
    )
    status = bool(
        _step_set(gt) == expected_steps
        and _step_set(bridge) == expected_steps
        and _step_set(planning) == expected_steps
        and _step_set(candidates) == expected_steps
        and _step_set(needs) == expected_steps
        and _step_set(gate) == expected_steps
        and _step_set(execution) == expected_steps
        and _first_text(gt, "gt_main_map_name") == "static_pca_7"
        and _first_bool(gt, "static_pca7_view_attached")
        and _first_bool(gt, "legacy_gt_columns_preserved")
        and bool((bridge["bridge_status"].astype(str) == "pass").all())
        and bool((planning["audit_status"].astype(str) == "pass").all())
        and bool((planning["action_planning_route"].astype(str) == "task2_8j_primary").all())
        and bool(planning["task2_8j_primary_route_used"].fillna(False).astype(bool).all())
        and bool(planning["task2_8j_material_promoted_to_action_candidates"].fillna(False).astype(bool).all())
        and primary_candidate_rows > 0
        and primary_need_rows > 0
        and bool((gate["coactivation_gate_audit_status"].astype(str) == "pass").all())
        and bool((execution["audit_status"].astype(str) == "pass").all())
        and bool(execution["actionmodule_received_actionframe_only"].fillna(False).astype(bool).all())
        and not bool(execution["direct_gk_input_to_actionmodule"].fillna(False).astype(bool).any())
        and not bool(execution["direct_ot_input_to_actionmodule"].fillna(False).astype(bool).any())
        and not bool(execution["direct_parameter_box_input_to_actionmodule"].fillna(False).astype(bool).any())
        and not bool(execution["canonical_parameter_write_performed"].fillna(False).astype(bool).any())
        and transition_time_ok
    )
    return {
        "task2_8j_32_version": TASK2_8J_32_VERSION,
        "run_label": label,
        "scenario": scenario,
        "requested_steps": steps,
        "observed_steps": "|".join(str(s) for s in sorted(_step_set(gt))),
        "gt_route_default_expected": "static_pca_7_smoke",
        "gt_main_map_name": _first_text(gt, "gt_main_map_name"),
        "static_pca7_view_attached": _first_bool(gt, "static_pca7_view_attached"),
        "legacy_gt_columns_preserved": _first_bool(gt, "legacy_gt_columns_preserved"),
        "bridge_rows": int(len(bridge)),
        "bridge_all_pass": bool((bridge["bridge_status"].astype(str) == "pass").all()),
        "action_planning_route": _first_text(planning, "action_planning_route"),
        "planning_all_pass": bool((planning["audit_status"].astype(str) == "pass").all()),
        "task2_8j_primary_route_used_all_steps": bool(planning["task2_8j_primary_route_used"].fillna(False).astype(bool).all()),
        "task2_8j_material_promoted_all_steps": bool(planning["task2_8j_material_promoted_to_action_candidates"].fillna(False).astype(bool).all()),
        "action_candidate_rows": int(len(candidates)),
        "task2_8j_primary_candidate_rows": primary_candidate_rows,
        "task2_8j_primary_need_rows": primary_need_rows,
        "gate_all_pass": bool((gate["coactivation_gate_audit_status"].astype(str) == "pass").all()),
        "execution_all_pass": bool((execution["audit_status"].astype(str) == "pass").all()),
        "actionmodule_actionframe_only_all_steps": bool(execution["actionmodule_received_actionframe_only"].fillna(False).astype(bool).all()),
        "direct_gk_input_count": _count_true(execution, "direct_gk_input_to_actionmodule"),
        "direct_ot_input_count": _count_true(execution, "direct_ot_input_to_actionmodule"),
        "direct_parameter_box_input_count": _count_true(execution, "direct_parameter_box_input_to_actionmodule"),
        "canonical_write_count": _count_true(execution, "canonical_parameter_write_performed"),
        "transition_time_ok": transition_time_ok,
        "validation_status": "pass" if status else "fail",
    }


def build_task2_8j_32_validation() -> dict[str, pd.DataFrame]:
    rows: list[dict[str, Any]] = []

    smoke = _run_default(steps=TASK2_8J_32_SMOKE_STEPS, scenario="normal")
    rows.append(_summarize_run(label="default_smoke", scenario="normal", steps=TASK2_8J_32_SMOKE_STEPS, outputs=smoke))

    for scenario in TASK2_8J_32_SCENARIOS:
        outputs = _run_default(steps=TASK2_8J_32_MULTI_STEPS, scenario=scenario)
        rows.append(_summarize_run(label="default_multistep", scenario=scenario, steps=TASK2_8J_32_MULTI_STEPS, outputs=outputs))

    summary = pd.DataFrame(rows)
    decision = pd.DataFrame([{
        "task2_8j_32_version": TASK2_8J_32_VERSION,
        "decision": "main_default_route_validated" if bool((summary["validation_status"].astype(str) == "pass").all()) else "main_default_route_not_validated",
        "all_runs_pass": bool((summary["validation_status"].astype(str) == "pass").all()),
        "run_count": int(len(summary)),
        "pass_count": int((summary["validation_status"].astype(str) == "pass").sum()),
        "fail_count": int((summary["validation_status"].astype(str) != "pass").sum()),
        "runtime_default_changed_by_task2_8j_32": False,
        "legacy_route_deleted_by_task2_8j_32": False,
        "canonical_write_enabled_by_task2_8j_32": False,
        "axis_execution_enabled_by_task2_8j_32": False,
        "superiority_claim_made": False,
        "recommended_next_task": "Task2-8j-33: broaden default-route stress scenarios" if bool((summary["validation_status"].astype(str) == "pass").all()) else "Fix main default route before further promotion",
    }])
    return {
        "task2_8j_32_decision": decision,
        "task2_8j_32_run_summary": summary,
    }


def write_task2_8j_32_validation(out_dir: Path) -> dict[str, pd.DataFrame]:
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = build_task2_8j_32_validation()
    for name, df in outputs.items():
        df.to_csv(out_dir / f"{name}.csv", index=False)
        df.to_json(out_dir / f"{name}.json", orient="records", indent=2, force_ascii=False)
    manifest = {
        "version": TASK2_8J_32_VERSION,
        "tables": sorted(outputs),
        "decision": str(outputs["task2_8j_32_decision"]["decision"].iloc[0]),
        "runtime_default_changed": False,
    }
    (out_dir / "task2_8j_32_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return outputs


if __name__ == "__main__":
    write_task2_8j_32_validation(Path("results/task2_8j_32_main_default_route_validation"))
