# Phase 2G-3 A/C/D Groups Consolidated Validation and Low-risk Repair Pack

## 1. Scope

This task consolidates A, C, and D group validation into one PR while keeping the validation findings split by A group, C group, D group, and the A→C→D cross-boundary path. The repair scope is intentionally low-risk: audit, export, summary, matrix, naming/readability, legacy comparison, and explicit missing-evidence reporting only.

No behavior-changing repair is included. Any finding that would require changing PressureTranslationModule formulas, ParameterWindow registry values, ParameterShadowBox update formulas, ActionModule behavior, action primitives, action strength design, world dynamics, safety boundaries, acceptance conditions, write paths, or v2 integration is deferred to an individual future task.

## 2. Background

Phase 2G-2d introduced the B-group dampen-only minimal intermediate-conservatism repair. This follow-up validates the remaining A/C/D groups together to reduce task count while preserving evidence granularity. The matrix keeps current, flat, relaxed_legacy_dampen_075, and repaired relaxed modes visible for comparison.

## 3. Group Definitions

| group | scope | modules | allowed repair |
| --- | --- | --- | --- |
| A | Pressure translation and parameter path evidence | `pressure_translation_module.py`, `parameter_window_binder.py`, `parameter_shadow_box.py`, `cycle_state.py` | summary/export/missing-evidence reporting only |
| C | ActionFrame and action boundary evidence | `action_surface_planning_module.py`, `action_execution_module.py`, ActionModule primitive package, `world_adapter.py` | action boundary summaries and channel/result readability only |
| D | world/audit/validation export evidence | `boundary_guard_module.py`/boundary guard exports, `audit_ledger_module.py`, `run_matrix_validation.py`, `profile_loader.py`, matrices | rollup summaries and matrix flags only |
| Cross | A→C→D traceability and forbidden shortcut checks | matrix exports across pressure/window/action/world/audit stages | traceability summaries and deferred-major-candidate separation only |

## 4. Matrix Design

The matrix `configs/matrices/matrix_phase2g3_acd_consolidated_validation_low_risk_repair.json` contains 16 runs of 4–6 steps. It includes required smoke, mode-comparison, relation-lock, no-exploration, high-noise, shock-recovery, sparse-projection, and v2-readiness runs plus four additional stress/readability variants. The v2 runs are readiness checks only; they do not modify or validate v2 as a production premise freeze.

## 5. A Group Findings

Pressure translation evidence is exported in `a_group_pressure_parameter_summary.csv` through `pressure_translation_rows`, and the pressure-to-window evidence is preserved in `acd_cross_boundary_summary.csv`. Parameter window evidence is exported through `parameter_window_rows`, `mode`, and mode comparison fields. The matrix keeps `current`, `flat`, `relaxed_legacy_dampen_075`, and repaired `relaxed` readable.

The ShadowBox write boundary is summarized with `shadow_box_rows`, `canonical_write_detected`, `rollback_snapshot_available`, and `parameter_to_action_direct_path_detected`. The repaired relaxed mode is detected when `intermediate_conservatism_mode == relaxed`, and `relaxed_legacy_dampen_075` remains available as an explicit rollback/comparison mode.

Large repair needed: no. No pressure conversion formula, ParameterWindow registry value, or ShadowBox update formula is changed in this PR.

## 6. C Group Findings

ActionFrame information preservation is summarized in `c_group_action_boundary_summary.csv` via row counts, action mass, channel counts, and source-column presence. ActionModule boundary evidence is captured by `actionmodule_input_boundary_clean`, `direct_parameter_box_input_to_actionmodule`, `gk_access_detected`, and `ot_access_detected`.

Action results remain readable with `action_result_rows` and `action_result_by_channel_available`. Channel readability is reported using serialized `action_channel_counts`, covering observed action channels without changing primitive definitions or strength formulas.

Large repair needed: no. No ActionModule behavior, action primitive, action strength, ActionFrame schema, or world input path is changed in this PR.

## 7. D Group Findings

WorldAdapter/world boundary evidence is summarized in `d_group_world_audit_export_summary.csv` using `world_transition_rows` and `world_actionframe_only_input`. BoundaryGuard and AuditLedger coverage are summarized by `boundary_guard_rows` and `audit_ledger_rows`.

`matrix_summary.json` now includes A/C/D/Cross present flags, pass totals, major-repair count, missing-evidence count, v2 trace readiness, and write/boundary violation totals. v2 trace readiness is reported from v2 trace CSV row availability only; it is not treated as a v2 integration change.

Large repair needed: no. No world dynamics, v2 body, BoundaryGuard safety condition, write path, or acceptance condition is changed in this PR.

## 8. Cross-boundary Findings

The new `acd_cross_boundary_summary.csv` checks pressure-to-window, window-to-ActionFrame, ActionFrame-to-action_result, action_result-to-world, and world-to-audit traceability. It also reports `forbidden_shortcut_detected` and per-run `cross_boundary_pass`.

The validation path remains ActionFrame-centered from C group into D group. The summary explicitly checks that ParameterBox direct input to ActionModule, G/K writeback, O_t writeback, dry-run canonical writes, and rollback-snapshot boundary failures do not appear as passing evidence.

## 9. Low-risk Repairs Applied

| file | repair | group | behavior change? | reason |
| --- | --- | --- | --- | --- |
| `scripts/run_matrix_validation.py` | Added A/C/D/Cross summary CSV builders and matrix summary rollups | A/C/D/Cross | no | Make existing evidence visible without changing runtime behavior |
| `configs/matrices/matrix_phase2g3_acd_consolidated_validation_low_risk_repair.json` | Added bounded 16-run validation matrix | A/C/D/Cross | no | Validate required modes/profiles/readiness paths |
| `docs/PHASE2G3_ACD_CONSOLIDATED_VALIDATION_LOW_RISK_REPAIR.md` | Added consolidated validation report | A/C/D/Cross | no | Separate findings and deferred-major-candidate policy |

## 10. Deferred Major Repair Candidates

| priority | group | module | issue | why deferred | recommended task |
| --- | --- | --- | --- | --- | --- |
| none | none | none | No major repair candidate was identified by this low-risk validation pack. | Not applicable. | Continue to Phase 2G-4 v2 premise freeze pack or post-repair confirmation stress. |

## 11. Validation Results

Validation commands for this PR are:

- `python -m json.tool configs/matrices/matrix_phase2g3_acd_consolidated_validation_low_risk_repair.json > /tmp/matrix_phase2g3_acd_consolidated_validation_low_risk_repair.validated.json`
- `python -m compileall .`
- `python scripts/run_smoke_validation.py`
- `python scripts/run_matrix_validation.py --matrix configs/matrices/matrix_phase2g3_acd_consolidated_validation_low_risk_repair.json --output-dir validation_runs/phase2g3_acd_consolidated_validation_low_risk_repair`

Expected validation evidence is read from `validation_runs/phase2g3_acd_consolidated_validation_low_risk_repair/matrix_summary.json` after the matrix completes. The summary reports `overall_pass`, `boundary_violation_total`, `dry_run_write_violation_count`, `forbidden_write_count`, A/C/D/Cross pass totals, missing-evidence count, major-repair count, and `v2_trace_readiness_pass`.

## 12. Recommendation

Recommended next task: Phase 2G-4 v2 premise freeze pack, optionally preceded by Phase 2G-4 post-repair confirmation stress if maintainers want one more focused stress pass. Individual A/C/D major repair tasks are not recommended unless future evidence creates entries in `deferred_major_repair_candidates.csv`.

## 13. Conclusion

Phase 2G-3 keeps A/C/D/Cross validation separated while reducing task count. The changes are limited to matrix, audit/export summaries, rollup flags, missing-evidence reporting, and documentation. Current, flat, repaired relaxed, and `relaxed_legacy_dampen_075` semantics are preserved, and no prohibited behavior-changing repair is included.
