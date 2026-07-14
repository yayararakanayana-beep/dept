from __future__ import annotations

import copy
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))
if str(ROOT / "validation") not in sys.path:
    sys.path.insert(0, str(ROOT / "validation"))

from relation_field_prediction_p2_precursor_audit import load_contract
from relation_field_prediction_p2_precursor_audit.audit_v1_1 import (
    _scalar,
    assert_primary_score_availability,
)
from relation_field_prediction_p2_formal_audit_v2 import (
    FormalAuditDatasetV2Error,
    expected_support_counts,
    expanded_prefix_signature,
    load_plan,
    validate_plan,
)


def test_v1_1_contract_matches_rf10_recovery_applicability() -> None:
    contract = load_contract()
    rf10 = __import__("json").loads(
        (
            ROOT
            / "configs"
            / "relation_field_predictive_validation_rc1.json"
        ).read_text(encoding="utf-8")
    )

    assert rf10["future_outcomes"]["recovery_failure"][
        "minimum_horizon"
    ] == 2
    recovery = contract["targets"]["recovery_margin_reduction"]
    assert recovery["minimum_horizon"] == 2
    assert recovery["rf10_applicability_field"] == (
        "future_recovery_failure_applicable"
    )
    assert contract["support_gates"][
        "contractually_inapplicable_cells_excluded"
    ] is True
    assert contract["status"].startswith("draft_")
    assert contract["data_independence"][
        "axis_transform_alone_counts_as_independent"
    ] is False


def test_singleton_scalar_reader_and_pre_future_gate() -> None:
    arrays = {
        "scalar": np.asarray(1.25),
        "singleton": np.asarray([2.5]),
        "vector": np.asarray([1.0, 2.0]),
    }
    assert _scalar(arrays, "scalar") == pytest.approx(1.25)
    assert _scalar(arrays, "singleton") == pytest.approx(2.5)
    assert _scalar(arrays, "vector") is None
    assert _scalar(arrays, "missing") is None

    contract = load_contract()
    scores = {
        target_id: {"p2_structure_margin": 0.0}
        for target_id in contract["targets"]
    }
    intervals = {
        target_id: {
            "lower": -0.1,
            "center": 0.0,
            "upper": 0.1,
        }
        for target_id in contract["targets"]
    }
    snapshot = {
        "cases": [
            {
                "case_id": "case-a",
                "prediction_scores": scores,
                "structure_intervals": intervals,
            }
        ]
    }
    result = assert_primary_score_availability(
        snapshot, contract
    )
    assert result["checked_before_future_read"] is True

    broken = copy.deepcopy(snapshot)
    broken["cases"][0]["prediction_scores"]["divergence"][
        "p2_structure_margin"
    ] = None
    with pytest.raises(
        Exception,
        match="before future read",
    ):
        assert_primary_score_availability(broken, contract)


def test_v2_plan_has_distinct_prefix_dynamics_and_support() -> None:
    contract = load_contract()
    plan = load_plan(contract=contract)

    assert len(plan["cases"]) == 36
    assert len(plan["prefix_profiles"]) == 36
    assert plan["independence"][
        "axis_transform_alone_counts_as_independent"
    ] is False
    assert plan["independence"][
        "future_only_counterfactual_pairs_excluded_from_primary_audit"
    ] is True

    raw = {
        expanded_prefix_signature(
            plan,
            case,
            transformed=False,
        )
        for case in plan["cases"]
    }
    recent = {
        expanded_prefix_signature(
            plan,
            case,
            recent_only=True,
            transformed=False,
        )
        for case in plan["cases"]
    }
    assert len(raw) == 36
    assert len(recent) >= 30

    counts = expected_support_counts(plan, contract)
    minimum_positive = contract["support_gates"][
        "minimum_positive_test_outcomes_per_target_horizon"
    ]
    minimum_negative = contract["support_gates"][
        "minimum_negative_test_outcomes_per_target_horizon"
    ]
    required_cells = 0
    for target_id, horizons in counts.items():
        for horizon, record in horizons.items():
            if not record["required"]:
                assert (
                    target_id == "recovery_margin_reduction"
                    and horizon == "1"
                )
                continue
            required_cells += 1
            assert record["positive_count"] >= minimum_positive
            assert record["negative_count"] >= minimum_negative
    assert required_cells == 11


def test_v2_plan_rejects_transform_only_duplicate() -> None:
    contract = load_contract()
    plan = load_plan(contract=contract)
    broken = copy.deepcopy(plan)

    first = broken["cases"][0]
    second = broken["cases"][1]
    second["prefix_profile_id"] = first["prefix_profile_id"]
    second["untransformed_prefix_sha256"] = first[
        "untransformed_prefix_sha256"
    ]

    with pytest.raises(
        FormalAuditDatasetV2Error,
        match="profile references must be unique",
    ):
        validate_plan(broken, contract)


def test_v2_plan_rejects_future_only_pair_in_primary_audit() -> None:
    contract = load_contract()
    plan = load_plan(contract=contract)
    broken = copy.deepcopy(plan)
    broken["independence"][
        "future_only_counterfactual_pairs_excluded_from_primary_audit"
    ] = False
    with pytest.raises(
        FormalAuditDatasetV2Error,
        match="future_only_counterfactual",
    ):
        validate_plan(broken, contract)
