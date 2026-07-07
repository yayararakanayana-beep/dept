#!/usr/bin/env python3
"""Run objective challenge validation for the DEPT prediction module."""
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


def _write_report(outputs: dict[str, pd.DataFrame], out_dir: Path, cfg: PredictionObjectiveChallengeConfig) -> Path:
    rows = outputs["prediction_objective_challenge_rows"]
    method_summary = outputs["prediction_objective_challenge_method_summary"]
    balanced = outputs["prediction_objective_challenge_balanced_accuracy"]
    comparison = outputs["prediction_objective_challenge_baseline_comparison"]
    stability = outputs["prediction_objective_challenge_seed_stability"]
    distribution = outputs["prediction_objective_challenge_direction_distribution"]
    worst = outputs["prediction_objective_challenge_worst_cases"]
    boundary = outputs["prediction_objective_challenge_boundary"]
    report_path = out_dir / "prediction_objective_challenge_report.md"

    lines: list[str] = []
    lines.append("# Prediction Objective Challenge Validation")
    lines.append("")
    lines.append("## Boundary")
    lines.append("")
    if boundary.empty:
        lines.append("Boundary table was empty.")
    else:
        b = boundary.iloc[0]
        lines.append(f"- prediction_input_contract: `{b.get('prediction_input_contract', '')}`")
        lines.append(f"- future_usage: `{b.get('future_usage', '')}`")
        lines.append(f"- forbidden_v2_trace_keys_passed_to_prediction: `{bool(b.get('forbidden_v2_trace_keys_passed_to_prediction', True))}`")
        lines.append(f"- boundary_pass: **{'PASS' if bool(b.get('boundary_pass', False)) else 'FAIL'}**")
        lines.append(f"- direction_diversity_pass: **{'PASS' if bool(b.get('direction_diversity_pass', False)) else 'FAIL'}**")
        lines.append(f"- actual_directions_seen: `{b.get('actual_directions_seen', '')}`")
    lines.append("")
    lines.append("## Configuration")
    lines.append("")
    lines.append(f"- seeds: `{','.join(str(s) for s in cfg.seeds)}`")
    lines.append(f"- patterns: `{','.join(cfg.patterns)}`")
    lines.append(f"- noise_levels: `{','.join(str(n) for n in cfg.noise_levels)}`")
    lines.append(f"- horizons: `{','.join(str(h) for h in cfg.horizons)}`")
    lines.append(f"- history_steps: `{cfg.history_steps}`")
    lines.append(f"- source_steps: `{cfg.source_steps}`")
    lines.append(f"- direction_match_floor: `{cfg.direction_match_floor}`")
    lines.append(f"- balanced_direction_floor: `{cfg.balanced_direction_floor}`")
    lines.append(f"- strength_abs_error_ceiling: `{cfg.strength_abs_error_ceiling}`")
    lines.append("")
    lines.append("## Direction distribution")
    lines.append("")
    lines.append(distribution.to_markdown(index=False) if not distribution.empty else "No direction distribution rows were produced.")
    lines.append("")
    lines.append("## Balanced accuracy")
    lines.append("")
    if balanced.empty:
        lines.append("No balanced accuracy rows were produced.")
    else:
        cols = [
            "method",
            "noise_level",
            "horizon",
            "balanced_direction_match_rate",
            "worst_pattern_direction_match_rate",
            "mean_pattern_strength_abs_error",
            "worst_pattern_strength_abs_error",
            "balanced_direction_pass",
            "strength_error_pass",
        ]
        lines.append(balanced[cols].to_markdown(index=False))
    lines.append("")
    lines.append("## Method summary")
    lines.append("")
    if method_summary.empty:
        lines.append("No method summary rows were produced.")
    else:
        cols = [
            "method",
            "pattern",
            "noise_level",
            "horizon",
            "direction_match_rate",
            "mean_strength_abs_error",
            "max_strength_abs_error",
            "mean_predicted_strength",
            "mean_actual_strength",
            "rows",
            "seeds",
        ]
        lines.append(method_summary[cols].to_markdown(index=False))
    lines.append("")
    lines.append("## Baseline comparison")
    lines.append("")
    if comparison.empty:
        lines.append("No baseline comparison rows were produced.")
    else:
        cols = [
            "baseline_method",
            "pattern",
            "noise_level",
            "horizon",
            "prediction_direction_match_rate",
            "baseline_direction_match_rate",
            "direction_match_lift",
            "prediction_mean_strength_abs_error",
            "baseline_mean_strength_abs_error",
            "strength_error_reduction",
        ]
        lines.append(comparison[cols].to_markdown(index=False))
    lines.append("")
    lines.append("## Worst cases")
    lines.append("")
    if worst.empty:
        lines.append("No worst cases were produced.")
    else:
        cols = [
            "method",
            "pattern",
            "noise_level",
            "horizon",
            "direction_match_rate",
            "mean_strength_abs_error",
            "max_strength_abs_error",
        ]
        lines.append(worst[cols].to_markdown(index=False))
    lines.append("")
    lines.append("## Seed stability")
    lines.append("")
    if stability.empty:
        lines.append("No seed stability rows were produced.")
    else:
        cols = [
            "method",
            "pattern",
            "noise_level",
            "horizon",
            "mean_seed_direction_match_rate",
            "min_seed_direction_match_rate",
            "std_seed_direction_match_rate",
            "mean_seed_strength_abs_error",
            "max_seed_strength_abs_error",
            "seeds",
        ]
        lines.append(stability[cols].to_markdown(index=False))
    lines.append("")
    lines.append("## Row counts")
    lines.append("")
    lines.append(f"- validation rows: `{len(rows)}`")
    lines.append(f"- method summary rows: `{len(method_summary)}`")
    lines.append(f"- balanced rows: `{len(balanced)}`")
    lines.append(f"- comparison rows: `{len(comparison)}`")
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
    parser.add_argument("--direction-match-floor", type=float, default=0.70)
    parser.add_argument("--balanced-direction-floor", type=float, default=0.60)
    parser.add_argument("--strength-abs-error-ceiling", type=float, default=0.12)
    args = parser.parse_args()

    cfg = PredictionObjectiveChallengeConfig(
        seeds=_parse_ints(args.seeds),
        patterns=_parse_strings(args.patterns),
        noise_levels=_parse_floats(args.noise_levels),
        horizons=_parse_ints(args.horizons),
        history_steps=args.history_steps,
        source_steps=args.source_steps,
        direction_match_floor=args.direction_match_floor,
        balanced_direction_floor=args.balanced_direction_floor,
        strength_abs_error_ceiling=args.strength_abs_error_ceiling,
    )
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = run_prediction_objective_challenge_validation(cfg)
    for name, df in outputs.items():
        df.to_csv(out_dir / f"{name}.csv", index=False)
    report_path = _write_report(outputs, out_dir, cfg)
    print(f"wrote {report_path}")
    print(outputs["prediction_objective_challenge_balanced_accuracy"].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
