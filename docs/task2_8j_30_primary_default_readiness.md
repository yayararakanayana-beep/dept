# Task2-8j-30 Primary Default Readiness

## Purpose

Task2-8j-30 decides whether `task2_8j_primary` is ready to be promoted from an explicit route to the next default-candidate ActionSurface route.

This task does **not** change the runtime default.  It produces a conservative readiness decision based on the Task2-8j-29 legacy-vs-primary comparison.

## Decision output

The validation produces:

```text
task2_8j_30_decision
task2_8j_30_promotion_gates
task2_8j_29_summary
task2_8j_29_route_delta
```

The workflow also writes CSV/JSON artifacts under:

```text
results/task2_8j_30_primary_default_readiness/
```

## Decision values

The decision is one of:

```text
eligible_for_default_candidate_route_trial
not_ready_for_default_candidate_route_trial
```

The first value means the route is eligible for a follow-up task that changes the default candidate route while retaining legacy fallback.

It does not mean Task2-8j is proven superior.

## Promotion gates

Task2-8j-30 requires all gates to pass:

```text
comparison_tables_exist
all_comparison_status_pass
legacy_all_planning_pass
task2_8j_all_planning_pass
legacy_all_execution_pass
task2_8j_all_execution_pass
legacy_actionframe_only_boundary
task2_8j_actionframe_only_boundary
task2_8j_primary_candidates_present
task2_8j_primary_needs_present
transition_time_ok_both_routes
no_canonical_write
no_direct_dept_actionmodule_input
gate_risk_delta_within_watch_bound
gate_decision_change_ratio_within_watch_bound
```

## Boundary retained

Task2-8j-30 does not:

- change `FullSpecRunnerConfig.action_planning_route`
- delete the legacy route
- delete legacy G_t
- make static_pca_7 the default route
- enable canonical writeback
- enable axis execution
- bypass local audit
- bypass coactivation gate
- pass G_t, O_t, Task2-8j tables, or parameter boxes directly to ActionModule

The ActionModule still receives only ActionFrame.

## Meaning of success

Passing Task2-8j-30 means:

```text
Task2-8j-primary is eligible for a default-candidate route trial.
```

The next task may switch the default candidate route, but only with legacy fallback retained and with explicit tests proving the old route remains available.

## Next task

Task2-8j-31 should switch the default candidate route to Task2-8j-primary while preserving legacy fallback and explicit `action_planning_route="legacy"` override.
