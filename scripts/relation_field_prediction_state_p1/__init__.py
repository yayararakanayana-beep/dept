"""P1公開入口。

実装核を同一パッケージ内から読み込み、P1の階層成果物に必要な
入れ子マニフェスト処理とリポジトリ基準パスだけを局所的に固定する。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Sequence

_PACKAGE_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _PACKAGE_DIR.parents[1]
_CORE_PATH = _PACKAGE_DIR / "_core.py"
_SPEC = importlib.util.spec_from_file_location(
    "_relation_field_prediction_state_p1_core",
    _CORE_PATH,
)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"cannot load P1 core module: {_CORE_PATH}")
_CORE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _CORE
_SPEC.loader.exec_module(_CORE)

DEFAULT_CONTRACT = _REPO_ROOT / "configs" / "relation_field_prediction_state_p1_contract.json"
DEFAULT_PROFILE = _REPO_ROOT / "configs" / "relation_field_prediction_state_p1_extraction_profile.json"
DEFAULT_RISK_REGISTRY = _REPO_ROOT / "configs" / "relation_field_prediction_state_p1_risk_registry.json"
_CORE.ROOT = _REPO_ROOT
_CORE.DEFAULT_CONTRACT = DEFAULT_CONTRACT
_CORE.DEFAULT_PROFILE = DEFAULT_PROFILE
_CORE.DEFAULT_RISK_REGISTRY = DEFAULT_RISK_REGISTRY


def _p1_manifest_entries(root: Path) -> list[dict[str, Any]]:
    manifest_path = root / "manifest.json"
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": _CORE._sha256_file(path),
            "size_bytes": path.stat().st_size,
        }
        for path in sorted(root.rglob("*"))
        if path.is_file() and path != manifest_path
    ]


def _write_p1_manifest(root: Path, artifact_version: str) -> None:
    _CORE._json_dump(
        root / "manifest.json",
        {
            "artifact_version": artifact_version,
            "hash_algorithm": "sha256",
            "files": _p1_manifest_entries(root),
        },
    )


def _verify_p1_manifest(root: Path) -> None:
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise _CORE.RelationFieldPredictionStateP1Error("manifest.json is missing")
    manifest = _CORE._json_load(manifest_path)
    expected: set[str] = set()
    for entry in manifest.get("files", []):
        relative = str(entry.get("path", ""))
        if not relative or relative in expected or relative == "manifest.json":
            raise _CORE.RelationFieldPredictionStateP1Error(
                "P1 manifest contains an invalid path"
            )
        expected.add(relative)
        path = root / relative
        if not path.is_file():
            raise _CORE.RelationFieldPredictionStateP1Error(
                f"P1 manifest file missing: {relative}"
            )
        if path.stat().st_size != int(entry.get("size_bytes", -1)):
            raise _CORE.RelationFieldPredictionStateP1Error(
                f"P1 manifest size mismatch: {relative}"
            )
        if _CORE._sha256_file(path) != entry.get("sha256"):
            raise _CORE.RelationFieldPredictionStateP1Error(
                f"P1 manifest hash mismatch: {relative}"
            )
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path != manifest_path
    }
    if actual != expected:
        raise _CORE.RelationFieldPredictionStateP1Error(
            "P1 manifest file set mismatch"
        )


# P1だけが入れ子成果物を持つため、既存G2の共通関数は変更しない。
_CORE._write_manifest = _write_p1_manifest
_CORE._verify_manifest = _verify_p1_manifest

RelationFieldPredictionStateP1Error = _CORE.RelationFieldPredictionStateP1Error
P1_STAGES = _CORE.P1_STAGES
validate_contract = _CORE.validate_contract
validate_extraction_profile = _CORE.validate_extraction_profile
validate_risk_registry = _CORE.validate_risk_registry
validate_prediction_state_series = _CORE.validate_prediction_state_series
main = _CORE.main


def load_contract(path: str | Path = DEFAULT_CONTRACT) -> dict[str, Any]:
    return _CORE.load_contract(path)


def load_extraction_profile(path: str | Path = DEFAULT_PROFILE) -> dict[str, Any]:
    return _CORE.load_extraction_profile(path)


def load_risk_registry(path: str | Path = DEFAULT_RISK_REGISTRY) -> dict[str, Any]:
    return _CORE.load_risk_registry(path)


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
    return _CORE.build_prediction_state_series(
        trajectory_dir,
        grid_artifact_dir,
        structure_artifact_dir,
        output,
        origins=origins,
        contract_path=contract_path,
        extraction_profile_path=extraction_profile_path,
        risk_registry_path=risk_registry_path,
    )


__all__ = [
    "RelationFieldPredictionStateP1Error",
    "DEFAULT_CONTRACT",
    "DEFAULT_PROFILE",
    "DEFAULT_RISK_REGISTRY",
    "P1_STAGES",
    "load_contract",
    "validate_contract",
    "load_extraction_profile",
    "validate_extraction_profile",
    "load_risk_registry",
    "validate_risk_registry",
    "build_prediction_state_series",
    "validate_prediction_state_series",
    "main",
]
