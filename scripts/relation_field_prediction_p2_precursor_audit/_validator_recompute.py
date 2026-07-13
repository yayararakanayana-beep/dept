from __future__ import annotations

from typing import Any, Mapping, Sequence

from .common import target_horizon_required
from ._validator_math import _bootstrap, _permutation, _point


def _reconstruct_samples(
    snapshot: Mapping[str, Any],
    futures: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> list[dict[str, Any]]:
    by_id = {
        str(row["case_id"]): row for row in futures["cases"]
    }
    rows: list[dict[str, Any]] = []
    for frozen in snapshot["cases"]:
        future = by_id[str(frozen["case_id"])]
        for horizon in contract["evaluation"]["horizons"]:
            payload = future["horizons"][str(int(horizon))]
            for target_id, target in contract["targets"].items():
                applicability = target.get(
                    "rf10_applicability_field"
                )
                rows.append(
                    {
                        "case_id": frozen["case_id"],
                        "partition": frozen["partition"],
                        "trajectory_group_id": frozen[
                            "trajectory_group_id"
                        ],
                        "cutoff_t": frozen["cutoff_t"],
                        "horizon": int(horizon),
                        "target_id": target_id,
                        "outcome": bool(
                            payload[target["rf10_outcome_field"]]
                        ),
                        "applicable": (
                            True
                            if applicability is None
                            else bool(payload[applicability])
                        ),
                        "scores": dict(
                            frozen["prediction_scores"][target_id]
                        ),
                        "structure_interval": frozen[
                            "structure_intervals"
                        ][target_id],
                        "applicability_coordinates": frozen[
                            "applicability"
                        ],
                    }
                )

    for partition in contract["input"]["allowed_partitions"]:
        for horizon in contract["evaluation"]["horizons"]:
            for target_id in sorted(contract["targets"]):
                selected = [
                    row
                    for row in rows
                    if row["partition"] == partition
                    and row["horizon"] == int(horizon)
                    and row["target_id"] == target_id
                    and row["scores"]["p2_structure_margin"]
                    is not None
                ]
                values = _permutation(
                    [
                        row["scores"]["p2_structure_margin"]
                        for row in selected
                    ],
                    {
                        "contract_version": contract[
                            "contract_version"
                        ],
                        "partition": partition,
                        "horizon": int(horizon),
                        "target_id": target_id,
                        "score_id": (
                            "p2_structure_margin_time_shuffled"
                        ),
                    },
                )
                for row, value in zip(selected, values):
                    row["scores"][
                        "p2_structure_margin_time_shuffled"
                    ] = value
    return rows


def _metric_rows(
    samples: Sequence[Mapping[str, Any]],
    contract: Mapping[str, Any],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    bootstrap_settings = contract["metrics"]["bootstrap"]
    for partition in contract["input"]["allowed_partitions"]:
        for horizon in contract["evaluation"]["horizons"]:
            for target_id in sorted(contract["targets"]):
                for score_id in contract["score_panels"]:
                    chosen = [
                        row
                        for row in samples
                        if row["partition"] == partition
                        and row["horizon"] == int(horizon)
                        and row["target_id"] == target_id
                        and row.get("applicable", True)
                        and row["scores"].get(score_id) is not None
                    ]
                    scores = [
                        float(row["scores"][score_id])
                        for row in chosen
                    ]
                    outcomes = [
                        bool(row["outcome"]) for row in chosen
                    ]
                    groups = [
                        str(row["trajectory_group_id"])
                        for row in chosen
                    ]
                    point = _point(scores, outcomes)
                    if scores:
                        bootstrap = _bootstrap(
                            scores,
                            outcomes,
                            groups,
                            replicates=int(
                                bootstrap_settings["replicates"]
                            ),
                            confidence=float(
                                bootstrap_settings["confidence"]
                            ),
                            key={
                                "contract_version": contract[
                                    "contract_version"
                                ],
                                "partition": partition,
                                "horizon": int(horizon),
                                "target_id": target_id,
                                "score_id": score_id,
                            },
                        )
                    else:
                        bootstrap = {
                            "requested_replicates": int(
                                bootstrap_settings["replicates"]
                            ),
                            "trajectory_group_count": 0,
                            "roc_auc_valid_replicates": 0,
                            "average_precision_valid_replicates": 0,
                            "roc_auc_interval": None,
                            "average_precision_interval": None,
                        }
                    output.append(
                        {
                            "partition": partition,
                            "horizon": int(horizon),
                            "target_id": target_id,
                            "score_id": score_id,
                            **point,
                            "bootstrap": bootstrap,
                        }
                    )
    return output


def _support(
    samples: Sequence[Mapping[str, Any]],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    all_test = [
        row for row in samples if row["partition"] == "test"
    ]
    cases = sorted({str(row["case_id"]) for row in all_test})
    applicable = [
        row for row in all_test if row.get("applicable", True)
    ]
    settings = contract["support_gates"]
    cells: list[dict[str, Any]] = []
    all_ok = True
    required_count = 0
    supported_count = 0

    for target_id in sorted(contract["targets"]):
        for horizon in contract["evaluation"]["horizons"]:
            horizon_value = int(horizon)
            required = target_horizon_required(
                contract, target_id, horizon_value
            )
            if not required:
                cells.append(
                    {
                        "target_id": target_id,
                        "horizon": horizon_value,
                        "required_for_support": False,
                        "status": "not_applicable_by_contract",
                        "sample_count": 0,
                        "positive_outcome_count": 0,
                        "negative_outcome_count": 0,
                        "supported": None,
                    }
                )
                continue

            required_count += 1
            chosen = [
                row
                for row in applicable
                if row["target_id"] == target_id
                and row["horizon"] == horizon_value
            ]
            positive = sum(bool(row["outcome"]) for row in chosen)
            negative = len(chosen) - positive
            ok = (
                len(cases)
                >= int(
                    settings[
                        "minimum_test_cases_for_accuracy_claim"
                    ]
                )
                and positive
                >= int(
                    settings[
                        "minimum_positive_test_outcomes_per_target_horizon"
                    ]
                )
                and negative
                >= int(
                    settings[
                        "minimum_negative_test_outcomes_per_target_horizon"
                    ]
                )
            )
            if ok:
                supported_count += 1
            all_ok = all_ok and ok
            cells.append(
                {
                    "target_id": target_id,
                    "horizon": horizon_value,
                    "required_for_support": True,
                    "status": "supported" if ok else "insufficient",
                    "sample_count": len(chosen),
                    "positive_outcome_count": positive,
                    "negative_outcome_count": negative,
                    "supported": ok,
                }
            )

    return {
        "test_case_count": len(cases),
        "minimum_test_case_count": int(
            settings["minimum_test_cases_for_accuracy_claim"]
        ),
        "required_cell_count": required_count,
        "supported_required_cell_count": supported_count,
        "contractually_inapplicable_cell_count": (
            len(cells) - required_count
        ),
        "all_target_horizon_cells_supported": all_ok,
        "cells": cells,
    }


def _decision(
    metrics: Sequence[Mapping[str, Any]],
    support: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    if not support["all_target_horizon_cells_supported"]:
        return {
            "status": "blocked_support_insufficient",
            "supported_targets": [],
            "unsupported_targets": sorted(contract["targets"]),
            "performance_interpretation_allowed": False,
            "reason": (
                "RF-10 support gates are not met for every applicable "
                "target and horizon."
            ),
        }

    required = int(
        contract["support_gates"][
            "minimum_supported_horizons_for_target_precursor_signal"
        ]
    )
    supported: list[str] = []
    audit: list[dict[str, Any]] = []
    for target_id in sorted(contract["targets"]):
        applicable_horizons = [
            int(horizon)
            for horizon in contract["evaluation"]["horizons"]
            if target_horizon_required(
                contract, target_id, int(horizon)
            )
        ]
        qualifying: list[int] = []
        for row in metrics:
            if (
                row["partition"] == "test"
                and row["target_id"] == target_id
                and row["score_id"] == "p2_structure_margin"
                and int(row["horizon"]) in applicable_horizons
            ):
                auc_interval = row["bootstrap"][
                    "roc_auc_interval"
                ]
                ap_interval = row["bootstrap"][
                    "average_precision_interval"
                ]
                prevalence = row["positive_prevalence"]
                if (
                    auc_interval is not None
                    and ap_interval is not None
                    and prevalence is not None
                    and auc_interval[0] > 0.5
                    and ap_interval[0] > prevalence
                ):
                    qualifying.append(int(row["horizon"]))
        ok = len(set(qualifying)) >= required
        if ok:
            supported.append(target_id)
        audit.append(
            {
                "target_id": target_id,
                "applicable_horizons": applicable_horizons,
                "qualifying_horizons": sorted(set(qualifying)),
                "minimum_required_horizons": required,
                "precursor_signal_supported": ok,
            }
        )

    all_targets = sorted(contract["targets"])
    if len(supported) == len(all_targets):
        status = "eligible_for_full_phase3_model_comparison"
    elif supported:
        status = "eligible_for_partial_phase3_model_comparison"
    else:
        status = "blocked_no_supported_precursor_signal"
    return {
        "status": status,
        "supported_targets": supported,
        "unsupported_targets": [
            target
            for target in all_targets
            if target not in supported
        ],
        "performance_interpretation_allowed": True,
        "target_audit": audit,
        "reason": (
            "Decision uses the preregistered bootstrap lower-bound "
            "rule without fitting a predictor and only on applicable "
            "horizons."
        ),
    }
