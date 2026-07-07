#!/usr/bin/env python3
"""Run Prediction Module Full Validation Phase 1 and write measurement reports."""
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


def _table(df: pd.DataFrame, cols: list[str]) -> str:
    if df.empty:
        return "No rows."
    return df[[c for c in cols if c in df.columns]].to_markdown(index=False)


def _write_markdown(outputs: dict[str, pd.DataFrame], out_dir: Path, cfg: PredictionFullValidationPhase1Config) -> Path:
    report_path = out_dir / "prediction_full_validation_phase1_report.md"
    rows = outputs["prediction_full_validation_phase1_rows"]
    method_summary = outputs["prediction_full_validation_phase1_method_summary"]
    comparison = outputs["prediction_full_validation_phase1_baseline_comparison"]
    seed_stability = outputs["prediction_full_validation_phase1_seed_stability"]
    horizon = outputs["prediction_full_validation_phase1_horizon_measurement"]
    boundary = outputs["prediction_full_validation_phase1_boundary"]

    lines: list[str] = [
        "# Task2-8j-24d Prediction Module Full Validation Phase 1",
        "",
        "This report is measurement-only. It does not define performance pass/fail thresholds.",
        "",
        "## Boundary contract measurement",
        "",
        boundary.to_markdown(index=False) if not boundary.empty else "No boundary rows.",
        "",
        "## Configuration",
        "",
        f"- seeds: `{','.join(str(s) for s in cfg.seeds)}`",
        f"- profiles: `{','.join(cfg.profiles)}`",
        f"- n_entities: `{cfg.n_entities}`",
        f"- warmup_steps: `{cfg.warmup_steps}`",
        f"- source_steps: `{cfg.source_steps}`",
        f"- max_horizon: `{cfg.max_horizon}`",
        "",
        "## Method measurement summary",
        "",
        _table(method_summary, [
            "method", "profile", "horizon", "direction_match_rate",
            "mean_strength_abs_error", "max_strength_abs_error", "p95_strength_abs_error",
            "mean_predicted_strength", "mean_actual_strength", "rows", "seeds",
        ]),
        "",
        "## Baseline delta measurement",
        "",
        _table(comparison, [
            "baseline_method", "profile", "horizon",
            "prediction_direction_match_rate", "baseline_direction_match_rate", "direction_match_lift",
            "prediction_mean_strength_abs_error", "baseline_mean_strength_abs_error", "mean_strength_error_delta_vs_baseline",
            "prediction_max_strength_abs_error", "baseline_max_strength_abs_error", "max_strength_error_delta_vs_baseline",
            "prediction_p95_strength_abs_error", "baseline_p95_strength_abs_error", "p95_strength_error_delta_vs_baseline",
        ]),
        "",
        "## Horizon measurement",
        "",
        horizon.to_markdown(index=False) if not horizon.empty else "No horizon rows.",
        "",
        "## Seed stability measurement",
        "",
        _table(seed_stability, [
            "method", "profile", "horizon", "mean_seed_direction_match_rate",
            "min_seed_direction_match_rate", "max_seed_direction_match_rate", "std_seed_direction_match_rate",
            "mean_seed_strength_abs_error", "max_seed_strength_abs_error", "worst_seed_max_strength_abs_error", "seeds",
        ]),
        "",
        "## Row counts",
        "",
        f"- validation rows: `{len(rows)}`",
        f"- method summary rows: `{len(method_summary)}`",
        f"- comparison rows: `{len(comparison)}`",
    ]
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
    args = parser.parse_args()
    cfg = PredictionFullValidationPhase1Config(
        seeds=_parse_ints(args.seeds),
        profiles=_parse_strings(args.profiles),
        n_entities=args.n_entities,
        warmup_steps=args.warmup_steps,
        source_steps=args.source_steps,
        max_horizon=args.max_horizon,
    )
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = run_prediction_full_validation_phase1(cfg)
    for name, df in outputs.items():
        df.to_csv(out_dir / f"{name}.csv", index=False)
    print(f"wrote {_write_markdown(outputs, out_dir, cfg)}")
    print(outputs["prediction_full_validation_phase1_method_summary"].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
