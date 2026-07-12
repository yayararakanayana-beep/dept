"""固定5軸 動的関係場 RF-3: 観測済み単一遷移の局所流れ逆算。"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import scipy
from scipy.optimize import linprog
from scipy.sparse import coo_matrix, eye, hstack

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "configs" / "relation_field_single_transition_rc1_contract.json"
AXIS_NAMES = ("resource_slack", "information_quality", "pressure", "exploration_room", "reversibility")
AXIS_BINS = (0.0, 0.25, 0.5, 0.75, 1.0)
GT_SHAPE = (5, 5, 5, 5, 5)
CELL_COUNT = 3125
GENESIS_HASH = hashlib.sha256(b"fixed5axis_gk_rc1_history_genesis").hexdigest()


class RelationFieldTransitionError(ValueError):
    """RF-3契約、入力、solver、成果物の不整合。"""


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _validate_sha256(value: str, name: str) -> None:
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise RelationFieldTransitionError(f"{name} must be a lowercase SHA-256 digest")


def _compute_gt_hash(*, trajectory_id: str, t: int, distribution: np.ndarray, source_state_hash: str) -> str:
    digest = hashlib.sha256()
    for value in ("fixed5axis_gk_rc1", trajectory_id, str(int(t))):
        digest.update(value.encode("utf-8")); digest.update(b"\0")
    digest.update(_canonical_json({"axes": AXIS_NAMES, "bins": AXIS_BINS})); digest.update(b"\0")
    digest.update(np.ascontiguousarray(distribution, dtype=np.dtype("<f8")).tobytes(order="C")); digest.update(b"\0")
    digest.update(source_state_hash.encode("ascii"))
    return digest.hexdigest()


def _compute_history_chain_hash(previous: str, gt_hash: str, t: int) -> str:
    return hashlib.sha256(f"{previous}\0{gt_hash}\0{int(t)}".encode("ascii")).hexdigest()


def _write_npz(path: Path, arrays: Mapping[str, np.ndarray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(arrays):
            buffer = io.BytesIO(); np.save(buffer, np.asarray(arrays[name]), allow_pickle=False)
            info = zipfile.ZipInfo(f"{name}.npy", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED; info.external_attr = 0o600 << 16
            archive.writestr(info, buffer.getvalue(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def _write_csv(path: Path, rows: Iterable[Mapping[str, Any]], fields: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _manifest_entries(root: Path, *, exclude: Iterable[str] = ()) -> list[dict[str, Any]]:
    excluded = set(exclude)
    return [
        {"path": path.relative_to(root).as_posix(), "sha256": _sha256_file(path), "size_bytes": path.stat().st_size}
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.relative_to(root).as_posix() not in excluded
    ]


def load_contract(path: str | Path = DEFAULT_CONTRACT) -> dict[str, Any]:
    contract = _load_json(Path(path)); validate_contract(contract); return contract


def validate_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("contract_version") != "relation_field_single_transition_rc1":
        raise RelationFieldTransitionError("unsupported RF-3 contract")
    solver = contract.get("solver", {})
    if solver.get("method") != "highs-ds":
        raise RelationFieldTransitionError("RF-3 solver method must be highs-ds")
    if float(solver.get("residual_penalty", 0)) <= float(solver.get("maximum_grid_path_cost", 0)):
        raise RelationFieldTransitionError("residual penalty must exceed the maximum grid path cost")
    if contract.get("uncertainty", {}).get("required_types") != [
        "identifiability", "evidence_sufficiency", "temporal_stability", "out_of_range"
    ]:
        raise RelationFieldTransitionError("RF-3 uncertainty contract mismatch")


def _load_grid(root: Path) -> dict[str, Any]:
    for name in ("contract.json", "manifest.json", "incidence.npz", "nodes.npz", "validation.json"):
        if not (root / name).is_file():
            raise RelationFieldTransitionError(f"grid artifact missing file: {name}")
    validation = _load_json(root / "validation.json")
    contract = _load_json(root / "contract.json")
    if validation.get("rf2_grid_gate") != "passed" or contract.get("contract_version") != "relation_field_grid_rc1":
        raise RelationFieldTransitionError("RF-2 grid artifact is not valid")
    with np.load(root / "incidence.npz", allow_pickle=False) as data:
        rows, cols = data["rows"].copy(), data["cols"].copy()
        values, shape = data["data"].copy(), tuple(int(v) for v in data["shape"])
        source, target, axis = data["edge_source"].copy(), data["edge_target"].copy(), data["edge_axis"].copy()
    with np.load(root / "nodes.npz", allow_pickle=False) as data:
        boundary = data["boundary_axis_count"].copy()
    if shape[0] != CELL_COUNT or source.shape != target.shape or source.shape != axis.shape:
        raise RelationFieldTransitionError("RF-2 grid payload mismatch")
    return {
        "contract": contract,
        "manifest_hash": _sha256_file(root / "manifest.json"),
        "incidence": coo_matrix((values, (rows, cols)), shape=shape).tocsr(),
        "edge_source": source.astype(np.int32),
        "edge_target": target.astype(np.int32),
        "edge_axis": axis.astype(np.int8),
        "boundary_axis_count": boundary.astype(np.uint8),
        "edge_count": int(source.size),
    }


def _validate_distribution(value: np.ndarray, tolerance: float) -> np.ndarray:
    array = np.ascontiguousarray(np.asarray(value), dtype=np.float64)
    if array.shape != GT_SHAPE or not np.all(np.isfinite(array)) or float(array.min()) < 0:
        raise RelationFieldTransitionError("invalid canonical G_t")
    total = float(array.sum(dtype=np.float64))
    if abs(total - 1.0) > tolerance:
        raise RelationFieldTransitionError(f"G_t mass {total:.17g} does not sum to one")
    return array


def _read_history_prefix(path: Path, to_t: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if int(row["t"]) > to_t:
                break
            rows.append(row)
    return rows


def _load_transition(trajectory: Path, from_t: int, to_t: int, tolerance: float) -> dict[str, Any]:
    if to_t != from_t + 1:
        raise RelationFieldTransitionError("RF-3 requires to_t = from_t + 1")
    mass_path, ledger_path = trajectory / "gt_mass.npy", trajectory / "history_ledger.csv"
    if not mass_path.is_file() or not ledger_path.is_file():
        raise RelationFieldTransitionError("canonical trajectory requires gt_mass.npy and history_ledger.csv")
    ledger = _read_history_prefix(ledger_path, to_t)
    selected = {int(row["t"]): row for row in ledger}
    if len(selected) != len(ledger) or from_t not in selected or to_t not in selected:
        raise RelationFieldTransitionError("requested transition is unavailable or duplicated")
    previous, chain = "", GENESIS_HASH
    for row in ledger:
        for field in ("gt_hash", "history_chain_hash", "source_state_hash"):
            _validate_sha256(row.get(field, ""), field)
        if row.get("previous_gt_hash"):
            _validate_sha256(row["previous_gt_hash"], "previous_gt_hash")
        if row.get("previous_gt_hash") != previous:
            raise RelationFieldTransitionError("history prefix previous_gt_hash mismatch")
        chain = _compute_history_chain_hash(chain, row["gt_hash"], int(row["t"]))
        if row.get("history_chain_hash") != chain:
            raise RelationFieldTransitionError("history prefix chain hash mismatch")
        previous = row["gt_hash"]
    first_row, second_row = selected[from_t], selected[to_t]
    if first_row.get("phase") != "pre_transition" or second_row.get("phase") != "pre_transition":
        raise RelationFieldTransitionError("RF-3 requires pre_transition G_t frames")
    if first_row.get("admissible_for_research", "").lower() != "true":
        raise RelationFieldTransitionError("from_t is not research-admissible")
    if second_row.get("admissible_for_research", "").lower() != "true" or second_row.get("continuity_status") != "continuous":
        raise RelationFieldTransitionError("to_t must be a continuous research-admissible transition")
    if int(second_row.get("delta_t", 0)) != 1 or second_row.get("previous_gt_hash") != first_row.get("gt_hash"):
        raise RelationFieldTransitionError("history link does not represent one continuous transition")
    mass = np.load(mass_path, mmap_mode="r", allow_pickle=False)
    if mass.ndim != 6 or tuple(mass.shape[1:]) != GT_SHAPE or mass.dtype != np.dtype("float64"):
        raise RelationFieldTransitionError("canonical gt_mass.npy shape or dtype mismatch")
    indices = (int(first_row["gt_row_index"]), int(second_row["gt_row_index"]))
    if min(indices) < 0 or max(indices) >= mass.shape[0]:
        raise RelationFieldTransitionError("history row index is outside gt_mass.npy")
    frames = [_validate_distribution(np.asarray(mass[index]), tolerance) for index in indices]
    trajectory_id = first_row.get("trajectory_id", "")
    if not trajectory_id or second_row.get("trajectory_id") != trajectory_id:
        raise RelationFieldTransitionError("trajectory identity mismatch")
    for row, frame in zip((first_row, second_row), frames, strict=True):
        expected = _compute_gt_hash(
            trajectory_id=trajectory_id,
            t=int(row["t"]),
            distribution=frame,
            source_state_hash=row["source_state_hash"],
        )
        if row.get("gt_hash") != expected:
            raise RelationFieldTransitionError("selected G_t hash mismatch")
    return {
        "trajectory_id": trajectory_id,
        "from_mass": frames[0],
        "to_mass": frames[1],
        "from_row": first_row,
        "to_row": second_row,
        "history_prefix_rows_read": len(ledger),
        "max_t_read": to_t,
    }


def invert_transition(from_mass: np.ndarray, to_mass: np.ndarray, grid: Mapping[str, Any], contract: Mapping[str, Any]) -> dict[str, Any]:
    validate_contract(contract)
    tolerance = float(contract["input"]["distribution_mass_tolerance"])
    source, target = _validate_distribution(from_mass, tolerance), _validate_distribution(to_mass, tolerance)
    delta = np.ascontiguousarray((target - source).reshape(-1, order="C"), dtype=np.float64)
    incidence, edge_count = grid["incidence"], int(grid["edge_count"])
    identity = eye(CELL_COUNT, format="csr", dtype=np.float64)
    matrix = hstack([incidence, -incidence, identity, -identity], format="csr")
    solver = contract["solver"]
    objective = np.concatenate([
        np.full(edge_count * 2, float(solver["coordinate_edge_cost"])),
        np.full(CELL_COUNT * 2, float(solver["residual_penalty"])),
    ])
    if not np.any(delta):
        vector = np.zeros(objective.size, dtype=np.float64)
        status = {"success": True, "status": 0, "message": "zero transition; solver skipped", "nit": 0}
    else:
        result = linprog(
            objective,
            A_eq=matrix,
            b_eq=delta,
            bounds=(0.0, None),
            method=solver["method"],
            options={
                "presolve": bool(solver["presolve"]),
                "primal_feasibility_tolerance": float(solver["primal_feasibility_tolerance"]),
                "dual_feasibility_tolerance": float(solver["dual_feasibility_tolerance"]),
            },
        )
        if not result.success or result.x is None:
            raise RelationFieldTransitionError(f"minimum-cost flow solver failed: {result.message}")
        vector = np.asarray(result.x, dtype=np.float64)
        status = {"success": True, "status": int(result.status), "message": str(result.message), "nit": int(result.nit)}
    forward = np.maximum(vector[:edge_count], 0.0)
    reverse = np.maximum(vector[edge_count:2 * edge_count], 0.0)
    positive = np.maximum(vector[2 * edge_count:2 * edge_count + CELL_COUNT], 0.0)
    negative = np.maximum(vector[2 * edge_count + CELL_COUNT:], 0.0)
    net = forward - reverse
    reconstructed = np.asarray(incidence @ net, dtype=np.float64)
    residual = delta - reconstructed
    if float(np.max(np.abs(residual - (positive - negative)))) > float(solver["reconstruction_tolerance"]):
        raise RelationFieldTransitionError("solver residual decomposition mismatch")
    return {
        "observed_delta": delta,
        "forward_flow": forward,
        "reverse_flow": reverse,
        "net_flow": net,
        "reconstructed_delta": reconstructed,
        "residual": residual,
        "positive_residual": positive,
        "negative_residual": negative,
        "solver": status,
    }


def _flow_rows(result: Mapping[str, Any], grid: Mapping[str, Any], threshold: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for edge_id in range(int(grid["edge_count"])):
        axis, low, high = int(grid["edge_axis"][edge_id]), int(grid["edge_source"][edge_id]), int(grid["edge_target"][edge_id])
        for amount, source, target, direction in (
            (float(result["forward_flow"][edge_id]), low, high, 1),
            (float(result["reverse_flow"][edge_id]), high, low, -1),
        ):
            if amount <= threshold:
                continue
            rows.append({
                "directed_flow_id": len(rows),
                "canonical_edge_id": edge_id,
                "source_cell_id": source,
                "target_cell_id": target,
                "axis_index": axis,
                "axis_name": AXIS_NAMES[axis],
                "direction": direction,
                "flow_amount": format(amount, ".17g"),
                "distance": "0.25",
                "confidence": "",
                "confidence_status": "not_calibrated_rf3",
                "representative_solution": "minimum_coordinate_cost_highs_ds",
            })
    return rows


def _metrics(result: Mapping[str, Any], grid: Mapping[str, Any], contract: Mapping[str, Any]) -> dict[str, Any]:
    delta, reconstructed, residual = result["observed_delta"], result["reconstructed_delta"], result["residual"]
    directed = result["forward_flow"] + result["reverse_flow"]
    changed_l1 = float(np.abs(delta).sum(dtype=np.float64))
    boundary = np.asarray(grid["boundary_axis_count"]) > 0
    threshold = float(contract["solver"]["flow_activation_threshold"])
    return {
        "solver": {**result["solver"], "method": contract["solver"]["method"], "scipy_version": scipy.__version__},
        "observed_delta_sum": float(delta.sum(dtype=np.float64)),
        "observed_delta_l1": changed_l1,
        "moved_mass_lower_bound": 0.5 * changed_l1,
        "active_directed_edge_count": int(np.count_nonzero(directed > threshold)),
        "active_canonical_edge_count": int(np.count_nonzero(np.abs(result["net_flow"]) > threshold)),
        "total_directed_edge_flow": float(directed.sum(dtype=np.float64)),
        "coordinate_transport_cost": float(contract["solver"]["coordinate_edge_cost"] * directed.sum(dtype=np.float64)),
        "reconstructed_delta_sum": float(reconstructed.sum(dtype=np.float64)),
        "residual_sum": float(residual.sum(dtype=np.float64)),
        "residual_l1": float(np.abs(residual).sum(dtype=np.float64)),
        "reconstruction_max_abs_error": float(np.max(np.abs(delta - reconstructed))),
        "reconstruction_rmse": float(np.sqrt(np.mean((delta - reconstructed) ** 2))),
        "simultaneous_opposite_edge_count": int(np.count_nonzero((result["forward_flow"] > threshold) & (result["reverse_flow"] > threshold))),
        "boundary_changed_mass_fraction": 0.0 if changed_l1 == 0 else float(np.abs(delta[boundary]).sum() / changed_l1),
        "reconstruction_tolerance": float(contract["solver"]["reconstruction_tolerance"]),
        "prediction_performed": False,
        "risk_classification_performed": False,
    }


def _uncertainty(grid: Mapping[str, Any], metrics: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "identifiability": {
            "status": "representative_solution_not_unique_in_general",
            "full_grid_cycle_rank": int(grid["edge_count"]) - CELL_COUNT + 1,
            "minimum_cost_solution_selected": True,
            "uniqueness_claim": False,
            "alternative_solution_audit": "deferred_to_rf4",
        },
        "evidence_sufficiency": {"status": "single_observed_transition_only", "gt_frames_used": 2, "history_dynamics_claim": False},
        "temporal_stability": {"status": "not_evaluated_in_rf3", "requires_rf5": True},
        "out_of_range": {
            "status": "not_evaluated_without_reference_corpus",
            "boundary_changed_mass_fraction": metrics["boundary_changed_mass_fraction"],
            "diagnostic_only": True,
        },
        "solver_numerical": {
            "residual_l1": metrics["residual_l1"],
            "reconstruction_max_abs_error": metrics["reconstruction_max_abs_error"],
            "solver_success": bool(metrics["solver"]["success"]),
        },
        "confidence_calibrated": False,
    }


def build_transition_field(
    trajectory_dir: str | Path,
    grid_artifact_dir: str | Path,
    output: str | Path,
    *,
    from_t: int,
    to_t: int,
    contract_path: str | Path = DEFAULT_CONTRACT,
) -> Path:
    contract, target = load_contract(contract_path), Path(output)
    if target.exists():
        raise RelationFieldTransitionError(f"output already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    grid = _load_grid(Path(grid_artifact_dir))
    source = _load_transition(
        Path(trajectory_dir), int(from_t), int(to_t), float(contract["input"]["distribution_mass_tolerance"])
    )
    result = invert_transition(source["from_mass"], source["to_mass"], grid, contract)
    metrics = _metrics(result, grid, contract)
    if metrics["reconstruction_max_abs_error"] > float(contract["solver"]["reconstruction_tolerance"]):
        raise RelationFieldTransitionError("reconstruction exceeds RF-3 tolerance")
    basis = {
        "contract_version": contract["contract_version"],
        "trajectory_id": source["trajectory_id"],
        "from_t": int(from_t),
        "to_t": int(to_t),
        "source_gt_hash_from": source["from_row"]["gt_hash"],
        "source_gt_hash_to": source["to_row"]["gt_hash"],
        "grid_manifest_hash": grid["manifest_hash"],
        "solver_method": contract["solver"]["method"],
    }
    relation_field_id = hashlib.sha256(_canonical_json(basis)).hexdigest()
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp-", dir=target.parent))
    try:
        _dump_json(temporary / "contract.json", contract)
        trajectory_root = temporary / "trajectories" / source["trajectory_id"]
        field_root = trajectory_root / "fields" / f"t_{int(to_t):06d}"
        field_root.mkdir(parents=True)
        identity = {
            "relation_field_id": relation_field_id,
            "trajectory_id": source["trajectory_id"],
            "t": int(to_t),
            "from_t": int(from_t),
            "to_t": int(to_t),
            "source_gt_hash_from": source["from_row"]["gt_hash"],
            "source_gt_hash_to": source["to_row"]["gt_hash"],
            "source_history_chain_hash": source["to_row"]["history_chain_hash"],
            "source_history_start_t": int(from_t),
            "source_history_end_t": int(to_t),
            "grid_contract_version": grid["contract"]["contract_version"],
            "grid_manifest_hash": grid["manifest_hash"],
            "derivation_version": contract["contract_version"],
            "max_source_t_read": int(to_t),
            "observed_transition_reconstruction_not_forecast": True,
        }
        _dump_json(field_root / "identity.json", identity)
        _write_csv(
            field_root / "local_flow_edges.csv",
            _flow_rows(result, grid, float(contract["solver"]["flow_activation_threshold"])),
            (
                "directed_flow_id", "canonical_edge_id", "source_cell_id", "target_cell_id", "axis_index",
                "axis_name", "direction", "flow_amount", "distance", "confidence", "confidence_status",
                "representative_solution",
            ),
        )
        _write_npz(field_root / "local_flow.npz", {
            "forward_flow": result["forward_flow"],
            "reverse_flow": result["reverse_flow"],
            "net_flow": result["net_flow"],
            "observed_delta": result["observed_delta"],
            "reconstructed_delta": result["reconstructed_delta"],
        })
        _dump_json(field_root / "reconstruction.json", metrics)
        _write_npz(field_root / "unresolved_residual.npz", {
            "residual": result["residual"],
            "positive_residual": result["positive_residual"],
            "negative_residual": result["negative_residual"],
        })
        _dump_json(field_root / "uncertainty.json", _uncertainty(grid, metrics))
        _dump_json(field_root / "manifest.json", {
            "relation_field_id": relation_field_id,
            "hash_algorithm": "sha256",
            "files": _manifest_entries(field_root, exclude={"manifest.json"}),
        })
        _dump_json(trajectory_root / "provenance.json", {
            "contract_version": contract["contract_version"],
            "trajectory_id": source["trajectory_id"],
            "source_files_read": ["gt_mass.npy:selected_rows_only", "history_ledger.csv:prefix_through_to_t"],
            "history_prefix_rows_read": source["history_prefix_rows_read"],
            "max_t_read": source["max_t_read"],
            "observed_logs_read": False,
            "truth_files_read": False,
            "source_writeback_performed": False,
            "canonical_gt_kt_copied": False,
        })
        _dump_json(trajectory_root / "relation_field_manifest.json", {
            "trajectory_id": source["trajectory_id"],
            "field_count": 1,
            "fields": [{"t": int(to_t), "relation_field_id": relation_field_id, "path": f"fields/t_{int(to_t):06d}"}],
        })
        validation = _validate_transition_artifact(temporary, Path(grid_artifact_dir), verify_manifest=False)
        _dump_json(temporary / "validation.json", validation)
        _dump_json(temporary / "manifest.json", {
            "contract_version": contract["contract_version"],
            "hash_algorithm": "sha256",
            "files": _manifest_entries(temporary, exclude={"manifest.json"}),
        })
        os.replace(temporary, target)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True); raise
    return target


def _verify_manifest(root: Path, manifest_path: Path) -> None:
    manifest = _load_json(manifest_path)
    for entry in manifest.get("files", []):
        path = (manifest_path.parent if manifest_path.parent != root else root) / entry["path"]
        if not path.is_file() or path.stat().st_size != int(entry["size_bytes"]) or _sha256_file(path) != entry["sha256"]:
            raise RelationFieldTransitionError(f"manifest mismatch: {path.relative_to(root)}")
    if manifest_path.parent == root:
        expected = {entry["path"] for entry in manifest.get("files", [])}
        actual = {path.relative_to(root).as_posix() for path in root.rglob("*") if path.is_file() and path != manifest_path}
        if expected != actual:
            raise RelationFieldTransitionError("root manifest file set mismatch")


def _validate_transition_artifact(root: Path, grid_artifact: Path, verify_manifest: bool) -> dict[str, Any]:
    contract = _load_json(root / "contract.json"); validate_contract(contract)
    trajectories = [path for path in (root / "trajectories").iterdir() if path.is_dir()]
    if len(trajectories) != 1:
        raise RelationFieldTransitionError("RF-3 artifact must contain exactly one trajectory")
    fields = [path for path in (trajectories[0] / "fields").iterdir() if path.is_dir()]
    if len(fields) != 1:
        raise RelationFieldTransitionError("RF-3 artifact must contain exactly one field")
    field = fields[0]
    if set(contract["storage"]["field_files"]) != {path.name for path in field.iterdir() if path.is_file()}:
        raise RelationFieldTransitionError("RF-3 field file set mismatch")
    if any(path.name in {"gt_mass.npy", "history_ledger.csv"} for path in root.rglob("*")):
        raise RelationFieldTransitionError("canonical G_t or K_t copied into RF-3 output")
    if verify_manifest:
        _verify_manifest(root, root / "manifest.json"); _verify_manifest(root, field / "manifest.json")
    grid = _load_grid(grid_artifact)
    identity = _load_json(field / "identity.json")
    metrics = _load_json(field / "reconstruction.json")
    uncertainty = _load_json(field / "uncertainty.json")
    if identity.get("max_source_t_read") != identity.get("to_t") or identity.get("grid_manifest_hash") != grid["manifest_hash"]:
        raise RelationFieldTransitionError("identity or causal cutoff mismatch")
    with np.load(field / "local_flow.npz", allow_pickle=False) as data:
        forward, reverse, net = data["forward_flow"], data["reverse_flow"], data["net_flow"]
        observed, reconstructed = data["observed_delta"], data["reconstructed_delta"]
    with np.load(field / "unresolved_residual.npz", allow_pickle=False) as data:
        residual, positive, negative = data["residual"], data["positive_residual"], data["negative_residual"]
    edge_count = int(grid["edge_count"])
    if any(array.shape != (edge_count,) for array in (forward, reverse, net)):
        raise RelationFieldTransitionError("flow array shape mismatch")
    if any(array.shape != (CELL_COUNT,) for array in (observed, reconstructed, residual, positive, negative)):
        raise RelationFieldTransitionError("delta or residual shape mismatch")
    if any(np.any(array < 0) for array in (forward, reverse, positive, negative)):
        raise RelationFieldTransitionError("directed flow or residual decomposition is negative")
    tolerance = float(contract["solver"]["reconstruction_tolerance"])
    checks = (
        net - (forward - reverse),
        np.asarray(grid["incidence"] @ net) - reconstructed,
        (observed - reconstructed) - residual,
        (positive - negative) - residual,
        observed - reconstructed,
    )
    if any(float(np.max(np.abs(check))) > tolerance for check in checks):
        raise RelationFieldTransitionError("RF-3 reconstruction or decomposition mismatch")
    if abs(float(observed.sum())) > float(contract["solver"]["mass_balance_tolerance"]):
        raise RelationFieldTransitionError("observed transition does not preserve normalized mass")
    threshold = float(contract["solver"]["flow_activation_threshold"])
    if np.count_nonzero((forward > threshold) & (reverse > threshold)):
        raise RelationFieldTransitionError("simultaneous opposite directed flow detected")
    with (field / "local_flow_edges.csv").open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != int(np.count_nonzero(forward > threshold) + np.count_nonzero(reverse > threshold)):
        raise RelationFieldTransitionError("directed flow CSV count mismatch")
    if any(key not in uncertainty for key in ("identifiability", "evidence_sufficiency", "temporal_stability", "out_of_range")):
        raise RelationFieldTransitionError("required uncertainty type missing")
    actual_max = float(np.max(np.abs(observed - reconstructed)))
    if abs(float(metrics["reconstruction_max_abs_error"]) - actual_max) > 1e-15:
        raise RelationFieldTransitionError("reconstruction metric mismatch")
    return {
        "rf3_single_transition_gate": "passed",
        "relation_field_id": identity["relation_field_id"],
        "trajectory_id": identity["trajectory_id"],
        "from_t": identity["from_t"],
        "to_t": identity["to_t"],
        "active_directed_edge_count": len(rows),
        "reconstruction_max_abs_error": actual_max,
        "residual_l1": float(np.abs(residual).sum()),
        "directed_nonnegative_flow": True,
        "causal_cutoff_respected": True,
        "uncertainty_present": True,
        "prediction_performed": False,
        "risk_classification_performed": False,
    }


def validate_transition_artifact(input_path: str | Path, grid_artifact_dir: str | Path) -> dict[str, Any]:
    root = Path(input_path)
    result = _validate_transition_artifact(root, Path(grid_artifact_dir), verify_manifest=True)
    if _load_json(root / "validation.json") != result:
        raise RelationFieldTransitionError("persisted RF-3 validation mismatch")
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    for name in ("trajectory", "grid-artifact", "output"):
        build.add_argument(f"--{name}", required=True)
    build.add_argument("--from-t", type=int, required=True); build.add_argument("--to-t", type=int, required=True)
    build.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    validate = commands.add_parser("validate")
    validate.add_argument("--input", required=True); validate.add_argument("--grid-artifact", required=True)
    args = parser.parse_args(argv)
    if args.command == "build":
        output = build_transition_field(
            args.trajectory, args.grid_artifact, args.output,
            from_t=args.from_t, to_t=args.to_t, contract_path=args.contract,
        )
        print(json.dumps({"output": str(output), "status": "built"}, ensure_ascii=False, sort_keys=True))
    else:
        print(json.dumps(validate_transition_artifact(args.input, args.grid_artifact), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
