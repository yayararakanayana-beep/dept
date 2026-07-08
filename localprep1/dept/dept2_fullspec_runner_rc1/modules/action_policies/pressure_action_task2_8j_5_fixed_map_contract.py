"""Task 2-8j-5: effective-dimension fixed-map contract RC1.

Decision:
    Use static PCA 7 as the provisional fixed effective-dimension map for
    subsequent validation work.

Interpretation:
    G_t main map is fixed to 7 axes.  The 6-axis map remains a stability
    reference / fallback baseline.  The 3-axis map remains a lightweight coarse
    monitoring reference.  The 8-axis map is not used as the main validation map.

V3 note:
    Do not expand G_t main axes by default.  For a future pseudo-open v3 system,
    keep G_t at fixed 7 axes and manage unexplained components as residual-side
    auxiliary information for O_t residual / exploration-candidate generation.

Boundary:
    - contract creation only
    - no canonical write
    - no runtime policy input
    - no upper-pressure connection
    - no ActionFrame / ActionModule / FullSpec runtime call
    - no action-weight conversion
    - no production adoption
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

TASK2_8J_5_VERSION = "effective_dimension_fixed_map_contract_rc1"
TASK2_8J_5_CONTRACT = (
    "Task2_8j_5_fixed_map_contract__static_pca_7_provisional_validation_fixed__"
    "6_axis_baseline_3_axis_lightweight_8_axis_reference__no_runtime_write"
)

BOUNDARY_COLUMNS = [
    "task2_8j_5_version",
    "task2_8j_5_contract",
    "contract_created",
    "validation_fixed_map_contract",
    "runtime_policy_input",
    "fullspec_runtime_connected",
    "upper_pressure_connected",
    "action_frame_created",
    "actionmodule_called",
    "canonical_write_performed",
    "gk_writeback_performed",
    "ot_writeback_performed",
    "action_weight_converted",
    "production_adoption_performed",
]

REQUIRED_FIXED_MAP_COLUMNS = BOUNDARY_COLUMNS + [
    "gt_main_component_count",
    "gt_main_map_name",
    "fixed_map_status",
    "fixed_map_scope",
    "standard_baseline_component_count",
    "lightweight_reference_component_count",
    "extra_reference_component_count",
    "six_axis_role",
    "three_axis_role",
    "eight_axis_role",
    "residual_auxiliary_dimension_policy",
    "residual_auxiliary_dimension_scope",
    "v2_residual_auxiliary_status",
    "v3_residual_auxiliary_status",
]

REQUIRED_EVIDENCE_COLUMNS = BOUNDARY_COLUMNS + [
    "evidence_task",
    "evidence_name",
    "evidence_value",
    "evidence_interpretation",
    "supports_7_axis_fixed_map",
]

REQUIRED_FINAL_COLUMNS = BOUNDARY_COLUMNS + [
    "gt_main_component_count",
    "fixed_map_decision",
    "fixed_map_reason",
    "production_freeze_performed",
    "next_task",
]


@dataclass(frozen=True)
class FixedMapContractConfig:
    gt_main_component_count: int = 7
    standard_baseline_component_count: int = 6
    lightweight_reference_component_count: int = 3
    extra_reference_component_count: int = 8
    fixed_map_scope: str = "subsequent_validation_only"


def _boundary_payload() -> dict:
    return {
        "task2_8j_5_version": TASK2_8J_5_VERSION,
        "task2_8j_5_contract": TASK2_8J_5_CONTRACT,
        "contract_created": True,
        "validation_fixed_map_contract": True,
        "runtime_policy_input": False,
        "fullspec_runtime_connected": False,
        "upper_pressure_connected": False,
        "action_frame_created": False,
        "actionmodule_called": False,
        "canonical_write_performed": False,
        "gk_writeback_performed": False,
        "ot_writeback_performed": False,
        "action_weight_converted": False,
        "production_adoption_performed": False,
    }


def build_fixed_map_contract_table(cfg: FixedMapContractConfig | None = None) -> pd.DataFrame:
    cfg = cfg or FixedMapContractConfig()
    row = {
        **_boundary_payload(),
        "gt_main_component_count": int(cfg.gt_main_component_count),
        "gt_main_map_name": "static_pca_7",
        "fixed_map_status": "provisional_validation_fixed",
        "fixed_map_scope": str(cfg.fixed_map_scope),
        "standard_baseline_component_count": int(cfg.standard_baseline_component_count),
        "lightweight_reference_component_count": int(cfg.lightweight_reference_component_count),
        "extra_reference_component_count": int(cfg.extra_reference_component_count),
        "six_axis_role": "old_standard_stability_baseline_and_fallback_reference",
        "three_axis_role": "lightweight_coarse_monitoring_reference",
        "eight_axis_role": "extra_reference_not_main_validation_map",
        "residual_auxiliary_dimension_policy": "keep_gt_main_7_axes_and_manage_unexplained_residuals_separately",
        "residual_auxiliary_dimension_scope": "ot_residual_and_future_v3_exploration_candidate_generation_only",
        "v2_residual_auxiliary_status": "not_required_for_main_validation",
        "v3_residual_auxiliary_status": "recommended_for_pseudo_open_system_residual_audit",
    }
    return pd.DataFrame([row], columns=REQUIRED_FIXED_MAP_COLUMNS)


def build_fixed_map_evidence_table() -> pd.DataFrame:
    rows = [
        (
            "Task2-8j-4",
            "structure_reidentification_delta_7_minus_6",
            "+0.211849",
            "7-axis map beats 6-axis map on structure re-identification.",
            True,
        ),
        (
            "Task2-8j-4b",
            "multi_scenario_decision",
            "no_clear_multi_scenario_gap",
            "Multi-scenario coarse labels do not reject 7-axis; no clear 6-axis advantage.",
            True,
        ),
        (
            "Task2-8j-4c",
            "stability_delta_7_minus_6",
            "-0.024925",
            "7-axis has small stability cost; treated as acceptable noise for macro-game extraction.",
            True,
        ),
        (
            "Task2-8j-4d",
            "seventh_axis_decision",
            "seventh_axis_has_interpretable_residual_value",
            "7th axis rescues interpretable residuals, especially coordination lag and information-quality residuals.",
            True,
        ),
        (
            "Task2-8j-4e",
            "negative_control_decision",
            "negative_control_no_leakage_detected",
            "Strict hidden/future leakage audit passes after distinguishing observable hidden-proxy features from hidden-truth input.",
            True,
        ),
    ]
    out = []
    for task, name, value, interpretation, supports in rows:
        out.append(
            {
                **_boundary_payload(),
                "evidence_task": task,
                "evidence_name": name,
                "evidence_value": value,
                "evidence_interpretation": interpretation,
                "supports_7_axis_fixed_map": bool(supports),
            }
        )
    return pd.DataFrame(out, columns=REQUIRED_EVIDENCE_COLUMNS)


def build_fixed_map_final_summary(cfg: FixedMapContractConfig | None = None) -> pd.DataFrame:
    cfg = cfg or FixedMapContractConfig()
    row = {
        **_boundary_payload(),
        "gt_main_component_count": int(cfg.gt_main_component_count),
        "fixed_map_decision": "use_static_pca_7_as_provisional_fixed_gt_main_map_for_validation",
        "fixed_map_reason": (
            "7-axis preserves the macro-game signal needed for coordination-lag, information-quality, "
            "and relation/residual reading; its small stability cost is treated as acceptable noise "
            "that can be reduced during later macro-dynamics coarse-graining."
        ),
        "production_freeze_performed": False,
        "next_task": "Task 2-8j-6: fixed-7-axis macro-game dynamics extraction validation",
    }
    return pd.DataFrame([row], columns=REQUIRED_FINAL_COLUMNS)


def validate_fixed_map_contract_tables(
    fixed_map: pd.DataFrame,
    evidence: pd.DataFrame,
    final_summary: pd.DataFrame,
    cfg: FixedMapContractConfig | None = None,
) -> list[str]:
    cfg = cfg or FixedMapContractConfig()
    errors: list[str] = []
    tables = {
        "fixed_map": (fixed_map, REQUIRED_FIXED_MAP_COLUMNS),
        "evidence": (evidence, REQUIRED_EVIDENCE_COLUMNS),
        "final_summary": (final_summary, REQUIRED_FINAL_COLUMNS),
    }
    for name, (table, required) in tables.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_5_empty_table:{name}")
            continue
        missing = [col for col in required if col not in table.columns]
        if missing:
            errors.append(f"task2_8j_5_missing_columns:{name}:" + ",".join(missing))
            continue
        if not bool(table["contract_created"].astype(bool).all()):
            errors.append(f"task2_8j_5_contract_not_created:{name}")
        if not bool(table["validation_fixed_map_contract"].astype(bool).all()):
            errors.append(f"task2_8j_5_validation_contract_not_true:{name}")
        for col in [
            "runtime_policy_input",
            "fullspec_runtime_connected",
            "upper_pressure_connected",
            "action_frame_created",
            "actionmodule_called",
            "canonical_write_performed",
            "gk_writeback_performed",
            "ot_writeback_performed",
            "action_weight_converted",
            "production_adoption_performed",
        ]:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_5_forbidden_true:{name}:{col}")
    if fixed_map is not None and not fixed_map.empty:
        if int(fixed_map["gt_main_component_count"].iloc[0]) != int(cfg.gt_main_component_count):
            errors.append("task2_8j_5_wrong_gt_main_component_count")
        if str(fixed_map["gt_main_map_name"].iloc[0]) != "static_pca_7":
            errors.append("task2_8j_5_wrong_gt_main_map_name")
    if evidence is not None and not evidence.empty:
        if not bool(evidence["supports_7_axis_fixed_map"].astype(bool).all()):
            errors.append("task2_8j_5_evidence_not_all_supportive")
    if final_summary is not None and not final_summary.empty:
        if bool(final_summary["production_freeze_performed"].astype(bool).any()):
            errors.append("task2_8j_5_production_freeze_performed_true")
    return errors


def build_and_validate_fixed_map_contract(
    cfg: FixedMapContractConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    cfg = cfg or FixedMapContractConfig()
    fixed_map = build_fixed_map_contract_table(cfg)
    evidence = build_fixed_map_evidence_table()
    final_summary = build_fixed_map_final_summary(cfg)
    errors = validate_fixed_map_contract_tables(fixed_map, evidence, final_summary, cfg)
    summary = {
        "gt_main_component_count": int(cfg.gt_main_component_count),
        "gt_main_map_name": "static_pca_7",
        "fixed_map_status": "provisional_validation_fixed",
        "standard_baseline_component_count": int(cfg.standard_baseline_component_count),
        "residual_auxiliary_dimension_policy": str(fixed_map["residual_auxiliary_dimension_policy"].iloc[0]),
        "production_freeze_performed": False,
        "canonical_write_performed": False,
        "validation_errors": errors,
    }
    return fixed_map, evidence, final_summary, errors, summary
