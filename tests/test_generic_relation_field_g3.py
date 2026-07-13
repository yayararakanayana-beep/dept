from __future__ import annotations

import csv
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

from generic_relation_field_g2 import (  # noqa: E402
    GenericRelationFieldG2Error,
    _json_dump,
    _load_npz,
    _write_deterministic_npz,
    _write_manifest,
    build_fixed5_structure_artifact,
    load_contract as load_g2_contract,
    validate_contract as validate_g2_contract,
    validate_structure_artifact,
)
from generic_relation_field_g3 import (  # noqa: E402
    GenericRelationFieldG3Error,
    build_scientific_compatibility_artifact,
    load_contract,
    load_validation_profile,
    run_negative_guard_audit,
    run_synthetic_structure_audit,
    validate_capability_claim,
    validate_mass_transition,
    validate_no_future_feature_keys,
    validate_prediction_alignment_record,
    validate_probability_claim,
    validate_scientific_compatibility_artifact,
    validate_simulator_output,
    validate_validation_profile,
)
from relation_field_axis_coupling_innovation_rc1 import build_axis_coupling_innovation  # noqa: E402
from relation_field_grid_rc1 import build_grid_artifact, cell_id_from_indices  # noqa: E402
from relation_field_hodge_decomposition_rc1 import build_hodge_decomposition  # noqa: E402
from relation_field_predictive_validation_rc1 import build_predictive_validation  # noqa: E402
from relation_field_risk_structure_rc1 import build_risk_structure  # noqa: E402
from relation_field_shape_dynamics_rc1 import build_shape_dynamics  # noqa: E402
from relation_field_single_transition_audit_rc1 import build_audit_artifact  # noqa: E402
from relation_field_single_transition_rc1 import (  # noqa: E402
    GENESIS_HASH,
    _compute_gt_hash,
    _compute_history_chain_hash,
    build_transition_field,
)
from relation_field_temporal_consistency_rc1 import build_temporal_relation_field  # noqa: E402


LEDGER_FIELDS = [
    "trajectory_id",
    "source_trajectory_id",
    "t",
    "phase",
    "gt_row_index",
    "gt_hash",
    "previous_gt_hash",
    "history_chain_hash",
    "delta_t",
    "continuity_status",
    "admissible_for_research",
    "source_state_ref",
    "source_state_hash",
]


def _point(indices: tuple[int, int, int, int, int]) -> np.ndarray:
    flat = np.zeros(3125, dtype=np.float64)
    flat[cell_id_from_indices(indices)] = 1.0
    return flat.reshape((5, 5, 5, 5, 5))


def _mixture(items: list[tuple[tuple[int, int, int, int, int], float]]) -> np.ndarray:
    flat = np.zeros(3125, dtype=np.float64)
    for indices, mass in items:
        flat[cell_id_from_indices(indices)] += float(mass)
    assert np.isclose(flat.sum(), 1.0)
    return flat.reshape((5, 5, 5, 5, 5))


def _write_trajectory(root: Path, frames: list[np.ndarray], *, trajectory_id: str) -> Path:
    root.mkdir(parents=True)
    np.save(root / "gt_mass.npy", np.stack(frames), allow_pickle=False)
    rows: list[dict[str, object]] = []
    previous_gt_hash = ""
    history_chain_hash = GENESIS_HASH
    for t, frame in enumerate(frames):
        digest = hashlib.sha256(np.ascontiguousarray(frame).tobytes()).hexdigest()
        source_state_hash = hashlib.sha256(f"g3-source-{t}-{digest}".encode()).hexdigest()
        gt_hash = _compute_gt_hash(
            trajectory_id=trajectory_id,
            t=t,
            distribution=frame,
            source_state_hash=source_state_hash,
        )
        history_chain_hash = _compute_history_chain_hash(history_chain_hash, gt_hash, t)
        rows.append(
            {
                "trajectory_id": trajectory_id,
                "source_trajectory_id": trajectory_id,
                "t": t,
                "phase": "pre_transition",
                "gt_row_index": t,
                "gt_hash": gt_hash,
                "previous_gt_hash": previous_gt_hash,
                "history_chain_hash": history_chain_hash,
                "delta_t": 0 if t == 0 else 1,
                "continuity_status": "initial" if t == 0 else "continuous",
                "admissible_for_research": True,
                "source_state_ref": f"states/step_{t:06d}.npz",
                "source_state_hash": source_state_hash,
            }
        )
        previous_gt_hash = gt_hash
    with (root / "history_ledger.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEDGER_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return root


def _write_case_manifest(path: Path, cases: list[dict[str, str]]) -> Path:
    path.write_text(
        json.dumps(
            {"manifest_version": "relation_field_predictive_validation_case_manifest_rc1", "cases": cases},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


@pytest.fixture(scope="module")
def g3_fixture(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    root = tmp_path_factory.mktemp("generic-relation-field-g3")
    prefix = [
        _point((0, 2, 2, 2, 2)),
        _point((1, 2, 2, 2, 2)),
        _point((2, 2, 2, 2, 2)),
        _point((3, 2, 2, 2, 2)),
        _point((3, 3, 2, 2, 2)),
    ]
    neutral_future = [
        _point((2, 3, 2, 2, 2)),
        _point((2, 2, 2, 2, 2)),
        _point((3, 2, 2, 2, 2)),
        _point((3, 3, 2, 2, 2)),
    ]
    divergent_future = [
        _mixture([((3, 3, 2, 2, 2), 0.5), ((2, 3, 2, 2, 2), 0.5)]),
        _mixture(
            [
                ((3, 3, 2, 2, 2), 0.25),
                ((2, 3, 2, 2, 2), 0.25),
                ((3, 2, 2, 2, 2), 0.25),
                ((2, 2, 2, 2, 2), 0.25),
            ]
        ),
        _mixture([((a, b, c, 2, 2), 0.125) for a in (2, 3) for b in (2, 3) for c in (1, 2)]),
        _mixture(
            [
                ((a, b, c, d, 2), 0.0625)
                for a in (2, 3)
                for b in (2, 3)
                for c in (1, 2)
                for d in (1, 2)
            ]
        ),
    ]
    trajectory_neutral = _write_trajectory(
        root / "trajectory_neutral", prefix + neutral_future, trajectory_id="traj_g3_shared_prefix"
    )
    trajectory_divergent = _write_trajectory(
        root / "trajectory_divergent", prefix + divergent_future, trajectory_id="traj_g3_shared_prefix"
    )
    grid = build_grid_artifact(root / "grid")
    structure = build_fixed5_structure_artifact(grid, root / "g2_structure")
    rf3 = build_transition_field(trajectory_neutral, grid, root / "rf3", from_t=0, to_t=1)
    rf4 = build_audit_artifact(grid, root / "rf4")
    rf5 = build_temporal_relation_field(trajectory_neutral, grid, root / "rf5", start_t=0, to_t=4)
    rf6 = build_hodge_decomposition(rf5, grid, root / "rf6")
    rf7 = build_shape_dynamics(trajectory_neutral, rf5, rf6, grid, root / "rf7")
    rf8 = build_axis_coupling_innovation(trajectory_neutral, grid, rf5, rf6, rf7, root / "rf8")
    rf9 = build_risk_structure(trajectory_neutral, grid, rf5, rf6, rf7, rf8, root / "rf9")
    case_manifest = _write_case_manifest(
        root / "cases.json",
        [
            {
                "case_id": "neutral_suffix",
                "partition": "development",
                "trajectory_dir": str(trajectory_neutral),
                "grid_artifact_dir": str(grid),
                "rf5_artifact_dir": str(rf5),
                "rf6_artifact_dir": str(rf6),
                "rf7_artifact_dir": str(rf7),
                "rf8_artifact_dir": str(rf8),
                "rf9_artifact_dir": str(rf9),
            },
            {
                "case_id": "divergent_suffix",
                "partition": "development",
                "trajectory_dir": str(trajectory_divergent),
                "grid_artifact_dir": str(grid),
                "rf5_artifact_dir": str(rf5),
                "rf6_artifact_dir": str(rf6),
                "rf7_artifact_dir": str(rf7),
                "rf8_artifact_dir": str(rf8),
                "rf9_artifact_dir": str(rf9),
            },
        ],
    )
    rf10 = build_predictive_validation(case_manifest, root / "rf10")
    sources = {
        "grid": grid,
        "trajectory": trajectory_neutral,
        "rf3": rf3,
        "rf4": rf4,
        "rf5": rf5,
        "rf6": rf6,
        "rf7": rf7,
        "rf8": rf8,
        "rf9": rf9,
        "rf10": rf10,
        "rf10_case_manifest": case_manifest,
    }
    source_hashes = {key: hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else _tree_hashes(path) for key, path in sources.items()}
    first = build_scientific_compatibility_artifact(structure, sources, root / "g3_first")
    second = build_scientific_compatibility_artifact(structure, sources, root / "g3_second")
    assert source_hashes == {
        key: hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else _tree_hashes(path)
        for key, path in sources.items()
    }
    return {
        "root": root,
        "structure": structure,
        "sources": sources,
        "first": first,
        "second": second,
    }


def test_contract_separates_compatibility_from_prediction_and_fixed_values() -> None:
    contract = load_contract()
    profile = load_validation_profile()

    assert contract["scope"]["fixed5_scientific_compatibility"] is True
    assert contract["scope"]["generic_rf_kernel_reimplementation"] is False
    assert contract["scope"]["prediction_model_implementation"] is False
    assert contract["acceptance"]["prediction_accuracy_claim"] == "not_evaluated"
    assert set(profile["source_contracts"]) == {f"RF-{index}" for index in range(3, 11)}

    generic_text = (ROOT / "scripts" / "generic_relation_field_g3.py").read_text(encoding="utf-8")
    contract_text = (ROOT / "configs" / "generic_relation_field_g3_contract.json").read_text(encoding="utf-8")
    for fixed_value in ("3125", "12500", "20000"):
        assert fixed_value not in generic_text
        assert fixed_value not in contract_text

    escaped_profile = deepcopy(profile)
    escaped_profile["numeric_payloads"][0]["path"] = "../outside.npz"
    with pytest.raises(GenericRelationFieldG3Error, match="repository-safe relative path"):
        validate_validation_profile(escaped_profile)


def test_synthetic_structure_matrix_covers_all_required_variations() -> None:
    result = run_synthetic_structure_audit(load_validation_profile())
    rows = {row["case_id"]: row for row in result["cases"]}

    assert result["all_synthetic_structure_cases_pass"] is True
    assert rows["three_axis_unequal_bins"]["axis_count"] == 3
    assert rows["seven_axis_binary"]["axis_count"] == 7
    assert rows["multiple_connected_components"]["connected_component_count"] == 2
    assert rows["face_free_cycle"]["face_count"] == 0
    assert rows["face_free_cycle"]["first_betti_number"] == 1
    assert rows["face_complex_with_hole"]["face_count"] > 0
    assert rows["face_complex_with_hole"]["first_betti_number"] == 1
    assert rows["coordinate_free_path"]["coordinates_available"] is False
    assert rows["identifier_order_permutation"]["canonical_structure_signature"] == rows["irregular_connected"][
        "canonical_structure_signature"
    ]
    assert result["prediction_accuracy_evaluated"] is False


def test_negative_guards_reject_shortcuts() -> None:
    profile = load_validation_profile()
    audit = run_negative_guard_audit(profile)
    assert audit["all_executed_g3_guards_closed"] is True
    assert audit["all_required_negative_guard_coverage_declared"] is True
    assert audit["executed_g3_guard_count"] == 7
    assert audit["inherited_g2_required_guard_count"] == 3

    dynamic_inside_kt = deepcopy(load_g2_contract())
    dynamic_inside_kt["production_scope"]["topology_is_static_within_kt"] = False
    with pytest.raises(GenericRelationFieldG2Error, match="static within"):
        validate_g2_contract(dynamic_inside_kt, require_source_files=False)

    with pytest.raises(GenericRelationFieldG3Error, match="without faces"):
        validate_capability_claim(
            {"faces": False, "coordinates": False},
            {"claim_type": "harmonic_component", "availability_status": "valid", "value": [0.0]},
        )
    with pytest.raises(GenericRelationFieldG3Error, match="without coordinates"):
        validate_capability_claim(
            {"faces": False, "coordinates": False},
            {"claim_type": "axis_direction", "availability_status": "valid", "direction_scope_ids": ["axis/x"]},
        )
    with pytest.raises(GenericRelationFieldG3Error, match="repair is forbidden"):
        validate_mass_transition([1.1, -0.1], [1.0, 0.0], tolerance=1e-10)
    with pytest.raises(GenericRelationFieldG3Error, match="cannot be averaged"):
        validate_prediction_alignment_record(
            {"alignment_status": "conflicting", "summary": {"mean_prediction": 0.5}}, profile
        )
    with pytest.raises(GenericRelationFieldG3Error, match="not independently calibrated"):
        validate_probability_claim(
            {"value_type": "probability", "calibration_status": "uncalibrated", "support_count": 100}, profile
        )
    with pytest.raises(GenericRelationFieldG3Error, match="action-evaluation"):
        validate_simulator_output({"recommended_action": "x"}, profile)
    with pytest.raises(GenericRelationFieldG3Error, match="future information"):
        validate_no_future_feature_keys({"features": {"future_input": 1.0}}, profile)


def test_full_rf3_through_rf10_compatibility_is_deterministic_and_valid(g3_fixture: dict[str, object]) -> None:
    first = g3_fixture["first"]
    second = g3_fixture["second"]
    assert isinstance(first, Path) and isinstance(second, Path)
    assert _tree_hashes(first) == _tree_hashes(second)

    validation = validate_scientific_compatibility_artifact(
        first,
        g3_fixture["structure"],
        g3_fixture["sources"],
    )
    assert validation["g3_scientific_compatibility_gate"] == "passed"
    assert validation["required_stage_count"] == 8
    assert validation["legacy_stage_validator_count"] == 8
    assert validation["numeric_payload_count"] > 0
    assert validation["numeric_array_count"] > validation["numeric_payload_count"]
    assert validation["semantic_payload_count"] > 0
    assert validation["all_scientific_invariants_pass"] is True
    assert validation["all_executed_g3_guards_closed"] is True
    assert validation["all_required_negative_guard_coverage_declared"] is True
    assert validation["inherited_g2_guards_executed_by_this_artifact"] is False
    assert validation["source_artifacts_unchanged"] is True
    assert validation["prediction_model_implemented"] is False
    assert validation["prediction_accuracy_evaluated"] is False
    assert validation["action_selection_performed"] is False
    identity = json.loads((first / "identity.json").read_text(encoding="utf-8"))
    assert set(identity["source_contract_hashes"]) == {f"RF-{index}" for index in range(3, 11)}
    profile = load_validation_profile()
    assert len(identity["declared_source_identity_hashes"]) == sum(
        len(paths) for paths in profile["source_identity_files"].values()
    )


def test_dense_legacy_arrays_are_reordered_by_identity_not_position(g3_fixture: dict[str, object]) -> None:
    artifact = g3_fixture["first"]
    structure = g3_fixture["structure"]
    sources = g3_fixture["sources"]
    assert isinstance(artifact, Path) and isinstance(structure, Path) and isinstance(sources, dict)
    registry = json.loads((artifact / "registry_index.json").read_text(encoding="utf-8"))
    source_edge_ids = registry["registries"]["edge"]["source_order_ids"]
    canonical_edge_ids = registry["registries"]["edge"]["canonical_order_ids"]
    assert source_edge_ids != canonical_edge_ids

    field = next((sources["rf3"] / "trajectories").glob("*/fields/t_*"))
    legacy = _load_npz(field / "local_flow.npz")["net_flow"]
    generic = _load_npz(artifact / "numeric_payloads.npz")["rf3_local_flow__net_flow"]
    legacy_by_id = dict(zip(source_edge_ids, legacy.tolist(), strict=True))
    expected = np.asarray([legacy_by_id[identity] for identity in canonical_edge_ids], dtype=np.float64)
    assert np.array_equal(generic, expected)


def test_independent_validator_rejects_numeric_tampering_even_with_fresh_manifest(
    g3_fixture: dict[str, object], tmp_path: Path
) -> None:
    source = g3_fixture["first"]
    assert isinstance(source, Path)
    tampered = tmp_path / "tampered_g3"
    shutil.copytree(source, tampered)
    arrays = _load_npz(tampered / "numeric_payloads.npz")
    arrays["rf3_local_flow__observed_delta"] = arrays["rf3_local_flow__observed_delta"].copy()
    arrays["rf3_local_flow__observed_delta"][0] += 0.125
    _write_deterministic_npz(tampered / "numeric_payloads.npz", arrays)
    (tampered / "manifest.json").unlink()
    _write_manifest(tampered, "generic_relation_field_g3_scientific_compatibility")

    with pytest.raises(GenericRelationFieldG3Error, match="numeric payload mismatch"):
        validate_scientific_compatibility_artifact(
            tampered,
            g3_fixture["structure"],
            g3_fixture["sources"],
        )


def test_independent_validator_rejects_profile_tampering_even_with_fresh_manifest(
    g3_fixture: dict[str, object], tmp_path: Path
) -> None:
    source = g3_fixture["first"]
    assert isinstance(source, Path)
    tampered = tmp_path / "tampered_g3_profile"
    shutil.copytree(source, tampered)
    profile = json.loads((tampered / "validation_profile.json").read_text(encoding="utf-8"))
    profile["negative_guard_profile"]["future_forbidden_key_fragments"].append("forged_future_key")
    _json_dump(tampered / "validation_profile.json", profile)
    (tampered / "manifest.json").unlink()
    _write_manifest(tampered, "generic_relation_field_g3_scientific_compatibility")

    with pytest.raises(GenericRelationFieldG3Error, match="canonical profile"):
        validate_scientific_compatibility_artifact(
            tampered,
            g3_fixture["structure"],
            g3_fixture["sources"],
        )


def test_structure_hash_tampering_is_rejected_before_scientific_comparison(
    g3_fixture: dict[str, object], tmp_path: Path
) -> None:
    structure = g3_fixture["structure"]
    assert isinstance(structure, Path)
    tampered = tmp_path / "tampered_structure"
    shutil.copytree(structure, tampered)
    profile = json.loads((tampered / "structure_profile.json").read_text(encoding="utf-8"))
    profile["structure_hash"] = "0" * 64
    _json_dump(tampered / "structure_profile.json", profile)
    (tampered / "manifest.json").unlink()
    _write_manifest(tampered, "generic_relation_structure_g2")

    with pytest.raises(GenericRelationFieldG2Error, match="structure hash mismatch"):
        validate_structure_artifact(tampered)
