"""Run PressureOutcomeAlignmentAudit RC2.

RC2 replaces the RC1 primary comparison:

    approved_* sign vs outcome

with the more correct primary comparison:

    semantic_effect / primitive_sequence vs observed outcome

The approved pressure sign remains diagnostic only.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from DEPT2_ActionModule_ActuationPrimitives_RC1.action_module.pressure_outcome_alignment_audit_rc2 import (
    build_rc2_outputs_from_results_dir,
    rc2_summary_json,
)


def run(results_dir: str | Path, out_dir: str | Path | None = None) -> dict:
    results = Path(results_dir)
    out = Path(out_dir) if out_dir is not None else results
    out.mkdir(parents=True, exist_ok=True)

    outputs = build_rc2_outputs_from_results_dir(results)

    name_map = {
        "pressure_outcome_alignment_rc2_semantic_primary": "pressure_outcome_alignment_rc2_semantic_primary.csv",
        "pressure_outcome_alignment_rc2_primitive_primary": "pressure_outcome_alignment_rc2_primitive_primary.csv",
        "pressure_outcome_alignment_rc2_chain_coverage": "pressure_outcome_alignment_rc2_chain_coverage.csv",
        "pressure_outcome_alignment_rc2_semantic_summary": "pressure_outcome_alignment_rc2_semantic_summary.csv",
        "pressure_outcome_alignment_rc2_primitive_summary": "pressure_outcome_alignment_rc2_primitive_summary.csv",
        "pressure_outcome_alignment_rc2_review": "pressure_outcome_alignment_rc2_review.csv",
    }
    for k, filename in name_map.items():
        outputs[k].to_csv(out / filename, index=False)

    summary = rc2_summary_json(outputs)
    summary.update({
        "results_dir": str(results),
        "outputs": name_map,
    })
    (out / "pressure_outcome_alignment_rc2_summary.json").write_text(
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
