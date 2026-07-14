"""Task 4用の決定論的な固定5軸合成シナリオ。"""
from __future__ import annotations

import csv
import hashlib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from fixed5axis_hdept_bridge_task2.canonical import (
    GENESIS_HASH,
    _compute_gt_hash,
    _compute_history_chain_hash,
)
from fixed5axis_hdept_bridge_task2.contracts import AXIS_BINS, AXIS_NAMES

SCENARIOS = (
    "stable_broad",
    "locked_fixation",
    "smooth_adaptation",
    "structured_exploration",
    "noisy_expansion",
    "oscillation",
    "boundary_divergence",
    "slow_fixation",
    "shock_full_recovery",
    "shock_partial_recovery",
    "shock_no_recovery",
)


@lru_cache(maxsize=1)
def _coordinates() -> np.ndarray:
    mesh = np.meshgrid(*([np.asarray(AXIS_BINS, dtype=np.float64)] * 5), indexing="ij")
    return np.stack([axis.reshape(-1) for axis in mesh], axis=1)


def _normalize(mass: np.ndarray) -> np.ndarray:
    value = np.asarray(mass, dtype=np.float64).reshape(5, 5, 5, 5, 5)
    value = np.maximum(value, 0.0) + 1e-15
    value /= float(np.sum(value, dtype=np.float64))
    return value.astype(np.float64, copy=False)


def _gaussian(center: Sequence[float], scale: Sequence[float]) -> np.ndarray:
    coordinates = _coordinates()
    center_array = np.asarray(center, dtype=np.float64)
    scale_array = np.asarray(scale, dtype=np.float64)
    exponent = -0.5 * np.sum(((coordinates - center_array) / scale_array) ** 2, axis=1)
    return _normalize(np.exp(exponent))


def _mixture(components: Sequence[tuple[float, Sequence[float], Sequence[float]]]) -> np.ndarray:
    combined = np.zeros((5, 5, 5, 5, 5), dtype=np.float64)
    total_weight = 0.0
    for weight, center, scale in components:
        combined += float(weight) * _gaussian(center, scale)
        total_weight += float(weight)
    if total_weight <= 0.0:
        raise ValueError("mixture weight must be positive")
    return _normalize(combined)


def _jitter(rng: np.random.Generator, magnitude: float = 0.015) -> np.ndarray:
    return rng.normal(0.0, magnitude, size=5)


def _clip_center(center: Sequence[float]) -> np.ndarray:
    return np.clip(np.asarray(center, dtype=np.float64), 0.03, 0.97)


def generate_trajectory(scenario: str, seed: int, horizon: int = 14) -> np.ndarray:
    if scenario not in SCENARIOS:
        raise ValueError(f"unsupported scenario: {scenario}")
    if horizon < 5:
        raise ValueError("horizon must be at least 5")
    rng = np.random.default_rng(int(seed))
    healthy = np.asarray([0.66, 0.72, 0.30, 0.68, 0.76], dtype=np.float64)
    unhealthy = np.asarray([0.18, 0.28, 0.91, 0.08, 0.16], dtype=np.float64)
    frames: list[np.ndarray] = []
    for t in range(horizon):
        phase = t / max(horizon - 1, 1)
        if scenario == "stable_broad":
            center = _clip_center(healthy + 0.010 * np.sin(0.45 * t + np.arange(5)) + _jitter(rng, 0.002))
            scale = np.asarray([0.19, 0.18, 0.16, 0.19, 0.17])
            frame = _gaussian(center, scale)
        elif scenario == "locked_fixation":
            center = _clip_center(unhealthy + _jitter(rng, 0.001))
            frame = _gaussian(center, [0.050, 0.050, 0.045, 0.045, 0.050])
        elif scenario == "smooth_adaptation":
            target = np.asarray([0.78, 0.82, 0.20, 0.80, 0.84])
            center = _clip_center(healthy * (1.0 - phase) + target * phase + _jitter(rng, 0.002))
            frame = _gaussian(center, [0.16, 0.16, 0.14, 0.17, 0.15])
        elif scenario == "structured_exploration":
            offset = np.asarray([0.17, 0.12, -0.05, 0.18, 0.10])
            center_a = _clip_center(healthy - 0.55 * offset + _jitter(rng, 0.003))
            center_b = _clip_center(healthy + 0.55 * offset + _jitter(rng, 0.003))
            weight = 0.5 + 0.08 * np.sin(0.55 * t)
            frame = _mixture(
                [
                    (weight, center_a, [0.10, 0.10, 0.09, 0.10, 0.10]),
                    (1.0 - weight, center_b, [0.10, 0.10, 0.09, 0.10, 0.10]),
                ]
            )
        elif scenario == "noisy_expansion":
            components: list[tuple[float, Sequence[float], Sequence[float]]] = []
            for index in range(8):
                boundary = rng.choice([0.02, 0.98], size=5)
                interior_mask = rng.random(5) < 0.35
                boundary[interior_mask] = rng.uniform(0.20, 0.80, size=int(np.sum(interior_mask)))
                weight = 0.075 + 0.015 * ((index + t) % 3)
                components.append((weight, boundary, [0.040, 0.045, 0.040, 0.045, 0.040]))
            noisy = _mixture(components)
            uniform = np.full((5, 5, 5, 5, 5), 1.0 / 3125.0, dtype=np.float64)
            frame = _normalize(0.72 * noisy + 0.28 * uniform)
        elif scenario == "oscillation":
            direction = np.asarray([0.16, -0.10, 0.18, -0.18, -0.14])
            sign = -1.0 if t % 2 else 1.0
            center = _clip_center(healthy + sign * direction + _jitter(rng, 0.0015))
            frame = _gaussian(center, [0.14, 0.14, 0.13, 0.14, 0.13])
        elif scenario == "boundary_divergence":
            accelerated = phase**1.6
            center = _clip_center(healthy * (1.0 - accelerated) + unhealthy * accelerated + _jitter(rng, 0.002))
            scale = np.asarray([0.17, 0.16, 0.14, 0.17, 0.15]) * (1.0 - 0.35 * accelerated)
            frame = _gaussian(center, scale)
        elif scenario == "slow_fixation":
            center = _clip_center(healthy * (1.0 - phase) + unhealthy * phase + _jitter(rng, 0.0015))
            scale = np.asarray([0.21, 0.20, 0.18, 0.21, 0.19]) * (1.0 - 0.72 * phase)
            frame = _gaussian(center, scale)
        else:
            shock_start = 4
            shock_peak = 6
            if t < shock_start:
                center = healthy + _jitter(rng, 0.0015)
            elif t <= shock_peak:
                shock_phase = (t - shock_start + 1) / (shock_peak - shock_start + 1)
                center = healthy * (1.0 - shock_phase) + unhealthy * shock_phase
            else:
                recovery_phase = (t - shock_peak) / max(horizon - 1 - shock_peak, 1)
                if scenario == "shock_full_recovery":
                    recovery_target = healthy
                elif scenario == "shock_partial_recovery":
                    recovery_target = 0.55 * healthy + 0.45 * unhealthy
                else:
                    recovery_target = 0.10 * healthy + 0.90 * unhealthy
                center = unhealthy * (1.0 - recovery_phase) + recovery_target * recovery_phase
                center = center + _jitter(rng, 0.0015)
            frame = _gaussian(_clip_center(center), [0.15, 0.15, 0.13, 0.16, 0.14])
        frames.append(frame)
    return np.stack(frames).astype(np.float64, copy=False)


def make_ledger_rows(trajectory_id: str, frames: np.ndarray) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    previous_gt_hash = ""
    chain_hash = GENESIS_HASH
    for t, frame in enumerate(frames):
        source_state_hash = hashlib.sha256(f"task4:{trajectory_id}:{t}".encode("utf-8")).hexdigest()
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
                "source_state_ref": f"synthetic/{trajectory_id}/step_{t:06d}.json",
                "source_state_hash": source_state_hash,
            }
        )
        previous_gt_hash = gt_hash
    return rows


def write_canonical_trajectory(root: Path, scenario: str, seed: int, horizon: int) -> dict[str, Any]:
    trajectory_id = f"task4_{scenario}_seed{seed}"
    frames = generate_trajectory(scenario, seed, horizon)
    rows = make_ledger_rows(trajectory_id, frames)
    root.mkdir(parents=True, exist_ok=False)
    np.save(root / "gt_mass.npy", frames, allow_pickle=False)
    fieldnames = list(rows[0])
    with (root / "history_ledger.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
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
        "generator": "fixed5axis_hdept_task4_synthetic_rc1",
        "scenario": scenario,
        "seed": seed,
        "forbidden_source_files_read": [],
        "source_writeback_performed": False,
    }
    (root / "provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "contract_version": "fixed5axis_gk_rc1",
        "canonical_manifest_excludes_derived": True,
        "file_count": 3,
        "files": [
            {"relative_path": "gt_mass.npy"},
            {"relative_path": "history_ledger.csv"},
            {"relative_path": "provenance.json"},
        ],
    }
    (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"trajectory_id": trajectory_id, "frames": frames, "ledger": rows}


def centroid(frame: np.ndarray) -> np.ndarray:
    return np.sum(frame.reshape(-1, 1) * _coordinates(), axis=0)
