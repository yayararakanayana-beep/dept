"""P3-1: G_t/K_t と関係場の因果的接続確認。

このモジュールは予測を行わない。P3 試作機が読む正本 G/K と RF-3 の
接続点を検証し、P3-2 へ渡す接続記録を作る。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

GT_SHAPE = (5, 5, 5, 5, 5)
FORBIDDEN_INPUT_NAMES = {
    "truth.jsonl",
    "summary.json",
    "metrics.jsonl",
    "future_state",
    "future_external_input",
    "future_event",
    "future_action",
    "risk_truth",
    "recovery_truth",
    "scenario_final_outcome",
    "terrain_truth",
    "flow_truth",
}

RELATION_FIELD_INVENTORY: dict[str, dict[str, Any]] = {
    "RF-3": {
        "role": "single_transition_observed_flow_basis",
        "script": "scripts/relation_field_single_transition_rc1.py",
        "consumption": "required_now",
        "files": [
            "identity.json",
            "local_flow_edges.csv",
            "local_flow.npz",
            "reconstruction.json",
            "unresolved_residual.npz",
            "uncertainty.json",
            "manifest.json",
        ],
    },
    "RF-4": {
        "role": "rf3_engineering_and_non_uniqueness_audit",
        "document": "docs/relation_field_rc1/RF4_SINGLE_TRANSITION_AUDIT.md",
        "consumption": "audit_sidecar_not_numeric_predictor_input",
        "files": [
            "scenario_results.jsonl",
            "minimum_action_certificates.json",
            "alternative_solution_audit.json",
            "alternative_candidates.npz",
            "solver_sensitivity.json",
            "residual_penalty_sensitivity.json",
            "locality_counterfactual.json",
        ],
    },
    "RF-5": {
        "role": "temporal_candidate_paths_and_common_structure",
        "script": "scripts/relation_field_temporal_consistency_rc1.py",
        "consumption": "required_in_p3_2_translation",
        "files": [
            "candidate_flows.npz",
            "candidate_index.json",
            "temporal_paths.json",
            "representative_flow.npz",
            "common_structure.npz",
            "temporal_diagnostics.json",
            "uncertainty.json",
        ],
    },
    "RF-6": {
        "role": "gradient_circulation_harmonic_decomposition",
        "script": "scripts/relation_field_hodge_decomposition_rc1.py",
        "consumption": "optional_p3_2_component_information",
        "files": [
            "candidate_components.npz",
            "candidate_metrics.json",
            "representative_components.npz",
            "path_family_components.npz",
            "common_input_components.npz",
            "decomposition_diagnostics.json",
        ],
    },
    "RF-7": {
        "role": "distribution_shape_and_flow_channel_dynamics",
        "script": "scripts/relation_field_shape_dynamics_rc1.py",
        "consumption": "optional_p3_2_shape_information",
        "files": [
            "frame_shape_metrics.npz",
            "frame_components.json",
            "transition_shape_metrics.npz",
            "transition_labels.json",
            "flow_channel_metrics.npz",
            "boundary_dynamics.npz",
            "field_shape_alignment.npz",
        ],
    },
    "RF-8": {
        "role": "axis_coupling_same_axis_dynamics_innovation_and_residual",
        "script": "scripts/relation_field_axis_coupling_innovation_rc1.py",
        "consumption": "optional_p3_2_coupling_and_residual_information",
        "files": [
            "axis_flow_family.npz",
            "position_flow_coupling.npz",
            "lag_feedback_coupling.npz",
            "same_axis_dynamics.json",
            "history_conditioned_innovation.npz",
            "innovation_labels.json",
            "unresolved_residual_ledger.npz",
        ],
    },
    "RF-9": {
        "role": "parallel_structural_risk_candidates",
        "script": "scripts/relation_field_risk_structure_rc1.py",
        "consumption": "context_only_not_truth_or_primary_flow_input",
        "files": [
            "risk_structure_metrics.npz",
            "risk_structure_candidates.json",
            "risk_evidence_ledger.json",
            "risk_counterevidence_ledger.json",
            "risk_structure_diagnostics.json",
            "uncertainty.json",
        ],
    },
}


class P3ConnectionError(ValueError):
    """P3-1 接続境界または成果物の不整合。"""


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def stable_fixed_edge_key(row: Mapping[str, Any]) -> str:
    """固定位置上の同一有向辺を表すキー。

    これは平行移動する流れ型の系譜 ID ではない。移動型の比較は RF-5 の
    平行移動非依存記述を P3-2 で翻訳して扱う。
    """
    edge = int(row["canonical_edge_id"])
    direction = int(row["direction"])
    if direction not in (-1, 1):
        raise P3ConnectionError("RF-3 direction must be -1 or 1")
    return f"edge:{edge}:direction:{direction:+d}"


def select_causal_cutoff_rows(
    rows: Sequence[Mapping[str, str]], cutoff_t: int
) -> tuple[dict[str, str], dict[str, str]]:
    """cutoff_t と直前時点だけを因果的接頭部から選ぶ。"""
    if cutoff_t < 1:
        raise P3ConnectionError("cutoff_t must be at least 1")
    prefix = [dict(row) for row in rows if int(row["t"]) <= cutoff_t]
    if not prefix:
        raise P3ConnectionError("G/K history prefix is empty")
    times = [int(row["t"]) for row in prefix]
    if times != sorted(times) or len(times) != len(set(times)):
        raise P3ConnectionError("G/K history prefix must be ordered and unique")
    by_t = {int(row["t"]): row for row in prefix}
    if cutoff_t not in by_t or cutoff_t - 1 not in by_t:
        raise P3ConnectionError("cutoff and immediately previous G_t are required")
    current = by_t[cutoff_t]
    previous = by_t[cutoff_t - 1]
    if current.get("continuity_status") != "continuous":
        raise P3ConnectionError("cutoff transition is not continuous")
    if current.get("previous_gt_hash") != previous.get("gt_hash"):
        raise P3ConnectionError("cutoff G/K history link hash mismatch")
    if current.get("admissible_for_research", "").lower() != "true":
        raise P3ConnectionError("cutoff G_t is not research-admissible")
    return previous, current


def _validate_rf3_identity(
    identity: Mapping[str, Any],
    *,
    trajectory_id: str,
    cutoff_t: int,
    previous_gt_hash: str,
    current_gt_hash: str,
) -> None:
    expected = {
        "trajectory_id": trajectory_id,
        "from_t": cutoff_t - 1,
        "to_t": cutoff_t,
        "source_gt_hash_from": previous_gt_hash,
        "source_gt_hash_to": current_gt_hash,
        "max_source_t_read": cutoff_t,
    }
    for key, value in expected.items():
        if identity.get(key) != value:
            raise P3ConnectionError(f"RF-3 identity mismatch: {key}")
    if identity.get("observed_transition_reconstruction_not_forecast") is not True:
        raise P3ConnectionError("RF-3 must remain observed reconstruction, not forecast")


def inspect_gk_connection(trajectory_dir: str | Path, cutoff_t: int) -> dict[str, Any]:
    """既存 G/K 検証器を通し、cutoff 時点の参照だけを返す。"""
    try:
        from fixed5axis_gk_rc1 import load_contract, validate_trajectory_artifact
    except ImportError as exc:  # pragma: no cover - repository layout failure
        raise P3ConnectionError("fixed5axis_gk_rc1 is unavailable") from exc

    root = Path(trajectory_dir)
    contract = load_contract()
    validation = validate_trajectory_artifact(root, contract)
    ledger_path = root / contract["storage"]["history_ledger_file"]
    mass_path = root / contract["storage"]["gt_file"]
    rows = _read_csv(ledger_path)
    previous, current = select_causal_cutoff_rows(rows, cutoff_t)

    mass = np.load(mass_path, mmap_mode="r", allow_pickle=False)
    if mass.ndim != 6 or tuple(mass.shape[1:]) != GT_SHAPE:
        raise P3ConnectionError("canonical G_t array shape mismatch")
    if mass.dtype != np.dtype("float64"):
        raise P3ConnectionError("canonical G_t must be float64")
    indices = (int(previous["gt_row_index"]), int(current["gt_row_index"]))
    if min(indices) < 0 or max(indices) >= mass.shape[0]:
        raise P3ConnectionError("cutoff row index is outside gt_mass.npy")

    return {
        "trajectory_dir": root.as_posix(),
        "trajectory_id": current["trajectory_id"],
        "cutoff_t": cutoff_t,
        "previous_t": cutoff_t - 1,
        "previous_gt_hash": previous["gt_hash"],
        "current_gt_hash": current["gt_hash"],
        "previous_gt_row_index": indices[0],
        "current_gt_row_index": indices[1],
        "gt_shape": list(GT_SHAPE),
        "gt_dtype": "float64",
        "history_chain_hash": current["history_chain_hash"],
        "maximum_source_t_allowed": cutoff_t,
        "existing_validator_result": validation,
    }


def inspect_rf3_connection(
    artifact_dir: str | Path,
    *,
    gk_snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    """cutoff 遷移の RF-3 数値成果物を G/K ハッシュへ接続する。"""
    root = Path(artifact_dir)
    trajectory_id = str(gk_snapshot["trajectory_id"])
    cutoff_t = int(gk_snapshot["cutoff_t"])
    field = root / "trajectories" / trajectory_id / "fields" / f"t_{cutoff_t:06d}"
    required = RELATION_FIELD_INVENTORY["RF-3"]["files"]
    missing = [name for name in required if not (field / name).is_file()]
    if missing:
        raise P3ConnectionError(f"RF-3 field files are missing: {missing}")

    identity = _load_json(field / "identity.json")
    _validate_rf3_identity(
        identity,
        trajectory_id=trajectory_id,
        cutoff_t=cutoff_t,
        previous_gt_hash=str(gk_snapshot["previous_gt_hash"]),
        current_gt_hash=str(gk_snapshot["current_gt_hash"]),
    )

    with np.load(field / "local_flow.npz", allow_pickle=False) as loaded:
        net_flow = np.asarray(loaded["net_flow"], dtype=np.float64)
        observed_delta = np.asarray(loaded["observed_delta"], dtype=np.float64)
    with np.load(field / "unresolved_residual.npz", allow_pickle=False) as loaded:
        residual = np.asarray(loaded["residual"], dtype=np.float64)
    if net_flow.ndim != 1:
        raise P3ConnectionError("RF-3 net_flow must be one-dimensional")
    if observed_delta.shape != (3125,) or residual.shape != (3125,):
        raise P3ConnectionError("RF-3 delta or residual shape mismatch")

    flow_rows = _read_csv(field / "local_flow_edges.csv")
    fixed_edge_keys = [stable_fixed_edge_key(row) for row in flow_rows]
    return {
        "artifact_dir": root.as_posix(),
        "field_dir": field.as_posix(),
        "relation_field_id": identity["relation_field_id"],
        "from_t": cutoff_t - 1,
        "to_t": cutoff_t,
        "source_gt_hash_from": identity["source_gt_hash_from"],
        "source_gt_hash_to": identity["source_gt_hash_to"],
        "edge_count": int(net_flow.size),
        "active_directed_flow_count": len(flow_rows),
        "active_fixed_edge_keys": fixed_edge_keys,
        "observed_delta_l1": float(np.abs(observed_delta).sum(dtype=np.float64)),
        "unresolved_residual_l1": float(np.abs(residual).sum(dtype=np.float64)),
        "maximum_source_t_read": int(identity["max_source_t_read"]),
        "observed_reconstruction_only": True,
    }


def build_connection_record(
    *,
    gk_trajectory_dir: str | Path,
    rf3_artifact_dir: str | Path,
    cutoff_t: int,
) -> dict[str, Any]:
    gk = inspect_gk_connection(gk_trajectory_dir, cutoff_t)
    rf3 = inspect_rf3_connection(rf3_artifact_dir, gk_snapshot=gk)
    return {
        "task_id": "P3-1",
        "status": "connection_confirmed",
        "purpose": "confirm causal G/K and relation-field connection before prediction implementation",
        "input_boundary": {
            "allowed": [
                "canonical G_t",
                "causal K_t prefix through cutoff_t",
                "relation-field products derived only through cutoff_t",
                "fixed grid identity and adjacency",
            ],
            "forbidden": sorted(FORBIDDEN_INPUT_NAMES),
            "pseudo_reality_internal_state_visible_to_predictor": False,
            "future_information_visible_to_predictor": False,
        },
        "gk_connection": gk,
        "rf3_connection": rf3,
        "flow_identity_decision": {
            "same_fixed_location_key": "canonical_edge_id + direction",
            "directed_flow_id_is_cross_time_identity": False,
            "relation_field_id_is_cross_time_flow_identity": False,
            "translation_or_moving_pattern_identity": "defer to RF-5 translation-invariant descriptor in P3-2",
            "reason": "absolute edge identity preserves fixed location but cannot identify a translated flow pattern",
        },
        "relation_field_inventory": RELATION_FIELD_INVENTORY,
        "p3_2_handoff": {
            "primary_numeric_sources": ["canonical G/K", "RF-3", "RF-5"],
            "optional_context_sources": ["RF-6", "RF-7", "RF-8", "RF-9"],
            "rf4_role": "audit evidence only",
            "translation_not_implemented_in_p3_1": True,
        },
        "source_writeback_performed": False,
        "prediction_performed": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gk-trajectory", required=True)
    parser.add_argument("--rf3-artifact", required=True)
    parser.add_argument("--cutoff-t", required=True, type=int)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    output = Path(args.output)
    if output.exists():
        raise P3ConnectionError(f"output already exists: {output}")
    record = build_connection_record(
        gk_trajectory_dir=args.gk_trajectory,
        rf3_artifact_dir=args.rf3_artifact,
        cutoff_t=args.cutoff_t,
    )
    _dump_json(output, record)
    print(json.dumps({"status": record["status"], "output": output.as_posix()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
