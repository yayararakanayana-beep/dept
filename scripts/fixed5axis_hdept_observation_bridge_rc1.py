"""固定5軸 G_t/K_t から H11_STRUCTURED M_t を作る Task 2 builder。"""
from fixed5axis_hdept_bridge_task2 import (
    AXIS_BINS, AXIS_NAMES, GENESIS_HASH, Fixed5AxisHDEPTBridgeError,
    _canonical_json, _compute_gt_hash, _compute_history_chain_hash,
    build_observation, load_feature_registry, main,
)

__all__ = [
    "AXIS_BINS", "AXIS_NAMES", "GENESIS_HASH",
    "Fixed5AxisHDEPTBridgeError", "_canonical_json",
    "_compute_gt_hash", "_compute_history_chain_hash",
    "build_observation", "load_feature_registry", "main",
]

if __name__ == "__main__":
    raise SystemExit(main())
