from __future__ import annotations

import argparse

from scripts.task3_1f_structure_extraction.final_validator import validate_final


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--contract", default="configs/task3_1f_structure_extraction_contract.json")
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    validate_final(
        args.artifact_dir,
        contract_path=args.contract,
        strict=args.strict,
        write_outputs=True,
    )


if __name__ == "__main__":
    main()
