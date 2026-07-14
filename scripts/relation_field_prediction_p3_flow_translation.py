"""P3-2: G/K由来の関係場を共通ミクロ流れ情報へ翻訳する。

このモジュールは予測を行わない。P3-3が利用できるよう、RF-3・RF-5を
中心とする観測済み関係場を、固定位置の流れ単位と軸文脈へ翻訳する。
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

from relation_field_prediction_p3_connection_check import (  # noqa: E402
    inspect_gk_connection,
    inspect_rf3_connection,
)

AXIS_NAMES = (
    "resource_slack",
    "information_quality",
    "pressure",
    "exploration_room",
    "reversibility",
)
GT_SHAPE = (5, 5, 5, 5, 5)
CELL_COUNT = 3125
FLOW_THRESHOLD = 1e-12


class P3FlowTranslationError(ValueError):
    """P3-2入力、時間整列、翻訳成果物の不整合。"""


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def _load_npz(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as loaded:
        return {name: np.asarray(loaded[name]).copy() for name in loaded.files}


def _finite_or_none(value: float | np.floating[Any]) -> float | None:
    number = float(value)
    return number if np.isfinite(number) else None


def _sign(value: float, threshold: float = FLOW_THRESHOLD) -> int:
    if value > threshold:
        return 1
    if value < -threshold:
        return -1
    return 0


def _flow_state(previous: float, current: float, threshold: float = FLOW_THRESHOLD) -> str:
    previous_sign = _sign(previous, threshold)
    current_sign = _sign(current, threshold)
    if previous_sign == 0 and current_sign == 0:
        return "inactive"
    if previous_sign == 0:
        return "activated"
    if current_sign == 0:
        return "ceased"
    if previous_sign != current_sign:
        return "reversed"
    if abs(current) > abs(previous) + threshold:
        return "strengthened"
    if abs(current) < abs(previous) - threshold:
        return "weakened"
    return "persisted"


def _load_grid(grid_artifact_dir: Path) -> dict[str, np.ndarray]:
    incidence_path = grid_artifact_dir / "incidence.npz"
    if not incidence_path.is_file():
        raise P3FlowTranslationError("RF-2 incidence.npz is required")
    arrays = _load_npz(incidence_path)
    required = {"edge_source", "edge_target", "edge_axis"}
    missing = sorted(required - set(arrays))
    if missing:
        raise P3FlowTranslationError(f"RF-2 grid payload is missing: {missing}")
    source = np.asarray(arrays["edge_source"], dtype=np.int32)
    target = np.asarray(arrays["edge_target"], dtype=np.int32)
    axis = np.asarray(arrays["edge_axis"], dtype=np.int8)
    if source.shape != target.shape or source.shape != axis.shape or source.ndim != 1:
        raise P3FlowTranslationError("RF-2 edge arrays are inconsistent")
    if np.any(source < 0) or np.any(target < 0) or np.any(source >= CELL_COUNT) or np.any(target >= CELL_COUNT):
        raise P3FlowTranslationError("RF-2 edge cell index is outside fixed grid")
    if np.any(axis < 0) or np.any(axis >= len(AXIS_NAMES)):
        raise P3FlowTranslationError("RF-2 edge axis index is invalid")
    return {"edge_source": source, "edge_target": target, "edge_axis": axis}


def _load_current_gt(trajectory_dir: Path, snapshot: Mapping[str, Any]) -> np.ndarray:
    mass = np.load(trajectory_dir / "gt_mass.npy", mmap_mode="r", allow_pickle=False)
    index = int(snapshot["current_gt_row_index"])
    current = np.asarray(mass[index], dtype=np.float64)
    if current.shape != GT_SHAPE or not np.all(np.isfinite(current)) or float(current.min()) < 0.0:
        raise P3FlowTranslationError("current canonical G_t is invalid")
    return current.reshape(-1, order="C")


def _load_rf5(rf5_artifact_dir: Path, snapshot: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "identity.json",
        "candidate_flows.npz",
        "candidate_index.json",
        "temporal_paths.json",
        "representative_flow.npz",
        "common_structure.npz",
        "temporal_diagnostics.json",
        "uncertainty.json",
        "validation.json",
    }
    missing = sorted(name for name in required if not (rf5_artifact_dir / name).is_file())
    if missing:
        raise P3FlowTranslationError(f"RF-5 artifact is missing: {missing}")
    identity = _load_json(rf5_artifact_dir / "identity.json")
    validation = _load_json(rf5_artifact_dir / "validation.json")
    if validation.get("rf5_temporal_consistency_gate") != "passed":
        raise P3FlowTranslationError("RF-5 validation gate did not pass")
    expected = {
        "trajectory_id": snapshot["trajectory_id"],
        "to_t": snapshot["cutoff_t"],
        "max_source_t_read": snapshot["cutoff_t"],
        "source_history_chain_hash": snapshot["history_chain_hash"],
    }
    for key, value in expected.items():
        if identity.get(key) != value:
            raise P3FlowTranslationError(f"RF-5 identity mismatch: {key}")
    representative = _load_npz(rf5_artifact_dir / "representative_flow.npz")
    common = _load_npz(rf5_artifact_dir / "common_structure.npz")
    candidates = _load_npz(rf5_artifact_dir / "candidate_flows.npz")
    diagnostics = _load_json(rf5_artifact_dir / "temporal_diagnostics.json")
    uncertainty = _load_json(rf5_artifact_dir / "uncertainty.json")
    transition_times = np.asarray(representative["transition_times"], dtype=np.int32)
    representative_flow = np.asarray(representative["net_flow"], dtype=np.float64)
    offsets = np.asarray(candidates["candidate_offsets"], dtype=np.int32)
    candidate_flow = np.asarray(candidates["candidate_net_flow"], dtype=np.float64)
    candidate_residual = np.asarray(candidates["candidate_residual"], dtype=np.float64)
    if transition_times.ndim != 1 or transition_times.size < 2:
        raise P3FlowTranslationError("P3-2 requires at least two RF-5 transitions")
    if int(transition_times[-1]) != int(snapshot["cutoff_t"]):
        raise P3FlowTranslationError("RF-5 latest transition does not match cutoff_t")
    if representative_flow.shape[0] != transition_times.size:
        raise P3FlowTranslationError("RF-5 representative-flow time dimension mismatch")
    if offsets.shape != (transition_times.size + 1,) or int(offsets[-1]) != candidate_flow.shape[0]:
        raise P3FlowTranslationError("RF-5 candidate offsets mismatch")
    if candidate_residual.shape != (candidate_flow.shape[0], CELL_COUNT):
        raise P3FlowTranslationError("RF-5 candidate residual shape mismatch")
    return {
        "identity": identity,
        "representative": representative,
        "common": common,
        "candidates": candidates,
        "diagnostics": diagnostics,
        "uncertainty": uncertainty,
        "transition_times": transition_times,
        "representative_flow": representative_flow,
        "offsets": offsets,
        "candidate_flow": candidate_flow,
        "candidate_residual": candidate_residual,
    }


def _load_rf8_optional(rf8_artifact_dir: Path | None, snapshot: Mapping[str, Any]) -> dict[str, Any] | None:
    if rf8_artifact_dir is None:
        return None
    required = {
        "identity.json",
        "axis_flow_family.npz",
        "lag_feedback_coupling.npz",
        "same_axis_dynamics.json",
        "history_conditioned_innovation.npz",
        "innovation_labels.json",
        "unresolved_residual_ledger.npz",
        "validation.json",
    }
    missing = sorted(name for name in required if not (rf8_artifact_dir / name).is_file())
    if missing:
        raise P3FlowTranslationError(f"RF-8 artifact is missing: {missing}")
    identity = _load_json(rf8_artifact_dir / "identity.json")
    validation = _load_json(rf8_artifact_dir / "validation.json")
    if validation.get("rf8_axis_coupling_innovation_gate") != "passed":
        raise P3FlowTranslationError("RF-8 validation gate did not pass")
    expected = {
        "trajectory_id": snapshot["trajectory_id"],
        "to_t": snapshot["cutoff_t"],
        "max_source_t_read": snapshot["cutoff_t"],
        "source_history_chain_hash": snapshot["history_chain_hash"],
    }
    for key, value in expected.items():
        if identity.get(key) != value:
            raise P3FlowTranslationError(f"RF-8 identity mismatch: {key}")
    return {
        "identity": identity,
        "axis_family": _load_npz(rf8_artifact_dir / "axis_flow_family.npz"),
        "lag_feedback": _load_npz(rf8_artifact_dir / "lag_feedback_coupling.npz"),
        "same_axis": _load_json(rf8_artifact_dir / "same_axis_dynamics.json"),
        "innovation": _load_npz(rf8_artifact_dir / "history_conditioned_innovation.npz"),
        "innovation_labels": _load_json(rf8_artifact_dir / "innovation_labels.json"),
        "residual": _load_npz(rf8_artifact_dir / "unresolved_residual_ledger.npz"),
    }


def _latest_candidate_summary(rf5: Mapping[str, Any]) -> dict[str, np.ndarray | float]:
    transition_index = int(rf5["transition_times"].size - 1)
    start = int(rf5["offsets"][transition_index])
    stop = int(rf5["offsets"][transition_index + 1])
    values = np.asarray(rf5["candidate_flow"][start:stop], dtype=np.float64)
    residual = np.asarray(rf5["candidate_residual"][start:stop], dtype=np.float64)
    if values.shape[0] < 1:
        raise P3FlowTranslationError("RF-5 latest transition has no candidates")
    residual_l1 = np.sum(np.abs(residual), axis=1)
    return {
        "minimum": np.min(values, axis=0),
        "maximum": np.max(values, axis=0),
        "mean": np.mean(values, axis=0),
        "residual_l1_minimum": float(np.min(residual_l1)),
        "residual_l1_maximum": float(np.max(residual_l1)),
        "residual_l1_mean": float(np.mean(residual_l1)),
    }


def _active_adjacency(grid: Mapping[str, np.ndarray], active: np.ndarray) -> list[list[int]]:
    source = grid["edge_source"]
    target = grid["edge_target"]
    by_cell: list[list[int]] = [[] for _ in range(CELL_COUNT)]
    for edge_id in np.flatnonzero(active):
        by_cell[int(source[edge_id])].append(int(edge_id))
        by_cell[int(target[edge_id])].append(int(edge_id))
    neighbors: list[list[int]] = [[] for _ in range(source.size)]
    for edge_id in np.flatnonzero(active):
        linked = set(by_cell[int(source[edge_id])]) | set(by_cell[int(target[edge_id])])
        linked.discard(int(edge_id))
        neighbors[int(edge_id)] = sorted(linked)
    return neighbors


def _axis_context(axis_index: int, rf5: Mapping[str, Any], rf8: Mapping[str, Any] | None) -> dict[str, Any]:
    last = int(rf5["transition_times"].size - 1)
    common = rf5["common"]
    diagnostics = rf5["diagnostics"]
    context: dict[str, Any] = {
        "axis_index": axis_index,
        "axis_name": AXIS_NAMES[axis_index],
        "flow_minimum": _finite_or_none(common["axis_flow_min"][last, axis_index]),
        "flow_maximum": _finite_or_none(common["axis_flow_max"][last, axis_index]),
        "flow_mean": _finite_or_none(common["axis_flow_mean"][last, axis_index]),
        "flow_acceleration": _finite_or_none(diagnostics["axis_flow_acceleration"][last][axis_index]),
        "direction_reversal": bool(diagnostics["axis_direction_reversal"][last][axis_index]),
        "rf8_available": rf8 is not None,
    }
    if rf8 is None:
        context.update({
            "coupling_from_axis": None,
            "same_axis_dynamics": None,
            "history_conditioned_innovation": None,
            "rf8_unavailable_reason": "RF-8 artifact not supplied",
        })
        return context
    lag = rf8["lag_feedback"]
    lag_index = int(np.asarray(lag["local_coupling_mean"]).shape[0] - 1)
    same_axis_rows = rf8["same_axis"].get("lags", [])
    same_axis = same_axis_rows[-1] if same_axis_rows else None
    innovation = rf8["innovation"]
    innovation_index = int(np.asarray(innovation["innovation_axis_flow"]).shape[0] - 1)
    context.update({
        "coupling_from_axis": {
            "mean": np.asarray(lag["local_coupling_mean"][lag_index, axis_index], dtype=np.float64).tolist(),
            "minimum": np.asarray(lag["local_coupling_minimum"][lag_index, axis_index], dtype=np.float64).tolist(),
            "maximum": np.asarray(lag["local_coupling_maximum"][lag_index, axis_index], dtype=np.float64).tolist(),
            "positive_consensus": np.asarray(lag["positive_consensus"][lag_index, axis_index], dtype=bool).tolist(),
            "negative_consensus": np.asarray(lag["negative_consensus"][lag_index, axis_index], dtype=bool).tolist(),
        },
        "same_axis_dynamics": None if same_axis is None else {
            key: same_axis[key][axis_index]
            for key in same_axis
            if key.endswith("_candidate") or key.endswith("_candidate_pair_fraction")
        },
        "history_conditioned_innovation": {
            "available": bool(innovation["baseline_available"][innovation_index]),
            "value": _finite_or_none(innovation["innovation_axis_flow"][innovation_index, axis_index]),
            "scale": _finite_or_none(innovation["innovation_scale"][innovation_index, axis_index]),
            "normalized_score": _finite_or_none(innovation["normalized_innovation_score"][innovation_index, axis_index]),
            "new_drive_candidate": bool(innovation["history_conditioned_new_drive_candidate"][innovation_index, axis_index]),
        },
        "rf8_unavailable_reason": None,
    })
    return context


def translate_micro_flows(
    *,
    current_gt: np.ndarray,
    grid: Mapping[str, np.ndarray],
    rf3_net_flow: np.ndarray,
    rf5: Mapping[str, Any],
    rf8: Mapping[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """検証済み配列を共通ミクロ流れ行へ翻訳する。"""
    representative = np.asarray(rf5["representative_flow"], dtype=np.float64)
    if representative.shape[0] < 2:
        raise P3FlowTranslationError("two RF-5 representative transitions are required")
    previous = representative[-2]
    current = representative[-1]
    edge_count = int(grid["edge_source"].size)
    if previous.shape != (edge_count,) or current.shape != (edge_count,) or rf3_net_flow.shape != (edge_count,):
        raise P3FlowTranslationError("flow edge count mismatch")
    candidate = _latest_candidate_summary(rf5)
    minimum = np.asarray(candidate["minimum"], dtype=np.float64)
    maximum = np.asarray(candidate["maximum"], dtype=np.float64)
    mean = np.asarray(candidate["mean"], dtype=np.float64)
    common_current = np.asarray(rf5["common"]["common_net_flow"][-1], dtype=np.float64)
    active = (
        (np.abs(previous) > FLOW_THRESHOLD)
        | (np.abs(current) > FLOW_THRESHOLD)
        | (np.abs(minimum) > FLOW_THRESHOLD)
        | (np.abs(maximum) > FLOW_THRESHOLD)
        | (np.abs(rf3_net_flow) > FLOW_THRESHOLD)
    )
    adjacency = _active_adjacency(grid, active)
    rows: list[dict[str, Any]] = []
    source_grid = grid["edge_source"]
    target_grid = grid["edge_target"]
    axis_grid = grid["edge_axis"]
    edge_common_fraction = float(rf5["diagnostics"]["edge_common_fraction"][-1])
    field_change = bool(rf5["diagnostics"]["field_change_candidate"][-1])
    for edge_id in np.flatnonzero(active):
        edge = int(edge_id)
        current_value = float(current[edge])
        previous_value = float(previous[edge])
        mean_value = float(mean[edge])
        direction = _sign(current_value if _sign(current_value) != 0 else mean_value)
        canonical_source = int(source_grid[edge])
        canonical_target = int(target_grid[edge])
        actual_source = canonical_source if direction >= 0 else canonical_target
        actual_target = canonical_target if direction >= 0 else canonical_source
        available_mass = float(current_gt[actual_source]) if direction != 0 else None
        rf3_value = float(rf3_net_flow[edge])
        state = _flow_state(previous_value, current_value)
        evidence = ["RF-5 representative temporal path", "RF-5 candidate interval"]
        counterevidence: list[str] = []
        if abs(float(common_current[edge])) > FLOW_THRESHOLD:
            evidence.append("flow sign and minimum magnitude common to saved optimal paths")
        if _sign(rf3_value) == _sign(current_value) and _sign(current_value) != 0:
            evidence.append("RF-3 representative agrees with RF-5 direction")
        elif _sign(rf3_value) != 0 or _sign(current_value) != 0:
            counterevidence.append("RF-3 and RF-5 representative directions differ")
        sign_ambiguous = float(minimum[edge]) < -FLOW_THRESHOLD and float(maximum[edge]) > FLOW_THRESHOLD
        if sign_ambiguous:
            counterevidence.append("RF-5 candidate family contains opposing directions")
        if field_change:
            counterevidence.append("RF-5 field-change candidate at cutoff")
        if edge_common_fraction < 1.0:
            counterevidence.append("saved optimal paths do not share every active edge")
        unavailable: list[str] = [
            "gross opposite-direction cancellation is unavailable because RF-5 stores net edge flow"
        ]
        if direction == 0:
            unavailable.append("directed source/target unavailable because candidate mean and representative flow are zero")
        if rf8 is None:
            unavailable.append("RF-8 coupling and innovation context unavailable")
        axis_index = int(axis_grid[edge])
        rows.append({
            "flow_id": f"fixed-edge:{edge}",
            "directed_flow_key": None if direction == 0 else f"edge:{edge}:direction:{direction:+d}",
            "canonical_edge_id": edge,
            "axis_index": axis_index,
            "axis_name": AXIS_NAMES[axis_index],
            "canonical_source_cell_id": canonical_source,
            "canonical_target_cell_id": canonical_target,
            "source_cell_id": None if direction == 0 else actual_source,
            "target_cell_id": None if direction == 0 else actual_target,
            "current_direction": direction,
            "current_flow": current_value,
            "previous_flow": previous_value,
            "flow_change": current_value - previous_value,
            "acceleration_candidate": current_value - previous_value,
            "persistence_state": state,
            "candidate_flow_minimum": float(minimum[edge]),
            "candidate_flow_maximum": float(maximum[edge]),
            "candidate_flow_mean": mean_value,
            "candidate_width": float(maximum[edge] - minimum[edge]),
            "candidate_sign_ambiguous": sign_ambiguous,
            "common_flow_minimum_magnitude": float(common_current[edge]),
            "rf3_representative_flow": rf3_value,
            "rf3_rf5_direction_agreement": _sign(rf3_value) == _sign(current_value),
            "same_direction_reinforcement": state == "strengthened",
            "same_direction_attenuation": state == "weakened",
            "direction_reversal": state == "reversed",
            "opposing_direction_candidate": sign_ambiguous,
            "opposite_cancellation_amount": None,
            "adjacent_active_edge_ids": adjacency[edge],
            "available_source_mass": available_mass,
            "axis_context": _axis_context(axis_index, rf5, rf8),
            "confidence": None,
            "confidence_status": "not_calibrated_candidate_evidence_only",
            "evidence": evidence,
            "counterevidence": counterevidence,
            "unavailable_fields": unavailable,
            "source_kind": "G/K-derived observed relation field",
            "prediction_performed": False,
        })
    residual_context = {
        "candidate_residual_l1_minimum": candidate["residual_l1_minimum"],
        "candidate_residual_l1_maximum": candidate["residual_l1_maximum"],
        "candidate_residual_l1_mean": candidate["residual_l1_mean"],
        "history_conditioned_innovation_kept_separate": True,
    }
    if rf8 is not None:
        residual = rf8["residual"]
        last = int(np.asarray(residual["transition_times"]).size - 1)
        residual_context["rf8_residual_l1_minimum"] = _finite_or_none(residual["residual_l1_minimum"][last])
        residual_context["rf8_residual_l1_maximum"] = _finite_or_none(residual["residual_l1_maximum"][last])
        residual_context["rf8_residual_l1_mean"] = _finite_or_none(residual["residual_l1_mean"][last])
    return rows, residual_context


def build_translation_artifact(
    *,
    gk_trajectory_dir: str | Path,
    grid_artifact_dir: str | Path,
    rf3_artifact_dir: str | Path,
    rf5_artifact_dir: str | Path,
    output_dir: str | Path,
    cutoff_t: int,
    rf8_artifact_dir: str | Path | None = None,
) -> Path:
    target = Path(output_dir)
    if target.exists():
        raise P3FlowTranslationError(f"output already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    gk_root = Path(gk_trajectory_dir)
    snapshot = inspect_gk_connection(gk_root, cutoff_t)
    rf3_connection = inspect_rf3_connection(Path(rf3_artifact_dir), gk_snapshot=snapshot)
    rf5 = _load_rf5(Path(rf5_artifact_dir), snapshot)
    grid = _load_grid(Path(grid_artifact_dir))
    current_gt = _load_current_gt(gk_root, snapshot)
    rf8 = _load_rf8_optional(None if rf8_artifact_dir is None else Path(rf8_artifact_dir), snapshot)
    rf3_field = Path(rf3_connection["field_dir"])
    rf3_net_flow = np.asarray(_load_npz(rf3_field / "local_flow.npz")["net_flow"], dtype=np.float64)
    rows, residual_context = translate_micro_flows(
        current_gt=current_gt,
        grid=grid,
        rf3_net_flow=rf3_net_flow,
        rf5=rf5,
        rf8=rf8,
    )
    if not rows:
        raise P3FlowTranslationError("translation produced no active micro-flow rows")
    if any(row["prediction_performed"] for row in rows):
        raise P3FlowTranslationError("P3-2 must not perform prediction")
    identity = {
        "task_id": "P3-2",
        "status": "translated",
        "trajectory_id": snapshot["trajectory_id"],
        "cutoff_t": cutoff_t,
        "source_history_chain_hash": snapshot["history_chain_hash"],
        "source_gt_hash": snapshot["current_gt_hash"],
        "rf3_relation_field_id": rf3_connection["relation_field_id"],
        "rf5_relation_field_id": rf5["identity"]["relation_field_id"],
        "rf8_axis_coupling_innovation_id": None if rf8 is None else rf8["identity"]["axis_coupling_innovation_id"],
        "maximum_source_t_read": cutoff_t,
        "future_information_read": False,
        "pseudo_reality_internal_state_read": False,
        "source_writeback_performed": False,
        "prediction_performed": False,
    }
    summary = {
        "translated_flow_count": len(rows),
        "rf8_context_available": rf8 is not None,
        "flow_state_counts": {
            state: sum(row["persistence_state"] == state for row in rows)
            for state in sorted({row["persistence_state"] for row in rows})
        },
        "sign_ambiguous_flow_count": sum(bool(row["candidate_sign_ambiguous"]) for row in rows),
        "uncalibrated_confidence_count": sum(row["confidence"] is None for row in rows),
        "residual_context": residual_context,
    }
    validation = {
        "p3_2_translation_gate": "passed",
        "nonempty_flow_rows": bool(rows),
        "all_rows_use_gk_derived_source": all(row["source_kind"] == "G/K-derived observed relation field" for row in rows),
        "no_prediction_performed": all(not row["prediction_performed"] for row in rows),
        "no_silent_confidence_fabrication": all(row["confidence"] is None for row in rows),
        "missing_gross_cancellation_marked_unavailable": all(
            row["opposite_cancellation_amount"] is None
            and any("gross opposite-direction cancellation" in reason for reason in row["unavailable_fields"])
            for row in rows
        ),
        "causal_cutoff_respected": identity["maximum_source_t_read"] == cutoff_t,
        "source_writeback_performed": False,
    }
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp-", dir=target.parent))
    try:
        _dump_json(temporary / "identity.json", identity)
        _write_jsonl(temporary / "micro_flows.jsonl", rows)
        _dump_json(temporary / "residual_context.json", residual_context)
        _dump_json(temporary / "summary.json", summary)
        _dump_json(temporary / "validation.json", validation)
        _dump_json(temporary / "provenance.json", {
            "source_files_read": [
                "gt_mass.npy:selected_cutoff_row_only",
                "history_ledger.csv:prefix_through_cutoff_t",
                "RF-2/incidence.npz",
                "RF-3/current cutoff field",
                "RF-5/causal temporal field",
            ] + ([] if rf8 is None else ["RF-8/causal coupling and residual field"]),
            "external_logs_read": False,
            "truth_files_read": False,
            "future_suffix_read": False,
            "canonical_or_parent_payload_copied": False,
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
    parser.add_argument("--rf3-artifact", required=True)
    parser.add_argument("--rf5-artifact", required=True)
    parser.add_argument("--rf8-artifact")
    parser.add_argument("--cutoff-t", required=True, type=int)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    output = build_translation_artifact(
        gk_trajectory_dir=args.gk_trajectory,
        grid_artifact_dir=args.grid_artifact,
        rf3_artifact_dir=args.rf3_artifact,
        rf5_artifact_dir=args.rf5_artifact,
        rf8_artifact_dir=args.rf8_artifact,
        cutoff_t=args.cutoff_t,
        output_dir=args.output,
    )
    print(json.dumps({"status": "translated", "output": output.as_posix()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
