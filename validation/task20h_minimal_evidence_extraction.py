#!/usr/bin/env python3
"""Task20H minimal evidence extraction.

Scans the frozen RC1 archive via zipfile and extracts only a small, bounded set
of non-runtime CSV/JSON/MD/TXT evidence files matching Task20G evidence gaps.
This is evidence-only: it does not migrate runtime code or implement gates.
"""
from __future__ import annotations

import argparse, json, re, shutil, zipfile
from pathlib import Path, PurePosixPath
from typing import Any

ARCHIVE = "DEPT2_FullSpecIntegratedClosedLoopRunner_RC1_Freeze.zip"
MAX_FILES = 10
MAX_SIZE = 200 * 1024
ALLOWED_EXT = {".csv", ".json", ".md", ".txt"}
DENY_PARTS = {"__pycache__", ".git"}

BOUNDARY_CHECK = {
    "canonical_write_enabled": False,
    "gk_writeback_enabled": False,
    "world_write_by_shadow_enabled": False,
    "parameter_update_implemented": False,
    "commit_gate_implemented": False,
    "rollback_gate_implemented": False,
    "action_module_reads_dept_internals": False,
    "evidence_extraction_is_controller": False,
}

CATEGORY_TERMS = {
    "coactivation_dampen_zone": [
        "coactivation", "dampen", "damping", "action candidate", "action_candidate",
        "shadow confirmation", "shadow_confirmation", "audit correlation", "audit_correlation",
    ],
    "residual_noise_high": [
        "residual noise", "residual_noise", "noise ledger", "noise_ledger", "sustained",
        "transient", "unresolved residual", "unresolved_residual", "carryover", "residual",
    ],
    "shock_recovery_window": [
        "shock onset", "shock_onset", "shock peak", "shock_peak", "recovery",
        "return-to-baseline", "return_to_baseline", "baseline", "stability window", "stability_window", "shock",
    ],
    "noise_ledger_exploration_gate_relationship": [
        "ablation", "delta vs baseline", "delta_vs_baseline", "noise ledger", "noise_ledger",
        "exploration", "projection", "coactivation gate", "coactivation_gate", "sidecar", "modulation",
    ],
}


def _short_path(path: Path, root: Path) -> str:
    try: return str(path.relative_to(root))
    except ValueError: return str(path)


def _empty_summary(root: Path, archive_path: Path, error: str | None = None) -> dict[str, Any]:
    return {
        "task": "Task20H minimal evidence extraction",
        "scope": "minimal evidence extraction only; no runtime migration; no gate implementation",
        "no_write": True,
        "archive": _short_path(archive_path, root),
        "max_files": MAX_FILES,
        "extracted_count": 0,
        "missing_input": error is not None,
        "input_error": error,
        "missing_categories": list(CATEGORY_TERMS),
        "boundary_check": dict(BOUNDARY_CHECK),
        "evidence_items": [],
    }


def _read_head(zf: zipfile.ZipFile, info: zipfile.ZipInfo, limit: int = 4096) -> str:
    try:
        with zf.open(info) as fh:
            return fh.read(limit).decode("utf-8", errors="ignore").lower()
    except Exception:
        return ""


def _candidate_match(text: str) -> tuple[str | None, str, int]:
    category_scores: dict[str, list[str]] = {}
    for category, terms in CATEGORY_TERMS.items():
        matches = [t for t in terms if t in text]
        if matches:
            category_scores[category] = matches
    if not category_scores:
        return None, "", 0

    # Prefer the stress-scenario category encoded in archive paths before falling
    # back to general term counts; many files mention shared words such as
    # exploration or gate.
    for category in CATEGORY_TERMS:
        if category in text:
            matches = category_scores[category]
            return category, ", ".join(matches[:5]), len(matches) + 10

    category, matches = max(category_scores.items(), key=lambda item: len(item[1]))
    return category, ", ".join(matches[:5]), len(matches)


def _safe_name(archive_name: str, index: int) -> str:
    name = PurePosixPath(archive_name).name
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name)
    return f"{index:02d}_{name}"


def build_evidence_index(input_root: Path, archive: Path | None = None, output_dir: Path | None = None, max_files: int = MAX_FILES) -> dict[str, Any]:
    root = input_root.resolve()
    archive_path = archive or root / ARCHIVE
    if not archive_path.is_absolute(): archive_path = root / archive_path
    output_dir = output_dir or root / "results/task20h_minimal_evidence"
    if not output_dir.is_absolute(): output_dir = root / output_dir
    extract_dir = output_dir / "extracted"
    if not archive_path.exists():
        return _empty_summary(root, archive_path, f"missing input: {archive_path}")

    items = []
    found: set[str] = set()
    with zipfile.ZipFile(archive_path) as zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        scored = []
        for info in infos:
            p = PurePosixPath(info.filename)
            if p.suffix.lower() not in ALLOWED_EXT or info.file_size > MAX_SIZE or any(part in DENY_PARTS for part in p.parts):
                continue
            if p.suffix.lower() == ".py":
                continue
            text = (info.filename + "\n" + _read_head(zf, info)).lower()
            cat, reason, score = _candidate_match(text)
            if cat and score:
                scored.append((0 if cat not in found else 1, -score, info.file_size, cat, reason, info))
        scored.sort(key=lambda x: (x[0], x[1], x[2], x[5].filename))
        if scored:
            extract_dir.mkdir(parents=True, exist_ok=True)
        selected = []
        used_paths: set[str] = set()
        for category in CATEGORY_TERMS:
            for row in scored:
                if row[3] == category and row[5].filename not in used_paths:
                    selected.append(row); used_paths.add(row[5].filename); break
        for row in scored:
            if len(selected) >= max_files:
                break
            if row[5].filename not in used_paths:
                selected.append(row); used_paths.add(row[5].filename)
        for _, _, _, cat, reason, info in selected[:max_files]:
            dest = extract_dir / _safe_name(info.filename, len(items)+1)
            with zf.open(info) as src, dest.open("wb") as out:
                shutil.copyfileobj(src, out)
            found.add(cat)
            items.append({
                "evidence_id": f"T20H-E{len(items)+1:02d}", "category": cat,
                "archive_path": info.filename, "extracted_path": _short_path(dest, root),
                "file_type": PurePosixPath(info.filename).suffix.lower(), "size_bytes": info.file_size,
                "matched_reason": reason or "matched category terms", "claim_scope": "evidence only",
            })
    return {
        "task": "Task20H minimal evidence extraction",
        "scope": "minimal evidence extraction only; no runtime migration; no gate implementation",
        "no_write": True, "archive": _short_path(archive_path, root), "max_files": max_files,
        "extracted_count": len(items), "missing_input": False, "input_error": None,
        "missing_categories": [c for c in CATEGORY_TERMS if c not in found],
        "boundary_check": dict(BOUNDARY_CHECK), "evidence_items": items,
    }


def write_evidence_index(summary: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    jp, mp = output_dir / "evidence_index.json", output_dir / "evidence_index.md"
    jp.write_text(json.dumps(summary, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    lines = ["# Task20H Minimal Evidence Extraction", "", f"no_write: `{str(summary['no_write']).lower()}`", f"extracted_count: `{summary['extracted_count']}`", "", "## Missing Categories"]
    lines += [f"- {c}" for c in summary.get("missing_categories", [])] or ["- none"]
    lines += ["", "## Evidence Items"]
    for item in summary.get("evidence_items", []):
        lines += [f"- `{item['evidence_id']}` `{item['category']}`: `{item['archive_path']}` -> `{item['extracted_path']}` ({item['size_bytes']} bytes)"]
    if not summary.get("evidence_items"): lines.append("No evidence files extracted.")
    lines += ["", "## Boundary Check"] + [f"- {k}: `{str(v).lower()}`" for k, v in summary["boundary_check"].items()]
    mp.write_text("\n".join(lines)+"\n", encoding="utf-8")
    return jp, mp


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-root", type=Path, default=Path.cwd())
    ap.add_argument("--archive", type=Path, default=None)
    ap.add_argument("--output-dir", type=Path, default=Path("results/task20h_minimal_evidence"))
    ap.add_argument("--max-files", type=int, default=MAX_FILES)
    args = ap.parse_args()
    out = args.output_dir if args.output_dir.is_absolute() else args.input_root / args.output_dir
    summary = build_evidence_index(args.input_root, args.archive, out, args.max_files)
    jp, mp = write_evidence_index(summary, out)
    print(f"wrote {jp}"); print(f"wrote {mp}")
    return 0

if __name__ == "__main__": raise SystemExit(main())
