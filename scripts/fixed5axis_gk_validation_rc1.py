"""固定5軸 G_t・K_t 採用検証 RC1。

正本整合、外部要因応答、完全分布の情報十分性、K_t履歴価値を
fit/validation/holdout分離で検証する。関係場やリスク予測器は固定しない。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import sys
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from pseudo_reality.distribution_terrain_v3_2_2 import (  # noqa: E402
    DistributionTerrainV322Config,
    DistributionTerrainV322World,
)
from fixed5axis_gk_rc1 import (  # noqa: E402
    AXIS_BINS,
    AXIS_NAMES,
    HistoryAccumulator,
    build_corpus,
    load_contract as load_foundation_contract,
    validate_trajectory_artifact,
)

DEFAULT_CONFIG = ROOT / "configs" / "fixed5axis_gk_validation_rc1.json"
EXTERNAL_KEYS = (
    "external_resource_supply",
    "external_demand",
    "external_competition_pressure",
    "external_information_noise",
    "external_shock",
    "external_constraint_pressure",
)
SINGLE_SCENARIOS = (
    "resource_shortage",
    "demand_increase",
    "competition_pressure",
    "information_noise",
    "shock",
    "constraint_pressure",
)
COMPOSITE_SCENARIOS = ("resource_noise_composite", "pressure_constraint_composite")


class ValidationError(ValueError):
    """検証契約または成果物の不整合。"""


def _json_load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _json_dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): _sha256_file(path)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _config_hash(config: Mapping[str, Any]) -> str:
    payload = json.dumps(config, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_validation_config(path: str | Path, profile: str) -> tuple[dict[str, Any], dict[str, Any]]:
    config = _json_load(Path(path))
    if config.get("contract_version") != "fixed5axis_gk_validation_rc1":
        raise ValidationError("unsupported validation contract")
    profiles = config.get("profiles", {})
    if profile not in profiles:
        raise ValidationError(f"unknown profile {profile!r}")
    selected = dict(profiles[profile])
    for split in ("fit", "validation", "holdout"):
        seeds = selected.get(f"{split}_seeds")
        if not isinstance(seeds, list) or not seeds or any(not isinstance(seed, int) for seed in seeds):
            raise ValidationError(f"invalid {split}_seeds")
    names = selected.get("scenario_names")
    if not isinstance(names, list) or "baseline" not in names:
        raise ValidationError("scenario_names must include baseline")
    if int(selected["pulse_start"]) < 0 or int(selected["pulse_end"]) <= int(selected["pulse_start"]):
        raise ValidationError("invalid pulse interval")
    if int(selected["transitions"]) < int(selected["pulse_end"]):
        raise ValidationError("transitions must cover the pulse interval")
    return config, selected


def _external_vector(config: Mapping[str, Any], split: str, scenario: str, active: bool) -> dict[str, float]:
    result = {key: 0.0 for key in EXTERNAL_KEYS}
    if not active or scenario == "baseline":
        return result
    raw = config["scenario_external_vectors"].get(scenario)
    if raw is None:
        raise ValidationError(f"missing scenario vector {scenario}")
    strength = float(config["strength_by_split"][split])
    for key, multiplier in raw.items():
        if key not in result:
            raise ValidationError(f"unknown external factor {key}")
        result[key] = float(np.clip(strength * float(multiplier), -1.0, 1.0))
    return result


def _trajectory_id(split: str, scenario: str, seed: int) -> str:
    return f"traj_{split}_{scenario}_seed{seed:03d}"


def _generate_source_trajectory(
    source_root: Path,
    config: Mapping[str, Any],
    profile: Mapping[str, Any],
    *,
    split: str,
    scenario: str,
    seed: int,
) -> None:
    trajectory_id = _trajectory_id(split, scenario, seed)
    trajectory_dir = source_root / "trajectories" / trajectory_id
    states_dir = trajectory_dir / "states"
    states_dir.mkdir(parents=True, exist_ok=False)
    transitions = int(profile["transitions"])
    pulse_start = int(profile["pulse_start"])
    pulse_end = int(profile["pulse_end"])
    world = DistributionTerrainV322World(DistributionTerrainV322Config(seed=seed))
    steps: list[dict[str, Any]] = []
    for t in range(transitions + 1):
        active = pulse_start <= t < pulse_end and t < transitions
        external = _external_vector(config, split, scenario, active)
        world.set_external_factors(external)
        state_ref = f"states/step_{t:06d}.npz"
        np.savez_compressed(trajectory_dir / state_ref, distribution=np.asarray(world.distribution, dtype=np.float64))
        steps.append({
            "trajectory_id": trajectory_id,
            "step": t,
            "phase": "pre_transition",
            "state_ref": state_ref,
            "history_available_through_step": None if t == 0 else t - 1,
            "observed_external_input": external,
            "observed_events": ["external_pulse"] if active else [],
            "observed_action": None,
        })
        if t < transitions:
            world.step()
    metadata = {
        "trajectory_id": trajectory_id,
        "scenario_id": scenario,
        "seed": seed,
        "initial_state_id": "distribution_terrain_v3_2_2_default_reset",
        "world_module": "pseudo_reality.distribution_terrain_v3_2_2",
        "world_class": "DistributionTerrainV322World",
        "world_version": "PseudoReality v3.3",
        "config_version": "fixed5axis_gk_validation_rc1",
        "total_steps": transitions,
        "dataset_split": split,
    }
    _json_dump(trajectory_dir / "metadata.json", metadata)
    _write_jsonl(trajectory_dir / "steps.jsonl", steps)
    _write_jsonl(trajectory_dir / "truth.jsonl", [{"future_risk_event": "sentinel"}])
    _json_dump(trajectory_dir / "summary.json", {"future_outcome": "sentinel"})
    _write_jsonl(trajectory_dir / "metrics.jsonl", [{"future_metric": 999.0}])


def generate_source_corpus(source_root: Path, config: Mapping[str, Any], profile: Mapping[str, Any]) -> None:
    if source_root.exists():
        raise ValidationError(f"source target already exists: {source_root}")
    for split in ("fit", "validation", "holdout"):
        for seed in profile[f"{split}_seeds"]:
            for scenario in profile["scenario_names"]:
                _generate_source_trajectory(source_root, config, profile, split=split, scenario=str(scenario), seed=int(seed))


def _source_roundtrip(source_root: Path, gk_root: Path) -> dict[str, Any]:
    manifest = _json_load(gk_root / "dataset_manifest.json")
    maximum_error = 0.0
    exact = 0
    total = 0
    rows: list[dict[str, Any]] = []
    for item in manifest["trajectories"]:
        trajectory_id = item["trajectory_id"]
        source_dir = source_root / "trajectories" / trajectory_id
        target_dir = gk_root / "trajectories" / trajectory_id
        mass = np.load(target_dir / "gt_mass.npy", allow_pickle=False)
        steps = [json.loads(line) for line in (source_dir / "steps.jsonl").read_text(encoding="utf-8").splitlines() if line]
        trajectory_exact = True
        for index, step in enumerate(steps):
            with np.load(source_dir / step["state_ref"], allow_pickle=False) as bundle:
                source = np.asarray(bundle["distribution"], dtype=np.float64)
            error = float(np.max(np.abs(source - mass[index])))
            maximum_error = max(maximum_error, error)
            same = bool(np.array_equal(source, mass[index]))
            exact += int(same)
            total += 1
            trajectory_exact = trajectory_exact and same
        rows.append({"trajectory_id": trajectory_id, "frame_count": len(steps), "exact": trajectory_exact})
    return {
        "trajectory_count": len(rows),
        "frame_count": total,
        "exact_frame_count": exact,
        "maximum_absolute_error": maximum_error,
        "all_frames_exact": exact == total,
        "trajectories": rows,
    }


def _deterministic_rebuild(first: Path, second: Path) -> dict[str, Any]:
    manifest = _json_load(first / "dataset_manifest.json")
    rows = []
    for item in manifest["trajectories"]:
        trajectory_id = item["trajectory_id"]
        left = first / "trajectories" / trajectory_id
        right = second / "trajectories" / trajectory_id
        mass_equal = (left / "gt_mass.npy").read_bytes() == (right / "gt_mass.npy").read_bytes()
        ledger_equal = (left / "history_ledger.csv").read_bytes() == (right / "history_ledger.csv").read_bytes()
        rows.append({"trajectory_id": trajectory_id, "gt_mass_equal": mass_equal, "history_ledger_equal": ledger_equal})
    return {"all_equal": all(row["gt_mass_equal"] and row["history_ledger_equal"] for row in rows), "trajectories": rows}


def _anomaly_audit(foundation: Mapping[str, Any]) -> list[dict[str, Any]]:
    accumulator = HistoryAccumulator(foundation, "traj_anomaly")
    distribution = np.full((5, 5, 5, 5, 5), 1.0 / 3125.0, dtype=np.float64)
    cases = [(0, "traj_anomaly"), (0, "traj_anomaly"), (3, "traj_anomaly"), (2, "traj_anomaly"), (3, "other")]
    for index, (t, source_id) in enumerate(cases):
        accumulator.append(
            t=t,
            phase="pre_transition",
            distribution=distribution,
            source_state_ref=f"states/row_{index:06d}.npz",
            source_state_hash=(f"{index + 1:064x}")[-64:],
            source_trajectory_id=source_id,
        )
    return [dict(row) for row in accumulator.ledger_rows]


def _centroids(distribution: np.ndarray) -> np.ndarray:
    grids = np.meshgrid(*([np.asarray(AXIS_BINS, dtype=np.float64)] * 5), indexing="ij")
    return np.asarray([float(np.sum(distribution * grid)) for grid in grids], dtype=np.float64)


def _marginals(distribution: np.ndarray) -> np.ndarray:
    values = []
    for axis in range(5):
        reduce_axes = tuple(index for index in range(5) if index != axis)
        values.extend(np.sum(distribution, axis=reduce_axes).tolist())
    return np.asarray(values, dtype=np.float64)


def _pairwise_marginals(distribution: np.ndarray) -> np.ndarray:
    values = []
    for left, right in combinations(range(5), 2):
        reduce_axes = tuple(index for index in range(5) if index not in (left, right))
        values.extend(np.sum(distribution, axis=reduce_axes).ravel(order="C").tolist())
    return np.asarray(values, dtype=np.float64)


def _entropy(distribution: np.ndarray) -> float:
    flat = distribution.ravel()
    positive = flat > 0
    return -float(np.sum(flat[positive] * np.log(flat[positive])))


def _hellinger(left: np.ndarray, right: np.ndarray) -> float:
    delta = np.sqrt(left) - np.sqrt(right)
    return math.sqrt(max(0.5 * float(np.sum(delta * delta)), 0.0))


def _js(left: np.ndarray, right: np.ndarray) -> float:
    p, q = left.ravel(), right.ravel()
    middle = 0.5 * (p + q)

    def kl(a: np.ndarray, b: np.ndarray) -> float:
        mask = a > 0
        return float(np.sum(a[mask] * np.log(a[mask] / b[mask])))

    return math.sqrt(max(0.5 * kl(p, middle) + 0.5 * kl(q, middle), 0.0))


def _representation(distribution: np.ndarray, name: str) -> np.ndarray:
    if name == "axis_means":
        return np.concatenate([_centroids(distribution), [_entropy(distribution), float(np.sum(distribution ** 2))]])
    if name == "axis_marginals":
        return np.concatenate([_marginals(distribution), [_entropy(distribution), float(np.sum(distribution ** 2))]])
    if name == "pairwise_marginals":
        return np.concatenate([_marginals(distribution), _pairwise_marginals(distribution)])
    if name == "full_distribution":
        return np.sqrt(distribution).ravel(order="C")
    raise ValidationError(f"unknown representation {name}")


@dataclass
class Trajectory:
    trajectory_id: str
    split: str
    scenario: str
    seed: int
    mass: np.ndarray


def _load_trajectories(gk_root: Path, split: str) -> list[Trajectory]:
    manifest = _json_load(gk_root / "dataset_manifest.json")
    rows: list[Trajectory] = []
    for item in manifest["trajectories"]:
        if str(item["dataset_split"]) != split:
            continue
        trajectory_id = str(item["trajectory_id"])
        directory = gk_root / "trajectories" / trajectory_id
        validation = validate_trajectory_artifact(directory)
        if not validation["research_admissible_history"]:
            raise ValidationError(f"non-admissible formal history: {trajectory_id}")
        provenance = _json_load(directory / "provenance.json")
        rows.append(Trajectory(
            trajectory_id=trajectory_id,
            split=split,
            scenario=str(provenance["scenario_id"]),
            seed=int(provenance["seed"]),
            mass=np.load(directory / "gt_mass.npy", allow_pickle=False),
        ))
    return rows


def _normal_variation_threshold(records: Sequence[Trajectory], quantile: float, minimum: float) -> tuple[float, list[float]]:
    baselines = [record for record in records if record.scenario == "baseline"]
    values: list[float] = []
    for record in baselines:
        values.extend(_hellinger(record.mass[t - 1], record.mass[t]) for t in range(1, len(record.mass)))
    for left, right in combinations(baselines, 2):
        for t in range(min(len(left.mass), len(right.mass))):
            values.append(_hellinger(left.mass[t], right.mass[t]))
    if not values:
        raise ValidationError("normal variation threshold has no fit observations")
    return max(float(np.quantile(values, quantile)), minimum), values


def _external_response_rows(records: Sequence[Trajectory], threshold: float, pulse_start: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    by_key = {(record.seed, record.scenario): record for record in records}
    temporal_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []
    for record in records:
        if record.scenario == "baseline":
            continue
        baseline = by_key.get((record.seed, "baseline"))
        if baseline is None:
            raise ValidationError(f"missing same-seed baseline for {record.trajectory_id}")
        distances = []
        js_distances = []
        centroid_vectors = []
        for t in range(len(record.mass)):
            current, reference = record.mass[t], baseline.mass[t]
            h = _hellinger(current, reference)
            js = _js(current, reference)
            tv = 0.5 * float(np.sum(np.abs(current - reference)))
            centroid = _centroids(current) - _centroids(reference)
            distances.append(h)
            js_distances.append(js)
            centroid_vectors.append(centroid)
            row = {
                "trajectory_id": record.trajectory_id,
                "split": record.split,
                "scenario": record.scenario,
                "seed": record.seed,
                "t": t,
                "hellinger": h,
                "jensen_shannon": js,
                "total_variation": tv,
                "detected": h > threshold,
                "entropy_delta": _entropy(current) - _entropy(reference),
                "concentration_delta": float(np.sum(current ** 2) - np.sum(reference ** 2)),
            }
            for axis, value in zip(AXIS_NAMES, centroid):
                row[f"centroid_delta_{axis}"] = float(value)
            temporal_rows.append(row)
        evaluation = list(range(min(pulse_start + 1, len(distances)), len(distances)))
        peak_t = max(evaluation, key=lambda index: distances[index]) if evaluation else int(np.argmax(distances))
        detected_times = [t for t in evaluation if distances[t] > threshold]
        feature = [distances[peak_t], js_distances[peak_t], distances[-1]]
        feature.extend(centroid_vectors[peak_t].tolist())
        summary = {
            "trajectory_id": record.trajectory_id,
            "split": record.split,
            "scenario": record.scenario,
            "seed": record.seed,
            "detected_any": bool(detected_times),
            "detection_rate": float(len(detected_times) / max(len(evaluation), 1)),
            "onset_t": detected_times[0] if detected_times else None,
            "onset_lag": (detected_times[0] - pulse_start) if detected_times else None,
            "peak_t": int(peak_t),
            "peak_hellinger": float(distances[peak_t]),
            "peak_to_threshold_ratio": float(distances[peak_t] / max(threshold, 1e-15)),
            "end_hellinger": float(distances[-1]),
            "signature": feature,
        }
        for axis, value in zip(AXIS_NAMES, centroid_vectors[peak_t]):
            summary[f"peak_centroid_delta_{axis}"] = float(value)
        summary_rows.append(summary)
    return pd.DataFrame(temporal_rows), pd.DataFrame(summary_rows)


def _scenario_summary(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return pd.DataFrame()
    grouped = []
    for (split, scenario), group in rows.groupby(["split", "scenario"], sort=True):
        vectors = group[[f"peak_centroid_delta_{axis}" for axis in AXIS_NAMES]].to_numpy(dtype=float)
        mean = vectors.mean(axis=0)
        norm = float(np.linalg.norm(mean))
        cosines = []
        for vector in vectors:
            denominator = float(np.linalg.norm(vector)) * norm
            if denominator > 1e-15:
                cosines.append(float(np.dot(vector, mean) / denominator))
        grouped.append({
            "split": split,
            "scenario": scenario,
            "seed_count": len(group),
            "scenario_seed_detection_rate": float(group["detected_any"].mean()),
            "median_detection_rate": float(group["detection_rate"].median()),
            "median_peak_hellinger": float(group["peak_hellinger"].median()),
            "median_peak_to_threshold_ratio": float(group["peak_to_threshold_ratio"].median()),
            "median_end_hellinger": float(group["end_hellinger"].median()),
            "direction_consistency_mean_cosine": float(np.mean(cosines)) if cosines else 0.0,
        })
    return pd.DataFrame(grouped)


def _signature_classification(fit: pd.DataFrame, evaluation: pd.DataFrame) -> pd.DataFrame:
    fit = fit[fit["scenario"].isin(SINGLE_SCENARIOS)].copy()
    evaluation = evaluation[evaluation["scenario"].isin(SINGLE_SCENARIOS)].copy()
    if fit.empty or evaluation.empty:
        return pd.DataFrame()
    centroids: dict[str, np.ndarray] = {}
    for scenario, group in fit.groupby("scenario"):
        centroids[str(scenario)] = np.mean(np.stack(group["signature"].map(np.asarray)), axis=0)
    rows = []
    for _, row in evaluation.iterrows():
        vector = np.asarray(row["signature"], dtype=float)
        predicted = min(centroids, key=lambda name: float(np.linalg.norm(vector - centroids[name])))
        rows.append({
            "trajectory_id": row["trajectory_id"],
            "split": row["split"],
            "seed": int(row["seed"]),
            "actual": row["scenario"],
            "predicted": predicted,
            "correct": predicted == row["scenario"],
        })
    return pd.DataFrame(rows)


def _fit_pca(records: Sequence[Trajectory], components: int) -> PCA:
    matrix = np.concatenate([np.sqrt(record.mass).reshape(len(record.mass), -1) for record in records], axis=0)
    count = min(int(components), matrix.shape[0] - 1, matrix.shape[1])
    if count < 1:
        raise ValidationError("not enough fit frames for PCA")
    return PCA(n_components=count, svd_solver="randomized", random_state=0).fit(matrix)


def _latent_map(records: Sequence[Trajectory], pca: PCA) -> dict[str, np.ndarray]:
    return {
        record.trajectory_id: pca.transform(np.sqrt(record.mass).reshape(len(record.mass), -1))
        for record in records
    }


def _sample_index(records: Sequence[Trajectory], max_width: int) -> list[tuple[Trajectory, int]]:
    rows = []
    for record in records:
        for t in range(max_width - 1, len(record.mass) - 1):
            rows.append((record, t))
    return rows


def _targets(index: Sequence[tuple[Trajectory, int]], latent: Mapping[str, np.ndarray]) -> np.ndarray:
    return np.stack([latent[record.trajectory_id][t + 1] - latent[record.trajectory_id][t] for record, t in index])


def _history_features(
    index: Sequence[tuple[Trajectory, int]],
    latent: Mapping[str, np.ndarray],
    width: int,
    mode: str = "correct",
) -> np.ndarray:
    rows = []
    permutation = np.arange(width)
    if mode == "shuffle" and width > 1:
        permutation = np.random.default_rng(0).permutation(width)
    for record, t in index:
        sequence = latent[record.trajectory_id][t - width + 1 : t + 1].copy()
        if mode == "reverse":
            sequence = sequence[::-1]
        elif mode == "repeat_current":
            sequence[:] = sequence[-1]
        elif mode == "shuffle":
            sequence = sequence[permutation]
        elif mode != "correct":
            raise ValidationError(f"unknown history mode {mode}")
        rows.append(sequence.ravel(order="C"))
    return np.stack(rows)


def _representation_features(index: Sequence[tuple[Trajectory, int]], name: str) -> np.ndarray:
    return np.stack([_representation(record.mass[t], name) for record, t in index])


@dataclass
class FittedModel:
    scaler: StandardScaler
    model: Ridge
    validation_rmse: float
    alpha: float


def _fit_best_ridge(
    train_x: np.ndarray,
    train_y: np.ndarray,
    validation_x: np.ndarray,
    validation_y: np.ndarray,
    alphas: Sequence[float],
) -> FittedModel:
    scaler = StandardScaler().fit(train_x)
    x_train = scaler.transform(train_x)
    x_validation = scaler.transform(validation_x)
    best: FittedModel | None = None
    for alpha in alphas:
        model = Ridge(alpha=float(alpha), solver="lsqr").fit(x_train, train_y)
        prediction = model.predict(x_validation)
        rmse = float(np.sqrt(np.mean((prediction - validation_y) ** 2)))
        candidate = FittedModel(scaler, model, rmse, float(alpha))
        if best is None or (candidate.validation_rmse, candidate.alpha) < (best.validation_rmse, best.alpha):
            best = candidate
    assert best is not None
    return best


def _rmse(bundle: FittedModel, features: np.ndarray, target: np.ndarray) -> float:
    prediction = bundle.model.predict(bundle.scaler.transform(features))
    return float(np.sqrt(np.mean((prediction - target) ** 2)))


def _write_manifest(root: Path) -> dict[str, Any]:
    files = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "manifest.json":
            continue
        files.append({
            "path": path.relative_to(root).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": _sha256_file(path),
        })
    manifest = {
        "file_count": len(files),
        "total_size_bytes": sum(item["size_bytes"] for item in files),
        "files": files,
    }
    _json_dump(root / "manifest.json", manifest)
    return manifest


def _gate_external(summary: pd.DataFrame, config: Mapping[str, Any]) -> str:
    rule = config["external_response"]
    selected = summary[summary["scenario"].isin(SINGLE_SCENARIOS)]
    validation = selected[selected["split"] == "validation"]
    holdout = selected[selected["split"] == "holdout"]
    composites = summary[(summary["split"] == "holdout") & summary["scenario"].isin(COMPOSITE_SCENARIOS)]
    if validation.empty or holdout.empty:
        return "failed"
    minimum_detection = float(rule["minimum_scenario_seed_detection_rate"])
    minimum_ratio = float(rule["minimum_median_peak_to_threshold_ratio"])
    validation_ok = bool(
        (validation["scenario_seed_detection_rate"] >= minimum_detection).all()
        and validation["median_peak_to_threshold_ratio"].median() >= minimum_ratio
    )
    holdout_ok = bool(
        (holdout["scenario_seed_detection_rate"] >= minimum_detection).all()
        and holdout["median_peak_to_threshold_ratio"].median() >= minimum_ratio
    )
    composite_ok = composites.empty or bool(
        (composites["scenario_seed_detection_rate"] >= minimum_detection).all()
    )
    if validation_ok and holdout_ok and composite_ok:
        return "passed"
    if bool((pd.concat([validation, holdout])["median_peak_to_threshold_ratio"] > 1.0).any()):
        return "partial"
    return "failed"


def run_validation(config_path: str | Path, profile_name: str, output_dir: str | Path) -> Path:
    config, profile = load_validation_config(config_path, profile_name)
    foundation = load_foundation_contract(ROOT / config["foundation_contract"])
    output = Path(output_dir)
    if output.exists():
        raise ValidationError(f"output already exists: {output}")
    output.mkdir(parents=True)
    _json_dump(output / "validation_contract.json", config)
    _json_dump(output / "profile.json", profile)

    work = output / "work"
    source = work / "source_corpus"
    generate_source_corpus(source, config, profile)
    source_before = _tree_hashes(source)
    first = work / "gk_first"
    second = work / "gk_second"
    build_corpus(source, first, ROOT / config["foundation_contract"])
    build_corpus(source, second, ROOT / config["foundation_contract"])
    source_after = _tree_hashes(source)

    integrity_dir = output / "representation_integrity"
    roundtrip = _source_roundtrip(source, first)
    deterministic = _deterministic_rebuild(first, second)
    anomalies = _anomaly_audit(foundation)
    source_writeback = {
        "source_tree_unchanged": source_before == source_after,
        "file_count": len(source_before),
    }
    _json_dump(integrity_dir / "exact_roundtrip.json", roundtrip)
    _json_dump(integrity_dir / "deterministic_rebuild.json", deterministic)
    pd.DataFrame(anomalies).to_csv(integrity_dir / "history_anomaly_audit.csv", index=False)
    _json_dump(integrity_dir / "source_writeback_audit.json", source_writeback)
    corpus_validation = _json_load(first / "validation.json")
    anomaly_statuses = [row["continuity_status"] for row in anomalies]
    representation_passed = bool(
        roundtrip["all_frames_exact"]
        and deterministic["all_equal"]
        and source_writeback["source_tree_unchanged"]
        and anomaly_statuses == ["initial", "duplicate", "gap", "out_of_order", "source_mismatch"]
        and corpus_validation["trajectory_level_split_check"] == "passed"
        and corpus_validation["history_admissibility_gate"] == "passed"
    )

    fit_records = _load_trajectories(first, "fit")
    validation_records = _load_trajectories(first, "validation")
    quantile = float(config["external_response"]["normal_variation_quantile"])
    threshold, normal_values = _normal_variation_threshold(
        fit_records,
        quantile,
        float(config["external_response"]["minimum_threshold"]),
    )
    fit_temporal, fit_response = _external_response_rows(
        fit_records, threshold, int(profile["pulse_start"])
    )
    validation_temporal, validation_response = _external_response_rows(
        validation_records, threshold, int(profile["pulse_start"])
    )

    pca = _fit_pca(fit_records, int(profile["pca_components"]))
    fit_latent = _latent_map(fit_records, pca)
    validation_latent = _latent_map(validation_records, pca)
    max_width = max(int(value) for value in profile["history_width_candidates"])
    fit_index = _sample_index(fit_records, max_width)
    validation_index = _sample_index(validation_records, max_width)
    fit_target = _targets(fit_index, fit_latent)
    validation_target = _targets(validation_index, validation_latent)
    alphas = [float(value) for value in profile["ridge_alphas"]]

    history_candidates: list[dict[str, Any]] = []
    history_models: dict[int, FittedModel] = {}
    for width in profile["history_width_candidates"]:
        width = int(width)
        bundle = _fit_best_ridge(
            _history_features(fit_index, fit_latent, width),
            fit_target,
            _history_features(validation_index, validation_latent, width),
            validation_target,
            alphas,
        )
        history_models[width] = bundle
        history_candidates.append({
            "history_width": width,
            "alpha": bundle.alpha,
            "validation_rmse": bundle.validation_rmse,
        })
    history_candidates.sort(key=lambda row: (row["validation_rmse"], row["history_width"], row["alpha"]))
    selected_width = int(history_candidates[0]["history_width"])
    current_bundle = history_models[1]
    selected_bundle = history_models[selected_width]

    representation_candidates: list[dict[str, Any]] = []
    representation_models: dict[str, FittedModel] = {}
    for name in config["information_sufficiency"]["representations"]:
        bundle = _fit_best_ridge(
            _representation_features(fit_index, name),
            fit_target,
            _representation_features(validation_index, name),
            validation_target,
            alphas,
        )
        representation_models[name] = bundle
        representation_candidates.append({
            "representation": name,
            "alpha": bundle.alpha,
            "validation_rmse": bundle.validation_rmse,
        })

    pca_hash = hashlib.sha256(
        np.ascontiguousarray(pca.components_, dtype=np.float64).tobytes()
    ).hexdigest()
    lock = {
        "contract_version": config["contract_version"],
        "profile": profile_name,
        "config_hash": _config_hash(config),
        "external_threshold": threshold,
        "normal_variation_quantile": quantile,
        "normal_variation_observation_count": len(normal_values),
        "pca_component_count": int(pca.n_components_),
        "pca_components_hash": pca_hash,
        "history_width": selected_width,
        "history_alpha": selected_bundle.alpha,
        "current_only_alpha": current_bundle.alpha,
        "representation_alphas": {
            name: model.alpha for name, model in representation_models.items()
        },
        "holdout_opened": False,
    }
    _json_dump(output / config["holdout_policy"]["lock_file"], lock)
    lock_hash = _sha256_file(output / config["holdout_policy"]["lock_file"])
    _json_dump(output / config["holdout_policy"]["lock_validation_file"], {
        "lock_hash": lock_hash,
        "selection_used_fit_and_validation_only": True,
        "holdout_opened_before_lock": False,
        "status": "valid",
    })

    holdout_records = _load_trajectories(first, "holdout")
    holdout_temporal, holdout_response = _external_response_rows(
        holdout_records, threshold, int(profile["pulse_start"])
    )
    all_response = pd.concat(
        [fit_response, validation_response, holdout_response], ignore_index=True
    )
    all_temporal = pd.concat(
        [fit_temporal, validation_temporal, holdout_temporal], ignore_index=True
    )
    scenario_summary = _scenario_summary(all_response)
    classification = pd.concat([
        _signature_classification(fit_response, validation_response),
        _signature_classification(fit_response, holdout_response),
    ], ignore_index=True)
    external_dir = output / "external_response"
    external_dir.mkdir(parents=True, exist_ok=True)
    all_temporal.to_csv(external_dir / "external_factor_response.csv", index=False)
    scenario_summary.to_csv(external_dir / "scenario_response_summary.csv", index=False)
    classification.to_csv(external_dir / "factor_signature_classification.csv", index=False)
    pd.DataFrame({"normal_variation_hellinger": normal_values}).to_csv(
        external_dir / "normal_variation.csv", index=False
    )
    external_gate = _gate_external(scenario_summary, config)

    holdout_latent = _latent_map(holdout_records, pca)
    holdout_index = _sample_index(holdout_records, max_width)
    holdout_target = _targets(holdout_index, holdout_latent)
    current_rmse = _rmse(
        current_bundle,
        _history_features(holdout_index, holdout_latent, 1),
        holdout_target,
    )
    selected_correct_rmse = _rmse(
        selected_bundle,
        _history_features(holdout_index, holdout_latent, selected_width, "correct"),
        holdout_target,
    )
    ablation_rows = []
    for mode in ("correct", "reverse", "repeat_current", "shuffle"):
        ablation_rows.append({
            "mode": mode,
            "history_width": selected_width,
            "holdout_rmse": _rmse(
                selected_bundle,
                _history_features(holdout_index, holdout_latent, selected_width, mode),
                holdout_target,
            ),
        })
    ablation = pd.DataFrame(ablation_rows)
    relative_improvement = (
        current_rmse - selected_correct_rmse
    ) / max(current_rmse, 1e-15)
    all_ablations_worse = bool(
        selected_width > 1
        and (
            ablation[ablation["mode"] != "correct"]["holdout_rmse"]
            > selected_correct_rmse
        ).all()
    )
    history_rule = config["history_value"]
    if (
        selected_width > 1
        and relative_improvement
        >= float(history_rule["minimum_relative_rmse_improvement_for_pass"])
        and all_ablations_worse
    ):
        history_gate = "passed"
    elif relative_improvement > float(
        history_rule["minimum_relative_rmse_improvement_for_partial"]
    ):
        history_gate = "partial"
    else:
        history_gate = "failed"
    history_dir = output / "history_value"
    history_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(history_candidates).to_csv(
        history_dir / "history_width_sensitivity.csv", index=False
    )
    ablation.to_csv(history_dir / "history_destruction_ablation.csv", index=False)
    _json_dump(history_dir / "gt_vs_gt_kt.json", {
        "current_only_holdout_rmse": current_rmse,
        "selected_history_width": selected_width,
        "selected_history_holdout_rmse": selected_correct_rmse,
        "relative_rmse_improvement": relative_improvement,
        "all_destruction_ablations_worse": all_ablations_worse,
        "history_value_gate": history_gate,
    })

    information_rows = []
    for name, model in representation_models.items():
        information_rows.append({
            "representation": name,
            "alpha": model.alpha,
            "validation_rmse": model.validation_rmse,
            "holdout_rmse": _rmse(
                model,
                _representation_features(holdout_index, name),
                holdout_target,
            ),
        })
    information = pd.DataFrame(information_rows)
    information_dir = output / "information_sufficiency"
    information_dir.mkdir(parents=True, exist_ok=True)
    information.to_csv(
        information_dir / "representation_comparison.csv", index=False
    )
    full_rmse = float(
        information.loc[
            information["representation"] == "full_distribution", "holdout_rmse"
        ].iloc[0]
    )
    summary_best = float(
        information.loc[
            information["representation"] != "full_distribution", "holdout_rmse"
        ].min()
    )
    tolerance = float(
        config["information_sufficiency"]["full_distribution_not_worse_tolerance"]
    )
    information_gate = (
        "passed" if full_rmse <= summary_best * (1.0 + tolerance) else "partial"
    )

    fit_current = np.stack([
        fit_latent[record.trajectory_id][t] for record, t in fit_index
    ])
    near_rows = []
    for record, t in validation_index + holdout_index:
        latent_map = validation_latent if record.split == "validation" else holdout_latent
        current = latent_map[record.trajectory_id][t]
        distances = np.linalg.norm(fit_current - current, axis=1)
        nearest = int(np.argmin(distances))
        fit_record, fit_t = fit_index[nearest]
        future_gap = float(np.linalg.norm(
            (latent_map[record.trajectory_id][t + 1] - current)
            - (
                fit_latent[fit_record.trajectory_id][fit_t + 1]
                - fit_latent[fit_record.trajectory_id][fit_t]
            )
        ))
        near_rows.append({
            "split": record.split,
            "query_trajectory": record.trajectory_id,
            "query_t": t,
            "nearest_fit_trajectory": fit_record.trajectory_id,
            "nearest_fit_t": fit_t,
            "current_latent_distance": float(distances[nearest]),
            "next_change_gap": future_gap,
        })
    pd.DataFrame(near_rows).sort_values(
        ["current_latent_distance", "next_change_gap"]
    ).head(200).to_csv(
        information_dir / "near_gt_divergence_pairs.csv", index=False
    )

    holdout_gate = (
        "passed"
        if all(np.isfinite(information["holdout_rmse"])) and np.isfinite(current_rmse)
        else "failed"
    )
    representation_gate = "passed" if representation_passed else "failed"
    if representation_gate == external_gate == history_gate == holdout_gate == "passed":
        judgement = "A_formal_adoption"
    elif representation_gate == "failed" or (
        external_gate == "failed" and history_gate == "failed"
    ):
        judgement = "C_rejected"
    else:
        judgement = "B_limited_adoption"
    final = output / "final"
    metrics = {
        "profile": profile_name,
        "representation_hard_gate": representation_gate,
        "information_sufficiency_gate": information_gate,
        "external_response_gate": external_gate,
        "history_value_gate": history_gate,
        "holdout_gate": holdout_gate,
        "external_threshold": threshold,
        "factor_signature_accuracy_validation": (
            float(
                classification[classification["split"] == "validation"]["correct"].mean()
            )
            if not classification.empty
            and (classification["split"] == "validation").any()
            else None
        ),
        "factor_signature_accuracy_holdout": (
            float(
                classification[classification["split"] == "holdout"]["correct"].mean()
            )
            if not classification.empty
            and (classification["split"] == "holdout").any()
            else None
        ),
        "current_only_holdout_rmse": current_rmse,
        "selected_history_width": selected_width,
        "selected_history_holdout_rmse": selected_correct_rmse,
        "history_relative_improvement": relative_improvement,
        "adoption_judgement": judgement,
        "selection_lock_hash": lock_hash,
    }
    _json_dump(final / "validation_metrics.json", metrics)
    _json_dump(final / "adoption_judgement.json", {
        "judgement": judgement,
        "A_claimed": judgement == "A_formal_adoption",
        "gates": {
            "representation": representation_gate,
            "information_sufficiency": information_gate,
            "external_response": external_gate,
            "history_value": history_gate,
            "holdout": holdout_gate,
        },
    })
    result_lines = [
        "# 固定5軸G_t・K_t 採用検証 RC1 結果",
        "",
        f"- 総合判定: `{judgement}`",
        f"- 正本情報保持: `{representation_gate}`",
        f"- 完全分布の情報十分性: `{information_gate}`",
        f"- 外部要因応答: `{external_gate}`",
        f"- K_t履歴価値: `{history_gate}`",
        f"- holdout手順: `{holdout_gate}`",
        "",
        "## 主要数値",
        "",
        f"- 外部応答検出閾値（Hellinger）: `{threshold:.8g}`",
        f"- 現在G_tのみ holdout RMSE: `{current_rmse:.8g}`",
        f"- 選択K_t幅: `{selected_width}`",
        f"- G_t＋K_t holdout RMSE: `{selected_correct_rmse:.8g}`",
        f"- 履歴相対改善率: `{relative_improvement:.6%}`",
        "",
        "Actions成功は実行整合を意味し、A採用は全科学判定通過時だけ主張する。",
    ]
    (final / "results.md").write_text(
        "\n".join(result_lines) + "\n", encoding="utf-8"
    )
    (final / "completion.md").write_text(
        "# Completion\n\n正式な固定5軸G_t・K_t成果物から、正本整合、外部応答、情報十分性、履歴価値を評価した。\n",
        encoding="utf-8",
    )

    shutil.rmtree(work)
    _write_manifest(output)
    return output


def validate_output(path: str | Path) -> dict[str, Any]:
    root = Path(path)
    required = [
        "validation_contract.json",
        "profile.json",
        "threshold_lock.json",
        "threshold_lock_validation.json",
        "representation_integrity/exact_roundtrip.json",
        "representation_integrity/deterministic_rebuild.json",
        "external_response/scenario_response_summary.csv",
        "history_value/gt_vs_gt_kt.json",
        "information_sufficiency/representation_comparison.csv",
        "final/validation_metrics.json",
        "final/adoption_judgement.json",
        "final/results.md",
        "manifest.json",
    ]
    missing = [name for name in required if not (root / name).is_file()]
    if missing:
        raise ValidationError(f"missing output files: {missing}")
    manifest = _json_load(root / "manifest.json")
    for item in manifest["files"]:
        path_item = root / item["path"]
        if not path_item.is_file() or _sha256_file(path_item) != item["sha256"]:
            raise ValidationError(f"manifest mismatch: {item['path']}")
    metrics = _json_load(root / "final" / "validation_metrics.json")
    allowed = {"passed", "partial", "failed"}
    for key in (
        "representation_hard_gate",
        "information_sufficiency_gate",
        "external_response_gate",
        "history_value_gate",
        "holdout_gate",
    ):
        if metrics[key] not in allowed:
            raise ValidationError(f"invalid gate {key}={metrics[key]}")
    return {
        "status": "valid",
        "file_count": manifest["file_count"],
        "adoption_judgement": metrics["adoption_judgement"],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--config", default=str(DEFAULT_CONFIG))
    run.add_argument("--profile", default="formal")
    run.add_argument("--output", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("--input", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "run":
        print(run_validation(args.config, args.profile, args.output))
    else:
        print(json.dumps(validate_output(args.input), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
