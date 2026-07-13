from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for value in (ROOT / "scripts", ROOT / "validation"):
    if str(value) not in sys.path:
        sys.path.insert(0, str(value))

from relation_field_prediction_p2_precursor_audit import (  # noqa: E402
    DEFAULT_CONTRACT,
    load_contract,
)
from relation_field_prediction_p2_precursor_audit.decision import (  # noqa: E402
    support_audit,
)
from relation_field_prediction_p2_precursor_audit.validator import (  # noqa: E402
    _support as independent_support,
)
from relation_field_prediction_p2_formal_audit import (  # noqa: E402
    expected_support_counts,
    expanded_prefix_signature,
    load_plan,
    validate_plan,
)


def _support_rows(contract: dict) -> list[dict]:
    rows: list[dict] = []
    for case_index in range(30):
        case_id = f"case-{case_index:03d}"
        for target_id in sorted(contract["targets"]):
            minimum = int(
                contract["targets"][target_id]["minimum_horizon"]
            )
            for horizon in contract["evaluation"]["horizons"]:
                applicable = int(horizon) >= minimum
                rows.append(
                    {
                        "case_id": case_id,
                        "partition": "test",
                        "trajectory_group_id": case_id,
                        "horizon": int(horizon),
                        "target_id": target_id,
                        "applicable": applicable,
                        "outcome": (
                            bool(case_index < 5)
                            if applicable
                            else False
                        ),
                    }
                )
    return rows


def test_v1_1_contract_keeps_v1_readable_and_fixes_applicability() -> None:
    contract = load_contract()
    assert DEFAULT_CONTRACT.name.endswith("_v1_1.json")
    assert (
        contract["contract_version"]
        == "relation_field_prediction_p2_precursor_audit_v1_1"
    )
    assert (
        contract["targets"]["recovery_margin_reduction"][
            "minimum_horizon"
        ]
        == 2
    )
    assert (
        contract["support_gates"][
            "contractually_inapplicable_cells_excluded"
        ]
        is True
    )

    old_contract = load_contract(
        ROOT
        / "configs"
        / "relation_field_prediction_p2_precursor_audit_contract.json"
    )
    assert (
        old_contract["contract_version"]
        == "relation_field_prediction_p2_precursor_audit_v1"
    )


def test_support_excludes_recovery_horizon_one_in_both_paths() -> None:
    contract = load_contract()
    rows = _support_rows(contract)
    builder = support_audit(rows, contract)
    independent = independent_support(rows, contract)
    assert builder == independent
    assert builder["test_case_count"] == 30
    assert builder["required_cell_count"] == 11
    assert builder["supported_required_cell_count"] == 11
    assert builder["contractually_inapplicable_cell_count"] == 1
    assert builder["all_target_horizon_cells_supported"] is True

    recovery_one = next(
        row
        for row in builder["cells"]
        if row["target_id"] == "recovery_margin_reduction"
        and row["horizon"] == 1
    )
    assert recovery_one == {
        "target_id": "recovery_margin_reduction",
        "horizon": 1,
        "required_for_support": False,
        "status": "not_applicable_by_contract",
        "sample_count": 0,
        "positive_outcome_count": 0,
        "negative_outcome_count": 0,
        "supported": None,
    }


def test_formal_plan_is_preregistered_independent_and_supported() -> None:
    contract = load_contract()
    plan = load_plan()
    validate_plan(plan, contract)

    assert len(plan["cases"]) == 36
    assert len(
        {case["trajectory_group_id"] for case in plan["cases"]}
    ) == 36
    assert {case["partition"] for case in plan["cases"]} == {"test"}
    assert all(
        "score" not in key.lower()
        for case in plan["cases"]
        for key in case
    )
    signatures = [
        expanded_prefix_signature(plan, case)
        for case in plan["cases"]
    ]
    assert len(signatures) == len(set(signatures)) == 36

    counts = expected_support_counts(plan, contract)
    for target_id, horizons in counts.items():
        for horizon, record in horizons.items():
            if not record["required"]:
                assert (
                    target_id == "recovery_margin_reduction"
                    and horizon == "1"
                )
                continue
            assert record["positive_count"] >= 5
            assert record["negative_count"] >= 5
