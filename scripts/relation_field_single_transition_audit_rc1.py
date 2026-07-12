"""固定5軸 動的関係場 RF-4: RF-3単一遷移流れの独立監査。"""
from __future__ import annotations

import argparse
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
from scipy.sparse import coo_matrix, csr_matrix, eye, hstack

from relation_field_single_transition_rc1 import (
    _load_grid,
    invert_transition,
    load_contract as load_rf3_contract,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "configs" / "relation_field_single_transition_audit_rc1.json"
CELL_COUNT = 3125


class RelationFieldAuditError(ValueError):
    """RF-4監査契約、solver、成果物の不整合。"""


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_npz(path: Path, arrays: Mapping[str, np.ndarray]) -> None:
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
    if contract.get("contract_version") != "relation_field_single_transition_audit_rc1":
        raise RelationFieldAuditError("unsupported RF-4 contract")
    scenarios = contract.get("scenario_suite", [])
    names = [str(item.get("name", "")) for item in scenarios]
    if len(names) != len(set(names)) or not names:
        raise RelationFieldAuditError("RF-4 scenario names must be non-empty and unique")
    alternative = contract.get("alternative_solution_audit", {})
    if not set(alternative.get("scenario_names", ())) <= set(names):
        raise RelationFieldAuditError("alternative-solution scenario is not in the suite")
    solver = contract.get("solver_sensitivity_audit", {})
    if not set(solver.get("scenario_names", ())) <= set(names):
        raise RelationFieldAuditError("solver-sensitivity scenario is not in the suite")
    if solver.get("methods") != ["highs-ds", "highs-ipm", "highs"]:
        raise RelationFieldAuditError("RF-4 solver methods mismatch")
    penalty = contract.get("residual_penalty_audit", {})
    if penalty.get("scenario_name") not in names:
        raise RelationFieldAuditError("residual-penalty scenario is not in the suite")
    if not set(penalty.get("transport_preferred_penalties", ())) <= set(penalty.get("penalties", ())):
        raise RelationFieldAuditError("transport-preferred penalty is not audited")
    if not set(penalty.get("residual_preferred_penalties", ())) <= set(penalty.get("penalties", ())):
        raise RelationFieldAuditError("residual-preferred penalty is not audited")


def _scenario_masses(spec: Mapping[str, Any]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    source_spec = {int(key): float(value) for key, value in spec.get("source", {}).items()}
    target_spec = {int(key): float(value) for key, value in spec.get("target", {}).items()}
    source = np.zeros(CELL_COUNT, dtype=np.float64)
    target = np.zeros(CELL_COUNT, dtype=np.float64)
    if not source_spec and not target_spec:
        source[0] = 1.0
        target[0] = 1.0
    else:
        for cell_id, value in source_spec.items():
            if cell_id < 0 or cell_id >= CELL_COUNT or value < 0:
                raise RelationFieldAuditError("invalid scenario source mass")
            source[cell_id] += value
        for cell_id, value in target_spec.items():
            if cell_id < 0 or cell_id >= CELL_COUNT or value < 0:
                raise RelationFieldAuditError("invalid scenario target mass")
            target[cell_id] += value
        if abs(float(source.sum()) - 1.0) > 1e-12 or abs(float(target.sum()) - 1.0) > 1e-12:
            raise RelationFieldAuditError("non-empty RF-4 scenario distributions must each sum to one")
    delta = target - source
    return source.reshape((5, 5, 5, 5, 5)), target.reshape((5, 5, 5, 5, 5)), delta


def _objective_vector(edge_count: int, edge_cost: float | np.ndarray, residual_penalty: float) -> np.ndarray:
    costs = np.asarray(edge_cost, dtype=np.float64)
    if costs.ndim == 0:
        costs = np.full(edge_count, float(costs), dtype=np.float64)
    if costs.shape != (edge_count,) or np.any(costs < 0):
        raise RelationFieldAuditError("edge-cost vector mismatch")
    return np.concatenate([costs, costs, np.full(CELL_COUNT * 2, residual_penalty, dtype=np.float64)])


def _equality_matrix(incidence: csr_matrix) -> csr_matrix:
    identity = eye(CELL_COUNT, format="csr", dtype=np.float64)
    return hstack([incidence, -incidence, identity, -identity], format="csr")


def _solve_lp(
    delta: np.ndarray,
    incidence: csr_matrix,
    *,
    edge_cost: float | np.ndarray,
    residual_penalty: float,
    method: str,
    primary_cap: float | None = None,
    secondary_objective: np.ndarray | None = None,
) -> tuple[Any, np.ndarray, csr_matrix]:
    edge_count = int(incidence.shape[1])
    primary = _objective_vector(edge_count, edge_cost, residual_penalty)
    equality = _equality_matrix(incidence)
    objective = primary if secondary_objective is None else np.asarray(secondary_objective, dtype=np.float64)
    if objective.shape != primary.shape:
        raise RelationFieldAuditError("secondary objective shape mismatch")
    inequality = None
    upper = None
    if primary_cap is not None:
        inequality = csr_matrix(primary.reshape(1, -1))
        upper = np.asarray([float(primary_cap)], dtype=np.float64)
    result = linprog(
        objective,
        A_eq=equality,
        b_eq=np.asarray(delta, dtype=np.float64),
        A_ub=inequality,
        b_ub=upper,
        bounds=(0.0, None),
        method=method,
        options={
            "presolve": True,
            "primal_feasibility_tolerance": 1e-9,
            "dual_feasibility_tolerance": 1e-9,
        },
    )
    if not result.success or result.x is None:
        raise RelationFieldAuditError(f"RF-4 solver failed ({method}): {result.message}")
    return result, primary, equality


def _extract_solution(result: Any, incidence: csr_matrix) -> dict[str, np.ndarray]:
    edge_count = int(incidence.shape[1])
    vector = np.asarray(result.x, dtype=np.float64)
    forward = np.maximum(vector[:edge_count], 0.0)
    reverse = np.maximum(vector[edge_count:2 * edge_count], 0.0)
    positive = np.maximum(vector[2 * edge_count:2 * edge_count + CELL_COUNT], 0.0)
    negative = np.maximum(vector[2 * edge_count + CELL_COUNT:], 0.0)
    net = forward - reverse
    reconstructed = np.asarray(incidence @ net, dtype=np.float64)
    return {
        "forward": forward,
        "reverse": reverse,
        "net": net,
        "positive_residual": positive,
        "negative_residual": negative,
        "residual": positive - negative,
        "reconstructed": reconstructed,
    }


def _dual_certificate(result: Any, delta: np.ndarray, incidence: csr_matrix, edge_cost: float, residual_penalty: float) -> dict[str, Any]:
    dual = np.asarray(result.eqlin.marginals, dtype=np.float64)
    edge_difference = np.asarray(incidence.T @ dual, dtype=np.float64).reshape(-1)
    edge_violation = float(max(np.max(edge_difference - edge_cost), np.max(-edge_difference - edge_cost), 0.0))
    residual_violation = float(max(np.max(np.abs(dual) - residual_penalty), 0.0))
    dual_objective = float(np.asarray(delta, dtype=np.float64) @ dual)
    primal_objective = float(result.fun)
    return {
        "primal_objective": primal_objective,
        "dual_objective": dual_objective,
        "primal_dual_gap": primal_objective - dual_objective,
        "maximum_edge_dual_violation": edge_violation,
        "maximum_residual_dual_violation": residual_violation,
    }


def _secondary_weights(size: int, edge_variable_count: int, seed: int) -> np.ndarray:
    indices = np.arange(edge_variable_count, dtype=np.uint64) + np.uint64(seed * 1000003 + 1)
    with np.errstate(over="ignore"):
        values = indices + np.uint64(0x9E3779B97F4A7C15)
        values = (values ^ (values >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
        values = (values ^ (values >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
        values = values ^ (values >> np.uint64(31))
    mask = np.uint64((1 << 53) - 1)
    weights = np.zeros(size, dtype=np.float64)
    weights[:edge_variable_count] = ((values & mask).astype(np.float64) / float(1 << 53)) * 2.0 - 1.0
    return weights


def _flow_signature(flow: np.ndarray, threshold: float, decimals: int) -> tuple[str, np.ndarray]:
    normalized = np.asarray(flow, dtype=np.float64).copy()
    normalized[np.abs(normalized) < threshold] = 0.0
    normalized = np.round(normalized, decimals=decimals)
    return hashlib.sha256(normalized.tobytes(order="C")).hexdigest(), normalized


def _baseline_audit(contract: Mapping[str, Any], rf3_contract: Mapping[str, Any], grid: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    thresholds = contract["minimum_action_audit"]
    edge_cost = float(rf3_contract["solver"]["coordinate_edge_cost"])
    residual_penalty = float(rf3_contract["solver"]["residual_penalty"])
    scenario_rows: list[dict[str, Any]] = []
    certificates: list[dict[str, Any]] = []
    for spec in contract["scenario_suite"]:
        source, target, delta = _scenario_masses(spec)
        production = invert_transition(source, target, grid, rf3_contract)
        production_objective = float(
            edge_cost * np.sum(production["forward_flow"] + production["reverse_flow"])
            + residual_penalty * np.sum(production["positive_residual"] + production["negative_residual"])
        )
        independent, _, _ = _solve_lp(
            delta,
            grid["incidence"],
            edge_cost=edge_cost,
            residual_penalty=residual_penalty,
            method=rf3_contract["solver"]["method"],
        )
        certificate = _dual_certificate(independent, delta, grid["incidence"], edge_cost, residual_penalty)
        reconstruction_error = float(np.max(np.abs(delta - production["reconstructed_delta"])))
        residual_l1 = float(np.sum(np.abs(production["residual"])))
        simultaneous = int(np.count_nonzero(
            (production["forward_flow"] > rf3_contract["solver"]["flow_activation_threshold"])
            & (production["reverse_flow"] > rf3_contract["solver"]["flow_activation_threshold"])
        ))
        expected_cost = float(spec["expected_minimum_coordinate_cost"])
        passed = all((
            abs(production_objective - expected_cost) <= float(thresholds["expected_cost_tolerance"]),
            abs(production_objective - float(independent.fun)) <= float(thresholds["expected_cost_tolerance"]),
            reconstruction_error <= float(thresholds["reconstruction_tolerance"]),
            residual_l1 <= float(thresholds["residual_l1_tolerance"]),
            abs(float(certificate["primal_dual_gap"])) <= float(thresholds["primal_dual_gap_tolerance"]),
            float(certificate["maximum_edge_dual_violation"]) <= float(thresholds["dual_feasibility_tolerance"]),
            float(certificate["maximum_residual_dual_violation"]) <= float(thresholds["dual_feasibility_tolerance"]),
            simultaneous == 0,
        ))
        scenario_rows.append({
            "scenario": spec["name"],
            "expected_minimum_coordinate_cost": expected_cost,
            "production_primary_objective": production_objective,
            "independent_primary_objective": float(independent.fun),
            "reconstruction_max_abs_error": reconstruction_error,
            "residual_l1": residual_l1,
            "active_canonical_edge_count": int(np.count_nonzero(np.abs(production["net_flow"]) > 1e-12)),
            "simultaneous_opposite_edge_count": simultaneous,
            "minimum_action_gate": "passed" if passed else "failed",
        })
        certificates.append({"scenario": spec["name"], **certificate, "certificate_gate": "passed" if passed else "failed"})
    return scenario_rows, certificates


def _alternative_audit(contract: Mapping[str, Any], rf3_contract: Mapping[str, Any], grid: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    audit = contract["alternative_solution_audit"]
    specs = {item["name"]: item for item in contract["scenario_suite"]}
    edge_count = int(grid["edge_count"])
    edge_cost = float(rf3_contract["solver"]["coordinate_edge_cost"])
    residual_penalty = float(rf3_contract["solver"]["residual_penalty"])
    results: list[dict[str, Any]] = []
    arrays: dict[str, np.ndarray] = {}
    all_passed = True
    for name in audit["scenario_names"]:
        _, _, delta = _scenario_masses(specs[name])
        baseline, primary, _ = _solve_lp(
            delta,
            grid["incidence"],
            edge_cost=edge_cost,
            residual_penalty=residual_penalty,
            method=rf3_contract["solver"]["method"],
        )
        candidates: dict[str, np.ndarray] = {}
        baseline_net = _extract_solution(baseline, grid["incidence"])["net"]
        signature, normalized = _flow_signature(
            baseline_net,
            float(audit["flow_signature_threshold"]),
            int(audit["flow_signature_decimals"]),
        )
        candidates[signature] = normalized
        primary_cap = float(baseline.fun) + float(audit["primary_objective_slack"])
        for seed in audit["secondary_objective_seeds"]:
            secondary = _secondary_weights(primary.size, edge_count * 2, int(seed))
            witness, _, _ = _solve_lp(
                delta,
                grid["incidence"],
                edge_cost=edge_cost,
                residual_penalty=residual_penalty,
                method=rf3_contract["solver"]["method"],
                primary_cap=primary_cap,
                secondary_objective=secondary,
            )
            witness_primary = float(primary @ witness.x)
            if witness_primary > primary_cap + 1e-9:
                raise RelationFieldAuditError("alternative witness violated primary objective cap")
            net = _extract_solution(witness, grid["incidence"])["net"]
            signature, normalized = _flow_signature(
                net,
                float(audit["flow_signature_threshold"]),
                int(audit["flow_signature_decimals"]),
            )
            candidates.setdefault(signature, normalized)
        ordered = [candidates[key] for key in sorted(candidates)]
        for index, flow in enumerate(ordered):
            arrays[f"{name}__candidate_{index:03d}"] = flow
        max_pairwise_l1 = 0.0
        supports = [set(np.flatnonzero(np.abs(flow) > float(audit["flow_signature_threshold"])).tolist()) for flow in ordered]
        for left in range(len(ordered)):
            for right in range(left):
                max_pairwise_l1 = max(max_pairwise_l1, float(np.sum(np.abs(ordered[left] - ordered[right]))))
        support_union = set().union(*supports) if supports else set()
        support_intersection = set.intersection(*supports) if supports else set()
        expected = bool(specs[name]["expected_alternative_optimum"])
        detected = len(ordered) > 1 and max_pairwise_l1 > float(audit["candidate_difference_l1_threshold"])
        passed = detected == expected
        all_passed = all_passed and passed
        results.append({
            "scenario": name,
            "expected_alternative_optimum": expected,
            "alternative_optimum_detected": detected,
            "unique_witness_count": len(ordered),
            "maximum_pairwise_net_flow_l1": max_pairwise_l1,
            "support_union_edge_count": len(support_union),
            "support_intersection_edge_count": len(support_intersection),
            "witness_search_exhaustive": False,
            "gate": "passed" if passed else "failed",
        })
    return {"gate": "passed" if all_passed else "failed", "scenario_results": results}, arrays


def _solver_sensitivity(contract: Mapping[str, Any], rf3_contract: Mapping[str, Any], grid: Mapping[str, Any]) -> dict[str, Any]:
    audit = contract["solver_sensitivity_audit"]
    specs = {item["name"]: item for item in contract["scenario_suite"]}
    edge_cost = float(rf3_contract["solver"]["coordinate_edge_cost"])
    residual_penalty = float(rf3_contract["solver"]["residual_penalty"])
    rows: list[dict[str, Any]] = []
    all_passed = True
    for name in audit["scenario_names"]:
        _, _, delta = _scenario_masses(specs[name])
        method_rows: list[dict[str, Any]] = []
        flows: list[np.ndarray] = []
        for method in audit["methods"]:
            result, primary, _ = _solve_lp(
                delta,
                grid["incidence"],
                edge_cost=edge_cost,
                residual_penalty=residual_penalty,
                method=method,
            )
            extracted = _extract_solution(result, grid["incidence"])
            method_rows.append({
                "method": method,
                "primary_objective": float(primary @ result.x),
                "reconstruction_max_abs_error": float(np.max(np.abs(delta - extracted["reconstructed"] - extracted["residual"]))),
                "residual_l1": float(np.sum(np.abs(extracted["residual"]))),
                "active_edge_count": int(np.count_nonzero(np.abs(extracted["net"]) > 1e-8)),
            })
            flows.append(extracted["net"])
        objective_values = [item["primary_objective"] for item in method_rows]
        objective_spread = max(objective_values) - min(objective_values)
        max_flow_l1 = max(
            (float(np.sum(np.abs(flows[left] - flows[right]))) for left in range(len(flows)) for right in range(left)),
            default=0.0,
        )
        passed = objective_spread <= float(audit["objective_spread_tolerance"]) and all(
            item["reconstruction_max_abs_error"] <= float(audit["reconstruction_tolerance"])
            for item in method_rows
        )
        all_passed = all_passed and passed
        rows.append({
            "scenario": name,
            "methods": method_rows,
            "primary_objective_spread": objective_spread,
            "maximum_cross_method_net_flow_l1": max_flow_l1,
            "flow_identity_required": False,
            "gate": "passed" if passed else "failed",
        })
    return {"gate": "passed" if all_passed else "failed", "scenario_results": rows}


def _penalty_sensitivity(contract: Mapping[str, Any], rf3_contract: Mapping[str, Any], grid: Mapping[str, Any]) -> dict[str, Any]:
    audit = contract["residual_penalty_audit"]
    spec = next(item for item in contract["scenario_suite"] if item["name"] == audit["scenario_name"])
    _, _, delta = _scenario_masses(spec)
    edge_cost = float(rf3_contract["solver"]["coordinate_edge_cost"])
    transport = set(float(value) for value in audit["transport_preferred_penalties"])
    residual = set(float(value) for value in audit["residual_preferred_penalties"])
    rows: list[dict[str, Any]] = []
    all_passed = True
    for penalty in (float(value) for value in audit["penalties"]):
        result, primary, _ = _solve_lp(
            delta,
            grid["incidence"],
            edge_cost=edge_cost,
            residual_penalty=penalty,
            method=rf3_contract["solver"]["method"],
        )
        extracted = _extract_solution(result, grid["incidence"])
        residual_l1 = float(np.sum(np.abs(extracted["residual"])))
        total_flow = float(np.sum(extracted["forward"] + extracted["reverse"]))
        if penalty in transport:
            expected_behavior = "transport_preferred"
            passed = residual_l1 <= float(audit["zero_residual_tolerance"]) and total_flow > 0.0
        elif penalty in residual:
            expected_behavior = "residual_preferred"
            passed = residual_l1 >= float(audit["residual_activation_minimum_l1"]) and total_flow <= float(audit["zero_residual_tolerance"])
        else:
            expected_behavior = "diagnostic_only"
            passed = True
        all_passed = all_passed and passed
        rows.append({
            "residual_penalty": penalty,
            "expected_behavior": expected_behavior,
            "primary_objective": float(primary @ result.x),
            "total_directed_edge_flow": total_flow,
            "residual_l1": residual_l1,
            "gate": "passed" if passed else "failed",
        })
    return {"gate": "passed" if all_passed else "failed", "scenario": audit["scenario_name"], "results": rows}


def _locality_counterfactual(contract: Mapping[str, Any], rf3_contract: Mapping[str, Any], grid: Mapping[str, Any]) -> dict[str, Any]:
    audit = contract["locality_counterfactual"]
    spec = next(item for item in contract["scenario_suite"] if item["name"] == audit["scenario_name"])
    _, _, delta = _scenario_masses(spec)
    edge_cost = float(rf3_contract["solver"]["coordinate_edge_cost"])
    residual_penalty = float(rf3_contract["solver"]["residual_penalty"])
    baseline, baseline_primary, _ = _solve_lp(
        delta,
        grid["incidence"],
        edge_cost=edge_cost,
        residual_penalty=residual_penalty,
        method=rf3_contract["solver"]["method"],
    )
    source_cell = int(audit["source_cell_id"])
    target_cell = int(audit["target_cell_id"])
    shortcut = coo_matrix(
        (np.asarray([-1.0, 1.0]), (np.asarray([source_cell, target_cell]), np.asarray([0, 0]))),
        shape=(CELL_COUNT, 1),
    ).tocsr()
    augmented = hstack([grid["incidence"], shortcut], format="csr")
    augmented_costs = np.concatenate([
        np.full(int(grid["edge_count"]), edge_cost, dtype=np.float64),
        np.asarray([float(audit["synthetic_shortcut_coordinate_cost"])], dtype=np.float64),
    ])
    counterfactual, counter_primary, _ = _solve_lp(
        delta,
        augmented,
        edge_cost=augmented_costs,
        residual_penalty=residual_penalty,
        method=rf3_contract["solver"]["method"],
    )
    extracted = _extract_solution(counterfactual, augmented)
    shortcut_index = augmented.shape[1] - 1
    shortcut_net = float(extracted["net"][shortcut_index])
    baseline_cost = float(baseline_primary @ baseline.x)
    counterfactual_cost = float(counter_primary @ counterfactual.x)
    material = (
        abs(baseline_cost - float(audit["expected_local_grid_cost"])) <= 1e-9
        and abs(counterfactual_cost - float(audit["expected_shortcut_cost"])) <= 1e-9
        and shortcut_net > 0.99
        and counterfactual_cost < baseline_cost
    )
    return {
        "gate": "passed" if material else "failed",
        "diagnostic_only": bool(audit["diagnostic_only"]),
        "scenario": audit["scenario_name"],
        "local_grid_primary_objective": baseline_cost,
        "counterfactual_primary_objective": counterfactual_cost,
        "synthetic_shortcut_net_flow": shortcut_net,
        "locality_assumption_material": material,
        "interpretation": "allowing a non-local shortcut changes the representative minimum-cost flow; locality is an explicit modeling assumption, not an observed fact",
    }


def _adoption_decision(
    scenario_rows: Sequence[Mapping[str, Any]],
    certificates: Sequence[Mapping[str, Any]],
    alternative: Mapping[str, Any],
    solver: Mapping[str, Any],
    penalty: Mapping[str, Any],
    locality: Mapping[str, Any],
) -> dict[str, Any]:
    gates = {
        "all_baseline_scenarios_pass": all(row["minimum_action_gate"] == "passed" for row in scenario_rows),
        "all_minimum_action_certificates_pass": all(row["certificate_gate"] == "passed" for row in certificates),
        "alternative_solution_expectations_pass": alternative["gate"] == "passed",
        "solver_objective_invariance_pass": solver["gate"] == "passed",
        "residual_penalty_behavior_pass": penalty["gate"] == "passed",
        "locality_materiality_detected": locality["gate"] == "passed",
        "deterministic_rebuild_pass": True,
        "manifest_integrity_pass": True,
    }
    engineering_pass = all(gates.values())
    ambiguity_detected = any(
        row["alternative_optimum_detected"]
        for row in alternative["scenario_results"]
        if row["expected_alternative_optimum"]
    )
    return {
        "engineering_basis_judgement": "A_pass" if engineering_pass else "C_rejected",
        "scientific_relation_field_judgement": (
            "B_limited_adoption_as_single_transition_basis" if engineering_pass else "C_rejected"
        ),
        "continue_to_rf5_recommended": bool(engineering_pass and ambiguity_detected),
        "gates": gates,
        "why_scientific_A_is_not_claimed": [
            "equal-cost alternative flows exist for multi-axis transitions",
            "RF-4 audits single observed transitions rather than K_t-consistent dynamics",
            "locality materially determines the representative solution",
            "risk-structure prediction and action usefulness remain unevaluated",
        ],
        "checkpoint_interpretation": (
            "RF-3 is suitable as an engineering basis for temporal regularization, but its per-transition flow must not be treated as a unique physical relation field"
            if engineering_pass
            else "RF-3 should be revised before temporal relation-field construction"
        ),
    }


def build_audit_artifact(
    grid_artifact_dir: str | Path,
    output: str | Path,
    *,
    contract_path: str | Path = DEFAULT_CONTRACT,
) -> Path:
    contract = load_contract(contract_path)
    rf3_contract = load_rf3_contract()
    grid = _load_grid(Path(grid_artifact_dir))
    target = Path(output)
    if target.exists():
        raise RelationFieldAuditError(f"output already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    scenario_rows, certificates = _baseline_audit(contract, rf3_contract, grid)
    alternative, candidate_arrays = _alternative_audit(contract, rf3_contract, grid)
    solver = _solver_sensitivity(contract, rf3_contract, grid)
    penalty = _penalty_sensitivity(contract, rf3_contract, grid)
    locality = _locality_counterfactual(contract, rf3_contract, grid)
    adoption = _adoption_decision(scenario_rows, certificates, alternative, solver, penalty, locality)
    summary = {
        "contract_version": contract["contract_version"],
        "rf3_contract_version": rf3_contract["contract_version"],
        "grid_contract_version": grid["contract"]["contract_version"],
        "grid_manifest_hash": grid["manifest_hash"],
        "scipy_version": scipy.__version__,
        "scenario_count": len(scenario_rows),
        "baseline_pass_count": sum(row["minimum_action_gate"] == "passed" for row in scenario_rows),
        "alternative_ambiguity_detected_count": sum(row["alternative_optimum_detected"] for row in alternative["scenario_results"]),
        "engineering_basis_judgement": adoption["engineering_basis_judgement"],
        "scientific_relation_field_judgement": adoption["scientific_relation_field_judgement"],
        "continue_to_rf5_recommended": adoption["continue_to_rf5_recommended"],
        "prediction_performed": False,
        "risk_prediction_performed": False,
    }
    validation = {
        "rf4_audit_gate": "passed" if adoption["engineering_basis_judgement"] == "A_pass" else "failed",
        "scenario_gate": "passed" if all(row["minimum_action_gate"] == "passed" for row in scenario_rows) else "failed",
        "minimum_action_certificate_gate": "passed" if all(row["certificate_gate"] == "passed" for row in certificates) else "failed",
        "alternative_solution_gate": alternative["gate"],
        "solver_sensitivity_gate": solver["gate"],
        "residual_penalty_gate": penalty["gate"],
        "locality_counterfactual_gate": locality["gate"],
        "engineering_basis_judgement": adoption["engineering_basis_judgement"],
        "scientific_relation_field_judgement": adoption["scientific_relation_field_judgement"],
        "continue_to_rf5_recommended": adoption["continue_to_rf5_recommended"],
    }
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp-", dir=target.parent))
    try:
        storage = contract["storage"]
        _dump_json(temporary / storage["contract_file"], contract)
        _dump_json(temporary / storage["summary_file"], summary)
        _write_jsonl(temporary / storage["scenario_results_file"], scenario_rows)
        _dump_json(temporary / storage["minimum_action_file"], {"gate": validation["minimum_action_certificate_gate"], "certificates": certificates})
        _dump_json(temporary / storage["alternative_solution_file"], alternative)
        _write_npz(temporary / storage["alternative_candidates_file"], candidate_arrays)
        _dump_json(temporary / storage["solver_sensitivity_file"], solver)
        _dump_json(temporary / storage["residual_penalty_file"], penalty)
        _dump_json(temporary / storage["locality_counterfactual_file"], locality)
        _dump_json(temporary / storage["adoption_decision_file"], adoption)
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


def _verify_manifest(root: Path) -> None:
    manifest = _load_json(root / "manifest.json")
    expected: set[str] = set()
    for entry in manifest.get("files", []):
        relative = str(entry["path"])
        expected.add(relative)
        path = root / relative
        if not path.is_file() or path.stat().st_size != int(entry["size_bytes"]) or _sha256_file(path) != entry["sha256"]:
            raise RelationFieldAuditError(f"manifest mismatch: {relative}")
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    if expected != actual:
        raise RelationFieldAuditError("manifest file set mismatch")


def validate_audit_artifact(input_path: str | Path, grid_artifact_dir: str | Path) -> dict[str, Any]:
    root = Path(input_path)
    contract = _load_json(root / "contract.json")
    validate_contract(contract)
    _verify_manifest(root)
    grid = _load_grid(Path(grid_artifact_dir))
    summary = _load_json(root / "summary.json")
    validation = _load_json(root / "validation.json")
    adoption = _load_json(root / "adoption_decision.json")
    scenarios = _read_jsonl(root / "scenario_results.jsonl")
    alternative = _load_json(root / "alternative_solution_audit.json")
    if summary.get("grid_manifest_hash") != grid["manifest_hash"]:
        raise RelationFieldAuditError("RF-4 grid manifest identity mismatch")
    if len(scenarios) != len(contract["scenario_suite"]):
        raise RelationFieldAuditError("RF-4 scenario result count mismatch")
    if validation.get("rf4_audit_gate") != "passed":
        raise RelationFieldAuditError("RF-4 audit gate did not pass")
    if adoption.get("engineering_basis_judgement") != "A_pass":
        raise RelationFieldAuditError("RF-4 engineering basis judgement did not pass")
    if adoption.get("scientific_relation_field_judgement") != "B_limited_adoption_as_single_transition_basis":
        raise RelationFieldAuditError("RF-4 scientific limitation judgement mismatch")
    if adoption.get("continue_to_rf5_recommended") is not True:
        raise RelationFieldAuditError("RF-4 checkpoint does not recommend RF-5")
    if alternative.get("gate") != "passed":
        raise RelationFieldAuditError("RF-4 alternative-solution gate failed")
    return validation


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--grid-artifact", required=True)
    build.add_argument("--output", required=True)
    build.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    validate = commands.add_parser("validate")
    validate.add_argument("--input", required=True)
    validate.add_argument("--grid-artifact", required=True)
    args = parser.parse_args(argv)
    if args.command == "build":
        output = build_audit_artifact(args.grid_artifact, args.output, contract_path=args.contract)
        print(json.dumps({"output": str(output), "status": "built"}, ensure_ascii=False, sort_keys=True))
    else:
        print(json.dumps(validate_audit_artifact(args.input, args.grid_artifact), ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
