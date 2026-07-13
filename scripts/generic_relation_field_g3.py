#!/usr/bin/env python3
"""G3: identity-keyed scientific compatibility and structure-independence audit.

G3 does not replace the frozen RF-3--RF-10 scientific kernels.  It validates
their source artifacts, materializes every declared scientific payload through
the G2 stable-identity registries, and independently reconstructs the payload
and scientific invariants during validation.
"""

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
from scipy.sparse import coo_matrix, csr_matrix

from generic_relation_field_g2 import (
    GenericRelationFieldG2Error,
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
    generate_product_faces,
    validate_structure_payload,
)
from relation_field_axis_coupling_innovation_rc1 import (
    validate_axis_coupling_innovation,
)
from relation_field_hodge_decomposition_rc1 import validate_hodge_artifact
from relation_field_predictive_validation_rc1 import validate_predictive_validation
from relation_field_risk_structure_rc1 import validate_risk_structure
from relation_field_shape_dynamics_rc1 import validate_shape_dynamics
from relation_field_single_transition_audit_rc1 import validate_audit_artifact
from relation_field_single_transition_rc1 import validate_transition_artifact
from relation_field_temporal_consistency_rc1 import validate_temporal_relation_field


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "configs" / "generic_relation_field_g3_contract.json"
DEFAULT_PROFILE = ROOT / "configs" / "generic_relation_field_g3_validation_profile.json"
STRUCTURAL_ROLES = {"axis", "cell", "edge", "face"}


class GenericRelationFieldG3Error(ValueError):
    """Raised when G3 input, compatibility, or safety validation fails."""


def _repo_path(raw: str) -> Path:
    path = (ROOT / str(raw)).resolve()
    if path != ROOT and ROOT not in path.parents:
        raise GenericRelationFieldG3Error(f"path escapes repository: {raw}")
    return path


def _validate_relative_source_path(raw: str, name: str) -> None:
    path = Path(raw)
    if not raw or path.is_absolute() or ".." in path.parts:
        raise GenericRelationFieldG3Error(f"{name} must be a repository-safe relative path")


def _resolve_beneath(root: Path, relative: str, name: str) -> Path:
    candidate = (root / relative).resolve()
    if candidate != root and root not in candidate.parents:
        raise GenericRelationFieldG3Error(f"{name} escapes its source root")
    return candidate


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise GenericRelationFieldG3Error(f"{name} must be an object")
    return value


def _list(value: Any, name: str) -> list[Any]:
    if not isinstance(value, list) or not value:
        raise GenericRelationFieldG3Error(f"{name} must be a non-empty list")
    return value


def _canonical_hash(value: Any) -> str:
    return _sha256_bytes(_canonical_json(value))


def _array_hash(value: np.ndarray) -> str:
    array = np.ascontiguousarray(value)
    header = _canonical_json({"dtype": array.dtype.str, "shape": list(array.shape)})
    return _sha256_bytes(header + array.tobytes(order="C"))


def _tree_hash(path: Path) -> str:
    if path.is_file():
        return _sha256_file(path)
    if not path.is_dir():
        raise GenericRelationFieldG3Error(f"source does not exist: {path}")
    rows = [
        {
            "path": item.relative_to(path).as_posix(),
            "size_bytes": item.stat().st_size,
            "sha256": _sha256_file(item),
        }
        for item in sorted(path.rglob("*"))
        if item.is_file()
    ]
    return _canonical_hash(rows)


def _recursive_keys(value: Any) -> Iterable[str]:
    if isinstance(value, Mapping):
        for key, child in value.items():
            yield str(key)
            yield from _recursive_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _recursive_keys(child)


def load_contract(path: str | Path = DEFAULT_CONTRACT) -> dict[str, Any]:
    contract = _json_load(Path(path))
    validate_contract(contract)
    return contract


def load_validation_profile(path: str | Path = DEFAULT_PROFILE) -> dict[str, Any]:
    profile = _json_load(Path(path))
    validate_validation_profile(profile)
    return profile


def validate_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("contract_version") != "generic_relation_field_g3":
        raise GenericRelationFieldG3Error("G3 contract version mismatch")
    scope = _mapping(contract.get("scope"), "scope")
    if scope.get("fixed5_scientific_compatibility") is not True:
        raise GenericRelationFieldG3Error("fixed5 scientific compatibility is required")
    for forbidden_true in (
        "generic_rf_kernel_reimplementation",
        "generic_gk_generation",
        "prediction_model_implementation",
        "prediction_accuracy_evaluation",
        "universal_irreversibility_claim",
        "action_evaluation_or_selection",
    ):
        if scope.get(forbidden_true) is not False:
            raise GenericRelationFieldG3Error(f"G3 scope boundary changed: {forbidden_true}")
    required_stages = _list(contract.get("required_stages"), "required_stages")
    if required_stages != [f"RF-{index}" for index in range(3, 11)]:
        raise GenericRelationFieldG3Error("G3 stage sequence must remain RF-3 through RF-10")
    canonicalization = _mapping(contract.get("canonicalization"), "canonicalization")
    for key in (
        "every_structural_dimension_must_be_declared",
        "undeclared_source_array_is_error",
        "numeric_payload_must_be_materialized",
        "hash_only_numeric_compatibility_is_forbidden",
        "semantic_json_payload_must_be_materialized",
        "dense_payload_requires_registry_ids_and_hashes",
    ):
        if canonicalization.get(key) is not True:
            raise GenericRelationFieldG3Error(f"G3 canonicalization safeguard disabled: {key}")
    if canonicalization.get("target_registry_order") != "unicode_codepoint_ascending_identity":
        raise GenericRelationFieldG3Error("unsupported canonical registry order")
    if contract.get("causal_boundary", {}).get("future_outcomes_are_target_side_only") is not True:
        raise GenericRelationFieldG3Error("RF-10 future outcomes must remain target-side only")
    storage = _mapping(contract.get("storage"), "storage")
    required_files = {
        "contract_file",
        "validation_profile_file",
        "identity_file",
        "registry_index_file",
        "numeric_payload_file",
        "numeric_index_file",
        "semantic_payload_file",
        "scientific_invariants_file",
        "synthetic_structure_audit_file",
        "negative_guard_audit_file",
        "validation_file",
        "manifest_file",
    }
    if not required_files <= set(storage):
        raise GenericRelationFieldG3Error("G3 storage contract is incomplete")
    acceptance = _mapping(contract.get("acceptance"), "acceptance")
    if acceptance.get("prediction_accuracy_claim") != "not_evaluated":
        raise GenericRelationFieldG3Error("G3 must not claim prediction accuracy")
    if acceptance.get("unknown_structure_accuracy_claim") != "not_evaluated":
        raise GenericRelationFieldG3Error("G3 must not claim unknown-structure accuracy")
    if acceptance.get("all_executed_g3_negative_guards_have_rejection_tests") is not True:
        raise GenericRelationFieldG3Error("G3 negative rejection tests are required")
    if acceptance.get("inherited_g2_negative_guards_required_in_ci") is not True:
        raise GenericRelationFieldG3Error("G2 inherited negative guards must remain in CI")


def validate_validation_profile(profile: Mapping[str, Any]) -> None:
    if profile.get("profile_id") != "generic_relation_field_g3_validation_profile":
        raise GenericRelationFieldG3Error("G3 validation profile ID mismatch")
    contracts = _mapping(profile.get("source_contracts"), "source_contracts")
    expected_stages = {f"RF-{index}" for index in range(3, 11)}
    if set(contracts) != expected_stages:
        raise GenericRelationFieldG3Error("G3 source contract stage set mismatch")
    for path in contracts.values():
        if not _repo_path(str(path)).is_file():
            raise GenericRelationFieldG3Error(f"missing source contract: {path}")
    required_roots = set(_list(profile.get("source_roots"), "source_roots"))
    if required_roots != {
        "grid", "trajectory", "rf3", "rf4", "rf5", "rf6", "rf7", "rf8", "rf9", "rf10", "rf10_case_manifest"
    }:
        raise GenericRelationFieldG3Error("G3 source root set mismatch")
    identity_files = _mapping(profile.get("source_identity_files"), "source_identity_files")
    expected_identity_roots = {f"rf{index}" for index in range(3, 11)}
    if set(identity_files) != expected_identity_roots:
        raise GenericRelationFieldG3Error("G3 source identity root set mismatch")
    for root_name, paths_value in identity_files.items():
        paths = _list(paths_value, f"source_identity_files.{root_name}")
        normalized = [str(value) for value in paths]
        for relative in normalized:
            _validate_relative_source_path(relative, "source identity path")
        if len(normalized) != len(set(normalized)):
            raise GenericRelationFieldG3Error(f"duplicate source identity path: {root_name}")
    numeric = _list(profile.get("numeric_payloads"), "numeric_payloads")
    semantic = _list(profile.get("semantic_payloads"), "semantic_payloads")
    for collection, name in ((numeric, "numeric"), (semantic, "semantic")):
        identifiers = [str(_mapping(value, name).get("payload_id", "")) for value in collection]
        if any(not value for value in identifiers) or len(set(identifiers)) != len(identifiers):
            raise GenericRelationFieldG3Error(f"{name} payload IDs must be unique and non-empty")
        if {str(value["stage"]) for value in collection} != expected_stages:
            raise GenericRelationFieldG3Error(f"{name} payloads must cover RF-3 through RF-10")
    for entry_value in numeric:
        entry = _mapping(entry_value, "numeric payload")
        if str(entry.get("root")) not in required_roots or not str(entry.get("path", "")):
            raise GenericRelationFieldG3Error("numeric payload source is incomplete")
        _validate_relative_source_path(str(entry["path"]), "numeric payload path")
        has_all = "all_arrays_dimension_roles" in entry
        has_groups = "groups" in entry
        if has_all == has_groups:
            raise GenericRelationFieldG3Error("numeric payload needs exactly one dimension mapping mode")
        groups = [entry] if has_all else _list(entry.get("groups"), "numeric groups")
        seen: set[str] = set()
        for group_value in groups:
            group = _mapping(group_value, "numeric group")
            roles = group.get("all_arrays_dimension_roles", group.get("dimension_roles"))
            if not isinstance(roles, list):
                raise GenericRelationFieldG3Error("numeric dimension roles must be a list")
            for role in roles:
                if role is not None and role not in STRUCTURAL_ROLES | {"legacy_descriptor"}:
                    raise GenericRelationFieldG3Error(f"unsupported numeric dimension role: {role}")
            if not has_all:
                keys = _list(group.get("keys"), "numeric group keys")
                overlap = seen & set(str(value) for value in keys)
                if overlap:
                    raise GenericRelationFieldG3Error(f"numeric array mapped twice: {sorted(overlap)}")
                seen.update(str(value) for value in keys)
    for entry_value in semantic:
        entry = _mapping(entry_value, "semantic payload")
        if str(entry.get("root")) not in required_roots or not str(entry.get("path", "")):
            raise GenericRelationFieldG3Error("semantic payload source is incomplete")
        _validate_relative_source_path(str(entry["path"]), "semantic payload path")
    cases = _list(profile.get("synthetic_structure_cases"), "synthetic_structure_cases")
    case_ids = [str(_mapping(value, "synthetic case").get("case_id", "")) for value in cases]
    if len(set(case_ids)) != len(case_ids) or any(not value for value in case_ids):
        raise GenericRelationFieldG3Error("synthetic case IDs must be unique and non-empty")
    required_case_ids = {
        "three_axis_unequal_bins",
        "seven_axis_binary",
        "irregular_connected",
        "multiple_connected_components",
        "face_free_cycle",
        "face_complex_with_hole",
        "coordinate_free_path",
        "identifier_order_permutation",
    }
    if set(case_ids) != required_case_ids:
        raise GenericRelationFieldG3Error("synthetic structure matrix is incomplete")


def _resolve_reference(raw: str) -> Any:
    if "#" not in raw:
        raise GenericRelationFieldG3Error(f"invalid source reference: {raw}")
    path_raw, dotted = raw.split("#", 1)
    value: Any = _json_load(_repo_path(path_raw))
    for key in dotted.split("."):
        value = _mapping(value, f"reference {raw}").get(key)
        if value is None:
            raise GenericRelationFieldG3Error(f"missing source reference field: {raw}")
    return value


def _normalize_sources(sources: Mapping[str, str | Path], profile: Mapping[str, Any]) -> dict[str, Path]:
    required = set(str(value) for value in profile["source_roots"])
    if set(sources) != required:
        missing = sorted(required - set(sources))
        extra = sorted(set(sources) - required)
        raise GenericRelationFieldG3Error(f"source roots mismatch; missing={missing}, extra={extra}")
    resolved = {key: Path(value).resolve() for key, value in sources.items()}
    for key, path in resolved.items():
        if key == "rf10_case_manifest":
            if not path.is_file():
                raise GenericRelationFieldG3Error("RF-10 case manifest is missing")
        elif not path.is_dir():
            raise GenericRelationFieldG3Error(f"source artifact directory is missing: {key}")
    return resolved


def _rf3_field_root(root: Path) -> tuple[Path, str]:
    fields = sorted(root.glob("trajectories/*/fields/t_*"))
    fields = [path for path in fields if (path / "local_flow.npz").is_file()]
    if len(fields) != 1:
        raise GenericRelationFieldG3Error("G3 requires exactly one RF-3 field in the compatibility source")
    return fields[0], fields[0].parents[1].name


def _payload_path(entry: Mapping[str, Any], sources: Mapping[str, Path]) -> Path:
    root = sources[str(entry["root"])]
    relative = str(entry["path"])
    if relative.startswith("__single_field__/"):
        field, _ = _rf3_field_root(root)
        return _resolve_beneath(field, relative.removeprefix("__single_field__/"), "payload path")
    return _resolve_beneath(root, relative, "payload path")


def _identity_path(root_name: str, relative: str, sources: Mapping[str, Path]) -> Path:
    root = sources[root_name]
    if relative.startswith("__single_field__/"):
        field, _ = _rf3_field_root(root)
        return _resolve_beneath(field, relative.removeprefix("__single_field__/"), "identity path")
    if "__trajectory__" in relative:
        _, trajectory_id = _rf3_field_root(root)
        relative = relative.replace("__trajectory__", trajectory_id)
    return _resolve_beneath(root, relative, "identity path")


def _source_hashes(sources: Mapping[str, Path]) -> dict[str, str]:
    return {key: _tree_hash(path) for key, path in sorted(sources.items())}


def _declared_source_identity_hashes(
    profile: Mapping[str, Any],
    sources: Mapping[str, Path],
) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for root_name, relative_paths in sorted(profile["source_identity_files"].items()):
        for relative_value in relative_paths:
            relative = str(relative_value)
            path = _identity_path(str(root_name), relative, sources)
            if not path.is_file():
                raise GenericRelationFieldG3Error(
                    f"declared source identity file is missing: {root_name}/{relative}"
                )
            _json_load(path)
            hashes[f"{root_name}/{relative}"] = _sha256_file(path)
    return hashes


def _source_contract_hashes(profile: Mapping[str, Any]) -> dict[str, str]:
    return {
        stage: _sha256_file(_repo_path(str(path)))
        for stage, path in sorted(profile["source_contracts"].items())
    }


def _run_legacy_validators(sources: Mapping[str, Path]) -> dict[str, Any]:
    validations = {
        "RF-3": validate_transition_artifact(sources["rf3"], sources["grid"]),
        "RF-4": validate_audit_artifact(sources["rf4"], sources["grid"]),
        "RF-5": validate_temporal_relation_field(sources["rf5"], sources["grid"]),
        "RF-6": validate_hodge_artifact(sources["rf6"], sources["rf5"], sources["grid"]),
        "RF-7": validate_shape_dynamics(
            sources["rf7"], sources["trajectory"], sources["rf5"], sources["rf6"], sources["grid"]
        ),
        "RF-8": validate_axis_coupling_innovation(
            sources["rf8"], sources["trajectory"], sources["grid"], sources["rf5"], sources["rf6"], sources["rf7"]
        ),
        "RF-9": validate_risk_structure(
            sources["rf9"], sources["trajectory"], sources["grid"], sources["rf5"], sources["rf6"], sources["rf7"], sources["rf8"]
        ),
        "RF-10": validate_predictive_validation(sources["rf10"], sources["rf10_case_manifest"]),
    }
    if set(validations) != {f"RF-{index}" for index in range(3, 11)}:
        raise GenericRelationFieldG3Error("legacy validator coverage mismatch")
    return validations


def _registries(structure: Mapping[str, Any]) -> tuple[dict[str, list[str]], dict[str, list[str]], dict[str, np.ndarray]]:
    source = {
        "axis": [str(row["axis_id"]) for row in structure["axis_registry"]["records"]],
        "cell": [str(value) for value in structure["cell_arrays"]["cell_ids"].tolist()],
        "edge": [str(value) for value in structure["edge_arrays"]["edge_ids"].tolist()],
        "face": [str(value) for value in structure["face_arrays"]["face_ids"].tolist()],
    }
    for role, identities in source.items():
        if len(set(identities)) != len(identities):
            raise GenericRelationFieldG3Error(f"duplicate G2 identities: {role}")
    canonical = {role: sorted(values) for role, values in source.items()}
    permutations = {
        role: np.asarray([values.index(identity) for identity in canonical[role]], dtype=np.int64)
        for role, values in source.items()
    }
    return source, canonical, permutations


def _registry_index(structure: Mapping[str, Any]) -> dict[str, Any]:
    source, canonical, _ = _registries(structure)
    return {
        "registry_index_version": "generic_relation_field_g3_registry_index",
        "structure_profile_id": structure["profile"]["structure_profile_id"],
        "structure_hash": structure["profile"]["structure_hash"],
        "target_order": "unicode_codepoint_ascending_identity",
        "registries": {
            role: {
                "source_order_ids": source[role],
                "canonical_order_ids": canonical[role],
                "source_order_hash": _canonical_hash(source[role]),
                "canonical_order_hash": _canonical_hash(canonical[role]),
            }
            for role in ("axis", "cell", "edge", "face")
        },
    }


def _array_groups(entry: Mapping[str, Any], keys: Sequence[str]) -> dict[str, tuple[list[Any], str | None]]:
    if "all_arrays_dimension_roles" in entry:
        roles = list(entry["all_arrays_dimension_roles"])
        return {key: (roles, None) for key in keys}
    groups: dict[str, tuple[list[Any], str | None]] = {}
    for value in entry["groups"]:
        group = _mapping(value, "numeric group")
        roles = list(group["dimension_roles"])
        transform = None if group.get("transform") is None else str(group["transform"])
        for raw_key in group["keys"]:
            key = str(raw_key)
            if key in groups:
                raise GenericRelationFieldG3Error(f"numeric array mapped twice: {key}")
            groups[key] = (roles, transform)
    if set(groups) != set(keys):
        missing = sorted(set(keys) - set(groups))
        stale = sorted(set(groups) - set(keys))
        raise GenericRelationFieldG3Error(f"numeric source key mapping mismatch; missing={missing}, stale={stale}")
    return groups


def _canonicalize_array(
    value: np.ndarray,
    roles: Sequence[Any],
    permutations: Mapping[str, np.ndarray],
    registry_sizes: Mapping[str, int],
) -> np.ndarray:
    array = np.asarray(value)
    if array.ndim != len(roles):
        raise GenericRelationFieldG3Error(f"numeric dimension declaration mismatch: shape={array.shape}, roles={roles}")
    result = array
    for dimension, role_value in enumerate(roles):
        if role_value not in STRUCTURAL_ROLES:
            continue
        role = str(role_value)
        if result.shape[dimension] != registry_sizes[role]:
            raise GenericRelationFieldG3Error(
                f"numeric structural dimension mismatch: role={role}, shape={result.shape}, dimension={dimension}"
            )
        result = np.take(result, permutations[role], axis=dimension)
    if result.dtype.kind == "O":
        raise GenericRelationFieldG3Error("object arrays are forbidden")
    return np.ascontiguousarray(result)


def _add_descriptor_derivatives(
    arrays: dict[str, np.ndarray],
    metadata: list[dict[str, Any]],
    *,
    output_key: str,
    descriptor: np.ndarray,
    stage: str,
    payload_id: str,
    source_file: str,
    source_sha: str,
    permutations: Mapping[str, np.ndarray],
    axis_count: int,
) -> None:
    if descriptor.ndim != 2 or descriptor.shape[1] != axis_count + axis_count * axis_count + 1:
        raise GenericRelationFieldG3Error("RF-5 descriptor does not match the G2 axis registry")
    derived = {
        f"{output_key}__axis_signed_flow": (descriptor[:, :axis_count], [None, "axis"]),
        f"{output_key}__source_axis_offsets": (
            descriptor[:, axis_count:-1].reshape(descriptor.shape[0], axis_count, axis_count),
            [None, "axis", "axis"],
        ),
        f"{output_key}__total_absolute_flow": (descriptor[:, -1], [None]),
    }
    sizes = {"axis": axis_count}
    for key, (value, roles) in derived.items():
        canonical = _canonicalize_array(value, roles, permutations, sizes)
        arrays[key] = canonical
        metadata.append(
            {
                "array_key": key,
                "stage": stage,
                "payload_id": payload_id,
                "source_file": source_file,
                "source_sha256": source_sha,
                "source_array_key": output_key.split("__", 1)[1],
                "derived_transform": "rf5_descriptor",
                "dimension_roles": roles,
                "shape": list(canonical.shape),
                "dtype": canonical.dtype.str,
                "content_hash": _array_hash(canonical),
            }
        )


def _materialize_numeric(
    profile: Mapping[str, Any],
    sources: Mapping[str, Path],
    structure: Mapping[str, Any],
) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    source_ids, _, permutations = _registries(structure)
    sizes = {role: len(values) for role, values in source_ids.items()}
    arrays: dict[str, np.ndarray] = {}
    metadata: list[dict[str, Any]] = []
    stages: set[str] = set()
    for entry_value in profile["numeric_payloads"]:
        entry = _mapping(entry_value, "numeric payload")
        path = _payload_path(entry, sources)
        if not path.is_file():
            raise GenericRelationFieldG3Error(f"numeric source file is missing: {entry['payload_id']}")
        loaded = _load_npz(path)
        groups = _array_groups(entry, sorted(loaded))
        source_file = f"{entry['root']}/{entry['path']}"
        source_sha = _sha256_file(path)
        stages.add(str(entry["stage"]))
        for source_key in sorted(loaded):
            roles, transform = groups[source_key]
            canonical = _canonicalize_array(loaded[source_key], roles, permutations, sizes)
            output_key = f"{entry['payload_id']}__{source_key}"
            if output_key in arrays:
                raise GenericRelationFieldG3Error(f"duplicate numeric output key: {output_key}")
            arrays[output_key] = canonical
            metadata.append(
                {
                    "array_key": output_key,
                    "stage": entry["stage"],
                    "payload_id": entry["payload_id"],
                    "source_file": source_file,
                    "source_sha256": source_sha,
                    "source_array_key": source_key,
                    "dimension_roles": roles,
                    "evidence_side": entry.get("evidence_side", "observed_or_inferred_source"),
                    "shape": list(canonical.shape),
                    "dtype": canonical.dtype.str,
                    "content_hash": _array_hash(canonical),
                }
            )
            if transform == "rf5_descriptor":
                _add_descriptor_derivatives(
                    arrays,
                    metadata,
                    output_key=output_key,
                    descriptor=np.asarray(loaded[source_key], dtype=np.float64),
                    stage=str(entry["stage"]),
                    payload_id=str(entry["payload_id"]),
                    source_file=source_file,
                    source_sha=source_sha,
                    permutations=permutations,
                    axis_count=sizes["axis"],
                )
    expected_stages = {f"RF-{index}" for index in range(3, 11)}
    if stages != expected_stages:
        raise GenericRelationFieldG3Error("numeric materialization stage coverage mismatch")
    return arrays, {
        "numeric_index_version": "generic_relation_field_g3_numeric_index",
        "structure_hash": structure["profile"]["structure_hash"],
        "array_count": len(arrays),
        "payload_count": len(profile["numeric_payloads"]),
        "arrays": metadata,
    }


def _read_semantic(path: Path, fmt: str) -> Any:
    if fmt == "json":
        return _json_load(path)
    if fmt == "jsonl":
        rows = []
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if line.strip():
                    rows.append(json.loads(line))
        return {"rows": rows}
    raise GenericRelationFieldG3Error(f"unsupported semantic format: {fmt}")


def _materialize_semantic(
    profile: Mapping[str, Any],
    sources: Mapping[str, Path],
    structure: Mapping[str, Any],
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    stages: set[str] = set()
    axis_ids = [str(row["axis_id"]) for row in structure["axis_registry"]["records"]]
    for entry_value in profile["semantic_payloads"]:
        entry = _mapping(entry_value, "semantic payload")
        path = _payload_path(entry, sources)
        if not path.is_file():
            raise GenericRelationFieldG3Error(f"semantic source file is missing: {entry['payload_id']}")
        payload = _read_semantic(path, str(entry.get("format", "json")))
        stages.add(str(entry["stage"]))
        records.append(
            {
                "payload_id": entry["payload_id"],
                "stage": entry["stage"],
                "source_file": f"{entry['root']}/{entry['path']}",
                "source_sha256": _sha256_file(path),
                "axis_registry_ids": axis_ids,
                "axis_registry_hash": _canonical_hash(axis_ids),
                "payload_hash": _canonical_hash(payload),
                "payload": payload,
            }
        )
    if stages != {f"RF-{index}" for index in range(3, 11)}:
        raise GenericRelationFieldG3Error("semantic materialization stage coverage mismatch")
    return {
        "semantic_payload_version": "generic_relation_field_g3_semantic_payloads",
        "payload_count": len(records),
        "records": records,
    }


def _semantic_by_id(semantic: Mapping[str, Any]) -> dict[str, Any]:
    return {str(row["payload_id"]): row["payload"] for row in semantic["records"]}


def _max_abs(value: np.ndarray) -> float:
    array = np.asarray(value, dtype=np.float64)
    return 0.0 if array.size == 0 else float(np.max(np.abs(array)))


def _canonical_boundary_matrices(structure: Mapping[str, Any]) -> tuple[csr_matrix, csr_matrix]:
    _, canonical, _ = _registries(structure)
    cell_lookup = {identity: index for index, identity in enumerate(canonical["cell"])}
    edge_lookup = {identity: index for index, identity in enumerate(canonical["edge"])}
    face_lookup = {identity: index for index, identity in enumerate(canonical["face"])}
    source_cell_ids = [str(value) for value in structure["cell_arrays"]["cell_ids"].tolist()]
    source_edge_ids = [str(value) for value in structure["edge_arrays"]["edge_ids"].tolist()]
    source_face_ids = [str(value) for value in structure["face_arrays"]["face_ids"].tolist()]
    source = np.asarray(structure["edge_arrays"]["source_cell_ordinal"], dtype=np.int64)
    target = np.asarray(structure["edge_arrays"]["target_cell_ordinal"], dtype=np.int64)
    rows: list[int] = []
    cols: list[int] = []
    data: list[float] = []
    for original_edge, edge_id in enumerate(source_edge_ids):
        column = edge_lookup[edge_id]
        rows.extend((cell_lookup[source_cell_ids[int(source[original_edge])]], cell_lookup[source_cell_ids[int(target[original_edge])]]))
        cols.extend((column, column))
        data.extend((-1.0, 1.0))
    boundary_1 = coo_matrix(
        (data, (rows, cols)), shape=(len(canonical["cell"]), len(canonical["edge"])), dtype=np.float64
    ).tocsr()
    face_arrays = structure["face_arrays"]
    indptr = np.asarray(face_arrays["face_indptr"], dtype=np.int64)
    members = np.asarray(face_arrays["edge_ordinals"], dtype=np.int64)
    signs = np.asarray(face_arrays["edge_signs"], dtype=np.float64)
    b2_rows: list[int] = []
    b2_cols: list[int] = []
    b2_data: list[float] = []
    for original_face, face_id in enumerate(source_face_ids):
        column = face_lookup[face_id]
        for offset in range(int(indptr[original_face]), int(indptr[original_face + 1])):
            edge_id = source_edge_ids[int(members[offset])]
            b2_rows.append(edge_lookup[edge_id])
            b2_cols.append(column)
            b2_data.append(float(signs[offset]))
    boundary_2 = coo_matrix(
        (b2_data, (b2_rows, b2_cols)),
        shape=(len(canonical["edge"]), len(canonical["face"])),
        dtype=np.float64,
    ).tocsr()
    return boundary_1, boundary_2


def _interval_audit(arrays: Mapping[str, np.ndarray], prefix: str) -> tuple[int, float]:
    count = 0
    largest_violation = 0.0
    for key in sorted(arrays):
        if not key.startswith(prefix) or not key.endswith("_minimum"):
            continue
        stem = key[: -len("_minimum")]
        mean_key, maximum_key = f"{stem}_mean", f"{stem}_maximum"
        if mean_key not in arrays or maximum_key not in arrays:
            continue
        minimum = np.asarray(arrays[key], dtype=np.float64)
        mean = np.asarray(arrays[mean_key], dtype=np.float64)
        maximum = np.asarray(arrays[maximum_key], dtype=np.float64)
        violation = max(_max_abs(np.minimum(mean - minimum, 0.0)), _max_abs(np.minimum(maximum - mean, 0.0)))
        largest_violation = max(largest_violation, violation)
        count += 1
    if count == 0:
        raise GenericRelationFieldG3Error(f"no interval triples audited for {prefix}")
    return count, largest_violation


def compute_scientific_invariants(
    arrays: Mapping[str, np.ndarray],
    semantic: Mapping[str, Any],
    structure: Mapping[str, Any],
    profile: Mapping[str, Any],
) -> dict[str, Any]:
    tolerance = {key: float(_resolve_reference(str(value))) for key, value in profile["scientific_tolerance_refs"].items()}
    results: dict[str, Any] = {}

    observed = np.asarray(arrays["rf3_local_flow__observed_delta"], dtype=np.float64)
    reconstructed = np.asarray(arrays["rf3_local_flow__reconstructed_delta"], dtype=np.float64)
    residual = np.asarray(arrays["rf3_unresolved_residual__residual"], dtype=np.float64)
    positive = np.asarray(arrays["rf3_unresolved_residual__positive_residual"], dtype=np.float64)
    negative = np.asarray(arrays["rf3_unresolved_residual__negative_residual"], dtype=np.float64)
    rf3_reconstruction = _max_abs(observed - reconstructed - residual)
    rf3_residual_split = _max_abs(residual - positive + negative)
    if max(rf3_reconstruction, rf3_residual_split) > tolerance["rf3_reconstruction"]:
        raise GenericRelationFieldG3Error("RF-3 generic reconstruction invariant failed")
    results["RF-3"] = {
        "status": "passed",
        "reconstruction_max_abs": rf3_reconstruction,
        "residual_split_max_abs": rf3_residual_split,
        "tolerance_source": profile["scientific_tolerance_refs"]["rf3_reconstruction"],
    }

    candidate_transition = np.asarray(arrays["rf5_candidate_flows__candidate_transition_index"], dtype=np.int64)
    observed_delta = np.asarray(arrays["rf5_candidate_flows__observed_delta"], dtype=np.float64)
    candidate_reconstructed = np.asarray(arrays["rf5_candidate_flows__candidate_reconstructed_delta"], dtype=np.float64)
    candidate_residual = np.asarray(arrays["rf5_candidate_flows__candidate_residual"], dtype=np.float64)
    expected = observed_delta[candidate_transition]
    rf5_reconstruction = _max_abs(expected - candidate_reconstructed - candidate_residual)
    axis_min = np.asarray(arrays["rf5_common_structure__axis_flow_min"], dtype=np.float64)
    axis_mean = np.asarray(arrays["rf5_common_structure__axis_flow_mean"], dtype=np.float64)
    axis_max = np.asarray(arrays["rf5_common_structure__axis_flow_max"], dtype=np.float64)
    rf5_interval_violation = max(_max_abs(np.minimum(axis_mean - axis_min, 0.0)), _max_abs(np.minimum(axis_max - axis_mean, 0.0)))
    if rf5_reconstruction > tolerance["rf5_reconstruction"] or rf5_interval_violation != 0.0:
        raise GenericRelationFieldG3Error("RF-5 candidate-family invariant failed")
    results["RF-5"] = {
        "status": "passed",
        "candidate_count": int(candidate_transition.size),
        "candidate_reconstruction_max_abs": rf5_reconstruction,
        "axis_interval_violation_max_abs": rf5_interval_violation,
        "axis_candidate_width_maximum": _max_abs(axis_max - axis_min),
        "tolerance_source": profile["scientific_tolerance_refs"]["rf5_reconstruction"],
    }

    input_flow = np.asarray(arrays["rf6_candidate_components__input_flow"], dtype=np.float64)
    gradient = np.asarray(arrays["rf6_candidate_components__gradient_flow"], dtype=np.float64)
    circulation = np.asarray(arrays["rf6_candidate_components__circulation_flow"], dtype=np.float64)
    harmonic = np.asarray(arrays["rf6_candidate_components__harmonic_flow"], dtype=np.float64)
    numerical = np.asarray(arrays["rf6_candidate_components__numerical_residual_flow"], dtype=np.float64)
    hodge_reconstruction = _max_abs(input_flow - gradient - circulation - harmonic - numerical)
    boundary_1, boundary_2 = _canonical_boundary_matrices(structure)
    circulation_divergence = _max_abs(np.asarray(boundary_1 @ circulation.T))
    gradient_face = _max_abs(np.asarray(boundary_2.T @ gradient.T))
    if hodge_reconstruction > tolerance["rf6_reconstruction"]:
        raise GenericRelationFieldG3Error("RF-6 Hodge reconstruction failed")
    if circulation_divergence > tolerance["rf6_circulation_divergence"]:
        raise GenericRelationFieldG3Error("RF-6 circulation divergence invariant failed")
    if gradient_face > tolerance["rf6_gradient_face_circulation"]:
        raise GenericRelationFieldG3Error("RF-6 gradient face-circulation invariant failed")
    results["RF-6"] = {
        "status": "passed",
        "reconstruction_max_abs": hodge_reconstruction,
        "circulation_divergence_max_abs": circulation_divergence,
        "gradient_face_circulation_max_abs": gradient_face,
        "harmonic_max_abs": _max_abs(harmonic),
        "tolerance_sources": {
            key: profile["scientific_tolerance_refs"][key]
            for key in ("rf6_reconstruction", "rf6_circulation_divergence", "rf6_gradient_face_circulation")
        },
    }

    rf7_count, rf7_violation = _interval_audit(arrays, "rf7_")
    if rf7_violation != 0.0:
        raise GenericRelationFieldG3Error("RF-7 interval ordering failed")
    results["RF-7"] = {"status": "passed", "interval_triples_checked": rf7_count, "interval_violation_max_abs": rf7_violation}

    rf8_count, rf8_violation = _interval_audit(arrays, "rf8_")
    axis_width = np.asarray(arrays["rf8_axis_flow_family__axis_signed_flow_ambiguity_width"], dtype=np.float64)
    axis_width_expected = np.asarray(arrays["rf8_axis_flow_family__axis_signed_flow_maximum"], dtype=np.float64) - np.asarray(
        arrays["rf8_axis_flow_family__axis_signed_flow_minimum"], dtype=np.float64
    )
    slope_width = np.asarray(arrays["rf8_position_flow_coupling__slope_ambiguity_width"], dtype=np.float64)
    slope_width_expected = np.asarray(arrays["rf8_position_flow_coupling__slope_maximum"], dtype=np.float64) - np.asarray(
        arrays["rf8_position_flow_coupling__slope_minimum"], dtype=np.float64
    )
    width_error = max(_max_abs(axis_width - axis_width_expected), _max_abs(slope_width - slope_width_expected))
    semantic_by_id = _semantic_by_id(semantic)
    innovation_labels = _mapping(semantic_by_id["rf8_innovation_labels"], "RF-8 innovation labels")
    if innovation_labels.get("new_drive_is_not_external_factor") is not True:
        raise GenericRelationFieldG3Error("RF-8 innovation semantics changed")
    if rf8_violation != 0.0 or width_error > 1e-15:
        raise GenericRelationFieldG3Error("RF-8 candidate interval invariant failed")
    results["RF-8"] = {
        "status": "passed",
        "interval_triples_checked": rf8_count,
        "interval_violation_max_abs": rf8_violation,
        "reported_width_error_max_abs": width_error,
        "innovation_and_transport_residual_separate": True,
    }

    risk = _mapping(semantic_by_id["rf9_candidates"], "RF-9 candidates")
    evidence = _mapping(semantic_by_id["rf9_evidence"], "RF-9 evidence")
    counterevidence = _mapping(semantic_by_id["rf9_counterevidence"], "RF-9 counterevidence")
    if risk.get("single_scalar_risk_score_produced") is not False or risk.get("true_irreversibility_claim") is not False:
        raise GenericRelationFieldG3Error("RF-9 semantic boundary changed")
    if any(key in {"risk_score", "scalar_risk_score", "aggregate_risk_score"} for key in _recursive_keys(risk)):
        raise GenericRelationFieldG3Error("RF-9 scalar risk score detected")
    rows = list(risk.get("rows", []))
    evidence_rows = list(evidence.get("rows", []))
    counter_rows = list(counterevidence.get("rows", []))
    if not rows or len(rows) != len(evidence_rows) or len(rows) != len(counter_rows):
        raise GenericRelationFieldG3Error("RF-9 candidate/evidence row alignment failed")
    numeric_candidate_keys = (
        "overconvergence_candidate", "fixation_candidate", "divergence_candidate",
        "recovery_margin_reduction_candidate", "new_drive_coincident_candidate",
        "unresolved_residual_dominance_candidate",
    )
    for key in numeric_candidate_keys:
        numeric = np.asarray(arrays[f"rf9_risk_structure_metrics__{key}"], dtype=np.uint8)
        semantic_values = np.asarray([bool(row[key]) for row in rows], dtype=np.uint8)
        if not np.array_equal(numeric, semantic_values):
            raise GenericRelationFieldG3Error(f"RF-9 numeric/semantic mismatch: {key}")
    results["RF-9"] = {
        "status": "passed",
        "candidate_row_count": len(rows),
        "parallel_candidate_fields_checked": len(numeric_candidate_keys),
        "counterevidence_preserved": True,
        "single_scalar_risk_score_produced": False,
        "true_irreversibility_claim": False,
    }

    snapshot = _mapping(semantic_by_id["rf10_prediction_snapshot"], "RF-10 prediction snapshot")
    leakage = _mapping(semantic_by_id["rf10_leakage_audit"], "RF-10 leakage audit")
    if snapshot.get("future_suffix_read_before_snapshot") is not False or snapshot.get("only_final_RF9_row_used") is not True:
        raise GenericRelationFieldG3Error("RF-10 prediction snapshot causal boundary failed")
    required_leakage = {
        "future_suffix_read_before_prediction_snapshot": False,
        "future_suffix_used_as_prediction_feature": False,
        "nonfinal_RF9_rows_evaluated": False,
        "only_final_RF9_rows_evaluated": True,
        "prediction_snapshot_frozen_before_future_read": True,
        "threshold_tuning_performed": False,
    }
    for key, expected_value in required_leakage.items():
        if leakage.get(key) is not expected_value:
            raise GenericRelationFieldG3Error(f"RF-10 leakage gate failed: {key}")
    results["RF-10"] = {
        "status": "passed",
        "case_count": len(snapshot.get("cases", [])),
        "only_final_rf9_row_used": True,
        "snapshot_frozen_before_future_read": True,
        "future_outcomes_evidence_side": "future_target_only",
    }

    alternative_count = sum(1 for key in arrays if key.startswith("rf4_alternative_candidates__"))
    if alternative_count < 1:
        raise GenericRelationFieldG3Error("RF-4 alternative candidate family is empty")
    results["RF-4"] = {"status": "passed", "alternative_candidate_array_count": alternative_count}
    return {
        "invariant_schema_version": "generic_relation_field_g3_scientific_invariants",
        "stages": {stage: results[stage] for stage in [f"RF-{index}" for index in range(3, 11)]},
        "all_scientific_invariants_pass": True,
    }


def _incidence_arrays(source: np.ndarray, target: np.ndarray, cell_count: int) -> dict[str, np.ndarray]:
    edge_count = source.size
    rows = np.empty(2 * edge_count, dtype=np.int64)
    rows[0::2], rows[1::2] = source, target
    cols = np.repeat(np.arange(edge_count, dtype=np.int64), 2)
    data = np.tile(np.asarray([-1.0, 1.0], dtype=np.float64), edge_count)
    return {
        "incidence_rows": rows,
        "incidence_cols": cols,
        "incidence_data": data,
        "incidence_shape": np.asarray([cell_count, edge_count], dtype=np.int64),
    }


def _empty_boundary() -> dict[str, np.ndarray]:
    return {"boundary_indptr": np.asarray([0], dtype=np.int64), "cell_ordinals": np.empty(0, dtype=np.int64)}


def _product_payload(case: Mapping[str, Any], metrics: Mapping[str, Any]) -> dict[str, Any]:
    bins = tuple(int(value) for value in case["axis_bin_counts"])
    if not bins or any(value < 2 for value in bins):
        raise GenericRelationFieldG3Error("synthetic product bins must be at least two")
    axis_count = len(bins)
    coordinates = np.asarray(list(np.ndindex(bins)), dtype=np.int64)
    cell_ids = np.asarray(["cell/" + "/".join(str(int(value)) for value in row) for row in coordinates])
    lookup = {tuple(int(value) for value in row): index for index, row in enumerate(coordinates)}
    source: list[int] = []
    target: list[int] = []
    edge_axis: list[int] = []
    for cell, row in enumerate(coordinates):
        for axis in range(axis_count):
            if int(row[axis]) >= bins[axis] - 1:
                continue
            following = row.copy()
            following[axis] += 1
            source.append(cell)
            target.append(lookup[tuple(int(value) for value in following)])
            edge_axis.append(axis)
    source_array = np.asarray(source, dtype=np.int64)
    target_array = np.asarray(target, dtype=np.int64)
    edge_count = source_array.size
    cell_values = np.zeros_like(coordinates, dtype=np.float64)
    for axis, count in enumerate(bins):
        cell_values[:, axis] = coordinates[:, axis] / float(count - 1)
    cell_arrays = {
        "cell_ids": cell_ids,
        "axis_bin_indices": coordinates,
        "coordinate_values": cell_values,
    }
    edge_arrays = {
        "edge_ids": np.asarray([f"edge/{index}" for index in range(edge_count)]),
        "source_cell_ordinal": source_array,
        "target_cell_ordinal": target_array,
        "axis_ordinal": np.asarray(edge_axis, dtype=np.int64),
        "topological_length": np.full(edge_count, float(metrics["topological_length"])),
        "coordinate_length": np.full(edge_count, float(metrics["coordinate_length"])),
        "transport_cost": np.full(edge_count, float(metrics["transport_cost"])),
        **_incidence_arrays(source_array, target_array, cell_ids.size),
    }
    if bool(case.get("include_faces")):
        face_arrays = generate_product_faces(coordinates, source_array, target_array, bins, [1, 1, -1, -1])
    else:
        face_arrays = {
            "face_ids": np.asarray([], dtype="<U1"),
            "face_indptr": np.asarray([0], dtype=np.int64),
            "edge_ordinals": np.empty(0, dtype=np.int64),
            "edge_signs": np.empty(0, dtype=np.int8),
        }
    memberships: list[np.ndarray] = []
    for axis, count in enumerate(bins):
        memberships.extend((np.flatnonzero(coordinates[:, axis] == 0), np.flatnonzero(coordinates[:, axis] == count - 1)))
    indptr = [0]
    for values in memberships:
        indptr.append(indptr[-1] + values.size)
    boundary_arrays = {
        "boundary_indptr": np.asarray(indptr, dtype=np.int64),
        "cell_ordinals": np.concatenate(memberships).astype(np.int64),
    }
    profile = {
        "profile_id": str(case["case_id"]),
        "capabilities": {"faces": bool(case.get("include_faces")), "coordinates": True},
        "counts": {
            "axis_count": axis_count,
            "cell_count": cell_ids.size,
            "edge_count": edge_count,
            "face_count": int(face_arrays["face_ids"].size),
            "face_edge_membership_count": int(face_arrays["edge_ordinals"].size),
            "boundary_set_count": len(memberships),
            "connected_component_count": 1,
        },
    }
    return {"profile": profile, "cell_arrays": cell_arrays, "edge_arrays": edge_arrays, "face_arrays": face_arrays, "boundary_arrays": boundary_arrays}


def _graph_payload(case: Mapping[str, Any], metrics: Mapping[str, Any]) -> dict[str, Any]:
    cells = list(case["cells"])
    edges = list(case["edges"])
    faces = list(case.get("faces", []))
    cell_ids = [str(row["cell_id"]) for row in cells]
    if len(set(cell_ids)) != len(cell_ids):
        raise GenericRelationFieldG3Error("synthetic graph contains duplicate cells")
    cell_lookup = {value: index for index, value in enumerate(cell_ids)}
    axis_ids = [str(value) for value in case.get("axis_ids", [])]
    axis_indices = np.asarray([row["axis_bin_indices"] for row in cells], dtype=np.int64).reshape(len(cells), len(axis_ids))
    coordinates = np.asarray([row["coordinates"] for row in cells], dtype=np.float64).reshape(len(cells), len(axis_ids))
    edge_ids = [str(row["edge_id"]) for row in edges]
    edge_lookup = {value: index for index, value in enumerate(edge_ids)}
    source = np.asarray([cell_lookup[str(row["source"])] for row in edges], dtype=np.int64)
    target = np.asarray([cell_lookup[str(row["target"])] for row in edges], dtype=np.int64)
    edge_count = len(edges)
    edge_arrays = {
        "edge_ids": np.asarray(edge_ids),
        "source_cell_ordinal": source,
        "target_cell_ordinal": target,
        "axis_ordinal": np.asarray([int(row["axis_ordinal"]) for row in edges], dtype=np.int64),
        "topological_length": np.full(edge_count, float(metrics["topological_length"])),
        "coordinate_length": np.full(edge_count, float(metrics["coordinate_length"])),
        "transport_cost": np.full(edge_count, float(metrics["transport_cost"])),
        **_incidence_arrays(source, target, len(cells)),
    }
    face_ids: list[str] = []
    members: list[int] = []
    signs: list[int] = []
    indptr = [0]
    for face in faces:
        face_ids.append(str(face["face_id"]))
        for edge_id, sign in face["members"]:
            members.append(edge_lookup[str(edge_id)])
            signs.append(int(sign))
        indptr.append(len(members))
    face_arrays = {
        "face_ids": np.asarray(face_ids, dtype=str),
        "face_indptr": np.asarray(indptr, dtype=np.int64),
        "edge_ordinals": np.asarray(members, dtype=np.int64),
        "edge_signs": np.asarray(signs, dtype=np.int8),
    }
    profile = {
        "profile_id": str(case["case_id"]),
        "axis_ids": axis_ids,
        "capabilities": {"faces": bool(faces), "coordinates": bool(axis_ids)},
        "counts": {
            "axis_count": len(axis_ids),
            "cell_count": len(cells),
            "edge_count": edge_count,
            "face_count": len(face_ids),
            "face_edge_membership_count": len(members),
            "boundary_set_count": 0,
            "connected_component_count": int(case["expected"]["connected_component_count"]),
        },
    }
    return {
        "profile": profile,
        "cell_arrays": {"cell_ids": np.asarray(cell_ids), "axis_bin_indices": axis_indices, "coordinate_values": coordinates},
        "edge_arrays": edge_arrays,
        "face_arrays": face_arrays,
        "boundary_arrays": _empty_boundary(),
    }


def _reorder_payload(source_payload: Mapping[str, Any], case_id: str) -> dict[str, Any]:
    payload = copy.deepcopy(source_payload)
    cells = payload["cell_arrays"]
    edges = payload["edge_arrays"]
    faces = payload["face_arrays"]
    boundaries = payload["boundary_arrays"]
    cell_count = int(np.asarray(cells["cell_ids"]).size)
    edge_count = int(np.asarray(edges["edge_ids"]).size)
    face_count = int(np.asarray(faces["face_ids"]).size)
    cell_perm = np.arange(cell_count - 1, -1, -1, dtype=np.int64)
    edge_perm = np.arange(edge_count - 1, -1, -1, dtype=np.int64)
    face_perm = np.arange(face_count - 1, -1, -1, dtype=np.int64)
    old_cell_to_new = np.empty(cell_count, dtype=np.int64)
    old_cell_to_new[cell_perm] = np.arange(cell_count, dtype=np.int64)
    old_edge_to_new = np.empty(edge_count, dtype=np.int64)
    old_edge_to_new[edge_perm] = np.arange(edge_count, dtype=np.int64)
    for key in ("cell_ids", "axis_bin_indices", "coordinate_values"):
        cells[key] = np.asarray(cells[key])[cell_perm]
    for key in ("edge_ids", "source_cell_ordinal", "target_cell_ordinal", "axis_ordinal", "topological_length", "coordinate_length", "transport_cost"):
        edges[key] = np.asarray(edges[key])[edge_perm]
    edges["source_cell_ordinal"] = old_cell_to_new[np.asarray(edges["source_cell_ordinal"], dtype=np.int64)]
    edges["target_cell_ordinal"] = old_cell_to_new[np.asarray(edges["target_cell_ordinal"], dtype=np.int64)]
    edges.update(_incidence_arrays(edges["source_cell_ordinal"], edges["target_cell_ordinal"], cell_count))
    old_indptr = np.asarray(faces["face_indptr"], dtype=np.int64)
    old_members = np.asarray(faces["edge_ordinals"], dtype=np.int64)
    old_signs = np.asarray(faces["edge_signs"], dtype=np.int8)
    new_members: list[int] = []
    new_signs: list[int] = []
    new_indptr = [0]
    for old_face in face_perm:
        start, end = int(old_indptr[old_face]), int(old_indptr[old_face + 1])
        new_members.extend(old_edge_to_new[old_members[start:end]].tolist())
        new_signs.extend(old_signs[start:end].tolist())
        new_indptr.append(len(new_members))
    faces["face_ids"] = np.asarray(faces["face_ids"])[face_perm]
    faces["face_indptr"] = np.asarray(new_indptr, dtype=np.int64)
    faces["edge_ordinals"] = np.asarray(new_members, dtype=np.int64)
    faces["edge_signs"] = np.asarray(new_signs, dtype=np.int8)
    boundaries["cell_ordinals"] = old_cell_to_new[np.asarray(boundaries["cell_ordinals"], dtype=np.int64)]
    payload["profile"]["profile_id"] = case_id
    return payload


def _synthetic_boundary_matrices(payload: Mapping[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    edges = payload["edge_arrays"]
    faces = payload["face_arrays"]
    shape = tuple(int(value) for value in edges["incidence_shape"])
    boundary_1 = coo_matrix(
        (
            np.asarray(edges["incidence_data"], dtype=np.float64),
            (np.asarray(edges["incidence_rows"], dtype=np.int64), np.asarray(edges["incidence_cols"], dtype=np.int64)),
        ),
        shape=shape,
    ).toarray()
    face_count = int(np.asarray(faces["face_ids"]).size)
    boundary_2 = np.zeros((shape[1], face_count), dtype=np.float64)
    indptr = np.asarray(faces["face_indptr"], dtype=np.int64)
    members = np.asarray(faces["edge_ordinals"], dtype=np.int64)
    signs = np.asarray(faces["edge_signs"], dtype=np.float64)
    for face in range(face_count):
        start, end = int(indptr[face]), int(indptr[face + 1])
        boundary_2[members[start:end], face] = signs[start:end]
    return boundary_1, boundary_2


def _first_betti_number(payload: Mapping[str, Any]) -> int:
    boundary_1, boundary_2 = _synthetic_boundary_matrices(payload)
    rank_1 = int(np.linalg.matrix_rank(boundary_1)) if boundary_1.size else 0
    rank_2 = int(np.linalg.matrix_rank(boundary_2)) if boundary_2.size else 0
    return int(boundary_1.shape[1] - rank_1 - rank_2)


def _structure_signature(payload: Mapping[str, Any]) -> str:
    cells = payload["cell_arrays"]
    edges = payload["edge_arrays"]
    faces = payload["face_arrays"]
    cell_ids = [str(value) for value in np.asarray(cells["cell_ids"]).tolist()]
    edge_ids = [str(value) for value in np.asarray(edges["edge_ids"]).tolist()]
    source = np.asarray(edges["source_cell_ordinal"], dtype=np.int64)
    target = np.asarray(edges["target_cell_ordinal"], dtype=np.int64)
    edge_rows = sorted(
        (edge_ids[index], cell_ids[int(source[index])], cell_ids[int(target[index])], int(edges["axis_ordinal"][index]))
        for index in range(len(edge_ids))
    )
    face_ids = [str(value) for value in np.asarray(faces["face_ids"]).tolist()]
    indptr = np.asarray(faces["face_indptr"], dtype=np.int64)
    members = np.asarray(faces["edge_ordinals"], dtype=np.int64)
    signs = np.asarray(faces["edge_signs"], dtype=np.int64)
    face_rows = []
    for face, face_id in enumerate(face_ids):
        start, end = int(indptr[face]), int(indptr[face + 1])
        face_rows.append((face_id, [(edge_ids[int(edge)], int(sign)) for edge, sign in zip(members[start:end], signs[start:end], strict=True)]))
    return _canonical_hash({"cells": sorted(cell_ids), "edges": edge_rows, "faces": sorted(face_rows)})


def run_synthetic_structure_audit(profile: Mapping[str, Any]) -> dict[str, Any]:
    metrics = profile["synthetic_edge_metrics"]
    payloads: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    for case_value in profile["synthetic_structure_cases"]:
        case = _mapping(case_value, "synthetic case")
        case_id = str(case["case_id"])
        kind = str(case["kind"])
        if kind == "product":
            payload = _product_payload(case, metrics)
        elif kind == "graph":
            payload = _graph_payload(case, metrics)
        elif kind == "reordered_copy":
            source_id = str(case["source_case_id"])
            if source_id not in payloads:
                raise GenericRelationFieldG3Error("reordered synthetic case source must appear earlier")
            payload = _reorder_payload(payloads[source_id], case_id)
        else:
            raise GenericRelationFieldG3Error(f"unsupported synthetic structure kind: {kind}")
        validation = validate_structure_payload(
            payload["profile"], payload["cell_arrays"], payload["edge_arrays"], payload["face_arrays"], payload["boundary_arrays"]
        )
        betti = _first_betti_number(payload)
        signature = _structure_signature(payload)
        expected = _mapping(case["expected"], "synthetic expected")
        for key in ("axis_count", "face_count", "connected_component_count"):
            if key in expected and int(validation[key]) != int(expected[key]):
                raise GenericRelationFieldG3Error(f"synthetic case {case_id} expected {key} mismatch")
        if "first_betti_number" in expected and betti != int(expected["first_betti_number"]):
            raise GenericRelationFieldG3Error(f"synthetic case {case_id} first Betti number mismatch")
        if expected.get("canonical_signature_matches_source") is True:
            source_id = str(case["source_case_id"])
            if signature != _structure_signature(payloads[source_id]):
                raise GenericRelationFieldG3Error("identifier reordering changed the canonical structure signature")
        payloads[case_id] = payload
        rows.append(
            {
                "case_id": case_id,
                "kind": kind,
                **validation,
                "first_betti_number": betti,
                "canonical_structure_signature": signature,
                "coordinates_available": bool(payload["profile"]["capabilities"]["coordinates"]),
                "faces_available": bool(payload["profile"]["capabilities"]["faces"]),
            }
        )
    return {
        "synthetic_audit_version": "generic_relation_field_g3_synthetic_structure_audit",
        "case_count": len(rows),
        "cases": rows,
        "all_synthetic_structure_cases_pass": True,
        "prediction_accuracy_evaluated": False,
        "generic_gk_generation_evaluated": False,
    }


def validate_capability_claim(capabilities: Mapping[str, Any], claim: Mapping[str, Any]) -> None:
    claim_type = str(claim.get("claim_type", ""))
    availability = str(claim.get("availability_status", ""))
    if claim_type == "harmonic_component" and capabilities.get("faces") is False:
        if availability not in {"unavailable", "withheld"} or claim.get("value") not in (None, []):
            raise GenericRelationFieldG3Error("harmonic component cannot be claimed without faces")
    if claim_type == "axis_direction" and capabilities.get("coordinates") is False:
        if availability not in {"unavailable", "withheld"} or claim.get("direction_scope_ids") not in (None, []):
            raise GenericRelationFieldG3Error("axis direction cannot be claimed without coordinates")


def validate_mass_transition(from_mass: Sequence[float], to_mass: Sequence[float], *, tolerance: float) -> None:
    for name, values in (("from_mass", from_mass), ("to_mass", to_mass)):
        array = np.asarray(values, dtype=np.float64)
        if array.ndim != 1 or array.size == 0 or not np.all(np.isfinite(array)):
            raise GenericRelationFieldG3Error(f"{name} is not a finite vector")
        if np.any(array < 0.0):
            raise GenericRelationFieldG3Error(f"{name} contains negative mass; repair is forbidden")
        if abs(float(array.sum()) - 1.0) > tolerance:
            raise GenericRelationFieldG3Error(f"{name} mass is not conserved; renormalization is forbidden")


def validate_prediction_alignment_record(record: Mapping[str, Any], profile: Mapping[str, Any]) -> None:
    if record.get("alignment_status") != "conflicting":
        return
    summary = _mapping(record.get("summary", {}), "prediction alignment summary")
    forbidden = set(profile["negative_guard_profile"]["conflicting_alignment_forbidden_summary_keys"])
    overlap = sorted(forbidden & set(summary))
    if overlap:
        raise GenericRelationFieldG3Error(f"conflicting predictors cannot be averaged: {overlap}")


def validate_probability_claim(claim: Mapping[str, Any], profile: Mapping[str, Any]) -> None:
    if claim.get("value_type") != "probability":
        return
    minimum = int(_resolve_reference(str(profile["negative_guard_profile"]["probability_claim_minimum_support_ref"])))
    if claim.get("calibration_status") != "calibrated_independent_evaluation":
        raise GenericRelationFieldG3Error("probability claim is not independently calibrated")
    if int(claim.get("support_count", -1)) < minimum:
        raise GenericRelationFieldG3Error("probability claim has insufficient support")
    if not claim.get("calibration_artifact_ref"):
        raise GenericRelationFieldG3Error("probability claim lacks calibration provenance")


def validate_simulator_output(output: Mapping[str, Any], profile: Mapping[str, Any]) -> None:
    forbidden = set(profile["negative_guard_profile"]["simulator_forbidden_keys"])
    overlap = sorted(forbidden & set(_recursive_keys(output)))
    if overlap:
        raise GenericRelationFieldG3Error(f"simulator produced action-evaluation output: {overlap}")


def validate_no_future_feature_keys(payload: Mapping[str, Any], profile: Mapping[str, Any]) -> None:
    fragments = [str(value) for value in profile["negative_guard_profile"]["future_forbidden_key_fragments"]]
    bad = sorted({key for key in _recursive_keys(payload) if any(fragment in key for fragment in fragments)})
    if bad:
        raise GenericRelationFieldG3Error(f"future information key detected: {bad}")


def run_negative_guard_audit(profile: Mapping[str, Any]) -> dict[str, Any]:
    checks: dict[str, bool] = {}

    def rejected(name: str, callback: Any) -> None:
        try:
            callback()
        except (GenericRelationFieldG3Error, GenericRelationFieldG2Error):
            checks[name] = True
        else:
            raise GenericRelationFieldG3Error(f"negative guard did not reject: {name}")

    rejected(
        "harmonic_without_faces",
        lambda: validate_capability_claim(
            {"faces": False, "coordinates": False},
            {"claim_type": "harmonic_component", "availability_status": "valid", "value": [0.0]},
        ),
    )
    rejected(
        "axis_direction_without_coordinates",
        lambda: validate_capability_claim(
            {"faces": False, "coordinates": False},
            {"claim_type": "axis_direction", "availability_status": "valid", "direction_scope_ids": ["axis/x"]},
        ),
    )
    rejected("future_information", lambda: validate_no_future_feature_keys({"future_state": [1]}, profile))
    rejected("negative_mass", lambda: validate_mass_transition([1.1, -0.1], [1.0, 0.0], tolerance=1e-12))
    rejected(
        "conflicting_predictor_average",
        lambda: validate_prediction_alignment_record(
            {"alignment_status": "conflicting", "summary": {"averaged_prediction": 0.5}}, profile
        ),
    )
    rejected(
        "unsupported_probability",
        lambda: validate_probability_claim(
            {"value_type": "probability", "calibration_status": "uncalibrated", "support_count": 1}, profile
        ),
    )
    rejected("simulator_action_selection", lambda: validate_simulator_output({"optimal_action": "x"}, profile))
    inherited_g2_checks = {
        "structure_hash_mismatch": "required_g2_integration_rejection_test",
        "structure_change_inside_kt": "required_g2_contract_rejection_test",
        "unknown_identity": "required_g2_field_record_rejection_test",
    }
    return {
        "negative_guard_audit_version": "generic_relation_field_g3_negative_guard_audit",
        "executed_g3_checks": checks,
        "inherited_g2_required_checks": inherited_g2_checks,
        "executed_g3_guard_count": len(checks),
        "inherited_g2_required_guard_count": len(inherited_g2_checks),
        "all_executed_g3_guards_closed": all(checks.values()),
        "all_required_negative_guard_coverage_declared": (
            set(checks) | set(inherited_g2_checks)
            == {
                "harmonic_without_faces",
                "axis_direction_without_coordinates",
                "future_information",
                "negative_mass",
                "conflicting_predictor_average",
                "unsupported_probability",
                "simulator_action_selection",
                "structure_hash_mismatch",
                "structure_change_inside_kt",
                "unknown_identity",
            }
        ),
    }


def _expected_validation(
    contract: Mapping[str, Any],
    numeric_index: Mapping[str, Any],
    semantic: Mapping[str, Any],
    invariants: Mapping[str, Any],
    synthetic: Mapping[str, Any],
    negative: Mapping[str, Any],
    legacy_validations: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "g3_scientific_compatibility_gate": "passed",
        "required_stage_count": len(contract["required_stages"]),
        "legacy_stage_validator_count": len(legacy_validations),
        "numeric_payload_count": int(numeric_index["payload_count"]),
        "numeric_array_count": int(numeric_index["array_count"]),
        "semantic_payload_count": int(semantic["payload_count"]),
        "all_scientific_invariants_pass": bool(invariants["all_scientific_invariants_pass"]),
        "all_synthetic_structure_cases_pass": bool(synthetic["all_synthetic_structure_cases_pass"]),
        "all_executed_g3_guards_closed": bool(negative["all_executed_g3_guards_closed"]),
        "all_required_negative_guard_coverage_declared": bool(
            negative["all_required_negative_guard_coverage_declared"]
        ),
        "inherited_g2_guards_executed_by_this_artifact": False,
        "source_artifacts_unchanged": True,
        "prediction_model_implemented": False,
        "prediction_accuracy_evaluated": False,
        "unknown_structure_accuracy_evaluated": False,
        "action_selection_performed": False,
    }


def _expected_identity(
    contract: Mapping[str, Any],
    profile: Mapping[str, Any],
    structure: Mapping[str, Any],
    sources: Mapping[str, Path],
    source_hashes: Mapping[str, str],
) -> dict[str, Any]:
    identity_basis = {
        "contract_hash": _canonical_hash(contract),
        "validation_profile_hash": _canonical_hash(profile),
        "structure_hash": structure["profile"]["structure_hash"],
        "source_hashes": dict(source_hashes),
        "source_contract_hashes": _source_contract_hashes(profile),
        "declared_source_identity_hashes": _declared_source_identity_hashes(profile, sources),
    }
    return {
        "artifact_id": _canonical_hash(identity_basis),
        "artifact_version": "generic_relation_field_g3_scientific_compatibility",
        **identity_basis,
        "canonical_gk_or_rf_writeback_performed": False,
        "prediction_model_implemented": False,
    }


def build_scientific_compatibility_artifact(
    structure_artifact_dir: str | Path,
    sources: Mapping[str, str | Path],
    output: str | Path,
    *,
    contract_path: str | Path = DEFAULT_CONTRACT,
    validation_profile_path: str | Path = DEFAULT_PROFILE,
) -> Path:
    target = Path(output)
    if target.exists():
        raise GenericRelationFieldG3Error(f"output already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    contract = load_contract(contract_path)
    profile = load_validation_profile(validation_profile_path)
    resolved = _normalize_sources(sources, profile)
    structure = _load_structure_artifact(Path(structure_artifact_dir), verify_manifest=True)
    if structure["profile"].get("source_grid_manifest_hash") != _sha256_file(resolved["grid"] / "manifest.json"):
        raise GenericRelationFieldG3Error("G2 structure and RF source grid do not match")
    source_hashes_before = _source_hashes(resolved)
    legacy_validations = _run_legacy_validators(resolved)
    numeric_arrays, numeric_index = _materialize_numeric(profile, resolved, structure)
    semantic = _materialize_semantic(profile, resolved, structure)
    invariants = compute_scientific_invariants(numeric_arrays, semantic, structure, profile)
    synthetic = run_synthetic_structure_audit(profile)
    negative = run_negative_guard_audit(profile)
    source_hashes_after = _source_hashes(resolved)
    if source_hashes_before != source_hashes_after:
        raise GenericRelationFieldG3Error("source artifact changed during G3 build")
    registry_index = _registry_index(structure)
    identity = _expected_identity(contract, profile, structure, resolved, source_hashes_before)
    validation = _expected_validation(contract, numeric_index, semantic, invariants, synthetic, negative, legacy_validations)
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp-", dir=target.parent))
    try:
        storage = contract["storage"]
        _json_dump(temporary / storage["contract_file"], contract)
        _json_dump(temporary / storage["validation_profile_file"], profile)
        _json_dump(temporary / storage["identity_file"], identity)
        _json_dump(temporary / storage["registry_index_file"], registry_index)
        _write_deterministic_npz(temporary / storage["numeric_payload_file"], numeric_arrays)
        _json_dump(temporary / storage["numeric_index_file"], numeric_index)
        _json_dump(temporary / storage["semantic_payload_file"], semantic)
        _json_dump(temporary / storage["scientific_invariants_file"], invariants)
        _json_dump(temporary / storage["synthetic_structure_audit_file"], synthetic)
        _json_dump(temporary / storage["negative_guard_audit_file"], negative)
        _json_dump(temporary / storage["validation_file"], validation)
        _write_manifest(temporary, "generic_relation_field_g3_scientific_compatibility")
        os.replace(temporary, target)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return target


def _assert_numeric_equal(expected: Mapping[str, np.ndarray], actual: Mapping[str, np.ndarray]) -> None:
    if set(expected) != set(actual):
        raise GenericRelationFieldG3Error("G3 numeric payload key set mismatch")
    for key in sorted(expected):
        left, right = np.asarray(expected[key]), np.asarray(actual[key])
        if left.shape != right.shape or left.dtype != right.dtype or not np.array_equal(left, right, equal_nan=True):
            raise GenericRelationFieldG3Error(f"G3 numeric payload mismatch: {key}")


def validate_scientific_compatibility_artifact(
    input_path: str | Path,
    structure_artifact_dir: str | Path,
    sources: Mapping[str, str | Path],
    *,
    contract_path: str | Path = DEFAULT_CONTRACT,
    validation_profile_path: str | Path = DEFAULT_PROFILE,
) -> dict[str, Any]:
    root = Path(input_path)
    _verify_manifest(root)
    contract = load_contract(contract_path)
    embedded_contract = _json_load(root / "contract.json")
    if embedded_contract != contract:
        raise GenericRelationFieldG3Error("G3 embedded contract does not match the canonical contract")
    profile = load_validation_profile(validation_profile_path)
    embedded_profile = _json_load(root / "validation_profile.json")
    if embedded_profile != profile:
        raise GenericRelationFieldG3Error("G3 embedded validation profile does not match the canonical profile")
    resolved = _normalize_sources(sources, profile)
    structure = _load_structure_artifact(Path(structure_artifact_dir), verify_manifest=True)
    identity = _json_load(root / contract["storage"]["identity_file"])
    source_hashes_before = _source_hashes(resolved)
    expected_identity = _expected_identity(contract, profile, structure, resolved, source_hashes_before)
    if identity != expected_identity:
        raise GenericRelationFieldG3Error("G3 identity payload mismatch")
    legacy_validations = _run_legacy_validators(resolved)
    expected_arrays, expected_index = _materialize_numeric(profile, resolved, structure)
    expected_semantic = _materialize_semantic(profile, resolved, structure)
    expected_invariants = compute_scientific_invariants(expected_arrays, expected_semantic, structure, profile)
    expected_synthetic = run_synthetic_structure_audit(profile)
    expected_negative = run_negative_guard_audit(profile)
    expected_registry = _registry_index(structure)
    actual_arrays = _load_npz(root / contract["storage"]["numeric_payload_file"])
    _assert_numeric_equal(expected_arrays, actual_arrays)
    comparisons = (
        (contract["storage"]["numeric_index_file"], expected_index),
        (contract["storage"]["semantic_payload_file"], expected_semantic),
        (contract["storage"]["scientific_invariants_file"], expected_invariants),
        (contract["storage"]["synthetic_structure_audit_file"], expected_synthetic),
        (contract["storage"]["negative_guard_audit_file"], expected_negative),
        (contract["storage"]["registry_index_file"], expected_registry),
    )
    for relative, expected in comparisons:
        if _json_load(root / relative) != expected:
            raise GenericRelationFieldG3Error(f"G3 independently recomputed payload mismatch: {relative}")
    expected_validation = _expected_validation(
        contract, expected_index, expected_semantic, expected_invariants, expected_synthetic, expected_negative, legacy_validations
    )
    if _json_load(root / contract["storage"]["validation_file"]) != expected_validation:
        raise GenericRelationFieldG3Error("G3 validation payload mismatch")
    if _source_hashes(resolved) != source_hashes_before:
        raise GenericRelationFieldG3Error("source artifact changed during G3 validation")
    return expected_validation


def _source_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--grid", required=True)
    parser.add_argument("--trajectory", required=True)
    for stage in range(3, 11):
        parser.add_argument(f"--rf{stage}", required=True)
    parser.add_argument("--rf10-case-manifest", required=True)


def _sources_from_args(args: argparse.Namespace) -> dict[str, str]:
    return {
        "grid": args.grid,
        "trajectory": args.trajectory,
        **{f"rf{stage}": getattr(args, f"rf{stage}") for stage in range(3, 11)},
        "rf10_case_manifest": args.rf10_case_manifest,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="build a G3 compatibility artifact")
    build.add_argument("--structure", required=True)
    build.add_argument("--output", required=True)
    build.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    build.add_argument("--profile", default=str(DEFAULT_PROFILE))
    _source_arguments(build)
    validate = subparsers.add_parser("validate", help="independently validate a G3 artifact")
    validate.add_argument("--input", required=True)
    validate.add_argument("--structure", required=True)
    validate.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    validate.add_argument("--profile", default=str(DEFAULT_PROFILE))
    _source_arguments(validate)
    synthetic = subparsers.add_parser("synthetic", help="run the topology-independence matrix")
    synthetic.add_argument("--profile", default=str(DEFAULT_PROFILE))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "build":
        output = build_scientific_compatibility_artifact(
            args.structure,
            _sources_from_args(args),
            args.output,
            contract_path=args.contract,
            validation_profile_path=args.profile,
        )
        print(output)
    elif args.command == "validate":
        result = validate_scientific_compatibility_artifact(
            args.input,
            args.structure,
            _sources_from_args(args),
            contract_path=args.contract,
            validation_profile_path=args.profile,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        result = run_synthetic_structure_audit(load_validation_profile(args.profile))
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "GenericRelationFieldG3Error",
    "build_scientific_compatibility_artifact",
    "compute_scientific_invariants",
    "load_contract",
    "load_validation_profile",
    "run_negative_guard_audit",
    "run_synthetic_structure_audit",
    "validate_capability_claim",
    "validate_contract",
    "validate_mass_transition",
    "validate_no_future_feature_keys",
    "validate_prediction_alignment_record",
    "validate_probability_claim",
    "validate_scientific_compatibility_artifact",
    "validate_simulator_output",
    "validate_validation_profile",
]
