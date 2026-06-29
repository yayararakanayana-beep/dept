# Task20b Watch Audit Design

## Purpose

Task20b is a documentation-only design step for decomposing the watch items that appeared in Task17 stress validation and Task18 ablation validation before moving toward any commit proposal or commit gate design.

The goal is to turn each `pass_with_watch` area into an explicit audit question: what was observed, which subsystem contributed to it, what evidence should be read, and what minimal validation would be needed in later PRs. Task20b does not implement validation scripts, generate results, or change runtime behavior.

## Position Relative to RC1 Freeze

`DEPT2_FullSpecIntegratedClosedLoopRunner_RC1_Freeze.zip` remains a frozen reference archive. Task20b treats RC1 as the source of prior validation claims and watch signals, but it does not expand the archive into the repository and does not import extracted code as canonical implementation.

The handoff notes identify Task17 stress / scenario validation and Task18 ablation validation as the immediate evidence sources. They also position Task20b as a safer next step before commit proposal, commit gate, rollback, or canonical update work.

## Watch Items and Review Questions

### `coactivation_dampen_zone`

Review questions:

- Which Task17 stress scenarios entered a dampen decision instead of allow or block?
- Did dampening happen only after coactivation pressure was visible to the gate?
- Did dampening prevent direct ActionFrame amplification while preserving the one-way ActionModule boundary?
- Are there cases where dampening appears too broad, hiding useful exploration or action candidates?
- Are there cases where dampening appears too narrow, allowing high-risk coactivation to proceed too strongly?

Expected evidence:

- Coactivation gate decision rows.
- Pre-gate action candidate summaries.
- Risk signal summaries used by the gate.
- Any Task17 watch annotations for dense same-step coactivation pressure.

### `residual_noise_high`

Review questions:

- Which stress cases raised high residual or high noise visibility?
- Did residual/noise entries remain observational ledger signals rather than Parameter Box writes?
- Did high residual/noise visibility influence exploration projection, ActionFrame intensity, or gate modulation indirectly?
- Did the ledger preserve unresolved residuals instead of dropping or normalizing them away?
- Did high residual/noise combine with shock recovery in a way that requires a distinct warning category?

Expected evidence:

- Residual/noise ledger rows and audit rows.
- Task17 high noise / residual growth scenario summaries.
- Task18 `no residual noise ledger signal` ablation summaries.
- Any shock-case annotations that add `residual_noise_high` as a watch.

### Shock Recovery Window

Review questions:

- How long did the system remain in a recovery state after a shock scenario?
- Which signals remained elevated during recovery: residuals, ambiguity, risk, gate dampening, or exploration projection changes?
- Did recovery remain a bounded observation window rather than a canonical update or writeback mechanism?
- Did the gate return toward baseline only after residual/noise and coactivation signals became consistent with recovery?
- Does the recovery window need separate summary fields for onset, peak, and return-to-baseline timing?

Expected evidence:

- Task17 shock recovery scenario outputs.
- Per-step residual/noise and gate decision summaries.
- Any recovery annotations that distinguish transient shock from sustained high-noise behavior.

### Noise Ledger / Exploration / Gate Contribution Relationship

Review questions:

- What changed when the residual/noise ledger signal was disabled in Task18?
- What changed when exploration, exploration bridge projection, local audit signal, or coactivation gate modulation was disabled?
- Does the evidence separate observational noise visibility from exploration candidate generation and final gate modulation?
- Does any path accidentally imply direct Parameter Box updates, G/K writeback, or ActionModule access to DEPT internals?
- Which contribution is necessary for visibility, which for candidate preservation, and which for action-side modulation?

Expected evidence:

- Task18 ablation summaries for `no exploration module`, `no residual noise ledger signal`, `no local audit signal`, `no exploration bridge projection`, and `no coactivation gate modulation`.
- Exploration projection summaries and sidecar preservation notes.
- Coactivation gate modulation differences between baseline and ablated runs.
- ActionFrame intensity summaries after gate decisions.

## Expected Existing Inputs

A future implementation PR may read selected, already-produced RC1 validation artifacts after a reviewed extraction or migration plan. The expected input categories are:

- Task17 stress / scenario validation summaries.
- Task17 per-scenario watch annotations.
- Task18 ablation validation summaries.
- Task18 ablation-effect annotations.
- Residual/noise ledger and residual/noise audit summaries.
- Coactivation gate decision summaries.
- Exploration projection and sidecar preservation summaries.
- ActionFrame intensity summaries after gate decisions.

This design does not require adding those result files to the repository in this PR.

## Expected Summary Output Shape

Task20b should eventually produce a compact human-readable summary, not a control action. A minimal shape is:

```text
Task20b Watch Audit Summary

source_inputs:
  task17_stress: <paths or identifiers reviewed>
  task18_ablation: <paths or identifiers reviewed>

watch_items:
  coactivation_dampen_zone:
    observed_in: [...]
    likely_contributors: [...]
    unresolved_questions: [...]
    recommended_next_validation: <small PR scope>

  residual_noise_high:
    observed_in: [...]
    likely_contributors: [...]
    unresolved_questions: [...]
    recommended_next_validation: <small PR scope>

  shock_recovery_window:
    observed_in: [...]
    likely_contributors: [...]
    unresolved_questions: [...]
    recommended_next_validation: <small PR scope>

  noise_ledger_exploration_gate_relationship:
    observed_in: [...]
    likely_contributors: [...]
    unresolved_questions: [...]
    recommended_next_validation: <small PR scope>

boundary_check:
  canonical_write_enabled: false
  gk_writeback_enabled: false
  parameter_update_implemented: false
  commit_gate_implemented: false
  action_module_reads_dept_internals: false
```

## Boundary Rules

Task20b is an observation and analysis design layer only. It is not a controller, gate, actuator, or parameter update path.

Rules:

- Do not enable canonical write.
- Do not implement G/K writeback.
- Do not implement real Parameter Box updates.
- Do not implement a commit gate or rollback gate.
- Do not treat `O_t` as a formal upper-pressure input.
- Do not allow ActionModule code to read DEPT internals.
- Do not connect exploration sidecar directly to ActionFrame.
- Do not add validation scripts in this design PR.
- Do not add tests or generated Task20b result files in this design PR.
- Do not commit expanded RC1 archive contents.

## Completion Criteria

Task20b design is complete when:

- The four watch areas are listed with review questions and expected evidence.
- The expected input categories from Task17 and Task18 are named without importing bulk results.
- The expected summary shape is defined.
- Boundary rules explicitly keep the work observational and non-controlling.
- Follow-up implementation is limited to small validation PRs after this design is reviewed.

## Minimal Validation Ideas for PR #4 and Later

These are proposed follow-up PR scopes only; they are not implemented here.

1. **PR #4: Static watch summary reader**
   - Read a small, reviewed subset of Task17 and Task18 summary artifacts.
   - Emit a non-authoritative Task20b summary using the shape above.
   - Include tests for parsing and summary formatting only.

2. **PR #5: Coactivation dampen audit**
   - Validate that dampen decisions correlate with visible coactivation pressure and risk signals.
   - Keep the audit read-only and prohibit gate behavior changes.

3. **PR #6: Residual/noise and shock recovery audit**
   - Separate sustained residual/noise elevation from shock recovery timing.
   - Report onset, peak, and recovery-window markers without changing runtime control.

4. **PR #7: Contribution relationship ablation audit**
   - Compare baseline and selected ablation summaries for ledger, exploration, local audit, bridge projection, and gate modulation contributions.
   - Verify that sidecar preservation and ActionFrame modulation remain separated by the documented boundaries.
