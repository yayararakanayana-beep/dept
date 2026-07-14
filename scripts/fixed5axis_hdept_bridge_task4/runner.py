"""Task 4: 校正生成、単体科学検証、最終確認、凍結判定。"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from fixed5axis_hdept_bridge_task2.builder import build_observation
from fixed5axis_hdept_bridge_task2.contracts import (
    DEFAULT_FEATURE_REGISTRY,
    _canonical_json,
    _sha256_file,
    _write_json,
    load_feature_registry,
)
from fixed5axis_hdept_bridge_task2.features import extract_feature_records
from fixed5axis_hdept_bridge_task3.validator import validate_observation

from .scenarios import centroid, generate_trajectory, make_ledger_rows, write_canonical_trajectory

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROTOCOL = ROOT / "configs" / "fixed5axis_hdept_task4_scientific_validation_rc1.json"
BUNDLE_FILES = (
    "fixed5axis_hdept_task4_calibration_rc1.json",
    "task4_calibration_audit.json",
    "task4_validation_report.json",
    "task4_final_confirmation_report.json",
    "task4_freeze_decision.json",
)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _hash_strings(values: Sequence[str]) -> str:
    return hashlib.sha256("\n".join(sorted(values)).encode("utf-8")).hexdigest()


def _creation_code_hash(protocol_path: Path) -> str:
    digest = hashlib.sha256()
    for path in (
        protocol_path,
        Path(__file__),
        Path(__file__).with_name("scenarios.py"),
    ):
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\x00")
        digest.update(path.read_bytes())
        digest.update(b"\x00")
    return digest.hexdigest()


def _split_cases(protocol: Mapping[str, Any], split_name: str) -> list[tuple[str, int, str]]:
    split = protocol["splits"][split_name]
    cases: list[tuple[str, int, str]] = []
    for seed in range(int(split["seed_start"]), int(split["seed_start"]) + int(split["seed_count"])):
        for scenario in split["scenario_families"]:
            trajectory_id = f"task4_{scenario}_seed{seed}"
            cases.append((scenario, seed, trajectory_id))
    return cases


def _make_calibration(protocol: Mapping[str, Any], protocol_path: Path, registry_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    registry = load_feature_registry(registry_path)
    feature_values: dict[str, list[float]] = {entry["id"]: [] for entry in registry["features"]}
    trajectory_ids: list[str] = []
    horizon = int(protocol["horizon"])
    evaluation_t = int(protocol["evaluation_t"])
    for scenario, seed, trajectory_id in _split_cases(protocol, "calibration"):
        frames = generate_trajectory(scenario, seed, horizon)
        rows = make_ledger_rows(trajectory_id, frames)
        records = extract_feature_records(frames[: evaluation_t + 1], rows[: evaluation_t + 1], registry)
        trajectory_ids.append(trajectory_id)
        for entry, record in zip(registry["features"], records, strict=True):
            if bool(entry.get("score", True)) and float(entry["cap"]) > 0.0 and record["available"]:
                feature_values[entry["id"]].append(float(record["value"]))

    settings = protocol["calibration"]
    minimum = int(settings["minimum_available_samples_per_scored_feature"])
    scale_floor = float(settings["final_scale_floor"])
    centers: list[float | None] = []
    scales: list[float | None] = []
    lower: list[float | None] = []
    upper: list[float | None] = []
    counts: list[int] = []
    scale_source: list[str] = []
    insufficient: list[str] = []
    for entry in registry["features"]:
        scoring = bool(entry.get("score", True)) and float(entry["cap"]) > 0.0
        values = np.asarray(feature_values[entry["id"]], dtype=np.float64)
        counts.append(int(values.size))
        if not scoring:
            centers.append(None)
            scales.append(None)
            lower.append(None)
            upper.append(None)
            scale_source.append("not_scored")
            continue
        if values.size < minimum:
            insufficient.append(entry["id"])
        center_value = float(np.median(values)) if values.size else 0.0
        mad = float(np.median(np.abs(values - center_value))) if values.size else 0.0
        scale_value = 1.4826 * mad
        source = "mad"
        if scale_value <= 1e-12:
            scale_value = float(np.std(values, ddof=1)) if values.size > 1 else 0.0
            source = "sample_std_fallback"
        if scale_value < scale_floor:
            scale_value = scale_floor
            source = "scale_floor_fallback"
        centers.append(center_value)
        scales.append(scale_value)
        lower.append(float(settings["clip_lower"]))
        upper.append(float(settings["clip_upper"]))
        scale_source.append(source)

    registry_hash = _sha256_file(registry_path)
    artifact = {
        "calibration_version": protocol["calibration_version"],
        "contract_version": protocol["contract_version"],
        "feature_registry_hash": registry_hash,
        "feature_order": [entry["id"] for entry in registry["features"]],
        "center": centers,
        "scale": scales,
        "clip_lower": lower,
        "clip_upper": upper,
        "fit_dataset_ids": [f"task4_calibration_{scenario}" for scenario in protocol["splits"]["calibration"]["scenario_families"]],
        "fit_trajectory_ids_hash": _hash_strings(trajectory_ids),
        "fit_time_boundary": {"maximum_t": evaluation_t, "future_suffix_used": False},
        "normalization_method": settings["method"],
        "creation_code_hash": _creation_code_hash(protocol_path),
        "feature_available_counts": counts,
        "scale_source": scale_source,
        "fit_trajectory_count": len(trajectory_ids),
        "fit_split": "calibration",
        "validation_or_confirmation_used_for_fit": False,
        "online_refit_allowed": False,
    }
    audit = {
        "status": "pass" if not insufficient else "fail",
        "calibration_version": protocol["calibration_version"],
        "fit_trajectory_count": len(trajectory_ids),
        "fit_trajectory_ids": sorted(trajectory_ids),
        "fit_trajectory_ids_hash": _hash_strings(trajectory_ids),
        "minimum_available_samples_per_scored_feature": minimum,
        "insufficient_scored_features": insufficient,
        "feature_available_counts": {entry["id"]: count for entry, count in zip(registry["features"], counts, strict=True)},
        "scale_source": {entry["id"]: source for entry, source in zip(registry["features"], scale_source, strict=True)},
        "validation_or_confirmation_used_for_fit": False,
        "fit_only_boundary_passed": True,
    }
    return artifact, audit


def _median(cases: Sequence[Mapping[str, Any]], path: Sequence[str]) -> float:
    values: list[float] = []
    for case in cases:
        value: Any = case
        for key in path:
            value = value[key]
        if value is not None:
            values.append(float(value))
    if not values:
        raise ValueError(f"no numeric values for path {path}")
    return float(np.median(np.asarray(values, dtype=np.float64)))


def _scenario_cases(cases: Sequence[Mapping[str, Any]], scenario: str) -> list[Mapping[str, Any]]:
    return [case for case in cases if case["scenario"] == scenario]


def _evaluate_hypotheses(protocol: Mapping[str, Any], cases: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by = {scenario: _scenario_cases(cases, scenario) for scenario in protocol["splits"]["validation"]["scenario_families"]}
    thresholds = {item["id"]: item for item in protocol["hypotheses"]}
    results: list[dict[str, Any]] = []

    h1 = thresholds["H1_false_stability_guard"]
    metrics = {
        "Stability_locked_minus_broad": _median(by["locked_fixation"], ["h11", "Stability", "value"]) - _median(by["stable_broad"], ["h11", "Stability", "value"]),
        "Exploration_broad_minus_locked": _median(by["stable_broad"], ["h11", "Exploration", "value"]) - _median(by["locked_fixation"], ["h11", "Exploration", "value"]),
        "StructuralDiversity_broad_minus_locked": _median(by["stable_broad"], ["h11", "StructuralDiversity", "value"]) - _median(by["locked_fixation"], ["h11", "StructuralDiversity", "value"]),
    }
    req = h1["requirements"]
    passed = metrics["Stability_locked_minus_broad"] >= float(req["Stability_locked_minus_broad_min"]) and metrics["Exploration_broad_minus_locked"] >= float(req["Exploration_broad_minus_locked_min"]) and metrics["StructuralDiversity_broad_minus_locked"] >= float(req["StructuralDiversity_broad_minus_locked_min"])
    results.append({"id": h1["id"], "critical": h1["critical"], "passed": passed, "metrics": metrics, "requirements": req})

    h2 = thresholds["H2_structured_exploration"]
    metrics = {
        "Exploration_structured_minus_locked": _median(by["structured_exploration"], ["h11", "Exploration", "value"]) - _median(by["locked_fixation"], ["h11", "Exploration", "value"]),
        "StructuralDiversity_structured_minus_locked": _median(by["structured_exploration"], ["h11", "StructuralDiversity", "value"]) - _median(by["locked_fixation"], ["h11", "StructuralDiversity", "value"]),
    }
    req = h2["requirements"]
    passed = metrics["Exploration_structured_minus_locked"] >= float(req["Exploration_structured_minus_locked_min"]) and metrics["StructuralDiversity_structured_minus_locked"] >= float(req["StructuralDiversity_structured_minus_locked_min"])
    results.append({"id": h2["id"], "critical": h2["critical"], "passed": passed, "metrics": metrics, "requirements": req})

    h3 = thresholds["H3_noise_guard"]
    metrics = {
        "Coherence_structured_minus_noise": _median(by["structured_exploration"], ["h11", "Coherence", "value"]) - _median(by["noisy_expansion"], ["h11", "Coherence", "value"]),
        "tail_mass_noise_minus_structured": _median(by["noisy_expansion"], ["features", "tail_mass"]) - _median(by["structured_exploration"], ["features", "tail_mass"]),
    }
    req = h3["requirements"]
    passed = metrics["Coherence_structured_minus_noise"] >= float(req["Coherence_structured_minus_noise_min"]) and metrics["tail_mass_noise_minus_structured"] >= float(req["tail_mass_noise_minus_structured_min"])
    results.append({"id": h3["id"], "critical": h3["critical"], "passed": passed, "metrics": metrics, "requirements": req})

    h4 = thresholds["H4_oscillation_detection"]
    metrics = {
        "oscillation_index_difference": _median(by["oscillation"], ["features", "oscillation_index"]) - _median(by["smooth_adaptation"], ["features", "oscillation_index"]),
        "motion_angle_difference": _median(by["oscillation"], ["features", "motion_angle"]) - _median(by["smooth_adaptation"], ["features", "motion_angle"]),
        "TrajectoryDynamics_absolute_difference": abs(_median(by["oscillation"], ["h11", "TrajectoryDynamics", "value"]) - _median(by["smooth_adaptation"], ["h11", "TrajectoryDynamics", "value"])),
    }
    req = h4["requirements"]
    passed = metrics["oscillation_index_difference"] >= float(req["oscillation_index_difference_min"]) and metrics["motion_angle_difference"] >= float(req["motion_angle_difference_min"]) and metrics["TrajectoryDynamics_absolute_difference"] >= float(req["TrajectoryDynamics_absolute_difference_min"])
    results.append({"id": h4["id"], "critical": h4["critical"], "passed": passed, "metrics": metrics, "requirements": req})

    h5 = thresholds["H5_boundary_divergence"]
    metrics = {
        "tail_mass_divergence_minus_broad": _median(by["boundary_divergence"], ["features", "tail_mass"]) - _median(by["stable_broad"], ["features", "tail_mass"]),
        "Coherence_broad_minus_divergence": _median(by["stable_broad"], ["h11", "Coherence", "value"]) - _median(by["boundary_divergence"], ["h11", "Coherence", "value"]),
        "Stability_broad_minus_divergence": _median(by["stable_broad"], ["h11", "Stability", "value"]) - _median(by["boundary_divergence"], ["h11", "Stability", "value"]),
    }
    req = h5["requirements"]
    passed = metrics["tail_mass_divergence_minus_broad"] >= float(req["tail_mass_divergence_minus_broad_min"]) and metrics["Coherence_broad_minus_divergence"] >= float(req["Coherence_broad_minus_divergence_min"]) and metrics["Stability_broad_minus_divergence"] >= float(req["Stability_broad_minus_divergence_min"])
    results.append({"id": h5["id"], "critical": h5["critical"], "passed": passed, "metrics": metrics, "requirements": req})

    h6 = thresholds["H6_slow_fixation"]
    metrics = {
        "Exploration_broad_minus_fixation": _median(by["stable_broad"], ["h11", "Exploration", "value"]) - _median(by["slow_fixation"], ["h11", "Exploration", "value"]),
        "StructuralDiversity_broad_minus_fixation": _median(by["stable_broad"], ["h11", "StructuralDiversity", "value"]) - _median(by["slow_fixation"], ["h11", "StructuralDiversity", "value"]),
    }
    req = h6["requirements"]
    passed = metrics["Exploration_broad_minus_fixation"] >= float(req["Exploration_broad_minus_fixation_min"]) and metrics["StructuralDiversity_broad_minus_fixation"] >= float(req["StructuralDiversity_broad_minus_fixation_min"])
    results.append({"id": h6["id"], "critical": h6["critical"], "passed": passed, "metrics": metrics, "requirements": req})

    h7 = thresholds["H7_recovery_contract_limit"]
    recovery_cases = by["shock_full_recovery"] + by["shock_partial_recovery"] + by["shock_no_recovery"]
    unavailable = all(not case["h11"]["Recoverability"]["available"] for case in recovery_cases)
    full_distance = _median(by["shock_full_recovery"], ["recovery_diagnostic", "return_distance"])
    partial_distance = _median(by["shock_partial_recovery"], ["recovery_diagnostic", "return_distance"])
    no_distance = _median(by["shock_no_recovery"], ["recovery_diagnostic", "return_distance"])
    metrics = {
        "Recoverability_unavailable": unavailable,
        "full_return_distance": full_distance,
        "partial_return_distance": partial_distance,
        "no_recovery_return_distance": no_distance,
    }
    passed = unavailable and full_distance < partial_distance < no_distance
    results.append({"id": h7["id"], "critical": h7["critical"], "passed": passed, "metrics": metrics, "requirements": h7["requirements"]})

    h8 = thresholds["H8_no_single_batch_half_collapse"]
    min_available = min(case["available_h11_axis_count"] for case in cases)
    all_half = any(case["all_available_h11_values_equal_half"] for case in cases)
    axis_stds: dict[str, float] = {}
    axis_names = next(iter(cases))["h11"].keys()
    for axis in axis_names:
        values = [float(case["h11"][axis]["value"]) for case in cases if case["h11"][axis]["available"]]
        if len(values) >= 2:
            axis_stds[axis] = float(np.std(np.asarray(values, dtype=np.float64)))
    minimum_std = min(axis_stds.values()) if axis_stds else 0.0
    req = h8["requirements"]
    passed = min_available >= int(req["minimum_available_h11_axes_per_case"]) and minimum_std >= float(req["minimum_cross_scenario_available_axis_standard_deviation"]) and not all_half
    results.append({"id": h8["id"], "critical": h8["critical"], "passed": passed, "metrics": {"minimum_available_h11_axes_per_case": min_available, "minimum_cross_scenario_available_axis_standard_deviation": minimum_std, "axis_standard_deviation": axis_stds, "any_case_all_available_values_equal_0_5": all_half}, "requirements": req})
    return results


def _evaluate_split(protocol: Mapping[str, Any], split_name: str, calibration_path: Path, work_root: Path) -> dict[str, Any]:
    cases: list[dict[str, Any]] = []
    horizon = int(protocol["horizon"])
    current_t = int(protocol["evaluation_t"])
    for scenario, seed, trajectory_id in _split_cases(protocol, split_name):
        case_root = work_root / f"{scenario}_seed{seed}"
        source_dir = case_root / "canonical"
        artifact_dir = case_root / "observation"
        source = write_canonical_trajectory(source_dir, scenario, seed, horizon)
        build_observation(source_dir, current_t, artifact_dir, calibration_path=calibration_path)
        validation = validate_observation(source_dir, current_t, artifact_dir, calibration_path=calibration_path)
        feature_document = _load_json(artifact_dir / "features.json")
        observation_document = _load_json(artifact_dir / "m_observation.json")
        feature_map = {record["feature_id"]: record["value"] for record in feature_document["features"]}
        h11 = observation_document["h11"]
        available_values = [float(axis["value"]) for axis in h11.values() if axis["available"]]
        reference_t = 3
        return_distance = float(np.linalg.norm(centroid(source["frames"][-1]) - centroid(source["frames"][reference_t])))
        cases.append(
            {
                "scenario": scenario,
                "seed": seed,
                "trajectory_id": trajectory_id,
                "task3_validation_status": validation["status"],
                "global_observation_status": observation_document["global_observation_status"],
                "available_h11_axis_count": len(available_values),
                "all_available_h11_values_equal_half": bool(available_values and all(abs(value - 0.5) <= 1e-12 for value in available_values)),
                "features": feature_map,
                "h11": h11,
                "recovery_diagnostic": {"reference_t": reference_t, "return_distance": return_distance},
            }
        )
    hypotheses = _evaluate_hypotheses(protocol, cases)
    return {
        "protocol_id": protocol["protocol_id"],
        "split": split_name,
        "case_count": len(cases),
        "trajectory_ids": sorted(case["trajectory_id"] for case in cases),
        "all_task3_validations_passed": all(case["task3_validation_status"] == "pass" for case in cases),
        "hypothesis_pass_count": sum(bool(item["passed"]) for item in hypotheses),
        "hypothesis_count": len(hypotheses),
        "all_critical_hypotheses_passed": all(bool(item["passed"]) for item in hypotheses if item["critical"]),
        "hypotheses": hypotheses,
        "case_summaries": cases,
        "claim_boundary": protocol["claim_boundary"],
    }


def _manifest(root: Path) -> dict[str, Any]:
    return {
        "bundle_id": "fixed5axis_hdept_task4_freeze_bundle_rc1",
        "hash_algorithm": "sha256",
        "files": [
            {"path": name, "sha256": _sha256_file(root / name), "size_bytes": (root / name).stat().st_size}
            for name in BUNDLE_FILES
        ],
    }


def generate_task4_bundle(output_dir: str | Path, *, protocol_path: str | Path = DEFAULT_PROTOCOL, registry_path: str | Path = DEFAULT_FEATURE_REGISTRY) -> Path:
    output = Path(output_dir)
    if output.exists():
        raise ValueError(f"output already exists: {output}")
    protocol_file = Path(protocol_path)
    registry_file = Path(registry_path)
    protocol = _load_json(protocol_file)
    if protocol.get("status") != "pre_registered_before_task4_execution":
        raise ValueError("Task 4 protocol is not pre-registered")
    calibration, calibration_audit = _make_calibration(protocol, protocol_file, registry_file)
    repeated_calibration, repeated_audit = _make_calibration(protocol, protocol_file, registry_file)
    calibration_reproducible = _canonical_json(calibration) == _canonical_json(repeated_calibration) and _canonical_json(calibration_audit) == _canonical_json(repeated_audit)

    temporary = Path(tempfile.mkdtemp(prefix="fixed5axis_hdept_task4_"))
    try:
        calibration_path = temporary / "calibration.json"
        _write_json(calibration_path, calibration)
        validation_report = _evaluate_split(protocol, "validation", calibration_path, temporary / "validation")
        confirmation_report = _evaluate_split(protocol, "final_confirmation", calibration_path, temporary / "final_confirmation")
        split_ids = {
            name: {trajectory_id for _, _, trajectory_id in _split_cases(protocol, name)}
            for name in ("calibration", "validation", "final_confirmation")
        }
        split_disjoint = not (split_ids["calibration"] & split_ids["validation"] or split_ids["calibration"] & split_ids["final_confirmation"] or split_ids["validation"] & split_ids["final_confirmation"])
        all_task3 = bool(validation_report["all_task3_validations_passed"] and confirmation_report["all_task3_validations_passed"])
        scientific_pass = bool(calibration_audit["status"] == "pass" and calibration_reproducible and split_disjoint and all_task3 and validation_report["all_critical_hypotheses_passed"] and confirmation_report["all_critical_hypotheses_passed"])
        decision = {
            "protocol_id": protocol["protocol_id"],
            "calibration_version": protocol["calibration_version"],
            "decision": protocol["freeze_gate"]["decision_on_pass"] if scientific_pass else protocol["freeze_gate"]["decision_on_fail"],
            "scientific_gate_passed": scientific_pass,
            "calibration_reproducible": calibration_reproducible,
            "split_identity_overlap_forbidden_passed": split_disjoint,
            "calibration_fit_only_passed": calibration_audit["fit_only_boundary_passed"],
            "calibration_sample_coverage_passed": calibration_audit["status"] == "pass",
            "all_task3_validations_passed": all_task3,
            "validation_all_critical_hypotheses_passed": validation_report["all_critical_hypotheses_passed"],
            "final_confirmation_all_critical_hypotheses_passed": confirmation_report["all_critical_hypotheses_passed"],
            "validation_hypothesis_pass_count": validation_report["hypothesis_pass_count"],
            "validation_hypothesis_count": validation_report["hypothesis_count"],
            "final_confirmation_hypothesis_pass_count": confirmation_report["hypothesis_pass_count"],
            "final_confirmation_hypothesis_count": confirmation_report["hypothesis_count"],
            "scientific_status": "B_limited_synthetic_fixed5_only",
            "claim_boundary": protocol["claim_boundary"],
        }
        output.mkdir(parents=True, exist_ok=False)
        _write_json(output / BUNDLE_FILES[0], calibration)
        _write_json(output / BUNDLE_FILES[1], calibration_audit)
        _write_json(output / BUNDLE_FILES[2], validation_report)
        _write_json(output / BUNDLE_FILES[3], confirmation_report)
        _write_json(output / BUNDLE_FILES[4], decision)
        _write_json(output / "task4_manifest.json", _manifest(output))
    finally:
        shutil.rmtree(temporary, ignore_errors=True)
    return output


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--protocol", default=str(DEFAULT_PROTOCOL))
    parser.add_argument("--feature-registry", default=str(DEFAULT_FEATURE_REGISTRY))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    output = generate_task4_bundle(args.output_dir, protocol_path=args.protocol, registry_path=args.feature_registry)
    print(output)
    return 0
