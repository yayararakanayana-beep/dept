import json
import subprocess
import sys
from pathlib import Path

import validation.task20j_gate_contract_freeze as task20j


def test_build_contract_missing_input_does_not_fail(monkeypatch, tmp_path):
    monkeypatch.setattr(task20j, "ROOT", tmp_path)
    contract = task20j.build_contract()
    assert contract["missing_input"] is True
    assert len(contract["input_errors"]) == len(task20j.SOURCE_TRACE)
    assert contract["no_write"] is True


def test_contract_core_flags_and_boundaries():
    contract = task20j.build_contract()
    assert contract["no_write"] is True
    assert contract["contract_frozen"] is True
    assert contract["ready_for_task21_no_write_gate"] is True
    assert all(value is False for value in contract["boundary_check"].values())
    assert contract["boundary_check"]["commit_gate_implemented"] is False
    assert contract["boundary_check"]["parameter_update_implemented"] is False


def test_candidate_contract_defaults_blocked():
    contract = task20j.build_contract()
    candidates = contract["candidate_contract"]
    assert {item["proposal_id"] for item in candidates} == {
        "T20F-P01-coactivation_dampen_zone",
        "T20F-P02-residual_noise_high",
        "T20F-P03-shock_recovery_window",
        "T20F-P04-noise_ledger_exploration_gate_relationship",
    }
    assert all(item["default_decision"] == "blocked" for item in candidates)


def test_task21_decision_schema_disallows_writes_and_actions():
    schema = task20j.build_contract()["task21_decision_schema"]
    assert schema["can_update_parameter"] is False
    assert schema["can_write_gk"] is False
    assert schema["can_write_world"] is False
    assert schema["can_trigger_action_module"] is False


def test_script_generates_json_and_markdown_outputs():
    subprocess.run([sys.executable, "validation/task20j_gate_contract_freeze.py"], check=True)
    json_path = Path("results/task20j_gate_contract_freeze/gate_contract_freeze.json")
    markdown_path = Path("results/task20j_gate_contract_freeze/gate_contract_freeze.md")
    assert json_path.exists()
    assert markdown_path.exists()
    data = json.loads(json_path.read_text(encoding="utf-8"))
    assert data["contract_frozen"] is True
    assert "# Task20J Gate Contract Freeze" in markdown_path.read_text(encoding="utf-8")
