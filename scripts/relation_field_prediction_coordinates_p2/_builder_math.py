from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

import numpy as np

from ._common import RelationFieldPredictionCoordinatesP2Error

@dataclass(frozen=True)
class _I:
    lower: np.ndarray
    center: np.ndarray
    upper: np.ndarray

    def __post_init__(self) -> None:
        lo = np.asarray(self.lower, dtype=np.float64)
        ce = np.asarray(self.center, dtype=np.float64)
        hi = np.asarray(self.upper, dtype=np.float64)
        if lo.shape != ce.shape or ce.shape != hi.shape:
            raise RelationFieldPredictionCoordinatesP2Error("candidate interval shape mismatch")
        if np.any(~np.isfinite(lo)) or np.any(~np.isfinite(ce)) or np.any(~np.isfinite(hi)):
            raise RelationFieldPredictionCoordinatesP2Error("candidate interval contains nonfinite value")
        if np.any(lo > ce + 1e-15) or np.any(ce > hi + 1e-15):
            raise RelationFieldPredictionCoordinatesP2Error("candidate interval is not ordered")
        object.__setattr__(self, "lower", np.ascontiguousarray(lo))
        object.__setattr__(self, "center", np.ascontiguousarray(ce))
        object.__setattr__(self, "upper", np.ascontiguousarray(hi))


def _single(value: Any) -> _I:
    array = np.asarray(value, dtype=np.float64)
    return _I(array, array, array)


def _triplet(lower: Any, center: Any, upper: Any) -> _I:
    lo, ce, hi = np.broadcast_arrays(
        np.asarray(lower, dtype=np.float64),
        np.asarray(center, dtype=np.float64),
        np.asarray(upper, dtype=np.float64),
    )
    return _I(np.minimum.reduce([lo, ce, hi]), ce, np.maximum.reduce([lo, ce, hi]))


def _neg(x: _I) -> _I:
    return _I(-x.upper, -x.center, -x.lower)


def _sub(a: _I, b: _I) -> _I:
    return _I(a.lower - b.upper, a.center - b.center, a.upper - b.lower)


def _mul(a: _I, b: _I) -> _I:
    p = np.stack((a.lower*b.lower, a.lower*b.upper, a.upper*b.lower, a.upper*b.upper))
    return _I(np.min(p, axis=0), a.center*b.center, np.max(p, axis=0))


def _abs(x: _I) -> _I:
    lower = np.where((x.lower <= 0) & (x.upper >= 0), 0.0, np.minimum(np.abs(x.lower), np.abs(x.upper)))
    upper = np.maximum(np.abs(x.lower), np.abs(x.upper))
    return _I(lower, np.abs(x.center), upper)


def _reduce(values: list[np.ndarray], operation: str) -> np.ndarray:
    broadcast = np.broadcast_arrays(*values)
    result = broadcast[0]
    for value in broadcast[1:]:
        result = np.minimum(result, value) if operation == "min" else np.maximum(result, value)
    return result


def _minimum(*xs: _I) -> _I:
    return _I(_reduce([x.lower for x in xs], "min"), _reduce([x.center for x in xs], "min"), _reduce([x.upper for x in xs], "min"))


def _maximum(*xs: _I) -> _I:
    return _I(_reduce([x.lower for x in xs], "max"), _reduce([x.center for x in xs], "max"), _reduce([x.upper for x in xs], "max"))


def _gt(x: _I, boundary: float, scale: float) -> _I:
    scale = max(abs(float(scale)), 1e-12)
    return _I((x.lower-boundary)/scale, (x.center-boundary)/scale, (x.upper-boundary)/scale)


def _lt(x: _I, boundary: float, scale: float) -> _I:
    return _I((boundary-x.upper)/max(abs(float(scale)),1e-12), (boundary-x.center)/max(abs(float(scale)),1e-12), (boundary-x.lower)/max(abs(float(scale)),1e-12))


def _any_axis(x: _I) -> _I:
    if x.center.ndim == 0:
        return x
    axes = tuple(range(x.center.ndim))
    return _I(np.asarray(np.max(x.lower, axis=axes)), np.asarray(np.max(x.center, axis=axes)), np.asarray(np.max(x.upper, axis=axes)))


def _record(entry: Mapping[str, Any], value: _I | None, reason: str | None = None) -> dict[str, Any]:
    base = {
        "coordinate_id": entry["coordinate_id"],
        "coordinate_name_ja": entry["coordinate_name_ja"],
        "coordinate_family": entry["coordinate_family"],
        "coordinate_role": entry["coordinate_role"],
        "registration_status": entry["registration_status"],
        "scope_type": entry["scope_type"],
        "source_feature_ids": list(entry.get("source_feature_ids", [])),
        "dependencies": list(entry.get("dependencies", [])),
        "formula": entry["formula"],
        "unit": entry.get("unit", "source_defined"),
        "normalization_id": entry.get("normalization_id", "source_contract"),
    }
    if value is None:
        return {**base, "availability": "unavailable", "unavailable_reasons": [reason or "missing_source"]}
    width = value.upper-value.lower
    return {
        **base,
        "availability": "available",
        "unavailable_reasons": [],
        "lower": value.lower,
        "center": value.center,
        "upper": value.upper,
        "shape": list(value.center.shape),
        "candidate_width_minimum": float(np.min(width)) if width.size else float(width),
        "candidate_width_mean": float(np.mean(width)) if width.size else float(width),
        "candidate_width_maximum": float(np.max(width)) if width.size else float(width),
        "boundary_status": (
            "confirmed_outside" if np.all(value.upper < 0)
            else "confirmed_inside" if np.all(value.lower > 0)
            else "boundary_ambiguous"
        ) if entry["coordinate_role"] in {"condition_margin", "structure_margin", "modifier"} else None,
    }


def _source(index: Mapping[str, Mapping[str, Any]], arrays: Mapping[str, np.ndarray], key: str) -> np.ndarray | None:
    if key not in arrays or key not in index:
        return None
    value = np.asarray(arrays[key])
    if value.dtype.kind not in "fiu" or value.size == 0 or np.any(~np.isfinite(value)):
        return None
    return np.asarray(value, dtype=np.float64)


def _source_single(ctx: Mapping[str, Any], key: str) -> _I | None:
    value = _source(ctx["index"], ctx["arrays"], key)
    return None if value is None else _single(value)


def _source_triplet(ctx: Mapping[str, Any], keys: Sequence[str]) -> _I | None:
    values = [_source(ctx["index"], ctx["arrays"], key) for key in keys]
    if any(v is None for v in values):
        return None
    return _triplet(values[0], values[1], values[2])

