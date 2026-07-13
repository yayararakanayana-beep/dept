"""P2-2: 因果的連続座標系列の構築と独立検証。"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from ._builder import build_coordinate_series
from ._common import (
    RelationFieldPredictionCoordinatesP2Error,
    load_contract as _load_contract,
    load_registry as _load_registry,
    validate_contract,
    validate_registry,
)
from ._independent_validator import validate_coordinate_series

_PACKAGE = Path(__file__).resolve().parent
_ROOT = _PACKAGE.parents[1]
DEFAULT_CONTRACT = _ROOT / "configs" / "relation_field_prediction_coordinates_p2_contract.json"
DEFAULT_REGISTRY = _ROOT / "configs" / "relation_field_prediction_coordinates_p2_registry.json"


def load_contract(path: str | Path = DEFAULT_CONTRACT) -> dict[str, Any]:
    return _load_contract(path)


def load_registry(path: str | Path = DEFAULT_REGISTRY) -> dict[str, Any]:
    return _load_registry(path)


def build_relation_field_prediction_coordinates(
    p1_series_dir: str | Path,
    output: str | Path,
    *,
    contract_path: str | Path = DEFAULT_CONTRACT,
    registry_path: str | Path = DEFAULT_REGISTRY,
) -> Path:
    return build_coordinate_series(
        p1_series_dir,
        output,
        contract=load_contract(contract_path),
        registry=load_registry(registry_path),
    )


def validate_relation_field_prediction_coordinates(
    p2_series_dir: str | Path,
    p1_series_dir: str | Path,
    *,
    contract_path: str | Path = DEFAULT_CONTRACT,
    registry_path: str | Path = DEFAULT_REGISTRY,
) -> dict[str, Any]:
    return validate_coordinate_series(
        p2_series_dir,
        p1_series_dir,
        contract=load_contract(contract_path),
        registry=load_registry(registry_path),
    )

__all__ = [
    "RelationFieldPredictionCoordinatesP2Error",
    "DEFAULT_CONTRACT",
    "DEFAULT_REGISTRY",
    "load_contract",
    "load_registry",
    "validate_contract",
    "validate_registry",
    "build_relation_field_prediction_coordinates",
    "validate_relation_field_prediction_coordinates",
]
