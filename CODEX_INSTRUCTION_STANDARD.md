# Canonical Codex Instruction Standard

This file is the single source of truth for drafting Codex implementation instructions in this repository.

## Mandatory use rule

Whenever a user asks for a Codex instruction, implementation contract, repair instruction, or Codex handoff for this repository:

1. Read this file before drafting.
2. Do not draft from memory or from a previous task's wording.
3. Instantiate every required section below for the current task.
4. Do not omit a section silently. Mark it `Not applicable` with a reason when genuinely inapplicable.
5. Treat Codex as a worker that follows the shortest visible path. Close shortcut paths explicitly.

## Required instruction structure

### 1. Task identity

State explicitly:

- New task or existing task
- Repository
- Base branch
- Working branch
- Existing pull request, if any

### 2. Exact objective

State the exact output to implement and what is outside scope. Do not ask Codex to choose the design.

### 3. Source of truth

For every configurable value or behavior, identify one authoritative source. Do not duplicate configurable formal values in code and configuration.

### 4. Ordered implementation procedure

Describe the implementation in the order Codex must execute it. Avoid vague phrases such as “implement correctly”, “ensure robustness”, or “use best judgment”.

### 5. Critical requirement contracts

For every critical requirement, include all four items:

- **Requirement:** what must be true
- **Required implementation:** how it must be implemented
- **Prohibited shortcut:** the cheapest incorrect implementation Codex could use
- **Verification:** how a test or independent process proves it was implemented

A critical requirement is incomplete unless all four items are present.

### 6. Smoke execution contract

Smoke must execute the same logical path as formal execution. Only scale may be reduced. List every formal stage and confirm that smoke executes it.

### 7. Tests

Separate:

- Positive tests
- Negative tests

Tests must verify values and behavior, not only file, column, key, or function existence. Every critical validator must have at least one negative test.

### 8. Stop conditions

Codex must stop instead of improvising when required sources are missing, specifications conflict, required computation cannot be implemented, or fixed conditions would need to be weakened.

### 9. Acceptance criteria

Use measurable criteria. Do not accept file existence, command success, or booleans written by the implementation itself as sufficient evidence.

### 10. Completion report

Require Codex to report:

- Files changed
- Commands executed
- Positive tests executed
- Negative tests executed
- Unimplemented or unresolved items
- Confirmation that no placeholder, fixed-pass, or self-certification path remains

## Mandatory shortcut audit before finalizing the instruction

Before delivering any Codex instruction, answer these questions for every critical output:

1. What is the cheapest fake implementation that satisfies the visible schema?
2. Can fixed values, empty values, `true`, or `0` replace real computation?
3. Can the producer certify its own output?
4. Can smoke skip a formal branch?
5. Is there a negative test?
6. Is configuration the only source of truth?
7. Can unimplemented work be hidden behind plausible defaults?
8. Would the smallest fake implementation pass the proposed tests?

Do not deliver the instruction until the answer to item 8 is `No` for every critical output.
