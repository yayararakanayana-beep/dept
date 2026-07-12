"""Lightweight prediction validation for Task 3.2-4.1 Rev1."""
from __future__ import annotations

import math
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.metrics import average_precision_score, balanced_accuracy_score, recall_score
from sklearn.preprocessing import StandardScaler

from task3_2_4_1_rev1_common import Rev1Error


def audit_feature_names(names: Iterable[str], config: Mapping[str, Any]) -> None:
    forbidden = [str(token).lower() for token in config["forbidden_feature_tokens"]]
    leaked = sorted(name for name in names if any(token in str(name).lower() for token in forbidden))
    if leaked:
        raise Rev1Error(f"future/metadata tokens leaked into Rev1 features: {leaked}")


def feature_names(family: str, task3_names: Sequence[str], macro_names: Sequence[str]) -> list[str]:
    if family == "current_risk":
        return ["current_risk", "current_value"]
    if family == "task3":
        return list(task3_names)
    if family == "task4":
        return list(macro_names)
    if family == "task3_plus_task4":
        return list(task3_names) + list(macro_names)
    raise Rev1Error(f"unknown prediction family {family}")


def fit_predictor(frame: pd.DataFrame, features: Sequence[str], config: Mapping[str, Any]) -> dict[str, Any]:
    audit_feature_names([name for name in features if name not in {"current_risk", "current_value"}], config)
    X = frame[list(features)].to_numpy(dtype=np.float64)
    scaler = StandardScaler().fit(X)
    transformed = scaler.transform(X)
    models: dict[str, Any] = {}
    for target in config["prediction"]["binary_targets"]:
        y = frame[target].to_numpy(dtype=int)
        if len(np.unique(y)) < 2:
            models[target] = {"kind": "constant_probability", "value": float(np.mean(y))}
        else:
            models[target] = LogisticRegression(
                C=float(config["prediction"]["logistic_C"]),
                max_iter=3000,
                class_weight="balanced",
                random_state=int(config["prediction"]["random_state"]),
            ).fit(transformed, y)
    for target in config["prediction"]["continuous_targets"]:
        valid = frame[target].notna().to_numpy()
        y = frame.loc[valid, target].to_numpy(dtype=np.float64)
        if len(y) == 0:
            models[target] = {"kind": "missing"}
        elif len(y) < 2 or np.allclose(y, y[0]):
            models[target] = {"kind": "constant", "value": float(y[0])}
        else:
            models[target] = Ridge(alpha=float(config["prediction"]["ridge_alpha"])).fit(transformed[valid], y)
    return {"features": list(features), "scaler": scaler, "models": models}


def predict(model: Mapping[str, Any], frame: pd.DataFrame, config: Mapping[str, Any]) -> pd.DataFrame:
    X = frame[list(model["features"])].to_numpy(dtype=np.float64)
    transformed = model["scaler"].transform(X)
    output = frame[["trajectory_id", "scenario_id", "seed", "split", "snapshot_step"]].copy()
    for target in config["prediction"]["binary_targets"]:
        fitted = model["models"][target]
        if isinstance(fitted, dict):
            values = np.full(len(frame), float(fitted["value"]), dtype=np.float64)
        else:
            values = fitted.predict_proba(transformed)[:, 1]
        output[f"actual__{target}"] = frame[target].to_numpy(dtype=float)
        output[f"predicted__{target}"] = values
    for target in config["prediction"]["continuous_targets"]:
        fitted = model["models"][target]
        if isinstance(fitted, dict) and fitted.get("kind") == "missing":
            values = np.full(len(frame), np.nan, dtype=np.float64)
        elif isinstance(fitted, dict):
            values = np.full(len(frame), float(fitted["value"]), dtype=np.float64)
        else:
            values = np.asarray(fitted.predict(transformed), dtype=np.float64)
        if "escape_cost" in target or "safe_reachable_range" in target:
            values = np.maximum(values, 0.0)
        if "last_action_window" in target:
            values = np.clip(values, -1.0, 8.0)
        output[f"actual__{target}"] = frame[target].to_numpy(dtype=float)
        output[f"predicted__{target}"] = values
    return output


def safe_spearman(actual: Sequence[float], predicted: Sequence[float]) -> float:
    a = np.asarray(actual, dtype=np.float64)
    p = np.asarray(predicted, dtype=np.float64)
    valid = np.isfinite(a) & np.isfinite(p)
    a, p = a[valid], p[valid]
    if len(a) < 2 or np.allclose(a, a[0]) or np.allclose(p, p[0]):
        return 0.0
    value = spearmanr(a, p).statistic
    return 0.0 if value is None or not math.isfinite(float(value)) else float(value)


def evaluate_predictions(predictions: pd.DataFrame, config: Mapping[str, Any]) -> dict[str, Any]:
    metrics: dict[str, Any] = {"row_count": len(predictions), "binary": {}, "continuous": {}}
    aps: list[float] = []
    ranks: list[float] = []
    maes: list[float] = []
    for target in config["prediction"]["binary_targets"]:
        actual = predictions[f"actual__{target}"].to_numpy(dtype=int)
        probability = predictions[f"predicted__{target}"].to_numpy(dtype=float)
        if int(actual.sum()) == 0:
            ap = 0.0
        elif int(actual.sum()) == len(actual):
            ap = 1.0
        else:
            ap = float(average_precision_score(actual, probability))
        classes = (probability >= 0.5).astype(int)
        balanced = (
            float(balanced_accuracy_score(actual, classes))
            if len(np.unique(actual)) > 1 else float(np.mean(classes == actual))
        )
        recall = float(recall_score(actual, classes, zero_division=0))
        metrics["binary"][target] = {
            "positive_count": int(actual.sum()), "average_precision": ap,
            "balanced_accuracy": balanced, "recall": recall,
        }
        if 0 < int(actual.sum()) < len(actual):
            aps.append(ap)
    for target in config["prediction"]["continuous_targets"]:
        actual = predictions[f"actual__{target}"].to_numpy(dtype=float)
        predicted = predictions[f"predicted__{target}"].to_numpy(dtype=float)
        valid = np.isfinite(actual) & np.isfinite(predicted)
        if not np.any(valid):
            result = {"row_count": 0, "mae": None, "rank_correlation": None}
        else:
            mae = float(np.mean(np.abs(actual[valid] - predicted[valid])))
            rank = safe_spearman(actual[valid], predicted[valid])
            result = {"row_count": int(valid.sum()), "mae": mae, "rank_correlation": rank}
            maes.append(mae)
            ranks.append(rank)
        metrics["continuous"][target] = result
    metrics["mean_variable_binary_ap"] = float(np.mean(aps)) if aps else 0.0
    metrics["mean_continuous_rank"] = float(np.mean(ranks)) if ranks else 0.0
    metrics["mean_continuous_mae"] = float(np.mean(maes)) if maes else float("inf")
    return metrics


def selection_key(row: Mapping[str, Any], primary: str) -> tuple[Any, ...]:
    primary_metrics = row["metrics"]["binary"][primary]
    return (
        float(primary_metrics["average_precision"]),
        float(row["metrics"]["mean_variable_binary_ap"]),
        float(row["metrics"]["binary"]["c3_escape_observed"]["average_precision"]),
        float(row["metrics"]["mean_continuous_rank"]),
        -float(row["metrics"]["mean_continuous_mae"]),
        -int(row["feature_count"]),
    )


def time_confounding_audit(truth: pd.DataFrame, selected_predictions: pd.DataFrame) -> dict[str, Any]:
    target = "dangerous_shrinking"
    actual = truth[target].to_numpy(dtype=int)
    step_rule = (truth["snapshot_step"].to_numpy(dtype=int) >= 28).astype(int)
    if 0 < int(actual.sum()) < len(actual):
        step_ap = float(average_precision_score(actual, step_rule.astype(float)))
    else:
        step_ap = float(np.mean(step_rule == actual))
    result: dict[str, Any] = {
        "step_ge_28": {
            "accuracy": float(np.mean(step_rule == actual)),
            "average_precision": step_ap,
            "positive_count": int(actual.sum()),
        },
        "by_snapshot_step": {},
    }
    for step, group in selected_predictions.groupby("snapshot_step", sort=True):
        a = group[f"actual__{target}"].to_numpy(dtype=int)
        p = group[f"predicted__{target}"].to_numpy(dtype=float)
        if int(a.sum()) == 0:
            ap = 0.0
        elif int(a.sum()) == len(a):
            ap = 1.0
        else:
            ap = float(average_precision_score(a, p))
        result["by_snapshot_step"][str(int(step))] = {
            "row_count": len(group), "positive_count": int(a.sum()), "average_precision": ap,
        }
    return result
