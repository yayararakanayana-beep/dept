"""Run DiagnosticClosedLoopRerunReview RC1."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from DEPT2_ActionModule_ActuationPrimitives_RC1.action_module.diagnostic_closed_loop_rerun_review import (
    build_review_outputs,
    review_summary_json,
    _safe_json,
)


def run(results_dir: str | Path, out_dir: str | Path | None = None) -> dict:
    results = Path(results_dir)
    out = Path(out_dir) if out_dir is not None else results
    out.mkdir(parents=True, exist_ok=True)

    outputs = build_review_outputs(results)
    name_map = {
        "diagnostic_rerun_semantic_family_review": "diagnostic_closed_loop_rerun_semantic_family_review_RC1.csv",
        "diagnostic_rerun_scenario_review": "diagnostic_closed_loop_rerun_scenario_review_RC1.csv",
        "diagnostic_rerun_review_class_summary": "diagnostic_closed_loop_rerun_review_class_summary_RC1.csv",
        "diagnostic_rerun_next_action_plan": "diagnostic_closed_loop_rerun_next_action_plan_RC1.csv",
    }
    for k, filename in name_map.items():
        outputs[k].to_csv(out / filename, index=False)

    rerun_summary = _safe_json(results / "diagnostic_closed_loop_rerun_summary_RC1.json")
    summary = review_summary_json(outputs, rerun_summary=rerun_summary)
    summary.update({
        "results_dir": str(results),
        "outputs": name_map,
    })
    (out / "diagnostic_closed_loop_rerun_review_summary_RC1.json").write_text(
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
