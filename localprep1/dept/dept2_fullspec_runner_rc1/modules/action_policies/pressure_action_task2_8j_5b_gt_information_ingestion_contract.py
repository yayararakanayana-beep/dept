"""Task 2-8j-5b: fixed-7-axis G_t information-ingestion contract RC1.

Premise:
    The validation setting assumes incomplete observation.  G_t is not a raw data
    warehouse and should not receive all available information.  It receives only
    observable, coarse-grained information groups that are useful for extracting
    macro-game dynamics from the fixed 7-axis effective map.

Purpose:
    Define what kinds of information may enter the fixed static_pca_7 G_t map,
    at what coarse-graining level, and how uncertainty / residuals are handled.

Future real-system note:
    In real systems, raw or already-compressed information may be translated by
    an AI translation layer into relation/distribution records.  That translation
    layer must preserve provenance, confidence, uncertainty, and residual escape
    routes.  This task does not implement that AI layer; it only fixes the v2
    validation ingestion contract.

Boundary:
    - contract creation only
    - no raw-data ingestion implementation
    - no AI translation implementation
    - no effective-dimension re-fitting or axis mutation
    - no residual auxiliary dimension injection into G_t main map
    - no canonical write / runtime policy input / upper-pressure connection
    - no ActionFrame / ActionModule / FullSpec runtime call
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

TASK2_8J_5B_VERSION = "fixed_7axis_gt_information_ingestion_contract_rc1"
TASK2_8J_5B_CONTRACT = (
    "Task2_8j_5b_gt_information_ingestion__incomplete_observation__"
    "coarse_grained_game_structure_inputs__static_pca_7_main_map__no_runtime_write"
)

BOUNDARY_COLUMNS = [
    "task2_8j_5b_version",
    "task2_8j_5b_contract",
    "contract_created",
    "validation_only",
    "incomplete_observation_assumption",
    "gt_main_map_name",
    "gt_main_component_count",
    "runtime_policy_input",
    "fullspec_runtime_connected",
    "upper_pressure_connected",
    "action_frame_created",
    "actionmodule_called",
    "canonical_write_performed",
    "gk_writeback_performed",
    "ot_writeback_performed",
    "ai_translation_implemented",
    "raw_data_ingestion_implemented",
    "axis_refit_performed",
    "axis_mutation_performed",
    "residual_auxiliary_injected_into_gt_main",
    "action_weight_converted",
]

REQUIRED_ALLOWED_GROUP_COLUMNS = BOUNDARY_COLUMNS + [
    "information_group",
    "group_role",
    "example_features",
    "coarse_graining_rule",
    "distribution_payload",
    "required_for_game_structure_extraction",
]

REQUIRED_FORBIDDEN_COLUMNS = BOUNDARY_COLUMNS + [
    "forbidden_input_type",
    "reason",
    "route",
]

REQUIRED_GRANULARITY_COLUMNS = BOUNDARY_COLUMNS + [
    "time_scale",
    "scope",
    "purpose",
    "kept_statistics",
]

REQUIRED_RESIDUAL_COLUMNS = BOUNDARY_COLUMNS + [
    "residual_case",
    "handling_policy",
    "v2_status",
    "v3_status",
]

REQUIRED_FINAL_COLUMNS = BOUNDARY_COLUMNS + [
    "allowed_group_count",
    "forbidden_input_count",
    "granularity_cell_count",
    "residual_policy_count",
    "ingestion_decision",
    "next_task",
]


@dataclass(frozen=True)
class GTInformationIngestionContractConfig:
    gt_main_map_name: str = "static_pca_7"
    gt_main_component_count: int = 7
    time_scales: tuple[str, ...] = ("short", "mid", "long")
    scopes: tuple[str, ...] = ("local", "relation", "global")


def _boundary_payload(cfg: GTInformationIngestionContractConfig | None = None) -> dict:
    cfg = cfg or GTInformationIngestionContractConfig()
    return {
        "task2_8j_5b_version": TASK2_8J_5B_VERSION,
        "task2_8j_5b_contract": TASK2_8J_5B_CONTRACT,
        "contract_created": True,
        "validation_only": True,
        "incomplete_observation_assumption": True,
        "gt_main_map_name": str(cfg.gt_main_map_name),
        "gt_main_component_count": int(cfg.gt_main_component_count),
        "runtime_policy_input": False,
        "fullspec_runtime_connected": False,
        "upper_pressure_connected": False,
        "action_frame_created": False,
        "actionmodule_called": False,
        "canonical_write_performed": False,
        "gk_writeback_performed": False,
        "ot_writeback_performed": False,
        "ai_translation_implemented": False,
        "raw_data_ingestion_implemented": False,
        "axis_refit_performed": False,
        "axis_mutation_performed": False,
        "residual_auxiliary_injected_into_gt_main": False,
        "action_weight_converted": False,
    }


def build_allowed_information_group_table(
    cfg: GTInformationIngestionContractConfig | None = None,
) -> pd.DataFrame:
    cfg = cfg or GTInformationIngestionContractConfig()
    rows = [
        (
            "relation_structure",
            "captures link strength, rigidity, lock-in, and relation-level topology shifts",
            "relation_strength; relation_rigidity; relation_lock; mode_separability",
            "aggregate by relation window and compare short/mid/long drift against K_t",
            "center; spread; direction; persistence; confidence; residual_route",
            True,
        ),
        (
            "coordination_behavior",
            "captures cooperation delay, coordination lag, sharing, and connection behavior",
            "coordination_lag; cooperate_tendency; share_tendency; connect_tendency",
            "keep lag level, change, acceleration, recurrence, and cross-agent dispersion",
            "center; dispersion; directional_change; recurrence; confidence; residual_route",
            True,
        ),
        (
            "resource_pressure",
            "captures depletion, inequality, commons health, and private-resource dispersion",
            "resource_pressure; resource_inequality; private_resource_std; commons_health",
            "coarse-grain as pressure/inequality/health proxies over local/relation/global scope",
            "center; spread; skew; pressure_direction; confidence; residual_route",
            True,
        ),
        (
            "information_quality",
            "captures observable delay, distortion, misread, and visibility-gap proxies",
            "information_quality; information_delay; information_distortion; misread_probability; observed_vs_hidden_gap_proxy",
            "treat as observable proxy signals, not hidden-truth inputs; preserve uncertainty",
            "center; uncertainty; degradation_direction; persistence; confidence; residual_route",
            True,
        ),
        (
            "action_tendency",
            "captures behavioral pressure such as hoarding, extraction, defense, amplification, and exploration",
            "hoard_tendency; extract_tendency; defend_tendency; amplify_tendency; explore_tendency",
            "aggregate tendencies by entity mix and relation context without using future outcomes",
            "center; spread; tendency_shift; imbalance; confidence; residual_route",
            True,
        ),
        (
            "effect_and_side_effect_proxy",
            "captures observable effect proxies and reversible/irreversible side-effect tendencies",
            "trust_delta; fatigue_delta; hidden_damage_delta; reversibility_delta; exploitation_risk_delta",
            "use as observed proxy deltas; never as direct action weights or hidden-truth labels",
            "delta_center; delta_spread; harm_direction; reversibility; confidence; residual_route",
            True,
        ),
        (
            "history_change",
            "captures change, acceleration, persistence, recurrence, reversal, and recovery signals",
            "delta; acceleration; persistence; recurrence; reversal; recovery_proxy",
            "derive from K_t comparison across short/mid/long windows",
            "velocity; acceleration; persistence; recurrence; confidence; residual_route",
            True,
        ),
    ]
    out = []
    for group, role, examples, rule, payload, required in rows:
        out.append(
            {
                **_boundary_payload(cfg),
                "information_group": group,
                "group_role": role,
                "example_features": examples,
                "coarse_graining_rule": rule,
                "distribution_payload": payload,
                "required_for_game_structure_extraction": bool(required),
            }
        )
    return pd.DataFrame(out, columns=REQUIRED_ALLOWED_GROUP_COLUMNS)


def build_forbidden_input_table(
    cfg: GTInformationIngestionContractConfig | None = None,
) -> pd.DataFrame:
    cfg = cfg or GTInformationIngestionContractConfig()
    rows = [
        ("full_raw_logs", "G_t is a coarse-grained distribution field, not a raw data warehouse.", "raw_log_archive_or_residual_source"),
        ("hidden_truth", "Hidden truth would leak unavailable state into the validation map.", "forbidden"),
        ("future_information", "Future information breaks causal validation.", "forbidden"),
        ("posthoc_correct_answer_labels", "Post-hoc labels are evaluation targets, not observation inputs.", "forbidden"),
        ("one_off_local_noise", "Single unpersistent noise should not be promoted to G_t main structure.", "residual_buffer"),
        ("unbounded_ai_interpretation", "AI translation must be constrained by provenance, confidence, and schema.", "future_ai_translation_contract"),
        ("direct_action_weights", "G_t ingestion must not create action policy or pressure weights.", "forbidden"),
        ("axis_mutation_request", "The fixed 7-axis map must not be changed during ingestion.", "future_dimension_update_review"),
    ]
    out = []
    for item, reason, route in rows:
        out.append(
            {
                **_boundary_payload(cfg),
                "forbidden_input_type": item,
                "reason": reason,
                "route": route,
            }
        )
    return pd.DataFrame(out, columns=REQUIRED_FORBIDDEN_COLUMNS)


def build_granularity_contract_table(
    cfg: GTInformationIngestionContractConfig | None = None) -> pd.DataFrame:
    cfg = cfg or GTInformationIngestionContractConfig()
    purpose_by_time = {
        "short": "detect immediate shift, shock, reversal, and local instability",
        "mid": "detect sustained coordination lag, relation lock, and pressure accumulation",
        "long": "detect structural bias, resource degradation, information decay, and recovery failure",
    }
    purpose_by_scope = {
        "local": "entity-level or local-state coarse signal",
        "relation": "pair/group relation signal and topology distortion",
        "global": "system-wide macro-game condition",
    }
    stats_by_time = {
        "short": "current_value; delta; local_variance; confidence",
        "mid": "moving_mean; acceleration; persistence; dispersion; confidence",
        "long": "trend; recurrence; skew; recovery_failure; confidence",
    }
    out = []
    for time_scale in cfg.time_scales:
        for scope in cfg.scopes:
            out.append(
                {
                    **_boundary_payload(cfg),
                    "time_scale": str(time_scale),
                    "scope": str(scope),
                    "purpose": f"{purpose_by_time.get(time_scale, 'coarse temporal reading')} / {purpose_by_scope.get(scope, 'coarse scope reading')}",
                    "kept_statistics": stats_by_time.get(time_scale, "center; spread; direction; confidence"),
                }
            )
    return pd.DataFrame(out, columns=REQUIRED_GRANULARITY_COLUMNS)


def build_residual_policy_table(cfg: GTInformationIngestionContractConfig | None = None) -> pd.DataFrame:
    cfg = cfg or GTInformationIngestionContractConfig()
    rows = [
        (
            "information_not_explainable_by_static_pca_7",
            "do_not_force_into_G_t_main; preserve as residual-side evidence with provenance and confidence",
            "audit_only_not_main_validation_input",
            "recommended_for_O_t_residual_and_exploration_candidate_generation",
        ),
        (
            "persistent_recurrent_residual_pattern",
            "track recurrence and concentration before proposing future dimension-update review",
            "record_as_future_review_signal_only",
            "candidate_for_pseudo_open_system_residual_auxiliary_dimension",
        ),
        (
            "low_confidence_ai_translation",
            "store uncertainty and avoid main-map overcommitment",
            "not_applicable_in_v2_no_ai_translation",
            "route_to_AI_translation_audit_and_residual_buffer",
        ),
        (
            "one_time_noise_or_unstable_artifact",
            "buffer but do not promote to main distribution structure",
            "residual_buffer_only",
            "residual_buffer_only_until_persistence_is_established",
        ),
    ]
    out = []
    for case, policy, v2_status, v3_status in rows:
        out.append(
            {
                **_boundary_payload(cfg),
                "residual_case": case,
                "handling_policy": policy,
                "v2_status": v2_status,
                "v3_status": v3_status,
            }
        )
    return pd.DataFrame(out, columns=REQUIRED_RESIDUAL_COLUMNS)


def build_final_summary(
    allowed: pd.DataFrame,
    forbidden: pd.DataFrame,
    granularity: pd.DataFrame,
    residual: pd.DataFrame,
    cfg: GTInformationIngestionContractConfig | None = None,
) -> pd.DataFrame:
    cfg = cfg or GTInformationIngestionContractConfig()
    row = {
        **_boundary_payload(cfg),
        "allowed_group_count": int(len(allowed)) if allowed is not None else 0,
        "forbidden_input_count": int(len(forbidden)) if forbidden is not None else 0,
        "granularity_cell_count": int(len(granularity)) if granularity is not None else 0,
        "residual_policy_count": int(len(residual)) if residual is not None else 0,
        "ingestion_decision": "use_observable_coarse_grained_game_structure_information_for_static_pca_7_gt",
        "next_task": "Task 2-8j-6: fixed-7-axis macro-game dynamics extraction validation",
    }
    return pd.DataFrame([row], columns=REQUIRED_FINAL_COLUMNS)


def validate_gt_information_ingestion_contract_tables(
    allowed: pd.DataFrame,
    forbidden: pd.DataFrame,
    granularity: pd.DataFrame,
    residual: pd.DataFrame,
    final_summary: pd.DataFrame,
    cfg: GTInformationIngestionContractConfig | None = None,
) -> list[str]:
    cfg = cfg or GTInformationIngestionContractConfig()
    errors: list[str] = []
    tables = {
        "allowed": (allowed, REQUIRED_ALLOWED_GROUP_COLUMNS),
        "forbidden": (forbidden, REQUIRED_FORBIDDEN_COLUMNS),
        "granularity": (granularity, REQUIRED_GRANULARITY_COLUMNS),
        "residual": (residual, REQUIRED_RESIDUAL_COLUMNS),
        "final_summary": (final_summary, REQUIRED_FINAL_COLUMNS),
    }
    forbidden_true_columns = [
        "runtime_policy_input",
        "fullspec_runtime_connected",
        "upper_pressure_connected",
        "action_frame_created",
        "actionmodule_called",
        "canonical_write_performed",
        "gk_writeback_performed",
        "ot_writeback_performed",
        "ai_translation_implemented",
        "raw_data_ingestion_implemented",
        "axis_refit_performed",
        "axis_mutation_performed",
        "residual_auxiliary_injected_into_gt_main",
        "action_weight_converted",
    ]
    for name, (table, required) in tables.items():
        if table is None or table.empty:
            errors.append(f"task2_8j_5b_empty_table:{name}")
            continue
        missing = [col for col in required if col not in table.columns]
        if missing:
            errors.append(f"task2_8j_5b_missing_columns:{name}:" + ",".join(missing))
            continue
        for col in ["contract_created", "validation_only", "incomplete_observation_assumption"]:
            if not bool(table[col].astype(bool).all()):
                errors.append(f"task2_8j_5b_required_true_not_all_true:{name}:{col}")
        if set(table["gt_main_map_name"].astype(str)) != {str(cfg.gt_main_map_name)}:
            errors.append(f"task2_8j_5b_wrong_gt_main_map_name:{name}")
        if set(table["gt_main_component_count"].astype(int)) != {int(cfg.gt_main_component_count)}:
            errors.append(f"task2_8j_5b_wrong_gt_main_component_count:{name}")
        for col in forbidden_true_columns:
            if bool(table[col].astype(bool).any()):
                errors.append(f"task2_8j_5b_forbidden_true:{name}:{col}")
    if allowed is not None and not allowed.empty:
        required_groups = {
            "relation_structure",
            "coordination_behavior",
            "resource_pressure",
            "information_quality",
            "action_tendency",
            "effect_and_side_effect_proxy",
            "history_change",
        }
        groups = set(allowed["information_group"].astype(str))
        missing_groups = sorted(required_groups - groups)
        if missing_groups:
            errors.append("task2_8j_5b_missing_allowed_groups:" + ",".join(missing_groups))
        if not bool(allowed["required_for_game_structure_extraction"].astype(bool).all()):
            errors.append("task2_8j_5b_allowed_group_not_required_for_game_structure")
    if forbidden is not None and not forbidden.empty:
        required_forbidden = {"hidden_truth", "future_information", "full_raw_logs", "unbounded_ai_interpretation"}
        got = set(forbidden["forbidden_input_type"].astype(str))
        missing_forbidden = sorted(required_forbidden - got)
        if missing_forbidden:
            errors.append("task2_8j_5b_missing_forbidden_inputs:" + ",".join(missing_forbidden))
    if granularity is not None and not granularity.empty:
        expected_cells = len(cfg.time_scales) * len(cfg.scopes)
        if len(granularity) != expected_cells:
            errors.append("task2_8j_5b_wrong_granularity_cell_count")
    if final_summary is not None and not final_summary.empty:
        decision = str(final_summary["ingestion_decision"].iloc[0])
        if "coarse_grained_game_structure" not in decision:
            errors.append("task2_8j_5b_wrong_ingestion_decision")
    return errors


def build_and_validate_gt_information_ingestion_contract(
    cfg: GTInformationIngestionContractConfig | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, list[str], dict]:
    cfg = cfg or GTInformationIngestionContractConfig()
    allowed = build_allowed_information_group_table(cfg)
    forbidden = build_forbidden_input_table(cfg)
    granularity = build_granularity_contract_table(cfg)
    residual = build_residual_policy_table(cfg)
    final_summary = build_final_summary(allowed, forbidden, granularity, residual, cfg)
    errors = validate_gt_information_ingestion_contract_tables(allowed, forbidden, granularity, residual, final_summary, cfg)
    summary = {
        "gt_main_map_name": str(cfg.gt_main_map_name),
        "gt_main_component_count": int(cfg.gt_main_component_count),
        "incomplete_observation_assumption": True,
        "allowed_group_count": int(len(allowed)),
        "forbidden_input_count": int(len(forbidden)),
        "granularity_cell_count": int(len(granularity)),
        "residual_policy_count": int(len(residual)),
        "ai_translation_implemented": False,
        "raw_data_ingestion_implemented": False,
        "axis_mutation_performed": False,
        "ingestion_decision": str(final_summary["ingestion_decision"].iloc[0]),
        "validation_errors": errors,
    }
    return allowed, forbidden, granularity, residual, final_summary, errors, summary
