"""Run CouplingReliefStagedUnlockRepair RC1."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from DEPT2_ActionModule_ActuationPrimitives_RC1.action_module.coupling_relief_staged_unlock_repair import (
    build_outputs_from_results_dir,
    sequence_repair_summary_json,
)


def run(results_dir: str | Path, out_dir: str | Path | None = None) -> dict:
    results = Path(results_dir)
    out = Path(out_dir) if out_dir is not None else results
    out.mkdir(parents=True, exist_ok=True)

    outputs = build_outputs_from_results_dir(results)
    name_map = {
        "coupling_relief_staged_unlock_targets": "coupling_relief_staged_unlock_targets_RC1.csv",
        "coupling_relief_staged_unlock_variant_alignment": "coupling_relief_staged_unlock_variant_alignment_RC1.csv",
        "coupling_relief_staged_unlock_variant_summary": "coupling_relief_staged_unlock_variant_summary_RC1.csv",
        "coupling_relief_staged_unlock_repaired_policy": "coupling_relief_staged_unlock_repaired_policy_RC1.csv",
        "coupling_relief_staged_unlock_prior_rc2": "coupling_relief_staged_unlock_prior_rc2_RC1.csv",
        "coupling_relief_staged_unlock_repair_table": "coupling_relief_staged_unlock_repair_table_RC1.csv",
    }
    for k, filename in name_map.items():
        outputs[k].to_csv(out / filename, index=False)

    summary = sequence_repair_summary_json(outputs)
    summary.update({
        "results_dir": str(results),
        "outputs": name_map,
    })
    (out / "coupling_relief_staged_unlock_repair_summary_RC1.json").write_text(
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
