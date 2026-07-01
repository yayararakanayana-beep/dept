#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT_FOR_IMPORTS = SCRIPT_DIR.parent
if str(REPO_ROOT_FOR_IMPORTS) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT_FOR_IMPORTS))

from dept2_fullspec_runner_rc1.runner.fullspec_integrated_closed_loop_runner import run_fullspec_task16

from scripts.profile_loader import (
    REPO_ROOT,
    build_runner_config,
    collect_metrics,
    acceptance_pass,
    dataframe_to_csv,
    load_json,
    write_json,
)


PER_RUN_EXPORTS = [
    # boundary / write / rollback audits
    "boundary_violation_report",
    "canonical_write_audit",
    "rollback_snapshot",
    "commit_gate_audit",
    "parameter_shadow_audit",
    "parameter_window_binding_audit",
    # exploration diagnostic chain
    "exploration_candidates",
    "exploration_sandbox",
    "exploration_decision",
    "exploration_local_audit",
    "local_audit",
    "exploration_sidecar",
    "exploration_projection",
    # planning / gate / action-side audits
    "action_surface_planning_audit",
    "coactivation_gate",
    "action_frame",
    "action_execution_audit",
    "world_transition_audit",
    "entity_trace",
    "relation_trace",
    "v2_hidden_trace",
    "v2_game_trace",
    "v2_resource_trace",
    "v2_information_trace",
    "v2_action_effect_trace",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Task22C profile matrix validation.")
    parser.add_argument("--matrix", default=str(REPO_ROOT / "configs" / "matrices" / "matrix_basic.json"))
    parser.add_argument("--output-dir", default=str(REPO_ROOT / "validation_runs" / "latest"))
    args = parser.parse_args()

    matrix_path = Path(args.matrix)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    matrix = load_json(matrix_path)
    rows = []
    per_run_dir = output_dir / "runs"
    per_run_dir.mkdir(parents=True, exist_ok=True)

    for run in matrix["runs"]:
        label = run["label"]
        cfg = build_runner_config(
            validation_profile=run["validation_profile"],
            world_profile=run["world_profile"],
            action_profile=run["action_profile"],
            overrides=run.get("overrides", {}),
        )
        out = run_fullspec_task16(cfg)
        metrics = collect_metrics(label, cfg, out)
        metrics["overall_pass"] = acceptance_pass(metrics)
        rows.append(metrics)

        rd = per_run_dir / label
        rd.mkdir(parents=True, exist_ok=True)
        write_json(rd / "summary.json", metrics)
        for name in PER_RUN_EXPORTS:
            df = out.get(name)
            if df is not None:
                dataframe_to_csv(df, rd / f"{name}.csv")

    fieldnames = list(rows[0].keys())
    with (output_dir / "matrix_metrics.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    overall = {
        "matrix_name": matrix.get("name", matrix_path.stem),
        "runs": len(rows),
        "overall_pass": all(bool(r["overall_pass"]) for r in rows),
        "boundary_violation_total": sum(int(r["boundary_violation_rows"]) for r in rows),
        "dry_run_write_violation_count": sum(1 for r in rows if bool(r["dry_run_write_violation"])),
        "forbidden_write_count": sum(1 for r in rows if bool(r["forbidden_write_detected"])),
        "projection_min": min(int(r["projection_rows"]) for r in rows),
        "action_frame_min": min(int(r["action_frame_rows"]) for r in rows),
        "action_source_audit_columns_present": all(bool(r.get("action_source_audit_columns_present", False)) for r in rows),
        "labels": [r["label"] for r in rows],
    }
    write_json(output_dir / "matrix_summary.json", overall)
    write_json(output_dir / "run_manifest.json", {"matrix": matrix, "overall": overall})

    (output_dir / "README.md").write_text(
        "# Latest matrix validation\n\n"
        f"matrix: `{overall['matrix_name']}`\n\n"
        f"overall_pass: `{overall['overall_pass']}`\n\n"
        "See `matrix_summary.json`, `matrix_metrics.csv`, and per-run CSV files.\n",
        encoding="utf-8",
    )

    print(json.dumps(overall, ensure_ascii=False, indent=2))
    return 0 if overall["overall_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
