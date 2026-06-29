# Task20e Commit Proposal Candidate Design

## 1. Purpose

Task20e defines a diagnostic design for future DEPT2 / H-DEPT commit proposal candidates derived from Task20b / Task20c watch evidence and Task20d interpretation. In this repository, "commit proposal" means an internal future candidate for parameter reflection or control consideration, not a Git commit.

This document does not implement a commit gate, rollback gate, parameter update, writeback path, or actuator connection.

## 2. Definition

A commit proposal candidate is a structured, no-write record that describes a possible future adjustment area, the evidence that motivated it, the expected diagnostic effect, and the guards required before it could be considered by any future gate design.

A candidate is not an approved update. It is not a controller. It cannot write to canonical parameters, G/K, world state, shadow state, or ActionModule internals.

## 3. Required Candidate Fields

Each candidate should include at least:

- `proposal_id`: Stable identifier for the candidate.
- `source_watch_item`: Watch item that motivated the candidate.
- `evidence_source`: Compact evidence path or paths.
- `affected_surface`: Observational or design surface under review.
- `proposed_adjustment_type`: Candidate classification, not an executable action.
- `expected_effect`: Diagnostic expectation to verify later.
- `risk`: Main risk if the candidate is over-interpreted.
- `reversibility`: Whether the candidate can remain reversible or observe-only.
- `required_guard`: Guard evidence required before future gate consideration.
- `no_write_status`: Must be true for Task20e / Task20f.
- `claim_scope`: Must remain diagnostic proposal only.

## 4. Candidate Design by Watch Item

### `coactivation_dampen_zone`

- Candidate type: `dampen_candidate` or `audit_required`.
- Affected surface: coactivation gate review, pre-gate action candidate summaries, and shadow/audit confirmation.
- Expected effect: clarify whether dampening is bounded to visible coactivation risk.
- Required guard: coactivation gate evidence, audit evidence, and shadow confirmation.
- Boundary note: do not perform direct Parameter Box updates and do not let ActionModule read DEPT internals.

### `residual_noise_high`

- Candidate type: `buffer_candidate` or `observe_only`.
- Affected surface: residual/noise ledger and unresolved residual preservation.
- Expected effect: preserve high residual/noise visibility for later interpretation.
- Required guard: residual/noise ledger audit rows and evidence that no canonical write occurs.
- Boundary note: do not convert residual/noise into direct parameter updates.

### `shock_recovery_window`

- Candidate type: `audit_required` or `defer`.
- Affected surface: shock recovery timing and recovery-state audit windows.
- Expected effect: separate transient recovery from sustained residual/noise elevation.
- Required guard: onset, peak, and return-to-baseline timing evidence.
- Boundary note: do not implement immediate dampening or forced rollback.

### `noise_ledger_exploration_gate_relationship`

- Candidate type: `audit_required`.
- Affected surface: residual/noise ledger, exploration projection, local audit, and coactivation gate modulation.
- Expected effect: decompose visibility, candidate preservation, and action-side modulation contributions.
- Required guard: ablation comparison evidence and sidecar boundary confirmation.
- Boundary note: do not connect exploration sidecar directly to ActionFrame.

## 5. Candidate Classification

- `observe_only`: Preserve and summarize evidence without proposing modulation.
- `dampen_candidate`: Candidate for future dampening review, not an active dampener.
- `buffer_candidate`: Candidate for future buffering or observation-window review, not a parameter write.
- `audit_required`: Candidate cannot proceed without more evidence decomposition.
- `defer`: Candidate should wait for more specific evidence before further design.

## 6. Conditions That May Allow Future Commit Gate Consideration

A candidate may be passed to a future commit gate design only if all of the following are true:

- Evidence source is explicit and small enough for review.
- Candidate remains no-write before gate review.
- Boundary checks remain false.
- Required guards are named and reviewable.
- Claim scope remains diagnostic proposal only.
- The candidate does not imply direct ActionModule access to DEPT internals.

## 7. Conditions That Must Block Future Commit Gate Consideration

A candidate must not be passed forward if it:

- Enables canonical write, G/K writeback, or world write by shadow.
- Implements real Parameter Box updates.
- Implements commit gate or rollback gate behavior.
- Treats `O_t` as formal upper-pressure input.
- Connects exploration sidecar directly to ActionFrame.
- Claims safety proof, deployment readiness, or performance superiority.
- Lacks explicit evidence source and required guard fields.

## 8. Relationship to Rollback, Shadow, and Audit

Rollback, shadow, and audit should remain evidence and guard concepts in this design. Shadow confirmation may be named as required evidence, but Task20e does not create a shadow write path. Rollback may be named as a future design concern, but Task20e does not implement rollback gate behavior. Audit remains observation-only.

## 9. Boundary Rules

Task20e does not enable canonical write, G/K writeback, world write by shadow, real parameter update, commit gate, rollback gate, `O_t` upper-pressure formalization, ActionModule internal access, or exploration sidecar to ActionFrame coupling.

## 10. Task20f No-Write Dry-Run Summary Format

Task20f should generate a compact summary with:

- task and scope fields;
- `no_write: true`;
- source path to Task20b watch audit summary;
- boundary checks all false;
- one proposal candidate for each observed watch item;
- candidate fields for source watch item, evidence source, candidate type, affected surface, expected effect, risk, reversibility, required guard, no-write status, and diagnostic-only claim scope.
