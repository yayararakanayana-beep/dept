from __future__ import annotations

import hashlib
import json
import shutil
import sys
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from fixed5axis_gk_rc1 import build_trajectory, load_contract as load_gk_contract  # noqa: E402
from generic_relation_field_g2 import (  # noqa: E402
    GenericRelationFieldG2Error,
    build_field_records_artifact,
    build_fixed5_history_view,
    build_fixed5_structure_artifact,
    load_contract,
    load_fixed_profile,
    validate_contract,
    validate_field_records_artifact,
    validate_fixed_profile,
    validate_history_view,
    validate_structure_artifact,
    validate_structure_payload,
)
from relation_field_grid_rc1 import build_grid_artifact  # noqa: E402


def _json_dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _tree_hash(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _distribution(step: int) -> np.ndarray:
    indices = np.indices((5, 5, 5, 5, 5)).sum(axis=0).astype(np.float64)
    mass = np.exp(-((indices - (8.0 + 0.2 * step)) ** 2) / 4.0)
    mass += (step + 1) * 1e-7
    mass /= mass.sum()
    return mass


def _make_source_trajectory(root: Path, frames: int = 4) -> Path:
    trajectory = root / "source_trajectory"
    (trajectory / "states").mkdir(parents=True)
    _json_dump(
        trajectory / "metadata.json",
        {
            "trajectory_id": "g2_test_trajectory",
            "scenario_id": "g2_test_scenario",
            "seed": 7,
            "initial_state_id": "g2_test_initial",
            "world_module": "tests.synthetic",
            "world_class": "SyntheticFixed5World",
            "world_version": "test",
            "config_version": "g2",
            "total_steps": frames - 1,
            "dataset_split": "fit",
        },
    )
    steps: list[dict[str, object]] = []
    for step in range(frames):
        state_ref = f"states/step_{step:06d}.npz"
        np.savez_compressed(trajectory / state_ref, distribution=_distribution(step))
        steps.append(
            {
                "trajectory_id": "g2_test_trajectory",
                "step": step,
                "phase": "pre_transition",
                "state_ref": state_ref,
                "observed_external_input": {"test_input": float(step)},
                "observed_action": None,
                "observed_events": [],
            }
        )
    _write_jsonl(trajectory / "steps.jsonl", steps)
    _write_jsonl(trajectory / "truth.jsonl", [{"future_outcome": "must_not_be_read"}])
    _json_dump(trajectory / "summary.json", {"future_outcome": "must_not_be_read"})
    _write_jsonl(trajectory / "metrics.jsonl", [{"future_metric": 999.0}])
    return trajectory


@pytest.fixture(scope="module")
def structure_fixture(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    root = tmp_path_factory.mktemp("g2_structure")
    grid = build_grid_artifact(root / "legacy_grid")
    first = build_fixed5_structure_artifact(grid, root / "structure_a")
    second = build_fixed5_structure_artifact(grid, root / "structure_b")
    return {"root": root, "grid": grid, "first": first, "second": second}


def test_generic_contract_contains_no_fixed_topology_values_and_profile_owns_them() -> None:
    generic_text = (ROOT / "configs" / "generic_relation_field_g2_contract.json").read_text(
        encoding="utf-8"
    )
    fixed = load_fixed_profile()
    fixed_mapping_text = (
        ROOT / "configs" / "fixed5axis_relation_structure_g2.json"
    ).read_text(encoding="utf-8")
    contract = load_contract()

    for forbidden in (
        "3125",
        "12500",
        "20000",
        "resource_slack",
        "information_quality",
        "exploration_room",
        "reversibility",
    ):
        assert forbidden not in generic_text
    for duplicated in ("3125", "12500", "20000", "[5, 5, 5, 5, 5]"):
        assert duplicated not in fixed_mapping_text
    assert fixed["expected_counts"]["cell_count"] == 3125
    assert fixed["expected_counts"]["edge_count"] == 12500
    assert fixed["expected_counts"]["face_count"] == 20000
    assert contract["production_scope"]["dynamic_topology_correspondence_implemented"] is False
    assert contract["production_scope"]["prediction_model_implemented"] is False


def test_contract_validators_reject_false_capability_claims() -> None:
    contract = load_contract()
    broken_contract = deepcopy(contract)
    broken_contract["production_scope"]["prediction_model_implemented"] = True
    with pytest.raises(GenericRelationFieldG2Error, match="prediction model"):
        validate_contract(broken_contract, require_source_files=False)

    fixed_mapping = json.loads(
        (ROOT / "configs" / "fixed5axis_relation_structure_g2.json").read_text(
            encoding="utf-8"
        )
    )
    fixed_mapping["capabilities"]["dynamic_topology_correspondence"] = True
    with pytest.raises(GenericRelationFieldG2Error, match="topology correspondence"):
        validate_fixed_profile(fixed_mapping)


def test_fixed5_adapter_is_deterministic_and_exactly_compatible(
    structure_fixture: dict[str, Path],
) -> None:
    first = structure_fixture["first"]
    second = structure_fixture["second"]

    assert _tree_bytes(first) == _tree_bytes(second)
    validation = validate_structure_artifact(first)
    profile = json.loads((first / "structure_profile.json").read_text(encoding="utf-8"))
    with np.load(first / "cell_registry.npz", allow_pickle=False) as cells:
        assert cells["cell_ids"][[0, -1]].tolist() == ["cell/0", "cell/3124"]
    with np.load(first / "edge_registry.npz", allow_pickle=False) as edges:
        assert edges["edge_ids"][[0, -1]].tolist() == ["edge/0", "edge/12499"]
        assert np.all(edges["transport_cost"] == 0.25)
    with np.load(first / "face_registry.npz", allow_pickle=False) as faces:
        assert faces["face_ids"][[0, -1]].tolist() == ["face/0", "face/19999"]

    assert validation["g2_structure_gate"] == "passed"
    assert validation["axis_count"] == 5
    assert validation["cell_count"] == 3125
    assert validation["edge_count"] == 12500
    assert validation["face_count"] == 20000
    assert validation["face_edge_membership_count"] == 80000
    assert validation["connected_component_count"] == 1
    assert validation["legacy_rf2_identity_exact"] is True
    assert validation["legacy_rf2_incidence_exact"] is True
    assert validation["legacy_rf3_edge_cost_exact"] is True
    assert validation["legacy_rf6_faces_exact"] is True
    assert validation["boundary_of_boundary"] == "exact_zero"
    assert profile["prediction_performed"] is False
    assert profile["canonical_gk_read"] is False
    assert profile["canonical_writeback_performed"] is False
    assert len(profile["source_contract_hashes"]) == 11


def test_generic_structure_validator_does_not_require_five_axes() -> None:
    cell_arrays = {
        "cell_ids": np.asarray(["node-a", "node-b", "node-c"]),
        "legacy_cell_id": np.asarray([10, 20, 30], dtype=np.int64),
        "axis_bin_indices": np.empty((3, 0), dtype=np.int32),
        "coordinate_values": np.empty((3, 0), dtype=np.float64),
    }
    edge_arrays = {
        "edge_ids": np.asarray(["link-alpha", "link-beta"]),
        "legacy_edge_id": np.asarray([8, 9], dtype=np.int64),
        "source_cell_ordinal": np.asarray([0, 1], dtype=np.int64),
        "target_cell_ordinal": np.asarray([1, 2], dtype=np.int64),
        "axis_ordinal": np.asarray([-1, -1], dtype=np.int32),
        "topological_length": np.ones(2),
        "coordinate_length": np.ones(2),
        "transport_cost": np.ones(2),
        "incidence_rows": np.asarray([0, 1, 1, 2], dtype=np.int64),
        "incidence_cols": np.asarray([0, 0, 1, 1], dtype=np.int64),
        "incidence_data": np.asarray([-1.0, 1.0, -1.0, 1.0]),
        "incidence_shape": np.asarray([3, 2], dtype=np.int64),
    }
    face_arrays = {
        "face_ids": np.empty(0, dtype="U1"),
        "legacy_face_id": np.empty(0, dtype=np.int64),
        "base_cell_ordinal": np.empty(0, dtype=np.int64),
        "axis_a_ordinal": np.empty(0, dtype=np.int32),
        "axis_b_ordinal": np.empty(0, dtype=np.int32),
        "face_indptr": np.asarray([0], dtype=np.int64),
        "edge_ordinals": np.empty(0, dtype=np.int64),
        "edge_signs": np.empty(0, dtype=np.int8),
    }
    boundary_arrays = {
        "boundary_indptr": np.asarray([0], dtype=np.int64),
        "cell_ordinals": np.empty(0, dtype=np.int64),
    }

    validation = validate_structure_payload(
        {}, cell_arrays, edge_arrays, face_arrays, boundary_arrays
    )

    assert validation["axis_count"] == 0
    assert validation["cell_count"] == 3
    assert validation["edge_count"] == 2
    assert validation["face_count"] == 0
    assert validation["connected_component_count"] == 1


def test_structure_validator_rejects_wrong_incidence_signs() -> None:
    cell_arrays = {
        "cell_ids": np.asarray(["left", "right"]),
        "legacy_cell_id": np.asarray([0, 1]),
        "axis_bin_indices": np.empty((2, 0), dtype=np.int32),
        "coordinate_values": np.empty((2, 0), dtype=np.float64),
    }
    edge_arrays = {
        "edge_ids": np.asarray(["wrong-way-link"]),
        "legacy_edge_id": np.asarray([0]),
        "source_cell_ordinal": np.asarray([0]),
        "target_cell_ordinal": np.asarray([1]),
        "axis_ordinal": np.asarray([-1]),
        "topological_length": np.ones(1),
        "coordinate_length": np.ones(1),
        "transport_cost": np.ones(1),
        "incidence_rows": np.asarray([0, 1]),
        "incidence_cols": np.asarray([0, 0]),
        "incidence_data": np.asarray([1.0, -1.0]),
        "incidence_shape": np.asarray([2, 1]),
    }
    face_arrays = {
        "face_ids": np.empty(0, dtype="U1"),
        "legacy_face_id": np.empty(0, dtype=np.int64),
        "base_cell_ordinal": np.empty(0, dtype=np.int64),
        "axis_a_ordinal": np.empty(0, dtype=np.int32),
        "axis_b_ordinal": np.empty(0, dtype=np.int32),
        "face_indptr": np.asarray([0], dtype=np.int64),
        "edge_ordinals": np.empty(0, dtype=np.int64),
        "edge_signs": np.empty(0, dtype=np.int8),
    }
    boundary_arrays = {
        "boundary_indptr": np.asarray([0]),
        "cell_ordinals": np.empty(0, dtype=np.int64),
    }

    with pytest.raises(GenericRelationFieldG2Error, match="incidence signs"):
        validate_structure_payload({}, cell_arrays, edge_arrays, face_arrays, boundary_arrays)


def test_structure_manifest_rejects_tampering(
    structure_fixture: dict[str, Path], tmp_path: Path
) -> None:
    copy = tmp_path / "structure"
    shutil.copytree(structure_fixture["first"], copy)
    profile = copy / "structure_profile.json"
    profile.write_text(profile.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(GenericRelationFieldG2Error, match="manifest"):
        validate_structure_artifact(copy)


def test_causal_history_view_is_keyed_prefix_only_and_no_writeback(
    structure_fixture: dict[str, Path], tmp_path: Path
) -> None:
    source = _make_source_trajectory(tmp_path / "source", frames=4)
    canonical = build_trajectory(source, tmp_path / "gk", load_gk_contract())
    before = _tree_hash(canonical)

    view = build_fixed5_history_view(
        canonical,
        structure_fixture["first"],
        tmp_path / "history_view",
        to_t=1,
    )
    after = _tree_hash(canonical)

    assert before == after
    validation = validate_history_view(view, structure_fixture["first"])
    identity = json.loads((view / "identity.json").read_text(encoding="utf-8"))
    with np.load(view / "mass_records.npz", allow_pickle=False) as arrays:
        assert arrays["frame_offsets"].tolist() == [0, 3125, 6250]
        assert arrays["cell_ordinals"].shape == (6250,)
        assert arrays["mass_values"].shape == (6250,)
    assert validation["g2_history_view_gate"] == "passed"
    assert identity["history_end_t"] == 1
    assert identity["frame_count"] == 2
    assert identity["source_future_mass_values_read"] is False
    assert identity["source_future_ledger_rows_parsed"] is False
    assert identity["source_truth_read"] is False
    assert identity["canonical_writeback_performed"] is False

    with pytest.raises(GenericRelationFieldG2Error, match="prediction time is absent"):
        build_fixed5_history_view(
            canonical,
            structure_fixture["first"],
            tmp_path / "missing_time_view",
            to_t=99,
        )


def test_history_view_rejects_structure_provenance_mismatch(
    structure_fixture: dict[str, Path], tmp_path: Path
) -> None:
    source = _make_source_trajectory(tmp_path / "source", frames=2)
    canonical = build_trajectory(source, tmp_path / "gk", load_gk_contract())
    provenance_path = canonical / "provenance.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
    provenance["axis_order"] = list(reversed(provenance["axis_order"]))
    _json_dump(provenance_path, provenance)

    with pytest.raises(GenericRelationFieldG2Error, match="provenance"):
        build_fixed5_history_view(
            canonical,
            structure_fixture["first"],
            tmp_path / "history_view",
            to_t=1,
        )


def _field_records() -> list[dict[str, object]]:
    return [
        {
            "record_id": "axis-flow/resource_slack",
            "feature_id": "axis_flow",
            "feature_group": "flow",
            "scope_type": "axis",
            "scope_ids": ["resource_slack"],
            "value": 0.25,
            "lower_bound": 0.20,
            "upper_bound": 0.30,
            "unit": "mass_per_step",
            "normalization_id": "none",
            "availability_status": "valid",
            "evidence_status": "inferred_candidate",
            "source_refs": ["rf5/candidate/0"],
        },
        {
            "record_id": "global/unresolved",
            "feature_id": "unresolved_residual",
            "feature_group": "uncertainty",
            "scope_type": "global",
            "scope_ids": [],
            "value": 0.01,
            "lower_bound": 0.0,
            "upper_bound": 0.02,
            "unit": "mass",
            "normalization_id": "unit_mass",
            "availability_status": "limited",
            "evidence_status": "observed",
            "source_refs": ["rf8/residual"],
        },
    ]


def test_keyed_field_records_are_deterministic_and_scope_checked(
    structure_fixture: dict[str, Path], tmp_path: Path
) -> None:
    causal_hash = "a" * 64
    first = build_field_records_artifact(
        structure_fixture["first"],
        tmp_path / "field_a",
        stage="coupling_drive",
        records=list(reversed(_field_records())),
        causal_prefix_hash=causal_hash,
        source_refs=["rf8/example"],
    )
    second = build_field_records_artifact(
        structure_fixture["first"],
        tmp_path / "field_b",
        stage="coupling_drive",
        records=_field_records(),
        causal_prefix_hash=causal_hash,
        source_refs=["rf8/example"],
    )

    assert _tree_bytes(first) == _tree_bytes(second)
    validation = validate_field_records_artifact(first, structure_fixture["first"])
    identity = json.loads((first / "identity.json").read_text(encoding="utf-8"))
    assert validation["g2_field_records_gate"] == "passed"
    assert validation["record_count"] == 2
    assert identity["fixed_length_primary_storage"] is False
    assert identity["prediction_performed"] is False
    assert identity["action_selection_performed"] is False

    invalid = _field_records()
    invalid[0] = {**invalid[0], "scope_ids": ["unknown_axis"]}
    with pytest.raises(GenericRelationFieldG2Error, match="unknown scope"):
        build_field_records_artifact(
            structure_fixture["first"],
            tmp_path / "field_invalid",
            stage="coupling_drive",
            records=invalid,
            causal_prefix_hash=causal_hash,
            source_refs=[],
        )


def test_field_records_reject_forecast_evidence_in_observation_foundation(
    structure_fixture: dict[str, Path], tmp_path: Path
) -> None:
    invalid = _field_records()
    invalid[0] = {**invalid[0], "evidence_status": "forecast"}

    with pytest.raises(GenericRelationFieldG2Error, match="evidence status"):
        build_field_records_artifact(
            structure_fixture["first"],
            tmp_path / "field_invalid",
            stage="risk_evidence",
            records=invalid,
            causal_prefix_hash="b" * 64,
            source_refs=[],
        )
