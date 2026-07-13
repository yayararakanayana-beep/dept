from __future__ import annotations

import copy
import shutil
import tempfile
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from .common import (
    RelationFieldPredictionP2PrecursorAuditError,
    canonical_digest,
    dump_json,
    load_json,
    resolve_case_manifest,
    sha256_file,
    tree_hash,
    write_manifest,
)
from .decision import phase3_decision, support_audit
from .metrics import deterministic_permutation, metric_record


def _lazy_dependencies() -> dict[str, Any]:
    try:
        from relation_field_hodge_decomposition_rc1 import _load_grid_with_indices
        from relation_field_prediction_coordinates_p2 import validate_relation_field_prediction_coordinates
        from relation_field_prediction_coordinates_p2._common import load_npz
        from relation_field_predictive_validation_rc1 import (
            compute_frame_metrics,
            compute_future_outcomes,
            load_contract as load_rf10_contract,
        )
        from relation_field_single_transition_rc1 import load_contract as load_rf3_contract
        from relation_field_temporal_consistency_rc1 import _load_history_window
    except Exception as exc:
        raise RelationFieldPredictionP2PrecursorAuditError(
            f"P2-4 repository dependency unavailable: {exc}"
        ) from exc
    return {
        "load_grid": _load_grid_with_indices,
        "validate_p2": validate_relation_field_prediction_coordinates,
        "load_npz": load_npz,
        "compute_frame_metrics": compute_frame_metrics,
        "compute_future_outcomes": compute_future_outcomes,
        "load_rf10_contract": load_rf10_contract,
        "load_rf3_contract": load_rf3_contract,
        "load_history": _load_history_window,
    }


def _origin_dir(p2_root: Path, cutoff_t: int, contract: Mapping[str, Any]) -> Path:
    storage = contract["storage"]
    return p2_root / str(storage["origin_container_dir"]) / str(storage["origin_name_format"]).format(origin_t=int(cutoff_t))


def _scalar(arrays: Mapping[str, np.ndarray], key: str) -> float | None:
    if key not in arrays:
        return None
    value = np.asarray(arrays[key], dtype=np.float64)
    if value.shape != () or not np.isfinite(value.item()):
        return None
    return float(value.item())


def _coordinate_triplet(arrays: Mapping[str, np.ndarray], coordinate_id: str) -> dict[str, float] | None:
    values = {part: _scalar(arrays, f"{coordinate_id}__{part}") for part in ("lower", "center", "upper")}
    if any(value is None for value in values.values()):
        return None
    return {key: float(value) for key, value in values.items() if value is not None}


def _compose_components(values: Sequence[float | None], mode: str) -> float | None:
    if any(value is None for value in values):
        return None
    numeric = [float(value) for value in values if value is not None]
    if mode == "identity" and len(numeric) == 1:
        return numeric[0]
    if mode == "minimum" and numeric:
        return min(numeric)
    raise RelationFieldPredictionP2PrecursorAuditError(f"P2-4 unsupported component composition: {mode}")


def _snapshot_case(case: Mapping[str, Any], contract: Mapping[str, Any], dependencies: Mapping[str, Any], validation_cache: dict[tuple[str, str], dict[str, Any]]) -> dict[str, Any]:
    p1_root = Path(case["p1_series_dir"])
    p2_root = Path(case["p2_series_dir"])
    cache_key = (str(p1_root), str(p2_root))
    if cache_key not in validation_cache:
        validation_cache[cache_key] = dependencies["validate_p2"](p2_root, p1_root)
    p2_contract = load_json(p2_root / "contract.json")
    if p2_contract.get("contract_version") != contract["parents"]["p2_contract_version"]:
        raise RelationFieldPredictionP2PrecursorAuditError("P2-4 parent P2 contract mismatch")
    origin = _origin_dir(p2_root, int(case["cutoff_t"]), p2_contract)
    if not origin.is_dir():
        raise RelationFieldPredictionP2PrecursorAuditError(f"P2-4 cutoff origin missing: {case['case_id']}")
    storage = p2_contract["storage"]
    coordinates = dependencies["load_npz"](origin / str(storage["coordinate_file"]))
    first = dependencies["load_npz"](origin / str(storage["first_difference_file"]))
    second = dependencies["load_npz"](origin / str(storage["second_difference_file"]))
    risk = load_json(origin / str(storage["risk_structure_file"]))
    risk_by_id = {str(row["risk_structure_id"]): row for row in risk["records"]}
    scores: dict[str, dict[str, float | None]] = {}
    intervals: dict[str, dict[str, float] | None] = {}
    for target_id, target in contract["targets"].items():
        coordinate_id = str(target["structure_coordinate_id"])
        intervals[target_id] = _coordinate_triplet(coordinates, coordinate_id)
        center = None if intervals[target_id] is None else intervals[target_id]["center"]
        component_values = [_scalar(coordinates, f"{coordinate_id_value}__center") for coordinate_id_value in target["component_coordinate_ids"]]
        p1_record = risk_by_id.get(target_id)
        scores[target_id] = {
            "p2_structure_margin": center,
            "p2_structure_margin_first_difference": _scalar(first, f"{coordinate_id}__center"),
            "p2_structure_margin_second_difference": _scalar(second, f"{coordinate_id}__center"),
            "p2_component_only_margin": _compose_components(component_values, str(target["component_composition"])),
            "p1_boolean_candidate": None if p1_record is None else float(bool(p1_record["p1_current_candidate"])),
            "always_negative": 0.0,
        }
    applicability: dict[str, float | None] = {}
    for coordinate_id in contract["applicability_stratification"]["coordinate_ids"]:
        applicability[coordinate_id] = _scalar(coordinates, f"{coordinate_id}__center")
    prefix_root = Path(case["prefix_trajectory_dir"])
    return {
        "case_id": str(case["case_id"]),
        "partition": str(case["partition"]),
        "trajectory_group_id": str(case["trajectory_group_id"]),
        "cutoff_t": int(case["cutoff_t"]),
        "prediction_scores": scores,
        "structure_intervals": intervals,
        "applicability": applicability,
        "p1_tree_hash": tree_hash(p1_root),
        "p2_tree_hash": tree_hash(p2_root),
        "prefix_trajectory_tree_hash": tree_hash(prefix_root),
        "p2_origin_manifest_sha256": sha256_file(origin / "manifest.json"),
        "future_suffix_read_before_snapshot": False,
    }


def freeze_prediction_snapshot(cases: Sequence[Mapping[str, Any]], contract: Mapping[str, Any]) -> dict[str, Any]:
    dependencies = _lazy_dependencies()
    validation_cache: dict[tuple[str, str], dict[str, Any]] = {}
    rows = [_snapshot_case(case, contract, dependencies, validation_cache) for case in cases]
    payload = {
        "contract_version": contract["contract_version"],
        "prediction_snapshot_frozen_before_full_trajectory_read": True,
        "future_suffix_read_before_snapshot": False,
        "cases": rows,
    }
    payload["prediction_snapshot_hash"] = canonical_digest(payload)
    return payload


def _future_case(case: Mapping[str, Any], snapshot: Mapping[str, Any], contract: Mapping[str, Any], dependencies: Mapping[str, Any], rf10_contract: Mapping[str, Any]) -> dict[str, Any]:
    cutoff_t = int(case["cutoff_t"])
    max_horizon = max(int(value) for value in contract["evaluation"]["horizons"])
    rf3 = dependencies["load_rf3_contract"]()
    tolerance = float(rf3["input"]["distribution_mass_tolerance"])
    prefix = dependencies["load_history"](Path(case["prefix_trajectory_dir"]), start_t=0, to_t=cutoff_t, mass_tolerance=tolerance, minimum_transition_count=1)
    full_prefix = dependencies["load_history"](Path(case["full_trajectory_dir"]), start_t=0, to_t=cutoff_t, mass_tolerance=tolerance, minimum_transition_count=1)
    if prefix["trajectory_id"] != full_prefix["trajectory_id"]:
        raise RelationFieldPredictionP2PrecursorAuditError("P2-4 prefix/full trajectory identity mismatch")
    if len(prefix["frames"]) != len(full_prefix["frames"]) or any(not np.array_equal(left, right) for left, right in zip(prefix["frames"], full_prefix["frames"])):
        raise RelationFieldPredictionP2PrecursorAuditError("P2-4 full trajectory prefix differs from frozen prediction prefix")
    if tree_hash(Path(case["prefix_trajectory_dir"])) != snapshot["prefix_trajectory_tree_hash"]:
        raise RelationFieldPredictionP2PrecursorAuditError("P2-4 prefix trajectory changed after snapshot")
    history = dependencies["load_history"](Path(case["full_trajectory_dir"]), start_t=cutoff_t, to_t=cutoff_t + max_horizon, mass_tolerance=tolerance, minimum_transition_count=max_horizon)
    grid = dependencies["load_grid"](Path(case["grid_artifact_dir"]))
    frame_metrics = [dependencies["compute_frame_metrics"](frame, grid) for frame in history["frames"]]
    horizons: dict[str, Any] = {}
    for horizon in contract["evaluation"]["horizons"]:
        horizon_value = int(horizon)
        horizons[str(horizon_value)] = dependencies["compute_future_outcomes"](frame_metrics[: horizon_value + 1], horizon_value, rf10_contract["future_outcomes"])
    return {
        "case_id": str(case["case_id"]),
        "trajectory_group_id": str(case["trajectory_group_id"]),
        "partition": str(case["partition"]),
        "cutoff_t": cutoff_t,
        "max_future_t_read": cutoff_t + max_horizon,
        "full_trajectory_tree_hash": tree_hash(Path(case["full_trajectory_dir"])),
        "prefix_frames_equal": True,
        "horizons": horizons,
    }


def read_future_outcomes(cases: Sequence[Mapping[str, Any]], snapshot: Mapping[str, Any], contract: Mapping[str, Any]) -> dict[str, Any]:
    dependencies = _lazy_dependencies()
    rf10_contract = dependencies["load_rf10_contract"]()
    if rf10_contract.get("contract_version") != contract["parents"]["rf10_contract_version"]:
        raise RelationFieldPredictionP2PrecursorAuditError("P2-4 RF-10 contract mismatch")
    if [int(value) for value in rf10_contract["evaluation"]["horizons"]] != [int(value) for value in contract["evaluation"]["horizons"]]:
        raise RelationFieldPredictionP2PrecursorAuditError("P2-4 RF-10 horizons changed")
    frozen = {str(row["case_id"]): row for row in snapshot["cases"]}
    rows = [_future_case(case, frozen[str(case["case_id"])], contract, dependencies, rf10_contract) for case in cases]
    return {
        "rf10_contract_version": rf10_contract["contract_version"],
        "rf10_contract_hash": canonical_digest(rf10_contract),
        "prediction_snapshot_hash": snapshot["prediction_snapshot_hash"],
        "future_read_started_after_snapshot": True,
        "cases": rows,
    }


def _sample_rows(snapshot: Mapping[str, Any], futures: Mapping[str, Any], contract: Mapping[str, Any]) -> list[dict[str, Any]]:
    future_by_id = {str(row["case_id"]): row for row in futures["cases"]}
    rows: list[dict[str, Any]] = []
    for frozen in snapshot["cases"]:
        future = future_by_id[str(frozen["case_id"])]
        for horizon in contract["evaluation"]["horizons"]:
            horizon_payload = future["horizons"][str(int(horizon))]
            for target_id, target in contract["targets"].items():
                applicable_field = target.get("rf10_applicability_field")
                applicable = True if applicable_field is None else bool(horizon_payload[applicable_field])
                rows.append({
                    "case_id": frozen["case_id"],
                    "partition": frozen["partition"],
                    "trajectory_group_id": frozen["trajectory_group_id"],
                    "cutoff_t": frozen["cutoff_t"],
                    "horizon": int(horizon),
                    "target_id": target_id,
                    "outcome": bool(horizon_payload[target["rf10_outcome_field"]]),
                    "applicable": applicable,
                    "scores": copy.deepcopy(frozen["prediction_scores"][target_id]),
                    "structure_interval": copy.deepcopy(frozen["structure_intervals"][target_id]),
                    "applicability_coordinates": copy.deepcopy(frozen["applicability"]),
                })
    for partition in contract["input"]["allowed_partitions"]:
        for horizon in contract["evaluation"]["horizons"]:
            for target_id in sorted(contract["targets"]):
                selected = [row for row in rows if row["partition"] == partition and row["horizon"] == int(horizon) and row["target_id"] == target_id and row["scores"]["p2_structure_margin"] is not None]
                permuted = deterministic_permutation([float(row["scores"]["p2_structure_margin"]) for row in selected], {"contract_version": contract["contract_version"], "partition": partition, "horizon": int(horizon), "target_id": target_id, "score_id": "p2_structure_margin_time_shuffled"})
                for row, value in zip(selected, permuted):
                    row["scores"]["p2_structure_margin_time_shuffled"] = value
    return rows


def _metrics(rows: Sequence[Mapping[str, Any]], contract: Mapping[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for partition in contract["input"]["allowed_partitions"]:
        for horizon in contract["evaluation"]["horizons"]:
            for target_id in sorted(contract["targets"]):
                for score_id in contract["score_panels"]:
                    records.append(metric_record(rows, partition=partition, horizon=int(horizon), target_id=target_id, score_id=score_id, contract=contract))
    return records


def _ablation(metrics: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    by_key = {(row["partition"], row["horizon"], row["target_id"], row["score_id"]): row for row in metrics}
    rows: list[dict[str, Any]] = []
    for key, primary in sorted(by_key.items()):
        partition, horizon, target_id, score_id = key
        if score_id != "p2_structure_margin":
            continue
        for comparison_id in ("p2_component_only_margin", "p1_boolean_candidate", "p2_structure_margin_time_shuffled", "always_negative"):
            comparison = by_key[(partition, horizon, target_id, comparison_id)]
            rows.append({
                "partition": partition,
                "horizon": horizon,
                "target_id": target_id,
                "comparison_score_id": comparison_id,
                "roc_auc_difference": None if primary["roc_auc"] is None or comparison["roc_auc"] is None else float(primary["roc_auc"] - comparison["roc_auc"]),
                "average_precision_difference": None if primary["average_precision"] is None or comparison["average_precision"] is None else float(primary["average_precision"] - comparison["average_precision"]),
                "superiority_claim": False,
            })
    return {"ablation_version": "relation_field_prediction_p2_precursor_ablation_v1", "rows": rows}


def _stratification(rows: Sequence[Mapping[str, Any]], contract: Mapping[str, Any]) -> dict[str, Any]:
    output: list[dict[str, Any]] = []
    for coordinate_id in contract["applicability_stratification"]["coordinate_ids"]:
        for target_id in sorted(contract["targets"]):
            for horizon in contract["evaluation"]["horizons"]:
                selected = [row for row in rows if row["target_id"] == target_id and row["horizon"] == int(horizon) and row.get("applicable", True) and row["applicability_coordinates"].get(coordinate_id) is not None]
                values = [float(row["applicability_coordinates"][coordinate_id]) for row in selected]
                median = None if not values else float(np.median(values))
                low = [] if median is None else [row for row in selected if float(row["applicability_coordinates"][coordinate_id]) <= median]
                high = [] if median is None else [row for row in selected if float(row["applicability_coordinates"][coordinate_id]) > median]
                output.append({
                    "coordinate_id": coordinate_id,
                    "target_id": target_id,
                    "horizon": int(horizon),
                    "sample_count": len(selected),
                    "median": median,
                    "lower_or_equal_outcome_rate": None if not low else float(np.mean([row["outcome"] for row in low])),
                    "upper_outcome_rate": None if not high else float(np.mean([row["outcome"] for row in high])),
                    "target_redefinition_performed": False,
                })
    return {"stratification_version": "relation_field_prediction_p2_precursor_stratification_v1", "rows": output}


def build_precursor_audit(case_manifest_path: str | Path, output: str | Path, *, contract: Mapping[str, Any]) -> Path:
    target = Path(output)
    if target.exists():
        raise RelationFieldPredictionP2PrecursorAuditError(f"output already exists: {target}")
    raw_manifest, cases = resolve_case_manifest(case_manifest_path, contract)
    source_roots = sorted({str(Path(case[field])) for case in cases for field in ("prefix_trajectory_dir", "full_trajectory_dir", "grid_artifact_dir", "p1_series_dir", "p2_series_dir")})
    before = {path: tree_hash(Path(path)) for path in source_roots}
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp-", dir=target.parent))
    try:
        dump_json(temporary / contract["storage"]["contract_file"], dict(contract))
        dump_json(temporary / contract["storage"]["frozen_case_manifest_file"], raw_manifest)
        snapshot = freeze_prediction_snapshot(cases, contract)
        dump_json(temporary / contract["storage"]["prediction_snapshot_file"], snapshot)
        futures = read_future_outcomes(cases, snapshot, contract)
        dump_json(temporary / contract["storage"]["future_outcomes_file"], futures)
        samples = _sample_rows(snapshot, futures, contract)
        dump_json(temporary / contract["storage"]["sample_ledger_file"], {"sample_ledger_version": "relation_field_prediction_p2_precursor_samples_v1", "prediction_snapshot_hash": snapshot["prediction_snapshot_hash"], "rows": samples})
        metrics = _metrics(samples, contract)
        dump_json(temporary / contract["storage"]["metrics_file"], {"metrics_version": "relation_field_prediction_p2_precursor_metrics_v1", "cross_target_aggregation_performed": False, "rows": metrics})
        support = support_audit(samples, contract)
        dump_json(temporary / contract["storage"]["support_file"], support)
        decision = phase3_decision(metrics, support, contract)
        decision.update({"precursor_accuracy_claim": False if decision["status"] == "blocked_support_insufficient" else None, "p3_predictor_fitted": False, "true_irreversibility_claim": False})
        dump_json(temporary / contract["storage"]["decision_file"], decision)
        dump_json(temporary / contract["storage"]["ablation_file"], _ablation(metrics))
        dump_json(temporary / contract["storage"]["stratification_file"], _stratification(samples, contract))
        dump_json(temporary / contract["storage"]["validation_file"], {
            "p2_4_audit_gate": "passed",
            "prediction_snapshot_frozen_before_future_read": True,
            "rf10_outcome_definitions_reused": True,
            "model_fitting_performed": False,
            "threshold_tuning_performed": False,
            "cross_target_aggregation_performed": False,
            "parent_writeback_performed": False,
            "independent_validator_available": True,
            "scientific_status": decision["status"],
        })
        write_manifest(temporary, "relation_field_prediction_p2_precursor_audit_v1")
        after = {path: tree_hash(Path(path)) for path in source_roots}
        if before != after:
            raise RelationFieldPredictionP2PrecursorAuditError("P2-4 source artifact was modified")
        temporary.rename(target)
        return target
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
