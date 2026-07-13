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

from fixed5axis_gk_rc1 import (  # noqa: E402
    AXIS_BINS,
    AXIS_NAMES,
    GENESIS_HASH,
    compute_gt_hash,
    compute_history_chain_hash,
)
from generic_relation_field_g2 import (  # noqa: E402
    _load_npz,
    _write_deterministic_npz,
    _write_manifest,
    build_fixed5_structure_artifact,
)
from relation_field_grid_rc1 import build_grid_artifact, cell_id_from_indices  # noqa: E402
from relation_field_prediction_state_p1 import (  # noqa: E402
    RelationFieldPredictionStateP1Error,
    build_prediction_state_series,
    load_contract,
    load_extraction_profile,
    load_risk_registry,
    validate_contract,
    validate_prediction_state_series,
)

LEDGER_FIELDS = [
    "trajectory_id", "source_trajectory_id", "t", "phase", "gt_row_index", "gt_hash",
    "previous_gt_hash", "history_chain_hash", "delta_t", "continuity_status",
    "admissible_for_research", "source_state_ref", "source_state_hash",
]


def _point(indices: tuple[int, int, int, int, int]) -> np.ndarray:
    flat = np.zeros(5 ** 5, dtype=np.float64)
    flat[cell_id_from_indices(indices)] = 1.0
    return flat.reshape((5, 5, 5, 5, 5))


def _mixture(items: list[tuple[tuple[int, int, int, int, int], float]]) -> np.ndarray:
    flat = np.zeros(5 ** 5, dtype=np.float64)
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
        distribution_hash = hashlib.sha256(np.ascontiguousarray(frame).tobytes()).hexdigest()
        source_state_hash = hashlib.sha256(f"p1-source-{t}-{distribution_hash}".encode()).hexdigest()
        gt_hash = compute_gt_hash(
            contract_version="fixed5axis_gk_rc1",
            trajectory_id=trajectory_id,
            t=t,
            distribution=frame,
            source_state_hash=source_state_hash,
        )
        history_chain_hash = compute_history_chain_hash(history_chain_hash, gt_hash, t)
        rows.append({
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
        })
        previous_gt_hash = gt_hash
    with (root / "history_ledger.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=LEDGER_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    (root / "provenance.json").write_text(
        json.dumps({
            "contract_version": "fixed5axis_gk_rc1",
            "axis_order": list(AXIS_NAMES),
            "axis_bins": list(AXIS_BINS),
            "gt_shape": [5, 5, 5, 5, 5],
            "gt_dtype": "float64",
            "gt_phase": "pre_transition",
            "source_mode": "reference_full",
            "trajectory_id": trajectory_id,
            "total_gt_frames": len(frames),
            "forbidden_source_files_read": [],
            "source_writeback_performed": False,
            "canonical_history_is_complete_gt_sequence": True,
        }, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return root


def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*")) if path.is_file()
    }


def _origin(root: Path, origin_t: int, contract: dict[str, object] | None = None) -> Path:
    active = contract or load_contract()
    storage = active["storage"]
    name = str(storage["origin_name_format"]).format(origin_t=origin_t)
    return root / str(storage["origin_container_dir"]) / name


@pytest.fixture(scope="module")
def p1_fixture(tmp_path_factory: pytest.TempPathFactory) -> dict[str, object]:
    root = tmp_path_factory.mktemp("relation-field-p1")
    prefix = [
        _point((0, 2, 2, 2, 2)),
        _point((1, 2, 2, 2, 2)),
        _point((2, 2, 2, 2, 2)),
        _point((3, 2, 2, 2, 2)),
        _point((3, 3, 2, 2, 2)),
        _point((3, 3, 3, 2, 2)),
        _point((3, 3, 3, 3, 2)),
        _point((3, 3, 3, 3, 3)),
    ]
    neutral_future = [_point((2, 3, 3, 3, 3)), _point((2, 2, 3, 3, 3))]
    divergent_future = [
        _mixture([((3, 3, 3, 3, 3), 0.5), ((2, 3, 3, 3, 3), 0.5)]),
        _mixture([((a, b, 3, 3, 3), 0.25) for a in (2, 3) for b in (2, 3)]),
    ]
    trajectory = _write_trajectory(root / "trajectory", prefix + neutral_future, trajectory_id="traj_p1_shared")
    trajectory_alt = _write_trajectory(root / "trajectory_alt", prefix + divergent_future, trajectory_id="traj_p1_shared")
    grid = build_grid_artifact(root / "grid")
    structure = build_fixed5_structure_artifact(grid, root / "structure")
    series = build_prediction_state_series(
        trajectory, grid, structure, root / "series", origins=[4, 5, 6, 7]
    )
    series_repeat = build_prediction_state_series(
        trajectory, grid, structure, root / "series_repeat", origins=[4, 5, 6, 7]
    )
    alt_prefix = build_prediction_state_series(
        trajectory_alt, grid, structure, root / "alt_prefix", origins=[4]
    )
    standalone = build_prediction_state_series(
        trajectory, grid, structure, root / "standalone", origins=[7]
    )
    return {
        "root": root,
        "trajectory": trajectory,
        "trajectory_alt": trajectory_alt,
        "grid": grid,
        "structure": structure,
        "series": series,
        "series_repeat": series_repeat,
        "alt_prefix": alt_prefix,
        "standalone": standalone,
    }


def test_contract_freezes_p1_without_predictor_or_fixed_counts() -> None:
    contract = load_contract()
    profile = load_extraction_profile()
    registry = load_risk_registry()
    assert contract["scope"]["prediction_model_implementation"] is False
    assert contract["scope"]["continuous_precursor_coordinate_implementation"] is False
    assert contract["input"]["forbidden_parent_stages"] == ["RF-4", "RF-10"]
    assert profile["included_stages"] == ["RF-3", "RF-5", "RF-6", "RF-7", "RF-8", "RF-9"]
    assert {row["risk_structure_id"] for row in registry["entries"] if row["role"] == "required_primary"} == {
        "overconvergence", "fixation", "divergence", "recovery_margin_reduction"
    }
    script_text = (ROOT / "scripts" / "relation_field_prediction_state_p1.py").read_text(encoding="utf-8")
    contract_text = (ROOT / "configs" / "relation_field_prediction_state_p1_contract.json").read_text(encoding="utf-8")
    for fixed_count in ("3125", "12500", "20000", "229", "15"):
        assert fixed_count not in script_text
        assert fixed_count not in contract_text


def test_builder_validator_and_backward_differences(p1_fixture: dict[str, object]) -> None:
    result = validate_prediction_state_series(
        p1_fixture["series"], p1_fixture["trajectory"], p1_fixture["grid"], p1_fixture["structure"]
    )
    assert result["p1_series_gate"] == "passed"
    assert result["origin_count"] == 4
    contract = load_contract()
    state_7 = _origin(Path(p1_fixture["series"]), 7) / contract["storage"]["state_dir"]
    base = _load_npz(state_7 / contract["storage"]["base_state_file"])
    first = _load_npz(state_7 / contract["storage"]["first_difference_file"])
    second = _load_npz(state_7 / contract["storage"]["second_difference_file"])
    difference_index = json.loads((state_7 / contract["storage"]["difference_index_file"]).read_text())
    assert len(base) > 0
    assert len(first) == difference_index["first_difference_count"] > 0
    assert len(second) == difference_index["second_difference_count"] > 0
    assert difference_index["zero_fill_performed"] is False
    assert not any(path.name.startswith("future_") for path in Path(p1_fixture["series"]).rglob("*"))


def test_candidate_count_is_derived_not_fixed(p1_fixture: dict[str, object]) -> None:
    contract = load_contract()
    origin = _origin(Path(p1_fixture["series"]), 7)
    state = origin / contract["storage"]["state_dir"]
    arrays = _load_npz(state / contract["storage"]["base_state_file"])
    rows = [json.loads(line) for line in (state / contract["storage"]["candidate_records_file"]).read_text().splitlines()]
    flow_count = int(np.asarray(arrays["rf5_candidate_flows__candidate_transition_index"]).size)
    risk_count = len(load_risk_registry()["entries"])
    assert len(rows) == flow_count + risk_count


def test_deterministic_build_and_same_prefix_different_future(p1_fixture: dict[str, object]) -> None:
    assert _tree_hashes(Path(p1_fixture["series"])) == _tree_hashes(Path(p1_fixture["series_repeat"]))
    contract = load_contract()
    first = _origin(Path(p1_fixture["series"]), 4)
    alt = _origin(Path(p1_fixture["alt_prefix"]), 4)
    assert _tree_hashes(first) == _tree_hashes(alt)
    assert validate_prediction_state_series(
        p1_fixture["alt_prefix"], p1_fixture["trajectory_alt"], p1_fixture["grid"], p1_fixture["structure"]
    )["p1_series_gate"] == "passed"


def test_series_and_standalone_origin_base_state_match(p1_fixture: dict[str, object]) -> None:
    contract = load_contract()
    series_state = _origin(Path(p1_fixture["series"]), 7) / contract["storage"]["state_dir"]
    standalone_state = _origin(Path(p1_fixture["standalone"]), 7) / contract["storage"]["state_dir"]
    for name in (
        contract["storage"]["base_state_file"],
        contract["storage"]["base_state_index_file"],
        contract["storage"]["semantic_state_file"],
        contract["storage"]["candidate_records_file"],
        contract["storage"]["risk_state_file"],
    ):
        assert (series_state / name).read_bytes() == (standalone_state / name).read_bytes()


def test_manifest_regenerated_numeric_tampering_is_rejected(p1_fixture: dict[str, object], tmp_path: Path) -> None:
    copied = tmp_path / "tampered"
    shutil.copytree(p1_fixture["series"], copied)
    contract = load_contract()
    origin = _origin(copied, 7)
    state = origin / contract["storage"]["state_dir"]
    base_path = state / contract["storage"]["base_state_file"]
    arrays = _load_npz(base_path)
    key = next(key for key, value in arrays.items() if np.asarray(value).dtype.kind == "f" and np.asarray(value).size)
    changed = {name: value.copy() for name, value in arrays.items()}
    changed[key].reshape(-1)[0] += 0.125
    _write_deterministic_npz(base_path, changed)
    _write_manifest(origin, "relation_field_prediction_state_p1_origin")
    _write_manifest(copied, "relation_field_prediction_state_p1_series")
    with pytest.raises(RelationFieldPredictionStateP1Error, match="base state"):
        validate_prediction_state_series(copied, p1_fixture["trajectory"], p1_fixture["grid"], p1_fixture["structure"])


def test_unregistered_file_and_contract_version_are_rejected(p1_fixture: dict[str, object], tmp_path: Path) -> None:
    extra = tmp_path / "extra"
    shutil.copytree(p1_fixture["series"], extra)
    (extra / "future_outcomes.npz").write_bytes(b"forbidden")
    with pytest.raises(Exception, match="manifest"):
        validate_prediction_state_series(extra, p1_fixture["trajectory"], p1_fixture["grid"], p1_fixture["structure"])

    altered = tmp_path / "altered"
    shutil.copytree(p1_fixture["series"], altered)
    payload = json.loads((altered / "contract.json").read_text())
    payload["contract_version"] = "tampered"
    (altered / "contract.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    _write_manifest(altered, "relation_field_prediction_state_p1_series")
    with pytest.raises(RelationFieldPredictionStateP1Error, match="unsupported P1 contract"):
        validate_prediction_state_series(altered, p1_fixture["trajectory"], p1_fixture["grid"], p1_fixture["structure"])


def test_contract_can_change_parent_and_origin_directories(p1_fixture: dict[str, object], tmp_path: Path) -> None:
    custom = deepcopy(load_contract())
    custom["storage"]["origin_container_dir"] = "prediction_origins"
    custom["storage"]["history_view_dir"] = "causal_history"
    custom["storage"]["parent_artifact_dir"] = "source_parents"
    custom["storage"]["state_dir"] = "x_t"
    custom_path = tmp_path / "custom_contract.json"
    custom_path.write_text(json.dumps(custom, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    validate_contract(custom)
    output = build_prediction_state_series(
        p1_fixture["trajectory"], p1_fixture["grid"], p1_fixture["structure"], tmp_path / "custom",
        origins=[4], contract_path=custom_path,
    )
    result = validate_prediction_state_series(
        output, p1_fixture["trajectory"], p1_fixture["grid"], p1_fixture["structure"]
    )
    assert result["p1_series_gate"] == "passed"
    assert (output / "prediction_origins" / "t_000004" / "source_parents" / "rf9").is_dir()


def test_manifest_regenerated_identity_and_index_tampering_is_rejected(
    p1_fixture: dict[str, object], tmp_path: Path
) -> None:
    contract = load_contract()

    identity_copy = tmp_path / "identity_tampered"
    shutil.copytree(p1_fixture["series"], identity_copy)
    origin = _origin(identity_copy, 7)
    identity_path = origin / contract["storage"]["origin_identity_file"]
    identity = json.loads(identity_path.read_text(encoding="utf-8"))
    identity["candidate_record_count"] = int(identity["candidate_record_count"]) + 1
    identity_path.write_text(json.dumps(identity, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_manifest(origin, "relation_field_prediction_state_p1_origin")
    _write_manifest(identity_copy, "relation_field_prediction_state_p1_series")
    with pytest.raises(RelationFieldPredictionStateP1Error, match="origin identity"):
        validate_prediction_state_series(
            identity_copy, p1_fixture["trajectory"], p1_fixture["grid"], p1_fixture["structure"]
        )

    index_copy = tmp_path / "index_tampered"
    shutil.copytree(p1_fixture["series"], index_copy)
    index_path = index_copy / contract["storage"]["series_index_file"]
    index = json.loads(index_path.read_text(encoding="utf-8"))
    index["rows"][-1]["candidate_record_count"] += 1
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_manifest(index_copy, "relation_field_prediction_state_p1_series")
    with pytest.raises(RelationFieldPredictionStateP1Error, match="series index"):
        validate_prediction_state_series(
            index_copy, p1_fixture["trajectory"], p1_fixture["grid"], p1_fixture["structure"]
        )
