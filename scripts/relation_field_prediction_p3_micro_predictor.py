"""P3-3: 共通ミクロ流れ情報から1ステップ先の流れとGを予測する。

A: 現在流れ継続
B: 加速度補正
C: 局所結合補正

疑似現実系の内部状態、未来情報、RF-10、truthは読まない。
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from relation_field_prediction_p3_connection_check import inspect_gk_connection  # noqa: E402
from relation_field_prediction_p3_flow_translation import (  # noqa: E402
    CELL_COUNT,
    GT_SHAPE,
    _load_current_gt,
    _load_grid,
)

DEFAULT_CONFIG = ROOT / "configs" / "relation_field_prediction_p3_prototype.json"
MODEL_NAMES = ("continuation", "acceleration", "local_coupling")


class P3MicroPredictionError(ValueError):
    """P3-3入力、予測、輸送制約の不整合。"""


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise P3MicroPredictionError(f"JSONL row {line_number} is not an object")
            rows.append(value)
    return rows


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def _write_npz(path: Path, arrays: Mapping[str, np.ndarray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(path, **{key: np.asarray(value) for key, value in arrays.items()})


def load_config(path: str | Path = DEFAULT_CONFIG) -> dict[str, Any]:
    config = _load_json(Path(path))
    if tuple(config.get("models", [])) != MODEL_NAMES:
        raise P3MicroPredictionError("P3-3 model order must remain continuation, acceleration, local_coupling")
    prediction = config.get("prediction", {})
    constraints = config.get("constraints", {})
    required_prediction = {
        "acceleration_weight",
        "acceleration_cap_ratio",
        "local_coupling_weight",
        "local_coupling_cap_ratio",
        "minimum_flow_scale",
    }
    required_constraints = {"flow_threshold", "mass_tolerance", "nonnegative_tolerance"}
    if required_prediction - set(prediction) or required_constraints - set(constraints):
        raise P3MicroPredictionError("P3-3 config is incomplete")
    numeric = [float(prediction[name]) for name in required_prediction]
    numeric += [float(constraints[name]) for name in required_constraints]
    if not all(np.isfinite(value) and value >= 0.0 for value in numeric):
        raise P3MicroPredictionError("P3-3 settings must be finite and nonnegative")
    scope = config.get("scope", {})
    if scope.get("prediction_horizon_steps") != 1:
        raise P3MicroPredictionError("P3-3 prototype predicts exactly one step")
    if scope.get("future_information_allowed") is not False:
        raise P3MicroPredictionError("future information must remain forbidden")
    if scope.get("pseudo_reality_internal_state_allowed") is not False:
        raise P3MicroPredictionError("pseudo-reality internal state must remain forbidden")
    return config


def load_translation_artifact(path: str | Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    root = Path(path)
    required = {
        "identity.json",
        "micro_flows.jsonl",
        "residual_context.json",
        "summary.json",
        "validation.json",
        "provenance.json",
    }
    missing = sorted(name for name in required if not (root / name).is_file())
    if missing:
        raise P3MicroPredictionError(f"P3-2 artifact is missing: {missing}")
    identity = _load_json(root / "identity.json")
    validation = _load_json(root / "validation.json")
    provenance = _load_json(root / "provenance.json")
    if validation.get("p3_2_translation_gate") != "passed":
        raise P3MicroPredictionError("P3-2 translation gate did not pass")
    if identity.get("prediction_performed") is not False:
        raise P3MicroPredictionError("P3-2 artifact must remain pre-prediction")
    if identity.get("future_information_read") is not False:
        raise P3MicroPredictionError("P3-2 artifact reports future information read")
    if identity.get("pseudo_reality_internal_state_read") is not False:
        raise P3MicroPredictionError("P3-2 artifact reports pseudo-reality internal state read")
    if provenance.get("future_suffix_read") is not False or provenance.get("truth_files_read") is not False:
        raise P3MicroPredictionError("P3-2 provenance violates prediction boundary")
    rows = _read_jsonl(root / "micro_flows.jsonl")
    if not rows:
        raise P3MicroPredictionError("P3-2 micro-flow rows are empty")
    edge_ids = [int(row["canonical_edge_id"]) for row in rows]
    if len(edge_ids) != len(set(edge_ids)):
        raise P3MicroPredictionError("P3-2 contains duplicate fixed-edge rows")
    if any(row.get("prediction_performed") is not False for row in rows):
        raise P3MicroPredictionError("P3-2 row already contains prediction")
    return identity, rows


def _mean_or_zero(values: list[float]) -> float:
    return 0.0 if not values else float(np.mean(np.asarray(values, dtype=np.float64)))


def predict_raw_edge_flows(
    rows: Sequence[Mapping[str, Any]],
    edge_count: int,
    config: Mapping[str, Any],
) -> dict[str, np.ndarray]:
    """A/B/Cの制約前の辺流量と各寄与を生成する。"""
    settings = config["prediction"]
    current = np.zeros(edge_count, dtype=np.float64)
    change = np.zeros(edge_count, dtype=np.float64)
    width = np.zeros(edge_count, dtype=np.float64)
    direction = np.zeros(edge_count, dtype=np.int8)
    row_by_edge: dict[int, Mapping[str, Any]] = {}
    for row in rows:
        edge = int(row["canonical_edge_id"])
        if edge < 0 or edge >= edge_count:
            raise P3MicroPredictionError("translated edge id is outside RF-2 grid")
        row_by_edge[edge] = row
        current[edge] = float(row["current_flow"])
        change[edge] = float(row["flow_change"])
        width[edge] = float(row["candidate_width"])
        direction[edge] = int(row["current_direction"])
    if not np.all(np.isfinite(current)) or not np.all(np.isfinite(change)):
        raise P3MicroPredictionError("translated flow contains non-finite values")
    if np.any(width < -1e-15) or not np.all(np.isfinite(width)):
        raise P3MicroPredictionError("candidate width is invalid")

    minimum_scale = float(settings["minimum_flow_scale"])
    acceleration_scale = np.maximum(np.maximum(np.abs(current), width), minimum_scale)
    acceleration_limit = float(settings["acceleration_cap_ratio"]) * acceleration_scale
    clipped_change = np.clip(change, -acceleration_limit, acceleration_limit)
    acceleration_contribution = float(settings["acceleration_weight"]) * clipped_change

    continuation = current.copy()
    acceleration = current + acceleration_contribution

    local_support = np.zeros(edge_count, dtype=np.float64)
    local_competition = np.zeros(edge_count, dtype=np.float64)
    local_coupling_contribution = np.zeros(edge_count, dtype=np.float64)
    local_raw = np.zeros(edge_count, dtype=np.float64)

    for edge, row in row_by_edge.items():
        flow_direction = int(direction[edge])
        if flow_direction == 0:
            candidate_mean = float(row.get("candidate_flow_mean", 0.0))
            flow_direction = 1 if candidate_mean > 0.0 else (-1 if candidate_mean < 0.0 else 0)
        source = row.get("source_cell_id")
        target = row.get("target_cell_id")
        if flow_direction == 0 or source is None or target is None:
            continue
        source_id = int(source)
        target_id = int(target)
        supportive: list[float] = []
        competing: list[float] = []
        for neighbor_id_value in row.get("adjacent_active_edge_ids", []):
            neighbor_id = int(neighbor_id_value)
            neighbor = row_by_edge.get(neighbor_id)
            if neighbor is None:
                continue
            neighbor_source = neighbor.get("source_cell_id")
            neighbor_target = neighbor.get("target_cell_id")
            if neighbor_source is None or neighbor_target is None:
                continue
            neighbor_amount = abs(float(neighbor["current_flow"]))
            if int(neighbor_target) == source_id or int(neighbor_source) == target_id:
                supportive.append(neighbor_amount)
            if int(neighbor_source) == source_id and int(neighbor_target) != target_id:
                competing.append(neighbor_amount)
        support = _mean_or_zero(supportive)
        competition = _mean_or_zero(competing)
        local_support[edge] = support
        local_competition[edge] = competition
        local_raw[edge] = support - competition
        correction_scale = max(abs(acceleration[edge]), abs(current[edge]), width[edge], minimum_scale)
        correction_cap = float(settings["local_coupling_cap_ratio"]) * correction_scale
        correction_magnitude = float(settings["local_coupling_weight"]) * local_raw[edge]
        correction_magnitude = float(np.clip(correction_magnitude, -correction_cap, correction_cap))
        local_coupling_contribution[edge] = flow_direction * correction_magnitude

    local_coupling = acceleration + local_coupling_contribution
    for name, values in {
        "continuation": continuation,
        "acceleration": acceleration,
        "local_coupling": local_coupling,
    }.items():
        if not np.all(np.isfinite(values)):
            raise P3MicroPredictionError(f"{name} produced non-finite edge flow")
    return {
        "current_flow": current,
        "flow_change": change,
        "candidate_width": width,
        "acceleration_change_clipped": clipped_change,
        "acceleration_contribution": acceleration_contribution,
        "local_support": local_support,
        "local_competition": local_competition,
        "local_coupling_raw": local_raw,
        "local_coupling_contribution": local_coupling_contribution,
        "raw_flow_continuation": continuation,
        "raw_flow_acceleration": acceleration,
        "raw_flow_local_coupling": local_coupling,
    }


def apply_transport_constraints(
    current_gt: np.ndarray,
    grid: Mapping[str, np.ndarray],
    raw_edge_flow: np.ndarray,
    *,
    flow_threshold: float,
    mass_tolerance: float,
    nonnegative_tolerance: float,
) -> dict[str, np.ndarray | float | int]:
    """出発セルの保有量を超える流出を比例縮小し、未来Gを生成する。"""
    current = np.asarray(current_gt, dtype=np.float64).reshape(-1)
    flow = np.asarray(raw_edge_flow, dtype=np.float64).reshape(-1)
    canonical_source = np.asarray(grid["edge_source"], dtype=np.int32)
    canonical_target = np.asarray(grid["edge_target"], dtype=np.int32)
    if current.size != CELL_COUNT:
        raise P3MicroPredictionError("current G_t cell count mismatch")
    if flow.shape != canonical_source.shape or flow.shape != canonical_target.shape:
        raise P3MicroPredictionError("edge-flow shape mismatch")
    if np.any(current < -nonnegative_tolerance) or not np.all(np.isfinite(current)):
        raise P3MicroPredictionError("current G_t is invalid")

    active = np.abs(flow) > flow_threshold
    directed_source = np.where(flow >= 0.0, canonical_source, canonical_target)
    directed_target = np.where(flow >= 0.0, canonical_target, canonical_source)
    amount = np.where(active, np.abs(flow), 0.0)
    outgoing = np.zeros(current.size, dtype=np.float64)
    np.add.at(outgoing, directed_source, amount)
    source_scale = np.ones(current.size, dtype=np.float64)
    constrained_sources = outgoing > current + mass_tolerance
    source_scale[constrained_sources] = np.divide(
        current[constrained_sources],
        outgoing[constrained_sources],
        out=np.zeros(np.count_nonzero(constrained_sources), dtype=np.float64),
        where=outgoing[constrained_sources] > 0.0,
    )
    edge_scale = np.where(active, source_scale[directed_source], 1.0)
    constrained_flow = flow * edge_scale
    constrained_amount = np.abs(constrained_flow)

    delta = np.zeros(current.size, dtype=np.float64)
    np.add.at(delta, directed_source, -constrained_amount)
    np.add.at(delta, directed_target, constrained_amount)
    predicted = current + delta
    minimum = float(np.min(predicted))
    if minimum < -nonnegative_tolerance:
        raise P3MicroPredictionError("transport constraints produced negative G_t")
    predicted[np.abs(predicted) <= nonnegative_tolerance] = 0.0
    mass_drift = float(np.sum(predicted, dtype=np.float64) - np.sum(current, dtype=np.float64))
    if abs(mass_drift) > mass_tolerance:
        raise P3MicroPredictionError("transport constraints violated mass preservation")
    if not np.all(np.isfinite(predicted)):
        raise P3MicroPredictionError("predicted G_t contains non-finite values")
    return {
        "constrained_flow": constrained_flow,
        "predicted_delta": delta,
        "predicted_gt": predicted,
        "edge_scale": edge_scale,
        "source_scale": source_scale,
        "constrained_source_count": int(np.count_nonzero(constrained_sources)),
        "constrained_edge_count": int(np.count_nonzero(edge_scale < 1.0 - 1e-15)),
        "raw_total_flow": float(np.sum(np.abs(flow), dtype=np.float64)),
        "constrained_total_flow": float(np.sum(np.abs(constrained_flow), dtype=np.float64)),
        "constraint_removed_flow": float(np.sum(np.abs(flow - constrained_flow), dtype=np.float64)),
        "moved_mass": float(0.5 * np.sum(np.abs(delta), dtype=np.float64)),
        "mass_drift": mass_drift,
        "minimum_predicted_mass": float(np.min(predicted)),
    }


def _prediction_rows(
    translation_rows: Sequence[Mapping[str, Any]],
    raw: Mapping[str, np.ndarray],
    constrained: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source_row in translation_rows:
        edge = int(source_row["canonical_edge_id"])
        rows.append({
            "flow_id": source_row["flow_id"],
            "canonical_edge_id": edge,
            "axis_index": int(source_row["axis_index"]),
            "axis_name": source_row["axis_name"],
            "current_flow": float(raw["current_flow"][edge]),
            "flow_change": float(raw["flow_change"][edge]),
            "acceleration_change_clipped": float(raw["acceleration_change_clipped"][edge]),
            "acceleration_contribution": float(raw["acceleration_contribution"][edge]),
            "local_support": float(raw["local_support"][edge]),
            "local_competition": float(raw["local_competition"][edge]),
            "local_coupling_raw": float(raw["local_coupling_raw"][edge]),
            "local_coupling_contribution": float(raw["local_coupling_contribution"][edge]),
            "continuation": {
                "raw_flow": float(raw["raw_flow_continuation"][edge]),
                "constrained_flow": float(constrained["continuation"]["constrained_flow"][edge]),
                "constraint_scale": float(constrained["continuation"]["edge_scale"][edge]),
            },
            "acceleration": {
                "raw_flow": float(raw["raw_flow_acceleration"][edge]),
                "constrained_flow": float(constrained["acceleration"]["constrained_flow"][edge]),
                "constraint_scale": float(constrained["acceleration"]["edge_scale"][edge]),
            },
            "local_coupling": {
                "raw_flow": float(raw["raw_flow_local_coupling"][edge]),
                "constrained_flow": float(constrained["local_coupling"]["constrained_flow"][edge]),
                "constraint_scale": float(constrained["local_coupling"]["edge_scale"][edge]),
            },
            "candidate_sign_ambiguous": bool(source_row["candidate_sign_ambiguous"]),
            "evidence": source_row["evidence"],
            "counterevidence": source_row["counterevidence"],
            "prediction_horizon_steps": 1,
        })
    return rows


def build_prediction_artifact(
    *,
    gk_trajectory_dir: str | Path,
    grid_artifact_dir: str | Path,
    translation_artifact_dir: str | Path,
    output_dir: str | Path,
    config_path: str | Path = DEFAULT_CONFIG,
) -> Path:
    target = Path(output_dir)
    if target.exists():
        raise P3MicroPredictionError(f"output already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    config = load_config(config_path)
    translation_identity, translation_rows = load_translation_artifact(translation_artifact_dir)
    cutoff_t = int(translation_identity["cutoff_t"])
    gk_root = Path(gk_trajectory_dir)
    snapshot = inspect_gk_connection(gk_root, cutoff_t)
    if snapshot["trajectory_id"] != translation_identity["trajectory_id"]:
        raise P3MicroPredictionError("P3-2 trajectory does not match G/K")
    if snapshot["current_gt_hash"] != translation_identity["source_gt_hash"]:
        raise P3MicroPredictionError("P3-2 source G_t hash does not match G/K")
    if snapshot["history_chain_hash"] != translation_identity["source_history_chain_hash"]:
        raise P3MicroPredictionError("P3-2 history chain does not match G/K")
    current_gt = _load_current_gt(gk_root, snapshot)
    grid = _load_grid(Path(grid_artifact_dir))
    edge_count = int(np.asarray(grid["edge_source"]).size)
    raw = predict_raw_edge_flows(translation_rows, edge_count, config)

    constraints = config["constraints"]
    constrained: dict[str, dict[str, Any]] = {}
    raw_keys = {
        "continuation": "raw_flow_continuation",
        "acceleration": "raw_flow_acceleration",
        "local_coupling": "raw_flow_local_coupling",
    }
    for model, key in raw_keys.items():
        constrained[model] = apply_transport_constraints(
            current_gt,
            grid,
            raw[key],
            flow_threshold=float(constraints["flow_threshold"]),
            mass_tolerance=float(constraints["mass_tolerance"]),
            nonnegative_tolerance=float(constraints["nonnegative_tolerance"]),
        )

    prediction_rows = _prediction_rows(translation_rows, raw, constrained)
    arrays: dict[str, np.ndarray] = {
        key: np.asarray(value) for key, value in raw.items()
    }
    for model in MODEL_NAMES:
        arrays[f"constrained_flow_{model}"] = np.asarray(constrained[model]["constrained_flow"])
        arrays[f"predicted_delta_{model}"] = np.asarray(constrained[model]["predicted_delta"]).reshape(GT_SHAPE, order="C")
        arrays[f"predicted_gt_{model}"] = np.asarray(constrained[model]["predicted_gt"]).reshape(GT_SHAPE, order="C")
        arrays[f"edge_constraint_scale_{model}"] = np.asarray(constrained[model]["edge_scale"])

    identity = {
        "task_id": "P3-3",
        "status": "predicted",
        "contract_version": config["contract_version"],
        "trajectory_id": snapshot["trajectory_id"],
        "cutoff_t": cutoff_t,
        "prediction_target_t": cutoff_t + 1,
        "prediction_horizon_steps": 1,
        "source_gt_hash": snapshot["current_gt_hash"],
        "source_history_chain_hash": snapshot["history_chain_hash"],
        "source_translation_task": translation_identity["task_id"],
        "source_rf3_relation_field_id": translation_identity["rf3_relation_field_id"],
        "source_rf5_relation_field_id": translation_identity["rf5_relation_field_id"],
        "source_rf8_axis_coupling_innovation_id": translation_identity.get("rf8_axis_coupling_innovation_id"),
        "maximum_source_t_read": cutoff_t,
        "future_information_read": False,
        "pseudo_reality_internal_state_read": False,
        "rf10_or_truth_read": False,
        "source_writeback_performed": False,
        "prediction_performed": True,
    }
    model_summary = {
        model: {
            "raw_total_flow": constrained[model]["raw_total_flow"],
            "constrained_total_flow": constrained[model]["constrained_total_flow"],
            "constraint_removed_flow": constrained[model]["constraint_removed_flow"],
            "constrained_source_count": constrained[model]["constrained_source_count"],
            "constrained_edge_count": constrained[model]["constrained_edge_count"],
            "moved_mass": constrained[model]["moved_mass"],
            "mass_drift": constrained[model]["mass_drift"],
            "minimum_predicted_mass": constrained[model]["minimum_predicted_mass"],
        }
        for model in MODEL_NAMES
    }
    summary = {
        "translated_active_flow_count": len(translation_rows),
        "edge_count": edge_count,
        "models": model_summary,
        "acceleration_contribution_l1": float(np.sum(np.abs(raw["acceleration_contribution"]), dtype=np.float64)),
        "local_coupling_contribution_l1": float(np.sum(np.abs(raw["local_coupling_contribution"]), dtype=np.float64)),
        "rf8_coupling_matrix_used_as_causal_coefficient": False,
        "new_edge_activation_predicted": False,
        "accuracy_evaluated": False,
    }
    mass_tolerance = float(constraints["mass_tolerance"])
    validation = {
        "p3_3_micro_prediction_gate": "passed",
        "all_models_generated": set(model_summary) == set(MODEL_NAMES),
        "all_predicted_distributions_nonnegative": all(
            constrained[model]["minimum_predicted_mass"] >= -float(constraints["nonnegative_tolerance"])
            for model in MODEL_NAMES
        ),
        "all_predicted_distributions_mass_preserving": all(
            abs(float(constrained[model]["mass_drift"])) <= mass_tolerance
            for model in MODEL_NAMES
        ),
        "source_capacity_constraints_applied": True,
        "causal_cutoff_respected": identity["maximum_source_t_read"] == cutoff_t,
        "future_information_read": False,
        "pseudo_reality_internal_state_read": False,
        "source_writeback_performed": False,
        "accuracy_evaluated": False,
    }

    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp-", dir=target.parent))
    try:
        _dump_json(temporary / "contract.json", config)
        _dump_json(temporary / "identity.json", identity)
        _write_npz(temporary / "predictions.npz", arrays)
        _write_jsonl(temporary / "flow_predictions.jsonl", prediction_rows)
        _dump_json(temporary / "summary.json", summary)
        _dump_json(temporary / "validation.json", validation)
        _dump_json(temporary / "provenance.json", {
            "source_files_read": [
                "gt_mass.npy:selected_cutoff_row_only",
                "history_ledger.csv:prefix_through_cutoff_t",
                "RF-2/incidence.npz",
                "P3-2/identity.json",
                "P3-2/micro_flows.jsonl",
                "P3-2/validation.json",
                "P3-2/provenance.json",
            ],
            "future_suffix_read": False,
            "truth_files_read": False,
            "external_logs_read": False,
            "pseudo_reality_internal_state_read": False,
            "source_writeback_performed": False,
        })
        os.replace(temporary, target)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return target


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gk-trajectory", required=True)
    parser.add_argument("--grid-artifact", required=True)
    parser.add_argument("--translation-artifact", required=True)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    output = build_prediction_artifact(
        gk_trajectory_dir=args.gk_trajectory,
        grid_artifact_dir=args.grid_artifact,
        translation_artifact_dir=args.translation_artifact,
        config_path=args.config,
        output_dir=args.output,
    )
    print(json.dumps({"status": "predicted", "output": output.as_posix()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
