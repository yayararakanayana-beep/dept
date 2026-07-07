#!/usr/bin/env python3
"""Run objective challenge validation and write measurement reports."""
from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd

from dept2_fullspec_runner_rc1.validation.dept_prediction_objective_challenge_validation import (
    PredictionObjectiveChallengeConfig,
    run_prediction_objective_challenge_validation,
)


def _parse_ints(value: str) -> tuple[int, ...]:
    return tuple(int(v.strip()) for v in value.split(",") if v.strip())


def _parse_floats(value: str) -> tuple[float, ...]:
    return tuple(float(v.strip()) for v in value.split(",") if v.strip())


def _parse_strings(value: str) -> tuple[str, ...]:
    return tuple(v.strip() for v in value.split(",") if v.strip())


def _show(df: pd.DataFrame, cols: list[str]) -> str:
    if df.empty:
        return "No rows."
    cols = [c for c in cols if c in df.columns]
    return df[cols].to_markdown(index=False)


def _write_report(outputs: dict[str, pd.DataFrame], out_dir: Path, cfg: PredictionObjectiveChallengeConfig) -> Path:
    report_path = out_dir / "prediction_objective_challenge_report.md"
    boundary = outputs["prediction_objective_challenge_boundary"]
    balanced = outputs["prediction_objective_challenge_balanced_accuracy"]
    comparison = outputs["prediction_objective_challenge_baseline_comparison"]
    worst = outputs["prediction_objective_challenge_worst_cases"]
    rows = outputs["prediction_objective_challenge_rows"]

    lines = [
        "# Prediction Objective Challenge Validation",
        "",
        "Measurement-only report. No performance pass/fail thresholds are defined here.",
        "",
        "## Boundary contract measurement",
        boundary.to_markdown(index=False) if not boundary.empty else "No boundary rows.",
        "",
        "## Configuration",
        f"- seeds: `{','.join(str(s) for s in cfg.seeds)}`",
        f"- patterns: `{','.join(cfg.patterns)}`",
        f"- noise_levels: `{','.join(str(n) for n in cfg.noise_levels)}`",
        f"- horizons: `{','.join(str(h) for h in cfg.horizons)}`",
        f"- history_steps: `{cfg.history_steps}`",
        f"- source_steps: `{cfg.source_steps}`",
        "",
        "## Balanced measurement by noise and horizon",
        _show(balanced, [
            "method", "noise_level", "horizon", "balanced_direction_match_rate",
            "min_pattern_direction_match_rate", "max_pattern_direction_match_rate",
            "mean_pattern_strength_abs_error", "max_pattern_strength_abs_error", "p95_pattern_strength_abs_error",
        ]),
        "",
        "## Baseline delta measurement",
        _show(comparison, [
            "baseline_method", "pattern", "noise_level", "horizon",
            "prediction_direction_match_rate", "baseline_direction_match_rate", "direction_match_lift",
            "prediction_mean_strength_abs_error", "baseline_mean_strength_abs_error", "mean_strength_error_delta_vs_baseline",
            "prediction_max_strength_abs_error", "baseline_max_strength_abs_error", "max_strength_error_delta_vs_baseline",
        ]),
        "",
        "## Worst observed cases",
        _show(worst, [
            "method", "pattern", "noise_level", "horizon", "direction_match_rate",
            "mean_strength_abs_error", "max_strength_abs_error", "p95_strength_abs_error",
        ]),
        "",
        "## Row counts",
        f"- validation rows: `{len(rows)}`",
        f"- balanced rows: `{len(balanced)}`",
        f"- comparison rows: `{len(comparison)}`",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default="artifacts/dept_prediction_objective_challenge")
    parser.add_argument("--seeds", default="101,202,303,404,505")
    parser.add_argument("--patterns", default="neutral,overconvergence,fixation,divergence")
    parser.add_argument("--noise-levels", default="0.0,0.02,0.05")
    parser.add_argument("--horizons", default="1,2,3,5")
    parser.add_argument("--history-steps", type=int, default=6)
    parser.add_argument("--source-steps", type=int, default=5)
    args = parser.parse_args()
    cfg = PredictionObjectiveChallengeConfig(
        seeds=_parse_ints(args.seeds),
        patterns=_parse_strings(args.patterns),
        noise_levels=_parse_floats(args.noise_levels),
        horizons=_parse_ints(args.horizons),
        history_steps=args.history_steps,
        source_steps=args.source_steps,
    )
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = run_prediction_objective_challenge_validation(cfg)
    for name, df in outputs.items():
        df.to_csv(out_dir / f"{name}.csv", index=False)
    print(f"wrote {_write_report(outputs, out_dir, cfg)}")
    print(outputs["prediction_objective_challenge_balanced_accuracy"].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
