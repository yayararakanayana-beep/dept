import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from validation.task20i_readiness_rerun_with_evidence import build_rerun_summary, write_rerun_summary


def test_readiness_rerun_is_conservative_and_writes_outputs(tmp_path: Path):
    readiness = tmp_path / "results/task20g_pre_commit_readiness/readiness_summary.json"
    evidence = tmp_path / "results/task20h_minimal_evidence/evidence_index.json"
    readiness.parent.mkdir(parents=True)
    evidence.parent.mkdir(parents=True)
    readiness.write_text(json.dumps({
        "candidate_readiness": [{
            "proposal_id": "P1", "source_watch_item": "coactivation_dampen_zone",
            "gate_ready": False, "next_required_evidence": ["source rows", "boundary evidence"],
        }]
    }))
    evidence.write_text(json.dumps({
        "evidence_items": [{"evidence_id": "E1", "category": "coactivation_dampen_zone"}]
    }))
    summary = build_rerun_summary(tmp_path)
    output = tmp_path / "results/task20i_readiness_rerun"
    write_rerun_summary(summary, output)

    assert summary["no_write"] is True
    assert all(value is False for value in summary["boundary_check"].values())
    assert summary["boundary_check"]["commit_gate_implemented"] is False
    assert summary["boundary_check"]["parameter_update_implemented"] is False
    assert summary["gate_ready_overall"] is False
    assert summary["candidate_readiness"][0]["new_gate_ready"] is False
    assert summary["candidate_readiness"][0]["readiness"] == "needs_more_evidence"
    assert (output / "readiness_rerun_summary.json").exists()
    assert (output / "readiness_rerun_summary.md").exists()


def test_readiness_rerun_reports_missing_inputs(tmp_path: Path):
    summary = build_rerun_summary(tmp_path)
    assert summary["missing_input"] is True
    assert summary["no_write"] is True
    assert summary["gate_ready_overall"] is False
