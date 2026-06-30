#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

cmd = [
    sys.executable,
    str(REPO_ROOT / "scripts" / "run_full_loop_validation.py"),
    "--validation-profile", "smoke",
    "--world-profile", "pseudo_reality_default",
    "--action-profile", "action_default",
    "--label", "smoke",
    "--output-dir", str(REPO_ROOT / "validation_runs" / "latest"),
]
raise SystemExit(subprocess.call(cmd, cwd=str(REPO_ROOT)))
