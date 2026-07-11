"""Calibrate Task 3.2-2 provisional outcomes against same-seed stable trajectories.

PseudoReality v3.3 has a natural baseline drift even with zero external input.
This post-processing stage removes that drift by comparing each trajectory with
``stable_continuation`` for the same seed. The resulting labels remain
exploratory diagnostics, not frozen risk definitions or game structures.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import task3_2_2_continuous_trajectory as trajectory  # noqa: E402
from task3_2_1_macro_dynamics_contract import load_contract  # noqa: E402

DEFAULT_CALIBRATION_CONFIG = ROOT / "configs" / "task3_2_2_reference_calibration.json"


class CalibrationError(ValueError):
    """Raised when stable-reference calibration cannot be completed."""


def load_calibration_config(path: str | Path = DEFAULT_CALIBRATION_CONFIG) -> dict[str, Any]:
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    if config.get("stable_reference_scenario") != "stable_continuation":
        raise CalibrationError("stable_reference_scenario must remain stable_continuation")
    rules = config.get("rules")
    if not isinstance(rules, dict):
        raise CalibrationError("calibration rules must be an object")
    required = {
        "baseline_steps",
        "tail_steps",
        "elevated_relative_risk_delta",
        "sustained_steps",
        "full_recovery_tolerance",
        "minimum_peak_elevation",
        "recovery_fraction",
        "fixation_concentration_ratio",
        "fixation_mobility_ratio",
        "fixation_rigidity_delta",
        "collapse_absolute_risk_score",
        "collapse_relative_risk_delta",
    }
    missing = sorted(required - set(rules))
    if missing:
        raise CalibrationError(f"calibration rules missing {missing}")
    return config


def _first_sustained(values: Sequence[float], threshold: float, length: int) -> int | None:
    run = 0
    for index, value in enumerate(values):
        run = run + 1 if value >= threshold else 0
        if run >= length:
            return index - length + 1
    return None


def _safe_ratio(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    return numerator / np.maximum(denominator, 1e-12)


def analyse_relative_outcome(
    metrics: Sequence[Mapping[str, float]],
    reference_metrics: Sequence[Mapping[str, float]],
    rules: Mapping[str, Any],
) -> dict[str, Any]:
    if len(metrics) != len(reference_metrics) or not metrics:
        raise CalibrationError("trajectory and stable reference must have equal non-zero length")

    absolute_risk = np.asarray([row["risk_score"] for row in metrics], dtype=np.float64)
    reference_risk = np.asarray([row["risk_score"] for row in reference_metrics], dtype=np.float64)
    relative_risk = absolute_risk - reference_risk
    concentration = np.asarray([row["concentration"] for row in metrics], dtype=np.float64)
    reference_concentration = np.asarray(
        [row["concentration"] for row in reference_metrics], dtype=np.float64
    )
    mobility = np.asarray([row["moved_mass"] for row in metrics], dtype=np.float64)
    reference_mobility = np.asarray([row["moved_mass"] for row in reference_metrics], dtype=np.float64)
    rigidity = np.asarray([row["weighted_rigidity"] for row in metrics], dtype=np.float64)
    reference_rigidity = np.asarray(
        [row["weighted_rigidity"] for row in reference_metrics], dtype=np.float64
    )

    baseline_count = min(int(rules["baseline_steps"]), len(metrics))
    tail_count = min(int(rules["tail_steps"]), len(metrics))
    relative_baseline = float(np.mean(relative_risk[:baseline_count]))
    relative_tail = float(np.mean(relative_risk[-tail_count:]))
    absolute_baseline = float(np.mean(absolute_risk[:baseline_count]))
    absolute_tail = float(np.mean(absolute_risk[-tail_count:]))
    reference_tail = float(np.mean(reference_risk[-tail_count:]))
    peak_step = int(np.argmax(relative_risk))
    peak_relative = float(relative_risk[peak_step])
    peak_absolute = float(absolute_risk[peak_step])
    peak_elevation = peak_relative - relative_baseline
    elevated_delta = float(rules["elevated_relative_risk_delta"])
    onset = _first_sustained(
        relative_risk.tolist(),
        relative_baseline + elevated_delta,
        int(rules["sustained_steps"]),
    )

    recovery_step: int | None = None
    for step in range(peak_step, len(relative_risk)):
        if relative_risk[step] <= relative_baseline + float(rules["full_recovery_tolerance"]):
            recovery_step = step
            break
    recovery_duration = None if recovery_step is None else recovery_step - peak_step
    if peak_elevation > 1e-12:
        recovered_fraction = float(np.clip((peak_relative - relative_tail) / peak_elevation, -1.0, 1.0))
    else:
        recovered_fraction = 0.0

    concentration_ratio = float(
        np.mean(_safe_ratio(concentration[-tail_count:], reference_concentration[-tail_count:]))
    )
    mobility_ratio = float(np.mean(_safe_ratio(mobility[-tail_count:], reference_mobility[-tail_count:])))
    rigidity_delta = float(np.mean((rigidity - reference_rigidity)[-tail_count:]))

    collapse = (
        absolute_tail >= float(rules["collapse_absolute_risk_score"])
        and relative_tail >= float(rules["collapse_relative_risk_delta"])
    )
    fixation = (
        concentration_ratio >= float(rules["fixation_concentration_ratio"])
        and mobility_ratio <= float(rules["fixation_mobility_ratio"])
        and rigidity_delta >= float(rules["fixation_rigidity_delta"])
    )
    minimum_peak = float(rules["minimum_peak_elevation"])
    recovery_fraction_gate = float(rules["recovery_fraction"])
    recovered_to_reference = recovery_step is not None and peak_elevation >= minimum_peak

    if collapse:
        event = "collapse"
        coarse = "collapse_or_divergence_candidate"
        recovery_outcome = "no_natural_recovery"
    elif fixation:
        event = "fixation"
        coarse = "fixation_candidate"
        recovery_outcome = "no_natural_recovery"
    elif recovered_to_reference:
        event = "none"
        coarse = "natural_recovery"
        recovery_outcome = "natural_recovery"
    elif peak_elevation >= minimum_peak and recovered_fraction >= recovery_fraction_gate:
        event = "delayed_recovery"
        coarse = "delayed_recovery"
        recovery_outcome = "delayed_natural_recovery"
    elif relative_tail >= relative_baseline + elevated_delta:
        event = "persistent_deterioration"
        coarse = "persistent_deterioration"
        recovery_outcome = "no_natural_recovery"
    else:
        event = "none"
        coarse = "stable"
        recovery_outcome = "not_evaluated"

    elevated = relative_risk >= relative_baseline + elevated_delta
    relative_diff = np.diff(relative_risk)
    risk_depth = {
        "return_time_steps": recovery_duration,
        "minimum_effective_action_strength": None,
        "recovery_probability": None,
        "hazard_persistence_steps": int(np.sum(elevated)),
        "deterioration_rate": float(np.max(relative_diff)) if len(relative_diff) else 0.0,
        "distance_from_safe_reference": float(max(0.0, relative_tail - relative_baseline)),
        "available_recovery_route_count": None,
        "relapse_probability": None,
    }
    return {
        "coarse_outcome": coarse,
        "future_risk_event": event,
        "risk_onset_step": onset,
        "recovery_outcome": recovery_outcome,
        "recovery_time_steps": recovery_duration,
        "irreversibility_level": 0 if recovery_outcome == "natural_recovery" else None,
        "boundary_crossing_step": None,
        "risk_depth": risk_depth,
        "baseline_risk_score": absolute_baseline,
        "tail_risk_score": absolute_tail,
        "peak_risk_score": peak_absolute,
        "peak_risk_step": peak_step,
        "reference_tail_risk_score": reference_tail,
        "relative_baseline_risk_delta": relative_baseline,
        "relative_tail_risk_delta": relative_tail,
        "peak_relative_risk_delta": peak_relative,
        "peak_elevation": peak_elevation,
        "recovered_fraction": recovered_fraction,
        "concentration_ratio": concentration_ratio,
        "mobility_ratio": mobility_ratio,
        "rigidity_delta": rigidity_delta,
        "label_is_provisional": True,
        "label_source": "measured_trajectory_relative_to_same_seed_stable_reference",
    }


def calibrate_corpus(
    input_dir: str | Path,
    generation_config_path: str | Path = trajectory.DEFAULT_CONFIG,
    calibration_config_path: str | Path = DEFAULT_CALIBRATION_CONFIG,
) -> dict[str, Any]:
    root = Path(input_dir)
    generation_config = trajectory.load_generation_config(generation_config_path)
    calibration_config = load_calibration_config(calibration_config_path)
    contract = load_contract(ROOT / generation_config["contract_path"])
    corpus_summary = trajectory._json_load(root / "corpus_summary.json")
    summaries = list(corpus_summary["summaries"])
    reference_name = calibration_config["stable_reference_scenario"]

    references: dict[int, list[dict[str, Any]]] = {}
    for summary in summaries:
        if summary["scenario_id"] == reference_name:
            trajectory_dir = root / "trajectories" / summary["trajectory_id"]
            references[int(summary["seed"])] = trajectory._read_jsonl(trajectory_dir / "metrics.jsonl")
    required_seeds = {int(summary["seed"]) for summary in summaries}
    if set(references) != required_seeds:
        raise CalibrationError("each seed requires one stable_continuation reference trajectory")

    calibrated: list[dict[str, Any]] = []
    for summary in summaries:
        trajectory_dir = root / "trajectories" / summary["trajectory_id"]
        metrics = trajectory._read_jsonl(trajectory_dir / "metrics.jsonl")
        outcome = analyse_relative_outcome(
            metrics,
            references[int(summary["seed"])],
            calibration_config["rules"],
        )
        summary = dict(summary)
        summary["outcome"] = outcome
        summary["calibration"] = {
            "method": calibration_config["comparison"],
            "reference_scenario": reference_name,
            "reference_seed": int(summary["seed"]),
        }
        trajectory._json_dump(trajectory_dir / "summary.json", summary)
        truth_rows = trajectory._truth_rows(
            str(summary["trajectory_id"]),
            int(summary["transitions"]),
            outcome,
        )
        trajectory._write_jsonl(trajectory_dir / "truth.jsonl", truth_rows)
        trajectory._write_trajectory_svg(
            trajectory_dir / "trajectory.svg",
            f"{summary['trajectory_id']}: {outcome['coarse_outcome']}",
            metrics,
        )
        validation = trajectory.validate_trajectory_directory(
            trajectory_dir,
            contract,
            generation_config,
        )
        validation["stable_reference_calibration"] = "passed"
        trajectory._json_dump(trajectory_dir / "validation.json", validation)
        calibrated.append(summary)

    outcome_counts: dict[str, int] = {}
    for summary in calibrated:
        label = str(summary["outcome"]["coarse_outcome"])
        outcome_counts[label] = outcome_counts.get(label, 0) + 1
    corpus_summary["summaries"] = calibrated
    corpus_summary["outcome_counts"] = outcome_counts
    corpus_summary["calibration"] = {
        "status": "passed",
        "method": calibration_config["comparison"],
        "stable_reference_scenario": reference_name,
        "labels_are_provisional": True,
    }
    trajectory._json_dump(root / "corpus_summary.json", corpus_summary)
    trajectory._write_comparison_csv(root / "scenario_comparison.csv", calibrated)
    trajectory._write_overview_svg(root / "trajectory_overview.svg", calibrated)
    corpus_validation = trajectory.validate_corpus(root, contract, generation_config)
    corpus_validation["stable_reference_calibration"] = "passed"
    corpus_validation["stable_reference_seed_count"] = len(references)
    trajectory._json_dump(root / "validation.json", corpus_validation)
    manifest = trajectory._write_manifest(root)
    return {
        "trajectory_count": len(calibrated),
        "outcome_counts": outcome_counts,
        "validation": corpus_validation,
        "manifest": {
            "file_count": manifest["file_count"],
            "total_size_bytes": manifest["total_size_bytes"],
        },
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--generation-config", default=str(trajectory.DEFAULT_CONFIG))
    parser.add_argument("--calibration-config", default=str(DEFAULT_CALIBRATION_CONFIG))
    args = parser.parse_args(argv)
    result = calibrate_corpus(args.input, args.generation_config, args.calibration_config)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CalibrationError",
    "DEFAULT_CALIBRATION_CONFIG",
    "analyse_relative_outcome",
    "calibrate_corpus",
    "load_calibration_config",
]
