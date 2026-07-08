from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "validation" / "task2_8j_30_primary_default_readiness.py"
SPEC = importlib.util.spec_from_file_location("task2_8j_30_validation", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
TASK2_8J_30 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = TASK2_8J_30
SPEC.loader.exec_module(TASK2_8J_30)


def test_task2_8j_30_primary_default_readiness_decision_and_artifacts(tmp_path: Path):
    outputs = TASK2_8J_30.write_task2_8j_30_readiness(tmp_path)

    decision = outputs["task2_8j_30_decision"]
    gates = outputs["task2_8j_30_promotion_gates"]
    summary = outputs["task2_8j_29_summary"]
    route_delta = outputs["task2_8j_29_route_delta"]

    assert decision is not None and not decision.empty
    assert gates is not None and not gates.empty
    assert summary is not None and not summary.empty
    assert route_delta is not None and not route_delta.empty

    assert set(decision["decision"].astype(str)) == {"eligible_for_default_candidate_route_trial"}
    assert set(decision["all_gates_pass"].astype(bool)) == {True}
    assert set(decision["runtime_default_changed_by_task2_8j_30"].astype(bool)) == {False}
    assert set(decision["legacy_route_deleted_by_task2_8j_30"].astype(bool)) == {False}
    assert set(decision["canonical_write_enabled_by_task2_8j_30"].astype(bool)) == {False}
    assert set(decision["axis_execution_enabled_by_task2_8j_30"].astype(bool)) == {False}
    assert set(decision["superiority_claim_made"].astype(bool)) == {False}

    assert set(gates["gate_name"].astype(str)) == set(TASK2_8J_30.PROMOTION_GATES)
    assert set(gates["gate_pass"].astype(bool)) == {True}
    assert int(decision["gate_count"].iloc[0]) == len(TASK2_8J_30.PROMOTION_GATES)
    assert int(decision["gate_fail_count"].iloc[0]) == 0
    assert int(decision["gate_pass_count"].iloc[0]) == len(TASK2_8J_30.PROMOTION_GATES)

    assert set(summary["comparison_status"].astype(str)) == {"pass"}
    assert bool((summary["task2_8j_total_primary_candidate_rows"].astype(int) > 0).all())
    assert bool((summary["task2_8j_total_primary_need_rows"].astype(int) > 0).all())

    assert bool(route_delta["both_actionframe_only"].astype(bool).all())
    assert bool(route_delta["legacy_transition_time_ok"].astype(bool).all())
    assert bool(route_delta["task2_8j_transition_time_ok"].astype(bool).all())
    assert float(route_delta["gate_risk_delta_task2_minus_legacy"].astype(float).abs().max()) <= TASK2_8J_30.MAX_ABS_MEAN_GATE_RISK_DELTA

    expected_files = [
        "task2_8j_30_decision.csv",
        "task2_8j_30_promotion_gates.csv",
        "task2_8j_29_summary.csv",
        "task2_8j_29_route_delta.csv",
        "task2_8j_30_manifest.json",
    ]
    for filename in expected_files:
        assert (tmp_path / filename).exists(), filename
