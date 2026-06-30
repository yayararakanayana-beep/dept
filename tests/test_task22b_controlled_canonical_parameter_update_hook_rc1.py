from pathlib import Path
import importlib.util
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "validation" / "task22b_controlled_canonical_parameter_update_hook_rc1.py"
spec = importlib.util.spec_from_file_location("task22b", MODULE_PATH)
task22b = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = task22b
spec.loader.exec_module(task22b)


def _run_and_load():
    summary, validation = task22b.build_summary()
    task22b.write_outputs(summary, validation)
    out = ROOT / "results/task22b_controlled_canonical_parameter_update_hook_rc1"
    return summary, validation, out


def test_summary_and_validation_json_exist():
    summary, validation, out = _run_and_load()
    assert (out / "update_hook_summary.json").is_file()
    assert (out / "update_hook_validation.json").is_file()
    assert (out / "update_hook_summary.md").is_file()
    assert (out / "update_hook_validation.md").is_file()
    assert json.loads((out / "update_hook_summary.json").read_text())["task"] == summary["task"]
    assert json.loads((out / "update_hook_validation.json").read_text())["passed"] == validation["passed"]


def test_required_four_cases_exist():
    summary, _, _ = _run_and_load()
    assert {c["case_id"] for c in summary["cases"]} == set(task22b.CASE_IDS)


def test_passed_true_requires_all_case_runner_execution_and_counts():
    summary, _, _ = _run_and_load()
    cases = {c["case_id"]: c for c in summary["cases"]}
    if summary["passed"]:
        assert all(c["runner_executed"] for c in cases.values())
        assert cases["controlled_update_on"]["canonical_write_count"] == 1
        assert cases["update_off"]["canonical_write_count"] == 0
        assert cases["real_watch_only_candidates"]["canonical_write_count"] == 0
        assert cases["forced_bad_update_rollback"]["rollback_count"] >= 1
        assert cases["forced_bad_update_rollback"]["rollback_restored_original"] is True


def test_passed_true_rejects_synthetic_fixed_mock_performance_sources():
    summary, _, _ = _run_and_load()
    if summary["passed"]:
        src = summary["performance_delta"]["performance_delta_source"]
        assert src == "real_runner_output"
        assert not any(token in src for token in ["synthetic", "fixed", "mock", "stub"])


def test_passed_true_rejects_fixed_or_assumed_boundary_audit():
    summary, _, _ = _run_and_load()
    audit_source = summary["boundary_audit"].get("audit_source")
    if summary["passed"]:
        assert audit_source not in {"fixed_zero_without_check", "assumed_zero"}
        assert summary["boundary_audit_available"] is True


def test_repository_boundary_flags_remain_closed():
    summary, _, _ = _run_and_load()
    assert summary["synthetic_metrics_used"] is False
    assert summary["parallel_runner_created"] is False
    assert summary["frozen_runner_modified"] is False
    audit = summary["boundary_audit"]
    if summary["passed"]:
        assert audit["gk_writeback_count"] == 0
        assert audit["world_direct_write_count"] == 0
        assert audit["action_module_internal_connection_count"] == 0
        assert audit["actionframe_direct_generation_count"] == 0


def test_bounded_update_hook_connected_only_when_safe_hook_found():
    summary, _, _ = _run_and_load()
    if summary["bounded_update_hook_connected"]:
        assert summary["safe_update_hook_found"] is True


def test_runner_unexecuted_metric_or_boundary_unavailable_force_failure():
    summary, _, _ = _run_and_load()
    if not summary["existing_runner_executed"]:
        assert summary["passed"] is False
    if summary["performance_delta"].get("performance_delta_source") == "unavailable_real_output_insufficient":
        assert summary["passed"] is False
    if summary.get("boundary_audit_available") is False:
        assert summary["passed"] is False


def test_runner_output_inventory_and_metric_classification_are_recorded():
    summary, _, _ = _run_and_load()
    assert "runner_output_inventory" in summary
    assert isinstance(summary["runner_output_inventory"], dict)
    assert "metric_candidates" in summary["performance_delta"] or summary["passed"] is False
    if summary["passed"]:
        perf = summary["performance_delta"]
        assert perf["metric_classification"] == "valid_performance_metric"
        assert perf["metric_source_table_or_key"]
        assert perf["target_metric_name"]
        metric_key = f"{perf['metric_source_table_or_key']}.{perf['target_metric_name']}".lower()
        assert "shadow_cycle_index" not in metric_key
        assert "theta" not in metric_key
        assert "parameter" not in metric_key
        assert "index" not in metric_key


def test_parameter_box_identity_is_recorded_and_confirmed_only_on_pass():
    summary, _, _ = _run_and_load()
    identity = summary["parameter_box_identity"]
    assert "located_via" in identity
    assert "is_runner_owned_lower_parameter_box" in identity
    assert "is_shadow_candidate_only" in identity
    assert "canonical_update_semantics" in identity
    if summary["passed"]:
        assert identity["located_via"] == "runner.parameter_shadow_box.box.state"
        assert identity["is_runner_owned_lower_parameter_box"] is True
        assert identity["is_shadow_candidate_only"] is False
        assert identity["canonical_update_semantics"] == "confirmed"



def test_boundary_counts_do_not_truncate_fractional_violations():
    summary, _, _ = _run_and_load()
    audit = summary["boundary_audit"]
    if summary["existing_runner_executed"]:
        assert audit["boundary_count_aggregation"] == "sum_and_max_no_int_truncation"
        assert isinstance(audit["boundary_violation_count"], float)
        if audit["controlled_boundary_regression_detected"]:
            assert summary["passed"] is False


def test_parameter_hook_and_runner_after_are_recorded():
    summary, _, _ = _run_and_load()
    cases = {c["case_id"]: c for c in summary["cases"]}
    controlled = cases["controlled_update_on"]
    assert "parameter_hook_after" in controlled
    assert "parameter_runner_after" in controlled
    assert "runner_recomputed_or_overwrote_parameter" in controlled
    if summary["existing_runner_executed"]:
        audit = summary["real_runner_effect_audit"]
        assert "controlled_parameter_hook_after" in audit
        assert "controlled_parameter_runner_after" in audit
        assert "controlled_runner_recomputed_or_overwrote_parameter" in audit


def test_no_immediate_improvement_is_allowed_but_boundary_regression_forces_failure():
    summary, _, _ = _run_and_load()
    effect = summary["real_runner_effect_audit"]
    assert effect.get("immediate_improvement_required") is False
    if effect.get("controlled_boundary_regression_detected") is True:
        assert summary["passed"] is False


def test_controlled_commit_fixture_preflight_is_recorded():
    summary, _, _ = _run_and_load()
    assert "controlled_commit_fixture_preflight" in summary
    assert isinstance(summary["controlled_commit_fixture_preflight"], list)
    if summary["existing_runner_executed"]:
        assert summary["controlled_commit_fixture_preflight"]
        selected = [c for c in summary["controlled_commit_fixture_preflight"] if c.get("selected")]
        if summary["passed"]:
            assert selected
            assert selected[0]["boundary_violation_count"] == 0.0
