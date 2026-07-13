"""固定5軸上位観測翻訳層 Task 2。"""
from .canonical import GENESIS_HASH, _compute_gt_hash, _compute_history_chain_hash
from .contracts import (
    AXIS_BINS, AXIS_NAMES, Fixed5AxisHDEPTBridgeError,
    _canonical_json, load_feature_registry,
)
from .builder import build_observation, main

__all__ = [
    "AXIS_BINS", "AXIS_NAMES", "GENESIS_HASH",
    "Fixed5AxisHDEPTBridgeError", "_canonical_json",
    "_compute_gt_hash", "_compute_history_chain_hash",
    "build_observation", "load_feature_registry", "main",
]
