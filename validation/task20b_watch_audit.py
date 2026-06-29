#!/usr/bin/env python3
"""Minimal Task20b watch audit summary generator.

This script is intentionally read-only with respect to DEPT control paths. It scans
already-available repository results/docs/handoff files for Task17/Task18 watch
signals and writes a compact summary. It never expands the RC1 freeze archive.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable

WATCH_ITEMS = {
    "coactivation_dampen_zone": (
        "coactivation_dampen_zone",
        "coactivation dampen",
        "coactivation_gate",
        "dampen",
    ),
    "residual_noise_high": (
        "residual_noise_high",
        "residual noise high",
        "high noise",
        "residual growth",
    ),
    "shock_recovery_window": (
        "shock recovery window",
        "shock_recovery_window",
        "shock recovery",
    ),
    "noise_ledger_exploration_gate_relationship": (
        "no residual noise ledger signal",
        "noise ledger",
        "exploration projection",
        "exploration bridge projection",
        "coactivation gate modulation",
        "noise ledger / exploration / gate",
    ),
}

BOUNDARY_CHECK = {
    "canonical_write_enabled": False,
    "gk_writeback_enabled": False,
    "world_write_by_shadow_enabled": False,
    "parameter_update_implemented": False,
    "commit_gate_implemented": False,
    "action_module_reads_dept_internals": False,
    "watch_audit_is_controller": False,
}

TEXT_SUFFIXES = {".md", ".txt", ".csv", ".json"}


def _short_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _candidate_files(root: Path) -> tuple[list[Path], list[Path]]:
    """Return result files and supporting docs/handoff files without touching zips."""
    result_files: list[Path] = []
    results_dir = root / "results"
    if results_dir.exists():
        for path in results_dir.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            if "task20b_watch_audit" in path.parts:
                continue
            result_files.append(path)

    support_files: list[Path] = []
    docs_dir = root / "docs"
    if docs_dir.exists():
        support_files.extend(
            path for path in docs_dir.rglob("*") if path.is_file() and path.suffix.lower() in {".md", ".txt"}
        )
    handoff = root / "DEPT2_FullSpecIntegratedClosedLoopRunner_RC1_Handoff.md"
    if handoff.exists():
        support_files.append(handoff)

    return sorted(result_files), sorted(support_files)


def _flatten_json(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _flatten_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _flatten_json(child)


def _read_records(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() == ".csv":
        return [dict(row) for row in csv.DictReader(text.splitlines())]
    if path.suffix.lower() == ".json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return [{"text": line.strip()} for line in text.splitlines() if line.strip()]
        return list(_flatten_json(data)) or [{"text": text[:500]}]
    return [{"text": line.strip()} for line in text.splitlines() if line.strip()]


def _record_text(record: dict[str, Any]) -> str:
    return json.dumps(record, ensure_ascii=False, sort_keys=True).lower()


def _field(record: dict[str, Any], names: tuple[str, ...]) -> str | None:
    for name in names:
        value = record.get(name)
        if value is not None:
            return str(value)
    return None


def _matches_watch(watch_name: str, record_text: str) -> bool:
    terms = WATCH_ITEMS[watch_name]
    if any(term in record_text for term in terms):
        return True
    if watch_name == "coactivation_dampen_zone":
        return "coactivation" in record_text and "dampen" in record_text
    if watch_name == "residual_noise_high":
        return "residual" in record_text and "noise" in record_text and "high" in record_text
    if watch_name == "noise_ledger_exploration_gate_relationship":
        return "ledger" in record_text and "exploration" in record_text and "gate" in record_text
    return False


def _add_evidence(
    summary: dict[str, Any],
    watch_name: str,
    source: str,
    case: str | None = None,
    note: str | None = None,
) -> None:
    item = summary["watch_items"][watch_name]
    item["observed"] = True
    if source not in item["observed_in"]:
        item["observed_in"].append(source)
    if case and case not in item["cases"]:
        item["cases"].append(case)
    if note and note not in item["notes"] and len(item["notes"]) < 5:
        item["notes"].append(note[:240])


def _apply_summary_evidence(summary: dict[str, Any], result_files: list[Path], root: Path) -> None:
    """Derive watch evidence from compact Task17/Task18 RC1 summary CSVs."""
    for path in result_files:
        source = _short_path(path, root)
        name = path.name.lower()
        records = _read_records(path)
        if name == "fullspec_task17_stress_validation_summary_rc1.csv":
            for record in records:
                if str(record.get("pass_with_watch_count", "0")) != "0":
                    _add_evidence(
                        summary,
                        "residual_noise_high",
                        source,
                        "Task17_StressScenarioValidation_RC1",
                        "Task17 compact summary reports pass_with_watch_count and max_observed_noise_score.",
                    )
                    _add_evidence(
                        summary,
                        "coactivation_dampen_zone",
                        source,
                        "Task17_StressScenarioValidation_RC1",
                        "Task17 compact summary reports pass_with_watch_count and max_observed_coactivation_risk.",
                    )
                    _add_evidence(
                        summary,
                        "shock_recovery_window",
                        source,
                        "Task17_StressScenarioValidation_RC1",
                        "Task17 stress matrix summary is the compact evidence source for shock recovery watch review.",
                    )
        elif name == "fullspec_task18_ablation_summary_rc1.csv":
            for record in records:
                if str(record.get("pass_with_ablation_effect_count", "0")) != "0":
                    _add_evidence(
                        summary,
                        "noise_ledger_exploration_gate_relationship",
                        source,
                        "Task18_AblationValidation_RC1",
                        "Task18 compact summary reports pass_with_ablation_effect_count and ablation_effect_cases.",
                    )

def build_summary(input_root: Path) -> dict[str, Any]:
    input_root = input_root.resolve()
    result_files, support_files = _candidate_files(input_root)
    # Watch observations must come from extracted/committed result evidence, not
    # from design notes. Supporting docs are listed for context only.
    files_to_scan = result_files

    summary: dict[str, Any] = {
        "task": "Task20b watch audit",
        "scope": "minimal watch-item audit; read-only summary; not a controller",
        "missing_input": not result_files,
        "source_inputs": {
            "results": [_short_path(path, input_root) for path in result_files],
            "task17_stress": [
                _short_path(path, input_root) for path in result_files if "task17_stress_matrix" in path.parts
            ],
            "task18_ablation": [
                _short_path(path, input_root) for path in result_files if "task18_ablation_validation" in path.parts
            ],
            "supporting_docs": [_short_path(path, input_root) for path in support_files],
        },
        "watch_items": {},
        "boundary_check": dict(BOUNDARY_CHECK),
    }

    for watch_name in WATCH_ITEMS:
        summary["watch_items"][watch_name] = {
            "observed": False,
            "observed_in": [],
            "cases": [],
            "cycles": [],
            "notes": [],
        }

    for path in files_to_scan:
        for record in _read_records(path):
            text = _record_text(record)
            case_id = _field(record, ("case", "case_id", "scenario", "scenario_id", "name"))
            cycle_id = _field(record, ("cycle", "cycle_id", "step", "step_id", "tick"))
            note = _field(record, ("watch", "watch_item", "status", "summary", "text", "note"))
            for watch_name in WATCH_ITEMS:
                if not _matches_watch(watch_name, text):
                    continue
                item = summary["watch_items"][watch_name]
                item["observed"] = True
                source = _short_path(path, input_root)
                if source not in item["observed_in"]:
                    item["observed_in"].append(source)
                if case_id and case_id not in item["cases"]:
                    item["cases"].append(case_id)
                if cycle_id and cycle_id not in item["cycles"]:
                    item["cycles"].append(cycle_id)
                if note and len(item["notes"]) < 5:
                    item["notes"].append(note[:240])

    _apply_summary_evidence(summary, result_files, input_root)
    return summary


def write_summary(summary: dict[str, Any], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "watch_audit_summary.json"
    md_path = output_dir / "watch_audit_summary.md"

    json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    lines = [
        "# Task20b Watch Audit Summary",
        "",
        f"missing_input: `{str(summary['missing_input']).lower()}`",
        "",
        "## Watch Items",
        "",
    ]
    for name, item in summary["watch_items"].items():
        lines.extend(
            [
                f"### {name}",
                f"- observed: `{str(item['observed']).lower()}`",
                f"- observed_in: {', '.join(item['observed_in']) if item['observed_in'] else 'none'}",
                f"- cases: {', '.join(item['cases']) if item['cases'] else 'none'}",
                f"- cycles: {', '.join(item['cycles']) if item['cycles'] else 'none'}",
                "",
            ]
        )
    lines.extend([
        "## Boundary Check",
        "",
    ])
    for key, value in summary["boundary_check"].items():
        lines.append(f"- {key}: `{str(value).lower()}`")
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the minimal Task20b watch audit summary.")
    parser.add_argument("--input-root", type=Path, default=Path.cwd())
    parser.add_argument("--output-dir", type=Path, default=Path("results/task20b_watch_audit"))
    args = parser.parse_args()

    output_dir = args.output_dir
    if not output_dir.is_absolute():
        output_dir = args.input_root / output_dir

    summary = build_summary(args.input_root)
    json_path, md_path = write_summary(summary, output_dir)
    print(f"wrote {json_path}")
    print(f"wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
