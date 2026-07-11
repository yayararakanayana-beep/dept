"""Public Task 3.2-4 runner with tradeoff-aware research grading."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

import task3_2_4_macro_dynamics as _core


def _judgement(
    selected: Mapping[str, Any],
    baseline: Mapping[str, Any],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    criteria = config["success_criteria"]
    lead_improvement = float(selected["median_lead_time_steps"]) - float(
        baseline["median_lead_time_steps"]
    )
    recall_improvement = float(selected["event_recall"]) - float(
        baseline["event_recall"]
    )
    pair_improvement = float(selected.get("near_state_pair_accuracy", 0.0)) - float(
        baseline.get("near_state_pair_accuracy", 0.0)
    )
    depth_relative_improvement = (
        float(baseline["depth_mae"]) - float(selected["depth_mae"])
    ) / max(float(baseline["depth_mae"]), 1e-12)

    improvements = {
        "lead_time": lead_improvement,
        "event_recall": recall_improvement,
        "near_state_pair": pair_improvement,
        "depth_mae_relative": depth_relative_improvement,
    }
    core_improvements = {
        "lead_time": lead_improvement
        >= float(criteria["lead_time_improvement_steps"]),
        "event_recall": recall_improvement
        >= float(criteria["event_recall_improvement"]),
        "near_state_pair": pair_improvement
        >= float(criteria["near_state_pair_improvement"]),
        "depth_mae": depth_relative_improvement
        >= float(criteria["depth_mae_relative_improvement"]),
    }

    degradation_limit = float(criteria["maximum_core_degradation"])
    depth_worsening_ratio = (
        float(selected["depth_mae"]) / max(float(baseline["depth_mae"]), 1e-12)
    )
    degradation_reasons = {
        "event_recall": float(selected["event_recall"])
        < float(baseline["event_recall"]) - degradation_limit,
        "point_false_alarm": float(selected["false_alarm_rate"])
        > float(baseline["false_alarm_rate"]) + degradation_limit,
        "safe_trajectory_false_alarm": int(selected.get("false_alarm_trajectory_count", 0))
        > int(baseline.get("false_alarm_trajectory_count", 0)),
        "near_state_pair": pair_improvement < -degradation_limit,
        "depth_mae": depth_worsening_ratio > 1.2,
        "brier_score": float(selected["brier_score"])
        > float(baseline["brier_score"]) + degradation_limit,
    }
    core_degraded = any(degradation_reasons.values())
    has_core_improvement = any(core_improvements.values())

    if has_core_improvement and not core_degraded:
        grade = "A_macro_dynamics_promising"
    elif has_core_improvement:
        grade = "B_macro_dynamics_partially_promising"
    elif (
        float(selected["brier_score"]) < float(baseline["brier_score"])
        or float(selected.get("near_state_pair_accuracy", 0.0))
        > float(baseline.get("near_state_pair_accuracy", 0.0))
        or float(selected["depth_mae"]) < float(baseline["depth_mae"])
    ):
        grade = "B_macro_dynamics_partially_promising"
    else:
        grade = "C_macro_dynamics_not_promising_at_current_resolution"

    return {
        "grade": grade,
        "improvements": improvements,
        "core_improvements": core_improvements,
        "core_degraded": core_degraded,
        "degradation_reasons": degradation_reasons,
        "depth_mae_worsening_ratio": depth_worsening_ratio,
        "interpretation": (
            "Earlier warning is treated as partial evidence when it is obtained "
            "with a safe-trajectory false alarm or major losses in risk-depth and "
            "near-state/different-future discrimination."
        ),
    }


_core._judgement = _judgement

MacroDynamicsError = _core.MacroDynamicsError
ChallengeIndex = _core.ChallengeIndex
DynamicsModel = _core.DynamicsModel
Entry = _core.Entry
MacroPreprocessor = _core.MacroPreprocessor
load_config = _core.load_config
macro_feature_frame = _core.macro_feature_frame
run = _core.run
validate_output = _core.validate_output
validate_selection_lock = _core.validate_selection_lock
main = _core.main


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ChallengeIndex",
    "DynamicsModel",
    "Entry",
    "MacroDynamicsError",
    "MacroPreprocessor",
    "load_config",
    "macro_feature_frame",
    "run",
    "validate_output",
    "validate_selection_lock",
    "main",
]
