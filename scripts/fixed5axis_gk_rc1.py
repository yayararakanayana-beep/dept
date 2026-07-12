"""Fixed five-axis G_t / K_t foundation (RC1).

This module converts existing PseudoReality v3.3 continuous-trajectory state
snapshots into a canonical fixed-grid G_t archive and an append-only K_t history
ledger. It deliberately does not construct a relation field, classify a game
structure, predict risk, or connect an action module.

Canonical data:
- G_t: the full (5, 5, 5, 5, 5) float64 probability mass distribution.
- K_t: an ordered ledger referencing every canonical G_t frame.

Derived transition metrics and history windows are recomputable convenience
layers. They are never treated as canonical history.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONTRACT = ROOT / "configs" / "fixed5axis_gk_rc1_contract.json"
AXIS_NAMES = (
    "resource_slack",
    "information_quality",
    "pressure",
    "exploration_room",
    "reversibility",
)
AXIS_BINS = (0.0, 0.25, 0.5, 0.75, 1.0)
GT_SHAPE = (5, 5, 5, 5, 5)
GT_DTYPE = np.dtype("<f8")
GENESIS_TOKEN = b"fixed5axis_gk_rc1_history_genesis"
_FORBIDDEN_OUTPUT_NAMES = {"truth.jsonl", "summary.json", "metrics.jsonl"}


class Fixed5AxisGKError(ValueError):
    """Raised when a fixed-five-axis G/K contract is violated."""


def _json_dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _json_load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise Fixed5AxisGKError(f"{path}:{line_number} must contain a JSON object")
            rows.append(value)
    return rows


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _safe_relative_path(value: str, *, field_name: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise Fixed5AxisGKError(f"{field_name} must remain inside the source trajectory directory")
    return path


def load_contract(path: str | Path = DEFAULT_CONTRACT) -> dict[str, Any]:
    contract = _json_load(Path(path))
    validate_contract(contract)
    return contract


def validate_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("contract_version") != "fixed5axis_gk_rc1":
        raise Fixed5AxisGKError("unsupported contract_version")
    axes = contract.get("axes")
    if not isinstance(axes, Mapping):
        raise Fixed5AxisGKError("contract.axes must be an object")
    if tuple(axes.get("order", ())) != AXIS_NAMES:
        raise Fixed5AxisGKError("fixed axis order does not match RC1")
    if tuple(float(x) for x in axes.get("bins", ())) != AXIS_BINS:
        raise Fixed5AxisGKError("fixed axis bins do not match RC1")
    if tuple(int(x) for x in axes.get("shape", ())) != GT_SHAPE:
        raise Fixed5AxisGKError("fixed G_t shape does not match RC1")
    if int(axes.get("cell_count", -1)) != int(np.prod(GT_SHAPE)):
        raise Fixed5AxisGKError("fixed cell_count does not match RC1")
    gt = contract.get("gt")
    if not isinstance(gt, Mapping):
        raise Fixed5AxisGKError("contract.gt must be an object")
    if gt.get("canonical_dtype") != "float64":
        raise Fixed5AxisGKError("RC1 canonical dtype must be float64")
    if gt.get("phase") != "pre_transition":
        raise Fixed5AxisGKError("RC1 G_t phase must be pre_transition")
    if gt.get("source_mode") != "reference_full":
        raise Fixed5AxisGKError("RC1 source_mode must be reference_full")


def validate_distribution(distribution: np.ndarray, contract: Mapping[str, Any]) -> np.ndarray:
    """Validate without clipping or renormalizing and return canonical little-endian float64."""

    validate_contract(contract)
    array = np.asarray(distribution)
    if array.shape != GT_SHAPE:
        raise Fixed5AxisGKError(f"distribution shape {array.shape} != {GT_SHAPE}")
    canonical = np.ascontiguousarray(array, dtype=GT_DTYPE)
    if not np.all(np.isfinite(canonical)):
        raise Fixed5AxisGKError("distribution contains non-finite values")
    negative_tolerance = float(contract["gt"]["negative_tolerance"])
    if float(canonical.min()) < -negative_tolerance:
        raise Fixed5AxisGKError("distribution contains negative mass")
    mass_tolerance = float(contract["gt"]["mass_tolerance"])
    total = float(canonical.sum(dtype=np.float64))
    if abs(total - 1.0) > mass_tolerance:
        raise Fixed5AxisGKError(f"distribution mass {total:.17g} does not sum to one")
    return canonical


def compute_gt_hash(
    *,
    contract_version: str,
    trajectory_id: str,
    t: int,
    distribution: np.ndarray,
    source_state_hash: str,
) -> str:
    array = np.ascontiguousarray(distribution, dtype=GT_DTYPE)
    digest = hashlib.sha256()
    digest.update(contract_version.encode("utf-8"))
    digest.update(b"\0")
    digest.update(trajectory_id.encode("utf-8"))
    digest.update(b"\0")
    digest.update(str(int(t)).encode("ascii"))
    digest.update(b"\0")
    digest.update(_canonical_json_bytes({"axes": AXIS_NAMES, "bins": AXIS_BINS}))
    digest.update(b"\0")
    digest.update(array.tobytes(order="C"))
    digest.update(b"\0")
    digest.update(source_state_hash.encode("ascii"))
    return digest.hexdigest()


def compute_history_chain_hash(previous_chain_hash: str, gt_hash: str, t: int) -> str:
    digest = hashlib.sha256()
    digest.update(previous_chain_hash.encode("ascii"))
    digest.update(b"\0")
    digest.update(gt_hash.encode("ascii"))
    digest.update(b"\0")
    digest.update(str(int(t)).encode("ascii"))
    return digest.hexdigest()


def initial_history_chain_hash() -> str:
    return hashlib.sha256(GENESIS_TOKEN).hexdigest()


@dataclass
class HistoryAccumulator:
    """In-memory append-only builder for one canonical trajectory history."""

    contract: Mapping[str, Any]
    trajectory_id: str
    masses: list[np.ndarray] = field(default_factory=list)
    ledger_rows: list[dict[str, Any]] = field(default_factory=list)
    _previous_gt_hash: str = ""
    _chain_hash: str = field(default_factory=initial_history_chain_hash)

    def append(
        self,
        *,
        t: int,
        phase: str,
        distribution: np.ndarray,
        source_state_ref: str,
        source_state_hash: str,
    ) -> None:
        if isinstance(t, bool) or not isinstance(t, int) or t < 0:
            raise Fixed5AxisGKError("t must be a non-negative integer")
        if phase != self.contract["gt"]["phase"]:
            raise Fixed5AxisGKError(f"phase {phase!r} is not the RC1 pre-transition phase")
        _safe_relative_path(source_state_ref, field_name="source_state_ref")
        if len(source_state_hash) != 64 or any(ch not in "0123456789abcdef" for ch in source_state_hash):
            raise Fixed5AxisGKError("source_state_hash must be a lowercase SHA-256 digest")

        if self.ledger_rows:
            previous_t = int(self.ledger_rows[-1]["t"])
            if t == previous_t:
                raise Fixed5AxisGKError(f"duplicate G_t time {t}")
            if t < previous_t:
                raise Fixed5AxisGKError(f"out-of-order G_t time {t} after {previous_t}")
            if t != previous_t + 1:
                raise Fixed5AxisGKError(f"gap in canonical history: {previous_t} -> {t}")
            continuity_status = "continuous"
            delta_t = t - previous_t
        else:
            continuity_status = "initial"
            delta_t = 0

        canonical = validate_distribution(distribution, self.contract)
        gt_hash = compute_gt_hash(
            contract_version=str(self.contract["contract_version"]),
            trajectory_id=self.trajectory_id,
            t=t,
            distribution=canonical,
            source_state_hash=source_state_hash,
        )
        chain_hash = compute_history_chain_hash(self._chain_hash, gt_hash, t)
        row = {
            "trajectory_id": self.trajectory_id,
            "t": t,
            "phase": phase,
            "gt_row_index": len(self.masses),
            "gt_hash": gt_hash,
            "previous_gt_hash": self._previous_gt_hash,
            "history_chain_hash": chain_hash,
            "delta_t": delta_t,
            "continuity_status": continuity_status,
            "source_state_ref": source_state_ref,
            "source_state_hash": source_state_hash,
        }
        self.masses.append(canonical.copy())
        self.ledger_rows.append(row)
        self._previous_gt_hash = gt_hash
        self._chain_hash = chain_hash

    def stacked_mass(self) -> np.ndarray:
        if not self.masses:
            raise Fixed5AxisGKError("cannot finalize an empty G_t history")
        return np.ascontiguousarray(np.stack(self.masses, axis=0), dtype=GT_DTYPE)


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _canonical_manifest(root: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "manifest.json" or "derived" in path.relative_to(root).parts:
            continue
        item: dict[str, Any] = {
            "relative_path": path.relative_to(root).as_posix(),
            "sha256": _file_sha256(path),
            "size_bytes": path.stat().st_size,
        }
        if path.suffix == ".npy":
            array = np.load(path, mmap_mode="r", allow_pickle=False)
            item["array_shape"] = list(array.shape)
            item["array_dtype"] = str(array.dtype)
        elif path.suffix == ".csv":
            with path.open("r", encoding="utf-8", newline="") as handle:
                item["row_count"] = max(sum(1 for _ in handle) - 1, 0)
        elif path.suffix == ".jsonl":
            with path.open("r", encoding="utf-8") as handle:
                item["row_count"] = sum(1 for line in handle if line.strip())
        files.append(item)
    return {
        "contract_version": "fixed5axis_gk_rc1",
        "canonical_manifest_excludes_derived": True,
        "file_count": len(files),
        "total_size_bytes": sum(int(item["size_bytes"]) for item in files),
        "files": files,
    }


def _source_config_hash(metadata: Mapping[str, Any]) -> str:
    value = {
        "world_module": metadata.get("world_module"),
        "world_class": metadata.get("world_class"),
        "world_version": metadata.get("world_version"),
        "config_version": metadata.get("config_version"),
        "initial_state_id": metadata.get("initial_state_id"),
    }
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _build_trajectory_into(
    source_trajectory_dir: Path,
    target_trajectory_dir: Path,
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    metadata_path = source_trajectory_dir / "metadata.json"
    steps_path = source_trajectory_dir / "steps.jsonl"
    if not metadata_path.is_file() or not steps_path.is_file():
        raise Fixed5AxisGKError("source trajectory requires metadata.json and steps.jsonl")

    source_files_read = ["metadata.json", "steps.jsonl"]
    metadata = _json_load(metadata_path)
    steps = _read_jsonl(steps_path)
    if not isinstance(metadata, Mapping):
        raise Fixed5AxisGKError("metadata.json must contain an object")
    trajectory_id = str(metadata.get("trajectory_id", ""))
    if not trajectory_id:
        raise Fixed5AxisGKError("metadata.trajectory_id is required")
    if not steps:
        raise Fixed5AxisGKError("steps.jsonl is empty")
    expected_steps = int(metadata.get("total_steps", len(steps) - 1)) + 1
    if len(steps) != expected_steps:
        raise Fixed5AxisGKError(f"step count {len(steps)} != expected {expected_steps}")

    accumulator = HistoryAccumulator(contract=contract, trajectory_id=trajectory_id)
    external_rows: list[dict[str, Any]] = []
    action_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    source_hashes_before: dict[str, str] = {}

    for expected_t, step in enumerate(steps):
        t = step.get("step")
        if t != expected_t:
            raise Fixed5AxisGKError(f"steps.jsonl must be ordered and contiguous; expected {expected_t}, got {t}")
        phase = str(step.get("phase", ""))
        state_ref = str(step.get("state_ref", ""))
        state_rel = _safe_relative_path(state_ref, field_name="state_ref")
        state_path = source_trajectory_dir / state_rel
        if not state_path.is_file():
            raise Fixed5AxisGKError(f"missing source state file {state_ref}")
        source_hash_before = _file_sha256(state_path)
        source_hashes_before[state_ref] = source_hash_before
        source_files_read.append(state_rel.as_posix())
        with np.load(state_path, allow_pickle=False) as bundle:
            if "distribution" not in bundle.files:
                raise Fixed5AxisGKError(f"{state_ref} does not contain distribution")
            distribution = np.asarray(bundle["distribution"])
        source_hash_after = _file_sha256(state_path)
        if source_hash_before != source_hash_after:
            raise Fixed5AxisGKError(f"source state changed while reading: {state_ref}")

        accumulator.append(
            t=int(t),
            phase=phase,
            distribution=distribution,
            source_state_ref=state_ref,
            source_state_hash=source_hash_before,
        )
        external_rows.append(
            {
                "trajectory_id": trajectory_id,
                "t": int(t),
                "observed_external_input": step.get("observed_external_input"),
            }
        )
        action_rows.append(
            {
                "trajectory_id": trajectory_id,
                "t": int(t),
                "observed_action": step.get("observed_action"),
            }
        )
        event_rows.append(
            {
                "trajectory_id": trajectory_id,
                "t": int(t),
                "observed_events": step.get("observed_events", []),
            }
        )

    if target_trajectory_dir.exists() and any(target_trajectory_dir.iterdir()):
        raise Fixed5AxisGKError(f"target trajectory directory is not empty: {target_trajectory_dir}")
    target_trajectory_dir.mkdir(parents=True, exist_ok=True)
    np.save(target_trajectory_dir / str(contract["storage"]["gt_file"]), accumulator.stacked_mass(), allow_pickle=False)
    ledger_fields = [
        "trajectory_id",
        "t",
        "phase",
        "gt_row_index",
        "gt_hash",
        "previous_gt_hash",
        "history_chain_hash",
        "delta_t",
        "continuity_status",
        "source_state_ref",
        "source_state_hash",
    ]
    _write_csv(
        target_trajectory_dir / str(contract["storage"]["history_ledger_file"]),
        accumulator.ledger_rows,
        ledger_fields,
    )
    _write_jsonl(target_trajectory_dir / str(contract["storage"]["external_log_file"]), external_rows)
    _write_jsonl(target_trajectory_dir / str(contract["storage"]["action_log_file"]), action_rows)
    _write_jsonl(target_trajectory_dir / str(contract["storage"]["event_log_file"]), event_rows)

    provenance = {
        "contract_version": contract["contract_version"],
        "axis_order": list(AXIS_NAMES),
        "axis_bins": list(AXIS_BINS),
        "gt_shape": list(GT_SHAPE),
        "gt_dtype": "float64",
        "gt_phase": contract["gt"]["phase"],
        "source_mode": contract["gt"]["source_mode"],
        "trajectory_id": trajectory_id,
        "world_module": metadata.get("world_module"),
        "world_class": metadata.get("world_class"),
        "world_version": metadata.get("world_version"),
        "world_config_hash": _source_config_hash(metadata),
        "dataset_split": metadata.get("dataset_split"),
        "seed": metadata.get("seed"),
        "scenario_id": metadata.get("scenario_id"),
        "total_gt_frames": len(accumulator.ledger_rows),
        "source_files_read": source_files_read,
        "forbidden_source_files_read": sorted(set(source_files_read) & _FORBIDDEN_OUTPUT_NAMES),
        "source_writeback_performed": False,
        "canonical_history_is_complete_gt_sequence": True,
        "derived_layers_are_canonical": False,
    }
    _json_dump(target_trajectory_dir / str(contract["storage"]["provenance_file"]), provenance)
    _json_dump(
        target_trajectory_dir / "derived" / "derivation_registry.json",
        {
            "contract_version": contract["contract_version"],
            "canonical": False,
            "entries": [],
            "policy": "delete_and_recompute_from_gt_mass_and_history_ledger",
        },
    )
    manifest = _canonical_manifest(target_trajectory_dir)
    _json_dump(target_trajectory_dir / str(contract["storage"]["manifest_file"]), manifest)
    validation = validate_trajectory_artifact(target_trajectory_dir, contract)
    _json_dump(target_trajectory_dir / "validation.json", validation)
    manifest = _canonical_manifest(target_trajectory_dir)
    _json_dump(target_trajectory_dir / str(contract["storage"]["manifest_file"]), manifest)
    validation = validate_trajectory_artifact(target_trajectory_dir, contract)
    _json_dump(target_trajectory_dir / "validation.json", validation)

    for state_ref, before_hash in source_hashes_before.items():
        if _file_sha256(source_trajectory_dir / state_ref) != before_hash:
            raise Fixed5AxisGKError(f"source writeback detected after build: {state_ref}")
    return validation


def build_trajectory(
    source_trajectory_dir: str | Path,
    output_root: str | Path,
    contract: Mapping[str, Any] | None = None,
) -> Path:
    """Build one trajectory atomically under output_root/trajectories/<trajectory_id>."""

    active_contract = dict(contract or load_contract())
    validate_contract(active_contract)
    source = Path(source_trajectory_dir)
    metadata = _json_load(source / "metadata.json")
    trajectory_id = str(metadata.get("trajectory_id", ""))
    if not trajectory_id:
        raise Fixed5AxisGKError("metadata.trajectory_id is required")
    output = Path(output_root)
    target = output / "trajectories" / trajectory_id
    if target.exists():
        raise Fixed5AxisGKError(f"append-only target already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{trajectory_id}.", dir=target.parent))
    try:
        _build_trajectory_into(source, temporary, active_contract)
        os.replace(temporary, target)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return target


def build_corpus(
    source_corpus_dir: str | Path,
    output_dir: str | Path,
    contract_path: str | Path = DEFAULT_CONTRACT,
) -> Path:
    contract = load_contract(contract_path)
    source_root = Path(source_corpus_dir)
    source_trajectories = sorted((source_root / "trajectories").glob("*"))
    source_trajectories = [path for path in source_trajectories if path.is_dir()]
    if not source_trajectories:
        raise Fixed5AxisGKError("source corpus contains no trajectory directories")
    output = Path(output_dir)
    if output.exists():
        raise Fixed5AxisGKError(f"append-only corpus target already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    records: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_source_keys: set[tuple[str, Any]] = set()
    try:
        _json_dump(temporary / "contract.json", contract)
        for source in source_trajectories:
            metadata = _json_load(source / "metadata.json")
            trajectory_id = str(metadata.get("trajectory_id", ""))
            if trajectory_id in seen_ids:
                raise Fixed5AxisGKError(f"duplicate trajectory_id {trajectory_id}")
            seen_ids.add(trajectory_id)
            source_key = (str(metadata.get("scenario_id")), metadata.get("seed"))
            if source_key in seen_source_keys:
                raise Fixed5AxisGKError(f"duplicate scenario/seed source key {source_key}")
            seen_source_keys.add(source_key)
            target = temporary / "trajectories" / trajectory_id
            validation = _build_trajectory_into(source, target, contract)
            records.append(
                {
                    "trajectory_id": trajectory_id,
                    "dataset_split": metadata.get("dataset_split"),
                    "scenario_id": metadata.get("scenario_id"),
                    "seed": metadata.get("seed"),
                    "total_gt_frames": validation["total_gt_frames"],
                    "representation_status": validation["status"],
                }
            )
        split_counts: dict[str, int] = {}
        for record in records:
            split = str(record["dataset_split"])
            split_counts[split] = split_counts.get(split, 0) + 1
        _json_dump(
            temporary / "dataset_manifest.json",
            {
                "contract_version": contract["contract_version"],
                "trajectory_count": len(records),
                "split_counts": split_counts,
                "trajectories": records,
                "prediction_or_relation_field_built": False,
                "research_adoption_not_yet_claimed": True,
            },
        )
        _json_dump(temporary / "manifest.json", _canonical_manifest(temporary))
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return output


def validate_trajectory_artifact(
    trajectory_dir: str | Path,
    contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    active_contract = dict(contract or load_contract())
    validate_contract(active_contract)
    directory = Path(trajectory_dir)
    storage = active_contract["storage"]
    mass_path = directory / str(storage["gt_file"])
    ledger_path = directory / str(storage["history_ledger_file"])
    provenance_path = directory / str(storage["provenance_file"])
    for path in (mass_path, ledger_path, provenance_path):
        if not path.is_file():
            raise Fixed5AxisGKError(f"missing canonical artifact file {path.name}")
    if any((directory / name).exists() for name in _FORBIDDEN_OUTPUT_NAMES):
        raise Fixed5AxisGKError("validation truth or prediction artifacts leaked into canonical trajectory output")

    mass = np.load(mass_path, mmap_mode="r", allow_pickle=False)
    if mass.ndim != 6 or tuple(mass.shape[1:]) != GT_SHAPE:
        raise Fixed5AxisGKError(f"gt_mass.npy shape {mass.shape} is not (T, {GT_SHAPE})")
    if mass.dtype != np.dtype("float64"):
        raise Fixed5AxisGKError(f"gt_mass.npy dtype {mass.dtype} != float64")
    ledger = _read_csv(ledger_path)
    provenance = _json_load(provenance_path)
    if len(ledger) != mass.shape[0]:
        raise Fixed5AxisGKError("history ledger row count does not match G_t frame count")
    if tuple(provenance.get("axis_order", ())) != AXIS_NAMES:
        raise Fixed5AxisGKError("provenance axis order mismatch")
    if tuple(float(x) for x in provenance.get("axis_bins", ())) != AXIS_BINS:
        raise Fixed5AxisGKError("provenance axis bins mismatch")
    if provenance.get("forbidden_source_files_read"):
        raise Fixed5AxisGKError("forbidden source files were read")

    previous_gt_hash = ""
    chain_hash = initial_history_chain_hash()
    trajectory_id: str | None = None
    for index, row in enumerate(ledger):
        if int(row["gt_row_index"]) != index:
            raise Fixed5AxisGKError("gt_row_index is not contiguous")
        t = int(row["t"])
        if t != index:
            raise Fixed5AxisGKError("RC1 trajectory time must start at zero and remain contiguous")
        if row["phase"] != active_contract["gt"]["phase"]:
            raise Fixed5AxisGKError("history ledger contains a non-pre-transition G_t")
        if row["continuity_status"] != ("initial" if index == 0 else "continuous"):
            raise Fixed5AxisGKError("history continuity status mismatch")
        if row["previous_gt_hash"] != previous_gt_hash:
            raise Fixed5AxisGKError("previous_gt_hash chain mismatch")
        current_trajectory_id = row["trajectory_id"]
        trajectory_id = trajectory_id or current_trajectory_id
        if current_trajectory_id != trajectory_id:
            raise Fixed5AxisGKError("multiple trajectory IDs in one K_t ledger")
        canonical = validate_distribution(np.asarray(mass[index]), active_contract)
        expected_gt_hash = compute_gt_hash(
            contract_version=str(active_contract["contract_version"]),
            trajectory_id=current_trajectory_id,
            t=t,
            distribution=canonical,
            source_state_hash=row["source_state_hash"],
        )
        if row["gt_hash"] != expected_gt_hash:
            raise Fixed5AxisGKError(f"G_t hash mismatch at t={t}")
        chain_hash = compute_history_chain_hash(chain_hash, expected_gt_hash, t)
        if row["history_chain_hash"] != chain_hash:
            raise Fixed5AxisGKError(f"history chain hash mismatch at t={t}")
        previous_gt_hash = expected_gt_hash

    log_counts: dict[str, int] = {}
    for key in ("external_log_file", "action_log_file", "event_log_file"):
        path = directory / str(storage[key])
        if not path.is_file():
            raise Fixed5AxisGKError(f"missing separate observed log {path.name}")
        count = len(_read_jsonl(path))
        if count != len(ledger):
            raise Fixed5AxisGKError(f"{path.name} row count does not match K_t")
        log_counts[path.name] = count

    return {
        "contract_version": active_contract["contract_version"],
        "trajectory_id": trajectory_id,
        "total_gt_frames": len(ledger),
        "gt_shape": list(mass.shape),
        "gt_dtype": str(mass.dtype),
        "axis_contract_exact": True,
        "mass_validation": "passed",
        "hash_validation": "passed",
        "history_chain_validation": "passed",
        "continuity_validation": "passed",
        "truth_isolation": "passed",
        "observed_log_counts": log_counts,
        "representation_hard_gate": "passed",
        "research_external_response_gate": "not_evaluated",
        "research_history_value_gate": "not_evaluated",
        "research_holdout_gate": "not_evaluated",
        "adoption_judgement": "B_limited_adoption_pending_research_gates",
        "status": "valid",
    }


def load_history_window(
    trajectory_dir: str | Path,
    *,
    last_n: int | None = None,
    start_t: int | None = None,
    end_t: int | None = None,
    contract: Mapping[str, Any] | None = None,
) -> tuple[np.ndarray, list[dict[str, str]]]:
    """Read a recomputable K_t window without modifying canonical files."""

    active_contract = dict(contract or load_contract())
    directory = Path(trajectory_dir)
    mass = np.load(directory / str(active_contract["storage"]["gt_file"]), mmap_mode="r", allow_pickle=False)
    ledger = _read_csv(directory / str(active_contract["storage"]["history_ledger_file"]))
    if last_n is not None and (start_t is not None or end_t is not None):
        raise Fixed5AxisGKError("last_n cannot be combined with start_t/end_t")
    if last_n is not None:
        if isinstance(last_n, bool) or not isinstance(last_n, int) or last_n <= 0:
            raise Fixed5AxisGKError("last_n must be a positive integer")
        start_index = max(0, len(ledger) - last_n)
        end_index = len(ledger)
    else:
        start_value = 0 if start_t is None else int(start_t)
        end_value = len(ledger) - 1 if end_t is None else int(end_t)
        if start_value < 0 or end_value < start_value or end_value >= len(ledger):
            raise Fixed5AxisGKError("invalid history window bounds")
        start_index = start_value
        end_index = end_value + 1
    return np.asarray(mass[start_index:end_index], dtype=GT_DTYPE).copy(), ledger[start_index:end_index]


def _entropy(distribution: np.ndarray) -> float:
    p = np.asarray(distribution, dtype=np.float64).ravel()
    mask = p > 0.0
    return -float(np.sum(p[mask] * np.log(p[mask])))


def _js_distance(left: np.ndarray, right: np.ndarray) -> float:
    p = np.asarray(left, dtype=np.float64).ravel()
    q = np.asarray(right, dtype=np.float64).ravel()
    m = 0.5 * (p + q)

    def kl(a: np.ndarray, b: np.ndarray) -> float:
        mask = a > 0.0
        return float(np.sum(a[mask] * np.log(a[mask] / b[mask])))

    divergence = 0.5 * kl(p, m) + 0.5 * kl(q, m)
    return float(math.sqrt(max(divergence, 0.0)))


def _hellinger_distance(left: np.ndarray, right: np.ndarray) -> float:
    delta = np.sqrt(np.asarray(left, dtype=np.float64)) - np.sqrt(np.asarray(right, dtype=np.float64))
    return float(math.sqrt(0.5 * float(np.sum(delta * delta))))


def _axis_moments(distribution: np.ndarray) -> tuple[list[float], list[float]]:
    coordinates = np.meshgrid(*([np.asarray(AXIS_BINS)] * len(AXIS_NAMES)), indexing="ij")
    centers: list[float] = []
    spreads: list[float] = []
    for coordinate in coordinates:
        center = float(np.sum(distribution * coordinate))
        spread = float(np.sqrt(np.sum(distribution * (coordinate - center) ** 2)))
        centers.append(center)
        spreads.append(spread)
    return centers, spreads


def derive_transition_metrics(
    trajectory_dir: str | Path,
    *,
    derivation_version: str = "transition_metrics_rc1",
    contract: Mapping[str, Any] | None = None,
    write: bool = False,
) -> list[dict[str, Any]]:
    """Compute a small replaceable transition layer from canonical G_t/K_t."""

    active_contract = dict(contract or load_contract())
    directory = Path(trajectory_dir)
    validate_trajectory_artifact(directory, active_contract)
    mass, ledger = load_history_window(directory, contract=active_contract)
    rows: list[dict[str, Any]] = []
    for index in range(1, len(ledger)):
        previous = mass[index - 1]
        current = mass[index]
        previous_centers, previous_spreads = _axis_moments(previous)
        current_centers, current_spreads = _axis_moments(current)
        row: dict[str, Any] = {
            "from_t": int(ledger[index - 1]["t"]),
            "to_t": int(ledger[index]["t"]),
            "delta_t": int(ledger[index]["t"]) - int(ledger[index - 1]["t"]),
            "derivation_name": "fixed5axis_transition_metrics",
            "derivation_version": derivation_version,
            "source_gt_hash_from": ledger[index - 1]["gt_hash"],
            "source_gt_hash_to": ledger[index]["gt_hash"],
            "jensen_shannon_distance": _js_distance(previous, current),
            "hellinger_distance": _hellinger_distance(previous, current),
            "entropy_delta": _entropy(current) - _entropy(previous),
            "concentration_delta": float(np.sum(current * current) - np.sum(previous * previous)),
        }
        for axis_index, axis_name in enumerate(AXIS_NAMES):
            row[f"axis_centroid_delta_{axis_name}"] = current_centers[axis_index] - previous_centers[axis_index]
            row[f"axis_spread_delta_{axis_name}"] = current_spreads[axis_index] - previous_spreads[axis_index]
        rows.append(row)

    if write:
        output_dir = directory / str(active_contract["storage"]["derived_directory"]) / "transition_metrics" / derivation_version
        if output_dir.exists():
            raise Fixed5AxisGKError(f"derived output already exists: {output_dir}")
        output_dir.mkdir(parents=True)
        fieldnames = list(rows[0]) if rows else [
            "from_t",
            "to_t",
            "delta_t",
            "derivation_name",
            "derivation_version",
            "source_gt_hash_from",
            "source_gt_hash_to",
        ]
        _write_csv(output_dir / "transition_metrics.csv", rows, fieldnames)
        _json_dump(
            output_dir / "metadata.json",
            {
                "canonical": False,
                "derivation_name": "fixed5axis_transition_metrics",
                "derivation_version": derivation_version,
                "source_contract_version": active_contract["contract_version"],
                "row_count": len(rows),
                "recomputable_from": ["gt_mass.npy", "history_ledger.csv"],
            },
        )
    return rows


def classify_adoption(evidence: Mapping[str, str]) -> dict[str, Any]:
    """Apply the frozen A/B/C decision structure without inventing missing evidence."""

    representation = str(evidence.get("representation_hard_gate", "not_evaluated"))
    external = str(evidence.get("external_response_gate", "not_evaluated"))
    history = str(evidence.get("history_value_gate", "not_evaluated"))
    holdout = str(evidence.get("holdout_gate", "not_evaluated"))
    allowed = {"passed", "partial", "failed", "not_evaluated"}
    for name, value in {
        "representation_hard_gate": representation,
        "external_response_gate": external,
        "history_value_gate": history,
        "holdout_gate": holdout,
    }.items():
        if value not in allowed:
            raise Fixed5AxisGKError(f"invalid adoption evidence status {name}={value!r}")

    if representation != "passed":
        judgement = "C_rejected"
        reason = "representation hard gate did not pass"
    elif external == history == holdout == "passed":
        judgement = "A_formal_adoption"
        reason = "representation and all research gates passed"
    elif external == "failed" and history == "failed":
        judgement = "C_rejected"
        reason = "both external-response and history-value gates failed"
    else:
        judgement = "B_limited_adoption"
        reason = "representation passed but one or more research gates are partial or not evaluated"
    return {
        "judgement": judgement,
        "reason": reason,
        "evidence": {
            "representation_hard_gate": representation,
            "external_response_gate": external,
            "history_value_gate": history,
            "holdout_gate": holdout,
        },
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_one = subparsers.add_parser("build-trajectory")
    build_one.add_argument("--source", required=True)
    build_one.add_argument("--output-root", required=True)
    build_one.add_argument("--contract", default=str(DEFAULT_CONTRACT))

    build_all = subparsers.add_parser("build-corpus")
    build_all.add_argument("--source-corpus", required=True)
    build_all.add_argument("--output", required=True)
    build_all.add_argument("--contract", default=str(DEFAULT_CONTRACT))

    validate_one = subparsers.add_parser("validate-trajectory")
    validate_one.add_argument("--trajectory", required=True)
    validate_one.add_argument("--contract", default=str(DEFAULT_CONTRACT))

    derive = subparsers.add_parser("derive-transition-metrics")
    derive.add_argument("--trajectory", required=True)
    derive.add_argument("--version", default="transition_metrics_rc1")
    derive.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    derive.add_argument("--write", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    contract = load_contract(args.contract)
    if args.command == "build-trajectory":
        target = build_trajectory(args.source, args.output_root, contract)
        print(target)
    elif args.command == "build-corpus":
        target = build_corpus(args.source_corpus, args.output, args.contract)
        print(target)
    elif args.command == "validate-trajectory":
        print(json.dumps(validate_trajectory_artifact(args.trajectory, contract), indent=2, sort_keys=True))
    elif args.command == "derive-transition-metrics":
        rows = derive_transition_metrics(
            args.trajectory,
            derivation_version=args.version,
            contract=contract,
            write=args.write,
        )
        print(json.dumps({"row_count": len(rows)}, indent=2, sort_keys=True))
    else:  # pragma: no cover
        raise AssertionError(args.command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
