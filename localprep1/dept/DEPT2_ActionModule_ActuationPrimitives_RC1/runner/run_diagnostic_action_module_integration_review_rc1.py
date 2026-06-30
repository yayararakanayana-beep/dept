"""Run DiagnosticActionModuleIntegrationReview RC1."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from DEPT2_ActionModule_ActuationPrimitives_RC1.action_module.diagnostic_action_module_integration_review import (
    build_outputs_from_results_dir,
    integration_review_summary_json,
)


def run(results_dir: str | Path, out_dir: str | Path | None = None) -> dict:
    results = Path(results_dir)
    out = Path(out_dir) if out_dir is not None else results
    out.mkdir(parents=True, exist_ok=True)

    outputs = build_outputs_from_results_dir(results)
    name_map = {
        "diagnostic_action_module_integration_milestones": "diagnostic_action_module_integration_milestones_RC1.csv",
        "diagnostic_action_module_integration_metrics": "diagnostic_action_module_integration_metrics_RC1.csv",
        "diagnostic_action_module_integration_readiness": "diagnostic_action_module_integration_readiness_RC1.csv",
        "diagnostic_action_module_integration_risks": "diagnostic_action_module_integration_risks_RC1.csv",
        "diagnostic_action_module_integration_next_plan": "diagnostic_action_module_integration_next_plan_RC1.csv",
    }
    for k, filename in name_map.items():
        outputs[k].to_csv(out / filename, index=False)

    summary = integration_review_summary_json(outputs)
    summary.update({
        "results_dir": str(results),
        "outputs": name_map,
    })
    (out / "diagnostic_action_module_integration_review_summary_RC1.json").write_text(
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
