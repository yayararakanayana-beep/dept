#!/usr/bin/env python3
"""Run Prediction Module Full Validation Phase 1 and write reports."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from dept2_fullspec_runner_rc1.validation.dept_prediction_full_validation_phase1 import (
    PredictionFullValidationPhase1Config,
    run_prediction_full_validation_phase1,
)


def _parse_ints(value: str) -> tuple[int, ...]:
    return tuple(int(v.strip()) for v in value.split(",") if v.strip())


def _parse_strings(value: str) -> tuple[str, ...]:
    return tuple(v.strip() for v in value.split(",") if v.strip())


def _write_markdown(outputs: dict[str, pd.DataFrame], out_dir: Path, cfg: PredictionFullValidationPhase1Config) -> Path:
    rows = outputs["prediction_full_validation_phase1_rows"]
    method_summary = outputs["prediction_full_validation_phase1_method_summary"]
    seed_stability = outputs["prediction_full_validation_phase1_seed_stability"]
    comparison = outputs["prediction_full_validation_phase1_baseline_comparison"]
    usable = outputs["prediction_full_validation_phase1_usable_horizon"]
    boundary = outputs["prediction_full_validation_phase1_boundary"]
    report_path = out_dir / "prediction_full_validation_phase1_report.md"

    lines: list[str] = []
    lines.append("# Task2-8j-24d Prediction Module Full Validation Phase 1")
    lines.append("")
    lines.append("## Boundary")
    lines.append("")
    if boundary.empty:
        lines.append("Boundary table was empty.")
    else:
        b = boundary.iloc[0]
        lines.append(f"- prediction_input_contract: `{b.get('prediction_input_contract', '')}`")
        lines.append(f"- v2_future_usage: `{b.get('v2_future_usage', '')}`")
        lines.append(f"- forbidden_v2_trace_keys_passed_to_prediction: `{bool(b.get('forbidden_v2_trace_keys_passed_to_prediction', True))}`")
        lines.append(f"- boundary_pass: **{'PASS' if bool(b.get('boundary_pass', False)) else 'FAIL'}**")
    lines.append("")
    lines.append("## Configuration")
    lines.append("")
    lines.append(f"- seeds: `{','.join(str(s) for s in cfg.seeds)}`")
    lines.append(f"- profiles: `{','.join(cfg.profiles)}`")
    lines.append(f"- n_entities: `{cfg.n_entities}`")
    lines.append(f"- warmup_steps: `{cfg.warmup_steps}`")
    lines.append(f"- source_steps: `{cfg.source_steps}`")
    lines.append(f"- max_horizon: `{cfg.max_horizon}`")
    lines.append(f"- direction_match_floor: `{cfg.direction_match_floor}`")
    lines.append(f"- strength_abs_error_ceiling: `{cfg.strength_abs_error_ceiling}`")
    lines.append("")
    lines.append("## Method summary")
    lines.append("")
    if method_summary.empty:
        lines.append("No method summary rows were produced.")
    else:
        cols = [
            "method",
            "profile",
            "horizon",
            "direction_match_rate",
            "mean_strength_abs_error",
            "mean_predicted_strength",
            "mean_actual_strength",
            "usable_horizon_pass",
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
            "profile",
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
    lines.append("## Usable horizon by profile and method")
    lines.append("")
    if usable.empty:
        lines.append("No usable horizon rows were produced.")
    else:
        lines.append(usable.to_markdown(index=False))
    lines.append("")
    lines.append("## Seed stability")
    lines.append("")
    if seed_stability.empty:
        lines.append("No seed stability rows were produced.")
    else:
        cols = [
            "method",
            "profile",
            "horizon",
            "mean_seed_direction_match_rate",
            "min_seed_direction_match_rate",
            "max_seed_direction_match_rate",
            "std_seed_direction_match_rate",
            "mean_seed_strength_abs_error",
            "max_seed_strength_abs_error",
            "seeds",
        ]
        lines.append(seed_stability[cols].to_markdown(index=False))
    lines.append("")
    lines.append("## Row counts")
    lines.append("")
    lines.append(f"- validation rows: `{len(rows)}`")
    lines.append(f"- method summary rows: `{len(method_summary)}`")
    lines.append(f"- comparison rows: `{len(comparison)}`")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default="artifacts/dept_prediction_full_validation_phase1")
    parser.add_argument("--seeds", default="101,202,303,404,505")
    parser.add_argument("--profiles", default="pseudo_reality_v2_shrinking_equilibrium,pseudo_reality_v2_trust_collapse,pseudo_reality_v2_public_stability_hidden_decay")
    parser.add_argument("--n-entities", type=int, default=18)
    parser.add_argument("--warmup-steps", type=int, default=3)
    parser.add_argument("--source-steps", type=int, default=8)
    parser.add_argument("--max-horizon", type=int, default=5)
    parser.add_argument("--direction-match-floor", type=float, default=0.25)
    parser.add_argument("--strength-abs-error-ceiling", type=float, default=0.25)
    args = parser.parse_args()

    cfg = PredictionFullValidationPhase1Config(
        seeds=_parse_ints(args.seeds),
        profiles=_parse_strings(args.profiles),
        n_entities=args.n_entities,
        warmup_steps=args.warmup_steps,
        source_steps=args.source_steps,
        max_horizon=args.max_horizon,
        direction_match_floor=args.direction_match_floor,
        strength_abs_error_ceiling=args.strength_abs_error_ceiling,
    )
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    outputs = run_prediction_full_validation_phase1(cfg)
    for name, df in outputs.items():
        df.to_csv(out_dir / f"{name}.csv", index=False)
    report_path = _write_markdown(outputs, out_dir, cfg)
    print(f"wrote {report_path}")
    print(outputs["prediction_full_validation_phase1_method_summary"].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
