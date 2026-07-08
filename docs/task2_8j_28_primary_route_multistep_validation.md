# Task2-8j-28 Primary Route Multistep Validation

## Purpose

Task2-8j-28 validates that the Task2-8j primary ActionSurface route can remain connected over multiple FullSpec loop steps.

Task2-8j-27 proved that Task2-8j operator material can be promoted into ActionSurfacePlanning as pre-gate action candidates for one loop.  Task2-8j-28 checks that the same route stays connected across several loop steps and across more than one scenario.

## Validation configuration

The dedicated test uses:

```python
FullSpecRunnerConfig(
    steps=4,
    scenario="normal" or "relation_lock",
    gt_route="static_pca_7_smoke",
    task2_8j_bridge_enabled=True,
    action_planning_route="task2_8j_primary",
    canonical_commit_enabled=False,
    canonical_commit_dry_run=True,
    run_baseline_shadow=False,
)
```

## What is checked

For each step, the test checks that:

- static_pca_7 G_t view remains attached
- Task2-8j bridge stays `pass`
- Task2-8j-24 operator material is available
- ActionSurfacePlanning uses `action_planning_route=task2_8j_primary`
- Task2-8j material is promoted to action candidates
- Task2-8j primary candidates are present in every step
- local observation needs include Task2-8j primary sources
- coactivation gate remains pre-ActionFrame and `pass`
- action execution audit remains `pass`
- pseudo-world time advances by exactly one step each cycle

## Boundary retained

Task2-8j-28 still does not:

- delete legacy G_t
- make static_pca_7 the default route
- perform canonical writeback
- execute axes directly
- bypass local audit
- bypass coactivation gate
- pass G_t, O_t, Task2-8j tables, or parameter boxes directly to ActionModule

The ActionModule still receives only ActionFrame.

## Meaning of success

Passing Task2-8j-28 means the Task2-8j primary action-planning route is not just a one-step smoke connection.  It can persist across a short multi-step FullSpec loop in both a normal and a relation-lock-biased scenario.

This is still a smoke/stability validation, not a performance superiority claim.

## Next task

Task2-8j-29 should compare legacy-primary vs Task2-8j-primary multi-step behavior using matched seeds/scenarios and summarize the differences in action-candidate composition, gate decisions, world-transition deltas, and audit stability.
