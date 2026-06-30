"""Run PressureOutcomeAlignmentAudit RC2b.

RC2b audits alignment readiness after DiagnosticActionTranslationPolicy_RC1.

It does not overclaim outcome improvement because rescued diagnostic actions were
not yet re-run through pseudo-reality.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from DEPT2_ActionModule_ActuationPrimitives_RC1.action_module.pressure_outcome_alignment_audit_rc2b import (
    build_outputs_from_results_dir,
    rc2b_summary_json,
    _safe_json,
)


def run(results_dir: str | Path, out_dir: str | Path | None = None) -> dict:
    results = Path(results_dir)
    out = Path(out_dir) if out_dir is not None else results
    out.mkdir(parents=True, exist_ok=True)

    outputs = build_outputs_from_results_dir(results)
    name_map = {
        "rc2b_semantic_policy_alignment": "pressure_outcome_alignment_rc2b_semantic_policy_alignment.csv",
        "rc2b_coverage_delta": "pressure_outcome_alignment_rc2b_coverage_delta.csv",
        "rc2b_outcome_attribution_status": "pressure_outcome_alignment_rc2b_outcome_attribution_status.csv",
        "rc2b_diagnostic_action_readiness": "pressure_outcome_alignment_rc2b_diagnostic_action_readiness.csv",
        "rc2b_next_closed_loop_requirements": "pressure_outcome_alignment_rc2b_next_closed_loop_requirements.csv",
    }
    for k, filename in name_map.items():
        outputs[k].to_csv(out / filename, index=False)

    policy_summary = _safe_json(results / "diagnostic_action_translation_policy_summary_RC1.json")
    summary = rc2b_summary_json(outputs, diagnostic_policy_summary=policy_summary)
    summary.update({
        "results_dir": str(results),
        "outputs": name_map,
        "boundary_note": "RC2b confirms diagnostic action coverage, but newly rescued actions require closed-loop rerun for true outcome attribution.",
    })
    (out / "pressure_outcome_alignment_rc2b_summary.json").write_text(
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
