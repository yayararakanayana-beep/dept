"""Freeze the Task20J no-write gate contract for future Task21 review.

This module reads the compact Task20F/G/H/I artifacts when present and writes a
small contract document. It does not implement a commit gate, rollback gate,
parameter update, canonical write, or controller.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "results" / "task20j_gate_contract_freeze"
JSON_OUTPUT = OUTPUT_DIR / "gate_contract_freeze.json"
MD_OUTPUT = OUTPUT_DIR / "gate_contract_freeze.md"

SOURCE_TRACE = {
    "proposal_summary": "results/task20f_no_write_dry_run/proposal_summary.json",
    "task20g_readiness": "results/task20g_pre_commit_readiness/readiness_summary.json",
    "task20h_evidence": "results/task20h_minimal_evidence/evidence_index.json",
    "task20i_rerun": "results/task20i_readiness_rerun/readiness_rerun_summary.json",
}

BOUNDARY_CHECK = {
    "canonical_write_enabled": False,
    "gk_writeback_enabled": False,
    "world_write_by_shadow_enabled": False,
    "parameter_update_implemented": False,
    "commit_gate_implemented": False,
    "rollback_gate_implemented": False,
    "action_module_reads_dept_internals": False,
    "action_frame_generation_implemented": False,
    "exploration_sidecar_to_actionframe_enabled": False,
    "gate_contract_is_controller": False,
}

TASK21_ALLOWED_BEHAVIOR = [
    "read Task20F proposal candidates",
    "read Task20I readiness rerun",
    "read Task20J gate contract",
    "generate gate_decision as no-write output only",
    "emit one decision per candidate: blocked, watch_only, shadow_trial_candidate, or commit_candidate",
    "record decision reason",
    "keep every boundary_check value false",
    "write summary output under results/task21_no_write_commit_gate/",
]

CRITERIA = [
    "target_parameter_is_clear",
    "update_direction_is_clear",
    "expected_effect_is_explainable",
    "minimum_evidence_exists",
    "counter_evidence_is_not_strong",
    "update_size_is_bounded",
    "rollback_path_exists",
    "do_nothing_risk_is_nontrivial",
    "boundary_violation_absent",
    "shadow_trial_is_possible",
]

TASK21_FORBIDDEN_BEHAVIOR = [
    "canonical parameter write",
    "ParameterBox update",
    "G/K writeback",
    "world write",
    "rollback execution",
    "ActionModule internal DEPT read",
    "ActionFrame generation",
    "exploration sidecar direct coupling",
    "commit gate acting as controller",
    "converting readiness into action",
    "hidden threshold-based parameter update",
]

DECISION_SCHEMA = {
    "proposal_id": "...",
    "source_watch_item": "...",
    "decision": "blocked | watch_only | shadow_trial_candidate | commit_candidate",
    "decision_reason": "...",
    "required_before_any_write": [],
    "no_write": True,
    "can_update_parameter": False,
    "can_write_gk": False,
    "can_write_world": False,
    "can_trigger_action_module": False,
}

CLAIM_SCOPE = [
    "This contract only freezes a no-write gate decision interface.",
    "It does not prove safety.",
    "It does not prove superiority.",
    "It does not permit real-world deployment.",
    "It does not implement control.",
    "It does not implement parameter updates.",
]

EXPECTED_CANDIDATES = [
    ("T20F-P01-coactivation_dampen_zone", "coactivation_dampen_zone"),
    ("T20F-P02-residual_noise_high", "residual_noise_high"),
    ("T20F-P03-shock_recovery_window", "shock_recovery_window"),
    ("T20F-P04-noise_ledger_exploration_gate_relationship", "noise_ledger_exploration_gate_relationship"),
]


def _read_json(path: Path) -> tuple[Any | None, str | None]:
    if not path.exists():
        return None, f"missing input: {path.relative_to(ROOT)}"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except json.JSONDecodeError as exc:
        return None, f"invalid json: {path.relative_to(ROOT)}: {exc}"


def _candidate_contract() -> list[dict[str, Any]]:
    return [
        {
            "proposal_id": proposal_id,
            "source_watch_item": source_watch_item,
            "default_decision": "watch_only",
            "default_decision_reason": "current evidence preserves observation value, but Task20J does not authorize canonical writes or force all candidates to blocked; Task21 must classify using the frozen criteria.",
            "allowed_task21_decisions": {
                "blocked": "adoption unavailable due to a boundary violation, unclear target parameter, strong counter-evidence, unavailable rollback, or comparable blocker",
                "watch_only": "continued observation only; signal exists but remains weak as an update candidate",
                "shadow_trial_candidate": "canonical update remains forbidden, but a no-write Parameter Shadow Box trial may be worth future review when criteria are satisfied",
                "commit_candidate": "future formal ParameterBox update candidate only; Task20J/Task21 remain no-write and cannot perform the update",
            },
            "gate_approval_allowed": False,
            "commit_allowed": False,
            "parameter_update_allowed": False,
            "shadow_trial_allowed_now": False,
            "commit_allowed_now": False,
            "classification_criteria": CRITERIA,
            "no_write": True,
        }
        for proposal_id, source_watch_item in EXPECTED_CANDIDATES
    ]


def build_contract() -> dict[str, Any]:
    input_errors = []
    loaded_inputs: dict[str, bool] = {}
    for label, rel_path in SOURCE_TRACE.items():
        _, error = _read_json(ROOT / rel_path)
        loaded_inputs[label] = error is None
        if error:
            input_errors.append(error)

    return {
        "task": "Task20J gate contract freeze",
        "scope": "contract freeze only; not a commit gate implementation; no parameter update",
        "no_write": True,
        "contract_frozen": True,
        "ready_for_task21_no_write_gate": True,
        "missing_input": bool(input_errors),
        "input_errors": input_errors,
        "loaded_inputs": loaded_inputs,
        "source_trace": SOURCE_TRACE,
        "boundary_check": BOUNDARY_CHECK,
        "task21_allowed_behavior": TASK21_ALLOWED_BEHAVIOR,
        "task21_forbidden_behavior": TASK21_FORBIDDEN_BEHAVIOR,
        "criteria": CRITERIA,
        "task21_decision_schema": DECISION_SCHEMA,
        "candidate_contract": _candidate_contract(),
        "claim_scope": CLAIM_SCOPE,
    }


def render_markdown(contract: dict[str, Any]) -> str:
    lines = [
        "# Task20J Gate Contract Freeze",
        "",
        f"- task: {contract['task']}",
        f"- scope: {contract['scope']}",
        f"- no_write: {str(contract['no_write']).lower()}",
        f"- contract_frozen: {str(contract['contract_frozen']).lower()}",
        f"- ready_for_task21_no_write_gate: {str(contract['ready_for_task21_no_write_gate']).lower()}",
        f"- missing_input: {str(contract['missing_input']).lower()}",
        "",
        "## Source Trace",
    ]
    for label, rel_path in contract["source_trace"].items():
        lines.append(f"- {label}: `{rel_path}`")

    lines.extend(["", "## Boundary Check"])
    for key, value in contract["boundary_check"].items():
        lines.append(f"- {key}: {str(value).lower()}")

    lines.extend(["", "## Task21 Allowed Behavior"])
    for item in contract["task21_allowed_behavior"]:
        lines.append(f"- {item}")

    lines.extend(["", "## Criteria"])
    for item in contract["criteria"]:
        lines.append(f"- {item}")

    lines.extend(["", "## Task21 Forbidden Behavior"])
    for item in contract["task21_forbidden_behavior"]:
        lines.append(f"- {item}")

    lines.extend(["", "## Candidate Contract"])
    for item in contract["candidate_contract"]:
        lines.append(
            f"- {item['proposal_id']} ({item['source_watch_item']}): default_decision={item['default_decision']}"
        )

    lines.extend(["", "## Task21 Decision Schema", "", "```json"])
    lines.append(json.dumps(contract["task21_decision_schema"], indent=2))
    lines.extend(["```", "", "## Claim Scope"])
    for item in contract["claim_scope"]:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    contract = build_contract()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_OUTPUT.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
    MD_OUTPUT.write_text(render_markdown(contract), encoding="utf-8")
    print(f"wrote {JSON_OUTPUT.relative_to(ROOT)}")
    print(f"wrote {MD_OUTPUT.relative_to(ROOT)}")
    if contract["missing_input"]:
        print("missing_input: true")


if __name__ == "__main__":
    main()
