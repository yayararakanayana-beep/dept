"""Public Task 3.2-4 challenge-corpus runner with generic schedule CSV output."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Mapping, Sequence

import task3_2_4_challenge_corpus as _core

_original_comparison_writer = _core.t2._write_comparison_csv


def _flexible_writer(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
        return
    if "outcome" in rows[0]:
        _original_comparison_writer(path, rows)
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(str(key))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))


_core.t2._write_comparison_csv = _flexible_writer

ChallengeError = _core.ChallengeError


def build_scenario(condition: str, seed: int, config: Mapping[str, Any]):
    if condition not in config["challenge"]["condition_groups"]:
        raise ChallengeError(f"unknown condition {condition}")
    return _core.build_scenario(condition, seed, config)


_core.build_scenario = build_scenario
generate = _core.generate
load_config = _core.load_config
validate = _core.validate
main = _core.main


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["ChallengeError", "build_scenario", "generate", "load_config", "validate", "main"]
