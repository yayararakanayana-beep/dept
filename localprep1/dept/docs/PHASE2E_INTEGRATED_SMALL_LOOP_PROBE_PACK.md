# Phase 2E Integrated Small-Loop Probe Pack

## 1. Scope

This report records the Phase 2E integrated small-loop probe pack. The purpose is hole-finding across closed-loop connection, ActionFrame source attribution, gate behavior, rollback/commit continuity, and ActionModule boundary integrity. It is not a performance comparison or tuning pass.

No runtime behavior was changed. The work adds only:

- `configs/matrices/matrix_phase2e_integrated_small_loop_probe_pack.json`
- `docs/PHASE2E_INTEGRATED_SMALL_LOOP_PROBE_PACK.md`

The runner, ActionExecutionModule, ActionFrame generation, gate decisions, action strength calculation, ActionModule boundary, acceptance rules, existing matrices, and existing profiles were left unchanged.

## 2. Background

Phase 2E-1 confirmed that ActionFrames can remain present even when `projection_rows = 0`.

Phase 2E-1b classified limited readability of those ActionFrame sources as a hole.

Phase 2E-1c / PR #34 added source-audit columns to ActionFrame output and aggregate source-audit fields to `action_execution_audit`. This integrated probe uses those columns to check whether ActionFrame source, exploration projection use, exploration channel semantics, and gate source remain readable across several small-loop stress conditions.

Confirmed ActionFrame audit columns:

- `action_source_category`
- `planning_source`
- `pressure_source`
- `binding_source`
- `gate_source`
- `exploration_projection_source`
- `exploration_channel_semantics`
- `action_source_audit_contract`

Confirmed `action_execution_audit` aggregate columns:

- `action_source_audit_columns_present`
- `action_source_category_values`
- `exploration_channel_semantics_values`

## 3. Matrix Design

Added matrix file: `configs/matrices/matrix_phase2e_integrated_small_loop_probe_pack.json`.

The matrix contains 20 runs, grouped into five categories with four runs each:

| Category | Runs | Aim |
|---|---:|---|
| Shock Recovery | 4 | Check ActionFrame continuity, gate behavior, source readability, and boundary safety after shock conditions. |
| Relation Lock / Unlock | 4 | Check whether relation-lock conditions thin ActionFrames, overproduce unlock-like action, or obscure source attribution. |
| High Noise Gate Risk | 4 | Check whether high noise over-dampens or blocks gate behavior and whether source audits remain readable. |
| Strong Action Boundary | 4 | Check strong-action settings against action-strength bounds and ActionModule boundary constraints. |
| K_t / Window Short Memory | 4 | Check short-memory behavior for source ambiguity, gate overreaction, and boundary/write integrity. |

All run definitions reuse keys already present in existing matrices: `seed`, `steps`, `exploration_enabled`, `action_coupling`, `drift_scale`, `shock_time`, `shock_strength`, `noise_scale`, `max_action_strength`, `strength_scale`, and `kt_window`.

## 4. Validation Commands

Executed from `localprep1/dept`:

```bash
python -m json.tool configs/matrices/matrix_phase2e_integrated_small_loop_probe_pack.json > /tmp/matrix_phase2e_integrated_small_loop_probe_pack.validated.json
python -m compileall .
python scripts/run_smoke_validation.py
python scripts/run_matrix_validation.py --matrix configs/matrices/matrix_phase2e_integrated_small_loop_probe_pack.json --output-dir validation_runs/phase2e_integrated_small_loop_probe_pack
cat validation_runs/phase2e_integrated_small_loop_probe_pack/matrix_summary.json
```

Cleanup after recording results:

```bash
rm -rf validation_runs
find . -type d \( -name "__pycache__" -o -name "pycache" \) -prune -exec rm -rf {} +
```

## 5. Matrix Summary

| Metric | Result |
|---|---:|
| runs | 20 |
| overall_pass | true |
| boundary_violation_total | 0 |
| dry_run_write_violation_count | 0 |
| forbidden_write_count | 0 |
| projection_min | 0 |
| action_frame_min | 737 |

`projection_min = 0` occurred in exploration-disabled cases and is not treated as a failure. In those cases, PR #34 audit columns still made ActionFrame source readable as pressure/parameter/binding planned actions with no projection available.

## 6. Category Results

### 6.1 Shock Recovery

Run labels:

- `shock_default_recovery_probe`
- `shock_buffered_recovery_probe`
- `shock_no_exploration_recovery_probe`
- `shock_low_coupling_recovery_probe`

| Run | ActionFrame rows | Projection rows | action_source_category | exploration_projection_source | exploration_channel_semantics | gate_source | action_strength max | pre_gate_action_strength max | gate_dampening_applied | Boundary/write/ActionModule violations | Rollback / commit gate | Hole candidate |
|---|---:|---:|---|---|---|---|---:|---:|---|---|---|---|
| shock_default_recovery_probe | 902 | 13 | mixed pressure/parameter/binding + exploration projection | used_by_planning | not_exploration_injection; projection-derived/mixed | dampen | 0.0048 | 0.0096 | all true | none | 6 / 6 | observation: full dampening |
| shock_buffered_recovery_probe | 902 | 19 | mixed pressure/parameter/binding + exploration projection | used_by_planning | not_exploration_injection; projection-derived/mixed | dampen | 0.0048 | 0.0096 | all true | none | 6 / 6 | observation: full dampening |
| shock_no_exploration_recovery_probe | 902 | 0 | pressure_parameter_binding_planned | none_available | not_exploration_injection; general action channel not projection-derived | allow; dampen | 0.0090 | 0.0096 | 770 true / 132 false | none | 6 / 6 | low: projection-zero source is readable but non-projection injection semantics need continued watching |
| shock_low_coupling_recovery_probe | 902 | 6 | mixed plus pressure_parameter_binding_planned | used_by_planning; none_available | not_exploration_injection; projection-derived/mixed; general action channel not projection-derived | dampen | 0.0048 | 0.0096 | all true | none | 6 / 6 | observation: full dampening |

Shock runs did not stop ActionFrame generation after shock conditions. Rollback/commit rows remained present and boundary/write checks stayed clean. The most notable pattern is broad dampening in most shock variants.

### 6.2 Relation Lock / Unlock

Run labels:

- `relation_lock_default_probe`
- `relation_lock_buffered_probe`
- `relation_unlock_pressure_probe`
- `relation_lock_low_coupling_probe`

| Run | ActionFrame rows | Projection rows | action_source_category | exploration_projection_source | exploration_channel_semantics | gate_source | action_strength max | pre_gate_action_strength max | gate_dampening_applied | Boundary/write/ActionModule violations | Rollback / commit gate | Hole candidate |
|---|---:|---:|---|---|---|---|---:|---:|---|---|---|---|
| relation_lock_default_probe | 836 | 3 | pressure_parameter_binding_planned; mixed | none_available; used_by_planning | not_exploration_injection; general action channel; projection-derived/mixed | allow; dampen | 0.0090 | 0.0096 | 715 true / 121 false | none | 6 / 6 | medium: low projection count and mixed source modes deserve focused follow-up |
| relation_lock_buffered_probe | 836 | 6 | mixed; pressure_parameter_binding_planned | used_by_planning; none_available | not_exploration_injection; projection-derived/mixed; general action channel | dampen | 0.0048 | 0.0096 | all true | none | 6 / 6 | observation: full dampening |
| relation_unlock_pressure_probe | 737 | 8 | mixed | used_by_planning | not_exploration_injection; projection-derived/mixed | dampen | 0.0048 | 0.0096 | all true | none | 6 / 6 | medium: thinnest ActionFrame count and full dampening |
| relation_lock_low_coupling_probe | 836 | 3 | pressure_parameter_binding_planned; mixed | none_available; used_by_planning | not_exploration_injection; general action channel; projection-derived/mixed | allow; dampen | 0.0090 | 0.0096 | 715 true / 121 false | none | 6 / 6 | medium: relation-lock low-coupling has low projection count |

Relation-lock variants stayed within boundary and write constraints but were the thinnest category. `relation_unlock_pressure_probe` produced the matrix-wide ActionFrame minimum of 737 rows.

### 6.3 High Noise Gate Risk

Run labels:

- `high_noise_default_gate_probe`
- `high_noise_buffered_gate_probe`
- `high_noise_strong_gate_probe`
- `high_noise_no_exploration_gate_probe`

| Run | ActionFrame rows | Projection rows | action_source_category | exploration_projection_source | exploration_channel_semantics | gate_source | action_strength max | pre_gate_action_strength max | gate_dampening_applied | Boundary/write/ActionModule violations | Rollback / commit gate | Hole candidate |
|---|---:|---:|---|---|---|---|---:|---:|---|---|---|---|
| high_noise_default_gate_probe | 902 | 22 | mixed | used_by_planning | not_exploration_injection; projection-derived/mixed | dampen | 0.0048 | 0.0096 | all true | none | 6 / 6 | observation: full dampening |
| high_noise_buffered_gate_probe | 902 | 31 | mixed | used_by_planning | not_exploration_injection; projection-derived/mixed | dampen | 0.0048 | 0.0096 | all true | none | 6 / 6 | observation: full dampening |
| high_noise_strong_gate_probe | 902 | 27 | mixed | used_by_planning | not_exploration_injection; projection-derived/mixed | dampen | 0.0048 | 0.0096 | all true | none | 6 / 6 | observation: full dampening under strong setting |
| high_noise_no_exploration_gate_probe | 902 | 0 | pressure_parameter_binding_planned | none_available | not_exploration_injection; general action channel not projection-derived | allow; dampen | 0.0096 | 0.0096 | 462 true / 440 false | none | 6 / 6 | low: projection-zero high-noise semantics should remain visible in future summaries |

High-noise runs passed without forbidden writes or dry-run write violations. Source categories did not collapse into `unknown_source`. Exploration-disabled high-noise used readable non-projection attribution.

### 6.4 Strong Action Boundary

Run labels:

- `strong_action_default_boundary_probe`
- `strong_action_buffered_boundary_probe`
- `strong_action_shock_boundary_probe`
- `strong_action_relation_lock_boundary_probe`

| Run | ActionFrame rows | Projection rows | action_source_category | exploration_projection_source | exploration_channel_semantics | gate_source | action_strength max | pre_gate_action_strength max | gate_dampening_applied | Boundary/write/ActionModule violations | Rollback / commit gate | Hole candidate |
|---|---:|---:|---|---|---|---|---:|---:|---|---|---|---|
| strong_action_default_boundary_probe | 902 | 29 | mixed | used_by_planning | not_exploration_injection; projection-derived/mixed | dampen | 0.0048 | 0.0096 | all true | none | 6 / 6 | observation: strong setting dampened to same bound |
| strong_action_buffered_boundary_probe | 902 | 29 | mixed | used_by_planning | not_exploration_injection; projection-derived/mixed | dampen | 0.0048 | 0.0096 | all true | none | 6 / 6 | observation: strong setting dampened to same bound |
| strong_action_shock_boundary_probe | 902 | 21 | mixed | used_by_planning | not_exploration_injection; projection-derived/mixed | dampen | 0.0048 | 0.0096 | all true | none | 6 / 6 | observation: shock + strong setting remained bounded |
| strong_action_relation_lock_boundary_probe | 836 | 7 | mixed; pressure_parameter_binding_planned | used_by_planning; none_available | not_exploration_injection; projection-derived/mixed; general action channel | dampen | 0.0048 | 0.0096 | all true | none | 6 / 6 | low: relation-lock strong-action source mix merits follow-up |

Strong-action settings did not breach ActionModule or write boundaries. `direct_parameter_box_input_to_actionmodule` remained false in all runs.

### 6.5 K_t / Window Short Memory

Run labels:

- `kt_short_memory_default_probe`
- `kt_short_memory_shock_probe`
- `kt_short_memory_relation_lock_probe`
- `kt_short_memory_high_noise_probe`

| Run | ActionFrame rows | Projection rows | action_source_category | exploration_projection_source | exploration_channel_semantics | gate_source | action_strength max | pre_gate_action_strength max | gate_dampening_applied | Boundary/write/ActionModule violations | Rollback / commit gate | Hole candidate |
|---|---:|---:|---|---|---|---|---:|---:|---|---|---|---|
| kt_short_memory_default_probe | 902 | 36 | mixed | used_by_planning | not_exploration_injection; projection-derived/mixed | dampen | 0.0048 | 0.0096 | all true | none | 6 / 6 | observation: full dampening |
| kt_short_memory_shock_probe | 902 | 16 | mixed; pressure_parameter_binding_planned | used_by_planning; none_available | not_exploration_injection; projection-derived/mixed; general action channel | dampen | 0.0048 | 0.0096 | all true | none | 6 / 6 | low: short-memory shock mixes projection and non-projection attribution |
| kt_short_memory_relation_lock_probe | 748 | 7 | mixed | used_by_planning | not_exploration_injection; projection-derived/mixed | dampen | 0.00493 | 0.00986 | all true | none | 6 / 6 | medium: short-memory relation-lock thins ActionFrames |
| kt_short_memory_high_noise_probe | 902 | 26 | mixed | used_by_planning | not_exploration_injection; projection-derived/mixed | dampen | 0.0048 | 0.0096 | all true | none | 6 / 6 | observation: full dampening |

Short-memory did not make source audits unreadable and did not produce boundary/write violations. The relation-lock short-memory variant was the main weak spot.

## 7. Cross-Category Findings

- Most stable category: strong action boundary, because all variants stayed bounded and clean despite increased action-strength settings.
- Most suspicious category: relation lock / unlock, because it had the lowest ActionFrame counts and low projection counts.
- ActionFrame-thinned category: relation lock / unlock, especially `relation_unlock_pressure_probe` at 737 rows and `kt_short_memory_relation_lock_probe` at 748 rows.
- Strongest gate reaction: most categories showed all-row dampening in many runs. This is not a failure here, but it is the clearest recurring observation.
- Hardest source category to read: projection-zero exploration-disabled runs, although PR #34 columns made them readable as `pressure_parameter_binding_planned` with `none_available` projection source.
- Hardest exploration-injection semantics to interpret: `exploration_injection_general_action_channel_not_projection_derived`, which is readable but should be explained more explicitly in a future source-semantics report.
- Next likely individual follow-up: relation-lock and short-memory relation-lock probes, focused on why ActionFrame counts thin relative to the rest of the pack while boundaries remain clean.

## 8. Hole Candidate List

| severity | category | run | symptom | likely source | recommended next task |
|---|---|---|---|---|---|
| medium | Relation Lock / Unlock | relation_unlock_pressure_probe | Lowest ActionFrame count: 737, with full dampening | relation-lock pressure/gate interaction | Focused relation-unlock pressure source audit |
| medium | K_t / Window Short Memory | kt_short_memory_relation_lock_probe | Low ActionFrame count: 748, full dampening | short memory + relation-lock interaction | Focused short-memory relation-lock probe |
| medium | Relation Lock / Unlock | relation_lock_default_probe | Projection rows only 3; mixed projection/no-projection source modes | relation-lock source thinning | Relation-lock projection source readability follow-up |
| low | High Noise Gate Risk | high_noise_no_exploration_gate_probe | projection_rows = 0 with non-projection exploration-injection semantics | exploration disabled high-noise channel semantics | Clarify non-projection exploration-injection terminology |
| low | Shock Recovery | shock_no_exploration_recovery_probe | projection_rows = 0; source remains readable but semantics are non-projection | exploration disabled shock channel semantics | Keep in Phase 2E summary as projection-zero readable control |
| observation_only | Cross-category | many dampened runs | Gate dampening applied to every ActionFrame row in many runs | stress profile and gate risk behavior | Summarize gate dampening prevalence before any behavior change |

No blocker or high-severity hole was found in this integrated pack.

## 9. Interpretation

Looking at Phase 2E-2 through Phase 2E-6 together was useful. It showed that projection-zero, relation-lock, high-noise, strong-action, and short-memory cases can be compared with the same audit vocabulary.

PR #34 audit columns were sufficiently useful for this pass. `action_source_category`, `exploration_projection_source`, `exploration_channel_semantics`, and `gate_source` remained present and interpretable, including in projection-zero runs.

No immediate implementation fix is required before Phase 2E Summary. The best follow-up categories are relation-lock / unlock and short-memory relation-lock, because those are where ActionFrame rows thinned most while all boundary/write constraints still passed.

The pack can proceed to Phase 2E Summary as a no-runtime-change validation artifact.

## 10. Conclusion

The Phase 2E integrated small-loop probe pack passed locally:

- `overall_pass: true`
- `boundary_violation_total: 0`
- `dry_run_write_violation_count: 0`
- `forbidden_write_count: 0`
- `action_frame_min: 737`
- `action_source_audit_columns_present: true` in inspected run-level action execution audits

The integrated pack did not expose boundary violations, direct ParameterBox input to ActionModule, forbidden writes, dry-run write violations, canonical write boundary failures, or unreadable ActionFrame source audits. It did surface observation-level and medium-priority follow-up candidates around relation-lock thinning, short-memory relation-lock thinning, projection-zero source semantics, and cross-category all-row gate dampening.

Recommended next task: proceed to Phase 2E Summary, then open focused follow-up work for relation-lock / unlock and K_t short-memory relation-lock behavior if Phase 2E Summary agrees these are worth isolating.
