#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT_FOR_IMPORTS = SCRIPT_DIR.parent
if str(REPO_ROOT_FOR_IMPORTS) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT_FOR_IMPORTS))

from dept2_fullspec_runner_rc1.runner.fullspec_integrated_closed_loop_runner import run_fullspec_task16

from scripts.observation_window_summary import build_observation_window_summary, flatten_observation_windows
from scripts.profile_loader import (
    REPO_ROOT,
    build_runner_config,
    collect_metrics,
    acceptance_pass,
    dataframe_to_csv,
    write_json,
)


def parse_overrides(raw: str | None) -> dict:
    if not raw:
        return {}
    return json.loads(raw)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run one Task22C full-loop validation with profiles.")
    parser.add_argument("--validation-profile", default="smoke")
    parser.add_argument("--world-profile", default="pseudo_reality_default")
    parser.add_argument("--action-profile", default="action_default")
    parser.add_argument("--label", default="single_run")
    parser.add_argument("--overrides-json", default=None, help="JSON object merged last into FullSpecRunnerConfig.")
    parser.add_argument("--output-dir", default=str(REPO_ROOT / "validation_runs" / "latest"))
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    cfg = build_runner_config(
        validation_profile=args.validation_profile,
        world_profile=args.world_profile,
        action_profile=args.action_profile,
        overrides=parse_overrides(args.overrides_json),
    )
    out = run_fullspec_task16(cfg)
    metrics = collect_metrics(args.label, cfg, out)
    metrics["overall_pass"] = acceptance_pass(metrics)

    write_json(output_dir / "summary.json", metrics)
    window_summary = build_observation_window_summary(args.label, cfg, out, metrics)
    write_json(output_dir / "observation_window_summary.json", window_summary)
    dataframe_to_csv(flatten_observation_windows(window_summary), output_dir / "observation_window_summary.csv")
    write_json(output_dir / "run_manifest.json", {
        "label": args.label,
        "validation_profile": args.validation_profile,
        "world_profile": args.world_profile,
        "action_profile": args.action_profile,
        "config": cfg.__dict__,
        "overall_pass": metrics["overall_pass"],
    })

    for name in [
        "boundary_violation_report",
        "canonical_write_audit",
        "rollback_snapshot",
        "commit_gate_audit",
        "parameter_shadow_audit",
        "parameter_window_binding_audit",
        "exploration_projection",
        "action_frame",
        "action_execution_audit",
    ]:
        df = out.get(name)
        if df is not None:
            dataframe_to_csv(df, output_dir / f"{name}.csv")

    (output_dir / "README.md").write_text(
        "# Latest validation run\n\n"
        f"label: `{args.label}`\n\n"
        f"overall_pass: `{metrics['overall_pass']}`\n\n"
        "See `summary.json`, `observation_window_summary.json`, `observation_window_summary.csv`, and CSV audit files.\n",
        encoding="utf-8",
    )

    print(json.dumps(metrics, ensure_ascii=False, indent=2))
    return 0 if metrics["overall_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
