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

## Pass rule

`passed=true` is allowed only when the existing runner executes, the lower ParameterBox state and safe hook are found, the controlled case writes exactly once, rollback restores the original value, real watch-only candidates are not written, performance delta is extracted from real runner output, boundary audit is explicit rather than assumed, and all prohibited boundary counts remain zero.
