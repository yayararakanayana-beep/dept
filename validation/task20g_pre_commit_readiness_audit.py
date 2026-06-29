#!/usr/bin/env python3
"""Task20G pre-commit readiness audit.

Reads the Task20f proposal-only compact summary and determines, without
writing canonical state or implementing any gate, whether the candidates have
enough evidence to proceed to commit-gate implementation. Compact summaries are
not sufficient evidence, so every candidate remains not gate-ready and records
the minimum next evidence needed.
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
    "readiness_audit_is_controller": False,
}

DEFAULT_NEXT_REQUIRED_EVIDENCE = [
    "candidate-specific source rows or trace excerpts, not only compact summary fields",
    "independent boundary evidence confirming no canonical parameter, G/K, world-state, or ActionModule write path",
    "reviewed guard evidence matching the candidate required_guard before any future commit-gate design",
]

CANDIDATE_EVIDENCE_HINTS = {
    "coactivation_dampen_zone": [
        "coactivation gate measurements showing the dampen zone, threshold context, and candidate impact window",
        "shadow/audit confirmation that dampening remains diagnostic and cannot update the Parameter Box",
    ],
    "residual_noise_high": [
        "residual/noise ledger rows showing sustained high residual/noise and unresolved residual preservation needs",
        "evidence that buffer handling is observe-only and cannot trigger canonical writes",
    ],
    "shock_recovery_window": [
        "shock onset, peak, recovery, and return-to-baseline timing evidence",
        "evidence separating recovery-window observation from rollback-gate behavior",
    ],
    "noise_ledger_exploration_gate_relationship": [
        "ablation comparison evidence separating ledger visibility, exploration projection, local audit, and gate modulation roles",
        "sidecar boundary evidence confirming no exploration sidecar to ActionFrame coupling",
    ],
}


def _short_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _load_json(source_path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not source_path.exists():
        return None, f"missing input: {source_path}"
    try:
        loaded = json.loads(source_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return None, f"invalid json: {source_path}: {exc}"
    if not isinstance(loaded, dict):
        return None, f"invalid input: {source_path}: expected a JSON object"
    return loaded, None


def _candidate_next_required_evidence(candidate: dict[str, Any]) -> list[str]:
    source_watch_item = str(candidate.get("source_watch_item", ""))
    evidence = list(DEFAULT_NEXT_REQUIRED_EVIDENCE)
    evidence.extend(CANDIDATE_EVIDENCE_HINTS.get(source_watch_item, []))
    required_guard = candidate.get("required_guard")
    if required_guard:
        evidence.append(f"documented satisfaction of required_guard: {required_guard}")
    return evidence


def build_summary(input_root: Path, source: Path | None = None) -> dict[str, Any]:
    input_root = input_root.resolve()
    source_path = source or input_root / "results" / "task20f_no_write_dry_run" / "proposal_summary.json"
    if not source_path.is_absolute():
        source_path = input_root / source_path

    proposal_summary, input_error = _load_json(source_path)
    candidates: list[dict[str, Any]] = []
    compact_summary_only = proposal_summary is not None

    if proposal_summary:
        for candidate in proposal_summary.get("proposal_candidates", []):
            if not isinstance(candidate, dict):
                continue
            candidates.append(
                {
                    "proposal_id": candidate.get("proposal_id"),
                    "source_watch_item": candidate.get("source_watch_item"),
                    "candidate_type": candidate.get("candidate_type"),
                    "evidence_source": candidate.get("evidence_source"),
                    "gate_ready": False,
                    "readiness_reason": "compact Task20f summary alone is insufficient evidence for commit-gate implementation",
                    "next_required_evidence": _candidate_next_required_evidence(candidate),
                    "no_write_status": True,
                }
            )

    return {
        "task": "Task20G pre-commit readiness audit",
        "scope": "no-write readiness audit; no commit gate; no parameter update",
        "no_write": True,
        "missing_input": proposal_summary is None,
        "input_error": input_error,
        "source": _short_path(source_path, input_root),
        "compact_summary_only": compact_summary_only,
        "commit_gate_implemented": False,
        "parameter_update_implemented": False,
        "gate_ready_overall": False,
        "boundary_check": dict(BOUNDARY_CHECK),
        "candidate_readiness": candidates,
    }


def write_summary(summary: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "readiness_summary.json"
    md_path = output_dir / "readiness_summary.md"
    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# Task20G Pre-Commit Readiness Audit",
        "",
        f"no_write: `{str(summary['no_write']).lower()}`",
        f"missing_input: `{str(summary['missing_input']).lower()}`",
        f"source: `{summary['source']}`",
        f"commit_gate_implemented: `{str(summary['commit_gate_implemented']).lower()}`",
        f"parameter_update_implemented: `{str(summary['parameter_update_implemented']).lower()}`",
        f"gate_ready_overall: `{str(summary['gate_ready_overall']).lower()}`",
        "",
        "## Readiness Decision",
        "",
        "Compact Task20f proposal summaries are not sufficient evidence to proceed to commit-gate implementation. All candidates remain `gate_ready: false`.",
        "",
        "## Candidate Readiness",
        "",
    ]
    if summary["candidate_readiness"]:
        for candidate in summary["candidate_readiness"]:
            lines.extend([
                f"### {candidate['proposal_id']}",
                f"- source_watch_item: `{candidate['source_watch_item']}`",
                f"- candidate_type: `{candidate['candidate_type']}`",
                f"- evidence_source: {candidate['evidence_source']}",
                f"- gate_ready: `{str(candidate['gate_ready']).lower()}`",
                f"- readiness_reason: {candidate['readiness_reason']}",
                "- next_required_evidence:",
            ])
            for item in candidate["next_required_evidence"]:
                lines.append(f"  - {item}")
            lines.append("")
    else:
        lines.extend(["No candidate readiness entries generated.", ""])

    lines.extend(["## Boundary Check", ""])
    for key, value in summary["boundary_check"].items():
        lines.append(f"- {key}: `{str(value).lower()}`")
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Task20G pre-commit readiness audit summary.")
    parser.add_argument("--input-root", type=Path, default=Path.cwd())
    parser.add_argument("--source", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=Path("results/task20g_pre_commit_readiness"))
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
