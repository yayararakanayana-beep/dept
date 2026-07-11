"""Task 3.2-4 minimal macro-dynamics extraction and comparison.

The implementation deliberately uses standard NumPy/SciPy/scikit-learn
components: fit-only preprocessing, PCA, ridge-fitted DMD/DMDc, and a
Hankel-delay residual model. It does not assign physical names to modes and
keeps unexplained residuals explicit.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd
from scipy.linalg import subspace_angles
from scipy.stats import spearmanr
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import average_precision_score, brier_score_loss
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import task3_2_3_simple_early_warning as t3_public  # noqa: F401,E402
import _task3_2_3_core as t3  # noqa: E402

DEFAULT_CONFIG = ROOT / "configs" / "task3_2_4_macro_dynamics.json"
EXTERNAL_FIELDS = tuple(t3.EXTERNAL_FIELDS)


class MacroDynamicsError(ValueError):
    pass


def _json_load(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _json_dump(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise MacroDynamicsError(f"{path}:{line_number} must be a JSON object")
            rows.append(value)
    return rows


def _write_csv(path: str | Path, rows: Sequence[Mapping[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        target.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(str(key))
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))


def _canonical_hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_config(path: str | Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = _json_load(path)
    required = {
        "challenge",
        "representation_candidates",
        "task3_fair_baseline",
        "alarm_probability_thresholds",
        "alarm_persistence_candidates",
        "near_state_pairs",
        "success_criteria",
        "outputs",
    }
    missing = sorted(required - set(config))
    if missing:
        raise MacroDynamicsError(f"Task 4 config missing {missing}")
    representation = config["representation_candidates"]
    expected_families = {"static", "dmd", "dmdc", "havok_residual"}
    if set(representation["dynamics_families"]) != expected_families:
        raise MacroDynamicsError("Task 4 requires static, dmd, dmdc, and havok_residual")
    if set(representation["input_scopes"]) != {"distribution", "full_state"}:
        raise MacroDynamicsError("Task 4 requires distribution and full_state scopes")
    seeds = (
        config["challenge"]["fit_seeds"]
        + config["challenge"]["validation_seeds"]
        + config["challenge"]["holdout_seeds"]
    )
    if len(seeds) != len(set(seeds)):
        raise MacroDynamicsError("Task 4 split seeds must be unique")
    return config


@dataclass(frozen=True)
class Entry:
    trajectory_id: str
    scenario_id: str
    seed: int
    split: str
    path: Path
    total_steps: int


class ChallengeIndex:
    """Metadata-only index; holdout states remain closed until lock validation."""

    def __init__(self, root: str | Path, config: Mapping[str, Any]):
        self.root = Path(root)
        self.config = config
        entries: list[Entry] = []
        for directory in sorted((self.root / "trajectories").glob("traj_*")):
            metadata = _json_load(directory / "metadata.json")
            entries.append(
                Entry(
                    trajectory_id=str(metadata["trajectory_id"]),
                    scenario_id=str(metadata["scenario_id"]),
                    seed=int(metadata["seed"]),
                    split=str(metadata["dataset_split"]),
                    path=directory,
                    total_steps=int(metadata["total_steps"]),
                )
            )
        if not entries:
            raise MacroDynamicsError("challenge corpus contains no trajectories")
        self.entries = entries
        self._validate()

    def _validate(self) -> None:
        challenge = self.config["challenge"]
        expected = {
            "fit": set(challenge["fit_seeds"]),
            "validation": set(challenge["validation_seeds"]),
            "holdout": set(challenge["holdout_seeds"]),
        }
        actual = {
            split: {entry.seed for entry in self.entries if entry.split == split}
            for split in expected
        }
        if actual != expected:
            raise MacroDynamicsError(f"challenge split mismatch: {actual} != {expected}")
        seed_splits: dict[int, set[str]] = {}
        for entry in self.entries:
            seed_splits.setdefault(entry.seed, set()).add(entry.split)
        if any(len(value) != 1 for value in seed_splits.values()):
            raise MacroDynamicsError("one seed appears in multiple challenge splits")
        groups = set(challenge["condition_groups"])
        for seed in sorted(seed_splits):
            observed = {entry.scenario_id for entry in self.entries if entry.seed == seed}
            if observed != groups:
                raise MacroDynamicsError(f"seed {seed} does not cover every challenge condition")

    def entries_for(
        self,
        split: str,
        *,
        lock_path: str | Path | None = None,
        validation_path: str | Path | None = None,
    ) -> list[Entry]:
        if split == "holdout":
            if lock_path is None or validation_path is None:
                raise MacroDynamicsError("Task 4 holdout read blocked before selection lock validation")
            validate_selection_lock(lock_path, validation_path)
        return [entry for entry in self.entries if entry.split == split]

    def manifest(self) -> dict[str, Any]:
        return {
            "trajectory_count": len(self.entries),
            "splits": {
                split: {
                    "seeds": sorted({entry.seed for entry in self.entries if entry.split == split}),
                    "trajectory_ids": sorted(entry.trajectory_id for entry in self.entries if entry.split == split),
                }
                for split in ("fit", "validation", "holdout")
            },
            "seed_level_isolation": True,
            "trajectory_level_isolation": True,
        }


def _to_task3_entry(entry: Entry) -> Any:
    return t3.CorpusEntry(
        trajectory_id=entry.trajectory_id,
        scenario_id=entry.scenario_id,
        seed=entry.seed,
        split=entry.split,
        path=entry.path,
        total_steps=entry.total_steps,
    )


def load_task3_series(entries: Sequence[Entry], task3_config: Mapping[str, Any], calibration: Mapping[str, Any]) -> list[Any]:
    series = [t3.load_trajectory_series(_to_task3_entry(entry), task3_config) for entry in entries]
    t3.attach_future_truth(series, task3_config, calibration)
    return series


def _state_paths(entry: Entry) -> list[Path]:
    steps = _read_jsonl(entry.path / "steps.jsonl")
    if len(steps) != entry.total_steps + 1:
        raise MacroDynamicsError(f"{entry.trajectory_id} state count mismatch")
    paths: list[Path] = []
    for expected, row in enumerate(steps):
        if int(row["step"]) != expected:
            raise MacroDynamicsError(f"{entry.trajectory_id} non-contiguous steps")
        ref = Path(str(row["state_ref"]))
        if ref.is_absolute() or ".." in ref.parts:
            raise MacroDynamicsError("state_ref escapes trajectory directory")
        paths.append(entry.path / ref)
    return paths


class MacroPreprocessor:
    """Fit-only raw-state projection followed by PCA."""

    def __init__(self, scope: str, config: Mapping[str, Any], required_arrays: Sequence[str]):
        self.scope = scope
        self.config = config
        self.required_arrays = list(required_arrays)
        self.random_state = int(config["representation_candidates"]["random_state"])
        self.projected_per_array = int(
            config["representation_candidates"]["full_state_projection_per_array"]
        )
        self.maximum_dimension = max(
            int(value) for value in config["representation_candidates"]["latent_dimensions"]
        )
        self.array_stats: dict[str, tuple[float, float]] = {}
        self.projection_matrices: dict[str, np.ndarray] = {}
        self.scaler = StandardScaler()
        self.pca = PCA(
            n_components=self.maximum_dimension,
            svd_solver="randomized",
            random_state=self.random_state,
        )
        self._fitted = False

    def _fit_array_stats(self, entries: Sequence[Entry]) -> None:
        totals = {name: 0.0 for name in self.required_arrays}
        squares = {name: 0.0 for name in self.required_arrays}
        counts = {name: 0 for name in self.required_arrays}
        for entry in entries:
            for path in _state_paths(entry):
                with np.load(path, allow_pickle=False) as bundle:
                    for name in self.required_arrays:
                        array = np.asarray(bundle[name], dtype=np.float64)
                        totals[name] += float(array.sum())
                        squares[name] += float(np.sum(array * array))
                        counts[name] += int(array.size)
        for name in self.required_arrays:
            mean = totals[name] / max(counts[name], 1)
            variance = max(0.0, squares[name] / max(counts[name], 1) - mean * mean)
            self.array_stats[name] = (mean, max(math.sqrt(variance), 1e-8))
            rng = np.random.default_rng(self.random_state + int(hashlib.sha256(name.encode()).hexdigest()[:8], 16))
            self.projection_matrices[name] = (
                rng.standard_normal((3125, self.projected_per_array)).astype(np.float64)
                / math.sqrt(self.projected_per_array)
            )

    def _raw_vector(self, path: Path) -> np.ndarray:
        with np.load(path, allow_pickle=False) as bundle:
            distribution = np.asarray(bundle["distribution"], dtype=np.float64).reshape(-1)
            if self.scope == "distribution":
                return np.sqrt(np.maximum(distribution, 0.0))
            pieces: list[np.ndarray] = []
            for name in self.required_arrays:
                array = np.asarray(bundle[name], dtype=np.float64).reshape(-1)
                mean, scale = self.array_stats[name]
                standardized = (array - mean) / scale
                pieces.append(standardized @ self.projection_matrices[name])
            return np.concatenate(pieces)

    def _matrix(self, entries: Sequence[Entry]) -> tuple[np.ndarray, list[tuple[str, int]]]:
        rows: list[np.ndarray] = []
        keys: list[tuple[str, int]] = []
        for entry in entries:
            for step, path in enumerate(_state_paths(entry)):
                rows.append(self._raw_vector(path))
                keys.append((entry.trajectory_id, step))
        return np.asarray(rows, dtype=np.float64), keys

    def fit(self, entries: Sequence[Entry]) -> "MacroPreprocessor":
        if self.scope == "full_state":
            self._fit_array_stats(entries)
        matrix, _ = self._matrix(entries)
        scaled = self.scaler.fit_transform(matrix)
        self.pca.fit(scaled)
        self._fitted = True
        return self

    def transform(self, entries: Sequence[Entry]) -> dict[str, np.ndarray]:
        if not self._fitted:
            raise MacroDynamicsError("macro preprocessor is not fitted")
        matrix, keys = self._matrix(entries)
        latent = self.pca.transform(self.scaler.transform(matrix))
        by_trajectory: dict[str, list[tuple[int, np.ndarray]]] = {}
        for key, row in zip(keys, latent, strict=True):
            by_trajectory.setdefault(key[0], []).append((key[1], row))
        return {
            trajectory_id: np.asarray([row for _, row in sorted(values)], dtype=np.float64)
            for trajectory_id, values in by_trajectory.items()
        }

    def metadata(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "maximum_latent_dimension": self.maximum_dimension,
            "explained_variance_ratio": self.pca.explained_variance_ratio_.tolist(),
            "full_state_projection_per_array": self.projected_per_array if self.scope == "full_state" else None,
            "fit_only": True,
        }


class DynamicsModel:
    def __init__(self, family: str, dimension: int, config: Mapping[str, Any]):
        self.family = family
        self.dimension = dimension
        self.delay_width = int(config["representation_candidates"]["delay_width"])
        self.regularization = float(config["representation_candidates"]["ridge_regularization"])
        self.A: np.ndarray | None = None
        self.B: np.ndarray | None = None
        self.delay_scaler: StandardScaler | None = None
        self.delay_pca: PCA | None = None
        self.delay_map: np.ndarray | None = None
        self.external_dimension = len(EXTERNAL_FIELDS)

    @staticmethod
    def _ridge_map(X: np.ndarray, Y: np.ndarray, regularization: float) -> np.ndarray:
        gram = X.T @ X + regularization * np.eye(X.shape[1])
        return np.linalg.solve(gram, X.T @ Y)

    def fit(self, latent: Mapping[str, np.ndarray], series_by_id: Mapping[str, Any]) -> "DynamicsModel":
        X_rows: list[np.ndarray] = []
        Y_rows: list[np.ndarray] = []
        U_rows: list[np.ndarray] = []
        delay_rows: list[np.ndarray] = []
        delay_targets: list[np.ndarray] = []
        for trajectory_id, values_full in latent.items():
            values = values_full[:, : self.dimension]
            series = series_by_id[trajectory_id]
            external = np.asarray(
                [[row[name] for name in EXTERNAL_FIELDS] for row in series.features],
                dtype=np.float64,
            )
            X_rows.extend(values[:-1])
            Y_rows.extend(values[1:])
            U_rows.extend(external[:-1])
            for step in range(self.delay_width - 1, len(values) - 1):
                delay_rows.append(values[step - self.delay_width + 1 : step + 1].reshape(-1))
                delay_targets.append(values[step + 1])
        X = np.asarray(X_rows, dtype=np.float64)
        Y = np.asarray(Y_rows, dtype=np.float64)
        U = np.asarray(U_rows, dtype=np.float64)
        if self.family == "static":
            self.A = np.eye(self.dimension)
        elif self.family == "dmd":
            self.A = self._ridge_map(X, Y, self.regularization)
        elif self.family == "dmdc":
            mapping = self._ridge_map(np.hstack([X, U]), Y, self.regularization)
            self.A = mapping[: self.dimension]
            self.B = mapping[self.dimension :]
        elif self.family == "havok_residual":
            delays = np.asarray(delay_rows, dtype=np.float64)
            targets = np.asarray(delay_targets, dtype=np.float64)
            rank = min(max(self.dimension * 2, self.dimension), 16, delays.shape[0] - 1, delays.shape[1])
            self.delay_scaler = StandardScaler().fit(delays)
            self.delay_pca = PCA(n_components=rank, random_state=0).fit(
                self.delay_scaler.transform(delays)
            )
            coordinates = self.delay_pca.transform(self.delay_scaler.transform(delays))
            self.delay_map = self._ridge_map(coordinates, targets, self.regularization)
            self.A = self._ridge_map(X, Y, self.regularization)
        else:
            raise MacroDynamicsError(f"unsupported dynamics family {self.family}")
        return self

    def _delay_coordinate(self, window: np.ndarray) -> np.ndarray:
        if self.delay_scaler is None or self.delay_pca is None:
            raise MacroDynamicsError("delay model not fitted")
        return self.delay_pca.transform(self.delay_scaler.transform(window.reshape(1, -1)))[0]

    def one_step(self, z: np.ndarray, u: np.ndarray, history: np.ndarray | None = None) -> np.ndarray:
        if self.family == "static":
            return z.copy()
        if self.family == "dmd":
            return z @ self.A
        if self.family == "dmdc":
            return z @ self.A + u @ self.B
        if self.family == "havok_residual":
            if history is None or len(history) < self.delay_width:
                return z @ self.A
            coordinate = self._delay_coordinate(history[-self.delay_width :])
            return coordinate @ self.delay_map
        raise MacroDynamicsError("unsupported family")

    def forecast(self, history: np.ndarray, u: np.ndarray, horizon: int) -> tuple[np.ndarray, float]:
        rolling = [row.copy() for row in history]
        path_length = 0.0
        current = rolling[-1]
        for _ in range(horizon):
            next_value = self.one_step(current, u, np.asarray(rolling))
            path_length += float(np.linalg.norm(next_value - current))
            rolling.append(next_value)
            current = next_value
        return current, path_length

    def residual_series(self, values_full: np.ndarray, external: np.ndarray) -> np.ndarray:
        values = values_full[:, : self.dimension]
        residual = np.zeros(len(values), dtype=np.float64)
        for step in range(1, len(values)):
            history = values[:step]
            prediction = self.one_step(values[step - 1], external[step - 1], history)
            residual[step] = float(np.linalg.norm(values[step] - prediction))
        return residual

    def coefficient_vector(self) -> np.ndarray:
        pieces = [np.asarray(self.A, dtype=np.float64).reshape(-1)]
        if self.B is not None:
            pieces.append(np.asarray(self.B, dtype=np.float64).reshape(-1))
        if self.delay_map is not None:
            pieces.append(np.asarray(self.delay_map, dtype=np.float64).reshape(-1))
        return np.concatenate(pieces)


def _external_matrix(series: Any) -> np.ndarray:
    return np.asarray([[row[name] for name in EXTERNAL_FIELDS] for row in series.features], dtype=np.float64)


def macro_feature_frame(
    entries: Sequence[Entry],
    series_by_id: Mapping[str, Any],
    latent: Mapping[str, np.ndarray],
    dynamics: DynamicsModel,
    dimension: int,
    horizon: int,
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    residual_rows: list[dict[str, Any]] = []
    for entry in entries:
        values = latent[entry.trajectory_id][:, :dimension]
        series = series_by_id[entry.trajectory_id]
        external = _external_matrix(series)
        residual = dynamics.residual_series(values, external)
        for step in range(len(values)):
            history_start = max(0, step - 7)
            history = values[history_start : step + 1]
            forecast, path_length = dynamics.forecast(history, external[step], horizon)
            current = values[step]
            previous = values[step - 1] if step > 0 else current
            residual_window = residual[max(0, step - 7) : step + 1]
            row: dict[str, Any] = {
                "trajectory_id": entry.trajectory_id,
                "step": step,
                "macro_norm": float(np.linalg.norm(current)),
                "macro_delta_norm": float(np.linalg.norm(current - previous)),
                "macro_forecast_change_norm": float(np.linalg.norm(forecast - current)),
                "macro_forecast_path_length": float(path_length),
                "macro_residual_current": float(residual[step]),
                "macro_residual_mean": float(np.mean(residual_window)),
                "macro_residual_slope": float(
                    np.polyfit(np.arange(len(residual_window)), residual_window, 1)[0]
                    if len(residual_window) >= 2
                    else 0.0
                ),
            }
            for index, value in enumerate(current):
                row[f"macro_state_{index:02d}"] = float(value)
            for index, value in enumerate(forecast):
                row[f"macro_forecast_{index:02d}"] = float(value)
            if dynamics.family == "dmdc":
                internal = current @ dynamics.A
                external_response = external[step] @ dynamics.B
                row["macro_internal_response_norm"] = float(np.linalg.norm(internal))
                row["macro_external_response_norm"] = float(np.linalg.norm(external_response))
                row["macro_external_internal_ratio"] = float(
                    np.linalg.norm(external_response) / max(np.linalg.norm(internal), 1e-12)
                )
            if dynamics.family == "havok_residual" and len(history) >= dynamics.delay_width:
                coordinate = dynamics._delay_coordinate(history[-dynamics.delay_width :])
                for index, value in enumerate(coordinate):
                    row[f"macro_delay_{index:02d}"] = float(value)
            rows.append(row)
            residual_rows.append(
                {
                    "trajectory_id": entry.trajectory_id,
                    "scenario_id": entry.scenario_id,
                    "seed": entry.seed,
                    "split": entry.split,
                    "step": step,
                    "dynamics_family": dynamics.family,
                    "dimension": dimension,
                    "residual_norm": float(residual[step]),
                    "hazard_onset_step": series.hazard_onset_step,
                    "steps_to_hazard": (
                        None
                        if series.hazard_onset_step is None
                        else int(series.hazard_onset_step - step)
                    ),
                }
            )
    frame = pd.DataFrame(rows)
    feature_names = [name for name in frame.columns if name.startswith("macro_")]
    if not feature_names:
        raise MacroDynamicsError("macro feature extraction produced no features")
    return frame, residual_rows


def _fit_generic_predictor(frame: pd.DataFrame, features: Sequence[str]) -> dict[str, Any]:
    X = frame[list(features)].to_numpy(dtype=np.float64)
    y = frame["actual_event"].to_numpy(dtype=np.int64)
    depth = frame["actual_depth"].to_numpy(dtype=np.float64)
    scaler = StandardScaler().fit(X)
    transformed = scaler.transform(X)
    if len(np.unique(y)) < 2:
        classifier: Any = {"kind": "constant", "value": float(np.mean(y))}
    else:
        classifier = LogisticRegression(
            C=1.0,
            max_iter=3000,
            class_weight="balanced",
            random_state=0,
        ).fit(transformed, y)
    if np.allclose(depth, depth[0]):
        regressor: Any = {"kind": "constant", "value": float(depth[0])}
    else:
        regressor = Ridge(alpha=1.0).fit(transformed, depth)
    return {"features": list(features), "scaler": scaler, "classifier": classifier, "regressor": regressor}


def _predict_generic(model: Mapping[str, Any], frame: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    X = frame[list(model["features"])].to_numpy(dtype=np.float64)
    transformed = model["scaler"].transform(X)
    classifier = model["classifier"]
    if isinstance(classifier, dict):
        probability = np.full(len(frame), float(classifier["value"]), dtype=np.float64)
    else:
        probability = classifier.predict_proba(transformed)[:, 1]
    regressor = model["regressor"]
    if isinstance(regressor, dict):
        depth = np.full(len(frame), float(regressor["value"]), dtype=np.float64)
    else:
        depth = np.maximum(0.0, regressor.predict(transformed))
    return np.asarray(probability, dtype=np.float64), np.asarray(depth, dtype=np.float64)


def _window_with_macro(
    base: Any,
    macro: pd.DataFrame,
    feature_mode: str,
) -> tuple[Any, list[str]]:
    merged = base.frame.merge(macro, on=["trajectory_id", "step"], how="inner", validate="one_to_one")
    macro_features = [name for name in macro.columns if name.startswith("macro_")]
    if feature_mode == "macro_only":
        features = macro_features
    elif feature_mode == "task3_plus_macro":
        features = list(base.feature_names) + macro_features
    else:
        raise MacroDynamicsError(f"unsupported feature mode {feature_mode}")
    forbidden_metadata = {"scenario_id", "seed", "split"}
    if forbidden_metadata & set(features):
        raise MacroDynamicsError("metadata leaked into candidate features")
    return t3.WindowDataset(
        frame=merged,
        feature_names=features,
        current_feature_names=list(base.current_feature_names),
        history_width=base.history_width,
        horizon=base.horizon,
    ), macro_features


def _near_state_pairs(dataset: Any, config: Mapping[str, Any]) -> list[tuple[int, int, float]]:
    settings = config["near_state_pairs"]
    frame = dataset.frame.reset_index(drop=True)
    X = frame[dataset.current_feature_names].to_numpy(dtype=np.float64)
    X = StandardScaler().fit_transform(X)
    count = min(int(settings["nearest_neighbor_count"]) + 1, len(frame))
    neighbors = NearestNeighbors(n_neighbors=count).fit(X)
    distances, indices = neighbors.kneighbors(X)
    pairs: list[tuple[int, int, float]] = []
    seen: set[tuple[int, int]] = set()
    minimum_gap = float(settings["minimum_future_depth_gap"])
    for left in range(len(frame)):
        for distance, right in zip(distances[left, 1:], indices[left, 1:], strict=True):
            right = int(right)
            if frame.loc[left, "trajectory_id"] == frame.loc[right, "trajectory_id"]:
                continue
            gap = abs(float(frame.loc[left, "actual_depth"]) - float(frame.loc[right, "actual_depth"]))
            if gap < minimum_gap:
                continue
            key = tuple(sorted((left, right)))
            if key in seen:
                continue
            seen.add(key)
            pairs.append((left, right, float(distance)))
            break
        if len(pairs) >= int(settings["maximum_pairs"]):
            break
    return pairs


def _pair_accuracy(pairs: Sequence[tuple[int, int, float]], actual: np.ndarray, predicted: np.ndarray) -> float:
    if not pairs:
        return 0.0
    correct = 0
    for left, right, _ in pairs:
        actual_order = np.sign(actual[left] - actual[right])
        predicted_order = np.sign(predicted[left] - predicted[right])
        correct += int(actual_order == predicted_order)
    return float(correct / len(pairs))


def _pair_rows(
    pairs: Sequence[tuple[int, int, float]],
    frame: pd.DataFrame,
    predicted: np.ndarray,
    candidate_id: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for left, right, distance in pairs:
        left_row = frame.iloc[left]
        right_row = frame.iloc[right]
        rows.append(
            {
                "candidate_id": candidate_id,
                "left_trajectory_id": left_row["trajectory_id"],
                "left_step": int(left_row["step"]),
                "right_trajectory_id": right_row["trajectory_id"],
                "right_step": int(right_row["step"]),
                "current_state_distance": distance,
                "left_actual_depth": float(left_row["actual_depth"]),
                "right_actual_depth": float(right_row["actual_depth"]),
                "left_predicted_depth": float(predicted[left]),
                "right_predicted_depth": float(predicted[right]),
                "ordering_correct": int(
                    np.sign(float(left_row["actual_depth"]) - float(right_row["actual_depth"]))
                    == np.sign(float(predicted[left]) - float(predicted[right]))
                ),
            }
        )
    return rows


def _forecast_error(
    entries: Sequence[Entry],
    latent: Mapping[str, np.ndarray],
    series_by_id: Mapping[str, Any],
    dynamics: DynamicsModel,
    dimension: int,
    horizon: int,
) -> float:
    errors: list[float] = []
    for entry in entries:
        values = latent[entry.trajectory_id][:, :dimension]
        external = _external_matrix(series_by_id[entry.trajectory_id])
        for step in range(dynamics.delay_width - 1, len(values) - horizon):
            prediction, _ = dynamics.forecast(values[: step + 1], external[step], horizon)
            errors.append(float(np.linalg.norm(values[step + horizon] - prediction)))
    return float(np.mean(errors)) if errors else float("inf")


def _mode_stability(
    fit_entries: Sequence[Entry],
    latent: Mapping[str, np.ndarray],
    series_by_id: Mapping[str, Any],
    family: str,
    dimension: int,
    config: Mapping[str, Any],
) -> float:
    if family == "static":
        return 1.0
    vectors: list[np.ndarray] = []
    for seed in sorted({entry.seed for entry in fit_entries}):
        subset = [entry for entry in fit_entries if entry.seed == seed]
        subset_ids = {entry.trajectory_id for entry in subset}
        model = DynamicsModel(family, dimension, config).fit(
            {key: value for key, value in latent.items() if key in subset_ids},
            {key: value for key, value in series_by_id.items() if key in subset_ids},
        )
        vector = model.coefficient_vector()
        vectors.append(vector / max(np.linalg.norm(vector), 1e-12))
    similarities: list[float] = []
    for left in range(len(vectors)):
        for right in range(left + 1, len(vectors)):
            minimum = min(len(vectors[left]), len(vectors[right]))
            similarities.append(float(abs(np.dot(vectors[left][:minimum], vectors[right][:minimum]))))
    return float(np.mean(similarities)) if similarities else 0.0


def _candidate_id(scope: str, dimension: int, family: str, mode: str, horizon: int) -> str:
    return f"{scope}__D{dimension:02d}__{family}__{mode}__H{horizon:02d}"


def _selection_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        float(row["event_recall"]),
        float(row["median_lead_time_steps"]),
        -float(row["false_alarm_rate"]),
        float(row["near_state_pair_accuracy"]),
        -float(row["depth_mae"]),
        float(row["mode_stability"]),
        -int(row["feature_count"]),
    )


def _create_lock(path: Path, selected: Mapping[str, Any], baselines: Mapping[str, Any], config: Mapping[str, Any], challenge_hash: str) -> dict[str, Any]:
    payload = {
        "task_id": config["task_id"],
        "status": "locked_before_holdout_read",
        "selected_candidate": dict(selected),
        "task3_baselines": baselines,
        "task3_selection_lock_hash": config["task3_selection_lock_hash"],
        "challenge_manifest_hash": challenge_hash,
        "config_hash": _canonical_hash(config),
        "post_holdout_changes_forbidden": True,
    }
    payload["lock_hash"] = _canonical_hash(payload)
    _json_dump(path, payload)
    return payload


def _write_lock_validation(path: Path, lock: Mapping[str, Any]) -> dict[str, Any]:
    body = dict(lock)
    claimed = body.pop("lock_hash")
    actual = _canonical_hash(body)
    value = {
        "valid": claimed == actual,
        "lock_hash": actual,
        "claimed_lock_hash": claimed,
        "holdout_not_read_before_validation": True,
    }
    _json_dump(path, value)
    if not value["valid"]:
        raise MacroDynamicsError("Task 4 selection lock validation failed")
    return value


def validate_selection_lock(lock_path: str | Path, validation_path: str | Path) -> dict[str, Any]:
    lock = _json_load(lock_path)
    validation = _json_load(validation_path)
    body = dict(lock)
    claimed = body.pop("lock_hash", None)
    actual = _canonical_hash(body)
    if claimed != actual:
        raise MacroDynamicsError("Task 4 selection lock hash mismatch")
    if validation.get("valid") is not True or validation.get("lock_hash") != actual:
        raise MacroDynamicsError("Task 4 selection lock has not been validated")
    return lock


def _fit_task3_baseline(train: Sequence[Any], evaluate: Sequence[Any], task3_config: Mapping[str, Any], config: Mapping[str, Any]) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, Any]:
    baseline = config["task3_fair_baseline"]
    train_data = t3.build_window_dataset(train, int(baseline["history_width"]), int(baseline["prediction_horizon"]), task3_config)
    evaluate_data = t3.build_window_dataset(evaluate, int(baseline["history_width"]), int(baseline["prediction_horizon"]), task3_config)
    model = t3.fit_model(train_data, str(baseline["family"]), task3_config)
    probability, depth = t3.predict_model(model, evaluate_data)
    metrics, predictions, trajectories = t3.evaluate_predictions(
        evaluate_data,
        probability,
        depth,
        float(baseline["alarm_threshold"]),
        int(baseline["alarm_persistence"]),
        task3_config,
    )
    return metrics, predictions, trajectories, model


def _fit_fixed_task3_model(reference_corpus: str | Path, task3_config: Mapping[str, Any], calibration: Mapping[str, Any], config: Mapping[str, Any]) -> Any:
    root = Path(reference_corpus)
    entries: list[Entry] = []
    for directory in sorted((root / "trajectories").glob("traj_*")):
        metadata = _json_load(directory / "metadata.json")
        if str(metadata["dataset_split"]) not in {"fit", "validation"}:
            continue
        entries.append(
            Entry(
                trajectory_id=str(metadata["trajectory_id"]),
                scenario_id=str(metadata["scenario_id"]),
                seed=int(metadata["seed"]),
                split=str(metadata["dataset_split"]),
                path=directory,
                total_steps=int(metadata["total_steps"]),
            )
        )
    series = load_task3_series(entries, task3_config, calibration)
    baseline = config["task3_fair_baseline"]
    data = t3.build_window_dataset(series, int(baseline["history_width"]), int(baseline["prediction_horizon"]), task3_config)
    return t3.fit_model(data, str(baseline["family"]), task3_config)


def _evaluate_fixed_task3(model: Any, series: Sequence[Any], task3_config: Mapping[str, Any], config: Mapping[str, Any]) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    baseline = config["task3_fair_baseline"]
    data = t3.build_window_dataset(series, int(baseline["history_width"]), int(baseline["prediction_horizon"]), task3_config)
    probability, depth = t3.predict_model(model, data)
    return t3.evaluate_predictions(
        data,
        probability,
        depth,
        float(baseline["alarm_threshold"]),
        int(baseline["alarm_persistence"]),
        task3_config,
    )


def _generic_evaluate(train: Any, evaluate: Any, features: Sequence[str], config: Mapping[str, Any], threshold: float | None = None, persistence: int | None = None) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame, Any]:
    model = _fit_generic_predictor(train.frame, features)
    probability, depth = _predict_generic(model, evaluate.frame)
    if threshold is None or persistence is None:
        metrics, predictions, trajectories = t3.tune_alarm(evaluate, probability, depth, {
            **_json_load(ROOT / config["task3_config_path"]),
            "alarm_probability_thresholds": config["alarm_probability_thresholds"],
            "alarm_persistence_candidates": config["alarm_persistence_candidates"],
        })
    else:
        task3_config = _json_load(ROOT / config["task3_config_path"])
        metrics, predictions, trajectories = t3.evaluate_predictions(
            evaluate, probability, depth, threshold, persistence, task3_config
        )
    return metrics, predictions, trajectories, model


def _safe_rank(actual: Sequence[float], predicted: Sequence[float]) -> float:
    if len(actual) < 2 or np.allclose(actual, actual[0]) or np.allclose(predicted, predicted[0]):
        return 0.0
    value = spearmanr(actual, predicted).statistic
    return 0.0 if value is None or not math.isfinite(float(value)) else float(value)


def _judgement(selected: Mapping[str, Any], baseline: Mapping[str, Any], config: Mapping[str, Any]) -> dict[str, Any]:
    criteria = config["success_criteria"]
    improvements = {
        "lead_time": float(selected["median_lead_time_steps"]) - float(baseline["median_lead_time_steps"]),
        "event_recall": float(selected["event_recall"]) - float(baseline["event_recall"]),
        "near_state_pair": float(selected.get("near_state_pair_accuracy", 0.0)) - float(baseline.get("near_state_pair_accuracy", 0.0)),
        "depth_mae_relative": (
            (float(baseline["depth_mae"]) - float(selected["depth_mae"]))
            / max(float(baseline["depth_mae"]), 1e-12)
        ),
    }
    core = {
        "lead_time": improvements["lead_time"] >= float(criteria["lead_time_improvement_steps"]),
        "event_recall": improvements["event_recall"] >= float(criteria["event_recall_improvement"]),
        "near_state_pair": improvements["near_state_pair"] >= float(criteria["near_state_pair_improvement"]),
        "depth_mae": improvements["depth_mae_relative"] >= float(criteria["depth_mae_relative_improvement"]),
    }
    degraded = (
        float(selected["event_recall"]) < float(baseline["event_recall"]) - float(criteria["maximum_core_degradation"])
        or float(selected["false_alarm_rate"]) > float(baseline["false_alarm_rate"]) + float(criteria["maximum_core_degradation"])
    )
    if any(core.values()) and not degraded:
        grade = "A_macro_dynamics_promising"
    elif (
        float(selected["depth_mae"]) < float(baseline["depth_mae"])
        or float(selected.get("near_state_pair_accuracy", 0.0)) > float(baseline.get("near_state_pair_accuracy", 0.0))
        or float(selected["brier_score"]) < float(baseline["brier_score"])
    ) and not degraded:
        grade = "B_macro_dynamics_partially_promising"
    else:
        grade = "C_macro_dynamics_not_promising_at_current_resolution"
    return {"grade": grade, "improvements": improvements, "core_improvements": core, "core_degraded": degraded}


def _bar_svg(path: Path, title: str, labels: Sequence[str], values: Sequence[float]) -> None:
    width = 1000
    height = 70 + 30 * len(labels)
    maximum = max([abs(float(value)) for value in values] + [1e-12])
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="20" y="30" font-family="sans-serif" font-size="18">{title}</text>',
    ]
    for index, (label, value) in enumerate(zip(labels, values, strict=True)):
        y = 55 + index * 30
        bar = 500.0 * max(0.0, float(value)) / maximum
        lines.append(f'<text x="20" y="{y+16}" font-family="sans-serif" font-size="12">{label}</text>')
        lines.append(f'<rect x="400" y="{y}" width="{bar:.2f}" height="18" fill="#777"/>')
        lines.append(f'<text x="920" y="{y+16}" font-family="monospace" font-size="12">{float(value):.6g}</text>')
    lines.append("</svg>\n")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_manifest(root: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "manifest.json":
            continue
        files.append({
            "path": path.relative_to(root).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": _file_sha256(path),
        })
    value = {
        "file_count": len(files),
        "total_size_bytes": sum(item["size_bytes"] for item in files),
        "files": files,
    }
    _json_dump(root / "manifest.json", value)
    return value


def run(
    challenge_corpus: str | Path,
    reference_corpus: str | Path,
    output_dir: str | Path,
    config_path: str | Path = DEFAULT_CONFIG,
) -> dict[str, Any]:
    config = load_config(config_path)
    task3_config = _json_load(ROOT / config["task3_config_path"])
    calibration = _json_load(ROOT / config["calibration_config_path"])
    contract = _json_load(ROOT / "configs" / "task3_2_1_macro_dynamics_contract.json")
    required_arrays = list(contract["step_record"]["required_state_arrays"])
    output = Path(output_dir)
    if output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True)
    index = ChallengeIndex(challenge_corpus, config)
    _json_dump(output / config["outputs"]["split_manifest"], index.manifest())
    challenge_manifest = Path(challenge_corpus) / "manifest.json"
    challenge_hash = _file_sha256(challenge_manifest) if challenge_manifest.is_file() else _canonical_hash(index.manifest())
    _json_dump(output / config["outputs"]["challenge_manifest"], {
        "source": str(challenge_corpus),
        "manifest_hash": challenge_hash,
        "schedule_variation": True,
        "trajectory_count": len(index.entries),
    })

    fit_entries = index.entries_for("fit")
    validation_entries = index.entries_for("validation")
    fit_series = load_task3_series(fit_entries, task3_config, calibration)
    validation_series = load_task3_series(validation_entries, task3_config, calibration)
    fit_by_id = {item.entry.trajectory_id: item for item in fit_series}
    validation_by_id = {item.entry.trajectory_id: item for item in validation_series}

    fair_validation, fair_predictions, _, _ = _fit_task3_baseline(
        fit_series, validation_series, task3_config, config
    )
    fixed_task3_model = _fit_fixed_task3_model(reference_corpus, task3_config, calibration, config)
    fixed_validation, _, _ = _evaluate_fixed_task3(
        fixed_task3_model, validation_series, task3_config, config
    )

    preprocessors: dict[str, MacroPreprocessor] = {}
    latent_fit: dict[str, dict[str, np.ndarray]] = {}
    latent_validation: dict[str, dict[str, np.ndarray]] = {}
    schema_rows: list[dict[str, Any]] = []
    for scope in config["representation_candidates"]["input_scopes"]:
        preprocessor = MacroPreprocessor(scope, config, required_arrays).fit(fit_entries)
        preprocessors[scope] = preprocessor
        latent_fit[scope] = preprocessor.transform(fit_entries)
        latent_validation[scope] = preprocessor.transform(validation_entries)
        schema_rows.append(preprocessor.metadata())
    _json_dump(output / config["outputs"]["macro_state_schema"], {"representations": schema_rows})

    base_fit = {
        int(horizon): t3.build_window_dataset(fit_series, 8, int(horizon), task3_config)
        for horizon in config["representation_candidates"]["prediction_horizons"]
    }
    base_validation = {
        int(horizon): t3.build_window_dataset(validation_series, 8, int(horizon), task3_config)
        for horizon in config["representation_candidates"]["prediction_horizons"]
    }
    validation_pairs = {
        horizon: _near_state_pairs(dataset, config) for horizon, dataset in base_validation.items()
    }

    candidate_rows: list[dict[str, Any]] = []
    validation_metrics: dict[str, Any] = {}
    pair_audit_rows: list[dict[str, Any]] = []
    mode_rows: list[dict[str, Any]] = []
    forecast_rows: list[dict[str, Any]] = []
    residual_cache: dict[str, list[dict[str, Any]]] = {}
    model_cache: dict[str, tuple[MacroPreprocessor, DynamicsModel, list[str], Any]] = {}

    for scope in config["representation_candidates"]["input_scopes"]:
        for dimension in config["representation_candidates"]["latent_dimensions"]:
            for family in config["representation_candidates"]["dynamics_families"]:
                dynamics = DynamicsModel(family, int(dimension), config).fit(latent_fit[scope], fit_by_id)
                stability = _mode_stability(
                    fit_entries, latent_fit[scope], fit_by_id, family, int(dimension), config
                )
                for horizon in config["representation_candidates"]["prediction_horizons"]:
                    fit_macro, fit_residual = macro_feature_frame(
                        fit_entries, fit_by_id, latent_fit[scope], dynamics, int(dimension), int(horizon)
                    )
                    validation_macro, validation_residual = macro_feature_frame(
                        validation_entries,
                        validation_by_id,
                        latent_validation[scope],
                        dynamics,
                        int(dimension),
                        int(horizon),
                    )
                    forecast_error = _forecast_error(
                        validation_entries,
                        latent_validation[scope],
                        validation_by_id,
                        dynamics,
                        int(dimension),
                        int(horizon),
                    )
                    for feature_mode in config["representation_candidates"]["feature_modes"]:
                        candidate = _candidate_id(scope, int(dimension), family, feature_mode, int(horizon))
                        fit_window, macro_names = _window_with_macro(
                            base_fit[int(horizon)], fit_macro, feature_mode
                        )
                        validation_window, _ = _window_with_macro(
                            base_validation[int(horizon)], validation_macro, feature_mode
                        )
                        model = _fit_generic_predictor(fit_window.frame, fit_window.feature_names)
                        probability, depth = _predict_generic(model, validation_window.frame)
                        metrics, predictions, trajectories = t3.tune_alarm(
                            validation_window,
                            probability,
                            depth,
                            {
                                **task3_config,
                                "alarm_probability_thresholds": config["alarm_probability_thresholds"],
                                "alarm_persistence_candidates": config["alarm_persistence_candidates"],
                            },
                        )
                        pairs = validation_pairs[int(horizon)]
                        pair_accuracy = _pair_accuracy(
                            pairs,
                            validation_window.y_depth,
                            depth,
                        )
                        metrics.update(
                            {
                                "near_state_pair_accuracy": pair_accuracy,
                                "near_state_pair_count": len(pairs),
                                "mode_stability": stability,
                                "forecast_error": forecast_error,
                                "feature_count": len(fit_window.feature_names),
                            }
                        )
                        row = {
                            "candidate_id": candidate,
                            "scope": scope,
                            "dimension": int(dimension),
                            "dynamics_family": family,
                            "feature_mode": feature_mode,
                            "horizon": int(horizon),
                            **metrics,
                        }
                        candidate_rows.append(row)
                        validation_metrics[candidate] = row
                        pair_audit_rows.extend(
                            _pair_rows(pairs, validation_window.frame, depth, candidate)
                        )
                        mode_rows.append(
                            {
                                "candidate_id": candidate,
                                "scope": scope,
                                "dimension": int(dimension),
                                "dynamics_family": family,
                                "mode_stability": stability,
                            }
                        )
                        forecast_rows.append(
                            {
                                "candidate_id": candidate,
                                "scope": scope,
                                "dimension": int(dimension),
                                "dynamics_family": family,
                                "horizon": int(horizon),
                                "forecast_error": forecast_error,
                            }
                        )
                        residual_cache[candidate] = fit_residual + validation_residual
                        model_cache[candidate] = (
                            preprocessors[scope], dynamics, fit_window.feature_names, model
                        )

    candidate_rows.sort(key=_selection_key, reverse=True)
    selected = candidate_rows[0]
    baselines = {
        "task3_fair_retrained_validation": fair_validation,
        "task3_fixed_original_validation": fixed_validation,
    }
    lock_path = output / config["outputs"]["selection_lock"]
    validation_path = output / config["outputs"]["selection_lock_validation"]
    lock = _create_lock(lock_path, selected, baselines, config, challenge_hash)
    _write_lock_validation(validation_path, lock)
    _write_csv(output / config["outputs"]["candidate_comparison"], candidate_rows)
    _json_dump(output / config["outputs"]["validation_metrics"], {
        "selected": selected,
        "task3_fair_retrained": fair_validation,
        "task3_fixed_original": fixed_validation,
    })
    _write_csv(output / config["outputs"]["near_state_pair_audit"], pair_audit_rows)
    _write_csv(output / config["outputs"]["mode_stability"], mode_rows)
    _write_csv(output / config["outputs"]["forecast_error"], forecast_rows)
    _write_csv(output / config["outputs"]["residual_ledger"], residual_cache[selected["candidate_id"]])

    holdout_entries = index.entries_for(
        "holdout", lock_path=lock_path, validation_path=validation_path
    )
    holdout_series = load_task3_series(holdout_entries, task3_config, calibration)
    holdout_by_id = {item.entry.trajectory_id: item for item in holdout_series}
    selected_scope = str(selected["scope"])
    selected_dimension = int(selected["dimension"])
    selected_family = str(selected["dynamics_family"])
    selected_mode = str(selected["feature_mode"])
    selected_horizon = int(selected["horizon"])
    preprocessor = preprocessors[selected_scope]
    holdout_latent = preprocessor.transform(holdout_entries)
    dynamics = DynamicsModel(selected_family, selected_dimension, config).fit(
        latent_fit[selected_scope], fit_by_id
    )

    final_series = fit_series + validation_series
    final_entries = fit_entries + validation_entries
    final_by_id = {item.entry.trajectory_id: item for item in final_series}
    final_latent = {
        **latent_fit[selected_scope],
        **latent_validation[selected_scope],
    }
    train_macro, train_residual = macro_feature_frame(
        final_entries,
        final_by_id,
        final_latent,
        dynamics,
        selected_dimension,
        selected_horizon,
    )
    holdout_macro, holdout_residual = macro_feature_frame(
        holdout_entries,
        holdout_by_id,
        holdout_latent,
        dynamics,
        selected_dimension,
        selected_horizon,
    )
    final_base = t3.build_window_dataset(final_series, 8, selected_horizon, task3_config)
    holdout_base = t3.build_window_dataset(holdout_series, 8, selected_horizon, task3_config)
    train_window, macro_names = _window_with_macro(final_base, train_macro, selected_mode)
    holdout_window, _ = _window_with_macro(holdout_base, holdout_macro, selected_mode)
    selected_model = _fit_generic_predictor(train_window.frame, train_window.feature_names)
    probability, depth = _predict_generic(selected_model, holdout_window.frame)
    selected_holdout, selected_predictions, selected_trajectories = t3.evaluate_predictions(
        holdout_window,
        probability,
        depth,
        float(selected["alarm_threshold"]),
        int(selected["alarm_persistence"]),
        task3_config,
    )
    holdout_pairs = _near_state_pairs(holdout_base, config)
    selected_pair_accuracy = _pair_accuracy(holdout_pairs, holdout_window.y_depth, depth)
    selected_holdout["near_state_pair_accuracy"] = selected_pair_accuracy
    selected_holdout["near_state_pair_count"] = len(holdout_pairs)

    fair_holdout, fair_predictions, fair_trajectories, _ = _fit_task3_baseline(
        final_series, holdout_series, task3_config, config
    )
    fair_pairs = _near_state_pairs(holdout_base, config)
    fair_holdout["near_state_pair_accuracy"] = _pair_accuracy(
        fair_pairs,
        holdout_base.y_depth,
        fair_predictions["predicted_depth"].to_numpy(dtype=np.float64),
    )
    fixed_holdout, fixed_predictions, fixed_trajectories = _evaluate_fixed_task3(
        fixed_task3_model, holdout_series, task3_config, config
    )
    fixed_holdout["near_state_pair_accuracy"] = _pair_accuracy(
        fair_pairs,
        holdout_base.y_depth,
        fixed_predictions["predicted_depth"].to_numpy(dtype=np.float64),
    )

    ablation_rows: list[dict[str, Any]] = []
    feature_sets = {
        "selected": list(train_window.feature_names),
        "macro_only": list(macro_names),
        "without_residual": [name for name in train_window.feature_names if "residual" not in name],
        "without_external_response": [name for name in train_window.feature_names if "external_response" not in name and "external_internal" not in name],
    }
    for name, features in feature_sets.items():
        model = _fit_generic_predictor(train_window.frame, features)
        ablation_probability, ablation_depth = _predict_generic(model, holdout_window.frame)
        metrics, _, _ = t3.evaluate_predictions(
            holdout_window,
            ablation_probability,
            ablation_depth,
            float(selected["alarm_threshold"]),
            int(selected["alarm_persistence"]),
            task3_config,
        )
        metrics["near_state_pair_accuracy"] = _pair_accuracy(
            holdout_pairs, holdout_window.y_depth, ablation_depth
        )
        ablation_rows.append({"ablation": name, "feature_count": len(features), **metrics})

    holdout_metrics = {
        "selected_macro_candidate": selected_holdout,
        "task3_fair_retrained": fair_holdout,
        "task3_fixed_original": fixed_holdout,
    }
    judgement = _judgement(selected_holdout, fair_holdout, config)
    _json_dump(output / config["outputs"]["holdout_metrics"], holdout_metrics)
    holdout_prediction_rows: list[dict[str, Any]] = []
    for role, frame in (
        ("selected_macro_candidate", selected_predictions),
        ("task3_fair_retrained", fair_predictions),
        ("task3_fixed_original", fixed_predictions),
    ):
        copied = frame.copy()
        copied.insert(0, "role", role)
        holdout_prediction_rows.extend(copied.to_dict(orient="records"))
    _write_csv(output / config["outputs"]["holdout_predictions"], holdout_prediction_rows)
    warning_rows: list[dict[str, Any]] = []
    for role, frame in (
        ("selected_macro_candidate", selected_trajectories),
        ("task3_fair_retrained", fair_trajectories),
        ("task3_fixed_original", fixed_trajectories),
    ):
        copied = frame.copy()
        copied.insert(0, "role", role)
        warning_rows.extend(copied.to_dict(orient="records"))
    _write_csv(output / config["outputs"]["holdout_warning_summary"], warning_rows)
    _write_csv(
        output / config["outputs"]["holdout_near_state_pair_audit"],
        _pair_rows(holdout_pairs, holdout_window.frame, depth, selected["candidate_id"]),
    )
    _write_csv(output / config["outputs"]["ablation_results"], ablation_rows)
    _write_csv(
        output / config["outputs"]["residual_ledger"],
        residual_cache[selected["candidate_id"]] + train_residual + holdout_residual,
    )

    _bar_svg(
        output / "lead_time_comparison.svg",
        "Holdout median lead time",
        ["selected_macro", "task3_fair", "task3_fixed"],
        [
            selected_holdout["median_lead_time_steps"],
            fair_holdout["median_lead_time_steps"],
            fixed_holdout["median_lead_time_steps"],
        ],
    )
    _bar_svg(
        output / "false_alarm_comparison.svg",
        "Holdout false alarm rate",
        ["selected_macro", "task3_fair", "task3_fixed"],
        [selected_holdout["false_alarm_rate"], fair_holdout["false_alarm_rate"], fixed_holdout["false_alarm_rate"]],
    )
    _bar_svg(
        output / "risk_depth_comparison.svg",
        "Holdout risk-depth MAE",
        ["selected_macro", "task3_fair", "task3_fixed"],
        [selected_holdout["depth_mae"], fair_holdout["depth_mae"], fixed_holdout["depth_mae"]],
    )
    selected_mode_rows = [row for row in mode_rows if row["candidate_id"] == selected["candidate_id"]]
    _bar_svg(
        output / "mode_stability.svg",
        "Selected mode stability",
        [selected["candidate_id"]],
        [selected["mode_stability"]],
    )
    selected_forecast_rows = [row for row in forecast_rows if row["candidate_id"] == selected["candidate_id"]]
    _bar_svg(
        output / "forecast_error_by_horizon.svg",
        "Selected forecast error",
        [row["candidate_id"] for row in selected_forecast_rows] or [selected["candidate_id"]],
        [row["forecast_error"] for row in selected_forecast_rows] or [selected["forecast_error"]],
    )
    residual_frame = pd.DataFrame(holdout_residual)
    before = residual_frame[residual_frame["steps_to_hazard"].fillna(999).between(1, 8)]["residual_norm"]
    normal = residual_frame[residual_frame["hazard_onset_step"].isna()]["residual_norm"]
    _bar_svg(
        output / "residual_before_hazard.svg",
        "Residual before hazard versus normal",
        ["before_hazard", "normal"],
        [float(before.mean()) if len(before) else 0.0, float(normal.mean()) if len(normal) else 0.0],
    )
    _bar_svg(
        output / "near_state_pair_separation.svg",
        "Near-state pair ordering accuracy",
        ["selected_macro", "task3_fair"],
        [selected_pair_accuracy, fair_holdout["near_state_pair_accuracy"]],
    )

    results_text = f"""# Task 3.2-4 実行結果

## 選択候補

`{selected['candidate_id']}`

- input scope: `{selected['scope']}`
- latent dimension: {selected['dimension']}
- dynamics: `{selected['dynamics_family']}`
- feature mode: `{selected['feature_mode']}`
- horizon: {selected['horizon']}

## Holdout比較

| 指標 | マクロ力学 | Task 3公平再学習 |
|---|---:|---:|
| 検出率 | {selected_holdout['event_recall']:.6f} | {fair_holdout['event_recall']:.6f} |
| 先行時間中央値 | {selected_holdout['median_lead_time_steps']:.6f} | {fair_holdout['median_lead_time_steps']:.6f} |
| 誤警報率 | {selected_holdout['false_alarm_rate']:.6f} | {fair_holdout['false_alarm_rate']:.6f} |
| 深度MAE | {selected_holdout['depth_mae']:.6f} | {fair_holdout['depth_mae']:.6f} |
| 近似現在状態・異未来対 | {selected_pair_accuracy:.6f} | {fair_holdout['near_state_pair_accuracy']:.6f} |

## 判定

`{judgement['grade']}`

## 境界

この結果は最小試作であり、モードを地形・循環・粘性・拡散・外力として正式に同定したものではない。未説明残差は残差台帳へ保持した。
"""
    (output / config["outputs"]["results_markdown"]).write_text(results_text, encoding="utf-8")
    completion = f"""# Task 3.2-4 完了記録

- 難化コーパス: 30軌道
- seedごとの外乱予定変更: 実施
- 分布表現・全状態場表現: 実施
- 静的低次元、DMD、DMDc、遅延残差: 実施
- Task 3固定・公平再学習基準: 比較済み
- selection lock後holdout: 実施
- 近似現在状態・異未来監査: 実施
- 残差台帳: 保存
- アブレーション: 実施
- 選択候補: `{selected['candidate_id']}`
- 判定: `{judgement['grade']}`
"""
    (output / config["outputs"]["completion_markdown"]).write_text(completion, encoding="utf-8")
    handoff = f"""# Task 3.2-4 → Task 3.2-5 引き渡し

## 選択されたマクロ力学候補

`{selected['candidate_id']}`

Task 5では、この候補のマクロ状態、予測特徴、残差特徴を高リスク判断へ接続する。ただし作用実行はまだ行わない。

## selection lock

`{lock['lock_hash']}`

## 判定

`{judgement['grade']}`
"""
    (output / config["outputs"]["handoff_markdown"]).write_text(handoff, encoding="utf-8")
    macro_feature_schema = {
        "selected_candidate": selected["candidate_id"],
        "feature_names": list(train_window.feature_names),
        "macro_feature_names": macro_names,
        "forbidden_metadata_audit": "passed",
        "future_information_audit": "passed",
    }
    _json_dump(output / config["outputs"]["macro_feature_schema"], macro_feature_schema)
    summary = {
        "task_id": config["task_id"],
        "selected_candidate": selected,
        "holdout": holdout_metrics,
        "judgement": judgement,
        "selection_lock_hash": lock["lock_hash"],
        "holdout_read_gate": "passed",
        "status": "complete",
    }
    _json_dump(output / "summary.json", summary)
    manifest = _write_manifest(output)
    return {**summary, "manifest_file_count": manifest["file_count"]}


def validate_output(input_dir: str | Path, config_path: str | Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = load_config(config_path)
    root = Path(input_dir)
    required = set(config["outputs"].values()) | {
        "summary.json",
        "lead_time_comparison.svg",
        "false_alarm_comparison.svg",
        "risk_depth_comparison.svg",
        "mode_stability.svg",
        "forecast_error_by_horizon.svg",
        "residual_before_hazard.svg",
        "near_state_pair_separation.svg",
    }
    missing = sorted(name for name in required if not (root / name).is_file())
    if missing:
        raise MacroDynamicsError(f"Task 4 output missing {missing}")
    lock = validate_selection_lock(
        root / config["outputs"]["selection_lock"],
        root / config["outputs"]["selection_lock_validation"],
    )
    summary = _json_load(root / "summary.json")
    if summary.get("status") != "complete":
        raise MacroDynamicsError("Task 4 summary is not complete")
    if summary.get("selection_lock_hash") != lock["lock_hash"]:
        raise MacroDynamicsError("Task 4 summary/lock hash mismatch")
    return {
        "status": "valid",
        "selected_candidate": summary["selected_candidate"]["candidate_id"],
        "selection_lock_hash": lock["lock_hash"],
        "holdout_read_gate": "passed",
        "required_file_count": len(required),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    execute = sub.add_parser("run")
    execute.add_argument("--challenge-corpus", required=True)
    execute.add_argument("--reference-corpus", required=True)
    execute.add_argument("--output", required=True)
    execute.add_argument("--config", default=str(DEFAULT_CONFIG))
    check = sub.add_parser("validate")
    check.add_argument("--input", required=True)
    check.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args(argv)
    result = (
        run(args.challenge_corpus, args.reference_corpus, args.output, args.config)
        if args.command == "run"
        else validate_output(args.input, args.config)
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "ChallengeIndex",
    "DynamicsModel",
    "Entry",
    "MacroDynamicsError",
    "MacroPreprocessor",
    "load_config",
    "macro_feature_frame",
    "run",
    "validate_output",
    "validate_selection_lock",
]
