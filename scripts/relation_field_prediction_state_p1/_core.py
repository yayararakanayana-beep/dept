#!/usr/bin/env python3
"""P1: 因果的な関係場予測状態 X_t の系列を構築・独立再検証する。"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from generic_relation_field_g2 import (
    _canonical_json,
    _json_dump,
    _json_load,
    _load_npz,
    _load_structure_artifact,
    _sha256_bytes,
    _sha256_file,
    _verify_manifest,
    _write_deterministic_npz,
    _write_manifest,
    build_fixed5_history_view,
    validate_history_view,
    validate_structure_artifact,
)
from generic_relation_field_g3 import (
    _array_groups,
    _array_hash,
    _canonical_hash,
    _canonicalize_array,
    _mapping,
    _payload_path,
    _read_semantic,
    _registries,
    _tree_hash,
    load_validation_profile as load_g3_validation_profile,
)
from relation_field_axis_coupling_innovation_rc1 import (
    build_axis_coupling_innovation,
    validate_axis_coupling_innovation,
)
from relation_field_hodge_decomposition_rc1 import (
    build_hodge_decomposition,
    validate_hodge_artifact,
)
from relation_field_risk_structure_rc1 import (
    build_risk_structure,
    validate_risk_structure,
)
from relation_field_shape_dynamics_rc1 import (
    build_shape_dynamics,
    validate_shape_dynamics,
)
from relation_field_single_transition_rc1 import (
    build_transition_field,
    validate_transition_artifact,
)
from relation_field_temporal_consistency_rc1 import (
    build_temporal_relation_field,
    validate_temporal_relation_field,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "configs" / "relation_field_prediction_state_p1_contract.json"
DEFAULT_PROFILE = ROOT / "configs" / "relation_field_prediction_state_p1_extraction_profile.json"
DEFAULT_RISK_REGISTRY = ROOT / "configs" / "relation_field_prediction_state_p1_risk_registry.json"
P1_STAGES = ("RF-3", "RF-5", "RF-6", "RF-7", "RF-8", "RF-9")


class RelationFieldPredictionStateP1Error(ValueError):
    """P1契約、親成果物、因果境界、状態、差分の不整合。"""


def _repo_path(raw: str | Path) -> Path:
    path = (ROOT / Path(raw)).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
    if path != ROOT and ROOT not in path.parents:
        raise RelationFieldPredictionStateP1Error(f"path escapes repository: {raw}")
    return path


def _canonical_digest(value: Any) -> str:
    return _sha256_bytes(_canonical_json(value))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise RelationFieldPredictionStateP1Error(f"{path}:{line_number} must contain an object")
            rows.append(value)
    return rows


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def load_contract(path: str | Path = DEFAULT_CONTRACT) -> dict[str, Any]:
    contract = _json_load(Path(path))
    validate_contract(contract)
    return contract


def validate_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("contract_version") != "relation_field_prediction_state_p1":
        raise RelationFieldPredictionStateP1Error("unsupported P1 contract")
    scope = _mapping(contract.get("scope"), "scope")
    forbidden_true = (
        "prediction_model_implementation",
        "continuous_precursor_coordinate_implementation",
        "future_target_generation",
        "prediction_accuracy_evaluation",
        "irreversibility_truth_generation",
        "action_evaluation_or_selection",
        "task3_direct_prediction_integration",
    )
    if any(scope.get(key) is not False for key in forbidden_true):
        raise RelationFieldPredictionStateP1Error("P1 scope boundary changed")
    input_contract = _mapping(contract.get("input"), "input")
    if tuple(input_contract.get("required_parent_stages", ())) != P1_STAGES:
        raise RelationFieldPredictionStateP1Error("P1 parent stage sequence mismatch")
    if set(input_contract.get("forbidden_parent_stages", ())) != {"RF-4", "RF-10"}:
        raise RelationFieldPredictionStateP1Error("P1 forbidden parent stages changed")
    if int(input_contract.get("minimum_origin_t", -1)) < 3:
        raise RelationFieldPredictionStateP1Error("P1 origin is too early for RF-9")
    state = _mapping(contract.get("state"), "state")
    if state.get("canonical_state_form") != "identity_keyed_variable_collection":
        raise RelationFieldPredictionStateP1Error("P1 state must remain identity keyed")
    if state.get("unavailable_value_zero_fill_forbidden") is not True:
        raise RelationFieldPredictionStateP1Error("P1 must not zero fill unavailable values")
    differences = _mapping(contract.get("differences"), "differences")
    required_difference_guards = (
        "same_feature_id_required",
        "same_scope_identity_required",
        "same_unit_required",
        "same_normalization_required",
        "same_shape_required",
        "missing_or_incomparable_is_unavailable_not_zero",
    )
    if any(differences.get(key) is not True for key in required_difference_guards):
        raise RelationFieldPredictionStateP1Error("P1 difference comparability guards changed")
    if contract.get("risk_registry", {}).get("single_scalar_risk_score_forbidden") is not True:
        raise RelationFieldPredictionStateP1Error("P1 must preserve parallel risk structures")
    storage = _mapping(contract.get("storage"), "storage")
    required_storage = {
        "origin_container_dir", "origin_name_format", "history_view_dir", "parent_artifact_dir",
        "parent_stage_dirs", "state_dir", "base_state_file", "base_state_index_file",
        "semantic_state_file", "candidate_records_file", "risk_state_file",
        "first_difference_file", "second_difference_file", "difference_index_file",
        "origin_identity_file", "origin_validation_file", "origin_manifest_file",
        "series_identity_file", "series_index_file", "series_validation_file", "series_manifest_file",
    }
    if not required_storage <= set(storage):
        raise RelationFieldPredictionStateP1Error("P1 storage contract is incomplete")
    if set(storage["parent_stage_dirs"]) != set(P1_STAGES):
        raise RelationFieldPredictionStateP1Error("P1 parent directory mapping mismatch")
    if storage.get("origin_manifest_file") != "manifest.json" or storage.get("series_manifest_file") != "manifest.json":
        raise RelationFieldPredictionStateP1Error("P1 manifests must use manifest.json")
    for key, value in storage.items():
        if key == "parent_stage_dirs" or not isinstance(value, str):
            continue
        path = Path(value)
        if path.is_absolute() or ".." in path.parts or not path.parts:
            raise RelationFieldPredictionStateP1Error(f"unsafe P1 storage path: {key}")
    for value in storage["parent_stage_dirs"].values():
        path = Path(str(value))
        if path.is_absolute() or ".." in path.parts or not path.parts:
            raise RelationFieldPredictionStateP1Error("unsafe P1 parent stage path")


def load_extraction_profile(path: str | Path = DEFAULT_PROFILE) -> dict[str, Any]:
    profile = _json_load(Path(path))
    validate_extraction_profile(profile)
    return profile


def validate_extraction_profile(profile: Mapping[str, Any]) -> None:
    if profile.get("profile_id") != "relation_field_prediction_state_p1_extraction_profile":
        raise RelationFieldPredictionStateP1Error("P1 extraction profile ID mismatch")
    if tuple(profile.get("included_stages", ())) != P1_STAGES:
        raise RelationFieldPredictionStateP1Error("P1 extraction stage sequence mismatch")
    if set(profile.get("excluded_stages", ())) != {"RF-4", "RF-10"}:
        raise RelationFieldPredictionStateP1Error("P1 extraction exclusions changed")
    g3_path = _repo_path(str(profile.get("source_g3_profile", "")))
    source = load_g3_validation_profile(g3_path)
    numeric_ids = {
        str(entry["payload_id"])
        for entry in source["numeric_payloads"]
        if str(entry["stage"]) in P1_STAGES
    }
    selectors = _mapping(profile.get("numeric_selectors"), "numeric_selectors")
    if set(selectors) != numeric_ids:
        raise RelationFieldPredictionStateP1Error("P1 numeric selector coverage mismatch")
    valid_modes = {"whole", "last_row", "latest_candidate_family", "mixed_last_row"}
    if any(_mapping(value, "numeric selector").get("mode") not in valid_modes for value in selectors.values()):
        raise RelationFieldPredictionStateP1Error("unsupported P1 numeric selector mode")
    current = _mapping(profile.get("current_distribution"), "current_distribution")
    if current.get("dimension_roles") != ["cell"]:
        raise RelationFieldPredictionStateP1Error("current distribution must be cell keyed")
    policy = _mapping(profile.get("difference_policy"), "difference_policy")
    if policy.get("eligible_dtype_kinds") != ["f"]:
        raise RelationFieldPredictionStateP1Error("P1 backward differences must remain floating-only")


def load_risk_registry(path: str | Path = DEFAULT_RISK_REGISTRY) -> dict[str, Any]:
    registry = _json_load(Path(path))
    validate_risk_registry(registry)
    return registry


def validate_risk_registry(registry: Mapping[str, Any]) -> None:
    if registry.get("registry_version") != "relation_field_prediction_state_p1_risk_registry":
        raise RelationFieldPredictionStateP1Error("P1 risk registry version mismatch")
    if registry.get("extensible") is not True or registry.get("single_scalar_risk_score_forbidden") is not True:
        raise RelationFieldPredictionStateP1Error("P1 risk registry must remain extensible and parallel")
    entries = registry.get("entries")
    if not isinstance(entries, list) or not entries:
        raise RelationFieldPredictionStateP1Error("P1 risk registry is empty")
    ids = [str(entry.get("risk_structure_id", "")) for entry in entries]
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        raise RelationFieldPredictionStateP1Error("P1 risk structure IDs must be unique")
    required = {
        "overconvergence", "fixation", "divergence", "recovery_margin_reduction"
    }
    primary = {
        str(entry["risk_structure_id"])
        for entry in entries
        if entry.get("role") == "required_primary"
    }
    if primary != required:
        raise RelationFieldPredictionStateP1Error("P1 required primary risk set mismatch")


def _selected_g3_profile(profile: Mapping[str, Any]) -> dict[str, Any]:
    source = load_g3_validation_profile(_repo_path(str(profile["source_g3_profile"])))
    selected = copy.deepcopy(source)
    selected["numeric_payloads"] = [
        value for value in source["numeric_payloads"] if str(value["stage"]) in P1_STAGES
    ]
    selected["semantic_payloads"] = [
        value for value in source["semantic_payloads"] if str(value["stage"]) in P1_STAGES
    ]
    selected["source_roots"] = ["grid", "trajectory", "rf3", "rf5", "rf6", "rf7", "rf8", "rf9"]
    selected["source_identity_files"] = {
        key: value for key, value in source["source_identity_files"].items() if key in {"rf3", "rf5", "rf6", "rf7", "rf8", "rf9"}
    }
    return selected


def _source_map(trajectory: Path, grid: Path, parents: Mapping[str, Path]) -> dict[str, Path]:
    return {
        "grid": grid,
        "trajectory": trajectory,
        "rf3": parents["RF-3"],
        "rf5": parents["RF-5"],
        "rf6": parents["RF-6"],
        "rf7": parents["RF-7"],
        "rf8": parents["RF-8"],
        "rf9": parents["RF-9"],
    }


def _select_last_path(payload: Any, dotted: str) -> None:
    if not isinstance(payload, dict):
        raise RelationFieldPredictionStateP1Error("semantic terminal selector requires an object")
    current: Any = payload
    parts = dotted.split(".")
    for part in parts[:-1]:
        if not isinstance(current, dict) or part not in current:
            raise RelationFieldPredictionStateP1Error(f"semantic selector path is absent: {dotted}")
        current = current[part]
    leaf = parts[-1]
    if not isinstance(current, dict) or not isinstance(current.get(leaf), list) or not current[leaf]:
        raise RelationFieldPredictionStateP1Error(f"semantic selector list is absent: {dotted}")
    current[leaf] = [copy.deepcopy(current[leaf][-1])]


def _semantic_snapshot(
    extraction: Mapping[str, Any],
    sources: Mapping[str, Path],
    structure: Mapping[str, Any],
) -> dict[str, Any]:
    g3 = _selected_g3_profile(extraction)
    selectors = extraction.get("semantic_selectors", {})
    default = extraction["default_semantic_selector"]
    axis_ids = [str(row["axis_id"]) for row in structure["axis_registry"]["records"]]
    records: list[dict[str, Any]] = []
    for raw in g3["semantic_payloads"]:
        entry = _mapping(raw, "semantic payload")
        path = _payload_path(entry, sources)
        if not path.is_file():
            raise RelationFieldPredictionStateP1Error(f"semantic source is missing: {entry['payload_id']}")
        payload = _read_semantic(path, str(entry.get("format", "json")))
        selector = _mapping(selectors.get(entry["payload_id"], default), "semantic selector")
        if selector.get("mode") == "last_list_items":
            payload = copy.deepcopy(payload)
            for dotted in selector.get("paths", []):
                _select_last_path(payload, str(dotted))
        elif selector.get("mode") != "whole":
            raise RelationFieldPredictionStateP1Error("unsupported P1 semantic selector")
        records.append({
            "payload_id": entry["payload_id"],
            "stage": entry["stage"],
            "source_file": f"{entry['root']}/{entry['path']}",
            "source_sha256": _sha256_file(path),
            "axis_registry_ids": axis_ids,
            "axis_registry_hash": _canonical_hash(axis_ids),
            "payload_hash": _canonical_hash(payload),
            "payload": payload,
        })
    stages = {str(row["stage"]) for row in records}
    if stages != set(P1_STAGES):
        raise RelationFieldPredictionStateP1Error("P1 semantic stage coverage mismatch")
    return {
        "semantic_state_version": "relation_field_prediction_state_p1_semantic",
        "payload_count": len(records),
        "records": records,
    }


def _select_numeric_payload(
    loaded: Mapping[str, np.ndarray],
    groups: Mapping[str, tuple[list[Any], str | None]],
    selector: Mapping[str, Any],
) -> dict[str, tuple[np.ndarray, list[Any], str | None]]:
    mode = str(selector["mode"])
    result: dict[str, tuple[np.ndarray, list[Any], str | None]] = {}
    if mode == "whole":
        for key, value in loaded.items():
            roles, transform = groups[key]
            result[key] = (np.asarray(value), list(roles), transform)
        return result
    if mode == "last_row":
        for key, value in loaded.items():
            roles, transform = groups[key]
            array = np.asarray(value)
            if array.ndim < 1 or array.shape[0] < 1:
                raise RelationFieldPredictionStateP1Error(f"cannot select last row: {key}")
            result[key] = (array[-1], list(roles[1:]), transform)
        return result
    if mode == "mixed_last_row":
        static = {str(value) for value in selector.get("static_keys", [])}
        for key, value in loaded.items():
            roles, transform = groups[key]
            array = np.asarray(value)
            if key in static:
                result[key] = (array, list(roles), transform)
            else:
                if array.ndim < 1 or array.shape[0] < 1:
                    raise RelationFieldPredictionStateP1Error(f"cannot select mixed last row: {key}")
                result[key] = (array[-1], list(roles[1:]), transform)
        return result
    if mode != "latest_candidate_family":
        raise RelationFieldPredictionStateP1Error(f"unsupported numeric selection mode: {mode}")
    index_key = str(selector["transition_index_key"])
    offset_key = str(selector["offset_key"])
    transition_rows = {str(value) for value in selector.get("transition_row_keys", [])}
    index = np.asarray(loaded[index_key], dtype=np.int64)
    if index.ndim != 1 or index.size == 0:
        raise RelationFieldPredictionStateP1Error("candidate transition index is empty")
    latest = int(np.max(index))
    mask = index == latest
    count = int(np.count_nonzero(mask))
    for key, value in loaded.items():
        roles, transform = groups[key]
        array = np.asarray(value)
        if key == offset_key:
            result[key] = (np.asarray([0, count], dtype=array.dtype), list(roles), transform)
        elif key in transition_rows:
            if array.ndim < 1 or latest >= array.shape[0]:
                raise RelationFieldPredictionStateP1Error(f"candidate transition row is absent: {key}")
            result[key] = (array[latest], list(roles[1:]), transform)
        elif array.ndim >= 1 and array.shape[0] == index.size:
            result[key] = (array[mask], list(roles), transform)
        else:
            raise RelationFieldPredictionStateP1Error(f"candidate array cannot be aligned: {key}")
    return result


def _difference_eligible(key: str, array: np.ndarray, extraction: Mapping[str, Any]) -> bool:
    policy = extraction["difference_policy"]
    if np.asarray(array).dtype.kind not in set(policy["eligible_dtype_kinds"]):
        return False
    lowered = key.lower()
    return not any(str(fragment).lower() in lowered for fragment in policy["excluded_source_key_fragments"])


def _numeric_snapshot(
    extraction: Mapping[str, Any],
    sources: Mapping[str, Path],
    structure: Mapping[str, Any],
    history_view: Path,
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    g3 = _selected_g3_profile(extraction)
    source_ids, _, permutations = _registries(structure)
    sizes = {role: len(values) for role, values in source_ids.items()}
    arrays: dict[str, np.ndarray] = {}
    raw_metadata: list[dict[str, Any]] = []
    stages: set[str] = set()
    for raw in g3["numeric_payloads"]:
        entry = _mapping(raw, "numeric payload")
        path = _payload_path(entry, sources)
        if not path.is_file():
            raise RelationFieldPredictionStateP1Error(f"numeric source is missing: {entry['payload_id']}")
        loaded = _load_npz(path)
        groups = _array_groups(entry, sorted(loaded))
        selected = _select_numeric_payload(
            loaded,
            groups,
            _mapping(extraction["numeric_selectors"][entry["payload_id"]], "numeric selector"),
        )
        source_sha = _sha256_file(path)
        stages.add(str(entry["stage"]))
        for source_key in sorted(selected):
            value, roles, transform = selected[source_key]
            canonical = _canonicalize_array(value, roles, permutations, sizes)
            output_key = f"{entry['payload_id']}__{source_key}"
            if output_key in arrays:
                raise RelationFieldPredictionStateP1Error(f"duplicate P1 array key: {output_key}")
            arrays[output_key] = canonical
            raw_metadata.append({
                "array_key": output_key,
                "stage": entry["stage"],
                "payload_id": entry["payload_id"],
                "source_file": f"{entry['root']}/{entry['path']}",
                "source_sha256": source_sha,
                "source_array_key": source_key,
                "dimension_roles": roles,
                "transform": transform,
            })
            if transform == "rf5_descriptor":
                descriptor = np.asarray(value, dtype=np.float64)
                axis_count = sizes["axis"]
                if descriptor.ndim != 2 or descriptor.shape[1] != axis_count + axis_count * axis_count + 1:
                    raise RelationFieldPredictionStateP1Error("RF-5 descriptor does not match axis registry")
                derived = {
                    f"{output_key}__axis_signed_flow": (descriptor[:, :axis_count], [None, "axis"]),
                    f"{output_key}__source_axis_offsets": (
                        descriptor[:, axis_count:-1].reshape(descriptor.shape[0], axis_count, axis_count),
                        [None, "axis", "axis"],
                    ),
                    f"{output_key}__total_absolute_flow": (descriptor[:, -1], [None]),
                }
                for derived_key, (derived_value, derived_roles) in derived.items():
                    canonical_derived = _canonicalize_array(derived_value, derived_roles, permutations, sizes)
                    arrays[derived_key] = canonical_derived
                    raw_metadata.append({
                        "array_key": derived_key,
                        "stage": entry["stage"],
                        "payload_id": entry["payload_id"],
                        "source_file": f"{entry['root']}/{entry['path']}",
                        "source_sha256": source_sha,
                        "source_array_key": source_key,
                        "dimension_roles": derived_roles,
                        "transform": "rf5_descriptor",
                    })
    if stages != set(P1_STAGES):
        raise RelationFieldPredictionStateP1Error("P1 numeric stage coverage mismatch")

    history_arrays = _load_npz(history_view / "mass_records.npz")
    offsets = np.asarray(history_arrays["frame_offsets"], dtype=np.int64)
    values = np.asarray(history_arrays["mass_values"], dtype=np.float64)
    if offsets.size < 2:
        raise RelationFieldPredictionStateP1Error("P1 history view has no current frame")
    current_source = values[int(offsets[-2]):int(offsets[-1])]
    current = np.take(current_source, permutations["cell"], axis=0)
    current_key = str(extraction["current_distribution"]["array_key"])
    arrays[current_key] = np.ascontiguousarray(current)
    raw_metadata.append({
        "array_key": current_key,
        "stage": "G_t",
        "payload_id": "current_distribution",
        "source_file": "g2_history/mass_records.npz",
        "source_sha256": _sha256_file(history_view / "mass_records.npz"),
        "source_array_key": "mass_values[current_frame]",
        "dimension_roles": ["cell"],
        "transform": None,
        "unit": extraction["current_distribution"]["unit"],
        "normalization_id": extraction["current_distribution"]["normalization_id"],
    })

    metadata: list[dict[str, Any]] = []
    for row in sorted(raw_metadata, key=lambda value: str(value["array_key"])):
        key = str(row["array_key"])
        array = np.asarray(arrays[key])
        unit = str(row.get("unit", extraction["difference_policy"]["default_unit"]))
        normalization_id = str(
            row.get("normalization_id", extraction["difference_policy"]["default_normalization_id"])
        )
        comparable_basis = {
            "feature_id": key,
            "dimension_roles": row["dimension_roles"],
            "shape": list(array.shape),
            "unit": unit,
            "normalization_id": normalization_id,
        }
        metadata.append({
            **row,
            "shape": list(array.shape),
            "dtype": array.dtype.str,
            "content_hash": _array_hash(array),
            "unit": unit,
            "normalization_id": normalization_id,
            "difference_eligible": _difference_eligible(key, array, extraction),
            "comparability_id": _canonical_digest(comparable_basis),
        })
    return arrays, {
        "base_state_index_version": "relation_field_prediction_state_p1_base_index",
        "array_count": len(arrays),
        "fixed_length_primary_vector": False,
        "arrays": metadata,
    }


def _semantic_by_id(semantic: Mapping[str, Any]) -> dict[str, Any]:
    return {str(row["payload_id"]): row["payload"] for row in semantic["records"]}


def _risk_state(semantic: Mapping[str, Any], registry: Mapping[str, Any]) -> dict[str, Any]:
    by_id = _semantic_by_id(semantic)
    candidates = _mapping(by_id["rf9_candidates"], "RF-9 candidates")
    evidence = _mapping(by_id["rf9_evidence"], "RF-9 evidence")
    counter = _mapping(by_id["rf9_counterevidence"], "RF-9 counterevidence")
    candidate_rows = list(candidates.get("rows", []))
    evidence_rows = list(evidence.get("rows", []))
    counter_rows = list(counter.get("rows", []))
    if len(candidate_rows) != 1 or len(evidence_rows) != 1 or len(counter_rows) != 1:
        raise RelationFieldPredictionStateP1Error("P1 requires one terminal RF-9 row")
    candidate, support, counterevidence = candidate_rows[0], evidence_rows[0], counter_rows[0]
    records: list[dict[str, Any]] = []
    for entry in registry["entries"]:
        source_field = str(entry["source_candidate_field"])
        if source_field not in candidate:
            raise RelationFieldPredictionStateP1Error(f"RF-9 candidate field is missing: {source_field}")
        evidence_field = entry.get("evidence_field")
        counter_field = entry.get("counterevidence_field")
        records.append({
            "risk_structure_id": entry["risk_structure_id"],
            "role": entry["role"],
            "current_candidate": bool(candidate[source_field]),
            "source_candidate_field": source_field,
            "evidence": [] if evidence_field is None else list(support.get(str(evidence_field), [])),
            "counterevidence": [] if counter_field is None else list(counterevidence.get(str(counter_field), [])),
            "true_irreversibility_claim": False,
            "future_prediction_claim": False,
        })
    return {
        "risk_state_version": "relation_field_prediction_state_p1_risk_state",
        "single_scalar_risk_score_produced": False,
        "terminal_transition_time": candidate.get("transition_time"),
        "records": records,
    }


def _candidate_records(
    arrays: Mapping[str, np.ndarray],
    risk_state: Mapping[str, Any],
) -> list[dict[str, Any]]:
    key = "rf5_candidate_flows__candidate_transition_index"
    if key not in arrays:
        raise RelationFieldPredictionStateP1Error("P1 RF-5 candidate family is absent")
    count = int(np.asarray(arrays[key]).size)
    rows: list[dict[str, Any]] = [
        {
            "candidate_record_id": f"flow_candidate/{index:06d}",
            "candidate_family": "RF-5_terminal_flow_family",
            "candidate_ordinal": index,
            "probability_interpretation": False,
            "representative_truth_claim": False,
            "numeric_source_prefix": "rf5_candidate_flows__",
        }
        for index in range(count)
    ]
    rows.extend(
        {
            "candidate_record_id": f"risk_structure/{row['risk_structure_id']}",
            "candidate_family": "RF-9_parallel_risk_structure",
            "risk_structure_id": row["risk_structure_id"],
            "role": row["role"],
            "current_candidate": row["current_candidate"],
            "probability_interpretation": False,
            "single_scalar_aggregation": False,
        }
        for row in risk_state["records"]
    )
    return sorted(rows, key=lambda row: str(row["candidate_record_id"]))


def _build_parents(
    trajectory: Path,
    grid: Path,
    parent_root: Path,
    stage_dirs: Mapping[str, str],
    origin_t: int,
) -> dict[str, Path]:
    parents = {stage: parent_root / str(stage_dirs[stage]) for stage in P1_STAGES}
    build_transition_field(trajectory, grid, parents["RF-3"], from_t=origin_t - 1, to_t=origin_t)
    build_temporal_relation_field(trajectory, grid, parents["RF-5"], start_t=0, to_t=origin_t)
    build_hodge_decomposition(parents["RF-5"], grid, parents["RF-6"])
    build_shape_dynamics(trajectory, parents["RF-5"], parents["RF-6"], grid, parents["RF-7"])
    build_axis_coupling_innovation(
        trajectory, grid, parents["RF-5"], parents["RF-6"], parents["RF-7"], parents["RF-8"]
    )
    build_risk_structure(
        trajectory, grid, parents["RF-5"], parents["RF-6"], parents["RF-7"], parents["RF-8"], parents["RF-9"]
    )
    return parents


def _validate_parents(trajectory: Path, grid: Path, parents: Mapping[str, Path]) -> dict[str, Any]:
    result = {
        "RF-3": validate_transition_artifact(parents["RF-3"], grid),
        "RF-5": validate_temporal_relation_field(parents["RF-5"], grid),
        "RF-6": validate_hodge_artifact(parents["RF-6"], parents["RF-5"], grid),
        "RF-7": validate_shape_dynamics(
            parents["RF-7"], trajectory, parents["RF-5"], parents["RF-6"], grid
        ),
        "RF-8": validate_axis_coupling_innovation(
            parents["RF-8"], trajectory, grid, parents["RF-5"], parents["RF-6"], parents["RF-7"]
        ),
        "RF-9": validate_risk_structure(
            parents["RF-9"], trajectory, grid, parents["RF-5"], parents["RF-6"], parents["RF-7"], parents["RF-8"]
        ),
    }
    if set(result) != set(P1_STAGES):
        raise RelationFieldPredictionStateP1Error("P1 parent validator coverage mismatch")
    return result


def _index_by_key(index: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {str(row["array_key"]): row for row in index["arrays"]}


def _compute_differences(
    origin_t: int,
    arrays: Mapping[str, np.ndarray],
    index: Mapping[str, Any],
    previous: tuple[int, Mapping[str, np.ndarray], Mapping[str, Any]] | None,
    previous_previous: tuple[int, Mapping[str, np.ndarray], Mapping[str, Any]] | None,
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray], dict[str, Any]]:
    current_meta = _index_by_key(index)
    first: dict[str, np.ndarray] = {}
    second: dict[str, np.ndarray] = {}
    availability: list[dict[str, Any]] = []
    first_intermediate_previous: dict[str, np.ndarray] = {}
    if previous is not None and previous_previous is not None:
        prev_t, prev_arrays, prev_index = previous
        prevprev_t, prevprev_arrays, prevprev_index = previous_previous
        prev_meta = _index_by_key(prev_index)
        prevprev_meta = _index_by_key(prevprev_index)
        previous_dt = prev_t - prevprev_t
        if previous_dt <= 0:
            raise RelationFieldPredictionStateP1Error("P1 previous origin spacing is invalid")
        for key, meta in prev_meta.items():
            if not meta.get("difference_eligible") or key not in prevprev_arrays or key not in prevprev_meta:
                continue
            if meta.get("comparability_id") != prevprev_meta[key].get("comparability_id"):
                continue
            first_intermediate_previous[key] = (
                np.asarray(prev_arrays[key], dtype=np.float64)
                - np.asarray(prevprev_arrays[key], dtype=np.float64)
            ) / float(previous_dt)
    for key in sorted(current_meta):
        meta = current_meta[key]
        if not meta.get("difference_eligible"):
            continue
        row: dict[str, Any] = {
            "array_key": key,
            "comparability_id": meta["comparability_id"],
            "first_status": "unavailable",
            "first_reason": "no_previous_origin",
            "second_status": "unavailable",
            "second_reason": "insufficient_previous_origins",
        }
        if previous is not None:
            prev_t, prev_arrays, prev_index = previous
            prev_meta = _index_by_key(prev_index)
            if key not in prev_arrays or key not in prev_meta:
                row["first_reason"] = "feature_missing_in_previous_origin"
            elif meta.get("comparability_id") != prev_meta[key].get("comparability_id"):
                row["first_reason"] = "feature_not_comparable_to_previous_origin"
            else:
                dt = origin_t - prev_t
                if dt <= 0:
                    raise RelationFieldPredictionStateP1Error("P1 origin spacing is invalid")
                first[key] = (
                    np.asarray(arrays[key], dtype=np.float64)
                    - np.asarray(prev_arrays[key], dtype=np.float64)
                ) / float(dt)
                row["first_status"] = "available"
                row["first_reason"] = None
                if previous_previous is not None and key in first_intermediate_previous:
                    prevprev_t = previous_previous[0]
                    midpoint_gap = ((origin_t + prev_t) - (prev_t + prevprev_t)) / 2.0
                    if midpoint_gap <= 0:
                        raise RelationFieldPredictionStateP1Error("P1 second-difference midpoint gap is invalid")
                    second[key] = (first[key] - first_intermediate_previous[key]) / float(midpoint_gap)
                    row["second_status"] = "available"
                    row["second_reason"] = None
                elif previous_previous is not None:
                    row["second_reason"] = "previous_first_rate_unavailable_or_incomparable"
        availability.append(row)
    return first, second, {
        "difference_index_version": "relation_field_prediction_state_p1_differences",
        "origin_t": origin_t,
        "first_difference_count": len(first),
        "second_difference_count": len(second),
        "zero_fill_performed": False,
        "records": availability,
    }


def _assert_array_payload(
    expected: Mapping[str, np.ndarray], actual: Mapping[str, np.ndarray], name: str
) -> None:
    if set(expected) != set(actual):
        raise RelationFieldPredictionStateP1Error(f"{name} array key mismatch")
    for key in expected:
        left, right = np.asarray(expected[key]), np.asarray(actual[key])
        if left.shape != right.shape or left.dtype.kind != right.dtype.kind:
            raise RelationFieldPredictionStateP1Error(f"{name} array metadata mismatch: {key}")
        equal = np.array_equal(left, right) if left.dtype.kind in "iubSU" else np.allclose(left, right, atol=1e-12, rtol=1e-12)
        if not equal:
            raise RelationFieldPredictionStateP1Error(f"{name} array value mismatch: {key}")


def _origin_paths(root: Path, storage: Mapping[str, Any], origin_t: int) -> dict[str, Any]:
    try:
        origin_name = str(storage["origin_name_format"]).format(origin_t=origin_t)
    except Exception as exc:
        raise RelationFieldPredictionStateP1Error("invalid P1 origin_name_format") from exc
    origin = root / str(storage["origin_container_dir"]) / origin_name
    parent_root = origin / str(storage["parent_artifact_dir"])
    return {
        "origin": origin,
        "history": origin / str(storage["history_view_dir"]),
        "parent_root": parent_root,
        "parents": {
            stage: parent_root / str(storage["parent_stage_dirs"][stage]) for stage in P1_STAGES
        },
        "state": origin / str(storage["state_dir"]),
    }


def build_prediction_state_series(
    trajectory_dir: str | Path,
    grid_artifact_dir: str | Path,
    structure_artifact_dir: str | Path,
    output: str | Path,
    *,
    origins: Sequence[int],
    contract_path: str | Path = DEFAULT_CONTRACT,
    extraction_profile_path: str | Path = DEFAULT_PROFILE,
    risk_registry_path: str | Path = DEFAULT_RISK_REGISTRY,
) -> Path:
    contract = load_contract(contract_path)
    extraction = load_extraction_profile(extraction_profile_path)
    registry = load_risk_registry(risk_registry_path)
    normalized_origins = [int(value) for value in origins]
    if not normalized_origins or normalized_origins != sorted(set(normalized_origins)):
        raise RelationFieldPredictionStateP1Error("P1 origins must be unique and strictly increasing")
    if any(value < int(contract["input"]["minimum_origin_t"]) for value in normalized_origins):
        raise RelationFieldPredictionStateP1Error("P1 origin is earlier than minimum_origin_t")
    target = Path(output)
    if target.exists():
        raise RelationFieldPredictionStateP1Error(f"output already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    trajectory = Path(trajectory_dir).resolve()
    grid = Path(grid_artifact_dir).resolve()
    structure_root = Path(structure_artifact_dir).resolve()
    validate_structure_artifact(structure_root)
    structure = _load_structure_artifact(structure_root, verify_manifest=True)
    trajectory_before = _tree_hash(trajectory)
    grid_before = _tree_hash(grid)
    structure_before = _tree_hash(structure_root)
    storage = contract["storage"]
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp-", dir=target.parent))
    try:
        _json_dump(temporary / "contract.json", contract)
        _json_dump(temporary / "extraction_profile.json", extraction)
        _json_dump(temporary / "risk_registry.json", registry)
        origin_cache: list[tuple[int, dict[str, np.ndarray], dict[str, Any], dict[str, Any]]] = []
        series_rows: list[dict[str, Any]] = []
        for origin_t in normalized_origins:
            paths = _origin_paths(temporary, storage, origin_t)
            build_fixed5_history_view(trajectory, structure_root, paths["history"], to_t=origin_t)
            parents = _build_parents(
                trajectory, grid, paths["parent_root"], storage["parent_stage_dirs"], origin_t
            )
            parent_validation = _validate_parents(trajectory, grid, parents)
            sources = _source_map(trajectory, grid, parents)
            arrays, index = _numeric_snapshot(extraction, sources, structure, paths["history"])
            semantic = _semantic_snapshot(extraction, sources, structure)
            risk = _risk_state(semantic, registry)
            candidates = _candidate_records(arrays, risk)
            state = paths["state"]
            state.mkdir(parents=True, exist_ok=True)
            _write_deterministic_npz(state / storage["base_state_file"], arrays)
            _json_dump(state / storage["base_state_index_file"], index)
            _json_dump(state / storage["semantic_state_file"], semantic)
            _write_jsonl(state / storage["candidate_records_file"], candidates)
            _json_dump(state / storage["risk_state_file"], risk)
            history_identity = _json_load(paths["history"] / "identity.json")
            identity = {
                "artifact_version": "relation_field_prediction_state_p1_origin",
                "origin_t": origin_t,
                "trajectory_id": history_identity["trajectory_id"],
                "causal_prefix_hash": history_identity["causal_prefix_hash"],
                "structure_hash": structure["profile"]["structure_hash"],
                "parent_manifest_hashes": {
                    stage: _sha256_file(parents[stage] / "manifest.json") for stage in P1_STAGES
                },
                "base_array_count": int(index["array_count"]),
                "candidate_record_count": len(candidates),
                "future_information_used": False,
                "RF10_used": False,
                "prediction_performed": False,
                "action_selection_performed": False,
                "canonical_writeback_performed": False,
            }
            _json_dump(paths["origin"] / storage["origin_identity_file"], identity)
            origin_cache.append((origin_t, arrays, index, {"paths": paths, "identity": identity, "parent_validation": parent_validation}))

        for ordinal, (origin_t, arrays, index, context) in enumerate(origin_cache):
            previous = None if ordinal < 1 else (origin_cache[ordinal - 1][0], origin_cache[ordinal - 1][1], origin_cache[ordinal - 1][2])
            previous_previous = None if ordinal < 2 else (
                origin_cache[ordinal - 2][0], origin_cache[ordinal - 2][1], origin_cache[ordinal - 2][2]
            )
            first, second, difference_index = _compute_differences(
                origin_t, arrays, index, previous, previous_previous
            )
            paths = context["paths"]
            state = paths["state"]
            _write_deterministic_npz(state / storage["first_difference_file"], first)
            _write_deterministic_npz(state / storage["second_difference_file"], second)
            _json_dump(state / storage["difference_index_file"], difference_index)
            validation = {
                "p1_origin_gate": "passed",
                "origin_t": origin_t,
                "parent_stage_validation_count": len(context["parent_validation"]),
                "base_array_count": int(index["array_count"]),
                "candidate_record_count": int(context["identity"]["candidate_record_count"]),
                "first_difference_count": len(first),
                "second_difference_count": len(second),
                "future_information_used": False,
                "RF10_used": False,
                "zero_fill_performed": False,
                "prediction_performed": False,
                "action_selection_performed": False,
                "canonical_writeback_performed": False,
            }
            _json_dump(paths["origin"] / storage["origin_validation_file"], validation)
            _write_manifest(paths["origin"], "relation_field_prediction_state_p1_origin")
            series_rows.append({
                "origin_t": origin_t,
                "origin_name": paths["origin"].name,
                "causal_prefix_hash": context["identity"]["causal_prefix_hash"],
                "base_array_count": int(index["array_count"]),
                "candidate_record_count": int(context["identity"]["candidate_record_count"]),
                "first_difference_count": len(first),
                "second_difference_count": len(second),
                "origin_manifest_hash": _sha256_file(paths["origin"] / storage["origin_manifest_file"]),
            })

        series_identity = {
            "artifact_version": "relation_field_prediction_state_p1_series",
            "trajectory_id": origin_cache[0][3]["identity"]["trajectory_id"],
            "structure_hash": structure["profile"]["structure_hash"],
            "origins": normalized_origins,
            "origin_count": len(normalized_origins),
            "fixed_length_primary_vector": False,
            "future_information_used": False,
            "RF10_used": False,
            "prediction_performed": False,
            "action_selection_performed": False,
            "canonical_writeback_performed": False,
        }
        _json_dump(temporary / storage["series_identity_file"], series_identity)
        _json_dump(temporary / storage["series_index_file"], {
            "series_index_version": "relation_field_prediction_state_p1_series_index",
            "rows": series_rows,
        })
        validation = {
            "p1_series_gate": "passed",
            "origin_count": len(normalized_origins),
            "origins_strictly_increasing": True,
            "all_origin_gates_passed": True,
            "parent_stages": list(P1_STAGES),
            "RF4_used_as_state": False,
            "RF10_used": False,
            "future_information_used": False,
            "zero_fill_performed": False,
            "prediction_performed": False,
            "action_selection_performed": False,
            "source_writeback_performed": False,
            "engineering_claim": contract["acceptance"]["engineering_claim"],
            "scientific_claim": contract["acceptance"]["scientific_claim"],
            "prediction_accuracy_claim": contract["acceptance"]["prediction_accuracy_claim"],
        }
        _json_dump(temporary / storage["series_validation_file"], validation)
        if trajectory_before != _tree_hash(trajectory) or grid_before != _tree_hash(grid) or structure_before != _tree_hash(structure_root):
            raise RelationFieldPredictionStateP1Error("P1 source writeback detected")
        _write_manifest(temporary, "relation_field_prediction_state_p1_series")
        os.replace(temporary, target)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return target


def validate_prediction_state_series(
    input_path: str | Path,
    trajectory_dir: str | Path,
    grid_artifact_dir: str | Path,
    structure_artifact_dir: str | Path,
) -> dict[str, Any]:
    root = Path(input_path)
    _verify_manifest(root)
    contract = _json_load(root / "contract.json")
    extraction = _json_load(root / "extraction_profile.json")
    registry = _json_load(root / "risk_registry.json")
    validate_contract(contract)
    validate_extraction_profile(extraction)
    validate_risk_registry(registry)
    trajectory = Path(trajectory_dir).resolve()
    grid = Path(grid_artifact_dir).resolve()
    structure_root = Path(structure_artifact_dir).resolve()
    validate_structure_artifact(structure_root)
    structure = _load_structure_artifact(structure_root, verify_manifest=True)
    trajectory_before = _tree_hash(trajectory)
    grid_before = _tree_hash(grid)
    structure_before = _tree_hash(structure_root)
    storage = contract["storage"]
    series_identity = _json_load(root / storage["series_identity_file"])
    series_index = _json_load(root / storage["series_index_file"])
    validation = _json_load(root / storage["series_validation_file"])
    origins = [int(value) for value in series_identity.get("origins", [])]
    if origins != sorted(set(origins)) or len(origins) != int(series_identity.get("origin_count", -1)):
        raise RelationFieldPredictionStateP1Error("P1 persisted origins are invalid")
    rows = list(series_index.get("rows", []))
    if [int(row["origin_t"]) for row in rows] != origins:
        raise RelationFieldPredictionStateP1Error("P1 series index origin mismatch")
    forbidden_names = {
        "future_outcomes.npz", "prediction_snapshot.json", "predictive_metrics.json",
        "sample_ledger.json", "truth.jsonl", "action_observations.jsonl", "event_observations.jsonl",
    }
    if any(path.name in forbidden_names for path in root.rglob("*")):
        raise RelationFieldPredictionStateP1Error("P1 contains a forbidden future or action payload")

    expected_series_identity = {
        "artifact_version": "relation_field_prediction_state_p1_series",
        "trajectory_id": None,
        "structure_hash": structure["profile"]["structure_hash"],
        "origins": origins,
        "origin_count": len(origins),
        "fixed_length_primary_vector": False,
        "future_information_used": False,
        "RF10_used": False,
        "prediction_performed": False,
        "action_selection_performed": False,
        "canonical_writeback_performed": False,
    }
    recomputed: list[dict[str, Any]] = []
    for row in rows:
        origin_t = int(row["origin_t"])
        paths = _origin_paths(root, storage, origin_t)
        _verify_manifest(paths["origin"])
        history_validation = validate_history_view(paths["history"], structure_root)
        if history_validation.get("g2_history_view_gate") != "passed":
            raise RelationFieldPredictionStateP1Error("P1 history view gate failed")
        history_identity = _json_load(paths["history"] / "identity.json")
        parent_validation = _validate_parents(trajectory, grid, paths["parents"])
        if set(parent_validation) != set(P1_STAGES):
            raise RelationFieldPredictionStateP1Error("P1 parent validation coverage failed")
        sources = _source_map(trajectory, grid, paths["parents"])
        expected_arrays, expected_index = _numeric_snapshot(extraction, sources, structure, paths["history"])
        expected_semantic = _semantic_snapshot(extraction, sources, structure)
        expected_risk = _risk_state(expected_semantic, registry)
        expected_candidates = _candidate_records(expected_arrays, expected_risk)
        state = paths["state"]
        actual_arrays = _load_npz(state / storage["base_state_file"])
        _assert_array_payload(expected_arrays, actual_arrays, "P1 base state")
        if _json_load(state / storage["base_state_index_file"]) != expected_index:
            raise RelationFieldPredictionStateP1Error("P1 base state index mismatch")
        if _json_load(state / storage["semantic_state_file"]) != expected_semantic:
            raise RelationFieldPredictionStateP1Error("P1 semantic state mismatch")
        if _json_load(state / storage["risk_state_file"]) != expected_risk:
            raise RelationFieldPredictionStateP1Error("P1 risk state mismatch")
        if _read_jsonl(state / storage["candidate_records_file"]) != expected_candidates:
            raise RelationFieldPredictionStateP1Error("P1 candidate records mismatch")
        expected_origin_identity = {
            "artifact_version": "relation_field_prediction_state_p1_origin",
            "origin_t": origin_t,
            "trajectory_id": history_identity["trajectory_id"],
            "causal_prefix_hash": history_identity["causal_prefix_hash"],
            "structure_hash": structure["profile"]["structure_hash"],
            "parent_manifest_hashes": {
                stage: _sha256_file(paths["parents"][stage] / "manifest.json") for stage in P1_STAGES
            },
            "base_array_count": int(expected_index["array_count"]),
            "candidate_record_count": len(expected_candidates),
            "future_information_used": False,
            "RF10_used": False,
            "prediction_performed": False,
            "action_selection_performed": False,
            "canonical_writeback_performed": False,
        }
        if _json_load(paths["origin"] / storage["origin_identity_file"]) != expected_origin_identity:
            raise RelationFieldPredictionStateP1Error("P1 origin identity mismatch")
        if expected_series_identity["trajectory_id"] is None:
            expected_series_identity["trajectory_id"] = history_identity["trajectory_id"]
        elif expected_series_identity["trajectory_id"] != history_identity["trajectory_id"]:
            raise RelationFieldPredictionStateP1Error("P1 trajectory identity changed across origins")
        recomputed.append({
            "origin_t": origin_t,
            "arrays": expected_arrays,
            "index": expected_index,
            "candidates": expected_candidates,
            "paths": paths,
            "identity": expected_origin_identity,
        })

    if series_identity != expected_series_identity:
        raise RelationFieldPredictionStateP1Error("P1 series identity mismatch")

    expected_rows: list[dict[str, Any]] = []
    for ordinal, current in enumerate(recomputed):
        origin_t = int(current["origin_t"])
        arrays = current["arrays"]
        index = current["index"]
        previous = None if ordinal < 1 else (
            int(recomputed[ordinal - 1]["origin_t"]),
            recomputed[ordinal - 1]["arrays"],
            recomputed[ordinal - 1]["index"],
        )
        previous_previous = None if ordinal < 2 else (
            int(recomputed[ordinal - 2]["origin_t"]),
            recomputed[ordinal - 2]["arrays"],
            recomputed[ordinal - 2]["index"],
        )
        first, second, difference_index = _compute_differences(
            origin_t, arrays, index, previous, previous_previous
        )
        paths = current["paths"]
        state = paths["state"]
        _assert_array_payload(first, _load_npz(state / storage["first_difference_file"]), "P1 first difference")
        _assert_array_payload(second, _load_npz(state / storage["second_difference_file"]), "P1 second difference")
        if _json_load(state / storage["difference_index_file"]) != difference_index:
            raise RelationFieldPredictionStateP1Error("P1 difference index mismatch")
        expected_origin_validation = {
            "p1_origin_gate": "passed",
            "origin_t": origin_t,
            "parent_stage_validation_count": len(P1_STAGES),
            "base_array_count": int(index["array_count"]),
            "candidate_record_count": len(current["candidates"]),
            "first_difference_count": len(first),
            "second_difference_count": len(second),
            "future_information_used": False,
            "RF10_used": False,
            "zero_fill_performed": False,
            "prediction_performed": False,
            "action_selection_performed": False,
            "canonical_writeback_performed": False,
        }
        if _json_load(paths["origin"] / storage["origin_validation_file"]) != expected_origin_validation:
            raise RelationFieldPredictionStateP1Error("P1 persisted origin validation mismatch")
        expected_rows.append({
            "origin_t": origin_t,
            "origin_name": paths["origin"].name,
            "causal_prefix_hash": current["identity"]["causal_prefix_hash"],
            "base_array_count": int(index["array_count"]),
            "candidate_record_count": len(current["candidates"]),
            "first_difference_count": len(first),
            "second_difference_count": len(second),
            "origin_manifest_hash": _sha256_file(paths["origin"] / storage["origin_manifest_file"]),
        })
    expected_series_index = {
        "series_index_version": "relation_field_prediction_state_p1_series_index",
        "rows": expected_rows,
    }
    if series_index != expected_series_index:
        raise RelationFieldPredictionStateP1Error("P1 series index mismatch")
    expected_validation = {
        "p1_series_gate": "passed",
        "origin_count": len(origins),
        "origins_strictly_increasing": True,
        "all_origin_gates_passed": True,
        "parent_stages": list(P1_STAGES),
        "RF4_used_as_state": False,
        "RF10_used": False,
        "future_information_used": False,
        "zero_fill_performed": False,
        "prediction_performed": False,
        "action_selection_performed": False,
        "source_writeback_performed": False,
        "engineering_claim": contract["acceptance"]["engineering_claim"],
        "scientific_claim": contract["acceptance"]["scientific_claim"],
        "prediction_accuracy_claim": contract["acceptance"]["prediction_accuracy_claim"],
    }
    if validation != expected_validation:
        raise RelationFieldPredictionStateP1Error("P1 persisted series validation mismatch")
    if trajectory_before != _tree_hash(trajectory) or grid_before != _tree_hash(grid) or structure_before != _tree_hash(structure_root):
        raise RelationFieldPredictionStateP1Error("P1 validator modified a source artifact")
    return validation


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build")
    build.add_argument("--trajectory", required=True)
    build.add_argument("--grid", required=True)
    build.add_argument("--structure", required=True)
    build.add_argument("--output", required=True)
    build.add_argument("--origins", required=True, help="comma-separated prediction origins")
    build.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    build.add_argument("--extraction-profile", default=str(DEFAULT_PROFILE))
    build.add_argument("--risk-registry", default=str(DEFAULT_RISK_REGISTRY))
    validate = subparsers.add_parser("validate")
    validate.add_argument("--input", required=True)
    validate.add_argument("--trajectory", required=True)
    validate.add_argument("--grid", required=True)
    validate.add_argument("--structure", required=True)
    args = parser.parse_args(argv)
    if args.command == "build":
        origins = [int(value.strip()) for value in args.origins.split(",") if value.strip()]
        build_prediction_state_series(
            args.trajectory, args.grid, args.structure, args.output,
            origins=origins,
            contract_path=args.contract,
            extraction_profile_path=args.extraction_profile,
            risk_registry_path=args.risk_registry,
        )
    else:
        result = validate_prediction_state_series(args.input, args.trajectory, args.grid, args.structure)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
