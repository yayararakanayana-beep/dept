import importlib.util
import json
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "validation" / "task20i_no_write_guard_readiness.py"
spec = importlib.util.spec_from_file_location("task20i_no_write_guard_readiness", MODULE_PATH)
task20i = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(task20i)


def test_missing_proposal_summary_does_not_fail(tmp_path):
    summary = task20i.build_summary(tmp_path)

    assert summary["missing_input"] is True
    assert summary["no_write"] is True
    assert summary["candidate_readiness"] == []
    assert all(value is False for value in summary["boundary_check"].values())


def test_proposal_candidates_generate_readiness_records(tmp_path):
    source_dir = tmp_path / "results" / "task20f_no_write_dry_run"
    source_dir.mkdir(parents=True)
    (source_dir / "proposal_summary.json").write_text(
        json.dumps(
            {
                "proposal_candidates": [
                    {
                        "proposal_id": "T20F-P01-coactivation_dampen_zone",
                        "source_watch_item": "coactivation_dampen_zone",
                        "candidate_type": "dampen_candidate",
                    },
                    {
                        "proposal_id": "T20F-P04-noise_ledger_exploration_gate_relationship",
                        "source_watch_item": "noise_ledger_exploration_gate_relationship",
                        "candidate_type": "audit_required",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    summary = task20i.build_summary(tmp_path)

    assert summary["missing_input"] is False
    assert summary["no_write"] is True
    assert len(summary["candidate_readiness"]) == 2
    assert all(item["readiness"] == "needs_more_evidence" for item in summary["candidate_readiness"])
    assert all(item["gate_ready"] is False for item in summary["candidate_readiness"])
    assert all(item["no_write_status"] is True for item in summary["candidate_readiness"])
    assert all(item["claim_scope"] == "guard readiness dry-run only" for item in summary["candidate_readiness"])


def test_boundary_flags_remain_disabled(tmp_path):
    summary = task20i.build_summary(tmp_path)
    boundary = summary["boundary_check"]

    assert all(value is False for value in boundary.values())
    assert boundary["commit_gate_implemented"] is False
    assert boundary["parameter_update_implemented"] is False
    assert boundary["guard_readiness_is_controller"] is False


def test_writes_output_json_and_markdown(tmp_path):
    summary = task20i.build_summary(tmp_path)
    json_path, md_path = task20i.write_summary(summary, tmp_path / "results" / "task20i_no_write_guard_readiness")

    assert json_path.exists()
    assert md_path.exists()
    loaded = json.loads(json_path.read_text(encoding="utf-8"))
    assert loaded["no_write"] is True
    assert loaded["boundary_check"]["guard_readiness_is_controller"] is False
    assert "Task20i No-Write Guard Readiness Summary" in md_path.read_text(encoding="utf-8")
