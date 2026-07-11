"""Validation helpers for Task 3.2-1 macro-dynamics trajectory data.

This task freezes the data boundary only. It deliberately does not define a
macro-dynamics model, risk threshold, history width, or extraction method.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "configs" / "task3_2_1_macro_dynamics_contract.json"


class ContractError(ValueError):
    """Raised when a Task 3.2-1 record violates the frozen data boundary."""


def load_contract(path: str | Path = DEFAULT_CONTRACT) -> dict[str, Any]:
    contract = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_contract(contract)
    return contract


def _require_mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractError(f"{name} must be an object")
    return value


def _require_sequence(value: Any, name: str) -> Sequence[Any]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ContractError(f"{name} must be a list")
    return value


def _require_fields(record: Mapping[str, Any], required: Iterable[str], name: str) -> None:
    missing = sorted(set(required) - set(record))
    if missing:
        raise ContractError(f"{name} missing required fields: {missing}")


def _require_int(value: Any, name: str, *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContractError(f"{name} must be an integer")
    if minimum is not None and value < minimum:
        raise ContractError(f"{name} must be >= {minimum}")
    return value


def _require_text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{name} must be a non-empty string")
    return value


def _require_optional_nonnegative_int(value: Any, name: str) -> int | None:
    if value is None:
        return None
    return _require_int(value, name, minimum=0)


def _walk_keys(value: Any) -> Iterable[str]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield str(key)
            yield from _walk_keys(child)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for child in value:
            yield from _walk_keys(child)


def validate_contract(contract: Mapping[str, Any]) -> None:
    _require_fields(
        contract,
        [
            "task_id",
            "prediction",
            "world",
            "trajectory_metadata",
            "step_record",
            "truth_record",
            "forbidden_model_input_fields",
            "storage",
        ],
        "contract",
    )
    prediction = _require_mapping(contract["prediction"], "prediction")
    if prediction.get("input_formula") != "X_t + L_t":
        raise ContractError("prediction.input_formula must remain X_t + L_t")
    if prediction.get("macro_dynamics_components_frozen") is not False:
        raise ContractError("Task 3.2-1 must not freeze macro-dynamics components")

    world = _require_mapping(contract["world"], "world")
    axes = list(_require_sequence(world.get("axes"), "world.axes"))
    if axes != [
        "resource_slack",
        "information_quality",
        "pressure",
        "exploration_room",
        "reversibility",
    ]:
        raise ContractError("world.axes must match the fixed five-axis coordinate order")
    if world.get("n_bins") != 5 or world.get("cell_count") != 3125:
        raise ContractError("world must use five bins and 3125 cells")

    storage = _require_mapping(contract["storage"], "storage")
    for field in (
        "raw_logs_are_canonical",
        "derived_features_must_be_recomputable",
        "trajectory_level_split_required",
        "random_row_split_forbidden",
    ):
        if storage.get(field) is not True:
            raise ContractError(f"storage.{field} must remain true")


def validate_trajectory_metadata(record: Mapping[str, Any], contract: Mapping[str, Any]) -> None:
    section = _require_mapping(contract["trajectory_metadata"], "trajectory_metadata")
    _require_fields(record, section["required_fields"], "trajectory metadata")
    _require_text(record["trajectory_id"], "trajectory_id")
    _require_text(record["scenario_id"], "scenario_id")
    _require_int(record["seed"], "seed", minimum=0)
    _require_text(record["initial_state_id"], "initial_state_id")
    _require_text(record["world_module"], "world_module")
    _require_text(record["world_class"], "world_class")
    _require_text(record["world_version"], "world_version")
    _require_text(record["config_version"], "config_version")
    _require_int(record["total_steps"], "total_steps", minimum=1)
    if record["dataset_split"] not in section["dataset_splits"]:
        raise ContractError(f"unsupported dataset_split: {record['dataset_split']!r}")


def validate_external_input(value: Any, contract: Mapping[str, Any]) -> None:
    external = _require_mapping(value, "observed_external_input")
    ranges = _require_mapping(contract["step_record"]["external_factor_ranges"], "external_factor_ranges")
    if set(external) != set(ranges):
        raise ContractError(
            "observed_external_input must contain exactly the six contracted external factors"
        )
    for name, bounds in ranges.items():
        number = external[name]
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(float(number)):
            raise ContractError(f"{name} must be a finite number")
        low, high = bounds
        if float(number) < float(low) or float(number) > float(high):
            raise ContractError(f"{name}={number} outside [{low}, {high}]")


def validate_model_input(value: Any, contract: Mapping[str, Any]) -> None:
    model_input = _require_mapping(value, "model_input")
    section = _require_mapping(contract["step_record"], "step_record")
    _require_fields(model_input, section["model_input_required_fields"], "model_input")
    forbidden = set(contract["forbidden_model_input_fields"])
    leaked = sorted(forbidden.intersection(_walk_keys(model_input)))
    if leaked:
        raise ContractError(f"model_input contains future/truth leakage fields: {leaked}")
    validate_external_input(model_input["observed_external_input"], contract)
    _require_sequence(model_input["observed_events"], "model_input.observed_events")


def validate_step_record(record: Mapping[str, Any], contract: Mapping[str, Any]) -> None:
    section = _require_mapping(contract["step_record"], "step_record")
    _require_fields(record, section["required_fields"], "step record")
    _require_text(record["trajectory_id"], "trajectory_id")
    step = _require_int(record["step"], "step", minimum=0)
    if record["phase"] != section["phase"]:
        raise ContractError(f"phase must be {section['phase']!r}")
    _require_text(record["state_ref"], "state_ref")

    history_step = record["history_available_through_step"]
    if step == 0:
        if history_step is not None:
            raise ContractError("step 0 must have history_available_through_step=null")
    else:
        history_step = _require_int(history_step, "history_available_through_step", minimum=0)
        if history_step != step - 1:
            raise ContractError("history_available_through_step must equal step - 1")

    validate_external_input(record["observed_external_input"], contract)
    _require_sequence(record["observed_events"], "observed_events")

    arrays = list(_require_sequence(record["state_arrays_available"], "state_arrays_available"))
    if len(arrays) != len(set(arrays)):
        raise ContractError("state_arrays_available must not contain duplicates")
    missing_arrays = sorted(set(section["required_state_arrays"]) - set(arrays))
    if missing_arrays:
        raise ContractError(f"state snapshot missing required arrays: {missing_arrays}")

    validate_model_input(record["model_input"], contract)
    for field in section["model_input_required_fields"]:
        if record[field] != record["model_input"][field]:
            raise ContractError(f"step record and model_input disagree on {field}")


def validate_truth_record(record: Mapping[str, Any], contract: Mapping[str, Any]) -> None:
    section = _require_mapping(contract["truth_record"], "truth_record")
    _require_fields(record, section["required_fields"], "truth record")
    _require_text(record["trajectory_id"], "trajectory_id")
    prediction_step = _require_int(record["prediction_step"], "prediction_step", minimum=0)
    target_step = _require_int(record["target_step"], "target_step", minimum=1)
    if target_step <= prediction_step:
        raise ContractError("target_step must be strictly later than prediction_step")
    _require_text(record["next_state_ref"], "next_state_ref")

    if record["future_risk_event"] not in section["future_risk_events"]:
        raise ContractError(f"unsupported future_risk_event: {record['future_risk_event']!r}")
    _require_optional_nonnegative_int(record["future_risk_horizon_steps"], "future_risk_horizon_steps")
    if record["recovery_outcome"] not in section["recovery_outcomes"]:
        raise ContractError(f"unsupported recovery_outcome: {record['recovery_outcome']!r}")
    _require_optional_nonnegative_int(record["recovery_time_steps"], "recovery_time_steps")

    level = record["irreversibility_level"]
    if level is not None and level not in section["irreversibility_levels"]:
        raise ContractError("irreversibility_level must be null or one of 0..4")

    risk_depth = _require_mapping(record["risk_depth"], "risk_depth")
    if set(risk_depth) != set(section["risk_depth_fields"]):
        raise ContractError("risk_depth must contain exactly the contracted candidate fields")
    for name, value in risk_depth.items():
        if value is not None and (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(float(value))
        ):
            raise ContractError(f"risk_depth.{name} must be null or a finite number")

    boundary = _require_optional_nonnegative_int(record["boundary_crossing_step"], "boundary_crossing_step")
    if boundary is not None and boundary <= prediction_step:
        raise ContractError("boundary_crossing_step must be later than prediction_step")
    if record["truth_source"] not in section["truth_sources"]:
        raise ContractError(f"unsupported truth_source: {record['truth_source']!r}")


def validate_bundle(
    metadata: Mapping[str, Any],
    step_records: Sequence[Mapping[str, Any]],
    truth_records: Sequence[Mapping[str, Any]],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    validate_trajectory_metadata(metadata, contract)
    if not step_records:
        raise ContractError("step_records must not be empty")
    if not truth_records:
        raise ContractError("truth_records must not be empty")

    trajectory_id = metadata["trajectory_id"]
    for record in step_records:
        validate_step_record(record, contract)
        if record["trajectory_id"] != trajectory_id:
            raise ContractError("step record trajectory_id does not match metadata")
    for record in truth_records:
        validate_truth_record(record, contract)
        if record["trajectory_id"] != trajectory_id:
            raise ContractError("truth record trajectory_id does not match metadata")

    ordered_steps = sorted(record["step"] for record in step_records)
    expected_steps = list(range(int(metadata["total_steps"]) + 1))
    if ordered_steps != expected_steps:
        raise ContractError(
            f"step records must cover contiguous states 0..total_steps; got {ordered_steps}"
        )

    truth_pairs = {(record["prediction_step"], record["target_step"]) for record in truth_records}
    expected_pairs = {(step, step + 1) for step in range(int(metadata["total_steps"]))}
    if truth_pairs != expected_pairs:
        raise ContractError("truth records must contain exactly one next-step target per transition")

    return {
        "trajectory_id": trajectory_id,
        "dataset_split": metadata["dataset_split"],
        "state_record_count": len(step_records),
        "transition_truth_count": len(truth_records),
        "future_leakage_check": "passed",
        "status": "valid",
    }


def validate_split_assignments(metadata_records: Sequence[Mapping[str, Any]], contract: Mapping[str, Any]) -> None:
    seen: dict[str, str] = {}
    for record in metadata_records:
        validate_trajectory_metadata(record, contract)
        trajectory_id = str(record["trajectory_id"])
        split = str(record["dataset_split"])
        if trajectory_id in seen and seen[trajectory_id] != split:
            raise ContractError(
                f"trajectory {trajectory_id!r} appears in multiple splits: {seen[trajectory_id]!r}, {split!r}"
            )
        seen[trajectory_id] = split


def build_model_input_window(
    step_records: Sequence[Mapping[str, Any]],
    current_step: int,
    history_width: int | None,
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Build an X_t + L_t view without exposing truth records.

    ``history_width=None`` means all available prior records. A positive integer
    keeps only the latest requested history. The current state remains separate
    from the history list so later tasks cannot silently treat X_t as a history row.
    """
    _require_int(current_step, "current_step", minimum=0)
    if history_width is not None:
        _require_int(history_width, "history_width", minimum=1)

    by_step = {record["step"]: record for record in step_records}
    if current_step not in by_step:
        raise ContractError(f"current_step {current_step} is not present")
    for record in step_records:
        validate_step_record(record, contract)

    start = 0 if history_width is None else max(0, current_step - history_width)
    history = [by_step[step]["model_input"] for step in range(start, current_step) if step in by_step]
    expected_history_steps = list(range(start, current_step))
    actual_history_steps = [step for step in range(start, current_step) if step in by_step]
    if actual_history_steps != expected_history_steps:
        raise ContractError("history window contains a missing step")

    return {
        "trajectory_id": by_step[current_step]["trajectory_id"],
        "current_step": current_step,
        "X_t": by_step[current_step]["model_input"],
        "L_t": history,
        "history_start_step": start if history else None,
        "history_end_step": current_step - 1 if history else None,
    }


__all__ = [
    "ContractError",
    "DEFAULT_CONTRACT",
    "build_model_input_window",
    "load_contract",
    "validate_bundle",
    "validate_contract",
    "validate_external_input",
    "validate_model_input",
    "validate_split_assignments",
    "validate_step_record",
    "validate_trajectory_metadata",
    "validate_truth_record",
]
