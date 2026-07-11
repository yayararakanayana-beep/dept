"""Public runner for Task 3.2-3 simple early-warning baselines."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

import _task3_2_3_core as _core
from _task3_2_3_core import *  # noqa: F401,F403

ROOT = _core.ROOT
EXTERNAL_FIELDS = _core.EXTERNAL_FIELDS
CorpusEntry = _core.CorpusEntry


def _apply_alarm(
    frame: pd.DataFrame,
    probability: np.ndarray,
    threshold: float,
    persistence: int,
) -> np.ndarray:
    """Apply a consecutive-threshold alarm without namedtuple field rewriting."""
    result = np.zeros(len(frame), dtype=np.int64)
    working = frame[["trajectory_id", "step"]].copy()
    working["position"] = np.arange(len(frame), dtype=np.int64)
    working["probability_value"] = np.asarray(probability, dtype=np.float64)
    for _, group in working.groupby("trajectory_id", sort=False):
        run = 0
        for row in group.sort_values("step").to_dict(orient="records"):
            run = run + 1 if float(row["probability_value"]) >= threshold else 0
            if run >= persistence:
                result[int(row["position"])] = 1
    return result


def _research_judgement(
    current_validation: Mapping[str, Any],
    history_validation: Mapping[str, Any],
    current_holdout: Mapping[str, Any],
    history_holdout: Mapping[str, Any],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    """Grade history only when it improves the current-state baseline.

    Reaching an absolute target is not itself an improvement when the current
    state baseline already reaches the same target. Core early-warning gains
    are kept separate from secondary calibration/error gains.
    """
    criteria = config["success_criteria"]
    epsilon = 1e-9
    validation_dimensions = {
        "event_recall_improved": (
            history_validation["event_recall"] > current_validation["event_recall"] + epsilon
        ),
        "lead_time_improved": (
            history_validation["median_lead_time_steps"]
            > current_validation["median_lead_time_steps"] + epsilon
        ),
        "average_precision_improved": (
            history_validation["average_precision"]
            - current_validation["average_precision"]
            >= float(criteria["average_precision_improvement"])
        ),
        "depth_rank_improved": (
            history_validation["depth_rank_correlation"]
            > current_validation["depth_rank_correlation"] + 0.05
            and history_validation["depth_rank_correlation"]
            >= float(criteria["depth_rank_correlation"])
        ),
        "false_alarm_improved": (
            history_validation["false_alarm_rate"]
            <= current_validation["false_alarm_rate"] - 0.01
        ),
        "depth_mae_improved": (
            history_validation["depth_mae"]
            <= 0.8 * max(float(current_validation["depth_mae"]), 1e-12)
        ),
    }
    holdout_direction = {
        "event_recall_non_decreasing": (
            history_holdout["event_recall"] >= current_holdout["event_recall"] - epsilon
        ),
        "lead_time_non_decreasing": (
            history_holdout["median_lead_time_steps"]
            >= current_holdout["median_lead_time_steps"] - epsilon
        ),
        "average_precision_non_decreasing": (
            history_holdout["average_precision"]
            >= current_holdout["average_precision"] - epsilon
        ),
        "depth_rank_non_decreasing": (
            history_holdout["depth_rank_correlation"]
            >= current_holdout["depth_rank_correlation"] - epsilon
        ),
        "false_alarm_non_increasing": (
            history_holdout["false_alarm_rate"]
            <= current_holdout["false_alarm_rate"] + epsilon
        ),
        "depth_mae_non_increasing": (
            history_holdout["depth_mae"] <= current_holdout["depth_mae"] + epsilon
        ),
    }
    core_keys = {
        "event_recall_improved",
        "lead_time_improved",
        "average_precision_improved",
        "depth_rank_improved",
    }
    improved_keys = {key for key, value in validation_dimensions.items() if bool(value)}
    core_improved = len(improved_keys & core_keys)
    maintained_mapping = {
        "event_recall_improved": "event_recall_non_decreasing",
        "lead_time_improved": "lead_time_non_decreasing",
        "average_precision_improved": "average_precision_non_decreasing",
        "depth_rank_improved": "depth_rank_non_decreasing",
        "false_alarm_improved": "false_alarm_non_increasing",
        "depth_mae_improved": "depth_mae_non_increasing",
    }
    maintained_improvements = sum(
        bool(holdout_direction[maintained_mapping[key]]) for key in improved_keys
    )
    if core_improved >= 1 and len(improved_keys) >= 2 and maintained_improvements >= 2:
        grade = "A_promising"
    elif improved_keys:
        grade = "B_partially_promising"
    else:
        grade = "C_not_promising_at_current_resolution"
    return {
        "grade": grade,
        "validation_dimensions": validation_dimensions,
        "holdout_direction": holdout_direction,
        "improved_validation_dimension_count": len(improved_keys),
        "core_early_warning_improvement_count": core_improved,
        "maintained_holdout_direction_count": maintained_improvements,
        "boundary": (
            "History is graded relative to the current-state baseline. "
            "This does not judge macro-dynamics extraction, and the current "
            "corpus reuses the same scenario schedules across seeds."
        ),
    }


_core._apply_alarm = _apply_alarm
_core._research_judgement = _research_judgement


def main(argv: Sequence[str] | None = None) -> int:
    return _core.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = list(_core.__all__) + ["CorpusEntry", "EXTERNAL_FIELDS", "ROOT", "main"]
