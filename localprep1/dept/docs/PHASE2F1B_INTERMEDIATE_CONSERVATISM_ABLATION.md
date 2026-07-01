# Phase 2F-1b Intermediate Conservatism Ablation Validation

## 1. Scope

This validation adds an explicit `intermediate_conservatism_mode` ablation switch for comparing `current`, `relaxed`, and `flat` behavior in the relation-unlock pressure probes. It is not a production behavior change: unspecified configuration defaults to `current`, preserving existing behavior.

## 2. Background

Phase 2F-1 found relation-unlock pressure runs with comparatively thin ActionFrames: `relation_unlock_pressure_focus_probe` 704 rows, `relation_unlock_pressure_dominant_probe` 726 rows, `relation_unlock_pressure_gate_observation_probe` 748 rows, and `relation_unlock_no_exploration_probe` 759 rows. Boundary/write audits were clean and source-audit columns were readable, so Phase 2F-1b checks whether thinning is caused by distributed intermediate conservatism rather than only upper pressure or ActionModule actuation.

The intended placement direction is: upper layers should emit cautious pressure, ActionModule/actuation layers should handle system-specific actuation strength, and intermediate layers should mostly provide translation, source audit, and boundary blocking rather than discretionary weakening.

## 3. Conservatism Placement Map

| layer | current conservative behavior | type | should remain? | reason |
|---|---|---|---|---|
| CoactivationGateModule | allow/dampen/defer/block/monitor_only; dampen applies a factor | discretionary weakening plus boundary safety | partially | defer/block/hard-block safety remains; dampen factor/threshold are ablated |
| ActionExecutionModule | applies gate dampening and prevents frames on block/defer | translation plus boundary safety | partially | block/defer and ActionFrame-only boundary remain; dampening factor is mode-controlled |
| ParameterWindowBinder | binds sparsity threshold, gate thresholds, channel gains | discretionary weakening | ablation-only | mode changes are only explicit matrix overrides; default is current |
| ActionSurfacePlanningModule | applies channel gains and candidate sparsity filtering | translation plus discretionary filtering | partially | pre-ActionFrame contract remains; filtering/gains are ablated |
| RepairedDiagnosticActionPolicy | delayed guarded unlock with 0.70 pending strength | system-specific actuation | compare | relaxed/flat alter pending strength; flat preserves delay in this implementation |
| ActionModule / world adapter | receives ActionFrame only and steps world | boundary safety and actuation | yes | never receives ParameterBox, G/K, O_t, or exploration sidecars |

## 4. Ablation Mode Design

- `current`: existing behavior. Gate dampening factor is 0.50, ParameterWindow thresholds/gains are unchanged, candidate sparsity is unchanged, and guarded unlock is delayed with strength factor 0.70.
- `relaxed`: dampening factor is 0.75; dampen threshold is raised to make dampening less likely while preserving defer/block thresholds; candidate sparsity is halved; relation-unlock family gains are neutralized to at least 1.00; guarded unlock delay remains with strength factor 0.90.
- `flat`: dampening is effectively allow-like with factor 1.00; candidate sparsity is 0.00; channel gains are 1.00; hard block/defer paths remain; guarded unlock delay is preserved with strength factor 1.00 (`flat-delay-preserved`).

## 5. Matrix Design

Matrix: `configs/matrices/matrix_phase2f1b_intermediate_conservatism_ablation.json`.

Run count: 24. Each group uses the same seed/profile/step settings and varies only `intermediate_conservatism_mode` across `current`, `relaxed`, and `flat`.

Groups: relation-unlock pressure, pressure-dominant, gate-observation, no-exploration, relation-lock default control, binding control, longer relation-unlock, and longer relation-lock control.

## 6. Validation Commands

```bash
cd localprep1/dept
python -m json.tool configs/matrices/matrix_phase2f1b_intermediate_conservatism_ablation.json > /tmp/matrix_phase2f1b_intermediate_conservatism_ablation.validated.json
python -m compileall .
python scripts/run_smoke_validation.py
python scripts/run_matrix_validation.py --matrix configs/matrices/matrix_phase2f1b_intermediate_conservatism_ablation.json --output-dir validation_runs/phase2f1b_intermediate_conservatism_ablation
cat validation_runs/phase2f1b_intermediate_conservatism_ablation/matrix_summary.json
```

## 7. Matrix Summary

| runs | overall_pass | boundary_violation_total | dry_run_write_violation_count | forbidden_write_count | projection_min | action_frame_min | action_source_audit_columns_present |
|---:|---|---:|---:|---:|---:|---:|---|
| 24 | true | 0 | 0 | 0 | 0 | 704 | true |

## 8. Current vs Relaxed vs Flat Results

| group | current rows | relaxed rows | flat rows | current action_mass | relaxed action_mass | flat action_mass | current gate | relaxed gate | flat gate | boundary status | world outcome summary | interpretation |
|---|---:|---:|---:|---:|---:|---:|---|---|---|---|---|---|
| relation_unlock_pressure | 704 | 836 | 836 | 3.388 | 5.924 | 6.901 | 0.50/current | 0.75/relaxed | 1.00/flat | clean | no boundary/write violation; no zero ActionFrame | rows and mass improve |
| relation_unlock_pressure_dominant | 726 | 836 | 836 | 3.115 | 6.879 | 6.981 | 0.50/current | 0.75/relaxed | 1.00/flat | clean | no boundary/write violation; no zero ActionFrame | rows and mass improve |
| relation_unlock_gate | 748 | 836 | 836 | 3.580 | 5.756 | 7.096 | 0.50/current | 0.75/relaxed | 1.00/flat | clean | no boundary/write violation; no zero ActionFrame | rows and mass improve |
| relation_unlock_no_exploration | 759 | 836 | 836 | 3.606 | 6.990 | 7.091 | 0.50/current | 0.75/relaxed | 1.00/flat | clean | projection_min includes intended no-exploration zeros | rows and mass improve without exploration |
| relation_lock_default_control | 836 | 836 | 836 | 3.470 | 6.531 | 7.239 | 0.50/current | 0.75/relaxed | 1.00/flat | clean | no zero ActionFrame | mass increases; rows already saturated |
| relation_lock_binding_control | 836 | 836 | 836 | 3.848 | 6.701 | 7.110 | 0.50/current | 0.75/relaxed | 1.00/flat | clean | no zero ActionFrame | mass increases; rows already saturated |
| relation_unlock_longer_run | 1584 | 1694 | 1694 | 6.961 | 11.322 | 14.937 | 0.50/current | 0.75/relaxed | 1.00/flat | clean | no zero ActionFrame | longer run confirms improvement |
| relation_lock_longer_run_control | 1694 | 1694 | 1694 | 7.557 | 14.317 | 14.859 | 0.50/current | 0.75/relaxed | 1.00/flat | clean | no zero ActionFrame | mass increases; rows already saturated |

## 9. Relation Unlock Pressure Findings

The relation-unlock pressure family improves in both `relaxed` and `flat`: the focused run rises from 704 to 836 rows, pressure-dominant from 726 to 836, gate-observation from 748 to 836, and no-exploration from 759 to 836. Action mass also rises materially. This indicates that at least part of the Phase 2F-1 thinning is attributable to intermediate conservatism: gate dampening, candidate sparsity, channel gains, and guarded-unlock strength all contribute.

## 10. Boundary Safety Findings

All 24 runs passed with `boundary_violation_total: 0`, `dry_run_write_violation_count: 0`, and `forbidden_write_count: 0`. Flat mode preserved ActionFrame-only ActionModule input, canonical-write prohibition, dry-run write prohibition, G/K/O_t writeback prohibition, and max-action-strength clipping.

## 11. Hole Candidate List

| severity | condition | symptom | likely source | recommended next task |
|---|---|---|---|---|
| observation_only | flat keeps guarded unlock delayed | report must mark `flat-delay-preserved` | RepairedDiagnosticActionPolicy sequencing | optionally compare no-delay in a later isolated ablation |
| medium | flat increases action mass substantially | safety is clean in short/medium runs but mass jumps | distributed discretionary weakening | run longer outcome-focused matrix before production changes |
| observation_only | projection_min is 0 | no-exploration rows are intentional | matrix design | keep projection-zero non-failure handling |

## 12. Interpretation

The result is closest to Pattern A: relaxed/flat increase ActionFrame rows and action mass while preserving boundary safety. Because world outcome checks in this matrix did not show boundary/write failures or zero flat ActionFrames, the evidence points toward over-conservative intermediate thinning. Longer outcome stress is still recommended before moving behavior out of the intermediate layer.

## 13. Recommendation

Recommendation: additional validation plus a design proposal to slightly relax intermediate conservatism and move remaining discretionary conservatism toward the upper-pressure layer and/or ActionModule actuation policy. Do not change production defaults yet. Next work should focus on longer world-outcome safety and a separate no-delay guarded-unlock comparison.

## 14. Conclusion

Phase 2F-1b provides an ablation-only, default-preserving comparison. `current` remains the default. `relaxed` and `flat` show that relation-unlock pressure thinning is materially improved by reducing intermediate conservatism while preserving hard safety boundaries in this validation matrix.
