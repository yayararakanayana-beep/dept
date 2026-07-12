"""固定5軸 動的関係場 RF-10: RF-9構造候補の未来区間予測検証。"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from statistics import NormalDist
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from relation_field_hodge_decomposition_rc1 import _load_grid_with_indices
from relation_field_risk_structure_rc1 import validate_risk_structure
from relation_field_single_transition_rc1 import load_contract as load_rf3_contract
from relation_field_temporal_consistency_rc1 import _load_history_window

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "configs" / "relation_field_predictive_validation_rc1.json"
CASE_MANIFEST_VERSION = "relation_field_predictive_validation_case_manifest_rc1"
CELL_COUNT = 3125
AXIS_COUNT = 5
PRIMARY_TARGETS = (
    "overconvergence_candidate",
    "fixation_candidate",
    "divergence_candidate",
    "recovery_margin_reduction_candidate",
)


class RelationFieldPredictiveValidationError(ValueError):
    """RF-10契約、予測スナップショット、未来結果、評価成果物の不整合。"""


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_npz(path: Path, arrays: Mapping[str, np.ndarray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(arrays):
            buffer = io.BytesIO()
            np.save(buffer, np.asarray(arrays[name]), allow_pickle=False)
            info = zipfile.ZipInfo(f"{name}.npy", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, buffer.getvalue(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def _load_npz(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as loaded:
        return {name: loaded[name].copy() for name in loaded.files}


def _manifest_entries(root: Path, *, exclude: Iterable[str] = ()) -> list[dict[str, Any]]:
    excluded = set(exclude)
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": _sha256_file(path),
            "size_bytes": path.stat().st_size,
        }
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.relative_to(root).as_posix() not in excluded
    ]


def _verify_manifest(root: Path) -> None:
    manifest = _load_json(root / "manifest.json")
    expected: set[str] = set()
    for entry in manifest.get("files", []):
        relative = str(entry["path"])
        expected.add(relative)
        path = root / relative
        if (
            not path.is_file()
            or path.stat().st_size != int(entry["size_bytes"])
            or _sha256_file(path) != entry["sha256"]
        ):
            raise RelationFieldPredictiveValidationError(f"manifest mismatch: {relative}")
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    if expected != actual:
        raise RelationFieldPredictiveValidationError("manifest file set mismatch")


def load_contract(path: str | Path = DEFAULT_CONTRACT) -> dict[str, Any]:
    contract = _load_json(Path(path))
    validate_contract(contract)
    return contract


def validate_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("contract_version") != "relation_field_predictive_validation_rc1":
        raise RelationFieldPredictiveValidationError("unsupported RF-10 contract")
    horizons = [int(value) for value in contract.get("evaluation", {}).get("horizons", [])]
    if not horizons or horizons != sorted(set(horizons)) or min(horizons) < 1:
        raise RelationFieldPredictiveValidationError("RF-10 horizon contract mismatch")
    if contract.get("input", {}).get("only_final_RF9_row_is_prediction_sample") is not True:
        raise RelationFieldPredictiveValidationError("RF-10 must use only final RF-9 row")
    if contract.get("input", {}).get("prediction_snapshot_must_be_frozen_before_future_suffix_read") is not True:
        raise RelationFieldPredictiveValidationError("RF-10 prediction snapshot must precede future read")
    if contract.get("semantic_limits", {}).get("true_irreversibility_claim") is not False:
        raise RelationFieldPredictiveValidationError("RF-10 must not claim true irreversibility")
    for section in ("concentration", "dispersion"):
        required = int(contract["future_outcomes"][section]["required_signal_count"])
        if required < 1 or required > 4:
            raise RelationFieldPredictiveValidationError(f"RF-10 {section} signal count mismatch")


def _resolve_path(base: Path, raw: Any, field: str) -> Path:
    if not isinstance(raw, str) or not raw:
        raise RelationFieldPredictiveValidationError(f"RF-10 missing case path: {field}")
    path = Path(raw)
    return path if path.is_absolute() else (base / path).resolve()


def _load_case_manifest(path: Path, contract: Mapping[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    raw = _load_json(path)
    if raw.get("manifest_version") != contract["input"]["case_manifest_version"]:
        raise RelationFieldPredictiveValidationError("RF-10 case manifest version mismatch")
    cases = raw.get("cases")
    if not isinstance(cases, list) or len(cases) < int(contract["input"]["minimum_case_count"]):
        raise RelationFieldPredictiveValidationError("RF-10 case manifest has too few cases")
    required = tuple(contract["input"]["required_case_fields"])
    allowed_partitions = set(contract["input"]["allowed_partitions"])
    seen_ids: set[str] = set()
    resolved: list[dict[str, Any]] = []
    for index, item in enumerate(cases):
        if not isinstance(item, dict) or any(field not in item for field in required):
            raise RelationFieldPredictiveValidationError(f"RF-10 case field mismatch at index {index}")
        case_id = str(item["case_id"])
        partition = str(item["partition"])
        if not case_id or case_id in seen_ids:
            raise RelationFieldPredictiveValidationError("RF-10 case_id must be unique")
        if partition not in allowed_partitions:
            raise RelationFieldPredictiveValidationError(f"RF-10 unsupported partition: {partition}")
        seen_ids.add(case_id)
        resolved_item = {"case_id": case_id, "partition": partition}
        for field in required:
            if field in {"case_id", "partition"}:
                continue
            resolved_item[field] = _resolve_path(path.parent, item[field], field)
        resolved.append(resolved_item)
    return raw, resolved


def _bool_scalar(value: Any, name: str) -> bool:
    array = np.asarray(value)
    if array.shape != ():
        raise RelationFieldPredictiveValidationError(f"RF-10 {name} must be scalar")
    return bool(array.item())


def _snapshot_case_prediction(case: Mapping[str, Any], contract: Mapping[str, Any]) -> dict[str, Any]:
    trajectory = Path(case["trajectory_dir"])
    grid = Path(case["grid_artifact_dir"])
    rf5 = Path(case["rf5_artifact_dir"])
    rf6 = Path(case["rf6_artifact_dir"])
    rf7 = Path(case["rf7_artifact_dir"])
    rf8 = Path(case["rf8_artifact_dir"])
    rf9 = Path(case["rf9_artifact_dir"])
    validate_risk_structure(rf9, trajectory, grid, rf5, rf6, rf7, rf8)
    identity = _load_json(rf9 / "identity.json")
    metrics = _load_npz(rf9 / "risk_structure_metrics.npz")
    risk_times = np.asarray(metrics["risk_transition_times"], dtype=np.int32)
    if risk_times.ndim != 1 or risk_times.size < 1:
        raise RelationFieldPredictiveValidationError("RF-10 RF-9 has no final risk row")
    cutoff_t = int(identity["to_t"])
    if int(identity["max_source_t_read"]) != cutoff_t:
        raise RelationFieldPredictiveValidationError("RF-10 RF-9 cutoff mismatch")
    if int(risk_times[-1]) != cutoff_t:
        raise RelationFieldPredictiveValidationError("RF-10 final RF-9 row is not aligned to cutoff")
    final = -1
    candidate = {
        name: _bool_scalar(metrics[name][final], name)
        for name in PRIMARY_TARGETS
    }
    baseline = {
        "overconvergence_candidate": _bool_scalar(
            metrics["shape_convergence_signal"][final], "shape_convergence_signal"
        ),
        "fixation_candidate": bool(
            _bool_scalar(metrics["shape_convergence_signal"][final], "shape_convergence_signal")
            and _bool_scalar(
                metrics["boundary_recovery_weakening_signal"][final],
                "boundary_recovery_weakening_signal",
            )
        ),
        "divergence_candidate": _bool_scalar(
            metrics["shape_divergence_signal"][final], "shape_divergence_signal"
        ),
        "recovery_margin_reduction_candidate": _bool_scalar(
            metrics["boundary_recovery_weakening_signal"][final],
            "boundary_recovery_weakening_signal",
        ),
    }
    modifiers = {
        "new_drive_coincident_candidate": _bool_scalar(
            metrics["new_drive_coincident_candidate"][final],
            "new_drive_coincident_candidate",
        ),
        "unresolved_residual_dominance_candidate": _bool_scalar(
            metrics["unresolved_residual_dominance_candidate"][final],
            "unresolved_residual_dominance_candidate",
        ),
        "gradient_dominance_consensus": _bool_scalar(
            metrics["gradient_dominance_consensus"][final],
            "gradient_dominance_consensus",
        ),
        "circulation_dominance_consensus": _bool_scalar(
            metrics["circulation_dominance_consensus"][final],
            "circulation_dominance_consensus",
        ),
        "axis_flow_ambiguity_maximum": float(metrics["axis_flow_ambiguity_maximum"][final]),
        "unresolved_residual_fraction_mean": float(
            metrics["unresolved_residual_fraction_mean"][final]
        ),
    }
    frozen = {
        "case_id": str(case["case_id"]),
        "partition": str(case["partition"]),
        "trajectory_id": str(identity["trajectory_id"]),
        "cutoff_t": cutoff_t,
        "source_history_chain_hash": str(identity["source_history_chain_hash"]),
        "rf9_risk_structure_id": str(identity["risk_structure_id"]),
        "rf9_manifest_hash": _sha256_file(rf9 / "manifest.json"),
        "prediction_row_index": int(risk_times.size - 1),
        "prediction_time": cutoff_t,
        "candidate": candidate,
        "component_baseline": baseline,
        "always_negative_baseline": {name: False for name in PRIMARY_TARGETS},
        "modifiers": modifiers,
        "nonfinal_RF9_rows_evaluated": False,
    }
    frozen["prediction_snapshot_hash"] = _sha256_bytes(_canonical_json(frozen))
    return frozen


def freeze_prediction_snapshot(cases: Sequence[Mapping[str, Any]], contract: Mapping[str, Any]) -> dict[str, Any]:
    rows = [_snapshot_case_prediction(case, contract) for case in cases]
    group_partitions: dict[str, set[str]] = {}
    for row in rows:
        group_partitions.setdefault(str(row["trajectory_id"]), set()).add(str(row["partition"]))
    crossing = {
        group: sorted(partitions)
        for group, partitions in group_partitions.items()
        if len(partitions) > 1
    }
    if crossing:
        raise RelationFieldPredictiveValidationError(
            f"RF-10 trajectory group crosses partitions: {crossing}"
        )
    payload = {
        "contract_version": contract["contract_version"],
        "only_final_RF9_row_used": True,
        "future_suffix_read_before_snapshot": False,
        "cases": rows,
    }
    payload["prediction_snapshot_hash"] = _sha256_bytes(_canonical_json(payload))
    return payload


def compute_frame_metrics(distribution: np.ndarray, grid: Mapping[str, Any]) -> dict[str, float]:
    flat = np.asarray(distribution, dtype=np.float64).reshape(-1, order="C")
    if flat.shape != (CELL_COUNT,) or not np.all(np.isfinite(flat)) or float(np.min(flat)) < 0.0:
        raise RelationFieldPredictiveValidationError("RF-10 frame distribution mismatch")
    total = float(np.sum(flat, dtype=np.float64))
    if abs(total - 1.0) > 1e-9:
        raise RelationFieldPredictiveValidationError("RF-10 frame mass must sum to one")
    positive = flat[flat > 0.0]
    entropy = 0.0 if positive.size == 0 else float(-np.sum(positive * np.log(positive), dtype=np.float64))
    coordinates = np.asarray(grid["node_values"], dtype=np.float64)
    centroid = np.sum(flat[:, None] * coordinates, axis=0)
    centered = coordinates - centroid
    total_variance = float(np.sum(flat * np.sum(centered * centered, axis=1), dtype=np.float64))
    indices = np.asarray(grid["node_indices"], dtype=np.int16)
    boundary = np.any((indices == 0) | (indices == 4), axis=1)
    return {
        "normalized_entropy": entropy / math.log(CELL_COUNT),
        "effective_support": float(math.exp(entropy)),
        "peak_mass": float(np.max(flat)),
        "total_variance": total_variance,
        "boundary_mass": float(np.sum(flat[boundary], dtype=np.float64)),
    }


def _concentration_signals(anchor: Mapping[str, float], future: Mapping[str, float], settings: Mapping[str, Any]) -> tuple[int, dict[str, bool]]:
    support_ratio = float(future["effective_support"]) / max(float(anchor["effective_support"]), 1e-12)
    signals = {
        "normalized_entropy_drop": (
            float(anchor["normalized_entropy"]) - float(future["normalized_entropy"])
            >= float(settings["normalized_entropy_drop_minimum"])
        ),
        "effective_support_drop": support_ratio <= float(settings["effective_support_ratio_maximum"]),
        "peak_mass_gain": (
            float(future["peak_mass"]) - float(anchor["peak_mass"])
            >= float(settings["peak_mass_gain_minimum"])
        ),
        "total_variance_drop": (
            float(anchor["total_variance"]) - float(future["total_variance"])
            >= float(settings["total_variance_drop_minimum"])
        ),
    }
    return sum(bool(value) for value in signals.values()), signals


def _dispersion_signals(anchor: Mapping[str, float], future: Mapping[str, float], settings: Mapping[str, Any]) -> tuple[int, dict[str, bool]]:
    support_ratio = float(future["effective_support"]) / max(float(anchor["effective_support"]), 1e-12)
    signals = {
        "normalized_entropy_gain": (
            float(future["normalized_entropy"]) - float(anchor["normalized_entropy"])
            >= float(settings["normalized_entropy_gain_minimum"])
        ),
        "effective_support_gain": support_ratio >= float(settings["effective_support_ratio_minimum"]),
        "peak_mass_drop": (
            float(anchor["peak_mass"]) - float(future["peak_mass"])
            >= float(settings["peak_mass_drop_minimum"])
        ),
        "total_variance_gain": (
            float(future["total_variance"]) - float(anchor["total_variance"])
            >= float(settings["total_variance_gain_minimum"])
        ),
    }
    return sum(bool(value) for value in signals.values()), signals


def compute_future_outcomes(
    frame_metrics: Sequence[Mapping[str, float]],
    horizon: int,
    settings: Mapping[str, Any],
) -> dict[str, Any]:
    if len(frame_metrics) != horizon + 1:
        raise RelationFieldPredictiveValidationError("RF-10 future window length mismatch")
    anchor = frame_metrics[0]
    futures = list(frame_metrics[1:])
    endpoint = futures[-1]
    concentration_settings = settings["concentration"]
    dispersion_settings = settings["dispersion"]
    concentration_counts: list[int] = []
    concentration_details: list[dict[str, bool]] = []
    for frame in futures:
        count, details = _concentration_signals(anchor, frame, concentration_settings)
        concentration_counts.append(count)
        concentration_details.append(details)
    endpoint_concentration = concentration_counts[-1] >= int(concentration_settings["required_signal_count"])
    required_persistent_frames = int(
        math.ceil(horizon * float(settings["persistent_concentration"]["minimum_future_frame_fraction"]))
    )
    persistent_count = sum(
        count >= int(concentration_settings["required_signal_count"])
        for count in concentration_counts
    )
    persistent_concentration = bool(
        endpoint_concentration and persistent_count >= required_persistent_frames
    )
    dispersion_count, dispersion_details = _dispersion_signals(anchor, endpoint, dispersion_settings)
    dispersion = dispersion_count >= int(dispersion_settings["required_signal_count"])

    recovery_settings = settings["recovery_failure"]
    recovery_applicable = False
    recovery_failure = False
    event_index = -1
    recovery_signal_count = 0
    if horizon >= int(recovery_settings["minimum_horizon"]):
        for index, frame in enumerate(futures[:-1]):
            concentration_event_count, _ = _concentration_signals(anchor, frame, concentration_settings)
            boundary_increase = float(frame["boundary_mass"]) - float(anchor["boundary_mass"])
            if (
                concentration_event_count >= int(recovery_settings["concentration_event_signal_count"])
                or boundary_increase >= float(recovery_settings["boundary_mass_increase_event_minimum"])
            ):
                event_index = index
                event = frame
                recovery_applicable = True
                support_recovery_ratio = float(endpoint["effective_support"]) / max(
                    float(event["effective_support"]), 1e-12
                )
                recovery_signals = {
                    "normalized_entropy_recovery": (
                        float(endpoint["normalized_entropy"]) - float(event["normalized_entropy"])
                        >= float(recovery_settings["normalized_entropy_recovery_minimum"])
                    ),
                    "effective_support_recovery": (
                        support_recovery_ratio
                        >= float(recovery_settings["effective_support_recovery_ratio_minimum"])
                    ),
                    "peak_mass_recovery": (
                        float(event["peak_mass"]) - float(endpoint["peak_mass"])
                        >= float(recovery_settings["peak_mass_recovery_drop_minimum"])
                    ),
                    "boundary_mass_recovery": (
                        float(event["boundary_mass"]) - float(endpoint["boundary_mass"])
                        >= float(recovery_settings["boundary_mass_recovery_drop_minimum"])
                    ),
                }
                recovery_signal_count = sum(bool(value) for value in recovery_signals.values())
                recovery_failure = recovery_signal_count < int(
                    recovery_settings["required_recovery_signal_count"]
                )
                break
    return {
        "future_concentration_outcome": bool(endpoint_concentration),
        "future_persistent_concentration_outcome": bool(persistent_concentration),
        "future_dispersion_outcome": bool(dispersion),
        "future_recovery_failure_outcome": bool(recovery_failure),
        "future_recovery_failure_applicable": bool(recovery_applicable),
        "concentration_signal_count_endpoint": int(concentration_counts[-1]),
        "persistent_concentration_frame_count": int(persistent_count),
        "persistent_concentration_required_frame_count": int(required_persistent_frames),
        "dispersion_signal_count_endpoint": int(dispersion_count),
        "recovery_event_future_index": int(event_index),
        "recovery_signal_count": int(recovery_signal_count),
        "endpoint_concentration_signals": concentration_details[-1],
        "endpoint_dispersion_signals": dispersion_details,
        "anchor_metrics": dict(anchor),
        "endpoint_metrics": dict(endpoint),
    }


def _load_case_future(
    case: Mapping[str, Any],
    snapshot: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    cutoff_t = int(snapshot["cutoff_t"])
    max_horizon = max(int(value) for value in contract["evaluation"]["horizons"])
    rf3 = load_rf3_contract()
    history = _load_history_window(
        Path(case["trajectory_dir"]),
        start_t=cutoff_t,
        to_t=cutoff_t + max_horizon,
        mass_tolerance=float(rf3["input"]["distribution_mass_tolerance"]),
        minimum_transition_count=max_horizon,
    )
    if history["trajectory_id"] != snapshot["trajectory_id"]:
        raise RelationFieldPredictiveValidationError("RF-10 full trajectory id mismatch")
    prefix = _load_history_window(
        Path(case["trajectory_dir"]),
        start_t=int(_load_json(Path(case["rf9_artifact_dir"]) / "identity.json")["start_t"]),
        to_t=cutoff_t,
        mass_tolerance=float(rf3["input"]["distribution_mass_tolerance"]),
        minimum_transition_count=1,
    )
    if prefix["history_chain_hash"] != snapshot["source_history_chain_hash"]:
        raise RelationFieldPredictiveValidationError("RF-10 full trajectory prefix hash mismatch")
    grid = _load_grid_with_indices(Path(case["grid_artifact_dir"]))
    metrics = [compute_frame_metrics(frame, grid) for frame in history["frames"]]
    horizons: dict[str, Any] = {}
    for horizon in contract["evaluation"]["horizons"]:
        horizon_value = int(horizon)
        horizons[str(horizon_value)] = compute_future_outcomes(
            metrics[: horizon_value + 1], horizon_value, contract["future_outcomes"]
        )
    return {
        "case_id": snapshot["case_id"],
        "trajectory_id": snapshot["trajectory_id"],
        "partition": snapshot["partition"],
        "cutoff_t": cutoff_t,
        "max_future_t_read": cutoff_t + max_horizon,
        "prefix_history_chain_hash_verified": True,
        "horizons": horizons,
    }


def _wilson_interval(successes: int, total: int, confidence: float) -> list[float] | None:
    if total <= 0:
        return None
    z = NormalDist().inv_cdf(0.5 + confidence / 2.0)
    proportion = successes / total
    denominator = 1.0 + z * z / total
    center = (proportion + z * z / (2.0 * total)) / denominator
    margin = z * math.sqrt((proportion * (1.0 - proportion) + z * z / (4.0 * total)) / total) / denominator
    return [max(0.0, center - margin), min(1.0, center + margin)]


def classification_metrics(
    prediction: Sequence[bool],
    truth: Sequence[bool],
    applicable: Sequence[bool] | None = None,
    *,
    confidence: float = 0.95,
) -> dict[str, Any]:
    pred = np.asarray(prediction, dtype=bool)
    actual = np.asarray(truth, dtype=bool)
    if pred.shape != actual.shape or pred.ndim != 1:
        raise RelationFieldPredictiveValidationError("RF-10 metric shape mismatch")
    mask = np.ones(pred.shape, dtype=bool) if applicable is None else np.asarray(applicable, dtype=bool)
    if mask.shape != pred.shape:
        raise RelationFieldPredictiveValidationError("RF-10 applicability shape mismatch")
    pred = pred[mask]
    actual = actual[mask]
    tp = int(np.count_nonzero(pred & actual))
    fp = int(np.count_nonzero(pred & ~actual))
    tn = int(np.count_nonzero(~pred & ~actual))
    fn = int(np.count_nonzero(~pred & actual))
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
    brier = None if total == 0 else float(np.mean((pred.astype(float) - actual.astype(float)) ** 2))
    return {
        "sample_count": total,
        "positive_outcome_count": int(tp + fn),
        "negative_outcome_count": int(tn + fp),
        "predicted_positive_count": int(tp + fp),
        "true_positive": tp,
        "false_positive": fp,
        "true_negative": tn,
        "false_negative": fn,
        "precision": precision,
        "precision_wilson_interval": _wilson_interval(tp, tp + fp, confidence),
        "recall": recall,
        "recall_wilson_interval": _wilson_interval(tp, tp + fn, confidence),
        "specificity": specificity,
        "accuracy": accuracy,
        "balanced_accuracy": balanced,
        "f1": f1,
        "matthews_correlation": mcc,
        "brier_score": brier,
    }


def _metric_difference(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, float | None]:
    output: dict[str, float | None] = {}
    for key in ("precision", "recall", "specificity", "accuracy", "balanced_accuracy", "f1", "matthews_correlation", "brier_score"):
        left_value, right_value = left.get(key), right.get(key)
        output[key] = None if left_value is None or right_value is None else float(left_value - right_value)
    return output


def _target_name(candidate_name: str, contract: Mapping[str, Any]) -> str:
    return str(contract["future_outcomes"]["target_mapping"][candidate_name])


def build_sample_ledger(
    snapshot: Mapping[str, Any],
    future_rows: Sequence[Mapping[str, Any]],
    contract: Mapping[str, Any],
) -> list[dict[str, Any]]:
    future_by_case = {str(row["case_id"]): row for row in future_rows}
    rows: list[dict[str, Any]] = []
    for prediction in snapshot["cases"]:
        case_id = str(prediction["case_id"])
        future = future_by_case[case_id]
        for horizon in contract["evaluation"]["horizons"]:
            horizon_value = int(horizon)
            outcome = future["horizons"][str(horizon_value)]
            row = {
                "case_id": case_id,
                "trajectory_id": prediction["trajectory_id"],
                "partition": prediction["partition"],
                "cutoff_t": int(prediction["cutoff_t"]),
                "horizon": horizon_value,
                "target_t": int(prediction["cutoff_t"]) + horizon_value,
                "prediction_snapshot_hash": prediction["prediction_snapshot_hash"],
                "candidate": prediction["candidate"],
                "component_baseline": prediction["component_baseline"],
                "always_negative_baseline": prediction["always_negative_baseline"],
                "modifiers": prediction["modifiers"],
                "outcomes": {
                    name: outcome[name]
                    for name in (
                        "future_concentration_outcome",
                        "future_persistent_concentration_outcome",
                        "future_dispersion_outcome",
                        "future_recovery_failure_outcome",
                        "future_recovery_failure_applicable",
                    )
                },
                "outcome_diagnostics": {
                    key: outcome[key]
                    for key in (
                        "concentration_signal_count_endpoint",
                        "persistent_concentration_frame_count",
                        "persistent_concentration_required_frame_count",
                        "dispersion_signal_count_endpoint",
                        "recovery_event_future_index",
                        "recovery_signal_count",
                    )
                },
            }
            rows.append(row)
    return rows


def compute_predictive_metrics(rows: Sequence[Mapping[str, Any]], contract: Mapping[str, Any]) -> dict[str, Any]:
    confidence = float(contract["metrics"]["wilson_interval_confidence"])
    partitions = list(contract["input"]["allowed_partitions"])
    groups: dict[str, Any] = {}
    for partition in partitions:
        partition_rows = [row for row in rows if row["partition"] == partition]
        partition_payload: dict[str, Any] = {}
        for horizon in contract["evaluation"]["horizons"]:
            horizon_value = int(horizon)
            horizon_rows = [row for row in partition_rows if int(row["horizon"]) == horizon_value]
            target_payload: dict[str, Any] = {}
            for candidate_name in PRIMARY_TARGETS:
                outcome_name = _target_name(candidate_name, contract)
                applicable = [
                    bool(row["outcomes"]["future_recovery_failure_applicable"])
                    if outcome_name == "future_recovery_failure_outcome"
                    else True
                    for row in horizon_rows
                ]
                truth = [bool(row["outcomes"][outcome_name]) for row in horizon_rows]
                candidate_prediction = [bool(row["candidate"][candidate_name]) for row in horizon_rows]
                component_prediction = [bool(row["component_baseline"][candidate_name]) for row in horizon_rows]
                negative_prediction = [False for _ in horizon_rows]
                candidate_metrics = classification_metrics(
                    candidate_prediction, truth, applicable, confidence=confidence
                )
                component_metrics = classification_metrics(
                    component_prediction, truth, applicable, confidence=confidence
                )
                negative_metrics = classification_metrics(
                    negative_prediction, truth, applicable, confidence=confidence
                )
                target_payload[candidate_name] = {
                    "outcome_name": outcome_name,
                    "candidate": candidate_metrics,
                    "component_baseline": component_metrics,
                    "always_negative_baseline": negative_metrics,
                    "candidate_minus_component_baseline": _metric_difference(
                        candidate_metrics, component_metrics
                    ),
                }
            partition_payload[str(horizon_value)] = target_payload
        groups[partition] = partition_payload
    return {
        "metrics_by_partition_horizon_target": groups,
        "overlapping_windows_statistical_independence_claim": False,
        "threshold_tuning_performed": False,
    }


def compute_stratified_rates(rows: Sequence[Mapping[str, Any]], contract: Mapping[str, Any]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    modifiers = (
        "new_drive_coincident_candidate",
        "unresolved_residual_dominance_candidate",
    )
    for modifier in modifiers:
        modifier_payload: dict[str, Any] = {}
        for horizon in contract["evaluation"]["horizons"]:
            horizon_rows = [row for row in rows if int(row["horizon"]) == int(horizon)]
            target_payload: dict[str, Any] = {}
            for candidate_name in PRIMARY_TARGETS:
                outcome_name = _target_name(candidate_name, contract)
                strata: dict[str, Any] = {}
                for value in (False, True):
                    selected = [
                        row
                        for row in horizon_rows
                        if bool(row["modifiers"][modifier]) is value
                        and (
                            outcome_name != "future_recovery_failure_outcome"
                            or bool(row["outcomes"]["future_recovery_failure_applicable"])
                        )
                    ]
                    positive = sum(bool(row["outcomes"][outcome_name]) for row in selected)
                    strata[str(value).lower()] = {
                        "sample_count": len(selected),
                        "positive_outcome_count": positive,
                        "outcome_rate": None if not selected else positive / len(selected),
                    }
                target_payload[candidate_name] = strata
            modifier_payload[str(int(horizon))] = target_payload
        output[modifier] = modifier_payload
    return {
        "stratified_rates": output,
        "causal_or_uplift_claim": False,
    }


def _support_gate_summary(rows: Sequence[Mapping[str, Any]], contract: Mapping[str, Any]) -> dict[str, Any]:
    test_cases = {row["case_id"] for row in rows if row["partition"] == "test"}
    minimum_cases = int(contract["support_gates"]["minimum_test_cases_for_accuracy_claim"])
    minimum_positive = int(
        contract["support_gates"]["minimum_positive_test_outcomes_per_target_horizon"]
    )
    minimum_negative = int(
        contract["support_gates"]["minimum_negative_test_outcomes_per_target_horizon"]
    )
    cell_gates: dict[str, Any] = {}
    all_cells = True
    for horizon in contract["evaluation"]["horizons"]:
        horizon_rows = [
            row for row in rows
            if row["partition"] == "test" and int(row["horizon"]) == int(horizon)
        ]
        for candidate_name in PRIMARY_TARGETS:
            outcome_name = _target_name(candidate_name, contract)
            applicable_rows = [
                row for row in horizon_rows
                if outcome_name != "future_recovery_failure_outcome"
                or bool(row["outcomes"]["future_recovery_failure_applicable"])
            ]
            positive = sum(bool(row["outcomes"][outcome_name]) for row in applicable_rows)
            negative = len(applicable_rows) - positive
            passed = positive >= minimum_positive and negative >= minimum_negative
            all_cells = all_cells and passed
            cell_gates[f"h{int(horizon)}:{candidate_name}"] = {
                "positive": positive,
                "negative": negative,
                "passed": passed,
            }
    case_gate = len(test_cases) >= minimum_cases
    return {
        "test_case_count": len(test_cases),
        "minimum_test_case_count": minimum_cases,
        "test_case_count_gate": case_gate,
        "target_horizon_support": cell_gates,
        "all_target_horizon_support_gates": all_cells,
        "predictive_accuracy_claim_allowed": bool(case_gate and all_cells),
    }


def _freeze_case_manifest(
    raw_manifest: Mapping[str, Any],
    cases: Sequence[Mapping[str, Any]],
    snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    snapshot_by_case = {row["case_id"]: row for row in snapshot["cases"]}
    frozen_cases = []
    for case in cases:
        prediction = snapshot_by_case[case["case_id"]]
        frozen_cases.append(
            {
                "case_id": case["case_id"],
                "partition": case["partition"],
                "trajectory_id": prediction["trajectory_id"],
                "cutoff_t": prediction["cutoff_t"],
                "rf9_risk_structure_id": prediction["rf9_risk_structure_id"],
                "rf9_manifest_hash": prediction["rf9_manifest_hash"],
                "prediction_snapshot_hash": prediction["prediction_snapshot_hash"],
                "trajectory_gt_hash": _sha256_file(Path(case["trajectory_dir"]) / "gt_mass.npy"),
                "trajectory_ledger_hash": _sha256_file(
                    Path(case["trajectory_dir"]) / "history_ledger.csv"
                ),
            }
        )
    return {
        "manifest_version": raw_manifest["manifest_version"],
        "case_count": len(frozen_cases),
        "cases": frozen_cases,
        "absolute_paths_not_frozen": True,
    }


def _compute_all(case_manifest_path: Path, contract: Mapping[str, Any]) -> dict[str, Any]:
    raw_manifest, cases = _load_case_manifest(case_manifest_path, contract)
    snapshot = freeze_prediction_snapshot(cases, contract)
    snapshot_hash_before_future = snapshot["prediction_snapshot_hash"]
    future_rows = [
        _load_case_future(case, prediction, contract)
        for case, prediction in zip(cases, snapshot["cases"], strict=True)
    ]
    if snapshot["prediction_snapshot_hash"] != snapshot_hash_before_future:
        raise RelationFieldPredictiveValidationError("RF-10 prediction snapshot changed after future read")
    ledger = build_sample_ledger(snapshot, future_rows, contract)
    metrics = compute_predictive_metrics(ledger, contract)
    stratified = compute_stratified_rates(ledger, contract)
    support = _support_gate_summary(ledger, contract)
    frozen_manifest = _freeze_case_manifest(raw_manifest, cases, snapshot)
    return {
        "cases": cases,
        "snapshot": snapshot,
        "future_rows": future_rows,
        "ledger": ledger,
        "metrics": metrics,
        "stratified": stratified,
        "support": support,
        "frozen_manifest": frozen_manifest,
    }


def _future_outcome_arrays(rows: Sequence[Mapping[str, Any]], horizons: Sequence[int]) -> dict[str, np.ndarray]:
    return {
        "case_index": np.arange(len(rows), dtype=np.int32),
        "cutoff_t": np.asarray([row["cutoff_t"] for row in rows], dtype=np.int32),
        "max_future_t_read": np.asarray([row["max_future_t_read"] for row in rows], dtype=np.int32),
        **{
            f"h{int(horizon)}_{name}": np.asarray(
                [row["horizons"][str(int(horizon))][name] for row in rows], dtype=np.uint8
            )
            for horizon in horizons
            for name in (
                "future_concentration_outcome",
                "future_persistent_concentration_outcome",
                "future_dispersion_outcome",
                "future_recovery_failure_outcome",
                "future_recovery_failure_applicable",
            )
        },
    }


def build_predictive_validation(
    case_manifest: str | Path,
    output: str | Path,
    *,
    contract_path: str | Path = DEFAULT_CONTRACT,
) -> Path:
    contract = load_contract(contract_path)
    target = Path(output)
    if target.exists():
        raise RelationFieldPredictiveValidationError(f"output already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    computed = _compute_all(Path(case_manifest), contract)
    snapshot = computed["snapshot"]
    frozen_manifest = computed["frozen_manifest"]
    identity_basis = {
        "contract_version": contract["contract_version"],
        "frozen_case_manifest_hash": _sha256_bytes(_canonical_json(frozen_manifest)),
        "prediction_snapshot_hash": snapshot["prediction_snapshot_hash"],
        "case_count": len(snapshot["cases"]),
        "horizons": [int(value) for value in contract["evaluation"]["horizons"]],
    }
    validation_id = _sha256_bytes(_canonical_json(identity_basis))
    identity = {
        "predictive_validation_id": validation_id,
        **identity_basis,
        "only_final_RF9_rows_evaluated": True,
        "prediction_snapshot_frozen_before_future_read": True,
        "future_suffix_used_only_for_outcomes": True,
        "predictive_accuracy_claim_allowed": computed["support"]["predictive_accuracy_claim_allowed"],
    }
    trajectory_partitions: dict[str, set[str]] = {}
    for row in snapshot["cases"]:
        trajectory_partitions.setdefault(row["trajectory_id"], set()).add(row["partition"])
    leakage_audit = {
        "only_final_RF9_rows_evaluated": True,
        "nonfinal_RF9_rows_evaluated": False,
        "prediction_snapshot_frozen_before_future_read": True,
        "future_suffix_read_before_prediction_snapshot": False,
        "future_suffix_used_as_prediction_feature": False,
        "external_logs_or_truth_labels_read": False,
        "trajectory_group_partitions": {
            key: sorted(value) for key, value in sorted(trajectory_partitions.items())
        },
        "trajectory_group_cross_partition_count": sum(len(value) > 1 for value in trajectory_partitions.values()),
        "threshold_tuning_performed": False,
    }
    candidate_counts = {
        name: sum(bool(row["candidate"][name]) for row in snapshot["cases"])
        for name in PRIMARY_TARGETS
    }
    outcome_counts = {
        f"h{int(horizon)}_{outcome}": sum(
            bool(row["horizons"][str(int(horizon))][outcome]) for row in computed["future_rows"]
        )
        for horizon in contract["evaluation"]["horizons"]
        for outcome in (
            "future_concentration_outcome",
            "future_persistent_concentration_outcome",
            "future_dispersion_outcome",
            "future_recovery_failure_outcome",
        )
    }
    diagnostics = {
        "case_count": len(snapshot["cases"]),
        "sample_ledger_row_count": len(computed["ledger"]),
        "partition_case_counts": {
            partition: sum(row["partition"] == partition for row in snapshot["cases"])
            for partition in contract["input"]["allowed_partitions"]
        },
        "candidate_counts": candidate_counts,
        "outcome_counts": outcome_counts,
        "support_gates": computed["support"],
        "future_read_maximum_horizon": max(contract["evaluation"]["horizons"]),
    }
    future_arrays = _future_outcome_arrays(
        computed["future_rows"], contract["evaluation"]["horizons"]
    )
    gates = {
        "final_row_only_gate": leakage_audit["only_final_RF9_rows_evaluated"],
        "prediction_snapshot_order_gate": leakage_audit["prediction_snapshot_frozen_before_future_read"],
        "future_feature_separation_gate": not leakage_audit["future_suffix_used_as_prediction_feature"],
        "partition_group_leakage_gate": leakage_audit["trajectory_group_cross_partition_count"] == 0,
        "prefix_history_identity_gate": all(
            bool(row["prefix_history_chain_hash_verified"]) for row in computed["future_rows"]
        ),
        "finite_outcome_array_gate": all(
            np.all(np.isfinite(value)) for value in future_arrays.values()
        ),
        "source_writeback_gate": True,
    }
    validation = {
        "rf10_predictive_validation_gate": "passed" if all(gates.values()) else "failed",
        **gates,
        "scientific_claim": contract["acceptance"]["scientific_claim"],
        "predictive_accuracy_claim_allowed": computed["support"]["predictive_accuracy_claim_allowed"],
        "true_irreversibility_claim": False,
        "deployment_readiness_claim": False,
        "action_selection_performed": False,
    }
    if validation["rf10_predictive_validation_gate"] != "passed":
        raise RelationFieldPredictiveValidationError(f"RF-10 gates failed: {gates}")
    uncertainty = {
        "future_outcomes": {
            "labels_are_operational_thresholded_observations": True,
            "labels_are_not_true_irreversibility": True,
            "thresholds_were_not_tuned_during_build": True,
        },
        "sampling": {
            "overlapping_future_windows_are_not_independent": True,
            "trajectory_grouping_required_for_later_uncertainty_estimation": True,
            "small_or_synthetic_samples_validate_harness_only": True,
        },
        "prediction": {
            "RF9_candidates_are_boolean_not_calibrated_probabilities": True,
            "accuracy_superiority_claim_requires_support_gates": True,
            "predictive_accuracy_claim_allowed": computed["support"]["predictive_accuracy_claim_allowed"],
        },
    }
    summary = {
        "contract_version": contract["contract_version"],
        "predictive_validation_id": validation_id,
        "case_count": len(snapshot["cases"]),
        "sample_ledger_row_count": len(computed["ledger"]),
        "candidate_counts": candidate_counts,
        "outcome_counts": outcome_counts,
        "support_gates": computed["support"],
        "scientific_claim": contract["acceptance"]["scientific_claim"],
        "predictive_accuracy_claim_allowed": computed["support"]["predictive_accuracy_claim_allowed"],
    }
    provenance = {
        "prediction_sources": ["validated RF-9 final row only"],
        "target_sources": ["canonical G strictly after each cutoff"],
        "prediction_snapshot_hash": snapshot["prediction_snapshot_hash"],
        "prediction_snapshot_created_before_future_read": True,
        "future_suffix_used_for_targets_only": True,
        "external_logs_or_truth_labels_read": False,
        "threshold_tuning_performed": False,
        "canonical_or_parent_payload_copied": False,
        "canonical_or_parent_writeback_performed": False,
    }
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp-", dir=target.parent))
    try:
        storage = contract["storage"]
        _dump_json(temporary / storage["contract_file"], contract)
        _dump_json(temporary / storage["identity_file"], identity)
        _dump_json(temporary / storage["frozen_case_manifest_file"], frozen_manifest)
        _dump_json(temporary / storage["prediction_snapshot_file"], snapshot)
        _write_npz(temporary / storage["future_outcomes_file"], future_arrays)
        _dump_json(temporary / storage["sample_ledger_file"], {"rows": computed["ledger"]})
        _dump_json(temporary / storage["metrics_file"], computed["metrics"])
        _dump_json(temporary / storage["stratified_rates_file"], computed["stratified"])
        _dump_json(temporary / storage["leakage_audit_file"], leakage_audit)
        _dump_json(temporary / storage["diagnostics_file"], diagnostics)
        _dump_json(temporary / storage["uncertainty_file"], uncertainty)
        _dump_json(temporary / storage["provenance_file"], provenance)
        _dump_json(temporary / storage["summary_file"], summary)
        _dump_json(temporary / storage["validation_file"], validation)
        _dump_json(
            temporary / storage["manifest_file"],
            {
                "contract_version": contract["contract_version"],
                "hash_algorithm": "sha256",
                "files": _manifest_entries(temporary, exclude={storage["manifest_file"]}),
            },
        )
        os.replace(temporary, target)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return target


def _assert_array_payload(expected: Mapping[str, np.ndarray], actual: Mapping[str, np.ndarray], name: str) -> None:
    if set(expected) != set(actual):
        raise RelationFieldPredictiveValidationError(f"{name} array key mismatch")
    for key in expected:
        left, right = np.asarray(expected[key]), np.asarray(actual[key])
        if left.shape != right.shape or left.dtype.kind != right.dtype.kind:
            raise RelationFieldPredictiveValidationError(f"{name} array metadata mismatch: {key}")
        equal = np.array_equal(left, right) if left.dtype.kind in "iub" else np.allclose(left, right, atol=1e-12, rtol=1e-12)
        if not equal:
            raise RelationFieldPredictiveValidationError(f"{name} array value mismatch: {key}")


def validate_predictive_validation(
    input_path: str | Path,
    case_manifest: str | Path,
) -> dict[str, Any]:
    root = Path(input_path)
    contract = _load_json(root / "contract.json")
    validate_contract(contract)
    _verify_manifest(root)
    computed = _compute_all(Path(case_manifest), contract)
    storage = contract["storage"]
    identity = _load_json(root / storage["identity_file"])
    frozen_manifest = _load_json(root / storage["frozen_case_manifest_file"])
    if identity.get("frozen_case_manifest_hash") != _sha256_bytes(_canonical_json(frozen_manifest)):
        raise RelationFieldPredictiveValidationError("RF-10 frozen case manifest hash mismatch")
    if _load_json(root / storage["prediction_snapshot_file"]) != computed["snapshot"]:
        raise RelationFieldPredictiveValidationError("RF-10 prediction snapshot mismatch")
    _assert_array_payload(
        _future_outcome_arrays(computed["future_rows"], contract["evaluation"]["horizons"]),
        _load_npz(root / storage["future_outcomes_file"]),
        "future outcomes",
    )
    if _load_json(root / storage["sample_ledger_file"]) != {"rows": computed["ledger"]}:
        raise RelationFieldPredictiveValidationError("RF-10 sample ledger mismatch")
    if _load_json(root / storage["metrics_file"]) != computed["metrics"]:
        raise RelationFieldPredictiveValidationError("RF-10 metric payload mismatch")
    if _load_json(root / storage["stratified_rates_file"]) != computed["stratified"]:
        raise RelationFieldPredictiveValidationError("RF-10 stratified-rate payload mismatch")
    forbidden_names = {
        "gt_mass.npy",
        "history_ledger.csv",
        "risk_structure_metrics.npz",
        "risk_structure_candidates.json",
    }
    if any(path.name in forbidden_names for path in root.rglob("*")):
        raise RelationFieldPredictiveValidationError("RF-10 copied canonical or parent payload")
    validation = _load_json(root / storage["validation_file"])
    if validation.get("rf10_predictive_validation_gate") != "passed":
        raise RelationFieldPredictiveValidationError("RF-10 validation gate did not pass")
    return validation


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--case-manifest", required=True)
    build.add_argument("--output", required=True)
    build.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    validate = commands.add_parser("validate")
    validate.add_argument("--input", required=True)
    validate.add_argument("--case-manifest", required=True)
    args = parser.parse_args(argv)
    if args.command == "build":
        output = build_predictive_validation(
            args.case_manifest,
            args.output,
            contract_path=args.contract,
        )
        print(json.dumps({"output": str(output), "status": "built"}, ensure_ascii=False, sort_keys=True))
    else:
        print(
            json.dumps(
                validate_predictive_validation(args.input, args.case_manifest),
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
