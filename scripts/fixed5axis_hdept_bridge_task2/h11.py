"""H11射影の安定した差し替え境界。

現在の既定値は旧RC1射影を呼ぶだけであり、出力値は変更しない。
新しい初期実装は別モジュールとして追加し、この境界から明示的に選択する。
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from .contracts import Fixed5AxisHDEPTBridgeError
from .h11_legacy_rc1 import construct_h11_legacy_rc1

LEGACY_RC1_PROJECTION_ID = "legacy_rc1_positive_negative_mean_sigmoid"
DEFAULT_H11_PROJECTION_ID = LEGACY_RC1_PROJECTION_ID
SUPPORTED_H11_PROJECTION_IDS = frozenset({LEGACY_RC1_PROJECTION_ID})


def construct_h11(
    records: Sequence[Mapping[str, Any]],
    registry: Mapping[str, Any],
    evidence_map: Mapping[str, Any],
    calibration: Mapping[str, Any] | None,
    history_frame_count: int,
    *,
    projection_id: str = DEFAULT_H11_PROJECTION_ID,
) -> tuple[dict[str, Any], str]:
    """選択されたH11射影を呼ぶ。

    Task 2〜4との後方互換のため、引数を追加しない既存呼出しは旧RC1方式へ
    委譲する。未知の方式を暗黙にフォールバックさせない。
    """
    if projection_id == LEGACY_RC1_PROJECTION_ID:
        return construct_h11_legacy_rc1(
            records,
            registry,
            evidence_map,
            calibration,
            history_frame_count,
        )
    raise Fixed5AxisHDEPTBridgeError(f"unsupported H11 projection_id: {projection_id}")
