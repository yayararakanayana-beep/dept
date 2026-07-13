from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping


class RelationFieldPredictionP2PrecursorAuditError(ValueError):
    """P2-4契約、入力境界、監査成果物または検証結果の不整合。"""


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def canonical_digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def tree_hash(root: Path) -> str:
    rows = [
        (path.relative_to(root).as_posix(), sha256_file(path), path.stat().st_size)
        for path in sorted(root.rglob("*"))
        if path.is_file()
    ]
    return canonical_digest(rows)


def manifest_entries(
    root: Path, *, excluded: Iterable[str] = ("manifest.json",)
) -> list[dict[str, Any]]:
    excluded_set = set(excluded)
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": sha256_file(path),
            "size_bytes": path.stat().st_size,
        }
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.relative_to(root).as_posix() not in excluded_set
    ]


def write_manifest(root: Path, artifact_version: str) -> None:
    dump_json(
        root / "manifest.json",
        {
            "artifact_version": artifact_version,
            "hash_algorithm": "sha256",
            "files": manifest_entries(root),
        },
    )


def verify_manifest(root: Path) -> None:
    path = root / "manifest.json"
    if not path.is_file():
        raise RelationFieldPredictionP2PrecursorAuditError(
            f"manifest missing: {root}"
        )
    manifest = load_json(path)
    expected: set[str] = set()
    for raw in manifest.get("files", []):
        relative = str(raw.get("path", ""))
        if not relative or relative == "manifest.json" or relative in expected:
            raise RelationFieldPredictionP2PrecursorAuditError(
                "manifest contains invalid path"
            )
        expected.add(relative)
        item = root / relative
        if (
            not item.is_file()
            or item.stat().st_size != int(raw.get("size_bytes", -1))
            or sha256_file(item) != raw.get("sha256")
        ):
            raise RelationFieldPredictionP2PrecursorAuditError(
                f"manifest mismatch: {relative}"
            )
    actual = {
        item.relative_to(root).as_posix()
        for item in root.rglob("*")
        if item.is_file() and item != path
    }
    if actual != expected:
        raise RelationFieldPredictionP2PrecursorAuditError(
            "manifest file set mismatch"
        )


def validate_contract(contract: Mapping[str, Any]) -> None:
    if (
        contract.get("contract_version")
        != "relation_field_prediction_p2_precursor_audit_v1"
    ):
        raise RelationFieldPredictionP2PrecursorAuditError(
            "unsupported P2-4 contract"
        )
    if (
        contract.get("parents", {}).get("p2_contract_version")
        != "relation_field_prediction_coordinates_p2_v1"
    ):
        raise RelationFieldPredictionP2PrecursorAuditError(
            "P2-4 parent P2 contract changed"
        )
    if (
        contract.get("parents", {}).get("rf10_contract_version")
        != "relation_field_predictive_validation_rc1"
    ):
        raise RelationFieldPredictionP2PrecursorAuditError(
            "P2-4 parent RF-10 contract changed"
        )
    horizons = [int(value) for value in contract.get("evaluation", {}).get("horizons", [])]
    if horizons != [1, 2, 4]:
        raise RelationFieldPredictionP2PrecursorAuditError(
            "P2-4 horizons must remain 1, 2, and 4"
        )
    if contract.get("evaluation", {}).get("model_fitting_forbidden") is not True:
        raise RelationFieldPredictionP2PrecursorAuditError(
            "P2-4 must not fit a predictor"
        )
    if contract.get("evaluation", {}).get("cross_target_aggregation_forbidden") is not True:
        raise RelationFieldPredictionP2PrecursorAuditError(
            "P2-4 must not aggregate risk targets"
        )
    if set(contract.get("targets", {})) != {
        "overconvergence",
        "fixation",
        "divergence",
        "recovery_margin_reduction",
    }:
        raise RelationFieldPredictionP2PrecursorAuditError(
            "P2-4 primary target set changed"
        )
    if (
        contract.get("input", {}).get(
            "prediction_snapshot_frozen_before_full_trajectory_read"
        )
        is not True
    ):
        raise RelationFieldPredictionP2PrecursorAuditError(
            "P2-4 snapshot must precede future read"
        )
    semantic = contract.get("semantic_limits", {})
    for key in (
        "true_irreversibility_claim",
        "causal_prediction_claim",
        "deployment_readiness_claim",
        "action_recommendation_claim",
        "p3_model_quality_claim",
    ):
        if semantic.get(key) is not False:
            raise RelationFieldPredictionP2PrecursorAuditError(
                f"P2-4 forbidden semantic claim enabled: {key}"
            )


def load_contract(path: str | Path) -> dict[str, Any]:
    value = load_json(Path(path))
    validate_contract(value)
    return value


def resolve_case_manifest(
    path: str | Path, contract: Mapping[str, Any]
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    manifest_path = Path(path).resolve()
    raw = load_json(manifest_path)
    if raw.get("manifest_version") != contract["input"]["case_manifest_version"]:
        raise RelationFieldPredictionP2PrecursorAuditError(
            "P2-4 case manifest version mismatch"
        )
    cases = raw.get("cases")
    if not isinstance(cases, list) or not cases:
        raise RelationFieldPredictionP2PrecursorAuditError(
            "P2-4 case manifest is empty"
        )
    required = list(contract["input"]["required_case_fields"])
    allowed = set(contract["input"]["allowed_partitions"])
    seen_ids: set[str] = set()
    group_partitions: dict[str, set[str]] = {}
    resolved: list[dict[str, Any]] = []
    for index, item in enumerate(cases):
        if not isinstance(item, dict) or any(field not in item for field in required):
            raise RelationFieldPredictionP2PrecursorAuditError(
                f"P2-4 case field mismatch at index {index}"
            )
        case_id = str(item["case_id"])
        partition = str(item["partition"])
        group_id = str(item["trajectory_group_id"])
        if not case_id or case_id in seen_ids:
            raise RelationFieldPredictionP2PrecursorAuditError(
                "P2-4 case_id must be unique"
            )
        if not group_id:
            raise RelationFieldPredictionP2PrecursorAuditError(
                "P2-4 trajectory_group_id must be nonempty"
            )
        if partition not in allowed:
            raise RelationFieldPredictionP2PrecursorAuditError(
                f"P2-4 unsupported partition: {partition}"
            )
        seen_ids.add(case_id)
        group_partitions.setdefault(group_id, set()).add(partition)
        row: dict[str, Any] = {
            "case_id": case_id,
            "partition": partition,
            "trajectory_group_id": group_id,
            "cutoff_t": int(item["cutoff_t"]),
        }
        if row["cutoff_t"] < 1:
            raise RelationFieldPredictionP2PrecursorAuditError(
                "P2-4 cutoff_t must be positive"
            )
        for field in required:
            if field in {"case_id", "partition", "trajectory_group_id", "cutoff_t"}:
                continue
            raw_path = item[field]
            if not isinstance(raw_path, str) or not raw_path:
                raise RelationFieldPredictionP2PrecursorAuditError(
                    f"P2-4 missing case path: {field}"
                )
            candidate = Path(raw_path)
            row[field] = (
                candidate.resolve()
                if candidate.is_absolute()
                else (manifest_path.parent / candidate).resolve()
            )
        resolved.append(row)
    crossing = {
        group: sorted(partitions)
        for group, partitions in group_partitions.items()
        if len(partitions) > 1
    }
    if crossing:
        raise RelationFieldPredictionP2PrecursorAuditError(
            f"P2-4 trajectory group crosses partitions: {crossing}"
        )
    return raw, resolved
