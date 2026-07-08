"""Task2-8j-30: default-candidate route readiness decision.

This validation consumes the Task2-8j-29 legacy-vs-primary comparison output and
applies conservative promotion gates.

It does not switch the runtime default.  It only decides whether the
Task2-8j-primary route is ready to become the next default-candidate route in a
separate follow-up task.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
import json

import pandas as pd

from validation.task2_8j_29_legacy_vs_primary_multistep_comparison import (
    TASK2_8J_29_SCENARIOS,
    TASK2_8J_29_STEPS,
    build_task2_8j_29_comparison,
)

TASK2_8J_30_VERSION = "task2_8j_30_primary_default_readiness_rc1"
TASK2_8J_30_DECISION_CONTRACT = (
    "Task2_8j_30_PrimaryDefaultReadiness__"
    "comparison_based_decision_only__no_runtime_default_switch"
)

MAX_ABS_MEAN_GATE_RISK_DELTA = 0.25
MAX_GATE_DECISION_CHANGED_STEP_RATIO = 0.50
REQUIRED_TOTAL_PRIMARY_CANDIDATES_PER_SCENARIO = 1


PROMOTION_GATES = [
    "comparison_tables_exist",
    "all_comparison_status_pass",
    "legacy_all_planning_pass",
    "task2_8j_all_planning_pass",
    "legacy_all_execution_pass",
    "task2_8j_all_execution_pass",
    "legacy_actionframe_only_boundary",
    "task2_8j_actionframe_only_boundary",
    "task2_8j_primary_candidates_present",
    "task2_8j_primary_needs_present",
    "transition_time_ok_both_routes",
    "no_canonical_write",
    "no_direct_dept_actionmodule_input",
    "gate_risk_delta_within_watch_bound",
    "gate_decision_change_ratio_within_watch_bound",
]


def _bool_all(series: pd.Series) -> bool:
    return bool(series.fillna(False).astype(bool).all())


def _count_true(series: pd.Series) -> int:
    return int(series.fillna(False).astype(bool).sum())


def _gate_rows(summary: pd.DataFrame, per_step: pd.DataFrame, route_delta: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    comparison_tables_exist = bool(not summary.empty and not per_step.empty and not route_delta.empty)
    rows.append({
        "gate_name": "comparison_tables_exist",
        "gate_pass": comparison_tables_exist,
        "gate_value": f"summary={len(summary)}|per_step={len(per_step)}|route_delta={len(route_delta)}",
        "required_value": "all_non_empty",
        "gate_reason": "Task2-8j-30 must be grounded in Task2-8j-29 comparison tables.",
    })

    if summary.empty or per_step.empty or route_delta.empty:
        for gate in PROMOTION_GATES[1:]:
            rows.append({
                "gate_name": gate,
                "gate_pass": False,
                "gate_value": "missing_comparison_tables",
                "required_value": "available",
                "gate_reason": "Comparison output is missing, so promotion readiness cannot be evaluated.",
            })
        return pd.DataFrame(rows)

    rows.extend([
        {
            "gate_name": "all_comparison_status_pass",
            "gate_pass": bool((summary["comparison_status"].astype(str) == "pass").all()),
            "gate_value": "|".join(summary["comparison_status"].astype(str)),
            "required_value": "all pass",
            "gate_reason": "Both routes must be comparison-ready before any default-candidate discussion.",
        },
        {
            "gate_name": "legacy_all_planning_pass",
            "gate_pass": _bool_all(summary["legacy_all_planning_pass"]),
            "gate_value": str(list(summary["legacy_all_planning_pass"].astype(bool))),
            "required_value": "all True",
            "gate_reason": "Legacy route must remain healthy because it will remain fallback.",
        },
        {
            "gate_name": "task2_8j_all_planning_pass",
            "gate_pass": _bool_all(summary["task2_8j_all_planning_pass"]),
            "gate_value": str(list(summary["task2_8j_all_planning_pass"].astype(bool))),
            "required_value": "all True",
            "gate_reason": "Task2-8j primary route must pass planning audits across scenarios.",
        },
        {
            "gate_name": "legacy_all_execution_pass",
            "gate_pass": _bool_all(summary["legacy_all_execution_pass"]),
            "gate_value": str(list(summary["legacy_all_execution_pass"].astype(bool))),
            "required_value": "all True",
            "gate_reason": "Legacy route execution audit must remain pass.",
        },
        {
            "gate_name": "task2_8j_all_execution_pass",
            "gate_pass": _bool_all(summary["task2_8j_all_execution_pass"]),
            "gate_value": str(list(summary["task2_8j_all_execution_pass"].astype(bool))),
            "required_value": "all True",
            "gate_reason": "Task2-8j route execution audit must remain pass.",
        },
        {
            "gate_name": "legacy_actionframe_only_boundary",
            "gate_pass": _bool_all(summary["legacy_all_actionframe_only"]),
            "gate_value": str(list(summary["legacy_all_actionframe_only"].astype(bool))),
            "required_value": "all True",
            "gate_reason": "ActionModule boundary must remain ActionFrame-only for legacy route.",
        },
        {
            "gate_name": "task2_8j_actionframe_only_boundary",
            "gate_pass": _bool_all(summary["task2_8j_all_actionframe_only"]),
            "gate_value": str(list(summary["task2_8j_all_actionframe_only"].astype(bool))),
            "required_value": "all True",
            "gate_reason": "Task2-8j must not pass DEPT internals directly to ActionModule.",
        },
    ])

    primary_candidates_ok = bool((summary["task2_8j_total_primary_candidate_rows"].astype(int) >= REQUIRED_TOTAL_PRIMARY_CANDIDATES_PER_SCENARIO).all())
    primary_needs_ok = bool((summary["task2_8j_total_primary_need_rows"].astype(int) >= REQUIRED_TOTAL_PRIMARY_CANDIDATES_PER_SCENARIO).all())
    rows.append({
        "gate_name": "task2_8j_primary_candidates_present",
        "gate_pass": primary_candidates_ok,
        "gate_value": str(list(summary["task2_8j_total_primary_candidate_rows"].astype(int))),
        "required_value": f">= {REQUIRED_TOTAL_PRIMARY_CANDIDATES_PER_SCENARIO} per scenario",
        "gate_reason": "The primary route must actually create Task2-8j-derived candidates.",
    })
    rows.append({
        "gate_name": "task2_8j_primary_needs_present",
        "gate_pass": primary_needs_ok,
        "gate_value": str(list(summary["task2_8j_total_primary_need_rows"].astype(int))),
        "required_value": f">= {REQUIRED_TOTAL_PRIMARY_CANDIDATES_PER_SCENARIO} per scenario",
        "gate_reason": "Task2-8j candidates should trigger local-observation needs, not bypass audit.",
    })

    transition_ok = bool(route_delta["legacy_transition_time_ok"].fillna(False).astype(bool).all() and route_delta["task2_8j_transition_time_ok"].fillna(False).astype(bool).all())
    rows.append({
        "gate_name": "transition_time_ok_both_routes",
        "gate_pass": transition_ok,
        "gate_value": f"legacy={_count_true(route_delta['legacy_transition_time_ok'])}/{len(route_delta)}|task2_8j={_count_true(route_delta['task2_8j_transition_time_ok'])}/{len(route_delta)}",
        "required_value": "all True for both routes",
        "gate_reason": "Both routes must advance pseudo-world time consistently.",
    })

    no_canonical_write = bool((per_step["canonical_parameter_write_performed"].fillna(False).astype(bool) == False).all() and (per_step["transition_canonical_write_performed"].fillna(False).astype(bool) == False).all())
    rows.append({
        "gate_name": "no_canonical_write",
        "gate_pass": no_canonical_write,
        "gate_value": f"execution_writes={_count_true(per_step['canonical_parameter_write_performed'])}|transition_writes={_count_true(per_step['transition_canonical_write_performed'])}",
        "required_value": "0 writes",
        "gate_reason": "Default-candidate readiness must not depend on irreversible canonical writeback.",
    })

    no_direct_inputs = bool(
        (per_step["direct_gk_input_to_actionmodule"].fillna(False).astype(bool) == False).all()
        and (per_step["direct_ot_input_to_actionmodule"].fillna(False).astype(bool) == False).all()
        and (per_step["direct_parameter_box_input_to_actionmodule"].fillna(False).astype(bool) == False).all()
    )
    rows.append({
        "gate_name": "no_direct_dept_actionmodule_input",
        "gate_pass": no_direct_inputs,
        "gate_value": (
            f"gk={_count_true(per_step['direct_gk_input_to_actionmodule'])}|"
            f"ot={_count_true(per_step['direct_ot_input_to_actionmodule'])}|"
            f"parameter_box={_count_true(per_step['direct_parameter_box_input_to_actionmodule'])}"
        ),
        "required_value": "0 direct inputs",
        "gate_reason": "ActionModule must still receive ActionFrame only.",
    })

    max_abs_gate_risk_delta = float(route_delta["gate_risk_delta_task2_minus_legacy"].astype(float).abs().max())
    gate_risk_ok = bool(max_abs_gate_risk_delta <= MAX_ABS_MEAN_GATE_RISK_DELTA)
    rows.append({
        "gate_name": "gate_risk_delta_within_watch_bound",
        "gate_pass": gate_risk_ok,
        "gate_value": f"max_abs={max_abs_gate_risk_delta:.6f}",
        "required_value": f"<= {MAX_ABS_MEAN_GATE_RISK_DELTA}",
        "gate_reason": "Task2-8j default-candidate route should not introduce large gate-risk shifts in smoke comparison.",
    })

    changed_ratio = float(route_delta["gate_decision_changed"].fillna(False).astype(bool).mean())
    changed_ratio_ok = bool(changed_ratio <= MAX_GATE_DECISION_CHANGED_STEP_RATIO)
    rows.append({
        "gate_name": "gate_decision_change_ratio_within_watch_bound",
        "gate_pass": changed_ratio_ok,
        "gate_value": f"ratio={changed_ratio:.6f}",
        "required_value": f"<= {MAX_GATE_DECISION_CHANGED_STEP_RATIO}",
        "gate_reason": "Gate-decision changes are allowed, but not enough to indicate route instability at this stage.",
    })

    return pd.DataFrame(rows)


def build_task2_8j_30_readiness() -> dict[str, pd.DataFrame]:
    comparison = build_task2_8j_29_comparison()
    summary = comparison["task2_8j_29_summary"]
    per_step = comparison["task2_8j_29_per_step_metrics"]
    route_delta = comparison["task2_8j_29_route_delta"]
    gates = _gate_rows(summary, per_step, route_delta)
    all_gates_pass = bool(gates["gate_pass"].fillna(False).astype(bool).all())
    decision = "eligible_for_default_candidate_route_trial" if all_gates_pass else "not_ready_for_default_candidate_route_trial"
    decision_row = pd.DataFrame([{
        "task2_8j_30_version": TASK2_8J_30_VERSION,
        "decision_contract": TASK2_8J_30_DECISION_CONTRACT,
        "decision": decision,
        "all_gates_pass": all_gates_pass,
        "gate_count": int(len(gates)),
        "gate_pass_count": int(gates["gate_pass"].fillna(False).astype(bool).sum()),
        "gate_fail_count": int((~gates["gate_pass"].fillna(False).astype(bool)).sum()),
        "scenarios": "|".join(TASK2_8J_29_SCENARIOS),
        "steps_per_route_per_scenario": TASK2_8J_29_STEPS,
        "recommended_next_task": "Task2-8j-31: switch Task2-8j-primary to default candidate route with legacy fallback" if all_gates_pass else "Repeat comparison with stricter scenarios before default-candidate switch",
        "runtime_default_changed_by_task2_8j_30": False,
        "legacy_route_deleted_by_task2_8j_30": False,
        "canonical_write_enabled_by_task2_8j_30": False,
        "axis_execution_enabled_by_task2_8j_30": False,
        "superiority_claim_made": False,
    }])
    return {
        "task2_8j_30_decision": decision_row,
        "task2_8j_30_promotion_gates": gates,
        "task2_8j_29_summary": summary,
        "task2_8j_29_route_delta": route_delta,
    }


def write_task2_8j_30_readiness(out_dir: Path) -> dict[str, pd.DataFrame]:
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = build_task2_8j_30_readiness()
    for name, df in outputs.items():
        df.to_csv(out_dir / f"{name}.csv", index=False)
        df.to_json(out_dir / f"{name}.json", orient="records", indent=2, force_ascii=False)
    manifest = {
        "version": TASK2_8J_30_VERSION,
        "contract": TASK2_8J_30_DECISION_CONTRACT,
        "tables": sorted(outputs),
        "decision": str(outputs["task2_8j_30_decision"]["decision"].iloc[0]),
        "runtime_default_changed": False,
    }
    (out_dir / "task2_8j_30_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return outputs


if __name__ == "__main__":
    write_task2_8j_30_readiness(Path("results/task2_8j_30_primary_default_readiness"))
