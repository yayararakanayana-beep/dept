from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from relation_field_grid_rc1 import (  # noqa: E402
    AXIS_NAMES,
    AXIS_STRIDES,
    CELL_COUNT,
    DEGREE_DISTRIBUTION,
    DIRECTED_NEIGHBOR_COUNT,
    GRID_SHAPE,
    UNDIRECTED_EDGE_COUNT,
    RelationFieldGridError,
    apply_incidence,
    build_grid_artifact,
    cell_id_from_indices,
    generate_grid_arrays,
    indices_from_cell_id,
    load_contracts,
    validate_grid_artifact,
)


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_grid_contract_matches_parent_and_fixes_sparse_operator_conventions() -> None:
    grid, parent = load_contracts()

    assert grid["axes"]["order"] == parent["axes"]["order"] == list(AXIS_NAMES)
    assert grid["axes"]["shape"] == parent["axes"]["shape"] == list(GRID_SHAPE)
    assert grid["axes"]["axis_strides"] == list(AXIS_STRIDES)
    assert grid["connectivity"]["undirected_edge_count"] == UNDIRECTED_EDGE_COUNT
    assert grid["connectivity"]["directed_neighbor_count"] == DIRECTED_NEIGHBOR_COUNT
    assert grid["operators"]["adjacency"]["storage"] == "CSR"
    assert grid["operators"]["incidence"]["storage"] == "COO"
    assert grid["operators"]["incidence"]["source_value"] == -1.0
    assert grid["operators"]["incidence"]["target_value"] == 1.0
    assert "dense_adjacency_matrix" in grid["prohibitions"]
    assert "perform_flow_inversion" in grid["prohibitions"]


@pytest.mark.parametrize(
    "indices",
    [
        (0, 0, 0, 0, 0),
        (4, 4, 4, 4, 4),
        (1, 2, 3, 4, 0),
        (4, 0, 2, 1, 3),
    ],
)
def test_cell_id_roundtrip_is_c_order_and_exact(indices: tuple[int, ...]) -> None:
    cell_id = cell_id_from_indices(indices)
    assert indices_from_cell_id(cell_id) == indices
    assert cell_id == int(np.ravel_multi_index(indices, GRID_SHAPE, order="C"))


def test_generated_grid_has_exact_counts_boundaries_and_local_edges() -> None:
    arrays = generate_grid_arrays()

    assert arrays["node_indices"].shape == (CELL_COUNT, 5)
    assert arrays["edge_source"].shape == (UNDIRECTED_EDGE_COUNT,)
    assert arrays["neighbor_indices"].shape == (DIRECTED_NEIGHBOR_COUNT,)
    assert arrays["incidence_rows"].shape == (DIRECTED_NEIGHBOR_COUNT,)
    assert dict(sorted(Counter(int(value) for value in arrays["degree"]).items())) == DEGREE_DISTRIBUTION
    assert int(arrays["neighbor_indptr"][-1]) == DIRECTED_NEIGHBOR_COUNT

    for edge_id in (0, 1, 2499, 2500, 12499):
        source = int(arrays["edge_source"][edge_id])
        target = int(arrays["edge_target"][edge_id])
        axis = int(arrays["edge_axis"][edge_id])
        source_indices = np.asarray(indices_from_cell_id(source))
        target_indices = np.asarray(indices_from_cell_id(target))
        difference = target_indices - source_indices
        assert np.count_nonzero(difference) == 1
        assert int(difference[axis]) == 1
        assert target - source == AXIS_STRIDES[axis]


def test_incidence_moves_mass_from_source_to_target_and_preserves_total() -> None:
    arrays = generate_grid_arrays()
    flow = np.zeros(UNDIRECTED_EDGE_COUNT, dtype=np.float64)
    edge_id = 731
    amount = 0.125
    flow[edge_id] = amount

    delta = apply_incidence(flow, arrays)
    source = int(arrays["edge_source"][edge_id])
    target = int(arrays["edge_target"][edge_id])

    assert delta[source] == pytest.approx(-amount)
    assert delta[target] == pytest.approx(amount)
    assert np.count_nonzero(delta) == 2
    assert float(delta.sum()) == pytest.approx(0.0)


def test_artifact_build_is_deterministic_valid_and_overwrite_protected(tmp_path: Path) -> None:
    first = build_grid_artifact(tmp_path / "grid_a")
    second = build_grid_artifact(tmp_path / "grid_b")

    assert _tree_bytes(first) == _tree_bytes(second)
    validation = validate_grid_artifact(first)
    assert validation["rf2_grid_gate"] == "passed"
    assert validation["cell_count"] == CELL_COUNT
    assert validation["undirected_edge_count"] == UNDIRECTED_EDGE_COUNT
    assert validation["graph_connected"] is True
    assert validation["reads_canonical_gt_kt"] is False
    assert validation["flow_inversion_performed"] is False

    with pytest.raises(RelationFieldGridError, match="already exists"):
        build_grid_artifact(first)


def test_manifest_detects_tampering(tmp_path: Path) -> None:
    artifact = build_grid_artifact(tmp_path / "grid")
    edges = artifact / "edges.csv"
    edges.write_text(edges.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")

    with pytest.raises(RelationFieldGridError, match="manifest"):
        validate_grid_artifact(artifact)


def test_persisted_validation_has_no_prediction_or_flow_claim(tmp_path: Path) -> None:
    artifact = build_grid_artifact(tmp_path / "grid")
    validation = json.loads((artifact / "validation.json").read_text(encoding="utf-8"))

    assert validation["prediction_performed"] is False
    assert validation["flow_inversion_performed"] is False
    assert validation["incidence_orientation"] == "source_minus_one_target_plus_one"
