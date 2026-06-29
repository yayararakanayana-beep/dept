import importlib.util
import json
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "validation" / "task20g_pre_commit_readiness_audit.py"
spec = importlib.util.spec_from_file_location("task20g_pre_commit_readiness_audit", MODULE_PATH)
task20g = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(task20g)


def test_missing_proposal_summary_does_not_enable_gate(tmp_path):
    summary = task20g.build_summary(tmp_path)

    assert summary["missing_input"] is True
    assert summary["no_write"] is True
    assert summary["commit_gate_implemented"] is False
    assert summary["parameter_update_implemented"] is False
    assert summary["gate_ready_overall"] is False
    assert summary["candidate_readiness"] == []
    assert all(value is False for value in summary["boundary_check"].values())


def test_compact_summary_keeps_all_candidates_not_gate_ready(tmp_path):
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
                        "evidence_source": "results/task17_stress_matrix/fullspec_task17_stress_validation_summary_RC1.csv",
                        "required_guard": "coactivation gate evidence; audit evidence; shadow confirmation; no ActionModule internal access",
                    },
                    {
                        "proposal_id": "T20F-P03-shock_recovery_window",
                        "source_watch_item": "shock_recovery_window",
                        "candidate_type": "audit_required",
                        "evidence_source": "results/task17_stress_matrix/fullspec_task17_stress_validation_summary_RC1.csv",
                        "required_guard": "shock onset, peak, and return-to-baseline evidence; no rollback gate implementation",
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    summary = task20g.build_summary(tmp_path)

    assert summary["missing_input"] is False
    assert summary["compact_summary_only"] is True
    assert summary["gate_ready_overall"] is False
    assert len(summary["candidate_readiness"]) == 2
    assert all(candidate["gate_ready"] is False for candidate in summary["candidate_readiness"])
    assert all(candidate["no_write_status"] is True for candidate in summary["candidate_readiness"])
    assert all(candidate["next_required_evidence"] for candidate in summary["candidate_readiness"])
    assert "shock onset" in " ".join(summary["candidate_readiness"][1]["next_required_evidence"])


def test_required_top_level_and_boundary_flags_remain_disabled(tmp_path):
    summary = task20g.build_summary(tmp_path)

    assert summary["no_write"] is True
    assert summary["commit_gate_implemented"] is False
    assert summary["parameter_update_implemented"] is False
    assert summary["gate_ready_overall"] is False
    assert all(value is False for value in summary["boundary_check"].values())
    assert summary["boundary_check"]["canonical_write_enabled"] is False
    assert summary["boundary_check"]["gk_writeback_enabled"] is False
    assert summary["boundary_check"]["world_write_by_shadow_enabled"] is False


def test_writes_readiness_json_and_markdown(tmp_path):
    summary = task20g.build_summary(tmp_path)
    json_path, md_path = task20g.write_summary(summary, tmp_path / "results" / "task20g_pre_commit_readiness")

    assert json_path.exists()
    assert md_path.exists()
    loaded = json.loads(json_path.read_text(encoding="utf-8"))
    assert loaded["no_write"] is True
    assert loaded["gate_ready_overall"] is False
    assert loaded["boundary_check"]["commit_gate_implemented"] is False
    assert "Task20G Pre-Commit Readiness Audit" in md_path.read_text(encoding="utf-8")
