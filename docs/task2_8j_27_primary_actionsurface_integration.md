# Task2-8j-27 Primary ActionSurface Integration

## Purpose

Task2-8j-27 makes Task2-8j material a primary input route for ActionSurfacePlanning.

Task2-8j-26 generated Task2-8j-24 material inside the FullSpec cycle and retained it as output.  Task2-8j-27 moves one step further: ActionSurfacePlanning now receives the Task2-8j operator-selection material and translates it into pre-gate action candidates.

## Main route

The intended test configuration is:

```python
FullSpecRunnerConfig(
    steps=1,
    gt_route="static_pca_7_smoke",
    task2_8j_bridge_enabled=True,
    action_planning_route="task2_8j_primary",
)
```

With this route, Task2-8j operator material is translated into action candidates before local audit, coactivation gate, and ActionFrame construction.

## Translation

Task2-8j operator material is mapped to existing pseudo-reality action channels:

```text
relation_lock        -> coupling_relief / relation_unlock
resource_pressure    -> buffer_increase
reversibility_loss   -> relation_unlock / buffer_increase
boundary_fragile     -> buffer_increase
oscillation          -> volatility_damping
```

The mapping keeps the existing ActionFrame-only boundary.  The action module still receives only ActionFrame, not G_t, O_t, Task2-8j tables, or parameter boxes.

## Fallback

Legacy repaired-policy candidates are retained as fallback rows when `action_planning_route="task2_8j_primary"`.

This means Task2-8j is promoted to the primary source, but the old route is not deleted.

## Still not done

Task2-8j-27 does not:

- delete legacy G_t
- make static_pca_7 the default route
- perform canonical writeback
- bypass coactivation gate
- bypass local audit
- call the ActionModule directly from Task2-8j material
- pass DEPT internals directly to the ActionModule

## Success criterion

The dedicated smoke test requires:

- FullSpec loop runs for one step
- Task2-8j bridge material is generated
- ActionSurfacePlanning audit reports `action_planning_route=task2_8j_primary`
- Task2-8j material is promoted to action candidates
- local observation needs include Task2-8j primary source
- action execution boundary remains pass

## Next task

Task2-8j-28 should run multiple-step loop validation with `action_planning_route="task2_8j_primary"` and compare stability against the legacy route.
