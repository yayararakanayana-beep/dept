"""Task2-8j-26: FullSpec Task2-8j integration bridge.

This module is the first runtime-adjacent bridge between the current FullSpec
loop and the Task2-8j material chain through Task2-8j-24.

It deliberately runs inside the FullSpec cycle and records Task2-8j-24 material
as FullSpec artifacts.  It does not yet replace the existing O_t route,
ActionSurfacePlanning, ActionFrame construction, canonical writeback, or axis
execution.  Those are later integration steps.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from dept2_fullspec_runner_rc1.modules.action_policies.pressure_action_task2_8j_24_terrain_operator_selection_dry_run import (
    TerrainOperatorSelectionDryRunConfig,
    build_and_validate_terrain_operator_selection_dry_run,
)

TASK2_8J_26_VERSION = "fullspec_task2_8j_integration_bridge_rc1"
TASK2_8J_26_CONTRACT = (
    "Task2_8j_26_FullSpec_bridge__static_pca_7_gt_route__"
    "task2_8j_24_material_chain_loaded_inside_fullspec_cycle__"
    "no_action_surface_replacement_no_canonical_write_no_axis_execution"
)


@dataclass(frozen=True)
class Task2_8jFullSpecIntegrationBridgeConfig:
    require_static_pca7_gt: bool = True
    require_task24_ready: bool = True


class Task2_8jFullSpecIntegrationBridge:
    name = "task2_8j_fullspec_integration_bridge"

    def __init__(self, cfg: Task2_8jFullSpecIntegrationBridgeConfig | None = None):
        self.cfg = cfg or Task2_8jFullSpecIntegrationBridgeConfig()

    def build(
        self,
        *,
        gt: pd.DataFrame,
        kt: pd.DataFrame,
        formal_packet: pd.DataFrame,
        ot_action_view: pd.DataFrame,
        pressure_intent_bundle: pd.DataFrame,
        loop_step: int,
    ) -> dict[str, pd.DataFrame]:
        selection, review, checks, final_summary, errors, summary = build_and_validate_terrain_operator_selection_dry_run(
            cfg=TerrainOperatorSelectionDryRunConfig()
        )

        bridge_audit = self._build_bridge_audit(
            gt=gt,
            kt=kt,
            formal_packet=formal_packet,
            ot_action_view=ot_action_view,
            pressure_intent_bundle=pressure_intent_bundle,
            selection=selection,
            review=review,
            checks=checks,
            final_summary=final_summary,
            errors=errors,
            summary=summary,
            loop_step=loop_step,
        )

        selection = self._annotate(selection, gt, loop_step, "task2_8j_24_operator_selection_material")
        review = self._annotate(review, gt, loop_step, "task2_8j_24_operator_review_material")
        checks = self._annotate(checks, gt, loop_step, "task2_8j_24_operator_check_material")
        final_summary = self._annotate(final_summary, gt, loop_step, "task2_8j_24_operator_summary_material")

        return {
            "task2_8j_bridge_audit": bridge_audit,
            "task2_8j_operator_selection": selection,
            "task2_8j_operator_review": review,
            "task2_8j_operator_checks": checks,
            "task2_8j_operator_summary": final_summary,
        }

    def _build_bridge_audit(
        self,
        *,
        gt: pd.DataFrame,
        kt: pd.DataFrame,
        formal_packet: pd.DataFrame,
        ot_action_view: pd.DataFrame,
        pressure_intent_bundle: pd.DataFrame,
        selection: pd.DataFrame,
        review: pd.DataFrame,
        checks: pd.DataFrame,
        final_summary: pd.DataFrame,
        errors: list[str],
        summary: dict[str, Any],
        loop_step: int,
    ) -> pd.DataFrame:
        gt_route = self._first_text(gt, "gt_route_selected", "missing")
        gt_map = self._first_text(gt, "gt_main_map_name", "legacy")
        gt_components = self._first_int(gt, "gt_main_component_count", -1)
        static_view = self._first_bool(gt, "static_pca7_view_attached", False)
        legacy_preserved = self._first_bool(gt, "legacy_gt_columns_preserved", False)
        formal_contains_ot = self._first_bool(formal_packet, "formal_contains_ot", False)
        formal_contains_exploration = self._first_bool(formal_packet, "formal_contains_exploration", False)
        task24_decision = str(summary.get("terrain_operator_selection_dry_run_decision", ""))
        checks_passed = bool(checks is not None and not checks.empty and (checks["check_status"].astype(str) == "pass").all())
        task24_ready = bool(len(errors) == 0 and task24_decision == "terrain_operator_selection_dry_run_ready")
        static_ready = bool(gt_map == "static_pca_7" and gt_components == 7 and static_view)
        bridge_ready = bool((static_ready or not self.cfg.require_static_pca7_gt) and (task24_ready or not self.cfg.require_task24_ready) and checks_passed)

        row = {
            "task2_8j_26_version": TASK2_8J_26_VERSION,
            "task2_8j_26_contract": TASK2_8J_26_CONTRACT,
            "loop_step": int(loop_step),
            "fullspec_loop_connected": True,
            "fullspec_bridge_enabled": True,
            "task2_8j_24_material_chain_loaded": True,
            "task2_8j_24_material_connected_inside_fullspec_cycle": True,
            "gt_route_selected": gt_route,
            "gt_main_map_name": gt_map,
            "gt_main_component_count": int(gt_components),
            "static_pca7_view_attached": bool(static_view),
            "legacy_gt_preserved": bool(legacy_preserved),
            "legacy_gt_deleted": False,
            "fullspec_gt_rows": self._row_count(gt),
            "fullspec_kt_rows": self._row_count(kt),
            "formal_packet_rows": self._row_count(formal_packet),
            "ot_action_view_rows": self._row_count(ot_action_view),
            "pressure_intent_rows": self._row_count(pressure_intent_bundle),
            "operator_selection_rows": self._row_count(selection),
            "operator_review_rows": self._row_count(review),
            "operator_check_rows": self._row_count(checks),
            "operator_summary_rows": self._row_count(final_summary),
            "task2_8j_24_decision": task24_decision,
            "task2_8j_24_ready": bool(task24_ready),
            "task2_8j_24_error_count": int(len(errors)),
            "task2_8j_24_errors": "|".join(errors),
            "task2_8j_24_checks_passed": bool(checks_passed),
            "formal_contains_ot": bool(formal_contains_ot),
            "formal_contains_exploration": bool(formal_contains_exploration),
            "action_surface_replaced_by_task2_8j": False,
            "action_candidates_replaced_by_task2_8j": False,
            "action_frame_replaced_by_task2_8j": False,
            "canonical_write_performed_by_bridge": False,
            "axis_execution_performed_by_bridge": False,
            "real_actionmodule_called_by_bridge": False,
            "direct_dept_read_by_actionmodule": False,
            "bridge_status": "pass" if bridge_ready else "fail",
            "next_task": "Task2-8j-27: feed Task2-8j material into existing ActionSurfacePlanning as a guarded optional input",
        }
        return pd.DataFrame([row])

    def _annotate(self, df: pd.DataFrame, gt: pd.DataFrame, loop_step: int, role: str) -> pd.DataFrame:
        out = pd.DataFrame() if df is None else df.copy()
        if out.empty:
            return out
        out["task2_8j_26_version"] = TASK2_8J_26_VERSION
        out["task2_8j_26_bridge_role"] = role
        out["fullspec_loop_connected"] = True
        out["fullspec_loop_step"] = int(loop_step)
        out["fullspec_gt_route_selected"] = self._first_text(gt, "gt_route_selected", "missing")
        out["fullspec_gt_main_map_name"] = self._first_text(gt, "gt_main_map_name", "legacy")
        out["fullspec_gt_main_component_count"] = self._first_int(gt, "gt_main_component_count", -1)
        out["fullspec_static_pca7_view_attached"] = self._first_bool(gt, "static_pca7_view_attached", False)
        out["legacy_gt_deleted_by_bridge"] = False
        out["canonical_write_performed_by_bridge"] = False
        out["axis_execution_performed_by_bridge"] = False
        out["real_actionmodule_called_by_bridge"] = False
        return out

    @staticmethod
    def _row_count(df: pd.DataFrame | None) -> int:
        return int(len(df)) if df is not None else 0

    @staticmethod
    def _first_text(df: pd.DataFrame | None, col: str, default: str) -> str:
        if df is None or df.empty or col not in df.columns:
            return default
        return str(df[col].iloc[0])

    @staticmethod
    def _first_int(df: pd.DataFrame | None, col: str, default: int) -> int:
        if df is None or df.empty or col not in df.columns:
            return int(default)
        try:
            return int(df[col].iloc[0])
        except Exception:
            return int(default)

    @staticmethod
    def _first_bool(df: pd.DataFrame | None, col: str, default: bool) -> bool:
        if df is None or df.empty or col not in df.columns:
            return bool(default)
        try:
            return bool(df[col].iloc[0])
        except Exception:
            return bool(default)
