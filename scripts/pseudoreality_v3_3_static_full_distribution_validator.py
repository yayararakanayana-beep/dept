#!/usr/bin/env python3
"""Independent persisted-artifact validator for Task 3.1e."""
from __future__ import annotations
import argparse
import json
from task3_1e_static_full_distribution import DEFAULT_CONFIG
from task3_1e_static_full_distribution.validation_checks import validate_artifacts
from task3_1e_static_full_distribution.validation_common import build_manifest, expected_counts
__all__ = ["validate_artifacts", "build_manifest", "expected_counts"]
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=("smoke", "formal"), required=True)
    parser.add_argument("--artifact-root", default="artifacts")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    checks = validate_artifacts(args.artifact_root, args.profile, args.config, write_outputs=True)
    failed = [name for name, payload in checks.items() if not payload["passed"]]
    if failed:
        print(json.dumps({"failed_checks": failed}, indent=2))
        if args.strict:
            raise SystemExit(1)
    else:
        print(json.dumps({"result": "PASS", "check_count": len(checks)}, indent=2))
if __name__ == "__main__":
    main()
