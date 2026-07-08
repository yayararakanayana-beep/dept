# Task2-8j 7-axis G_t Reversible Development Policy

## Position

From this point forward, Task2-8j development uses the fixed `static_pca_7` / 7-axis `G_t` line as the main development base.

This means future Task2-8j work should treat the 7-axis `G_t` route as the primary line for:

- relation-field construction
- O_t bridge / observation-map continuation
- action-module input preparation
- non-execution action-material validation
- later reversible integration work

## Non-deletion rule

Older `G_t` routes must not be deleted as part of ordinary development.

The following legacy/reference routes should remain available unless a later explicit archival PR replaces this policy:

- 3-axis lightweight / coarse monitoring reference
- 6-axis stability baseline / fallback reference
- 8-axis reference / non-main comparison route
- older G_t-related validation artifacts needed to reproduce prior decisions

The intent is not to keep old routes as equal main candidates. The intent is to preserve reversibility, auditability, comparison ability, and rollback safety.

## Reversibility rule

Updates should be additive or clearly reversible.

Do not perform destructive migration such as:

- deleting old `G_t` code simply because 7-axis is now primary
- overwriting old outputs without a new name or explicit migration record
- removing fallback references needed to compare 7-axis behavior against older baselines
- making the 7-axis line impossible to roll back from

If a future task needs to retire an old route, do it through a separate explicit archival step, not as a side effect of unrelated feature work.

## Runtime boundary

This policy does not by itself introduce real ActionModule runtime execution.

It also does not perform:

- canonical writeback
- axis execution
- production adoption
- irreversible replacement of legacy G_t references

The current state remains a development-base freeze, not a final deployment switch.

## Practical development rule

For new Task2-8j work:

1. Start from the 7-axis `G_t` base.
2. Keep old G_t routes available as references/fallbacks.
3. Add migration or bridge code rather than deleting legacy paths.
4. Preserve enough metadata to reconstruct which G_t route produced which downstream artifact.
5. Treat any destructive cleanup as a dedicated, reviewable, reversible PR.

## Summary

Main development base:

```text
7-axis G_t / static_pca_7
```

Legacy routes:

```text
preserved, not main, not deleted
```

Update style:

```text
reversible, additive, auditable
```
