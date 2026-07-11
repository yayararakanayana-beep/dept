from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "task3_2_1_macro_dynamics_contract.py"
SPEC = importlib.util.spec_from_file_location("task3_2_1_contract", MODULE_PATH)
assert SPEC and SPEC.loader
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


def contract() -> dict:
    return module.load_contract(ROOT / "configs" / "task3_2_1_macro_dynamics_contract.json")


def external() -> dict[str, float]:
    return {
        "external_resource_supply": 0.0,
        "external_demand": 0.0,
        "external_competition_pressure": 0.0,
        "external_information_noise": 0.0,
        "external_shock": 0.0,
        "external_constraint_pressure": 0.0,
    }


def metadata(split: str = "exploratory") -> dict:
    return {
        "trajectory_id": "traj_0001",
        "scenario_id": "stable_smoke",
        "seed": 7,
        "initial_state_id": "default_reset",
        "world_module": "pseudo_reality.distribution_terrain_v3_2_2",
        "world_class": "DistributionTerrainV322World",
        "world_version": "v3.3",
        "config_version": "task3_2_smoke_v1",
        "total_steps": 2,
        "dataset_split": split,
    }


def step_record(step: int, c: dict) -> dict:
    state_ref = f"states/traj_0001/step_{step:06d}.npz"
    model_input = {
        "state_ref": state_ref,
        "history_available_through_step": None if step == 0 else step - 1,
        "observed_external_input": external(),
        "observed_events": [],
        "observed_action": None,
        "observed_response": None,
    }
    return {
        "trajectory_id": "traj_0001",
        "step": step,
        "phase": "pre_transition",
        "state_ref": state_ref,
        "history_available_through_step": None if step == 0 else step - 1,
        "observed_external_input": external(),
        "observed_events": [],
        "observed_action": None,
        "observed_response": None,
        "state_arrays_available": list(c["step_record"]["required_state_arrays"]),
        "model_input": model_input,
    }


def truth_record(step: int, c: dict) -> dict:
    return {
        "trajectory_id": "traj_0001",
        "prediction_step": step,
        "target_step": step + 1,
        "next_state_ref": f"states/traj_0001/step_{step + 1:06d}.npz",
        "future_risk_event": "not_evaluated",
        "future_risk_horizon_steps": None,
        "recovery_outcome": "not_evaluated",
        "recovery_time_steps": None,
        "irreversibility_level": None,
        "risk_depth": {name: None for name in c["truth_record"]["risk_depth_fields"]},
        "boundary_crossing_step": None,
        "truth_source": "not_evaluated",
    }


def test_contract_and_valid_bundle_pass() -> None:
    c = contract()
    steps = [step_record(step, c) for step in range(3)]
    truth = [truth_record(step, c) for step in range(2)]
    result = module.validate_bundle(metadata(), steps, truth, c)
    assert result == {
        "trajectory_id": "traj_0001",
        "dataset_split": "exploratory",
        "state_record_count": 3,
        "transition_truth_count": 2,
        "future_leakage_check": "passed",
        "status": "valid",
    }


def test_model_input_future_leakage_is_rejected() -> None:
    c = contract()
    record = step_record(0, c)
    record["model_input"]["future_risk_event"] = "collapse"
    with pytest.raises(module.ContractError, match="leakage"):
        module.validate_step_record(record, c)


def test_history_alignment_is_enforced() -> None:
    c = contract()
    record = step_record(2, c)
    record["history_available_through_step"] = 0
    record["model_input"]["history_available_through_step"] = 0
    with pytest.raises(module.ContractError, match="step - 1"):
        module.validate_step_record(record, c)


def test_required_full_state_arrays_are_enforced() -> None:
    c = contract()
    record = step_record(0, c)
    record["state_arrays_available"].remove("distribution")
    with pytest.raises(module.ContractError, match="missing required arrays"):
        module.validate_step_record(record, c)


def test_external_factor_range_is_enforced() -> None:
    c = contract()
    record = step_record(0, c)
    record["observed_external_input"]["external_shock"] = -0.1
    record["model_input"]["observed_external_input"]["external_shock"] = -0.1
    with pytest.raises(module.ContractError, match="outside"):
        module.validate_step_record(record, c)


def test_truth_must_point_forward() -> None:
    c = contract()
    record = truth_record(1, c)
    record["target_step"] = 1
    with pytest.raises(module.ContractError, match="strictly later"):
        module.validate_truth_record(record, c)


def test_trajectory_split_leakage_is_rejected() -> None:
    c = contract()
    fit = metadata("fit")
    holdout = copy.deepcopy(fit)
    holdout["dataset_split"] = "holdout"
    with pytest.raises(module.ContractError, match="multiple splits"):
        module.validate_split_assignments([fit, holdout], c)


def test_model_input_window_keeps_current_state_separate_from_history() -> None:
    c = contract()
    steps = [step_record(step, c) for step in range(3)]
    window = module.build_model_input_window(steps, current_step=2, history_width=1, contract=c)
    assert window["current_step"] == 2
    assert window["X_t"]["state_ref"].endswith("step_000002.npz")
    assert len(window["L_t"]) == 1
    assert window["L_t"][0]["state_ref"].endswith("step_000001.npz")
    serialized = json.dumps(window)
    assert "future_risk_event" not in serialized
    assert "next_state_ref" not in serialized
