# Task20j Next Evidence Request Manifest

no_write: `true`

max_files_next_extraction: `10`

## Requested Evidence

### T20J-R01-coactivation-gate-rows
- watch_item: `coactivation_dampen_zone`
- proposal_id: `T20F-P01-coactivation_dampen_zone`
- evidence_type: Task17 per-cycle coactivation gate rows with action candidate and audit correlation summaries
- preferred_format: `csv_or_json_summary`
- reason: Needed to check whether dampening aligns with visible coactivation risk before any future gate design discussion.
- do_not_extract: RC1 runtime code, bulk-expanded archive contents, full execution logs

### T20J-R02-residual-noise-ledger-rows
- watch_item: `residual_noise_high`
- proposal_id: `T20F-P02-residual_noise_high`
- evidence_type: Task17 residual/noise ledger per-cycle rows with sustained/transient classification and carryover summary
- preferred_format: `csv_or_json_summary`
- reason: Needed to distinguish sustained high noise from transient shock/noise behavior while preserving unresolved residuals.
- do_not_extract: canonical parameter updates, G/K writeback artifacts, large intermediate generated artifacts

### T20J-R03-shock-recovery-window-rows
- watch_item: `shock_recovery_window`
- proposal_id: `T20F-P03-shock_recovery_window`
- evidence_type: Task17 shock onset, peak, return-to-baseline, and recovery stability summary rows
- preferred_format: `csv_or_json_summary`
- reason: Needed to define the recovery window before considering any future guard design.
- do_not_extract: rollback gate implementation, full execution logs, runtime code

### T20J-R04-ablation-contribution-rows
- watch_item: `noise_ledger_exploration_gate_relationship`
- proposal_id: `T20F-P04-noise_ledger_exploration_gate_relationship`
- evidence_type: Task18 ablation matrix, delta vs baseline, interpretation summary, and sidecar boundary confirmation summaries
- preferred_format: `csv_or_json_summary`
- reason: Needed to decompose ledger visibility, exploration preservation, and gate modulation contributions.
- do_not_extract: exploration sidecar to ActionFrame coupling, ActionModule internal access, bulk-expanded archive contents

## Boundary Check

- canonical_write_enabled: `false`
- gk_writeback_enabled: `false`
- world_write_by_shadow_enabled: `false`
- parameter_update_implemented: `false`
- commit_gate_implemented: `false`
- rollback_gate_implemented: `false`
- action_module_reads_dept_internals: `false`
- manifest_is_controller: `false`
