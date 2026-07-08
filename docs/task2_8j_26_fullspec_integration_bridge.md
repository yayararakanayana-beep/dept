# Task2-8j-26 FullSpec Task2-8j Integration Bridge

## Purpose

Task2-8j-26 connects the Task2-8j material chain through Task2-8j-24 into the current FullSpec runner cycle.

This is the first bridge where Task2-8j material is generated and retained inside a FullSpec loop rather than being only an isolated validation artifact.

## What is connected

When `FullSpecRunnerConfig.task2_8j_bridge_enabled=True`, the FullSpec runner now loads Task2-8j-24 terrain operator material inside the cycle after G/K, O_t, upper pressure, and pressure translation are available.

The following tables become FullSpec outputs:

```text
task2_8j_bridge_audit
task2_8j_operator_selection
task2_8j_operator_review
task2_8j_operator_checks
task2_8j_operator_summary
```

## Required mode

The intended smoke configuration is:

```python
FullSpecRunnerConfig(
    steps=1,
    gt_route="static_pca_7_smoke",
    task2_8j_bridge_enabled=True,
)
```

## Boundary retained in Task2-8j-26

This bridge does not yet replace:

- existing O_t route
- existing ActionSurfacePlanning
- existing action candidates
- existing ActionFrame construction
- canonical writeback
- axis execution

It does connect Task2-8j-24 material into the FullSpec cycle as persisted FullSpec output.

## Next task

Task2-8j-27 should feed Task2-8j material into the existing ActionSurfacePlanning module as a guarded optional input.

That is the next step toward making Task2-8j material affect action planning rather than only being produced beside it.
