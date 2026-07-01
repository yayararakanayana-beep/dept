#!/usr/bin/env python3
"""Profile loading utilities for Task22C Rev1 LocalPrep-1.

Profiles are intentionally plain JSON so GitHub/Codex validation can vary the
pseudo-reality system and the action profile without editing runner code.
"""
from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path
from typing import Any, Dict

from dept2_fullspec_runner_rc1.contracts import FullSpecRunnerConfig


REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_ROOT = REPO_ROOT / "configs"


def load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_named_profile(kind: str, name: str) -> Dict[str, Any]:
    path = CONFIG_ROOT / kind / f"{name}.json"
    if not path.exists():
        available = sorted(p.stem for p in (CONFIG_ROOT / kind).glob("*.json"))
        raise FileNotFoundError(f"Profile not found: {kind}/{name}. Available: {available}")
    return load_json(path)


def merge_config(
    *,
    validation_profile: str,
    world_profile: str,
    action_profile: str,
    overrides: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    v = load_named_profile("validation_profiles", validation_profile)
    w = load_named_profile("world_profiles", world_profile)
    a = load_named_profile("action_profiles", action_profile)

    merged.update(v.get("defaults", {}))
    merged.update(w.get("config", {}))
    merged.update(a.get("config", {}))
    merged.update(overrides or {})

    merged["validation_profile_name"] = validation_profile
    merged["world_profile_name"] = world_profile
    merged["action_profile_name"] = action_profile
    return merged


def build_runner_config(
    *,
    validation_profile: str,
    world_profile: str,
    action_profile: str,
    overrides: Dict[str, Any] | None = None,
) -> FullSpecRunnerConfig:
    merged = merge_config(
        validation_profile=validation_profile,
        world_profile=world_profile,
        action_profile=action_profile,
        overrides=overrides,
    )
    allowed = {f.name for f in fields(FullSpecRunnerConfig)}
    unknown = sorted(set(merged) - allowed)
    if unknown:
        raise ValueError(f"Profile produced unsupported FullSpecRunnerConfig fields: {unknown}")
    return FullSpecRunnerConfig(**merged)


def ensure_output_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def dataframe_to_csv(df, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def collect_metrics(label: str, cfg: FullSpecRunnerConfig, out: Dict[str, Any]) -> Dict[str, Any]:
    import pandas as pd

    def df(name: str):
        return out.get(name, pd.DataFrame())

    bvr = df("boundary_violation_report")
    write = df("canonical_write_audit")
    rollback = df("rollback_snapshot")
    commit = df("commit_gate_audit")
    projection = df("exploration_projection")
    action_frame = df("action_frame")
    gate = df("coactivation_gate")
    exec_audit = df("action_execution_audit")
    world = df("world_transition_audit")
    binding = df("parameter_window_binding_audit")

    def sum_col(frame, col):
        if frame is None or frame.empty or col not in frame.columns:
            return 0.0
        return float(pd.to_numeric(frame[col], errors="coerce").fillna(0.0).sum())

    def mean_col(frame, col):
        if frame is None or frame.empty or col not in frame.columns:
            return 0.0
        s = pd.to_numeric(frame[col], errors="coerce").fillna(0.0)
        return float(s.mean()) if len(s) else 0.0

    def bool_any(frame, col):
        return bool(frame is not None and not frame.empty and col in frame.columns and frame[col].astype(bool).any())

    def bool_all(frame, col):
        return bool(frame is not None and not frame.empty and col in frame.columns and frame[col].astype(bool).all())

    def sum_bool(frame, col):
        if frame is None or frame.empty or col not in frame.columns:
            return 0
        return int(frame[col].astype(bool).sum())

    forbidden = (
        bool_any(write, "world_write_performed")
        or bool_any(write, "gk_writeback_performed")
        or bool_any(write, "ot_writeback_performed")
        or bool_any(write, "actionmodule_direct_input")
        or bool_any(exec_audit, "direct_parameter_box_input_to_actionmodule")
        or bool_any(world, "gk_writeback_performed")
        or bool_any(world, "ot_writeback_performed")
        or bool_any(world, "canonical_parameter_write_performed")
    )

    return {
        "label": label,
        "scenario": cfg.scenario,
        "seed": cfg.seed,
        "steps": cfg.steps,
        "world_profile": cfg.world_profile_name,
        "action_profile": cfg.action_profile_name,
        "validation_profile": cfg.validation_profile_name,
        "canonical_commit_enabled": cfg.canonical_commit_enabled,
        "canonical_commit_dry_run": cfg.canonical_commit_dry_run,
        "canonical_binding_source": cfg.canonical_binding_source,
        "boundary_violation_rows": 0 if bvr is None else int(len(bvr)),
        "commit_gate_rows": 0 if commit is None else int(len(commit)),
        "canonical_write_rows": sum_bool(write, "canonical_write_performed"),
        "dry_run_write_violation": bool_any(write, "canonical_commit_dry_run") and bool_any(write, "canonical_write_performed"),
        "rollback_snapshot_rows": 0 if rollback is None else int(len(rollback)),
        "rollback_ready_rows": sum_bool(rollback, "rollback_ready"),
        "projection_rows": 0 if projection is None else int(len(projection)),
        "action_frame_rows": 0 if action_frame is None else int(len(action_frame)),
        "action_frame_strength_sum": sum_col(action_frame, "action_strength"),
        "gate_risk_mean": mean_col(gate, "coactivation_risk_score"),
        "binding_pass": bool(binding is not None and not binding.empty and "audit_status" in binding.columns and binding["audit_status"].astype(str).eq("pass").all()),
        "binding_used_in_planning": bool_all(df("action_surface_planning_audit"), "parameter_window_binding_used"),
        "binding_used_in_gate": bool_all(gate, "parameter_window_binding_used"),
        "forbidden_write_detected": forbidden,
        "direct_parameter_box_input_to_actionmodule": bool_any(exec_audit, "direct_parameter_box_input_to_actionmodule"),
    }


def acceptance_pass(metrics: Dict[str, Any]) -> bool:
    return (
        metrics["boundary_violation_rows"] == 0
        and not metrics["dry_run_write_violation"]
        and not metrics["forbidden_write_detected"]
        and not metrics["direct_parameter_box_input_to_actionmodule"]
        and metrics["rollback_snapshot_rows"] >= metrics["steps"]
        and metrics["commit_gate_rows"] >= metrics["steps"]
        and metrics["action_frame_rows"] > 0
    )
