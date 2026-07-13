from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from fixed5axis_hdept_observation_bridge_rc1 import (  # noqa: E402
    AXIS_BINS,
    AXIS_NAMES,
    GENESIS_HASH,
    _canonical_json,
    _compute_gt_hash,
    _compute_history_chain_hash,
    build_observation,
    load_feature_registry,
)


def _dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _distribution(step: int, *, future_variant: float = 0.0) -> np.ndarray:
    grids = np.meshgrid(*([np.asarray(AXIS_BINS, dtype=np.float64)] * 5), indexing="ij")
    center = np.asarray(
        [
            0.32 + 0.025 * step,
            0.61 - 0.018 * step,
            0.42 + 0.014 * step,
            0.55 + 0.020 * np.sin(step),
            0.68 - 0.012 * step,
        ],
        dtype=np.float64,
    )
    if step >= 5:
        center[0] += future_variant
        center[3] -= 0.5 * future_variant
    squared = sum(((grid - center[index]) / (0.17 + 0.015 * index)) ** 2 for index, grid in enumerate(grids))
    value = np.exp(-0.5 * squared)
    value += 1e-10
    value /= value.sum(dtype=np.float64)
    return value.astype(np.float64)


def _make_canonical(root: Path, *, frames: int = 6, future_variant: float = 0.0) -> Path:
    root.mkdir(parents=True)
    trajectory_id = "traj_fixed5_hdept_task2"
    mass = np.stack([_distribution(step, future_variant=future_variant) for step in range(frames)])
    np.save(root / "gt_mass.npy", mass, allow_pickle=False)
    fields = [
        "trajectory_id", "source_trajectory_id", "t", "phase", "gt_row_index", "gt_hash",
        "previous_gt_hash", "history_chain_hash", "delta_t", "continuity_status",
        "admissible_for_research", "source_state_ref", "source_state_hash",
    ]
    rows = []
    previous_gt_hash = ""
    chain_hash = GENESIS_HASH
    for step in range(frames):
        source_hash = hashlib.sha256(f"source-state-{step}".encode()).hexdigest()
        gt_hash = _compute_gt_hash(
            contract_version="fixed5axis_gk_rc1",
            trajectory_id=trajectory_id,
            t=step,
            distribution=mass[step],
            source_state_hash=source_hash,
        )
        chain_hash = _compute_history_chain_hash(chain_hash, gt_hash, step)
        rows.append(
            {
                "trajectory_id": trajectory_id,
                "source_trajectory_id": trajectory_id,
                "t": step,
                "phase": "pre_transition",
                "gt_row_index": step,
                "gt_hash": gt_hash,
                "previous_gt_hash": previous_gt_hash,
                "history_chain_hash": chain_hash,
                "delta_t": 0 if step == 0 else 1,
                "continuity_status": "initial" if step == 0 else "continuous",
                "admissible_for_research": True,
                "source_state_ref": f"states/step_{step:06d}.npz",
                "source_state_hash": source_hash,
            }
        )
        previous_gt_hash = gt_hash
    with (root / "history_ledger.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)
    _dump(
        root / "provenance.json",
        {
            "contract_version": "fixed5axis_gk_rc1",
            "axis_order": list(AXIS_NAMES),
            "axis_bins": list(AXIS_BINS),
            "gt_shape": [5, 5, 5, 5, 5],
            "gt_dtype": "float64",
            "gt_phase": "pre_transition",
            "trajectory_id": trajectory_id,
            "forbidden_source_files_read": [],
            "source_writeback_performed": False,
        },
    )
    _dump(
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


def _tree_hash(path: Path) -> dict[str, str]:
    return {
        item.relative_to(path).as_posix(): hashlib.sha256(item.read_bytes()).hexdigest()
        for item in sorted(path.rglob("*"))
        if item.is_file()
    }


def _make_calibration(path: Path) -> Path:
    registry_path = ROOT / "configs" / "fixed5axis_hdept_feature_registry_rc1.json"
    registry = load_feature_registry(registry_path)
    registry_hash = hashlib.sha256(registry_path.read_bytes()).hexdigest()
    center = []
    scale = []
    lower = []
    upper = []
    for entry in registry["features"]:
        scoring = bool(entry.get("score", True)) and float(entry["cap"]) > 0.0
        center.append(0.0 if scoring else None)
        scale.append(1.0 if scoring else None)
        lower.append(-3.0 if scoring else None)
        upper.append(3.0 if scoring else None)
    _dump(
        path,
        {
            "calibration_version": "task2_test_fixture_only",
            "feature_registry_hash": registry_hash,
            "feature_order": [entry["id"] for entry in registry["features"]],
            "center": center,
            "scale": scale,
            "clip_lower": lower,
            "clip_upper": upper,
            "fit_dataset_ids": ["synthetic_unit_test_only"],
            "fit_trajectory_ids_hash": "a" * 64,
            "fit_time_boundary": {"maximum_t": 4},
            "normalization_method": "zscore",
            "creation_code_hash": "b" * 64,
        },
    )
    return path


def _read_outputs(root: Path) -> dict[str, object]:
    return {
        name: json.loads((root / name).read_text(encoding="utf-8"))
        for name in ("identity.json", "features.json", "m_observation.json", "audit.json", "provenance.json", "manifest.json")
    }


def test_feature_only_builder_preserves_source_and_unavailability_semantics(tmp_path: Path) -> None:
    source = _make_canonical(tmp_path / "canonical")
    before = _tree_hash(source)
    output = build_observation(source, 4, tmp_path / "output")
    after = _tree_hash(source)
    assert before == after

    values = _read_outputs(output)
    features = values["features.json"]["features"]
    observation = values["m_observation.json"]
    audit = values["audit.json"]
    assert len(features) == 47
    assert [item["feature_id"] for item in features] == [
        item["id"] for item in load_feature_registry(ROOT / "configs" / "fixed5axis_hdept_feature_registry_rc1.json")["features"]
    ]
    assert all(item["value"] is None and item["confidence"] == 0.0 for item in features if item["derivation_status"].startswith("reserved_"))
    assert observation["global_observation_status"] == "HOLD_RECOMMENDED"
    assert all(not axis["available"] for axis in observation["h11"].values())
    assert all(axis["transport_value"] == 0.5 and axis["transport_value_is_neutral_placeholder"] for axis in observation["h11"].values())
    assert audit["future_suffix_read"] is False
    assert audit["truth_used"] is False
    assert audit["source_writeback_performed"] is False
    assert audit["neutral_placeholder_used_as_evidence"] is False


def test_calibrated_builder_is_deterministic_and_emits_limited_h11(tmp_path: Path) -> None:
    source = _make_canonical(tmp_path / "canonical")
    calibration = _make_calibration(tmp_path / "calibration.json")
    first = build_observation(source, 4, tmp_path / "out_a", calibration_path=calibration)
    second = build_observation(source, 4, tmp_path / "out_b", calibration_path=calibration)
    for name in ("identity.json", "features.json", "m_observation.json", "audit.json", "provenance.json", "manifest.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes()

    observation = json.loads((first / "m_observation.json").read_text(encoding="utf-8"))
    assert observation["global_observation_status"] == "LIMITED"
    assert list(observation["h11"]) == [
        "Stability", "AdaptabilityStar", "Exploration", "Efficiency", "Robustness",
        "StructuralDiversity", "TrajectoryDynamics", "Predictability", "Coherence",
        "Recoverability", "NoveltyQuality",
    ]
    assert any(axis["available"] for axis in observation["h11"].values())
    assert observation["h11"]["Predictability"]["status"] == "UNAVAILABLE"
    assert observation["h11"]["Recoverability"]["status"] == "UNAVAILABLE"
    assert all(axis["status"] != "READY" for axis in observation["h11"].values())
    available_values = [axis["value"] for axis in observation["h11"].values() if axis["available"]]
    assert available_values
    assert all(0.0 <= value <= 1.0 for value in available_values)
    assert len({round(value, 12) for value in available_values}) > 1


def test_same_prefix_different_future_produces_identical_output(tmp_path: Path) -> None:
    source_a = _make_canonical(tmp_path / "canonical_a", future_variant=0.0)
    source_b = _make_canonical(tmp_path / "canonical_b", future_variant=0.20)
    calibration = _make_calibration(tmp_path / "calibration.json")
    out_a = build_observation(source_a, 4, tmp_path / "out_a", calibration_path=calibration)
    out_b = build_observation(source_b, 4, tmp_path / "out_b", calibration_path=calibration)
    for name in ("identity.json", "features.json", "m_observation.json", "audit.json", "provenance.json", "manifest.json"):
        assert (out_a / name).read_bytes() == (out_b / name).read_bytes()


def test_initial_frame_reports_insufficient_history_and_cli_runs(tmp_path: Path) -> None:
    source = _make_canonical(tmp_path / "canonical", frames=1)
    output = build_observation(source, 0, tmp_path / "direct")
    observation = json.loads((output / "m_observation.json").read_text(encoding="utf-8"))
    assert observation["global_observation_status"] == "INSUFFICIENT_HISTORY"

    cli_output = tmp_path / "cli"
    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "fixed5axis_hdept_observation_bridge_rc1.py"),
            "--trajectory-dir", str(source),
            "--current-t", "0",
            "--output-dir", str(cli_output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert str(cli_output) in completed.stdout
    assert (cli_output / "manifest.json").is_file()
