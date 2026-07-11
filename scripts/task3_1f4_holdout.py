from __future__ import annotations

import argparse

from scripts.task3_1f_structure_extraction.holdout import evaluate_holdout


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--selection-artifact-dir", required=True)
    parser.add_argument("--holdout-bundle", required=True)
    parser.add_argument("--holdout-row-map", required=True)
    parser.add_argument("--holdout-evaluation-metadata", required=True)
    parser.add_argument("--output-root", default="artifacts")
    parser.add_argument("--contract", default="configs/task3_1f_structure_extraction_contract.json")
    args = parser.parse_args()
    print(
        evaluate_holdout(
            selection_artifact_dir=args.selection_artifact_dir,
            holdout_bundle=args.holdout_bundle,
            holdout_row_map=args.holdout_row_map,
            holdout_evaluation_metadata=args.holdout_evaluation_metadata,
            output_root=args.output_root,
            contract_path=args.contract,
        )
    )


if __name__ == "__main__":
    main()
