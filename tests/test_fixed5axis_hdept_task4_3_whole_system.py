from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from fixed5axis_hdept_bridge_task4.whole_system import (  # noqa: E402
    DEFAULT_EXECUTION_LOCK,
    DEFAULT_PROTOCOL,
    CaseSpec,
    _case_plan,
    _fit_calibration,
    _input_distance,
    _load_json,
    _planning_diagnostics,
    _random8_definition,
    generate_case_frames,
)
from fixed5axis_hdept_bridge_task2.contracts import (  # noqa: E402
    DEFAULT_FEATURE_REGISTRY,
    DEFAULT_MEANING_PATCH,
)


def test_execution_lock_is_frozen_before_generation() -> None:
    protocol = _load_json(DEFAULT_PROTOCOL)
    lock = _load_json(DEFAULT_EXECUTION_LOCK)
    assert protocol["status"] == "preregistered_design_only_not_executed"
    assert lock["status"] == "locked_before_task4_3_generation"
    assert lock["parent_protocol"] == protocol["protocol_id"]
    assert lock["generation"]["evaluation_t"] == lock["generation"]["horizon"] - 1
    assert lock["sample_size"]["candidate_seed_counts"] == [12, 24, 36, 48, 64]
    assert lock["random8"]["ensemble_count"] == 32
    assert lock["statistics"]["bootstrap_count"] == 2000


def test_case_plan_is_deterministic_and_contains_registered_families() -> None:
    protocol = _load_json(DEFAULT_PROTOCOL)
    lock = _load_json(DEFAULT_EXECUTION_LOCK)
    first = _case_plan(protocol, lock, "validation", 2)
    second = _case_plan(protocol, lock, "validation", 2)
    assert first == second
    assert len(first) == 44
    assert len({case.case_id for case in first}) == len(first)
    assert sum(case.kind == "global" for case in first) == 14
    assert sum(case.kind == "local_scale" for case in first) == 14
    assert sum(case.kind == "continuity" for case in first) == 16
    registered = {item["id"] for item in protocol["controlled_distribution_families"]}
    observed = {case.family for case in first if case.kind == "global"}
    assert observed == registered


def test_generated_frames_are_deterministic_finite_and_normalized() -> None:
    spec = CaseSpec(
        split="validation",
        seed=5100,
        case_id="unit_correlated",
        kind="global",
        family="correlated_whole_system",
        strength=0.7,
    )
    first = generate_case_frames(spec, 9)
    second = generate_case_frames(spec, 9)
    assert np.array_equal(first, second)
    assert first.shape == (9, 5, 5, 5, 5, 5)
    assert first.dtype == np.float64
    assert np.all(np.isfinite(first))
    assert np.all(first >= 0.0)
    assert np.allclose(np.sum(first, axis=(1, 2, 3, 4, 5)), 1.0, atol=1e-12)


def test_local_perturbation_input_distance_increases_with_mass_fraction() -> None:
    baseline = generate_case_frames(
        CaseSpec("validation", 5100, "baseline", "global", "broad_isotropic", strength=0.0),
        9,
    )[-1]
    fractions = [0.005, 0.01, 0.02, 0.05, 0.10, 0.20, 0.40]
    distances = []
    for fraction in fractions:
        frames = generate_case_frames(
            CaseSpec("validation", 5100, f"local_{fraction}", "local_scale", "matched_local_perturbation", mass_fraction=fraction),
            9,
        )
        distances.append(_input_distance(baseline, frames[-1]))
    assert all(right > left for left, right in zip(distances, distances[1:]))


def test_calibration_marks_constants_non_scoring_without_scale_floor() -> None:
    protocol = _load_json(DEFAULT_PROTOCOL)
    lock = copy.deepcopy(_load_json(DEFAULT_EXECUTION_LOCK))
    lock["calibration"]["minimum_available_samples"] = 2
    calibration, audit = _fit_calibration(
        Path(DEFAULT_PROTOCOL),
        Path(DEFAULT_EXECUTION_LOCK),
        Path(DEFAULT_FEATURE_REGISTRY),
        protocol,
        lock,
        2,
    )
    assert audit["status"] == "pass"
    assert calibration["meaning_patch_hash"] == hashlib.sha256(Path(DEFAULT_MEANING_PATCH).read_bytes()).hexdigest()
    assert calibration["validation_or_confirmation_used_for_fit"] is False
    for feature in ("mode_count", "cluster_balance"):
        index = calibration["feature_order"].index(feature)
        assert calibration["center"][index] is None
        assert calibration["scale"][index] is None
        assert calibration["clip_lower"][index] is None
        assert calibration["clip_upper"][index] is None
    assert "scale_floor_fallback" not in calibration["scale_source"]


def test_calibration_only_planning_does_not_read_evaluation_splits() -> None:
    protocol = _load_json(DEFAULT_PROTOCOL)
    lock = copy.deepcopy(_load_json(DEFAULT_EXECUTION_LOCK))
    lock["calibration"]["minimum_available_samples"] = 2
    lock["statistics"]["bootstrap_count"] = 50
    calibration, _ = _fit_calibration(
        Path(DEFAULT_PROTOCOL),
        Path(DEFAULT_EXECUTION_LOCK),
        Path(DEFAULT_FEATURE_REGISTRY),
        protocol,
        lock,
        2,
    )
    diagnostics = _planning_diagnostics(protocol, lock, calibration, 2)
    assert diagnostics["seed_count"] == 2
    assert len(diagnostics["axis_order"]) >= 2
    assert diagnostics["mean_scale_response_spearman"] > 0.0
    assert diagnostics["mean_global_profile_effect"] > 0.0


def test_random8_definition_is_fixed_and_orthonormal() -> None:
    lock = _load_json(DEFAULT_EXECUTION_LOCK)
    first = _random8_definition(30, lock)
    second = _random8_definition(30, lock)
    assert first == second
    assert len(first["members"]) == 32
    assert first["dimension"] == 8
    for member in first["members"]:
        matrix = np.asarray(member["matrix"], dtype=np.float64)
        assert np.allclose(matrix.T @ matrix, np.eye(8), atol=1e-10)
