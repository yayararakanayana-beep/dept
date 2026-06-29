import json, zipfile
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from validation.task20h_minimal_evidence_extraction import build_evidence_index, write_evidence_index


def test_missing_zip_reports_missing_input(tmp_path: Path):
    summary = build_evidence_index(tmp_path, tmp_path / "missing.zip", tmp_path / "out")
    assert summary["missing_input"] is True
    assert summary["extracted_count"] == 0
    assert summary["missing_categories"]


def test_extracts_only_allowed_small_evidence_and_caps_count(tmp_path: Path):
    archive = tmp_path / "fixture.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("results/coactivation_gate.csv", "coactivation gate rows,dampen zone,shadow confirmation\n")
        zf.writestr("results/noise_ledger.json", '{"residual noise ledger":"sustained vs transient carryover"}')
        zf.writestr("docs/shock_recovery.md", "shock onset shock peak recovery return-to-baseline recovery stability window")
        zf.writestr("docs/ablation.txt", "ablation matrix delta vs baseline noise ledger exploration projection sidecar boundary confirmation")
        zf.writestr("runtime/should_not_extract.py", "# coactivation dampen runtime code")
        zf.writestr("bin/blob.bin", b"coactivation\x00dampen")
        for i in range(20):
            zf.writestr(f"extra/residual_{i}.csv", "residual noise ledger carryover")
    output_dir = tmp_path / "out"
    summary = build_evidence_index(tmp_path, archive, output_dir, max_files=3)
    write_evidence_index(summary, output_dir)

    assert summary["extracted_count"] <= 3
    assert len(summary["evidence_items"]) == summary["extracted_count"]
    extracted = list((output_dir / "extracted").glob("*"))
    assert len(extracted) == summary["extracted_count"]
    assert all(p.suffix in {".csv", ".json", ".md", ".txt"} for p in extracted)
    assert not any(p.suffix == ".py" for p in extracted)
    assert (output_dir / "evidence_index.json").exists()
    assert (output_dir / "evidence_index.md").exists()
    loaded = json.loads((output_dir / "evidence_index.json").read_text())
    assert loaded["boundary_check"]["commit_gate_implemented"] is False
