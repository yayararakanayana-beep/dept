"""Task 4-3: fixed5 whole-system validation implementation and freeze bundle."""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import math
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from fixed5axis_hdept_bridge_task2.builder import build_observation
from fixed5axis_hdept_bridge_task2.canonical import GENESIS_HASH, _compute_gt_hash, _compute_history_chain_hash
from fixed5axis_hdept_bridge_task2.contracts import (
    AXIS_BINS,
    AXIS_NAMES,
    DEFAULT_BRIDGE_CONTRACT,
    DEFAULT_FEATURE_REGISTRY,
    DEFAULT_FIXED5_CONTRACT,
    DEFAULT_MEANING_PATCH,
    _canonical_json,
    _sha256_file,
    _write_json,
    load_bridge_contract,
    load_evidence_map,
    load_feature_registry,
    load_fixed5_contract,
)
from fixed5axis_hdept_bridge_task2.features import extract_feature_records
from fixed5axis_hdept_bridge_task2.h11 import construct_h11
from fixed5axis_hdept_bridge_task3.validator import (
    _read_reference_source,
    _reference_features,
    validate_observation,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROTOCOL = ROOT / "configs" / "fixed5axis_hdept_task4_2_whole_system_validation_preregistration_rc1.json"
DEFAULT_EXECUTION_LOCK = ROOT / "configs" / "fixed5axis_hdept_task4_3_execution_lock_rc1.json"

REFERENCE_GROUPS = (
    "axis_participation_and_dependency",
    "effective_dimensionality",
    "spread_shape_and_density",
    "whole_system_motion_and_trajectory",
)

@dataclass(frozen=True)
class CaseSpec:
    split: str
    seed: int
    case_id: str
    kind: str
    family: str
    strength: float | None = None
    mass_fraction: float | None = None
    continuity_path: str | None = None
    alpha: float | None = None

def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))

def _hash_strings(values: Iterable[str]) -> str:
    return hashlib.sha256("\n".join(sorted(str(v) for v in values)).encode("utf-8")).hexdigest()

def _hash_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()

def _coordinates() -> np.ndarray:
    mesh = np.meshgrid(*([np.asarray(AXIS_BINS, dtype=np.float64)] * 5), indexing="ij")
    return np.stack([axis.reshape(-1) for axis in mesh], axis=1)

COORDINATES = _coordinates()

def _normalize(mass: np.ndarray) -> np.ndarray:
    value = np.maximum(np.asarray(mass, dtype=np.float64).reshape(5, 5, 5, 5, 5), 0.0) + 1e-15
    value /= float(np.sum(value, dtype=np.float64))
    return value

def _gaussian_cov(center: np.ndarray, covariance: np.ndarray) -> np.ndarray:
    centered = COORDINATES - np.asarray(center, dtype=np.float64)
    covariance = 0.5 * (np.asarray(covariance, dtype=np.float64) + np.asarray(covariance, dtype=np.float64).T)
    covariance = covariance + 1e-6 * np.eye(5)
    inverse = np.linalg.pinv(covariance)
    exponent = -0.5 * np.einsum("ni,ij,nj->n", centered, inverse, centered, optimize=True)
    exponent -= float(np.max(exponent))
    return _normalize(np.exp(exponent))

def _baseline_parameters(seed: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(int(seed))
    center = np.clip(0.50 + rng.normal(0.0, 0.045, size=5), 0.32, 0.68)
    scales = np.clip(0.17 + rng.normal(0.0, 0.012, size=5), 0.135, 0.205)
    covariance = np.diag(scales * scales)
    direction_a = rng.normal(size=5)
    direction_a /= max(float(np.linalg.norm(direction_a)), 1e-12)
    direction_b = rng.normal(size=5)
    direction_b -= direction_a * float(direction_a @ direction_b)
    direction_b /= max(float(np.linalg.norm(direction_b)), 1e-12)
    return center, covariance, direction_a, direction_b

def _rotation_matrix(angle: float) -> np.ndarray:
    value = np.eye(5)
    c, s = math.cos(angle), math.sin(angle)
    value[0, 0], value[0, 1] = c, -s
    value[1, 0], value[1, 1] = s, c
    return value

def _base_frame(seed: int, t: int, horizon: int) -> np.ndarray:
    center, covariance, _, _ = _baseline_parameters(seed)
    phase = t / max(horizon - 1, 1)
    oscillation = 0.006 * np.sin(0.7 * t + np.arange(5))
    return _gaussian_cov(np.clip(center + oscillation * (0.25 + 0.75 * phase), 0.05, 0.95), covariance)

def _transformed_frame(seed: int, family: str, strength: float, t: int, horizon: int) -> np.ndarray:
    center, covariance, direction_a, direction_b = _baseline_parameters(seed)
    phase = t / max(horizon - 1, 1)
    smooth = phase * phase * (3.0 - 2.0 * phase)
    center_now = center.copy()
    covariance_now = covariance.copy()
    if family == "anisotropic_whole_system":
        scales = np.sqrt(np.diag(covariance_now))
        scales[0] *= max(0.38, 1.0 - 0.58 * strength * smooth)
        scales[1] *= 1.0 + 0.58 * strength * smooth
        covariance_now = np.diag(scales * scales)
    elif family == "correlated_whole_system":
        rho = 0.72 * strength * smooth
        covariance_now[0, 1] = covariance_now[1, 0] = rho * math.sqrt(covariance_now[0, 0] * covariance_now[1, 1])
        covariance_now[2, 3] = covariance_now[3, 2] = -0.55 * rho * math.sqrt(covariance_now[2, 2] * covariance_now[3, 3])
    elif family == "translated_whole_system":
        center_now = np.clip(center + 0.28 * strength * smooth * direction_a, 0.06, 0.94)
    elif family == "rotating_whole_system":
        rotation = _rotation_matrix(0.95 * strength * smooth)
        covariance_now = rotation @ covariance_now @ rotation.T
        center_now = np.clip(center + 0.05 * strength * math.sin(math.pi * phase) * direction_b, 0.06, 0.94)
    elif family == "contracting_or_expanding_whole_system":
        sign = -1.0 if seed % 2 == 0 else 1.0
        factor = max(0.42, 1.0 + sign * 0.62 * strength * smooth)
        covariance_now = covariance_now * factor * factor
    elif family == "temporally_curved_whole_system":
        center_now = np.clip(
            center + 0.20 * strength * phase * direction_a + 0.22 * strength * phase * phase * direction_b,
            0.06,
            0.94,
        )
    elif family == "broad_isotropic":
        return _base_frame(seed, t, horizon)
    else:
        raise ValueError(f"unsupported whole-system family: {family}")
    return _gaussian_cov(center_now, covariance_now)

def _local_perturbation_frame(seed: int, fraction: float, t: int, horizon: int) -> np.ndarray:
    center, _, direction_a, _ = _baseline_parameters(seed)
    local_center = np.clip(center + 0.34 * direction_a, 0.05, 0.95)
    local_covariance = np.diag(np.full(5, 0.065**2, dtype=np.float64))
    phase = t / max(horizon - 1, 1)
    weight = float(fraction) * (0.20 + 0.80 * phase)
    return _normalize((1.0 - weight) * _base_frame(seed, t, horizon) + weight * _gaussian_cov(local_center, local_covariance))

def generate_case_frames(spec: CaseSpec, horizon: int) -> np.ndarray:
    frames: list[np.ndarray] = []
    for t in range(horizon):
        if spec.kind == "global":
            frame = _transformed_frame(spec.seed, spec.family, float(spec.strength or 0.0), t, horizon)
        elif spec.kind == "local_scale":
            frame = _local_perturbation_frame(spec.seed, float(spec.mass_fraction), t, horizon)
        elif spec.kind == "continuity":
            baseline = _base_frame(spec.seed, t, horizon)
            transformed = _transformed_frame(spec.seed, str(spec.continuity_path), 0.78, t, horizon)
            alpha = float(spec.alpha)
            frame = _normalize((1.0 - alpha) * baseline + alpha * transformed)
        else:
            raise ValueError(f"unsupported case kind: {spec.kind}")
        frames.append(frame)
    return np.stack(frames).astype(np.float64, copy=False)

def _case_plan(protocol: Mapping[str, Any], lock: Mapping[str, Any], split: str, seed_count: int) -> list[CaseSpec]:
    split_def = protocol["split_design"][split]
    seed_start = int(split_def["seed_start"])
    strengths = [float(v) for v in lock["generation"]["global_strength_cycle"]]
    continuity_alphas = [float(v) for v in lock["generation"]["continuity_alphas"]]
    continuity_paths = [str(v) for v in lock["generation"]["continuity_paths"]]
    families = [str(item["id"]) for item in protocol["controlled_distribution_families"]]
    fractions = [float(v) for v in protocol["local_to_global_matched_perturbations"]["mass_fractions"]]
    result: list[CaseSpec] = []
    for offset, seed in enumerate(range(seed_start, seed_start + int(seed_count))):
        strength = strengths[offset % len(strengths)]
        for family in families:
            case_strength = 0.0 if family == "broad_isotropic" else strength
            result.append(CaseSpec(split, seed, f"{split}_seed{seed}_global_{family}", "global", family, strength=case_strength))
        for fraction in fractions:
            token = str(fraction).replace(".", "p")
            result.append(CaseSpec(split, seed, f"{split}_seed{seed}_local_{token}", "local_scale", "matched_local_perturbation", mass_fraction=fraction))
        for path in continuity_paths:
            for alpha in continuity_alphas:
                token = str(alpha).replace(".", "p")
                result.append(CaseSpec(split, seed, f"{split}_seed{seed}_continuity_{path}_{token}", "continuity", path, continuity_path=path, alpha=alpha))
    return result

def _ledger_rows(trajectory_id: str, frames: np.ndarray) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    previous_gt_hash = ""
    chain_hash = GENESIS_HASH
    for t, frame in enumerate(frames):
        source_state_hash = hashlib.sha256(f"task4-3:{trajectory_id}:{t}".encode("utf-8")).hexdigest()
        gt_hash = _compute_gt_hash(
            contract_version="fixed5axis_gk_rc1",
            trajectory_id=trajectory_id,
            t=t,
            distribution=frame,
            source_state_hash=source_state_hash,
        )
        chain_hash = _compute_history_chain_hash(chain_hash, gt_hash, t)
        rows.append(
            {
                "trajectory_id": trajectory_id,
                "source_trajectory_id": trajectory_id,
                "t": t,
                "phase": "pre_transition",
                "gt_row_index": t,
                "gt_hash": gt_hash,
                "previous_gt_hash": previous_gt_hash,
                "history_chain_hash": chain_hash,
                "delta_t": 0 if t == 0 else 1,
                "continuity_status": "initial" if t == 0 else "continuous",
                "admissible_for_research": True,
                "source_state_ref": f"synthetic_task4_3/{trajectory_id}/step_{t:06d}.json",
                "source_state_hash": source_state_hash,
            }
        )
        previous_gt_hash = gt_hash
    return rows

def _write_case(root: Path, spec: CaseSpec, frames: np.ndarray) -> Path:
    root.mkdir(parents=True, exist_ok=False)
    trajectory_id = spec.case_id
    rows = _ledger_rows(trajectory_id, frames)
    np.save(root / "gt_mass.npy", frames, allow_pickle=False)
    with (root / "history_ledger.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    provenance = {
        "contract_version": "fixed5axis_gk_rc1",
        "axis_order": list(AXIS_NAMES),
        "axis_bins": list(AXIS_BINS),
        "gt_shape": [5, 5, 5, 5, 5],
        "gt_dtype": "float64",
        "gt_phase": "pre_transition",
        "trajectory_id": trajectory_id,
        "generator": "fixed5axis_hdept_task4_3_whole_system_rc1",
        "case_spec": spec.__dict__,
        "forbidden_source_files_read": [],
        "source_writeback_performed": False,
    }
    _write_json(root / "provenance.json", provenance)
    _write_json(
        root / "manifest.json",
        {
            "contract_version": "fixed5axis_gk_rc1",
            "canonical_manifest_excludes_derived": True,
            "file_count": 3,
            "files": [
                {"relative_path": "gt_mass.npy"},
                {"relative_path": "history_ledger.csv"},
                {"relative_path": "provenance.json"},
            ],
        },
    )
    return root

def _feature_records_for_frames(frames: np.ndarray, registry: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = _ledger_rows("task4_3_direct_feature_extraction", frames)
    return extract_feature_records(frames, rows, registry)

def _fit_calibration(
    protocol_path: Path,
    lock_path: Path,
    registry_path: Path,
    protocol: Mapping[str, Any],
    lock: Mapping[str, Any],
    seed_count: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    registry = load_feature_registry(registry_path)
    values: dict[str, list[float]] = {entry["id"]: [] for entry in registry["features"]}
    case_ids: list[str] = []
    horizon = int(lock["generation"]["horizon"])
    for spec in _case_plan(protocol, lock, "design_calibration", seed_count):
        records = _feature_records_for_frames(generate_case_frames(spec, horizon), registry)
        case_ids.append(spec.case_id)
        for entry, record in zip(registry["features"], records, strict=True):
            if bool(entry.get("score", True)) and float(entry["cap"]) > 0.0 and record["available"]:
                values[entry["id"]].append(float(record["value"]))
    center: list[float | None] = []
    scale: list[float | None] = []
    lower: list[float | None] = []
    upper: list[float | None] = []
    non_scoring: list[str] = []
    source: list[str] = []
    counts: list[int] = []
    clip_lower = float(lock["calibration"]["clip_lower"])
    clip_upper = float(lock["calibration"]["clip_upper"])
    minimum = int(lock["calibration"]["minimum_available_samples"])
    for entry in registry["features"]:
        scoring = bool(entry.get("score", True)) and float(entry["cap"]) > 0.0
        data = np.asarray(values[entry["id"]], dtype=np.float64)
        counts.append(int(data.size))
        if not scoring:
            center.append(None); scale.append(None); lower.append(None); upper.append(None); source.append("contract_non_scoring")
            continue
        if data.size < minimum:
            raise ValueError(f"insufficient calibration samples for {entry['id']}: {data.size}")
        median = float(np.median(data))
        mad = float(np.median(np.abs(data - median)))
        width = 1.4826 * mad
        width_source = "mad"
        if width <= float(lock["calibration"]["constant_tolerance"]):
            width = float(np.std(data, ddof=1)) if data.size > 1 else 0.0
            width_source = "sample_std_fallback"
        if width <= float(lock["calibration"]["constant_tolerance"]):
            center.append(None); scale.append(None); lower.append(None); upper.append(None)
            non_scoring.append(entry["id"]); source.append("non_scoring_constant")
        else:
            center.append(median); scale.append(width); lower.append(clip_lower); upper.append(clip_upper); source.append(width_source)
    artifact = {
        "calibration_version": "fixed5axis_hdept_task4_3_whole_system_rc1",
        "feature_registry_hash": _sha256_file(registry_path),
        "feature_order": [entry["id"] for entry in registry["features"]],
        "center": center,
        "scale": scale,
        "clip_lower": lower,
        "clip_upper": upper,
        "fit_dataset_ids": ["task4_3_design_calibration_whole_system"],
        "fit_trajectory_ids_hash": _hash_strings(case_ids),
        "fit_time_boundary": {"maximum_t": int(lock["generation"]["evaluation_t"]), "future_suffix_used": False},
        "normalization_method": "robust_zscore",
        "creation_code_hash": _hash_strings([_sha256_file(protocol_path), _sha256_file(lock_path), _sha256_file(Path(__file__))]),
        "non_scoring_feature_ids": sorted(non_scoring),
        "meaning_patch_hash": _sha256_file(DEFAULT_MEANING_PATCH),
        "feature_available_counts": counts,
        "scale_source": source,
        "fit_case_count": len(case_ids),
        "fit_seed_count": int(seed_count),
        "fit_split": "design_calibration",
        "validation_or_confirmation_used_for_fit": False,
        "online_refit_allowed": False,
    }
    audit = {
        "status": "pass",
        "fit_seed_count": int(seed_count),
        "fit_case_count": len(case_ids),
        "fit_case_ids_hash": _hash_strings(case_ids),
        "non_scoring_feature_ids": sorted(non_scoring),
        "feature_available_counts": {entry["id"]: count for entry, count in zip(registry["features"], counts, strict=True)},
        "scale_source": {entry["id"]: item for entry, item in zip(registry["features"], source, strict=True)},
        "fit_only_boundary_passed": True,
        "meaning_patch_hash_matched": artifact["meaning_patch_hash"] == _sha256_file(DEFAULT_MEANING_PATCH),
    }
    return artifact, audit

def _registry_with_fit_constants(registry: Mapping[str, Any], calibration: Mapping[str, Any]) -> dict[str, Any]:
    effective = copy.deepcopy(dict(registry))
    blocked = set(calibration.get("non_scoring_feature_ids", []))
    for entry in effective["features"]:
        if entry["id"] in blocked:
            entry["score"] = False
            entry["calibration_non_scoring_constant"] = True
    return effective

def _direct_case_summary(
    spec: CaseSpec,
    frames: np.ndarray,
    registry: Mapping[str, Any],
    evidence_map: Mapping[str, Any],
    calibration: Mapping[str, Any],
) -> dict[str, Any]:
    effective_registry = _registry_with_fit_constants(registry, calibration)
    records = _feature_records_for_frames(frames, effective_registry)
    axes, global_status = construct_h11(records, effective_registry, evidence_map, calibration, len(frames))
    return {
        "case_spec": spec.__dict__,
        "global_observation_status": global_status,
        "features": {record["feature_id"]: record["value"] for record in records},
        "feature_available": {record["feature_id"]: bool(record["available"]) for record in records},
        "h11": axes,
    }

def _profile_vector(summary: Mapping[str, Any], axis_order: Sequence[str]) -> np.ndarray:
    values = []
    for axis in axis_order:
        item = summary["h11"][axis]
        if not item["available"] or item["value"] is None:
            raise ValueError(f"axis {axis} unavailable in required profile")
        values.append(float(item["value"]))
    return np.asarray(values, dtype=np.float64)

def _profile_distance(left: Mapping[str, Any], right: Mapping[str, Any], axis_order: Sequence[str]) -> float:
    values = []
    for axis in axis_order:
        a, b = left["h11"][axis], right["h11"][axis]
        if a["available"] and b["available"]:
            weight = math.sqrt(float(a["confidence"]) * float(b["confidence"]))
            values.append(weight * (float(a["value"]) - float(b["value"])))
    if not values:
        raise ValueError("no jointly available H11 axes")
    return float(np.linalg.norm(np.asarray(values, dtype=np.float64)))

def _rankdata(values: Sequence[float]) -> np.ndarray:
    array = np.asarray(values, dtype=np.float64)
    order = np.argsort(array, kind="mergesort")
    ranks = np.empty(array.size, dtype=np.float64)
    start = 0
    while start < array.size:
        end = start + 1
        while end < array.size and array[order[end]] == array[order[start]]:
            end += 1
        rank = 0.5 * (start + end - 1) + 1.0
        ranks[order[start:end]] = rank
        start = end
    return ranks

def _spearman(left: Sequence[float], right: Sequence[float]) -> float:
    x, y = _rankdata(left), _rankdata(right)
    if x.size < 2 or float(np.std(x)) <= 1e-15 or float(np.std(y)) <= 1e-15:
        return 0.0
    return float(np.corrcoef(x, y)[0, 1])

def _bootstrap_mean_ci(values: Sequence[float], seeds: Sequence[int], confidence: float) -> tuple[float, float]:
    array = np.asarray(values, dtype=np.float64)
    if array.size == 0:
        return (float("nan"), float("nan"))
    samples = np.empty(len(seeds), dtype=np.float64)
    for index, seed in enumerate(seeds):
        rng = np.random.default_rng(int(seed))
        samples[index] = float(np.mean(array[rng.integers(0, array.size, size=array.size)]))
    alpha = 1.0 - float(confidence)
    return (float(np.quantile(samples, alpha / 2.0)), float(np.quantile(samples, 1.0 - alpha / 2.0)))

def _bootstrap_one_sided_p_less_than_zero(values: Sequence[float], seeds: Sequence[int]) -> float:
    array = np.asarray(values, dtype=np.float64)
    if array.size == 0:
        return 1.0
    non_favorable = 0
    for seed in seeds:
        rng = np.random.default_rng(int(seed))
        mean = float(np.mean(array[rng.integers(0, array.size, size=array.size)]))
        non_favorable += int(mean >= 0.0)
    return float((non_favorable + 1) / (len(seeds) + 1))

def _holm_adjust(p_values: Mapping[str, float]) -> dict[str, float]:
    ordered = sorted(p_values.items(), key=lambda item: (item[1], item[0]))
    total = len(ordered)
    adjusted: dict[str, float] = {}
    running = 0.0
    for index, (key, value) in enumerate(ordered):
        candidate = min(1.0, (total - index) * float(value))
        running = max(running, candidate)
        adjusted[key] = running
    return adjusted

def _axis_order_for_calibration(summaries: Sequence[Mapping[str, Any]], evidence_map: Mapping[str, Any]) -> list[str]:
    result = []
    for axis in evidence_map["axis_order"]:
        if all(summary["h11"][axis]["available"] for summary in summaries):
            result.append(axis)
    if len(result) < 2:
        raise ValueError("fewer than two jointly available H11 axes")
    return result

def _planning_diagnostics(
    protocol: Mapping[str, Any],
    lock: Mapping[str, Any],
    calibration: Mapping[str, Any],
    seed_count: int,
) -> dict[str, Any]:
    registry = load_feature_registry(DEFAULT_FEATURE_REGISTRY)
    evidence_map = load_evidence_map()
    horizon = int(lock["generation"]["horizon"])
    specs = _case_plan(protocol, lock, "design_calibration", seed_count)
    summaries = {spec.case_id: _direct_case_summary(spec, generate_case_frames(spec, horizon), registry, evidence_map, calibration) for spec in specs}
    axis_order = _axis_order_for_calibration(list(summaries.values()), evidence_map)
    fractions = [float(v) for v in protocol["local_to_global_matched_perturbations"]["mass_fractions"]]
    rhos: list[float] = []
    global_effects: list[float] = []
    seed_start = int(protocol["split_design"]["design_calibration"]["seed_start"])
    for seed in range(seed_start, seed_start + seed_count):
        baseline = summaries[f"design_calibration_seed{seed}_global_broad_isotropic"]
        distances = []
        for fraction in fractions:
            token = str(fraction).replace(".", "p")
            distances.append(_profile_distance(baseline, summaries[f"design_calibration_seed{seed}_local_{token}"], axis_order))
        rhos.append(_spearman(fractions, distances))
        global_distances = []
        for item in protocol["controlled_distribution_families"]:
            family = item["id"]
            if family == "broad_isotropic":
                continue
            global_distances.append(_profile_distance(baseline, summaries[f"design_calibration_seed{seed}_global_{family}"], axis_order))
        global_effects.append(float(np.median(global_distances)))
    bootstrap_seeds = list(range(int(lock["statistics"]["bootstrap_seed_start"]), int(lock["statistics"]["bootstrap_seed_start"]) + int(lock["statistics"]["bootstrap_count"])))
    rho_ci = _bootstrap_mean_ci(rhos, bootstrap_seeds, float(protocol["multiple_testing_and_uncertainty"]["confidence_level"]))
    effect_ci = _bootstrap_mean_ci(global_effects, bootstrap_seeds, float(protocol["multiple_testing_and_uncertainty"]["confidence_level"]))
    return {
        "seed_count": int(seed_count),
        "axis_order": axis_order,
        "mean_scale_response_spearman": float(np.mean(rhos)),
        "scale_response_spearman_ci": list(rho_ci),
        "median_seed_spearman": float(np.median(rhos)),
        "mean_global_profile_effect": float(np.mean(global_effects)),
        "global_profile_effect_ci": list(effect_ci),
        "planning_passed": bool(
            rho_ci[0] > float(lock["sample_size"]["minimum_lower_ci"])
            and float(np.median(rhos)) >= float(lock["sample_size"]["minimum_median_spearman"])
            and effect_ci[0] > float(lock["sample_size"]["minimum_global_profile_effect"])
        ),
    }

def _select_sample_size(
    protocol_path: Path,
    lock_path: Path,
    registry_path: Path,
    protocol: Mapping[str, Any],
    lock: Mapping[str, Any],
) -> tuple[int, dict[str, Any], dict[str, Any], dict[str, Any]]:
    attempts = []
    for seed_count in [int(v) for v in lock["sample_size"]["candidate_seed_counts"]]:
        calibration, calibration_audit = _fit_calibration(protocol_path, lock_path, registry_path, protocol, lock, seed_count)
        diagnostics = _planning_diagnostics(protocol, lock, calibration, seed_count)
        attempts.append(diagnostics)
        if diagnostics["planning_passed"]:
            artifact = {
                "lock_id": "fixed5axis_hdept_task4_3_sample_size_lock_rc1",
                "status": "locked_before_validation_generation",
                "selected_seed_count_per_split": seed_count,
                "candidate_attempts": attempts,
                "target_power": protocol["sample_size_lock"]["target_power"],
                "familywise_alpha": protocol["sample_size_lock"]["familywise_alpha"],
                "validation_generated_before_lock": False,
                "final_confirmation_generated_before_validation_freeze": False,
            }
            return seed_count, calibration, calibration_audit, artifact
    raise ValueError("calibration-only sample-size planning did not support any registered candidate")

def _read_artifact_summary(
    spec: CaseSpec,
    canonical_dir: Path,
    observation_dir: Path,
    calibration_path: Path,
    registry: Mapping[str, Any],
    fixed5: Mapping[str, Any],
    bridge: Mapping[str, Any],
    evaluation_t: int,
) -> dict[str, Any]:
    validation = validate_observation(canonical_dir, evaluation_t, observation_dir, calibration_path=calibration_path)
    source = _read_reference_source(canonical_dir, evaluation_t, fixed5, bridge)
    reference_records = _reference_features(source["frames"], source["ledger"], registry)
    feature_doc = _load_json(observation_dir / "features.json")
    h11_doc = _load_json(observation_dir / "m_observation.json")
    task2_features = {item["feature_id"]: item for item in feature_doc["features"]}
    reference_features = {item["feature_id"]: item for item in reference_records}
    return {
        "case_spec": spec.__dict__,
        "task3_validation_status": validation["status"],
        "global_observation_status": h11_doc["global_observation_status"],
        "h11": h11_doc["h11"],
        "task2_features": {key: value["value"] for key, value in task2_features.items()},
        "task2_feature_available": {key: bool(value["available"]) for key, value in task2_features.items()},
        "reference_features": {key: value["value"] for key, value in reference_features.items()},
        "reference_feature_available": {key: bool(value["available"]) for key, value in reference_features.items()},
        "gt_hash": source["gt_hash"],
        "history_chain_hash": source["history_chain_hash"],
        "canonical_relative_path": canonical_dir.as_posix(),
        "observation_relative_path": observation_dir.as_posix(),
    }

def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n")

def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]

def _generate_split(
    output: Path,
    split: str,
    protocol: Mapping[str, Any],
    lock: Mapping[str, Any],
    seed_count: int,
    calibration_path: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    registry = load_feature_registry(DEFAULT_FEATURE_REGISTRY)
    fixed5 = load_fixed5_contract(DEFAULT_FIXED5_CONTRACT)
    bridge = load_bridge_contract(DEFAULT_BRIDGE_CONTRACT)
    horizon = int(lock["generation"]["horizon"])
    evaluation_t = int(lock["generation"]["evaluation_t"])
    summaries: list[dict[str, Any]] = []
    source_hash_before: dict[str, str] = {}
    source_hash_after: dict[str, str] = {}
    for spec in _case_plan(protocol, lock, split, seed_count):
        case_root = output / "cases" / split / spec.case_id
        canonical_dir = case_root / "canonical"
        observation_dir = case_root / "observation"
        frames = generate_case_frames(spec, horizon)
        _write_case(canonical_dir, spec, frames)
        source_hash_before[spec.case_id] = _tree_hash(canonical_dir)
        build_observation(canonical_dir, evaluation_t, observation_dir, calibration_path=calibration_path)
        source_hash_after[spec.case_id] = _tree_hash(canonical_dir)
        summary = _read_artifact_summary(spec, canonical_dir, observation_dir, calibration_path, registry, fixed5, bridge, evaluation_t)
        summary["canonical_relative_path"] = canonical_dir.relative_to(output).as_posix()
        summary["observation_relative_path"] = observation_dir.relative_to(output).as_posix()
        summaries.append(summary)
    audit = {
        "split": split,
        "seed_count": seed_count,
        "case_count": len(summaries),
        "all_task3_validations_passed": all(item["task3_validation_status"] == "pass" for item in summaries),
        "source_writeback_absent": source_hash_before == source_hash_after,
        "trajectory_ids_hash": _hash_strings(item["case_spec"]["case_id"] for item in summaries),
    }
    return summaries, audit

def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode("utf-8"))
            digest.update(b"\x00")
            digest.update(path.read_bytes())
            digest.update(b"\x00")
    return digest.hexdigest()

def _reference_feature_order(protocol: Mapping[str, Any], calibration: Mapping[str, Any], rows: Sequence[Mapping[str, Any]]) -> tuple[list[str], dict[str, list[str]]]:
    blocked = set(calibration.get("non_scoring_feature_ids", []))
    groups: dict[str, list[str]] = {}
    for group, requested in protocol["independent_reference_vector"]["groups"].items():
        selected = []
        for feature in requested:
            if feature in blocked:
                continue
            values = [row["reference_features"].get(feature) for row in rows if row["reference_feature_available"].get(feature)]
            if len(values) >= 2 and float(np.std(np.asarray(values, dtype=np.float64))) > 1e-12:
                selected.append(feature)
        if selected:
            groups[group] = selected
    order = [feature for group in REFERENCE_GROUPS for feature in groups.get(group, [])]
    if not order:
        raise ValueError("no varying independent reference features")
    return order, groups

def _common_axis_order(rows: Sequence[Mapping[str, Any]], evidence_map: Mapping[str, Any]) -> list[str]:
    result = [axis for axis in evidence_map["axis_order"] if all(row["h11"][axis]["available"] for row in rows)]
    if len(result) < 2:
        raise ValueError("fewer than two common available H11 axes")
    return result

def _matrix(rows: Sequence[Mapping[str, Any]], keys: Sequence[str], source: str) -> np.ndarray:
    return np.asarray([[float(row[source][key]) for key in keys] for row in rows], dtype=np.float64)

def _h11_matrix(rows: Sequence[Mapping[str, Any]], axes: Sequence[str]) -> np.ndarray:
    return np.asarray([[float(row["h11"][axis]["value"]) for axis in axes] for row in rows], dtype=np.float64)

def _standardize_fit(array: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mean = np.mean(array, axis=0)
    scale = np.std(array, axis=0, ddof=1)
    scale = np.where(scale > 1e-12, scale, 1.0)
    return (array - mean) / scale, mean, scale

def _standardize_apply(array: np.ndarray, mean: np.ndarray, scale: np.ndarray) -> np.ndarray:
    return (array - mean) / scale

def _ridge_fit(x: np.ndarray, y: np.ndarray, ridge: float) -> np.ndarray:
    design = np.concatenate([np.ones((x.shape[0], 1)), x], axis=1)
    penalty = np.eye(design.shape[1]) * float(ridge)
    penalty[0, 0] = 0.0
    return np.linalg.solve(design.T @ design + penalty, design.T @ y)

def _ridge_predict(x: np.ndarray, coefficients: np.ndarray) -> np.ndarray:
    design = np.concatenate([np.ones((x.shape[0], 1)), x], axis=1)
    return design @ coefficients

def _random8_definition(feature_count: int, lock: Mapping[str, Any]) -> dict[str, Any]:
    members = []
    dimension = min(int(lock["random8"]["dimension"]), feature_count)
    for seed in range(int(lock["random8"]["seed_start"]), int(lock["random8"]["seed_start"]) + int(lock["random8"]["ensemble_count"])):
        rng = np.random.default_rng(seed)
        matrix = rng.normal(size=(feature_count, dimension))
        q, _ = np.linalg.qr(matrix)
        members.append({"seed": seed, "matrix": q[:, :dimension].tolist()})
    return {"basis_id": "fixed5axis_hdept_task4_3_random8_rc1", "feature_count": feature_count, "dimension": dimension, "members": members}

def _decoder_lock(
    calibration_rows: Sequence[Mapping[str, Any]],
    protocol: Mapping[str, Any],
    lock: Mapping[str, Any],
    calibration: Mapping[str, Any],
) -> dict[str, Any]:
    evidence_map = load_evidence_map()
    axes = _common_axis_order(calibration_rows, evidence_map)
    feature_order, groups = _reference_feature_order(protocol, calibration, calibration_rows)
    x_raw = _h11_matrix(calibration_rows, axes)
    y_raw = _matrix(calibration_rows, feature_order, "reference_features")
    x, x_mean, x_scale = _standardize_fit(x_raw)
    y, y_mean, y_scale = _standardize_fit(y_raw)
    ridge = float(lock["decoding"]["ridge_lambda"])
    h11_coefficients = _ridge_fit(x, y, ridge)
    random_definition = _random8_definition(len(feature_order), lock)
    random_coefficients = []
    for member in random_definition["members"]:
        matrix = np.asarray(member["matrix"], dtype=np.float64)
        projected = y @ matrix
        random_coefficients.append(_ridge_fit(projected, y, ridge).tolist())
    _, _, vt = np.linalg.svd(y, full_matrices=False)
    pca_dimension = min(8, vt.shape[0])
    pca_components = vt[:pca_dimension].T
    pca_coefficients = _ridge_fit(y @ pca_components, y, ridge)
    return {
        "lock_id": "fixed5axis_hdept_task4_3_decoder_lock_rc1",
        "status": "fit_on_design_calibration_only",
        "axis_order": axes,
        "reference_feature_order": feature_order,
        "reference_groups": groups,
        "x_mean": x_mean.tolist(),
        "x_scale": x_scale.tolist(),
        "y_mean": y_mean.tolist(),
        "y_scale": y_scale.tolist(),
        "ridge_lambda": ridge,
        "h11_coefficients": h11_coefficients.tolist(),
        "random8_definition": random_definition,
        "random8_coefficients": random_coefficients,
        "pca8_components": pca_components.tolist(),
        "pca8_coefficients": pca_coefficients.tolist(),
        "calibration_case_ids_hash": _hash_strings(row["case_spec"]["case_id"] for row in calibration_rows),
        "validation_or_confirmation_used": False,
    }

def _binomial_quantile(n: int, p: float, q: float) -> int:
    p = min(max(float(p), 0.0), 1.0)
    cumulative = 0.0
    for k in range(n + 1):
        cumulative += math.comb(n, k) * (p**k) * ((1.0 - p) ** (n - k))
        if cumulative >= q:
            return k
    return n

def _input_distance(left: np.ndarray, right: np.ndarray) -> float:
    p, q = left.reshape(-1), right.reshape(-1)
    tv = 0.5 * float(np.sum(np.abs(p - q), dtype=np.float64))
    marginal = []
    for axis in range(5):
        summed = tuple(index for index in range(5) if index != axis)
        pm = np.sum(left, axis=summed, dtype=np.float64)
        qm = np.sum(right, axis=summed, dtype=np.float64)
        marginal.append(float(np.sum(np.abs(np.cumsum(pm - qm)[:-1]), dtype=np.float64) * 0.25))
    return tv + float(np.linalg.norm(np.asarray(marginal, dtype=np.float64)))

def _output_distance(left: Mapping[str, Any], right: Mapping[str, Any], axes: Sequence[str]) -> float:
    return _profile_distance(left, right, axes)

def _evaluate_e2(
    calibration_rows: Sequence[Mapping[str, Any]],
    rows: Sequence[Mapping[str, Any]],
    decoder: Mapping[str, Any],
    protocol: Mapping[str, Any],
    lock: Mapping[str, Any],
) -> dict[str, Any]:
    axes = decoder["axis_order"]
    features = decoder["reference_feature_order"]
    x = _standardize_apply(
        _h11_matrix(rows, axes),
        np.asarray(decoder["x_mean"], dtype=np.float64),
        np.asarray(decoder["x_scale"], dtype=np.float64),
    )
    y = _standardize_apply(
        _matrix(rows, features, "reference_features"),
        np.asarray(decoder["y_mean"], dtype=np.float64),
        np.asarray(decoder["y_scale"], dtype=np.float64),
    )
    h11_prediction = _ridge_predict(x, np.asarray(decoder["h11_coefficients"], dtype=np.float64))
    random_predictions = []
    for member, coefficients in zip(decoder["random8_definition"]["members"], decoder["random8_coefficients"], strict=True):
        matrix = np.asarray(member["matrix"], dtype=np.float64)
        random_predictions.append(_ridge_predict(y @ matrix, np.asarray(coefficients, dtype=np.float64)))
    random_losses = np.stack([np.mean((prediction - y) ** 2, axis=1) for prediction in random_predictions], axis=1)
    random_median_loss = np.median(random_losses, axis=1)
    h11_losses = np.mean((h11_prediction - y) ** 2, axis=1)
    intercept_losses = np.mean(y**2, axis=1)
    seed_ids = sorted(set(int(row["case_spec"]["seed"]) for row in rows))
    h11_by_seed = {seed: float(np.mean([loss for row, loss in zip(rows, h11_losses, strict=True) if int(row["case_spec"]["seed"]) == seed])) for seed in seed_ids}
    intercept_by_seed = {seed: float(np.mean([loss for row, loss in zip(rows, intercept_losses, strict=True) if int(row["case_spec"]["seed"]) == seed])) for seed in seed_ids}
    random_by_seed = {seed: float(np.mean([loss for row, loss in zip(rows, random_median_loss, strict=True) if int(row["case_spec"]["seed"]) == seed])) for seed in seed_ids}
    bootstrap_seeds = list(range(int(lock["statistics"]["bootstrap_seed_start"]), int(lock["statistics"]["bootstrap_seed_start"]) + int(lock["statistics"]["bootstrap_count"])))
    overall_intercept_diff = [h11_by_seed[seed] - intercept_by_seed[seed] for seed in seed_ids]
    overall_random_diff = [h11_by_seed[seed] - random_by_seed[seed] for seed in seed_ids]
    intercept_ci = _bootstrap_mean_ci(overall_intercept_diff, bootstrap_seeds, float(protocol["multiple_testing_and_uncertainty"]["confidence_level"]))
    random_ci = _bootstrap_mean_ci(overall_random_diff, bootstrap_seeds, float(protocol["multiple_testing_and_uncertainty"]["confidence_level"]))
    group_results = {}
    group_p_values: dict[str, float] = {}
    feature_index = {feature: index for index, feature in enumerate(features)}
    for group, group_features in decoder["reference_groups"].items():
        indices = [feature_index[feature] for feature in group_features]
        h_loss = np.mean((h11_prediction[:, indices] - y[:, indices]) ** 2, axis=1)
        i_loss = np.mean(y[:, indices] ** 2, axis=1)
        differences = []
        for seed in seed_ids:
            selected = [index for index, row in enumerate(rows) if int(row["case_spec"]["seed"]) == seed]
            differences.append(float(np.mean(h_loss[selected]) - np.mean(i_loss[selected])))
        ci = _bootstrap_mean_ci(differences, bootstrap_seeds, float(protocol["multiple_testing_and_uncertainty"]["confidence_level"]))
        p_value = _bootstrap_one_sided_p_less_than_zero(differences, bootstrap_seeds)
        group_p_values[group] = p_value
        group_results[group] = {
            "mean_h11_minus_intercept_loss": float(np.mean(differences)),
            "ci": list(ci),
            "one_sided_bootstrap_p": p_value,
        }
    adjusted = _holm_adjust(group_p_values)
    alpha = float(lock["statistics"]["holm_familywise_alpha"])
    for group, item in group_results.items():
        item["holm_adjusted_p"] = adjusted[group]
        item["passed"] = bool(item["ci"][1] < 0.0 and adjusted[group] < alpha)
    passed = all(item["passed"] for item in group_results.values()) and intercept_ci[1] < 0.0 and random_ci[1] < 0.0
    return {
        "passed": bool(passed),
        "group_results": group_results,
        "aggregate_h11_minus_intercept": {"mean": float(np.mean(overall_intercept_diff)), "ci": list(intercept_ci), "passed": intercept_ci[1] < 0.0},
        "aggregate_h11_minus_random8_median": {"mean": float(np.mean(overall_random_diff)), "ci": list(random_ci), "passed": random_ci[1] < 0.0},
        "axis_order": axes,
        "reference_feature_order": features,
    }

def _evaluate_e3(rows: Sequence[Mapping[str, Any]], protocol: Mapping[str, Any], lock: Mapping[str, Any], axes: Sequence[str]) -> dict[str, Any]:
    fractions = [float(v) for v in protocol["local_to_global_matched_perturbations"]["mass_fractions"]]
    seed_ids = sorted(set(int(row["case_spec"]["seed"]) for row in rows))
    by_id = {row["case_spec"]["case_id"]: row for row in rows}
    rhos = []
    curves = {}
    split = str(rows[0]["case_spec"]["split"])
    for seed in seed_ids:
        baseline = by_id[f"{split}_seed{seed}_global_broad_isotropic"]
        distances = []
        for fraction in fractions:
            token = str(fraction).replace(".", "p")
            distances.append(_profile_distance(baseline, by_id[f"{split}_seed{seed}_local_{token}"], axes))
        rhos.append(_spearman(fractions, distances))
        curves[str(seed)] = {"fractions": fractions, "distances": distances}
    bootstrap_seeds = list(range(int(lock["statistics"]["bootstrap_seed_start"]), int(lock["statistics"]["bootstrap_seed_start"]) + int(lock["statistics"]["bootstrap_count"])))
    ci = _bootstrap_mean_ci(rhos, bootstrap_seeds, float(protocol["multiple_testing_and_uncertainty"]["confidence_level"]))
    return {"passed": ci[0] > 0.0, "mean_seed_spearman": float(np.mean(rhos)), "ci": list(ci), "per_seed": dict(zip(map(str, seed_ids), rhos, strict=True)), "curves": curves}

def _continuity_ratios(rows: Sequence[Mapping[str, Any]], output_root: Path, axes: Sequence[str]) -> list[dict[str, Any]]:
    by_key: dict[tuple[int, str], list[Mapping[str, Any]]] = {}
    for row in rows:
        spec = row["case_spec"]
        if spec["kind"] == "continuity":
            by_key.setdefault((int(spec["seed"]), str(spec["continuity_path"])), []).append(row)
    result = []
    for (seed, path), items in sorted(by_key.items()):
        items = sorted(items, key=lambda row: float(row["case_spec"]["alpha"]))
        for left, right in zip(items, items[1:], strict=False):
            left_frame = np.load(output_root / left["canonical_relative_path"] / "gt_mass.npy", mmap_mode="r", allow_pickle=False)[-1]
            right_frame = np.load(output_root / right["canonical_relative_path"] / "gt_mass.npy", mmap_mode="r", allow_pickle=False)[-1]
            input_distance = _input_distance(np.asarray(left_frame), np.asarray(right_frame))
            output_distance = _output_distance(left, right, axes)
            result.append({
                "seed": seed,
                "path": path,
                "alpha_left": left["case_spec"]["alpha"],
                "alpha_right": right["case_spec"]["alpha"],
                "input_distance": input_distance,
                "output_distance": output_distance,
                "ratio": output_distance / max(input_distance, 1e-15),
            })
    return result

def _prediction_bound(reference_count: int, reference_total: int, evaluation_total: int, quantile: float) -> int:
    p = (reference_count + 1.0) / (reference_total + 2.0)
    return _binomial_quantile(evaluation_total, p, quantile)

def _evaluate_e4(
    calibration_rows: Sequence[Mapping[str, Any]],
    rows: Sequence[Mapping[str, Any]],
    output_root: Path,
    axes: Sequence[str],
    lock: Mapping[str, Any],
) -> dict[str, Any]:
    calibration_ratios = _continuity_ratios(calibration_rows, output_root, axes)
    evaluation_ratios = _continuity_ratios(rows, output_root, axes)
    threshold = float(np.quantile([item["ratio"] for item in calibration_ratios], float(lock["continuity"]["reference_quantile"])))
    calibration_exceed = sum(item["ratio"] > threshold for item in calibration_ratios)
    evaluation_exceed = sum(item["ratio"] > threshold for item in evaluation_ratios)
    allowed = _prediction_bound(calibration_exceed, len(calibration_ratios), len(evaluation_ratios), float(lock["statistics"]["binomial_prediction_quantile"]))
    nonfinite = any(not math.isfinite(item["ratio"]) for item in evaluation_ratios)
    exceedances = [item for item in evaluation_ratios if item["ratio"] > threshold]
    return {
        "passed": bool(not nonfinite and evaluation_exceed <= allowed),
        "reference_ratio_threshold": threshold,
        "calibration_exceedance_count": calibration_exceed,
        "evaluation_exceedance_count": evaluation_exceed,
        "allowed_evaluation_exceedance_count": allowed,
        "nonfinite_found": nonfinite,
        "exceedances": exceedances,
        "threshold_crossing_records": [],
        "unlogged_jump_found": bool(exceedances and evaluation_exceed > allowed),
    }

def _calibrated_feature_value(value: float, center: float, scale: float, lower: float, upper: float) -> float:
    return float(np.clip((value - center) / scale, lower, upper))

def _feature_clip_counts(rows: Sequence[Mapping[str, Any]], calibration: Mapping[str, Any]) -> dict[str, dict[str, int]]:
    result = {}
    for index, feature in enumerate(calibration["feature_order"]):
        if calibration["scale"][index] is None:
            continue
        lower = float(calibration["clip_lower"][index]); upper = float(calibration["clip_upper"][index])
        count = 0; total = 0
        for row in rows:
            if row["reference_feature_available"].get(feature):
                value = _calibrated_feature_value(float(row["reference_features"][feature]), float(calibration["center"][index]), float(calibration["scale"][index]), lower, upper)
                total += 1
                if abs(value - lower) <= 1e-12 or abs(value - upper) <= 1e-12:
                    count += 1
        result[feature] = {"clip_count": count, "total": total}
    return result

def _evaluate_e5(
    calibration_rows: Sequence[Mapping[str, Any]],
    rows: Sequence[Mapping[str, Any]],
    calibration: Mapping[str, Any],
    lock: Mapping[str, Any],
    axes: Sequence[str],
) -> dict[str, Any]:
    reference = _feature_clip_counts(calibration_rows, calibration)
    evaluation = _feature_clip_counts(rows, calibration)
    feature_results = {}
    passed = True
    for feature, eval_counts in evaluation.items():
        ref = reference[feature]
        allowed = _prediction_bound(ref["clip_count"], ref["total"], eval_counts["total"], float(lock["statistics"]["binomial_prediction_quantile"]))
        item_passed = eval_counts["clip_count"] <= allowed
        passed = passed and item_passed
        feature_results[feature] = {"calibration": ref, "evaluation": eval_counts, "allowed_evaluation_clip_count": allowed, "passed": item_passed}
    collapse = {}
    for axis in axes:
        values = [float(row["h11"][axis]["value"]) for row in rows if row["h11"][axis]["available"]]
        collapsed = len(values) < 2 or float(np.std(np.asarray(values, dtype=np.float64))) <= 1e-12
        collapse[axis] = collapsed
        passed = passed and not collapsed
    return {
        "passed": bool(passed),
        "feature_clip_results": feature_results,
        "axis_collapsed": collapse,
        "fit_split_only": calibration["fit_split"] == "design_calibration" and not calibration["validation_or_confirmation_used_for_fit"],
        "online_refit_disabled": calibration["online_refit_allowed"] is False,
    }

def _effective_rank(matrix: np.ndarray) -> float:
    centered = matrix - np.mean(matrix, axis=0, keepdims=True)
    singular = np.linalg.svd(centered, compute_uv=False)
    power = singular * singular
    if float(np.sum(power)) <= 1e-15:
        return 0.0
    probabilities = power / float(np.sum(power))
    positive = probabilities[probabilities > 0]
    return float(math.exp(-np.sum(positive * np.log(positive))))

def _evaluate_e6(
    calibration_rows: Sequence[Mapping[str, Any]],
    rows: Sequence[Mapping[str, Any]],
    decoder: Mapping[str, Any],
    e2: Mapping[str, Any],
) -> dict[str, Any]:
    axes = decoder["axis_order"]
    matrix = _h11_matrix(rows, axes)
    centered = matrix - np.mean(matrix, axis=0, keepdims=True)
    rank = int(np.linalg.matrix_rank(centered, tol=1e-10))
    identical_pairs = []
    correlations = {}
    for left_index, left in enumerate(axes):
        for right_index in range(left_index + 1, len(axes)):
            right = axes[right_index]
            if np.array_equal(matrix[:, left_index], matrix[:, right_index]):
                identical_pairs.append([left, right])
            correlations[f"{left}__{right}"] = _spearman(matrix[:, left_index], matrix[:, right_index])
    leave_one_out = {}
    for axis in axes:
        reduced = [item for item in axes if item != axis]
        x_cal = _h11_matrix(calibration_rows, reduced)
        y_cal = _matrix(calibration_rows, decoder["reference_feature_order"], "reference_features")
        x_eval = _h11_matrix(rows, reduced)
        y_eval = _matrix(rows, decoder["reference_feature_order"], "reference_features")
        x_cal_std, x_mean, x_scale = _standardize_fit(x_cal)
        y_cal_std, y_mean, y_scale = _standardize_fit(y_cal)
        coefficients = _ridge_fit(x_cal_std, y_cal_std, float(decoder["ridge_lambda"]))
        prediction = _ridge_predict(_standardize_apply(x_eval, x_mean, x_scale), coefficients)
        target = _standardize_apply(y_eval, y_mean, y_scale)
        leave_one_out[axis] = float(np.mean((prediction - target) ** 2))
    feature_ablation = {}
    for axis in axes:
        refs = list(rows[0]["h11"][axis]["evidence_feature_ids"])
        coverage = float(rows[0]["h11"][axis]["evidence_coverage"])
        feature_ablation[axis] = {
            "referenced_feature_count": len(refs),
            "single_feature_removal_retains_some_evidence": len(refs) > 1,
            "baseline_evidence_coverage": coverage,
        }
    passed = rank > 1 and not identical_pairs
    return {
        "passed": bool(passed),
        "numerical_rank": rank,
        "effective_rank": _effective_rank(matrix),
        "identical_axis_pairs": identical_pairs,
        "pairwise_spearman": correlations,
        "leave_one_axis_out_decoding_loss": leave_one_out,
        "feature_ablation_survival": feature_ablation,
        "random8_comparison": e2["aggregate_h11_minus_random8_median"],
        "pca8_status": "diagnostic_definition_frozen",
        "H12_C_status": "not_evaluated_no_fixed5_implementation",
        "H20_status": "not_evaluated_no_fixed5_implementation",
    }

def _evaluate_e7(rows: Sequence[Mapping[str, Any]], calibration: Mapping[str, Any]) -> dict[str, Any]:
    registry = load_feature_registry(DEFAULT_FEATURE_REGISTRY)
    by_id = {entry["id"]: entry for entry in registry["features"]}
    checks = {
        "Predictability_unavailable": all(not row["h11"]["Predictability"]["available"] for row in rows),
        "Recoverability_unavailable": all(not row["h11"]["Recoverability"]["available"] for row in rows),
        "Robustness_not_ready": all(row["h11"]["Robustness"]["status"] in {"UNAVAILABLE", "LIMITED"} for row in rows),
        "mode_count_contract_non_scoring": by_id["mode_count"]["score"] is False,
        "cluster_balance_contract_non_scoring": by_id["cluster_balance"]["score"] is False,
        "mode_count_not_fit_scored": calibration["center"][calibration["feature_order"].index("mode_count")] is None,
        "cluster_balance_not_fit_scored": calibration["center"][calibration["feature_order"].index("cluster_balance")] is None,
        "neutral_placeholder_not_evidence": all(
            all(not (axis["transport_value_is_neutral_placeholder"] and axis["available"]) for axis in row["h11"].values())
            for row in rows
        ),
    }
    return {"passed": all(checks.values()), "checks": checks}

def _evaluate_split(
    split: str,
    calibration_rows: Sequence[Mapping[str, Any]],
    rows: Sequence[Mapping[str, Any]],
    protocol: Mapping[str, Any],
    lock: Mapping[str, Any],
    calibration: Mapping[str, Any],
    decoder: Mapping[str, Any],
    output_root: Path,
    split_audit: Mapping[str, Any],
) -> dict[str, Any]:
    axes = decoder["axis_order"]
    e1 = {
        "passed": bool(split_audit["all_task3_validations_passed"] and split_audit["source_writeback_absent"]),
        "all_task3_validations_passed": split_audit["all_task3_validations_passed"],
        "source_writeback_absent": split_audit["source_writeback_absent"],
    }
    e2 = _evaluate_e2(calibration_rows, rows, decoder, protocol, lock)
    e3 = _evaluate_e3(rows, protocol, lock, axes)
    e4 = _evaluate_e4(calibration_rows, rows, output_root, axes, lock)
    e5 = _evaluate_e5(calibration_rows, rows, calibration, lock, axes)
    e6 = _evaluate_e6(calibration_rows, rows, decoder, e2)
    e7 = _evaluate_e7(rows, calibration)
    domains = {
        "E1_engineering_and_causal_integrity": e1,
        "E2_whole_system_information_preservation": e2,
        "E3_local_to_global_scale_response": e3,
        "E4_continuity_and_threshold_audit": e4,
        "E5_calibration_health": e5,
        "E6_axis_role_separation_and_compression": e6,
        "E7_missing_evidence_and_claim_limits": e7,
        "E8_auxiliary_basis_scope": {
            "passed": True,
            "critical": False,
            "Random8": "evaluated",
            "PCA8": "diagnostic_definition_frozen",
            "H12_C": "not_evaluated",
            "H20": "not_evaluated",
        },
    }
    critical_pass = all(domains[key]["passed"] for key in domains if key != "E8_auxiliary_basis_scope")
    return {
        "split": split,
        "case_count": len(rows),
        "seed_count": len(set(int(row["case_spec"]["seed"]) for row in rows)),
        "critical_domains_passed": bool(critical_pass),
        "domains": domains,
        "claim_boundary": protocol["decision_logic_after_execution"]["maximum_claim"],
    }

def _bundle_manifest(root: Path) -> dict[str, Any]:
    excluded_prefixes = ("cases/",)
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "task4_3_manifest.json":
            continue
        relative = path.relative_to(root).as_posix()
        files.append({"path": relative, "sha256": _sha256_file(path), "size_bytes": path.stat().st_size})
    return {
        "bundle_id": "fixed5axis_hdept_task4_3_whole_system_freeze_bundle_rc1",
        "hash_algorithm": "sha256",
        "file_count": len(files),
        "files": files,
        "contains_full_case_artifacts": any(item["path"].startswith(excluded_prefixes) for item in files),
    }

def _compact_freeze(output: Path, decision: Mapping[str, Any], validation_report: Mapping[str, Any], confirmation_report: Mapping[str, Any], calibration_audit: Mapping[str, Any], sample_lock: Mapping[str, Any], independent: Mapping[str, Any]) -> Path:
    target = output / "compact_freeze"
    target.mkdir(parents=True, exist_ok=False)
    payloads = {
        "task4_3_freeze_decision.json": decision,
        "task4_3_validation_summary.json": {key: validation_report[key] for key in ("split", "case_count", "seed_count", "critical_domains_passed", "domains", "claim_boundary")},
        "task4_3_final_confirmation_summary.json": {key: confirmation_report[key] for key in ("split", "case_count", "seed_count", "critical_domains_passed", "domains", "claim_boundary")},
        "task4_3_calibration_summary.json": calibration_audit,
        "task4_3_sample_size_lock.json": sample_lock,
        "task4_3_independent_validation_summary.json": independent,
    }
    for name, payload in payloads.items():
        _write_json(target / name, payload)
    _write_json(target / "task4_3_compact_manifest.json", _bundle_manifest(target))
    return target

def generate_task4_3_bundle(
    output_dir: str | Path,
    *,
    protocol_path: str | Path = DEFAULT_PROTOCOL,
    execution_lock_path: str | Path = DEFAULT_EXECUTION_LOCK,
    test_mode: bool = False,
) -> Path:
    output = Path(output_dir)
    if output.exists():
        raise ValueError(f"output already exists: {output}")
    protocol_file = Path(protocol_path)
    lock_file = Path(execution_lock_path)
    protocol = _load_json(protocol_file)
    lock = _load_json(lock_file)
    if protocol.get("status") != "preregistered_design_only_not_executed":
        raise ValueError("Task 4-2 protocol is not frozen")
    if lock.get("status") != "locked_before_task4_3_generation":
        raise ValueError("Task 4-3 execution lock is not frozen")
    if test_mode:
        lock = copy.deepcopy(lock)
        lock["calibration"]["minimum_available_samples"] = int(lock["test_mode"]["minimum_available_samples"])
        lock["statistics"]["bootstrap_count"] = int(lock["test_mode"]["bootstrap_count"])
    output.mkdir(parents=True, exist_ok=False)
    _write_json(output / "protocol_snapshot.json", protocol)
    _write_json(output / "execution_lock_snapshot.json", lock)
    if test_mode:
        seed_count = int(lock["test_mode"]["seed_count"])
        calibration, calibration_audit = _fit_calibration(protocol_file, lock_file, DEFAULT_FEATURE_REGISTRY, protocol, lock, seed_count)
        sample_lock = {
            "lock_id": "task4_3_test_only_sample_lock",
            "status": "test_only_not_scientific",
            "selected_seed_count_per_split": seed_count,
            "validation_generated_before_lock": False,
            "final_confirmation_generated_before_validation_freeze": False,
        }
    else:
        seed_count, calibration, calibration_audit, sample_lock = _select_sample_size(protocol_file, lock_file, DEFAULT_FEATURE_REGISTRY, protocol, lock)
    calibration_path = output / "fixed5axis_hdept_task4_3_calibration_rc1.json"
    _write_json(calibration_path, calibration)
    _write_json(output / "task4_3_calibration_audit.json", calibration_audit)
    _write_json(output / "task4_3_sample_size_lock.json", sample_lock)

    calibration_rows, calibration_split_audit = _generate_split(output, "design_calibration", protocol, lock, seed_count, calibration_path)
    _write_jsonl(output / "case_summaries_design_calibration.jsonl", calibration_rows)
    _write_json(output / "design_calibration_split_audit.json", calibration_split_audit)
    decoder = _decoder_lock(calibration_rows, protocol, lock, calibration)
    _write_json(output / "task4_3_decoder_lock.json", decoder)

    validation_rows, validation_audit = _generate_split(output, "validation", protocol, lock, seed_count, calibration_path)
    _write_jsonl(output / "case_summaries_validation.jsonl", validation_rows)
    _write_json(output / "validation_split_audit.json", validation_audit)
    validation_report = _evaluate_split("validation", calibration_rows, validation_rows, protocol, lock, calibration, decoder, output, validation_audit)
    _write_json(output / "task4_3_validation_report.json", validation_report)
    validation_freeze_hash = _sha256_file(output / "task4_3_validation_report.json")
    sample_lock["validation_report_frozen_before_final_confirmation_generation"] = True
    sample_lock["validation_report_sha256"] = validation_freeze_hash
    _write_json(output / "task4_3_sample_size_lock.json", sample_lock)

    confirmation_rows, confirmation_audit = _generate_split(output, "final_confirmation", protocol, lock, seed_count, calibration_path)
    _write_jsonl(output / "case_summaries_final_confirmation.jsonl", confirmation_rows)
    _write_json(output / "final_confirmation_split_audit.json", confirmation_audit)
    confirmation_report = _evaluate_split("final_confirmation", calibration_rows, confirmation_rows, protocol, lock, calibration, decoder, output, confirmation_audit)
    _write_json(output / "task4_3_final_confirmation_report.json", confirmation_report)

    split_ids = {
        "design_calibration": {row["case_spec"]["case_id"] for row in calibration_rows},
        "validation": {row["case_spec"]["case_id"] for row in validation_rows},
        "final_confirmation": {row["case_spec"]["case_id"] for row in confirmation_rows},
    }
    split_disjoint = not (
        split_ids["design_calibration"] & split_ids["validation"]
        or split_ids["design_calibration"] & split_ids["final_confirmation"]
        or split_ids["validation"] & split_ids["final_confirmation"]
    )
    scientific_pass = bool(validation_report["critical_domains_passed"] and confirmation_report["critical_domains_passed"] and split_disjoint)
    decision = {
        "decision_id": "fixed5axis_hdept_task4_3_freeze_decision_rc1",
        "test_mode": bool(test_mode),
        "decision": (
            "test_only_bundle_generated"
            if test_mode
            else (
                "eligible_for_task5_diagnostic_only"
                if scientific_pass
                else "blocked_scientific_bridge_failure"
            )
        ),
        "scientific_gate_passed": bool(scientific_pass and not test_mode),
        "split_identity_disjoint": split_disjoint,
        "selected_seed_count_per_split": seed_count,
        "validation_critical_domains_passed": validation_report["critical_domains_passed"],
        "final_confirmation_critical_domains_passed": confirmation_report["critical_domains_passed"],
        "maximum_claim": protocol["decision_logic_after_execution"]["maximum_claim"],
        "real_world_or_closed_loop_claim": False,
        "task5_authorized": bool(scientific_pass and not test_mode),
    }
    _write_json(output / "task4_3_freeze_decision.json", decision)

    from .whole_system_validator import validate_task4_3_bundle
    independent = validate_task4_3_bundle(output, write_report=False)
    _write_json(output / "task4_3_independent_validation_report.json", independent)
    _compact_freeze(output, decision, validation_report, confirmation_report, calibration_audit, sample_lock, independent)
    _write_json(output / "task4_3_manifest.json", _bundle_manifest(output))
    return output

def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--protocol", default=str(DEFAULT_PROTOCOL))
    parser.add_argument("--execution-lock", default=str(DEFAULT_EXECUTION_LOCK))
    parser.add_argument("--test-mode", action="store_true")
    return parser

def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    output = generate_task4_3_bundle(
        args.output_dir,
        protocol_path=args.protocol,
        execution_lock_path=args.execution_lock,
        test_mode=bool(args.test_mode),
    )
    print(output)
    return 0
