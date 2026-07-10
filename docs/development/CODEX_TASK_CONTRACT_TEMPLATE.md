# Codex Task Contract Template

## Task identity

- New or existing task:
- Repository:
- Base branch:
- Working branch:

## Objective

State the exact implementation outcome. Do not ask Codex to choose the design.

## Fixed inputs and configuration source

- Configuration file:
- Values that are fixed:
- Values that may vary:
- Stop conditions:

## Files allowed to change

List exact paths or bounded directories.

## Files forbidden to change

List protected implementation and specification paths.

## Required execution paths

Describe formal and smoke paths. Smoke must use the same logic with reduced scale.

## Generator / audit / validator separation

- Generator responsibilities:
- Audit responsibilities:
- Validator responsibilities:
- Which component writes the validation report:

## Adversarial shortcut audit

| Critical requirement | Cheapest fake implementation | Independent prevention | Required negative test |
|---|---|---|---|
|  |  |  |  |

The task contract is incomplete until every critical requirement has a row.

## Mandatory negative tests

List concrete artifact corruptions or omissions and the expected validator failure.

## Acceptance criteria

Use measurable criteria. File or key existence alone is insufficient.

## PR body requirements

Require the implementer to report:

- Actual execution paths run
- Negative tests run
- Configuration source used
- Any unimplemented or deferred computation
- Why no placeholder or self-certification path remains
