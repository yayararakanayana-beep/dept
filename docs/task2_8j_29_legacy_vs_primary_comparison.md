# Task2-8j-29 Legacy vs Task2-8j Primary Multistep Comparison

## Purpose

Task2-8j-29 compares two FullSpec multi-step routes under matched seeds and scenarios:

```text
legacy
  existing repaired-policy ActionSurfacePlanning route

task2_8j_primary
  Task2-8j operator material promoted into ActionSurfacePlanning as primary candidate source
```

This task is diagnostic. It does not claim that one route is superior. It checks that both routes can run under matched conditions and that the difference is visible in explicit comparison tables.

## Configuration

Each route is run with:

```python
FullSpecRunnerConfig(
    steps=4,
    seed=42,
    scenario="normal" or "relation_lock",
    gt_route="static_pca_7_smoke",
    canonical_commit_enabled=False,
    canonical_commit_dry_run=True,
    run_baseline_shadow=False,
)
```

The route-specific settings are:

```python
# legacy
task2_8j_bridge_enabled=False
action_planning_route="legacy"

# task2_8j_primary
task2_8j_bridge_enabled=True
action_planning_route="task2_8j_primary"
```

## Output tables

The validation produces:

```text
task2_8j_29_summary
task2_8j_29_per_step_metrics
task2_8j_29_route_delta
```

The workflow also writes CSV/JSON artifacts under:

```text
results/task2_8j_29_legacy_vs_primary_multistep_comparison/
```

## What is compared

For each scenario and loop step, the comparison records:

- action candidate row count
- Task2-8j primary candidate count
- legacy fallback candidate count
- action channel set
- semantic effect set
- total action strength
- local observation need rows
- coactivation gate decision
- coactivation risk score
- action execution audit status
- ActionFrame-only boundary status
- world transition time consistency
- mean state deltas for activity, volatility, uncertainty, relation_lock, coupling, exploration, reversibility, and entropy

## Boundary retained

Task2-8j-29 still does not:

- delete legacy G_t
- make static_pca_7 the default route
- perform canonical writeback
- execute axes directly
- bypass local audit
- bypass coactivation gate
- pass G_t, O_t, Task2-8j tables, or parameter boxes directly to ActionModule

The ActionModule still receives only ActionFrame.

## Meaning of success

Passing Task2-8j-29 means:

- both routes run for the same scenario/seed/step count
- both routes preserve the ActionFrame-only action boundary
- Task2-8j-primary actually produces Task2-8j-derived candidates
- comparison tables are generated and can be inspected

This is a comparison-readiness task, not a superiority claim.

## Next task

Task2-8j-30 should use the comparison outputs to decide whether Task2-8j-primary can be promoted from explicit route to the default candidate route, while keeping legacy as fallback.
