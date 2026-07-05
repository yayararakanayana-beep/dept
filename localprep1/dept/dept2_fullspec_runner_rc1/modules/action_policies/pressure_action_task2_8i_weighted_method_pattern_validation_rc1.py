"""Task 2-8i RC1 side-effect calibrated wrapper.

This wrapper preserves the Task 2-8i weighted-pattern experiment while
calibrating the per-step side-effect scale to the more precise action-method
setting found in Task 2-8h.

Boundary is unchanged:
    - validation only
    - synthetic dynamics only
    - no exploration-axis incentive
    - no real H-DEPT upper pressure connection
    - no ActionFrame / ActionModule / world runtime / canonical write
"""
from __future__ import annotations

from . import pressure_action_task2_8i_weighted_method_pattern_validation as _base

TASK2_8I_VERSION = _base.TASK2_8I_VERSION
TASK2_8I_CONTRACT = _base.TASK2_8I_CONTRACT
HORIZON = _base.HORIZON
SEEDS = _base.SEEDS
INITIAL_RISK_LEVELS = _base.INITIAL_RISK_LEVELS
CRASH_THRESHOLDS = _base.CRASH_THRESHOLDS
PREDICTION_ACCURACIES = _base.PREDICTION_ACCURACIES
REQUIRED_TASK2_8I_COLUMNS = _base.REQUIRED_TASK2_8I_COLUMNS
WeightPatternSpec = _base.WeightPatternSpec
WEIGHT_PATTERNS = _base.WEIGHT_PATTERNS
WeightedPatternConfig = _base.WeightedPatternConfig
build_pattern_recommendation_table = _base.build_pattern_recommendation_table
summarize_weight_pattern_validation = _base.summarize_weight_pattern_validation
validate_weight_pattern_validation = _base.validate_weight_pattern_validation


def _side_effects_rc1_calibrated(
    pattern: WeightPatternSpec,
    actions: tuple[str, ...],
    active_gate: float,
    prediction_correct: bool,
    actual_effect: float,
) -> dict[str, float]:
    """Lower-cost side-effect model for precise weighted methods.

    Task 2-8h showed that direction-selective / state-dependent / early-release
    methods can act as thin resistance rather than wall-like coefficient
    interventions. Task 2-8i therefore uses a smaller per-step side-effect scale
    while preserving the same ordering:
      - stronger direction weight costs more,
      - incorrect prediction costs more,
      - release/state gates reduce accumulated cost through active_gate/duration.
    """
    if active_gate <= 0.0:
        return {
            "short_gain_loss": 0.0,
            "liquidity_loss": 0.0,
            "overcooling_loss": 0.0,
            "mismatch_cost": 0.0,
            "complexity_cost": 0.0,
        }
    n_actions = len(actions)
    precision_scale = 1.0 if prediction_correct else 1.30
    direction_exposure = 0.35 + 0.75 * float(pattern.direction_weight)
    state_release_discount = 1.0 - 0.20 * float(pattern.state_dependence_weight) - 0.12 * float(pattern.release_weight)
    state_release_discount = max(0.55, state_release_discount)

    short_gain_loss = (
        0.00012 + 0.00032 * float(pattern.base_strength) ** 2
    ) * direction_exposure * active_gate * precision_scale * state_release_discount
    liquidity_loss = (
        0.00010 + 0.00026 * float(pattern.base_strength)
    ) * direction_exposure * active_gate * precision_scale * state_release_discount
    overcooling_loss = max(0.0, actual_effect - 0.010) * (0.010 + 0.004 * n_actions)
    mismatch_cost = 0.0 if prediction_correct else 0.00055 * float(pattern.direction_weight) * active_gate + 0.00025 * float(pattern.base_strength)
    complexity_cost = 0.00008 * max(0, n_actions - 1) * float(pattern.base_strength) * active_gate
    return {
        "short_gain_loss": float(short_gain_loss),
        "liquidity_loss": float(liquidity_loss),
        "overcooling_loss": float(overcooling_loss),
        "mismatch_cost": float(mismatch_cost),
        "complexity_cost": float(complexity_cost),
    }


def _install_calibration() -> None:
    _base._side_effects = _side_effects_rc1_calibrated


def build_weight_pattern_validation_table(cfg: WeightedPatternConfig = WeightedPatternConfig()):
    _install_calibration()
    return _base.build_weight_pattern_validation_table(cfg)


def build_and_validate_weight_pattern_validation_table():
    _install_calibration()
    table = _base.build_weight_pattern_validation_table()
    errors = _base.validate_weight_pattern_validation(table)
    summary = _base.summarize_weight_pattern_validation(table)
    return table, errors, summary
