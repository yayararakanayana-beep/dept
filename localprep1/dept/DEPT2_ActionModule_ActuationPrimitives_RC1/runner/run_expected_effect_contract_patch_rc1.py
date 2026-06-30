"""Run ExpectedEffectContractPatch RC1."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from DEPT2_ActionModule_ActuationPrimitives_RC1.action_module.expected_effect_contract_patch import (
    build_outputs_from_results_dir,
    patch_summary_json,
)


def run(results_dir: str | Path, out_dir: str | Path | None = None) -> dict:
    results = Path(results_dir)
    out = Path(out_dir) if out_dir is not None else results
    out.mkdir(parents=True, exist_ok=True)

    outputs = build_outputs_from_results_dir(results)
    name_map = {
        "expected_effect_contract_patch_table": "expected_effect_contract_patch_table_RC1.csv",
        "expected_effect_contract_patch_alignment": "expected_effect_contract_patch_alignment_RC1.csv",
        "expected_effect_contract_patch_semantic_summary": "expected_effect_contract_patch_semantic_summary_RC1.csv",
        "expected_effect_contract_patch_comparison": "expected_effect_contract_patch_comparison_RC1.csv",
        "expected_effect_contract_patch_target_comparison": "expected_effect_contract_patch_target_comparison_RC1.csv",
        "expected_effect_contract_patch_targets": "expected_effect_contract_patch_targets_RC1.csv",
    }
    for k, filename in name_map.items():
        outputs[k].to_csv(out / filename, index=False)

    summary = patch_summary_json(outputs)
    summary.update({
        "results_dir": str(results),
        "outputs": name_map,
        "patch_note": "diagnostic expected-effect contracts are patched for validation; not H-DEPT pressure tuning.",
    })
    (out / "expected_effect_contract_patch_summary_RC1.json").write_text(
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
