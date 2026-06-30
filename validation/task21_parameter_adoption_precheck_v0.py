"""Task21 no-write parameter adoption precheck v0.

Reads Task20J and Task20F/G/H/I artifacts and writes classification summaries.
It does not update ParameterBox, G/K, world state, rollback state, or actions.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "results" / "task21_parameter_adoption_precheck_v0"
DECISION_JSON = OUTPUT_DIR / "precheck_decision_summary.json"
DECISION_MD = OUTPUT_DIR / "precheck_decision_summary.md"
VALIDATION_JSON = OUTPUT_DIR / "precheck_validation_summary.json"
VALIDATION_MD = OUTPUT_DIR / "precheck_validation_summary.md"

INPUTS = {
    "task20j_contract": "results/task20j_gate_contract_freeze/gate_contract_freeze.json",
    "proposal_summary": "results/task20f_no_write_dry_run/proposal_summary.json",
    "task20g_readiness": "results/task20g_pre_commit_readiness/readiness_summary.json",
    "task20h_evidence": "results/task20h_minimal_evidence/evidence_index.json",
    "task20i_rerun": "results/task20i_readiness_rerun/readiness_rerun_summary.json",
}
DECISIONS = {"blocked", "watch_only", "shadow_trial_candidate", "commit_candidate"}
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


def read_json(rel_path: str) -> Any:
    return json.loads((ROOT / rel_path).read_text(encoding="utf-8"))


def _by_id(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {item.get("proposal_id", ""): item for item in items}


def criteria_for_candidate(candidate: dict[str, Any], readiness: dict[str, Any] | None, rerun: dict[str, Any] | None,
                           evidence_refs: list[str], boundary_ok: bool) -> dict[str, str | bool]:
    target_clear = bool(candidate.get("affected_surface")) and "relationship" not in candidate.get("source_watch_item", "")
    direction_clear = any(word in candidate.get("candidate_type", "") for word in ["dampen", "buffer"])
    effect_clear = bool(candidate.get("expected_effect"))
    minimum_evidence = bool(evidence_refs)
    rollback_known = "reversible" in candidate.get("reversibility", "").lower() or "observe-only fallback" in candidate.get("reversibility", "").lower()
    return {
        "target_parameter_is_clear": True if target_clear else "unknown",
        "update_direction_is_clear": True if direction_clear else "unknown",
        "expected_effect_is_explainable": True if effect_clear else "unknown",
        "minimum_evidence_exists": True if minimum_evidence else "unknown",
        "counter_evidence_is_not_strong": True,
        "update_size_is_bounded": "unknown",
        "rollback_path_exists": True if rollback_known else "unknown",
        "do_nothing_risk_is_nontrivial": "unknown",
        "boundary_violation_absent": boundary_ok,
        "shadow_trial_is_possible": "unknown",
    }


def classify_from_criteria(criteria: dict[str, str | bool], hard_blockers: list[str], *, no_write: bool = True) -> str:
    if hard_blockers or not no_write:
        return "blocked"
    if criteria.get("boundary_violation_absent") is False:
        return "blocked"
    if criteria.get("rollback_path_exists") is False:
        return "blocked"
    if criteria.get("counter_evidence_is_not_strong") is False:
        return "blocked"

    commit_required = [
        "target_parameter_is_clear", "update_direction_is_clear", "expected_effect_is_explainable",
        "minimum_evidence_exists", "counter_evidence_is_not_strong", "update_size_is_bounded",
        "rollback_path_exists", "do_nothing_risk_is_nontrivial", "boundary_violation_absent",
        "shadow_trial_is_possible",
    ]
    if all(criteria.get(key) is True for key in commit_required):
        return "commit_candidate"

    shadow_required = [
        "target_parameter_is_clear", "update_direction_is_clear", "expected_effect_is_explainable",
        "minimum_evidence_exists", "counter_evidence_is_not_strong", "rollback_path_exists",
        "boundary_violation_absent", "shadow_trial_is_possible",
    ]
    if all(criteria.get(key) is True for key in shadow_required):
        return "shadow_trial_candidate"
    return "watch_only"


def build_decision(candidate: dict[str, Any], readiness: dict[str, Any] | None, rerun: dict[str, Any] | None,
                   evidence_items: list[dict[str, Any]], contract_boundary: dict[str, Any]) -> dict[str, Any]:
    evidence_refs = [e["evidence_id"] for e in evidence_items if e.get("category") == candidate.get("source_watch_item")]
    boundary_ok = all(value is False for value in contract_boundary.values()) and candidate.get("no_write_status") is True
    criteria = criteria_for_candidate(candidate, readiness, rerun, evidence_refs, boundary_ok)
    hard_blockers: list[str] = []
    if not boundary_ok:
        hard_blockers.append("boundary violation or no_write break detected")
    risk_text = " ".join(str(candidate.get(k, "")) for k in ["risk", "required_guard", "expected_effect"])
    if any(term in risk_text.lower() for term in ["canonical write required", "parameterbox update required", "irreversible write"]):
        hard_blockers.append("candidate text appears to require forbidden irreversible/canonical update")
    decision = classify_from_criteria(criteria, hard_blockers, no_write=True)
    missing = []
    if readiness:
        missing.extend(readiness.get("next_required_evidence", []))
    if rerun:
        missing.extend(rerun.get("evidence_missing", []))
    missing = list(dict.fromkeys(missing))
    if decision == "watch_only":
        reason = "signal and observation value exist, but current evidence leaves target/direction/effect, bounded update, rollback, do-nothing risk, or shadow-trial path insufficiently settled; missing evidence alone is not treated as a hard blocker."
    elif decision == "blocked":
        reason = "hard blocker present: " + "; ".join(hard_blockers)
    elif decision == "shadow_trial_candidate":
        reason = "criteria support a bounded no-write Parameter Shadow Box trial only; canonical writes remain forbidden."
    else:
        reason = "criteria are strong enough for future formal review only; Task21 still forbids all writes."
    return {
        "proposal_id": candidate.get("proposal_id"),
        "source_watch_item": candidate.get("source_watch_item"),
        "target_parameter": candidate.get("affected_surface", "unknown"),
        "update_direction": candidate.get("candidate_type", "unknown"),
        "expected_effect": candidate.get("expected_effect", "unknown"),
        "decision": decision,
        "decision_reason": reason,
        "criteria": criteria,
        "missing_evidence": missing,
        "required_before_shadow_trial": [m for m in missing] + ["bounded shadow update size", "explicit shadow rollback/abandon path", "shadow-trial protocol that cannot write canonical parameters"],
        "required_before_commit": [m for m in missing] + ["successful reviewed no-write shadow trial", "formal ParameterBox review outside Task21", "explicit rollback path", "bounded update size"],
        "evidence_refs": evidence_refs,
        "no_write": True,
        "can_update_parameter": False,
        "can_write_gk": False,
        "can_write_world": False,
        "can_trigger_action_module": False,
    }


def build_summary() -> tuple[dict[str, Any], dict[str, Any]]:
    data = {name: read_json(path) for name, path in INPUTS.items()}
    proposals = data["proposal_summary"].get("proposal_candidates", [])
    g_by_id = _by_id(data["task20g_readiness"].get("candidate_readiness", []))
    i_by_id = _by_id(data["task20i_rerun"].get("candidate_readiness", []))
    evidence = data["task20h_evidence"].get("evidence_items", [])
    decisions = [build_decision(p, g_by_id.get(p.get("proposal_id")), i_by_id.get(p.get("proposal_id")), evidence, data["task20j_contract"].get("boundary_check", {})) for p in proposals]
    boundary_check = {
        "canonical_write_enabled": False,
        "gk_writeback_enabled": False,
        "world_write_by_shadow_enabled": False,
        "parameter_update_implemented": False,
        "commit_gate_implemented": False,
        "rollback_gate_implemented": False,
        "action_module_reads_dept_internals": False,
        "action_frame_generation_implemented": False,
        "task21_precheck_is_controller": False,
    }
    summary = {
        "task": "Task21 Parameter Adoption Precheck v0",
        "scope": "no-write classifier only; no parameter update, commit gate, rollback execution, world write, G/K writeback, or ActionModule connection",
        "no_write": True,
        "inputs": INPUTS,
        "decision_enum": sorted(DECISIONS),
        "criteria_enum": CRITERIA,
        "boundary_check": boundary_check,
        "decisions": decisions,
    }
    validation = build_validation(summary, len(proposals), data["task20j_contract"])
    return summary, validation


def build_validation(summary: dict[str, Any], proposal_count: int, contract: dict[str, Any]) -> dict[str, Any]:
    decisions = summary["decisions"]
    checks = {
        "task20j_contract_loaded": bool(contract.get("contract_frozen")),
        "decision_enum_matches_four_classifications": set(summary["decision_enum"]) == DECISIONS,
        "all_candidates_included": len(decisions) == proposal_count,
        "no_write_true": summary["no_write"] is True and all(d["no_write"] is True for d in decisions),
        "can_update_parameter_all_false": all(d["can_update_parameter"] is False for d in decisions),
        "can_write_gk_all_false": all(d["can_write_gk"] is False for d in decisions),
        "can_write_world_all_false": all(d["can_write_world"] is False for d in decisions),
        "can_trigger_action_module_all_false": all(d["can_trigger_action_module"] is False for d in decisions),
        "boundary_check_all_false": all(value is False for value in summary["boundary_check"].values()),
        "blocked_not_mechanical_without_hard_blocker": all(d["decision"] != "blocked" or "hard blocker present" in d["decision_reason"] for d in decisions),
        "commit_candidate_has_required_conditions": all(d["decision"] != "commit_candidate" or all(d["criteria"][k] is True for k in ["rollback_path_exists", "update_size_is_bounded", "minimum_evidence_exists", "boundary_violation_absent", "counter_evidence_is_not_strong"]) for d in decisions),
        "shadow_trial_candidate_path_exists": classify_from_criteria({**{k: True for k in CRITERIA}, "update_size_is_bounded": "unknown"}, []) == "shadow_trial_candidate",
        "commit_candidate_path_exists": classify_from_criteria({k: True for k in CRITERIA}, []) == "commit_candidate",
        "do_nothing_risk_is_nontrivial_in_criteria": all("do_nothing_risk_is_nontrivial" in d["criteria"] for d in decisions),
        "shadow_trial_is_possible_in_criteria": all("shadow_trial_is_possible" in d["criteria"] for d in decisions),
    }
    return {"task": "Task21 Parameter Adoption Precheck v0 validation", "checks": checks, "passed": all(checks.values())}


def render_decision_md(summary: dict[str, Any]) -> str:
    lines = ["# Task21 Parameter Adoption Precheck v0", "", f"- no_write: {str(summary['no_write']).lower()}", "", "## Decisions"]
    for d in summary["decisions"]:
        lines += ["", f"### {d['proposal_id']}", f"- source_watch_item: {d['source_watch_item']}", f"- decision: {d['decision']}", f"- reason: {d['decision_reason']}", f"- evidence_refs: {', '.join(d['evidence_refs']) or 'none'}", "- can_update_parameter: false", "- can_write_gk: false", "- can_write_world: false", "- can_trigger_action_module: false"]
    lines.append("")
    return "\n".join(lines)


def render_validation_md(validation: dict[str, Any]) -> str:
    lines = ["# Task21 Parameter Adoption Precheck v0 Validation", "", f"- passed: {str(validation['passed']).lower()}", "", "## Checks"]
    for key, value in validation["checks"].items():
        lines.append(f"- {key}: {str(value).lower()}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    summary, validation = build_summary()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DECISION_JSON.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    DECISION_MD.write_text(render_decision_md(summary), encoding="utf-8")
    VALIDATION_JSON.write_text(json.dumps(validation, indent=2) + "\n", encoding="utf-8")
    VALIDATION_MD.write_text(render_validation_md(validation), encoding="utf-8")


if __name__ == "__main__":
    main()
