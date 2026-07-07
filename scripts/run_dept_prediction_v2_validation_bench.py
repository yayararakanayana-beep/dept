#!/usr/bin/env python3
"""Run the v2 heldout validation bench and write CSV/Markdown reports."""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from dept2_fullspec_runner_rc1.validation.dept_prediction_v2_validation_bench import (
    V2PredictionBenchConfig,
    run_v2_prediction_validation_bench,
)


def _format_bool(value) -> str:
    return "PASS" if bool(value) else "FAIL"


def _write_markdown(outputs: dict[str, pd.DataFrame], out_dir: Path, cfg: V2PredictionBenchConfig) -> Path:
    rows = outputs["v2_prediction_validation_rows"]
    summary = outputs["v2_prediction_validation_summary"]
    boundary = outputs["v2_prediction_validation_boundary"]
    report_path = out_dir / "v2_prediction_validation_report.md"

    lines: list[str] = []
    lines.append("# DEPT Prediction v2 Heldout Validation Report")
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
        lines.append(f"- boundary_pass: **{_format_bool(b.get('boundary_pass', False))}**")
    lines.append("")
    lines.append("## Configuration")
    lines.append("")
    lines.append(f"- seed: `{cfg.seed}`")
    lines.append(f"- n_entities: `{cfg.n_entities}`")
    lines.append(f"- warmup_steps: `{cfg.warmup_steps}`")
    lines.append(f"- source_steps: `{cfg.source_steps}`")
    lines.append(f"- max_horizon: `{cfg.max_horizon}`")
    lines.append(f"- direction_match_floor: `{cfg.direction_match_floor}`")
    lines.append(f"- strength_abs_error_ceiling: `{cfg.strength_abs_error_ceiling}`")
    lines.append("")
    lines.append("## Horizon summary")
    lines.append("")
    if summary.empty:
        lines.append("No summary rows were produced.")
    else:
        display_cols = [
            "profile",
            "horizon",
            "direction_match_rate",
            "mean_strength_abs_error",
            "max_strength_abs_error",
            "mean_predicted_dynamics_strength",
            "mean_actual_dynamics_strength",
            "direction_floor_pass",
            "strength_error_pass",
        ]
        lines.append(summary[display_cols].to_markdown(index=False))
    lines.append("")
    lines.append("## Usable horizon by profile")
    lines.append("")
    if summary.empty:
        lines.append("No usable horizon could be computed.")
    else:
        usable_rows = []
        for profile, group in summary.groupby("profile"):
            usable = group[group["direction_floor_pass"] & group["strength_error_pass"]]
            usable_horizon = int(usable["horizon"].max()) if not usable.empty else 0
            usable_rows.append({
                "profile": profile,
                "usable_horizon": usable_horizon,
                "tested_horizons": ",".join(str(int(h)) for h in sorted(group["horizon"].unique())),
            })
        lines.append(pd.DataFrame(usable_rows).to_markdown(index=False))
    lines.append("")
    lines.append("## Row counts")
    lines.append("")
    lines.append(f"- validation rows: `{len(rows)}`")
    lines.append(f"- summary rows: `{len(summary)}`")
    lines.append("")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default="artifacts/dept_prediction_v2_validation", help="Output directory for reports")
    parser.add_argument("--seed", type=int, default=202)
    parser.add_argument("--n-entities", type=int, default=18)
    parser.add_argument("--warmup-steps", type=int, default=3)
    parser.add_argument("--source-steps", type=int, default=6)
    parser.add_argument("--max-horizon", type=int, default=5)
    parser.add_argument("--direction-match-floor", type=float, default=0.25)
    parser.add_argument("--strength-abs-error-ceiling", type=float, default=0.25)
    args = parser.parse_args()

    cfg = V2PredictionBenchConfig(
        seed=args.seed,
        n_entities=args.n_entities,
        warmup_steps=args.warmup_steps,
        source_steps=args.source_steps,
        max_horizon=args.max_horizon,
        direction_match_floor=args.direction_match_floor,
        strength_abs_error_ceiling=args.strength_abs_error_ceiling,
    )
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    outputs = run_v2_prediction_validation_bench(cfg)
    for name, df in outputs.items():
        df.to_csv(out_dir / f"{name}.csv", index=False)
    report_path = _write_markdown(outputs, out_dir, cfg)
    print(f"wrote {report_path}")
    print(outputs["v2_prediction_validation_summary"].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
