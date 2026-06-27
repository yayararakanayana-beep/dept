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

## DEPT2 / H-DEPT Closed-Loop Constraints

- Exploration modules must not update the Parameter Box directly.
- Parameter Box updates are limited to pressure from an upper layer.
- Exploration modules are limited to candidate generation, sandbox evaluation, and adoption judgment.
- Exploration module update frequency must be determined functionally from system state, entropy, residuals, and ambiguity.
- Fixed reference values must be read from the Parameter Box.
- Action modules must not directly access DEPT internals.
- Action modules must be treated as one-way actuators / translators.

## Documentation and Implementation Discipline

- Prefer documenting assumptions before encoding them in implementation.
- Avoid over-specifying behavior that is not yet implemented.
- Keep README updates aligned with the actual repository state.
- Do not create `src/` or `tests/` contents unless the requested task explicitly includes implementation or tests.
