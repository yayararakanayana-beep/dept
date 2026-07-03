#!/usr/bin/env python3
"""Phase 2G-18 observation-window export probe.

This validation-only probe inspects existing full-loop output directories and
confirms that Phase 2G-17 observation-window JSON/CSV exports are readable. It
never imports ActionModule code and never feeds observation-window output back
into runtime inputs.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Mapping

REQUIRED_WINDOWS = [
    "v2_direct_benefit_window",
    "h11_possibility_distribution_window",
    "pressure_action_alignment_window",
    "risk_band_window",
    "v2_direct_growth_window",
    "composite_balance_window",
]
REQUIRED_WINDOW_KEYS = {
    "window_name",
    "status_label",
    "evidence_fields",
    "warning_flags",
    "unresolved_flags",
    "short_reason",
}
DERIVED_CONTEXT_WINDOW_KEYS = REQUIRED_WINDOW_KEYS | {"derived_fields", "context_fields"}
ALLOWED_STATUS_LABELS = {"healthy", "watch", "warning", "critical", "unresolved"}
BOUNDARY_NOTE_SNIPPET = "not runtime ActionModule inputs"


def _load_json(path: Path) -> Mapping[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def validate_output_dir(output_dir: Path) -> dict[str, Any]:
    json_path = output_dir / "observation_window_summary.json"
    csv_path = output_dir / "observation_window_summary.csv"
    if not json_path.exists():
        raise FileNotFoundError(json_path)
    if not csv_path.exists():
        raise FileNotFoundError(csv_path)

    summary = _load_json(json_path)
    boundary_note = str(summary.get("boundary_note", ""))
    if BOUNDARY_NOTE_SNIPPET not in boundary_note:
        raise ValueError(f"{json_path} boundary_note does not preserve the ActionModule boundary")

    windows = summary.get("windows")
    if not isinstance(windows, list):
        raise ValueError(f"{json_path} windows must be a list")
    window_names = [window.get("window_name") for window in windows if isinstance(window, dict)]
    if window_names != REQUIRED_WINDOWS:
        raise ValueError(f"{json_path} window order/name mismatch: {window_names}")

    for window in windows:
        if not isinstance(window, dict):
            raise ValueError(f"{json_path} contains a non-object window")
        required_keys = DERIVED_CONTEXT_WINDOW_KEYS if window.get("window_name") in {"v2_direct_benefit_window", "v2_direct_growth_window"} else REQUIRED_WINDOW_KEYS
        if set(window) != required_keys:
            raise ValueError(f"{json_path} {window.get('window_name')} keys mismatch: {sorted(window)}")
        if window["status_label"] not in ALLOWED_STATUS_LABELS:
            raise ValueError(f"{json_path} {window['window_name']} invalid status_label: {window['status_label']}")
        for key in ["evidence_fields", "warning_flags", "unresolved_flags"]:
            if not isinstance(window[key], list):
                raise ValueError(f"{json_path} {window['window_name']} {key} must be a list")
        if not isinstance(window["short_reason"], str) or not window["short_reason"]:
            raise ValueError(f"{json_path} {window['window_name']} short_reason must be non-empty")

    with csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != len(REQUIRED_WINDOWS):
        raise ValueError(f"{csv_path} must contain {len(REQUIRED_WINDOWS)} data rows, found {len(rows)}")
    csv_window_names = [row.get("window_name") for row in rows]
    if csv_window_names != REQUIRED_WINDOWS:
        raise ValueError(f"{csv_path} window order/name mismatch: {csv_window_names}")
    for row in rows:
        if row.get("status_label") not in ALLOWED_STATUS_LABELS:
            raise ValueError(f"{csv_path} {row.get('window_name')} invalid status_label: {row.get('status_label')}")
        if BOUNDARY_NOTE_SNIPPET not in str(row.get("boundary_note", "")):
            raise ValueError(f"{csv_path} {row.get('window_name')} missing boundary note")

    return {
        "output_dir": str(output_dir),
        "label": summary.get("label", ""),
        "world_profile": summary.get("world_profile", ""),
        "statuses": {window["window_name"]: window["status_label"] for window in windows},
        "warning_flags": {window["window_name"]: window["warning_flags"] for window in windows},
        "unresolved_flags": {window["window_name"]: window["unresolved_flags"] for window in windows},
        "csv_rows": len(rows),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate Phase 2G-18 observation-window export readability.")
    parser.add_argument("output_dirs", nargs="+", type=Path, help="Full-loop output directories to inspect.")
    args = parser.parse_args()

    results = [validate_output_dir(path) for path in args.output_dirs]
    print(json.dumps({"passed": True, "checked_runs": results}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
