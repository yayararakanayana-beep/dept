from __future__ import annotations

import ast
import copy
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from relation_field_prediction_coordinates_p2 import (  # noqa: E402
    RelationFieldPredictionCoordinatesP2Error,
    build_relation_field_prediction_coordinates,
    load_contract,
    load_registry,
    validate_relation_field_prediction_coordinates,
)
from relation_field_prediction_coordinates_p2 import _builder_output as _builder  # noqa: E402
from relation_field_prediction_coordinates_p2._builder_math import _neg  # noqa: E402
from relation_field_prediction_coordinates_p2._common import (  # noqa: E402
    dump_json,
    load_json,
    load_npz,
    tree_hash,
    write_deterministic_npz,
    write_manifest,
)


def _meta(key: str, value: np.ndarray) -> dict[str, object]:
    return {
        "array_key": key,
        "shape": list(value.shape),
        "dtype": value.dtype.str,
        "unit": "source_defined",
        "normalization_id": "source_contract",
        "comparability_id": f"stable/{key}/{value.shape}",
        "difference_eligible": True,
    }


def _synthetic_arrays(step: int) -> dict[str, np.ndarray]:
    shape = {
        0: (0, 0, 0, 0, 0, 0, 0, 0),
        1: (-1, -1, -1, -1, 1, 1, -1, -1),
        2: (1, 1, 1, 1, -1, -1, 1, 1),
        3: (0, 0, 0, 0, 0, 0, 0, 0),
    }[step]
    names = [
        "total_variance_delta", "entropy_delta", "effective_support_delta", "participation_delta",
        "l2_concentration_delta", "peak_mass_delta", "major_component_count_delta", "component_mass_entropy_delta",
    ]
    arrays = {f"rf7_transition_shape_metrics__{name}": np.asarray(value, dtype=np.float64) for name, value in zip(names, shape)}
    support = [(10, 11, 12), (5, 6, 7), (15, 16, 17), (15, 16, 17)][step]
    concentration = [(0.1, 0.2, 0.3), (0.5, 0.6, 0.7), (0.1, 0.2, 0.3), (0.1, 0.2, 0.3)][step]
    for suffix, value in zip(("minimum", "mean", "maximum"), support):
        arrays[f"rf7_flow_channel_metrics__effective_edge_support_{suffix}"] = np.asarray(value, dtype=np.float64)
    for suffix, value in zip(("minimum", "mean", "maximum"), concentration):
        arrays[f"rf7_flow_channel_metrics__maximum_edge_fraction_{suffix}"] = np.asarray(value, dtype=np.float64)
    axis = [1.0, 2.0, 1.0, -1.0][step]
    for suffix, offset in (("minimum", -0.05), ("mean", 0.0), ("maximum", 0.05)):
        arrays[f"rf8_axis_flow_family__axis_signed_flow_{suffix}"] = np.full(5, axis + offset, dtype=np.float64)
    inward = [1.0, 0.0, 1.0, 2.0][step]
    for suffix, offset in (("minimum", -0.01), ("mean", 0.0), ("maximum", 0.01)):
        arrays[f"rf7_boundary_dynamics__mass_weighted_inward_flow_{suffix}"] = np.asarray(max(0.0, inward + offset), dtype=np.float64)
    arrays["rf7_boundary_dynamics__boundary_mass_persistence"] = np.asarray(0.8, dtype=np.float64)
    arrays["rf7_transition_shape_metrics__total_variation_distance"] = np.asarray(0.1, dtype=np.float64)
    for suffix, value in (("minimum", 0.2), ("mean", 0.25), ("maximum", 0.3)):
        arrays[f"rf8_unresolved_residual_ledger__residual_l1_{suffix}"] = np.asarray(value, dtype=np.float64)
    arrays.update({
        "rf7_flow_channel_metrics__gradient_energy_minimum": np.asarray(2.0),
        "rf7_flow_channel_metrics__gradient_energy_maximum": np.asarray(2.2),
        "rf7_flow_channel_metrics__circulation_energy_minimum": np.asarray(0.2),
        "rf7_flow_channel_metrics__circulation_energy_maximum": np.asarray(0.3),
        "rf8_history_conditioned_innovation__prior_transition_count": np.asarray(3.0),
        "rf8_history_conditioned_innovation__effective_support": np.asarray(2.0),
        "rf8_axis_flow_family__axis_signed_flow_ambiguity_width": np.full(5, 0.1),
        "rf7_frame_shape_metrics__l2_concentration": np.asarray(0.4 + 0.1 * step),
        "rf7_frame_shape_metrics__total_variance": np.asarray(1.0 + step),
        "rf7_frame_shape_metrics__effective_support": np.asarray(10.0 + step),
        "rf7_frame_shape_metrics__any_boundary_mass": np.asarray(0.2),
        "rf7_frame_shape_metrics__major_component_count": np.asarray(1.0),
    })
    return arrays


def _make_synthetic_p1(root: Path) -> Path:
    storage = {
        "origin_container_dir": "origins", "origin_name_format": "t_{origin_t:06d}",
        "parent_artifact_dir": "parents", "state_dir": "state",
        "parent_stage_dirs": {"RF-7": "rf7", "RF-8": "rf8", "RF-9": "rf9"},
        "base_state_file": "base_state.npz", "base_state_index_file": "base_state_index.json",
        "risk_state_file": "risk_state.json", "series_validation_file": "validation.json",
        "series_index_file": "series_index.json",
    }
    dump_json(root / "contract.json", {"contract_version": "relation_field_prediction_state_p1", "storage": storage})
    dump_json(root / "validation.json", {"p1_series_gate": "passed"})
    rows = []
    candidates = [
        dict(overconvergence=False, fixation=False, divergence=False, recovery_margin_reduction=False),
        dict(overconvergence=True, fixation=True, divergence=False, recovery_margin_reduction=True),
        dict(overconvergence=False, fixation=False, divergence=True, recovery_margin_reduction=False),
        dict(overconvergence=False, fixation=False, divergence=False, recovery_margin_reduction=False),
    ]
    for step, origin_t in enumerate((4, 5, 6, 7)):
        origin = root / "origins" / f"t_{origin_t:06d}"
        state = origin / "state"
        state.mkdir(parents=True)
        arrays = _synthetic_arrays(step)
        write_deterministic_npz(state / "base_state.npz", arrays)
        dump_json(state / "base_state_index.json", {"arrays": [_meta(k, v) for k, v in sorted(arrays.items())]})
        risk_rows = [{"risk_structure_id": rid, "current_candidate": value} for rid, value in candidates[step].items()]
        dump_json(state / "risk_state.json", {"records": risk_rows})
        rf7 = origin / "parents" / "rf7"; rf8 = origin / "parents" / "rf8"; rf9 = origin / "parents" / "rf9"
        dump_json(rf7 / "contract.json", {
            "transition_shape_metrics": {"shape_scalar_tolerance": 1e-3, "effective_support_tolerance": 1e-3},
            "flow_channel_metrics": {"channel_change_tolerance": 0.1},
            "boundary_dynamics": {"maximum_inward_flow_for_sticking": 0.05},
        })
        dump_json(rf8 / "contract.json", {
            "same_axis_dynamics": {"magnitude_tolerance": 0.1},
            "history_conditioned_innovation": {"minimum_prior_transition_count_for_label": 2, "minimum_effective_support_for_label": 1.5},
        })
        dump_json(rf9 / "contract.json", {
            "risk_structure": {"boundary_persistence_threshold": 0.5, "boundary_recovery_change_tolerance": 0.1, "energy_dominance_tolerance": 1e-12},
            "unresolved_residual": {"dominance_fraction": 0.5, "absolute_floor": 0.01},
        })
        dump_json(origin / "identity.json", {"origin_t": origin_t})
        write_manifest(origin, "synthetic_p1_origin")
        rows.append({"origin_t": origin_t})
    dump_json(root / "series_index.json", {"rows": rows})
    write_manifest(root, "synthetic_p1_series")
    return root


@pytest.fixture()
def synthetic_p1(tmp_path: Path) -> Path:
    return _make_synthetic_p1(tmp_path / "p1")


def test_contract_registry_and_independence_boundary() -> None:
    contract = load_contract()
    registry = load_registry()
    assert contract["scope"]["independent_validator_implementation"] is True
    assert contract["scope"]["precursor_validity_evaluation"] is False
    assert len(registry["entries"]) == 64
    ids = {row["coordinate_id"] for row in registry["entries"]}
    assert {
        "p2.risk.overconvergence.structure_margin", "p2.risk.fixation.structure_margin",
        "p2.risk.divergence.structure_margin", "p2.risk.recovery_margin_reduction.structure_margin",
        "p2.game_structure.basin_persistence",
    } <= ids
    path = ROOT / "scripts" / "relation_field_prediction_coordinates_p2" / "_independent_validator.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import): imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom): imported.append(node.module or "")
    assert not any("_builder" in name or "_formula" in name for name in imported)


def test_builder_and_true_independent_validator(synthetic_p1: Path, tmp_path: Path) -> None:
    before = tree_hash(synthetic_p1)
    output = build_relation_field_prediction_coordinates(synthetic_p1, tmp_path / "p2")
    result = validate_relation_field_prediction_coordinates(output, synthetic_p1)
    assert result["p2_series_gate"] == "passed"
    assert result["independent_formula_recomputation"] is True
    assert result["builder_formula_module_imported"] is False
    assert tree_hash(synthetic_p1) == before
    index = load_json(output / "origins" / "t_000005" / "coordinate_index.json")
    by_id = {row["coordinate_id"]: row for row in index["records"]}
    for cid in (
        "p2.condition.shape.convergence", "p2.condition.pathway.narrowing",
        "p2.condition.same_axis.amplification", "p2.condition.recovery.return_suppression",
        "p2.risk.overconvergence.structure_margin", "p2.risk.fixation.structure_margin",
        "p2.risk.divergence.structure_margin", "p2.risk.recovery_margin_reduction.structure_margin",
    ):
        assert by_id[cid]["availability"] == "available"
    assert by_id["p2.pathway.available_path_count"]["unavailable_reasons"] == ["reserved_not_implemented"]


def test_deterministic_build_and_backward_differences(synthetic_p1: Path, tmp_path: Path) -> None:
    a = build_relation_field_prediction_coordinates(synthetic_p1, tmp_path / "a")
    b = build_relation_field_prediction_coordinates(synthetic_p1, tmp_path / "b")
    def hashes(root: Path) -> dict[str, str]:
        import hashlib
        return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*")) if p.is_file()}
    assert hashes(a) == hashes(b)
    diff = load_json(a / "origins" / "t_000007" / "difference_index.json")
    assert diff["first_difference_count"] > 0
    assert diff["second_difference_count"] > 0
    assert diff["zero_fill_performed"] is False


def test_independent_validator_detects_builder_formula_mutation(synthetic_p1: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    original = _builder._shape
    def mutated(ctx):
        result = original(ctx)
        assert result is not None
        result = dict(result)
        result["convergence"] = _neg(result["convergence"])
        return result
    monkeypatch.setattr(_builder, "_shape", mutated)
    bad = build_relation_field_prediction_coordinates(synthetic_p1, tmp_path / "bad")
    with pytest.raises(RelationFieldPredictionCoordinatesP2Error, match="independent coordinate"):
        validate_relation_field_prediction_coordinates(bad, synthetic_p1)


def test_manifest_regenerated_coordinate_tampering_is_rejected(synthetic_p1: Path, tmp_path: Path) -> None:
    output = build_relation_field_prediction_coordinates(synthetic_p1, tmp_path / "p2")
    origin = output / "origins" / "t_000005"
    path = origin / "coordinates.npz"
    arrays = load_npz(path)
    key = "p2.risk.overconvergence.structure_margin__center"
    arrays[key] = arrays[key] + 0.25
    write_deterministic_npz(path, arrays)
    write_manifest(origin, "relation_field_prediction_coordinates_p2_origin")
    write_manifest(output, "relation_field_prediction_coordinates_p2_series")
    with pytest.raises(RelationFieldPredictionCoordinatesP2Error, match="independent coordinate"):
        validate_relation_field_prediction_coordinates(output, synthetic_p1)


def test_unregistered_file_and_contract_change_are_rejected(synthetic_p1: Path, tmp_path: Path) -> None:
    output = build_relation_field_prediction_coordinates(synthetic_p1, tmp_path / "p2")
    (output / "future_outcomes.json").write_text("{}\n", encoding="utf-8")
    with pytest.raises(RelationFieldPredictionCoordinatesP2Error, match="manifest"):
        validate_relation_field_prediction_coordinates(output, synthetic_p1)
    output2 = build_relation_field_prediction_coordinates(synthetic_p1, tmp_path / "p2b")
    payload = load_json(output2 / "contract.json")
    payload["contract_version"] = "tampered"
    dump_json(output2 / "contract.json", payload)
    write_manifest(output2, "relation_field_prediction_coordinates_p2_series")
    with pytest.raises(RelationFieldPredictionCoordinatesP2Error, match="stored contract"):
        validate_relation_field_prediction_coordinates(output2, synthetic_p1)


try:
    import csv
    import hashlib
    from fixed5axis_gk_rc1 import AXIS_BINS, AXIS_NAMES, GENESIS_HASH, compute_gt_hash, compute_history_chain_hash
    from generic_relation_field_g2 import build_fixed5_structure_artifact
    from relation_field_grid_rc1 import build_grid_artifact, cell_id_from_indices
    from relation_field_prediction_state_p1 import build_prediction_state_series, validate_prediction_state_series
    HAVE_CURRENT_P1 = True
except Exception:
    HAVE_CURRENT_P1 = False


def _real_point(indices: tuple[int, int, int, int, int]) -> np.ndarray:
    flat=np.zeros(5**5,dtype=np.float64);flat[cell_id_from_indices(indices)]=1.0
    return flat.reshape((5,5,5,5,5))


def _real_write_trajectory(root: Path, frames: list[np.ndarray]) -> Path:
    root.mkdir(parents=True);np.save(root/"gt_mass.npy",np.stack(frames),allow_pickle=False)
    fields=["trajectory_id","source_trajectory_id","t","phase","gt_row_index","gt_hash","previous_gt_hash","history_chain_hash","delta_t","continuity_status","admissible_for_research","source_state_ref","source_state_hash"]
    rows=[];previous="";chain=GENESIS_HASH;trajectory_id="traj_p2_current_main"
    for t,frame in enumerate(frames):
        distribution_hash=hashlib.sha256(np.ascontiguousarray(frame).tobytes()).hexdigest();source_hash=hashlib.sha256(f"p2-source-{t}-{distribution_hash}".encode()).hexdigest()
        gt_hash=compute_gt_hash(contract_version="fixed5axis_gk_rc1",trajectory_id=trajectory_id,t=t,distribution=frame,source_state_hash=source_hash);chain=compute_history_chain_hash(chain,gt_hash,t)
        rows.append({"trajectory_id":trajectory_id,"source_trajectory_id":trajectory_id,"t":t,"phase":"pre_transition","gt_row_index":t,"gt_hash":gt_hash,"previous_gt_hash":previous,"history_chain_hash":chain,"delta_t":0 if t==0 else 1,"continuity_status":"initial" if t==0 else "continuous","admissible_for_research":True,"source_state_ref":f"states/step_{t:06d}.npz","source_state_hash":source_hash});previous=gt_hash
    with (root/"history_ledger.csv").open("w",encoding="utf-8",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=fields,lineterminator="\n");writer.writeheader();writer.writerows(rows)
    dump_json(root/"provenance.json",{"contract_version":"fixed5axis_gk_rc1","axis_order":list(AXIS_NAMES),"axis_bins":list(AXIS_BINS),"gt_shape":[5,5,5,5,5],"gt_dtype":"float64","gt_phase":"pre_transition","source_mode":"reference_full","trajectory_id":trajectory_id,"total_gt_frames":len(frames),"forbidden_source_files_read":[],"source_writeback_performed":False,"canonical_history_is_complete_gt_sequence":True})
    return root


@pytest.mark.skipif(not HAVE_CURRENT_P1, reason="current repository P1 modules are unavailable")
def test_current_main_p1_artifact_integration(tmp_path: Path) -> None:
    frames=[
        _real_point((0,2,2,2,2)),_real_point((1,2,2,2,2)),_real_point((2,2,2,2,2)),_real_point((3,2,2,2,2)),
        _real_point((3,3,2,2,2)),_real_point((3,3,3,2,2)),_real_point((3,3,3,3,2)),_real_point((3,3,3,3,3)),
    ]
    trajectory=_real_write_trajectory(tmp_path/"trajectory",frames);grid=build_grid_artifact(tmp_path/"grid");structure=build_fixed5_structure_artifact(grid,tmp_path/"structure")
    p1=build_prediction_state_series(trajectory,grid,structure,tmp_path/"p1",origins=[4,5,6,7])
    assert validate_prediction_state_series(p1,trajectory,grid,structure)["p1_series_gate"]=="passed"
    output=build_relation_field_prediction_coordinates(p1,tmp_path/"p2-real");result=validate_relation_field_prediction_coordinates(output,p1)
    assert result["p2_series_gate"]=="passed"
    latest=output/"origins"/"t_000007";index=load_json(latest/"coordinate_index.json");by_id={row["coordinate_id"]:row for row in index["records"]}
    for cid in ("p2.condition.shape.convergence","p2.condition.shape.divergence","p2.condition.pathway.narrowing","p2.condition.pathway.widening","p2.condition.same_axis.amplification","p2.condition.same_axis.decay","p2.condition.same_axis.axis_stop","p2.condition.recovery.weakening","p2.condition.recovery.strengthening","p2.condition.recovery.return_suppression"):
        assert by_id[cid]["availability"]=="available"
    risk=load_json(latest/"risk_structure_margins.json")
    assert len(risk["records"])==4
    assert all(row["p1_boolean_consistent"] is True for row in risk["records"])
