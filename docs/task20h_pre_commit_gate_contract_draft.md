# Task20h Pre-Commit Gate Contract Draft

## 1. Purpose

Task20h drafts the contract a future DEPT2 / H-DEPT pre-commit gate would need before implementation. This is a design draft only and does not implement a commit gate.

## 2. Position of the Contract

The contract sits after proposal generation and evidence sufficiency review. It describes what a future gate may inspect, which outputs it may produce, and which conditions must block progress.

## 3. Candidate Gate Inputs

A future gate contract may accept the following read-only inputs:

- `proposal_summary`: proposal-only candidate records.
- `evidence_sufficiency`: sufficiency audit status for each candidate.
- `guard_readiness`: no-write guard readiness dry-run results.
- `boundary_check`: false-only boundary flags.
- `no_write` status: must be true before gate design review.
- `required_guard`: candidate-specific guard evidence.

## 4. Candidate Gate Outputs

A future gate may emit only design-stage statuses unless a later PR explicitly implements more:

- `accept_for_further_design`
- `needs_more_evidence`
- `reject_boundary_violation`
- `defer`

These outputs are not parameter updates and are not runtime controls.

## 5. Hard Blockers

Any future gate design must block candidates when any of the following are true or missing:

- `canonical_write_enabled` is true.
- `gk_writeback_enabled` is true.
- `world_write_by_shadow_enabled` is true.
- `parameter_update_implemented` is true.
- `action_module_reads_dept_internals` is true.
- `proposal_summary_is_controller` or guard readiness controller status is true.
- Evidence source is missing.
- `no_write` is false.

## 6. Items That May Be Passed to a Future Gate Design

- No-write proposal candidates with explicit evidence sources.
- Evidence sufficiency records that clearly mark insufficient gate evidence.
- Guard readiness dry-run records with `gate_ready: false` until detailed evidence exists.
- Boundary checks that are all false.

## 7. Items That Must Not Be Passed as Gate-Ready

- Candidates based only on compact summaries but claiming readiness.
- Candidates with missing evidence source.
- Candidates with `no_write_status: false`.
- Candidates implying direct canonical parameter update, G/K writeback, world write, rollback, or ActionModule internal access.
- Candidates claiming safety proof, deployment readiness, or performance superiority.

## 8. Rollback / Shadow / Audit Relationship

Rollback and shadow remain guard concepts only in this draft. Audit remains observation-only. Shadow confirmation can be requested as evidence, but this contract does not create a shadow write path. Rollback can be named as a future concern, but this contract does not implement rollback behavior.

## 9. ActionModule Boundary

A future gate must not require ActionModule to read G/K, `O_t`, Parameter Box internals, exploration sidecars, or DEPT internals. ActionModule boundaries remain one-way actuator/translator boundaries.

## 10. `O_t` / Upper Pressure Boundary

`O_t` remains a lower local observation surface. This contract does not treat `O_t` as a formal upper-pressure input and does not create any path from `O_t` to canonical parameter updates.

## 11. Future Implementation Test Conditions

A later implementation PR would need tests that confirm:

- hard blockers reject boundary violations;
- missing evidence keeps candidates out of gate-ready status;
- `no_write` false blocks progression;
- all boundary flags remain false in dry-run paths;
- ActionModule boundary assumptions are preserved;
- rollback and parameter update paths remain absent unless separately reviewed.

## 12. Explicit Non-Implementation Statement

This PR does not implement a commit gate. It does not implement rollback gate behavior, parameter updates, canonical writes, G/K writeback, world write by shadow, action connections, or runtime control.
