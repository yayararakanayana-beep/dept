#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Q9-style full integration validation.")
    parser.add_argument("--output-dir", default=str(REPO_ROOT / "validation_runs" / "latest"))
    args = parser.parse_args()

    tmp_matrix = REPO_ROOT / "configs" / "matrices" / "_q9_localprep_matrix.json"
    matrix = {
        "name": "q9_localprep",
        "description": "Q9-style local validation matrix for GitHub-ready package.",
        "runs": [
            {"label": "dryrun_normal_shadow", "world_profile": "pseudo_reality_default", "action_profile": "action_default", "validation_profile": "q9_dryrun", "overrides": {"seed": 1}},
            {"label": "dryrun_shock_shadow", "world_profile": "pseudo_reality_shock", "action_profile": "action_default", "validation_profile": "q9_dryrun", "overrides": {"seed": 2}},
            {"label": "enabled_canonbind_normal", "world_profile": "pseudo_reality_default", "action_profile": "action_default", "validation_profile": "q9_default", "overrides": {"seed": 1}},
            {"label": "enabled_canonbind_relation_lock", "world_profile": "pseudo_reality_relation_lock", "action_profile": "action_default", "validation_profile": "q9_default", "overrides": {"seed": 3}},
            {"label": "enabled_canonbind_exploration_loss", "world_profile": "pseudo_reality_exploration_loss", "action_profile": "action_default", "validation_profile": "q9_default", "overrides": {"seed": 4}},
            {"label": "enabled_canonbind_shock", "world_profile": "pseudo_reality_shock", "action_profile": "action_default", "validation_profile": "q9_default", "overrides": {"seed": 5, "steps": 10}},
        ],
    }
    tmp_matrix.write_text(json.dumps(matrix, ensure_ascii=False, indent=2), encoding="utf-8")
    cmd = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "run_matrix_validation.py"),
        "--matrix", str(tmp_matrix),
        "--output-dir", args.output_dir,
    ]
    return subprocess.call(cmd, cwd=str(REPO_ROOT))


if __name__ == "__main__":
    raise SystemExit(main())
