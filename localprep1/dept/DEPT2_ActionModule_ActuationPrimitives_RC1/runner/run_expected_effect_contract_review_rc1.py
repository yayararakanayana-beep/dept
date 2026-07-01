"""Run ExpectedEffectContractReview RC1."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from DEPT2_ActionModule_ActuationPrimitives_RC1.action_module.expected_effect_contract_review import (
    build_outputs_from_results_dir,
    expected_contract_review_summary_json,
)


def run(results_dir: str | Path, out_dir: str | Path | None = None) -> dict:
    results = Path(results_dir)
    out = Path(out_dir) if out_dir is not None else results
    out.mkdir(parents=True, exist_ok=True)

    outputs = build_outputs_from_results_dir(results)
    name_map = {
        "expected_effect_contract_review_table": "expected_effect_contract_review_table_RC1.csv",
        "expected_effect_contract_feature_evidence": "expected_effect_contract_feature_evidence_RC1.csv",
        "expected_effect_contract_candidate_contracts": "expected_effect_contract_candidate_contracts_RC1.csv",
        "expected_effect_contract_class_summary": "expected_effect_contract_class_summary_RC1.csv",
        "expected_effect_contract_next_action_plan": "expected_effect_contract_next_action_plan_RC1.csv",
    }
    for k, filename in name_map.items():
        outputs[k].to_csv(out / filename, index=False)

    summary = expected_contract_review_summary_json(outputs)
    summary.update({
        "results_dir": str(results),
        "outputs": name_map,
        "review_note": "candidate contracts are diagnostic candidates only; not frozen until patch+rereun.",
    })
    (out / "expected_effect_contract_review_summary_RC1.json").write_text(
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
