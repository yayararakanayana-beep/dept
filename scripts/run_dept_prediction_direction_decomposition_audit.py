#!/usr/bin/env python3
"""Run prediction direction decomposition audit and write measurement reports."""
from __future__ import annotations

import argparse
from pathlib import Path
import pandas as pd

from dept2_fullspec_runner_rc1.validation.dept_prediction_direction_decomposition_audit import (
    PredictionDirectionDecompositionAuditConfig,
    run_prediction_direction_decomposition_audit,
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


def _write_report(outputs: dict[str, pd.DataFrame], out_dir: Path, cfg: PredictionDirectionDecompositionAuditConfig) -> Path:
    report_path = out_dir / "prediction_direction_decomposition_audit_report.md"
    rows = outputs["prediction_direction_decomposition_rows"]
    group = outputs["prediction_direction_decomposition_group_summary"]
    confusion = outputs["prediction_direction_decomposition_confusion"]
    component = outputs["prediction_direction_decomposition_component_summary"]
    boundary = outputs["prediction_direction_decomposition_boundary"]

    lines = [
        "# Task2-8j-24e Prediction Direction Decomposition Audit",
        "",
        "Measurement-only report. This audit explains direction components and does not change prediction behavior.",
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
        "## Direction confusion measurement",
        _show(confusion, [
            "actual_direction", "predicted_direction", "rows", "mean_strength_abs_error", "max_strength_abs_error",
            "mean_neutral_buffer_distance", "mean_shrink_equilibrium_measure",
            "mean_bias_concentration_measure", "mean_divergence_release_measure",
        ]),
        "",
        "## Component summary by actual direction",
        _show(component, [
            "actual_direction", "pattern", "rows", "direction_match_rate",
            "mean_predicted_overconvergence_strength", "mean_predicted_fixation_strength", "mean_predicted_divergence_strength",
            "mean_neutral_buffer_distance", "mean_shrink_equilibrium_measure", "mean_bias_concentration_measure", "mean_divergence_release_measure",
            "mean_relation_lock_delta", "mean_relation_rigidity_delta", "mean_flow_delta",
            "mean_exploration_delta", "mean_uncertainty_delta", "mean_volatility_delta",
        ]),
        "",
        "## Group summary",
        _show(group, [
            "actual_direction", "predicted_direction", "pattern", "noise_level", "horizon", "rows", "direction_match_rate",
            "mean_neutral_buffer_distance", "mean_shrink_equilibrium_measure", "mean_bias_concentration_measure", "mean_divergence_release_measure",
            "mean_predicted_overconvergence_strength", "mean_predicted_fixation_strength", "mean_predicted_divergence_strength", "mean_predicted_direction_margin",
        ]),
        "",
        "## Row counts",
        f"- audit rows: `{len(rows)}`",
        f"- group rows: `{len(group)}`",
        f"- confusion rows: `{len(confusion)}`",
        f"- component rows: `{len(component)}`",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default="artifacts/dept_prediction_direction_decomposition_audit")
    parser.add_argument("--seeds", default="101,202,303,404,505")
    parser.add_argument("--patterns", default="neutral,overconvergence,fixation,divergence")
    parser.add_argument("--noise-levels", default="0.0,0.02,0.05")
    parser.add_argument("--horizons", default="1,2,3,5")
    parser.add_argument("--history-steps", type=int, default=6)
    parser.add_argument("--source-steps", type=int, default=5)
    args = parser.parse_args()
    cfg = PredictionDirectionDecompositionAuditConfig(
        seeds=_parse_ints(args.seeds),
        patterns=_parse_strings(args.patterns),
        noise_levels=_parse_floats(args.noise_levels),
        horizons=_parse_ints(args.horizons),
        history_steps=args.history_steps,
        source_steps=args.source_steps,
    )
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs = run_prediction_direction_decomposition_audit(cfg)
    for name, df in outputs.items():
        df.to_csv(out_dir / f"{name}.csv", index=False)
    print(f"wrote {_write_report(outputs, out_dir, cfg)}")
    print(outputs["prediction_direction_decomposition_confusion"].to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
