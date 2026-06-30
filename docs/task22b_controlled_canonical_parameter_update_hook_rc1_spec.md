# Task22B Controlled Canonical ParameterBox Update Hook RC1

Task22B is the first controlled canonical lower ParameterBox update hook validation for the frozen RC1 closed-loop runner. It depends on Task22A-CI proving that the archived existing runner can execute in GitHub Actions with `requirements.txt` installed.

## Scope

The validation extracts `DEPT2_FullSpecIntegratedClosedLoopRunner_RC1_Freeze.zip` to a temporary directory, imports `dept2_fullspec_runner_rc1.runner.FullSpecIntegratedClosedLoopRunner`, instantiates the existing runner, locates `runner.parameter_shadow_box.box.state`, and applies at most one bounded in-run lower ParameterBox update through `validation/support/task22b_canonical_update_controller.py`.

## Non-goals and closed boundaries

Task22B does not redesign Parameter Shadow Box, rebuild the Task21 classifier, create a parallel runner, use synthetic metrics for primary validation, use fixed boundary zero as proof, add G/K writeback, add world direct writes, connect ActionModule internals, or directly generate ActionFrames.

## Required cases

1. `update_off`: baseline runner execution with no canonical write.
2. `controlled_update_on`: controlled commit fixture with exactly one bounded write and real runner output metric comparison.
3. `forced_bad_update_rollback`: bounded write followed by rollback to the snapshot before runner execution continues.
4. `real_watch_only_candidates`: Task21 real `watch_only` candidates are read and confirmed as non-updating.

## Runner output inventory and metric classification

The summary records every runner output table/key plus its columns and numeric columns. Numeric metric candidates are classified as:

- `valid_performance_metric`: real closed-loop performance fields whose names indicate residual, error, loss, stability, recovery, violation, unsafe, boundary, closed-loop, risk, cost, uncertainty, volatility, conflict, instability, noise, reversibility, success, or passed semantics.
- `audit_or_index_metric`: audit row, cycle, step, seed, table index, or row index fields. These are excluded from performance improvement.
- `parameter_value_metric`: theta, ParameterBox value, shadow value, or `shadow_cycle_index` fields. These are excluded from performance improvement.
- `unavailable`: numeric fields without recognizable closed-loop performance semantics.

`shadow_cycle_index`, audit/index fields, row/cycle/step indices, `theta_after`, and raw parameter values cannot satisfy Task22B performance improvement. If no valid real runner metric improves in `controlled_update_on` versus `update_off`, Task22B remains `passed=false`.

## ParameterBox identity

The summary includes `parameter_box_identity` with `located_via`, `is_runner_owned_lower_parameter_box`, `is_shadow_candidate_only`, and `canonical_update_semantics`. `canonical_update_semantics=confirmed` is required for `passed=true`.

## Pass rule

`passed=true` is allowed only when the existing runner executes, the lower ParameterBox state and safe hook are found, the controlled case writes exactly once, rollback restores the original value, real watch-only candidates are not written, performance delta is extracted from a valid real runner output metric that improves, boundary audit is explicit rather than assumed, and all prohibited boundary counts remain zero.

## Real effect and boundary regression checks

Task22B records `parameter_before`, `parameter_hook_after`, and `parameter_runner_after` separately for each case. The `runner_recomputed_or_overwrote_parameter` flag shows whether `runner.run()` changed the hooked value after the controller wrote it.

Boundary counts use `sum` and `max` aggregation, never `int(mean)`. Any non-zero boundary count, including fractional values such as `0.5`, remains non-zero. `boundary_violation_report_rows > 0` is treated as a boundary violation. If `controlled_update_on` worsens boundary counts versus `update_off`, Task22B remains `passed=false`.

If no valid real runner performance metric improves, the summary records `no_valid_metric_improved=true` and Task22B remains `passed=false`.

## Controlled commit fixture preflight

`controlled_update_on` is not fixed to `action_intensity_cap +0.04`. The validator preflights bounded deltas `+0.01`, `-0.01`, `+0.02`, `-0.02`, `+0.04`, and `-0.04` across lower ParameterBox targets and selects only a candidate whose real runner boundary violation count is zero and does not regress versus `update_off`.

Immediate performance improvement is not required for Task22B safety-hook validation. A valid real runner metric is still reported, but `passed=true` depends on safe execution: one canonical write, rollback restoration, watch-only non-update, confirmed ParameterBox identity, no boundary regression, and zero boundary violations with sum/max no-truncation counting.
