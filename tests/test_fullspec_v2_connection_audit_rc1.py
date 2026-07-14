from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from validation.fullspec_v2_connection_audit_rc1 import run_validation  # noqa: E402


def test_fullspec_v2_connection_audit_rc1() -> None:
    summary = run_validation(REPO_ROOT / "results" / "fullspec_v2_connection_audit_rc1")
    assert summary["overall_pass"], summary["failed_critical_checks"]
