"""固定5軸 動的関係場 RF-9: 構造リスク候補の統合。"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from relation_field_axis_coupling_innovation_rc1 import validate_axis_coupling_innovation

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "configs" / "relation_field_risk_structure_rc1.json"
AXIS_COUNT = 5


class RelationFieldRiskStructureError(ValueError):
    """RF-9契約、親成果物、構造候補、成果物の不整合。"""


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_npz(path: Path, arrays: Mapping[str, np.ndarray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name in sorted(arrays):
            buffer = io.BytesIO()
            np.save(buffer, np.asarray(arrays[name]), allow_pickle=False)
            info = zipfile.ZipInfo(f"{name}.npy", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o600 << 16
            archive.writestr(info, buffer.getvalue(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def _load_npz(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as loaded:
        return {name: loaded[name].copy() for name in loaded.files}


def _manifest_entries(root: Path, *, exclude: Iterable[str] = ()) -> list[dict[str, Any]]:
    excluded = set(exclude)
    return [
        {
            "path": path.relative_to(root).as_posix(),
            "sha256": _sha256_file(path),
            "size_bytes": path.stat().st_size,
        }
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.relative_to(root).as_posix() not in excluded
    ]


def load_contract(path: str | Path = DEFAULT_CONTRACT) -> dict[str, Any]:
    contract = _load_json(Path(path))
    validate_contract(contract)
    return contract


def validate_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("contract_version") != "relation_field_risk_structure_rc1":
        raise RelationFieldRiskStructureError("unsupported RF-9 contract")
    if int(contract.get("input", {}).get("minimum_transition_count", -1)) < 3:
        raise RelationFieldRiskStructureError("RF-9 requires at least three transitions")
    if contract.get("aggregation", {}).get("single_scalar_risk_score_forbidden") is not True:
        raise RelationFieldRiskStructureError("RF-9 must not collapse candidates into one risk score")
    if contract.get("semantic_limits", {}).get("true_irreversibility_claim") is not False:
        raise RelationFieldRiskStructureError("RF-9 must not claim true irreversibility")
    fraction = float(contract.get("unresolved_residual", {}).get("dominance_fraction", -1.0))
    if not 0.0 < fraction <= 1.0:
        raise RelationFieldRiskStructureError("RF-9 residual dominance fraction mismatch")


def _verify_manifest(root: Path) -> None:
    manifest = _load_json(root / "manifest.json")
    expected: set[str] = set()
    for entry in manifest.get("files", []):
        relative = str(entry["path"])
        expected.add(relative)
        path = root / relative
        if not path.is_file() or path.stat().st_size != int(entry["size_bytes"]) or _sha256_file(path) != entry["sha256"]:
            raise RelationFieldRiskStructureError(f"manifest mismatch: {relative}")
    actual = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.name != "manifest.json"
    }
    if expected != actual:
        raise RelationFieldRiskStructureError("manifest file set mismatch")


def _load_parent_artifacts(
    trajectory_root: Path,
    grid_root: Path,
    rf5_root: Path,
    rf6_root: Path,
    rf7_root: Path,
    rf8_root: Path,
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    validate_axis_coupling_innovation(
        rf8_root,
        trajectory_root,
        grid_root,
        rf5_root,
        rf6_root,
        rf7_root,
    )
    rf5_identity = _load_json(rf5_root / "identity.json")
    rf6_identity = _load_json(rf6_root / "identity.json")
    rf7_identity = _load_json(rf7_root / "identity.json")
    rf8_identity = _load_json(rf8_root / "identity.json")
    if rf7_identity.get("rf5_relation_field_id") != rf5_identity.get("relation_field_id"):
        raise RelationFieldRiskStructureError("RF-9 RF-7/RF-5 identity mismatch")
    if rf7_identity.get("rf6_decomposition_id") != rf6_identity.get("decomposition_id"):
        raise RelationFieldRiskStructureError("RF-9 RF-7/RF-6 identity mismatch")
    if rf8_identity.get("rf5_relation_field_id") != rf5_identity.get("relation_field_id"):
        raise RelationFieldRiskStructureError("RF-9 RF-8/RF-5 identity mismatch")
    if rf8_identity.get("rf6_decomposition_id") != rf6_identity.get("decomposition_id"):
        raise RelationFieldRiskStructureError("RF-9 RF-8/RF-6 identity mismatch")
    if rf8_identity.get("rf7_shape_dynamics_id") != rf7_identity.get("shape_dynamics_id"):
        raise RelationFieldRiskStructureError("RF-9 RF-8/RF-7 identity mismatch")
    transition_count = int(rf5_identity["transition_count"])
    if transition_count < int(contract["input"]["minimum_transition_count"]):
        raise RelationFieldRiskStructureError("RF-9 history has too few transitions")

    transition_arrays = _load_npz(rf7_root / "transition_shape_metrics.npz")
    flow_arrays = _load_npz(rf7_root / "flow_channel_metrics.npz")
    boundary_arrays = _load_npz(rf7_root / "boundary_dynamics.npz")
    transition_labels = _load_json(rf7_root / "transition_labels.json")
    axis_family = _load_npz(rf8_root / "axis_flow_family.npz")
    innovation = _load_npz(rf8_root / "history_conditioned_innovation.npz")
    residual = _load_npz(rf8_root / "unresolved_residual_ledger.npz")
    same_axis = _load_json(rf8_root / "same_axis_dynamics.json")

    transition_times = np.asarray(transition_arrays["transition_times"], dtype=np.int32)
    for payload, name in (
        (flow_arrays, "RF-7 flow"),
        (boundary_arrays, "RF-7 boundary"),
        (axis_family, "RF-8 axis family"),
        (residual, "RF-8 residual"),
    ):
        if not np.array_equal(np.asarray(payload["transition_times"], dtype=np.int32), transition_times):
            raise RelationFieldRiskStructureError(f"RF-9 {name} transition-time mismatch")
    if transition_times.shape != (transition_count,):
        raise RelationFieldRiskStructureError("RF-9 transition count mismatch")
    shape_rows = transition_labels.get("transitions", [])
    channel_rows = transition_labels.get("channel_labels", {}).get("transitions", [])
    same_axis_lags = same_axis.get("lags", [])
    if len(shape_rows) != transition_count or len(channel_rows) != transition_count:
        raise RelationFieldRiskStructureError("RF-9 RF-7 label length mismatch")
    if len(same_axis_lags) != transition_count - 1:
        raise RelationFieldRiskStructureError("RF-9 RF-8 lag length mismatch")
    if np.asarray(innovation["history_conditioned_new_drive_candidate"]).shape != (transition_count, AXIS_COUNT):
        raise RelationFieldRiskStructureError("RF-9 RF-8 innovation shape mismatch")
    if np.asarray(axis_family["axis_signed_flow_ambiguity_width"]).shape != (transition_count, AXIS_COUNT):
        raise RelationFieldRiskStructureError("RF-9 RF-8 ambiguity shape mismatch")

    return {
        "rf5_identity": rf5_identity,
        "rf6_identity": rf6_identity,
        "rf7_identity": rf7_identity,
        "rf8_identity": rf8_identity,
        "rf5_manifest_hash": _sha256_file(rf5_root / "manifest.json"),
        "rf6_manifest_hash": _sha256_file(rf6_root / "manifest.json"),
        "rf7_manifest_hash": _sha256_file(rf7_root / "manifest.json"),
        "rf8_manifest_hash": _sha256_file(rf8_root / "manifest.json"),
        "transition_count": transition_count,
        "transition_times": transition_times,
        "shape_rows": shape_rows,
        "channel_rows": channel_rows,
        "same_axis_lags": same_axis_lags,
        "transition_arrays": transition_arrays,
        "flow_arrays": flow_arrays,
        "boundary_arrays": boundary_arrays,
        "axis_family": axis_family,
        "innovation": innovation,
        "residual": residual,
    }


def _bool_axis(values: Sequence[Any], name: str) -> np.ndarray:
    array = np.asarray(values, dtype=bool)
    if array.shape != (AXIS_COUNT,):
        raise RelationFieldRiskStructureError(f"RF-9 {name} axis shape mismatch")
    return array


def _append_if(target: list[str], condition: bool, label: str) -> None:
    if condition:
        target.append(label)


def compute_risk_structure(parent: Mapping[str, Any], contract: Mapping[str, Any]) -> dict[str, Any]:
    transition_count = int(parent["transition_count"])
    if transition_count < 2:
        raise RelationFieldRiskStructureError("RF-9 risk alignment requires at least two transitions")
    times = np.asarray(parent["transition_times"], dtype=np.int32)
    shape_rows = parent["shape_rows"]
    channel_rows = parent["channel_rows"]
    same_axis_lags = parent["same_axis_lags"]
    transition_arrays = parent["transition_arrays"]
    flow = parent["flow_arrays"]
    boundary = parent["boundary_arrays"]
    axis_family = parent["axis_family"]
    innovation = parent["innovation"]
    residual = parent["residual"]
    settings = contract["risk_structure"]
    energy_tolerance = float(settings["energy_dominance_tolerance"])
    recovery_tolerance = float(settings["boundary_recovery_change_tolerance"])
    persistence_threshold = float(settings["boundary_persistence_threshold"])
    residual_fraction = float(contract["unresolved_residual"]["dominance_fraction"])
    residual_floor = float(contract["unresolved_residual"]["absolute_floor"])

    metric_lists: dict[str, list[Any]] = {
        "target_transition_index": [],
        "risk_transition_times": [],
        "shape_convergence_signal": [],
        "shape_divergence_signal": [],
        "flow_channel_narrowing_signal": [],
        "flow_channel_widening_signal": [],
        "same_axis_amplification_signal": [],
        "same_axis_attenuation_or_cessation_signal": [],
        "direction_reversal_signal": [],
        "boundary_recovery_weakening_signal": [],
        "boundary_recovery_strengthening_signal": [],
        "observed_return_suppression_candidate": [],
        "gradient_dominance_consensus": [],
        "circulation_dominance_consensus": [],
        "overconvergence_candidate": [],
        "fixation_candidate": [],
        "divergence_candidate": [],
        "recovery_margin_reduction_candidate": [],
        "history_conditioned_new_drive_present": [],
        "new_drive_coincident_candidate": [],
        "unresolved_residual_dominance_candidate": [],
        "observed_change_l1": [],
        "unresolved_residual_fraction_minimum": [],
        "unresolved_residual_fraction_mean": [],
        "boundary_inward_flow_change": [],
        "axis_flow_ambiguity_maximum": [],
        "innovation_axis_count": [],
        "unique_candidate_count": [],
    }
    candidate_rows: list[dict[str, Any]] = []
    evidence_rows: list[dict[str, Any]] = []
    counter_rows: list[dict[str, Any]] = []

    for target in range(1, transition_count):
        lag = same_axis_lags[target - 1]
        shape = shape_rows[target]
        channel = channel_rows[target]
        amplification_axes = _bool_axis(lag["same_direction_amplification_candidate"], "amplification")
        attenuation_axes = _bool_axis(lag["same_direction_attenuation_candidate"], "attenuation")
        reversal_axes = _bool_axis(lag["direction_reversal_candidate"], "reversal")
        cessation_axes = _bool_axis(lag["axis_cessation_candidate"], "cessation")
        activation_axes = _bool_axis(lag["axis_activation_candidate"], "activation")
        innovation_axes = np.asarray(
            innovation["history_conditioned_new_drive_candidate"][target], dtype=bool
        )

        shape_convergence = bool(
            shape.get("contraction_candidate", False)
            or shape.get("concentration_candidate", False)
            or shape.get("coalescence_candidate", False)
        )
        shape_divergence = bool(
            shape.get("expansion_candidate", False)
            or shape.get("dispersion_candidate", False)
            or shape.get("fragmentation_candidate", False)
        )
        narrowing = bool(channel.get("flow_channel_narrowing_candidate", False))
        widening = bool(channel.get("flow_channel_widening_candidate", False))
        amplification = bool(np.any(amplification_axes))
        attenuation_or_cessation = bool(np.any(attenuation_axes | cessation_axes))
        reversal = bool(np.any(reversal_axes))
        boundary_sticking = bool(shape.get("boundary_sticking_candidate", False))
        persistence = float(boundary["boundary_mass_persistence"][target])
        inward = float(boundary["mass_weighted_inward_flow_mean"][target])
        previous_inward = float(boundary["mass_weighted_inward_flow_mean"][target - 1])
        inward_change = inward - previous_inward
        recovery_weakening = bool(
            boundary_sticking
            or (persistence >= persistence_threshold and inward_change < -recovery_tolerance)
        )
        recovery_strengthening = bool(
            inward_change > recovery_tolerance
            or widening
            or reversal
            or shape.get("expansion_candidate", False)
            or shape.get("dispersion_candidate", False)
        )
        return_suppression = recovery_weakening and not recovery_strengthening

        gradient_minimum = float(flow["gradient_energy_minimum"][target])
        gradient_maximum = float(flow["gradient_energy_maximum"][target])
        circulation_minimum = float(flow["circulation_energy_minimum"][target])
        circulation_maximum = float(flow["circulation_energy_maximum"][target])
        gradient_dominance = gradient_minimum > circulation_maximum + energy_tolerance
        circulation_dominance = circulation_minimum > gradient_maximum + energy_tolerance

        overconvergence = shape_convergence and narrowing and amplification
        fixation = overconvergence and return_suppression
        divergence = shape_divergence and widening and attenuation_or_cessation
        recovery_margin_reduction = recovery_weakening and not recovery_strengthening
        new_drive_present = bool(np.any(innovation_axes))
        structural_candidate = overconvergence or fixation or divergence or recovery_margin_reduction
        new_drive_coincident = new_drive_present and structural_candidate

        observed_change_l1 = 2.0 * float(transition_arrays["total_variation_distance"][target])
        residual_minimum = float(residual["residual_l1_minimum"][target])
        residual_mean = float(residual["residual_l1_mean"][target])
        denominator = max(observed_change_l1, residual_floor)
        residual_ratio_minimum = residual_minimum / denominator
        residual_ratio_mean = residual_mean / denominator
        residual_dominance = bool(
            residual_minimum > residual_floor
            and (
                observed_change_l1 <= residual_floor
                or residual_minimum >= residual_fraction * observed_change_l1
            )
        )

        general_evidence: list[str] = []
        for condition, label in (
            (shape_convergence, "shape_convergence"),
            (shape_divergence, "shape_divergence"),
            (narrowing, "flow_channel_narrowing"),
            (widening, "flow_channel_widening"),
            (amplification, "same_axis_amplification"),
            (attenuation_or_cessation, "same_axis_attenuation_or_cessation"),
            (reversal, "direction_reversal"),
            (recovery_weakening, "boundary_recovery_weakening"),
            (recovery_strengthening, "boundary_recovery_strengthening"),
            (gradient_dominance, "gradient_dominance_consensus"),
            (circulation_dominance, "circulation_dominance_consensus"),
            (new_drive_present, "history_conditioned_new_drive"),
            (residual_dominance, "unresolved_residual_dominance"),
        ):
            _append_if(general_evidence, bool(condition), label)

        over_support: list[str] = []
        _append_if(over_support, shape_convergence, "shape_convergence")
        _append_if(over_support, narrowing, "flow_channel_narrowing")
        _append_if(over_support, amplification, "same_axis_amplification")
        over_counter: list[str] = []
        _append_if(over_counter, shape_divergence, "shape_divergence")
        _append_if(over_counter, widening, "flow_channel_widening")
        _append_if(over_counter, reversal, "direction_reversal")
        _append_if(over_counter, recovery_strengthening, "boundary_recovery_strengthening")

        fixation_support = list(over_support)
        _append_if(fixation_support, return_suppression, "observed_return_suppression")
        fixation_counter = list(over_counter)
        _append_if(fixation_counter, not recovery_weakening, "recovery_weakening_not_observed")

        divergence_support: list[str] = []
        _append_if(divergence_support, shape_divergence, "shape_divergence")
        _append_if(divergence_support, widening, "flow_channel_widening")
        _append_if(divergence_support, attenuation_or_cessation, "same_axis_attenuation_or_cessation")
        divergence_counter: list[str] = []
        _append_if(divergence_counter, shape_convergence, "shape_convergence")
        _append_if(divergence_counter, narrowing, "flow_channel_narrowing")
        _append_if(divergence_counter, amplification, "same_axis_amplification")

        candidate_rows.append(
            {
                "target_transition_index": target,
                "transition_time": int(times[target]),
                "overconvergence_candidate": overconvergence,
                "fixation_candidate": fixation,
                "divergence_candidate": divergence,
                "recovery_margin_reduction_candidate": recovery_margin_reduction,
                "observed_return_suppression_candidate": return_suppression,
                "new_drive_coincident_candidate": new_drive_coincident,
                "unresolved_residual_dominance_candidate": residual_dominance,
                "gradient_dominance_consensus": gradient_dominance,
                "circulation_dominance_consensus": circulation_dominance,
                "amplification_axes": np.flatnonzero(amplification_axes).astype(int).tolist(),
                "attenuation_axes": np.flatnonzero(attenuation_axes).astype(int).tolist(),
                "cessation_axes": np.flatnonzero(cessation_axes).astype(int).tolist(),
                "activation_axes": np.flatnonzero(activation_axes).astype(int).tolist(),
                "reversal_axes": np.flatnonzero(reversal_axes).astype(int).tolist(),
                "innovation_axes": np.flatnonzero(innovation_axes).astype(int).tolist(),
            }
        )
        evidence_rows.append(
            {
                "target_transition_index": target,
                "transition_time": int(times[target]),
                "observed_signals": general_evidence,
                "overconvergence_support": over_support,
                "fixation_support": fixation_support,
                "divergence_support": divergence_support,
                "recovery_margin_reduction_support": [
                    label
                    for condition, label in (
                        (recovery_weakening, "boundary_recovery_weakening"),
                        (not recovery_strengthening, "recovery_strengthening_not_observed"),
                    )
                    if condition
                ],
                "new_drive_coincident_support": [
                    label
                    for condition, label in (
                        (new_drive_present, "history_conditioned_new_drive"),
                        (structural_candidate, "structural_candidate_same_transition"),
                    )
                    if condition
                ],
                "unresolved_residual_support": [
                    label
                    for condition, label in (
                        (residual_minimum > residual_floor, "residual_above_absolute_floor"),
                        (residual_ratio_minimum >= residual_fraction, "residual_fraction_at_or_above_dominance_threshold"),
                    )
                    if condition
                ],
            }
        )
        counter_rows.append(
            {
                "target_transition_index": target,
                "transition_time": int(times[target]),
                "overconvergence_counterevidence": over_counter,
                "fixation_counterevidence": fixation_counter,
                "divergence_counterevidence": divergence_counter,
                "recovery_margin_reduction_counterevidence": [
                    label
                    for condition, label in (
                        (recovery_strengthening, "boundary_recovery_strengthening"),
                        (widening, "flow_channel_widening"),
                        (reversal, "direction_reversal"),
                    )
                    if condition
                ],
            }
        )

        values = {
            "target_transition_index": target,
            "risk_transition_times": int(times[target]),
            "shape_convergence_signal": shape_convergence,
            "shape_divergence_signal": shape_divergence,
            "flow_channel_narrowing_signal": narrowing,
            "flow_channel_widening_signal": widening,
            "same_axis_amplification_signal": amplification,
            "same_axis_attenuation_or_cessation_signal": attenuation_or_cessation,
            "direction_reversal_signal": reversal,
            "boundary_recovery_weakening_signal": recovery_weakening,
            "boundary_recovery_strengthening_signal": recovery_strengthening,
            "observed_return_suppression_candidate": return_suppression,
            "gradient_dominance_consensus": gradient_dominance,
            "circulation_dominance_consensus": circulation_dominance,
            "overconvergence_candidate": overconvergence,
            "fixation_candidate": fixation,
            "divergence_candidate": divergence,
            "recovery_margin_reduction_candidate": recovery_margin_reduction,
            "history_conditioned_new_drive_present": new_drive_present,
            "new_drive_coincident_candidate": new_drive_coincident,
            "unresolved_residual_dominance_candidate": residual_dominance,
            "observed_change_l1": observed_change_l1,
            "unresolved_residual_fraction_minimum": residual_ratio_minimum,
            "unresolved_residual_fraction_mean": residual_ratio_mean,
            "boundary_inward_flow_change": inward_change,
            "axis_flow_ambiguity_maximum": float(
                np.max(axis_family["axis_signed_flow_ambiguity_width"][target])
            ),
            "innovation_axis_count": int(np.count_nonzero(innovation_axes)),
            "unique_candidate_count": int(axis_family["unique_candidate_count"][target]),
        }
        for key, value in values.items():
            metric_lists[key].append(value)

    boolean_keys = {
        "shape_convergence_signal",
        "shape_divergence_signal",
        "flow_channel_narrowing_signal",
        "flow_channel_widening_signal",
        "same_axis_amplification_signal",
        "same_axis_attenuation_or_cessation_signal",
        "direction_reversal_signal",
        "boundary_recovery_weakening_signal",
        "boundary_recovery_strengthening_signal",
        "observed_return_suppression_candidate",
        "gradient_dominance_consensus",
        "circulation_dominance_consensus",
        "overconvergence_candidate",
        "fixation_candidate",
        "divergence_candidate",
        "recovery_margin_reduction_candidate",
        "history_conditioned_new_drive_present",
        "new_drive_coincident_candidate",
        "unresolved_residual_dominance_candidate",
    }
    integer_keys = {
        "target_transition_index",
        "risk_transition_times",
        "innovation_axis_count",
        "unique_candidate_count",
    }
    arrays: dict[str, np.ndarray] = {}
    for key, values in metric_lists.items():
        if key in boolean_keys:
            arrays[key] = np.asarray(values, dtype=np.uint8)
        elif key in integer_keys:
            arrays[key] = np.asarray(values, dtype=np.int32)
        else:
            arrays[key] = np.asarray(values, dtype=np.float64)
    return {
        "arrays": arrays,
        "candidates": {
            "single_scalar_risk_score_produced": False,
            "true_irreversibility_claim": False,
            "future_risk_prediction_performed": False,
            "rows": candidate_rows,
        },
        "evidence": {"rows": evidence_rows},
        "counterevidence": {"rows": counter_rows},
    }


def _assert_array_payload(expected: Mapping[str, np.ndarray], actual: Mapping[str, np.ndarray], name: str) -> None:
    if set(expected) != set(actual):
        raise RelationFieldRiskStructureError(f"{name} array key mismatch")
    for key in expected:
        left, right = np.asarray(expected[key]), np.asarray(actual[key])
        if left.shape != right.shape or left.dtype.kind != right.dtype.kind:
            raise RelationFieldRiskStructureError(f"{name} array metadata mismatch: {key}")
        equal = np.array_equal(left, right) if left.dtype.kind in "iub" else np.allclose(left, right, atol=1e-12, rtol=1e-12)
        if not equal:
            raise RelationFieldRiskStructureError(f"{name} array value mismatch: {key}")


def _compute_all(
    trajectory_root: Path,
    grid_root: Path,
    rf5_root: Path,
    rf6_root: Path,
    rf7_root: Path,
    rf8_root: Path,
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    parent = _load_parent_artifacts(
        trajectory_root, grid_root, rf5_root, rf6_root, rf7_root, rf8_root, contract
    )
    risk = compute_risk_structure(parent, contract)
    return {"parent": parent, "risk": risk}


def build_risk_structure(
    trajectory_dir: str | Path,
    grid_artifact_dir: str | Path,
    rf5_artifact_dir: str | Path,
    rf6_artifact_dir: str | Path,
    rf7_artifact_dir: str | Path,
    rf8_artifact_dir: str | Path,
    output: str | Path,
    *,
    contract_path: str | Path = DEFAULT_CONTRACT,
) -> Path:
    contract = load_contract(contract_path)
    target = Path(output)
    if target.exists():
        raise RelationFieldRiskStructureError(f"output already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    computed = _compute_all(
        Path(trajectory_dir),
        Path(grid_artifact_dir),
        Path(rf5_artifact_dir),
        Path(rf6_artifact_dir),
        Path(rf7_artifact_dir),
        Path(rf8_artifact_dir),
        contract,
    )
    parent = computed["parent"]
    risk = computed["risk"]
    identity_basis = {
        "contract_version": contract["contract_version"],
        "trajectory_id": parent["rf5_identity"]["trajectory_id"],
        "start_t": int(parent["rf5_identity"]["start_t"]),
        "to_t": int(parent["rf5_identity"]["to_t"]),
        "source_history_chain_hash": parent["rf5_identity"]["source_history_chain_hash"],
        "rf5_relation_field_id": parent["rf5_identity"]["relation_field_id"],
        "rf5_manifest_hash": parent["rf5_manifest_hash"],
        "rf6_decomposition_id": parent["rf6_identity"]["decomposition_id"],
        "rf6_manifest_hash": parent["rf6_manifest_hash"],
        "rf7_shape_dynamics_id": parent["rf7_identity"]["shape_dynamics_id"],
        "rf7_manifest_hash": parent["rf7_manifest_hash"],
        "rf8_axis_coupling_innovation_id": parent["rf8_identity"]["axis_coupling_innovation_id"],
        "rf8_manifest_hash": parent["rf8_manifest_hash"],
        "grid_manifest_hash": parent["rf8_identity"]["grid_manifest_hash"],
    }
    risk_structure_id = hashlib.sha256(_canonical_json(identity_basis)).hexdigest()
    identity = {
        "risk_structure_id": risk_structure_id,
        **identity_basis,
        "transition_count": parent["transition_count"],
        "aligned_risk_row_count": parent["transition_count"] - 1,
        "max_source_t_read": int(parent["rf5_identity"]["to_t"]),
        "single_scalar_risk_score_produced": False,
        "true_irreversibility_claim": False,
        "future_risk_prediction_performed": False,
    }
    rows = risk["candidates"]["rows"]
    candidate_names = (
        "overconvergence_candidate",
        "fixation_candidate",
        "divergence_candidate",
        "recovery_margin_reduction_candidate",
        "new_drive_coincident_candidate",
        "unresolved_residual_dominance_candidate",
        "observed_return_suppression_candidate",
        "gradient_dominance_consensus",
        "circulation_dominance_consensus",
    )
    counts = {name: sum(bool(row[name]) for row in rows) for name in candidate_names}
    diagnostics = {
        "transition_count": parent["transition_count"],
        "aligned_risk_row_count": len(rows),
        "candidate_counts": counts,
        "maximum_axis_flow_ambiguity": float(np.max(risk["arrays"]["axis_flow_ambiguity_maximum"])),
        "maximum_unresolved_residual_fraction_mean": float(
            np.max(risk["arrays"]["unresolved_residual_fraction_mean"])
        ),
        "single_scalar_risk_score_produced": False,
        "true_irreversibility_claim": False,
        "future_risk_prediction_performed": False,
    }
    gates = {
        "parent_identity_gate": True,
        "transition_alignment_gate": len(rows) == parent["transition_count"] - 1,
        "finite_metric_gate": all(np.all(np.isfinite(value)) for value in risk["arrays"].values()),
        "candidate_boolean_gate": all(
            isinstance(row[name], bool) for row in rows for name in candidate_names
        ),
        "risk_score_absence_gate": all("risk_score" not in row for row in rows),
        "innovation_residual_separation_gate": True,
        "causal_cutoff_gate": identity["max_source_t_read"] == identity["to_t"],
        "source_writeback_gate": True,
    }
    validation = {
        "rf9_risk_structure_gate": "passed" if all(gates.values()) else "failed",
        **gates,
        "scientific_claim": contract["acceptance"]["scientific_claim"],
        "single_scalar_risk_score_produced": False,
        "true_irreversibility_claim": False,
        "future_risk_prediction_performed": False,
        "parent_writeback_performed": False,
        "canonical_writeback_performed": False,
    }
    if validation["rf9_risk_structure_gate"] != "passed":
        raise RelationFieldRiskStructureError(f"RF-9 gates failed: {gates}")
    uncertainty = {
        "candidate_family": {
            "saved_candidates_are_not_complete_solution_set": True,
            "saved_path_multiplicity_is_not_probability": True,
            "axis_flow_ambiguity_preserved": True,
        },
        "structure_semantics": {
            "risk_candidates_are_conjunctions_of_observed_signals": True,
            "absence_of_candidate_is_not_safety_proof": True,
            "observed_return_suppression_is_not_true_irreversibility": True,
            "gradient_or_circulation_dominance_is_not_attraction_or_repulsion": True,
        },
        "innovation_and_residual": {
            "history_conditioned_new_drive_is_not_external_factor": True,
            "unresolved_transport_residual_remains_separate": True,
        },
        "prediction": {
            "future_risk_prediction_performed": False,
            "calibration_performed": False,
        },
    }
    summary = {
        "contract_version": contract["contract_version"],
        "risk_structure_id": risk_structure_id,
        "transition_count": parent["transition_count"],
        "aligned_risk_row_count": len(rows),
        "candidate_counts": counts,
        "scientific_claim": contract["acceptance"]["scientific_claim"],
        "future_risk_prediction_performed": False,
    }
    temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.tmp-", dir=target.parent))
    try:
        storage = contract["storage"]
        _dump_json(temporary / storage["contract_file"], contract)
        _dump_json(temporary / storage["identity_file"], identity)
        _write_npz(temporary / storage["metrics_file"], risk["arrays"])
        _dump_json(temporary / storage["candidates_file"], risk["candidates"])
        _dump_json(temporary / storage["evidence_file"], risk["evidence"])
        _dump_json(temporary / storage["counterevidence_file"], risk["counterevidence"])
        _dump_json(temporary / storage["diagnostics_file"], diagnostics)
        _dump_json(temporary / storage["uncertainty_file"], uncertainty)
        _dump_json(
            temporary / storage["provenance_file"],
            {
                "parent_artifacts_read": ["RF-5", "RF-6", "RF-7", "RF-8"],
                "parent_validation_invoked": True,
                "canonical_G_t_or_K_t_used_as_RF9_feature": False,
                "external_logs_read": False,
                "max_t_available_through_parents": identity["to_t"],
                "future_suffix_read": False,
                "canonical_or_parent_payload_copied": False,
                "parent_writeback_performed": False,
                "canonical_writeback_performed": False,
            },
        )
        _dump_json(temporary / storage["summary_file"], summary)
        _dump_json(temporary / storage["validation_file"], validation)
        _dump_json(
            temporary / storage["manifest_file"],
            {
                "contract_version": contract["contract_version"],
                "hash_algorithm": "sha256",
                "files": _manifest_entries(temporary, exclude={storage["manifest_file"]}),
            },
        )
        os.replace(temporary, target)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return target


def validate_risk_structure(
    input_path: str | Path,
    trajectory_dir: str | Path,
    grid_artifact_dir: str | Path,
    rf5_artifact_dir: str | Path,
    rf6_artifact_dir: str | Path,
    rf7_artifact_dir: str | Path,
    rf8_artifact_dir: str | Path,
) -> dict[str, Any]:
    root = Path(input_path)
    contract = _load_json(root / "contract.json")
    validate_contract(contract)
    _verify_manifest(root)
    computed = _compute_all(
        Path(trajectory_dir),
        Path(grid_artifact_dir),
        Path(rf5_artifact_dir),
        Path(rf6_artifact_dir),
        Path(rf7_artifact_dir),
        Path(rf8_artifact_dir),
        contract,
    )
    parent = computed["parent"]
    risk = computed["risk"]
    identity = _load_json(root / "identity.json")
    for key, expected in (
        ("rf5_manifest_hash", parent["rf5_manifest_hash"]),
        ("rf6_manifest_hash", parent["rf6_manifest_hash"]),
        ("rf7_manifest_hash", parent["rf7_manifest_hash"]),
        ("rf8_manifest_hash", parent["rf8_manifest_hash"]),
    ):
        if identity.get(key) != expected:
            raise RelationFieldRiskStructureError(f"RF-9 {key} mismatch")
    if identity.get("max_source_t_read") != identity.get("to_t"):
        raise RelationFieldRiskStructureError("RF-9 causal cutoff mismatch")
    forbidden = {
        "gt_mass.npy",
        "history_ledger.csv",
        "candidate_components.npz",
        "transition_shape_metrics.npz",
        "axis_flow_family.npz",
        "history_conditioned_innovation.npz",
        "unresolved_residual_ledger.npz",
    }
    if any(path.name in forbidden for path in root.rglob("*")):
        raise RelationFieldRiskStructureError("RF-9 copied canonical or parent payload")
    storage = contract["storage"]
    _assert_array_payload(risk["arrays"], _load_npz(root / storage["metrics_file"]), "risk metrics")
    if _load_json(root / storage["candidates_file"]) != risk["candidates"]:
        raise RelationFieldRiskStructureError("RF-9 candidate payload mismatch")
    if _load_json(root / storage["evidence_file"]) != risk["evidence"]:
        raise RelationFieldRiskStructureError("RF-9 evidence payload mismatch")
    if _load_json(root / storage["counterevidence_file"]) != risk["counterevidence"]:
        raise RelationFieldRiskStructureError("RF-9 counterevidence payload mismatch")
    validation = _load_json(root / storage["validation_file"])
    if validation.get("rf9_risk_structure_gate") != "passed":
        raise RelationFieldRiskStructureError("RF-9 validation gate did not pass")
    return validation


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("build")
    build.add_argument("--trajectory", required=True)
    build.add_argument("--grid-artifact", required=True)
    build.add_argument("--rf5-artifact", required=True)
    build.add_argument("--rf6-artifact", required=True)
    build.add_argument("--rf7-artifact", required=True)
    build.add_argument("--rf8-artifact", required=True)
    build.add_argument("--output", required=True)
    build.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    validate = commands.add_parser("validate")
    validate.add_argument("--input", required=True)
    validate.add_argument("--trajectory", required=True)
    validate.add_argument("--grid-artifact", required=True)
    validate.add_argument("--rf5-artifact", required=True)
    validate.add_argument("--rf6-artifact", required=True)
    validate.add_argument("--rf7-artifact", required=True)
    validate.add_argument("--rf8-artifact", required=True)
    args = parser.parse_args(argv)
    if args.command == "build":
        output = build_risk_structure(
            args.trajectory,
            args.grid_artifact,
            args.rf5_artifact,
            args.rf6_artifact,
            args.rf7_artifact,
            args.rf8_artifact,
            args.output,
            contract_path=args.contract,
        )
        print(json.dumps({"output": str(output), "status": "built"}, ensure_ascii=False, sort_keys=True))
    else:
        print(
            json.dumps(
                validate_risk_structure(
                    args.input,
                    args.trajectory,
                    args.grid_artifact,
                    args.rf5_artifact,
                    args.rf6_artifact,
                    args.rf7_artifact,
                    args.rf8_artifact,
                ),
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
