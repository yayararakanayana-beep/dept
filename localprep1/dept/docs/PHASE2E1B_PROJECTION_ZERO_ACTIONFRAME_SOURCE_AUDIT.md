# Phase 2E-1b Projection-Zero ActionFrame Source Audit

## 1. Scope

- This audit investigates the Phase 2E-1 observation that `projection_rows = 0` while `ActionFrame` rows continue to be generated.
- This is a source-attribution and audit-gap task only. It is not a fix task, performance validation, runner rewrite, matrix change, profile change, or acceptance-condition change.
- Existing code, existing profiles, the existing Phase 2E-1 matrix, runner behavior, acceptance conditions, and existing CSV schemas were not modified.
- The analysis below uses only CSV/JSON files emitted by the existing Phase 2E-1 matrix rerun.

## 2. Main HEAD

- Checkout branch name at work start: `work`; report branch: `phase2e1b-projection-zero-actionframe-source-audit`.
- Phase 2E-1 merge commit confirmed: **yes** (`1cdba45 Merge PR #32: Add Phase 2E-1 exploration zero NO_OP probe`).

```text
1cdba45 Merge PR #32: Add Phase 2E-1 exploration zero NO_OP probe
db50a6b Add Phase 2E-1 exploration zero NO_OP probe
2c2e988 Merge PR #30: Freeze PseudoReality v2 Impl-A handoff
0c54eef Freeze PseudoReality v2 Impl-A handoff
281006b Merge PR #29: Add Phase 2D full integrated summary audit
```

## 3. Test Commands

- `pwd`
- `git status --short --branch`
- `git branch --show-current`
- `git log --oneline -5`
- `cd localprep1/dept`
- `python -m compileall .`
- `python scripts/run_smoke_validation.py`
- `python scripts/run_matrix_validation.py --matrix configs/matrices/matrix_phase2e1_exploration_zero_no_op_probe.json --output-dir validation_runs/phase2e1b_projection_zero_actionframe_source_audit`
- `cat validation_runs/phase2e1b_projection_zero_actionframe_source_audit/matrix_summary.json`
- `find validation_runs/phase2e1b_projection_zero_actionframe_source_audit -maxdepth 3 -type f | sort`

## 4. Matrix Summary

| runs | overall_pass | boundary_violation_total | dry_run_write_violation_count | forbidden_write_count | projection_min | action_frame_min |
|---:|---|---:|---:|---:|---:|---:|
| 10 | true | 0 | 0 | 0 | 0 | 3410 |

## 5. Available Audit Files and Columns

All run directories emitted the required CSV set inspected for this task: `exploration_candidates.csv`, `exploration_sandbox.csv`, `exploration_decision.csv`, `exploration_sidecar.csv`, `exploration_projection.csv`, `action_surface_planning_audit.csv`, `coactivation_gate.csv`, `action_frame.csv`, and `action_execution_audit.csv`. The optional files present included `parameter_shadow_audit.csv`, `parameter_window_binding_audit.csv`, `canonical_write_audit.csv`, `rollback_snapshot.csv`, and `commit_gate_audit.csv`. The optional files `weak_pressure.csv`, `pressure_intent_bundle.csv`, `pressure_translation_audit.csv`, `parameter_updates.csv`, `action_affordance.csv`, `action_candidates.csv`, `local_observation_needs.csv`, and `boundary_guard_audit.csv` were not available as standalone CSVs in these run directories.

Key columns observed:

- `action_frame.csv`: `source_pressure_component`, `component_direction`, `source_semantic_effect`, `semantic_effect`, `intent_family`, `suggested_control_route`, `action_primitive`, `primitive_sequence`, `action_channel`, `action_strength`, `parameter_window_binding_used`, `candidate_status`, `planning_stage`, `pressure_intent_used`, `shadow_parameter_summary_used`, `exploration_projection_used`, `action_frame_created_by_planning`, `actionmodule_called_by_planning`, `reads_gk_directly`, `reads_ot_directly`, `ot_direct_actionmodule_input`, `canonical_parameter_write`, `world_write_performed`, `gk_writeback_performed`, `ot_action_view_used`, `source_candidate_fingerprint`, `coactivation_gate_decision`, `source_action_candidate_rows`, `exploration_projection_rows_available`, `reads_exploration_sidecar_directly`, `reads_parameter_box_directly`, `gate_block_applied`, `gate_defer_applied`, `gate_dampening_applied`, `scheduled_step`, `execute_step`.
- `action_surface_planning_audit.csv`: `pressure_intent_rows`, `ot_action_view_rows`, `affordance_rows`, `action_candidate_rows`, `local_observation_need_rows`, `pressure_intent_used`, `ot_action_view_used`, `shadow_parameter_summary_used`, `parameter_window_binding_used`, `exploration_projection_used`, `action_frame_created_by_planning`, `actionmodule_called_by_planning`, `planning_writeback_performed`, `canonical_write_performed`, `world_write_performed`, `gk_writeback_performed`, `ot_direct_actionmodule_input`, `v8_direct_actionmodule_input`, `exploration_sidecar_direct_actionmodule_input`.
- `coactivation_gate.csv`: `coactivation_gate_decision`, `gate_reason`, `coactivation_risk_score`, `parameter_window_binding_used`, `risk_score`, `pressure_component_score`, `exploration_component_score`, `action_component_score`, `candidate_risk_max`, `action_strength_max`, `action_strength_mean`, `exploration_projection_rows`, `action_candidate_rows`, `exploration_projection_active`, `gate_applies_to_action_frame`, `gate_dampening_factor`, `allow_like_decision`, `dampen_like_decision`, `defer_like_decision`, `block_like_decision`, `monitor_only_decision`, `actionmodule_called_by_gate`, `parameter_box_updated_by_gate`, `world_write_performed_by_gate`, `gk_writeback_performed_by_gate`, `ot_writeback_performed_by_gate`, `canonical_parameter_write_by_gate`.
- `action_execution_audit.csv`: `source_action_candidate_rows`, `action_frame_rows`, `shadow_parameter_rows_available_but_not_passed_to_actionmodule`, `exploration_projection_rows_available_but_only_projection_is_frame_eligible`, `exploration_sidecar_rows_retained_but_not_passed_to_actionmodule`, `coactivation_gate_decision`, `actionmodule_received_actionframe_only`, `direct_gk_input_to_actionmodule`, `direct_ot_input_to_actionmodule`, `direct_v8_input_to_actionmodule`, `direct_exploration_sidecar_input_to_actionmodule`, `direct_parameter_box_input_to_actionmodule`, `canonical_parameter_write_performed`, `gk_writeback_performed`, `ot_writeback_performed`, `world_step_performed_by_adapter`.
- `exploration_decision.csv`: `decision_status`, `decision_score`, `decision_reason`, `sandbox_status`, `sandbox_verified`, `candidate_count`, `sandbox_count`, `passed_count`, `watch_count`, `blocked_count`, `exploration_updates_parameter_box`, `exploration_executes_action`, `exploration_writes_world`, `exploration_writes_gk`, `exploration_writes_ot`.
- `exploration_sidecar.csv`: includes the decision columns above plus sidecar/bridge columns such as `sidecar_direct_actionmodule_input`, `bridge_writes_world`, `bridge_writes_gk`, `bridge_writes_ot`, `bridge_updates_parameter_box`, `bridge_calls_actionmodule`, `bridge_creates_actionframe`, `parameter_window_binding_used`, `passes_projection_adoption_threshold`, `eligible_for_action_projection`, `bridge_status`.
- `exploration_projection.csv`: for projection-zero runs the file exists but has no header/data rows; for enabled controls it exposes projection provenance columns including `projection_id`, `sidecar_id`, `candidate_axis_id`, `action_channel_hint`, `projection_strength`, `projection_decision`, `projection_source_verified`, `projection_writes_world`, `projection_writes_gk`, `projection_writes_ot`, `projection_updates_parameter_box`, `projection_calls_actionmodule`, and `projection_creates_actionframe`.

## 6. Projection-Zero Run Table

| run label | exploration_enabled | candidates | decision | projection | action_frame | strength sum | strength max | exploration_projection_used T/F | exploration_injection | no_op | gate risk mean | binding planning/gate | classification |
|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---|---|
| `repro_slow_drift_default_phase2b_zero_projection` | default | 153 | 153 | 0 | 3410 | 15.204 | 0.009 | 0 / 3410 | 1056 | 0 | 0.443 | true / true | C |
| `repro_exploration_loss_no_exploration_default` | false | 0 | 24 | 0 | 3410 | 15.898 | 0.009 | 0 / 3410 | 1056 | 0 | 0.446 | true / true | B/C |
| `repro_exploration_loss_no_exploration_buffered` | false | 0 | 36 | 0 | 5126 | 24.065 | 0.009 | 0 / 5126 | 1584 | 0 | 0.451 | true / true | B/C |
| `repro_slow_drift_low_coupling_no_exploration` | false | 0 | 36 | 0 | 5126 | 23.599 | 0.009 | 0 / 5126 | 1584 | 0 | 0.461 | true / true | B/C |
| `repro_shock_no_exploration_buffered` | false | 0 | 36 | 0 | 5522 | 20.677 | 0.009 | 0 / 5522 | 1188 | 0 | 0.437 | true / true | B/C |
| `probe_exploration_loss_no_exploration_low_coupling` | false | 0 | 24 | 0 | 3410 | 16.040 | 0.009 | 0 / 3410 | 1056 | 0 | 0.441 | true / true | B/C |

Classification key: `B` = expected exploration-disabled behavior; `C` = ActionFrame remains but exact row-level source attribution is incomplete in existing CSVs. The default slow-drift run is classified `C` rather than `B` because exploration was not explicitly disabled: candidates and decisions existed, but decisions were `watch`/`block`, projection remained zero, and non-projection ActionFrame channels continued.

## 7. Action Channel Breakdown

| run label | exploration_injection | uncertainty_probe | buffer_increase | relation_unlock / guarded_relation_unlock | volatility_damping | coupling_relief | no_op | other |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `repro_slow_drift_default_phase2b_zero_projection` | 1056 | 792 | 528 | 506 | 0 | 528 | 0 | 0 |
| `repro_exploration_loss_no_exploration_default` | 1056 | 792 | 528 | 506 | 0 | 528 | 0 | 0 |
| `repro_exploration_loss_no_exploration_buffered` | 1584 | 1188 | 792 | 770 | 0 | 792 | 0 | 0 |
| `repro_slow_drift_low_coupling_no_exploration` | 1584 | 1188 | 792 | 770 | 0 | 792 | 0 | 0 |
| `repro_shock_no_exploration_buffered` | 1188 | 836 | 1188 | 770 | 0 | 792 | 0 | 748 |
| `probe_exploration_loss_no_exploration_low_coupling` | 1056 | 792 | 528 | 506 | 0 | 528 | 0 | 0 |

The shock run's `other` rows are `diagnostic_probe_restraint_direct` (396) and `diagnostic_update_restraint` (352).

## 8. Source Attribution Attempt

- `exploration_projection` derived: Existing CSVs support a negative attribution for projection-zero runs. `action_frame.csv` and `action_surface_planning_audit.csv` both show `exploration_projection_used = False` for all projection-zero rows/steps. Therefore the remaining ActionFrame rows are not recorded as projection-derived.
- `pressure / parameter` derived: Existing CSVs show `pressure_intent_used = True`, `shadow_parameter_summary_used = True`, and `parameter_window_binding_used = True` in planning/action-frame records. This supports that pressure/shadow-parameter/windowed planning inputs are active, but it does not give a precise per-row source label proving which input caused each ActionFrame row.
- `WindowBinder / binding` derived: `parameter_window_binding_used = True` is present in planning and gate audit rows for all projection-zero runs. This supports a binding-mediated planning/gating path, but not a complete row-level origin chain.
- `guard / buffer` derived: Channel names such as `buffer_increase`, `coupling_relief`, and `guarded_relation_unlock` strongly indicate guard/buffer/action-safety channels. However, the CSVs do not expose a direct `source`/`planning_source`/`gate_source` column that would prove source category for every row.
- source-column gap: `action_frame.csv` has useful fields (`source_pressure_component`, `source_semantic_effect`, `planning_stage`, `source_candidate_fingerprint`) but no explicit `action_source`, `planning_source`, `pressure_source`, `binding_source`, or `gate_source` classification column. Exact source attribution remains partially unknown.

## 9. Exploration Injection Under Zero Projection

`exploration_injection` rows remain in every projection-zero run: 1056 rows in 24-step default/low-coupling runs, 1584 rows in 36-step buffered/low-coupling runs, and 1188 rows in the shock buffered run. This is the most important audit finding.

Available evidence says these rows are **not recorded as exploration-projection-derived** because `exploration_projection_used = False` for all ActionFrame rows when `projection_rows = 0`, and planning audit also records `exploration_projection_used = False` for every step. The most conservative interpretation is:

- `exploration_injection` appears to be an action-channel name that can be produced by the general action planning path even when no exploration projection is active.
- The name is potentially misleading under zero projection because it sounds exploration-derived while the exposed audit says no projection was used.
- Existing CSVs do not provide enough row-level source columns to decide whether the channel is a safe general action channel, a pressure/parameter/binding action, or a stale exploration-adjacent action name.
- No boundary/write failure was observed, and action strength maxima stayed bounded at `0.009`, so this is not currently evidenced as an unsafe write or ActionModule boundary breach.
- A future audit column should disambiguate `exploration_injection` source semantics before any suppression decision is made.

## 10. Boundary / Write / ActionModule Integrity

- Boundary violation rows: `0` total.
- Dry-run write violations: `0` total.
- Forbidden writes: `0` total.
- Direct ParameterBox input to ActionModule: `false` in matrix metrics and action execution audit.
- Canonical write audit files are present; no forbidden write was detected by the matrix summary.
- G/K/O_t writeback from planning/gate/action-frame surfaces was not observed in the inspected boolean columns.
- Rollback snapshot rows and commit gate rows matched run steps: 24/24 for 24-step runs and 36/36 for 36-step runs.
- Coactivation gate continued to allow one initial step and dampen the remaining steps in every projection-zero run (`allow: 1`, then `dampen: steps - 1`), so the gate is passing/dampening ActionFrame flow rather than blocking all action under zero projection.

## 11. Interpretation

Overall classification: **Action without source clarity**, with a secondary **Expected exploration-disabled behavior** explanation for the explicitly disabled runs.

Details:

- For exploration-disabled runs, candidate and sandbox rows are zero, decisions are `skipped_disabled`, projection rows are zero, and ActionFrame rows continue through non-projection planning/gating. This is expected behavior at the broad run level.
- For the default slow-drift reproduction, exploration was not disabled: candidates/sandbox/decisions exist, but decision statuses are `watch`/`block`, so projection rows are zero. ActionFrame rows still continue.
- The available CSVs are enough to say the surviving ActionFrame rows are not marked as `exploration_projection` derived.
- The available CSVs are not enough to provide exact row-level source attribution for `exploration_injection` or to distinguish pressure-derived vs binding-derived vs guard/buffer-derived causes for each ActionFrame row.
- Therefore this audit does not justify code changes or suppression in this task; it identifies an audit-column gap.

## 12. Recommended Next Step

Recommended next task: **Phase 2E-1c: `actionframe_source_column_patch`** or equivalent audit-column enhancement.

The next small loop should add explicit no-behavior-change audit fields such as `action_source_category`, `planning_source`, `pressure_source`, `binding_source`, `gate_source`, and a clarified flag for whether `exploration_injection` came from an actual exploration projection. If the project prefers to continue probes first, Phase 2E-2 `high_noise_gate_risk_probe` can proceed, but the source-attribution gap should remain tracked.
