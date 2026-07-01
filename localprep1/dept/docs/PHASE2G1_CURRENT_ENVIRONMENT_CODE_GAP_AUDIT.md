# Phase 2G-1 Current Environment Code Gap Repair and Validation Readiness Audit

## 1. Scope

This is an audit/report PR, not a repair-implementation PR. It adds one small validation-readiness matrix and this audit report only.

No production runner behavior, gate logic, ActionModule behavior, acceptance logic, safety boundary, canonical-write path, dry-run write path, or v2 integration behavior is changed.

The purpose is to confirm whether the current FullSpec runner environment is trustworthy enough for the next v2 validation step after the Phase 2F-1e relaxed-default change.

## 2. Background

Phase 2F-1b introduced `intermediate_conservatism_mode` values `current`, `relaxed`, and `flat` for comparison. Phase 2F-1c and Phase 2F-1d evaluated `relaxed` as a default candidate. Phase 2F-1e changed the `FullSpecRunnerConfig.intermediate_conservatism_mode` default from `current` to `relaxed`.

For ongoing validation:

- `relaxed` is the default mode.
- `current` remains available as an explicit baseline.
- `flat` remains available as an upper-comparison validation mode.
- v2 validation should not proceed if mode selection, boundary/write audit visibility, ActionModule boundary evidence, or summary readability has blocker/high gaps.

## 3. Audit Questions

- Does unspecified/default configuration resolve to `relaxed`?
- Do explicit `current`, `relaxed`, and `flat` runs still execute?
- Does smoke validation pass?
- Does the small readiness matrix pass?
- Are boundary/write audit fields readable in summary or per-run metrics?
- Is ActionModule boundary evidence readable?
- Is `action_source_audit_columns_present` stable?
- Is intentional `projection_min = 0` for no-exploration runs treated as observation-only rather than failure?
- Does `matrix_summary.json` contain the minimum fields needed for v2 pre-validation review?
- Are there blocker/high holes before v2 integration?

## 4. Validation Commands

Executed from `localprep1/dept`:

```bash
python -m json.tool configs/matrices/matrix_phase2g1_current_environment_readiness_audit.json > /tmp/matrix_phase2g1_current_environment_readiness_audit.validated.json
python -m compileall .
python scripts/run_smoke_validation.py
python scripts/run_matrix_validation.py --matrix configs/matrices/matrix_phase2g1_current_environment_readiness_audit.json --output-dir validation_runs/phase2g1_current_environment_readiness_audit
cat validation_runs/phase2g1_current_environment_readiness_audit/matrix_summary.json
```

Cleanup after collecting audit evidence:

```bash
rm -rf validation_runs
find . -type d \( -name "__pycache__" -o -name "pycache" \) -prune -exec rm -rf {} +
git status --short
```

## 5. Matrix Design

Matrix file: `configs/matrices/matrix_phase2g1_current_environment_readiness_audit.json`

Design:

- Runs: 10
- Steps: 3 for mode smoke/no-exploration runs, 4 for relation-unlock pressure smoke
- Seeds: 101 and 202 for the default/current/relaxed/flat smoke groups
- Required mode coverage:
  - `default_unspecified_smoke`: no `intermediate_conservatism_mode` override
  - `explicit_current_smoke`: `intermediate_conservatism_mode = current`
  - `explicit_relaxed_smoke`: `intermediate_conservatism_mode = relaxed`
  - `explicit_flat_smoke`: `intermediate_conservatism_mode = flat`
- Additional audit coverage:
  - `no_exploration_projection_zero_check`: `exploration_enabled = false`
  - `relation_unlock_pressure_smoke`: relation-lock world with conservative action profile

## 6. Matrix Summary

| runs | overall_pass | boundary_violation_total | dry_run_write_violation_count | forbidden_write_count | projection_min | action_frame_min | action_source_audit_columns_present |
| ---: | :---: | ---: | ---: | ---: | ---: | ---: | :---: |
| 10 | true | 0 | 0 | 0 | 0 | 407 | true |

The `projection_min = 0` row came from the intentional no-exploration check. The matrix still passed because ActionFrame rows remained non-zero and acceptance does not require projection rows when exploration is intentionally disabled.

## 7. Default and Explicit Mode Findings

Result: pass.

| condition | observed mode | observed gate threshold mode | observed channel gain mode | finding |
| --- | --- | --- | --- | --- |
| default unspecified seed 101 | relaxed | relaxed_dampen_less_often | relaxed_relation_unlock_neutralized | default resolved to relaxed |
| default unspecified seed 202 | relaxed | relaxed_dampen_less_often | relaxed_relation_unlock_neutralized | default resolved to relaxed |
| explicit current seed 101 | current | current | current | explicit current works |
| explicit current seed 202 | current | current | current | explicit current works |
| explicit relaxed seed 101 | relaxed | relaxed_dampen_less_often | relaxed_relation_unlock_neutralized | explicit relaxed works |
| explicit relaxed seed 202 | relaxed | relaxed_dampen_less_often | relaxed_relation_unlock_neutralized | explicit relaxed works |
| explicit flat seed 101 | flat | flat_dampen_as_allow_hard_defer_block_preserved | flat_all_one | explicit flat works |
| explicit flat seed 202 | flat | flat_dampen_as_allow_hard_defer_block_preserved | flat_all_one | explicit flat works |

`current`, `relaxed`, and `flat` remain usable for future comparison. `current` should be treated as explicit baseline. `flat` should remain a validation upper-comparison mode, not a production default.

## 8. Boundary and Write Audit Findings

Result: pass for blocker/high criteria.

- `boundary_violation_total = 0`.
- `dry_run_write_violation_count = 0`.
- `forbidden_write_count = 0`.
- Per-run `direct_parameter_box_input_to_actionmodule = false` for all runs.
- Per-run canonical write rows were 0.
- World-transition audit headers expose `gk_writeback_performed`, `ot_writeback_performed`, and `canonical_parameter_write_performed`.
- ActionFrame headers expose builder-side writeback fields including `world_write_performed_by_builder`, `gk_writeback_performed_by_builder`, and `canonical_parameter_write`.
- Action execution audit headers expose `canonical_parameter_write_performed`, `gk_writeback_performed`, and `ot_writeback_performed`.

No canonical write, dry-run write, forbidden write, direct ParameterBox input to ActionModule, G/K writeback, or O_t writeback was detected in this matrix.

## 9. ActionModule Boundary and Action Source Findings

Result: pass for blocker/high criteria.

- The ActionModule boundary audit is readable through per-run `action_execution_audit.csv`.
- `actionmodule_input_contract` and `actionmodule_received_actionframe_only` are present in `action_execution_audit.csv`.
- `direct_gk_input_to_actionmodule`, `direct_ot_input_to_actionmodule`, `direct_v8_input_to_actionmodule`, `direct_exploration_sidecar_input_to_actionmodule`, and `direct_parameter_box_input_to_actionmodule` are present in `action_execution_audit.csv`.
- `action_source_audit_columns_present = true` in every run and in aggregate `matrix_summary.json`.
- ActionFrame source columns are readable, including `action_channel`, `action_strength`, `action_source_category`, `planning_source`, `pressure_source`, `binding_source`, `gate_source`, and `exploration_projection_source`.
- No mode-specific audit format drift was observed across `current`, `relaxed`, and `flat` smoke runs.

## 10. Projection Zero / No-Exploration Findings

Result: observation-only.

The no-exploration run intentionally produced `projection_rows = 0`, which drove aggregate `projection_min = 0`. This did not cause a failed matrix because `action_frame_rows` remained non-zero; the no-exploration run had 407 ActionFrame rows. This is consistent with prior Phase 2E/2F documentation: no-exploration projection zeros are expected and should not be treated as failures when ActionFrame evidence remains present.

## 11. V2 Readiness Findings

Current runner connection points appear sufficient for the next audit/readiness step, with some export-readability improvements recommended before heavier v2 evidence review.

Readable now:

- `world_trace_before`: internal artifact used by runner action execution and transition audit.
- `world_trace_after`: internal artifact used by runner action execution and transition audit.
- `world_transition_audit`: exported by matrix validation.
- `action_frame`: exported by matrix validation.
- `action_execution_audit`: exported by matrix validation.
- `action_result`: present as a cycle artifact and populated from ActionModule sequence events.
- `boundary_guard_audit`: present as a cycle artifact.
- `cycle_audit_row`: present as a cycle artifact.

Export/readability caveat:

- `action_result`, `boundary_guard_audit`, and `cycle_audit_row` are present in runner artifacts but are not currently listed in `scripts/run_matrix_validation.py` per-run CSV exports. This is not a blocker for the current matrix because boundary/write and ActionModule evidence are available through exported summary metrics, `boundary_violation_report`, `action_frame`, `action_execution_audit`, and `world_transition_audit`. It is a medium next-task candidate if v2 review needs these exact artifacts as first-class CSV exports.

## 12. Hole Candidate List

| severity | condition | symptom | likely source | recommended next task |
| --- | --- | --- | --- | --- |
| medium | v2 artifact export readability | `action_result`, `boundary_guard_audit`, and `cycle_audit_row` are runner artifacts but are not included in matrix per-run CSV exports | `scripts/run_matrix_validation.py` `PER_RUN_EXPORTS` list | Add an audit-only export/readability task before heavier v2 evidence review, without changing runner behavior |
| observation_only | no-exploration projection-zero check | `projection_min = 0` with `overall_pass = true` and `action_frame_min = 407` | intentional `exploration_enabled = false` matrix condition | Keep documenting projection-zero as expected when ActionFrame rows are non-zero |
| observation_only | flat mode role | explicit `flat` works and uses `flat_all_one` channel gain mode | validation comparison mode | Keep `flat` as upper-comparison validation mode only |
| observation_only | current mode role | explicit `current` works and uses `current` threshold/gain modes | explicit baseline path | Keep `current` as explicit baseline only |

No blocker holes were found. No high holes were found.

## 13. Recommendation

Recommendation: **v2前提固定へ進んでよい**.

A lightweight audit-export follow-up is recommended before a larger v2 evidence campaign if reviewers want `action_result`, `boundary_guard_audit`, and `cycle_audit_row` emitted as first-class per-run CSV files. That follow-up should remain audit-only and must not alter runner behavior.

## 14. Conclusion

The Phase 2G-1 readiness audit found that the current environment is usable as a validation base after the relaxed-default change:

- Unspecified mode resolves to `relaxed`.
- Explicit `current`, `relaxed`, and `flat` modes execute and remain distinguishable.
- Smoke validation passed.
- The new readiness matrix passed.
- Boundary/write totals stayed clean.
- ActionModule boundary and action-source audit columns are readable.
- Intentional no-exploration `projection_min = 0` is not misclassified as a failure.
- No blocker/high holes were identified before v2 validation.

Recommended next task: add an audit-export/readability enhancement for `action_result`, `boundary_guard_audit`, and `cycle_audit_row` if those exact artifacts are needed as CSV evidence in the next v2 validation PR.
