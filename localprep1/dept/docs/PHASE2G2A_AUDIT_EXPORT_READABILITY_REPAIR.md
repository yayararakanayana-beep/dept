# Phase 2G-2a Audit / Export Readability Repair

## 1. Scope

This task is an audit/export/readability repair, not a production behavior repair.

It only makes existing runner artifacts and existing per-run evidence easier to read through CSV exports, matrix summary fields, and a small readability matrix. It does not change production runner behavior, acceptance criteria, gate logic, ActionModule behavior, action policy, safety boundaries, write paths, default values, or v2 integration behavior.

## 2. Background

Phase 2G-1a found no blocker/high current-environment issues and confirmed default relaxed mode, explicit current/relaxed/flat mode paths, boundary/write audit readability, and intentional projection-zero handling. It left a medium readability gap: `action_result`, `boundary_guard_audit`, and `cycle_audit_row` existed as runner artifacts but were not first-class per-run CSV exports.

Phase 2G-1b identified intermediate-maintenance, ExplorationModule, and ParameterWindowBinder candidates for later repair probes. Before those repairs, reviewer-facing module-by-module thinning evidence needs to be visible without changing candidate generation, gate decisions, ActionFrame generation, or action execution behavior.

This repair is therefore intentionally observational: it exports and summarizes what the runner already produced.

## 3. Changes

- Added `action_result`, `boundary_guard_audit`, and `cycle_audit_row` to the per-run CSV export list.
- Added per-run observational helper CSVs:
  - `module_thinning_audit.csv`
  - `gate_decision_summary.csv`
  - `candidate_retention_summary.csv`
  - `actionframe_retention_summary.csv`
- Added matrix-level visibility fields to `matrix_summary.json`.
- Added `matrix_phase2g2a_audit_export_readability.json`, an 8-run lightweight readability matrix.
- Kept acceptance logic unchanged; the new readability fields are not commit gates and do not change pass/fail behavior.

## 4. New / Added Exports

| export | source artifact | behavior change? | purpose |
| --- | --- | :---: | --- |
| `action_result.csv` | `action_result` runner output | false | Make ActionModule result rows first-class per-run evidence. |
| `boundary_guard_audit.csv` | `boundary_guard_audit` runner output | false | Make boundary guard status and diagnostic-only write flags directly reviewable. |
| `cycle_audit_row.csv` | `cycle_audit_row` runner output | false | Make cycle-level row counts and audit rollups directly reviewable. |
| `module_thinning_audit.csv` | existing run metrics and existing audit artifacts | false | Summarize module-level row counts, action mass, gate counts, and write/boundary observations. |
| `gate_decision_summary.csv` | existing `coactivation_gate` and `action_frame` artifacts | false | Count allow/dampen/defer/block/monitor_only decisions and explicitly mark action loss as unavailable when not derivable. |
| `candidate_retention_summary.csv` | existing planning/projection/gate artifacts | false | Show available candidate/projection/gate row counts without deriving new control logic. |
| `actionframe_retention_summary.csv` | existing execution audit, ActionFrame, and action result artifacts | false | Show ActionFrame/action-result row evidence and action mass from existing artifacts. |

## 5. New / Added Summary Fields

`matrix_summary.json` now includes these readability fields:

- `action_result_export_present`
- `boundary_guard_audit_export_present`
- `cycle_audit_row_export_present`
- `module_thinning_audit_present`
- `gate_decision_summary_present`
- `candidate_retention_summary_present`
- `actionframe_retention_summary_present`
- `action_frame_min`
- `action_mass_min`
- `gate_allow_total`
- `gate_dampen_total`
- `gate_defer_total`
- `gate_block_total`
- `action_source_audit_columns_present`

Existing boundary/write fields remain present:

- `boundary_violation_total`
- `dry_run_write_violation_count`
- `forbidden_write_count`

## 6. Readability Matrix Design

Matrix file: `configs/matrices/matrix_phase2g2a_audit_export_readability.json`

Design:

- Runs: 8
- Steps: 3 for default/current/relaxed/flat/no-exploration smoke readability checks; 4 for relation-lock, high-noise, and shock readability checks.
- Seeds: 301 through 307.
- Required coverage:
  - `default_unspecified_relaxed_smoke`: no `intermediate_conservatism_mode` override, confirming the default path remains readable.
  - `explicit_current_smoke`: explicit current baseline.
  - `explicit_relaxed_smoke`: explicit relaxed path.
  - `explicit_flat_smoke`: explicit flat upper-bound comparison path.
  - `no_exploration_projection_zero_readability`: `exploration_enabled=false`, confirming ActionFrame evidence remains readable when projection rows are intentionally zero.
  - `relation_unlock_pressure_readability`: relation-lock pressure case for gate/action thinning evidence.
  - `high_noise_readability`: high-noise case for candidate/gate/action evidence.
- Optional coverage included:
  - `shock_recovery_readability`: shock profile readability case.

## 7. Validation Results

Validation was run from `localprep1/dept`.

| check | result |
| --- | :---: |
| `python -m json.tool configs/matrices/matrix_phase2g2a_audit_export_readability.json > /tmp/matrix_phase2g2a_audit_export_readability.validated.json` | pass |
| `python -m compileall .` | pass |
| `python scripts/run_smoke_validation.py` | pass |
| `python scripts/run_matrix_validation.py --matrix configs/matrices/matrix_phase2g2a_audit_export_readability.json --output-dir validation_runs/phase2g2a_audit_export_readability` | pass |

| summary field | value |
| --- | ---: |
| runs | 8 |
| overall_pass | true |
| boundary_violation_total | 0 |
| dry_run_write_violation_count | 0 |
| forbidden_write_count | 0 |
| action_result_export_present | true |
| boundary_guard_audit_export_present | true |
| cycle_audit_row_export_present | true |
| module_thinning_audit_present | true |
| action_source_audit_columns_present | true |
| action_frame_min | 407 |
| action_mass_min | 1.7661978761818378 |
| gate_allow_total | 18 |
| gate_dampen_total | 9 |
| gate_defer_total | 0 |
| gate_block_total | 0 |

## 8. Behavior Preservation Check

| behavior area | changed? |
| --- | :---: |
| gate logic changed? | false |
| ActionModule behavior changed? | false |
| acceptance changed? | false |
| safety boundary changed? | false |
| default changed? | false |
| write path changed? | false |
| v2 integration changed? | false |

## 9. Remaining Readability Gaps

| severity | missing evidence | why needed | next task |
| --- | --- | --- | --- |
| medium | Exact per-gate action loss is not available from current artifacts | Later gate decomposition work may need pre/post gate action mass by decision, but this repair only observes existing artifacts | Phase 2G-2b candidate retention / gate decomposition probe |
| low | `gate_input_rows` can be `not_available` when no existing gate artifact column directly records it | Direct pre-gate row count would simplify module thinning review | Phase 2G-2b candidate retention / gate decomposition probe |
| low | Candidate retention is summarized from existing planning/projection/gate artifacts only | A deeper decomposition may need stage-specific candidate identity joins | Phase 2G-2b intermediate conservatism repair probe or candidate retention probe |

## 10. Recommendation

Proceed to the next small repair-probe task with the new readability artifacts available. Recommended candidates:

- Phase 2G-2b intermediate conservatism repair probe.
- Phase 2G-2b candidate retention / gate decomposition probe.
- Phase 2G-2b parameter-window sweep audit.
- If the next review only needs premise-level visibility, proceed toward v2 premise freeze with the readability caveats above.

## 11. Conclusion

Phase 2G-2a makes the existing action result, boundary guard, cycle audit, and module thinning evidence directly readable without changing runner behavior. The lightweight matrix passed with zero boundary violations, zero dry-run write violations, zero forbidden writes, and all requested first-class exports present.
