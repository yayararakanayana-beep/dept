#!/usr/bin/env python3
"""Run PressureSignSemanticsAudit RC1.

Task A: create the chain table:

    approved pressure sign
    -> semantic effect
    -> translated primitive / sequence
    -> actual action channel
    -> observed outcome

This runner uses existing ActionModule_ActuationPrimitives_RC1 result CSVs.
It does not tune DEPT and does not run a new experiment by default.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from action_module.pressure_sign_semantics_audit import (
    build_outputs_from_results_dir,
    audit_summary_json,
)


def run(results_dir: str | Path, out_dir: str | Path | None = None) -> dict:
    results = Path(results_dir)
    out = Path(out_dir) if out_dir is not None else results
    out.mkdir(parents=True, exist_ok=True)

    outputs = build_outputs_from_results_dir(results)

    name_map = {
        "pressure_sign_component_table": "pressure_sign_component_table_RC1.csv",
        "pressure_sign_semantic_chain": "pressure_sign_semantic_chain_RC1.csv",
        "pressure_semantic_plan_action_chain": "pressure_semantic_plan_action_chain_RC1.csv",
        "pressure_semantic_outcome_alignment": "pressure_semantic_outcome_alignment_RC1.csv",
        "pressure_primitive_outcome_alignment": "pressure_primitive_outcome_alignment_RC1.csv",
        "pressure_sign_component_summary": "pressure_sign_component_summary_RC1.csv",
        "pressure_semantic_outcome_summary": "pressure_semantic_outcome_summary_RC1.csv",
        "pressure_primitive_outcome_summary": "pressure_primitive_outcome_summary_RC1.csv",
        "pressure_outcome_increment_table": "pressure_outcome_increment_table_RC1.csv",
    }
    for k, filename in name_map.items():
        outputs[k].to_csv(out / filename, index=False)

    summary = audit_summary_json(outputs)
    summary.update({
        "results_dir": str(results),
        "outputs": name_map,
        "note": "This audit separates pressure sign, semantic effect, primitive/action, and outcome. It does not tune DEPT.",
    })
    (out / "pressure_sign_semantics_audit_summary_RC1.json").write_text(
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
