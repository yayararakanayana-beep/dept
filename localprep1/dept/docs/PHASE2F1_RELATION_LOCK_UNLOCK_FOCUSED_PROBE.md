# Phase 2F-1 Relation Lock / Unlock Focused Probe

## 1. Scope

Phase 2F-1 is an observation-only focused probe for relation-lock / unlock behavior. The purpose is not to fix or retune runner behavior; it is to separate likely causes for ActionFrame thinning that remained as medium hole candidates after the Phase 2E integrated pack and Phase 2E summary.

The probe is limited to relation-lock / unlock conditions and asks whether thinning is primarily associated with gate dampening, low projection rows, pressure / parameter / binding source behavior, relation_unlock action suppression, or normal safety suppression under relation-lock state.

No implementation behavior was changed. This task adds one matrix and this report only:

- `localprep1/dept/configs/matrices/matrix_phase2f1_relation_lock_unlock_focused_probe.json`
- `localprep1/dept/docs/PHASE2F1_RELATION_LOCK_UNLOCK_FOCUSED_PROBE.md`

Runner code, ActionExecutionModule code, ActionFrame generation, gate decisions, action strength calculation, ActionModule boundaries, acceptance conditions, existing matrices, existing profiles, and profile loading remain unchanged.

## 2. Background

Phase 2E-1 established projection-zero / exploration-zero source readability as a local-probe topic. Phase 2E-1b and Phase 2E-1c then made ActionFrame provenance easier to audit, especially after PR #34 added source audit columns. The columns checked for this focused probe were:

- ActionFrame side: `action_source_category`, `planning_source`, `pressure_source`, `binding_source`, `gate_source`, `exploration_projection_source`, `exploration_channel_semantics`, `action_source_audit_contract`.
- `action_execution_audit` side: `action_source_audit_columns_present`, `action_source_category_values`, `exploration_channel_semantics_values`.

Phase 2E Integrated Small-Loop Probe Pack / PR #39 passed overall with clean boundary/write behavior, but relation-lock / unlock rows concentrated several medium hole candidates:

- `relation_unlock_pressure_probe`: ActionFrame count 737, matrix minimum, full dampening.
- `relation_lock_default_probe`: projection rows 3 with mixed projection / no-projection source modes.
- `relation_lock_low_coupling_probe`: projection rows 3 and relation-lock source thinning.
- `kt_short_memory_relation_lock_probe`: ActionFrame count 748 with short memory x relation-lock thinning.

Phase 2E Summary / PR #41 concluded that these were not immediate boundary failures, but they warranted focused follow-up because ActionFrame count thinning was visible while boundary violations, forbidden writes, dry-run write violations, and ActionModule boundary violations remained absent.

This Phase 2F-1 probe intentionally does not deep-dive K_t short memory. That remains a Phase 2F-2 topic.

## 3. Matrix Design

Added matrix file:

- `configs/matrices/matrix_phase2f1_relation_lock_unlock_focused_probe.json`

Run count: 16.

Run categories:

| Category | Runs | Purpose |
|---|---:|---|
| Baseline再確認 | 4 | Recheck relation-lock default/buffered, relation_unlock pressure, and low-coupling focused conditions against Phase 2E symptoms. |
| Gate variation | 3 | Observe dampening prevalence under slightly higher noise without modifying gate logic. |
| Projection variation | 3 | Compare exploration-enabled, exploration-disabled, and unlock/no-exploration source readability. |
| Pressure / binding variation | 3 | Observe source categories under existing strength/action-profile variation without introducing unknown override keys. |
| Duration / coupling variation | 3 | Determine whether thinning remains bounded or recovers over 24-step relation-lock / unlock runs. |

The matrix uses only existing matrix-style keys: `seed`, `steps`, `world_profile`, `action_profile`, `validation_profile`, `exploration_enabled`, `action_coupling`, `drift_scale`, `noise_scale`, `max_action_strength`, and `strength_scale`. It does not use `kt_window`.

## 4. Validation Commands

Commands run from repository root and `localprep1/dept`:

```bash
pwd
git status --short --branch
git branch --show-current
git log --oneline -8
rg -n "action_source_category|action_source_audit_columns_present|relation_unlock_pressure_probe|relation_lock_default_probe|relation_lock_low_coupling_probe|medium hole|gate dampening|ActionFrame count" localprep1/dept/dept2_fullspec_runner_rc1/modules/action_execution_module.py localprep1/dept/docs/PHASE2E_SMALL_LOOP_AUDIT_SUMMARY.md localprep1/dept/docs/PHASE2E_INTEGRATED_SMALL_LOOP_PROBE_PACK.md
cd localprep1/dept
python -m json.tool configs/matrices/matrix_phase2f1_relation_lock_unlock_focused_probe.json > /tmp/matrix_phase2f1_relation_lock_unlock_focused_probe.validated.json
python -m compileall .
python scripts/run_smoke_validation.py
python scripts/run_matrix_validation.py --matrix configs/matrices/matrix_phase2f1_relation_lock_unlock_focused_probe.json --output-dir validation_runs/phase2f1_relation_lock_unlock_focused_probe
cat validation_runs/phase2f1_relation_lock_unlock_focused_probe/matrix_summary.json
```

## 5. Matrix Summary

| Metric | Result |
|---|---:|
| runs | 16 |
| overall_pass | true |
| boundary_violation_total | 0 |
| dry_run_write_violation_count | 0 |
| forbidden_write_count | 0 |
| projection_min | 0 |
| action_frame_min | 704 |
| action_source_audit_columns_present | true in inspected run-level `action_execution_audit.csv` rows |

The matrix summary did not include an aggregate `action_source_audit_columns_present` field, so this report inspected per-run `action_execution_audit.csv` and ActionFrame columns directly.

## 6. Run Results

| run label | ActionFrame rows | projection rows | source/category highlights | strength max/pre max | gate/dampening | boundary/write/ActionModule | rollback/commit gate | interpretation |
|---|---:|---:|---|---:|---|---|---|---|
| `relation_lock_default_focus_probe` | 836 | 3 | source `mixed_pressure_parameter_binding_and_exploration_projection:407; pressure_parameter_binding_planned:429`; pressure `pressure_intent_bundle:836`; binding `parameter_window_binding:836`; projection `none_available:429; used_by_planning:407`; semantics `exploration_injection_general_action_channel_not_projection_derived:132; exploration_injection_projection_derived_or_mixed:132; not_exploration_injection:572` | 0.0048 / 0.0096 | gate `coactivation_gate:dampen:836`; dampening `True:836` | boundary 0; dry-run false; forbidden false; direct PB false; canonical_write_performed false; G/K/O_t writeback false | rollback ready; commit gate audit rows 6; no performed write | Phase 2E low projection signature reproduced, but source audit remains readable. |
| `relation_lock_buffered_focus_probe` | 836 | 6 | source `mixed_pressure_parameter_binding_and_exploration_projection:836`; pressure `pressure_intent_bundle:836`; binding `parameter_window_binding:836`; projection `used_by_planning:836`; semantics `exploration_injection_projection_derived_or_mixed:264; not_exploration_injection:572` | 0.0048 / 0.0096 | gate `coactivation_gate:dampen:836`; dampening `True:836` | boundary 0; dry-run false; forbidden false; direct PB false; canonical_write_performed false; G/K/O_t writeback false | rollback ready; commit gate audit rows 6; no performed write | Full dampening without additional ActionFrame thinning below 836. |
| `relation_unlock_pressure_focus_probe` | 704 | 3 | source `mixed_pressure_parameter_binding_and_exploration_projection:352; pressure_parameter_binding_planned:352`; pressure `pressure_intent_bundle:704`; binding `parameter_window_binding:704`; projection `none_available:352; used_by_planning:352`; semantics `exploration_injection_general_action_channel_not_projection_derived:110; exploration_injection_projection_derived_or_mixed:88; not_exploration_injection:506` | 0.009 / 0.0096 | gate `coactivation_gate:allow:88; coactivation_gate:dampen:616`; dampening `False:88; True:616` | boundary 0; dry-run false; forbidden false; direct PB false; canonical_write_performed false; G/K/O_t writeback false | rollback ready; commit gate audit rows 6; no performed write | Matrix minimum; relation_unlock thinning reproduced below Phase 2E 737 while source remains readable. |
| `relation_lock_low_coupling_focus_probe` | 836 | 5 | source `mixed_pressure_parameter_binding_and_exploration_projection:550; pressure_parameter_binding_planned:286`; pressure `pressure_intent_bundle:836`; binding `parameter_window_binding:836`; projection `none_available:286; used_by_planning:550`; semantics `exploration_injection_general_action_channel_not_projection_derived:88; exploration_injection_projection_derived_or_mixed:176; not_exploration_injection:572` | 0.0048 / 0.0096 | gate `coactivation_gate:dampen:836`; dampening `True:836` | boundary 0; dry-run false; forbidden false; direct PB false; canonical_write_performed false; G/K/O_t writeback false | rollback ready; commit gate audit rows 6; no performed write | Low coupling does not reduce below 836 in this focused seed. |
| `relation_lock_default_gate_observation_probe` | 836 | 2 | source `mixed_pressure_parameter_binding_and_exploration_projection:286; pressure_parameter_binding_planned:550`; pressure `pressure_intent_bundle:836`; binding `parameter_window_binding:836`; projection `none_available:550; used_by_planning:286`; semantics `exploration_injection_general_action_channel_not_projection_derived:176; exploration_injection_projection_derived_or_mixed:88; not_exploration_injection:572` | 0.009 / 0.0096 | gate `coactivation_gate:allow:121; coactivation_gate:dampen:715`; dampening `False:121; True:715` | boundary 0; dry-run false; forbidden false; direct PB false; canonical_write_performed false; G/K/O_t writeback false | rollback ready; commit gate audit rows 6; no performed write | Less than full dampening but same 836 ActionFrame rows. |
| `relation_unlock_pressure_gate_observation_probe` | 748 | 6 | source `mixed_pressure_parameter_binding_and_exploration_projection:539; pressure_parameter_binding_planned:209`; pressure `pressure_intent_bundle:748`; binding `parameter_window_binding:748`; projection `none_available:209; used_by_planning:539`; semantics `exploration_injection_general_action_channel_not_projection_derived:55; exploration_injection_projection_derived_or_mixed:165; not_exploration_injection:528` | 0.009 / 0.0099 | gate `coactivation_gate:allow:88; coactivation_gate:dampen:660`; dampening `False:88; True:660` | boundary 0; dry-run false; forbidden false; direct PB false; canonical_write_performed false; G/K/O_t writeback false | rollback ready; commit gate audit rows 6; no performed write | Reproduces Phase 2E 748-like thin band under unlock pressure. |
| `relation_lock_buffered_gate_observation_probe` | 836 | 11 | source `mixed_pressure_parameter_binding_and_exploration_projection:836`; pressure `pressure_intent_bundle:836`; binding `parameter_window_binding:836`; projection `used_by_planning:836`; semantics `exploration_injection_projection_derived_or_mixed:264; not_exploration_injection:572` | 0.0048 / 0.0096 | gate `coactivation_gate:dampen:836`; dampening `True:836` | boundary 0; dry-run false; forbidden false; direct PB false; canonical_write_performed false; G/K/O_t writeback false | rollback ready; commit gate audit rows 6; no performed write | More projection rows but unchanged 836 ActionFrame count. |
| `relation_lock_exploration_enabled_probe` | 836 | 8 | source `mixed_pressure_parameter_binding_and_exploration_projection:836`; pressure `pressure_intent_bundle:836`; binding `parameter_window_binding:836`; projection `used_by_planning:836`; semantics `exploration_injection_projection_derived_or_mixed:264; not_exploration_injection:572` | 0.0048 / 0.0096 | gate `coactivation_gate:dampen:836`; dampening `True:836` | boundary 0; dry-run false; forbidden false; direct PB false; canonical_write_performed false; G/K/O_t writeback false | rollback ready; commit gate audit rows 6; no performed write | Exploration availability increases projection rows/readability but not ActionFrame count above relation-lock baseline. |
| `relation_lock_no_exploration_probe` | 836 | 0 | source `pressure_parameter_binding_planned:836`; pressure `pressure_intent_bundle:836`; binding `parameter_window_binding:836`; projection `none_available:836`; semantics `exploration_injection_general_action_channel_not_projection_derived:264; not_exploration_injection:572` | 0.009 / 0.0096 | gate `coactivation_gate:allow:121; coactivation_gate:dampen:715`; dampening `False:121; True:715` | boundary 0; dry-run false; forbidden false; direct PB false; canonical_write_performed false; G/K/O_t writeback false | rollback ready; commit gate audit rows 6; no performed write | projection rows 0 is safe/readable; no ActionFrame collapse. |
| `relation_unlock_no_exploration_probe` | 759 | 0 | source `pressure_parameter_binding_planned:759`; pressure `pressure_intent_bundle:759`; binding `parameter_window_binding:759`; projection `none_available:759`; semantics `exploration_injection_general_action_channel_not_projection_derived:220; not_exploration_injection:539` | 0.009 / 0.0099 | gate `coactivation_gate:allow:88; coactivation_gate:dampen:671`; dampening `False:88; True:671` | boundary 0; dry-run false; forbidden false; direct PB false; canonical_write_performed false; G/K/O_t writeback false | rollback ready; commit gate audit rows 6; no performed write | Unlock thinning remains, but source is pressure/binding readable despite projection 0. |
| `relation_lock_pressure_dominant_probe` | 836 | 11 | source `mixed_pressure_parameter_binding_and_exploration_projection:836`; pressure `pressure_intent_bundle:836`; binding `parameter_window_binding:836`; projection `used_by_planning:836`; semantics `exploration_injection_projection_derived_or_mixed:264; not_exploration_injection:572` | 0.0049 / 0.0099 | gate `coactivation_gate:dampen:836`; dampening `True:836` | boundary 0; dry-run false; forbidden false; direct PB false; canonical_write_performed false; G/K/O_t writeback false | rollback ready; commit gate audit rows 6; no performed write | Stronger action scaling is dampened and stays bounded. |
| `relation_lock_binding_dominant_probe` | 836 | 1 | source `mixed_pressure_parameter_binding_and_exploration_projection:143; pressure_parameter_binding_planned:693`; pressure `pressure_intent_bundle:836`; binding `parameter_window_binding:836`; projection `none_available:693; used_by_planning:143`; semantics `exploration_injection_general_action_channel_not_projection_derived:220; exploration_injection_projection_derived_or_mixed:44; not_exploration_injection:572` | 0.009 / 0.0096 | gate `coactivation_gate:allow:121; coactivation_gate:dampen:715`; dampening `False:121; True:715` | boundary 0; dry-run false; forbidden false; direct PB false; canonical_write_performed false; G/K/O_t writeback false | rollback ready; commit gate audit rows 6; no performed write | Low projection rows but readable pressure/binding source; no count collapse. |
| `relation_unlock_pressure_dominant_probe` | 726 | 1 | source `mixed_pressure_parameter_binding_and_exploration_projection:88; pressure_parameter_binding_planned:638`; pressure `pressure_intent_bundle:726`; binding `parameter_window_binding:726`; projection `none_available:638; used_by_planning:88`; semantics `exploration_injection_general_action_channel_not_projection_derived:187; exploration_injection_projection_derived_or_mixed:22; not_exploration_injection:517` | 0.0048 / 0.0096 | gate `coactivation_gate:dampen:726`; dampening `True:726` | boundary 0; dry-run false; forbidden false; direct PB false; canonical_write_performed false; G/K/O_t writeback false | rollback ready; commit gate audit rows 6; no performed write | Thin unlock pressure row with full dampening and low projection; medium follow-up. |
| `relation_lock_longer_run_probe` | 3410 | 9 | source `mixed_pressure_parameter_binding_and_exploration_projection:1144; pressure_parameter_binding_planned:2266`; pressure `pressure_intent_bundle:3410`; binding `parameter_window_binding:3410`; projection `none_available:2266; used_by_planning:1144`; semantics `exploration_injection_general_action_channel_not_projection_derived:704; exploration_injection_projection_derived_or_mixed:352; not_exploration_injection:2354` | 0.009 / 0.0101 | gate `coactivation_gate:allow:121; coactivation_gate:dampen:3289`; dampening `False:121; True:3289` | boundary 0; dry-run false; forbidden false; direct PB false; canonical_write_performed false; G/K/O_t writeback false | rollback ready; commit gate audit rows 24; no performed write | Longer run scales up rows; thinning does not worsen into collapse. |
| `relation_unlock_longer_run_probe` | 3300 | 54 | source `mixed_pressure_parameter_binding_and_exploration_projection:3300`; pressure `pressure_intent_bundle:3300`; binding `parameter_window_binding:3300`; projection `used_by_planning:3300`; semantics `exploration_injection_projection_derived_or_mixed:990; not_exploration_injection:2310` | 0.005 / 0.01 | gate `coactivation_gate:dampen:3300`; dampening `True:3300` | boundary 0; dry-run false; forbidden false; direct PB false; canonical_write_performed false; G/K/O_t writeback false | rollback ready; commit gate audit rows 24; no performed write | Longer unlock run recovers absolute rows but remains fully dampened. |
| `relation_lock_low_coupling_longer_run_probe` | 3410 | 24 | source `mixed_pressure_parameter_binding_and_exploration_projection:2145; pressure_parameter_binding_planned:1265`; pressure `pressure_intent_bundle:3410`; binding `parameter_window_binding:3410`; projection `none_available:1265; used_by_planning:2145`; semantics `exploration_injection_general_action_channel_not_projection_derived:396; exploration_injection_projection_derived_or_mixed:660; not_exploration_injection:2354` | 0.009 / 0.0103 | gate `coactivation_gate:allow:121; coactivation_gate:dampen:3289`; dampening `False:121; True:3289` | boundary 0; dry-run false; forbidden false; direct PB false; canonical_write_performed false; G/K/O_t writeback false | rollback ready; commit gate audit rows 24; no performed write | Low coupling longer run is stable; no boundary or source-readability failure. |

## 7. Focused Findings

### 7.1 ActionFrame thinning

Relation-lock baseline-style runs commonly produced 836 ActionFrame rows for 6-step runs. The thinnest relation_unlock-focused runs were:

- `relation_unlock_pressure_focus_probe`: 704 rows.
- `relation_unlock_pressure_dominant_probe`: 726 rows.
- `relation_unlock_pressure_gate_observation_probe`: 748 rows.
- `relation_unlock_no_exploration_probe`: 759 rows.

This reproduces and slightly intensifies the Phase 2E 737 / 748 thin band for relation_unlock pressure variants. Longer runs did not collapse: `relation_lock_longer_run_probe` and `relation_lock_low_coupling_longer_run_probe` reached 3410 rows, while `relation_unlock_longer_run_probe` reached 3300 rows. The longer-run result suggests bounded per-step thinning rather than progressive starvation.

### 7.2 Gate dampening

Full dampening was reproduced in several runs, including buffered relation-lock, exploration-enabled relation-lock, pressure-dominant relation-lock, relation_unlock_pressure_dominant, and relation_unlock_longer. Other runs mixed `allow` and `dampen`, but no run was dominated by `block` or `defer` in ActionFrame `gate_source`.

Dampening correlates with action strength compression: typical pre-gate maxima were about 0.0096-0.0103, while fully dampened action maxima were about 0.0048-0.0050. However, full dampening alone does not explain row count thinning because several full-dampening relation-lock runs still had 836 rows, while relation_unlock pressure variants thinned to 704-748.

### 7.3 Projection source

Projection rows ranged from 0 to 54. Projection-zero runs remained readable:

- `relation_lock_no_exploration_probe`: 836 ActionFrame rows, projection 0, `pressure_parameter_binding_planned:836`, `exploration_projection_source:none_available:836`.
- `relation_unlock_no_exploration_probe`: 759 ActionFrame rows, projection 0, `pressure_parameter_binding_planned:759`, `exploration_projection_source:none_available:759`.

Low projection rows do not by themselves cause ActionFrame collapse. Relation-lock rows with projection 1-3 still had 836 rows, while relation_unlock pressure rows with projection 1-3 were thinner. The likely difference is relation_unlock pressure semantics interacting with gate/source composition, not projection count alone.

### 7.4 Pressure / binding source

All runs retained readable `pressure_source:pressure_intent_bundle` and `binding_source:parameter_window_binding`. Neither pressure nor binding source fell to `none` in the inspected ActionFrames.

`pressure_parameter_binding_planned` remained common, especially where projection was 0 or low. Mixed source rows increased when projection was available and used by planning. This is expected source composition rather than source audit unreadability.

### 7.5 Relation unlock action semantics

The focused matrix did not expose unreadable relation_unlock source behavior. Relation_unlock pressure variants produced ActionFrames with pressure/binding-backed rows and, when projection rows existed, mixed projection-backed rows. The thinnest run (`relation_unlock_pressure_focus_probe`, 704 rows) still had readable source split: 352 mixed rows and 352 pressure/parameter/binding-planned rows.

The current classification is medium observation: relation_unlock pressure is consistently thinner than relation-lock defaults, but there is no evidence of over-suppression through missing source, block/defer dominance, ActionFrame zero rows, or ActionModule boundary violation. It looks more like bounded safety suppression plus relation_unlock pressure/gate/source interaction than an immediate bug.

### 7.6 Boundary integrity

Boundary integrity remained clean:

- `boundary_violation_total: 0`.
- `dry_run_write_violation_count: 0`.
- `forbidden_write_count: 0`.
- `direct_parameter_box_input_to_actionmodule: false` in inspected run summaries.
- `canonical_write_performed: false` in canonical write audits.
- `world_write_performed: false`, `gk_writeback_performed: false`, and `ot_writeback_performed: false` in canonical write audits.
- ActionFrame source audit columns remained readable.

Some run summaries report `canonical_write_rows` as audit-row counts under the existing runner summary convention; the actual `canonical_write_performed` field in the canonical write audit rows was false.

## 8. Hole Candidate List

| severity | run | symptom | likely source | recommended next task |
|---|---|---|---|---|
| medium | `relation_unlock_pressure_focus_probe` | ActionFrame minimum 704, below Phase 2E 737, with readable mixed + pressure/binding source | relation_unlock pressure/gate/source interaction | Phase 2F follow-up focused on relation_unlock pressure semantics before code changes |
| medium | `relation_unlock_pressure_dominant_probe` | 726 rows, projection 1, full dampening | relation_unlock pressure plus full dampening and low projection | Compare with additional relation_unlock seeds / profile-neutral observation matrix |
| medium | `relation_unlock_pressure_gate_observation_probe` | 748 rows, close to Phase 2E thin band | relation_unlock pressure/gate interaction | Keep as regression-observation candidate for Phase 2F-2/2F-3 |
| low | `relation_lock_default_focus_probe` | projection rows 3 and mixed/no-projection source modes | low projection availability under relation-lock | No fix; continue source-readability monitoring |
| low | `relation_lock_binding_dominant_probe` | projection row 1 but stable 836 ActionFrames | low projection without collapse | No fix; keep as projection-low control |
| observation_only | `relation_lock_no_exploration_probe` | projection rows 0 but source readable and 836 ActionFrames | expected no-exploration path | Preserve projection_min=0 as non-failure |
| observation_only | `relation_unlock_no_exploration_probe` | projection rows 0 with 759 rows and readable source | relation_unlock pressure/binding path without projection | Observe, not a blocker |
| observation_only | `relation_unlock_longer_run_probe` | 3300 rows and full dampening over 24 steps | bounded safety dampening | Longer-run monitoring only |

No blocker or high-severity hole was found.

## 9. Interpretation

- Relation-lock ActionFrame thinning was reproduced as a bounded pattern. Standard relation-lock 6-step runs stayed around 836 rows; relation_unlock pressure variants thinned to 704-759 rows.
- Thinning is not explained by gate dampening alone. Full dampening appears in stable 836-row runs as well as thinner relation_unlock pressure runs.
- Thinning is not explained by projection rows alone. projection 0 relation-lock retained 836 rows and readable sources; projection 1-3 relation-lock controls did not collapse.
- Pressure / binding sources remained present and readable. There is no evidence that ActionFrames are thinning because `pressure_source` or `binding_source` becomes `none`.
- Relation_unlock pressure actions are thinner, but not currently proven over-suppressed: the action source remains readable, no block/defer dominance appears, and no boundary/write violations occur.
- No immediate code fix is recommended from Phase 2F-1 alone.
- The next task should be Phase 2F-2 for K_t short memory x relation-lock, while retaining relation_unlock pressure as a medium observation candidate for a later seed/profile-focused follow-up.
- A relation-lock correction PR should not be created yet unless a later probe demonstrates ActionFrame zero rows, unreadable source audit, block/defer dominance, or boundary/write failure.

## 10. Conclusion

Phase 2F-1 confirms that relation_unlock pressure conditions are the thinnest relation-lock / unlock category, with a new local minimum of 704 ActionFrame rows. The thinning is bounded, source-auditable, and boundary-clean. The observed pattern points to a relation_unlock pressure/gate/source interaction rather than a direct ActionModule boundary violation, a projection-only failure, or a pressure/binding source disappearance.

Recommended next task: proceed to Phase 2F-2 for K_t short memory x relation-lock, and keep relation_unlock pressure as a medium follow-up candidate if later evidence suggests over-suppression or source unreadability.
