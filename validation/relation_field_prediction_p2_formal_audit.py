from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))
if str(ROOT / "validation") not in sys.path:
    sys.path.insert(0, str(ROOT / "validation"))

from generic_relation_field_g2 import build_fixed5_structure_artifact
from relation_field_grid_rc1 import build_grid_artifact
from relation_field_prediction_coordinates_p2 import build_relation_field_prediction_coordinates, validate_relation_field_prediction_coordinates
from relation_field_prediction_p2_precursor_audit import DEFAULT_CONTRACT, build_relation_field_prediction_p2_precursor_audit, load_contract, validate_relation_field_prediction_p2_precursor_audit
from relation_field_prediction_p2_precursor_audit.common import canonical_digest, dump_json, load_json
from relation_field_prediction_state_p1 import build_prediction_state_series, validate_prediction_state_series
from relation_field_prediction_p2_formal_audit_plan import DEFAULT_PLAN, expected_support_counts, load_plan, validate_plan
from relation_field_prediction_p2_formal_audit_helpers import _scientific_status, _transformed_geometry, _verify_expected_outcomes, _verify_primary_score_availability, _primary_metric_summary, _write_trajectory


def run(
    work_dir: Path,
    *,
    plan_path: Path = DEFAULT_PLAN,
    contract_path: Path = DEFAULT_CONTRACT,
) -> dict[str, Any]:
    work_dir = work_dir.resolve()
    plan = load_plan(plan_path)
    contract = load_contract(contract_path)
    validate_plan(plan, contract)

    if work_dir.exists():
        shutil.rmtree(work_dir)
    work_dir.mkdir(parents=True)

    frozen_plan = {
        "plan": plan,
        "plan_sha256": canonical_digest(plan),
        "contract_version": contract["contract_version"],
        "contract_sha256": canonical_digest(contract),
        "frozen_before_p1_or_p2_build": True,
        "score_driven_selection_performed": False,
    }
    dump_json(work_dir / "dataset_plan_frozen.json", frozen_plan)
    expected_counts = expected_support_counts(plan, contract)
    dump_json(
        work_dir / "expected_support_preflight.json",
        expected_counts,
    )

    grid = build_grid_artifact(work_dir / "grid")
    structure = build_fixed5_structure_artifact(
        grid, work_dir / "structure"
    )
    case_manifest: dict[str, Any] = {
        "manifest_version": contract["input"][
            "case_manifest_version"
        ],
        "cases": [],
    }

    for position, case in enumerate(plan["cases"], start=1):
        case_id = str(case["case_id"])
        family = plan["families"][case["family_id"]]
        geometry = _transformed_geometry(plan, case)
        prefix_frames = geometry[
            f"{family['prefix_kind']}_prefix"
        ]
        future_frames = [
            geometry[name] for name in family["future_pattern"]
        ]
        case_root = work_dir / "cases" / case_id
        trajectory_id = f"p2_4_formal_{case_id}"
        print(
            f"[{position:02d}/{len(plan['cases'])}] "
            f"build {case_id} family={case['family_id']}",
            flush=True,
        )

        prefix = _write_trajectory(
            case_root / "prefix",
            prefix_frames,
            trajectory_id,
        )
        p1 = build_prediction_state_series(
            prefix,
            grid,
            structure,
            case_root / "p1",
            origins=[int(value) for value in plan["origins"]],
        )
        validate_prediction_state_series(
            p1, prefix, grid, structure
        )
        p2 = build_relation_field_prediction_coordinates(
            p1, case_root / "p2"
        )
        validate_relation_field_prediction_coordinates(p2, p1)
        full = _write_trajectory(
            case_root / "full",
            list(prefix_frames) + list(future_frames),
            trajectory_id,
        )

        case_manifest["cases"].append(
            {
                "case_id": case_id,
                "partition": "test",
                "trajectory_group_id": case[
                    "trajectory_group_id"
                ],
                "prefix_trajectory_dir": str(
                    prefix.relative_to(work_dir)
                ),
                "full_trajectory_dir": str(
                    full.relative_to(work_dir)
                ),
                "grid_artifact_dir": str(
                    grid.relative_to(work_dir)
                ),
                "p1_series_dir": str(p1.relative_to(work_dir)),
                "p2_series_dir": str(p2.relative_to(work_dir)),
                "cutoff_t": int(plan["cutoff_t"]),
            }
        )

    manifest_path = work_dir / "case_manifest.json"
    dump_json(manifest_path, case_manifest)

    audit = build_relation_field_prediction_p2_precursor_audit(
        manifest_path,
        work_dir / "audit",
        contract_path=contract_path,
    )
    independent_validation = (
        validate_relation_field_prediction_p2_precursor_audit(
            audit,
            manifest_path,
            contract_path=contract_path,
        )
    )
    expected_gate = _verify_expected_outcomes(plan, audit)
    availability_gate = _verify_primary_score_availability(
        audit, contract
    )

    support = load_json(audit / "support_audit.json")
    if not support["all_target_horizon_cells_supported"]:
        raise FormalAuditDatasetError(
            f"formal support gate failed: {support}"
        )
    recovery_horizon_one = next(
        row
        for row in support["cells"]
        if row["target_id"] == "recovery_margin_reduction"
        and int(row["horizon"]) == 1
    )
    if (
        recovery_horizon_one["status"]
        != "not_applicable_by_contract"
        or recovery_horizon_one["required_for_support"] is not False
    ):
        raise FormalAuditDatasetError(
            "recovery horizon one applicabilility correction failed"
         )

    decision = load_json(audit / "decision.json")
    scientific_status = _scientific_status(
        str(decision["status"])
    )
    primary_metrics = _primary_metric_summary(audit, contract)

    summary = {
        "formal_audit_status": "completed",
        "dataset_scope": plan["scientific_scope"],
        "test_case_count": len(plan["cases"]),
        "trajectory_group_count": len(
            {
                case["trajectory_group_id"]
                for case in plan["cases"]
            }
        ),
        "shared_prediction_prefix_between_cases": False,
        "support_gate": support,
        "decision": decision,
        "primary_metrics": primary_metrics,
        "independent_validation": independent_validation,
        "expected_outcome_validation": expected_gate,
        "primary_score_availability": availability_gate,
        "scientific_status": scientific_status,
        "real_world_generalization_claim": False,
        "true_irreversibility_claim": False,
        "p3_model_fitted": False,
    }
    dump_json(work_dir / "formal_audit_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--work-dir",
        type=Path,
        default=ROOT / "results" / "p2_4_formal_audit",
    )
    parser.add_argument(
        "--plan",
        type=Path,
        default=DEFAULT_PLAN,
    )
    parser.add_argument(
        "--contract",
        type=Path,
        default=DEFAULT_CONTRACT,
    )
    args = parser.parse_args()
    run(
        args.work_dir,
        plan_path=args.plan,
        contract_path=args.contract,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
