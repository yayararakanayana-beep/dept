"""固定5軸 動的関係場 RF-6: 時間候補流れの勾配・循環・調和分解。"""
from __future__ import annotations

import argparse
import hashlib
import io
import itertools
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
from scipy.sparse import coo_matrix, csr_matrix
from scipy.sparse.linalg import lsqr

from relation_field_single_transition_rc1 import _load_grid
from relation_field_temporal_consistency_rc1 import validate_temporal_relation_field

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "configs" / "relation_field_hodge_decomposition_rc1.json"
CELL_COUNT = 3125
EDGE_COUNT = 12500
FACE_COUNT = 20000
AXIS_COUNT = 5
GRID_SHAPE = (5, 5, 5, 5, 5)
GRID_STRIDES = (625, 125, 25, 5, 1)


class RelationFieldHodgeError(ValueError):
    """RF-6契約、位相複体、分解、成果物の不整合。"""


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


def load_contract(path: str | Path = DEFAULT_CONTRACT) -> dict[str, Any]:
    contract = _load_json(Path(path))
    validate_contract(contract)
    return contract


def validate_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("contract_version") != "relation_field_hodge_decomposition_rc1":
        raise RelationFieldHodgeError("unsupported RF-6 contract")
    topology = contract.get("cubical_complex", {})
    if (
        int(topology.get("node_count", -1)) != CELL_COUNT
        or int(topology.get("edge_count", -1)) != EDGE_COUNT
        or int(topology.get("face_count", -1)) != FACE_COUNT
        or int(topology.get("expected_first_betti_number", -1)) != 0
    ):
        raise RelationFieldHodgeError("RF-6 topology contract mismatch")
    decomposition = contract.get("decomposition", {})
    if decomposition.get("gradient_solver") != "scipy_sparse_lsqr_with_node_0_gauge":
        raise RelationFieldHodgeError("RF-6 gradient solver mismatch")
    if decomposition.get("harmonic_component") != "zero_under_fixed_contractible_full_complex":
        raise RelationFieldHodgeError("RF-6 harmonic contract mismatch")


def _load_grid_with_indices(root: Path) -> dict[str, Any]:
    grid = _load_grid(root)
    with np.load(root / "nodes.npz", allow_pickle=False) as loaded:
        indices = loaded["indices"].copy()
        values = loaded["values"].copy()
    if indices.shape != (CELL_COUNT, AXIS_COUNT) or values.shape != indices.shape:
        raise RelationFieldHodgeError("RF-2 node payload mismatch")
    grid["node_indices"] = indices.astype(np.int16)
    grid["node_values"] = values.astype(np.float64)
    return grid


def generate_face_complex(grid: Mapping[str, Any]) -> dict[str, Any]:
    source = np.asarray(grid["edge_source"], dtype=np.int32)
    target = np.asarray(grid["edge_target"], dtype=np.int32)
    edge_lookup = {(int(left), int(right)): edge_id for edge_id, (left, right) in enumerate(zip(source, target, strict=True))}
    face_base: list[int] = []
    face_axis_a: list[int] = []
    face_axis_b: list[int] = []
    face_edges: list[tuple[int, int, int, int]] = []
    face_signs: list[tuple[int, int, int, int]] = []
    node_indices = np.asarray(grid["node_indices"], dtype=np.int16)
    for base_cell in range(CELL_COUNT):
        indices = node_indices[base_cell]
        for axis_a, axis_b in itertools.combinations(range(AXIS_COUNT), 2):
            if int(indices[axis_a]) >= GRID_SHAPE[axis_a] - 1 or int(indices[axis_b]) >= GRID_SHAPE[axis_b] - 1:
                continue
            vertex_00 = base_cell
            vertex_10 = base_cell + GRID_STRIDES[axis_a]
            vertex_01 = base_cell + GRID_STRIDES[axis_b]
            vertex_11 = vertex_10 + GRID_STRIDES[axis_b]
            try:
                edge_a_low = edge_lookup[(vertex_00, vertex_10)]
                edge_b_high = edge_lookup[(vertex_10, vertex_11)]
                edge_a_high = edge_lookup[(vertex_01, vertex_11)]
                edge_b_low = edge_lookup[(vertex_00, vertex_01)]
            except KeyError as exc:
                raise RelationFieldHodgeError("RF-6 face references a missing RF-2 edge") from exc
            face_base.append(base_cell)
            face_axis_a.append(axis_a)
            face_axis_b.append(axis_b)
            face_edges.append((edge_a_low, edge_b_high, edge_a_high, edge_b_low))
            face_signs.append((1, 1, -1, -1))
    base = np.asarray(face_base, dtype=np.int32)
    axis_a = np.asarray(face_axis_a, dtype=np.int8)
    axis_b = np.asarray(face_axis_b, dtype=np.int8)
    edge_ids = np.asarray(face_edges, dtype=np.int32)
    signs = np.asarray(face_signs, dtype=np.int8)
    if base.shape != (FACE_COUNT,) or edge_ids.shape != (FACE_COUNT, 4):
        raise RelationFieldHodgeError("RF-6 generated face count mismatch")
    rows = edge_ids.reshape(-1)
    cols = np.repeat(np.arange(FACE_COUNT, dtype=np.int32), 4)
    data = signs.reshape(-1).astype(np.float64)
    boundary_2 = coo_matrix((data, (rows, cols)), shape=(EDGE_COUNT, FACE_COUNT)).tocsr()
    boundary_1 = csr_matrix(grid["incidence"], dtype=np.float64)
    boundary_of_boundary = boundary_1 @ boundary_2
    boundary_of_boundary.eliminate_zeros()
    max_abs = 0.0 if boundary_of_boundary.nnz == 0 else float(np.max(np.abs(boundary_of_boundary.data)))
    return {
        "face_base_cell": base,
        "face_axis_a": axis_a,
        "face_axis_b": axis_b,
        "face_edge_ids": edge_ids,
        "face_edge_signs": signs,
        "boundary_2": boundary_2,
        "boundary_of_boundary_max_abs": max_abs,
    }


def _verify_manifest(root: Path) -> None:
    manifest = _load_json(root / "manifest.json")
    expected: set[str] = set()
    for entry in manifest.get("files", []):
        relative = str(entry["path"])
        expected.add(relative)
        path = root / relative
        if not path.is_file() or path.stat().st_size != int(entry["size_bytes"]) or _sha256_file(path) != entry["sha256"]:
            raise RelationFieldHodgeError(f"manifest mismatch: {relative}")
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    if expected != actual:
        raise RelationFieldHodgeError("manifest file set mismatch")


def _load_rf5_artifact(root: Path, grid_root: Path) -> dict[str, Any]:
    validate_temporal_relation_field(root, grid_root)
    identity = _load_json(root / "identity.json")
    paths = _load_json(root / "temporal_paths.json")
    summary = _load_json(root / "summary.json")
    with np.load(root / "candidate_flows.npz", allow_pickle=False) as loaded:
        offsets = loaded["candidate_offsets"].copy()
        candidate_flow = loaded["candidate_net_flow"].copy()
        transition_index = loaded["candidate_transition_index"].copy()
    with np.load(root / "representative_flow.npz", allow_pickle=False) as loaded:
        transition_times = loaded["transition_times"].copy()
    with np.load(root / "common_structure.npz", allow_pickle=False) as loaded:
        common_flow = loaded["common_net_flow"].copy()
    transition_count = int(identity["transition_count"])
    if offsets.shape != (transition_count + 1,) or candidate_flow.shape[1:] != (EDGE_COUNT,):
        raise RelationFieldHodgeError("RF-5 candidate payload mismatch")
    if common_flow.shape != (transition_count, EDGE_COUNT) or transition_times.shape != (transition_count,):
        raise RelationFieldHodgeError("RF-5 temporal payload mismatch")
    representative_path = [int(value) for value in paths["representative_path"]]
    optimal_paths = [[int(value) for value in path] for path in paths["optimal_paths"]]
    if len(representative_path) != transition_count or any(len(path) != transition_count for path in optimal_paths):
        raise RelationFieldHodgeError("RF-5 path length mismatch")
    return {
        "identity": identity,
        "summary": summary,
        "manifest_hash": _sha256_file(root / "manifest.json"),
        "offsets": offsets.astype(np.int32),
        "candidate_flow": np.asarray(candidate_flow, dtype=np.float64),
        "candidate_transition_index": transition_index.astype(np.int32),
        "transition_times": transition_times.astype(np.int32),
        "common_flow": np.asarray(common_flow, dtype=np.float64),
        "representative_path": representative_path,
        "optimal_paths": optimal_paths,
        "optimal_path_count": len(optimal_paths),
    }


def decompose_edge_flow(
    edge_flow: np.ndarray,
    boundary_1: csr_matrix,
    boundary_2: csr_matrix,
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    flow = np.asarray(edge_flow, dtype=np.float64)
    if flow.shape != (EDGE_COUNT,) or not np.all(np.isfinite(flow)):
        raise RelationFieldHodgeError("RF-6 edge flow shape or finiteness mismatch")
    settings = contract["decomposition"]
    reduced_gradient = boundary_1.transpose().tocsr()[:, 1:]
    solution = lsqr(
        reduced_gradient,
        flow,
        atol=float(settings["gradient_atol"]),
        btol=float(settings["gradient_btol"]),
        iter_lim=int(settings["gradient_iteration_limit"]),
        show=False,
    )
    node_potential = np.zeros(CELL_COUNT, dtype=np.float64)
    node_potential[1:] = np.asarray(solution[0], dtype=np.float64)
    gradient = np.asarray(boundary_1.transpose() @ node_potential, dtype=np.float64).reshape(-1)
    circulation = flow - gradient
    harmonic = np.zeros_like(flow)
    residual = flow - gradient - circulation - harmonic
    face_circulation = np.asarray(boundary_2.transpose() @ circulation, dtype=np.float64).reshape(-1)
    gradient_face_circulation = np.asarray(boundary_2.transpose() @ gradient, dtype=np.float64).reshape(-1)
    circulation_divergence = np.asarray(boundary_1 @ circulation, dtype=np.float64).reshape(-1)
    reconstruction = gradient + circulation + harmonic + residual
    metrics = {
        "input_energy": float(np.dot(flow, flow)),
        "gradient_energy": float(np.dot(gradient, gradient)),
        "circulation_energy": float(np.dot(circulation, circulation)),
        "harmonic_energy": 0.0,
        "numerical_residual_energy": float(np.dot(residual, residual)),
        "gradient_energy_fraction": 0.0 if not np.any(flow) else float(np.dot(gradient, gradient) / np.dot(flow, flow)),
        "circulation_energy_fraction": 0.0 if not np.any(flow) else float(np.dot(circulation, circulation) / np.dot(flow, flow)),
        "reconstruction_max_abs": float(np.max(np.abs(flow - reconstruction))),
        "gradient_circulation_inner_product": float(np.dot(gradient, circulation)),
        "circulation_divergence_max_abs": float(np.max(np.abs(circulation_divergence))),
        "gradient_face_circulation_max_abs": float(np.max(np.abs(gradient_face_circulation))),
        "face_circulation_max_abs": float(np.max(np.abs(face_circulation))),
        "harmonic_max_abs": 0.0,
        "numerical_residual_max_abs": float(np.max(np.abs(residual))),
        "solver_stop_code": int(solution[1]),
        "solver_iteration_count": int(solution[2]),
        "solver_residual_norm": float(solution[3]),
        "solver_normal_residual_norm": float(solution[7]),
    }
    return {
        "input_flow": flow,
        "gradient_flow": gradient,
        "circulation_flow": circulation,
        "harmonic_flow": harmonic,
        "numerical_residual_flow": residual,
        "node_potential": node_potential,
        "face_circulation": face_circulation,
        "metrics": metrics,
    }


def _same_sign_common(values: np.ndarray, threshold: float) -> np.ndarray:
    common = np.zeros(values.shape[1], dtype=np.float64)
    positive = np.all(values > threshold, axis=0)
    negative = np.all(values < -threshold, axis=0)
    if np.any(positive):
        common[positive] = np.min(values[:, positive], axis=0)
    if np.any(negative):
        common[negative] = np.max(values[:, negative], axis=0)
    return common


def _aggregate_path_family(
    component_arrays: Mapping[str, np.ndarray],
    rf5: Mapping[str, Any],
    threshold: float,
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    transition_count = int(rf5["identity"]["transition_count"])
    offsets = np.asarray(rf5["offsets"], dtype=np.int32)
    optimal_paths = rf5["optimal_paths"]
    aggregate: dict[str, list[np.ndarray]] = {
        "gradient_min": [], "gradient_max": [], "gradient_mean": [], "gradient_common": [],
        "circulation_min": [], "circulation_max": [], "circulation_mean": [], "circulation_common": [],
    }
    gradient_spread: list[float] = []
    circulation_spread: list[float] = []
    unique_candidate_count: list[int] = []
    for transition in range(transition_count):
        local_indices = [int(path[transition]) for path in optimal_paths]
        flat_indices = np.asarray([int(offsets[transition]) + local for local in local_indices], dtype=np.int64)
        unique_candidate_count.append(len(set(int(value) for value in flat_indices)))
        gradient = component_arrays["gradient_flow"][flat_indices]
        circulation = component_arrays["circulation_flow"][flat_indices]
        aggregate["gradient_min"].append(np.min(gradient, axis=0))
        aggregate["gradient_max"].append(np.max(gradient, axis=0))
        aggregate["gradient_mean"].append(np.mean(gradient, axis=0))
        aggregate["gradient_common"].append(_same_sign_common(gradient, threshold))
        aggregate["circulation_min"].append(np.min(circulation, axis=0))
        aggregate["circulation_max"].append(np.max(circulation, axis=0))
        aggregate["circulation_mean"].append(np.mean(circulation, axis=0))
        aggregate["circulation_common"].append(_same_sign_common(circulation, threshold))
        gradient_spread.append(float(np.max(np.ptp(gradient, axis=0))))
        circulation_spread.append(float(np.max(np.ptp(circulation, axis=0))))
    arrays = {name: np.stack(values) for name, values in aggregate.items()}
    arrays["transition_times"] = np.asarray(rf5["transition_times"], dtype=np.int32)
    diagnostics = {
        "unique_optimal_candidate_count_per_transition": unique_candidate_count,
        "candidate_family_gradient_spread_max_abs": gradient_spread,
        "candidate_family_circulation_spread_max_abs": circulation_spread,
    }
    return arrays, diagnostics


def _select_representative(component_arrays: Mapping[str, np.ndarray], rf5: Mapping[str, Any], boundary_2: csr_matrix) -> dict[str, np.ndarray]:
    offsets = np.asarray(rf5["offsets"], dtype=np.int32)
    flat_indices = np.asarray([
        int(offsets[transition]) + int(candidate)
        for transition, candidate in enumerate(rf5["representative_path"])
    ], dtype=np.int32)
    circulation = component_arrays["circulation_flow"][flat_indices]
    face_circulation = np.stack([
        np.asarray(boundary_2.transpose() @ flow, dtype=np.float64).reshape(-1)
        for flow in circulation
    ])
    return {
        "transition_times": np.asarray(rf5["transition_times"], dtype=np.int32),
        "flat_candidate_index": flat_indices,
        "input_flow": component_arrays["input_flow"][flat_indices],
        "gradient_flow": component_arrays["gradient_flow"][flat_indices],
        "circulation_flow": circulation,
        "harmonic_flow": component_arrays["harmonic_flow"][flat_indices],
        "numerical_residual_flow": component_arrays["numerical_residual_flow"][flat_indices],
        "node_potential": component_arrays["node_potential"][flat_indices],
        "face_circulation": face_circulation,
    }


def _decompose_matrix(
    flows: np.ndarray,
    boundary_1: csr_matrix,
    boundary_2: csr_matrix,
    contract: Mapping[str, Any],
) -> tuple[dict[str, np.ndarray], list[dict[str, Any]]]:
    results = [decompose_edge_flow(flow, boundary_1, boundary_2, contract) for flow in np.asarray(flows, dtype=np.float64)]
    arrays = {
        "input_flow": np.stack([result["input_flow"] for result in results]),
        "gradient_flow": np.stack([result["gradient_flow"] for result in results]),
        "circulation_flow": np.stack([result["circulation_flow"] for result in results]),
        "harmonic_flow": np.stack([result["harmonic_flow"] for result in results]),
        "numerical_residual_flow": np.stack([result["numerical_residual_flow"] for result in results]),
        "node_potential": np.stack([result["node_potential"] for result in results]),
    }
    return arrays, [result["metrics"] for result in results]


def build_hodge_decomposition(
    rf5_artifact_dir: str | Path,
    grid_artifact_dir: str | Path,
    output: str | Path,
    *,
    contract_path: str | Path = DEFAULT_CONTRACT,
) -> Path:
    contract = load_contract(contract_path)
    target = Path(output)
    if target.exists():
        raise RelationFieldHodgeError(f"output already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    grid_root = Path(grid_artifact_dir)
    rf5_root = Path(rf5_artifact_dir)
    grid = _load_grid_with_indices(grid_root)
    topology = generate_face_complex(grid)
    if topology["boundary_of_boundary_max_abs"] > float(contract["acceptance"]["boundary_of_boundary_tolerance"]):
        raise RelationFieldHodgeError("RF-6 boundary-of-boundary identity failed")
    rf5 = _load_rf5_artifact(rf5_root, grid_root)
    boundary_1 = csr_matrix(grid["incidence"], dtype=np.float64)
    boundary_2 = csr_matrix(topology["boundary_2"], dtype=np.float64)
    candidate_arrays, candidate_metrics = _decompose_matrix(rf5["candidate_flow"], boundary_1, boundary_2, contract)
    candidate_arrays["candidate_transition_index"] = np.asarray(rf5["candidate_transition_index"], dtype=np.int32)
    candidate_arrays["candidate_offsets"] = np.asarray(rf5["offsets"], dtype=np.int32)
    representative = _select_representative(candidate_arrays, rf5, boundary_2)
    family_arrays, family_diagnostics = _aggregate_path_family(candidate_arrays, rf5, threshold=1e-12)
    common_arrays, common_metrics = _decompose_matrix(rf5["common_flow"], boundary_1, boundary_2, contract)
    common_arrays["transition_times"] = np.asarray(rf5["transition_times"], dtype=np.int32)
    acceptance = contract["acceptance"]
    maxima = {
        "reconstruction_max_abs": max(metric["reconstruction_max_abs"] for metric in candidate_metrics + common_metrics),
        "gradient_circulation_inner_product_max_abs": max(abs(metric["gradient_circulation_inner_product"]) for metric in candidate_metrics + common_metrics),
        "circulation_divergence_max_abs": max(metric["circulation_divergence_max_abs"] for metric in candidate_metrics + common_metrics),
        "gradient_face_circulation_max_abs": max(metric["gradient_face_circulation_max_abs"] for metric in candidate_metrics + common_metrics),
        "harmonic_max_abs": 0.0,
        "numerical_residual_max_abs": max(metric["numerical_residual_max_abs"] for metric in candidate_metrics + common_metrics),
        "solver_iteration_count_max": max(metric["solver_iteration_count"] for metric in candidate_metrics + common_metrics),
    }
    ambiguous_transitions = [
        index for index, count in enumerate(family_diagnostics["unique_optimal_candidate_count_per_transition"])
        if count > 1
    ]
    ambiguous_gradient_spread = max(
        (family_diagnostics["candidate_family_gradient_spread_max_abs"][index] for index in ambiguous_transitions),
        default=0.0,
    )
    ambiguous_circulation_spread = max(
        (family_diagnostics["candidate_family_circulation_spread_max_abs"][index] for index in ambiguous_transitions),
        default=0.0,
    )
    gates = {
        "topology_gate": topology["boundary_of_boundary_max_abs"] <= float(acceptance["boundary_of_boundary_tolerance"]),
        "reconstruction_gate": maxima["reconstruction_max_abs"] <= float(acceptance["reconstruction_tolerance"]),
        "orthogonality_gate": maxima["gradient_circulation_inner_product_max_abs"] <= float(acceptance["orthogonality_tolerance"]),
        "circulation_divergence_gate": maxima["circulation_divergence_max_abs"] <= float(acceptance["circulation_divergence_tolerance"]),
        "gradient_face_circulation_gate": maxima["gradient_face_circulation_max_abs"] <= float(acceptance["gradient_face_circulation_tolerance"]),
        "harmonic_gate": maxima["harmonic_max_abs"] <= float(acceptance["harmonic_max_abs_tolerance"]),
        "numerical_residual_gate": maxima["numerical_residual_max_abs"] <= float(acceptance["numerical_residual_tolerance"]),
        "ambiguous_gradient_commonality_gate": ambiguous_gradient_spread <= float(acceptance["ambiguous_same_delta_gradient_spread_tolerance"]),
        "ambiguous_circulation_separation_gate": not ambiguous_transitions or ambiguous_circulation_spread >= float(acceptance["ambiguous_same_delta_circulation_spread_minimum"]),
    }
    overall = all(gates.values())
    if not overall:
        raise RelationFieldHodgeError(f"RF-6 decomposition gates failed: {gates}")
    identity_basis = {
        "contract_version": contract["contract_version"],
        "rf5_relation_field_id": rf5["identity"]["relation_field_id"],
        "rf5_manifest_hash": rf5["manifest_hash"],
        "grid_manifest_hash": grid["manifest_hash"],
        "transition_count": int(rf5["identity"]["transition_count"]),
        "candidate_count": int(rf5["candidate_flow"].shape[0]),
    }
    decomposition_id = hashlib.sha256(_canonical_json(identity_basis)).hexdigest()
    identity = {
        "decomposition_id": decomposition_id,
        **identity_basis,
        "start_t": int(rf5["identity"]["start_t"]),
        "to_t": int(rf5["identity"]["to_t"]),
        "max_source_t_read": int(rf5["identity"]["max_source_t_read"]),
        "unique_true_flow_claim": False,
        "risk_prediction_performed": False,
    }
    topology_json = {
        "node_count": CELL_COUNT,
        "edge_count": EDGE_COUNT,
        "face_count": FACE_COUNT,
        "axis_pair_count": 10,
        "boundary_condition": contract["cubical_complex"]["boundary_condition"],
        "expected_first_betti_number": 0,
        "harmonic_dimension_basis": contract["cubical_complex"]["harmonic_dimension_basis"],
        "boundary_of_boundary_max_abs": float(topology["boundary_of_boundary_max_abs"]),
        "harmonic_component_expected_zero": True,
        "nonzero_harmonic_claim": False,
    }
    diagnostics = {
        **maxima,
        **family_diagnostics,
        "ambiguous_transition_indices": ambiguous_transitions,
        "ambiguous_gradient_spread_max_abs": ambiguous_gradient_spread,
        "ambiguous_circulation_spread_max_abs": ambiguous_circulation_spread,
        "gates": gates,
    }
    uncertainty = {
        "candidate_identifiability": {
            "candidate_count": int(rf5["candidate_flow"].shape[0]),
            "optimal_path_count": int(rf5["optimal_path_count"]),
            "representative_path_is_not_unique_truth": True,
        },
        "component_spread": {
            "gradient_spread_max_abs_per_transition": family_diagnostics["candidate_family_gradient_spread_max_abs"],
            "circulation_spread_max_abs_per_transition": family_diagnostics["candidate_family_circulation_spread_max_abs"],
        },
        "harmonic": {
            "expected_zero_only_under_current_full_contractible_grid": True,
            "masked_or_noncontractible_future_domains_may_change_this": True,
        },
        "prediction_performed": False,
        "risk_prediction_performed": False,
    }
    validation = {
        "rf6_hodge_decomposition_gate": "passed",
        **gates,
        "scientific_claim": acceptance["scientific_claim"],
        "prediction_performed": False,
        "risk_prediction_performed": False,
        "parent_writeback_performed": False,
    }
    summary = {
        "contract_version": contract["contract_version"],
        "decomposition_id": decomposition_id,
        "transition_count": int(rf5["identity"]["transition_count"]),
        "candidate_count": int(rf5["candidate_flow"].shape[0]),
        "optimal_path_count": int(rf5["optimal_path_count"]),
        "ambiguous_transition_count": len(ambiguous_transitions),
        "gradient_energy_mean": float(np.mean([metric["gradient_energy"] for metric in candidate_metrics])),
        "circulation_energy_mean": float(np.mean([metric["circulation_energy"] for metric in candidate_metrics])),
        "ambiguous_gradient_spread_max_abs": ambiguous_gradient_spread,
        "ambiguous_circulation_spread_max_abs": ambiguous_circulation_spread,
        "harmonic_expected_zero": True,
        "scientific_claim": acceptance["scientific_claim"],
        "risk_prediction_performed": False,
    }
    metrics_payload = {
        "candidate_metrics": [
            {
                "flat_candidate_index": index,
                "transition_index": int(rf5["candidate_transition_index"][index]),
                **metric,
            }
            for index, metric in enumerate(candidate_metrics)
        ],
        "common_input_metrics": [
            {"transition_index": index, **metric}
            for index, metric in enumerate(common_metrics)
        ],
    }
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp-", dir=target.parent))
    try:
        storage = contract["storage"]
        _dump_json(temporary / storage["contract_file"], contract)
        _dump_json(temporary / storage["identity_file"], identity)
        _dump_json(temporary / storage["topology_file"], topology_json)
        _write_npz(temporary / storage["faces_file"], {
            "face_base_cell": topology["face_base_cell"],
            "face_axis_a": topology["face_axis_a"],
            "face_axis_b": topology["face_axis_b"],
            "face_edge_ids": topology["face_edge_ids"],
            "face_edge_signs": topology["face_edge_signs"],
        })
        _write_npz(temporary / storage["candidate_components_file"], candidate_arrays)
        _dump_json(temporary / storage["candidate_metrics_file"], metrics_payload)
        _write_npz(temporary / storage["representative_components_file"], representative)
        _write_npz(temporary / storage["path_family_components_file"], family_arrays)
        _write_npz(temporary / storage["common_input_components_file"], common_arrays)
        _dump_json(temporary / storage["decomposition_diagnostics_file"], diagnostics)
        _dump_json(temporary / storage["uncertainty_file"], uncertainty)
        _dump_json(temporary / storage["provenance_file"], {
            "source_artifacts_read": ["RF-2 grid artifact", "RF-5 temporal candidate-field artifact"],
            "rf5_relation_field_id": rf5["identity"]["relation_field_id"],
            "rf5_manifest_hash": rf5["manifest_hash"],
            "grid_manifest_hash": grid["manifest_hash"],
            "canonical_G_t_or_K_t_direct_read": False,
            "external_logs_read": False,
            "parent_writeback_performed": False,
        })
        _dump_json(temporary / storage["summary_file"], summary)
        _dump_json(temporary / storage["validation_file"], validation)
        _dump_json(temporary / storage["manifest_file"], {
            "contract_version": contract["contract_version"],
            "hash_algorithm": "sha256",
            "files": _manifest_entries(temporary, exclude={storage["manifest_file"]}),
        })
        os.replace(temporary, target)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return target


def validate_hodge_artifact(
    input_path: str | Path,
    rf5_artifact_dir: str | Path,
    grid_artifact_dir: str | Path,
) -> dict[str, Any]:
    root = Path(input_path)
    contract = _load_json(root / "contract.json")
    validate_contract(contract)
    _verify_manifest(root)
    grid_root = Path(grid_artifact_dir)
    grid = _load_grid_with_indices(grid_root)
    topology = generate_face_complex(grid)
    rf5 = _load_rf5_artifact(Path(rf5_artifact_dir), grid_root)
    identity = _load_json(root / "identity.json")
    validation = _load_json(root / "validation.json")
    topology_json = _load_json(root / "topology.json")
    if identity.get("rf5_manifest_hash") != rf5["manifest_hash"] or identity.get("grid_manifest_hash") != grid["manifest_hash"]:
        raise RelationFieldHodgeError("RF-6 parent artifact identity mismatch")
    if topology_json.get("face_count") != FACE_COUNT or topology_json.get("expected_first_betti_number") != 0:
        raise RelationFieldHodgeError("RF-6 topology metadata mismatch")
    with np.load(root / "faces.npz", allow_pickle=False) as loaded:
        if not np.array_equal(loaded["face_base_cell"], topology["face_base_cell"]):
            raise RelationFieldHodgeError("RF-6 face base-cell mismatch")
        if not np.array_equal(loaded["face_edge_ids"], topology["face_edge_ids"]):
            raise RelationFieldHodgeError("RF-6 face edge mismatch")
        if not np.array_equal(loaded["face_edge_signs"], topology["face_edge_signs"]):
            raise RelationFieldHodgeError("RF-6 face orientation mismatch")
    boundary_1 = csr_matrix(grid["incidence"], dtype=np.float64)
    boundary_2 = csr_matrix(topology["boundary_2"], dtype=np.float64)
    with np.load(root / "candidate_components.npz", allow_pickle=False) as loaded:
        input_flow = loaded["input_flow"].copy()
        gradient = loaded["gradient_flow"].copy()
        circulation = loaded["circulation_flow"].copy()
        harmonic = loaded["harmonic_flow"].copy()
        residual = loaded["numerical_residual_flow"].copy()
    if input_flow.shape != rf5["candidate_flow"].shape or not np.array_equal(input_flow, rf5["candidate_flow"]):
        raise RelationFieldHodgeError("RF-6 candidate input does not match RF-5")
    tolerance = contract["acceptance"]
    reconstruction = gradient + circulation + harmonic + residual
    if float(np.max(np.abs(input_flow - reconstruction))) > float(tolerance["reconstruction_tolerance"]):
        raise RelationFieldHodgeError("RF-6 reconstruction mismatch")
    if float(np.max(np.abs(harmonic))) > float(tolerance["harmonic_max_abs_tolerance"]):
        raise RelationFieldHodgeError("RF-6 harmonic component must be zero on the fixed complex")
    if float(np.max(np.abs(residual))) > float(tolerance["numerical_residual_tolerance"]):
        raise RelationFieldHodgeError("RF-6 numerical residual mismatch")
    for index in range(input_flow.shape[0]):
        divergence = np.asarray(boundary_1 @ circulation[index], dtype=np.float64)
        face_gradient = np.asarray(boundary_2.transpose() @ gradient[index], dtype=np.float64)
        if float(np.max(np.abs(divergence))) > float(tolerance["circulation_divergence_tolerance"]):
            raise RelationFieldHodgeError("RF-6 circulation divergence mismatch")
        if float(np.max(np.abs(face_gradient))) > float(tolerance["gradient_face_circulation_tolerance"]):
            raise RelationFieldHodgeError("RF-6 gradient face-circulation mismatch")
    if validation.get("rf6_hodge_decomposition_gate") != "passed":
        raise RelationFieldHodgeError("RF-6 validation gate did not pass")
    return validation


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--rf5-artifact", required=True)
    build.add_argument("--grid-artifact", required=True)
    build.add_argument("--output", required=True)
    build.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    validate = commands.add_parser("validate")
    validate.add_argument("--input", required=True)
    validate.add_argument("--rf5-artifact", required=True)
    validate.add_argument("--grid-artifact", required=True)
    args = parser.parse_args(argv)
    if args.command == "build":
        output = build_hodge_decomposition(
            args.rf5_artifact,
            args.grid_artifact,
            args.output,
            contract_path=args.contract,
        )
        print(json.dumps({"output": str(output), "status": "built"}, ensure_ascii=False, sort_keys=True))
    else:
        print(json.dumps(validate_hodge_artifact(args.input, args.rf5_artifact, args.grid_artifact), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
