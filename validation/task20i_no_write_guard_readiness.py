#!/usr/bin/env python3
"""Task20i no-write guard readiness dry-run.

Reads Task20f proposal candidates and emits a conservative guard readiness audit.
All candidates remain not gate-ready because compact summaries alone are not
enough evidence for a future commit gate.
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
    "guard_readiness_is_controller": False,
}

MISSING_EVIDENCE = {
    "coactivation_dampen_zone": [
        "per-cycle coactivation gate rows",
        "action candidate rows",
        "shadow confirmation rows",
        "audit correlation rows",
    ],
    "residual_noise_high": [
        "residual/noise ledger per-cycle rows",
        "sustained vs transient noise classification",
        "unresolved residual carryover rows",
    ],
    "shock_recovery_window": [
        "shock onset cycle",
        "shock peak cycle",
        "return-to-baseline cycle",
        "recovery stability window rows",
    ],
    "noise_ledger_exploration_gate_relationship": [
        "ablation matrix per-case rows",
        "noise ledger contribution rows",
        "exploration projection contribution rows",
        "coactivation gate modulation rows",
        "sidecar boundary confirmation rows",
    ],
}


def _short_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists():
        return None, f"missing input: {path}"
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except json.JSONDecodeError as exc:
        return None, f"invalid json: {path}: {exc}"


def _missing_for_watch(watch_item: str) -> list[str]:
    return list(MISSING_EVIDENCE.get(watch_item, ["candidate-specific evidence rows"]))


def build_summary(input_root: Path, source: Path | None = None) -> dict[str, Any]:
    input_root = input_root.resolve()
    source_path = source or input_root / "results" / "task20f_no_write_dry_run" / "proposal_summary.json"
    if not source_path.is_absolute():
        source_path = input_root / source_path

    proposal_summary, input_error = _load_json(source_path)
    candidate_readiness: list[dict[str, Any]] = []

    if proposal_summary:
        for candidate in proposal_summary.get("proposal_candidates", []):
            if not isinstance(candidate, dict):
                continue
            watch_item = str(candidate.get("source_watch_item", "unknown"))
            missing = _missing_for_watch(watch_item)
            candidate_readiness.append(
                {
                    "proposal_id": str(candidate.get("proposal_id", "unknown")),
                    "source_watch_item": watch_item,
                    "candidate_type": str(candidate.get("candidate_type", "unknown")),
                    "readiness": "needs_more_evidence",
                    "gate_ready": False,
                    "reason": "compact summary evidence is sufficient for design discussion but insufficient for commit gate readiness",
                    "missing_evidence": missing,
                    "required_next_evidence": missing,
                    "no_write_status": True,
                    "claim_scope": "guard readiness dry-run only",
                }
            )

    return {
        "task": "Task20i no-write guard readiness dry-run",
        "scope": "read-only guard readiness audit; not a commit gate; no parameter update",
        "no_write": True,
        "missing_input": proposal_summary is None,
        "input_error": input_error,
        "source": _short_path(source_path, input_root),
        "boundary_check": dict(BOUNDARY_CHECK),
        "candidate_readiness": candidate_readiness,
    }


def write_summary(summary: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "guard_readiness_summary.json"
    md_path = output_dir / "guard_readiness_summary.md"

    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# Task20i No-Write Guard Readiness Summary",
        "",
        f"no_write: `{str(summary['no_write']).lower()}`",
        f"missing_input: `{str(summary['missing_input']).lower()}`",
        f"source: `{summary['source']}`",
        "",
        "## Candidate Readiness",
        "",
    ]
    if summary["candidate_readiness"]:
        for item in summary["candidate_readiness"]:
            lines.extend(
                [
                    f"### {item['proposal_id']}",
                    f"- source_watch_item: `{item['source_watch_item']}`",
                    f"- candidate_type: `{item['candidate_type']}`",
                    f"- readiness: `{item['readiness']}`",
                    f"- gate_ready: `{str(item['gate_ready']).lower()}`",
                    f"- reason: {item['reason']}",
                    f"- missing_evidence: {', '.join(item['missing_evidence'])}",
                    f"- required_next_evidence: {', '.join(item['required_next_evidence'])}",
                    f"- no_write_status: `{str(item['no_write_status']).lower()}`",
                    f"- claim_scope: {item['claim_scope']}",
                    "",
                ]
            )
    else:
        lines.extend(["No candidate readiness records generated.", ""])

    lines.extend(["## Boundary Check", ""])
    for key, value in summary["boundary_check"].items():
        lines.append(f"- {key}: `{str(value).lower()}`")
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Task20i no-write guard readiness dry-run summary.")
    parser.add_argument("--input-root", type=Path, default=Path.cwd())
    parser.add_argument("--source", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=Path("results/task20i_no_write_guard_readiness"))
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
