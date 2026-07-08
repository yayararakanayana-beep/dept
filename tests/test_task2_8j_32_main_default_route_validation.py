from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "validation" / "task2_8j_32_main_default_route_validation.py"
SPEC = importlib.util.spec_from_file_location("task2_8j_32_validation", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
TASK2_8J_32 = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = TASK2_8J_32
SPEC.loader.exec_module(TASK2_8J_32)


def test_task2_8j_32_main_default_route_smoke_and_multistep(tmp_path: Path):
    outputs = TASK2_8J_32.write_task2_8j_32_validation(tmp_path)

    decision = outputs["task2_8j_32_decision"]
    summary = outputs["task2_8j_32_run_summary"]

    assert decision is not None and not decision.empty
    assert summary is not None and not summary.empty

    assert set(decision["decision"].astype(str)) == {"main_default_route_validated"}
    assert set(decision["all_runs_pass"].astype(bool)) == {True}
    assert set(decision["runtime_default_changed_by_task2_8j_32"].astype(bool)) == {False}
    assert set(decision["legacy_route_deleted_by_task2_8j_32"].astype(bool)) == {False}
    assert set(decision["canonical_write_enabled_by_task2_8j_32"].astype(bool)) == {False}
    assert set(decision["axis_execution_enabled_by_task2_8j_32"].astype(bool)) == {False}
    assert set(decision["superiority_claim_made"].astype(bool)) == {False}

    assert set(summary["validation_status"].astype(str)) == {"pass"}
    assert set(summary["gt_main_map_name"].astype(str)) == {"static_pca_7"}
    assert set(summary["static_pca7_view_attached"].astype(bool)) == {True}
    assert set(summary["legacy_gt_columns_preserved"].astype(bool)) == {True}
    assert set(summary["bridge_all_pass"].astype(bool)) == {True}
    assert set(summary["action_planning_route"].astype(str)) == {"task2_8j_primary"}
    assert set(summary["planning_all_pass"].astype(bool)) == {True}
    assert set(summary["task2_8j_primary_route_used_all_steps"].astype(bool)) == {True}
    assert set(summary["task2_8j_material_promoted_all_steps"].astype(bool)) == {True}
    assert bool((summary["task2_8j_primary_candidate_rows"].astype(int) > 0).all())
    assert bool((summary["task2_8j_primary_need_rows"].astype(int) > 0).all())
    assert set(summary["gate_all_pass"].astype(bool)) == {True}
    assert set(summary["execution_all_pass"].astype(bool)) == {True}
    assert set(summary["actionmodule_actionframe_only_all_steps"].astype(bool)) == {True}
    assert set(summary["direct_gk_input_count"].astype(int)) == {0}
    assert set(summary["direct_ot_input_count"].astype(int)) == {0}
    assert set(summary["direct_parameter_box_input_count"].astype(int)) == {0}
    assert set(summary["canonical_write_count"].astype(int)) == {0}
    assert set(summary["transition_time_ok"].astype(bool)) == {True}

    expected_files = [
        "task2_8j_32_decision.csv",
        "task2_8j_32_run_summary.csv",
        "task2_8j_32_manifest.json",
    ]
    for filename in expected_files:
        assert (tmp_path / filename).exists(), filename
