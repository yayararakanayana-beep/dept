"""dept_prediction_module: DEPT-side prediction values without action judgment.

The module is intentionally placed on the DEPT side.  It reads DEPT-owned
observation/log artifacts and emits prediction values only.

It does not decide whether something is dangerous, safe, admissible, rejected,
or action-worthy.  Those interpretations belong to later stages.  Its outputs
are current values, projected no-action values, deltas, uncertainty/context
signals, and source lineage.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable
import json

import pandas as pd

from dept2_fullspec_runner_rc1.modules.world_adapter import trace_fingerprint

IDENTITY_COLS = {"entity_id", "source", "target", "t", "scenario", "seed"}
ENTITY_EXCLUDE_PREFIXES = ("gt_", "kt_", "ot_", "v8_", "action_frame", "pressure_intent")
OT_NUMERIC_COLUMNS = [
    "activity",
    "volatility",
    "uncertainty",
    "relation_lock",
    "coupling",
    "exploration",
    "reversibility",
    "entropy",
    "relation_degree",
    "ot_residual_score",
    "ot_noise_score",
    "ot_unresolved_score",
    "ot_ambiguity_score",
    "ot_macro_micro_mismatch_score",
    "ot_boundary_instability_score",
    "ot_local_observation_need_score",
]
RESIDUAL_CONTEXT_COLUMNS = [
    "ot_residual_score",
    "ot_noise_score",
    "ot_unresolved_score",
    "ot_ambiguity_score",
    "ot_macro_micro_mismatch_score",
    "ot_boundary_instability_score",
    "observation_count",
    "active_count",
    "consecutive_active_count",
    "max_noise_score_seen",
    "noise_delta",
    "residual_delta",
]
JUDGMENT_TOKENS = ("risk", "safe", "unsafe", "admit", "reject", "danger", "should_action")


@dataclass(frozen=True)
class PredictionModuleConfig:
    max_unmapped_columns_recorded: int = 64
    include_entity_metric_rows: bool = True
    include_relation_metric_rows: bool = True


def _empty(columns: Iterable[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=list(columns))


def _numeric_columns(df: pd.DataFrame, exclude: set[str] | None = None) -> list[str]:
    if df is None or df.empty:
        return []
    exclude = exclude or set()
    cols: list[str] = []
    for col in df.columns:
        if col in exclude:
            continue
        if any(str(col).startswith(prefix) for prefix in ENTITY_EXCLUDE_PREFIXES):
            continue
        series = pd.to_numeric(df[col], errors="coerce")
        if series.notna().any():
            cols.append(str(col))
    return cols


def _first_world_t(trace: Dict[str, pd.DataFrame] | None) -> int:
    if not trace or "entity_trace" not in trace or trace["entity_trace"].empty or "t" not in trace["entity_trace"].columns:
        return -1
    return int(trace["entity_trace"]["t"].iloc[0])


def _safe_float(value, default: float = 0.0) -> float:
    try:
        out = float(value)
        if pd.isna(out):
            return float(default)
        return out
    except Exception:
        return float(default)


def _json_dict(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


class DEPTPredictionModule:
    name = "dept_prediction_module"

    def __init__(self, cfg: PredictionModuleConfig | None = None):
        self.cfg = cfg or PredictionModuleConfig()

    def build(
        self,
        *,
        world_trace_before: Dict[str, pd.DataFrame] | None,
        baseline_trace_after: Dict[str, pd.DataFrame] | None,
        gt: pd.DataFrame | None,
        kt: pd.DataFrame | None,
        ot_native: pd.DataFrame | None,
        ot_action_view: pd.DataFrame | None,
        residual_noise_log: pd.DataFrame | None,
        loop_step: int,
        seed: int,
        scenario: str,
    ) -> dict[str, pd.DataFrame]:
        entity_projection = self.build_entity_projection(
            world_trace_before=world_trace_before,
            baseline_trace_after=baseline_trace_after,
            ot_action_view=ot_action_view,
            residual_noise_log=residual_noise_log,
            loop_step=loop_step,
            seed=seed,
            scenario=scenario,
        )
        relation_projection = self.build_relation_projection(
            world_trace_before=world_trace_before,
            baseline_trace_after=baseline_trace_after,
            loop_step=loop_step,
            seed=seed,
            scenario=scenario,
        )
        ot_context = self.build_ot_prediction_context(
            ot_native=ot_native,
            ot_action_view=ot_action_view,
            residual_noise_log=residual_noise_log,
            loop_step=loop_step,
            seed=seed,
            scenario=scenario,
        )
        global_summary = self.build_global_prediction_summary(
            world_trace_before=world_trace_before,
            baseline_trace_after=baseline_trace_after,
            gt=gt,
            kt=kt,
            ot_native=ot_native,
            ot_action_view=ot_action_view,
            residual_noise_log=residual_noise_log,
            entity_projection=entity_projection,
            relation_projection=relation_projection,
            ot_context=ot_context,
            loop_step=loop_step,
            seed=seed,
            scenario=scenario,
        )
        output_packet = self.build_prediction_output_packet(global_summary, entity_projection, relation_projection, ot_context)
        return {
            "dept_prediction_entity_projection": entity_projection,
            "dept_prediction_relation_projection": relation_projection,
            "dept_prediction_ot_context": ot_context,
            "dept_prediction_global_summary": global_summary,
            "dept_prediction_output_packet": output_packet,
        }

    def build_entity_projection(
        self,
        *,
        world_trace_before: Dict[str, pd.DataFrame] | None,
        baseline_trace_after: Dict[str, pd.DataFrame] | None,
        ot_action_view: pd.DataFrame | None,
        residual_noise_log: pd.DataFrame | None,
        loop_step: int,
        seed: int,
        scenario: str,
    ) -> pd.DataFrame:
        columns = [
            "loop_step", "run_seed", "run_scenario", "entity_id", "world_t_current", "world_t_projection",
            "metric_name", "current_value", "projected_no_action_value", "projected_no_action_delta",
            "projection_source", "projection_horizon_steps", "ot_id", "ot_identity_key",
            "ot_residual_score", "ot_noise_score", "ot_unresolved_score", "ot_ambiguity_score",
            "ot_macro_micro_mismatch_score", "ot_boundary_instability_score", "noise_delta", "residual_delta",
            "source_trace_fingerprint_current", "source_trace_fingerprint_projection",
        ]
        if not world_trace_before or "entity_trace" not in world_trace_before or world_trace_before["entity_trace"].empty:
            return _empty(columns)
        current = world_trace_before["entity_trace"].copy()
        baseline = baseline_trace_after.get("entity_trace", pd.DataFrame()).copy() if baseline_trace_after else pd.DataFrame()
        world_t_current = _first_world_t(world_trace_before)
        world_t_projection = _first_world_t(baseline_trace_after)
        current_fp = trace_fingerprint(world_trace_before)
        projection_fp = trace_fingerprint(baseline_trace_after) if baseline_trace_after else "missing"

        metric_cols = _numeric_columns(current, exclude=IDENTITY_COLS)
        baseline_lookup = baseline.set_index("entity_id") if not baseline.empty and "entity_id" in baseline.columns else pd.DataFrame()
        ot_lookup = self._latest_by_entity(ot_action_view)
        noise_lookup = self._latest_by_entity(residual_noise_log)
        rows: list[dict] = []
        for _, ent in current.iterrows():
            entity_id = str(ent["entity_id"])
            projected = baseline_lookup.loc[entity_id] if entity_id in baseline_lookup.index else None
            ot = ot_lookup.loc[entity_id] if entity_id in ot_lookup.index else None
            noise = noise_lookup.loc[entity_id] if entity_id in noise_lookup.index else None
            for metric in metric_cols:
                current_value = _safe_float(ent.get(metric))
                if projected is not None and metric in baseline_lookup.columns:
                    projected_value = _safe_float(projected.get(metric), current_value)
                    projection_source = "baseline_no_action_trace"
                    horizon = max(0, world_t_projection - world_t_current)
                else:
                    projected_value = current_value
                    projection_source = "current_value_carried_forward_no_projection_trace"
                    horizon = 0
                rows.append({
                    "loop_step": int(loop_step),
                    "run_seed": int(seed),
                    "run_scenario": str(scenario),
                    "entity_id": entity_id,
                    "world_t_current": int(world_t_current),
                    "world_t_projection": int(world_t_projection),
                    "metric_name": str(metric),
                    "current_value": float(current_value),
                    "projected_no_action_value": float(projected_value),
                    "projected_no_action_delta": float(projected_value - current_value),
                    "projection_source": projection_source,
                    "projection_horizon_steps": int(horizon),
                    "ot_id": "" if ot is None else str(ot.get("ot_id", "")),
                    "ot_identity_key": "" if ot is None else str(ot.get("ot_identity_key", entity_id)),
                    "ot_residual_score": _safe_float(None if ot is None else ot.get("ot_residual_score")),
                    "ot_noise_score": _safe_float(None if noise is None else noise.get("ot_noise_score", None if ot is None else ot.get("ot_noise_score"))),
                    "ot_unresolved_score": _safe_float(None if noise is None else noise.get("ot_unresolved_score", None if ot is None else ot.get("ot_unresolved_score"))),
                    "ot_ambiguity_score": _safe_float(None if noise is None else noise.get("ot_ambiguity_score", None if ot is None else ot.get("ot_ambiguity_score"))),
                    "ot_macro_micro_mismatch_score": _safe_float(None if noise is None else noise.get("ot_macro_micro_mismatch_score", None if ot is None else ot.get("ot_macro_micro_mismatch_score"))),
                    "ot_boundary_instability_score": _safe_float(None if noise is None else noise.get("ot_boundary_instability_score", None if ot is None else ot.get("ot_boundary_instability_score"))),
                    "noise_delta": _safe_float(None if noise is None else noise.get("noise_delta")),
                    "residual_delta": _safe_float(None if noise is None else noise.get("residual_delta")),
                    "source_trace_fingerprint_current": current_fp,
                    "source_trace_fingerprint_projection": projection_fp,
                })
        return pd.DataFrame(rows, columns=columns)

    def build_relation_projection(
        self,
        *,
        world_trace_before: Dict[str, pd.DataFrame] | None,
        baseline_trace_after: Dict[str, pd.DataFrame] | None,
        loop_step: int,
        seed: int,
        scenario: str,
    ) -> pd.DataFrame:
        columns = [
            "loop_step", "run_seed", "run_scenario", "source", "target", "world_t_current", "world_t_projection",
            "relation_metric_name", "current_value", "projected_no_action_value", "projected_no_action_delta",
            "projection_source", "projection_horizon_steps", "source_trace_fingerprint_current", "source_trace_fingerprint_projection",
        ]
        if not world_trace_before or "relation_trace" not in world_trace_before:
            return _empty(columns)
        current = world_trace_before.get("relation_trace", pd.DataFrame()).copy()
        if current.empty:
            return _empty(columns)
        baseline = baseline_trace_after.get("relation_trace", pd.DataFrame()).copy() if baseline_trace_after else pd.DataFrame()
        world_t_current = _first_world_t(world_trace_before)
        world_t_projection = _first_world_t(baseline_trace_after)
        current_fp = trace_fingerprint(world_trace_before)
        projection_fp = trace_fingerprint(baseline_trace_after) if baseline_trace_after else "missing"
        metric_cols = _numeric_columns(current, exclude=IDENTITY_COLS)
        key_cols = ["source", "target"]
        baseline_lookup = baseline.set_index(key_cols) if not baseline.empty and set(key_cols).issubset(baseline.columns) else pd.DataFrame()
        rows: list[dict] = []
        for _, rel in current.iterrows():
            key = (rel["source"], rel["target"])
            projected = baseline_lookup.loc[key] if key in baseline_lookup.index else None
            for metric in metric_cols:
                current_value = _safe_float(rel.get(metric))
                if projected is not None and metric in baseline_lookup.columns:
                    projected_value = _safe_float(projected.get(metric), current_value)
                    projection_source = "baseline_no_action_trace"
                    horizon = max(0, world_t_projection - world_t_current)
                else:
                    projected_value = current_value
                    projection_source = "current_value_carried_forward_no_projection_trace"
                    horizon = 0
                rows.append({
                    "loop_step": int(loop_step),
                    "run_seed": int(seed),
                    "run_scenario": str(scenario),
                    "source": str(rel["source"]),
                    "target": str(rel["target"]),
                    "world_t_current": int(world_t_current),
                    "world_t_projection": int(world_t_projection),
                    "relation_metric_name": str(metric),
                    "current_value": float(current_value),
                    "projected_no_action_value": float(projected_value),
                    "projected_no_action_delta": float(projected_value - current_value),
                    "projection_source": projection_source,
                    "projection_horizon_steps": int(horizon),
                    "source_trace_fingerprint_current": current_fp,
                    "source_trace_fingerprint_projection": projection_fp,
                })
        return pd.DataFrame(rows, columns=columns)

    def build_ot_prediction_context(
        self,
        *,
        ot_native: pd.DataFrame | None,
        ot_action_view: pd.DataFrame | None,
        residual_noise_log: pd.DataFrame | None,
        loop_step: int,
        seed: int,
        scenario: str,
    ) -> pd.DataFrame:
        columns = [
            "loop_step", "run_seed", "run_scenario", "entity_id", "ot_id", "ot_identity_key",
            "context_metric_name", "context_metric_value", "context_source_table", "source_world_t",
        ]
        rows: list[dict] = []
        sources = [
            ("ot_native", ot_native),
            ("ot_action_view", ot_action_view),
            ("residual_noise_log", residual_noise_log),
        ]
        for source_name, df in sources:
            if df is None or df.empty:
                continue
            entity_col = "entity_id" if "entity_id" in df.columns else None
            for _, r in df.iterrows():
                entity_id = str(r.get(entity_col, r.get("ot_identity_key", ""))) if entity_col else str(r.get("ot_identity_key", ""))
                ot_id = str(r.get("ot_id", ""))
                identity = str(r.get("ot_identity_key", entity_id))
                world_t = int(_safe_float(r.get("t", r.get("last_seen_t", -1)), -1))
                for metric in OT_NUMERIC_COLUMNS + RESIDUAL_CONTEXT_COLUMNS:
                    if metric not in df.columns:
                        continue
                    rows.append({
                        "loop_step": int(loop_step),
                        "run_seed": int(seed),
                        "run_scenario": str(scenario),
                        "entity_id": entity_id,
                        "ot_id": ot_id,
                        "ot_identity_key": identity,
                        "context_metric_name": str(metric),
                        "context_metric_value": _safe_float(r.get(metric)),
                        "context_source_table": source_name,
                        "source_world_t": int(world_t),
                    })
        return pd.DataFrame(rows, columns=columns)

    def build_global_prediction_summary(
        self,
        *,
        world_trace_before: Dict[str, pd.DataFrame] | None,
        baseline_trace_after: Dict[str, pd.DataFrame] | None,
        gt: pd.DataFrame | None,
        kt: pd.DataFrame | None,
        ot_native: pd.DataFrame | None,
        ot_action_view: pd.DataFrame | None,
        residual_noise_log: pd.DataFrame | None,
        entity_projection: pd.DataFrame,
        relation_projection: pd.DataFrame,
        ot_context: pd.DataFrame,
        loop_step: int,
        seed: int,
        scenario: str,
    ) -> pd.DataFrame:
        entity = world_trace_before.get("entity_trace", pd.DataFrame()) if world_trace_before else pd.DataFrame()
        relation = world_trace_before.get("relation_trace", pd.DataFrame()) if world_trace_before else pd.DataFrame()
        baseline_entity = baseline_trace_after.get("entity_trace", pd.DataFrame()) if baseline_trace_after else pd.DataFrame()
        baseline_relation = baseline_trace_after.get("relation_trace", pd.DataFrame()) if baseline_trace_after else pd.DataFrame()
        numeric_entity_cols = _numeric_columns(entity, exclude=IDENTITY_COLS)
        numeric_relation_cols = _numeric_columns(relation, exclude=IDENTITY_COLS)
        gt_numeric_cols = _numeric_columns(gt if gt is not None else pd.DataFrame())
        kt_numeric_cols = _numeric_columns(kt if kt is not None else pd.DataFrame())
        unmapped = {
            "entity_columns": [c for c in entity.columns if c not in IDENTITY_COLS and c not in numeric_entity_cols],
            "relation_columns": [c for c in relation.columns if c not in IDENTITY_COLS and c not in numeric_relation_cols],
            "gt_columns": [] if gt is None else [c for c in gt.columns if c not in gt_numeric_cols],
            "kt_columns": [] if kt is None else [c for c in kt.columns if c not in kt_numeric_cols],
        }
        for key in list(unmapped):
            unmapped[key] = list(map(str, unmapped[key]))[: self.cfg.max_unmapped_columns_recorded]
        row = {
            "loop_step": int(loop_step),
            "run_seed": int(seed),
            "run_scenario": str(scenario),
            "prediction_module_name": self.name,
            "prediction_build_status": "pass",
            "source_trace_fingerprint_current": trace_fingerprint(world_trace_before) if world_trace_before else "missing",
            "source_trace_fingerprint_projection": trace_fingerprint(baseline_trace_after) if baseline_trace_after else "missing",
            "world_t_current": _first_world_t(world_trace_before),
            "world_t_projection": _first_world_t(baseline_trace_after),
            "entity_rows_current": int(len(entity)),
            "entity_rows_projection": int(len(baseline_entity)),
            "relation_rows_current": int(len(relation)),
            "relation_rows_projection": int(len(baseline_relation)),
            "gt_rows": int(len(gt)) if gt is not None else 0,
            "kt_rows": int(len(kt)) if kt is not None else 0,
            "ot_native_rows": int(len(ot_native)) if ot_native is not None else 0,
            "ot_action_view_rows": int(len(ot_action_view)) if ot_action_view is not None else 0,
            "residual_noise_log_rows": int(len(residual_noise_log)) if residual_noise_log is not None else 0,
            "entity_projection_rows": int(len(entity_projection)),
            "relation_projection_rows": int(len(relation_projection)),
            "ot_context_rows": int(len(ot_context)),
            "mean_entity_projected_abs_delta": float(entity_projection["projected_no_action_delta"].abs().mean()) if not entity_projection.empty else 0.0,
            "mean_relation_projected_abs_delta": float(relation_projection["projected_no_action_delta"].abs().mean()) if not relation_projection.empty else 0.0,
            "mean_observation_uncertainty": self._mean_ot_metric(ot_context, "uncertainty"),
            "mean_residual_score": self._mean_ot_metric(ot_context, "ot_residual_score"),
            "mean_unresolved_score": self._mean_ot_metric(ot_context, "ot_unresolved_score"),
            "mean_ambiguity_score": self._mean_ot_metric(ot_context, "ot_ambiguity_score"),
            "mean_macro_micro_mismatch_score": self._mean_ot_metric(ot_context, "ot_macro_micro_mismatch_score"),
            "unmapped_information_json": _json_dict(unmapped),
        }
        for col in numeric_entity_cols:
            row[f"current_mean_entity_{col}"] = float(pd.to_numeric(entity[col], errors="coerce").mean())
        for col in numeric_relation_cols:
            row[f"current_mean_relation_{col}"] = float(pd.to_numeric(relation[col], errors="coerce").mean())
        for col in gt_numeric_cols[:24]:
            row[f"source_gt_{col}"] = float(pd.to_numeric(gt[col], errors="coerce").mean()) if gt is not None and col in gt.columns else 0.0
        for col in kt_numeric_cols[:24]:
            row[f"source_kt_{col}"] = float(pd.to_numeric(kt[col], errors="coerce").mean()) if kt is not None and col in kt.columns else 0.0
        return pd.DataFrame([row])

    def build_prediction_output_packet(
        self,
        global_summary: pd.DataFrame,
        entity_projection: pd.DataFrame,
        relation_projection: pd.DataFrame,
        ot_context: pd.DataFrame,
    ) -> pd.DataFrame:
        if global_summary is None or global_summary.empty:
            return pd.DataFrame()
        g = global_summary.iloc[0]
        row = {
            "loop_step": int(g.get("loop_step", -1)),
            "run_seed": int(g.get("run_seed", -1)),
            "run_scenario": str(g.get("run_scenario", "unknown")),
            "prediction_packet_id": f"dept_prediction_packet_s{int(g.get('run_seed', -1))}_t{int(g.get('loop_step', -1))}",
            "source_trace_fingerprint_current": str(g.get("source_trace_fingerprint_current", "missing")),
            "source_trace_fingerprint_projection": str(g.get("source_trace_fingerprint_projection", "missing")),
            "world_t_current": int(g.get("world_t_current", -1)),
            "world_t_projection": int(g.get("world_t_projection", -1)),
            "entity_projection_rows": int(len(entity_projection)),
            "relation_projection_rows": int(len(relation_projection)),
            "ot_context_rows": int(len(ot_context)),
            "mean_entity_projected_abs_delta": float(g.get("mean_entity_projected_abs_delta", 0.0)),
            "mean_relation_projected_abs_delta": float(g.get("mean_relation_projected_abs_delta", 0.0)),
            "mean_observation_uncertainty": float(g.get("mean_observation_uncertainty", 0.0)),
            "mean_residual_score": float(g.get("mean_residual_score", 0.0)),
            "mean_unresolved_score": float(g.get("mean_unresolved_score", 0.0)),
            "mean_ambiguity_score": float(g.get("mean_ambiguity_score", 0.0)),
            "mean_macro_micro_mismatch_score": float(g.get("mean_macro_micro_mismatch_score", 0.0)),
            "packet_content_type": "prediction_values_only_no_action_judgment",
        }
        return pd.DataFrame([row])

    @staticmethod
    def _latest_by_entity(df: pd.DataFrame | None) -> pd.DataFrame:
        if df is None or df.empty or "entity_id" not in df.columns:
            return pd.DataFrame()
        sort_cols = [c for c in ["t", "last_seen_t", "loop_step"] if c in df.columns]
        out = df.copy()
        if sort_cols:
            out = out.sort_values(sort_cols)
        return out.drop_duplicates("entity_id", keep="last").set_index("entity_id")

    @staticmethod
    def _mean_ot_metric(ot_context: pd.DataFrame, metric_name: str) -> float:
        if ot_context is None or ot_context.empty:
            return 0.0
        rows = ot_context[ot_context["context_metric_name"].astype(str) == str(metric_name)]
        if rows.empty:
            return 0.0
        return float(pd.to_numeric(rows["context_metric_value"], errors="coerce").fillna(0.0).mean())


def output_contains_judgment_terms(outputs: dict[str, pd.DataFrame]) -> bool:
    """Test helper: true if emitted table names/columns/values contain judgment tokens."""
    for table_name, df in outputs.items():
        lower_name = str(table_name).lower()
        if any(tok in lower_name for tok in JUDGMENT_TOKENS):
            return True
        if df is None or df.empty:
            continue
        for col in df.columns:
            lower_col = str(col).lower()
            if any(tok in lower_col for tok in JUDGMENT_TOKENS):
                return True
        text_values = df.select_dtypes(include=["object"]).astype(str)
        for value in text_values.to_numpy().flatten().tolist():
            lower_value = str(value).lower()
            if any(tok in lower_value for tok in JUDGMENT_TOKENS):
                return True
    return False
