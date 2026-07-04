"""Task 2-7c-light v2: observe strength/trend balance without forcing positive net."""
from __future__ import annotations

import pandas as pd

from .pressure_action_task2_7c_light_strength_trend_validation import (
    HORIZON,
    STRENGTH_MULTIPLIERS,
    TASK2_7C_LIGHT_VERSION,
    REQUIRED_TASK2_7C_COLUMNS,
    build_strength_trend_light_validation_table,
    summarize_strength_trend_light_validation,
)

TASK2_7C_LIGHT_V2_VERSION = TASK2_7C_LIGHT_VERSION + "_observe_net"


def validate_strength_trend_light_validation_v2_table(table: pd.DataFrame) -> list[str]:
    errors: list[str] = []
    if table is None or table.empty:
        return ["task2_7c_light_table_empty"]
    missing = sorted(set(REQUIRED_TASK2_7C_COLUMNS) - set(table.columns))
    if missing:
        return ["task2_7c_missing:" + ",".join(missing)]
    for field in ["runtime_policy_input", "action_frame_created", "actionmodule_called", "world_runtime_called", "canonical_write_performed"]:
        if bool(table[field].astype(bool).any()):
            errors.append(f"task2_7c_forbidden_true:{field}")
    if set(table["strength_multiplier"].astype(float)) != set(float(x) for x in STRENGTH_MULTIPLIERS):
        errors.append("task2_7c_strength_multipliers_missing")
    if int(table["horizon"].max()) != HORIZON:
        errors.append("task2_7c_horizon_not_40")
    # Do not require positive net benefit.  Net benefit is an observation target.
    if not bool((table["risk_auc_reduction"] > 0.0).any()):
        errors.append("task2_7c_no_risk_auc_reduction")
    if not bool(table["risk_trend_class"].isin(["trend_reversal", "trend_damping", "temporary_relief", "side_effect_dominant", "no_effect"]).all()):
        errors.append("task2_7c_unknown_trend_class")
    return errors


def build_and_validate_strength_trend_light_v2_table() -> tuple[pd.DataFrame, list[str], dict]:
    table = build_strength_trend_light_validation_table()
    errors = validate_strength_trend_light_validation_v2_table(table)
    summary = summarize_strength_trend_light_validation(table)
    summary = dict(summary)
    summary["net_benefit_positive_rows"] = int((table["long_term_net_benefit"] > 0.0).sum()) if not table.empty else 0
    summary["net_benefit_negative_rows"] = int((table["long_term_net_benefit"] < 0.0).sum()) if not table.empty else 0
    return table, errors, summary
