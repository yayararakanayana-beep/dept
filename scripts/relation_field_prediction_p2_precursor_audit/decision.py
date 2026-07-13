from __future__ import annotations

from typing import Any, Mapping, Sequence

from .common import target_horizon_required


def support_audit(
    rows: Sequence[Mapping[str, Any]], contract: Mapping[str, Any]
) -> dict[str, Any]:
    all_test_rows = [row for row in rows if row["partition"] == "test"]
    unique_cases = sorted({str(row["case_id"]) for row in all_test_rows})
    settings = contract["support_gates"]
    applicable_rows = [
        row for row in all_test_rows if row.get("applicable", True)
    ]
    cells: list[dict[str, Any]] = []
    all_required_cells_supported = True
    required_cell_count = 0
    supported_required_cell_count = 0

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

            required_cell_count += 1
            selected = [
                row
                for row in applicable_rows
                if row["target_id"] == target_id
                and int(row["horizon"]) == horizon_value
            ]
            positive = sum(bool(row["outcome"]) for row in selected)
            negative = len(selected) - positive
            supported = (
                len(unique_cases)
                >= int(settings["minimum_test_cases_for_accuracy_claim"])
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
            if supported:
                supported_required_cell_count += 1
            all_required_cells_supported = (
                all_required_cells_supported and supported
            )
            cells.append(
                {
                    "target_id": target_id,
                    "horizon": horizon_value,
                    "required_for_support": True,
                    "status": "supported" if supported else "insufficient",
                    "sample_count": len(selected),
                    "positive_outcome_count": positive,
                    "negative_outcome_count": negative,
                    "supported": supported,
                }
            )

    return {
        "test_case_count": len(unique_cases),
        "minimum_test_case_count": int(
            settings["minimum_test_cases_for_accuracy_claim"]
        ),
        "required_cell_count": required_cell_count,
        "supported_required_cell_count": supported_required_cell_count,
        "contractually_inapplicable_cell_count": len(cells)
        - required_cell_count,
        "all_target_horizon_cells_supported": all_required_cells_supported,
        "cells": cells,
    }


def phase3_decision(
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

    primary = contract["evaluation"]["primary_partition_for_phase3_decision"]
    needed_horizons = int(
        contract["support_gates"][
            "minimum_supported_horizons_for_target_precursor_signal"
        ]
    )
    supported_targets: list[str] = []
    target_rows: list[dict[str, Any]] = []

    for target_id in sorted(contract["targets"]):
        qualifying: list[int] = []
        applicable_horizons = [
            int(horizon)
            for horizon in contract["evaluation"]["horizons"]
            if target_horizon_required(contract, target_id, int(horizon))
        ]
        for row in metrics:
            if (
                row["partition"] != primary
                or row["target_id"] != target_id
                or row["score_id"] != "p2_structure_margin"
                or int(row["horizon"]) not in applicable_horizons
            ):
                continue
            auc_interval = row["bootstrap"].get("roc_auc_interval")
            ap_interval = row["bootstrap"].get(
                "average_precision_interval"
            )
            prevalence = row.get("positive_prevalence")
            qualifies = bool(
                auc_interval is not None
                and ap_interval is not None
                and prevalence is not None
                and float(auc_interval[0]) > 0.5
                and float(ap_interval[0]) > float(prevalence)
            )
            if qualifies:
                qualifying.append(int(row["horizon"]))

        target_supported = len(set(qualifying)) >= needed_horizons
        if target_supported:
            supported_targets.append(target_id)
        target_rows.append(
            {
                "target_id": target_id,
                "applicable_horizons": applicable_horizons,
                "qualifying_horizons": sorted(set(qualifying)),
                "minimum_required_horizons": needed_horizons,
                "precursor_signal_supported": target_supported,
            }
        )

    all_targets = sorted(contract["targets"])
    if len(supported_targets) == len(all_targets):
        status = "eligible_for_full_phase3_model_comparison"
    elif supported_targets:
        status = "eligible_for_partial_phase3_model_comparison"
    else:
        status = "blocked_no_supported_precursor_signal"

    return {
        "status": status,
        "supported_targets": supported_targets,
        "unsupported_targets": [
            value for value in all_targets if value not in supported_targets
        ],
        "performance_interpretation_allowed": True,
        "target_audit": target_rows,
        "reason": (
            "Decision uses the preregistered bootstrap lower-bound rule "
            "without fitting a predictor and only on applicable horizons."
        ),
    }
