# Phase 2F-1c Relaxed / Flat Long-Run Outcome Validation

## 1. Scope

This validation adds a default-preserving long-run comparison matrix for `intermediate_conservatism_mode` values `current`, `relaxed`, and `flat`.

- Purpose: check whether the Phase 2F-1b `relaxed` and `flat` modes remain boundary-safe and outcome-safe beyond the short comparison runs.
- `current` remains the baseline and the unspecified default.
- This is not a default-change PR.
- The evidence is intended only as decision support for whether `relaxed` can later be considered as a new default.
- `flat` is not a default candidate; it is an upper-bound and risk-comparison mode.

## 2. Background

Phase 2F-1b showed that reducing distributed intermediate conservatism improved relation-unlock ActionFrame thinning and increased action mass while preserving hard boundary checks. Representative Phase 2F-1b row results were:

- `relation_unlock_pressure`: `current` 704 rows, `relaxed` 836 rows, `flat` 836 rows.
- `relation_unlock_pressure_dominant`: `current` 726 rows, `relaxed` 836 rows, `flat` 836 rows.
- `relation_unlock_gate`: `current` 748 rows, `relaxed` 836 rows, `flat` 836 rows.
- `relation_unlock_no_exploration`: `current` 759 rows, `relaxed` 836 rows, `flat` 836 rows.

Phase 2F-1b was mostly short/mid-range. Phase 2F-1c therefore checks whether longer runs introduce uncertainty, volatility, coupling, relation-lock, reversibility, m-overall, boundary, write, or ActionModule-side regressions.

## 3. Default Decision Question

**Can relaxed become the new default intermediate conservatism mode?**

In Japanese: **relaxedを新しいdefaultにしてよいか？**

This report does not change the default. `flat` is explicitly treated as an upper-bound comparison and safety-risk probe, not as a default candidate.

## 4. Matrix Design

- Matrix: `configs/matrices/matrix_phase2f1c_relaxed_flat_long_run_outcome_validation.json`.
- Run count: 24.
- Steps: 12 per run.
- Seeds: 2 seeds (`101`, `202`).
- Groups:
  - `relation_unlock_pressure`
  - `relation_unlock_pressure_dominant`
  - `relation_unlock_no_exploration`
  - `relation_lock_default_control`
- Comparison method: each group uses the same scenario/profile/seed/steps and varies only `intermediate_conservatism_mode` across `current`, `relaxed`, and `flat`.
- Runtime note: an initial 36-run, 24-step local attempt exceeded local runtime limits, so this committed matrix uses 24 runs at 12 steps. This remains longer than the Phase 2F-1b 6-step probes while keeping the validation runnable in the current environment.

## 5. Validation Commands

```bash
cd localprep1/dept
python -m json.tool configs/matrices/matrix_phase2f1c_relaxed_flat_long_run_outcome_validation.json > /tmp/matrix_phase2f1c_relaxed_flat_long_run_outcome_validation.validated.json
python -m compileall .
python scripts/run_smoke_validation.py
python scripts/run_matrix_validation.py --matrix configs/matrices/matrix_phase2f1c_relaxed_flat_long_run_outcome_validation.json --output-dir validation_runs/phase2f1c_relaxed_flat_long_run_outcome_validation
cat validation_runs/phase2f1c_relaxed_flat_long_run_outcome_validation/matrix_summary.json
```

## 6. Matrix Summary

| runs | overall_pass | boundary_violation_total | dry_run_write_violation_count | forbidden_write_count | projection_min | action_frame_min | action_source_audit_columns_present |
|---:|---|---:|---:|---:|---:|---:|---|
| 24 | true | 0 | 0 | 0 | 0 | 1606 | true |

`projection_min` is 0 because the no-exploration group intentionally disables exploration. The action source/audit path remained readable through the exported ActionFrame and execution audit files.

## 7. Long-Run Mode Comparison

Values are averages across the two seeds in each group.

| group | seed count | steps | current rows | relaxed rows | flat rows | current action_mass | relaxed action_mass | flat action_mass | current world outcome | relaxed world outcome | flat world outcome | boundary status | interpretation |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|---|---|---|
| relation_unlock_pressure | 2 | 12 | 1606 | 1694 | 1694 | 7.285 | 12.257 | 15.160 | uncertainty +0.00039, volatility +0.00091, coupling +0.00621 | uncertainty +0.00030, volatility +0.00089, coupling +0.00610 | uncertainty +0.00024, volatility +0.00087, coupling +0.00602 | clean | `relaxed` improves rows and mass without worse world deltas; `flat` adds more mass. |
| relation_unlock_pressure_dominant | 2 | 12 | 1606 | 1694 | 1694 | 7.285 | 12.257 | 15.160 | uncertainty +0.00039, volatility +0.00091, coupling +0.00621 | uncertainty +0.00030, volatility +0.00089, coupling +0.00610 | uncertainty +0.00024, volatility +0.00087, coupling +0.00602 | clean | same stable improvement pattern as pressure run. |
| relation_unlock_no_exploration | 2 | 12 | 1606 | 1694 | 1694 | 7.285 | 14.852 | 15.160 | uncertainty +0.00039, volatility +0.00091, coupling +0.00621 | uncertainty +0.00025, volatility +0.00087, coupling +0.00603 | uncertainty +0.00024, volatility +0.00087, coupling +0.00602 | clean | improvement persists without exploration. |
| relation_lock_default_control | 2 | 12 | 1694 | 1694 | 1694 | 7.605 | 12.415 | 15.332 | uncertainty +0.00031, volatility +0.00089, coupling +0.00612 | uncertainty +0.00018, volatility +0.00085, coupling +0.00595 | uncertainty +0.00010, volatility +0.00083, coupling +0.00583 | clean | rows already saturated; mass increases, no boundary or world-delta regression observed. |

## 8. Relation Unlock Outcome Findings

- `relaxed` improved relation-unlock pressure thinning in all pressure-family groups from 1606 average rows to 1694 average rows.
- `relaxed` did not zero out ActionFrames and did not show mid-run collapse in the exported row totals.
- `flat` matched the row count of `relaxed` but raised total action mass further, making it useful as an upper-bound comparison rather than a default candidate.
- `guarded_relation_unlock_action_mass` increased from 0.797 in `current` to 1.655 in `relaxed` and 2.276 in `flat` for the pressure-family groups.
- `relation_unlock_family_action_mass` increased from 2.081 in `current` to 3.694 in `relaxed` and 4.762 in `flat` for the pressure and pressure-dominant groups.
- `relation_unlock_no_exploration` showed stronger `relaxed` relation-unlock family mass (4.485) while remaining boundary clean.

## 9. World Outcome Safety Findings

The exported world transition audit provides per-step mean deltas rather than absolute outcome means for this matrix. Within those available columns:

- `uncertainty`: `relaxed` was not worse than `current` in any group; pressure-family averages moved from +0.00039 to +0.00030.
- `volatility`: `relaxed` was slightly lower than `current` in every group.
- `coupling`: `relaxed` was slightly lower than `current` in every group.
- `relation_lock`: `relaxed` remained close to `current`; no structural over-unlock symptom was observed in this 12-step validation.
- `reversibility`: `relaxed` remained close to `current`; no reversal snapback or uncertainty explosion was observed.
- `entropy` and `exploration`: deltas remained close to `current`, with no boundary or source-readability failure.
- `m_overall`: no direct `m_overall` column was exported by the current runner summary, so this report does not claim a measured `m_overall` result.

## 10. Boundary Safety Findings

Across all 24 runs:

- `boundary_violation_total`: 0.
- `dry_run_write_violation_count`: 0.
- `forbidden_write_count`: 0.
- `direct_parameter_box_input_to_actionmodule`: false in per-run metrics.
- `canonical_write_performed`: 0 rows.
- `world_write_performed_by_builder`: no forbidden write detected.
- `gk_writeback_performed`: no forbidden write detected.
- `ot_writeback_performed`: no forbidden write detected.
- ActionModule input remained ActionFrame-only under the existing execution audit contract.

## 11. Default Candidate Assessment

Assessment: **provisional default candidate**.

Reasons:

- `relaxed` preserved boundary/write safety in all 24 committed runs.
- `relaxed` improved pressure-family rows from 1606 to 1694 and increased action mass without zero ActionFrames.
- `relaxed` did not worsen the available uncertainty, volatility, or coupling deltas relative to `current`.
- `relaxed` did not show obvious relation-lock over-release or flat-style action excess in this matrix.
- However, this matrix was reduced to 12 steps because 24-step local validation exceeded runtime limits, and `m_overall` is not directly exported. A longer or more efficient stress run is still needed before a default-change PR.

## 12. Hole Candidate List

| severity | condition | symptom | likely source | recommended next task |
|---|---|---|---|---|
| medium | 24-step validation exceeded local runtime limits | committed matrix uses 12-step runs | runner/matrix runtime cost | add a lighter aggregate runner or staged 24-step subset before default change |
| medium | no direct `m_overall` export in current matrix summary | world outcome assessment relies on mean-delta columns | existing summary/export schema | add summary-only `m_overall` export if the runner already computes it |
| low | `flat` increases action mass substantially | rows match `relaxed` but mass is higher | flat removes most discretionary intermediate conservatism | keep `flat` as upper-bound/stress mode only |
| observation_only | no-exploration projection rows are zero | `projection_min` is 0 but acceptance still passes | intentional matrix override | continue documenting projection-zero as expected for no-exploration runs |

## 13. Recommendation

- Keep the default as `current` for now.
- Proceed toward preparation for a possible `relaxed` default change only after an additional longer stress validation or a runtime-improved 24/48-step matrix.
- Keep `flat` only as a validation upper-bound/risk probe.
- Do not move intermediate conservatism into production defaults in this PR.
- If future stress tests show uncertainty/volatility/coupling regressions, investigate moving conservatism to the ActionModule/actuation side instead of weakening safety boundaries.

## 14. Conclusion

The result is closest to **Pattern A with a runtime caveat**: `relaxed` improves rows/action mass, remains boundary-safe, and does not worsen the available world outcome deltas in this longer-than-Phase-2F-1b validation. Because the committed matrix uses 12-step runs after 24-step validation exceeded local runtime limits, `relaxed` should be treated as a **provisional default candidate**, not as ready for an immediate default change. The next task should run a more efficient 24/48-step stress comparison or add summary-only outcome exports before proposing any default change.
