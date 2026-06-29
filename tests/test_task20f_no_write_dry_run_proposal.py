import importlib.util
import json
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "validation" / "task20f_no_write_dry_run_proposal.py"
spec = importlib.util.spec_from_file_location("task20f_no_write_dry_run_proposal", MODULE_PATH)
task20f = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(task20f)


def test_missing_watch_summary_does_not_fail(tmp_path):
    summary = task20f.build_summary(tmp_path)

    assert summary["missing_input"] is True
    assert summary["no_write"] is True
    assert summary["proposal_candidates"] == []
    assert all(value is False for value in summary["boundary_check"].values())


def test_observed_watch_items_generate_proposal_candidates(tmp_path):
    source_dir = tmp_path / "results" / "task20b_watch_audit"
    source_dir.mkdir(parents=True)
    (source_dir / "watch_audit_summary.json").write_text(
        json.dumps(
            {
                "watch_items": {
                    "coactivation_dampen_zone": {
                        "observed": True,
                        "observed_in": ["results/task17_stress_matrix/fullspec_task17_stress_validation_summary_RC1.csv"],
                    },
                    "residual_noise_high": {
                        "observed": False,
                        "observed_in": ["results/task17_stress_matrix/fullspec_task17_stress_validation_summary_RC1.csv"],
                    },
                    "noise_ledger_exploration_gate_relationship": {
                        "observed": True,
                        "observed_in": ["results/task18_ablation_validation/fullspec_task18_ablation_summary_RC1.csv"],
                    },
                }
            }
        ),
        encoding="utf-8",
    )

    summary = task20f.build_summary(tmp_path)

    assert summary["missing_input"] is False
    assert summary["no_write"] is True
    assert len(summary["proposal_candidates"]) == 2
    assert {candidate["source_watch_item"] for candidate in summary["proposal_candidates"]} == {
        "coactivation_dampen_zone",
        "noise_ledger_exploration_gate_relationship",
    }
    assert all(candidate["no_write_status"] is True for candidate in summary["proposal_candidates"])
    assert all(candidate["claim_scope"] == "diagnostic proposal only" for candidate in summary["proposal_candidates"])


def test_boundary_flags_remain_disabled(tmp_path):
    summary = task20f.build_summary(tmp_path)
    boundary = summary["boundary_check"]

    assert all(value is False for value in boundary.values())
    assert boundary["commit_gate_implemented"] is False
    assert boundary["parameter_update_implemented"] is False
    assert boundary["proposal_summary_is_controller"] is False


def test_writes_output_json_and_markdown(tmp_path):
    summary = task20f.build_summary(tmp_path)
    json_path, md_path = task20f.write_summary(summary, tmp_path / "results" / "task20f_no_write_dry_run")

    assert json_path.exists()
    assert md_path.exists()
    loaded = json.loads(json_path.read_text(encoding="utf-8"))
    assert loaded["no_write"] is True
    assert loaded["boundary_check"]["proposal_summary_is_controller"] is False
    assert "Task20f No-Write Dry-Run Proposal Summary" in md_path.read_text(encoding="utf-8")
