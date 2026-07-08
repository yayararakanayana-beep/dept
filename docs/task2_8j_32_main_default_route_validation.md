# Task2-8j-32 Main Default Route Validation

## Purpose

Task2-8j-32 validates the post-Task2-8j-31 main default FullSpec route.

The point is to confirm that the default `FullSpecRunnerConfig()` now runs the Task2-8j-primary route without explicitly passing route settings in each test.

## What is validated

The validation relies on the default configuration for route selection:

```python
FullSpecRunnerConfig(
    steps=..., 
    scenario=..., 
    canonical_commit_enabled=False,
    canonical_commit_dry_run=True,
    run_baseline_shadow=False,
)
```

The default route is expected to be:

```text
gt_route="static_pca_7_smoke"
task2_8j_bridge_enabled=True
action_planning_route="task2_8j_primary"
```

## Runs

Task2-8j-32 checks:

```text
default_smoke:
  normal, 1 step

default_multistep:
  normal, 4 steps
  relation_lock, 4 steps
```

## Required pass conditions

Each run must show:

- static_pca_7 G_t is attached
- legacy G_t columns are preserved
- Task2-8j bridge passes
- ActionSurfacePlanning route is `task2_8j_primary`
- Task2-8j material is promoted to action candidates
- Task2-8j primary candidates exist
- Task2-8j local-observation needs exist
- coactivation gate passes
- action execution audit passes
- ActionModule receives ActionFrame only
- no direct G/K input to ActionModule
- no direct O_t input to ActionModule
- no direct ParameterBox input to ActionModule
- no canonical writeback
- world transition time advances correctly

## Boundary retained

Task2-8j-32 does not:

- change runtime defaults
- delete legacy route
- delete legacy G_t
- enable canonical writeback
- enable axis execution
- claim superiority

It only validates the main default route that was introduced in Task2-8j-31.

## Meaning of success

Passing Task2-8j-32 means the current main-default FullSpec route is validated for smoke and short multi-step execution.

The natural next task is broader stress validation of the default route.
