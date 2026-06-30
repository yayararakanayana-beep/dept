#!/usr/bin/env python3
"""Task20I readiness re-run with extracted evidence.

Reads Task20G readiness and Task20H extracted evidence summaries, then performs
a conservative no-write readiness re-run. This is not a commit gate and never
enables parameter updates.
"""
from __future__ import annotations

import argparse, json
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
    "readiness_rerun_is_controller": False,
}


def _short_path(path: Path, root: Path) -> str:
    try: return str(path.relative_to(root))
    except ValueError: return str(path)


def _load_json(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.exists(): return None, f"missing input: {path}"
    try: data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc: return None, f"invalid json: {path}: {exc}"
    return (data, None) if isinstance(data, dict) else (None, f"invalid input: {path}: expected a JSON object")


def build_rerun_summary(input_root: Path, readiness: Path | None = None, evidence: Path | None = None) -> dict[str, Any]:
    root = input_root.resolve()
    readiness_path = readiness or root / "results/task20g_pre_commit_readiness/readiness_summary.json"
    evidence_path = evidence or root / "results/task20h_minimal_evidence/evidence_index.json"
    if not readiness_path.is_absolute(): readiness_path = root / readiness_path
    if not evidence_path.is_absolute(): evidence_path = root / evidence_path
    readiness_data, readiness_error = _load_json(readiness_path)
    evidence_data, evidence_error = _load_json(evidence_path)
    evidence_items = evidence_data.get("evidence_items", []) if evidence_data else []
    by_category: dict[str, list[dict[str, Any]]] = {}
    for item in evidence_items:
        if isinstance(item, dict): by_category.setdefault(str(item.get("category")), []).append(item)

    candidates = []
    for candidate in (readiness_data or {}).get("candidate_readiness", []):
        if not isinstance(candidate, dict): continue
        category = str(candidate.get("source_watch_item", ""))
        found = by_category.get(category, [])
        prev_missing = candidate.get("next_required_evidence", []) or []
        evidence_missing = list(prev_missing)
        reason = "additional extracted evidence is absent or still too compact for gate readiness"
        if found:
            reason = "minimal extracted evidence was found, but conservative re-run still requires reviewed category-complete source rows and boundary evidence"
        candidates.append({
            "proposal_id": candidate.get("proposal_id"),
            "source_watch_item": candidate.get("source_watch_item"),
            "previous_gate_ready": bool(candidate.get("gate_ready", False)),
            "new_gate_ready": False,
            "readiness": "needs_more_evidence",
            "evidence_found": [i.get("evidence_id") for i in found],
            "evidence_missing": evidence_missing,
            "reason": reason,
            "claim_scope": "readiness re-run only",
        })
    return {
        "task": "Task20I readiness re-run with extracted evidence",
        "scope": "read-only readiness re-run; not a commit gate; no parameter update",
        "no_write": True,
        "gate_ready_overall": False,
        "source_readiness": _short_path(readiness_path, root),
        "source_evidence_index": _short_path(evidence_path, root),
        "missing_input": readiness_error is not None or evidence_error is not None,
        "input_errors": [e for e in [readiness_error, evidence_error] if e],
        "boundary_check": dict(BOUNDARY_CHECK),
        "candidate_readiness": candidates,
    }


def write_rerun_summary(summary: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    jp, mp = output_dir / "readiness_rerun_summary.json", output_dir / "readiness_rerun_summary.md"
    jp.write_text(json.dumps(summary, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    lines = ["# Task20I Readiness Re-run With Extracted Evidence", "", f"no_write: `{str(summary['no_write']).lower()}`", f"gate_ready_overall: `{str(summary['gate_ready_overall']).lower()}`", "", "## Candidate Readiness"]
    for c in summary.get("candidate_readiness", []):
        lines += [f"### {c['proposal_id']}", f"- source_watch_item: `{c['source_watch_item']}`", f"- new_gate_ready: `{str(c['new_gate_ready']).lower()}`", f"- readiness: `{c['readiness']}`", f"- evidence_found: {', '.join(c['evidence_found']) if c['evidence_found'] else 'none'}", f"- reason: {c['reason']}", ""]
    if not summary.get("candidate_readiness"): lines.append("No candidate readiness entries generated.\n")
    lines += ["## Boundary Check"] + [f"- {k}: `{str(v).lower()}`" for k, v in summary["boundary_check"].items()]
    mp.write_text("\n".join(lines)+"\n", encoding="utf-8")
    return jp, mp


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-root", type=Path, default=Path.cwd())
    ap.add_argument("--readiness", type=Path, default=None)
    ap.add_argument("--evidence", type=Path, default=None)
    ap.add_argument("--output-dir", type=Path, default=Path("results/task20i_readiness_rerun"))
    args = ap.parse_args()
    out = args.output_dir if args.output_dir.is_absolute() else args.input_root / args.output_dir
    summary = build_rerun_summary(args.input_root, args.readiness, args.evidence)
    jp, mp = write_rerun_summary(summary, out)
    print(f"wrote {jp}"); print(f"wrote {mp}")
    return 0

if __name__ == "__main__": raise SystemExit(main())
