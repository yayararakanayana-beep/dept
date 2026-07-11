from __future__ import annotations

import argparse
from pathlib import Path

from task3_1f_structure_extraction import run_stage_bc_formal, run_stage_bc_smoke


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Task 3.1f-3 Stage B/C fit-validation batch.")
    parser.add_argument("--profile", choices=("smoke", "formal"), required=True)
    parser.add_argument("--fit-bundle", required=True)
    parser.add_argument("--fit-row-map", required=True)
    parser.add_argument("--fit-evaluation-metadata")
    parser.add_argument("--validation-bundle", required=True)
    parser.add_argument("--validation-row-map", required=True)
    parser.add_argument("--validation-evaluation-metadata")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--contract", default="configs/task3_1f_structure_extraction_contract.json")
    parser.add_argument("--smoke-ranks", type=int, default=2)
    args = parser.parse_args()

    fit_evaluation = args.fit_evaluation_metadata or str(Path(args.fit_row_map).with_name("fit_evaluation_metadata.csv"))
    validation_evaluation = args.validation_evaluation_metadata or str(
        Path(args.validation_row_map).with_name("validation_evaluation_metadata.csv")
    )
    if args.profile == "formal":
        output = run_stage_bc_formal(
            args.fit_bundle,
            args.fit_row_map,
            fit_evaluation,
            args.validation_bundle,
            args.validation_row_map,
            validation_evaluation,
            args.output_root,
            args.contract,
        )
    else:
        output = run_stage_bc_smoke(
            args.fit_bundle,
            args.fit_row_map,
            args.validation_bundle,
            args.validation_row_map,
            args.output_root,
            args.contract,
            smoke_ranks=args.smoke_ranks,
            fit_evaluation_metadata=fit_evaluation,
            validation_evaluation_metadata=validation_evaluation,
        )
    print(output)


if __name__ == "__main__":
    main()
