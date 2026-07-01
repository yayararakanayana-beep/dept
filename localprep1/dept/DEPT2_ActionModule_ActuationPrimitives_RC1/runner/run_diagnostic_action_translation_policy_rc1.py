"""Run DiagnosticActionTranslationPolicy RC1.

Builds a validation-only action translation policy from existing semantic chain
outputs. It does not claim safety or governance readiness.

Goal:
    ensure pressure semantic effects survive into weak diagnostic actions so
    later pressure-outcome alignment audits can be meaningful.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from DEPT2_ActionModule_ActuationPrimitives_RC1.action_module.diagnostic_action_translation_policy import (
    DiagnosticPolicyConfig,
    build_outputs_from_results_dir,
    diagnostic_policy_summary_json,
)


def run(results_dir: str | Path, out_dir: str | Path | None = None, mode: str = "alignment_probe") -> dict:
    results = Path(results_dir)
    out = Path(out_dir) if out_dir is not None else results
    out.mkdir(parents=True, exist_ok=True)

    cfg = DiagnosticPolicyConfig(mode=mode)
    outputs = build_outputs_from_results_dir(results, cfg=cfg)

    name_map = {
        "diagnostic_policy_plan": "diagnostic_action_translation_policy_plan_RC1.csv",
        "diagnostic_policy_action_frame": "diagnostic_action_translation_policy_action_frame_RC1.csv",
        "diagnostic_policy_drop_reason": "diagnostic_action_translation_policy_drop_reason_RC1.csv",
        "diagnostic_policy_semantic_coverage": "diagnostic_action_translation_policy_semantic_coverage_RC1.csv",
        "diagnostic_policy_primitive_route_summary": "diagnostic_action_translation_policy_primitive_route_summary_RC1.csv",
        "diagnostic_policy_family_summary": "diagnostic_action_translation_policy_family_summary_RC1.csv",
    }

    for k, filename in name_map.items():
        outputs[k].to_csv(out / filename, index=False)

    summary = diagnostic_policy_summary_json(outputs)
    summary.update({
        "results_dir": str(results),
        "outputs": name_map,
        "policy_note": "validation-only weak diagnostic action pass-through; not a safety/governance policy",
    })
    (out / "diagnostic_action_translation_policy_summary_RC1.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2))
    return summary


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results-dir", default="results")
    ap.add_argument("--out", default=None)
    ap.add_argument("--mode", default="alignment_probe", choices=["alignment_probe", "diagnostic_translation"])
    args = ap.parse_args()
    run(args.results_dir, args.out, mode=args.mode)


if __name__ == "__main__":
    main()
