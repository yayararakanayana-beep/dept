from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from relation_field_grid_rc1 import build_grid_artifact  # noqa: E402
from relation_field_temporal_consistency_rc1 import (  # noqa: E402
    _load_grid_with_nodes,
    generate_transition_candidates,
    load_contract,
)


def test_fractional_mass_flow_preserves_rf3_reconstruction_tolerance(tmp_path: Path) -> None:
    grid_path = build_grid_artifact(tmp_path / "grid")
    grid = _load_grid_with_nodes(grid_path)
    contract = load_contract()
    delta = np.zeros(3125, dtype=np.float64)
    delta[0] = -(1.0 / 3.0)
    delta[1] = 1.0 / 3.0

    candidates = generate_transition_candidates(delta, grid, contract)

    assert contract["candidate_generation"]["candidate_signature_decimals"] == 12
    assert candidates
    for candidate in candidates:
        reconstructed_from_stored_flow = np.asarray(
            grid["incidence"] @ candidate["net_flow"], dtype=np.float64
        )
        assert np.max(np.abs(reconstructed_from_stored_flow - candidate["reconstructed"])) < 1e-9
        assert np.max(
            np.abs(delta - reconstructed_from_stored_flow - candidate["residual"])
        ) < 1e-9
