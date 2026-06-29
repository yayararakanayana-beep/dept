import importlib.util
import json
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "validation" / "task20b_watch_audit.py"
spec = importlib.util.spec_from_file_location("task20b_watch_audit", MODULE_PATH)
task20b_watch_audit = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(task20b_watch_audit)


def test_missing_input_does_not_fail(tmp_path):
    summary = task20b_watch_audit.build_summary(tmp_path)

    assert summary["missing_input"] is True
    assert set(summary["watch_items"]) == {
        "coactivation_dampen_zone",
        "residual_noise_high",
        "shock_recovery_window",
        "noise_ledger_exploration_gate_relationship",
    }


def test_watch_items_are_summarized_from_dummy_results(tmp_path):
    results_dir = tmp_path / "results" / "task17_stress_matrix"
    results_dir.mkdir(parents=True)
    (results_dir / "summary.json").write_text(
        json.dumps(
            {
                "records": [
                    {
                        "case_id": "S04",
                        "cycle": 3,
                        "watch": "coactivation_dampen_zone",
                        "decision": "coactivation gate dampen",
                    },
                    {
                        "case_id": "S05",
                        "cycle": 4,
                        "watch": "residual_noise_high during shock recovery window",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    ablation_dir = tmp_path / "results" / "task18_ablation_validation"
    ablation_dir.mkdir(parents=True)
    (ablation_dir / "summary.md").write_text(
        "no residual noise ledger signal changed exploration projection and coactivation gate modulation\n",
        encoding="utf-8",
    )

    summary = task20b_watch_audit.build_summary(tmp_path)

    assert summary["missing_input"] is False
    assert summary["watch_items"]["coactivation_dampen_zone"]["observed"] is True
    assert "S04" in summary["watch_items"]["coactivation_dampen_zone"]["cases"]
    assert summary["watch_items"]["residual_noise_high"]["observed"] is True
    assert summary["watch_items"]["shock_recovery_window"]["observed"] is True
    assert summary["watch_items"]["noise_ledger_exploration_gate_relationship"]["observed"] is True


def test_compact_task17_task18_csv_summaries_are_evidence(tmp_path):
    task17_dir = tmp_path / "results" / "task17_stress_matrix"
    task17_dir.mkdir(parents=True)
    (task17_dir / "fullspec_task17_stress_validation_summary_RC1.csv").write_text(
        "task,pass_with_watch_count,max_observed_noise_score,max_observed_coactivation_risk\n"
        "Task17_StressScenarioValidation_RC1,7,0.77,0.56\n",
        encoding="utf-8",
    )
    task18_dir = tmp_path / "results" / "task18_ablation_validation"
    task18_dir.mkdir(parents=True)
    (task18_dir / "fullspec_task18_ablation_summary_RC1.csv").write_text(
        "task,pass_with_ablation_effect_count,ablation_effect_cases\n"
        "Task18_AblationValidation_RC1,5,5\n",
        encoding="utf-8",
    )

    summary = task20b_watch_audit.build_summary(tmp_path)

    assert summary["missing_input"] is False
    assert summary["source_inputs"]["task17_stress"] == [
        "results/task17_stress_matrix/fullspec_task17_stress_validation_summary_RC1.csv"
    ]
    assert summary["source_inputs"]["task18_ablation"] == [
        "results/task18_ablation_validation/fullspec_task18_ablation_summary_RC1.csv"
    ]
    assert summary["watch_items"]["coactivation_dampen_zone"]["observed_in"] == [
        "results/task17_stress_matrix/fullspec_task17_stress_validation_summary_RC1.csv"
    ]
    assert summary["watch_items"]["noise_ledger_exploration_gate_relationship"]["observed_in"] == [
        "results/task18_ablation_validation/fullspec_task18_ablation_summary_RC1.csv"
    ]


def test_boundary_flags_remain_disabled(tmp_path):
    summary = task20b_watch_audit.build_summary(tmp_path)
    boundary = summary["boundary_check"]

    assert boundary["canonical_write_enabled"] is False
    assert boundary["gk_writeback_enabled"] is False
    assert boundary["world_write_by_shadow_enabled"] is False
    assert boundary["parameter_update_implemented"] is False
    assert boundary["commit_gate_implemented"] is False
    assert boundary["watch_audit_is_controller"] is False


def test_writes_small_summary_files(tmp_path):
    summary = task20b_watch_audit.build_summary(tmp_path)
    json_path, md_path = task20b_watch_audit.write_summary(summary, tmp_path / "results" / "task20b_watch_audit")

    assert json_path.exists()
    assert md_path.exists()
    assert json.loads(json_path.read_text(encoding="utf-8"))["missing_input"] is True
    assert "Task20b Watch Audit Summary" in md_path.read_text(encoding="utf-8")
