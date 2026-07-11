"""Task 3.2-3: simple prediction and early-warning baselines.

This module measures how far current state and simple observed history can
anticipate high-risk transitions before any macro-dynamics extraction is used.
It enforces trajectory/seed split isolation and refuses to read holdout state
files until a validated selection lock exists.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    precision_recall_curve,
    precision_score,
    recall_score,
)
from sklearn.preprocessing import StandardScaler

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_CONFIG = ROOT / "configs" / "task3_2_3_simple_early_warning.json"
EXTERNAL_FIELDS = (
    "external_resource_supply",
    "external_demand",
    "external_competition_pressure",
    "external_information_noise",
    "external_shock",
    "external_constraint_pressure",
)
CURRENT_MODEL_FAMILIES = {"current_risk_threshold", "current_state_logistic"}
HISTORY_MODEL_FAMILIES = {"trend_extrapolation", "history_logistic"}


class BaselineError(ValueError):
    """Raised when Task 3.2-3 boundaries or data contracts are violated."""


def _json_load(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _json_dump(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise BaselineError(f"{path}:{line_number} must contain an object")
            rows.append(value)
    return rows


def _write_csv(path: str | Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, np.number)):
        raise BaselineError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise BaselineError(f"{name} must be finite")
    return result


def load_config(path: str | Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = _json_load(path)
    validate_config(config)
    return config


def validate_config(config: Mapping[str, Any]) -> None:
    required = {
        "history_widths",
        "prediction_horizons",
        "alarm_persistence_candidates",
        "alarm_probability_thresholds",
        "model_families",
        "split_contract",
        "current_weighted_arrays",
        "transition_weighted_arrays",
        "transition_scalar_fields",
        "history_base_features",
        "history_statistics",
        "model_parameters",
        "selection_weights",
        "forbidden_feature_tokens",
        "outputs",
    }
    missing = sorted(required - set(config))
    if missing:
        raise BaselineError(f"config missing {missing}")
    for name in ("history_widths", "prediction_horizons", "alarm_persistence_candidates"):
        values = config[name]
        if not isinstance(values, list) or not values or any(
            isinstance(value, bool) or not isinstance(value, int) or value < 1 for value in values
        ):
            raise BaselineError(f"{name} must contain positive integers")
        if len(values) != len(set(values)):
            raise BaselineError(f"{name} must not contain duplicates")
    thresholds = config["alarm_probability_thresholds"]
    if not isinstance(thresholds, list) or not thresholds or any(
        not 0.0 < _finite(value, "alarm threshold") < 1.0 for value in thresholds
    ):
        raise BaselineError("alarm_probability_thresholds must be inside (0, 1)")
    expected_families = {
        "always_safe",
        "current_risk_threshold",
        "current_state_logistic",
        "trend_extrapolation",
        "history_logistic",
    }
    if set(config["model_families"]) != expected_families:
        raise BaselineError("model_families must contain the five frozen baseline families")
    split = config["split_contract"]
    fit = set(split["fit_seeds"])
    validation = set(split["validation_seeds"])
    holdout = set(split["holdout_seeds"])
    if not fit or not validation or not holdout or fit & validation or fit & holdout or validation & holdout:
        raise BaselineError("fit, validation, and holdout seed sets must be non-empty and disjoint")
    if split.get("holdout_requires_validated_selection_lock") is not True:
        raise BaselineError("holdout lock requirement must remain enabled")
    if split.get("random_row_split_forbidden") is not True:
        raise BaselineError("random row split must remain forbidden")


@dataclass(frozen=True)
class CorpusEntry:
    trajectory_id: str
    scenario_id: str
    seed: int
    split: str
    path: Path
    total_steps: int


@dataclass
class TrajectorySeries:
    entry: CorpusEntry
    features: list[dict[str, float]]
    relative_risk: np.ndarray | None = None
    hazard_mask: np.ndarray | None = None
    hazard_kind: list[str] | None = None
    hazard_onset_step: int | None = None


@dataclass
class WindowDataset:
    frame: pd.DataFrame
    feature_names: list[str]
    current_feature_names: list[str]
    history_width: int
    horizon: int

    @property
    def X(self) -> np.ndarray:
        return self.frame[self.feature_names].to_numpy(dtype=np.float64)

    @property
    def y_event(self) -> np.ndarray:
        return self.frame["actual_event"].to_numpy(dtype=np.int64)

    @property
    def y_depth(self) -> np.ndarray:
        return self.frame["actual_depth"].to_numpy(dtype=np.float64)


class CorpusIndex:
    """Metadata-only corpus index with an explicit holdout read gate."""

    def __init__(self, root: str | Path, config: Mapping[str, Any]):
        self.root = Path(root)
        self.config = config
        trajectory_root = self.root / "trajectories"
        if not trajectory_root.is_dir():
            raise BaselineError(f"missing trajectory directory: {trajectory_root}")
        entries: list[CorpusEntry] = []
        for directory in sorted(trajectory_root.glob("traj_*")):
            metadata = _json_load(directory / "metadata.json")
            entries.append(
                CorpusEntry(
                    trajectory_id=str(metadata["trajectory_id"]),
                    scenario_id=str(metadata["scenario_id"]),
                    seed=int(metadata["seed"]),
                    split=str(metadata["dataset_split"]),
                    path=directory,
                    total_steps=int(metadata["total_steps"]),
                )
            )
        if not entries:
            raise BaselineError("corpus has no trajectories")
        if len({entry.trajectory_id for entry in entries}) != len(entries):
            raise BaselineError("trajectory_id values must be unique")
        self.entries = entries
        self._validate_splits()

    def _validate_splits(self) -> None:
        contract = self.config["split_contract"]
        expected = {
            "fit": set(int(value) for value in contract["fit_seeds"]),
            "validation": set(int(value) for value in contract["validation_seeds"]),
            "holdout": set(int(value) for value in contract["holdout_seeds"]),
        }
        actual: dict[str, set[int]] = {name: set() for name in expected}
        seen_trajectory: dict[str, str] = {}
        seed_splits: dict[int, set[str]] = {}
        for entry in self.entries:
            if entry.split not in expected:
                raise BaselineError(f"unsupported split {entry.split!r}; exploratory data is not formal input")
            actual[entry.split].add(entry.seed)
            seed_splits.setdefault(entry.seed, set()).add(entry.split)
            previous = seen_trajectory.setdefault(entry.trajectory_id, entry.split)
            if previous != entry.split:
                raise BaselineError(f"trajectory {entry.trajectory_id} appears in multiple splits")
        if any(len(splits) != 1 for splits in seed_splits.values()):
            raise BaselineError("a seed appears in multiple splits")
        if actual != expected:
            raise BaselineError(f"split seed mismatch: expected {expected}, got {actual}")
        reference = str(self.config["stable_reference_scenario"])
        for seed in sorted(seed_splits):
            matches = [entry for entry in self.entries if entry.seed == seed and entry.scenario_id == reference]
            if len(matches) != 1:
                raise BaselineError(f"seed {seed} requires exactly one {reference} trajectory")

    def entries_for(
        self,
        split: str,
        *,
        selection_lock_path: str | Path | None = None,
        selection_validation_path: str | Path | None = None,
    ) -> list[CorpusEntry]:
        if split == "holdout":
            if selection_lock_path is None or selection_validation_path is None:
                raise BaselineError("holdout read blocked until selection lock paths are supplied")
            validate_selection_lock(selection_lock_path, selection_validation_path)
        return [entry for entry in self.entries if entry.split == split]

    def split_manifest(self) -> dict[str, Any]:
        return {
            "trajectory_count": len(self.entries),
            "splits": {
                split: {
                    "seeds": sorted({entry.seed for entry in self.entries if entry.split == split}),
                    "trajectory_ids": sorted(
                        entry.trajectory_id for entry in self.entries if entry.split == split
                    ),
                }
                for split in ("fit", "validation", "holdout")
            },
            "trajectory_level_split": True,
            "seed_level_split": True,
            "random_row_split": False,
        }


def _weighted_mean(distribution: np.ndarray, value: np.ndarray) -> float:
    return float(np.sum(distribution * value))


def _coordinate_arrays(shape: Sequence[int]) -> list[np.ndarray]:
    axes = [np.linspace(0.0, 1.0, int(size)) for size in shape]
    return list(np.meshgrid(*axes, indexing="ij"))


def extract_current_features(
    state_path: str | Path,
    step_record: Mapping[str, Any],
    config: Mapping[str, Any],
) -> dict[str, float]:
    with np.load(state_path, allow_pickle=False) as state:
        distribution = np.asarray(state["distribution"], dtype=np.float64)
        if distribution.ndim != 5 or not np.all(np.isfinite(distribution)):
            raise BaselineError(f"invalid distribution in {state_path}")
        if abs(float(distribution.sum()) - 1.0) > 1e-5:
            raise BaselineError(f"distribution mass mismatch in {state_path}")
        result: dict[str, float] = {
            "entropy": -float(np.sum(distribution * np.log(np.maximum(distribution, 1e-12)))),
            "concentration": float(np.sum(distribution**2)),
            "max_mass": float(np.max(distribution)),
        }
        axis_names = (
            "resource_slack",
            "information_quality",
            "pressure",
            "exploration_room",
            "reversibility",
        )
        for name, coordinate in zip(axis_names, _coordinate_arrays(distribution.shape), strict=True):
            center = float(np.sum(distribution * coordinate))
            result[f"center_{name}"] = center
            result[f"spread_{name}"] = float(
                np.sqrt(np.sum(distribution * (coordinate - center) ** 2))
            )
        for name in config["current_weighted_arrays"]:
            if name not in state.files:
                raise BaselineError(f"state missing weighted array {name}")
            result[f"weighted_{name}"] = _weighted_mean(
                distribution, np.asarray(state[name], dtype=np.float64)
            )
        for name in config["transition_weighted_arrays"]:
            if name not in state.files:
                raise BaselineError(f"state missing transition array {name}")
            result[f"weighted_{name}"] = _weighted_mean(
                distribution, np.asarray(state[name], dtype=np.float64)
            )
        for name in config["transition_scalar_fields"]:
            if name not in state.files:
                raise BaselineError(f"state missing transition scalar {name}")
            result[name] = float(np.asarray(state[name], dtype=np.float64))
        result["moved_mass"] = float(np.sum(np.asarray(state["last_flow"], dtype=np.float64)))

    risk_score = (
        0.20 * result["weighted_damage"]
        + 0.15 * result["weighted_rigidity"]
        + 0.15 * result["weighted_friction"]
        + 0.10 * result["weighted_viscosity"]
        + 0.15 * (1.0 - result["weighted_recovery_speed"])
        + 0.10 * (1.0 - result["weighted_route_support"])
        + 0.05 * (1.0 - result["weighted_viability_reserve"])
        + 0.10 * result["weighted_negative_viability_pressure"]
    )
    result["risk_score"] = float(risk_score)
    external = step_record.get("observed_external_input")
    if not isinstance(external, Mapping):
        raise BaselineError("step record missing observed_external_input")
    for name in EXTERNAL_FIELDS:
        result[name] = _finite(external[name], name)
    audit_feature_names(result, config)
    return result


def audit_feature_names(features: Mapping[str, Any] | Iterable[str], config: Mapping[str, Any]) -> None:
    names = list(features) if not isinstance(features, Mapping) else list(features.keys())
    forbidden = [str(token).lower() for token in config["forbidden_feature_tokens"]]
    leaked = sorted(
        name for name in names if any(token in str(name).lower() for token in forbidden)
    )
    if leaked:
        raise BaselineError(f"forbidden metadata/truth tokens in features: {leaked}")


def load_trajectory_series(entry: CorpusEntry, config: Mapping[str, Any]) -> TrajectorySeries:
    steps = _read_jsonl(entry.path / "steps.jsonl")
    if len(steps) != entry.total_steps + 1:
        raise BaselineError(f"{entry.trajectory_id} state count mismatch")
    features: list[dict[str, float]] = []
    for expected_step, record in enumerate(steps):
        if int(record["step"]) != expected_step:
            raise BaselineError(f"{entry.trajectory_id} contains non-contiguous steps")
        state_ref = Path(str(record["state_ref"]))
        if state_ref.is_absolute() or ".." in state_ref.parts:
            raise BaselineError("state_ref must remain inside trajectory directory")
        features.append(extract_current_features(entry.path / state_ref, record, config))
    if len({tuple(sorted(row)) for row in features}) != 1:
        raise BaselineError(f"{entry.trajectory_id} feature schema changes across time")
    return TrajectorySeries(entry=entry, features=features)


def attach_future_truth(
    series: Sequence[TrajectorySeries],
    config: Mapping[str, Any],
    calibration_config: Mapping[str, Any],
) -> None:
    reference_name = str(config["stable_reference_scenario"])
    references = {
        item.entry.seed: item
        for item in series
        if item.entry.scenario_id == reference_name
    }
    rules = calibration_config["rules"]
    for item in series:
        reference = references.get(item.entry.seed)
        if reference is None:
            raise BaselineError(f"missing same-seed stable reference for {item.entry.trajectory_id}")
        if len(item.features) != len(reference.features):
            raise BaselineError("target and same-seed reference lengths differ")
        risk = np.asarray([row["risk_score"] for row in item.features], dtype=np.float64)
        reference_risk = np.asarray(
            [row["risk_score"] for row in reference.features], dtype=np.float64
        )
        relative = risk - reference_risk
        elevated = relative >= float(rules["elevated_relative_risk_delta"])
        sustained = np.zeros_like(elevated, dtype=bool)
        run = 0
        for step, active in enumerate(elevated):
            run = run + 1 if bool(active) else 0
            if run >= int(rules["sustained_steps"]):
                sustained[step] = True
        concentration = np.asarray(
            [row["concentration"] for row in item.features], dtype=np.float64
        )
        reference_concentration = np.asarray(
            [row["concentration"] for row in reference.features], dtype=np.float64
        )
        mobility = np.asarray([row["moved_mass"] for row in item.features], dtype=np.float64)
        reference_mobility = np.asarray(
            [row["moved_mass"] for row in reference.features], dtype=np.float64
        )
        rigidity = np.asarray(
            [row["weighted_rigidity"] for row in item.features], dtype=np.float64
        )
        reference_rigidity = np.asarray(
            [row["weighted_rigidity"] for row in reference.features], dtype=np.float64
        )
        fixation = (
            concentration / np.maximum(reference_concentration, 1e-12)
            >= float(rules["fixation_concentration_ratio"])
        ) & (
            mobility / np.maximum(reference_mobility, 1e-12)
            <= float(rules["fixation_mobility_ratio"])
        ) & (
            rigidity - reference_rigidity >= float(rules["fixation_rigidity_delta"])
        )
        collapse = (
            risk >= float(rules["collapse_absolute_risk_score"])
        ) & (
            relative >= float(rules["collapse_relative_risk_delta"])
        )
        hazard = sustained | fixation | collapse
        kinds: list[str] = []
        for step in range(len(hazard)):
            if collapse[step]:
                kinds.append("collapse")
            elif fixation[step]:
                kinds.append("fixation")
            elif sustained[step]:
                kinds.append("elevated_risk")
            else:
                kinds.append("none")
        active_steps = np.flatnonzero(hazard)
        item.relative_risk = relative
        item.hazard_mask = hazard
        item.hazard_kind = kinds
        item.hazard_onset_step = int(active_steps[0]) if len(active_steps) else None


def _history_statistics(values: np.ndarray) -> dict[str, float]:
    if values.ndim != 1 or len(values) < 1:
        raise BaselineError("history values must be one-dimensional and non-empty")
    current = float(values[-1])
    previous = float(values[-2]) if len(values) >= 2 else current
    delta = current - previous
    mean = float(np.mean(values))
    slope = 0.0
    if len(values) >= 2:
        slope = float(np.polyfit(np.arange(len(values), dtype=np.float64), values, 1)[0])
    acceleration = (
        float(values[-1] - 2.0 * values[-2] + values[-3]) if len(values) >= 3 else 0.0
    )
    differences = np.diff(values)
    nonzero = np.sign(differences[np.abs(differences) > 1e-12])
    reversals = int(np.sum(nonzero[1:] != nonzero[:-1])) if len(nonzero) >= 2 else 0
    return {
        "delta_1": delta,
        "mean_gap": current - mean,
        "slope": slope,
        "acceleration": acceleration,
        "std": float(np.std(values)),
        "minimum": float(np.min(values)),
        "maximum": float(np.max(values)),
        "reversal_count": float(reversals),
    }


def feature_vector_at(
    item: TrajectorySeries,
    step: int,
    history_width: int,
    config: Mapping[str, Any],
) -> dict[str, float]:
    if step < history_width - 1:
        raise BaselineError("insufficient history for requested feature vector")
    vector = {f"current__{name}": float(value) for name, value in item.features[step].items()}
    start = step - history_width + 1
    for base_name in config["history_base_features"]:
        values = np.asarray(
            [item.features[index][base_name] for index in range(start, step + 1)],
            dtype=np.float64,
        )
        statistics = _history_statistics(values)
        for statistic in config["history_statistics"]:
            vector[f"history__{base_name}__{statistic}"] = float(statistics[statistic])
    audit_feature_names(vector, config)
    return vector


def build_window_dataset(
    series: Sequence[TrajectorySeries],
    history_width: int,
    horizon: int,
    config: Mapping[str, Any],
) -> WindowDataset:
    rows: list[dict[str, Any]] = []
    feature_names: list[str] | None = None
    for item in series:
        if item.relative_risk is None or item.hazard_mask is None:
            raise BaselineError("future truth must be attached before building windows")
        final_step = len(item.features) - 1
        for step in range(history_width - 1, final_step - horizon + 1):
            if item.hazard_onset_step is not None and step >= item.hazard_onset_step:
                continue
            future_slice = slice(step + 1, step + horizon + 1)
            future_hazard = item.hazard_mask[future_slice]
            future_relative = item.relative_risk[future_slice]
            event = bool(np.any(future_hazard))
            if event:
                future_indices = np.flatnonzero(future_hazard)
                next_hazard_step = step + 1 + int(future_indices[0])
            else:
                next_hazard_step = None
            recovery_difficulty = False
            if event and item.hazard_onset_step is not None:
                recovery_difficulty = bool(np.all(item.hazard_mask[item.hazard_onset_step :]))
            features = feature_vector_at(item, step, history_width, config)
            if feature_names is None:
                feature_names = sorted(features)
            elif sorted(features) != feature_names:
                raise BaselineError("window feature schema changed")
            rows.append(
                {
                    "trajectory_id": item.entry.trajectory_id,
                    "scenario_id": item.entry.scenario_id,
                    "seed": item.entry.seed,
                    "split": item.entry.split,
                    "step": step,
                    "history_width": history_width,
                    "horizon": horizon,
                    "actual_event": int(event),
                    "actual_depth": float(max(0.0, np.max(future_relative))),
                    "actual_hazard_duration": int(np.sum(future_hazard)),
                    "actual_recovery_difficulty": int(recovery_difficulty),
                    "hazard_onset_step": item.hazard_onset_step,
                    "next_hazard_step": next_hazard_step,
                    **features,
                }
            )
    if not rows or feature_names is None:
        raise BaselineError(f"no windows for W={history_width}, H={horizon}")
    frame = pd.DataFrame(rows)
    current = [name for name in feature_names if name.startswith("current__")]
    return WindowDataset(frame, feature_names, current, history_width, horizon)


def _constant_or_logistic(
    X: np.ndarray,
    y: np.ndarray,
    parameters: Mapping[str, Any],
) -> dict[str, Any]:
    classes = np.unique(y)
    if len(classes) < 2:
        return {"kind": "constant", "probability": float(np.mean(y))}
    scaler = StandardScaler().fit(X)
    transformed = scaler.transform(X)
    model = LogisticRegression(
        C=float(parameters["logistic_C"]),
        max_iter=int(parameters["logistic_max_iter"]),
        class_weight="balanced",
        random_state=int(parameters["random_state"]),
    ).fit(transformed, y)
    return {"kind": "logistic", "scaler": scaler, "model": model}


def _predict_probability(model: Mapping[str, Any], X: np.ndarray) -> np.ndarray:
    if model["kind"] == "constant":
        return np.full(len(X), float(model["probability"]), dtype=np.float64)
    return np.asarray(
        model["model"].predict_proba(model["scaler"].transform(X))[:, 1],
        dtype=np.float64,
    )


def _fit_ridge(X: np.ndarray, y: np.ndarray, parameters: Mapping[str, Any]) -> dict[str, Any]:
    if np.allclose(y, y[0]):
        return {"kind": "constant", "value": float(y[0])}
    scaler = StandardScaler().fit(X)
    model = Ridge(alpha=float(parameters["ridge_alpha"])).fit(scaler.transform(X), y)
    return {"kind": "ridge", "scaler": scaler, "model": model}


def _predict_ridge(model: Mapping[str, Any], X: np.ndarray) -> np.ndarray:
    if model["kind"] == "constant":
        return np.full(len(X), float(model["value"]), dtype=np.float64)
    return np.maximum(
        0.0,
        np.asarray(model["model"].predict(model["scaler"].transform(X)), dtype=np.float64),
    )


def _model_columns(dataset: WindowDataset, family: str) -> tuple[list[str], np.ndarray]:
    if family == "always_safe":
        return [], np.zeros((len(dataset.frame), 1), dtype=np.float64)
    if family == "current_risk_threshold":
        columns = ["current__risk_score"]
        return columns, dataset.frame[columns].to_numpy(dtype=np.float64)
    if family == "current_state_logistic":
        columns = list(dataset.current_feature_names)
        return columns, dataset.frame[columns].to_numpy(dtype=np.float64)
    if family == "trend_extrapolation":
        slope = dataset.frame["history__risk_score__slope"].to_numpy(dtype=np.float64)
        current = dataset.frame["current__risk_score"].to_numpy(dtype=np.float64)
        values = (current + slope * dataset.horizon).reshape(-1, 1)
        return ["trend_extrapolated_risk"], values
    if family == "history_logistic":
        columns = list(dataset.feature_names)
        return columns, dataset.frame[columns].to_numpy(dtype=np.float64)
    raise BaselineError(f"unsupported model family {family}")


def fit_model(dataset: WindowDataset, family: str, config: Mapping[str, Any]) -> dict[str, Any]:
    columns, X = _model_columns(dataset, family)
    if family == "always_safe":
        event = {"kind": "constant", "probability": 0.0}
        depth = {"kind": "constant", "value": 0.0}
    else:
        event = _constant_or_logistic(X, dataset.y_event, config["model_parameters"])
        depth = _fit_ridge(X, dataset.y_depth, config["model_parameters"])
    return {
        "family": family,
        "columns": columns,
        "event_model": event,
        "depth_model": depth,
    }


def predict_model(
    model: Mapping[str, Any], dataset: WindowDataset
) -> tuple[np.ndarray, np.ndarray]:
    _, X = _model_columns(dataset, str(model["family"]))
    return _predict_probability(model["event_model"], X), _predict_ridge(model["depth_model"], X)


def _apply_alarm(
    frame: pd.DataFrame,
    probability: np.ndarray,
    threshold: float,
    persistence: int,
) -> np.ndarray:
    result = np.zeros(len(frame), dtype=np.int64)
    working = frame[["trajectory_id", "step"]].copy()
    working["_position"] = np.arange(len(frame))
    working["_probability"] = probability
    for _, group in working.groupby("trajectory_id", sort=False):
        run = 0
        for row in group.sort_values("step").itertuples(index=False):
            run = run + 1 if float(row._probability) >= threshold else 0
            if run >= persistence:
                result[int(row._position)] = 1
    return result


def _safe_spearman(actual: Sequence[float], predicted: Sequence[float]) -> float:
    if len(actual) < 2 or np.allclose(actual, actual[0]) or np.allclose(predicted, predicted[0]):
        return 0.0
    value = spearmanr(actual, predicted).statistic
    return 0.0 if value is None or not math.isfinite(float(value)) else float(value)


def evaluate_predictions(
    dataset: WindowDataset,
    probability: np.ndarray,
    predicted_depth: np.ndarray,
    threshold: float,
    persistence: int,
    config: Mapping[str, Any],
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    if len(probability) != len(dataset.frame) or len(predicted_depth) != len(dataset.frame):
        raise BaselineError("prediction length mismatch")
    alarm = _apply_alarm(dataset.frame, probability, threshold, persistence)
    y = dataset.y_event
    negatives = int(np.sum(y == 0))
    false_positives = int(np.sum((alarm == 1) & (y == 0)))
    average_precision = float(average_precision_score(y, probability)) if np.any(y) else 0.0
    brier = float(brier_score_loss(y, probability))
    point_precision = float(precision_score(y, alarm, zero_division=0))
    point_recall = float(recall_score(y, alarm, zero_division=0))
    false_alarm_rate = float(false_positives / negatives) if negatives else 0.0
    depth_mae = float(np.mean(np.abs(dataset.y_depth - predicted_depth)))

    predictions = dataset.frame[
        [
            "trajectory_id",
            "scenario_id",
            "seed",
            "split",
            "step",
            "history_width",
            "horizon",
            "actual_event",
            "actual_depth",
            "actual_hazard_duration",
            "actual_recovery_difficulty",
            "hazard_onset_step",
            "next_hazard_step",
        ]
    ].copy()
    predictions["probability"] = probability
    predictions["predicted_depth"] = predicted_depth
    predictions["alarm"] = alarm

    trajectory_rows: list[dict[str, Any]] = []
    event_count = 0
    detected_count = 0
    lead_times: list[int] = []
    false_alarm_trajectories = 0
    for trajectory_id, group in predictions.groupby("trajectory_id", sort=False):
        ordered = group.sort_values("step")
        onset_values = ordered["hazard_onset_step"].dropna()
        onset = int(onset_values.iloc[0]) if len(onset_values) else None
        alarm_rows = ordered[ordered["alarm"] == 1]
        first_alarm = int(alarm_rows.iloc[0]["step"]) if len(alarm_rows) else None
        detected = False
        lead = None
        if onset is not None:
            event_count += 1
            if first_alarm is not None and first_alarm <= onset:
                detected = True
                detected_count += 1
                lead = onset - first_alarm
                lead_times.append(lead)
        elif first_alarm is not None:
            false_alarm_trajectories += 1
        trajectory_rows.append(
            {
                "trajectory_id": trajectory_id,
                "scenario_id": str(ordered.iloc[0]["scenario_id"]),
                "seed": int(ordered.iloc[0]["seed"]),
                "split": str(ordered.iloc[0]["split"]),
                "hazard_onset_step": onset,
                "first_alarm_step": first_alarm,
                "detected_before_or_at_onset": int(detected),
                "lead_time_steps": lead,
                "false_alarm_count": int(np.sum((ordered["alarm"] == 1) & (ordered["actual_event"] == 0))),
                "max_predicted_depth": float(ordered["predicted_depth"].max()),
                "max_actual_depth": float(ordered["actual_depth"].max()),
            }
        )
    trajectory_frame = pd.DataFrame(trajectory_rows)
    event_recall = float(detected_count / event_count) if event_count else 0.0
    median_lead = float(np.median(lead_times)) if lead_times else 0.0
    depth_rank = _safe_spearman(
        trajectory_frame["max_actual_depth"].to_numpy(dtype=np.float64),
        trajectory_frame["max_predicted_depth"].to_numpy(dtype=np.float64),
    )
    weights = config["selection_weights"]
    normalized_lead = min(1.0, median_lead / max(1, dataset.horizon))
    selection_score = (
        float(weights["event_recall"]) * event_recall
        + float(weights["average_precision"]) * average_precision
        + float(weights["normalized_lead_time"]) * normalized_lead
        + float(weights["depth_rank_correlation"]) * max(0.0, depth_rank)
        - float(weights["false_alarm_rate_penalty"]) * false_alarm_rate
        - float(weights["brier_penalty"]) * brier
    )
    metrics = {
        "window_count": len(dataset.frame),
        "positive_window_count": int(np.sum(y)),
        "negative_window_count": negatives,
        "average_precision": average_precision,
        "point_precision": point_precision,
        "point_recall": point_recall,
        "false_alarm_rate": false_alarm_rate,
        "brier_score": brier,
        "depth_mae": depth_mae,
        "depth_rank_correlation": depth_rank,
        "event_trajectory_count": event_count,
        "detected_event_trajectory_count": detected_count,
        "event_recall": event_recall,
        "median_lead_time_steps": median_lead,
        "minimum_lead_time_steps": min(lead_times) if lead_times else None,
        "maximum_lead_time_steps": max(lead_times) if lead_times else None,
        "false_alarm_trajectory_count": false_alarm_trajectories,
        "selection_score": float(selection_score),
        "alarm_threshold": float(threshold),
        "alarm_persistence": int(persistence),
    }
    return metrics, predictions, trajectory_frame


def tune_alarm(
    dataset: WindowDataset,
    probability: np.ndarray,
    predicted_depth: np.ndarray,
    config: Mapping[str, Any],
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    candidates: list[tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]] = []
    for threshold in config["alarm_probability_thresholds"]:
        for persistence in config["alarm_persistence_candidates"]:
            candidates.append(
                evaluate_predictions(
                    dataset,
                    probability,
                    predicted_depth,
                    float(threshold),
                    int(persistence),
                    config,
                )
            )
    candidates.sort(
        key=lambda item: (
            item[0]["selection_score"],
            item[0]["event_recall"],
            item[0]["median_lead_time_steps"],
            -item[0]["false_alarm_rate"],
            -item[0]["alarm_threshold"],
        ),
        reverse=True,
    )
    return candidates[0]


def candidate_id(family: str, history_width: int, horizon: int) -> str:
    if family in {"always_safe", "current_risk_threshold", "current_state_logistic"}:
        return f"{family}__H{horizon:02d}"
    return f"{family}__W{history_width:02d}__H{horizon:02d}"


def _dataset_for_candidate(
    datasets: Mapping[tuple[str, int, int], WindowDataset],
    split: str,
    family: str,
    history_width: int,
    horizon: int,
    maximum_history: int,
) -> WindowDataset:
    width = maximum_history if family in {
        "always_safe",
        "current_risk_threshold",
        "current_state_logistic",
    } else history_width
    return datasets[(split, width, horizon)]


def serialize_model(model: Mapping[str, Any]) -> dict[str, Any]:
    def serialize_estimator(estimator: Mapping[str, Any]) -> dict[str, Any]:
        kind = estimator["kind"]
        if kind == "constant":
            return {key: value for key, value in estimator.items() if key != "model"}
        scaler: StandardScaler = estimator["scaler"]
        fitted = estimator["model"]
        payload: dict[str, Any] = {
            "kind": kind,
            "scaler_mean": scaler.mean_.tolist(),
            "scaler_scale": scaler.scale_.tolist(),
            "intercept": np.asarray(fitted.intercept_).reshape(-1).tolist(),
            "coefficient": np.asarray(fitted.coef_).tolist(),
        }
        return payload

    return {
        "family": model["family"],
        "columns": list(model["columns"]),
        "event_model": serialize_estimator(model["event_model"]),
        "depth_model": serialize_estimator(model["depth_model"]),
    }


def create_selection_lock(
    path: str | Path,
    selected_id: str,
    selected_candidates: Mapping[str, Mapping[str, Any]],
    config: Mapping[str, Any],
    feature_schema_hash: str,
    corpus_hash: str,
    fit_seed_cv: Mapping[str, Any],
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "task_id": config["task_id"],
        "status": "locked_before_holdout_read",
        "selected_overall": selected_id,
        "locked_candidates": selected_candidates,
        "feature_schema_hash": feature_schema_hash,
        "config_hash": _canonical_hash(config),
        "corpus_manifest_hash": corpus_hash,
        "fit_seed_cross_check": fit_seed_cv,
        "final_training_splits": ["fit", "validation"],
        "holdout_seed_values": list(config["split_contract"]["holdout_seeds"]),
        "post_holdout_changes_forbidden": True,
    }
    payload["lock_hash"] = _canonical_hash(payload)
    _json_dump(path, payload)
    return payload


def validate_selection_lock(
    selection_lock_path: str | Path,
    selection_validation_path: str | Path,
) -> dict[str, Any]:
    lock = _json_load(selection_lock_path)
    validation = _json_load(selection_validation_path)
    claimed_hash = lock.get("lock_hash")
    body = dict(lock)
    body.pop("lock_hash", None)
    actual_hash = _canonical_hash(body)
    if claimed_hash != actual_hash:
        raise BaselineError("selection lock hash mismatch")
    if validation.get("valid") is not True or validation.get("lock_hash") != actual_hash:
        raise BaselineError("selection lock has not been independently validated")
    return lock


def write_selection_validation(path: str | Path, lock: Mapping[str, Any]) -> dict[str, Any]:
    body = dict(lock)
    claimed = body.pop("lock_hash", None)
    actual = _canonical_hash(body)
    validation = {
        "valid": bool(claimed == actual),
        "lock_hash": actual,
        "claimed_lock_hash": claimed,
        "holdout_not_read_before_validation": True,
    }
    _json_dump(path, validation)
    if validation["valid"] is not True:
        raise BaselineError("failed to validate selection lock")
    return validation


def _candidate_spec(
    family: str,
    history_width: int,
    horizon: int,
    metrics: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "candidate_id": candidate_id(family, history_width, horizon),
        "family": family,
        "history_width": history_width,
        "horizon": horizon,
        "alarm_threshold": metrics["alarm_threshold"],
        "alarm_persistence": metrics["alarm_persistence"],
        "validation_metrics": dict(metrics),
    }


def _fit_seed_cross_check(
    selected: Mapping[str, Any],
    fit_series: Sequence[TrajectorySeries],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    width = int(selected["history_width"])
    horizon = int(selected["horizon"])
    family = str(selected["family"])
    maximum_history = max(int(value) for value in config["history_widths"])
    if family in {"always_safe", "current_risk_threshold", "current_state_logistic"}:
        width = maximum_history
    rows: list[dict[str, Any]] = []
    fit_seeds = sorted({item.entry.seed for item in fit_series})
    for held_seed in fit_seeds:
        training_series = [item for item in fit_series if item.entry.seed != held_seed]
        checking_series = [item for item in fit_series if item.entry.seed == held_seed]
        train = build_window_dataset(training_series, width, horizon, config)
        check = build_window_dataset(checking_series, width, horizon, config)
        model = fit_model(train, family, config)
        probability, depth = predict_model(model, check)
        metrics, _, _ = evaluate_predictions(
            check,
            probability,
            depth,
            float(selected["alarm_threshold"]),
            int(selected["alarm_persistence"]),
            config,
        )
        rows.append({"held_out_fit_seed": held_seed, **metrics})
    return {
        "folds": rows,
        "mean_average_precision": float(np.mean([row["average_precision"] for row in rows])),
        "mean_event_recall": float(np.mean([row["event_recall"] for row in rows])),
        "mean_depth_rank_correlation": float(
            np.mean([row["depth_rank_correlation"] for row in rows])
        ),
    }


def _bar_svg(path: Path, title: str, labels: Sequence[str], values: Sequence[float]) -> None:
    width = 1000
    row_height = 30
    height = 70 + row_height * len(labels)
    maximum = max([abs(float(value)) for value in values] + [1e-12])
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="20" y="30" font-family="sans-serif" font-size="18">{title}</text>',
    ]
    for index, (label, value) in enumerate(zip(labels, values, strict=True)):
        y = 55 + index * row_height
        bar = 500.0 * max(0.0, float(value)) / maximum
        lines.append(f'<text x="20" y="{y + 16}" font-family="sans-serif" font-size="12">{label}</text>')
        lines.append(f'<rect x="400" y="{y}" width="{bar:.2f}" height="18" fill="#777"/>')
        lines.append(f'<text x="920" y="{y + 16}" font-family="monospace" font-size="12">{float(value):.5g}</text>')
    lines.append("</svg>\n")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _scatter_svg(path: Path, title: str, actual: Sequence[float], predicted: Sequence[float]) -> None:
    width, height = 760, 620
    margin = 70
    maximum = max([float(value) for value in actual] + [float(value) for value in predicted] + [1e-12])
    points = []
    for x_value, y_value in zip(actual, predicted, strict=True):
        x = margin + (width - 2 * margin) * float(x_value) / maximum
        y = height - margin - (height - 2 * margin) * float(y_value) / maximum
        points.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="5" fill="#333"/>')
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="20" y="30" font-family="sans-serif" font-size="18">{title}</text>',
        f'<line x1="{margin}" y1="{height-margin}" x2="{width-margin}" y2="{height-margin}" stroke="#777"/>',
        f'<line x1="{margin}" y1="{height-margin}" x2="{margin}" y2="{margin}" stroke="#777"/>',
        f'<line x1="{margin}" y1="{height-margin}" x2="{width-margin}" y2="{margin}" stroke="#aaa" stroke-dasharray="4 4"/>',
        *points,
        '</svg>\n',
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def _precision_recall_svg(path: Path, y: np.ndarray, probability: np.ndarray) -> None:
    precision, recall, _ = precision_recall_curve(y, probability)
    width, height, margin = 760, 620, 70
    points = " ".join(
        f"{margin + (width - 2 * margin) * float(r):.2f},{height - margin - (height - 2 * margin) * float(p):.2f}"
        for p, r in zip(precision, recall, strict=True)
    )
    path.write_text(
        "\n".join(
            [
                f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
                '<rect width="100%" height="100%" fill="white"/>',
                '<text x="20" y="30" font-family="sans-serif" font-size="18">Holdout precision-recall</text>',
                f'<line x1="{margin}" y1="{height-margin}" x2="{width-margin}" y2="{height-margin}" stroke="#777"/>',
                f'<line x1="{margin}" y1="{height-margin}" x2="{margin}" y2="{margin}" stroke="#777"/>',
                f'<polyline points="{points}" fill="none" stroke="#222" stroke-width="2"/>',
                '</svg>\n',
            ]
        ),
        encoding="utf-8",
    )


def _warning_timeline_svg(path: Path, rows: pd.DataFrame, title: str) -> None:
    ordered = rows.sort_values("step")
    width, height, margin = 1000, 280, 60
    steps = ordered["step"].to_numpy(dtype=np.float64)
    probabilities = ordered["probability"].to_numpy(dtype=np.float64)
    if len(steps) < 2:
        return
    minimum, maximum = float(steps.min()), float(steps.max())
    span = max(1.0, maximum - minimum)
    points = " ".join(
        f"{margin + (width - 2*margin) * (step-minimum)/span:.2f},{height-margin-(height-2*margin)*probability:.2f}"
        for step, probability in zip(steps, probabilities, strict=True)
    )
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="20" y="28" font-family="sans-serif" font-size="16">{title}</text>',
        f'<polyline points="{points}" fill="none" stroke="#222" stroke-width="2"/>',
    ]
    for row in ordered.itertuples(index=False):
        if int(row.alarm) == 1:
            x = margin + (width - 2 * margin) * (float(row.step) - minimum) / span
            lines.append(f'<line x1="{x:.2f}" y1="{margin}" x2="{x:.2f}" y2="{height-margin}" stroke="#777"/>')
    onset_values = ordered["hazard_onset_step"].dropna()
    if len(onset_values):
        onset = float(onset_values.iloc[0])
        x = margin + (width - 2 * margin) * (onset - minimum) / span
        lines.append(f'<line x1="{x:.2f}" y1="{margin}" x2="{x:.2f}" y2="{height-margin}" stroke="#000" stroke-width="3"/>')
    lines.append("</svg>\n")
    path.write_text("\n".join(lines), encoding="utf-8")


def _write_manifest(output_dir: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for path in sorted(output_dir.rglob("*")):
        if not path.is_file() or path.name == "manifest.json":
            continue
        files.append(
            {
                "path": path.relative_to(output_dir).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": _file_sha256(path),
            }
        )
    manifest = {
        "file_count": len(files),
        "total_size_bytes": sum(item["size_bytes"] for item in files),
        "files": files,
    }
    _json_dump(output_dir / "manifest.json", manifest)
    return manifest


def _research_judgement(
    current_validation: Mapping[str, Any],
    history_validation: Mapping[str, Any],
    current_holdout: Mapping[str, Any],
    history_holdout: Mapping[str, Any],
    config: Mapping[str, Any],
) -> dict[str, Any]:
    criteria = config["success_criteria"]
    validation_dimensions = {
        "event_recall_improved": history_validation["event_recall"] > current_validation["event_recall"],
        "lead_time_target": history_validation["median_lead_time_steps"] >= float(criteria["lead_time_median_steps"]),
        "average_precision_improved": (
            history_validation["average_precision"] - current_validation["average_precision"]
            >= float(criteria["average_precision_improvement"])
        ),
        "depth_rank_target": history_validation["depth_rank_correlation"] >= float(criteria["depth_rank_correlation"]),
    }
    holdout_direction = {
        "event_recall_non_decreasing": history_holdout["event_recall"] >= current_holdout["event_recall"],
        "average_precision_non_decreasing": history_holdout["average_precision"] >= current_holdout["average_precision"],
        "depth_rank_non_decreasing": history_holdout["depth_rank_correlation"] >= current_holdout["depth_rank_correlation"],
    }
    improved = sum(bool(value) for value in validation_dimensions.values())
    maintained = sum(bool(value) for value in holdout_direction.values())
    if improved >= int(criteria["minimum_improved_dimensions_for_A"]) and maintained >= 2:
        grade = "A_promising"
    elif improved >= 1 or maintained >= 1:
        grade = "B_partially_promising"
    else:
        grade = "C_not_promising_at_current_resolution"
    return {
        "grade": grade,
        "validation_dimensions": validation_dimensions,
        "holdout_direction": holdout_direction,
        "improved_validation_dimension_count": improved,
        "maintained_holdout_direction_count": maintained,
        "boundary": "This judges simple history baselines only; it does not judge macro-dynamics extraction.",
    }


def _candidate_sort_key(item: Mapping[str, Any]) -> tuple[float, float, float, float]:
    metrics = item["validation_metrics"]
    return (
        float(metrics["selection_score"]),
        float(metrics["event_recall"]),
        float(metrics["median_lead_time_steps"]),
        -float(metrics["false_alarm_rate"]),
    )


def run_baselines(
    input_dir: str | Path,
    output_dir: str | Path,
    config_path: str | Path = DEFAULT_CONFIG,
) -> dict[str, Any]:
    config = load_config(config_path)
    generation_config = _json_load(ROOT / config["generation_config_path"])
    calibration_config = _json_load(ROOT / config["calibration_config_path"])
    output = Path(output_dir)
    if output.exists():
        import shutil
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    index = CorpusIndex(input_dir, config)
    _json_dump(output / config["outputs"]["split_manifest"], index.split_manifest())

    fit_entries = index.entries_for("fit")
    validation_entries = index.entries_for("validation")
    fit_series = [load_trajectory_series(entry, config) for entry in fit_entries]
    validation_series = [load_trajectory_series(entry, config) for entry in validation_entries]
    attach_future_truth(fit_series, config, calibration_config)
    attach_future_truth(validation_series, config, calibration_config)

    datasets: dict[tuple[str, int, int], WindowDataset] = {}
    for split, split_series in (("fit", fit_series), ("validation", validation_series)):
        for width in config["history_widths"]:
            for horizon in config["prediction_horizons"]:
                datasets[(split, int(width), int(horizon))] = build_window_dataset(
                    split_series, int(width), int(horizon), config
                )
    maximum_history = max(int(value) for value in config["history_widths"])
    schema_dataset = datasets[("fit", maximum_history, int(config["prediction_horizons"][0]))]
    feature_schema = {
        "current_features": schema_dataset.current_feature_names,
        "history_features": [
            name for name in schema_dataset.feature_names if name.startswith("history__")
        ],
        "all_features": schema_dataset.feature_names,
        "feature_count": len(schema_dataset.feature_names),
        "forbidden_feature_audit": "passed",
        "model_input_boundary": "X_t + L_t only",
    }
    feature_schema_hash = _canonical_hash(feature_schema)
    feature_schema["schema_hash"] = feature_schema_hash
    _json_dump(output / config["outputs"]["feature_schema"], feature_schema)
    label_schema = {
        "actual_event": "hazard begins within the future horizon",
        "actual_depth": "maximum non-negative relative risk in the future horizon",
        "actual_hazard_duration": "number of future hazard steps inside the horizon",
        "actual_recovery_difficulty": "hazard remains active through trajectory end",
        "truth_reference": "same-seed stable_continuation, truth side only",
        "irreversibility_claim": False,
        "scenario_id_used_as_truth": False,
    }
    _json_dump(output / config["outputs"]["label_schema"], label_schema)

    window_manifest_rows: list[dict[str, Any]] = []
    for (split, width, horizon), dataset in datasets.items():
        for row in dataset.frame.itertuples(index=False):
            window_manifest_rows.append(
                {
                    "trajectory_id": row.trajectory_id,
                    "split": split,
                    "step": row.step,
                    "history_width": width,
                    "horizon": horizon,
                    "actual_event": row.actual_event,
                    "actual_depth": row.actual_depth,
                }
            )
    _write_csv(
        output / config["outputs"]["window_manifest"],
        window_manifest_rows,
        ["trajectory_id", "split", "step", "history_width", "horizon", "actual_event", "actual_depth"],
    )

    candidate_rows: list[dict[str, Any]] = []
    candidate_specs: dict[str, dict[str, Any]] = {}
    validation_prediction_rows: list[dict[str, Any]] = []
    fit_metrics_rows: list[dict[str, Any]] = []
    for horizon in config["prediction_horizons"]:
        for family in config["model_families"]:
            widths = (
                [maximum_history]
                if family in {"always_safe", "current_risk_threshold", "current_state_logistic"}
                else list(config["history_widths"])
            )
            for width in widths:
                train = _dataset_for_candidate(
                    datasets, "fit", family, int(width), int(horizon), maximum_history
                )
                validation = _dataset_for_candidate(
                    datasets, "validation", family, int(width), int(horizon), maximum_history
                )
                model = fit_model(train, family, config)
                fit_probability, fit_depth = predict_model(model, train)
                fit_metrics, _, _ = evaluate_predictions(
                    train,
                    fit_probability,
                    fit_depth,
                    0.5,
                    1,
                    config,
                )
                probability, depth = predict_model(model, validation)
                validation_metrics, predictions, _ = tune_alarm(
                    validation, probability, depth, config
                )
                cid = candidate_id(family, int(width), int(horizon))
                spec = _candidate_spec(family, int(width), int(horizon), validation_metrics)
                candidate_specs[cid] = spec
                candidate_rows.append(
                    {
                        "candidate_id": cid,
                        "family": family,
                        "history_width": int(width),
                        "horizon": int(horizon),
                        **validation_metrics,
                    }
                )
                fit_metrics_rows.append(
                    {
                        "candidate_id": cid,
                        "family": family,
                        "history_width": int(width),
                        "horizon": int(horizon),
                        **fit_metrics,
                    }
                )
                predictions = predictions.copy()
                predictions.insert(0, "candidate_id", cid)
                validation_prediction_rows.extend(predictions.to_dict(orient="records"))

    ranked = sorted(candidate_specs.values(), key=_candidate_sort_key, reverse=True)
    selected = ranked[0]
    best_current = sorted(
        [item for item in ranked if item["family"] in CURRENT_MODEL_FAMILIES],
        key=_candidate_sort_key,
        reverse=True,
    )[0]
    best_history = sorted(
        [item for item in ranked if item["family"] in HISTORY_MODEL_FAMILIES],
        key=_candidate_sort_key,
        reverse=True,
    )[0]
    fit_seed_cv = _fit_seed_cross_check(selected, fit_series, config)
    corpus_manifest_path = Path(input_dir) / "manifest.json"
    corpus_hash = _file_sha256(corpus_manifest_path) if corpus_manifest_path.is_file() else _canonical_hash(index.split_manifest())
    locked_candidates = {
        "selected_overall": selected,
        "best_current": best_current,
        "best_history": best_history,
    }
    lock_path = output / config["outputs"]["selection_lock"]
    validation_path = output / config["outputs"]["selection_lock_validation"]
    lock = create_selection_lock(
        lock_path,
        str(selected["candidate_id"]),
        locked_candidates,
        config,
        feature_schema_hash,
        corpus_hash,
        fit_seed_cv,
    )
    write_selection_validation(validation_path, lock)

    _json_dump(output / config["outputs"]["fit_metrics"], {"candidates": fit_metrics_rows, "selected_fit_seed_cross_check": fit_seed_cv})
    _json_dump(output / config["outputs"]["validation_metrics"], {"selected": selected, "best_current": best_current, "best_history": best_history})
    _write_csv(
        output / config["outputs"]["candidate_comparison"],
        candidate_rows,
        list(candidate_rows[0].keys()),
    )
    _write_csv(
        output / config["outputs"]["validation_predictions"],
        validation_prediction_rows,
        list(validation_prediction_rows[0].keys()),
    )

    holdout_entries = index.entries_for(
        "holdout",
        selection_lock_path=lock_path,
        selection_validation_path=validation_path,
    )
    holdout_series = [load_trajectory_series(entry, config) for entry in holdout_entries]
    attach_future_truth(holdout_series, config, calibration_config)
    final_training_series = fit_series + validation_series

    holdout_metrics_by_role: dict[str, dict[str, Any]] = {}
    holdout_prediction_rows: list[dict[str, Any]] = []
    trajectory_summary_rows: list[dict[str, Any]] = []
    selected_serialized_model: dict[str, Any] | None = None
    for role, spec in locked_candidates.items():
        family = str(spec["family"])
        width = int(spec["history_width"])
        if family in {"always_safe", "current_risk_threshold", "current_state_logistic"}:
            width = maximum_history
        horizon = int(spec["horizon"])
        train = build_window_dataset(final_training_series, width, horizon, config)
        holdout = build_window_dataset(holdout_series, width, horizon, config)
        model = fit_model(train, family, config)
        probability, depth = predict_model(model, holdout)
        metrics, predictions, trajectory_frame = evaluate_predictions(
            holdout,
            probability,
            depth,
            float(spec["alarm_threshold"]),
            int(spec["alarm_persistence"]),
            config,
        )
        holdout_metrics_by_role[role] = {
            "candidate": spec,
            "metrics": metrics,
        }
        predictions = predictions.copy()
        predictions.insert(0, "role", role)
        predictions.insert(1, "candidate_id", spec["candidate_id"])
        holdout_prediction_rows.extend(predictions.to_dict(orient="records"))
        trajectory_frame = trajectory_frame.copy()
        trajectory_frame.insert(0, "role", role)
        trajectory_frame.insert(1, "candidate_id", spec["candidate_id"])
        trajectory_summary_rows.extend(trajectory_frame.to_dict(orient="records"))
        if role == "selected_overall":
            selected_serialized_model = {
                "candidate": spec,
                "model": serialize_model(model),
                "selection_lock_hash": lock["lock_hash"],
            }
            _precision_recall_svg(
                output / "precision_recall_curve.svg", holdout.y_event, probability
            )
            _scatter_svg(
                output / "risk_depth_prediction.svg",
                "Holdout risk-depth prediction",
                holdout.y_depth,
                depth,
            )
            selected_trajectory = trajectory_frame
            _bar_svg(
                output / "lead_time_by_trajectory.svg",
                "Holdout lead time by trajectory",
                selected_trajectory["trajectory_id"].astype(str).tolist(),
                selected_trajectory["lead_time_steps"].fillna(0.0).astype(float).tolist(),
            )
            _bar_svg(
                output / "false_alarm_by_trajectory.svg",
                "Holdout false alarms by trajectory",
                selected_trajectory["trajectory_id"].astype(str).tolist(),
                selected_trajectory["false_alarm_count"].astype(float).tolist(),
            )
            for trajectory_id, group in predictions.groupby("trajectory_id", sort=False):
                _warning_timeline_svg(
                    output / f"warning_timeline_{trajectory_id}.svg",
                    group,
                    f"{trajectory_id} warning timeline",
                )

    if selected_serialized_model is None:
        raise BaselineError("selected model was not serialized")
    _json_dump(output / config["outputs"]["selected_model"], selected_serialized_model)
    _json_dump(output / config["outputs"]["holdout_metrics"], holdout_metrics_by_role)
    _write_csv(
        output / config["outputs"]["holdout_predictions"],
        holdout_prediction_rows,
        list(holdout_prediction_rows[0].keys()),
    )
    _write_csv(
        output / config["outputs"]["trajectory_warning_summary"],
        trajectory_summary_rows,
        list(trajectory_summary_rows[0].keys()),
    )

    judgement = _research_judgement(
        best_current["validation_metrics"],
        best_history["validation_metrics"],
        holdout_metrics_by_role["best_current"]["metrics"],
        holdout_metrics_by_role["best_history"]["metrics"],
        config,
    )
    selected_holdout = holdout_metrics_by_role["selected_overall"]["metrics"]
    results_text = f"""# Task 3.2-3 実行結果

## 選択された単純基準

- candidate: `{selected['candidate_id']}`
- family: `{selected['family']}`
- history width: `{selected['history_width']}`
- prediction horizon: `{selected['horizon']}`
- alarm threshold: `{selected['alarm_threshold']}`
- alarm persistence: `{selected['alarm_persistence']}`

## Validation

- event recall: {selected['validation_metrics']['event_recall']:.6f}
- median lead time: {selected['validation_metrics']['median_lead_time_steps']:.6f}
- average precision: {selected['validation_metrics']['average_precision']:.6f}
- false alarm rate: {selected['validation_metrics']['false_alarm_rate']:.6f}
- depth rank correlation: {selected['validation_metrics']['depth_rank_correlation']:.6f}

## Holdout

- event recall: {selected_holdout['event_recall']:.6f}
- median lead time: {selected_holdout['median_lead_time_steps']:.6f}
- average precision: {selected_holdout['average_precision']:.6f}
- false alarm rate: {selected_holdout['false_alarm_rate']:.6f}
- depth rank correlation: {selected_holdout['depth_rank_correlation']:.6f}

## 履歴の有望性判定

- grade: `{judgement['grade']}`
- improved validation dimensions: {judgement['improved_validation_dimension_count']}
- maintained holdout directions: {judgement['maintained_holdout_direction_count']}

## 境界

この結果は単純な現在状態・履歴基準の評価であり、動的関係場、マクロ力学、不可逆性、ゲーム構造を確定するものではない。
"""
    (output / config["outputs"]["results_markdown"]).write_text(results_text, encoding="utf-8")
    completion_text = f"""# Task 3.2-3 完了記録

Task 3.2-3は完了した。

- 5種類の単純基準を比較
- fit seed内交差確認を実施
- validationで候補を選択
- selection lockをholdout読込前に作成・検証
- holdoutはlock後にのみ読込
- 高リスク検出、先行時間、誤警報、リスク深度順位を保存
- 最良単純基準: `{selected['candidate_id']}`
- 履歴有望性判定: `{judgement['grade']}`

Task 4はこの選択済み基準を比較対象として使用する。
"""
    (output / config["outputs"]["completion_markdown"]).write_text(completion_text, encoding="utf-8")
    handoff_text = f"""# Task 3.2-3 → Task 3.2-4 引き渡し

## Task 4が超えるべき基準

`{selected['candidate_id']}`

Task 4では、少なくとも次のいずれかを改善すること。

1. 警報先行時間
2. 同じ先行時間での誤警報
3. リスク深度順位
4. 固定化候補と崩壊候補の区別
5. seed間安定性

## 固定境界

- 予測入力はX_t + L_t
- scenario ID、seed、split、未来情報は入力禁止
- holdout後のTask 3基準変更は禁止
- Task 3のselection lock hash: `{lock['lock_hash']}`
- Task 3はマクロ力学要素を固定していない
"""
    (output / config["outputs"]["handoff_markdown"]).write_text(handoff_text, encoding="utf-8")
    summary = {
        "task_id": config["task_id"],
        "selected_candidate": selected,
        "best_current": best_current,
        "best_history": best_history,
        "holdout": holdout_metrics_by_role,
        "research_judgement": judgement,
        "selection_lock_hash": lock["lock_hash"],
        "holdout_read_gate": "passed",
        "future_feature_leakage_audit": "passed",
        "status": "complete",
    }
    _json_dump(output / "summary.json", summary)
    manifest = _write_manifest(output)
    return {**summary, "manifest_file_count": manifest["file_count"]}


def validate_output(output_dir: str | Path, config_path: str | Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = load_config(config_path)
    root = Path(output_dir)
    required = set(config["outputs"].values()) | {
        "summary.json",
        "precision_recall_curve.svg",
        "lead_time_by_trajectory.svg",
        "false_alarm_by_trajectory.svg",
        "risk_depth_prediction.svg",
    }
    missing = sorted(name for name in required if not (root / name).is_file())
    if missing:
        raise BaselineError(f"output missing required files: {missing}")
    lock = validate_selection_lock(
        root / config["outputs"]["selection_lock"],
        root / config["outputs"]["selection_lock_validation"],
    )
    feature_schema = _json_load(root / config["outputs"]["feature_schema"])
    audit_feature_names(feature_schema["all_features"], config)
    summary = _json_load(root / "summary.json")
    if summary.get("status") != "complete":
        raise BaselineError("summary is not complete")
    if summary.get("selection_lock_hash") != lock["lock_hash"]:
        raise BaselineError("summary and selection lock hashes differ")
    holdout = _json_load(root / config["outputs"]["holdout_metrics"])
    if set(holdout) != {"selected_overall", "best_current", "best_history"}:
        raise BaselineError("holdout must contain the three locked comparison roles")
    return {
        "status": "valid",
        "selection_lock_hash": lock["lock_hash"],
        "selected_candidate": summary["selected_candidate"]["candidate_id"],
        "holdout_gate": "passed",
        "feature_leakage_audit": "passed",
        "required_file_count": len(required),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    run = subparsers.add_parser("run")
    run.add_argument("--input", required=True)
    run.add_argument("--output", required=True)
    run.add_argument("--config", default=str(DEFAULT_CONFIG))
    validate = subparsers.add_parser("validate")
    validate.add_argument("--input", required=True)
    validate.add_argument("--config", default=str(DEFAULT_CONFIG))
    args = parser.parse_args(argv)
    result = (
        run_baselines(args.input, args.output, args.config)
        if args.command == "run"
        else validate_output(args.input, args.config)
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "BaselineError",
    "CorpusIndex",
    "TrajectorySeries",
    "WindowDataset",
    "attach_future_truth",
    "audit_feature_names",
    "build_window_dataset",
    "candidate_id",
    "create_selection_lock",
    "evaluate_predictions",
    "extract_current_features",
    "feature_vector_at",
    "fit_model",
    "load_config",
    "load_trajectory_series",
    "predict_model",
    "run_baselines",
    "tune_alarm",
    "validate_config",
    "validate_output",
    "validate_selection_lock",
    "write_selection_validation",
]
