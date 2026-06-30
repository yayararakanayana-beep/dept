"""Run ProbeRestraintPrimitivePatch RC1."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from DEPT2_ActionModule_ActuationPrimitives_RC1.action_module.probe_restraint_primitive_patch import (
    build_outputs_from_results_dir,
    patch_summary_json,
)


def run(results_dir: str | Path, out_dir: str | Path | None = None) -> dict:
    results = Path(results_dir)
    out = Path(out_dir) if out_dir is not None else results
    out.mkdir(parents=True, exist_ok=True)

    outputs = build_outputs_from_results_dir(results)
    name_map = {
        "probe_restraint_primitive_patch_table": "probe_restraint_primitive_patch_table_RC1.csv",
        "probe_restraint_primitive_patched_action_frame": "probe_restraint_primitive_patched_action_frame_RC1.csv",
        "probe_restraint_primitive_patch_alignment": "probe_restraint_primitive_patch_alignment_RC1.csv",
        "probe_restraint_primitive_patch_summary": "probe_restraint_primitive_patch_summary_RC1.csv",
        "probe_restraint_primitive_patch_contract_basis": "probe_restraint_primitive_patch_contract_basis_RC1.csv",
    }
    for k, filename in name_map.items():
        outputs[k].to_csv(out / filename, index=False)

    summary = patch_summary_json(outputs)
    summary.update({
        "results_dir": str(results),
        "outputs": name_map,
    })
    (out / "probe_restraint_primitive_patch_summary_RC1.json").write_text(
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
