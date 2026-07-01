"""Run DiagnosticClosedLoopRerun RC1."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from DEPT2_ActionModule_ActuationPrimitives_RC1.action_module.diagnostic_closed_loop_rerun import (
    DiagnosticRerunConfig,
    build_outputs_from_results_dir,
    diagnostic_rerun_summary_json,
)


def run(results_dir: str | Path, out_dir: str | Path | None = None) -> dict:
    results = Path(results_dir)
    out = Path(out_dir) if out_dir is not None else results
    out.mkdir(parents=True, exist_ok=True)

    outputs = build_outputs_from_results_dir(results, cfg=DiagnosticRerunConfig())

    name_map = {
        "diagnostic_closed_loop_combined_trace": "diagnostic_closed_loop_combined_trace_RC1.csv",
        "diagnostic_closed_loop_action_application": "diagnostic_closed_loop_action_application_RC1.csv",
        "diagnostic_closed_loop_semantic_isolated_alignment": "diagnostic_closed_loop_semantic_isolated_alignment_RC1.csv",
        "diagnostic_closed_loop_semantic_summary": "diagnostic_closed_loop_semantic_summary_RC1.csv",
        "diagnostic_closed_loop_scenario_summary": "diagnostic_closed_loop_scenario_summary_RC1.csv",
    }
    for k, filename in name_map.items():
        outputs[k].to_csv(out / filename, index=False)

    summary = diagnostic_rerun_summary_json(outputs)
    summary.update({
        "results_dir": str(results),
        "outputs": name_map,
        "rerun_note": "Diagnostic actions were actually applied to pseudo-reality in combined and isolated replay modes.",
    })
    (out / "diagnostic_closed_loop_rerun_summary_RC1.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", default="results")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    run(args.results_dir, args.out)


if __name__ == "__main__":
    main()
