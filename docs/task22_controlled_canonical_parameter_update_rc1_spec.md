# Task22 Controlled Canonical Parameter Update RC1

## Purpose

Task22 minimally integrates a bounded canonical lower-ParameterBox update into closed-loop validation. It compares `update_off`, `controlled_update_on`, `forced_bad_update_rollback`, and `real_watch_only_candidates` while reusing the existing RC1 closed-loop runner from the frozen archive.

## Relationship to Task21

Task21 remains a no-write classifier. Task22 reads Task21 outputs to confirm that the real candidate set is still `watch_only` and therefore receives no canonical update. The canonical update path is exercised only with Task22 controlled fixtures.

## Canonical Update Scope

- The only opened boundary is an in-run canonical update to lower ParameterBox state.
- At most one canonical write is allowed per run.
- The target parameter must already exist in the ParameterBox state.
- The delta must be within `max_step_delta`.
- The validation records before, after, delta, source candidate, rollback snapshot, canonical write count, and update reason.
- Source configuration and frozen archive contents are not permanently modified.

## Prohibited Behavior

Task22 does not add G/K writeback, world direct writes, ActionModule internal DEPT reads, ActionFrame direct generation, exploration-sidecar direct coupling, hidden threshold updates, unbounded updates, Task21 classifier redesign, or Parameter Shadow Box redesign.

## Commit Conditions

A controlled fixture may commit only when it has `decision = commit_candidate`, clear target and direction, explainable expected effect, minimum evidence, weak counter-evidence, bounded update size, rollback path, nontrivial do-nothing risk, absent boundary violation, possible shadow trial, an existing target parameter, delta within `max_step_delta`, and a creatable rollback snapshot.

## Rollback Conditions

Rollback is triggered if post-update evidence worsens residual/noise, recovery, coactivation risk, boundary margin, action quality, or parameter drift beyond the Task22 tolerance. Rollback must restore the pre-update ParameterBox state and record the rollback reason and snapshot id.

## Closed-Loop Comparison Cases

- **Case A: `update_off`** — canonical updates disabled.
- **Case B: `controlled_update_on`** — a controlled commit fixture performs one bounded canonical lower-ParameterBox update when all commit conditions pass.
- **Case C: `forced_bad_update_rollback`** — a forced bad bounded update intentionally worsens metrics and must roll back.
- **Case D: `real_watch_only_candidates`** — Task21 real watch-only candidates are read but never canonically updated.

## Performance Metrics

Task22 records residual/noise, recovery time, coactivation risk, boundary margin, action quality, parameter drift, rollback count, and stability after update. Existing runner outputs are reused where present, with minimal derived metrics from those outputs when an exact metric name is not emitted.

## Completion Conditions

Task22 passes only when bounded writes and rollback behavior are observed in the controlled cases, real watch-only candidates are not updated, boundary counts stay zero, controlled update improves at least one target metric versus update-off, safety metrics are not materially worse, the forced rollback run survives, and validation reports include performance deltas.
