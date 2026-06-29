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

## Documentation and Implementation Discipline

- Prefer documenting assumptions before encoding them in implementation.
- Avoid over-specifying behavior that is not yet implemented.
- Keep README updates aligned with the actual repository state.
- Do not create `src/` or `tests/` contents unless the requested task explicitly includes implementation or tests.
