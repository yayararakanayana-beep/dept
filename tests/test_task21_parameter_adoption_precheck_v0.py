import json
import subprocess
import sys
from pathlib import Path

import validation.task21_parameter_adoption_precheck_v0 as task21


def test_script_generates_outputs():
    subprocess.run([sys.executable, "validation/task21_parameter_adoption_precheck_v0.py"], check=True)
    for path in [task21.DECISION_JSON, task21.DECISION_MD, task21.VALIDATION_JSON, task21.VALIDATION_MD]:
        assert path.exists()


def test_decision_enum_and_required_fields():
    summary, validation = task21.build_summary()
    assert validation["passed"] is True
    assert set(summary["decision_enum"]) == task21.DECISIONS
    required = {
        "proposal_id", "source_watch_item", "target_parameter", "update_direction", "expected_effect",
        "decision", "decision_reason", "criteria", "missing_evidence", "required_before_shadow_trial",
        "required_before_commit", "evidence_refs", "no_write", "can_update_parameter", "can_write_gk",
        "can_write_world", "can_trigger_action_module",
    }
    assert summary["decisions"]
    for decision in summary["decisions"]:
        assert required <= set(decision)
        assert decision["decision"] in task21.DECISIONS


def test_no_write_boundaries_are_maintained():
    summary, _ = task21.build_summary()
    assert summary["no_write"] is True
    assert all(value is False for value in summary["boundary_check"].values())
    for decision in summary["decisions"]:
        assert decision["no_write"] is True
        assert decision["can_update_parameter"] is False
        assert decision["can_write_gk"] is False
        assert decision["can_write_world"] is False
        assert decision["can_trigger_action_module"] is False


def test_all_criteria_are_present():
    summary, _ = task21.build_summary()
    for decision in summary["decisions"]:
        assert set(task21.CRITERIA) == set(decision["criteria"])
        assert "do_nothing_risk_is_nontrivial" in decision["criteria"]
        assert "shadow_trial_is_possible" in decision["criteria"]
        assert all(value in {True, False, "unknown"} for value in decision["criteria"].values())


def test_commit_candidate_requires_safeguards():
    base = {key: True for key in task21.CRITERIA}
    for missing_key in ["rollback_path_exists", "update_size_is_bounded", "minimum_evidence_exists"]:
        criteria = dict(base)
        criteria[missing_key] = False
        assert task21.classify_from_criteria(criteria, []) != "commit_candidate"


def test_explicit_hard_blockers_are_blocked_but_unknown_is_watch_only():
    base = {key: True for key in task21.CRITERIA}
    for hard_blocker_key in [
        "rollback_path_exists",
        "counter_evidence_is_not_strong",
        "boundary_violation_absent",
    ]:
        criteria = dict(base)
        criteria[hard_blocker_key] = False
        assert task21.classify_from_criteria(criteria, []) == "blocked"
    assert task21.classify_from_criteria(base, [], no_write=False) == "blocked"

    unknown = {key: "unknown" for key in task21.CRITERIA}
    unknown["boundary_violation_absent"] = "unknown"
    assert task21.classify_from_criteria(unknown, []) == "watch_only"


def test_synthetic_fixture_reaches_all_four_classifications():
    all_true = {key: True for key in task21.CRITERIA}
    weak = {key: "unknown" for key in task21.CRITERIA}
    weak["boundary_violation_absent"] = True
    assert task21.classify_from_criteria(weak, ["boundary violation"]) == "blocked"
    assert task21.classify_from_criteria(weak, []) == "watch_only"
    shadow_ready = dict(all_true)
    shadow_ready["update_size_is_bounded"] = "unknown"
    assert task21.classify_from_criteria(shadow_ready, []) == "shadow_trial_candidate"
    assert task21.classify_from_criteria(all_true, []) == "commit_candidate"


def test_generated_json_contains_all_candidates_and_validation_checks():
    subprocess.run([sys.executable, "validation/task21_parameter_adoption_precheck_v0.py"], check=True)
    data = json.loads(Path(task21.DECISION_JSON).read_text(encoding="utf-8"))
    validation = json.loads(Path(task21.VALIDATION_JSON).read_text(encoding="utf-8"))
    proposal_ids = {d["proposal_id"] for d in data["decisions"]}
    assert proposal_ids == {
        "T20F-P01-coactivation_dampen_zone",
        "T20F-P02-residual_noise_high",
        "T20F-P03-shock_recovery_window",
        "T20F-P04-noise_ledger_exploration_gate_relationship",
    }
    assert validation["checks"]["blocked_not_mechanical_without_hard_blocker"] is True
    assert validation["checks"]["commit_candidate_has_required_conditions"] is True
