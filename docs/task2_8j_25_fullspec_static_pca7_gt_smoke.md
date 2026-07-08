# Task2-8j-25 FullSpec static_pca_7 G_t Smoke Connection

## Purpose

This task checks whether the current FullSpec runner can loop with a 7-axis `G_t` route attached.

The goal is not to replace the FullSpec runner or delete the old G_t route.  The goal is to add the smallest reversible connection point and verify that the loop still runs.

## Change

A new `FullSpecRunnerConfig.gt_route` option is added.

```text
legacy
static_pca_7_smoke
```

The default remains:

```text
legacy
```

When `gt_route="static_pca_7_smoke"`, `GKBuilderModule` preserves the existing legacy G_t columns and adds a 7-axis static_pca_7 view:

```text
static_pca7_axis_1_activity_volatility
static_pca7_axis_2_uncertainty_conflict
static_pca7_axis_3_relation_lock_coupling
static_pca7_axis_4_exploration
static_pca7_axis_5_reversibility
static_pca7_axis_6_entropy_overconvergence
static_pca7_axis_7_relation_flow_curl
```

## Boundary

This is a smoke connection only.

It does not perform:

- legacy G_t deletion
- irreversible replacement
- canonical writeback
- axis execution
- real ActionModule runtime expansion
- production adoption

## Test

The dedicated smoke test runs the existing FullSpec loop for one step with:

```python
FullSpecRunnerConfig(steps=1, gt_route="static_pca_7_smoke")
```

The test checks that:

- G_t is produced
- the static_pca_7 view is attached
- legacy G_t columns are preserved
- the formal G/K packet still passes upper-pressure boundary checks
- O_t observation audit is produced
- action execution audit is produced
- no canonical writeback or axis execution is performed by this G_t route

## Interpretation

If this test passes, it means the current FullSpec runner can loop with the 7-axis G_t route attached as an additive view.

It does not yet mean that the 7-axis route is the default runtime route.

The next safe step would be to compare legacy and static_pca_7_smoke behavior side by side before changing defaults.
