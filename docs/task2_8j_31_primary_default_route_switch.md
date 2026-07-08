# Task2-8j-31 Primary Default Route Switch

## Purpose

Task2-8j-31 switches the FullSpec default candidate route to the Task2-8j primary route.

This is the follow-up to Task2-8j-30, where the readiness decision was `eligible_for_default_candidate_route_trial`.

## Default after this task

`FullSpecRunnerConfig()` now defaults to:

```python
gt_route="static_pca_7_smoke"
task2_8j_bridge_enabled=True
action_planning_route="task2_8j_primary"
```

This means the ordinary FullSpec configuration now uses:

```text
static_pca_7 G_t
  -> Task2-8j bridge material
  -> Task2-8j primary ActionSurfacePlanning
  -> local audit
  -> coactivation gate
  -> ActionFrame
  -> ActionModule
```

## Legacy fallback retained

The legacy route remains available by explicit override:

```python
FullSpecRunnerConfig(
    gt_route="legacy",
    task2_8j_bridge_enabled=False,
    action_planning_route="legacy",
)
```

The legacy G_t route is not deleted.

## Boundary retained

Task2-8j-31 does not:

- delete legacy G_t
- delete the legacy repaired-policy route
- enable canonical writeback
- enable axis execution
- bypass local audit
- bypass coactivation gate
- pass G_t, O_t, Task2-8j tables, or parameter boxes directly to ActionModule

The ActionModule still receives only ActionFrame.

## Validation

The dedicated test checks both:

1. Default `FullSpecRunnerConfig()` uses Task2-8j-primary route and produces Task2-8j-derived candidates.
2. Explicit legacy override still works and produces legacy repaired-policy candidates.

## Meaning of success

Passing Task2-8j-31 means the project has moved from:

```text
Task2-8j-primary as explicit experimental route
```

to:

```text
Task2-8j-primary as FullSpec default candidate route
```

while still preserving legacy fallback.
