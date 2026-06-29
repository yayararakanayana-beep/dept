#!/usr/bin/env python3
"""Task20f no-write dry-run proposal summary generator.

Reads the Task20b watch audit summary and emits diagnostic proposal candidates
for observed watch items only. It never implements parameter updates, commit
gates, rollback gates, writeback, or actuator connections.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

BOUNDARY_CHECK = {
    "canonical_write_enabled": False,
    "gk_writeback_enabled": False,
    "world_write_by_shadow_enabled": False,
    "parameter_update_implemented": False,
    "commit_gate_implemented": False,
    "rollback_gate_implemented": False,
    "action_module_reads_dept_internals": False,
    "proposal_summary_is_controller": False,
}

CANDIDATE_RULES = {
    "coactivation_dampen_zone": {
        "candidate_type": "dampen_candidate",
        "affected_surface": "coactivation gate audit and pre-gate action candidate review",
        "expected_effect": "diagnostically check whether dampening aligns with visible coactivation risk without direct parameter updates",
        "risk": "over-broad dampening could hide useful candidates if treated as control instead of audit",
        "reversibility": "proposal-only; reversible by dropping the candidate before any future gate design",
        "required_guard": "coactivation gate evidence; audit evidence; shadow confirmation; no ActionModule internal access",
    },
    "residual_noise_high": {
        "candidate_type": "buffer_candidate",
        "affected_surface": "residual/noise ledger observation and unresolved residual preservation",
        "expected_effect": "diagnostically preserve high residual/noise visibility for later review",
        "risk": "residual/noise could be over-interpreted as a write signal instead of an observation signal",
        "reversibility": "proposal-only; observe-only fallback remains available",
        "required_guard": "residual/noise ledger audit; no canonical write; no Parameter Box update",
    },
    "shock_recovery_window": {
        "candidate_type": "audit_required",
        "affected_surface": "shock recovery timing and recovery-window audit",
        "expected_effect": "diagnostically separate transient shock recovery from sustained residual/noise elevation",
        "risk": "prematurely treating shock recovery as rollback or immediate dampening would exceed evidence",
        "reversibility": "proposal-only; defer until onset/peak/recovery timing evidence is available",
        "required_guard": "shock onset, peak, and return-to-baseline evidence; no rollback gate implementation",
    },
    "noise_ledger_exploration_gate_relationship": {
        "candidate_type": "audit_required",
        "affected_surface": "noise ledger, exploration projection, local audit, and coactivation gate contribution review",
        "expected_effect": "diagnostically decompose visibility, candidate preservation, and gate modulation contributions",
        "risk": "collapsing ledger, exploration, and gate roles could imply an unsafe direct control path",
        "reversibility": "proposal-only; candidate can be removed without changing runtime behavior",
        "required_guard": "ablation comparison evidence; sidecar boundary confirmation; no exploration sidecar to ActionFrame coupling",
    },
}


def _short_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _load_watch_summary(source_path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not source_path.exists():
        return None, f"missing input: {source_path}"
    try:
        return json.loads(source_path.read_text(encoding="utf-8")), None
    except json.JSONDecodeError as exc:
        return None, f"invalid json: {source_path}: {exc}"


def _evidence_source(item: dict[str, Any]) -> str:
    observed_in = item.get("observed_in") or []
    if isinstance(observed_in, list) and observed_in:
        return "; ".join(str(source) for source in observed_in)
    return "not recorded"


def _proposal_id(index: int, watch_name: str) -> str:
    return f"T20F-P{index:02d}-{watch_name}"


def build_summary(input_root: Path, source: Path | None = None) -> dict[str, Any]:
    input_root = input_root.resolve()
    source_path = source or input_root / "results" / "task20b_watch_audit" / "watch_audit_summary.json"
    if not source_path.is_absolute():
        source_path = input_root / source_path

    watch_summary, input_error = _load_watch_summary(source_path)
    proposal_candidates: list[dict[str, Any]] = []

    if watch_summary:
        watch_items = watch_summary.get("watch_items", {})
        for index, (watch_name, item) in enumerate(watch_items.items(), start=1):
            if not isinstance(item, dict) or item.get("observed") is not True:
                continue
            rule = CANDIDATE_RULES.get(watch_name)
            if rule is None:
                continue
            proposal_candidates.append(
                {
                    "proposal_id": _proposal_id(index, watch_name),
                    "source_watch_item": watch_name,
                    "evidence_source": _evidence_source(item),
                    "candidate_type": rule["candidate_type"],
                    "affected_surface": rule["affected_surface"],
                    "expected_effect": rule["expected_effect"],
                    "risk": rule["risk"],
                    "reversibility": rule["reversibility"],
                    "required_guard": rule["required_guard"],
                    "no_write_status": True,
                    "claim_scope": "diagnostic proposal only",
                }
            )

    return {
        "task": "Task20f no-write dry-run proposal summary",
        "scope": "proposal-only; read-only; no commit gate; no parameter update",
        "no_write": True,
        "missing_input": watch_summary is None,
        "input_error": input_error,
        "source": _short_path(source_path, input_root),
        "boundary_check": dict(BOUNDARY_CHECK),
        "proposal_candidates": proposal_candidates,
    }


def write_summary(summary: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "proposal_summary.json"
    md_path = output_dir / "proposal_summary.md"

    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# Task20f No-Write Dry-Run Proposal Summary",
        "",
        f"no_write: `{str(summary['no_write']).lower()}`",
        f"missing_input: `{str(summary['missing_input']).lower()}`",
        f"source: `{summary['source']}`",
        "",
        "## Proposal Candidates",
        "",
    ]
    if summary["proposal_candidates"]:
        for candidate in summary["proposal_candidates"]:
            lines.extend(
                [
                    f"### {candidate['proposal_id']}",
                    f"- source_watch_item: `{candidate['source_watch_item']}`",
                    f"- evidence_source: {candidate['evidence_source']}",
                    f"- candidate_type: `{candidate['candidate_type']}`",
                    f"- affected_surface: {candidate['affected_surface']}",
                    f"- expected_effect: {candidate['expected_effect']}",
                    f"- risk: {candidate['risk']}",
                    f"- reversibility: {candidate['reversibility']}",
                    f"- required_guard: {candidate['required_guard']}",
                    f"- no_write_status: `{str(candidate['no_write_status']).lower()}`",
                    f"- claim_scope: {candidate['claim_scope']}",
                    "",
                ]
            )
    else:
        lines.extend(["No proposal candidates generated.", ""])

    lines.extend(["## Boundary Check", ""])
    for key, value in summary["boundary_check"].items():
        lines.append(f"- {key}: `{str(value).lower()}`")
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Task20f no-write dry-run proposal summary.")
    parser.add_argument("--input-root", type=Path, default=Path.cwd())
    parser.add_argument("--source", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=Path("results/task20f_no_write_dry_run"))
    args = parser.parse_args()

    output_dir = args.output_dir
    if not output_dir.is_absolute():
        output_dir = args.input_root / output_dir

    summary = build_summary(args.input_root, args.source)
    json_path, md_path = write_summary(summary, output_dir)
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
