from __future__ import annotations

import hashlib
import math
from typing import Any, Mapping, Sequence

import numpy as np

from .common import RelationFieldPredictionP2PrecursorAuditError, canonical_bytes


def _arrays(
    scores: Sequence[float], outcomes: Sequence[bool]
) -> tuple[np.ndarray, np.ndarray]:
    x = np.asarray(scores, dtype=float)
    y = np.asarray(outcomes, dtype=bool)
    if (
        x.ndim != 1
        or y.ndim != 1
        or x.shape != y.shape
        or np.any(~np.isfinite(x))
    ):
        raise RelationFieldPredictionP2PrecursorAuditError(
            "validator metric input mismatch"
        )
    return x, y


def _auc(
    scores: Sequence[float], outcomes: Sequence[bool]
) -> float | None:
    x, y = _arrays(scores, outcomes)
    positive = x[y]
    negative = x[~y]
    if positive.size == 0 or negative.size == 0:
        return None
    value = 0.0
    for item in positive:
        value += np.count_nonzero(item > negative)
        value += 0.5 * np.count_nonzero(item == negative)
    return float(value / (positive.size * negative.size))


def _ap(
    scores: Sequence[float], outcomes: Sequence[bool]
) -> float | None:
    x, y = _arrays(scores, outcomes)
    positive_count = int(np.count_nonzero(y))
    if positive_count == 0:
        return None
    order = np.argsort(-x, kind="mergesort")
    x = x[order]
    y = y[order]
    seen = 0
    true_seen = 0
    value = 0.0
    start = 0
    while start < x.size:
        stop = start + 1
        while stop < x.size and x[stop] == x[start]:
            stop += 1
        added = int(np.count_nonzero(y[start:stop]))
        seen += stop - start
        true_seen += added
        if added:
            value += (
                added / positive_count
            ) * (true_seen / seen)
        start = stop
    return float(value)


def _classification(
    scores: Sequence[float], outcomes: Sequence[bool]
) -> dict[str, Any]:
    x, y = _arrays(scores, outcomes)
    prediction = x > 0
    tp = int(np.count_nonzero(prediction & y))
    fp = int(np.count_nonzero(prediction & ~y))
    tn = int(np.count_nonzero(~prediction & ~y))
    fn = int(np.count_nonzero(~prediction & y))
    total = tp + fp + tn + fn

    def divide(numerator: float, denominator: float) -> float | None:
        return None if denominator == 0 else float(numerator / denominator)

    precision = divide(tp, tp + fp)
    recall = divide(tp, tp + fn)
    specificity = divide(tn, tn + fp)
    accuracy = divide(tp + tn, total)
    balanced = (
        None
        if recall is None or specificity is None
        else 0.5 * (recall + specificity)
    )
    denominator = math.sqrt(
        (tp + fp) * (tp + fn) * (tn + fp) * (tn + fn)
    )
    return {
        "true_positive": tp,
        "false_positive": fp,
        "true_negative": tn,
        "false_negative": fn,
        "precision": precision,
        "recall": recall,
        "specificity": specificity,
        "accuracy": accuracy,
        "balanced_accuracy": balanced,
        "f1": divide(2 * tp, 2 * tp + fp + fn),
        "matthews_correlation": divide(
            tp * tn - fp * fn, denominator
        ),
        "brier_score": (
            None
            if total == 0
            else float(
                np.mean(
                    (
                        prediction.astype(float)
                        - y.astype(float)
                    )
                    ** 2
                )
            )
        ),
    }


def _point(
    scores: Sequence[float], outcomes: Sequence[bool]
) -> dict[str, Any]:
    x, y = _arrays(scores, outcomes)
    positive = x[y]
    negative = x[~y]
    result = {
        "sample_count": int(y.size),
        "positive_outcome_count": int(np.count_nonzero(y)),
        "negative_outcome_count": int(np.count_nonzero(~y)),
        "positive_prevalence": (
            None if y.size == 0 else float(np.mean(y))
        ),
        "roc_auc": _auc(x, y),
        "average_precision": _ap(x, y),
        "positive_score_mean": (
            None
            if positive.size == 0
            else float(np.mean(positive))
        ),
        "negative_score_mean": (
            None
            if negative.size == 0
            else float(np.mean(negative))
        ),
        "positive_score_median": (
            None
            if positive.size == 0
            else float(np.median(positive))
        ),
        "negative_score_median": (
            None
            if negative.size == 0
            else float(np.median(negative))
        ),
    }
    result.update(_classification(x, y))
    return result


def _seed(value: Mapping[str, Any]) -> int:
    return int.from_bytes(
        hashlib.sha256(canonical_bytes(value)).digest()[:8],
        "big",
    )


def _bootstrap(
    scores: Sequence[float],
    outcomes: Sequence[bool],
    groups: Sequence[str],
    *,
    replicates: int,
    confidence: float,
    key: Mapping[str, Any],
) -> dict[str, Any]:
    x, y = _arrays(scores, outcomes)
    group = np.asarray([str(value) for value in groups], dtype=object)
    unique = sorted(set(group.tolist()))
    if not unique:
        return {
            "requested_replicates": replicates,
            "trajectory_group_count": 0,
            "roc_auc_valid_replicates": 0,
            "average_precision_valid_replicates": 0,
            "roc_auc_interval": None,
            "average_precision_interval": None,
        }
    indices_by_group = {
        value: np.flatnonzero(group == value) for value in unique
    }
    rng = np.random.default_rng(_seed(key))
    aucs: list[float] = []
    aps: list[float] = []
    for _ in range(replicates):
        chosen = rng.choice(unique, size=len(unique), replace=True)
        selected = np.concatenate(
            [indices_by_group[str(value)] for value in chosen]
        )
        auc = _auc(x[selected], y[selected])
        ap = _ap(x[selected], y[selected])
        if auc is not None:
            aucs.append(auc)
        if ap is not None:
            aps.append(ap)
    alpha = (1 - confidence) / 2

    def interval(values: list[float]) -> list[float] | None:
        if not values:
            return None
        return [
            float(
                np.quantile(values, alpha, method="linear")
            ),
            float(
                np.quantile(
                    values, 1 - alpha, method="linear"
                )
            ),
        ]

    return {
        "requested_replicates": replicates,
        "trajectory_group_count": len(unique),
        "roc_auc_valid_replicates": len(aucs),
        "average_precision_valid_replicates": len(aps),
        "roc_auc_interval": interval(aucs),
        "average_precision_interval": interval(aps),
    }


def _permutation(
    values: Sequence[float], key: Mapping[str, Any]
) -> list[float]:
    x = np.asarray(values, dtype=float)
    rng = np.random.default_rng(_seed(key))
    return x[rng.permutation(x.size)].astype(float).tolist()


