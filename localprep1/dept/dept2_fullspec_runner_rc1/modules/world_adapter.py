"""world_adapter: owns pseudo-reality state, step, trace, and trace audit.

Task3 strengthens the boundary between the pseudo-reality world and DEPT2:
  - PseudoReality state is the only canonical world state.
  - G/K and O_t are derived from emitted traces; they are never written back.
  - Each emitted trace is validated, copied, fingerprinted, and audited.
  - Step transitions are summarized without exposing DEPT internals to the world.
"""
from __future__ import annotations

from hashlib import sha256
from typing import Dict, Optional
import json
import pandas as pd

from DEPT2_ActionModule_ActuationPrimitives_RC1.pseudo_reality.system import (
    PseudoRealityConfig,
    PseudoRealitySystem,
    STATE_FEATURES,
)
from DEPT2_ActionModule_ActuationPrimitives_RC1.action_module.integrated_diagnostic_closed_loop import (
    step_with_repaired_actions,
)
from dept2_fullspec_runner_rc1.contracts import FullSpecRunnerConfig

ENTITY_REQUIRED_COLUMNS = {"entity_id", "t", "scenario", "seed", *STATE_FEATURES}
RELATION_REQUIRED_COLUMNS = {"source", "target", "relation_strength", "relation_rigidity", "flow", "t", "scenario", "seed"}


def _stable_hash_df(df: pd.DataFrame) -> str:
    if df is None or df.empty:
        return "empty"
    # Stable-ish table hash for deterministic trace lineage audit.
    data = df.sort_index(axis=1).to_csv(index=False).encode("utf-8")
    return sha256(data).hexdigest()[:16]


def trace_fingerprint(trace: Dict[str, pd.DataFrame]) -> str:
    entity_hash = _stable_hash_df(trace.get("entity_trace", pd.DataFrame()))
    relation_hash = _stable_hash_df(trace.get("relation_trace", pd.DataFrame()))
    return sha256(f"entity={entity_hash}|relation={relation_hash}".encode("utf-8")).hexdigest()[:16]


class WorldAdapter:
    name = "world_adapter"

    def __init__(self, cfg: FullSpecRunnerConfig):
        world_cfg = PseudoRealityConfig(
            seed=cfg.seed,
            scenario=cfg.scenario,
            n_entities=cfg.n_entities,
            action_coupling=cfg.action_coupling,
            noise_scale=cfg.noise_scale,
            drift_scale=cfg.drift_scale,
            shock_time=cfg.shock_time,
            shock_strength=cfg.shock_strength,
        )
        self.world = PseudoRealitySystem(world_cfg)
        self.baseline_world = PseudoRealitySystem(world_cfg)
        self.trace_contract = "pseudo_reality_trace__world_owned__dept_read_only__Task3_RC1"

    def snapshot(self) -> Dict[str, pd.DataFrame]:
        """Emit a defensive trace copy from the pseudo-world.

        The returned trace may be read by G/K and O_t builders, but no module is
        allowed to treat it as a writable world state. Future tasks can replace
        internals without changing this trace contract.
        """
        trace = self._copy_trace(self.world.emit_trace())
        self.validate_trace_schema(trace)
        return trace

    def step(self, action_frame: Optional[pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        """Apply ActionFrame to pseudo-reality and return the next trace.

        The world only sees the ActionFrame-like table. It does not see G/K,
        O_t, v8, exploration sidecars, parameter boxes, or upper-pressure internals.
        """
        trace = step_with_repaired_actions(self.world, action_frame if action_frame is not None else pd.DataFrame())
        trace = self._copy_trace(trace)
        self.validate_trace_schema(trace)
        return trace

    def baseline_step(self) -> Dict[str, pd.DataFrame]:
        trace = self.baseline_world.step(None)
        trace = self._copy_trace(trace)
        self.validate_trace_schema(trace)
        return trace

    def audit_trace(self, trace: Dict[str, pd.DataFrame], loop_step: int, phase: str) -> pd.DataFrame:
        """Return one audit row for a trace without mutating the trace itself."""
        self.validate_trace_schema(trace)
        e = trace["entity_trace"]
        r = trace["relation_trace"]
        row = {
            "loop_step": loop_step,
            "trace_phase": phase,
            "trace_contract": self.trace_contract,
            "trace_fingerprint": trace_fingerprint(trace),
            "world_t": int(e["t"].iloc[0]) if not e.empty else -1,
            "seed": int(e["seed"].iloc[0]) if not e.empty else -1,
            "scenario": str(e["scenario"].iloc[0]) if not e.empty else "unknown",
            "entity_rows": int(len(e)),
            "relation_rows": int(len(r)),
            "entity_columns": json.dumps(sorted(e.columns), ensure_ascii=False),
            "relation_columns": json.dumps(sorted(r.columns), ensure_ascii=False),
            "schema_valid": True,
            "dept_internal_columns_present": bool(self._dept_internal_columns(e) or self._dept_internal_columns(r)),
            "world_owned_state": True,
            "gk_written_back_to_world": False,
            "ot_written_back_to_world": False,
            "canonical_parameter_written_to_world": False,
        }
        for col in ["uncertainty", "exploration", "relation_lock", "volatility", "reversibility", "entropy"]:
            row[f"mean_{col}"] = float(e[col].mean()) if col in e.columns and not e.empty else 0.0
        return pd.DataFrame([row])

    def audit_transition(self, before: Dict[str, pd.DataFrame], after: Dict[str, pd.DataFrame], loop_step: int) -> pd.DataFrame:
        """Summarize one world transition for cycle-level audit."""
        self.validate_trace_schema(before)
        self.validate_trace_schema(after)
        b = before["entity_trace"].set_index("entity_id")
        a = after["entity_trace"].set_index("entity_id")
        common = b.index.intersection(a.index)
        row = {
            "loop_step": loop_step,
            "transition_contract": "world_transition_from_actionframe_only__Task3_RC1",
            "trace_before_fingerprint": trace_fingerprint(before),
            "trace_after_fingerprint": trace_fingerprint(after),
            "world_t_before": int(before["entity_trace"]["t"].iloc[0]) if not before["entity_trace"].empty else -1,
            "world_t_after": int(after["entity_trace"]["t"].iloc[0]) if not after["entity_trace"].empty else -1,
            "entity_count_before": int(len(before["entity_trace"])),
            "entity_count_after": int(len(after["entity_trace"])),
            "relation_count_before": int(len(before["relation_trace"])),
            "relation_count_after": int(len(after["relation_trace"])),
            "gk_writeback_performed": False,
            "ot_writeback_performed": False,
            "canonical_parameter_write_performed": False,
        }
        for col in STATE_FEATURES:
            if col in b.columns and col in a.columns and len(common) > 0:
                row[f"mean_delta_{col}"] = float((a.loc[common, col] - b.loc[common, col]).mean())
                row[f"abs_mean_delta_{col}"] = float((a.loc[common, col] - b.loc[common, col]).abs().mean())
        return pd.DataFrame([row])

    @staticmethod
    def validate_trace_schema(trace: Dict[str, pd.DataFrame]) -> None:
        if not isinstance(trace, dict):
            raise TypeError("Trace must be a dict with entity_trace and relation_trace DataFrames")
        if "entity_trace" not in trace or "relation_trace" not in trace:
            raise ValueError("Trace missing entity_trace or relation_trace")
        e = trace["entity_trace"]
        r = trace["relation_trace"]
        if not isinstance(e, pd.DataFrame) or not isinstance(r, pd.DataFrame):
            raise TypeError("Trace entries must be pandas DataFrames")
        missing_e = sorted(ENTITY_REQUIRED_COLUMNS - set(e.columns))
        missing_r = sorted(RELATION_REQUIRED_COLUMNS - set(r.columns))
        if missing_e:
            raise ValueError(f"entity_trace missing columns: {missing_e}")
        if missing_r:
            raise ValueError(f"relation_trace missing columns: {missing_r}")
        if e.empty:
            raise ValueError("entity_trace must not be empty")
        if e["t"].nunique() != 1 or e["seed"].nunique() != 1 or e["scenario"].nunique() != 1:
            raise ValueError("entity_trace must represent one world t/seed/scenario")
        if not r.empty and (r["t"].nunique() != 1 or r["seed"].nunique() != 1 or r["scenario"].nunique() != 1):
            raise ValueError("relation_trace must represent one world t/seed/scenario")

    @staticmethod
    def _copy_trace(trace: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        return {k: v.copy(deep=True) for k, v in trace.items()}

    @staticmethod
    def _dept_internal_columns(df: pd.DataFrame) -> list[str]:
        prefixes = ("gt_", "kt_", "ot_", "v8_", "exploration_", "action_frame", "final_gate", "pressure_intent")
        return [c for c in df.columns if c.startswith(prefixes)]
