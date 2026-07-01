"""gk_builder: builds G_t/K_t from pseudo-reality traces only.

Task3 strengthens this module from a simple wrapper into a formal boundary:
  - Input trace schema is validated before build.
  - Input trace fingerprint is recorded before and after build to confirm read-only use.
  - G_t and K_t receive explicit source/provenance contracts.
  - Formal H-DEPT packet is checked for lower-artifact leakage.
  - A gk_build_audit row is emitted every cycle.
"""
from __future__ import annotations

from typing import Dict
import pandas as pd

from DEPT2_ActionModule_ActuationPrimitives_RC1.pseudo_reality.observation import GtKtBuilder
from dept2_fullspec_runner_rc1.contracts import FullSpecRunnerConfig
from dept2_fullspec_runner_rc1.modules.world_adapter import WorldAdapter, trace_fingerprint

FORBIDDEN_FORMAL_PREFIXES = ("graph_object", "v8_", "final_gate", "action_surface", "ot_", "exploration_", "action_frame")


class GKBuilderModule:
    name = "gk_builder"

    def __init__(self, cfg: FullSpecRunnerConfig):
        self.cfg = cfg
        self.builder = GtKtBuilder(kt_window=cfg.kt_window)
        self.contract = "G_t_K_t_from_world_trace_only__no_writeback__Task3_RC1"

    def build(self, trace: Dict[str, pd.DataFrame], loop_step: int | None = None) -> dict[str, pd.DataFrame]:
        WorldAdapter.validate_trace_schema(trace)
        fp_before = trace_fingerprint(trace)
        trace_t = int(trace["entity_trace"]["t"].iloc[0])

        gt = self.builder.build_gt(trace)
        kt = self.builder.build_kt_global()
        formal = self.builder.build_formal_packet(gt, kt)

        fp_after = trace_fingerprint(trace)
        if fp_before != fp_after:
            raise RuntimeError("G/K build mutated the input world trace")

        gt = self._annotate_gt(gt, trace_t, fp_before)
        kt = self._annotate_kt(kt, trace_t, fp_before)
        formal = self._annotate_formal(formal, trace_t, fp_before)
        self.validate_no_lower_leak(formal)

        audit = self.build_audit(gt, kt, formal, trace_t, fp_before, fp_after, loop_step)
        return {"gt": gt, "kt": kt, "formal_packet": formal, "gk_build_audit": audit}

    def _annotate_gt(self, gt: pd.DataFrame, trace_t: int, fp: str) -> pd.DataFrame:
        out = gt.copy()
        out["gk_source_contract"] = self.contract
        out["gk_source_trace_fingerprint"] = fp
        out["gk_source_world_t"] = trace_t
        out["gk_builder_module"] = self.name
        out["gk_writeback_performed"] = False
        return out

    def _annotate_kt(self, kt: pd.DataFrame, trace_t: int, fp: str) -> pd.DataFrame:
        out = kt.copy()
        out["gk_source_contract"] = self.contract
        out["gk_source_trace_fingerprint"] = fp
        out["gk_source_world_t"] = trace_t
        out["kt_window"] = int(self.cfg.kt_window)
        out["gk_builder_module"] = self.name
        out["gk_writeback_performed"] = False
        return out

    def _annotate_formal(self, formal: pd.DataFrame, trace_t: int, fp: str) -> pd.DataFrame:
        out = formal.copy()
        out["formal_input_source_contract"] = "formal_input_is_GK_only__no_Ot_no_v8_no_exploration__Task3_RC1"
        out["gk_source_contract"] = self.contract
        out["gk_source_trace_fingerprint"] = fp
        out["gk_source_world_t"] = trace_t
        out["gk_writeback_performed"] = False
        out["formal_contains_ot"] = False
        out["formal_contains_v8"] = False
        out["formal_contains_exploration"] = False
        out["formal_contains_action_surface"] = False
        return out

    def build_audit(
        self,
        gt: pd.DataFrame,
        kt: pd.DataFrame,
        formal: pd.DataFrame,
        trace_t: int,
        fp_before: str,
        fp_after: str,
        loop_step: int | None,
    ) -> pd.DataFrame:
        leaked = self._lower_leaks(formal)
        kt_n = int(kt["kt_n_observations"].iloc[0]) if not kt.empty and "kt_n_observations" in kt.columns else 0
        row = {
            "loop_step": -1 if loop_step is None else int(loop_step),
            "gk_build_contract": self.contract,
            "source_trace_fingerprint_before": fp_before,
            "source_trace_fingerprint_after": fp_after,
            "source_trace_mutated_by_gk_builder": fp_before != fp_after,
            "source_world_t": int(trace_t),
            "gt_rows": int(len(gt)),
            "kt_rows": int(len(kt)),
            "formal_packet_rows": int(len(formal)),
            "kt_window": int(self.cfg.kt_window),
            "kt_n_observations": kt_n,
            "formal_columns_count": int(len(formal.columns)),
            "formal_lower_leak_count": int(len(leaked)),
            "formal_lower_leak_columns": "|".join(leaked),
            "gk_writeback_performed": False,
            "canonical_world_write_performed": False,
            "build_status": "pass" if fp_before == fp_after and not leaked else "fail",
        }
        return pd.DataFrame([row])

    @staticmethod
    def validate_no_lower_leak(formal_packet: pd.DataFrame) -> None:
        leaked = GKBuilderModule._lower_leaks(formal_packet)
        if leaked:
            raise ValueError(f"Formal G/K packet leaked lower internals: {leaked}")

    @staticmethod
    def _lower_leaks(formal_packet: pd.DataFrame) -> list[str]:
        if formal_packet is None:
            return []
        return [c for c in formal_packet.columns if c.startswith(FORBIDDEN_FORMAL_PREFIXES)]
