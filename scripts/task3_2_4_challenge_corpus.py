"""Generate Task 3.2-4 challenge trajectories with seed-varying schedules."""
from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import task3_2_2_continuous_trajectory as t2  # noqa: E402
from task3_2_1_macro_dynamics_contract import load_contract  # noqa: E402

DEFAULT_CONFIG = ROOT / "configs" / "task3_2_4_macro_dynamics.json"
EXTERNAL_FIELDS = tuple(t2.EXTERNAL_FIELDS)


class ChallengeError(ValueError):
    pass


def load_config(path: str | Path = DEFAULT_CONFIG) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    challenge = value.get("challenge")
    if not isinstance(challenge, dict):
        raise ChallengeError("challenge config missing")
    seeds = challenge["fit_seeds"] + challenge["validation_seeds"] + challenge["holdout_seeds"]
    if len(seeds) != len(set(seeds)):
        raise ChallengeError("challenge seeds must be unique")
    if "stable_continuation" not in challenge["condition_groups"]:
        raise ChallengeError("stable_continuation is required for same-seed calibration")
    return value


def _clip_inputs(values: Mapping[str, float]) -> dict[str, float]:
    result: dict[str, float] = {}
    for name in EXTERNAL_FIELDS:
        low, high = (-1.0, 1.0) if name in EXTERNAL_FIELDS[:2] else (0.0, 1.0)
        value = float(np.clip(float(values.get(name, 0.0)), low, high))
        if not math.isfinite(value):
            raise ChallengeError(f"non-finite input {name}")
        result[name] = value
    return result


def _zero() -> dict[str, float]:
    return {name: 0.0 for name in EXTERNAL_FIELDS}


def _scaled(base: Mapping[str, float], multiplier: float) -> dict[str, float]:
    return _clip_inputs({name: float(base.get(name, 0.0)) * multiplier for name in EXTERNAL_FIELDS})


def _mix(left: Mapping[str, float], right: Mapping[str, float], weight: float) -> dict[str, float]:
    return _clip_inputs(
        {
            name: (1.0 - weight) * float(left.get(name, 0.0)) + weight * float(right.get(name, 0.0))
            for name in EXTERNAL_FIELDS
        }
    )


def _segment(start: int, end: int | None, event: str, values: Mapping[str, float]) -> dict[str, Any]:
    return {"start": int(start), "end": None if end is None else int(end), "event": event, **_clip_inputs(values)}


def _base_vectors() -> dict[str, dict[str, float]]:
    return {
        "mild": _clip_inputs(
            {
                "external_resource_supply": -0.2,
                "external_demand": 0.2,
                "external_competition_pressure": 0.25,
                "external_information_noise": 0.2,
                "external_shock": 0.45,
                "external_constraint_pressure": 0.25,
            }
        ),
        "delayed": _clip_inputs(
            {
                "external_resource_supply": -0.45,
                "external_demand": 0.4,
                "external_competition_pressure": 0.55,
                "external_information_noise": 0.5,
                "external_shock": 0.75,
                "external_constraint_pressure": 0.65,
            }
        ),
        "persistent": _clip_inputs(
            {
                "external_resource_supply": -0.75,
                "external_demand": 0.45,
                "external_competition_pressure": 0.7,
                "external_information_noise": 0.6,
                "external_shock": 0.15,
                "external_constraint_pressure": 0.65,
            }
        ),
        "fixation": _clip_inputs(
            {
                "external_resource_supply": -0.4,
                "external_demand": 0.85,
                "external_competition_pressure": 1.0,
                "external_information_noise": 0.65,
                "external_shock": 0.2,
                "external_constraint_pressure": 1.0,
            }
        ),
        "collapse": _clip_inputs(
            {
                "external_resource_supply": -1.0,
                "external_demand": 0.9,
                "external_competition_pressure": 1.0,
                "external_information_noise": 0.9,
                "external_shock": 1.0,
                "external_constraint_pressure": 1.0,
            }
        ),
    }


def build_scenario(condition: str, seed: int, config: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    challenge = config["challenge"]
    condition_index = list(challenge["condition_groups"]).index(condition)
    rng = np.random.default_rng(seed * 1009 + condition_index * 7919)
    start = int(rng.integers(challenge["start_step_range"][0], challenge["start_step_range"][1] + 1))
    duration = int(rng.integers(challenge["duration_range"][0], challenge["duration_range"][1] + 1))
    end = start + duration
    multiplier = float(rng.uniform(*challenge["strength_multiplier_range"]))
    residual = float(rng.uniform(*challenge["residual_burden_range"]))
    relapse = bool(rng.random() < float(challenge["relapse_probability"]))
    relapse_delay = int(rng.integers(challenge["relapse_delay_range"][0], challenge["relapse_delay_range"][1] + 1))
    vectors = _base_vectors()
    segments: list[dict[str, Any]] = []

    if condition == "stable_continuation":
        weak = _scaled(vectors["mild"], float(rng.uniform(0.0, 0.12)))
        weak["external_resource_supply"] = float(rng.uniform(-0.03, 0.03))
        weak["external_demand"] = float(rng.uniform(-0.03, 0.03))
        segments = [
            _segment(0, start, "stable_prefix", _zero()),
            _segment(start, min(end, challenge["transitions"]), "weak_background_variation", weak),
            _segment(min(end, challenge["transitions"]), None, "stable_tail", _zero()),
        ]
    elif condition == "temporary_disturbance":
        disturbance = _scaled(vectors["mild"], multiplier)
        segments = [
            _segment(0, start, "pre_disturbance", _zero()),
            _segment(start, end, "temporary_disturbance", disturbance),
            _segment(end, None, "disturbance_removed", _zero()),
        ]
    elif condition == "delayed_or_failed_recovery":
        disturbance = _scaled(vectors["delayed"], multiplier)
        residual_values = _scaled(disturbance, residual)
        segments = [
            _segment(0, start, "pre_disturbance", _zero()),
            _segment(start, end, "extended_disturbance", disturbance),
            _segment(end, None, "residual_burden", residual_values),
        ]
    elif condition == "persistent_deterioration":
        first = _scaled(vectors["persistent"], multiplier)
        second = _mix(first, vectors["fixation"], float(rng.uniform(0.1, 0.45)))
        switch = min(challenge["transitions"] - 1, start + max(3, duration // 2))
        segments = [
            _segment(0, start, "quiet_prefix", _zero()),
            _segment(start, switch, "persistent_phase_a", first),
            _segment(switch, None, "persistent_phase_b", second),
        ]
    elif condition == "fixation_path":
        first = _scaled(vectors["persistent"], float(rng.uniform(0.65, 0.95)))
        second = _scaled(vectors["fixation"], multiplier)
        if seed % 2:
            first, second = second, first
        switch = min(challenge["transitions"] - 1, end)
        segments = [
            _segment(0, start, "quiet_prefix", _zero()),
            _segment(start, switch, "fixation_path_phase_a", first),
            _segment(switch, None, "fixation_path_phase_b", second),
        ]
    elif condition == "collapse_path":
        collapse = _scaled(vectors["collapse"], multiplier)
        buildup = _mix(vectors["persistent"], collapse, float(rng.uniform(0.2, 0.55)))
        if seed % 2 == 0:
            segments = [
                _segment(0, start, "quiet_prefix", _zero()),
                _segment(start, end, "abrupt_collapse_shock", collapse),
                _segment(end, None, "collapse_residual", _scaled(collapse, max(0.55, residual))),
            ]
        else:
            segments = [
                _segment(0, start, "quiet_prefix", _zero()),
                _segment(start, end, "gradual_collapse_buildup", buildup),
                _segment(end, None, "collapse_threshold_crossing", collapse),
            ]
    else:
        raise ChallengeError(f"unknown condition {condition}")

    if relapse and condition in {"temporary_disturbance", "delayed_or_failed_recovery"}:
        relapse_start = end + relapse_delay
        if relapse_start < challenge["transitions"] - 2:
            relapse_end = min(challenge["transitions"], relapse_start + max(3, duration // 2))
            prefix = [segment for segment in segments if segment["start"] < relapse_start]
            if prefix:
                prefix[-1]["end"] = relapse_start
            relapse_values = _scaled(vectors["mild"], float(rng.uniform(0.5, 1.0)) * multiplier)
            segments = prefix + [
                _segment(relapse_start, relapse_end, "relapse", relapse_values),
                _segment(relapse_end, None, "post_relapse_tail", _scaled(relapse_values, residual)),
            ]

    # Normalize contiguous segment boundaries and remove zero-width segments.
    normalized: list[dict[str, Any]] = []
    cursor = 0
    for segment in segments:
        segment = dict(segment)
        segment["start"] = cursor
        end_value = segment["end"]
        if end_value is not None:
            end_value = max(cursor + 1, min(int(end_value), int(challenge["transitions"])))
            segment["end"] = end_value
        normalized.append(segment)
        if end_value is None:
            break
        cursor = end_value
    if normalized[-1]["end"] is not None:
        normalized.append(_segment(cursor, None, "terminal_tail", _zero()))

    parameters = {
        "condition_group": condition,
        "seed": seed,
        "start_step": start,
        "duration": duration,
        "strength_multiplier": multiplier,
        "residual_burden": residual,
        "relapse_enabled": relapse,
        "relapse_delay": relapse_delay,
        "schedule_hash": t2.hashlib.sha256(
            json.dumps(normalized, sort_keys=True).encode("utf-8")
        ).hexdigest(),
    }
    return {
        "description": f"Task 3.2-4 seed-varying challenge condition: {condition}",
        "segments": normalized,
    }, parameters


def _split(seed: int, config: Mapping[str, Any]) -> str:
    challenge = config["challenge"]
    if seed in challenge["fit_seeds"]:
        return "fit"
    if seed in challenge["validation_seeds"]:
        return "validation"
    if seed in challenge["holdout_seeds"]:
        return "holdout"
    raise ChallengeError(f"unassigned seed {seed}")


def generate(output_dir: str | Path, config_path: str | Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = load_config(config_path)
    task2_config = t2.load_generation_config(ROOT / config["task2_config_path"])
    contract = load_contract(ROOT / task2_config["contract_path"])
    output = Path(output_dir)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    challenge = config["challenge"]
    seeds = challenge["fit_seeds"] + challenge["validation_seeds"] + challenge["holdout_seeds"]
    summaries: list[dict[str, Any]] = []
    schedule_rows: list[dict[str, Any]] = []
    for condition in challenge["condition_groups"]:
        for seed in seeds:
            scenario, parameters = build_scenario(condition, int(seed), config)
            summary = t2.generate_trajectory(
                output,
                "task3_2_4_challenge",
                condition,
                scenario,
                int(seed),
                int(challenge["transitions"]),
                _split(int(seed), config),
                task2_config,
                contract,
            )
            summary["challenge_parameters"] = parameters
            t2._json_dump(
                output / "trajectories" / summary["trajectory_id"] / "summary.json",
                summary,
            )
            summaries.append(summary)
            schedule_rows.append({"trajectory_id": summary["trajectory_id"], **parameters})

    t2._write_comparison_csv(output / "scenario_comparison.csv", summaries)
    t2._write_overview_svg(output / "trajectory_overview.svg", summaries)
    outcome_counts: dict[str, int] = {}
    for summary in summaries:
        label = str(summary["outcome"]["coarse_outcome"])
        outcome_counts[label] = outcome_counts.get(label, 0) + 1
    corpus_summary = {
        "task_id": config["task_id"],
        "profile": "task3_2_4_challenge",
        "transitions_per_trajectory": int(challenge["transitions"]),
        "trajectory_count": len(summaries),
        "scenarios": list(challenge["condition_groups"]),
        "seeds": seeds,
        "outcome_counts": outcome_counts,
        "summaries": summaries,
        "schedule_variation": True,
    }
    t2._json_dump(output / "corpus_summary.json", corpus_summary)
    fields = list(schedule_rows[0].keys())
    t2._write_comparison_csv(output / "challenge_schedule_manifest.csv", schedule_rows)
    validation = t2.validate_corpus(output, contract, task2_config)
    schedule_hashes = [row["schedule_hash"] for row in schedule_rows]
    if len(schedule_hashes) != len(set(schedule_hashes)):
        raise ChallengeError("challenge schedules are not unique across trajectories")
    validation.update(
        {
            "schedule_variation_check": "passed",
            "unique_schedule_count": len(schedule_hashes),
            "split_seed_check": "passed",
        }
    )
    t2._json_dump(output / "validation.json", validation)
    manifest = t2._write_manifest(output)
    return {
        "trajectory_count": len(summaries),
        "transition_count": len(summaries) * int(challenge["transitions"]),
        "state_count": len(summaries) * (int(challenge["transitions"]) + 1),
        "unique_schedule_count": len(schedule_hashes),
        "validation": validation,
        "manifest_file_count": manifest["file_count"],
    }


def validate(input_dir: str | Path, config_path: str | Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = load_config(config_path)
    task2_config = t2.load_generation_config(ROOT / config["task2_config_path"])
    contract = load_contract(ROOT / task2_config["contract_path"])
    result = t2.validate_corpus(input_dir, contract, task2_config)
    summary = t2._json_load(Path(input_dir) / "corpus_summary.json")
    expected = len(config["challenge"]["condition_groups"]) * (
        len(config["challenge"]["fit_seeds"])
        + len(config["challenge"]["validation_seeds"])
        + len(config["challenge"]["holdout_seeds"])
    )
    if int(summary["trajectory_count"]) != expected:
        raise ChallengeError("challenge trajectory count mismatch")
    hashes = [item["challenge_parameters"]["schedule_hash"] for item in summary["summaries"]]
    if len(hashes) != len(set(hashes)):
        raise ChallengeError("challenge schedule uniqueness check failed")
    return {**result, "schedule_variation_check": "passed", "unique_schedule_count": len(hashes)}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("generate")
    run.add_argument("--output", required=True)
    run.add_argument("--config", default=str(DEFAULT_CONFIG))
    check = sub.add_parser("validate")
    check.add_argument("--input", required=True)
    check.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args(argv)
    result = generate(args.output, args.config) if args.command == "generate" else validate(args.input, args.config)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["ChallengeError", "build_scenario", "generate", "load_config", "validate"]
