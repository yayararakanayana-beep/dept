"""Validation report and manifest output for Task 3.1e."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any
import pandas as pd
from .validation_common import Recorder, build_manifest

def _write_outputs(artifact_dir: Path, profile: str, counts: dict[str, Any], recorder: Recorder, coverage: pd.DataFrame | None) -> None:
    (artifact_dir / "quality_checks.json").write_text(json.dumps(recorder.checks, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = ["# Task 3.1e Validation Results", "", f"- Profile: `{profile}`", f"- Result: `{'PASS' if not recorder.failed else 'FAIL'}`", f"- Checks passed: `{len(recorder.checks) - len(recorder.failed)}` / `{len(recorder.checks)}`", f"- Snapshot rows: `{counts['snapshot_total']}`", f"- Adaptive pool / selected: `{counts['adaptive_pool']}` / `{counts['adaptive_selected']}`", ""]
    if coverage is not None:
        lines.extend(["## Coverage", "", coverage.to_markdown(index=False), ""])
    if recorder.failed:
        lines.extend(["## Failed checks", ""] + [f"- `{name}`" for name in recorder.failed] + [""])
    lines.extend(["## Scope limitations", "", "- This artifact validates the static Task 3.1e corpus only.", "- It does not select semantic axes or define dynamic G_t update timing.", "- It does not connect K_t, O_t, H-DEPT, or the Action Module.", ""])
    (artifact_dir / "results.md").write_text("\n".join(lines), encoding="utf-8")
    (artifact_dir / "artifact_manifest.json").write_text(json.dumps(build_manifest(artifact_dir), indent=2, sort_keys=True) + "\n", encoding="utf-8")
