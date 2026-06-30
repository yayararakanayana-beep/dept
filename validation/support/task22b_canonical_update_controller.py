"""Task22B bounded canonical lower ParameterBox update controller.

This helper is intentionally small: it updates only an already-instantiated
RC1 runner's owned lower ParameterBox state, records a rollback snapshot, and
keeps explicit boundary counters. It does not create a runner or touch source
configuration.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any
import hashlib
import json
import uuid

MAX_ALLOWED_ABS_DELTA = 0.05


@dataclass
class CanonicalUpdateIntent:
    intent_id: str
    source: str
    source_candidate_id: str
    target_parameter_path: str
    direction: str
    requested_delta: float
    bounded_delta: float
    expected_effect: str
    commit_reason: str
    counter_evidence_summary: str
    max_abs_delta: float
    rollback_required: bool


@dataclass
class CanonicalUpdateSnapshot:
    snapshot_id: str
    target_parameter_path: str
    parameter_before: float
    timestamp_or_run_id: str
    source_case_id: str
    fingerprint: str
    state_rows: list[dict[str, Any]]


class ControlledCanonicalUpdateController:
    """One-write bounded update hook for runner-owned lower ParameterBox state."""

    def __init__(self, runner: Any):
        self.runner = runner
        self.canonical_write_count = 0
        self.rollback_count = 0
        self.snapshots: dict[str, CanonicalUpdateSnapshot] = {}
        self.canonical_update_ledger: list[dict[str, Any]] = []
        self.audit = {
            "audit_source": "explicit_controller_audit",
            "canonical_write_count": 0,
            "gk_writeback_count": 0,
            "world_direct_write_count": 0,
            "action_module_internal_connection_count": 0,
            "actionframe_direct_generation_count": 0,
            "boundary_violation_count": 0,
        }

    def locate_state(self) -> tuple[Any | None, str | None]:
        box = getattr(getattr(self.runner, "parameter_shadow_box", None), "box", None)
        state = getattr(box, "state", None)
        if state is None:
            return None, None
        return state, "runner.parameter_shadow_box.box.state"

    def state_snapshot(self) -> list[dict[str, Any]]:
        state, _ = self.locate_state()
        if state is None:
            raise RuntimeError("parameter_box_state_unreachable")
        rows = state.to_dict(orient="records") if hasattr(state, "to_dict") else list(state)
        return sorted(rows, key=lambda row: json.dumps(row, sort_keys=True, default=str))

    def state_fingerprint(self) -> str:
        payload = json.dumps(self.state_snapshot(), sort_keys=True, default=str, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def read_parameter(self, name: str) -> float:
        state, _ = self.locate_state()
        if state is None:
            raise RuntimeError("parameter_box_state_unreachable")
        rows = state[state["parameter_name"] == name]
        if rows.empty:
            raise KeyError(name)
        return float(rows.iloc[0]["theta"])

    def write_parameter(self, name: str, value: float) -> None:
        state, _ = self.locate_state()
        if state is None:
            raise RuntimeError("parameter_box_state_unreachable")
        mask = state["parameter_name"] == name
        if not bool(mask.any()):
            raise KeyError(name)
        state.loc[mask, "theta"] = float(value)

    def snapshot(self, case_id: str, target_parameter_path: str, parameter_name: str) -> CanonicalUpdateSnapshot:
        snap = CanonicalUpdateSnapshot(
            snapshot_id=f"task22b-{case_id}-{uuid.uuid4().hex[:10]}",
            target_parameter_path=target_parameter_path,
            parameter_before=self.read_parameter(parameter_name),
            timestamp_or_run_id=datetime.now(timezone.utc).isoformat(),
            source_case_id=case_id,
            fingerprint=self.state_fingerprint(),
            state_rows=self.state_snapshot(),
        )
        self.snapshots[snap.snapshot_id] = snap
        return snap

    def apply(self, *, case_id: str, intent: CanonicalUpdateIntent, parameter_name: str, allow_watch_only: bool = False) -> dict[str, Any]:
        before = self.read_parameter(parameter_name)
        snap = self.snapshot(case_id, intent.target_parameter_path, parameter_name)
        reasons: list[str] = []
        if self.canonical_write_count != 0:
            reasons.append("canonical_write_count_already_nonzero")
        if intent.max_abs_delta > MAX_ALLOWED_ABS_DELTA:
            reasons.append("max_abs_delta_exceeds_task22b_limit")
        if abs(intent.bounded_delta) > intent.max_abs_delta:
            reasons.append("bounded_delta_exceeds_intent_max")
        if intent.source == "task21_real_watch_only" and not allow_watch_only:
            reasons.append("watch_only_candidate_not_commit_eligible")
        if intent.source not in {"controlled_commit_fixture", "commit_candidate", "forced_bad_update_fixture"}:
            reasons.append("source_not_commit_eligible")
        if self.audit["boundary_violation_count"] != 0:
            reasons.append("boundary_violation_count_nonzero")
        if reasons:
            return {"commit_decision": "blocked", "blocked_reasons": reasons, "snapshot": asdict(snap), "parameter_before": before, "parameter_after": before, "parameter_delta": 0.0}
        after = before + float(intent.bounded_delta)
        self.write_parameter(parameter_name, after)
        self.canonical_write_count += 1
        self.audit["canonical_write_count"] = self.canonical_write_count
        post_fingerprint = self.state_fingerprint()
        entry = {
            "update_id": intent.intent_id,
            "case_id": case_id,
            "approved_canonical_update_applied": True,
            "approved_baseline_shift": case_id == "controlled_update_on",
            "updated_parameter": parameter_name,
            "old_value": before,
            "new_value": after,
            "delta": after - before,
            "max_abs_delta": intent.max_abs_delta,
            "bounded_delta_confirmed": abs(after - before) <= intent.max_abs_delta <= MAX_ALLOWED_ABS_DELTA,
            "one_write_only_confirmed": self.canonical_write_count == 1,
            "rollback_restores_original_confirmed": None,
            "pre_update_snapshot": asdict(snap),
            "post_update_snapshot": self.state_snapshot(),
            "rollback_snapshot": None,
            "pre_update_fingerprint": snap.fingerprint,
            "post_update_fingerprint": post_fingerprint,
            "rollback_fingerprint": None,
        }
        self.canonical_update_ledger.append(entry)
        return {"commit_decision": "committed", "blocked_reasons": [], "snapshot": asdict(snap), "parameter_before": before, "parameter_after": after, "parameter_delta": after - before, **entry}

    def rollback(self, snapshot_id: str, parameter_name: str) -> dict[str, Any]:
        snap = self.snapshots[snapshot_id]
        self.write_parameter(parameter_name, snap.parameter_before)
        self.rollback_count += 1
        after = self.read_parameter(parameter_name)
        rollback_fingerprint = self.state_fingerprint()
        restored = after == snap.parameter_before and rollback_fingerprint == snap.fingerprint
        if self.canonical_update_ledger:
            self.canonical_update_ledger[-1]["rollback_snapshot"] = self.state_snapshot()
            self.canonical_update_ledger[-1]["rollback_fingerprint"] = rollback_fingerprint
            self.canonical_update_ledger[-1]["rollback_restores_original_confirmed"] = restored
        return {"rollback_count": self.rollback_count, "rollback_snapshot_id": snapshot_id, "rollback_snapshot": self.state_snapshot(), "rollback_fingerprint": rollback_fingerprint, "parameter_after_rollback": after, "rollback_restored_original": restored}
