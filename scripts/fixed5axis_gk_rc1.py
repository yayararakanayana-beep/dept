"""固定5軸 G_t・K_t 基盤 RC1。

PseudoReality v3.3 の連続軌道から、完全な固定5軸分布 G_t と、
全 G_t を参照する追記専用履歴 K_t を構築する。
関係場、ゲーム構造、リスク予測、作用接続は行わない。
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
GENESIS_HASH = hashlib.sha256(b"fixed5axis_gk_rc1_history_genesis").hexdigest()
FORBIDDEN_CANONICAL_FILES = {"truth.jsonl", "summary.json", "metrics.jsonl"}
LEDGER_FIELDS = (
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
)


class Fixed5AxisGKError(ValueError):
    """固定5軸 G/K 契約違反。"""


def _json_load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _json_dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields))
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _safe_relative(value: str, name: str) -> Path:
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise Fixed5AxisGKError(f"{name} must remain inside the source trajectory directory")
    return path


def load_contract(path: str | Path = DEFAULT_CONTRACT) -> dict[str, Any]:
    contract = _json_load(Path(path))
    validate_contract(contract)
    return contract


def validate_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("contract_version") != "fixed5axis_gk_rc1":
        raise Fixed5AxisGKError("unsupported contract_version")
    axes = contract.get("axes", {})
    if tuple(axes.get("order", ())) != AXIS_NAMES:
        raise Fixed5AxisGKError("fixed axis order does not match RC1")
    if tuple(float(value) for value in axes.get("bins", ())) != AXIS_BINS:
        raise Fixed5AxisGKError("fixed axis bins do not match RC1")
    if tuple(int(value) for value in axes.get("shape", ())) != GT_SHAPE:
        raise Fixed5AxisGKError("fixed G_t shape does not match RC1")
    if int(axes.get("cell_count", -1)) != 3125:
        raise Fixed5AxisGKError("fixed cell_count does not match RC1")
    gt = contract.get("gt", {})
    if gt.get("canonical_dtype") != "float64" or gt.get("phase") != "pre_transition":
        raise Fixed5AxisGKError("invalid RC1 G_t dtype or phase")
    if gt.get("source_mode") != "reference_full":
        raise Fixed5AxisGKError("RC1 source_mode must be reference_full")


def validate_distribution(distribution: np.ndarray, contract: Mapping[str, Any]) -> np.ndarray:
    """補正せずに検証し、little-endian float64 の正本配列を返す。"""
    validate_contract(contract)
    array = np.asarray(distribution)
    if array.shape != GT_SHAPE:
        raise Fixed5AxisGKError(f"distribution shape {array.shape} != {GT_SHAPE}")
    canonical = np.ascontiguousarray(array, dtype=GT_DTYPE)
    if not np.all(np.isfinite(canonical)):
        raise Fixed5AxisGKError("distribution contains non-finite values")
    if float(canonical.min()) < -float(contract["gt"]["negative_tolerance"]):
        raise Fixed5AxisGKError("distribution contains negative mass")
    total = float(canonical.sum(dtype=np.float64))
    if abs(total - 1.0) > float(contract["gt"]["mass_tolerance"]):
        raise Fixed5AxisGKError(f"distribution mass {total:.17g} does not sum to one")
    return canonical


def compute_gt_hash(
    *, contract_version: str, trajectory_id: str, t: int,
    distribution: np.ndarray, source_state_hash: str,
) -> str:
    digest = hashlib.sha256()
    for value in (contract_version, trajectory_id, str(int(t))):
        digest.update(value.encode("utf-8")); digest.update(b"\0")
    digest.update(_canonical_json({"axes": AXIS_NAMES, "bins": AXIS_BINS})); digest.update(b"\0")
    digest.update(np.ascontiguousarray(distribution, dtype=GT_DTYPE).tobytes(order="C")); digest.update(b"\0")
    digest.update(source_state_hash.encode("ascii"))
    return digest.hexdigest()


def compute_history_chain_hash(previous: str, gt_hash: str, t: int) -> str:
    return hashlib.sha256(f"{previous}\0{gt_hash}\0{int(t)}".encode("ascii")).hexdigest()


def initial_history_chain_hash() -> str:
    return GENESIS_HASH


@dataclass
class HistoryAccumulator:
    """1軌道分の追記専用 G_t/K_t 構築器。異常時点も捨てずに記録する。"""
    contract: Mapping[str, Any]
    trajectory_id: str
    masses: list[np.ndarray] = field(default_factory=list)
    ledger_rows: list[dict[str, Any]] = field(default_factory=list)
    _previous_gt_hash: str = ""
    _chain_hash: str = GENESIS_HASH

    def append(
        self, *, t: int, phase: str, distribution: np.ndarray,
        source_state_ref: str, source_state_hash: str,
        source_trajectory_id: str | None = None,
    ) -> None:
        if isinstance(t, bool) or not isinstance(t, int) or t < 0:
            raise Fixed5AxisGKError("t must be a non-negative integer")
        if phase != self.contract["gt"]["phase"]:
            raise Fixed5AxisGKError("phase is not pre_transition")
        _safe_relative(source_state_ref, "source_state_ref")
        if len(source_state_hash) != 64 or any(ch not in "0123456789abcdef" for ch in source_state_hash):
            raise Fixed5AxisGKError("source_state_hash must be a lowercase SHA-256 digest")

        source_id = self.trajectory_id if source_trajectory_id is None else str(source_trajectory_id)
        source_matches = source_id == self.trajectory_id
        previous_t = int(self.ledger_rows[-1]["t"]) if self.ledger_rows else None
        if previous_t is None:
            status, delta_t = ("initial" if source_matches else "source_mismatch"), 0
        else:
            delta_t = t - previous_t
            if not source_matches: status = "source_mismatch"
            elif t == previous_t: status = "duplicate"
            elif t < previous_t: status = "out_of_order"
            elif t > previous_t + 1: status = "gap"
            else: status = "continuous"

        canonical = validate_distribution(distribution, self.contract)
        gt_hash = compute_gt_hash(
            contract_version=str(self.contract["contract_version"]), trajectory_id=self.trajectory_id,
            t=t, distribution=canonical, source_state_hash=source_state_hash,
        )
        chain_hash = compute_history_chain_hash(self._chain_hash, gt_hash, t)
        admissible = status in set(self.contract["kt"]["admissible_continuity_status"])
        self.masses.append(canonical.copy())
        self.ledger_rows.append({
            "trajectory_id": self.trajectory_id,
            "source_trajectory_id": source_id,
            "t": t,
            "phase": phase,
            "gt_row_index": len(self.masses) - 1,
            "gt_hash": gt_hash,
            "previous_gt_hash": self._previous_gt_hash,
            "history_chain_hash": chain_hash,
            "delta_t": delta_t,
            "continuity_status": status,
            "admissible_for_research": admissible,
            "source_state_ref": source_state_ref,
            "source_state_hash": source_state_hash,
        })
        self._previous_gt_hash, self._chain_hash = gt_hash, chain_hash

    def stacked_mass(self) -> np.ndarray:
        if not self.masses:
            raise Fixed5AxisGKError("cannot finalize an empty G_t history")
        return np.ascontiguousarray(np.stack(self.masses), dtype=GT_DTYPE)


def _source_config_hash(metadata: Mapping[str, Any]) -> str:
    keys = ("world_module", "world_class", "world_version", "config_version", "initial_state_id")
    return hashlib.sha256(_canonical_json({key: metadata.get(key) for key in keys})).hexdigest()


def _manifest(root: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "manifest.json" or "derived" in path.relative_to(root).parts:
            continue
        item: dict[str, Any] = {
            "relative_path": path.relative_to(root).as_posix(),
            "sha256": _sha256_file(path), "size_bytes": path.stat().st_size,
        }
        if path.suffix == ".npy":
            array = np.load(path, mmap_mode="r", allow_pickle=False)
            item.update(array_shape=list(array.shape), array_dtype=str(array.dtype))
        elif path.suffix == ".csv":
            item["row_count"] = max(len(path.read_text(encoding="utf-8").splitlines()) - 1, 0)
        elif path.suffix == ".jsonl":
            item["row_count"] = sum(bool(line.strip()) for line in path.read_text(encoding="utf-8").splitlines())
        files.append(item)
    return {
        "contract_version": "fixed5axis_gk_rc1",
        "canonical_manifest_excludes_derived": True,
        "file_count": len(files),
        "total_size_bytes": sum(int(item["size_bytes"]) for item in files),
        "files": files,
    }


def _build_into(source: Path, target: Path, contract: Mapping[str, Any]) -> dict[str, Any]:
    metadata_path, steps_path = source / "metadata.json", source / "steps.jsonl"
    if not metadata_path.is_file() or not steps_path.is_file():
        raise Fixed5AxisGKError("source trajectory requires metadata.json and steps.jsonl")
    metadata, steps = _json_load(metadata_path), _read_jsonl(steps_path)
    trajectory_id = str(metadata.get("trajectory_id", ""))
    if not trajectory_id or not steps:
        raise Fixed5AxisGKError("source trajectory identity or steps are missing")
    if len(steps) != int(metadata.get("total_steps", len(steps) - 1)) + 1:
        raise Fixed5AxisGKError("source step count does not match metadata")

    accumulator = HistoryAccumulator(contract, trajectory_id)
    external_rows: list[dict[str, Any]] = []
    action_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    source_hashes: dict[str, str] = {}
    source_files_read = ["metadata.json", "steps.jsonl"]

    for step in steps:
        t = step.get("step")
        if isinstance(t, bool) or not isinstance(t, int) or t < 0:
            raise Fixed5AxisGKError(f"invalid source step value {t!r}")
        state_ref = str(step.get("state_ref", ""))
        state_path = source / _safe_relative(state_ref, "state_ref")
        if not state_path.is_file():
            raise Fixed5AxisGKError(f"missing source state file {state_ref}")
        before = _sha256_file(state_path)
        with np.load(state_path, allow_pickle=False) as bundle:
            if "distribution" not in bundle.files:
                raise Fixed5AxisGKError(f"{state_ref} does not contain distribution")
            distribution = np.asarray(bundle["distribution"])
        if _sha256_file(state_path) != before:
            raise Fixed5AxisGKError(f"source state changed while reading: {state_ref}")
        source_hashes[state_ref] = before
        source_files_read.append(state_ref)
        accumulator.append(
            t=t, phase=str(step.get("phase", "")), distribution=distribution,
            source_state_ref=state_ref, source_state_hash=before,
            source_trajectory_id=str(step.get("trajectory_id", trajectory_id)),
        )
        common = {"trajectory_id": trajectory_id, "t": t}
        external_rows.append({**common, "observed_external_input": step.get("observed_external_input")})
        action_rows.append({**common, "observed_action": step.get("observed_action")})
        event_rows.append({**common, "observed_events": step.get("observed_events", [])})

    if target.exists() and any(target.iterdir()):
        raise Fixed5AxisGKError(f"target trajectory directory is not empty: {target}")
    target.mkdir(parents=True, exist_ok=True)
    storage = contract["storage"]
    np.save(target / storage["gt_file"], accumulator.stacked_mass(), allow_pickle=False)
    _write_csv(target / storage["history_ledger_file"], accumulator.ledger_rows, LEDGER_FIELDS)
    _write_jsonl(target / storage["external_log_file"], external_rows)
    _write_jsonl(target / storage["action_log_file"], action_rows)
    _write_jsonl(target / storage["event_log_file"], event_rows)
    statuses = [row["continuity_status"] for row in accumulator.ledger_rows]
    _json_dump(target / storage["provenance_file"], {
        "contract_version": contract["contract_version"],
        "axis_order": list(AXIS_NAMES), "axis_bins": list(AXIS_BINS),
        "gt_shape": list(GT_SHAPE), "gt_dtype": "float64",
        "gt_phase": contract["gt"]["phase"], "source_mode": contract["gt"]["source_mode"],
        "trajectory_id": trajectory_id,
        "world_module": metadata.get("world_module"), "world_class": metadata.get("world_class"),
        "world_version": metadata.get("world_version"), "world_config_hash": _source_config_hash(metadata),
        "dataset_split": metadata.get("dataset_split"), "seed": metadata.get("seed"),
        "scenario_id": metadata.get("scenario_id"), "total_gt_frames": len(statuses),
        "source_files_read": source_files_read,
        "forbidden_source_files_read": sorted(set(source_files_read) & FORBIDDEN_CANONICAL_FILES),
        "source_writeback_performed": False,
        "canonical_history_is_complete_gt_sequence": all(
            row["admissible_for_research"] for row in accumulator.ledger_rows
        ),
        "recorded_continuity_statuses": statuses,
        "derived_layers_are_canonical": False,
    })
    _json_dump(target / "derived" / "derivation_registry.json", {
        "contract_version": contract["contract_version"], "canonical": False, "entries": [],
        "policy": "delete_and_recompute_from_gt_mass_and_history_ledger",
    })
    _json_dump(target / storage["manifest_file"], _manifest(target))
    validation = validate_trajectory_artifact(target, contract)
    _json_dump(target / "validation.json", validation)
    _json_dump(target / storage["manifest_file"], _manifest(target))

    for state_ref, before in source_hashes.items():
        if _sha256_file(source / state_ref) != before:
            raise Fixed5AxisGKError(f"source writeback detected after build: {state_ref}")
    return validation


def build_trajectory(
    source_trajectory_dir: str | Path, output_root: str | Path,
    contract: Mapping[str, Any] | None = None,
) -> Path:
    active = dict(contract or load_contract()); validate_contract(active)
    source = Path(source_trajectory_dir)
    trajectory_id = str(_json_load(source / "metadata.json").get("trajectory_id", ""))
    if not trajectory_id:
        raise Fixed5AxisGKError("metadata.trajectory_id is required")
    target = Path(output_root) / "trajectories" / trajectory_id
    if target.exists():
        raise Fixed5AxisGKError(f"append-only target already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{trajectory_id}.", dir=target.parent))
    try:
        _build_into(source, temporary, active)
        os.replace(temporary, target)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return target


def build_corpus(
    source_corpus_dir: str | Path, output_dir: str | Path,
    contract_path: str | Path = DEFAULT_CONTRACT,
) -> Path:
    contract = load_contract(contract_path)
    sources = sorted(path for path in (Path(source_corpus_dir) / "trajectories").glob("*") if path.is_dir())
    if not sources:
        raise Fixed5AxisGKError("source corpus contains no trajectory directories")
    output = Path(output_dir)
    if output.exists():
        raise Fixed5AxisGKError(f"append-only corpus target already exists: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    records: list[dict[str, Any]] = []
    seen_ids: set[str] = set(); seen_keys: set[tuple[str, Any]] = set()
    try:
        _json_dump(temporary / "contract.json", contract)
        for source in sources:
            metadata = _json_load(source / "metadata.json")
            trajectory_id = str(metadata.get("trajectory_id", ""))
            key = (str(metadata.get("scenario_id")), metadata.get("seed"))
            if trajectory_id in seen_ids or key in seen_keys:
                raise Fixed5AxisGKError("duplicate trajectory identity or scenario/seed source key")
            seen_ids.add(trajectory_id); seen_keys.add(key)
            validation = _build_into(source, temporary / "trajectories" / trajectory_id, contract)
            records.append({
                "trajectory_id": trajectory_id, "dataset_split": metadata.get("dataset_split"),
                "scenario_id": metadata.get("scenario_id"), "seed": metadata.get("seed"),
                "total_gt_frames": validation["total_gt_frames"],
                "artifact_integrity_gate": validation["artifact_integrity_gate"],
                "research_admissible_history": validation["research_admissible_history"],
            })
        split_counts: dict[str, int] = {}
        for record in records:
            split = str(record["dataset_split"]); split_counts[split] = split_counts.get(split, 0) + 1
        _json_dump(temporary / "dataset_manifest.json", {
            "contract_version": contract["contract_version"], "trajectory_count": len(records),
            "split_counts": split_counts, "trajectories": records,
            "prediction_or_relation_field_built": False, "research_adoption_not_yet_claimed": True,
        })
        integrity = all(record["artifact_integrity_gate"] == "passed" for record in records)
        admissible = all(record["research_admissible_history"] for record in records)
        _json_dump(temporary / "validation.json", {
            "contract_version": contract["contract_version"], "trajectory_count": len(records),
            "trajectory_level_split_check": "passed",
            "artifact_integrity_gate": "passed" if integrity else "failed",
            "history_admissibility_gate": "passed" if admissible else "failed",
            "deterministic_rebuild_gate": "not_evaluated",
            "representation_hard_gate": "partial" if integrity and admissible else "failed",
            "research_external_response_gate": "not_evaluated",
            "research_history_value_gate": "not_evaluated", "research_holdout_gate": "not_evaluated",
            "adoption_judgement": (
                "B_limited_adoption_pending_determinism_and_research_gates"
                if integrity and admissible else "C_rejected"
            ),
        })
        _json_dump(temporary / "manifest.json", _manifest(temporary))
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True); raise
    return output


def validate_trajectory_artifact(
    trajectory_dir: str | Path, contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    active = dict(contract or load_contract()); validate_contract(active)
    directory, storage = Path(trajectory_dir), active["storage"]
    mass_path = directory / storage["gt_file"]
    ledger_path = directory / storage["history_ledger_file"]
    provenance_path = directory / storage["provenance_file"]
    for path in (mass_path, ledger_path, provenance_path):
        if not path.is_file(): raise Fixed5AxisGKError(f"missing canonical artifact file {path.name}")
    if any((directory / name).exists() for name in FORBIDDEN_CANONICAL_FILES):
        raise Fixed5AxisGKError("validation truth or prediction artifacts leaked into canonical output")

    mass = np.load(mass_path, mmap_mode="r", allow_pickle=False)
    ledger, provenance = _read_csv(ledger_path), _json_load(provenance_path)
    if mass.ndim != 6 or tuple(mass.shape[1:]) != GT_SHAPE or mass.dtype != np.dtype("float64"):
        raise Fixed5AxisGKError("invalid canonical G_t storage shape or dtype")
    if len(ledger) != mass.shape[0]: raise Fixed5AxisGKError("ledger and G_t frame count differ")
    if tuple(provenance.get("axis_order", ())) != AXIS_NAMES: raise Fixed5AxisGKError("axis order mismatch")
    if tuple(float(v) for v in provenance.get("axis_bins", ())) != AXIS_BINS: raise Fixed5AxisGKError("axis bins mismatch")
    if provenance.get("forbidden_source_files_read"): raise Fixed5AxisGKError("forbidden source files were read")

    previous_hash, chain_hash, previous_t = "", GENESIS_HASH, None
    trajectory_id: str | None = None
    anomalies = {"gap": 0, "duplicate": 0, "out_of_order": 0, "source_mismatch": 0}
    admissible_statuses = set(active["kt"]["admissible_continuity_status"])
    for index, row in enumerate(ledger):
        if int(row["gt_row_index"]) != index: raise Fixed5AxisGKError("gt_row_index is not contiguous")
        t = int(row["t"]); current_id = row["trajectory_id"]
        trajectory_id = trajectory_id or current_id
        if current_id != trajectory_id: raise Fixed5AxisGKError("multiple canonical trajectory IDs")
        if row["phase"] != active["gt"]["phase"]: raise Fixed5AxisGKError("non-pre-transition G_t")
        if row["previous_gt_hash"] != previous_hash: raise Fixed5AxisGKError("previous_gt_hash mismatch")
        source_matches = row.get("source_trajectory_id", current_id) == current_id
        if previous_t is None: expected_status, expected_delta = ("initial" if source_matches else "source_mismatch"), 0
        else:
            expected_delta = t - previous_t
            if not source_matches: expected_status = "source_mismatch"
            elif t == previous_t: expected_status = "duplicate"
            elif t < previous_t: expected_status = "out_of_order"
            elif t > previous_t + 1: expected_status = "gap"
            else: expected_status = "continuous"
        if row["continuity_status"] != expected_status or int(row["delta_t"]) != expected_delta:
            raise Fixed5AxisGKError(f"continuity metadata mismatch at row {index}")
        expected_admissible = expected_status in admissible_statuses
        if (row.get("admissible_for_research", "").lower() == "true") != expected_admissible:
            raise Fixed5AxisGKError(f"admissibility mismatch at row {index}")
        if expected_status in anomalies: anomalies[expected_status] += 1
        canonical = validate_distribution(np.asarray(mass[index]), active)
        expected_hash = compute_gt_hash(
            contract_version=active["contract_version"], trajectory_id=current_id, t=t,
            distribution=canonical, source_state_hash=row["source_state_hash"],
        )
        if row["gt_hash"] != expected_hash: raise Fixed5AxisGKError(f"G_t hash mismatch at row {index}")
        chain_hash = compute_history_chain_hash(chain_hash, expected_hash, t)
        if row["history_chain_hash"] != chain_hash: raise Fixed5AxisGKError("history chain mismatch")
        previous_hash, previous_t = expected_hash, t

    log_counts: dict[str, int] = {}
    for key in ("external_log_file", "action_log_file", "event_log_file"):
        path = directory / storage[key]
        if not path.is_file() or len(_read_jsonl(path)) != len(ledger):
            raise Fixed5AxisGKError(f"separate observed log mismatch: {path.name}")
        log_counts[path.name] = len(ledger)
    research_admissible = sum(anomalies.values()) == 0
    return {
        "contract_version": active["contract_version"], "trajectory_id": trajectory_id,
        "total_gt_frames": len(ledger), "gt_shape": list(mass.shape), "gt_dtype": str(mass.dtype),
        "axis_contract_exact": True, "mass_validation": "passed", "hash_validation": "passed",
        "history_chain_validation": "passed",
        "continuity_validation": "passed_with_no_anomalies" if research_admissible else "passed_with_recorded_anomalies",
        "continuity_anomaly_counts": anomalies, "research_admissible_history": research_admissible,
        "truth_isolation": "passed", "observed_log_counts": log_counts,
        "artifact_integrity_gate": "passed",
        "representation_hard_gate": "partial" if research_admissible else "failed",
        "representation_pending_checks": ["deterministic_rebuild", "trajectory_level_split_corpus_check"],
        "research_external_response_gate": "not_evaluated", "research_history_value_gate": "not_evaluated",
        "research_holdout_gate": "not_evaluated",
        "adoption_judgement": (
            "B_limited_adoption_pending_representation_and_research_gates"
            if research_admissible else "C_rejected_due_to_history_anomaly"
        ),
        "status": "valid" if research_admissible else "valid_with_recorded_anomalies",
    }


def load_history_window(
    trajectory_dir: str | Path, *, last_n: int | None = None,
    start_t: int | None = None, end_t: int | None = None,
    contract: Mapping[str, Any] | None = None,
) -> tuple[np.ndarray, list[dict[str, str]]]:
    active = dict(contract or load_contract()); directory = Path(trajectory_dir)
    mass = np.load(directory / active["storage"]["gt_file"], mmap_mode="r", allow_pickle=False)
    ledger = _read_csv(directory / active["storage"]["history_ledger_file"])
    if last_n is not None and (start_t is not None or end_t is not None):
        raise Fixed5AxisGKError("last_n cannot be combined with time bounds")
    if last_n is not None:
        if isinstance(last_n, bool) or not isinstance(last_n, int) or last_n <= 0:
            raise Fixed5AxisGKError("last_n must be positive")
        indices = list(range(max(0, len(ledger) - last_n), len(ledger)))
    elif start_t is None and end_t is None:
        indices = list(range(len(ledger)))
    else:
        statuses = {row["continuity_status"] for row in ledger}
        times = [int(row["t"]) for row in ledger]
        if statuses - {"initial", "continuous", "gap"} or any(b <= a for a, b in zip(times, times[1:])):
            raise Fixed5AxisGKError("time-bounded windows require unique monotonic history")
        start = times[0] if start_t is None else int(start_t)
        end = times[-1] if end_t is None else int(end_t)
        if end < start: raise Fixed5AxisGKError("invalid history window bounds")
        indices = [index for index, t in enumerate(times) if start <= t <= end]
        if not indices: raise Fixed5AxisGKError("history window contains no stored G_t frames")
    return np.asarray(mass[indices], dtype=GT_DTYPE).copy(), [ledger[index] for index in indices]


def _entropy(distribution: np.ndarray) -> float:
    values = np.asarray(distribution, dtype=np.float64).ravel(); mask = values > 0
    return -float(np.sum(values[mask] * np.log(values[mask])))


def _js_distance(left: np.ndarray, right: np.ndarray) -> float:
    p, q = np.asarray(left, dtype=np.float64).ravel(), np.asarray(right, dtype=np.float64).ravel()
    middle = 0.5 * (p + q)
    def kl(a: np.ndarray, b: np.ndarray) -> float:
        mask = a > 0; return float(np.sum(a[mask] * np.log(a[mask] / b[mask])))
    return math.sqrt(max(0.5 * kl(p, middle) + 0.5 * kl(q, middle), 0.0))


def _hellinger(left: np.ndarray, right: np.ndarray) -> float:
    delta = np.sqrt(left) - np.sqrt(right)
    return math.sqrt(0.5 * float(np.sum(delta * delta)))


def _axis_moments(distribution: np.ndarray) -> tuple[list[float], list[float]]:
    grids = np.meshgrid(*([np.asarray(AXIS_BINS)] * 5), indexing="ij")
    centers, spreads = [], []
    for grid in grids:
        center = float(np.sum(distribution * grid)); centers.append(center)
        spreads.append(float(np.sqrt(np.sum(distribution * (grid - center) ** 2))))
    return centers, spreads


def derive_transition_metrics(
    trajectory_dir: str | Path, *, derivation_version: str = "transition_metrics_rc1",
    contract: Mapping[str, Any] | None = None, write: bool = False,
) -> list[dict[str, Any]]:
    active = dict(contract or load_contract()); directory = Path(trajectory_dir)
    validation = validate_trajectory_artifact(directory, active)
    if not validation["research_admissible_history"]:
        raise Fixed5AxisGKError("transition metrics require research-admissible history")
    mass, ledger = load_history_window(directory, contract=active)
    rows: list[dict[str, Any]] = []
    for index in range(1, len(ledger)):
        previous, current = mass[index - 1], mass[index]
        pc, ps = _axis_moments(previous); cc, cs = _axis_moments(current)
        row: dict[str, Any] = {
            "from_t": int(ledger[index - 1]["t"]), "to_t": int(ledger[index]["t"]),
            "delta_t": int(ledger[index]["t"]) - int(ledger[index - 1]["t"]),
            "derivation_name": "fixed5axis_transition_metrics", "derivation_version": derivation_version,
            "source_gt_hash_from": ledger[index - 1]["gt_hash"], "source_gt_hash_to": ledger[index]["gt_hash"],
            "jensen_shannon_distance": _js_distance(previous, current),
            "hellinger_distance": _hellinger(previous, current),
            "entropy_delta": _entropy(current) - _entropy(previous),
            "concentration_delta": float(np.sum(current * current) - np.sum(previous * previous)),
        }
        for axis_index, axis_name in enumerate(AXIS_NAMES):
            row[f"axis_centroid_delta_{axis_name}"] = cc[axis_index] - pc[axis_index]
            row[f"axis_spread_delta_{axis_name}"] = cs[axis_index] - ps[axis_index]
        rows.append(row)
    if write:
        output = directory / active["storage"]["derived_directory"] / "transition_metrics" / derivation_version
        if output.exists(): raise Fixed5AxisGKError(f"derived output already exists: {output}")
        output.mkdir(parents=True)
        fields = list(rows[0]) if rows else (
            "from_t", "to_t", "delta_t", "derivation_name", "derivation_version",
            "source_gt_hash_from", "source_gt_hash_to",
        )
        _write_csv(output / "transition_metrics.csv", rows, fields)
        _json_dump(output / "metadata.json", {
            "canonical": False, "derivation_name": "fixed5axis_transition_metrics",
            "derivation_version": derivation_version, "source_contract_version": active["contract_version"],
            "row_count": len(rows), "recomputable_from": ["gt_mass.npy", "history_ledger.csv"],
        })
    return rows


def classify_adoption(evidence: Mapping[str, str]) -> dict[str, Any]:
    keys = ("representation_hard_gate", "external_response_gate", "history_value_gate", "holdout_gate")
    values = {key: str(evidence.get(key, "not_evaluated")) for key in keys}
    allowed = {"passed", "partial", "failed", "not_evaluated"}
    if any(value not in allowed for value in values.values()):
        raise Fixed5AxisGKError("invalid adoption evidence status")
    if values["representation_hard_gate"] == "failed":
        judgement, reason = "C_rejected", "representation hard gate failed"
    elif values["representation_hard_gate"] == "passed" and all(values[key] == "passed" for key in keys[1:]):
        judgement, reason = "A_formal_adoption", "representation and all research gates passed"
    elif values["external_response_gate"] == values["history_value_gate"] == "failed":
        judgement, reason = "C_rejected", "external-response and history-value gates failed"
    else:
        judgement, reason = "B_limited_adoption", "one or more gates are partial or not evaluated"
    return {"judgement": judgement, "reason": reason, "evidence": values}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest="command", required=True)
    one = sub.add_parser("build-trajectory"); one.add_argument("--source", required=True); one.add_argument("--output-root", required=True); one.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    corpus = sub.add_parser("build-corpus"); corpus.add_argument("--source-corpus", required=True); corpus.add_argument("--output", required=True); corpus.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    validate = sub.add_parser("validate-trajectory"); validate.add_argument("--trajectory", required=True); validate.add_argument("--contract", default=str(DEFAULT_CONTRACT))
    derive = sub.add_parser("derive-transition-metrics"); derive.add_argument("--trajectory", required=True); derive.add_argument("--version", default="transition_metrics_rc1"); derive.add_argument("--contract", default=str(DEFAULT_CONTRACT)); derive.add_argument("--write", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv); contract = load_contract(args.contract)
    if args.command == "build-trajectory": print(build_trajectory(args.source, args.output_root, contract))
    elif args.command == "build-corpus": print(build_corpus(args.source_corpus, args.output, args.contract))
    elif args.command == "validate-trajectory": print(json.dumps(validate_trajectory_artifact(args.trajectory, contract), indent=2, sort_keys=True))
    elif args.command == "derive-transition-metrics": print(json.dumps({"row_count": len(derive_transition_metrics(args.trajectory, derivation_version=args.version, contract=contract, write=args.write))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
