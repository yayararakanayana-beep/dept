# AGENTS.md

## Repository Purpose

This repository is intended to serve as a closed-loop verification codebase for DEPT2 / H-DEPT.

At the current stage, the repository should be treated as a minimal scaffold. Do not assume that the runtime architecture, module boundaries, or verification protocol are fully implemented unless they are explicitly documented in committed files.

## General Working Rules

- Do not break existing specifications or documented behavior.
- Do not introduce large redesigns without first proposing the design and waiting for approval.
- Keep changes small, explicit, and compatible with the current scaffold stage.
- When changing implementation behavior, add or update tests that cover the change.
- If Python tests are added, use `pytest`.

## Codex Execution Integrity Rules

These rules apply to every implementation, validation, audit, and data-generation task.

1. Output existence is not evidence of correctness.
2. Do not use fixed values, empty values, zeros, constant booleans, placeholders, or hard-coded pass results in place of required computation.
3. A generator must not certify its own output as valid. Critical validation must re-read persisted artifacts and independently recompute checks.
4. Every major formal execution branch must also run through the same code path in reduced form in the smoke profile. Smoke may reduce counts, seeds, or steps; it must not remove required logic.
5. Every critical validator must have at least one negative test proving that corrupted, incomplete, duplicated, or placeholder output fails.
6. Configuration files must be the single source of truth for configurable formal values. Do not duplicate formal constants in implementation code.
7. Missing, unknown, uncomputed, or unimplemented results must fail closed. Do not emit plausible-looking defaults.
8. Before implementation, identify the cheapest fake implementation that could satisfy the visible schema and add an independent check or negative test that makes it fail.
9. Separate generation, audit, and validation responsibilities when a task produces evidence used to judge its own correctness.
10. If the specification cannot be satisfied, stop and report the conflict. Do not weaken dimensions, sample counts, checks, or execution paths without explicit approval.

See `docs/development/CODEX_EXECUTION_INTEGRITY.md` and use `docs/development/CODEX_TASK_CONTRACT_TEMPLATE.md` for new Codex implementation contracts.

## RC1 Freeze Archive Handling

- Keep `DEPT2_FullSpecIntegratedClosedLoopRunner_RC1_Freeze.zip` as a frozen reference archive unless a task explicitly says to replace it.
- Do not expand the archive into the repository as part of archive-registration or documentation-only work.
- Do not commit bulk-expanded archive contents; avoid giant diffs by migrating only small, reviewed slices in future PRs.
- Read `DEPT2_FullSpecIntegratedClosedLoopRunner_RC1_Handoff.md` when it is present before planning implementation work derived from the archive.
- Treat archive extraction as a local review/planning step unless the requested task explicitly includes migrating selected files into the active codebase.

## DEPT2 / H-DEPT Closed-Loop Constraints

- Exploration modules must not update the Parameter Box directly.
- Parameter Box updates are limited to pressure from an upper layer.
- Exploration modules are limited to candidate generation, sandbox evaluation, and adoption judgment.
- Exploration module update frequency must be determined functionally from system state, entropy, residuals, and ambiguity.
- Fixed reference values must be read from the Parameter Box.
- Action modules must not directly access DEPT internals.
- Action modules must be treated as one-way actuators / translators.
- Watch audit work is an observation and analysis layer only; it must not become a controller, gate, actuator, or parameter update path.
- Task20f no-write dry-run proposals are proposal-only summaries and must not become controllers.
- Task20G pre-commit readiness audits are no-write evidence checks only and must not become controllers, gates, rollback mechanisms, or parameter update paths.
- No-write dry-run proposal generation is not a commit gate.
- Proposal candidates and readiness audits must not write to canonical parameters, G/K, world state, or ActionModule internals.

## Documentation and Implementation Discipline

- Prefer documenting assumptions before encoding them in implementation.
- Avoid over-specifying behavior that is not yet implemented.
- Keep README updates aligned with the actual repository state.
- Do not create `src/` or `tests/` contents unless the requested task explicitly includes implementation or tests.

## Task20H / Task20I Boundaries

- Task20H minimal evidence extraction is evidence-only and must not migrate RC1 runtime code.
- Task20I readiness re-run is not a commit gate and must not enable parameter updates.
- Extracted evidence must remain small, bounded, and reviewable.
## Task20J Boundary

- Task20J freezes the no-write parameter-adoption precheck contract.
- It classifies lower-parameter update candidates into blocked / watch_only / shadow_trial_candidate / commit_candidate without allowing canonical ParameterBox writes.
- Task21 may read the contract but must remain no-write unless a later explicit task changes that boundary.
## Task22 Boundary

- Task22 may run `python validation/task22_controlled_canonical_parameter_update_rc1.py` to attempt existing-runner execution before comparing `update_off`, `controlled_update_on`, `forced_bad_update_rollback`, and `real_watch_only_candidates`.
- Task22 declares `pandas` in `requirements.txt` for frozen RC1 runner execution, but must still report `passed: false` when the existing runner cannot execute; synthetic metrics or fixed-zero boundary flags must not produce a passing validation.
- Task22's intended canonical update scope is limited to bounded in-run lower ParameterBox state only.
- G/K writeback, world direct write, ActionModule internal DEPT connection, and ActionFrame direct generation boundaries remain closed.
- Task22 is not a Parameter Shadow Box redesign or Task21 classifier rebuild; Task21 real `watch_only` candidates must not be canonically updated.
