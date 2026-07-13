from __future__ import annotations

import hashlib
import math
from typing import Any, Mapping, Sequence

import numpy as np

from .common import RelationFieldPredictionP2PrecursorAuditError, canonical_bytes


def _as_arrays(scores: Sequence[float], outcomes: Sequence[bool]) -> tuple[np.ndarray, np.ndarray]:
    score = np.asarray(scores, dtype=np.float64)
    truth = np.asarray(outcomes, dtype=bool)
    if score.ndim != 1 or truth.ndim != 1 or score.shape != truth.shape:
        raise RelationFieldPredictionP2PrecursorAuditError("P2-4 metric shape mismatch")
    if np.any(~np.isfinite(score)):
        raise RelationFieldPredictionP2PrecursorAuditError("P2-4 score contains nonfinite value")
    return score, truth


def roc_auc(scores: Sequence[float], outcomes: Sequence[bool]) -> float | None:
    score, truth = _as_arrays(scores, outcomes)
    positive = score[truth]
    negative = score[~truth]
    if positive.size == 0 or negative.size == 0:
        return None
    wins = 0.0
    for value in positive:
        wins += float(np.count_nonzero(value > negative))
        wins += 0.5 * float(np.count_nonzero(value == negative))
    return wins / float(positive.size * negative.size)


def average_precision(scores: Sequence[float], outcomes: Sequence[bool]) -> float | None:
    score, truth = _as_arrays(scores, outcomes)
    positives = int(np.count_nonzero(truth))
    if positives == 0:
        return None
    order = np.argsort(-score, kind="mergesort")
    sorted_score = score[order]
    sorted_truth = truth[order]
    total_seen = 0
    true_seen = 0
    ap = 0.0
    index = 0
    while index < sorted_score.size:
        stop = index + 1
        while stop < sorted_score.size and sorted_score[stop] == sorted_score[index]:
            stop += 1
        group_truth = sorted_truth[index:stop]
        total_seen += stop - index
        added = int(np.count_nonzero(group_truth))
        true_seen += added
        if added:
            ap += (added / positives) * (true_seen / total_seen)
        index = stop
    return float(ap)


def classification_metrics(scores: Sequence[float], outcomes: Sequence[bool]) -> dict[str, Any]:
    score, truth = _as_arrays(scores, outcomes)
    prediction = score > 0.0
    tp = int(np.count_nonzero(prediction & truth))
    fp = int(np.count_nonzero(prediction & ~truth))
    tn = int(np.count_nonzero(~prediction & ~truth))
    fn = int(np.count_nonzero(~prediction & truth))
    total = tp + fp + tn + fn

    def ratio(numerator: float, denominator: float) -> float | None:
        return None if denominator == 0 else float(numerator / denominator)

    precision = ratio(tp, tp + fp)
    recall = ratio(tp, tp + fn)
    specificity = ratio(tn, tn + fp)
    accuracy = ratio(tp + tn, total)
    balanced = None if recall is None or specificity is None else 0.5 * (recall + specificity)
    f1 = ratio(2 * tp, 2 * tp + fp + fn)
    denominator = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    mcc = ratio(tp * tn - fp * fn, denominator)
    brier = None if total == 0 else float(np.mean((prediction.astype(float) - truth.astype(float)) ** 2))
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
        "f1": f1,
        "matthews_correlation": mcc,
        "brier_score": brier,
    }


def point_metrics(scores: Sequence[float], outcomes: Sequence[bool]) -> dict[str, Any]:
    score, truth = _as_arrays(scores, outcomes)
    positive = score[truth]
    negative = score[~truth]
    prevalence = None if truth.size == 0 else float(np.mean(truth))
    result: dict[str, Any] = {
        "sample_count": int(truth.size),
        "positive_outcome_count": int(np.count_nonzero(truth)),
        "negative_outcome_count": int(np.count_nonzero(~truth)),
        "positive_prevalence": prevalence,
        "roc_auc": roc_auc(score, truth),
        "average_precision": average_precision(score, truth),
        "positive_score_mean": None if positive.size == 0 else float(np.mean(positive)),
        "negative_score_mean": None if negative.size == 0 else float(np.mean(negative)),
        "positive_score_median": None if positive.size == 0 else float(np.median(positive)),
        "negative_score_median": None if negative.size == 0 else float(np.median(negative)),
    }
    result.update(classification_metrics(score, truth))
    return result


def _seed(key: Mapping[str, Any]) -> int:
    digest = hashlib.sha256(canonical_bytes(key)).digest()
    return int.from_bytes(digest[:8], "big", signed=False)


def grouped_bootstrap(
    scores: Sequence[float],
    outcomes: Sequence[bool],
    groups: Sequence[str],
    *,
    replicates: int,
    confidence: float,
    seed_key: Mapping[str, Any],
) -> dict[str, Any]:
    score, truth = _as_arrays(scores, outcomes)
    group = np.asarray([str(value) for value in groups], dtype=object)
    if group.shape != score.shape or any(not value for value in group.tolist()):
        raise RelationFieldPredictionP2PrecursorAuditError("P2-4 bootstrap group mismatch")
    unique = sorted(set(group.tolist()))
    if not unique:
        return {"replicate_count": 0, "roc_auc_interval": None, "average_precision_interval": None}
    by_group = {value: np.flatnonzero(group == value) for value in unique}
    rng = np.random.default_rng(_seed(seed_key))
    auc_values: list[float] = []
    ap_values: list[float] = []
    for _ in range(int(replicates)):
        sampled = rng.choice(unique, size=len(unique), replace=True)
        indices = np.concatenate([by_group[str(value)] for value in sampled])
        auc = roc_auc(score[indices], truth[indices])
        ap = average_precision(score[indices], truth[indices])
        if auc is not None:
            auc_values.append(float(auc))
        if ap is not None:
            ap_values.append(float(ap))
    alpha = (1.0 - float(confidence)) / 2.0

    def interval(values: list[float]) -> list[float] | None:
        if not values:
            return None
        return [
            float(np.quantile(values, alpha, method="linear")),
            float(np.quantile(values, 1.0 - alpha, method="linear")),
        ]

    return {
        "requested_replicates": int(replicates),
        "trajectory_group_count": len(unique),
        "roc_auc_valid_replicates": len(auc_values),
        "average_precision_valid_replicates": len(ap_values),
        "roc_auc_interval": interval(auc_values),
        "average_precision_interval": interval(ap_values),
    }


def metric_record(
    rows: Sequence[Mapping[str, Any]],
    *,
    partition: str,
    horizon: int,
    target_id: str,
    score_id: str,
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    selected = [
        row for row in rows
        if row["partition"] == partition
        and int(row["horizon"]) == int(horizon)
        and row["target_id"] == target_id
        and row.get("applicable", True)
        and row["scores"].get(score_id) is not None
    ]
    scores = [float(row["scores"][score_id]) for row in selected]
    outcomes = [bool(row["outcome"]) for row in selected]
    groups = [str(row["trajectory_group_id"]) for row in selected]
    point = point_metrics(scores, outcomes)
    bootstrap_settings = contract["metrics"]["bootstrap"]
    bootstrap = grouped_bootstrap(
        scores,
        outcomes,
        groups,
        replicates=int(bootstrap_settings["replicates"]),
        confidence=float(bootstrap_settings["confidence"]),
        seed_key={
            "contract_version": contract["contract_version"],
            "partition": partition,
            "horizon": int(horizon),
            "target_id": target_id,
            "score_id": score_id,
        },
    ) if scores else {
        "requested_replicates": int(bootstrap_settings["replicates"]),
        "trajectory_group_count": 0,
        "roc_auc_valid_replicates": 0,
        "average_precision_valid_replicates": 0,
        "roc_auc_interval": None,
        "average_precision_interval": None,
    }
    return {
        "partition": partition,
        "horizon": int(horizon),
        "target_id": target_id,
        "score_id": score_id,
        **point,
        "bootstrap": bootstrap,
    }


def deterministic_permutation(values: Sequence[float], key: Mapping[str, Any]) -> list[float]:
    array = np.asarray(values, dtype=np.float64)
    rng = np.random.default_rng(_seed(key))
    return array[rng.permutation(array.size)].astype(float).tolist()
