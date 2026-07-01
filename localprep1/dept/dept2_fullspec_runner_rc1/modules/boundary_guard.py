"""boundary_guard: unified invariant checks for Task15.

Task15 turns the accumulated per-module boundary checks into a first-class
boundary guard module.  The guard remains diagnostic-only: it reads module
audits, emits a per-cycle boundary_guard_audit and optional violation report,
and never writes to world, G/K, O_t, ActionFrame, or canonical parameters.
"""
from __future__ import annotations

import pandas as pd


def _rows(df: pd.DataFrame | None) -> int:
    return int(len(df)) if df is not None else 0


def _first_bool(df: pd.DataFrame | None, col: str, default: bool = False) -> bool:
    if df is None or df.empty or col not in df.columns:
        return bool(default)
    try:
        return bool(df[col].iloc[0])
    except Exception:
        return bool(default)


def _any_bool(df: pd.DataFrame | None, col: str, default: bool = False) -> bool:
    if df is None or df.empty or col not in df.columns:
        return bool(default)
    try:
        return bool(df[col].astype(bool).any())
    except Exception:
        return bool(default)


def _first_text(df: pd.DataFrame | None, col: str, default: str = "missing") -> str:
    if df is None or df.empty or col not in df.columns:
        return default
    return str(df[col].iloc[0])


def _first_int(df: pd.DataFrame | None, col: str, default: int = 0) -> int:
    if df is None or df.empty or col not in df.columns:
        return int(default)
    try:
        return int(df[col].fillna(default).iloc[0])
    except Exception:
        return int(default)

REQUIRED_AUDIT_FIELDS = [
    "run_seed", "run_scenario", "loop_step",
    "world_trace_audit_rows", "world_transition_audit_rows",
    "gt_rows", "kt_rows", "formal_packet_rows", "gk_build_audit_rows",
    "ot_rows", "ot_observation_audit_rows", "residual_noise_rows", "residual_noise_ledger_audit_rows",
    "m_rows", "pressure_rows", "upper_pressure_audit_rows", "h11_rows", "intent_rows", "pressure_translation_audit_rows",
    "shadow_update_rows", "parameter_shadow_audit_rows",
    "exploration_status", "action_candidate_rows", "local_observation_need_rows", "action_surface_planning_audit_rows", "action_surface_planning_status", "gate_decision", "action_frame_rows", "action_execution_audit_rows", "action_execution_status",
    "world_transition_rows", "boundary_violation_count",
]


class BoundaryGuard:
    name = "boundary_guard"

    def validate_world_trace_audit(self, world_trace_audit: pd.DataFrame) -> list[str]:
        violations: list[str] = []
        if world_trace_audit is None or world_trace_audit.empty:
            return ["world_trace_audit_missing"]
        required = {
            "trace_contract", "trace_fingerprint", "world_t", "entity_rows", "relation_rows",
            "schema_valid", "world_owned_state", "gk_written_back_to_world",
            "ot_written_back_to_world", "canonical_parameter_written_to_world",
        }
        missing = sorted(required - set(world_trace_audit.columns))
        if missing:
            violations.append(f"world_trace_audit_required_fields_missing:{','.join(missing)}")
        if "schema_valid" in world_trace_audit.columns and not bool(world_trace_audit["schema_valid"].astype(bool).all()):
            violations.append("world_trace_schema_invalid")
        for col in ["gk_written_back_to_world", "ot_written_back_to_world", "canonical_parameter_written_to_world"]:
            if col in world_trace_audit.columns and bool(world_trace_audit[col].astype(bool).any()):
                violations.append(f"world_boundary_violation:{col}")
        if "dept_internal_columns_present" in world_trace_audit.columns and bool(world_trace_audit["dept_internal_columns_present"].astype(bool).any()):
            violations.append("world_trace_contains_dept_internal_columns")
        return violations

    def validate_world_transition_audit(self, world_transition_audit: pd.DataFrame) -> list[str]:
        violations: list[str] = []
        if world_transition_audit is None or world_transition_audit.empty:
            return ["world_transition_audit_missing"]
        required = {
            "transition_contract", "trace_before_fingerprint", "trace_after_fingerprint",
            "world_t_before", "world_t_after", "gk_writeback_performed",
            "ot_writeback_performed", "canonical_parameter_write_performed",
        }
        missing = sorted(required - set(world_transition_audit.columns))
        if missing:
            violations.append(f"world_transition_audit_required_fields_missing:{','.join(missing)}")
        if "world_t_before" in world_transition_audit.columns and "world_t_after" in world_transition_audit.columns:
            delta = (world_transition_audit["world_t_after"] - world_transition_audit["world_t_before"]).astype(int)
            if not bool((delta == 1).all()):
                violations.append("world_transition_time_not_incremented_by_one")
        for col in ["gk_writeback_performed", "ot_writeback_performed", "canonical_parameter_write_performed"]:
            if col in world_transition_audit.columns and bool(world_transition_audit[col].astype(bool).any()):
                violations.append(f"world_transition_boundary_violation:{col}")
        return violations

    def validate_gk_build_audit(self, gk_build_audit: pd.DataFrame) -> list[str]:
        violations: list[str] = []
        if gk_build_audit is None or gk_build_audit.empty:
            return ["gk_build_audit_missing"]
        required = {
            "gk_build_contract", "source_trace_fingerprint_before", "source_trace_fingerprint_after",
            "source_trace_mutated_by_gk_builder", "source_world_t", "gt_rows", "kt_rows",
            "formal_packet_rows", "formal_lower_leak_count", "gk_writeback_performed", "build_status",
        }
        missing = sorted(required - set(gk_build_audit.columns))
        if missing:
            violations.append(f"gk_build_audit_required_fields_missing:{','.join(missing)}")
        if "source_trace_mutated_by_gk_builder" in gk_build_audit.columns and bool(gk_build_audit["source_trace_mutated_by_gk_builder"].astype(bool).any()):
            violations.append("gk_builder_mutated_world_trace")
        if "formal_lower_leak_count" in gk_build_audit.columns and int(gk_build_audit["formal_lower_leak_count"].sum()) > 0:
            violations.append("gk_formal_packet_lower_leak")
        if "gk_writeback_performed" in gk_build_audit.columns and bool(gk_build_audit["gk_writeback_performed"].astype(bool).any()):
            violations.append("gk_writeback_performed")
        if "build_status" in gk_build_audit.columns and not bool(gk_build_audit["build_status"].eq("pass").all()):
            violations.append("gk_build_status_not_pass")
        return violations

    def validate_formal_packet(self, formal_packet: pd.DataFrame) -> list[str]:
        violations: list[str] = []
        forbidden = ("ot_", "v8_", "exploration_", "graph_object", "action_surface", "final_gate", "action_frame")
        leaked = [c for c in formal_packet.columns if c.startswith(forbidden)] if formal_packet is not None else []
        if leaked:
            violations.append(f"formal_input_lower_leak:{','.join(leaked)}")
        for col in ["formal_contains_ot", "formal_contains_v8", "formal_contains_exploration", "formal_contains_action_surface"]:
            if formal_packet is not None and col in formal_packet.columns and bool(formal_packet[col].astype(bool).any()):
                violations.append(f"formal_input_flagged_lower_leak:{col}")
        return violations


    def validate_ot_outputs(
        self,
        ot_native: pd.DataFrame,
        ot_action_view: pd.DataFrame,
        ot_exploration_view: pd.DataFrame,
        ot_observation_audit: pd.DataFrame,
        residual_noise_log: pd.DataFrame,
        residual_noise_ledger_audit: pd.DataFrame,
    ) -> list[str]:
        """Validate Task4 O_t and residual/noise ledger boundaries."""
        violations: list[str] = []
        if ot_native is None or ot_native.empty:
            return ["ot_native_missing"]
        required_native = {
            "ot_id", "ot_identity_key", "ot_contract", "ot_residual_score",
            "ot_noise_score", "ot_unresolved_score", "ot_ambiguity_score",
            "ot_gk_generation_performed", "ot_upper_formal_input_performed",
            "ot_action_module_direct_input", "ot_writeback_performed",
        }
        missing_native = sorted(required_native - set(ot_native.columns))
        if missing_native:
            violations.append(f"ot_native_required_fields_missing:{','.join(missing_native)}")
        for col in ["ot_gk_generation_performed", "ot_upper_formal_input_performed", "ot_action_module_direct_input", "ot_writeback_performed"]:
            if col in ot_native.columns and bool(ot_native[col].astype(bool).any()):
                violations.append(f"ot_boundary_violation:{col}")
        if "ot_contract" in ot_native.columns and not bool(ot_native["ot_contract"].astype(str).str.contains("not_GK_generator", regex=False).all()):
            violations.append("ot_contract_missing_not_gk_generator")
        if ot_action_view is None or ot_action_view.empty:
            violations.append("ot_action_view_missing")
        elif "ot_action_view_contract" not in ot_action_view.columns:
            violations.append("ot_action_view_contract_missing")
        if ot_exploration_view is None or ot_exploration_view.empty:
            violations.append("ot_exploration_view_missing")
        elif "ot_exploration_view_contract" not in ot_exploration_view.columns:
            violations.append("ot_exploration_view_contract_missing")
        if residual_noise_log is None or residual_noise_log.empty:
            violations.append("residual_noise_log_missing")
        else:
            required_noise = {
                "noise_event_id", "ot_id", "noise_status", "noise_kind", "noise_retained",
                "noise_retention_contract", "written_back_to_gk", "written_back_to_world",
                "used_as_upper_formal_input",
            }
            missing_noise = sorted(required_noise - set(residual_noise_log.columns))
            if missing_noise:
                violations.append(f"residual_noise_required_fields_missing:{','.join(missing_noise)}")
            if len(residual_noise_log) < len(ot_native):
                violations.append("residual_noise_rows_less_than_ot_rows")
            for col in ["written_back_to_gk", "written_back_to_world", "used_as_upper_formal_input"]:
                if col in residual_noise_log.columns and bool(residual_noise_log[col].astype(bool).any()):
                    violations.append(f"residual_noise_boundary_violation:{col}")
            if "noise_retained" in residual_noise_log.columns and not bool(residual_noise_log["noise_retained"].astype(bool).all()):
                violations.append("residual_noise_not_all_retained")
        if ot_observation_audit is None or ot_observation_audit.empty:
            violations.append("ot_observation_audit_missing")
        else:
            for col in ["all_noise_retained", "ot_is_gk_generator", "ot_used_as_upper_formal_input", "ot_is_action_module_direct_input", "ot_writeback_performed"]:
                if col not in ot_observation_audit.columns:
                    violations.append(f"ot_observation_audit_field_missing:{col}")
            for col in ["ot_is_gk_generator", "ot_used_as_upper_formal_input", "ot_is_action_module_direct_input", "ot_writeback_performed"]:
                if col in ot_observation_audit.columns and bool(ot_observation_audit[col].astype(bool).any()):
                    violations.append(f"ot_observation_audit_boundary_violation:{col}")
            if "all_noise_retained" in ot_observation_audit.columns and not bool(ot_observation_audit["all_noise_retained"].astype(bool).all()):
                violations.append("ot_observation_audit_noise_not_all_retained")
        if residual_noise_ledger_audit is None or residual_noise_ledger_audit.empty:
            violations.append("residual_noise_ledger_audit_missing")
        else:
            for col in ["all_noise_retained", "unclassified_noise_discarded", "ledger_available_for_exploration"]:
                if col not in residual_noise_ledger_audit.columns:
                    violations.append(f"noise_ledger_audit_field_missing:{col}")
            if "all_noise_retained" in residual_noise_ledger_audit.columns and not bool(residual_noise_ledger_audit["all_noise_retained"].astype(bool).all()):
                violations.append("noise_ledger_not_all_retained")
            if "unclassified_noise_discarded" in residual_noise_ledger_audit.columns and bool(residual_noise_ledger_audit["unclassified_noise_discarded"].astype(bool).any()):
                violations.append("unclassified_noise_discarded")
        return violations


    def validate_upper_pressure_audit(self, upper_pressure_audit: pd.DataFrame) -> list[str]:
        """Validate that upper pressure is derived from formal G/K only."""
        violations: list[str] = []
        if upper_pressure_audit is None or upper_pressure_audit.empty:
            return ["upper_pressure_audit_missing"]
        required = {
            "upper_pressure_contract", "formal_input_contract_seen",
            "formal_packet_fingerprint", "formal_rows", "m_rows", "pressure_rows",
            "formal_lower_leak_count", "formal_input_is_gk_only",
            "m_lower_leak_count", "pressure_lower_leak_count",
            "upper_uses_ot", "upper_uses_v8", "upper_uses_exploration",
            "upper_uses_action_surface", "upper_uses_action_result",
            "truth_used_for_m_observation", "truth_used_for_pressure_candidate",
            "upper_writeback_performed", "audit_status",
        }
        missing = sorted(required - set(upper_pressure_audit.columns))
        if missing:
            violations.append(f"upper_pressure_audit_required_fields_missing:{','.join(missing)}")
        int_zero_fields = [
            "formal_lower_leak_count",
            "m_lower_leak_count",
            "pressure_lower_leak_count",
            "formal_required_columns_missing_count",
        ]
        for col in int_zero_fields:
            if col in upper_pressure_audit.columns and int(upper_pressure_audit[col].fillna(0).astype(int).sum()) != 0:
                violations.append(f"upper_pressure_boundary_violation:{col}")
        bool_forbidden = [
            "upper_uses_ot",
            "upper_uses_v8",
            "upper_uses_exploration",
            "upper_uses_action_surface",
            "upper_uses_action_result",
            "truth_used_for_m_observation",
            "truth_used_for_pressure_candidate",
            "upper_writeback_performed",
        ]
        for col in bool_forbidden:
            if col in upper_pressure_audit.columns and bool(upper_pressure_audit[col].astype(bool).any()):
                violations.append(f"upper_pressure_boundary_violation:{col}")
        if "formal_input_is_gk_only" in upper_pressure_audit.columns and not bool(upper_pressure_audit["formal_input_is_gk_only"].astype(bool).all()):
            violations.append("upper_pressure_formal_input_not_gk_only")
        if "audit_status" in upper_pressure_audit.columns and not bool(upper_pressure_audit["audit_status"].eq("pass").all()):
            violations.append("upper_pressure_audit_status_not_pass")
        if "upper_pressure_contract" in upper_pressure_audit.columns and not bool(upper_pressure_audit["upper_pressure_contract"].astype(str).str.contains("formal_GK_only", regex=False).all()):
            violations.append("upper_pressure_contract_not_formal_gk_only")
        return violations

    def validate_pressure_translation_audit(self, pressure_translation_audit: pd.DataFrame) -> list[str]:
        """Validate non-compressive H11 pressure translation boundaries."""
        violations: list[str] = []
        if pressure_translation_audit is None or pressure_translation_audit.empty:
            return ["pressure_translation_audit_missing"]
        required = {
            "pressure_translation_contract", "pressure_translation_input_source",
            "m_rows", "weak_pressure_rows", "h11_rows", "intent_rows",
            "approved_pressure_component_count", "h11_pressure_component_count",
            "intent_pressure_component_count", "h11_dimension_count",
            "component_identity_preserved", "component_direction_preserved",
            "h11_field_created", "pressure_intent_bundle_created",
            "noncompressive_translation_passed", "compression_allowed_before_action_planner",
            "action_frame_created_by_translation", "actionmodule_called_by_translation",
            "translation_uses_ot", "translation_uses_v8", "translation_uses_exploration",
            "translation_uses_action_surface", "translation_uses_action_result",
            "translation_writeback_performed", "truth_used_for_pressure_translation",
            "m_lower_leak_count", "weak_pressure_lower_leak_count",
            "h11_lower_leak_count", "intent_lower_leak_count",
            "pressure_translation_audit_status",
        }
        missing = sorted(required - set(pressure_translation_audit.columns))
        if missing:
            violations.append(f"pressure_translation_audit_required_fields_missing:{','.join(missing)}")
        required_true = [
            "component_identity_preserved",
            "component_direction_preserved",
            "h11_field_created",
            "pressure_intent_bundle_created",
            "noncompressive_translation_passed",
        ]
        for col in required_true:
            if col in pressure_translation_audit.columns and not bool(pressure_translation_audit[col].astype(bool).all()):
                violations.append(f"pressure_translation_required_true_failed:{col}")
        forbidden_true = [
            "compression_allowed_before_action_planner",
            "action_frame_created_by_translation",
            "actionmodule_called_by_translation",
            "translation_uses_ot",
            "translation_uses_v8",
            "translation_uses_exploration",
            "translation_uses_action_surface",
            "translation_uses_action_result",
            "translation_writeback_performed",
            "truth_used_for_pressure_translation",
        ]
        for col in forbidden_true:
            if col in pressure_translation_audit.columns and bool(pressure_translation_audit[col].astype(bool).any()):
                violations.append(f"pressure_translation_boundary_violation:{col}")
        for col in ["m_lower_leak_count", "weak_pressure_lower_leak_count", "h11_lower_leak_count", "intent_lower_leak_count"]:
            if col in pressure_translation_audit.columns and int(pressure_translation_audit[col].fillna(0).astype(int).sum()) != 0:
                violations.append(f"pressure_translation_lower_artifact_leak:{col}")
        if "pressure_translation_audit_status" in pressure_translation_audit.columns and not bool(pressure_translation_audit["pressure_translation_audit_status"].eq("pass").all()):
            violations.append("pressure_translation_audit_status_not_pass")
        if "pressure_translation_contract" in pressure_translation_audit.columns and not bool(pressure_translation_audit["pressure_translation_contract"].astype(str).str.contains("noncompressive_H11_pressure_translation", regex=False).all()):
            violations.append("pressure_translation_contract_not_task9_noncompressive")
        return violations

    def validate_parameter_updates(self, parameter_updates: pd.DataFrame) -> list[str]:
        violations: list[str] = []
        if parameter_updates is None or parameter_updates.empty:
            return ["parameter_updates_missing"]
        required = {
            "parameter_name", "theta_before", "theta_after", "theta_delta",
            "parameter_update_mode", "shadow_carryover_enabled", "commit_status",
            "lower_parameter_update_committed", "canonical_write_performed",
            "canonical_theta_written", "world_write_performed", "world_state_written",
            "gk_writeback_performed", "canonical_gk_written", "rollback_ready",
            "parameter_shadow_contract", "shadow_previous_fingerprint", "shadow_next_fingerprint",
        }
        missing = sorted(required - set(parameter_updates.columns))
        if missing:
            violations.append(f"parameter_updates_required_fields_missing:{','.join(missing)}")
        for col in [
            "canonical_write_performed", "canonical_theta_written", "world_write_performed",
            "world_state_written", "gk_writeback_performed", "canonical_gk_written",
            "lower_parameter_update_committed", "commit_gate_passed", "truth_used_for_parameter_update",
        ]:
            if col in parameter_updates.columns and bool(parameter_updates[col].astype(bool).any()):
                violations.append(f"parameter_boundary_violation:{col}")
        if "parameter_update_mode" in parameter_updates.columns and not bool(parameter_updates["parameter_update_mode"].eq("shadow_only").all()):
            violations.append("parameter_update_mode_not_shadow_only")
        if "shadow_carryover_enabled" in parameter_updates.columns and not bool(parameter_updates["shadow_carryover_enabled"].astype(bool).all()):
            violations.append("shadow_carryover_not_enabled")
        if "rollback_ready" in parameter_updates.columns and not bool(parameter_updates["rollback_ready"].astype(bool).all()):
            violations.append("parameter_shadow_not_rollback_ready")
        if "commit_status" in parameter_updates.columns and not bool(parameter_updates["commit_status"].eq("not_committed").all()):
            violations.append("parameter_commit_status_not_blocked")
        return violations

    def validate_parameter_shadow_audit(self, parameter_shadow_audit: pd.DataFrame) -> list[str]:
        violations: list[str] = []
        if parameter_shadow_audit is None or parameter_shadow_audit.empty:
            return ["parameter_shadow_audit_missing"]
        required = {
            "parameter_shadow_contract", "shadow_cycle_index", "previous_shadow_fingerprint",
            "new_shadow_fingerprint", "previous_shadow_fingerprint_matches_last_cycle",
            "shadow_carryover_enabled", "shadow_state_rows", "parameter_update_rows",
            "max_abs_theta_delta", "max_allowed_step_delta", "bounded_delta_pass",
            "rollback_ready", "commit_status", "commit_gate_passed",
            "lower_parameter_update_committed", "canonical_write_performed",
            "canonical_theta_written", "world_write_performed", "world_state_written",
            "gk_writeback_performed", "canonical_gk_written", "truth_used_for_parameter_update",
            "audit_status",
        }
        missing = sorted(required - set(parameter_shadow_audit.columns))
        if missing:
            violations.append(f"parameter_shadow_audit_required_fields_missing:{','.join(missing)}")
        forbidden_true = [
            "commit_gate_passed", "lower_parameter_update_committed", "canonical_write_performed",
            "canonical_theta_written", "world_write_performed", "world_state_written",
            "gk_writeback_performed", "canonical_gk_written", "truth_used_for_parameter_update",
        ]
        for col in forbidden_true:
            if col in parameter_shadow_audit.columns and bool(parameter_shadow_audit[col].astype(bool).any()):
                violations.append(f"parameter_shadow_audit_boundary_violation:{col}")
        required_true = ["previous_shadow_fingerprint_matches_last_cycle", "shadow_carryover_enabled", "bounded_delta_pass", "rollback_ready"]
        for col in required_true:
            if col in parameter_shadow_audit.columns and not bool(parameter_shadow_audit[col].astype(bool).all()):
                violations.append(f"parameter_shadow_audit_required_true_failed:{col}")
        if "commit_status" in parameter_shadow_audit.columns and not bool(parameter_shadow_audit["commit_status"].eq("not_committed").all()):
            violations.append("parameter_shadow_commit_status_not_blocked")
        if "audit_status" in parameter_shadow_audit.columns and not bool(parameter_shadow_audit["audit_status"].eq("pass").all()):
            violations.append("parameter_shadow_audit_status_not_pass")
        if "parameter_shadow_contract" in parameter_shadow_audit.columns and not bool(parameter_shadow_audit["parameter_shadow_contract"].astype(str).str.contains("bounded_shadow_carryover", regex=False).all()):
            violations.append("parameter_shadow_contract_not_bounded_shadow")
        return violations

    def validate_canonical_update(
        self,
        commit_gate_audit: pd.DataFrame,
        rollback_snapshot: pd.DataFrame,
        canonical_parameter_state: pd.DataFrame,
        canonical_write_audit: pd.DataFrame,
    ) -> list[str]:
        """Validate Q8 controlled canonical update boundaries."""
        violations: list[str] = []
        if commit_gate_audit is None or commit_gate_audit.empty:
            return ["canonical_commit_gate_audit_missing"]
        if canonical_write_audit is None or canonical_write_audit.empty:
            violations.append("canonical_write_audit_missing")
            return violations
        if rollback_snapshot is None or rollback_snapshot.empty:
            violations.append("rollback_snapshot_missing")
        if canonical_parameter_state is None or canonical_parameter_state.empty:
            violations.append("canonical_parameter_state_missing")

        required_gate = {
            "q8_commit_gate_contract", "commit_gate_passed", "commit_gate_reason",
            "canonical_commit_enabled", "canonical_commit_dry_run", "rollback_snapshot_ready",
            "audit_status",
        }
        missing_gate = sorted(required_gate - set(commit_gate_audit.columns))
        if missing_gate:
            violations.append(f"canonical_commit_gate_required_fields_missing:{','.join(missing_gate)}")

        required_write = {
            "canonical_commit_id", "loop_step", "commit_gate_passed", "commit_gate_reason",
            "canonical_commit_enabled", "canonical_commit_dry_run", "rollback_snapshot_id",
            "canonical_write_performed", "world_write_performed", "gk_writeback_performed",
            "ot_writeback_performed", "actionmodule_direct_input", "audit_status",
        }
        missing_write = sorted(required_write - set(canonical_write_audit.columns))
        if missing_write:
            violations.append(f"canonical_write_audit_required_fields_missing:{','.join(missing_write)}")

        def _any_bool(df: pd.DataFrame, col: str) -> bool:
            return bool(df is not None and not df.empty and col in df.columns and df[col].astype(bool).any())

        if _any_bool(canonical_write_audit, "world_write_performed"):
            violations.append("canonical_boundary_violation:world_write_performed")
        if _any_bool(canonical_write_audit, "gk_writeback_performed"):
            violations.append("canonical_boundary_violation:gk_writeback_performed")
        if _any_bool(canonical_write_audit, "ot_writeback_performed"):
            violations.append("canonical_boundary_violation:ot_writeback_performed")
        if _any_bool(canonical_write_audit, "actionmodule_direct_input"):
            violations.append("canonical_boundary_violation:actionmodule_direct_input")

        write_performed = _any_bool(canonical_write_audit, "canonical_write_performed")
        gate_passed = _any_bool(canonical_write_audit, "commit_gate_passed")
        dry_run = _any_bool(canonical_write_audit, "canonical_commit_dry_run")
        enabled = _any_bool(canonical_write_audit, "canonical_commit_enabled")
        rollback_ready = _any_bool(commit_gate_audit, "rollback_snapshot_ready")

        if write_performed and not gate_passed:
            violations.append("canonical_write_without_commit_gate_pass")
        if write_performed and dry_run:
            violations.append("canonical_write_during_dry_run")
        if write_performed and not enabled:
            violations.append("canonical_write_while_disabled")
        if write_performed and not rollback_ready:
            violations.append("canonical_write_without_rollback_snapshot_ready")

        if "audit_status" in commit_gate_audit.columns and not bool(commit_gate_audit["audit_status"].astype(str).eq("pass").all()):
            violations.append("canonical_commit_gate_audit_status_not_pass")
        if "audit_status" in canonical_write_audit.columns and not bool(canonical_write_audit["audit_status"].astype(str).isin(["pass", "blocked"]).all()):
            violations.append("canonical_write_audit_status_invalid")
        return violations

    def validate_local_audit_outputs(self, local_audit: pd.DataFrame, role: str | None = None) -> list[str]:
        """Validate Task8 v8-style local audit boundary.

        v8/local audit may inspect local candidates, but it must not become a
        G/K generator, upper formal input, parameter updater, ActionModule caller,
        or writeback path.
        """
        violations: list[str] = []
        if local_audit is None or local_audit.empty:
            violations.append(f"local_audit_missing:{role or 'unknown'}")
            return violations
        if role and "local_audit_role" in local_audit.columns and not bool(local_audit["local_audit_role"].eq(role).all()):
            violations.append(f"local_audit_role_mismatch:{role}")
        if "v8_support_status" in local_audit.columns and not bool(local_audit["v8_support_status"].eq("pass").all()):
            violations.append(f"local_audit_status_not_pass:{role or 'unknown'}")
        for col in [
            "v8_is_gk_generator", "v8_is_upper_formal_input", "v8_generates_pressure",
            "v8_updates_parameter_box", "v8_calls_actionmodule", "v8_writes_world",
            "v8_writes_gk", "v8_writes_ot", "v8_writes_canonical_parameter",
            "local_audit_writeback_performed", "action_frame_created_by_local_audit",
            "actionmodule_direct_input_from_local_audit", "exploration_projection_created_by_local_audit",
            "exploration_action_created_by_local_audit", "sidecar_compression_by_local_audit",
        ]:
            if col in local_audit.columns and bool(local_audit[col].astype(bool).any()):
                violations.append(f"local_audit_boundary_violation:{role or 'unknown'}:{col}")
        if "local_audit_contract" in local_audit.columns and not bool(local_audit["local_audit_contract"].astype(str).str.contains("not_GK_generator", regex=False).all()):
            violations.append(f"local_audit_contract_missing_not_gk_generator:{role or 'unknown'}")
        return violations

    def validate_exploration_bridge(self, exploration_sidecar: pd.DataFrame, exploration_projection: pd.DataFrame) -> list[str]:
        """Validate Task10 bridge: full sidecar retained, projection thin and verified."""
        violations: list[str] = []
        if exploration_sidecar is None or exploration_sidecar.empty:
            violations.append("sidecar_missing")
            return violations
        if "full_context_present" in exploration_sidecar.columns and not bool(exploration_sidecar["full_context_present"].astype(bool).all()):
            violations.append("sidecar_context_not_preserved")
        if "sidecar_is_noncompressed" in exploration_sidecar.columns and not bool(exploration_sidecar["sidecar_is_noncompressed"].astype(bool).all()):
            violations.append("sidecar_compressed")
        for col in [
            "sidecar_direct_actionmodule_input", "bridge_writes_world", "bridge_writes_gk",
            "bridge_writes_ot", "bridge_updates_parameter_box", "bridge_calls_actionmodule",
            "bridge_creates_actionframe",
        ]:
            if col in exploration_sidecar.columns and bool(exploration_sidecar[col].astype(bool).any()):
                violations.append(f"exploration_bridge_boundary_violation:{col}")
        if "eligible_for_action_projection" in exploration_sidecar.columns:
            eligible = exploration_sidecar["eligible_for_action_projection"].fillna(False).astype(bool)
            if bool(eligible.any()):
                if exploration_projection is None or exploration_projection.empty:
                    violations.append("eligible_exploration_missing_projection")
        if exploration_projection is not None and not exploration_projection.empty:
            required = {
                "projection_contract", "sidecar_id", "candidate_axis_id", "projection_strength",
                "projection_source_verified", "projection_source_local_audit_passed",
                "projection_is_thin", "projection_contains_full_sidecar_payload",
                "sidecar_direct_actionmodule_input",
            }
            missing = sorted(required - set(exploration_projection.columns))
            if missing:
                violations.append(f"exploration_projection_contract_missing:{missing}")
            else:
                if not bool(exploration_projection["projection_contract"].astype(str).str.contains("thin_projection_only", regex=False).all()):
                    violations.append("exploration_projection_not_thin_contract")
                if not bool(exploration_projection["projection_source_verified"].astype(bool).all()):
                    violations.append("unverified_exploration_projection")
                if not bool(exploration_projection["projection_source_local_audit_passed"].astype(bool).all()):
                    violations.append("projection_without_local_audit_pass")
                if not bool(exploration_projection["projection_is_thin"].astype(bool).all()):
                    violations.append("projection_not_marked_thin")
                if bool(exploration_projection["projection_contains_full_sidecar_payload"].astype(bool).any()):
                    violations.append("projection_contains_full_sidecar_payload")
                if bool(exploration_projection["sidecar_direct_actionmodule_input"].astype(bool).any()):
                    violations.append("sidecar_direct_actionmodule_input")
                if "sidecar_id" in exploration_sidecar.columns:
                    sidecars = set(exploration_sidecar["sidecar_id"].astype(str))
                    projected = set(exploration_projection["sidecar_id"].astype(str))
                    if not projected.issubset(sidecars):
                        violations.append("projection_sidecar_reference_missing")
        return violations


    def validate_action_surface_planning_audit(self, planning_audit: pd.DataFrame) -> list[str]:
        """Validate Task11 pre-ActionFrame action-surface planning boundary."""
        violations: list[str] = []
        if planning_audit is None or planning_audit.empty:
            return ["action_surface_planning_audit_missing"]
        required = {
            "planning_contract", "audit_status", "graph_object_rows", "pressure_intent_rows",
            "ot_action_view_rows", "affordance_rows", "action_candidate_rows",
            "local_observation_need_rows", "pressure_intent_used", "ot_action_view_used",
            "shadow_parameter_summary_used", "candidates_have_required_contract",
            "action_frame_created_by_planning", "actionmodule_called_by_planning",
            "planning_writeback_performed", "canonical_write_performed",
            "world_write_performed", "gk_writeback_performed", "ot_direct_actionmodule_input",
        }
        missing = sorted(required - set(planning_audit.columns))
        if missing:
            violations.append(f"action_surface_planning_audit_required_fields_missing:{','.join(missing)}")
        if "audit_status" in planning_audit.columns and not bool(planning_audit["audit_status"].eq("pass").all()):
            violations.append("action_surface_planning_audit_status_not_pass")
        for col in [
            "action_frame_created_by_planning", "actionmodule_called_by_planning",
            "planning_writeback_performed", "canonical_write_performed", "world_write_performed",
            "gk_writeback_performed", "ot_direct_actionmodule_input",
            "v8_direct_actionmodule_input", "exploration_sidecar_direct_actionmodule_input",
        ]:
            if col in planning_audit.columns and bool(planning_audit[col].astype(bool).any()):
                violations.append(f"action_surface_planning_boundary_violation:{col}")
        for col in ["pressure_intent_used", "ot_action_view_used", "shadow_parameter_summary_used", "candidates_have_required_contract"]:
            if col in planning_audit.columns and not bool(planning_audit[col].astype(bool).all()):
                violations.append(f"action_surface_planning_required_true_failed:{col}")
        if "action_candidate_rows" in planning_audit.columns and int(planning_audit["action_candidate_rows"].sum()) <= 0:
            violations.append("action_surface_planning_no_candidates")
        if "local_observation_need_rows" in planning_audit.columns and int(planning_audit["local_observation_need_rows"].sum()) <= 0:
            violations.append("action_surface_planning_no_local_observation_needs")
        if "planning_contract" in planning_audit.columns and not bool(planning_audit["planning_contract"].astype(str).str.contains("pre_ActionFrame_only", regex=False).all()):
            violations.append("action_surface_planning_contract_not_pre_actionframe")
        return violations

    def validate_action_surface_outputs(
        self,
        action_affordance: pd.DataFrame,
        action_candidates: pd.DataFrame,
        local_observation_needs: pd.DataFrame,
    ) -> list[str]:
        """Validate Task11 outputs before local audit/gate/ActionFrame."""
        violations: list[str] = []
        if action_affordance is None or action_affordance.empty:
            violations.append("action_affordance_missing")
        else:
            if "action_surface_planning_contract" not in action_affordance.columns:
                violations.append("action_affordance_planning_contract_missing")
            for col in ["action_frame_created_by_planning", "actionmodule_called_by_planning", "planning_writeback_performed"]:
                if col in action_affordance.columns and bool(action_affordance[col].astype(bool).any()):
                    violations.append(f"action_affordance_boundary_violation:{col}")
        if action_candidates is None or action_candidates.empty:
            violations.append("action_candidates_missing")
        else:
            required = {"candidate_status", "action_candidate_contract", "planning_stage", "pressure_intent_used", "action_frame_created_by_planning", "actionmodule_called_by_planning"}
            missing = sorted(required - set(action_candidates.columns))
            if missing:
                violations.append(f"action_candidates_required_fields_missing:{','.join(missing)}")
            if "candidate_status" in action_candidates.columns and not bool(action_candidates["candidate_status"].eq("pre_gate_candidate").all()):
                violations.append("action_candidates_not_pre_gate")
            for col in ["action_frame_created_by_planning", "actionmodule_called_by_planning", "canonical_parameter_write", "world_write_performed", "gk_writeback_performed", "ot_direct_actionmodule_input"]:
                if col in action_candidates.columns and bool(action_candidates[col].astype(bool).any()):
                    violations.append(f"action_candidate_boundary_violation:{col}")
            if "action_candidate_contract" in action_candidates.columns and not bool(action_candidates["action_candidate_contract"].astype(str).str.contains("pre_ActionFrame_candidate", regex=False).all()):
                violations.append("action_candidate_contract_not_pre_actionframe")
        if local_observation_needs is None or local_observation_needs.empty:
            violations.append("local_observation_needs_missing")
        else:
            required_needs = {"entity_id", "local_observation_need_score", "requires_action_local_audit", "need_source_contract", "action_frame_created_by_need_builder", "actionmodule_called_by_need_builder"}
            missing = sorted(required_needs - set(local_observation_needs.columns))
            if missing:
                violations.append(f"local_observation_needs_required_fields_missing:{','.join(missing)}")
            for col in ["action_frame_created_by_need_builder", "actionmodule_called_by_need_builder"]:
                if col in local_observation_needs.columns and bool(local_observation_needs[col].astype(bool).any()):
                    violations.append(f"local_observation_needs_boundary_violation:{col}")
        return violations

    def validate_coactivation_gate(self, coactivation_gate: pd.DataFrame) -> list[str]:
        """Validate Task12 coactivation gate boundary and audit fields."""
        violations: list[str] = []
        if coactivation_gate is None or coactivation_gate.empty:
            return ["coactivation_gate_missing"]
        required = {
            "coactivation_gate_decision", "gate_reason", "coactivation_risk_score",
            "pressure_component_score", "exploration_component_score",
            "action_component_score", "local_risk_component_score",
            "noise_component_score", "shadow_component_score",
            "gate_required_before_actionframe", "gate_applies_to_action_frame",
            "gate_dampening_factor", "coactivation_gate_audit_status",
            "action_frame_created_by_gate", "actionmodule_called_by_gate",
            "parameter_box_updated_by_gate", "world_write_performed_by_gate",
            "gk_writeback_performed_by_gate", "ot_writeback_performed_by_gate",
            "canonical_parameter_write_by_gate", "sidecar_direct_actionmodule_input_by_gate",
            "coactivation_gate_contract",
        }
        missing = sorted(required - set(coactivation_gate.columns))
        if missing:
            violations.append(f"coactivation_gate_required_fields_missing:{','.join(missing)}")
        valid_decisions = {"allow", "dampen", "defer", "block", "monitor_only"}
        if "coactivation_gate_decision" in coactivation_gate.columns and not bool(coactivation_gate["coactivation_gate_decision"].astype(str).isin(valid_decisions).all()):
            violations.append("coactivation_gate_invalid_decision")
        if "coactivation_gate_audit_status" in coactivation_gate.columns and not bool(coactivation_gate["coactivation_gate_audit_status"].eq("pass").all()):
            violations.append("coactivation_gate_audit_status_not_pass")
        for col in ["gate_required_before_actionframe", "gate_applies_to_action_frame"]:
            if col in coactivation_gate.columns and not bool(coactivation_gate[col].astype(bool).all()):
                violations.append(f"coactivation_gate_required_true_failed:{col}")
        forbidden = [
            "action_frame_created_by_gate", "actionmodule_called_by_gate",
            "parameter_box_updated_by_gate", "world_write_performed_by_gate",
            "gk_writeback_performed_by_gate", "ot_writeback_performed_by_gate",
            "canonical_parameter_write_by_gate", "sidecar_direct_actionmodule_input_by_gate",
        ]
        for col in forbidden:
            if col in coactivation_gate.columns and bool(coactivation_gate[col].astype(bool).any()):
                violations.append(f"coactivation_gate_boundary_violation:{col}")
        if "coactivation_risk_score" in coactivation_gate.columns:
            risk = pd.to_numeric(coactivation_gate["coactivation_risk_score"], errors="coerce")
            if bool((risk < 0).any() or (risk > 1).any() or risk.isna().any()):
                violations.append("coactivation_gate_risk_score_out_of_bounds")
        if "gate_dampening_factor" in coactivation_gate.columns:
            factor = pd.to_numeric(coactivation_gate["gate_dampening_factor"], errors="coerce")
            if bool((factor < 0).any() or (factor > 1).any() or factor.isna().any()):
                violations.append("coactivation_gate_dampening_factor_out_of_bounds")
        if "coactivation_gate_contract" in coactivation_gate.columns and not bool(coactivation_gate["coactivation_gate_contract"].astype(str).str.contains("Task12_same_step_coactivation_gate", regex=False).all()):
            violations.append("coactivation_gate_contract_not_task12")
        return violations


    def validate_action_frame(self, action_frame: pd.DataFrame, gate_decision: pd.DataFrame) -> list[str]:
        violations: list[str] = []
        if gate_decision is None or gate_decision.empty:
            violations.append("coactivation_gate_missing_before_action_frame")
        if action_frame is not None and not action_frame.empty:
            for col in ["reads_gk_directly", "reads_ot_directly", "reads_v8_directly", "reads_exploration_sidecar_directly", "canonical_parameter_write"]:
                if col in action_frame.columns and bool(action_frame[col].astype(bool).any()):
                    violations.append(f"action_module_boundary_violation:{col}")
            if "action_frame_contract" not in action_frame.columns:
                violations.append("action_frame_contract_missing")
        return violations


    def validate_action_execution_audit(self, action_execution_audit: pd.DataFrame) -> list[str]:
        """Validate Task14 ActionFrame builder + ActionModule adapter boundary."""
        violations: list[str] = []
        if action_execution_audit is None or action_execution_audit.empty:
            return ["action_execution_audit_missing"]
        required = {
            "action_execution_contract", "audit_status", "source_action_candidate_rows",
            "action_frame_rows", "coactivation_gate_decision",
            "coactivation_gate_applied_before_actionframe", "action_frame_contract_present",
            "actionmodule_called_by_adapter", "actionmodule_input_contract",
            "actionmodule_received_actionframe_only", "direct_gk_input_to_actionmodule",
            "direct_ot_input_to_actionmodule", "direct_v8_input_to_actionmodule",
            "direct_exploration_sidecar_input_to_actionmodule",
            "direct_parameter_box_input_to_actionmodule", "canonical_parameter_write_performed",
            "gk_writeback_performed", "ot_writeback_performed",
            "world_step_performed_by_adapter", "world_t_before", "world_t_after",
        }
        missing = sorted(required - set(action_execution_audit.columns))
        if missing:
            violations.append(f"action_execution_audit_required_fields_missing:{','.join(missing)}")
        if "audit_status" in action_execution_audit.columns and not bool(action_execution_audit["audit_status"].eq("pass").all()):
            violations.append("action_execution_audit_status_not_pass")
        for col in [
            "direct_gk_input_to_actionmodule", "direct_ot_input_to_actionmodule",
            "direct_v8_input_to_actionmodule", "direct_exploration_sidecar_input_to_actionmodule",
            "direct_parameter_box_input_to_actionmodule", "canonical_parameter_write_performed",
            "gk_writeback_performed", "ot_writeback_performed",
        ]:
            if col in action_execution_audit.columns and bool(action_execution_audit[col].astype(bool).any()):
                violations.append(f"action_execution_boundary_violation:{col}")
        for col in [
            "coactivation_gate_applied_before_actionframe", "action_frame_contract_present",
            "actionmodule_called_by_adapter", "actionmodule_received_actionframe_only",
            "world_step_performed_by_adapter",
        ]:
            if col in action_execution_audit.columns and not bool(action_execution_audit[col].astype(bool).all()):
                violations.append(f"action_execution_required_true_failed:{col}")
        if "actionmodule_input_contract" in action_execution_audit.columns and not bool(action_execution_audit["actionmodule_input_contract"].eq("ActionFrame_only").all()):
            violations.append("actionmodule_input_contract_not_actionframe_only")
        if "world_t_before" in action_execution_audit.columns and "world_t_after" in action_execution_audit.columns:
            delta = (action_execution_audit["world_t_after"] - action_execution_audit["world_t_before"]).astype(int)
            if not bool((delta == 1).all()):
                violations.append("action_execution_world_time_not_incremented_by_one")
        if "action_execution_contract" in action_execution_audit.columns and not bool(action_execution_audit["action_execution_contract"].astype(str).str.contains("ActionFrame_only_input", regex=False).all()):
            violations.append("action_execution_contract_missing_actionframe_only")
        return violations


    def build_boundary_guard_audit(self, artifacts, cycle_audit_row: pd.DataFrame) -> pd.DataFrame:
        """Build a per-cycle invariant ledger for Task15.

        This is deliberately separate from the earlier validate_* helpers.  The
        helpers are used as immediate fail checks; this table is the research
        audit surface that records which invariant passed, failed, or must be
        watched in each cycle.
        """
        rows = []
        step = int(artifacts.step)
        seed = int(artifacts.seed)
        scenario = str(artifacts.scenario)

        def add(rule_id: str, domain: str, invariant_jp: str, passed: bool, observed: str,
                source: str, severity: str = "block_on_fail", expected: str = "pass") -> None:
            rows.append({
                "run_seed": seed,
                "run_scenario": scenario,
                "loop_step": step,
                "rule_id": rule_id,
                "boundary_domain": domain,
                "invariant_jp": invariant_jp,
                "expected": expected,
                "observed": observed,
                "guard_status": "pass" if bool(passed) else "fail",
                "severity": severity,
                "source_audit_table": source,
                "boundary_guard_contract": "Task12_coactivation_gate_boundary_guard__diagnostic_only__no_runtime_writeback__RC1",
                "guard_writes_world": False,
                "guard_writes_gk": False,
                "guard_writes_ot": False,
                "guard_writes_actionframe": False,
                "guard_writes_canonical_parameter": False,
            })

        # World and trace invariants.
        add(
            "BG01_world_trace_schema_valid",
            "world_adapter",
            "疑似現実traceはschema妥当で、DEPT内部列を含まない",
            _first_bool(artifacts.world_trace_audit, "schema_valid") and not _any_bool(artifacts.world_trace_audit, "dept_internal_columns_present"),
            f"schema_valid={_first_bool(artifacts.world_trace_audit, 'schema_valid')};dept_internal={_any_bool(artifacts.world_trace_audit, 'dept_internal_columns_present')}",
            "world_trace_audit",
        )
        add(
            "BG02_world_transition_no_dept_writeback",
            "world_adapter",
            "world遷移にG/K・O_t・canonical parameterの書き戻しを混ぜない",
            not _any_bool(artifacts.world_transition_audit, "gk_writeback_performed")
            and not _any_bool(artifacts.world_transition_audit, "ot_writeback_performed")
            and not _any_bool(artifacts.world_transition_audit, "canonical_parameter_write_performed"),
            f"gk={_any_bool(artifacts.world_transition_audit, 'gk_writeback_performed')};ot={_any_bool(artifacts.world_transition_audit, 'ot_writeback_performed')};canonical={_any_bool(artifacts.world_transition_audit, 'canonical_parameter_write_performed')}",
            "world_transition_audit",
        )
        add(
            "BG03_gk_builder_read_only",
            "gk_builder",
            "G/K生成器はworld traceを読むだけで、traceやworldへ書き戻さない",
            _first_text(artifacts.gk_build_audit, "build_status") == "pass"
            and not _any_bool(artifacts.gk_build_audit, "source_trace_mutated_by_gk_builder")
            and not _any_bool(artifacts.gk_build_audit, "gk_writeback_performed"),
            f"status={_first_text(artifacts.gk_build_audit, 'build_status')};mutated={_any_bool(artifacts.gk_build_audit, 'source_trace_mutated_by_gk_builder')};gk_writeback={_any_bool(artifacts.gk_build_audit, 'gk_writeback_performed')}",
            "gk_build_audit",
        )
        add(
            "BG04_formal_packet_gk_only",
            "gk_builder_to_upper_pressure",
            "上位圧へのformal inputはG/K由来のみで、O_t・v8・探索・作用面を混ぜない",
            len(self.validate_formal_packet(artifacts.formal_packet)) == 0,
            f"formal_packet_rows={_rows(artifacts.formal_packet)};violations={len(self.validate_formal_packet(artifacts.formal_packet))}",
            "formal_packet",
        )

        # O_t and noise invariants.
        add(
            "BG05_ot_not_gk_or_upper_or_action_input",
            "ot_observation_module",
            "O_tはG/K生成器・上位圧formal input・ActionModule直接入力にならない",
            not _any_bool(artifacts.ot_observation_audit, "ot_is_gk_generator")
            and not _any_bool(artifacts.ot_observation_audit, "ot_used_as_upper_formal_input")
            and not _any_bool(artifacts.ot_observation_audit, "ot_is_action_module_direct_input")
            and not _any_bool(artifacts.ot_observation_audit, "ot_writeback_performed"),
            f"gk_generator={_any_bool(artifacts.ot_observation_audit, 'ot_is_gk_generator')};upper_input={_any_bool(artifacts.ot_observation_audit, 'ot_used_as_upper_formal_input')};action_direct={_any_bool(artifacts.ot_observation_audit, 'ot_is_action_module_direct_input')};writeback={_any_bool(artifacts.ot_observation_audit, 'ot_writeback_performed')}",
            "ot_observation_audit",
        )
        add(
            "BG06_residual_noise_retained",
            "residual_noise_ledger",
            "未分類ノイズ・未解決残差・低ノイズを捨てず、探索用台帳へ残す",
            _first_bool(artifacts.residual_noise_ledger_audit, "all_noise_retained")
            and not _any_bool(artifacts.residual_noise_ledger_audit, "unclassified_noise_discarded")
            and _first_bool(artifacts.residual_noise_ledger_audit, "ledger_available_for_exploration"),
            f"all_retained={_first_bool(artifacts.residual_noise_ledger_audit, 'all_noise_retained')};discarded={_any_bool(artifacts.residual_noise_ledger_audit, 'unclassified_noise_discarded')};for_exploration={_first_bool(artifacts.residual_noise_ledger_audit, 'ledger_available_for_exploration')}",
            "residual_noise_ledger_audit",
        )

        # Upper pressure, parameter, and translation invariants.
        add(
            "BG07_upper_pressure_formal_gk_only",
            "upper_pressure_module",
            "上位圧はG/K formal packetのみから作り、O_t・v8・探索・作用情報を混ぜない",
            _first_text(artifacts.upper_pressure_audit, "audit_status") == "pass"
            and _first_bool(artifacts.upper_pressure_audit, "formal_input_is_gk_only")
            and _first_int(artifacts.upper_pressure_audit, "formal_lower_leak_count", 1) == 0,
            f"status={_first_text(artifacts.upper_pressure_audit, 'audit_status')};gk_only={_first_bool(artifacts.upper_pressure_audit, 'formal_input_is_gk_only')};lower_leak={_first_int(artifacts.upper_pressure_audit, 'formal_lower_leak_count', 1)}",
            "upper_pressure_audit",
        )
        add(
            "BG08_pressure_translation_noncompressive_pre_action",
            "pressure_translation_module",
            "上位圧はH11局所受圧場と意味付き圧意図へ非圧縮変換し、ActionFrameやActionModuleは作らない",
            _first_text(artifacts.pressure_translation_audit, "pressure_translation_audit_status") == "pass"
            and _first_bool(artifacts.pressure_translation_audit, "noncompressive_translation_passed")
            and _first_bool(artifacts.pressure_translation_audit, "component_identity_preserved")
            and _first_bool(artifacts.pressure_translation_audit, "component_direction_preserved")
            and not _any_bool(artifacts.pressure_translation_audit, "action_frame_created_by_translation")
            and not _any_bool(artifacts.pressure_translation_audit, "actionmodule_called_by_translation"),
            f"status={_first_text(artifacts.pressure_translation_audit, 'pressure_translation_audit_status')};noncompressive={_first_bool(artifacts.pressure_translation_audit, 'noncompressive_translation_passed')};actionframe={_any_bool(artifacts.pressure_translation_audit, 'action_frame_created_by_translation')};actionmodule={_any_bool(artifacts.pressure_translation_audit, 'actionmodule_called_by_translation')}",
            "pressure_translation_audit",
        )
        add(
            "BG09_parameter_shadow_only_no_commit",
            "parameter_shadow_box",
            "パラメーターはshadow仮更新のみ。本更新・canonical write・world/G/K writebackは禁止",
            _first_text(artifacts.parameter_shadow_audit, "audit_status") == "pass"
            and _first_bool(artifacts.parameter_shadow_audit, "shadow_carryover_enabled")
            and _first_text(artifacts.parameter_shadow_audit, "commit_status") == "not_committed"
            and not _any_bool(artifacts.parameter_shadow_audit, "canonical_write_performed")
            and not _any_bool(artifacts.parameter_shadow_audit, "world_write_performed")
            and not _any_bool(artifacts.parameter_shadow_audit, "gk_writeback_performed"),
            f"status={_first_text(artifacts.parameter_shadow_audit, 'audit_status')};carryover={_first_bool(artifacts.parameter_shadow_audit, 'shadow_carryover_enabled')};commit={_first_text(artifacts.parameter_shadow_audit, 'commit_status')};canonical={_any_bool(artifacts.parameter_shadow_audit, 'canonical_write_performed')};world={_any_bool(artifacts.parameter_shadow_audit, 'world_write_performed')};gk={_any_bool(artifacts.parameter_shadow_audit, 'gk_writeback_performed')}",
            "parameter_shadow_audit",
        )

        add(
            "BG09B_controlled_canonical_update_boundary",
            "controlled_canonical_update",
            "canonical本更新はcommit gate通過・rollback snapshotあり・dry_runでない時だけ許可。world/G/K/O_t/ActionModuleへは書かない",
            _first_text(artifacts.commit_gate_audit, "audit_status") == "pass"
            and _first_text(artifacts.canonical_write_audit, "audit_status") in {"pass", "blocked"}
            and not _any_bool(artifacts.canonical_write_audit, "world_write_performed")
            and not _any_bool(artifacts.canonical_write_audit, "gk_writeback_performed")
            and not _any_bool(artifacts.canonical_write_audit, "ot_writeback_performed")
            and not _any_bool(artifacts.canonical_write_audit, "actionmodule_direct_input")
            and (
                not _any_bool(artifacts.canonical_write_audit, "canonical_write_performed")
                or (
                    _first_bool(artifacts.canonical_write_audit, "commit_gate_passed")
                    and _first_bool(artifacts.canonical_write_audit, "canonical_commit_enabled")
                    and not _first_bool(artifacts.canonical_write_audit, "canonical_commit_dry_run")
                    and _first_bool(artifacts.commit_gate_audit, "rollback_snapshot_ready")
                )
            ),
            f"gate={_first_text(artifacts.commit_gate_audit, 'commit_gate_reason')};write={_any_bool(artifacts.canonical_write_audit, 'canonical_write_performed')};dry_run={_first_bool(artifacts.canonical_write_audit, 'canonical_commit_dry_run')};enabled={_first_bool(artifacts.canonical_write_audit, 'canonical_commit_enabled')}",
            "commit_gate_audit+canonical_write_audit",
        )

        # Exploration and bridge invariants.
        add(
            "BG10_unverified_exploration_cannot_pass",
            "exploration_module",
            "未検証探索候補は作用側へ通さない。Task10ではsandbox検証済みかつlocal audit通過済み候補だけが薄いprojectionになれる",
            not _any_bool(artifacts.exploration_decision, "unverified_candidate_can_pass")
            and _first_bool(artifacts.exploration_decision, "all_passed_candidates_verified", True)
            and not _any_bool(artifacts.exploration_decision, "exploration_generates_pressure")
            and not _any_bool(artifacts.exploration_decision, "exploration_updates_parameter_box")
            and not _any_bool(artifacts.exploration_decision, "exploration_executes_action"),
            f"unverified_can_pass={_any_bool(artifacts.exploration_decision, 'unverified_candidate_can_pass')};passed_count={_first_int(artifacts.exploration_decision, 'passed_count', 0)};all_passed_verified={_first_bool(artifacts.exploration_decision, 'all_passed_candidates_verified', True)};status={_first_text(artifacts.exploration_decision, 'exploration_task7_status', _first_text(artifacts.exploration_decision, 'exploration_task2_status'))}",
            "exploration_decision",
        )
        add(
            "BG10b_local_audit_v8_boundary",
            "local_audit_module",
            "v8局所監査は探索候補・作用候補を見るだけで、G/K生成・上位圧入力・作用実行・書き戻しをしない",
            _rows(artifacts.exploration_local_audit) > 0
            and _rows(artifacts.action_local_audit) > 0
            and _first_text(artifacts.exploration_local_audit, "v8_support_status") == "pass"
            and _first_text(artifacts.action_local_audit, "v8_support_status") == "pass"
            and not _any_bool(artifacts.exploration_local_audit, "v8_is_gk_generator")
            and not _any_bool(artifacts.action_local_audit, "v8_is_gk_generator")
            and not _any_bool(artifacts.exploration_local_audit, "v8_is_upper_formal_input")
            and not _any_bool(artifacts.action_local_audit, "v8_is_upper_formal_input")
            and not _any_bool(artifacts.exploration_local_audit, "v8_writes_gk")
            and not _any_bool(artifacts.action_local_audit, "v8_writes_gk")
            and not _any_bool(artifacts.exploration_local_audit, "v8_writes_world")
            and not _any_bool(artifacts.action_local_audit, "v8_writes_world")
            and not _any_bool(artifacts.exploration_local_audit, "v8_calls_actionmodule")
            and not _any_bool(artifacts.action_local_audit, "v8_calls_actionmodule"),
            f"exploration_rows={_rows(artifacts.exploration_local_audit)};action_rows={_rows(artifacts.action_local_audit)};exploration_status={_first_text(artifacts.exploration_local_audit, 'v8_support_status')};action_status={_first_text(artifacts.action_local_audit, 'v8_support_status')}",
            "exploration_local_audit+action_local_audit",
        )

        add(
            "BG11_exploration_sidecar_retained_projection_thin",
            "exploration_bridge_module",
            "探索文脈はfull sidecarに残し、作用側へは薄いprojectionだけを渡す",
            _rows(artifacts.exploration_sidecar) > 0
            and _first_bool(artifacts.exploration_sidecar, "full_context_present")
            and _first_bool(artifacts.exploration_sidecar, "sidecar_is_noncompressed")
            and (
                not _any_bool(artifacts.exploration_sidecar, "eligible_for_action_projection")
                or (
                    _rows(artifacts.exploration_projection) > 0
                    and _first_bool(artifacts.exploration_projection, "projection_is_thin")
                    and not _any_bool(artifacts.exploration_projection, "projection_contains_full_sidecar_payload")
                    and _first_bool(artifacts.exploration_projection, "projection_source_verified")
                    and _first_bool(artifacts.exploration_projection, "projection_source_local_audit_passed")
                    and not _any_bool(artifacts.exploration_projection, "sidecar_direct_actionmodule_input")
                )
            ),
            f"sidecar_rows={_rows(artifacts.exploration_sidecar)};eligible={_any_bool(artifacts.exploration_sidecar, 'eligible_for_action_projection')};full_context={_first_bool(artifacts.exploration_sidecar, 'full_context_present')};noncompressed={_first_bool(artifacts.exploration_sidecar, 'sidecar_is_noncompressed')};projection_rows={_rows(artifacts.exploration_projection)};projection_thin={_first_bool(artifacts.exploration_projection, 'projection_is_thin')};verified={_first_bool(artifacts.exploration_projection, 'projection_source_verified')};local_audit={_first_bool(artifacts.exploration_projection, 'projection_source_local_audit_passed')}",
            "exploration_sidecar+exploration_projection",
        )

        # Action-side invariants.
        add(
            "BG12_action_surface_pre_actionframe_only",
            "action_surface_planning_module",
            "作用面計画はActionFrame前の候補生成まで。ActionFrame生成・ActionModule呼び出しは禁止",
            _first_text(artifacts.action_surface_planning_audit, "audit_status") == "pass"
            and not _any_bool(artifacts.action_surface_planning_audit, "action_frame_created_by_planning")
            and not _any_bool(artifacts.action_surface_planning_audit, "actionmodule_called_by_planning")
            and not _any_bool(artifacts.action_surface_planning_audit, "planning_writeback_performed"),
            f"status={_first_text(artifacts.action_surface_planning_audit, 'audit_status')};frame={_any_bool(artifacts.action_surface_planning_audit, 'action_frame_created_by_planning')};module={_any_bool(artifacts.action_surface_planning_audit, 'actionmodule_called_by_planning')};writeback={_any_bool(artifacts.action_surface_planning_audit, 'planning_writeback_performed')}",
            "action_surface_planning_audit",
        )
        add(
            "BG13_coactivation_gate_before_actionframe",
            "coactivation_gate_module",
            "同時発火門は圧・探索・作用候補・shadow・riskを見て、ActionFrame前にallow/dampen/defer/block/monitor_onlyを決める",
            _rows(artifacts.coactivation_gate) > 0
            and _first_bool(artifacts.coactivation_gate, "gate_required_before_actionframe")
            and _first_text(artifacts.coactivation_gate, "coactivation_gate_audit_status") == "pass"
            and _first_text(artifacts.coactivation_gate, "coactivation_gate_decision") in {"allow", "dampen", "defer", "block", "monitor_only"}
            and not _any_bool(artifacts.coactivation_gate, "action_frame_created_by_gate")
            and not _any_bool(artifacts.coactivation_gate, "actionmodule_called_by_gate")
            and not _any_bool(artifacts.coactivation_gate, "world_write_performed_by_gate")
            and not _any_bool(artifacts.coactivation_gate, "gk_writeback_performed_by_gate")
            and not _any_bool(artifacts.coactivation_gate, "ot_writeback_performed_by_gate")
            and not _any_bool(artifacts.coactivation_gate, "canonical_parameter_write_by_gate")
            and _first_bool(artifacts.action_execution_audit, "coactivation_gate_applied_before_actionframe"),
            f"gate_rows={_rows(artifacts.coactivation_gate)};gate_decision={_first_text(artifacts.coactivation_gate, 'coactivation_gate_decision')};risk={_first_text(artifacts.coactivation_gate, 'coactivation_risk_score')};required_before_frame={_first_bool(artifacts.coactivation_gate, 'gate_required_before_actionframe')};applied_before_frame={_first_bool(artifacts.action_execution_audit, 'coactivation_gate_applied_before_actionframe')}",
            "coactivation_gate+action_execution_audit",
        )
        direct_core = (
            _any_bool(artifacts.action_execution_audit, "direct_gk_input_to_actionmodule")
            or _any_bool(artifacts.action_execution_audit, "direct_ot_input_to_actionmodule")
            or _any_bool(artifacts.action_execution_audit, "direct_v8_input_to_actionmodule")
            or _any_bool(artifacts.action_execution_audit, "direct_exploration_sidecar_input_to_actionmodule")
            or _any_bool(artifacts.action_execution_audit, "direct_parameter_box_input_to_actionmodule")
        )
        add(
            "BG14_actionmodule_actionframe_only",
            "action_execution_module",
            "作用モジュールはActionFrameだけを読む。G/K・O_t・v8・sidecar・ParameterBoxを直接読まない",
            _first_text(artifacts.action_execution_audit, "audit_status") == "pass"
            and _first_bool(artifacts.action_execution_audit, "actionmodule_received_actionframe_only")
            and not direct_core,
            f"status={_first_text(artifacts.action_execution_audit, 'audit_status')};actionframe_only={_first_bool(artifacts.action_execution_audit, 'actionmodule_received_actionframe_only')};direct_core={direct_core}",
            "action_execution_audit",
        )

        # Audit and guard invariants.
        missing_required = self.validate_audit_row(cycle_audit_row)
        add(
            "BG15_cycle_audit_row_complete",
            "audit_ledger_module",
            "cycle audit rowは必須列を持ち、各周期の因果追跡に使える",
            len(missing_required) == 0 and cycle_audit_row is not None and not cycle_audit_row.empty,
            f"cycle_rows={_rows(cycle_audit_row)};missing_required_count={len(missing_required)}",
            "cycle_audit_row",
        )
        add(
            "BG16_boundary_guard_diagnostic_only",
            "boundary_guard",
            "boundary guardは診断専用で、world/G/K/O_t/ActionFrame/canonical parameterを書き換えない",
            True,
            "guard_writes_world=False;guard_writes_gk=False;guard_writes_ot=False;guard_writes_actionframe=False;guard_writes_canonical_parameter=False",
            "boundary_guard_audit",
            severity="contract",
        )
        return pd.DataFrame(rows)

    def build_boundary_violation_report(self, boundary_guard_audit: pd.DataFrame, existing_violations: list[str] | None = None) -> pd.DataFrame:
        """Return fail rows plus any legacy validation violations.

        Empty report means the boundary guard passed.  Existing validate_*
        violations are included so old and new guard paths are visible in one
        table.
        """
        rows = []
        if boundary_guard_audit is not None and not boundary_guard_audit.empty:
            failed = boundary_guard_audit[boundary_guard_audit["guard_status"].astype(str) == "fail"]
            for _, r in failed.iterrows():
                rows.append({
                    "run_seed": int(r.get("run_seed", -1)),
                    "run_scenario": str(r.get("run_scenario", "unknown")),
                    "loop_step": int(r.get("loop_step", -1)),
                    "violation_source": "boundary_guard_audit",
                    "rule_id": str(r.get("rule_id", "unknown")),
                    "boundary_domain": str(r.get("boundary_domain", "unknown")),
                    "severity": str(r.get("severity", "block_on_fail")),
                    "violation_detail": str(r.get("observed", "")),
                    "task15_violation_report_contract": "Task15_boundary_violation_report__empty_means_pass__RC1",
                })
        for v in existing_violations or []:
            rows.append({
                "run_seed": int(boundary_guard_audit["run_seed"].iloc[0]) if boundary_guard_audit is not None and not boundary_guard_audit.empty else -1,
                "run_scenario": str(boundary_guard_audit["run_scenario"].iloc[0]) if boundary_guard_audit is not None and not boundary_guard_audit.empty else "unknown",
                "loop_step": int(boundary_guard_audit["loop_step"].iloc[0]) if boundary_guard_audit is not None and not boundary_guard_audit.empty else -1,
                "violation_source": "legacy_validate_helper",
                "rule_id": "legacy_validation",
                "boundary_domain": "legacy_boundary_guard",
                "severity": "block_on_fail",
                "violation_detail": str(v),
                "task15_violation_report_contract": "Task15_boundary_violation_report__empty_means_pass__RC1",
            })
        columns = [
            "run_seed", "run_scenario", "loop_step", "violation_source", "rule_id",
            "boundary_domain", "severity", "violation_detail",
            "task15_violation_report_contract",
        ]
        return pd.DataFrame(rows, columns=columns)

    def validate_boundary_guard_audit(self, boundary_guard_audit: pd.DataFrame) -> list[str]:
        violations: list[str] = []
        if boundary_guard_audit is None or boundary_guard_audit.empty:
            return ["boundary_guard_audit_missing"]
        required = {
            "rule_id", "boundary_domain", "invariant_jp", "guard_status", "severity",
            "source_audit_table", "boundary_guard_contract", "guard_writes_world",
            "guard_writes_gk", "guard_writes_ot", "guard_writes_actionframe",
            "guard_writes_canonical_parameter",
        }
        missing = sorted(required - set(boundary_guard_audit.columns))
        if missing:
            violations.append(f"boundary_guard_audit_required_fields_missing:{','.join(missing)}")
        if "guard_status" in boundary_guard_audit.columns and bool((boundary_guard_audit["guard_status"].astype(str) == "fail").any()):
            failed = boundary_guard_audit.loc[boundary_guard_audit["guard_status"].astype(str) == "fail", "rule_id"].astype(str).tolist()
            violations.append(f"boundary_guard_rule_failed:{'|'.join(failed)}")
        for col in ["guard_writes_world", "guard_writes_gk", "guard_writes_ot", "guard_writes_actionframe", "guard_writes_canonical_parameter"]:
            if col in boundary_guard_audit.columns and bool(boundary_guard_audit[col].astype(bool).any()):
                violations.append(f"boundary_guard_diagnostic_only_violation:{col}")
        return violations

    def validate_audit_row(self, audit_row: pd.DataFrame) -> list[str]:
        if audit_row is None or audit_row.empty:
            return ["cycle_audit_row_missing"]
        missing = [c for c in REQUIRED_AUDIT_FIELDS if c not in audit_row.columns]
        return [f"cycle_audit_required_fields_missing:{','.join(missing)}"] if missing else []
