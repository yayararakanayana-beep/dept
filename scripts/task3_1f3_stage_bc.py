from __future__ import annotations

import argparse
from task3_1f_structure_extraction import run_stage_bc_smoke


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Task 3.1f-3 Stage B/C fit-validation batch smoke path.")
    parser.add_argument("--fit-bundle", required=True)
    parser.add_argument("--fit-row-map", required=True)
    parser.add_argument("--validation-bundle", required=True)
    parser.add_argument("--validation-row-map", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--contract", default="configs/task3_1f_structure_extraction_contract.json")
    parser.add_argument("--smoke-ranks", type=int, default=2)
    args = parser.parse_args()
    out = run_stage_bc_smoke(
        args.fit_bundle,
        args.fit_row_map,
        args.validation_bundle,
        args.validation_row_map,
        args.output_root,
        args.contract,
        smoke_ranks=args.smoke_ranks,
    )
    print(out)

if __name__ == "__main__":
    main()
