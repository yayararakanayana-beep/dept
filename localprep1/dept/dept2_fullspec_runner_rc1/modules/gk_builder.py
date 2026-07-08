"""gk_builder: builds G_t/K_t from pseudo-reality traces only.

Task3 strengthens this module from a simple wrapper into a formal boundary:
  - Input trace schema is validated before build.
  - Input trace fingerprint is recorded before and after build to confirm read-only use.
  - G_t and K_t receive explicit source/provenance contracts.
  - Formal H-DEPT packet is checked for lower-artifact leakage.
  - A gk_build_audit row is emitted every cycle.

Task2-8j-25 adds an additive static_pca_7 smoke route.  It does not delete or
replace the legacy G_t columns.  It only attaches a 7-axis G_t view so the
existing FullSpec loop can be tested with 7-axis metadata present.
"""
from __future__ import annotations

from typing import Dict
import pandas as pd

from DEPT2_ActionModule_ActuationPrimitives_RC1.pseudo_reality.observation import GtKtBuilder
from dept2_fullspec_runner_rc1.contracts import FullSpecRunnerConfig
from dept2_fullspec_runner_rc1.modules.world_adapter import WorldAdapter, trace_fingerprint

FORBIDDEN_FORMAL_PREFIXES = ("graph_object", "v8_", "final_gate", "action_surface", "ot_", "exploration_", "action_frame")

LEGACY_GT_ROUTE = "legacy"
STATIC_PCA_7_SMOKE_ROUTE = "static_pca_7_smoke"
STATIC_PCA_7_AXIS_COLUMNS = [
    "static_pca7_axis_1_activity_volatility",
    "static_pca7_axis_2_uncertainty_conflict",
    "static_pca7_axis_3_relation_lock_coupling",
    "static_pca7_axis_4_exploration",
    "static_pca7_axis_5_reversibility",
    "static_pca7_axis_6_entropy_overconvergence",
    "static_pca7_axis_7_relation_flow_curl",
]


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
        gt_route = str(getattr(self.cfg, "gt_route", LEGACY_GT_ROUTE) or LEGACY_GT_ROUTE)
        gt = self._apply_gt_route(gt, gt_route)
        kt = self.builder.build_kt_global()
        formal = self.builder.build_formal_packet(gt, kt)

        fp_after = trace_fingerprint(trace)
        if fp_before != fp_after:
            raise RuntimeError("G/K build mutated the input world trace")

        gt = self._annotate_gt(gt, trace_t, fp_before)
        kt = self._annotate_kt(kt, trace_t, fp_before, gt_route)
        formal = self._annotate_formal(formal, trace_t, fp_before, gt_route)
        self.validate_no_lower_leak(formal)

        audit = self.build_audit(gt, kt, formal, trace_t, fp_before, fp_after, loop_step, gt_route)
        return {"gt": gt, "kt": kt, "formal_packet": formal, "gk_build_audit": audit}

    def _apply_gt_route(self, gt: pd.DataFrame, gt_route: str) -> pd.DataFrame:
        if gt is None or gt.empty:
            return pd.DataFrame() if gt is None else gt.copy()
        if gt_route == LEGACY_GT_ROUTE:
            return gt.copy()
        if gt_route != STATIC_PCA_7_SMOKE_ROUTE:
            raise ValueError(f"Unsupported gt_route: {gt_route}")

        out = gt.copy()
        out["static_pca7_axis_1_activity_volatility"] = self._avg(out, "gt_activity", "gt_volatility")
        out["static_pca7_axis_2_uncertainty_conflict"] = self._avg(out, "gt_uncertainty", "gt_conflict")
        out["static_pca7_axis_3_relation_lock_coupling"] = self._avg(out, "gt_relation_lock", "gt_coupling")
        out["static_pca7_axis_4_exploration"] = out["gt_exploration"].astype(float)
        out["static_pca7_axis_5_reversibility"] = out["gt_reversibility"].astype(float)
        out["static_pca7_axis_6_entropy_overconvergence"] = self._avg(out, "gt_entropy", "gt_overconvergence")
        out["static_pca7_axis_7_relation_flow_curl"] = self._avg(out, "gt_relation_curl", "gt_flow_curl")
        out["gt_route_selected"] = STATIC_PCA_7_SMOKE_ROUTE
        out["gt_main_map_name"] = "static_pca_7"
        out["gt_main_component_count"] = 7
        out["legacy_gt_columns_preserved"] = True
        out["static_pca7_view_attached"] = True
        out["static_pca7_axis_count"] = len(STATIC_PCA_7_AXIS_COLUMNS)
        out["static_pca7_connection_scope"] = "fullspec_loop_smoke_only_no_irreversible_replacement"
        out["canonical_write_performed_by_gt_route"] = False
        out["axis_execution_performed_by_gt_route"] = False
        out["legacy_gt_deleted_by_gt_route"] = False
        return out

    @staticmethod
    def _avg(df: pd.DataFrame, left: str, right: str) -> pd.Series:
        return (df[left].astype(float) + df[right].astype(float)) / 2.0

    def _annotate_gt(self, gt: pd.DataFrame, trace_t: int, fp: str) -> pd.DataFrame:
        out = gt.copy()
        out["gk_source_contract"] = self.contract
        out["gk_source_trace_fingerprint"] = fp
        out["gk_source_world_t"] = trace_t
        out["gk_builder_module"] = self.name
        out["gk_writeback_performed"] = False
        return out

    def _annotate_kt(self, kt: pd.DataFrame, trace_t: int, fp: str, gt_route: str) -> pd.DataFrame:
        out = kt.copy()
        out["gk_source_contract"] = self.contract
        out["gk_source_trace_fingerprint"] = fp
        out["gk_source_world_t"] = trace_t
        out["kt_window"] = int(self.cfg.kt_window)
        out["gk_builder_module"] = self.name
        out["gt_route_selected"] = gt_route
        out["gk_writeback_performed"] = False
        return out

    def _annotate_formal(self, formal: pd.DataFrame, trace_t: int, fp: str, gt_route: str) -> pd.DataFrame:
        out = formal.copy()
        out["formal_input_source_contract"] = "formal_input_is_GK_only__no_Ot_no_v8_no_exploration__Task3_RC1"
        out["gk_source_contract"] = self.contract
        out["gk_source_trace_fingerprint"] = fp
        out["gk_source_world_t"] = trace_t
        out["gt_route_selected"] = gt_route
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
        gt_route: str,
    ) -> pd.DataFrame:
        leaked = self._lower_leaks(formal)
        kt_n = int(kt["kt_n_observations"].iloc[0]) if not kt.empty and "kt_n_observations" in kt.columns else 0
        static_cols_present = [c for c in STATIC_PCA_7_AXIS_COLUMNS if c in gt.columns]
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
            "gt_route_selected": gt_route,
            "gt_main_map_name": "static_pca_7" if gt_route == STATIC_PCA_7_SMOKE_ROUTE else "legacy",
            "gt_main_component_count": 7 if gt_route == STATIC_PCA_7_SMOKE_ROUTE else -1,
            "legacy_gt_preserved": True,
            "legacy_gt_deleted": False,
            "static_pca7_view_attached": gt_route == STATIC_PCA_7_SMOKE_ROUTE,
            "static_pca7_axis_count": int(len(static_cols_present)),
            "static_pca7_axis_columns": "|".join(static_cols_present),
            "formal_columns_count": int(len(formal.columns)),
            "formal_lower_leak_count": int(len(leaked)),
            "formal_lower_leak_columns": "|".join(leaked),
            "gk_writeback_performed": False,
            "canonical_world_write_performed": False,
            "axis_execution_performed": False,
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
